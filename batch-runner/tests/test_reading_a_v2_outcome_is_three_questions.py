"""The outcome reader, checked against defects made by hand before any run.

``experiment-design`` §5 asks who validates the judge. Here the judge is not a
model -- nothing in this run marks an answer -- but the logic that decides what
a task's ending *was* is a judge all the same, and its failures are the quiet
kind: a task counted as done because a file exists, a task counted as failed
because a validator was not installed.

So every case below is built rather than observed. A refusal notice that opens
cleanly, a ``finalize`` whose file was short-written, a spreadsheet that is a
zip of nothing, a format with no validator in this venv. Each one is a shape a
real run can produce, and each is put through the reader before a model is
asked anything.

The property under test is separation. ``finalize`` accepted, a usable file,
and the work being any good are three answers, they disagree in both
directions, and the reader never lets one stand in for another.

Offline, and free. Nothing here calls a model or a backend.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

import pytest

from core.agentic_v2_outcome import (
    FINALIZE_ACCEPTED,
    FINALIZE_ENDED_FIRST,
    FINALIZE_NOT_CALLED,
    Outcome,
    count_separately,
    read_outcome,
    refusal_phrase_in,
)

#: What a model writes when it cannot do the task. Opens cleanly, is not empty,
#: and is not an answer.
A_REFUSAL_NOTICE = (
    "I was unable to complete this analysis because the reference workbook "
    "could not be opened in this environment.\n"
)

#: A real answer, for the contrast. Says nothing about whether it is correct.
AN_ANSWER = (
    "## Q3 capital plan\n\nThe three sites are ranked below by payback "
    "period, with the assumptions listed under each.\n"
)


def _succeeded(**changed: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "success": True,
        "text": "",
        "deliverable_text": AN_ANSWER,
        "files": [],
        "error": None,
    }
    record.update(changed)
    return record


def _failed(error: str, **changed: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "success": False,
        "text": "",
        "deliverable_text": "",
        "files": [],
        "error": error,
    }
    record.update(changed)
    return record


def _write(root: Path, name: str, content: bytes | str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# Question 1: was finalize accepted
# ---------------------------------------------------------------------------


def test_a_successful_record_is_a_finalize_that_was_accepted(tmp_path):
    outcome = read_outcome("t1", _succeeded())
    assert outcome.finalize == FINALIZE_ACCEPTED
    assert outcome.finalize_was_accepted is True
    assert outcome.error_type is None


def test_the_runners_own_name_for_never_finalising_is_kept_apart(tmp_path):
    """``finalize_not_called`` is its own ending and not a generic failure."""
    outcome = read_outcome("t2", _failed("finalize_not_called"))
    assert outcome.finalize == FINALIZE_NOT_CALLED
    assert outcome.finalize_was_accepted is False


@pytest.mark.parametrize(
    "error",
    ["tool_budget_exhausted", "compute_backend_error", "task_wall_time_exhausted"],
)
def test_a_run_that_ended_first_is_not_counted_as_never_finalising(error):
    """A ceiling and a model that talked itself out are different failures.

    Folding them together would put a harness defect and a model behaviour in
    the same column, which is the distinction the whole corrected-harness run
    is about.
    """
    outcome = read_outcome("t3", _failed(error))
    assert outcome.finalize == FINALIZE_ENDED_FIRST
    assert outcome.error_type == error


# ---------------------------------------------------------------------------
# Question 2: is there a real file
# ---------------------------------------------------------------------------


def test_a_finalize_whose_file_was_short_written_is_not_a_usable_file(tmp_path):
    """(1) yes, (2) no. The case a single ``status`` word cannot hold.

    A collection that meets a full disk between two files leaves a directory
    that looks like a finished task with fewer deliverables.
    """
    empty = _write(tmp_path, "answer.md", "")
    outcome = read_outcome(
        "t4", _succeeded(), collected_paths=[empty], collection_root=tmp_path
    )

    assert outcome.finalize_was_accepted is True
    assert outcome.produced_a_usable_file is False
    assert outcome.files[0].size_bytes == 0


def test_a_named_file_that_never_arrived_is_reported_as_missing(tmp_path):
    outcome = read_outcome(
        "t5",
        _succeeded(),
        collected_paths=[tmp_path / "never-written.xlsx"],
        collection_root=tmp_path,
    )
    verdict = outcome.files[0]
    assert verdict.exists is False
    assert verdict.is_usable is False
    assert outcome.produced_a_usable_file is False


def test_a_spreadsheet_that_is_not_one_fails_to_open(tmp_path):
    """The extension claims a format; the bytes have to back it.

    Built as a zip with nothing in it, because that is the shape a truncated
    or half-written ``.xlsx`` really takes -- a plain text file with an xlsx
    name would be caught by anything.
    """
    path = tmp_path / "model.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("not-a-workbook.txt", "nothing here")

    outcome = read_outcome(
        "t6", _succeeded(), collected_paths=[path], collection_root=tmp_path
    )
    assert outcome.files[0].openable is not True
    assert outcome.produced_a_usable_file is False

    # In a venv that has the library, "not True" is specifically False rather
    # than "not checked" -- so this case is not quietly passing because nothing
    # looked at the bytes.
    pytest.importorskip("openpyxl")
    assert outcome.files[0].openable is False
    assert outcome.files[0].problems


def test_a_real_text_file_is_usable(tmp_path):
    path = _write(tmp_path, "answer.md", AN_ANSWER)
    outcome = read_outcome(
        "t7", _succeeded(), collected_paths=[path], collection_root=tmp_path
    )
    assert outcome.files[0].is_usable is True
    assert outcome.produced_a_usable_file is True


def test_a_format_with_no_validator_is_not_checked_rather_than_good(tmp_path):
    """Three-valued, and it stays three-valued.

    ``openable is None`` means nobody looked. Counting it as usable would
    report a thin venv as a good result; counting it as broken would report one
    as a bad model. It gets its own column.
    """
    path = _write(tmp_path, "answer.sldprt", b"\x00\x01binary\x02")
    outcome = read_outcome(
        "t8", _succeeded(), collected_paths=[path], collection_root=tmp_path
    )

    verdict = outcome.files[0]
    assert verdict.openable is None
    assert verdict.is_usable is False
    assert outcome.files_not_checked == (verdict,)


def test_a_file_outside_the_collection_is_refused(tmp_path):
    """A path that escapes the collection root is not this task's deliverable."""
    outside = _write(tmp_path, "elsewhere/answer.md", AN_ANSWER)
    root = tmp_path / "collection"
    root.mkdir()

    outcome = read_outcome(
        "t9", _succeeded(), collected_paths=[outside], collection_root=root
    )
    assert outcome.files[0].is_usable is False
    assert outcome.files[0].problems


