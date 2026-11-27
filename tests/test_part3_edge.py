import py_compile, unittest
import numpy as np
from core.interfaces import ASRBackend, TokenInfo, Transcription
from experiments import run_edge as R


class Fake(ASRBackend):
    name = "fake"
    def __init__(self, ref_by_len, lat_per_s=0.1):
        self.ref, self.lat, self.calls = ref_by_len, lat_per_s, 0
    def transcribe(self, audio, sr):
        self.calls += 1
        toks = [TokenInfo(w, np.zeros(1), 0.0) for w in self.ref[len(audio)].split()]
        return Transcription(toks, self.lat * len(audio) / sr, len(audio) / sr, "fake")


class TestEdge(unittest.TestCase):
    def setUp(self):
        self.audios = [np.zeros(16000, np.float32), np.zeros(32000, np.float32)]
        self.refs = {16000: "hello world", 32000: "good morning now"}

    def test_rtf_wer_warmup_and_repeats(self):
        b = Fake(self.refs, 0.25)
        r = R.measure_backend(b, self.audios, ["hello world", "good evening now"], repeats=3, warmup=1)
        self.assertEqual(b.calls, (1 + 3) * 2)
        self.assertAlmostEqual(r["rtf_median"], 0.25)
        self.assertEqual(len(r["rtf_runs"]), 3)
        self.assertAlmostEqual(r["wer"], 1 / 5)                  # one substitution in 5 reference words
        self.assertAlmostEqual(r["audio_s"], 3.0)

    def test_fewer_than_three_repeats_refused(self):
        with self.assertRaises(ValueError):
            R.measure_backend(Fake(self.refs), self.audios, ["a", "b"], repeats=2)

    def test_helpers(self):
        self.assertTrue(R.cpu_string())
        self.assertGreater(R.peak_rss_mb(), 1.0)

    def test_torch_dependent_modules_at_least_compile(self):
        for f in ("core/ct2_backend.py", "experiments/run_edge.py", "experiments/run_silence_stress.py"):
            py_compile.compile(f, doraise=True)

    def test_ct2_backend_declares_no_logits(self):
        from core import ct2_backend
        self.assertFalse(ct2_backend.CT2Backend.provides_logits)


if __name__ == "__main__":
    unittest.main()
