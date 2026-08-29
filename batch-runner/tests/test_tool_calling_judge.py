"""Tests for ``core.tool_calling_judge.ToolCallingJudge`` (PR2 task 203)."""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.rubric_loader import RubricItem, TaskRubric
from core.tool_calling_judge import (
    ToolCallingJudge,
    ToolCallingResult,
    resolve_visual_file_cap,
)


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "grader_judge_v2.md"
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")
tool_calling_judge_module = importlib.import_module("core.tool_calling_judge")


# ── Helpers / fakes ──────────────────────────────────────────────────


def test_prompt_cache_key_respects_azure_length_limit():
    exact_key = "x" * 64
    exact = ToolCallingJudge(
        client=None,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        prompt_cache_key=exact_key,
    )
    long_key = "x" * 65
    bounded = ToolCallingJudge(
        client=None,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        prompt_cache_key=long_key,
    )

    assert exact.prompt_cache_key == exact_key
    assert bounded.prompt_cache_key == hashlib.sha256(
        long_key.encode("utf-8")
    ).hexdigest()
    assert len(bounded.prompt_cache_key) == 64


def _usage(
    in_tok: int = 100, out_tok: int = 30, cached_tok: int = 7
) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=in_tok,
        output_tokens=out_tok,
        input_tokens_details=SimpleNamespace(cached_tokens=cached_tok),
    )


