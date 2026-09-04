"""The gate reads the input files rather than taking their fingerprints on trust.

Before this, the check compared the first 32 of a fingerprint's 64 characters
against the folder name in the file's own path, and called that a match. The
other 32 characters were never compared against anything, so a fingerprint
could be half wrong and pass. Nothing read a byte of any file.

The tests here hold the check to reading the file. The proof is the sweep at
the bottom: every single-character change to every fingerprint, at every one of
the 64 positions, must be caught. Half of those positions used to sail through.

The second thing these tests hold is the answer given when no copy of a file is
on the machine. It must be its own visible answer — "this went unchecked" — and
never silence, because a fingerprint nobody compared is not evidence, and the
report is read by someone deciding whether to authorise a bill.

That answer is also kept in a list of its own, apart from the disagreements.
The two say different things: a disagreement means the plan pinned the wrong
file and reads the same on every machine, while a missing copy means only that
this machine has not downloaded the benchmark yet. Both stop a run. Merging
them would force anything asking "is anything else wrong?" to either fail on a
build server or filter by guesswork, and a filter that could swallow a
disagreement would undo the whole check.

The third thing is what a folder name is allowed to prove. The folder half of
the rule above was itself built on a premise the dataset does not honour: that
a folder of 32 hexadecimal characters is the start of its file's fingerprint.
Measured on the pinned revision, that is true of 200 of its 549 files and false
of the other 349 — every one of the 248 under ``deliverable_files/`` among
them. The two shapes are identical on the page, so a *match* between folder and
written value is evidence and a *mismatch* is not evidence of anything. The
tests below hold the check to that asymmetry: it keeps the 32 characters when
they agree, and when they disagree it reports the disagreement, blocks the run,
and names no culprit.

Nothing here calls a model, downloads anything, or spends anything.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_preflight import (  # noqa: E402
    conditions_from_plan,
    describe_input_file_checks,
    load_plan,
    run_envelope_preflight,
)
from core.execution_envelope_tasks import (  # noqa: E402
    DATASET_DATA_FILE,
    HOW_TO_GET_THE_FILES,
    INPUT_FILE_DISAGREED,
    INPUT_FILE_FOLDER_NAME_ONLY,
    INPUT_FILE_NOT_CHECKED,
    INPUT_FILE_READ,
    REFERENCE_PATH_FINGERPRINT_LENGTH,
    CatalogTask,
    TaskCatalog,
    check_input_file_versions,
    folder_name_agrees_with,
    load_task_catalog,
    locate_input_file,
    path_folder_is_shaped_like_a_fingerprint,
    reference_files_for,
    sha256_of_file,
    verify_input_file_versions,
)
from core.execution_envelope_tasks import (  # noqa: E402
    _copy_in_the_download_cache,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)

# A fingerprint of something else entirely, used as a donor when a tampered
# value has to look exactly as plausible as the real one.
UNRELATED_FINGERPRINT = (
    "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
)


# ── A small benchmark made of real files, so the check has bytes to read ───


def _write_reference_file(root: Path, name: str, body: bytes) -> str:
    """Put a file in a folder this dataset really did name after it.

    Two hundred of the pinned revision's 549 files are like this. Only these
    ones can have 32 characters of their fingerprint confirmed without a copy.
    """
    fingerprint = hashlib.sha256(body).hexdigest()
    folder = root / "reference_files" / fingerprint[:REFERENCE_PATH_FINGERPRINT_LENGTH]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(body)
    return f"reference_files/{fingerprint[:REFERENCE_PATH_FINGERPRINT_LENGTH]}/{name}"


def _write_file_in_an_opaque_folder(root: Path, name: str, body: bytes) -> str:
    """Put a file in a 32-character folder that is *not* named after it.

    The other 349 of the pinned revision's 549 files are like this, including
    every one of the 248 under ``deliverable_files/``. On the page the path
    looks exactly like the one above — 32 hexadecimal characters either way —
    which is the whole reason the shape cannot be read as provenance:

        reference_files/4e6e2b8d17f751e483aad52c109813b4/Fall Music Tour Ref File.xlsx

    really hashes to ``3d0ebb81…`` at the pinned revision, and nothing about
    the path says so.
    """
    folder_name = hashlib.sha256(b"named after something else: " + name.encode())
    folder_name = folder_name.hexdigest()[:REFERENCE_PATH_FINGERPRINT_LENGTH]
    assert not hashlib.sha256(body).hexdigest().startswith(folder_name)
    folder = root / "reference_files" / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(body)
    return f"reference_files/{folder_name}/{name}"


def _task(task_id: str, paths: tuple[str, ...]) -> CatalogTask:
    return CatalogTask(
        task_id=task_id,
        sector="Retail Trade",
        occupation="Buyer",
        deliverable_file_extensions=(".xlsx",),
        reference_file_count=len(paths),
        reference_file_extensions=(".xlsx",),
        reference_file_paths=paths,
        prompt_sha256="c" * 64,
        prompt_character_count=100,
        rubric_item_count=5,
        widest_rubric_criterion_characters=200,
    )


@pytest.fixture
def small_benchmark(tmp_path):
    """A dataset root holding two reference files and one data file.

    Everything the check reads is a real file with a real fingerprint, so the
    tests can tamper with a written value and watch what happens.
    """
    root = tmp_path / "dataset"
    root.mkdir()
    first = _write_reference_file(root, "Costs.xlsx", b"one hundred widgets\n")
    second = _write_reference_file(root, "Notes.docx", b"a note about widgets\n")

    data_file = root / DATASET_DATA_FILE
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_bytes(b"a stand-in for the benchmark's own data file\n")

    catalog = TaskCatalog(
        schema_version="gdpval-task-catalog-v1",
        dataset_repo_id="example/benchmark",
        dataset_revision="d" * 40,
        dataset_file_sha256=sha256_of_file(data_file),
        tasks=(_task("task-one", (first, second)),),
    )
    written = {
        f"{catalog.dataset_repo_id}@{catalog.dataset_revision}": (
            catalog.dataset_file_sha256
        ),
        first: sha256_of_file(root / first),
        second: sha256_of_file(root / second),
    }
    return root, catalog, ("task-one",), written


@pytest.fixture
def opaque_benchmark(tmp_path):
    """The same benchmark, with one file in a folder not named after it.

    Both written fingerprints are correct. The only difference between the two
    files is one nobody can see from the path: one folder repeats the start of
    its file's fingerprint and the other does not, exactly as 200 and 349 of
    the pinned revision's files respectively do.
    """
    root = tmp_path / "dataset"
    root.mkdir()
    honest = _write_reference_file(root, "Costs.xlsx", b"one hundred widgets\n")
    opaque = _write_file_in_an_opaque_folder(
        root, "Notes.docx", b"a note about widgets\n"
    )

    data_file = root / DATASET_DATA_FILE
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_bytes(b"a stand-in for the benchmark's own data file\n")

    catalog = TaskCatalog(
        schema_version="gdpval-task-catalog-v1",
        dataset_repo_id="example/benchmark",
        dataset_revision="d" * 40,
        dataset_file_sha256=sha256_of_file(data_file),
        tasks=(_task("task-one", (honest, opaque)),),
    )
    written = {
        f"{catalog.dataset_repo_id}@{catalog.dataset_revision}": (
            catalog.dataset_file_sha256
        ),
        honest: sha256_of_file(root / honest),
        opaque: sha256_of_file(root / opaque),
    }
    return root, catalog, ("task-one",), written, honest, opaque


@pytest.fixture
def no_download_cache(monkeypatch):
    """A machine that has never downloaded the benchmark.

    This is the state a fresh build runner is in, and it is not the same as
    pointing the check at an empty folder: the check also looks in the download
    cache, which on a developer's machine usually holds the pinned revision
    already. Emptying both is what makes these tests say the same thing in both
    places.
    """
    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", lambda **_: None)


def _verify(benchmark, written=None, root=None):
    dataset_root, catalog, task_ids, honest = benchmark
    return verify_input_file_versions(
        honest if written is None else written,
        task_ids,
        catalog,
        dataset_root if root is None else root,
    )


# ── The honest plan passes, and says how it was checked ────────────────────


def test_honest_fingerprints_pass_with_nothing_left_over(small_benchmark):
    result = _verify(small_benchmark)

    assert result.problems == ()
    assert result.everything_was_read


def test_every_file_reports_all_sixty_four_characters_compared(small_benchmark):
    result = _verify(small_benchmark)

    assert len(result.checks) == 3
    for check in result.checks:
        assert check.state == INPUT_FILE_READ, check.path
        assert check.characters_compared == 64, check.path


def test_the_dataset_file_itself_is_read_not_only_compared_to_the_catalogue(
    small_benchmark,
):
    result = _verify(small_benchmark)

    data_file_checks = [
        check for check in result.checks if check.path == DATASET_DATA_FILE
    ]
    assert len(data_file_checks) == 1
    assert data_file_checks[0].state == INPUT_FILE_READ


def test_a_file_that_changed_on_disk_is_caught_even_though_nothing_was_edited(
    small_benchmark,
):
    dataset_root, _, _, honest = small_benchmark
    path = sorted(key for key in honest if key.startswith("reference_files/"))[0]
    (dataset_root / path).write_bytes(b"something else entirely\n")

    result = _verify(small_benchmark)

    assert any("describes some other file" in note for note in result.problems)


# ── When no copy is there, that is its own answer ───────────────────────────


def test_a_file_no_copy_of_which_is_reachable_is_reported_not_passed(
    small_benchmark, tmp_path
):
    result = _verify(small_benchmark, root=tmp_path / "nowhere")

    assert result.missing_copies != ()
    assert not result.everything_was_read


def test_the_report_says_how_to_get_the_missing_files_for_nothing(
    small_benchmark, tmp_path
):
    result = _verify(small_benchmark, root=tmp_path / "nowhere")

    assert any("hf download" in note for note in result.missing_copies)
    assert any("--dataset-root" in note for note in result.missing_copies)


def test_the_command_the_report_names_is_one_this_machine_can_run():
    """A pointer a reader cannot follow is worse than none: it reads as a fact.

    ``huggingface-cli`` was named here until the pinned huggingface-hub stopped
    shipping it as anything but a message saying it "is deprecated and no
    longer works" — which it prints on the way to exiting without downloading
    a byte. Nothing is downloaded here either; the command is only asked
    whether it exists, with ``--help``.

    A machine that does not have the program at all is skipped rather than
    failed. Not being able to ask is not the same answer as asking and being
    told no, which is the distinction this whole module is about.
    """
    import shlex
    import shutil
    import subprocess

    quoted = HOW_TO_GET_THE_FILES[HOW_TO_GET_THE_FILES.index("`") + 1 :]
    program = shlex.split(quoted[: quoted.index("`")])[0]
    if shutil.which(program) is None:
        pytest.skip(f"{program} is not on this machine, so it cannot be asked")

    finished = subprocess.run(
        [program, "--help"], capture_output=True, text=True, timeout=120
    )

    assert finished.returncode == 0, finished.stderr
    assert "no longer works" not in (finished.stdout + finished.stderr)


def test_a_missing_copy_says_how_much_of_the_fingerprint_went_unchecked(
    small_benchmark, tmp_path
):
    result = _verify(small_benchmark, root=tmp_path / "nowhere")

    by_path = {check.path: check for check in result.checks}
    reference = [
        check
        for path, check in by_path.items()
        if path.startswith("reference_files/")
    ]
    assert reference
    for check in reference:
        assert check.state == INPUT_FILE_FOLDER_NAME_ONLY
        assert check.characters_compared == REFERENCE_PATH_FINGERPRINT_LENGTH


def test_a_fingerprint_nobody_could_compare_is_never_called_fully_checked(
    small_benchmark, tmp_path
):
    result = _verify(small_benchmark, root=tmp_path / "nowhere")

    assert result.fully_checked == ()
    assert len(result.not_fully_checked) == len(result.checks)


def test_the_folder_disagreeing_still_stops_the_run_without_naming_a_culprit(
    small_benchmark, tmp_path
):
    """A missing copy must not turn into a free pass for the folder rule.

    It must not turn into a verdict either. The folder and the written value
    disagree; that is reported, it blocks, and which of the two is wrong is
    left unsaid, because in this dataset a folder that is not named after its
    file disagrees with a *correct* fingerprint exactly like this.
    """
    dataset_root, catalog, task_ids, honest = small_benchmark
    path = sorted(key for key in honest if key.startswith("reference_files/"))[0]
    tampered = dict(honest)
    tampered[path] = UNRELATED_FINGERPRINT

    result = verify_input_file_versions(
        tampered, task_ids, catalog, tmp_path / "nowhere"
    )
    gate = check_input_file_versions(
        tampered, task_ids, catalog, tmp_path / "nowhere"
    )
    check = {item.path: item for item in result.checks}[path]

    assert any(path in note for note in result.missing_copies)
    assert any("does not repeat the first 32" in note for note in result.all_notes)
    assert gate != []
    # not filed as a verdict, and not filed as work that was done
    assert not any("describes some other file" in note for note in result.all_notes)
    assert check.state == INPUT_FILE_NOT_CHECKED
    assert check.characters_compared == 0


def test_the_old_folder_verdict_would_be_caught_if_it_came_back(
    small_benchmark, tmp_path
):
    """Proof the test above can fail, by rebuilding what the check used to say.

    Until this was fixed the branch appended a problem reading "the fingerprint
    written for <path> does not match the folder the dataset keeps that file
    in, so the written value describes some other file", and recorded the file
    as ``folder name only`` with 32 of 64 characters compared. Both are
    reconstructed here so the assertions above are shown to be load-bearing.
    """
    dataset_root, catalog, task_ids, honest = small_benchmark
    path = sorted(key for key in honest if key.startswith("reference_files/"))[0]
    tampered = dict(honest)
    tampered[path] = UNRELATED_FINGERPRINT

    result = verify_input_file_versions(
        tampered, task_ids, catalog, tmp_path / "nowhere"
    )
    as_it_used_to_be = dataclasses.replace(
        result,
        problems=result.problems
        + (
            f"the fingerprint written for {path} does not match the folder the "
            "dataset keeps that file in, so the written value describes some "
            "other file",
        ),
        checks=tuple(
            dataclasses.replace(
                check,
                state=INPUT_FILE_FOLDER_NAME_ONLY,
                characters_compared=REFERENCE_PATH_FINGERPRINT_LENGTH,
            )
            if check.path == path
            else check
            for check in result.checks
        ),
    )
    was = {item.path: item for item in as_it_used_to_be.checks}[path]

    assert any(
        "describes some other file" in note for note in as_it_used_to_be.all_notes
    )
    assert was.characters_compared == REFERENCE_PATH_FINGERPRINT_LENGTH
    assert was.state == INPUT_FILE_FOLDER_NAME_ONLY


def test_a_missing_copy_is_not_filed_as_a_disagreement(
    small_benchmark, tmp_path
):
    """Absent bytes say nothing about whether the written value is right."""
    result = _verify(small_benchmark, root=tmp_path / "nowhere")

    assert result.problems == ()
    assert len(result.missing_copies) == 3


def test_a_disagreement_is_never_filed_as_a_missing_copy(small_benchmark):
    """The set-aside list must not be able to swallow a real fault.

    Six tests elsewhere set ``missing_copies`` aside to mean "this machine has
    not downloaded the benchmark". If a disagreement could land there, a plan
    pinning the wrong file would be filtered out of all six.
    """
    dataset_root, catalog, task_ids, honest = small_benchmark
    path = sorted(key for key in honest if key.startswith("reference_files/"))[0]
    (dataset_root / path).write_bytes(b"a different file altogether\n")

    result = verify_input_file_versions(honest, task_ids, catalog, dataset_root)

    assert result.missing_copies == ()
    assert any("describes some other file" in note for note in result.problems)


def test_both_lists_are_reasons_not_to_start(small_benchmark, tmp_path):
    """Splitting the answer in two must not quietly drop half of the gate."""
    dataset_root, catalog, task_ids, honest = small_benchmark

    result = verify_input_file_versions(
        honest, task_ids, catalog, tmp_path / "nowhere"
    )
    gate = check_input_file_versions(
        honest, task_ids, catalog, tmp_path / "nowhere"
    )

    assert result.all_notes == result.problems + result.missing_copies
    assert gate == list(result.all_notes)
    assert gate != []


# ── A folder shaped like a fingerprint is not a fingerprint ────────────────
#
# The check used to read a path's *shape*: a folder of 32 hexadecimal
# characters was taken to be the first half of that file's own fingerprint. It
# is true of 200 of the pinned revision's 549 files and false of the other 349,
# including every one of the 248 under ``deliverable_files/``, and the two look
# identical on the page.
#
# Two things followed. A correct fingerprint for one of the 349 was filed as
# "the written value describes some other file" — a verdict the check had no
# basis for. And a file nothing had compared was recorded as 32 of 64
# characters checked, which is never-measured published as half-measured.


def test_the_shape_of_a_path_is_not_read_as_a_promise_about_its_contents():
    """The predicate says what it can see, and its name says so too.

    Both of these paths are the same shape. One folder is the start of its
    file's fingerprint and the other is not, and no reading of the path can
    tell them apart — which is why the answer here is only "worth comparing",
    and the comparing is done elsewhere against a real value.
    """
    body = b"one hundred widgets\n"
    real = hashlib.sha256(body).hexdigest()
    named_after_it = f"reference_files/{real[:32]}/Costs.xlsx"
    named_after_nothing = f"reference_files/{'0123456789abcdef' * 2}/Costs.xlsx"

    assert path_folder_is_shaped_like_a_fingerprint(named_after_it)
    assert path_folder_is_shaped_like_a_fingerprint(named_after_nothing)

    assert folder_name_agrees_with(named_after_it, real)
    assert not folder_name_agrees_with(named_after_nothing, real)
    assert not folder_name_agrees_with("inputs/Costs.xlsx", real)


def test_a_correct_fingerprint_under_an_opaque_folder_is_not_accused(
    opaque_benchmark, tmp_path
):
    """The false accusation, gone. This is the regression itself.

    Both fingerprints in this plan are correct. One file's folder happens to be
    named after it and the other's is not — the arrangement 349 of the pinned
    revision's 549 files are in. Before this fix the second one was reported as
    a written value that "describes some other file".
    """
    _, catalog, task_ids, written, honest, opaque = opaque_benchmark

    result = verify_input_file_versions(
        written, task_ids, catalog, tmp_path / "nowhere"
    )

    assert result.problems == ()
    assert not any(
        "describes some other file" in note for note in result.all_notes
    )
    assert any(opaque in note for note in result.missing_copies)


def test_an_opaque_folder_is_recorded_as_nothing_compared_not_half_compared(
    opaque_benchmark, tmp_path
):
    """The second harm: effort that was never spent, written down as spent."""
    _, catalog, task_ids, written, honest, opaque = opaque_benchmark

    result = verify_input_file_versions(
        written, task_ids, catalog, tmp_path / "nowhere"
    )
    by_path = {check.path: check for check in result.checks}

    assert by_path[opaque].state == INPUT_FILE_NOT_CHECKED
    assert by_path[opaque].characters_compared == 0
    # and the file whose folder really does agree still gets its 32 characters,
    # because 32 hexadecimal characters do not line up by accident
    assert by_path[honest].state == INPUT_FILE_FOLDER_NAME_ONLY
    assert by_path[honest].characters_compared == REFERENCE_PATH_FINGERPRINT_LENGTH


def test_withdrawing_the_accusation_does_not_withdraw_the_gate(
    opaque_benchmark, tmp_path
):
    """Fail closed. Saying less must not mean stopping less.

    ``problems`` is now empty for this plan, and the run must still refuse to
    start. It does because the note goes to ``missing_copies``, which the
    preflight folds back into its own problems — being unable to check a
    fingerprint has always been a reason not to start.
    """
    _, catalog, task_ids, written, honest, opaque = opaque_benchmark

    gate = check_input_file_versions(
        written, task_ids, catalog, tmp_path / "nowhere"
    )
    result = verify_input_file_versions(
        written, task_ids, catalog, tmp_path / "nowhere"
    )

    assert gate != []
    assert any(opaque in note for note in gate)
    assert not result.everything_was_read
    assert gate == list(result.all_notes)


def test_a_copy_under_an_opaque_folder_that_disagrees_is_not_called_tampering(
    opaque_benchmark
):
    """With the bytes in hand the same restraint applies, for the same reason.

    A copy sitting in a folder nobody proved was named after it could be any
    revision. The two disagree; which one is wrong is not knowable from here.
    The stronger sentence is kept for the file whose folder the bytes or the
    written value confirm.
    """
    dataset_root, catalog, task_ids, written, honest, opaque = opaque_benchmark
    (dataset_root / opaque).write_bytes(b"some other revision of the note\n")

    result = verify_input_file_versions(written, task_ids, catalog, dataset_root)
    check = {item.path: item for item in result.checks}[opaque]

    assert check.state == INPUT_FILE_DISAGREED
    assert check.characters_compared == 64
    assert any("do not describe the same file" in note for note in result.problems)
    assert not any(
        "describes some other file" in note for note in result.problems
    )


def test_both_files_pass_when_the_copies_are_there_and_agree(opaque_benchmark):
    """The opaque folder is not being treated as a fault of its own.

    Nothing about a folder that is not named after its file is wrong. It is
    only unhelpful, and the check must say nothing at all about it when the
    bytes are readable and match.
    """
    dataset_root, catalog, task_ids, written, _, _ = opaque_benchmark

    result = verify_input_file_versions(written, task_ids, catalog, dataset_root)

    assert result.problems == ()
    assert result.missing_copies == ()
    assert result.everything_was_read
    assert result.everything_agreed


# ── The path shape that used to be waved through ───────────────────────────


def test_a_path_that_says_nothing_about_its_contents_is_not_waved_through(
    tmp_path,
):
    """The old check compared nothing at all for a differently shaped path.

    Its folder-name rule only applied when the folder was exactly 32 characters
    long. Any other path skipped the comparison entirely and was reported as
    fine, which is the one answer that was certainly wrong.
    """
    catalog = TaskCatalog(
        schema_version="gdpval-task-catalog-v1",
        dataset_repo_id="example/benchmark",
        dataset_revision="d" * 40,
        dataset_file_sha256="a" * 64,
        tasks=(_task("task-one", ("inputs/Costs.xlsx",)),),
    )
    written = {
        f"{catalog.dataset_repo_id}@{catalog.dataset_revision}": "a" * 64,
        "inputs/Costs.xlsx": UNRELATED_FINGERPRINT,
    }

    result = verify_input_file_versions(written, ("task-one",), catalog, tmp_path)

    assert not path_folder_is_shaped_like_a_fingerprint("inputs/Costs.xlsx")
    by_path = {check.path: check for check in result.checks}
    assert by_path["inputs/Costs.xlsx"].state == INPUT_FILE_NOT_CHECKED
    assert by_path["inputs/Costs.xlsx"].characters_compared == 0
    assert any("none of its 64" in note for note in result.missing_copies)


def test_a_value_that_is_not_a_fingerprint_at_all_is_reported(small_benchmark):
    dataset_root, catalog, task_ids, honest = small_benchmark
    path = sorted(key for key in honest if key.startswith("reference_files/"))[0]
    tampered = dict(honest)
    tampered[path] = "not a fingerprint"

    result = verify_input_file_versions(tampered, task_ids, catalog, dataset_root)

    assert any("is not a SHA-256 value" in note for note in result.problems)
    by_path = {check.path: check for check in result.checks}
    assert by_path[path].state == INPUT_FILE_NOT_CHECKED


# ── Where a copy may be looked for ─────────────────────────────────────────


def test_a_folder_named_on_purpose_is_preferred_over_the_download_cache(
    small_benchmark,
):
    dataset_root, catalog, _, honest = small_benchmark
    path = sorted(key for key in honest if key.startswith("reference_files/"))[0]

    found = locate_input_file(path, catalog, dataset_root)

    assert found == dataset_root / path


def test_a_copy_in_a_named_folder_is_read_rather_than_refused(small_benchmark):
    """A file sitting right there is evidence, and refusing it helps nobody."""
    dataset_root, catalog, _, _ = small_benchmark
    assert not path_folder_is_shaped_like_a_fingerprint(DATASET_DATA_FILE)

    found = locate_input_file(DATASET_DATA_FILE, catalog, dataset_root)

    assert found == dataset_root / DATASET_DATA_FILE


def test_a_disagreement_in_a_named_folder_is_not_called_tampering(
    small_benchmark,
):
    """A named folder promises no particular revision, so say only what is known.

    The data file's path says nothing about its contents, unlike a reference
    file's. If the copy in the folder disagrees with the written fingerprint,
    that folder may simply hold a different revision of the benchmark. Naming
    the written value as the wrong one would be a guess.
    """
    dataset_root, catalog, task_ids, honest = small_benchmark
    (dataset_root / DATASET_DATA_FILE).write_bytes(b"a different revision\n")

    result = verify_input_file_versions(honest, task_ids, catalog, dataset_root)

    assert any("different revision" in note for note in result.problems)
    assert not any("describes some other file" in note for note in result.problems)


def test_a_disagreement_about_a_reference_file_is_called_what_it_is(
    small_benchmark,
):
    """A reference file's path repeats its own fingerprint, so there is no doubt."""
    dataset_root, catalog, task_ids, honest = small_benchmark
    path = sorted(key for key in honest if key.startswith("reference_files/"))[0]
    (dataset_root / path).write_bytes(b"a different file altogether\n")

    result = verify_input_file_versions(honest, task_ids, catalog, dataset_root)

    assert any("describes some other file" in note for note in result.problems)


