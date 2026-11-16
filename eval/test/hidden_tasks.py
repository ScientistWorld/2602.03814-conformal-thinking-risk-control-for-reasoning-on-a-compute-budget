"""Held-out task generator for the hidden test.

This module is private to eval/test/. It holds the held-out (model, dataset)
profiles and the seeds of every held-out calibration pool and test set; the
visible train side never sees them.

The trajectory process measures the same thing as the public development
generator (chunked reasoning runs with trial answers, confidence-type signals
and token counts; signals whose informativeness differs between profiles and
target risks), at comparable difficulty. It is deliberately broader than the
public generator: profile parameters come from wider private ranges with
randomly shaped curves, and several mechanisms appear only here (confident
intermediate mistakes, runs that show no progress and then solve late, runs
that reach the correct answer and later abandon it, and signal noise that
grows over the run). A method therefore cannot reproduce the held-out process by fitting the
public generator's parameters.
"""

from __future__ import annotations

import hashlib
import math
import random

_SECRET = "ct-hidden-v2-5e81c0a94b7d2f36a1c8"

NUM_PROFILES = 3
CHANNELS = ("confidence", "eat_confidence")
SETTINGS = {"natural": None, "ratio_3_1": 0.75, "ratio_1_1": 0.50, "ratio_1_3": 0.25}
NATURAL_SOLVABLE_PROBABILITY = 0.58

# Each profile group holds one profile per signal regime (which signal is the
# more informative one), in a private order, with all other parameters drawn
# at random.
_REGIMES = {0: ["conf", "eat", "cross"], 1: ["eat", "cross", "conf"]}


def derived_seed(*parts: object) -> int:
    text = ":".join([_SECRET, *map(str, parts)])
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _span(rng: random.Random, low: tuple[float, float], high: tuple[float, float]) -> list[float]:
    return [rng.uniform(*low), rng.uniform(*high)]


def _channel(rng: random.Random, quality: str) -> dict:
    """quality: 'good', 'poor' (noisy, biased, often fooled), 'fast_fooled' or 'slow_robust'."""
    ch = {
        "floor": rng.uniform(0.08, 0.22),
        "gain": rng.uniform(0.68, 0.82),
        "gamma": rng.uniform(0.7, 1.4),
        "df": rng.uniform(4.0, 15.0),
        "rho": rng.uniform(0.1, 0.5),
        "late_lag": rng.randint(2, 4),
        "attenuation": rng.uniform(0.05, 0.3),
        "noise_growth": rng.uniform(0.2, 0.9),
    }
    if quality == "good":
        ch.update(noise=rng.uniform(0.025, 0.045), offset_sd=rng.uniform(0.02, 0.04), lag=rng.randint(0, 1), fooled=rng.uniform(0.1, 0.4), spike_seen=rng.uniform(0.3, 0.6))
    elif quality == "poor":
        ch.update(noise=rng.uniform(0.045, 0.07), offset_sd=rng.uniform(0.06, 0.11), lag=rng.randint(0, 2), fooled=rng.uniform(0.7, 1.0), spike_seen=rng.uniform(0.7, 1.0))
    elif quality == "fast_fooled":
        ch.update(noise=rng.uniform(0.025, 0.04), offset_sd=rng.uniform(0.02, 0.04), lag=0, fooled=rng.uniform(0.85, 1.0), spike_seen=rng.uniform(0.8, 1.0))
    else:  # slow_robust
        ch.update(noise=rng.uniform(0.03, 0.045), offset_sd=rng.uniform(0.02, 0.04), lag=rng.randint(2, 3), fooled=rng.uniform(0.0, 0.1), spike_seen=rng.uniform(0.2, 0.45))
    return ch


