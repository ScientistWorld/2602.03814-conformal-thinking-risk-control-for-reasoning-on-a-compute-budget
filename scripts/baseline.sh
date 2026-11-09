#!/bin/bash
# Register the baseline stopping policies so every evaluator scores them:
#   upper_only         - single risk-controlled upper ("stop when confident") threshold
#   naive_calibration  - thresholds tuned on raw validation risk, no finite-sample correction
# The always-full-budget control (full_budget) is built into the evaluators.
#
# Usage: bash scripts/baseline.sh

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p outputs/upper_only outputs/naive_calibration
cat > outputs/upper_only/policy.json <<'JSON'
{"command": ["python", "baseline/upper_only.py"]}
JSON
cat > outputs/naive_calibration/policy.json <<'JSON'
{"command": ["python", "baseline/naive_calibration.py"]}
JSON