def test_nothing_is_looked_for_outside_the_pinned_revision(monkeypatch):
    """The download cache is asked about one revision, and told not to fetch."""
    asked = {}

    def fake_try_to_load_from_cache(**kwargs):
        asked.update(kwargs)
        return None

    import huggingface_hub

    monkeypatch.setattr(
        huggingface_hub, "try_to_load_from_cache", fake_try_to_load_from_cache
    )

    assert _copy_in_the_download_cache("owner/name", "e" * 40, "a/file.txt") is None
    assert asked == {
        "repo_id": "owner/name",
        "filename": "a/file.txt",
        "repo_type": "dataset",
        "revision": "e" * 40,
    }


def test_a_cache_answer_that_is_not_a_path_is_not_treated_as_one(monkeypatch):
    """The cache says "this revision has no such file" with a sentinel object."""
    sentinel = object()

    import huggingface_hub

    monkeypatch.setattr(
        huggingface_hub, "try_to_load_from_cache", lambda **_: sentinel
    )

    assert _copy_in_the_download_cache("owner/name", "e" * 40, "a/file.txt") is None


def test_a_damaged_cache_stops_the_check_rather_than_the_process(monkeypatch):
    import huggingface_hub

    def explode(**_):
        raise OSError("the cache folder is unreadable")

    monkeypatch.setattr(huggingface_hub, "try_to_load_from_cache", explode)

    assert _copy_in_the_download_cache("owner/name", "e" * 40, "a/file.txt") is None


