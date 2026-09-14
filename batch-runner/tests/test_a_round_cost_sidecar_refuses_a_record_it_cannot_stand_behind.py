"""A published floor must be refusable, and these are the records it refuses.

``derive_round_cost_sidecar.py`` publishes a dollar figure to the dashboard
without re-deriving it. Everything it writes is copied out of
``docs/run_records/round_state.json``, which means the file it writes is only
worth what that record is worth. Copying is the whole job, so the only place
this script can go wrong is in copying something that no longer holds together.

A derived figure that guesses is worse than an absent one. Absence reads as
"nobody priced this", which is true and legible; a guess reads as a
measurement. So every check in the producer is a place where a value could have
been defaulted, inferred or quietly dropped instead, and this file injects the
defect each one stands for and watches it refuse.

The five classes come from the audit brief, and each is a way a relayed round
can actually break rather than a way a JSON file can be malformed:

  omission      a leg's record landed without a field the figure depends on
  duplicate     the same leg's ledger was read twice, counting its calls twice
  reset         a counter went back to zero between legs while the amount stayed
  resume        a leg was replayed, so a count outgrew the pass it came from
  unknown price the pricer found no table and every call came out free

Beside those, the structural claims: that the round is not provider-billed,
that the cross-check ran and agreed, that the floor flag and the unmeasured
count say the same thing, and that the lineages add up to the round.

Every case starts from the real committed record and changes exactly one thing,
so a refusal here is a refusal of that one thing. The record itself is never
mutated -- each case works on a deep copy -- and ``build_sidecar`` writes no
files at any point. No model is called.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from scripts import derive_round_cost_sidecar as sidecar  # noqa: E402

ROUND_STATE = BATCH_RUNNER_ROOT / "docs" / "run_records" / "round_state.json"

#: Stand-ins. The producer records the round state's hash and its own so a
#: reader can check provenance; neither is what these cases are about, and
#: hashing files here would only make the tests slower and no stricter.
A_HASH = "0" * 64


def _the_real_record() -> dict[str, Any]:
    return json.loads(ROUND_STATE.read_text(encoding="utf-8"))


def _build(record: dict[str, Any], *, path: Path = Path("round_state.json")) -> dict[str, Any]:
    return sidecar.build_sidecar(
        record,
        round_state_path=path,
        round_state_sha256=A_HASH,
        script_sha256=A_HASH,
    )


# ── omission ──────────────────────────────────────────────────────────────
#
# `del`, not `pop(..., None)`. If one of these fields is ever renamed the
# deletion raises KeyError and the test errors loudly, which is the right
# outcome: a renamed field means this file is checking a record that no longer
# exists.


def omit_the_cross_check(record: dict[str, Any]) -> None:
    """The block the whole figure is copied from never landed."""
    del record["cost"]["ledger_cross_check"]


def omit_the_measured_count(record: dict[str, Any]) -> None:
    """The amount survived a leg's write-up and one of its counts did not.

    This is the defect the brief is actually about, in miniature. A measured
    count is what makes the figure a floor of something rather than a number;
    without it the screen could still show a dollar amount and say nothing
    about how much of the round it covers.
    """
    del record["cost"]["ledger_cross_check"]["calls_measured"]


def omit_the_price_fingerprint(record: dict[str, Any]) -> None:
    """No fingerprint means no way to tell which table priced this."""
    del record["cost"]["ledger_cross_check"]["price_table_sha256"]


def omit_the_legs(record: dict[str, Any]) -> None:
    """The method string names a leg count, so the legs have to be there."""
    del record["legs_read"]


def omit_the_lineages(record: dict[str, Any]) -> None:
    """The figure claims to cover every lineage; that needs a list of them."""
    del record["cost"]["per_lineage"]


# ── duplicate ─────────────────────────────────────────────────────────────


def list_one_ledger_twice(record: dict[str, Any]) -> None:
    """One leg's ledger read twice sums that leg's calls twice.

    The dangerous shape: the leg count still matches the ledger count, the
    totals still agree with each other, and the round simply looks larger than
    it was. Only the hashes can tell.
    """
    ledgers = record["cost"]["ledger_cross_check"]["ledgers"]
    ledgers[3]["sha256"] = ledgers[0]["sha256"]


def leave_a_ledger_unidentified(record: dict[str, Any]) -> None:
    """A ledger with no hash cannot be shown not to be one of the others."""
    del record["cost"]["ledger_cross_check"]["ledgers"][2]["sha256"]


def read_no_ledgers_at_all(record: dict[str, Any]) -> None:
    """An empty list is a cross-check that priced nothing and said a number."""
    record["cost"]["ledger_cross_check"]["ledgers"] = []


# ── reset ─────────────────────────────────────────────────────────────────


def reset_every_counter(record: dict[str, Any]) -> None:
    """The counters went back to zero between legs and the amount stayed.

    The floor flag is cleared too, so the record is internally consistent about
    having counted nothing. What it is not consistent about is still carrying
    $112.77 of calls it now says never happened.
    """
    check = record["cost"]["ledger_cross_check"]
    check["calls_total"] = 0
    check["calls_measured"] = 0
    check["calls_unmeasured"] = 0
    check["tasks_with_a_call"] = 0
    check["derived_total_is_a_floor"] = False


def reset_the_leg_list(record: dict[str, Any]) -> None:
    """The relay restarted its leg list; the ledgers remember the earlier legs."""
    record["legs_read"] = record["legs_read"][:1]


# ── resume ────────────────────────────────────────────────────────────────


def replay_a_leg_into_the_task_count(record: dict[str, Any]) -> None:
    """More tasks than calls: a task with a call has at least one call."""
    check = record["cost"]["ledger_cross_check"]
    check["tasks_with_a_call"] = check["calls_total"] + 1


def replay_a_leg_into_the_measured_count(record: dict[str, Any]) -> None:
    """Counting a replayed leg's calls again overruns the pass they came from."""
    check = record["cost"]["ledger_cross_check"]
    check["calls_measured"] = check["calls_total"]


