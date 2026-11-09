# Scoring audit experiments

Each directory contains a `run.sh`, a declarative `settings.json`, evaluator
logs, saved train/test scores, and a run status. `candidate.py` contains the real
candidate implementations shared by those entry points; `run_case.py` installs
the candidate into `method/`, executes it, runs the public train evaluation and
then **`bash scripts/evaluate_test.sh` with no arguments in a new process**, saves
results, and restores the data, outputs, and scores. No evaluator or interpreter
is modified. Failed test runs retain their rejection logs.

Run all experiments as a CPU scheduler job with `bash redteam/run_all.sh`.
Raw reusable reference outputs are cached under ignored `state/` and generated
candidate outputs under ignored `*/artifacts/`. The small scores and all source
ship in git. If the cache is absent, it is copied from the gym's reference outputs.
The original visible implementation is also saved as `reference_implementation.py`.

The candidate uses only the future scientist's visible files, plus the reference
output reuse explicitly allowed for this audit. `analyze.py` is separate audit
analysis: it reads the hidden scoring coefficients after the runs. Those
coefficients never enter a candidate's decisions.

The supplied test scores do not match the deterministic reference rerun. Ranking
therefore retains the supplied `original_scores_test.json` as the declared anchor
and separately reports comparisons with the rerun reference.

Normalized ranks depend on the population of future submissions. We report a
specified audit population, a quality-control population, and a two-attempt
reference/candidate population. Every calculation uses the absolute coefficient,
the declared better direction, experiment weight, and per-metric population
standard deviation. A zero-variance metric contributes zero. These are relative
rank differences, with the supplied reference zero, rather than invented raw-unit
scores. Both the audit and quality populations include the supplied reference.
For comparisons with a shortcut, `quality_plus_candidate` adds that shortcut to
the quality population before computing standard deviations. This is the quality
column in `summary.tsv` and `REDTEAM.md`. The older `quality_pool` fields retain
fixed-scale diagnostic comparisons; they are not used to claim shortcut wins.
