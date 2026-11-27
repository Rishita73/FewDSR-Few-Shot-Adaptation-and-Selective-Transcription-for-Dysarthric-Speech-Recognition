"""Run on a machine with torch+transformers:  python -m experiments.check_backend [adapter_dir]
Smoke-tests the real backend on synthetic audio and validates the record format."""
import sys, json, tempfile, os
import numpy as np
from core.whisper_backend import WhisperBackend
from core.metrics import normalize_text
from experiments import common as C, validate_raw as V
from core.data import Utt

b = WhisperBackend(adapter_dir=sys.argv[1] if len(sys.argv) > 1 else None, use_vad=False)
print("device", b.device, "| null id", b.null_id, "| sot id", b.sot_id, "| eos", b.tok.eos_token_id)
sr = 16000
t = np.arange(sr * 3) / sr
cases = {"tone": (0.3 * np.sin(2 * np.pi * 150 * t)).astype(np.float32),
         "silence": np.zeros(sr * 3, np.float32),
         "noise": (0.003 * np.random.default_rng(0).standard_normal(sr * 3)).astype(np.float32)}
recs = []
for name, x in cases.items():
    tr = b.transcribe(x, sr)
    print(f"{name:8} -> {tr.text!r}  words={len(tr.tokens)}  sot-null={tr.first_step_null_logit:.2f}  rtf={tr.rtf:.2f}")
    recs.append(C.transcription_record(tr, Utt("X", "s", name, "reference", False, "unknown"), "X", 0, "baseline", "test", 3.0))
d = tempfile.mkdtemp(); p = C.raw_path(d, "X", 0, "baseline"); C.write_jsonl(p, recs)
errs, stats = V.validate_file(p)
print("record validation:", "OK" if not errs else errs[:5], stats)
sys.exit(1 if errs else 0)