def add_a_lineage_to_the_round_total_after_the_fact(record: dict[str, Any]) -> None:
    """A resumed lineage was added to the records total and nothing else moved.

    The recorded difference between the two totals is the tell. It was written
    when the cross-check ran, and it still describes the round as it was then.
    """
    cost = record["cost"]
    cost["round_total_usd"] += cost["per_lineage"]["A"]["derived_cost_usd"]


def edit_the_recorded_difference(record: dict[str, Any]) -> None:
    """Tidying the difference to zero hides which pass produced the figure."""
    record["cost"]["ledger_cross_check"]["difference_from_the_records_usd"] = 0.0


def make_the_two_totals_really_disagree(record: dict[str, Any]) -> None:
    """Half a dollar apart is not the per-task rounding the record blames.

    The difference field is updated to match, so the record is self-consistent
    and still wrong: two derivations of the same round that disagree by an
    amount no rounding produces mean one of them priced different calls.
    """
    cost = record["cost"]
    cost["round_total_usd"] = cost["ledger_cross_check"]["derived_total_usd"] - 0.5
    cost["ledger_cross_check"]["difference_from_the_records_usd"] = 0.5


# ── unknown price ─────────────────────────────────────────────────────────


def lose_the_price_table(record: dict[str, Any]) -> None:
    record["cost"]["ledger_cross_check"]["price_table_sha256"] = None


def truncate_the_price_fingerprint(record: dict[str, Any]) -> None:
    """A short fingerprint is the digest-folder mistake, not a hash."""
    check = record["cost"]["ledger_cross_check"]
    check["price_table_sha256"] = check["price_table_sha256"][:32]


