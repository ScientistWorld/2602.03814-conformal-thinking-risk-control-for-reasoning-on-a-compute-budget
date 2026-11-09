# Evaluation

## What is evaluated

A submission is a **stopping-policy program**. It is registered by a manifest
`outputs/<method_name>/policy.json`:

```json
{"command": ["python", "path/to/your_policy.py", "serve"]}
```

The command is run from the repository root. `scripts/evaluate_train.sh` (visible
development profiles), `scripts/evaluate.sh` (same, written to `scoring/scores.json`)
and `scripts/evaluate_test.sh` (held-out profiles) discover every manifest under
`outputs/` and score every method found; no arguments are needed. Only the
`command` field is read; any other field in the manifest is ignored. Every
operating point (one calibration draw and one target risk) runs in a **fresh
subprocess**: a policy sees exactly one calibration set and one pass over that
point's held-out instances, and nothing carries over between operating points.

## Online stopping protocol (JSON lines on stdin/stdout)

The evaluator writes one JSON object per line to the policy's stdin and, except
for `shutdown`, reads exactly one JSON object per line from its stdout
(diagnostics go to stderr, which is logged under `logs/`).

1. **Calibrate.** `{"type": "calibrate", "calibration_id": str, "epsilon": float, "delta": float, "instances": [...]}`
   Each instance is a labelled calibration trajectory:
   `{"id", "gold", "budget_tokens", "steps": [{"step", "tokens", "prediction", "signals": {"confidence", "eat_confidence", "token_fraction"}}, ...]}`.
   Reply `{"ok": true}`. The policy must use only these instances to set its
   stopping behaviour for the following held-out instances, targeting realized
   risk at most `epsilon` with probability at least `1 - delta`. Identifiers are
   opaque; the same `calibration_id` is used for the same calibration set at
   different target risks (in different processes).
2. **Begin an instance.** `{"type": "begin", "id": str, "budget_tokens": int}` → reply `{"ok": true}`.
   No label, gold answer, solvability flag or future chunk is ever sent for held-out instances.
3. **Step.** `{"type": "step", "step": {"step", "tokens", "prediction", "signals"}}` → reply
   `{"action": "continue" | "answer" | "defer"}`. Chunks are revealed one at a time.
   * `answer` stops and emits that chunk's `prediction`.
   * `defer` stops and abstains (counted as incorrect for accuracy).
   * `continue` asks for the next chunk. After the last chunk the budget is
     exhausted and the final chunk's prediction is emitted.
4. `{"type": "shutdown"}` (no reply).

The evaluator, not the policy, decides the exit type: an `answer` before the
last chunk is an **early answer**; an `answer` or `continue` at the last chunk is
a **budget exit**; `defer` at any chunk is a **defer**. Tokens are charged up to
the chunk where the policy stopped (`tokens` is cumulative). Any other reply, a
crash, or a non-JSON line is a protocol failure.

Trial answers are opaque numeric strings; wrong answers can persist across
chunks and correct answers can flicker, so answer text alone does not reveal
correctness.

## Data

Trajectories are simulated reasoning runs. Each *profile* stands for one
(reasoning model, dataset) pair and has its own mapping from signals to
correctness (signal scale and curvature, noise, how often hopeless runs become
falsely confident, how persistent wrong answers are). The visible side uses
the public profiles in `data/generate_synthetic_reasoning.py`; the held-out test
uses different profiles drawn from the same documented parameter ranges, with
their own calibration pools and test sets. A stopping rule therefore has to be
set from each profile's calibration data; thresholds copied from the public
profiles do not transfer.

An instance is **solvable** when its full-budget (final-chunk) answer is correct.

## Experiments (all fixed by the evaluator)

Every experiment uses 3 profiles, 1000 held-out instances per profile, labelled
calibration sets drawn from a separate pool of 1000 per profile, and `delta = 0.1`.
Each (profile, calibration draw, epsilon) triple is one operating point.

| Experiment | Solvable:unsolvable mix | Calibration size | Draws per profile | Target risks `epsilon` |
|---|---|---:|---:|---|
| `adaptive_budget_efficiency` | natural (~58% solvable) | 400 | 4 | 0.10, 0.15, 0.20 |
| `risk_control` | natural, separate profiles | 50 | 10 | 0.05, 0.10, 0.20, 0.25 |
| `difficulty_mix_3_1` | 3:1 | 400 | 4 | 0.10, 0.15, 0.20 |
| `difficulty_mix_1_1` | 1:1 | 400 | 4 | 0.10, 0.15, 0.20 |
| `difficulty_mix_1_3` | 1:3 | 400 | 4 | 0.05, 0.10, 0.125 |

The 1:3 mix uses tighter tolerances because there, deferring every instance at
the first chunk already has a premature-defer risk of only about 0.18.

## Metrics (per experiment, averaged over its operating points)

Scored (enter the ranking):

- **token_savings** (primary, coefficient 1.0): `1 - tokens used / full-budget tokens`.
- **accuracy** (coefficient 0.5): fraction of held-out instances whose emitted answer is correct; a defer counts as incorrect.

Constraints (enforced by a gate, coefficient 0):

- **false_positive_risk**: fraction of instances with an early answer that is wrong.
- **false_negative_risk**: for each deferred instance, the fraction of its chunks from the defer point to the end whose prediction is correct; averaged over all instances (0 for non-deferred instances).
- **violation_rate**: fraction of operating points where realized `false_positive_risk > epsilon` or `false_negative_risk > epsilon`.

**Gate.** If `violation_rate > 0.15` in any experiment, or the policy breaks the
protocol anywhere, the whole run is failed: every experiment reports accuracy 0,
token savings 0, risks 1, violation rate 1 (`constraint_satisfied = 0`), and the
reason is recorded under `_failures`. A valid policy therefore always scores at
least as high as a failed one.

Diagnostics (coefficient 0): `solvable_accuracy`, `unsolvable_token_savings`,
`defer_fraction`, `defer_precision`, `budget_exit_fraction`, `constraint_satisfied`.

No metric depends on wall-clock time.

## Baselines scored alongside every method

- `full_budget` (built into the evaluators): never stops early.
- `upper_only`: stops once a confidence signal is high enough; no early abstention.
- `naive_calibration`: chooses its operating point on raw validation risk without a finite-sample correction.

## Paper setup (for reference)

The paper evaluates Qwen3-8B, Qwen3-30B-A3B, DeepSeek-R1-Distill-Qwen-32B and
Qwen3-VL-8B on AIME 1983-2025, DeepScaleR without AIME, GPQA-Diamond and
MathVision, with risk-control checks over 40 random validation/test splits with
50 validation examples and epsilon swept over [0, 1]. Its results are curves
(risk vs. epsilon, accuracy vs. tokens), not scalar tables, so this benchmark's
reference values come from its own scaled runs.
