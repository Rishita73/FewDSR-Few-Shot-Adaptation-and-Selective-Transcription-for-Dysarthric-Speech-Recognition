"""Audio loading: mono float32 in [-1, 1] at the target sample rate.
Uses soundfile when installed, else scipy (16/32-bit PCM or float wav)."""
from __future__ import annotations
from math import gcd
import numpy as np
from fewdsr_config import CFG


def _read(path: str):
    try:
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32", always_2d=False)
        return np.asarray(data, dtype=np.float32), int(sr)
    except ImportError:
        from scipy.io import wavfile
        sr, data = wavfile.read(path)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype == np.uint8:
            data = (data.astype(np.float32) - 128.0) / 128.0
        else:
            data = data.astype(np.float32)
        return data, int(sr)


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out or len(x) == 0:
        return x.astype(np.float32)
    from scipy.signal import resample_poly
    g = gcd(sr_in, sr_out)
    return resample_poly(x, sr_out // g, sr_in // g).astype(np.float32)


def load_audio(path: str, sr: int = CFG.sample_rate) -> np.ndarray:
    data, sr_in = _read(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = resample(data, sr_in, sr)
    return np.clip(data, -1.0, 1.0).astype(np.float32)
