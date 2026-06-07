# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-07 11:27] - method_runs
- Implemented Conformal Thinking calibration and inference on saved reasoning trajectories.
- Verified the method executes end-to-end through `scripts/reproduce.sh`.

### [2026-06-07 11:35] - core_claim
- Scheduler job `0a166eb2-90f` completed successfully in the compute environment.
- Reproduced the scaled core claim: dual upper/lower threshold stopping improved token savings from 0.389 to 0.657 while keeping risk excess at 0.000.
- `python validate.py --compare` passed import separation, evaluation-output, and scoring checks.

## Stop Justification
- Completed at milestone `core_claim`. The paper's actual stopping algorithm is implemented and validated on a non-trivial scaled synthetic trajectory benchmark; higher milestones would require large real LLM trajectory generation outside the current compact reproduction scope.
