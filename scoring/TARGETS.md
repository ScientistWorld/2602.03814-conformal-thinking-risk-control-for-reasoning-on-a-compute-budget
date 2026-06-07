# Evaluation Targets

## Primary: adaptive_budget_efficiency

Tests whether an adaptive reasoning-budget policy can reduce token use compared with a reference adaptive baseline while preserving bounded stopping risk.

- **Primary metric**: `token_savings` (higher is better)
- **Benefit metrics**: `accuracy`, `solvable_accuracy`, `token_savings`, `unsolvable_token_savings`, `defer_fraction`, and `defer_precision`
- **Constraint metrics**: `token_fraction`, `false_positive_risk`, `false_negative_risk`, `max_realized_risk`, and `exit_budget_fraction`
- **Diagnostic metric**: `risk_excess` is reported but has zero scoring coefficient
- **Evaluation**: run `bash scripts/reproduce.sh`; the evaluator reads saved decisions from `outputs/*/results.json` and writes `scoring/scores.json`

## Constraint: risk_control

Tests whether the selected operating point respects the requested answer-error and premature-defer risk tolerance while still saving compute.

- **Primary metric**: `false_positive_risk` (lower is better)
- **Benefit metrics**: `accuracy`, `solvable_accuracy`, `token_savings`, `unsolvable_token_savings`, `defer_fraction`, and `defer_precision`
- **Constraint metrics**: `token_fraction`, `false_positive_risk`, `false_negative_risk`, `max_realized_risk`, and `exit_budget_fraction`
- **Diagnostic metric**: `risk_excess` is reported but has zero scoring coefficient
- **Evaluation**: run `bash scripts/evaluate.sh` after method artifacts exist; the evaluator recomputes metrics from saved decisions and labels

## Additional: difficulty_mix_3_1

Tests the policy on a synthetic split with a 3:1 solvable:unsolvable mix.

- **Primary metric**: `token_savings` (higher is better)
- **Benefit metrics**: `accuracy`, `solvable_accuracy`, `token_savings`, `unsolvable_token_savings`, `defer_fraction`, and `defer_precision`
- **Constraint metrics**: `token_fraction`, `false_positive_risk`, `false_negative_risk`, `max_realized_risk`, and `exit_budget_fraction`
- **Diagnostic metric**: `risk_excess` is reported but has zero scoring coefficient
- **Evaluation**: run `bash scripts/reproduce.sh`; the evaluator reads `outputs/*/ratio_3_1.json`

## Additional: difficulty_mix_1_1

Tests the policy when solvable and unsolvable trajectories are balanced.

- **Primary metric**: `token_savings` (higher is better)
- **Benefit metrics**: `accuracy`, `solvable_accuracy`, `token_savings`, `unsolvable_token_savings`, `defer_fraction`, and `defer_precision`
- **Constraint metrics**: `token_fraction`, `false_positive_risk`, `false_negative_risk`, `max_realized_risk`, and `exit_budget_fraction`
- **Diagnostic metric**: `risk_excess` is reported but has zero scoring coefficient
- **Evaluation**: run `bash scripts/reproduce.sh`; the evaluator reads `outputs/*/ratio_1_1.json`

## Additional: difficulty_mix_1_3

Tests a setting where most trajectories are unsolvable within the full budget, so policies that wait to the budget limit tend to waste tokens.

- **Primary metric**: `token_savings` (higher is better)
- **Benefit metrics**: `accuracy`, `solvable_accuracy`, `token_savings`, `unsolvable_token_savings`, `defer_fraction`, and `defer_precision`
- **Constraint metrics**: `token_fraction`, `false_positive_risk`, `false_negative_risk`, `max_realized_risk`, and `exit_budget_fraction`
- **Diagnostic metric**: `risk_excess` is reported but has zero scoring coefficient
- **Evaluation**: run `bash scripts/reproduce.sh`; the evaluator reads `outputs/*/ratio_1_3.json`
