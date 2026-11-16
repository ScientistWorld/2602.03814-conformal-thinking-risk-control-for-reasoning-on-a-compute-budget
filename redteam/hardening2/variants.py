#!/usr/bin/env python3
"""Candidate stopping policies for the second hardening audit (REVIEW.md items).

Every candidate speaks the benchmark's online protocol (``serve``) and is
registered exactly like a future method: ``outputs/<name>/policy.json``.

* Honest variants change the calibration or the signal set (same losses,
  same online decisions as the reference).
* Shortcut probes try what REVIEW.md / HARDENING.md left open: fitting the
  public simulator to the calibration set and calibrating on simulated samples
  ("simfit"), calibrating on public-simulator data, reading the hidden test
  generator at test time, uncalibrated hand-written rules, and the older
  probes whose outcome could change with a new trajectory process.

Usage:
  python redteam/hardening2/variants.py serve <variant> [--family new|old]
  python redteam/hardening2/variants.py build-bank --family new|old
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib.util
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "method"))
import conformal_thinking as ct  # noqa: E402

CHANNELS = ("confidence", "eat_confidence")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── fast Alg. 1 (same semantics as method/conformal_thinking.py) ────────────


def kl_bernoulli(p: float, q: float) -> float:
    p = min(max(p, 0.0), 1.0)
    q = min(max(q, 1e-12), 1 - 1e-12)
    out = 0.0
    if p > 0:
        out += p * math.log(p / q)
    if p < 1:
        out += (1 - p) * math.log((1 - p) / (1 - q))
    return out


def kl_feasible(risk: float, n: int, epsilon: float, delta: float) -> bool:
    """Hoeffding relative-entropy tail bound: accept when exp(-n KL(risk||eps)) <= delta."""
    if risk >= epsilon:
        return False
    return math.exp(-n * kl_bernoulli(risk, epsilon)) <= delta


def feasible(risk: float, n: int, epsilon: float, delta: float, bound: str) -> bool:
    if bound == "naive":
        return risk <= epsilon
    if bound == "kl":
        return kl_feasible(risk, n, epsilon, delta)
    return ct.ucb(risk, n, delta) <= epsilon


class Prepared:
    __slots__ = ("budget", "tokens", "correct", "first", "T", "values", "runmax")

    def __init__(self, inst: dict, signals) -> None:
        steps = inst["steps"]
        self.budget = ct.budget_of(inst)
        self.tokens = [s["tokens"] for s in steps]
        self.correct = [s["prediction"] == inst["gold"] for s in steps]
        self.first = next((i for i, c in enumerate(self.correct) if c), None)
        self.T = len(steps)
        self.values = {name: [ct.signal(s, name, self.budget) for s in steps] for name in signals}
        self.runmax = {}
        for name, vals in self.values.items():
            out, best = [], -1e9
            for v in vals:
                best = v if v > best else best
                out.append(best)
            self.runmax[name] = out


def fast_select(rows, n, epsilon, delta, bound):
    best = None
    for name, thr, risk, eff in rows:
        if not feasible(risk, n, epsilon, delta, bound):
            continue
        adjusted = ct.ucb(risk, n, delta) if bound == "ucb" else risk
        key = (eff, adjusted)
        if best is None or key < best[0]:
            best = (key, ct.Candidate(name, thr, risk, adjusted, eff))
    return None if best is None else best[1]


def fast_calibrate(instances, epsilon, delta, signals=ct.SIGNALS, variant="dual", bound="ucb", n_eff=None, lower_mode="selected"):
    """Return (upper, lower) candidates exactly as the reference's Alg. 1 would select them."""
    prepared = [Prepared(inst, set(signals) | set(ct.CONFIDENCE_SIGNALS)) for inst in instances]
    n = n_eff or len(prepared)
    m = len(prepared)
    rows = []
    for name in signals:
        for thr in ct.UPPER_GRID:
            fp = eff = 0.0
            for p in prepared:
                idx = bisect.bisect_left(p.runmax[name], thr)
                if idx < p.T:
                    if not p.correct[idx]:
                        fp += 1.0
                else:
                    idx = p.T - 1
                if p.first is not None:
                    eff += max(0, idx - p.first) / p.T
            rows.append((name, thr, fp / m, eff / m))
    upper = fast_select(rows, n, epsilon, delta, bound)
    if variant == "upper_only":
        return upper, None
    scale = upper.threshold if upper is not None else 1.0
    lower_signal = ct.lower_signal_for(upper) if lower_mode == "selected" else "confidence"
    rows = []
    for c in ct.C_GRID:
        fn = eff = 0.0
        for p in prepared:
            vals = p.values[lower_signal]
            half = p.budget / 2.0
            idx = p.T - 1
            lowered = False
            for i in range(p.T):
                if vals[i] < scale * ct.sigmoid(c * (p.tokens[i] - half)):
                    idx, lowered = i, True
                    break
            if lowered:
                future = p.correct[idx:]
                fn += sum(future) / len(future)
            eff += sum(1 for ok in p.correct[: idx + 1] if not ok) / p.T
        rows.append((lower_signal, c, fn / m, eff / m))
    lower = fast_select(rows, n, epsilon, delta, bound)
    return upper, lower


