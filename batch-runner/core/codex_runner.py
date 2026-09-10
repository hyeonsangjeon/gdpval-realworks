"""Hand one GDPVal task to the real Codex runtime and collect what it made.

This is the execution half of the Codex run place; ``core/codex_runtime_config``
holds the settings half. The runtime here is not a stand-in: the pinned
``openai-codex`` SDK starts the Codex binary as ``codex app-server`` and speaks
JSON-RPC to it, so a turn run through this module is the agent harness doing
its own planning, its own tool calls and its own file edits. We give it a
directory and a prompt; what it does in between is its own.

That is also why the shape of this module differs from the other run places.
``core/subprocess_runner.py`` asks a model for a program and then runs the
program itself, so it knows exactly how many requests happened and exactly what
executed. Here we know neither. What we can control is the boundary — one fresh
session per task, one directory per task, a wall-clock limit, and a sweep for
anything still running afterwards — and that boundary is what this module is
mostly made of.

Refusal instead of substitution
-------------------------------

Every failure path returns a result saying what went wrong. None of them falls
back to another runner. A comparison of run places is only worth reading if the
Codex column contains Codex results or an explicit reason it has none; a
silently substituted subprocess run would make the column a duplicate of a
neighbouring one while still being labelled Codex.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from core.codex_cost import (
    CodexTokenTotals,
    read_thread_totals,
    settle_codex_turn,
    turn_usage_delta,
)
from core.codex_runtime_config import (
    CodexProviderConfigurationError,
    CodexProviderLike,
    CodexRuntimeUnavailable,
    FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV,
    NEUTRALISED_ENV_NAMES,
    build_isolated_environment,
    require_pinned_runtime,
    resolve_run_root_base,
)
from core.cost_metering import CostRecorder
from core.cost_receipts import STAGE_GENERATION, RETRY_NONE, make_call_id
from core.execution_envelope_observed import (
    API_FAMILY_RESPONSES,
    RecordsItsFirstRequest,
)
from core.execution_errors import classify_execution_error
from core.execution_environment_readiness import (
    ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY,
)
from core.reference_integrity import ReferenceIntegrityError, copy_verified_reference

#: Wall-clock limit for one task's turn. Longer than the subprocess mode's
#: limit because an agent's turn covers planning, several model requests and
#: however many commands it decides to run, where the subprocess mode's covers
#: only the execution of a program already written.
CODEX_TURN_TIMEOUT = int(os.getenv("CODEX_TURN_TIMEOUT", "900"))

#: How long to wait for a turn to stop after we ask it to. Codex is told to
#: interrupt first; only when that produces nothing is the process torn down.
CODEX_INTERRUPT_GRACE_SECONDS = float(os.getenv("CODEX_INTERRUPT_GRACE", "20"))

#: Files the runtime keeps for its own purposes, which are not deliverables
#: and whose names do not begin with a dot. The four that did -- ``.codex``,
#: ``.git``, ``.pytest_cache``, ``.venv`` -- are covered by the rule in
#: :meth:`CodexWorkspace.collect_deliverables` that skips anything hidden, and
#: naming them here as well would suggest the others are collectable.
_NOT_A_DELIVERABLE = (
    "__pycache__",
    "node_modules",
)

#: Characters NTFS will not take in a name, replaced so a deliverable produced
#: on Linux can still be downloaded on Windows. ``\`` is on that list for the
#: same reason the rest are, and was the one member missing: a file named
#: ``q1\q2.md`` is one legal name here and a name ``_save_files`` refuses.
_NTFS_FORBIDDEN = re.compile(r'[\\:"<>|*?\r\n]')


def _unused_deliverable_name(name: str, taken: set[str]) -> str:
    """``name``, or the first free variation of it.

    Replacing forbidden characters can map two distinct files onto one name --
    ``q1?.md`` and ``q1_.md`` both become ``q1_.md``. ``_save_files`` refuses a
    repeat, and refusing costs the task every other file with it. Neither of
    the two is litter, so neither is dropped; the second is numbered, the way
    anything else that receives a name it already has does it.

    Returns ``name`` unchanged if nothing is free, leaving the saver to refuse
    it. That is the honest outcome for a hundred colliding names: better a
    refusal that says which file than a silent hundred-and-first guess.
    """
    if name not in taken:
        return name
    parent, separator, base = name.rpartition("/")
    stem, dot, extension = base.rpartition(".")
    # `rpartition` puts everything in the third value when there is no dot, and
    # the split is done on the base so `v1.0/README` is not read as an
    # extension of `v1`.
    head, tail = (stem, dot + extension) if dot else (base, "")
    for ordinal in range(2, 100):
        candidate = f"{parent}{separator}{head} ({ordinal}){tail}"
        if candidate not in taken:
            return candidate
    return name

#: How long the auth-command preflight waits. Generous next to the runtime's
#: own 30s auth timeout, because a first sign-in can be slower than a cached
#: one and a preflight that times out early would report the wrong fault.
_AUTH_PREFLIGHT_TIMEOUT = 60

#: A GUID is a tenant or subscription identifier. Not a secret, but not ours to
#: scatter through logs either, so the preflight's reason drops them.
_GUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

#: Belt and braces. ``core.codex_azure_token`` promises never to put a token in
#: its diagnostics, and the preflight never reads one from stdout — but the
#: reason string is the one thing here that gets written down, so anything
#: shaped like a JSON Web Token is removed from it before it can be.
_JWT_SHAPED = re.compile(r"\beyJ[A-Za-z0-9_\-\.]{10,}")


def _auth_failure_reason(stderr: str) -> str:
    """One short line saying why the auth command produced no token."""
    lines = [line.strip() for line in (stderr or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return "the auth command failed without saying why"
    # The command's own message is the one written for this situation; the
    # SDK's chained credential report above it is long and mostly about
    # credentials that were never going to work here.
    chosen = next(
        (line for line in reversed(lines) if line.startswith("codex-azure-token:")),
        lines[-1],
    )
    chosen = _JWT_SHAPED.sub("<redacted>", _GUID.sub("<guid>", chosen))
    return chosen[:300]


class CodexRunError(RuntimeError):
    """A Codex run could not start or could not be trusted to have run."""


class CodexAuthCommandFailed(CodexRunError):
    """The provider's auth command could not produce a token where Codex runs it.

    Its own category, because the alternative is what this project actually
    lived through. Codex reads the token from the command's stdout; when the
    command fails it prints nothing, Codex forwards an empty bearer, and the
    gateway answers ``401 Access denied due to invalid subscription key or
    wrong API endpoint``. Every noun in that sentence points somewhere the
    fault is not, and several paid runs went looking there. Raising here, with
    the command's own reason attached, keeps a local sign-in problem local.
    """


#: What the auth-command preflight reports. Deliberately holds no token and no
#: token-derived value — only whether stdout carried one, and why not.
@dataclass(frozen=True)
class AuthCommandProbe:
    """Whether the auth command can mint where Codex will run it."""

    ran: bool
    exit_code: int | None
    produced_a_token: bool
    reason: str | None
    azure_config_dir: str | None

    @property
    def ok(self) -> bool:
        return self.ran and self.exit_code == 0 and self.produced_a_token

    def as_record(self) -> dict[str, Any]:
        return {
            "ran": self.ran,
            "exit_code": self.exit_code,
            "produced_a_token": self.produced_a_token,
            "reason": self.reason,
            "azure_config_dir": self.azure_config_dir,
            "ok": self.ok,
        }


# ── Orphan sweep ────────────────────────────────────────────────────────────
#
# ``CodexClient.close`` signals the app-server it started and nothing else. The
# agent, though, spawns commands of its own, and those are grandchildren of
# this process. If the app-server goes away without reaping them they keep
# running — holding the task's directory open, and in a batch run accumulating
# across tasks.
#
# So the boundary is drawn here instead: take the set of this process's
# descendants before the runtime starts, take it again after the runtime is
# closed, and stop whatever is new. Working from a before-and-after difference
# rather than from "everything under us" keeps a batch runner's other children
# out of range.


def _descendant_pids(root_pid: int) -> set[int]:
    """Every live descendant of ``root_pid``, read from ``/proc``.

    Returns an empty set where ``/proc`` is not available, which makes the
    sweep a no-op rather than an error on platforms that do not have it. A
    sweep that cannot see is reported as having found nothing, and
    :class:`CodexWorkspace` records that difference rather than claiming a
    clean result it did not observe.
    """
    proc = Path("/proc")
    if not proc.is_dir():
        return set()
    children: dict[int, list[int]] = {}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        parent = None
        for line in status.splitlines():
            if line.startswith("PPid:"):
                try:
                    parent = int(line.split(":", 1)[1].strip())
                except ValueError:
                    parent = None
                break
        if parent is None:
            continue
        children.setdefault(parent, []).append(int(entry.name))

    found: set[int] = set()
    frontier = [root_pid]
    while frontier:
        current = frontier.pop()
        for child in children.get(current, ()):
            if child in found:
                continue
            found.add(child)
            frontier.append(child)
    return found


def sweep_orphans(before: set[int], root_pid: int | None = None) -> tuple[int, ...]:
    """Stop descendants that appeared since ``before``; return what was stopped.

    ``SIGTERM`` first, then ``SIGKILL`` for anything still alive, because a
    command holding a half-written file should get its chance to finish the
    write. Processes that disappear between the two are the normal case and are
    not an error.
    """
    import signal
    import time

    root = os.getpid() if root_pid is None else root_pid
    survivors = sorted(_descendant_pids(root) - before)
    if not survivors:
        return ()

    for pid in survivors:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            continue
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        still = [pid for pid in survivors if pid in _descendant_pids(root)]
        if not still:
            return tuple(survivors)
        time.sleep(0.1)
    for pid in survivors:
        if pid not in _descendant_pids(root):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            continue
    return tuple(survivors)


# ── Per-task workspace ──────────────────────────────────────────────────────


@dataclass
class CodexWorkspace:
    """One task's directories: where it works, and where its runtime lives.

    Four separate roots, because they answer to different owners:

    ``workspace``  what Codex may write in, and where deliverables are looked
                   for afterwards.
    ``codex_home`` ``CODEX_HOME`` — the runtime's config, sign-in state and
                   session files. Inside the task, so a run cannot read or
                   write the operator's own.
    ``home``       ``HOME`` and the XDG roots, so a tool that writes "to the
                   home directory" writes here.
    ``root``       the private parent that holds all three and is removed with
                   the task.

    ``root`` is deliberately **not** under ``/tmp``. Codex will not create its
    ``codex-linux-sandbox`` helper when ``CODEX_HOME`` is inside the temporary
    directory, and an agent that cannot reach that helper cannot execute
    anything — see the long note in ``core/codex_runtime_config.py``. It is
    still one directory per task, made with the same 0o700 permissions and
    removed by :meth:`cleanup`; only the parent moved.
    """

    root: Path
    workspace: Path
    codex_home: Path
    home: Path
    staged_reference_names: tuple[str, ...] = ()

    @classmethod
    def create(cls, *, task_id: str) -> "CodexWorkspace":
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", task_id)[:48] or "task"
        base = resolve_run_root_base()
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix=f"gdpval-codex-{safe}-", dir=base))
        workspace = root / "workspace"
        codex_home = root / "codex_home"
        home = root / "home"
        for directory in (workspace, codex_home, home):
            directory.mkdir(parents=True, exist_ok=False)
        return cls(
            root=root, workspace=workspace, codex_home=codex_home, home=home
        )

    def stage_references(self, reference_files: Sequence[str] | None) -> None:
        """Copy the task's reference files in, verified, read-only.

        Uses the repository's own ``copy_verified_reference``, so the copy is
        checked against the source's digest and left at mode 0o400 exactly as
        it is for every other run place. Two tasks never share a directory, so
        one task's references cannot appear in another's — the isolation is the
        directory, not a filter.
        """
        if not reference_files:
            return
        names: list[str] = []
        for source in reference_files:
            copied = copy_verified_reference(source, self.workspace)
            names.append(Path(str(copied)).name)
        self.staged_reference_names = tuple(names)

    def collect_deliverables(self) -> list[dict[str, Any]]:
        """Everything in the workspace that is not an input or runtime litter.

        Walks subdirectories, because an agent given a directory frequently
        makes one. The staged references are excluded by name: they came from
        the task, and returning them as output would credit the run with
        producing its own inputs.

        Every name returned is one ``_save_files`` will accept. That is not a
        courtesy. The saver refuses a batch, not a file, so one unsaveable
        name discards the whole task -- and on run 34485072751 one did, to a
        task the model had already answered.
        """
        skip = set(self.staged_reference_names)
        collected: list[dict[str, Any]] = []
        taken: set[str] = set()
        for path in sorted(self.workspace.rglob("*")):
            if path.is_dir():
                continue
            try:
                relative = path.relative_to(self.workspace)
            except ValueError:  # pragma: no cover - rglob stays inside
                continue
            if any(part in _NOT_A_DELIVERABLE for part in relative.parts):
                continue
            if any(part.startswith(".") for part in relative.parts):
                # Not a deliverable, and not saveable either: `_save_files`
                # refuses any hidden component. An agent building something in
                # a directory writes `.gitignore` and friends without being
                # asked, and before this they took the answer down with them.
                continue
            if relative.as_posix() in skip or relative.name in skip:
                continue
            if path.suffix == ".pyc":
                continue
            if path.is_symlink():
                # A link can point outside the task. The bytes it names were
                # not produced here, so it is not collected as a deliverable.
                continue
            try:
                content = path.read_bytes()
            except OSError:
                continue
            filename = _unused_deliverable_name(
                _NTFS_FORBIDDEN.sub("_", relative.as_posix()), taken
            )
            taken.add(filename)
            collected.append({"filename": filename, "content": content})
        return collected

    def cleanup(self) -> None:
        """Remove the task's directories, including the read-only copies."""

        def _force(func, path, _exc):  # pragma: no cover - platform dependent
            try:
                os.chmod(path, 0o700)
            except OSError:
                return
            func(path)

        shutil.rmtree(self.root, onerror=_force)


