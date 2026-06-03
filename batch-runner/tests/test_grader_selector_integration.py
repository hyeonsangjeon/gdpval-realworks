"""Selector integration tests for the v2 tool-calling grader path."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


def _final(text: str) -> dict:
    return {"type": "message", "content": [{"type": "output_text", "text": text}]}


def _response(*, output, in_tok=80, out_tok=20):
    return SimpleNamespace(
        output=output,
        output_text="",
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok),
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
                    "ops": ["inspect_structure", "read_content"],
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


def test_wrong_format_fails_manifest_but_excludes_overall_style(monkeypatch, tmp_path):
    from core.rubric_loader import RubricItem, TaskRubric

    fake_client = SimpleNamespace(responses=ScriptedResponses([]))
    grader = _grader(monkeypatch, fake_client)

    deliverable_dir = tmp_path / "task"
    deliverable_dir.mkdir()
    (deliverable_dir / "Plan.docx").write_text("wrong format", encoding="utf-8")

    items = [
        RubricItem("manifest", "Submission is provided as a single PDF document.", 1, None),
        RubricItem("style", "Overall formatting and style of the deliverable", 5, None),
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

    responses = ScriptedResponses([
        _response(output=[_final(_payload("pass", 1.0, "session 13 polished"))]),
        _response(output=[_final(_payload("partial", 0.5, "session 14 readable"))]),
    ])
    fake_client = SimpleNamespace(responses=responses)
    grader = _grader(monkeypatch, fake_client)

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
    assert style.verdict == "partial"
    assert style.awarded_score == 3.0
    assert grade.judge_call_count == 2
