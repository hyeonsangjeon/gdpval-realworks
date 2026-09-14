"""The bill and the voice, counted from opposite ends of the same run.

``scripts/run_agentic_v2_stage.py`` keeps two accounts of every paid call and
says in ``model_calls_record`` that they are kept apart on purpose -- "the two
are computed from different things and disagreement between them is worth being
able to see". Until now nothing has ever put them side by side, while the
corrected-harness plan's stopping rules say the run halts if they disagree. A
stopping rule with no reader is a sentence.

This file is the reader's test, and it is an integration test rather than a unit
one: a real :class:`~core.agentic_v2_model_voice.AzureFoundryVoice` over a
scripted client, the real ``run_model_conversation`` loop, the real
``model_turns_of``, and a real sqlite ledger in ``tmp_path``. The counts being
compared are produced by the same code the paid run uses, so an agreement here
is evidence about that path rather than about two fixtures.

The finding it is built around
------------------------------

**Plain equality is the wrong invariant, and asserting it would stop good runs.**
The voice appends its row only after a reply arrives with usable counts; a reply
that arrives without them leaves no row at all. The same reply still reaches the
ledger -- the provider answered and will bill for it -- as a row with an empty
usage. So the ledger is legitimately ahead by exactly the uncounted replies::

    receipt.model_calls == voice rows + model_calls_not_counted

That case is built here from a real reply with no usage block, and the reader is
required to call it agreement. The direction of a real gap is checked too: a
call that never reached the bill and a bill holding a call the voice never saw
are different failures and are reported as such.

Offline. The client is a list of prepared answers, the desk is a list written in
advance, and the ledger is a file in a temp directory. Nothing here asks a model
or costs anything.
"""
from __future__ import annotations

import json
from typing import Any, Optional, Sequence

import pytest

from core.agentic_v2_call_agreement import compare, describe, the_stop_rule
from core.agentic_v2_conversation import (
    LoopLimits,
    ScriptedToolDesk,
    ToolOutcome,
    run_model_conversation,
)
from core.agentic_v2_conversation_runner import model_turns_of
from core.agentic_v2_cost_binding import bind_run_to_ledger
from core.agentic_v2_model_voice import AzureFoundryVoice
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    STATUS_UNAVAILABLE,
    CostReceiptLedger,
    load_receipt_price_table,
)
from core.execution_envelope_cost import load_provider_price_table

RUN_ID = "a-run-that-kept-two-accounts"
DEPLOYMENT = "gdpval-realworks"

#: What the stub replies report as having answered. In the committed price list
#: under ``azure``, so the receipt can reach ``complete`` and the amounts are
#: the repository's own rather than invented for this file.
RESOLVED_MODEL = "gpt-5.4"

IN_TOKENS = 400
OUT_TOKENS = 31


# ---------------------------------------------------------------------------
# A provider that answers from a list
# ---------------------------------------------------------------------------


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Reply:
    """One prepared response, in the shape the Responses API returns.

    ``usage=None`` is the case the whole module is about: the provider served
    the request, will bill for it, and said nothing about what it used.
    """

    def __init__(
        self,
        *,
        tool: Optional[str] = "workspace_apply",
        call_id: str = "call_1",
        usage: Optional[tuple[int, int]] = (IN_TOKENS, OUT_TOKENS),
        text: str = "",
    ) -> None:
        self.output: list[dict[str, Any]] = (
            [
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": tool,
                    "arguments": json.dumps({"operation": "list", "path": "inputs"}),
                }
            ]
            if tool
            else []
        )
        self.output_text = text
        self.model = RESOLVED_MODEL
        self.usage = None if usage is None else _Usage(*usage)


class _ScriptedClient:
    """Hands back prepared replies in order, and keeps what it was sent."""

    def __init__(self, replies: Sequence[_Reply]) -> None:
        self.sent: list[dict[str, Any]] = []
        prepared = list(replies)
        outer = self

        class _Responses:
            @staticmethod
            def create(**payload: Any) -> Any:
                outer.sent.append(payload)
                if not prepared:
                    raise AssertionError("the loop asked more times than scripted")
                return prepared.pop(0)

        self.responses = _Responses()


