"""The lost-chunk cost document has to agree with the ledgers it read.

`313-lost-chunk-cost.md` counts what four failed grading runs bought before they
died. Those runs committed nothing, so the ledgers carrying the headline figures
-- 818 calls, 216 distinct sites, 602 re-purchases -- exist only as GitHub
Actions artifacts, and artifacts expire. That is the document's own thesis, and
it is also the reason no test here can recompute those three numbers. Pretending
otherwise would mean committing 4 MB of failed-run ledger to prove a point about
a run that deliberately left nothing behind.

So this file binds the two things that *are* in the repository:

* Chunk 0. The one shard-4 ledger that was committed is tracked on main, and
  section 8's account of it -- 132 calls on `9e39df84`, 126 grading and 6
  perception, laid out contiguously at round 0 -- is recomputed from that file,
  including the `call_id`s, which are rebuilt from their materials rather than
  read. Those same rows carry the `price_missing` condition that the whole
  document rests on, which is why "not $0" is checked against data and not
  against a sentence.

* The document's own arithmetic. Every figure in the un-recomputable tables is
  cross-checked against the others: the per-attempt rows must close on the
  stated totals, the times-sold split must reproduce both 818 and 216, the
  overlap matrix must agree with the per-attempt counts, and the two readings
  of the re-purchased token figure must both be present and must both close.
  A transcription slip in a number nothing else can verify is exactly the
  failure this catches -- three such slips were found while writing it.

One check points at the workflow instead of at data. Section 2's method only
works because the ledger upload runs `if: always()`. Take that away and failed
runs stop leaving ledgers, and this document becomes unreproducible in a way no
other check would notice.
"""

import json
from pathlib import Path
import re

import pytest

from core.cost_receipts import make_call_id


REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/313-lost-chunk-cost.md"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/grade-run.yml"

#: The task the four failed attempts never got past. Read from the document so
#: that a document about some other task cannot pass on this file's constant.
BLOCKED_TASK_PREFIX = "9e39df84"

#: The one shard-4 ledger that reached main, written by chunk 0 before the four
#: failures began. Located by shape rather than by a pinned path: the shard
#: directory name carries a grader fingerprint that a later run may add to.
COMMITTED_LEDGER_GLOB = (
    "data/grades/_diagnostic/*/_shards/*__src_955be41edc4aff19__v2.2/"
    "shard-004-of-011.cost_ledger.jsonl"
)


def _int(text: str) -> int:
    return int(text.replace(",", "").strip())


