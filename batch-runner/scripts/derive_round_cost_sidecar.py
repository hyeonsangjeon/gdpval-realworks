"""Publish a relayed round's already-derived floor where the dashboard reads it.

``derive_run_cost.py`` prices a run's tokens back out of that run's own sqlite
ledger and writes ``results/<exp>/report/derived_cost.json``. The dashboard
reads exactly that file. For a single run it works: the ledger is still to hand
when someone goes looking for the money.

A relayed run does not get that second chance. ``exp035`` ran as six legs across
two lineages, and its six ledgers lived at ``/tmp/relay/...`` and
``/tmp/leg7_artifact/...`` on runners that no longer exist. The derivation was
performed while they did -- ``roll_up_round.py --ledger`` read all six, priced
them against the committed table, and cross-checked the result against the
per-task records. That answer is committed, in
``docs/run_records/round_state.json`` under ``cost.ledger_cross_check``.

So the floor is not missing. It is in the repository, in a block carrying every
count the display contract asks for, and nothing carries it the last step to the
screen. The largest measured-token evidence this project has shows no derived
figure while a 30-task trial shows one. This script is that last step, and
nothing more than that step: it re-prices nothing, sums nothing, and adds
nothing to any ledger amount. Every number it writes is copied from a block
another tool wrote, and the checks below exist to establish that the block still
says what it said when it was written.

**What scope it publishes, and why.** The round: both lineages, every leg. Not
because it is the larger number -- because it is the only scope the record
supports. The per-lineage blocks carry a dollar figure and nothing else; they
have no call counts and no price fingerprint, so a lineage-B-only sidecar could
only be assembled by inventing the counts that make it displayable. And the
round is the honest figure anyway: ``roll_up_round.py`` says it plainly --
a task two lineages both solved is one task of coverage and two payments of
cost. The superseded lineage's spend was really spent. Dropping it would call
part of the economic cost zero.

**What it is not.** Not a receipt, and never folded into one. A receipt says
*the run stood behind this figure*; this says *someone priced the run's tokens
afterwards, from outside it*. ``derived_total_is_provider_billed`` is hard-coded
false. This is a floor: 56 of the round's 510 calls reported no usage at all,
so the real amount is higher by an unknown margin. It excludes grading.

No model is called. Nothing is re-derived. The only write is the sidecar.

    python3 scripts/derive_round_cost_sidecar.py \\
        --round-state docs/run_records/round_state.json \\
        --output results/exp035_codex_foundry_full220/report/derived_cost.json

``--check`` re-runs the projection and compares bytes without writing, which is
how a reader confirms the committed file came from the committed record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

#: `projectDerivedCost` in scripts/cost-receipt.mjs caps the method string. A
#: longer one is refused at the display layer, so it is refused here instead of
#: being written and discovered later.
MAX_METHOD_LENGTH = 512

#: The four counts the display contract requires, in the order it reads them.
REQUIRED_COUNTS = (
    "calls_total",
    "calls_measured",
    "calls_unmeasured",
    "tasks_with_a_call",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

#: The records round each task to the millionth and the ledgers round once over
#: the whole round, so the two totals differ by that rounding. A cent is far
#: above the rounding and far below any real disagreement about calls.
MAX_ROUNDING_DIFFERENCE_USD = 0.01

#: Floating point comparison of two figures that are both already rounded to the
#: millionth. Anything this close is the same number written twice.
EPSILON_USD = 5e-07


class DerivationRefused(Exception):
    """The record does not support the figure, so no file is written.

    Every raise below is a case where a value could have been guessed, defaulted
    or quietly dropped instead. A derived cost that guesses is worse than an
    absent one: absent reads as "nobody priced this", and a guess reads as a
    measurement.
    """


def _require(block: dict[str, Any], key: str, where: str) -> Any:
    if key not in block:
        raise DerivationRefused(f"{where} has no {key!r}")
    return block[key]


def _require_count(block: dict[str, Any], key: str, where: str) -> int:
    value = _require(block, key, where)
    # bool is an int in Python and would sail through isinstance. A count that
    # arrived as True is a record someone edited by hand.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DerivationRefused(f"{where}.{key} is not a count: {value!r}")
    return value


def _require_amount(block: dict[str, Any], key: str, where: str) -> float:
    value = _require(block, key, where)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DerivationRefused(f"{where}.{key} is not an amount: {value!r}")
    if value < 0:
        raise DerivationRefused(f"{where}.{key} is negative: {value!r}")
    return float(value)


def _require_true(block: dict[str, Any], key: str, where: str) -> None:
    if _require(block, key, where) is not True:
        raise DerivationRefused(
            f"{where}.{key} is not true, so the record does not stand behind "
            "this figure and neither will this file"
        )


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_the_ledgers(check: dict[str, Any]) -> list[str]:
    """Return the ledger hashes, refusing a list that cannot be what it says.

    The method string names how many ledgers the figure came from, so the list
    has to be real. A repeated hash is the specific shape of a double count: the
    same leg's ledger read twice sums that leg's calls twice, and the total
    would look like a larger round rather than a broken one.
    """
    ledgers = _require(check, "ledgers", "cost.ledger_cross_check")
    if not isinstance(ledgers, list) or not ledgers:
        raise DerivationRefused(
            "cost.ledger_cross_check.ledgers is empty, so the cross-check read "
            "nothing and its figure has no ledger behind it"
        )
    hashes: list[str] = []
    for index, entry in enumerate(ledgers):
        if not isinstance(entry, dict):
            raise DerivationRefused(f"cost.ledger_cross_check.ledgers[{index}] is not an object")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise DerivationRefused(
                f"cost.ledger_cross_check.ledgers[{index}] has no usable sha256: {digest!r}"
            )
        hashes.append(digest)
    duplicated = sorted({h for h in hashes if hashes.count(h) > 1})
    if duplicated:
        raise DerivationRefused(
            "cost.ledger_cross_check.ledgers lists the same ledger more than "
            f"once ({', '.join(d[:12] for d in duplicated)}), which would have "
            "counted one leg's calls twice"
        )
    return hashes


def _check_the_totals_agree(cost: dict[str, Any], check: dict[str, Any]) -> None:
    """Verify the record's own agreement claim instead of trusting it.

    ``agrees_with_the_run_records`` and ``difference_from_the_records_usd`` are
    written by the tool that performed the cross-check. Recomputing the
    difference here is cheap and catches the one thing a boolean cannot: a
    record whose totals were edited after the claim was made.
    """
    records_total = _require_amount(cost, "round_total_usd", "cost")
    ledgers_total = _require_amount(check, "derived_total_usd", "cost.ledger_cross_check")
    claimed = _require(check, "difference_from_the_records_usd", "cost.ledger_cross_check")
    if isinstance(claimed, bool) or not isinstance(claimed, (int, float)):
        raise DerivationRefused(
            f"cost.ledger_cross_check.difference_from_the_records_usd is not a number: {claimed!r}"
        )
    observed = ledgers_total - records_total
    if abs(observed - float(claimed)) > EPSILON_USD:
        raise DerivationRefused(
            "cost.ledger_cross_check.difference_from_the_records_usd says "
            f"{claimed!r} but the two totals in this record differ by "
            f"{observed!r}. One of them was changed after the cross-check ran."
        )
    if abs(observed) > MAX_ROUNDING_DIFFERENCE_USD:
        raise DerivationRefused(
            f"the ledgers and the records differ by ${abs(observed):.6f}, which "
            "is too large to be the per-task rounding the record blames it on"
        )


def _check_the_lineages_add_up(cost: dict[str, Any]) -> tuple[float, list[str]]:
    """Return the superseded spend and the lineage names, having checked both.

    The published figure covers every lineage, so the method says how much of it
    bought work a later lineage replaced. That sentence is only true if the
    round total really is the lineages summed, and if the superseded amount
    really is the superseded lineages'. Both are arithmetic on numbers already
    in the record -- no lineage is re-priced here.
    """
    per_lineage = _require(cost, "per_lineage", "cost")
    if not isinstance(per_lineage, dict) or not per_lineage:
        raise DerivationRefused("cost.per_lineage is empty")

    summed = 0.0
    for name, block in sorted(per_lineage.items()):
        if not isinstance(block, dict):
            raise DerivationRefused(f"cost.per_lineage.{name} is not an object")
        summed += _require_amount(block, "derived_cost_usd", f"cost.per_lineage.{name}")
    records_total = _require_amount(cost, "round_total_usd", "cost")
    if abs(summed - records_total) > EPSILON_USD:
        raise DerivationRefused(
            f"cost.round_total_usd is {records_total!r} but the lineages sum to "
            f"{summed!r}. The published figure claims to cover every lineage, "
            "and this record does not support that."
        )
    return summed, sorted(per_lineage)


def _superseded_spend(round_state: dict[str, Any], cost: dict[str, Any]) -> float:
    """Check the record's superseded figure against the lineages it names."""
    claimed = _require_amount(cost, "spent_on_work_that_was_superseded_usd", "cost")
    superseded = _require(round_state, "superseded_lineages", "round_state")
    if not isinstance(superseded, list):
        raise DerivationRefused("superseded_lineages is not a list")
    per_lineage = cost["per_lineage"]
    recomputed = 0.0
    for name in superseded:
        if name not in per_lineage:
            raise DerivationRefused(
                f"superseded_lineages names {name!r}, which cost.per_lineage does not carry"
            )
        recomputed += float(per_lineage[name]["derived_cost_usd"])
    if abs(recomputed - claimed) > EPSILON_USD:
        raise DerivationRefused(
            f"cost.spent_on_work_that_was_superseded_usd is {claimed!r} but the "
            f"superseded lineages {superseded!r} sum to {recomputed!r}"
        )
    return claimed


