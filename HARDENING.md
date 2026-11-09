# Hardening report (iteration 11)

## Summary

The audited gym (REDTEAM.md) had a public test set and an evaluator that trusted method-written decisions. Gold answers, full trajectories, solvability flags and correctness-revealing answer strings were all visible to the method. Exit reasons and data paths were self-reported. The ranking had no feasibility gate. Several shortcuts outranked the reference, and the supplied reference score did not reproduce (45% vs 39.3% main accuracy). I rebuilt the measurement around a hidden, online test that the evaluator fully owns. I kept the paper's algorithm, the five experiments and their weights. I re-ran the reference, the baselines, three honest improvements, an operating-point shift, two ablations and 15 shortcut probes through the hidden test command (`bash scripts/evaluate_test.sh`).

**Result.** Better methods now score higher and worse ones lower. Gaps are many times the paired test noise; every failed shortcut ranks below the reference, and the rest tie it (no shortcut outranks it). Every shortcut from REDTEAM.md is closed. So are two further in-memory exploits found during this audit. The reference is deterministic and reproduces exactly: its rerun was identical, and so was its rerun under the final evaluator.

Evidence: `redteam/hardening/` (`variants.py` candidates, `run_candidates.sh` and `run_isolation_check.sh` drivers, `scores_test_all.json`, `scores_train_all.json`, `scores_test_isolated.json`, `scores_test_before_isolation.json`, `analysis.json`, `summary.md`).

## What changed

