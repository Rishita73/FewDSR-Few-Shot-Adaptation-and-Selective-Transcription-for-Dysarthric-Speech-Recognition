# RUNBOOK: executing Part 2 on real hardware (Colab T4 or any machine with torch)

The Part 2 code was written and unit-tested WITHOUT torch/network. Everything that touches the real model must be
run once by a human/agent with internet + TORGO. Do these steps in order; stop at the first failure and fix it.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests                    # 48 tests, 5 skipped (slow)           expect OK
FEWDSR_SLOW=1 python -m unittest tests.test_part2_slow -v   # real Whisper + PEFT checks   expect OK (downloads ~1 GB)
python -m experiments.check_lora                        # prints 24 modules + MEASURED trainable %   (expect 294,912 = ~0.12 %)
python -m experiments.check_backend                     # tone/silence/noise smoke + record validation; READ the silence output
python -m experiments.prepare_data --torgo-root /path/to/TORGO --out data/manifest.json
# smoke (2-3 minutes) into a SEPARATE dir:
python -m experiments.run_baseline --speakers F01 --limit 3 --out results/smoke
python -m experiments.run_adapt    --speakers F01 --budgets 5 --epochs 2 --limit 3 --out results/smoke --adapters artifacts/smoke
python -m experiments.validate_raw results/smoke
# real runs (>=1 mild + >=1 severe speaker; see severity map in fewdsr_config.py, VERIFY it):
python -m experiments.run_baseline --speakers F04 M01 --max-test 100
python -m experiments.run_adapt    --speakers F04 M01 --budgets 5 10 20 40 --max-test 100
python -m experiments.validate_raw results/raw
```
Likely first-run problems and what to do:
| Symptom | Cause / fix |
|---|---|
| `TypeError ... output_logits` | transformers too old: `pip install -U transformers>=4.40` |
| `RuntimeError: LoRA wrapped N modules` | PEFT/regex mismatch: print `model.named_modules()`, fix ONLY `lora_target_regex` in fewdsr_config.py |
| `Could not find a <|nospeech|>` | tokenizer naming: print `tok.convert_ids_to_tokens(range(50355,50366))`, extend `resolve_nospeech_id` |
| `n logits != generated tokens` / shape errors in `steps_from_logits` | HF version returns logits differently: inspect `out.logits` type/len, adapt ONLY `WhisperBackend.transcribe` |
| `validate_raw`: null_logit not finite | scores instead of raw logits were used: confirm `output_logits=True` is honoured |
| val WER never improves, best_epoch 0 | lr too high/low or K too small: try `--lr 3e-4`, more epochs; report honestly, do not hide |
| CUDA OOM | `batch_size=2` in `RealLoraAdapter` or run on CPU |
| Missing prompts / 0 utterances | TORGO layout differs: adapt only `core.data.build_manifest` + its test |
