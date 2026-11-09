#!/bin/bash
set -euo pipefail
cd /home/user
bash redteam/reference_cached/run.sh
bash redteam/shortcut_relabel_budget/run.sh
python3 redteam/analyze.py
