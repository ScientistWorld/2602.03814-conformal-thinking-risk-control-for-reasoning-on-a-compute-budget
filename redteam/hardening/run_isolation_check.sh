#!/bin/bash
# Phase 2 of the hardening audit (after one-process-per-operating-point isolation).
#  1. "Before": the new in-memory probes through the previous hidden test
#     (eval/test/evaluate_split.py at commit e371aec, one process per experiment).
#  2. "After": reference, baselines, cheaper honest variants and the probes through
#     the current hidden test command (plus an outcome dump for paired noise).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
HERE=redteam/hardening
PROBES="shortcut_accumulate_calibration shortcut_test_memory_lookahead"
RERUN="better_tighter_bound variant_stricter_calibration weaker_confidence_only shortcut_encoded_answers $PROBES"

register() {  # register <outputs dir> <variant>
  mkdir -p "$1/$2"
  printf '{"command": ["python", "%s/variants.py", "serve", "%s"]}\n' "$HERE" "$2" > "$1/$2/policy.json"
}

# 1. before isolation
rm -rf tmp/eval_before_isolation tmp/before_outputs
mkdir -p tmp/eval_before_isolation tmp/before_outputs/conformal_thinking
git show e371aec:eval/test/evaluate_split.py > tmp/eval_before_isolation/evaluate_split.py
git show e371aec:eval/test/hidden_tasks.py > tmp/eval_before_isolation/hidden_tasks.py
echo '{"command": ["python", "method/conformal_thinking.py", "serve"]}' > tmp/before_outputs/conformal_thinking/policy.json
for name in $PROBES; do register tmp/before_outputs "$name"; done
echo "== probes through the pre-isolation hidden test $(date)"
time python tmp/eval_before_isolation/evaluate_split.py --outputs tmp/before_outputs \
  --scores "$HERE/scores_test_before_isolation.json"

# 2. after isolation, through the hidden test command
SKIP_EVAL=1 bash scripts/method.sh
bash scripts/baseline.sh
for name in $RERUN; do register outputs "$name"; done
rm -rf logs/hardening_outcomes_isolated
echo "== hidden test with per-operating-point isolation $(date)"
time bash scripts/evaluate_test.sh --save-outcomes logs/hardening_outcomes_isolated
cp scoring/scores_test.json "$HERE/scores_test_isolated.json"
for name in $RERUN; do rm -rf "outputs/$name"; done
rm -f scoring/scores_test.json
python "$HERE/analyze.py"
