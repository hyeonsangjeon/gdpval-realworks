"""A file nobody asked for is not a file that failed.

``step5_validate`` counts the tasks a run owed a deliverable file for, writes the
count to ``validate_stats.json``, and ``step6_report`` divides by it::

    round(succeeded / total * 100, 1) if total else 0.0

``if total else 0.0`` answers "how many of nothing" with the worst value on the
scale — the same ``0.0%`` a run earns by failing every file it was asked for.
Four full 220-task runs published exactly that, and their committed reports still
carry the row::

    | Tasks requiring files  | 0        |
    | Successfully generated | 0 (0.0%) |

``exp013``, ``exp014``, ``exp025``, ``exp026``. Not one of them generated a file
badly; none was asked for a file at all.

The gate said the same thing from the other side. With nothing in the counts,
``needs_files_missing`` was empty, so::

    All 0 file-required tasks have deliverable files ✓

printed the tick a run earns by generating every file it owed — a verdict on
something that was never looked at.

Two arrangements reach ``total == 0`` and they are not the same. A subset run
that selected only text-only tasks genuinely owed no file: nothing was measured,
and saying so is the whole of it. A **full** run is different. The manifest is
built from the source parquet under a digest check and states its own count in
``_summary.needs_files``; ``core.repo_bootstrapper.validate_needs_files_manifest``
requires that int to equal the number of file-required entries in the tasks map
(``:769-777``). A full run whose count came out zero against a summary declaring
185 read a manifest whose two halves disagree — file generation went unchecked,
and it fails rather than passing with a checkmark.

Pinned here:

* the renderer refuses a rate without a denominator, in both artefacts;
* a genuine ``0.0%`` over a real denominator still prints, and so does ``100.0%``;
* the tick is printed only where files were actually looked at;
* a full run that counted none against a manifest that declares some fails;
* the markdown and the HTML answer the same payload the same way;
* the four frozen reports are full runs with no denominator, and today's
  renderer no longer turns their payload into a rate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

BATCH_RUNNER = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER))

import step5_validate as step5  # noqa: E402
import step6_report  # noqa: E402
from step6_report import NO_FILE_TASKS_IN_SCOPE, _file_generation_generated  # noqa: E402

_FULL_ROW_COUNT = 220
_TICK = "file-required tasks have deliverable files ✓"
_NOT_MEASURED = "No file-required tasks in scope — file generation was not measured"

#: What the four runs published, kept as a literal so the two glyphs this change
#: distinguishes sit side by side in one file.
_SHIPPED_ZERO = "0 (0.0%)"

#: The runs whose committed reports carry it. Every one is a full 220-task run.
_FROZEN = (
    "exp013_GPT54_reasoning_high",
    "exp014_GPT54_reasoning_medium",
    "exp025_GPT54_high_postfix",
    "exp026_sandbox_skills_multimodal",
)


# ── The renderer ──────────────────────────────────────────────────────────


class TestTheCell:
    def test_no_denominator_is_not_a_rate(self):
        # THE DEFECT, in one assertion.
        assert _file_generation_generated(0, 0) == NO_FILE_TASKS_IN_SCOPE
        assert _file_generation_generated(0, 0) != _SHIPPED_ZERO
        assert "%" not in _file_generation_generated(0, 0)

    def test_the_sentinel_says_which_of_the_two_it_is(self):
        # A bare "n/a" is readable as either "not applicable" or "no record".
        # It has to name the one it means.
        assert NO_FILE_TASKS_IN_SCOPE.startswith("n/a")
        assert "no task in this run required a file" in NO_FILE_TASKS_IN_SCOPE

    def test_a_real_zero_over_a_real_denominator_still_prints(self):
        # The negative control, and the reason this could not be "hide every
        # zero". A run asked for 185 files that produced none has failed exactly
        # as badly as 0.0% suggests, and must keep saying so.
        assert _file_generation_generated(0, 185) == _SHIPPED_ZERO

    @pytest.mark.parametrize(
        ("succeeded", "total", "expected"),
        [
            (4, 4, "4 (100.0%)"),
            (177, 185, "177 (95.7%)"),
            (1, 3, "1 (33.3%)"),
            (185, 185, "185 (100.0%)"),
        ],
    )
    def test_a_measured_rate_keeps_its_value(self, succeeded, total, expected):
        assert _file_generation_generated(succeeded, total) == expected


# ── Driving the real report builders ──────────────────────────────────────


def _report_data(file_generation: dict | None) -> dict:
    """A report_data dict with ``file_generation`` set the way step6 sets it.

    ``generate_report`` reads ``validate_stats.json`` and falls back to an
    all-null block when it cannot (``step6_report.py:1679-1691``); ``None`` here
    stands for that fallback, which is what ``exp026c`` published.
    """
    data = {
        "experiment_id": "exp999_file_generation",
        "experiment_name": "file generation",
        "condition_name": "condition_a",
        "model": "gpt-5.4",
        "execution_mode": "subprocess",
        "started_at": "2026-09-05T00:00:00Z",
        "duration": "1m",
        "results": [
            {"task_id": "t1", "status": "success", "sector": "Finance", "qa_score": 8.0},
        ],
    }
    rd = step6_report._build_report_data(
        data,
        {
            "overview": "",
            "quality_analysis": "",
            "failure_patterns": "",
            "recommendations": "",
        },
        step6_report._compute_summary(data),
        step6_report._compute_sector_breakdown(data),
        task_results=[],
        error_tasks=[],
    )
    rd["file_generation"] = file_generation or {
        "needs_files_total": None,
        "files_succeeded": None,
        "files_failed": None,
        "files_absent": None,
        "dummy_files_created": None,
        "dummy_task_ids": [],
    }
    return rd


def _stats(total, succeeded, failed, absent=0) -> dict:
    return {
        "needs_files_total": total,
        "files_succeeded": succeeded,
        "files_failed": failed,
        "files_absent": absent,
        "absent_task_ids": [],
        "dummy_files_created": 0,
        "dummy_task_ids": [],
        "policy_caveat": None,
    }


def _file_generation_rows(markdown: str) -> dict[str, str]:
    """The ``| Metric | Value |`` rows of the File Generation table."""
    rows: dict[str, str] = {}
    inside = False
    for line in markdown.splitlines():
        if line.startswith("## File Generation"):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside and line.startswith("| ") and "|--" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 2 and cells[0] != "Metric":
                rows[cells[0]] = cells[1]
    return rows


def _file_gen_card(html: str) -> str | None:
    """The File Gen Rate card, or None when the HTML carries no such card.

    Sliced rather than parsed: the cards are emitted as one flat run of
    ``<div class="card">`` siblings, so the next ``label`` opens the next card.
    """
    at = html.find(">File Gen Rate<")
    if at < 0:
        return None
    rest = html[at:]
    nxt = rest.find('<div class="label">', 1)
    return rest if nxt < 0 else rest[:nxt]


# ── The markdown ──────────────────────────────────────────────────────────


class TestTheMarkdownSection:
    def test_no_denominator_prints_the_sentinel_not_a_rate(self):
        rows = _file_generation_rows(
            step6_report._build_markdown(_report_data(_stats(0, 0, 0)))
        )
        assert rows["Tasks requiring files"] == "0"
        assert rows["Successfully generated"] == NO_FILE_TASKS_IN_SCOPE
        assert rows["Successfully generated"] != _SHIPPED_ZERO

    def test_a_real_zero_is_unchanged(self):
        rows = _file_generation_rows(
            step6_report._build_markdown(_report_data(_stats(185, 0, 185)))
        )
        assert rows["Tasks requiring files"] == "185"
        assert rows["Successfully generated"] == _SHIPPED_ZERO
        assert rows["Failed (empty outputs preserved)"] == "185"

    def test_a_full_house_is_unchanged(self):
        rows = _file_generation_rows(
            step6_report._build_markdown(_report_data(_stats(185, 185, 0)))
        )
        assert rows["Successfully generated"] == "185 (100.0%)"

    def test_the_absent_note_quotes_a_measured_percentage(self):
        # Reachable only with a denominator — a task can be absent only if the
        # manifest said it owed a file — so this sentence never quotes a rate
        # that was not measured.
        markdown = step6_report._build_markdown(_report_data(_stats(185, 177, 6, absent=2)))
        rows = _file_generation_rows(markdown)
        assert rows["Absent from submission (never checked)"] == "2"
        assert "The 95.7% above is out of a denominator that includes them." in markdown

    def test_no_record_prints_no_section_at_all(self):
        # ``exp026c``: step5 wrote no stats, so there is nothing to report and
        # the section is omitted rather than filled with zeros.
        markdown = step6_report._build_markdown(_report_data(None))
        assert "## File Generation" not in markdown
        assert _file_generation_rows(markdown) == {}


# ── The HTML ──────────────────────────────────────────────────────────────


class TestTheHtmlCard:
    def test_no_denominator_gets_a_card_that_says_so(self):
        # The two artefacts used to disagree about this payload: the markdown
        # printed 0 (0.0%) and the HTML printed nothing. A missing card is not
        # readable as "there was no rate".
        card = _file_gen_card(step6_report._build_html(_report_data(_stats(0, 0, 0))))
        assert card is not None, "the zero-denominator run lost its card again"
        assert ">n/a<" in card
        assert "no task in this run required a file" in card
        assert "%" not in card

    def test_a_real_zero_still_shows_its_rate(self):
        card = _file_gen_card(step6_report._build_html(_report_data(_stats(185, 0, 185))))
        assert ">0.0%<" in card
        assert "0 / 185 tasks" in card

    def test_a_full_house_still_shows_its_rate(self):
        card = _file_gen_card(step6_report._build_html(_report_data(_stats(4, 4, 0))))
        assert ">100.0%<" in card
        assert "4 / 4 tasks" in card

    def test_no_record_gets_no_card(self):
        # And the markdown omits the section for the same payload, so the two
        # artefacts stay in step.
        assert _file_gen_card(step6_report._build_html(_report_data(None))) is None

    @pytest.mark.parametrize(
        "stats",
        [_stats(0, 0, 0), _stats(185, 0, 185), _stats(4, 4, 0), None],
        ids=["no-denominator", "real-zero", "full-house", "no-record"],
    )
    def test_the_two_artefacts_answer_the_same_payload_the_same_way(self, stats):
        rd = _report_data(stats)
        rows = _file_generation_rows(step6_report._build_markdown(rd))
        card = _file_gen_card(step6_report._build_html(rd))

        if stats is None:
            assert rows == {} and card is None
            return
        # A rate on one artefact means a rate on the other.
        assert ("%" in rows["Successfully generated"]) == ("%" in card)


# ── The gate ──────────────────────────────────────────────────────────────


def _canonical_ids() -> list[str]:
    return [f"task-{index:03d}" for index in range(_FULL_ROW_COUNT)]


def _write_parquet(upload: Path, task_ids: list[str], with_files: set[str]) -> None:
    data_dir = upload / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (upload / "deliverable_files").mkdir(exist_ok=True)

    files = []
    for task_id in task_ids:
        if task_id not in with_files:
            files.append([])
            continue
        relative = f"deliverable_files/{task_id}.docx"
        (upload / relative).write_bytes(b"deliverable")
        files.append([relative])

    empty = [[] for _ in task_ids]
    pd.DataFrame({
        "task_id": task_ids,
        "sector": ["Information"] * len(task_ids),
        "occupation": ["Analyst"] * len(task_ids),
        "prompt": ["Write something"] * len(task_ids),
        "reference_files": empty,
        "reference_file_urls": [[] for _ in task_ids],
        "reference_file_hf_uris": [[] for _ in task_ids],
        "deliverable_text": ["done"] * len(task_ids),
        "deliverable_files": files,
        "deliverable_file_urls": [[] for _ in task_ids],
        "deliverable_file_hf_uris": [[] for _ in task_ids],
    }).to_parquet(data_dir / "train-00000-of-00001.parquet", index=False)


def _prepare(
    tmp_path: Path,
    *,
    row_ids: list[str],
    manifest_needs: dict[str, bool],
    with_files: set[str],
    scope: dict,
    summary: dict | None = None,
) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    upload = workspace / "upload"
    workspace.mkdir(parents=True, exist_ok=True)
    _write_parquet(upload, row_ids, with_files)
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps({"task_scope": scope}), encoding="utf-8"
    )
    (workspace / "step0_needs_files_manifest.json").write_text(
        json.dumps({
            "tasks": {
                task_id: {"needs_files": needed}
                for task_id, needed in manifest_needs.items()
            },
            "_summary": {"active_policy": "deliverable_only", **(summary or {})},
        }),
        encoding="utf-8",
    )
    return workspace, upload


def _run(monkeypatch, workspace: Path, upload: Path) -> tuple[bool, dict]:
    monkeypatch.setattr(step5, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step5, "UPLOAD_DIR", upload)
    passed = step5.validate(data_dir=str(upload))
    stats = json.loads((workspace / "validate_stats.json").read_text(encoding="utf-8"))
    return passed, stats


class TestTheGate:
    def test_a_subset_that_owed_no_file_says_nothing_was_measured(
        self, tmp_path, monkeypatch, capsys
    ):
        """A run that selected only text-only tasks genuinely owed no file."""
        passed, stats = _run(monkeypatch, *_prepare(
            tmp_path,
            row_ids=["task-000", "task-002"],
            manifest_needs={"task-000": False, "task-001": True, "task-002": False},
            with_files=set(),
            scope={
                "mode": "explicit_ids",
                "expected_count": 2,
                "task_ids": ["task-000", "task-002"],
            },
            summary={"needs_files": 1},
        ))
        out = capsys.readouterr().out

        assert passed is True
        assert stats["needs_files_total"] == 0
        assert _NOT_MEASURED in out
        assert "not a 0% generation rate" in out
        # The claim the old code made about this run.
        assert _TICK not in out
        assert "All 0 " not in out

    def test_a_full_run_that_counted_none_against_a_manifest_that_declares_some_fails(
        self, tmp_path, monkeypatch, capsys
    ):
        """The fail-closed half.

        ``validate_needs_files_manifest`` requires ``_summary.needs_files`` to
        equal the file-required entries in the tasks map, so these two halves
        disagreeing means the file this run read is not one that passed
        validation. Nothing downstream can tell that from a zero.
        """
        passed, stats = _run(monkeypatch, *_prepare(
            tmp_path,
            row_ids=_canonical_ids(),
            manifest_needs={task_id: False for task_id in _canonical_ids()},
            with_files=set(),
            scope={"mode": "full", "expected_count": _FULL_ROW_COUNT},
            summary={"needs_files": 185},
        ))
        out = capsys.readouterr().out

        assert passed is False
        assert "Validation FAILED" in out
        assert "No file-required tasks were counted" in out
        assert "_summary declares 185" in out
        assert "file generation went unchecked" in out
        assert stats["needs_files_total"] == 0
        # Not both at once: the run is told one thing about itself.
        assert _NOT_MEASURED not in out
        assert _TICK not in out

    def test_a_full_run_whose_manifest_declares_none_is_only_unmeasured(
        self, tmp_path, monkeypatch, capsys
    ):
        """The four frozen runs' shape: summary and tasks map agree on zero.

        Nothing is wrong with the manifest, so nothing fails — but nothing was
        measured either, and the report may not claim a rate.
        """
        passed, stats = _run(monkeypatch, *_prepare(
            tmp_path,
            row_ids=_canonical_ids(),
            manifest_needs={task_id: False for task_id in _canonical_ids()},
            with_files=set(),
            scope={"mode": "full", "expected_count": _FULL_ROW_COUNT},
            summary={"needs_files": 0},
        ))
        out = capsys.readouterr().out

        assert passed is True
        assert stats["needs_files_total"] == 0
        assert _NOT_MEASURED in out
        assert _TICK not in out

    def test_a_run_that_looked_at_its_files_keeps_its_tick(
        self, tmp_path, monkeypatch, capsys
    ):
        """새로운 기준이 기존 실험에 영향을 미치면 안 된다 — the negative control."""
        passed, stats = _run(monkeypatch, *_prepare(
            tmp_path,
            row_ids=_canonical_ids(),
            manifest_needs={"task-000": True, "task-001": True, "task-002": False},
            with_files={"task-000", "task-001"},
            scope={"mode": "full", "expected_count": _FULL_ROW_COUNT},
            summary={"needs_files": 2},
        ))
        out = capsys.readouterr().out

        assert passed is True
        assert "Validation PASSED" in out
        assert f"All 2 {_TICK}" in out
        assert _NOT_MEASURED not in out
        assert (stats["needs_files_total"], stats["files_succeeded"]) == (2, 2)

    def test_a_run_with_a_failure_is_unchanged(self, tmp_path, monkeypatch, capsys):
        passed, stats = _run(monkeypatch, *_prepare(
            tmp_path,
            row_ids=_canonical_ids(),
            manifest_needs={"task-000": True, "task-001": True},
            with_files={"task-000"},
            scope={"mode": "full", "expected_count": _FULL_ROW_COUNT},
            summary={"needs_files": 2},
        ))
        out = capsys.readouterr().out

        assert passed is True
        assert "1 file-required tasks had no files" in out
        assert _TICK not in out
        assert _NOT_MEASURED not in out
        assert (stats["needs_files_total"], stats["files_failed"]) == (2, 1)


# ── The frozen corpus ─────────────────────────────────────────────────────


class TestTheFourRuns:
    """The reports that shipped the defect, read as data.

    All four are full 220-task runs in which no task required a file. Each
    published ``0 (0.0%)`` — a rate divided out of a zero denominator — and each
    has had that one cell corrected in place to what the fixed renderer emits,
    with a note recording the change. Nothing else in them was touched: the runs
    were not re-executed and the narrative was not regenerated.
    """

    @pytest.mark.parametrize("run", _FROZEN)
    def test_each_is_a_full_run_with_no_denominator(self, run):
        report = BATCH_RUNNER / "results" / run / "report" / "report.md"
        assert report.exists(), f"{run} lost its report"
        markdown = report.read_text(encoding="utf-8")

        total = re.search(r"\| Total Tasks \| (\d+) \|", markdown)
        assert total and total.group(1) == "220", f"{run} is not a full run"

        rows = _file_generation_rows(markdown)
        assert rows["Tasks requiring files"] == "0"
        assert rows["Successfully generated"] == NO_FILE_TASKS_IN_SCOPE, (
            f"{run} publishes a file generation rate for a run in which no task "
            f"required a file: {rows['Successfully generated']!r}"
        )

    @pytest.mark.parametrize("run", _FROZEN)
    def test_none_of_them_still_carries_the_row_that_shipped(self, run):
        markdown = (
            BATCH_RUNNER / "results" / run / "report" / "report.md"
        ).read_text(encoding="utf-8")

        shipped_row = f"| Successfully generated | {_SHIPPED_ZERO} |"
        assert shipped_row not in markdown, f"{run} still publishes {shipped_row}"

        # A correction that hides what it corrected is not a correction: the
        # note stays, and it quotes the value the run actually published.
        assert "**Corrected " in markdown, f"{run} was changed without a note"
        assert f"`{_SHIPPED_ZERO}`" in markdown, (
            f"{run} no longer records what it used to say"
        )

    def test_todays_renderer_gives_their_payload_no_rate(self):
        # The payload all four carry, put through the code that replaced the
        # rule which turned it into 0.0%.
        assert _file_generation_generated(0, 0) == NO_FILE_TASKS_IN_SCOPE
        assert _file_generation_generated(0, 0) != _SHIPPED_ZERO
