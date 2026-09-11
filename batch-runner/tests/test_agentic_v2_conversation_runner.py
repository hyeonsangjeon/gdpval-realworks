"""Whether a model can drive a real V2 run, and be billed for it correctly.

Every test here uses :class:`~core.agentic_v2_conversation.ScriptedVoice` and
:class:`~core.agentic_v2_fixture_backend.AgenticV2FixtureBackend`. No model is
called, no guest is booted, nothing is spent, and ``foundation_only`` stays on
throughout — the ``exec_run`` refusal is not worked around in these tests, it is
one of the things they check.

What is proved here is the shape of the join, not the behaviour of a real model.
A stand-in that always says the same thing cannot show that a model *would*
choose well. It can show that when something chooses, the choice goes through
the same dispatcher, lands in the same hash chains, produces the same verified
envelope, and reaches the ledger under an id that will not collide with another
task's.
"""

from __future__ import annotations

import pytest

from core.agentic_v2_conversation import (
    AskForTool,
    GaveUp,
    LoopLimits,
    ScriptedVoice,
    StopReason,
)
from core.agentic_v2_conversation_runner import (
    ConversationRunnerRefused,
    PerTaskCeilings,
    RunWideCeilings,
    TaskConversations,
    build_runner_factory,
    conversation_seam,
    model_turns_of,
)
from core.agentic_v2_cost_binding import bind_run_to_ledger
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_provenance import verify_agentic_v2_result
from core.agentic_v2_runner import AgenticV2ScriptedRunner
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    CostReceiptLedger,
    RETRY_NONE,
    load_receipt_price_table,
)


PROFILE = {
    "tool_contract_version": "2.0",
    "policy_profile_id": "offline-full-v1",
    "foundation_only": True,
}

CEILINGS = PerTaskCeilings(
    max_model_turns=8,
    max_written_tokens_per_turn=4096,
    max_seconds=60.0,
    max_model_calls=8,
    max_input_tokens=100_000,
    max_output_tokens=20_000,
    max_repeats_of_one_request=2,
)


def _write(call_id="w-1", path="report.txt", content="the answer", **counts):
    return AskForTool(
        call_id=call_id,
        tool_name="workspace_apply",
        arguments={"operation": "write", "path": path, "content": content},
        why="write the deliverable",
        **counts,
    )


def _finalize(call_id="f-1", deliverables=("report.txt",), **counts):
    return AskForTool(
        call_id=call_id,
        tool_name="finalize",
        arguments={"deliverables": list(deliverables), "summary": "done"},
        why="hand it in",
        **counts,
    )


def _backend_factory(tmp_path):
    return lambda **kwargs: AgenticV2FixtureBackend(root=tmp_path, **kwargs)


def _run(tmp_path, replies, *, task_id="task-1", conversations=None, **kwargs):
    """One conversation-driven run, returning the envelope and the outcome."""
    held = conversations if conversations is not None else TaskConversations(CEILINGS)
    limits = held.limits_for(task_id, 1)
    voice = ScriptedVoice(replies=list(replies))
    runner = AgenticV2ScriptedRunner(
        backend_factory=_backend_factory(tmp_path),
        conversation=conversation_seam(
            voice=voice,
            limits=limits,
            on_outcome=lambda outcome: held.record(task_id, 1, outcome),
        ),
        profile=PROFILE,
        **kwargs,
    )
    result = runner.run("Write the report", task_id=task_id)
    return result, held.outcome_of(task_id, 1), held


# ── a model drives a real run ────────────────────────────────────────────


