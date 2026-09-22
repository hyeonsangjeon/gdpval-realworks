"""Host-owned cumulative deadlines for the opt-in A/B/C Codex pilot.

The deadline is wall time, not model time or a monetary allowance. Its state
must accompany a restart; a missing or incompatible restore never starts a
new clock. B/C can bind a retained native session to this same host record;
A keeps fresh sessions. Neither control authorizes a paid run.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

FORMAT = "codex-task-deadline-v1"
CONTINUATION_FORMAT = "codex-native-continuation-v1"
_USAGE_FIELDS = frozenset({
    "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
    "output_tokens", "reasoning_output_tokens",
})
TOTAL_SECONDS = 180 * 60
ATTEMPT_SECONDS = 30 * 60
EXHAUSTED = "task_deadline_exhausted"
ATTEMPTS_EXHAUSTED = "task_attempt_budget_exhausted"
STATE_REFUSED = "task_deadline_state_refused"


class TaskDeadlineRefused(ValueError):
    """The host cannot establish the original cell budget safely."""


class TaskDeadlineExhausted(TimeoutError):
    """No time remains for another provider call."""


@dataclass(frozen=True)
class CodexTaskDeadlineControl:
    """The one opt-in block; timings and A/B/C attempt policy are fixed."""

    condition: str
    repetition: int

    def __post_init__(self) -> None:
        if type(self.condition) is not str or self.condition not in {"A", "B", "C"}:
            raise TaskDeadlineRefused("task_deadline requires condition A, B or C")
        if type(self.repetition) is not int or self.repetition not in {1, 2}:
            raise TaskDeadlineRefused("task_deadline requires repetition 1 or 2")

    @classmethod
    def from_mapping(cls, value: Any) -> CodexTaskDeadlineControl | None:
        if value is None:
            return None
        if type(value) is not dict or set(value) != {"condition", "repetition"}:
            raise TaskDeadlineRefused("task_deadline requires only condition and repetition")
        return cls(**value)

    @property
    def max_attempts(self) -> int | None:
        return 4 if self.condition == "A" else None

    def as_dict(self) -> dict[str, Any]:
        return {"condition": self.condition, "repetition": self.repetition}


def validate_deadline_execution(execution: dict, condition: dict) -> CodexTaskDeadlineControl | None:
    """Validate the opt-in at config load and again at the prepared consumer."""
    codex = execution.get("codex")
    if not isinstance(codex, dict):
        # Leave validation of legacy/other-mode Codex settings to their owner.
        return None
    control = CodexTaskDeadlineControl.from_mapping(
        codex.get("task_deadline")
    )
    if control is not None and (
        execution.get("mode") != "codex_foundry"
        or type(execution.get("timeout")) is not int
        or execution["timeout"] != ATTEMPT_SECONDS
        or type(execution.get("max_retries")) is not int
        or execution["max_retries"] != 3
        or (condition.get("qa") or {}).get("enabled")
        or condition.get("preprocessors")
        or execution.get("comparison_input_capture") is not None
        or execution.get("pilot_input_capture") is not None
    ):
        raise TaskDeadlineRefused("task_deadline requires its fixed Codex attempt controls, without QA/preprocessors or another pilot")
    return control


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _regular_private(path: Path) -> None:
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600):
        raise TaskDeadlineRefused("deadline state must be a private single-link regular file")


def _valid_totals(value: Any) -> bool:
    return (type(value) is dict and set(value) == _USAGE_FIELDS
            and all(item is None or (type(item) is int and item >= 0)
                    for item in value.values()))


def _validate_continuation(value: Any, attempts: list[dict]) -> None:
    """Validate host metadata, never open an agent transcript or auth store."""
    if value is None:
        return
    if (type(value) is not dict or set(value) != {
        "format", "identity_sha256", "request_sha256", "workspace", "phase", "thread_id",
        "usage_boundary", "turns", "native_resumes", "terminal_reason",
    } or value["format"] != CONTINUATION_FORMAT
            or type(value["identity_sha256"]) is not str
            or len(value["identity_sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in value["identity_sha256"])
            or type(value["request_sha256"]) is not str or len(value["request_sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in value["request_sha256"])
            or type(value["workspace"]) is not dict
            or value["phase"] not in {"pre_thread", "starting", "bound"}
            or not _valid_totals(value["usage_boundary"])
            or type(value["turns"]) is not list
            or type(value["native_resumes"]) is not int or value["native_resumes"] < 0
            or value["terminal_reason"] not in {None, "completed", "content_filter"}):
        raise TaskDeadlineRefused("native continuation binding is invalid")
    if not attempts or any(attempt["workspace_root"] != value["workspace"].get("root")
                           for attempt in attempts):
        raise TaskDeadlineRefused("native continuation workspace differs from its admissions")
    if value["phase"] == "bound":
        if type(value["thread_id"]) is not str or not value["thread_id"].strip():
            raise TaskDeadlineRefused("bound native thread identifier is missing")
    elif (value["thread_id"] is not None or value["turns"]
          or value["native_resumes"] or value["terminal_reason"] is not None):
        raise TaskDeadlineRefused("pre-thread continuation has bound activity")
    prior = -1
    for turn in value["turns"]:
        if (type(turn) is not dict or set(turn) != {
            "attempt_index", "call_id", "before", "after", "phase",
        } or type(turn["attempt_index"]) is not int
                or not prior < turn["attempt_index"] < len(attempts)
                or (turn["call_id"] is not None
                    and (type(turn["call_id"]) is not str or not turn["call_id"]))
                or not _valid_totals(turn["before"])
                or turn["phase"] not in {"in_flight", "observed", "settled", "unmetered"}
                or (turn["after"] is None) != (turn["phase"] == "in_flight")
                or (turn["after"] is not None and not _valid_totals(turn["after"]))
                or (turn["phase"] == "settled" and turn["call_id"] is None)
                or (turn["phase"] == "unmetered" and turn["call_id"] is not None)):
            raise TaskDeadlineRefused("native continuation usage boundary is invalid")
        prior = turn["attempt_index"]
    if value["turns"]:
        last = value["turns"][-1]
        boundary = last["after"] or dict.fromkeys(_USAGE_FIELDS)
        if value["usage_boundary"] != boundary:
            raise TaskDeadlineRefused("native continuation usage boundary differs from its turn")


class CodexTaskDeadlineStore:
    """One locked host record for an explicitly declared run/condition/repeat.

    Atomic replacement reuses the existing private-JSON writer. The checksum
    detects damaged/edited state, not an adversarial host operator able to
    replace both state and checksum. The problem agent gets neither this path
    nor write permission to it. A process holds the lock until all tasks stop.
    """

    def __init__(
        self, root: Path, *, run_id: str, experiment_id: str,
        condition_key: str, control: CodexTaskDeadlineControl,
        task_ids: list[str], prepared_fingerprint: str,
        initialize: bool = False, clock: Callable[[], float] = time.time,
    ) -> None:
        # Config validation also runs without backend SDKs installed. Import
        # host persistence only when a real state directory is opened.
        import fcntl
        from core.codex_runtime_config import (
            path_is_within, resolve_run_root_base, system_temporary_directory,
        )
        from core.hf_publication import _assert_no_symlink_ancestors

        self._lock: int | None = None
        try:
            self.root = _assert_no_symlink_ancestors(Path(root))
        except (OSError, ValueError):
            raise TaskDeadlineRefused("unsafe deadline state root") from None
        self.control = control
        self.clock = clock
        self._closed = False
        if (type(control) is not CodexTaskDeadlineControl
                or not all(type(value) is str and value for value in (
                run_id, experiment_id, condition_key, prepared_fingerprint))
                or not task_ids or any(type(task) is not str or not task for task in task_ids)
                or len(task_ids) != len(set(task_ids))):
            raise TaskDeadlineRefused("deadline identity and ordered tasks are required")
        # Both temporary carve-outs are writable by the sandbox, independently
        # of its task workspace. A private mode alone does not isolate a process
        # running as the same uid.
        for writable in (resolve_run_root_base(), system_temporary_directory(), Path("/tmp")):
            if path_is_within(self.root, writable):
                raise TaskDeadlineRefused("deadline state is inside an agent-writable root")
        self.identity = {
            "run_id": run_id, "experiment_id": experiment_id,
            "condition_key": condition_key, **control.as_dict(),
            "ordered_task_ids": list(task_ids),
            "prepared_fingerprint": prepared_fingerprint,
            "total_seconds": TOTAL_SECONDS, "attempt_seconds": ATTEMPT_SECONDS,
            "max_attempts": control.max_attempts,
        }
        self.path = self.root / "deadlines.json"
        try:
            if initialize:
                # An existing reservation, even a partial one, is never adopted.
                self.root.mkdir(mode=0o700, parents=False, exist_ok=False)
            metadata = self.root.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
                raise TaskDeadlineRefused("deadline root must be a private directory")
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
            if initialize:
                flags |= os.O_CREAT | os.O_EXCL
            self._lock = os.open(self.root / "lock", flags, 0o600)
            _regular_private(self.root / "lock")
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if initialize:
                now = self._now()
                self._write({
                    "format": FORMAT, "identity": self.identity,
                    "last_observed_unix": now,
                    "cells": {task: {
                        "started_unix": None, "expires_unix": None,
                        "attempts": [], "wait_seconds": 0.0,
                        "continuation": None, "terminal_reason": None,
                    } for task in task_ids},
                })
            self._read()
        except (OSError, ValueError) as exc:
            self.close()
            if isinstance(exc, TaskDeadlineRefused):
                raise
            raise TaskDeadlineRefused("deadline initialization/restore refused; retain host state") from None

    def _now(self) -> float:
        now = self.clock()
        if type(now) not in {int, float} or not math.isfinite(now) or now < 0:
            raise TaskDeadlineRefused("deadline clock is invalid")
        return float(now)

    def _read(self) -> dict:
        from core.hf_publication import _load_private_json_object

        if self._closed:
            raise TaskDeadlineRefused("deadline store is closed")
        try:
            _regular_private(self.path)
            raw = _load_private_json_object(self.path, "deadline state")
            if set(raw) != {"payload", "sha256"} or _digest(raw["payload"]) != raw["sha256"]:
                raise TaskDeadlineRefused("deadline state checksum mismatch")
            data = raw["payload"]
            if (set(data) != {"format", "identity", "last_observed_unix", "cells"}
                    or data["format"] != FORMAT or data["identity"] != self.identity
                    or set(data["cells"]) != set(self.identity["ordered_task_ids"])):
                raise TaskDeadlineRefused("deadline restore identity mismatch")
            last = data["last_observed_unix"]
            if type(last) not in {int, float} or not math.isfinite(last) or self._now() < last:
                raise TaskDeadlineRefused("deadline clock moved backwards")
            for cell in data["cells"].values():
                if set(cell) != {"started_unix", "expires_unix", "attempts", "wait_seconds", "continuation", "terminal_reason"}:
                    raise TaskDeadlineRefused("deadline cell shape mismatch")
                if cell["terminal_reason"] not in {None, "content_filtered"}:
                    raise TaskDeadlineRefused("deadline terminal reason is invalid")
                start, expiry = cell["started_unix"], cell["expires_unix"]
                if start is None:
                    if expiry is not None or cell["attempts"] or cell["wait_seconds"] != 0 or cell["terminal_reason"] is not None:
                        raise TaskDeadlineRefused("unstarted deadline cell has activity")
                elif (type(start) not in {int, float} or not math.isfinite(start)
                      or start < 0 or start > last or type(expiry) not in {int, float}
                      or expiry != start + TOTAL_SECONDS):
                    raise TaskDeadlineRefused("deadline expiry is incompatible")
                if (type(cell["wait_seconds"]) not in {int, float}
                        or not 0 <= cell["wait_seconds"] <= TOTAL_SECONDS
                        or type(cell["attempts"]) is not list):
                    raise TaskDeadlineRefused("deadline accounting is invalid")
                if self.control.max_attempts is not None and len(cell["attempts"]) > self.control.max_attempts:
                    raise TaskDeadlineRefused("deadline attempt count is incompatible")
                for index, attempt in enumerate(cell["attempts"]):
                    if (type(attempt) is not dict
                            or set(attempt) != {"index", "admitted_unix", "workspace_root"}
                            or type(attempt["index"]) is not int or attempt["index"] != index
                            or type(attempt["admitted_unix"]) not in {int, float}
                            or not start <= attempt["admitted_unix"] < expiry
                            or type(attempt["workspace_root"]) is not str):
                        raise TaskDeadlineRefused("deadline attempt record is invalid")
                _validate_continuation(cell["continuation"], cell["attempts"])
                if self.control.condition == "A" and cell["continuation"] is not None:
                    raise TaskDeadlineRefused("A requires fresh native sessions")
            return data
        except (OSError, ValueError, TypeError, KeyError) as exc:
            if isinstance(exc, TaskDeadlineRefused):
                raise
            raise TaskDeadlineRefused("deadline restore state is missing or invalid") from None

    def _write(self, data: dict) -> None:
        from core.hf_publication import _write_private_json

        try:
            _write_private_json(self.path, {"payload": data, "sha256": _digest(data)})
        except (OSError, ValueError, TypeError):
            raise TaskDeadlineRefused("deadline state could not be persisted") from None

    def for_task(self, task_id: str) -> CodexTaskDeadline:
        if task_id not in self.identity["ordered_task_ids"]:
            raise TaskDeadlineRefused("task is not a declared deadline cell")
        return CodexTaskDeadline(self, task_id)

    def close(self) -> None:
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None
        self._closed = True


@dataclass(frozen=True)
class CodexTaskDeadline:
    store: CodexTaskDeadlineStore
    task_id: str

    @property
    def retains_thread(self) -> bool:
        """B/C share one continuation mechanism; A never adopts a thread."""
        return self.store.control.condition in {"B", "C"}

    def _state(self, *, start: bool = False) -> tuple[dict, dict, float]:
        data = self.store._read()
        cell = data["cells"][self.task_id]
        now = self.store._now()
        if now < data["last_observed_unix"]:
            raise TaskDeadlineRefused("deadline clock moved backwards")
        if start and cell["started_unix"] is None:
            cell["started_unix"] = now
            cell["expires_unix"] = now + TOTAL_SECONDS
        data["last_observed_unix"] = now
        # Persist before any provider boundary, including first admission.
        self.store._write(data)
        return data, cell, now

    def remaining_seconds(self) -> float:
        _, cell, now = self._state(start=True)
        return max(0.0, cell["expires_unix"] - now)

    def bound_timeout(self, single_attempt_seconds: float) -> float:
        remaining = self.remaining_seconds()
        if remaining <= 0:
            raise TaskDeadlineExhausted(EXHAUSTED)
        return min(float(single_attempt_seconds), remaining)

    def attempts_remaining(self) -> bool:
        _, cell, _ = self._state()
        limit = self.store.control.max_attempts
        return limit is None or len(cell["attempts"]) < limit

    def require_resumable(self) -> None:
        """Accounting replay never grants permission to reopen a terminal cell."""
        _, cell, _ = self._state()
        if cell["terminal_reason"] is not None:
            raise TaskDeadlineRefused("content filter stopped this deadline cell")
        binding = cell["continuation"]
        if binding is not None and binding["terminal_reason"] is not None:
            raise TaskDeadlineRefused("native continuation is terminal: " + binding["terminal_reason"])

    def admit_attempt(self, workspace_root: Path) -> int:
        from core.codex_runtime_config import path_is_within

        data, cell, now = self._state(start=True)
        if now >= cell["expires_unix"]:
            raise TaskDeadlineExhausted(EXHAUSTED)
        limit = self.store.control.max_attempts
        if limit is not None and len(cell["attempts"]) >= limit:
            raise TaskDeadlineExhausted(ATTEMPTS_EXHAUSTED)
        if path_is_within(self.store.root, workspace_root):
            raise TaskDeadlineRefused("deadline state is inside the problem workspace")
        index = len(cell["attempts"])
        cell["attempts"].append({
            "index": index, "admitted_unix": now,
            "workspace_root": str(workspace_root.absolute()),
        })
        self.store._write(data)
        return index

    def accounting_continuation(self, identity_sha256: str | None = None) -> dict | None:
        """Read validated host metadata, including terminal usage, without admission.

        Callers must still validate the request, workspace and receipt ledger
        before settlement. This view is not permission to resume a thread.
        """
        _, cell, _ = self._state()
        binding = cell["continuation"]
        if not self.retains_thread:
            return None
        if binding is None:
            if cell["attempts"]:
                raise TaskDeadlineRefused("admitted cell is missing its native continuation binding")
            return None
        if identity_sha256 is not None and binding["identity_sha256"] != identity_sha256:
            raise TaskDeadlineRefused("native continuation request/runtime identity mismatch")
        if binding["phase"] == "starting":
            raise TaskDeadlineRefused("native thread creation was interrupted before its identifier was bound")
        return binding

    def continuation(self, identity_sha256: str | None = None) -> dict | None:
        """Get a resumable binding; terminal cells remain terminal after replay."""
        binding = self.accounting_continuation(identity_sha256)
        if binding is not None and binding["terminal_reason"] is not None:
            raise TaskDeadlineRefused("native continuation is terminal: " + binding["terminal_reason"])
        return binding

    def bind_workspace(self, identity_sha256: str, request_sha256: str, workspace: dict) -> None:
        """Seal the initial staged layout before any runtime can be opened."""
        data, cell, _ = self._state()
        if (not self.retains_thread or cell["continuation"] is not None
                or len(cell["attempts"]) != 1):
            raise TaskDeadlineRefused("native continuation cannot replace an admitted workspace")
        cell["continuation"] = {
            "format": CONTINUATION_FORMAT, "identity_sha256": identity_sha256,
            "request_sha256": request_sha256,
            "workspace": workspace, "phase": "pre_thread", "thread_id": None,
            "usage_boundary": dict.fromkeys(_USAGE_FIELDS, 0), "turns": [],
            "native_resumes": 0, "terminal_reason": None,
        }
        _validate_continuation(cell["continuation"], cell["attempts"])
        self.store._write(data)

    def thread_starting(self) -> None:
        """Write ahead of thread/start; an ambiguous response never means fresh."""
        data, cell, _ = self._state()
        binding = cell["continuation"]
        if binding is None or binding["phase"] != "pre_thread":
            raise TaskDeadlineRefused("native thread start lacks a proven pre-thread binding")
        binding["phase"] = "starting"
        self.store._write(data)

    def bind_thread(self, thread_id: str, *, resumed: bool) -> None:
        """Bind the actual response ID before a turn or receipt can be opened."""
        data, cell, _ = self._state()
        binding = cell["continuation"]
        if binding is None or type(thread_id) is not str or not thread_id.strip():
            raise TaskDeadlineRefused("native runtime returned no thread identifier")
        if resumed:
            if binding["phase"] != "bound" or binding["thread_id"] != thread_id:
                raise TaskDeadlineRefused("native resume returned a different thread identifier")
            binding["native_resumes"] += 1
        else:
            if binding["phase"] != "starting":
                raise TaskDeadlineRefused("native thread response has no pending start")
            binding.update(phase="bound", thread_id=thread_id)
        self.store._write(data)

    def begin_turn(self, attempt_index: int, call_id: str | None) -> dict:
        """Keep a durable receipt ID and invalidate an unobserved usage gap."""
        data, cell, _ = self._state()
        binding = cell["continuation"]
        if (binding is None or binding["phase"] != "bound"
                or binding["terminal_reason"] is not None
                or attempt_index != len(cell["attempts"]) - 1
                or any(turn["attempt_index"] == attempt_index for turn in binding["turns"])):
            raise TaskDeadlineRefused("native turn is not a new admitted attempt")
        before = dict(binding["usage_boundary"])
        binding["turns"].append({
            "attempt_index": attempt_index, "call_id": call_id,
            "before": before, "after": None, "phase": "in_flight",
        })
        # A killed process may miss further activity. Never subtract a stale
        # observation from the next turn and attribute the unseen gap to it.
        binding["usage_boundary"] = dict.fromkeys(_USAGE_FIELDS)
        self.store._write(data)
        return before

    def observe_turn(self, attempt_index: int, after: dict, *, terminal_reason: str | None = None) -> None:
        """Write observed totals before idempotent ledger settlement."""
        from core.codex_cost import CodexTokenTotals, turn_usage_delta

        data, cell, _ = self._state()
        binding = cell["continuation"]
        if binding is None or not binding["turns"] or not _valid_totals(after):
            raise TaskDeadlineRefused("native turn observation is invalid")
        turn = binding["turns"][-1]
        if turn["attempt_index"] != attempt_index or turn["phase"] != "in_flight":
            raise TaskDeadlineRefused("native turn observation belongs to another attempt")
        try:
            turn_usage_delta(CodexTokenTotals(**turn["before"]), CodexTokenTotals(**after))
        except ValueError:
            raise TaskDeadlineRefused("native cumulative usage moved backwards") from None
        turn.update(after=after, phase="observed")
        binding["usage_boundary"] = after
        binding["terminal_reason"] = terminal_reason
        _validate_continuation(binding, cell["attempts"])
        self.store._write(data)

    def acknowledge_usage(self, attempt_index: int) -> None:
        """Mark a persisted observation only after its existing ledger settles."""
        data, cell, _ = self._state()
        binding = cell["continuation"]
        if binding is None:
            raise TaskDeadlineRefused("native usage has no continuation binding")
        for turn in binding["turns"]:
            if turn["attempt_index"] == attempt_index and turn["phase"] == "observed":
                turn["phase"] = "settled" if turn["call_id"] is not None else "unmetered"
                self.store._write(data)
                return
        raise TaskDeadlineRefused("native usage observation is missing")

    def stop_content_filter(self) -> None:
        """Retain a content-filter refusal even if no usage event arrived."""
        data, cell, _ = self._state()
        cell["terminal_reason"] = "content_filtered"
        binding = cell["continuation"]
        if binding is not None:
            binding["terminal_reason"] = "content_filter"
        self.store._write(data)

    def wait(self, seconds: float, sleep: Callable[[float], None]) -> None:
        """Charge a backoff to the original expiry, including an oversleep."""
        before = self.remaining_seconds()
        delay = min(float(seconds), before)
        if delay <= 0:
            raise TaskDeadlineExhausted(EXHAUSTED)
        sleep(delay)
        data, cell, now = self._state()
        cell["wait_seconds"] += min(before, max(0.0, before - max(0.0, cell["expires_unix"] - now)))
        self.store._write(data)
        if now >= cell["expires_unix"]:
            raise TaskDeadlineExhausted(EXHAUSTED)

    def as_record(self) -> dict[str, Any]:
        _, cell, now = self._state()
        return {
            "format": FORMAT, "run_id": self.store.identity["run_id"],
            "task_id": self.task_id, **self.store.control.as_dict(),
            "total_seconds": TOTAL_SECONDS, "attempt_seconds": ATTEMPT_SECONDS,
            "started_unix": cell["started_unix"], "expires_unix": cell["expires_unix"],
            "remaining_seconds": (None if cell["expires_unix"] is None else max(0.0, cell["expires_unix"] - now)),
            "attempts_admitted": len(cell["attempts"]),
            "wait_seconds": cell["wait_seconds"],
            "retained_attempts": len(cell["attempts"]),
            "session_policy": "retained_native_thread" if self.retains_thread else "fresh_session",
            "native_resumes": (cell["continuation"] or {}).get("native_resumes", 0),
            "terminal_reason": cell["terminal_reason"],
            "model_call_accounting": "not_complete", "invoice_accounting": "unavailable",
        }

    def refused_result(self, category: str, previous: dict | None = None) -> dict:
        """Keep the last attempt's evidence while recording a terminal budget stop."""
        result = dict(previous or {})
        result.update(task_id=self.task_id, status="error", error=category)
        observability = dict(result.get("observability") or {})
        observability.update(error_category=category, task_deadline=self.as_record())
        result["observability"] = observability
        result.setdefault("deliverable_files", [])
        return result
