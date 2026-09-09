"""Two arms on the turn route, and the answer they are not allowed to give.

Why this file exists
--------------------

After run ``34346945494`` the position was: the same identity, minting its
token the way the Codex runtime does, gets ``200`` from ``GET /models`` on the
host that answered ``401`` to run ``34347516170``'s one turn. Four candidate
causes were closed by that pair — the address, the identity, the deployment
name, the header format — and the refusal was still not located. The message
Azure returned ("invalid subscription key or wrong API endpoint") is a gateway
string that more than one kind of refusal shares, so it does not locate it
either.

``--auth-discriminator`` asks the *turn route* something it cannot answer with
a completion: a ``POST`` carrying a body that names no model. The point is not
the status it gets back. The point is the pair:

* if a bearer that is plainly not a token is stopped at the gate, and the
  minted one gets through to the part that reads the body, then authorization
  runs first and the minted bearer cleared it;
* if both are stopped at the gate, the minted bearer is being refused where a
  non-token is;
* **if the non-token is *not* stopped at the gate**, this host reads the body
  first and neither status means anything about authorization. The probe has
  to say so rather than reading the minted arm's number as an answer.

That third branch is what the tests below spend the most effort on. An
instrument that can only return the answer it was built to find is not an
instrument, and this one is being built by the same person who wants the
answer.

Nothing here reaches the network. The auth command is a script this file
writes, and the route is served by a socket on this machine, with a token that
is a sentence.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codex_runtime_config import CodexProviderSettings  # noqa: E402
from scripts.diagnose_codex_foundry_connection import (  # noqa: E402
    AUTH_DISCRIMINATOR_SCHEMA,
    MALFORMED_TURN_BODY,
    NOT_ESTABLISHED_BY_THE_DISCRIMINATOR,
    OBVIOUSLY_INVALID_BEARER,
    VERDICT_BEARER_CLEARS_THE_AUTH_GATE,
    VERDICT_BEARER_REFUSED_AT_THE_AUTH_GATE,
    VERDICT_CHECK_ORDER_NOT_ESTABLISHED,
    VERDICT_DISCRIMINATOR_INCONCLUSIVE,
    auth_discriminator_probe,
    build_redactor,
    classify_discriminator,
    main,
    post_malformed_turn,
)

#: Not a credential. Distinctive enough that a leak into the record is a
#: substring search away.
FAKE_TOKEN = "FAKE-TOKEN-NOT-A-CREDENTIAL-0123456789"


class _TurnRoute:
    """A host that answers ``POST /responses`` differently per bearer.

    It decides on the Authorization header, which is the only way to script the
    two arms independently — and, incidentally, the only way this test can tell
    that the probe really did send two different bearers rather than the same
    one twice.
    """

    def __init__(
        self,
        *,
        minted: tuple[int, str],
        control: tuple[int, str],
    ):
        self.minted = minted
        self.control = control
        self.calls: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):  # noqa: D102 - silence the default
                pass

            def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler's spelling
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode() if length else ""
                headers = {k.lower(): v for k, v in self.headers.items()}
                outer.calls.append(
                    {"path": self.path, "headers": headers, "body": raw}
                )
                is_control = OBVIOUSLY_INVALID_BEARER in headers.get(
                    "authorization", ""
                )
                status, message = outer.control if is_control else outer.minted
                body = json.dumps({"error": {"message": message}}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "_TurnRoute":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)


def _settings(port: int, *, deployment: str = "a-deployment") -> CodexProviderSettings:
    """Real settings, pointed at a socket on this machine.

    ``classify_endpoint`` refuses anything but https, so only ``base_url`` is
    redirected and every other field stays what production computes.
    """
    real = CodexProviderSettings(
        endpoint="https://example-account.openai.azure.com/openai/v1/",
        model=deployment,
    )

    class _Redirected(CodexProviderSettings):
        @property
        def base_url(self) -> str:
            return f"http://127.0.0.1:{port}/v1"

    return _Redirected(endpoint=real.endpoint, model=real.model)


def _with_auth_command(settings: CodexProviderSettings, argv: list[str]):
    """Swap the argv, keeping ``auth_command`` a *method* like the real one.

    A helper that models it as a value is how run ``34340775246`` spent a real
    Azure login to discover ``'method' object is not iterable``.
    """

    class _Fixed(type(settings)):  # type: ignore[misc]
        def auth_command(self) -> list[str]:
            return argv

    return _Fixed(endpoint=settings.endpoint, model=settings.model)


def _printer(tmp_path: Path, *, token: str = FAKE_TOKEN) -> list[str]:
    script = tmp_path / "auth_command.py"
    script.write_text(
        f"import sys\nsys.stdout.write({token!r} + chr(10))\n", encoding="utf-8"
    )
    return [sys.executable, str(script)]


# ── What goes on the wire ───────────────────────────────────────────────────


def test_the_request_goes_to_the_turn_route_not_the_listing():
    """``/responses``. A discriminator asking ``/models`` would re-measure the
    question the read-only probe already answered."""
    with _TurnRoute(minted=(400, "bad body"), control=(401, "denied")) as host:
        post_malformed_turn(_settings(host.port), FAKE_TOKEN)
    assert host.calls[0]["path"] == "/v1/responses"


def test_the_bearer_is_sent_the_way_the_turn_sends_it():
    """Same header name and format the pinned binary was measured using.

    If this drifted, the pair below would be about a header the runtime does
    not send and would say nothing about the turn's refusal.
    """
    with _TurnRoute(minted=(400, "bad body"), control=(401, "denied")) as host:
        post_malformed_turn(_settings(host.port), FAKE_TOKEN)
    assert host.calls[0]["headers"]["authorization"] == f"Bearer {FAKE_TOKEN}"
    assert host.calls[0]["headers"]["content-type"] == "application/json"


def test_the_body_names_no_model_and_asks_for_no_completion():
    """The structural half of "this cannot generate anything".

    Measured on the socket rather than asserted about the constant, because
    what matters is the bytes that left, not the dict they came from.
    """
    with _TurnRoute(minted=(400, "bad body"), control=(401, "denied")) as host:
        post_malformed_turn(_settings(host.port), FAKE_TOKEN)
    sent = json.loads(host.calls[0]["body"])
    assert "model" not in sent
    assert "input" not in sent
    assert "messages" not in sent
    assert sent == MALFORMED_TURN_BODY


def test_a_refusal_body_is_read_rather_than_discarded():
    """The sentence is the evidence; a bare status could not be compared."""
    with _TurnRoute(minted=(401, "a specific refusal"), control=(401, "x")) as host:
        outcome = post_malformed_turn(_settings(host.port), FAKE_TOKEN)
    assert outcome["status"] == 401
    assert outcome["message"] == "a specific refusal"
    assert outcome["error"] is None


def test_a_host_that_is_not_there_is_an_error_not_a_status():
    """A closed port is a fact about this runner, not about the resource."""
    outcome = post_malformed_turn(_settings(9), FAKE_TOKEN)
    assert outcome["status"] is None
    assert outcome["error"]


# ── The pair, and what it is allowed to conclude ────────────────────────────


def test_a_stopped_control_and_a_body_complaint_means_the_bearer_got_through():
    verdict, note = classify_discriminator(
        {"status": 400, "message": "missing model"},
        {"status": 401, "message": "denied"},
    )
    assert verdict == VERDICT_BEARER_CLEARS_THE_AUTH_GATE
    assert "past authorization" in note
    # It must not turn into a recommendation. A narrowing is not a fix.
    assert "not obviously the fix" in note


def test_both_stopped_at_the_gate_keeps_the_question_on_the_token():
    verdict, note = classify_discriminator(
        {"status": 401, "message": "denied"},
        {"status": 401, "message": "denied"},
    )
    assert verdict == VERDICT_BEARER_REFUSED_AT_THE_AUTH_GATE
    # Names what it rules *out* as well as what it points at. "Authorization"
    # alone would be read as "the token", and the identity's rights on this
    # one operation are the other half of that.
    assert "not the payload, the deployment name or the route" in note
    assert "rights on this operation" in note


def test_a_403_counts_as_the_gate_on_either_arm():
    """401 and 403 are both "stopped at authorization" for this question.

    They differ in what to do next, and the record carries the number for that.
    They do not differ in *where* the request died, which is all this verdict
    claims.
    """
    verdict, _ = classify_discriminator(
        {"status": 403, "message": "forbidden"},
        {"status": 403, "message": "forbidden"},
    )
    assert verdict == VERDICT_BEARER_REFUSED_AT_THE_AUTH_GATE


def test_a_control_that_is_not_stopped_makes_the_whole_pair_meaningless():
    """The branch this design exists for.

    A host that answers 400 to a string that is obviously not a token has
    looked at the body before it looked at the credential. The minted arm's
    400 then says nothing whatsoever about authorization — and it is exactly
    the reading somebody wanting good news would take.
    """
    verdict, note = classify_discriminator(
        {"status": 400, "message": "missing model"},
        {"status": 400, "message": "missing model"},
    )
    assert verdict == VERDICT_CHECK_ORDER_NOT_ESTABLISHED
    assert "not evidence about authorization" in note
    assert "still open" in note


def test_an_unauthenticated_two_hundred_does_not_become_a_clear_verdict():
    """Even a 200 on the control arm is not permission to read the other one."""
    verdict, _ = classify_discriminator(
        {"status": 400, "message": "missing model"},
        {"status": 200, "message": None},
    )
    assert verdict == VERDICT_CHECK_ORDER_NOT_ESTABLISHED


def test_a_served_malformed_body_withdraws_the_free_claim():
    """If the host served it, "nothing could be generated" stops being true.

    The verdict is inconclusive and the note says the cost is unknown, because
    the argument for this probe being free is that the body selects no
    deployment — and a 200 is the host disagreeing.
    """
    verdict, note = classify_discriminator(
        {"status": 200, "message": None},
        {"status": 401, "message": "denied"},
    )
    assert verdict == VERDICT_DISCRIMINATOR_INCONCLUSIVE
    assert "cost is unknown" in note


def test_a_transport_failure_on_either_arm_is_inconclusive():
    for minted, control in (
        ({"status": None, "error": "URLError: x"}, {"status": 401}),
        ({"status": 400}, {"status": None, "error": "URLError: x"}),
    ):
        verdict, note = classify_discriminator(minted, control)
        assert verdict == VERDICT_DISCRIMINATOR_INCONCLUSIVE
        assert "says nothing about the resource" in note


def test_a_pair_that_fits_neither_shape_is_named_rather_than_forced():
    """404 or 5xx on the minted arm against a stopped control.

    Silently filing this under one of the two real verdicts is how a probe
    starts reporting conclusions it did not reach.
    """
    for status in (404, 429, 500):
        verdict, note = classify_discriminator(
            {"status": status, "message": "?"}, {"status": 401, "message": "denied"}
        )
        assert verdict == VERDICT_DISCRIMINATOR_INCONCLUSIVE
        assert "does not fit the question" in note


# ── The record ──────────────────────────────────────────────────────────────


def test_both_arms_are_actually_sent_and_with_different_bearers(tmp_path: Path):
    """Two requests, two credentials. A single-armed probe would be unreadable."""
    with _TurnRoute(minted=(400, "missing model"), control=(401, "denied")) as host:
        settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
        record = auth_discriminator_probe(settings, redact=build_redactor())

    assert len(host.calls) == 2
    bearers = {call["headers"]["authorization"] for call in host.calls}
    assert bearers == {f"Bearer {FAKE_TOKEN}", f"Bearer {OBVIOUSLY_INVALID_BEARER}"}
    assert record["verdict"] == VERDICT_BEARER_CLEARS_THE_AUTH_GATE
    assert record["arms"]["minted_bearer"]["status"] == 400
    assert record["arms"]["invalid_bearer_control"]["status"] == 401


def test_the_record_names_no_resource_and_carries_no_token(tmp_path: Path):
    """Read end to end, then searched. The token is in neither arm."""
    with _TurnRoute(minted=(401, "denied"), control=(401, "denied")) as host:
        settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
        record = auth_discriminator_probe(settings, redact=build_redactor())

    serialized = json.dumps(record)
    assert FAKE_TOKEN not in serialized
    assert "example-account" not in serialized
    assert record["schema"] == AUTH_DISCRIMINATOR_SCHEMA
    assert record["inference_requested"] is False
    assert record["endpoint_host_fingerprint"].startswith("sha256:")
    assert len(record["body_sha256"]) == 64


def test_the_two_refusals_are_compared_before_they_are_redacted(tmp_path: Path):
    """Otherwise this flag would be measuring the redactor.

    Redaction maps distinct strings onto one placeholder. Two refusals that
    differ only in a URL come out identical on the far side of it, and
    ``same_message_as_control`` would read ``True`` for a host that was
    plainly distinguishing between the two bearers.
    """
    with _TurnRoute(
        minted=(401, "denied for https://one.example/a"),
        control=(401, "denied for https://two.example/b"),
    ) as host:
        settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
        record = auth_discriminator_probe(settings, redact=build_redactor())

    assert record["same_message_as_control"] is False
    # And the record itself still carries no URL, which is the reason the
    # redactor collapses them in the first place.
    assert "one.example" not in json.dumps(record)


def test_identical_refusals_are_reported_as_identical(tmp_path: Path):
    with _TurnRoute(minted=(401, "same sentence"), control=(401, "same sentence")) as h:
        settings = _with_auth_command(_settings(h.port), _printer(tmp_path))
        record = auth_discriminator_probe(settings, redact=build_redactor())
    assert record["same_message_as_control"] is True


def test_a_mint_failure_sends_neither_arm(tmp_path: Path):
    """Nothing is sent, and the record says it measured nothing.

    A probe that fell through to sending only the control arm would produce a
    record whose ``arms`` half-populated and whose verdict looked like a
    finding about the resource.
    """
    with _TurnRoute(minted=(400, "x"), control=(401, "y")) as host:
        settings = _with_auth_command(
            _settings(host.port), [sys.executable, "-c", "raise SystemExit(9)"]
        )
        record = auth_discriminator_probe(settings, redact=build_redactor())

    assert host.calls == []
    assert record["token"]["minted"] is False
    assert record["arms"] == {"minted_bearer": None, "invalid_bearer_control": None}
    assert record["verdict"] == VERDICT_DISCRIMINATOR_INCONCLUSIVE
    assert "measures nothing about the resource" in record["verdict_note"]


def test_the_record_states_what_it_cannot_settle(tmp_path: Path):
    """Including, explicitly, that a clear verdict is not a reason to grant a role."""
    with _TurnRoute(minted=(400, "missing model"), control=(401, "denied")) as host:
        settings = _with_auth_command(_settings(host.port), _printer(tmp_path))
        record = auth_discriminator_probe(settings, redact=build_redactor())
    joined = " ".join(record["not_established"])
    assert "not a reason to grant a role" in joined
    assert "unpriced call is not a proven free one" in joined
    assert "not the Codex runtime" in joined
    assert record["not_established"] == list(NOT_ESTABLISHED_BY_THE_DISCRIMINATOR)


# ── The command line ────────────────────────────────────────────────────────


def test_the_three_probes_refuse_to_run_together(capsys):
    """They write different records to the same ``--out``; one would win."""
    for extra in (["--read-only-probe"], ["--send-request"]):
        with pytest.raises(SystemExit):
            main(["--deployment", "d", "--auth-discriminator", *extra])
        assert "run them separately" in capsys.readouterr().err


def test_an_inconclusive_run_does_not_exit_zero(tmp_path: Path, monkeypatch):
    """"The probe ran" is not the result.

    A green step for a run that could not discriminate is how a workflow ends
    up reporting a measurement nobody made.
    """
    with _TurnRoute(minted=(400, "missing model"), control=(400, "missing model")) as h:
        settings = _with_auth_command(_settings(h.port), _printer(tmp_path))
        monkeypatch.setattr(
            "scripts.diagnose_codex_foundry_connection.settings_from_environment",
            lambda *_a, **_k: settings,
        )
        out = tmp_path / "record.json"
        code = main(
            ["--deployment", "d", "--auth-discriminator", "--out", str(out)]
        )
    assert code == 1
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["verdict"] == VERDICT_CHECK_ORDER_NOT_ESTABLISHED


def test_a_refusal_at_the_gate_exits_zero_because_it_is_an_answer(
    tmp_path: Path, monkeypatch
):
    """Bad news that was successfully measured is still a measurement."""
    with _TurnRoute(minted=(401, "denied"), control=(401, "denied")) as h:
        settings = _with_auth_command(_settings(h.port), _printer(tmp_path))
        monkeypatch.setattr(
            "scripts.diagnose_codex_foundry_connection.settings_from_environment",
            lambda *_a, **_k: settings,
        )
        code = main(["--deployment", "d", "--auth-discriminator"])
    assert code == 0


# ── The gate the record has to pass in CI ───────────────────────────────────
#
# Same reasoning as test_codex_readonly_token_probe.py: the workflow's leak
# check is a heredoc that nothing imports, so it is executed here. A third
# record shape now lands in it, and the shape has no `observed` key — the
# unbranched version would raise KeyError inside an `always()` step and take
# the job down *after* the run rather than before it.

WORKFLOW = Path(__file__).resolve().parents[2] / (
    ".github/workflows/codex-foundry-connection-diagnostic.yml"
)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _leak_check_source() -> str:
    import yaml

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = parsed["jobs"]["diagnose"]["steps"]
    step = next(s for s in steps if s.get("id") == "leak_check")
    body = step["run"]
    opened = body.index("<<'PY'\n") + len("<<'PY'\n")
    return body[opened : body.index("\nPY", opened)]


def _run_leak_check(tmp_path: Path, records: dict[str, dict]) -> tuple[int, str]:
    import subprocess
    import textwrap

    for name, record in records.items():
        (tmp_path / name).write_text(json.dumps(record), encoding="utf-8")
    source = textwrap.dedent(_leak_check_source()).replace(
        '"/tmp/codex-foundry', f'"{tmp_path}/codex-foundry'
    )
    done = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin"},
    )
    return done.returncode, done.stdout + done.stderr


def _discriminator_record() -> dict:
    return {
        "schema": AUTH_DISCRIMINATOR_SCHEMA,
        "inference_requested": False,
        "settings": {"model": "a-deployment"},
        "token": {"minted": True, "error": None},
        "arms": {
            "minted_bearer": {"status": 400, "message": "missing model"},
            "invalid_bearer_control": {"status": 401, "message": "denied"},
        },
        "verdict": VERDICT_BEARER_CLEARS_THE_AUTH_GATE,
        "not_established": list(NOT_ESTABLISHED_BY_THE_DISCRIMINATOR),
    }


def test_the_leak_check_accepts_a_discriminator_record(tmp_path: Path):
    """The regression this section exists for: it must not KeyError."""
    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-auth-discriminator.json": _discriminator_record()}
    )
    assert code == 0, output
    assert "record=clean (1 checked)" in output


def test_the_leak_check_still_enforces_the_no_request_claim(tmp_path: Path):
    """Branching on schema must not amount to exempting the new shape."""
    record = _discriminator_record()
    record["inference_requested"] = True
    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-auth-discriminator.json": record}
    )
    assert code == 1
    assert "claims a request was made" in output


def test_the_leak_check_reads_the_discriminator_record_by_its_real_path():
    """The substitution above is only honest if this is the path CI checks."""
    assert '"/tmp/codex-foundry-auth-discriminator.json"' in _leak_check_source()


def test_the_discriminator_record_is_published_with_the_others():
    """An artifact that is checked and then not uploaded proves nothing later."""
    import yaml

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = parsed["jobs"]["diagnose"]["steps"]
    keep = next(s for s in steps if s.get("name") == "Keep the record")
    assert "/tmp/codex-foundry-auth-discriminator.json" in keep["with"]["path"]


def test_the_discriminator_step_is_free_and_ungated():
    """It must run on the dry dispatches, which are the only ones left.

    The paid turn is behind ``inputs.send_request`` and a fingerprint check.
    This step is behind neither, because it costs nothing and because a
    diagnostic that only runs on the dispatches that spend money is not
    available when it is most needed. It also must not carry
    ``--send-request``: that flag on this step would buy a turn from a step
    documented as free.
    """
    import yaml

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = parsed["jobs"]["diagnose"]["steps"]
    step = next(s for s in steps if s.get("id") == "auth_discriminator")
    assert "if" not in step, step.get("if")
    assert "--auth-discriminator" in step["run"]
    assert "--send-request" not in step["run"]
