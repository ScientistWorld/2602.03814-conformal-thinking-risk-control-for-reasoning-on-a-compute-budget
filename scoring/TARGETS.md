# Evaluation Targets

## Primary: dual_threshold_efficiency

Tests whether a risk-calibrated adaptive stopping policy can reduce reasoning-token use compared with an upper-threshold-only adaptive baseline.

- **Primary metric**: `token_savings` (higher is better)
- **Benefit metrics**: `accuracy` (higher is better), `token_fraction` (lower is better)
- **Constraint metrics**: `false_positive_risk`, `false_negative_risk`, and `risk_excess` (all lower is better)
- **Evaluation**: run `bash scripts/reproduce.sh`, which generates fixed reasoning trajectories, runs the baseline and method, and writes `scoring/scores.json`

## Constraint: risk_control

Tests whether the selected operating point respects the requested false-positive and false-negative risk tolerance while still saving compute.

- **Primary metric**: `risk_excess` (lower is better)
- **Benefit metrics**: `token_savings` (higher is better), `token_fraction` (lower is better), `accuracy` (higher is better)
- **Constraint metrics**: `false_positive_risk` and `false_negative_risk` must remain at or below the configured tolerance
- **Evaluation**: run `bash scripts/evaluate.sh` after method artifacts exist; the evaluator reads saved method and baseline outputs rather than recalibrating the method itself