# ── The runner ──────────────────────────────────────────────────────────────


def _turn_failure_category(
    failure: Any, *, http_status_code: int | None = None
) -> str:
    """Why a turn failed, when the failure says so.

    ``turn_failed`` is true of every failed turn and useful about none of
    them. On run ``34485072751`` three of the five tasks ended with

        stream disconnected before completion: Your requests to <deployment>
        ... have exceeded rate limit.

    and were recorded under the same word as a turn that failed for any other
    reason -- so the run could not say, from its own record, that it had been
    refused for rate rather than defeated by the task.

    The status code, when the SDK reports one, is asked first. It is the
    provider's own answer rather than our reading of an English sentence, and
    it does not depend on the wording surviving a version of the runtime or a
    change of region. Reading a bare ``429`` out of prose is the mistake
    :mod:`core.execution_errors` is careful not to make -- a traceback names
    lines -- but a status code *field* holding 429 means exactly one thing.

    :func:`classify_execution_error` already keeps that vocabulary for the
    rest. Its fallback, ``execution_error``, says less than ``turn_failed``
    does, so the fallback is not taken; only an answer more specific than
    "the turn failed" replaces it.
    """
    if http_status_code == 429:
        return "rate_limited"
    category = classify_execution_error(str(failure))
    if not category or category == "execution_error":
        return "turn_failed"
    return category


