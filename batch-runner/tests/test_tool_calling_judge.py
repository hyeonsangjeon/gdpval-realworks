"""Tests for ``core.tool_calling_judge.ToolCallingJudge`` (PR2 task 203)."""

from __future__ import annotations

import base64
import hashlib
import importlib
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
              cached_tok: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        output=output or [],
        output_text=output_text,
        usage=_usage(in_tok, out_tok, cached_tok),
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


def test_visual_preflight_runs_before_main_without_vision_tool_or_base64(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    visual_item = RubricItem(
        rubric_item_id="r2",
        criterion="Chart formatting is clean and colors are legible",
        score=4, required=None,
    )
    PIL = pytest.importorskip("PIL")
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
    assert "tool boom" in output["output"]


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

    PIL = pytest.importorskip("PIL")
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


def test_visual_file_cap_fails_before_render_vision_or_main(
    deliverable_dir, task_and_item, monkeypatch
):
    task, _ = task_and_item
    names = ["a.png", "b.png", "c.png", "d.png"]
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
        "required_visual_file_cap_exceeded:planned=4,cap=3"
    )
    assert result.score_excluded is True
    assert result.render_call_count == 0
    assert result.perception_call_count == 0
    assert result.main_api_call_count == 0
    assert vision.calls == []
    assert client.responses.calls == []


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
    judge = ToolCallingJudge(client=client, model="gpt-5.4",
                             prompt_template=PROMPT_TEMPLATE)
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
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE
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
        client=client, model="gpt-5.4", prompt_template=PROMPT_TEMPLATE
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
