"""Client admission fixtures only; no server hard-limit or tokenizer proof."""

import json
import threading
from copy import deepcopy
from http.client import HTTPConnection
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor

import pytest

import gpt56_pilot_wire_receipt as wire
import step2_run_inference as step2
from .test_gpt56_pilot_provider_observation import (
    CANARY, MODEL, UPSTREAM, _body, _post, _sse, _upstream, loopback_only,
)


def _request(maximum=None, *, text="fixture", **extra):
    document = {"model": MODEL, "input": text, **extra}
    if maximum is not None:
        document["max_output_tokens"] = maximum
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode()


def _response(inputs=4, outputs=1, *, status="completed"):
    document = json.loads(_body())
    document.update(status=status, usage={"input_tokens": inputs, "output_tokens": outputs,
                                         "total_tokens": inputs + outputs})
    return {"body": json.dumps(document).encode()}


def _caps(capture):
    result = capture.summary()
    assert wire.bounded_provider_observation(result) == result
    assert step2._bounded_codex_diagnostics({"provider_observation": result}) == {"provider_observation": result}
    caps = result["runtime_caps"]
    assert caps["token_hard_limit_enforced"] is False
    assert caps["client_token_precheck"]["server_hard_limit_verified"] is False
    assert caps["client_token_precheck"]["enabled"] is True
    assert CANARY not in json.dumps(result)
    return caps


def test_complete_usage_drives_remaining_field_without_sdk_double_count(monkeypatch, capsys):
    with _upstream(monkeypatch, [_response(30, 6), _response(20, 4)]) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url, body=_request(10000))[0] == 200
            capture.report_usage({"inputTokens": 30, "outputTokens": 6})
            assert _post(capture.base_url, body=_request())[0] == 200
            capture.report_usage({"inputTokens": 50, "outputTokens": 10})
        finally:
            capture.close()
    caps = _caps(capture)
    check = caps["client_token_precheck"]
    assert len(received) == len(calls) == capture.requests == 2
    assert [json.loads(row[1])["max_output_tokens"] for row in received] == [10000, 9994]
    assert all(int(row[2]["Content-Length"]) == len(row[1]) for row in received)
    assert (check["accounted_input_tokens"], check["accounted_output_tokens"]) == (50, 10)
    assert (check["remaining_input_tokens"], check["remaining_output_tokens"]) == (299950, 9990)
    assert check["checked_requests"] == 2 and check["blocked_requests"] == 0
    assert check["usage_known"] is True and caps["stop_reason"] is None
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_input_estimate_boundary_refuses_before_upstream_construction(monkeypatch, offset):
    request = _request(1)
    first_inputs = 300000 - len(request) + offset
    with _upstream(monkeypatch, [_response(first_inputs, 0), _response(0, 0)]) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url)[0] == 200
            assert _post(capture.base_url, body=request)[0] == (400 if offset > 0 else 200)
        finally:
            capture.close()
    caps = _caps(capture)
    check = caps["client_token_precheck"]
    assert len(received) == len(calls) == capture.requests == (1 if offset > 0 else 2)
    assert check["last_input_estimate"] == len(request)
    assert check["remaining_input_tokens"] == len(request) - offset
    assert caps["stop_reason"] == (wire.NATIVE_INPUT_PRECHECK_EXCEEDED if offset > 0 else None)
    assert check["blocked_requests"] == int(offset > 0)


@pytest.mark.parametrize("maximum", [9, 10, 11])
def test_output_field_boundary_refuses_instead_of_silently_clamping(monkeypatch, maximum):
    with _upstream(monkeypatch, [_response(0, 9990), _response(0, 0)]) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url)[0] == 200
            assert _post(capture.base_url, body=_request(maximum))[0] == (400 if maximum > 10 else 200)
        finally:
            capture.close()
    caps = _caps(capture)
    check = caps["client_token_precheck"]
    assert len(received) == len(calls) == (1 if maximum > 10 else 2)
    assert check["last_output_limit"] == maximum and check["remaining_output_tokens"] == 10
    assert caps["stop_reason"] == (wire.NATIVE_OUTPUT_PRECHECK_EXCEEDED if maximum > 10 else None)
    if maximum <= 10:
        assert json.loads(received[1][1])["max_output_tokens"] == maximum


