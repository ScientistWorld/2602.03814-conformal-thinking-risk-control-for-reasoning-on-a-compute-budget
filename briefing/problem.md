# Problem Definition

## Research Question

Reasoning language models can improve answer accuracy by spending more test-time compute, but a fixed reasoning budget wastes tokens on easy or hopeless instances and an adaptive budget can stop too early. The problem is to choose, for each reasoning instance, when to stop generating intermediate reasoning while preserving a user-specified bound on the error introduced by stopping.

The benchmark asks whether a system can allocate reasoning effort adaptively across a set of difficult question-answering tasks. A solution receives a prompt, a reasoning model's partial reasoning trajectory over time, candidate answers at intermediate stopping points, and scalar stopping signals. It must decide when to stop, answer, or abstain/defer before the maximum token budget is exhausted.

## Why It Matters

Reasoning models are expensive at inference time. A useful stopping policy should save tokens without turning operating-point selection into a hidden accuracy failure mode, especially on hard datasets where many examples may never become answerable within the allowed budget.

## Success Criteria

A successful solution should:

- Keep realized early-stopping risk at or below a user-selected tolerance on held-out test data.
- Reduce token usage relative to a full-budget or uniform-budget policy at comparable task accuracy.
- Work across multiple stopping signals, datasets, and difficulty mixes without relying on test-set labels for operating-point selection.
- Report both benefit metrics, such as accuracy and token reduction, and constraint metrics, such as false positive and false negative risk.
