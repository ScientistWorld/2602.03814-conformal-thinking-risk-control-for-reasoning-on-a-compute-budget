# Scientist Constraints

These constraints define what future scientist agents must hold fixed when trying to improve the benchmark. The goal is to improve risk-controlled adaptive stopping, not to win by changing the task or by using information the deployed policy would not have.

## Interface

A method is a stopping-policy program registered in `outputs/<method>/policy.json` and scored through the online protocol in `briefing/evaluation.md`. The evaluators own the trajectories, the gold answers, the calibration draws, the target risks `epsilon`, the confidence `delta`, the calibration and test sizes, the exit semantics and token accounting, and the failure gate. Do not modify `eval/`, the generator in `data/`, or the experiment definitions to change a score.

## Calibration data

Within one calibration call, a policy may use only the calibration instances the evaluator sends in that call (plus any fixed design choices made in advance). In particular, do not:

- read, import or execute anything under `eval/test/`, or search the filesystem for held-out data;
- calibrate on extra labelled data, including trajectories generated from the public simulator in `data/`, instead of or in addition to the supplied calibration set;
- persist calibration sets or held-out observations to disk (or any other channel) and reuse them at another operating point, experiment or evaluation run (each operating point already runs in a fresh process; carrying state across them by other means is out of bounds);
- fit the public simulator's parameters to the calibration set and calibrate on synthetic samples from it.

Fixed design choices (signal transformations, candidate grids, model families) may be developed on the public development profiles; the operating point itself must come from the supplied calibration set and `epsilon`/`delta`.

## Held-out instances

A policy decides from the chunks revealed so far. It must not try to obtain later chunks, labels or solvability information by any route other than the protocol, and must answer every step message with exactly one action.

## Risk targets

Use the `epsilon` and `delta` sent by the evaluator. Calibrating to a looser tolerance trades a constraint failure for savings and is scored as a failure; calibrating to a stricter one leaves allowed risk unused and costs tokens.

## Metrics

Do not score wall-clock time. Token use is charged by the evaluator up to the chunk where the policy stopped; budget exits, early answers and defers are derived by the evaluator from where the policy stopped.

## Compliance Checklist

- [ ] The method is a policy program registered in `outputs/<method>/policy.json`; `eval/` and `data/` are unchanged
- [ ] Each operating point is set only from the calibration instances of that call, `epsilon` and `delta`
- [ ] No access to `eval/test/`, no extra simulated or external labelled data, no state shared across calibration calls through disk
- [ ] Decisions use only chunks revealed so far
- [ ] Improvements are reported with the realized risks and violation rates, not only token savings
