"""Telling a turn ceiling spent on refused calls apart from one spent on work.

``experiment-design`` §3 is about axes and §5 is about who validates the judge.
Both land here. The corrected-harness plan promises to separate three failures
-- a tool the desk refuses, a run that hits its tool-call ceiling, and a model
that talks and stops without finalising -- and only two of those are endings.

A refusal is not an ending. :data:`core.agentic_v2_conversation._ENDS_THE_RUN`
leaves ``capability_unavailable`` out on purpose: the desk hands the refusal
back and the loop carries on, because reading a refusal and choosing something
else is the behaviour stage one exists to measure. What the refusal does is
spend a turn. So a task refused seven times ends at its ceiling, and its row
says ``tool_budget_exhausted`` -- the same word as a task that spent seven
turns doing real work and ran out. One of those is a closed tool desk and the
other is a task too big for eight calls, and before this module they were the
same number.

Every case is built rather than observed, and the ones that matter most are the
pairs: two tasks identical in every existing column, separated only by the new
one. Offline, and free. Nothing here calls a model or a backend.
"""
from __future__ import annotations

from typing import Any

import pytest

from core.agentic_v2_conversation import TurnRecord, ends_the_run
from core.agentic_v2_outcome import (
    FINALIZE_ACCEPTED,
    FINALIZE_ENDED_FIRST,
    FINALIZE_NOT_CALLED,
    count_separately,
    ending_label,
    read_outcome,
    refusals_handed_back_in,
)

#: What asking to run a command gets from the fixture desk today.
REFUSED = "capability_unavailable"

#: What ended twelve of trial_30's thirty tasks. Also handed back.
BROWSER = "capability_unavailable"


def _turn(number: int, *, ok: bool, error: str | None = None, tool: str = "browser_run") -> TurnRecord:
    return TurnRecord(
        turn=number,
        call_id=f"call_{number:03d}",
        tool_name=tool,
        argument_names=("url",),
        stated_reason="",
        ok=ok,
        error_type=error,
        request_sha256=None,
        result_sha256=None,
        result_bytes=0,
        input_tokens=100,
        output_tokens=10,
        replayed=False,
    )


def _succeeded(**changed: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "success": True,
        "text": "",
        "deliverable_text": "## The answer\n\nThree sites, ranked.\n",
        "files": [],
        "error": None,
    }
    record.update(changed)
    return record


def _failed(error: str) -> dict[str, Any]:
    return {
        "success": False,
        "text": "",
        "deliverable_text": "",
        "files": [],
        "error": error,
    }


# ---------------------------------------------------------------------------
# What counts as a refusal handed back
# ---------------------------------------------------------------------------


def test_a_refused_turn_is_counted():
    turns = [_turn(1, ok=False, error=REFUSED), _turn(2, ok=True)]
    assert refusals_handed_back_in(turns) == (REFUSED,)


def test_a_turn_that_ended_the_run_is_not_a_handed_back_refusal():
    """The distinction the whole column rests on.

    ``compute_backend_error`` is a broken desk and it stops the run. Counting
    it here would put a harness defect in a column about tool policy, which is
    the confusion this module was written to prevent.
    """
    assert ends_the_run("compute_backend_error") is True
    assert refusals_handed_back_in([_turn(1, ok=False, error="compute_backend_error")]) == ()


@pytest.mark.parametrize(
    "ending",
    ["tool_budget_exhausted", "task_wall_time_exhausted", "compute_start_failed"],
)
def test_no_ending_reason_is_ever_counted_as_a_refusal(ending):
    assert refusals_handed_back_in([_turn(1, ok=False, error=ending)]) == ()


def test_a_successful_turn_is_not_a_refusal():
    assert refusals_handed_back_in([_turn(1, ok=True), _turn(2, ok=True)]) == ()


def test_a_failed_turn_with_no_reason_is_not_invented_into_one():
    """A blank ``error_type`` is a gap in the record, not a refusal.

    Counting it would manufacture evidence for the hypothesis under test, which
    is the direction this run must not be wrong in.
    """
    assert refusals_handed_back_in([_turn(1, ok=False, error=None)]) == ()
    assert refusals_handed_back_in([_turn(1, ok=False, error="")]) == ()


