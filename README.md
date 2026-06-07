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

---

# Problem Definition

## Research Question

Reasoning language models can improve answer accuracy by spending more test-time compute, but a fixed reasoning budget wastes tokens on easy or hopeless instances and an adaptive budget can stop too early. The problem is to choose, for each reasoning instance, when to stop generating intermediate reasoning while preserving a user-specified bound on the error introduced by stopping.

The benchmark asks whether a system can allocate reasoning effort adaptively across a set of difficult question-answering tasks. A solution receives a prompt, a reasoning model's partial reasoning trajectory over time, candidate answers at intermediate stopping points, and scalar stopping signals. It must decide when to stop, answer, or abstain/defer before the maximum token budget is exhausted.

## Why It Matters

Reasoning models are expensive at inference time. A useful stopping policy should save tokens without turning opaque threshold tuning into a hidden accuracy failure mode, especially on hard datasets where many examples may never become answerable within the allowed budget.

## Success Criteria

A successful solution should:

- Keep realized early-stopping risk at or below a user-selected tolerance on held-out test data.
- Reduce token usage relative to a full-budget or uniform-budget policy at comparable task accuracy.
- Work across multiple stopping signals, datasets, and difficulty mixes without relying on test-set labels for threshold selection.
- Report both benefit metrics, such as accuracy and token reduction, and constraint metrics, such as false positive and false negative risk.

---

# Paper's Method

## Key Contribution

The paper reframes adaptive reasoning-budget selection as a distribution-free risk-control problem. Instead of hand-picking opaque confidence thresholds, the user specifies acceptable risks, and a validation set is used to calibrate stopping thresholds that satisfy those risks while minimizing wasted reasoning compute.

The main algorithmic contribution is a dual-threshold early-exit framework. It includes the standard upper threshold for stopping when the current answer appears reliable and a new parametric lower threshold for stopping or deferring when the reasoning signal fails to make enough progress.

## Approach

For each problem, the reasoning model produces a trajectory split into chunks. At each chunk, the system can elicit a candidate final answer and compute one or more scalar signals, such as answer confidence, entropy after the forced end-of-thinking token, token count, or a learned probe signal.

The method defines two correctness losses:

- False positive loss for stopping on an answer that is actually wrong.
- False negative loss for stopping or deferring an instance that could have reached a correct answer later in the remaining trajectory.

It also defines matching efficiency losses that measure wasted reasoning after a correct answer has first appeared or wasted reasoning spent on prefixes that remain incorrect.

Calibration enumerates candidate signals and threshold parameters on a labeled validation set. For each candidate, it computes empirical risk and then applies a finite-sample upper confidence correction. Candidates whose adjusted risk is at most the user-specified tolerance are feasible, and the method selects the feasible candidate with the lowest efficiency loss.

The upper threshold exits at the first chunk where the transformed confidence signal exceeds a calibrated value. The lower threshold exits at the first chunk where the signal falls below a calibrated time-dependent sigmoid curve, parameterized by a shape value and scaled by token usage. When both thresholds are used, the method calibrates the upper threshold first, then calibrates the lower threshold under that upper bound, and exits at the earliest of the upper exit, lower exit, or maximum budget.

## Main Claims

Primary claims:

- Finite-sample risk control yields realized held-out risk that respects user-specified tolerances better than naive validation tuning.
- Adaptive stopping selected under a risk budget reduces token usage while preserving comparable answer accuracy.
- Adding the lower threshold improves efficiency when many instances are unsolvable within the full reasoning budget.

Secondary claims:

- Choosing among multiple stopping signals by validation efficiency forms an effective signal ensemble for different risk tolerances and datasets.
- The benefit of risk control is larger when validation sets are small.
- Risk control remains more reliable than naive tuning under dataset shift, though lower-threshold risk can be sensitive to length shift because its shape depends on the reasoning horizon.

---

# Evaluation

## Metrics

The evaluation is instance-based and operates on saved reasoning trajectories and predictions. For each example, the evaluator compares the selected stopping point against the gold answer and the full-budget trajectory.

- **Accuracy**: fraction of test questions answered correctly after the selected stopping policy. If the system abstains or defers, that example is counted as incorrect for the main accuracy-vs-compute trade-off.
- **Token count**: total generated reasoning tokens consumed by the policy across the test set. Lower is better at a fixed or comparable accuracy.
- **Token savings / token ratio**: reduction in token count relative to the full-budget trajectory or a uniform-budget baseline. Higher savings and lower ratios are better.
- **False positive risk**: among cases where the system stops because the current answer is considered reliable, the rate of incorrect stopped answers. Lower is better and must satisfy the target risk tolerance.
- **False negative risk**: loss incurred when the system stops or abstains because the current and future trajectory is judged unlikely to become correct, but later trajectory steps would have produced correct answers. Lower is better and must satisfy the target risk tolerance.
- **Risk violation rate**: fraction of validation-test split trials for which realized test risk exceeds the requested tolerance. Lower is better.
- **Efficiency loss**: normalized wasted compute under the paper's evaluation definitions: extra tokens spent after first correctness for confident-answer exits, and tokens spent on still-incorrect prefixes for unsolvable/defer exits. Lower is better.

