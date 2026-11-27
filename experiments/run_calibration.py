"""Objectives 3, 4, 5: calibration, hallucination grounding and selective transcription on RAW outputs.
Needs no model: reads results/raw/*.jsonl only.

    python -m experiments.run_calibration --raw results/raw --out results/calibration.json

Pooling policy (primary): LOSO-style. For held-out speaker S, T/gamma/tau are fitted on the VALIDATION
words of all OTHER speakers (same condition) and applied to S's TEST words. Secondary: per-speaker fit
on S's own validation words. Both are written. Test records are never used for fitting."""
from __future__ import annotations
import argparse, glob, json, math, os, re, sys
from typing import Dict, List, Tuple

from fewdsr_config import CFG
from core import eval_calibration as E
from experiments import common as C
from experiments import validate_raw as V

NAME = re.compile(r"^(?P<spk>.+)_K(?P<k>\d+)_(?P<cond>baseline|lora)\.jsonl$")


def load_raw(raw_dir: str, validate: bool = True) -> Dict[Tuple[str, int, str], List[dict]]:
    """(speaker, k, condition) -> records. Refuses to run on files that fail the Part 2 validator."""
    if validate:
        errs, _ = V.validate_dir(raw_dir)
        if errs:
            raise SystemExit("raw files failed validation (run experiments.validate_raw):\n  " + "\n  ".join(errs[:10]))
    out = {}
    for f in sorted(glob.glob(os.path.join(raw_dir, "*.jsonl"))):
        m = NAME.match(os.path.basename(f))
        if m:
            out[(m["spk"], int(m["k"]), m["cond"])] = C.read_jsonl(f)
    return out


def condition_name(k: int, cond: str) -> str:
    return "baseline" if cond == "baseline" else f"lora_K{k}"


def group_by_condition(raw) -> Dict[str, Dict[str, List[dict]]]:
    g: Dict[str, Dict[str, List[dict]]] = {}
    for (spk, k, cond), recs in raw.items():
        g.setdefault(condition_name(k, cond), {})[spk] = recs
    return g


def run(raw_dir: str, target_risk: float = CFG.target_risk, validate: bool = True) -> dict:
    raw = load_raw(raw_dir, validate)
    if not raw:
        raise SystemExit(f"no raw files in {raw_dir}")
    out = {"target_risk": target_risk, "conditions": {}}
    for name, recs_by_spk in sorted(group_by_condition(raw).items()):
        out["conditions"][name] = E.evaluate_condition(recs_by_spk, CFG.torgo_severity, target_risk, CFG.ece_bins)
    return out


def _fmt(x, pct=False, nd=3):
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%" if pct else f"{x:.{nd}f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--out", default="results/calibration.json")
    ap.add_argument("--target-risk", type=float, default=CFG.target_risk)
    a = ap.parse_args(argv)
    res = run(a.raw, a.target_risk)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=lambda o: None if (isinstance(o, float) and not math.isfinite(o)) else o)
    for name, c in res["conditions"].items():
        for proto in ("loso", "local"):
            p = c["protocols"][proto]["pooled"]
            if p.get("empty"):
                print(f"{name:10s} {proto:5s}: no scorable speakers {c['protocols'][proto]['errors']}"); continue
            cal, gr, se = p["calibration"], p["grounding"], p["selective"]
            print(f"{name:10s} {proto:5s}: ECE {_fmt(cal['ece_before'])}->{_fmt(cal['ece_after'])}  "
                  f"ins {_fmt(gr['insertion_rate_before'], True)}->{_fmt(gr['insertion_rate_after'], True)}  "
                  f"AURC {_fmt(se['aurc'])}  cov@tau {_fmt(se['coverage_at_tau'], True)}  "
                  f"risk@tau {_fmt(se['realized_risk_at_tau'], True)} (target {args_pct(a.target_risk)})")
    print("->", a.out)
    return 0


def args_pct(x):
    return f"{x * 100:.0f}%"


if __name__ == "__main__":
    sys.exit(main())