def test_turns_are_read_as_records_or_as_the_dicts_they_serialise_to():
    """The conversation is kept beside the run and arrives in either shape."""
    as_records = [_turn(1, ok=False, error=REFUSED)]
    as_dicts = [record.as_dict() for record in as_records]
    assert refusals_handed_back_in(as_dicts) == refusals_handed_back_in(as_records)
    assert refusals_handed_back_in(as_dicts) == (REFUSED,)


def test_a_task_with_no_turns_has_no_refusals_and_is_not_an_error():
    """A task that never reached a model has nothing to read, not a zero."""
    outcome = read_outcome("t0", _failed("compute_start_failed"))
    assert outcome.tool_refusals == ()
    assert outcome.met_a_refusal is False


# ---------------------------------------------------------------------------
# The pair this module exists for
# ---------------------------------------------------------------------------


def test_two_tasks_at_the_same_ceiling_differ_only_in_the_new_column():
    """Identical in every column that existed before. Not the same finding.

    Seven refused calls and seven useful ones reach the ceiling the same way,
    and ``tool_budget_exhausted`` is the honest name for both endings. The
    reason they got there is a different fact and it now has somewhere to live.
    """
    refused = read_outcome(
        "refused",
        _failed("tool_budget_exhausted"),
        turns=[_turn(n, ok=False, error=BROWSER) for n in range(1, 8)],
    )
    worked = read_outcome(
        "worked",
        _failed("tool_budget_exhausted"),
        turns=[_turn(n, ok=True) for n in range(1, 8)],
    )

    # Every pre-existing answer agrees.
    assert refused.finalize == worked.finalize == FINALIZE_ENDED_FIRST
    assert refused.error_type == worked.error_type == "tool_budget_exhausted"
    assert refused.produced_a_usable_file == worked.produced_a_usable_file
    assert refused.quality is worked.quality is None

    # The new one does not.
    assert refused.met_a_refusal is True
    assert worked.met_a_refusal is False
    assert refused.tool_refusals_by_kind == {BROWSER: 7}
    assert worked.tool_refusals_by_kind == {}


def test_the_cross_tab_splits_one_ending_into_the_two_stories():
    counted = count_separately(
        [
            read_outcome(
                "refused",
                _failed("tool_budget_exhausted"),
                turns=[_turn(n, ok=False, error=BROWSER) for n in range(1, 8)],
            ),
            read_outcome(
                "worked",
                _failed("tool_budget_exhausted"),
                turns=[_turn(n, ok=True) for n in range(1, 8)],
            ),
        ]
    )

    assert counted["endings_after_a_refusal"]["tool_budget_exhausted"] == {
        "with_refusals": 1,
        "without": 1,
    }
    assert counted["tasks_that_met_a_refusal"] == 1
    assert counted["tool_refusals"] == 7


# ---------------------------------------------------------------------------
# The three the plan promises to separate
# ---------------------------------------------------------------------------


def test_tool_refusal_turn_exhaustion_and_a_silent_model_are_three_rows():
    """Named separately, and the refusal is not one of the endings.

    The first two tasks below met the same refusal. One ran out of calls and
    the other stopped talking, and those are different findings about the same
    cause -- which is why the cause is a column and not a third ending.
    """
    outcomes = [
        read_outcome(
            "ceiling",
            _failed("tool_budget_exhausted"),
            turns=[_turn(n, ok=False, error=BROWSER) for n in range(1, 9)],
        ),
        read_outcome(
            "gave_up",
            _failed("finalize_not_called"),
            turns=[_turn(1, ok=False, error=BROWSER), _turn(2, ok=True)],
        ),
        read_outcome(
            "quiet",
            _failed("finalize_not_called"),
            turns=[_turn(1, ok=True)],
        ),
    ]
    counted = count_separately(outcomes)

    assert counted["endings_after_a_refusal"] == {
        "tool_budget_exhausted": {"with_refusals": 1, "without": 0},
        FINALIZE_NOT_CALLED: {"with_refusals": 1, "without": 1},
    }
    assert counted["tool_refusals_by_kind"] == {BROWSER: 9}


