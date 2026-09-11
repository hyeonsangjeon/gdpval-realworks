"""Getting the guest's files onto the host, or not pretending they are there.

``finalize`` ends a V2 task by naming the files the model considers its answer.
By the time the run record exists those bytes are already in memory and already
checked against the digests the guest declared — that is
``verify_agentic_v2_terminal_result`` in :mod:`core.agentic_v2_provenance`, and
it is not repeated here. What has never existed is the other half: putting them
on the host, in the layout the submission pipeline reads, in a way that cannot
leave a half-written answer behind.

**Why a half-written collection is the failure worth designing against.** A task
with five deliverables that writes three and then meets a full disk leaves a
directory that looks exactly like a finished task with three deliverables.
Nothing downstream can tell the difference: ``fill_parquet`` reads the paths,
``step5_validate`` checks they exist, and the submission goes out short. So the
files are written into a staging directory named after the attempt, every one is
read back and re-hashed, and only then is the directory moved into place. An
interrupted collection leaves a ``.collecting-…`` directory that is obviously
not a result.

**Why the bytes are hashed again after they are written.** They were hashed
coming out of the guest. Hashing them again after the write is asking a
different question: not *did the guest produce this*, but *is this what is on the
host's disk now*. A short write, a filesystem that silently truncates, and a
disk that filled between two files all produce a file that exists and is wrong.
One extra pass over at most 64 MiB is the only way to know, and the cost of not
knowing is a corrupt deliverable submitted under a clean name.

**Why the model's directory structure is kept.** ``finalize`` takes workspace-
relative paths, and the contract already guarantees they are unique within one
call. Flattening them to basenames would turn ``analysis/summary.xlsx`` and
``raw/summary.xlsx`` into one file, and the loss would look like a model that
produced fewer deliverables than it did. The structure is carried across
unchanged, under ``deliverable_files/<task_id>/``.

**Why an existing directory is refused rather than replaced.** A second
collection for a task that already has one means either a retry after an
abandoned attempt or a bug, and those want opposite handling. Refusing makes the
caller say which: :func:`discard_previous_collection` exists so that overwriting
a previous attempt's answer is always a line somebody wrote on purpose.

Nothing here runs a model, boots a guest, or decides whether a task succeeded.
It is handed a verified result and it either puts it on disk completely or
leaves nothing behind.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from core.agentic_v2_contract import canonical_relative_path


DELIVERABLE_ROOT = "deliverable_files"
"""The directory name the submission parquet's paths are relative to.

Fixed by ``fill_parquet`` and the dataset layout, not by this module.
"""

MOST_BYTES_IN_ONE_COLLECTION = 64 * 1024 * 1024
"""The ceiling this enforces for itself.

The backend enforces the same figure when it reads the files out of the
workspace. Checking it again here is not redundancy for its own sake: this is
the module that writes to the host's disk, and a writer that trusts a limit
applied somewhere else has no limit at all if that somewhere else changes.
"""

STAGING_PREFIX = ".collecting-"
"""What an interrupted collection leaves behind, so it cannot be mistaken.

A directory under this name is not a result and no reader treats it as one.
"""


class CollectionRefused(RuntimeError):
    """The deliverables were not collected, and nothing was left on disk."""


@dataclass(frozen=True)
class CollectedDeliverable:
    """One file, where the model put it and where it now is."""

    #: Repo-relative, in the form the submission parquet stores.
    submission_path: str
    #: What ``finalize`` called it, inside the guest's workspace.
    workspace_path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class Collection:
    """Everything one task's ``finalize`` produced, now on the host."""

    task_id: str
    directory: Path
    deliverables: tuple[CollectedDeliverable, ...]

    def submission_paths(self) -> list[str]:
        """The value the pipeline's ``deliverable_files`` field takes."""
        return [item.submission_path for item in self.deliverables]

    def journal_entries(self) -> list[dict[str, Any]]:
        """The shape :meth:`core.agentic_v2_task_journal.TaskJournal.close_task`
        records — a path with the digest and size that were verified for it."""
        return [
            {
                "path": item.submission_path,
                "sha256": item.sha256,
                "size": item.size,
            }
            for item in self.deliverables
        ]

    def total_bytes(self) -> int:
        return sum(item.size for item in self.deliverables)


def _task_directory_name(task_id: str) -> str:
    """The task's own directory under ``deliverable_files``.

    Validated as a single path component rather than trusted: a task id with a
    slash in it would otherwise write one level up, and task ids come from a
    dataset this repository does not own.
    """
    name = str(task_id)
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise CollectionRefused(
            f"task id {task_id!r} is not usable as a directory name"
        )
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in name):
        raise CollectionRefused(f"task id {task_id!r} holds a control character")
    return name