def build_sidecar(
    round_state: dict[str, Any],
    *,
    round_state_path: Path,
    round_state_sha256: str,
    script_sha256: str,
) -> dict[str, Any]:
    """Project a committed round record into the sidecar the dashboard reads.

    Reads one block -- ``cost.ledger_cross_check`` -- because that is the only
    block in the record whose figure and whose counts came from the same pass
    over the same ledgers. The per-task records carry a total too, and it is
    checked against this one, but it is not the figure published: its counts
    live elsewhere and pairing a total from one derivation with counts from
    another is how a display ends up describing something nobody measured.
    """
    cost = _require(round_state, "cost", "round_state")
    if not isinstance(cost, dict):
        raise DerivationRefused("round_state.cost is not an object")

    # A round that claims to be provider-billed is not a derived estimate, and
    # publishing it as one would put an invoice's authority behind a floor.
    if _require(cost, "is_provider_billed", "cost") is not False:
        raise DerivationRefused(
            "cost.is_provider_billed is not false, so this record is not "
            "describing a derived estimate and must not be published as one"
        )

    check = _require(cost, "ledger_cross_check", "cost")
    if not isinstance(check, dict):
        raise DerivationRefused("cost.ledger_cross_check is not an object")
    _require_true(check, "performed", "cost.ledger_cross_check")
    _require_true(check, "agrees_with_the_run_records", "cost.ledger_cross_check")

    ledger_hashes = _check_the_ledgers(check)
    _check_the_totals_agree(cost, check)
    _, lineages = _check_the_lineages_add_up(cost)
    superseded_usd = _superseded_spend(round_state, cost)

    counts = {
        name: _require_count(check, name, "cost.ledger_cross_check")
        for name in REQUIRED_COUNTS
    }
    total = _require_amount(check, "derived_total_usd", "cost.ledger_cross_check")

    is_floor = _require(check, "derived_total_is_a_floor", "cost.ledger_cross_check")
    if not isinstance(is_floor, bool):
        raise DerivationRefused(
            f"cost.ledger_cross_check.derived_total_is_a_floor is not a boolean: {is_floor!r}"
        )
    # At the producer the flag and the unmeasured count are one fact stated
    # twice. Where they diverge the record is unreadable rather than
    # half-readable, and the display layer refuses it for the same reason.
    if is_floor != (counts["calls_unmeasured"] > 0):
        raise DerivationRefused(
            f"derived_total_is_a_floor is {is_floor!r} but calls_unmeasured is "
            f"{counts['calls_unmeasured']!r}. These are the same fact and this "
            "record states it two ways."
        )
    if counts["calls_measured"] + counts["calls_unmeasured"] > counts["calls_total"]:
        raise DerivationRefused(
            f"calls_measured {counts['calls_measured']} + calls_unmeasured "
            f"{counts['calls_unmeasured']} exceeds calls_total {counts['calls_total']}"
        )
    if counts["tasks_with_a_call"] > counts["calls_total"]:
        raise DerivationRefused(
            f"tasks_with_a_call {counts['tasks_with_a_call']} exceeds the "
            f"calls_total {counts['calls_total']} it was counted from"
        )
    # A zero beside calls that reported usage is not a price -- it is a pricer
    # that found no table. The display layer already refuses to render that as a
    # free run; refusing to write it keeps the two from disagreeing.
    if total == 0.0 and counts["calls_measured"] > 0:
        raise DerivationRefused(
            f"derived_total_usd is 0.0 with {counts['calls_measured']} measured "
            "calls, which is a missing price rather than a free round"
        )
    if total > 0.0 and counts["calls_total"] == 0:
        raise DerivationRefused(
            f"derived_total_usd is {total!r} with no calls behind it"
        )

    price_sha = _require(check, "price_table_sha256", "cost.ledger_cross_check")
    if not isinstance(price_sha, str) or not _SHA256.fullmatch(price_sha):
        raise DerivationRefused(
            f"cost.ledger_cross_check.price_table_sha256 is not a sha256: {price_sha!r}"
        )

    legs = _require(round_state, "legs_read", "round_state")
    if not isinstance(legs, list) or not legs:
        raise DerivationRefused("legs_read is empty, so the round read no legs")
    # One ledger per leg is what the cross-check claims to have done. A count
    # that disagrees means the cross-check saw a different round than this
    # record describes, and the method string would name the wrong number.
    if len(legs) != len(ledger_hashes):
        raise DerivationRefused(
            f"the round read {len(legs)} legs but the cross-check lists "
            f"{len(ledger_hashes)} ledgers"
        )
    leg_count = len(legs)

    method = (
        f"roll_up_round.py --ledger over the {len(ledger_hashes)} run ledgers of "
        f"this round's relay ({len(lineages)} lineages, {leg_count} legs), priced "
        f"with the committed receipt price table (sha256 {price_sha[:8]}...); the "
        "same fingerprint the run's own task records carry. Copied from "
        f"{round_state_path.as_posix()} cost.ledger_cross_check and not re-priced "
        f"here. Covers every lineage, ${superseded_usd:.6f} of it work a later "
        "lineage superseded. Excludes grading."
    )
    if len(method) > MAX_METHOD_LENGTH:
        raise DerivationRefused(
            f"the method string is {len(method)} characters, over the "
            f"{MAX_METHOD_LENGTH} the display contract allows"
        )

    return {
        "what_this_is": (
            "The derived floor this round already computed, copied to where the "
            "dashboard reads it. Not a receipt and not an invoice: a receipt "
            "says the run stood behind a figure, this says someone priced the "
            "run's tokens afterwards from outside it. A floor because "
            f"{counts['calls_unmeasured']} of {counts['calls_total']} calls "
            "reported no usage at all. Solving only -- grading is not in it."
        ),
        "method": method,
        "price_table_sha256": price_sha,
        "calls_total": counts["calls_total"],
        "calls_measured": counts["calls_measured"],
        "calls_unmeasured": counts["calls_unmeasured"],
        "tasks_with_a_call": counts["tasks_with_a_call"],
        "derived_total_usd": total,
        "derived_total_is_a_floor": is_floor,
        "derived_total_is_provider_billed": False,
        # Null, not {}. An empty map reads as "the pricer refused nothing",
        # which is false -- it refused calls_unmeasured of them. The record
        # keeps no per-reason breakdown, so the honest value is the absent one,
        # and the display contract accepts null for exactly this case.
        "pricer_refusals": None,
        "source": {
            "round_state": round_state_path.as_posix(),
            "round_state_sha256": round_state_sha256,
            "ledger_sha256": ledger_hashes,
            "derived_by": "batch-runner/scripts/derive_round_cost_sidecar.py",
            "derived_by_sha256": script_sha256,
            "round_total_usd_from_the_task_records": cost["round_total_usd"],
            "spent_on_work_that_was_superseded_usd": superseded_usd,
        },
    }


