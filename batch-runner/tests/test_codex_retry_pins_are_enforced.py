"""Count the requests one turn actually sends, against the real binary.

Why this file exists
--------------------

``scripts/diagnose_codex_foundry_connection.py`` reports a request plan, and
that plan used to contain the line ``"retries_configured": 0``. Nothing set it.
It was a number the script wrote about itself, in a dictionary the runtime
never reads, while the provider table said nothing about retries at all and the
runtime therefore used its own defaults — ``request_max_retries`` 4 and
``stream_max_retries`` 5.

The gap between those two facts is not academic. Measured here, one turn
against a server that answers HTTP 500 sends **thirty** requests when the
counters are unset. A diagnostic advertised as one cheap call was, on any
endpoint that failed the way a misconfigured endpoint usually fails, thirty
calls. The plan would still have said zero.

So this file does not check that a constant is zero. It starts the pinned
``codex`` binary, points it at a server on this machine that refuses in four
different ways, and counts what arrives. Two things are asserted:

1. with the settings this repository ships, one turn is one request — except
   on 401, where it is two, for a reason no supported key removes;
2. without the pins, it is not, and by a margin large enough that leaving them
   unset would be a real bill.

The second half is what keeps the first from being a tautology. A test that
only measured the pinned case would still pass if the pins stopped being
emitted and the runtime happened to default to one.

The token is fake
-----------------

The provider table here is the one ``provider_config_overrides`` builds for a
real deployment, with exactly two keys rewritten: ``base_url``, so the requests
arrive on this machine, and ``auth.command``, so the token is a fixed string
that is not a credential and was never minted.
:func:`test_only_the_destination_and_the_token_source_are_rewritten` asserts
that those two are the only differences, so the ``Authorization`` header this
file observes is produced by the same ``auth.*`` block production emits.

No sandbox is needed
--------------------

Every turn here dies on an HTTP response, which happens before the agent could
ask to run anything. So unlike ``test_codex_runtime_end_to_end.py``, this file
has nothing to skip on a host whose sandbox cannot start — it measures the same
numbers on the NAS and on a runner.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codex_runtime_config import (  # noqa: E402
    AUTH_RETRY_REQUESTS_NOT_REMOVED_BY_PINNING,
    DEFAULT_REQUEST_MAX_RETRIES,
    DEFAULT_STREAM_MAX_RETRIES,
    CodexProviderConfigurationError,
    CodexProviderLike,
    CodexProviderSettings,
    CodexRuntimeUnavailable,
    _toml_literal,
    provider_config_overrides,
    require_pinned_runtime,
)

_RUNTIME_PROBLEM: str | None = None
try:
    require_pinned_runtime()
except CodexRuntimeUnavailable as exc:  # pragma: no cover - environment shape
    _RUNTIME_PROBLEM = str(exc)

pytestmark = pytest.mark.skipif(
    _RUNTIME_PROBLEM is not None,
    reason=f"the pinned Codex runtime is not installed: {_RUNTIME_PROBLEM}",
)

#: Not a credential, and shaped so that it could not be mistaken for one in a
#: log. Nothing mints a token in this file.
FAKE_TOKEN = "FAKE-TOKEN-NOT-A-CREDENTIAL-0123456789"

#: A settings object with the endpoint shape production uses. Never called: the
#: table built from it is redirected to loopback before the runtime sees it.
REAL_SHAPED_SETTINGS = CodexProviderSettings(
    endpoint="https://example-account.openai.azure.com/openai/v1/",
    model="a-deployment",
)


# ── The far end of the wire ─────────────────────────────────────────────────


class RefusingResponses:
    """A Responses endpoint that refuses on a script and counts what arrives.

    ``status`` is answered to every request. ``drop=True`` instead writes half
    an SSE frame and kills the socket, which is the failure the runtime's
    *stream* retry counter governs rather than its request retry counter — the
    two are separate settings and only measuring both shows it.

    ``limit`` is a backstop, not a parameter of the experiment: past it the
    server stops answering so a runaway retry loop ends the test instead of
    hanging it. :attr:`overran` reports whether it was hit, and every assertion
    below checks it, because a count of 40 could otherwise mean "40 retries" or
    "far more than 40, silently truncated".
    """

    def __init__(self, status: int, *, drop: bool = False, limit: int = 40):
        self.status = status
        self.drop = drop
        self.limit = limit
        self.calls: list[dict] = []
        self.overran = False
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):  # noqa: D102 - silence the default
                pass

            def handle_one_request(self):
                # The runtime hangs up on us as readily as we hang up on it;
                # neither is a test failure.
                try:
                    super().handle_one_request()
                except (BrokenPipeError, ConnectionResetError):
                    self.close_connection = True

            def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler's spelling
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                with outer._lock:
                    outer.calls.append(
                        {
                            "path": self.path,
                            "headers": {
                                key.lower(): value
                                for key, value in self.headers.items()
                            },
                            "body_bytes": len(body),
                        }
                    )
                    count = len(outer.calls)
                    if count > outer.limit:
                        outer.overran = True
                if count > outer.limit:
                    self.close_connection = True
                    return
                if outer.drop:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    self.wfile.write(b'data: {"type":"response.created"}\n\n')
                    self.wfile.flush()
                    self.close_connection = True
                    try:
                        self.connection.close()
                    except OSError:
                        pass
                    return
                payload = json.dumps(
                    {"error": {"message": "scripted refusal", "type": "test"}}
                ).encode()
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "RefusingResponses":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)

    def authorization_headers(self) -> set[str]:
        """Every distinct credential header seen, with the fake token masked."""
        seen: set[str] = set()
        for call in self.calls:
            for name in ("authorization", "api-key", "x-api-key"):
                value = call["headers"].get(name)
                if value is not None:
                    seen.add(f"{name}: {value.replace(FAKE_TOKEN, '<FAKE-TOKEN>')}")
        return seen


# ── The provider table, production's minus two keys ─────────────────────────


def _token_printer(tmp_path: Path) -> tuple[Path, Path]:
    """A stand-in auth command: prints the fake token, logs that it ran.

    The log is how the auth-command count is measured. Counting notifications
    or log lines from the runtime would not answer the question — a retry that
    re-mints the token is visible only as a second run of this script.
    """
    calls = tmp_path / "auth-command-runs.log"
    script = tmp_path / "print_fake_token.py"
    script.write_text(
        "import sys\n"
        f"open({str(calls)!r}, 'a').write('ran\\n')\n"
        f"sys.stdout.write({FAKE_TOKEN!r} + chr(10))\n",
        encoding="utf-8",
    )
    return script, calls


def _redirected_table(
    port: int, printer: Path, settings: CodexProviderSettings
) -> tuple[str, ...]:
    """``provider_config_overrides(settings)`` with base_url and auth.command
    rewritten, and nothing else touched."""
    prefix = f"model_providers.{settings.provider_id}"
    rewritten: list[str] = []
    for override in provider_config_overrides(settings):
        if override.startswith(f"{prefix}.base_url="):
            rewritten.append(
                f"{prefix}.base_url="
                f"{_toml_literal(f'http://127.0.0.1:{port}/v1')}"
            )
        elif override.startswith(f"{prefix}.auth.command="):
            rewritten.append(f"{prefix}.auth.command={_toml_literal(sys.executable)}")
        elif override.startswith(f"{prefix}.auth.args="):
            rewritten.append(f"{prefix}.auth.args={_toml_literal([str(printer)])}")
        else:
            rewritten.append(override)
    return tuple(rewritten)


class _RedirectedProvider(CodexProviderLike):
    """Production's provider table, pointed at a server on this machine."""

    def __init__(self, port: int, printer: Path, settings: CodexProviderSettings):
        self.port = port
        self.printer = printer
        self.settings = settings
        self.model = settings.model
        self.provider_id = settings.provider_id

    def config_overrides(self) -> tuple[str, ...]:
        return _redirected_table(self.port, self.printer, self.settings)


