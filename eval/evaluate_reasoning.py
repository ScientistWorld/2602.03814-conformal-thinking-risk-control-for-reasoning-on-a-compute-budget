#!/usr/bin/env python3
"""Evaluate adaptive reasoning-budget artifacts without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def select_operating_point(result: dict, epsilon: float) -> dict:
    points = result.get("epsilons", [])
    if not points:
        raise ValueError(f"No epsilon results found in {result}")
    return min(points, key=lambda item: abs(item["epsilon"] - epsilon))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def canonical_reason(reason: str) -> str:
    aliases = {
        "upper": "answer",
        "answer": "answer",
        "lower": "defer",
        "defer": "defer",
        "budget": "budget",
    }
    if reason not in aliases:
        raise ValueError(f"Invalid exit reason {reason!r}")
    return aliases[reason]


def fp_loss(instance: dict, exit_idx: int, reason: str) -> float:
    if canonical_reason(reason) != "answer":
        return 0.0
    return 0.0 if instance["steps"][exit_idx]["prediction"] == instance["gold"] else 1.0


def fn_loss(instance: dict, exit_idx: int, reason: str) -> float:
    if canonical_reason(reason) != "defer":
        return 0.0
    future = instance["steps"][exit_idx:]
    if not future:
        return 0.0
    return sum(1.0 for step in future if step["prediction"] == instance["gold"]) / len(future)


def data_path_for(result: dict, fallback: Path) -> Path:
    configured = result.get("config", {}).get("data")
    return Path(configured) if configured else fallback


def recompute_policy_metrics(policy: dict, data: list[dict], epsilon: float) -> dict[str, float]:
    decisions = policy.get("decisions")
    if decisions is None:
        raise ValueError(
            f"Policy {policy.get('name', '<unnamed>')} has no per-example decisions; "
            "evaluation must recompute metrics from raw stopping decisions."
        )

    by_id = {instance["id"]: instance for instance in data if instance.get("split") == "test"}
    if len(decisions) != len(by_id):
        raise ValueError(
            f"Policy {policy.get('name', '<unnamed>')} has {len(decisions)} decisions "
            f"for {len(by_id)} test examples."
        )

    total_tokens = 0
    full_tokens = 0
    correct = 0
    fp_values: list[float] = []
    fn_values: list[float] = []
    reasons = {"answer": 0, "defer": 0, "budget": 0}
    solvable_count = 0
    solvable_correct = 0
    unsolvable_tokens = 0
    unsolvable_full_tokens = 0
    defer_count = 0
    defer_unsolvable = 0

    seen: set[str] = set()
    for decision in decisions:
        instance_id = decision["id"]
        if instance_id in seen:
            raise ValueError(f"Duplicate decision for {instance_id}")
        seen.add(instance_id)
        if instance_id not in by_id:
            raise ValueError(f"Decision references unknown test example {instance_id}")

        instance = by_id[instance_id]
        exit_idx = int(decision["exit_idx"])
        reason = canonical_reason(decision["reason"])
        if exit_idx < 0 or exit_idx >= len(instance["steps"]):
            raise ValueError(f"Invalid exit_idx {exit_idx} for {instance_id}")

        step = instance["steps"][exit_idx]
        is_solvable = bool(instance.get("solvable_under_budget"))
        reasons[reason] += 1
        total_tokens += step["tokens"]
        full_tokens += instance["steps"][-1]["tokens"]
        is_correct = step["prediction"] == instance["gold"] and reason != "defer"
        correct += int(is_correct)
        fp_values.append(fp_loss(instance, exit_idx, reason))
        fn_values.append(fn_loss(instance, exit_idx, reason))
        if is_solvable:
            solvable_count += 1
            solvable_correct += int(is_correct)
        else:
            unsolvable_tokens += step["tokens"]
            unsolvable_full_tokens += instance["steps"][-1]["tokens"]
        if reason == "defer":
            defer_count += 1
            defer_unsolvable += int(not is_solvable)

    if seen != set(by_id):
        missing = sorted(set(by_id) - seen)[:5]
        raise ValueError(f"Missing decisions for test examples: {missing}")

    n = len(by_id)
    token_fraction = total_tokens / full_tokens if full_tokens else 0.0
    false_positive_risk = mean(fp_values)
    false_negative_risk = mean(fn_values)
    max_realized_risk = max(false_positive_risk, false_negative_risk)
    unsolvable_token_fraction = (
        unsolvable_tokens / unsolvable_full_tokens if unsolvable_full_tokens else 0.0
    )
    return {
        "accuracy": correct / n if n else 0.0,
        "solvable_accuracy": solvable_correct / solvable_count if solvable_count else 0.0,
        "token_fraction": token_fraction,
        "token_savings": 1.0 - token_fraction,
        "unsolvable_token_savings": 1.0 - unsolvable_token_fraction,
        "false_positive_risk": false_positive_risk,
        "false_negative_risk": false_negative_risk,
        "max_realized_risk": max_realized_risk,
        "risk_excess": max(0.0, max_realized_risk - epsilon),
        "defer_fraction": reasons["defer"] / n if n else 0.0,
        "defer_precision": defer_unsolvable / defer_count if defer_count else 0.0,
        "exit_budget_fraction": reasons["budget"] / n if n else 0.0,
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
    method_result = load(method_path)
    baseline_result = load(baseline_path)
    method_data = load_jsonl(data_path_for(method_result, Path("data/synthetic_reasoning.jsonl")))
    baseline_data = load_jsonl(data_path_for(baseline_result, Path("data/synthetic_reasoning.jsonl")))
    method_point = select_operating_point(method_result, epsilon)
    baseline_point = select_operating_point(baseline_result, epsilon)
    scores["experiments"][experiment_name] = {
        "results": {
            "upper_only": recompute_policy_metrics(
                baseline_point["policies"]["upper_only"], baseline_data, method_point["epsilon"]
            ),
            "conformal_thinking": recompute_policy_metrics(
                method_point["policies"]["conformal_thinking"], method_data, method_point["epsilon"]
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

    method_result = load(Path(args.method_results))
    baseline_result = load(Path(args.baseline_results))
    method_data = load_jsonl(data_path_for(method_result, Path("data/synthetic_reasoning.jsonl")))
    baseline_data = load_jsonl(data_path_for(baseline_result, Path("data/synthetic_reasoning.jsonl")))
    method_point = select_operating_point(method_result, args.epsilon)
    baseline_point = select_operating_point(baseline_result, args.epsilon)

    scores = {"experiments": {}}
    scores["experiments"]["adaptive_budget_efficiency"] = {
        "results": {
            "upper_only": recompute_policy_metrics(
                baseline_point["policies"]["upper_only"], baseline_data, method_point["epsilon"]
            ),
            "conformal_thinking": recompute_policy_metrics(
                method_point["policies"]["conformal_thinking"], method_data, method_point["epsilon"]
            ),
        }
    }
    scores["experiments"]["risk_control"] = {
        "results": {
            "naive_or_uncalibrated": recompute_policy_metrics(
                baseline_point["policies"]["upper_only"], baseline_data, method_point["epsilon"]
            ),
            "conformal_thinking": recompute_policy_metrics(
                method_point["policies"]["conformal_thinking"], method_data, method_point["epsilon"]
            ),
        }
    }
    for ratio in ("3_1", "1_1", "1_3"):
        add_policy_comparison(
            scores,
            f"difficulty_mix_{ratio}",
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
