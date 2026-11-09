#!/bin/bash
# Audit run for the hardened gym. Installs every candidate exactly like a future
# method (outputs/<name>/policy.json), scores all of them with the hidden test
# command (plus an outcome dump used only for the paired-noise analysis) and the
# visible train command, saves the evidence, then removes the candidates.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
HERE=redteam/hardening

SKIP_EVAL=1 bash scripts/method.sh
bash scripts/baseline.sh

CANDIDATES=$(python -c "import sys; sys.path.insert(0, '$HERE'); import variants; print(' '.join(variants.VARIANTS))")
mkdir -p outputs/reference_rerun
cp outputs/conformal_thinking/policy.json outputs/reference_rerun/policy.json
for name in $CANDIDATES; do
  mkdir -p "outputs/$name"
  printf '{"command": ["python", "%s/variants.py", "serve", "%s"]}\n' "$HERE" "$name" > "outputs/$name/policy.json"
done
# A manifest that tries to point the evaluator at its own data/scores is just ignored.
mkdir -p outputs/shortcut_manifest_overrides
cat > outputs/shortcut_manifest_overrides/policy.json <<'JSON'
{"command": ["python", "method/conformal_thinking.py", "serve"],
 "config": {"data": "data/easy.jsonl", "epsilon": 1000, "tokens": -1000000000},
 "scores": {"token_savings": 1.0, "accuracy": 1.0}}
JSON

rm -rf logs/hardening_outcomes
echo "== hidden test (all candidates) $(date)"
time bash scripts/evaluate_test.sh --save-outcomes logs/hardening_outcomes
cp scoring/scores_test.json "$HERE/scores_test_all.json"
python "$HERE/analyze.py" || echo "analysis (test only) failed"

echo "== visible train (all candidates) $(date)"
time bash scripts/evaluate_train.sh
cp scoring/scores_train.json "$HERE/scores_train_all.json"
python "$HERE/analyze.py"

for name in $CANDIDATES reference_rerun shortcut_manifest_overrides; do
  rm -rf "outputs/$name"
done
rm -f scoring/scores_train.json scoring/scores_test.json
