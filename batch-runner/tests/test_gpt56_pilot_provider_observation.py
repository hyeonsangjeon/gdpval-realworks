"""Synthetic HTTP bodies/rollouts only; never a live identity or budget proof."""

import json
import socket
import threading
from contextlib import contextmanager
from http.client import HTTPConnection, IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

import gpt56_pilot_wire_receipt as wire
import step2_run_inference as step2
from .test_gpt56_pilot_wire_receipt import REQUESTED, _finish, _start, _transport, _turn

CANARY = "PRIVATE_WIRE_CANARY_token_prompt_endpoint_never_publish"
UPSTREAM = "https://fixture-foundry.services.ai.azure.com/openai/v1"
MODEL = "gpt-5.6-sol"


def _body(model=MODEL):
    return json.dumps({"object": "response", "id": CANARY, "model": model,
                       "output": [{"text": CANARY}]}).encode()


def _sse(model=MODEL, *, final=True):
    response = json.loads(_body(model))
    kinds = ["response.created", "response.output_text.delta"]
    if final:
        kinds.append("response.completed")
    return b"".join(b"data: " + json.dumps(
        {"type": kind, "response": response} if kind != "response.output_text.delta" else
        {"type": kind, "delta": CANARY}).encode() + b"\r\n\r\n" for kind in kinds)


@pytest.fixture(autouse=True)
def loopback_only(monkeypatch):
    """Trap all non-loopback socket destinations, not just the expected API."""
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def checked(original):
        def call(sock, address):
            assert sock.family == socket.AF_INET and address[0] == "127.0.0.1"
            return original(sock, address)
        return call

    monkeypatch.setattr(socket.socket, "connect", checked(connect))
    monkeypatch.setattr(socket.socket, "connect_ex", checked(connect_ex))


@contextmanager
def _upstream(monkeypatch, rows, *, on_request=None):
    received, timeouts = [], []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, payload, dict(self.headers)))
            if on_request is not None:
                on_request()
            row = rows[len(received) - 1]
            self.send_response_only(row.get("status", 200))
            self.send_header("Content-Type", row.get("type", "application/json"))
            self.send_header("Content-Length", str(len(row["body"]) + row.get("missing", 0)))
            self.send_header("Connection", "close")
            for name, value in row.get("headers", {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.close_connection = True
            try:
                # Awkward byte boundaries, including UTF-8/CRLF/JSON boundaries.
                for start in range(0, len(row["body"]), 137):
                    self.wfile.write(row["body"][start:start + 137])
            except (BrokenPipeError, ConnectionResetError):
                pass

    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, *_args):
            raise AssertionError("synthetic_server_error")

    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()

    def connection(host, *, timeout):
        assert host == "fixture-foundry.services.ai.azure.com"
        timeouts.append(timeout)
        return HTTPConnection("127.0.0.1", server.server_port, timeout=timeout)

    monkeypatch.setattr(wire, "HTTPSConnection", connection)
    try:
        yield received, timeouts
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def _post(base_url, suffix="/responses", *, method="POST", headers=None):
    parsed = urlsplit(base_url)
    connection = HTTPConnection("127.0.0.1", parsed.port, timeout=5)
    try:
        connection.request(method, parsed.path + suffix, body=CANARY.encode(), headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + CANARY,
            "Cookie": CANARY, "Proxy-Authorization": CANARY, **(headers or {}),
        })
        response = connection.getresponse()
        try:
            body = response.read()
        except IncompleteRead as error:
            body = error.partial
        return response.status, body
    finally:
        connection.close()


@pytest.mark.parametrize("kind", ["json", "sse"])
def test_native_posts_and_response_model_reach_receipt_and_step2(monkeypatch, capsys, kind):
    body = _body() if kind == "json" else _sse()
    row = {"body": body, "type": "application/json" if kind == "json" else "text/event-stream"}
    observer = wire._TransportObservation(dict(REQUESTED))
    observer.approved_base_url = UPSTREAM
    provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"])
    key = "model_providers.gdpval-foundry.base_url="
    overrides = (key + json.dumps(UPSTREAM), "model_providers.gdpval-foundry.request_max_retries=0",
                 "model_providers.gdpval-foundry.stream_max_retries=0", 'model_reasoning_effort="max"')
    with _upstream(monkeypatch, [row, row]) as (received, _timeouts):
        changed = observer.configure_provider_observer(provider, overrides, timeout=60)
        try:
            assert changed[1:] == overrides[1:] and changed[0] != overrides[0]
            assert provider.base_url == UPSTREAM
            assert observer.provider_observation()["native_request_count"] is None
            fake = _transport(observer)
            _start(fake)
            assert _post(observer.provider_capture.base_url) == (200, body)
            assert _post(observer.provider_capture.base_url, "/responses/compact") == (200, body)
            _turn(fake)
        finally:
            observer.close_provider_observer()
        receipt = _finish(fake)
    observed = receipt["provider_observation"]
    assert observed["native_request_count"] == 2  # Two HTTP attempts within one SDK turn.
    assert observed["native_request_count_reason"] is None
    assert observed["served_model"] == MODEL != REQUESTED["deployment"]
    assert observed["served_model_reason"] is None
    assert observed["served_model_version"] is None
    assert observed["native_cap_enforced"] is observed["provider_receipt_confirmed"] is False
    assert receipt["served_model"]["value"] == MODEL
    assert receipt["usage"]["model_call_count"] == wire._unavailable()
    assert set(receipt["requests"]) == {"thread/start", "turn/start"}
    projected = step2._bounded_codex_diagnostics({"items_seen": 7, "provider_observation": observed})
    assert projected == {"items_seen": 7, "provider_observation": observed}
    assert [row[0] for row in received] == ["/openai/v1/responses", "/openai/v1/responses/compact"]
    assert all(row[1] == CANARY.encode() and row[2]["Authorization"] == "Bearer " + CANARY for row in received)
    assert all("Cookie" not in row[2] and "Proxy-Authorization" not in row[2] for row in received)
    output = capsys.readouterr()
    public = json.dumps(receipt) + json.dumps(projected) + output.out + output.err
    assert all(secret not in public for secret in (CANARY, UPSTREAM, observer.provider_capture.route, "Bearer"))


