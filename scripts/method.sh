#!/bin/bash
# Run the paper's proposed method.
#
# This script trains/runs the paper's method using code in method/.
#
# Usage:
#   bash scripts/method.sh [data_jsonl] [output_json]

set -e

cd /home/user

DATA_PATH="${1:-data/synthetic_reasoning.jsonl}"
OUTPUT_PATH="${2:-outputs/conformal_thinking/results.json}"

python method/conformal_thinking.py \
  --data "$DATA_PATH" \
  --output "$OUTPUT_PATH" \
  --calibration ucb \
  --epsilons 0.18 0.25 0.32 0.40

if [ "${SKIP_EVAL:-0}" != "1" ]; then
  bash scripts/evaluate.sh
fi
