import json, os, tempfile, unittest
import numpy as np
from fewdsr_config import CFG
from core import metrics as M
from core.calibration_guard import CalibrationGuard, softmax_top_prob
from core.selective_engine import SelectiveTranscriptionEngine
from core.vad_preprocessor import PausePreservingVAD
from core.interfaces import TokenInfo
from core.model_manager import SimulatedBackend
from core import data as D

SR = 16000


class TestMetrics(unittest.TestCase):
    def test_wer_basic(self):
        self.assertAlmostEqual(M.wer("a b c d", "a b c d"), 0.0)
        self.assertAlmostEqual(M.wer("a b c d", "a x c d"), 0.25)
        self.assertAlmostEqual(M.wer("a b c d", "a b c"), 0.25)
        c = M.word_edit_counts("a b", "a b x y")
        self.assertEqual((c.substitutions, c.deletions, c.insertions), (0, 0, 2))
        self.assertAlmostEqual(c.rate, 1.0)

    def test_wer_can_exceed_one_and_normalises(self):
        self.assertGreater(M.wer("please call", "Please, call! thank you for watching"), 1.0)
        self.assertEqual(M.wer("Hello, World!", "hello world"), 0.0)

    def test_devanagari_not_mangled(self):
        s = "कृपया डॉक्टर को बुलाओ"
        self.assertEqual(M.normalize_text(s), s)
        self.assertEqual(M.wer(s, s), 0.0)
        self.assertAlmostEqual(M.wer(s, "कृपया डॉक्टर को बुलाओ नहीं"), 0.25)

    def test_cer(self):
        self.assertAlmostEqual(M.cer("abcd", "abxd"), 0.25)

    def test_corpus_wer_is_micro_average(self):
        r = M.corpus_wer(["a b c d", "e"], ["a b c d", "x"])
        self.assertAlmostEqual(r["wer"], 1 / 5)

    def test_ece_perfect_and_overconfident(self):
        rng = np.random.default_rng(0)
        conf = rng.uniform(0, 1, 20000)
        correct = rng.uniform(0, 1, 20000) < conf
        self.assertLess(M.expected_calibration_error(conf, correct)[0], 0.02)
        over = np.full(1000, 0.95); corr = np.arange(1000) % 2
        self.assertAlmostEqual(M.expected_calibration_error(over, corr)[0], 0.45, places=2)

    def test_risk_coverage_and_threshold(self):
        conf = np.array([.9, .8, .7, .6, .5, .4])
        corr = np.array([1, 1, 1, 0, 1, 0])
        cov, risk, thr = M.risk_coverage_curve(conf, corr)
        self.assertAlmostEqual(cov[-1], 1.0)
        self.assertAlmostEqual(risk[2], 0.0)
        self.assertAlmostEqual(risk[-1], 2 / 6)
        self.assertAlmostEqual(M.threshold_for_target_risk(conf, corr, 0.0), 0.7)
        self.assertEqual(M.threshold_for_target_risk([.9], [0], 0.0), float("inf"))
        self.assertTrue(0 <= M.aurc(conf, corr) <= 1)


class TestCalibration(unittest.TestCase):
    def _overconfident_data(self, n=4000, seed=1):
        rng = np.random.default_rng(seed)
        # logits are too sharp: top logit +4 over rivals but only ~70 % correct
        Z = np.sort(rng.normal(0, 1, (n, 6)), axis=1)[:, ::-1].copy()
        Z[:, 0] += 4.0
        y = (rng.uniform(size=n) < 0.70).astype(int)
        return Z, y

    def test_fit_temperature_reduces_ece_and_keeps_argmax(self):
        Z, y = self._overconfident_data()
        g = CalibrationGuard()
        before = M.expected_calibration_error(softmax_top_prob(Z, 1.0), y)[0]
        T = g.fit_temperature(Z, y)
        after = M.expected_calibration_error(g.calibrated_confidence(Z), y)[0]
        self.assertGreater(T, 1.5)
        self.assertLess(after, before / 3)
        self.assertTrue(np.all(np.argmax(Z, 1) == np.argmax(Z / T, 1)))

    def test_fit_temperature_validates_input(self):
        with self.assertRaises(ValueError):
            CalibrationGuard().fit_temperature(np.zeros((0, 3)), [])

    def test_grounding_margin(self):
        g = CalibrationGuard(gamma=1.2)
        self.assertTrue(g.is_grounded(8.0, 1.0))
        self.assertFalse(g.is_grounded(4.1, 4.3))
        self.assertAlmostEqual(g.margin(5, 2), 3.0)

    def test_fit_gamma_keeps_recall(self):
        rng = np.random.default_rng(3)
        speech = rng.normal(5, 1, 1000); halluc = rng.normal(-0.5, 1, 1000)
        d = np.concatenate([speech, halluc]); s = np.r_[np.ones(1000), np.zeros(1000)]
        g = CalibrationGuard(); gamma = g.fit_gamma(d, s, 0.95)
        self.assertGreaterEqual(np.mean(speech >= gamma), 0.949)
        self.assertLess(np.mean(halluc >= gamma), 0.05)


