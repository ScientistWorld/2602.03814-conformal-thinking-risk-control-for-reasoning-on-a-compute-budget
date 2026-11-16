#!/usr/bin/env python3
"""Visible train evaluator for risk-controlled adaptive reasoning budgets.

Scores every stopping-policy program registered by a manifest
``outputs/<method>/policy.json`` (``{"command": [...]}``) on the public
development profiles of ``data/generate_synthetic_reasoning.py``. It uses the
same online protocol, experiments, operating points, metrics and feasibility
gate as the held-out test, which runs on different (held-out) profiles:

* calibration sets are labelled draws from a public calibration pool;
* held-out trajectories are revealed one chunk at a time; the exit type is
  derived from where the policy stopped and tokens are charged up to there;
* every scored number is recomputed here from per-instance outcomes;
* a policy whose realized risk exceeds the target at more than
  ``MAX_VIOLATION_RATE`` of operating points in any experiment, or that breaks
  the protocol, is scored as failed (failure values in every experiment).

Run with no arguments to score every method in ``outputs/``.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import hashlib

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "data"))
import generate_synthetic_reasoning as public_data  # noqa: E402

PUBLIC_SEED = "conformal-thinking-public-dev-v1"
PROFILE_NAMES = sorted(public_data.PUBLIC_PROFILES)

SLICE = "train"
DELTA = 0.1
MAX_VIOLATION_RATE = 0.15
POOL_SIZE = 1000
TEST_SIZE = 1000
# Compute limits for a policy process (one operating point). They count CPU
# time, not wall-clock time, so they do not depend on machine load: a process
# is stopped when it has used CPU_SECONDS_PER_PROCESS of CPU, or when a reply
# is pending and its process tree has made no CPU progress at all for
# IDLE_SECONDS (a deadlocked or sleeping policy). The reference policy uses a
# few CPU seconds per operating point.
CPU_SECONDS_PER_PROCESS = 3600
IDLE_SECONDS = 1800
ACTIONS = {"continue", "answer", "defer"}

# Fixed by the evaluator: calibration-set size, number of calibration draws per
# profile, and the target risk levels. The 1:3 mix uses tighter tolerances
# because there deferring everything immediately already has a false-negative
# risk of only about 0.18. ``group`` selects a disjoint set of profiles and
# pools, so calibration data seen in one experiment never helps another.
EXPERIMENTS = {
    "adaptive_budget_efficiency": {"group": 0, "setting": "natural", "calibration_size": 400, "draws": 4, "epsilons": [0.10, 0.15, 0.20]},
    "risk_control": {"group": 1, "setting": "natural", "calibration_size": 50, "draws": 10, "epsilons": [0.05, 0.10, 0.20, 0.25]},
    "difficulty_mix_3_1": {"group": 0, "setting": "ratio_3_1", "calibration_size": 400, "draws": 4, "epsilons": [0.10, 0.15, 0.20]},
    "difficulty_mix_1_1": {"group": 0, "setting": "ratio_1_1", "calibration_size": 400, "draws": 4, "epsilons": [0.10, 0.15, 0.20]},
    "difficulty_mix_1_3": {"group": 0, "setting": "ratio_1_3", "calibration_size": 400, "draws": 4, "epsilons": [0.05, 0.10, 0.125]},
}

METRICS = [
    "accuracy",
    "token_savings",
    "solvable_accuracy",
    "unsolvable_token_savings",
    "false_positive_risk",
    "false_negative_risk",
    "violation_rate",
    "constraint_satisfied",
    "defer_fraction",
    "defer_precision",
    "budget_exit_fraction",
]
FAILED_VALUES = {
    "accuracy": 0.0,
    "token_savings": 0.0,
    "solvable_accuracy": 0.0,
    "unsolvable_token_savings": 0.0,
    "false_positive_risk": 1.0,
    "false_negative_risk": 1.0,
    "violation_rate": 1.0,
    "constraint_satisfied": 0.0,
    "defer_fraction": 0.0,
    "defer_precision": 0.0,
    "budget_exit_fraction": 1.0,
}
FULL_BUDGET_KEY = "full_budget"


class PolicyError(RuntimeError):
    pass


# ── policy process ───────────────────────────────────────────────────────────


# The CPU limit is set inside the child by a small shim that then execs the
# policy command (preexec_fn is unsafe while other threads start processes).
_CPU_LIMIT_SHIM = (
    "import os, resource, sys; "
    "limit = int(sys.argv[1]); "
    "resource.setrlimit(resource.RLIMIT_CPU, (limit, limit + 30)); "
    "os.execvp(sys.argv[2], sys.argv[2:])"
)


def _tree_cpu_seconds(root_pid: int) -> float | None:
    """CPU seconds used by a process and its live descendants (Linux /proc); None if unavailable."""
    try:
        parents: dict[int, int] = {}
        times: dict[int, float] = {}
        tick = os.sysconf("SC_CLK_TCK")
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/stat", encoding="utf-8") as handle:
                    fields = handle.read().rsplit(")", 1)[1].split()
            except OSError:
                continue
            parents[int(entry)] = int(fields[1])
            times[int(entry)] = sum(int(x) for x in fields[11:15]) / tick
    except OSError:
        return None
    if root_pid not in times:
        return None
    total, stack = 0.0, [root_pid]
    children: dict[int, list[int]] = {}
    for pid, ppid in parents.items():
        children.setdefault(ppid, []).append(pid)
    while stack:
        pid = stack.pop()
        total += times.get(pid, 0.0)
        stack.extend(children.get(pid, []))
    return total


class PolicyProcess:
    def __init__(self, command: list[str], log_path: Path) -> None:
        resolved = [sys.executable if part in {"python", "python3"} and i == 0 else part for i, part in enumerate(command)]
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = log_path.open("a", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "-c", _CPU_LIMIT_SHIM, str(CPU_SECONDS_PER_PROCESS), *resolved],
            cwd=str(REPO_ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log,
            text=True,
            bufsize=1,
        )
        self._pending = False
        self._closed = threading.Event()
        self._watchdog = threading.Thread(target=self._watch_idle, daemon=True)
        self._watchdog.start()

    def _watch_idle(self) -> None:
        """Stop a policy that waits on nothing: a reply is pending and its CPU time does not move."""
        last_cpu, last_progress = None, time.monotonic()
        while not self._closed.wait(min(30.0, IDLE_SECONDS / 3.0)):
            cpu = _tree_cpu_seconds(self.proc.pid)
            if cpu is None:
                return
            now = time.monotonic()
            if not self._pending or last_cpu is None or cpu > last_cpu + 0.01:
                last_cpu, last_progress = cpu, now
            elif now - last_progress > IDLE_SECONDS:
                self.proc.kill()
                return

    def request(self, message: dict) -> dict:
        try:
            self.proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise PolicyError(f"policy stopped accepting input: {exc}") from exc
        self._pending = True
        line = self.proc.stdout.readline()
        self._pending = False
        if not line:
            raise PolicyError("policy exited (crash, CPU limit or idle) without replying")
        try:
            reply = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PolicyError(f"policy replied with non-JSON output: {line[:200]!r}") from exc
        if not isinstance(reply, dict):
            raise PolicyError(f"policy reply must be a JSON object, got {line[:200]!r}")
        if "error" in reply:
            raise PolicyError(f"policy reported an error: {str(reply['error'])[:200]}")
        return reply

    def close(self) -> None:
        self._closed.set()
        try:
            self.proc.stdin.write(json.dumps({"type": "shutdown"}) + "\n")
            self.proc.stdin.flush()
            self.proc.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self._log.close()


# ── per-instance outcomes and metrics ────────────────────────────────────────


def public_step(step: dict) -> dict:
    return {
        "step": step["step"],
        "tokens": step["tokens"],
        "prediction": step["prediction"],
        "signals": dict(step["signals"]),
    }


def calibration_view(instance: dict, index: int) -> dict:
    return {
        "id": f"cal{index:05d}",
        "gold": instance["gold"],
        "budget_tokens": instance["budget_tokens"],
        "steps": [public_step(step) for step in instance["steps"]],
    }


def run_instance(policy: PolicyProcess | None, instance: dict, query_id: str) -> tuple[str, int]:
    """Reveal chunks one at a time; return (exit kind, stopping chunk index)."""
    steps = instance["steps"]
    last = len(steps) - 1
    if policy is None:  # evaluator-owned full-budget control
        return "budget", last
    policy.request({"type": "begin", "id": query_id, "budget_tokens": instance["budget_tokens"]})
    for index, step in enumerate(steps):
        reply = policy.request({"type": "step", "step": public_step(step)})
        action = reply.get("action")
        if action not in ACTIONS:
            raise PolicyError(f"invalid action {action!r}; expected one of {sorted(ACTIONS)}")
        if action == "defer":
            return "defer", index
        if action == "answer":
            # An answer at the final chunk is not an early exit: the budget is spent.
            return ("answer", index) if index < last else ("budget", last)
    return "budget", last


def point_metrics(test: list[dict], outcomes: list[tuple[str, int]], epsilon: float) -> dict:
    n = len(test)
    correct = fp = fn = 0.0
    used = full = 0
    solvable_n = solvable_correct = 0
    unsolvable_used = unsolvable_full = 0
    defers = defers_unsolvable = budget_exits = 0
    for instance, (kind, index) in zip(test, outcomes):
        steps = instance["steps"]
        gold = instance["gold"]
        is_correct_step = [step["prediction"] == gold for step in steps]
        solvable = is_correct_step[-1]  # the full-budget answer is correct
        tokens = steps[index]["tokens"]
        used += tokens
        full += instance["budget_tokens"]
        answered_correct = kind != "defer" and is_correct_step[index]
        correct += answered_correct
        if kind == "answer" and not is_correct_step[index]:
            fp += 1.0
        if kind == "defer":
            future = is_correct_step[index:]
            fn += sum(future) / len(future)
            defers += 1
            defers_unsolvable += int(not solvable)
        if kind == "budget":
            budget_exits += 1
        if solvable:
            solvable_n += 1
            solvable_correct += answered_correct
        else:
            unsolvable_used += tokens
            unsolvable_full += instance["budget_tokens"]
    fp_risk = fp / n
    fn_risk = fn / n
    return {
        "accuracy": correct / n,
        "token_savings": 1.0 - used / full,
        "solvable_accuracy": solvable_correct / solvable_n if solvable_n else 0.0,
        "unsolvable_token_savings": 1.0 - unsolvable_used / unsolvable_full if unsolvable_full else 0.0,
        "false_positive_risk": fp_risk,
        "false_negative_risk": fn_risk,
        "violation": float(fp_risk > epsilon or fn_risk > epsilon),
        "defer_fraction": defers / n,
        "defer_precision": defers_unsolvable / defers if defers else 0.0,
        "budget_exit_fraction": budget_exits / n,
    }


def aggregate(points: list[dict]) -> dict:
    keys = [k for k in points[0] if k != "violation"]
    out = {key: sum(point[key] for point in points) / len(points) for key in keys}
    out["violation_rate"] = sum(point["violation"] for point in points) / len(points)
    out["constraint_satisfied"] = float(out["violation_rate"] <= MAX_VIOLATION_RATE)
    return {metric: out[metric] for metric in METRICS}


def derived_seed(*parts: object) -> int:
    text = ":".join([PUBLIC_SEED, *map(str, parts)])
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def build_tasks(keys: set[tuple[str, int]], pool_size: int, test_size: int) -> dict[tuple[str, int], list[dict]]:
    """Return {(setting, group): [{"pool": [...], "test": [...]} per public profile]}.

    The visible side has only the public profiles, so every group reuses them
    with its own pool and test seeds.
    """
    tasks: dict[tuple[str, int], list[dict]] = {}
    for setting, group in sorted(keys):
        entries = []
        for index, name in enumerate(PROFILE_NAMES):
            profile = public_data.PUBLIC_PROFILES[name]
            pool_seed = derived_seed("pool", setting, group, index)
            test_seed = derived_seed("test", setting, group, index)
            entries.append(
                {
                    "pool": public_data.generate_split(profile, setting, pool_size, pool_seed, "pool"),
                    "test": public_data.generate_split(profile, setting, test_size, test_seed, "test"),
                }
            )
        tasks[(setting, group)] = entries
    return tasks


def draw_indices(experiment: str, profile_index: int, draw: int, size: int) -> list[int]:
    rng = random.Random(derived_seed("draw", experiment, profile_index, draw))
    return rng.sample(range(POOL_SIZE), size)


def opaque_id(*parts: object) -> str:
    return format(derived_seed("id", *parts), "016x")


def run_experiment(
    experiment: str,
    config: dict,
    tasks: list[dict],
    command: list[str] | None,
    log_dir: Path,
    outcome_path: Path | None = None,
) -> tuple[dict, str | None]:
    """Score one method on one experiment.

    Every operating point (one calibration draw and one epsilon) runs in a fresh
    policy process, so nothing observed at one operating point (calibration sets
    or held-out chunks) is available at another. Identifiers are opaque.
    """
    log_path = log_dir / f"{experiment}.log"
    if command is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")
    points = []
    saved = []
    try:
        for profile_index, task in enumerate(tasks):
            for draw in range(config["draws"]):
                indices = draw_indices(experiment, profile_index, draw, config["calibration_size"])
                calibration = [calibration_view(task["pool"][i], j) for j, i in enumerate(indices)]
                calibration_id = opaque_id("calibration", experiment, profile_index, draw)
                for epsilon in config["epsilons"]:
                    policy = PolicyProcess(command, log_path) if command is not None else None
                    try:
                        if policy is not None:
                            policy.request(
                                {
                                    "type": "calibrate",
                                    "calibration_id": calibration_id,
                                    "epsilon": epsilon,
                                    "delta": DELTA,
                                    "instances": calibration,
                                }
                            )
                        outcomes = [
                            run_instance(policy, instance, opaque_id("query", experiment, profile_index, draw, epsilon, qi))
                            for qi, instance in enumerate(task["test"])
                        ]
                    finally:
                        if policy is not None:
                            policy.close()
                    points.append(point_metrics(task["test"], outcomes, epsilon))
                    if outcome_path is not None:
                        saved.append(
                            {
                                "profile": profile_index,
                                "draw": draw,
                                "epsilon": epsilon,
                                "outcomes": "".join(f"{kind[0]}{index}," for kind, index in outcomes),
                            }
                        )
                    if command is None:
                        break  # the full-budget control does not depend on calibration
                if command is None:
                    break
    except PolicyError as exc:
        return dict(FAILED_VALUES), f"protocol failure: {exc}"
    if outcome_path is not None:
        outcome_path.parent.mkdir(parents=True, exist_ok=True)
        outcome_path.write_text(json.dumps(saved), encoding="utf-8")
    metrics = aggregate(points)
    if not metrics["constraint_satisfied"]:
        failed = dict(FAILED_VALUES)
        return failed, (
            f"risk constraint failed: realized risk exceeded epsilon at {metrics['violation_rate']:.3f} of "
            f"operating points (allowed {MAX_VIOLATION_RATE}); measured FP={metrics['false_positive_risk']:.4f}, "
            f"FN={metrics['false_negative_risk']:.4f}, savings={metrics['token_savings']:.4f}, "
            f"accuracy={metrics['accuracy']:.4f}"
        )
    return metrics, None


# ── discovery and driver ─────────────────────────────────────────────────────


def discover_methods(outputs_root: Path) -> dict[str, list[str]]:
    methods: dict[str, list[str]] = {}
    for manifest in sorted(outputs_root.glob("*/policy.json")):
        name = manifest.parent.name
        if name.startswith("_") or name == FULL_BUDGET_KEY:
            continue
        try:
            spec = json.loads(manifest.read_text(encoding="utf-8"))
            command = spec["command"]
            if not (isinstance(command, list) and command and all(isinstance(part, str) for part in command)):
                raise ValueError("command must be a non-empty list of strings")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            methods[name] = []
            print(f"[{SLICE}] invalid manifest {manifest}: {exc}", file=sys.stderr)
            continue
        methods[name] = command
    return methods


def build_scores(args: argparse.Namespace) -> dict:
    outputs_root = Path(args.outputs)
    if not outputs_root.is_absolute():
        outputs_root = REPO_ROOT / outputs_root
    methods = discover_methods(outputs_root)
    settings = {(config["setting"], config["group"]) for config in EXPERIMENTS.values()}
    tasks = build_tasks(settings, POOL_SIZE, TEST_SIZE)
    log_root = REPO_ROOT / "logs" / f"eval_{SLICE}"

    jobs = [(name, experiment) for name in [FULL_BUDGET_KEY, *methods] for experiment in EXPERIMENTS]

    def work(job: tuple[str, str]) -> tuple[str, str, dict, str | None]:
        name, experiment = job
        config = EXPERIMENTS[experiment]
        if name == FULL_BUDGET_KEY:
            command = None
        else:
            command = methods[name]
            if not command:
                return name, experiment, dict(FAILED_VALUES), "invalid policy manifest"
        outcome_path = Path(args.save_outcomes) / name / f"{experiment}.json" if args.save_outcomes else None
        try:
            metrics, failure = run_experiment(
                experiment, config, tasks[(config["setting"], config["group"])], command, log_root / name, outcome_path
            )
        except OSError as exc:
            metrics, failure = dict(FAILED_VALUES), f"could not start policy: {exc}"
        print(f"[{SLICE}] {name} / {experiment}: " + (failure or "ok"), file=sys.stderr, flush=True)
        return name, experiment, metrics, failure

    workers = max(1, args.workers or min(16, len(os.sched_getaffinity(0))))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(work, jobs))

    scores: dict = {
        "_metadata": {
            "slice": SLICE,
            "delta": DELTA,
            "max_violation_rate": MAX_VIOLATION_RATE,
            "test_size_per_profile": TEST_SIZE,
            "profiles": PROFILE_NAMES,
            "experiments": EXPERIMENTS,
        },
        "experiments": {},
    }
    # A policy that breaks its risk constraint (or the protocol) in any experiment
    # has failed the task: the whole run is scored with the failure values, so a
    # failed method can never outrank one that solves the task on other metrics.
    failed_in: dict[str, list[str]] = {}
    for name, experiment, _, failure in results:
        if failure:
            failed_in.setdefault(name, []).append(experiment)
    for name, experiment, metrics, failure in results:
        entry = scores["experiments"].setdefault(experiment, {"results": {}, "_failures": {}})
        if name in failed_in:
            entry["results"][name] = dict(FAILED_VALUES)
            entry["_failures"][name] = failure or ("run failed in " + ", ".join(sorted(failed_in[name])))
        else:
            entry["results"][name] = metrics
    for experiment in EXPERIMENTS:
        entry = scores["experiments"].get(experiment)
        if entry is not None:
            entry["results"] = dict(sorted(entry["results"].items()))
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outputs", default="outputs", help="directory holding <method>/policy.json manifests")
    parser.add_argument("--scores", default="scoring/scores_train.json")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--save-outcomes", default="", help="optional directory for per-instance outcomes")
    args = parser.parse_args()
    scores = build_scores(args)
    out = Path(args.scores)
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
