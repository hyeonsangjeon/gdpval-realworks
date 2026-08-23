from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from core.grader import Grader
from core.deliverable_selector import (
    CriterionTargetPlan,
    DeliverableSelection,
    SelectionTarget,
)
from core.grader_preflight import plan_task_runtime, summarize_cohort
from core.rubric_loader import RubricItem, TaskRubric


def _task(items: list[RubricItem]) -> TaskRubric:
    return TaskRubric(
        task_id="task-1",
        sector="test",
        occupation="test",
        prompt="Create Sample.xlsx from Reference.pdf.",
        rubric_items=items,
        rubric_pretty="",
        reference_files=["reference_files/Reference.pdf"],
        gold_deliverable_files=[],
    )


def test_plan_runs_real_prechecks_before_counting_visual_calls(tmp_path: Path):
    workbook = tmp_path / "Sample.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "Summary"
    wb.save(workbook)
    items = [
        RubricItem("filename", "The deliverable basename is 'Sample'.", 1, None),
        RubricItem(
            "worksheet",
            "The workbook contains a worksheet named exactly 'Summary'.",
            1,
            None,
        ),
        RubricItem(
            "reference",
            "Amounts match the source invoice in Reference.pdf.",
            2,
            None,
        ),
        RubricItem(
            "chart-reference",
            "Accounts are consistent with COA.xlsx.",
            2,
            None,
        ),
        RubricItem("visual", "The chart layout is readable.", 2, None),
        RubricItem(
            "sound-technician",
            "Sound Technician fees are attributed correctly.",
            2,
            None,
        ),
    ]

    plan = plan_task_runtime({}, _task(items), tmp_path)

    assert plan["precheck_candidates"] == 0
    assert plan["precheck_resolved"] == 0
    assert plan["precheck_fallbacks"] == 0
    assert plan["judge_routes"] == {"text": 5, "visual": 1}
    assert plan["planned_main_judgments"] == 6
    assert plan["planned_render_calls"] == 1
    assert plan["planned_perception_calls"] == 1
    assert plan["errors"] == []


def test_plan_sends_generic_worksheet_content_to_judge(tmp_path: Path):
    workbook = tmp_path / "Sample.xlsx"
    workbook.write_bytes(b"content is not inspected without an exact sheet name")
    task = _task([
        RubricItem(
            "worksheet-content",
            "The first worksheet contains selected sample data.",
            2,
            None,
        )
    ])

    plan = plan_task_runtime({}, task, tmp_path)

    assert plan["precheck_candidates"] == 0
    assert plan["precheck_resolved"] == 0
    assert plan["precheck_fallbacks"] == 0
    assert plan["judge_routes"] == {"text": 1}


