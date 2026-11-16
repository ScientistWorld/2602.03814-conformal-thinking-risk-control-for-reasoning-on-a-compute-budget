#!/bin/bash
# Job entry point: reproduce the reference end to end from the final code.
# Only the reference method and the baselines are registered for this run, so
# the stored reference scores never share a run with other policies.
#   AUDIT=full : afterwards, rerun the hardening audit (redteam/hardening2/run_audit.sh;
#                resumable through tmp/job_state/$RUN_TAG).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

for dir in outputs/*/; do
  [ -d "$dir" ] || continue
  case "$(basename "$dir")" in
    conformal_thinking|upper_only|naive_calibration) ;;
    *) echo "removing stray registration $dir"; rm -rf "$dir" ;;
  esac
done

echo "== reference reproduction $(date)"
time bash scripts/reproduce.sh || echo "WARNING: reproduce.sh exited non-zero"
mkdir -p redteam/hardening2
cp scoring/scores_test.json redteam/hardening2/reference_only_scores_test.json
cp scoring/scores_train.json redteam/hardening2/reference_only_scores_train.json

if [ "${AUDIT:-full}" = "full" ]; then
  export RUN_TAG="${RUN_TAG:-hardening2-v3}"
  bash redteam/hardening2/run_audit.sh
fi
