"""The free half of the connection question, and what it may not claim.

Why this file exists
--------------------

Run ``34319880025`` sent one turn and got 401. Four things were then checked
and all four matched a path that demonstrably works: the URL, the token scope,
the header name and format, and the OIDC identity. Grading posts to the same
``https://<account>.<host>/openai/v1/`` with the same
``https://ai.azure.com/.default`` scope under the same login, and has produced
tens of thousands of graded rows there.

So the 401 was not located. What remained was a difference nobody had measured:
the grading and inference paths mint their token **in process**, through
``get_bearer_token_provider``; the Codex runtime runs the provider's
``auth.command`` as a **child process** and reads stdout. Two credential chains
in the same job can resolve differently.

``--read-only-probe`` closes that gap without spending anything. It mints the
token the way Codex does and issues ``GET {base_url}/models`` — a listing, no
prompt, no completion. A 200 says the token is accepted by that resource and
moves the question to something narrower than the identity. A 401 reproduces
the refusal for nothing.

What is asserted here
---------------------

Two classes of thing, and the second matters as much as the first:

1. that the probe reads the outcome off the wire — status, count, membership —
   rather than off what it hoped for;
2. that it cannot leak. The token is never in the record, never in an error
   message, and a failing auth command has its **stdout** withheld even though
   its stderr is quoted, because stdout is where a token would be.

Nothing here reaches the network. The auth command is a script this file
writes, and the listing is served by a socket on this machine.
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
    NOT_ESTABLISHED_BY_A_LISTING,
    READ_ONLY_SCHEMA,
    build_redactor,
    list_models_read_only,
    mint_token_the_way_codex_does,
    read_only_probe,
)

#: Not a credential. Shaped so it could not be mistaken for one in a log, and
#: distinctive enough that a leak into the record is a substring search away.
FAKE_TOKEN = "FAKE-TOKEN-NOT-A-CREDENTIAL-0123456789"


class _Listing:
    """A host that answers ``GET /models`` on a script and records the headers."""

    def __init__(self, status: int, payload: dict | None = None):
        self.status = status
        self.payload = payload
        self.calls: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):  # noqa: D102 - silence the default
                pass

            def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's spelling
                outer.calls.append(
                    {
                        "path": self.path,
                        "headers": {k.lower(): v for k, v in self.headers.items()},
                    }
                )
                body = json.dumps(
                    outer.payload
                    if outer.payload is not None
                    else {"error": {"message": "scripted refusal"}}
                ).encode()
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "_Listing":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)


def _settings(port: int, *, deployment: str = "a-deployment") -> CodexProviderSettings:
    """Real settings, pointed at a socket on this machine.

    ``classify_endpoint`` refuses anything but https, so the settings object is
    built on a real-shaped endpoint and only ``base_url`` is redirected — by
    subclassing, so every other field stays exactly what production computes.
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


def _printer(tmp_path: Path, *, token: str = FAKE_TOKEN, code: int = 0) -> Path:
    script = tmp_path / "auth_command.py"
    script.write_text(
        "import sys\n"
        f"sys.stdout.write({token!r} + chr(10))\n"
        f"sys.exit({code})\n",
        encoding="utf-8",
    )
    return script


def _with_auth_command(settings: CodexProviderSettings, argv: list[str]):
    class _Fixed(type(settings)):  # type: ignore[misc]
        @property
        def auth_command(self) -> list[str]:
            return argv

    return _Fixed(endpoint=settings.endpoint, model=settings.model)


# ── What the wire says ──────────────────────────────────────────────────────


def test_a_listed_deployment_is_reported_as_listed(tmp_path: Path):
    """200 plus membership, both read out of the response body."""
    payload = {"data": [{"id": "a-deployment"}, {"id": "another"}]}
    with _Listing(200, payload) as host:
        settings = _settings(host.port)
        outcome = list_models_read_only(settings, FAKE_TOKEN)
    assert outcome["status"] == 200
    assert outcome["models_listed"] == 2
    assert outcome["deployment_listed"] is True
    assert outcome["error"] is None
    assert host.calls[0]["path"] == "/v1/models"


def test_a_deployment_absent_from_the_listing_is_reported_absent(tmp_path: Path):
    """The case that would explain the 401 for nothing.

    A name that is not on the resource is the cheapest explanation there is,
    and it is reported as ``False`` rather than as an error, because the call
    succeeded — it is the answer that is negative, not the probe.
    """
    payload = {"data": [{"id": "something-else"}]}
    with _Listing(200, payload) as host:
        settings = _settings(host.port, deployment="not-there")
        outcome = list_models_read_only(settings, FAKE_TOKEN)
    assert outcome["status"] == 200
    assert outcome["deployment_listed"] is False


