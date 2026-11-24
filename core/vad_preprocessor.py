import numpy as np

class PausePreservingVAD:
    """
    Stage 1: Pause-Preserving Audio Preprocessor
    Designed specifically for dysarthric speech where irregular breathing
    intervals and vocal fatigue cause standard VAD to prematurely truncate speech.
    
    Uses an extended hangover window (default: 600ms) to bridge atypical pauses.
    """
    def __init__(self, sample_rate=16000, frame_ms=30, energy_thresh_percentile=35, hangover_ms=600):
        self.sample_rate = sample_rate
        self.frame_len = int(sample_rate * (frame_ms / 1000.0))
        self.hangover_frames = int(hangover_ms / frame_ms)
        self.energy_thresh_percentile = energy_thresh_percentile
        self.hangover_ms = hangover_ms

    def process(self, audio: np.ndarray, custom_hangover_ms=None):
        if custom_hangover_ms is not None:
            hangover_frames = int(custom_hangover_ms / 30)
        else:
            hangover_frames = self.hangover_frames

        # Normalize audio to [-1, 1]
        if np.max(np.abs(audio)) > 0:
            audio_norm = audio / np.max(np.abs(audio))
        else:
            audio_norm = audio

        num_frames = len(audio_norm) // self.frame_len
        if num_frames == 0:
            return {"speech_mask": np.ones_like(audio, dtype=bool), "segments": []}

        # Compute Short-Time Frame Energy (dB)
        energies = []
        for i in range(num_frames):
            frame = audio_norm[i * self.frame_len : (i + 1) * self.frame_len]
            rms = np.sqrt(np.mean(frame**2) + 1e-12)
            energies.append(rms)
        energies = np.array(energies)

        # Adaptive threshold based on percentile
        threshold = np.percentile(energies, self.energy_thresh_percentile)
        raw_speech_flags = energies > threshold

        # Apply Extended Hangover Window to preserve breathing pauses
        smoothed_flags = np.copy(raw_speech_flags)
        hangover_counter = 0

        for i in range(len(smoothed_flags)):
            if raw_speech_flags[i]:
                hangover_counter = hangover_frames
            else:
                if hangover_counter > 0:
                    smoothed_flags[i] = True
                    hangover_counter -= 1

        # Expand frame flags to full audio sample mask
        speech_mask = np.repeat(smoothed_flags, self.frame_len)
        if len(speech_mask) < len(audio):
            pad_len = len(audio) - len(speech_mask)
            speech_mask = np.pad(speech_mask, (0, pad_len), constant_values=smoothed_flags[-1])

        # Find detected pauses that were preserved
        pauses = []
        in_pause = False
        pause_start = 0
        time_axis = np.linspace(0, len(audio) / self.sample_rate, len(audio))

        for idx, is_raw_speech in enumerate(raw_speech_flags):
            t_sec = idx * 0.03
            if not is_raw_speech and smoothed_flags[idx]:
                if not in_pause:
                    in_pause = True
                    pause_start = t_sec
            else:
                if in_pause:
                    in_pause = False
                    pause_end = t_sec
                    if pause_end - pause_start >= 0.15:
                        pauses.append({"start": round(pause_start, 2), "end": round(pause_end, 2), "duration_sec": round(pause_end - pause_start, 2)})

        return {
            "energies": energies,
            "threshold": float(threshold),
            "speech_mask": speech_mask,
            "preserved_pauses": pauses,
            "raw_active_percent": float(np.mean(raw_speech_flags) * 100),
            "preserved_active_percent": float(np.mean(smoothed_flags) * 100)
        }