def price_every_call_at_nothing(record: dict[str, Any]) -> None:
    """A pricer that found no table returns zero for calls that reported usage.

    Everything else is made consistent with the zero -- both totals, the
    recorded difference, every lineage, the superseded spend -- so the only
    thing left to object to is the one that matters: 454 calls reported usage
    and the round came out free. Unknown is not zero, and this is what that
    rule looks like at the producer.
    """
    cost = record["cost"]
    cost["round_total_usd"] = 0.0
    cost["spent_on_work_that_was_superseded_usd"] = 0.0
    cost["ledger_cross_check"]["derived_total_usd"] = 0.0
    cost["ledger_cross_check"]["difference_from_the_records_usd"] = 0.0
    for lineage in cost["per_lineage"].values():
        lineage["derived_cost_usd"] = 0.0


# ── the structural claims ─────────────────────────────────────────────────


def claim_the_provider_billed_it(record: dict[str, Any]) -> None:
    """A floor published as an invoice is the misreading this file prevents."""
    record["cost"]["is_provider_billed"] = True


def say_the_cross_check_never_ran(record: dict[str, Any]) -> None:
    record["cost"]["ledger_cross_check"]["performed"] = False


def say_the_cross_check_disagreed(record: dict[str, Any]) -> None:
    record["cost"]["ledger_cross_check"]["agrees_with_the_run_records"] = False


def clear_the_floor_flag(record: dict[str, Any]) -> None:
    """56 calls are still unpriced; clearing the flag makes the screen say `≈`."""
    record["cost"]["ledger_cross_check"]["derived_total_is_a_floor"] = False


def break_the_lineage_sum(record: dict[str, Any]) -> None:
    """If the lineages do not add up, "covers every lineage" is not true."""
    record["cost"]["per_lineage"]["A"]["derived_cost_usd"] += 1.0


def zero_the_superseded_spend(record: dict[str, Any]) -> None:
    """Calling superseded work free is calling part of the round's cost zero."""
    record["cost"]["spent_on_work_that_was_superseded_usd"] = 0.0


def name_a_lineage_that_is_not_there(record: dict[str, Any]) -> None:
    record["superseded_lineages"] = ["C"]


def hand_a_count_a_boolean(record: dict[str, Any]) -> None:
    """``True`` is an ``int`` in Python, so this has to be refused on purpose."""
    record["cost"]["ledger_cross_check"]["calls_measured"] = True


def make_a_count_negative(record: dict[str, Any]) -> None:
    record["cost"]["ledger_cross_check"]["calls_unmeasured"] = -1


INJECTIONS: tuple[tuple[str, Callable[[dict[str, Any]], None], str], ...] = (
    # omission
    ("omission: the cross-check block", omit_the_cross_check, "has no 'ledger_cross_check'"),
    ("omission: the measured count", omit_the_measured_count, "has no 'calls_measured'"),
    ("omission: the price fingerprint", omit_the_price_fingerprint, "has no 'price_table_sha256'"),
    ("omission: the legs", omit_the_legs, "has no 'legs_read'"),
    ("omission: the lineages", omit_the_lineages, "has no 'per_lineage'"),
    # duplicate
    ("duplicate: one ledger twice", list_one_ledger_twice, "the same ledger more than once"),
    ("duplicate: a ledger with no hash", leave_a_ledger_unidentified, "no usable sha256"),
    ("duplicate: no ledgers at all", read_no_ledgers_at_all, "the cross-check read nothing"),
    # reset
    ("reset: every counter", reset_every_counter, "with no calls behind it"),
    ("reset: the leg list", reset_the_leg_list, "but the cross-check lists"),
    # resume
    (
        "resume: replayed into the task count",
        replay_a_leg_into_the_task_count,
        "exceeds the calls_total",
    ),
    (
        "resume: replayed into the measured count",
        replay_a_leg_into_the_measured_count,
        "exceeds calls_total",
    ),
    (
        "resume: a lineage added afterwards",
        add_a_lineage_to_the_round_total_after_the_fact,
        "was changed after the cross-check ran",
    ),
    (
        "resume: the difference was edited",
        edit_the_recorded_difference,
        "was changed after the cross-check ran",
    ),
    (
        "resume: the totals really disagree",
        make_the_two_totals_really_disagree,
        "too large to be the per-task rounding",
    ),
    # unknown price
    ("unknown price: no table", lose_the_price_table, "is not a sha256"),
    ("unknown price: a truncated fingerprint", truncate_the_price_fingerprint, "is not a sha256"),
    (
        "unknown price: every call free",
        price_every_call_at_nothing,
        "a missing price rather than a free round",
    ),
    # structural
    ("structural: provider billed", claim_the_provider_billed_it, "is not false"),
    ("structural: never performed", say_the_cross_check_never_ran, "performed is not true"),
    (
        "structural: did not agree",
        say_the_cross_check_disagreed,
        "agrees_with_the_run_records is not true",
    ),
    ("structural: the floor flag cleared", clear_the_floor_flag, "states it two ways"),
    ("structural: the lineages do not add up", break_the_lineage_sum, "lineages sum to"),
    ("structural: superseded spend zeroed", zero_the_superseded_spend, "superseded lineages"),
    ("structural: an unknown lineage", name_a_lineage_that_is_not_there, "does not carry"),
    ("structural: a count arrived as a boolean", hand_a_count_a_boolean, "is not a count: True"),
    ("structural: a negative count", make_a_count_negative, "is not a count: -1"),
)


