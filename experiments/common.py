"""Shared helpers for Part 2 experiment scripts (pure python; backend-agnostic)."""
from __future__ import annotations
import json, math, os, random
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
from fewdsr_config import CFG
from core import metrics as M
from core.data import Utt, SpeakerSplit, nested_budget_splits
from core.interfaces import ASRBackend

TOPK = 20


def feasible_budgets(utts: Sequence[Utt], speaker: str, n_val: int) -> List[int]:
    """Budgets from CFG.budgets that fit the speaker's UNIQUE prompt count, leaving
    n_val validation prompts and at least 1 test prompt. 0 is always feasible."""
    uniq = len({M.normalize_text(u.text) for u in utts if u.speaker == speaker})
    return [b for b in CFG.budgets if b == 0 or b + n_val < uniq]


def speaker_splits(utts: Sequence[Utt], speaker: str, n_val: int = 10,
                   max_test: Optional[int] = None) -> Dict[int, SpeakerSplit]:
    """THE ONLY way to build splits in Part 2/3. Always derived from the full feasible
    budget list so baseline and every K share identical validation and test sets."""
    budgets = feasible_budgets(utts, speaker, n_val)
    splits = nested_budget_splits(utts, speaker, tuple(budgets), n_val)
    test = sorted(splits[budgets[0]].test, key=lambda u: u.wav)
    if max_test is not None and len(test) > max_test:
        rng = random.Random(f"{CFG.seed}-test-{speaker}")
        test = sorted(rng.sample(test, max_test), key=lambda u: u.wav)
    for s in splits.values():
        s.test = test
    return splits


def _clean(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def transcription_record(tr, utt: Utt, speaker: str, k: int, condition: str, split: str, audio_s: float) -> dict:
    return {
        "speaker": speaker, "k": k, "condition": condition, "split": split,
        "wav": utt.wav, "ref": utt.text, "hyp": tr.text,
        "audio_s": round(float(audio_s), 4), "latency_s": round(float(tr.latency_s), 4),
        "first_step_null_logit": _clean(float(getattr(tr, "first_step_null_logit", float("nan")))),
        "words": [{"word": t.word, "topk_logits": [float(v) for v in t.topk_logits],
                   "null_logit": float(t.null_logit)} for t in tr.tokens],
    }


def evaluate_utts(backend: ASRBackend, utts: Sequence[Utt], load_audio: Callable[[str], np.ndarray],
                  speaker: str, k: int, condition: str, split: str,
                  log: Callable[[str], None] = print) -> List[dict]:
    recs = []
    for i, u in enumerate(utts):
        audio = load_audio(u.wav)
        tr = backend.transcribe(audio, CFG.sample_rate)
        recs.append(transcription_record(tr, u, speaker, k, condition, split, len(audio) / CFG.sample_rate))
        if (i + 1) % 25 == 0:
            log(f"  {speaker} K={k} {condition} {split}: {i + 1}/{len(utts)}")
    return recs


def raw_path(out_dir: str, speaker: str, k: int, condition: str) -> str:
    return os.path.join(out_dir, f"{speaker}_K{k}_{condition}.jsonl")


def write_jsonl(path: str, records: Sequence[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)                 # atomic: a crashed run never leaves a half file


def read_jsonl(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def summarize(records: Sequence[dict], split: str = "test") -> dict:
    rs = [r for r in records if r["split"] == split]
    refs, hyps = [r["ref"] for r in rs], [r["hyp"] for r in rs]
    c = M.corpus_wer(refs, hyps)
    return {"n_utts": len(rs), "wer": c["wer"], "cer": M.corpus_cer(refs, hyps),
            "insertion_rate": c["insertion_rate"], "n_words": c["n_ref"]}


def select_speakers(utts: Sequence[Utt], requested: Optional[Sequence[str]], include_controls: bool = False):
    avail = sorted({u.speaker for u in utts if include_controls or not u.is_control})
    if not requested:
        return avail
    missing = [s for s in requested if s not in avail]
    if missing:
        raise ValueError(f"speakers not in manifest: {missing}; available: {avail}")
    return list(requested)