# ── What the reader is shown ───────────────────────────────────────────────


def test_the_report_shows_how_each_file_was_checked_even_when_all_is_well(
    small_benchmark,
):
    dataset_root, catalog, task_ids, honest = small_benchmark
    plan = load_plan(PLAN_PATH)

    result = run_envelope_preflight(
        plan, root=BATCH_RUNNER_ROOT, dataset_root=dataset_root
    )
    lines = describe_input_file_checks(result)

    assert lines
    assert any("of 64 characters compared" in line for line in lines)


def test_the_written_report_carries_the_per_file_state(small_benchmark):
    """Every recorded state is one of the four this module can produce.

    Pointing the real plan at the small benchmark's root means one of its
    pinned files — the dataset's own data file — is found, read, and turns out
    to be the stand-in rather than the pinned revision. So this run really does
    produce a disagreement, and that is asserted rather than merely tolerated:
    until the disagreeing state existed, this exact case was written down as
    ``read the file``, indistinguishable from a file that checked out.
    """
    dataset_root, _, _, _ = small_benchmark
    plan = load_plan(PLAN_PATH)

    result = run_envelope_preflight(
        plan, root=BATCH_RUNNER_ROOT, dataset_root=dataset_root
    )

    written = result.as_dict()["input_files"]
    assert written
    seen = set()
    for environment, entry in written.items():
        assert "checks" in entry, environment
        for check in entry["checks"]:
            assert check["state"] in {
                INPUT_FILE_READ,
                INPUT_FILE_DISAGREED,
                INPUT_FILE_FOLDER_NAME_ONLY,
                INPUT_FILE_NOT_CHECKED,
            }
            seen.add((check["path"], check["state"]))

    assert (DATASET_DATA_FILE, INPUT_FILE_DISAGREED) in seen