def _tok(w, top, null, gap=2.0):
    """gap = spacing between successive top-k logits (small gap => flat => low confidence)."""
    return TokenInfo(w, np.array([top - i * gap for i in range(4)], dtype=float), null)


class TestSelective(unittest.TestCase):
    def test_three_way_rule(self):
        g = CalibrationGuard(temperature=1.0, gamma=1.2)
        toks = g.apply([_tok("call", 9.0, 1.0), _tok("maybe", 5.0, 1.0, gap=0.1), _tok("thank", 9.0, 9.5)])
        self.assertTrue(toks[0].grounded and not toks[2].grounded)
        r = SelectiveTranscriptionEngine(0.7).process(toks)
        self.assertEqual(r["text"], "call [UNCERTAIN: maybe]")
        self.assertEqual((r["accepted"], r["uncertain"], r["suppressed"]), (1, 1, 1))
        self.assertAlmostEqual(r["coverage"], 0.5)

    def test_html_is_escaped(self):
        g = CalibrationGuard(); t = g.apply([_tok("<script>", 9, 1)])
        self.assertNotIn("<script>", SelectiveTranscriptionEngine().process(t)["html"])

    def test_fit_tau(self):
        e = SelectiveTranscriptionEngine()
        tau = e.fit_tau([.95, .9, .6, .5], [1, 1, 0, 0], 0.0)
        self.assertAlmostEqual(tau, 0.9)


class TestVAD(unittest.TestCase):
    def _sig(self, pause_s):
        rng = np.random.default_rng(0)
        t = np.arange(int(SR * 1.0)) / SR
        tone = 0.4 * np.sin(2 * np.pi * 180 * t)
        noise = lambda s: 0.002 * rng.standard_normal(int(SR * s))
        return np.concatenate([noise(0.5), tone, noise(pause_s), tone, noise(0.5)]).astype(np.float32)

    def test_short_pause_is_bridged_long_pause_splits(self):
        v = PausePreservingVAD(SR, hangover_ms=600)
        r1 = v.process(self._sig(0.5))
        self.assertEqual(len(r1["segments"]), 1)
        self.assertTrue(r1["preserved_pauses"])
        r2 = v.process(self._sig(1.5))
        self.assertEqual(len(r2["segments"]), 2)

    def test_hangover_parameter_matters(self):
        sig = self._sig(0.5)
        self.assertEqual(len(PausePreservingVAD(SR, hangover_ms=100).process(sig)["segments"]), 2)
        self.assertEqual(len(PausePreservingVAD(SR, hangover_ms=600).process(sig)["segments"]), 1)

    def test_silence_has_no_speech_and_trim_keeps_internal_pause(self):
        v = PausePreservingVAD(SR)
        self.assertEqual(v.process(np.zeros(SR))["segments"], [])
        sig = self._sig(0.5)
        out = v.trim(sig)
        self.assertLess(len(out), len(sig))
        self.assertGreater(len(out), int(SR * 2.4))     # 2 s tone + 0.5 s pause kept

    def test_short_input(self):
        self.assertEqual(PausePreservingVAD(SR).process(np.zeros(10))["segments"], [])


