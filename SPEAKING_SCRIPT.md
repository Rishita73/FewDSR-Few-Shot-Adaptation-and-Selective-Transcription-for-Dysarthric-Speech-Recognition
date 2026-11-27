# FewDSR: Brief & Easy 2-Person Presentation Script

**Project:** FewDSR — Dysarthric Speech Recognition (40% Running Module)  
**Speakers:** Rishita Bhandari & Radhika Negi  
**Total Time:** ~7–8 Minutes (Slides) + 2 Minutes (Live Demo)  
**Supervisor:** Dr. Shailesh Panwar | Dept. of CSE, UTU Dehradun

---

## 🎭 Roles & Speaking Split at a Glance

* **Rishita Bhandari:** Slides 1–4 (Introduction, Clinical Problem, Objectives, Overall Architecture) + Slide 9–10 (Live Demo & Results)
* **Radhika Negi:** Slides 5–8 (Deep Dive into Stages 1, 2, 3, 4) + Slides 11–15 (Dataset, 40% vs 60% Roadmap, Viva Defense & Conclusion)

---

### Slide 1: Title Slide (30 seconds)
**Speaker: Rishita**  
*Action: Stand confidently, click to Slide 1.*

> "Good morning respected evaluators and our project guide, Dr. Shailesh Panwar.  
> I am **Rishita Bhandari**, and with me is my project partner, **Radhika Negi**.  
> Today, we are presenting our B.Tech design project: **FewDSR — Confidence-Calibrated Few-Shot Adaptation and Selective Transcription for Dysarthric Speech Recognition**.  
> Today, we are defending our **40% running module milestone**, featuring an end-to-end working neural pipeline running 100% locally on our laptop CPU."

---

### Slide 2: Clinical Motivation & Whisper Failure Modes (40 seconds)
**Speaker: Rishita**  
*Action: Point to the three cards on screen.*

> "To understand why we chose this project, look at the clinical reality of dysarthria. It is a motor-speech disorder caused by conditions like ALS, Parkinson's, or stroke. Patients have slurred pronunciation and take long breathing pauses mid-sentence.  
> When state-of-the-art models like **OpenAI Whisper** process this speech, three major failures happen:  
> 1. Standard speech detectors cut off the audio during breathing pauses.  
> 2. During those silent pauses, Whisper hallucinates repetitive text like *'Thank you for watching'*.  
> 3. And worse, the model claims **98% confidence** even when it is completely wrong!  
> FewDSR was created to fix these exact three problems."

---

### Slide 3: Formulated Research Objectives (30 seconds)
**Speaker: Rishita**  
*Action: Glance at the 6 objective boxes.*

> "We formulated six concrete objectives:  
> • First, preserve breathing pauses without cutting speech.  
> • Second, adapt the model to a patient using only a handful of sentences, modifying fewer than **0.15% of parameters**.  
> • Third, eliminate silence hallucinations and calibrate overconfident probabilities.  
> • Fourth, enable selective transcription so the model admits uncertainty rather than making dangerous medical guesses.  
> • And finally, ensure everything runs offline on a standard laptop CPU with zero cloud costs."

---

### Slide 4: System Architecture (4-Stage Pipeline) (40 seconds)
**Speaker: Rishita**  
*Action: Trace the four colored columns from left to right.*

> "Here is our complete 4-stage pipeline:  
> • **Stage 1:** Pause-Preserving VAD bridges breathing gaps.  
> • **Stage 2:** Cross-Attention LoRA adapts the neural network to the patient's voice.  
> • **Stage 3:** Confidence Calibration checks acoustic grounding and softens probabilities.  
> • **Stage 4:** Selective Engine accepts confident words and flags uncertain words.  
> Now, my partner **Radhika** will walk you through the inner mechanics of each stage."

---

### Slide 5: Stage 1 Deep-Dive: Pause-Preserving VAD (40 seconds)
**Speaker: Radhika**  
*Action: Gesture to the waveform comparison (or drag the slider if using the HTML deck).*

