# Evaluation Targets

All targets are measured by `scripts/evaluate_test.sh` (held-out profiles) and `scripts/evaluate_train.sh` / `scripts/evaluate.sh` (public development profiles), which run every policy registered under `outputs/<method>/policy.json` through the online stopping protocol in `briefing/evaluation.md`. Every number is recomputed by the evaluator from per-instance stopping decisions on trajectories it owns.

Every experiment has the same metric structure:

- **Scored benefit metrics**: `token_savings` (coefficient 1.0, higher is better; primary metric everywhere except `risk_control`) and `accuracy` (coefficient 0.5, higher is better), averaged over the experiment's operating points.
- **Constraint metrics** (coefficient 0, enforced by the gate): `false_positive_risk`, `false_negative_risk`, `violation_rate` (fraction of operating points with realized risk above the target). If `violation_rate > 0.15` in any experiment, or the protocol is broken, the whole run receives the failure values (accuracy 0, savings 0, risks 1).
- **Diagnostics** (coefficient 0): `solvable_accuracy`, `unsolvable_token_savings`, `constraint_satisfied`, `defer_fraction`, `defer_precision`, `budget_exit_fraction`.

Across all experiments, the most informative stopping signal differs between profiles and target risks, so a policy restricted to one fixed signal should save fewer tokens than one that chooses among the signals from its calibration data (measured on the hidden test: confidence-only and EAT-only both rank clearly below the reference).

## Primary: adaptive_budget_efficiency (weight 0.3)

Natural mix (~58% solvable), 400 calibration examples, 4 draws per profile, target risks 0.10 / 0.15 / 0.20. Target: save tokens relative to running every instance to the full budget, at accuracy comparable to the confident-stop baseline, with no constraint failure.

## Constraint: risk_control (weight 0.2)

Primary metric: `violation_rate` (the paper's risk-control measurement: realized risk vs. the target across calibration draws). Scoring is the same as elsewhere (token savings and accuracy; violation rate gated).

Natural mix on separate held-out profiles, 50 calibration examples, 10 draws per profile, target risks 0.05 / 0.10 / 0.20 / 0.25. Target: realized risks within tolerance on at least 85% of operating points (the paper's claim is that finite-sample-corrected calibration achieves this while naive validation tuning does not), with as many tokens saved as the scarce calibration data allows. With only 50 examples the reference's lower (no-progress) exit is never feasible on the held-out profiles, so here it saves exactly as much as the confident-stop baseline; tighter finite-sample bounds leave room above it.

## Additional: difficulty_mix_3_1 (weight 0.15)

3:1 solvable:unsolvable, 400 calibration examples, 4 draws, target risks 0.10 / 0.15 / 0.20. Target: savings beyond the confident-stop baseline at comparable accuracy.

## Additional: difficulty_mix_1_1 (weight 0.15)

1:1 mix, same calibration and tolerances. Target: a larger savings gain over the confident-stop baseline than in the 3:1 mix.

## Additional: difficulty_mix_1_3 (weight 0.2)

1:3 mix, 400 calibration examples, 4 draws, target risks 0.05 / 0.10 / 0.125. Target: substantial savings where a confident-stop policy runs most instances to the budget.