@pytest.mark.parametrize("case,reason", [
    ("rollout", "malformed_response"), ("quoted_model", "malformed_response"),
    ("missing_model", "response_model_not_returned"), ("malformed", "malformed_response"),
    ("duplicate", "malformed_response"), ("private_model", "response_model_not_allowlisted"),
    ("created_only", "response_capture_incomplete"), ("oversize", "response_capture_limit"),
    ("encoded", "encoded_response"), ("http_error", "provider_response_error"),
    ("redirect", "redirect_refused"), ("truncated", "transport_failed"),
])
def test_missing_or_unsafe_provider_evidence_stays_null(monkeypatch, capsys, case, reason):
    row = {"body": _body()}
    if case == "rollout":
        row["body"] = json.dumps({"type": "turn_context", "payload": {"model": MODEL, "text": CANARY}}).encode()
    elif case == "quoted_model":
        row["body"] = json.dumps({"type": "response_item", "content": json.loads(_body())}).encode()
    elif case == "missing_model":
        row["body"] = b'{"object":"response","output":[]}'
    elif case == "malformed":
        row["body"] = CANARY.encode()
    elif case == "duplicate":
        row["body"] = b'{"object":"response","model":"gpt-5.6-sol","model":"gpt-5.6-sol"}'
    elif case == "private_model":
        row["body"] = _body(CANARY)
    elif case == "created_only":
        row.update(body=_sse(final=False), type="text/event-stream")
    elif case == "oversize":
        row["body"] = b" " * (wire._CAPTURE_BYTES + 1) + _body()
    elif case == "encoded":
        row["headers"] = {"Content-Encoding": "gzip"}
    elif case == "http_error":
        row.update(status=429, body=CANARY.encode())
    elif case == "redirect":
        row.update(status=307, headers={"Location": "https://never-contact.invalid/" + CANARY})
    elif case == "truncated":
        row["missing"] = 17
    with _upstream(monkeypatch, [row]) as (received, _timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            _post(capture.base_url)
        finally:
            capture.close()
        observed = capture.summary()
    assert len(received) == observed["native_request_count"] == 1
    assert observed["served_model"] is None and observed["served_model_reason"] == reason
    assert observed["served_model_version"] is None
    output = capsys.readouterr()
    assert CANARY not in json.dumps(observed) + output.out + output.err


def test_differing_actual_models_are_not_collapsed_to_requested_model(monkeypatch):
    with _upstream(monkeypatch, [{"body": _body()}, {"body": _body("gpt-5.6-sol-fast")}]) as (received, _timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            _post(capture.base_url)
            _post(capture.base_url)
        finally:
            capture.close()
    assert len(received) == capture.summary()["native_request_count"] == 2
    assert capture.summary()["served_model"] is None
    assert capture.summary()["served_model_reason"] == "response_models_differ"


@pytest.mark.parametrize("suffix,method", [("/models", "GET"), ("/responses?redirect=1", "POST"),
                                          ("/../responses", "POST"), ("/responses", "CONNECT")])
def test_no_arbitrary_upstream_or_unsupported_transport(monkeypatch, suffix, method):
    with _upstream(monkeypatch, []) as (received, _timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            status, body = _post(capture.base_url, suffix, method=method)
            assert status == 400 and body == b""
        finally:
            capture.close()
    assert received == []
    assert capture.summary()["native_request_count"] is None
    assert capture.summary()["native_request_count_reason"] == "unsupported_native_route"


def test_one_cumulative_deadline_no_retry_or_turn_count_substitution(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(wire.time, "monotonic", lambda: clock[0])
    with _upstream(monkeypatch, [{"body": _body()}, {"body": _body()}],
                   on_request=lambda: clock.__setitem__(0, clock[0] + 35)) as (received, timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            assert _post(capture.base_url)[0] == 200
            _post(capture.base_url)
        finally:
            capture.close()
    assert timeouts == [60, 25]
    assert len(received) == capture.summary()["native_request_count"] == 2
    assert capture.summary()["served_model"] is None
    assert capture.summary()["served_model_reason"] == "deadline_exceeded"


@pytest.mark.parametrize("damage", ["count", "bool", "reason", "model", "extra", "version", "authority"])
def test_step2_projection_cannot_publish_untyped_or_private_metadata(damage, capsys):
    raw = wire._provider_summary()
    if damage == "count":
        raw["native_request_count"] = -1
    elif damage == "bool":
        raw["native_request_count"] = True
    elif damage == "reason":
        raw["served_model_reason"] = CANARY
    elif damage == "model":
        raw.update(served_model=CANARY, served_model_reason=None)
    elif damage == "extra":
        raw["raw_body"] = CANARY
    elif damage == "version":
        raw["served_model_version"] = "2026-07-09"
    elif damage == "authority":
        raw["native_cap_enforced"] = True
    result = step2._bounded_codex_diagnostics({"provider_observation": raw})
    assert result == {"provider_observation": wire._provider_summary("invalid_observation")}
    output = capsys.readouterr()
    assert CANARY not in json.dumps(result) + output.out + output.err


def test_listener_failure_and_missing_observer_are_explicit_not_zero(monkeypatch):
    observer = wire._TransportObservation(dict(REQUESTED))
    assert observer.provider_observation() == wire._provider_summary()
    observer.approved_base_url = UPSTREAM
    provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"])
    overrides = ('model_providers.gdpval-foundry.base_url=' + json.dumps(UPSTREAM),)

    def unavailable(*_args):
        raise OSError(CANARY)

    monkeypatch.setattr(wire, "_ProviderHTTPObservation", unavailable)
    assert observer.configure_provider_observer(provider, overrides, timeout=60) == overrides
    assert observer.provider_observation() == wire._provider_summary("observer_start_failed")
    assert step2._bounded_codex_diagnostics({"items_seen": 2}) == {"items_seen": 2}


@pytest.mark.parametrize("target", ["https://other.services.ai.azure.com/openai/v1", UPSTREAM + "?x=1",
                                   "http://fixture-foundry.services.ai.azure.com/openai/v1"])
def test_source_bound_upstream_cannot_be_replaced(monkeypatch, target):
    observer = wire._TransportObservation(dict(REQUESTED))
    observer.approved_base_url = UPSTREAM
    provider = SimpleNamespace(base_url=target, provider_id=REQUESTED["provider_id"])

    def forbidden(*_args):
        raise AssertionError("listener_or_network_before_binding")

    monkeypatch.setattr(wire, "_ProviderHTTPObservation", forbidden)
    with pytest.raises(wire.PilotWireReceiptRefused, match="^pilot_wire_receipt_refused$"):
        observer.configure_provider_observer(provider, ('model_providers.gdpval-foundry.base_url=' + json.dumps(target),),
                                             timeout=60)


def test_sse_byte_boundaries_and_rollout_quotes_never_supply_identity():
    parser = wire._ResponseModel("text/event-stream; charset=utf-8", "identity", 200)
    for value in _sse():
        parser.feed(bytes([value]))
    assert parser.finish() == (MODEL, None)
    parser = wire._ResponseModel("text/event-stream", "", 200)
    event = {"type": "response.output_text.delta", "delta": _body().decode()}
    parser.feed(b"data: " + json.dumps(event).encode() + b"\n\n")
    assert parser.finish() == (None, "response_capture_incomplete")


def test_capture_does_not_turn_the_provisional_32_into_a_native_limit(monkeypatch):
    with _upstream(monkeypatch, [{"body": _body()}] * 33) as (received, _timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            for _ in range(33):
                assert _post(capture.base_url)[0] == 200
        finally:
            capture.close()
    assert len(received) == capture.summary()["native_request_count"] == 33
    assert capture.summary()["native_cap_enforced"] is False


def test_pinned_python_sdk_passes_the_observed_url_to_the_cli_not_python_http(monkeypatch):
    from importlib.metadata import version
    from openai_codex.client import CodexClient, CodexConfig

    assert version("openai-codex") == version("openai-codex-cli-bin") == "0.147.0"
    observed = []

    def fake_process(args, **kwargs):
        observed.append((args, kwargs))
        return SimpleNamespace()

    monkeypatch.setattr("openai_codex.client.subprocess.Popen", fake_process)
    monkeypatch.setattr(CodexClient, "_start_reader_thread", lambda _self: None)
    monkeypatch.setattr(CodexClient, "_start_stderr_drain_thread", lambda _self: None)
    override = 'model_providers.gdpval-foundry.base_url="http://127.0.0.1:32123/fixture"'
    client = CodexClient(CodexConfig(config_overrides=(override,)))
    client.start()
    args, kwargs = observed[0]
    assert args[-5:] == ["--config", override, "app-server", "--listen", "stdio://"]
    assert kwargs["encoding"] == "utf-8"
    assert len(observed) == 1  # Process creation was trapped, not executed.
