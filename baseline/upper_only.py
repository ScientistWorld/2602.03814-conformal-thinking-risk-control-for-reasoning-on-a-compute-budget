#!/usr/bin/env python3
"""Upper-threshold-only baseline from adaptive reasoning work."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "method"))
from conformal_thinking import run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/synthetic_reasoning.jsonl")
    parser.add_argument("--output", default="outputs/baseline/results.json")
    parser.add_argument("--calibration", choices=["ucb", "naive"], default="ucb")
    parser.add_argument("--delta", type=float, default=0.1)
    parser.add_argument("--epsilons", nargs="+", type=float, default=[0.18, 0.25, 0.32, 0.40])
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