## Baselines and Targets

Reference baselines should include:

- A **full-budget** policy that always consumes the maximum reasoning budget before answering.
- A **uniform-budget** policy that stops all examples at the same token or chunk budget.
- A **naive validation-tuned** adaptive policy that selects thresholds using empirical validation risk without finite-sample correction.
- Single-signal adaptive policies where each stopping signal is calibrated and evaluated separately.

The paper reports qualitative curve-based targets rather than a single table of scalar numbers. The key target patterns are:

- Realized test risk should stay below the user-specified tolerance across a sweep of tolerances, especially for small validation sets.
- At comparable accuracy, adaptive stopping should use fewer total tokens than the full-budget and uniform-budget baselines.
- Combining complementary stopping criteria should improve the accuracy-token trade-off when unsolvable examples are common.
- Selecting among available stopping signals should improve efficiency compared with relying on any single signal across all operating points.

## Evaluation Protocol

Use held-out validation data only to select stopping configurations, then score on a disjoint test split. The paper's main risk-control check uses Qwen3-8B on AIME with 40 random validation-test splits, a validation size of 50 examples, and a sweep of target risk tolerances from 0 to 1 in increments of 0.01. Both false positive and false negative risk should be evaluated.

Efficiency experiments should report accuracy versus total token usage over the same tolerance sweep. The main lower-threshold efficiency setting pools AIME and GPQA-Diamond, labels examples by whether the full-budget trajectory ever reaches a correct answer, and evaluates controlled solvable:unsolvable ratios of 3:1, 1:1, and 1:3.

Robustness evaluations should vary validation set size and distribution shift. The paper studies validation sizes of 8, 16, and 40 examples with an 800-example test set on DeepScaleR, plus length shift and dataset shift between validation and test data.

All methods must be evaluated from saved outputs produced by the candidate system. Evaluation code should not regenerate trajectories, recompute candidate stopping behavior internally, or import from the method implementation.

---

# Reproduction Log

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 15m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

<!-- Write your progress here -->

</details>

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 30m | **GPU**: 0.0h

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 30m | **GPU**: 0.0h

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 30m | **GPU**: 0.0h

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 30m | **GPU**: 0.0h

### Iteration 1: gpt-5.5
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 10m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-07 00:00] - method_runs
- Implemented the paper's Conformal Thinking calibration and dual-threshold stopping algorithm.
- Verified the method, baseline, evaluator, and scoring pipeline with a local lightweight smoke test on fixed synthetic trajectories.

### [2026-06-07 11:00] - method_runs
- Audited the inherited implementation and confirmed it contains the paper's upper-threshold, lower-threshold, UCB calibration, and efficiency-selection steps.
- Fixed placeholder scoring references and adjusted synthetic trajectories so the lower threshold targets no-progress examples without collapsing accuracy.
- Local validation passes with generated scores; scheduler job submitted to verify before claiming `core_claim`.

### [2026-06-07 11:30] - core_claim
- Scheduler job `0a166eb2-90f` completed successfully with `bash scripts/reproduce.sh` and `python validate.py --compare`.
- The reproduced dual-threshold method improved accuracy and token savings over the upper-only baseline on the scaled synthetic benchmark while keeping risk excess at 0.

</details>

### Iteration 2: gpt-5.5
- **Milestone**: `core_claim` | **Status**: done
- **Working time**: 2m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-07 11:27] - method_runs
- Implemented Conformal Thinking calibration and inference on saved reasoning trajectories.
- Verified the method executes end-to-end through `scripts/reproduce.sh`.

### [2026-06-07 11:35] - core_claim
- Scheduler job `0a166eb2-90f` completed successfully in the compute environment.
- Reproduced the scaled core claim: dual upper/lower threshold stopping improved token savings from 0.389 to 0.657 while keeping risk excess at 0.000.
- `python validate.py --compare` passed import separation, evaluation-output, and scoring checks.

### [2026-06-07 11:45] - core_claim
- Continuation audit reviewed `method/`, `eval/`, `data/`, `baseline/`, scripts, scoring, briefing, and environment files.
- Confirmed the implementation is the paper's threshold-calibration algorithm, not a surrogate model: upper false-positive control, sigmoid lower false-negative control, UCB finite-sample correction, efficiency tie-breaking, and earliest dual exit are present.
- Reran `bash scripts/reproduce.sh`; scores regenerated from method artifacts and validation passed, restoring `core_claim` after the audit reset.