class FastPolicy(ct.ConformalThinkingPolicy):
    """Reference decisions with candidates chosen by ``fast_calibrate``."""

    def __init__(self, signals=None, variant="dual", bound="ucb", lower_mode="selected", epsilon_scale=1.0):
        super().__init__(variant, "ucb")
        self.signals = list(signals or ct.SIGNALS)
        self.bound = bound
        self.lower_mode = lower_mode
        self.epsilon_scale = epsilon_scale

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        self.upper, self.lower = fast_calibrate(
            instances, epsilon * self.epsilon_scale, delta, self.signals, self.variant, self.bound, lower_mode=self.lower_mode
        )

    def decide(self, step):
        if self.upper is not None and ct.signal(step, self.upper.name, self.budget) >= self.upper.threshold:
            return "answer"
        if self.lower is not None:
            scale = self.upper.threshold if self.upper is not None else 1.0
            curve = ct.lower_curve(step["tokens"], self.budget, self.lower.threshold, scale)
            if ct.signal(step, self.lower.name, self.budget) < curve:
                return "defer"
        return "continue"


# ── honest variants ─────────────────────────────────────────────────────────


class JointCalibrationPolicy(FastPolicy):
    """Joint search over (signal, upper threshold, lower shape) for the combined policy (Sec. 4.4 remark).

    Both thresholds use the same signal (lower on confidence when the signal is
    the token count). Feasibility applies the finite-sample bound to the
    combined policy's FP and FN risks; among feasible configurations the one
    with the smallest validation token fraction plus error rate wins.
    """

    UPPER = [i / 100.0 for i in range(20, 100, 2)]
    LOWER = [i / 1000.0 for i in range(8, 81, 4)] + [None]

    def __init__(self, bound="ucb"):
        super().__init__(bound=bound)

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        prepared = [Prepared(inst, set(ct.SIGNALS)) for inst in instances]
        n = len(prepared)
        best = None
        for name in ct.SIGNALS:
            lower_name = name if name in ct.CONFIDENCE_SIGNALS else ct.DEFAULT_LOWER_SIGNAL
            for h in self.UPPER:
                ups = []
                for p in prepared:
                    idx = bisect.bisect_left(p.runmax[name], h)
                    ups.append((idx, True) if idx < p.T else (p.T - 1, False))
                for c in self.LOWER:
                    fp = fn = frac = wrong = 0.0
                    for p, (uidx, upper_hit) in zip(prepared, ups):
                        idx, kind = (uidx, "upper" if upper_hit else "budget")
                        if c is not None:
                            vals = p.values[lower_name]
                            half = p.budget / 2.0
                            for i in range(uidx if upper_hit else p.T):
                                if vals[i] < h * ct.sigmoid(c * (p.tokens[i] - half)):
                                    idx, kind = i, "lower"
                                    break
                        if kind == "upper" and not p.correct[idx]:
                            fp += 1.0
                        if kind == "lower":
                            future = p.correct[idx:]
                            fn += sum(future) / len(future)
                        frac += p.tokens[idx] / p.budget
                        wrong += float(kind == "lower" or not p.correct[idx])
                    if not (feasible(fp / n, n, epsilon, delta, self.bound) and feasible(fn / n, n, epsilon, delta, self.bound)):
                        continue
                    key = ((frac + wrong) / n, (fp + fn) / n)
                    if best is None or key < best[0]:
                        best = (key, name, lower_name, h, c)
        self.upper = self.lower = None
        if best is None:
            return
        _, name, lower_name, h, c = best
        self.upper = ct.Candidate(name, h, 0.0, 0.0, 0.0)
        if c is not None:
            self.lower = ct.Candidate(lower_name, c, 0.0, 0.0, 0.0)


