| method | rank Q | paired SE | rank all | train rank | main acc / savings | risk_control acc / savings | 1:3 acc / savings | failed |
|---|---:|---:|---:|---:|---|---|---|---|
| better_joint_tighter_bound | +1.039 | 0.008 | +1.143 | +0.494 | 0.512 / 0.553 | 0.475 / 0.285 | 0.195 / 0.467 | — |
| better_joint_calibration | +0.536 | 0.007 | +0.589 | +0.274 | 0.517 / 0.512 | 0.508 / 0.150 | 0.214 / 0.372 | — |
| better_tighter_bound | +0.533 | 0.005 | +0.590 | +0.160 | 0.496 / 0.492 | 0.513 / 0.205 | 0.226 / 0.317 | — |
| conformal_thinking | +0.000 | — | +0.000 | +0.000 | 0.510 / 0.441 | 0.529 / 0.109 | 0.240 / 0.166 | — |
| fast_reference | +0.000 | 0.000 | +0.000 | — | 0.510 / 0.441 | 0.529 / 0.109 | 0.240 / 0.166 | — |
| shortcut_read_hidden | +0.000 | 0.000 | +0.000 | — | 0.510 / 0.441 | 0.529 / 0.109 | 0.240 / 0.166 | — |
| shortcut_simfit_cautious | -0.126 | 0.005 | -0.139 | — | 0.547 / 0.359 | 0.497 / 0.199 | 0.249 / 0.063 | — |
| upper_only | -0.337 | 0.006 | -0.383 | -0.231 | 0.556 / 0.320 | 0.529 / 0.109 | 0.249 / 0.079 | — |
| weaker_eat_only | -0.366 | 0.005 | -0.362 | -0.417 | 0.520 / 0.324 | 0.528 / 0.092 | 0.240 / 0.142 | — |
| weaker_confidence_only | -0.370 | 0.005 | -0.392 | -0.232 | 0.533 / 0.337 | 0.531 / 0.085 | 0.245 / 0.108 | — |
| variant_stricter_calibration | -1.300 | 0.008 | -1.349 | -0.734 | 0.567 / 0.110 | 0.533 / 0.000 | 0.249 / 0.004 | — |
| weaker_token_budget | -1.657 | 0.011 | -1.686 | -1.218 | 0.560 / 0.000 | 0.533 / 0.000 | 0.250 / 0.000 | — |
| full_budget | -1.657 | 0.011 | -1.686 | -1.218 | 0.560 / 0.000 | 0.533 / 0.000 | 0.250 / 0.000 | — |
| shortcut_all_defer | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_early_answer | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_fixed_rule | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_ignore_epsilon | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_public_simulator_calibration | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_simfit_hybrid | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_simfit_naive | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_simfit_ucb | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_stop_on_repeat | -3.078 | — | -2.741 | — | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| naive_calibration | -3.527 | — | -2.741 | +0.088 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |

Before (gym as of the start of this iteration):

| probe | rank Q before | risk_control acc / savings / violation | failed |
|---|---:|---|---|
| shortcut_read_hidden | +1.838 | 0.556 / 0.791 / 0.000 | — |
| shortcut_simfit_cautious | -0.009 | 0.498 / 0.350 / 0.000 | — |
| shortcut_simfit_hybrid | +0.522 | 0.496 / 0.408 / 0.033 | — |
| shortcut_simfit_naive | -2.921 | 0.000 / 0.000 / 1.000 | adaptive_budget_efficiency, difficulty_mix_1_1, difficulty_mix_1_3, difficulty_mix_3_1, risk_control |
| shortcut_simfit_ucb | +0.530 | 0.493 / 0.411 / 0.100 | — |