def test_summarize_cohort_preserves_order_and_sums_counts(tmp_path: Path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    (first_dir / "one.txt").write_text("one", encoding="utf-8")
    (second_dir / "two.txt").write_text("two", encoding="utf-8")
    first = _task([RubricItem("one", "Content is correct.", 1, None)])
    second = TaskRubric(
        **{**first.__dict__, "task_id": "task-2", "rubric_items": [
            RubricItem("two", "Content is complete.", 1, None)
        ]}
    )

    summary = summarize_cohort([
        plan_task_runtime({}, first, first_dir),
        plan_task_runtime({}, second, second_dir),
    ])

    assert summary["ordered_task_ids"] == ["task-1", "task-2"]
    assert summary["rubric_items"] == 2
    assert summary["judge_routes"] == {"text": 2}
    assert summary["unsupported_visual_paths"] == []
    assert summary["errors"] == []


def test_plan_never_constructs_azure_grader(monkeypatch, tmp_path: Path):
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    monkeypatch.setattr(
        Grader,
        "__init__",
        lambda *args, **kwargs: pytest.fail("planner initialized Grader client"),
    )

    plan = plan_task_runtime(
        {}, _task([RubricItem("one", "Content is correct.", 1, None)]), tmp_path
    )

    assert plan["errors"] == []


def test_plan_fails_closed_on_selection_error(tmp_path: Path):
    plan = plan_task_runtime(
        {}, _task([RubricItem("one", "Content is correct.", 1, None)]), tmp_path
    )

    assert plan["selection"]["selection_status"] == "no_generated_candidate"
    assert plan["errors"]


def test_plan_enforces_visual_call_cap(tmp_path: Path):
    (tmp_path / "report.pdf").write_bytes(b"pdf")
    config = {
        "judge": {"perception": {"visual": {"call_cap_per_task": 0}}}
    }
    plan = plan_task_runtime(
        config,
        _task([RubricItem("visual", "The chart layout is readable.", 1, None)]),
        tmp_path,
    )

    assert plan["planned_main_judgments"] == 0
    assert plan["planned_render_calls"] == 0
    assert plan["planned_perception_calls"] == 0
    assert plan["items"][0]["outcome"] == "preflight_error"
    assert plan["items"][0]["preflight_error"] == (
        "task visual budget exceeded: planned=1, cap=0"
    )
    assert plan["errors"] == [
        "task visual budget exceeded: planned=1, cap=0"
    ]


def test_plan_enforces_runtime_visual_file_cap(monkeypatch, tmp_path: Path):
    paths = [f"report-{index}.pdf" for index in range(11)]
    for path in paths:
        (tmp_path / path).write_bytes(b"pdf")
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="single_primary",
        primary_targets=[SelectionTarget("bundle", paths, "pdf")],
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="primary_bundle",
            target_ids=["bundle"],
            selected_paths=paths,
        ),
    )

    plan = plan_task_runtime(
        {},
        _task([RubricItem("visual", "The chart layout is readable.", 1, None)]),
        tmp_path,
    )

    assert plan["planned_render_calls"] == 0
    assert plan["planned_perception_calls"] == 0
    assert plan["errors"] == [
        "visual: required_visual_file_cap_exceeded:planned=11,cap=10"
    ]


def test_plan_enforces_the_configured_visual_file_cap(monkeypatch, tmp_path: Path):
    """The preflight has to plan under the run's cap, not the default one.

    A cohort graded with a lowered ``file_cap_per_item`` would otherwise be
    told its bundles fit when the grader is about to fail them closed, which
    is the one thing a preflight exists to prevent.
    """
    paths = [f"report-{index}.pdf" for index in range(4)]
    for path in paths:
        (tmp_path / path).write_bytes(b"pdf")
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="single_primary",
        primary_targets=[SelectionTarget("bundle", paths, "pdf")],
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="primary_bundle",
            target_ids=["bundle"],
            selected_paths=paths,
        ),
    )

    plan = plan_task_runtime(
        {"judge": {"perception": {"visual": {"file_cap_per_item": 3}}}},
        _task([RubricItem("visual", "The chart layout is readable.", 1, None)]),
        tmp_path,
    )

    assert plan["errors"] == [
        "visual: required_visual_file_cap_exceeded:planned=4,cap=3"
    ]


def test_plan_plans_a_visual_bundle_up_to_the_default_cap(
    monkeypatch, tmp_path: Path
):
    """Ten files is the default ceiling, and the tenth still renders.

    The cap used to be 3, which silently dropped whole bundles of five and
    six reports at grading time. Pinning the boundary here keeps a future
    tightening of the default from passing quietly.
    """
    paths = [f"report-{index}.pdf" for index in range(10)]
    for path in paths:
        (tmp_path / path).write_bytes(b"pdf")
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="single_primary",
        primary_targets=[SelectionTarget("bundle", paths, "pdf")],
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="primary_bundle",
            target_ids=["bundle"],
            selected_paths=paths,
        ),
    )

    plan = plan_task_runtime(
        {},
        _task([RubricItem("visual", "The chart layout is readable.", 1, None)]),
        tmp_path,
    )

    assert plan["errors"] == []
    assert plan["planned_main_judgments"] == 1
    assert plan["planned_render_calls"] == 10
    assert plan["items"][0]["planned_visual_paths"] == sorted(paths)


