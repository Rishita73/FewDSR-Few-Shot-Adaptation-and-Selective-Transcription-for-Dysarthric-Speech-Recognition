# Integrity notes (read before touching reports or claims)

Found while auditing the 40 % prototype against the synopsis (Part 1):

1. **All reported results were hard-coded.** `core/model_manager.py` (old) contained literal
   WER/CER values (36.4→9.1, 62.5→12.5, 66.7→16.7, 150→0, 85.7→0), literal "logits", and literal
   "baseline outputs". No Whisper model, LoRA training, or TORGO audio was ever executed.
   `app.py` tabs 2 and 3 (benchmark table, scaling curve, reliability diagram, "ECE 0.284→0.082") were also
   typed-in constants. These numbers are **not measurements** and must not appear in the thesis, report or
   viva as results. (They were moved to `data/simulated_demo.json`, flagged simulated, and removed from tabs 2/3.)
2. **Sample audio is synthetic** (sine tones from `generate_samples.py`). It is not TORGO and not a clinical
   recording. The old UI claimed "Authentic Clinical Archive … John E. Pierce SLP Archive" and "Real Clinical
   Recording"; these claims were removed.
3. **Synopsis arithmetic error:** LoRA r=8 on q,v of 12 decoder cross-attention blocks of Whisper-small =
   12 x 2 x (768x8 + 8x768) = **294,912 params ≈ 0.12 %** of ~241.7 M, not "<0.02 %". Part 2 must measure the real
   count and the synopsis/report text must be corrected to the measured value.
4. **Synopsis technical note:** Whisper's `<|nospeech|>` logit is only meaningful at the first decoding step
   (HF suppresses special tokens at later steps). Part 2 must use raw logits (`output_logits=True`) and document
   exactly how per-step z(nospeech) is obtained.
5. Existing `.docx` reports and `generate_report.py` embed the fabricated numbers. Part 3 regenerates them from
   `results/summary.json`. Do not edit them by hand and do not distribute them.
6. TORGO speaker severity labels in the old UI were inconsistent. `fewdsr_config.py:torgo_severity` is now the
   single source and is marked **VERIFY** against the official TORGO documentation.
