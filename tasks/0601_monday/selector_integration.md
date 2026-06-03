# SELECTOR INTEGRATION

## One-line Conclusion
The deterministic deliverable selector is integrated into the v2 tool-calling grader path with minimal scoring changes: it chooses the files shown to the judge/prechecks, separates reference echoes, records task-level and item-level audit fields, handles the four selection states, and applies hybrid routing including split-children aggregation. No Azure run, vision run, full-220 regrade, push, or merge was performed.

## Integration Points
- `batch-runner/core/grader.py:397` routes v2 tool-calling tasks into `_grade_task_with_selector`; legacy v1 and batch paths are left unchanged.
- `batch-runner/core/grader.py:476` calls `select_deliverables(...)` once per task, before item prechecks/judge calls.
- `batch-runner/core/grader.py:488` applies `plan_targets_for_criterion(...)` per rubric item so each item sees only its selected target paths.
- `batch-runner/core/grader.py:1593` calls `ToolCallingJudge.judge_item(...)` with selected candidate paths plus separately labeled reference paths.
- `batch-runner/core/tool_calling_judge.py:185` accepts `reference_file_names` for prompt rendering only.
- `batch-runner/prompts/grader_judge_v2.md:114` now labels selected candidate files separately from `Reference input files (NOT candidate deliverables)`.

## Selection States
- `ok`: normal precheck/judge flow using selected primary targets.
- `selection_error`: harness could not choose despite candidates; items are marked `judge_error`, `score_excluded=true`, and task `error="selection_error"` so this is visible but not scored as a rubric failure.
- `no_generated_candidate`: model produced no generated candidate after reference set-diff; items fail with score impact, but task `error` remains null because this is a model deliverable failure, not a harness failure.
- `wrong_format_primary`: generated files exist but none match the requested primary format; existence/format items fail with score impact, while task-level overall style is `score_excluded=true` because there is no valid style target.

## Hybrid Routing
- `manifest`, `file_target`, and `primary_bundle` route a criterion to selected primary paths only.
- `split_children` calls the judge once per selected primary target and records child verdicts.
- Split aggregation is `blocking_min_else_mean`: any child `fail` uses the minimum child partial; otherwise the item uses the mean child partial. Child `judge_error` propagates to item `judge_error`.

## Audit Fields
Task-level audit fields now serialize through the existing `asdict` grade JSON path:

- `selected_deliverables`
- `reference_files_excluded`
- `selection_rule`
- `selection_status`
- `selection_error`

Item-level audit fields are recorded on every selector-path item:

- `target_scope`
- `target_ids`
- `child_grades`
- `aggregation_rule`
- `selected_paths`
- `support_paths_visible`
- `selection_status`
- `selection_error`
- `score_excluded`

`batch-runner/schemas/grade.schema.json` allows these fields so partial/final grade JSON validation preserves the audit trail.

## Verification
Commands run:

```bash
PYTHONPATH=batch-runner .venv/bin/python -m pytest \
  batch-runner/tests/test_deliverable_selector.py \
  batch-runner/tests/test_grader_selector_integration.py \
  batch-runner/tests/test_grader_tool_dispatch.py \
  batch-runner/tests/test_tool_calling_judge.py \
  batch-runner/tests/test_grader.py -q
```

Result: `55 passed, 1 warning`.

```bash
cd batch-runner
PYTHONPATH=. ../.venv/bin/python -m pytest \
  tests/test_grade_schema.py \
  tests/test_step8_grade.py -q
```

Result: `21 passed, 1 warning`.

```bash
PYTHONPATH=batch-runner .venv/bin/python -m pytest \
  batch-runner/tests/test_grader_judge_v2_prompt.py -q
```

Result: `8 passed`.

Integrated selector dry-run through `Grader._select_deliverables`:

- gold owner-target files: 20/20
- checked gold task classes: 5/5
- wrong-format controls: 7/7
- no-generated control: `no_generated_candidate`

## Scope Guard
No scoring/verdict/evidence parsing logic was replaced. The selector changes which file paths are visible to prechecks and the judge. Existing v1 text-extraction and batch-tier paths remain unchanged.

## Next
Owner review, then SP secret rotation, one controlled regrade, and v1/v2 comparison using the new audit fields to restore exactly which files every item saw.