# ---------------------------------------------------------------------------
# Question 3: not measured, and not accidentally answered
# ---------------------------------------------------------------------------


def test_quality_is_never_answered(tmp_path):
    path = _write(tmp_path, "answer.md", AN_ANSWER)
    outcome = read_outcome(
        "t10", _succeeded(), collected_paths=[path], collection_root=tmp_path
    )

    assert outcome.quality is None
    assert "no judge is run" in outcome.quality_not_measured_because
    assert outcome.as_row()["quality"] is None


def test_a_refusal_notice_passes_one_and_two_and_is_flagged(tmp_path):
    """The case this module exists for.

    ``finalize`` accepted, a non-empty file that opens cleanly as text, and no
    work done. Everything a pipeline can see says success.
    """
    path = _write(tmp_path, "answer.md", A_REFUSAL_NOTICE)
    outcome = read_outcome(
        "t11",
        _succeeded(deliverable_text=A_REFUSAL_NOTICE),
        collected_paths=[path],
        collection_root=tmp_path,
    )

    assert outcome.finalize_was_accepted is True
    assert outcome.produced_a_usable_file is True
    assert outcome.reads_like_a_refusal_notice == "i was unable to"
    assert outcome.quality is None


def test_a_real_answer_is_not_flagged(tmp_path):
    outcome = read_outcome("t12", _succeeded(deliverable_text=AN_ANSWER))
    assert outcome.reads_like_a_refusal_notice is None