def test_files_nobody_could_read_are_named_apart_but_still_refuse_a_start(
    tmp_path, no_download_cache
):
    """The machine-dependent answer is named, and still blocks.

    This is the state a build server is in: no download cache, so nothing to
    read. The notes must be reachable by name, so a test about something else
    can set them aside deliberately, and must still appear among the problems,
    so nobody reads the report as "the fingerprints checked out".
    """
    plan = load_plan(PLAN_PATH)

    result = run_envelope_preflight(
        plan, root=BATCH_RUNNER_ROOT, dataset_root=tmp_path / "nowhere"
    )

    assert result.missing_input_file_problems
    for note in result.missing_input_file_problems:
        assert "is on this machine" in note, note
        assert note in result.all_problems, note
    assert result.may_start is False


def test_what_was_named_apart_matches_what_went_unread(
    tmp_path, no_download_cache
):
    """The named list is derived from the per-file states, not written twice."""
    plan = load_plan(PLAN_PATH)

    result = run_envelope_preflight(
        plan, root=BATCH_RUNNER_ROOT, dataset_root=tmp_path / "nowhere"
    )

    unread = sum(
        len(verification.not_fully_checked)
        for verification in result.input_files.values()
    )
    assert unread == len(result.missing_input_file_problems)
    assert result.as_dict()["every_input_file_was_read"] is False


