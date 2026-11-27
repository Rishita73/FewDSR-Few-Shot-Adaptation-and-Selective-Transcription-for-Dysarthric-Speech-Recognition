# RUNBOOK: executing Part 3 for real

Part 3 code was written and unit-tested on SYNTHETIC fixture files only (`tests/fixtures_part3.py`). No real result exists until
someone with TORGO + torch runs Part 2 and then these steps. Stop at the first failure.

## 0. Preconditions
```bash
pip install -r requirements.txt
python -m unittest discover -s tests                         # all green
ls results/raw/*_baseline.jsonl results/raw/*_lora.jsonl     # REAL files from docs/RUNBOOK_PART2.md
python -m experiments.validate_raw results/raw               # VALID
```
Verify the severity map in `fewdsr_config.py` against the official TORGO documentation before reporting by-severity numbers.

## 1. Calibration, grounding, selective output (no model needed)
```bash
python -m experiments.run_calibration --raw results/raw --out results/calibration.json
```
Read the printed LOSO and per-speaker lines. Warnings in `results/calibration.json` (`protocols.*.params.*.warnings`) matter:
"temperature not fitted", "fitted T sits at the search bound", "only N insertions in validation", "abstain on all".
LOSO needs >= 2 speakers in a condition; with one speaker only the per-speaker protocol exists (the summary says so).

## 2. Silence / pause stress test (needs torch + model + manifest)
```bash
python -m experiments.run_silence_stress --manifest data/manifest.json --speakers F04 M01 --n 10
```
Builds digital silence, low noise and real utterances with a 2.2 s pause, with the VAD off and on. If the guarded hallucination rate is not lower than
the unguarded one, report that and analyse why (e.g. no-speech logit not informative, VAD already removes the silence).

## 3. INT8 vs FP32 on CPU (needs ctranslate2 + faster-whisper)
```bash
python -m experiments.run_edge --check
python -m experiments.run_edge --manifest data/manifest.json --speaker F04 --k 10 --n 30 --adapter artifacts/adapters/F04_K10
```
Writes `results/edge/edge.json` (RTF = median of 3 passes after warm-up, peak RSS, size on disk, WER on the same utterances, CPU string).
Likely problems: `ct2-transformers-converter` not on PATH (the python -m fallback is unverified); missing `tokenizer.json` in the merged directory
(save the fast tokenizer); faster-whisper version differences in `WhisperModel.transcribe` kwargs (adapt only `core/ct2_backend.py`).
INT8 has no raw logits: Stage 3/4 numbers always come from the FP32 raw files.

## 4. Summary, figures, report, app
```bash
python -m experiments.run_all --raw results/raw --out results         # add --headline baseline|lora_K20|... to change the headline condition
python -m experiments.validate_summary results/summary.json
python -m experiments.make_report                                      # results/FewDSR_Results_Chapter.docx
python -m streamlit run app.py                                         # Real tab needs torch and artifacts/adapters/*
grep -rnE "36\.4|62\.5|66\.7|150\.0|0\.284|0\.082" --include=*.py --include=*.md .   # only docs/INTEGRITY_NOTES.md may match
```
Headline condition defaults to the first available of K=10, 20, 5, 40, baseline: this is a presentation choice, not a tuned one. All conditions are in `summary.json → conditions`.
Never run `run_all --fixture` on real files, and never copy numbers from a fixture summary.

## 5. After the run, append to `docs/HANDOFF_PART3.md`
Library versions, hardware, the real results table, warnings seen, deviations, remaining risks.
