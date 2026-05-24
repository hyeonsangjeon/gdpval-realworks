# `cost_opt_results/` — sweep run artifacts

Per-run output of `scripts/grading_cost_sweep.py` (Track 2 of
[TASK_GRADE_COST_SWEEP](../TASK_GRADE_COST_SWEEP.md)). Each sweep creates
a timestamped subdir; raw artifacts stay local (`.gitignore`), but
`RESULTS.md` is committable.

## Run a sweep

```
# Dry-run (validates plan + estimates costs; no API calls)
python scripts/grading_cost_sweep.py --dry-run

# Live sweep
python scripts/grading_cost_sweep.py \
  --plan tasks/0523_saturday/grading_cost_sweep_plan.yaml \
  --output-dir tasks/0523_saturday/cost_opt_results/$(date -u +%Y-%m-%dT%H-%M-%SZ)/

# Resume
python scripts/grading_cost_sweep.py --resume tasks/0523_saturday/cost_opt_results/<ts>/

# Partial phases
python scripts/grading_cost_sweep.py --phases A
```

## Files written per run

```
<ts>/
├── plan.snapshot.yaml      # frozen copy of the plan at run start
├── progress.json           # resume cache (completed variants, cum cost)
├── runs/<variant>/         # config.yaml + grade.json + run.log per variant
├── summary.json            # all variant metrics + winner
├── RESULTS.md              # human report (TL;DR, Phase A/B/C, Diversity)
└── winner_config.yaml      # drop-in candidate (when a winner is found)
```

## Read `RESULTS.md`

- **TL;DR** — winner, full-run cost vs baseline, score Δ.
- **Phase A/B/C** — single-axis / combos / stability tables.
- **Diversity Validator** — gpt-4o agreement (advisory).
- **Caveats** — token-based estimates; verify vs tenant billing.

## Promote the winner

1. Inspect `winner_config.yaml`; keep the auto-generated banner line.
2. Copy to `batch-runner/grading_configs/recommended_<YYYY-MM-DD>.yaml`.
3. Validate with a real 220-task full sweep (Δscore ±2pp vs baseline).
4. Open a PR replacing `default_gpt5pro.yaml`; reference the sweep dir.

## Hard rules

- Sweep does NOT touch `data/grades/` — variants live here only.
- Sweep does NOT modify `step8_grade.py`, `core/grader*`, or prompts.
- Default cost cap **$80**; sweep aborts mid-run if exceeded.
- `temperature=0`, `seed=42` enforced in every rendered config.
