"""An extension against a name is naming a file, not demanding a format.

``_required_primary_extensions`` decides what format a task is asking for, and
``select_deliverables`` refuses the whole task -- ``wrong_format_primary``,
every rubric item a judge error, a score of zero -- when nothing delivered
matches. Its patterns reach across the task with ``.*``, and ``_norm`` has
already folded the prompt and every rubric line into a single line, so the
``.*`` crosses sentences that have nothing to do with each other.

What it crosses into is usually a *reference input*: the file the task told the
model to read. Measured on the pinned revision, the widest of these matches ran
6,847 characters and ended on ``pm duties final.pdf`` -- a PDF the task supplies
-- on a task whose own first rubric line reads "Deliverable is a Word document".

The cost, measured rather than argued:

* On the 185 gold-bearing tasks, **six** had the benchmark's own expert answer
  called the wrong format. A gold answer is the format the task wanted by
  definition, so all six were the inference being wrong, and each lost its
  whole task: 268 rubric items, 427 points, 3.01 per cent of the corpus.
* On the committed paid 220-task run ``exp003_GPT52Chat_baseline_runner_exec``
  the same guard fired 12 times, every one scoring 0.0 or 0.01. Comparing each
  against that task's own first rubric line: **six agreed and six did not**.

The rule that separates the two readings is that a format demand writes the
extension on its own -- "as a single .pdf", "in .pptx format" -- and a filename
writes it against a name: ``pm duties final.pdf``,
``territory_fit_report_ref_(3).xlsx``. Requiring whitespace in front is the
whole change. It cannot widen an inference, so it cannot make the guard fire
anywhere it does not fire today.

Nothing here calls a model, marks anything, or spends anything.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.deliverable_selector import (  # noqa: E402
    _required_primary_extensions,
    select_deliverables,
)


def _path(task: str, name: str) -> str:
    return f"deliverable_files/{task}/{name}"


def _ref_url(name: str) -> str:
    encoded = name.replace(" ", "%20")
    return (
        "https://huggingface.co/datasets/openai/gdpval/resolve/main/"
        f"reference_files/hash/{encoded}"
    )


# ── The rule itself ───────────────────────────────────────────────────────

# Verbatim from the pinned revision. Each is one rubric line from a task whose
# gold answer is a different format from the one this line used to imply, and
# each names a reference input the task supplies.
FILENAMES_IN_REAL_RUBRIC_LINES = [
    pytest.param(
        "Includes any details that materially contradicts what is found in "
        "PM Duties FINAL.pdf",
        ".pdf",
        id="1e5a1d7f-a-supplied-pdf-on-a-task-answered-in-word",
    ),
    pytest.param(
        "All figures (counts, durations) are derived from the provided "
        "'Inventory Incident Report FINAL.xlsx'",
        ".xlsx",
        id="552b7dd0-a-supplied-workbook-on-a-task-answered-in-powerpoint",
    ),
    pytest.param(
        "Includes a brief assumptions/notes section indicating sources "
        "(e.g., “Pricing Email.docx”)",
        ".docx",
        id="15d37511-a-supplied-letter-on-a-task-answered-in-a-workbook",
    ),
    pytest.param(
        "Each flyer contains one of the eligible homes listed in "
        "Massabama Active Listings.xlsx",
        ".xlsx",
        id="11593a50-a-supplied-workbook-on-a-task-answered-in-pdf",
    ),
    pytest.param(
        "No numeric values or rankings in the presentation contradict the "
        "aggregations computed from territory_fit_report_ref_(3).xlsx",
        ".xlsx",
        id="a69be28f-a-bracket-before-the-dot-is-still-a-filename",
    ),
]


@pytest.mark.parametrize("line,extension", FILENAMES_IN_REAL_RUBRIC_LINES)
def test_an_extension_written_against_a_name_is_not_a_format_demand(
    line: str, extension: str
) -> None:
    """The trigger word is present; the extension belongs to a filename."""
    text = f"Produce the final deliverable for the client. {line}"
    assert extension not in _required_primary_extensions(text)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("The deliverable must be a single .pdf", ".pdf"),
        ("Deliver exactly one .xlsx workbook", ".xlsx"),
        ("The final file is a .docx", ".docx"),
        ("Delivers the deliverable as a file in .pptx format", ".pptx"),
        ("Package all content as a single .zip", ".zip"),
    ],
)
def test_an_extension_standing_on_its_own_is_still_a_format_demand(
    text: str, expected: str
) -> None:
    assert expected in _required_primary_extensions(text)


def test_the_extension_at_the_very_start_of_a_line_still_counts():
    """There is no character in front of it at all, which is not a name."""
    assert ".ipynb" in _required_primary_extensions(".ipynb is required")


# ── What the ``.*`` was reaching across ───────────────────────────────────


def test_a_trigger_word_cannot_reach_a_filename_in_a_different_sentence():
    """The measured failure: 6,847 characters between the two.

    ``_norm`` makes the prompt and every rubric line one line, so nothing in
    the pattern stops ``final`` here from meeting ``.pdf`` there. Both halves
    are innocent; the join is the defect.
    """
    text = (
        "Build the final schedule chart for the maintenance team. "
        + "Cover every asset class and note the intervals. " * 40
        + "Includes any details that materially contradicts what is found in "
        "PM Duties FINAL.pdf"
    )
    assert _required_primary_extensions(text) == set()


def test_the_same_sentence_with_the_extension_freed_still_demands_the_format():
    """The join is the defect, not the distance. Distance alone is allowed."""
    text = (
        "Build the final schedule chart for the maintenance team. "
        + "Cover every asset class and note the intervals. " * 40
        + "The deliverable must be a single .pdf"
    )
    assert _required_primary_extensions(text) == {".pdf"}


# ── End to end, on the six gold answers that were refused ─────────────────

# task id, what the task supplies, what the expert answer is, the rubric line
# that used to decide the format, and that task's own first rubric line.
GOLD_ANSWERS_THAT_WERE_CALLED_THE_WRONG_FORMAT = [
    pytest.param(
        "1e5a1d7f",
        "PM Duties (1).pdf",
        "PM Schedule Chart.docx",
        "Includes any details that materially contradicts what is found in "
        "PM Duties FINAL.pdf",
        "Deliverable is a Word document",
        id="1e5a1d7f-word",
    ),
    pytest.param(
        "552b7dd0",
        "Inventory Incident Report FINAL.xlsx",
        "Inventory Incident Reports FINAL.pptx",
        "All figures (counts, durations) are derived from the provided "
        "'Inventory Incident Report FINAL.xlsx'",
        "Delivers a PowerPoint presentation file in .pptx format that opens "
        "without errors",
        id="552b7dd0-powerpoint",
    ),
    pytest.param(
        "15d37511",
        "Pricing Email.docx",
        "GloNGroRealEstate Marketplace Pro Forma.xlsx",
        "Includes a brief assumptions/notes section indicating sources "
        "(e.g., “Pricing Email.docx”)",
        "The deliverable is provided in a spreadsheet format (e.g., Excel, "
        "CSV, or equivalent).",
        id="15d37511-spreadsheet",
    ),
    pytest.param(
        "11593a50",
        "Massabama Active Listings.xlsx",
        "Massabama Home Flyers.pdf",
        "Each flyer contains one of the eligible homes listed in "
        "Massabama Active Listings.xlsx",
        "Creates a pdf document",
        id="11593a50-pdf",
    ),
    pytest.param(
        "a69be28f",
        "Territory Fit Report REF (3).xlsx",
        "Territory Fit Deck.pdf",
        "No numeric values or rankings in the presentation contradict the "
        "aggregations computed from territory_fit_report_ref_(3).xlsx",
        "The deliverable is a multi-slide presentation exported to PDF "
        "format.",
        id="a69be28f-pdf",
    ),
]


@pytest.mark.parametrize(
    "task,reference,gold,filename_line,first_line",
    GOLD_ANSWERS_THAT_WERE_CALLED_THE_WRONG_FORMAT,
)
def test_the_expert_answer_is_no_longer_refused_for_its_format(
    task: str, reference: str, gold: str, filename_line: str, first_line: str
) -> None:
    """A gold answer is the format the task wanted. It cannot be the wrong one."""
    selection = select_deliverables(
        task_id=task,
        deliverable_files=[_path(task, gold), _path(task, reference)],
        reference_file_urls=[_ref_url(reference)],
        instruction="Produce the final deliverable described below.",
        rubric_items=[
            {"criterion": first_line, "score": 3},
            {"criterion": filename_line, "score": 2},
        ],
    )

    assert selection.selection_status != "wrong_format_primary", (
        selection.selection_error
    )
    assert selection.primary_targets, "the task must have something to grade"
    assert {
        path.rsplit("/", 1)[-1]
        for target in selection.primary_targets
        for path in target.paths
    } == {gold}


def test_the_supplied_file_is_still_kept_out_of_what_gets_graded():
    """Not refusing must not turn a reference input into a deliverable."""
    task, reference, gold = (
        "11593a50",
        "Massabama Active Listings.xlsx",
        "Massabama Home Flyers.pdf",
    )
    selection = select_deliverables(
        task_id=task,
        deliverable_files=[_path(task, gold), _path(task, reference)],
        reference_file_urls=[_ref_url(reference)],
        instruction="Produce the final deliverable described below.",
        rubric_items=[
            {"criterion": "Creates a pdf document", "score": 3},
            {
                "criterion": "Each flyer contains one of the eligible homes "
                "listed in Massabama Active Listings.xlsx",
                "score": 2,
            },
        ],
    )
    assert _path(task, reference) in selection.reference_files_excluded
    assert _path(task, reference) not in [
        path for target in selection.primary_targets for path in target.paths
    ]


# ── The guard keeps its teeth ─────────────────────────────────────────────


def test_a_task_that_really_asks_for_one_format_still_refuses_another():
    """The six the guard was right about must stay refused.

    Otherwise this trades one silent loss for another.
    """
    selection = select_deliverables(
        task_id="really-wants-a-workbook",
        deliverable_files=[_path("really-wants-a-workbook", "Summary.docx")],
        instruction="Deliver a single Excel workbook of the quarter's figures.",
        rubric_items=[
            {"criterion": "Provides a single Excel workbook.", "score": 3}
        ],
    )
    assert selection.selection_status == "wrong_format_primary"
    assert selection.primary_targets == []


def test_the_change_can_only_narrow_an_inference_never_widen_one():
    """Whitespace in front is a restriction, so no text can gain a format.

    This is what bounds the blast radius: a run cannot start refusing a task it
    accepts today. Measured across all 220 tasks of the pinned revision, no
    task gained a format and none was newly refused.
    """
    permissive_alternatives = [
        "single pdf",
        "single word file",
        "single excel workbook",
        "single powerpoint",
        "single zip",
        "wav file",
        "mp4 video",
        "python notebook",
    ]
    for text in permissive_alternatives:
        assert _required_primary_extensions(text), (
            f"{text!r} names a format in words and must keep working"
        )
