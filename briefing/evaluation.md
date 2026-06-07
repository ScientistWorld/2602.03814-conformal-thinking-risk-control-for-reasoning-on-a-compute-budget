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
