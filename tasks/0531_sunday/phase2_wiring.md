# PHASE 2 — perception wiring + instrumentation

## Wiring (file:line, on branch `feat/wire-perception`)

Two-file change. Read-only on every other module.

| where | what |
|---|---|
| [batch-runner/core/grader.py](../../batch-runner/core/grader.py#L1138-L1177) `_build_tool_judge` | Reads `judge.perception.visual` and `judge.perception.audio` from config. When `model` is present, instantiates `VisionPerception` / `AudioPerception` (sharing the Grader's Azure client) and injects them into `ToolCallingJudge(vision_perception=..., audio_perception=...)`. Previously these blocks were dead config. |
| [batch-runner/core/grader.py](../../batch-runner/core/grader.py#L378-L386) `grade_task` | Calls `self._tool_judge.reset_perception()` at each task boundary so per-task call caps reset. |
| [batch-runner/core/grader.py](../../batch-runner/core/grader.py#L1212-L1218) `_judge_via_tool_calling` | Copies the per-item runtime instrumentation (`routing_modality`, `perception_called`, `tools_used`) from the `ToolCallingResult` into the `ItemGrade` so it lands in `data/grades/*.json`. |
| [batch-runner/core/grader.py](../../batch-runner/core/grader.py#L118-L127) `ItemGrade` | Adds 3 instrumentation fields (see schema below). |
| [batch-runner/core/tool_calling_judge.py](../../batch-runner/core/tool_calling_judge.py#L78-L84) `ToolCallingResult` | Adds `tools_used: List[str]` and `perception_called: bool`. |
| [batch-runner/core/tool_calling_judge.py](../../batch-runner/core/tool_calling_judge.py#L205-L306) `judge_item` loop | Appends every dispatched function-call name to `tools_used`. |
| [batch-runner/core/tool_calling_judge.py](../../batch-runner/core/tool_calling_judge.py#L335-L346) `reset_perception` | Calls `.reset()` on each wired sub-judge (no-op when unwired). |
| [batch-runner/core/tool_calling_judge.py](../../batch-runner/core/tool_calling_judge.py#L620-L716) `_finalize` | Derives `perception_called = any(t in {"vision_judge","audio_judge"})` and stamps both fields onto every return path (including the `judge_error` and JSON-parse-fail branches). |

The dispatch path that exposes `vision_judge` / `audio_judge` to the
model already existed in `tool_calling_judge.py:419` (guarded on the
sub-judge being non-None) — the wiring change is what makes that guard
true at runtime.

## Instrumentation schema (added to `data/grades/<exp>.json` -> tasks[].items[])

Defined in `ItemGrade` (grader.py:118-127):

| field | type | semantics |
|---|---|---|
| `routing_modality` | `str | null` | `visual` / `audio` / `formatting` / `text` from `grader_routing.classify_criterion`. `null` on precheck items (no judge call). |
| `perception_called` | `bool` | `True` iff `vision_judge` or `audio_judge` was dispatched at least once for this item. |
| `tools_used` | `list[str] | null` | Ordered list of dispatched function names (`read_deliverable`, `vision_judge`, `audio_judge`, ...). Empty list on judge-decided items that fired zero tools; `null` on precheck. |

The fourth field `model_tier` the rev2 spec mentions is **not** added —
the v2 grader is single-tier per run (config-bound), and tier is already
captured at the per-run level in `judge.model`. Adding a per-item tier
column would be redundant noise. Flagged for owner review.

## Runtime proof (not config-only)

`batch-runner/tests/test_perception_wiring.py` — 5 tests, all PASS:

| test | proves |
|---|---|
| `test_grader_wires_perception_subjudges` | v2 config with `perception.{visual,audio}` → `tj.vision_perception` / `tj.audio_perception` are non-None instances, share the Grader's Azure client, and carry the right deployment names. |
| `test_grader_no_perception_block_leaves_subjudges_none` | dead-config baseline (no perception block) leaves both sub-judges None, matching the pre-wiring state. |
| `test_vision_dispatch_sets_perception_called_instrumentation` | When the model dispatches a `vision_judge` call on a VISUAL item: `perception_called=True`, `tools_used` contains `"vision_judge"`, `routing_modality=="visual"`, and the sub-judge's `judge()` was actually called. |
| `test_text_item_has_no_perception_call` | TEXT-modality items don't trigger perception (`perception_called=False`, no `vision_judge` in `tools_used`). |
| `test_reset_perception_resets_subjudges` | Per-task `reset()` propagates to wired sub-judges. |

```
$ pytest tests/test_perception_wiring.py -q
5 passed, 1 warning in 1.26s
```

This satisfies rule 9 (declared != wired): the *capability* is proven by
runtime instrumentation, not by config inspection.

## What's *not* wired here (recorded, not fixed)

Per ownership scope and rev2 (dead config: 기록만):

- `grades_per_task: 3` is still **not wired**. Grader still grades each
  task once.
- `compaction` array-shape is still disabled (`compact_threshold=None`).
  See the existing comment at `tool_calling_judge.py:235-244`.
- `model_tier` per-item instrumentation: not added (see above).

These are dead config and should NOT be reported as functional.
