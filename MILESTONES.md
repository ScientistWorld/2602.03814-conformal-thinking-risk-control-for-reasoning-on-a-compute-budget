# Reproduction Milestones

**Current: secondary_claims**

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

### [2026-06-07 12:16] - core_claim_plus
- Extended the main reusable evaluator so `scores.json` includes the full metric set declared by `reference.json`, including solvable accuracy, unsolvable token savings, maximum realized risk, and defer precision.
- Reran `bash scripts/reproduce.sh`; the scaled benchmark still passes `python validate.py --compare`.

### [2026-06-07 12:20] - core_claim_plus
- Completed final gym verification of scoring metadata, method-agnostic documentation, train/test split wiring, download portability, and repository hygiene.
- Added explicit scaled-reference notes in `reference.json`, aligned `scoring/TARGETS.md` with the scored metric set, and removed stale transcript artifacts from the tracked workspace.

### [2026-11-09] - core_claim_plus (hardening, iteration 11)
- Rebuilt the measurement as a hidden, online test: held-out profiles, calibration pools and test sets are generated only inside `eval/test/`; methods are stopping-policy programs that see one chunk at a time; exits, tokens and every score are computed by the evaluator; any risk-constraint or protocol failure fails the run.
- Reproduced on the hidden test: lower+upper thresholds save more tokens than upper-only (gap +0.10 → +0.16 → +0.22 from 3:1 → natural → 1:1 mixes), UCB never violates the risk target while naive calibration fails the gate with 50 calibration examples. Reference is deterministic and reproduces exactly. Details in `HARDENING.md`.

### [2026-11-16] - secondary_claims (hardening, round 2)
- Signal-ensemble claim (Fig. 5) now exercised: on the hidden test, confidence-only and EAT-only rank −0.37 below the reference (paired SE 0.005), and the ensemble saves more than either single signal in every experiment.
- Lower-threshold gain over upper-only grows with the unsolvable share (+0.057 at 3:1, +0.121 natural, +0.129 at 1:1); UCB never violates the target while naive calibration fails at n=50 (37.5% of operating points).
- Risk control matters more for small validation sets (Fig. 7): naive calibration stays within the gate with 400 calibration examples but fails with 50.
- Not exercised: the dataset/length-shift ablations (Fig. 8-9) and the learned probe signal.
- Lower threshold calibrated on the selected signal, as in Sec. 4.4. Simulator-fit and hidden-generator shortcuts closed (details in `HARDENING.md`).

## Stop Justification
- Completed at milestone `core_claim_plus`.
