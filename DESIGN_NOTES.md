# Design Notes (current gym, iteration 11)

- **Interface.** A method is a stopping-policy program registered in `outputs/<method>/policy.json`. Evaluators run it through a JSON-lines protocol (calibrate, then begin/step per held-out instance) in a fresh process per operating point. See `briefing/evaluation.md`.
- **Train vs test.** `eval/train/evaluate_split.py` builds tasks from the public profiles in `data/generate_synthetic_reasoning.py`. `eval/test/evaluate_split.py` builds them from private profiles and seeds in `eval/test/hidden_tasks.py`. The two share no code. Experiments, operating points, metrics and the gate are identical.
- **Ownership.** The evaluators own trajectories, gold answers, calibration draws, epsilon/delta, sizes, exit semantics, token accounting and the failure gate. Nothing the method writes is scored.
- **Scoring.** `token_savings` (1.0) and `accuracy` (0.5) are scored. False-positive/false-negative risk and the violation rate are gated constraints (violation rate > 0.15 in any experiment ⇒ failure values everywhere).
- **Audit evidence.** `redteam/hardening/` and `HARDENING.md`.
