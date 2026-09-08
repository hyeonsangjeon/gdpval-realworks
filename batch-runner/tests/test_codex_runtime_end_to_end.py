"""Drive the real Codex runtime, end to end, without paying a model.

Why this file is not a unit test
--------------------------------

The Codex run place's whole claim is that a real agent harness plans, calls
tools and edits files on its own. A test that replaced
:class:`openai_codex.Codex` with a mock would be checking that our own calls
line up with our own stubs — it could pass with the Codex binary uninstalled,
which is exactly the situation it is supposed to detect.

So nothing here is mocked except the far end of the wire. Every test in this
file starts the pinned ``codex`` binary through the pinned SDK, over real
JSON-RPC, in a real per-task directory, under the same workspace-write sandbox
a paid run uses. What is replaced is only the Responses endpoint: a
:class:`ScriptedResponses` server on ``127.0.0.1`` answers the runtime's HTTP
requests from a script. The runtime cannot tell the difference, which is the
point — the leg between us and the runtime is the leg being tested.

:class:`~core.codex_runtime_config.LoopbackCodexProvider` is how the runner is
pointed at it. It exists because
:class:`~core.codex_runtime_config.CodexProviderSettings` refuses a loopback
address and should keep refusing one; see ``core/executor.py``, where an
experiment holding a loopback provider is rejected before a runner is built.

What a paid deployment would still have to prove
------------------------------------------------

This file establishes that the harness works. It cannot establish that a
Foundry deployment answers Codex's ``responses`` wire format, that the auth
command's token is accepted, or that the pinned Codex version is compatible
with our region — the scripted server accepts anything. Those three are the
blockers recorded in ``core.execution_environment_readiness``.

Sandboxing and this machine
---------------------------

The agent's file writes go through ``exec_command``, which Codex runs inside a
sandbox. On a kernel without usable unprivileged user namespaces the sandbox
cannot start at all — the NAS this repository is often edited on runs 3.10, and
both of Codex's Linux backends fail there. Where that happens, the assertions
that depend on a command having *run* skip with the runtime's own error text,
and the rest of the chain is still asserted. The sandbox is never turned off to
make a test pass: a run with the sandbox disabled would not be the
configuration anything else uses.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import pytest

from core.codex_cost import CODEX_STRUCTURAL_REASONS
from core.codex_runner import CodexAgentRunner, CodexWorkspace
from core.codex_runtime_config import (
    CREDENTIAL_ENV_NAMES,
    NEUTRALISED_ENV_NAMES,
    CodexProviderConfigurationError,
    CodexProviderSettings,
    CodexRuntimeUnavailable,
    LoopbackCodexProvider,
    require_pinned_runtime,
)
from core.cost_receipts import (
    REASON_USAGE_ABSENT,
    STATE_RESERVED,
    STATE_SETTLED,
    CostReceiptLedger,
)

# The whole file needs the pinned runtime; there is no half-measure. A skip
# here means the binary is absent and the run place is *not* covered — which is
# why CI installs it rather than relying on this skip.
_RUNTIME_PROBLEM: str | None = None
try:
    require_pinned_runtime()
except CodexRuntimeUnavailable as exc:  # pragma: no cover - environment shape
    _RUNTIME_PROBLEM = str(exc)

pytestmark = pytest.mark.skipif(
    _RUNTIME_PROBLEM is not None,
    reason=f"the pinned Codex runtime is not installed: {_RUNTIME_PROBLEM}",
)


# ── The stand-in Responses endpoint ─────────────────────────────────────────


def _sse(events: list[dict]) -> bytes:
    return "".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        for event in events
    ).encode("utf-8")


def _usage(
    *, input_tokens: int, output_tokens: int, cached: int, reasoning: int
) -> dict:
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_tokens_details": {"cached_tokens": cached},
        "output_tokens_details": {"reasoning_tokens": reasoning},
        "total_tokens": input_tokens + output_tokens,
    }


#: The two scripted replies of the headline test, and what the runtime adds up
#: from them. Codex reports a *thread* total, not a per-request one, so the
#: settled receipt carries the sum — which is the reason the adapter subtracts a
#: before-total rather than copying the last number it saw.
TOOL_TURN_USAGE = _usage(input_tokens=11, output_tokens=7, cached=3, reasoning=2)
FINAL_TURN_USAGE = _usage(input_tokens=40, output_tokens=12, cached=8, reasoning=3)


def says_run_this(command: str, *, call_id: str = "call_1") -> Callable:
    """Script one reply that asks the agent to run ``command``.

    ``exec_command`` is the tool Codex offers for shell work; the name and the
    argument shape are read off the ``tools`` array the runtime itself sends,
    not guessed at.
    """

    def reply(_request: dict, index: int) -> tuple[int, bytes]:
        return 200, _sse(
            [
                {
                    "type": "response.created",
                    "response": {"id": f"resp_{index}", "status": "in_progress"},
                },
                {
                    "type": "response.output_item.done",
                    "output_index": 0,
                    "item": {
                        "type": "function_call",
                        "id": f"fc_{index}",
                        "call_id": call_id,
                        "name": "exec_command",
                        "arguments": json.dumps(
                            {"cmd": command, "yield_time_ms": 10_000}
                        ),
                        "status": "completed",
                    },
                },
                {
                    "type": "response.completed",
                    "response": {
                        "id": f"resp_{index}",
                        "status": "completed",
                        "usage": TOOL_TURN_USAGE,
                    },
                },
            ]
        )

    return reply


def says(text: str, *, usage: dict | None = FINAL_TURN_USAGE) -> Callable:
    """Script one reply that finishes the turn with ``text``.

    ``usage=None`` scripts a completion that reports no tokens at all, which is
    how a provider that says nothing about cost is reproduced.
    """

    def reply(_request: dict, index: int) -> tuple[int, bytes]:
        response: dict[str, Any] = {"id": f"resp_{index}", "status": "completed"}
        if usage is not None:
            response["usage"] = usage
        return 200, _sse(
            [
                {
                    "type": "response.created",
                    "response": {"id": f"resp_{index}", "status": "in_progress"},
                },
                {
                    "type": "response.output_item.done",
                    "output_index": 0,
                    "item": {
                        "type": "message",
                        "id": f"msg_{index}",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": text}],
                    },
                },
                {"type": "response.completed", "response": response},
            ]
        )

    return reply


def refuses(status: int = 400, message: str = "scripted provider failure"):
    """Script an HTTP failure from the provider.

    400 by default and deliberately: Codex retries a 5xx by itself, around
    thirty times with backoff, so a scripted 500 would be measuring the
    runtime's retry policy rather than our handling of a refusal.
    """

    def reply(_request: dict, _index: int) -> tuple[int, bytes]:
        return status, json.dumps({"error": {"message": message}}).encode()

    return reply


def stalls(stop: threading.Event, seconds: float = 120.0):
    """Script a reply that never arrives in time.

    Waits on an event rather than sleeping, so the server thread unblocks at
    teardown instead of holding the test run open for two minutes.
    """

    def reply(_request: dict, _index: int) -> tuple[int, bytes]:
        stop.wait(seconds)
        return 503, b"{}"

    return reply


class ScriptedResponses:
    """A Responses endpoint on ``127.0.0.1`` that answers from a script.

    Each entry in ``script`` answers one request, in order. Running past the end
    is recorded rather than absorbed: a turn that made more requests than the
    test expected is a fact the test should be able to show. Where the runtime's
    own retrying makes the count uninteresting — a refusal — ``repeat_last``
    keeps answering with the final entry.
    """

    def __init__(self, script: list[Callable], *, repeat_last: bool = False):
        self._script = list(script)
        self._repeat_last = repeat_last
        self.requests: list[dict] = []
        self.overruns = 0
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):  # keep pytest output readable
                pass

            def handle_one_request(self):
                # A turn that was interrupted, or a client that gave up, leaves
                # a half-written socket behind. That is the test's subject, not
                # a problem with the stand-in, so it is not printed.
                try:
                    super().handle_one_request()
                except (BrokenPipeError, ConnectionResetError):
                    self.close_connection = True

            def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler's name
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError:
                    body = {"__unparsed__": raw.decode("utf-8", "replace")}
                with outer._lock:
                    index = len(outer.requests)
                    outer.requests.append({"path": self.path, "body": body})
                    if index < len(outer._script):
                        reply = outer._script[index]
                    elif outer._repeat_last and outer._script:
                        reply = outer._script[-1]
                    else:
                        outer.overruns += 1
                        reply = None
                if reply is None:
                    status = 409
                    payload = b'{"error":{"message":"unscripted request"}}'
                else:
                    status, payload = reply(body, index)
                content_type = (
                    "text/event-stream" if status == 200 else "application/json"
                )
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )

    def __enter__(self) -> "ScriptedResponses":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)

    # -- reading what the runtime sent -----------------------------------

    def request_bodies(self) -> list[dict]:
        with self._lock:
            return [entry["body"] for entry in self.requests]

    def tool_results(self) -> list[dict]:
        """Every ``function_call_output`` the runtime fed back to the model."""
        found: list[dict] = []
        for body in self.request_bodies():
            for item in body.get("input") or ():
                if isinstance(item, dict) and (
                    item.get("type") == "function_call_output"
                ):
                    found.append(item)
        return found

    def tool_output_text(self) -> str:
        return "\n".join(
            str(item.get("output", "")) for item in self.tool_results()
        )


# ── Sandbox availability on the host running the test ───────────────────────

#: What Codex says when the kernel will not give it a sandbox. Matched rather
#: than guessed at: both alternatives are quoted from a real run on a 3.10
#: kernel, one per Linux backend Codex has.
_SANDBOX_CANNOT_START = re.compile(
    r"bwrap: Creating new namespace failed"
    r"|permission profiles requiring direct runtime enforcement"
)


def sandbox_refused(server: ScriptedResponses) -> str | None:
    """The reason the sandbox could not run a command, if that is what happened.

    ``None`` when a command actually ran, whatever its exit status. A command
    that ran and failed is a test failure; a sandbox that could not start is a
    property of the machine, and the tests that need one say so and skip.
    """
    text = server.tool_output_text()
    if _SANDBOX_CANNOT_START.search(text):
        return text.strip().splitlines()[-1]
    return None


# ── Fixtures and helpers ────────────────────────────────────────────────────


class temporarily_set:
    """Add names to ``os.environ`` for the duration of a block."""

    def __init__(self, values: dict):
        self._values = values
        self._saved: dict = {}

    def __enter__(self):
        for name, value in self._values.items():
            self._saved[name] = os.environ.get(name)
            os.environ[name] = value
        return self

    def __exit__(self, *_exc):
        for name, previous in self._saved.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


@pytest.fixture
def ledger(tmp_path: Path):
    with CostReceiptLedger(
        tmp_path / "receipts.sqlite3", run_id="codex-e2e"
    ) as opened:
        yield opened


@pytest.fixture
def reference_file(tmp_path: Path) -> str:
    path = tmp_path / "inputs" / "reference.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("The agreed unit price is 42 dollars.\n", encoding="utf-8")
    return str(path)


def runner_for(
    server: ScriptedResponses,
    *,
    ledger: CostReceiptLedger | None = None,
    timeout: int = 180,
) -> CodexAgentRunner:
    return CodexAgentRunner(
        LoopbackCodexProvider(port=server.port),
        timeout=timeout,
        cost_ledger=ledger,
        run_id="codex-e2e",
        condition_name="condition_a",
    )


#: What the scripted model asks the agent to run: read the staged reference,
#: write a deliverable from it. Deliberately plain shell — the point is that the
#: agent ran something in its own directory, not that it ran something clever.
_WRITE_THE_DELIVERABLE = (
    "printf 'Quoted price: ' > answer.md && cat reference.txt >> answer.md"
)


# ── The chain, start to finish ──────────────────────────────────────────────


def test_a_turn_starts_a_runtime_calls_a_tool_and_comes_back_with_a_file(
    ledger: CostReceiptLedger, reference_file: str
):
    """Runtime start → tool call → reference read → deliverable → cost.

    The test this file exists for. Everything it asserts happened inside a real
    ``codex app-server`` process talking JSON-RPC to the pinned SDK.
    """
    with ScriptedResponses(
        [says_run_this(_WRITE_THE_DELIVERABLE), says("wrote answer.md")]
    ) as server:
        result = runner_for(server, ledger=ledger).run(
            "Read reference.txt and write answer.md quoting the price.",
            reference_files=[reference_file],
            task_id="task-e2e-1",
        )

        # The runtime started and reached the endpoint at all.
        assert len(server.requests) == 2, server.request_bodies()
        assert server.overruns == 0

        # It offered the model its own tools — we did not supply these.
        tool_names = {
            tool.get("name")
            for tool in server.request_bodies()[0].get("tools") or ()
        }
        assert "exec_command" in tool_names

        # It ran the tool call and fed the result back. This is the round trip a
        # mocked SDK cannot demonstrate: the second request carries the output
        # of a command the first request asked for.
        assert [item["call_id"] for item in server.tool_results()] == ["call_1"]

        refusal = sandbox_refused(server)

    # The turn completed and the final message came back through the SDK.
    assert result["success"] is True, result.get("error")
    assert result["text"] == "wrote answer.md"

    # One receipt for one turn, settled, carrying the thread's tokens — not one
    # invented row per model request, which is what the structural reason says.
    calls = ledger.calls_for("task-e2e-1")
    assert len(calls) == 1
    assert calls[0]["state"] == STATE_SETTLED
    assert calls[0]["input_tokens"] == 51  # 11 + 40, the thread total
    assert calls[0]["output_tokens"] == 19  # 7 + 12
    assert calls[0]["cached_input_tokens"] == 11  # 3 + 8
    assert calls[0]["reasoning_tokens"] == 5  # 2 + 3
    assert CODEX_STRUCTURAL_REASONS[0] in calls[0]["missing_reasons"]

    if refusal:
        pytest.skip(
            "this kernel gives Codex no sandbox, so the command it was asked "
            f"to run could not execute: {refusal}"
        )

    # The deliverable exists and was built from the staged reference. The
    # reference itself is not reported as something the run produced.
    names = {entry["filename"] for entry in result["files"]}
    assert names == {"answer.md"}, names
    written = result["files"][0]["content"].decode("utf-8")
    assert written == "Quoted price: The agreed unit price is 42 dollars.\n"


def test_a_reference_file_is_an_input_not_a_deliverable(reference_file: str):
    """Handing the agent a file must not credit the run with producing it."""
    with ScriptedResponses([says("nothing to do")]) as server:
        result = runner_for(server).run(
            "Say nothing.", reference_files=[reference_file], task_id="task-ro"
        )
    assert result["success"] is True
    assert result["files"] == []


def test_the_agent_is_told_which_reference_files_it_has(reference_file: str):
    """The names reach the model; the agent reads the bytes itself."""
    with ScriptedResponses([says("noted")]) as server:
        result = runner_for(server).run(
            "Summarise the reference.",
            reference_files=[reference_file],
            task_id="task-prompt",
        )
        assert result["success"] is True
        sent = json.dumps(server.request_bodies()[0])
    assert "reference.txt" in sent


# ── Isolation between tasks ─────────────────────────────────────────────────


def test_two_tasks_get_two_directories_and_neither_holds_the_others_files(
    tmp_path: Path,
):
    """The isolation is the directory, so this checks the directories.

    Runs without a sandbox, so it holds on every host — the agent's own view of
    the same fact is the next test, which needs one.
    """
    first = tmp_path / "alpha-secret.txt"
    first.write_text("alpha\n", encoding="utf-8")
    second = tmp_path / "beta-secret.txt"
    second.write_text("beta\n", encoding="utf-8")

    alpha = CodexWorkspace.create(task_id="task-alpha")
    beta = CodexWorkspace.create(task_id="task-beta")
    try:
        alpha.stage_references([str(first)])
        beta.stage_references([str(second)])
        assert alpha.workspace != beta.workspace
        assert alpha.codex_home != beta.codex_home
        assert alpha.home != beta.home
        alpha_names = {path.name for path in alpha.workspace.rglob("*")}
        beta_names = {path.name for path in beta.workspace.rglob("*")}
        assert alpha_names == {"alpha-secret.txt"}
        assert beta_names == {"beta-secret.txt"}
    finally:
        alpha.cleanup()
        beta.cleanup()


def test_the_agent_cannot_see_the_other_tasks_files(tmp_path: Path):
    """Asked of the agent itself, by having it list what it can reach."""
    first = tmp_path / "alpha-secret.txt"
    first.write_text("alpha\n", encoding="utf-8")
    second = tmp_path / "beta-secret.txt"
    second.write_text("beta\n", encoding="utf-8")

    listings: list[str] = []
    for label, source in (("alpha", first), ("beta", second)):
        with ScriptedResponses(
            [says_run_this("ls -1"), says(f"listed for {label}")]
        ) as server:
            result = runner_for(server).run(
                "List the directory.",
                reference_files=[str(source)],
                task_id=f"task-{label}",
            )
            assert result["success"] is True, result.get("error")
            refusal = sandbox_refused(server)
            if refusal:
                pytest.skip(
                    "this kernel gives Codex no sandbox, so the agent could "
                    f"not be asked what it can see: {refusal}"
                )
            listings.append(server.tool_output_text())

    assert "alpha-secret.txt" in listings[0]
    assert "beta-secret.txt" not in listings[0]
    assert "beta-secret.txt" in listings[1]
    assert "alpha-secret.txt" not in listings[1]


def test_the_task_directory_is_removed_when_the_task_ends(reference_file: str):
    """Nothing is left on disk afterwards, including the read-only copies."""
    parent = Path(tempfile.gettempdir())
    before = {entry.name for entry in parent.glob("gdpval-codex-*")}
    with ScriptedResponses([says("done")]) as server:
        runner_for(server).run(
            "Do nothing.",
            reference_files=[reference_file],
            task_id="task-cleanup",
        )
    after = {entry.name for entry in parent.glob("gdpval-codex-*")}
    assert after - before == set()


def test_the_runtime_gets_none_of_the_operators_codex_state():
    """``CODEX_HOME``, the operator's sign-in and their plugins stay outside.

    The SDK *merges* our environment over the parent's rather than replacing it,
    so isolation cannot be done by leaving a name out — it has to be written
    over. Checked against a parent process that has every one of the names set
    to something recognisable, so a variable that slipped through would be
    visible rather than merely absent.
    """
    operators_own = "/operator/private"
    workspace = CodexWorkspace.create(task_id="task-env")
    try:
        runner = CodexAgentRunner(
            LoopbackCodexProvider(port=1), verify_runtime=False
        )
        polluted = {name: operators_own for name in NEUTRALISED_ENV_NAMES}
        with temporarily_set(polluted):
            built = runner._build_environment(workspace)

        # Nothing of the operator's survives anywhere.
        assert [
            name
            for name in NEUTRALISED_ENV_NAMES
            if built.get(name) == operators_own
        ] == []
        # Credentials arrive blank: there is no task value to redirect them to.
        assert [
            name for name in CREDENTIAL_ENV_NAMES if built.get(name)
        ] == []
        # The state variables are redirected into this task, so a runtime that
        # writes "to the home directory" writes inside the directory that is
        # removed when the task ends.
        assert built["CODEX_HOME"] == str(workspace.codex_home)
        assert built["HOME"] == str(workspace.home)
        for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
            assert built[name].startswith(str(workspace.home)), name
        # The loopback stand-in's own variable is present, and is not a secret.
        assert built["GDPVAL_CODEX_LOOPBACK_KEY"] == (
            "loopback-stand-in-not-a-credential"
        )
    finally:
        shutil.rmtree(workspace.root, ignore_errors=True)


# ── Failure, refusal, and the absence of a fallback ─────────────────────────


def test_a_provider_refusal_is_reported_not_papered_over(
    ledger: CostReceiptLedger,
):
    """The endpoint refuses; the run place says so and produces nothing.

    Specifically it does not quietly hand the task to another runner. That would
    fill the Codex column of a run-place comparison with a subprocess run's
    numbers. The receipt stays open rather than being abandoned, because the
    request did leave and may have been billed.
    """
    with ScriptedResponses([refuses(400)], repeat_last=True) as server:
        result = runner_for(server, ledger=ledger).run(
            "Anything.", task_id="task-refused"
        )
    assert result["success"] is False
    assert result["error_category"] == "turn_failed"
    assert result["text"] == ""
    assert result["files"] == []
    assert "scripted provider failure" in result["error"]

    calls = ledger.calls_for("task-refused")
    assert len(calls) == 1
    assert calls[0]["state"] == STATE_RESERVED
    assert calls[0]["model_cost_usd"] is None


def test_an_endpoint_that_is_not_listening_fails_rather_than_falling_back(
    ledger: CostReceiptLedger,
):
    """A closed port is a Codex failure, not a reason to run something else."""
    with ScriptedResponses([says("unused")]) as server:
        port = server.port
    # The server is closed now, so nothing answers on that port.
    result = CodexAgentRunner(
        LoopbackCodexProvider(port=port),
        timeout=120,
        cost_ledger=ledger,
        run_id="codex-e2e",
    ).run("Anything.", task_id="task-closed")

    assert result["success"] is False
    assert result["error_category"] == "turn_failed"
    assert result["files"] == []
    assert ledger.calls_for("task-closed")[0]["state"] == STATE_RESERVED


def test_a_turn_that_overruns_is_interrupted_and_leaves_its_receipt_open(
    ledger: CostReceiptLedger,
):
    """A timeout is not an abandonment.

    The request went out. The model may have answered it and it may have been
    billed, so the reservation stays open — which is how the ledger says "a cost
    may exist here that we could not measure". Marking it abandoned would be
    recording a zero we never observed.
    """
    stop = threading.Event()
    try:
        with ScriptedResponses([stalls(stop)], repeat_last=True) as server:
            started = time.monotonic()
            result = runner_for(server, ledger=ledger, timeout=5).run(
                "Take your time.", task_id="task-timeout"
            )
            elapsed = time.monotonic() - started
    finally:
        stop.set()

    assert result["success"] is False
    assert result["error_category"] == "timeout"
    assert "5 seconds" in result["error"]
    # Interrupted near the limit, not left to run to the scripted 120 seconds.
    assert elapsed < 60, elapsed

    calls = ledger.calls_for("task-timeout")
    assert len(calls) == 1
    assert calls[0]["state"] == STATE_RESERVED
    assert calls[0]["model_cost_usd"] is None


def test_a_turn_that_reports_no_usage_settles_as_absent_not_as_zero(
    ledger: CostReceiptLedger,
):
    """Silence about tokens is recorded as silence.

    A turn whose provider reported nothing must not appear as a free one;
    ``usage_absent`` is the difference between "cost nothing" and "cost
    unknown".
    """
    with ScriptedResponses([says("done", usage=None)]) as server:
        result = runner_for(server, ledger=ledger).run(
            "Anything.", task_id="task-no-usage"
        )
    assert result["success"] is True

    calls = ledger.calls_for("task-no-usage")
    assert len(calls) == 1
    assert calls[0]["state"] == STATE_SETTLED
    assert calls[0]["input_tokens"] is None
    assert calls[0]["output_tokens"] is None
    assert calls[0]["model_cost_usd"] is None
    assert REASON_USAGE_ABSENT in calls[0]["missing_reasons"]


def test_running_a_task_twice_opens_two_receipts(ledger: CostReceiptLedger):
    """A retry is a second cost, so it gets a second row.

    Settling a second turn onto the first turn's receipt would silently discard
    what the retry cost.
    """
    with ScriptedResponses([says("first"), says("second")]) as server:
        runner = runner_for(server, ledger=ledger)
        assert runner.run("Anything.", task_id="task-twice")["success"] is True
        assert runner.run("Anything.", task_id="task-twice")["success"] is True

    calls = ledger.calls_for("task-twice")
    assert len(calls) == 2
    assert len({call["call_id"] for call in calls}) == 2
    assert {call["state"] for call in calls} == {STATE_SETTLED}
    assert [call["input_tokens"] for call in calls] == [40, 40]


def test_asking_for_a_deployment_this_run_place_was_not_given_is_refused(
    ledger: CostReceiptLedger,
):
    """No request leaves. The recorded model and the called model cannot drift."""
    with ScriptedResponses([says("should not be reached")]) as server:
        result = runner_for(server, ledger=ledger).run(
            "Anything.", model="some-other-deployment", task_id="task-mismatch"
        )
        assert server.requests == []
    assert result["success"] is False
    assert result["error_category"] == "model_mismatch"
    assert ledger.calls_for("task-mismatch") == []


# ── The stand-in is an instrument, not a run mode ───────────────────────────


def test_a_real_experiment_cannot_be_pointed_at_the_loopback_stand_in():
    """``core/executor.py`` builds runners for experiments and takes only the
    real settings class. Without that refusal, a results file produced against
    ``127.0.0.1`` would be indistinguishable from one that cost money."""
    from core.executor import TaskExecutor

    with pytest.raises(CodexProviderConfigurationError):
        TaskExecutor(
            "codex_foundry",
            codex_options={"provider_settings": LoopbackCodexProvider(port=1)},
        )


def test_the_settings_class_still_refuses_a_loopback_address():
    """And it refuses it through the repository's own endpoint classifier."""
    with pytest.raises(CodexProviderConfigurationError):
        CodexProviderSettings(endpoint="http://127.0.0.1:9/v1", model="anything")
