#!/bin/bash
# Second hardening audit (REVIEW.md items). Runs after the reference-only
# reproduction in scripts/run.sh, so the stored reference scores never share a
# run with these candidates.
#
# 1. Final gym: register every candidate in redteam/hardening2/variants.py
#    exactly like a future method, score all of them with the hidden test
#    command (plus a per-instance outcome dump for paired noise), and score the
#    reference, baselines and honest variants on the visible train profiles.
# 2. Gym as of the start of this iteration (commit 6090d6e, rebuilt under
#    tmp/old_gym): score the new probes there, for before/after numbers.
# 3. Rank everything (redteam/hardening2/analyze.py), then remove the candidates.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
HERE=redteam/hardening2
OLD=tmp/old_gym

echo "== cpus: nproc=$(nproc) affinity=$(python -c 'import os; print(len(os.sched_getaffinity(0)))')"
python "$HERE/variants.py" build-bank --family new
python "$HERE/variants.py" build-bank --family old

SKIP_EVAL=1 bash scripts/method.sh
bash scripts/baseline.sh
CANDIDATES=$(python -c "import sys; sys.path.insert(0, '$HERE'); import variants; print(' '.join(variants.VARIANTS))")
for name in $CANDIDATES; do
  mkdir -p "outputs/$name"
  printf '{"command": ["python", "%s/variants.py", "serve", "%s"]}\n' "$HERE" "$name" > "outputs/$name/policy.json"
done

rm -rf logs/hardening2_outcomes
echo "== hidden test, all candidates $(date)"
time bash scripts/evaluate_test.sh --save-outcomes logs/hardening2_outcomes --scores "$HERE/scores_test_all.json"
python "$HERE/analyze.py" || echo "analysis (test only) failed"

echo "== before: new probes on the gym as of commit 6090d6e $(date)"
mkdir -p "$OLD/eval/test"
for f in evaluate_split.py hidden_tasks.py; do
  [ -f "$OLD/eval/test/$f" ] || git show "6090d6e:eval/test/$f" > "$OLD/eval/test/$f"
done
rm -rf "$OLD/outputs" && mkdir -p "$OLD/outputs"
for name in shortcut_simfit_ucb shortcut_simfit_naive shortcut_simfit_hybrid shortcut_simfit_cautious shortcut_read_hidden; do
  mkdir -p "$OLD/outputs/$name"
  printf '{"command": ["python", "%s/%s/variants.py", "serve", "%s", "--family", "old"]}\n' "$REPO_ROOT" "$HERE" "$name" > "$OLD/outputs/$name/policy.json"
done
time python "$OLD/eval/test/evaluate_split.py" --outputs "$REPO_ROOT/$OLD/outputs" --scores "$REPO_ROOT/$HERE/old_gym_scores_test.json"
python "$HERE/analyze.py"

echo "== visible train, reference/baselines/honest variants $(date)"
TRAIN_OUT=tmp/audit_train_outputs
rm -rf "$TRAIN_OUT" && mkdir -p "$TRAIN_OUT"
for name in conformal_thinking upper_only naive_calibration better_tighter_bound better_joint_calibration \
            better_joint_tighter_bound variant_stricter_calibration weaker_confidence_only weaker_eat_only weaker_token_budget; do
  cp -r "outputs/$name" "$TRAIN_OUT/"
done
time python eval/train/evaluate_split.py --outputs "$TRAIN_OUT" --scores "$HERE/scores_train_all.json"
python "$HERE/analyze.py" || echo "analysis failed"

for name in $CANDIDATES; do
  rm -rf "outputs/$name"
done
rm -rf "$TRAIN_OUT"
