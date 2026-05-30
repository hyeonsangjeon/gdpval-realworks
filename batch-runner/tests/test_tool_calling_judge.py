"""Tests for ``core.tool_calling_judge.ToolCallingJudge`` (PR2 task 203)."""

from __future__ import annotations

import base64
import io
import json
import struct
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.rubric_loader import RubricItem, TaskRubric
from core.tool_calling_judge import ToolCallingJudge, ToolCallingResult


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "grader_judge_v2.md"
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")


# ── Helpers / fakes ──────────────────────────────────────────────────


def _usage(in_tok: int = 100, out_tok: int = 30) -> SimpleNamespace:
    return SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok)


def _response(*, output: list[dict] | None = None, output_text: str = "",
              in_tok: int = 100, out_tok: int = 30) -> SimpleNamespace:
    return SimpleNamespace(
        output=output or [],
        output_text=output_text,
        usage=_usage(in_tok, out_tok),
        incomplete_details=None,
        status=None,
    )


def _fc(call_id: str, name: str, **args: Any) -> dict:
    return {
        "type": "function_call",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(args),
    }


def _final(text: str) -> dict:
    return {"type": "message", "content": [{"type": "output_text", "text": text}]}


class ScriptedResponses:
    """Returns a queued list of responses, one per ``create`` call."""

    def __init__(self, script: list[SimpleNamespace]):
        self.script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("Scripted client ran out of responses")
        return self.script.pop(0)


class FakeClient:
    def __init__(self, responses: ScriptedResponses):
        self.responses = responses


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def deliverable_dir(tmp_path: Path) -> Path:
    f = tmp_path / "report.xlsx"
    # We don't actually need a valid xlsx — read_deliverable is called via
    # the live module against a real file, so write a 1-cell workbook.
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "alpha"
    ws["A2"] = "beta"
    wb.save(f)
    return tmp_path


@pytest.fixture
def task_and_item() -> tuple[TaskRubric, RubricItem]:
    item = RubricItem(
        rubric_item_id="r1",
        criterion="The deliverable contains an 'alpha' label in column A",
        score=5,
        required=None,
    )
    task = TaskRubric(
        task_id="t1",
        sector="Information",
        occupation="Analyst",
        prompt="Make a report",
        rubric_items=[item],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )
    return task, item


# ── Single-shot finish (no tool calls) ───────────────────────────────


def test_no_tool_call_path_parses_final_json(deliverable_dir, task_and_item):
    task, item = task_and_item
    final_payload = json.dumps({
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "label present",
        "confidence": 0.9,
        "reasoning": "ok",
        "tool_calls_made": 0,
    })
    client = FakeClient(ScriptedResponses([_response(output=[_final(final_payload)])]))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE)
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert isinstance(res, ToolCallingResult)
    assert res.verdict == "pass"
    assert res.partial_score == 1.0
    assert res.awarded_score == 5.0
    assert res.tool_calls_made == 0
    assert res.iterations == 1
    assert res.judge_error is None
    assert res.routing_modality == "text"


# ── One tool round then final ────────────────────────────────────────


def test_tool_round_then_final(deliverable_dir, task_and_item):
    task, item = task_and_item
    # Iteration 1: model asks to inspect_structure.
    iter1 = _response(output=[_fc(
        "c1", "read_deliverable",
        op="inspect_structure", path="report.xlsx",
    )])
    iter2 = _response(output=[_final(json.dumps({
        "verdict": "pass", "partial_score": 1.0,
        "evidence": "kind=xlsx, 1 sheet",
        "confidence": 0.95, "reasoning": "ok",
        "tool_calls_made": 1,
    }))])
    client = FakeClient(ScriptedResponses([iter1, iter2]))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE)
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.verdict == "pass"
    assert res.tool_calls_made == 1
    assert res.iterations == 2
    # The second call's input should include the function_call AND the
    # function_call_output messages we appended.
    second_input = client.responses.calls[1]["input"]
    types = [m.get("type") for m in second_input if isinstance(m, dict)]
    assert "function_call" in types
    assert "function_call_output" in types


# ── Tool-cap enforcement ────────────────────────────────────────────


def test_tool_call_cap_short_circuits(deliverable_dir, task_and_item):
    task, item = task_and_item

    # Build a script where the model keeps asking for inspect_structure
    # until the cap of 2 is hit; then issues final.
    def ask(i):
        return _response(output=[_fc(f"c{i}", "read_deliverable",
                                     op="inspect_structure",
                                     path="report.xlsx")])
    script = [ask(1), ask(2), ask(3),
              _response(output=[_final(json.dumps({
                  "verdict": "pass", "partial_score": 1.0,
                  "evidence": "got enough", "confidence": 0.5,
                  "reasoning": "stopping", "tool_calls_made": 2,
              }))])]
    client = FakeClient(ScriptedResponses(script))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE,
                             per_item_tool_call_cap=2)
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    # 2 real tool dispatches; the 3rd request was refused via
    # cap_exceeded envelope returned to the model.
    assert res.tool_calls_made == 2
    assert res.verdict == "pass"


def test_max_iterations_breaks(deliverable_dir, task_and_item):
    task, item = task_and_item
    # Model just loops forever asking for tools; never issues final.
    def ask(i):
        return _response(output=[_fc(f"c{i}", "read_deliverable",
                                     op="inspect_structure",
                                     path="report.xlsx")])
    client = FakeClient(ScriptedResponses([ask(i) for i in range(20)]))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE,
                             per_item_tool_call_cap=100,
                             max_iterations=3)
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.verdict == "judge_error"
    assert res.judge_error == "max_iterations_exceeded"
    assert res.iterations == 3