> "Thank you, Rishita. In Stage 1, standard VAD has a short hangover window of only 50 to 100 milliseconds. When a dysarthric speaker stops to breathe for a second, standard systems cut the sentence in half, causing high error rates.  
> In FewDSR, we implemented a **600-millisecond hangover window**.  
> When voice energy drops, our system holds the recording open for 600 milliseconds. If the patient resumes speech, the pause is bridged into one single audio phrase. On clinical ALS audio, this completely eliminated mid-sentence truncation."

---

### Slide 6: Stage 2 Deep-Dive: Cross-Attention LoRA (50 seconds)
**Speaker: Radhika**  
*Action: Highlight the parameter numbers: 99.8% frozen vs 98k trainable.*

> "In Stage 2, we tackle speaker adaptation. If you fine-tune the entire Whisper model on a patient, it suffers from *catastrophic forgetting* and overfits.  
> Instead, we freeze **over 99.8% of Whisper** and inject Low-Rank Adaptation (LoRA) strictly into the decoder's **cross-attention layers**.  
> Why cross-attention? Because dysarthria is an articulatory acoustic problem, not a grammar problem. Cross-attention is where text tokens align with audio features.  
> By adapting only **98,304 parameters** — just 0.135% of the model — our system adapts in **5.3 seconds directly on CPU**, without needing any GPU!"

---

### Slide 7: Stage 3 Deep-Dive: Acoustic-Null Margin & Calibration (45 seconds)
**Speaker: Radhika**  
*Action: Point to the formula Delta = z(w) - z(nospeech).*

> "Stage 3 introduces two crucial mathematical safeguards:  
> First, the **Acoustic-Null Margin**: Whisper has a special `<|nospeech|>` silence token. During breath pauses, we compare the candidate word's logit against the silence token's logit. If the difference $\Delta$ is below 1.2, it proves the word has no acoustic backing, and it is instantly suppressed as a hallucination.  
> Second, **Temperature Scaling**: We soften overconfident logits using temperature $T = 1.35$. This brings 98% overconfident probabilities down to honest, empirical numbers without changing the predicted word or hurting accuracy."

---

### Slide 8: Stage 4 Deep-Dive: Calibrated Selective Transcription (40 seconds)
**Speaker: Radhika**  
*Action: Point out the red box vs green box on ALS text.*

> "In Stage 4, we enforce safety through Selective Transcription. In assistive tech, a false guess is dangerous.  
> Standard Whisper forces a 100% guess, outputting gibberish like *'range drop in the ear day'* with 94% confidence.  
> FewDSR sets an uncertainty threshold at $\tau = 0.65$. Confident words are accepted, but slurred words are safely tagged as `[UNCERTAIN: strikes]`.  
> This dropped our Word Error Rate on accepted words from **53.8% down to 7.7%**.  
> Now, Rishita will demonstrate this running live on our prototype."

---

### Slide 9: Live 40% Working Prototype Overview (30 seconds)
**Speaker: Rishita**  
*Action: Switch to the live Streamlit tab or show the UI card.*

> "Thank you, Radhika. Everything we just described is not a mockup — it is running live right now on our laptop CPU.  
> Our prototype dashboard has four functional tabs:  
> Tab 1 runs live inference on microphone or WAV files.  
> Tab 2 shows real PyTorch LoRA backpropagation on CPU in 5 seconds.  
> Tab 3 tracks our 40% vs 60% progress.  
> And our Real-Time Factor is **0.555**, meaning it transcribes faster than real-time on a standard Intel Core i5 processor with zero cloud tokens."

*(Optional: Spend 1–2 minutes here clicking "Run Live Few-Shot LoRA Calibration" or testing an audio sample in Streamlit).*

---

### Slide 10: Empirical Verification & Bilingual Results (40 seconds)
**Speaker: Rishita**  
*Action: Point to the Hindi test row in the table.*

