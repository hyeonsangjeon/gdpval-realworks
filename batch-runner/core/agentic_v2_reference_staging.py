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
from core.agentic_v2_fixture_backend import _MAX_FILE_BYTES
from core.file_reader import get_supported_extensions, read_reference_file

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
TOO_LARGE_FOR_THE_WORKSPACE = "larger_than_the_workspace_file_limit"
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

#: The biggest file the fixture workspace can hold, read from the code that
#: enforces it.
#:
#: Imported rather than written down, and imported past the underscore on
#: purpose. That name is what :meth:`AgenticV2FixtureBackend._read_bytes`
#: measures every file against while it walks the workspace, so it is the only
#: number that is true by construction. A copy here would be a second number to
#: keep correct, and the day it drifted this module would stage files the
#: backend then refused.
#:
#: The limit matters far more than its size suggests, because of *where* the
#: backend applies it. It is not a read limit on the file the model asked for;
#: the walk reads every regular file under the workspace root, so one oversized
#: file makes the walk raise, and the walk runs on ``write``. Measured on this
#: repository's own fixture backend: a 900 KiB input leaves ``list``, ``read``
#: and ``write`` all working, and a 2 MiB input leaves ``list`` and ``read``
#: working and makes ``write`` raise. A task staged that way can look at its
#: inputs and can never save a deliverable.
#:
#: That failure is also invisible from inside the loop. The dispatcher turns any
#: exception into ``{"ok": False, "error_type": "fixture_backend_error"}``, so
#: the model is told only that something went wrong, tries again, and spends its
#: whole call budget on writes that cannot succeed. The record would show a model
#: that produced nothing.
WORKSPACE_FILE_LIMIT = _MAX_FILE_BYTES

#: Where a text rendering of a file appears, beneath the inputs prefix.
EXTRACTION_PREFIX = "extracted"

#: What came of trying to render one file as text.
#:
#: Separate strings rather than a boolean, because "no rendering" covers four
#: quite different situations and only one of them is a defect. Counting them
#: together would hide the one that is.
EXTRACTION_IS_TEXT = "text_was_read_out_of_it"
EXTRACTION_IS_A_LABEL = "the_reader_describes_this_kind_rather_than_reading_it"
EXTRACTION_IS_EMPTY = "the_reader_found_no_text_in_it"
EXTRACTION_TRUNCATED = "text_was_read_out_of_it_and_cut_to_the_workspace_limit"
EXTRACTION_FAILED = "the_reader_could_not_open_it"

#: The name of the one file in the workspace that says what the others are.
INPUTS_GUIDE = "INPUTS.md"


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
class ExtractedText:
    """What a text rendering of one file came to, including nothing.

    A rendering is not the file and is never described as one. It is what this
    repository's own reader — :func:`core.file_reader.read_reference_file`, the
    same one V1 puts in its prompts — could get out of the bytes. For a
    spreadsheet that is the cells; for a photograph it is the word "photograph"
    and its pixel dimensions, which is a label rather than a rendering and is
    recorded as one.

    The reason to keep all four outcomes apart is that only one of them is a
    defect. A ``.png`` yielding no text is the format; a ``.pdf`` yielding no
    text is a scan, and a task that needs it read is a task nobody can do here.
    Counting them together would report nine images and five scans as fourteen
    unreadable files and lose which five mattered.
    """

    relative_path: str
    outcome: str
    characters: int
    label: str = ""
    written_to: str | None = None

    @property
    def model_path(self) -> str | None:
        """Where the model finds it, or ``None`` when nothing was written."""
        if self.written_to is None:
            return None
        return f"{MODEL_INPUT_PREFIX}/{self.written_to}"

    @property
    def is_readable(self) -> bool:
        return self.outcome in (EXTRACTION_IS_TEXT, EXTRACTION_TRUNCATED)

    def as_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "outcome": self.outcome,
            "characters": self.characters,
            "label": self.label,
            "model_path": self.model_path,
        }


