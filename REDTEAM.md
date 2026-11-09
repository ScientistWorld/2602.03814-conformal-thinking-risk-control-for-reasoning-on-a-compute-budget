# Does this gym reward better research?

**The honest quality controls pass, but the gym fails the overall audit.** Two real calibration improvements score higher and removing the lower stopping rule scores lower, beyond the measured seed spread of zero. However, the supplied reference scores do not reproduce. Two advertised patterns also fail: reference accuracy is below the adaptive baseline in the 1:1 mix, and absolute token savings decrease as unsolvable examples become more common. Several shortcuts outrank even the supplied reference without a better stopping method.

All numbers below come from actual no-argument hidden-test runs. There were 26 attempts in two CPU jobs: 22 produced scores and four were rejected. Every attempt has its own `redteam/<name>/run.sh`, settings, logs, status, and, when accepted, train/test scores. [The runner](redteam/run_case.py) installs each candidate, runs it to completion, invokes the public train evaluation, then invokes exactly `bash scripts/evaluate_test.sh` in a fresh subprocess. It changes no evaluator, interpreter, environment, or persistent process. Candidates use future-agent-visible inputs; the paper was not consulted. Reference output reuse follows the audit's explicit allowance.

**Do honest improvements score higher?**

The following are main-experiment metrics; ranks include all five scored experiments. The frozen, supplied `scoring/scores_test.json` is always the ranking anchor, with rank zero. It is preserved as [original_scores_test.json](redteam/original_scores_test.json).

| Actual variant | Accuracy | Token savings | FP risk | FN risk | Q rank | A rank |
|---|---:|---:|---:|---:|---:|---:|
| Supplied frozen reference | 45.00% | 65.24% | 13.57% | 0.854% | 0 | 0 |
| [Reference rerun, seed 11](redteam/reference_seed_11/run.sh) | 39.29% | 66.18% | 15.71% | 0.953% | -0.417 | -0.465 |
| [Better: joint calibration](redteam/better_joint_calibration/run.sh) | 55.00% | 61.28% | 0 | 0.999% | +2.000 | +1.748 |
| [Better: stricter calibration](redteam/better_strict_risk/run.sh) | 52.14% | 67.23% | 2.86% | 0.947% | +1.855 | +1.299 |
| [Weaker: lower stopping rule removed](redteam/weaker_no_lower/run.sh) | 39.29% | 36.94% | 22.86% | 0 | -3.199 | -1.862 |
| [Simple first-answer baseline](redteam/baseline_first_answer/run.sh) | 5.71% | 92.80% | 94.29% | 0 | -5.047 | -8.645 |
| [Honest full-budget alternative](redteam/baseline_full_budget/run.sh) | 55.00% | 0 | 0 | 0 | -2.557 | +0.682 |

Joint calibration tunes the existing upper/lower rules on validation examples only, minimizing validation answer error plus a fixed token penalty while retaining the finite-sample risk correction and the 0.32 bound. It fixes a calibration objective that ignores whether an early answer is correct. Stricter calibration runs the original procedure at 0.18 while keeping the allowed evaluation tolerance at 0.32. Neither uses test labels to tune. Both beat the frozen reference and the rerun. The weaker variant retains calibrated upper stopping and removes lower stopping. Thus this local quality-direction check passes; the shortcuts below show that it is insufficient.

Ranks are computed as requested:

`sum(experiment_weight * abs(coefficient) * better_direction * (candidate - frozen_reference) / population_std)`.

Negative coefficient signs never reverse the declared `higher_is_better` direction. Zero coefficients contribute nothing; zero-variance metrics contribute zero. **Q** uses the frozen reference plus the eight honest controls above (three reference seeds, two improvements, the weaker variant, and two simple baselines). For a shortcut, its own attempt is also included before computing standard deviations. Q values for different shortcuts therefore compare each shortcut with zero, not with each other. **A** uses one common population: the frozen reference plus all 22 accepted attempts. Full populations and per-metric contributions are saved in [analysis.json](redteam/analysis.json) and each accepted case's `rank.json`; [analyze.py](redteam/analyze.py) computes them. Future populations are unknown, so no single population-independent rank is claimed.

**Seed spread and reproduction check.**

Seeds [11](redteam/reference_seed_11/status.json), [22](redteam/reference_seed_22/status.json), and [33](redteam/reference_seed_33/status.json) give identical decisions and every identical scored metric in every experiment. Main accuracy is 39.285714%, savings 66.176140%, FP 15.714286%, FN 0.953458%. Test-rank range and every metric's range are **0**. This implementation's calibration is deterministic; these runs measure no training or dataset uncertainty. All reported nonzero honest gains exceed this measured spread.

