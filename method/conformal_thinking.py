#!/usr/bin/env python3
"""Reproduction of Conformal Thinking threshold calibration.

Implements the paper's actual computational steps:
  * false-positive upper-threshold stopping (Eq. 6, 10)
  * false-negative lower sigmoid threshold (Eq. 7, 11, 12)
  * Hoeffding UCB finite-sample risk correction (Eq. 25)
  * efficiency-loss tie-breaking among feasible candidates (Alg. 1)
  * combined lower+upper stopping (Eq. 17)
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


FORCING_STRING = "\n **Final Answer**\n \\boxed{"


@dataclass(frozen=True)
class Candidate:
    name: str
    threshold: float
    risk: float
    adjusted_risk: float
    efficiency_loss: float


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def ucb(risk: float, n: int, delta: float) -> float:
    return risk + math.sqrt(math.log(1.0 / delta) / (2.0 * n))


def signal(step: dict, name: str, max_tokens: int) -> float:
    if name == "token_fraction":
        return step["tokens"] / max_tokens
    return step["signals"][name]


def first_correct_step(instance: dict) -> int | None:
    for idx, step in enumerate(instance["steps"]):
        if step["prediction"] == instance["gold"]:
            return idx
    return None


def upper_exit(instance: dict, signal_name: str, threshold: float) -> tuple[int, str]:
    max_tokens = instance["steps"][-1]["tokens"]
    for idx, step in enumerate(instance["steps"]):
        if signal(step, signal_name, max_tokens) >= threshold:
            return idx, "upper"
    return len(instance["steps"]) - 1, "budget"


def lower_curve(tokens: int, budget: int, c: float, upper_threshold: float) -> float:
    return upper_threshold * sigmoid(c * (tokens - budget / 2.0))


def lower_exit(
    instance: dict, signal_name: str, c: float, upper_threshold: float = 1.0
) -> tuple[int, str]:
    budget = instance["steps"][-1]["tokens"]
    for idx, step in enumerate(instance["steps"]):
        if signal(step, signal_name, budget) < lower_curve(step["tokens"], budget, c, upper_threshold):
            return idx, "lower"
    return len(instance["steps"]) - 1, "budget"


def dual_exit(instance: dict, signal_name: str, upper_threshold: float, c: float) -> tuple[int, str]:
    up_idx, up_reason = upper_exit(instance, signal_name, upper_threshold)
    low_idx, low_reason = lower_exit(instance, signal_name, c, upper_threshold)
    if low_idx < up_idx:
        return low_idx, low_reason
    if up_idx < low_idx:
        return up_idx, up_reason
    if up_reason == "upper":
        return up_idx, "upper"
    if low_reason == "lower":
        return low_idx, "lower"
    return up_idx, "budget"


def fp_loss(instance: dict, exit_idx: int, reason: str) -> float:
    if reason != "upper":
        return 0.0
    return 0.0 if instance["steps"][exit_idx]["prediction"] == instance["gold"] else 1.0


def fn_loss(instance: dict, exit_idx: int, reason: str) -> float:
    if reason != "lower":
        return 0.0
    future = instance["steps"][exit_idx:]
    if not future:
        return 0.0
    return sum(1.0 for step in future if step["prediction"] == instance["gold"]) / len(future)


def upper_efficiency_loss(instance: dict, exit_idx: int) -> float:
    first = first_correct_step(instance)
    if first is None:
        return 0.0
    return max(0, exit_idx - first) / len(instance["steps"])


def lower_efficiency_loss(instance: dict, exit_idx: int) -> float:
    prefix = instance["steps"][: exit_idx + 1]
    return sum(1.0 for step in prefix if step["prediction"] != instance["gold"]) / len(instance["steps"])


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def calibrate(
    validation: list[dict],
    signal_names: list[str],
    thresholds: list[float],
    epsilon: float,
    delta: float,
    exit_fn: Callable[[dict, str, float], tuple[int, str]],
    risk_fn: Callable[[dict, int, str], float],
    efficiency_fn: Callable[[dict, int], float],
    method_name: str,
) -> Candidate | None:
    feasible: list[Candidate] = []
    for signal_name in signal_names:
        for threshold in thresholds:
            exits = [exit_fn(instance, signal_name, threshold) for instance in validation]
            risk = mean(risk_fn(instance, idx, reason) for instance, (idx, reason) in zip(validation, exits))
            adjusted = ucb(risk, len(validation), delta) if method_name == "ucb" else risk
            if adjusted <= epsilon:
                eff = mean(efficiency_fn(instance, idx) for instance, (idx, _) in zip(validation, exits))
                feasible.append(Candidate(signal_name, threshold, risk, adjusted, eff))
    if not feasible:
        return None
    return min(feasible, key=lambda cand: (cand.efficiency_loss, cand.adjusted_risk))


def evaluate_policy(
    data: list[dict],
    name: str,
    exit_fn: Callable[[dict], tuple[int, str]],
) -> dict:
    total_tokens = 0
    full_tokens = 0
    correct = 0
    fp = []
    fn = []
    reasons = {"upper": 0, "lower": 0, "budget": 0}
    for instance in data:
        exit_idx, reason = exit_fn(instance)
        step = instance["steps"][exit_idx]
        reasons[reason] += 1
        total_tokens += step["tokens"]
        full_tokens += instance["steps"][-1]["tokens"]
        correct += int(step["prediction"] == instance["gold"] and reason != "lower")
        fp.append(fp_loss(instance, exit_idx, reason))
        fn.append(fn_loss(instance, exit_idx, reason))

    n = len(data)
    return {
        "name": name,
        "accuracy": correct / n,
        "false_positive_risk": mean(fp),
        "false_negative_risk": mean(fn),
        "tokens_used": total_tokens,
        "full_budget_tokens": full_tokens,
        "token_fraction": total_tokens / full_tokens if full_tokens else 0.0,
        "token_savings": 1.0 - (total_tokens / full_tokens if full_tokens else 0.0),
        "exit_upper_fraction": reasons["upper"] / n,
        "exit_lower_fraction": reasons["lower"] / n,
        "exit_budget_fraction": reasons["budget"] / n,
    }


def run(args: argparse.Namespace) -> dict:
    all_data = load_jsonl(Path(args.data))
    validation = [row for row in all_data if row["split"] == "validation"]
    test = [row for row in all_data if row["split"] == "test"]
    signal_names = ["confidence", "eat_confidence", "token_fraction"]
    confidence_signal = ["confidence"]
    upper_grid = [i / 100.0 for i in range(5, 101)]
    # Very small c values make the sigmoid lower threshold nearly flat and can
    # trigger at the first chunk. The paper's lower threshold is a progress
    # curve over the token budget, so the grid starts where the curve is low
    # early and rises around the midpoint.
    c_grid = [i / 1000.0 for i in range(8, 81)]

    results = {"config": vars(args), "epsilons": []}
    for epsilon in args.epsilons:
        upper = calibrate(
            validation,
            signal_names,
            upper_grid,
            epsilon,
            args.delta,
            upper_exit,
            fp_loss,
            upper_efficiency_loss,
            args.calibration,
        )
        if upper is None:
            continue

        lower = calibrate(
            validation,
            confidence_signal,
            c_grid,
            epsilon,
            args.delta,
            lambda instance, sig, c: lower_exit(instance, sig, c, upper.threshold),
            fn_loss,
            lower_efficiency_loss,
            args.calibration,
        )
        if lower is None:
            continue

        upper_only = evaluate_policy(
            test,
            "upper_only",
            lambda instance, cand=upper: upper_exit(instance, cand.name, cand.threshold),
        )
        lower_only = evaluate_policy(
            test,
            "lower_only",
            lambda instance, cand=lower, up=upper: lower_exit(instance, cand.name, cand.threshold, up.threshold),
        )
        dual = evaluate_policy(
            test,
            "conformal_thinking",
            lambda instance, up=upper, low=lower: dual_exit(instance, up.name, up.threshold, low.threshold),
        )
        full_budget = evaluate_policy(
            test,
            "full_budget",
            lambda instance: (len(instance["steps"]) - 1, "budget"),
        )
        results["epsilons"].append(
            {
                "epsilon": epsilon,
                "upper_candidate": upper.__dict__,
                "lower_candidate": lower.__dict__,
                "policies": {
                    "full_budget": full_budget,
                    "upper_only": upper_only,
                    "lower_only": lower_only,
                    "conformal_thinking": dual,
                },
            }
        )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/synthetic_reasoning.jsonl")
    parser.add_argument("--output", default="outputs/conformal_thinking/results.json")
    parser.add_argument("--calibration", choices=["ucb", "naive"], default="ucb")
    parser.add_argument("--delta", type=float, default=0.1)
    parser.add_argument("--epsilons", nargs="+", type=float, default=[0.18, 0.25, 0.32, 0.40])
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