# ── simulator-fit shortcut (REVIEW.md item 2) ───────────────────────────────


def instance_stats(instances: list[dict]) -> list[float]:
    """Summary statistics used to match a calibration set to simulated profiles."""
    solv = [i for i in instances if i["steps"][-1]["prediction"] == i["gold"]]
    uns = [i for i in instances if i["steps"][-1]["prediction"] != i["gold"]]

    def mean(xs, default=0.0):
        xs = list(xs)
        return sum(xs) / len(xs) if xs else default

    out = [mean(len(i["steps"]) for i in instances), mean(i["budget_tokens"] / len(i["steps"]) for i in instances)]
    firsts = []
    for i in solv:
        first = next(k for k, s in enumerate(i["steps"]) if s["prediction"] == i["gold"])
        firsts.append(first / len(i["steps"]))
    out += [mean(firsts), math.sqrt(mean((f - mean(firsts)) ** 2 for f in firsts))]
    for name in CHANNELS:
        for group in (solv, uns):
            bins = [[] for _ in range(5)]
            for i in group:
                T = len(i["steps"])
                for k, s in enumerate(i["steps"]):
                    bins[min(4, int(5 * k / T))].append(s["signals"][name])
            out += [mean(b) for b in bins]
        maxes = [max(s["signals"][name] for s in i["steps"]) for i in uns]
        out += [mean(m >= q for m in maxes) for q in (0.5, 0.65, 0.8)]
        out.append(mean(i["steps"][-1]["signals"][name] >= 0.7 for i in solv))
        out.append(mean(max(s["signals"][name] for s in i["steps"]) for i in solv))
        rel = []
        for i in solv:
            first = next(k for k, s in enumerate(i["steps"]) if s["prediction"] == i["gold"])
            rel.append(i["steps"][min(first + 2, len(i["steps"]) - 1)]["signals"][name])
        out.append(mean(rel))
        diffs = [abs(a["signals"][name] - b["signals"][name]) for i in instances for a, b in zip(i["steps"], i["steps"][1:])]
        out.append(mean(diffs))
        offs = [mean(s["signals"][name] for s in i["steps"][:3]) for i in instances]
        out.append(math.sqrt(mean((o - mean(offs)) ** 2 for o in offs)))
    after = [not s["prediction"] == i["gold"] for i in solv for k, s in enumerate(i["steps"]) if k > next(j for j, t in enumerate(i["steps"]) if t["prediction"] == i["gold"])]
    out.append(mean(after))
    repeats = [a["prediction"] == b["prediction"] for i in uns for a, b in zip(i["steps"], i["steps"][1:])]
    out.append(mean(repeats))
    return out