def test_a_wrong_fingerprint_stops_the_comparison_starting(small_benchmark):
    dataset_root, _, _, _ = small_benchmark
    plan = load_plan(PLAN_PATH)

    result = run_envelope_preflight(
        plan, root=BATCH_RUNNER_ROOT, dataset_root=dataset_root
    )

    assert not result.may_start


# ── The committed plan, checked against whatever this machine holds ────────


def test_the_committed_plan_is_either_read_in_full_or_says_it_was_not(
    small_benchmark,
):
    """No third answer. Either the files were read, or that is said out loud."""
    catalog = load_task_catalog()
    plan = load_plan(PLAN_PATH)
    entry = conditions_from_plan(plan)["host_python_process"]

    result = verify_input_file_versions(
        entry.input_file_versions, entry.task_ids, catalog
    )

    assert result.problems == (), result.problems
    if result.everything_was_read:
        assert result.missing_copies == ()
    else:
        assert result.missing_copies != ()


def test_the_committed_plan_pins_exactly_the_files_the_five_tasks_use():
    catalog = load_task_catalog()
    plan = load_plan(PLAN_PATH)
    entry = conditions_from_plan(plan)["host_python_process"]
    dataset_key = f"{catalog.dataset_repo_id}@{catalog.dataset_revision}"

    written = {str(key) for key in entry.input_file_versions}

    assert written - {dataset_key} == set(
        reference_files_for(entry.task_ids, catalog)
    )


