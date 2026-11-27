import unittest
from core import eval_stats as S
from tests.fixtures_part3 import make_records


class TestStats(unittest.TestCase):
    def test_bootstrap_deterministic_and_needs_two(self):
        a = S.bootstrap_ci([.2, .4, .6, .8]); b = S.bootstrap_ci([.2, .4, .6, .8])
        self.assertEqual(a, b)
        self.assertLessEqual(a[0], .5); self.assertGreaterEqual(a[1], .5)
        self.assertIsNone(S.bootstrap_ci([.3]))

    def test_wilcoxon_edge_cases(self):
        self.assertIsNone(S.wilcoxon([1, 2, 3], [1, 2, 3])["p"])
        r = S.wilcoxon(list(range(1, 21)), [x - 0.5 for x in range(1, 21)])
        self.assertLess(r["p"], 0.001)
        self.assertEqual(r["n_nonzero"], 20)

    def test_paired_comparison_detects_improvement_and_pairs_by_wav(self):
        a = {s: make_records(s, 0, "baseline") for s in ("F04", "M01", "M05")}
        b = {s: make_records(s, 10, "lora") for s in ("F04", "M01", "M05")}
        c = S.paired_comparison(a, b)
        self.assertEqual(c["n_speakers"], 3)
        self.assertGreater(c["mean_diff"], 0)                    # lora better by construction
        self.assertLess(c["wilcoxon_utterance_level"]["p"], 0.01)
        self.assertEqual(c["wilcoxon_utterance_level"]["n_pairs"], 3 * 40)
        # swapping the arguments flips the sign
        self.assertAlmostEqual(S.paired_comparison(b, a)["mean_diff"], -c["mean_diff"])

    def test_scaling_missing_budget_is_not_imputed(self):
        raw = {}
        for s in ("F04", "M05"):
            raw[(s, 0, "baseline")] = make_records(s, 0, "baseline")
            raw[(s, 5, "lora")] = make_records(s, 5, "lora")
        raw[("F04", 20, "lora")] = make_records("F04", 20, "lora")
        sc = S.scaling_analysis(raw)
        self.assertEqual(sc["K"], [0, 5, 20])
        self.assertEqual(sc["n_speakers"], [2, 2, 1])
        self.assertIsNone(sc["wer_ci95"][2])                     # one speaker: no CI
        self.assertNotIn("20", sc["per_speaker"]["M05"])


if __name__ == "__main__":
    unittest.main()
