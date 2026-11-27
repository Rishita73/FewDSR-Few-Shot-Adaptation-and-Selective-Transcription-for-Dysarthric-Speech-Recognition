# HANDOFF → Agent for PART 2 (Real Whisper + LoRA engine)

## 0. Starting state (verify first, 2 minutes)
```bash
pip install -r requirements.txt
python -m unittest discover -s tests          # expect: Ran 25 tests ... OK
```
If this is not green, STOP and fix the environment (do not edit Part 1 code to make it pass).
Read, in order: `docs/INTEGRITY_NOTES.md`, `docs/CONTRACTS.md`, `core/interfaces.py`, `fewdsr_config.py`.
Part 1 could not run torch/transformers/peft (no network in its sandbox): **everything in this Part is
unverified code you must run for real.**

## 1. Prerequisites you must obtain
- TORGO dataset (free for research, University of Toronto, registration required). Expected layout:
  `<TORGO>/<SPK>/Session<N>/wav_headMic/*.wav` and `.../prompts/*.txt`. Speakers F01 F03 F04 M01 M02 M03 M04 M05
  (+ FC/MC controls). If the layout differs, adapt ONLY `core/data.py:build_manifest` and extend its test; keep the
  `Utt` dataclass unchanged.
- `openai/whisper-small` weights via Hugging Face. Run on GPU if available (Colab T4 ok), CPU is fine for K<=40.
- Do NOT commit audio or weights (see `.gitignore`).

## 2. Tasks (do in this order; one commit per task)

### 2.1 `core/audio_io.py`
`load_audio(path, sr=CFG.sample_rate) -> np.float32 mono in [-1,1]` (soundfile + resample via librosa/torchaudio).
Test with a generated wav (extend `generate_samples.py` style; no TORGO needed).

### 2.2 `core/whisper_backend.py` – class `WhisperBackend(ASRBackend)`
- `__init__(model_name=CFG.base_model, adapter_dir=None, device=None, topk=20)`. Load `WhisperForConditionalGeneration`
  + `WhisperProcessor`; if `adapter_dir` given: `PeftModel.from_pretrained`. Language `"en"`, task `"transcribe"`,
  greedy (num_beams=1), `model.generation_config.forced_decoder_ids=None`, pass `language/task` to `generate`.
- `transcribe(audio, sr)`: features via processor (log-mel 80), then
  `generate(..., return_dict_in_generate=True, output_logits=True)`.
  **Use `output_logits` (RAW), NOT `output_scores`**: HF logits processors set special tokens (incl. the no-speech
  token) to -inf in `scores`, which would make z(nospeech) = -inf and silently break the grounding margin.
- no-speech token id: `tok.convert_tokens_to_ids("<|nospeech|>")`; if it equals `unk_token_id` try `"<|nocaptions|>"`;
  `assert` it is valid. For every generated step take (a) top-K raw logits sorted descending (K=`topk`), (b) raw logit at
  the no-speech id. Also store `first_step_null_logit` (step 0), which is the quantity OpenAI's own no-speech
  probability uses; put it on `Transcription` as an extra attribute `first_step_null_logit`.
- Word aggregation in `core/word_align.py`: group BPE tokens into words (token text beginning with a space starts a new
  word; skip special tokens). Per CONTRACTS: for each word use the subtoken with the lowest raw top-probability for
  `topk_logits`/`null_logit`. **Important:** `topk_logits[0]` must be the logit of the token actually emitted. Under greedy decoding
  that is the argmax; add a unit test (mock tensors, no model needed) asserting this and the word grouping, including
  a multi-subtoken word and a punctuation token.
- Return `Transcription(backend="whisper[-lora]", is_simulated=False, latency_s, audio_duration_s)`.
- Empty/near-silent audio must return zero tokens, not crash (test it with real model on 3 s of zeros: record
  what it outputs; this is the hallucination case Part 3 studies. Do not "fix" it here).
