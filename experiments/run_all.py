"""Build results/summary.json (+ figures) from RAW outputs. Reads only files under results/.

  python -m experiments.run_all --raw results/raw --out results
Optional inputs (used if present, otherwise the section is null and says so):
  results/edge/edge.json            from experiments.run_edge
  results/stress/stress.jsonl       from experiments.run_silence_stress
Never fabricates: anything missing is null and listed under "missing"."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, os, sys
from dataclasses import asdict
from typing import Dict, List, Optional

from fewdsr_config import CFG
from core import eval_calibration as E, eval_stats as S, metrics as M
from experiments import common as C
from experiments import run_calibration as RC

HEADLINE_PREFERENCE = ["lora_K10", "lora_K20", "lora_K5", "lora_K40", "baseline"]


def _clean(o):
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return _clean(o.item())
    except ImportError:
        pass
    return o


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _baseline_block(raw) -> dict:
    by_spk, groups = {}, {}
    for (spk, k, cond), recs in sorted(raw.items()):
        if cond != "baseline":
            continue
        t = S.only_test(recs)
        if not t:
            continue
        refs, hyps = [r["ref"] for r in t], [r["hyp"] for r in t]
        cw = M.corpus_wer(refs, hyps)
        by_spk[spk] = {"wer": cw["wer"], "cer": M.corpus_cer(refs, hyps), "ins_rate": cw["insertion_rate"],
                       "n_words": cw["n_ref"], "n_utts": len(t), "severity": CFG.torgo_severity.get(spk, "unknown")}
        groups.setdefault(by_spk[spk]["severity"], ([], []))
        groups[by_spk[spk]["severity"]][0].extend(refs); groups[by_spk[spk]["severity"]][1].extend(hyps)
    by_sev = {}
    for sev, (refs, hyps) in groups.items():
        cw = M.corpus_wer(refs, hyps)
        by_sev[sev] = {"wer": cw["wer"], "cer": M.corpus_cer(refs, hyps), "ins_rate": cw["insertion_rate"],
                       "n_words": cw["n_ref"]}
    return {"by_severity": by_sev, "by_speaker": by_spk}


def _lora_block(adapters_dir: Optional[str], missing: List[str]) -> Optional[dict]:
    """Measured trainable-parameter share, read from the train_info.json that Part 2 wrote next to each adapter."""
    import glob
    files = sorted(glob.glob(os.path.join(adapters_dir or "", "*", "train_info.json")))
    infos = []
    for f in files:
        with open(f) as fh:
            infos.append(json.load(fh))
    infos = [i for i in infos if i.get("trainable_pct") is not None]
    if not infos:
        missing.append("measured LoRA trainable-parameter share unavailable (no artifacts/adapters/*/train_info.json)")
        return None
    pcts = sorted({round(float(i["trainable_pct"]), 6) for i in infos})
    return {"n_adapters": len(infos), "trainable_pct": pcts[0], "trainable_pct_all_equal": len(pcts) == 1,
            "trainable_params": infos[0].get("trainable_params"), "total_params": infos[0].get("total_params")}


def build_summary(raw_dir: str, results_dir: str, headline: Optional[str] = None, n_boot: int = 1000,
                  fixture: bool = False, adapters_dir: Optional[str] = "artifacts/adapters") -> dict:
    raw = RC.load_raw(raw_dir, validate=True)
    if not raw:
        raise SystemExit(f"no raw files in {raw_dir}")
    missing: List[str] = []
    cal = RC.run(raw_dir, CFG.target_risk, validate=False)
    conds = cal["conditions"]
    if headline is None:
        headline = next((h for h in HEADLINE_PREFERENCE if h in conds), sorted(conds)[0])
    if headline not in conds:
        raise SystemExit(f"headline condition {headline!r} not in {sorted(conds)}")
    hc = conds[headline]
    loso = hc["protocols"]["loso"]
    if loso.get("pooled", {}).get("empty"):
        missing.append(f"LOSO calibration for {headline}: {loso['errors'] or 'no scorable speakers'}")
    pooled = loso["pooled"] if not loso["pooled"].get("empty") else hc["protocols"]["local"]["pooled"]
    proto_used = "loso" if not loso["pooled"].get("empty") else "local"
    dep = hc.get("deploy_params") or {}

    # ---- speakers
    speakers = {}
    for spk in sorted({s for (s, _k, _c) in raw}):
        ks = sorted(k for (s, k, _c) in raw if s == spk)
        recs = next(v for (s, _k, _c), v in raw.items() if s == spk)
        speakers[spk] = {"severity": CFG.torgo_severity.get(spk, "unknown"),
                         "n_val_utts": sum(r["split"] == "val" for r in recs),
                         "n_test_utts": sum(r["split"] == "test" for r in recs),
                         "budgets_available": ks, "budgets_missing": [k for k in CFG.budgets if k not in ks]}
        if speakers[spk]["budgets_missing"]:
            missing.append(f"{spk}: budgets {speakers[spk]['budgets_missing']} not run or infeasible")

    scaling = S.scaling_analysis(raw, n_boot)
    cmp = {}
    def grp(k, cond): return {s: v for (s, kk, c), v in raw.items() if kk == k and c == cond}
    base = grp(0, "baseline")
    for k in CFG.budgets:
        if k == 0:
            continue
        other = grp(k, "lora")
        if base and other:
            cmp[f"k0_vs_k{k}"] = S.paired_comparison(base, other, n_boot)
    for a, b in zip([5, 10, 20], [10, 20, 40]):
        if grp(a, "lora") and grp(b, "lora"):
            cmp[f"k{a}_vs_k{b}"] = S.paired_comparison(grp(a, "lora"), grp(b, "lora"), n_boot)
    k10 = cmp.get("k0_vs_k10")

    # ---- hallucination stress test (optional)
    stress = None
    sp_path = os.path.join(results_dir, "stress", "stress.jsonl")
    if os.path.exists(sp_path):
        if dep.get("gamma") is not None:
            stress = E.stress_hallucination(C.read_jsonl(sp_path), dep["gamma"])
        else:
            missing.append("stress test present but no deployment gamma could be fitted")
    else:
        missing.append("silence/pause stress test not run (results/stress/stress.jsonl absent)")

    edge = None
    ep = os.path.join(results_dir, "edge", "edge.json")
    if os.path.exists(ep):
        with open(ep) as f:
            edge = json.load(f)
    else:
        missing.append("edge (INT8 vs FP32) benchmark not run (results/edge/edge.json absent)")

    cal_s = pooled["calibration"]; gr = pooled["grounding"]; se = pooled["selective"]
    taus = {s: p["tau"] for s, p in loso["params"].items() if p}
    summary = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "is_fixture": bool(fixture),
        "config": asdict(CFG),
        "provenance": {"raw_dir": raw_dir, "raw_file_sha256_16": {os.path.basename(f): _sha(f) for f in sorted(
            os.path.join(raw_dir, n) for n in os.listdir(raw_dir) if n.endswith(".jsonl"))}},
        "speakers": speakers,
        "baseline": _baseline_block(raw),
        "scaling": scaling,
        "calibration": {
            "headline_condition": headline, "protocol": proto_used,
            "T": {s: p["T"] for s, p in loso["params"].items() if p},
            "ece_before": cal_s["ece_before"], "ece_after": cal_s["ece_after"],
            "nll_before": cal_s["nll_before"], "nll_after": cal_s["nll_after"],
            "reliability": {"before": cal_s["reliability_before"], "after": cal_s["reliability_after"]},
            "per_speaker_fit_ece": {s: {"before": v["calibration"]["ece_before"], "after": v["calibration"]["ece_after"]}
                                    for s, v in hc["protocols"]["local"]["by_speaker"].items() if "calibration" in v},
            "warnings": {s: p["warnings"] for s, p in loso["params"].items() if p and p["warnings"]}},
        "hallucination": {
            "insertion_rate_before": gr["insertion_rate_before"], "insertion_rate_after": gr["insertion_rate_after"],
            "wer_before": gr["wer_before"], "wer_after": gr["wer_after"], "speech_recall": gr["speech_recall"],
            "gamma": dep.get("gamma"), "gamma_by_speaker": {s: p["gamma"] for s, p in loso["params"].items() if p},
            "stress_test": stress},
        "selective": {
            "tau": dep.get("tau"), "tau_by_speaker": taus, "target_risk": CFG.target_risk,
            "risk_coverage": se["risk_coverage"], "aurc": se["aurc"],
            "coverage_at_target_risk": se["coverage_at_tau"], "realized_risk_at_tau": se["realized_risk_at_tau"],
            "target_met": se["target_met"], "oracle_coverage_at_target_risk": se["oracle_coverage_at_target_risk"],
            "all_word_error_rate": se["all_word_error_rate"]},
        "edge": edge,
        "lora": _lora_block(adapters_dir, missing),
        "stats": {"wilcoxon_p_k0_vs_k10": (k10["wilcoxon_utterance_level"]["p"] if k10 else None),
                  "wilcoxon_speaker_p_k0_vs_k10": (k10["wilcoxon_speaker_level"]["p"] if k10 else None),
                  "comparisons": cmp},
        "conditions": {n: {"deploy_params": c.get("deploy_params"),
                           "loso_pooled": c["protocols"]["loso"]["pooled"], "local_pooled": c["protocols"]["local"]["pooled"],
                           "by_severity_loso": c["protocols"]["loso"]["by_severity"]} for n, c in conds.items()},
        "deploy_params": {n: c.get("deploy_params") for n, c in conds.items()},
        "missing": missing}
    return _clean(summary)


def make_figures(summary: dict, fig_dir: str) -> List[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(fig_dir, exist_ok=True)
    out = []
    sc = summary["scaling"]
    if sc["K"]:
        fig, ax = plt.subplots(figsize=(6, 3.8))
        for spk, d in sc["per_speaker"].items():
            ax.plot([int(k) for k in d], [v * 100 for v in d.values()], marker="o", lw=1, alpha=.5, label=spk)
        ax.plot(sc["K"], [m * 100 for m in sc["wer_mean"]], "k-o", lw=2.5, label="mean over speakers")
        for k, m, ci in zip(sc["K"], sc["wer_mean"], sc["wer_ci95"]):
            if ci:
                ax.vlines(k, ci[0] * 100, ci[1] * 100, color="k", lw=1.5)
        ax.set_xlabel("adaptation utterances K (0 = zero-shot)"); ax.set_ylabel("WER (%)"); ax.legend(fontsize=7)
        ax.set_title("WER vs few-shot budget (bars: 95% bootstrap CI over speakers)", fontsize=9)
        p = os.path.join(fig_dir, "scaling_curve.png"); fig.tight_layout(); fig.savefig(p, dpi=150); plt.close(fig); out.append(p)
    rel = summary["calibration"]["reliability"]
    if rel["before"]:
        fig, axs = plt.subplots(1, 2, figsize=(8, 3.8), sharey=True)
        for ax, key, ttl in zip(axs, ("before", "after"), ("T = 1", "fitted T (LOSO)")):
            bins = [b for b in rel[key] if b["count"]]
            ax.plot([0, 1], [0, 1], "k--", lw=1)
            ax.bar([b["conf"] for b in bins], [b["acc"] for b in bins], width=0.08, alpha=.7)
            ax.set_title(f"{ttl}: ECE {summary['calibration']['ece_' + key]:.3f}", fontsize=9)
            ax.set_xlabel("confidence"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        axs[0].set_ylabel("word accuracy")
        p = os.path.join(fig_dir, "reliability.png"); fig.tight_layout(); fig.savefig(p, dpi=150); plt.close(fig); out.append(p)
    rc = summary["selective"]["risk_coverage"]
    if rc and rc["coverage"]:
        fig, ax = plt.subplots(figsize=(5.5, 3.8))
        ax.plot([c * 100 for c in rc["coverage"]], [r * 100 for r in rc["risk"]])
        ax.axhline(summary["selective"]["target_risk"] * 100, color="r", ls="--", lw=1, label="target risk")
        ax.set_xlabel("coverage (% of grounded words)"); ax.set_ylabel("error rate of accepted words (%)"); ax.legend()
        p = os.path.join(fig_dir, "risk_coverage.png"); fig.tight_layout(); fig.savefig(p, dpi=150); plt.close(fig); out.append(p)
    bs = summary["baseline"]["by_severity"]
    if bs:
        fig, ax = plt.subplots(figsize=(5.5, 3.8))
        names = sorted(bs)
        ax.bar(names, [bs[n]["wer"] * 100 for n in names])
        ax.set_ylabel("zero-shot WER (%)"); ax.set_title("Baseline WER by severity group (TORGO map in config)", fontsize=9)
        p = os.path.join(fig_dir, "wer_by_severity.png"); fig.tight_layout(); fig.savefig(p, dpi=150); plt.close(fig); out.append(p)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--out", default="results")
    ap.add_argument("--headline", default=None, help="condition for the headline calibration/selective numbers, "
                                                       "e.g. lora_K10 or baseline (default: first available of K10,K20,K5,K40,baseline)")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--adapters", default="artifacts/adapters")
    ap.add_argument("--fixture", action="store_true", help="mark output as test-fixture data (never for real results)")
    a = ap.parse_args(argv)
    summ = build_summary(a.raw, a.out, a.headline, a.boot, a.fixture, a.adapters)
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summ, f, indent=1)
    figs = make_figures(summ, os.path.join(a.out, "figures"))
    from experiments.validate_summary import validate
    errs = validate(summ)
    print(f"-> {path} + {len(figs)} figures; headline={summ['calibration']['headline_condition']} "
          f"protocol={summ['calibration']['protocol']}")
    for m in summ["missing"]:
        print("MISSING:", m)
    for e in errs:
        print("SCHEMA ERROR:", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