def _files_from(result: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    if not isinstance(result, Mapping):
        raise CollectionRefused("a result to collect from must be a mapping")
    if result.get("success") is not True:
        raise CollectionRefused(
            "only a successful run has deliverables to collect; a failed one is "
            "recorded by its error, not by an empty directory"
        )
    files = result.get("files")
    if not isinstance(files, Sequence) or isinstance(files, (str, bytes)):
        raise CollectionRefused("a result's files must be a list")
    if not files:
        raise CollectionRefused(
            "a successful run with no files did not finalize anything, and an "
            "empty collection would be indistinguishable from a lost one"
        )
    return files


def _write_one(
    *,
    staging: Path,
    relative: str,
    content: bytes,
) -> None:
    """Write one file under the staging directory, refusing a link or a repeat."""
    target = staging / PurePosixPath(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        descriptor = os.open(str(target), flags, 0o644)
    except FileExistsError:
        raise CollectionRefused(
            f"two deliverables both want {relative!r}; one would silently "
            "replace the other"
        ) from None
    except OSError as error:
        raise CollectionRefused(f"could not write {relative!r}: {error}") from None
    try:
        written = 0
        while written < len(content):
            written += os.write(descriptor, content[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _verify_on_disk(staging: Path, relative: str, expected: str, size: int) -> None:
    """Read back what was just written and insist it is the same file."""
    target = staging / PurePosixPath(relative)
    digest = hashlib.sha256()
    seen = 0
    with open(target, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            seen += len(chunk)
            digest.update(chunk)
    if seen != size or digest.hexdigest() != expected:
        raise CollectionRefused(
            f"{relative!r} is not on disk as it came out of the guest "
            f"({seen} bytes, {digest.hexdigest()[:12]}…, expected {size} bytes, "
            f"{expected[:12]}…)"
        )


def collect_deliverables(
    result: Mapping[str, Any],
    *,
    task_id: str,
    into: str | Path,
    attempt_name: str,
) -> Collection:
    """Put one task's deliverables on the host, completely or not at all.

    ``attempt_name`` names the staging directory and must be unique per
    attempt; :func:`core.agentic_v2_task_journal.workspace_name_for` produces
    exactly such a name, which is why the two are meant to be used together. A
    reused name would let a second attempt write into the first one's staging
    directory and inherit its files.
    """
    files = _files_from(result)
    root = Path(into) / DELIVERABLE_ROOT
    directory = root / _task_directory_name(task_id)
    if directory.exists():
        raise CollectionRefused(
            f"{directory} already holds a collection for this task; clear it "
            "with discard_previous_collection if replacing it is intended"
        )
    if not attempt_name or "/" in attempt_name or attempt_name.startswith("."):
        raise CollectionRefused(f"attempt name {attempt_name!r} is not usable")

    staging = root / f"{STAGING_PREFIX}{attempt_name}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    collected: list[CollectedDeliverable] = []
    total = 0
    try:
        for entry in files:
            if not isinstance(entry, Mapping):
                raise CollectionRefused("a file entry must be a mapping")
            content = entry.get("content")
            if not isinstance(content, bytes):
                raise CollectionRefused(
                    "a deliverable's content must be bytes; text would have "
                    "been decoded somewhere and a spreadsheet does not survive "
                    "that"
                )
            try:
                relative = canonical_relative_path(entry.get("filename"))
            except ValueError as error:
                raise CollectionRefused(
                    f"deliverable path {entry.get('filename')!r} is not a "
                    f"canonical relative path: {error}"
                ) from None
            if relative == ".":
                raise CollectionRefused("a deliverable cannot be the directory")
            total += len(content)
            if total > MOST_BYTES_IN_ONE_COLLECTION:
                raise CollectionRefused(
                    f"this task's deliverables exceed "
                    f"{MOST_BYTES_IN_ONE_COLLECTION} bytes"
                )
            digest = hashlib.sha256(content).hexdigest()
            _write_one(staging=staging, relative=relative, content=content)
            _verify_on_disk(staging, relative, digest, len(content))
            collected.append(
                CollectedDeliverable(
                    submission_path=(
                        f"{DELIVERABLE_ROOT}/{_task_directory_name(task_id)}/"
                        f"{relative}"
                    ),
                    workspace_path=relative,
                    sha256=digest,
                    size=len(content),
                )
            )

        directory.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, directory)
    except BaseException:
        # Including KeyboardInterrupt: a staging directory left where a result
        # belongs is exactly the confusion this module exists to prevent.
        shutil.rmtree(staging, ignore_errors=True)
        raise

    _fsync_directory(directory.parent)
    return Collection(
        task_id=str(task_id),
        directory=directory,
        deliverables=tuple(collected),
    )


def _fsync_directory(where: Path) -> None:
    descriptor = os.open(str(where), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def discard_previous_collection(into: str | Path, task_id: str) -> bool:
    """Remove a task's collected deliverables, deliberately.

    Returns whether there was anything to remove. Separate from
    :func:`collect_deliverables` so that throwing away a previous attempt's
    answer is never something that happens as a side effect of retrying.
    """
    directory = Path(into) / DELIVERABLE_ROOT / _task_directory_name(task_id)
    if not directory.exists():
        return False
    if not directory.is_dir():
        raise CollectionRefused(f"{directory} is not a directory")
    shutil.rmtree(directory)
    return True


def abandoned_collections(into: str | Path) -> list[Path]:
    """Staging directories left by collections that were interrupted.

    Worth reporting rather than cleaning silently: each one is a task that
    spent money and produced files that never reached the submission, and that
    is a line in the run's account of itself.
    """
    root = Path(into) / DELIVERABLE_ROOT
    if not root.is_dir():
        return []
    return sorted(
        child
        for child in root.iterdir()
        if child.is_dir() and child.name.startswith(STAGING_PREFIX)
    )
