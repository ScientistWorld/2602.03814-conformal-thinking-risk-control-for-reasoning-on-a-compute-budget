# Design Notes

## Checks Performed

- Read `scripts/evaluate_train.sh` and `scripts/evaluate_test.sh` side by side. The train script invokes `eval/train/evaluate_split.py` and writes `scoring/scores_train.json`; the test script invokes `eval/test/evaluate_split.py` and writes `scoring/scores_test.json`.
- Read both split evaluators to confirm they score saved method artifacts and do not import from `method/` or regenerate the paper method inline.
- Grepped for cross-imports between `eval/train/` and `eval/test/`, hardcoded `METHOD_NAME` defaults, forbidden paper-agreement metric names, and hardware-dependent speed metrics.
- Confirmed `scoring/reference.json` parses as JSON and `scripts/evaluate_{train,test}.sh` pass `bash -n`.
- Confirmed no `scoring/scores_train.json` or `scoring/scores_test.json` stubs exist.

## Changes Made

- Replaced the previous visible half / held-out complement split with disjoint stratified slices using a five-way partition:
  - `eval/train/` scores residues `{0, 1}`.
  - `eval/test/` scores residues `{3, 4}`.
  - Residue `2` is left unused as a buffer.
- Kept stratification by solvability and trajectory-length bucket so train and test remain comparable while making the exact held-out slice less directly inferable from the visible train split.
- Added subgroup metrics computed from saved per-example stopping decisions:
  - `solvable_accuracy`
  - `unsolvable_token_savings`
  - `lower_exit_precision`
- Added positional artifact support to both split evaluators so callers can pass result JSON paths directly as well as through `--method-results`.
- Updated `scoring/reference.json` so every metric has `higher_is_better`, `coefficient`, and `description`, and added the new subgroup metrics to each existing experiment.

## Runtime Concerns for Next Iteration

- I did not run either evaluator or produce scores, per the design-only instruction. The runner should verify that all existing output artifacts contain `decisions` for the new disjoint slices and that the new subgroup metrics are populated for every experiment.
- The split still uses public synthetic data; its protection comes from hidden test selection and subgroup triangulation, not from hidden examples. A method that memorizes all visible data labels could still overfit if it correctly infers the held-out selector.
- `lower_exit_precision` is `0.0` when a method never uses lower exits. That is intentional as a weak benefit signal for the paper's lower-threshold claim, but the runner should watch whether it over-penalizes conservative methods that satisfy risk through upper-only behavior.
