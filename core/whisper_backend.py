"""Real Whisper backend (Part 2).  !!! Written without access to torch/transformers in the
authoring sandbox: run `python -m experiments.check_backend` FIRST on your machine. !!!

Key design points
* RAW logits (generate(output_logits=True)), never `output_scores`, because HF logit
  processors set special tokens (incl. the no-speech token) to -inf in `scores`.
* One TokenInfo per WORD (core.word_align.group_into_words).
* first_step_null_logit = raw z(<|nospeech|>) at the <|startoftranscript|> position
  (OpenAI's definition of no-speech probability), via one extra decoder forward pass.
"""
from __future__ import annotations
import time
from typing import Optional
import numpy as np

from fewdsr_config import CFG
from core.interfaces import ASRBackend, Transcription
from core.vad_preprocessor import PausePreservingVAD
from core.word_align import steps_from_logits, group_into_words

MAX_SECONDS = 30.0          # Whisper short-form window; TORGO utterances are shorter


def special_token_ids(tok) -> set:
    """All special-token ids. Newer transformers releases removed `additional_special_tokens_ids`
    (AttributeError on WhisperTokenizer), so every attribute is optional; the caller also adds every id >= eos."""
    ids = set()
    for attr in ("all_special_ids", "additional_special_tokens_ids"):
        try:
            ids |= set(getattr(tok, attr) or [])
        except AttributeError:
            pass
    return ids


def resolve_nospeech_id(tokenizer) -> int:
    unk = getattr(tokenizer, "unk_token_id", None)
    for name in ("<|nospeech|>", "<|nocaptions|>"):
        tid = tokenizer.convert_tokens_to_ids(name)
        if tid is not None and tid != unk:
            return int(tid)
    raise RuntimeError("Could not find a <|nospeech|>/<|nocaptions|> token in this tokenizer")


class WhisperBackend(ASRBackend):
    is_simulated = False

    def __init__(self, model_name: str = CFG.base_model, adapter_dir: Optional[str] = None,
                 device: Optional[str] = None, topk: int = 20, use_vad: bool = True,
                 vad_pad_s: float = 0.2, max_new_tokens: int = 128,
                 model=None, processor=None, compute_sot_null: bool = True):
        import os, torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        if not os.environ.get("FEWDSR_HF_VERBOSE"):          # per-utterance generate() warnings flood the log
            from transformers.utils import logging as _hf_logging
            _hf_logging.set_verbosity_error()
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.processor = processor or WhisperProcessor.from_pretrained(model_name)
        if model is None:
            model = WhisperForConditionalGeneration.from_pretrained(model_name)
            if adapter_dir:
                from peft import PeftModel
                model = PeftModel.from_pretrained(model, adapter_dir)
        self.model = model.to(self.device)
        self.model.eval()
        self.tok = self.processor.tokenizer
        self.null_id = resolve_nospeech_id(self.tok)
        self.sot_id = self.tok.convert_tokens_to_ids("<|startoftranscript|>")
        self.special_ids = special_token_ids(self.tok)
        self.special_ids |= {i for i in range(self.tok.eos_token_id, len(self.tok))}  # all specials sit above eos
        self.k = topk
        self.use_vad = use_vad
        self.vad = PausePreservingVAD(CFG.sample_rate, CFG.vad_frame_ms, CFG.vad_hangover_ms)
        self.vad_pad = int(vad_pad_s * CFG.sample_rate)
        self.max_new_tokens = max_new_tokens
        self.compute_sot_null = compute_sot_null
        self.name = "whisper-lora" if adapter_dir or hasattr(model, "peft_config") else "whisper"

    # ------------------------------------------------------------------
    def _prep(self, audio: np.ndarray, sr: int) -> np.ndarray:
        audio = np.asarray(audio, dtype=np.float32)
        if sr != CFG.sample_rate:
            from core.audio_io import resample
            audio = resample(audio, sr, CFG.sample_rate)
        if self.use_vad and len(audio) > 0:
            res = self.vad.process(audio)
            if res["segments"]:
                s = max(0, int(res["segments"][0][0] * CFG.sample_rate) - self.vad_pad)
                e = min(len(audio), int(res["segments"][-1][1] * CFG.sample_rate) + self.vad_pad)
                audio = audio[s:e]
        return audio

    def transcribe(self, audio: np.ndarray, sr: int) -> Transcription:
        torch = self.torch
        dur_in = len(audio) / sr if sr else 0.0
        t0 = time.perf_counter()
        x = self._prep(audio, sr)
        if len(x) / CFG.sample_rate > MAX_SECONDS:
            raise ValueError(f"audio longer than {MAX_SECONDS}s is not supported (short-form only)")
        if len(x) < 400:                       # < 25 ms: nothing to decode
            return Transcription([], time.perf_counter() - t0, dur_in, self.name, False)
        feats = self.processor.feature_extractor(x, sampling_rate=CFG.sample_rate,
                                                 return_tensors="pt").input_features.to(self.device)
        with torch.no_grad():
            out = self.model.generate(
                input_features=feats, language="en", task="transcribe",
                num_beams=1, do_sample=False, max_new_tokens=self.max_new_tokens,
                return_dict_in_generate=True, output_logits=True)
            seq = out.sequences[0]
            raw = getattr(out, "logits", None)
            if raw is None:
                raise RuntimeError("generate() returned no raw logits (output_logits ignored by this transformers version?)")
            n = len(raw)
            if n == 0 and seq.shape[0] > 8:          # prompt is ~4 tokens; text was generated but no logits came back
                raise RuntimeError(f"generate() produced {seq.shape[0]} tokens but 0 raw-logit steps: output_logits not honoured")
            gen_ids = seq[-n:].tolist() if n else []       # robust to prompt being included or not
            logits = (torch.stack([l[0] for l in raw]).float().cpu().numpy()
                      if n else np.zeros((0, 1), np.float32))
            sot_null = self._sot_null(feats) if self.compute_sot_null else float("nan")
        if n:
            topk, null = steps_from_logits(gen_ids, logits, self.null_id, self.k)
            words = group_into_words(gen_ids, topk, null, lambda ids: self.tok.decode(ids), self.special_ids)
        else:
            words = []
        return Transcription(tokens=words, latency_s=time.perf_counter() - t0, audio_duration_s=dur_in,
                             backend=self.name, is_simulated=False, first_step_null_logit=sot_null)

    def _sot_null(self, feats) -> float:
        torch = self.torch
        dec = torch.tensor([[self.sot_id]], device=self.device)
        o = self.model(input_features=feats, decoder_input_ids=dec)
        return float(o.logits[0, -1, self.null_id].float().cpu())