@pytest.mark.parametrize("damage", ["absent", "null", "partial", "float", "bool", "negative", "total"])
def test_unknown_usage_cannot_be_reopened_by_late_sdk_totals(monkeypatch, damage):
    document = json.loads(_response()["body"])
    if damage == "absent":
        del document["usage"]
    elif damage == "null":
        document["usage"] = None
    elif damage == "partial":
        del document["usage"]["output_tokens"]
    else:
        field = "total_tokens" if damage == "total" else "input_tokens"
        document["usage"][field] = {"float": 4.0, "bool": True, "negative": -1, "total": 999}[damage]
    with _upstream(monkeypatch, [{"body": json.dumps(document).encode()}]) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url)[0] == 200
            capture.report_usage({"inputTokens": 10, "outputTokens": 7})
            assert _post(capture.base_url, body=_request(1)) == (400, b"")
        finally:
            capture.close()
    caps = _caps(capture)
    check = caps["client_token_precheck"]
    assert len(received) == len(calls) == 1
    assert caps["stop_reason"] == wire.NATIVE_USAGE_UNVERIFIED and check["usage_known"] is False
    assert check["accounted_input_tokens"] is check["accounted_output_tokens"] is None
    assert check["remaining_input_tokens"] is check["remaining_output_tokens"] is None


@pytest.mark.parametrize("kind", ["created_only", "incomplete", "failed", "in_progress", "truncated",
                                  "duplicate_terminal", "after_terminal", "http_error"])
def test_partial_or_failed_response_blocks_the_next_request(monkeypatch, kind):
    row = _response()
    if kind == "created_only":
        row.update(body=_sse(final=False), type="text/event-stream")
    elif kind in {"incomplete", "failed"}:
        document = json.loads(_response(status=kind)["body"])
        row.update(body=b"data: " + json.dumps({"type": "response." + kind, "response": document}).encode()
                   + b"\n\n", type="text/event-stream")
    elif kind == "in_progress":
        row = _response(status=kind)
    elif kind == "truncated":
        row["missing"] = 17
    elif kind == "duplicate_terminal":
        row.update(body=_sse() + _sse(), type="text/event-stream")
    elif kind == "after_terminal":
        row.update(body=_sse() + b'data: {"type":"response.output_text.delta","delta":"late"}\n\n',
                   type="text/event-stream")
    else:
        row["status"] = 503
    with _upstream(monkeypatch, [row]) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url)[0] == row.get("status", 200)
            assert _post(capture.base_url) == (400, b"")
        finally:
            capture.close()
    caps = _caps(capture)
    assert len(received) == len(calls) == 1
    assert caps["stop_reason"] == wire.NATIVE_USAGE_UNVERIFIED
    assert caps["client_token_precheck"]["usage_known"] is False


@pytest.mark.parametrize("maximum", [None, False, 0, -1, 1.5, "10", 2 ** 63])
def test_invalid_explicit_output_field_never_connects(monkeypatch, maximum):
    body = json.dumps({"model": MODEL, "input": CANARY, "max_output_tokens": maximum}).encode()
    with _upstream(monkeypatch, []) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url, body=body) == (400, b"")
        finally:
            capture.close()
    assert not received and not calls
    assert _caps(capture)["stop_reason"] == wire.NATIVE_OUTPUT_LIMIT_UNAVAILABLE


@pytest.mark.parametrize("damage", ["compact", "alias", "duplicate", "malformed", "content_type",
                                    "encoding", "length", "remote_state", "template", "image", "opaque",
                                    "server_tool", "background", "nonfinite", "nonfinite_exponent", "surrogate"])
