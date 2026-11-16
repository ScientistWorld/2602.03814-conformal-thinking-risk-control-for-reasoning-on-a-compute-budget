#!/usr/bin/env python3
"""Public generator of synthetic reasoning trajectories (development data).

The paper evaluates early stopping on reasoning-model trajectories split into
chunks. At every chunk the model yields a trial answer, scalar uncertainty
signals and a cumulative token count. This module simulates such trajectories
so the benchmark runs without large-model inference.

Each *profile* plays the role of one (reasoning model, dataset) pair. What the
paper observes across models and datasets, and what the profiles reproduce:

* Which stopping signal is most informative differs between (model, dataset)
  pairs and with the target risk (paper Fig. 1 right, Fig. 5). Every signal
  channel has its own lag behind the moment the answer becomes correct, its own
  noise level, tail weight and autocorrelation, its own per-question bias, and
  its own susceptibility to *false confidence* (hopeless runs that settle on a
  wrong answer and look confident).
* Hopeless runs either stay flat, wander, or become falsely confident late;
  solvable runs become correct at some chunk and the signals rise after it
  (strongly for most questions, weakly for some, late for others).
* Trial answers are opaque numeric strings from one vocabulary. Wrong answers
  persist across chunks and correct answers can flicker, so answer text alone
  does not reveal correctness. Chunk lengths vary.

The three public profiles below are the visible development profiles used by
``eval/train``. They are *not* a description of the held-out profiles: the
held-out test uses other (model, dataset) pairs from a broader process whose
parameters and mechanisms are not published. A stopping rule therefore has to
be set from each profile's own labelled calibration data.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

CHANNELS = ("confidence", "eat_confidence")

PUBLIC_PROFILES = {
    # Confidence is the sharper signal here; the EAT-style signal lags and is
    # fooled more often by falsely confident runs.
    "public_a": {
        "steps": [10, 18], "stride": [24, 46], "chunk_cv": 0.25,
        "solve_latest_frac": 0.58, "solve_shape": [1.2, 1.5],
        "solvable_mix": {"clean": 0.72, "muted": 0.14, "late_signal": 0.14},
        "unsolvable_mix": {"flat": 0.45, "wander": 0.30, "false_confident": 0.25},
        "rise_width": 3.0, "rise_knots": [0.0, 0.3, 0.6, 0.85, 1.0],
        "muted_clarity": [0.35, 0.6], "drift": [0.0, 0.25], "wander_amp": 0.3,
        "progress": [0.2, 0.4], "ease_lift": 0.06,
        "fc_onset": [0.45, 0.85], "fc_boost": [0.65, 1.0],
        "early_lucky_rate": 0.05, "flicker_rate": 0.04, "unsolv_lucky_rate": 0.006,
        "wrong_stickiness": 0.55, "fc_stickiness": 0.9,
        "channels": {
            "confidence": {"floor": 0.15, "gain": 0.78, "gamma": 1.0, "noise": 0.035, "df": 10, "rho": 0.3,
                           "offset_sd": 0.03, "lag": 0, "late_lag": 3, "fooled": 0.3, "attenuation": 0.15},
            "eat_confidence": {"floor": 0.12, "gain": 0.75, "gamma": 1.3, "noise": 0.06, "df": 5, "rho": 0.4,
                               "offset_sd": 0.06, "lag": 1, "late_lag": 4, "fooled": 0.75, "attenuation": 0.2},
        },
    },
    # Confidence is badly calibrated across questions and nearly always fooled
    # by falsely confident runs; the EAT-style signal is the reliable one.
    "public_b": {
        "steps": [9, 17], "stride": [22, 42], "chunk_cv": 0.35,
        "solve_latest_frac": 0.62, "solve_shape": [1.0, 1.2],
        "solvable_mix": {"clean": 0.66, "muted": 0.18, "late_signal": 0.16},
        "unsolvable_mix": {"flat": 0.40, "wander": 0.30, "false_confident": 0.30},
        "rise_width": 3.5, "rise_knots": [0.0, 0.2, 0.5, 0.8, 1.0],
        "muted_clarity": [0.35, 0.6], "drift": [0.0, 0.3], "wander_amp": 0.3,
        "progress": [0.15, 0.35], "ease_lift": 0.05,
        "fc_onset": [0.4, 0.8], "fc_boost": [0.7, 1.0],
        "early_lucky_rate": 0.05, "flicker_rate": 0.06, "unsolv_lucky_rate": 0.004,
        "wrong_stickiness": 0.65, "fc_stickiness": 0.85,
        "channels": {
            "confidence": {"floor": 0.18, "gain": 0.72, "gamma": 0.8, "noise": 0.05, "df": 6, "rho": 0.3,
                           "offset_sd": 0.1, "lag": 0, "late_lag": 3, "fooled": 0.9, "attenuation": 0.25},
            "eat_confidence": {"floor": 0.1, "gain": 0.8, "gamma": 1.2, "noise": 0.035, "df": 12, "rho": 0.3,
                               "offset_sd": 0.03, "lag": 1, "late_lag": 2, "fooled": 0.12, "attenuation": 0.1},
        },
    },
    # Confidence reacts first but is fooled by falsely confident runs; the
    # EAT-style signal reacts later but is rarely fooled. Which one is more
    # efficient depends on the target risk.
    "public_c": {
        "steps": [11, 19], "stride": [26, 50], "chunk_cv": 0.2,
        "solve_latest_frac": 0.52, "solve_shape": [1.5, 1.3],
        "solvable_mix": {"clean": 0.76, "muted": 0.12, "late_signal": 0.12},
        "unsolvable_mix": {"flat": 0.40, "wander": 0.25, "false_confident": 0.35},
        "rise_width": 2.5, "rise_knots": [0.0, 0.35, 0.65, 0.9, 1.0],
        "muted_clarity": [0.4, 0.65], "drift": [0.0, 0.2], "wander_amp": 0.25,
        "progress": [0.2, 0.45], "ease_lift": 0.07,
        "fc_onset": [0.5, 0.9], "fc_boost": [0.6, 0.95],
        "early_lucky_rate": 0.07, "flicker_rate": 0.03, "unsolv_lucky_rate": 0.009,
        "wrong_stickiness": 0.45, "fc_stickiness": 0.92,
        "channels": {
            "confidence": {"floor": 0.2, "gain": 0.72, "gamma": 1.1, "noise": 0.03, "df": 10, "rho": 0.2,
                           "offset_sd": 0.03, "lag": 0, "late_lag": 2, "fooled": 0.95, "attenuation": 0.2},
            "eat_confidence": {"floor": 0.15, "gain": 0.78, "gamma": 0.9, "noise": 0.035, "df": 10, "rho": 0.3,
                               "offset_sd": 0.03, "lag": 2, "late_lag": 3, "fooled": 0.05, "attenuation": 0.1},
        },
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


def clip(value: float) -> float:
    return max(0.001, min(0.999, value))


def choose(rng: random.Random, weights: dict) -> str:
    total = sum(weights.values())
    pick = rng.random() * total
    for key, weight in weights.items():
        pick -= weight
        if pick <= 0:
            return key
    return key


def rise(x: float, knots: list) -> float:
    """Monotone piecewise-linear rise: 0 for x <= 0, 1 for x >= 1, through the knots."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    pos = x * (len(knots) - 1)
    i = int(pos)
    return knots[i] + (knots[i + 1] - knots[i]) * (pos - i)


