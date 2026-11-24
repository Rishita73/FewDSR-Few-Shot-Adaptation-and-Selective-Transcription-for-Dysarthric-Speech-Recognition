import numpy as np

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
    def __init__(self, temperature=1.35, gamma=1.2):
        self.temperature = temperature
        self.gamma = gamma

    def calibrate_logits(self, logits: np.ndarray, temp: float = None) -> np.ndarray:
        T = temp if temp is not None else self.temperature
        scaled = logits / max(T, 0.01)
        # Softmax with numerical stability
        exp_logits = np.exp(scaled - np.max(scaled, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
        return probs

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

    def compute_ece(self, confidences, ground_truth_correctness, n_bins=5):
        """
        Computes Expected Calibration Error (ECE) across prediction bins.
        """
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        total_samples = len(confidences)
        bin_stats = []

        for i in range(n_bins):
            b_low, b_high = bin_boundaries[i], bin_boundaries[i+1]
            in_bin = (confidences >= b_low) & (confidences < b_high) if i < n_bins - 1 else (confidences >= b_low) & (confidences <= b_high)
            bin_size = np.sum(in_bin)
            
            if bin_size > 0:
                bin_acc = np.mean(np.array(ground_truth_correctness)[in_bin])
                bin_conf = np.mean(np.array(confidences)[in_bin])
                diff = abs(bin_acc - bin_conf)
                ece += (bin_size / total_samples) * diff
                bin_stats.append({"bin": f"{b_low:.1f}-{b_high:.1f}", "acc": round(bin_acc, 3), "conf": round(bin_conf, 3), "count": int(bin_size)})
            else:
                bin_stats.append({"bin": f"{b_low:.1f}-{b_high:.1f}", "acc": 0.0, "conf": 0.0, "count": 0})

        return round(float(ece), 4), bin_stats
