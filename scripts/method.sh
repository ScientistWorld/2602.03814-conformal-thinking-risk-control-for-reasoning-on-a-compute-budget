#!/bin/bash
# Run the paper's proposed method.
#
# This script trains/runs the paper's method using code in method/.
#
# Usage:
#   bash scripts/method.sh

set -e

cd /home/user

python method/conformal_thinking.py \
  --data data/synthetic_reasoning.jsonl \
  --output outputs/conformal_thinking/results.json \
  --calibration ucb \
  --epsilons 0.18 0.25 0.32 0.40

bash scripts/evaluate.sh