def test_a_refused_listing_records_the_status_rather_than_raising():
    """401 here is the finding: the refusal reproduced without a turn."""
    with _Listing(401) as host:
        settings = _settings(host.port)
        outcome = list_models_read_only(settings, FAKE_TOKEN)
    assert outcome["status"] == 401
    assert outcome["models_listed"] is None
    assert outcome["deployment_listed"] is None


def test_the_token_is_sent_the_way_the_turn_sends_it():
    """Same header name and format as the turn, measured on the socket.

    If this drifted, a 200 here would stop being evidence about the turn.
    """
    with _Listing(200, {"data": []}) as host:
        settings = _settings(host.port)
        list_models_read_only(settings, FAKE_TOKEN)
    assert host.calls[0]["headers"]["authorization"] == f"Bearer {FAKE_TOKEN}"


def test_nothing_is_asked_to_be_generated():
    """A GET with no body. The claim "this cannot cost tokens" is structural."""
    with _Listing(200, {"data": []}) as host:
        settings = _settings(host.port)
        list_models_read_only(settings, FAKE_TOKEN)
    call = host.calls[0]
    assert "content-length" not in call["headers"]
    assert call["path"].endswith("/models")


# ── Minting it the way Codex does ───────────────────────────────────────────


def test_the_token_comes_from_the_child_process_stdout(tmp_path: Path):
    """The whole point: the argv the provider table carries, run as a child."""
    settings = _with_auth_command(
        _settings(9999), [sys.executable, str(_printer(tmp_path))]
    )
    assert mint_token_the_way_codex_does(settings) == FAKE_TOKEN


