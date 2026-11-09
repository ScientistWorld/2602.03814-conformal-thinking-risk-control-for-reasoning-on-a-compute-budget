#!/bin/bash
# Evaluation script — scores every stopping policy registered under
# outputs/<method>/policy.json on the visible benchmark and writes
# scoring/scores.json (same experiments and metrics as scoring/reference.json).
#
# Self-contained: uses only eval/ and the public data generator in data/;
# it never imports method/. Policies are run as subprocesses through the
# online stopping protocol described in briefing/evaluation.md.
#
# Usage: bash scripts/evaluate.sh [--outputs DIR]

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p scoring
python eval/train/evaluate_split.py --scores scoring/scores.json "$@"
