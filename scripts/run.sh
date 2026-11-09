#!/bin/bash
# Score the visible train slice and held-out test slice against all saved
# method artifacts discovered by the evaluators.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

bash scripts/evaluate_train.sh checkpoints
bash scripts/evaluate_test.sh checkpoints
