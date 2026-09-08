"""Pin what Codex's token numbers actually mean, before anyone reads them wrong.

The number 51 caused a real problem. A note in
`tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md` said "two turns of 11 and 40
input tokens settle as 51", which invites two incompatible readings -- 11 + 40 =
51, or a cumulative 11 then 40 giving a delta of 29 -- and gives the reader no
way to tell which the code does. The code was right and the sentence was wrong,
but nothing in the suite said so, because no test imported this module at all.

So this file states the shape as executable fact:

* 11 and 40 are **two requests inside one turn**, not two turns. Codex sums them
  and reports 51 on `ThreadTokenUsage.total`. That is the number the receipt
  takes, and `test_the_thread_total_is_the_sum_of_its_requests` says so with the
  same three numbers the note argued about.
* `.last` would be 40 -- the final request alone. Charging that would lose the
  tool-call request entirely, which is
  `test_the_last_sample_is_not_the_turn_and_is_not_used`.
* The delta arithmetic exists so a second turn on a shared thread cannot
  re-charge the first, and today it never changes an answer, because
  `codex_runner` gives every task a fresh thread. That is worth a test precisely
  *because* it is dormant: a dormant guard with no test is a guard that quietly
  stops working before anyone needs it.

The other half is the refusals. Everything here is arithmetic on numbers that
end up in a cost ledger, and the interesting cases are the ones where the honest
answer is "I cannot tell you":

* a cumulative counter that goes backwards raises, rather than clamping to zero
  and reporting a plausible small number that is not true;
* a token class the receipt has no field for -- `cache_write_input_tokens` --
  produces `usage_partial` instead of silently vanishing into a total that then
  looks complete;
* a turn that reported nothing produces `usage_absent`, not a free turn;
* every settlement carries `call_reachability_unknown`, including the ones that
  price cleanly, because one turn is an unknown number of model requests and
  that stays true when the arithmetic works.

None of this needs the Codex binary, a sandbox, or a network. The SDK's objects
are duck-typed here on purpose: this module reads them by attribute so that it
stays testable on a machine where the runtime cannot start, which is every
machine this project currently has.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.codex_cost import (  # noqa: E402
    CODEX_COST_BUCKET,
    CODEX_STRUCTURAL_REASONS,
    CodexTokenTotals,
    CodexUsageError,
    missing_reasons_for,
    read_breakdown,
    read_thread_totals,
    settle_codex_turn,
    to_call_usage,
    turn_usage_delta,
)
from core.cost_receipts import (  # noqa: E402
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    REASON_CALL_REACHABILITY_UNKNOWN,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
)


def breakdown(
    *,
    input_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    cache_write_input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_output_tokens: int | None = None,
) -> SimpleNamespace:
    """Stand in for the SDK's `TokenUsageBreakdown`.

    Duck-typed rather than imported, for the same reason the module under test
    reads it by attribute: this has to work where the runtime does not.
    """
    return SimpleNamespace(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_write_input_tokens=cache_write_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
    )


def thread_usage(*, total: object = None, last: object = None) -> SimpleNamespace:
    """Stand in for the SDK's `ThreadTokenUsage`."""
    return SimpleNamespace(total=total, last=last)


# ---------------------------------------------------------------------------
# The 11 / 40 / 51 question, settled
# ---------------------------------------------------------------------------


def test_the_thread_total_is_the_sum_of_its_requests() -> None:
    """One turn, two requests of 11 and 40: the thread total reads 51.

    These are the exact numbers the end-to-end fixture sends and the exact
    numbers the prose got wrong. 51 is a sum across requests within a turn --
    not a cumulative figure to be differenced against an earlier turn, and not
    two separate rows.
    """
    usage = thread_usage(
        total=breakdown(input_tokens=51, output_tokens=19),
        last=breakdown(input_tokens=40, output_tokens=12),
    )
    totals = read_thread_totals(usage)

    assert totals.input_tokens == 51
    assert totals.output_tokens == 19


def test_the_last_sample_is_not_the_turn_and_is_not_used() -> None:
    """`.last` is the final request alone; taking it would lose the first one.

    40 is a real number the SDK offers, and it is the wrong one: the tool-call
    request that cost 11 would go unbilled.
    """
    usage = thread_usage(
        total=breakdown(input_tokens=51),
        last=breakdown(input_tokens=40),
    )
    assert read_thread_totals(usage).input_tokens == 51
    assert read_thread_totals(usage).input_tokens != 40


