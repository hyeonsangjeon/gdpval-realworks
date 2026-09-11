"""Putting a task's reference files where the model can actually open them.

Every V2 record so far has carried the same true, useless sentence: 125 of 220
tasks name reference files that nothing copies into the workspace.
:func:`core.agentic_v2_manifest_binding.unmet_needs` reports it per task and
says outright that reporting is not fixing. This is the fixing.

**Why this is not a new copy routine.** The hard part of moving a file from a
downloaded dataset into a workspace is not the copy; it is doing it without
following a link out of the tree, without accepting a file that changed halfway
through, and without a path that climbs out of the destination.
:mod:`core.agentic_input_manifest` already solved that for V1, carefully, and
those primitives are imported here rather than written again. A second
implementation of a security-critical copy is a second thing to get right and a
second thing to keep right.

**Why it is not simply V1's function, then.** Three things in
:func:`core.agentic_input_manifest.build_input_manifest` are wrong for V2, and
each is a deliberate difference rather than an oversight:

*It stages into a temporary directory and deletes it.* V1 wants the identities
— it computes hashes so the Docker backend can verify its own staging against
them. V2 wants the bytes to still be there when a task starts. The destination
here is real and outlives the call.

*It takes V1's selection manifest.* ``validate_selection_manifest`` pins
``schema_version == "agentic-task-subset-v1"`` and ``seed == "20260717"``. V2's
cohort comes from :mod:`core.agentic_v2_preregistration` with its own seal.
Neither could satisfy the other's check, and loosening V1's would weaken a
frozen identity that other work depends on.

*It raises on the first problem, which would refuse the whole cohort.* That is
right for V1, where the manifest is all-or-nothing. It is wrong here, and the
dataset says so: task ``a941b6d8-4289-4500-b45a-f8e4fc94a724`` carries a 689.1
MB video, larger than ``MAX_INPUT_SINGLE``. Under V1's semantics that one file
refuses all two hundred and twenty tasks. So refusal here is **per file**, it is
**recorded by name and reason**, and the other files of that same task are still
delivered.

**What a refusal must never become.** A file that could not be staged is not the
same as a task with no files, and neither is the same as a task that got
everything. If those three collapse into one, a model failing because it was
never given the spreadsheet reads afterwards as a model that could not do the
work. So the record distinguishes them, per task, by name, and
:func:`staging_record` is what the run record carries instead of the old flat
``reference_file_bytes_are_in_the_guest: False``.

**What this does not decide.** It does not choose a substitute for a file too
large to deliver — a transcript, sampled frames, a summary. That choice changes
what the task measures and belongs to whoever is willing to write down that it
was made. Here the file is refused, named, and its size given.

Nothing here calls a model, opens a guest, or spends anything.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from core.agentic_compute import (
    MAX_DEPTH,
    MAX_INPUT_FILES,
    MAX_INPUT_SINGLE,
    MAX_INPUT_TOTAL,
    MAX_PATH_BYTES,
    _open_regular_beneath_nofollow,
    _sha256_descriptor,
    _source_identity,
)

STAGING_SCHEMA_VERSION = "agentic-v2-reference-staging-v1"

#: Where a staged file appears from the model's point of view.
#:
#: The same prefix V1's merkle records use, so a path quoted in a V2 record
#: means the same thing as one quoted in a V1 record.
MODEL_INPUT_PREFIX = "inputs"

#: Why a file was not delivered.
#:
#: Short, stable strings rather than free prose, because these are counted and
#: grouped across 220 tasks and a sentence that varies cannot be. The detail
#: field beside them carries the specifics.
TOO_LARGE = "larger_than_the_single_file_limit"
TOO_MANY = "task_names_more_files_than_the_limit_allows"
TOTAL_TOO_LARGE = "task_total_would_exceed_the_input_limit"
NOT_IN_SNAPSHOT = "not_present_in_the_pinned_snapshot"
UNSAFE_PATH = "path_is_not_a_safe_relative_component"
NOT_A_PLAIN_FILE = "source_is_a_link_or_not_a_single_link_regular_file"
CHANGED_WHILE_COPYING = "source_changed_while_it_was_being_copied"
SNAPSHOT_IS_A_LINK_FARM = "snapshot_root_is_a_huggingface_cache_of_symlinks"

#: What to do about it, said once, where the refusal is raised.
#:
#: Measured on this repository's own pinned snapshot: **301 of 301** files under
#: ``reference_files/`` are symlinks and none is a regular file. That is not
#: corruption, it is how ``huggingface_hub`` stores a cache — the snapshot tree
#: is names, the bytes live once in a sibling ``blobs/`` directory, and every
#: name points at them with a relative link that climbs *out* of the snapshot
#: root.
#:
#: Two things follow, and both are easy to get wrong. Anything opened with
#: ``O_NOFOLLOW`` — which is everything in this module and in
#: :mod:`core.agentic_input_manifest` — refuses all 301 files. And "resolve the
#: link, then check it is beneath the root" does not rescue it either, because
#: the target genuinely is not beneath the root. So the fix is not to relax the
#: opener. It is to ask for the bytes instead of the names, which ``hf
#: download --local-dir`` does: the same command against the same revision then
#: writes real files.
#:
#: Worth the paragraph because the generic refusal for this is "source is a
#: link", which reads as a planted link and a security finding rather than as
#: the ordinary shape of an ordinary cache.
LINK_FARM_DETAIL = (
    "the snapshot root is a huggingface_hub cache, whose files are symlinks "
    "into a sibling blobs/ directory outside the root. Nothing is wrong with "
    "it and nothing here will follow it. Fetch with `hf download ... "
    "--local-dir <dir>` against the same revision, which writes the bytes, and "
    "stage from that directory."
)


@dataclass(frozen=True)
class StagedFile:
    """One file that arrived, with what it is."""

    relative_path: str
    size_bytes: int
    sha256: str

    @property
    def model_path(self) -> str:
        return f"{MODEL_INPUT_PREFIX}/{self.relative_path}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "model_path": self.model_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class RefusedFile:
    """One file that did not arrive, and why — by name, never as a count."""

    relative_path: str
    reason: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class TaskStaging:
    """What one task was actually given, and what it was not."""

    task_id: str
    workspace: str
    delivered: tuple[StagedFile, ...]
    refused: tuple[RefusedFile, ...]

    @property
    def named(self) -> int:
        return len(self.delivered) + len(self.refused)

    @property
    def everything_arrived(self) -> bool:
        """True only when the task needed files and got all of them.

        A task naming no files is not "complete" here; it is a task the whole
        question does not apply to. Merging the two would let a stage of tasks
        with no inputs report as fully staged.
        """
        return bool(self.delivered) and not self.refused

    @property
    def ran_without_its_inputs(self) -> bool:
        """The condition a result must be read in the light of."""
        return bool(self.refused)

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "workspace": self.workspace,
            "files_named": self.named,
            "delivered": [one.as_dict() for one in self.delivered],
            "refused": [one.as_dict() for one in self.refused],
            "everything_arrived": self.everything_arrived,
        }


def snapshot_problem(snapshot_root: str | Path) -> str | None:
    """Whether a root can be staged from at all, answered before 220 tasks try.

    Per-file refusal is right for a file, and wrong for a root: a cache of
    symlinks produces the same refusal 261 times and looks like 125 broken
    tasks rather than one wrong directory. This is the question asked once, by
    whoever is about to stage, so the answer arrives before the work does.

    Returns ``None`` when the root looks stageable. Deliberately cheap: it
    looks at the shape of ``reference_files/`` rather than reading anything.
    """
    root = Path(snapshot_root)
    if not root.is_dir():
        return f"{root} is not a directory"

    references = root / "reference_files"
    if not references.is_dir():
        return (
            f"{references} does not exist, so no task can be given its inputs "
            "from here. Fetch the dataset with `--local-dir` pointed at the "
            "root being staged from."
        )

    links = 0
    plain = 0
    for path in references.rglob("*"):
        if path.is_symlink():
            links += 1
        elif path.is_file():
            plain += 1
        if links and plain:
            break

    if links and not plain:
        return (
            f"every file under {references} is a symlink ({links} seen and no "
            f"regular file): {LINK_FARM_DETAIL}"
        )
    if not links and not plain:
        return f"{references} holds no files"
    return None


def _unsafe_reason(relative: Path) -> str | None:
    """Whether a dataset-supplied path may be joined onto a destination.

    The same conditions V1 refuses on, kept identical on purpose: this decides
    where bytes get written, and two staging paths that disagree about what a
    safe path is would be a gap nobody notices until one of them is used.
    """
    if relative.is_absolute():
        return "path is absolute"
    if not relative.parts:
        return "path is empty"
    if ".." in relative.parts:
        return "path climbs out of the tree"
    if any(part.startswith(".") for part in relative.parts):
        return "path has a hidden component"
    if len(relative.parts) > MAX_DEPTH:
        return f"path is deeper than {MAX_DEPTH}"
    if len(relative.as_posix().encode("utf-8")) > MAX_PATH_BYTES:
        return f"path is longer than {MAX_PATH_BYTES} bytes"
    return None


class _CannotCopy(Exception):
    """A copy that stopped, carrying which refusal it is.

    One exception type with a ``reason`` on it rather than several types, or a
    bare ``ValueError`` sorted out by the caller. The first version did the
    latter, and it quietly labelled a file with a second hard link as
    ``source_changed_while_it_was_being_copied`` — a record asserting a race
    that never happened, in the one module whose purpose is that a record can be
    read against a result. The reason travels with the refusal so the two cannot
    drift apart.
    """

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _copy_one(
    *, snapshot_root: Path, relative: Path, destination: Path
) -> StagedFile:
    """Copy one file, or raise :class:`_CannotCopy` saying which refusal it is.

    Opened beneath the snapshot root with ``O_NOFOLLOW`` at every component, so
    a link planted in the dataset cannot redirect the read. Hashed while being
    copied, then the source is checked twice more — its identity and its digest
    — because a file that changed halfway through produces a destination that
    matches neither version and would otherwise be indistinguishable from a
    clean copy.
    """
    try:
        descriptor = _open_regular_beneath_nofollow(snapshot_root, relative)
    except OSError as exc:
        raise _CannotCopy(
            NOT_A_PLAIN_FILE,
            f"could not be opened without following a link: "
            f"{errno.errorcode.get(exc.errno, exc.errno)} {exc.strerror}",
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise _CannotCopy(NOT_A_PLAIN_FILE, "source is not a regular file")
        if before.st_nlink != 1:
            raise _CannotCopy(
                NOT_A_PLAIN_FILE,
                f"source has {before.st_nlink} hard links, so another name for "
                "the same bytes could change them between the check and the read",
            )
        if before.st_size > MAX_INPUT_SINGLE:
            raise _CannotCopy(
                TOO_LARGE,
                f"{before.st_size} bytes is over the {MAX_INPUT_SINGLE} byte limit",
            )
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with os.fdopen(os.dup(descriptor), "rb") as source, destination.open(
            "xb"
        ) as sink:
            for chunk in iter(lambda: source.read(65536), b""):
                digest.update(chunk)
                sink.write(chunk)
        after = os.fstat(descriptor)
        if _source_identity(after) != _source_identity(before):
            raise _CannotCopy(
                CHANGED_WHILE_COPYING, "source identity changed during the copy"
            )
        if _sha256_descriptor(descriptor) != digest.hexdigest():
            raise _CannotCopy(
                CHANGED_WHILE_COPYING, "source contents changed during the copy"
            )
    finally:
        os.close(descriptor)
    return StagedFile(
        relative_path=relative.as_posix(),
        size_bytes=before.st_size,
        sha256=digest.hexdigest(),
    )


def stage_task_reference_files(
    *,
    task_id: str,
    reference_files: Sequence[Any],
    snapshot_root: str | Path,
    into: str | Path,
) -> TaskStaging:
    """Give one task its files, and say exactly what it did not get.

    Never raises for a file it cannot deliver. A task that names twenty files
    and can be given nineteen is given nineteen, and the twentieth is in the
    record by name — which is the whole point, because the alternative is a task
    that quietly ran short.
    """
    snapshot_root = Path(snapshot_root).resolve()
    workspace = Path(into).resolve()
    workspace.mkdir(mode=0o700, parents=True, exist_ok=True)

    delivered: list[StagedFile] = []
    refused: list[RefusedFile] = []
    running_total = 0

    named = [str(one) for one in (reference_files or [])]
    over_the_count = named[MAX_INPUT_FILES:]
    for path in over_the_count:
        refused.append(
            RefusedFile(
                relative_path=path,
                reason=TOO_MANY,
                detail=(
                    f"the task names {len(named)} files and the limit is "
                    f"{MAX_INPUT_FILES}"
                ),
            )
        )

    for raw in named[:MAX_INPUT_FILES]:
        relative = Path(raw)
        unsafe = _unsafe_reason(relative)
        if unsafe is not None:
            refused.append(
                RefusedFile(relative_path=raw, reason=UNSAFE_PATH, detail=unsafe)
            )
            continue

        source = snapshot_root / relative
        if source.is_symlink():
            # Checked before `is_file`, which follows the link and would report
            # a file that this module will then refuse to open -- the confusing
            # pair of answers that cost the first attempt at this an hour.
            refused.append(
                RefusedFile(
                    relative_path=relative.as_posix(),
                    reason=SNAPSHOT_IS_A_LINK_FARM,
                    detail=LINK_FARM_DETAIL,
                )
            )
            continue
        if not source.is_file():
            refused.append(
                RefusedFile(
                    relative_path=relative.as_posix(),
                    reason=NOT_IN_SNAPSHOT,
                    detail=f"no file at {relative.as_posix()} under the snapshot root",
                )
            )
            continue

        size = source.stat().st_size
        if size > MAX_INPUT_SINGLE:
            refused.append(
                RefusedFile(
                    relative_path=relative.as_posix(),
                    reason=TOO_LARGE,
                    detail=(
                        f"{size} bytes, over the {MAX_INPUT_SINGLE} byte "
                        "single-file limit. Delivering it would mean choosing "
                        "what the model gets instead, which changes what the "
                        "task measures."
                    ),
                )
            )
            continue
        if running_total + size > MAX_INPUT_TOTAL:
            refused.append(
                RefusedFile(
                    relative_path=relative.as_posix(),
                    reason=TOTAL_TOO_LARGE,
                    detail=(
                        f"{running_total + size} bytes would pass the "
                        f"{MAX_INPUT_TOTAL} byte total for one task"
                    ),
                )
            )
            continue

        destination = workspace / relative
        try:
            staged = _copy_one(
                snapshot_root=snapshot_root,
                relative=relative,
                destination=destination,
            )
        except _CannotCopy as exc:
            # Whatever landed before the refusal is removed. A short file left
            # in the workspace is worse than no file: the model opens it, reads
            # it as the whole thing, and the record says it was refused.
            destination.unlink(missing_ok=True)
            refused.append(
                RefusedFile(
                    relative_path=relative.as_posix(),
                    reason=exc.reason,
                    detail=exc.detail,
                )
            )
            continue

        running_total += staged.size_bytes
        delivered.append(staged)

    return TaskStaging(
        task_id=task_id,
        workspace=str(workspace),
        delivered=tuple(delivered),
        refused=tuple(refused),
    )


def stage_cohort(
    *,
    tasks: Iterable[Any],
    snapshot_root: str | Path,
    into: str | Path,
) -> tuple[TaskStaging, ...]:
    """Stage every task in a bound cohort, each into its own directory.

    Per task rather than per cohort, because the tasks do not share a workspace
    and because a file that one task may open is not a file every task may open.
    The directory is named by the task id's digest for the same reason V1 does
    it: a task id is dataset-supplied and a directory name is a filesystem
    decision, and the two should not be the same string.
    """
    into = Path(into)
    return tuple(
        stage_task_reference_files(
            task_id=task.task_id,
            reference_files=getattr(task, "reference_files", ()) or (),
            snapshot_root=snapshot_root,
            into=into
            / hashlib.sha256(str(task.task_id).encode("utf-8")).hexdigest(),
        )
        for task in tasks
    )


def staging_record(stagings: Sequence[TaskStaging]) -> dict[str, Any]:
    """What the run record carries about which tasks got their inputs.

    Replaces the flat ``reference_file_bytes_are_in_the_guest: False`` that
    :func:`core.agentic_v2_manifest_binding.unmet_needs` writes today. That
    field was honest when nothing was staged; once something is, a single
    boolean for a whole cohort is the field most likely to be read as "all of
    them" or "none of them" when the truth is "most".

    The summary counts are for a reader skimming. The per-task detail underneath
    is what a result gets read against, and it is not summarised away: every
    refused file appears by name.
    """
    stagings = list(stagings)
    needed = [one for one in stagings if one.named]
    short = [one for one in needed if one.ran_without_its_inputs]
    reasons: dict[str, int] = {}
    for one in stagings:
        for refusal in one.refused:
            reasons[refusal.reason] = reasons.get(refusal.reason, 0) + 1

    return {
        "schema_version": STAGING_SCHEMA_VERSION,
        "tasks_seen": len(stagings),
        "tasks_naming_reference_files": len(needed),
        "tasks_given_everything_they_named": len(needed) - len(short),
        "tasks_that_ran_without_some_input": len(short),
        "files_delivered": sum(len(one.delivered) for one in stagings),
        "bytes_delivered": sum(
            file.size_bytes for one in stagings for file in one.delivered
        ),
        "refusals_by_reason": dict(sorted(reasons.items())),
        "what_that_means": (
            f"{len(needed) - len(short)} of {len(needed)} tasks that name "
            "reference files were given all of them. "
            f"{len(short)} were not, and each missing file is named below. A "
            "failure on one of those is not evidence about the model."
        ),
        "tasks": [one.as_dict() for one in stagings],
    }


__all__ = [
    "CHANGED_WHILE_COPYING",
    "LINK_FARM_DETAIL",
    "MODEL_INPUT_PREFIX",
    "NOT_A_PLAIN_FILE",
    "NOT_IN_SNAPSHOT",
    "SNAPSHOT_IS_A_LINK_FARM",
    "STAGING_SCHEMA_VERSION",
    "RefusedFile",
    "StagedFile",
    "TOO_LARGE",
    "TOO_MANY",
    "TOTAL_TOO_LARGE",
    "TaskStaging",
    "UNSAFE_PATH",
    "snapshot_problem",
    "stage_cohort",
    "stage_task_reference_files",
    "staging_record",
]
