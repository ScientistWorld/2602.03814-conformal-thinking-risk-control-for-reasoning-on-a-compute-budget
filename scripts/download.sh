#!/bin/bash
# Download all data and models needed for this environment.
#
# Estimated total download size: 0 GB
# Estimated disk usage: under 10 MB
#
# This benchmark has no external resources: every trajectory is simulated by
# the public generator in data/generate_synthetic_reasoning.py (visible
# development data, generated in memory by eval/train/) or by the held-out
# generator inside eval/test/. The command below writes an optional local copy
# of public development data for inspection; it is idempotent.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="$(command -v python3 || command -v python)"
mkdir -p data/downloads
for profile in public_a public_b public_c; do
  for setting in natural ratio_3_1 ratio_1_1 ratio_1_3; do
    target="data/downloads/dev_${profile}_${setting}.jsonl"
    if [ ! -f "$target" ]; then
      "$PY" data/generate_synthetic_reasoning.py \
        --profile "$profile" --setting "$setting" --size 500 --output "$target"
    fi
  done
done