def test_a_fresh_thread_charges_the_whole_total() -> None:
    """The live shape: one fresh thread, one turn, before-total zero.

    `codex_runner` opens a thread per task, so this is what actually happens on
    every run today -- the delta equals the total, and 51 is what the receipt
    gets.
    """
    delta = turn_usage_delta(
        CodexTokenTotals.zero(),
        CodexTokenTotals(
            input_tokens=51,
            cached_input_tokens=11,
            output_tokens=19,
            reasoning_output_tokens=5,
            cache_write_input_tokens=0,
        ),
    )
    assert delta.input_tokens == 51
    assert delta.output_tokens == 19
    assert delta.cached_input_tokens == 11
    assert delta.reasoning_output_tokens == 5


def test_a_second_turn_on_one_thread_is_not_charged_the_first_one_again() -> None:
    """The dormant guard, exercised.

    Nothing in the runner reaches this today. It is tested anyway: a guard that
    is never exercised is a guard that can rot silently and then fail on the
    first day something depends on it. If a future change reuses a thread across
    turns, this is what stops the second settlement from re-billing the first.
    """
    after_first = CodexTokenTotals(input_tokens=51, output_tokens=19)
    after_second = CodexTokenTotals(input_tokens=140, output_tokens=44)

    delta = turn_usage_delta(after_first, after_second)

    assert delta.input_tokens == 89
    assert delta.output_tokens == 25


# ---------------------------------------------------------------------------
# Refusals: where the honest answer is "I cannot tell you"
# ---------------------------------------------------------------------------


def test_a_cumulative_counter_that_goes_backwards_is_refused() -> None:
    """A total that shrank means the reading is not what we think it is.

    Clamping to zero would produce a small, plausible, untrue number and put it
    in a ledger. Raising says the thing that is actually known.
    """
    with pytest.raises(CodexUsageError) as raised:
        turn_usage_delta(
            CodexTokenTotals(input_tokens=51),
            CodexTokenTotals(input_tokens=40),
        )

    message = str(raised.value)
    assert "51" in message and "40" in message
    assert "input_tokens" in message


def test_an_unreadable_before_total_yields_unknown_rather_than_everything() -> None:
    """Not knowing where a turn started is not a licence to charge all of it.

    `after` alone cannot be attributed: some of it may belong to earlier turns.
    `None` -- the count was not established -- is the true answer, and it flows
    on to `usage_absent` rather than to a confident figure.
    """
    delta = turn_usage_delta(
        CodexTokenTotals(input_tokens=None),
        CodexTokenTotals(input_tokens=51),
    )
    assert delta.input_tokens is None


def test_a_negative_count_is_refused_at_the_point_of_reading() -> None:
    with pytest.raises(CodexUsageError):
        read_breakdown(breakdown(input_tokens=-1))


def test_a_count_that_is_not_a_number_is_refused() -> None:
    """Including `True`, which `isinstance(x, int)` would otherwise wave past."""
    with pytest.raises(CodexUsageError):
        read_breakdown(breakdown(input_tokens="lots"))
    with pytest.raises(CodexUsageError):
        read_breakdown(breakdown(input_tokens=True))


def test_no_usage_notification_is_absent_not_free() -> None:
    """A turn that reported nothing did not cost nothing.

    `None` here is the SDK's real behaviour -- `_collect_turn_result` keeps the
    last notification seen, and there may have been none.
    """
    totals = read_thread_totals(None)
    assert totals.is_empty
    assert REASON_USAGE_ABSENT in missing_reasons_for(totals)


def test_zero_is_a_measurement_and_absent_is_not() -> None:
    """The one place a zero is right, kept distinct from the many where it is not."""
    assert not CodexTokenTotals.zero().is_empty
    assert CodexTokenTotals().is_empty


# ---------------------------------------------------------------------------
# Token classes the receipt cannot express
# ---------------------------------------------------------------------------


def test_cache_writes_make_the_receipt_partial_rather_than_disappearing() -> None:
    """There is no `cache_write_input_tokens` field and no rate for it.

    Three options existed: fold it into `input_tokens` and change the priced
    amount on a guess, drop it and report a total that looks complete, or say
    the receipt is partial. Only the third is true.
    """
    totals = CodexTokenTotals(input_tokens=51, cache_write_input_tokens=7)

    assert REASON_USAGE_PARTIAL in missing_reasons_for(totals)
    usage = to_call_usage(totals)
    assert usage.input_tokens == 51, "a cache write must not inflate the input count"
    assert not hasattr(usage, "cache_write_input_tokens")