class Family:
    """The public simulator the attacker fits, with a prior over its parameters."""

    def __init__(self, which: str) -> None:
        self.which = which
        if which == "old":
            self.gen = load_module(HERE / "old_public_generator.py", "old_public_generator")
        else:
            self.gen = load_module(ROOT / "data" / "generate_synthetic_reasoning.py", "public_generator")

    def sample_profile(self, rng: random.Random) -> dict:
        if self.which == "old":
            # The old public generator documented the ranges held-out profiles came from.
            profile = {}
            for key, (low, high) in self.gen.PROFILE_RANGES.items():
                profile[key] = rng.randint(low, high) if key in {"steps_min", "steps_max", "stride_min", "stride_max"} else rng.uniform(low, high)
            return profile
        # New public generator: no published held-out ranges. Widen the span of
        # the three public profiles by 50% on each side, independently per leaf.
        publics = list(self.gen.PUBLIC_PROFILES.values())
        return self._widen(publics, rng)

    def _widen(self, values, rng):
        first = values[0]
        if isinstance(first, dict):
            return {key: self._widen([v[key] for v in values], rng) for key in first}
        if isinstance(first, list):
            if len(first) == 5:  # rise knots
                incs = sorted(rng.random() for _ in range(3))
                return [0.0, *incs, 1.0]
            out = [self._widen([v[i] for v in values], rng) for i in range(len(first))]
            if all(isinstance(x, (int, float)) for x in out) and len(out) == 2:
                out = sorted(out)
            return out
        if isinstance(first, bool) or not isinstance(first, (int, float)):
            return first
        low, high = min(values), max(values)
        spread = max(high - low, abs(high) * 0.2, 1e-3)
        low, high = low - 0.5 * spread, high + 0.5 * spread
        if isinstance(first, int):
            return rng.randint(int(math.floor(max(0, low))), int(math.ceil(high)))
        value = rng.uniform(low, high)
        return max(0.0, value)

    def fix(self, profile: dict) -> dict:
        if self.which == "new":
            for ch in profile["channels"].values():
                ch["fooled"] = min(1.0, ch["fooled"])
                ch["df"] = max(3.0, ch["df"])
                ch["rho"] = min(0.9, ch["rho"])
            profile["steps"] = [max(4, profile["steps"][0]), max(profile["steps"][0] + 1, profile["steps"][1])]
            profile["stride"] = [max(5, profile["stride"][0]), max(profile["stride"][0] + 1, profile["stride"][1])]
            profile["solve_shape"] = [max(0.3, x) for x in profile["solve_shape"]]
            profile["solve_latest_frac"] = min(0.95, max(0.2, profile["solve_latest_frac"]))
            profile["rise_width"] = max(1.0, profile["rise_width"])
        else:
            profile["steps_max"] = max(profile["steps_max"], profile["steps_min"] + 1)
            profile["stride_max"] = max(profile["stride_max"], profile["stride_min"] + 1)
        return profile

    def simulate(self, profile: dict, size: int, rng: random.Random, solvable_fraction: float | None) -> list[dict]:
        if solvable_fraction is None:
            return [self.gen.make_instance(rng, profile, 0.58) for _ in range(size)]
        want_s = int(round(size * solvable_fraction))
        want_u = size - want_s
        s_rows, u_rows = [], []
        tries = 0
        while (len(s_rows) < want_s or len(u_rows) < want_u) and tries < size * 40:
            tries += 1
            row = self.gen.make_instance(rng, profile, max(0.05, min(0.95, solvable_fraction)))
            if row["steps"][-1]["prediction"] == row["gold"]:
                if len(s_rows) < want_s:
                    s_rows.append(row)
            elif len(u_rows) < want_u:
                u_rows.append(row)
        rows = s_rows + u_rows
        rng.shuffle(rows)
        return rows


BANK_PROFILES = 500
BANK_INSTANCES = 80


def bank_path(which: str) -> Path:
    return ROOT / "tmp" / f"simfit_bank_{which}.json"


def build_bank(which: str) -> list[dict]:
    family = Family(which)
    rng = random.Random(20261116)
    bank = []
    for _ in range(BANK_PROFILES):
        profile = family.fix(family.sample_profile(rng))
        rows = family.simulate(profile, BANK_INSTANCES, rng, None)
        bank.append({"profile": profile, "stats": instance_stats(rows)})
    path = bank_path(which)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bank), encoding="utf-8")
    return bank