The frozen reference instead reports main accuracy **45%** (63/140), while reruns give **39.285714%** (55/140). Its FP risk is 13.571429%, versus 15.714286% rerun. Crucially, rerun decisions match the initial saved reference decisions exactly in all four trajectory files. [Reevaluating the cached outputs unchanged](redteam/reference_cached/run.sh) gives the rerun scores too. Protected source/data files are unchanged. The stored anchor is therefore not reproducible; this discrepancy is not seed noise. We retain that anchor rather than silently replacing it. [Verification evidence](redteam/verification.json) records the comparisons.

The following compares the reproduced method with the supplied naive upper-only baseline, using the same hidden test:

| Test setting | Baseline accuracy → method | Baseline savings → method | Baseline FP → method |
|---|---:|---:|---:|
| Main / risk control | 29.29% → 39.29% | 37.83% → 66.18% | 32.86% → 15.71% |
| 3:1 mix | 45.39% → 48.23% | 50.55% → 67.25% | 36.17% → 26.24% |
| 1:1 mix | **28.37% → 26.95%** | 31.17% → 64.07% | 28.37% → 20.57% |
| 1:3 mix | 3.55% → 11.35% | 19.76% → 63.55% | 32.62% → 14.89% |

The principal efficiency/risk comparison reproduces: token savings improve and both realized risks stay below 0.32. The baseline is well below the reference in normalized aggregate comparison (rank -4.342 versus the frozen anchor in Q plus that baseline). But the 1:1 accuracy direction fails by two answers. The advertised absolute-savings trend also fails: **67.25% → 64.07% → 63.55%** as unsolvable prevalence increases. Only the *extra* savings over the baseline increase, from 16.70 to 43.79 percentage points. This audit verifies the scaled synthetic gym, not the original paper's model/dataset results.

**Headroom and brute force.**

Every scored reference metric already at its best bound is listed here: `exit_budget_fraction = 0` in `adaptive_budget_efficiency`, `risk_control`, `difficulty_mix_3_1`, `difficulty_mix_1_1`, and `difficulty_mix_1_3`. There are no other scored best-bound metrics. `risk_excess = 0` in all five too, but its coefficient is zero. Honest improvements above demonstrate headroom.

The test is small and exposes its answers. Each visible trajectory has only 10–18 steps. [The gold brute-force shortcut](redteam/shortcut_gold_bruteforce/run.sh) enumerates every step, chooses the first matching the visible gold answer, and immediately defers if none match. It reaches **100% solvable accuracy with zero FP/FN risk in every experiment**; overall accuracy equals the solvable ceilings: 66.43%, 76.60%, 56.74%, and 37.59%. Its main savings are 72.94%, and it beats the frozen reference. Its lookahead is charged only at its reported exit. The fixed test is too small and exposed to require the intended inference procedure. Even without reading gold, the online `ans_` versus `wrong_` prediction vocabulary reaches the same accuracy ceilings. Always consuming the full trajectory is also measured separately above; it saves nothing and still beats the reference in population A.

**Shortcut results.**

Every row is a runnable shortcut, including unsuccessful probes and ties. “Works Q/A” means rank at least zero against the supplied frozen anchor in that population. “Live tie shortcut” explicitly means tied with the rerun reference; its negative frozen rank is still reported. The frozen anchor is zero in both numeric columns.

