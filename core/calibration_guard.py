from typing import List, Sequence
import numpy as np
from scipy.optimize import minimize_scalar

from core.interfaces import TokenInfo
from core.metrics import expected_calibration_error


def softmax_top_prob(topk_logits: np.ndarray, T: float) -> np.ndarray:
    """p of the first (largest) logit. topk_logits: [N, K] or [K]."""
    z = np.atleast_2d(np.asarray(topk_logits, dtype=float)) / max(T, 1e-6)
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e[:, 0] / e.sum(axis=1)


class CalibrationGuard:
    """
    Stage 3: Post-Hoc Temperature Calibration & Acoustic-Null Margin Grounding
    Formulated in FewDSR Section 5 (Stage 3).
    
    1. Acoustic-Null Grounding Margin:
       Delta = z(w) - z(nospeech)
       If Delta < gamma: token lacks acoustic grounding and is flagged as a pause hallucination.
       
    2. Temperature Scaling:
       P_calib = softmax(z / T)
       Corrects the overconfidence common in autoregressive decoders on dysarthric audio.
    """
    def __init__(self, temperature: float = 1.35, gamma: float = 1.2):
        self.temperature = float(temperature)
        self.gamma = float(gamma)

    # ---- temperature ----
    def fit_temperature(self, topk_logits: np.ndarray, correct: Sequence[int],
                        bounds=(0.05, 10.0)) -> float:
        """Learn T on VALIDATION data only (never on the test set)."""
        Z = np.asarray(topk_logits, dtype=float)
        y = np.asarray(correct, dtype=float)
        if Z.ndim != 2 or len(Z) != len(y) or len(y) == 0:
            raise ValueError("topk_logits must be [N,K] with N == len(correct) > 0")
        eps = 1e-12

        def nll(T):
            p = np.clip(softmax_top_prob(Z, T), eps, 1 - eps)
            return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

        self.temperature = float(minimize_scalar(nll, bounds=bounds, method="bounded").x)
        return self.temperature

    def calibrated_confidence(self, topk_logits: np.ndarray, T: float | None = None) -> np.ndarray:
        return softmax_top_prob(topk_logits, self.temperature if T is None else T)

    def calibrate_logits(self, logits: np.ndarray, temp: float = None) -> np.ndarray:
        T = temp if temp is not None else self.temperature
        scaled = logits / max(T, 0.01)
        exp_logits = np.exp(scaled - np.max(scaled, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
        return probs

    # ---- acoustic-null grounding ----
    def margin(self, top_logit: float, null_logit: float) -> float:
        return float(top_logit - null_logit)

    def is_grounded(self, top_logit: float, null_logit: float, gamma: float | None = None) -> bool:
        return self.margin(top_logit, null_logit) >= (self.gamma if gamma is None else gamma)

    def check_acoustic_null_margin(self, top_logit: float, nospeech_logit: float, custom_gamma=None):
        g = custom_gamma if custom_gamma is not None else self.gamma
        delta = top_logit - nospeech_logit
        is_grounded = delta >= g
        return {
            "delta": round(float(delta), 3),
            "gamma_threshold": round(float(g), 3),
            "is_grounded": bool(is_grounded),
            "status": "Acoustically Grounded" if is_grounded else "HALT: Non-Speech Hallucination Suppressed"
        }

    def fit_gamma(self, deltas: Sequence[float], is_speech: Sequence[int],
                  min_speech_recall: float = 0.95) -> float:
        """Pick the LARGEST gamma that still keeps >= min_speech_recall of tokens
        that were genuinely spoken (is_speech==1), so hallucinated tokens
        (is_speech==0) are rejected as aggressively as possible."""
        d = np.asarray(deltas, dtype=float)
        s = np.asarray(is_speech, dtype=int)
        if (s == 1).sum() == 0:
            raise ValueError("need at least one genuinely-spoken token")
        self.gamma = float(np.quantile(d[s == 1], 1.0 - min_speech_recall))
        return self.gamma

    # ---- apply to a token list (Stage 3 entry point) ----
    def apply(self, tokens: List[TokenInfo]) -> List[TokenInfo]:
        for t in tokens:
            t.raw_conf = float(softmax_top_prob(t.topk_logits, 1.0)[0])
            t.calib_conf = float(softmax_top_prob(t.topk_logits, self.temperature)[0])
            t.grounded = self.is_grounded(t.top_logit, t.null_logit)
        return tokens

    def compute_ece(self, confidences, ground_truth_correctness, n_bins=10):
        return expected_calibration_error(confidences, ground_truth_correctness, n_bins)

