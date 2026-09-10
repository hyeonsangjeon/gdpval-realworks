"""The one probe entitled to say inference worked, and the guards on that claim.

Everything before this in the diagnostic asks the resource a question it can
answer without serving anybody: a listing, a body with no model in it, a bearer
that was never valid. Run ``34437632382`` finished that line of questioning --
all six header arms, up to and including every runtime header at once with
``stream: true``, still cleared the gate. No property the Codex runtime *adds*
is what refuses it.

What has never been sent to this resource is a request it could actually serve.
So nobody knows whether this identity may infer here at all, and the two
readings that remain -- "the model field resolves a deployment and a second
authorization check refuses it" and "the resource is fine and something
Codex-side is at fault" -- are not distinguishable from any record on disk.

This file is the instrument's test, not the answer. It pins the parts that make
the single request worth sending: that the body is servable, that there is
exactly one of it, that a `200` carrying no text is *not* reported as a
completion, and that the exit code means inference and nothing else. The probe
costs money on the real host; every host in this file is a socket on this
machine.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from diagnose_codex_foundry_connection import (  # noqa: E402
    NOT_ESTABLISHED_BY_A_VALID_REQUEST,
    VALID_REQUEST_ANSWER_KEPT_CHARS,
    VALID_REQUEST_ATTEMPTS,
    VALID_REQUEST_INPUT,
    VALID_REQUEST_MAX_OUTPUT_TOKENS,
    VALID_REQUEST_SCHEMA,
    VERDICT_INFERENCE_REFUSED_AT_THE_AUTH_GATE,
    VERDICT_INFERENCE_REQUEST_REJECTED,
    VERDICT_INFERENCE_SUCCEEDED,
    VERDICT_VALID_REQUEST_INCONCLUSIVE,
    classify_valid_request,
    main,
    valid_request_probe,
)

# The redirected settings, the fake token and the auth-command printer belong
# to the discriminator's tests. A second copy here would be a second thing to
# keep true.
from tests.test_codex_auth_discriminator import (  # noqa: E402
    FAKE_TOKEN,
    _printer,
    _settings,
    _with_auth_command,
)


def _no_redaction(value) -> str | None:
    """Identity, so a test reads the message the host actually sent."""
    return None if value is None else str(value)


class _Host:
    """A loopback host that answers with whatever payload the rule returns.

    The sweep's host only ever produces an error envelope, because no arm of a
    sweep can be served. This one has to be able to return a *completion*, so
    the rule hands back a whole body rather than a message string.
    """

    def __init__(self, rule: Callable[[dict, dict], tuple[int, Any]]):
        self.calls: list[dict] = []
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):  # noqa: D102 - silence the default
                pass

            def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler's spelling
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                headers = {k.lower(): v for k, v in self.headers.items()}
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except Exception:  # noqa: BLE001 - a body we cannot parse is data
                    parsed = {}
                with outer._lock:
                    outer.calls.append(
                        {"path": self.path, "headers": headers, "body": parsed}
                    )
                status, body = rule(headers, parsed)
                payload = (
                    body.encode("utf-8")
                    if isinstance(body, str)
                    else json.dumps(body).encode("utf-8")
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "_Host":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)


def _answers(text: str = "ok", *, usage: dict | None = None):
    """A host that completes, in the shape the Responses API returns."""

    def rule(_headers: dict, body: dict) -> tuple[int, Any]:
        payload: dict[str, Any] = {
            "id": "resp_test",
            "model": body.get("model"),
            "output_text": text,
        }
        if usage is not None:
            payload["usage"] = usage
        return 200, payload

    return rule


def _refuses(status: int, message: str):
    def rule(_headers: dict, _body: dict) -> tuple[int, Any]:
        return status, {"error": {"message": message}}

    return rule


def _probe(host: _Host, tmp_path: Path) -> dict:
    settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
    return valid_request_probe(settings, redact=_no_redaction)


# ── What goes on the wire ───────────────────────────────────────────────────


def test_the_body_is_a_request_the_route_can_actually_serve(tmp_path: Path):
    """The whole point, asserted rather than trusted.

    Every earlier probe deliberately sent something unservable. If this one
    drifted into doing the same -- a missing ``model``, an empty ``input`` --
    it would buy another `400` and answer nothing, while still being reported
    as the probe that was supposed to settle the question.
    """
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)
        sent = host.calls[0]["body"]

    assert sent["model"] == "a-deployment", sent
    assert sent["input"] == VALID_REQUEST_INPUT
    assert record["attempt"]["status"] == 200


def test_the_output_ceiling_is_on_the_wire_and_not_only_in_the_record(
    tmp_path: Path,
):
    """A limit that is written down but not sent is a limit on the report."""
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)
        sent = host.calls[0]["body"]

    assert sent["max_output_tokens"] == VALID_REQUEST_MAX_OUTPUT_TOKENS
    assert record["limits"]["max_output_tokens"] == VALID_REQUEST_MAX_OUTPUT_TOKENS
    assert record["attempt"]["max_output_tokens"] == VALID_REQUEST_MAX_OUTPUT_TOKENS


def test_nothing_is_streamed_and_nothing_is_stored(tmp_path: Path):
    """``stream`` off so one read gets the whole answer; ``store`` off so the
    prompt is not retained server-side by a diagnostic that had no reason to."""
    with _Host(_answers()) as host:
        _probe(host, tmp_path)
        sent = host.calls[0]["body"]

    assert sent["stream"] is False
    assert sent["store"] is False


def test_the_input_carries_no_benchmark_content(tmp_path: Path):
    """A diagnostic prompt, kept trivial and public on purpose."""
    with _Host(_answers()) as host:
        _probe(host, tmp_path)
        sent = host.calls[0]["body"]

    assert isinstance(sent["input"], str)
    assert len(sent["input"]) < 120, "this is a status check, not a task"


def test_the_minted_bearer_is_what_is_sent(tmp_path: Path):
    """Same credential the runtime uses; a probe on a different one proves
    nothing about the runtime's refusal."""
    with _Host(_answers()) as host:
        _probe(host, tmp_path)
        headers = host.calls[0]["headers"]

    assert headers["authorization"] == f"Bearer {FAKE_TOKEN}"


