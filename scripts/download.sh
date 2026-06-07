#!/bin/bash
# Download all data and models needed for this environment.
#
# Run on a node with internet access BEFORE building the container
# or submitting compute jobs.
#
# This script should be idempotent — safe to run multiple times.
# It should skip files that already exist.
#
# Update the storage estimate below as you add downloads.
#
# Estimated total download size: 0 GB
# Estimated disk usage after extraction: about 6 MB
#
# This reproduction has no remote resources. The command below regenerates the
# tracked synthetic trajectories used for portable smoke tests.

set -e

cd /home/user

# This scaled reproduction uses agent-authored synthetic trajectory data stored
# in git. No external downloads are required for the runnable benchmark.
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
