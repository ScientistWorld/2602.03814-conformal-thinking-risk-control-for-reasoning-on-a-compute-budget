#!/usr/bin/env python3
"""Reproduction of Conformal Thinking threshold calibration.

Implements the paper's actual computational steps:
  * false-positive upper-threshold stopping (Eq. 6, 10)
  * false-negative lower sigmoid threshold scaled by the upper threshold
    (Eq. 7, 11, 12, Sec. 4.4)
  * Hoeffding UCB finite-sample risk correction (Eq. 25)
  * efficiency-loss selection among feasible signal/threshold candidates
    (Alg. 1, Eq. 8, 9, 16)
  * two-step combination: calibrate the upper threshold first, then the lower
    threshold under it, and exit at min(tau_+, tau_-, T) (Eq. 17)

The policy is deployed through the benchmark's online stopping protocol
(``serve``): the evaluator sends a labelled calibration set with the target
risk ``epsilon`` and confidence ``delta``; the policy calibrates with Alg. 1
and then receives held-out trajectories one chunk at a time, answering
``continue``, ``answer`` or ``defer`` after each chunk.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from typing import Callable, Iterable


SIGNALS = ["confidence", "eat_confidence", "token_fraction"]
LOWER_SIGNAL = "confidence"
UPPER_GRID = [i / 100.0 for i in range(5, 101)]
# Very small c values make the sigmoid lower threshold nearly flat and can
# trigger at the first chunk. The paper's lower threshold is a progress curve
# over the token budget, so the grid starts where the curve is low early and
# rises around the budget midpoint.
C_GRID = [i / 1000.0 for i in range(8, 81)]


@dataclass(frozen=True)
class Candidate:
    name: str
    threshold: float
    risk: float
    adjusted_risk: float
    efficiency_loss: float


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def ucb(risk: float, n: int, delta: float) -> float:
    """Hoeffding upper confidence bound for a [0, 1]-bounded loss (Eq. 25)."""
    return risk + math.sqrt(math.log(1.0 / delta) / (2.0 * n))


def budget_of(instance: dict) -> int:
    return int(instance.get("budget_tokens") or instance["steps"][-1]["tokens"])


def signal(step: dict, name: str, budget: int) -> float:
    if name == "token_fraction":
        return step["tokens"] / budget
    return step["signals"][name]


def first_correct_step(instance: dict) -> int | None:
    for idx, step in enumerate(instance["steps"]):
        if step["prediction"] == instance["gold"]:
            return idx
    return None


def upper_exit(instance: dict, signal_name: str, threshold: float) -> tuple[int, str]:
    budget = budget_of(instance)
    for idx, step in enumerate(instance["steps"]):
        if signal(step, signal_name, budget) >= threshold:
            return idx, "upper"
    return len(instance["steps"]) - 1, "budget"


def lower_curve(tokens: int, budget: int, c: float, upper_threshold: float) -> float:
    """Parametric lower threshold (Eq. 12) bounded by the upper threshold."""
    return upper_threshold * sigmoid(c * (tokens - budget / 2.0))


def lower_exit(instance: dict, signal_name: str, c: float, upper_threshold: float = 1.0) -> tuple[int, str]:
    budget = budget_of(instance)
    for idx, step in enumerate(instance["steps"]):
        if signal(step, signal_name, budget) < lower_curve(step["tokens"], budget, c, upper_threshold):
            return idx, "lower"
    return len(instance["steps"]) - 1, "budget"


def fp_loss(instance: dict, exit_idx: int, reason: str) -> float:
    """False positive loss (Eq. 6)."""
    if reason != "upper":
        return 0.0
    return 0.0 if instance["steps"][exit_idx]["prediction"] == instance["gold"] else 1.0


def fn_loss(instance: dict, exit_idx: int, reason: str) -> float:
    """False negative loss (Eq. 7): correctness averaged over remaining steps."""
    if reason != "lower":
        return 0.0
    future = instance["steps"][exit_idx:]
    if not future:
        return 0.0
    return sum(1.0 for step in future if step["prediction"] == instance["gold"]) / len(future)


def upper_efficiency_loss(instance: dict, exit_idx: int) -> float:
    """Upper-threshold efficiency loss (Eq. 8)."""
    first = first_correct_step(instance)
    if first is None:
        return 0.0
    return max(0, exit_idx - first) / len(instance["steps"])


def lower_efficiency_loss(instance: dict, exit_idx: int) -> float:
    """Lower-threshold efficiency loss (Eq. 9)."""
    prefix = instance["steps"][: exit_idx + 1]
    return sum(1.0 for step in prefix if step["prediction"] != instance["gold"]) / len(instance["steps"])


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def candidate_statistics(
    validation: list[dict],
    signal_names: list[str],
    thresholds: list[float],
    exit_fn: Callable[[dict, str, float], tuple[int, str]],
    risk_fn: Callable[[dict, int, str], float],
    efficiency_fn: Callable[[dict, int], float],
) -> list[tuple[str, float, float, float]]:
    """Empirical risk (Eq. 14) and efficiency loss (Eq. 16) of every candidate."""
    stats = []
    for signal_name in signal_names:
        for threshold in thresholds:
            exits = [exit_fn(instance, signal_name, threshold) for instance in validation]
            risk = mean(risk_fn(instance, idx, reason) for instance, (idx, reason) in zip(validation, exits))
            eff = mean(efficiency_fn(instance, idx) for instance, (idx, _) in zip(validation, exits))
            stats.append((signal_name, threshold, risk, eff))
    return stats


def select(
    stats: list[tuple[str, float, float, float]], n: int, epsilon: float, delta: float, calibration: str
) -> Candidate | None:
    """Alg. 1: keep candidates whose adjusted risk is <= epsilon, pick min efficiency loss."""
    feasible = []
    for signal_name, threshold, risk, eff in stats:
        adjusted = ucb(risk, n, delta) if calibration == "ucb" else risk
        if adjusted <= epsilon:
            feasible.append(Candidate(signal_name, threshold, risk, adjusted, eff))
    if not feasible:
        return None
    return min(feasible, key=lambda cand: (cand.efficiency_loss, cand.adjusted_risk))


class ConformalThinkingPolicy:
    """Calibrated dual-threshold (or upper-only) early-exit policy."""

    def __init__(self, variant: str = "dual", calibration: str = "ucb") -> None:
        self.variant = variant
        self.calibration = calibration
        self.upper: Candidate | None = None
        self.lower: Candidate | None = None
        self._cache_id: object = None
        self._upper_stats: list | None = None
        self._lower_stats: dict[float, list] = {}
        self.budget = 1

    def calibrate(self, instances: list[dict], epsilon: float, delta: float, calibration_id: object = None) -> None:
        if calibration_id is None or calibration_id != self._cache_id:
            self._cache_id = calibration_id
            self._upper_stats = None
            self._lower_stats = {}
        n = len(instances)
        if self._upper_stats is None:
            self._upper_stats = candidate_statistics(
                instances, SIGNALS, UPPER_GRID, upper_exit, fp_loss, upper_efficiency_loss
            )
        self.upper = select(self._upper_stats, n, epsilon, delta, self.calibration)
        self.lower = None
        if self.variant == "upper_only":
            return
        # Sec. 4.4: the lower curve is scaled by the selected upper threshold so the
        # two thresholds never intersect. Without a feasible upper threshold the
        # curve is scaled by the maximum signal value.
        scale = self.upper.threshold if self.upper is not None else 1.0
        if scale not in self._lower_stats:
            self._lower_stats[scale] = candidate_statistics(
                instances,
                [LOWER_SIGNAL],
                C_GRID,
                lambda instance, sig, c: lower_exit(instance, sig, c, scale),
                fn_loss,
                lower_efficiency_loss,
            )
        self.lower = select(self._lower_stats[scale], n, epsilon, delta, self.calibration)

    def begin(self, budget_tokens: int) -> None:
        self.budget = max(1, int(budget_tokens))

    def decide(self, step: dict) -> str:
        """Online Eq. 17: exit at the earliest of the upper and lower exits."""
        if self.upper is not None and signal(step, self.upper.name, self.budget) >= self.upper.threshold:
            return "answer"
        if self.lower is not None:
            scale = self.upper.threshold if self.upper is not None else 1.0
            curve = lower_curve(step["tokens"], self.budget, self.lower.threshold, scale)
            if signal(step, LOWER_SIGNAL, self.budget) < curve:
                return "defer"
        return "continue"


def serve(policy: ConformalThinkingPolicy) -> None:
    """JSON-lines stopping protocol over stdin/stdout."""
    out = sys.stdout
    for line in sys.stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        kind = message.get("type")
        if kind == "step":
            reply = {"action": policy.decide(message["step"])}
        elif kind == "begin":
            policy.begin(message["budget_tokens"])
            reply = {"ok": True}
        elif kind == "calibrate":
            policy.calibrate(
                message["instances"], float(message["epsilon"]), float(message["delta"]), message.get("calibration_id")
            )
            reply = {"ok": True}
        elif kind == "shutdown":
            return
        else:
            reply = {"error": f"unknown message type {kind!r}"}
        out.write(json.dumps(reply) + "\n")
        out.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    serve_parser = sub.add_parser("serve", help="run the online stopping protocol on stdin/stdout")
    serve_parser.add_argument("--variant", choices=["dual", "upper_only"], default="dual")
    serve_parser.add_argument("--calibration", choices=["ucb", "naive"], default="ucb")
    args = parser.parse_args()
    if args.command == "serve":
        serve(ConformalThinkingPolicy(args.variant, args.calibration))


if __name__ == "__main__":
    main()
