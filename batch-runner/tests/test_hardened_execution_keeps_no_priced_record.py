"""A hardened run keeps no priced record, and says so rather than saying $0.

Most execution modes are metered: the client is wrapped, every call is
reserved before it leaves and settled when it returns, and the task ends with
a receipt that names what it cost. Two modes are not. ``agentic_sandbox``, and
``sandbox`` with ``hardened_substrate`` on, run the model behind an attested
substrate this process does not wrap. There is no honest number to write, so
``step2_run_inference`` does not open a ledger for them at all and marks the
receipt ``unavailable`` with ``stage_unsupported``.

That policy is three lines, and until now nothing held it in place. The gap
was recorded when the metering work merged (#257) and this module closes it.

Two different mistakes could be made here, in opposite directions, and both
are silent:

* **Metering the attested path.** Turning the ledger on for a hardened run —
  by narrowing the flag, or by moving the ``open_cost_recorder`` call out from
  under its guard — produces a receipt that looks priced and is not, because
  the calls this process can see are not the calls that were billed. An
  understated bill that presents as a complete one is the worst shape a cost
  record takes; it is the failure the four statuses exist to prevent.
* **Letting "unrecorded" read as "free".** ``unavailable`` and ``$0.00`` look
  the same in a total. They are opposites: one is an absence of knowledge, the
  other a measurement. A hardened run that summarised to zero would quietly
  subtract real spend from a report.

The flag governing both is ``hardened_requested``, and it covers *two* modes,
not one. Narrowing it to ``agentic_sandbox`` alone would leave the hardened
sandbox metered while still reading as deliberate.

Why part of this is read from the source rather than run. The policy lives
inside ``main()`` in ``step2_run_inference`` — a long function that reaches the
branch only after argument parsing, workspace setup, dataset load and client
construction. There is no hardened end-to-end harness in this suite to drive
it: ``hardened=True`` is a defined parameter with no exercised path, and
building one needs the signature-approval gate, which means a real run. So the
structural half of this module asks the module's own syntax tree the three
questions a harness would have asked, and the behavioural half runs the
receipt semantics that branch produces, which *are* reachable. Between them
the branch is pinned at both ends: which calls happen, and what they report.

Nothing here calls a model, runs a sandbox, marks anything, or spends
anything. It parses one file and builds receipts in memory.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from core.cost_receipts import (
    REASON_LEDGER_ABSENT,
    REASON_STAGE_UNSUPPORTED,
    STATUS_COMPLETE,
    STATUS_UNAVAILABLE,
    CostReceipt,
    summarise_receipts,
)

STEP2 = Path(__file__).resolve().parents[1] / "step2_run_inference.py"
FLAG = "hardened_requested"


@pytest.fixture(scope="module")
def step2_tree() -> ast.Module:
    """``step2_run_inference`` as syntax, not text.

    Parsed rather than grepped so the assertions survive reformatting, moved
    lines and rewritten comments, and fail only when the *structure* changes —
    which is the thing being held still.
    """
    return ast.parse(STEP2.read_text(encoding="utf-8"))


def _calls_to(node: ast.AST, name: str) -> list[ast.Call]:
    """Every call to *name*, whether plain or reached through an attribute."""
    calls = []
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        func = inner.func
        if isinstance(func, ast.Name) and func.id == name:
            calls.append(inner)
        elif isinstance(func, ast.Attribute) and func.attr == name:
            calls.append(inner)
    return calls


def _is_not_flag(test: ast.expr) -> bool:
    """True for the expression ``not hardened_requested``."""
    return (
        isinstance(test, ast.UnaryOp)
        and isinstance(test.op, ast.Not)
        and isinstance(test.operand, ast.Name)
        and test.operand.id == FLAG
    )


def test_a_hardened_run_opens_no_cost_ledger(step2_tree: ast.Module) -> None:
    """The ledger is opened under ``if not hardened_requested:``, or not at all.

    This is the keystone. Metering starts at ``open_cost_recorder`` — it
    returns the recorder that then wraps every client — so a hardened run
    stays unmetered exactly as long as that one call stays behind the guard.
    Moving it out, or adding a second unguarded call beside it, would wrap the
    attested path and start writing prices for calls this process never saw.

    Stated as "every call is guarded" rather than "the call on line N is
    guarded" so that a *new* unguarded call fails this too.
    """
    every = {call.lineno for call in _calls_to(step2_tree, "open_cost_recorder")}
    assert every, "step2 no longer opens a cost ledger anywhere; this guard moved"

    guarded = {
        call.lineno
        for node in ast.walk(step2_tree)
        if isinstance(node, ast.If) and _is_not_flag(node.test)
        for stmt in node.body
        for call in _calls_to(stmt, "open_cost_recorder")
    }
    assert every == guarded, (
        f"open_cost_recorder is reached outside `if not {FLAG}:` at lines "
        f"{sorted(every - guarded)}; a hardened run would be metered"
    )


def test_hardened_covers_the_agentic_mode_and_the_sandbox_flag(
    step2_tree: ast.Module,
) -> None:
    """Both unmetered modes set the flag — not just the obvious one.

    ``agentic_sandbox`` is a mode; the hardened substrate is an option *on*
    the ordinary sandbox mode. Reading the flag quickly suggests the first
    covers it. It does not, and dropping the second would leave hardened
    sandbox runs metered while the code still looked deliberate.
    """
    assigned = [
        node
        for node in ast.walk(step2_tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == FLAG
            for target in node.targets
        )
    ]
    assert len(assigned) == 1, f"expected exactly one place to define {FLAG}"

    literals = {
        inner.value
        for inner in ast.walk(assigned[0].value)
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str)
    }
    assert {"agentic_sandbox", "sandbox", "hardened_substrate"} <= literals, (
        f"{FLAG} no longer names both unmetered modes; it reads {sorted(literals)}"
    )


def test_an_unmetered_hardened_task_blames_the_stage_not_a_lost_ledger(
    step2_tree: ast.Module,
) -> None:
    """The two ways to have no ledger are told apart in the receipt.

    A hardened run has no ledger *by design*; an ordinary run without one has
    lost something. Both produce ``unavailable``, and the reason code is the
    only thing that distinguishes "this mode is not priceable" from "the
    ledger did not open, go and find out why". Collapsing them to one reason
    would turn a real fault into something that looks intended.
    """
    selections = [
        call.keywords[0].value
        for call in _calls_to(step2_tree, "unavailable")
        if len(call.keywords) == 1
        and call.keywords[0].arg == "reasons"
        and isinstance(call.keywords[0].value, ast.IfExp)
    ]
    assert len(selections) == 1, (
        "expected one receipt that picks its reason from " + FLAG
    )

    chosen = selections[0]
    assert isinstance(chosen.test, ast.Name) and chosen.test.id == FLAG

    def named(branch: ast.expr) -> set[str]:
        return {
            inner.id for inner in ast.walk(branch) if isinstance(inner, ast.Name)
        }

    assert named(chosen.body) == {"REASON_STAGE_UNSUPPORTED"}
    assert named(chosen.orelse) == {"REASON_LEDGER_ABSENT"}


def test_a_hardened_task_reports_unavailable_rather_than_zero() -> None:
    """What that branch hands back, run rather than read.

    ``estimated_cost_usd`` is the only field that claims to be a total, and it
    stays ``None`` here. ``known_cost_usd`` is ``0.0``, which is honest — zero
    was confirmed, because nothing was — and is not a total, because the
    status says it is not one.
    """
    receipt = CostReceipt.unavailable(reasons=(REASON_STAGE_UNSUPPORTED,))
    payload = receipt.as_dict()

    assert payload["status"] == STATUS_UNAVAILABLE
    assert payload["estimated_cost_usd"] is None
    assert payload["missing_reasons"] == [REASON_STAGE_UNSUPPORTED]
    assert payload["model_calls"] == 0
    assert payload["components"] == []


def test_an_ordinary_run_without_a_ledger_says_something_else() -> None:
    """The other side of the same branch, so the two cannot converge.

    If a refactor ever made both paths produce the same reason, the assertion
    above would still pass on its own. This one fails.
    """
    assert CostReceipt.unavailable().missing_reasons == (REASON_LEDGER_ABSENT,)
    assert (
        CostReceipt.unavailable(reasons=(REASON_STAGE_UNSUPPORTED,)).missing_reasons
        != CostReceipt.unavailable().missing_reasons
    )


@pytest.mark.parametrize(
    "payload",
    [{}, "not a mapping at all", {"schema_version": "1.3", "known_cost_usd": 9.0}],
    ids=["empty", "not-a-mapping", "superseded-schema"],
)
def test_every_way_of_arriving_at_unavailable_carries_a_reason(payload) -> None:
    """``unavailable`` and nothing else is not a state this produces.

    A reader shown "unavailable" with no reason cannot act on it, and one that
    rejects reason-less receipts drops the row — so the run loses a task from
    its report rather than showing it as unpriced.

    The paths that reach ``unavailable`` without anyone choosing a reason are
    the fail-closed ones: reading back a row that is missing, malformed, or
    written to a superseded schema. A receipt from an older build carrying a
    real amount is refused rather than trusted, since the fields behind that
    number have since changed meaning.

    (``CostReceipt.unavailable`` will pass an empty tuple through if handed
    one explicitly. No caller does — every site takes the default or names its
    own reason — so that is a latent trap rather than a defect, and left
    alone here rather than fixed on a branch scoped to a test gap.)
    """
    receipt = CostReceipt.from_dict(payload)

    assert receipt.status == STATUS_UNAVAILABLE
    assert receipt.missing_reasons == (REASON_LEDGER_ABSENT,)
    assert receipt.as_dict()["estimated_cost_usd"] is None
    assert summarise_receipts([receipt]).missing_reasons == (REASON_LEDGER_ABSENT,)


def test_a_whole_hardened_run_never_summarises_to_zero_dollars() -> None:
    """Every task unpriced keeps the run unpriced.

    A summary is where the misreading would do damage: one number, on a
    report, next to runs that do have totals. It stays ``unavailable`` and
    keeps the reason, so the run reads as unmeasured rather than as free.
    """
    receipts = [CostReceipt.unavailable(reasons=(REASON_STAGE_UNSUPPORTED,))] * 3
    summary = summarise_receipts(receipts).as_dict()

    assert summary["status"] == STATUS_UNAVAILABLE
    assert summary["estimated_cost_usd"] is None
    assert summary["missing_reasons"] == [REASON_STAGE_UNSUPPORTED]


def test_one_unmetered_task_stops_the_run_claiming_a_total() -> None:
    """A mixed run is a floor, never a total.

    Only some pipelines are hardened, so a run can hold priced tasks beside
    unpriceable ones. The priced amount is still worth reporting — but as
    ``partial``, where it reads as "at least this much". Were it to summarise
    ``complete``, the report would state a total that is missing every
    hardened task's spend and give no sign of it.
    """
    priced = CostReceipt(
        status=STATUS_COMPLETE,
        known_cost_usd=Decimal("1.25"),
        model_cost_usd=Decimal("1.25"),
        model_calls=1,
    )
    summary = summarise_receipts(
        [priced, CostReceipt.unavailable(reasons=(REASON_STAGE_UNSUPPORTED,))]
    ).as_dict()

    assert summary["status"] == "partial"
    assert summary["estimated_cost_usd"] is None
    assert summary["known_cost_usd"] == pytest.approx(1.25)
    assert REASON_STAGE_UNSUPPORTED in summary["missing_reasons"]
