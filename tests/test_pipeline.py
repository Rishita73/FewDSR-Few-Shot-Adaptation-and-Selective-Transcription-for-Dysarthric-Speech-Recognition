import unittest
from core.model_manager import SimulatedBackend
from core.pipeline import run_pipeline
class T(unittest.TestCase):
    def test_all_demo_entries_run(self):
        b = SimulatedBackend()
        for fn in b.db:
            r = run_pipeline(b.transcribe_file(fn, 4.0), 1.35, 1.2, 0.7)
            self.assertEqual(r.selective["accepted"] + r.selective["uncertain"] + r.selective["suppressed"], len(r.transcription.tokens))
            self.assertTrue(r.transcription.is_simulated)
if __name__ == "__main__":
    unittest.main()
