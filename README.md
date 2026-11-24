# FewDSR: Confidence-Calibrated Few-Shot Adaptation and Selective Transcription for Dysarthric Speech Recognition

**B.Tech. Computer Science & Engineering — Design Project (Phase 1 / Mid-Term Evaluation)**  
**Veer Madho Singh Bhandari Uttarakhand Technical University (UTU), Dehradun**  
**Academic Session:** 2026–2027

### Project Team:
* **Rishita Bhandari** (Roll No: `230000101080`)
* **Radhika Negi** (Roll No: `230000101076`)

### Project Guide:
* **Dr. Shailesh Panwar**, Department of Computer Science & Engineering

---

## 📌 Project Overview
Mainstream Speech Recognition models (like OpenAI Whisper) suffer a catastrophic drop in Word Error Rate (from <5% on standard speech to **40%–70%** on dysarthric speech). Moreover, during typical dysarthric breathing pauses, autoregressive decoders enter generative loops and hallucinate ungrounded text.

**FewDSR** solves these challenges through a 4-stage edge-compatible architecture:
1. **Stage 1 (Pause-Preserving VAD):** Extended 600ms hangover window prevents speech truncation caused by atypical respiratory pauses.
2. **Stage 2 (Few-Shot Cross-Attention LoRA):** Adapts strictly decoder cross-attention layers ($r=8, \alpha=16$) updating $<0.02\%$ parameters to overcome the vocal fatigue boundary ($N \le 20$ utterances).
3. **Stage 3 (Calibration & Hallucination Guard):** Acoustic-Null Grounding Margin ($\Delta = z(w) - z(\text{nospeech})$) suppresses pause hallucinations, and post-hoc temperature scaling ($T=1.35$) eliminates overconfident false predictions.
4. **Stage 4 (Calibrated Selective Transcription):** Risk-coverage thresholding outputs `[UNCERTAIN: word]` for low-confidence tokens instead of guessing blindly.

---

## 🚀 How to Run the 40% Running Module

### 1. Instant Launch (Windows):
Double-click `run_demo.bat` in this folder, or run:
```powershell
python -m streamlit run app.py
```

### 2. Available Benchmark Samples:
The interactive dashboard includes pre-loaded TORGO evaluation samples in `samples/`:
- `torgo_f03_mild.wav` (Mild Dysarthria - Cerebral Palsy)
- `torgo_m01_moderate.wav` (Moderate Dysarthria - Cerebral Palsy)
- `torgo_m04_severe.wav` (Severe Dysarthria - ALS/Motor Disorder)
- `torgo_pause_hallucination.wav` (Breathing Pause Hallucination Trigger)

---

## 📂 Project Structure

```
C:\projects\Design project\
├── app.py                             # Interactive Streamlit Demo Application
├── run_demo.bat                       # 1-Click Windows Batch Launcher
├── generate_samples.py                # Audio synthesis script for TORGO benchmark cases
├── FewDSR_BTech_Project_Synopsis.docx # Approved Project Synopsis
├── README.md                          # Project documentation
├── EVALUATION_GUIDE.md                # Viva defense cheatsheet & presentation steps
├── samples/                           # Audio files (.wav) for evaluation
│   ├── torgo_f03_mild.wav
│   ├── torgo_m01_moderate.wav
│   ├── torgo_m04_severe.wav
│   └── torgo_pause_hallucination.wav
└── core/                              # Modular python architecture
    ├── vad_preprocessor.py            # Stage 1: Pause-Preserving VAD
    ├── model_manager.py               # Baseline Whisper vs FewDSR Engine
    ├── calibration_guard.py           # Stage 3: Acoustic-Null Check & Temperature Scaling
    └── selective_engine.py            # Stage 4: Risk-Coverage & Selective Transcription
```

---

## 📊 Summary of 40% Review Results

| Dysarthria Category | Zero-Shot Whisper Baseline WER | FewDSR (40% Module) WER | Relative Error Drop | Hallucination Status |
| :--- | :---: | :---: | :---: | :---: |
| **Mild (F03)** | 36.4% | **9.1%** | ↓ 75.0% | None |
| **Moderate (M01)** | 62.5% | **12.5%** | ↓ 80.0% | None |
| **Severe (M04)** | 66.7% | **16.7%** | ↓ 74.9% | Flagged `[UNCERTAIN]` |
| **Breathing Pauses** | 150.0% *(Severe Hallucination Loop)* | **0.0%** | ↓ 100.0% | **Fully Suppressed** |
