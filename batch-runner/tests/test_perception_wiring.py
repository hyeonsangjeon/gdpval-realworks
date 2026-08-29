"""PR3 (0531) — perception wiring + runtime instrumentation.

Proves at runtime (not by config inspection) that:
  1. A v2 config with judge.perception.{visual,audio} causes Grader to
     instantiate and inject VisionPerception/AudioPerception into the
     ToolCallingJudge (previously left None -> dead config).
  2. The harness renders and invokes vision before the main VISUAL request,
      while the main model receives neither a vision tool nor image bytes.
  3. A v2 config WITHOUT a perception block leaves the sub-judges None.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(text: str) -> dict:
    return {"type": "message", "content": [{"type": "output_text", "text": text}]}


def _fc(name: str, args: dict, call_id: str = "c1") -> dict:
    return {"type": "function_call", "name": name,
            "arguments": json.dumps(args), "call_id": call_id}


def _response(*, output, in_tok=50, out_tok=10):
    return SimpleNamespace(
        output=output,
        output_text="",
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok,
                              input_tokens_details=SimpleNamespace(cached_tokens=0)),
    )


class ScriptedResponses:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)


class FakeVision:
    """Stand-in VisionPerception with the same surface the judge calls."""

    def __init__(self):
        self.calls = 0
        self.reset_count = 0
        self.remaining_calls = 5

    def reset(self):
        self.reset_count += 1

    def judge(self, *, criterion, image_b64, cache_key=None):
        self.calls += 1
        return SimpleNamespace(
            judge_error=None,
            to_dict=lambda: {
                "verdict": "pass", "partial_score": 1.0,
                "evidence": "chart has titled axes", "confidence": 0.9,
                "reasoning": "looks good", "judge_error": None,
                "api_call_count": 1, "input_tokens": 20,
                "output_tokens": 5, "cached_tokens": 2,
                "latency_ms": 10.0, "usage_complete": True,
            },
        )


# ---------------------------------------------------------------------------
# 1. Grader wires perception from config
# ---------------------------------------------------------------------------

def _v2_cfg(with_perception: bool) -> dict:
    import core.grader as grader_mod
    prompt_v1 = (Path(grader_mod.__file__).resolve().parent.parent
                 / "prompts" / "grader_judge.md")
    judge = {
        "provider": "azure_openai",
        "api_version": "2025-04-01-preview",
        "model": "gpt-5.4",
        "reasoning": {"effort": "medium"},
        "generation": {"max_output_tokens": 2400},
        "tools": {"read_deliverable": {
            "ops": ["inspect_structure", "read_content", "inspect_formatting",
                    "probe_audio", "probe_video"],
            "per_item_call_cap": 8, "max_iterations": 6}},
    }
    if with_perception:
        judge["perception"] = {
            "visual": {"model": "gpt-5.4", "vision": True, "call_cap_per_task": 5},
            "audio": {"model": "gpt-audio-1.5", "call_cap_per_task": 3,
                      "trim_seconds": 30, "endpoint_env": "AZURE_AUDIO_ENDPOINT"},
        }
    return {
        "schema_version": "2.0",
        "judge": judge,
        "prompt": {"template": str(prompt_v1)},
        "grader": {"evidence_max_chars": 200},
        "tpm_guard": {},
    }


def test_grader_wires_perception_subjudges():
    from core.grader import Grader

    fake_client = SimpleNamespace(responses=ScriptedResponses([]))

    config = _v2_cfg(with_perception=True)
    config["_runtime"] = {
        "experiment_id": "exp003_GPT52Chat_baseline_runner_exec",
        "rubric_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
    }
    grader = Grader(config, rubric_loader=None, client=fake_client)
    tj = grader._tool_judge
    assert tj is not None
    assert tj.vision_perception is not None, "VisionPerception must be wired"
    assert tj.audio_perception is not None, "AudioPerception must be wired"
    # Sub-judges share the grader's Azure client.
    assert tj.vision_perception.client is fake_client
    assert tj.audio_perception.client is fake_client
    assert tj.vision_perception.deployment == "gpt-5.4"
    assert tj.audio_perception.deployment == "gpt-audio-1.5"
    assert getattr(tj.before_upstream_call, "__self__", None) is grader
    assert getattr(
        tj.vision_perception.before_upstream_call, "__self__", None
    ) is grader
    # Audio too, and this line is the one that was missing. The three readers
    # share one client and therefore one token-per-minute allowance, so a
    # spacer two of them honour paces nothing. It went unnoticed because a
    # mistyped content part meant no audio request ever reached a model.
    assert getattr(
        tj.audio_perception.before_upstream_call, "__self__", None
    ) is grader
    raw_cache_key = json.dumps(
        (
            "exp003_GPT52Chat_baseline_runner_exec",
            "gpt-5.4",
            "11e7900cdcac61bc4daf59e65feb238acda98fbf",
            "v2.2",
        ),
        separators=(",", ":"),
    )
    assert len(raw_cache_key) > 64
    assert tj.prompt_cache_key == hashlib.sha256(
        raw_cache_key.encode("utf-8")
    ).hexdigest()
    assert len(tj.prompt_cache_key) == 64
    assert tj.finalization_retries == 1
    assert grader.prompt_version == "v2.2"


def test_grader_no_perception_block_leaves_subjudges_none():
    from core.grader import Grader

    fake_client = SimpleNamespace(responses=ScriptedResponses([]))

    grader = Grader(
        _v2_cfg(with_perception=False),
        rubric_loader=None,
        client=fake_client,
    )
    tj = grader._tool_judge
    assert tj is not None
    assert tj.vision_perception is None
    assert tj.audio_perception is None


# ---------------------------------------------------------------------------
# 2. Instrumentation records a real harness visual prepass
# ---------------------------------------------------------------------------

def test_harness_visual_prepass_sets_perception_instrumentation(
    monkeypatch, tmp_path
):
    from core.tool_calling_judge import ToolCallingJudge
    import core.tool_calling_judge as tool_judge_mod
    from core.rubric_loader import RubricItem, TaskRubric

    final = json.dumps({"verdict": "pass", "partial_score": 1.0,
                        "evidence": "chart titled axes present",
                        "confidence": 0.9, "reasoning": "ok"})
    client = SimpleNamespace(responses=ScriptedResponses([
        _response(output=[_msg(final)]),
    ]))
    (tmp_path / "chart.png").write_bytes(b"source image")
    monkeypatch.setattr(
        tool_judge_mod,
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
    fake_vision = FakeVision()
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4",
        prompt_template="grade {{criterion}}",
        vision_perception=fake_vision,
    )
    item = RubricItem(rubric_item_id="r1",
                      criterion="Overall chart visual appearance and color",
                      score=5, required=None)
    task = TaskRubric(task_id="t1", sector="Info", occupation="Analyst",
                      prompt="x", rubric_items=[item], rubric_pretty="",
                      reference_files=[], gold_deliverable_files=[])

    res = judge.judge_item(task=task, item=item,
                           deliverable_dir=str(tmp_path), file_names=["chart.png"])

    assert res.routing_modality == "visual"
    assert res.perception_called is True
    assert res.tools_used == [
        "harness_render_to_image", "harness_vision_perception"
    ]
    assert fake_vision.calls == 1
    assert res.verdict == "pass"
    assert res.perception_call_count == 1
    assert res.render_call_count == 1
    request = client.responses.calls[0]
    assert [tool["name"] for tool in request["tools"]] == ["read_deliverable"]
    assert "vision_judge" not in json.dumps(request)
    assert "image_b64" not in json.dumps(request)


def test_text_item_has_no_perception_call():
    from core.tool_calling_judge import ToolCallingJudge
    from core.rubric_loader import RubricItem, TaskRubric

    final = json.dumps({"verdict": "pass", "partial_score": 1.0,
                        "evidence": "value 42 present", "confidence": 0.9,
                        "reasoning": "ok"})
    client = SimpleNamespace(responses=ScriptedResponses([
        _response(output=[_msg(final)]),
    ]))
    judge = ToolCallingJudge(
        client=client, model="gpt-5.4",
        prompt_template="grade {{criterion}}",
        vision_perception=FakeVision(),
    )
    item = RubricItem(rubric_item_id="r1",
                      criterion="The total revenue equals 42",
                      score=5, required=None)
    task = TaskRubric(task_id="t1", sector="Info", occupation="Analyst",
                      prompt="x", rubric_items=[item], rubric_pretty="",
                      reference_files=[], gold_deliverable_files=[])

    res = judge.judge_item(task=task, item=item,
                           deliverable_dir="/tmp", file_names=["out.csv"])
    assert res.routing_modality == "text"
    assert res.perception_called is False
    assert "vision_judge" not in res.tools_used


def test_reset_perception_resets_subjudges():
    from core.tool_calling_judge import ToolCallingJudge

    fv = FakeVision()
    judge = ToolCallingJudge(
        client=SimpleNamespace(responses=ScriptedResponses([])),
        model="gpt-5.4", prompt_template="x",
        vision_perception=fv,
    )
    judge.reset_perception()
    judge.reset_perception()
    assert fv.reset_count == 2
