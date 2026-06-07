# Experiment Overview

## dual_threshold_efficiency

Tests the paper's central compute-efficiency claim in a compact benchmark setting. The experiment compares an adaptive policy that can stop for both confident success and likely failure against the standard confident-success-only adaptive baseline, then measures whether the added stopping option saves more reasoning tokens while keeping error-risk metrics within the requested operating tolerance.

## risk_control

Tests the reliability side of the claim. The experiment measures whether the deployed stopping outputs stay within the configured risk budget on held-out examples, so improvements in token savings are penalized if they come from excessive incorrect early answers or premature deferrals.

## lower_threshold_ratio_3_1

Tests the lower-threshold efficiency claim when most examples are solvable within the full budget. The expected benefit is present but smaller because confident-success exits already handle many examples.

## lower_threshold_ratio_1_1

Tests the same stopping policies when solvable and unsolvable examples are balanced. This setting should expose more wasted full-budget runs for an upper-only baseline and more useful early deferrals for a dual-exit policy.

## lower_threshold_ratio_1_3

Tests the high-unsolvable regime emphasized by the paper. A useful policy should avoid spending nearly the full budget on many examples that do not improve, while still respecting the configured early-stopping risk.
