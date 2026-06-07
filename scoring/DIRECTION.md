# Research Direction

## Research Problem

This benchmark studies adaptive inference for reasoning language models under explicit risk constraints. The central question is how to decide when a partially generated reasoning trajectory has consumed enough compute, while preserving a user-chosen bound on the errors caused by stopping early.

## Research Scope

This benchmark focuses on risk-aware reasoning-budget allocation. A scientist should work on methods that improve stopping policies for ongoing reasoning traces, including how to estimate deployment risk, choose operating points from validation data, combine stopping signals, or detect when further reasoning is unlikely to help.

## Approach Scope

In-scope work must remain within adaptive stopping, abstention, calibration, and signal selection for fixed reasoning trajectories or fixed reasoning models. A scientist may redesign stopping signals, improve validation-efficient calibration, change how multiple signals are combined, introduce alternative bounded-loss risk criteria, or improve no-progress detection.

The output should still be a policy that consumes partial reasoning information and decides when to stop before a maximum budget. It must be evaluated by the same risk, accuracy, and token-use metrics as the benchmark.

## Out of Bounds

- Replacing the problem with model training for better task accuracy. The paper is about controlling inference-time reasoning compute for a fixed model, not improving the model's underlying reasoning ability.
- Switching to a stronger base model, external solver, retrieval system, verifier with extra supervision, or tool-use pipeline to improve answers. That changes the task rather than the stopping method.
- Optimizing only average token count while ignoring false positive and false negative risk. The paper's claim is compute reduction under risk control.
- Using test labels or post-hoc test curves to choose operating points. The research question is validation-time calibration for deployment.
- Reporting only a Pareto sweep without selecting risk-constrained operating points. Comparative curves are useful diagnostics, but the benchmark requires deployable configurations tied to user-specified tolerances.
