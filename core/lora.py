"""LoRA on decoder cross-attention q/v (Part 2).  Torch/PEFT code, UNVERIFIED in the
authoring sandbox -> run `python -m experiments.check_lora` first.
"""
from __future__ import annotations
import copy, random
from typing import Callable, List, Optional, Sequence, Tuple
import numpy as np

from fewdsr_config import CFG


def build_lora_model(base):
    """Wrap a WhisperForConditionalGeneration with cross-attention-only LoRA and
    VERIFY that exactly 2 x decoder_layers modules were wrapped, all cross-attn."""
    from peft import LoraConfig, get_peft_model
    from peft.tuners.lora import LoraLayer
    cfg = LoraConfig(r=CFG.lora_r, lora_alpha=CFG.lora_alpha, lora_dropout=CFG.lora_dropout,
                     target_modules=CFG.lora_target_regex, bias="none")
    model = get_peft_model(base, cfg)
    wrapped = [n for n, m in model.named_modules() if isinstance(m, LoraLayer)]
    expected = 2 * base.config.decoder_layers
    bad = [n for n in wrapped if "decoder.layers" not in n or "encoder_attn" not in n]
    if len(wrapped) != expected or bad:
        raise RuntimeError(f"LoRA wrapped {len(wrapped)} modules (expected {expected}); unexpected: {bad[:5]}. "
                           f"Fix fewdsr_config.lora_target_regex.")
    return model


def count_trainable(model) -> Tuple[int, int, float]:
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total, 100.0 * trainable / total


def _make_batch(feats: List, label_ids: List[List[int]], pad_id: int, device):
    import torch
    x = torch.stack(feats).to(device)
    L = max(len(l) for l in label_ids)
    y = torch.full((len(label_ids), L), -100, dtype=torch.long)
    for i, l in enumerate(label_ids):
        y[i, : len(l)] = torch.tensor(l)
    return x, y.to(device)


def encode_labels(tokenizer, text: str, sot_id: int) -> List[int]:
    """Labels = text + <|endoftext|> only. The 3 forced prefix tokens
    (<|en|><|transcribe|><|notimestamps|>) are masked with -100 so the loss
    adapts the TEXT; the leading <|startoftranscript|> is removed because the
    model prepends decoder_start_token_id itself when shifting labels right."""
    tokenizer.set_prefix_tokens(language="en", task="transcribe", predict_timestamps=False)
    ids = tokenizer(text).input_ids                     # [sot, en, transcribe, notimestamps, ..., eot]
    if ids and ids[0] == sot_id:
        ids = ids[1:]
    return [-100] * 3 + ids[3:]


def encode_example(tokenizer, text: str, sot_id: int):
    """(decoder_input_ids, labels) for teacher forcing with the SAME prefix the decoder sees at inference.
    full = [sot, en, transcribe, notimestamps, text..., eot]
    decoder_input_ids = full[:-1]   (real prefix tokens, never padding)
    labels            = full[1:] with the 3 prefix predictions (en, transcribe, notimestamps) masked to -100.
    Passing labels alone makes HF shift them right and replace the masked prefix by PAD, so the text would be
    trained from [sot, pad, pad, pad] but decoded from [sot, en, transcribe, notimestamps]: a train/inference mismatch."""
    tokenizer.set_prefix_tokens(language="en", task="transcribe", predict_timestamps=False)
    full = list(tokenizer(text).input_ids)
    if not full or full[0] != sot_id or len(full) < 6:
        raise ValueError(f"unexpected tokenization for {text!r}: {full[:6]}")
    return full[:-1], [-100] * 3 + full[4:]


def _pad_decoder_batch(feats, examples, pad_id: int, device):
    import torch
    x = torch.stack(feats).to(device)
    L = max(len(d) for d, _ in examples)
    din = torch.full((len(examples), L), pad_id, dtype=torch.long)
    y = torch.full((len(examples), L), -100, dtype=torch.long)
    for i, (d, l) in enumerate(examples):
        din[i, : len(d)] = torch.tensor(d)
        y[i, : len(l)] = torch.tensor(l)
    return x, din.to(device), y.to(device)


def train_lora(model, processor, utts: Sequence, load_audio: Callable[[str], np.ndarray],
               eval_fn: Optional[Callable[[], float]] = None, epochs: int = 15, lr: float = 1e-3,
               batch_size: int = 4, patience: int = 3, seed: int = CFG.seed, device: str = "cpu",
               log: Callable[[str], None] = print) -> dict:
    """Train LoRA params only. `eval_fn()` must return VALIDATION WER (fraction) of the
    current in-memory model; best-val weights are restored at the end.
    Epoch 0 (untrained, LoRA B=0 => identical to base) is a candidate, so adaptation
    can never be worse than zero-shot on validation."""
    import torch
    torch.manual_seed(seed)
    rng = random.Random(seed)
    tok = processor.tokenizer
    sot = tok.convert_tokens_to_ids("<|startoftranscript|>")
    feats = [processor.feature_extractor(load_audio(u.wav), sampling_rate=CFG.sample_rate,
                                         return_tensors="pt").input_features[0] for u in utts]
    examples = [encode_example(tok, u.text, sot) for u in utts]
    params = [p for p in model.parameters() if p.requires_grad]
    if not params:
        raise RuntimeError("no trainable parameters; did you call build_lora_model?")
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.0)

    def snapshot():
        return {n: p.detach().clone() for n, p in model.named_parameters() if p.requires_grad}

    def evaluate():
        if eval_fn is None:
            return float("nan")
        model.eval(); model.config.use_cache = True
        w = eval_fn()
        return w

    best_w, best_state, best_epoch, bad = evaluate(), snapshot(), 0, 0
    history = [{"epoch": 0, "train_loss": None, "val_wer": best_w}]
    log(f"epoch 0 val WER {best_w:.3f}")
    n = len(utts)
    for ep in range(1, epochs + 1):
        model.train(); model.config.use_cache = False
        order = list(range(n)); rng.shuffle(order)
        losses = []
        for s in range(0, n, batch_size):
            idx = order[s: s + batch_size]
            x, din, y = _pad_decoder_batch([feats[i] for i in idx], [examples[i] for i in idx], tok.pad_token_id, device)
            loss = model(input_features=x, decoder_input_ids=din, labels=y).loss
            opt.zero_grad(); loss.backward(); opt.step()
            losses.append(float(loss.detach().cpu()))
        w = evaluate()
        history.append({"epoch": ep, "train_loss": float(np.mean(losses)), "val_wer": w})
        log(f"epoch {ep} loss {np.mean(losses):.4f} val WER {w:.3f}")
        if eval_fn is None:
            best_state, best_epoch = snapshot(), ep
            continue
        if w < best_w - 1e-9:
            best_w, best_state, best_epoch, bad = w, snapshot(), ep, 0
        else:
            bad += 1
            if bad >= patience:
                break
    with torch.no_grad():
        for n_, p in model.named_parameters():
            if n_ in best_state:
                p.copy_(best_state[n_])
    model.eval(); model.config.use_cache = True
    return {"best_epoch": best_epoch, "best_val_wer": best_w, "history": history}
