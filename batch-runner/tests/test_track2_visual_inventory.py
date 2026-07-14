"""Model-free regression for the checked-in Track 2 vision-call inventory."""

from __future__ import annotations

import json
from pathlib import Path

from core.grader_routing import Modality, resolve_runtime_routing


INVENTORY_SOURCE = Path(
    "../data/grades/"
    "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini"
    "__rubric_v2_tools_mini.json"
)
SUPPORTED_VISUAL_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".xlsm",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".webp",
}
EXPECTED_SUPPORTED_CALL_TOTAL = 467
EXPECTED_SUPPORTED_CALL_MAX = 68
CONFIGURED_TASK_CAP = 72


def _supported_calls(criterion: str, selected_paths: list[str]) -> int:
    decision = resolve_runtime_routing(criterion, selected_paths)
    if decision.modality is not Modality.VISUAL:
        return 0
    stable_paths = sorted(
        dict.fromkeys(selected_paths), key=lambda path: (path.casefold(), path)
    )
    return sum(
        Path(path).suffix.lower() in SUPPORTED_VISUAL_EXTENSIONS
        for path in stable_paths
    )


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