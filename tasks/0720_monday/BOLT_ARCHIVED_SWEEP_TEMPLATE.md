# BOLT: Restore the Archived v1 Sweep Template Contract

- Date: 2026-07-20
- Status: `APPROVED`
- Base: `main@eaacc6769406399759c84539d84fdda9da67abb5`
- Branch: `bolt/archived-sweep-template`
- Execution boundary: model-free only

## Outcome

Restore the historical v1 grading-cost sweep renderer after its template moved
under `batch-runner/grading_configs/_archive_v1/`. The renderer must consume the
archived template explicitly, preserve its deterministic temperature/seed and
per-variant output guards, and make the two stale root tests pass again.

## Falsifiable Hypothesis

`render_temp_config()` fails only because `SWEEP_TEMPLATE` still points to the
removed top-level `grading_configs/_sweep_template.yaml`. Pointing the constant
and user-facing script documentation at `_archive_v1/_sweep_template.yaml`
should make both known failures pass without changing rendered config semantics.

## Reproduction

```text
python3 -m pytest -q \
  scripts/__tests__/test_grading_cost_sweep.py::test_render_temp_config_enforces_seed_temp \
  scripts/__tests__/test_grading_cost_sweep.py::test_winner_config_has_comment_banner

2 failed: FileNotFoundError for
batch-runner/grading_configs/_sweep_template.yaml
```

The tracked template exists only at
`batch-runner/grading_configs/_archive_v1/_sweep_template.yaml`.

## Scope

Allowed implementation files:

- `scripts/grading_cost_sweep.py`
- `scripts/__tests__/test_grading_cost_sweep.py`
- `tasks/rebuilding_grading_task/DEVIATIONS.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`
- this BOLT record

## Non-Goals

- Do not run a grading sweep, Step 8, model/API call, or paid workflow.
- Do not make the v1 sweep an active or recommended grading path.
- Do not change v2 grading, routing, score math, prompts, prices, or budgets.
- Do not move or duplicate the archived template.
- Do not copy stale code or rolling documentation from preserved worktrees.

## Implementation Steps

1. Add a regression assertion that the default sweep template resolves to the
   tracked `_archive_v1` file and remains schema v1.
2. Update the sweep script constant and module documentation to that path.
3. Run the two reproducing tests, then the complete cost-sweep test module.
4. Mark the historical DEVIATIONS row resolved without deleting the incident.
5. Run branch-scoped static checks and update canonical completion records.

## Acceptance Gates

- The archived template is the only default template consumed by the v1 sweep.
- Both original failures pass.
- The complete `test_grading_cost_sweep.py` module passes.
- Rendered variants still force `temperature=0`, `seed=42`, unique config names,
  and isolated per-variant output directories.
- Active v2 config defaults and workflows are unchanged.
- `git diff --check` passes.
- No model/API, grading, upload, workflow dispatch, or remote mutation occurs.

## Evidence

| Check | Result |
|---|---|
| Reproduction | `2 failed` with stale top-level template path |
| Focused fix | `3 passed` (path contract plus both original failures) |
| Full cost-sweep module | `13 passed`, 0 warnings |
| Root scripts suite | `39 passed`, 0 failed/skipped/warnings |
| Static checks | Ruff clean and `py_compile` passed for both touched Python files |
| Independent review | `grading-engineer` approved with 0 mandatory findings |

## Decision

`APPROVED` — the historical v1 renderer consumes only the tracked archive;
output isolation is regression-locked, and active v2 grading plus every
paid/runtime path remain unchanged.
