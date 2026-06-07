# Experiment Overview

## dual_threshold_efficiency

Tests the paper's central compute-efficiency claim in a compact benchmark setting. The experiment compares an adaptive policy that can stop for both confident success and likely failure against the standard confident-success-only adaptive baseline, then measures whether the added stopping option saves more reasoning tokens while keeping error-risk metrics within the requested operating tolerance.

## risk_control

Tests the reliability side of the claim. The experiment measures whether the deployed stopping outputs stay within the configured risk budget on held-out examples, so improvements in token savings are penalized if they come from excessive incorrect early answers or premature deferrals.