@dataclass(frozen=True)
class TaskStaging:
    """What one task was actually given, and what it was not."""

    task_id: str
    workspace: str
    delivered: tuple[StagedFile, ...]
    refused: tuple[RefusedFile, ...]
    extractions: tuple[ExtractedText, ...] = ()
    guide: str | None = None

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

    @property
    def could_open_nothing(self) -> bool:
        """Files arrived and not one of them can be opened.

        Worth its own name because it is the state most easily mistaken for a
        lazy model. The task is handed a directory, the directory has files in
        it, every attempt to read one comes back as an error, and the answer is
        written from the prompt alone.

        Answered from the renderings, so it is ``False`` where none was
        attempted. That is a limit of the field rather than a claim: without a
        rendering pass nothing here has opened anything, and a run that reports
        this as ``False`` for every task should be checked for having asked for
        renderings at all.
        """
        if not self.delivered or not self.extractions:
            return False
        return not any(one.is_readable for one in self.extractions)

    @property
    def worked_from_the_prompt_alone(self) -> bool:
        """The task named files and not one readable character reached it.

        A superset of :attr:`could_open_nothing`, and the reason it exists is
        that the subset reads as reassurance where it is least deserved.
        ``could_open_nothing`` asks its question of the files that arrived, so a
        task whose every file was refused has no files to ask about and comes
        back ``False`` -- the same answer given by a task that got everything
        and read it fine. Six of the 220 are in exactly that position: every
        file refused for size, nothing delivered, and the summary saying no.

        True here means the model had the prompt and nothing else, however it
        got there. That is the whole question a result needs answering, because
        a thin answer to a task in this state is the environment's, and reading
        it as the model's would be reading a fault we introduced as a finding
        about the thing under test.
        """
        if not self.named:
            return False
        return not any(one.is_readable for one in self.extractions)

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "workspace": self.workspace,
            "files_named": self.named,
            "delivered": [one.as_dict() for one in self.delivered],
            "refused": [one.as_dict() for one in self.refused],
            "extractions": [one.as_dict() for one in self.extractions],
            "guide": self.guide,
            "everything_arrived": self.everything_arrived,
            "could_open_nothing": self.could_open_nothing,
            "worked_from_the_prompt_alone": self.worked_from_the_prompt_alone,
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


def _make_directory_0700(directory: Path) -> None:
    """Create ``directory`` and any missing parent, each one at 0o700.

    ``Path.mkdir(mode=..., parents=True)`` applies the mode to the last
    component only; every parent it has to create takes the process umask
    instead, which is 0o755 in the usual case. That is invisible until the
    provenance replay runs, because it models every workspace directory as
    0o700: a staged tree with 0o755 halfway down describes a starting state
    whose digest the replay cannot reproduce, and the task is thrown away
    after it has already been worked. Walk the chain and set each mode here,
    with an explicit chmod so the umask cannot take bits off either.
    """
    missing: list[Path] = []
    current = directory
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    for one in reversed(missing):
        one.mkdir(exist_ok=True)
        one.chmod(0o700)


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
        _make_directory_0700(destination.parent)
        digest = hashlib.sha256()
        with os.fdopen(os.dup(descriptor), "rb") as source, destination.open(
            "xb"
        ) as sink:
            for chunk in iter(lambda: source.read(65536), b""):
                digest.update(chunk)
                sink.write(chunk)
        # 0o600 to match what the fixture backend gives a file the model
        # writes, and so what the provenance replay models for every file it
        # holds. A staged file left at the umask default describes a workspace
        # whose state digest no re-derivation can reproduce.
        os.chmod(destination, 0o600)
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


#: Room left under the workspace limit for the note that says text was cut.
_TRUNCATION_ROOM = 512

#: How the reader reports a file it recognised and then could not open.
#:
#: :func:`core.file_reader.read_reference_file` swallows the exception and hands
#: back this sentence as though it were the document. Harmless where it was
#: written — a prompt reader shows it to a person — and not harmless here, where
#: the string would be written into the workspace as the file's rendering and the
#: model would read "[Error reading x.xlsx: ...]" as the contents of x.xlsx.
#:
#: Matched on rather than caught, because there is nothing to catch. That makes
#: this a dependency on a detail of another module's behaviour, which is exactly
#: the kind of thing that changes without anyone noticing, so
#: ``test_the_reader_still_swallows`` runs the reader against a corrupt file and
#: fails if it ever starts raising instead.
_READER_ERROR_PREFIX = "[Error reading "