def test_the_request_goes_to_responses_under_the_configured_base_url(
    tmp_path: Path,
):
    """The address has been cleared as a cause once; keep it cleared."""
    with _Host(_answers()) as host:
        _probe(host, tmp_path)

    assert host.calls[0]["path"] == "/v1/responses"


# ── Exactly one of them ─────────────────────────────────────────────────────


def test_one_request_is_sent_when_it_succeeds(tmp_path: Path):
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    assert len(host.calls) == 1
    assert record["requests_sent"] == 1
    assert record["requests_planned"] == VALID_REQUEST_ATTEMPTS == 1


def test_a_refusal_is_not_retried(tmp_path: Path):
    """The ceiling that matters most. A retry loop added later would multiply
    the cost of every future failure silently, so the count is asserted on the
    failing path and not just on the happy one."""
    with _Host(_refuses(401, "Access denied")) as host:
        record = _probe(host, tmp_path)

    assert len(host.calls) == 1
    assert record["requests_sent"] == 1
    assert "no retry" in record["limits"]["abort_on"]


def test_the_limits_are_declared_in_the_record(tmp_path: Path):
    """Pre-declared, so a run that exceeded them is visibly a different run."""
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    limits = record["limits"]
    assert limits["attempts"] == 1
    assert limits["concurrency"] == 1
    assert limits["timeout_seconds"] > 0
    assert limits["abort_on"]


# ── Reading the answer, and refusing to overstate it ────────────────────────


def test_two_hundred_with_text_is_the_only_success(tmp_path: Path):
    with _Host(_answers("ok")) as host:
        record = _probe(host, tmp_path)

    assert record["verdict"] == VERDICT_INFERENCE_SUCCEEDED
    assert record["attempt"]["answer"] == "ok"
    assert record["attempt"]["model_echoed"] == "a-deployment"


