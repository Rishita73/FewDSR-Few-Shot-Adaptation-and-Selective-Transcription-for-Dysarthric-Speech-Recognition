"""Part 3 statistics over raw records: speaker WER, paired Wilcoxon, speaker-level bootstrap CIs.

Unit of analysis matters and is reported explicitly:
* utterance-level Wilcoxon pools utterances of all speakers -> utterances are NOT independent
  (they are nested in speakers), so its p-value is optimistic. We therefore also report the
  speaker-level Wilcoxon (n = number of speakers; with n speakers the smallest possible two-sided
  p is 2 / 2**n) and a speaker-level paired bootstrap CI of the WER difference.
* The bootstrap resamples SPEAKERS with replacement (seed = CFG.seed).
"""
from __future__ import annotations
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from fewdsr_config import CFG
from core import metrics as M


def only_test(recs: Sequence[dict]) -> List[dict]:
    return [r for r in recs if r["split"] == "test"]


def speaker_wer(recs: Sequence[dict]) -> Optional[float]:
    t = only_test(recs)
    if not t:
        return None
    return M.corpus_wer([r["ref"] for r in t], [r["hyp"] for r in t])["wer"]


def per_utt_wer(recs: Sequence[dict]) -> Dict[str, float]:
    return {r["wav"]: M.wer(r["ref"], r["hyp"]) for r in only_test(recs)}


def bootstrap_ci(values: Sequence[float], n_boot: int = 1000, seed: int = CFG.seed,
                 alpha: float = 0.05) -> Optional[Tuple[float, float]]:
    """Percentile CI of the MEAN over resampled speakers. None when < 2 speakers."""
    v = np.asarray(values, dtype=float)
    if v.size < 2:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(n_boot, v.size))
    means = v[idx].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def wilcoxon(a: Sequence[float], b: Sequence[float]) -> dict:
    """Two-sided Wilcoxon signed-rank on paired samples. p is None if undefined (all differences 0, n < 1)."""
    from scipy.stats import wilcoxon as _w
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    res = {"n_pairs": int(d.size), "n_nonzero": int((d != 0).sum()),
           "median_diff": float(np.median(d)) if d.size else None, "p": None}
    if res["n_nonzero"] == 0:
        return res
    try:
        res["p"] = float(_w(a, b, zero_method="wilcox", alternative="two-sided").pvalue)
    except ValueError:
        pass
    return res


def paired_comparison(recs_a: Dict[str, List[dict]], recs_b: Dict[str, List[dict]],
                      n_boot: int = 1000, seed: int = CFG.seed) -> dict:
    """A vs B (e.g. baseline vs lora K=10) over the speakers present in BOTH.
    diff = WER_A - WER_B (positive: B better). Utterances paired by wav path."""
    spk = sorted(set(recs_a) & set(recs_b))
    ua, ub, sa, sb = [], [], [], []
    for s in spk:
        ma, mb = per_utt_wer(recs_a[s]), per_utt_wer(recs_b[s])
        common = sorted(set(ma) & set(mb))
        ua += [ma[w] for w in common]; ub += [mb[w] for w in common]
        wa, wb = speaker_wer(recs_a[s]), speaker_wer(recs_b[s])
        if wa is not None and wb is not None:
            sa.append(wa); sb.append(wb)
    diffs = np.asarray(sa) - np.asarray(sb)
    out = {"speakers": spk, "n_speakers": len(sa),
           "mean_wer_a": float(np.mean(sa)) if sa else None, "mean_wer_b": float(np.mean(sb)) if sb else None,
           "mean_diff": float(diffs.mean()) if diffs.size else None,
           "diff_ci95": bootstrap_ci(diffs, n_boot, seed) if diffs.size else None,
           "wilcoxon_utterance_level": wilcoxon(ua, ub),
           "wilcoxon_speaker_level": wilcoxon(sa, sb)}
    out["diff_ci95"] = list(out["diff_ci95"]) if out["diff_ci95"] else None
    return out


def scaling_analysis(recs: Dict[Tuple[str, int, str], List[dict]], n_boot: int = 1000,
                     seed: int = CFG.seed) -> dict:
    """recs: (speaker, k, condition) -> records. Returns K list, mean speaker WER and 95 % CI per K,
    speakers per K (K can have fewer speakers: infeasible budgets are missing, never imputed)."""
    per: Dict[str, Dict[int, float]] = {}
    for (s, k, _c), rs in recs.items():
        w = speaker_wer(rs)
        if w is not None:
            per.setdefault(s, {})[k] = w
    ks = sorted({k for d in per.values() for k in d})
    mean, ci, nsp = [], [], []
    for k in ks:
        vals = [d[k] for d in per.values() if k in d]
        mean.append(float(np.mean(vals)))
        c = bootstrap_ci(vals, n_boot, seed)
        ci.append(list(c) if c else None)
        nsp.append(len(vals))
    return {"K": ks, "wer_mean": mean, "wer_ci95": ci, "n_speakers": nsp,
            "per_speaker": {s: {str(k): v for k, v in sorted(d.items())} for s, d in sorted(per.items())}}
