#!/usr/bin/env python3
"""Public generator of synthetic reasoning trajectories (development data).

The paper evaluates early stopping on reasoning-model trajectories that are
split into chunks. At every chunk the model yields a trial answer, scalar
uncertainty signals and a cumulative token count. This module simulates such
trajectories so that the benchmark is runnable without large-model inference.

Each *profile* plays the role of one (reasoning model, dataset) pair. Profiles
differ in how their signals map to correctness (signal scale/curvature, noise,
how often unsolvable runs become falsely confident, how sticky wrong answers
are), so a stopping rule tuned on one profile does not transfer verbatim to
another: it has to be calibrated on that profile's labelled calibration data.

Public profiles below are used by the visible train evaluator. The held-out
test evaluator draws its own profiles from the same documented parameter
ranges (see ``PROFILE_RANGES``) with private seeds.

Trial answers are opaque numeric strings. Correct and wrong answers come from
the same vocabulary, wrong answers can persist across chunks, and correct
answers can flicker, so answer text alone does not reveal correctness.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

# Documented ranges for every profile parameter. Public profiles and held-out
# profiles are both drawn from (or lie inside) these ranges.
PROFILE_RANGES = {
    "steps_min": (9, 11),
    "steps_max": (16, 20),
    "stride_min": (20, 28),
    "stride_max": (40, 52),
    "solve_latest_frac": (0.5, 0.65),
    "conf_floor": (0.12, 0.24),
    "conf_gain": (0.62, 0.8),
    "conf_sharpness": (7.0, 12.0),
    "muted_rate": (0.08, 0.22),
    "unsolv_base": (0.06, 0.16),
    "unsolv_drift": (0.12, 0.28),
    "false_confident_rate": (0.12, 0.26),
    "false_conf_boost": (0.28, 0.42),
    "noise": (0.025, 0.05),
    "eat_noise": (0.04, 0.07),
    "early_lucky_rate": (0.03, 0.08),
    "flicker_rate": (0.02, 0.07),
    "unsolv_lucky_rate": (0.002, 0.01),
    "wrong_stickiness": (0.4, 0.7),
    "false_conf_stickiness": (0.8, 0.95),
    "conf_gamma": (0.6, 1.6),
    "eat_gamma": (0.6, 1.6),
}

PUBLIC_PROFILES = {
    "public_a": {
        "steps_min": 10, "steps_max": 18, "stride_min": 24, "stride_max": 46,
        "solve_latest_frac": 0.58, "conf_floor": 0.18, "conf_gain": 0.76,
        "conf_sharpness": 10.0, "muted_rate": 0.12, "unsolv_base": 0.10,
        "unsolv_drift": 0.20, "false_confident_rate": 0.18, "false_conf_boost": 0.34,
        "noise": 0.035, "eat_noise": 0.055, "early_lucky_rate": 0.06,
        "flicker_rate": 0.04, "unsolv_lucky_rate": 0.006, "wrong_stickiness": 0.55,
        "false_conf_stickiness": 0.9, "conf_gamma": 1.0, "eat_gamma": 1.0,
    },
    "public_b": {
        "steps_min": 9, "steps_max": 17, "stride_min": 22, "stride_max": 42,
        "solve_latest_frac": 0.62, "conf_floor": 0.14, "conf_gain": 0.70,
        "conf_sharpness": 8.0, "muted_rate": 0.18, "unsolv_base": 0.08,
        "unsolv_drift": 0.25, "false_confident_rate": 0.22, "false_conf_boost": 0.38,
        "noise": 0.045, "eat_noise": 0.065, "early_lucky_rate": 0.05,
        "flicker_rate": 0.06, "unsolv_lucky_rate": 0.004, "wrong_stickiness": 0.65,
        "false_conf_stickiness": 0.85, "conf_gamma": 1.4, "eat_gamma": 0.8,
    },
    "public_c": {
        "steps_min": 11, "steps_max": 19, "stride_min": 26, "stride_max": 50,
        "solve_latest_frac": 0.52, "conf_floor": 0.22, "conf_gain": 0.66,
        "conf_sharpness": 11.0, "muted_rate": 0.10, "unsolv_base": 0.14,
        "unsolv_drift": 0.15, "false_confident_rate": 0.14, "false_conf_boost": 0.30,
        "noise": 0.03, "eat_noise": 0.045, "early_lucky_rate": 0.07,
        "flicker_rate": 0.03, "unsolv_lucky_rate": 0.009, "wrong_stickiness": 0.45,
        "false_conf_stickiness": 0.92, "conf_gamma": 0.7, "eat_gamma": 1.3,
    },
}

# Solvable fraction used when generating each benchmark setting. ``None``
# means the profile's natural mix (instances are generated with probability
# 0.58 of being solvable); ratio settings are built exactly by labelling each
# generated instance as solvable/unsolvable under the full budget (is the
# answer at the final chunk correct?) and keeping the requested counts, as in
# the paper's subsampling protocol.
SETTINGS = {
    "natural": None,
    "ratio_3_1": 0.75,
    "ratio_1_1": 0.50,
    "ratio_1_3": 0.25,
}
NATURAL_SOLVABLE_PROBABILITY = 0.58


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def clip(value: float) -> float:
    return max(0.001, min(0.999, value))


def make_instance(rng: random.Random, profile: dict, solvable_probability: float) -> dict:
    """Simulate one reasoning trajectory; returns gold, budget and steps."""
    p = profile
    total_steps = rng.randint(int(p["steps_min"]), int(p["steps_max"]))
    stride = rng.randint(int(p["stride_min"]), int(p["stride_max"]))
    gold = str(rng.randint(0, 9999))
    distractors: list[str] = []
    num_distractors = rng.randint(2, 4)
    while len(distractors) < num_distractors:
        candidate = str(rng.randint(0, 9999))
        if candidate != gold and candidate not in distractors:
            distractors.append(candidate)

    solvable = rng.random() < solvable_probability
    latest = max(4, int(total_steps * p["solve_latest_frac"]))
    solve_step = rng.randint(3, latest) if solvable else total_steps + 1
    muted = solvable and rng.random() < p["muted_rate"]
    false_confident = (not solvable) and rng.random() < p["false_confident_rate"]
    stickiness = p["false_conf_stickiness"] if false_confident else p["wrong_stickiness"]

    steps = []
    previous_wrong: str | None = None
    for t in range(1, total_steps + 1):
        frac = t / total_steps
        tokens = max(1, t * stride + rng.randint(-5, 5))
        noise = rng.gauss(0.0, p["noise"])
        if solvable:
            gain = p["conf_gain"] * (0.45 if muted else 1.0)
            raw = p["conf_floor"] + gain * sigmoid(p["conf_sharpness"] * (frac - solve_step / total_steps)) + noise
            if t >= solve_step:
                correct = rng.random() >= p["flicker_rate"]
            else:
                correct = rng.random() < p["early_lucky_rate"]
        else:
            raw = p["unsolv_base"] + p["unsolv_drift"] * frac + noise
            if false_confident:
                raw += p["false_conf_boost"] * sigmoid(12.0 * (frac - 0.68))
            correct = rng.random() < p["unsolv_lucky_rate"]

        if correct:
            prediction = gold
        else:
            if previous_wrong is not None and rng.random() < stickiness:
                prediction = previous_wrong
            else:
                prediction = rng.choice(distractors)
            previous_wrong = prediction

        confidence = clip(raw) ** p["conf_gamma"]
        eat = clip(raw + rng.gauss(0.0, p["eat_noise"])) ** p["eat_gamma"]
        steps.append(
            {
                "step": t,
                "tokens": tokens,
                "prediction": prediction,
                "signals": {
                    "confidence": round(confidence, 6),
                    "eat_confidence": round(eat, 6),
                    "token_fraction": round(frac, 6),
                },
            }
        )

    return {
        "gold": gold,
        "budget_tokens": steps[-1]["tokens"],
        "steps": steps,
    }


def is_solvable(instance: dict) -> bool:
    """Solvable under the full budget: the answer at the final chunk is correct."""
    return instance["steps"][-1]["prediction"] == instance["gold"]


def generate_split(profile: dict, setting: str, size: int, seed: int, id_prefix: str) -> list[dict]:
    """Generate ``size`` labelled instances for one profile and setting."""
    rng = random.Random(seed)
    target = SETTINGS[setting]
    rows: list[dict] = []
    if target is None:
        while len(rows) < size:
            rows.append(make_instance(rng, profile, NATURAL_SOLVABLE_PROBABILITY))
    else:
        want_solvable = int(round(size * target))
        want_unsolvable = size - want_solvable
        solvable_rows: list[dict] = []
        unsolvable_rows: list[dict] = []
        while len(solvable_rows) < want_solvable or len(unsolvable_rows) < want_unsolvable:
            # Over-generate the scarcer class, then subsample by full-budget label.
            row = make_instance(rng, profile, target)
            bucket = solvable_rows if is_solvable(row) else unsolvable_rows
            limit = want_solvable if bucket is solvable_rows else want_unsolvable
            if len(bucket) < limit:
                bucket.append(row)
        rows = solvable_rows + unsolvable_rows
        rng.shuffle(rows)
    for index, row in enumerate(rows):
        row["id"] = f"{id_prefix}{index:05d}"
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", choices=sorted(PUBLIC_PROFILES), default="public_a")
    parser.add_argument("--setting", choices=sorted(SETTINGS), default="natural")
    parser.add_argument("--size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=260203814)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = generate_split(PUBLIC_PROFILES[args.profile], args.setting, args.size, args.seed, "dev")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            row["solvable_under_budget"] = is_solvable(row)
            handle.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
