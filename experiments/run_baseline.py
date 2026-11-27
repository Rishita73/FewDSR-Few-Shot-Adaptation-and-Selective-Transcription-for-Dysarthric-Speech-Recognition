"""Zero-shot baseline (Objective 1).
python -m experiments.run_baseline --manifest data/manifest.json --speakers F01 M01 --max-test 100
Smoke run: add --limit 5 --out results/smoke   (never mix smoke and real outputs in one dir)."""
import argparse, os
from fewdsr_config import CFG
from core import data as D
from core.audio_io import load_audio
from experiments import common as C


def main(argv=None, backend_factory=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifest.json")
    ap.add_argument("--speakers", nargs="*")
    ap.add_argument("--out", default="results/raw")
    ap.add_argument("--max-test", type=int, default=100)
    ap.add_argument("--n-val", type=int, default=10)
    ap.add_argument("--limit", type=int, default=None, help="smoke runs only")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-vad", action="store_true")
    a = ap.parse_args(argv)
    utts = D.load_manifest(a.manifest)
    spks = C.select_speakers(utts, a.speakers)
    if backend_factory is None:
        from core.whisper_backend import WhisperBackend
        backend_factory = lambda: WhisperBackend(use_vad=not a.no_vad)
    backend = None
    for spk in spks:
        path = C.raw_path(a.out, spk, 0, "baseline")
        if os.path.exists(path) and not a.force:
            print(f"skip {path} (exists)"); continue
        sp = C.speaker_splits(utts, spk, a.n_val, a.max_test)[0]
        val, test = sp.validation[: a.limit], sp.test[: a.limit]
        backend = backend or backend_factory()
        recs = C.evaluate_utts(backend, val, load_audio, spk, 0, "baseline", "val")
        recs += C.evaluate_utts(backend, test, load_audio, spk, 0, "baseline", "test")
        C.write_jsonl(path, recs)
        s = C.summarize(recs)
        print(f"{spk}: test WER {s['wer']*100:.1f}%  CER {s['cer']*100:.1f}%  ins {s['insertion_rate']*100:.1f}%  "
              f"({s['n_utts']} utts) -> {path}")


if __name__ == "__main__":
    main()