# ── Routing modality detection ──────────────────────────────────────


def test_routing_modality_visual_advertises_vision_tool(deliverable_dir, task_and_item):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r2",
        criterion="Chart formatting is clean and colors are legible",
        score=4, required=None,
    )
    client = FakeClient(ScriptedResponses([_response(output=[_final(json.dumps({
        "verdict": "pass", "partial_score": 1.0, "evidence": "n/a",
        "confidence": 0.5, "reasoning": "x", "tool_calls_made": 0,
    }))])]))

    class _StubVision:
        def judge(self, **kw): raise AssertionError("not used in this test")

    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE,
                             vision_perception=_StubVision())
    res = judge.judge_item(task=task, item=visual_item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.routing_modality == "visual"
    tool_names = [t["name"] for t in client.responses.calls[0]["tools"]]
    assert "vision_judge" in tool_names
    assert "read_deliverable" in tool_names


def test_routing_modality_text_omits_perception_tools(deliverable_dir, task_and_item):
    task, item = task_and_item
    client = FakeClient(ScriptedResponses([_response(output=[_final(json.dumps({
        "verdict": "pass", "partial_score": 1.0, "evidence": "x",
        "confidence": 0.5, "reasoning": "x", "tool_calls_made": 0,
    }))])]))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE,
                             vision_perception=object(),
                             audio_perception=object())
    judge.judge_item(task=task, item=item,
                     deliverable_dir=str(deliverable_dir),
                     file_names=["report.xlsx"])
    tool_names = [t["name"] for t in client.responses.calls[0]["tools"]]
    assert tool_names == ["read_deliverable"]


# ── Vision sub-judge dispatch ────────────────────────────────────────


def test_vision_tool_dispatch_invokes_perception(deliverable_dir, task_and_item):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r3",
        criterion="Render quality of the chart image",
        score=4, required=None,
    )

    PIL = pytest.importorskip("PIL")
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(buf, format="PNG")
    fake_b64 = base64.b64encode(buf.getvalue()).decode()

    class _StubVision:
        def __init__(self):
            self.calls = []

        def judge(self, *, criterion, image_b64, cache_key=None):
            self.calls.append((criterion, cache_key, len(image_b64)))
            return SimpleNamespace(
                verdict="pass", partial_score=1.0, evidence="clean chart",
                confidence=0.8, reasoning="ok", judge_error=None,
                to_dict=lambda: {"verdict": "pass", "partial_score": 1.0,
                                 "evidence": "clean chart", "confidence": 0.8,
                                 "reasoning": "ok", "judge_error": None},
            )

    stub = _StubVision()

    iter1 = _response(output=[_fc("c1", "vision_judge",
                                  criterion="Render quality",
                                  image_b64=fake_b64)])
    iter2 = _response(output=[_final(json.dumps({
        "verdict": "pass", "partial_score": 1.0,
        "evidence": "vision sub-judge agreed",
        "confidence": 0.9, "reasoning": "ok",
        "tool_calls_made": 1,
    }))])
    client = FakeClient(ScriptedResponses([iter1, iter2]))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE,
                             vision_perception=stub)
    res = judge.judge_item(task=task, item=visual_item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.verdict == "pass"
    assert len(stub.calls) == 1
    assert res.tool_calls_made == 1


# ── Error paths ──────────────────────────────────────────────────────


def test_upstream_exception_yields_judge_error(deliverable_dir, task_and_item):
    task, item = task_and_item

    class _BoomResponses:
        def create(self, **kw):
            raise RuntimeError("boom")

    judge = ToolCallingJudge(
        client=SimpleNamespace(responses=_BoomResponses()),
        model="gpt-5.4", prompt_template=PROMPT_TEMPLATE,
    )
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.verdict == "judge_error"
    assert res.judge_error is not None
    assert "RuntimeError" in res.judge_error


def test_unparseable_final_text_is_judge_error(deliverable_dir, task_and_item):
    task, item = task_and_item
    client = FakeClient(ScriptedResponses([_response(output=[_final(
        "this is not json at all"
    )])]))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE)
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.verdict == "judge_error"
    assert res.judge_error == "final_json_parse_failed"


def test_missing_evidence_downgrades_to_fail(deliverable_dir, task_and_item):
    task, item = task_and_item
    final_payload = json.dumps({
        "verdict": "pass", "partial_score": 1.0,
        "evidence": "   ",  # whitespace only
        "confidence": 0.9, "reasoning": "ok", "tool_calls_made": 0,
    })
    client = FakeClient(ScriptedResponses([_response(output=[_final(final_payload)])]))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE)
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.verdict == "fail"
    assert res.partial_score == 0.0
    assert res.evidence == "missing evidence"


def test_unknown_tool_name_returns_envelope_error(deliverable_dir, task_and_item):
    task, item = task_and_item
    iter1 = _response(output=[_fc("c1", "definitely_not_a_tool")])
    iter2 = _response(output=[_final(json.dumps({
        "verdict": "fail", "partial_score": 0.0,
        "evidence": "tool unavailable", "confidence": 0.5,
        "reasoning": "could not inspect", "tool_calls_made": 1,
    }))])
    client = FakeClient(ScriptedResponses([iter1, iter2]))
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE)
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    # Judge handled it and returned a fail — the unknown function is
    # surfaced via function_call_output to the model, not raised.
    assert res.verdict == "fail"
    assert res.tool_calls_made == 1
    # Second call's input should have the envelope-error output.
    second_input = client.responses.calls[1]["input"]
    outputs = [m for m in second_input if isinstance(m, dict)
               and m.get("type") == "function_call_output"]
    assert outputs and "bad_function" in outputs[0]["output"]
