#!/bin/bash
# Job entry point.
# 1. Final reference reproduction from the final code: the reference method and
#    the baselines alone (nothing else registered), train + hidden test.
# 2. AUDIT=full : redteam/hardening2/run_audit.sh (every audit candidate through
#    the hidden test, before/after probes on the previous gym, analysis).
#    AUDIT=none : stop after step 1.
# Phases leave markers in tmp/job_state/$RUN_TAG so a preempted job resumes.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export RUN_TAG="${RUN_TAG:-hardening2-v2}"
STATE="tmp/job_state/$RUN_TAG"
mkdir -p "$STATE"

if [ ! -f "$STATE/reproduce.done" ]; then
  # Only the reference and the baselines may be registered for this run.
  for dir in outputs/*/; do
    [ -d "$dir" ] || continue
    case "$(basename "$dir")" in
      conformal_thinking|upper_only|naive_calibration) ;;
      *) echo "removing stray registration $dir"; rm -rf "$dir" ;;
    esac
  done
  echo "== final reference reproduction $(date)"
  time bash scripts/reproduce.sh || echo "WARNING: reproduce.sh exited non-zero (validate --compare checks against reference.json values that this job replaces)"
  mkdir -p redteam/hardening2
  cp scoring/scores_test.json redteam/hardening2/reference_only_scores_test.json
  cp scoring/scores_train.json redteam/hardening2/reference_only_scores_train.json
  touch "$STATE/reproduce.done"
fi

case "${AUDIT:-full}" in
  full) bash redteam/hardening2/run_audit.sh ;;
  none) ;;
esac
