"""The grader half of "an archive of stems is audio".

``core/grader_routing.py`` decides where an item is judged and is deliberately
pure, so the question it now asks -- *is any selected file audio, or an archive
that holds audio* -- has to be answered by whoever is allowed to touch the
disk. That is ``Grader._selected_paths_have_audio``, and this file covers it
plus the two places that call it: the paid run and the model-free preflight
that is supposed to predict the paid run exactly.

The defect being fixed: stage 1 graded a task made entirely of music -- tempo,
key, vocals, mix -- whose whole deliverable is one 180 MB ``.zip`` of stems.
``.zip`` is not an audio extension, so every listening criterion was demoted to
TEXT and answered by reading an archive listing. The task recorded
``perception_call_count: 0`` and scored 41.8 of 62.

The companion file ``test_grader_empty_read_routing.py`` does the same job for
the text probe; the two share one engine, ``Grader._any_selected_path``.
"""

from __future__ import annotations

import zipfile
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
    grader._audio_content_cache = {}
    return grader


@pytest.fixture
def stems(tmp_path: Path) -> Path:
    """The shape of the real deliverable: audio, packaged."""
    archive = tmp_path / "DEJA VU  STEMS .zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Master.wav", b"RIFF....WAVEfmt master")
        zf.writestr("Bass.wav", b"RIFF....WAVEfmt bass")
        zf.writestr("session notes.txt", b"140 bpm, G major")
    return archive


@pytest.fixture
def documents(tmp_path: Path) -> Path:
    """The control: the same container, nothing to listen to."""
    archive = tmp_path / "DEJA VU  STEMS .zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("report.docx", b"not really a docx")
        zf.writestr("session notes.txt", b"140 bpm, G major")
    return archive


# ── The probe: True is the interesting answer, None is an admission ──


def test_an_archive_of_stems_is_audio(tmp_path, stems):
    assert _probe_surface()._selected_paths_have_audio(
        tmp_path, ["DEJA VU  STEMS .zip"]
    ) is True


def test_an_archive_of_documents_is_examined_and_found_silent(
    tmp_path, documents
):
    assert _probe_surface()._selected_paths_have_audio(
        tmp_path, ["DEJA VU  STEMS .zip"]
    ) is False


def test_one_audio_file_answers_for_the_whole_set(tmp_path, documents):
    (tmp_path / "master.wav").write_bytes(b"RIFF")

    assert _probe_surface()._selected_paths_have_audio(
        tmp_path, ["DEJA VU  STEMS .zip", "master.wav"]
    ) is True


def test_a_zip_that_will_not_open_never_reads_as_silent(tmp_path):
    """Not hypothetical: one gold deliverable is a ``.zip`` that is not one.

    ``PrivateCrypMixV2.zip`` raises ``BadZipFile`` on open. ``None`` keeps the
    existing extension test in charge there rather than promoting an item
    towards a file nothing can extract.
    """
    (tmp_path / "broken.zip").write_bytes(b"not an archive at all")

    assert _probe_surface()._selected_paths_have_audio(
        tmp_path, ["broken.zip"]
    ) is None


def test_a_missing_file_never_reads_as_silent(tmp_path):
    assert _probe_surface()._selected_paths_have_audio(
        tmp_path, ["was_never_delivered.zip"]
    ) is None


def test_no_selected_paths_is_not_a_finding_either(tmp_path):
    assert _probe_surface()._selected_paths_have_audio(tmp_path, []) is None
    assert _probe_surface()._selected_paths_have_audio(
        tmp_path, ["", None]
    ) is None


def test_each_archive_is_opened_once_per_task_not_once_per_rubric_item(
    tmp_path, monkeypatch
):
    """Thirty-five items asking about one 180 MB archive.

    Without the memo this task alone would walk that archive's directory 35
    times. The reset that bounds the memo to one task is covered by
    ``test_the_preflight_starts_each_task_with_an_empty_memo``.
    """
    (tmp_path / "stems.zip").write_bytes(b"")
    opened: list[Path] = []

    def _counting(path):
        opened.append(Path(path))
        return True

    monkeypatch.setattr("core.grader.has_audio_content", _counting)
    grader = _probe_surface()

    for _ in range(5):
        grader._selected_paths_have_audio(tmp_path, ["stems.zip"])

    assert len(opened) == 1


def test_the_two_probes_do_not_share_a_memo(tmp_path, stems):
    """Same key, different question. One dict would answer both with one."""
    grader = object.__new__(Grader)
    grader._audio_content_cache = {}
    grader._text_layer_cache = {}
    name = "DEJA VU  STEMS .zip"

    grader._selected_paths_have_audio(tmp_path, [name])

    assert grader._audio_content_cache[name] is True
    assert name not in grader._text_layer_cache


