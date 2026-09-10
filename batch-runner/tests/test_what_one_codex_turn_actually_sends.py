"""What one Codex turn actually puts on the wire.

Two things written in this repository about a Codex turn are narrower than
they read, and both are load-bearing for what may be claimed about the 401.

The first is ``test_codex_retry_pins_are_enforced.py``'s
``paths == ["/v1/responses"]``. It is true of the requests that harness saw,
and that harness implements ``do_POST`` and nothing else --
``BaseHTTPRequestHandler`` answers an unimplemented verb with ``501`` without
ever calling the recorder, so a ``GET`` would have been refused by the
instrument and left no trace in the count it reports. "One request" and "one
request of the only kind we looked for" are different measurements, and only
the second one had been made.

The second is the diagnostic's summary line, ``tool execution observed:
false -- this prompt forbids tools, by design``. That is true of execution.
The request carries ten tool definitions and ``tool_choice: "auto"``
regardless of what the prompt says, and ``core/codex_runtime_config.py`` has
no key that removes them. A plan promising that no tools are *sent* through
this path cannot be kept, however the prompt is worded.

Neither correction moves the 401. Both change what may be written about it,
and both change what a contrast against the direct Python path is able to
control for: not the body, which differs by two orders of magnitude, but the
resource, the deployment, the identity and the route.

Nothing here mints a token or reaches any network but loopback.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.azure_ai_clients import (  # noqa: E402
    AzureAIRouteSettings,
    AzureAIWorkload,
)
from core.codex_runtime_config import (  # noqa: E402
    CodexRuntimeUnavailable,
    require_pinned_runtime,
)

# Imported rather than copied. These are the fake token, the production-shaped
# settings and the redirected provider table the retry-pin measurement already
# uses; a second copy of them here would be a second thing to keep true.
from tests.test_codex_retry_pins_are_enforced import (  # noqa: E402
    FAKE_TOKEN,
    REAL_SHAPED_SETTINGS,
    _RedirectedProvider,
    _token_printer,
)

_RUNTIME_PROBLEM: str | None = None
try:
    require_pinned_runtime()
except CodexRuntimeUnavailable as exc:  # pragma: no cover - environment shape
    _RUNTIME_PROBLEM = str(exc)

#: Applied per test rather than to the module. The URL-derivation test below
#: needs no runtime and must not be skipped along with the ones that do.
needs_runtime = pytest.mark.skipif(
    _RUNTIME_PROBLEM is not None,
    reason=f"the pinned Codex runtime is not installed: {_RUNTIME_PROBLEM}",
)

#: Every verb a client could reach for. The point of the list is that nothing
#: falls through to ``501`` unrecorded.
EVERY_VERB = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")

#: What production got. Reproduced so the inventory is of the failing turn
#: rather than of some other turn that happened to succeed.
REFUSAL_STATUS = 401

#: A backstop, not a parameter. Past it the server stops answering, so a
#: runaway loop ends the test rather than hanging it, and ``overran`` says
#: which of the two happened.
REQUEST_BACKSTOP = 40

#: Header names an Azure gateway might read a credential out of instead of, or
#: in preference to, ``authorization``. A second credential the runtime did not
#: mean to send would be a cheap explanation for a refusal, so its absence is
#: worth asserting rather than assuming.
OTHER_CREDENTIAL_HEADERS = (
    "api-key",
    "x-api-key",
    "ocp-apim-subscription-key",
    "subscription-key",
    "x-ms-api-key",
)


def describe_credential(headers: dict[str, str], expected: str) -> dict:
    """The credential's *shape*, and deliberately none of its content.

    The token in this file is a known non-credential, so printing it would
    harm nothing -- and building the habit of printing one would. Everything
    here is a comparison whose result is a boolean or a length.
    """
    lowered = {name.lower(): value for name, value in headers.items()}
    raw = lowered.get("authorization")
    out: dict = {
        "present": raw is not None,
        "other_credential_headers": [
            name for name in OTHER_CREDENTIAL_HEADERS if name in lowered
        ],
    }
    if raw is None:
        return out
    out["has_bearer_prefix"] = raw.startswith("Bearer ")
    out["scheme"] = raw.split(" ", 1)[0] if " " in raw else "(no space)"
    value = raw[len("Bearer ") :] if raw.startswith("Bearer ") else None
    out["value_matches_what_auth_printed"] = value == expected
    out["value_length"] = len(value) if value is not None else None
    out["expected_length"] = len(expected)
    return out


class RecordsEveryVerb:
    """Answers ``REFUSAL_STATUS`` to anything, and writes down what it was."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.overran = False
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):  # noqa: D102 - silence the default
                pass

            def handle_one_request(self):
                # The runtime hangs up as readily as we do; neither is a
                # failure of the measurement.
                try:
                    super().handle_one_request()
                except (BrokenPipeError, ConnectionResetError):
                    self.close_connection = True

            def _record(self):
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length else b""
                with outer._lock:
                    outer.calls.append(
                        {
                            "method": self.command,
                            "path": self.path,
                            "header_names": sorted(
                                name.lower() for name in self.headers.keys()
                            ),
                            # Values as well as names, because a later
                            # measurement replays some of them and needs to
                            # replay what is actually sent rather than what a
                            # reader would guess. ``authorization`` is the one
                            # exception and is described in shape only, below.
                            "header_values": {
                                name.lower(): (
                                    f"<{len(value)} chars>"
                                    if name.lower() == "authorization"
                                    else value
                                )
                                for name, value in self.headers.items()
                            },
                            "credential": describe_credential(
                                dict(self.headers.items()), FAKE_TOKEN
                            ),
                            "body": body,
                        }
                    )
                    count = len(outer.calls)
                    if count > REQUEST_BACKSTOP:
                        outer.overran = True
                if count > REQUEST_BACKSTOP:
                    self.close_connection = True
                    return
                payload = json.dumps(
                    {"error": {"message": "scripted refusal", "type": "test"}}
                ).encode()
                self.send_response(REFUSAL_STATUS)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)

        for verb in EVERY_VERB:
            setattr(Handler, f"do_{verb}", Handler._record)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )

    def __enter__(self) -> "RecordsEveryVerb":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)


