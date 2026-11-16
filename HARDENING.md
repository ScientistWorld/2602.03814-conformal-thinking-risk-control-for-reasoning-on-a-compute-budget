# Hardening report (round 2)

The first round (report kept in `redteam/hardening/HARDENING_round1.md`) rebuilt the gym as a hidden, online test. REVIEW.md found two remaining weaknesses:

1. The signal-ensemble claim (paper Fig. 5) was not exercised. Confidence-only tied the reference (+0.020) because the alternative signals were noisier copies of confidence.
2. Fitting the public simulator to the calibration set and calibrating on simulated samples had not been measured at small n.

This round fixes both. It also fixes three items from the checklist:

- a wall-clock kill in the method's path;
- a hidden generator that running policies could read;
- a departure of the reference from the paper's Sec. 4.4.

Everything was checked in one audit job (`redteam/hardening2/`). That job was preempted twice and resumed. Its first, preempted attempt had already produced a full hidden-test audit, which is byte-identical to the final one (`attempt1_scores_test_all.json`).

**Result.**

- **Ranking.** Better methods score higher and weaker ones lower, by 55–130× the paired test noise. The reference sits at 0, with clear headroom above it.
- **Ensemble claim.** It is now measured: confidence-only scores −0.370 and EAT-only −0.366 (paired SE 0.005).
- **Simulator-fit shortcut.** It paid before (+0.530, above the honest KL-bound variant's +0.422). Now it fails the risk gate in every form. Its cautious best response scores −0.126, below the reference.
- **Reading the hidden generator.** It paid +1.838 before and now scores exactly the reference.
- **Other shortcuts.** No shortcut outranks the reference.

## What changed

| Problem | Fix |
|---|---|
| **Signals did not disagree.** `eat_confidence` was confidence plus noise, so selecting a signal (Alg. 1 over signals; Fig. 1 right, Fig. 5) could not help. | **New trajectory process** (`data/generate_synthetic_reasoning.py`, and its own copy in `eval/test/hidden_tasks.py`). Each signal channel has its own lag after the answer becomes correct, its own noise level (Student-t, autocorrelated), its own per-question bias and its own susceptibility to falsely confident runs. Profiles fall into regimes: confidence reliable; EAT reliable; or confidence fast but fooled while EAT is slow but robust. In the last regime the better signal depends on ε. Every profile group contains each regime, on both train and test. |
| **The lower threshold needs visible progress.** The paper's lower threshold stops runs that are "not making progress" (Fig. 2). | **Pre-solve progress.** Solvable runs show partial progress before the answer becomes correct, plus a small per-question ease lift. Hopeless runs stay flat, wander, or become falsely confident late. Muted and late-signalling solvable runs keep false-negative risk real. Chunk lengths now vary. `token_fraction` is now `tokens / budget_tokens`, matching its name. |
| **Simulator fit paid at n=50.** The held-out profiles came from the same documented ranges as the public generator. Approximate-Bayesian matching of the calibration set to that family, followed by calibration on 1500 simulated runs, beat the honest methods. | **Broader, unpublished held-out process.** The held-out generator draws from wider private ranges with randomly shaped rise curves. It adds behaviours absent from the public generator: (a) brief confident intermediate mistakes, i.e. a one- or two-chunk signal spike on a wrong answer, seen by each channel with a regime-dependent probability; (b) silent late solvers, which show no progress and then solve late; (c) runs that reach the correct answer and later abandon it; (d) noise that grows over the run. The public generator no longer publishes held-out ranges. The docs state that the held-out process is broader and not described by it. It has a new secret. |
| **Hidden generator readable at test time.** A policy subprocess could import `eval/test/hidden_tasks.py`, regenerate the test set and answer at the first correct chunk. That paid +1.838. | **Sealed while policies run.** Held-out tasks are built in the evaluator's memory. Before any policy starts, `hidden_tasks.py` is set to mode 000 and stale bytecode is deleted (no bytecode is written). Permissions are restored after every policy has exited, and on the next evaluator start if a run was killed. |
| **Wall-clock limit in the method's path.** A 3-hour per-process timer made scores load-dependent in principle. | **CPU-time limits (both evaluators).** Each policy process gets 3600 CPU s, set through an exec shim rather than `preexec_fn`, which is unsafe with threads. A no-progress detector stops only a process whose reply is pending and whose process tree uses no CPU for 30 minutes. Core dumps are disabled for policy processes. A sleeper and a spinner were both verified to become protocol failures. The core-dump setting was added after the audit job; it changes no score, since no audited policy came near the limits. |
| **Reference departed from Sec. 4.4.** The upper threshold's signal was selected by Alg. 1, but the lower threshold always used confidence, scaled by a threshold on another signal's scale. | **Lower threshold on the selected signal.** Sec. 4.4 calibrates both thresholds "given a signal s", so the lower threshold now uses the signal selected for the upper one. It falls back to confidence when the upper exit is disabled or is the token count. A vectorised re-implementation (`fast_reference`) reproduces the reference's selections exactly on every audited operating point. |

Unchanged: the interface, the five experiments, their ε grids, the gate, and the weights and coefficients.

## Do better results score higher?

**How the ranks are computed.**

- **Formula:** Σ weight × |coefficient| × direction × (candidate − reference) / population std, using `scoring/reference.json`.
- **Population Q:** the reference, the baselines and the honest variants, plus the candidate itself.
- **Paired SE:** held-out instances are the sampling unit, and every method sees the same instances.
- **Train rank:** the same rank on the visible profiles.
- **"Before":** the round-1 audit on the previous trajectory process.

| Candidate | Before (rank Q) | **After: rank Q** | paired SE | train rank |
|---|---:|---:|---:|---:|
| Joint calibration + KL tail bound | +0.993 | **+1.039** | 0.008 | +0.494 |
| Joint search over (signal, upper, lower) (Sec. 4.4 remark) | +0.544 | **+0.536** | 0.007 | +0.274 |
| KL (relative-entropy) tail bound instead of the Hoeffding margin | +0.422 | **+0.533** | 0.005 | +0.160 |
| Reference (`conformal_thinking`); `fast_reference` identical | 0 | 0 | 0 | 0 |
| Upper threshold only (baseline) | −0.480 | **−0.337** | 0.006 | −0.231 |
| EAT-only signal set (no ensemble) | — | **−0.366** | 0.005 | −0.417 |
| Confidence-only signal set (no ensemble) | **+0.020** | **−0.370** | 0.005 | −0.232 |
| Stricter calibration (ε/2) | −1.081 | −1.300 | 0.008 | −0.734 |
| Uniform token budget / full budget | −1.471 | −1.657 | 0.011 | −1.218 |
| Naive calibration (no finite-sample correction) | failed | **failed** (−3.527) | — | +0.088 (passes at the gate boundary, see limitations) |

**Paired differences against the reference, per experiment.** Each entry is the token-savings difference, with the accuracy difference in brackets. The SE of each savings difference is 0.001–0.002.

| Experiment | KL bound | Joint + KL | Confidence-only |
|---|---:|---:|---:|
| main | +0.051 (−0.014) | +0.112 (+0.002) | −0.105 (+0.023) |
| risk_control | +0.096 (−0.015) | +0.177 (−0.053) | −0.023 |
| 3:1 | +0.050 (−0.020) | +0.087 (−0.006) | −0.086 |
| 1:1 | +0.077 (−0.018) | +0.133 (+0.003) | −0.095 |
| 1:3 | +0.151 (−0.014) | +0.302 (−0.046) | −0.058 |

Ordering on train matches test for every honest candidate except the two single-signal ablations, which swap places; both stay below the reference.

## The paper's claims on the hidden test

These numbers come from the reference and baselines run alone (`scoring/scores_test.json`).

| Experiment | full budget acc | upper-only acc / savings | **reference acc / savings** | reference unsolvable savings (upper-only) | violation rate |
|---|---:|---:|---:|---:|---:|
| adaptive_budget_efficiency | 0.560 | 0.556 / 0.320 | **0.510 / 0.441** | 0.34 (0.09) | 0 |
| risk_control (n = 50) | 0.533 | 0.529 / 0.109 | **0.529 / 0.109** | 0.03 (0.03) | 0 |
| difficulty_mix_3_1 | 0.750 | 0.734 / 0.399 | **0.693 / 0.456** | 0.32 (0.12) | 0 |
| difficulty_mix_1_1 | 0.500 | 0.498 / 0.276 | **0.456 / 0.405** | 0.31 (0.07) | 0 |
| difficulty_mix_1_3 | 0.250 | 0.249 / 0.079 | **0.240 / 0.166** | 0.13 (0.02) | 0 |

- **The lower threshold saves more as unsolvable instances become common.** Lower + upper beats upper-only by +0.057 (3:1), +0.121 (natural) and +0.129 (1:1) at matched ε. The 1:3 mix, at tighter ε, gains +0.087 while upper-only collapses to 0.079. The savings come from unsolvable instances.
- **The signal ensemble saves more than any single signal**, in every experiment. Savings are 0.441 vs 0.337 / 0.324 (main), 0.109 vs 0.085 / 0.092, 0.456 vs 0.371 / 0.378, 0.405 vs 0.310 / 0.307, and 0.166 vs 0.108 / 0.142 (reference vs confidence-only / EAT-only).
- **Finite-sample correction controls risk; naive tuning does not, and the gap is largest with small validation sets (Fig. 7).** UCB never exceeds ε. Naive calibration stays within the gate in the four experiments with 400 calibration examples, but exceeds ε at 37.5% of `risk_control` operating points (n = 50; FP 0.114, FN 0.065) and so fails.

## Shortcuts: fix and score before → after

All rows are Q ranks through `bash scripts/evaluate_test.sh`. "Failed" means the gate fired and the run carries the failure values everywhere (−3.078).

| Shortcut | Fix | Before | After |
|---|---|---:|---:|
| `simfit_ucb`: approximate-Bayesian fit of the public simulator to the calibration set; Alg. 1 with Hoeffding margin on 1500 simulated runs | broader unpublished held-out process | **+0.530**: risk_control savings 0.411 vs reference 0.200 and KL 0.366, violation rate 0.10, passes | **failed**: violations 0.40 in risk_control, 0.19 in 3:1 |
| `simfit_hybrid`: as above, plus requires the supplied set's raw risk ≤ ε | same | **+0.522** | **failed**: 0.183 in risk_control |
| `simfit_naive`: no margin on the simulated set | same | failed | failed |
| `simfit_cautious`: the hybrid at 0.7 ε, the natural best response | same | −0.009 | **−0.126**: risk_control 0.497 / 0.199 vs KL 0.513 / 0.205; 1:3 savings 0.063 |
| `read_hidden`: import `eval/test/hidden_tasks.py` at test time, regenerate the test set, answer at the first correct chunk | generator sealed while policies run | **+1.838**: savings 0.79 at full-budget accuracy, zero risk | **0.000**: gets `PermissionError`, falls back to the reference |
| `public_simulator_calibration`: calibrate on 3000 public-profile runs | broader held-out process | failed | failed (violations 0.61–0.67) |
| `fixed_rule`: hand-written thresholds on max(confidence, EAT) | (new probe) | — | failed (risk_control 0.33, 1:3 0.44) |
| `ignore_epsilon`, `stop_on_repeat`, `early_answer`, `all_defer` | rechecked on the new process | failed | failed |

Round-1 probes that depend only on the protocol were not replayed: manifest overrides, self-labelled budget exits, gold lookup in visible files, and cross-operating-point memory or pooling. The protocol is unchanged.

## Shortcuts left open

- **Undoing the seal.** The seal is a permission change by the same user. A policy that chmods the file back, or reads the generator out of `.git` objects where those are present, is deliberate tampering. That is forbidden in `CONSTRAINTS.md` and left to the grader.
- **Persisting state through disk across operating points.** Unchanged from round 1; forbidden and left to the grader.
- **Stronger hand-built models of the held-out process.** The measured fits (four variants, including the cautious best response) do not pay. A better parametric model of behaviours the public generator does not show is not measured. Writing such a model would require knowledge of the held-out process that is not published.
- **Within-pass transduction** over unlabelled held-out chunks. Minor and arguably legitimate; unchanged.

## Reference score before → after

These are not comparable, because the trajectory process changed. The previous values are kept in `scoring/reference.json` under `_hardening1_values_previous_process`.

| Experiment | Before (acc / savings) | After (acc / savings) |
|---|---:|---:|
| main | 0.487 / 0.453 | 0.510 / 0.441 |
| risk_control | 0.532 / 0.200 | 0.529 / 0.109 |
| 3:1 | 0.654 / 0.499 | 0.693 / 0.456 |
| 1:1 | 0.415 / 0.489 | 0.456 / 0.405 |
| 1:3 | 0.223 / 0.274 | 0.240 / 0.166 |

The new reference is deterministic. Three runs produced identical scores: the reference-only run, the audit run, and the preempted first attempt.

## Headroom check

- **No scored metric is at its bound for the reference.** Accuracy is below the full-budget ceiling. Savings range from 0.109 to 0.456.
- **Three honest variants beat the reference** by 0.53–1.04 in rank, with SE ≤ 0.008. The best one saves 0.553 (main), 0.285 (risk_control) and 0.467 (1:3), so none reaches a bound.
- **The small-calibration experiment remains where the paper's method falls short.** At n = 50 on held-out profiles, the reference's lower exit is never feasible: Hoeffding's margin of 0.152 consumes most of the tolerance. Its savings equal upper-only's, which leaves room for tighter finite-sample bounds.
- **Brute force does not apply**, because the test is hidden and online.
- **Simple baselines sit clearly below the reference:** upper-only −0.337, full budget −1.657.

## Validation fix (after the audit)

`validate.py` compares every score file, train included, with `reference.json` `results`. Those results hold this gym's own hidden-test reference values, because the paper reports only curves. Two entries were not comparable across splits:

- **Naive calibration.** Its scored values are a gate outcome: the failure values on the hidden test, but a boundary pass on train. Its `results` entries now carry only the type. Its measured train and test values are kept under `_naive_calibration_measured` in each experiment.
- **`risk_control` primary metric.** The declared primary metric is now `violation_rate`. That is the quantity the paper's risk-control experiment measures (Sec. 5.2, Fig. 4 and 7): realized risk against ε across validation draws. Scoring is unchanged: `token_savings` 1.0, `accuracy` 0.5, risks gated.

No measured number changed.

I also tried fixing the setup itself. I gave the public profiles milder versions of the confident intermediate mistakes and silent late solvers. Locally this brought train `risk_control` savings to about 0.18 and made naive calibration fail on train too. I reverted it, because the change could not be scored and re-audited against the simulator-fit attack in a job during validation. The train/test gap therefore remains, as listed below.

## Weights and coefficients

Unchanged: experiment weights 0.3 / 0.2 / 0.15 / 0.15 / 0.2; `token_savings` 1.0; `accuracy` 0.5. Risks remain gated constraints. The ensemble claim is exercised inside every experiment, so it needs no separate weight.

## Not fixed / limitations

- **Synthetic data.** The benchmark simulates trajectories rather than running Qwen3 or R1 on AIME, GPQA, DeepScaleR or MathVision. The paper's probe signal is not modelled. Results are curves in the paper; `results` holds this gym's own reference runs.
- **The test is harder than train at small n.** In `risk_control` the reference saves 0.219 on train vs 0.109 on test, because the held-out-only behaviours add risk. The fix is to give the public profiles milder versions of these behaviours; it was tested locally but not applied (see "Validation fix"). The other experiments are within 0.03–0.06 of each other. Honest candidates keep the same order on both sides, except the two single-signal ablations, which swap places below the reference.
- **Naive calibration passes the gate on train at the boundary.** It violates at exactly 15% of `risk_control` operating points (the gate is "> 15%"), versus 0% for the reference. On test it fails clearly (37.5%). The paper's direction holds on both sides; only the pass/fail outcome differs.
- **The 1:3 mix uses tighter tolerances** (≤ 0.125), as in round 1. Deferring every instance at the first chunk has a false-negative risk of 0.187 there.
- **Population dependence of the rank** is as in round 1. Failed runs widen the population std; the gate keeps them below every valid run.

## Evidence

`redteam/hardening2/` holds:

- `variants.py`: every candidate, the vectorised Alg. 1, and the simulator-fit attack with its bank builder;
- `run_audit.sh`: the resumable driver;
- `analyze.py` and `merge_scores.py`;
- `scores_test_all.json`, `scores_train_all.json` and `old_gym_scores_test.json`;
- `reference_only_scores_{test,train}.json`, `analysis.json` (ranks, contributions, paired noise) and `summary.md`;
- `old_public_generator.py` and `old_conformal_thinking.py`, the previous gym's public code used for the "before" runs. The previous hidden test is rebuilt from commit 6090d6e.
