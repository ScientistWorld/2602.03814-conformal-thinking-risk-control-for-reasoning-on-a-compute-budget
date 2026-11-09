#!/usr/bin/env python3
"""Upper-threshold-only stopping baseline ("stop when confident").

Prior adaptive-reasoning work stops once a confidence signal crosses a single
upper threshold. This baseline calibrates that threshold with the same
finite-sample risk control as the reference but has no lower (no-progress)
exit. It speaks the benchmark's online stopping protocol on stdin/stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "method"))
from conformal_thinking import ConformalThinkingPolicy, serve  # noqa: E402

if __name__ == "__main__":
    serve(ConformalThinkingPolicy(variant="upper_only", calibration="ucb"))