def _one_refused_turn(tmp_path: Path) -> dict:
    """Send one turn into a server that refuses it, and report everything.

    The stream is consumed rather than merely started: ``Thread.turn`` returns
    a handle and sends nothing until something iterates it, so a version of
    this without the ``for`` loop would record zero requests and read as proof
    that a turn sends none.
    """
    from core.codex_runner import CodexAgentRunner, CodexWorkspace

    printer, call_log = _token_printer(tmp_path)
    with RecordsEveryVerb() as server:
        runner = CodexAgentRunner(
            _RedirectedProvider(server.port, printer, REAL_SHAPED_SETTINGS),
            timeout=90,
        )
        workspace = CodexWorkspace.create(task_id="wire-inventory")
        codex = None
        try:
            codex = runner.open_runtime(workspace)
            thread = runner.start_thread(codex, workspace)
            handle = thread.turn("Say OK.")
            try:
                for _event in handle.stream():
                    pass
            except Exception:  # noqa: BLE001 - the refusal is the measurement
                pass
        except Exception:  # noqa: BLE001 - so is a runtime that gives up
            pass
        finally:
            if codex is not None:
                try:
                    codex.close()
                except Exception:  # noqa: BLE001 - teardown, not the subject
                    pass
            workspace.cleanup()

        return {
            "calls": list(server.calls),
            "overran": server.overran,
            "auth_command_runs": (
                len(call_log.read_text(encoding="utf-8").splitlines())
                if call_log.exists()
                else 0
            ),
        }


# ── The instrument, before what it measures ─────────────────────────────────


def test_the_recorder_actually_sees_every_verb_it_claims_to():
    """Without this, the inventory below passes by not looking.

    ``test_a_refused_turn_sends_no_request_of_any_verb_but_post`` asserts an
    absence, and an absence is exactly what a broken recorder reports. If the
    ``setattr`` loop that installs ``do_GET`` and its siblings ever stopped
    running, every non-POST would be answered ``501`` by
    ``BaseHTTPRequestHandler`` and the inventory would go on passing while
    measuring nothing -- which is the same blind spot this file exists to
    correct, reintroduced one layer down.

    So: send one of each by hand and require that all seven come back.
    """
    import http.client

    with RecordsEveryVerb() as server:
        for verb in EVERY_VERB:
            conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
            try:
                conn.request(verb, "/v1/responses", body=b"{}")
                response = conn.getresponse()
                response.read()
                assert response.status == REFUSAL_STATUS, (verb, response.status)
            finally:
                conn.close()

    assert [call["method"] for call in server.calls] == list(EVERY_VERB)