# ── One turn, measured ──────────────────────────────────────────────────────


def _one_turn(
    tmp_path: Path,
    *,
    status: int,
    drop: bool = False,
    settings: CodexProviderSettings = REAL_SHAPED_SETTINGS,
) -> dict:
    """Send exactly one turn and report what the far end received.

    The stream is consumed rather than merely started. ``Thread.turn`` returns
    a handle and sends nothing until something iterates it, so a version of
    this that dropped the ``for`` loop would measure zero requests and read as
    proof that no retries happen.
    """
    from core.codex_runner import CodexAgentRunner, CodexWorkspace

    printer, call_log = _token_printer(tmp_path)
    with RefusingResponses(status, drop=drop) as server:
        runner = CodexAgentRunner(
            _RedirectedProvider(server.port, printer, settings), timeout=90
        )
        workspace = CodexWorkspace.create(task_id=f"retry-probe-{status}-{drop}")
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
        finally:
            if codex is not None:
                try:
                    codex.close()
                except Exception:  # noqa: BLE001 - teardown, not the subject
                    pass
            workspace.cleanup()

        return {
            "requests": len(server.calls),
            "overran": server.overran,
            "auth_command_runs": (
                len(call_log.read_text(encoding="utf-8").splitlines())
                if call_log.exists()
                else 0
            ),
            "authorization": server.authorization_headers(),
            "paths": sorted({call["path"] for call in server.calls}),
        }


