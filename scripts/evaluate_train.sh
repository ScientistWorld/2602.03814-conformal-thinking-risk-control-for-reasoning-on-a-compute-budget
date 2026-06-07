#!/bin/bash
# Visible train-slice evaluation entry point.
#
# Mirrors scripts/evaluate.sh's artifact-reading contract, but writes
# scoring/scores_train.json and evaluates only eval/train/'s deterministic
# buffered visible slice of the original paper test examples.

set -e

cd /home/user

mkdir -p scoring

python eval/train/evaluate_split.py "$@"
