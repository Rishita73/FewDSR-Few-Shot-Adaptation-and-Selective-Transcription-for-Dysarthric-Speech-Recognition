"""Glue: Backend -> Stage 3 (calibration/grounding) -> Stage 4 (selective).
The UI and the experiment scripts BOTH call run_pipeline(); no logic lives in app.py."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np

from core.interfaces import Transcription
from core.calibration_guard import CalibrationGuard
from core.selective_engine import SelectiveTranscriptionEngine


@dataclass
class PipelineResult:
    transcription: Transcription
    selective: dict
    temperature: float
    gamma: float
    tau: float


def run_pipeline(transcription: Transcription, temperature: float, gamma: float, tau: float) -> PipelineResult:
    guard = CalibrationGuard(temperature=temperature, gamma=gamma)
    guard.apply(transcription.tokens)
    sel = SelectiveTranscriptionEngine(tau).process(transcription.tokens)
    return PipelineResult(transcription, sel, temperature, gamma, tau)