def _response(*, output: list[dict] | None = None, output_text: str = "",
              in_tok: int = 100, out_tok: int = 30,
              cached_tok: int = 7, status: str | None = None,
              incomplete_reason: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        output=output or [],
        output_text=output_text,
        usage=_usage(in_tok, out_tok, cached_tok),
        incomplete_details=(
            SimpleNamespace(reason=incomplete_reason)
            if incomplete_reason is not None else None
        ),
        status=status,
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


class StubVision:
    def __init__(self, *, remaining_calls: int = 5, judge_error: str | None = None):
        self.remaining_calls = remaining_calls
        self.judge_error = judge_error
        self.calls: list[dict[str, Any]] = []

    def judge(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        payload = {
            "verdict": "judge_error" if self.judge_error else "pass",
            "partial_score": 0.0 if self.judge_error else 1.0,
            "evidence": "visible surface is legible",
            "confidence": 0.9,
            "reasoning": "render inspected",
            "judge_error": self.judge_error,
            "api_call_count": 1,
            "input_tokens": 31,
            "output_tokens": 9,
            "cached_tokens": 3,
            "latency_ms": 12.5,
            "usage_complete": True,
        }
        return SimpleNamespace(
            judge_error=self.judge_error,
            to_dict=lambda: payload,
        )


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


def test_upstream_provider_error_is_class_only_in_result_and_log(
    deliverable_dir, task_and_item, caplog
):
    task, item = task_and_item
    sensitive = (
        "https://private.services.ai.azure.com/openai/v1/ "
        "deployment=private"
    )

    class FailingResponses:
        def create(self, **_kwargs):
            raise RuntimeError(sensitive)

    judge = ToolCallingJudge(
        client=FakeClient(FailingResponses()),
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
    )

    with caplog.at_level("WARNING", logger="core.tool_calling_judge"):
        result = judge.judge_item(
            task=task,
            item=item,
            deliverable_dir=str(deliverable_dir),
            file_names=["report.xlsx"],
        )

    assert result.judge_error == "provider_error:RuntimeError"
    assert sensitive not in result.judge_error
    assert sensitive not in caplog.text


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


def test_empty_final_response_retries_once_without_tools(
    deliverable_dir, task_and_item, caplog
):
    task, item = task_and_item
    first = _response(
        output=[_fc(
            "c1", "read_deliverable",
            op="inspect_structure", path="report.xlsx",
        )],
        in_tok=100,
        out_tok=30,
        cached_tok=7,
    )
    empty = _response(
        output=[{"type": "reasoning", "id": "r1", "summary": []}],
        in_tok=200,
        out_tok=2400,
        cached_tok=50,
        status="incomplete",
        incomplete_reason="max_output_tokens",
    )
    final = _response(
        output=[_final(json.dumps({
            "verdict": "pass",
            "partial_score": 1.0,
            "evidence": "all subdivisions are represented",
            "confidence": 0.9,
            "reasoning": "verified from prior tool evidence",
        }))],
        in_tok=210,
        out_tok=60,
        cached_tok=55,
    )
    client = FakeClient(ScriptedResponses([first, empty, final]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=1,
    )

    with caplog.at_level("WARNING", logger="core.tool_calling_judge"):
        result = judge.judge_item(
            task=task,
            item=item,
            deliverable_dir=str(deliverable_dir),
            file_names=["report.xlsx"],
        )

    assert result.verdict == "pass"
    assert result.main_api_call_count == 3
    assert result.iterations == 3
    assert result.input_tokens == 510
    assert result.output_tokens == 2490
    assert result.cached_tokens == 112
    retry = client.responses.calls[2]
    assert "tools" not in retry
    assert "parallel_tool_calls" not in retry
    assert retry["reasoning"] == {"effort": "low"}
    assert retry["input"][-1]["content"] == (
        tool_calling_judge_module._FINALIZATION_RETRY_PROMPT
    )
    assert "max_output_tokens" in caplog.text
    assert "all subdivisions are represented" not in caplog.text


def test_empty_final_retry_budget_exhaustion_stays_fail_closed(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    empty = _response(
        out_tok=2400,
        status="incomplete",
        incomplete_reason="max_output_tokens",
    )
    client = FakeClient(ScriptedResponses([empty, empty]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=1,
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == "empty_final_text"
    assert result.main_api_call_count == 2
    assert result.iterations == 2
    assert len(client.responses.calls) == 2


def test_finalization_retry_uses_configured_max_effort(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    empty = _response(
        out_tok=2400,
        status="incomplete",
        incomplete_reason="max_output_tokens",
    )
    final = _response(
        output=[_final(json.dumps({
            "verdict": "pass",
            "partial_score": 1.0,
            "evidence": "validated from prior evidence",
            "confidence": 0.9,
            "reasoning": "finalized with max effort",
        }))],
    )
    client = FakeClient(ScriptedResponses([empty, final]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.6-sol",
        prompt_template=PROMPT_TEMPLATE,
        reasoning_effort="max",
        finalization_reasoning_effort="max",
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "pass"
    assert client.responses.calls[0]["reasoning"] == {"effort": "max"}
    assert client.responses.calls[1]["reasoning"] == {"effort": "max"}


def test_semantic_invalid_final_retries_once_with_configured_max_effort(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    invalid = _response(output=[_final("{}")])
    final = _response(
        output=[_final(json.dumps({
            "verdict": "pass",
            "partial_score": 1.0,
            "evidence": "validated from prior evidence",
            "confidence": 0.9,
            "reasoning": "semantic envelope recovered",
        }))],
    )
    client = FakeClient(ScriptedResponses([invalid, final]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.6-sol",
        prompt_template=PROMPT_TEMPLATE,
        reasoning_effort="max",
        finalization_reasoning_effort="max",
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "pass"
    assert result.main_api_call_count == 2
    assert "tools" not in client.responses.calls[1]
    assert client.responses.calls[1]["reasoning"] == {"effort": "max"}


def test_semantic_invalid_final_at_iteration_limit_uses_retry_budget(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    invalid = _response(output=[_final("{}")])
    final = _response(output=[_final(json.dumps({
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "recovered after the normal iteration budget",
        "confidence": 0.9,
        "reasoning": "bounded finalization succeeded",
    }))])
    client = FakeClient(ScriptedResponses([invalid, final]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.6-sol",
        prompt_template=PROMPT_TEMPLATE,
        max_iterations=1,
        finalization_retries=1,
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "pass"
    assert result.main_api_call_count == 2
    assert result.iterations == 2
    assert "tools" not in client.responses.calls[1]


def test_semantic_invalid_final_at_iteration_limit_retries_only_once(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    client = FakeClient(ScriptedResponses([
        _response(output=[_final("{}")]),
        _response(output=[_final("{}")]),
    ]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.6-sol",
        prompt_template=PROMPT_TEMPLATE,
        max_iterations=1,
        finalization_retries=1,
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "judge_error"
    assert result.main_api_call_count == 2
    assert result.iterations == 2
    assert len(client.responses.calls) == 2


def test_malformed_final_json_retries_once_without_tools(
    deliverable_dir, task_and_item, caplog
):
    task, item = task_and_item
    malformed = _response(
        output=[_final('{"verdict":"pass","partial_score":')],
        in_tok=200,
        out_tok=80,
        cached_tok=50,
    )
    final = _response(
        output=[_final(json.dumps({
            "verdict": "pass",
            "partial_score": 1.0,
            "evidence": "all divisions are represented",
            "confidence": 0.9,
            "reasoning": "verified from prior tool evidence",
        }))],
        in_tok=210,
        out_tok=60,
        cached_tok=55,
    )
    client = FakeClient(ScriptedResponses([malformed, final]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=1,
    )

    with caplog.at_level("WARNING", logger="core.tool_calling_judge"):
        result = judge.judge_item(
            task=task,
            item=item,
            deliverable_dir=str(deliverable_dir),
            file_names=["report.xlsx"],
        )

    assert result.verdict == "pass"
    assert result.main_api_call_count == 2
    assert result.iterations == 2
    assert result.input_tokens == 410
    assert result.output_tokens == 140
    assert result.cached_tokens == 105
    retry = client.responses.calls[1]
    assert "tools" not in retry
    assert retry["reasoning"] == {"effort": "low"}
    assert "final_json_parse_failed" in caplog.text
    assert '"partial_score":' not in caplog.text


def test_malformed_final_retry_budget_exhaustion_stays_fail_closed(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    malformed = _response(
        output=[_final('{"verdict":"pass","partial_score":')]
    )
    client = FakeClient(ScriptedResponses([malformed, malformed]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=1,
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == "final_json_parse_failed"
    assert result.main_api_call_count == 2
    assert result.iterations == 2
    assert len(client.responses.calls) == 2


def test_empty_then_malformed_final_shares_one_retry_budget(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    empty = _response(
        output=[{"type": "reasoning", "id": "r1", "summary": []}],
        in_tok=100,
        out_tok=2400,
        cached_tok=7,
        status="incomplete",
        incomplete_reason="max_output_tokens",
    )
    malformed = _response(
        output=[_final("not-json")],
        in_tok=200,
        out_tok=40,
        cached_tok=50,
    )
    unused_valid = _response(output=[_final(json.dumps({
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "unused",
        "confidence": 0.9,
        "reasoning": "unused",
    }))])
    scripted = ScriptedResponses([empty, malformed, unused_valid])
    judge = ToolCallingJudge(
        client=FakeClient(scripted),
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=1,
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == "final_json_parse_failed"
    assert result.main_api_call_count == 2
    assert result.iterations == 2
    assert result.input_tokens == 300
    assert result.output_tokens == 2440
    assert result.cached_tokens == 57
    assert len(scripted.calls) == 2
    assert len(scripted.script) == 1


def test_finalization_retry_setting_is_clamped_to_one(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    malformed = _response(output=[_final('{"verdict":"pass","partial_score":')])
    unused_valid = _response(output=[_final(json.dumps({
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "unused",
        "confidence": 0.9,
        "reasoning": "unused",
    }))])
    scripted = ScriptedResponses([malformed, malformed, unused_valid])
    judge = ToolCallingJudge(
        client=FakeClient(scripted),
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=2,
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert judge.finalization_retries == 1
    assert result.verdict == "judge_error"
    assert result.judge_error == "final_json_parse_failed"
    assert result.main_api_call_count == 2
    assert len(scripted.calls) == 2
    assert len(scripted.script) == 1


def test_finalization_tool_call_is_rejected_without_dispatch(
    deliverable_dir, task_and_item, monkeypatch, caplog
):
    task, item = task_and_item
    malformed = _response(output=[_final('{"verdict":"pass","partial_score":')])
    unexpected_tool_call = _response(output=[_fc(
        "unexpected",
        "read_deliverable",
        op="inspect_structure",
        path="report.xlsx",
    )])
    client = FakeClient(ScriptedResponses([malformed, unexpected_tool_call]))
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("finalization must not dispatch tools"),
    )
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=1,
    )

    with caplog.at_level("WARNING", logger="core.tool_calling_judge"):
        result = judge.judge_item(
            task=task,
            item=item,
            deliverable_dir=str(deliverable_dir),
            file_names=["report.xlsx"],
        )

    assert result.verdict == "judge_error"
    assert result.judge_error == "unexpected_tool_call_during_finalization"
    assert result.score_excluded is True
    assert result.main_api_call_count == 2
    assert result.tool_calls_made == 0
    assert result.tools_used == []
    assert "rejected tool call during finalization" in caplog.text


def test_malformed_retry_accounts_latency_guard_and_missing_usage(
    deliverable_dir, task_and_item, monkeypatch
):
    task, item = task_and_item
    ticks = iter([1.0, 1.125, 2.0, 2.250])
    monkeypatch.setattr(
        tool_calling_judge_module.time, "perf_counter", lambda: next(ticks)
    )
    malformed = _response(
        output=[_final('{"verdict":"pass","partial_score":')],
        in_tok=41,
        out_tok=6,
        cached_tok=4,
    )
    final = _response(output=[_final(json.dumps({
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "recovered",
        "confidence": 0.9,
        "reasoning": "valid JSON",
    }))])
    final.usage = None
    guarded = []
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([malformed, final])),
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=1,
        before_upstream_call=lambda: guarded.append("main"),
    )

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "pass"
    assert guarded == ["main", "main"]
    assert result.main_api_call_count == 2
    assert result.latency_ms == 375.0
    assert result.input_tokens == 41
    assert result.output_tokens == 6
    assert result.cached_tokens == 4
    assert result.usage_complete is False


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


def test_visual_preflight_runs_before_main_without_vision_tool_or_base64(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r2",
        criterion="Chart formatting is clean and colors are legible",
        score=4, required=None,
    )
    pytest.importorskip("PIL")
    from PIL import Image
    image = io.BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(image, format="PNG")
    image_b64 = base64.b64encode(image.getvalue()).decode("ascii")

    final = _response(output=[_final(json.dumps({
        "verdict": "pass", "partial_score": 1.0,
        "evidence": "vision confirmed legible colors",
        "confidence": 0.9, "reasoning": "visual evidence used",
        "tool_calls_made": 0,
    }))])
    events = []

    class OrderedResponses(ScriptedResponses):
        def create(self, **kwargs):
            events.append("main")
            return super().create(**kwargs)

    client = FakeClient(OrderedResponses([final]))
    render_calls = []

    def fake_read(op, path, *, base_dir, scope=None):
        events.append(f"render:{path}")
        render_calls.append((op, path, scope))
        return {
            "ok": True,
            "data": {
                "kind": "image_png_base64",
                "source_kind": "xlsx",
                "scope": {"workbook_page": 1},
                "source_sheet_count": 1,
                "converted_page_count": 1,
                "renderer": {"converter": "libreoffice"},
                "byte_size": len(image.getvalue()),
                "base64": image_b64,
            },
        }

    monkeypatch.setattr(tool_calling_judge_module, "read_deliverable", fake_read)

    class OrderedVision(StubVision):
        def judge(self, **kwargs):
            events.append("vision")
            return super().judge(**kwargs)

    stub = OrderedVision()
    upstream_calls = []
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE,
                             vision_perception=stub,
                             before_upstream_call=lambda: upstream_calls.append(1))
    res = judge.judge_item(task=task, item=visual_item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.routing_modality == "visual"
    tool_names = [t["name"] for t in client.responses.calls[0]["tools"]]
    assert tool_names == ["read_deliverable"]
    op_enum = client.responses.calls[0]["tools"][0]["parameters"]["properties"]["op"]["enum"]
    assert "render_to_image" not in op_enum
    assert render_calls == [
        ("render_to_image", "report.xlsx", {"workbook_page": 1})
    ]
    assert events == ["render:report.xlsx", "vision", "main"]
    assert len(stub.calls) == 1
    assert len(client.responses.calls) == 1
    request_json = json.dumps(client.responses.calls[0], sort_keys=True)
    assert image_b64 not in request_json
    assert "image_b64" not in request_json
    assert "vision_judge" not in request_json
    assert "TRUSTED_VISUAL_EVIDENCE_BEGIN" in request_json
    assert "source_sha256" in request_json
    assert "sampled_first_surface" in request_json
    assert res.verdict == "pass"
    assert res.perception_called is True
    assert res.tools_used == [
        "harness_render_to_image", "harness_vision_perception"
    ]
    assert res.tool_calls_made == 0
    assert res.main_api_call_count == 1
    assert res.perception_call_count == 1
    assert res.perception_input_tokens == 31
    assert res.perception_output_tokens == 9
    assert res.perception_cached_tokens == 3
    assert res.perception_total_latency_ms == 12.5
    assert res.render_call_count == 1
    assert res.usage_complete is True
    assert len(upstream_calls) == 1  # main; StubVision does not own a guard


def test_visual_without_perception_config_is_judge_error(
    deliverable_dir, task_and_item
):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r2-unconfigured",
        criterion="Overall Style",
        score=4, required=None,
    )
    scripted = ScriptedResponses([])
    judge = ToolCallingJudge(
        client=FakeClient(scripted), model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
    )
    result = judge.judge_item(
        task=task, item=visual_item,
        deliverable_dir=str(deliverable_dir), file_names=["report.xlsx"],
    )
    assert result.verdict == "judge_error"
    assert result.judge_error == "required_visual_perception_unconfigured"
    assert result.perception_called is False
    assert scripted.calls == []


def test_visual_render_failure_is_instrumented_judge_error(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r2-render-fail",
        criterion="Overall visual polish",
        score=4, required=None,
    )
    client = FakeClient(ScriptedResponses([]))
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: {
            "ok": False,
            "error_type": "dependency_missing",
            "error": "LibreOffice executable not found",
        },
    )

    class _NoVisionCall:
        def judge(self, **kwargs):
            raise AssertionError("vision must not run when rendering failed")

    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE,
        vision_perception=_NoVisionCall(),
    )
    result = judge.judge_item(
        task=task, item=visual_item,
        deliverable_dir=str(deliverable_dir), file_names=["report.xlsx"],
    )
    assert result.verdict == "judge_error"
    assert result.judge_error.startswith(
        "required_visual_render_failed:dependency_missing:"
    ) or result.judge_error.startswith(
        "required_visual_render_failed:report.xlsx:dependency_missing:"
    )
    assert result.perception_called is False
    assert result.tools_used == ["harness_render_to_image"]
    assert result.render_call_count == 1
    assert result.main_api_call_count == 0
    assert result.score_excluded is True
    assert client.responses.calls == []


def test_required_visual_perception_failure_is_judge_error(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r2-vision-fail",
        criterion="Overall visual polish",
        score=4, required=None,
    )
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: {
            "ok": True,
            "data": {"base64": base64.b64encode(b"not-an-image").decode()},
        },
    )

    failed_vision = StubVision(judge_error="bad_image")
    client = FakeClient(ScriptedResponses([]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE,
        vision_perception=failed_vision,
    )
    result = judge.judge_item(
        task=task, item=visual_item,
        deliverable_dir=str(deliverable_dir), file_names=["report.xlsx"],
    )
    assert result.verdict == "judge_error"
    assert result.judge_error == (
        "required_visual_perception_failed:report.xlsx:bad_image"
    )
    assert result.perception_called is True
    assert result.tools_used == [
        "harness_render_to_image", "harness_vision_perception"
    ]
    assert result.main_api_call_count == 0
    assert result.score_excluded is True
    assert client.responses.calls == []


def test_invalid_vision_verdict_is_blocked_before_main_judge(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r2-invalid-vision",
        criterion="Overall visual polish",
        score=4,
        required=None,
    )
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: {
            "ok": True,
            "data": {
                "kind": "image_png_base64",
                "source_kind": "xlsx",
                "scope": {"workbook_page": 1},
                "source_sheet_count": 1,
                "converted_page_count": 1,
                "renderer": {"converter": "libreoffice"},
                "byte_size": 5,
                "base64": "aW1hZ2U=",
            },
        },
    )

    class InvalidVision:
        call_cap = 1
        calls_used = 0

        @property
        def remaining_calls(self):
            return 1

        def judge(self, **kwargs):
            return SimpleNamespace(to_dict=lambda: {
                "verdict": "judge_error",
                "partial_score": 0.0,
                "evidence": "",
                "confidence": 0.0,
                "reasoning": "invalid",
                "judge_error": None,
                "api_call_count": 1,
                "input_tokens": 10,
                "output_tokens": 2,
                "cached_tokens": 0,
                "latency_ms": 3.0,
                "usage_complete": True,
            })

    client = FakeClient(ScriptedResponses([]))
    result = ToolCallingJudge(
        client=client,
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        vision_perception=InvalidVision(),
    ).judge_item(
        task=task,
        item=visual_item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == (
        "required_visual_perception_failed:report.xlsx:invalid_vision_envelope"
    )
    assert result.score_excluded is True
    assert result.perception_called is True
    assert result.main_api_call_count == 0
    assert client.responses.calls == []


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


def test_audio_tool_usage_is_recorded_as_perception(tmp_path, task_and_item):
    task, _ = task_and_item
    (tmp_path / "clip.wav").write_bytes(b"RIFFfake")
    item = RubricItem(
        rubric_item_id="audio-1",
        criterion="Audio voice is clear",
        score=3,
        required=None,
    )

    class StubAudio:
        def judge(self, **kwargs):
            return SimpleNamespace(
                judge_error=None,
                to_dict=lambda: {
                    "verdict": "pass", "partial_score": 1.0,
                    "evidence": "voice clearly audible", "confidence": 0.9,
                    "reasoning": "heard", "judge_error": None,
                    "api_call_count": 1, "input_tokens": 70,
                    "output_tokens": 12, "cached_tokens": 5,
                    "latency_ms": 14.0, "usage_complete": True,
                },
            )

    client = FakeClient(ScriptedResponses([
        _response(output=[_fc(
            "audio-call", "audio_judge",
            criterion=item.criterion, audio_path="clip.wav",
        )], in_tok=20, out_tok=3, cached_tok=2),
        _response(output=[_final(json.dumps({
            "verdict": "pass", "partial_score": 1.0,
            "evidence": "voice clearly audible", "confidence": 0.9,
            "reasoning": "audio evidence used",
        }))], in_tok=25, out_tok=4, cached_tok=3),
    ]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        audio_perception=StubAudio(),
    )

    result = judge.judge_item(
        task=task, item=item, deliverable_dir=str(tmp_path),
        file_names=["clip.wav"],
    )

    assert result.verdict == "pass"
    assert result.main_api_call_count == 2
    assert result.input_tokens == 45
    assert result.output_tokens == 7
    assert result.cached_tokens == 5
    assert result.perception_call_count == 1
    assert result.perception_input_tokens == 70
    assert result.perception_output_tokens == 12
    assert result.perception_cached_tokens == 5
    assert result.perception_total_latency_ms == 14.0
    assert result.perception_called is True
    assert result.usage_complete is True


def _audio_item() -> RubricItem:
    return RubricItem(
        rubric_item_id="audio-1",
        criterion="The Master track contains no vocals (instrumental-only).",
        score=2,
        required=None,
    )


class _DeafAudio:
    """A listening model that is asked and never answers."""

    def __init__(self, judge_error: str = "provider_error:BadRequestError"):
        self.judge_error = judge_error
        self.calls = 0

    def judge(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            judge_error=self.judge_error,
            to_dict=lambda: {
                "verdict": "judge_error", "partial_score": 0.0,
                "evidence": "", "confidence": 0.0,
                "reasoning": "audio call failed: BadRequestError",
                "judge_error": self.judge_error,
                "api_call_count": 1, "input_tokens": 0,
                "output_tokens": 0, "cached_tokens": 0,
                "latency_ms": 267.64, "usage_complete": False,
            },
        )


def test_a_listening_call_that_never_answers_is_not_scored_as_a_failure(
    tmp_path, task_and_item,
):
    """Taken from a real paid run, where it cost a gold deliverable six marks.

    In run ``33241377185`` the gold task ``38889c3b`` had three audio items
    come back ``verdict: "fail"``, ``awarded_score: 0.0``,
    ``score_excluded: false``, each carrying
    ``evidence: "audio call failed: BadRequestError"``. The listening model
    had been rejected with a 400 and never heard anything; the judge read a
    broken tool as an absent quality and marked the work down for it.

    Nothing about the deliverable was known at that point, so nothing about
    the deliverable may be asserted. The item is a judge error and leaves the
    score, which is what a failed visual prepass has always done.
    """
    task, _ = task_and_item
    (tmp_path / "stems.zip").write_bytes(b"PK\x03\x04fake")
    audio = _DeafAudio()

    client = FakeClient(ScriptedResponses([
        _response(output=[_fc(
            "audio-call", "audio_judge",
            criterion=_audio_item().criterion, audio_path="stems.zip",
        )], in_tok=20, out_tok=3, cached_tok=2),
        # The judge does exactly what it did in the real run: writes a
        # confident `fail` whose only evidence is the tool's error text.
        _response(output=[_final(json.dumps({
            "verdict": "fail", "partial_score": 0.0,
            "evidence": "audio call failed: BadRequestError",
            "confidence": 0.78, "reasoning": "could not verify",
        }))], in_tok=25, out_tok=4, cached_tok=3),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=audio,
    )

    result = judge.judge_item(
        task=task, item=_audio_item(), deliverable_dir=str(tmp_path),
        file_names=["stems.zip"],
    )

    assert audio.calls == 1
    assert result.verdict == "judge_error"
    assert result.judge_error == "audio_perception_failed:provider_error:BadRequestError"
    assert result.score_excluded is True
    assert result.awarded_score == 0.0
    # Still counted and still priced -- excluded from the score is not
    # excluded from the receipt.
    assert result.perception_called is True
    assert result.perception_call_count == 1
    assert result.usage_complete is False


def test_a_listening_call_the_judge_asked_wrong_stays_the_judge_s_to_fix(
    tmp_path, task_and_item,
):
    """A bad path is not a broken model, and must not end the item.

    The tool answers with the message that says what was wrong, the judge is
    meant to read it and ask again, and an item that goes on to be marked
    from other evidence keeps its mark.
    """
    task, _ = task_and_item
    (tmp_path / "stems.zip").write_bytes(b"PK\x03\x04fake")

    class _NeverReached:
        def judge(self, **kwargs):  # pragma: no cover - must not be called
            raise AssertionError("dispatch should have refused the path first")

    client = FakeClient(ScriptedResponses([
        _response(output=[_fc(
            "audio-call", "audio_judge",
            criterion=_audio_item().criterion,
            audio_path="not-in-the-allowlist.wav",
        )], in_tok=20, out_tok=3, cached_tok=2),
        _response(output=[_final(json.dumps({
            "verdict": "fail", "partial_score": 0.0,
            "evidence": "the master track has a lead vocal throughout",
            "confidence": 0.8, "reasoning": "heard elsewhere in the bundle",
        }))], in_tok=25, out_tok=4, cached_tok=3),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=_NeverReached(),
    )

    result = judge.judge_item(
        task=task, item=_audio_item(), deliverable_dir=str(tmp_path),
        file_names=["stems.zip"],
    )

    assert result.verdict == "fail"
    assert result.judge_error is None
    assert result.score_excluded is False


def test_a_listening_call_that_recovers_leaves_no_error(tmp_path, task_and_item):
    """One failed attempt does not condemn an item the run went on to hear.

    The mark depends on whether the audio was heard, not on how many tries it
    took. Excluding a recovered item would throw away a reading the run
    actually has -- and paid for.
    """
    task, _ = task_and_item
    (tmp_path / "clip.wav").write_bytes(b"RIFFfake")

    class _FlakyAudio:
        def __init__(self):
            self.calls = 0

        def judge(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return _DeafAudio("provider_error:APITimeoutError").judge()
            return SimpleNamespace(
                judge_error=None,
                to_dict=lambda: {
                    "verdict": "pass", "partial_score": 1.0,
                    "evidence": "no vocal content in the master",
                    "confidence": 0.9, "reasoning": "heard",
                    "judge_error": None, "api_call_count": 1,
                    "input_tokens": 70, "output_tokens": 12,
                    "cached_tokens": 5, "latency_ms": 14.0,
                    "usage_complete": True,
                },
            )

    audio = _FlakyAudio()
    call = _fc("audio-call", "audio_judge",
               criterion=_audio_item().criterion, audio_path="clip.wav")
    client = FakeClient(ScriptedResponses([
        _response(output=[call], in_tok=20, out_tok=3, cached_tok=2),
        _response(output=[_fc(
            "audio-call-2", "audio_judge",
            criterion=_audio_item().criterion, audio_path="clip.wav",
        )], in_tok=20, out_tok=3, cached_tok=2),
        _response(output=[_final(json.dumps({
            "verdict": "pass", "partial_score": 1.0,
            "evidence": "no vocal content in the master",
            "confidence": 0.9, "reasoning": "heard on the retry",
        }))], in_tok=25, out_tok=4, cached_tok=3),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=audio,
    )

    result = judge.judge_item(
        task=task, item=_audio_item(), deliverable_dir=str(tmp_path),
        file_names=["clip.wav"],
    )

    assert audio.calls == 2
    assert result.verdict == "pass"
    assert result.judge_error is None
    assert result.score_excluded is False
    # The failed attempt is still on the bill and still leaves the run unable
    # to say the token count is complete.
    assert result.perception_call_count == 2
    assert result.usage_complete is False


def test_model_cannot_call_render_to_image(deliverable_dir, task_and_item):
    task, item = task_and_item
    client = FakeClient(ScriptedResponses([
        _response(output=[_fc(
            "c1", "read_deliverable", op="render_to_image", path="report.xlsx"
        )]),
        _response(output=[_final(json.dumps({
            "verdict": "fail", "partial_score": 0.0,
            "evidence": "visual rendering unavailable to model",
            "confidence": 1.0, "reasoning": "harness-owned",
        }))]),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE
    )

    result = judge.judge_item(
        task=task, item=item, deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "fail"
    output = next(
        entry for entry in client.responses.calls[1]["input"]
        if entry.get("type") == "function_call_output"
    )
    assert "bad_op" in output["output"]


def test_model_read_path_must_match_exact_allowlist(deliverable_dir, task_and_item):
    task, item = task_and_item
    client = FakeClient(ScriptedResponses([
        _response(output=[_fc(
            "c1", "read_deliverable", op="read_content", path="other.xlsx"
        )]),
        _response(output=[_final(json.dumps({
            "verdict": "fail", "partial_score": 0.0,
            "evidence": "requested path was not allowlisted",
            "confidence": 1.0, "reasoning": "bad path",
        }))]),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE
    )

    judge.judge_item(
        task=task, item=item, deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"], reference_file_names=["reference.xlsx"],
    )

    output = next(
        entry for entry in client.responses.calls[1]["input"]
        if entry.get("type") == "function_call_output"
    )
    assert "bad_path" in output["output"]


def test_exact_reference_path_is_allowed(deliverable_dir, task_and_item):
    task, item = task_and_item
    (deliverable_dir / "reference.txt").write_text(
        "trusted task input", encoding="utf-8"
    )
    client = FakeClient(ScriptedResponses([
        _response(output=[_fc(
            "c1", "read_deliverable", op="read_content", path="reference.txt"
        )]),
        _response(output=[_final(json.dumps({
            "verdict": "fail", "partial_score": 0.0,
            "evidence": "candidate lacks the referenced value",
            "confidence": 0.9, "reasoning": "comparison complete",
        }))]),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE
    )

    judge.judge_item(
        task=task, item=item, deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"], reference_file_names=["reference.txt"],
    )

    output = next(
        entry for entry in client.responses.calls[1]["input"]
        if entry.get("type") == "function_call_output"
    )
    payload = json.loads(output["output"])
    assert payload["ok"] is True
    assert "trusted task input" in payload["data"]["text"]


@pytest.mark.parametrize("raw_arguments", [[], None])
def test_non_mapping_function_arguments_become_tool_error(
    deliverable_dir, task_and_item, raw_arguments
):
    task, item = task_and_item
    malformed_call = {
        "type": "function_call",
        "call_id": "c1",
        "name": "read_deliverable",
        "arguments": json.dumps(raw_arguments),
    }
    client = FakeClient(ScriptedResponses([
        _response(output=[malformed_call]),
        _response(output=[_final(json.dumps({
            "verdict": "fail", "partial_score": 0.0,
            "evidence": "tool arguments were invalid",
            "confidence": 1.0, "reasoning": "bad args",
        }))]),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE
    )

    result = judge.judge_item(
        task=task, item=item, deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "fail"
    output = next(
        entry for entry in client.responses.calls[1]["input"]
        if entry.get("type") == "function_call_output"
    )
    assert "bad_args" in output["output"]


def test_reasoning_item_is_preserved_before_function_output(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    reasoning_payload = {
        "type": "reasoning", "id": "reasoning-1",
        "summary": [{"type": "summary_text", "text": "inspect first"}],
    }

    class SDKReasoningItem:
        type = "reasoning"

        def model_dump(self, **kwargs):
            return dict(reasoning_payload)

    client = FakeClient(ScriptedResponses([
        _response(output=[
            SDKReasoningItem(),
            _fc("c1", "read_deliverable", op="inspect_structure", path="report.xlsx"),
        ]),
        _response(output=[_final(json.dumps({
            "verdict": "pass", "partial_score": 1.0,
            "evidence": "kind=xlsx", "confidence": 0.9,
            "reasoning": "inspected",
        }))]),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE
    )

    judge.judge_item(
        task=task, item=item, deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    continuation = client.responses.calls[1]["input"]
    types = [entry.get("type") for entry in continuation]
    assert types[-3:] == ["reasoning", "function_call", "function_call_output"]
    assert continuation[-3] == reasoning_payload


def test_tool_exception_becomes_function_output_error(
    deliverable_dir, task_and_item, monkeypatch
):
    task, item = task_and_item
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("tool boom")),
    )
    client = FakeClient(ScriptedResponses([
        _response(output=[_fc(
            "c1", "read_deliverable", op="read_content", path="report.xlsx"
        )]),
        _response(output=[_final(json.dumps({
            "verdict": "fail", "partial_score": 0.0,
            "evidence": "tool inspection failed", "confidence": 1.0,
            "reasoning": "tool error",
        }))]),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE
    )

    result = judge.judge_item(
        task=task, item=item, deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "fail"
    output = next(
        entry for entry in client.responses.calls[1]["input"]
        if entry.get("type") == "function_call_output"
    )
    assert "tool_exception" in output["output"]
    assert "task_execution_error:RuntimeError" in output["output"]
    assert "tool boom" not in output["output"]


def test_audio_dispatch_exception_is_class_only(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    sensitive = "https://private.services.ai.azure.com/"

    class FailingAudio:
        def judge(self, **_kwargs):
            raise RuntimeError(sensitive)

    audio = deliverable_dir / "clip.wav"
    audio.write_bytes(b"audio")
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])),
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        audio_perception=FailingAudio(),
    )

    result = judge._dispatch_tool(
        _fc(
            "a1",
            "audio_judge",
            criterion=item.criterion,
            audio_path="clip.wav",
        ),
        deliverable_dir=str(deliverable_dir),
        allowed_paths={"clip.wav"},
    )

    assert result["error"] == "provider_error:RuntimeError"
    assert sensitive not in str(result)


def test_main_api_usage_call_count_and_latency_are_exact(
    deliverable_dir, task_and_item, monkeypatch
):
    task, item = task_and_item
    ticks = iter([2.0, 2.125])
    monkeypatch.setattr(
        tool_calling_judge_module.time, "perf_counter", lambda: next(ticks)
    )
    client = FakeClient(ScriptedResponses([
        _response(
            output=[_final(json.dumps({
                "verdict": "pass", "partial_score": 1.0,
                "evidence": "alpha is present", "confidence": 0.9,
                "reasoning": "observed",
            }))],
            in_tok=41,
            out_tok=6,
            cached_tok=4,
        ),
    ]))
    guarded = []
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE,
        before_upstream_call=lambda: guarded.append("main"),
    )

    result = judge.judge_item(
        task=task, item=item, deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert guarded == ["main"]
    assert result.main_api_call_count == 1
    assert result.input_tokens == 41
    assert result.output_tokens == 6
    assert result.cached_tokens == 4
    assert result.latency_ms == 125.0
    assert result.usage_complete is True
    assert "temperature" not in client.responses.calls[0]
    assert "seed" not in client.responses.calls[0]


# ── Harness-owned visual preflight ──────────────────────────────────


def test_visual_preflight_processes_bounded_paths_in_stable_order(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r3",
        criterion="Render quality of the chart image",
        score=4, required=None,
    )

    pytest.importorskip("PIL")
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(buf, format="PNG")
    fake_b64 = base64.b64encode(buf.getvalue()).decode()

    for name in ("z.png", "a.png", "m.png"):
        (deliverable_dir / name).write_bytes(b"source-" + name.encode())
    render_order = []

    def fake_render(op, path, *, base_dir, scope=None):
        render_order.append(path)
        return {
            "ok": True,
            "data": {
                "source_kind": "image",
                "scope": {},
                "renderer": {"rasterizer": "pillow"},
                "byte_size": 64,
                "base64": fake_b64,
            },
        }

    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        fake_render,
    )
    final = _response(output=[_final(json.dumps({
        "verdict": "pass", "partial_score": 1.0,
        "evidence": "all sampled surfaces are legible",
        "confidence": 0.9, "reasoning": "ok",
        "tool_calls_made": 0,
    }))])
    client = FakeClient(ScriptedResponses([final]))
    stub = StubVision(remaining_calls=3)
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE,
                             vision_perception=stub)
    res = judge.judge_item(task=task, item=visual_item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["z.png", "a.png", "m.png"])
    assert res.verdict == "pass"
    assert render_order == ["a.png", "m.png", "z.png"]
    assert len(stub.calls) == 3
    assert res.render_call_count == 3
    assert res.perception_call_count == 3
    assert res.tool_calls_made == 0
    assert res.perception_called is True
    assert [entry["path"] for entry in res.visual_provenance] == [
        "a.png", "m.png", "z.png"
    ]
    assert set(res.visual_provenance[0]) == {
        "path", "source_sha256", "scope", "renderer_metadata",
        "coverage_metadata", "vision",
    }
    assert set(res.visual_provenance[0]["vision"]) == {
        "verdict", "evidence", "confidence", "reasoning", "judge_error",
    }
    assert "base64" not in json.dumps(res.visual_provenance)
    assert str(deliverable_dir) not in json.dumps(res.visual_provenance)
    prompt = client.responses.calls[0]["input"][0]["content"]
    assert prompt.index('"path": "a.png"') < prompt.index(
        '"path": "m.png"'
    ) < prompt.index('"path": "z.png"')


def test_visual_preflight_filters_unsupported_bundle_paths(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r-bundle",
        criterion="The organizational chart layout is readable",
        score=4,
        required=None,
    )
    # .csv, not .docx: documents render now, so a docx here would no longer
    # be the unsupported case this test exists to cover.
    (deliverable_dir / "Notes.csv").write_bytes(b"header_a,header_b\n1,2\n")
    (deliverable_dir / "Chart.pdf").write_bytes(b"pdf")

    pytest.importorskip("PIL")
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color="blue").save(buf, format="PNG")
    fake_b64 = base64.b64encode(buf.getvalue()).decode()
    render_order = []

    def fake_render(op, path, *, base_dir, scope=None):
        render_order.append(path)
        source_kind = Path(path).suffix.lower().lstrip(".")
        data = {
            "source_kind": source_kind,
            "scope": scope or {},
            "renderer": {
                "converter": "libreoffice",
                "rasterizer": "pymupdf",
                "libreoffice_binary": "soffice",
                "libreoffice_version": "LibreOffice 24.2.7.2",
                "pymupdf_version": "1.28.0",
            },
            "byte_size": 64,
            "base64": fake_b64,
        }
        if source_kind == "pdf":
            data["source_page_count"] = 1
        else:
            data["source_sheet_count"] = 1
            data["converted_page_count"] = 1
        return {"ok": True, "data": data}

    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        fake_render,
    )
    final = _response(output=[_final(json.dumps({
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "the chart tiers are readable",
        "confidence": 0.9,
        "reasoning": "ok",
    }))])
    client = FakeClient(ScriptedResponses([final]))
    vision = StubVision(remaining_calls=2)
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        vision_perception=vision,
    )

    result = judge.judge_item(
        task=task,
        item=visual_item,
        deliverable_dir=str(deliverable_dir),
        file_names=["Notes.csv", "Chart.pdf", "report.xlsx"],
    )

    assert result.verdict == "pass"
    assert render_order == ["Chart.pdf", "report.xlsx"]
    assert result.render_call_count == result.perception_call_count == 2
    assert [entry["path"] for entry in result.visual_provenance] == [
        "Chart.pdf",
        "report.xlsx",
    ]
    # Unrenderable, but still named to the model so it knows what was there.
    assert "Notes.csv" in client.responses.calls[0]["input"][0]["content"]


def test_visual_file_cap_fails_before_render_vision_or_main(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    names = [f"{chr(ord('a') + index)}.png" for index in range(11)]
    for name in names:
        (deliverable_dir / name).write_bytes(b"source")
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("render must not start"),
    )
    vision = StubVision(remaining_calls=5)
    client = FakeClient(ScriptedResponses([]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        vision_perception=vision,
    )

    result = judge.judge_item(
        task=task,
        item=RubricItem("r-file-cap", "Overall Style", 4, None),
        deliverable_dir=str(deliverable_dir),
        file_names=names,
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == (
        "required_visual_file_cap_exceeded:planned=11,cap=10"
    )
    assert result.score_excluded is True
    assert result.render_call_count == 0
    assert result.perception_call_count == 0
    assert result.main_api_call_count == 0
    assert vision.calls == []
    assert client.responses.calls == []


def test_visual_file_cap_comes_from_the_grading_config(
    deliverable_dir, task_and_item, monkeypatch
):
    """The cap in force is a config value, and it is the one enforced.

    It used to be a constant in this module, which meant a run's grade file
    recorded no trace of the cap it graded under. A judge constructed with a
    different cap has to actually use it, or the value in provenance is
    decoration.
    """
    task, _ = task_and_item
    names = ["a.png", "b.png", "c.png", "d.png"]
    for name in names:
        (deliverable_dir / name).write_bytes(b"source")
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("render must not start"),
    )
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])),
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        vision_perception=StubVision(remaining_calls=5),
        visual_file_cap=3,
    )

    result = judge.judge_item(
        task=task,
        item=RubricItem("r-file-cap", "Overall Style", 4, None),
        deliverable_dir=str(deliverable_dir),
        file_names=names,
    )

    assert result.judge_error == (
        "required_visual_file_cap_exceeded:planned=4,cap=3"
    )


@pytest.mark.parametrize(
    "visual, expected",
    [
        ({}, 10),
        ({"model": "gpt-5.4"}, 10),
        # ``file_cap_per_item:`` with nothing after it is how YAML spells a key
        # someone started and did not finish. It reads back as None, which is
        # indistinguishable from the key being absent, so it takes the default
        # rather than failing a dispatch over a blank line.
        ({"file_cap_per_item": None}, 10),
        ({"file_cap_per_item": 3}, 3),
        ({"file_cap_per_item": 25}, 25),
    ],
)
def test_resolve_visual_file_cap_reads_the_perception_block(visual, expected):
    assert resolve_visual_file_cap({"perception": {"visual": visual}}) == expected


@pytest.mark.parametrize("judge_config", [{}, {"perception": {}}, {"perception": {"visual": {}}}])
def test_resolve_visual_file_cap_tolerates_a_missing_perception_block(judge_config):
    assert resolve_visual_file_cap(judge_config) == 10


@pytest.mark.parametrize("bad", [0, -1, 2.5, "3", True])
def test_resolve_visual_file_cap_rejects_a_cap_that_is_not_a_positive_int(bad):
    # True is here on purpose: bool is an int subclass, so an unguarded check
    # would resolve ``file_cap_per_item: true`` to a cap of one file.
    with pytest.raises(ValueError, match="file_cap_per_item"):
        resolve_visual_file_cap(
            {"perception": {"visual": {"file_cap_per_item": bad}}}
        )


@pytest.mark.parametrize(
    ("source_kind", "render_data", "expected_total"),
    [
        ("pdf", {"source_page_count": 9}, 9),
        ("pptx", {"source_slide_count": 12}, 12),
        ("xlsx", {"converted_page_count": 4}, 4),
        ("docx", {"converted_page_count": 3}, 3),
        ("image", {}, 1),
    ],
)
def test_coverage_reports_how_many_surfaces_the_sample_came_from(
    source_kind, render_data, expected_total
):
    """``sampled_first_surface`` only means something beside a total.

    Page 1 of a one-page memo is the whole deliverable; page 1 of a
    forty-page report is 2.5% of it, and an "overall style" verdict drawn
    from it deserves to be read differently. The judge is shown this
    metadata, so a missing total is not merely unrecorded -- it tells the
    model the length is unknown.

    `#189` added the .docx branch without adding it here, so every rendered
    document claimed an unknown length while a workbook, whose count comes
    from the very same LibreOffice conversion, reported one.
    """
    coverage = ToolCallingJudge._coverage_metadata(
        RubricItem("r-coverage", "Overall Style", 4, None),
        {"source_kind": source_kind, **render_data},
    )

    assert coverage["coverage_mode"] == "sampled_first_surface"
    assert coverage["sampled_surface_count"] == 1
    assert coverage["total_surface_count"] == expected_total


def test_every_rendered_kind_says_where_its_surface_count_comes_from():
    """Two hand-kept lists, one owner: whatever the renderer can emit.

    An absent kind degrades silently -- ``.get`` returns None and the judge
    is told the deliverable's length is unknown -- so nothing fails and the
    loss only surfaces in the grades. Deriving the expectation from the
    renderer is what makes the next added kind fail here instead.
    """
    from core.tools.read_deliverable import _EXT_KIND

    renderable = {
        _EXT_KIND[suffix]
        for suffix in tool_calling_judge_module._VISUAL_RENDER_SCOPES
    }
    declared = set(tool_calling_judge_module._TOTAL_SURFACE_KEYS)

    assert renderable <= declared, (
        f"rendered {sorted(renderable - declared)} would report an unknown "
        "surface count"
    )


def test_visual_cap_preflight_fails_before_render_vision_or_main(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    for name in ("a.png", "b.png"):
        (deliverable_dir / name).write_bytes(b"source")
    visual_item = RubricItem(
        rubric_item_id="r-cap",
        criterion="Overall Style",
        score=4,
        required=None,
    )
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: pytest.fail("render must not start"),
    )
    vision = StubVision(remaining_calls=1)
    client = FakeClient(ScriptedResponses([]))
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        vision_perception=vision,
    )

    result = judge.judge_item(
        task=task,
        item=visual_item,
        deliverable_dir=str(deliverable_dir),
        file_names=["b.png", "a.png"],
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == (
        "required_visual_cap_preflight_failed:planned=2,remaining=1"
    )
    assert result.render_call_count == 0
    assert result.perception_call_count == 0
    assert result.main_api_call_count == 0
    assert vision.calls == []
    assert client.responses.calls == []


def test_visual_preflight_records_exact_render_latency(monkeypatch, tmp_path):
    (tmp_path / "chart.png").write_bytes(b"source")
    ticks = iter([4.0, 4.05])
    monkeypatch.setattr(
        tool_calling_judge_module.time, "perf_counter", lambda: next(ticks)
    )
    monkeypatch.setattr(
        tool_calling_judge_module,
        "read_deliverable",
        lambda *args, **kwargs: {
            "ok": True,
            "data": {
                "source_kind": "image", "scope": {},
                "renderer": {"rasterizer": "pillow"},
                "byte_size": 8, "base64": "aW1hZ2U=",
            },
        },
    )
    item = RubricItem(
        rubric_item_id="visual-latency",
        criterion="Overall Style",
        score=4,
        required=None,
    )
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])),
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        vision_perception=StubVision(),
    )

    prepass = judge.preflight_visual(
        item=item, deliverable_dir=str(tmp_path), file_names=["chart.png"]
    )

    assert prepass.judge_error is None
    assert prepass.render_call_count == 1
    assert prepass.render_total_latency_ms == pytest.approx(50.0)


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
    judge = ToolCallingJudge(
        client=client,
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=0,
    )
    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(deliverable_dir),
                           file_names=["report.xlsx"])
    assert res.verdict == "judge_error"
    assert res.judge_error == "final_json_parse_failed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("partial_score", "not-a-number"),
        ("partial_score", {"value": 1}),
        ("partial_score", True),
        ("partial_score", 10 ** 1000),
        ("partial_score", float("inf")),
        ("confidence", "high"),
        ("confidence", {"value": 0.9}),
        ("confidence", True),
        ("confidence", None),
        ("confidence", 2.0),
        ("confidence", float("nan")),
    ],
)
def test_invalid_numeric_final_envelope_is_score_excluded_judge_error(
    deliverable_dir, task_and_item, field, value
):
    task, item = task_and_item
    payload = {
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "alpha is present",
        "confidence": 0.9,
        "reasoning": "observed",
    }
    payload[field] = value
    client = FakeClient(ScriptedResponses([
        _response(
            output=[_final(json.dumps(payload))],
            in_tok=41,
            out_tok=6,
            cached_tok=4,
        )
    ]))

    result = ToolCallingJudge(
        client=client,
        model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=0,
    ).judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == "invalid_final_envelope"
    assert result.score_excluded is True
    assert result.main_api_call_count == 1
    assert result.input_tokens == 41
    assert result.output_tokens == 6
    assert result.cached_tokens == 4


def test_missing_confidence_is_invalid_final_envelope(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    payload = {
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "alpha is present",
        "reasoning": "observed",
    }
    client = FakeClient(ScriptedResponses([
        _response(output=[_final(json.dumps(payload))], in_tok=9, out_tok=2)
    ]))

    result = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE,
        finalization_retries=0,
    ).judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == "invalid_final_envelope"
    assert result.score_excluded is True
    assert result.input_tokens == 9
    assert result.output_tokens == 2


def test_five_thousand_digit_json_integer_is_invalid_not_an_exception(
    deliverable_dir, task_and_item
):
    task, item = task_and_item
    raw = (
        '{"verdict":"pass","partial_score":'
        + ("9" * 5000)
        + ',"evidence":"alpha","confidence":0.9,"reasoning":"observed"}'
    )
    client = FakeClient(ScriptedResponses([
        _response(output=[_final(raw)], in_tok=13, out_tok=5, cached_tok=1)
    ]))

    result = ToolCallingJudge(
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE,
        finalization_retries=0,
    ).judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "judge_error"
    assert result.judge_error == "invalid_final_envelope"
    assert result.score_excluded is True
    assert result.input_tokens == 13
    assert result.output_tokens == 5
    assert result.cached_tokens == 1


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


# ── audio_judge can reach a stem inside an archive ───────────────────
#
# The one stage-1 task made entirely of music ships its whole deliverable as a
# single ``.zip`` of stems. Without ``member`` the listening model can only be
# handed the archive itself, which is not a thing it can hear, so every
# listening criterion on that task had to be answered some other way.

class _RecordingAudio:
    """Remembers the path it was handed and whether it still exists."""

    def __init__(self):
        self.paths: list[str] = []
        self.existed: list[bool] = []
        self.bytes_seen: list[bytes] = []

    def judge(self, *, criterion: str, audio_path: str):
        self.paths.append(audio_path)
        self.existed.append(Path(audio_path).is_file())
        self.bytes_seen.append(Path(audio_path).read_bytes())
        return SimpleNamespace(
            judge_error=None,
            to_dict=lambda: {"verdict": "pass", "partial_score": 1.0},
        )


def _stems_archive(base_dir: Path, name: str = "stems.zip") -> Path:
    import zipfile

    archive = base_dir / name
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Master.wav", b"RIFF....WAVEfmt master")
        zf.writestr("Bass.wav", b"RIFF....WAVEfmt bass")
        zf.writestr("notes.txt", b"session notes")
    return archive


def _audio_judge(judge, deliverable_dir, **kwargs):
    return judge._dispatch_tool(
        _fc("a1", "audio_judge", **kwargs),
        deliverable_dir=str(deliverable_dir),
        allowed_paths={kwargs["audio_path"]},
    )


def test_naming_a_member_hands_over_the_stem_and_not_the_archive(
    deliverable_dir, task_and_item
):
    _stems_archive(deliverable_dir)
    audio = _RecordingAudio()
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])), model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=audio,
    )

    result = _audio_judge(
        judge, deliverable_dir,
        criterion="The Master track contains no vocals.",
        audio_path="stems.zip", member="Master.wav",
    )

    assert result["ok"] is True
    assert audio.bytes_seen == [b"RIFF....WAVEfmt master"]
    # It got a real file on disk, not a handle or a buffer.
    assert audio.existed == [True]
    assert audio.paths[0].endswith(".wav")


def test_the_extracted_stem_does_not_outlive_the_call(
    deliverable_dir, task_and_item
):
    """Two 180 MB archives per task is why this is a context manager."""
    _stems_archive(deliverable_dir)
    audio = _RecordingAudio()
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])), model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=audio,
    )

    _audio_judge(
        judge, deliverable_dir, criterion="c",
        audio_path="stems.zip", member="Bass.wav",
    )

    assert not Path(audio.paths[0]).exists()


def test_omitting_member_still_hands_over_the_file_itself(
    deliverable_dir, task_and_item
):
    (deliverable_dir / "clip.wav").write_bytes(b"RIFF....WAVEfmt clip")
    audio = _RecordingAudio()
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])), model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=audio,
    )

    result = _audio_judge(
        judge, deliverable_dir, criterion="c", audio_path="clip.wav",
    )

    assert result["ok"] is True
    assert audio.paths == [str(deliverable_dir / "clip.wav")]


def test_a_null_member_is_the_same_as_none_at_all(
    deliverable_dir, task_and_item
):
    """The schema types ``member`` nullable, so a model may send ``null``."""
    (deliverable_dir / "clip.wav").write_bytes(b"RIFF....WAVEfmt clip")
    audio = _RecordingAudio()
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])), model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=audio,
    )

    result = _audio_judge(
        judge, deliverable_dir, criterion="c",
        audio_path="clip.wav", member=None,
    )

    assert result["ok"] is True
    assert audio.paths == [str(deliverable_dir / "clip.wav")]


def test_an_unknown_member_is_told_what_the_archive_holds(
    deliverable_dir, task_and_item
):
    """The judge's own mistake to correct, so it gets a usable message.

    ``public_task_error_text`` would return ``code:type`` and strip exactly
    the member list that lets the next call succeed. ``read_deliverable``
    surfaces ``str(exc)`` for the identical mistake made through ``scope``.
    """
    _stems_archive(deliverable_dir)
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])), model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=_RecordingAudio(),
    )

    result = _audio_judge(
        judge, deliverable_dir, criterion="c",
        audio_path="stems.zip", member="Vocals.wav",
    )

    assert result["ok"] is False
    assert result["error_type"] == "bad_scope"
    assert "Master.wav" in result["error"]


def test_a_member_that_is_not_a_string_is_a_bad_argument(
    deliverable_dir, task_and_item
):
    _stems_archive(deliverable_dir)
    audio = _RecordingAudio()
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])), model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=audio,
    )

    result = _audio_judge(
        judge, deliverable_dir, criterion="c",
        audio_path="stems.zip", member=17,
    )

    assert result["ok"] is False
    assert result["error_type"] == "bad_args"
    assert audio.paths == []


def test_member_cannot_be_used_to_reach_outside_the_allowlist(
    deliverable_dir, task_and_item
):
    """The archive is still checked against the allowlist before extraction."""
    _stems_archive(deliverable_dir)
    audio = _RecordingAudio()
    judge = ToolCallingJudge(
        client=FakeClient(ScriptedResponses([])), model="gpt-5.4",
        prompt_template=PROMPT_TEMPLATE, audio_perception=audio,
    )

    result = judge._dispatch_tool(
        _fc("a1", "audio_judge", criterion="c",
            audio_path="stems.zip", member="Master.wav"),
        deliverable_dir=str(deliverable_dir),
        allowed_paths={"other.wav"},
    )

    assert result["ok"] is False
    assert audio.paths == []


def test_the_schema_offers_member_without_demanding_it():
    schema = ToolCallingJudge._audio_tool_schema()
    params = schema["parameters"]

    assert "member" in params["properties"]
    assert params["required"] == ["criterion", "audio_path"]
    # Nullable, because ``additionalProperties: False`` plus a non-nullable
    # optional is how a model ends up unable to say "the whole file".
    assert params["properties"]["member"]["type"] == ["string", "null"]