def _profile(rng: random.Random, regime: str) -> dict:
    increments = [rng.uniform(0.5, 1.5) for _ in range(4)]
    total = sum(increments)
    knots = [0.0]
    for inc in increments:
        knots.append(knots[-1] + inc / total)
    knots[-1] = 1.0
    if regime == "conf":
        channels = {"confidence": _channel(rng, "good"), "eat_confidence": _channel(rng, "poor")}
    elif regime == "eat":
        channels = {"confidence": _channel(rng, "poor"), "eat_confidence": _channel(rng, "good")}
    else:
        channels = {"confidence": _channel(rng, "fast_fooled"), "eat_confidence": _channel(rng, "slow_robust")}
    steps_min = rng.randint(8, 12)
    stride_min = rng.randint(18, 30)
    return {
        "regime": regime,
        "steps": [steps_min, rng.randint(16, 22)],
        "stride": [stride_min, rng.randint(38, 60)],
        "chunk_cv": rng.uniform(0.1, 0.45),
        "solve_latest_frac": rng.uniform(0.45, 0.68),
        "solve_shape": [rng.uniform(0.8, 2.2), rng.uniform(0.8, 2.2)],
        "solvable_mix": {
            "clean": rng.uniform(0.55, 0.8),
            "muted": rng.uniform(0.08, 0.25),
            "late_signal": rng.uniform(0.06, 0.22),
            "late_flip": rng.uniform(0.0, 0.08),
            "silent": rng.uniform(0.08, 0.2),
        },
        "unsolvable_mix": {
            "flat": rng.uniform(0.25, 0.55),
            "wander": rng.uniform(0.15, 0.4),
            "false_confident": rng.uniform(0.15, 0.38) if regime != "cross" else rng.uniform(0.25, 0.4),
        },
        "rise_width": rng.uniform(2.0, 4.5),
        "rise_knots": knots,
        "muted_clarity": _span(rng, (0.3, 0.45), (0.55, 0.7)),
        "drift": [0.0, rng.uniform(0.15, 0.32)],
        "wander_amp": rng.uniform(0.2, 0.35),
        "progress": _span(rng, (0.12, 0.25), (0.3, 0.48)),
        "ease_lift": rng.uniform(0.03, 0.09),
        "fc_onset": _span(rng, (0.35, 0.55), (0.75, 0.92)),
        "fc_boost": _span(rng, (0.55, 0.72), (0.9, 1.0)),
        "flip_drop": _span(rng, (0.3, 0.45), (0.55, 0.75)),
        "spike_rate": rng.uniform(0.06, 0.16),
        "spike_height": _span(rng, (0.45, 0.6), (0.8, 0.95)),
        "early_lucky_rate": rng.uniform(0.02, 0.08),
        "flicker_rate": rng.uniform(0.02, 0.08),
        "unsolv_lucky_rate": rng.uniform(0.002, 0.01),
        "wrong_stickiness": rng.uniform(0.35, 0.75),
        "fc_stickiness": rng.uniform(0.8, 0.97),
        "channels": channels,
    }


def hidden_profiles(group: int = 0) -> list[dict]:
    """Held-out profiles; each profile group is a disjoint set of (model, dataset) pairs."""
    return [_profile(random.Random(derived_seed("profile", group, index)), regime) for index, regime in enumerate(_REGIMES[group])]


def _clip(value: float) -> float:
    return max(0.001, min(0.999, value))


def _choose(rng: random.Random, weights: dict) -> str:
    total = sum(weights.values())
    pick = rng.random() * total
    for key, weight in weights.items():
        pick -= weight
        if pick <= 0:
            return key
    return key


def _rise(x: float, knots: list) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    pos = x * (len(knots) - 1)
    i = int(pos)
    return knots[i] + (knots[i + 1] - knots[i]) * (pos - i)


def _heavy_noise(rng: random.Random, df: float) -> float:
    z = rng.gauss(0.0, 1.0)
    chi = rng.gammavariate(df / 2.0, 2.0)
    return z / math.sqrt(chi / df) * math.sqrt((df - 2.0) / df)


