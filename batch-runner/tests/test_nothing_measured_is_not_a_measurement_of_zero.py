"""#114 -- a run that measured nothing must not publish zero.

``step6_report._compute_summary`` averaged the scores it had. When it had none
-- every task errored, so no task was scored, and nothing recorded a latency --
it wrote ``0.0`` and ``0`` anyway, and the report published::

    | Avg QA Score | 0.0/10 |
    | Avg Latency  | 0ms    |

which reads as a model that failed every rubric item in no time at all. Neither
sentence was measured. The same collapse ran in ``_compute_sector_breakdown``,
so a sector whose every task errored was published as a sector that scored zero.

The repo already knew the answer. ``step3_format_results.py:103`` computes the
same quantities as ``... if b["scores"] else None`` and renders a dash for the
empty case at ``:420``. ``ExperimentDetail.tsx`` renders a per-task score as
``task.qa_score != null ? ... : '—'``. Only the aggregate invented a number.

Two producers, one contract. ``core/hf_publication._publication_summary``
recomputes the summary from the published identity and ``hf_publication.py:996``
refuses to upload on any difference, so fixing one side alone would have made
every all-error run unpublishable. Both moved together, and the agreement is
asserted below rather than assumed.

One direction only: a run that measured anything is untouched, and a score that
really is zero still prints ``0.0/10``. Both are negative controls here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BATCH_RUNNER = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER))

import step6_report  # noqa: E402
from core.hf_publication import PublicationTaskResult, _publication_summary  # noqa: E402
from core.measurement_display import NOT_MEASURED, render_measured  # noqa: E402
from core.narrative_analyzer import NarrativeAnalyzer  # noqa: E402

REPO_ROOT = BATCH_RUNNER.parent
SRC = REPO_ROOT / "src"

#: The six figures that have no honest zero. ``success_rate_pct`` is
#: deliberately not among them: its 0.0 fallback fires only when
#: ``total_tasks`` is 0, and that 0 is printed right beside it, so a reader can
#: see there was nothing to divide.
UNMEASURABLE_KEYS = (
    "avg_qa_score",
    "min_qa_score",
    "max_qa_score",
    "avg_latency_ms",
    "max_latency_ms",
    "total_latency_ms",
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _run(results: list[dict]) -> dict:
    return {
        "experiment_id": "exp999_nothing_measured",
        "experiment_name": "nothing measured",
        "condition_name": "condition_a",
        "model": "gpt-5.6",
        "execution_mode": "subprocess",
        "started_at": "2026-08-31T00:00:00Z",
        "duration": "0m",
        "results": results,
    }


def _error(task_id: str, sector: str = "Finance") -> dict:
    return {"task_id": task_id, "status": "error", "sector": sector, "error": "boom"}


def _scored(task_id: str, qa: float, ms: int, sector: str = "Finance") -> dict:
    return {
        "task_id": task_id,
        "status": "success",
        "sector": sector,
        "qa_score": qa,
        "latency_ms": ms,
    }


#: Every task errored. Nothing was scored and nothing was timed.
ALL_ERROR = [_error("t1"), _error("t2")]

#: One task got through. This run must come out exactly as it always did.
MIXED = [_scored("t1", 8.5, 1200), _error("t2")]

#: A task that really did score zero, in five milliseconds. The dash must not
#: swallow it.
GENUINE_ZERO = [_scored("t1", 0, 5)]


def _report(results: list[dict]) -> tuple[dict, list[dict], str, str]:
    """Drive the real path: summary -> sectors -> report_data -> markdown/html."""
    data = _run(results)
    summary = step6_report._compute_summary(data)
    sectors = step6_report._compute_sector_breakdown(data)
    report_data = step6_report._build_report_data(
        data,
        {
            "overview": "",
            "quality_analysis": "",
            "failure_patterns": "",
            "recommendations": "",
        },
        summary,
        sectors,
        task_results=[],
        error_tasks=[],
    )
    return (
        summary,
        sectors,
        step6_report._build_markdown(report_data),
        step6_report._build_html(report_data),
    )


def _key_metrics(markdown: str) -> dict[str, str]:
    """The ``| Metric | Value |`` rows of the Key Metrics table."""
    rows: dict[str, str] = {}
    inside = False
    for line in markdown.splitlines():
        if line.startswith("## Key Metrics"):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside and line.startswith("| ") and "|--" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 2 and cells[0] != "Metric":
                rows[cells[0]] = cells[1]
    return rows


# ── The helper ────────────────────────────────────────────────────────────


class TestRenderMeasured:
    def test_absent_renders_the_dash(self):
        assert render_measured(None) == NOT_MEASURED
        assert render_measured(None, "/10") == NOT_MEASURED
        assert render_measured(None, "ms", ",") == NOT_MEASURED

    def test_a_real_zero_still_renders_as_zero(self):
        assert render_measured(0) == "0"
        assert render_measured(0, "/10") == "0/10"
        assert render_measured(0.0, "/10", ".1f") == "0.0/10"
        assert render_measured(0, "ms", ",") == "0ms"

    def test_the_dash_is_the_one_step3_writes(self):
        # step3_format_results.py renders "-" for an empty bucket. A reader who
        # has seen one report has already seen this one.
        step3 = (BATCH_RUNNER / "step3_format_results.py").read_text(encoding="utf-8")
        assert 'else "-"' in step3
        assert NOT_MEASURED == "-"

    @pytest.mark.parametrize(
        ("value", "suffix", "spec", "expected"),
        [
            (8.5, "/10", "", "8.5/10"),
            (1200, "ms", ",", "1,200ms"),
            (1234567, "ms", ",", "1,234,567ms"),
            (6.239, "/10", ".1f", "6.2/10"),
            (10, "/10", "", "10/10"),
        ],
    )
    def test_a_measured_value_keeps_its_formatting(self, value, suffix, spec, expected):
        assert render_measured(value, suffix, spec) == expected


# ── The producer ──────────────────────────────────────────────────────────


class TestSummary:
    def test_all_error_run_measures_nothing(self):
        summary, _, _, _ = _report(ALL_ERROR)
        for key in UNMEASURABLE_KEYS:
            assert summary[key] is None, f"{key} invented a measurement"

    def test_all_error_run_still_reports_what_it_does_know(self):
        summary, _, _, _ = _report(ALL_ERROR)
        assert summary["total_tasks"] == 2
        assert summary["success_count"] == 0
        assert summary["error_count"] == 2
        # Deliberately kept: 0 successes out of 2 really is 0.0%, and the 2 is
        # printed beside it.
        assert summary["success_rate_pct"] == 0.0

    def test_a_measured_run_is_unchanged(self):
        summary, _, _, _ = _report(MIXED)
        assert summary["avg_qa_score"] == 8.5
        assert summary["min_qa_score"] == 8.5
        assert summary["max_qa_score"] == 8.5
        assert summary["avg_latency_ms"] == 1200
        assert summary["max_latency_ms"] == 1200
        assert summary["total_latency_ms"] == 1200
        assert summary["total_tasks"] == 2
        assert summary["success_count"] == 1
        assert summary["success_rate_pct"] == 50.0

    def test_a_genuine_zero_survives(self):
        summary, _, _, _ = _report(GENUINE_ZERO)
        assert summary["avg_qa_score"] == 0.0
        assert summary["min_qa_score"] == 0
        assert summary["max_qa_score"] == 0
        assert summary["avg_latency_ms"] == 5

    def test_one_measured_task_is_enough(self):
        # The boundary: the smallest run that has anything to average.
        summary, _, _, _ = _report([_scored("t1", 7.25, 900)])
        assert summary["avg_qa_score"] == 7.25
        assert summary["total_latency_ms"] == 900

    def test_an_empty_run_measures_nothing_and_does_not_divide(self):
        summary, sectors, _, _ = _report([])
        assert summary["total_tasks"] == 0
        assert summary["success_rate_pct"] == 0.0
        assert sectors == []
        for key in UNMEASURABLE_KEYS:
            assert summary[key] is None

    def test_a_scored_task_that_errored_still_counts_as_a_measurement(self):
        # qa_score is what makes a score, not status. A task that scored and
        # then failed has been measured.
        summary, _, _, _ = _report(
            [{"task_id": "t1", "status": "error", "sector": "Finance",
              "qa_score": 3.0, "latency_ms": 400, "error": "boom"}]
        )
        assert summary["avg_qa_score"] == 3.0
        assert summary["avg_latency_ms"] == 400
        assert summary["success_count"] == 0


class TestSectorBreakdown:
    def test_a_sector_whose_tasks_all_errored_measures_nothing(self):
        _, sectors, _, _ = _report(ALL_ERROR)
        assert len(sectors) == 1
        assert sectors[0]["sector"] == "Finance"
        assert sectors[0]["total"] == 2
        assert sectors[0]["avg_qa_score"] is None
        assert sectors[0]["avg_latency_ms"] is None

    def test_one_dead_sector_does_not_silence_a_live_one(self):
        _, sectors, _, _ = _report(
            [_scored("t1", 9.0, 800, "Information"), _error("t2", "Finance")]
        )
        by_sector = {s["sector"]: s for s in sectors}
        assert by_sector["Information"]["avg_qa_score"] == 9.0
        assert by_sector["Information"]["avg_latency_ms"] == 800
        assert by_sector["Finance"]["avg_qa_score"] is None
        assert by_sector["Finance"]["avg_latency_ms"] is None

    def test_a_sector_that_scored_zero_is_not_a_sector_that_scored_nothing(self):
        _, sectors, _, _ = _report(GENUINE_ZERO)
        assert sectors[0]["avg_qa_score"] == 0.0
        assert sectors[0]["avg_latency_ms"] == 5


# ── What gets published ───────────────────────────────────────────────────


class TestMarkdown:
    def test_all_error_run_prints_dashes_not_zeroes(self):
        _, _, markdown, _ = _report(ALL_ERROR)
        metrics = _key_metrics(markdown)
        for label in (
            "Avg QA Score",
            "Min QA Score",
            "Max QA Score",
            "Avg Latency",
            "Max Latency",
            "Total LLM Time",
        ):
            assert metrics[label] == NOT_MEASURED, f"{label} published a number"
        assert "0.0/10" not in markdown
        assert "0ms" not in markdown

    def test_total_llm_time_does_not_divide_an_absent_measurement(self):
        # ``total_latency_ms // 1000`` on None is a TypeError. The report would
        # not have been written at all.
        _, _, markdown, _ = _report(ALL_ERROR)
        assert _key_metrics(markdown)["Total LLM Time"] == NOT_MEASURED

    def test_all_error_run_still_prints_its_counts(self):
        _, _, markdown, _ = _report(ALL_ERROR)
        metrics = _key_metrics(markdown)
        assert metrics["Total Tasks"] == "2"
        assert metrics["Success"] == "0 (0.0%)"
        assert metrics["Errors"] == "2"

    def test_a_measured_run_prints_exactly_what_it_always_did(self):
        _, _, markdown, _ = _report(MIXED)
        metrics = _key_metrics(markdown)
        assert metrics["Avg QA Score"] == "8.5/10"
        assert metrics["Min QA Score"] == "8.5/10"
        assert metrics["Max QA Score"] == "8.5/10"
        assert metrics["Avg Latency"] == "1,200ms"
        assert metrics["Max Latency"] == "1,200ms"
        assert metrics["Total LLM Time"] == "1s"
        assert NOT_MEASURED not in metrics.values()

    def test_a_genuine_zero_prints_as_zero(self):
        _, _, markdown, _ = _report(GENUINE_ZERO)
        metrics = _key_metrics(markdown)
        assert metrics["Avg QA Score"] == "0.0/10"
        assert metrics["Min QA Score"] == "0/10"
        assert metrics["Avg Latency"] == "5ms"
        assert metrics["Total LLM Time"] == "0s"
        assert NOT_MEASURED not in metrics.values()

    def test_a_dead_sector_row_carries_dashes(self):
        _, _, markdown, _ = _report(ALL_ERROR)
        row = next(line for line in markdown.splitlines() if line.startswith("| Finance"))
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert cells[0] == "Finance"
        assert cells[1] == "2"
        assert cells[-2] == NOT_MEASURED
        assert cells[-1] == NOT_MEASURED

    def test_a_live_sector_row_is_unchanged(self):
        _, _, markdown, _ = _report(MIXED)
        row = next(line for line in markdown.splitlines() if line.startswith("| Finance"))
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert cells[-2] == "8.5/10"
        assert cells[-1] == "1,200ms"


class TestHtml:
    def test_all_error_run_shows_no_zero_score_card(self):
        _, _, _, html = _report(ALL_ERROR)
        assert f">{NOT_MEASURED}</div>" in html
        assert ">0.0</div>" not in html

    def test_a_measured_run_keeps_its_cards(self):
        _, _, _, html = _report(MIXED)
        assert ">8.5</div>" in html
        assert f">{NOT_MEASURED}</div>" not in html

    def test_a_genuine_zero_keeps_its_card(self):
        _, _, _, html = _report(GENUINE_ZERO)
        assert ">0.0</div>" in html
        assert f">{NOT_MEASURED}</div>" not in html


# ── The publication gate ──────────────────────────────────────────────────


def _gate_summary(results: list[dict]) -> dict:
    """What ``step7_upload_hf.sh`` recomputes before it will publish."""
    identity = tuple(
        PublicationTaskResult(
            task_id=r["task_id"],
            deliverable_text="",
            deliverable_files=(),
            deliverable_file_urls=(),
            deliverable_file_hf_uris=(),
            status=r.get("status", "success"),
            sector=r.get("sector", ""),
            retried=r.get("retried", False),
            qa_score=r.get("qa_score"),
            latency_ms=r.get("latency_ms", 0),
        )
        for r in results
    )
    return _publication_summary(identity)


class TestPublicationGate:
    """``hf_publication.py:996`` refuses to upload when the two disagree.

    Fixing only ``step6_report`` would have made every all-error run
    unpublishable -- a worse failure than the one being fixed.
    """

    @pytest.mark.parametrize(
        ("label", "results"),
        [("all-error", ALL_ERROR), ("mixed", MIXED), ("genuine-zero", GENUINE_ZERO),
         ("empty", [])],
    )
    def test_both_producers_agree(self, label, results):
        summary, _, _, _ = _report(results)
        assert _gate_summary(results) == summary, f"{label} would be refused publication"

    def test_the_gate_measures_nothing_on_an_all_error_run(self):
        gate = _gate_summary(ALL_ERROR)
        for key in UNMEASURABLE_KEYS:
            assert gate[key] is None

    def test_the_gate_still_rejects_a_real_disagreement(self):
        # The agreement above is not vacuous: a summary that differs is caught.
        summary, _, _, _ = _report(ALL_ERROR)
        tampered = dict(summary, avg_qa_score=0.0)
        assert _gate_summary(ALL_ERROR) != tampered


# ── The narrator ──────────────────────────────────────────────────────────


def _narrative_prompt(summary: dict, sectors: list[dict]) -> str:
    """The user prompt call 1 hands the narrating model."""
    analyzer = NarrativeAnalyzer.__new__(NarrativeAnalyzer)
    analyzer.client = None
    analyzer.model = "gpt-5.6-sol"
    analyzer.reasoning_effort = "max"
    analyzer._heartbeat_active = False
    analyzer._heartbeat_thread = None
    analyzer._start_heartbeat = lambda: None
    analyzer._stop_heartbeat = lambda: None

    captured: dict[str, str] = {}

    def _capture(system, user_prompt):
        captured["user"] = user_prompt
        # ``_parse_response`` rejects empty values, so the stub returns prose.
        return ('{"overview": "ok", "quality_analysis": "ok"}', 1.0, 1, 1)

    analyzer._call_responses_api = _capture
    analyzer._call_1_sector_analysis({"meta": {}}, summary, sectors)
    return captured["user"]


class TestNarratorPrompt:
    """A figure that reaches the narrator comes back as published prose.

    A table cell can be corrected. A paragraph saying the model scored zero is
    harder to withdraw, so the absence is spelled out here rather than left as
    a dash to be interpreted.
    """

    def test_an_unmeasured_run_does_not_hand_the_narrator_a_zero(self):
        summary, sectors, _, _ = _report(ALL_ERROR)
        prompt = _narrative_prompt(summary, sectors)
        assert "0/10" not in prompt
        assert "0.0/10" not in prompt
        assert "0ms" not in prompt

    def test_an_unmeasured_run_is_told_the_figure_is_absent(self):
        summary, sectors, _, _ = _report(ALL_ERROR)
        prompt = _narrative_prompt(summary, sectors)
        assert "was never measured" in prompt
        assert "not that it came out" in prompt
        assert "Do not describe it as a low score" in prompt

    def test_a_measured_run_is_not_given_the_note(self):
        summary, sectors, _, _ = _report(MIXED)
        prompt = _narrative_prompt(summary, sectors)
        assert "was never measured" not in prompt
        assert "8.5/10" in prompt
        assert "1200ms" in prompt

    def test_a_genuine_zero_is_not_called_absent(self):
        summary, sectors, _, _ = _report(GENUINE_ZERO)
        prompt = _narrative_prompt(summary, sectors)
        assert "was never measured" not in prompt
        assert "0/10" in prompt

    def test_a_dead_sector_alone_still_triggers_the_note(self):
        summary, sectors, _, _ = _report(
            [_scored("t1", 9.0, 800, "Information"), _error("t2", "Finance")]
        )
        # The run-level figures were all measured; only one sector was not.
        assert all(summary[key] is not None for key in UNMEASURABLE_KEYS)
        prompt = _narrative_prompt(summary, sectors)
        assert "was never measured" in prompt

    def test_the_prompt_survives_an_absent_score_at_all(self):
        # The sector line used to format avg_qa_score with ":.1f", which raises
        # TypeError on None. The narrative call would have died outright.
        summary, sectors, _, _ = _report(ALL_ERROR)
        assert NOT_MEASURED in _narrative_prompt(summary, sectors)


# ── The dashboard reads the same contract ─────────────────────────────────


class TestFrontendMirror:
    """``scripts/aggregate-reports.mjs`` copies these straight onto the board.

    ``ExperimentEntry.avg_qa_score`` feeds ``.toFixed(2)`` in the leaderboard,
    so a null that the TypeScript did not admit to would be a crash rather than
    a dash.
    """

    def test_report_summary_admits_the_six_can_be_absent(self):
        report_ts = (SRC / "types" / "report.ts").read_text(encoding="utf-8")
        block = report_ts.split("export interface ReportSummary")[1].split("}")[0]
        for key in UNMEASURABLE_KEYS:
            assert f"{key}: number | null" in block, f"{key} is still typed as a number"

    def test_success_rate_stays_a_number_on_purpose(self):
        report_ts = (SRC / "types" / "report.ts").read_text(encoding="utf-8")
        block = report_ts.split("export interface ReportSummary")[1].split("}")[0]
        assert "success_rate_pct: number\n" in block

    def test_sector_and_leaderboard_entries_admit_it_too(self):
        report_ts = (SRC / "types" / "report.ts").read_text(encoding="utf-8")
        for interface in ("SectorBreakdown", "ExperimentEntry", "SectorMatrix"):
            block = report_ts.split(f"export interface {interface}")[1].split("\n}")[0]
            assert "avg_qa_score: number | null" in block, interface

    def test_no_surface_coerces_an_absent_score_to_zero(self):
        # `?? 0` on one of these is the same defect in a different language: it
        # paints the coldest colour on the heatmap and drags a chart axis down
        # to zero, on a run that was never measured.
        offenders = []
        for path in sorted(SRC.rglob("*.ts")) + sorted(SRC.rglob("*.tsx")):
            text = path.read_text(encoding="utf-8")
            for pattern in ("avg_qa_score ?? 0", "qaScore ?? 0", "avg_latency_ms ?? 0"):
                if pattern in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {pattern}")
        assert offenders == []
