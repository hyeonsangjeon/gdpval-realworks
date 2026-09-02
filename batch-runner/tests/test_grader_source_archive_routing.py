"""The grader half of "a React component is judged by reading it".

``core/grader_routing.py`` decides where an item is judged and is deliberately
pure, so the question it now asks -- *is every selected file program text, with
nothing anywhere in it that could be turned into a picture* -- has to be
answered by whoever is allowed to touch the disk. That is
``Grader._selected_paths_are_source_code``, and this file covers it plus the
two places that call it: the paid run and the model-free preflight that is
supposed to predict the paid run exactly.

The defect being fixed: task 7de33b48 delivers one 3.5 KB
``screen_reader_status_message.zip`` -- two ``.tsx`` files, a ``.css``, a
``README.md`` and a ``package.json``. Five of its rubric items, worth eight
points, name ``render``, ``layout`` and ``visual``, so all five routed VISUAL,
found no render target in an archive, and were recorded as
``required_visual_render_target_unavailable``. There is no picture in that
submission to find. The component's appearance is not a property of the
submission at all -- it exists only once something builds and runs the code --
so the JSX and the CSS are not a substitute for looking at the page. They are
the only place the answer is written down.

The companion file ``test_grader_archive_audio_routing.py`` does the same job
for the audio probe, and the two are deliberately mirror images: that one
promotes so a criterion about sound is not answered by reading, this one
demotes so a criterion about code is not refused for want of a picture.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from core.grader import Grader
from core.grader_preflight import _planner, plan_task_runtime
from core.rubric_loader import RubricItem, TaskRubric


def _probe_surface() -> Grader:
    """A Grader with nothing on it but what the probe needs."""
    grader = object.__new__(Grader)
    grader._source_code_cache = {}
    return grader


#: The real deliverable's member list, read out of the judge's own recorded
#: evidence rather than guessed: ``entry_count: 5``, ``size_bytes: 3504``.
REAL_MEMBERS = (
    "screen-reader-status-message/README.md",
    "screen-reader-status-message/package.json",
    "screen-reader-status-message/src/ScreenReaderStatusMessage.tsx",
    "screen-reader-status-message/src/ScreenReaderStatusMessage.css",
    "screen-reader-status-message/src/ScreenReaderStatusMessage.test.tsx",
)

ARCHIVE_NAME = "screen_reader_status_message.zip"


@pytest.fixture
def component(tmp_path: Path) -> Path:
    """The shape of the real deliverable: source, packaged."""
    archive = tmp_path / ARCHIVE_NAME
    with zipfile.ZipFile(archive, "w") as zf:
        for member in REAL_MEMBERS:
            zf.writestr(member, "x")
    return archive


@pytest.fixture
def component_with_a_screenshot(tmp_path: Path) -> Path:
    """The control: the same container, with something to look at in it."""
    archive = tmp_path / ARCHIVE_NAME
    with zipfile.ZipFile(archive, "w") as zf:
        for member in REAL_MEMBERS:
            zf.writestr(member, "x")
        zf.writestr("docs/screenshot.png", b"\x89PNG\r\n\x1a\n")
    return archive


# ── The probe: True is the interesting answer, None is an admission ──


def test_an_archive_of_source_has_nothing_in_it_to_look_at(
    tmp_path, component
):
    assert _probe_surface()._selected_paths_are_source_code(
        tmp_path, [ARCHIVE_NAME]
    ) is True


def test_a_screenshot_in_the_archive_settles_it_for_the_archive(
    tmp_path, component_with_a_screenshot
):
    assert _probe_surface()._selected_paths_are_source_code(
        tmp_path, [ARCHIVE_NAME]
    ) is False


def test_one_file_worth_looking_at_answers_for_the_whole_set(
    tmp_path, component
):
    """Where this reducer parts company with its audio sibling.

    One audio file in a bundle makes the bundle worth listening to, so that
    probe returns ``True`` on the first yes. One screenshot beside the source
    makes "there is nothing here to look at" false, so this one returns
    ``False`` on the first no and ``True`` has to be earned by every file.
    """
    (tmp_path / "preview.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    assert _probe_surface()._selected_paths_are_source_code(
        tmp_path, [ARCHIVE_NAME, "preview.png"]
    ) is False


def test_a_file_the_probe_cannot_answer_for_withholds_the_yes(
    tmp_path, component
):
    """A missing sibling is not evidence that the bundle holds no picture.

    What this signal does is demote a visual item, so an unknown has to leave
    the item where it was rather than carry the rest of the set over the line.
    """
    assert _probe_surface()._selected_paths_are_source_code(
        tmp_path, [ARCHIVE_NAME, "was_never_delivered.zip"]
    ) is None


def test_an_archive_that_will_not_open_is_not_read_as_source(tmp_path):
    (tmp_path / "broken.zip").write_bytes(b"not an archive at all")

    assert _probe_surface()._selected_paths_are_source_code(
        tmp_path, ["broken.zip"]
    ) is None


def test_no_selected_paths_is_not_a_finding_either(tmp_path):
    assert _probe_surface()._selected_paths_are_source_code(tmp_path, []) is None
    assert _probe_surface()._selected_paths_are_source_code(
        tmp_path, ["", None]
    ) is None


def test_each_archive_is_opened_once_per_task_not_once_per_rubric_item(
    tmp_path, monkeypatch
):
    """Thirty-nine items on this task, five of which ask about the archive."""
    (tmp_path / ARCHIVE_NAME).write_bytes(b"")
    opened: list[Path] = []

    def _counting(path):
        opened.append(Path(path))
        return True

    monkeypatch.setattr("core.grader.has_only_source_code_content", _counting)
    grader = _probe_surface()

    for _ in range(5):
        grader._selected_paths_are_source_code(tmp_path, [ARCHIVE_NAME])

    assert len(opened) == 1


def test_the_probes_do_not_share_a_memo(tmp_path, component):
    """Same key, three different questions. One dict would answer all three."""
    grader = object.__new__(Grader)
    grader._source_code_cache = {}
    grader._audio_content_cache = {}
    grader._text_layer_cache = {}

    grader._selected_paths_are_source_code(tmp_path, [ARCHIVE_NAME])

    assert grader._source_code_cache[ARCHIVE_NAME] is True
    assert ARCHIVE_NAME not in grader._audio_content_cache
    assert ARCHIVE_NAME not in grader._text_layer_cache


def test_the_preflight_starts_each_task_with_an_empty_memo():
    # The memo is keyed on a relative name, so carrying one across tasks would
    # answer for `bundle.zip` in task B with what was read in task A.
    assert _planner({})._source_code_cache == {}


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


#: The five excluded items, verbatim from the graded task record, with the
#: ``max_score`` each was worth: 2 + 2 + 2 + 1 + 1 = 8 points on a task whose
#: published total is 33.25 of 52.
EXCLUDED_ITEMS = [
    RubricItem(
        "d5e53223",
        'Before any status message occurs, the rendered DOM includes an '
        'element with role="status".',
        2,
        None,
    ),
    RubricItem(
        "64d2650b",
        "When a status message is triggered, its content is rendered inside "
        'the element with role="status".',
        2,
        None,
    ),
    RubricItem(
        "8c97a84d",
        "ScreenReaderStatusMessage.css defines a class to visually hide the "
        "live region while keeping it in the accessibility tree (no visual "
        "impact on layout).",
        2,
        None,
    ),
    RubricItem(
        "efbbd263",
        "Tests verify that enabling visible does not change the surrounding "
        "rendered text content or layout.",
        1,
        None,
    ),
    RubricItem(
        "0eaf31e2",
        "ScreenReaderStatusMessage.test.tsx uses React Testing Library to "
        "render and query the component.",
        1,
        None,
    ),
]

_PROMPT = "Deliver a React screen-reader status message component."


def test_the_preflight_reads_the_component_instead_of_failing_closed(
    tmp_path, component
):
    """The eight-point exclusion, reproduced at the level that predicts it.

    ``plan_task_runtime`` is the model-free rehearsal of a paid run: same
    selection, same routing, no API calls. Before this change it planned five
    visual judgments here and raised
    ``required_visual_render_target_unavailable`` for every one of them, which
    is exactly what the paid run then recorded.
    """
    plan = plan_task_runtime(
        {}, _task(_PROMPT, EXCLUDED_ITEMS), tmp_path
    )

    assert plan["judge_routes"] == {"text": 5}
    assert plan["planned_render_calls"] == 0
    assert plan["errors"] == []


def test_a_screenshot_in_the_bundle_still_asks_for_the_picture(
    tmp_path, component_with_a_screenshot
):
    """The control. Nothing about the criteria differs from the test above --
    only whether the archive they point at has anything to look at.

    It still errors, because a ``.zip`` is not renderable however good a
    reason there is to want it rendered. That is the pre-existing limit this
    change does not touch and must not paper over: the item is refused, not
    answered from the source it happens to contain.
    """
    plan = plan_task_runtime(
        {}, _task(_PROMPT, EXCLUDED_ITEMS), tmp_path
    )

    assert plan["judge_routes"] == {"visual": 5}
    assert all(
        "required_visual_render_target_unavailable" in error
        for error in plan["errors"]
    )
    assert len(plan["errors"]) == 5


def test_a_csv_is_still_refused_rather_than_answered_from_its_characters(
    tmp_path
):
    """The fail-closed rule this sits next to, through the whole grader path.

    Data has a look that a reader sees on opening it, so "page layout is
    visually polished" against a ``.csv`` is not a question reading can
    honestly settle, and a text verdict there would be invented rather than
    merely absent. ``.csv`` is deliberately absent from
    ``GRADER_SOURCE_CODE_EXTENSIONS`` for this reason.
    ``test_explicit_visual_item_fails_closed_without_render_target`` covers
    the same property from the selector side.
    """
    (tmp_path / "Summary.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    item = RubricItem(
        "polish", "Document color and page layout are visually polished.", 4,
        None,
    )

    plan = plan_task_runtime({}, _task("Produce Summary.csv.", [item]), tmp_path)

    assert plan["judge_routes"] == {"visual": 1}
    assert any(
        "required_visual_render_target_unavailable" in error
        for error in plan["errors"]
    )
    assert _probe_surface()._selected_paths_are_source_code(
        tmp_path, ["Summary.csv"]
    ) is False


def test_finding_source_does_not_route_the_rest_of_the_task_to_text(
    tmp_path, component
):
    """Why the probe is defensive only.

    The other thirty-four items on this task are ordinary content checks that
    were already routing text, and one of them asks whether the archive opens
    at all. Demoting on the file rather than on the criterion would be a
    different change with a different blast radius; this one only ever fires
    where the criterion itself named something visual.
    """
    opens = RubricItem(
        "zip", "The submission is a .zip archive that opens successfully.", 1,
        None,
    )

    plan = plan_task_runtime(
        {}, _task(_PROMPT, [opens, EXCLUDED_ITEMS[0]]), tmp_path
    )

    assert plan["judge_routes"] == {"text": 2}
    assert plan["errors"] == []
