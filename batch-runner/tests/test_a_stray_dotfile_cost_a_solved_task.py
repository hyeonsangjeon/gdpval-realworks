"""What the workspace hands over has to be something the run can save.

Run `34485072751`, task 3 of 5:

    [3/5] 2ea2e5b5-...-93763f28b19d (Computer and Information Systems
    Managers)... ✗ deliverable filename is invalid or duplicated

The model had already answered by then. Its own receipt for that task records
one model call, 268,999 input tokens and 8,727 output tokens. The answer was
collected out of the workspace and then refused on the way to disk, and the
whole task was recorded as an error -- deliverables included, the good files
along with whatever the bad one was.

Which one was bad cannot be recovered. The message names no file, and the
task's directory is deleted when the task ends. So these tests do two things:
they make the refusal impossible for the cases that caused it, and they make
any refusal that remains say which file it was about.

The cause was two rules that had drifted apart:

* `CodexWorkspace.collect_deliverables` excluded six names by hand --
  `.codex`, `.git`, `__pycache__`, `.pytest_cache`, `.venv`, `node_modules`.
* `_save_files` refuses *any* path component beginning with a dot, plus
  backslashes, plus a name it has already seen.

Four of the collector's six were dot-names, so the intent was the same; the
collector had just written it out as a list. A seventh dot-name -- and an
agent working in a directory makes those without being asked -- passed the
collector and hit the saver. Neither function had a test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.codex_runner import CodexWorkspace
from step2_run_inference import _save_files


def a_workspace(tmp_path: Path, files: dict[str, str]) -> CodexWorkspace:
    """A task's workspace holding exactly `files`, keyed by relative path.

    Built directly rather than through `CodexWorkspace.create`, which resolves
    a run root outside the temporary directory for reasons that have nothing
    to do with collecting files.
    """
    root = tmp_path / "root"
    workspace = root / "workspace"
    for relative, text in files.items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    workspace.mkdir(parents=True, exist_ok=True)
    (root / "codex_home").mkdir(parents=True, exist_ok=True)
    (root / "home").mkdir(parents=True, exist_ok=True)
    return CodexWorkspace(
        root=root,
        workspace=workspace,
        codex_home=root / "codex_home",
        home=root / "home",
    )


def names(collected) -> list[str]:
    return [entry["filename"] for entry in collected]


# ── the file that was lost ───────────────────────────────────────────────


def test_a_hidden_file_no_longer_costs_the_task(tmp_path):
    """The shape of run 34485072751's task 3: an answer, and a dot-name.

    `.gitignore` is the ordinary case -- an agent told to build something in a
    directory writes one. Before, it reached `_save_files`, which refused it,
    which discarded the report next to it.
    """
    workspace = a_workspace(
        tmp_path,
        {
            "systems_assessment.md": "# Assessment\n",
            ".gitignore": "__pycache__/\n",
        },
    )

    collected = workspace.collect_deliverables()

    assert names(collected) == ["systems_assessment.md"]


def test_the_answer_survives_being_saved(tmp_path):
    """Collected is not the same as saved. This runs the real saver."""
    workspace = a_workspace(
        tmp_path,
        {
            "soap_note_2024-03-01_CS.md": "# SOAP\n",
            ".config/settings.json": "{}",
        },
    )

    saved = _save_files(
        workspace.collect_deliverables(),
        "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
        upload_root=tmp_path / "upload",
    )

    assert saved == [
        "deliverable_files/0112fc9b-c3b2-4084-8993-5a4abb1f54f1"
        "/soap_note_2024-03-01_CS.md"
    ]


def test_a_hidden_directory_takes_what_is_under_it(tmp_path):
    """The dot can be on any component, not just the last one."""
    workspace = a_workspace(
        tmp_path,
        {"report.md": "x", ".cache/pip/wheel": "y", "notes/.draft.md": "z"},
    )

    assert names(workspace.collect_deliverables()) == ["report.md"]


@pytest.mark.parametrize(
    "litter",
    [".codex/sessions/a.jsonl", ".git/config", ".pytest_cache/v/x",
     ".venv/bin/python", "__pycache__/m.cpython-310.pyc", "node_modules/p/i.js"],
)
def test_the_six_that_were_named_by_hand_are_still_skipped(tmp_path, litter):
    """Generalising the rule did not stop excluding what it used to exclude."""
    workspace = a_workspace(tmp_path, {"report.md": "x", litter: "y"})

    assert names(workspace.collect_deliverables()) == ["report.md"]


# ── the other two ways a name could not be saved ─────────────────────────


def test_a_backslash_is_replaced_like_every_other_forbidden_character(tmp_path):
    r"""On Linux `a\b.md` is one legal filename. To the saver it is a refusal.

    `_NTFS_FORBIDDEN` is named for the set NTFS will not take, and `\` is in
    that set; it was the one member missing. Replacing it costs nothing on
    Linux and is required on Windows anyway.
    """
    workspace = a_workspace(tmp_path, {"q1\\q2.md": "x"})

    assert names(workspace.collect_deliverables()) == ["q1_q2.md"]


def test_two_names_that_collide_after_replacement_both_survive(tmp_path):
    """Replacement can map two distinct files onto one name.

    The saver refuses the second as a duplicate, and the task dies. Neither
    file is litter, so neither is dropped: the second is given a name that is
    free, the way anything else that downloads a file twice does it.
    """
    workspace = a_workspace(tmp_path, {"q1?.md": "first", "q1_.md": "second"})

    collected = workspace.collect_deliverables()

    assert sorted(names(collected)) == ["q1_ (2).md", "q1_.md"]
    assert sorted(entry["content"] for entry in collected) == [b"first", b"second"]


def test_a_collision_without_an_extension_is_still_resolved(tmp_path):
    workspace = a_workspace(tmp_path, {"Makefile?": "a", "Makefile_": "b"})

    assert sorted(names(workspace.collect_deliverables())) == [
        "Makefile_", "Makefile_ (2)"
    ]


def test_a_dot_in_a_directory_name_is_not_mistaken_for_an_extension(tmp_path):
    """`v1.0/README` renames on the file, not on the directory."""
    workspace = a_workspace(tmp_path, {"v1.0/README?": "a", "v1.0/README_": "b"})

    assert sorted(names(workspace.collect_deliverables())) == [
        "v1.0/README_", "v1.0/README_ (2)"
    ]


# ── the invariant ────────────────────────────────────────────────────────


def test_everything_the_workspace_offers_can_be_saved(tmp_path):
    """The property the two functions have to have, over the awkward cases.

    This is the test that would have caught it. It does not assert a list of
    names; it asserts that the saver accepts whatever the collector produced.
    """
    workspace = a_workspace(
        tmp_path,
        {
            "report.md": "a",
            "data/summary.csv": "b",
            ".gitignore": "c",
            ".config/x.json": "d",
            "notes/.hidden": "e",
            "__pycache__/m.pyc": "f",
            "node_modules/p/i.js": "g",
            "chart?.png": "h",
            "chart_.png": "i",
            "path\\with\\backslash.txt": "j",
            'quote".txt': "k",
            "a:b<c>d|e*f.txt": "l",
        },
    )

    collected = workspace.collect_deliverables()

    saved = _save_files(collected, "t", upload_root=tmp_path / "upload")
    assert len(saved) == len(collected)
    for relative in saved:
        assert (tmp_path / "upload" / relative).is_file()


# ── what a refusal says when there still is one ──────────────────────────


def test_a_refusal_names_the_file(tmp_path):
    """The message run 34485072751 produced, with the one fact it lacked.

    The collector cannot be the only producer of deliverables -- every
    execution mode's files come through here -- so the saver still refuses
    names. It now says which.
    """
    with pytest.raises(ValueError) as refusal:
        _save_files(
            [{"filename": ".gitignore", "content": b"x"}],
            "t",
            upload_root=tmp_path / "upload",
        )

    assert "deliverable filename is invalid or duplicated" in str(refusal.value)
    assert ".gitignore" in str(refusal.value)


def test_a_refused_name_cannot_write_its_own_line_into_the_log(tmp_path):
    """The name comes from the model, and goes into a build log.

    A newline in it would let a rejected filename forge log lines. `repr`
    escapes it, which is why the message quotes rather than interpolates.
    """
    with pytest.raises(ValueError) as refusal:
        _save_files(
            [{"filename": ".a\nStep 3: Format results\n", "content": b"x"}],
            "t",
            upload_root=tmp_path / "upload",
        )

    assert "\n" not in str(refusal.value)


def test_a_refused_name_cannot_fill_the_log_either(tmp_path):
    with pytest.raises(ValueError) as refusal:
        _save_files(
            [{"filename": "." + "n" * 5000, "content": b"x"}],
            "t",
            upload_root=tmp_path / "upload",
        )

    assert len(str(refusal.value)) < 400


def test_the_duplicate_that_is_named_is_the_second_one(tmp_path):
    """A producer that is not the collector can still send two of a name."""
    with pytest.raises(ValueError, match="report.md"):
        _save_files(
            [
                {"filename": "report.md", "content": b"a"},
                {"filename": "report.md", "content": b"b"},
            ],
            "t",
            upload_root=tmp_path / "upload",
        )


# ── what did not change ──────────────────────────────────────────────────


def test_a_staged_reference_is_still_not_a_deliverable(tmp_path):
    """Returning an input as output would credit the run with its own input."""
    workspace = a_workspace(tmp_path, {"input.xlsx": "a", "report.md": "b"})
    workspace.staged_reference_names = ("input.xlsx",)

    assert names(workspace.collect_deliverables()) == ["report.md"]


def test_a_symlink_is_still_not_collected(tmp_path):
    workspace = a_workspace(tmp_path, {"report.md": "a"})
    outside = tmp_path / "outside.md"
    outside.write_text("not produced here", encoding="utf-8")
    (workspace.workspace / "link.md").symlink_to(outside)

    assert names(workspace.collect_deliverables()) == ["report.md"]


def test_a_pyc_is_still_not_collected(tmp_path):
    workspace = a_workspace(tmp_path, {"report.md": "a", "helper.pyc": "b"})

    assert names(workspace.collect_deliverables()) == ["report.md"]


def test_an_empty_workspace_collects_nothing(tmp_path):
    assert a_workspace(tmp_path, {}).collect_deliverables() == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode 000 file")
def test_a_file_that_cannot_be_read_is_skipped_not_fatal(tmp_path):
    """Unreadable is not the same as invalid; it was skipped before, still is."""
    workspace = a_workspace(tmp_path, {"report.md": "a", "locked.md": "b"})
    (workspace.workspace / "locked.md").chmod(0o000)
    try:
        assert names(workspace.collect_deliverables()) == ["report.md"]
    finally:
        (workspace.workspace / "locked.md").chmod(0o600)
