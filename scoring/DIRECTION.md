# Research Direction

## Research Problem

This benchmark studies adaptive inference for reasoning language models under explicit risk constraints. The central question is how to decide when a partially generated reasoning trajectory has consumed enough compute, while preserving a user-chosen bound on the errors caused by stopping early, using only a small labelled calibration set from the deployment distribution.

## Research Scope

A scientist should work on stopping policies for ongoing reasoning traces: how to estimate deployment risk from limited calibration data with a valid finite-sample guarantee, how to choose operating points that use the allowed risk efficiently, how to combine or transform stopping signals (including answer-consistency information across chunks), and how to detect that further reasoning is unlikely to help.

Measured room for improvement exists: on the held-out test the reference leaves a large part of the possible savings unused, especially in the small-calibration and unsolvable-heavy settings, where its calibration is conservative (tighter finite-sample bounds and searching the combined stopping rule jointly both score clearly higher). Which signal is informative differs between (model, dataset) pairs and target risks, and held-out pairs show behaviours the development profiles do not, so improvements should come from better use of the calibration data, not from modelling the development profiles.

## Approach Scope

The output must remain a policy that consumes partial reasoning information chunk by chunk and decides when to stop or abstain before a maximum budget, calibrated only on the supplied calibration set for the supplied `epsilon` and `delta`. It is evaluated by the benchmark's risk, accuracy and token metrics and its failure gate.

## Out of Bounds

- Improving the underlying model's reasoning, or using a stronger model, external solver, verifier or retrieval to change the answers. The trajectories are fixed.
- Using labelled data beyond the supplied calibration set: held-out data, the public simulator as an unlimited source of labelled calibration data, or calibration sets carried over between calls.
- Optimizing token count while ignoring the realized false positive and false negative risks; such runs fail the gate.
- Choosing operating points from test outcomes or test curves.
