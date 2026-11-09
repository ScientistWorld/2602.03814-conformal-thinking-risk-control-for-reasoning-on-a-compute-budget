#!/bin/bash
# Visible train evaluation: scores every policy registered under
# outputs/<method>/policy.json on the public development profiles and writes
# scoring/scores_train.json. Same protocol, experiments and metrics as the
# held-out test.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p scoring
python eval/train/evaluate_split.py "$@"
