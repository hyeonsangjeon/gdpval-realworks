"""Synthetic HTTP bodies/rollouts only; never a live identity or budget proof."""

import json
import socket
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.client import HTTPConnection, IncompleteRead, RemoteDisconnected
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

import gpt56_pilot_wire_receipt as wire
import step2_run_inference as step2
from core import codex_runner
from .test_gpt56_pilot_wire_receipt import REQUESTED, USAGE, _finish, _start, _transport, _turn

CANARY = "PRIVATE_WIRE_CANARY_token_prompt_endpoint_never_publish"
UPSTREAM = "https://fixture-foundry.services.ai.azure.com/openai/v1"
MODEL = "gpt-5.6-sol"


def _body(model=MODEL):
    return json.dumps({"object": "response", "id": CANARY, "model": model,
                       "status": "completed", "usage": {"input_tokens": 4, "output_tokens": 1,
                                                          "total_tokens": 5},
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


def _post(base_url, suffix="/responses", *, method="POST", headers=None, body=None):
    parsed = urlsplit(base_url)
    connection = HTTPConnection("127.0.0.1", parsed.port, timeout=5)
    try:
        payload = json.dumps({"model": MODEL, "input": CANARY}).encode() if body is None else body
        connection.request(method, parsed.path + suffix, body=payload, headers={
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
            assert _post(observer.provider_capture.base_url) == (200, body)
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
    assert observed["native_cap_enforced"] is True
    assert observed["provider_receipt_confirmed"] is False
    assert observed["native_request_limit"] == 32
    assert observed["native_request_limit_sha256"] == wire.NATIVE_CAPS_SHA256
    assert observed["native_request_blocked_count"] == 0 and observed["native_request_cap_reason"] is None
    assert receipt["served_model"]["value"] == MODEL
    assert receipt["usage"]["model_call_count"] == wire._unavailable()
    assert set(receipt["requests"]) == {"thread/start", "turn/start"}
    projected = step2._bounded_codex_diagnostics({"items_seen": 7, "provider_observation": observed})
    assert projected == {"items_seen": 7, "provider_observation": observed}
    assert [row[0] for row in received] == ["/openai/v1/responses"] * 2
    assert [json.loads(row[1]) for row in received] == [
        {"model": MODEL, "input": CANARY, "max_output_tokens": 10000},
        {"model": MODEL, "input": CANARY, "max_output_tokens": 9999},
    ]
    assert all(row[2]["Authorization"] == "Bearer " + CANARY for row in received)
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
            try:
                _post(capture.base_url)
            except RemoteDisconnected:
                pass  # The deadline watchdog may close before the error response.
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
    with pytest.raises(wire.PilotWireReceiptRefused, match="^pilot_wire_receipt_refused$"):
        observer.configure_provider_observer(provider, overrides, timeout=60)
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


def test_native_request_cap_blocks_33_before_upstream(monkeypatch):
    with _upstream(monkeypatch, [{"body": _body()}] * 32) as (received, timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            for _ in range(32):
                assert _post(capture.base_url)[0] == 200
            assert _post(capture.base_url, "/responses/compact") == (400, b"")
        finally:
            capture.close()
    observed = capture.summary()
    assert len(received) == len(timeouts) == observed["native_request_count"] == 32
    assert observed["native_request_count_reason"] is None
    assert observed["native_cap_enforced"] is True
    assert observed["native_request_blocked_count"] == 1
    assert observed["native_request_cap_reason"] == wire.NATIVE_REQUEST_CAP_EXCEEDED
    assert capture.closed and not capture.thread.is_alive() and capture.server.socket.fileno() == -1


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


def test_close_interrupts_incomplete_local_headers(monkeypatch):
    capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
    accepted = threading.Event()
    original = capture.server.get_request

    def get_request():
        result = original()
        accepted.set()
        return result

    monkeypatch.setattr(capture.server, "get_request", get_request)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.settimeout(0.2)
        client.connect(("127.0.0.1", capture.server.server_port))
        assert accepted.wait(1)
        client.sendall(b"POST /incomplete HTTP/1.1\r\nHost: fixture\r\n")
        capture.close()
        assert client.recv(1) == b""
        assert capture.summary()["native_request_count"] == 0
        closed = capture.summary()
        capture._response_finished(MODEL, None)
        assert capture.summary() == closed
    finally:
        client.close()
        capture.close()


@pytest.mark.parametrize("count", [1, 31, 32])
def test_native_request_cap_allows_the_snapshot_limit(monkeypatch, count):
    with _upstream(monkeypatch, [{"body": _body()}] * count) as (received, timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            for index in range(count):
                suffix = "/responses"  # Compact has no verified output-limit field.
                assert _post(capture.base_url, suffix) == (200, _body())
            assert not capture.cap_exceeded and not capture.closed
        finally:
            capture.close()
    summary = capture.summary()
    assert len(received) == len(timeouts) == summary["native_request_count"] == count
    assert summary["native_request_limit"] == wire._native_request_limit() == 32
    assert summary["native_request_blocked_count"] == 0
    assert summary["native_request_cap_reason"] is None and summary["native_cap_enforced"] is True


def test_native_request_cap_reserves_the_last_slot_atomically(monkeypatch):
    with _upstream(monkeypatch, [{"body": _body()}] * 32) as (received, timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        barrier = threading.Barrier(4)

        def final_request(_index):
            barrier.wait(timeout=2)
            try:
                return _post(capture.base_url)[0]
            except (OSError, IncompleteRead):
                return None  # Closure may interrupt another local connection.

        try:
            for _ in range(31):
                assert _post(capture.base_url)[0] == 200
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(final_request, range(4)))
        finally:
            capture.close()
    assert 31 <= len(received) <= 32
    assert len(timeouts) == capture.summary()["native_request_count"] == 32
    assert capture.summary()["native_request_blocked_count"] >= 1
    assert capture.summary()["native_request_cap_reason"] == wire.NATIVE_REQUEST_CAP_EXCEEDED


@pytest.mark.parametrize("damage", ["missing", "drift"])
def test_native_request_cap_refuses_unsealed_caps_before_a_listener(monkeypatch, tmp_path, damage):
    path = tmp_path / "caps.yaml"
    if damage == "drift":
        path.write_bytes(wire._NATIVE_CAPS_PATH.read_bytes().replace(b"native_model_calls: 32", b"native_model_calls: 99"))
    monkeypatch.setattr(wire, "_NATIVE_CAPS_PATH", path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("listener_before_sealed_cap")

    monkeypatch.setattr(socket.socket, "bind", forbidden)
    with pytest.raises(wire.PilotWireReceiptRefused, match="^pilot_wire_receipt_refused$"):
        wire._ProviderHTTPObservation(UPSTREAM, 60)


@pytest.mark.parametrize("damage", ["limit", "digest", "blocked", "reason", "forwarded"])
def test_native_request_cap_projection_refuses_inconsistent_claims(monkeypatch, damage, capsys):
    capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
    capture.close()
    raw = capture.summary()
    if damage == "limit":
        raw["native_request_limit"] = 33
    elif damage == "digest":
        raw["native_request_limit_sha256"] = "0" * 64
    elif damage == "blocked":
        raw["native_request_blocked_count"] = 1
    elif damage == "reason":
        raw["native_request_cap_reason"] = CANARY
    else:
        raw["native_request_count"] = 33
    projected = step2._bounded_codex_diagnostics({"provider_observation": raw})
    assert projected == {"provider_observation": wire._provider_summary("invalid_observation")}
    output = capsys.readouterr()
    assert CANARY not in json.dumps(projected) + output.out + output.err


@pytest.mark.parametrize("terminal", [None, "completed"])
@pytest.mark.parametrize("with_usage", [False, True])
def test_native_request_cap_stops_process_and_preserves_partial_receipt(
        monkeypatch, tmp_path, capsys, terminal, with_usage):
    """Real runner/SDK close + harmless child; no Rust, auth, provider or host admission.

    The fake turn even returns success after its denied request. The real runner
    must override that result, and unknown terminal/usage must stay unknown.
    """
    from openai_codex.client import CodexClient, CodexConfig
    from gpt56_pilot_runtime_caps_usage import _UsageObservation

    observer = wire._TransportObservation(dict(REQUESTED))
    observer.approved_base_url = UPSTREAM
    observer.bind_task_text(CANARY)
    provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"])
    overrides = ('model_providers.gdpval-foundry.base_url=' + json.dumps(UPSTREAM),)
    owner = SimpleNamespace(failed=False, approved_limits={"model_calls": wire._native_request_limit(),
                                                         "input_tokens": 300000, "output_tokens": 10000},
                            wire=SimpleNamespace(document={"requested": dict(REQUESTED)}))

    def poison():
        owner.failed = True

    owner._poison = poison
    observer.caps_usage_observer = _UsageObservation(owner, observer)
    runner = object.__new__(codex_runner.CodexAgentRunner)
    runner.timeout, runner.cost_ledger = 5, None
    monkeypatch.setattr(codex_runner, "_load_turn_collector", lambda: None)

    with _upstream(monkeypatch, [{"body": _body()}] * 32) as (received, timeouts), subprocess.Popen(
            [sys.executable, "-I", "-u", "-c", "import signal; print('ready', flush=True); signal.pause()"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env={}) as process:
        assert process.stdout.readline() == "ready\n"
        client = CodexClient(CodexConfig())
        client._proc = process  # Do not start or initialize a real Codex CLI.
        client._router.route_response = lambda _message: "original-response"
        client._coerce_notification = lambda *_args: "original-notification"
        codex = SimpleNamespace(_client=client, close=client.close)
        fake = SimpleNamespace(observer=observer, codex=codex, client=client,
                               thread_id="thread-private", turn_id="turn-private")
        observer.configure_provider_observer(provider, overrides, timeout=runner.timeout)
        capture = observer.provider_capture
        replies = []

        def open_runtime(_workspace, *, pilot_wire_observer):
            assert pilot_wire_observer is observer
            wire.install_runtime_observer(codex, observer)
            observer.bind_provider_runtime(codex)
            return codex

        def run_turn():
            for _ in range(32):
                replies.append(_post(capture.base_url))
            replies.append(_post(capture.base_url))
            if terminal is not None:
                client._coerce_notification("turn/completed", {
                    "threadId": fake.thread_id, "turn": {"id": fake.turn_id, "status": terminal},
                })
            return SimpleNamespace(final_response=CANARY, id=fake.turn_id, usage=None)

        def turn(text):
            client._write_message({"id": "rpc-turn", "method": "turn/start", "params": {
                "threadId": fake.thread_id, "input": [{"type": "text", "text": text}],
            }})
            client._router.route_response({"id": "rpc-turn", "result": {"turn": {"id": fake.turn_id}}})
            if with_usage:
                client._coerce_notification("thread/tokenUsage/updated", {
                    "threadId": fake.thread_id, "turnId": fake.turn_id, "tokenUsage": USAGE,
                })
            return SimpleNamespace(id=fake.turn_id, run=run_turn)

        def start_thread(*_args, **_kwargs):
            _start(fake)
            return SimpleNamespace(id=fake.thread_id, turn=turn)

        def collect():
            assert capture.closed and not capture.thread.is_alive()
            assert capture.server.socket.fileno() == -1
            assert process.poll() is not None and observer.provider_runtime is None
            return []

        monkeypatch.setattr(runner, "open_runtime", open_runtime)
        monkeypatch.setattr(runner, "start_thread", start_thread)
        workspace = SimpleNamespace(workspace=tmp_path, collect_deliverables=collect)
        try:
            outcome = runner._run_one_turn(workspace=workspace, task_text=CANARY,
                                          experiment_prompt={"system": "private developer text"},
                                          task_id="synthetic-task", pilot_wire_observer=observer)
            assert outcome.success is False and outcome.text == ""
            assert outcome.error == outcome.error_category == wire.NATIVE_REQUEST_CAP_EXCEEDED
            assert replies == [(200, _body())] * 32 + [(400, b"")]
            assert process.wait(timeout=1) is not None
            receipt = observer.finish(success=False, thread_id=outcome.thread_id, turn_id=outcome.turn_id)
            usage = observer.caps_usage_observer.verified()
        finally:
            observer.close_provider_observer()
            observer.close_provider_runtime()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=1)
    assert len(received) == len(timeouts) == receipt["provider_observation"]["native_request_count"] == 32
    assert receipt["provider_observation"]["native_request_blocked_count"] == 1
    assert receipt["provider_observation"]["native_request_cap_reason"] == wire.NATIVE_REQUEST_CAP_EXCEEDED
    assert receipt["correlation"]["status"] == terminal  # No invented terminal acknowledgement.
    assert usage["snapshots"] == receipt["usage"]["snapshots"]
    assert len(usage["snapshots"]) == int(with_usage)
    assert usage["threshold_observation"] == "native_request_cap_exceeded_usage_may_be_partial"
    projected = step2._bounded_codex_diagnostics({"provider_observation": receipt["provider_observation"]})
    assert projected["provider_observation"] == receipt["provider_observation"]
    assert step2.infra_retry_category({"status": "error", "observability": {
        "error_category": outcome.error_category}}) is None
    output = capsys.readouterr()
    assert all(value not in json.dumps(receipt) + json.dumps(projected) + output.out + output.err
               for value in (CANARY, UPSTREAM, "Bearer", capture.route))
