"""A round that solved a task twice still covers it once, and still paid twice.

exp035 grew two lineages over one fixed 220. Leg 3 started from scratch instead
of resuming, so lineage B re-solved the 45 tasks lineage A had already done.
That leaves every round-level figure with two defensible-looking answers, and
the wrong one is the one you get by reaching for the same operator twice:

- add coverage and the round reads 147 of 220, which is more tasks than exist
  in the overlap and more progress than anyone made;
- deduplicate cost and the round reads $41.78, which is what lineage B spent,
  not what the round spent. The provider billed for both attempts.

So the two figures take different operators over the same set, and the roll-up
has to apply each to the right one. This file pins that, plus the three states
:mod:`scripts.roll_up_round` refuses to average over rather than report.

The refusals matter more than the arithmetic. Each one is a defect this round
actually produced or came close to producing: a leg that resumed nothing
(34603033098), a leg that restored the *shorter* lineage and would have stranded
work, and a record built against the wrong ledger set. A roll-up that quietly
absorbed any of them would still print a plausible round state.

Offline: builds its own records in a tmp dir. Nothing here reads a real run,
contacts a provider, or prices a call.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from roll_up_round import Leg, RollUpRefused, roll_up  # noqa: E402

RECORDS = Path(__file__).resolve().parents[1] / "docs" / "run_records"

#: Four tasks is the smallest fixed list that can hold the shape: one both
#: lineages solved, one only the survivor reached, one only the superseded
#: lineage reached (for the refusal), and one nobody got to.
SHARED, SURVIVOR_ONLY, SUPERSEDED_ONLY, UNREACHED = (
    "task-shared",
    "task-survivor-only",
    "task-superseded-only",
    "task-never-reached",
)
FIXED = [SHARED, SURVIVOR_ONLY, SUPERSEDED_ONLY, UNREACHED]


def _row(n: int, task_id: str, *, status: str, cost: float | None, files: int = 0):
    if status == "pending":
        return {
            "n": n,
            "task_id": task_id,
            "sector": "Manufacturing",
            "occupation": "Mechanical Engineers",
            "status": "pending",
            "attempted": False,
            "outcome": "never_started",
            "reason": "run_ended_before_this_task",
            "attempts": 0,
            "deliverable_file_count": 0,
            "deliverable_bytes": 0,
            "derived_cost_usd_from_measured_tokens": 0.0,
        }
    return {
        "n": n,
        "task_id": task_id,
        "sector": "Manufacturing",
        "occupation": "Mechanical Engineers",
        "status": status,
        "attempted": True,
        "outcome": "ok" if status == "success" else "failed",
        "reason": None if status == "success" else "rate_limit",
        "attempts": 1,
        "deliverable_file_count": files,
        "deliverable_bytes": files * 1000,
        "derived_cost_usd_from_measured_tokens": cost,
    }


def _record(tmp_path: Path, name: str, attempted: dict[str, tuple]) -> Path:
    """One run record: every task in the fixed list, attempted ones detailed."""
    rows = []
    for n, task_id in enumerate(FIXED, start=1):
        if task_id in attempted:
            status, cost, files = attempted[task_id]
            rows.append(_row(n, task_id, status=status, cost=cost, files=files))
        else:
            rows.append(_row(n, task_id, status="pending", cost=0.0))
    directory = tmp_path / name
    directory.mkdir()
    (directory / "outcomes.json").write_text(json.dumps(rows))
    return directory


@pytest.fixture
def two_lineages(tmp_path: Path):
    """Lineage A solved the shared task. Lineage B re-solved it, then went on.

    B's second leg inherits A's — sorry, its own predecessor's — row verbatim,
    which is what a correct resume does.
    """
    a = Leg("A", "100", _record(tmp_path, "a", {SHARED: ("success", 1.00, 2)}))
    b1 = Leg("B", "200", _record(tmp_path, "b1", {SHARED: ("success", 3.00, 5)}))
    b2 = Leg(
        "B",
        "300",
        _record(
            tmp_path,
            "b2",
            {SHARED: ("success", 3.00, 5), SURVIVOR_ONLY: ("error", 0.50, 0)},
        ),
    )
    return a, b1, b2


def test_coverage_unions_across_lineages_instead_of_adding(two_lineages):
    a, b1, b2 = two_lineages
    document = roll_up([a, b1, b2], surviving="B")

    state = document["round_state"]
    assert state["tasks_total"] == 4
    # A reached 1 and B reached 2. Added that is 3; the union is 2, and 2 is
    # how many of the four tasks this round actually has a result for.
    assert state["tasks_attempted"] == 2
    assert state["tasks_never_attempted"] == 2
    assert document["duplication"]["tasks_solved_by_more_than_one_lineage"] == 1


def test_cost_adds_across_lineages_instead_of_unioning(two_lineages):
    a, b1, b2 = two_lineages
    cost = roll_up([a, b1, b2], surviving="B")["cost"]

    # A paid $1.00 for the shared task; B paid $3.00 for the same task and
    # $0.50 for its own. Deduplicating would drop A's dollar, which was spent.
    assert cost["round_total_usd"] == pytest.approx(4.50)
    assert cost["spent_on_work_that_was_superseded_usd"] == pytest.approx(1.00)
    assert cost["is_provider_billed"] is False


def test_a_lineages_cost_comes_from_its_final_leg_not_the_sum_of_its_legs(
    two_lineages,
):
    """B's legs report $3.00 and $3.50. B spent $3.50, not $6.50.

    A resumed leg's record is built with its predecessors' ledgers, so it
    already contains their tasks at their prices. Summing the legs counts the
    inherited work once per leg that inherited it.
    """
    a, b1, b2 = two_lineages
    per_lineage = roll_up([a, b1, b2], surviving="B")["cost"]["per_lineage"]

    assert per_lineage["B"]["derived_cost_usd"] == pytest.approx(3.50)
    assert per_lineage["B"]["final_leg"] == "lineage B run 300"


def test_a_task_only_the_superseded_lineage_reached_stops_the_roll_up(tmp_path):
    """The failure mode the relay came within one input of producing.

    Run 34631861765 restored lineage B, the longer one. Had it restored lineage
    A, B's extra tasks would have been real, paid-for results sitting outside
    the surviving record -- and a round state read off the survivor alone would
    have reported them as never attempted.
    """
    a = Leg(
        "A",
        "100",
        _record(
            tmp_path,
            "a",
            {SHARED: ("success", 1.00, 2), SUPERSEDED_ONLY: ("success", 1.00, 3)},
        ),
    )
    b = Leg("B", "200", _record(tmp_path, "b", {SHARED: ("success", 3.00, 5)}))

    with pytest.raises(RollUpRefused) as refusal:
        roll_up([a, b], surviving="B")
    assert SUPERSEDED_ONLY in str(refusal.value)
    assert "only by a superseded lineage" in str(refusal.value)


def test_a_later_leg_that_lost_inherited_work_stops_the_roll_up(tmp_path):
    b1 = Leg(
        "B",
        "200",
        _record(
            tmp_path,
            "b1",
            {SHARED: ("success", 3.00, 5), SURVIVOR_ONLY: ("success", 1.00, 1)},
        ),
    )
    b2 = Leg("B", "300", _record(tmp_path, "b2", {SHARED: ("success", 3.00, 5)}))

    with pytest.raises(RollUpRefused) as refusal:
        roll_up([b1, b2], surviving="B")
    assert "had already attempted" in str(refusal.value)


def test_a_later_leg_that_changed_an_inherited_result_stops_the_roll_up(tmp_path):
    """Two records disagreeing about one attempt is a finding, not a tie-break."""
    b1 = Leg("B", "200", _record(tmp_path, "b1", {SHARED: ("success", 3.00, 5)}))
    b2 = Leg("B", "300", _record(tmp_path, "b2", {SHARED: ("error", 3.00, 0)}))

    with pytest.raises(RollUpRefused) as refusal:
        roll_up([b1, b2], surviving="B")
    assert "disagree about one attempt" in str(refusal.value)


def test_records_describing_different_task_lists_stop_the_roll_up(tmp_path):
    """Same ids, different order is a different fixed list.

    Every report in this round counts by position -- "tasks 59 to 102" -- so a
    reordered list makes those ranges name different work while every id-set
    check still passes.
    """
    forward = _record(tmp_path, "forward", {SHARED: ("success", 1.00, 2)})
    rows = json.loads((forward / "outcomes.json").read_text())
    rows[0]["task_id"], rows[1]["task_id"] = rows[1]["task_id"], rows[0]["task_id"]
    shuffled = tmp_path / "shuffled"
    shuffled.mkdir()
    (shuffled / "outcomes.json").write_text(json.dumps(rows))

    with pytest.raises(RollUpRefused) as refusal:
        roll_up([Leg("A", "100", forward), Leg("B", "200", shuffled)], surviving="B")
    assert "same fixed task list" in str(refusal.value)


def test_a_missing_ledger_is_reported_as_unchecked_not_as_agreement(two_lineages):
    a, b1, b2 = two_lineages
    check = roll_up([a, b1, b2], surviving="B")["cost"]["ledger_cross_check"]

    assert check["performed"] is False
    assert "agrees_with_the_run_records" not in check


def test_a_task_with_no_derivable_cost_makes_the_round_total_a_floor(tmp_path):
    """``null`` is not zero, and a total containing one is not a total."""
    priced = Leg("B", "200", _record(tmp_path, "p", {SHARED: ("error", None, 0)}))

    cost = roll_up([priced], surviving="B")["cost"]
    assert cost["round_total_usd"] == pytest.approx(0.0)
    assert cost["round_total_is_a_floor"] is True
    assert cost["per_lineage"]["B"]["tasks_with_no_derivable_cost"] == 1


@pytest.mark.skipif(
    not (RECORDS / "exp035_run34631861765_partial" / "outcomes.json").is_file(),
    reason="the committed run records for this round are not present",
)
def test_the_committed_records_still_roll_up_to_the_round_the_reports_state():
    """The figures three ``report.md`` files quote, recomputed from the records.

    If a record is rebuilt and a number moves, this fails here rather than in a
    reader's head three documents later.
    """
    document = roll_up(
        [
            Leg("A", "34571840967", RECORDS / "exp035_run34571840967_partial"),
            Leg("B", "34603033098", RECORDS / "exp035_run34603033098_partial"),
            Leg("B", "34631861765", RECORDS / "exp035_run34631861765_partial"),
        ],
        surviving="B",
    )

    assert document["fixed_task_list"]["task_count"] == 220
    assert document["fixed_task_list"]["identical_across_every_record"] is True

    state = document["round_state"]
    assert (state["tasks_attempted"], state["coverage_percent"]) == (102, 46.4)
    assert (state["tasks_succeeded"], state["tasks_failed"]) == (74, 28)
    assert state["tasks_never_attempted"] == 118

    assert document["failure_reasons"] == {
        "content_filter": 5,
        "rate_limit": 15,
        "transport_error": 7,
        "turn_failed": 1,
    }
    assert document["duplication"] == {
        "tasks_solved_by_more_than_one_lineage": 45,
        "tasks_reached_only_by_a_superseded_lineage": 0,
        "why_coverage_does_not_add": document["duplication"][
            "why_coverage_does_not_add"
        ],
    }
    assert document["deliverables"] == {"files": 269, "bytes": 611_429_470}

    # $14.3866 superseded + $41.7784 surviving, both floors.
    cost = document["cost"]
    assert round(cost["per_lineage"]["A"]["derived_cost_usd"], 4) == 14.3866
    assert round(cost["per_lineage"]["B"]["derived_cost_usd"], 4) == 41.7784
    assert round(cost["round_total_usd"], 4) == 56.1650
    assert cost["round_total_is_a_floor"] is True

    # 58 inherited, none lost, none altered. That is what "the resume worked"
    # means, and it is the one thing this round had never managed before.
    (inheritance,) = document["inheritance_checks"]
    assert inheritance["tasks_inherited"] == 58
    assert inheritance["tasks_lost"] == 0
    assert inheritance["inherited_rows_identical"] is True
    assert inheritance["tasks_added_by_the_later_leg"] == 44
