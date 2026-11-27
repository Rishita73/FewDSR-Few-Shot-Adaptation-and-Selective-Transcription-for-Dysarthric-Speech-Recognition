"""TORGO manifest, K-shot sampling and Leave-One-Speaker-Out splits.
Pure python/numpy: runs without torch or audio libraries."""
from __future__ import annotations
import json, os, random, re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Sequence

from fewdsr_config import CFG
from core.metrics import normalize_text


@dataclass
class Utt:
    speaker: str
    session: str
    wav: str
    text: str
    is_control: bool
    severity: str          # 'control' | 'mild' | 'moderate' | 'severe' | 'unknown'
    mic: str = "headMic"


def _usable_prompt(txt: str) -> bool:
    """TORGO prompts that are image descriptions ('[...]'), file refs or
    'xxx' placeholders are not transcripts of the audio -> skip."""
    t = txt.strip()
    return bool(t) and not t.startswith("[") and "input/" not in t and "xxx" not in t.lower()


def build_manifest(torgo_root: str, mic: str = "headMic") -> List[Utt]:
    """Expected layout (standard TORGO release):
        <root>/<SPK>/Session<N>/wav_<mic>/<id>.wav
        <root>/<SPK>/Session<N>/prompts/<id>.txt
    """
    utts: List[Utt] = []
    if not os.path.isdir(torgo_root):
        raise FileNotFoundError(f"TORGO root not found: {torgo_root}")
    for spk in sorted(os.listdir(torgo_root)):
        sp_dir = os.path.join(torgo_root, spk)
        if not os.path.isdir(sp_dir):
            continue
        is_ctl = spk.upper().startswith("FC") or spk.upper().startswith("MC")
        sev = "control" if is_ctl else CFG.torgo_severity.get(spk.upper(), "unknown")
        for sess in sorted(os.listdir(sp_dir)):
            wav_dir = os.path.join(sp_dir, sess, f"wav_{mic}")
            pr_dir = os.path.join(sp_dir, sess, "prompts")
            if not (os.path.isdir(wav_dir) and os.path.isdir(pr_dir)):
                continue
            for fn in sorted(os.listdir(wav_dir)):
                if not fn.lower().endswith(".wav"):
                    continue
                pf = os.path.join(pr_dir, os.path.splitext(fn)[0] + ".txt")
                if not os.path.isfile(pf):
                    continue
                with open(pf, encoding="utf-8", errors="ignore") as f:
                    txt = f.read().strip()
                if _usable_prompt(txt):
                    utts.append(Utt(spk, sess, os.path.join(wav_dir, fn), txt, is_ctl, sev, mic))
    return utts


def save_manifest(utts: Sequence[Utt], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(u) for u in utts], f, ensure_ascii=False, indent=1)


def load_manifest(path: str) -> List[Utt]:
    with open(path, encoding="utf-8") as f:
        return [Utt(**d) for d in json.load(f)]


@dataclass
class SpeakerSplit:
    speaker: str
    k: int
    calibration: List[Utt]      # the K utterances used to train LoRA
    validation: List[Utt]       # used to fit T, gamma, tau (never test)
    test: List[Utt]


def make_speaker_split(utts: Sequence[Utt], speaker: str, k: int, n_val: int = 10,
                       seed: int = CFG.seed) -> SpeakerSplit:
    """Leave-One-Speaker-Out: `speaker` is the held-out target. Calibration,
    validation and test are TEXT-DISJOINT (TORGO repeats prompts; sharing a
    sentence between calibration and test would leak the answer)."""
    mine = [u for u in utts if u.speaker == speaker]
    if not mine:
        raise ValueError(f"no utterances for speaker {speaker}")
    by_text: Dict[str, List[Utt]] = {}
    for u in mine:
        by_text.setdefault(normalize_text(u.text), []).append(u)
    texts = sorted(by_text)
    rng = random.Random(f"{seed}-{speaker}")      # string seed: stable across runs
    rng.shuffle(texts)

    cal: List[Utt] = []; val: List[Utt] = []; used = set()
    for t in texts:                                # one utterance per unique prompt
        if len(cal) >= k:
            break
        cal.append(by_text[t][0]); used.add(t)
    for t in texts:
        if len(val) >= n_val:
            break
        if t not in used:
            val.append(by_text[t][0]); used.add(t)
    test = [u for t in texts if t not in used for u in by_text[t]]
    if k > 0 and len(cal) < k:
        raise ValueError(f"{speaker}: only {len(cal)} unique prompts, cannot draw K={k}")
    return SpeakerSplit(speaker, k, cal, val, test)


def nested_budget_splits(utts: Sequence[Utt], speaker: str, budgets=CFG.budgets, n_val: int = 10,
                         seed: int = CFG.seed) -> Dict[int, SpeakerSplit]:
    """Same validation/test sets for every K so curves are comparable; the K=5
    calibration set is a subset of K=10, etc. (nested)."""
    kmax = max(budgets)
    big = make_speaker_split(utts, speaker, kmax, n_val, seed)
    out = {}
    for k in budgets:
        out[k] = SpeakerSplit(speaker, k, big.calibration[:k], big.validation, big.test)
    return out
