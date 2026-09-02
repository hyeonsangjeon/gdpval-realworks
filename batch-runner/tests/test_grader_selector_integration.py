"""Selector integration tests for the v2 tool-calling grader path."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.deliverable_selector import AUDIO_EXTENSIONS, select_deliverables
from core.media_types import GRADER_AUDIO_EXTENSIONS


def _final(text: str) -> dict:
    return {"type": "message", "content": [{"type": "output_text", "text": text}]}


def _function_call(call_id: str, **arguments) -> dict:
    return {
        "type": "function_call",
        "name": "read_deliverable",
        "arguments": json.dumps(arguments),
        "call_id": call_id,
    }


def _response(*, output, in_tok=80, out_tok=20):
    return SimpleNamespace(
        output=output,
        output_text="",
        usage=SimpleNamespace(
            input_tokens=in_tok,
            output_tokens=out_tok,
            input_tokens_details=SimpleNamespace(cached_tokens=5),
        ),
        incomplete_details=None,
        status=None,
    )


class ScriptedResponses:
    def __init__(self, script=None):
        self.script = list(script or [])
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("ScriptedResponses ran out of responses")
        return self.script.pop(0)


class CountingVision:
    def __init__(self, call_cap=72):
        self.call_cap = call_cap
        self.calls = []

    @property
    def remaining_calls(self):
        return self.call_cap - len(self.calls)

    def reset(self):
        self.calls.clear()

    def judge(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            judge_error=None,
            to_dict=lambda: {
                "verdict": "pass",
                "partial_score": 1.0,
                "evidence": "visible surface is polished",
                "confidence": 0.9,
                "reasoning": "render inspected",
                "judge_error": None,
                "api_call_count": 1,
                "input_tokens": 11,
                "output_tokens": 4,
                "cached_tokens": 2,
                "latency_ms": 8.0,
                "usage_complete": True,
            },
        )


def _payload(verdict: str, partial: float, evidence: str) -> str:
    return json.dumps(
        {
            "verdict": verdict,
            "partial_score": partial,
            "evidence": evidence,
            "confidence": 0.9,
            "reasoning": "ok",
            "tool_calls_made": 0,
        }
    )


@pytest.mark.parametrize("suffix", sorted(GRADER_AUDIO_EXTENSIONS))
def test_selector_preserves_supported_audio_primary(suffix: str):
    selection = select_deliverables(
        task_id="audio-task",
        deliverable_files=[f"final_mix{suffix}", "production_notes.txt"],
        instruction="Submit a single audio file with supporting notes.",
    )

    assert AUDIO_EXTENSIONS == set(GRADER_AUDIO_EXTENSIONS)
    assert selection.selection_status == "ok"
    assert selection.task_class == "main_plus_support"
    assert selection.primary_targets[0].paths == [f"final_mix{suffix}"]
    assert selection.support_artifacts == ["production_notes.txt"]


def test_selector_rejects_known_unsupported_audio_primary():
    selection = select_deliverables(
        task_id="audio-task",
        deliverable_files=["final_mix.wma", "production_notes.txt"],
        instruction="Submit a single audio file with supporting notes.",
    )

    assert selection.selection_status == "wrong_format_primary"


def _grader(monkeypatch, fake_client):
    from core.grader import Grader
    import core.grader as grader_mod

    prompt_v1 = (
        Path(grader_mod.__file__).resolve().parent.parent
        / "prompts"
        / "grader_judge.md"
    )
    cfg = {
        "judge": {
            "provider": "azure_openai",
            "api_version": "2025-04-01-preview",
            "model": "gpt-5.4",
            "reasoning": {"effort": "medium"},
            "generation": {"max_output_tokens": 2400},
            "tools": {
                "read_deliverable": {
                    "ops": [
                        "inspect_structure", "read_content", "inspect_formatting"
                    ],
                    "per_item_call_cap": 8,
                    "max_iterations": 6,
                },
            },
        },
        "prompt": {"template": str(prompt_v1)},
        "grader": {"evidence_max_chars": 200},
        "tpm_guard": {},
    }
    return Grader(cfg, rubric_loader=None, client=fake_client)


def test_selector_filters_reference_and_records_audit(monkeypatch, tmp_path):
    from core.rubric_loader import RubricItem, TaskRubric

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "professional layout"))])
    ])
    fake_client = SimpleNamespace(responses=responses)
    grader = _grader(monkeypatch, fake_client)

    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Input.xlsx").write_text("reference", encoding="utf-8")
    (deliverable_dir / "Support.xlsx").write_text("support", encoding="utf-8")
    (deliverable_dir / "Output.pdf").write_text("candidate", encoding="utf-8")

    items = [
        RubricItem("manifest", "A single PDF file is delivered.", 1, None),
        RubricItem("style", "Overall formatting and style of the deliverable", 5, None),
    ]
    task = TaskRubric(
        task_id="t-single",
        sector="Information",
        occupation="Analyst",
        prompt="Create a single PDF report.",
        rubric_items=items,
        rubric_pretty="",
        reference_files=["reference_files/hash/Input.xlsx"],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))

    assert grade.selection_status == "ok"
    assert grade.reference_files_excluded == ["Input.xlsx"]
    assert grade.selected_deliverables["task_class"] == "main_plus_support"
    assert grade.items[0].target_scope == "manifest"
    assert grade.items[0].selected_paths == ["Output.pdf"]
    assert grade.items[1].target_scope == "file_target"
    assert grade.items[1].selected_paths == ["Output.pdf"]
    assert grade.items[1].support_paths_visible == []

    prompt = responses.calls[0]["input"][0]["content"]
    assert "Selected candidate deliverable files" in prompt
    assert "- path: `Output.pdf`" in prompt
    assert "Reference input files (NOT candidate deliverables)" in prompt
    assert "- path: `Input.xlsx`" in prompt


@pytest.mark.parametrize(
    "style_criterion",
    [
        "Overall Style",
        "Overall formatting and style of the deliverable",
        "The overall presentation and professional polish",
    ],
)
def test_wrong_format_fails_manifest_but_excludes_overall_style(
    monkeypatch, tmp_path, style_criterion
):
    from core.rubric_loader import RubricItem, TaskRubric

    fake_client = SimpleNamespace(responses=ScriptedResponses([]))
    grader = _grader(monkeypatch, fake_client)

    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Plan.docx").write_text("wrong format", encoding="utf-8")

    items = [
        RubricItem("manifest", "Submission is provided as a single PDF document.", 1, None),
        RubricItem("style", style_criterion, 5, None),
    ]
    task = TaskRubric(
        task_id="t-wrong-format",
        sector="Information",
        occupation="Analyst",
        prompt="Submit a single PDF document.",
        rubric_items=items,
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))

    assert grade.selection_status == "wrong_format_primary"
    assert grade.error is None
    assert grade.items[0].verdict == "fail"
    assert grade.items[0].score_excluded is False
    assert grade.items[1].verdict == "judge_error"
    assert grade.items[1].score_excluded is True
    assert grade.total_max == 1
    assert grade.judge_call_count == 0


def test_split_children_routes_each_primary_and_aggregates(monkeypatch, tmp_path):
    from core.rubric_loader import RubricItem, TaskRubric

    evidence_13 = "session 13 polished " + ("a" * 130)
    evidence_14 = "session 14 readable " + ("b" * 130)
    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "two files provided"))]),
        _response(output=[_final(_payload("pass", 1.0, evidence_13))]),
        _response(output=[_final(_payload("partial", 0.5, evidence_14))]),
    ])
    fake_client = SimpleNamespace(responses=responses)
    grader = _grader(monkeypatch, fake_client)

    class FakeVision:
        def __init__(self):
            self.calls = []
            self.remaining_calls = 5

        def reset(self):
            self.calls.clear()

        def judge(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                judge_error=None,
                to_dict=lambda: {
                    "verdict": "pass",
                    "partial_score": 1.0,
                    "evidence": "visible slide",
                    "confidence": 0.9,
                    "reasoning": "render inspected",
                    "judge_error": None,
                    "api_call_count": 1,
                    "input_tokens": 11,
                    "output_tokens": 4,
                    "cached_tokens": 2,
                    "latency_ms": 8.0,
                    "usage_complete": True,
                },
            )

    fake_vision = FakeVision()
    grader._tool_judge.vision_perception = fake_vision
    import core.tool_calling_judge as tool_judge_mod
    monkeypatch.setattr(
        tool_judge_mod,
        "read_deliverable",
        lambda *args, **kwargs: {
            "ok": True,
            "data": {
                "base64": "aW1hZ2U=",
                "scope": {"slide": 1},
                "source_kind": "pptx",
                "source_slide_count": 3,
                "converted_page_count": 3,
                "renderer": {
                    "converter": "libreoffice",
                    "libreoffice_binary": "soffice",
                    "libreoffice_version": "LibreOffice 24.2.7.2",
                    "pymupdf_version": "1.26.3",
                },
            },
        },
    )

    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Session_13_Nurturing_Parenting_Recovery.pptx").write_text(
        "deck 13", encoding="utf-8"
    )
    (deliverable_dir / "Session_14_Nurturing_Parenting_Recovery.pptx").write_text(
        "deck 14", encoding="utf-8"
    )

    items = [
        RubricItem(
            "manifest",
            "Exactly 2 files are provided.",
            1,
            None,
        ),
        RubricItem("style", "Overall formatting and style of the deliverable", 4, None),
    ]
    task = TaskRubric(
        task_id="t-split",
        sector="Information",
        occupation="Analyst",
        prompt="Create two distinct .pptx files for Session 13 and Session 14.",
        rubric_items=items,
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    style = grade.items[1]

    assert grade.selection_status == "ok"
    assert grade.selected_deliverables["task_class"] == "separate_equivalent"
    assert style.target_scope == "split_children"
    assert style.aggregation_rule == "blocking_min_else_mean"
    assert len(style.child_grades) == 2
    assert style.evidence == "split_children: see child_grades for 2 per-target evidence entries"
    assert len(style.evidence) <= 200
    assert style.child_grades[0]["evidence"] == evidence_13
    assert style.child_grades[1]["evidence"] == evidence_14
    assert style.verdict == "partial"
    assert style.awarded_score == 3.0
    assert style.routing_modality == "visual"
    assert style.perception_called is True
    assert style.tools_used == [
        "harness_render_to_image", "harness_vision_perception",
        "harness_render_to_image", "harness_vision_perception",
    ]
    assert all(child["perception_called"] for child in style.child_grades)
    assert all(not child["score_excluded"] for child in style.child_grades)
    assert len(fake_vision.calls) == 2
    assert len(responses.calls) == 3
    assert style.judge_call_count == 2
    assert style.perception_call_count == 2
    assert style.render_call_count == 2
    assert grade.judge_call_count == 3
    assert grade.judge_input_tokens == 240
    assert grade.judge_output_tokens == 60
    assert grade.judge_cached_tokens == 15
    assert grade.perception_call_count == 2
    assert grade.perception_input_tokens == 22
    assert grade.perception_output_tokens == 8
    assert grade.perception_cached_tokens == 4
    assert grade.perception_total_latency_ms == 16.0
    assert grade.render_call_count == 2
    assert grade.usage_complete is True
    assert len(style.visual_provenance) == 2
    assert all(len(child["visual_provenance"]) == 1 for child in style.child_grades)
    serialized = asdict(grade)
    serialized_provenance = serialized["items"][1]["visual_provenance"]
    assert serialized_provenance[0]["renderer_metadata"]["renderer"][
        "libreoffice_version"
    ] == "LibreOffice 24.2.7.2"
    serialized_text = json.dumps(serialized)
    assert "base64" not in serialized_text
    assert str(deliverable_dir) not in serialized_text


def test_split_visual_renderer_failure_excludes_parent_before_child_main(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "two files provided"))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))

    class FakeVision:
        remaining_calls = 5

        def __init__(self):
            self.calls = []

        def reset(self):
            self.calls.clear()

        def judge(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                judge_error=None,
                to_dict=lambda: {
                    "verdict": "pass", "partial_score": 1.0,
                    "evidence": "visible slide", "confidence": 0.9,
                    "reasoning": "render inspected", "judge_error": None,
                    "api_call_count": 1, "input_tokens": 11,
                    "output_tokens": 4, "cached_tokens": 2,
                    "latency_ms": 8.0, "usage_complete": True,
                },
            )

    fake_vision = FakeVision()
    grader._tool_judge.vision_perception = fake_vision
    import core.tool_calling_judge as tool_judge_mod

    def fake_render(op, path, **kwargs):
        if "14" in path:
            return {
                "ok": False,
                "error_type": "unsupported_scope",
                "error": "slide surface unavailable",
            }
        return {
            "ok": True,
            "data": {
                "base64": "aW1hZ2U=", "scope": {"slide": 1},
                "source_kind": "pptx", "source_slide_count": 2,
                "converted_page_count": 2,
                "renderer": {
                    "converter": "libreoffice",
                    "libreoffice_binary": "soffice",
                    "libreoffice_version": "LibreOffice 24.2.7.2",
                    "pymupdf_version": "1.26.3",
                },
            },
        }

    monkeypatch.setattr(tool_judge_mod, "read_deliverable", fake_render)
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    for session in (13, 14):
        (deliverable_dir / f"Session_{session}_Nurturing_Parenting_Recovery.pptx").write_text(
            f"deck {session}", encoding="utf-8"
        )
    task = TaskRubric(
        task_id="t-split-fail", sector="Information", occupation="Analyst",
        prompt="Create two distinct .pptx files for Session 13 and Session 14.",
        rubric_items=[
            RubricItem("manifest", "Exactly 2 files are provided.", 1, None),
            RubricItem("style", "Overall Style", 4, None),
        ],
        rubric_pretty="", reference_files=[], gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    style = grade.items[1]

    assert style.verdict == "judge_error"
    assert style.score_excluded is True
    assert style.perception_called is True
    assert all(child["score_excluded"] for child in style.child_grades)
    assert style.render_call_count == 2
    assert style.perception_call_count == 1
    assert len(fake_vision.calls) == 1
    assert len(style.visual_provenance) == 1
    assert len(style.child_grades[0]["visual_provenance"]) == 1
    assert style.child_grades[1]["visual_provenance"] == []
    assert style.visual_provenance[0]["renderer_metadata"]["renderer"][
        "libreoffice_version"
    ] == "LibreOffice 24.2.7.2"
    assert grade.judge_call_count == 1
    assert grade.total_max == 1
    assert len(responses.calls) == 1


def test_split_visual_cap_is_preflighted_before_any_render_or_child_main(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "two files provided"))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))

    class CappedVision:
        remaining_calls = 1

        def __init__(self):
            self.calls = []

        def reset(self):
            self.calls.clear()

        def judge(self, **kwargs):
            self.calls.append(kwargs)
            raise AssertionError("vision must not run after cap preflight failure")

    vision = CappedVision()
    grader._tool_judge.vision_perception = vision
    import core.tool_calling_judge as tool_judge_mod

    monkeypatch.setattr(
        tool_judge_mod,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("render must not start"),
    )
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    for session in (13, 14):
        (deliverable_dir / f"Session_{session}_Nurturing_Parenting_Recovery.pptx").write_text(
            f"deck {session}", encoding="utf-8"
        )
    task = TaskRubric(
        task_id="t-split-cap", sector="Information", occupation="Analyst",
        prompt="Create two distinct .pptx files for Session 13 and Session 14.",
        rubric_items=[
            RubricItem("manifest", "Exactly 2 files are provided.", 1, None),
            RubricItem("style", "Overall Style", 4, None),
        ],
        rubric_pretty="", reference_files=[], gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    style = grade.items[1]

    assert style.verdict == "judge_error"
    assert style.score_excluded is True
    assert style.render_call_count == 0
    assert style.perception_call_count == 0
    assert grade.judge_call_count == 1
    assert vision.calls == []
    assert len(responses.calls) == 1


def test_docx_overall_style_uses_formatting_tool_without_visual_prepass(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([
        _response(output=[_function_call(
            "inspect-1", op="inspect_formatting", path="Brief.docx"
        )]),
        _response(output=[_final(_payload(
            "pass", 1.0, "heading styles and margins are consistent"
        ))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    dispatched = []

    def fake_read(op, path, *, base_dir, scope=None):
        dispatched.append((op, path, scope))
        return {"ok": True, "data": {"kind": "docx", "style_count": 4}}

    monkeypatch.setattr(tool_judge_mod, "read_deliverable", fake_read)
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Brief.docx").write_bytes(b"docx")
    task = TaskRubric(
        task_id="t-docx-style",
        sector="Information",
        occupation="Analyst",
        prompt="Create a Word document.",
        rubric_items=[RubricItem("style", "Overall Style", 4, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    style = grade.items[0]

    assert style.verdict == "pass"
    assert style.routing_modality == "formatting"
    assert style.perception_called is False
    assert style.score_excluded is False
    assert style.render_call_count == 0
    assert dispatched == [("inspect_formatting", "Brief.docx", None)]
    assert "inspect_formatting" in responses.calls[0]["input"][0]["content"]


def test_mixed_docx_pdf_overall_style_routes_children_and_parent_provenance(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "document styles are consistent"))]),
        _response(output=[_final(_payload("pass", 1.0, "PDF page is visually polished"))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision()
    grader._tool_judge.vision_perception = vision
    rendered_paths = []

    def fake_render(op, path, **kwargs):
        rendered_paths.append(path)
        return {
            "ok": True,
            "data": {
                "kind": "image_png_base64",
                "base64": "aW1hZ2U=",
                "byte_size": 5,
                "scope": {"page": 1},
                "source_kind": "pdf",
                "source_page_count": 2,
                "renderer": {
                    "rasterizer": "pymupdf",
                    "pymupdf_version": "1.26.3",
                    "dpi": 150,
                },
            },
        }

    monkeypatch.setattr(tool_judge_mod, "read_deliverable", fake_render)
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Action_Plan.docx").write_bytes(b"docx")
    (deliverable_dir / "Checklist.pdf").write_bytes(b"pdf")
    task = TaskRubric(
        task_id="t-mixed-style",
        sector="Information",
        occupation="Analyst",
        prompt=(
            "Create exactly two separate deliverables: one Word .docx "
            "action plan and one .pdf checklist."
        ),
        rubric_items=[RubricItem("style", "Overall Style", 4, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    style = grade.items[0]
    children = {Path(child["selected_paths"][0]).suffix: child for child in style.child_grades}

    assert style.routing_modality == "mixed"
    assert style.perception_called is True
    assert style.verdict == "pass"
    assert rendered_paths == ["Checklist.pdf"]
    assert len(vision.calls) == 1
    assert children[".docx"]["routing_modality"] == "formatting"
    assert children[".docx"]["perception_called"] is False
    assert children[".docx"]["visual_provenance"] == []
    assert children[".pdf"]["routing_modality"] == "visual"
    assert children[".pdf"]["perception_called"] is True
    assert len(children[".pdf"]["visual_provenance"]) == 1
    assert len(style.visual_provenance) == 1
    assert style.render_call_count == 1
    assert style.perception_call_count == 1
    assert grade.judge_call_count == 2


def test_mixed_visual_preflight_failure_excludes_parent_before_docx_main(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision()
    grader._tool_judge.vision_perception = vision
    render_calls = []

    def failed_render(op, path, **kwargs):
        render_calls.append(path)
        return {"ok": False, "error_type": "render_error", "error": "bad pdf"}

    monkeypatch.setattr(tool_judge_mod, "read_deliverable", failed_render)
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Action_Plan.docx").write_bytes(b"docx")
    (deliverable_dir / "Checklist.pdf").write_bytes(b"pdf")
    task = TaskRubric(
        task_id="t-mixed-fail",
        sector="Information",
        occupation="Analyst",
        prompt="Create two separate files: one .docx document and one PDF document.",
        rubric_items=[RubricItem("style", "Overall Style", 4, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    style = grade.items[0]
    child_modalities = {child["routing_modality"] for child in style.child_grades}

    assert style.verdict == "judge_error"
    assert style.score_excluded is True
    assert style.routing_modality == "mixed"
    assert style.perception_called is False
    assert child_modalities == {"formatting", "visual"}
    assert all(child["score_excluded"] for child in style.child_grades)
    assert render_calls == ["Checklist.pdf"]
    assert style.render_call_count == 1
    assert vision.calls == []
    assert responses.calls == []
    assert grade.judge_call_count == 0


def test_split_preflight_failure_records_prior_perception_call(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric
    from core.tool_calling_judge import VisualPrepassResult

    grader = _grader(monkeypatch, SimpleNamespace(responses=ScriptedResponses([])))
    grader._tool_judge.preflight_visual = lambda **kwargs: VisualPrepassResult(
        judge_error="required_visual_render_failed:second.pptx:render_error",
        perception_call_count=1,
        perception_input_tokens=11,
        perception_output_tokens=4,
        perception_total_latency_ms=8.0,
        render_call_count=2,
        render_total_latency_ms=12.0,
        tools_used=[
            "harness_render_to_image",
            "harness_vision_perception",
            "harness_render_to_image",
        ],
    )
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Session_1.pptx").write_bytes(b"one")
    (deliverable_dir / "Session_2.pptx").write_bytes(b"two")
    task = TaskRubric(
        task_id="t-partial-preflight",
        sector="Information",
        occupation="Analyst",
        prompt="Create two distinct .pptx files for Session 1 and Session 2.",
        rubric_items=[RubricItem("style", "Overall Style", 4, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    style = grader.grade_task(task, str(deliverable_dir)).items[0]

    assert style.verdict == "judge_error"
    assert style.score_excluded is True
    assert style.perception_call_count == 1
    assert style.perception_called is True


def test_explicit_visual_item_fails_closed_without_render_target(
    monkeypatch, tmp_path
):
    """A visual item with nothing renderable must error, not text-judge.

    This used to be spelled with a .docx deliverable. Documents render now, so
    the unrenderable case needs a format that genuinely has no render target;
    the property under test -- fail closed, touch no model -- is unchanged.
    """
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision()
    grader._tool_judge.vision_perception = vision
    monkeypatch.setattr(
        tool_judge_mod,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("unrenderable file must fail before render"),
    )
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Summary.csv").write_bytes(b"header_a,header_b\n1,2\n")
    task = TaskRubric(
        task_id="t-csv-visual",
        sector="Information",
        occupation="Analyst",
        prompt="Create a CSV export of the summary table.",
        rubric_items=[RubricItem(
            "visual", "Document color and page layout are visually polished", 4, None
        )],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    item = grade.items[0]

    assert item.routing_modality == "visual"
    assert item.verdict == "judge_error"
    assert item.score_excluded is True
    assert item.evidence == "required_visual_render_target_unavailable"
    assert item.render_call_count == 0
    assert vision.calls == []
    assert responses.calls == []


def test_explicit_visual_docx_renders_instead_of_failing_closed(
    monkeypatch, tmp_path
):
    """The inverse of the test above, on the same criterion and deliverable.

    This exact shape -- a visual rubric item whose only deliverable is a
    document -- is what produced 73 `required_visual_render_target_unavailable`
    items across 24 tasks in the sol-220 run, none of which reached a model.
    """
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "page layout is polished"))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision()
    grader._tool_judge.vision_perception = vision
    rendered = []

    def fake_render(op, path, **kwargs):
        rendered.append((path, kwargs.get("scope")))
        return {
            "ok": True,
            "data": {
                "kind": "image_png_base64",
                "base64": "aW1hZ2U=",
                "byte_size": 5,
                "scope": {"page": 1},
                "source_kind": "docx",
                "converted_page_count": 3,
                "renderer": {
                    "converter": "libreoffice",
                    "rasterizer": "pymupdf",
                    "libreoffice_binary": "soffice",
                    "libreoffice_version": "LibreOffice 24.2.7.2",
                    "pymupdf_version": "1.26.3",
                    "dpi": 150,
                },
            },
        }

    monkeypatch.setattr(tool_judge_mod, "read_deliverable", fake_render)
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Brief.docx").write_bytes(b"docx")
    task = TaskRubric(
        task_id="t-docx-visual",
        sector="Information",
        occupation="Analyst",
        prompt="Create a Word document.",
        rubric_items=[RubricItem(
            "visual", "Document color and page layout are visually polished", 4, None
        )],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    item = grade.items[0]

    assert item.routing_modality == "visual"
    assert item.verdict == "pass"
    assert item.score_excluded is False
    assert item.evidence != "required_visual_render_target_unavailable"
    assert rendered == [("Brief.docx", {"page": 1})]
    assert item.render_call_count == 1
    assert len(vision.calls) == 1
    assert item.visual_provenance[0]["path"] == "Brief.docx"
    assert (
        item.visual_provenance[0]["renderer_metadata"]["source_kind"] == "docx"
    )


def test_split_visual_child_validation_precedes_task_budget_and_render(
    monkeypatch, tmp_path
):
    """Child validation runs before the task budget check and before render.

    The child used to be spelled ``Notes.txt`` and reached this path through
    the real selector. It cannot any more: under a generic style criterion a
    child routes visual only if its suffix is renderable, so "routes visual,
    nothing to render" now needs an extensionless child -- and
    ``select_deliverables`` drops extensionless files rather than making them
    primary targets. The state is therefore constructed here instead of
    selected, the same way ``test_grader_preflight`` constructs it for the
    planner. The ordering under test is untouched: with the vision cap at 0
    the *task budget* error is also armed, and the child error must still be
    the one that surfaces, before any render call.
    """
    from core.deliverable_selector import (
        CriterionTargetPlan,
        DeliverableSelection,
        SelectionTarget,
    )
    from core.grader import Grader
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision(call_cap=0)
    grader._tool_judge.vision_perception = vision
    monkeypatch.setattr(
        tool_judge_mod,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("child validation must precede render"),
    )
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Notes").write_bytes(b"text")
    (deliverable_dir / "Chart.pdf").write_bytes(b"pdf")
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="t-split-unsupported",
        task_class="separate_equivalent",
        primary_targets=[
            SelectionTarget("notes", ["Notes"], ""),
            SelectionTarget("chart", ["Chart.pdf"], "pdf"),
        ],
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="split_children",
            target_ids=["notes", "chart"],
            selected_paths=["Notes", "Chart.pdf"],
            aggregation_rule="blocking_min_else_mean",
        ),
    )
    task = TaskRubric(
        task_id="t-split-unsupported",
        sector="Information",
        occupation="Analyst",
        prompt="Create two separate deliverables: a text file and a PDF.",
        rubric_items=[RubricItem("style", "Overall Style", 4, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    item = grade.items[0]

    assert item.target_scope == "split_children"
    assert item.routing_modality == "visual"
    assert item.verdict == "judge_error"
    assert item.score_excluded is True
    assert item.evidence == (
        "notes: required_visual_render_target_unavailable"
    )
    assert all(
        child["evidence"].endswith(
            "required_visual_render_target_unavailable"
        )
        for child in item.child_grades
    )
    assert item.judge_call_count == 0
    assert item.render_call_count == 0
    assert item.perception_call_count == 0
    assert all(child["score_excluded"] for child in item.child_grades)
    assert vision.calls == []
    assert responses.calls == []


def test_split_text_child_no_longer_blocks_its_visual_sibling(
    monkeypatch, tmp_path
):
    """Task bf68f2ad on the sol-220 rerun, end to end.

    An ``.xlsx`` and a ``.txt`` under one "Overall formatting and style" item,
    scope ``split_children``, aggregation ``blocking_min_else_mean``. The text
    child had no visual render target; because a split item fails whole on its
    first child error, the spreadsheet was dragged down with it and the
    published item carries ``visual_provenance: []`` with nothing scored.

    The text child now routes to text and the spreadsheet renders and is
    judged. What makes this safe rather than lenient is that the judge sees
    every child in full -- the text as text, the workbook as an image -- so
    nothing is answered from a partial view.
    """
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "plain text is tidy"))]),
        _response(output=[_final(_payload("pass", 1.0, "workbook is legible"))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision()
    grader._tool_judge.vision_perception = vision
    rendered = []

    def fake_render(op, path, **kwargs):
        rendered.append((path, kwargs.get("scope")))
        return {
            "ok": True,
            "data": {
                "kind": "image_png_base64",
                "base64": "aW1hZ2U=",
                "byte_size": 5,
                "scope": {"workbook_page": 1},
                "source_kind": "xlsx",
                "converted_page_count": 1,
                "renderer": {
                    "converter": "libreoffice",
                    "rasterizer": "pymupdf",
                    "libreoffice_binary": "soffice",
                    "libreoffice_version": "LibreOffice 24.2.7.2",
                    "pymupdf_version": "1.26.3",
                    "dpi": 150,
                },
            },
        }

    monkeypatch.setattr(tool_judge_mod, "read_deliverable", fake_render)
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "MIG_Welding_Catch_Up_Plan.xlsx").write_bytes(b"xlsx")
    (deliverable_dir / "MIG_Welding_Catch_Up_Summary.txt").write_bytes(b"summary")
    task = TaskRubric(
        task_id="t-split-text-sibling",
        sector="Manufacturing",
        occupation="Welder",
        prompt=(
            "Create two separate deliverables: a spreadsheet catch-up plan "
            "and a text file summary."
        ),
        rubric_items=[RubricItem(
            "style", "Overall formatting and style of the deliverable", 5, None
        )],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    item = grade.items[0]

    assert item.target_scope == "split_children"
    assert item.verdict != "judge_error"
    assert item.score_excluded is False
    assert "required_visual_render_target_unavailable" not in (item.evidence or "")
    # The spreadsheet still reached the judge as an image.
    assert rendered == [("MIG_Welding_Catch_Up_Plan.xlsx", {"workbook_page": 1})]
    assert [entry["path"] for entry in item.visual_provenance] == [
        "MIG_Welding_Catch_Up_Plan.xlsx"
    ]
    # ...and the text child was judged on the text channel, not skipped.
    assert {child["routing_modality"] for child in item.child_grades} == {
        "text",
        "visual",
    }
    assert not any(
        child["verdict"] == "judge_error" for child in item.child_grades
    )


def test_split_children_render_every_child_past_the_old_file_cap(
    monkeypatch, tmp_path
):
    """Four one-file children under one item, end to end.

    This is the shape the old cap of three failed closed on R1: four separate
    reports, all renderable, none over any budget, and the item scored nothing
    because the constant said three. The union is one batched prepass, so the
    cap still binds on it -- it is just no longer set below the size of an
    ordinary multi-deliverable submission.
    """
    from core.rubric_loader import RubricItem, TaskRubric
    from core.deliverable_selector import (
        CriterionTargetPlan,
        DeliverableSelection,
        SelectionTarget,
    )
    from core.grader import Grader
    import core.tool_calling_judge as tool_judge_mod

    paths = [f"report-{index}.pdf" for index in range(4)]
    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, f"{path} is legible"))])
        for path in paths
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision()
    grader._tool_judge.vision_perception = vision
    rendered = []

    def fake_render(op, path, **kwargs):
        rendered.append(path)
        return {
            "ok": True,
            "data": {
                "kind": "image_png_base64",
                "base64": "aW1hZ2U=",
                "byte_size": 5,
                "scope": {"page": 1},
                "source_kind": "pdf",
                "converted_page_count": 1,
                "renderer": {
                    "converter": "libreoffice",
                    "rasterizer": "pymupdf",
                    "libreoffice_binary": "soffice",
                    "libreoffice_version": "LibreOffice 24.2.7.2",
                    "pymupdf_version": "1.26.3",
                    "dpi": 150,
                },
            },
        }

    monkeypatch.setattr(tool_judge_mod, "read_deliverable", fake_render)
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    targets = []
    for index, path in enumerate(paths):
        (deliverable_dir / path).write_bytes(b"pdf")
        targets.append(SelectionTarget(f"target-{index}", [path], "pdf"))
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="t-split-wide",
        task_class="separate_equivalent",
        primary_targets=targets,
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="split_children",
            target_ids=[target.target_id for target in targets],
            selected_paths=paths,
            aggregation_rule="blocking_min_else_mean",
        ),
    )
    task = TaskRubric(
        task_id="t-split-wide",
        sector="Information",
        occupation="Analyst",
        prompt="Create four separate PDF reports, one per region.",
        rubric_items=[RubricItem("style", "Overall Style", 4, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    item = grade.items[0]

    assert item.target_scope == "split_children"
    assert item.routing_modality == "visual"
    assert item.verdict != "judge_error"
    assert item.score_excluded is False
    assert sorted(rendered) == sorted(paths)
    assert [entry["path"] for entry in item.visual_provenance] == sorted(paths)
    assert len(item.child_grades) == 4
    assert not any(
        child["verdict"] == "judge_error" for child in item.child_grades
    )


def test_split_children_union_over_the_file_cap_fails_before_render(
    monkeypatch, tmp_path
):
    """Past the cap the item still fails closed, and before any render.

    The runtime and the preflight have to agree here or a cohort would be
    told a plan the grader will not run. The preflight half of that pair
    lives in ``tests/test_grader_preflight.py``.
    """
    from core.rubric_loader import RubricItem, TaskRubric
    from core.deliverable_selector import (
        CriterionTargetPlan,
        DeliverableSelection,
        SelectionTarget,
    )
    from core.grader import Grader
    import core.tool_calling_judge as tool_judge_mod

    paths = [f"report-{index}.pdf" for index in range(11)]
    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision()
    grader._tool_judge.vision_perception = vision
    monkeypatch.setattr(
        tool_judge_mod,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("cap must precede render"),
    )
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    targets = []
    for index, path in enumerate(paths):
        (deliverable_dir / path).write_bytes(b"pdf")
        targets.append(SelectionTarget(f"target-{index}", [path], "pdf"))
    selection = DeliverableSelection(
        selection_status="ok",
        task_id="t-split-over-cap",
        task_class="separate_equivalent",
        primary_targets=targets,
    )
    monkeypatch.setattr(Grader, "_select_deliverables", lambda *args: selection)
    monkeypatch.setattr(
        "core.grader.plan_targets_for_criterion",
        lambda *args: CriterionTargetPlan(
            target_scope="split_children",
            target_ids=[target.target_id for target in targets],
            selected_paths=paths,
            aggregation_rule="blocking_min_else_mean",
        ),
    )
    task = TaskRubric(
        task_id="t-split-over-cap",
        sector="Information",
        occupation="Analyst",
        prompt="Create eleven separate PDF reports, one per region.",
        rubric_items=[RubricItem("style", "Overall Style", 4, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    item = grade.items[0]

    assert item.verdict == "judge_error"
    assert item.score_excluded is True
    assert item.evidence == "required_visual_file_cap_exceeded:planned=11,cap=10"
    assert item.render_call_count == 0
    assert item.perception_call_count == 0
    assert vision.calls == []
    assert responses.calls == []


@pytest.mark.parametrize(
    ("second_name", "vision_cap", "expected_error"),
    [
        # A ``Notes.txt`` case used to sit here. It is removed rather than
        # re-spelled: this test needs the criterion to stay generic so the
        # docx child routes formatting and the item comes out mixed, and under
        # a generic criterion plain text no longer routes visual at all. The
        # blocking property is still covered by the budget case below, and the
        # behaviour that replaced the removed one is asserted in
        # ``test_split_text_child_no_longer_blocks_its_visual_sibling``.
        (
            "Chart.pdf",
            0,
            "task_visual_budget_exceeded:required_calls=1,cap=0",
        ),
    ],
)
def test_mixed_split_preflight_error_blocks_formatting_child_main(
    monkeypatch, tmp_path, second_name, vision_cap, expected_error
):
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision(call_cap=vision_cap)
    grader._tool_judge.vision_perception = vision
    monkeypatch.setattr(
        tool_judge_mod,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("preflight error must precede render"),
    )
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Brief.docx").write_bytes(b"docx")
    (deliverable_dir / second_name).write_bytes(b"secondary")
    second_kind = "PDF" if second_name.endswith(".pdf") else "text file"
    task = TaskRubric(
        task_id="t-mixed-preflight",
        sector="Information",
        occupation="Analyst",
        prompt=(
            "Create two separate deliverables: a Word document and a "
            f"{second_kind}."
        ),
        rubric_items=[RubricItem("style", "Overall Style", 4, None)],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))
    item = grade.items[0]

    assert item.target_scope == "split_children"
    assert item.routing_modality == "mixed"
    assert item.verdict == "judge_error"
    assert item.score_excluded is True
    assert item.judge_call_count == 0
    assert item.render_call_count == 0
    assert item.perception_call_count == 0
    assert {child["routing_modality"] for child in item.child_grades} == {
        "formatting",
        "visual",
    }
    assert all(
        child["evidence"] == expected_error for child in item.child_grades
    )
    assert vision.calls == []
    assert responses.calls == []


def test_task_visual_budget_fails_all_visual_items_before_any_calls(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision(call_cap=1)
    grader._tool_judge.vision_perception = vision
    monkeypatch.setattr(
        tool_judge_mod,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("budget must fail before render"),
    )
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Report.pdf").write_bytes(b"pdf")
    task = TaskRubric(
        task_id="t-budget-fail",
        sector="Information",
        occupation="Analyst",
        prompt="Create one PDF report.",
        rubric_items=[
            RubricItem("v1", "Chart color is readable", 2, None),
            RubricItem("v2", "Graph layout is polished", 2, None),
        ],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))

    assert all(item.verdict == "judge_error" for item in grade.items)
    assert all(item.score_excluded for item in grade.items)
    assert all(
        item.evidence == "task_visual_budget_exceeded:required_calls=2,cap=1"
        for item in grade.items
    )
    assert grade.render_call_count == 0
    assert grade.perception_call_count == 0
    assert grade.judge_call_count == 0
    assert vision.calls == []
    assert responses.calls == []


def _image_only_pdf(path: Path) -> Path:
    """A PDF whose pages are pictures and whose text layer is empty."""
    pytest.importorskip("reportlab")
    pytest.importorskip("fitz")
    pytest.importorskip("PIL")
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    photo = path.parent / f"_{path.stem}.png"
    Image.new("RGB", (64, 64), color="white").save(photo)
    document = canvas.Canvas(str(path))
    for _ in range(2):
        document.drawImage(ImageReader(str(photo)), 40, 40, width=200, height=200)
        document.showPage()
    document.save()
    photo.unlink()
    return path


def _typed_pdf(path: Path) -> Path:
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    document = canvas.Canvas(str(path))
    document.drawString(100, 750, "The total contract value is 4,200 USD.")
    document.showPage()
    document.save()
    return path


def _scan_beside_readable_return(tmp_path: Path) -> Path:
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    _image_only_pdf(deliverable_dir / "Scan.pdf")
    _typed_pdf(deliverable_dir / "Return.pdf")
    return deliverable_dir


def _content_task(task_id: str, count: int):
    from core.rubric_loader import RubricItem, TaskRubric

    return TaskRubric(
        task_id=task_id,
        sector="Finance",
        occupation="Tax Preparer",
        prompt="Produce Scan.pdf and Return.pdf.",
        rubric_items=[
            RubricItem(
                f"r{index}",
                "The document states the total contract value.",
                2,
                None,
            )
            for index in range(count)
        ],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )


def test_visual_budget_falls_back_before_it_excludes_a_whole_task(
    monkeypatch, tmp_path
):
    """The 43dc9778 shape: over budget, and still graded.

    Two items about the contents of a bundle holding one scan and one
    readable return. Each escalates on the scan, so the task wants two
    renders against a cap of one. Excluding both would leave nothing scored,
    which is not a zero -- it is an ``all_items_score_excluded`` task that
    the analysers drop from the corpus. Falling back to the readable sibling
    grades it, and says so on the payload.
    """
    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "the return states 4,200"))]),
        _response(output=[_final(_payload("pass", 1.0, "the return states 4,200"))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision(call_cap=1)
    grader._tool_judge.vision_perception = vision

    grade = grader.grade_task(
        _content_task("t-budget-fallback", 2),
        str(_scan_beside_readable_return(tmp_path)),
    )

    assert grade.visual_budget_fallback == (
        "task_visual_budget_exceeded:required_calls=2,cap=1"
    )
    # Rescued outright: nothing was left over for the task to record.
    assert grade.visual_budget_unmet is None
    assert grade.error is None
    assert [item.verdict for item in grade.items] == ["pass", "pass"]
    assert not any(item.score_excluded for item in grade.items)
    assert all(item.visual_budget_downgraded for item in grade.items)
    assert [item.routing_modality for item in grade.items] == ["text", "text"]
    assert grade.pct == 100.0
    # The point of falling back is not to spend the budget differently.
    assert vision.calls == []
    assert grade.render_call_count == 0


def test_a_task_with_nothing_readable_still_fails_closed(monkeypatch, tmp_path):
    """The rule task 64 established, which this must not undo.

    When *every* selected file is a picture there is no text to fall back
    to, and reading zero characters would produce a fail verdict about a
    document that says the thing. Over budget with nothing to give up is
    still over budget.
    """
    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision(call_cap=1)
    grader._tool_judge.vision_perception = vision
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    _image_only_pdf(deliverable_dir / "Scan.pdf")
    _image_only_pdf(deliverable_dir / "Return.pdf")

    grade = grader.grade_task(
        _content_task("t-nothing-readable", 2), str(deliverable_dir)
    )

    assert grade.visual_budget_fallback is None
    assert all(item.score_excluded for item in grade.items)
    assert not any(item.visual_budget_downgraded for item in grade.items)
    assert grade.error == "all_items_score_excluded"
    # The task that leaves the corpus carries its own reason for leaving,
    # rather than only the items that are leaving with it.
    assert grade.visual_budget_unmet == grade.items[0].evidence
    assert grade.visual_budget_unmet is not None
    assert vision.calls == []
    assert responses.calls == []


def test_a_criterion_that_names_a_picture_is_not_given_a_text_verdict(
    monkeypatch, tmp_path
):
    """"Is the chart colour readable" has no answer in the characters.

    The fallback trades a preferred render for an acceptable read. A
    criterion classified VISUAL on its own words never had a read to fall
    back to, so the budget still fails it closed -- which is what
    ``test_task_visual_budget_fails_all_visual_items_before_any_calls``
    pins, here with a readable file present to prove the fallback is not
    what decides it.
    """
    from core.rubric_loader import RubricItem, TaskRubric

    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision(call_cap=1)
    grader._tool_judge.vision_perception = vision
    task = TaskRubric(
        task_id="t-explicit-visual",
        sector="Finance",
        occupation="Tax Preparer",
        prompt="Produce Scan.pdf and Return.pdf.",
        rubric_items=[
            RubricItem("v1", "Chart color is readable", 2, None),
            RubricItem("v2", "Graph layout is polished", 2, None),
        ],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(_scan_beside_readable_return(tmp_path)))

    assert grade.visual_budget_fallback is None
    assert all(item.score_excluded for item in grade.items)
    assert all(
        item.evidence == "task_visual_budget_exceeded:required_calls=4,cap=1"
        for item in grade.items
    )
    assert grade.visual_budget_unmet == (
        "task_visual_budget_exceeded:required_calls=4,cap=1"
    )
    assert vision.calls == []


def test_the_fallback_saves_what_it_can_and_excludes_the_rest(
    monkeypatch, tmp_path
):
    """A budget that the fallback narrows but still cannot meet.

    Three items on the same scan-beside-readable-return bundle: two content
    criteria that escalated only on the scan, and one that names a chart.
    Strict, the task wants four renders against a cap of one. Dropping the
    escalation takes it to two -- an improvement, still over. So the two
    content items are graded from the readable file and the chart item is
    excluded, which is the honest split: the fallback rescues exactly the
    items that had somewhere else to go, and invents nothing for the one
    that did not.

    The task survives with a partial score instead of vanishing from the
    corpus, and ``visual_budget_fallback`` records the original shortfall so
    a reader can see this score was reached the cheap way.
    """
    from core.rubric_loader import RubricItem, TaskRubric

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "states 4,200 USD"))]),
        _response(output=[_final(_payload("pass", 1.0, "states 4,200 USD"))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision(call_cap=1)
    grader._tool_judge.vision_perception = vision
    task = TaskRubric(
        task_id="t-partial-rescue",
        sector="Finance",
        occupation="Tax Preparer",
        prompt="Produce Scan.pdf and Return.pdf.",
        rubric_items=[
            RubricItem("c1", "The document states the total contract value.", 2, None),
            RubricItem("c2", "The document states the total contract value.", 2, None),
            RubricItem("v1", "Chart color is readable", 2, None),
        ],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(_scan_beside_readable_return(tmp_path)))

    by_id = {item.rubric_item_id: item for item in grade.items}
    assert grade.error is None
    assert grade.visual_budget_fallback == (
        "task_visual_budget_exceeded:required_calls=4,cap=1"
    )
    assert [by_id[i].score_excluded for i in ("c1", "c2", "v1")] == [
        False, False, True,
    ]
    assert [by_id[i].visual_budget_downgraded for i in ("c1", "c2", "v1")] == [
        True, True, False,
    ]
    assert [by_id[i].routing_modality for i in ("c1", "c2")] == ["text", "text"]
    assert by_id["v1"].evidence == (
        "task_visual_budget_exceeded:required_calls=2,cap=1"
    )
    # Narrowed and still short: the task records both what it gave up and
    # what that did not buy it. Neither field alone describes this task.
    assert grade.visual_budget_fallback != grade.visual_budget_unmet
    assert grade.visual_budget_unmet == (
        "task_visual_budget_exceeded:required_calls=2,cap=1"
    )
    assert vision.calls == []


def test_task_visual_budget_within_cap_spends_per_criterion(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "chart is readable"))]),
        _response(output=[_final(_payload("pass", 1.0, "graph is polished"))]),
    ])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision(call_cap=2)
    grader._tool_judge.vision_perception = vision
    render_calls = []

    def fake_render(op, path, **kwargs):
        render_calls.append(path)
        return {
            "ok": True,
            "data": {
                "kind": "image_png_base64",
                "base64": "aW1hZ2U=",
                "byte_size": 5,
                "scope": {"page": 1},
                "source_kind": "pdf",
                "source_page_count": 1,
                "renderer": {
                    "rasterizer": "pymupdf",
                    "pymupdf_version": "1.26.3",
                    "dpi": 150,
                },
            },
        }

    monkeypatch.setattr(tool_judge_mod, "read_deliverable", fake_render)
    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Report.pdf").write_bytes(b"pdf")
    task = TaskRubric(
        task_id="t-budget-pass",
        sector="Information",
        occupation="Analyst",
        prompt="Create one PDF report.",
        rubric_items=[
            RubricItem("v1", "Chart color is readable", 2, None),
            RubricItem("v2", "Graph layout is polished", 2, None),
        ],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(deliverable_dir))

    assert all(item.verdict == "pass" for item in grade.items)
    assert render_calls == ["Report.pdf", "Report.pdf"]
    assert len(vision.calls) == 2
    assert grade.render_call_count == 2
    assert grade.perception_call_count == 2
    assert grade.judge_call_count == 2