def test_the_preflight_starts_each_task_with_an_empty_memo():
    # The memo is keyed on a relative name, so carrying one across tasks would
    # answer for `stems.zip` in task B with what was read in task A.
    assert _planner({})._audio_content_cache == {}


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


_MIX_ITEM = RubricItem(
    "vocals", "The Master track contains no vocals (instrumental-only).", 2, None
)
_NAMING_ITEM = RubricItem(
    "naming", "The deliverable is named DEJA VU STEMS.", 1, None
)


def test_the_preflight_sends_a_mix_criterion_to_the_listening_model(
    tmp_path, stems
):
    """The ten-item failure, reproduced at the level that predicts it.

    ``plan_task_runtime`` is the model-free rehearsal of a paid run: same
    selection, same routing, no API calls. Before this change it planned TEXT
    here, which is exactly what the paid run then did.
    """
    plan = plan_task_runtime(
        {}, _task("Deliver the stems archive.", [_MIX_ITEM]), tmp_path
    )

    assert plan["judge_routes"] == {"audio": 1}
    assert plan["planned_audio_calls"] == 1


def test_the_preflight_still_demotes_a_mix_criterion_over_documents(
    tmp_path, documents
):
    """The control. Nothing about the criterion differs from the test above --
    only whether the archive it points at has anything to listen to."""
    plan = plan_task_runtime(
        {}, _task("Deliver the stems archive.", [_MIX_ITEM]), tmp_path
    )

    assert plan["judge_routes"] == {"text": 1}
    assert plan["planned_audio_calls"] == 0
    assert plan["errors"] == []


def test_finding_audio_does_not_route_the_rest_of_the_task_to_it(
    tmp_path, stems
):
    """Why the probe is defensive only, priced.

    The real task has 35 items against this one archive and a cap of 3
    listening calls. Promoting on the file rather than on the criterion would
    spend all three on whichever items came first -- here, on checking a
    filename.
    """
    plan = plan_task_runtime(
        {}, _task("Deliver the stems archive.", [_NAMING_ITEM, _MIX_ITEM]),
        tmp_path,
    )

    assert plan["judge_routes"] == {"audio": 1, "text": 1}
    assert plan["planned_audio_calls"] == 1


def test_the_preflight_says_out_loud_that_audio_needs_configuring(
    tmp_path, stems
):
    """An audio route on a config with no audio model is a preflight finding.

    This is the check that would have caught the defect from the other side:
    a cohort that plans zero audio calls on a music task never trips it, which
    is why it stayed quiet through stage 1.
    """
    plan = plan_task_runtime(
        {}, _task("Deliver the stems archive.", [_MIX_ITEM]), tmp_path
    )

    assert any("require configured audio perception" in e for e in plan["errors"])
    assert any("routes=1" in e for e in plan["errors"])


def test_a_configured_cohort_plans_the_call_within_its_cap(tmp_path, stems):
    config = {"judge": {"perception": {"audio": {
        "model": "gpt-4o-audio-preview", "call_cap_per_task": 3,
    }}}}

    plan = plan_task_runtime(
        config, _task("Deliver the stems archive.", [_MIX_ITEM]), tmp_path
    )

    assert plan["planned_audio_calls"] == 1
    assert plan["audio_call_cap"] == 3
    assert not any("budget exceeded" in e for e in plan["errors"])
    assert not any("require configured" in e for e in plan["errors"])


# ── The defect PR #93 fixed must stay fixed ──────────────────────────


def test_sound_technician_fees_on_a_budget_are_still_not_audio(tmp_path):
    """The criterion PR #93 was written for, through the whole grader path.

    An ``.xlsx`` is a zip container, so "does this archive hold audio" is a
    question that could plausibly have been asked of it -- and answering yes
    would send a line item about contractor fees to a listening model. It does
    not: ``_kind_of`` gives an Office file its own kind rather than ``zip``, so
    the probe short-circuits to ``False`` and the extension demotion PR #93
    added is left in charge. Checked against all 146 Office deliverables in the
    gold corpus, every one of which probes ``False``.

    ``test_audio_keyword_with_xlsx_target_downgrades_to_text`` covers the pure
    routing call. This covers the paid path, where the probe actually runs.
    """
    import openpyxl

    book = openpyxl.Workbook()
    book.active["A1"] = "Sound Technician"
    book.save(tmp_path / "tour_budget.xlsx")
    item = RubricItem(
        "fees",
        "Band and Crew includes Sound Technician fees attributed to the "
        "tour manager.",
        2,
        None,
    )

    plan = plan_task_runtime(
        {}, _task("Produce tour_budget.xlsx.", [item]), tmp_path
    )

    assert plan["judge_routes"] == {"text": 1}
    assert plan["planned_audio_calls"] == 0
    assert _probe_surface()._selected_paths_have_audio(
        tmp_path, ["tour_budget.xlsx"]
    ) is False
