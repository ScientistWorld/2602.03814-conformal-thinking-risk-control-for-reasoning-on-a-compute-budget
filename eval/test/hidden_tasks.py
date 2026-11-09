"""Held-out task generator for the hidden test.

This module is private to eval/test/. It holds the held-out (model, dataset)
profiles and the seeds of every held-out calibration pool and test set; the
visible train side never sees them. The trajectory process follows the
public development generator's documented parameter ranges so train and test
measure the same thing at comparable difficulty.
"""

from __future__ import annotations

import hashlib
import math
import random

_SECRET = "ct-hidden-7f3c91d2a8b54e06b1d9"

_RANGES = {
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
_INTEGER_KEYS = {"steps_min", "steps_max", "stride_min", "stride_max"}
NUM_PROFILES = 3
SETTINGS = {"natural": None, "ratio_3_1": 0.75, "ratio_1_1": 0.50, "ratio_1_3": 0.25}
NATURAL_SOLVABLE_PROBABILITY = 0.58


def derived_seed(*parts: object) -> int:
    text = ":".join([_SECRET, *map(str, parts)])
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def hidden_profiles(group: int = 0) -> list[dict]:
    """Held-out profiles; each profile group is a disjoint set of (model, dataset) pairs."""
    profiles = []
    for index in range(NUM_PROFILES):
        rng = random.Random(derived_seed("profile", group, index))
        profile = {}
        for key, (low, high) in _RANGES.items():
            profile[key] = rng.randint(low, high) if key in _INTEGER_KEYS else rng.uniform(low, high)
        profiles.append(profile)
    return profiles


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _clip(value: float) -> float:
    return max(0.001, min(0.999, value))


def _make_instance(rng: random.Random, p: dict, solvable_probability: float) -> dict:
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
            raw = p["conf_floor"] + gain * _sigmoid(p["conf_sharpness"] * (frac - solve_step / total_steps)) + noise
            if t >= solve_step:
                correct = rng.random() >= p["flicker_rate"]
            else:
                correct = rng.random() < p["early_lucky_rate"]
        else:
            raw = p["unsolv_base"] + p["unsolv_drift"] * frac + noise
            if false_confident:
                raw += p["false_conf_boost"] * _sigmoid(12.0 * (frac - 0.68))
            correct = rng.random() < p["unsolv_lucky_rate"]

        if correct:
            prediction = gold
        else:
            if previous_wrong is not None and rng.random() < stickiness:
                prediction = previous_wrong
            else:
                prediction = rng.choice(distractors)
            previous_wrong = prediction

        confidence = _clip(raw) ** p["conf_gamma"]
        eat = _clip(raw + rng.gauss(0.0, p["eat_noise"])) ** p["eat_gamma"]
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
    return {"gold": gold, "budget_tokens": steps[-1]["tokens"], "steps": steps}


def _solvable(instance: dict) -> bool:
    return instance["steps"][-1]["prediction"] == instance["gold"]


def generate(profile: dict, setting: str, size: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    target = SETTINGS[setting]
    if target is None:
        return [_make_instance(rng, profile, NATURAL_SOLVABLE_PROBABILITY) for _ in range(size)]
    want_solvable = int(round(size * target))
    want_unsolvable = size - want_solvable
    solvable_rows: list[dict] = []
    unsolvable_rows: list[dict] = []
    while len(solvable_rows) < want_solvable or len(unsolvable_rows) < want_unsolvable:
        row = _make_instance(rng, profile, target)
        if _solvable(row):
            if len(solvable_rows) < want_solvable:
                solvable_rows.append(row)
        elif len(unsolvable_rows) < want_unsolvable:
            unsolvable_rows.append(row)
    rows = solvable_rows + unsolvable_rows
    rng.shuffle(rows)
    return rows


def build_tasks(keys: set[tuple[str, int]], pool_size: int, test_size: int) -> dict[tuple[str, int], list[dict]]:
    """Return {(setting, profile group): [{"pool": [...], "test": [...]} per hidden profile]}."""
    tasks: dict[tuple[str, int], list[dict]] = {}
    for setting, group in sorted(keys):
        entries = []
        for index, profile in enumerate(hidden_profiles(group)):
            entries.append(
                {
                    "pool": generate(profile, setting, pool_size, derived_seed("pool", setting, group, index)),
                    "test": generate(profile, setting, test_size, derived_seed("test", setting, group, index)),
                }
            )
        tasks[(setting, group)] = entries
    return tasks
