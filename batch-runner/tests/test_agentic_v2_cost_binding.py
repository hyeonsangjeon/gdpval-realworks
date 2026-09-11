"""The V2 cost binding, held to the two things it exists to prevent.

A zero that should have been a gap, and a bug of ours that reads as a flaky
sandbox. Both are the kind of error that looks like a clean result, which is why
they get tests rather than a comment.

Nothing here contacts a provider or boots anything. The ledger is a real SQLite
file in a temp directory; the price table is the committed one.
"""

from __future__ import annotations

import importlib
import sys
from decimal import Decimal

import pytest

from core.agentic_v2_contract import ERROR_TYPES
from core.agentic_v2_cost_binding import (
    DISPOSITION_AMBIGUOUS,
    DISPOSITION_RUNNER_DEFECT,
    DISPOSITION_TERMINAL_BUDGET,
    DISPOSITION_TERMINAL_CAPABILITY,
    DISPOSITION_TERMINAL_STOP,
    DISPOSITIONS,
    ERROR_DISPOSITION,
    GuestRuntime,
    ModelTurn,
    RETRYABLE_DISPOSITIONS,
    RUNTIME_KIND_MICROVM_GUEST,
    bind_run_to_ledger,
    describe_run_outcome,
    disposition_for_error,
    retry_kind_for_error,
)
from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    CallUsage,
    CostReceiptLedger,
    REASON_RUNTIME_UNPRICED,
    RETRY_INFRASTRUCTURE,
    RETRY_INTERNAL_RECOVERY,
    RETRY_NONE,
    RETRY_SEMANTIC,
    STAGE_GENERATION,
    STAGE_GRADING,
    STATUS_COMPLETE,
    STATUS_NOT_RUN,
    STATUS_PARTIAL,
    load_receipt_price_table,
)


@pytest.fixture
def ledger(tmp_path):
    book = CostReceiptLedger(
        tmp_path / "cost.sqlite3",
        run_id="test-run",
        price_table=load_receipt_price_table(),
    )
    yield book
    book.close()


def _turn(call_id="call-1", **overrides):
    fields = {
        "call_id": call_id,
        "usage": CallUsage(input_tokens=1000, output_tokens=200),
        "provider": "azure_openai",
        "requested_model": "gpt-5.4",
        "deployment": "gpt-5.4",
        "api_version": "2025-04-01-preview",
        "resolved_model": "gpt-5.4",
    }
    fields.update(overrides)
    return ModelTurn(**fields)


class TestEveryErrorIsClassifiedAndNoneByDefault:
    def test_the_map_covers_the_contract_exactly(self):
        assert set(ERROR_DISPOSITION) == set(ERROR_TYPES)

    def test_every_disposition_is_one_of_the_declared_ones(self):
        assert set(ERROR_DISPOSITION.values()) <= set(DISPOSITIONS)

    def test_an_unknown_error_raises_rather_than_defaulting(self):
        # A default is how a new failure mode ends up silently attributed to
        # whoever the default happened to name.
        with pytest.raises(ValueError, match="no recorded disposition"):
            disposition_for_error("a_failure_mode_nobody_has_seen")

    def test_none_and_nonsense_raise_too(self):
        for value in (None, 0, [], {}):
            with pytest.raises(ValueError):
                disposition_for_error(value)

    def test_the_import_guard_fires_when_the_contract_moves(self, monkeypatch):
        # The map is only total because something checks. Prove the check works
        # by giving the contract an error type nobody classified.
        import core.agentic_v2_contract as contract

        monkeypatch.setattr(
            contract, "ERROR_TYPES", (*ERROR_TYPES, "newly_invented_failure")
        )
        monkeypatch.delitem(sys.modules, "core.agentic_v2_cost_binding")
        with pytest.raises(RuntimeError, match="out of step with the contract"):
            importlib.import_module("core.agentic_v2_cost_binding")


class TestOurOwnBugsDoNotReadAsAFlakySandbox:
    """Seven error types only this code can produce."""

    DEFECTS = (
        "runner_internal_error",
        "invalid_backend_result",
        "invalid_backend_state",
        "invalid_result_envelope",
        "invalid_lifecycle_transition",
        "finalize_result_mismatch",
        "finalize_result_missing",
    )

    @pytest.mark.parametrize("error", DEFECTS)
    def test_a_runner_defect_is_not_infrastructure(self, error):
        assert disposition_for_error(error) == DISPOSITION_RUNNER_DEFECT
        assert disposition_for_error(error) != RETRY_INFRASTRUCTURE

    @pytest.mark.parametrize("error", DEFECTS)
    def test_a_runner_defect_gets_no_retry(self, error):
        # Retrying changes nothing until the code changes.
        assert retry_kind_for_error(error) is None

    @pytest.mark.parametrize("error", DEFECTS)
    def test_it_says_plainly_whose_fault_it_is(self, error):
        described = describe_run_outcome({"success": False, "error": error})
        assert described["attributable_to"] == "this runner"


