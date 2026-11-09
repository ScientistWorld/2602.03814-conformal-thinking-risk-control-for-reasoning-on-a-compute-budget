#!/bin/bash
set -euo pipefail
cd /home/user
for name in \
  reference_seed_11 reference_seed_22 reference_seed_33 reference_cached \
  better_joint_calibration better_strict_risk weaker_no_lower \
  baseline_full_budget baseline_first_answer \
  shortcut_gold_bruteforce shortcut_encoded_answers shortcut_solvable_flag \
  shortcut_early_budget shortcut_relabel_budget shortcut_all_defer shortcut_all_answer \
  shortcut_data_redirect shortcut_fixed_trajectory_tokens shortcut_impossible_tokens \
  shortcut_summary_forgery shortcut_self_report_only \
  shortcut_empty_decisions shortcut_null_decisions shortcut_invalid_exit \
  shortcut_move_baseline shortcut_operating_point; do
  echo "Running $name"
  bash "redteam/$name/run.sh"
done
python3 redteam/analyze.py
