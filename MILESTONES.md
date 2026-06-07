# Reproduction Milestones

**Current: core_claim_plus**

## Progress Log

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

### [2026-06-07 12:12] - core_claim_plus
- Completed final verification of folder structure, method/evaluation separation, reusable scoring, and train/test split wiring.
- Cleaned public-facing experiment and metric names so from-scratch documentation stays method-agnostic, then reran `python validate.py --compare`.

## Stop Justification
- Completed at milestone `core_claim_plus`.
