"""Hosted-only real Codex 0.147.0 -> production precheck -> scripted HTTP.

No provider, credential or model is used. This is wiring evidence, never
served-model/capability evidence. NAS runs must not select this integration.
"""

import json
import os
import re
import sys

import pytest

from core import codex_runner, runner_environment
from core.codex_runtime_config import CodexProviderSettings, require_pinned_runtime
import gpt56_pilot_wire_receipt as wire
from scripts import diagnose_codex_foundry_connection as diagnostic
from .test_codex_retry_pins_are_enforced import _token_printer
from .test_gpt56_pilot_provider_observation import MODEL, UPSTREAM, _upstream, loopback_only


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("GDPVAL_NATIVE_LOOPBACK_PROOF") != "1",
    reason="explicit hosted model-free runtime proof only",
)]


def _scripted_response(*, report_context=True):
    response = {"object": "response", "id": "synthetic-response", "model": MODEL,
                "model_version": "synthetic-test-version", "reasoning": {"effort": "max"},
                "context_window": 1_000_000, "status": "completed",
                "usage": {"input_tokens": 90, "output_tokens": 1, "total_tokens": 91,
                          "input_tokens_details": {"cached_tokens": 0},
                          "output_tokens_details": {"reasoning_tokens": 0}}}
    if not report_context:
        response.pop("context_window")
    message = {"type": "message", "id": "synthetic-message", "role": "assistant",
               "status": "completed", "content": [{"type": "output_text", "text": "CONNECTED"}]}
    events = [
        {"type": "response.created", "response": {"object": "response", "id": "synthetic-response",
                                                  "model": MODEL, "status": "in_progress"}},
        {"type": "response.output_item.done", "output_index": 0, "item": message},
        {"type": "response.completed", "response": {**response, "output": [message]}},
    ]
    return b"".join(b"event: " + event["type"].encode() + b"\ndata: "
                    + json.dumps(event).encode() + b"\n\n" for event in events)


def _input_shape(value):
    """Only schema labels and value types, never text, references or payloads."""
    def label(raw):
        return raw if type(raw) is str and re.fullmatch(r"[a-z_]{1,48}", raw) else None
    result = {"container": type(value).__name__}
    if type(value) is not list:
        return result
    result["items"] = []
    for item in value[:32]:
        if type(item) is not dict:
            result["items"].append({"container": type(item).__name__})
            continue
        content = item.get("content")
        row = {"type": label(item.get("type")), "role": label(item.get("role")),
               "content_container": type(content).__name__,
               "opaque_fields_present": [key for key in (
                   "encrypted_content", "image_url", "file_id", "file_data", "file_url", "audio")
                   if item.get(key) is not None]}
        if item.get("type") == "additional_tools":
            tools = item.get("tools")
            row["local_definitions_only"] = wire._local_tool_definitions(tools, namespaces=True)
            row["definition_count"] = len(tools) if type(tools) is list else None
            row["definition_types"] = [label(tool.get("type")) if type(tool) is dict else None
                                       for tool in tools[:32]] if type(tools) is list else []
        if type(content) is list:
            row["parts"] = [{"container": type(part).__name__,
                              "type": label(part.get("type")) if type(part) is dict else None,
                              "text_container": type(part.get("text")).__name__ if type(part) is dict else None}
                             for part in content[:32]]
        result["items"].append(row)
    return result