def test_uninspectable_request_fails_closed_without_private_egress(monkeypatch, capsys, damage):
    body, headers, suffix = _request(), {}, "/responses"
    reason = wire.NATIVE_TOKEN_REQUEST_UNVERIFIED
    if damage == "compact":
        suffix, reason = "/responses/compact", wire.NATIVE_OUTPUT_LIMIT_UNAVAILABLE
    elif damage == "alias":
        body, reason = _request(1, max_tokens=10001), wire.NATIVE_OUTPUT_LIMIT_UNAVAILABLE
    elif damage == "duplicate":
        body = b'{"input":"x","max_output_tokens":1,"max_output_tokens":10001}'
    elif damage == "malformed":
        body = CANARY.encode()
    elif damage == "content_type":
        headers = {"Content-Type": "application/octet-stream"}
    elif damage == "encoding":
        headers = {"Content-Encoding": "gzip"}
    elif damage == "length":
        headers = {"Content-Length": str(wire._REQUEST_CAPTURE_BYTES + 1)}
    elif damage == "remote_state":
        body = _request(previous_response_id=CANARY)
    elif damage == "template":
        body = _request(prompt={"id": CANARY})
    elif damage == "image":
        body = _request(text=[{"role": "user", "content": [{"type": "input_image", "image_url": CANARY}]}])
    elif damage == "opaque":
        body = _request(text=[{"type": "reasoning", "encrypted_content": CANARY}])
    elif damage == "server_tool":
        body = _request(tools=[{"type": "web_search"}])
    elif damage == "background":
        body = _request(background=True)
    elif damage == "nonfinite_exponent":
        body = b'{"input":"x","max_output_tokens":1,"temperature":1e309}'
    elif damage == "surrogate":
        body = b'{"input":"\\ud800","max_output_tokens":1}'
    else:
        body = b'{"input":"x","temperature":NaN}'
    with _upstream(monkeypatch, []) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url, suffix, body=body, headers=headers) == (400, b"")
        finally:
            capture.close()
    caps = _caps(capture)
    assert not received and not calls and capture.requests == 0
    assert caps["stop_reason"] == reason
    assert caps["client_token_precheck"]["blocked_requests"] == 1
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err + json.dumps(caps)


def test_concurrent_requests_cannot_share_the_same_output_remainder(monkeypatch):
    started, release = threading.Event(), threading.Event()

    def first_request():
        if not started.is_set():
            started.set()
            assert release.wait(2)

    with _upstream(monkeypatch, [_response(2, 9999), _response(2, 1)], on_request=first_request) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(_post, capture.base_url)
                assert started.wait(2)
                second = pool.submit(_post, capture.base_url)
                assert len(received) == len(calls) == 1
                release.set()
                assert first.result(timeout=3)[0] == second.result(timeout=3)[0] == 200
        finally:
            release.set()
            capture.close()
    caps = _caps(capture)
    assert [json.loads(row[1])["max_output_tokens"] for row in received] == [10000, 1]
    assert caps["client_token_precheck"]["accounted_output_tokens"] == 10000
    assert caps["client_token_precheck"]["remaining_output_tokens"] == 0


def test_exhausted_output_does_not_insert_zero_or_start_another_request(monkeypatch):
    with _upstream(monkeypatch, [_response(1, 10000)]) as (received, calls):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url)[0] == 200
            assert _post(capture.base_url) == (400, b"")
        finally:
            capture.close()
    assert len(received) == len(calls) == 1
    assert _caps(capture)["stop_reason"] == wire.NATIVE_OUTPUT_PRECHECK_EXCEEDED


@pytest.mark.parametrize("stream", [False, True])
def test_response_content_type_and_body_remain_transparent(monkeypatch, stream):
    body, content_type = (_sse(), "text/event-stream") if stream else (_body(), "application/json")
    with _upstream(monkeypatch, [{"body": body, "type": content_type}]):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        address = urlsplit(capture.base_url)
        connection = HTTPConnection("127.0.0.1", address.port, timeout=5)
        try:
            connection.request("POST", address.path + "/responses", body=_request(),
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            assert response.status == 200 and response.getheader("Content-Type") == content_type
            assert response.read() == body
        finally:
            connection.close()
            capture.close()
    assert _caps(capture)["client_token_precheck"]["usage_known"] is True


@pytest.mark.parametrize("damage", ["server_claim", "estimator", "extra", "bool_count", "negative_count",
                                    "remaining", "unknown_usage", "private_count"])
def test_precheck_projection_is_closed_and_cannot_upgrade_server_authority(damage):
    capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
    capture.close()
    raw = deepcopy(capture.summary())
    check = raw["runtime_caps"]["client_token_precheck"]
    if damage == "server_claim":
        check["server_hard_limit_verified"] = True
    elif damage == "estimator":
        check["input_estimator"] = CANARY
    elif damage == "extra":
        check["raw_request"] = CANARY
    elif damage == "bool_count":
        check["checked_requests"] = True
    elif damage == "negative_count":
        check["blocked_requests"] = -1
    elif damage == "remaining":
        check["remaining_output_tokens"] = 10001
    elif damage == "unknown_usage":
        check["usage_known"] = False
    else:
        check["last_input_estimate"] = CANARY
    result = wire.bounded_provider_observation(raw)
    assert result == wire._provider_summary("invalid_observation")
    assert CANARY not in json.dumps(result)
