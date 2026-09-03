"""The PR3 report must count the table it points at, not restate a number.

Closing PR3 task 302 moved one row in ``000-OVERVIEW.md`` from open to done.
Four other places on ``main`` kept asserting the opposite — the report headline,
its exit-condition tally, its 302 section, and the CHANGELOG entry — because
each of them had the count *written out* rather than derived. That is the same
failure as a hash sealed in one document and moved in another: a status is
claimed in more places than the change touched.

So these tests do not check that the documents say "18". They read the OVERVIEW
tables, count, and require every prose claim to agree with what was counted. A
row flipped back to ⚠️ makes the prose wrong and the suite red, in either
direction.

What is *not* here: the recomputation of the cost figures themselves. That
lives in ``test_the_cost_budget_gate_measures_the_pipeline_that_runs.py``, which
derives them from the committed grade payloads and cost ledgers. This file only
requires that every document quoting those figures quotes the same ones.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS = REPO_ROOT / "tasks/rebuilding_grading_task"
OVERVIEW = TASKS / "000-OVERVIEW.md"
REPORT = TASKS / "PR3_REPORT.md"
COST_BUDGET = TASKS / "PR3_COST_BUDGET.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

#: Status marks the OVERVIEW task tables are allowed to carry. A row that
#: starts with anything else is unreadable to every count below, so it fails
#: loudly instead of being silently counted as not-done.
DONE = "✅"
KNOWN_MARKS = (DONE, "⚠️", "☐")

#: The bounds PR3 task 302 answered with. These are pinned to the committed
#: measurement by ``test_the_cost_budget_gate_measures_the_pipeline_that_runs``,
#: which recomputes them from the grade payloads; here they only anchor the
#: parse. What this file enforces is that the report's prose, the report's own
#: table, the OVERVIEW row, the cost report and the CHANGELOG all quote the
#: *same* range — presence of a figure somewhere in a long document proves
#: nothing.
COST_LOW = "$411.80"
COST_HIGH = "$980.84"

#: Wording that only made sense while 302 was open. Left as explicit pins: the
#: derived tests below catch a *count* going stale, these catch a sentence that
#: was true once being carried forward unchanged.
RETIRED_CLAIMS = (
    "남은 하나(302)",
    "이 보고서가 닫지 못하는 유일한 항목",
    "1개 미해결(302)",
    "다섯 중 넷이 충족됐고",
    "One item is deliberately left open",
    "so it stays with the owner rather than being decided here",
)

_ROW = re.compile(r"^\|\s*(\d{3})\s*\|(.+?)\|(.+?)\|\s*$")
_SECTION = re.compile(r"^#{2,3}\s")
_MD_LINK = re.compile(r"\[[^\]]*\]\((\.\/[^)]+\.md)\)")
_USD = re.compile(r"\$[\d,]+\.\d\d")
#: A run-cost row in the 302 table: ``| label | tasks | low | high | per task |``
_COST_ROW = re.compile(
    r"^\|[^|]+\|\s*\d+\s*\|\s*\**(\$[\d,]+\.\d\d)\**\s*\|\s*\**(\$[\d,]+\.\d\d)\**\s*\|",
    re.M,
)
#: Any ``$a ~ $b`` in the dash/tilde spellings these documents use.
_ANY_RANGE = re.compile(r"(\$[\d,]+\.?\d*)\s*[~–—-]\s*(\$[\d,]+\.?\d*)")

#: Above this a quoted dollar range is a per-*run* figure, below it a per-task
#: one. The two do not come close to overlapping in these documents — per-task
#: tops out at $58.24 and per-run bottoms out at $411.80 — so the split needs
#: no list of exceptions to maintain.
RUN_LEVEL_USD = Decimal(100)


def _money(text: str) -> Decimal:
    return Decimal(text.lstrip("$").replace(",", ""))


def _read(path: Path) -> str:
    assert path.is_file(), f"missing document: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def _tasks_by_pr() -> dict[str, list[tuple[str, str, str]]]:
    """``{"PR1": [(id, task cell, status cell), ...], ...}`` from the OVERVIEW.

    Sections are delimited by their own headings rather than by a stop-marker
    string, so adding prose between the tables cannot quietly drop a row.
    """
    sections: dict[str, list[tuple[str, str, str]]] = {}
    current: str | None = None
    for line in _read(OVERVIEW).splitlines():
        heading = re.match(r"^###\s+(PR\d)\s+—", line)
        if heading:
            current = heading.group(1)
            sections.setdefault(current, [])
            continue
        if current and _SECTION.match(line) and not heading:
            current = None
            continue
        if not current:
            continue
        row = _ROW.match(line)
        if row:
            sections[current].append(
                (row.group(1), row.group(2).strip(), row.group(3).strip())
            )
    return sections


def _all_rows() -> list[tuple[str, str, str]]:
    return [row for rows in _tasks_by_pr().values() for row in rows]


def _exit_conditions() -> list[tuple[int, str]]:
    """``[(number, verdict), ...]`` from the exit-condition headings."""
    text = _read(REPORT)
    start = text.index("## PR3 종료 조건 대조")
    tail = text[start + 1 :]
    end = tail.find("\n## ")
    body = tail if end == -1 else tail[:end]
    return [
        (int(number), verdict)
        for number, verdict in re.findall(
            r"^###\s+(\d)\..*?—\s*\*\*(.+?)\*\*\s*$", body, re.M
        )
    ]


def _exit_condition_summary() -> str:
    text = _read(REPORT)
    start = text.index("## PR3 종료 조건 대조")
    return text[start : text.index("### 1.", start)]


def _report_302_section() -> str:
    text = _read(REPORT)
    start = text.index("### 302 —")
    return text[start : text.index("\n### ", start + 1)]


def _cost_bounds() -> tuple[str, str]:
    """``(low, high)`` — the envelope of the run-cost table in the 302 section."""
    rows = _COST_ROW.findall(_report_302_section())
    assert len(rows) >= 3, f"the 302 run-cost table parsed to {len(rows)} rows"
    return (
        min((low for low, _ in rows), key=_money),
        max((high for _, high in rows), key=_money),
    )


# --------------------------------------------------------------------------
# the tables parse at all
# --------------------------------------------------------------------------


def test_the_overview_still_has_the_three_task_tables():
    sections = _tasks_by_pr()
    assert sorted(sections) == ["PR1", "PR2", "PR3"]
    for name, rows in sections.items():
        assert rows, f"{name} table parsed to zero rows — the parser or the table moved"


def test_every_task_row_carries_a_status_mark_the_count_can_read():
    unreadable = [
        (task_id, status)
        for task_id, _, status in _all_rows()
        if not status.startswith(KNOWN_MARKS)
    ]
    assert not unreadable, f"rows with an uncountable status: {unreadable}"


def test_task_ids_are_unique_and_grouped_by_their_own_hundred():
    sections = _tasks_by_pr()
    ids = [task_id for task_id, _, _ in _all_rows()]
    assert len(ids) == len(set(ids)), f"duplicate task ids: {ids}"
    for index, name in enumerate(("PR1", "PR2", "PR3"), start=1):
        stray = [t for t, _, _ in sections[name] if not t.startswith(str(index))]
        assert not stray, f"{name} table holds ids from another PR: {stray}"


# --------------------------------------------------------------------------
# the report's numbers are the table's numbers
# --------------------------------------------------------------------------


def test_the_report_states_the_total_the_table_actually_holds():
    match = re.search(r"=\s*\*\*(\d+)개\*\*다", _read(REPORT))
    assert match, "the report no longer states a task total in a countable form"
    assert int(match.group(1)) == len(_all_rows())


def test_the_report_states_the_per_pr_split_the_tables_actually_hold():
    match = re.search(
        r"PR1\s*(\d+)개\([^)]*\)\s*\+\s*PR2\s*(\d+)개\([^)]*\)\s*\+\s*PR3\s*(\d+)개\([^)]*\)",
        _read(REPORT),
    )
    assert match, "the report no longer states the per-PR split in a countable form"
    sections = _tasks_by_pr()
    stated = tuple(int(group) for group in match.groups())
    counted = tuple(len(sections[name]) for name in ("PR1", "PR2", "PR3"))
    assert stated == counted


def test_the_report_states_the_done_count_the_table_actually_holds():
    match = re.search(r"지금 상태는 \*\*(\d+)개 중 (\d+)개 ✅\*\*", _read(REPORT))
    assert match, "the report no longer states its status tally in a countable form"
    rows = _all_rows()
    stated_total, stated_done = (int(group) for group in match.groups())
    assert stated_total == len(rows)
    assert stated_done == sum(1 for _, _, status in rows if status.startswith(DONE))


def test_the_report_names_the_pr3_tasks_the_pr3_table_actually_holds():
    pr3 = [task_id for task_id, _, _ in _tasks_by_pr()["PR3"]]
    overview = _read(OVERVIEW)
    match = re.search(r"PR3의 (\S+) 항목\(([^)]*)\)은 모두 닫혔다", overview)
    assert match, "the OVERVIEW no longer states which PR3 tasks are closed"
    named = re.findall(r"\d{3}", match.group(2))
    assert named == pr3, f"prose names {named}, table holds {pr3}"


# --------------------------------------------------------------------------
# the exit-condition tally agrees with its own headings
# --------------------------------------------------------------------------


def test_the_exit_conditions_are_five_and_numbered_in_order():
    conditions = _exit_conditions()
    assert [number for number, _ in conditions] == [1, 2, 3, 4, 5]


def test_the_exit_condition_summary_agrees_with_the_headings():
    unmet = [number for number, verdict in _exit_conditions() if "미충족" in verdict]
    summary = _exit_condition_summary()
    if unmet:
        assert "충족되지 않" in summary, (
            f"conditions {unmet} are marked 미충족 but the summary does not say so"
        )
    else:
        assert "모두 충족" in summary, (
            "every condition heading says 충족 but the summary does not say so"
        )
        assert "충족되지 않았다" not in summary


def test_condition_one_agrees_with_whether_the_table_is_finished():
    verdicts = dict(_exit_conditions())
    rows = _all_rows()
    finished = all(status.startswith(DONE) for _, _, status in rows)
    # Condition 1 *is* "every task row is done", so it cannot disagree with the
    # table it is about.
    assert ("미충족" in verdicts[1]) is not finished


# --------------------------------------------------------------------------
# 302 specifically
# --------------------------------------------------------------------------


def test_the_302_row_is_done_and_points_at_the_report_that_closed_it():
    row = {task_id: (task, status) for task_id, task, status in _all_rows()}["302"]
    task_cell, status = row
    assert status.startswith(DONE), f"302 is marked {status[:8]!r}"
    assert "PR3_COST_BUDGET.md" in status, (
        "the 302 row does not link the report that answers it"
    )
    assert "302-cost-budget-recheck.md" in task_cell


@pytest.mark.parametrize(
    "path", [OVERVIEW, REPORT, COST_BUDGET, CHANGELOG], ids=lambda p: p.name
)
def test_every_document_quotes_the_same_single_per_run_range(path: Path):
    """One per-run range, and it is the one the 302 table adds up to.

    Set equality rather than a substring search on purpose. A long document
    containing the right figure *somewhere* proves nothing — the drift this
    guards against is a second, slightly different copy of the same range
    living a few paragraphs away from the first.
    """
    low, high = _cost_bounds()
    quoted = {
        (start, end)
        for start, end in _ANY_RANGE.findall(_read(path))
        if _money(start) >= RUN_LEVEL_USD
    }
    assert quoted == {(low, high)}, (
        f"{path.name} quotes per-run ranges {sorted(quoted) or '[none]'}; "
        f"the 302 table adds up to {low}–{high}"
    )


def test_the_302_range_is_the_envelope_of_the_302_table():
    """The prose bound must be the min/max of the runs the table lists.

    Nothing here decides what the numbers *should* be — that is recomputed from
    the committed payloads in the cost-budget test. This only refuses a report
    whose sentence and whose table disagree, which is how a figure gets revised
    in one place and left in another.
    """
    low, high = _cost_bounds()
    assert (low, high) == (COST_LOW, COST_HIGH), (
        "the 302 table's envelope moved; the measurement test is the authority "
        "on whether that is correct, and this pin has to move with it"
    )


def test_the_report_302_section_records_an_answer_not_a_deferral():
    body = _report_302_section()
    for figure in ("8.2", "19.6"):
        assert figure in body, f"the 302 section does not state {figure}"
    assert "PR3_COST_BUDGET.md" in body
    assert "`< $50`" in body, (
        "the 302 section no longer states the gate the measurement was taken against"
    )


def test_no_document_still_carries_a_claim_that_302_is_open():
    if not all(status.startswith(DONE) for _, _, status in _all_rows()):
        pytest.skip("a task row is open; the retired wording may be live again")
    for path in (REPORT, OVERVIEW, CHANGELOG):
        text = _read(path)
        still_there = [claim for claim in RETIRED_CLAIMS if claim in text]
        assert not still_there, f"{path.name} still says: {still_there}"


def test_the_superseded_smoke_findings_say_so_before_their_abc_question():
    text = _read(TASKS / "PR3_SMOKE_FINDINGS.md")
    banner_at = text.index("PR3_COST_BUDGET.md")
    question_at = text.index("A / B / C")
    assert banner_at < question_at, (
        "the A/B/C decision request is not preceded by the notice that it is closed"
    )


# --------------------------------------------------------------------------
# the links the counts depend on resolve
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", [OVERVIEW, REPORT], ids=lambda p: p.name)
def test_relative_document_links_resolve(path: Path):
    missing = sorted(
        {
            target
            for target in _MD_LINK.findall(_read(path))
            if not (path.parent / target).resolve().is_file()
        }
    )
    assert not missing, f"{path.name} links documents that do not exist: {missing}"


def test_the_follow_up_list_is_contiguous_and_registers_the_302_side_finding():
    text = _read(REPORT)
    body = text[text.index("## 후속 항목") :]
    numbers = [int(n) for n in re.findall(r"^(\d+)\.\s+\*\*", body, re.M)]
    assert numbers == list(range(1, len(numbers) + 1)), f"follow-up list: {numbers}"
    assert "319-the-published-index-still-says-zero.md" in body
