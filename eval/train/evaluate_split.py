#!/usr/bin/env python3
"""Visible train-slice evaluator for Conformal Thinking artifacts.

This evaluator reads method output artifacts and recomputes the benchmark
metrics on a visible buffered slice of the paper's original test split. It
does not import from method/ or rerun the algorithm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


SLICE = "train"
SPLIT_SEED = "conformal-thinking-anti-shortcut-v2"
SLICE_MODULUS = 5
SLICE_RESIDUES = {0, 1}
CONTROL_POLICIES = {"full_budget", "lower_only", "upper_only"}
EXPERIMENT_FILES = {
    "dual_threshold_efficiency": "results.json",
    "risk_control": "results.json",
    "lower_threshold_ratio_3_1": "ratio_3_1.json",
    "lower_threshold_ratio_1_1": "ratio_1_1.json",
    "lower_threshold_ratio_1_3": "ratio_1_3.json",
}
FALLBACK_DATA = {
    "results.json": Path("data/synthetic_reasoning.jsonl"),
    "ratio_3_1.json": Path("data/synthetic_ratio_3_1.jsonl"),
    "ratio_1_1.json": Path("data/synthetic_ratio_1_1.jsonl"),
    "ratio_1_3.json": Path("data/synthetic_ratio_1_3.jsonl"),
}


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


def data_path_for(result: dict, fallback: Path) -> Path:
    configured = result.get("config", {}).get("data")
    return Path(configured) if configured else fallback


def difficulty_bucket(instance: dict) -> str:
    steps = len(instance["steps"])
    if steps <= 12:
        return "short"
    if steps <= 15:
        return "medium"
    return "long"


def stable_key(instance_id: str) -> str:
    return hashlib.sha256(f"{SPLIT_SEED}:{instance_id}".encode("utf-8")).hexdigest()


def slice_ids(data: list[dict]) -> set[str]:
    groups: dict[tuple[bool, str], list[str]] = defaultdict(list)
    for instance in data:
        if instance.get("split") != "test":
            continue
        key = (bool(instance.get("solvable_under_budget")), difficulty_bucket(instance))
        groups[key].append(instance["id"])

    selected: set[str] = set()
    for ids in groups.values():
        ordered = sorted(ids, key=stable_key)
        for index, instance_id in enumerate(ordered):
            if index % SLICE_MODULUS in SLICE_RESIDUES:
                selected.add(instance_id)
    return selected


def recompute_policy_metrics(policy: dict, data: list[dict], eval_ids: set[str], epsilon: float) -> dict[str, float]:
    decisions = policy.get("decisions")
    if decisions is None:
        raise ValueError(
            f"Policy {policy.get('name', '<unnamed>')} has no per-example decisions; "
            "evaluation must recompute metrics from raw stopping decisions."
        )

    by_id = {instance["id"]: instance for instance in data if instance.get("id") in eval_ids}
    if set(by_id) != eval_ids:
        missing = sorted(eval_ids - set(by_id))[:5]
        raise ValueError(f"Evaluation slice references missing examples: {missing}")

    total_tokens = 0
    full_tokens = 0
    correct = 0
    fp_values: list[float] = []
    fn_values: list[float] = []
    reasons = {"upper": 0, "lower": 0, "budget": 0}
    solvable_count = 0
    solvable_correct = 0
    unsolvable_tokens = 0
    unsolvable_full_tokens = 0
    lower_exit_count = 0
    lower_exit_unsolvable = 0

    seen: set[str] = set()
    for decision in decisions:
        instance_id = decision["id"]
        if instance_id not in eval_ids:
            continue
        if instance_id in seen:
            raise ValueError(f"Duplicate decision for {instance_id}")
        seen.add(instance_id)

        instance = by_id[instance_id]
        exit_idx = int(decision["exit_idx"])
        reason = decision["reason"]
        if reason not in reasons:
            raise ValueError(f"Invalid exit reason {reason!r} for {instance_id}")
        if exit_idx < 0 or exit_idx >= len(instance["steps"]):
            raise ValueError(f"Invalid exit_idx {exit_idx} for {instance_id}")

        step = instance["steps"][exit_idx]
        is_solvable = bool(instance.get("solvable_under_budget"))
        reasons[reason] += 1
        total_tokens += step["tokens"]
        full_tokens += instance["steps"][-1]["tokens"]
        is_correct = step["prediction"] == instance["gold"] and reason != "lower"
        correct += int(is_correct)
        fp_values.append(fp_loss(instance, exit_idx, reason))
        fn_values.append(fn_loss(instance, exit_idx, reason))
        if is_solvable:
            solvable_count += 1
            solvable_correct += int(is_correct)
        else:
            unsolvable_tokens += step["tokens"]
            unsolvable_full_tokens += instance["steps"][-1]["tokens"]
        if reason == "lower":
            lower_exit_count += 1
            lower_exit_unsolvable += int(not is_solvable)

    if seen != eval_ids:
        missing = sorted(eval_ids - seen)[:5]
        raise ValueError(f"Missing decisions for {SLICE} examples: {missing}")

    n = len(eval_ids)
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
        "exit_lower_fraction": reasons["lower"] / n if n else 0.0,
        "lower_exit_precision": lower_exit_unsolvable / lower_exit_count if lower_exit_count else 0.0,
        "exit_budget_fraction": reasons["budget"] / n if n else 0.0,
    }


def unique_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        normalized = path
        if normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def expand_method_roots(provided: list[str] | None) -> list[Path]:
    paths: list[Path] = []
    for item in provided or []:
        path = Path(item)
        if path.is_dir():
            paths.extend(sorted(path.glob("*/results.json")))
            direct_result = path / "results.json"
            if direct_result.exists():
                paths.append(direct_result)
        else:
            paths.append(path)
    return paths


def discover_method_results(provided: list[str] | None, baseline_path: Path) -> list[Path]:
    paths = expand_method_roots(provided)
    paths.extend(sorted(Path("outputs").glob("*/results.json")))
    return [
        path
        for path in unique_paths(paths)
        if path.exists() and path != baseline_path and path.parent.name != "baseline"
    ]


def method_policy_entries(result: dict, artifact_path: Path, epsilon: float) -> list[tuple[str, str]]:
    policies = select_operating_point(result, epsilon).get("policies", {})
    directory_name = artifact_path.parent.name
    usable = sorted(name for name in policies if name not in CONTROL_POLICIES)
    if directory_name in usable:
        return [(directory_name, directory_name)]
    if len(usable) == 1:
        return [(directory_name, usable[0])]
    return [(name, name) for name in usable]


def companion_artifact(main_artifact: Path, filename: str) -> Path:
    return main_artifact if filename == "results.json" else main_artifact.with_name(filename)


def add_result(
    results: dict[str, dict[str, float]],
    method_name: str,
    artifact_path: Path,
    policy_name: str,
    fallback_data: Path,
    epsilon: float,
) -> None:
    if method_name in results:
        raise ValueError(f"Multiple artifacts produced the same method key {method_name!r}")
    result = load(artifact_path)
    point = select_operating_point(result, epsilon)
    policies = point.get("policies", {})
    if policy_name not in policies:
        raise ValueError(f"{artifact_path} has no policy {policy_name!r}")
    data = load_jsonl(data_path_for(result, fallback_data))
    results[method_name] = recompute_policy_metrics(policies[policy_name], data, slice_ids(data), point["epsilon"])


def build_scores(args: argparse.Namespace) -> dict:
    baseline_path = Path(args.baseline_results)
    method_paths = discover_method_results(args.method_results, baseline_path)
    scores = {
        "_metadata": {
            "slice": SLICE,
            "split": "deterministic stratified buffered two-fifths of original test examples",
            "split_seed": SPLIT_SEED,
        },
        "experiments": {},
    }

    for experiment_name, filename in EXPERIMENT_FILES.items():
        fallback_data = FALLBACK_DATA[filename]
        experiment_results: dict[str, dict[str, float]] = {}

        baseline_artifact = baseline_path if filename == "results.json" else baseline_path.with_name(filename)
        if baseline_artifact.exists():
            baseline_key = "naive_or_uncalibrated" if experiment_name == "risk_control" else "upper_only"
            add_result(experiment_results, baseline_key, baseline_artifact, "upper_only", fallback_data, args.epsilon)

        for main_artifact in method_paths:
            artifact = companion_artifact(main_artifact, filename)
            if not artifact.exists():
                continue
            result = load(artifact)
            for method_name, policy_name in method_policy_entries(result, artifact, args.epsilon):
                add_result(experiment_results, method_name, artifact, policy_name, fallback_data, args.epsilon)

        if experiment_results:
            scores["experiments"][experiment_name] = {"results": experiment_results}

    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method-results", action="append", default=None)
    parser.add_argument("method_artifacts", nargs="*")
    parser.add_argument("--baseline-results", default="outputs/baseline/results.json")
    parser.add_argument("--scores", default="scoring/scores_train.json")
    parser.add_argument("--epsilon", type=float, default=0.32)
    args = parser.parse_args()
    if args.method_artifacts:
        args.method_results = (args.method_results or []) + args.method_artifacts

    scores = build_scores(args)
    out = Path(args.scores)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(scores, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