def _extract_one(
    *,
    source: Path,
    relative: Path,
    workspace: Path,
    limit: int,
) -> ExtractedText:
    """Render one file as text beside it, or say why there is no rendering.

    Never raises. A file that cannot be rendered is a file the model will have
    to work without, which is a fact about the run to be recorded rather than an
    error to be handled — the task still goes ahead, and the record carries what
    it went ahead without.
    """
    suffix = relative.suffix.lower()
    mode = get_supported_extensions().get(suffix)
    if mode != "text":
        # A photograph, a recording, an archive. The reader has a sentence for
        # each and that sentence is worth carrying, but it is a label and is
        # never written into the workspace as if it were the file's contents.
        try:
            label = read_reference_file(str(source)).strip()
        except Exception as exc:  # pragma: no cover - the reader swallows
            label = f"{type(exc).__name__}"
        return ExtractedText(
            relative_path=relative.as_posix(),
            outcome=EXTRACTION_IS_A_LABEL,
            characters=0,
            label=label[:200],
        )

    try:
        text = read_reference_file(str(source))
    except Exception as exc:  # pragma: no cover - the reader swallows
        return ExtractedText(
            relative_path=relative.as_posix(),
            outcome=EXTRACTION_FAILED,
            characters=0,
            label=f"{type(exc).__name__}: {exc}"[:200],
        )

    if text.startswith(_READER_ERROR_PREFIX):
        return ExtractedText(
            relative_path=relative.as_posix(),
            outcome=EXTRACTION_FAILED,
            characters=0,
            label=text.strip()[:200],
        )
    if not text.strip():
        # The five scanned PDFs in the pinned revision land here. Writing an
        # empty file would be the worst of the options: the model opens it,
        # reads nothing, and concludes the document is blank rather than that
        # it is a picture of a document.
        return ExtractedText(
            relative_path=relative.as_posix(),
            outcome=EXTRACTION_IS_EMPTY,
            characters=0,
            label="the reader opened it and found no text",
        )

    encoded = text.encode("utf-8")
    outcome = EXTRACTION_IS_TEXT
    if len(encoded) > limit - _TRUNCATION_ROOM:
        # Cut on bytes, because bytes are what the backend counts, and then
        # back to a character boundary so the file is still valid UTF-8.
        encoded = encoded[: limit - _TRUNCATION_ROOM]
        text = encoded.decode("utf-8", errors="ignore")
        text += (
            f"\n\n[This rendering was cut here to stay under the "
            f"{limit} byte workspace file limit. The original file is longer.]\n"
        )
        outcome = EXTRACTION_TRUNCATED

    written = Path(EXTRACTION_PREFIX) / relative.with_suffix(relative.suffix + ".txt")
    destination = workspace / written
    _make_directory_0700(destination.parent)
    destination.write_text(text, encoding="utf-8")
    destination.chmod(0o600)
    return ExtractedText(
        relative_path=relative.as_posix(),
        outcome=outcome,
        characters=len(text),
        label="",
        written_to=written.as_posix(),
    )


def _write_inputs_guide(
    *,
    workspace: Path,
    delivered: Sequence[StagedFile],
    refused: Sequence[RefusedFile],
    extractions: Sequence[ExtractedText],
) -> str:
    """Write the one file that says what the others are, and return its name.

    Needed because nothing else tells the model its inputs exist. The task
    wording comes from the dataset and is sealed against edits by
    :mod:`core.agentic_v2_manifest_binding`, so it cannot be the carrier; it
    describes work, not a directory layout. Without this the files are staged
    into a path the model has never been given and has no reason to guess.

    A file rather than more prompt on purpose. It costs nothing per turn, it can
    say more than a system message reasonably should, and a model that never
    opens it is a fact the tool log records — which a sentence in the prompt
    would not be.
    """
    renderings = {one.relative_path: one for one in extractions}
    lines = [
        "# Your input files",
        "",
        "These are the files the task refers to. They were copied here before",
        "you started. Paths are relative to your working directory.",
        "",
    ]
    if not delivered and not refused:
        # Written anyway, and this is the whole reason the guide is
        # unconditional. The standing instructions tell the model to open this
        # file first; when it was skipped for a task that names nothing, that
        # read came back `ok: False`, and one failed tool call ends a task --
        # see `dispatch_one` in core.agentic_v2_runner. So every task that
        # names no files died on turn one, three attempts each, against an
        # environment defect that would have read as the model failing. How
        # many that is is counted from the catalogue in
        # tests/test_agentic_v2_reference_staging.py rather than written here:
        # the figure in this comment was wrong for a day and nothing noticed.
        lines.append("## This task names no files")
        lines.append("")
        lines.append(
            "It is not that they are missing: the dataset lists none for this"
        )
        lines.append(
            "task. Nothing was lost on the way here and there is nothing to go"
        )
        lines.append(
            "looking for. Do the task from its wording, and write your answer"
        )
        lines.append("into this directory.")
        lines.append("")
    if delivered:
        lines.append("## Files you have")
        lines.append("")
        for one in sorted(delivered, key=lambda f: f.relative_path):
            rendered = renderings.get(one.relative_path)
            lines.append(f"- `{one.model_path}` — {one.size_bytes:,} bytes")
            if rendered is not None and rendered.model_path:
                lines.append(
                    f"  - text version: `{rendered.model_path}`"
                    + (
                        " (cut short)"
                        if rendered.outcome == EXTRACTION_TRUNCATED
                        else ""
                    )
                )
            elif rendered is not None and rendered.label:
                lines.append(f"  - no text version: {rendered.label}")
        lines.append("")
    if refused:
        lines.append("## Files the task names that are not here")
        lines.append("")
        for one in sorted(refused, key=lambda f: f.relative_path):
            rendered = renderings.get(one.relative_path)
            lines.append(f"- `{one.relative_path}` — {one.reason}")
            if rendered is not None and rendered.model_path:
                lines.append(
                    f"  - a text version is here instead: `{rendered.model_path}`"
                )
            elif rendered is not None and rendered.label:
                lines.append(f"  - {rendered.label}")
        lines.append("")
        lines.append(
            "Nothing was found to stand in for these. Where a text version is"
        )
        lines.append(
            "listed, it was read out of that same file and is not a replacement"
        )
        lines.append(
            "for it. Do the task with what you have, and say in your answer what"
        )
        lines.append("you could not see.")
        lines.append("")
    lines.append("## How to read them")
    lines.append("")
    lines.append(
        "`workspace_apply` with `operation: read` returns text and only text. A"
    )
    lines.append(
        "spreadsheet, a PDF or a document read that way fails, because the bytes"
    )
    lines.append(
        "are not text — that failure is the format, not a mistake you made. Read"
    )
    lines.append("the text version listed above instead, where there is one.")
    lines.append("")
    lines.append(
        "A text version is an extraction, not the file. Layout, images, styling"
    )
    lines.append(
        "and anything a picture carries are lost. Where one is marked cut short,"
    )
    lines.append("the rest of the document exists and you have not been shown it.")
    destination = workspace / INPUTS_GUIDE
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    destination.chmod(0o600)
    return f"{MODEL_INPUT_PREFIX}/{INPUTS_GUIDE}"