# ── How many requests, of what kind ─────────────────────────────────────────


@needs_runtime
def test_a_refused_turn_sends_no_request_of_any_verb_but_post(tmp_path):
    """The `501` blind spot, closed by looking for all seven verbs."""
    measured = _one_refused_turn(tmp_path)
    assert not measured["overran"], "the backstop was hit; the count is a floor"

    by_verb = {
        verb: [call for call in measured["calls"] if call["method"] == verb]
        for verb in EVERY_VERB
    }
    other = {verb: len(calls) for verb, calls in by_verb.items() if verb != "POST"}
    assert sum(other.values()) == 0, (
        f"a verb other than POST reached the wire: {other}. The retry-pin "
        f"harness would not have seen this."
    )
    assert {call["path"] for call in by_verb["POST"]} == {"/v1/responses"}


@needs_runtime
def test_the_second_request_is_the_re_mint_and_there_is_no_third(tmp_path):
    """Two requests for one refused turn, and the token command ran twice."""
    measured = _one_refused_turn(tmp_path)
    assert not measured["overran"]
    assert len(measured["calls"]) == 2
    # The pins removed the retries they govern; this pair is the runtime
    # re-minting the token once and trying again, which no key removes.
    assert measured["auth_command_runs"] == 2


# ── What is in the body ─────────────────────────────────────────────────────


@needs_runtime
def test_the_request_carries_tools_no_prompt_can_switch_off(tmp_path):
    """`tool execution observed: false` is about execution, not the request."""
    measured = _one_refused_turn(tmp_path)
    body = json.loads(measured["calls"][0]["body"].decode("utf-8"))

    tools = body.get("tools")
    assert isinstance(tools, list) and tools, (
        "the turn sent no tools, which would make the 'no tools are sent' "
        "claim true -- update the diagnostic's record and this test together"
    )
    names = {tool.get("name") or tool.get("type") for tool in tools}
    # Named individually because these two are what a promise of "no tools,
    # no files, no work materials" is understood to exclude.
    assert "exec_command" in names, names
    assert "web_search" in names, names
    assert body.get("tool_choice") == "auto", body.get("tool_choice")

    # The diagnostic's record writes this number into every run. Asserting it
    # here rather than restating it means the record and the wire cannot drift
    # apart in silence: a runtime that starts sending a different set fails
    # this line instead of quietly making the record wrong.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from diagnose_codex_foundry_connection import (
        TOOL_DEFINITIONS_THE_RUNTIME_ALWAYS_SENDS,
    )

    assert len(tools) == TOOL_DEFINITIONS_THE_RUNTIME_ALWAYS_SENDS, (
        f"the runtime sent {len(tools)} tools, the record claims "
        f"{TOOL_DEFINITIONS_THE_RUNTIME_ALWAYS_SENDS}: {sorted(names)}"
    )


@needs_runtime
def test_the_body_is_mostly_instructions_and_tools_not_the_prompt(tmp_path):
    """Two orders of magnitude, which is why no body-level A/B is possible."""
    measured = _one_refused_turn(tmp_path)
    raw = measured["calls"][0]["body"]
    body = json.loads(raw.decode("utf-8"))

    def weight(key: str) -> int:
        return len(json.dumps(body.get(key), ensure_ascii=False).encode("utf-8"))

    # Order-of-magnitude assertions, not fingerprints: the pinned runtime makes
    # exact byte counts stable, and pinning them here would fail on a version
    # bump for a reason that has nothing to do with the claim.
    assert len(raw) > 20_000, f"the turn body was {len(raw)} bytes"
    assert weight("tools") > 10_000, f"tools were {weight('tools')} bytes"
    assert weight("instructions") > 10_000, (
        f"instructions were {weight('instructions')} bytes"
    )
    # The prompt is a rounding error in its own request.
    assert weight("input") < weight("tools") + weight("instructions")


