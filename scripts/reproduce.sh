#!/bin/bash
# Reproduce the paper's results end-to-end on this scaled benchmark.
#
# 1. Register the reference method and the baselines (no training needed:
#    each is a stopping-policy program calibrated online by the evaluator).
# 2. Score them on the visible train profiles (scores_train.json and
#    scores.json) and on the held-out test profiles (scores_test.json).
# 3. Validate the workspace.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_EVAL=1 bash scripts/method.sh
bash scripts/baseline.sh

bash scripts/evaluate_train.sh
cp scoring/scores_train.json scoring/scores.json
bash scripts/evaluate_test.sh
python validate.py --compare
