"""Part 3: calibration / grounding / selective evaluation on RAW per-utterance records.

Pure numpy + the Part 1 modules. No torch, no model. Input is the list of dicts that Part 2
writes to results/raw/*.jsonl (see docs/CONTRACTS.md).

Protocol rules enforced in code (not just documented):
* T, gamma, tau are fitted ONLY from records tagged split == "val" (`words_table` asserts it).
* Evaluation numbers come ONLY from records tagged split == "test".
* Primary protocol is LOSO-style: parameters for held-out speaker S are fitted on the validation
  words of all OTHER speakers. Secondary protocol: per-speaker fit on S's own validation words.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from fewdsr_config import CFG
from core import metrics as M
from core.calibration_guard import CalibrationGuard, softmax_top_prob
from core.selective_engine import SelectiveTranscriptionEngine

MIN_MINORITY = 3          # need >= 3 correct AND >= 3 wrong validation words to fit T
MIN_INSERTIONS = 5        # fewer validation insertions -> gamma is set by speech recall only (warned)
T_BOUNDS = (0.05, 10.0)


class FitError(ValueError):
    """Parameters cannot be fitted from the supplied validation words."""


# --------------------------------------------------------------------------- word tables
def record_word_labels(rec: dict) -> List[Optional[str]]:
    """One label per entry of rec['words']: 'C' correct, 'S' substituted, 'I' inserted, or None for
    entries that normalise to nothing (pure punctuation). Words that normalise to several words
    (e.g. "don't" -> "don t") get 'C' only if all parts are correct, 'I' only if all are inserted."""
    labels = M.hyp_word_labels(rec["ref"], rec["hyp"])
    counts = [len(M.normalize_text(w["word"]).split()) for w in rec["words"]]
    if sum(counts) != len(labels):
        raise ValueError(f"record {rec.get('wav')}: words do not match hyp (tampered or inconsistent file)")
    out, i = [], 0
    for c in counts:
        if c == 0:
            out.append(None)
            continue
        grp = labels[i:i + c]
        i += c
        out.append("C" if all(g == "C" for g in grp) else ("I" if all(g == "I" for g in grp) else "S"))
    return out


@dataclass
class WordTable:
    Z: np.ndarray            # [N, K] raw top-K logits, column 0 = emitted token
    delta: np.ndarray        # [N]    z(w) - z(nospeech)
    correct: np.ndarray      # [N]    1 if label == 'C'
    is_speech: np.ndarray    # [N]    0 if label == 'I' (insertion = hallucination proxy)

    def __len__(self) -> int:
        return int(self.Z.shape[0])

    @staticmethod
    def concat(tables: Sequence["WordTable"]) -> "WordTable":
        tabs = [t for t in tables if len(t)]
        if not tabs:
            return WordTable(np.zeros((0, 1)), np.zeros(0), np.zeros(0, int), np.zeros(0, int))
        return WordTable(np.vstack([t.Z for t in tabs]), np.concatenate([t.delta for t in tabs]),
                         np.concatenate([t.correct for t in tabs]), np.concatenate([t.is_speech for t in tabs]))


def words_table(records: Sequence[dict], split: str) -> WordTable:
    """Per-hypothesis-word arrays for `split` records. Records of any other split are an ERROR
    (this is the leakage guard: a test record can never reach a fitting routine)."""
    bad = [r.get("wav") for r in records if r.get("split") != split]
    if bad:
        raise AssertionError(f"split leakage: expected only '{split}' records, found {len(bad)} others")
    Z, delta, correct, speech = [], [], [], []
    for r in records:
        for w, lab in zip(r["words"], record_word_labels(r)):
            if lab is None:
                continue
            z = np.asarray(w["topk_logits"], dtype=float)
            Z.append(z)
            delta.append(z[0] - float(w["null_logit"]))
            correct.append(int(lab == "C"))
            speech.append(int(lab != "I"))
    if not Z:
        return WordTable(np.zeros((0, 1)), np.zeros(0), np.zeros(0, int), np.zeros(0, int))
    return WordTable(np.vstack(Z), np.asarray(delta), np.asarray(correct, int), np.asarray(speech, int))


# --------------------------------------------------------------------------- fitting
@dataclass
class Params:
    T: float
    gamma: float
    tau: float                       # may be +inf: abstain on everything
    n_words: int
    n_insertions: int
    n_grounded: int
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = {"T": self.T, "gamma": self.gamma, "tau": self.tau, "n_val_words": self.n_words,
             "n_val_insertions": self.n_insertions, "n_val_grounded": self.n_grounded,
             "warnings": list(self.warnings)}
        return d


def fit_params(val: WordTable, target_risk: float = CFG.target_risk,
               min_speech_recall: float = 0.95) -> Params:
    """Fit T (NLL), gamma (speech recall), tau (target risk on grounded words) from VALIDATION words."""
    n = len(val)
    if n == 0:
        raise FitError("no validation words")
    warns: List[str] = []
    guard = CalibrationGuard()

    n_ok = int(val.correct.sum()); n_bad = n - n_ok
    if min(n_ok, n_bad) < MIN_MINORITY:
        T = 1.0
        warns.append(f"temperature not fitted (only {n_ok} correct / {n_bad} wrong validation words); kept T=1")
    else:
        T = guard.fit_temperature(val.Z, val.correct, bounds=T_BOUNDS)
        if T <= T_BOUNDS[0] * 1.02 or T >= T_BOUNDS[1] * 0.98:
            warns.append(f"fitted T={T:.3f} sits at the search bound; calibration is unreliable")

    if int(val.is_speech.sum()) == 0:
        raise FitError("no genuinely spoken validation words (all hypothesis words were insertions)")
    n_ins = int((val.is_speech == 0).sum())
    gamma = guard.fit_gamma(val.delta, val.is_speech, min_speech_recall)
    if n_ins < MIN_INSERTIONS:
        warns.append(f"only {n_ins} insertions in validation: gamma is set by the {min_speech_recall:.0%} speech-recall "
                     "rule alone and says nothing about hallucination rejection")

    grounded = val.delta >= gamma
    if not grounded.any():
        tau = float("inf")
        warns.append("no validation word passes the grounding margin; tau=inf (abstain on all)")
    else:
        conf = softmax_top_prob(val.Z[grounded], T)
        tau = SelectiveTranscriptionEngine().fit_tau(conf, val.correct[grounded], target_risk)
        if not np.isfinite(tau):
            warns.append(f"no confidence threshold reaches target risk {target_risk:.0%} on validation; tau=inf "
                         "(abstain on all)")
    return Params(float(T), float(gamma), float(tau), n, n_ins, int(grounded.sum()), warns)


# --------------------------------------------------------------------------- scoring test data
@dataclass
class Scored:
    """Everything needed to compute test metrics, for one or many speakers."""
    conf_before: np.ndarray
    conf_after: np.ndarray
    correct: np.ndarray
    is_speech: np.ndarray
    grounded: np.ndarray             # bool
    tau: np.ndarray                  # per-word tau of the speaker the word came from
    refs: List[str]
    hyps_before: List[str]
    hyps_after: List[str]            # words with delta < gamma removed

    @staticmethod
    def concat(items: Sequence["Scored"]) -> "Scored":
        items = list(items)
        cat = lambda f: np.concatenate([getattr(s, f) for s in items]) if items else np.zeros(0)
        return Scored(cat("conf_before"), cat("conf_after"), cat("correct").astype(int), cat("is_speech").astype(int),
                      cat("grounded").astype(bool), cat("tau"),
                      [r for s in items for r in s.refs], [h for s in items for h in s.hyps_before],
                      [h for s in items for h in s.hyps_after])


def grounded_hyp(rec: dict, gamma: float) -> str:
    return " ".join(w["word"] for w in rec["words"]
                    if float(w["topk_logits"][0]) - float(w["null_logit"]) >= gamma)


def score_test(test_recs: Sequence[dict], p: Params) -> Scored:
    tab = words_table(test_recs, "test")
    return Scored(
        conf_before=softmax_top_prob(tab.Z, 1.0) if len(tab) else np.zeros(0),
        conf_after=softmax_top_prob(tab.Z, p.T) if len(tab) else np.zeros(0),
        correct=tab.correct, is_speech=tab.is_speech, grounded=tab.delta >= p.gamma,
        tau=np.full(len(tab), p.tau),
        refs=[r["ref"] for r in test_recs], hyps_before=[r["hyp"] for r in test_recs],
        hyps_after=[grounded_hyp(r, p.gamma) for r in test_recs])


def _nll(conf, correct) -> Optional[float]:
    if len(conf) == 0:
        return None
    p = np.clip(np.asarray(conf, float), 1e-12, 1 - 1e-12)
    y = np.asarray(correct, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _thin(a: np.ndarray, n: int = 200) -> List[float]:
    if len(a) <= n:
        return [float(x) for x in a]
    idx = np.unique(np.linspace(0, len(a) - 1, n).astype(int))
    return [float(a[i]) for i in idx]


def summarize_scored(s: Scored, target_risk: float = CFG.target_risk, n_bins: int = CFG.ece_bins) -> dict:
    """All Stage 3/4 test metrics for a (possibly pooled) Scored. Returns JSON-friendly dict."""
    n = len(s.correct)
    out: dict = {"n_words": n, "n_utts": len(s.refs)}
    if n == 0:
        out["empty"] = True
        return out
    ece_b, bins_b = M.expected_calibration_error(s.conf_before, s.correct, n_bins)
    ece_a, bins_a = M.expected_calibration_error(s.conf_after, s.correct, n_bins)
    out["calibration"] = {"ece_before": ece_b, "ece_after": ece_a, "nll_before": _nll(s.conf_before, s.correct),
                          "nll_after": _nll(s.conf_after, s.correct),
                          "reliability_before": bins_b, "reliability_after": bins_a}

    cw_b = M.corpus_wer(s.refs, s.hyps_before)
    cw_a = M.corpus_wer(s.refs, s.hyps_after)
    n_ins = int((s.is_speech == 0).sum())
    n_ins_kept = int(((s.is_speech == 0) & s.grounded).sum())
    n_true = int((s.is_speech == 1).sum())
    n_true_kept = int(((s.is_speech == 1) & s.grounded).sum())
    out["grounding"] = {
        "wer_before": cw_b["wer"], "wer_after": cw_a["wer"],
        "insertion_rate_before": cw_b["insertion_rate"], "insertion_rate_after": cw_a["insertion_rate"],
        "insertions_before": cw_b["ins"], "insertions_after": cw_a["ins"],
        "deletions_before": cw_b["del"], "deletions_after": cw_a["del"], "n_ref_words": cw_b["n_ref"],
        "hyp_insertions_removed": n_ins - n_ins_kept, "hyp_insertions_total": n_ins,
        "spoken_words_kept": n_true_kept, "spoken_words_total": n_true,
        "speech_recall": (n_true_kept / n_true) if n_true else None}

    g = s.grounded
    conf_g, corr_g = s.conf_after[g], s.correct[g]
    sel: dict = {"n_grounded_words": int(g.sum()), "target_risk": target_risk,
                 "all_word_error_rate": float(1 - s.correct.mean())}
    if g.any():
        cov, risk, _ = M.risk_coverage_curve(conf_g, corr_g)
        sel["risk_coverage"] = {"coverage": _thin(cov), "risk": _thin(risk)}
        sel["aurc"] = M.aurc(conf_g, corr_g)
        acc = g & (s.conf_after >= s.tau)
        sel["n_accepted"] = int(acc.sum())
        sel["coverage_at_tau"] = float(acc.sum() / g.sum())
        sel["realized_risk_at_tau"] = float(1 - s.correct[acc].mean()) if acc.any() else None
        sel["target_met"] = (bool(1 - s.correct[acc].mean() <= target_risk) if acc.any() else None)
        # descriptive only: best coverage the TEST curve could reach (needs test labels, not deployable)
        ok = np.where(risk <= target_risk)[0]
        sel["oracle_coverage_at_target_risk"] = float(cov[ok.max()]) if ok.size else 0.0
    else:
        sel.update({"risk_coverage": {"coverage": [], "risk": []}, "aurc": None, "n_accepted": 0,
                    "coverage_at_tau": 0.0, "realized_risk_at_tau": None, "target_met": None,
                    "oracle_coverage_at_target_risk": 0.0})
    out["selective"] = sel
    return out


# --------------------------------------------------------------------------- one condition, all speakers
def evaluate_condition(recs_by_spk: Dict[str, List[dict]], severity: Dict[str, str],
                       target_risk: float = CFG.target_risk, n_bins: int = CFG.ece_bins) -> dict:
    """recs_by_spk: speaker -> all raw records (val + test) of ONE condition (baseline or lora K).
    Returns LOSO (primary) and per-speaker (secondary) results plus pooled-all-val deployment params."""
    val = {s: words_table([r for r in rs if r["split"] == "val"], "val") for s, rs in recs_by_spk.items()}
    test = {s: [r for r in rs if r["split"] == "test"] for s, rs in recs_by_spk.items()}
    speakers = sorted(recs_by_spk)
    res: dict = {"speakers": speakers, "protocols": {}}

    for proto in ("loso", "local"):
        params: Dict[str, Optional[Params]] = {}
        errors: Dict[str, str] = {}
        for s in speakers:
            fit_tab = (WordTable.concat([val[o] for o in speakers if o != s]) if proto == "loso" else val[s])
            try:
                params[s] = fit_params(fit_tab, target_risk)
            except FitError as e:
                params[s] = None
                errors[s] = (f"{e}" + (" (LOSO needs >= 2 speakers in this condition)" if proto == "loso" and len(speakers) < 2 else ""))
        scored = {s: score_test(test[s], params[s]) for s in speakers if params[s] is not None and test[s]}
        sev_groups: Dict[str, List[Scored]] = {}
        for s, sc in scored.items():
            sev_groups.setdefault(severity.get(s, "unknown"), []).append(sc)
        res["protocols"][proto] = {
            "params": {s: (p.as_dict() if p else None) for s, p in params.items()},
            "errors": errors,
            "pooled": summarize_scored(Scored.concat(list(scored.values())), target_risk, n_bins) if scored else {"empty": True},
            "by_speaker": {s: summarize_scored(sc, target_risk, n_bins) for s, sc in scored.items()},
            "by_severity": {k: summarize_scored(Scored.concat(v), target_risk, n_bins) for k, v in sev_groups.items()},
            "speakers_scored": sorted(scored)}
    try:
        dp = fit_params(WordTable.concat(list(val.values())), target_risk)
        res["deploy_params"] = dp.as_dict()
    except FitError as e:
        res["deploy_params"] = None
        res["deploy_error"] = str(e)
    return res


# --------------------------------------------------------------------------- silence / pause stress test
def stress_hallucination(records: Sequence[dict], gamma: float) -> dict:
    """records: stress clips written by experiments/run_silence_stress.py, with keys
    kind in {'zeros','noise','pause'}, vad (bool), ref ('' for zeros/noise), hyp, words.
    A clip 'hallucinates' if it contains >= 1 inserted word (every word on silence/noise is an insertion).
    'guarded' removes words with delta < gamma first."""
    out: dict = {}
    groups: Dict[str, List[dict]] = {}
    for r in records:
        groups.setdefault(f"{r['kind']}|vad={'on' if r['vad'] else 'off'}", []).append(r)
    for key, rs in sorted(groups.items()):
        raw_h = guard_h = raw_w = guard_w = 0
        for r in rs:
            labels = record_word_labels(r)
            ins = [i for i, l in enumerate(labels) if l == "I"]
            kept = [i for i in ins
                    if float(r["words"][i]["topk_logits"][0]) - float(r["words"][i]["null_logit"]) >= gamma]
            raw_h += bool(ins); guard_h += bool(kept); raw_w += len(ins); guard_w += len(kept)
        n = len(rs)
        out[key] = {"n_clips": n, "hallucination_rate_unguarded": raw_h / n, "hallucination_rate_guarded": guard_h / n,
                    "inserted_words_unguarded": raw_w, "inserted_words_guarded": guard_w}
    return out
