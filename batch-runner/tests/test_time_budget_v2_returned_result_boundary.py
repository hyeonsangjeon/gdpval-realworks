"""Real typed voice/consumer/backend/capture; local kernel state is synthetic."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from openai.types.responses import Response, ResponseFunctionToolCall

from core import agentic_v2_model_voice, agentic_v2_runner, azure_ai_clients
from core.agentic_v2_provenance import (
    verify_agentic_v2_failure_result,
    verify_agentic_v2_result,
)
from core.result_fingerprint import validate_inference_result_fingerprint
from gpt54_prepared_input_attestation import _identity
from .test_time_budget_first_v2_observation import (
    _case, _transport, dual_roots, entry, handoff_source_seed,
    handoff_sources, observation_kernel, offline,
)


@pytest.mark.parametrize("ending", ["finalize", "refused_finalize"])
def test_time_budget_v2_real_voice_returned_result(handoff_sources, tmp_path, monkeypatch, capsys, ending):
    """A typed write/finalize loop must preserve its canonical success or failure."""
    case = _case(handoff_sources, tmp_path)
    effects = _transport(monkeypatch, case)
    transport = azure_ai_clients.OpenAI
    original_create = transport.create
    original_run = agentic_v2_runner.AgenticV2ScriptedRunner.run
    original_capture = entry._capture
    typed, raw_runner, at_capture = [], [], []

    def create(client, **kwargs):
        # Keep the existing route/auth isolation and request assertions. Only
        # the ordinary Responses seam changes: use real SDK response types.
        response = original_create(client, **kwargs)
        call = dict(response.output[0])
        if len(effects.requests) == 2 and ending == "refused_finalize":
            arguments = json.loads(call["arguments"])
            arguments["deliverables"] = ["missing-synthetic-output.txt"]
            call["arguments"] = json.dumps(arguments)
        value = Response.model_validate({
            "id": "synthetic-response-" + str(len(effects.requests)),
            "created_at": 0, "object": "response", "status": "completed",
            "model": response.model, "parallel_tool_calls": False,
            "tool_choice": "auto", "tools": [], "output": [call],
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                "input_tokens_details": {"cached_tokens": 5, "cache_write_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 3},
            },
        })
        assert type(value) is Response and type(value.output[0]) is ResponseFunctionToolCall
        typed.append(value)
        return value

    def run(runner, **kwargs):
        value = original_run(runner, **kwargs)
        raw_runner.append(deepcopy(value))
        return value

    def capture(raw, *args):
        at_capture.append((deepcopy(raw), args))
        return original_capture(raw, *args)

    assert entry.AzureFoundryVoice is agentic_v2_model_voice.AzureFoundryVoice
    monkeypatch.setattr(transport, "create", create)
    monkeypatch.setattr(agentic_v2_runner.AgenticV2ScriptedRunner, "run", run)
    monkeypatch.setattr(entry, "_capture", capture)
    returned = entry.run_first_v2_observation(handoff_sources.plan, **case.arguments)
    data = Path(returned["result_path"]).read_bytes()
    payload = json.loads(data)
    assert _identity(data) == returned["result_identity"]
    assert validate_inference_result_fingerprint(payload) == returned["result_fingerprint"]
    assert len(raw_runner) == len(at_capture) == len(effects.runners) == len(effects.controls) == 1
    raw, (consumed, capture_arguments), row = raw_runner[0], at_capture[0], payload["results"][0]

    # Exact faithful replay, not merely "a second call happened": the returned
    # call arguments and actual backend answer must keep their pairing.
    assert len(effects.requests) == len(typed) == 2
    assert [value.output[0].name for value in typed] == ["workspace_apply", "finalize"]
    first, second = typed[0].output[0], typed[1].output[0]
    replay = effects.requests[1]["input"]
    assert len(replay) == 3 and replay[0] == effects.requests[0]["input"][0]
    assert replay[1] == {
        "type": "function_call", "call_id": first.call_id,
        "name": first.name,
        "arguments": json.dumps(json.loads(first.arguments), sort_keys=True, separators=(",", ":")),
    }
    assert set(replay[2]) == {"type", "call_id", "output"}
    assert replay[2]["type"] == "function_call_output" and replay[2]["call_id"] == first.call_id
    events = raw["agentic_v2"]["private_audit"]["events"]
    tools = [event["payload"] for event in events if event["kind"] == "tool_result"]
    assert len(tools) == 2
    assert [tool["request"]["name"] for tool in tools] == ["workspace_apply", "finalize"]
    assert [tool["request"]["call_id"] for tool in tools] == [first.call_id, second.call_id]
    assert json.loads(replay[2]["output"]) == {
        "call_id": first.call_id, "tool": first.name, "ok": True, "error_type": None,
        "result": tools[0]["result"]["data"],
    }
    assert tools[0]["request"]["arguments"] == json.loads(first.arguments)
    assert tools[1]["request"]["arguments"] == json.loads(second.arguments)

    control = effects.controls[0]
    assert payload["time_budget_observation"] == control.as_record()
    assert control.first_start == 2600 and control.cleanup_complete is True
    assert control.as_record()["host_reusable"] is True
    assert control.cleanup_deadline - control.terminal_at == 20
    assert control.as_record()["remote_cancellation_confirmed"] is False
    assert effects.events.count("provider_close") == effects.events.count("credential_close") == 1
    assert row["task_id"] == case.arguments["observation"].task_id
    assert row["retried"] is False and row["resume_round"] is None
    assert row["usage"] == {"input_tokens": 50, "output_tokens": 25}
    available = row["observability"]["usage_availability"]
    assert available["client_construction_attempts"] == 1
    assert available["responses_create_invocations"] == available["completed_responses"] == 2
    assert available["usage_complete"] is True
    assert available["native_model_attempts"] is available["repeated_request_count"] is available["written_tokens"] is None
    assert available["money_hard_cap"] is False and available["cached_and_reasoning_tokens_are_subsets"] is True
    assert all(call["model_binding"] == "matched" and call["response_returned"] is True
               and call["usage"]["cached_input_tokens"] == 5 and call["usage"]["reasoning_output_tokens"] == 3
               for call in available["response_records"])
    assert payload["observation_execution"]["runtime_source"] == case.marker["runtime_source"]
    assert payload["observation_execution"]["frozen_grader"] == case.marker["frozen_grader"]
    assert payload["observation_execution"]["inputs"] == case.marker["inputs"]
    assert returned["grading_performed"] is returned["upload_performed"] is False

    if ending == "finalize":
        verify_agentic_v2_result(raw)
        assert {key: consumed[key] for key in raw} == raw
        assert row["status"] == returned["status"] == "success" and row["error"] is None
        assert control.terminal_reason == "completed"
        assert row["observability"]["runner_success"] is True
        assert row["observability"]["runner_result_verified"] is True
        assert row["deliverable_file_records"] == [{
            "path": f"deliverable_files/{row['task_id']}/report.txt",
            **_identity(b"Explicitly synthetic output.\n"),
        }]
        assert (case.arguments["destination"] / "upload" / row["deliverable_files"][0]).read_bytes() == b"Explicitly synthetic output.\n"
    else:
        verify_agentic_v2_failure_result(raw)
        verify_agentic_v2_failure_result({key: consumed[key] for key in raw})
        assert {key: consumed[key] for key in raw} == raw
        assert raw["error"] == consumed["error"] == row["error"] == "artifact_not_openable"
        assert row["observability"]["runner_error"] == "artifact_not_openable"
        assert row["observability"]["runner_success"] is False
        assert row["observability"]["runner_result_verified"] is True
        assert row["status"] == returned["status"] == "error" and control.terminal_reason == "failed"
        assert row["content"] == row["deliverable_text"] == ""
        assert row["deliverable_files"] == row["deliverable_file_records"] == []
        assert row["observability"]["required_deliverable_missing"] is True

        # Keeping a code cannot make a forged receipt or success flag verify.
        # These are pure validation checks, not additional observation attempts.
        for corruption in ("audit", "success"):
            invalid = deepcopy(consumed)
            if corruption == "audit":
                invalid["agentic_v2"]["trace_pair_sha256"] = "0" * 64
            else:
                invalid["success"] = True
            with pytest.raises(ValueError):
                verify_agentic_v2_failure_result({key: invalid[key] for key in raw})
            rejected, files = original_capture(invalid, *capture_arguments)
            bad_row = rejected["results"][0]
            assert bad_row["status"] == "error" and bad_row["observability"]["runner_result_verified"] is False
            assert files == {} and bad_row["deliverable_files"] == []

    claims = list(case.arguments["observation_directory"].glob("*.claimed.json"))
    assert len(claims) == 1 and case.consumed.is_file()
    reserved = {path: path.read_bytes() for path in (case.consumed, *claims)}
    before = (list(effects.events), len(typed), len(effects.requests))
    with pytest.raises(entry.FirstV2ObservationRefused, match="direction_observation_already_consumed"):
        entry.run_first_v2_observation(handoff_sources.plan, **case.arguments)
    assert (effects.events, len(typed), len(effects.requests)) == before
    assert {path: path.read_bytes() for path in reserved} == reserved
    assert capsys.readouterr() == ("", "")
    (tmp_path / "safe-boundary.json").write_text(json.dumps({
        "format": "v2-real-voice-result-boundary-proof-v1", "scenario": ending,
        "responses": 2, "faithful_second_request_verified": True,
        "runner_error": raw.get("error"), "captured_error": row["error"],
        "runner_result_verified": row["observability"]["runner_result_verified"],
        "status": row["status"], "terminal_reason": control.terminal_reason,
        "cleanup_complete": True, "permanent_claims": 1, "duplicate_refused_without_effect": True,
        "kernel": "synthetic_fixture_not_host_evidence",
    }, sort_keys=True, indent=2) + "\n")
