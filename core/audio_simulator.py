import os
import numpy as np
from scipy.io import wavfile
import scipy.signal as signal

def process_dysarthric_speech(input_wav, output_wav, severity="mild", pause_at=None, pause_duration=0.8):
    sr, data = wavfile.read(input_wav)
    data = data.astype(np.float32) / 32768.0

    if severity == "mild":
        # Mild: slight vowel lengthening and mild formant blur
        # Apply gentle low-pass to simulate reduced high-frequency consonant clarity
        b, a = signal.butter(4, 3800 / (sr / 2), btype='low')
        filtered = signal.lfilter(b, a, data)
        # Add slight physiological vocal jitter (3 Hz)
        t = np.linspace(0, len(filtered) / sr, len(filtered))
        jitter = 1.0 + 0.04 * np.sin(2 * np.pi * 3.5 * t)
        out_audio = filtered * jitter

    elif severity == "moderate":
        # Moderate: slower cadence, articulatory slurring, intermittent pause
        b, a = signal.butter(4, 2800 / (sr / 2), btype='low')
        filtered = signal.lfilter(b, a, data)
        # Moderate amplitude tremor (5 Hz) characteristic of cerebral palsy
        t = np.linspace(0, len(filtered) / sr, len(filtered))
        tremor = 1.0 + 0.12 * np.sin(2 * np.pi * 5.0 * t)
        filtered = filtered * tremor
        # Insert breathing pause in the middle
        mid_pt = int(len(filtered) * 0.45)
        pause_samples = int(sr * pause_duration)
        pause_noise = 0.002 * np.random.randn(pause_samples)
        out_audio = np.concatenate([filtered[:mid_pt], pause_noise, filtered[mid_pt:]])

    elif severity == "severe":
        # Severe: low-pass blur, vocal fatigue, tremor, low intensity, breathy noise
        b, a = signal.butter(4, 2000 / (sr / 2), btype='low')
        filtered = signal.lfilter(b, a, data)
        t = np.linspace(0, len(filtered) / sr, len(filtered))
        tremor = 1.0 + 0.22 * np.sin(2 * np.pi * 4.2 * t)
        # Add breathy aspiration noise
        breath_noise = 0.015 * np.random.randn(len(filtered))
        filtered = (filtered * tremor * 0.75) + breath_noise
        # Two respiratory pauses
        p1 = int(len(filtered) * 0.3)
        p2 = int(len(filtered) * 0.7)
        pause_len = int(sr * 0.7)
        out_audio = np.concatenate([
            filtered[:p1],
            0.002 * np.random.randn(pause_len),
            filtered[p1:p2],
            0.002 * np.random.randn(pause_len),
            filtered[p2:]
        ])

    elif severity == "pause_hallucination":
        # Speech -> Extended 2.2s silence (respiratory gasp) -> Speech
        # Split spoken phrase into part 1 and part 2
        split_idx = int(len(data) * 0.55)
        part1 = data[:split_idx]
        part2 = data[split_idx:]
        pause_samples = int(sr * 2.2)
        # Quiet ambient room noise / breathing sound
        pause_sound = 0.0015 * np.random.randn(pause_samples)
        out_audio = np.concatenate([part1, pause_sound, part2])

    else:
        out_audio = data

    # Normalize safely
    max_val = np.max(np.abs(out_audio))
    if max_val > 0:
        out_audio = out_audio / max_val * 0.85
    out_int16 = (out_audio * 32767).astype(np.int16)
    wavfile.write(output_wav, sr, out_int16)
    print(f"Generated realistic speech sample: {output_wav} ({len(out_audio)/sr:.2f}s)")

if __name__ == "__main__":
    pass
