"""Integration test: ``Grader._judge`` dispatches to ``ToolCallingJudge``
when the config opts into the v2 path (PR2 task 203)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


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
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)


def test_production_sol_max_config_wires_all_grading_roles():
    from core.grader import Grader

    config_path = Path("grading_configs/default_v2_sol_max.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    client = SimpleNamespace(responses=ScriptedResponses([]))

    grader = Grader(config, rubric_loader=None, client=client)

    assert grader.model == "gpt-5.6-sol"
    assert grader._tool_judge.model == "gpt-5.6-sol"
    assert grader._tool_judge.reasoning_effort == "max"
    assert grader._tool_judge.finalization_reasoning_effort == "max"
    assert grader._tool_judge.vision_perception.deployment == "gpt-5.6-sol"
    assert grader._tool_judge.vision_perception.reasoning_effort == "max"
    assert grader._tool_judge.audio_perception.deployment == "gpt-audio-1.5"


def test_grader_dispatch_uses_tool_calling_judge_when_configured(monkeypatch, tmp_path):
    """End-to-end: a config with judge.tools.read_deliverable causes
    Grader._judge to delegate, and the delegated call returns an
    ItemGrade with verdict/awarded_score set from the tool-calling
    judge's final JSON."""
    from core.grader import Grader
    from core.rubric_loader import RubricItem, TaskRubric

    final_payload = json.dumps({
        "verdict": "pass", "partial_score": 1.0,
        "evidence": "kind=xlsx", "confidence": 0.9,
        "reasoning": "ok", "tool_calls_made": 0,
    })

    fake_client = SimpleNamespace(
        responses=ScriptedResponses([_response(output=[_final(final_payload)])])
    )

    import core.grader as grader_mod

    # Write a deliverable file.
    deliverable_dir = tmp_path / "deliverables"
    deliverable_dir.mkdir()
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active["A1"] = "alpha"
    wb.save(deliverable_dir / "out.xlsx")

    # Build minimal v2 grading config.
    prompt_v1 = Path(grader_mod.__file__).resolve().parent.parent / "prompts" / "grader_judge.md"
    cfg = {
        "schema_version": "2.0",
        "judge": {
            "provider": "azure_openai",
            "api_version": "2025-04-01-preview",
            "model": "gpt-5.4",
            "reasoning": {"effort": "medium"},
            "generation": {"max_output_tokens": 2400},
            # The trigger:
            "tools": {
                "read_deliverable": {
                    "ops": ["inspect_structure", "read_content",
                            "inspect_formatting", "probe_audio", "probe_video"],
                    "per_item_call_cap": 8,
                    "max_iterations": 6,
                },
            },
        },
        "prompt": {"template": str(prompt_v1)},
        "grader": {"evidence_max_chars": 200, "judge_max_retries": 2},
        "tpm_guard": {},
    }

    grader = Grader(cfg, rubric_loader=None, client=fake_client)
    assert grader._tool_judge is not None, "tool-calling judge should be active"
    assert grader._tool_judge.finalization_retries == 1

    item = RubricItem(
        rubric_item_id="r1",
        criterion="The deliverable mentions alpha",
        score=5, required=None,
    )
    task = TaskRubric(
        task_id="t1", sector="Information", occupation="Analyst",
        prompt="x", rubric_items=[item], rubric_pretty="",
        reference_files=[], gold_deliverable_files=[],
    )

    files = [deliverable_dir / "out.xlsx"]
    ig, in_tok, out_tok = grader._judge(task, item, files)
    assert ig.verdict == "pass"
    assert ig.awarded_score == 5.0
    assert ig.evidence == "kind=xlsx"
    assert in_tok == 80
    assert out_tok == 20
    op_enum = fake_client.responses.calls[0]["tools"][0][
        "parameters"
    ]["properties"]["op"]["enum"]
    assert op_enum == [
        "inspect_structure", "read_content", "inspect_formatting",
        "probe_audio", "probe_video",
    ]
    assert "render_to_image" not in op_enum


def test_grader_without_tools_block_uses_legacy_path(monkeypatch, tmp_path):
    """No judge.tools => _tool_judge stays None => legacy _judge runs."""
    from core.grader import Grader
    import core.grader as grader_mod

    fake_client = SimpleNamespace()

    prompt_v1 = Path(grader_mod.__file__).resolve().parent.parent / "prompts" / "grader_judge.md"
    cfg = {
        "schema_version": "1.0",
        "judge": {
            "provider": "azure_openai",
            "api_version": "2025-04-01-preview",
            "model": "gpt-5.4",
            "reasoning": {"effort": "high"},
            "generation": {"max_output_tokens": 1024},
        },
        "prompt": {"template": str(prompt_v1)},
        "grader": {},
        "tpm_guard": {},
    }
    grader = Grader(cfg, rubric_loader=None, client=fake_client)
    assert grader._tool_judge is None
