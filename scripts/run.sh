#!/bin/bash
# Score the visible train slice and held-out test slice against all saved
# method artifacts discovered by the evaluators.

set -e

cd /home/user

bash scripts/evaluate_train.sh /home/user/checkpoints
bash scripts/evaluate_test.sh /home/user/checkpoints