def test_plan_filters_unsupported_paths_from_visual_bundle(
    monkeypatch, tmp_path: Path
):
    # Brief.docx is here to prove the opposite of what it used to prove: a
    # document is now a render target, so only Notes.csv is filtered out.
    paths = ["Brief.docx", "Chart.pdf", "Notes.csv"]
    for path in paths:
        (tmp_path / path).write_bytes(path.encode("utf-8"))
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="main_bundle",
        primary_targets=[SelectionTarget("bundle", paths, "mixed")],
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="primary_bundle",
            target_ids=["bundle"],
            selected_paths=paths,
        ),
    )

    plan = plan_task_runtime(
        {},
        _task([RubricItem("visual", "The org chart layout is readable.", 1, None)]),
        tmp_path,
    )

    assert plan["judge_routes"] == {"visual": 1}
    assert plan["planned_main_judgments"] == 1
    assert plan["planned_render_calls"] == 2
    assert plan["planned_perception_calls"] == 2
    assert plan["items"][0]["planned_visual_paths"] == [
        "Brief.docx",
        "Chart.pdf",
    ]
    assert plan["unsupported_visual_paths"] == ["Notes.csv"]
    assert plan["errors"] == []


def test_plan_counts_audio_routes_and_fails_closed_on_model_selected_calls(
    monkeypatch, tmp_path: Path
):
    path = "clip.wav"
    (tmp_path / path).write_bytes(b"wav")
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="single_primary",
        primary_targets=[SelectionTarget("clip", [path], "audio")],
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="file_target",
            target_ids=["clip"],
            selected_paths=[path],
        ),
    )
    config = {
        "judge": {
            "perception": {
                "audio": {"model": "gpt-audio-1.5", "call_cap_per_task": 0}
            }
        }
    }

    plan = plan_task_runtime(
        config,
        _task([RubricItem("audio", "The audio narration is clear.", 1, None)]),
        tmp_path,
    )

    assert plan["judge_routes"] == {"audio": 1}
    assert plan["planned_audio_calls"] == 1
    assert plan["planned_render_calls"] == 0
    assert plan["planned_perception_calls"] == 1
    assert plan["audio_call_cap"] == 0
    assert plan["errors"] == [
        "task audio budget exceeded: planned=1, cap=0",
        "audio perception calls are model-selected and cannot be exact: routes=1",
    ]


def test_plan_split_children_matches_runtime_shape(tmp_path: Path):
    (tmp_path / "brief.docx").write_bytes(b"docx")
    (tmp_path / "appendix.pdf").write_bytes(b"pdf")
    task = TaskRubric(
        task_id="task-1",
        sector="test",
        occupation="test",
        prompt="Provide two separate deliverables: a Word document and a PDF.",
        rubric_items=[RubricItem("style", "Overall Style", 2, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    plan = plan_task_runtime({}, task, tmp_path)

    assert plan["selection"]["task_class"] == "separate_equivalent"
    assert plan["judge_routes"] == {"mixed": 1}
    assert plan["planned_main_judgments"] == 2
    assert plan["planned_render_calls"] == 1
    assert plan["items"][0]["child_routes"] == ["visual", "formatting"]


def test_plan_split_children_enforces_parent_visual_file_cap(
    monkeypatch, tmp_path: Path
):
    """The union of a split item's children is capped like a bundle is.

    The runtime hands that whole union to one batched prepass, which renders
    and perceives every path in it, so the cap has to bind there too. It is
    also what keeps an over-cap item from booking its entire union into the
    task visual budget and failing the task's other items with it.
    """
    paths = [f"report-{index}.pdf" for index in range(11)]
    targets = []
    for index, path in enumerate(paths):
        (tmp_path / path).write_bytes(b"pdf")
        targets.append(SelectionTarget(f"target-{index}", [path], "pdf"))
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="separate_equivalent",
        primary_targets=targets,
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="split_children",
            target_ids=[target.target_id for target in targets],
            selected_paths=paths,
            aggregation_rule="blocking_min_else_mean",
        ),
    )

    plan = plan_task_runtime(
        {},
        _task([RubricItem("style", "Overall Style", 1, None)]),
        tmp_path,
    )

    assert plan["judge_routes"] == {"visual": 1}
    assert plan["planned_main_judgments"] == 0
    assert plan["planned_render_calls"] == 0
    assert plan["planned_perception_calls"] == 0
    assert plan["items"][0]["outcome"] == "preflight_error"
    assert plan["errors"] == [
        "style: required_visual_file_cap_exceeded:planned=11,cap=10"
    ]


def test_plan_split_children_spans_more_children_than_the_old_cap(
    monkeypatch, tmp_path: Path
):
    """Four children under one item, which the old cap of three failed closed.

    This is the shape that cost R1 real coverage: nothing here is over budget
    and nothing is unrenderable, the item simply spanned more deliverables
    than the constant allowed, so it scored nothing rather than scoring on a
    partial view.
    """
    paths = [f"report-{index}.pdf" for index in range(4)]
    targets = []
    for index, path in enumerate(paths):
        (tmp_path / path).write_bytes(b"pdf")
        targets.append(SelectionTarget(f"target-{index}", [path], "pdf"))
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="separate_equivalent",
        primary_targets=targets,
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="split_children",
            target_ids=[target.target_id for target in targets],
            selected_paths=paths,
            aggregation_rule="blocking_min_else_mean",
        ),
    )

    plan = plan_task_runtime(
        {},
        _task([RubricItem("style", "Overall Style", 1, None)]),
        tmp_path,
    )

    assert plan["errors"] == []
    assert plan["items"][0]["outcome"] == "judge"
    assert plan["planned_main_judgments"] == 4
    assert plan["planned_render_calls"] == 4
    assert plan["planned_perception_calls"] == 4
    assert plan["items"][0]["planned_visual_paths"] == sorted(paths)


