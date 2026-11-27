"""Dependency-free WER / CER / insertion / ECE / risk-coverage metrics.
(jiwer is listed in requirements for cross-checking, but nothing here needs it.)
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Sequence, Tuple
import numpy as np


def normalize_text(s: str) -> str:
    """Lower-case, drop punctuation/symbols, collapse whitespace.
    Uses Unicode categories (NOT \\w) so Devanagari vowel signs (category Mc/Mn)
    are preserved."""
    s = unicodedata.normalize("NFC", s).lower()
    s = "".join(" " if unicodedata.category(c)[0] in ("P", "S") else c for c in s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class EditCounts:
    substitutions: int
    deletions: int
    insertions: int
    n_ref: int

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    @property
    def rate(self) -> float:
        if self.n_ref == 0:
            return 0.0 if self.errors == 0 else float(self.errors)
        return self.errors / self.n_ref


def _align(ref: Sequence, hyp: Sequence) -> EditCounts:
    n, m = len(ref), len(hyp)
    d = np.zeros((n + 1, m + 1), dtype=np.int64)
    d[:, 0] = np.arange(n + 1)
    d[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + cost)
    i, j, S, D, I = n, m, 0, 0, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i, j] == d[i - 1, j - 1] + (0 if ref[i - 1] == hyp[j - 1] else 1):
            S += 0 if ref[i - 1] == hyp[j - 1] else 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i, j] == d[i - 1, j] + 1:
            D += 1; i -= 1
        else:
            I += 1; j -= 1
    return EditCounts(S, D, I, n)


def word_edit_counts(ref: str, hyp: str) -> EditCounts:
    return _align(normalize_text(ref).split(), normalize_text(hyp).split())


def char_edit_counts(ref: str, hyp: str) -> EditCounts:
    return _align(list(normalize_text(ref)), list(normalize_text(hyp)))


def wer(ref: str, hyp: str) -> float:
    """Fraction (e.g. 0.25 == 25 %). Can exceed 1.0 when insertions dominate."""
    return word_edit_counts(ref, hyp).rate


def cer(ref: str, hyp: str) -> float:
    return char_edit_counts(ref, hyp).rate


def corpus_wer(refs: Sequence[str], hyps: Sequence[str]) -> dict:
    """Corpus-level WER (sum of errors / sum of ref words), the standard way."""
    S = D = I = N = 0
    for r, h in zip(refs, hyps):
        c = word_edit_counts(r, h)
        S += c.substitutions; D += c.deletions; I += c.insertions; N += c.n_ref
    return {"wer": (S + D + I) / N if N else 0.0, "sub": S, "del": D, "ins": I, "n_ref": N,
            "insertion_rate": I / N if N else 0.0}


# ---------------- calibration ----------------
def expected_calibration_error(conf, correct, n_bins: int = 10) -> Tuple[float, List[dict]]:
    conf = np.asarray(conf, dtype=float)
    correct = np.asarray(correct, dtype=float)
    if conf.size == 0:
        return 0.0, []
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece, stats = 0.0, []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (conf >= lo) & ((conf < hi) if i < n_bins - 1 else (conf <= hi))
        if m.any():
            acc, c = correct[m].mean(), conf[m].mean()
            ece += m.mean() * abs(acc - c)
            stats.append({"lo": lo, "hi": hi, "acc": float(acc), "conf": float(c), "count": int(m.sum())})
        else:
            stats.append({"lo": lo, "hi": hi, "acc": float("nan"), "conf": float("nan"), "count": 0})
    return float(ece), stats


# ---------------- selective prediction ----------------
def risk_coverage_curve(conf, correct):
    """Sort by confidence (desc); at coverage k/N the risk is the error rate of
    the k most-confident predictions. Returns (coverage, risk, thresholds)."""
    conf = np.asarray(conf, dtype=float)
    err = 1.0 - np.asarray(correct, dtype=float)
    if conf.size == 0:
        return np.array([]), np.array([]), np.array([])
    order = np.argsort(-conf, kind="stable")
    err_sorted = err[order]
    k = np.arange(1, conf.size + 1)
    return k / conf.size, np.cumsum(err_sorted) / k, conf[order]


def aurc(conf, correct) -> float:
    cov, risk, _ = risk_coverage_curve(conf, correct)
    return float(np.mean(risk)) if risk.size else 0.0


def threshold_for_target_risk(conf, correct, target_risk: float) -> float:
    """Smallest tau whose accepted set (conf >= tau) has empirical risk <= target.
    Returns +inf if no non-empty set satisfies it (abstain on everything)."""
    cov, risk, thr = risk_coverage_curve(conf, correct)
    ok = np.where(risk <= target_risk)[0]
    return float(thr[ok.max()]) if ok.size else float("inf")


# ---------------- per-hypothesis-word labels (used to fit T, gamma, tau) ----------------
def hyp_word_labels(ref: str, hyp: str) -> List[str]:
    """For every word of the (normalised) hypothesis return 'C' (correct, aligned
    match), 'S' (substituted) or 'I' (inserted: no counterpart in the reference).
    len(result) == len(normalize_text(hyp).split()).
      correctness label  = 1 if 'C' else 0         (for temperature / tau fitting)
      speech label       = 0 if 'I' else 1         (for gamma fitting; insertions are
                                                    the hallucination proxy)"""
    r, h = normalize_text(ref).split(), normalize_text(hyp).split()
    n, m = len(r), len(h)
    d = np.zeros((n + 1, m + 1), dtype=np.int64)
    d[:, 0] = np.arange(n + 1); d[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (0 if r[i - 1] == h[j - 1] else 1))
    labels = [""] * m
    i, j = n, m
    while j > 0:
        if i > 0 and d[i, j] == d[i - 1, j - 1] + (0 if r[i - 1] == h[j - 1] else 1):
            labels[j - 1] = "C" if r[i - 1] == h[j - 1] else "S"
            i, j = i - 1, j - 1
        elif i > 0 and d[i, j] == d[i - 1, j] + 1:
            i -= 1                              # deletion: consumes a ref word only
        else:
            labels[j - 1] = "I"; j -= 1
    return labels


def corpus_cer(refs: Sequence[str], hyps: Sequence[str]) -> float:
    E = N = 0
    for r, h in zip(refs, hyps):
        c = char_edit_counts(r, h)
        E += c.errors; N += c.n_ref
    return E / N if N else 0.0
