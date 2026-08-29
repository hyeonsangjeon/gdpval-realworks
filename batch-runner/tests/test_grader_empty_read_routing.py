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