def hybrid_calibrate(synthetic, real, epsilon, delta, lower_mode):
    """Feasible only if the synthetic risk passes Hoeffding at the synthetic size AND the
    supplied set's raw empirical risk is within epsilon; most efficient on the synthetic set."""

    def table(rows_of, data, scale=None, lower_signal=None):
        return rows_of(data, scale, lower_signal)

    def upper_rows(data, _scale, _sig):
        prepared = [Prepared(inst, set(ct.SIGNALS)) for inst in data]
        rows = []
        for name in ct.SIGNALS:
            for thr in ct.UPPER_GRID:
                fp = eff = 0.0
                for p in prepared:
                    idx = bisect.bisect_left(p.runmax[name], thr)
                    if idx < p.T:
                        fp += 0.0 if p.correct[idx] else 1.0
                    else:
                        idx = p.T - 1
                    if p.first is not None:
                        eff += max(0, idx - p.first) / p.T
                rows.append((name, thr, fp / len(prepared), eff / len(prepared)))
        return rows

    def lower_rows(data, scale, sig):
        prepared = [Prepared(inst, set(ct.SIGNALS)) for inst in data]
        rows = []
        for c in ct.C_GRID:
            fn = eff = 0.0
            for p in prepared:
                vals = p.values[sig]
                idx, lowered = p.T - 1, False
                for i in range(p.T):
                    if vals[i] < scale * ct.sigmoid(c * (p.tokens[i] - p.budget / 2.0)):
                        idx, lowered = i, True
                        break
                if lowered:
                    fut = p.correct[idx:]
                    fn += sum(fut) / len(fut)
                eff += sum(1 for ok in p.correct[: idx + 1] if not ok) / p.T
            rows.append((sig, c, fn / len(prepared), eff / len(prepared)))
        return rows

    def pick(syn_rows, real_rows):
        best = None
        for (name, thr, risk, eff), (_, _, real_risk, _) in zip(syn_rows, real_rows):
            if ct.ucb(risk, len(synthetic), delta) <= epsilon and real_risk <= epsilon:
                key = (eff, risk)
                if best is None or key < best[0]:
                    best = (key, ct.Candidate(name, thr, risk, risk, eff))
        return None if best is None else best[1]

    upper = pick(upper_rows(synthetic, None, None), upper_rows(real, None, None))
    scale = upper.threshold if upper is not None else 1.0
    sig = ct.lower_signal_for(upper) if lower_mode == "selected" else "confidence"
    lower = pick(lower_rows(synthetic, scale, sig), lower_rows(real, scale, sig))
    return upper, lower


class SimFitPolicy(FastPolicy):
    """Fit the public simulator to the calibration set, then calibrate on simulated samples.

    1. Match the calibration set's summary statistics against a bank of
       simulated profiles drawn from the public simulator's prior (ABC).
    2. Simulate ``SYNTHETIC`` labelled trajectories from the nearest profiles at
       the calibration set's solvable fraction.
    3. Run the reference's Alg. 1 on the synthetic set (``bound`` = Hoeffding
       at the synthetic size, or naive).
    """

    NEAREST = 6
    SYNTHETIC = 1500

    def __init__(self, which: str, bound: str, epsilon_scale: float = 1.0) -> None:
        super().__init__(bound=bound, lower_mode="selected" if which == "new" else "confidence", epsilon_scale=epsilon_scale)
        self.family = Family(which)
        path = bank_path(which)
        self.bank = json.loads(path.read_text()) if path.exists() else build_bank(which)

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        epsilon *= self.epsilon_scale
        target = instance_stats(instances)
        cols = list(zip(*[b["stats"] for b in self.bank]))
        sds = []
        for col in cols:
            mu = sum(col) / len(col)
            sds.append(math.sqrt(sum((x - mu) ** 2 for x in col) / len(col)) or 1.0)
        dist = []
        for k, b in enumerate(self.bank):
            dist.append((sum(((x - y) / sd) ** 2 for x, y, sd in zip(b["stats"], target, sds)), k))
        dist.sort()
        seed = int(hashlib.sha256(json.dumps([instances[0]["gold"], len(instances)]).encode()).hexdigest()[:12], 16)
        rng = random.Random(seed)
        solvable = sum(i["steps"][-1]["prediction"] == i["gold"] for i in instances) / len(instances)
        synthetic = []
        per = self.SYNTHETIC // self.NEAREST
        for _, k in dist[: self.NEAREST]:
            synthetic += self.family.simulate(self.bank[k]["profile"], per, rng, solvable)
        if self.bound == "hybrid":
            self.upper, self.lower = hybrid_calibrate(synthetic, instances, epsilon, delta, self.lower_mode)
        else:
            self.upper, self.lower = fast_calibrate(
                synthetic, epsilon, delta, self.signals, self.variant, self.bound, lower_mode=self.lower_mode
            )
        print(f"simfit: nearest d={dist[0][0]:.1f}, n_syn={len(synthetic)}, upper={self.upper}, lower={self.lower}", file=sys.stderr)


