# Experiment Overview

## adaptive_budget_efficiency

Tests the central compute-efficiency question in a compact benchmark setting. The experiment compares a candidate adaptive stopping policy against a reference adaptive baseline and measures whether the candidate uses fewer reasoning tokens while keeping answer-error and premature-defer risk within the requested tolerance.

## risk_control

Tests the reliability side of the benchmark. The experiment measures whether deployed stopping decisions stay within the configured risk budget on held-out examples, so token savings are penalized if they come from too many incorrect early answers or premature deferrals.

## difficulty_mix_3_1

Tests efficiency when most examples are solvable within the full budget. The expected opportunity for extra savings is present but modest because many examples can be answered before the budget is exhausted.

## difficulty_mix_1_1

Tests the same decision problem when solvable and unsolvable examples are balanced. This setting exposes more wasted full-budget runs and gives useful policies more room to save compute.

## difficulty_mix_1_3

Tests a high-unsolvable regime. A useful policy should avoid spending nearly the full budget on many examples that do not improve, while still respecting the configured answer-error and premature-defer risks.
