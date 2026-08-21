"""Model-free regression for the checked-in Track 2 vision-call inventory."""

from __future__ import annotations

import json
from pathlib import Path

from core.grader_routing import Modality, resolve_runtime_routing
from core.tool_calling_judge import ToolCallingJudge


INVENTORY_SOURCE = Path(
    "../data/grades/"
    "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini"
    "__rubric_v2_tools_mini.json"
)
# Derived from the runtime, never restated. This file used to keep its own
# copy of the supported-extension set, and the copy is how a drift hides: when
# .docx rendering was added, a hardcoded list here would have kept reporting
# the old call volume against the cap and nothing would have said so.
#
# The totals below are a forward projection -- what a run over these 220 tasks
# would plan today -- not a record of what the checked-in run did. Adding a
# format moves them, which is the point: it forces a fresh look at the cap.
# .docx took the total from 466 to 574 and left the per-task max at 68,
# because the task holding the max carries no document deliverable.
EXPECTED_SUPPORTED_CALL_TOTAL = 574
EXPECTED_SUPPORTED_CALL_MAX = 68
CONFIGURED_TASK_CAP = 72


def _supported_calls(criterion: str, selected_paths: list[str]) -> int:
    decision = resolve_runtime_routing(criterion, selected_paths)
    if decision.modality is not Modality.VISUAL:
        return 0
    return len(ToolCallingJudge.planned_supported_visual_names(selected_paths))


def _item_supported_calls(item: dict) -> int:
    criterion = str(item.get("criterion") or "")
    children = item.get("child_grades") or []
    if item.get("target_scope") == "split_children" and children:
        return sum(
            _supported_calls(criterion, list(child.get("selected_paths") or []))
            for child in children
        )
    return _supported_calls(criterion, list(item.get("selected_paths") or []))


def test_checked_in_220_inventory_fits_task_vision_cap():
    payload = json.loads(INVENTORY_SOURCE.read_text(encoding="utf-8"))
    task_calls = [
        sum(_item_supported_calls(item) for item in task.get("items", []))
        for task in payload.get("tasks", [])
    ]

    assert len(task_calls) == 220
    assert sum(task_calls) == EXPECTED_SUPPORTED_CALL_TOTAL
    assert max(task_calls) == EXPECTED_SUPPORTED_CALL_MAX
    assert EXPECTED_SUPPORTED_CALL_MAX <= CONFIGURED_TASK_CAP