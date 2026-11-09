# Problem Definition

## Research Question

Reasoning language models can improve answer accuracy by spending more test-time compute, but a fixed reasoning budget wastes tokens on easy or hopeless instances and an adaptive budget can stop too early. The problem is to choose, for each reasoning instance, when to stop generating intermediate reasoning while preserving a user-specified bound on the error introduced by stopping.

A solution is a stopping policy. Before deployment on a given (model, dataset) pair it receives a small labelled calibration set of complete reasoning trajectories, a target risk `epsilon` and a confidence level `delta`. It then watches unseen trajectories one reasoning chunk at a time (the trial answer, scalar uncertainty signals and the cumulative token count at that chunk) and after each chunk decides to continue, to stop and answer, or to stop and defer (abstain) before the maximum token budget is exhausted.

## Why It Matters

Reasoning models are expensive at inference time. A useful stopping policy should save tokens without turning operating-point selection into a hidden accuracy failure mode, especially on hard datasets where many examples never become answerable within the allowed budget. The mapping from a raw stopping signal to the error it causes differs between models and datasets, so the operating point has to be set from limited labelled calibration data, with the finite size of that data taken into account.

## Success Criteria

A successful solution should:

- Keep realized stopping risks (wrong early answers; premature deferrals of instances that would later have been answered correctly) at or below the requested tolerance on unseen data, for the stated confidence level, across calibration draws.
- Use as few reasoning tokens as possible within that constraint, at the highest accuracy it can keep.
- Work across (model, dataset) profiles, small and large calibration sets, and different mixes of solvable and unsolvable instances, using only the supplied calibration data.