def _make_instance(rng: random.Random, p: dict, solvable_probability: float) -> dict:
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
    flip_step = total_steps + 1
    if solvable:
        kind = _choose(rng, p["solvable_mix"])
        latest = max(4, int(total_steps * p["solve_latest_frac"]))
        solve_step = min(latest, 3 + int(rng.betavariate(*p["solve_shape"]) * (latest - 2)))
        clarity = rng.uniform(*p["muted_clarity"]) if kind == "muted" else rng.uniform(0.9, 1.05)
        progress = rng.uniform(*p["progress"])
        if kind == "silent":
            # Shows no progress at all, then solves late.
            progress = 0.0
            solve_step = rng.randint(max(3, (latest + 3) // 2), latest)
        if kind == "late_flip":
            flip_step = solve_step + rng.randint(2, 5)
            drop = rng.uniform(*p["flip_drop"])
    else:
        kind = _choose(rng, p["unsolvable_mix"])
        solve_step = total_steps + 1
        drift = rng.uniform(*p["drift"])
        onset = max(2, int(round(rng.uniform(*p["fc_onset"]) * total_steps)))
        boost = rng.uniform(*p["fc_boost"])
    stickiness = p["fc_stickiness"] if kind == "false_confident" else p["wrong_stickiness"]
    # Confident intermediate mistake: for one or two chunks before the run is
    # correct, the model commits to a wrong answer and looks confident.
    spike_steps: set[int] = set()
    spike_height = 0.0
    last_wrong_step = min(total_steps, solve_step - 1)
    if last_wrong_step >= 1 and rng.random() < p["spike_rate"]:
        first = rng.randint(1, last_wrong_step)
        spike_steps = set(range(first, min(last_wrong_step, first + rng.randint(0, 1)) + 1))
        spike_height = rng.uniform(*p["spike_height"])

    channel_state = {}
    for name in CHANNELS:
        ch = p["channels"][name]
        channel_state[name] = {
            "offset": rng.gauss(0.0, ch["offset_sd"]),
            "fooled": rng.random() < ch["fooled"],
            "lag": ch["lag"] + (ch["late_lag"] if kind == "late_signal" else 0),
            "noise": 0.0,
            "spike": bool(spike_steps) and rng.random() < ch["spike_seen"],
        }

    wander = 0.0
    tokens = 0
    steps = []
    previous_wrong: str | None = None
    for t in range(1, total_steps + 1):
        frac = t / total_steps
        tokens += max(1, int(round(stride * math.exp(rng.gauss(0.0, p["chunk_cv"]) - p["chunk_cv"] ** 2 / 2))))
        if solvable and t >= flip_step:
            correct = rng.random() < p["unsolv_lucky_rate"]
        elif solvable:
            correct = rng.random() >= p["flicker_rate"] if t >= solve_step else rng.random() < p["early_lucky_rate"]
        else:
            correct = rng.random() < p["unsolv_lucky_rate"]
            if kind == "wander":
                wander = max(-1.0, min(1.0, wander + rng.gauss(0.0, 0.4)))

        if t in spike_steps:
            correct = False
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
                start = solve_step + state["lag"]
                latent = p["ease_lift"] + clarity * (
                    progress * min(1.0, t / start) + (1.0 - progress) * _rise((t - start + 1) / width, knots)
                )
                if t >= flip_step + state["lag"]:
                    latent *= drop
            else:
                latent = drift * frac
                if kind == "wander":
                    latent += p["wander_amp"] * (0.5 + 0.5 * wander)
                elif kind == "false_confident":
                    share = 1.0 if state["fooled"] else ch["attenuation"]
                    latent += share * boost * _rise((t - onset - state["lag"] + 1) / width, knots)
            if t in spike_steps and state["spike"]:
                latent = max(latent, spike_height)
            rho = ch["rho"]
            scale = ch["noise"] * (1.0 + ch["noise_growth"] * frac)
            state["noise"] = rho * state["noise"] + math.sqrt(1.0 - rho * rho) * scale * _heavy_noise(rng, ch["df"])
            raw = ch["floor"] + ch["gain"] * latent + state["offset"] + state["noise"]
            signals[name] = round(_clip(raw) ** ch["gamma"], 6)
        steps.append({"step": t, "tokens": tokens, "prediction": prediction, "signals": signals})

    budget = steps[-1]["tokens"]
    for step in steps:
        step["signals"]["token_fraction"] = round(step["tokens"] / budget, 6)
    return {"gold": gold, "budget_tokens": budget, "steps": steps}


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
