"""What a task finished before the clock ran out. Deliberately not a grade.

Grading resumes at task granularity: ``--resume`` harvests completed
``task_id``s and the driver re-marks everything else from item one. That bound
was chosen on purpose -- ``Grader._check_should_stop`` says "the loss is
bounded at one task and the driver keeps the rest" -- and it holds right up
until one task is longer than a chunk.

``9e39df84`` is that task. Fifty-seven items, ~360 minutes at observed pace,
against a platform ceiling of 351.7. Four paid attempts stopped at 45, 54, 54
and 55 items and each one began again at item one, because a dropped task
leaves nothing behind. No budget setting fixes it; raising the budget only
moves where the money is lost to inside the task.

This module is the other half of the fix in ``305-resume-granularity.md``:
let the dropped task leave its finished items on disk so the next chunk
continues from them.

Three things make that safe, and none of them is optional.

**A checkpoint is not a score.** ``TaskProgress`` has no ``pct``, no
``critical_fail``, no total. Those are computed over a whole rubric and are
false on half of one -- plausible-looking and wrong. The type is structurally
unable to carry them, because a checkpoint shaped like a ``TaskGrade`` is one
someone eventually reads as a ``TaskGrade``. A task is complete when every
item is graded, and not before.

**A checkpoint names the grader that wrote it.** Between two chunks, ``core/``
can change. Shard-level mixing is caught -- ``grader_source_hash`` is a merge
contract identity field, and a mismatched shard is refused loudly. *Inside* a
task there is no such guard: items 1-30 graded at fingerprint X and items
31-57 at fingerprint Y would emerge wearing only Y, and the merge would pass
it. That is worse than the shard case, which fails noisily; this one succeeds
quietly. So resume refuses a checkpoint whose fingerprint is not the current
one and re-grades the task whole.

**A checkpoint carries what was spent, not just what was done.** The per-task
perception caps (``AUDIO_CALL_CAP``, ``VISION_CALL_CAP``) are reset at each
task boundary by ``reset_perception``. A task resumed three times would reset
three times and listen nine times where its neighbour listened three -- the
same rubric marked with a different instrument. Restoring the spent counters
is what keeps the two comparable.

Raw model responses are stripped on the way in. A checkpoint is an operational
artifact that outlives the process and gets committed by the workflow; it has
no business holding a judge's reasoning text.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

#: Bumped when the on-disk shape changes incompatibly. An older checkpoint is
#: discarded rather than migrated -- the task is re-graded, which costs time
#: and is always correct, where a migration guess would cost correctness.
CHECKPOINT_FORMAT = "task-progress-v1"

#: Fields on an ``ItemGrade`` that must never reach disk here. ``grader``
#: config already defaults ``save_raw_responses`` to false, but a checkpoint
#: is written on the failure path, and the failure path is exactly where a
#: debugging flag is most likely to have been switched on.
_REDACTED_ITEM_FIELDS = ("judge_raw_response",)


class CheckpointRejected(Exception):
    """A checkpoint exists but cannot be trusted for this task.

    Carries ``reason`` so the caller can log *why* a task is being re-marked
    from scratch. A silent discard and a silent acceptance look identical in
    a log, and only one of them is correct.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def rubric_order_fingerprint(rubric_item_ids: Sequence[str]) -> str:
    """Digest of a task's rubric item ids, in order.

    Answers "is this the same rubric, asked the same way". Order is part of
    the question: the resume below trusts that the stored items are a prefix
    of the remaining work, and a reordered rubric would make a prefix of the
    old order a scattering of the new one.
    """
    digest = hashlib.sha256(b"gdpval-task-progress-rubric-v1\x00")
    for item_id in rubric_item_ids:
        raw = str(item_id).encode("utf-8")
        digest.update(len(raw).to_bytes(4, "big"))
        digest.update(raw)
    return digest.hexdigest()


@dataclass(frozen=True)
class TaskProgress:
    """Items a task got through, and what it spent getting through them.

    Note what is absent: every field a reader could mistake for a result.
    """

    task_id: str
    grader_source_hash: str
    rubric_fingerprint: str
    #: Serialized ``ItemGrade``s, in canonical rubric order, raw responses
    #: stripped. A prefix of the task's rubric, never a sample of it.
    completed_items: list[dict[str, Any]] = field(default_factory=list)
    #: ``{"vision": n, "audio": m}`` -- calls already charged against this
    #: task's per-task caps.
    perception_spent: dict[str, int] = field(default_factory=dict)
    #: The one task-level tally that is not recomputed from the items.
    #:
    #: Every other usage number on a ``TaskGrade`` -- judge calls, tokens,
    #: latency, perception, ``usage_complete`` -- is summed from per-item
    #: instrumentation by ``Grader._aggregate_tool_instrumentation``, and
    #: those per-item fields ride along inside ``completed_items``. Carrying
    #: a second copy of them here would be a number that is written, read,
    #: assigned and then overwritten a line later: it would look like it was
    #: keeping the task's history and would be doing nothing. Prechecks
    #: resolve an item without a judge call, so nothing per-item counts them.
    precheck_count: int = 0

    @property
    def completed_item_ids(self) -> list[str]:
        return [str(item.get("rubric_item_id")) for item in self.completed_items]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": CHECKPOINT_FORMAT,
            "task_id": self.task_id,
            "grader_source_hash": self.grader_source_hash,
            "rubric_fingerprint": self.rubric_fingerprint,
            "completed_items": self.completed_items,
            "perception_spent": dict(self.perception_spent),
            "precheck_count": self.precheck_count,
        }


