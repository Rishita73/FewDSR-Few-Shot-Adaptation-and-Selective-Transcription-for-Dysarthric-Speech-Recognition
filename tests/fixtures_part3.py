"""SYNTHETIC raw-record generator for Part 3 tests. Nothing here resembles a result: it exists only to
exercise the code paths with known structure (overconfident logits, low-margin insertions).
Never use it to produce numbers for the report; run_all marks such output with --fixture."""
import numpy as np
from experiments import common as C

P_OK = {"baseline": 0.60, "lora": 0.80}


def _logits(rng, ok: bool):
    z0 = 10 + rng.normal(0, .5)
    gap = max(0.2, rng.normal(5.0, 1.5) if ok else rng.normal(3.5, 1.5))
    rest = z0 - gap - np.concatenate([[0.0], np.cumsum(rng.uniform(0.05, 1.0, 18))])
    return [float(z0)] + [float(v) for v in rest]


def make_records(spk, k, cond, n_val=30, n_test=40, ins_p=0.25, seed=0):
    """Same wavs/refs for every (k,cond) of a speaker; model outputs depend on (spk,k,cond)."""
    utt_rng = np.random.default_rng(sum(map(ord, spk)))
    out_rng = np.random.default_rng(sum(map(ord, spk)) * 1000 + k * 10 + (cond == "lora") + seed)
    recs = []
    for split, n in (("val", n_val), ("test", n_test)):
        for i in range(n):
            ref_words = [f"w{int(utt_rng.integers(0, 500))}" for _ in range(3)]
            hyp_words, wd = [], []
            for w in ref_words:
                ok = out_rng.random() < P_OK[cond]
                hyp_words.append(w if ok else f"x{int(out_rng.integers(0, 500))}")
                z = _logits(out_rng, ok)
                wd.append({"word": hyp_words[-1], "topk_logits": z, "null_logit": z[0] - float(out_rng.normal(6.0 if ok else 4.0, 1.0))})
            if out_rng.random() < ins_p:
                z = _logits(out_rng, False)
                hyp_words.append(f"ins{i}")
                wd.append({"word": hyp_words[-1], "topk_logits": z, "null_logit": z[0] - float(out_rng.normal(0.0, 0.7))})
            recs.append({"speaker": spk, "k": k, "condition": cond, "split": split, "wav": f"/fix/{spk}/{split}_{i:03d}.wav",
                         "ref": " ".join(ref_words), "hyp": " ".join(hyp_words), "audio_s": 1.5, "latency_s": 0.4,
                         "first_step_null_logit": 1.0, "words": wd})
    return recs


def write_fixture(raw_dir, speakers=("F04", "M01", "M05"), budgets=(5, 10, 20), **kw):
    for spk in speakers:
        C.write_jsonl(C.raw_path(raw_dir, spk, 0, "baseline"), make_records(spk, 0, "baseline", **kw))
        for k in budgets:
            if k == 20 and spk == "M05":          # deliberately missing: infeasible budget
                continue
            C.write_jsonl(C.raw_path(raw_dir, spk, k, "lora"), make_records(spk, k, "lora", **kw))