class TestData(unittest.TestCase):
    def _fake_torgo(self, root):
        for spk, n in [("F01", 80), ("M01", 80), ("FC01", 5)]:
            for sess in ("Session1",):
                w = os.path.join(root, spk, sess, "wav_headMic"); p = os.path.join(root, spk, sess, "prompts")
                os.makedirs(w); os.makedirs(p)
                for i in range(n):
                    open(os.path.join(w, f"{i:04d}.wav"), "wb").close()
                    txt = f"sentence number {i % 60}" if i < 75 else "[image of a cat]"
                    open(os.path.join(p, f"{i:04d}.txt"), "w").write(txt)

    def test_manifest_and_filtering(self):
        with tempfile.TemporaryDirectory() as r:
            self._fake_torgo(r)
            u = D.build_manifest(r)
            self.assertTrue(all(not x.text.startswith("[") for x in u))
            self.assertEqual({x.speaker for x in u}, {"F01", "M01", "FC01"})
            self.assertTrue(all(x.is_control for x in u if x.speaker == "FC01"))
            self.assertEqual(next(x for x in u if x.speaker == "M01").severity, "severe")
            p = os.path.join(r, "m.json"); D.save_manifest(u, p)
            self.assertEqual(len(D.load_manifest(p)), len(u))

    def test_split_is_text_disjoint_deterministic_and_nested(self):
        with tempfile.TemporaryDirectory() as r:
            self._fake_torgo(r); u = D.build_manifest(r)
            s = D.nested_budget_splits(u, "F01")
            norm = lambda L: {M.normalize_text(x.text) for x in L}
            for k, sp in s.items():
                self.assertEqual(len(sp.calibration), k)
                self.assertFalse(norm(sp.calibration) & norm(sp.test))
                self.assertFalse(norm(sp.validation) & norm(sp.test))
                self.assertFalse(norm(sp.calibration) & norm(sp.validation))
            self.assertEqual([x.wav for x in s[5].calibration], [x.wav for x in s[10].calibration[:5]])
            self.assertEqual([x.wav for x in s[0].test], [x.wav for x in s[40].test])
            s2 = D.nested_budget_splits(u, "F01")
            self.assertEqual([x.wav for x in s[10].calibration], [x.wav for x in s2[10].calibration])

    def test_missing_root(self):
        with self.assertRaises(FileNotFoundError):
            D.build_manifest("/nonexistent")


class TestSimulatedBackend(unittest.TestCase):
    def test_flagged_simulated_and_pipeline(self):
        b = SimulatedBackend()
        tr = b.transcribe_file("torgo_pause_hallucination.wav", 5.5)
        self.assertTrue(tr.is_simulated)
        g = CalibrationGuard(); g.apply(tr.tokens)
        out = SelectiveTranscriptionEngine(0.5).process(tr.tokens)
        self.assertEqual(out["suppressed"], 4)
        self.assertNotIn("Thank", out["text"])
        with self.assertRaises(KeyError):
            b.transcribe_file("unknown.wav")

    def test_config_lora_targets_cross_attention_only(self):
        import re
        rx = re.compile(CFG.lora_target_regex)
        self.assertTrue(rx.fullmatch("model.decoder.layers.3.encoder_attn.q_proj"))
        self.assertFalse(rx.fullmatch("model.decoder.layers.3.self_attn.q_proj"))
        self.assertFalse(rx.fullmatch("model.encoder.layers.3.self_attn.q_proj"))
        self.assertFalse(rx.fullmatch("model.decoder.layers.3.encoder_attn.k_proj"))


if __name__ == "__main__":
    unittest.main()


class TestLabels(unittest.TestCase):
    def test_hyp_word_labels(self):
        self.assertEqual(M.hyp_word_labels("please call doctor at ten",
                                           "please call doctor thank you at ten"),
                         ["C", "C", "C", "I", "I", "C", "C"])
        self.assertEqual(M.hyp_word_labels("a b c", "a x c"), ["C", "S", "C"])
        self.assertEqual(M.hyp_word_labels("a b c", "a c"), ["C", "C"])
        self.assertEqual(M.hyp_word_labels("a b", ""), [])
        for ref, hyp in [("a b c d e", "a x c e f g"), ("one two", "two one")]:
            lab = M.hyp_word_labels(ref, hyp)
            self.assertEqual(len(lab), len(hyp.split()))
            self.assertLessEqual(lab.count("C"), len(ref.split()))   # cannot match more words than the ref has
