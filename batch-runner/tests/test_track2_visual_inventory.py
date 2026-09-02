"""Model-free regression for the checked-in Track 2 vision-call inventory."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

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
#
# Two limits, because the figures look more complete than they are.
#
# First, the projection reads the selected_paths this run recorded, so the 5
# tasks it recorded as selection_error contribute nothing -- they have no
# paths. The selector now resolves those (set_diff_then_uniform_primaries),
# and a fresh run would plan roughly 18 more calls than the figure below,
# peaking at 5 on any one of them. That does not move the max, which is why
# this stays a fixed expectation rather than a re-derived one: deriving it
# would need the task instructions, which this file deliberately does not
# read.
#
# Second -- and this is why the numbers here are NOT a basis for the task cap
# -- `resolve_runtime_routing` is called without text-layer signals, and only
# a measured signal escalates. The no-text-layer escalation is therefore
# invisible to this projection. `test_the_projection_is_exact_or_blind`
# below measures how invisible, against the 185-task gold run. This file
# counts what a criterion asks for by its wording. What a task actually
# spends is counted from a run, in
# `test_the_picture_budget_was_counted.py`, and that is where
# `call_cap_per_task` is argued.
EXPECTED_SUPPORTED_CALL_TOTAL = 574
EXPECTED_SUPPORTED_CALL_MAX = 68
#: Read, not restated, for the reason the note above gives about the extension
#: set: a second copy of a number is how the two drift apart quietly.
CONFIGURED_TASK_CAP = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "grading_configs" / "default_v2.yaml")
    .read_text(encoding="utf-8")
)["judge"]["perception"]["visual"]["call_cap_per_task"]

#: The 185-task gold corpus, by the fingerprint its payloads carry rather than
#: by a filename, which encodes a config hash the cap moves.
GOLD_CORPUS_FINGERPRINT = (
    "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
)

#: The three heaviest renderers on that run: ``task_id[:8] -> (measured,
#: projected)``. Pinned because the gap between the two columns is the whole
#: reason this file's totals do not set the task cap, and a claim that large
#: should not live only in a comment.
GOLD_HEAVIEST_MEASURED_AND_PROJECTED = {
    "43dc9778": (68, 2),
    "b9665ca1": (59, 2),
    "9a8c8e28": (39, 39),
}


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


def test_checked_in_220_inventory_call_volume_holds_steady():
    """A format, a router change or a selector change moves these figures.

    The assertion against the cap at the foot is a floor, not the argument
    for the cap: criterion-named demand alone must not exceed the budget. The
    argument lives in `test_the_picture_budget_was_counted.py`, which counts
    what a run spent instead of what its wording asked for.
    """
    payload = json.loads(INVENTORY_SOURCE.read_text(encoding="utf-8"))
    task_calls = [
        sum(_item_supported_calls(item) for item in task.get("items", []))
        for task in payload.get("tasks", [])
    ]

    assert len(task_calls) == 220
    assert sum(task_calls) == EXPECTED_SUPPORTED_CALL_TOTAL
    assert max(task_calls) == EXPECTED_SUPPORTED_CALL_MAX
    assert EXPECTED_SUPPORTED_CALL_MAX <= CONFIGURED_TASK_CAP


def _gold_run() -> dict:
    grades = Path(__file__).resolve().parents[2] / "data" / "grades"
    found = [
        payload
        for path in sorted(grades.rglob("*.json"))
        if not {"_shards", "_repeats", "_superseded"} & set(path.parts)
        for payload in [_maybe_payload(path)]
        if payload is not None
        and payload.get("expected_ordered_task_ids_sha256")
        == GOLD_CORPUS_FINGERPRINT
        and payload.get("run_status") == "final"
    ]
    assert len(found) == 1, f"{len(found)} committed payloads claim to be it"
    return found[0]


def _maybe_payload(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) and "tasks" in payload else None


def test_the_projection_is_exact_or_blind():
    """How far this file's count is from what a run really spent, measured.

    Not a defect in the projection — it answers what a criterion asks for by
    its wording, and it answers it exactly when that is where the demand comes
    from. ``9a8c8e28`` projects 39 against 39 measured for precisely that
    reason.

    The other two are the case a task budget exists for, and the count is
    blind to it: their demand is the no-text-layer escalation, which needs a
    measured signal from the file itself and so cannot appear here at all. 68
    and 59 renders both project as 2. That is the gap this file must not be
    read across, and pinning it is what stops it being read across.
    """
    gold = _gold_run()
    by_prefix = {task["task_id"][:8]: task for task in gold["tasks"]}
    heaviest = sorted(
        gold["tasks"],
        key=lambda task: int(task.get("render_call_count") or 0),
        reverse=True,
    )[:3]

    assert [task["task_id"][:8] for task in heaviest] == list(
        GOLD_HEAVIEST_MEASURED_AND_PROJECTED
    )
    for prefix, (measured, projected) in (
        GOLD_HEAVIEST_MEASURED_AND_PROJECTED.items()
    ):
        task = by_prefix[prefix]
        assert int(task["render_call_count"]) == measured, prefix
        assert (
            sum(_item_supported_calls(item) for item in task.get("items", []))
            == projected
        ), prefix