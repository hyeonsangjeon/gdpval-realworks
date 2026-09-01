"""#112 -- an honest token total is not out of range.

``_cost_count`` bounded two different kinds of field with one constant. How
many times a run called a model, and how many tokens those calls carried,
reach it through the same helper, and the one bound covering both was sized
for the smaller of them:

* the largest ``model_calls`` ever published is 2,346;
* the token count published beside it is 21,688,749.

Ten published token totals crossed the shared 10,000,000 bound and were
refused as out of range, on figures nothing was wrong with -- 2,337 marking
calls carrying about nine thousand tokens of rubric and deliverable each. The
producer in ``core/cost_receipts.py`` has no such bound at all, so it recorded
them and then the reader would not read them back.

Latent rather than loud, because ``project_cost_receipt`` runs over per-task
rows and those are smaller. The largest published one is 7,108,104 -- 71% of
the bound. A corpus 1.41x this one puts a single task over.

The fix separates the two bounds and derives the token one instead of guessing
it. A receipt is one contract with three readers -- ``core/cost_projection``,
``scripts/cost-receipt.mjs`` and the dashboard -- and above ``2**53 - 1`` a
JSON integer stops meaning the same thing to all of them, because it no longer
survives ``JSON.parse`` intact. That is a property of the format, checkable
from here, and unlike a guess about how large a run gets it does not go stale.

The calls bound does not move. It stays at 10,000,000, which real runs use two
hundredths of a percent of.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

BATCH_RUNNER = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER))

import core.cost_projection as cost_projection  # noqa: E402
from core.cost_projection import (  # noqa: E402
    _MAX_MODEL_CALLS,
    _MAX_TOKENS,
    project_cost_receipt,
)

REPO_ROOT = BATCH_RUNNER.parent
GRADES = REPO_ROOT / "data" / "grades"
MIRROR = REPO_ROOT / "scripts" / "cost-receipt.mjs"

#: What both fields were bounded by before this change.
SHARED_BOUND = 10_000_000

#: The figure that started this: one published shard's grading input tokens.
THE_SHARD_TOTAL = 21_688_749

BUCKETS = ("problem_solving_cost", "grading_cost")


def _receipt(**overrides) -> dict:
    """A minimal receipt the reader accepts, for varying one field at a time."""
    base = {
        "schema_version": "cost-receipt-v1",
        "currency": "USD",
        "status": "unavailable",
        "estimated_cost_usd": None,
        "known_cost_usd": None,
        "model_cost_usd": None,
        "runtime_cost_usd": None,
        "model_calls": None,
        "usage": {},
        "components": [],
        "price_table_sha256": None,
        "missing_reasons": ["ledger_unreadable"],
    }
    base.update(overrides)
    return base


def _tokens(count) -> dict:
    return _receipt(usage={"input_tokens": count})


def _refusal(value, field="probe"):
    """The reader's complaint about ``value``, or ``None`` if it accepted it."""
    try:
        project_cost_receipt(value, field)
    except ValueError as exc:
        return str(exc)
    return None


def _published_receipts():
    """Every receipt committed under ``data/grades``, run-level and per-task.

    Yields ``(path, where, receipt)`` with the raw published dict, not a
    reconstruction -- what is under test is whether the reader reads the bytes
    that are already in this repository.
    """
    for path in sorted(GRADES.rglob("*.json")):
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        summary = doc.get("summary")
        if isinstance(summary, dict):
            for field in BUCKETS:
                if isinstance(summary.get(field), dict):
                    yield path, f"summary.{field}", summary[field]
        for index, row in enumerate(doc.get("tasks") or []):
            if not isinstance(row, dict):
                continue
            for field in BUCKETS:
                if isinstance(row.get(field), dict):
                    yield path, f"tasks[{index}].{field}", row[field]


@pytest.fixture
def as_it_was(monkeypatch):
    """The reader with the two bounds shared again, exactly as before.

    The old code passed one constant to both call sites, so restoring the token
    bound to that constant restores the old behaviour without reimplementing
    it. Any before/after claim below is measured against the real function.
    """
    monkeypatch.setattr(cost_projection, "_MAX_TOKENS", SHARED_BOUND)
    return cost_projection


# --------------------------------------------------------------------------
# The figure a real run produces
# --------------------------------------------------------------------------


def test_the_shard_total_that_started_this_is_read_back():
    """The specific published figure, at its published size."""
    assert THE_SHARD_TOTAL > SHARED_BOUND
    assert _refusal(_tokens(THE_SHARD_TOTAL)) is None


def test_the_shard_total_was_refused_before(as_it_was):
    """The same figure, through the same function, with the bounds shared."""
    assert _refusal(_tokens(THE_SHARD_TOTAL)) == "probe.usage.input_tokens is out of range"