class TestTheModelDrivesTheRun:
    def test_a_conversation_produces_a_successful_run(self, tmp_path):
        result, outcome, _ = _run(tmp_path, [_write(), _finalize()])
        assert result["success"] is True
        assert outcome.stop_reason is StopReason.FINISHED_NORMALLY
        assert [file["filename"] for file in result["files"]] == ["report.txt"]

    def test_the_file_the_model_wrote_is_the_file_that_comes_back(self, tmp_path):
        result, _, _ = _run(
            tmp_path, [_write(content="ninety-four percent"), _finalize()]
        )
        assert result["files"][0]["content"] == b"ninety-four percent"

    def test_a_conversation_driven_run_verifies(self, tmp_path):
        """The same check every scripted run passes, with a model choosing."""
        result, _, _ = _run(tmp_path, [_write(), _finalize()])
        verify_agentic_v2_result(result)

    def test_the_envelope_carries_no_extra_key_for_the_conversation(self, tmp_path):
        result, _, _ = _run(tmp_path, [_write(), _finalize()])
        assert set(result) == {
            "success",
            "text",
            "deliverable_text",
            "files",
            "agentic_v2",
        }

    def test_the_run_is_still_foundation_only(self, tmp_path):
        result, _, _ = _run(tmp_path, [_write(), _finalize()])
        assert result["agentic_v2"]["foundation_only"] is True


# ── the model's calls go through the runner's bookkeeping ────────────────


class TestNothingReachesPastTheRunner:
    def test_the_model_s_calls_are_in_the_hash_chains(self, tmp_path):
        """A desk holding the dispatcher directly would leave these empty."""
        result, _, _ = _run(tmp_path, [_write(), _finalize()])
        events = result["agentic_v2"]["public_trace"]["events"]
        kinds = [entry["kind"] for entry in events]
        assert kinds.count("tool_result_public") == 2

    def test_the_chain_commits_a_state_for_each_call(self, tmp_path):
        result, _, _ = _run(tmp_path, [_write(), _finalize()])
        for entry in result["agentic_v2"]["public_trace"]["events"]:
            if entry["kind"] == "tool_result_public":
                assert len(entry["state_sha256"]) == 64

    def test_the_private_and_public_traces_agree_in_length(self, tmp_path):
        result, _, _ = _run(tmp_path, [_write(), _finalize()])
        block = result["agentic_v2"]
        assert len(block["private_audit"]["events"]) == len(
            block["public_trace"]["events"]
        )

    def test_the_trace_head_is_a_digest(self, tmp_path):
        result, _, _ = _run(tmp_path, [_write(), _finalize()])
        head = result["agentic_v2"]["public_trace"]["event_chain_head_sha256"]
        assert len(head) == 64


# ── a failed tool call ends the run, because the trace schema says so ────


class TestAFailedToolEndsTheRun:
    """The loop would let a model recover from a tool error. The trace cannot.

    :func:`~core.agentic_v2_provenance.verify_agentic_v2_result` refuses any
    trace in which a tool event follows a tool result with ``ok`` false, so a
    run that kept going after a failure would build a record of itself that
    cannot be verified. The runner therefore stops on the failure, and these
    tests pin both halves of that: that it stops, and that it says *why* in the
    tool's own words.

    The cost is real and is not hidden: under this schema a model gets one tool
    mistake per task. Lifting that means changing the trace schema.
    """

    BAD = AskForTool(
        call_id="x-1",
        tool_name="exec_run",
        arguments={"command": ["echo", "hi"]},
        why="try to run something",
    )

    def test_the_run_ends_on_the_failed_call(self, tmp_path):
        result, _, _ = _run(tmp_path, [self.BAD, _write(), _finalize()])
        assert result["success"] is False

    def test_the_error_is_the_tool_s_own_and_not_a_runner_defect(self, tmp_path):
        """The property that matters for a 220-task run.

        If this said ``runner_internal_error`` the ledger would bucket a model's
        bad arguments as this harness being broken, and the run's failure counts
        would describe the wrong thing entirely.
        """
        result, _, _ = _run(tmp_path, [self.BAD, _write(), _finalize()])
        assert result["error"] == "invalid_arguments"
        assert result["error"] != "runner_internal_error"

    def test_the_later_replies_were_never_asked_for(self, tmp_path):
        """Proof the run really stopped rather than finishing quietly."""
        voice = ScriptedVoice(replies=[self.BAD, _write(), _finalize()])
        held = TaskConversations(CEILINGS)
        AgenticV2ScriptedRunner(
            backend_factory=_backend_factory(tmp_path),
            conversation=conversation_seam(
                voice=voice, limits=held.limits_for("task-1", 1)
            ),
            profile=PROFILE,
        ).run("Write the report", task_id="task-1")
        assert len(voice.requests_seen) == 1

    def test_no_tool_event_follows_the_failed_one(self, tmp_path):
        """The trace invariant, checked on the trace this run produced."""
        result, _, _ = _run(tmp_path, [self.BAD, _write(), _finalize()])
        kinds = [
            entry["kind"]
            for entry in result["agentic_v2"]["public_trace"]["events"]
        ]
        assert kinds.count("tool_result_public") == 1
        assert kinds[-1] == "failure"

    def test_a_scripted_run_ends_the_same_way_on_the_same_call(self, tmp_path):
        """Both call sources obey one rule, so one reading of the record works."""
        result = AgenticV2ScriptedRunner(
            backend_factory=_backend_factory(tmp_path),
            scripted_calls=[
                {
                    "call_id": "x-1",
                    "name": "exec_run",
                    "arguments": {"command": ["echo", "hi"]},
                }
            ],
            profile=PROFILE,
        ).run("Write the report", task_id="task-1")
        assert result["success"] is False
        assert result["error"] == "invalid_arguments"