def test_the_flag_reads_the_opening_only():
    """A phrase quoted deep inside a long answer is not a refusal notice."""
    buried = AN_ANSWER + "x" * 2000 + "I was unable to reach the 2019 filing."
    assert refusal_phrase_in(buried) is None
    assert refusal_phrase_in("I was unable to " + buried) == "i was unable to"


def test_not_being_flagged_is_not_evidence_of_quality(tmp_path):
    """Stated as a test so that the absence of a flag is never read as a pass.

    A model can fail a task in fluent prose, and this list is short on purpose.
    The flag only ever adds a warning; it never grants one.
    """
    path = _write(tmp_path, "answer.md", "The answer is 4.\n")
    outcome = read_outcome(
        "t13",
        _succeeded(deliverable_text="The answer is 4.\n"),
        collected_paths=[path],
        collection_root=tmp_path,
    )
    assert outcome.reads_like_a_refusal_notice is None
    assert outcome.quality is None


# ---------------------------------------------------------------------------
# The three are never summed
# ---------------------------------------------------------------------------


def test_an_outcome_has_no_truth_value(tmp_path):
    outcome = read_outcome("t14", _succeeded())
    with pytest.raises(TypeError, match="three answers"):
        bool(outcome)
    with pytest.raises(TypeError):
        if outcome:  # pragma: no cover - the raise is the assertion
            pass


def test_the_tallies_share_one_denominator_and_stay_apart(tmp_path):
    """Thirty in, thirty reported three times over, no rate produced."""
    good = _write(tmp_path, "good/answer.md", AN_ANSWER)
    refusing = _write(tmp_path, "refusing/answer.md", A_REFUSAL_NOTICE)

    outcomes = [
        read_outcome(
            "done",
            _succeeded(),
            collected_paths=[good],
            collection_root=tmp_path,
        ),
        read_outcome(
            "refused",
            _succeeded(deliverable_text=A_REFUSAL_NOTICE),
            collected_paths=[refusing],
            collection_root=tmp_path,
        ),
        read_outcome("ceiling", _failed("tool_budget_exhausted")),
        read_outcome("silent", _failed("finalize_not_called")),
    ]

    counted = count_separately(outcomes)
    assert counted["tasks"] == 4
    assert counted["finalize_accepted"] == 2
    assert counted["finalize_not_called"] == 1
    assert counted["finalize_ended_first"] == 1
    assert counted["produced_a_usable_file"] == 2
    assert counted["read_like_a_refusal_notice"] == 1
    assert counted["quality_measured"] == 0

    # The two that produced a file are not two tasks done: one of them is the
    # model saying it could not. Nothing in the tally claims otherwise.
    assert "not whether it is right" in counted["quality_note"]


def test_a_task_that_never_ran_is_in_the_denominator(tmp_path):
    """Not dropped, and not counted as a failure of the model either."""
    never = read_outcome("never", _failed("compute_start_failed"))
    counted = count_separately([never])
    assert counted["tasks"] == 1
    assert counted["finalize_accepted"] == 0
    assert counted["produced_a_usable_file"] == 0
    assert never.error_type == "compute_start_failed"


def test_the_row_puts_the_three_side_by_side_without_deriving_one(tmp_path):
    path = _write(tmp_path, "answer.md", A_REFUSAL_NOTICE)
    row = read_outcome(
        "t15",
        _succeeded(deliverable_text=A_REFUSAL_NOTICE),
        collected_paths=[path],
        collection_root=tmp_path,
    ).as_row()

    assert row["finalize"] == FINALIZE_ACCEPTED
    assert row["files_usable"] == 1
    assert row["reads_like_a_refusal_notice"] == "i was unable to"
    assert row["quality"] is None
    assert "status" not in row, (
        "a single status word is what this module exists to replace"
    )


def test_the_outcome_is_frozen(tmp_path):
    outcome = read_outcome("t16", _succeeded())
    with pytest.raises(Exception):
        outcome.finalize = FINALIZE_NOT_CALLED  # type: ignore[misc]
    assert isinstance(outcome, Outcome)
