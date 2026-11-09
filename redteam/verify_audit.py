#!/usr/bin/env python3
"""Lightweight evidence/restoration checks; does not run a method or evaluator."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "redteam"


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    start = (AUDIT / "start_commit.txt").read_text().strip()
    protected = ["baseline", "briefing", "data", "environment", "eval", "method", "scoring", "scripts"]
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", start, "--", *protected], cwd=ROOT, text=True
    ).splitlines()
    analysis = load(AUDIT / "analysis.json")
    seeds = [load(AUDIT / f"reference_seed_{s}/scores_test.json")["experiments"] for s in [11, 22, 33]]
    equal_decisions = {}
    for filename in ["results.json", "ratio_3_1.json", "ratio_1_1.json", "ratio_1_3.json"]:
        original = load(AUDIT / "state/reference_outputs/conformal_thinking" / filename)
        fresh = load(AUDIT / "reference_seed_11/artifacts/conformal_thinking" / filename)
        a = min(original["epsilons"], key=lambda p: abs(p["epsilon"] - .32))
        b = min(fresh["epsilons"], key=lambda p: abs(p["epsilon"] - .32))
        equal_decisions[filename] = a["policies"]["conformal_thinking"]["decisions"] == b["policies"]["conformal_thinking"]["decisions"]
    output_restored = all(
        (ROOT / "outputs" / p.relative_to(AUDIT / "state/reference_outputs")).exists()
        and digest(p) == digest(ROOT / "outputs" / p.relative_to(AUDIT / "state/reference_outputs"))
        for p in (AUDIT / "state/reference_outputs").rglob("*.json")
    )
    statuses = [load(p) for p in sorted(AUDIT.glob("*/status.json"))]
    evidence = {
        "start_commit": start,
        "protected_paths_differing_from_start": changed,
        "outputs_restored": output_restored,
        "scoring_scores_test_restored": digest(ROOT / "scoring/scores_test.json") == digest(AUDIT / "original_scores_test.json"),
        "seeds": [11, 22, 33],
        "seed_experiments_identical": seeds[0] == seeds[1] == seeds[2],
        "seed_rank_range": analysis["seed_rank_range"],
        "original_and_rerun_decisions_identical": equal_decisions,
        "cached_and_rerun_metrics_identical": load(AUDIT / "reference_cached/scores_test.json")["experiments"] == seeds[0],
        "stored_scores_match_rerun": analysis["reference_matches_initial_scores_test"],
        "attempt_count": len(statuses),
        "successful_test_count": sum(s["test_returncode"] == 0 for s in statuses),
        "rejected_test_count": sum(s["test_returncode"] != 0 for s in statuses),
        "every_hidden_command_exact": all(s["hidden_command"] == "bash scripts/evaluate_test.sh" for s in statuses),
        "candidate_file_removed": not (ROOT / "method/redteam_candidate.py").exists(),
        "generated_data_removed": not (ROOT / "method/redteam_generated_data").exists(),
        "unrestored_case_backups": [str(p.relative_to(ROOT)) for p in AUDIT.glob("*/worktree_before")],
    }
    (AUDIT / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    assert not changed, changed
    assert output_restored and evidence["scoring_scores_test_restored"]
    assert evidence["seed_experiments_identical"] and all(equal_decisions.values())
    assert evidence["cached_and_rerun_metrics_identical"]
    assert evidence["attempt_count"] == 26 and evidence["successful_test_count"] == 22
    assert evidence["every_hidden_command_exact"]
    assert evidence["candidate_file_removed"] and evidence["generated_data_removed"]
    assert not evidence["unrestored_case_backups"]
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
