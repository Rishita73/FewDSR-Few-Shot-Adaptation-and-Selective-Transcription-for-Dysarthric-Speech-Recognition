"""Build the RESULTS chapter (.docx) from results/summary.json. Every number is read from the summary;
there are no numeric literals about results in this file.   python -m experiments.make_report [--summary results/summary.json]
Refuses fixture summaries unless --allow-fixture. This is the Results/Evaluation/Limitations chapter, not the whole
report: Introduction / literature / design chapters are yours to write (without the old invented numbers)."""
from __future__ import annotations
import argparse, json, os, sys
from typing import List, Optional


def pct(x: Optional[float], nd: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{nd}f}%"


def num(x: Optional[float], nd: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def p_str(p: Optional[float]) -> str:
    return "n/a" if p is None else ("<0.001" if p < 0.001 else f"{p:.3f}")


def verdict(cmp: Optional[dict], a: str, b: str) -> str:
    """Plain-language, sign-aware sentence about WER(a) - WER(b). Reports negative results as such."""
    if not cmp or cmp.get("mean_diff") is None:
        return f"{a} vs {b}: not measured."
    d, ci = cmp["mean_diff"], cmp.get("diff_ci95")
    base = (f"{a} vs {b} over {cmp['n_speakers']} speaker(s): mean WER {pct(cmp['mean_wer_a'])} -> {pct(cmp['mean_wer_b'])} "
            f"(difference {d * 100:+.1f} points")
    if ci:
        base += f", 95% bootstrap CI [{ci[0] * 100:+.1f}, {ci[1] * 100:+.1f}]"
    base += "). "
    if ci is None:
        return base + "Too few speakers for a confidence interval; treat as descriptive only."
    if ci[0] > 0:
        return base + f"{b} had lower WER and the interval excludes zero."
    if ci[1] < 0:
        return base + f"{b} had HIGHER WER than {a} (negative result) and the interval excludes zero."
    return base + "The interval includes zero: no reliable difference was detected."


def build_docx(s: dict, path: str) -> None:
    from docx import Document
    from docx.shared import Pt, Inches
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"; doc.styles["Normal"].font.size = Pt(11)

    def table(rows: List[List[str]], header: List[str]):
        t = doc.add_table(rows=1, cols=len(header)); t.style = "Light Grid Accent 1"
        for i, h in enumerate(header):
            t.rows[0].cells[i].text = h
        for r in rows:
            cells = t.add_row().cells
            for i, v in enumerate(r):
                cells[i].text = str(v)
        doc.add_paragraph()

    doc.add_heading("FewDSR - Experimental Results and Evaluation", 0)
    doc.add_paragraph(f"Generated from results/summary.json on {s['generated']}. All figures below were measured on the "
                      f"TORGO data processed by this repository; nothing is taken from the earlier prototype.")

    doc.add_heading("1. Experimental setup", 1)
    cal = s["calibration"]
    doc.add_paragraph(f"Base model {s['config']['base_model']}; LoRA r={s['config']['lora_r']}, alpha={s['config']['lora_alpha']} "
                      f"on decoder cross-attention q/v; seed {s['config']['seed']}. Calibration protocol: {cal['protocol'].upper()} "
                      f"(parameters for each held-out speaker fitted on the validation words of the other speakers). "
                      f"Headline condition: {cal['headline_condition']}.")
    lo = s.get("lora")
    if lo:
        doc.add_paragraph(f"Measured trainable parameters: {lo['trainable_params']} of {lo['total_params']} "
                          f"({lo['trainable_pct']:.4f}% ).")
    table([[k, v["severity"], v["n_val_utts"], v["n_test_utts"], str(v["budgets_available"]), str(v["budgets_missing"])]
           for k, v in s["speakers"].items()],
          ["Speaker", "Severity (config map)", "Val utts", "Test utts", "Budgets run", "Budgets missing"])

    doc.add_heading("2. Zero-shot baseline", 1)
    b = s["baseline"]
    table([[k, pct(v["wer"]), pct(v["cer"]), pct(v["ins_rate"]), v["n_words"], v["severity"]] for k, v in b["by_speaker"].items()],
          ["Speaker", "WER", "CER", "Insertion rate", "Ref words", "Severity"])
    table([[k, pct(v["wer"]), pct(v["cer"]), pct(v["ins_rate"]), v["n_words"]] for k, v in b["by_severity"].items()],
          ["Severity group", "WER", "CER", "Insertion rate", "Ref words"])

    doc.add_heading("3. Few-shot adaptation", 1)
    sc = s["scaling"]
    table([[k, pct(m), ("n/a" if ci is None else f"[{pct(ci[0])}, {pct(ci[1])}]"), n]
           for k, m, ci, n in zip(sc["K"], sc["wer_mean"], sc["wer_ci95"], sc["n_speakers"])],
          ["K", "Mean speaker WER", "95% bootstrap CI", "Speakers"])
    doc.add_paragraph("Mean over speakers; K = 0 is the zero-shot baseline. Budgets infeasible for a speaker are missing, not imputed.")
    cmp = s["stats"]["comparisons"]
    for name in sorted(cmp):
        a_, b_ = name.replace("k", "K").split("_vs_")
        c = cmp[name]
        doc.add_paragraph(verdict(c, a_, b_))
        doc.add_paragraph(f"   Wilcoxon signed-rank p: utterance level {p_str(c['wilcoxon_utterance_level']['p'])} "
                          f"(n={c['wilcoxon_utterance_level']['n_pairs']}, utterances are nested in speakers so this p is optimistic); "
                          f"speaker level {p_str(c['wilcoxon_speaker_level']['p'])} (n={c['wilcoxon_speaker_level']['n_pairs']}).")
    if os.path.exists(os.path.join(os.path.dirname(path), "figures", "scaling_curve.png")):
        doc.add_picture(os.path.join(os.path.dirname(path), "figures", "scaling_curve.png"), width=Inches(5.2))

    doc.add_heading("4. Confidence calibration (Stage 3)", 1)
    doc.add_paragraph(f"Pooled test words, protocol {cal['protocol'].upper()}: ECE {num(cal['ece_before'])} at T = 1 versus "
                      f"{num(cal['ece_after'])} after temperature scaling; binary NLL {num(cal['nll_before'])} -> {num(cal['nll_after'])}.")
    table([[k, num(v)] for k, v in cal["T"].items()], ["Held-out speaker", "Fitted T"])
    for spk, w in cal.get("warnings", {}).items():
        doc.add_paragraph(f"Warning ({spk}): " + "; ".join(w))
    rp = os.path.join(os.path.dirname(path), "figures", "reliability.png")
    if os.path.exists(rp):
        doc.add_picture(rp, width=Inches(5.5))

    doc.add_heading("5. Hallucination suppression (acoustic-null grounding)", 1)
    h = s["hallucination"]
    doc.add_paragraph(f"Deployment margin gamma (fitted on pooled validation words) = {num(h['gamma'])}. On the test words, "
                      f"insertion rate {pct(h['insertion_rate_before'])} -> {pct(h['insertion_rate_after'])}; "
                      f"WER {pct(h['wer_before'])} -> {pct(h['wer_after'])}; fraction of correctly spoken words kept: {pct(h['speech_recall'])}.")
    if h.get("stress_test"):
        table([[k, v["n_clips"], pct(v["hallucination_rate_unguarded"]), pct(v["hallucination_rate_guarded"]),
                v["inserted_words_unguarded"], v["inserted_words_guarded"]] for k, v in h["stress_test"].items()],
              ["Clip type | VAD", "Clips", "Hallucination rate (no guard)", "with guard", "Inserted words", "with guard"])
        doc.add_paragraph("Stress clips: digital silence, low-level noise, and a real test utterance with 2.2 s of silence inserted. "
                          "Any word on silence/noise counts as a hallucination. If the guarded rate is not lower, grounding did not help here.")
    else:
        doc.add_paragraph("The silence/pause stress test has not been run.")

    doc.add_heading("6. Selective transcription (Stage 4)", 1)
    se = s["selective"]
    doc.add_paragraph(f"Target accepted-word error rate {pct(se['target_risk'], 0)}. Deployment tau (pooled validation fit) = {num(se['tau'])}. "
                      f"On held-out speakers (per-speaker LOSO tau) the accepted-word error rate was {pct(se['realized_risk_at_tau'])} at "
                      f"{pct(se['coverage_at_target_risk'])} coverage of grounded words (all-word error rate {pct(se['all_word_error_rate'])}); "
                      f"AURC {num(se['aurc'])}. Target met: {se['target_met']}. Note: word-level risk counts substitutions and insertions, not deletions.")
    rcp = os.path.join(os.path.dirname(path), "figures", "risk_coverage.png")
    if os.path.exists(rcp):
        doc.add_picture(rcp, width=Inches(4.8))

    doc.add_heading("7. CPU deployment (INT8)", 1)
    e = s.get("edge")
    if e:
        table([["Real-time factor (median of %d passes)" % e.get("repeats", 0), num(e["fp32_rtf"]), num(e["int8_rtf"])],
               ["WER on same utterances", pct(e.get("fp32_wer")), pct(e["int8_wer"])],
               ["Peak RSS (MB)", num(e.get("fp32_peak_rss_mb"), 0), num(e.get("int8_peak_rss_mb"), 0)],
               ["Model size on disk (MB)", num((e.get("fp32_model_bytes") or 0) / 1e6, 0), num((e.get("int8_model_bytes") or 0) / 1e6, 0)]],
              ["Metric", "FP32 (HF, CPU)", "INT8 (CTranslate2)"])
        doc.add_paragraph(f"Measured on: {e['cpu']}. Speaker {e.get('speaker')}, K={e.get('k')}, {e.get('n_utts')} utterances. "
                          "Raw logits are not available on the INT8 path, so calibration and selective output were evaluated on FP32 only. "
                          "These numbers describe this CPU only.")
    else:
        doc.add_paragraph("The INT8 vs FP32 benchmark has not been run; no real-time or memory claim is made.")

    doc.add_heading("8. Limitations", 1)
    for t in ["TORGO is read speech with a small number of dysarthric speakers; results do not establish performance on spontaneous or clinical speech.",
              "The severity map is a configuration table that must be verified against the TORGO documentation.",
              "Few-shot splits are text-disjoint, but TORGO repeats prompts heavily and many are single words; WER on single words is coarse.",
              "LOSO-style fitting pools validation words of other speakers; with few speakers the fitted T, gamma and tau are noisy. Per-speaker fits are reported as a secondary protocol.",
              "Utterance-level significance tests ignore that utterances are nested in speakers; use the speaker-level interval as the more conservative statement.",
              "The silence/pause stress test uses synthetic silence and noise inserted into real utterances; it is not a clinical measurement.",
              "RTF, memory and size were measured on one CPU and one speaker/budget only."]:
        doc.add_paragraph(t, style="List Bullet")
    if s.get("missing"):
        doc.add_heading("Not measured in this run", 2)
        for m in s["missing"]:
            doc.add_paragraph(m, style="List Bullet")

    doc.add_heading("9. Reproduction", 1)
    doc.add_paragraph("python -m experiments.validate_raw results/raw\npython -m experiments.run_all --raw results/raw --out results\n"
                      "python -m experiments.validate_summary results/summary.json\npython -m experiments.make_report")
    doc.save(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="results/summary.json")
    ap.add_argument("--out", default="results/FewDSR_Results_Chapter.docx")
    ap.add_argument("--allow-fixture", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.exists(a.summary):
        raise SystemExit(f"{a.summary} not found: run experiments.run_all first (no report is written without real results)")
    with open(a.summary, encoding="utf-8") as f:
        s = json.load(f)
    if s.get("is_fixture") and not a.allow_fixture:
        raise SystemExit("summary is marked is_fixture=true (test data): refusing to write a report")
    build_docx(s, a.out)
    print("->", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
