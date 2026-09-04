"""#161 -- a latency nobody measured is not a task that took no time.

#114 fixed the summary level: a run where nothing was timed stopped publishing
``Avg Latency | 0ms``. It could not fix the per-task level, because its
``_report`` helper drives ``_build_report_data`` with ``task_results=[]`` --
the two task tables were never rendered, so the per-task latency cell was
never exercised by that test at all.

Both tables handed the value straight to ``f"{value:.0f}ms"``, and that is two
defects in one expression.

**It crashes.** Step 2 writes ``latency_ms: None`` on purpose for a task that
failed before anything was timed -- a reference-integrity failure
(``step2_run_inference.py:2128``) or an exception raised on the way to the call
(``:2309``, ``:2325``). ``result.get("latency_ms", 0)`` does *not* turn that
into a 0: the default fires only when the key is **absent**, and the key is
present holding ``None``. So ``None`` reached the format string and raised
``TypeError: unsupported format string passed to NoneType.__format__``. Step 6
died and no report was written at all.

**It invents a measurement.** A payload that carries no ``latency_ms`` key got
the ``0`` default and printed ``0ms`` -- a duration, in a column where every
other row is a real one.

In the *same* f-string, ``qa_score`` is guarded honestly::

    qa_str = f"{r['qa_score']}/10" if r["qa_score"] is not None else "-"

The row already knew how to say "not recorded". It did it for the score and
not for the time.

Two producers, one contract. ``core/hf_publication`` projects the same field
through ``core.result_projection.project_result_row`` and
``hf_publication.py:996`` refuses to upload when its projection disagrees with
what step 6 wrote, so both sides moved together and the agreement is asserted
below rather than assumed.

No published number moves. Every aggregation site filters with a *truthiness*
test -- ``step3_format_results.py:97``/``:107``, ``step6_report.py:200``/
``:439``, ``hf_publication.py:905`` -- which already dropped ``None`` and ``0``
alike, so no average, max or total can shift. The dashboard already rendered a
falsy latency as an em dash (``ExperimentDetail.tsx:1136``, ``:1382``), so a
``null`` displays exactly where a ``0`` used to.

One direction only: a task that really was timed keeps its exact previous text,
and a task that genuinely took 0ms still prints ``0ms``. Both are negative
controls here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BATCH_RUNNER = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER))

import step3_format_results as step3  # noqa: E402
import step6_report  # noqa: E402
from core.hf_publication import (  # noqa: E402
    PublicationTaskResult,
    _publication_summary,
    _task_report_projection,
)
from core.prepared_fingerprint import prepared_fingerprint  # noqa: E402
from core.result_fingerprint import inference_result_fingerprint  # noqa: E402
from core.result_projection import project_result_row  # noqa: E402

REPO_ROOT = BATCH_RUNNER.parent
SRC = REPO_ROOT / "src"


# ── Fixtures ──────────────────────────────────────────────────────────────


def _run(results: list[dict]) -> dict:
    return {
        "experiment_id": "exp999_unmeasured_latency",
        "experiment_name": "unmeasured latency",
        "condition_name": "condition_a",
        "model": "gpt-5.6",
        "execution_mode": "subprocess",
        "started_at": "2026-09-04T00:00:00Z",
        "duration": "0m",
        "results": results,
    }


def _timed(task_id: str, ms: float, sector: str = "Finance") -> dict:
    """A task that was measured. Its cell must not move."""
    return {
        "task_id": task_id,
        "status": "success",
        "sector": sector,
        "occupation": "Analyst",
        "qa_score": 8.5,
        "latency_ms": ms,
    }


def _never_timed(task_id: str, sector: str = "Finance") -> dict:
    """What step 2 actually writes when it fails before timing anything."""
    return {
        "task_id": task_id,
        "status": "error",
        "sector": sector,
        "occupation": "Analyst",
        "latency_ms": None,
        "error": "reference input integrity check failed",
    }


def _no_latency_key(task_id: str, sector: str = "Finance") -> dict:
    """An older payload that carries no latency field at all."""
    return {
        "task_id": task_id,
        "status": "error",
        "sector": sector,
        "occupation": "Analyst",
        "error": "boom",
    }


def _genuine_zero(task_id: str, sector: str = "Finance") -> dict:
    """A task that really was timed, at 0ms. The dash must not swallow it."""
    return {
        "task_id": task_id,
        "status": "success",
        "sector": sector,
        "occupation": "Analyst",
        "qa_score": 7,
        "latency_ms": 0,
    }


def _report(results: list[dict]) -> tuple[list[dict], str, str]:
    """Drive the real path with a NON-empty task table -- #114's blind spot."""
    data = _run(results)
    task_results, error_tasks = step6_report._build_task_results(data)
    report_data = step6_report._build_report_data(
        data,
        {
            "overview": "",
            "quality_analysis": "",
            "failure_patterns": "",
            "recommendations": "",
        },
        step6_report._compute_summary(data),
        step6_report._compute_sector_breakdown(data),
        task_results=task_results,
        error_tasks=error_tasks,
    )
    return (
        task_results,
        step6_report._build_markdown(report_data),
        step6_report._build_html(report_data),
    )


