"""Which request property closes a gate that the plain request gets through.

Run ``34361684546`` established the check order on the real host: a plainly
invalid bearer is stopped at the gate, and the minted bearer gets past it to
the part that reads the body. The Codex runtime sends *that same minted token
to that same URL* and is answered at the gate, with the control arm's sentence
word for word. Four transmission explanations were then measured offline and
all four are false -- the header is present, it is a ``Bearer``, its value is
exactly what the auth command printed, and no second credential rides along.

So the difference is somewhere in the rest of what the runtime puts on the
wire. The sweep adds those properties to a request already known to clear the
gate, one at a time, and reports which one -- if any -- closes it.

The tests here are about the *instrument*. A sweep is only worth its requests
if each arm sends the property it names, if the count is what the record says,
and if it reports "nothing closed the gate" as an answer rather than as a
failure. Every host in this file is a socket on this machine; nothing here
mints a token or leaves loopback.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from diagnose_codex_foundry_connection import (  # noqa: E402
    CODEX_ACCEPT,
    CODEX_ORIGINATOR,
    CODEX_RUNTIME_HEADERS,
    CODEX_USER_AGENT,
    MALFORMED_TURN_BODY,
    OBVIOUSLY_INVALID_BEARER,
    SWEEP_ARMS,
    SWEEP_SCHEMA,
    VERDICT_A_REQUEST_PROPERTY_CLOSES_THE_GATE,
    VERDICT_NO_REQUEST_PROPERTY_CLOSES_THE_GATE,
    VERDICT_SWEEP_INCONCLUSIVE,
    classify_sweep,
    main,
    transmission_sweep,
)

# The redirected settings, the fake token and the auth-command printer are the
# discriminator's. A second copy here would be a second thing to keep true.
from tests.test_codex_auth_discriminator import (  # noqa: E402
    FAKE_TOKEN,
    _printer,
    _settings,
    _with_auth_command,
)


def _no_redaction(value) -> str | None:
    """Identity, so a test reads the message the host sent.

    The production caller passes the real redactor; these tests are about which
    arm got which status, and routing them through a redactor would mean a
    failure could be the redactor's rather than the sweep's.
    """
    return None if value is None else str(value)


class _ScriptedHost:
    """Answers ``POST /responses`` according to a rule over the request.

    The rule takes the lowercased headers and the parsed body and returns
    ``(status, message)``. That is what lets a test script "this host refuses
    anything carrying ``originator``" and then check that the sweep names
    ``originator`` -- rather than checking that the sweep names whatever it
    was going to name anyway.
    """

    def __init__(self, rule: Callable[[dict, dict], tuple[int, str]]):
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
                status, message = rule(headers, parsed)
                payload = json.dumps({"error": {"message": message}}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "_ScriptedHost":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)

    @property
    def minted_calls(self) -> list[dict]:
        """Everything but the control arm, in the order the sweep sent it."""
        return [
            call
            for call in self.calls
            if OBVIOUSLY_INVALID_BEARER not in call["headers"].get("authorization", "")
        ]


def _sweep(host: _ScriptedHost, tmp_path: Path) -> dict:
    settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
    return transmission_sweep(settings, redact=_no_redaction)


def _gate_on(predicate: Callable[[dict, dict], bool]):
    """A host that refuses at the gate exactly when ``predicate`` holds."""

    def rule(headers: dict, body: dict) -> tuple[int, str]:
        if OBVIOUSLY_INVALID_BEARER in headers.get("authorization", ""):
            return 401, "Access denied due to invalid subscription key"
        if predicate(headers, body):
            return 401, "Access denied due to invalid subscription key"
        return 400, "Missed model deployment"

    return rule


def _never_at_the_gate(headers: dict, body: dict) -> tuple[int, str]:
    return _gate_on(lambda _h, _b: False)(headers, body)


# ── The promise that makes this free ────────────────────────────────────────


def test_no_arm_can_select_a_deployment():
    """The whole cost argument, asserted rather than commented.

    Every arm is a POST to a live inference route. What keeps that from being
    a purchase is that no body names a model, so there is no deployment for a
    completion to be billed against. An arm that grew a ``model`` key would
    break that quietly, which is why the sweep also raises on it at runtime.
    """
    for name, _headers, body, _why in SWEEP_ARMS:
        if body is None:
            continue
        assert "model" not in body, f"arm {name!r} names a model"
        assert "input" not in body, f"arm {name!r} carries input"
        assert "messages" not in body, f"arm {name!r} carries messages"


def test_an_arm_that_named_a_model_stops_the_run_before_it_starts(
    tmp_path: Path, monkeypatch
):
    """And it stops before the token is minted, not after the arms are sent."""
    import diagnose_codex_foundry_connection as module

    monkeypatch.setattr(
        module,
        "SWEEP_ARMS",
        (("bad", {}, {**MALFORMED_TURN_BODY, "model": "a-deployment"}, "why"),),
    )
    with _ScriptedHost(_never_at_the_gate) as host:
        with pytest.raises(ValueError, match="names a model"):
            _sweep(host, tmp_path)
        assert host.calls == [], "an arm was sent before the guard ran"


# ── Does each arm send what it says it sends ────────────────────────────────


def test_the_sweep_sends_one_request_per_arm_and_one_control(tmp_path: Path):
    """The count in the record is the count on the wire, not a constant."""
    with _ScriptedHost(_never_at_the_gate) as host:
        record = _sweep(host, tmp_path)

    assert record["schema"] == SWEEP_SCHEMA
    assert len(host.calls) == len(SWEEP_ARMS) + 1
    assert record["requests_sent"] == len(host.calls)
    assert record["requests_planned"] == record["requests_sent"]
    assert {call["path"] for call in host.calls} == {"/v1/responses"}


def test_each_arm_puts_on_the_wire_exactly_the_property_it_names(tmp_path: Path):
    """An arm that does not send its property measures nothing and says so.

    This is the failure that would be invisible: every arm comes back 400, the
    verdict reads ``no_request_property_closes_the_auth_gate``, and it means
    only that the sweep never varied anything. So the arms are checked against
    the wire one by one.
    """
    with _ScriptedHost(_never_at_the_gate) as host:
        _sweep(host, tmp_path)

    sent = host.minted_calls
    assert len(sent) == len(SWEEP_ARMS)
    by_arm = {name: sent[i] for i, (name, _h, _b, _w) in enumerate(SWEEP_ARMS)}

    baseline = by_arm["baseline"]
    assert baseline["headers"]["accept"] == "application/json"
    assert "originator" not in baseline["headers"]
    assert baseline["body"] == MALFORMED_TURN_BODY
    assert "stream" not in baseline["body"]

    assert by_arm["accept_event_stream"]["headers"]["accept"] == CODEX_ACCEPT
    assert "originator" not in by_arm["accept_event_stream"]["headers"]

    originator_arm = by_arm["originator_and_user_agent"]
    assert originator_arm["headers"]["originator"] == CODEX_ORIGINATOR
    assert originator_arm["headers"]["user-agent"] == CODEX_USER_AGENT
    assert originator_arm["headers"]["accept"] == "application/json"

    runtime_arm = by_arm["codex_runtime_headers"]
    for header in CODEX_RUNTIME_HEADERS:
        assert runtime_arm["headers"].get(header) == CODEX_RUNTIME_HEADERS[header]
    assert "originator" not in runtime_arm["headers"]

    # Deliberately the body field on its own: sending it with the Accept that
    # usually accompanies it would make a flip un-attributable to either.
    stream_arm = by_arm["stream_true"]
    assert stream_arm["body"].get("stream") is True
    assert stream_arm["headers"]["accept"] == "application/json"

    everything = by_arm["everything"]
    assert everything["body"].get("stream") is True
    assert everything["headers"]["accept"] == CODEX_ACCEPT
    assert everything["headers"]["originator"] == CODEX_ORIGINATOR
    for header in CODEX_RUNTIME_HEADERS:
        assert everything["headers"].get(header) == CODEX_RUNTIME_HEADERS[header]


def test_every_arm_carries_the_minted_bearer_and_only_the_control_does_not(
    tmp_path: Path,
):
    """A varied arm that lost its credential would flip for the wrong reason."""
    with _ScriptedHost(_never_at_the_gate) as host:
        _sweep(host, tmp_path)

    minted = [call["headers"]["authorization"] for call in host.minted_calls]
    assert minted == [f"Bearer {FAKE_TOKEN}"] * len(SWEEP_ARMS)
    controls = [
        call["headers"]["authorization"]
        for call in host.calls
        if call not in host.minted_calls
    ]
    assert controls == [f"Bearer {OBVIOUSLY_INVALID_BEARER}"]


def test_the_synthetic_identifiers_carry_nothing_from_this_machine(tmp_path: Path):
    """The runtime's own session ids name an installation; these do not.

    Replaying the measured identifiers would put a machine identifier on
    someone else's host to test a question about header *shape*. The stand-ins
    are the same shape and mean nothing, and ``x-codex-turn-metadata`` stays
    real JSON so a gateway that parses it does not reject it for the wrong
    reason.
    """
    metadata = json.loads(CODEX_RUNTIME_HEADERS["x-codex-turn-metadata"])
    assert set(metadata) >= {"installation_id", "session_id", "turn_id"}
    for key in ("installation_id", "session_id", "thread_id", "turn_id"):
        assert metadata[key] == "00000000-0000-7000-8000-000000000000"
    assert metadata["turn_started_at_unix_ms"] == 0


# ── Reading the arms ────────────────────────────────────────────────────────


def test_a_property_that_closes_the_gate_is_named(tmp_path: Path):
    """The result this sweep exists to produce, against a host that has one."""
    with _ScriptedHost(
        _gate_on(lambda headers, _body: "originator" in headers)
    ) as host:
        record = _sweep(host, tmp_path)

    assert record["verdict"] == VERDICT_A_REQUEST_PROPERTY_CLOSES_THE_GATE
    assert record["properties_that_closed_the_gate"] == [
        "originator_and_user_agent",
        "everything",
    ]
    assert "originator_and_user_agent" in record["verdict_note"]
    assert record["arms"]["baseline"]["status"] == 400
    assert record["arms"]["originator_and_user_agent"]["status"] == 401


def test_a_body_field_can_be_the_one_that_closes_it(tmp_path: Path):
    """Headers are the likelier answer; the sweep must not assume they are."""
    with _ScriptedHost(
        _gate_on(lambda _headers, body: body.get("stream") is True)
    ) as host:
        record = _sweep(host, tmp_path)

    assert record["verdict"] == VERDICT_A_REQUEST_PROPERTY_CLOSES_THE_GATE
    assert record["properties_that_closed_the_gate"] == ["stream_true", "everything"]


def test_nothing_closing_the_gate_is_an_answer_and_says_where_to_look_next(
    tmp_path: Path,
):
    """A null result moves the question to the body rather than ending it."""
    with _ScriptedHost(_never_at_the_gate) as host:
        record = _sweep(host, tmp_path)

    assert record["verdict"] == VERDICT_NO_REQUEST_PROPERTY_CLOSES_THE_GATE
    assert record["properties_that_closed_the_gate"] == []
    assert "the body" in record["verdict_note"]


def test_only_the_combination_closing_it_is_reported_as_a_combination(
    tmp_path: Path,
):
    """Isolated arms buy this distinction; the record has to keep it."""
    with _ScriptedHost(
        _gate_on(
            lambda headers, body: "originator" in headers and body.get("stream") is True
        )
    ) as host:
        record = _sweep(host, tmp_path)

    assert record["verdict"] == VERDICT_A_REQUEST_PROPERTY_CLOSES_THE_GATE
    assert record["properties_that_closed_the_gate"] == ["everything"]
    assert "needs more than one" in record["verdict_note"]


# ── The premise, re-tested every run ────────────────────────────────────────


def test_a_control_that_is_not_stopped_at_the_gate_voids_every_arm(tmp_path: Path):
    """Without the check order, a 401 on an arm is not about authorization."""

    def rule(headers: dict, _body: dict) -> tuple[int, str]:
        return 400, "this host reads the body first"

    with _ScriptedHost(rule) as host:
        record = _sweep(host, tmp_path)

    assert record["verdict"] == VERDICT_SWEEP_INCONCLUSIVE
    assert "control" in record["verdict_note"]
    assert record["properties_that_closed_the_gate"] == []


def test_a_baseline_that_no_longer_clears_the_gate_is_inconclusive(tmp_path: Path):
    """If the plain request is refused too, the sweep's question has moved.

    Reporting every arm as a flip here would be the worst failure available:
    it names five properties as causes on a host where none of them is doing
    anything.
    """
    with _ScriptedHost(_gate_on(lambda _h, _b: True)) as host:
        record = _sweep(host, tmp_path)

    assert record["verdict"] == VERDICT_SWEEP_INCONCLUSIVE
    assert record["properties_that_closed_the_gate"] == []


def test_a_mint_failure_sends_no_arm_at_all(tmp_path: Path):
    """No token, no requests -- and a record that says it measured nothing."""
    failing = tmp_path / "fails.py"
    failing.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    with _ScriptedHost(_never_at_the_gate) as host:
        settings = _with_auth_command(
            _settings(host.port), [sys.executable, str(failing)]
        )
        record = transmission_sweep(settings, redact=_no_redaction)
        assert host.calls == []

    assert record["verdict"] == VERDICT_SWEEP_INCONCLUSIVE
    assert record["token"]["minted"] is False
    assert record["requests_sent"] == 0
    assert "measures nothing" in record["verdict_note"]


def test_a_transport_failure_on_the_control_is_not_read_as_a_flip(tmp_path: Path):
    """A control that never arrived is an absent control, not a passing one."""
    assert (
        classify_sweep(
            {"baseline": {"status": 400}, "accept_event_stream": {"status": 401}},
            {"status": None, "error": "URLError: nothing listening"},
        )[0]
        == VERDICT_SWEEP_INCONCLUSIVE
    )


# ── What the record does and does not carry ─────────────────────────────────


def test_the_record_names_no_resource_and_carries_no_token(tmp_path: Path):
    """The account name and the token stay out; the deployment stays in.

    The deployment is what the diagnostic is *about* and every record in this
    script carries it. What must not appear is the account -- the host is a
    ``sha256:`` fingerprint for that reason -- and the bearer.
    """
    with _ScriptedHost(_never_at_the_gate) as host:
        record = _sweep(host, tmp_path)

    serialised = json.dumps(record)
    assert FAKE_TOKEN not in serialised
    assert "example-account" not in serialised
    assert record["inference_requested"] is False
    assert record["endpoint_host_fingerprint"].startswith("sha256:")
    assert all(len(arm["body_sha256"]) == 64 for arm in record["arms"].values())


def test_the_record_states_what_it_cannot_settle(tmp_path: Path):
    """Including, in every run, that these arms are not the runtime."""
    with _ScriptedHost(_never_at_the_gate) as host:
        record = _sweep(host, tmp_path)

    joined = " ".join(record["not_established"])
    assert "urllib" in joined
    assert "unpriced" in joined
    assert "not a reason to request a role" in joined


def test_the_record_separates_check_order_from_what_the_identity_may_do(
    tmp_path: Path,
):
    """A 400 is the gate letting an unservable body through, nothing more.

    Reading it as "inference would be permitted" is the specific mistake this
    sweep is most able to invite, because every arm it sends is deliberately
    unservable: the thing that would prove a servable body is served is the
    one thing no arm here may carry. So the limit is asserted rather than
    left to whoever writes the summary.
    """
    with _ScriptedHost(_never_at_the_gate) as host:
        record = _sweep(host, tmp_path)

    permission = [
        line for line in record["not_established"] if line.startswith("the permission:")
    ]
    assert len(permission) == 1, record["not_established"]
    assert "not what the identity may do" in permission[0]
    assert "does not show that a servable body would be served" in permission[0]


def test_each_arm_reports_the_body_it_actually_hashed(tmp_path: Path):
    """Two arms differ in body; the hashes have to differ with them."""
    with _ScriptedHost(_never_at_the_gate) as host:
        record = _sweep(host, tmp_path)

    plain = record["arms"]["baseline"]["body_sha256"]
    assert record["arms"]["accept_event_stream"]["body_sha256"] == plain
    assert record["arms"]["stream_true"]["body_sha256"] != plain
    assert record["arms"]["everything"]["body_sha256"] != plain


def test_a_refusal_identical_to_the_control_is_flagged_as_identical(tmp_path: Path):
    """The comparison that made the 401 readable, kept per arm.

    An arm answered with the control's exact sentence is the shape the paid
    turn produced. Recording the comparison per arm is what would let a future
    reader see it happen rather than infer it.
    """
    with _ScriptedHost(
        _gate_on(lambda headers, _b: "originator" in headers)
    ) as host:
        record = _sweep(host, tmp_path)

    assert record["arms"]["originator_and_user_agent"]["same_message_as_control"] is True
    assert record["arms"]["baseline"]["same_message_as_control"] is False
    assert record["arms"]["baseline"]["same_message_as_baseline"] is True


# ── The values, bound to the runtime they were read from ───────────────────


def test_the_replayed_values_are_the_ones_the_runtime_actually_sends(tmp_path: Path):
    """Guessing these would have been wrong twice, so they are not guessed.

    The originator is ``codex_python_sdk`` -- not the ``codex_cli_rs`` a
    reader would expect from the CLI -- and the runtime asks for
    ``text/event-stream``, not JSON. Both were read off the wire, and both are
    checked against it here: a sweep that replays a value the runtime stopped
    sending is testing a header nobody sends, and would come back null for a
    reason that has nothing to do with the host.
    """
    pytest.importorskip("tests.test_what_one_codex_turn_actually_sends")
    from tests.test_what_one_codex_turn_actually_sends import (
        _RUNTIME_PROBLEM,
        _one_refused_turn,
    )

    if _RUNTIME_PROBLEM is not None:
        pytest.skip(f"the pinned Codex runtime is not installed: {_RUNTIME_PROBLEM}")

    measured = _one_refused_turn(tmp_path)
    assert measured["calls"], "no request arrived, so nothing was compared"
    names = set(measured["calls"][0]["header_names"])
    values = measured["calls"][0]["header_values"]

    missing = set(CODEX_RUNTIME_HEADERS) - names
    assert not missing, (
        f"the sweep replays {sorted(missing)}, which this runtime no longer "
        f"sends. Those arms would be testing headers nobody sends"
    )
    assert values.get("originator") == CODEX_ORIGINATOR, (
        f"the sweep replays originator={CODEX_ORIGINATOR!r}; this runtime "
        f"sends {values.get('originator')!r}"
    )
    assert values.get("accept") == CODEX_ACCEPT, (
        f"the sweep replays Accept={CODEX_ACCEPT!r}; this runtime asks for "
        f"{values.get('accept')!r}"
    )
    # The user-agent carries a version, so the pinned version is the part
    # worth binding: a bump that changed it would make the replay a different
    # string from the one the host sees from the runtime.
    assert values.get("user-agent", "").startswith("codex_python_sdk/"), values.get(
        "user-agent"
    )
    assert CODEX_USER_AGENT.startswith("codex_python_sdk/")

    body = json.loads(measured["calls"][0]["body"].decode("utf-8"))
    assert body.get("stream") is True, (
        "the sweep's stream_true arm reproduces a body field the runtime no "
        "longer sets"
    )


# ── The step that runs it ───────────────────────────────────────────────────


def _sweep_record() -> dict:
    return {
        "schema": SWEEP_SCHEMA,
        "inference_requested": False,
        "settings": {"model": "a-deployment"},
        "token": {"minted": True, "error": None},
        "requests_planned": 7,
        "requests_sent": 7,
        "arms": {"baseline": {"status": 400, "message": "missing model"}},
        "control": {"status": 401, "message": "denied"},
        "properties_that_closed_the_gate": [],
        "verdict": VERDICT_NO_REQUEST_PROPERTY_CLOSES_THE_GATE,
        "not_established": ["urllib, unpriced, not a reason to request a role"],
    }


def test_the_leak_check_accepts_a_sweep_record(tmp_path: Path):
    """A record the redaction check cannot parse is a record it withholds."""
    from tests.test_codex_auth_discriminator import _run_leak_check

    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-transmission-sweep.json": _sweep_record()}
    )
    assert code == 0, output
    assert "record=clean (1 checked)" in output


def test_the_leak_check_still_enforces_the_no_request_claim_on_the_sweep(
    tmp_path: Path,
):
    """Adding a shape must not amount to exempting it."""
    from tests.test_codex_auth_discriminator import _run_leak_check

    record = _sweep_record()
    record["inference_requested"] = True
    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-transmission-sweep.json": record}
    )
    assert code == 1
    assert "claims a request was made" in output


def test_the_leak_check_reads_the_sweep_record_by_its_real_path():
    """The substitution above is only honest if this is the path CI checks."""
    from tests.test_codex_auth_discriminator import _leak_check_source

    assert '"/tmp/codex-foundry-transmission-sweep.json"' in _leak_check_source()


def test_the_sweep_record_is_published_with_the_others():
    """An artifact that is checked and then not uploaded proves nothing later."""
    import yaml

    from tests.test_codex_auth_discriminator import WORKFLOW

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = parsed["jobs"]["diagnose"]["steps"]
    keep = next(s for s in steps if s.get("name") == "Keep the record")
    assert "/tmp/codex-foundry-transmission-sweep.json" in keep["with"]["path"]


def test_the_sweep_step_is_free_and_ungated_and_cannot_buy_a_turn():
    """Seven requests, none of which can select a deployment.

    ``--send-request`` on this step would buy a turn from a step whose comment
    says it cannot, so its absence is asserted rather than trusted -- the same
    guard the discriminator step carries.
    """
    import yaml

    from tests.test_codex_auth_discriminator import WORKFLOW

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = parsed["jobs"]["diagnose"]["steps"]
    step = next(s for s in steps if s.get("id") == "transmission_sweep")
    assert "if" not in step, step.get("if")
    assert "--transmission-sweep" in step["run"]
    assert "--send-request" not in step["run"]


def test_the_step_fails_when_fewer_arms_went_than_it_reports_on():
    """Arms that never went are not evidence, and must not read as null."""
    import yaml

    from tests.test_codex_auth_discriminator import WORKFLOW

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = parsed["jobs"]["diagnose"]["steps"]
    step = next(s for s in steps if s.get("id") == "transmission_sweep")
    assert "requests_sent" in step["run"] and "requests_planned" in step["run"]
    assert 'record["token"]["minted"]' in step["run"]


# ── The command line ────────────────────────────────────────────────────────


def test_the_four_probes_refuse_to_run_together(capsys):
    """They write different records to the same ``--out``; one would win."""
    for extra in (
        ["--read-only-probe"],
        ["--send-request"],
        ["--auth-discriminator"],
    ):
        with pytest.raises(SystemExit):
            main(["--deployment", "d", "--transmission-sweep", *extra])
        assert "run them separately" in capsys.readouterr().err


def test_an_inconclusive_sweep_does_not_exit_zero(tmp_path: Path, monkeypatch):
    """"The sweep ran" is not the result."""
    import diagnose_codex_foundry_connection as module

    def rule(headers: dict, _body: dict) -> tuple[int, str]:
        return 400, "this host reads the body first"

    with _ScriptedHost(rule) as host:
        monkeypatch.setattr(
            module,
            "settings_from_environment",
            lambda *_a, **_k: _with_auth_command(
                _settings(host.port), _printer(tmp_path)
            ),
        )
        code = main(
            [
                "--deployment",
                "a-deployment",
                "--transmission-sweep",
                "--out",
                str(tmp_path / "sweep.json"),
            ]
        )
    assert code == 1


def test_a_null_result_exits_zero_because_it_is_an_answer(tmp_path: Path, monkeypatch):
    """Nothing closing the gate moves the question; it does not fail the run."""
    import diagnose_codex_foundry_connection as module

    with _ScriptedHost(_never_at_the_gate) as host:
        monkeypatch.setattr(
            module,
            "settings_from_environment",
            lambda *_a, **_k: _with_auth_command(
                _settings(host.port), _printer(tmp_path)
            ),
        )
        out = tmp_path / "sweep.json"
        code = main(
            ["--deployment", "a-deployment", "--transmission-sweep", "--out", str(out)]
        )

    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["verdict"] == VERDICT_NO_REQUEST_PROPERTY_CLOSES_THE_GATE