def test_zero_cache_writes_lose_nothing_and_so_are_not_flagged() -> None:
    totals = CodexTokenTotals(input_tokens=51, cache_write_input_tokens=0)
    assert REASON_USAGE_PARTIAL not in missing_reasons_for(totals)


def test_audio_fields_stay_unreported_rather_than_zero() -> None:
    """Codex reports no audio split, so `None` -- not 0 -- is the fact."""
    usage = to_call_usage(CodexTokenTotals(input_tokens=51))
    assert usage.audio_input_tokens is None
    assert usage.audio_output_tokens is None


# ---------------------------------------------------------------------------
# What every Codex settlement has to admit
# ---------------------------------------------------------------------------


def test_a_turn_is_never_claimed_to_be_one_call() -> None:
    """Even a clean, fully-priced turn carries `call_reachability_unknown`.

    Codex decides for itself how many model requests to make, and exposes none
    of them individually. The uncertainty is structural: it does not go away
    when the arithmetic happens to work, so the reason is unconditional.
    """
    clean = CodexTokenTotals(
        input_tokens=51,
        cached_input_tokens=11,
        cache_write_input_tokens=0,
        output_tokens=19,
        reasoning_output_tokens=5,
    )
    reasons = missing_reasons_for(clean)

    assert REASON_CALL_REACHABILITY_UNKNOWN in reasons
    assert REASON_USAGE_ABSENT not in reasons
    assert REASON_USAGE_PARTIAL not in reasons
    assert CODEX_STRUCTURAL_REASONS == (REASON_CALL_REACHABILITY_UNKNOWN,)


def test_reasons_are_not_repeated() -> None:
    totals = CodexTokenTotals(cache_write_input_tokens=3)
    reasons = missing_reasons_for(totals)
    assert len(reasons) == len(set(reasons))


def test_codex_spend_is_problem_solving_and_never_grading() -> None:
    """Solving a task and grading it are different budgets and must not mix."""
    assert CODEX_COST_BUCKET == BUCKET_PROBLEM_SOLVING
    assert CODEX_COST_BUCKET != BUCKET_GRADING


# ---------------------------------------------------------------------------
# The settlement handed to the ledger
# ---------------------------------------------------------------------------


class RecordingLedger:
    """Captures one `settle` call so the arguments can be inspected."""

    def __init__(self) -> None:
        self.settled: list[dict[str, object]] = []

    def settle(self, call_id, *, usage, resolved_model, extra_reasons):  # noqa: ANN001
        self.settled.append(
            {
                "call_id": call_id,
                "usage": usage,
                "resolved_model": resolved_model,
                "extra_reasons": extra_reasons,
            }
        )
        return "settled"


def test_the_settlement_carries_the_delta_and_its_reasons() -> None:
    ledger = RecordingLedger()
    totals = CodexTokenTotals(
        input_tokens=51,
        cached_input_tokens=11,
        cache_write_input_tokens=7,
        output_tokens=19,
        reasoning_output_tokens=5,
    )

    settle_codex_turn(
        ledger, "call-1", totals=totals, resolved_model="gpt-5.4-codex"
    )

    (entry,) = ledger.settled
    assert entry["call_id"] == "call-1"
    assert entry["resolved_model"] == "gpt-5.4-codex"
    assert entry["usage"].input_tokens == 51
    assert REASON_CALL_REACHABILITY_UNKNOWN in entry["extra_reasons"]
    assert REASON_USAGE_PARTIAL in entry["extra_reasons"]


def test_an_empty_turn_still_settles_and_says_it_saw_nothing() -> None:
    """A turn with no usage is settled as unknown, never abandoned as free."""
    ledger = RecordingLedger()
    settle_codex_turn(ledger, "call-2", totals=CodexTokenTotals())

    (entry,) = ledger.settled
    assert entry["usage"].is_empty
    assert REASON_USAGE_ABSENT in entry["extra_reasons"]
    assert REASON_CALL_REACHABILITY_UNKNOWN in entry["extra_reasons"]
