"""End-to-end orchestration of Part 2 scripts with a FAKE backend/adapter (no torch)."""
import io, os, shutil, tempfile, unittest, contextlib
import numpy as np
from scipy.io import wavfile

from core import data as D, metrics as M
from core.interfaces import ASRBackend, TokenInfo, Transcription
from experiments import common as C, run_baseline, run_adapt, validate_raw as V, prepare_data


class FakeBackend(ASRBackend):
    """Identifies the utterance by audio length (each fixture wav has a unique length)."""
    name = "fake"

    def __init__(self, refs, corrupt):
        self.refs, self.corrupt = refs, corrupt

    def transcribe(self, audio, sr):
        ref = self.refs[len(audio)]
        words = ref.split()
        out = [("zzz" if (i % self.corrupt == 0) else w) for i, w in enumerate(words)] if self.corrupt else words
        toks = [TokenInfo(w, np.array([9.0 - 0.1 * j for j in range(20)]), 1.0) for w in out]
        return Transcription(toks, 0.01, len(audio) / sr, self.name)


class FakeAdapter:
    def __init__(self, refs):
        self.refs, self.calls = refs, []

    def adapt(self, speaker, k, split, adapter_dir):
        self.calls.append((speaker, k, len(split.calibration)))
        os.makedirs(adapter_dir, exist_ok=True)
        return FakeBackend(self.refs, corrupt=0), {"best_epoch": 3, "trainable_pct": 0.12}


def build_fixture(root):
    refs, n = {}, [0]
    for spk, uniq in [("F01", 80), ("M01", 80), ("M02", 30)]:
        w = os.path.join(root, spk, "Session1", "wav_headMic"); p = os.path.join(root, spk, "Session1", "prompts")
        os.makedirs(w); os.makedirs(p)
        for i in range(uniq):
            n[0] += 1
            length = 1600 + n[0] * 7
            wavfile.write(os.path.join(w, f"{i:04d}.wav"), 16000, (np.random.default_rng(i).standard_normal(length) * 3000).astype(np.int16))
            txt = f"please say word{i} now"
            open(os.path.join(p, f"{i:04d}.txt"), "w").write(txt)
            refs[length] = txt
    return refs


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        fn(*a, **k)
    return buf.getvalue()


class TestFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tor = os.path.join(self.tmp, "torgo"); os.makedirs(self.tor)
        self.refs = build_fixture(self.tor)
        self.manifest = os.path.join(self.tmp, "m.json")
        self.out = os.path.join(self.tmp, "raw")
        self.out_ad = os.path.join(self.tmp, "adapters")
        quiet(prepare_data.main, ["--torgo-root", self.tor, "--out", self.manifest])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_prepare_data_lists_feasible_budgets(self):
        txt = quiet(prepare_data.main, ["--torgo-root", self.tor, "--out", self.manifest])
        self.assertIn("M02", txt); self.assertIn("[0, 5, 10]", txt)              # 30 prompts: K=20 would leave no test prompt
        self.assertIn("[0, 5, 10, 20, 40]", txt)

    def test_splits_identical_test_across_k_and_max_test(self):
        u = D.load_manifest(self.manifest)
        s = C.speaker_splits(u, "F01", 10, max_test=12)
        self.assertEqual(sorted(s), [0, 5, 10, 20, 40])
        self.assertEqual(len(s[0].test), 12)
        ref = [x.wav for x in s[0].test]
        for sp in s.values():
            self.assertEqual([x.wav for x in sp.test], ref)
        self.assertEqual([x.wav for x in C.speaker_splits(u, "F01", 10, 12)[5].test], ref)   # deterministic
        self.assertEqual(sorted(C.speaker_splits(u, "M02", 10)), [0, 5, 10])

    def run_all(self, **kw):
        fb = lambda: FakeBackend(self.refs, corrupt=3)
        quiet(run_baseline.main, ["--manifest", self.manifest, "--out", self.out, "--max-test", "15"], backend_factory=fb)
        ad = FakeAdapter(self.refs)
        quiet(run_adapt.main, ["--manifest", self.manifest, "--out", self.out, "--adapters", self.out_ad,
                               "--max-test", "15", "--budgets", "5", "10", "40"], adapter=ad)
        return ad

    def test_full_flow_validates_and_improves(self):
        ad = self.run_all()
        errs, tot = V.validate_dir(self.out)
        self.assertEqual(errs, [])
        self.assertGreater(tot["words"], 0)
        files = sorted(os.listdir(self.out))
        self.assertIn("F01_K0_baseline.jsonl", files); self.assertIn("F01_K40_lora.jsonl", files)
        self.assertNotIn("M02_K40_lora.jsonl", files)                 # infeasible K skipped, not faked
        self.assertIn("M02_K10_lora.jsonl", files)
        b = C.summarize(C.read_jsonl(os.path.join(self.out, "F01_K0_baseline.jsonl")))
        l = C.summarize(C.read_jsonl(os.path.join(self.out, "F01_K10_lora.jsonl")))
        self.assertGreater(b["wer"], 0.2); self.assertEqual(l["wer"], 0.0)
        self.assertEqual(b["n_utts"], 15)
        recs = C.read_jsonl(os.path.join(self.out, "F01_K5_lora.jsonl"))
        self.assertEqual({r["split"] for r in recs}, {"val", "test"})
        self.assertEqual(sum(r["split"] == "val" for r in recs), 10)
        self.assertIn(("F01", 5, 5), ad.calls)                         # calibration size == K

    def test_calibration_never_overlaps_eval_texts(self):
        u = D.load_manifest(self.manifest)
        for sp in C.speaker_splits(u, "F01", 10, 15).values():
            cal = {M.normalize_text(x.text) for x in sp.calibration}
            ev = {M.normalize_text(x.text) for x in sp.validation + sp.test}
            self.assertFalse(cal & ev)

    def test_resume_skips_and_force_reruns(self):
        self.run_all()
        out = quiet(run_baseline.main, ["--manifest", self.manifest, "--out", self.out, "--max-test", "15"],
                    backend_factory=lambda: self.fail("must not build backend when everything exists"))
        self.assertIn("skip", out)
        ad = FakeAdapter(self.refs)
        quiet(run_adapt.main, ["--manifest", self.manifest, "--out", self.out, "--adapters", self.out_ad,
                               "--max-test", "15", "--budgets", "5"], adapter=ad)
        self.assertEqual(ad.calls, [])

    def test_k0_rejected_in_adapt_and_unknown_speaker(self):
        with self.assertRaises(SystemExit):
            quiet(run_adapt.main, ["--manifest", self.manifest, "--budgets", "0"], adapter=FakeAdapter(self.refs))
        with self.assertRaises(ValueError):
            quiet(run_baseline.main, ["--manifest", self.manifest, "--speakers", "ZZ9"], backend_factory=lambda: None)

    def test_validator_catches_tampering(self):
        self.run_all()
        p = os.path.join(self.out, "F01_K0_baseline.jsonl")
        recs = C.read_jsonl(p)
        recs[0]["words"][0]["topk_logits"] = recs[0]["words"][0]["topk_logits"][:5]
        recs[1]["words"][0]["null_logit"] = None
        recs[2]["hyp"] = "tampered"
        C.write_jsonl(p, recs)
        errs, _ = V.validate_file(p)
        text = "\n".join(errs)
        self.assertIn("topk_logits must have 20", text)
        self.assertIn("null_logit must be finite", text)
        self.assertIn("hyp != join(words)", text)

    def test_validator_catches_test_set_drift(self):
        self.run_all()
        p = os.path.join(self.out, "F01_K10_lora.jsonl")
        recs = C.read_jsonl(p)
        test_idx = [i for i, r in enumerate(recs) if r["split"] == "test"]
        recs.pop(test_idx[0])
        C.write_jsonl(p, recs)
        errs, _ = V.validate_dir(self.out)
        self.assertTrue(any("test set of F01_K10_lora.jsonl differs" in e or "differs" in e for e in errs))

    def test_smoke_limit_and_filename_check(self):
        quiet(run_baseline.main, ["--manifest", self.manifest, "--out", os.path.join(self.tmp, "smoke"),
                                  "--speakers", "F01", "--limit", "2"], backend_factory=lambda: FakeBackend(self.refs, 0))
        recs = C.read_jsonl(os.path.join(self.tmp, "smoke", "F01_K0_baseline.jsonl"))
        self.assertEqual(len(recs), 4)
        bad = os.path.join(self.tmp, "bad.jsonl"); open(bad, "w").write("{}")
        self.assertTrue(V.validate_file(bad)[0])


if __name__ == "__main__":
    unittest.main()
