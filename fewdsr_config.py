"""Single source of truth for every hyper-parameter named in the synopsis.

RULE FOR ALL AGENTS: never hard-code these numbers elsewhere. Import them:
    from fewdsr_config import CFG
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class FewDSRConfig:
    # Audio / Stage 1 (synopsis s5, Stage 1)
    sample_rate: int = 16000
    vad_frame_ms: int = 30
    vad_hangover_ms: int = 600
    n_mels: int = 80

    # Stage 2: LoRA on decoder cross-attention q/v (synopsis s5, Stage 2)
    base_model: str = "openai/whisper-small"
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    # HF Whisper names the decoder cross-attention block "encoder_attn".
    # The regex deliberately EXCLUDES decoder self_attn and the encoder.
    lora_target_regex: str = r".*decoder\.layers\.\d+\.encoder_attn\.(q_proj|v_proj)"
    budgets: Tuple[int, ...] = (0, 5, 10, 20, 40)   # K utterances (Objective 2)

    # Stage 3
    temperature_init: float = 1.0      # real value is LEARNED on validation data
    gamma_init: float = 1.2            # grounding margin; tuned on validation data
    ece_bins: int = 10

    # Stage 4
    tau_init: float = 0.70             # selective threshold; tuned for target risk
    target_risk: float = 0.10

    # Reproducibility
    seed: int = 1234

    # TORGO speaker metadata. !!! VERIFY against the official TORGO documentation
    # before publishing; the original prototype labelled these inconsistently.
    torgo_severity: Dict[str, str] = field(default_factory=lambda: {
        "F01": "severe", "F03": "mild", "F04": "mild",
        "M01": "severe", "M02": "severe", "M03": "mild",
        "M04": "severe", "M05": "moderate",
    })


CFG = FewDSRConfig()