class PublicSimulatorPolicy(FastPolicy):
    """Ignore the supplied calibration set; calibrate on 3000 public-profile trajectories at its mix."""

    def __init__(self) -> None:
        super().__init__()
        self.family = Family("new")

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        solvable = sum(i["steps"][-1]["prediction"] == i["gold"] for i in instances) / len(instances)
        rng = random.Random(9100)
        rows = []
        for profile in self.family.gen.PUBLIC_PROFILES.values():
            rows += self.family.simulate(profile, 1000, rng, solvable)
        super().calibrate(rows, epsilon, delta)


# ── reading the hidden generator at test time ───────────────────────────────


class ReadHiddenPolicy(FastPolicy):
    """Try to load eval/test/hidden_tasks.py while running and use it as an oracle.

    If the file is readable, regenerate the held-out pools and test sets, find
    the ones this operating point uses and answer each held-out instance at its
    first correct chunk (deferring hopeless ones at once). If it is not
    readable, fall back to the reference.
    """

    KEYS = [("natural", 0), ("natural", 1), ("ratio_3_1", 0), ("ratio_1_1", 0), ("ratio_1_3", 0)]

    def __init__(self) -> None:
        super().__init__()
        self.lookup: dict | None = None
        self.plan = None
        self.t = 0

    @staticmethod
    def _sig(step: dict) -> str:
        return json.dumps([step["tokens"], step["prediction"], step["signals"]], sort_keys=True)

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        super().calibrate(instances, epsilon, delta, calibration_id)
        path = Path("eval/test/hidden_tasks.py")
        try:
            path.read_text()
            hidden = load_module(path, "hidden_tasks_probe")
        except (OSError, ImportError, SyntaxError) as exc:
            print(f"read_hidden: hidden generator unreadable ({exc.__class__.__name__}); using reference", file=sys.stderr)
            return
        target = {(i["gold"], self._sig(i["steps"][0])) for i in instances[:5]}
        for setting, group in self.KEYS:
            for index, profile in enumerate(hidden.hidden_profiles(group)):
                pool = hidden.generate(profile, setting, 1000, hidden.derived_seed("pool", setting, group, index))
                if any((p["gold"], self._sig(p["steps"][0])) in target for p in pool):
                    test = hidden.generate(profile, setting, 1000, hidden.derived_seed("test", setting, group, index))
                    self.lookup = {self._sig(t["steps"][0]): t for t in test}
                    print(f"read_hidden: matched {setting}/{group}/{index}", file=sys.stderr)
                    return
        print("read_hidden: no match", file=sys.stderr)

    def begin(self, budget_tokens):
        super().begin(budget_tokens)
        self.plan = None
        self.t = 0

    def decide(self, step):
        if self.lookup is None:
            return super().decide(step)
        if self.t == 0:
            inst = self.lookup.get(self._sig(step))
            if inst is not None:
                first = next((k for k, s in enumerate(inst["steps"]) if s["prediction"] == inst["gold"]), None)
                last_ok = inst["steps"][-1]["prediction"] == inst["gold"]
                self.plan = ("answer", first) if first is not None and last_ok else ("defer", 0)
        self.t += 1
        if self.plan is None:
            return super().decide(step)
        kind, index = self.plan
        return kind if self.t - 1 >= index else "continue"


