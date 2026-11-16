# Experiment Overview

All experiments score a stopping policy on unseen reasoning trajectories from held-out (model, dataset) profiles. The policy receives labelled calibration data and a target risk level for each operating point, then makes online continue / answer / defer decisions chunk by chunk. Every experiment reports token savings and accuracy (scored) and the realized risks (constraints). A policy that exceeds its target risk too often in any experiment, or breaks the protocol, is scored as failed everywhere.

The profiles differ in which stopping signal is informative, and the held-out profiles come from a broader process than the visible development profiles, so every experiment also measures whether a policy adapts to the (model, dataset) pair from its calibration data rather than relying on the development profiles.

## adaptive_budget_efficiency

The central compute-efficiency question on a natural mix of solvable and unsolvable instances, with a moderately large calibration set. It establishes how many reasoning tokens a policy can save, and how much accuracy it keeps, while its realized risks stay within the requested tolerances.

## risk_control

The reliability question in the small-calibration regime: only 50 labelled examples per draw, ten independent draws per profile, and a sweep of tolerances from strict to loose, on profiles not used by any other experiment. It establishes whether realized risk stays within tolerance across calibration draws, and how much compute a policy can still save when its calibration evidence is scarce.

## difficulty_mix_3_1

Efficiency when most instances (75%) are solvable within the full budget. Most of the available savings come from stopping solvable instances once they have converged.

## difficulty_mix_1_1

Efficiency when solvable and unsolvable instances are balanced, so more runs would otherwise consume the full budget without ever becoming correct.

## difficulty_mix_1_3

Efficiency when most instances (75%) are unsolvable within the full budget. Policies that only stop when confident spend nearly the full budget on most instances; tolerances are tighter here because abstaining on everything immediately would otherwise look almost acceptable.