#: Notification methods the turn stream is read for. Matched as strings
#: because this module does not import the SDK -- see :func:`read_breakdown`.
_NOTIFY_TOKEN_USAGE = "thread/tokenUsage/updated"
_NOTIFY_ITEM_COMPLETED = "item/completed"
_NOTIFY_TURN_COMPLETED = "turn/completed"

#: Fields of a ``CodexErrorInfo`` variant that carry an HTTP status. Named
#: rather than derived, because this module does not import the SDK at module
#: scope; ``test_every_status_carrying_variant_is_named`` asks the SDK whether
#: this list is still complete, so a variant added by a version bump is a
#: failing test rather than a status silently going unread.
_ERROR_INFO_WITH_STATUS = (
    "http_connection_failed",
    "response_stream_disconnected",
    "response_stream_connection_failed",
    "response_too_many_failed_attempts",
)


def _http_status_from_turn_error(error: Any) -> int | None:
    """The status code a ``TurnError`` reports, if it reports one.

    ``TurnError.codex_error_info`` is a tagged union whose relevant variants
    each hold a single object with an ``http_status_code``. Reached by
    attribute, so a variant we have not seen simply yields ``None`` instead of
    raising.
    """
    info = getattr(error, "codex_error_info", None)
    if info is None:
        return None
    root = getattr(info, "root", info)
    for name in _ERROR_INFO_WITH_STATUS:
        detail = getattr(root, name, None)
        if detail is None:
            continue
        code = getattr(detail, "http_status_code", None)
        if isinstance(code, int):
            return code
    return None


