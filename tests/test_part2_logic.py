import os, tempfile, unittest
import numpy as np
from scipy.io import wavfile
from core.word_align import steps_from_logits, group_into_words
from core.audio_io import load_audio, resample
from core.lora import encode_labels
from core.interfaces import Transcription


class TestStepsFromLogits(unittest.TestCase):
    def test_emitted_is_first_rest_descending_and_null(self):
        rng = np.random.default_rng(0)
        L = rng.normal(0, 1, (4, 100)).astype(np.float32)
        gen = [int(L[t].argmax()) for t in range(4)]
        topk, null = steps_from_logits(gen, L, null_id=7, k=20)
        self.assertEqual(topk.shape, (4, 20))
        for t in range(4):
            self.assertAlmostEqual(float(topk[t, 0]), float(L[t].max()), places=5)
            self.assertTrue(np.all(np.diff(topk[t, 1:]) <= 0))
            self.assertLessEqual(topk[t, 1], topk[t, 0])
            self.assertAlmostEqual(float(null[t]), float(L[t, 7]), places=5)

    def test_emitted_not_argmax_is_still_first(self):
        L = np.arange(50, dtype=np.float32)[None, :]          # argmax = 49
        topk, _ = steps_from_logits([10], L, 0, k=5)
        self.assertEqual(float(topk[0, 0]), 10.0)              # emitted logit first
        self.assertEqual(list(topk[0, 1:]), [49.0, 48.0, 47.0, 46.0])

    def test_errors(self):
        with self.assertRaises(ValueError):
            steps_from_logits([1, 2], np.zeros((1, 30), np.float32), 0, 5)
        with self.assertRaises(ValueError):
            steps_from_logits([1], np.zeros((1, 3), np.float32), 0, 5)


VOCAB = {1: " she", 2: " had", 3: " gre", 4: "asy", 5: ",", 6: " dark", 7: ".", 99: "<|eot|>", 98: "<|en|>"}
decode = lambda ids: "".join(VOCAB[i] for i in ids)


def _topk(top, gap):
    return np.array([top - j * gap for j in range(20)], dtype=np.float32)


class TestGrouping(unittest.TestCase):
    def test_words_special_punct_and_min_conf_subtoken(self):
        ids = [98, 1, 2, 3, 4, 5, 6, 7, 99]
        tk = np.stack([_topk(9, 3.0)] * len(ids)); nl = np.arange(len(ids), dtype=float)
        tk[3] = _topk(5, 3.0)         # " gre": confident
        tk[4] = _topk(5, 0.2)         # "asy": the LEAST confident subtoken of "greasy"
        tk[5] = _topk(5, 0.01)        # "," punctuation: flat but must be ignored
        words = group_into_words(ids, tk, nl, decode, {98, 99})
        self.assertEqual([w.word for w in words], ["she", "had", "greasy,", "dark."])
        g = words[2]
        self.assertTrue(np.allclose(g.topk_logits, tk[4]))     # carried by "asy", not "," nor " gre"
        self.assertEqual(g.null_logit, 4.0)
        self.assertLess(g.raw_conf, words[0].raw_conf)

    def test_punct_only_word_dropped_and_empty(self):
        ids = [7]
        words = group_into_words(ids, np.stack([_topk(5, 1)]), np.zeros(1), decode, set())
        self.assertEqual(words, [])
        self.assertEqual(group_into_words([], np.zeros((0, 20)), np.zeros(0), decode, set()), [])

    def test_utf8_split_across_tokens_decodes_jointly(self):
        # a Devanagari word whose two byte-level pieces are individually undecodable
        pieces = {1: " \u0915", 2: "\u0943"}
        dec = lambda ids: "".join(pieces[i] for i in ids)
        w = group_into_words([1, 2], np.stack([_topk(6, 2)] * 2), np.zeros(2), dec, set())
        self.assertEqual([x.word for x in w], ["\u0915\u0943"])


class TestAudioIO(unittest.TestCase):
    def test_resample_stereo_int16(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.wav")
            t = np.arange(44100) / 44100
            st = np.stack([np.sin(2 * np.pi * 440 * t)] * 2, axis=1)
            wavfile.write(p, 44100, (st * 20000).astype(np.int16))
            x = load_audio(p)
            self.assertEqual(x.dtype, np.float32); self.assertEqual(x.ndim, 1)
            self.assertAlmostEqual(len(x), 16000, delta=2)
            self.assertLessEqual(float(np.abs(x).max()), 1.0)
            self.assertGreater(float(np.abs(x).max()), 0.5)
            self.assertEqual(len(resample(np.zeros(0, np.float32), 8000, 16000)), 0)


class FakeTok:
    def set_prefix_tokens(self, **k): pass
    def __call__(self, text):
        class O: pass
        o = O(); o.input_ids = [50258, 50259, 50359, 50363] + [100 + len(w) for w in text.split()] + [50257]
        return o


class TestLabels(unittest.TestCase):
    def test_encode_labels(self):
        y = encode_labels(FakeTok(), "ab cde", 50258)
        self.assertEqual(y, [-100, -100, -100, 102, 103, 50257])


class TestInterfaces(unittest.TestCase):
    def test_new_field_defaults(self):
        self.assertTrue(np.isnan(Transcription(tokens=[]).first_step_null_logit))


if __name__ == "__main__":
    unittest.main()
