"""What a 220-task run has already done, written down before it becomes true.

A run over 220 tasks takes hours, and hours is long enough that it will be
interrupted — a runner restarted, a host reclaimed, a wall clock reached. So it
has to be resumable, and the resume has to answer one question per task: *was
this finished, and if not, what has already been spent on it?*

**Why the obvious journal is wrong.** The obvious journal writes one record per
task when the task ends. If the process dies during task 137 there is no record
for 137, so a resume re-runs it — which is right about the work and wrong about
the money. The first attempt's model calls were made and charged, and they are
now invisible to the run's own accounting. Over a few interruptions the run
under-reports its own cost, which is the precise failure the rule *a missing
cost is partial, never zero* exists to stop. A journal that only records
endings cannot distinguish a task that never started from one that started,
cost money, and vanished.

So there are **two records per attempt**, and the first is written *before* the
work:

``opened``
    Flushed to disk before the first model call. It names the task, the attempt
    number, the workspace that attempt owns, and the stage the spend will be
    booked under. Its only purpose is to exist when the process dies.

``closed``
    Written once the outcome is known. It names the disposition, the
    deliverables that were carried out, and whether the cost was settled.

An ``opened`` with no ``closed`` is the signature of an interruption, and it is
the only thing in this repository that can tell one apart from a task that was
never reached.

**What resume is allowed to conclude.** Four states, and the decision is total
over them:

===========================  ==========================================
state                        decision
===========================  ==========================================
no record                    run it, as attempt 1
opened + closed(finished)    skip it — it is done
opened + closed(failed)      run it again if the disposition is
                             retryable, otherwise skip it as a settled
                             failure
opened, no closed            run it again — **and carry the abandoned
                             attempt forward**, so the task's receipt can
                             never afterwards claim to be complete
===========================  ==========================================

**Where attempt numbers come from.** Nowhere, until now.
:func:`core.cost_receipts.make_call_id` derives a call's ledger name partly from
``attempt_index``, which is what keeps a retry's rows from colliding with the
rows of the attempt it is replacing. Nothing owned that number. This journal
does: it hands one out only after the intent to spend is on disk, so a crashed
attempt's number is never reissued and its ledger rows keep their own names
rather than being overwritten by the attempt that followed.

**Per-task isolation, as a refusal rather than a convention.** Each attempt is
given its own workspace name and the journal refuses to hand the same one out
twice. Two tasks sharing a directory would cross-contaminate deliverables in a
way that reads, afterwards, as a model that produced someone else's file. A
resumed attempt gets a *new* directory rather than the dead one's, because a
half-written workspace left by a killed process boots into a guest and produces
work that looks like the model's and is not.

**Refusing to resume into a different run.** The header record holds the run id
and a digest of the fixed task manifest. Appending to a journal whose header
disagrees is refused. Resuming a 220-task run against a different task list
would silently change what "finished" means, and the change would surface as a
coverage figure nobody could reproduce.

**Surviving the kill it exists for.** Records are appended as one line each and
``fsync``-ed, and the containing directory is ``fsync``-ed when the file is
first created, so the file itself survives too. A *last* line that is torn —
the process died mid-write — is dropped, because a journal that refuses to load
after a crash is a journal that does not work at the one moment it is for. A
torn line anywhere *earlier* is refused: that is not an interruption, it is
corruption, and continuing past it would silently drop attempts.

Dropping the torn tail is safe in one direction and only because of the
ordering. An ``opened`` record is flushed *before* :meth:`TaskJournal.open_task`
returns, so a torn ``opened`` means the caller never got its attempt number and
never made a call — there is no spend to lose. A torn ``closed`` leaves an
attempt looking abandoned, which over-states what was lost rather than
under-stating it. Both errors fall on the side that cannot make a receipt claim
more than it should.

This module writes no ledger rows, contacts no provider, boots nothing and
opens nothing. It records and it refuses.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from core.agentic_v2_cost_binding import (
    RETRYABLE_DISPOSITIONS,
    disposition_for_error,
)
from core.agentic_v2_provenance import canonical_sha256
from core.cost_receipts import STAGE_GENERATION, STATUS_COMPLETE, STATUS_PARTIAL


JOURNAL_SCHEMA_VERSION = "agentic-v2-task-journal-v1"
"""Written into the header and checked on load.

