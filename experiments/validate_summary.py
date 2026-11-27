"""Validate results/summary.json against docs/CONTRACTS.md (+ Part 3 additive keys).
   python -m experiments.validate_summary results/summary.json   (exit 1 on any problem)"""
from __future__ import annotations
import json, math, sys
from typing import List

TOP = ["generated", "config", "baseline", "scaling", "calibration", "hallucination", "selective", "edge", "stats"]


def _finite_or_none(x, path, errs):
    if isinstance(x, float) and not math.isfinite(x):
        errs.append(f"{path}: non-finite number (must be null)")
    elif isinstance(x, dict):
        for k, v in x.items():
            _finite_or_none(v, f"{path}.{k}", errs)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _finite_or_none(v, f"{path}[{i}]", errs)


def validate(s: dict) -> List[str]:
    errs: List[str] = []
    for k in TOP:
        if k not in s:
            errs.append(f"missing top-level key {k!r}")
    if errs:
        return errs
    _finite_or_none(s, "$", errs)
    sc = s["scaling"]
    n = len(sc["K"])
    if not (len(sc["wer_mean"]) == len(sc["wer_ci95"]) == len(sc["n_speakers"]) == n):
        errs.append("scaling: K / wer_mean / wer_ci95 / n_speakers lengths differ")
    for i, ci in enumerate(sc["wer_ci95"]):
        if ci is not None and not (len(ci) == 2 and ci[0] <= ci[1]):
            errs.append(f"scaling.wer_ci95[{i}] malformed")
    for i, m in enumerate(sc["wer_mean"]):
        if not (isinstance(m, (int, float)) and m >= 0):
            errs.append(f"scaling.wer_mean[{i}] must be a non-negative fraction")
    for spk, d in sc["per_speaker"].items():
        for k, v in d.items():
            if not (isinstance(v, (int, float)) and v >= 0):
                errs.append(f"scaling.per_speaker.{spk}.{k}: bad WER")
    c = s["calibration"]
    for k in ("T", "ece_before", "ece_after", "reliability"):
        if k not in c:
            errs.append(f"calibration.{k} missing")
    for k in ("ece_before", "ece_after"):
        v = c.get(k)
        if v is not None and not (0 <= v <= 1):
            errs.append(f"calibration.{k}={v} outside [0,1]")
    for t, v in (c.get("T") or {}).items():
        if not (isinstance(v, (int, float)) and v > 0):
            errs.append(f"calibration.T.{t} must be > 0")
    for k in ("insertion_rate_before", "insertion_rate_after", "gamma"):
        if k not in s["hallucination"]:
            errs.append(f"hallucination.{k} missing")
    sel = s["selective"]
    for k in ("tau", "risk_coverage", "aurc", "coverage_at_target_risk"):
        if k not in sel:
            errs.append(f"selective.{k} missing")
    rc = sel.get("risk_coverage") or {}
    if len(rc.get("coverage", [])) != len(rc.get("risk", [])):
        errs.append("selective.risk_coverage coverage/risk lengths differ")
    cv = sel.get("coverage_at_target_risk")
    if cv is not None and not (0 <= cv <= 1):
        errs.append("selective.coverage_at_target_risk outside [0,1]")
    if s["edge"] is not None:
        for k in ("fp32_rtf", "int8_rtf", "int8_wer", "cpu"):
            if k not in s["edge"]:
                errs.append(f"edge.{k} missing")
    if "wilcoxon_p_k0_vs_k10" not in s["stats"]:
        errs.append("stats.wilcoxon_p_k0_vs_k10 missing")
    p = s["stats"].get("wilcoxon_p_k0_vs_k10")
    if p is not None and not (0 <= p <= 1):
        errs.append("stats.wilcoxon_p_k0_vs_k10 outside [0,1]")
    return errs


def main(argv=None) -> int:
    path = (argv or sys.argv[1:] or ["results/summary.json"])[0]
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    errs = validate(s)
    for e in errs:
        print("ERROR", e)
    print("VALID" if not errs else f"{len(errs)} problem(s)")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
