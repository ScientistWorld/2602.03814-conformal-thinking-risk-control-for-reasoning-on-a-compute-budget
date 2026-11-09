#!/bin/bash
# Job entry point.
#   AUDIT=full      : redteam/hardening/run_candidates.sh (every candidate, train + test)
#   AUDIT=isolation : redteam/hardening/run_isolation_check.sh (phase-2 audit, test only)
#   AUDIT=none      : skip the audit
# then rerun the reference method and baselines end to end from the final code.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

case "${AUDIT:-none}" in
  full) bash redteam/hardening/run_candidates.sh ;;
  isolation) bash redteam/hardening/run_isolation_check.sh ;;
  none) ;;
esac

echo "== final reference reproduction $(date)"
time bash scripts/reproduce.sh
