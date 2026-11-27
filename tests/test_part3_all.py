"""End-to-end Part 3 flow on SYNTHETIC fixture raw files (never real results)."""
import contextlib, io, json, os, shutil, tempfile, unittest, warnings
warnings.simplefilter("ignore", ResourceWarning)
import numpy as np
from docx import Document

from core import data as D
from experiments import common as C, run_all, run_calibration, validate_summary, make_report, run_silence_stress
from core.interfaces import ASRBackend, TokenInfo, Transcription
from tests.fixtures_part3 import write_fixture, make_records


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()) as b:
        r = fn(*a, **k)
    return r, b.getvalue()


class TestAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.raw = os.path.join(self.tmp, "raw"); self.res = os.path.join(self.tmp, "results")
        write_fixture(self.raw)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra):
        return quiet(run_all.main, ["--raw", self.raw, "--out", self.res, "--adapters", os.path.join(self.tmp, "none"), "--boot", "200", *extra])

    def test_summary_validates_and_reports_missing_honestly(self):
        rc, out = self._run("--fixture")
        self.assertEqual(rc, 0, out)
        s = json.load(open(os.path.join(self.res, "summary.json")))
        self.assertEqual(validate_summary.validate(s), [])
        self.assertTrue(s["is_fixture"])
        self.assertEqual(s["calibration"]["headline_condition"], "lora_K10")
        self.assertEqual(s["scaling"]["K"], [0, 5, 10, 20])
        self.assertEqual(s["scaling"]["n_speakers"], [3, 3, 3, 2])           # M05 has no K=20: reported, not imputed
        self.assertEqual(s["speakers"]["M05"]["budgets_missing"], [20, 40])
        self.assertEqual(s["speakers"]["F04"]["budgets_missing"], [40])
        miss = " ".join(s["missing"])
        for must in ("stress test", "edge", "LoRA trainable"):
            self.assertIn(must, miss)
        self.assertIsNone(s["edge"]); self.assertIsNone(s["lora"]); self.assertIsNone(s["hallucination"]["stress_test"])
        self.assertLess(s["calibration"]["ece_after"], s["calibration"]["ece_before"])
        self.assertIsNotNone(s["stats"]["wilcoxon_p_k0_vs_k10"])
        for f in ("scaling_curve", "reliability", "risk_coverage", "wer_by_severity"):
            self.assertTrue(os.path.getsize(os.path.join(self.res, "figures", f + ".png")) > 1000)
        self.assertTrue(set(s["deploy_params"]) >= {"baseline", "lora_K5", "lora_K10", "lora_K20"})
        self.assertEqual(len(s["provenance"]["raw_file_sha256_16"]), 11)   # 3 baseline + 3x2 lora + 2 K20

    def test_headline_choice_and_unknown_headline(self):
        _, _ = self._run("--fixture", "--headline", "baseline")
        s = json.load(open(os.path.join(self.res, "summary.json")))
        self.assertEqual(s["calibration"]["headline_condition"], "baseline")
        with self.assertRaises(SystemExit):
            self._run("--headline", "lora_K99")

    def test_refuses_invalid_raw(self):
        p = C.raw_path(self.raw, "F04", 0, "baseline")
        recs = C.read_jsonl(p); recs[0]["hyp"] += " extra"                     # hyp != join(words)
        C.write_jsonl(p, recs)
        with self.assertRaises(SystemExit):
            self._run()

    def test_validator_catches_schema_damage(self):
        self._run("--fixture")
        s = json.load(open(os.path.join(self.res, "summary.json")))
        s["calibration"]["ece_after"] = 1.7; del s["selective"]["tau"]; s["scaling"]["wer_mean"].pop()
        errs = validate_summary.validate(s)
        self.assertTrue(any("ece_after" in e for e in errs)); self.assertTrue(any("selective.tau" in e for e in errs))
        self.assertTrue(any("lengths differ" in e for e in errs))

    def test_stress_and_edge_inputs_are_picked_up(self):
        class Echo(ASRBackend):
            name = "echo"
            def transcribe(self, audio, sr):
                # hallucinates a low-margin word on silence, nothing otherwise
                if float(np.abs(audio).max()) < 0.05:
                    z = [5.0] + [1.0] * 19
                    return Transcription([TokenInfo("thanks", np.array(z), 4.9)], 0.01, len(audio) / sr, "echo")
                return Transcription([], 0.01, len(audio) / sr, "echo")
        # fake manifest of real (tiny) wavs
        from scipy.io import wavfile
        wd = os.path.join(self.tmp, "wav"); os.makedirs(wd)
        utts = []
        for i in range(40):
            p = os.path.join(wd, f"{i:03d}.wav"); wavfile.write(p, 16000, (np.random.default_rng(i).standard_normal(8000) * 3000).astype(np.int16))
            utts.append(D.Utt("F04", "S1", p, f"word{i} here", False, "mild"))
        recs = run_silence_stress.run_stress(lambda vad: Echo(), utts, lambda p: wavfile.read(p)[1].astype(np.float32) / 32768, 3, ["F04"], 10, 100, log=lambda *_: None)
        self.assertEqual(len(recs), 3 * 3 * 2)                                  # 3 utts x 3 clip kinds x vad on/off
        os.makedirs(os.path.join(self.res, "stress")); C.write_jsonl(os.path.join(self.res, "stress", "stress.jsonl"), recs)
        os.makedirs(os.path.join(self.res, "edge"))
        json.dump({"cpu": "TEST CPU", "fp32_rtf": 0.9, "int8_rtf": 0.4, "int8_wer": 0.3, "fp32_wer": 0.29, "repeats": 3}, open(os.path.join(self.res, "edge", "edge.json"), "w"))
        os.makedirs(os.path.join(self.tmp, "ad", "F04_K10")); json.dump({"trainable_pct": 0.12, "trainable_params": 294912, "total_params": 241000000}, open(os.path.join(self.tmp, "ad", "F04_K10", "train_info.json"), "w"))
        rc, out = quiet(run_all.main, ["--raw", self.raw, "--out", self.res, "--adapters", os.path.join(self.tmp, "ad"), "--boot", "100", "--fixture"])
        self.assertEqual(rc, 0, out)
        s = json.load(open(os.path.join(self.res, "summary.json")))
        st = s["hallucination"]["stress_test"]
        self.assertIsNotNone(st)
        z = st["zeros|vad=off"]
        self.assertEqual(z["hallucination_rate_unguarded"], 1.0)
        self.assertEqual(z["hallucination_rate_guarded"], 0.0)                  # margin 0.1 < fitted gamma
        self.assertEqual(s["edge"]["cpu"], "TEST CPU"); self.assertEqual(s["lora"]["trainable_params"], 294912)
        self.assertFalse(any("stress test not run" in m for m in s["missing"]))

    def test_report_built_from_summary_only_and_refuses_fixture(self):
        self._run("--fixture")
        sp = os.path.join(self.res, "summary.json"); out = os.path.join(self.tmp, "r.docx")
        with self.assertRaises(SystemExit):
            make_report.main(["--summary", sp, "--out", out])
        with self.assertRaises(SystemExit):
            make_report.main(["--summary", os.path.join(self.tmp, "nope.json"), "--out", out, "--allow-fixture"])
        make_report.main(["--summary", sp, "--out", out, "--allow-fixture"])
        text = "\n".join(p.text for p in Document(out).paragraphs)
        for needle in ("Limitations", "LOSO", "has not been run"):
            self.assertIn(needle, text)
        s = json.load(open(sp))
        self.assertIn(f"{s['calibration']['ece_before']:.3f}", text)           # number came from summary
        self.assertNotRegex(text, r"36\.4|0\.284|0\.082")

    def test_verdict_reports_negative_and_null_results(self):
        v = make_report.verdict
        self.assertIn("HIGHER", v({"n_speakers": 4, "mean_wer_a": .3, "mean_wer_b": .4, "mean_diff": -.1, "diff_ci95": [-.15, -.05]}, "K0", "K10"))
        self.assertIn("no reliable difference", v({"n_speakers": 4, "mean_wer_a": .3, "mean_wer_b": .29, "mean_diff": .01, "diff_ci95": [-.05, .06]}, "K0", "K10"))
        self.assertIn("excludes zero", v({"n_speakers": 4, "mean_wer_a": .5, "mean_wer_b": .3, "mean_diff": .2, "diff_ci95": [.1, .3]}, "K0", "K10"))
        self.assertIn("Too few", v({"n_speakers": 1, "mean_wer_a": .5, "mean_wer_b": .3, "mean_diff": .2, "diff_ci95": None}, "K0", "K10"))

    def test_run_calibration_cli(self):
        out = os.path.join(self.tmp, "cal.json")
        rc, txt = quiet(run_calibration.main, ["--raw", self.raw, "--out", out])
        self.assertEqual(rc, 0)
        self.assertIn("loso", txt); self.assertIn("lora_K10", txt)
        self.assertEqual(sorted(json.load(open(out))["conditions"]), ["baseline", "lora_K10", "lora_K20", "lora_K5"])


if __name__ == "__main__":
    unittest.main()