def test_every_published_run_summary_is_read_back():
    """Not a constructed example: the run-level receipts in this repository."""
    refused = [
        (path.name, where, _refusal(receipt, where))
        for path, where, receipt in _published_receipts()
        if where.startswith("summary.") and _refusal(receipt, where)
    ]
    assert refused == []


def test_what_the_producer_records_the_reader_reads():
    """The two halves of the contract, on the size that split them.

    ``core/cost_receipts.py`` bounds no count anywhere, so a total this size is
    recorded without complaint. A reader that then refuses it is not enforcing
    the contract, it is disagreeing with the other half of it.
    """
    assert "_MAX_COUNT" not in (BATCH_RUNNER / "core" / "cost_receipts.py").read_text("utf-8")
    from core.cost_receipts import CallUsage

    recorded = CallUsage(input_tokens=THE_SHARD_TOTAL, output_tokens=0)
    assert recorded.input_tokens == THE_SHARD_TOTAL
    assert _refusal(_tokens(recorded.input_tokens)) is None


# --------------------------------------------------------------------------
# Two quantities, two bounds
# --------------------------------------------------------------------------


def test_a_run_carries_far_more_tokens_than_it_made_calls():
    """The shape of every real run: thousands of calls, millions of tokens."""
    receipt = _receipt(model_calls=2_337, usage={"input_tokens": THE_SHARD_TOTAL})
    projected = project_cost_receipt(receipt, "probe")
    assert projected["model_calls"] == 2_337
    assert projected["usage"]["input_tokens"] == THE_SHARD_TOTAL


def test_the_calls_bound_did_not_move():
    """Loosening one field must not quietly loosen the other.

    This is the half of the change that could have gone unnoticed: raising a
    shared constant would have taken ``model_calls`` with it, and nothing in
    the published corpus would have shown it, because real call counts are four
    thousand times under the bound either way.
    """
    assert _MAX_MODEL_CALLS == SHARED_BOUND
    assert _refusal(_receipt(model_calls=SHARED_BOUND)) is None
    assert _refusal(_receipt(model_calls=SHARED_BOUND + 1)) == "probe.model_calls is out of range"


def test_a_call_count_the_size_of_a_token_count_is_still_refused():
    """A run does not make nine quadrillion calls, and may not claim to."""
    assert _refusal(_receipt(model_calls=_MAX_TOKENS)) == "probe.model_calls is out of range"


def test_a_component_line_is_bounded_the_same_way_as_the_receipt_above_it():
    """Both call sites for each bound, not just the outer one."""
    line = {
        "name": "grading",
        "stage": "grading",
        "retry_kind": "none",
        "status": "unavailable",
        "known_cost_usd": None,
        "model_calls": 2_337,
        "usage": {"input_tokens": THE_SHARD_TOTAL},
        "missing_reasons": ["ledger_unreadable"],
    }
    assert _refusal(_receipt(components=[line])) is None
    over = dict(line, model_calls=SHARED_BOUND + 1)
    assert _refusal(_receipt(components=[over])) == (
        "probe.components[0].model_calls is out of range"
    )


def test_the_bound_has_to_be_named_at_every_call_site():
    """What keeps the two from silently sharing one constant again.

    A default would have let a later call site pick up whichever bound happened
    to be the default, which is how the two came to share one in the first
    place. Requiring the argument makes the choice visible where it is made.
    """
    with pytest.raises(TypeError):
        cost_projection._cost_count(1, "probe")  # type: ignore[call-arg]


# --------------------------------------------------------------------------
# The bound is derived, not chosen
# --------------------------------------------------------------------------


def test_the_bound_is_the_largest_exactly_representable_json_integer():
    """Why this number and not a rounder one.

    A JSON number is a double to the reader on the other side of the contract.
    At ``2**53`` doubles stop being able to tell consecutive integers apart, so
    the file can say one integer and that reader hold another -- silently, with
    its integer check still satisfied. The bound is that boundary.
    """
    assert _MAX_TOKENS == 2**53 - 1
    assert float(_MAX_TOKENS) == _MAX_TOKENS
    assert float(_MAX_TOKENS + 1) == float(_MAX_TOKENS + 2)  # indistinguishable
    assert json.loads(json.dumps({"n": _MAX_TOKENS}))["n"] == _MAX_TOKENS


def test_one_past_the_bound_is_refused():
    assert _refusal(_tokens(_MAX_TOKENS)) is None
    assert _refusal(_tokens(_MAX_TOKENS + 1)) == "probe.usage.input_tokens is out of range"