def render(sidecar: dict[str, Any]) -> str:
    """Match derive_run_cost.py's formatting so the two sidecars read alike."""
    return json.dumps(sidecar, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Publish a relayed round's already-derived cost floor as the "
            "derived_cost.json the dashboard reads. Re-prices nothing."
        )
    )
    parser.add_argument("--round-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare against the file on disk without writing it",
    )
    args = parser.parse_args()

    script = Path(__file__).resolve()
    try:
        round_state = json.loads(args.round_state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"REFUSED: {args.round_state} could not be read: {err}", file=sys.stderr)
        return 2

    try:
        sidecar = build_sidecar(
            round_state,
            round_state_path=args.round_state,
            round_state_sha256=sha256_of(args.round_state),
            script_sha256=sha256_of(script),
        )
    except DerivationRefused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2

    rendered = render(sidecar)
    floor = " (a floor)" if sidecar["derived_total_is_a_floor"] else ""
    print(f"round state        : {args.round_state}")
    print(f"price table        : {sidecar['price_table_sha256']}")
    print(
        f"calls              : {sidecar['calls_total']} "
        f"({sidecar['calls_measured']} measured, "
        f"{sidecar['calls_unmeasured']} unmeasured)"
    )
    print(f"derived total      : ${sidecar['derived_total_usd']:.6f}{floor}")
    print("provider billed    : no")

    if args.check:
        if not args.output.exists():
            print(f"REFUSED: {args.output} does not exist", file=sys.stderr)
            return 2
        on_disk = args.output.read_text(encoding="utf-8")
        if on_disk != rendered:
            print(
                f"REFUSED: {args.output} is not what this record projects to",
                file=sys.stderr,
            )
            return 2
        print(f"checked {args.output} — identical")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