# ── a conversation that never commits an answer ──────────────────────────


class TestAConversationThatStops:
    def test_a_model_that_walks_away_is_not_a_success(self, tmp_path):
        result, outcome, _ = _run(tmp_path, [GaveUp(note="not sure how")])
        assert result["success"] is False
        assert outcome.produced_an_answer is False

    def test_walking_away_is_reported_as_finalize_not_called(self, tmp_path):
        result, _, _ = _run(tmp_path, [GaveUp(note="not sure how")])
        assert result["error"] == "finalize_not_called"

    def test_a_model_that_writes_but_never_finalizes_is_not_a_success(
        self, tmp_path
    ):
        result, _, _ = _run(tmp_path, [_write(), GaveUp(note="done enough")])
        assert result["success"] is False
        assert result["error"] == "finalize_not_called"

    def test_a_cancelled_conversation_is_reported_as_cancelled(self, tmp_path):
        result, _, _ = _run(
            tmp_path,
            [_write(), _finalize()],
            cancel_requested=lambda: True,
        )
        assert result["success"] is False
        assert result["error"] == "cancelled"

    def test_a_cancelled_run_is_not_called_a_runner_defect(self, tmp_path):
        """The conversation loop reports a thrown desk as broken; it is not."""
        result, outcome, _ = _run(
            tmp_path,
            [_write(), _finalize()],
            cancel_requested=lambda: True,
        )
        assert outcome.stop_reason is StopReason.TOOL_DESK_BROKE
        assert result["error"] != "runner_internal_error"


# ── one call source, not two ─────────────────────────────────────────────


class TestOneCallSource:
    def test_a_script_and_a_model_together_are_refused(self, tmp_path):
        with pytest.raises(ValueError, match="script or by a model"):
            AgenticV2ScriptedRunner(
                backend_factory=_backend_factory(tmp_path),
                scripted_calls=[{"call_id": "c-1", "name": "finalize"}],
                conversation=lambda prompt, dispatch: None,
                profile=PROFILE,
            )

    def test_a_conversation_that_is_not_callable_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="must be callable"):
            AgenticV2ScriptedRunner(
                backend_factory=_backend_factory(tmp_path),
                conversation="ask the model",
                profile=PROFILE,
            )

    def test_a_scripted_run_still_works_unchanged(self, tmp_path):
        """The seam is an addition; the old call source must be untouched."""
        result = AgenticV2ScriptedRunner(
            backend_factory=_backend_factory(tmp_path),
            scripted_calls=[
                {
                    "call_id": "w-1",
                    "name": "workspace_apply",
                    "arguments": {
                        "operation": "write",
                        "path": "report.txt",
                        "content": "scripted",
                    },
                },
                {
                    "call_id": "f-1",
                    "name": "finalize",
                    "arguments": {
                        "deliverables": ["report.txt"],
                        "summary": "done",
                    },
                },
            ],
            profile=PROFILE,
        ).run("Write the report", task_id="task-1")
        assert result["success"] is True


# ── ceilings ─────────────────────────────────────────────────────────────


