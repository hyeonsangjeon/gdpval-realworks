"""Integration test: ``Grader._judge`` dispatches to ``ToolCallingJudge``
when the config opts into the v2 path (PR2 task 203)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


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


def test_grader_dispatch_uses_tool_calling_judge_when_configured(monkeypatch, tmp_path):
    """End-to-end: a config with judge.tools.read_deliverable causes
    Grader._judge to delegate, and the delegated call returns an
    ItemGrade with verdict/awarded_score set from the tool-calling
    judge's final JSON."""
    from core.grader import Grader
    from core.rubric_loader import RubricItem, TaskRubric

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")

    final_payload = json.dumps({
        "verdict": "pass", "partial_score": 1.0,
        "evidence": "kind=xlsx", "confidence": 0.9,
        "reasoning": "ok", "tool_calls_made": 0,
    })

    fake_client = SimpleNamespace(
        responses=ScriptedResponses([_response(output=[_final(final_payload)])])
    )

    # Stub out AzureOpenAI in Grader's namespace so __init__ uses our fake.
    import core.grader as grader_mod
    monkeypatch.setattr(grader_mod, "AzureOpenAI", lambda **kw: fake_client)

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
            "endpoint_env": "AZURE_OPENAI_ENDPOINT",
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

    grader = Grader(cfg, rubric_loader=None)
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

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
    monkeypatch.setattr(grader_mod, "AzureOpenAI", lambda **kw: SimpleNamespace())

    prompt_v1 = Path(grader_mod.__file__).resolve().parent.parent / "prompts" / "grader_judge.md"
    cfg = {
        "schema_version": "1.0",
        "judge": {
            "provider": "azure_openai",
            "endpoint_env": "AZURE_OPENAI_ENDPOINT",
            "api_version": "2025-04-01-preview",
            "model": "gpt-5.4",
            "reasoning": {"effort": "high"},
            "generation": {"max_output_tokens": 1024},
        },
        "prompt": {"template": str(prompt_v1)},
        "grader": {},
        "tpm_guard": {},
    }
    grader = Grader(cfg, rubric_loader=None)
    assert grader._tool_judge is None