# ── What the shipped settings cost ──────────────────────────────────────────


@pytest.mark.parametrize(
    "status, drop, label",
    [
        (429, False, "rate limited"),
        (500, False, "server error"),
        (200, True, "connection dropped mid-stream"),
    ],
)
def test_a_refused_turn_sends_one_request_with_the_shipped_settings(
    tmp_path: Path, status: int, drop: bool, label: str
):
    """The pins do what the plan says they do, measured at the socket."""
    assert DEFAULT_REQUEST_MAX_RETRIES == 0 and DEFAULT_STREAM_MAX_RETRIES == 0
    measured = _one_turn(tmp_path, status=status, drop=drop)
    assert not measured["overran"]
    assert measured["requests"] == 1, f"{label}: {measured}"


def test_an_unauthorized_turn_still_costs_two_requests(tmp_path: Path):
    """The residue the pins do not remove, asserted rather than glossed.

    On 401 the runtime re-runs the provider's auth command and retries once
    with the fresh token — the behaviour the config reference describes under
    ``auth.refresh_interval_ms`` ("set to 0 to refresh only after an
    authentication retry"). Neither retry counter binds it and no documented
    key switches it off.

    This is asserted at exactly 2 on purpose. If a future runtime removes the
    retry, this test fails and the constant, the docstring in
    ``codex_runtime_config`` and the diagnostic's record all get corrected
    together, instead of the repository quietly keeping a claim that stopped
    being true.
    """
    measured = _one_turn(tmp_path, status=401)
    assert not measured["overran"]
    assert measured["requests"] == AUTH_RETRY_REQUESTS_NOT_REMOVED_BY_PINNING == 2
    assert measured["auth_command_runs"] == 2, (
        "two requests with one token would be a plain retry; the second token "
        f"is what identifies this as the auth refresh: {measured}"
    )


# ── What leaving them unset would cost ──────────────────────────────────────


@pytest.mark.parametrize(
    "status, drop, at_least",
    [
        # 5 request attempts x 6 stream attempts, per the published defaults.
        (500, False, 20),
        # The stream counter alone, so the two are shown to be separate keys.
        (200, True, 4),
    ],
)
def test_leaving_the_counters_unset_multiplies_one_turn(
    tmp_path: Path, status: int, drop: bool, at_least: int
):
    """The measurement that makes the pins worth having.

    Lower bounds rather than exact counts: the numbers observed are 30 and 6,
    but a runtime that retried slightly differently would still be making the
    point this test exists to make, and an exact match would turn a patch
    release into a red build for no reason. The bound is far enough above 1
    that no amount of drift makes an unpinned turn cheap.
    """
    unpinned = CodexProviderSettings(
        endpoint=REAL_SHAPED_SETTINGS.endpoint,
        model=REAL_SHAPED_SETTINGS.model,
        request_max_retries=4,
        stream_max_retries=5,
    )
    measured = _one_turn(tmp_path, status=status, drop=drop, settings=unpinned)
    assert not measured["overran"]
    assert measured["requests"] >= at_least, measured