def stage_task_reference_files(
    *,
    task_id: str,
    reference_files: Sequence[Any],
    snapshot_root: str | Path,
    into: str | Path,
    render_text: bool = False,
    workspace_file_limit: int = WORKSPACE_FILE_LIMIT,
) -> TaskStaging:
    """Give one task its files, and say exactly what it did not get.

    Never raises for a file it cannot deliver. A task that names twenty files
    and can be given nineteen is given nineteen, and the twentieth is in the
    record by name — which is the whole point, because the alternative is a task
    that quietly ran short.

    ``render_text`` adds a text rendering beside each file that has one, and a
    short guide naming everything. Off by default, so the plain staging path
    stays exactly what it was and a caller has to ask for the rest. The stage
    runner asks, for a reason worth stating where it is easy to find:

    With ``exec_run`` shut, ``workspace_apply(read)`` is the only way the model
    can open anything, and it decodes UTF-8. Measured against the pinned
    revision by decoding all 261 files the 220 tasks name, 258 of them fail —
    86 spreadsheets, 74 PDFs, 67 documents, and the images, recordings and
    archives after them. Three decode: two CAD ``.STEP`` files and one ``.txt``.
    So without a rendering the model can list its inputs and open three of them.
    Every other read comes back as a bare ``fixture_backend_error``, and the
    answer gets written from the prompt alone by a model that has no way to say
    it was never shown the file.

    That is an environment defect and not a model failure, and the two are
    indistinguishable in a result. Which is why the compensation is made
    explicit here, recorded per file, and named in the pre-registration as a
    difference from the Codex run, whose model has a real shell and opens these
    files itself.
    """
    snapshot_root = Path(snapshot_root).resolve()
    workspace = Path(into).resolve()
    _make_directory_0700(workspace)

    delivered: list[StagedFile] = []
    refused: list[RefusedFile] = []
    extractions: list[ExtractedText] = []
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
            if render_text:
                extractions.append(
                    _extract_one(
                        source=source,
                        relative=relative,
                        workspace=workspace,
                        limit=workspace_file_limit,
                    )
                )
            continue
        if size > workspace_file_limit:
            # Refused so that the rest of the task can work. Staging it would
            # not give the model the file -- the backend cannot read anything
            # this big either -- it would make the walk over the workspace raise,
            # and the walk runs on `write`. One 2 MB spreadsheet left in place
            # costs the task every deliverable it tries to save.
            #
            # 24 of the 261 files in the pinned revision are in this band, and
            # 5 of them have a text rendering worth having. The rendering is
            # made below and named in the guide; the original is recorded here
            # as not delivered, because it is not.
            refused.append(
                RefusedFile(
                    relative_path=relative.as_posix(),
                    reason=TOO_LARGE_FOR_THE_WORKSPACE,
                    detail=(
                        f"{size} bytes, over the {workspace_file_limit} byte "
                        "limit the fixture workspace applies to every file it "
                        "holds. Staged, it would make every write fail rather "
                        "than only this file's read."
                    ),
                )
            )
            if render_text:
                extractions.append(
                    _extract_one(
                        source=source,
                        relative=relative,
                        workspace=workspace,
                        limit=workspace_file_limit,
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
        if render_text:
            extractions.append(
                _extract_one(
                    source=source,
                    relative=relative,
                    workspace=workspace,
                    limit=workspace_file_limit,
                )
            )

    guide = None
    if render_text:
        # Unconditional. A task that names no files still needs the guide,
        # because the instructions send the model to it first and a read that
        # fails ends the task outright rather than returning an error the model
        # can act on.
        guide = _write_inputs_guide(
            workspace=workspace,
            delivered=delivered,
            refused=refused,
            extractions=extractions,
        )

    return TaskStaging(
        task_id=task_id,
        workspace=str(workspace),
        delivered=tuple(delivered),
        refused=tuple(refused),
        extractions=tuple(extractions),
        guide=guide,
    )


def stage_cohort(
    *,
    tasks: Iterable[Any],
    snapshot_root: str | Path,
    into: str | Path,
    render_text: bool = False,
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
            render_text=render_text,
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
    blind = [one for one in needed if one.could_open_nothing]
    prompt_only = [one for one in needed if one.worked_from_the_prompt_alone]
    reasons: dict[str, int] = {}
    for one in stagings:
        for refusal in one.refused:
            reasons[refusal.reason] = reasons.get(refusal.reason, 0) + 1
    outcomes: dict[str, int] = {}
    for one in stagings:
        for rendering in one.extractions:
            outcomes[rendering.outcome] = outcomes.get(rendering.outcome, 0) + 1

    return {
        "schema_version": STAGING_SCHEMA_VERSION,
        "tasks_seen": len(stagings),
        "tasks_naming_reference_files": len(needed),
        "tasks_given_everything_they_named": len(needed) - len(short),
        "tasks_that_ran_without_some_input": len(short),
        "tasks_that_could_open_nothing": len(blind),
        "tasks_that_worked_from_the_prompt_alone": len(prompt_only),
        "files_delivered": sum(len(one.delivered) for one in stagings),
        "bytes_delivered": sum(
            file.size_bytes for one in stagings for file in one.delivered
        ),
        "refusals_by_reason": dict(sorted(reasons.items())),
        "renderings_by_outcome": dict(sorted(outcomes.items())),
        "what_that_means": (
            f"{len(needed) - len(short)} of {len(needed)} tasks that name "
            "reference files were given all of them. "
            f"{len(short)} were not, and each missing file is named below. A "
            "failure on one of those is not evidence about the model. "
            f"{len(prompt_only)} are further along than that: nothing readable "
            "reached them at all, so whatever they answered was answered from "
            "the prompt, and grading them against the inputs they never saw "
            "would be scoring this environment and calling it the model."
        ),
        "what_a_rendering_is": (
            "a text extraction made by core.file_reader, staged beside the file "
            "it came from and never in place of it. It exists because "
            "workspace_apply(read) decodes UTF-8 and almost every reference "
            "file is binary, so with exec_run shut the model would otherwise be "
            "unable to open its own inputs. It is lossy, and a task whose work "
            "needs what it loses is a task this environment cannot set fairly"
        ),
        "tasks": [one.as_dict() for one in stagings],
    }


__all__ = [
    "CHANGED_WHILE_COPYING",
    "EXTRACTION_FAILED",
    "EXTRACTION_IS_A_LABEL",
    "EXTRACTION_IS_EMPTY",
    "EXTRACTION_IS_TEXT",
    "EXTRACTION_PREFIX",
    "EXTRACTION_TRUNCATED",
    "ExtractedText",
    "INPUTS_GUIDE",
    "LINK_FARM_DETAIL",
    "MODEL_INPUT_PREFIX",
    "NOT_A_PLAIN_FILE",
    "NOT_IN_SNAPSHOT",
    "SNAPSHOT_IS_A_LINK_FARM",
    "STAGING_SCHEMA_VERSION",
    "RefusedFile",
    "StagedFile",
    "TOO_LARGE",
    "TOO_LARGE_FOR_THE_WORKSPACE",
    "TOO_MANY",
    "TOTAL_TOO_LARGE",
    "TaskStaging",
    "UNSAFE_PATH",
    "WORKSPACE_FILE_LIMIT",
    "snapshot_problem",
    "stage_cohort",
    "stage_task_reference_files",
    "staging_record",
]