def test_plan_split_children_still_enforces_the_cap_on_one_child(
    monkeypatch, tmp_path: Path
):
    """A single over-cap child fails before the union is ever assembled.

    One failing child fails the whole item, so the error a reader sees names
    the child rather than the union. Keeping both paths covered means a
    future change to either one cannot quietly take the other with it.
    """
    paths = [f"report-{index}.pdf" for index in range(11)]
    for path in paths:
        (tmp_path / path).write_bytes(b"pdf")
    targets = [
        SelectionTarget("target-wide", paths, "pdf"),
        SelectionTarget("target-narrow", ["summary.pdf"], "pdf"),
    ]
    (tmp_path / "summary.pdf").write_bytes(b"pdf")
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="separate_equivalent",
        primary_targets=targets,
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="split_children",
            target_ids=[target.target_id for target in targets],
            selected_paths=paths + ["summary.pdf"],
            aggregation_rule="blocking_min_else_mean",
        ),
    )

    plan = plan_task_runtime(
        {},
        _task([RubricItem("style", "Overall Style", 1, None)]),
        tmp_path,
    )

    assert plan["judge_routes"] == {"visual": 1}
    assert plan["planned_main_judgments"] == 0
    assert plan["planned_render_calls"] == 0
    assert plan["planned_perception_calls"] == 0
    assert plan["items"][0]["outcome"] == "preflight_error"
    assert plan["errors"] == [
        "style: target-wide: required_visual_file_cap_exceeded:planned=11,cap=10"
    ]


def test_plan_split_children_fails_when_visual_child_has_no_render_target(
    monkeypatch, tmp_path: Path
):
    """One unrenderable visual child still fails the whole split item.

    The child used to be spelled ``Notes.txt``. Plain text under a generic
    style criterion now routes to text rather than dying on a missing render
    target, so the unrenderable case needs a target that still routes visual
    and still has nothing to render: an extensionless file, which carries no
    evidence of its kind either way and so is never demoted (same reasoning as
    ``test_audio_keyword_with_extensionless_target_stays_audio``). The
    property under test -- one child's missing render target blocks every
    sibling -- is unchanged.
    """
    paths = ["Notes", "Chart.pdf"]
    for path in paths:
        (tmp_path / path).write_bytes(path.encode("utf-8"))
    targets = [
        SelectionTarget("notes", ["Notes"], ""),
        SelectionTarget("chart", ["Chart.pdf"], "pdf"),
    ]
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="separate_equivalent",
        primary_targets=targets,
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="split_children",
            target_ids=["notes", "chart"],
            selected_paths=paths,
            aggregation_rule="blocking_min_else_mean",
        ),
    )

    plan = plan_task_runtime(
        {"judge": {"perception": {"visual": {"call_cap_per_task": 0}}}},
        _task([RubricItem("style", "Overall Style", 1, None)]),
        tmp_path,
    )

    assert plan["judge_routes"] == {"visual": 1}
    assert plan["planned_main_judgments"] == 0
    assert plan["planned_render_calls"] == 0
    assert plan["planned_perception_calls"] == 0
    assert plan["unsupported_visual_paths"] == ["Notes"]
    assert plan["items"][0]["outcome"] == "preflight_error"
    assert plan["items"][0]["preflight_error"] == (
        "notes: required_visual_render_target_unavailable"
    )
    assert plan["items"][0]["child_errors"] == [{
        "target_id": "notes",
        "error": "required_visual_render_target_unavailable",
    }]
    assert plan["errors"] == [
        "style: notes: required_visual_render_target_unavailable"
    ]