def _task_rows(text: str, marker: str) -> list[str]:
    """Rows of the per-task table -- the lines naming a task id."""
    return [line for line in text.splitlines() if marker in line]


# ── The defect ────────────────────────────────────────────────────────────


class TestTheCrash:
    def test_formatting_none_as_a_duration_is_the_error_that_killed_step6(self):
        """The expression both tables used, against the value step 2 writes."""
        with pytest.raises(TypeError):
            f"{None:.0f}ms"

    def test_get_with_a_zero_default_does_not_rescue_a_stored_none(self):
        """Why the 0 default never prevented it: the key is present."""
        stored = {"latency_ms": None}
        assert stored.get("latency_ms", 0) is None

    def test_a_report_with_an_unmeasured_task_is_written_at_all(self):
        """Regression: this raised TypeError and produced no report."""
        rows, markdown, html = _report([_timed("t1", 1200), _never_timed("t2")])
        assert rows[1]["latency_ms"] is None
        assert markdown.strip()
        assert html.strip()

    def test_every_step2_unmeasured_task_renders_without_raising(self):
        """All three of step 2's untimed exits write the same None."""
        for i in range(3):
            _rows, markdown, html = _report([_never_timed(f"t{i}")])
            assert markdown.strip() and html.strip()


# ── Three states, kept apart ──────────────────────────────────────────────


class TestTheMarkdownTable:
    def test_a_task_step2_never_timed_says_so(self):
        _rows, markdown, _html = _report([_never_timed("t1")])
        row = _task_rows(markdown, "t1")[0]
        assert row.endswith("| - |"), row
        assert "0ms" not in row

    def test_a_task_carrying_no_latency_key_says_so_too(self):
        _rows, markdown, _html = _report([_no_latency_key("t1")])
        row = _task_rows(markdown, "t1")[0]
        assert row.endswith("| - |"), row
        assert "0ms" not in row

    def test_a_measured_task_keeps_its_exact_previous_text(self):
        _rows, markdown, _html = _report([_timed("t1", 1200)])
        assert "| 8.5/10 | 1200ms |" in markdown

    def test_a_measured_task_still_rounds_the_way_it_always_did(self):
        _rows, markdown, _html = _report([_timed("t1", 1234.6)])
        assert "1235ms" in markdown

    def test_a_task_that_really_took_no_time_still_prints_zero(self):
        _rows, markdown, _html = _report([_genuine_zero("t1")])
        assert "| 7/10 | 0ms |" in markdown

    def test_the_three_states_are_three_different_cells(self):
        _rows, markdown, _html = _report(
            [_timed("t1", 1200), _never_timed("t2"), _no_latency_key("t3")]
        )
        measured = _task_rows(markdown, "t1")[0]
        unmeasured = _task_rows(markdown, "t2")[0]
        absent = _task_rows(markdown, "t3")[0]
        assert measured.endswith("| 1200ms |")
        assert unmeasured.endswith("| - |")
        assert absent.endswith("| - |")
        # Scoped to the task rows on purpose: the Key Metrics table above them
        # prints a real ``1,200ms`` average, and that measurement is correct.
        assert "ms" not in unmeasured and "ms" not in absent


class TestTheHtmlTable:
    def test_a_task_step2_never_timed_says_so(self):
        _rows, _markdown, html = _report([_never_timed("t1")])
        row = _task_rows(html, "t1")[0]
        assert "<td>—</td></tr>" in row, row
        assert "0ms" not in row

    def test_a_task_carrying_no_latency_key_says_so_too(self):
        _rows, _markdown, html = _report([_no_latency_key("t1")])
        assert "<td>—</td></tr>" in _task_rows(html, "t1")[0]

    def test_a_measured_task_keeps_its_exact_previous_text(self):
        _rows, _markdown, html = _report([_timed("t1", 1200)])
        assert "<td>8.5/10</td><td>1200ms</td></tr>" in html

    def test_a_task_that_really_took_no_time_still_prints_zero(self):
        _rows, _markdown, html = _report([_genuine_zero("t1")])
        assert "<td>0ms</td></tr>" in html

    def test_the_em_dash_is_the_one_the_score_cell_beside_it_uses(self):
        """The row already said '—' for an unscored task. Same word, same row."""
        _rows, _markdown, html = _report([_never_timed("t1")])
        assert "<td>—</td><td>—</td></tr>" in html


