#!/bin/bash
# Held-out test evaluation: scores every policy registered under
# outputs/<method>/policy.json on held-out profiles generated inside eval/test/
# and writes scoring/scores_test.json. Runs with no arguments.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p scoring
# An interrupted run may have left the held-out generator sealed; the
# evaluator unseals it on start, reads it, and seals it while policies run.
python eval/test/evaluate_split.py "$@"