def redact_item(item: Mapping[str, Any]) -> dict[str, Any]:
    """Copy an ``ItemGrade`` dict with the model's own words removed."""
    cleaned = dict(item)
    for name in _REDACTED_ITEM_FIELDS:
        if name in cleaned:
            cleaned[name] = None
    return cleaned


@dataclass(frozen=True)
class TaskProgressDraft:
    """What the grader knows when a task stops early, before it is stamped.

    A checkpoint is assembled by two components because neither one holds all
    of it. The grader has the finished items and the running tallies; it does
    *not* know its own source fingerprint, which is a digest over files the
    grader never reads and which ``step8`` computes. So the grader hands out a
    draft and the driver stamps the identity onto it.

    Every field a checkpoint can carry still lives in this module, which is
    what makes "a checkpoint holds no scores" something a reader can verify by
    opening one file rather than three.
    """

    completed_items: tuple[Mapping[str, Any], ...] = ()
    perception_spent: Mapping[str, int] = field(default_factory=dict)
    precheck_count: int = 0


def build_progress(
    *,
    task_id: str,
    grader_source_hash: str,
    rubric_item_ids: Sequence[str],
    draft: TaskProgressDraft,
) -> TaskProgress:
    return TaskProgress(
        task_id=task_id,
        grader_source_hash=grader_source_hash,
        rubric_fingerprint=rubric_order_fingerprint(rubric_item_ids),
        completed_items=[redact_item(item) for item in draft.completed_items],
        perception_spent={
            str(k): int(v) for k, v in draft.perception_spent.items()
        },
        precheck_count=draft.precheck_count,
    )


def checkpoint_path(partial_path: Path, task_id: str) -> Path:
    """Where a task's progress lives, next to the partial it belongs to.

    Beside the shard's own partial rather than in a shared directory: two
    shards grading disjoint slices must not be able to read each other's
    checkpoints, and a path derived from the partial gets that for free --
    the partial path already encodes experiment, config, fingerprint, scope,
    shard index and run ordinal.
    """
    safe = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in task_id)
    return partial_path.parent / "_progress" / f"{partial_path.stem}__{safe}.json"


def write_checkpoint(partial_path: Path, progress: TaskProgress) -> Path:
    """Persist a task's progress atomically.

    Atomic because this is written as the process is being told to stop. A
    half-written checkpoint that still parses is the one failure this whole
    module exists to avoid.
    """
    path = checkpoint_path(partial_path, progress.task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(progress.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def load_checkpoint(
    partial_path: Path,
    *,
    task_id: str,
    grader_source_hash: str,
    rubric_item_ids: Sequence[str],
) -> TaskProgress | None:
    """Return a usable checkpoint, or ``None`` when there is none.

    Raises :class:`CheckpointRejected` when one exists but fails a guard --
    the caller re-grades the task from scratch and logs the reason. That
    distinction matters: "no checkpoint" is the ordinary first chunk, while
    "a checkpoint I refused" is a fact about a fingerprint or a rubric having
    moved underneath a paid run, and it should be visible in the log.
    """
    path = checkpoint_path(partial_path, task_id)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise CheckpointRejected(f"unreadable checkpoint: {exc}") from exc

    if raw.get("format") != CHECKPOINT_FORMAT:
        raise CheckpointRejected(
            f"format {raw.get('format')!r} is not {CHECKPOINT_FORMAT!r}"
        )
    if raw.get("task_id") != task_id:
        raise CheckpointRejected(
            f"checkpoint belongs to {raw.get('task_id')!r}, not {task_id!r}"
        )
    if raw.get("grader_source_hash") != grader_source_hash:
        # The guard the shard-level merge contract cannot provide. See the
        # module docstring: this is the failure that would otherwise succeed.
        raise CheckpointRejected(
            "checkpoint was written by grader source "
            f"{str(raw.get('grader_source_hash'))[:16]}, current is "
            f"{grader_source_hash[:16]}; the task is re-graded whole rather "
            "than finished by a second grader"
        )
    expected = rubric_order_fingerprint(rubric_item_ids)
    if raw.get("rubric_fingerprint") != expected:
        raise CheckpointRejected(
            "rubric items or their order changed since the checkpoint"
        )

    items = raw.get("completed_items")
    if not isinstance(items, list):
        raise CheckpointRejected("completed_items is not a list")
    stored_ids = [str(entry.get("rubric_item_id")) for entry in items]
    if stored_ids != [str(i) for i in rubric_item_ids[: len(stored_ids)]]:
        # A prefix is the only shape resume can continue from. Anything else
        # means items were skipped, and a skipped item resumed past would be
        # scored as never-attempted.
        raise CheckpointRejected(
            "completed items are not a prefix of the rubric in canonical order"
        )
    if len(stored_ids) >= len(rubric_item_ids):
        raise CheckpointRejected(
            "checkpoint claims every item; a finished task belongs in the "
            "partial as a grade, not here as progress"
        )

    spent = raw.get("perception_spent") or {}
    if not isinstance(spent, dict):
        raise CheckpointRejected("perception_spent is not an object")

    return TaskProgress(
        task_id=task_id,
        grader_source_hash=grader_source_hash,
        rubric_fingerprint=expected,
        completed_items=[redact_item(entry) for entry in items],
        perception_spent={str(k): int(v) for k, v in spent.items()},
        precheck_count=int(raw.get("precheck_count") or 0),
    )


def discard_checkpoint(partial_path: Path, task_id: str) -> None:
    """Remove a task's checkpoint once the task is graded whole.

    Called on the success path. A checkpoint left behind for a completed task
    is inert today -- ``load_checkpoint`` refuses a full item list -- but it
    is also a file claiming a task is unfinished when it is not, and the next
    person to read the directory should not have to know that.
    """
    path = checkpoint_path(partial_path, task_id)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
