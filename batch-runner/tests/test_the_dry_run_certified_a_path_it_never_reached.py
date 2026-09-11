"""The dry run certified a path it had never reached.

On 2026-09-11 the first paid ``advance_check_5`` dispatch passed the OIDC
identity check, the route check, the deployment check and the cohort binding,
printed its run id and where it would write, and then died:

    TypeError: CostReceiptLedger.__init__() missing 1 required keyword-only
    argument: 'run_id'

Four minutes earlier a dry run of the same stage had finished with "Every
condition for the paid run is met". Both sentences were produced by the same
script. The dry run returned several hundred lines above the line that broke,
so the branch it was speaking for had never been executed -- not in CI, not in
a test, not once.

The signature fix is one keyword. These tests are about the other half: that
the free job now reaches the paid run's setup, and that the sentence it prints
says what it checked rather than what it hoped.

One thing worth keeping, because it changes what the lesson is. mypy had this.
Run against the pre-fix file it says, at the exact line:

    scripts/run_agentic_v2_stage.py:859: error: Missing named argument "run_id"
    for "CostReceiptLedger"  [call-arg]

It was the fourth of ninety-three errors across twenty-two files, and nothing
in CI type-checks ``scripts/``. So the defect was not invisible; it was sitting
in output nobody reads because the output is mostly noise. These tests close
the one hole. The wider fix -- a type check this script actually has to pass --
is its own change and is not in this one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

SCRIPTS = BATCH_RUNNER_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_agentic_v2_stage as stage  # noqa: E402
from core.cost_receipts import CostReceiptLedger  # noqa: E402


# ── the line that broke ───────────────────────────────────────────────────


def test_the_ledger_opens_with_the_arguments_the_paid_run_gives_it(tmp_path):
    """The whole of the original defect, in one call.

    Against the real class, not a double. A double with a forgiving signature
    is how the paid path passed review while being uncallable.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")

    assert isinstance(ledger, CostReceiptLedger)
    assert ledger.run_id == "a-run"
    assert (tmp_path / "cost_receipts.sqlite3").exists()
    ledger.close()


def test_the_ledger_carries_the_run_id_rather_than_defaulting_to_something():
    """``run_id`` is required, and that is the right shape for it.

    A ledger that invented its own run id would have made this call keep
    working and put every shard's rows under a name nobody chose.
    """
    import inspect

    parameter = inspect.signature(CostReceiptLedger.__init__).parameters["run_id"]

    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


# ── the free job now reaches it ───────────────────────────────────────────


def test_the_dry_run_opens_the_ledger_the_paid_run_will_write_to(tmp_path):
    """The check that makes the failure free instead of paid."""
    assert stage.the_paid_setup_a_dry_run_can_reach("advance_check_5") == []


def test_a_broken_ledger_is_a_problem_the_dry_run_reports(monkeypatch):
    """The same TypeError, arriving in the job that costs nothing.

    Had this existed on 2026-09-11 the paid dispatch would not have been made:
    the dry run ahead of it would have gone red.
    """

    def cannot_be_opened(into, *, run_id):
        raise TypeError("missing 1 required keyword-only argument: 'run_id'")

    monkeypatch.setattr(stage, "open_the_ledger", cannot_be_opened)

    problems = stage.the_paid_setup_a_dry_run_can_reach("advance_check_5")

    assert len(problems) == 1
    assert "cost ledger cannot be opened" in problems[0]


def test_the_scratch_directory_does_not_survive_the_check(monkeypatch):
    """A dry run writes nothing that outlives it, ledger included."""
    seen: list[Path] = []

    real = stage.open_the_ledger

    def remember(into, *, run_id):
        seen.append(Path(into))
        return real(into, run_id=run_id)

    monkeypatch.setattr(stage, "open_the_ledger", remember)
    stage.the_paid_setup_a_dry_run_can_reach("advance_check_5")

    assert seen and not seen[0].exists()


# ── the sentence it prints ────────────────────────────────────────────────


def test_the_paid_run_opens_its_ledger_through_the_same_helper():
    """One call site, so the dry run cannot be checking a different line.

    Two calls to the constructor -- one in the dry run and one in the paid
    path -- would let exactly this defect back in the moment they drifted.
    """
    source = (SCRIPTS / "run_agentic_v2_stage.py").read_text(encoding="utf-8")

    assert source.count("CostReceiptLedger(") == 1
    assert source.count("open_the_ledger(") == 3  # def, dry run, paid run


def test_the_dry_run_no_longer_claims_the_paid_run_will_reach_the_model():
    """The sentence that was false, and why it was false.

    The free job holds no `id-token`, so it has no Azure identity and cannot
    check the route, the deployment or the conversation. Claiming every
    condition was met is how a green dry run preceded a paid crash.
    """
    source = (SCRIPTS / "run_agentic_v2_stage.py").read_text(encoding="utf-8")

    assert "Every condition for the paid run is met" not in source
    assert "Every condition " in source and "this job can reach" in source
    assert "cannot reach the model" in source


@pytest.mark.parametrize(
    "promise",
    ["the plan", "the seal", "the cohort", "the amounts", "the staged inputs"],
)
def test_the_dry_run_names_what_it_did_check(promise):
    """Narrowing a claim is only useful if the narrower one is specific."""
    source = (SCRIPTS / "run_agentic_v2_stage.py").read_text(encoding="utf-8")

    assert promise in source


# ── the same gap, one line further down ───────────────────────────────────
#
# The ledger crash was cheap because it happened before the first call. Two
# calls in the paid path are not cheap in the same way: `receipt_for` runs
# once per task *after* the model has answered, and it calls `model_turns_of`
# and then `bind_run_to_ledger`. A keyword drifting in either of those is the
# identical mistake arriving after the money is spent, and with no receipt
# written for the task that was just paid for -- which is the one outcome the
# whole ledger exists to prevent.
#
# Neither can be reached without a real conversation outcome, so no dry run
# will ever execute them. Binding the arguments is the part that can be
# checked without one, and it is the part that broke.


def test_the_receipt_call_after_the_model_answers_still_binds():
    """`model_turns_of` accepts exactly the keywords the paid path passes."""
    import inspect

    from core.agentic_v2_conversation_runner import model_turns_of

    inspect.signature(model_turns_of).bind(
        object(),  # the outcome; only its presence is being checked here
        run_id="a-run",
        task_id="a-task",
        attempt=1,
        provider="azure",
        requested_model="gpt-5.4",
        deployment="gpt-5.4",
        resolved_model=None,
    )


def test_the_ledger_binding_after_the_model_answers_still_binds():
    """And `bind_run_to_ledger` accepts what it is handed next."""
    import inspect

    from core.agentic_v2_cost_binding import bind_run_to_ledger

    inspect.signature(bind_run_to_ledger).bind(
        object(),  # the ledger
        task_id="a-task",
        model_turns=(),
    )