def test_the_javascript_reader_is_pinned_to_the_same_two_bounds():
    """The mirror, read as text, because a drifted mirror is the same defect.

    ``scripts/cost-receipt.mjs`` reads the receipts this module writes. If the
    two disagree about either bound, a payload is publishable by one reader and
    not the other -- which is exactly the state this change is fixing between
    the producer and this reader. There is no import that can check this from
    Python, so the source is read.
    """
    source = MIRROR.read_text("utf-8")
    tokens = re.search(r"^const MAX_TOKENS = (.+);$", source, re.MULTILINE)
    calls = re.search(r"^const MAX_MODEL_CALLS = (.+);$", source, re.MULTILINE)
    assert tokens and calls, "the mirror no longer declares both bounds"
    # Number.MAX_SAFE_INTEGER is 2**53 - 1: the same boundary, under the name
    # the language gives it.
    assert tokens.group(1) == "Number.MAX_SAFE_INTEGER"
    assert int(calls.group(1).replace("_", "")) == _MAX_MODEL_CALLS
    assert "const MAX_COUNT" not in source, "the shared bound is still declared"


# --------------------------------------------------------------------------
# Nothing else about the check moved
# --------------------------------------------------------------------------


def test_a_negative_count_is_still_refused():
    assert _refusal(_tokens(-1)) == "probe.usage.input_tokens is out of range"
    assert _refusal(_receipt(model_calls=-1)) == "probe.model_calls is out of range"


def test_a_fractional_count_is_still_refused():
    assert _refusal(_tokens(1.5)) == "probe.usage.input_tokens must be an integer"
    assert _refusal(_tokens(float(THE_SHARD_TOTAL))) == (
        "probe.usage.input_tokens must be an integer"
    )


def test_a_boolean_is_still_not_an_integer():
    assert _refusal(_tokens(True)) == "probe.usage.input_tokens must be an integer"
    assert _refusal(_receipt(model_calls=False)) == "probe.model_calls must be an integer"


def test_an_absent_count_is_still_absent_rather_than_zero():
    """The distinction the whole receipt shape exists to hold."""
    projected = project_cost_receipt(_receipt(model_calls=None, usage={"input_tokens": None}))
    assert projected["model_calls"] is None
    assert projected["usage"]["input_tokens"] is None


# --------------------------------------------------------------------------
# Blast radius, measured on what is published
# --------------------------------------------------------------------------


def test_the_corpus_is_large_enough_for_the_measurements_below():
    published = list(_published_receipts())
    assert len(published) > 300, len(published)
    assert any(where.startswith("summary.") for _p, where, _r in published)


def test_nothing_the_reader_accepted_before_is_refused_now(as_it_was):
    """One direction only: this change may free receipts, never trap them."""
    trapped = []
    for path, where, receipt in _published_receipts():
        before = _refusal(receipt, where)
        monkey = as_it_was._MAX_TOKENS
        assert monkey == SHARED_BOUND
        as_it_was._MAX_TOKENS = _MAX_TOKENS
        try:
            after = _refusal(receipt, where)
        finally:
            as_it_was._MAX_TOKENS = SHARED_BOUND
        if before is None and after is not None:
            trapped.append(f"{path.name} {where}: {after}")
    assert trapped == []


def test_the_only_receipts_that_change_are_the_wrongly_refused_ones(as_it_was):
    """And every one of them changes for the one reason claimed."""
    freed = []
    for path, where, receipt in _published_receipts():
        before = _refusal(receipt, where)
        as_it_was._MAX_TOKENS = _MAX_TOKENS
        try:
            after = _refusal(receipt, where)
        finally:
            as_it_was._MAX_TOKENS = SHARED_BOUND
        if before == after:
            continue
        assert after is None, f"{path.name} {where}: {before} -> {after}"
        assert "usage." in before and "is out of range" in before, before
        freed.append((path.name, where))
    assert freed, "expected the published corpus to contain the refused totals"
    assert all(where.startswith("summary.") for _name, where in freed)


def test_the_figures_do_not_move_for_anything_already_accepted(as_it_was):
    """The change is a bound, not an arithmetic: accepted output is identical."""
    for path, where, receipt in _published_receipts():
        try:
            before = as_it_was.project_cost_receipt(receipt, where)
        except ValueError:
            continue
        as_it_was._MAX_TOKENS = _MAX_TOKENS
        try:
            after = as_it_was.project_cost_receipt(receipt, where)
        finally:
            as_it_was._MAX_TOKENS = SHARED_BOUND
        assert before == after, f"{path.name} {where}"


def test_every_published_per_task_receipt_still_reads():
    """The rows production actually projects, which were never over the bound.

    They are the reason this was latent rather than breaking runs, and they are
    the reason it was worth fixing anyway: the largest is 71% of the bound that
    was there, so the margin was one larger corpus wide.
    """
    rows = [(p, w, r) for p, w, r in _published_receipts() if w.startswith("tasks[")]
    assert len(rows) > 300
    assert [f"{p.name} {w}" for p, w, r in rows if _refusal(r, w)] == []
    largest = max(
        (value or 0)
        for _p, _w, receipt in rows
        for value in (receipt.get("usage") or {}).values()
        if isinstance(value, int) and not isinstance(value, bool)
    )
    assert largest < SHARED_BOUND
    assert largest > SHARED_BOUND * 0.7
