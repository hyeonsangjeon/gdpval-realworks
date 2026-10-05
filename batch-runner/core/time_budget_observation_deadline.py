"""The prospective comparison's nonrenewable 1200s + 20s host control.

This is not the closed CodexTaskDeadlineStore, a model-request quota, a launch
gate, or a remote cancellation guarantee. The caller reserves one observation
in a host-owned directory before preparing it. An existing reservation is never
adopted. A retained host lease means cleanup was not confirmed.
Durable cleanup snapshots are never release authority. A missing lease after
interrupted finalization is also uncertainty: reuse needs the same live host's
one-use, before-deadline confirmation, not a receipt or a restarted process.

Supervision belongs to the main thread of the owned POSIX host process. SIGALRM
interrupts blocking local I/O, including turn creation and Responses.create;
unsupported threads and pre-existing timers refuse before generation. No daemon
watchdog or independently renewed cleanup grace is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Callable, Iterator

STUDY_ID = "gpt54_sandboxv2_codex_time_budget_v1"
GENERATION_SECONDS = 1200
CLEANUP_SECONDS = 20
TIMEOUT = "time_budget_observation_deadline_exhausted"
REFUSED = "time_budget_observation_admission_refused"
CLEANUP_UNCONFIRMED = "time_budget_observation_cleanup_unconfirmed"
TASK_IDS = (
    "02aa1805-c658-4069-8a6a-02dec146063a",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",
)


class ObservationDeadlineRefused(ValueError):
    """No admission, restart, or clean-host claim is available."""


class ObservationTimedOut(BaseException):
    """Cannot be swallowed by provider/tool retry handlers catching Exception."""


class ObservationCleanupExpired(BaseException):
    """The single cleanup deadline has expired; retain the host lease."""


def _json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


@dataclass(frozen=True)
class ObservationIdentity:
    study_id: str
    run_id: str
    condition: str
    repeat: int
    task_id: str
    reviewed_source_sha: str
    reviewed_source_tree: str
    registration_sha256: str
    input_sha256: str

    def __post_init__(self) -> None:
        suffix = {"sandbox_v2": "v2", "codex": "codex"}.get(self.condition)
        if (
            self.study_id != STUDY_ID
            or suffix is None
            or type(self.repeat) is not int
            or self.repeat not in (1, 2)
            or self.run_id != f"gpt54_time_budget_v1_{suffix}_r{self.repeat}"
            or self.task_id not in TASK_IDS
        ):
            raise ObservationDeadlineRefused(REFUSED)
        for name, length in (
            ("reviewed_source_sha", 40),
            ("reviewed_source_tree", 40),
            ("registration_sha256", 64),
            ("input_sha256", 64),
        ):
            value = getattr(self, name)
            if (
                type(value) is not str
                or re.fullmatch(f"[0-9a-f]{{{length}}}", value) is None
            ):
                raise ObservationDeadlineRefused(REFUSED)

    @property
    def key(self) -> str:
        # Changing an input/source digest must not mint a second attempt at the
        # same registered observation. Bindings live in its immutable receipt.
        return hashlib.sha256(
            _json(
                {
                    name: getattr(self, name)
                    for name in (
                        "study_id",
                        "run_id",
                        "condition",
                        "repeat",
                        "task_id",
                    )
                }
            )
        ).hexdigest()


class TimeBudgetObservation:
    """One reserved observation, including the host's final cleanup obligation."""

    # No durable success bit can attest to the completion of its own fsync.
    # Keep snapshots pessimistic and authorize reuse only after ALL finalization
    # I/O returned within the deadline. PID binding rejects inherited fork state.
    _released_hosts: dict[tuple[int, int, int, str], str] = {}

    def __init__(
        self,
        directory: Path,
        identity: ObservationIdentity,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        if type(identity) is not ObservationIdentity:
            raise ObservationDeadlineRefused(REFUSED)
        from core.inference_manifest import _assert_no_symlink_ancestors

        path = Path(directory)
        if ".." in path.parts:
            raise ObservationDeadlineRefused(REFUSED)
        self.directory = Path(os.path.abspath(path))
        _assert_no_symlink_ancestors(self.directory)
        self._directory_identity = self.directory.stat()
        if (
            not stat.S_ISDIR(self._directory_identity.st_mode)
            or self._directory_identity.st_uid != os.geteuid()
            or stat.S_IMODE(self._directory_identity.st_mode) & 0o077
        ):
            raise ObservationDeadlineRefused(REFUSED)
        self.identity = identity
        self.clock = clock
        self._last_clock = self._now()
        self.first_start: float | None = None
        self.terminal_at: float | None = None
        self.terminal_reason: str | None = None
        self.cleanup_deadline: float | None = None
        self.cleanup_complete = False
        self.cleanup_expired = False
        self.cleanup_failed = False
        self.interruption_attempted = False
        self.interruption_acknowledged = False
        self._claimed = False
        self._supervising = 0
        self._cleanup_step_end: float | None = None
        self._before_processes: dict[int, tuple[int, str, str]] | None = None
        self._finished = False
        self._cleanup_finished_at: float | None = None
        self._host_key = (
            os.getpid(),
            self._directory_identity.st_dev,
            self._directory_identity.st_ino,
            str(self.directory),
        )
        if os.path.lexists(self.directory / (identity.key + ".admitted.json")):
            raise ObservationDeadlineRefused(REFUSED)
        parent = self._directory_fd()
        try:
            admitted = {
                name for name in os.listdir(parent) if name.endswith(".admitted.json")
            }
        finally:
            os.close(parent)
        released = self._released_hosts.pop(self._host_key, None)
        if admitted and (
            released is None or released + ".admitted.json" not in admitted
        ):
            # In particular, unlink may have succeeded before its fsync timed
            # out. Absence of host-lease.json must not admit the next observation.
            raise ObservationDeadlineRefused(REFUSED)
        self._write("host-lease.json", {"observation": identity.key})
        # Failure between these writes deliberately retains the host lease.
        self._write(identity.key + ".admitted.json", asdict(identity))

    def _now(self) -> float:
        now = self.clock()
        if (
            type(now) not in (int, float)
            or not math.isfinite(now)
            or now < getattr(self, "_last_clock", now)
        ):
            raise ObservationDeadlineRefused("time_budget_monotonic_clock_refused")
        self._last_clock = now
        return float(now)

    def _directory_fd(self) -> int:
        from core.inference_manifest import _assert_no_symlink_ancestors

        _assert_no_symlink_ancestors(self.directory)
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        current = os.fstat(fd)
        if (current.st_dev, current.st_ino) != (
            self._directory_identity.st_dev,
            self._directory_identity.st_ino,
        ):
            os.close(fd)
            raise ObservationDeadlineRefused(REFUSED)
        return fd

    def _write(self, name: str, value: object) -> None:
        payload = memoryview(_json(value))
        self._arm()
        parent = self._directory_fd()
        try:
            self._arm()
            fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            # An alarm must not trigger another buffered flush while unwinding.
            with os.fdopen(fd, "wb", buffering=0) as target:
                self._arm()
                while payload:
                    written = target.write(payload)
                    self._arm()
                    if not written:
                        raise ObservationDeadlineRefused(REFUSED)
                    payload = payload[written:]
                os.fsync(target.fileno())
                self._arm()
            self._arm()
            os.fsync(parent)
            self._arm()
        except OSError as error:
            raise ObservationDeadlineRefused(REFUSED) from error
        finally:
            os.close(parent)

    def claim(self, *, run_id: str, condition: str, task_id: str) -> None:
        if (
            self._claimed
            or self._finished
            or self.terminal_reason is not None
            or (run_id, condition, task_id)
            != (self.identity.run_id, self.identity.condition, self.identity.task_id)
        ):
            raise ObservationDeadlineRefused(REFUSED)
        self._require_owned_host()
        self._before_processes = self._descendants()
        self._write(self.identity.key + ".claimed.json", {"claimed": True})
        self._claimed = True

    def require_unclaimed(self) -> None:
        """A second factory cannot construct another provider for this identity."""
        if (
            self._claimed
            or self._finished
            or self.terminal_reason is not None
            or os.path.lexists(self.directory / (self.identity.key + ".claimed.json"))
        ):
            raise ObservationDeadlineRefused(REFUSED)
        self._require_owned_host()
        os.close(self._directory_fd())

    def start(self) -> None:
        if (
            not self._claimed
            or self.terminal_reason is not None
            or not self._supervising
        ):
            raise ObservationDeadlineRefused(REFUSED)
        if self.first_start is None:
            self.first_start = self._now()
            self._write(
                self.identity.key + ".started.json",
                {
                    "first_start_monotonic": self.first_start,
                    "generation_deadline_monotonic": self.first_start
                    + GENERATION_SECONDS,
                },
            )
        self.check_generation()
        self._arm()

    def remaining_seconds(self) -> float:
        if self.terminal_reason is not None:
            return 0.0
        if self.first_start is None:
            return float(GENERATION_SECONDS)
        return max(0.0, self.first_start + GENERATION_SECONDS - self._now())

    def check_generation(self) -> None:
        if self.terminal_reason == TIMEOUT:
            raise ObservationTimedOut(TIMEOUT)
        if self.terminal_reason is not None:
            raise ObservationDeadlineRefused(REFUSED)
        if self.first_start is not None and self.remaining_seconds() <= 0:
            self.terminal(TIMEOUT)
            raise ObservationTimedOut(TIMEOUT)

    def terminal(self, reason: str) -> None:
        if self.terminal_reason is not None:
            return  # The first terminal result is immutable, including timeout.
        if reason not in {"completed", "failed", "cancelled", "abandoned", TIMEOUT}:
            raise ObservationDeadlineRefused(REFUSED)
        now = self._now()
        if (
            self.first_start is not None
            and now >= self.first_start + GENERATION_SECONDS
        ):
            reason = TIMEOUT
        self.terminal_reason = reason
        self.terminal_at = now
        self.cleanup_deadline = (
            self.first_start + GENERATION_SECONDS + CLEANUP_SECONDS
            if reason == TIMEOUT
            else now + CLEANUP_SECONDS
        )
        try:
            # SIGALRM is one-shot. Arm the ORIGINAL absolute cleanup end before
            # any terminal receipt I/O, including when called by the alarm or
            # outside a generation supervisor. Persistence spends the remainder.
            with self.supervise():
                self._arm()
                self._write(
                    self.identity.key + ".terminal.json",
                    {
                        "reason": reason,
                        "terminal_monotonic": now,
                        "cleanup_deadline_monotonic": self.cleanup_deadline,
                    },
                )
                self._arm()
        except BaseException:
            self.cleanup_failed = True
            raise

    def remaining_cleanup(self) -> float:
        if self.cleanup_deadline is None:
            raise ObservationDeadlineRefused("time_budget_cleanup_before_terminal")
        return max(0.0, self.cleanup_deadline - self._now())

    def _alarm(self, signum, frame) -> None:
        if self.terminal_reason is None:
            self.interruption_attempted = True
            try:
                self.terminal(
                    TIMEOUT
                )  # Persist the latch BEFORE interruption/unwinding.
            except Exception:
                # A failed receipt write must not turn the alarm into an
                # Exception that a provider's internal retry loop can swallow.
                # terminal() has already latched the outcome in memory; never
                # release this host without the missing durable evidence.
                self.cleanup_failed = True
            raise ObservationTimedOut(TIMEOUT)
        self.cleanup_expired |= self.remaining_cleanup() <= 0
        self.cleanup_failed = True
        self.cleanup_complete = False
        self._released_hosts.pop(self._host_key, None)
        raise ObservationCleanupExpired(CLEANUP_UNCONFIRMED)

    def _arm(self) -> None:
        if self._supervising:
            remaining = (
                self.remaining_cleanup()
                if self.terminal_reason is not None
                else self.remaining_seconds()
                if self.first_start is not None
                else None
            )
            if self._cleanup_step_end is not None:
                remaining = min(remaining, self._cleanup_step_end - self._now())
            if remaining is not None and remaining <= 0:
                self._alarm(signal.SIGALRM, None)
            signal.setitimer(signal.ITIMER_REAL, remaining or 0.0)

    @contextmanager
    def supervise(self) -> Iterator[None]:
        if self._supervising:
            self._supervising += 1
            try:
                yield
            finally:
                self._supervising -= 1
            return
        self._require_owned_host()
        previous = signal.signal(signal.SIGALRM, self._alarm)
        self._supervising = 1
        try:
            self._arm()
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, previous)
            self._supervising = 0

    def _require_owned_host(self) -> None:
        if (
            threading.current_thread() is not threading.main_thread()
            or not hasattr(signal, "setitimer")
            or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0)
        ):
            raise ObservationDeadlineRefused(
                "time_budget_owned_host_supervision_required"
            )

    def cleanup(
        self,
        operation: Callable[[], object],
        *,
        interruption: bool = False,
        step_seconds: float | None = None,
    ) -> bool:
        """All close/join/collect/remove stages spend this same remainder."""
        if self._finished:
            raise ObservationDeadlineRefused(REFUSED)
        if self.terminal_reason is None:
            self.terminal("failed")
        if interruption:
            self.interruption_attempted = True
        previous_end = self._cleanup_step_end
        try:
            if step_seconds is not None:
                # A short interrupt/close attempt leaves time to kill an owned
                # worker. It can shorten, never extend, the one cleanup end.
                if not 0 < step_seconds <= CLEANUP_SECONDS:
                    raise ObservationDeadlineRefused(REFUSED)
                self._cleanup_step_end = min(
                    self.cleanup_deadline, self._now() + step_seconds
                )
            if self.remaining_cleanup() <= 0:
                raise ObservationCleanupExpired(CLEANUP_UNCONFIRMED)
            with self.supervise():
                self._arm()
                acknowledged = operation()
                if (
                    self.remaining_cleanup() <= 0
                    or self._cleanup_step_end is not None
                    and self._now() >= self._cleanup_step_end
                ):
                    raise ObservationCleanupExpired(CLEANUP_UNCONFIRMED)
            if interruption:
                # Returning None from close/terminate is NOT remote acknowledgement.
                self.interruption_acknowledged |= acknowledged is True
            elif acknowledged is False:
                self.cleanup_failed = True
                return False
            return True
        except ObservationCleanupExpired:
            self.cleanup_expired |= self.remaining_cleanup() <= 0
            self.cleanup_failed = True
            return False
        except Exception:
            self.cleanup_failed = True
            return False
        finally:
            self._cleanup_step_end = previous_end
            if self._supervising:
                if self.remaining_cleanup() > 0:
                    self._arm()
                else:
                    signal.setitimer(signal.ITIMER_REAL, 0.0)

    @staticmethod
    def _process(pid: int) -> tuple[int, str, str] | None:
        try:
            # stat's command name may contain spaces and parentheses. Fields
            # after its final ')' are state, parent, group, ... start ticks.
            with open(f"/proc/{pid}/stat", "rb") as source:
                fields = source.read(8192).rsplit(b")", 1)[1].split()
            return int(fields[2]), fields[19].decode("ascii"), fields[0].decode("ascii")
        except FileNotFoundError:
            return None

    @classmethod
    def _descendants(cls) -> dict[int, tuple[int, str, str]]:
        proc = Path("/proc")
        if not proc.is_dir():
            raise ObservationDeadlineRefused(
                "time_budget_owned_host_supervision_required"
            )
        parents = {}
        identities = {}
        for leaf in proc.iterdir():
            if not leaf.name.isdigit():
                continue
            pid = int(leaf.name)
            try:
                with (leaf / "stat").open("rb") as source:
                    fields = source.read(8192).rsplit(b")", 1)[1].split()
                parents[pid] = int(fields[1])
                identities[pid] = (
                    int(fields[2]),
                    fields[19].decode("ascii"),
                    fields[0].decode("ascii"),
                )
            except (FileNotFoundError, ProcessLookupError):
                continue
        owned = {os.getpid()}
        while True:
            new = {pid for pid, parent in parents.items() if parent in owned} - owned
            if not new:
                break
            owned.update(new)
        return {pid: identities[pid] for pid in owned if pid != os.getpid()}

    def stop_owned_processes(self, process=None) -> bool:
        """Stop only new owned descendants; never signal the host's group.

        TERM, KILL, the SDK process wait, and confirmation all consume the
        existing cleanup remainder. A process identity that cannot be confirmed
        stopped retains the host lease; sending a signal alone is not proof.
        """

        def stop():
            if self._before_processes is None:
                return False
            owned = {
                pid: value
                for pid, value in self._descendants().items()
                if self._before_processes.get(pid, (None, None))[1] != value[1]
            }
            for sig in (signal.SIGTERM, signal.SIGKILL):
                for pid, identity in owned.items():
                    current = self._process(pid)
                    if (
                        current is None
                        or current[1] != identity[1]
                        or current[2] == "Z"
                    ):
                        continue
                    try:
                        self.interruption_attempted |= self.terminal_reason == TIMEOUT
                        if current[0] == pid and pid != os.getpgrp():
                            os.killpg(pid, sig)
                        else:
                            os.kill(pid, sig)
                    except ProcessLookupError:
                        pass
            if process is not None:
                # The pinned SDK owns a Popen. Capture it BEFORE SDK.close()
                # clears _proc, and never perform its unbounded final wait.
                if process.poll() is None:
                    self.interruption_attempted |= self.terminal_reason == TIMEOUT
                    process.kill()
                process.wait(timeout=min(1.0, self.remaining_cleanup()))
            return all(
                (current := self._process(pid)) is None
                or current[1] != identity[1]
                or current[2] == "Z"
                for pid, identity in owned.items()
            )

        return self.cleanup(stop)

    def finish_cleanup(self, confirmed: bool) -> None:
        if self._finished:
            raise ObservationDeadlineRefused(REFUSED)
        try:
            if self.terminal_reason is None:
                self.terminal("abandoned")
            if self._before_processes is not None:
                self.cleanup(
                    lambda: (
                        not any(
                            value[2] != "Z"
                            and self._before_processes.get(pid, (None, None))[1] != value[1]
                            for pid, value in self._descendants().items()
                        )
                    )
                )
            with self.supervise():
                self._arm()
                parent = self._directory_fd()
                try:
                    self._arm()
                    fd = os.open("host-lease.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                    with os.fdopen(fd, "rb") as lease:
                        held = os.fstat(lease.fileno())
                        if (
                            not stat.S_ISREG(held.st_mode)
                            or held.st_nlink != 1
                            or lease.read(4096) != _json({"observation": self.identity.key})
                        ):
                            raise ObservationDeadlineRefused(REFUSED)
                    self._arm()
                    releasable = bool(
                        confirmed and not self.cleanup_failed and not self.cleanup_expired
                    )
                    # This snapshot precedes its own write/fsync and lease I/O.
                    # Never write optimistic reusable-host evidence that would
                    # need an unbounded compensating write after expiry.
                    snapshot = self.as_record()
                    snapshot["finalization_pending"] = True
                    self._write(self.identity.key + ".cleanup.json", snapshot)
                    self._arm()
                    if releasable:
                        os.unlink("host-lease.json", dir_fd=parent)
                        self._arm()
                        os.fsync(parent)
                        self._arm()
                finally:
                    os.close(parent)
                self._arm()
            # Include supervisor teardown, not just receipt persistence, in the
            # final sample. No filesystem operation follows this confirmation.
            finished = self._now()
            if finished >= self.cleanup_deadline:
                raise ObservationCleanupExpired(CLEANUP_UNCONFIRMED)
            self._cleanup_finished_at = finished
            self.cleanup_complete = releasable
            if releasable:
                self._released_hosts[self._host_key] = self.identity.key
        except ObservationCleanupExpired:
            self.cleanup_expired = True
            self.cleanup_failed = True
            self.cleanup_complete = False
            self._released_hosts.pop(self._host_key, None)
        except BaseException:
            self.cleanup_failed = True
            self.cleanup_complete = False
            self._released_hosts.pop(self._host_key, None)
            raise
        finally:
            self._finished = True

    def as_record(self) -> dict:
        now = self._now()
        return {
            "policy": "time_budget_observation_deadline_v1",
            "identity": asdict(self.identity),
            "admitted": True,
            "first_start_monotonic": self.first_start,
            "terminal_reason": self.terminal_reason,
            "generation_elapsed_seconds": (
                None
                if self.first_start is None
                else (now if self.terminal_at is None else self.terminal_at)
                - self.first_start
            ),
            "cleanup_deadline_monotonic": self.cleanup_deadline,
            "cleanup_finished_monotonic": self._cleanup_finished_at,
            "cleanup_elapsed_seconds": None
            if self.terminal_at is None
            else (now if self._cleanup_finished_at is None else self._cleanup_finished_at)
            - self.terminal_at,
            "interruption_attempted": self.interruption_attempted,
            "interruption_acknowledged": self.interruption_acknowledged,
            "interruption_acknowledgement_scope": "local_runtime_only_not_remote_cancellation",
            "cleanup_complete": self.cleanup_complete,
            "cleanup_expired": self.cleanup_expired,
            "host_reusable": self.cleanup_complete,
            "remote_cancellation_confirmed": False,
            "remote_billing_bound": False,
        }
