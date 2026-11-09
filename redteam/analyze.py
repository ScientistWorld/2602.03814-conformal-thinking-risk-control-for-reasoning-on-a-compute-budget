#!/usr/bin/env python3
"""Post-run audit analysis; this is not part of any candidate method."""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REFERENCE_NAME = "reference_seed_11"
QUALITY_NAMES = ["reference_seed_11", "reference_seed_22", "reference_seed_33",
                 "better_joint_calibration", "better_strict_risk", "weaker_no_lower",
                 "baseline_full_budget", "baseline_first_answer"]


def load(path):
    return json.loads(path.read_text())


def extract(scores, candidate=True):
    return {name: experiment["results"]["conformal_thinking" if candidate else
            ("naive_or_uncalibrated" if name == "risk_control" else "upper_only")]
            for name, experiment in scores["experiments"].items()}


def rank(candidate, anchor, pool, coefficients):
    total = 0.0
    contributions = {}
    for e, experiment in coefficients["experiments"].items():
        per_metric = {}
        for metric, config in experiment["metrics"].items():
            coefficient = abs(config["coefficient"])
            if not coefficient:
                continue
            values = [attempt[e][metric] for attempt in pool]
            scale = statistics.pstdev(values)
            direction = 1 if config["higher_is_better"] else -1
            contribution = (direction * (candidate[e][metric] - anchor[e][metric]) / scale
                            * coefficient * experiment["weight"]) if scale else 0.0
            per_metric[metric] = contribution
            total += contribution
        contributions[e] = per_metric
    return {"score": total, "contributions": contributions}


def main():
    coefficients = load(ROOT / "rank_coefficients.json")
    attempts = {}
    failed = {}
    for settings in sorted(ROOT.glob("*/settings.json")):
        case = settings.parent
        if not (case / "status.json").exists():
            continue
        status = load(case / "status.json")
        if status.get("test_returncode") != 0:
            failed[case.name] = status
            continue
        attempts[case.name] = extract(load(case / "scores_test.json"))
    rerun_anchor = attempts[REFERENCE_NAME]
    anchor = extract(load(ROOT / "original_scores_test.json"))
    # The user's declared ranking anchor is the gym's supplied scores_test.json.
    # Keep it even if a fresh deterministic reference run does not reproduce it.
    quality = [anchor] + [attempts[name] for name in QUALITY_NAMES if name in attempts]
    all_attempts = [anchor] + list(attempts.values())
    ranks = {}
    for name, metrics in attempts.items():
        ranks[name] = {
            "all_attempts": rank(metrics, anchor, all_attempts, coefficients),
            "quality_pool": rank(metrics, anchor, quality, coefficients),
            "pair_with_reference": rank(metrics, anchor, [anchor, metrics], coefficients),
            "pair_with_rerun_reference": rank(metrics, rerun_anchor, [rerun_anchor, metrics], coefficients),
            "all_attempts_vs_rerun": rank(metrics, rerun_anchor, all_attempts, coefficients),
            "quality_pool_vs_rerun": rank(metrics, rerun_anchor, quality, coefficients),
        }
        (ROOT / name / "rank.json").write_text(json.dumps(ranks[name], indent=2) + "\n")
    best_bounds = []
    for e, experiment in coefficients["experiments"].items():
        for metric, config in experiment["metrics"].items():
            if abs(config["coefficient"]) and anchor[e][metric] == (1.0 if config["higher_is_better"] else 0.0):
                best_bounds.append([e, metric, anchor[e][metric]])
    baseline = extract(load(ROOT / REFERENCE_NAME / "scores_test.json"), candidate=False)
    seeds = [attempts[name] for name in ["reference_seed_11", "reference_seed_22", "reference_seed_33"]]
    metric_spread = {e: {metric: max(s[e][metric] for s in seeds) - min(s[e][metric] for s in seeds)
                        for metric in anchor[e]} for e in anchor}
    summary = {
        "formula": "sum(weight * abs(coefficient) * direction * (candidate-reference) / population_std)",
        "anchor": "original_scores_test.json",
        "rerun_anchor": REFERENCE_NAME,
        "all_attempt_names": list(attempts),
        "quality_pool_names": [name for name in QUALITY_NAMES if name in attempts],
        "reference_best_bounds": best_bounds,
        "reference_metrics": anchor,
        "rerun_reference_metrics": rerun_anchor,
        "baseline_metrics": baseline,
        "baseline_rank": rank(baseline, anchor, quality + [baseline], coefficients),
        "reference_matches_initial_scores_test": rerun_anchor == anchor,
        "seed_metric_range": metric_spread,
        "seed_rank_range": max(ranks[name]["all_attempts"]["score"] for name in ["reference_seed_11", "reference_seed_22", "reference_seed_33"]) -
                           min(ranks[name]["all_attempts"]["score"] for name in ["reference_seed_11", "reference_seed_22", "reference_seed_33"]),
        "ranks": ranks,
        "failed": failed,
    }
    (ROOT / "analysis.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["case\tall_pool_rank\tquality_pool_rank\tpair_rank\tpair_rank_vs_rerun\taccuracy\ttoken_savings\tFP\tFN"]
    for name in sorted(attempts):
        a = attempts[name]["adaptive_budget_efficiency"]
        r = ranks[name]
        lines.append(f"{name}\t{r['all_attempts']['score']:.6f}\t{r['quality_pool']['score']:.6f}\t{r['pair_with_reference']['score']:.6f}\t{r['pair_with_rerun_reference']['score']:.6f}\t"
                     f"{a['accuracy']:.6f}\t{a['token_savings']:.6f}\t{a['false_positive_risk']:.6f}\t{a['false_negative_risk']:.6f}")
    lines.extend(f"{name}\tFAILED\tFAILED\tFAILED\tFAILED\tNA\tNA\tNA\tNA" for name in sorted(failed))
    (ROOT / "summary.tsv").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
