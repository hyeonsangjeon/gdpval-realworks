"""Four file shapes the selector used to refuse or hide, and the lines it holds.

exp036 (GPT-5.6 Sol, five tasks) lost two whole tasks and nine items to the
selector before any judge was called:

* 02aa1805 -- a workbook and the requested email saved as ``.eml``. ``.eml``
  was not document-like, so one document plus one unknown file fell through
  to ``ambiguous_candidates``: 71 items, 86 points, never judged.
* 0112fc9b -- one SOAP note saved as ``.docx`` and as a same-name ``.html``,
  no format requested, no PDF to fall back on: ``format_variant_no_match``,
  55 items, 66 points. The same rule refused seven of GPT-5.4's exp035 tasks.
* 3baa0009 -- "Accompany the article with a JPG chart". The chart was an
  image, images are always support, support is never rendered, so the nine
  chart items (11 points) were excluded for want of anything to look at --
  for both models.
* One document beside a preview page, a script or a vector file under another
  name falls through to ``ambiguous_candidates`` for the same reason as the
  ``.eml``.

The shapes below are taken from those tasks. Rubric lines are synthetic except
where a test says it quotes one. Nothing here calls a model.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.deliverable_selector import (  # noqa: E402
    DOCUMENT_EXTENSIONS,
    RENDITION_ORDER,
    WORD_EXTENSIONS,
    plan_targets_for_criterion,
    select_deliverables,
)


def _p(task: str, name: str) -> str:
    return f"deliverable_files/{task}/{name}"


def _select(task, names, criteria, instruction=""):
    return select_deliverables(
        task_id=task,
        deliverable_files=[_p(task, name) for name in names],
        instruction=instruction,
        rubric_items=[{"criterion": c, "score": 1} for c in criteria],
    )


def _names(paths):
    return [path.rsplit("/", 1)[-1] for path in paths]


def _primaries(selection):
    return [_names(t.paths)[0] for t in selection.primary_targets]


# ── F1: an email saved as .eml is a document ─────────────────────────────

EMAIL = "Email_to_Manager_Well_Recommendations.eml"
WORKBOOK = "Illinois_Green_Hydrogen_Well_Screening.xlsx"
EMAIL_CRITERIA = [
    "Provides an email to the manager recommending wells with the Excel attached.",
    "The email names each recommended well by water system and well ID.",
    "If the second worksheet contains two or more rows, the email highlights at least two wells.",
    "The workbook has a second tab listing only the potential wells.",
    "Overall formatting and style of the deliverable",
]


def test_an_email_message_beside_the_workbook_is_graded_not_refused():
    selection = _select("02aa1805", [EMAIL, WORKBOOK], EMAIL_CRITERIA)

    assert ".eml" in DOCUMENT_EXTENSIONS
    assert selection.selection_status == "ok"
    assert selection.task_class == "separate_equivalent"
    assert selection.selection_rule == "set_diff_then_separate_primaries"
    assert _primaries(selection) == [EMAIL, WORKBOOK]


def test_email_criteria_reach_the_message_and_sheet_criteria_still_reach_the_workbook():
    selection = _select("02aa1805", [EMAIL, WORKBOOK], EMAIL_CRITERIA)
    plans = [plan_targets_for_criterion(selection, c) for c in EMAIL_CRITERIA]

    assert plans[0].target_scope == "manifest"
    assert plans[1].target_scope == "file_target"
    assert _names(plans[1].selected_paths) == [EMAIL]
    # Names both the email and the worksheet: the judge gets both files.
    assert plans[2].target_scope == "primary_bundle"
    assert _names(plans[2].selected_paths) == [EMAIL, WORKBOOK]
    assert _names(plans[3].selected_paths) == [WORKBOOK]
    assert plans[4].target_scope == "split_children"


@pytest.mark.parametrize("criterion", EMAIL_CRITERIA + [
    "The memo opens with a one-line summary.",
    "The letter is addressed to the plant manager.",
    "Each tab uses frozen header rows.",
])
def test_an_eml_email_is_routed_exactly_as_the_same_email_saved_as_docx(criterion):
    # exp003 answered this task with a .docx email and was graded; the same
    # message saved as .eml must reach the same items.
    def plan(ext):
        stem = EMAIL[: -len(".eml")]
        selection = _select("02aa1805", [stem + ext, WORKBOOK], EMAIL_CRITERIA)
        result = plan_targets_for_criterion(selection, criterion)
        return result.target_scope, [n.replace(stem + ext, "EMAIL") for n in _names(result.selected_paths)]

    assert plan(".eml") == plan(".docx")


def test_an_email_is_not_a_word_file_when_a_word_file_is_required():
    # .eml shares the Word routing words, not the Word family: it must not
    # satisfy a requested .docx, or be picked by the single-family checks.
    assert ".eml" not in WORD_EXTENSIONS
    selection = _select(
        "word-required", ["Memo.eml"],
        ["The deliverable must be a Word (.docx) document."],
    )
    assert selection.selection_status == "wrong_format_primary"


def test_an_outlook_msg_is_never_a_primary():
    # Binary OLE that nothing in the grader can read. Beside a workbook it is
    # a support file; beside a same-name readable copy it is the copy set aside.
    beside_workbook = _select("msg", [WORKBOOK, "Email_to_Manager.msg"], EMAIL_CRITERIA)
    assert beside_workbook.selection_status == "ok"
    assert _primaries(beside_workbook) == [WORKBOOK]
    assert _names(beside_workbook.support_artifacts) == ["Email_to_Manager.msg"]

    beside_copy = _select("msg", ["Email_to_Manager.docx", "Email_to_Manager.msg"], EMAIL_CRITERIA)
    assert beside_copy.selection_status == "ok"
    assert _primaries(beside_copy) == ["Email_to_Manager.docx"]
    assert _names(beside_copy.support_artifacts) == ["Email_to_Manager.msg"]


# ── F2: a same-name copy in another rendition is set aside, by fixed order ──

def test_a_same_name_html_copy_no_longer_refuses_the_note():
    # 0112fc9b: no format requested, no PDF to fall back on.
    selection = _select(
        "0112fc9b",
        ["CS_SOAP_Note_2024-03-01.docx", "CS_SOAP_Note_2024-03-01.html"],
        ["The note documents the mechanism of injury."],
        instruction="Please create a SOAP note for the visit.",
    )

    assert selection.selection_status == "ok"
    assert selection.selection_rule == "set_diff_single+rendition_copies"
    assert _primaries(selection) == ["CS_SOAP_Note_2024-03-01.docx"]
    assert _names(selection.support_artifacts) == ["CS_SOAP_Note_2024-03-01.html"]


def test_a_csv_export_gives_way_to_its_workbook_and_nothing_else_moves():
    # 15d37511 (exp035): the .csv is the only file set aside.
    stem = "GloNGroRealEstate_Year1_Revenue_Gross_Margin_Projection"
    selection = _select(
        "15d37511",
        [stem + ".csv", stem + ".xlsx", "build_glongro_projection.py", "extracted/pricing-image.png"],
        ["Provides a revenue projection for year one."],
    )

    assert selection.selection_status == "ok"
    assert selection.selection_rule.endswith("+rendition_copies")
    assert stem + ".xlsx" in _primaries(selection)
    assert stem + ".csv" in _names(selection.support_artifacts)
    assert stem + ".csv" not in _primaries(selection)


def test_each_html_copy_gives_way_to_its_own_pdf():
    # 9a8c8e28 (exp035): three documents, each left as .html and .pdf. The PDF
    # fallback wanted exactly one PDF and found three.
    docs = ["editorial-accessibility-checklist", "editorial-accessibility-guide", "editorial-accessibility-quiz"]
    names = ["accessibility-docs.css"] + [d + ext for d in docs for ext in (".html", ".pdf")]
    selection = _select("9a8c8e28", names, ["The guide explains alt text."])

    assert selection.selection_status == "ok"
    assert sorted(_primaries(selection)) == [d + ".pdf" for d in docs]
    assert sorted(_names(selection.support_artifacts)) == sorted(
        ["accessibility-docs.css"] + [d + ".html" for d in docs]
    )


def test_only_the_copy_is_set_aside_never_the_other_documents():
    # 1aecc095 (exp035). Picking one file for the whole task would have left a
    # lone .txt; setting aside only the copy keeps all three Word documents.
    names = [
        "MA Telehealth Workflow Email.docx",
        "MA Telehealth Workflow Email.txt",
        "Telehealth Roadmap.docx",
        "Telehealth Workflow.docx",
    ]
    selection = _select("1aecc095", names, ["The roadmap lists three phases."])

    assert selection.selection_status == "ok"
    assert sorted(_primaries(selection)) == sorted(n for n in names if n.endswith(".docx"))
    assert _names(selection.support_artifacts) == ["MA Telehealth Workflow Email.txt"]


@pytest.mark.parametrize(
    "names,criteria",
    [
        # 0e386e32 (exp035): same name, different folders -- two source files.
        (
            ["frontend/index.html", "relayer/src/index.ts", "app-codebase.zip", "app-submission.zip"],
            ["Submission is a single ZIP archive that contains the complete codebase."],
        ),
        # 7de33b48 (exp035): a component, its stylesheet and the package.
        (
            ["ScreenReaderStatusMessage.css", "ScreenReaderStatusMessage.tsx", "screen-reader-status-message.zip"],
            ["The zip archive contains a top-level file named README.md."],
        ),
        # A workbook and a memo that share a name are two deliverables.
        (["Budget.docx", "Budget.xlsx"], ["The memo explains the budget."]),
        # Two files of one format are two files.
        (["Report.docx", "report.docx", "report.md"], ["The report has a summary."]),
    ],
    ids=["other-folder", "source-files", "cross-family", "same-format"],
)
def test_distinct_files_that_share_a_name_are_never_set_aside(names, criteria):
    selection = _select("distinct", names, criteria)

    assert selection.selection_status == "selection_error"
    assert selection.selection_rule == "format_variant_no_match"
    assert sorted(_names(selection.support_artifacts)) == sorted(_names(names))


def test_a_requested_format_outranks_the_fixed_order():
    # PDF ranks first, but the task asks for Word: each document keeps its
    # .docx. Ranking by the fixed order alone would keep the PDFs and then
    # fail the Word requirement, so the refusal would stand.
    selection = _select(
        "word-wins",
        ["a.docx", "a.pdf", "b.docx", "b.pdf"],
        ["The deliverable must be a Word (.docx) document."],
    )

    assert selection.selection_status == "ok"
    assert sorted(_primaries(selection)) == ["a.docx", "b.docx"]
    assert sorted(_names(selection.support_artifacts)) == ["a.pdf", "b.pdf"]


# Quoted from 2c249e0f (openai/gdpval@11e7900c), one of exp037's first 25.
DATA_FLOW_PROMPT = (
    "Deliver an OpenAPI 3.0+ specification in YAML format. Also, include a text file "
    "called data_flow.txt that describes the expected data flow and how robots will use them."
)
DATA_FLOW_LINE = (
    "A text file named data_flow.txt (or a close variant) is included and describes the "
    "expected data flow and how robots use the API"
)
DATA_FLOW_FILES = ["data_flow.txt", "data_flow.docx", "robot_data_upload_api.yaml"]


def test_the_text_file_the_task_asks_for_is_graded_not_its_word_twin():
    # Ranked by the fixed order alone, the .docx was kept and the judge was
    # asked whether the text file exists while it could open only the Word file.
    selection = _select("2c249e0f", DATA_FLOW_FILES, [DATA_FLOW_LINE], instruction=DATA_FLOW_PROMPT)

    assert selection.selection_status == "ok"
    assert selection.selection_rule == "set_diff_then_separate_primaries+rendition_copies"
    assert _primaries(selection) == ["data_flow.txt", "robot_data_upload_api.yaml"]
    assert _names(selection.support_artifacts) == ["data_flow.docx"]
    plan = plan_targets_for_criterion(selection, DATA_FLOW_LINE)
    assert plan.target_scope == "file_target"
    assert _names(plan.selected_paths) == ["data_flow.txt"]

    # The same files under a task that names neither format: the fixed order.
    unnamed = _select(
        "2c249e0f", DATA_FLOW_FILES, ["The API covers uploads."],
        instruction="Deliver an OpenAPI specification.",
    )
    assert _primaries(unnamed) == ["data_flow.docx", "robot_data_upload_api.yaml"]
    assert _names(unnamed.support_artifacts) == ["data_flow.txt"]


@pytest.mark.parametrize(
    "names,instruction,kept,kept_unnamed",
    [
        (["notes.txt", "notes.docx"], "Save the notes as a plain text file.",
         ["notes.txt"], ["notes.docx"]),
        # 854f3814's request, quoted.
        (["instructions.md", "instructions.docx", "query.overpassql"],
         "Provide instructions in Markdown format.",
         ["instructions.md", "query.overpassql"], ["instructions.docx", "query.overpassql"]),
        (["guide.html", "guide.docx"], "Publish the guide as a web page.",
         ["guide.html"], ["guide.docx"]),
        (["sales.csv", "sales.xlsx"], "Export the sales table as a CSV file.",
         ["sales.csv"], ["sales.xlsx"]),
        (["message.eml", "message.docx"], "Save the email as an .eml file.",
         ["message.eml"], ["message.docx"]),
        (["a.docx", "a.pdf", "b.docx", "b.pdf"], "Draft each letter in Word.",
         ["a.docx", "b.docx"], ["a.pdf", "b.pdf"]),
        (["q1.xlsx", "q1.pdf", "q2.xlsx", "q2.pdf"], "Build each forecast as an Excel workbook.",
         ["q1.xlsx", "q2.xlsx"], ["q1.pdf", "q2.pdf"]),
        (["kickoff.pptx", "kickoff.pdf", "review.pptx", "review.pdf"],
         "Prepare each meeting's slides in PowerPoint.",
         ["kickoff.pptx", "review.pptx"], ["kickoff.pdf", "review.pdf"]),
        # PDF leads the fixed order already; naming it keeps it there.
        (["a.pdf", "a.html", "b.pdf", "b.html"], "Export each guide as a PDF.",
         ["a.pdf", "b.pdf"], ["a.pdf", "b.pdf"]),
    ],
    ids=["plain-text", "markdown", "html", "csv", "eml", "word", "spreadsheet", "slides", "pdf"],
)
def test_a_rendition_the_task_names_outranks_the_fixed_order(names, instruction, kept, kept_unnamed):
    criteria = ["Covers every point in the brief."]
    selection = _select("named", names, criteria, instruction=instruction)
    unnamed = _select("named", names, criteria, instruction="Complete the assignment.")

    for result, expected in ((selection, kept), (unnamed, kept_unnamed)):
        assert result.selection_status == "ok"
        assert result.selection_rule.endswith("+rendition_copies")
        assert sorted(_primaries(result)) == sorted(expected)
        assert sorted(_names(result.support_artifacts)) == sorted(set(names) - set(expected))


@pytest.mark.parametrize(
    "instruction",
    [
        "Write up the notes.",
        "Provide the notes as a Word document and as a plain text file.",
    ],
    ids=["none-named", "both-named"],
)
def test_without_exactly_one_named_rendition_the_fixed_order_decides(instruction):
    selection = _select(
        "order", ["notes.txt", "notes.docx"], ["The notes list three risks."],
        instruction=instruction,
    )

    assert selection.selection_status == "ok"
    assert _primaries(selection) == ["notes.docx"]
    assert _names(selection.support_artifacts) == ["notes.txt"]


@pytest.mark.parametrize(
    "names,instruction,kept",
    [
        # The never-a-primary rule for .msg holds even when the task asks for
        # an Outlook message: the judge reads the same email in the .docx.
        (["message.msg", "message.docx"], "Save the email in Outlook as a .msg file.",
         ["message.docx"]),
        # A legacy .doc has no reader either; the PDFs stay the graded copies.
        (["a.doc", "a.pdf", "b.doc", "b.pdf"], "Save each letter as a Word 97 .doc file.",
         ["a.pdf", "b.pdf"]),
        # Nor does the fixed order keep it over a plain-text copy.
        (["memo.doc", "memo.txt"], "Save the memo as a Word 97 .doc file.", ["memo.txt"]),
    ],
    ids=["outlook-msg", "legacy-doc", "legacy-doc-beside-text"],
)
def test_naming_a_format_the_grader_cannot_open_never_hides_the_copy_it_can_read(
    names, instruction, kept
):
    selection = _select("unreadable", names, ["The letter is signed."], instruction=instruction)

    assert selection.selection_status == "ok"
    assert sorted(_primaries(selection)) == sorted(kept)
    assert sorted(_names(selection.support_artifacts)) == sorted(set(names) - set(kept))


@pytest.mark.parametrize(
    "names,kept",
    [
        (["memo.doc", "memo.txt"], ["memo.txt"]),
        (["ledger.xls", "ledger.csv"], ["ledger.csv"]),
        (["memo.doc", "memo.md"], ["memo.md"]),
        (["memo.doc", "memo.eml"], ["memo.eml"]),
        (["a.doc", "a.txt", "b.doc", "b.txt"], ["a.txt", "b.txt"]),
    ],
    ids=["doc-txt", "xls-csv", "doc-md", "doc-eml", "two-pairs"],
)
def test_the_fixed_order_keeps_the_copy_the_judge_can_read_over_a_legacy_binary(names, kept):
    # A .doc or .xls has no reader and no renderer: graded alone it is an empty
    # read. Ranked ahead of the readable copy, it hid the same memo from the judge.
    selection = _select(
        "legacy", names, ["The memo lists the quarterly risks."],
        instruction="Write a memo to the board listing the quarterly risks.",
    )

    assert selection.selection_status == "ok"
    assert selection.selection_rule.endswith("+rendition_copies")
    assert sorted(_primaries(selection)) == sorted(kept)
    assert sorted(_names(selection.support_artifacts)) == sorted(set(names) - set(kept))


def test_a_text_and_html_twin_keeps_the_text_beside_another_document():
    # The .html outranked the .txt, and beside the workbook F4 then made the
    # kept page a companion, so the note had no primary at all.
    selection = _select(
        "twin", ["note.txt", "note.html", "vitals.xlsx"], ["The note records the vitals."],
        instruction="Write the note and the vitals sheet.",
    )

    assert selection.selection_status == "ok"
    assert selection.selection_rule.endswith("+rendition_copies")
    assert sorted(_primaries(selection)) == ["note.txt", "vitals.xlsx"]
    assert _names(selection.support_artifacts) == ["note.html"]


@pytest.mark.parametrize(
    "names,kept",
    [
        # Ranked ahead of the .doc, the kept page would become the CSV's
        # companion (F4) and the guide would have no primary.
        (["guide.doc", "guide.html", "plan.csv"], ["guide.doc", "plan.csv"]),
        # The price of that order, recorded in the seal doc's Limits: alone,
        # the pair keeps the .doc the judge cannot read.
        (["guide.doc", "guide.html"], ["guide.doc"]),
    ],
    ids=["beside-a-csv", "alone"],
)
def test_a_page_ranks_below_a_legacy_binary(names, kept):
    selection = _select("page-legacy", names, ["The guide explains alt text."], instruction="Write the guide.")

    assert selection.selection_status == "ok"
    assert sorted(_primaries(selection)) == sorted(kept)
    assert _names(selection.support_artifacts) == ["guide.html"]


# Quoted from 62f04c2f (openai/gdpval@11e7900c): the two prompt sentences that
# ask for the files, and the rubric lines that name their formats.
EXCHANGE_PROMPT = (
    "Please create a one-page Word document that will serve as an overview of the program. "
    "Next, please create an Excel spreadsheet that will serve as the Exchange Authorization form."
)
EXCHANGE_LINES = [
    "A Word file is submitted as a separate file in .docx or .doc format "
    "(not PDF/ODT/Google Doc and not embedded).",
    "An Excel workbook is submitted as a separate file in .xlsx or .xls format "
    "(not CSV/Google Sheet/PDF and not embedded).",
    "The Exchange Authorization form content is delivered in the Excel file, "
    "not pasted or embedded inside the Word document.",
]
EXCHANGE_FORM = "Gravon Exchange Authorization Form"
EXCHANGE_OVERVIEW = "Gravon Shoes Exchange Program Overview"


def test_a_format_the_task_forbids_is_not_a_format_it_names():
    # 62f04c2f with a same-name PDF export of each file. Counted as naming PDF,
    # "not PDF" named both formats of each group, so the fixed order kept the
    # PDFs and hid the workbook and the Word file the task asks for.
    names = [EXCHANGE_FORM + ".xlsx", EXCHANGE_FORM + ".pdf",
             EXCHANGE_OVERVIEW + ".docx", EXCHANGE_OVERVIEW + ".pdf"]
    selection = _select("62f04c2f", names, EXCHANGE_LINES, instruction=EXCHANGE_PROMPT)

    assert selection.selection_status == "ok"
    assert selection.selection_rule.endswith("+rendition_copies")
    assert sorted(_primaries(selection)) == [EXCHANGE_FORM + ".xlsx", EXCHANGE_OVERVIEW + ".docx"]
    assert sorted(_names(selection.support_artifacts)) == [
        EXCHANGE_FORM + ".pdf", EXCHANGE_OVERVIEW + ".pdf",
    ]
    for line in EXCHANGE_LINES[:2]:
        plan = plan_targets_for_criterion(selection, line)
        assert not [p for p in _names(plan.selected_paths) if p.endswith(".pdf")]


@pytest.mark.parametrize(
    "names,instruction,kept",
    [
        (["a.docx", "a.pdf", "b.docx", "b.pdf"], "Do not use PDF; submit Word.", ["a.docx", "b.docx"]),
        (["notes.docx", "notes.txt"], "Do not submit a plain-text file.", ["notes.docx"]),
        # A negation ends at a clause break, a comma included.
        (["notes.md", "notes.docx"], "No more than two pages, in Markdown.", ["notes.md"]),
    ],
    ids=["not-pdf-then-word", "not-plain-text", "comma-ends-the-negation"],
)
def test_a_negated_format_word_names_nothing(names, instruction, kept):
    selection = _select("negated", names, ["Covers every point in the brief."], instruction=instruction)

    assert selection.selection_status == "ok"
    assert selection.selection_rule.endswith("+rendition_copies")
    assert sorted(_primaries(selection)) == sorted(kept)
    assert sorted(_names(selection.support_artifacts)) == sorted(set(names) - set(kept))


@pytest.mark.parametrize(
    "names,kept",
    [
        # Beside a workbook, a page whose format the task names is not a
        # companion (F4 declines), so keeping the .html would refuse the task.
        (["guide.html", "guide.docx", "budget.xlsx"], ["guide.docx", "budget.xlsx"]),
        # Beside two Word files the unchanged rules grade only documents, so
        # keeping the .html would leave the guide with no primary at all.
        (["guide.html", "guide.docx", "a.docx", "b.docx"], ["guide.docx", "a.docx", "b.docx"]),
    ],
    ids=["refused-otherwise", "hidden-otherwise"],
)
def test_a_named_rendition_the_rules_would_not_grade_leaves_the_fixed_order(names, kept):
    selection = _select(
        "page", names, ["The guide explains alt text."],
        instruction="Publish the guide as a web page.",
    )

    assert selection.selection_status == "ok"
    assert selection.selection_rule.endswith("+rendition_copies")
    assert sorted(_primaries(selection)) == sorted(kept)
    assert _names(selection.support_artifacts) == ["guide.html"]


def test_the_models_own_summary_never_chooses_the_copy():
    selection = select_deliverables(
        task_id="summary",
        deliverable_files=[_p("summary", n) for n in ("notes.md", "notes.docx")],
        instruction="Write up the notes.",
        rubric_items=[{"criterion": "The notes list three risks.", "score": 1}],
        deliverable_summary="The Markdown file notes.md is the deliverable.",
    )

    assert _primaries(selection) == ["notes.docx"]
    assert _names(selection.support_artifacts) == ["notes.md"]


def test_a_named_rendition_does_not_reach_a_format_variant_main_already_answers():
    # The tie-break lives inside the copy rule only. Where main's single-PDF
    # fallback answers the task, its answer is unchanged.
    selection = _select(
        "answered", ["report.docx", "report.pdf"], ["The report has a summary."],
        instruction="Write the report in Markdown or Word.",
    )

    assert selection.selection_rule == "set_diff_then_format_variant"
    assert _primaries(selection) == ["report.pdf"]


def test_copies_are_only_set_aside_where_the_task_was_refused():
    # An existing format-variant answer is left exactly as it was.
    selection = _select("unchanged", ["report.docx", "report.pdf"], ["The report has a summary."])

    assert selection.selection_rule == "set_diff_then_format_variant"
    assert _primaries(selection) == ["report.pdf"]


def test_the_rendition_order_is_fixed_and_complete_for_the_measured_corpora():
    assert RENDITION_ORDER == (
        # what the renderer draws
        ".pdf", ".docx", ".xlsx", ".xlsm", ".pptx",
        # what the reader opens
        ".eml", ".md", ".txt", ".csv",
        # legacy binaries with neither
        ".doc", ".xls", ".ppt",
        # pages F4 makes companions
        ".html", ".htm",
        # never a primary
        ".msg",
    )
    # Every other extension seen in gold-185, exp003, exp035 and exp036 is a
    # distinct-file kind that is never set aside as a copy.
    never_copies = {
        ".zip", ".py", ".json", ".yaml", ".yml", ".ipynb", ".overpassql",
        ".sol", ".ts", ".tsx", ".js", ".css", ".tf", ".svg", ".wav", ".mp4",
        ".png", ".jpg",
    }
    assert never_copies.isdisjoint(RENDITION_ORDER)


# ── F3: a requested image file is graded beside the document ──────────────

# Quoted from 3baa0009 and b1a79ce1 (openai/gdpval@11e7900c).
JPG_LINE = "Deliverable includes at least one chart image saved as a JPG (.jpg or .jpeg)"
PNG_LINE = "Deliverable moodboard is in PNG file format."
CHART_FILES = [
    "create_global_growth_chart.py",
    "world_bank_global_growth_2024_2025_2027.jpg",
    "world_bank_global_outlook_article.md",
]


def test_a_requested_jpg_chart_is_graded_beside_the_article():
    selection = _select("3baa0009", CHART_FILES, [JPG_LINE, "The chart clearly displays 2025 as 2.3%"])

    assert selection.selection_status == "ok"
    assert selection.selection_rule == "set_diff_then_separate_primaries+requested_image"
    # Added after the existing primaries, never in place of them.
    assert _primaries(selection) == [
        "create_global_growth_chart.py",
        "world_bank_global_outlook_article.md",
        "world_bank_global_growth_2024_2025_2027.jpg",
    ]
    assert selection.primary_targets[-1].evidence_rule == "requested_image_primary"
    assert selection.support_artifacts == []


def test_the_requested_image_is_shown_to_visual_and_manifest_criteria_only():
    selection = _select("3baa0009", CHART_FILES, [JPG_LINE])
    jpg = "world_bank_global_growth_2024_2025_2027.jpg"

    chart = plan_targets_for_criterion(selection, "The chart clearly displays 2025 as 2.3%")
    assert jpg in _names(chart.selected_paths)
    manifest = plan_targets_for_criterion(selection, "Article is in PDF format.")
    assert manifest.target_scope == "manifest"
    assert jpg in _names(manifest.selected_paths)
    # A text criterion keeps the plan it had before the image was added, so a
    # chart beside a renderable document does not send it to the renderer.
    text = plan_targets_for_criterion(selection, "Explicitly attributes information to the World Bank")
    assert jpg not in _names(text.selected_paths)
    assert _names(text.selected_paths) == ["create_global_growth_chart.py", "world_bank_global_outlook_article.md"]


def test_a_requested_moodboard_png_is_graded_beside_its_script():
    # b1a79ce1 (exp035): the script was the only primary, and the moodboard
    # criteria were answered by reading drawing code.
    selection = _select("b1a79ce1", ["generate_moodboard.py", "music_video_moodboard.png"], [PNG_LINE])

    assert _primaries(selection) == ["generate_moodboard.py", "music_video_moodboard.png"]


def test_an_image_to_be_placed_inside_the_pdf_is_not_promoted():
    # 99ac6944 asks for .png charts *within* the PDF; the PDF is the deliverable.
    selection = _select(
        "99ac6944",
        ["IEM_Signal_Flow.png", "IEM_Budget_Breakdown.png", "West_Coast_Tour_IEM_Mobile_Setup.pdf"],
        [
            "The PDF contains the image of a simple mixer input/output wiring and "
            "signal flow chart as a .png image format.",
            "A single PDF file is delivered.",
        ],
        instruction=(
            "Within the same document, please also include a simple mixer "
            "input/output wiring and signal flow chart in .png format for reference."
        ),
    )

    assert _primaries(selection) == ["West_Coast_Tour_IEM_Mobile_Setup.pdf"]
    assert "requested_image" not in selection.selection_rule


def test_an_input_image_named_in_the_prompt_is_not_promoted():
    # f2986c1f names its reference photo; a copy left in the output is not a
    # requested deliverable.
    selection = _select(
        "f2986c1f",
        ["Drug_list_identified.xlsx", "what are these annotated.jpg"],
        ["Identifies each medication shown in the image."],
        instruction='An emergency response team has provided the image titled "what are these.jpg."',
    )

    assert _primaries(selection) == ["Drug_list_identified.xlsx"]


def test_an_image_in_another_format_than_the_one_requested_stays_support():
    selection = _select(
        "3baa0009",
        ["world_bank_global_outlook_article.md", "world_bank_chart.png"],
        [JPG_LINE],
    )

    assert _primaries(selection) == ["world_bank_global_outlook_article.md"]
    assert _names(selection.support_artifacts) == ["world_bank_chart.png"]


# ── F4: one document and a companion of another kind under another name ────

@pytest.mark.parametrize("companion", ["SOAP_preview.html", "render_note.js", "body_diagram.svg", "note.css"])
def test_a_companion_beside_the_only_document_is_support(companion):
    selection = _select(
        "companion",
        ["CS_SOAP_Note_2024-03-01.docx", companion],
        ["The note documents the mechanism of injury."],
        instruction="Please create a SOAP note for the visit.",
    )

    assert selection.selection_status == "ok"
    assert selection.task_class == "main_plus_support"
    assert selection.selection_rule == "set_diff_then_companion_support"
    assert _primaries(selection) == ["CS_SOAP_Note_2024-03-01.docx"]
    assert _names(selection.support_artifacts) == [companion]


def test_a_companion_whose_format_the_task_names_is_not_demoted():
    selection = _select(
        "companion",
        ["CS_SOAP_Note_2024-03-01.docx", "SOAP_preview.html"],
        ["The note is also published as an HTML page."],
    )

    assert selection.selection_status == "selection_error"
    assert selection.selection_rule == "ambiguous_candidates"


def test_two_documents_and_a_companion_keep_their_existing_rule():
    selection = _select("companion", ["a.docx", "b.docx", "c.html"], ["The memo is short."])

    assert selection.selection_rule == "set_diff_then_uniform_primaries"
    assert sorted(_primaries(selection)) == ["a.docx", "b.docx"]


def test_a_companion_without_an_extension_still_declines():
    selection = _select("companion", ["report.docx", ".DS_Store"], ["The report is short."])

    assert selection.selection_status == "selection_error"
    assert selection.selection_rule == "ambiguous_candidates"
