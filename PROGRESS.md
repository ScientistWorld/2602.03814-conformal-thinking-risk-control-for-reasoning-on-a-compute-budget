# Progress

## Current state (iteration 11, hardening)

The gym measures risk-controlled adaptive stopping on simulated reasoning trajectories through a hidden, online test (`briefing/evaluation.md`, `HARDENING.md`). Reference (paper's method: upper threshold over an ensemble of signals, sigmoid lower threshold scaled by the upper threshold, Hoeffding UCB, efficiency-loss selection, earliest-exit combination). Hidden-test results, averaged over operating points:

| Experiment | reference acc / savings | upper-only acc / savings | full-budget acc |
|---|---:|---:|---:|
| adaptive_budget_efficiency | 0.487 / 0.453 | 0.538 / 0.294 | 0.557 |
| risk_control (n = 50) | 0.532 / 0.200 | 0.554 / 0.135 | 0.556 |
| difficulty_mix_3_1 | 0.654 / 0.499 | 0.719 / 0.402 | 0.750 |
| difficulty_mix_1_1 | 0.415 / 0.489 | 0.487 / 0.266 | 0.500 |
| difficulty_mix_1_3 | 0.223 / 0.274 | 0.251 / 0.072 | 0.250 |

The reference violates the risk target at 0 operating points. Naive calibration violates at 22.5% in `risk_control` and fails the run.

## History (iterations 1-10)



## What Works

- Read the paper and implemented the core Conformal Thinking algorithm: upper-threshold false-positive control, parametric sigmoid lower-threshold false-negative control, Hoeffding UCB finite-sample correction, efficiency-loss candidate selection, and combined earliest-exit inference.
- Added a reproducible synthetic reasoning-trajectory dataset generator that provides fixed prompts, gold answers, stepwise predictions, confidence-like signals, and token counts.
- Added a baseline, reusable evaluator, shell scripts, scoring reference, and documentation.
- Local smoke test passed: `bash scripts/reproduce.sh` followed by `python validate.py --compare`.
- Scheduler job `0a166eb2-90f` passed the same end-to-end reproduction pipeline in the compute environment.
- Continuation audit on 2026-06-07 reran `bash scripts/reproduce.sh` and confirmed the evaluation reads saved baseline/method artifacts, `eval/` does not import from `method/`, and generated scores remain consistent with the reference contract.
- Tightened the evaluator during the continuation audit: method and baseline artifacts now include per-example stopping decisions, and `eval/` recomputes accuracy, token use, false-positive risk, and false-negative risk from those decisions plus held-out labels instead of trusting aggregate metrics reported by the method.
- Added scaled Figure 6-style solvable:unsolvable mix experiments at 3:1, 1:1, and 1:3. The reproduction script now regenerates each fixed split, runs upper-only and dual-threshold policies, and evaluates each saved artifact.
- Continuation audit on 2026-06-07 extended the reusable evaluator to emit all metrics declared in `scoring/reference.json`, including solvable accuracy, unsolvable token savings, max realized risk, and defer precision.

## Results

Current smoke-test operating point (`epsilon = 0.32`) on `data/synthetic_reasoning.jsonl` after the audit fix:

- `upper_only`: accuracy 0.308, token fraction 0.611, token savings 0.389, false-positive risk 0.339, false-negative risk 0.000, risk excess 0.019.
- `conformal_thinking`: accuracy 0.403, token fraction 0.343, token savings 0.657, false-positive risk 0.169, false-negative risk 0.008, risk excess 0.000, lower-exit fraction 0.428.

Additional solvable:unsolvable mix results:

- `3:1`: upper-only token savings 0.480 versus Conformal Thinking 0.668; risk excess is 0.000 for both, and the dual policy exits by the lower threshold on 0.292 of examples.
- `1:1`: upper-only token savings 0.332 versus Conformal Thinking 0.663; risk excess is 0.000 for both, and the dual policy exits by the lower threshold on 0.533 of examples.
- `1:3`: upper-only token savings 0.210 versus Conformal Thinking 0.641; risk excess is 0.000 for both, and the dual policy exits by the lower threshold on 0.719 of examples.

This supports `core_claim_plus` on the scaled synthetic benchmark: the dual-threshold method improves token efficiency and accuracy while keeping risk within tolerance, and the lower-threshold contribution grows as unsolvable trajectories become more common.

`scoring/reference.json` is a scaled benchmark reference for this runnable gym. The paper markdown reports the relevant outcomes mainly as curves in figures, not exact scalar tables; the paper-reported numerical setup is documented in `briefing/evaluation.md`.

## Remaining

- Higher milestones would require secondary robustness settings, such as repeated split trials, validation-size ablations, distribution-shift tests, or real LLM trajectory data.
- Full-scale reproduction would require generating or acquiring large reasoning-model trajectories for the paper's benchmark suite.

## Issues

- No official implementation was linked in the paper markdown or found via the arXiv/GitHub search performed during this turn, so the reproduction implements the algorithm directly from the paper.
- The original paper's main numerical results are presented as curves in figures rather than scalar tables, so `reference.json` encodes the claimed operating constraints and comparison structure rather than copied curve coordinates.
- The full paper setup uses large reasoning LLMs and AIME/GPQA/DeepScaleR/MathVision trajectories. This reproduction uses fixed synthetic trajectories to keep the environment runnable without large model downloads or login-node inference.
- Audit fix: the previous `reference.json` contained placeholder zeros. It now uses nonzero operating targets matching the scaled benchmark's score contract, and `scores.json` is regenerated by `scripts/evaluate.sh`.
- The expanded `reference.json` uses scalar operating targets from the fixed scaled benchmark because the paper reports the relevant results as figures/curves without tabulated coordinates.
- Continuation audit fix: the previous evaluator copied aggregate metric fields from method outputs. This has been corrected so scored metrics are recomputed independently from per-example decisions in the output artifacts.
- Final verification cleanup: public-facing scoring and evaluation documentation now use generic answer/defer/budget terminology so from-scratch agents can understand the task without seeing the paper's implementation details.
- Continuation audit fix: `scores.json` now includes every metric family declared by `reference.json`; missing values such as `solvable_accuracy`, `unsolvable_token_savings`, `max_realized_risk`, and `defer_precision` are recomputed in `eval/`.

## Deviations from Paper

- (Iteration 11) The data generator now has opaque answers, persistent wrong answers, muted-confidence solvable runs and per-profile signal transforms. Solvability is labelled by the full-budget answer. Calibration happens online through the evaluator's protocol, so calibration size, draws and epsilon are fixed by the benchmark (400 or 50 examples; epsilon grids per experiment).

- **Data/model scale**: The paper uses trajectories from Qwen3-8B, Qwen3-30B-A3B, DeepSeek-R1-Distill-Qwen-32B, and Qwen3-VL-8B on AIME, GPQA-Diamond, DeepScaleR, and MathVision. This reproduction substitutes a deterministic synthetic trajectory dataset with the same fields needed by the algorithm. The substitution avoids multi-GB model downloads and expensive LLM inference while preserving the paper's stopping-policy computation.
- **Signal set**: The paper evaluates confidence, EAT, token count, and a trained probe. This reproduction includes confidence-like, EAT-like, and token-fraction signals, but omits the learned probe because it requires hidden states from a large model trajectory corpus.