class TestTheUndecidableCaseStaysUndecided:
    def test_a_wall_clock_running_out_is_not_assigned_to_either_side(self):
        assert disposition_for_error("task_wall_time_exhausted") == (
            DISPOSITION_AMBIGUOUS
        )

    def test_it_is_not_quietly_counted_as_an_environment_fault(self):
        described = describe_run_outcome(
            {"success": False, "error": "task_wall_time_exhausted"}
        )
        assert described["attributable_to"] == "undecidable from the error alone"
        assert described["retry_kind_for_next_attempt"] is None

    def test_exactly_one_error_is_ambiguous(self):
        # If this grows, somebody has given up on classifying rather than
        # thought harder, and that should be a visible decision.
        ambiguous = [
            error for error, value in ERROR_DISPOSITION.items()
            if value == DISPOSITION_AMBIGUOUS
        ]
        assert ambiguous == ["task_wall_time_exhausted"]


class TestTheThreeRetryKindsMeanWhatReadinessReadsThemAs:
    @pytest.mark.parametrize(
        "error,expected",
        [
            ("compute_start_failed", RETRY_INFRASTRUCTURE),
            ("compute_backend_error", RETRY_INFRASTRUCTURE),
            ("invalid_arguments", RETRY_SEMANTIC),
            ("finalize_not_called", RETRY_SEMANTIC),
            ("call_id_conflict", RETRY_INTERNAL_RECOVERY),
        ],
    )
    def test_it_returns_a_kind_the_ledger_accepts(self, error, expected):
        assert retry_kind_for_error(error) == expected

    @pytest.mark.parametrize(
        "error",
        ["tool_budget_exhausted", "cancelled", "capability_unavailable",
         "task_wall_time_exhausted", "runner_internal_error"],
    )
    def test_terminal_endings_get_no_retry_kind(self, error):
        assert retry_kind_for_error(error) is None

    def test_a_model_asking_wrongly_is_the_model(self):
        described = describe_run_outcome(
            {"success": False, "error": "unknown_tool"}
        )
        assert described["attributable_to"] == "model"

    def test_a_declared_absence_is_not_a_fault(self):
        described = describe_run_outcome(
            {"success": False, "error": "capability_unavailable"}
        )
        assert described["disposition"] == DISPOSITION_TERMINAL_CAPABILITY
        assert "declared absence rather than a fault" in (
            described["attributable_to"]
        )

    def test_a_budget_and_a_stop_blame_nobody(self):
        for error, disposition in (
            ("tool_budget_exhausted", DISPOSITION_TERMINAL_BUDGET),
            ("cancelled", DISPOSITION_TERMINAL_STOP),
        ):
            described = describe_run_outcome({"success": False, "error": error})
            assert described["disposition"] == disposition
            assert described["attributable_to"].startswith("neither")

    def test_success_says_so_rather_than_leaving_a_key_out(self):
        described = describe_run_outcome({"success": True})
        assert described["succeeded"] is True
        assert described["disposition"] is None
        assert described["attributable_to"] is None