# ── How the credential arrives ──────────────────────────────────────────────


@needs_runtime
def test_the_credential_arrives_in_the_shape_the_auth_command_printed(tmp_path):
    """Where run `34361684546` left the question, answered with a fake token.

    That run established that the minted bearer *clears* this host's auth gate
    -- `400 Missed model deployment` -- while a plainly invalid bearer is
    stopped at it with `401 Access denied due to invalid subscription key...`,
    which is byte for byte what the paid turn `34347516170` got back. So the
    token is acceptable and the runtime is answered as though it were not, and
    the difference has to be in how the runtime transmits it.

    These are the cheap explanations, in the order they would be cheap, and
    every one of them is false: the header is present, it is a `Bearer`, its
    value is *exactly* what the auth command printed -- not truncated, not
    wrapped, no trailing newline -- and no second credential header rides
    alongside for a gateway to prefer and reject. The re-mint on the second
    request sends the same thing.

    So this test does not find the fault. It rules out the four places it
    would have been cheapest to find, which is what makes the remaining
    difference -- the runtime's own headers, `stream: true`, and a body two
    orders of magnitude larger -- the place left to look.
    """
    measured = _one_refused_turn(tmp_path)
    assert not measured["overran"]
    assert measured["calls"], "no request arrived, so nothing was measured"

    for index, call in enumerate(measured["calls"], start=1):
        credential = call["credential"]
        assert credential["present"], f"request {index} carried no credential"
        assert credential["has_bearer_prefix"], (index, credential["scheme"])
        assert credential["value_matches_what_auth_printed"], (
            f"request {index} sent {credential['value_length']} characters "
            f"where the auth command printed {credential['expected_length']}"
        )
        assert credential["other_credential_headers"] == [], (
            f"request {index} carried a second credential header: "
            f"{credential['other_credential_headers']}"
        )


@needs_runtime
def test_the_runtime_adds_headers_the_working_python_path_does_not(tmp_path):
    """The difference that is left, named so it can be tested next.

    `openai.OpenAI` -- the client that produced 68,610 graded rows against
    this same resource -- sends none of these. Asserting they are present is
    not asserting they are the fault; it fixes *what* differs so the next
    diagnostic can add them to a request that is known to clear the gate and
    see whether the gate closes.
    """
    measured = _one_refused_turn(tmp_path)
    names = set(measured["calls"][0]["header_names"])

    codex_only = {
        "originator",
        "session-id",
        "thread-id",
        "x-client-request-id",
        "x-codex-beta-features",
        "x-codex-turn-metadata",
        "x-codex-window-id",
    }
    missing = codex_only - names
    assert not missing, (
        f"the runtime stopped sending {sorted(missing)}; the list of what "
        f"differs from the working path is now wrong and the next diagnostic "
        f"is aimed at the wrong thing"
    )


# ── The one thing that is the same on both paths ────────────────────────────

def test_the_codex_path_and_the_inference_path_post_to_the_same_url():
    """No runtime, no secret, no network: two derivations, one string.

    ``grade-run.yml`` passes only ``FOUNDRY_PROJECT_ENDPOINT`` and so does the
    Codex diagnostic, and both let ``AzureAIRouteSettings.from_env`` derive the
    direct ``/openai/v1/`` endpoint from it. Reading that in the source is not
    the same as running both and comparing what comes out, which is what this
    does -- against a stand-in account name, so it needs nothing privileged.

    This is what closes "the address is wrong" as a cause of the 401, and it is
    also what makes the remaining difference legible: same URL, same scope,
    different client and a body two orders of magnitude apart.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from diagnose_codex_foundry_connection import settings_from_environment

    env = {
        "AZURE_AI_ROUTE_PROFILE": "direct-v1",
        "FOUNDRY_PROJECT_ENDPOINT": (
            "https://a-stand-in-account.services.ai.azure.com"
            "/api/projects/a-project"
        ),
    }

    codex = settings_from_environment("a-deployment", env)
    inference = AzureAIRouteSettings.from_env(env).select(
        AzureAIWorkload.INFERENCE
    )

    assert (
        f"{codex.base_url}/responses"
        == f"{inference.endpoint.url.rstrip('/')}/responses"
    )
    assert inference.token_scope == "https://ai.azure.com/.default"
