#!/usr/bin/env python3
"""Candidate stopping policies used to audit the hardened gym.

Every candidate speaks the benchmark's online protocol (``serve``) and is
registered exactly like a future method: ``outputs/<name>/policy.json``.
Honest variants change the calibration or the stopping signal; shortcut
variants try the exploits reported in REDTEAM.md against the new interface.
None of them reads held-out data.

Usage: python redteam/hardening/variants.py serve <variant>
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "method"))
import conformal_thinking as ct  # noqa: E402


# ── honest improvements ──────────────────────────────────────────────────────


def kl_bernoulli(p: float, q: float) -> float:
    p = min(max(p, 0.0), 1.0)
    q = min(max(q, 1e-12), 1 - 1e-12)
    out = 0.0
    if p > 0:
        out += p * math.log(p / q)
    if p < 1:
        out += (1 - p) * math.log((1 - p) / (1 - q))
    return out


def hoeffding_kl_feasible(risk: float, n: int, epsilon: float, delta: float) -> bool:
    """Hoeffding's relative-entropy tail bound for [0, 1] losses (tighter than Eq. 25).

    P(mean <= risk | true risk >= epsilon) <= exp(-n KL(risk || epsilon)) for risk < epsilon.
    The candidate is accepted when that p-value is at most delta.
    """
    if risk >= epsilon:
        return False
    return math.exp(-n * kl_bernoulli(risk, epsilon)) <= delta


class TighterBoundPolicy(ct.ConformalThinkingPolicy):
    """Same Alg. 1 search, losses and two-step combination; KL tail bound instead of Eq. 25."""

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        original = ct.select

        def select(stats, n, eps, dlt, calibration):
            feasible = [
                ct.Candidate(name, thr, risk, risk, eff)
                for name, thr, risk, eff in stats
                if hoeffding_kl_feasible(risk, n, eps, dlt)
            ]
            if not feasible:
                return None
            return min(feasible, key=lambda cand: (cand.efficiency_loss, cand.adjusted_risk))

        ct.select = select
        try:
            super().calibrate(instances, epsilon, delta, calibration_id)
        finally:
            ct.select = original


class JointCalibrationPolicy(ct.ConformalThinkingPolicy):
    """Joint search over (signal, upper threshold, lower shape) for the combined policy.

    The paper (Sec. 4.4) notes that searching the product space gives stronger
    guarantees at higher calibration cost. Feasibility uses the same Hoeffding
    correction (Eq. 25) on the *combined* policy's FP and FN risks; among
    feasible pairs the one with the smallest validation token fraction plus
    error rate wins.
    """

    UPPER = [i / 100.0 for i in range(20, 100, 2)]
    LOWER = [i / 1000.0 for i in range(8, 81, 4)] + [None]

    def _joint_table(self, instances, calibration_id):
        if calibration_id is not None and getattr(self, "_joint_id", None) == calibration_id:
            return self._joint_rows
        rows = []
        n = len(instances)
        for signal_name in ct.SIGNALS:
            for h in self.UPPER:
                ups = [ct.upper_exit(inst, signal_name, h) for inst in instances]
                for c in self.LOWER:
                    fp = fn = frac = wrong = 0.0
                    for inst, up in zip(instances, ups):
                        if c is None:
                            idx, reason = up
                        else:
                            low = ct.lower_exit(inst, ct.LOWER_SIGNAL, c, h)
                            take_low = low[0] < up[0] or (low[0] == up[0] and up[1] != "upper" and low[1] == "lower")
                            idx, reason = low if take_low else up
                        fp += ct.fp_loss(inst, idx, reason)
                        fn += ct.fn_loss(inst, idx, reason)
                        frac += inst["steps"][idx]["tokens"] / ct.budget_of(inst)
                        wrong += float(reason == "lower" or inst["steps"][idx]["prediction"] != inst["gold"])
                    rows.append((signal_name, h, c, fp / n, fn / n, frac / n + wrong / n))
        self._joint_id, self._joint_rows = calibration_id, rows
        return rows

    def feasible(self, fp, fn, n, epsilon, delta):
        margin = math.sqrt(math.log(1.0 / delta) / (2.0 * n))
        return fp + margin <= epsilon and fn + margin <= epsilon

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        n = len(instances)
        best = None
        for signal_name, h, c, fp, fn, objective in self._joint_table(instances, calibration_id):
            if not self.feasible(fp, fn, n, epsilon, delta):
                continue
            key = (objective, fp + fn)
            if best is None or key < best[0]:
                best = (key, signal_name, h, c)
        self.upper = self.lower = None
        if best is None:
            return
        _, signal_name, h, c = best
        self.upper = ct.Candidate(signal_name, h, 0.0, 0.0, 0.0)
        if c is not None:
            self.lower = ct.Candidate(ct.LOWER_SIGNAL, c, 0.0, 0.0, 0.0)


class CombinedImprovementPolicy(JointCalibrationPolicy):
    """Joint search with the KL tail bound instead of the additive Hoeffding margin."""

    def feasible(self, fp, fn, n, epsilon, delta):
        return hoeffding_kl_feasible(fp, n, epsilon, delta) and hoeffding_kl_feasible(fn, n, epsilon, delta)


# ── operating-point shift (not a better method under the paper's objective) ──


class StricterCalibrationPolicy(ct.ConformalThinkingPolicy):
    """REDTEAM better_strict_risk: calibrate at half the requested tolerance.

    Trades tokens for accuracy by leaving half of the allowed risk unused; the
    paper's objective is the least compute that still satisfies the tolerance.
    """

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        super().calibrate(instances, epsilon / 2.0, delta, ("strict", calibration_id))


# ── weaker variants ──────────────────────────────────────────────────────────


class ConfidenceOnlyPolicy(ct.ConformalThinkingPolicy):
    """Reference without the signal ensemble: the upper threshold uses confidence only."""

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        original = ct.SIGNALS
        ct.SIGNALS = ["confidence"]
        try:
            super().calibrate(instances, epsilon, delta, calibration_id=("conf-only", calibration_id))
        finally:
            ct.SIGNALS = original


class TokenBudgetPolicy(ct.ConformalThinkingPolicy):
    """Uniform token budget: risk-controlled upper threshold on the token fraction only."""

    def __init__(self):
        super().__init__("upper_only", "ucb")

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        original = ct.SIGNALS
        ct.SIGNALS = ["token_fraction"]
        try:
            super().calibrate(instances, epsilon, delta, calibration_id=("token-only", calibration_id))
        finally:
            ct.SIGNALS = original


# ── shortcut probes (REDTEAM.md exploits re-expressed for the online interface) ──


class Fixed:
    """Stateless probes."""

    def __init__(self, action_fn):
        self.action_fn = action_fn
        self.t = 0
        self.begin_message: dict = {}

    def calibrate(self, *args, **kwargs):
        pass

    def begin(self, budget_tokens):
        self.t = 0

    def decide(self, step):
        self.t += 1
        return self.action_fn(self, step)


def encoded_answers(self, step):
    # REDTEAM shortcut_encoded_answers: stop when the answer string reveals correctness.
    return "answer" if str(step["prediction"]).startswith("ans_") else "continue"


def stop_on_repeat(self, step):
    # Answer-stability oracle that worked when wrong answers never repeated.
    previous = getattr(self, "previous", None)
    self.previous = step["prediction"]
    return "answer" if previous == step["prediction"] else "continue"


def claim_budget(self, step):
    # REDTEAM shortcut_relabel_budget / early_budget: self-label an early exit as a budget exit.
    return "budget"


def early_answer(self, step):
    # Answer at the first chunk (relabelled-early-budget exploit under evaluator-derived exits).
    return "answer"


def all_defer(self, step):
    return "defer"


class GoldLookupPolicy(ct.ConformalThinkingPolicy):
    """REDTEAM gold/solvability lookup: search visible files for this instance's gold answer.

    With trajectories hidden, nothing visible matches; it falls back to the reference.
    """

    def __init__(self):
        super().__init__("dual", "ucb")
        self.known: dict[str, str] = {}
        for path in (ROOT / "data").rglob("*.jsonl"):
            for line in path.read_text().splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.known[str(row.get("id"))] = row.get("gold")
        self.gold = None

    def begin_with(self, message):
        self.gold = self.known.get(str(message.get("id")))
        self.solvable = message.get("solvable_under_budget")

    def decide(self, step):
        if self.gold is not None:
            return "answer" if step["prediction"] == self.gold else "continue"
        if getattr(self, "solvable", None) is False:
            return "defer"
        return super().decide(step)


class IgnoreEpsilonPolicy(ct.ConformalThinkingPolicy):
    """REDTEAM shortcut_operating_point: calibrate at a looser tolerance than requested."""

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        super().calibrate(instances, 0.4, delta, ("loose", calibration_id))


class PublicSimulatorPolicy(ct.ConformalThinkingPolicy):
    """Ignore the supplied calibration set; calibrate on 3000 examples from the public simulator.

    Tests whether knowledge of the public generator (and unlimited extra labelled
    data from it) substitutes for the evaluator's calibration data. The mix is
    matched to the supplied calibration set's solvable fraction.
    """

    def __init__(self):
        super().__init__("dual", "ucb")
        sys.path.insert(0, str(ROOT / "data"))
        import generate_synthetic_reasoning as public_data

        self.public = public_data
        self.cache: dict = {}

    def calibrate(self, instances, epsilon, delta, calibration_id=None):
        solvable = sum(inst["steps"][-1]["prediction"] == inst["gold"] for inst in instances) / len(instances)
        targets = {"ratio_3_1": 0.75, "natural": 0.55, "ratio_1_1": 0.5, "ratio_1_3": 0.25}
        setting = min(targets, key=lambda key: abs(targets[key] - solvable))
        if setting not in self.cache:
            rows = []
            for index, profile in enumerate(self.public.PUBLIC_PROFILES.values()):
                rows += self.public.generate_split(profile, setting, 1000, 9100 + index, "sim")
            self.cache[setting] = rows
        super().calibrate(self.cache[setting], epsilon, delta, ("public-sim", setting))


VARIANTS = {
    "better_tighter_bound": lambda: TighterBoundPolicy("dual", "ucb"),
    "better_joint_calibration": lambda: JointCalibrationPolicy("dual", "ucb"),
    "better_joint_tighter_bound": lambda: CombinedImprovementPolicy("dual", "ucb"),
    "variant_stricter_calibration": lambda: StricterCalibrationPolicy("dual", "ucb"),
    "weaker_confidence_only": lambda: ConfidenceOnlyPolicy("dual", "ucb"),
    "weaker_token_budget": lambda: TokenBudgetPolicy(),
    "shortcut_encoded_answers": lambda: Fixed(encoded_answers),
    "shortcut_stop_on_repeat": lambda: Fixed(stop_on_repeat),
    "shortcut_claim_budget": lambda: Fixed(claim_budget),
    "shortcut_early_answer": lambda: Fixed(early_answer),
    "shortcut_all_defer": lambda: Fixed(all_defer),
    "shortcut_gold_lookup": lambda: GoldLookupPolicy(),
    "shortcut_ignore_epsilon": lambda: IgnoreEpsilonPolicy("dual", "ucb"),
    "shortcut_public_simulator_calibration": lambda: PublicSimulatorPolicy(),
}


def serve(policy) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        kind = message.get("type")
        if kind == "step":
            reply = {"action": policy.decide(message["step"])}
        elif kind == "begin":
            policy.begin(message.get("budget_tokens", 1))
            if hasattr(policy, "begin_with"):
                policy.begin_with(message)
            reply = {"ok": True}
        elif kind == "calibrate":
            policy.calibrate(message["instances"], float(message["epsilon"]), float(message["delta"]), message.get("calibration_id"))
            reply = {"ok": True}
        elif kind == "shutdown":
            return
        else:
            reply = {"error": f"unknown message {kind!r}"}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "serve" or sys.argv[2] not in VARIANTS:
        raise SystemExit(f"usage: variants.py serve <{'|'.join(VARIANTS)}>")
    serve(VARIANTS[sys.argv[2]]())