A journal read by code that expects different fields is worse than an
unreadable one, because it produces a resume plan rather than an error.
"""

RECORD_HEADER = "header"
RECORD_OPENED = "opened"
RECORD_CLOSED = "closed"

RECORD_KINDS = (RECORD_HEADER, RECORD_OPENED, RECORD_CLOSED)

OUTCOME_FINISHED = "finished"
"""The task produced its deliverables and they were carried out of the guest."""

OUTCOME_FAILED = "failed"
"""The attempt ended with one of the contract's error types."""

OUTCOMES = (OUTCOME_FINISHED, OUTCOME_FAILED)

DECISION_RUN = "run_it"
DECISION_SKIP_FINISHED = "skip_it_finished"
DECISION_SKIP_SETTLED_FAILURE = "skip_it_settled_failure"

DECISIONS = (DECISION_RUN, DECISION_SKIP_FINISHED, DECISION_SKIP_SETTLED_FAILURE)

#: How many attempts one task may be given before the run stops trying.
#:
#: Present so that a task failing for a reason that *looks* retryable and is
#: not — a semantic failure the model reproduces every time — cannot spend the
#: run's whole budget by itself. The ceiling is low on purpose: the point of a
#: retry here is to survive an interruption, not to sample the model until it
#: succeeds.
MOST_ATTEMPTS_PER_TASK = 3

#: How much of a task id survives into a workspace directory name.
#:
#: Truncation alone would let two long ids collide, so the full id's digest is
#: appended; see :func:`workspace_name_for`.
MOST_CHARACTERS_FROM_A_TASK_ID = 48


class JournalRefused(RuntimeError):
    """The journal will not do what was asked, and nothing was written."""


class JournalCorrupt(JournalRefused):
    """The file on disk is not a journal this can safely continue from."""


# ---------------------------------------------------------------------------
# What is on disk
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenedAttempt:
    """An intent to spend, recorded before anything was spent."""

    task_id: str
    attempt_index: int
    workspace_name: str
    stage: str
    opened_at: float


@dataclass(frozen=True)
class ClosedAttempt:
    """How one attempt ended, once that was known."""

    task_id: str
    attempt_index: int
    outcome: str
    error_type: str | None
    disposition: str | None
    deliverables: tuple[Mapping[str, Any], ...]
    cost_settled: bool
    closed_at: float


@dataclass(frozen=True)
class TaskStanding:
    """Everything the journal knows about one task, resolved.

    ``abandoned_attempts`` is the count of attempts that were opened and never
    closed. It is the number that stops a receipt claiming to be complete.
    """

    task_id: str
    attempts: int
    abandoned_attempts: int
    last_closed: ClosedAttempt | None
    decision: str
    reason: str

    @property
    def cost_is_fully_accounted(self) -> bool:
        """Whether every attempt on this task reached a settled cost.

        False whenever an attempt was abandoned, and false when the attempt
        that closed said its cost had not been settled. Either way the spend
        exists and this run cannot name it.
        """
        if self.abandoned_attempts:
            return False
        if self.last_closed is None:
            return True
        return self.last_closed.cost_settled


@dataclass
class JournalState:
    """A journal read back off disk."""

    run_id: str
    manifest_sha256: str
    schema_version: str
    opened: list[OpenedAttempt] = field(default_factory=list)
    closed: list[ClosedAttempt] = field(default_factory=list)
    #: True when the final line was a partial write and was dropped.
    dropped_torn_tail: bool = False

    def attempts_for(self, task_id: str) -> list[OpenedAttempt]:
        return [record for record in self.opened if record.task_id == task_id]

    def closes_for(self, task_id: str) -> list[ClosedAttempt]:
        return [record for record in self.closed if record.task_id == task_id]

    def workspace_names(self) -> set[str]:
        return {record.workspace_name for record in self.opened}


