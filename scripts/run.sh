#!/bin/bash
# Job entry point: audit every candidate through the hidden test, then rerun the
# reference method and baselines end to end from the final code.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ "${SKIP_AUDIT:-0}" != "1" ]; then
  bash redteam/hardening/run_candidates.sh
fi

echo "== final reference reproduction $(date)"
time bash scripts/reproduce.sh
