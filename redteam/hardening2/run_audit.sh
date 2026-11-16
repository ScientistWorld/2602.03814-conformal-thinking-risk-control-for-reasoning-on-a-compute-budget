#!/bin/bash
# Second hardening audit (REVIEW.md items). Runs after the reference-only
# reproduction in scripts/run.sh, so the stored reference scores never share a
# run with these candidates. Resumable: each finished phase leaves a marker in
# tmp/job_state/$RUN_TAG, and a restarted job (preemption) skips it.
#
# 1. Final gym: every candidate in redteam/hardening2/variants.py is registered
#    as <outputs dir>/<name>/policy.json (one outputs dir per batch, never the
#    main outputs/) and scored by the hidden test command, with a per-instance
#    outcome dump for paired noise. Batches are merged into scores_test_all.json.
# 2. Gym as of the start of this iteration (commit 6090d6e, rebuilt under
#    tmp/old_gym): the new probes, for before/after numbers.
# 3. Visible train for the reference, baselines and honest variants.
# 4. Ranking (redteam/hardening2/analyze.py).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
HERE=redteam/hardening2
OLD=tmp/old_gym
STATE="tmp/job_state/${RUN_TAG:-hardening2}"
PARTS=tmp/hardening2_parts
mkdir -p "$STATE" "$PARTS"

phase() {  # helpers called by a phase must not assign to "name" (bash dynamic scope)
  local name=$1
  shift
  if [ -f "$STATE/$name.done" ]; then
    echo "== skip $name (done in an earlier attempt)"
    return
  fi
  echo "== $name $(date)"
  "$@"
  touch "$STATE/$name.done"
}

register() {  # register <dir> <name>...
  local dir=$1 nam2
  shift
  rm -rf "$dir" && mkdir -p "$dir"
  for nam2 in "$@"; do
    mkdir -p "$dir/$nam2"
    case $nam2 in
      conformal_thinking) echo '{"command": ["python", "method/conformal_thinking.py", "serve"]}' > "$dir/$nam2/policy.json" ;;
      upper_only) echo '{"command": ["python", "baseline/upper_only.py"]}' > "$dir/$nam2/policy.json" ;;
      naive_calibration) echo '{"command": ["python", "baseline/naive_calibration.py"]}' > "$dir/$nam2/policy.json" ;;
      *) printf '{"command": ["python", "%s/variants.py", "serve", "%s"]}\n' "$HERE" "$nam2" > "$dir/$nam2/policy.json" ;;
    esac
  done
}

test_batch() {  # test_batch <batch> <name>...
  local batch=$1
  shift
  register "tmp/audit_outputs/$batch" "$@"
  time bash scripts/evaluate_test.sh --outputs "tmp/audit_outputs/$batch" --scores "$PARTS/test_$batch.json" \
    --save-outcomes logs/hardening2_outcomes
}

train_batch() {
  local batch=$1
  shift
  register "tmp/audit_outputs/train_$batch" "$@"
  time python eval/train/evaluate_split.py --outputs "tmp/audit_outputs/train_$batch" --scores "$PARTS/train_$batch.json"
}

banks() {
  echo "cpus: nproc=$(nproc) affinity=$(python -c 'import os; print(len(os.sched_getaffinity(0)))')"
  python "$HERE/variants.py" build-bank --family new
  python "$HERE/variants.py" build-bank --family old
}

old_gym() {
  local nam2 f
  mkdir -p "$OLD/eval/test"
  for f in evaluate_split.py hidden_tasks.py; do
    [ -f "$OLD/eval/test/$f" ] || git show "6090d6e:eval/test/$f" > "$OLD/eval/test/$f"
  done
  rm -rf "$OLD/outputs" && mkdir -p "$OLD/outputs"
  for nam2 in shortcut_simfit_ucb shortcut_simfit_naive shortcut_simfit_hybrid shortcut_simfit_cautious shortcut_read_hidden; do
    mkdir -p "$OLD/outputs/$nam2"
    printf '{"command": ["python", "%s/%s/variants.py", "serve", "%s", "--family", "old"]}\n' "$REPO_ROOT" "$HERE" "$nam2" > "$OLD/outputs/$nam2/policy.json"
  done
  time python "$OLD/eval/test/evaluate_split.py" --outputs "$REPO_ROOT/$OLD/outputs" --scores "$REPO_ROOT/$HERE/old_gym_scores_test.json"
}

phase banks banks
phase test_b1 test_batch b1 conformal_thinking upper_only naive_calibration fast_reference
phase test_b2 test_batch b2 better_tighter_bound better_joint_calibration better_joint_tighter_bound
phase test_b3 test_batch b3 variant_stricter_calibration weaker_confidence_only weaker_eat_only weaker_token_budget
phase test_b4 test_batch b4 shortcut_simfit_ucb shortcut_simfit_naive shortcut_simfit_hybrid shortcut_simfit_cautious
phase test_b5 test_batch b5 shortcut_public_simulator_calibration shortcut_read_hidden shortcut_stop_on_repeat \
  shortcut_fixed_rule shortcut_early_answer shortcut_all_defer shortcut_ignore_epsilon
python "$HERE/merge_scores.py" "$HERE/scores_test_all.json" "$PARTS"/test_b*.json
python "$HERE/analyze.py" || echo "analysis (test only) failed"

phase old_gym old_gym
python "$HERE/analyze.py" || echo "analysis failed"

phase train_t1 train_batch t1 conformal_thinking upper_only naive_calibration better_tighter_bound
phase train_t2 train_batch t2 better_joint_calibration better_joint_tighter_bound
phase train_t3 train_batch t3 variant_stricter_calibration weaker_confidence_only weaker_eat_only weaker_token_budget
python "$HERE/merge_scores.py" "$HERE/scores_train_all.json" "$PARTS"/train_t*.json
python "$HERE/analyze.py"
rm -rf tmp/audit_outputs