def test_the_other_response_shape_is_read_too(tmp_path: Path):
    """Responses bodies carry text in ``output[].content[].text`` as well as in
    ``output_text``. Missing one would report a real completion as a failure."""

    def rule(_headers: dict, _body: dict) -> tuple[int, Any]:
        return 200, {
            "output": [{"content": [{"type": "output_text", "text": "ok"}]}],
        }

    with _Host(rule) as host:
        record = _probe(host, tmp_path)

    assert record["verdict"] == VERDICT_INFERENCE_SUCCEEDED
    assert record["attempt"]["answer"] == "ok"


def test_two_hundred_without_text_is_not_reported_as_inference(tmp_path: Path):
    """The guard this probe exists to have.

    A status is not a completion. Every previous finding in this diagnostic was
    a status read for more than it said, and the one probe allowed to claim
    inference must be the strictest about it.
    """

    def rule(_headers: dict, _body: dict) -> tuple[int, Any]:
        return 200, {"id": "resp_test", "output": []}

    with _Host(rule) as host:
        record = _probe(host, tmp_path)

    assert record["verdict"] == VERDICT_VALID_REQUEST_INCONCLUSIVE
    assert record["verdict"] != VERDICT_INFERENCE_SUCCEEDED
    assert record["attempt"]["answer"] is None


def test_whitespace_is_not_an_answer(tmp_path: Path):
    with _Host(_answers("   \n  ")) as host:
        record = _probe(host, tmp_path)

    assert record["verdict"] == VERDICT_VALID_REQUEST_INCONCLUSIVE


def test_the_ceiling_is_large_enough_for_a_model_that_reasons_first():
    """The failure mode that would have wasted the decisive request.

    The deployments this is pointed at spend output tokens on reasoning before
    emitting any text. At the API's minimum of 16 the ceiling is consumed
    entirely by that, and the answer comes back `200 incomplete` with no text
    -- correctly refused as a success, and therefore one paid request spent on
    an artefact of this probe's own configuration.
    """
    assert VALID_REQUEST_MAX_OUTPUT_TOKENS >= 256


def test_a_truncated_answer_names_the_ceiling_rather_than_blaming_the_route(
    tmp_path: Path,
):
    """A `200 incomplete` is a model that ran, not a route that said nothing.

    Reported as inconclusive -- no text is no completion -- but the note has to
    say which of the two it was, or the next reader repairs the wrong thing.
    """

    def rule(_headers: dict, _body: dict) -> tuple[int, Any]:
        return 200, {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [],
            "usage": {"input_tokens": 9, "output_tokens": 512},
        }

    with _Host(rule) as host:
        record = _probe(host, tmp_path)

    assert record["verdict"] == VERDICT_VALID_REQUEST_INCONCLUSIVE
    assert record["attempt"]["response_status"] == "incomplete"
    assert record["attempt"]["incomplete_reason"] == "max_output_tokens"
    note = record["verdict_note"]
    assert "the model ran" in note
    assert "not free" in note
    assert str(VALID_REQUEST_MAX_OUTPUT_TOKENS) in note


def test_a_completed_response_records_its_api_status_too(tmp_path: Path):
    """The Responses status is not the HTTP status; both are written down."""

    def rule(_headers: dict, _body: dict) -> tuple[int, Any]:
        return 200, {"status": "completed", "output_text": "ok"}

    with _Host(rule) as host:
        record = _probe(host, tmp_path)

    assert record["verdict"] == VERDICT_INFERENCE_SUCCEEDED
    assert record["attempt"]["response_status"] == "completed"
    assert record["attempt"]["incomplete_reason"] is None


@pytest.mark.parametrize("status", [401, 403])
def test_a_refusal_at_the_gate_is_named_as_one(tmp_path: Path, status: int):
    """The finding no earlier probe could produce: a *servable* request
    refused. That is a permission fact, unlike a `400` on a body nothing could
    serve."""
    with _Host(_refuses(status, "Access denied")) as host:
        record = _probe(host, tmp_path)

    assert record["verdict"] == VERDICT_INFERENCE_REFUSED_AT_THE_AUTH_GATE
    assert str(status) in record["verdict_note"]