@dataclass(frozen=True)
class ResumePlan:
    """What a resumed run should do with each task in the manifest."""

    run_id: str
    standings: tuple[TaskStanding, ...]

    def to_run(self) -> tuple[str, ...]:
        return tuple(
            standing.task_id
            for standing in self.standings
            if standing.decision == DECISION_RUN
        )

    def receipt_ceiling(self) -> str:
        """The best status this run's receipt may claim, given what was lost.

        A ceiling, never a verdict: the journal can lower what a receipt is
        allowed to say and can never raise it. Anything abandoned puts the run
        at :data:`core.cost_receipts.STATUS_PARTIAL` permanently, because the
        spend happened and no row names it.
        """
        if all(standing.cost_is_fully_accounted for standing in self.standings):
            return STATUS_COMPLETE
        return STATUS_PARTIAL

    def unaccounted_tasks(self) -> tuple[str, ...]:
        return tuple(
            standing.task_id
            for standing in self.standings
            if not standing.cost_is_fully_accounted
        )


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


def manifest_digest(task_ids: Sequence[str]) -> str:
    """A digest of the fixed task list, order included.

    Order is part of it because a run that executes the same 220 tasks in a
    different order is a different run for every purpose that matters here:
    which tasks a wall clock cut off, and which were reached at all.
    """
    ids = [str(value) for value in task_ids]
    if not ids:
        raise JournalRefused("a task manifest with no tasks in it is not a manifest")
    if len(set(ids)) != len(ids):
        raise JournalRefused("a task manifest may not name the same task twice")
    return canonical_sha256(ids)