# ── stateless probes ────────────────────────────────────────────────────────


class Fixed:
    def __init__(self, action_fn):
        self.action_fn = action_fn
        self.state: dict = {}

    def calibrate(self, *args, **kwargs):
        pass

    def begin(self, budget_tokens):
        self.state = {"budget": budget_tokens}

    def decide(self, step):
        return self.action_fn(self.state, step)


def stop_on_repeat(state, step):
    previous = state.get("previous")
    state["previous"] = step["prediction"]
    return "answer" if previous == step["prediction"] else "continue"


def fixed_rule(state, step):
    # Hand-written, uncalibrated thresholds on the raw signals.
    best = max(step["signals"]["confidence"], step["signals"]["eat_confidence"])
    if best >= 0.85:
        return "answer"
    if step["tokens"] / state["budget"] >= 0.5 and best < 0.35:
        return "defer"
    return "continue"


VARIANTS = {
    # honest
    "better_tighter_bound": lambda a: FastPolicy(bound="kl"),
    "better_joint_calibration": lambda a: JointCalibrationPolicy("ucb"),
    "better_joint_tighter_bound": lambda a: JointCalibrationPolicy("kl"),
    "variant_stricter_calibration": lambda a: FastPolicy(epsilon_scale=0.5),
    "weaker_confidence_only": lambda a: FastPolicy(signals=["confidence"]),
    "weaker_eat_only": lambda a: FastPolicy(signals=["eat_confidence"]),
    "weaker_token_budget": lambda a: FastPolicy(signals=["token_fraction"], variant="upper_only"),
    "fast_reference": lambda a: FastPolicy(),
    # shortcuts
    "shortcut_simfit_ucb": lambda a: SimFitPolicy(a.family, "ucb"),
    "shortcut_simfit_naive": lambda a: SimFitPolicy(a.family, "naive"),
    "shortcut_simfit_hybrid": lambda a: SimFitPolicy(a.family, "hybrid"),
    # best response to misspecification: the hybrid at 70% of the requested tolerance
    "shortcut_simfit_cautious": lambda a: SimFitPolicy(a.family, "hybrid", epsilon_scale=0.7),
    "shortcut_public_simulator_calibration": lambda a: PublicSimulatorPolicy(),
    "shortcut_read_hidden": lambda a: ReadHiddenPolicy(),
    "shortcut_stop_on_repeat": lambda a: Fixed(stop_on_repeat),
    "shortcut_fixed_rule": lambda a: Fixed(fixed_rule),
    "shortcut_early_answer": lambda a: Fixed(lambda s, step: "answer"),
    "shortcut_all_defer": lambda a: Fixed(lambda s, step: "defer"),
}


class IgnoreEpsilon(FastPolicy):
    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        self.upper, self.lower = fast_calibrate(instances, 0.4, delta, self.signals, self.variant, self.bound)


VARIANTS["shortcut_ignore_epsilon"] = lambda a: IgnoreEpsilon()


def serve(policy) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        kind = message.get("type")
        if kind == "step":
            reply = {"action": policy.decide(message["step"])}
        elif kind == "begin":
            policy.begin(message["budget_tokens"])
            reply = {"ok": True}
        elif kind == "calibrate":
            policy.calibrate(message["instances"], float(message["epsilon"]), float(message["delta"]), message.get("calibration_id"))
            reply = {"ok": True}
        elif kind == "shutdown":
            return
        else:
            reply = {"error": f"unknown message type {kind!r}"}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["serve", "build-bank"])
    parser.add_argument("variant", nargs="?")
    parser.add_argument("--family", choices=["new", "old"], default="new")
    args = parser.parse_args()
    if args.command == "build-bank":
        bank = build_bank(args.family)
        print(f"bank {args.family}: {len(bank)} profiles -> {bank_path(args.family)}")
        return
    serve(VARIANTS[args.variant](args))


if __name__ == "__main__":
    main()
