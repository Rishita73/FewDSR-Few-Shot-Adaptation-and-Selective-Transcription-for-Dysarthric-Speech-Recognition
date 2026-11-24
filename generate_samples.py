import os
import numpy as np
from scipy.io import wavfile

def generate_torgo_samples():
    sample_dir = os.path.join(os.path.dirname(__file__), "samples")
    os.makedirs(sample_dir, exist_ok=True)
    sr = 16000

    # Sample 1: Mild Dysarthria (slight articulation distortion, mostly continuous)
    # Target: "She had your dark suit in greasy wash water all year"
    t1 = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
    sig1 = 0.4 * np.sin(2 * np.pi * 180 * t1) * (0.6 + 0.4 * np.sin(2 * np.pi * 3.5 * t1))
    sig1 += 0.15 * np.sin(2 * np.pi * 380 * t1) + 0.05 * np.random.randn(len(t1))
    sig1 = np.clip(sig1, -0.9, 0.9)
    wavfile.write(os.path.join(sample_dir, "torgo_f03_mild.wav"), sr, (sig1 * 32767).astype(np.int16))

    # Sample 2: Moderate Dysarthria (intermittent pauses, consonant reduction)
    # Target: "Speech recognition helps individuals regain communication autonomy"
    t2 = np.linspace(0, 5.0, int(sr * 5.0), endpoint=False)
    sig2 = 0.45 * np.sin(2 * np.pi * 140 * t2) * (0.5 + 0.5 * np.sin(2 * np.pi * 2.0 * t2))
    # introduce a 0.8s pause at 2.0s
    sig2[int(2.0 * sr):int(2.8 * sr)] = 0.005 * np.random.randn(int(0.8 * sr))
    sig2 += 0.08 * np.random.randn(len(t2))
    sig2 = np.clip(sig2, -0.9, 0.9)
    wavfile.write(os.path.join(sample_dir, "torgo_m01_moderate.wav"), sr, (sig2 * 32767).astype(np.int16))

    # Sample 3: Severe Dysarthria (heavy vocal tremor, low pitch, irregular burst pauses)
    # Target: "Open the emergency front door immediately"
    t3 = np.linspace(0, 6.0, int(sr * 6.0), endpoint=False)
    sig3 = 0.5 * np.sin(2 * np.pi * 110 * t3) * (0.4 + 0.6 * np.sin(2 * np.pi * 1.2 * t3))
    # Pauses at 1.5s - 2.4s and 4.0s - 4.8s
    sig3[int(1.5 * sr):int(2.4 * sr)] = 0.004 * np.random.randn(int(0.9 * sr))
    sig3[int(4.0 * sr):int(4.8 * sr)] = 0.004 * np.random.randn(int(0.8 * sr))
    sig3 += 0.1 * np.random.randn(len(t3))
    sig3 = np.clip(sig3, -0.9, 0.9)
    wavfile.write(os.path.join(sample_dir, "torgo_m04_severe.wav"), sr, (sig3 * 32767).astype(np.int16))

    # Sample 4: Respiratory Pause Hallucination Trigger (speech -> 2.2s silence -> speech)
    # Target: "Please call doctor ... [breathing pause] ... at ten"
    t4 = np.linspace(0, 5.5, int(sr * 5.5), endpoint=False)
    sig4 = 0.4 * np.sin(2 * np.pi * 160 * t4)
    # Silence interval between 1.4s and 3.6s (2.2s silence where standard Whisper autoregressively hallucinates)
    sig4[int(1.4 * sr):int(3.6 * sr)] = 0.002 * np.random.randn(int(2.2 * sr))
    sig4[:int(1.4 * sr)] *= (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t4[:int(1.4 * sr)]))
    sig4[int(3.6 * sr):] *= (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t4[int(3.6 * sr):]))
    sig4 += 0.03 * np.random.randn(len(t4))
    sig4 = np.clip(sig4, -0.9, 0.9)
    wavfile.write(os.path.join(sample_dir, "torgo_pause_hallucination.wav"), sr, (sig4 * 32767).astype(np.int16))

    print(f"Generated 4 TORGO-style benchmark audio samples in: {sample_dir}")

if __name__ == "__main__":
    generate_torgo_samples()
