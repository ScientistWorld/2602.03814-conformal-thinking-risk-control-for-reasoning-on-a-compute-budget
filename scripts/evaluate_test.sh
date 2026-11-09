#!/bin/bash
# Held-out test evaluation: scores every policy registered under
# outputs/<method>/policy.json on held-out profiles generated inside eval/test/
# and writes scoring/scores_test.json. Runs with no arguments.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p scoring
python eval/test/evaluate_split.py "$@"