# ── Where the token goes ────────────────────────────────────────────────────


def test_the_token_arrives_as_an_authorization_bearer_header(tmp_path: Path):
    """Measured, not inferred from the fact that other callers use this scope.

    That the repository's other Azure paths ask for the same token scope says
    nothing about what Codex does with the string its ``auth.command`` prints.
    This observes the header on the wire: the token is carried as
    ``Authorization: Bearer``, on ``POST /v1/responses``, and not as the
    ``api-key`` header the legacy Azure route expects.
    """
    measured = _one_turn(tmp_path, status=401)
    assert measured["authorization"] == {"authorization: Bearer <FAKE-TOKEN>"}
    assert measured["paths"] == ["/v1/responses"]
    assert measured["auth_command_runs"] >= 1


def test_only_the_destination_and_the_token_source_are_rewritten(tmp_path: Path):
    """The seam between this file and production, made auditable.

    If a later change added a key to the production table, this fails unless
    the redirected table carries it too — so the header and count measurements
    above cannot drift into describing a provider nobody uses.
    """
    printer, _ = _token_printer(tmp_path)
    production = list(provider_config_overrides(REAL_SHAPED_SETTINGS))
    redirected = list(_redirected_table(9999, printer, REAL_SHAPED_SETTINGS))
    assert len(production) == len(redirected)
    differing = [
        original.split("=", 1)[0]
        for original, rewritten in zip(production, redirected)
        if original != rewritten
    ]
    prefix = f"model_providers.{REAL_SHAPED_SETTINGS.provider_id}"
    # ``auth.command`` is allowed to coincide rather than required to differ:
    # production runs the token module with this same interpreter, so
    # rewriting the command to ``sys.executable`` is often a no-op and only
    # ``auth.args`` moves. The seam is still exactly these three keys.
    assert set(differing) <= {
        f"{prefix}.base_url",
        f"{prefix}.auth.command",
        f"{prefix}.auth.args",
    }
    assert f"{prefix}.base_url" in differing, "the destination must be redirected"
    assert f"{prefix}.auth.args" in differing, "the token source must be replaced"


# ── The table itself ────────────────────────────────────────────────────────


def test_the_provider_table_carries_both_counters_at_zero():
    """Emitted, not merely defaulted in Python.

    An unset key is the runtime's 4 and 5, so a settings object that held 0 and
    never wrote it would produce exactly the thirty-request turn this change
    exists to prevent.
    """
    prefix = f"model_providers.{REAL_SHAPED_SETTINGS.provider_id}"
    overrides = provider_config_overrides(REAL_SHAPED_SETTINGS)
    assert f"{prefix}.request_max_retries=0" in overrides
    assert f"{prefix}.stream_max_retries=0" in overrides


@pytest.mark.parametrize("value", [-1, True, 1.5, "0", None])
def test_a_retry_count_that_is_not_a_whole_non_negative_number_is_refused(value):
    """``True`` is in this list because ``bool`` is an ``int`` and would be
    rendered into the table as ``true`` — a type error the runtime would report
    about a config file no operator wrote."""
    with pytest.raises(CodexProviderConfigurationError):
        CodexProviderSettings(
            endpoint=REAL_SHAPED_SETTINGS.endpoint,
            model=REAL_SHAPED_SETTINGS.model,
            request_max_retries=value,
        )


def test_no_real_token_is_ever_minted_here(tmp_path: Path):
    """The auth command handed to the runtime is the fake printer.

    Checked on the table rather than by grepping this file for a module name:
    what matters is what the runtime is told to run, and the printer's own
    source is asserted to hold the fake string and nothing that reaches Entra.
    """
    printer, _ = _token_printer(tmp_path)
    table = _redirected_table(9999, printer, REAL_SHAPED_SETTINGS)
    args_line = next(line for line in table if ".auth.args=" in line)
    assert str(printer) in args_line
    assert "--scope" not in args_line

    printed = printer.read_text(encoding="utf-8")
    assert FAKE_TOKEN in printed
    assert "azure" not in printed.lower()
