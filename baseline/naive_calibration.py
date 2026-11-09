#!/usr/bin/env python3
"""Naive validation tuning baseline.

Selects stopping thresholds directly on the empirical validation risk, with no
finite-sample correction (the paper's NAIVE calibration). It speaks the
benchmark's online stopping protocol on stdin/stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "method"))
from conformal_thinking import ConformalThinkingPolicy, serve  # noqa: E402

if __name__ == "__main__":
    serve(ConformalThinkingPolicy(variant="dual", calibration="naive"))
