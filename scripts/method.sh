#!/bin/bash
# Register the paper's method (risk-controlled dual-threshold early exit).
#
# The method needs no training: its deliverable is a stopping-policy program
# that calibrates on whatever labelled calibration set the evaluator sends and
# then stops held-out trajectories online. This script registers that program
# in outputs/conformal_thinking/policy.json, which the evaluators discover.
#
# Usage: bash scripts/method.sh

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p outputs/conformal_thinking
cat > outputs/conformal_thinking/policy.json <<'JSON'
{"command": ["python", "method/conformal_thinking.py", "serve"]}
JSON

if [ "${SKIP_EVAL:-0}" != "1" ]; then
  bash scripts/evaluate.sh
fi