@pytest.mark.parametrize("status", [400, 404, 429, 500])
def test_other_statuses_are_rejections_and_never_successes(
    tmp_path: Path, status: int
):
    with _Host(_refuses(status, "nope")) as host:
        record = _probe(host, tmp_path)

    assert record["verdict"] == VERDICT_INFERENCE_REQUEST_REJECTED
    assert record["verdict"] != VERDICT_INFERENCE_SUCCEEDED


def test_a_transport_failure_is_inconclusive_not_a_refusal(tmp_path: Path):
    """Nothing reached a status, so nothing was learned about the identity."""
    with _Host(_answers()) as host:
        port = host.port
    settings = _with_auth_command(_settings(port), _printer(tmp_path))
    record = valid_request_probe(settings, redact=_no_redaction, timeout=2)

    assert record["verdict"] == VERDICT_VALID_REQUEST_INCONCLUSIVE
    assert record["attempt"]["error"]
    assert record["attempt"]["status"] is None


def test_the_answer_is_capped(tmp_path: Path):
    """A model that ignored the ceiling cannot spill into the artifact."""
    with _Host(_answers("y" * 5000)) as host:
        record = _probe(host, tmp_path)

    assert len(record["attempt"]["answer"]) == VALID_REQUEST_ANSWER_KEPT_CHARS


# ── Usage, without inventing a price ────────────────────────────────────────


def test_usage_is_recorded_with_no_price_attached(tmp_path: Path):
    """Counts are measured; the rate is not registered here. Filling
    ``price_usd`` would put a number in a ledger that nothing measured."""
    usage = {"input_tokens": 11, "output_tokens": 2, "total_tokens": 13}
    with _Host(_answers("ok", usage=usage)) as host:
        record = _probe(host, tmp_path)

    reported = record["attempt"]["usage"]
    assert reported["reported"] is True
    assert reported["input_tokens"] == 11
    assert reported["output_tokens"] == 2
    assert reported["price_usd"] is None
    assert reported["pricing"] == "partial"


def test_a_response_without_usage_is_null_and_not_zero(tmp_path: Path):
    """A missing count is unknown. Zero is a measurement."""
    with _Host(_answers("ok")) as host:
        record = _probe(host, tmp_path)

    reported = record["attempt"]["usage"]
    assert reported["reported"] is False
    assert reported["input_tokens"] is None
    assert reported["pricing"] == "null"
    assert reported["price_usd"] is None


# ── The record ──────────────────────────────────────────────────────────────


def test_the_record_admits_it_asked_for_inference(tmp_path: Path):
    """The redaction check tells free records from paid ones by this field.
    Writing ``false`` to stay in the cheap branch is the lie it is built to
    catch, so the truth is asserted at the source."""
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    assert record["schema"] == VALID_REQUEST_SCHEMA
    assert record["inference_requested"] is True


def test_no_token_survives_into_the_record(tmp_path: Path):
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    assert FAKE_TOKEN not in json.dumps(record)
    assert record["token"] == {
        "minted": True,
        "mechanism": "auth_command",
        "error": None,
    }


def test_the_resource_is_named_only_by_fingerprint(tmp_path: Path):
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    assert record["settings_fingerprint"].startswith("sha256:")
    assert record["endpoint_host_fingerprint"].startswith("sha256:")
    assert "example-account" not in json.dumps(record)


def test_a_mint_failure_sends_nothing(tmp_path: Path):
    """No token, no request, no cost -- and a record saying so."""
    with _Host(_answers()) as host:
        settings = _with_auth_command(
            _settings(host.port), [sys.executable, "-c", "raise SystemExit(3)"]
        )
        record = valid_request_probe(settings, redact=_no_redaction)
        calls = list(host.calls)

    assert calls == []
    assert record["requests_sent"] == 0
    assert record["token"]["minted"] is False
    assert record["verdict"] == VERDICT_VALID_REQUEST_INCONCLUSIVE
    assert "nothing was sent" in record["verdict_note"]