class TestCeilings:
    def test_fresh_limits_are_complete(self):
        assert CEILINGS.fresh_limits().whats_missing() == []

    def test_each_task_gets_a_budget_that_has_spent_nothing(self):
        held = TaskConversations(CEILINGS)
        first = held.limits_for("task-1", 1)
        first.budget.record(input_tokens=500, output_tokens=100)
        second = held.limits_for("task-2", 1)
        assert second.budget.input_tokens_used == 0
        assert first.budget is not second.budget

    def test_the_run_wide_total_sums_every_task(self):
        held = TaskConversations(CEILINGS)
        for task_id in ("task-1", "task-2"):
            held.limits_for(task_id, 1).budget.record(
                input_tokens=500, output_tokens=100
            )
        assert held.spent == {
            "model_calls": 2,
            "input_tokens": 1000,
            "output_tokens": 200,
        }

    def test_a_retried_task_s_first_attempt_is_not_lost(self):
        held = TaskConversations(CEILINGS)
        held.limits_for("task-1", 1).budget.record(
            input_tokens=500, output_tokens=100
        )
        held.limits_for("task-1", 2).budget.record(
            input_tokens=700, output_tokens=200
        )
        assert held.spent["input_tokens"] == 1200
        assert len(held.budgets) == 2

    def test_a_run_under_its_ceiling_may_start_the_next_task(self):
        held = TaskConversations(CEILINGS, RunWideCeilings(max_model_calls=10))
        held.limits_for("task-1", 1).budget.record(
            input_tokens=1, output_tokens=1
        )
        assert held.run_wide_refusal() is None

    def test_a_run_at_its_ceiling_refuses_the_next_task(self):
        held = TaskConversations(CEILINGS, RunWideCeilings(max_model_calls=1))
        held.limits_for("task-1", 1).budget.record(
            input_tokens=1, output_tokens=1
        )
        assert "max_model_calls" in (held.run_wide_refusal() or "")

    def test_an_unset_run_wide_ceiling_never_refuses(self):
        held = TaskConversations(CEILINGS)
        for index in range(5):
            held.limits_for(f"task-{index}", 1).budget.record(
                input_tokens=10_000, output_tokens=1_000
            )
        assert held.run_wide_refusal() is None


# ── the factory the driver uses ──────────────────────────────────────────