# ── The cell renderer itself ──────────────────────────────────────────────


class TestTheCell:
    @pytest.mark.parametrize("value", [None, "1200", "", [], {}, object()])
    def test_anything_that_is_not_a_number_is_not_a_duration(self, value):
        assert step6_report._task_latency_cell(value, absent="-") == "-"

    def test_a_bool_is_not_a_measurement_either(self):
        """True is an int in Python. It is not 1 millisecond."""
        assert step6_report._task_latency_cell(True, absent="-") == "-"
        assert step6_report._task_latency_cell(False, absent="-") == "-"

    @pytest.mark.parametrize(
        "value,expected",
        [(0, "0ms"), (0.0, "0ms"), (5, "5ms"), (1234.6, "1235ms")],
    )
    def test_a_real_measurement_renders_exactly_as_before(self, value, expected):
        assert step6_report._task_latency_cell(value, absent="-") == expected

    def test_the_caller_chooses_how_absence_is_spelled(self):
        assert step6_report._task_latency_cell(None, absent="—") == "—"
        assert step6_report._task_latency_cell(None, absent="-") == "-"


# ── The projection ────────────────────────────────────────────────────────


class TestTheProjection:
    def test_an_unmeasured_latency_survives_as_unmeasured(self):
        row = project_result_row({}, _never_timed("t1"))
        assert row["latency_ms"] is None

    def test_an_absent_latency_is_not_invented_as_zero(self):
        row = project_result_row({}, _no_latency_key("t1"))
        assert row["latency_ms"] is None

    def test_a_measured_latency_is_carried_through_untouched(self):
        row = project_result_row({}, _timed("t1", 1234.6))
        assert row["latency_ms"] == 1234.6

    def test_a_genuine_zero_is_carried_through_as_a_zero(self):
        row = project_result_row({}, _genuine_zero("t1"))
        assert row["latency_ms"] == 0


# ── Two producers, one contract ───────────────────────────────────────────


class TestBothProducersAgree:
    """``hf_publication.py:996`` refuses to upload on any disagreement.

    Fixing step 6 alone would have made every run containing an untimed task
    unpublishable. Both sides read the same field the same way, and that is
    asserted here rather than assumed.
    """

    @pytest.mark.parametrize(
        "result", [_never_timed("t1"), _no_latency_key("t1"), _genuine_zero("t1")]
    )
    def test_step6_and_the_publication_projection_render_the_same_value(
        self, result
    ):
        step6_rows, _markdown, _html = _report([result])
        published = _task_report_projection(
            PublicationTaskResult(
                result["task_id"],
                "",
                (),
                (),
                (),
                status=result["status"],
                latency_ms=project_result_row({}, result)["latency_ms"],
            )
        )
        assert step6_rows[0]["latency_ms"] == published["latency_ms"]

    def test_the_publication_summary_is_unmoved_by_an_unmeasured_task(self):
        """Its ``if result.latency_ms`` filter already dropped None and 0."""
        timed = PublicationTaskResult("t1", "", (), (), (), latency_ms=1200)
        with_none = _publication_summary(
            (timed, PublicationTaskResult("t2", "", (), (), (), latency_ms=None))
        )
        with_zero = _publication_summary(
            (timed, PublicationTaskResult("t2", "", (), (), (), latency_ms=0))
        )
        assert with_none == with_zero
        assert with_none["avg_latency_ms"] == 1200
        assert with_none["total_latency_ms"] == 1200


# ── No published number moves ─────────────────────────────────────────────


class TestNoAggregateMoves:
    """Owner rule: a new distinction must not disturb an existing experiment."""

    def test_the_run_summary_is_identical_whichever_way_absence_is_spelled(self):
        stored_none = step6_report._compute_summary(
            _run([_timed("t1", 1200), _never_timed("t2")])
        )
        key_absent = step6_report._compute_summary(
            _run([_timed("t1", 1200), _no_latency_key("t2")])
        )
        assert stored_none == key_absent
        assert stored_none["avg_latency_ms"] == 1200
        assert stored_none["max_latency_ms"] == 1200
        assert stored_none["total_latency_ms"] == 1200

    def test_the_sector_breakdown_is_identical_too(self):
        stored_none = step6_report._compute_sector_breakdown(
            _run([_timed("t1", 1200), _never_timed("t2")])
        )
        key_absent = step6_report._compute_sector_breakdown(
            _run([_timed("t1", 1200), _no_latency_key("t2")])
        )
        assert stored_none == key_absent

    def test_a_run_where_everything_was_timed_is_untouched(self):
        summary = step6_report._compute_summary(
            _run([_timed("t1", 1200), _timed("t2", 800)])
        )
        assert summary["avg_latency_ms"] == 1000
        assert summary["max_latency_ms"] == 1200
        assert summary["total_latency_ms"] == 2000