class TestGuestTimeIsUnpricedAndThatIsRecordedAsAGapNotAsZero:
    """The headline requirement: a host whose bill is unreadable is not free."""

    def test_the_runtime_kind_is_not_in_the_price_table(self):
        table = load_receipt_price_table()
        assert table.runtime(RUNTIME_KIND_MICROVM_GUEST) is None, (
            "if a price has been added for the guest, this test's premise is "
            "gone -- update it deliberately rather than deleting it"
        )

    def test_the_runtime_row_carries_no_amount_and_says_why(self, ledger):
        bind_run_to_ledger(
            ledger,
            task_id="task-1",
            guest_runtime=GuestRuntime(entry_id="guest-1", seconds=11.775),
        )
        rows = ledger._connection.execute(
            "SELECT * FROM cost_runtime WHERE task_id = 'task-1'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["runtime_cost_usd"] is None
        assert REASON_RUNTIME_UNPRICED in rows[0]["missing_reasons"]

    def test_the_receipt_is_partial_and_not_a_clean_zero(self, ledger):
        bind_run_to_ledger(
            ledger,
            task_id="task-1",
            model_turns=[_turn()],
            guest_runtime=GuestRuntime(entry_id="guest-1", seconds=11.775),
        )
        receipt = ledger.receipt_for("task-1", BUCKET_PROBLEM_SOLVING)
        assert receipt.status == STATUS_PARTIAL
        assert receipt.status != STATUS_COMPLETE

    def test_a_measured_figure_is_used_when_there_is_one(self, ledger):
        # Under-claiming is the default, not the rule. A caller that has really
        # measured the bill gets to record it.
        bind_run_to_ledger(
            ledger,
            task_id="task-2",
            guest_runtime=GuestRuntime(
                entry_id="guest-2", seconds=600.0, usd=Decimal("0.0641")
            ),
        )
        row = ledger._connection.execute(
            "SELECT * FROM cost_runtime WHERE task_id = 'task-2'"
        ).fetchone()
        assert Decimal(row["runtime_cost_usd"]) == Decimal("0.0641")

    def test_seconds_without_a_price_never_become_a_derived_amount(self, ledger):
        # The tempting bug: multiply seconds by a rate somebody half-remembers.
        bind_run_to_ledger(
            ledger,
            task_id="task-3",
            guest_runtime=GuestRuntime(entry_id="guest-3", seconds=3600.0),
        )
        row = ledger._connection.execute(
            "SELECT * FROM cost_runtime WHERE task_id = 'task-3'"
        ).fetchone()
        assert row["runtime_cost_usd"] is None


class TestProblemSolvingCostStaysApartFromGrading:
    def test_a_grading_stage_is_refused(self, ledger):
        with pytest.raises(ValueError, match="problem-solving cost"):
            bind_run_to_ledger(
                ledger, task_id="task-1", model_turns=[_turn()],
                stage=STAGE_GRADING,
            )

    def test_nothing_is_written_to_the_grading_bucket(self, ledger):
        bind_run_to_ledger(
            ledger,
            task_id="task-1",
            model_turns=[_turn()],
            guest_runtime=GuestRuntime(entry_id="guest-1", seconds=1.0),
        )
        grading = ledger.receipt_for("task-1", BUCKET_GRADING)
        # not_run, not a $0 complete: this task has not been graded, which is a
        # different sentence from "grading was free".
        assert grading.status == STATUS_NOT_RUN
        assert grading.model_calls == 0
        assert ledger.calls_for("task-1", bucket=BUCKET_GRADING) == []

    def test_the_default_stage_buckets_as_problem_solving(self, ledger):
        written = bind_run_to_ledger(
            ledger, task_id="task-1", model_turns=[_turn()]
        )
        assert written["bucket"] == BUCKET_PROBLEM_SOLVING


class TestTheCallsThemselvesLandWhereTheLedgerExpects:
    def test_a_turn_is_reserved_and_settled(self, ledger):
        written = bind_run_to_ledger(
            ledger, task_id="task-1", model_turns=[_turn()]
        )
        assert written["settled_call_ids"] == ["call-1"]
        calls = ledger.calls_for("task-1", bucket=BUCKET_PROBLEM_SOLVING)
        assert len(calls) == 1
        assert calls[0]["state"] == "settled"

    def test_a_first_attempt_is_not_recorded_as_a_retry(self, ledger):
        bind_run_to_ledger(ledger, task_id="task-1", model_turns=[_turn()])
        calls = ledger.calls_for("task-1", bucket=BUCKET_PROBLEM_SOLVING)
        assert calls[0]["retry_kind"] == RETRY_NONE

    def test_a_retry_carries_the_kind_the_previous_error_earned(self, ledger):
        kind = retry_kind_for_error("compute_start_failed")
        bind_run_to_ledger(
            ledger,
            task_id="task-1",
            model_turns=[
                _turn("call-1"),
                _turn("call-2", retry_kind=kind),
            ],
        )
        kinds = {
            call["call_id"]: call["retry_kind"]
            for call in ledger.calls_for("task-1", bucket=BUCKET_PROBLEM_SOLVING)
        }
        assert kinds == {"call-1": RETRY_NONE, "call-2": RETRY_INFRASTRUCTURE}

    def test_a_run_with_no_turns_still_records_its_guest_time(self, ledger):
        # A task that died before reaching the model is not a task that cost
        # nothing; an absent row reads as free.
        written = bind_run_to_ledger(
            ledger,
            task_id="task-1",
            guest_runtime=GuestRuntime(entry_id="guest-1", seconds=2.5),
        )
        assert written["settled_call_ids"] == []
        assert written["runtime_entry_id"] == "guest-1"
        assert ledger.receipt_for("task-1", BUCKET_PROBLEM_SOLVING).status == (
            STATUS_PARTIAL
        )


class TestTheDispositionsAreDistinctFromTheRetryKinds:
    def test_the_retryable_set_is_exactly_the_ledger_three(self):
        assert set(RETRYABLE_DISPOSITIONS) == {
            RETRY_INFRASTRUCTURE, RETRY_SEMANTIC, RETRY_INTERNAL_RECOVERY
        }

    def test_no_terminal_disposition_leaks_into_a_retry_kind(self):
        for error in ERROR_TYPES:
            kind = retry_kind_for_error(error)
            assert kind is None or kind in RETRYABLE_DISPOSITIONS
