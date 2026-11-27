# Contracts shared by all agents (do not break)

## Ground rules
- Python 3.10+. Run tests with `python -m unittest discover -s tests` (no pytest needed). **All tests must pass
  before you hand off.** Never delete or weaken an existing test; add new ones.
- Hyper-parameters live ONLY in `fewdsr_config.py` (`from fewdsr_config import CFG`).
- Metrics live ONLY in `core/metrics.py`. Do not re-implement WER/ECE elsewhere.
- Never fit T, gamma or tau on test data. Validation split only (`core/data.py:SpeakerSplit.validation`).
- Never print or display a number in UI/report that was not read from a file in `results/`.
- WER/CER are stored as FRACTIONS (0.364), formatted as % only at display time.
- Anything simulated must set `is_simulated=True` and show a SIMULATED banner.
- Randomness: always seed from `CFG.seed`.

## File ownership (avoid merge conflicts)
| Path | Owner | Others may |
|---|---|---|
| fewdsr_config.py, core/interfaces.py, core/metrics.py, core/data.py, core/calibration_guard.py, core/selective_engine.py, core/vad_preprocessor.py, core/pipeline.py | Part 1 | add functions; **never rename/remove** existing ones |
| core/whisper_backend.py, core/lora.py, core/audio_io.py, core/word_align.py, experiments/prepare_data.py, experiments/run_baseline.py, experiments/run_adapt.py | Part 2 | read only |
| core/ct2_backend.py, experiments/run_calibration.py, experiments/run_all.py, experiments/make_report.py, app.py (final), docs/final | Part 3 | read only |
| tests/test_part1.py, tests/test_pipeline.py | Part 1 | read only (add new files `test_partN_*.py`) |

## Data contracts
`TokenInfo` / `Transcription` / `ASRBackend`: see `core/interfaces.py`.
Word-level rule (Part 2 must follow): one `TokenInfo` per WORD. For a multi-subtoken word use the subtoken with the
LOWEST raw top-probability: its `topk_logits` (K=20, raw un-suppressed logits) and its `null_logit`.

**Amendment (Part 2):** `topk_logits[0]` is ALWAYS the logit of the token actually emitted; entries `1..19` are the largest logits of the
OTHER tokens, descending. Normally `[0]` is also the maximum, but if a HF logits-processor forced a token that is not the raw argmax,
`topk_logits[0] < topk_logits[1]` (validator counts these; calibration math still treats index 0 as the chosen token).
`first_step_null_logit` = raw z(<|nospeech|>) at the `<|startoftranscript|>` position (OpenAI definition), may be `null` if unavailable.
`null_logit` per word = raw z(<|nospeech|>) at the carrying subtoken's decoding step (after the forced language/task prefix).

**Split rule (Part 2/3):** ALWAYS build splits with `experiments.common.speaker_splits(utts, spk, n_val, max_test)`; never call
`nested_budget_splits` directly. It uses the full feasible budget list so val/test are identical for every K and for the baseline.
Use the same `--max-test`/`--n-val` for baseline and adaptation. `validate_raw` fails if test/val sets differ across conditions.
Budgets infeasible for a speaker (fewer unique prompts than K + n_val + 1) are skipped and must be reported as missing, never imputed.

### Raw per-utterance record (Part 2 writes, Part 3 reads)
`results/raw/{speaker}_K{k}_{condition}.jsonl`, one JSON object per TEST utterance:
```json
{"speaker":"F01","k":10,"condition":"baseline|lora","split":"test","wav":"...","ref":"...","hyp":"...",
 "audio_s":3.41,"latency_s":1.2,"first_step_null_logit":2.1,
 "words":[{"word":"please","topk_logits":[9.1,6.2,...20 floats],"null_logit":1.3}]}
```
Same schema for `split":"val"` (needed to fit T/gamma/tau). `condition=baseline` is K=0 zero-shot.

### Summary (Part 3 writes, app reads): `results/summary.json`
```json
{"generated":"ISO8601","config":{...CFG as dict...},
 "baseline":{"by_severity":{"mild":{"wer":..,"cer":..,"ins_rate":..,"n_words":..}, ...}, "by_speaker":{...}},
 "scaling":{"K":[0,5,10,20,40],"wer_mean":[..],"wer_ci95":[[lo,hi],..],"per_speaker":{...}},
 "calibration":{"T":{"F01":..},"ece_before":..,"ece_after":..,"reliability":{"before":[bins],"after":[bins]}},
 "hallucination":{"insertion_rate_before":..,"insertion_rate_after":..,"gamma":..},
 "selective":{"tau":..,"risk_coverage":{"coverage":[..],"risk":[..]},"aurc":..,"coverage_at_target_risk":..},
 "edge":{"fp32_rtf":..,"int8_rtf":..,"int8_wer":..,"cpu":"..."},
 "stats":{"wilcoxon_p_k0_vs_k10":..}}
```
