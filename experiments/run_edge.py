"""Objective 6: INT8 CTranslate2 vs FP32 Hugging Face on CPU. Measures ONLY what it measures.

  python -m experiments.run_edge --check                         # is ctranslate2/faster-whisper importable? CPU string?
  python -m experiments.run_edge --manifest data/manifest.json --speaker F04 --k 10 --n 30 [--adapter artifacts/adapters/F04_K10]
Writes results/edge/edge.json. Each backend is measured in its OWN subprocess (so peak RSS is not polluted
by the other model). RTF = total decode time / total audio time; the reported RTF is the MEDIAN over
`--repeats` passes (default 3) after 1 untimed warm-up pass over the same utterances. WER is computed on the
same test utterances for both. The CPU model string is recorded; nothing is extrapolated to other machines."""
from __future__ import annotations
import argparse, json, os, platform, subprocess, sys
from typing import Callable, Dict, List, Sequence
import numpy as np

from fewdsr_config import CFG
from core import metrics as M


def cpu_string() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine() or "unknown"


def _peak_rss_windows_mb() -> float:
    """Peak working set of this process via kernel32/psapi (no extra dependency)."""
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ps = ctypes.WinDLL("psapi", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
    if not ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        return float("nan")
    return pmc.PeakWorkingSetSize / (1024.0 * 1024.0)


def peak_rss_mb() -> float:
    if sys.platform == "win32":
        try:
            return _peak_rss_windows_mb()
        except Exception:
            return float("nan")                                       # report NaN rather than guess
    import resource                                                   # Unix only; imported lazily
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss          # KB on Linux, bytes on macOS
    return r / (1024.0 * 1024.0) if sys.platform == "darwin" else r / 1024.0


def measure_backend(backend, audios: Sequence[np.ndarray], refs: Sequence[str], repeats: int = 3,
                    warmup: int = 1, clock: Callable[[], float] = None) -> dict:
    """Pure measurement logic (unit-tested with a fake backend). Uses backend-reported latency_s."""
    if repeats < 3:
        raise ValueError("repeats must be >= 3 (handoff requires median of >= 3 runs)")
    sr = CFG.sample_rate
    for _ in range(warmup):
        for a in audios:
            backend.transcribe(a, sr)
    rtfs, hyps = [], []
    for rep in range(repeats):
        lat = aud = 0.0
        cur = []
        for a in audios:
            tr = backend.transcribe(a, sr)
            lat += tr.latency_s; aud += len(a) / sr
            cur.append(tr.text)
        rtfs.append(lat / aud if aud else float("nan"))
        hyps = cur                                                   # greedy decoding: passes should agree
    c = M.corpus_wer(list(refs), hyps)
    return {"rtf_median": float(np.median(rtfs)), "rtf_runs": [float(x) for x in rtfs], "wer": c["wer"],
            "n_utts": len(audios), "audio_s": float(sum(len(a) for a in audios) / sr)}


def _child(args) -> None:
    from core import data as D
    from core.audio_io import load_audio
    from experiments import common as C
    utts = D.load_manifest(args.manifest)
    splits = C.speaker_splits(utts, args.speaker, args.n_val, args.max_test)
    sp = splits[args.k] if args.k in splits else splits[0]            # val/test identical for every K
    test = sp.test[: args.n]
    audios = [load_audio(u.wav) for u in test]; refs = [u.text for u in test]
    if args.mode == "fp32":
        from core.ct2_backend import dir_size_bytes
        from core.whisper_backend import WhisperBackend
        backend = WhisperBackend(model_name=args.hf_dir or CFG.base_model, device="cpu", compute_sot_null=False)
        size = dir_size_bytes(args.hf_dir) if args.hf_dir else None
    else:
        from core.ct2_backend import CT2Backend, dir_size_bytes
        backend = CT2Backend(args.ct2_dir, device="cpu", compute_type="int8")
        size = dir_size_bytes(args.ct2_dir)
    res = measure_backend(backend, audios, refs, repeats=args.repeats)
    res.update({"mode": args.mode, "peak_rss_mb": peak_rss_mb(), "model_size_bytes": size})
    print("RESULT " + json.dumps(res))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--manifest", default="data/manifest.json")
    ap.add_argument("--speaker")
    ap.add_argument("--k", type=int, default=0)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--n-val", type=int, default=10)
    ap.add_argument("--max-test", type=int, default=100)
    ap.add_argument("--adapter", default=None, help="LoRA adapter dir to merge before conversion (omit for zero-shot)")
    ap.add_argument("--work", default="artifacts/edge")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default="results/edge/edge.json")
    ap.add_argument("--mode", choices=["fp32", "int8"], help=argparse.SUPPRESS)
    ap.add_argument("--hf-dir", help=argparse.SUPPRESS)
    ap.add_argument("--ct2-dir", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.mode:
        _child(a); return 0
    if a.check:
        for mod in ("ctranslate2", "faster_whisper", "torch", "transformers"):
            try:
                m = __import__(mod); print(f"{mod}: OK {getattr(m, '__version__', '')}")
            except Exception as e:
                print(f"{mod}: MISSING ({e.__class__.__name__})")
        print("cpu:", cpu_string()); return 0
    if not a.speaker:
        ap.error("--speaker is required")
    from core.ct2_backend import convert_to_ct2, merge_lora_to_hf
    hf_dir = merge_lora_to_hf(a.adapter, os.path.join(a.work, "hf_merged"))
    ct2_dir = convert_to_ct2(hf_dir, os.path.join(a.work, "ct2_int8"))
    common = ["--manifest", a.manifest, "--speaker", a.speaker, "--k", str(a.k), "--n", str(a.n),
              "--n-val", str(a.n_val), "--max-test", str(a.max_test), "--repeats", str(a.repeats)]
    out: Dict[str, dict] = {}
    for mode, extra in (("fp32", ["--hf-dir", hf_dir]), ("int8", ["--ct2-dir", ct2_dir])):
        p = subprocess.run([sys.executable, "-m", "experiments.run_edge", "--mode", mode, *common, *extra],
                           capture_output=True, text=True)
        line = next((l for l in p.stdout.splitlines() if l.startswith("RESULT ")), None)
        if p.returncode != 0 or line is None:
            raise SystemExit(f"{mode} measurement failed:\n{p.stdout[-800:]}\n{p.stderr[-1500:]}")
        out[mode] = json.loads(line[7:])
    summ = {"cpu": cpu_string(), "speaker": a.speaker, "k": a.k, "adapter": a.adapter, "n_utts": out["fp32"]["n_utts"],
            "repeats": a.repeats, "fp32_rtf": out["fp32"]["rtf_median"], "int8_rtf": out["int8"]["rtf_median"],
            "fp32_wer": out["fp32"]["wer"], "int8_wer": out["int8"]["wer"],
            "fp32_peak_rss_mb": out["fp32"]["peak_rss_mb"], "int8_peak_rss_mb": out["int8"]["peak_rss_mb"],
            "fp32_model_bytes": out["fp32"]["model_size_bytes"], "int8_model_bytes": out["int8"]["model_size_bytes"],
            "int8_logits_available": False,
            "note": "FP32 = merged HF Whisper on CPU; INT8 = CTranslate2 int8. Stage 3/4 need raw logits, unavailable on INT8."}
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(summ, f, indent=1)
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())