@dataclass
class TurnObservation:
    """What the turn's own event stream said, whether or not it completed.

    ``TurnHandle.run`` collects the running token usage, the thread items and
    the completed turn, and *then* raises if the turn failed -- so everything
    it had collected leaves with the exception. That is why seven of the nine
    ledger rows on run ``34500590783`` carry no token count: those turns were
    refused part-way through, after the stream had been reporting a running
    total for a minute, and the total went out with the error.

    Reading the same stream on the way past keeps it. A refused turn can then
    settle for what it is measured to have spent instead of staying an open
    reservation that says only "a cost may exist here".
    """

    result: Any = None
    timed_out: bool = False
    failure: str | None = None
    usage: Any = None
    items_seen: int = 0
    turn: Any = None

    @property
    def http_status_code(self) -> int | None:
        return _http_status_from_turn_error(getattr(self.turn, "error", None))


def _recording_stream(events: Any, observed: TurnObservation) -> Any:
    """Yield ``events`` unchanged, remembering the three that matter."""
    for event in events:
        method = getattr(event, "method", "") or ""
        payload = getattr(event, "payload", None)
        if method == _NOTIFY_TOKEN_USAGE:
            usage = getattr(payload, "token_usage", None)
            if usage is not None:
                observed.usage = usage
        elif method == _NOTIFY_ITEM_COMPLETED:
            observed.items_seen += 1
        elif method == _NOTIFY_TURN_COMPLETED:
            observed.turn = getattr(payload, "turn", None)
        yield event


def _load_turn_collector() -> Any:
    """The SDK's own stream-to-result collector, or ``None``.

    Borrowed rather than reimplemented: it decides which agent message is the
    final answer, and that answer is the deliverable text step 4 fills into
    the parquet. A local copy of that rule is a way to lose a deliverable to a
    detail of message phases. The runtime is pinned to an exact version, so a
    symbol moving is a pin failure rather than a silent one; ``None`` here
    falls back to ``TurnHandle.run`` and to observing nothing, which is what
    this runner did before.
    """
    try:  # pragma: no cover - exercised only where the SDK is installed
        from openai_codex._run import _collect_turn_result
    except Exception:  # noqa: BLE001
        return None
    return _collect_turn_result


@dataclass
class CodexRunOutcome:
    """What one turn produced, before it is flattened to the runner's dict."""

    success: bool
    text: str
    files: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    error_category: str | None = None
    usage_delta: CodexTokenTotals = field(default_factory=CodexTokenTotals)
    items_seen: int = 0
    http_status_code: int | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    swept_pids: tuple[int, ...] = ()


