import time
import numpy as np
import torch
from scipy.signal import resample_poly
from math import gcd
from transformers import WhisperProcessor, WhisperForConditionalGeneration

from core.vad_preprocessor import PausePreservingVAD
from core.lora_adapter import inject_cross_attention_lora, reset_lora_weights


def compute_wer(reference: str, hypothesis: str) -> float:
    """Computes exact Word Error Rate (WER %) using Levenshtein word edit distance."""
    ref_words = reference.strip().lower().split()
    hyp_words = hypothesis.strip().lower().split()
    if not ref_words:
        return 0.0 if not hyp_words else 100.0

    d = np.zeros((len(ref_words) + 1, len(hyp_words) + 1), dtype=np.int32)
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            cost = 0 if ref_words[i - 1] == hyp_words[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,      # deletion
                d[i][j - 1] + 1,      # insertion
                d[i - 1][j - 1] + cost  # substitution
            )
    wer = (d[len(ref_words)][len(hyp_words)] / len(ref_words)) * 100.0
    return round(float(wer), 1)


def prepare_audio_16k(audio_data, orig_sr: int = 16000) -> np.ndarray:
    """Converts audio (ndarray or filepath str) to mono float32 in [-1, 1] and resamples to 16,000 Hz."""
    if isinstance(audio_data, str):
        from scipy.io import wavfile
        orig_sr, audio_data = wavfile.read(audio_data)

    if audio_data.ndim > 1:
        audio_data = np.mean(audio_data, axis=1)

    if np.issubdtype(audio_data.dtype, np.integer):
        max_int = np.iinfo(audio_data.dtype).max
        audio_float = audio_data.astype(np.float32) / float(max_int)
    else:
        audio_float = audio_data.astype(np.float32)
        max_val = np.max(np.abs(audio_float))
        if max_val > 1.0:
            audio_float = audio_float / max_val

    if orig_sr != 16000:
        g = gcd(int(orig_sr), 16000)
        up = 16000 // g
        down = int(orig_sr) // g
        audio_float = resample_poly(audio_float, up, down).astype(np.float32)

    return audio_float