def workspace_name_for(task_id: str, attempt_index: int) -> str:
    """A directory name for one attempt that no other attempt will be given.

    The task id is cleaned to what a filesystem and a jailer will both accept
    and truncated; the truncation is made safe by appending eight hex
    characters of the full id, so two long ids sharing a prefix do not share a
    workspace.
    """
    if not isinstance(attempt_index, int) or isinstance(attempt_index, bool):
        raise JournalRefused(f"attempt index {attempt_index!r} is not a number")
    if attempt_index < 1:
        raise JournalRefused("attempt numbering starts at 1")
    raw = str(task_id)
    if not raw:
        raise JournalRefused("a task with no id cannot be given a workspace")
    cleaned = "".join(
        character if (character.isalnum() or character in "-_") else "-"
        for character in raw
    )
    stem = cleaned.strip("-")[:MOST_CHARACTERS_FROM_A_TASK_ID] or "task"
    if not stem[0].isalnum():
        stem = f"t{stem}"
    tail = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{tail}-a{attempt_index:02d}"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _line_records(path: Path) -> tuple[list[Mapping[str, Any]], bool]:
    """Every complete record in the file, and whether a torn tail was dropped.

    Records are written ASCII-only, so a write cut in half cannot leave an
    undecodable byte sequence behind — the damage is always a short line, which
    is a thing this can see.
    """
    text = path.read_text(encoding="utf-8")
    if not text:
        raise JournalCorrupt(f"journal {path} is empty and has no header")
    lines = text.split("\n")
    dropped = False
    if lines and lines[-1] == "":
        lines.pop()
    else:
        # No trailing newline: the last write did not finish.
        dropped = True
        lines.pop()
    records: list[Mapping[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except ValueError as error:
            raise JournalCorrupt(
                f"journal {path} line {number} is not a record, and it is not "
                f"the last line, so this is corruption rather than an "
                f"interruption: {error}"
            ) from None
        if not isinstance(value, Mapping):
            raise JournalCorrupt(f"journal {path} line {number} is not an object")
        records.append(value)
    return records, dropped


def _read_opened(value: Mapping[str, Any]) -> OpenedAttempt:
    return OpenedAttempt(
        task_id=str(value["task_id"]),
        attempt_index=int(value["attempt_index"]),
        workspace_name=str(value["workspace_name"]),
        stage=str(value["stage"]),
        opened_at=float(value["at"]),
    )


def _read_closed(value: Mapping[str, Any]) -> ClosedAttempt:
    deliverables = value.get("deliverables") or ()
    if not isinstance(deliverables, Sequence) or isinstance(deliverables, (str, bytes)):
        raise JournalCorrupt("a closed record's deliverables must be a list")
    outcome = str(value["outcome"])
    if outcome not in OUTCOMES:
        raise JournalCorrupt(f"a closed record names an unknown outcome {outcome!r}")
    error_type = value.get("error_type")
    return ClosedAttempt(
        task_id=str(value["task_id"]),
        attempt_index=int(value["attempt_index"]),
        outcome=outcome,
        error_type=None if error_type is None else str(error_type),
        disposition=(
            None if value.get("disposition") is None else str(value["disposition"])
        ),
        deliverables=tuple(dict(entry) for entry in deliverables),
        cost_settled=bool(value["cost_settled"]),
        closed_at=float(value["at"]),
    )


def read_journal(path: str | Path) -> JournalState:
    """Load a journal, dropping a torn final line and refusing an earlier one."""
    where = Path(path)
    try:
        records, dropped = _line_records(where)
    except FileNotFoundError:
        raise JournalRefused(f"there is no journal at {where}") from None
    if not records:
        raise JournalCorrupt(f"journal {where} holds no complete record")

    head = records[0]
    if head.get("kind") != RECORD_HEADER:
        raise JournalCorrupt(f"journal {where} does not begin with a header")
    try:
        state = JournalState(
            run_id=str(head["run_id"]),
            manifest_sha256=str(head["manifest_sha256"]),
            schema_version=str(head["schema_version"]),
            dropped_torn_tail=dropped,
        )
    except KeyError as error:
        raise JournalCorrupt(f"journal {where} header is missing {error}") from None
    if state.schema_version != JOURNAL_SCHEMA_VERSION:
        raise JournalCorrupt(
            f"journal {where} was written under {state.schema_version!r} and this "
            f"is {JOURNAL_SCHEMA_VERSION!r}"
        )

    for number, value in enumerate(records[1:], start=2):
        kind = value.get("kind")
        try:
            if kind == RECORD_OPENED:
                state.opened.append(_read_opened(value))
            elif kind == RECORD_CLOSED:
                state.closed.append(_read_closed(value))
            elif kind == RECORD_HEADER:
                raise JournalCorrupt(
                    f"journal {where} has a second header at line {number}"
                )
            else:
                raise JournalCorrupt(
                    f"journal {where} line {number} is of unknown kind {kind!r}"
                )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, JournalCorrupt):
                raise
            raise JournalCorrupt(
                f"journal {where} line {number} is malformed: {error}"
            ) from None
    return state


# ---------------------------------------------------------------------------
# Deciding
# ---------------------------------------------------------------------------


def _standing_for(state: JournalState, task_id: str) -> TaskStanding:
    opens = state.attempts_for(task_id)
    closes = state.closes_for(task_id)
    closed_indices = {record.attempt_index for record in closes}
    abandoned = sum(
        1 for record in opens if record.attempt_index not in closed_indices
    )
    last_closed = closes[-1] if closes else None

    if not opens:
        return TaskStanding(
            task_id=task_id,
            attempts=0,
            abandoned_attempts=0,
            last_closed=None,
            decision=DECISION_RUN,
            reason="never attempted",
        )

    if last_closed is not None and last_closed.outcome == OUTCOME_FINISHED:
        return TaskStanding(
            task_id=task_id,
            attempts=len(opens),
            abandoned_attempts=abandoned,
            last_closed=last_closed,
            decision=DECISION_SKIP_FINISHED,
            reason="finished, with deliverables carried out",
        )

    if len(opens) >= MOST_ATTEMPTS_PER_TASK:
        return TaskStanding(
            task_id=task_id,
            attempts=len(opens),
            abandoned_attempts=abandoned,
            last_closed=last_closed,
            decision=DECISION_SKIP_SETTLED_FAILURE,
            reason=(
                f"{len(opens)} attempts is the ceiling; a further one would "
                "spend without evidence that it would end differently"
            ),
        )

    if abandoned and (last_closed is None or last_closed.attempt_index < max(
        record.attempt_index for record in opens
    )):
        return TaskStanding(
            task_id=task_id,
            attempts=len(opens),
            abandoned_attempts=abandoned,
            last_closed=last_closed,
            decision=DECISION_RUN,
            reason=(
                "the last attempt was interrupted before it could say how it "
                "ended; its spend is real and is carried forward"
            ),
        )

    if last_closed is None:  # pragma: no cover - unreachable by construction
        # Every open attempt is either closed or abandoned, and the abandoned
        # case returned above. Raising rather than asserting because `assert`
        # is removed under -O, and a silent fall-through here would decide a
        # task's fate from nothing.
        raise JournalCorrupt(
            f"task {task_id!r} has open attempts, none abandoned, and no close"
        )
    if last_closed.disposition in RETRYABLE_DISPOSITIONS:
        return TaskStanding(
            task_id=task_id,
            attempts=len(opens),
            abandoned_attempts=abandoned,
            last_closed=last_closed,
            decision=DECISION_RUN,
            reason=f"failed with a retryable disposition: {last_closed.disposition}",
        )
    return TaskStanding(
        task_id=task_id,
        attempts=len(opens),
        abandoned_attempts=abandoned,
        last_closed=last_closed,
        decision=DECISION_SKIP_SETTLED_FAILURE,
        reason=(
            f"failed with {last_closed.disposition!r}, which a further attempt "
            "would not change"
        ),
    )


def plan_resume(state: JournalState, task_ids: Sequence[str]) -> ResumePlan:
    """Decide, for every task in the fixed manifest, what a resume should do.

    Refuses a manifest that is not the one the journal was opened against. A
    resume against a different task list would quietly redefine what "finished"
    means for the run, and the redefinition would only ever surface as a
    coverage figure that could not be reproduced.
    """
    digest = manifest_digest(task_ids)
    if digest != state.manifest_sha256:
        raise JournalRefused(
            "this journal was opened against a different task manifest "
            f"({state.manifest_sha256[:12]}…, and this one is {digest[:12]}…). "
            "Resuming across manifests would change what the run covers"
        )
    known = set(task_ids)
    strays = sorted({record.task_id for record in state.opened} - known)
    if strays:
        raise JournalRefused(
            f"the journal holds attempts on tasks the manifest does not name: "
            f"{strays[:5]}"
        )
    return ResumePlan(
        run_id=state.run_id,
        standings=tuple(_standing_for(state, task_id) for task_id in task_ids),
    )


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


class TaskJournal:
    """The append-only record a resumable run is driven from.

    One instance owns one file. Opening an existing file adopts its contents
    after checking that the run and the manifest are the same ones — so a
    restarted process continues the journal it left rather than starting a
    second one beside it.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        task_ids: Sequence[str],
        stage: str = STAGE_GENERATION,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = Path(path)
        self.run_id = str(run_id)
        self.task_ids = tuple(str(value) for value in task_ids)
        self.manifest_sha256 = manifest_digest(self.task_ids)
        self.stage = str(stage)
        self._clock = clock
        self._known = set(self.task_ids)
        self._open_task: OpenedAttempt | None = None

        if self.path.exists() and self.path.stat().st_size > 0:
            state = read_journal(self.path)
            if state.run_id != self.run_id:
                raise JournalRefused(
                    f"journal {self.path} belongs to run {state.run_id!r} and this "
                    f"is {self.run_id!r}; two runs must not share a journal"
                )
            if state.manifest_sha256 != self.manifest_sha256:
                raise JournalRefused(
                    f"journal {self.path} was opened against a different task "
                    "manifest"
                )
            self.state = state
        else:
            self.state = JournalState(
                run_id=self.run_id,
                manifest_sha256=self.manifest_sha256,
                schema_version=JOURNAL_SCHEMA_VERSION,
            )
            # A zero-length file is a header write that did not survive. Nothing
            # had been opened when it was made, so there is nothing to recover
            # and starting the header again loses no attempt.
            self._create_with_header()

    # -- disk ------------------------------------------------------------

    def _create_with_header(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        header = {
            "kind": RECORD_HEADER,
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "run_id": self.run_id,
            "manifest_sha256": self.manifest_sha256,
            "task_count": len(self.task_ids),
            "stage": self.stage,
            "at": self._clock(),
        }
        self._append(header)
        # The record is durable; the directory entry pointing at the file is
        # not, until the directory itself is flushed.
        directory = os.open(str(self.path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _append(self, record: Mapping[str, Any]) -> None:
        line = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        )
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    # -- the two records -------------------------------------------------

    def open_task(self, task_id: str) -> OpenedAttempt:
        """Record the intent to spend on one task, and hand out its attempt.

        Written and flushed before the caller makes a single model call. The
        record's whole purpose is to exist if the process does not.
        """
        task_id = str(task_id)
        if task_id not in self._known:
            raise JournalRefused(
                f"task {task_id!r} is not in this run's fixed manifest"
            )
        if self._open_task is not None:
            raise JournalRefused(
                f"task {self._open_task.task_id!r} is still open; one task at a "
                "time is what keeps two tasks out of one sandbox"
            )
        prior = self.state.attempts_for(task_id)
        if any(
            record.outcome == OUTCOME_FINISHED
            for record in self.state.closes_for(task_id)
        ):
            raise JournalRefused(f"task {task_id!r} has already finished")
        if len(prior) >= MOST_ATTEMPTS_PER_TASK:
            raise JournalRefused(
                f"task {task_id!r} has had {len(prior)} attempts, which is the "
                f"ceiling of {MOST_ATTEMPTS_PER_TASK}"
            )
        attempt_index = len(prior) + 1
        workspace = workspace_name_for(task_id, attempt_index)
        if workspace in self.state.workspace_names():
            raise JournalRefused(
                f"workspace {workspace!r} has been used before; a reused "
                "workspace is how one task's files end up in another's result"
            )
        opened = OpenedAttempt(
            task_id=task_id,
            attempt_index=attempt_index,
            workspace_name=workspace,
            stage=self.stage,
            opened_at=self._clock(),
        )
        self._append({
            "kind": RECORD_OPENED,
            "task_id": opened.task_id,
            "attempt_index": opened.attempt_index,
            "workspace_name": opened.workspace_name,
            "stage": opened.stage,
            "at": opened.opened_at,
        })
        self.state.opened.append(opened)
        self._open_task = opened
        return opened

    def close_task(
        self,
        *,
        outcome: str,
        error_type: str | None = None,
        deliverables: Iterable[Mapping[str, Any]] = (),
        cost_settled: bool,
    ) -> ClosedAttempt:
        """Record how the open attempt ended, once its cost has been settled.

        ``cost_settled`` is not a courtesy flag. A caller that settled nothing
        and says it did turns an unpriced attempt into one the receipt will
        count as complete, and the loss is unrecoverable afterwards because the
        guest and its workspace are gone.
        """
        opened = self._open_task
        if opened is None:
            raise JournalRefused("no task is open, so there is nothing to close")
        if outcome not in OUTCOMES:
            raise JournalRefused(
                f"{outcome!r} is not an outcome; it is one of {OUTCOMES}"
            )

        if outcome == OUTCOME_FINISHED:
            if error_type is not None:
                raise JournalRefused(
                    "a finished task does not also carry an error type"
                )
            disposition = None
            collected = tuple(dict(entry) for entry in deliverables)
            if not collected:
                raise JournalRefused(
                    "a task that finished with no deliverables carried out is "
                    "not a task that finished; the workspace is purged at close "
                    "and there is nothing left to collect later"
                )
            for entry in collected:
                missing = {"path", "sha256", "size"} - set(entry)
                if missing:
                    raise JournalRefused(
                        f"a deliverable is missing {sorted(missing)}; a path with "
                        "no digest is a claim rather than a record"
                    )
        else:
            # Raises on an error type the contract does not name, which is the
            # point: an unrecorded failure mode must not reach the report as a
            # blank. Re-raised as a refusal so that a caller guarding the
            # journal with one exception type does not miss it.
            try:
                disposition = disposition_for_error(error_type)
            except ValueError as error:
                raise JournalRefused(str(error)) from None
            collected = tuple(dict(entry) for entry in deliverables)

        closed = ClosedAttempt(
            task_id=opened.task_id,
            attempt_index=opened.attempt_index,
            outcome=outcome,
            error_type=error_type,
            disposition=disposition,
            deliverables=collected,
            cost_settled=bool(cost_settled),
            closed_at=self._clock(),
        )
        self._append({
            "kind": RECORD_CLOSED,
            "task_id": closed.task_id,
            "attempt_index": closed.attempt_index,
            "outcome": closed.outcome,
            "error_type": closed.error_type,
            "disposition": closed.disposition,
            "deliverables": [dict(entry) for entry in closed.deliverables],
            "cost_settled": closed.cost_settled,
            "at": closed.closed_at,
        })
        self.state.closed.append(closed)
        self._open_task = None
        return closed

    # -- reading back ----------------------------------------------------

    def plan(self) -> ResumePlan:
        """What a resume of this run would do, as of what is on disk now."""
        return plan_resume(self.state, self.task_ids)

    def standing(self, task_id: str) -> TaskStanding:
        return _standing_for(self.state, str(task_id))
