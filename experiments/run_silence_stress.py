"""Objective 5 stress test on REAL TORGO audio (needs torch + the model; run on the Part 2 machine).

For each of N test utterances per speaker (taken from the speaker's TEST set, deterministic) builds:
  zeros  : 3.0 s of digital silence                      (ref = "")
  noise  : 3.0 s of low-level seeded Gaussian noise       (ref = "")
  pause  : the real utterance with a 2.2 s silence inserted at its midpoint (ref = original text)
and decodes each with the backend with and without the VAD. Raw outputs go to results/stress/stress.jsonl;
`core.eval_calibration.stress_hallucination` turns them into rates using gamma fitted on VALIDATION data.
    python -m experiments.run_silence_stress --manifest data/manifest.json --speakers F04 M01 --n 10
"""
from __future__ import annotations
import argparse, json, os
import numpy as np
from fewdsr_config import CFG
from core import data as D
from core.audio_io import load_audio
from experiments import common as C

NOISE_RMS = 0.002        # about -54 dBFS


def make_clips(utt_audio: np.ndarray, seed_key: str, pause_s: float = 2.2, sil_s: float = 3.0):
    sr = CFG.sample_rate
    import zlib
    rng = np.random.default_rng(zlib.crc32(f"{CFG.seed}-{seed_key}".encode("utf-8")))   # stable across runs
    mid = len(utt_audio) // 2
    pause = np.zeros(int(pause_s * sr), dtype=np.float32)
    return {
        "zeros": (np.zeros(int(sil_s * sr), dtype=np.float32), ""),
        "noise": ((rng.standard_normal(int(sil_s * sr)) * NOISE_RMS).astype(np.float32), ""),
        "pause": (np.concatenate([utt_audio[:mid], pause, utt_audio[mid:]]).astype(np.float32), None)}


def run_stress(backend_factory, utts, load, n_per_speaker: int, speakers, n_val: int, max_test: int, log=print):
    recs = []
    for spk in speakers:
        sp = C.speaker_splits(utts, spk, n_val, max_test)[0]
        chosen = sp.test[:n_per_speaker]
        for use_vad in (False, True):
            backend = backend_factory(use_vad)
            for u in chosen:
                audio = load(u.wav)
                for kind, (clip, ref) in make_clips(audio, f"{spk}-{os.path.basename(u.wav)}").items():
                    tr = backend.transcribe(clip, CFG.sample_rate)
                    rec = C.transcription_record(tr, u, spk, 0, "baseline", "test", len(clip) / CFG.sample_rate)
                    rec.update({"kind": kind, "vad": use_vad, "ref": u.text if ref is None else ref})
                    recs.append(rec)
            log(f"{spk} vad={use_vad}: {len(chosen)} utterances x 3 clips")
    return recs


def main(argv=None, backend_factory=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifest.json")
    ap.add_argument("--speakers", nargs="*")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--n-val", type=int, default=10)
    ap.add_argument("--max-test", type=int, default=100)
    ap.add_argument("--out", default="results/stress/stress.jsonl")
    a = ap.parse_args(argv)
    utts = D.load_manifest(a.manifest)
    spks = C.select_speakers(utts, a.speakers)
    if backend_factory is None:
        from core.whisper_backend import WhisperBackend
        backend_factory = lambda vad: WhisperBackend(use_vad=vad)
    recs = run_stress(backend_factory, utts, load_audio, a.n, spks, a.n_val, a.max_test)
    C.write_jsonl(a.out, recs)
    print(f"{len(recs)} stress records -> {a.out}")


if __name__ == "__main__":
    main()
