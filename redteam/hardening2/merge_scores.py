#!/usr/bin/env python3
"""Merge per-batch evaluator score files into one (methods are scored independently).

Usage: python redteam/hardening2/merge_scores.py <out.json> <part.json>...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    out_path, *parts = sys.argv[1:]
    merged: dict = {}
    for part in parts:
        scores = json.loads(Path(part).read_text(encoding="utf-8"))
        if not merged:
            merged = {"_metadata": scores["_metadata"], "experiments": {}}
        for experiment, entry in scores["experiments"].items():
            target = merged["experiments"].setdefault(experiment, {"results": {}, "_failures": {}})
            for method, metrics in entry["results"].items():
                if method in target["results"] and target["results"][method] != metrics:
                    raise SystemExit(f"{method} differs between batches in {experiment}")
                target["results"][method] = metrics
            target["_failures"].update(entry.get("_failures", {}))
    for entry in merged["experiments"].values():
        entry["results"] = dict(sorted(entry["results"].items()))
    Path(out_path).write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(f"merged {len(parts)} files -> {out_path}")


if __name__ == "__main__":
    main()
