#!/usr/bin/env python3
"""Evaluate Conformal Thinking artifacts without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def select_operating_point(result: dict, epsilon: float) -> dict:
    points = result.get("epsilons", [])
    if not points:
        raise ValueError(f"No epsilon results found in {result}")
    return min(points, key=lambda item: abs(item["epsilon"] - epsilon))


def metrics(policy: dict, epsilon: float) -> dict[str, float]:
    return {
        "accuracy": policy["accuracy"],
        "token_fraction": policy["token_fraction"],
        "token_savings": policy["token_savings"],
        "false_positive_risk": policy["false_positive_risk"],
        "false_negative_risk": policy["false_negative_risk"],
        "risk_excess": max(
            0.0,
            max(policy["false_positive_risk"], policy["false_negative_risk"]) - epsilon,
        ),
        "exit_lower_fraction": policy.get("exit_lower_fraction", 0.0),
        "exit_budget_fraction": policy.get("exit_budget_fraction", 0.0),
    }


def add_policy_comparison(
    scores: dict,
    experiment_name: str,
    method_path: Path,
    baseline_path: Path,
    epsilon: float,
) -> None:
    if not method_path.exists() or not baseline_path.exists():
        return
    method_point = select_operating_point(load(method_path), epsilon)
    baseline_point = select_operating_point(load(baseline_path), epsilon)
    scores["experiments"][experiment_name] = {
        "results": {
            "upper_only": metrics(baseline_point["policies"]["upper_only"], method_point["epsilon"]),
            "conformal_thinking": metrics(
                method_point["policies"]["conformal_thinking"], method_point["epsilon"]
            ),
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method-results", default="outputs/conformal_thinking/results.json")
    parser.add_argument("--baseline-results", default="outputs/baseline/results.json")
    parser.add_argument("--scores", default="scoring/scores.json")
    parser.add_argument("--epsilon", type=float, default=0.32)
    args = parser.parse_args()

    method_point = select_operating_point(load(Path(args.method_results)), args.epsilon)
    baseline_point = select_operating_point(load(Path(args.baseline_results)), args.epsilon)

    scores = {"experiments": {}}
    scores["experiments"]["dual_threshold_efficiency"] = {
        "results": {
            "upper_only": metrics(baseline_point["policies"]["upper_only"], method_point["epsilon"]),
            "conformal_thinking": metrics(
                method_point["policies"]["conformal_thinking"], method_point["epsilon"]
            ),
        }
    }
    scores["experiments"]["risk_control"] = {
        "results": {
            "naive_or_uncalibrated": metrics(
                baseline_point["policies"]["upper_only"], method_point["epsilon"]
            ),
            "conformal_thinking": metrics(
                method_point["policies"]["conformal_thinking"], method_point["epsilon"]
            ),
        }
    }
    for ratio in ("3_1", "1_1", "1_3"):
        add_policy_comparison(
            scores,
            f"lower_threshold_ratio_{ratio}",
            Path(f"outputs/conformal_thinking/ratio_{ratio}.json"),
            Path(f"outputs/baseline/ratio_{ratio}.json"),
            args.epsilon,
        )

    out = Path(args.scores)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(scores, handle, indent=2)


if __name__ == "__main__":
    main()
