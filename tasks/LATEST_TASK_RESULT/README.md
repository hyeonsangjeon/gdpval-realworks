# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-20
- Status: SHIPPED — archived v1 sweep-template contract restored

## Task

- Record one BOLT-sized repair for the two known root test failures caused by
  the archived v1 grading sweep template.
- Restore historical v1 sweep rendering without moving the archive, changing
  active v2 grading, or executing any grading/model/API path.
- Lock the archive path and schema contract with a focused regression, then
  clear the historical deviation with executable evidence.

## Result

- Added `tasks/0720_monday/BOLT_ARCHIVED_SWEEP_TEMPLATE.md` with a falsifiable
  hypothesis, bounded file scope, non-goals, acceptance gates, and evidence.
- Changed the v1-only `SWEEP_TEMPLATE` constant and module documentation from
  the removed top-level path to
  `batch-runner/grading_configs/_archive_v1/_sweep_template.yaml`.
- Added a regression proving the default template is the tracked archive,
  remains schema version `1.0`, and is not duplicated in the active directory.
- Preserved deterministic `temperature=0`, `seed=42`, unique config naming,
  winner banner generation, and per-variant output isolation.
- Marked the original PR3 deviation resolved while retaining its incident and
  cause. Removed only pre-existing lint noise in the two touched Python files.
- Squash-merged the reviewed BOLT through PR #114 as
  `16305fd7c0661fdcb07bd298bfd4a9ccf4ffb381`. The automatic free
  `Aggregate Tests & Deploy` run `29731574595` completed successfully.

## Verification

- Reproduction before the fix: **2 failed** with `FileNotFoundError` for the
  removed top-level `_sweep_template.yaml`.
- Focused archive contract and both original failures: **3 passed**.
- Complete cost-sweep module: **13 passed, 0 failed, 0 warnings**.
- Complete root `scripts/__tests__`: **39 passed, 0 failed, 0 skipped,
  0 warnings**.
- Ruff and `py_compile` passed for the two touched Python files.
- `git diff --check` passed. `grading-engineer` approved the final path,
  output-isolation, archived-only, and documentation contracts with zero
  mandatory findings.
- The post-merge workflow completed successfully and no paid/model/grading/HF
  workflow ran for the merge commit.
- No sweep, Step 8, model/API call, grading run, HF upload, or paid execution
  occurred. Only the standard free push-triggered deploy gate ran.

## Remaining Work

- No implementation work remains for this archived v1 path-contract BOLT.
- The v1 sweep remains archived and reproduction-only. Any future v2 cost sweep
  requires a separate template and separately approved experiment plan.