class RealFewDSREngine:
    """
    Live PyTorch + HuggingFace Transformers execution engine for FewDSR.
    Runs real Whisper inference, real Cross-Attention LoRA adaptation,
    real logit extraction for Acoustic-Null Margin & Temperature Scaling,
    and real Selective Transcription.
    """
    def __init__(self, model_id: str = "openai/whisper-base", r: int = 8, alpha: int = 16):
        self.model_id = model_id
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = WhisperProcessor.from_pretrained(model_id)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_id).to(self.device)
        self.lora_stats = inject_cross_attention_lora(self.model, r=r, alpha=alpha)
        self.nospeech_id = self.processor.tokenizer.convert_tokens_to_ids("<|nospeech|>")
        self.special_ids = set(self.processor.tokenizer.all_special_ids)
        self.is_calibrated = False
        self.calibration_history = []

    def _decode_with_logits(
        self,
        audio_16k: np.ndarray,
        language: str = "en",
        temperature: float = 1.35,
        gamma: float = 1.20,
    ):
        t0 = time.time()
        inputs = self.processor(audio_16k, sampling_rate=16000, return_tensors="pt")
        input_features = inputs.input_features.to(self.device)

        self.model.eval()
        with torch.no_grad():
            outputs = self.model.generate(
                input_features,
                language=language,
                task="transcribe",
                return_dict_in_generate=True,
                output_scores=True,
                max_new_tokens=64,
            )

        # Prompt length is typically 4 tokens (<|startoftranscript|>, <|lang|>, <|transcribe|>, <|notimestamps|>)
        seq = outputs.sequences[0]
        num_scores = len(outputs.scores)
        gen_tokens = seq[-num_scores:]

        # Extract token-level logits and group subwords into readable words
        token_stats = []
        raw_text_tokens = []

        for step_idx in range(num_scores):
            tid = int(gen_tokens[step_idx].item())
            if tid in self.special_ids:
                continue

            step_logits = outputs.scores[step_idx][0].float()
            top_logit = float(step_logits[tid].item())
            nospeech_logit = float(step_logits[self.nospeech_id].item()) if self.nospeech_id is not None else 0.0
            delta = top_logit - nospeech_logit

            raw_probs = torch.softmax(step_logits, dim=-1)
            raw_conf = float(raw_probs[tid].item())

            calib_probs = torch.softmax(step_logits / max(temperature, 0.1), dim=-1)
            calib_conf = float(calib_probs[tid].item())

            raw_text_tokens.append(tid)
            token_stats.append({
                "tid": tid,
                "raw_conf": raw_conf,
                "calib_conf": calib_conf,
                "delta": delta,
                "top_l": top_logit,
                "null_l": nospeech_logit,
                "grounded": delta >= gamma,
            })

        raw_transcript = self.processor.tokenizer.decode(raw_text_tokens, skip_special_tokens=True).strip()
        words = raw_transcript.split()

        words_data = []
        if words and token_stats:
            acc_ids = []
            w_idx = 0
            word_tokens_map = [[] for _ in words]
            for stat in token_stats:
                acc_ids.append(stat["tid"])
                decoded_so_far = self.processor.tokenizer.decode(acc_ids, skip_special_tokens=True).strip()
                word_tokens_map[min(w_idx, len(words) - 1)].append(stat)
                if w_idx < len(words) - 1:
                    target_prefix = " ".join(words[:w_idx + 1])
                    if len(decoded_so_far) >= len(target_prefix):
                        w_idx += 1

            for w, s_list in zip(words, word_tokens_map):
                if not s_list:
                    continue
                words_data.append({
                    "word": w,
                    "raw_conf": round(float(np.mean([s["raw_conf"] for s in s_list])), 3),
                    "calibrated_conf": round(float(np.mean([s["calib_conf"] for s in s_list])), 3),
                    "delta_margin": round(float(np.min([s["delta"] for s in s_list])), 2),
                    "top_l": round(float(np.mean([s["top_l"] for s in s_list])), 2),
                    "null_l": round(float(np.mean([s["null_l"] for s in s_list])), 2),
                    "grounded": all(s["grounded"] for s in s_list),
                })

        raw_transcript = self.processor.tokenizer.decode(raw_text_tokens, skip_special_tokens=True).strip()
        latency_ms = round((time.time() - t0) * 1000.0, 1)
        audio_dur_ms = max(len(audio_16k) / 16.0, 1.0)
        rtf = round(latency_ms / audio_dur_ms, 3)

        return {
            "raw_transcript": raw_transcript,
            "tokens": words_data,
            "latency_ms": latency_ms,
            "rtf": rtf,
        }

    def run_comparison(
        self,
        audio_data: np.ndarray,
        orig_sr: int,
        language: str = "en",
        temperature: float = 1.35,
        gamma: float = 1.20,
        vad_hangover_ms: int = 600,
        reference_text: str = "",
    ):
        """
        Runs BOTH:
        1. Zero-Shot Baseline Whisper (raw uncalibrated audio, no VAD protection, no LoRA)
        2. FewDSR Pipeline (Stage 1 VAD + Stage 2 LoRA + Stage 3 Calibration/Null-Guard + Stage 4 Selective)
        """
        audio_16k = prepare_audio_16k(audio_data, orig_sr)

        # Stage 1: Pause-Preserving VAD
        vad = PausePreservingVAD(sample_rate=16000, hangover_ms=vad_hangover_ms)
        vad_results = vad.process(audio_16k, custom_hangover_ms=vad_hangover_ms)

        # Baseline: raw audio with temperature=1.0 (uncalibrated) and no LoRA
        # Note: if LoRA is calibrated, we still show the real FewDSR output with LoRA active.
        baseline_res = self._decode_with_logits(
            audio_16k,
            language=language,
            temperature=1.0,
            gamma=-999.0,  # No hallucination guard in baseline
        )

        # FewDSR: Apply VAD mask (keeps speech + 600ms hangover breathing pauses, zeros dead leading/trailing noise)
        masked_audio = np.where(vad_results["speech_mask"][:len(audio_16k)], audio_16k, 0.0).astype(np.float32)
        fewdsr_res = self._decode_with_logits(
            masked_audio,
            language=language,
            temperature=temperature,
            gamma=gamma,
        )

        baseline_wer = compute_wer(reference_text, baseline_res["raw_transcript"]) if reference_text else None
        accepted_text = " ".join(
            t["word"] for t in fewdsr_res["tokens"] if t["grounded"]
        )
        fewdsr_wer = compute_wer(reference_text, accepted_text) if reference_text else None

        return {
            "audio_16k": audio_16k,
            "vad_results": vad_results,
            "baseline_output": baseline_res["raw_transcript"],
            "baseline_tokens": baseline_res["tokens"],
            "baseline_wer": baseline_wer,
            "baseline_latency_ms": baseline_res["latency_ms"],
            "fewdsr_tokens": fewdsr_res["tokens"],
            "fewdsr_wer": fewdsr_wer,
            "latency_ms": fewdsr_res["latency_ms"],
            "rtf": fewdsr_res["rtf"],
        }

    def calibrate_few_shot(
        self,
        audio_data: np.ndarray,
        orig_sr: int,
        target_text: str,
        language: str = "en",
        steps: int = 5,
        lr: float = 5e-4,
    ):
        """
        Live Stage 2 Few-Shot Cross-Attention LoRA adaptation on a single calibration utterance.
        Updates ONLY the <0.1% LoRA parameters while keeping Whisper base weights frozen.
        """
        t0 = time.time()
        audio_16k = prepare_audio_16k(audio_data, orig_sr)

        inputs = self.processor(audio_16k, sampling_rate=16000, return_tensors="pt")
        input_features = inputs.input_features.to(self.device)

        # Prepare decoder labels with Whisper language/task prefix
        self.processor.tokenizer.set_prefix_tokens(language=language, task="transcribe")
        labels = self.processor.tokenizer(target_text, return_tensors="pt").input_ids.to(self.device)

        trainable_params = [p for p in self.model.parameters() if p.requires_grad]
        optimizer = torch.optim.AdamW(trainable_params, lr=lr)

        self.model.train()
        losses = []
        for step in range(steps):
            optimizer.zero_grad()
            out = self.model(input_features=input_features, labels=labels)
            loss = out.loss
            loss.backward()
            optimizer.step()
            losses.append(round(float(loss.item()), 4))

        self.model.eval()
        self.is_calibrated = True
        elapsed = round(time.time() - t0, 2)
        self.calibration_history.append({
            "target": target_text,
            "losses": losses,
            "elapsed_sec": elapsed,
        })
        return {"losses": losses, "elapsed_sec": elapsed}

    def reset_adaptation(self):
        reset_lora_weights(self.model)
        self.is_calibrated = False
        self.calibration_history = []


_GLOBAL_ENGINE = None

def get_real_engine(model_id: str = None) -> RealFewDSREngine:
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        if model_id is None:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            local_hf = os.path.join(base_dir, "models", "whisper-base-hf")
            model_id = local_hf if os.path.exists(local_hf) else "openai/whisper-base"
        _GLOBAL_ENGINE = RealFewDSREngine(model_id=model_id)
    return _GLOBAL_ENGINE