- Optionally trim audio with `PausePreservingVAD.trim()` behind a flag `use_vad=True` (default True, 600 ms from CFG).
  Keep a pad (e.g. 0.2 s) so Whisper gets context.

### 2.3 `core/lora.py`
- `build_lora_model(base)` using `peft.LoraConfig(r=CFG.lora_r, lora_alpha=CFG.lora_alpha, lora_dropout=CFG.lora_dropout,
  target_modules=CFG.lora_target_regex, bias="none")`. `target_modules` as a regex string is matched with full-match
  semantics by PEFT: verify by listing `[n for n,_ in model.named_modules() if "lora_A" in n]` and asserting that
  **exactly 24 modules** (12 layers × {q,v}) are wrapped, all under `decoder.layers.*.encoder_attn`. If PEFT reports
  other counts, fix the regex in `fewdsr_config.py` (single source of truth) and keep the existing regex unit test green.
- `count_trainable(model)` → `(trainable, total, pct)`. **Record the measured pct** (expected ≈0.12 %, NOT "<0.02 %" as the
  synopsis claims) in your completion report.
- `train_lora(model, processor, utts, val_utts, epochs, lr=1e-3, batch_size=4, seed=CFG.seed, device)`:
  frozen base, `use_cache=False`, no SpecAugment, labels = tokenizer(prefix tokens + normalized text + eos) with pad → -100,
  decoder_input_ids = shift-right of labels (use the model's own shift in `forward(labels=...)`). Training and inference prefix
  tokens (`<|startoftranscript|><|en|><|transcribe|><|notimestamps|>`) must be identical. Compute val WER (via
  `core/metrics.py`) each epoch; keep the best-val-WER adapter weights (early stopping, patience 3). K=0 → skip training.
  Loop is manual (no HF Trainer) to stay deterministic and light. Set `torch.manual_seed(CFG.seed)`.
- Save adapter: `artifacts/adapters/{speaker}_K{k}/` (`save_pretrained`). Loading it back into a fresh base must reproduce
  identical transcripts for 3 val utterances (write this as a slow test guarded by `FEWDSR_SLOW=1`).

### 2.4 Experiment scripts (`experiments/`; add `__init__.py`)
- `prepare_data.py --torgo-root PATH --out data/manifest.json` → `build_manifest` + `save_manifest`; print counts per
  speaker, and the number of UNIQUE prompts per speaker (K=40 needs ≥ 40 + n_val unique prompts; if a speaker has
  fewer, record it and cap budgets for that speaker explicitly, do not fake).
- `run_baseline.py --speakers ... ` : zero-shot `WhisperBackend` on each speaker's TEST (and VAL) split from
  `nested_budget_splits`; write `results/raw/{spk}_K0_baseline.jsonl` (schema in CONTRACTS) and print corpus WER, CER,
  insertion rate per speaker/severity using `core.metrics.corpus_wer`.
- `run_adapt.py --speakers ... --budgets 5 10 20 40` : for each K train LoRA on `split.calibration`, validate on
  `split.validation`, evaluate on `split.test` with the SAME test set used by the baseline (guaranteed by
  `nested_budget_splits`); write `results/raw/{spk}_K{k}_lora.jsonl` + `artifacts/adapters/...`. Also write val-split raw
  records (`"split":"val"`).
- All scripts: `--limit N` for smoke runs, deterministic seeds, resume-safe (skip existing outputs unless `--force`).

## 3. Acceptance checklist (all must be true)
- [ ] `python -m unittest discover -s tests` green (Part 1 tests untouched + your new `tests/test_part2_*.py`)
- [ ] 24 LoRA-wrapped modules, all cross-attention q/v; measured trainable % reported
- [ ] Zero-shot baseline and K ∈ {5,10,20,40} run on **≥ 2 real TORGO speakers** (one mild, one severe) with real numbers
- [ ] Raw jsonl files follow the CONTRACTS schema exactly (a validator script `experiments/validate_raw.py` that checks
      keys, K=20 descending logits, `topk_logits[0]` ≥ others, finite `null_logit`; run it on all outputs)
- [ ] Test sets identical across K for a given speaker (assert in `run_adapt.py`)
- [ ] No test-set data used for training/early-stopping/threshold choice

## 4. Do NOT
- Do not touch `fewdsr_config.py` values other than `lora_target_regex` (and only if the 24-module check demands it).
- Do not rename/remove anything in Part 1 files. Do not edit `app.py`, `docs/HANDOFF_PART3.md` (except appending your
  report to *this* file), or the report generators.
- Do not apply temperature scaling, gamma, tau or selective logic in Part 2 outputs: store RAW logits only.
- Do not invent or pre-fill any result. If a run cannot be performed (no GPU/data), say so in your report.

## 5. Completion report (append below when done)
Include: library versions (`pip freeze | grep -E "torch|transformers|peft"`), measured trainable %, per-speaker
baseline & K-scaling WER table (real), runtime per run, deviations from this spec, known issues.

---
## COMPLETION REPORT - Part 2 (authoring agent, sandbox WITHOUT torch/network/TORGO)

**Status: code-complete and logic-tested; NOT yet executed against the real model or real TORGO.**
Therefore Part 2 is only fully "done" after someone runs `docs/RUNBOOK_PART2.md` and appends real numbers below.

### Delivered
| File | Purpose | Verified how |
|---|---|---|
| `core/audio_io.py` | wav -> mono float32 16 kHz (soundfile, scipy fallback) | unit tests (stereo/int16/44.1k) |
| `core/word_align.py` | raw logits -> top-K rows (emitted token first) -> word-level `TokenInfo` (min-confidence subtoken, punctuation ignored, byte-split UTF-8 safe) | unit tests incl. Devanagari split |
| `core/whisper_backend.py` | real HF Whisper, `output_logits=True`, no-speech id resolution, sot-position null logit, VAD trim+pad | **py_compile only** -> `tests/test_part2_slow.py`, `experiments/check_backend.py` |
| `core/lora.py` | cross-attn LoRA with 24-module assertion, `count_trainable`, label encoding (prefix masked), training loop with val-WER early stopping where epoch 0 = zero-shot candidate | `encode_labels` unit-tested; rest **py_compile only** |
| `experiments/common.py` | feasible budgets, `speaker_splits` (identical val/test across K), record writer (atomic), summaries | unit + flow tests |
| `experiments/prepare_data.py`, `run_baseline.py`, `run_adapt.py` | CLI pipeline, resume-safe, `--limit` smoke mode | end-to-end flow tests with fake backend/adapter |
| `experiments/validate_raw.py` | CONTRACTS validator incl. cross-condition val/test identity | tamper tests |
| `experiments/check_lora.py`, `check_backend.py` | real-machine sanity checks | not run |
| `docs/RUNBOOK_PART2.md` | exact commands + troubleshooting | - |
Test suite: 48 tests (43 run, 5 slow skipped), all green.

### Measured numbers
NONE. No WER, trainable-% (predicted 294,912 params = 0.122 %, to be *measured*), or RTF were measured. Append them here after the runbook.

### Deviations / decisions
1. `topk_logits[0]` = emitted token's logit (not necessarily the max); contract amended in CONTRACTS.md.
2. Training audio goes through the same VAD trim/pad as inference (`backend._prep`).
3. Labels mask the 3 forced prefix tokens; only text + `<|endoftext|>` are trained.
4. Budgets infeasible for a speaker are skipped explicitly (never padded/faked).
5. `Transcription.first_step_null_logit` added (additive change to a Part 1 file).
6. `--max-test` (default 100) deterministically subsamples test prompts (TORGO has thousands of single-word utterances).

### Known risks (unverified)
HF `generate` return structure for `output_logits` varies by version (tail-slicing used to be robust); PEFT regex full-match behaviour;
lr=1e-3 may need tuning; `PeftModel.generate` with Whisper kwargs; speed of per-epoch validation decode on CPU.