def test_every_cross_reference_in_the_module_points_at_something_real(
    small_benchmark,
):
    """A cross-reference in prose is a claim, and claims get checked here.

    Writing this file, the module explanation was left pointing at a constant
    under a name it never had. Nobody would have noticed, which is the same
    reason nobody noticed the check was reading half a fingerprint.

    Every docstring in the file is read, not only the one at the top, because
    the first version of this test read only the top one and the next stale
    reference written into the file went into a field docstring instead.

    Builtins count as real. A docstring saying which exception a function
    raises points at ``ValueError``, which exists; calling that dangling would
    push writers into plain prose to appease a test, which is the wrong way
    round.
    """
    import builtins
    import dataclasses
    import re

    import core.execution_envelope_tasks as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    referenced = set(
        re.findall(
            r":(?:data|func|class|attr|meth):`([A-Za-z_][A-Za-z0-9_.]*)`", source
        )
    )
    classes = [
        value
        for value in vars(module).values()
        if isinstance(value, type) and getattr(value, "__module__", "") == module.__name__
    ]

    def member(holder, name):
        """A name on this holder, counting fields a dataclass declares.

        A field with no default is not an attribute of the class object, only
        of its instances, so ``getattr`` alone would call a perfectly real
        field a dangling reference.
        """
        found = getattr(holder, name, None)
        if found is not None:
            return found
        if dataclasses.is_dataclass(holder):
            for field in dataclasses.fields(holder):
                if field.name == name:
                    return field
        return None

    def resolves(name: str) -> bool:
        head, _, rest = name.partition(".")
        for holder in [module, builtins] + ([] if rest else classes):
            found = member(holder, head)
            if found is None:
                continue
            for step in rest.split(".") if rest else []:
                found = member(found, step)
                if found is None:
                    break
            else:
                return True
        return False

    assert len(referenced) >= 6, referenced
    assert sorted(name for name in referenced if not resolves(name)) == []