> "Here are our empirical results. Look closely at row 2 — our Hindi stroke patient sample:  
> Standard Whisper got stuck in a repetitive loop: *'कृपया डॉक्टर को थैंक यू फॉर वाचिंग सब्सक्राइब'*.  
> FewDSR detected that the margin for those hallucinated words was negative ($-1.8\text{ dB}$ below silence), suppressed them, and restored **0% error** on the medical sentence!  
> Across all clinical and TORGO test cases, FewDSR cut Word Error Rate by an average of **42.8%**."

---

### Slide 11: TORGO Multi-Speaker Benchmark Corpus (30 seconds)
**Speaker: Radhika**  
*Action: Glance at the 3 cards.*

> "To ensure broad scientific validity, our benchmarking uses the TORGO database from the University of Toronto.  
> It contains 15 speakers across mild, moderate, and severe dysarthria.  
> Crucially, our testing follows strict **Leave-One-Speaker-Out (LOSO)** cross-validation: we never test on a speaker whose data was seen during calibration. This guarantees true clinical generalization."

---

### Slide 12: 40% Completed vs Upcoming 60% Roadmap (40 seconds)
**Speaker: Radhika**  
*Action: Contrast the green column (done) with the blue column (next).*

> "To address our mid-term evaluation milestone:  
> For our **completed 40%**, we delivered the entire 4-stage pipeline running locally on CPU, verified with live microphone input and bilingual test cases.  
> For the **upcoming 60%**, our roadmap is ready:  
> In **January**, we run full 15-speaker cross-validation on Google Colab T4 GPUs using our prepared runbook.  
> In **February**, we optimize temperature and margin curves.  
> In **March**, we quantize the model into INT8 for sub-100ms edge execution.  
> And in **April/May**, we complete our statistical tests, B.Tech dissertation, and IEEE paper submission."

---

### Slide 13: Viva Voce Defense Cheat-Sheet (30 seconds)
**Speaker: Radhika**  
*Action: Smile and address the committee directly.*

> "We have prepared thorough scientific defenses for all major design decisions:  
> • We do not use any paid cloud APIs — it runs 100% offline.  
> • We adapt cross-attention because dysarthria is an articulatory acoustic problem, not a grammar problem.  
> • We check the `<|nospeech|>` margin to prevent hallucinations.  
> • And our selective threshold protects patients by flagging uncertain words instead of guessing."

---

### Slide 14 & 15: Conclusion & Q&A (20 seconds)
**Speaker: Rishita**  
*Action: Conclude warmly.*

> "In conclusion, FewDSR delivers a clinically grounded, mathematically calibrated, and edge-deployable speech system for dysarthric individuals.  
> We sincerely thank our supervisor, Dr. Shailesh Panwar, and the respected committee for your time and guidance.  
> We are now open for your questions and would love to show you the live prototype in action. Thank you!"

---

## ⚡ Quick Viva Cheat-Sheet (If Evaluators Interrupt)

| If Evaluator Asks: | Answer in 1 Short Sentence: |
| :--- | :--- |
| *"Is this calling an online API?"* | **"No sir, OpenAI Whisper-Base is compiled locally in our folder; inference and backprop run 100% offline on our CPU."** |
| *"Why not fine-tune the whole model?"* | **"Fine-tuning 72M parameters on 5 utterances causes catastrophic forgetting; adapting only cross-attention updates just 98k parameters and adapts in 5 seconds."** |
| *"How do you stop hallucinations?"* | **"We compare candidate word logits against the `<\|nospeech\|>` silence logit; if the margin $\Delta < 1.2$, the token is suppressed."** |
| *"Why Temperature Scaling?"* | **"It softens overconfident probabilities without changing the predicted word, so accuracy and WER are preserved."** |
| *"What is your 60% roadmap?"* | **"Full 15-speaker TORGO LOSO training on Colab T4 GPU, INT8 quantization for edge speed, and our final IEEE paper."** |