def test_real_pinned_sol_diagnostic_passes_unchanged_token_precheck(monkeypatch, tmp_path):
    # Actual runner admission, never the synthetic native_hosted_runner fixture.
    host = runner_environment.require_execution()
    require_pinned_runtime()
    printer, _ = _token_printer(tmp_path)
    monkeypatch.setenv("GDPVAL_CODEX_RUN_ROOT", str(tmp_path / "isolated-runtimes"))
    monkeypatch.setattr(codex_runner, "resolve_run_root_base", lambda: tmp_path / "isolated-runtimes")

    class FakeAuthSettings(CodexProviderSettings):
        def auth_command(self, source_environment=None):
            return [sys.executable, str(printer)]

    settings = FakeAuthSettings(endpoint=UPSTREAM, model=MODEL, reasoning_effort="max",
                                model_context_window=1_000_000)
    shapes, ingress = [], []
    original_precheck = wire._ProviderHTTPObservation._token_request
    original_forward = wire._ProviderHTTPObservation.forward

    def observe_precheck(self, body, suffix):
        # Do not publish arbitrary body values, prompt text or headers. These
        # facts locate the refusal without changing the production decision.
        try:
            document = json.loads(body)
            tools = document.get("tools", [])
            shape = {"bytes": len(body), "text_input": wire._text_input(document.get("input")),
                     "input_shape": _input_shape(document.get("input")),
                     "tool_count": len(tools), "local_tools_only": all(
                         tool.get("type") in {"function", "custom"} for tool in tools),
                     "sol_requested": document.get("model") == MODEL,
                     "max_requested": (document.get("reasoning") or {}).get("effort") == "max",
                     "opaque_context_keys": [key for key in (
                         "previous_response_id", "conversation", "prompt", "context_management")
                         if document.get(key) is not None]}
        except (ValueError, TypeError, AttributeError):
            shape = {"json_shape": "uninspectable"}
        shapes.append(shape)
        try:
            admitted = original_precheck(self, body, suffix)
        except wire._TokenPrecheckRefused as error:
            shape["refusal"] = error.reason
            raise
        shape["forwarded_max_output_tokens"] = json.loads(admitted)["max_output_tokens"]
        return admitted

    def observe_ingress(self, handler):
        ingress.append({"json_content_type": handler.headers.get("Content-Type", "").lower().replace(" ", "")
                        in {"application/json", "application/json;charset=utf-8"},
                        "identity_encoding": handler.headers.get("Content-Encoding", "identity").lower() == "identity"})
        return original_forward(self, handler)

    monkeypatch.setattr(wire._ProviderHTTPObservation, "_token_request", observe_precheck)
    monkeypatch.setattr(wire._ProviderHTTPObservation, "forward", observe_ingress)
    with _upstream(monkeypatch, [{"body": _scripted_response(), "type": "text/event-stream",
                                 "headers": {"x-ratelimit-remaining-tokens": "0"}}]) as (received, _):
        record = diagnostic.probe(settings, timeout=30, response_artifact_parent=tmp_path)
    proof = {"schema": "sol_native_loopback/1", "evidence_type": "synthetic_model_free",
             "model_calls": 0, "fake_upstream_requests": len(received),
             "ingress": list(ingress), "request_shapes": list(shapes), "verdict": record["verdict"],
             "runner": host, "observed": record["observed"]}
    destination = os.environ.get("GDPVAL_NATIVE_LOOPBACK_REPORT")
    if destination:
        from pathlib import Path
        Path(destination).write_text(json.dumps(proof, indent=2) + "\n")
    assert len(received) == 1, json.dumps(proof)
    assert len(shapes) == 1 and ingress == [{"json_content_type": True, "identity_encoding": True}]
    assert shapes[0]["text_input"] and shapes[0]["local_tools_only"]
    assert shapes[0]["sol_requested"] and shapes[0]["max_requested"]
    assert shapes[0]["opaque_context_keys"] == []
    assert shapes[0]["forwarded_max_output_tokens"] == 10_000
    assert record["verdict"] == diagnostic.VERDICT_CONNECTED, json.dumps(proof)
    assert record["observed"]["provider_transport"]["native_request_count"] == 1
    assert record["observed"]["provider_transport"]["runtime_caps"]["stop_reason"] is None
    assert record["observed"]["provider_response_evidence"]["state"] == "observed"
    assert not list((tmp_path / "isolated-runtimes").glob("**/workspace"))

    # The observed live failure, replayed with NO provider/credential/model:
    # HTTP 200 without context must produce an explicit evidence refusal,
    # even when the real SDK sees the observer's 502 and reports turn failure.
    refused_root = tmp_path / "missing-context"
    refused_root.mkdir(mode=0o700)
    with _upstream(monkeypatch, [{"body": _scripted_response(report_context=False),
                                 "type": "text/event-stream",
                                 "headers": {"x-ratelimit-remaining-tokens": "0"}}]) as (denied_received, _):
        refused = diagnostic.probe(settings, timeout=30, response_artifact_parent=refused_root)
    proof["missing_context_case"] = {"verdict": refused["verdict"],
        "fake_upstream_requests": len(denied_received),
        "state": refused["observed"]["provider_response_evidence"]["state"],
        "stop_reason": refused["observed"]["provider_transport"]["runtime_caps"]["stop_reason"]}
    if destination:
        Path(destination).write_text(json.dumps(proof, indent=2) + "\n")
    assert proof["missing_context_case"] == {
        "verdict": diagnostic.VERDICT_RESPONSE_EVIDENCE_REFUSED, "fake_upstream_requests": 1,
        "state": "unverified", "stop_reason": "context_window_unverified",
    }, json.dumps(proof)
    assert not list((tmp_path / "isolated-runtimes").glob("**/workspace"))