# ── The sweep: no character of any fingerprint may be changed unnoticed ────


def _tamper_variants(honest):
    """Every single-character change, at every position, on every fingerprint.

    Exhaustive rather than sampled, because the whole failure being fixed here
    was a range of positions nobody had looked at.
    """
    for key, original in sorted(honest.items()):
        for position in range(64):
            replacement = "1" if original[position] == "0" else "0"
            changed = dict(honest)
            changed[key] = (
                original[:position] + replacement + original[position + 1 :]
            )
            yield f"{key} position {position}", changed


def test_no_single_character_of_any_fingerprint_can_be_changed_unnoticed(
    small_benchmark,
):
    dataset_root, catalog, task_ids, honest = small_benchmark
    assert check_input_file_versions(honest, task_ids, catalog, dataset_root) == []

    missed = [
        name
        for name, changed in _tamper_variants(honest)
        if not check_input_file_versions(changed, task_ids, catalog, dataset_root)
    ]

    assert missed == []


def test_the_sweep_covers_all_sixty_four_positions_of_all_three_fingerprints(
    small_benchmark,
):
    """The sweep is only worth its result if it is as wide as it claims."""
    _, _, _, honest = small_benchmark

    variants = list(_tamper_variants(honest))

    assert len(variants) == 3 * 64


def test_half_a_fingerprint_swapped_for_another_real_one_is_caught(
    small_benchmark,
):
    """The change that used to pass: keep the folder's half, replace the rest."""
    dataset_root, catalog, task_ids, honest = small_benchmark
    donors = sorted(honest.values()) + [UNRELATED_FINGERPRINT]

    missed = []
    for key, original in sorted(honest.items()):
        for donor in donors:
            if donor == original:
                continue
            changed = dict(honest)
            changed[key] = original[:32] + donor[32:]
            if not check_input_file_versions(
                changed, task_ids, catalog, dataset_root
            ):
                missed.append(f"{key} second half from {donor[:8]}")

    assert missed == []


# ── Compared, and it disagreed, is its own answer ───────────────────────────
#
# The check has always caught a plan that pins the wrong file: the mismatch
# goes into ``problems`` and the run does not start. What it did not do was
# *record* the mismatch. A disagreeing file came back with the same state as a
# matching one — "read the file", 64 of 64 characters compared, read from
# <path> — so every summary built from those records counted it as checked.
#
# That is the failure this module's own docstring warns about, one case over:
# "a check that stayed quiet about it would be claiming to have done work it
# did not do". Here the work was done. The answer was the part that went
# missing.


def _disagreeing(benchmark):
    """A plan that pins a real fingerprint of some entirely different file."""
    dataset_root, catalog, task_ids, honest = benchmark
    path = sorted(key for key in honest if key.startswith("reference_files/"))[0]
    tampered = dict(honest)
    tampered[path] = hashlib.sha256(b"a completely different file\n").hexdigest()
    result = verify_input_file_versions(tampered, task_ids, catalog, dataset_root)
    return path, result


def test_a_disagreement_is_not_counted_as_a_fingerprint_that_checked_out(
    small_benchmark,
):
    """The regression itself.

    Before this was fixed, ``fully_checked`` held both files and
    ``everything_agreed`` did not exist — the only summary available said two
    of two, for a plan pinning a file that is not the one it names.
    """
    path, result = _disagreeing(small_benchmark)

    assert len(result.checks) == 3
    assert path not in [check.path for check in result.fully_checked]
    assert len(result.fully_checked) == 2
    assert [check.path for check in result.disagreements] == [path]
    assert not result.everything_agreed


def test_the_record_says_which_file_it_actually_read(small_benchmark):
    path, result = _disagreeing(small_benchmark)
    check = {item.path: item for item in result.checks}[path]

    assert check.state == INPUT_FILE_DISAGREED
    assert check.disagreed
    assert not check.fully_checked


def test_all_sixty_four_characters_are_still_reported_as_compared(small_benchmark):
    """Honest about the effort as well as the answer.

    Rounding ``characters_compared`` down to 0 on a disagreement would be the
    opposite error: it would say the machine could not tell, when it could and
    did. The count is what was compared; the state is what came of it.
    """
    path, result = _disagreeing(small_benchmark)
    check = {item.path: item for item in result.checks}[path]

    assert check.characters_compared == 64
    assert check.was_read