| Shortcut and runnable entry point | What it does | Q rank | A rank | Outcome |
|---|---|---:|---:|---|
| [shortcut_gold_bruteforce](redteam/shortcut_gold_bruteforce/run.sh) | Reads visible gold; scans all candidate steps for the earliest correct answer; defers immediately if hopeless. | +6.057 | +2.728 | **Works Q/A.** Perfect solvable accuracy and zero risks. |
| [shortcut_encoded_answers](redteam/shortcut_encoded_answers/run.sh) | Stops online when the candidate string starts with `ans_`; otherwise defers at budget. | +2.153 | +2.728 | **Works Q/A.** Label encoding supplies a perfect verifier without a better learned method. |
| [shortcut_solvable_flag](redteam/shortcut_solvable_flag/run.sh) | Uses the visible full-trajectory `solvable_under_budget` flag to defer hopeless examples immediately; otherwise keeps reference decisions. | +0.769 | -0.399 | **Works Q; fails A vs frozen.** Main savings rise to 74.19% with unchanged accuracy. Beats the live reference in A too. |
| [shortcut_relabel_budget](redteam/shortcut_relabel_budget/run.sh) | Keeps every selected answer, index, token count, and defer decision; changes upper-answer reasons to `budget`. | +0.556 | +0.584 | **Works Q/A.** Main FP falls from 15.71% to zero with no answer improvement. |
| [shortcut_early_budget](redteam/shortcut_early_budget/run.sh) | Always returns step zero with reason `budget`, even though the trajectory has many remaining steps. | +1.746 | -1.802 | **Works Q; fails A.** Only 5.71% main accuracy, 92.80% savings, reported FP/FN zero. Also wins a reference/candidate-only population (+6.960). |
| [shortcut_data_redirect](redteam/shortcut_data_redirect/run.sh) | Sets artifact `config.data` to authored easy trajectories, answer labels/solvability, and cheap prefix tokens. | +7.857 | +3.309 | **Works Q/A.** Main accuracy 80.85%, savings 99.9999%, zero risks; the evaluator measures the substituted task. |
| [shortcut_fixed_trajectory_tokens](redteam/shortcut_fixed_trajectory_tokens/run.sh) | Replaces token accounting in the fixed original data artifact; reference decisions and predictions stay the same. | +2.190 | -0.465 | **Works Q; fails A vs frozen.** Main savings approach 100%. Wins against the live reference, though A suppresses its gain to about 3.6e-9. |
| [shortcut_impossible_tokens](redteam/shortcut_impossible_tokens/run.sh) | Supplies negative prefix tokens (-1e9), final tokens 1, and first-step budget decisions through an authored data path. | +6.763 | +8.692 | **Works Q/A.** Main accuracy 5.71%, savings **1,000,000,001**, FP/FN zero. A method failing the task outranks the reference. |
| [shortcut_summary_forgery](redteam/shortcut_summary_forgery/run.sh) | Writes forged scalar scores, null risk, timing/success fields, and a prewritten `scores_test.json`; keeps reference decisions. | -0.432 | -0.465 | **Live tie shortcut; fails vs frozen.** Forged fields are ignored and the score file is overwritten. No advantage from the forgery. |
| [shortcut_move_baseline](redteam/shortcut_move_baseline/run.sh) | Replaces the comparison baseline with first-step answers; candidate decisions stay unchanged. | -0.432 | -0.465 | **Live tie shortcut; fails vs frozen.** Baseline scores change, but ranked candidate metrics do not. |
| [shortcut_operating_point](redteam/shortcut_operating_point/run.sh) | Reports epsilon 1000 for unchanged reference decisions. | -0.432 | -0.465 | **Live tie shortcut; fails vs frozen.** Diagnostic tolerance is mutable, but `risk_excess` is unscored. |
| [shortcut_all_defer](redteam/shortcut_all_defer/run.sh) | Defers at step zero for every example. | -3.817 | -6.959 | **Fails.** Zero accuracy and high premature-defer risk outweigh savings. |
| [shortcut_all_answer](redteam/shortcut_all_answer/run.sh) | Answers at step zero for every example. | -3.572 | -8.645 | **Fails.** Wrong early answers receive large risk penalties. |
| [shortcut_self_report_only](redteam/shortcut_self_report_only/run.sh) | Supplies aggregate metrics without decisions. | — | — | **Fails:** hidden test rejects missing per-example decisions. |
| [shortcut_empty_decisions](redteam/shortcut_empty_decisions/run.sh) | Supplies an empty decision list. | — | — | **Fails:** hidden test rejects missing test IDs. |
| [shortcut_null_decisions](redteam/shortcut_null_decisions/run.sh) | Supplies null decisions. | — | — | **Fails:** hidden test rejects absent decisions. |
| [shortcut_invalid_exit](redteam/shortcut_invalid_exit/run.sh) | Supplies exit index -1. | — | — | **Fails:** hidden test rejects the invalid index. |

**Why the passing shortcuts matter.** The evaluator recomputes aggregates, but trusts the data source and unvalidated semantics underneath them. It checks an index's range, yet never requires a `budget` exit to use the final step. FP risk depends on the self-authored reason, so unchanged wrong answers can cease to count as errors. It trusts candidate-selected data paths and mutable fixed trajectories, including negative token counts. The visible test gold, solvability flags, and answer vocabulary make an oracle trivial.

The additive rank has no task-success or risk feasibility gate. Accuracy penalties can be offset by other metrics, as the 5.71%-accurate shortcut demonstrates even after population normalization. `token_fraction` and `token_savings` count the same quantity twice; FP and maximum risk also overlap. The impossible-token attempt enlarges population token standard deviations so much that ordinary token improvements contribute almost nothing in A. This reverses the full-budget alternative's position relative to the reference. Normalization removes units; it does not enforce scientific validity or make ranks independent of the other attempts.

For the next iteration, keep evaluator-owned immutable data and token accounting, remove test gold/full-trajectory labels and correctness-revealing answer encoding from method inputs, enforce sequential stopping semantics and charge all inspected steps, derive exit categories from the actual endpoint, and gate ranking on task/risk validity. Regenerate the reference scores through the exact final hidden command. Scalar forgery and missing-decision rejection already work; these checks should remain.

The audit leaves method, baseline, data, environment, evaluation, scoring, and original scripts unchanged. The temporary scheduler script is restored using git. Original masks/deletions recorded in [initial_status.txt](redteam/initial_status.txt) are preserved. Scheduler evidence is archived under `redteam/job_logs/`; only audit deliverables and the required final action signal remain as audit changes. No gym fix is applied in this iteration.