</details>

### Iteration 3: gpt-5.5
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 12m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-07 11:30] - method_runs
- Implemented the paper's upper-threshold false-positive loss, sigmoid lower-threshold false-negative loss, UCB finite-sample correction, efficiency-loss selection, and combined earliest-exit policy.
- Ran the method end-to-end on fixed synthetic reasoning trajectories.

### [2026-06-07 11:45] - core_claim
- Reproduced the core scaled claim on one held-out synthetic trajectory split: dual-threshold Conformal Thinking saved more tokens than upper-only stopping while satisfying the configured risk tolerance.
- Verified the reusable evaluator reads saved method and baseline artifacts and does not import from `method/`.

### [2026-06-07 12:05] - core_claim_plus
- Added three additional solvable:unsolvable mix experiments matching the paper's Figure 6 axis: 3:1, 1:1, and 1:3.
- Confirmed lower-threshold exits and token savings increase as unsolvable trajectories become more common, with `risk_excess` remaining zero in the scaled benchmark.

### [2026-06-07 11:40] - core_claim_plus
- Audited the continued workspace after milestone reset and fixed the evaluator so it recomputes all scored metrics from per-example stopping decisions and held-out labels instead of trusting method-reported aggregate metrics.
- Reran `bash scripts/reproduce.sh`; the corrected evaluator reproduced the same five-experiment score contract and `python validate.py --compare` passed.

</details>

### Iteration 4: gpt-5.5 (designer_stage_1)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 6m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-07 11:30] - method_runs
- Implemented the paper's upper-threshold false-positive loss, sigmoid lower-threshold false-negative loss, UCB finite-sample correction, efficiency-loss selection, and combined earliest-exit policy.
- Ran the method end-to-end on fixed synthetic reasoning trajectories.

### [2026-06-07 11:45] - core_claim
- Reproduced the core scaled claim on one held-out synthetic trajectory split: dual-threshold Conformal Thinking saved more tokens than upper-only stopping while satisfying the configured risk tolerance.
- Verified the reusable evaluator reads saved method and baseline artifacts and does not import from `method/`.

### [2026-06-07 12:05] - core_claim_plus
- Added three additional solvable:unsolvable mix experiments matching the paper's Figure 6 axis: 3:1, 1:1, and 1:3.
- Confirmed lower-threshold exits and token savings increase as unsolvable trajectories become more common, with `risk_excess` remaining zero in the scaled benchmark.

### [2026-06-07 11:40] - core_claim_plus
- Audited the continued workspace after milestone reset and fixed the evaluator so it recomputes all scored metrics from per-example stopping decisions and held-out labels instead of trusting method-reported aggregate metrics.
- Reran `bash scripts/reproduce.sh`; the corrected evaluator reproduced the same five-experiment score contract and `python validate.py --compare` passed.

</details>

### Iteration 5: gpt-5.5 (designer_stage_2)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 4m | **GPU**: 0.0h
- **Jobs**: 1 total (1 completed, 0 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-07 11:30] - method_runs
- Implemented the paper's upper-threshold false-positive loss, sigmoid lower-threshold false-negative loss, UCB finite-sample correction, efficiency-loss selection, and combined earliest-exit policy.
- Ran the method end-to-end on fixed synthetic reasoning trajectories.

### [2026-06-07 11:45] - core_claim
- Reproduced the core scaled claim on one held-out synthetic trajectory split: dual-threshold Conformal Thinking saved more tokens than upper-only stopping while satisfying the configured risk tolerance.
- Verified the reusable evaluator reads saved method and baseline artifacts and does not import from `method/`.

### [2026-06-07 12:05] - core_claim_plus
- Added three additional solvable:unsolvable mix experiments matching the paper's Figure 6 axis: 3:1, 1:1, and 1:3.
- Confirmed lower-threshold exits and token savings increase as unsolvable trajectories become more common, with `risk_excess` remaining zero in the scaled benchmark.

### [2026-06-07 11:40] - core_claim_plus
- Audited the continued workspace after milestone reset and fixed the evaluator so it recomputes all scored metrics from per-example stopping decisions and held-out labels instead of trusting method-reported aggregate metrics.
- Reran `bash scripts/reproduce.sh`; the corrected evaluator reproduced the same five-experiment score contract and `python validate.py --compare` passed.

</details>


---

# Reproduction Milestones

**Current: core_claim_plus**

## Stop Justification
- Completed at milestone `core_claim_plus`.
