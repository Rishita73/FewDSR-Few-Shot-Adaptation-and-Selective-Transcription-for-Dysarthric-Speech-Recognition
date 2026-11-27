"""Real-model tests. Skipped unless FEWDSR_SLOW=1 (needs torch, transformers, peft, internet/HF cache).
    FEWDSR_SLOW=1 python -m unittest tests.test_part2_slow -v
These were WRITTEN but NOT EXECUTED in the authoring sandbox (no torch). Run them first."""
import os, tempfile, unittest
import numpy as np

SLOW = os.environ.get("FEWDSR_SLOW") == "1"


@unittest.skipUnless(SLOW, "set FEWDSR_SLOW=1")
class TestRealModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.whisper_backend import WhisperBackend
        cls.backend = WhisperBackend(use_vad=False)
        t = np.arange(16000 * 3) / 16000
        cls.audio = (0.3 * np.sin(2 * np.pi * 150 * t)).astype(np.float32)

    def test_record_contract(self):
        tr = self.backend.transcribe(self.audio, 16000)
        for w in tr.tokens:
            self.assertEqual(len(w.topk_logits), 20)
            self.assertTrue(np.all(np.diff(w.topk_logits[1:]) <= 0))
            self.assertTrue(np.isfinite(w.null_logit))      # raw logits, not -inf scores
        self.assertTrue(np.isfinite(tr.first_step_null_logit))

    def test_empty_and_silence_do_not_crash(self):
        self.assertEqual(self.backend.transcribe(np.zeros(10, np.float32), 16000).tokens, [])
        self.backend.transcribe(np.zeros(48000, np.float32), 16000)

    def test_too_long_rejected(self):
        with self.assertRaises(ValueError):
            self.backend.transcribe(np.zeros(16000 * 31, np.float32), 16000)

    def test_lora_wraps_24_cross_attention_modules_and_trainable_pct(self):
        from transformers import WhisperForConditionalGeneration
        from core.lora import build_lora_model, count_trainable
        from fewdsr_config import CFG
        m = build_lora_model(WhisperForConditionalGeneration.from_pretrained(CFG.base_model))
        tr, tot, pct = count_trainable(m)
        self.assertEqual(tr, 294912)                        # 12 layers x 2 proj x (768*8 + 8*768)
        self.assertLess(pct, 0.2); self.assertGreater(pct, 0.05)

    def test_untrained_lora_equals_base_and_adapter_roundtrip(self):
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        from core.lora import build_lora_model
        from core.whisper_backend import WhisperBackend
        from fewdsr_config import CFG
        proc = WhisperProcessor.from_pretrained(CFG.base_model)
        m = build_lora_model(WhisperForConditionalGeneration.from_pretrained(CFG.base_model))
        b = WhisperBackend(model=m, processor=proc, use_vad=False)
        self.assertEqual(b.transcribe(self.audio, 16000).text, self.backend.transcribe(self.audio, 16000).text)  # B=0 => identity
        with tempfile.TemporaryDirectory() as d:
            m.save_pretrained(d)
            b2 = WhisperBackend(adapter_dir=d, use_vad=False)
            self.assertEqual(b2.transcribe(self.audio, 16000).text, b.transcribe(self.audio, 16000).text)


if __name__ == "__main__":
    unittest.main()
