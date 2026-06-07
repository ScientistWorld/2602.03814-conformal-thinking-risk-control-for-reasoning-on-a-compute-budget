# Progress

## What Works

- Read the paper and implemented the core Conformal Thinking algorithm: upper-threshold false-positive control, parametric sigmoid lower-threshold false-negative control, Hoeffding UCB finite-sample correction, efficiency-loss candidate selection, and combined earliest-exit inference.
- Added a reproducible synthetic reasoning-trajectory dataset generator that provides fixed prompts, gold answers, stepwise predictions, confidence-like signals, and token counts.
- Added a baseline, reusable evaluator, shell scripts, scoring reference, and documentation.
- Local smoke test passed: `bash scripts/reproduce.sh` followed by `python validate.py --compare`.

## Results

Current smoke-test operating point (`epsilon = 0.32`) on `data/synthetic_reasoning.jsonl`:

- `upper_only`: accuracy 0.417, token fraction 0.665, token savings 0.335, false-positive risk 0.317, false-negative risk 0.000, risk excess 0.000.
- `conformal_thinking`: accuracy 0.317, token fraction 0.372, token savings 0.628, false-positive risk 0.131, false-negative risk 0.098, risk excess 0.000.

This supports `method_runs` locally. The submitted CPU job is intended to verify the same pipeline under the scheduler before claiming `core_claim`.

## Remaining

- Inspect the submitted job result and, if it matches the smoke test, update the milestone to `core_claim`.
- If budget remains, expand beyond the minimum by adding repeated split trials or additional synthetic difficulty mixtures.

## Issues

- The original paper's main numerical results are presented as curves in figures rather than scalar tables, so `reference.json` encodes the claimed operating constraints and comparison structure rather than copied curve coordinates.
- The full paper setup uses large reasoning LLMs and AIME/GPQA/DeepScaleR/MathVision trajectories. This reproduction uses fixed synthetic trajectories to keep the environment runnable without large model downloads or login-node inference.

## Deviations from Paper

- **Data/model scale**: The paper uses trajectories from Qwen3-8B, Qwen3-30B-A3B, DeepSeek-R1-Distill-Qwen-32B, and Qwen3-VL-8B on AIME, GPQA-Diamond, DeepScaleR, and MathVision. This reproduction substitutes a deterministic synthetic trajectory dataset with the same fields needed by the algorithm. The substitution avoids multi-GB model downloads and expensive LLM inference while preserving the paper's stopping-policy computation.
- **Signal set**: The paper evaluates confidence, EAT, token count, and a trained probe. This reproduction includes confidence-like, EAT-like, and token-fraction signals, but omits the learned probe because it requires hidden states from a large model trajectory corpus.
