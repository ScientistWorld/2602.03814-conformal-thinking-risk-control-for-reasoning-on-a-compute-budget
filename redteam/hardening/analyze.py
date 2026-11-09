#!/usr/bin/env python3
"""Rank every audited candidate against the reference and measure paired test noise.

Inputs (written by redteam/hardening/run_candidates.sh):
  redteam/hardening/scores_test_all.json   hidden-test scores of every candidate
  redteam/hardening/scores_train_all.json  visible-train scores of every candidate
  logs/hardening_outcomes/<method>/<experiment>.json  per-instance test outcomes

Rank (as specified for this gym):
  sum_e weight_e * sum_m |coef_m| * dir_m * (candidate - reference) / std_m(population)
where dir_m = +1 if higher_is_better else -1 and std is the population standard
deviation of that metric across the attempts in the population.

Paired noise: every method sees identical held-out instances, so the standard
error of a candidate-minus-reference difference is computed from per-instance
influence values (linearised ratio for token savings), treating the test
instances as the sampling unit. Experiments use disjoint instances and are
combined as independent.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "eval" / "test"))
import hidden_tasks  # noqa: E402

REFERENCE = "conformal_thinking"
BASELINES = ["full_budget", "upper_only", "naive_calibration"]
HONEST = [
    "reference_rerun",
    "better_tighter_bound",
    "better_joint_calibration",
    "better_joint_tighter_bound",
    "variant_stricter_calibration",
    "weaker_confidence_only",
    "weaker_token_budget",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def results(scores: dict) -> dict[str, dict[str, dict]]:
    """{method: {experiment: metrics}}"""
    out: dict[str, dict[str, dict]] = {}
    for experiment, entry in scores["experiments"].items():
        for method, metrics in entry["results"].items():
            out.setdefault(method, {})[experiment] = metrics
    return out


def scored_metrics(reference: dict) -> dict[str, list[tuple[str, float, int]]]:
    out = {}
    for experiment, spec in reference["experiments"].items():
        rows = []
        for metric, mspec in spec["metrics"].items():
            if mspec["coefficient"]:
                rows.append((metric, abs(mspec["coefficient"]), 1 if mspec["higher_is_better"] else -1))
        out[experiment] = rows
    return out


def population_std(pool: list[dict], scored) -> dict[tuple[str, str], float]:
    std = {}
    for experiment, rows in scored.items():
        for metric, _, _ in rows:
            std[(experiment, metric)] = statistics.pstdev([m[experiment][metric] for m in pool])
    return std


def rank(candidate: dict, anchor: dict, std, scored, weights) -> dict:
    total = 0.0
    parts = {}
    for experiment, rows in scored.items():
        for metric, coef, direction in rows:
            scale = std[(experiment, metric)]
            value = 0.0
            if scale:
                value = weights[experiment] * coef * direction * (candidate[experiment][metric] - anchor[experiment][metric]) / scale
            parts[f"{experiment}.{metric}"] = value
            total += value
    return {"score": total, "contributions": parts}


def parse_outcomes(text: str) -> list[tuple[str, int]]:
    return [(item[0], int(item[1:])) for item in text.split(",") if item]


def per_instance(tasks, saved: list[dict]):
    """Average over operating points of each test instance's (correct, tokens used)."""
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
    """Return (diff_acc, se_acc, diff_sav, se_sav, se_combined_per_unit) for one experiment."""
    cand = per_instance(tasks, cand_saved)
    ref = per_instance(tasks, ref_saved)
    profiles = sorted(set(cand) & set(ref))
    k = len(profiles)
    diff_acc = diff_sav = 0.0
    var_acc = var_sav = 0.0
    z_combo_var = 0.0
    for profile in profiles:
        test = tasks[profile]["test"]
        full = [instance["budget_tokens"] for instance in test]
        n = len(test)
        fbar = sum(full) / n
        d_acc = [c[0] - r[0] for c, r in zip(cand[profile], ref[profile])]
        d_used = [r[1] - c[1] for c, r in zip(cand[profile], ref[profile])]  # savings difference numerator
        da = sum(d_acc) / n
        ds = sum(d_used) / sum(full)
        z_sav = [(u - ds * f) / fbar for u, f in zip(d_used, full)]
        diff_acc += da / k
        diff_sav += ds / k
        var_acc += statistics.pvariance(d_acc) / n / k**2
        var_sav += statistics.pvariance(z_sav) / n / k**2
        combo = [coef_acc * a + coef_sav * z for a, z in zip(d_acc, z_sav)]
        z_combo_var += statistics.pvariance(combo) / n / k**2
    return diff_acc, math.sqrt(var_acc), diff_sav, math.sqrt(var_sav), math.sqrt(z_combo_var)


