import unittest
import numpy as np
from core import eval_calibration as E
from core.eval_calibration import WordTable, FitError
from tests.fixtures_part3 import make_records


def rec(ref, words, split="val"):
    return {"speaker": "S", "k": 0, "condition": "baseline", "split": split, "wav": "x.wav", "ref": ref,
            "hyp": " ".join(w[0] for w in words), "audio_s": 1.0, "latency_s": 0.1,
            "words": [{"word": w, "topk_logits": [5.0] + [4.0 - i * .1 for i in range(19)], "null_logit": n} for w, n in words]}


class TestLabels(unittest.TestCase):
    def test_punctuation_and_apostrophe(self):
        r = rec("hello don't stop", [("Hello,", 0.0), ("don't", 0.0), ("—", 0.0), ("stop", 0.0), ("now", 0.0)])
        self.assertEqual(E.record_word_labels(r), ["C", "C", None, "C", "I"])

    def test_tampered_words_rejected(self):
        r = rec("a b", [("a", 0.0), ("b", 0.0)])
        r["hyp"] = "a b c"
        with self.assertRaises(ValueError):
            E.record_word_labels(r)


class TestLeakageGuard(unittest.TestCase):
    def test_test_records_never_reach_fitting_table(self):
        with self.assertRaises(AssertionError):
            E.words_table([rec("a", [("a", 0.0)], split="test")], "val")


class TestFit(unittest.TestCase):
    def setUp(self):
        self.val = E.words_table([r for r in make_records("F04", 0, "baseline") if r["split"] == "val"], "val")

    def test_overconfident_logits_give_T_above_one_and_grounding_margin(self):
        p = E.fit_params(self.val, 0.10)
        self.assertGreater(p.T, 1.0)
        self.assertTrue(np.isfinite(p.gamma))
        # inserted words have delta ~ 0, spoken words ~ 4-6: gamma must sit between
        self.assertGreater(p.gamma, 0.5)
        self.assertEqual(p.n_words, len(self.val))

    def test_all_correct_validation_keeps_T_one(self):
        t = E.words_table([rec("a b c d e f", [(w, -3.0) for w in "abcdef"])] * 2, "val")
        p = E.fit_params(t)
        self.assertEqual(p.T, 1.0)
        self.assertTrue(any("not fitted" in w for w in p.warnings))

    def test_zero_words_raises(self):
        with self.assertRaises(FitError):
            E.fit_params(WordTable.concat([]))

    def test_abstain_all_when_target_unreachable_does_not_crash(self):
        val = E.words_table([rec("a b c d e f", [(w.upper() if False else f"z{w}", -3.0) for w in "abcdef"])] * 2, "val")
        p = E.fit_params(val, 0.10)
        self.assertTrue(np.isinf(p.tau))
        self.assertTrue(any("abstain" in w for w in p.warnings))
        test = [r for r in make_records("F04", 0, "baseline") if r["split"] == "test"]
        out = E.summarize_scored(E.score_test(test, p), 0.10)
        self.assertEqual(out["selective"]["n_accepted"], 0)
        self.assertEqual(out["selective"]["coverage_at_tau"], 0.0)
        self.assertIsNone(out["selective"]["realized_risk_at_tau"])


class TestCondition(unittest.TestCase):
    def setUp(self):
        self.recs = {s: make_records(s, 0, "baseline") for s in ("F04", "M01", "M05")}
        self.sev = {"F04": "mild", "M01": "severe", "M05": "moderate"}

    def test_calibration_and_grounding_improve_on_structured_data(self):
        res = E.evaluate_condition(self.recs, self.sev)
        pooled = res["protocols"]["loso"]["pooled"]
        self.assertLess(pooled["calibration"]["ece_after"], pooled["calibration"]["ece_before"])
        self.assertLess(pooled["calibration"]["nll_after"], pooled["calibration"]["nll_before"])
        g = pooled["grounding"]
        self.assertLess(g["insertion_rate_after"], g["insertion_rate_before"])
        self.assertGreater(g["speech_recall"], 0.85)
        se = pooled["selective"]
        self.assertLess(se["realized_risk_at_tau"], se["all_word_error_rate"])
        self.assertEqual(set(res["protocols"]["loso"]["by_severity"]), {"mild", "severe", "moderate"})

    def test_loso_ignores_heldout_validation_but_local_uses_it(self):
        base = E.evaluate_condition(self.recs, self.sev)
        broken = {s: [dict(r) for r in rs] for s, rs in self.recs.items()}
        for r in broken["M01"]:
            if r["split"] == "val":
                r["words"] = [dict(w, null_logit=w["topk_logits"][0] - 50.0) for w in r["words"]]   # absurd margins
        res = E.evaluate_condition(broken, self.sev)
        self.assertEqual(base["protocols"]["loso"]["params"]["M01"], res["protocols"]["loso"]["params"]["M01"])
        self.assertNotEqual(base["protocols"]["local"]["params"]["M01"]["gamma"], res["protocols"]["local"]["params"]["M01"]["gamma"])

    def test_single_speaker_condition_reports_loso_unavailable(self):
        res = E.evaluate_condition({"F04": self.recs["F04"]}, self.sev)
        self.assertTrue(res["protocols"]["loso"]["pooled"].get("empty"))
        self.assertIn("F04", res["protocols"]["loso"]["errors"])
        self.assertFalse(res["protocols"]["local"]["pooled"].get("empty"))


class TestStress(unittest.TestCase):
    def test_guard_removes_low_margin_words_only(self):
        mk = lambda kind, vad, words: {"kind": kind, "vad": vad, "ref": "", "hyp": " ".join(w for w, _ in words),
                                       "words": [{"word": w, "topk_logits": [5.0] + [1.0] * 19, "null_logit": 5.0 - d} for w, d in words]}
        recs = [mk("zeros", False, [("thank", 0.1), ("you", 0.2)]), mk("zeros", False, [("hi", 3.0)]), mk("zeros", False, [])]
        out = E.stress_hallucination(recs, gamma=1.0)["zeros|vad=off"]
        self.assertEqual(out["n_clips"], 3)
        self.assertAlmostEqual(out["hallucination_rate_unguarded"], 2 / 3)
        self.assertAlmostEqual(out["hallucination_rate_guarded"], 1 / 3)
        self.assertEqual((out["inserted_words_unguarded"], out["inserted_words_guarded"]), (3, 1))


if __name__ == "__main__":
    unittest.main()
