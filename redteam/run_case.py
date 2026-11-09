#!/usr/bin/env python3
"""Install one candidate, evaluate in fresh subprocesses, save evidence, restore.

The hidden command is always exactly `bash scripts/evaluate_test.sh` without
arguments. Nothing modifies eval/, its process, imports, or Python environment.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORING_FILES = ["scores_train.json", "scores_test.json"]


def copytree(source, destination):
    shutil.copytree(source, destination, dirs_exist_ok=True)


def remove(path):
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def run(command, log):
    with log.open("w") as handle:
        completed = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
    return completed.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    args = parser.parse_args()
    case = Path(args.case)
    if not case.is_absolute():
        case = ROOT / case
    state = ROOT / "redteam/state"
    state.mkdir(parents=True, exist_ok=True)
    if not (state / "reference_outputs").exists():
        copytree(ROOT / "outputs", state / "reference_outputs")
    backup = case / "worktree_before"
    if backup.exists():
        raise RuntimeError(f"Unrestored previous attempt: {backup}")
    backup.mkdir()
    copytree(ROOT / "outputs", backup / "outputs")
    copytree(ROOT / "data", backup / "data")
    for name in SCORING_FILES:
        if (ROOT / "scoring" / name).exists():
            shutil.copy2(ROOT / "scoring" / name, backup / name)
    installed = ROOT / "method/redteam_candidate.py"
    if installed.exists():
        raise RuntimeError("Refusing to overwrite an existing candidate")
    status = {"case": case.name, "hidden_command": "bash scripts/evaluate_test.sh"}
    started = time.monotonic()
    try:
        remove(ROOT / "outputs")
        (ROOT / "outputs").mkdir()
        copytree(state / "reference_outputs/baseline", ROOT / "outputs/baseline")
        for name in SCORING_FILES:
            remove(ROOT / "scoring" / name)
        shutil.copy2(ROOT / "redteam/candidate.py", installed)
        status["method_returncode"] = run([sys.executable, str(installed), str(case)], case / "method.log")
        if status["method_returncode"]:
            return
        status["train_returncode"] = run(["bash", "scripts/evaluate_train.sh"], case / "train.log")
        if (ROOT / "scoring/scores_train.json").exists():
            shutil.copy2(ROOT / "scoring/scores_train.json", case / "scores_train.json")
        if case.name == "shortcut_summary_forgery":
            # Try directly authored score files as well as aggregate fields.
            (ROOT / "scoring/scores_test.json").write_text('{"forged_score": 1000000000}\n')
        status["test_returncode"] = run(["bash", "scripts/evaluate_test.sh"], case / "test.log")
        if (ROOT / "scoring/scores_test.json").exists():
            shutil.copy2(ROOT / "scoring/scores_test.json", case / "scores_test.json")
        # Retain reusable raw evidence but do not commit bulky generated artifacts.
        copytree(ROOT / "outputs", case / "artifacts")
        summaries = {}
        for path in (ROOT / "outputs/conformal_thinking").glob("*.json"):
            content = json.loads(path.read_text())
            summaries[path.name] = {"config": content.get("config"),
                                    "epsilons": [p["epsilon"] for p in content.get("epsilons", [])]}
        (case / "method_config.json").write_text(json.dumps(summaries, indent=2) + "\n")
    finally:
        status["elapsed_seconds"] = time.monotonic() - started
        (case / "status.json").write_text(json.dumps(status, indent=2) + "\n")
        remove(ROOT / "outputs")
        shutil.move(str(backup / "outputs"), ROOT / "outputs")
        remove(ROOT / "data")
        shutil.move(str(backup / "data"), ROOT / "data")
        for name in SCORING_FILES:
            remove(ROOT / "scoring" / name)
            if (backup / name).exists():
                shutil.move(str(backup / name), ROOT / "scoring" / name)
        remove(installed)
        remove(ROOT / "method/redteam_generated_data")
        remove(backup)


if __name__ == "__main__":
    main()
