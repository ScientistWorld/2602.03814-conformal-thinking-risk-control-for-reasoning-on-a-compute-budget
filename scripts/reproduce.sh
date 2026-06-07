#!/bin/bash
# Reproduce the paper's results end-to-end.
#
# This script runs inside the compute container and should call
# scripts/baseline.sh and scripts/method.sh to run baselines and
# the paper's method, each of which calls scripts/evaluate.sh.
#
# Assumes:
#   - Container is built (environment/container.sif)
#   - Data and models are downloaded (via scripts/download.sh)
#   - Working directory is /home/user
#
# This is the "gold standard" reproduction — 
# You do not need to run this, but keep this in good shape
# so other agents can easily run a full loop of reproduction and get the paper's numbers.

set -e

cd /home/user

python data/generate_synthetic_reasoning.py --output data/synthetic_reasoning.jsonl
python data/generate_synthetic_reasoning.py \
  --output data/synthetic_ratio_3_1.jsonl \
  --solvable-probability 0.75 \
  --seed 260203815
python data/generate_synthetic_reasoning.py \
  --output data/synthetic_ratio_1_1.jsonl \
  --solvable-probability 0.50 \
  --seed 260203816
python data/generate_synthetic_reasoning.py \
  --output data/synthetic_ratio_1_3.jsonl \
  --solvable-probability 0.25 \
  --seed 260203817

bash scripts/baseline.sh data/synthetic_reasoning.jsonl outputs/baseline/results.json
SKIP_EVAL=1 bash scripts/method.sh data/synthetic_reasoning.jsonl outputs/conformal_thinking/results.json

for ratio in 3_1 1_1 1_3; do
  bash scripts/baseline.sh "data/synthetic_ratio_${ratio}.jsonl" "outputs/baseline/ratio_${ratio}.json"
  SKIP_EVAL=1 bash scripts/method.sh \
    "data/synthetic_ratio_${ratio}.jsonl" \
    "outputs/conformal_thinking/ratio_${ratio}.json"
done

bash scripts/evaluate.sh
python validate.py --compare
