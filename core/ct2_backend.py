"""INT8 CPU backend via CTranslate2 / faster-whisper (Part 3, Objective 6).

!!! Written WITHOUT network/torch/ctranslate2 in the authoring sandbox: py_compile only. Run
`python -m experiments.run_edge --check` on the target machine first. !!!

WHAT IS AND IS NOT AVAILABLE ON THIS PATH (stated, not hidden)
* Available : transcript text, latency, audio duration  -> WER and RTF.
* NOT available: raw top-K logits and the <|nospeech|> logit. faster-whisper's public API exposes
  text and (optionally) per-word probabilities, not raw logits. We do NOT synthesise them. Every
  TokenInfo returned here carries NaN logits and `Transcription.first_step_null_logit` is NaN.
  Therefore Stage 3 (temperature, grounding) and Stage 4 (selective output) cannot be run on this
  backend; calibration/hallucination results come from the FP32 Hugging Face path and the INT8 path
  is evaluated for WER, RTF, memory and size only. `CT2Backend.provides_logits` is False so callers can check.
"""
from __future__ import annotations
import os, subprocess, sys, time
from typing import List, Optional
import numpy as np

from fewdsr_config import CFG
from core.interfaces import ASRBackend, TokenInfo, Transcription
from core.vad_preprocessor import PausePreservingVAD


def merge_lora_to_hf(adapter_dir: Optional[str], out_dir: str, base: str = CFG.base_model) -> str:
    """Merge a LoRA adapter into the base weights and save a plain HF checkpoint (+ processor)."""
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    model = WhisperForConditionalGeneration.from_pretrained(base)
    if adapter_dir:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_dir).merge_and_unload()
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    WhisperProcessor.from_pretrained(base).save_pretrained(out_dir)
    return out_dir


def convert_to_ct2(hf_dir: str, ct2_dir: str, quantization: str = "int8") -> str:
    """Runs `ct2-transformers-converter`. Needs ctranslate2 installed (provides the CLI)."""
    import shutil
    exe = shutil.which("ct2-transformers-converter")
    head = [exe] if exe else [sys.executable, "-m", "ctranslate2.converters.transformers"]   # fallback is UNVERIFIED
    cmd = head + ["--model", hf_dir, "--output_dir", ct2_dir, "--quantization", quantization, "--force",
                  "--copy_files", "tokenizer.json", "preprocessor_config.json"]
    subprocess.run(cmd, check=True)
    return ct2_dir


def dir_size_bytes(path: str) -> int:
    return sum(os.path.getsize(os.path.join(r, f)) for r, _d, fs in os.walk(path) for f in fs)


class CT2Backend(ASRBackend):
    is_simulated = False
    provides_logits = False

    def __init__(self, ct2_dir: str, device: str = "cpu", compute_type: str = "int8", use_vad: bool = True,
                 vad_pad_s: float = 0.2, cpu_threads: int = 0, language: str = "en"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(ct2_dir, device=device, compute_type=compute_type, cpu_threads=cpu_threads)
        self.language = language
        self.use_vad = use_vad
        self.vad = PausePreservingVAD(CFG.sample_rate, CFG.vad_frame_ms, CFG.vad_hangover_ms)
        self.vad_pad = int(vad_pad_s * CFG.sample_rate)
        self.name = f"ct2-{compute_type}"

    def _prep(self, audio: np.ndarray, sr: int) -> np.ndarray:        # identical trimming to WhisperBackend._prep
        audio = np.asarray(audio, dtype=np.float32)
        if sr != CFG.sample_rate:
            from core.audio_io import resample
            audio = resample(audio, sr, CFG.sample_rate)
        if self.use_vad and len(audio) > 0:
            res = self.vad.process(audio)
            if res["segments"]:
                s = max(0, int(res["segments"][0][0] * CFG.sample_rate) - self.vad_pad)
                e = min(len(audio), int(res["segments"][-1][1] * CFG.sample_rate) + self.vad_pad)
                audio = audio[s:e]
        return audio

    def transcribe(self, audio: np.ndarray, sr: int) -> Transcription:
        dur = len(audio) / sr if sr else 0.0
        t0 = time.perf_counter()
        x = self._prep(audio, sr)
        if len(x) < 400:
            return Transcription([], time.perf_counter() - t0, dur, self.name, False)
        segments, _info = self.model.transcribe(x, language=self.language, task="transcribe", beam_size=1,
                                                temperature=0.0, condition_on_previous_text=False,
                                                without_timestamps=True, vad_filter=False)
        text = " ".join(s.text.strip() for s in segments).strip()          # generator: decoding happens here
        lat = time.perf_counter() - t0
        nan = np.full(1, np.nan)
        toks: List[TokenInfo] = [TokenInfo(w, nan.copy(), float("nan")) for w in text.split()]
        return Transcription(toks, lat, dur, self.name, False, float("nan"))