def test_plan_split_children_text_child_no_longer_blocks_its_siblings(
    monkeypatch, tmp_path: Path
):
    """The fix for the case above, at the level it actually cost us.

    Task bf68f2ad on the sol-220 rerun is exactly this shape: an ``.xlsx``
    and a ``.txt`` under one "Overall formatting and style" item, scope
    ``split_children``, aggregation ``blocking_min_else_mean``. The ``.txt``
    child had no render target, and because a split item fails whole on its
    first child error the ``.xlsx`` sibling was dragged down with it -- the
    published item carries ``visual_provenance: []`` and scored nothing.

    The text child now routes to text, contributes no visual preflight error,
    and the spreadsheet is rendered and judged on its own merits.
    """
    paths = ["MIG_Welding_Catch_Up_Summary.txt", "MIG_Welding_Catch_Up_Plan.xlsx"]
    for path in paths:
        (tmp_path / path).write_bytes(path.encode("utf-8"))
    targets = [
        SelectionTarget("summary", [paths[0]], "txt"),
        SelectionTarget("plan", [paths[1]], "xlsx"),
    ]
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="task-1",
        task_class="separate_equivalent",
        primary_targets=targets,
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader_preflight.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="split_children",
            target_ids=["summary", "plan"],
            selected_paths=paths,
            aggregation_rule="blocking_min_else_mean",
        ),
    )

    plan = plan_task_runtime(
        {"judge": {"perception": {"visual": {"call_cap_per_task": 4}}}},
        _task([RubricItem(
            "style", "Overall formatting and style of the deliverable", 5, None
        )]),
        tmp_path,
    )

    assert plan["errors"] == []
    assert plan["items"][0]["outcome"] != "preflight_error"
    assert plan["unsupported_visual_paths"] == []
    # The spreadsheet still renders; only the text child was diverted.
    assert plan["planned_render_calls"] == 1


@pytest.mark.parametrize(
    ("second_name", "visual_cap", "expected_error"),
    [
        # A ``Notes.txt`` case used to sit here, erroring with
        # ``required_visual_render_target_unavailable``. It is gone rather
        # than re-spelled because the state it described is now unreachable:
        # under a generic style criterion a file routes visual only if its
        # suffix is renderable, so "routes visual, cannot render" no longer
        # exists for this kind of criterion. Removing the fix would make the
        # case reappear -- which is what
        # ``test_plan_split_children_text_child_no_longer_blocks_its_siblings``
        # is for. The surviving case keeps the mixed routing (docx →
        # formatting, pdf → visual) and the blocking property intact.
        (
            "Chart.pdf",
            0,
            "task visual budget exceeded: planned=1, cap=0",
        ),
    ],
)
def test_plan_mixed_split_preflight_error_blocks_all_main_calls(
    tmp_path: Path, second_name: str, visual_cap: int, expected_error: str
):
    (tmp_path / "Brief.docx").write_bytes(b"docx")
    (tmp_path / second_name).write_bytes(b"secondary")
    second_kind = "PDF" if second_name.endswith(".pdf") else "text file"
    task = TaskRubric(
        task_id="task-1",
        sector="test",
        occupation="test",
        prompt=(
            "Create two separate deliverables: a Word document and a "
            f"{second_kind}."
        ),
        rubric_items=[RubricItem("style", "Overall Style", 1, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )
    config = {
        "judge": {
            "perception": {"visual": {"call_cap_per_task": visual_cap}}
        }
    }

    plan = plan_task_runtime(config, task, tmp_path)

    assert plan["judge_routes"] == {"mixed": 1}
    assert plan["planned_main_judgments"] == 0
    assert plan["planned_render_calls"] == 0
    assert plan["planned_perception_calls"] == 0
    assert plan["items"][0]["outcome"] == "preflight_error"
    assert plan["errors"] == [expected_error]