def test_being_able_to_read_every_file_is_kept_apart_from_liking_the_answer(
    small_benchmark,
):
    """Two questions, two properties, and the names have to mean it.

    ``everything_was_read`` is about whether this machine could look. A plan
    pinning the wrong file reads every byte of it, so the honest answer there
    is yes — which is exactly why it must not be the property anybody uses to
    decide the inputs are sound.
    """
    _, result = _disagreeing(small_benchmark)

    assert result.everything_was_read
    assert not result.everything_agreed


def test_the_honest_plan_still_answers_yes_to_both(small_benchmark):
    """The other side of the pair, so neither property is quietly always-False."""
    result = _verify(small_benchmark)

    assert result.everything_was_read
    assert result.everything_agreed
    assert result.disagreements == ()
    assert all(check.state == INPUT_FILE_READ for check in result.checks)


def test_a_disagreement_still_stops_the_run_exactly_as_before(small_benchmark):
    """No behaviour was changed — only what gets written down about it.

    This check has always blocked. If recording the outcome had also changed
    whether it blocks, that would be a new condition acting on work already
    under way, which is not what this fix is for.
    """
    path, result = _disagreeing(small_benchmark)

    assert any("describes some other file" in note for note in result.problems)
    assert result.missing_copies == ()
    assert any(path in note for note in result.all_notes)


def test_a_copy_that_was_only_pointed_at_also_records_the_disagreement(
    small_benchmark, tmp_path, no_download_cache
):
    """The hedged branch, where nothing promises which revision the folder holds.

    The wording of that problem is deliberately softer — it says the two
    disagree rather than naming a culprit. The recorded state is not softer,
    because the fingerprint is unproven either way.
    """
    _, catalog, task_ids, honest = small_benchmark
    path = "inputs/Costs.xlsx"
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "inputs").mkdir(parents=True)
    (elsewhere / path).write_bytes(b"some other revision of the costs\n")
    catalog = TaskCatalog(
        schema_version=catalog.schema_version,
        dataset_repo_id=catalog.dataset_repo_id,
        dataset_revision=catalog.dataset_revision,
        dataset_file_sha256=catalog.dataset_file_sha256,
        tasks=(_task("task-one", (path,)),),
    )
    written = {
        f"{catalog.dataset_repo_id}@{catalog.dataset_revision}": (
            catalog.dataset_file_sha256
        ),
        path: UNRELATED_FINGERPRINT,
    }

    result = verify_input_file_versions(written, ("task-one",), catalog, elsewhere)
    check = {item.path: item for item in result.checks}[path]

    assert not path_folder_is_shaped_like_a_fingerprint(path)
    assert check.state == INPUT_FILE_DISAGREED
    assert any("do not describe the same file" in note for note in result.problems)


def test_not_having_the_file_is_still_a_different_answer_from_disagreeing(
    small_benchmark, tmp_path, no_download_cache
):
    """The new state must not swallow the two that already existed.

    "I could not check" and "I checked and it is wrong" are different findings
    with different remedies — one is cleared by downloading the benchmark for
    nothing, the other by fixing the plan.
    """
    result = _verify(small_benchmark, root=tmp_path / "nowhere")

    assert result.disagreements == ()
    assert {check.state for check in result.checks} <= {
        INPUT_FILE_FOLDER_NAME_ONLY,
        INPUT_FILE_NOT_CHECKED,
    }
    assert result.missing_copies
    assert not result.everything_was_read


def test_the_published_record_carries_the_disagreement(small_benchmark):
    """``as_dict`` is what anything downstream reads, so it has to say it too."""
    path, result = _disagreeing(small_benchmark)

    written = result.as_dict()
    by_path = {check["path"]: check for check in written["checks"]}

    assert by_path[path]["state"] == INPUT_FILE_DISAGREED
    assert by_path[path]["characters_compared"] == 64
    assert written["problems"]


def test_the_printed_summary_does_not_read_as_reassurance(small_benchmark):
    """What a person about to authorise a bill actually sees.

    The old line was "2 of 2 input file(s) read off this machine and compared
    in full" — every word of it true, and the wrong impression entirely.
    """
    path, verification = _disagreeing(small_benchmark)
    result = dataclasses.replace(
        run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT),
        input_files={"docker_container": verification},
    )

    lines = describe_input_file_checks(result)
    summary = lines[0]
    for_that_file = [line for line in lines if path in line]

    assert "2 of 3" in summary
    assert "turned out to be a different file" in summary
    assert len(for_that_file) == 1
    assert INPUT_FILE_DISAGREED in for_that_file[0]
    assert "do not match" in for_that_file[0]


def test_the_old_record_would_be_caught_if_it_came_back(small_benchmark):
    """Proof that the tests above can fail.

    The regression is one word wide: return ``INPUT_FILE_READ`` instead of
    ``INPUT_FILE_DISAGREED`` and every assertion in this section goes quiet
    again. Rebuilding that record here, in memory, and insisting the summaries
    turn back into the misleading ones is what makes those assertions evidence
    rather than decoration.
    """
    path, result = _disagreeing(small_benchmark)
    as_it_used_to_be = dataclasses.replace(
        result,
        checks=tuple(
            dataclasses.replace(check, state=INPUT_FILE_READ)
            if check.disagreed
            else check
            for check in result.checks
        ),
    )

    assert as_it_used_to_be.everything_agreed
    assert as_it_used_to_be.disagreements == ()
    assert len(as_it_used_to_be.fully_checked) == 3
    # and the problem was there the whole time, which is why this went unnoticed
    assert as_it_used_to_be.problems == result.problems
    assert path in "".join(as_it_used_to_be.problems)
