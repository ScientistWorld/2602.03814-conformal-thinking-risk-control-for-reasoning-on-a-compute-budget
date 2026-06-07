#!/usr/bin/env python3
"""Generate a small reasoning-trajectory dataset for Conformal Thinking.

The paper evaluates early stopping on LLM reasoning trajectories. The full
Qwen3/AIME/GPQA setup is too expensive for a smoke-test reproduction, so this
script creates deterministic trajectories with the same fields required by the
paper's calibration procedure: stepwise predictions, confidence signals, token
counts, and gold answers. The method code never generates labels or scores; it
only consumes the trajectories produced here.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def make_instance(rng: random.Random, idx: int, split: str) -> dict:
    total_steps = rng.randint(10, 18)
    token_stride = rng.randint(24, 46)
    gold = f"ans_{idx % 97}"

    solvable = rng.random() < (0.58 if split == "test" else 0.60)
    latest_solve_step = max(4, int(total_steps * 0.58))
    solve_step = rng.randint(3, latest_solve_step) if solvable else total_steps + 1
    false_confident = (not solvable) and rng.random() < 0.18

    steps = []
    for t in range(1, total_steps + 1):
        frac = t / total_steps
        tokens = t * token_stride + rng.randint(-5, 5)
        noise = rng.gauss(0.0, 0.035)

        if solvable:
            confidence = 0.18 + 0.76 * sigmoid(10.0 * (frac - solve_step / total_steps)) + noise
            correct = t >= solve_step
            if t < solve_step and rng.random() < 0.06:
                correct = True
        else:
            confidence = 0.10 + 0.20 * frac + noise
            if false_confident:
                confidence += 0.34 * sigmoid(12.0 * (frac - 0.68))
            correct = rng.random() < 0.015

        confidence = max(0.001, min(0.999, confidence))
        prediction = gold if correct else f"wrong_{idx}_{t % 11}"
        steps.append(
            {
                "step": t,
                "tokens": max(1, tokens),
                "prediction": prediction,
                "signals": {
                    "confidence": confidence,
                    "eat_confidence": max(0.001, min(0.999, confidence + rng.gauss(0.0, 0.055))),
                    "token_fraction": frac,
                },
            }
        )

    return {
        "id": f"{split}_{idx:04d}",
        "split": split,
        "question": f"Synthetic reasoning problem {idx}",
        "gold": gold,
        "solvable_under_budget": any(s["prediction"] == gold for s in steps),
        "steps": steps,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/synthetic_reasoning.jsonl")
    parser.add_argument("--validation-size", type=int, default=180)
    parser.add_argument("--test-size", type=int, default=360)
    parser.add_argument("--seed", type=int, default=260203814)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as handle:
        for i in range(args.validation_size):
            handle.write(json.dumps(make_instance(rng, i, "validation")) + "\n")
        for i in range(args.test_size):
            handle.write(json.dumps(make_instance(rng, i, "test")) + "\n")


if __name__ == "__main__":
    main()
