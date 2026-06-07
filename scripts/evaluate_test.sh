#!/bin/bash
# Held-out test-slice evaluation entry point.
#
# Mirrors scripts/evaluate.sh's artifact-reading contract, but writes
# scoring/scores_test.json and invokes eval/test/'s held-out buffered slice.
# When scores_train.json is present, eval/test/ scores the same method keys for
# each experiment.

set -e

cd /home/user

mkdir -p scoring

python eval/test/evaluate_split.py "$@"