# ── Step 3 renders the other task table ───────────────────────────────────


def _step3_markdown(tmp_path, monkeypatch) -> str:
    """Drive the real ``format_results()`` over the three states.

    Step 3 writes ``results/<exp_id>/<exp_id>.md``, whose task table carries the
    same latency column. It used ``r.get("latency_ms") or 0``, which does not
    crash -- and prints ``0ms`` for a task nobody timed, which is the other half
    of this defect.
    """
    task_ids = ["timed", "never-timed", "no-key"]
    prepared = {
        "experiment_id": "exp998",
        "experiment_name": "unmeasured latency",
        "publication_generation": "exp998:100:1",
        "source": "student/exp998",
        "task_scope": {"task_ids": task_ids},
        "tasks": [
            {"task_id": tid, "sector": "Finance", "occupation": "Accountants"}
            for tid in task_ids
        ],
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)

    results = [
        {
            "task_id": "timed",
            "status": "success",
            "deliverable_text": "a deliverable",
            "deliverable_files": [],
            "latency_ms": 1200,
        },
        {
            "task_id": "never-timed",
            "status": "error",
            "deliverable_text": "",
            "deliverable_files": [],
            "latency_ms": None,
            "error": "reference input integrity check failed",
        },
        {
            "task_id": "no-key",
            "status": "error",
            "deliverable_text": "",
            "deliverable_files": [],
            "error": "boom",
        },
    ]
    inference = {
        "experiment_id": "exp998",
        "experiment_name": "unmeasured latency",
        "publication_generation": "exp998:100:1",
        "source": "student/exp998",
        "prepared_fingerprint": prepared["prepared_fingerprint"],
        "ordered_task_ids": task_ids,
        "condition": "condition_a",
        "execution_mode": "sandbox",
        "model": "gpt-5.4",
        "started_at": "2026-09-04T08:00:00Z",
        "completed_at": "2026-09-04T08:10:00Z",
        "resume_rounds_used": 0,
        "results": results,
        "summary": {"total": 3, "success": 1, "error": 2, "qa_failed": 0},
    }
    inference["result_fingerprint"] = inference_result_fingerprint(inference)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    root = tmp_path / "batch-runner"
    root.mkdir()
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    (workspace / "step2_inference_results.json").write_text(
        json.dumps(inference), encoding="utf-8"
    )
    monkeypatch.setattr(step3, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step3, "BATCH_RUNNER_ROOT", root)
    step3.format_results()
    return (root / "results" / "exp998" / "exp998.md").read_text(encoding="utf-8")


class TestTheStep3TaskTable:
    def test_a_task_step2_never_timed_says_so(self, tmp_path, monkeypatch):
        row = _task_rows(_step3_markdown(tmp_path, monkeypatch), "never-ti")[0]
        assert row.endswith("| - |"), row
        assert "ms" not in row

    def test_a_task_carrying_no_latency_key_says_so_too(self, tmp_path, monkeypatch):
        row = _task_rows(_step3_markdown(tmp_path, monkeypatch), "no-key")[0]
        assert row.endswith("| - |"), row
        assert "ms" not in row

    def test_a_measured_task_keeps_its_exact_previous_text(
        self, tmp_path, monkeypatch
    ):
        row = _task_rows(_step3_markdown(tmp_path, monkeypatch), "`timed…`")[0]
        assert row.endswith("| 1200ms |"), row

    def test_the_sector_average_still_counts_only_what_was_timed(
        self, tmp_path, monkeypatch
    ):
        """Its truthiness filter already dropped both. No published number moves."""
        markdown = _step3_markdown(tmp_path, monkeypatch)
        assert "| 1,200ms |" in markdown


# ── The frontend mirror ───────────────────────────────────────────────────

class TestTheDashboardSaysTheSameThing:
    def test_the_type_admits_the_value_the_producer_writes(self):
        types = (SRC / "types" / "report.ts").read_text(encoding="utf-8")
        assert "latency_ms: number | null" in types

    def test_the_task_cell_still_renders_absence_as_an_em_dash(self):
        page = (SRC / "pages" / "ExperimentDetail.tsx").read_text(encoding="utf-8")
        cell = "task.latency_ms ? `${(task.latency_ms / 1000).toFixed(1)}s` : '—'"
        assert page.count(cell) == 2
        assert "task.latency_ms ?? 0" not in page

    def test_sorting_puts_an_unmeasured_task_where_an_unscored_one_goes(self):
        page = (SRC / "pages" / "ExperimentDetail.tsx").read_text(encoding="utf-8")
        assert page.count("latency_ms ?? -1") == 2