def a_voice(replies: Sequence[_Reply]) -> AzureFoundryVoice:
    return AzureFoundryVoice(
        client=_ScriptedClient(replies),
        deployment=DEPLOYMENT,
        resource="a-resource",
        budget=StageOneBudget(
            max_model_calls=16, max_input_tokens=1_000_000, max_output_tokens=100_000
        ),
        instructions="do the task",
        max_output_tokens_per_turn=8192,
        prices=load_provider_price_table("azure"),
    )


def a_conversation(voice: AzureFoundryVoice, answers: Sequence[ToolOutcome]):
    return run_model_conversation(
        task_prompt="the task",
        voice=voice,
        desk=ScriptedToolDesk(answers=list(answers)),
        limits=LoopLimits(
            max_model_turns=8,
            max_written_tokens_per_turn=2048,
            max_seconds=60.0,
            max_repeats_of_one_request=4,
            budget=StageOneBudget(
                max_model_calls=16,
                max_input_tokens=1_000_000,
                max_output_tokens=100_000,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Putting one real task through the whole money path
# ---------------------------------------------------------------------------


def a_ledger(tmp_path) -> CostReceiptLedger:
    """The same constructor the paid run reaches, with the committed prices."""
    return CostReceiptLedger(
        str(tmp_path / "cost_receipts.sqlite3"),
        run_id=RUN_ID,
        price_table=load_receipt_price_table(),
    )


def settle(ledger, *, task_id: str, attempt: int, outcome) -> dict[str, Any]:
    turns = model_turns_of(
        outcome,
        run_id=RUN_ID,
        task_id=task_id,
        attempt=attempt,
        provider="azure",
        requested_model=DEPLOYMENT,
        deployment=DEPLOYMENT,
        resolved_model=RESOLVED_MODEL,
    )
    bind_run_to_ledger(ledger, task_id=task_id, model_turns=turns)
    return ledger.receipt_for(
        task_id, bucket=BUCKET_PROBLEM_SOLVING, when_empty=STATUS_UNAVAILABLE
    ).as_dict()


def a_record(*, per_attempt, conversations, results) -> dict[str, Any]:
    """The three places the run record keeps the two counts in."""
    return {
        "model_calls": {"per_attempt": list(per_attempt)},
        "conversations": {"conversations": dict(conversations)},
        "run": {"results": list(results)},
    }


def one_task_through_everything(
    tmp_path,
    replies: Sequence[_Reply],
    answers: Sequence[ToolOutcome],
    *,
    task_id: str = "a-task",
):
    """A real voice, a real loop, a real ledger, and the record they produce."""
    voice = a_voice(replies)
    outcome = a_conversation(voice, answers)
    ledger = a_ledger(tmp_path)
    try:
        receipt = settle(ledger, task_id=task_id, attempt=1, outcome=outcome)
    finally:
        ledger.close()

    record = a_record(
        per_attempt=[
            {"task_id": task_id, "attempt": 1, "calls": voice.ledger()},
        ],
        conversations={f"{task_id}#1": outcome.as_dict()},
        results=[{"task_id": task_id, "problem_solving_cost": receipt}],
    )
    return voice, outcome, receipt, record


FINISHED = ToolOutcome.committed({"deliverables": ["answer.md"]})


# ---------------------------------------------------------------------------
# The ordinary case
# ---------------------------------------------------------------------------


def test_a_finished_task_agrees_on_both_counts(tmp_path):
    """Three calls, three rows, three settled, same tokens on both sides."""
    voice, outcome, receipt, record = one_task_through_everything(
        tmp_path,
        replies=[_Reply(call_id=f"call_{n}") for n in range(3)],
        answers=[ToolOutcome.worked(bytes=12), ToolOutcome.worked(bytes=12), FINISHED],
    )

    assert len(voice.calls) == 3
    assert outcome.model_calls_not_counted == 0
    assert receipt["model_calls"] == 3

    one = compare(record)[0]
    assert one.counts_agree is True
    assert one.tokens_agree is True
    assert one.agrees is True
    assert one.voice_input_tokens == 3 * IN_TOKENS


def test_the_receipt_reaching_complete_is_the_committed_price_list(tmp_path):
    """Not a claim this file needs, but it says which path was exercised.

    A ``partial`` receipt here would mean the ledger never got the prices, and
    the agreement below would be about a run shape the paid path does not have.
    """
    _, _, receipt, _ = one_task_through_everything(
        tmp_path,
        replies=[_Reply()],
        answers=[FINISHED],
    )
    assert receipt["status"] == "complete"
    assert receipt["usage"]["input_tokens"] == IN_TOKENS


def test_the_stop_rule_says_they_agree(tmp_path):
    _, _, _, record = one_task_through_everything(
        tmp_path,
        replies=[_Reply()],
        answers=[FINISHED],
    )
    verdict = the_stop_rule(record)
    assert verdict["agree"] is True
    assert verdict["compared"] == 1
    assert verdict["disagreed"] == 0
    assert "the bill and the voice describe the same calls" in describe(verdict)


# ---------------------------------------------------------------------------
# The reply that was billed and never counted
# ---------------------------------------------------------------------------


def test_a_reply_with_no_usage_leaves_the_ledger_one_ahead(tmp_path):
    """Built from a real reply, because the numbers matter more than the shape.

    The provider answers a second time and says nothing about what it used. The
    voice files nothing; the conversation files the turn number; the ledger gets
    a row with an empty usage. One call, two records, and they differ by one.
    """
    voice, outcome, receipt, _ = one_task_through_everything(
        tmp_path,
        replies=[_Reply(), _Reply(usage=None)],
        answers=[ToolOutcome.worked(bytes=12)],
    )

    assert len(voice.calls) == 1
    assert outcome.model_calls_not_counted == 1
    assert receipt["model_calls"] == 2, (
        "the uncounted reply did not reach the ledger, which is the defect "
        "model_turns_of's second loop exists to prevent"
    )


def test_that_difference_is_agreement_and_not_a_defect(tmp_path):
    """The invariant this module is built around.

    A reader that asserted equality would halt this run, and the run is fine:
    every call either side saw is accounted for on both.
    """
    _, _, _, record = one_task_through_everything(
        tmp_path,
        replies=[_Reply(), _Reply(usage=None)],
        answers=[ToolOutcome.worked(bytes=12)],
    )

    one = compare(record)[0]
    assert one.voice_counted == 1
    assert one.not_counted == 1
    assert one.ledger_counted == 2
    assert one.the_voice_accounts_for == 2
    assert one.counts_agree is True
    assert one.agrees is True
    assert the_stop_rule(record)["agree"] is True


def test_the_uncounted_reply_does_not_disturb_the_token_comparison(tmp_path):
    """Because an absent usage contributes nothing rather than a zero.

    If it contributed a zero the receipt would hold a smaller-looking total than
    the voice and the two would read as disagreeing about tokens, which would be
    an invented complaint about a run that is behaving.
    """
    _, _, receipt, record = one_task_through_everything(
        tmp_path,
        replies=[_Reply(), _Reply(usage=None)],
        answers=[ToolOutcome.worked(bytes=12)],
    )
    assert receipt["usage"]["input_tokens"] == IN_TOKENS
    assert compare(record)[0].tokens_agree is True


# ---------------------------------------------------------------------------
# Real disagreement, in both directions
# ---------------------------------------------------------------------------


def test_a_call_that_never_reached_the_bill_is_caught(tmp_path):
    """The voice saw three, the ledger holds two. Spend, unrecorded."""
    voice, outcome, receipt, _ = one_task_through_everything(
        tmp_path,
        replies=[_Reply(call_id=f"call_{n}") for n in range(3)],
        answers=[ToolOutcome.worked(bytes=12), ToolOutcome.worked(bytes=12), FINISHED],
    )
    short = dict(receipt)
    short["model_calls"] = 2
    short["usage"] = {"input_tokens": 2 * IN_TOKENS, "output_tokens": 2 * OUT_TOKENS}

    record = a_record(
        per_attempt=[{"task_id": "a-task", "attempt": 1, "calls": voice.ledger()}],
        conversations={"a-task#1": outcome.as_dict()},
        results=[{"task_id": "a-task", "problem_solving_cost": short}],
    )

    one = compare(record)[0]
    assert one.counts_agree is False
    assert one.agrees is False
    assert "the ledger holds 2 call(s) and the voice accounts for 3" in one.why()
    assert the_stop_rule(record)["agree"] is False


def test_a_bill_holding_a_call_the_voice_never_saw_is_caught(tmp_path):
    """The other direction, and it is the more expensive one.

    A ledger ahead of what the run can evidence is an amount nobody can attach
    to a request that was made.
    """
    voice, outcome, receipt, _ = one_task_through_everything(
        tmp_path,
        replies=[_Reply()],
        answers=[FINISHED],
    )
    inflated = dict(receipt)
    inflated["model_calls"] = 4

    record = a_record(
        per_attempt=[{"task_id": "a-task", "attempt": 1, "calls": voice.ledger()}],
        conversations={"a-task#1": outcome.as_dict()},
        results=[{"task_id": "a-task", "problem_solving_cost": inflated}],
    )

    one = compare(record)[0]
    assert one.counts_agree is False
    assert one.ledger_counted == 4
    assert one.the_voice_accounts_for == 1
    assert "a-task" in describe(the_stop_rule(record))


def test_counts_can_agree_while_tokens_do_not(tmp_path):
    """Two calls each side, and one of them was charged for something else.

    Checked because a count-only reader would pass this, and the amount is what
    the receipt is for.
    """
    voice, outcome, receipt, _ = one_task_through_everything(
        tmp_path,
        replies=[_Reply(call_id="call_0"), _Reply(call_id="call_1")],
        answers=[ToolOutcome.worked(bytes=12), FINISHED],
    )
    wrong = dict(receipt)
    wrong["usage"] = {"input_tokens": 9_999, "output_tokens": 2 * OUT_TOKENS}

    record = a_record(
        per_attempt=[{"task_id": "a-task", "attempt": 1, "calls": voice.ledger()}],
        conversations={"a-task#1": outcome.as_dict()},
        results=[{"task_id": "a-task", "problem_solving_cost": wrong}],
    )

    one = compare(record)[0]
    assert one.counts_agree is True
    assert one.tokens_agree is False
    assert one.agrees is False
    assert "9999 in" in one.why()


# ---------------------------------------------------------------------------
# What cannot be compared is not counted as agreement
# ---------------------------------------------------------------------------


def test_a_task_with_no_receipt_is_not_comparable(tmp_path):
    voice, outcome, _, _ = one_task_through_everything(
        tmp_path, replies=[_Reply()], answers=[FINISHED]
    )
    record = a_record(
        per_attempt=[{"task_id": "a-task", "attempt": 1, "calls": voice.ledger()}],
        conversations={"a-task#1": outcome.as_dict()},
        results=[{"task_id": "a-task"}],
    )

    one = compare(record)[0]
    assert one.agrees is None
    assert one.not_comparable_because == (
        "the run record carries no receipt for this task"
    )


def test_a_record_where_nothing_can_be_compared_does_not_report_agreement():
    """The vacuous pass this reader must never produce.

    A stage whose receipts all went missing has not agreed about anything, and
    ``agree: true`` on that record would be the quiet version of the failure the
    stopping rule is written for.
    """
    record = a_record(
        per_attempt=[
            {"task_id": "a-task", "attempt": 1, "calls": []},
            {"task_id": "another", "attempt": 1, "calls": []},
        ],
        conversations={},
        results=[],
    )
    verdict = the_stop_rule(record)

    assert verdict["tasks"] == 2
    assert verdict["compared"] == 0
    assert verdict["not_comparable"] == 2
    assert verdict["agree"] is False


def test_a_task_that_never_ran_is_not_compared(tmp_path):
    """A ``not_run`` receipt has no calls on either side to disagree about."""
    record = a_record(
        per_attempt=[],
        conversations={},
        results=[
            {
                "task_id": "never-reached",
                "problem_solving_cost": {"status": "not_run", "model_calls": 0},
            }
        ],
    )
    one = compare(record)[0]
    assert one.agrees is None
    assert "not_run" in (one.not_comparable_because or "")
    assert the_stop_rule(record)["compared"] == 0


def test_a_receipt_with_no_usage_leaves_the_token_question_open(tmp_path):
    """``None``, not ``True``. Nothing looked, so nothing passed."""
    voice, outcome, receipt, _ = one_task_through_everything(
        tmp_path, replies=[_Reply()], answers=[FINISHED]
    )
    silent = dict(receipt)
    silent["usage"] = {}

    record = a_record(
        per_attempt=[{"task_id": "a-task", "attempt": 1, "calls": voice.ledger()}],
        conversations={"a-task#1": outcome.as_dict()},
        results=[{"task_id": "a-task", "problem_solving_cost": silent}],
    )

    one = compare(record)[0]
    assert one.tokens_agree is None
    assert one.counts_agree is True
    assert one.agrees is True, "an unanswered question is not a failed one"


# ---------------------------------------------------------------------------
# Reading the record itself
# ---------------------------------------------------------------------------


def test_attempts_of_one_task_are_summed_against_its_one_receipt():
    """The receipt is per task; the voices are per attempt.

    A retried task has two voices and one receipt, and comparing either voice
    alone against it would report a disagreement that is only an arithmetic
    mistake in the reader.
    """
    calls = [{"input_tokens": IN_TOKENS, "output_tokens": OUT_TOKENS}]
    record = a_record(
        per_attempt=[
            {"task_id": "retried", "attempt": 1, "calls": list(calls)},
            {"task_id": "retried", "attempt": 2, "calls": list(calls)},
        ],
        conversations={
            "retried#1": {"model_calls_not_counted": 0},
            "retried#2": {"model_calls_not_counted": 0},
        },
        results=[
            {
                "task_id": "retried",
                "problem_solving_cost": {
                    "status": "complete",
                    "model_calls": 2,
                    "usage": {
                        "input_tokens": 2 * IN_TOKENS,
                        "output_tokens": 2 * OUT_TOKENS,
                    },
                },
            }
        ],
    )

    one = compare(record)[0]
    assert one.attempts == (1, 2)
    assert one.voice_counted == 2
    assert one.agrees is True


def test_a_task_id_containing_a_hash_still_finds_its_conversation():
    """``held.as_dict()`` keys on ``task#attempt`` and task ids are not ours.

    Split from the left, this task's uncounted reply would be attributed to a
    task named ``odd``, and two tasks would be wrong at once.
    """
    record = a_record(
        per_attempt=[{"task_id": "odd#name", "attempt": 1, "calls": []}],
        conversations={"odd#name#1": {"model_calls_not_counted": 1}},
        results=[
            {
                "task_id": "odd#name",
                "problem_solving_cost": {"status": "partial", "model_calls": 1},
            }
        ],
    )

    one = compare(record)[0]
    assert one.task_id == "odd#name"
    assert one.not_counted == 1
    assert one.counts_agree is True


def test_an_empty_record_reports_nothing_rather_than_agreement():
    verdict = the_stop_rule({})
    assert verdict["tasks"] == 0
    assert verdict["agree"] is False


def test_the_verdict_says_when_it_can_fire(tmp_path):
    """So that the stopping rule is not read as a mid-run halt.

    A receipt exists only after a task settles, which is after the calls have
    been paid for. This reader catches a disagreement; it does not prevent the
    call that caused one.
    """
    _, _, _, record = one_task_through_everything(
        tmp_path, replies=[_Reply()], answers=[FINISHED]
    )
    verdict = the_stop_rule(record)
    assert "after a task settles" in verdict["when_this_can_fire"]
    assert "not a check that can stop the next call" in verdict["when_this_can_fire"]


def test_every_row_carries_its_own_sentence(tmp_path):
    _, _, _, record = one_task_through_everything(
        tmp_path, replies=[_Reply()], answers=[FINISHED]
    )
    row = compare(record)[0].as_row()
    assert row["task_id"] == "a-task"
    assert row["why"].startswith("a-task: ")
    assert set(row) >= {
        "voice_counted",
        "not_counted",
        "the_voice_accounts_for",
        "ledger_counted",
        "counts_agree",
        "tokens_agree",
        "agrees",
    }


@pytest.mark.parametrize("missing", ["model_calls", "conversations", "run"])
def test_a_half_written_record_is_read_rather_than_refused(tmp_path, missing):
    """A killed run leaves a partial record, and that is when this is wanted.

    A reader that raised on the shape would be one nobody could point at the
    run they actually have.
    """
    _, _, _, record = one_task_through_everything(
        tmp_path, replies=[_Reply()], answers=[FINISHED]
    )
    record.pop(missing)
    verdict = the_stop_rule(record)
    assert isinstance(verdict["agree"], bool)