def test_the_ceiling_keeps_its_own_name_rather_than_the_generic_ending():
    """``ended_before_it_could_be`` covers three unlike things; the label does
    not."""
    assert ending_label(read_outcome("a", _failed("tool_budget_exhausted"))) == (
        "tool_budget_exhausted"
    )
    assert ending_label(read_outcome("b", _failed("task_wall_time_exhausted"))) == (
        "task_wall_time_exhausted"
    )
    assert ending_label(read_outcome("c", _failed("finalize_not_called"))) == (
        FINALIZE_NOT_CALLED
    )
    assert ending_label(read_outcome("d", _succeeded())) == FINALIZE_ACCEPTED


# ---------------------------------------------------------------------------
# A refusal is not a failure
# ---------------------------------------------------------------------------


def test_a_task_that_was_refused_and_finished_anyway_is_a_success():
    """The behaviour stage one is for. Four closed doors and a deliverable.

    If this counted as a failure the column would be measuring the tool desk's
    policy rather than the model's response to it.
    """
    outcome = read_outcome(
        "worked_around_it",
        _succeeded(),
        turns=[_turn(n, ok=False, error=BROWSER) for n in range(1, 5)]
        + [_turn(5, ok=True, tool="finalize")],
    )
    assert outcome.finalize == FINALIZE_ACCEPTED
    assert outcome.finalize_was_accepted is True
    assert outcome.met_a_refusal is True
    assert len(outcome.tool_refusals) == 4

    counted = count_separately([outcome])
    assert counted["finalize_accepted"] == 1
    assert counted["endings_after_a_refusal"][FINALIZE_ACCEPTED] == {
        "with_refusals": 1,
        "without": 0,
    }


# ---------------------------------------------------------------------------
# The refusal count never joins the endings
# ---------------------------------------------------------------------------


def test_the_refusals_are_not_in_the_denominator():
    """Nine refusals across two tasks. The denominator is two."""
    counted = count_separately(
        [
            read_outcome(
                "a",
                _failed("tool_budget_exhausted"),
                turns=[_turn(n, ok=False, error=BROWSER) for n in range(1, 9)],
            ),
            read_outcome(
                "b", _succeeded(), turns=[_turn(1, ok=False, error=BROWSER)]
            ),
        ]
    )
    assert counted["tasks"] == 2
    assert counted["tool_refusals"] == 9

    endings = (
        counted["finalize_accepted"]
        + counted["finalize_not_called"]
        + counted["finalize_ended_first"]
    )
    assert endings == counted["tasks"], "the three endings still partition the tasks"


def test_the_cross_tab_totals_back_to_the_task_count():
    outcomes = [
        read_outcome("a", _succeeded(), turns=[_turn(1, ok=False, error=BROWSER)]),
        read_outcome("b", _succeeded(), turns=[_turn(1, ok=True)]),
        read_outcome("c", _failed("finalize_not_called")),
    ]
    counted = count_separately(outcomes)
    total = sum(
        row["with_refusals"] + row["without"]
        for row in counted["endings_after_a_refusal"].values()
    )
    assert total == counted["tasks"] == 3


def test_the_tally_says_in_words_that_a_refusal_is_not_an_ending():
    counted = count_separately([read_outcome("a", _succeeded())])
    assert "a cause and not an ending" in counted["refusal_note"]


def test_the_row_carries_the_count_and_the_kinds():
    row = read_outcome(
        "t",
        _failed("tool_budget_exhausted"),
        turns=[
            _turn(1, ok=False, error=BROWSER),
            _turn(2, ok=False, error="workspace_apply_rejected"),
            _turn(3, ok=False, error=BROWSER),
        ],
    ).as_row()

    assert row["tool_refusals"] == 3
    assert row["tool_refusals_by_kind"] == {BROWSER: 2, "workspace_apply_rejected": 1}
    assert row["error_type"] == "tool_budget_exhausted"
    assert row["quality"] is None


def test_a_refusal_column_is_still_not_a_quality_measure():
    """Zero refusals says nothing about whether the work was any good."""
    outcome = read_outcome("t", _succeeded(), turns=[_turn(1, ok=True)])
    assert outcome.met_a_refusal is False
    assert outcome.quality is None
    with pytest.raises(TypeError, match="three answers"):
        bool(outcome)