def test_a_failing_auth_command_withholds_its_stdout(tmp_path: Path):
    """stderr is quoted; stdout is not, because stdout is where a token is.

    A command that fails *after* printing is not hypothetical — a credential
    chain can emit a token and then exit non-zero on a later step. Quoting
    stdout in the error would put it in the record and in the job log.
    """
    script = tmp_path / "loud_failure.py"
    script.write_text(
        "import sys\n"
        f"sys.stdout.write({FAKE_TOKEN!r})\n"
        "sys.stderr.write('chain exhausted')\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    settings = _with_auth_command(_settings(9999), [sys.executable, str(script)])
    with pytest.raises(RuntimeError) as caught:
        mint_token_the_way_codex_does(settings)
    message = str(caught.value)
    assert "chain exhausted" in message
    assert FAKE_TOKEN not in message


def test_an_empty_token_is_a_failure_not_an_empty_bearer(tmp_path: Path):
    """Otherwise the probe would send ``Bearer `` and blame the resource."""
    settings = _with_auth_command(
        _settings(9999), [sys.executable, str(_printer(tmp_path, token=""))]
    )
    with pytest.raises(RuntimeError, match="printed no token"):
        mint_token_the_way_codex_does(settings)


# ── The record ──────────────────────────────────────────────────────────────


def test_the_record_names_no_resource_and_carries_no_token(tmp_path: Path):
    """Read end to end, then searched.

    The endpoint appears only as a fingerprint, and the token appears nowhere,
    including inside ``settings`` — which is emitted whole.
    """
    payload = {"data": [{"id": "a-deployment"}]}
    with _Listing(200, payload) as host:
        settings = _with_auth_command(
            _settings(host.port), [sys.executable, str(_printer(tmp_path))]
        )
        record = read_only_probe(settings, redact=build_redactor())

    serialized = json.dumps(record)
    assert FAKE_TOKEN not in serialized
    assert "example-account" not in serialized
    assert record["schema"] == READ_ONLY_SCHEMA
    assert record["inference_requested"] is False
    assert record["token"]["minted"] is True
    assert record["endpoint_host_fingerprint"].startswith("sha256:")
    assert record["listing"]["status"] == 200
    assert record["listing"]["deployment_listed"] is True


def test_a_mint_failure_stops_before_the_network(tmp_path: Path):
    """No listing is attempted, and the record says so rather than reporting
    a status nobody received."""
    settings = _with_auth_command(_settings(9999), [sys.executable, "-c", "exit(9)"])
    record = read_only_probe(settings, redact=build_redactor())
    assert record["token"]["minted"] is False
    assert record["token"]["error"]
    assert record["listing"] is None


def test_the_record_states_what_a_two_hundred_does_not_prove(tmp_path: Path):
    """A listing is not a turn, and the record has to say so itself.

    Without this, a green read-only probe is exactly the kind of result that
    gets quoted as "the connection works".
    """
    with _Listing(200, {"data": []}) as host:
        settings = _with_auth_command(
            _settings(host.port), [sys.executable, str(_printer(tmp_path))]
        )
        record = read_only_probe(settings, redact=build_redactor())
    joined = " ".join(record["not_established"])
    assert "a listing is not a completion" in joined
    assert "unpriced call is not a proven free one" in joined


# ── The gate the record has to pass in CI ───────────────────────────────────
#
# The workflow's leak check is a heredoc, so nothing imports it and nothing
# ran it until here. It was written when one record shape existed and it
# indexed `record["observed"]` unconditionally; the read-only record has no
# such key, so publishing it would have raised KeyError inside an `always()`
# step and taken the job down after the run, not before it.
#
# So these tests execute the workflow's actual script. The only edit is the
# directory the records live in — `/tmp` is hardcoded there and a test must
# not write to the paths a real run uses. The path list itself is asserted
# separately and unedited, so the substitution cannot hide a missing file.

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
    # yaml has already stripped the block scalar's indentation, so the heredoc
    # terminator is flush left here even though it is indented in the file.
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


def _readonly_record() -> dict:
    return {
        "schema": READ_ONLY_SCHEMA,
        "inference_requested": False,
        "settings": {"model": "a-deployment"},
        "token": {"minted": True, "error": None},
        "listing": {"status": 200, "models_listed": 3, "deployment_listed": True},
        "not_established": list(NOT_ESTABLISHED_BY_A_LISTING),
    }


def _turn_record() -> dict:
    return {
        "schema": "codex_foundry_connection/2",
        "verdict": "connected",
        "observed": {"tool_execution_observed": False},
    }


def test_the_leak_check_accepts_a_read_only_record(tmp_path: Path):
    """The regression this section exists for: it must not KeyError."""
    code, output = _run_leak_check(
        tmp_path, {"codex-foundry-readonly.json": _readonly_record()}
    )
    assert code == 0, output
    assert "record=clean (1 checked)" in output


def test_the_leak_check_still_reads_both_shapes_in_one_run(tmp_path: Path):
    """A real dispatch writes both files. Both get checked, neither is skipped."""
    code, output = _run_leak_check(
        tmp_path,
        {
            "codex-foundry-readonly.json": _readonly_record(),
            "codex-foundry-connection.json": _turn_record(),
        },
    )
    assert code == 0, output
    assert "record=clean (2 checked)" in output


def test_the_leak_check_rejects_a_read_only_record_that_claims_a_request(
    tmp_path: Path,
):
    """The read-only record's one substantive claim is still enforced.

    Branching on schema must not amount to exempting the new shape.
    """
    record = _readonly_record()
    record["inference_requested"] = True
    code, output = _run_leak_check(tmp_path, {"codex-foundry-readonly.json": record})
    assert code == 1
    assert "claims a request was made" in output


def test_the_leak_check_still_rejects_a_turn_record_missing_its_observation(
    tmp_path: Path,
):
    """Fail closed: a connection record without `observed` is an error, not a pass.

    ``.get("observed", {})`` would have been the shorter fix and would have
    turned a renamed field into silence.
    """
    record = _turn_record()
    del record["observed"]
    code, output = _run_leak_check(tmp_path, {"codex-foundry-connection.json": record})
    assert code != 0
    assert "KeyError" in output or "observed" in output


def test_the_leak_check_reads_the_read_only_record_by_its_real_path():
    """The substitution above is only honest if this list is what CI checks."""
    source = _leak_check_source()
    for path in (
        "/tmp/codex-foundry-plan.json",
        "/tmp/codex-foundry-readonly.json",
        "/tmp/codex-foundry-connection.json",
    ):
        assert f'"{path}"' in source


def test_the_read_only_record_is_published_with_the_others():
    """An artifact that is checked and then not uploaded proves nothing later."""
    import yaml

    parsed = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = parsed["jobs"]["diagnose"]["steps"]
    keep = next(s for s in steps if s.get("name") == "Keep the record")
    assert "/tmp/codex-foundry-readonly.json" in keep["with"]["path"]