def load_reference_phase1(test: dict, name: str) -> dict:
    return results(load(HERE / "scores_test_all.json"))[name]


def main() -> None:
    reference_spec = load(ROOT / "scoring" / "reference.json")
    scored = scored_metrics(reference_spec)
    weights = {e: spec["weight"] for e, spec in reference_spec["experiments"].items()}
    test = results(load(HERE / "scores_test_all.json"))
    failures = {e: dict(v.get("_failures", {})) for e, v in load(HERE / "scores_test_all.json")["experiments"].items()}
    isolated_path = HERE / "scores_test_isolated.json"
    rerun_isolated: list[str] = []
    identical_after_isolation: dict[str, bool] = {}
    if isolated_path.exists():
        # Phase 2: the current evaluator (one process per operating point). Its
        # values replace phase-1 values for every method it scored.
        isolated_scores = load(isolated_path)
        for name, metrics in results(isolated_scores).items():
            if name in test:
                identical_after_isolation[name] = test[name] == metrics
            test[name] = metrics
            rerun_isolated.append(name)
            for e, v in isolated_scores["experiments"].items():
                failures[e].pop(name, None)
                if name in v.get("_failures", {}):
                    failures[e][name] = v["_failures"][name]
    train_path = HERE / "scores_train_all.json"
    train = results(load(train_path)) if train_path.exists() else {}
    anchor = test[REFERENCE]

    quality_names = [REFERENCE] + [n for n in BASELINES + HONEST if n in test]
    quality = [test[n] for n in quality_names]
    everyone = list(test.values())
    std_quality = population_std(quality, scored)
    std_all = population_std(everyone, scored)

    # Paired noise against the reference on identical held-out instances.
    experiments = load(HERE / "scores_test_all.json")["_metadata"]["experiments"]
    keys = {(c["setting"], c["group"]) for c in experiments.values()}
    tasks = hidden_tasks.build_tasks(keys, 1000, load(HERE / "scores_test_all.json")["_metadata"]["test_size_per_profile"])
    outcome_root = ROOT / "logs" / "hardening_outcomes"

    report = {
        "reference": REFERENCE,
        "quality_population": quality_names,
        "rerun_with_isolation": rerun_isolated,
        "identical_after_isolation": identical_after_isolation,
        "methods": {},
    }
    before_path = HERE / "scores_test_before_isolation.json"
    if before_path.exists():
        before = results(load(before_path))
        before_failures = {e: v.get("_failures", {}) for e, v in load(before_path)["experiments"].items()}
        report["before_isolation"] = {}
        for name, metrics in before.items():
            if name == REFERENCE:
                continue
            std_b = population_std(quality + [metrics], scored)
            report["before_isolation"][name] = {
                "rank_quality_plus_self": rank(metrics, before[REFERENCE], std_b, scored, weights)["score"],
                "reference_identical_to_phase1": before[REFERENCE] == load_reference_phase1(test, REFERENCE),
                "test": {e: {m: metrics[e][m] for m in ("accuracy", "token_savings", "violation_rate")} for e in metrics},
                "failures": {e: before_failures[e][name] for e in before_failures if name in before_failures[e]},
            }
    for name, metrics in sorted(test.items()):
        own_quality = quality if name in quality_names else quality + [metrics]
        std_own = population_std(own_quality, scored)
        entry = {
            "test": {e: {m: metrics[e][m] for m in ("accuracy", "token_savings", "false_positive_risk", "false_negative_risk", "violation_rate")} for e in metrics},
            "train": {e: {m: train[name][e][m] for m in ("accuracy", "token_savings", "violation_rate")} for e in train.get(name, {})},
            "failures": {e: failures[e][name] for e in failures if name in failures[e]},
            "rank_quality_plus_self": rank(metrics, anchor, std_own, scored, weights)["score"],
            "rank_all_attempts": rank(metrics, anchor, std_all, scored, weights)["score"],
            "contributions_quality_plus_self": rank(metrics, anchor, std_own, scored, weights)["contributions"],
        }
        if train.get(name) and train.get(REFERENCE):
            entry["train_rank_vs_train_reference"] = rank(
                train[name], train[REFERENCE], population_std([train[n] for n in quality_names if n in train] + ([train[name]] if name not in quality_names else []), scored), scored, weights
            )["score"]
        # Paired noise (only where both ran without failure).
        noise = {}
        se_total_sq = 0.0
        for experiment, config in experiments.items():
            iso_root = ROOT / "logs" / "hardening_outcomes_isolated"
            root = iso_root if (iso_root / name / f"{experiment}.json").exists() and (iso_root / REFERENCE / f"{experiment}.json").exists() else outcome_root
            cand_file = root / name / f"{experiment}.json"
            ref_file = root / REFERENCE / f"{experiment}.json"
            if name == REFERENCE or not cand_file.exists() or not ref_file.exists():
                continue
            if name in failures.get(experiment, {}) or REFERENCE in failures.get(experiment, {}):
                continue
            coefs = {m: c for m, c, _ in scored[experiment]}
            sa = std_own[(experiment, "accuracy")] or 1.0
            ss = std_own[(experiment, "token_savings")] or 1.0
            da, sea, dsv, ses, se_unit = paired_noise(
                tasks[(config["setting"], config["group"])],
                load(cand_file),
                load(ref_file),
                coefs.get("accuracy", 0.0) / sa,
                coefs.get("token_savings", 0.0) / ss,
            )
            noise[experiment] = {"diff_accuracy": da, "se_accuracy": sea, "diff_token_savings": dsv, "se_token_savings": ses}
            se_total_sq += (weights[experiment] * se_unit) ** 2
        entry["paired_noise"] = noise
        entry["rank_se_quality_plus_self"] = math.sqrt(se_total_sq) if noise else None
        report["methods"][name] = entry

    (HERE / "analysis.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = ["| method | rank (quality+self) | paired SE | rank (all) | train rank | main acc | main savings | failed experiments |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for name, entry in sorted(report["methods"].items(), key=lambda item: -item[1]["rank_quality_plus_self"]):
        main = entry["test"]["adaptive_budget_efficiency"]
        se = entry["rank_se_quality_plus_self"]
        tr = entry.get("train_rank_vs_train_reference")
        lines.append(
            f"| {name} | {entry['rank_quality_plus_self']:+.3f} | {('%.3f' % se) if se is not None else '—'} | "
            f"{entry['rank_all_attempts']:+.3f} | {('%+.3f' % tr) if tr is not None else '—'} | {main['accuracy']:.3f} | "
            f"{main['token_savings']:.3f} | {', '.join(sorted(entry['failures'])) or '—'} |"
        )
    if "before_isolation" in report:
        lines += ["", "Pre-isolation hidden test (one policy process per experiment):", "", "| probe | rank before | failed experiments before |", "|---|---:|---|"]
        for name, entry in sorted(report["before_isolation"].items()):
            lines.append(f"| {name} | {entry['rank_quality_plus_self']:+.3f} | {', '.join(sorted(entry['failures'])) or '—'} |")
    (HERE / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
