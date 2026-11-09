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

In this benchmark the calibrated policy is deployed online: the evaluator sends a labelled calibration set with the target risk and confidence level, the policy runs the calibration above (upper threshold over the confidence, EAT-style and token-fraction signals; lower threshold over confidence with a grid of sigmoid shapes; Hoeffding correction with the supplied delta), and then decides continue/answer/defer chunk by chunk. If no candidate is feasible the corresponding exit is disabled, so the policy falls back to the full budget.

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
