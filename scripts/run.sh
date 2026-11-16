#!/bin/bash
# Job entry point.
# 1. Final reference reproduction from the final code: the reference method and
#    the baselines alone (nothing else registered), train + hidden test.
# 2. AUDIT=full : redteam/hardening2/run_audit.sh (every audit candidate through
#    the hidden test, before/after probes on the previous gym, analysis).
#    AUDIT=none : stop after step 1.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "== final reference reproduction $(date)"
time bash scripts/reproduce.sh || echo "WARNING: reproduce.sh exited non-zero (validate --compare checks against reference.json values that this job replaces)"

case "${AUDIT:-full}" in
  full) bash redteam/hardening2/run_audit.sh ;;
  none) ;;
esac