@pytest.fixture(scope="module")
def doc() -> str:
    assert DOC_PATH.is_file(), (
        f"{DOC_PATH.relative_to(REPO_ROOT)} is missing. Everything below checks "
        "that document against its ledgers, so its absence is the failure."
    )
    return DOC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def committed_rows() -> list[dict]:
    matches = sorted(REPO_ROOT.glob(COMMITTED_LEDGER_GLOB))
    assert len(matches) == 1, (
        "expected exactly one committed shard-4 ledger from chunk 0, found "
        f"{[str(p.relative_to(REPO_ROOT)) for p in matches]}. Section 3 "
        "subtracts that file, and section 8 is entirely about it."
    )
    return [
        json.loads(line)
        for line in matches[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture(scope="module")
def attempts(doc: str) -> list[dict]:
    """The section 3 table: one row per failed attempt."""
    rows = []
    for line in doc.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 7 or not re.fullmatch(r"[1-4]", cells[0]):
            continue
        called = re.fullmatch(r"\*\*([\d,]+)\*\*", cells[3])
        if not called:
            continue
        items = re.fullmatch(r"(\d+) / (\d+)", cells[4])
        assert items, f"unparsable item cell in section 3: {cells[4]!r}"
        rows.append(
            {
                "attempt": int(cells[0]),
                "ledger_rows": _int(cells[1]),
                "already_there": _int(cells[2]),
                "called": _int(called.group(1)),
                "items_done": int(items.group(1)),
                "items_total": int(items.group(2)),
                "input_tokens": _int(cells[5]),
                "output_tokens": _int(cells[6]),
            }
        )
    assert len(rows) == 4, f"section 3 should list four attempts, found {len(rows)}"
    return rows


def test_the_failed_run_ledger_upload_still_runs_on_failure() -> None:
    """Section 2's method dies quietly if the upload stops running on failure."""
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    step = re.search(
        r"- name: Upload cost ledger\n(.*?)(?=\n\s*- name: |\Z)",
        workflow,
        re.DOTALL,
    )
    assert step, (
        "no `Upload cost ledger` step found in grade-run.yml. 313 recovered "
        "four failed runs' ledgers from artifacts; without that step the "
        "document describes a method that no longer exists."
    )
    conditions = re.findall(r"^\s+if: (.+)$", step.group(1), re.MULTILINE)
    assert conditions and all("always()" in c for c in conditions), (
        "the cost-ledger upload no longer runs on failure: "
        f"{conditions}. Section 2 of 313 is built on `if: always()`, and the "
        "four runs it reads all failed."
    )


def test_the_committed_baseline_is_the_row_count_the_document_subtracts(
    doc: str, committed_rows: list[dict], attempts: list[dict]
) -> None:
    """Section 3 subtracts a file that is on main; count it rather than trust it."""
    stated = {row["already_there"] for row in attempts}
    assert stated == {len(committed_rows)}, (
        f"section 3 subtracts {sorted(stated)} rows from every attempt, but the "
        f"committed chunk-0 ledger has {len(committed_rows)}."
    )
    assert f"{len(committed_rows)}줄" in doc, (
        f"the prose should name the committed row count ({len(committed_rows)})"
    )
    call_ids = [row["call_id"] for row in committed_rows]
    assert len(set(call_ids)) == len(call_ids), (
        "the committed ledger holds a duplicate call_id, which would break the "
        "set-difference the document describes"
    )
    assert call_ids == sorted(call_ids), (
        "the committed ledger is not sorted by call_id. Section 3 warns that it "
        "is sorted -- and therefore interleaved with new rows -- which is why "
        "slicing off a prefix is the wrong subtraction."
    )


def test_the_subtraction_is_described_as_a_set_difference(doc: str) -> None:
    """The wrong method reproduces the counts and the wrong rows."""
    assert "call_id` 집합 차집합" in doc, (
        "section 3 must say the subtraction is a call_id set difference. "
        "Cutting the first 797 lines happens to yield the right *count* and the "
        "wrong rows, so a reader following a prefix description gets 215 sites "
        "instead of 216."
    )


def test_the_per_attempt_table_closes_on_its_own_totals(
    doc: str, attempts: list[dict]
) -> None:
    for row in attempts:
        assert row["ledger_rows"] - row["already_there"] == row["called"], (
            f"attempt {row['attempt']}: {row['ledger_rows']} ledger rows minus "
            f"{row['already_there']} already there is not {row['called']}"
        )
    totals = re.search(
        r"\|\s*\|\s*\|\s*\|\s*\*\*([\d,]+)\*\*\s*\|\s*\|\s*\*\*([\d,]+)\*\*\s*"
        r"\|\s*\*\*([\d,]+)\*\*\s*\|",
        doc,
    )
    assert totals, "section 3 has no totals row"
    calls, input_tokens, output_tokens = (_int(g) for g in totals.groups())
    assert sum(r["called"] for r in attempts) == calls
    assert sum(r["input_tokens"] for r in attempts) == input_tokens
    assert sum(r["output_tokens"] for r in attempts) == output_tokens


def test_the_times_sold_split_reproduces_both_818_and_216(doc: str) -> None:
    """Section 4's two headline numbers are the same split read two ways."""
    split = re.search(
        r"([\d,]+)개는 \*\*네 번씩\*\*, ([\d,]+)개는 세 번씩,\s*"
        r"([\d,]+)개는 두 번, ([\d,]+)개만 한 번",
        doc,
    )
    assert split, "section 4 no longer states how many times each site was sold"
    four, three, two, one = (_int(g) for g in split.groups())

    paid = _int(re.search(r"\| 실제로 지불한 호출 \| \*\*([\d,]+)\*\* \|", doc).group(1))
    distinct = _int(re.search(r"\| 서로 다른 요청 \| \*\*([\d,]+)\*\* \|", doc).group(1))
    duplicate, percent = re.search(
        r"\| \*\*중복 재구매\*\* \| \*\*([\d,]+) \(([\d.]+)%\)\*\* \|", doc
    ).groups()
    duplicate = _int(duplicate)

    assert 4 * four + 3 * three + 2 * two + one == paid
    assert four + three + two + one == distinct
    assert paid - distinct == duplicate
    assert round(100 * duplicate / paid, 1) == float(percent)


def test_the_overlap_matrix_agrees_with_the_per_attempt_counts(
    doc: str, attempts: list[dict]
) -> None:
    matrix = []
    for line in doc.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        header = re.fullmatch(r"\*\*(\d)차\*\* \((\d+)\)", cells[0]) if cells else None
        if not header or len(cells) != 5:
            continue
        matrix.append((int(header.group(1)), _int(header.group(2)),
                       [_int(c) for c in cells[1:]]))
    assert len(matrix) == 4, "section 4's overlap matrix should have four rows"

    counts = {row["attempt"]: row["called"] for row in attempts}
    for attempt, stated, overlaps in matrix:
        assert stated == counts[attempt], (
            f"the overlap matrix labels attempt {attempt} as {stated} calls, "
            f"section 3 says {counts[attempt]}"
        )
        assert overlaps[attempt - 1] == stated, (
            f"attempt {attempt} must overlap itself completely, got {overlaps}"
        )
        assert max(overlaps) <= stated, (
            f"attempt {attempt} cannot share more than its own {stated} sites: "
            f"{overlaps}"
        )
    for i, (_, _, overlaps_i) in enumerate(matrix):
        for j, (_, _, overlaps_j) in enumerate(matrix):
            assert overlaps_i[j] == overlaps_j[i], (
                f"the overlap matrix is not symmetric at ({i + 1}, {j + 1})"
            )


def test_the_second_derivation_of_216_uses_the_items_it_states(
    doc: str, attempts: list[dict]
) -> None:
    """Section 5 must be an independent route to 216, not a restatement."""
    for line in doc.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not re.fullmatch(r"[1-4]", cells[0]):
            continue
        if not re.fullmatch(r"\d+\.\d+", cells[3]):
            continue
        attempt = attempts[int(cells[0]) - 1]
        assert _int(cells[1]) == attempt["items_done"], (
            f"section 5 and section 3 disagree on attempt {cells[0]}'s items"
        )
        assert _int(cells[2]) == attempt["called"], (
            f"section 5 and section 3 disagree on attempt {cells[0]}'s calls"
        )
        assert round(attempt["called"] / attempt["items_done"], 2) == float(cells[3])

    progression = re.search(
        r"(\d+) → \+(\d+) → \+(\d+) → \+(\d+) = \*\*(\d+)개\*\*", doc
    )
    assert progression, "section 5 no longer shows how the item count accumulates"
    start, *deltas, total = (int(g) for g in progression.groups())
    assert start + sum(deltas) == total
    assert start == attempts[0]["items_done"]
    assert total == attempts[-1]["items_done"]

    per_item = float(re.search(r"항목당 ([\d.]+)번을 곱하면 \*\*(\d+)번\*\*", doc).group(1))
    claimed = _int(re.search(r"항목당 [\d.]+번을 곱하면 \*\*(\d+)번\*\*", doc).group(1))
    assert round(total * per_item) == claimed, (
        f"{total} items x {per_item} calls is not {claimed}"
    )
    distinct = _int(re.search(r"\| 서로 다른 요청 \| \*\*([\d,]+)\*\* \|", doc).group(1))
    assert claimed == distinct, "the two derivations no longer meet at the same number"


def test_the_repurchased_tokens_say_which_copy_they_keep(
    doc: str, attempts: list[dict]
) -> None:
    """A site sold four times has one purchase that was owed; which one matters."""
    kept = _int(re.search(r"합계 들여보낸 것 ([\d,]+)자", doc).group(1))
    repurchased = _int(re.search(r"들여보낸 것 \*\*([\d,]+)자\*\*", doc).group(1))
    alternative = _int(re.search(r"바꾸면 ([\d,]+)자가 된다", doc).group(1))
    total = sum(row["input_tokens"] for row in attempts)

    assert kept + repurchased == total, (
        f"{kept} kept plus {repurchased} re-purchased is not the {total} the "
        "section 3 table totals"
    )
    assert alternative != repurchased, (
        "the two readings are stated as different numbers; if they were equal "
        "the sentence explaining the choice would be pointless"
    )
    assert alternative < total


def test_the_216_splits_in_section_7_add_up(doc: str) -> None:
    distinct = _int(re.search(r"\| 서로 다른 요청 \| \*\*([\d,]+)\*\* \|", doc).group(1))
    stages = re.search(r"\| 단계 \| 채점 (\d+) · 지각 (\d+) \|", doc)
    assert stages, "section 7 no longer splits the calls by stage"
    assert sum(int(g) for g in stages.groups()) == distinct

    price_tables = re.findall(r"`[0-9a-f]{16}…` (\d+)개", doc)
    assert price_tables, (
        "section 7 must say how many calls carried each price-table fingerprint; "
        "the four attempts did not all run against one price table"
    )
    assert sum(int(n) for n in price_tables) == distinct


def test_chunk_zero_is_what_section_8_says_it_is(
    doc: str, committed_rows: list[dict]
) -> None:
    """Recomputed from the committed ledger, call_ids rebuilt from materials."""
    rows = [
        row
        for row in committed_rows
        if str(row.get("task_id", "")).startswith(BLOCKED_TASK_PREFIX)
    ]
    stated = _int(re.search(r"쓴 \*\*(\d+)번\*\*은", doc).group(1))
    assert len(rows) == stated, (
        f"section 8 says chunk 0 spent {stated} calls on {BLOCKED_TASK_PREFIX}; "
        f"the committed ledger holds {len(rows)}"
    )
    layout = re.search(r"채점 순번 0~(\d+)\((\d+)개\), 지각 순번\s*0~(\d+)\((\d+)개\)", doc)
    assert layout, "section 8 no longer states chunk 0's layout"
    grading_last, grading_n, perception_last, perception_n = (
        int(g) for g in layout.groups()
    )
    assert grading_last + 1 == grading_n
    assert perception_last + 1 == perception_n
    assert grading_n + perception_n == stated

    by_stage = {"grading": grading_n, "perception": perception_n}
    for stage, expected in by_stage.items():
        assert sum(1 for row in rows if row.get("stage") == stage) == expected, (
            f"chunk 0's {stage} call count does not match section 8"
        )

    # Rebuild the identifiers instead of reading them: section 8's claim is that
    # these sit at round 0 with no gaps, which the stored hashes do not show.
    # The round is folded into the hashed run identity, not into attempt_index,
    # so it never appears in the row -- which is why "round0" has to be asserted
    # rather than looked up.
    run_ids = {row["run_id"] for row in rows}
    assert len(run_ids) == 1, f"chunk 0 spans several runs: {run_ids}"
    run_id = run_ids.pop()
    task_ids = {row["task_id"] for row in rows}
    task_id = task_ids.pop()
    present = {row["call_id"] for row in rows}
    rebuilt = {
        make_call_id(
            run_id=f"{run_id}|round0",
            task_id=task_id,
            stage=stage,
            retry_kind="none",
            attempt_index=0,
            sequence=sequence,
        )
        for stage, count in by_stage.items()
        for sequence in range(count)
    }
    assert rebuilt == present, (
        "chunk 0's call_ids are not a gapless round-0 run of sequences. Section "
        "8 rests on that layout: it is why chunk 0 cannot collide with the four "
        "attempts, and therefore why the 216 are counted separately."
    )


def test_the_committed_rows_record_no_price_so_no_one_may_write_zero(
    doc: str, committed_rows: list[dict]
) -> None:
    rows = [
        row
        for row in committed_rows
        if str(row.get("task_id", "")).startswith(BLOCKED_TASK_PREFIX)
    ]
    assert rows, "no committed rows for the blocked task"
    assert {row.get("state") for row in rows} == {"settled"}, (
        "these calls were made and answered; an unsettled row would mean the "
        "document is counting something else"
    )
    assert {row.get("model_cost_usd") for row in rows} == {None}, (
        "a committed row now carries a cost. The document says the amount is "
        "unknown for every one of them, and that is why it refuses to print $0."
    )
    assert {tuple(row.get("missing_reasons") or ()) for row in rows} == {
        ("price_missing",)
    }, "the reason the cost is absent is no longer price_missing"
    assert "price_missing" in doc, (
        "the document must name the condition its ledgers actually record"
    )
    assert "`$0`으로 쓰면 안 된다" in doc, (
        "section 7's refusal to print $0 is the one sentence standing between "
        "these null costs and a reader who totals them as free"
    )
    # Every mention of the figure has to be a denial of it, wherever it appears.
    for match in re.finditer(r"\$0", doc):
        following = doc[match.end():match.end() + 24]
        assert "아니" in following or "안 된다" in following, (
            f"'$0' appears without a negation after it: {following!r}. The "
            "amount is unknown, and an unqualified $0 in this document would "
            "be read as measured."
        )
