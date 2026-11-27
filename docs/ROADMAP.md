# FewDSR – three-part completion roadmap

| Part | Goal | Synopsis objectives | Exit criterion |
|---|---|---|---|
| **1 (DONE)** | Honest, tested foundation: metrics, data/LOSO splits, real VAD, real calibration/grounding/selective code, contracts, honest UI | infrastructure for 1-5 | 25 unit tests green; UI labelled SIMULATED; handoff written |
| **2** | Real engine: Whisper-small backend with raw-logit extraction, word aggregation, LoRA cross-attn adaptation, TORGO data prep, zero-shot baseline + K-shot runs producing `results/raw/*.jsonl` | 1 (baseline), 2 (few-shot LoRA) | baseline + LoRA run end-to-end on >=2 TORGO speakers; trainable-param % measured; tests green |
| **3 (CODE DONE, NOT EXECUTED ON REAL DATA)** | Science + edge + delivery: calibration/gamma/tau fitted on validation, ECE & risk-coverage & hallucination evaluation on all speakers (LOSO), INT8 CTranslate2 + RTF, statistics, app wired to real results, regenerated report | 3, 4, 5, 6 + stats | `results/summary.json` real; app shows only real numbers; report regenerated; all tests green |

Hand-off protocol: each agent finishes by (a) running all tests, (b) appending a "Completion report" section to its
own HANDOFF file (what was done, deviations, measured numbers, known issues), (c) NOT starting the next part.
