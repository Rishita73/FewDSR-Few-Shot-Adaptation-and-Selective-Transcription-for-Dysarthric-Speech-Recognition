# FewDSR: Evaluator Presentation Script & Live Demo Guide

**Veer Madho Singh Bhandari Uttarakhand Technical University (UTU), Dehradun**  
**Design Project Mid-Term Evaluation (40% Running Module)**  
**Students:** Rishita Bhandari (`230000101080`) & Radhika Negi (`230000101076`)  
**Guide:** Dr. Shailesh Panwar

---

## 🎯 How to Present Your Live 40% Working Prototype (3-Minute Script)

### Step 1: Explain What Is Running Live (20 seconds)
> "Respected Evaluators, our project is **FewDSR: Confidence-Calibrated Few-Shot Adaptation and Selective Transcription for Dysarthric Speech Recognition**.  
> Today we are demonstrating our **live 40% running module** powered by **OpenAI Whisper-Base running locally on CPU** with our custom **PyTorch Cross-Attention LoRA adapters**, **600ms Pause-Preserving VAD**, **Acoustic-Null Hallucination Guard**, and **Selective Transcription**."

### Step 2: Live ASR & Calibration Demo — Tab 1 (60 seconds)
1. Pick **"🇮🇳 Hindi Assistive Case"** or **"🏥 Real Clinical Recording (Spastic Dysarthria in ALS)"** (or click **"🎤 Record Live Microphone"** and speak slowly with a 2-second pause!).
2. Show the **Stage 1 VAD Waveform**: *"Standard VAD cuts off dysarthric breathing pauses. Our 600ms hangover window preserves the breathing interval."*
3. Show the **Side-by-Side Comparison**:
   - **Left:** Uncalibrated Whisper Baseline.
   - **Right:** FewDSR Pipeline with real token-level `[UNCERTAIN: word]` badges.
4. Expand **"🔍 Inspect Real Token Logits"**:
   - Point out the **real logits** $z(w)$ and `<|nospeech|>` logits extracted directly from Whisper's decoder!
   - Show how $\Delta = z(w) - z(\text{nospeech})$ catches ungrounded silence hallucinations and how Temperature Scaling ($T = 1.35$) calibrates overconfident probabilities.

### Step 3: Live Few-Shot Cross-Attention LoRA Training — Tab 2 (45 seconds)
1. Switch to **Tab 2: "🧠 2. Live Few-Shot LoRA Training (Stage 2)"**.
2. Point out the live PyTorch parameter count: **>99.7% of Whisper is frozen**, and only the **decoder cross-attention `q_proj` & `v_proj` LoRA matrices** are trainable.
3. Click **"⚡ Run Live Few-Shot LoRA Calibration"**:
   - Evaluators will watch the **real PyTorch Cross-Entropy Loss curve drop live** in ~3 seconds on CPU!

### Step 4: What We Built (40%) vs What We Will Do Next (60%) — Tab 3 (30 seconds)
1. Switch to **Tab 3: "🗺️ 3. Project Status: 40% Done vs Next 60%"**.
2. Walk evaluators through:
   - **Completed (40%):** All 4 pipeline stages working end-to-end on CPU, live LoRA adapter, logit extraction, Hindi & clinical test cases.
   - **Next 60%:** Full 15-speaker TORGO Leave-One-Speaker-Out (LOSO) evaluation, validation-learned $T^*$ & $\gamma^*$ optimization, CTranslate2 INT8 quantization, and final IEEE paper + thesis.

---

## 💡 Top 5 Evaluator Viva Questions & Quick Answers

1. **Q: Is this using an external cloud API or token like OpenAI / Google API?**
   - **Answer:** *"No sir/ma'am. It does not use any cloud API or paid tokens. We have downloaded and compiled OpenAI Whisper-Base locally onto our laptop. The inference and PyTorch backpropagation run 100% locally and offline on CPU."*

2. **Q: Why LoRA on Cross-Attention specifically, instead of full fine-tuning?**
   - **Answer:** *"Full fine-tuning on 1–5 dysarthric utterances causes catastrophic forgetting and degrades general language modeling. Furthermore, dysarthria alters the mapping between acoustic features and phonetic targets, which happens at the encoder-decoder cross-attention interface ($Q$ from decoder, $K, V$ from audio encoder). LoRA adds low-rank matrices to $Q$ and $V$, adapting only 0.135% (98k) parameters in ~3 seconds on CPU."*

3. **Q: What is the Acoustic-Null Margin check?**
   - **Answer:** *"Standard Whisper hallucinates fluent phrases during prolonged dysarthric pauses. We extract the logit for the special token `<|nospeech|>` alongside candidate token $w$. If the margin $\Delta = z(w) - z(\text{nospeech})$ is below our safety threshold $\gamma$, the token is suppressed as ungrounded silence hallucination."*

4. **Q: Why do you need Temperature Scaling?**
   - **Answer:** *"Modern neural networks produce overconfident probabilities (softmax $P \approx 0.99$ even when wrong). By applying temperature parameter $T > 1.0$ ($P = \text{softmax}(z/T)$), we soften the logits, bringing confidence in line with true empirical accuracy without changing token rank."*

5. **Q: What is Selective Transcription?**
   - **Answer:** *"In medical and assistive contexts, an incorrect word can lead to dangerous actions (e.g. wrong medicine dosage). Instead of forcing an ungrounded guess, our system outputs `[UNCERTAIN: word]` when calibrated confidence is below $\tau = 0.65$, preserving safety while maintaining high coverage."*

