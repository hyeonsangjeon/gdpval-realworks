"""The grader half of "an empty read is not an absent document".

``core/grader_routing.py`` decides where an item is judged and is deliberately
pure, so the question it now asks -- *does any selected file yield a single
character of text* -- has to be answered by whoever is allowed to touch the
disk. That is ``Grader._selected_paths_have_text``, and this file covers it
plus the two places that call it: the paid run and the model-free preflight
that is supposed to predict the paid run exactly.

The defect being fixed: stage 1 graded a gold deliverable that is a two-page
scan. Ten rubric items about its contents routed TEXT, read zero characters,
and were failed as "that content is absent" -- about a document that says all
ten things, on pages the harness had already rendered for the same task's
other items.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.grader import Grader
from core.grader_preflight import _planner, plan_task_runtime
from core.grader_routing import Modality, resolve_runtime_routing
from core.rubric_loader import RubricItem, TaskRubric


def _probe_surface() -> Grader:
    """A Grader with nothing on it but what the probe needs.

    ``__init__`` opens an Azure client. The probe reads files and a dict, so
    it is built the same way ``grader_preflight`` builds one.
    """
    grader = object.__new__(Grader)
    grader._text_layer_cache = {}
    return grader


@pytest.fixture
def scan(tmp_path: Path) -> Path:
    """Two pages of image and not one character of text."""
    pytest.importorskip("reportlab")
    pytest.importorskip("fitz")
    pytest.importorskip("PIL")
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    photo = tmp_path / "_page.png"
    Image.new("RGB", (64, 64), color="white").save(photo)
    p = tmp_path / "Scan.pdf"
    document = canvas.Canvas(str(p))
    for _ in range(2):
        document.drawImage(ImageReader(str(photo)), 40, 40, width=200, height=200)
        document.showPage()
    document.save()
    photo.unlink()
    return p


@pytest.fixture
def typed(tmp_path: Path) -> Path:
    """The control: the same shape of file, with a text layer."""
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    p = tmp_path / "Scan.pdf"
    document = canvas.Canvas(str(p))
    document.drawString(100, 750, "The total contract value is 4,200 USD.")
    document.showPage()
    document.save()
    return p


@pytest.fixture
def sibling(tmp_path: Path) -> Path:
    """A readable file under its own name, to be selected beside the scan."""
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    p = tmp_path / "Return.pdf"
    document = canvas.Canvas(str(p))
    document.drawString(100, 750, "The total contract value is 4,200 USD.")
    document.showPage()
    document.save()
    return p


# ── The probe: False is a claim, None is an admission ────────────────


def test_one_readable_file_answers_for_the_whole_set(tmp_path, scan):
    (tmp_path / "notes.txt").write_text("readable", encoding="utf-8")

    answer = _probe_surface()._selected_paths_have_text(
        tmp_path, ["Scan.pdf", "notes.txt"]
    )

    assert answer is True


def test_every_file_examined_and_none_had_text_is_a_finding(tmp_path, scan):
    (tmp_path / "blank.txt").write_text("  \n", encoding="utf-8")

    answer = _probe_surface()._selected_paths_have_text(
        tmp_path, ["Scan.pdf", "blank.txt"]
    )

    assert answer is False


def test_one_file_it_cannot_speak_for_poisons_the_answer(tmp_path, scan):
    # ``.wav`` is not a kind text is carried in, so "this file has no text" is
    # not a finding about it. Escalation reads ``False`` as "look at the pages
    # instead", and half a set is not grounds for that.
    (tmp_path / "stems.wav").write_bytes(b"\x00")

    answer = _probe_surface()._selected_paths_have_text(
        tmp_path, ["Scan.pdf", "stems.wav"]
    )

    assert answer is None


def test_no_selected_paths_is_not_a_finding_either(tmp_path):
    assert _probe_surface()._selected_paths_have_text(tmp_path, []) is None
    assert _probe_surface()._selected_paths_have_text(tmp_path, ["", None]) is None


def test_a_missing_file_never_reads_as_empty(tmp_path):
    answer = _probe_surface()._selected_paths_have_text(
        tmp_path, ["was_never_written.pdf"]
    )

    assert answer is None


def test_each_file_is_opened_once_per_task_not_once_per_rubric_item(
    tmp_path, monkeypatch
):
    """A task's items all ask about the same files.

    Without the memo a 20-item task re-reads every page of every scan 20
    times. The reset that bounds the memo to one task is covered by
    ``test_the_preflight_starts_each_task_with_an_empty_memo``.
    """
    (tmp_path / "notes.txt").write_text("readable", encoding="utf-8")
    opened: list[Path] = []

    def _counting(path):
        opened.append(Path(path))
        return True

    monkeypatch.setattr("core.grader.has_extractable_text", _counting)
    grader = _probe_surface()

    for _ in range(5):
        grader._selected_paths_have_text(tmp_path, ["notes.txt"])

    assert len(opened) == 1


def test_the_preflight_starts_each_task_with_an_empty_memo():
    # The memo is keyed on a relative name, so carrying one across tasks would
    # answer for `report.pdf` in task B with what was read in task A.
    assert _planner({})._text_layer_cache == {}


# ── The paid run and its free rehearsal must agree ───────────────────


def _task(prompt: str, items: list[RubricItem]) -> TaskRubric:
    return TaskRubric(
        task_id="task-1",
        sector="test",
        occupation="test",
        prompt=prompt,
        rubric_items=items,
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )


_CONTENT_ITEM = RubricItem(
    "value", "The document states the total contract value.", 2, None
)


def test_the_preflight_escalates_a_scan_to_the_render_path(tmp_path, scan):
    """The ten-item failure, reproduced at the level that predicts it.

    ``plan_task_runtime`` is the model-free rehearsal of a paid run: same
    selection, same routing, no API calls. Before this change it planned TEXT
    here, which is exactly what the paid run then did.
    """
    plan = plan_task_runtime({}, _task("Produce Scan.pdf.", [_CONTENT_ITEM]), tmp_path)

    assert plan["judge_routes"] == {"visual": 1}
    assert plan["planned_render_calls"] == 1
    assert plan["errors"] == []


def test_the_preflight_leaves_a_readable_document_on_the_text_path(tmp_path, typed):
    """The control. Escalating this one would be a regression and a cost.

    Nothing about the criterion changed between this test and the one above --
    only whether the file it points at can be read.
    """
    plan = plan_task_runtime({}, _task("Produce Scan.pdf.", [_CONTENT_ITEM]), tmp_path)

    assert plan["judge_routes"] == {"text": 1}
    assert plan["planned_render_calls"] == 0
    assert plan["errors"] == []


# ── The complement: which file, not whether any file (task 79) ───────
#
# ``_selected_paths_have_text`` is right about its own question and wrong as
# the only question. Stage 3 selected a two-page Loss Prevention flowchart
# carrying zero characters -- page one is a single full-page image -- next to
# a readable 1,756-character memo. The bundle answered "yes, there is text",
# the item stayed on the text path, and the flowchart was never rendered or
# looked at by anything. ``_some_selected_path_lacks_text`` asks per file, on
# the same memo, so the picture is seen without re-reading the memo.


def test_a_picture_beside_a_readable_file_is_reported(tmp_path, scan):
    (tmp_path / "memo.txt").write_text("The deposit was never banked.")

    surface = _probe_surface()
    assert surface._selected_paths_have_text(
        tmp_path, ["memo.txt", scan.name]
    ) is True
    assert surface._some_selected_path_lacks_text(
        tmp_path, ["memo.txt", scan.name]
    ) is True


def test_every_file_readable_is_a_finding_of_no_gap(tmp_path, typed):
    (tmp_path / "memo.txt").write_text("The deposit was never banked.")

    answer = _probe_surface()._some_selected_path_lacks_text(
        tmp_path, ["memo.txt", typed.name]
    )

    assert answer is False


def test_a_definite_gap_outranks_a_file_it_cannot_speak_for(tmp_path, scan):
    """A measured no is enough; an unknown alongside it changes nothing."""
    (tmp_path / "mystery.bin").write_bytes(b"\x00\x01\x02")

    answer = _probe_surface()._some_selected_path_lacks_text(
        tmp_path, [scan.name, "mystery.bin"]
    )

    assert answer is True


def test_an_unknown_with_no_definite_gap_admits_it(tmp_path, typed):
    (tmp_path / "mystery.bin").write_bytes(b"\x00\x01\x02")

    answer = _probe_surface()._some_selected_path_lacks_text(
        tmp_path, [typed.name, "mystery.bin"]
    )

    assert answer is None


def test_a_missing_file_is_not_a_gap_in_the_deliverable(tmp_path):
    """Absent is unknowable, not empty -- the same rule as its sibling."""
    answer = _probe_surface()._some_selected_path_lacks_text(
        tmp_path, ["never_written.pdf"]
    )

    assert answer is None


def test_no_selected_paths_is_not_a_finding_here_either(tmp_path):
    surface = _probe_surface()
    assert surface._some_selected_path_lacks_text(tmp_path, []) is None
    assert surface._some_selected_path_lacks_text(tmp_path, ["", None]) is None


def test_the_two_questions_share_one_read_of_each_file(tmp_path, monkeypatch):
    """Asking twice must not open the file twice."""
    (tmp_path / "notes.txt").write_text("readable")
    opened: list[str] = []

    import core.grader as grader_module

    monkeypatch.setattr(
        grader_module,
        "has_extractable_text",
        lambda path: (opened.append(str(path)), True)[1],
    )

    grader = _probe_surface()
    grader._selected_paths_have_text(tmp_path, ["notes.txt"])
    grader._some_selected_path_lacks_text(tmp_path, ["notes.txt"])

    assert len(opened) == 1


# ── Which files escalated is which files get looked at (task 83) ─────
#
# Escalating and rendering are two different sets, and treating them as one
# cost a whole task its score. Stage 3's task 43dc9778 delivers a two-page
# scan beside a 17-page readable return, and all 67 of its rubric items
# select both files. Every item escalated on the scan -- correctly, that is
# the rule above doing its job -- and then asked for the bundle: 67 x 2 = 134
# renders against a task visual budget of 72. Over budget, all 67 items
# excluded, ``all_items_score_excluded``, 87.36% to 0.00%.
#
# The escalation was right and the render scope was wrong. What makes a file
# escalate is a fact about that file, so that file is what gets rendered.


def test_the_probe_names_the_file_that_cannot_be_read(tmp_path, scan, sibling):
    answer = _probe_surface()._paths_without_text(
        tmp_path, ["Return.pdf", "Scan.pdf"]
    )

    assert answer == ("Scan.pdf",)


def test_a_file_the_probe_cannot_speak_for_is_not_named(tmp_path, scan):
    """Same discipline as everywhere else here: only a measured no counts.

    An unknown named in the render set would spend a picture on a guess,
    which is what the ``None`` rule exists to prevent.
    """
    (tmp_path / "mystery.bin").write_bytes(b"\x00\x01\x02")

    answer = _probe_surface()._paths_without_text(
        tmp_path, ["Scan.pdf", "mystery.bin", "never_written.pdf"]
    )

    assert answer == ("Scan.pdf",)


def test_only_the_unreadable_file_is_planned_for_rendering():
    decision = resolve_runtime_routing(
        _CONTENT_ITEM.criterion,
        ["Return.pdf", "Scan.pdf"],
        selected_paths_have_text=True,
        some_selected_path_lacks_text=True,
        paths_without_text=("Scan.pdf",),
    )

    assert decision.modality is Modality.VISUAL
    assert decision.render_paths == ("Scan.pdf",)
    assert decision.render_targets(["Return.pdf", "Scan.pdf"]) == ["Scan.pdf"]


def test_a_set_where_nothing_can_be_read_is_not_narrowed():
    """Narrower or nothing.

    When every selected file lacks text the render set is the selection, and
    recording that twice is a second thing to keep in step with the first.
    """
    decision = resolve_runtime_routing(
        _CONTENT_ITEM.criterion,
        ["Flowchart.pdf", "Scan.pdf"],
        selected_paths_have_text=False,
        paths_without_text=("Flowchart.pdf", "Scan.pdf"),
    )

    assert decision.modality is Modality.VISUAL
    assert decision.render_paths is None
    assert decision.render_targets(["Flowchart.pdf", "Scan.pdf"]) == [
        "Flowchart.pdf",
        "Scan.pdf",
    ]


def test_a_criterion_that_names_a_picture_still_asks_for_the_whole_bundle():
    """The narrowing belongs to the escalation, not to VISUAL in general.

    "Do the chart colours match the palette" is a question about the
    deliverable. Answering it from one file of two would be answering a
    different question, and nothing about that item's routing depends on
    which of its files happens to carry a text layer.
    """
    decision = resolve_runtime_routing(
        "The chart colors match the brand palette.",
        ["Return.pdf", "Scan.pdf"],
        selected_paths_have_text=True,
        some_selected_path_lacks_text=True,
        paths_without_text=("Scan.pdf",),
    )

    assert decision.modality is Modality.VISUAL
    assert decision.render_paths is None


def test_an_escalation_that_names_no_files_asks_for_all_of_them():
    """The answer is optional, and its absence is not a narrowing.

    A caller that measures ``some_selected_path_lacks_text`` without saying
    which file it was gets exactly the behaviour that shipped before this.
    """
    decision = resolve_runtime_routing(
        _CONTENT_ITEM.criterion,
        ["Return.pdf", "Scan.pdf"],
        selected_paths_have_text=True,
        some_selected_path_lacks_text=True,
    )

    assert decision.modality is Modality.VISUAL
    assert decision.render_paths is None


def test_one_scan_no_longer_spends_a_whole_task_visual_budget(
    tmp_path, scan, sibling
):
    """The regression, at the scale that fits in a test.

    Measured on the code this replaces, these same three items planned
    ``task visual budget exceeded: planned=6, cap=4``, rendered nothing, and
    took every item down with them -- the shape of ``planned=134, cap=72`` on
    the real task. Each item now plans the scan alone.
    """
    items = [
        RubricItem(f"r{index}", _CONTENT_ITEM.criterion, 2, None)
        for index in range(3)
    ]

    plan = plan_task_runtime(
        {"judge": {"perception": {"visual": {"call_cap_per_task": 4}}}},
        _task("Produce Scan.pdf and Return.pdf.", items),
        tmp_path,
    )

    assert plan["judge_routes"] == {"visual": 3}
    assert [item["planned_visual_paths"] for item in plan["items"]] == [
        ["Scan.pdf"],
        ["Scan.pdf"],
        ["Scan.pdf"],
    ]
    assert plan["planned_render_calls"] == 3
    assert plan["errors"] == []