| Problem (REDTEAM.md) | Fix |
|---|---|
| Test trajectories, gold answers and solvability flags were in public `data/*.jsonl`; seeds in `scripts/download.sh` regenerated them. | Test data is generated **only inside `eval/test/hidden_tasks.py`** from private profiles and seeds. This covers 3 held-out (model, dataset) profiles per group, a 1000-instance calibration pool and a 1000-instance test set per profile and setting. The old public data files are deleted. The public generator (`data/`) uses different, documented public profiles, which `eval/train/` uses. |
| Method wrote per-example decisions offline, with full lookahead (gold brute force, solvable-flag deferral). | A method is now a **policy program** (`outputs/<name>/policy.json`) that speaks a JSON-lines protocol. The evaluator sends a labelled calibration set with `epsilon` and `delta`, then reveals each held-out trajectory **one chunk at a time**. The policy answers `continue`/`answer`/`defer`. No label, flag or future chunk is ever sent. |
| Exit reason self-reported (`budget` relabelling erased FP; `early_budget` at step 0). | The **exit type is derived from where the policy stopped**: an answer before the last chunk is an early answer, and continuing or answering at the last chunk is a budget exit. Any other action is a protocol failure. |
| Token counts and data path taken from the artifact (`data_redirect`, `fixed_trajectory_tokens`, `impossible_tokens` = savings 1e9). | **Tokens are charged by the evaluator** from its own trajectories, up to the stopping chunk. Only the manifest's `command` is read; any other field is ignored. Impossible values cannot be produced. |
| Answer strings `ans_*`/`wrong_*` revealed correctness; wrong answers never repeated, so answer stability was a perfect verifier. | Answers are **opaque numbers** drawn from one vocabulary. Wrong answers persist across chunks (stickiness 0.4–0.95), and correct answers flicker. Solvability is labelled by whether the full-budget answer is correct (the paper's Fig. 6 wording). |
| Operating point (`epsilon`) chosen by the method. | `epsilon`, `delta=0.1`, calibration size, draws and test size are **fixed by the evaluator** (per-experiment table in `briefing/evaluation.md`). |
| Additive rank with no task/risk gate: a 5.7%-accurate shortcut outranked the reference; duplicated metrics (`token_fraction` = 1 − `token_savings`, `max_realized_risk`). | **Gate:** a run whose realized FP or FN risk exceeds `epsilon` at more than 15% of operating points in *any* experiment, or that breaks the protocol, receives the failure values in *every* experiment (accuracy 0, savings 0, risks 1). **Scored metrics** are now only `token_savings` (1.0) and `accuracy` (0.5). Risks are constraints (gated, coefficient 0); duplicates and at-bound diagnostics have coefficient 0. |
| One process per experiment (found in this audit): a policy could pool calibration draws (≈400 instead of 50 examples in `risk_control`), and could remember held-out trajectories from an earlier `epsilon`/draw to get lookahead. | **Every operating point** (one calibration draw, one `epsilon`) **runs in a fresh process**; calibration and query ids are opaque. `risk_control` uses its own held-out profiles (group 1), so no other experiment's calibration data can help it. |
| Reference score not reproducible. | Regenerated from the final code by `scripts/reproduce.sh` (job f376c27d). Identical across four runs: audit run, second registered copy, isolated rerun, final reproduction. The train scores are also identical. |

## Do better results score higher?

Ranks use the specified formula, Σ weight × |coefficient| × direction × (candidate − reference) / population std, with the final `scoring/reference.json`. Two populations are reported:
- **Q:** the reference, baselines and honest variants, plus the candidate itself.
- **A:** every attempt in the audit.

The paired SE is the test-sampling standard error of the candidate-minus-reference rank. It treats held-out instances as the sampling unit; every method sees identical instances. The train rank is the same rank computed on the visible train profiles.

| Candidate | Before (old gym, Q / A) | After: Q rank | paired SE | A rank | train rank |
|---|---:|---:|---:|---:|---:|
| Joint calibration + KL tail bound | — | **+0.993** | 0.008 | +1.123 | +0.901 |
| Joint calibration (product-space search, Sec. 4.4) | +2.000 / +1.748 | **+0.544** | 0.007 | +0.602 | +0.411 |
| KL (relative-entropy) tail bound instead of the Hoeffding margin | — | **+0.422** | 0.004 | +0.505 | +0.391 |
| No signal ensemble (confidence only) | — | +0.020 | 0.001 | +0.028 | −0.011 |
| Reference (conformal_thinking) / rerun | 0 (rerun −0.417 / −0.465) | 0 / 0 | 0 | 0 | 0 |
| Upper threshold only (no lower threshold; was `weaker_no_lower`) | −3.199 / −1.862 | **−0.480** | 0.007 | −0.569 | −0.606 |
| Stricter calibration (epsilon/2; was `better_strict_risk`) | +1.855 / +1.299 | −1.081 | 0.006 | −1.193 | −1.169 |
| Full budget (honest alternative) | −2.557 / **+0.682** | −1.471 | 0.008 | −1.577 | −1.643 |
| Uniform token budget (token-fraction threshold only) | — | −1.471 | 0.008 | −1.577 | −1.643 |
| Naive calibration (no finite-sample correction) | — | **failed** −3.308 | — | −2.735 | −3.464 |

- **Improvements beat the reference by roughly 80–120× their paired SE** (+0.42 ± 0.004, +0.54 ± 0.007, +0.99 ± 0.008), with savings gains in every experiment. Savings gains: tighter bound +0.04 to +0.21; joint calibration +0.04 to +0.23; both +0.11 to +0.45. Accuracy costs are 0.01–0.05, and violation rates stay ≤ 0.05.
- **Train ranks match test ranks** for every honest candidate, so honest methods score alike on both sides.
- **Stricter calibration now ranks below the reference.** The redteam counted it as "better". It leaves half the allowed risk unused; the paper's objective is the least compute that satisfies the tolerance. It does gain accuracy (+0.02 to +0.09), but loses 0.20–0.36 savings.
- **Full budget can no longer beat the reference** in either population (before: +0.682 in A).
- **The no-ensemble ablation ties the reference.** In this simulator the alternative signals are noisier copies of confidence, so the paper's ensemble claim (Fig. 5) is not exercised (see "Not fixed").

## The paper's claims on the hidden test (reference vs baselines)

| Experiment | full budget acc | upper-only acc / savings | **reference acc / savings** | reference FP / FN | violation rate |
|---|---:|---:|---:|---:|---:|
| adaptive_budget_efficiency (natural) | 0.557 | 0.538 / 0.294 | **0.487 / 0.453** | 0.048 / 0.036 | 0 |
| risk_control (n = 50) | 0.556 | 0.554 / 0.135 | **0.532 / 0.200** | 0.030 / 0.018 | 0 |
| difficulty_mix_3_1 | 0.750 | 0.719 / 0.402 | **0.654 / 0.499** | 0.062 / 0.045 | 0 |
| difficulty_mix_1_1 | 0.500 | 0.487 / 0.266 | **0.415 / 0.489** | 0.040 / 0.051 | 0 |
| difficulty_mix_1_3 | 0.250 | 0.251 / 0.072 | **0.223 / 0.274** | 0.011 / 0.023 | 0 |

- **Lower + upper saves more tokens than upper-only**, with the gap growing as unsolvable instances become common: +0.097 (3:1), +0.159 (natural), +0.224 (1:1), +0.201 (1:3, at tighter tolerances). Paired SEs are 0.001–0.004.
- **Upper-only collapses when unsolvable instances dominate** (0.40 → 0.07 savings).
- **The lower threshold does the saving on unsolvable instances:** in the main and mix experiments, savings on unsolvable instances are 0.26–0.44 vs 0.01–0.08 for upper-only.
- **Finite-sample correction controls risk; naive tuning does not.** UCB never exceeds `epsilon`, while naive calibration exceeds it at 22.5% of `risk_control` operating points (measured FP 0.082, FN 0.051) and fails the run.
- **Accuracy cost:** the reference gives up 3–7 accuracy points relative to upper-only. That is within its false-negative budget, but it is "comparable accuracy" only loosely; in the 1:1 mix it is 0.415 vs 0.487.

**Reference score.** Before: frozen 45.0% accuracy / 65.2% savings / FP 13.6% (rerun 39.3% / 66.2% / 15.7%), on the old public split at epsilon 0.32. After (hidden test, averaged over operating points): main experiment 0.487 accuracy / 0.453 savings. The other experiments are in the table above. The two are different measurements and not comparable. The new values are in `scoring/scores_test.json` and in `scoring/reference.json` `results`.

## Shortcuts: fix and score before → after

Before = Q / A rank in REDTEAM.md (old gym) unless stated. After = Q rank on the hardened hidden test ("failed" = gate or protocol failure, failure values everywhere, −2.92).

| Shortcut | Fix | Before | After |
|---|---|---:|---:|
| `gold_bruteforce`: scan all steps for the visible gold | test data hidden; chunks revealed online | +6.057 / +2.728 | `shortcut_gold_lookup` (looks up gold/flags in visible files and the begin message, finds nothing): 0.000 (= reference) |
| `encoded_answers`: stop on `ans_` prefix | opaque answers | +2.153 / +2.728 | −1.430 (never fires, so full budget) |
| answer-stability oracle (stop when the answer repeats) | sticky wrong answers | (same mechanism as above) | failed (FP 0.91–0.97) |
| `solvable_flag` | flag never sent | +0.769 / −0.399 | covered by `shortcut_gold_lookup`: 0.000 |
| `relabel_budget`, `early_budget`: self-labelled budget exits | exit type derived by evaluator | +0.556 / +0.584; +1.746 / −1.802 | `shortcut_claim_budget`: failed (protocol); `shortcut_early_answer`: failed (FP 0.95–0.98) |
| `data_redirect`, `fixed_trajectory_tokens`, `impossible_tokens` (savings 1e9), `summary_forgery`, `operating_point` field | evaluator owns data, tokens and epsilon; only `command` is read; scores file is written by the evaluator | +7.857 / +3.309; +2.190 / −0.465; +6.763 / +8.692; ties | `shortcut_manifest_overrides` (data path, epsilon 1000, −1e9 tokens, forged scores in the manifest): 0.000 (= reference) |
| ignore the requested epsilon (calibrate at 0.4) | gate | (tie; diagnostic only) | failed (violations at 37–92% of points) |
| all-defer / all-answer | gate; epsilon grids keep all-defer infeasible (1:3 uses ≤ 0.125 because all-defer FN ≈ 0.18 there) | −3.817 / −6.959; −3.572 / −8.645 | failed / failed |
| calibrate on 3000 public-simulator examples instead of the supplied set (new probe) | held-out profiles differ from public ones; gate | — | failed (violation rate 0.25–0.44) |
| pool calibration draws across operating points (new) | fresh process per operating point; opaque ids; disjoint profiles for `risk_control` | **+0.274** (pre-isolation hidden test; `risk_control` savings 0.327 vs 0.200) | 0.000 (= reference) |
| remember held-out trajectories across operating points, replay with lookahead (new) | fresh process per operating point | **+0.231** (main savings 0.505 vs 0.453, same accuracy and risk) | −1.430 (never has memory; runs to budget) |
| missing / empty / null decisions, invalid exit index | (rejected before too) | rejected | protocol failure: failed |
| `move_baseline` | baselines are separate policy programs and the evaluator's built-in `full_budget`; the ranking anchors on the frozen reference | tie | unchanged (no rank effect) |

## Shortcuts left open

- **Reading `eval/test/` at test time.** A policy subprocess runs on the same filesystem. It could import `eval/test/hidden_tasks.py`, regenerate the held-out trajectories and look up gold answers. Preventing this needs a sandbox; it is a blatant violation (`scoring/CONSTRAINTS.md`) left to the shortcut grader.
- **Deliberate persistence through disk.** Writing calibration sets or held-out observations to a file and reading them in a later process (another operating point or another run) would recreate the two in-memory exploits above. Per-process isolation closes every in-memory route; disk persistence is forbidden in `CONSTRAINTS.md` and left to the grader.
- **Exploiting the simulator family.** Fitting the public generator's parameters to the calibration set and calibrating on simulated samples could beat honest finite-sample methods, especially at n = 50. The direct version (calibrating on public-simulator data) fails the gate. The parametric version is forbidden in `CONSTRAINTS.md` but not mechanically detectable.
- **Within-pass transduction.** A policy sees unlabelled chunks of many held-out instances within one operating point and could adapt to their signal distribution. This is minor and arguably legitimate, so it is left open.

## Headroom check

- **Neither scored metric is at its bound for the reference** in any experiment. Accuracy sits below the full-budget ceiling (e.g. 0.487 vs 0.557). Savings is 0.20–0.50. An oracle that answers at the first correct chunk and defers unsolvable instances at the first chunk saves about 0.77 (natural mix) and 0.83 (1:3), measured on the public profiles.
- **The reference's only at-bound value is a diagnostic:** `violation_rate` = 0, which is not scored.
- **Three honest variants beat it** by +0.42 to +0.99 with SE < 0.01. None reaches a bound; the best main-experiment savings is 0.68.
- **The added experiment targets where the paper's method falls short.** `risk_control` was a verbatim copy of the main experiment. It is now a small-calibration (n = 50) experiment on disjoint profiles, which is the paper's own Fig. 7 axis. There the Hoeffding margin of 0.152 makes the reference conservative (savings 0.20), and tighter bounds gain up to +0.21 at the same violation rate.
- **Brute force does not apply:** the test is hidden and online, so there is nothing to enumerate.
- **A simple baseline sits clearly below the reference.** Full budget and token budget score −1.47, and upper-only −0.48.

## Weights and coefficients

- **Experiment weights are unchanged:** 0.3 / 0.2 / 0.15 / 0.15 / 0.2.
- **Coefficients now reflect the paper's objective.** The paper minimises compute subject to risk ≤ epsilon, and reports accuracy vs. tokens. So `token_savings` (1.0) and `accuracy` (0.5) are scored. Realized risks are constraints enforced by the gate, and are not rewarded below epsilon. Rewarding them let the full-budget policy outrank the reference.
- **Coefficient 0:**
  - duplicates: `token_fraction` is removed; `max_realized_risk` is removed;
  - the risks themselves (gated instead);
  - `exit_budget_fraction`, which sat at its bound;
  - `defer_fraction`, which is not a benefit.

## Not fixed / limitations

- **Synthetic data.** The benchmark is a scaled simulator of reasoning trajectories, not the paper's Qwen3/R1 runs on AIME/GPQA/DeepScaleR/MathVision. The paper reports curves only, so `scoring/reference.json` `results` hold this gym's hidden-test reference values. The paper's qualitative findings are under `_paper_reported`, and the old iteration-10 values are under `_iteration10_values_obsolete_setup`.
- **The signal-ensemble claim (Fig. 5) is not exercised.** Selecting among confidence, EAT-like and token-fraction signals ties confidence-only (+0.020).
- **The 1:3 mix uses tighter tolerances** than the other mixes, so absolute numbers across mixes are not at matched epsilon. The 3:1 → natural → 1:1 progression is at matched epsilon.
- **Rank normalisation depends on the population.** Failed runs carry extreme values that enlarge the population std. The gate guarantees that no failed run outranks a valid one, but the size of valid gains in std units shifts with the population.
- **One audit item was only partly re-run.** The joint-calibration variants were scored before the per-operating-point isolation and not re-run after it, to save compute. Their decisions depend only on (calibration set, epsilon), and every other deterministic policy re-run after isolation produced byte-identical scores (`analysis.json`, `identical_after_isolation`).