@pytest.mark.parametrize(
    "mutate,expected",
    [(mutate, expected) for _, mutate, expected in INJECTIONS],
    ids=[label for label, _, _ in INJECTIONS],
)
def test_an_injected_defect_is_refused_rather_than_published(
    mutate: Callable[[dict[str, Any]], None], expected: str
) -> None:
    """One field changed on the real record, and no file comes out of it."""
    record = copy.deepcopy(_the_real_record())
    mutate(record)
    with pytest.raises(sidecar.DerivationRefused) as refusal:
        _build(record)
    assert expected in str(refusal.value), (
        "the record was refused, but for a different reason than the one this "
        f"case injects. Expected {expected!r}, got: {refusal.value}"
    )


def test_a_method_string_too_long_for_the_display_is_refused_here() -> None:
    """Refuse at the producer what the display would refuse on arrival.

    The method string carries the path it was copied from, so a deep enough
    path pushes it past the length ``projectDerivedCost`` accepts. Written
    instead of refused, the file would sit on disk looking finished and vanish
    from the screen with no explanation at the point of reading.
    """
    with pytest.raises(sidecar.DerivationRefused) as refusal:
        _build(_the_real_record(), path=Path("a/" * 300 + "round_state.json"))
    assert "over the" in str(refusal.value)
    assert str(sidecar.MAX_METHOD_LENGTH) in str(refusal.value)


def test_the_real_record_is_published_exactly_as_it_stands() -> None:
    """The control: without an injection, every figure is the record's own.

    If this ever fails alongside the cases above, the producer has become
    strict about something the committed record does not satisfy, and the
    refusals stop meaning what they say.
    """
    record = _the_real_record()
    built = _build(record)
    check = record["cost"]["ledger_cross_check"]

    for field in ("derived_total_usd", "price_table_sha256", *sidecar.REQUIRED_COUNTS):
        assert built[field] == check[field], f"{field} was not copied unchanged"
    assert built["derived_total_is_a_floor"] is True
    # Hard-coded at the producer, never read from the record: a derived figure
    # has no way to become an invoice by being written down differently.
    assert built["derived_total_is_provider_billed"] is False
    # Null rather than {}. An empty map would read as "the pricer refused
    # nothing", which is false for 56 of the round's calls.
    assert built["pricer_refusals"] is None
    assert built["source"]["round_total_usd_from_the_task_records"] == (
        record["cost"]["round_total_usd"]
    )
    assert built["source"]["ledger_sha256"] == [led["sha256"] for led in check["ledgers"]]
