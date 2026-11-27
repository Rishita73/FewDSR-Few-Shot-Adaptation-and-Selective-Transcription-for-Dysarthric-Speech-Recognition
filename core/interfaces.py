"""Data contracts shared by ALL parts. Do not change field names without
updating docs/CONTRACTS.md and every test.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Sequence
import numpy as np


@dataclass
class TokenInfo:
    """One decoded unit (word-level after aggregation).

    topk_logits : the K largest pre-softmax logits at this decoding step,
                  sorted DESCENDING. topk_logits[0] is z(w), the chosen token's
                  logit under greedy decoding. Used for temperature scaling.
    null_logit  : logit of Whisper's <|nospeech|> token at the same step,
                  i.e. z(nospeech) in the synopsis formula.
    """
    word: str
    topk_logits: np.ndarray
    null_logit: float
    raw_conf: float = float("nan")      # softmax(z)[0] over topk (T = 1)
    calib_conf: float = float("nan")    # softmax(z / T)[0] (filled by Stage 3)
    grounded: Optional[bool] = None     # filled by Stage 3 (Delta >= gamma)

    @property
    def top_logit(self) -> float:
        return float(self.topk_logits[0])


@dataclass
class Transcription:
    tokens: List[TokenInfo]
    latency_s: float = 0.0
    audio_duration_s: float = 0.0
    backend: str = "unknown"
    is_simulated: bool = False
    # raw logit of <|nospeech|> at the <|startoftranscript|> position (OpenAI's definition); nan if unavailable
    first_step_null_logit: float = float("nan")

    @property
    def text(self) -> str:
        return " ".join(t.word for t in self.tokens)

    @property
    def rtf(self) -> float:
        return self.latency_s / self.audio_duration_s if self.audio_duration_s > 0 else float("nan")


class ASRBackend(ABC):
    """Anything that turns audio into Transcription. Implementations:
       - SimulatedBackend (Part 1, core/model_manager.py)  : demo only
       - WhisperBackend   (Part 2, core/whisper_backend.py): real HF Whisper (+LoRA)
       - CT2Backend       (Part 3, core/ct2_backend.py)    : INT8 CPU
    """
    name: str = "abstract"
    is_simulated: bool = False

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sr: int) -> Transcription: ...
