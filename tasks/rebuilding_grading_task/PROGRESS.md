# PR3 Decision Run — PROGRESS

Started: 2026-05-30 (autonomous run per TASK_grading_v2_cost_decision.md)

| step | result | artifacts | next |
|---|---|---|---|
| 0a (schema check) | existing exp003 v2 grade JSONs have NO cached_tokens — only judge_input_tokens / judge_output_tokens. \$168 estimate priced raw input at full rate. | data/grades/exp003*v2*.json | add cached_tokens capture to ToolCallingJudge |
| 0b (code) | Added `cached_tokens` field to `ToolCallingResult` + side-channel `_last_cached_tokens` accumulator in `Grader` → `TaskGrade.judge_cached_tokens` (default 0, optional). `analyze_grade_run.py` now computes `effective_cost` (cache-discounted at 50%) + `cache_hit_ratio`. Schema `additionalProperties:true` auto-allows the new field. | batch-runner/core/tool_calling_judge.py, batch-runner/core/grader.py, scripts/analyze_grade_run.py | run 3-task probe on exp998/default_v2 |
| 0c (regression) | batch-runner 563 passed / 5 skipped / 0 fail. scripts 2 fail (test_grading_cost_sweep) — pre-existing, unrelated (refs archived configs from PR2 task 207). | pytest -q | proceed |
