"""Whether a task actually got the files its prompt tells it to open.

The gap this closes was stated for a week before it was sized, and the sizing
found two things that decide what these tests have to hold.

*One file in the dataset cannot be delivered at all.* A 689.1 MB video is over
the compute contract's own single-file limit. So refusal has to be per file: a
cohort that refuses all 220 tasks because one of them names one oversized video
is not a stricter run, it is no run. The tests below check that a refusal is
local -- the other files of that same task still arrive.

*A refusal must stay distinguishable from having nothing to refuse.* Three
states get confused whenever they are stored as one boolean: a task given
everything, a task given some of it, and a task that named no files at all. If
they collapse, a model that failed because it was never handed the spreadsheet
reads afterwards as a model that could not do the work. So every assertion here
that touches the record checks the missing file is present *by name*, not that a
count went up.

And one thing found by running it rather than by reading it: every file in a
``huggingface_hub`` snapshot is a symlink into a blob store outside the snapshot
root, so the hardened opener refuses all 301 of them. That is the ordinary shape
of an ordinary cache and not a security finding, and the refusal has to say so
-- otherwise the next person reads "source is a link" as a planted link.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core import agentic_v2_reference_staging as staging  # noqa: E402
from core.agentic_v2_reference_staging import (  # noqa: E402
    CHANGED_WHILE_COPYING,
    NOT_A_PLAIN_FILE,
    NOT_IN_SNAPSHOT,
    SNAPSHOT_IS_A_LINK_FARM,
    TOO_LARGE,
    TOO_MANY,
    TOTAL_TOO_LARGE,
    UNSAFE_PATH,
    snapshot_problem,
    stage_cohort,
    stage_task_reference_files,
    staging_record,
)

PAYLOAD = b"a spreadsheet, for the purposes of this test\x00\xff\xfe"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    """A dataset root shaped like the real one, with real bytes in it."""
    root = tmp_path / "snapshot"
    folder = root / "reference_files" / "abc123"
    folder.mkdir(parents=True)
    (folder / "sheet.xlsx").write_bytes(PAYLOAD)
    (folder / "notes.pdf").write_bytes(b"a pdf")
    return root


def _stage(snapshot: Path, tmp_path: Path, *names: str, task_id: str = "t"):
    return stage_task_reference_files(
        task_id=task_id,
        reference_files=list(names),
        snapshot_root=snapshot,
        into=tmp_path / "workspace",
    )


def _reasons(result) -> list[str]:
    return [one.reason for one in result.refused]


# ── The bytes arrive, and they are the right bytes ────────────────────────


def test_a_named_file_arrives_with_its_contents_unchanged(snapshot, tmp_path):
    """The whole point, and the thing every other test here assumes.

    Checked byte for byte rather than by size, because the payload contains
    NUL, ``0xff`` and ``0xfe`` -- the sequence that a copy through a text pipe
    silently mangles, which is how an ``.xlsx`` arrives corrupt and reads
    afterwards as a model that produced a broken spreadsheet.
    """
    result = _stage(snapshot, tmp_path, "reference_files/abc123/sheet.xlsx")

    assert result.refused == ()
    assert len(result.delivered) == 1

    landed = Path(result.workspace) / "reference_files/abc123/sheet.xlsx"
    assert landed.read_bytes() == PAYLOAD


def test_the_recorded_digest_is_the_digest_of_what_landed(snapshot, tmp_path):
    """A hash in a record is a claim, and this is the test that it is true."""
    result = _stage(snapshot, tmp_path, "reference_files/abc123/sheet.xlsx")
    only = result.delivered[0]

    assert only.sha256 == DIGEST
    assert only.size_bytes == len(PAYLOAD)

    landed = Path(result.workspace) / only.relative_path
    assert hashlib.sha256(landed.read_bytes()).hexdigest() == only.sha256


def test_the_model_path_says_where_the_file_appears_to_the_model(
    snapshot, tmp_path
):
    """`inputs/…`, the same prefix V1 uses.

    Two records that both quote a path should mean the same place by it.
    """
    result = _stage(snapshot, tmp_path, "reference_files/abc123/sheet.xlsx")

    assert result.delivered[0].model_path == (
        "inputs/reference_files/abc123/sheet.xlsx"
    )


def test_a_task_naming_several_files_gets_all_of_them(snapshot, tmp_path):
    result = _stage(
        snapshot,
        tmp_path,
        "reference_files/abc123/sheet.xlsx",
        "reference_files/abc123/notes.pdf",
    )

    assert result.refused == ()
    assert {one.relative_path for one in result.delivered} == {
        "reference_files/abc123/sheet.xlsx",
        "reference_files/abc123/notes.pdf",
    }
    assert result.everything_arrived is True


# ── One refusal is one refusal, not a cohort ──────────────────────────────


def test_an_undeliverable_file_does_not_take_its_siblings_down_with_it(
    snapshot, tmp_path, monkeypatch
):
    """The 689 MB video, in miniature.

    V1's staging raises on the first problem, which is right for V1 and would
    here mean one oversized video refusing every task in the stage. The file is
    refused; the task still gets the rest.
    """
    monkeypatch.setattr(staging, "MAX_INPUT_SINGLE", 10)

    result = _stage(
        snapshot,
        tmp_path,
        "reference_files/abc123/sheet.xlsx",  # over the patched limit
        "reference_files/abc123/notes.pdf",  # five bytes, under it
    )

    assert _reasons(result) == [TOO_LARGE]
    assert [one.relative_path for one in result.delivered] == [
        "reference_files/abc123/notes.pdf"
    ]


def test_an_oversized_file_is_refused_with_its_size_and_not_truncated(
    snapshot, tmp_path, monkeypatch
):
    """Never a short file on disk, which would read as a corrupt download."""
    monkeypatch.setattr(staging, "MAX_INPUT_SINGLE", 10)

    result = _stage(snapshot, tmp_path, "reference_files/abc123/sheet.xlsx")

    only = result.refused[0]
    assert only.reason == TOO_LARGE
    assert str(len(PAYLOAD)) in only.detail
    assert "changes what the task measures" in only.detail
    assert not (Path(result.workspace) / only.relative_path).exists()


def test_a_task_whose_files_would_pass_the_total_stops_at_the_total(
    snapshot, tmp_path, monkeypatch
):
    monkeypatch.setattr(staging, "MAX_INPUT_TOTAL", len(PAYLOAD) + 1)

    result = _stage(
        snapshot,
        tmp_path,
        "reference_files/abc123/sheet.xlsx",
        "reference_files/abc123/notes.pdf",
    )

    assert len(result.delivered) == 1
    assert _reasons(result) == [TOTAL_TOO_LARGE]


def test_more_files_than_the_limit_allows_refuses_the_excess_by_name(
    snapshot, tmp_path, monkeypatch
):
    """The excess is named, not counted.

    A task told "you named too many files" cannot be read later; a task told
    *which* ones it did not get can.
    """
    monkeypatch.setattr(staging, "MAX_INPUT_FILES", 1)

    result = _stage(
        snapshot,
        tmp_path,
        "reference_files/abc123/sheet.xlsx",
        "reference_files/abc123/notes.pdf",
    )

    assert _reasons(result) == [TOO_MANY]
    assert result.refused[0].relative_path == "reference_files/abc123/notes.pdf"
    assert len(result.delivered) == 1


# ── Paths the dataset supplies are not trusted ────────────────────────────


@pytest.mark.parametrize(
    "path, because",
    [
        ("../escape.txt", "path climbs out of the tree"),
        ("reference_files/../../escape.txt", "path climbs out of the tree"),
        ("/etc/passwd", "path is absolute"),
        (".hidden/file.txt", "path has a hidden component"),
        ("/".join(["deep"] * 40) + "/file.txt", "deeper than"),
        ("reference_files/" + "n" * 300 + ".xlsx", "longer than"),
    ],
)
def test_a_path_that_could_write_outside_the_workspace_is_refused(
    snapshot, tmp_path, path, because
):
    """Refused on the path, before anything is opened or created.

    These come from a dataset file. Being a published, pinned dataset makes
    them likely to be fine and does not make them checked, and the cost of
    being wrong is a write outside the workspace.
    """
    result = _stage(snapshot, tmp_path, path)

    assert _reasons(result) == [UNSAFE_PATH]
    assert because in result.refused[0].detail
    assert result.delivered == ()


def test_nothing_is_written_above_the_workspace(snapshot, tmp_path):
    """The property the path rules exist for, checked on the filesystem."""
    canary = tmp_path / "escape.txt"

    _stage(snapshot, tmp_path, "../escape.txt", "../../escape.txt")

    assert not canary.exists()


def test_a_file_the_snapshot_does_not_have_is_refused_by_name(
    snapshot, tmp_path
):
    result = _stage(snapshot, tmp_path, "reference_files/abc123/absent.docx")

    assert _reasons(result) == [NOT_IN_SNAPSHOT]
    assert "absent.docx" in result.refused[0].detail


# ── The shape a real snapshot actually arrives in ─────────────────────────


def test_a_symlink_is_refused_as_a_cache_rather_than_as_an_attack(
    snapshot, tmp_path
):
    """301 of 301 real files hit this, and the wording is the whole value.

    The generic answer for a symlink is "source is a link", which reads as
    something planted. What it actually means is that the dataset was fetched
    into a ``huggingface_hub`` cache, where every name is a link into a blob
    store outside the root. The refusal has to name the fix, because the
    correct next step -- fetch again with ``--local-dir`` -- is not something
    the generic message would ever suggest.
    """
    outside = tmp_path / "blobs" / "deadbeef"
    outside.parent.mkdir()
    outside.write_bytes(PAYLOAD)
    link = snapshot / "reference_files" / "abc123" / "linked.xlsx"
    link.symlink_to(os.path.relpath(outside, link.parent))

    result = _stage(snapshot, tmp_path, "reference_files/abc123/linked.xlsx")

    assert _reasons(result) == [SNAPSHOT_IS_A_LINK_FARM]
    assert "--local-dir" in result.refused[0].detail
    assert not (Path(result.workspace) / "reference_files/abc123/linked.xlsx").exists()


def test_a_hard_link_is_refused_as_a_link_and_not_as_a_race(snapshot, tmp_path):
    """Same rule V1 applies, kept rather than relaxed — and named correctly.

    A second name for the same inode means something else can change the bytes
    after they were checked and before they were read, so it is refused. The
    test is here for the *reason* string as much as for the refusal: the first
    version of this module sorted every mid-copy problem into one bucket and
    reported this one as ``source_changed_while_it_was_being_copied``, which
    states that a race occurred. Nothing raced. A record that invents an event
    is worse than one that says less.
    """
    target = snapshot / "reference_files" / "abc123" / "sheet.xlsx"
    os.link(target, snapshot / "reference_files" / "abc123" / "second-name.xlsx")

    result = _stage(snapshot, tmp_path, "reference_files/abc123/sheet.xlsx")

    assert _reasons(result) == [NOT_A_PLAIN_FILE]
    assert "hard links" in result.refused[0].detail
    assert CHANGED_WHILE_COPYING not in _reasons(result)
    assert result.delivered == ()


def test_a_refused_file_leaves_nothing_behind_in_the_workspace(
    snapshot, tmp_path
):
    """Whatever a refusal costs, it must not cost a half-written file.

    A short file in the workspace is the worst of the three outcomes: the model
    opens it and reads it as the whole document, while the record says it was
    refused. The two disagree and the result looks like a model that misread a
    spreadsheet.
    """
    os.link(
        snapshot / "reference_files" / "abc123" / "sheet.xlsx",
        snapshot / "reference_files" / "abc123" / "second-name.xlsx",
    )

    result = _stage(
        snapshot,
        tmp_path,
        "reference_files/abc123/sheet.xlsx",
        "reference_files/abc123/notes.pdf",
    )

    workspace = Path(result.workspace)
    assert not (workspace / "reference_files/abc123/sheet.xlsx").exists()
    assert sorted(one.name for one in workspace.rglob("*") if one.is_file()) == [
        "notes.pdf"
    ]


# ── Asking the question once, instead of 261 times ────────────────────────


def test_a_cache_of_symlinks_is_diagnosed_before_any_task_is_staged(
    snapshot, tmp_path
):
    """One wrong directory should not look like 125 broken tasks."""
    for path in list((snapshot / "reference_files").rglob("*")):
        if path.is_file():
            moved = tmp_path / "blobs" / path.name
            moved.parent.mkdir(exist_ok=True)
            path.rename(moved)
            path.symlink_to(os.path.relpath(moved, path.parent))

    problem = snapshot_problem(snapshot)

    assert problem is not None
    assert "symlink" in problem
    assert "--local-dir" in problem


def test_a_directory_of_real_files_has_no_problem(snapshot):
    assert snapshot_problem(snapshot) is None


def test_a_root_that_is_not_there_is_named_rather_than_crashed_on(tmp_path):
    assert "is not a directory" in snapshot_problem(tmp_path / "absent")


def test_a_root_with_no_reference_files_directory_says_so(tmp_path):
    (tmp_path / "root").mkdir()

    problem = snapshot_problem(tmp_path / "root")

    assert "does not exist" in problem
    assert "--local-dir" in problem


# ── Three states that must not collapse into one ──────────────────────────


def test_a_task_that_named_nothing_is_not_counted_as_fully_staged(
    snapshot, tmp_path
):
    """`everything_arrived` is about files, and it had none to arrive.

    Reported as True, a cohort of tasks needing no inputs would read as a
    cohort that was fully staged -- which is the reading this whole record
    exists to prevent.
    """
    result = _stage(snapshot, tmp_path)

    assert result.everything_arrived is False
    assert result.ran_without_its_inputs is False
    assert result.named == 0


def test_the_record_tells_the_three_states_apart(snapshot, tmp_path):
    """Given everything, given some of it, and had nothing to be given."""
    everything = _stage(
        snapshot, tmp_path / "a", "reference_files/abc123/sheet.xlsx", task_id="all"
    )
    partly = _stage(
        snapshot,
        tmp_path / "b",
        "reference_files/abc123/sheet.xlsx",
        "reference_files/abc123/absent.docx",
        task_id="some",
    )
    nothing = _stage(snapshot, tmp_path / "c", task_id="none")

    record = staging_record([everything, partly, nothing])

    assert record["tasks_seen"] == 3
    assert record["tasks_naming_reference_files"] == 2
    assert record["tasks_given_everything_they_named"] == 1
    assert record["tasks_that_ran_without_some_input"] == 1


def test_every_file_a_task_did_not_get_is_in_the_record_by_name(
    snapshot, tmp_path
):
    """A count cannot be read against a result; a filename can."""
    partly = _stage(
        snapshot,
        tmp_path,
        "reference_files/abc123/sheet.xlsx",
        "reference_files/abc123/absent.docx",
    )

    record = staging_record([partly])
    only = record["tasks"][0]

    assert [one["relative_path"] for one in only["refused"]] == [
        "reference_files/abc123/absent.docx"
    ]
    assert record["refusals_by_reason"] == {NOT_IN_SNAPSHOT: 1}


def test_the_record_says_what_a_failure_on_a_short_task_does_not_prove(
    snapshot, tmp_path
):
    """The sentence a reader needs, carried with the numbers rather than near them."""
    partly = _stage(
        snapshot, tmp_path, "reference_files/abc123/absent.docx"
    )

    record = staging_record([partly])

    assert "not evidence about the model" in record["what_that_means"]


def test_the_summary_counts_agree_with_the_detail_underneath(
    snapshot, tmp_path
):
    """Two places to read the same fact is two places for it to differ."""
    results = [
        _stage(
            snapshot,
            tmp_path / str(index),
            "reference_files/abc123/sheet.xlsx",
            task_id=f"t{index}",
        )
        for index in range(3)
    ]

    record = staging_record(results)

    assert record["files_delivered"] == sum(
        len(one["delivered"]) for one in record["tasks"]
    )
    assert record["bytes_delivered"] == len(PAYLOAD) * 3


# ── A cohort, rather than a task ──────────────────────────────────────────


class _Task:
    def __init__(self, task_id: str, *names: str) -> None:
        self.task_id = task_id
        self.reference_files = names


def test_each_task_in_a_cohort_gets_its_own_directory(snapshot, tmp_path):
    """They do not share a workspace, so they must not share a staging root.

    One task reading another's inputs would be undetectable from a result and
    would make a cohort's tasks quietly non-independent.
    """
    staged = stage_cohort(
        tasks=[
            _Task("first", "reference_files/abc123/sheet.xlsx"),
            _Task("second", "reference_files/abc123/notes.pdf"),
        ],
        snapshot_root=snapshot,
        into=tmp_path / "cohort",
    )

    assert staged[0].workspace != staged[1].workspace
    assert not (Path(staged[0].workspace) / "reference_files/abc123/notes.pdf").exists()


def test_two_tasks_naming_the_same_file_both_get_it(snapshot, tmp_path):
    staged = stage_cohort(
        tasks=[
            _Task("first", "reference_files/abc123/sheet.xlsx"),
            _Task("second", "reference_files/abc123/sheet.xlsx"),
        ],
        snapshot_root=snapshot,
        into=tmp_path / "cohort",
    )

    for one in staged:
        landed = Path(one.workspace) / "reference_files/abc123/sheet.xlsx"
        assert landed.read_bytes() == PAYLOAD


def test_a_task_directory_is_not_named_with_the_task_id_itself(
    snapshot, tmp_path
):
    """A task id comes from the dataset; a directory name is ours.

    The same rule V1 follows. It is what stops a task id that happens to
    contain a path separator from deciding where files are written.
    """
    staged = stage_cohort(
        tasks=[_Task("a/../b", "reference_files/abc123/sheet.xlsx")],
        snapshot_root=snapshot,
        into=tmp_path / "cohort",
    )

    assert Path(staged[0].workspace).name == hashlib.sha256(
        b"a/../b"
    ).hexdigest()
    assert Path(staged[0].workspace).is_relative_to((tmp_path / "cohort").resolve())


def test_a_cohort_of_nothing_stages_nothing_and_does_not_fail(tmp_path, snapshot):
    assert stage_cohort(tasks=[], snapshot_root=snapshot, into=tmp_path) == ()