def test_the_record_says_what_a_completion_would_still_not_prove(tmp_path: Path):
    """A `200` here is the best result this diagnostic can produce and it is
    still four steps short of a benchmark run. The limits ride with the record
    so the good news cannot travel without them."""
    with _Host(_answers()) as host:
        record = _probe(host, tmp_path)

    assert record["not_established"] == list(NOT_ESTABLISHED_BY_A_VALID_REQUEST)
    joined = " ".join(record["not_established"])
    assert "220-task" in joined
    assert "not that the Codex runtime can" in joined
    assert "partial" in joined


def test_the_classifier_never_calls_an_unread_status_a_success():
    """Belt and braces on the one verdict that may not be wrong."""
    for attempt in (
        {"status": 200, "answer": None},
        {"status": 401, "answer": "ok"},
        {"status": 400, "answer": "ok"},
        {"status": None, "error": "boom"},
        {"status": 200, "answer": "", "error": None},
    ):
        verdict, note = classify_valid_request(attempt)
        assert verdict != VERDICT_INFERENCE_SUCCEEDED, attempt
        assert note


# ── The workflow wiring ─────────────────────────────────────────────────────


def _valid_request_record() -> dict:
    return {
        "schema": VALID_REQUEST_SCHEMA,
        "inference_requested": True,
        "settings": {"model": "a-deployment"},
        "token": {"minted": True, "mechanism": "auth_command", "error": None},
        "requests_planned": 1,
        "requests_sent": 1,
        "attempt": {"status": 200, "answer": "ok", "usage": {"pricing": "partial"}},
        "verdict": VERDICT_INFERENCE_SUCCEEDED,
        "not_established": ["urllib, not the runtime; unpriced; not a task solved"],
    }


def _steps() -> list[dict]:
    import yaml

    from tests.test_codex_auth_discriminator import WORKFLOW

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return parsed["jobs"]["diagnose"]["steps"]


def _step() -> dict:
    return next(s for s in _steps() if s.get("id") == "valid_request")


def test_the_paid_step_is_off_unless_it_is_asked_for_and_pinned():
    """Two conditions, like the turn's. The input is the person's intention
    and the fingerprint is the machine's evidence that the intention is about
    the right resource; intention alone once bought a paid call."""
    guard = _step()["if"]
    assert "inputs.send_valid_request" in guard
    assert "steps.pinned.outputs.confirmed == 'yes'" in guard


def test_the_input_defaults_to_off():
    import yaml

    from tests.test_codex_auth_discriminator import WORKFLOW

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # `on:` parses as the boolean True in YAML 1.1, which is why this is not
    # spelled the obvious way.
    inputs = parsed[True]["workflow_dispatch"]["inputs"]
    assert inputs["send_valid_request"]["default"] is False


def test_the_paid_step_cannot_also_buy_a_codex_turn():
    """One purchase per step. ``--send-request`` here would spend twice from a
    step whose ceilings only describe one of them."""
    run = _step()["run"]
    assert "--valid-request" in run
    assert "--send-request" not in run


def test_the_step_fails_if_it_sent_more_than_it_planned():
    """The ceiling that costs money if it slips, checked on the wire count
    rather than on the constant."""
    run = _step()["run"]
    assert "requests_sent" in run and "requests_planned" in run
    assert 'record["token"]["minted"]' in run


def test_the_summary_reports_whether_text_came_back_not_the_text():
    """A model's words do not belong in a job summary; whether there were any
    is the whole finding."""
    summary = next(s for s in _steps() if s.get("name") == "Summary")["run"]
    assert "VR_TEXT=" in summary
    assert "bool(" in summary
    assert "VR_PRICING" in summary


def test_the_record_is_published_with_the_others():
    keep = next(s for s in _steps() if s.get("name") == "Keep the record")
    assert "/tmp/codex-foundry-valid-request.json" in keep["with"]["path"]


def test_the_leak_check_reads_it_by_its_real_path():
    from tests.test_codex_auth_discriminator import _leak_check_source

    assert '"/tmp/codex-foundry-valid-request.json"' in _leak_check_source()


def test_the_leak_check_accepts_a_valid_request_record(tmp_path: Path):
    from tests.test_codex_auth_discriminator import _run_leak_check

    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-valid-request.json": _valid_request_record()}
    )
    assert code == 0, output
    assert "record=clean (1 checked)" in output