class TestTheRunnerFactory:
    def _task(self, task_id="task-1"):
        from core.agentic_v2_run_driver import TaskToRun

        return TaskToRun(
            task_id=task_id,
            prompt="Write the report",
            occupation="Analyst",
            sector="Finance",
        )

    def _factory(self, tmp_path, held, replies=None):
        return build_runner_factory(
            backend_factory=_backend_factory(tmp_path),
            profile=PROFILE,
            voice=ScriptedVoice(
                replies=list(replies if replies is not None else [_write(), _finalize()])
            ),
            conversations=held,
            attempt_of=lambda task_id: 1,
        )

    def test_the_factory_builds_a_runner_that_runs(self, tmp_path):
        held = TaskConversations(CEILINGS)
        runner = self._factory(tmp_path, held)(self._task())
        result = runner.run("Write the report", task_id="task-1")
        assert result["success"] is True

    def test_the_outcome_is_kept_beside_the_run(self, tmp_path):
        held = TaskConversations(CEILINGS)
        self._factory(tmp_path, held)(self._task()).run(
            "Write the report", task_id="task-1"
        )
        assert held.outcome_of("task-1", 1).stop_reason is StopReason.FINISHED_NORMALLY
        assert held.attempts_of("task-1") == (1,)

    def test_a_factory_with_neither_voice_is_refused(self, tmp_path):
        with pytest.raises(ConversationRunnerRefused, match="exactly one"):
            build_runner_factory(
                backend_factory=_backend_factory(tmp_path),
                profile=PROFILE,
                conversations=TaskConversations(CEILINGS),
                attempt_of=lambda task_id: 1,
            )

    def test_a_factory_with_both_voices_is_refused(self, tmp_path):
        """Not a style objection. The two disagree about which budget is real.

        ``voice`` carries whatever budget it was built with and ``voice_for``
        is handed the task's own; a factory holding both would use one and
        quietly drop the other, and which one it dropped would only show up in
        the bill.
        """
        with pytest.raises(ConversationRunnerRefused, match="exactly one"):
            build_runner_factory(
                backend_factory=_backend_factory(tmp_path),
                profile=PROFILE,
                voice=ScriptedVoice(replies=[_finalize()]),
                voice_for=lambda budget: ScriptedVoice(replies=[_finalize()]),
                conversations=TaskConversations(CEILINGS),
                attempt_of=lambda task_id: 1,
            )

    def test_each_task_gets_a_voice_built_on_its_own_budget(self, tmp_path):
        """The reason ``voice_for`` exists, stated as an assertion.

        A paid voice holds a budget and refuses before the call that would pass
        it. If the run built one voice and reused it, task 220 would be refused
        by task 1's spending. Here each task's voice must receive *that task's*
        budget object — the same one the loop charges — so the two ceilings are
        one number rather than two that drift.
        """
        held = TaskConversations(CEILINGS)
        handed: list[StageOneBudget] = []

        def voice_for(budget):
            handed.append(budget)
            return ScriptedVoice(replies=[_write(), _finalize()])

        factory = build_runner_factory(
            backend_factory=_backend_factory(tmp_path),
            profile=PROFILE,
            voice_for=voice_for,
            conversations=held,
            attempt_of=lambda task_id: 1,
        )
        for task_id in ("task-1", "task-2", "task-3"):
            factory(self._task(task_id)).run("Write the report", task_id=task_id)

        assert len(handed) == 3
        assert len({id(budget) for budget in handed}) == 3, (
            "three tasks were handed the same budget object, which is the "
            "sharing this argument exists to prevent"
        )
        for task_id, budget in zip(("task-1", "task-2", "task-3"), handed):
            assert held.budgets[(task_id, 1)] is budget, (
                "the voice was built on a budget the loop does not charge, so "
                "the voice's ceiling and the run's accounting are two "
                "different numbers"
            )

    def test_a_voice_for_that_returns_nothing_is_refused(self, tmp_path):
        factory = build_runner_factory(
            backend_factory=_backend_factory(tmp_path),
            profile=PROFILE,
            voice_for=lambda budget: None,
            conversations=TaskConversations(CEILINGS),
            attempt_of=lambda task_id: 1,
        )
        with pytest.raises(ConversationRunnerRefused, match="no way to ask a model"):
            factory(self._task())

    def test_a_spent_run_refuses_before_a_guest_is_booted(self, tmp_path):
        held = TaskConversations(CEILINGS, RunWideCeilings(max_model_calls=1))
        held.limits_for("task-0", 1).budget.record(
            input_tokens=1, output_tokens=1
        )
        with pytest.raises(ConversationRunnerRefused, match="run-wide"):
            self._factory(tmp_path, held)(self._task())

    def test_the_record_survives_being_turned_into_a_dict(self, tmp_path):
        held = TaskConversations(CEILINGS)
        self._factory(tmp_path, held)(self._task()).run(
            "Write the report", task_id="task-1"
        )
        record = held.as_dict()
        assert record["conversations"]["task-1#1"]["produced_an_answer"] is True
        assert record["per_task_ceilings"]["max_model_turns"] == 8


# ── what the conversation costs, in the ledger ───────────────────────────


@pytest.fixture
def ledger(tmp_path):
    book = CostReceiptLedger(
        tmp_path / "cost.sqlite3",
        run_id="test-run",
        price_table=load_receipt_price_table(),
    )
    yield book
    book.close()