class CodexAgentRunner(RecordsItsFirstRequest):
    """Runs one GDPVal task per Codex session against a Foundry deployment."""

    #: Codex opens its own requests inside a turn and does not report how many.
    #: ``True`` describes the boundary we do control — a new session, and one
    #: turn, per task — and the count inside it is exactly what the cost
    #: adapter marks ``call_reachability_unknown``.
    SENDS_A_FRESH_REQUEST_PER_TURN = True

    #: What we put in front of the agent about its reference files: the
    #: directory listing and the names. Not previews — the agent reads the
    #: files itself with its own tools, which is the reason to use it at all.
    #: Claiming a preview section we do not build would misreport the
    #: comparison's one-first-request check.
    REFERENCE_FILE_PROMPT_SECTIONS = ("file_structure", "available_files")

    FIRST_REQUEST_EXTRA_SECTIONS: tuple[str, ...] = ()

    OBSERVED_RUN_PLACE = ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY

    #: Codex speaks the Responses contract to its provider — that is what
    #: ``wire_api = "responses"`` in the provider table selects, and the only
    #: family ``core.codex_runtime_config.SUPPORTED_WIRE_API`` allows. Recorded
    #: rather than left at the inherited chat-completions default, because the
    #: comparison tells the two families apart and a wrong label here would
    #: hide a run place having changed products.
    OBSERVED_API_FAMILY = API_FAMILY_RESPONSES

    def __init__(
        self,
        provider: CodexProviderLike,
        *,
        timeout: int | None = None,
        cost_ledger: Any | None = None,
        run_id: str | None = None,
        condition_name: str | None = None,
        codex_bin: str | None = None,
        verify_runtime: bool = True,
        preflight_auth: bool = True,
    ) -> None:
        """
        Args:
            provider: which deployment to call and how to describe it. Either
                a :class:`~core.codex_runtime_config.CodexProviderSettings`
                naming a real Foundry deployment, or a
                :class:`~core.codex_runtime_config.LoopbackCodexProvider`,
                which can only name a server on this machine and is how the
                end-to-end check runs the real runtime without paying for it.
            timeout: wall-clock seconds for one turn.
            cost_ledger: a ``CostReceiptLedger``. Optional, because a
                structure check has no ledger; when absent no cost is recorded
                and nothing is invented to stand in for it.
            codex_bin: path to the Codex binary. Left ``None``, the SDK finds
                the one the pinned distribution installed, which is what any
                real run uses.
            verify_runtime: check the pinned versions on construction.
            preflight_auth: run the provider's auth command once, in the
                isolated environment, before starting a runtime, and refuse to
                start when it produces no token. Off only for the connection
                diagnostic, which sometimes needs the failing request itself.
        """
        if not isinstance(provider, CodexProviderLike):
            raise CodexProviderConfigurationError(
                "the Codex run place needs a provider description; refusing "
                "to guess an endpoint or a deployment"
            )
        self.provider = provider
        self.timeout = int(timeout) if timeout else CODEX_TURN_TIMEOUT
        self.cost_ledger = cost_ledger
        self.run_id = run_id
        self.condition_name = condition_name
        self.codex_bin = codex_bin
        self.preflight_auth = bool(preflight_auth)
        self._auth_probe: AuthCommandProbe | None = None
        self.shared_first_request = False
        self.last_run_diagnostics: dict[str, Any] | None = None
        self._turns_per_task: dict[str, int] = {}

        if verify_runtime:
            # Raised, not swallowed. A missing runtime must stop the run place,
            # not quietly downgrade it to something else that does work.
            require_pinned_runtime()

    # -- SDK access ---------------------------------------------------------

    def _build_environment(self, workspace: CodexWorkspace) -> dict[str, str]:
        """The isolated environment, plus whatever the provider needs in it.

        The provider's additions are checked against the names the isolation
        blanks and the names the repository forbids outright, so this cannot
        become a route back in for a static Azure credential — which is the
        one thing the auth-command design exists to prevent.
        """
        environment = build_isolated_environment(
            codex_home=workspace.codex_home, task_home=workspace.home
        )
        extra = dict(self.provider.extra_environment())
        if extra:
            blanked = set(NEUTRALISED_ENV_NAMES) | set(
                FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV
            )
            offending = sorted(set(extra) & blanked)
            if offending:
                raise CodexProviderConfigurationError(
                    "a provider asked to set "
                    + ", ".join(offending)
                    + " in the Codex environment; those names are blanked or "
                    "forbidden here"
                )
            environment.update(extra)
        return environment

    def preflight_auth_command(
        self, workspace: CodexWorkspace
    ) -> AuthCommandProbe:
        """Run the provider's auth command where Codex will run it.

        Same argv, same isolated environment, same working directory. The point
        is not to obtain a token — the token is read, checked for emptiness and
        dropped without being stored, logged or returned — but to find out
        whether one *can* be obtained from inside the isolation, before a turn
        turns that question into a gateway error about something else.

        Providers that authenticate by environment variable have no command to
        run; for those this reports ``ran=False`` and nothing is claimed.
        """
        build = getattr(self.provider, "auth_command", None)
        if not callable(build):
            return AuthCommandProbe(
                ran=False,
                exit_code=None,
                produced_a_token=False,
                reason="this provider authenticates by environment variable",
                azure_config_dir=None,
            )
        argv = list(build())
        config_dir = None
        if "--azure-config-dir" in argv:
            config_dir = argv[argv.index("--azure-config-dir") + 1]
        # The overlay merged onto this process's environment, because that is
        # what the child actually gets: the pinned SDK does
        # ``env = os.environ.copy(); env.update(self.config.env)`` before
        # ``Popen``. Handing the overlay alone would give the auth command a
        # smaller environment than a real turn does, and a preflight that
        # tests a stricter world than production can fail on things production
        # would not — which is its own kind of wrong answer.
        environment = {**os.environ, **self._build_environment(workspace)}
        try:
            completed = subprocess.run(
                argv,
                cwd=str(workspace.workspace),
                env=environment,
                capture_output=True,
                text=True,
                timeout=_AUTH_PREFLIGHT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return AuthCommandProbe(
                ran=True,
                exit_code=None,
                produced_a_token=False,
                reason=(
                    f"the auth command did not finish within "
                    f"{_AUTH_PREFLIGHT_TIMEOUT}s"
                ),
                azure_config_dir=config_dir,
            )
        except OSError as exc:
            return AuthCommandProbe(
                ran=False,
                exit_code=None,
                produced_a_token=False,
                reason=f"the auth command could not be started ({exc.strerror})",
                azure_config_dir=config_dir,
            )
        # Truthiness only. The value is not kept, not returned and not logged;
        # what is recorded is that stdout was or was not empty.
        produced = bool(completed.stdout.strip())
        return AuthCommandProbe(
            ran=True,
            exit_code=completed.returncode,
            produced_a_token=produced,
            reason=None if produced and completed.returncode == 0
            else _auth_failure_reason(completed.stderr),
            azure_config_dir=config_dir,
        )

    def require_a_usable_auth_command(
        self, workspace: CodexWorkspace
    ) -> AuthCommandProbe:
        """Check the sign-in once per runner, and refuse to start without it.

        Cached on the runner rather than repeated per task: the answer is a
        property of the environment, not of the task, and a batch of 220 would
        otherwise pay for 220 sign-ins to learn the same thing.

        A provider with no auth command, or a runner built with
        ``preflight_auth=False``, passes through untouched — the first because
        there is nothing to check, the second because the connection diagnostic
        sometimes needs to send the request that fails and see what comes back.
        """
        if not self.preflight_auth:
            return AuthCommandProbe(
                ran=False,
                exit_code=None,
                produced_a_token=False,
                reason="the auth-command preflight was turned off for this run",
                azure_config_dir=None,
            )
        if self._auth_probe is None:
            self._auth_probe = self.preflight_auth_command(workspace)
        probe = self._auth_probe
        if probe.ran and not probe.ok:
            where = (
                f" (sign-in read from {probe.azure_config_dir})"
                if probe.azure_config_dir
                else " (this machine has no Azure CLI sign-in to point at)"
            )
            raise CodexAuthCommandFailed(
                "the provider's auth command produced no token inside the "
                f"isolated environment{where}: {probe.reason}. Codex would "
                "send an empty bearer and the gateway would answer 401 about "
                "an invalid subscription key, which would be about the wrong "
                "thing."
            )
        return probe

    def open_runtime(self, workspace: CodexWorkspace) -> Any:
        """Start the Codex client a run uses, against this provider.

        Public, and paired with :meth:`start_thread`, because the connection
        diagnostic drives the runtime for a different purpose — it consumes the
        turn stream itself, to keep the structured error the SDK's own
        collector discards — and a second construction that merely *resembled*
        this one would let the two drift. The one that would then be wrong is
        the diagnostic, whose entire value is being about the configuration a
        real run uses.

        The two steps stay separate rather than becoming one ``open_session``
        because their failures are different findings: a runtime that will not
        start and a session that will not open are reported under different
        categories, and merging them would lose that distinction at the only
        moment it matters.

        Before either, the auth command is run once per runner in the same
        isolated environment. A runtime that starts with a sign-in that cannot
        mint will reach the deployment and be refused there, and the refusal
        will describe the endpoint rather than the sign-in.
        """
        self.require_a_usable_auth_command(workspace)
        environment = self._build_environment(workspace)
        overrides = self.provider.config_overrides()
        try:
            from openai_codex import Codex
            from openai_codex.client import CodexConfig
        except ImportError as exc:
            raise CodexRuntimeUnavailable(
                f"the pinned Codex SDK could not be imported ({exc})"
            ) from None
        config = CodexConfig(
            codex_bin=self.codex_bin,
            config_overrides=tuple(overrides),
            env=environment,
            cwd=str(workspace.workspace),
        )
        return Codex(config)

    def start_thread(
        self,
        codex: Any,
        workspace: CodexWorkspace,
        *,
        developer_instructions: str | None = None,
    ) -> Any:
        """Open one thread on ``codex``, with the settings a run opens it with.

        The sandbox preset and the approval mode are read from this object's
        own methods rather than passed in, so there is no argument by which a
        caller can ask for a weaker isolation than a run gets.
        """
        return codex.thread_start(
            model=self.provider.model,
            model_provider=self.provider.provider_id,
            cwd=str(workspace.workspace),
            sandbox=self._sandbox_preset(),
            approval_mode=self._approval_mode(),
            developer_instructions=developer_instructions,
        )

    def _sandbox_preset(self) -> Any:
        """The filesystem policy for the agent: write inside its workspace.

        Read-only would stop it producing a deliverable at all; full access
        would let it out of the task directory, which is the isolation this run
        place is built on. There is no argument that turns this off, including
        for the mock check — a check that ran the agent unsandboxed would be
        checking a configuration nothing else uses.
        """
        from openai_codex import Sandbox

        return Sandbox.workspace_write

    def _approval_mode(self) -> Any:
        """Never stop to ask. A batch run has nobody to answer."""
        from openai_codex import ApprovalMode

        return ApprovalMode.deny_all

    # -- prompt -------------------------------------------------------------

    def build_task_text(
        self,
        task_prompt: str,
        workspace: CodexWorkspace,
        *,
        occupation: str = "professional",
        perception_text: str | None = None,
    ) -> str:
        """The one message the agent gets, plus what is on disk beside it."""
        parts = [
            f"You are working as a {occupation}.",
            "",
            task_prompt.strip(),
        ]
        if perception_text:
            parts.extend(["", perception_text.strip()])
        parts.extend(
            [
                "",
                "Working directory: this is your workspace. Write every "
                "deliverable here as a real file. Anything you leave outside "
                "it will not be collected.",
            ]
        )
        if workspace.staged_reference_names:
            listing = "\n".join(
                f"- {name}" for name in workspace.staged_reference_names
            )
            parts.extend(
                [
                    "",
                    "Reference files already in the working directory "
                    "(read-only):",
                    listing,
                ]
            )
        else:
            parts.extend(["", "This task has no reference files."])
        return "\n".join(parts)

    # -- run ----------------------------------------------------------------

    def run(
        self,
        task_prompt: str,
        model: str | None = None,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
        perception_text: Optional[str] = None,
        run_id: Optional[str] = None,
        condition_name: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict:
        """Run one task in a fresh Codex session and return the standard dict.

        ``model`` is accepted for signature compatibility with the other run
        places, but it must match the deployment the provider was configured
        with. Letting a caller name a different deployment here would let an
        experiment's recorded model and the model actually called drift apart
        without anything noticing.
        """
        requested = (model or self.provider.model).strip()
        if requested != self.provider.model:
            return self._failure(
                f"this Codex run place is configured for deployment "
                f"{self.provider.model!r} and was asked for {requested!r}; "
                "refusing rather than calling a different model than the one "
                "the run will be recorded against",
                category="model_mismatch",
            )

        workspace: CodexWorkspace | None = None
        try:
            workspace = CodexWorkspace.create(task_id=task_id or "task")
        except OSError as exc:
            return self._failure(
                f"could not create the task workspace: {exc}",
                category="workspace_error",
            )

        try:
            try:
                workspace.stage_references(reference_files)
            except (ReferenceIntegrityError, OSError) as exc:
                return self._failure(
                    f"could not stage the task's reference files: {exc}",
                    category="reference_error",
                )

            outcome = self._run_one_turn(
                workspace=workspace,
                task_text=self.build_task_text(
                    task_prompt,
                    workspace,
                    occupation=occupation,
                    perception_text=perception_text,
                ),
                experiment_prompt=experiment_prompt,
                task_id=task_id,
            )
        finally:
            if workspace is not None:
                try:
                    workspace.cleanup()
                except OSError:
                    pass

        self.last_run_diagnostics = {
            "thread_id": outcome.thread_id,
            "turn_id": outcome.turn_id,
            "swept_orphan_pids": list(outcome.swept_pids),
            # How far into the turn it got, and what the provider answered
            # with. A turn refused after forty items is a different fact from
            # one refused after two, and only the first is evidence that the
            # limit is reached by what one turn spends rather than by how fast
            # turns arrive.
            "items_seen": outcome.items_seen,
            "http_status_code": outcome.http_status_code,
            "usage_delta": {
                "input_tokens": outcome.usage_delta.input_tokens,
                "cached_input_tokens": outcome.usage_delta.cached_input_tokens,
                "cache_write_input_tokens": (
                    outcome.usage_delta.cache_write_input_tokens
                ),
                "output_tokens": outcome.usage_delta.output_tokens,
                "reasoning_output_tokens": (
                    outcome.usage_delta.reasoning_output_tokens
                ),
            },
        }
        result: dict[str, Any] = {
            "success": outcome.success,
            "text": outcome.text,
            "files": outcome.files,
        }
        if outcome.error:
            result["error"] = outcome.error
        if outcome.error_category:
            result["error_category"] = outcome.error_category
        return result

    def _run_one_turn(
        self,
        *,
        workspace: CodexWorkspace,
        task_text: str,
        experiment_prompt: Optional[dict],
        task_id: Optional[str],
    ) -> CodexRunOutcome:
        before_pids = _descendant_pids(os.getpid())
        call_id: str | None = None
        codex: Any = None
        try:
            try:
                codex = self.open_runtime(workspace)
            except (CodexRuntimeUnavailable, CodexProviderConfigurationError) as exc:
                return CodexRunOutcome(
                    success=False,
                    text="",
                    error=str(exc),
                    error_category="runtime_unavailable",
                )
            except Exception as exc:  # noqa: BLE001
                return CodexRunOutcome(
                    success=False,
                    text="",
                    error=f"the Codex runtime would not start: {exc}",
                    error_category="runtime_start_failed",
                )

            developer_instructions = None
            if isinstance(experiment_prompt, dict):
                system = experiment_prompt.get("system")
                if isinstance(system, str) and system.strip():
                    developer_instructions = system.strip()

            try:
                thread = self.start_thread(
                    codex,
                    workspace,
                    developer_instructions=developer_instructions,
                )
            except Exception as exc:  # noqa: BLE001
                return CodexRunOutcome(
                    success=False,
                    text="",
                    error=f"the Codex session would not open: {exc}",
                    error_category="session_start_failed",
                )

            before_totals = CodexTokenTotals.zero()
            call_id = self._reserve_call(task_id)

            try:
                turn_handle = thread.turn(task_text)
            except Exception as exc:  # noqa: BLE001
                # The turn never started, so nothing was sent and nothing was
                # billed. This is one of the few places `abandon` is right.
                self._abandon_call(call_id, "the turn never started")
                call_id = None
                return CodexRunOutcome(
                    success=False,
                    text="",
                    error=f"the Codex turn would not start: {exc}",
                    error_category="turn_start_failed",
                    thread_id=getattr(thread, "id", None),
                )

            observed = self._await_turn(turn_handle)
            result, timed_out, failure = (
                observed.result, observed.timed_out, observed.failure
            )

            def _settle_what_was_measured() -> CodexTokenTotals:
                """Bill the ended turn for the tokens the stream reported.

                A turn that was refused or interrupted part-way still sent
                requests and still ran up a total, and the stream had been
                saying so all along. Settling for that figure is not a claim
                that it is the whole bill -- the reservation was opened with
                ``call_reachability_unknown``, so the receipt stays ``partial``
                either way. It is the difference between a receipt that says
                "a cost may exist here" and one that says "at least this much
                was spent, and there may be more".

                When the stream reported nothing, the reservation is left
                open, which is the older and still-correct answer.
                """
                nonlocal call_id
                measured = turn_usage_delta(
                    before_totals, read_thread_totals(observed.usage)
                )
                if measured.is_empty:
                    return measured
                self._settle_call(call_id, measured)
                call_id = None
                return measured

            if timed_out:
                # The turn was sent and the model may well have answered, so
                # the reservation is never abandoned. What the stream managed
                # to report before the interrupt is settled; what it did not
                # stays an open reservation.
                measured = _settle_what_was_measured()
                files = workspace.collect_deliverables()
                return CodexRunOutcome(
                    success=False,
                    text="",
                    files=files,
                    error=(
                        f"the Codex turn exceeded {self.timeout} seconds and "
                        "was interrupted"
                    ),
                    error_category="timeout",
                    usage_delta=measured,
                    items_seen=observed.items_seen,
                    thread_id=getattr(thread, "id", None),
                    turn_id=getattr(turn_handle, "id", None),
                )

            if failure is not None:
                status_code = observed.http_status_code
                measured = _settle_what_was_measured()
                files = workspace.collect_deliverables()
                return CodexRunOutcome(
                    success=False,
                    text="",
                    files=files,
                    error=f"the Codex turn failed: {failure}",
                    error_category=_turn_failure_category(
                        failure, http_status_code=status_code
                    ),
                    usage_delta=measured,
                    items_seen=observed.items_seen,
                    http_status_code=status_code,
                    thread_id=getattr(thread, "id", None),
                    turn_id=getattr(turn_handle, "id", None),
                )

            after_totals = read_thread_totals(getattr(result, "usage", None))
            delta = turn_usage_delta(before_totals, after_totals)
            self._settle_call(call_id, delta)
            call_id = None

            files = workspace.collect_deliverables()
            text = getattr(result, "final_response", None) or ""
            return CodexRunOutcome(
                success=True,
                text=text,
                files=files,
                usage_delta=delta,
                items_seen=observed.items_seen,
                thread_id=getattr(thread, "id", None),
                turn_id=getattr(result, "id", None),
            )
        finally:
            if codex is not None:
                try:
                    codex.close()
                except Exception:  # noqa: BLE001 - closing must not mask a result
                    pass
            swept = sweep_orphans(before_pids)
            if swept:
                self.last_swept_pids = swept

    def _await_turn(self, turn_handle: Any) -> TurnObservation:
        """Consume a turn under a wall clock; interrupt it if it overruns.

        The SDK exposes no timeout of its own -- ``Thread.run`` blocks until the
        turn completes -- so the limit is enforced here, by consuming the turn on
        a worker thread and asking Codex to interrupt when the clock runs out.
        Interrupting first, rather than killing the process, gives the agent the
        chance to finish writing whatever file it had open.

        The stream is read on the way past rather than only at the end, so a
        turn that is refused or interrupted still reports what it had spent.
        The observation is written by the worker and read by this thread after
        it stops; on the timeout path the worker may still be running, and the
        reading is then a moment stale rather than torn -- every field is a
        single assignment or a count only that thread increments.
        """
        observed = TurnObservation()
        collector = _load_turn_collector()

        def _consume() -> None:
            try:
                if collector is None:
                    observed.result = turn_handle.run()
                    return
                stream = turn_handle.stream()
                try:
                    observed.result = collector(
                        _recording_stream(stream, observed),
                        turn_id=turn_handle.id,
                    )
                finally:
                    stream.close()
            except BaseException as exc:  # noqa: BLE001
                observed.failure = str(exc)

        worker = threading.Thread(
            target=_consume, name="codex-turn", daemon=True
        )
        worker.start()
        worker.join(self.timeout)

        if worker.is_alive():
            try:
                turn_handle.interrupt()
            except Exception:  # noqa: BLE001
                pass
            worker.join(CODEX_INTERRUPT_GRACE_SECONDS)
            observed.result = None
            observed.failure = None
            observed.timed_out = True
        return observed

    # -- cost ---------------------------------------------------------------

    def _reserve_call(self, task_id: str | None) -> str | None:
        """Open a receipt for the turn we are about to send.

        One receipt per turn, not per model request. Codex opens however many
        requests it needs inside a turn and reports only a running thread
        total, so a per-request receipt would be a row we invented. What the
        ledger gets instead is one row for the boundary we do control, carrying
        ``call_reachability_unknown`` — the repository's existing word for
        "this covers calls we could not enumerate".

        The identifier is built the same way ``core.cost_metering`` builds its
        own, so a Codex row merges with the rest of a run's rows instead of
        sitting under a naming scheme of its own. ``attempt_index`` counts this
        runner's turns per task: re-running a task must open a second receipt,
        not settle a second result onto the first one's row.

        ``retry_kind`` comes from whatever attribution scope the caller has
        open. It used to be ``RETRY_NONE``, written here as a literal, which
        meant the infrastructure retries added in #502 reached the ledger
        labelled as first attempts: all nine rows of run ``34500590783`` say
        ``none`` although four of them were retries. The scope is entered on
        this thread, immediately around the call, so reading it here is
        reading the caller's own answer rather than guessing at one.
        """
        if self.cost_ledger is None:
            return None
        task = task_id or "unknown-task"
        attempt = self._turns_per_task.get(task, 0)
        self._turns_per_task[task] = attempt + 1
        attribution = CostRecorder.current()
        retry_kind = (
            attribution.retry_kind if attribution is not None else RETRY_NONE
        )
        call_id = make_call_id(
            run_id=self.run_id or getattr(self.cost_ledger, "run_id", "codex"),
            task_id=task,
            stage=STAGE_GENERATION,
            retry_kind=retry_kind,
            attempt_index=attempt,
            sequence=0,
        )
        self.cost_ledger.reserve(
            call_id=call_id,
            task_id=task,
            stage=STAGE_GENERATION,
            retry_kind=retry_kind,
            provider="azure",
            requested_model=self.provider.model,
            deployment=self.provider.model,
            api_version="v1",
            note="one Codex turn; the model requests inside it are not "
            "individually reported",
        )
        return call_id

    def _settle_call(self, call_id: str | None, delta: CodexTokenTotals) -> None:
        if self.cost_ledger is None or call_id is None:
            return
        settle_codex_turn(
            self.cost_ledger,
            call_id,
            totals=delta,
            resolved_model=self.provider.model,
        )

    def _abandon_call(self, call_id: str | None, note: str) -> None:
        if self.cost_ledger is None or call_id is None:
            return
        try:
            self.cost_ledger.abandon(call_id, note=note)
        except Exception:  # noqa: BLE001 - a ledger fault must not hide the run's
            pass

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _failure(message: str, *, category: str) -> dict:
        return {
            "success": False,
            "text": "",
            "files": [],
            "error": message,
            "error_category": category,
        }

    def close(self) -> None:
        """Nothing outlives a task here; each run closes its own runtime."""
        return None
