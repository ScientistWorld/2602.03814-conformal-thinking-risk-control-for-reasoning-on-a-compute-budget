#!/usr/bin/env python3
"""Rank every audited candidate against the reference and measure paired test noise.

Inputs (written by redteam/hardening2/run_audit.sh):
  redteam/hardening2/scores_test_all.json     hidden test, every candidate (final gym)
  redteam/hardening2/scores_train_all.json    visible train, reference/baselines/honest variants
  redteam/hardening2/old_gym_scores_test.json new probes on the gym as it was before this iteration
  redteam/hardening/scores_test_all.json      the previous audit's population on the old gym
  logs/hardening2_outcomes/<method>/<experiment>.json  per-instance outcomes (paired noise)

Rank (as specified for this gym):
  sum_e weight_e * sum_m |coef_m| * dir_m * (candidate - reference) / std_m(population)
Population "Q": the reference, the baselines and the honest variants, plus the
candidate itself. Paired SE: every method sees identical held-out instances;
held-out instances are the sampling unit (linearised ratio for token savings).
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "eval" / "test"))
sys.dont_write_bytecode = True
try:  # an interrupted hidden-test run may have left the generator sealed
    os.chmod(ROOT / "eval" / "test" / "hidden_tasks.py", 0o644)
except OSError:
    pass
import hidden_tasks  # noqa: E402

REFERENCE = "conformal_thinking"
BASELINES = ["full_budget", "upper_only", "naive_calibration"]
HONEST = [
    "better_tighter_bound",
    "better_joint_calibration",
    "better_joint_tighter_bound",
    "variant_stricter_calibration",
    "weaker_confidence_only",
    "weaker_eat_only",
    "weaker_token_budget",
    "fast_reference",
]
OLD_HONEST = [
    "reference_rerun",
    "better_tighter_bound",
    "better_joint_calibration",
    "better_joint_tighter_bound",
    "variant_stricter_calibration",
    "weaker_confidence_only",
    "weaker_token_budget",
]
SHOWN = ("accuracy", "token_savings", "false_positive_risk", "false_negative_risk", "violation_rate")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def results(scores: dict) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for experiment, entry in scores["experiments"].items():
        for method, metrics in entry["results"].items():
            out.setdefault(method, {})[experiment] = metrics
    return out


def failures_of(scores: dict) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for experiment, entry in scores["experiments"].items():
        for method, reason in entry.get("_failures", {}).items():
            out.setdefault(method, {})[experiment] = reason
    return out


def scored_metrics(reference: dict) -> dict[str, list[tuple[str, float, int]]]:
    out = {}
    for experiment, spec in reference["experiments"].items():
        out[experiment] = [
            (metric, abs(m["coefficient"]), 1 if m["higher_is_better"] else -1)
            for metric, m in spec["metrics"].items()
            if m["coefficient"]
        ]
    return out


def population_std(pool: list[dict], scored) -> dict[tuple[str, str], float]:
    return {
        (experiment, metric): statistics.pstdev([m[experiment][metric] for m in pool])
        for experiment, rows in scored.items()
        for metric, _, _ in rows
    }


def rank(candidate: dict, anchor: dict, std, scored, weights) -> float:
    total = 0.0
    for experiment, rows in scored.items():
        for metric, coef, direction in rows:
            scale = std[(experiment, metric)]
            if scale:
                total += weights[experiment] * coef * direction * (candidate[experiment][metric] - anchor[experiment][metric]) / scale
    return total


def parse_outcomes(text: str) -> list[tuple[str, int]]:
    return [(item[0], int(item[1:])) for item in text.split(",") if item]


def per_instance(tasks, saved: list[dict]):
    sums: dict[int, list[list[float]]] = {}
    counts: dict[int, int] = {}
    for point in saved:
        profile = point["profile"]
        test = tasks[profile]["test"]
        acc = sums.setdefault(profile, [[0.0, 0.0] for _ in test])
        counts[profile] = counts.get(profile, 0) + 1
        for slot, (instance, (kind, index)) in zip(acc, zip(test, parse_outcomes(point["outcomes"]))):
            step = instance["steps"][index]
            slot[0] += float(kind != "d" and step["prediction"] == instance["gold"])
            slot[1] += step["tokens"]
    return {p: [[a / counts[p], u / counts[p]] for a, u in rows] for p, rows in sums.items()}


def paired_noise(tasks, cand_saved, ref_saved, coef_acc, coef_sav):
    cand = per_instance(tasks, cand_saved)
    ref = per_instance(tasks, ref_saved)
    profiles = sorted(set(cand) & set(ref))
    k = len(profiles)
    diff_acc = diff_sav = var_acc = var_sav = combo_var = 0.0
    for profile in profiles:
        test = tasks[profile]["test"]
        full = [instance["budget_tokens"] for instance in test]
        n = len(test)
        fbar = sum(full) / n
        d_acc = [c[0] - r[0] for c, r in zip(cand[profile], ref[profile])]
        d_used = [r[1] - c[1] for c, r in zip(cand[profile], ref[profile])]
        ds = sum(d_used) / sum(full)
        z_sav = [(u - ds * f) / fbar for u, f in zip(d_used, full)]
        diff_acc += sum(d_acc) / n / k
        diff_sav += ds / k
        var_acc += statistics.pvariance(d_acc) / n / k**2
        var_sav += statistics.pvariance(z_sav) / n / k**2
        combo_var += statistics.pvariance([coef_acc * a + coef_sav * z for a, z in zip(d_acc, z_sav)]) / n / k**2
    return diff_acc, math.sqrt(var_acc), diff_sav, math.sqrt(var_sav), math.sqrt(combo_var)


def main() -> None:
    spec = load(ROOT / "scoring" / "reference.json")
    scored = scored_metrics(spec)
    weights = {e: s["weight"] for e, s in spec["experiments"].items()}
    test_scores = load(HERE / "scores_test_all.json")
    test = results(test_scores)
    fails = failures_of(test_scores)
    train_path = HERE / "scores_train_all.json"
    train = results(load(train_path)) if train_path.exists() else {}
    anchor = test[REFERENCE]
    quality_names = [REFERENCE] + [n for n in BASELINES + HONEST if n in test]
    quality = [test[n] for n in quality_names]
    std_all = population_std(list(test.values()), scored)

    experiments = test_scores["_metadata"]["experiments"]
    keys = {(c["setting"], c["group"]) for c in experiments.values()}
    tasks = hidden_tasks.build_tasks(keys, 1000, test_scores["_metadata"]["test_size_per_profile"])
    outcome_root = ROOT / "logs" / "hardening2_outcomes"

    report: dict = {"reference": REFERENCE, "quality_population": quality_names, "methods": {}}
    for name, metrics in sorted(test.items()):
        own = quality if name in quality_names else quality + [metrics]
        std_own = population_std(own, scored)
        entry = {
            "test": {e: {m: metrics[e][m] for m in SHOWN} for e in metrics},
            "failures": fails.get(name, {}),
            "rank_quality_plus_self": rank(metrics, anchor, std_own, scored, weights),
            "rank_all_attempts": rank(metrics, anchor, std_all, scored, weights),
        }
        if name in train and REFERENCE in train:
            pool = [train[n] for n in quality_names if n in train] + ([train[name]] if name not in quality_names else [])
            entry["train"] = {e: {m: train[name][e][m] for m in SHOWN} for e in train[name]}
            entry["train_rank"] = rank(train[name], train[REFERENCE], population_std(pool, scored), scored, weights)
        noise = {}
        se_sq = 0.0
        for experiment, config in experiments.items():
            cand_file = outcome_root / name / f"{experiment}.json"
            ref_file = outcome_root / REFERENCE / f"{experiment}.json"
            if name == REFERENCE or not cand_file.exists() or not ref_file.exists() or experiment in entry["failures"]:
                continue
            coefs = {m: c for m, c, _ in scored[experiment]}
            da, sea, dsv, ses, se_unit = paired_noise(
                tasks[(config["setting"], config["group"])],
                load(cand_file),
                load(ref_file),
                coefs.get("accuracy", 0.0) / (std_own[(experiment, "accuracy")] or 1.0),
                coefs.get("token_savings", 0.0) / (std_own[(experiment, "token_savings")] or 1.0),
            )
            noise[experiment] = {"diff_accuracy": da, "se_accuracy": sea, "diff_token_savings": dsv, "se_token_savings": ses}
            se_sq += (weights[experiment] * se_unit) ** 2
        entry["paired_noise"] = noise
        entry["rank_se"] = math.sqrt(se_sq) if noise else None
        report["methods"][name] = entry

    # Before: the new probes on the gym as it was before this iteration, ranked
    # against that gym's reference within the previous audit's population.
    old_path = HERE / "old_gym_scores_test.json"
    if old_path.exists():
        old_scores = load(old_path)
        old_new = results(old_scores)
        old_fails = failures_of(old_scores)
        prev = results(load(ROOT / "redteam" / "hardening" / "scores_test_all.json"))
        old_anchor = prev[REFERENCE]
        old_quality = [prev[n] for n in [REFERENCE, *BASELINES, *OLD_HONEST] if n in prev]
        report["before"] = {}
        for name, metrics in sorted(old_new.items()):
            if name == "full_budget":
                continue
            std_b = population_std(old_quality + [metrics], scored)
            report["before"][name] = {
                "rank_quality_plus_self": rank(metrics, old_anchor, std_b, scored, weights),
                "test": {e: {m: metrics[e][m] for m in SHOWN} for e in metrics},
                "failures": old_fails.get(name, {}),
                "old_reference_test": {e: {m: old_anchor[e][m] for m in SHOWN} for e in old_anchor},
            }

    (HERE / "analysis.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "| method | rank Q | paired SE | rank all | train rank | main acc / savings | risk_control acc / savings | 1:3 acc / savings | failed |",
        "|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for name, entry in sorted(report["methods"].items(), key=lambda item: -item[1]["rank_quality_plus_self"]):
        t = entry["test"]
        se = entry["rank_se"]
        tr = entry.get("train_rank")
        cell = lambda e: f"{t[e]['accuracy']:.3f} / {t[e]['token_savings']:.3f}"
        lines.append(
            f"| {name} | {entry['rank_quality_plus_self']:+.3f} | {('%.3f' % se) if se is not None else '—'} | "
            f"{entry['rank_all_attempts']:+.3f} | {('%+.3f' % tr) if tr is not None else '—'} | {cell('adaptive_budget_efficiency')} | "
            f"{cell('risk_control')} | {cell('difficulty_mix_1_3')} | {', '.join(sorted(entry['failures'])) or '—'} |"
        )
    if "before" in report:
        lines += ["", "Before (gym as of the start of this iteration):", "", "| probe | rank Q before | risk_control acc / savings / violation | failed |", "|---|---:|---|---|"]
        for name, entry in report["before"].items():
            rc = entry["test"]["risk_control"]
            lines.append(
                f"| {name} | {entry['rank_quality_plus_self']:+.3f} | {rc['accuracy']:.3f} / {rc['token_savings']:.3f} / {rc['violation_rate']:.3f} | "
                f"{', '.join(sorted(entry['failures'])) or '—'} |"
            )
    (HERE / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
