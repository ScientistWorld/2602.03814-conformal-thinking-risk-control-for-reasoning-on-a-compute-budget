# Verification Report (iteration 11)

- `python validate.py --compare` passes on the final score files.
- The reference method is deterministic. Its hidden-test scores were identical across the audit run, a second registered copy, a rerun under per-operating-point isolation, and the final `scripts/reproduce.sh` run.
- Every honest variant ranks in the expected direction on both the visible train profiles and the hidden test, with gaps far larger than the paired test noise. Every shortcut probe from REDTEAM.md, plus four new ones, either fails the gate or ties/undercuts the reference (`HARDENING.md`).
- `eval/` does not import `method/`. `eval/train/` and `eval/test/` are independent. No committed code references `shared/`. `scripts/download.sh` has no external resources to fetch: all data is simulated, and it writes optional public development samples to `data/downloads/`.
- Limitation: synthetic trajectories; the paper reports curves only, so `scoring/reference.json` `results` hold this gym's hidden-test reference values.