def heavy_noise(rng: random.Random, df: float) -> float:
    """Unit-variance Student-t draw."""
    z = rng.gauss(0.0, 1.0)
    chi = rng.gammavariate(df / 2.0, 2.0)
    return z / math.sqrt(chi / df) * math.sqrt((df - 2.0) / df)


def make_instance(rng: random.Random, p: dict, solvable_probability: float) -> dict:
    """Simulate one reasoning trajectory; returns gold, budget and chunks."""
    total_steps = rng.randint(*p["steps"])
    stride = rng.randint(*p["stride"])
    gold = str(rng.randint(0, 9999))
    distractors: list[str] = []
    for _ in range(rng.randint(2, 4)):
        candidate = str(rng.randint(0, 9999))
        while candidate == gold or candidate in distractors:
            candidate = str(rng.randint(0, 9999))
        distractors.append(candidate)

    solvable = rng.random() < solvable_probability
    knots = p["rise_knots"]
    width = p["rise_width"]
    if solvable:
        kind = choose(rng, p["solvable_mix"])
        latest = max(4, int(total_steps * p["solve_latest_frac"]))
        solve_step = 3 + int(rng.betavariate(*p["solve_shape"]) * (latest - 2))
        solve_step = min(solve_step, latest)
        clarity = rng.uniform(*p["muted_clarity"]) if kind == "muted" else rng.uniform(0.9, 1.05)
        progress = rng.uniform(*p["progress"])
    else:
        kind = choose(rng, p["unsolvable_mix"])
        solve_step = total_steps + 1
        drift = rng.uniform(*p["drift"])
        onset = max(2, int(round(rng.uniform(*p["fc_onset"]) * total_steps)))
        boost = rng.uniform(*p["fc_boost"])
    stickiness = p["fc_stickiness"] if kind == "false_confident" else p["wrong_stickiness"]

    channel_state = {}
    for name in CHANNELS:
        ch = p["channels"][name]
        channel_state[name] = {
            "offset": rng.gauss(0.0, ch["offset_sd"]),
            "fooled": rng.random() < ch["fooled"],
            "lag": ch["lag"] + (ch["late_lag"] if kind == "late_signal" else 0),
            "noise": 0.0,
        }

    wander = 0.0
    tokens = 0
    steps = []
    previous_wrong: str | None = None
    for t in range(1, total_steps + 1):
        frac = t / total_steps
        tokens += max(1, int(round(stride * math.exp(rng.gauss(0.0, p["chunk_cv"]) - p["chunk_cv"] ** 2 / 2))))
        if solvable:
            if t >= solve_step:
                correct = rng.random() >= p["flicker_rate"]
            else:
                correct = rng.random() < p["early_lucky_rate"]
        else:
            correct = rng.random() < p["unsolv_lucky_rate"]
            if kind == "wander":
                wander = max(-1.0, min(1.0, wander + rng.gauss(0.0, 0.4)))

        if correct:
            prediction = gold
        else:
            if previous_wrong is not None and rng.random() < stickiness:
                prediction = previous_wrong
            else:
                prediction = rng.choice(distractors)
            previous_wrong = prediction

        signals = {}
        for name in CHANNELS:
            ch = p["channels"][name]
            state = channel_state[name]
            if solvable:
                # Progress before the answer becomes correct, then a rise after it
                # (delayed by the channel's lag); plus a small question-level lift.
                start = solve_step + state["lag"]
                latent = p["ease_lift"] + clarity * (
                    progress * min(1.0, t / start) + (1.0 - progress) * rise((t - start + 1) / width, knots)
                )
            else:
                latent = drift * frac
                if kind == "wander":
                    latent += p["wander_amp"] * (0.5 + 0.5 * wander)
                elif kind == "false_confident":
                    share = 1.0 if state["fooled"] else ch["attenuation"]
                    latent += share * boost * rise((t - onset - state["lag"] + 1) / width, knots)
            rho = ch["rho"]
            state["noise"] = rho * state["noise"] + math.sqrt(1.0 - rho * rho) * ch["noise"] * heavy_noise(rng, ch["df"])
            raw = ch["floor"] + ch["gain"] * latent + state["offset"] + state["noise"]
            signals[name] = round(clip(raw) ** ch["gamma"], 6)
        steps.append({"step": t, "tokens": tokens, "prediction": prediction, "signals": signals})

    budget = steps[-1]["tokens"]
    for step in steps:
        step["signals"]["token_fraction"] = round(step["tokens"] / budget, 6)
    return {"gold": gold, "budget_tokens": budget, "steps": steps}


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
