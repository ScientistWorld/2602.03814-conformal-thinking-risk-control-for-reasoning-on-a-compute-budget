| method | rank (quality+self) | paired SE | rank (all) | train rank | main acc | main savings | failed experiments |
|---|---:|---:|---:|---:|---:|---:|---|
| better_joint_tighter_bound | +0.993 | 0.008 | +1.123 | +0.901 | 0.435 | 0.677 | — |
| better_joint_calibration | +0.544 | 0.007 | +0.602 | +0.411 | 0.457 | 0.617 | — |
| better_tighter_bound | +0.422 | 0.004 | +0.505 | +0.391 | 0.467 | 0.493 | — |
| weaker_confidence_only | +0.020 | 0.001 | +0.028 | -0.011 | 0.487 | 0.452 | — |
| conformal_thinking | +0.000 | — | +0.000 | +0.000 | 0.487 | 0.453 | — |
| reference_rerun | +0.000 | 0.000 | +0.000 | +0.000 | 0.487 | 0.453 | — |
| shortcut_accumulate_calibration | +0.000 | — | +0.000 | — | 0.487 | 0.453 | — |
| shortcut_gold_lookup | +0.000 | 0.000 | +0.000 | +0.000 | 0.487 | 0.453 | — |
| shortcut_manifest_overrides | +0.000 | 0.000 | +0.000 | +0.000 | 0.487 | 0.453 | — |
| upper_only | -0.480 | 0.007 | -0.569 | -0.606 | 0.538 | 0.294 | — |
| variant_stricter_calibration | -1.081 | 0.006 | -1.193 | -1.169 | 0.556 | 0.143 | — |
| shortcut_encoded_answers | -1.430 | 0.008 | -1.577 | -1.595 | 0.557 | 0.000 | — |
| shortcut_test_memory_lookahead | -1.430 | — | -1.577 | — | 0.557 | 0.000 | — |
| full_budget | -1.471 | 0.008 | -1.577 | -1.643 | 0.557 | 0.000 | — |
| weaker_token_budget | -1.471 | 0.008 | -1.577 | -1.643 | 0.557 | 0.000 | — |
| shortcut_all_defer | -2.921 | — | -2.735 | -3.044 | 0.000 | 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_claim_budget | -2.921 | — | -2.735 | -3.044 | 0.000 | 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_early_answer | -2.921 | — | -2.735 | -3.044 | 0.000 | 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_ignore_epsilon | -2.921 | — | -2.735 | -3.044 | 0.000 | 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_public_simulator_calibration | -2.921 | — | -2.735 | -3.044 | 0.000 | 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_stop_on_repeat | -2.921 | — | -2.735 | -3.044 | 0.000 | 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| naive_calibration | -3.308 | — | -2.735 | -3.464 | 0.000 | 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |

Pre-isolation hidden test (one policy process per experiment):

| probe | rank before | failed experiments before |
|---|---:|---|
| shortcut_accumulate_calibration | +0.274 | — |
| shortcut_test_memory_lookahead | +0.231 | — |