def test_the_leak_check_refuses_a_paid_record_that_denies_being_paid(
    tmp_path: Path,
):
    """The free branch is the cheap branch. A paid record claiming
    ``inference_requested: false`` would hide a real request inside it."""
    from tests.test_codex_auth_discriminator import _run_leak_check

    record = _valid_request_record()
    record["inference_requested"] = False
    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-valid-request.json": record}
    )
    assert code == 1
    assert "denies sending a request" in output


def test_the_leak_check_refuses_a_record_that_sent_more_than_it_planned(
    tmp_path: Path,
):
    from tests.test_codex_auth_discriminator import _run_leak_check

    record = _valid_request_record()
    record["requests_sent"] = 4
    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-valid-request.json": record}
    )
    assert code == 1
    assert "more requests than it planned" in output


def test_an_unrecognised_schema_is_withheld_rather_than_waved_through(
    tmp_path: Path,
):
    """The branch that used to be the turn's ``else``.

    A new record shape landing in a branch written for a different one is how
    the sweep record crashed this check in CI. That crash was safe by luck; on
    the paid probe it would mean the money was already spent and the evidence
    thrown away. An unknown schema is now refused by name.
    """
    from tests.test_codex_auth_discriminator import _run_leak_check

    record = _valid_request_record()
    record["schema"] = "codex_foundry_something_new/1"
    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-valid-request.json": record}
    )
    assert code == 1
    assert "has no check here" in output


def test_the_turn_record_still_has_its_own_check(tmp_path: Path):
    """Naming the branches must not have quietly dropped one."""
    from tests.test_codex_auth_discriminator import _run_leak_check

    record = {
        "schema": "codex_foundry_connection/2",
        "verdict": "not_sent",
        "observed": {"tool_execution_observed": True},
    }
    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-connection.json": record}
    )
    assert code == 1
    assert "claims tool execution" in output


# ── The command line ────────────────────────────────────────────────────────


def _run_main(host: _Host, tmp_path: Path, monkeypatch) -> tuple[int, dict]:
    import diagnose_codex_foundry_connection as module

    monkeypatch.setattr(
        module,
        "settings_from_environment",
        lambda *_a, **_k: _with_auth_command(_settings(host.port), _printer(tmp_path)),
    )
    out = tmp_path / "valid.json"
    code = main(
        ["--deployment", "a-deployment", "--valid-request", "--out", str(out)]
    )
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_exit_zero_means_inference_worked(tmp_path: Path, monkeypatch):
    with _Host(_answers("ok")) as host:
        code, written = _run_main(host, tmp_path, monkeypatch)

    assert code == 0
    assert written["verdict"] == VERDICT_INFERENCE_SUCCEEDED


def test_a_refusal_does_not_exit_zero_however_informative_it_is(
    tmp_path: Path, monkeypatch
):
    """A `401` here would be the most useful thing this script has ever
    produced, and it is still not inference working. The exit code answers one
    question and nothing else may borrow it."""
    with _Host(_refuses(401, "Access denied")) as host:
        code, written = _run_main(host, tmp_path, monkeypatch)

    assert code == 1
    assert written["verdict"] == VERDICT_INFERENCE_REFUSED_AT_THE_AUTH_GATE


def test_a_two_hundred_without_text_does_not_exit_zero(tmp_path: Path, monkeypatch):
    def rule(_headers: dict, _body: dict) -> tuple[int, Any]:
        return 200, {"output": []}

    with _Host(rule) as host:
        code, _written = _run_main(host, tmp_path, monkeypatch)

    assert code == 1


def test_it_refuses_to_run_beside_the_other_probes(capsys):
    """They write different records to the same ``--out``; one would win."""
    for extra in (
        ["--read-only-probe"],
        ["--send-request"],
        ["--auth-discriminator"],
        ["--transmission-sweep"],
    ):
        with pytest.raises(SystemExit):
            main(["--deployment", "d", "--valid-request", *extra])
        assert "run them separately" in capsys.readouterr().err
