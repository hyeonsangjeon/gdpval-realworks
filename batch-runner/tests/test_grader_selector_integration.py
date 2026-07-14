"""Selector integration tests for the v2 tool-calling grader path."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest


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


def _grader(monkeypatch, fake_client):
    from core.grader import Grader
    import core.grader as grader_mod

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
    monkeypatch.setattr(grader_mod, "AzureOpenAI", lambda **kw: fake_client)
    prompt_v1 = (
        Path(grader_mod.__file__).resolve().parent.parent
        / "prompts"
        / "grader_judge.md"
    )
    cfg = {
        "judge": {
            "provider": "azure_openai",
            "endpoint_env": "AZURE_OPENAI_ENDPOINT",
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
    return Grader(cfg, rubric_loader=None)


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
    assert len(responses.calls) == 2
    assert style.judge_call_count == 2
    assert style.perception_call_count == 2
    assert style.render_call_count == 2
    assert grade.judge_call_count == 2
    assert grade.judge_input_tokens == 160
    assert grade.judge_output_tokens == 40
    assert grade.judge_cached_tokens == 10
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

    responses = ScriptedResponses([])
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
    assert grade.judge_call_count == 0
    assert grade.total_max == 1
    assert responses.calls == []


def test_split_visual_cap_is_preflighted_before_any_render_or_child_main(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric

    responses = ScriptedResponses([])
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
    assert grade.judge_call_count == 0
    assert vision.calls == []
    assert responses.calls == []


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


def test_explicit_visual_docx_remains_fail_closed_unsupported(
    monkeypatch, tmp_path
):
    from core.rubric_loader import RubricItem, TaskRubric
    import core.tool_calling_judge as tool_judge_mod

    responses = ScriptedResponses([])
    grader = _grader(monkeypatch, SimpleNamespace(responses=responses))
    vision = CountingVision()
    grader._tool_judge.vision_perception = vision
    monkeypatch.setattr(
        tool_judge_mod,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("unsupported DOCX must fail before render"),
    )
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
    assert item.verdict == "judge_error"
    assert item.score_excluded is True
    assert "unsupported_path" in item.evidence
    assert item.render_call_count == 0
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
