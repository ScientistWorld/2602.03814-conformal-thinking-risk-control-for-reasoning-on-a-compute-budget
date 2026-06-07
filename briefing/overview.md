# Overview

- **Paper ID:** 2602.03814
- **Title:** Conformal Thinking: Risk Control for Reasoning on a Compute Budget
- **Domain:** Large Language Models / Test-Time Reasoning / Risk-Controlled Inference
- **TL;DR:** The paper calibrates adaptive early stopping for reasoning LLMs so users can trade off error risk and token cost with statistical risk control rather than hand-tuned thresholds.

## Short Summary

Reasoning LLMs often improve with more generated reasoning tokens, but fixed budgets waste compute and heuristic early exits can silently harm accuracy. This paper formulates reasoning-budget selection as risk control: a user specifies acceptable false positive and false negative risks, and held-out validation data calibrates stopping thresholds with finite-sample correction. The method combines a standard confidence-based upper threshold with a parametric lower threshold that stops trajectories unlikely to become correct. Experiments on math, science, and vision reasoning benchmarks show improved token efficiency while respecting target risks more reliably than naive validation tuning.

## Key Results

- Risk-controlled calibration keeps empirical test risk below target tolerances more consistently than naive validation tuning across random validation-test splits.
- Selecting the most efficient calibrated stopping signal improves the accuracy-versus-token trade-off across several reasoning models.
- Combining upper and lower exits saves more tokens when unsolvable examples are common, because the lower exit avoids spending the full budget on trajectories that do not improve.
