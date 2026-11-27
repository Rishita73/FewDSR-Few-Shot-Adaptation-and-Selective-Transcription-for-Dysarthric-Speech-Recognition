"""Few-shot cross-attention LoRA (Objective 2).
python -m experiments.run_adapt --manifest data/manifest.json --speakers F01 M01 --budgets 5 10 20 40 --max-test 100
Evaluates on the SAME val/test sets as run_baseline (guaranteed by common.speaker_splits)."""
import argparse, json, os
from fewdsr_config import CFG
from core import data as D
from core import metrics as M
from core.audio_io import load_audio
from experiments import common as C


class RealLoraAdapter:
    """Trains LoRA for one (speaker, K) and returns (backend, info). Torch required."""
    def __init__(self, device=None, epochs=15, lr=1e-3, batch_size=4, patience=3, use_vad=True):
        self.kw = dict(epochs=epochs, lr=lr, batch_size=batch_size, patience=patience)
        self.device, self.use_vad = device, use_vad

    def adapt(self, speaker, k, split, adapter_dir):
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        from core.lora import build_lora_model, count_trainable, train_lora
        from core.whisper_backend import WhisperBackend
        device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        processor = WhisperProcessor.from_pretrained(CFG.base_model)
        model = build_lora_model(WhisperForConditionalGeneration.from_pretrained(CFG.base_model))
        tr, tot, pct = count_trainable(model)
        backend = WhisperBackend(model=model, processor=processor, device=device, use_vad=self.use_vad)
        refs = [u.text for u in split.validation]

        def eval_fn():
            hyps = [backend.transcribe(load_audio(u.wav), CFG.sample_rate).text for u in split.validation]
            return M.corpus_wer(refs, hyps)["wer"]

        # train on EXACTLY the audio the backend will see at inference (same VAD trim/pad)
        prep = lambda path: backend._prep(load_audio(path), CFG.sample_rate)
        backend.compute_sot_null = False              # skip the extra forward pass during validation
        try:
            info = train_lora(model, processor, split.calibration, prep, eval_fn=eval_fn,
                              device=device, seed=CFG.seed, **self.kw)
        finally:
            backend.compute_sot_null = True
        info.update({"trainable_params": tr, "total_params": tot, "trainable_pct": pct, "k": k, "speaker": speaker})
        os.makedirs(adapter_dir, exist_ok=True)
        model.save_pretrained(adapter_dir)
        with open(os.path.join(adapter_dir, "train_info.json"), "w") as f:
            json.dump(info, f, indent=1)
        return backend, info


def main(argv=None, adapter=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifest.json")
    ap.add_argument("--speakers", nargs="*")
    ap.add_argument("--budgets", nargs="*", type=int, default=[b for b in CFG.budgets if b > 0])
    ap.add_argument("--out", default="results/raw")
    ap.add_argument("--adapters", default="artifacts/adapters")
    ap.add_argument("--max-test", type=int, default=100)
    ap.add_argument("--n-val", type=int, default=10)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--limit", type=int, default=None, help="smoke runs only")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if 0 in a.budgets:
        raise SystemExit("K=0 is the baseline: use run_baseline")
    utts = D.load_manifest(a.manifest)
    spks = C.select_speakers(utts, a.speakers)
    adapter = adapter or RealLoraAdapter(epochs=a.epochs, lr=a.lr)
    for spk in spks:
        splits = C.speaker_splits(utts, spk, a.n_val, a.max_test)
        base_test = [u.wav for u in splits[0].test]
        for k in a.budgets:
            if k not in splits:
                print(f"{spk}: K={k} infeasible (too few unique prompts) -> skipped, recorded as missing"); continue
            sp = splits[k]
            assert [u.wav for u in sp.test] == base_test, "test set must be identical across K"
            assert len(sp.calibration) == k
            path = C.raw_path(a.out, spk, k, "lora")
            if os.path.exists(path) and not a.force:
                print(f"skip {path} (exists)"); continue
            backend, info = adapter.adapt(spk, k, sp, os.path.join(a.adapters, f"{spk}_K{k}"))
            val, test = sp.validation[: a.limit], sp.test[: a.limit]
            recs = C.evaluate_utts(backend, val, load_audio, spk, k, "lora", "val")
            recs += C.evaluate_utts(backend, test, load_audio, spk, k, "lora", "test")
            C.write_jsonl(path, recs)
            s = C.summarize(recs)
            print(f"{spk} K={k}: test WER {s['wer']*100:.1f}%  CER {s['cer']*100:.1f}%  ins {s['insertion_rate']*100:.1f}%  "
                  f"best_epoch {info.get('best_epoch')}  trainable {info.get('trainable_pct', float('nan')):.3f}% -> {path}")


if __name__ == "__main__":
    main()