class TestTheConversationReachesTheLedger:
    def _outcome(self, tmp_path, task_id="task-1"):
        _, outcome, _ = _run(
            tmp_path,
            [
                _write(input_tokens=1000, output_tokens=200),
                _finalize(input_tokens=1500, output_tokens=120),
            ],
            task_id=task_id,
        )
        return outcome

    def _turns(self, outcome, **overrides):
        fields = {
            "run_id": "run-a",
            "task_id": "task-1",
            "attempt": 1,
            # "azure", not "azure_openai": the price table keys on
            # ``provider:resolved_model`` and does no prefix matching, so a
            # provider spelt another way prices nothing at all.
            "provider": "azure",
            "requested_model": "gpt-5.4",
        }
        fields.update(overrides)
        return model_turns_of(outcome, **fields)

    def test_every_turn_becomes_a_ledger_entry(self, tmp_path):
        turns = self._turns(self._outcome(tmp_path))
        assert len(turns) == 2

    def test_the_counts_are_the_ones_the_provider_reported(self, tmp_path):
        turns = self._turns(self._outcome(tmp_path))
        assert turns[0].usage.input_tokens == 1000
        assert turns[1].usage.output_tokens == 120

    def test_no_count_is_a_zero_standing_in_for_an_unknown(self, tmp_path):
        """The loop refuses a reply it cannot charge for, so this holds."""
        turns = self._turns(self._outcome(tmp_path))
        assert all(turn.usage.input_tokens is not None for turn in turns)

    def test_call_ids_from_different_tasks_do_not_collide(self, tmp_path):
        first = self._turns(
            self._outcome(tmp_path / "a", "task-1"), task_id="task-1"
        )
        second = self._turns(
            self._outcome(tmp_path / "b", "task-2"), task_id="task-2"
        )
        assert {turn.call_id for turn in first} & {
            turn.call_id for turn in second
        } == set()

    def test_call_ids_from_two_attempts_do_not_collide(self, tmp_path):
        outcome = self._outcome(tmp_path)
        first = self._turns(outcome, attempt=1)
        second = self._turns(outcome, attempt=2, preceding_error="finalize_not_called")
        assert {turn.call_id for turn in first} & {
            turn.call_id for turn in second
        } == set()

    def test_a_first_attempt_carries_no_retry_kind(self, tmp_path):
        turns = self._turns(self._outcome(tmp_path))
        assert all(turn.retry_kind == RETRY_NONE for turn in turns)

    def test_a_retry_is_billed_as_a_retry(self, tmp_path):
        turns = self._turns(
            self._outcome(tmp_path), preceding_error="finalize_not_called"
        )
        assert all(turn.retry_kind != RETRY_NONE for turn in turns)

    def test_an_attempt_that_should_not_have_happened_is_refused(self, tmp_path):
        """``cancelled`` has no next attempt, so there is no kind to file it
        under and inventing ``retry_none`` would hide a broken retry rule."""
        with pytest.raises(ConversationRunnerRefused, match="no next attempt"):
            self._turns(self._outcome(tmp_path), preceding_error="cancelled")

    def test_the_turns_settle_into_the_ledger(self, tmp_path, ledger):
        written = bind_run_to_ledger(
            ledger,
            task_id="task-1",
            model_turns=self._turns(self._outcome(tmp_path)),
        )
        assert len(written["settled_call_ids"]) == 2
        receipt = ledger.receipt_for("task-1", BUCKET_PROBLEM_SOLVING)
        assert receipt.model_cost_usd is not None
        assert receipt.model_cost_usd > 0

    def test_a_model_with_no_price_settles_as_partial_and_not_as_zero(
        self, tmp_path, ledger
    ):
        """The conversation's calls happened; what they cost is unknown.

        A run whose model is missing from the price table must not report a
        tidy ``$0``. Zero is a claim that the calls were free, and they were
        not — the receipt has to say it does not know. Written down here
        because the join is where a 220-task run acquires its cost, and a
        silent zero across 220 tasks is the shape of an unnoticed bill.
        """
        turns = self._turns(
            self._outcome(tmp_path), requested_model="a-model-nobody-priced"
        )
        bind_run_to_ledger(ledger, task_id="task-1", model_turns=turns)
        receipt = ledger.receipt_for("task-1", BUCKET_PROBLEM_SOLVING)
        assert receipt.status == "partial"
        assert "price_missing" in receipt.missing_reasons

    def test_the_conversation_lands_in_the_problem_solving_bucket(
        self, tmp_path, ledger
    ):
        """A task run is not grading, and the two totals stay apart."""
        written = bind_run_to_ledger(
            ledger,
            task_id="task-1",
            model_turns=self._turns(self._outcome(tmp_path)),
        )
        assert written["bucket"] == BUCKET_PROBLEM_SOLVING

    def test_an_empty_conversation_produces_no_entries(self, tmp_path):
        _, outcome, _ = _run(tmp_path, [GaveUp(note="nothing to do")])
        assert self._turns(outcome) == ()
