# Evaluation

## Metrics

The evaluation is instance-based and operates on saved reasoning trajectories plus saved stopping decisions from a candidate system. For each example, the evaluator compares the selected stopping point against the gold answer and the full-budget trajectory.

- **Accuracy**: fraction of test questions answered correctly at the selected stopping point. If the system abstains or defers, that example is counted as incorrect for the main accuracy-vs-compute trade-off.
- **Token count**: total generated reasoning tokens consumed by the policy across the test set. Lower is better at fixed or comparable accuracy.
- **Token savings / token ratio**: reduction in token count relative to the full-budget trajectory or a uniform-budget baseline. Higher savings and lower ratios are better.
- **False positive risk**: risk of emitting an answer before the budget is exhausted when that answer is wrong.
- **False negative risk**: risk of abstaining or deferring before later trajectory steps would have produced a correct answer.
- **Risk excess**: amount by which the larger realized risk exceeds the configured risk tolerance. This is a diagnostic constraint metric; lower is better.
- **Defer fraction and defer precision**: how often the system abstains/defers and how often those decisions occur on examples that are not solved by the full-budget trajectory.

No scored metric depends on wall-clock time. Compute efficiency is measured through generated token counts and normalized token fractions.

## Baselines and Targets

Reference baselines should include:

- A **full-budget** policy that always consumes the maximum reasoning budget before answering.
- A **uniform-budget** policy that stops all examples at the same token or chunk budget.
- A **validation-tuned adaptive** policy that selects an operating point from labeled validation data.
- Single-signal adaptive policies where each available stopping signal is evaluated separately.

The key target patterns are:

- Realized test risk should stay below the user-specified tolerance across a sweep of tolerances, especially when validation data is limited.
- At comparable accuracy, adaptive stopping should use fewer total tokens than full-budget and uniform-budget policies.
- Useful policies should save more compute when the test mix contains more examples that are not solved by the full reasoning budget.
- Selecting among available stopping signals should improve efficiency compared with relying on any single signal across all operating points.

## Evaluation Protocol

Use held-out validation data only to select stopping configurations, then score on a disjoint test split. Evaluation should report accuracy versus total token usage over a sweep of risk tolerances, with both answer-error and premature-defer risks measured.

The benchmark includes difficulty-mix experiments with solvable:unsolvable ratios of 3:1, 1:1, and 1:3. An example is considered solvable if the full-budget trajectory reaches a correct answer at least once.

All methods must be evaluated from saved outputs produced by the candidate system. Evaluation code must not regenerate trajectories, recompute candidate stopping behavior internally, or import from the method implementation.

## Paper Setup

The paper evaluates Qwen3-8B, Qwen3-30B-A3B, DeepSeek-R1-Distill-Qwen-32B, and Qwen3-VL-8B on AIME 1983-2025, DeepScaleR without AIME, GPQA-Diamond, and MathVision. Its risk-control sanity check uses Qwen3-8B on AIME with 40 validation-test splits, validation size 50, and an epsilon sweep from 0 to 1 in increments of 0.01. The paper reports the main outcomes as plotted risk-vs-epsilon and accuracy-vs-token curves rather than scalar tables, so this runnable gym uses fixed scaled scalar targets in `scoring/reference.json` while preserving the same benefit and constraint metric structure.
