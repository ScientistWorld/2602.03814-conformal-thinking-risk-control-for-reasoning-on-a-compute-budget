# Conformal Thinking: Risk Control for Reasoning on a Compute Budget

| This paper | Scientist World, the framework this environment belongs to |
|:---:|:---:|
| <a href="https://arxiv.org/abs/2602.03814"><img alt="This paper on arXiv" src="https://img.shields.io/badge/arXiv-2602.03814-b31b1b?logo=arxiv&logoColor=white"></a> | <a href="https://arxiv.org/abs/2611.08478"><img alt="Scientist World on arXiv" src="https://img.shields.io/badge/arXiv-2611.08478-b31b1b?logo=arxiv&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world"><img alt="Scientist World code" src="https://img.shields.io/badge/Code-Scientist_World-181717?logo=github&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world_cli"><img alt="Command line code" src="https://img.shields.io/badge/Code-Command_line-181717?logo=github&logoColor=white"></a> |

| | |
|---|---|
| **Paper ID** | [2602.03814](https://arxiv.org/abs/2602.03814) |
| **Domain** | Large Language Models / Test-Time Reasoning / Risk-Controlled Inference |
| **TL;DR** | The paper calibrates adaptive early stopping for reasoning LLMs so users can trade off error risk and token cost with statistical risk control rather than hand-tuned thresholds. |

## Summary

Reasoning LLMs often improve with more generated reasoning tokens, but fixed budgets waste compute and heuristic early exits can silently harm accuracy. This paper formulates reasoning-budget selection as risk control: a user specifies acceptable false positive and false negative risks, and held-out validation data calibrates stopping thresholds with finite-sample correction. The method combines a standard confidence-based upper threshold with a parametric lower threshold that stops trajectories unlikely to become correct. Experiments on math, science, and vision reasoning benchmarks show improved token efficiency while respecting target risks more reliably than naive validation tuning.

## Problem

Reasoning language models can improve answer accuracy by spending more test-time compute, but a fixed reasoning budget wastes tokens on easy or hopeless instances and an adaptive budget can stop too early. The problem is to choose, for each reasoning instance, when to stop generating intermediate reasoning while preserving a user-specified bound on the error introduced by stopping.

The benchmark asks whether a system can allocate reasoning effort adaptively across a set of difficult question-answering tasks. A solution receives a prompt, a reasoning model's partial reasoning trajectory over time, candidate answers at intermediate stopping points, and scalar stopping signals. It must decide when to stop, answer, or abstain/defer before the maximum token budget is exhausted.

## The paper's method

The paper reframes adaptive reasoning-budget selection as a distribution-free risk-control problem. Instead of hand-picking opaque confidence thresholds, the user specifies acceptable risks, and a validation set is used to calibrate stopping thresholds that satisfy those risks while minimizing wasted reasoning compute.

The main algorithmic contribution is a dual-threshold early-exit framework. It includes the standard upper threshold for stopping when the current answer appears reliable and a new parametric lower threshold for stopping or deferring when the reasoning signal fails to make enough progress.

## Key results of the paper

- Risk-controlled calibration keeps empirical test risk below target tolerances more consistently than naive validation tuning across random validation-test splits.
- Selecting the most efficient calibrated stopping signal improves the accuracy-versus-token trade-off across several reasoning models.
- Combining upper and lower exits saves more tokens when unsolvable examples are common, because the lower exit avoids spending the full budget on trajectories that do not improve.

## Run it

```bash
pip install sciworld
sw research 2602.03814 --mode innovate --agent claude-code
sw evaluate 2602.03814
```

## More

The full problem statement, method notes, evaluation protocol and reproduction log are in [DETAILS.md](DETAILS.md).

