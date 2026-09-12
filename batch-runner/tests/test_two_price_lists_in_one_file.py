"""One file, two price lists, and the voice was reading the wrong one.

Measured, not supposed. ``experiments/execution_envelope/model_price_table.json``
holds two blocks of rates for the same models:

* ``models.gpt-5.4`` — $1.25 in, $5.00 out per million. No source, no review
  date. The file's own note records that on 2026-08-29 every figure in this
  block was checked against the Azure Retail Prices API and **none of them
  matched a published meter**.
* ``providers.azure:gpt-5.4`` — $2.50 in, $15.00 out per million, with the
  three meter names it was read from, the API it was read from, and the date.

The cost ledger has always read the second. The voice read the first, so the
run record and the sqlite ledger written by the same run priced the same calls
at two different rates — a factor of two on input and three on output.

Neither figure was marked as doubtful, and the run record's docstring said the
two were computed from "the same list", differing only in the key. Same file,
different block.

The fix is a loader, not an edit to the price list. The list is shared and its
bytes are fingerprinted into receipts, so changing it would invalidate the
provenance of records that are already written. ``load_provider_price_table``
reads the sourced block and keys it the way the voice looks things up.

Three scripts build a paid Azure client and price what they spend — the V2
stage and the two probes — and all three read the unsourced block. The swap is
applied to all three, and the constant naming the provider lives beside the
loader rather than being copied into each.

What is *not* swapped, deliberately: ``estimate_cost_ceiling``. That is a
pre-run figure and the planning block is what the pre-registration's approved
amounts were computed from. Moving it would move a number that has already been
approved, which is a different decision from fixing what a run reports about
calls it has already made.

What is pinned here
-------------------

* the sourced rates are what the voice's loader returns,
* the two blocks really do disagree, so this is a measurement and not a story,
* the voice and the ledger now reach the *same* figure on the same tokens,
* a rate with no source or no review date is refused,
* a model this provider does not price is left out rather than borrowed from
  the unsourced block — missing stays partial and never becomes a number,
* all three paid voices moved, and the ceiling did not.

Nothing here calls a model or opens a network connection.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

SCRIPTS = BATCH_RUNNER_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_agentic_v2_stage as stage  # noqa: E402
from core.cost_receipts import (  # noqa: E402
    CallUsage,
    load_receipt_price_table,
    price_call,
)
from core.execution_envelope_cost import (  # noqa: E402
    PRICE_TABLE_PATH,
    load_price_table,
    load_provider_price_table,
)

# What the six calls the first paid stage never filed actually carried.
UNFILED_INPUT_TOKENS = 17_775
UNFILED_OUTPUT_TOKENS = 292

PINNED_MODEL = "gpt-5.4"

#: Every script that builds a paid client and prices what it spends.
#:
#: All three had the same line. The defect was found reading the first.
PAID_VOICES = (
    "run_agentic_v2_stage.py",
    "run_agentic_stage_a_probe.py",
    "run_agentic_stage_d_probe.py",
)


def a_price_list(tmp_path: Path, providers: dict) -> Path:
    """A committed-shaped file holding only what a case needs."""
    document = {
        "schema_version": "execution-envelope-price-table-v1",
        "currency": "USD",
        "unit": "per 1,000,000 tokens",
        "models": {
            "a-model": {
                "input_usd_per_million": "1.00",
                "output_usd_per_million": "2.00",
            }
        },
        "cost_receipt_schema_version": "cost-receipt-price-table-v1",
        "providers": providers,
    }
    target = tmp_path / "model_price_table.json"
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def a_sourced_entry(**changes) -> dict:
    entry = {
        "input_usd_per_million": "2.50",
        "cached_input_usd_per_million": "0.25",
        "output_usd_per_million": "15.00",
        "reasoning_billed_as": "output",
        "source": "https://prices.azure.com/api/retail/prices",
        "last_reviewed": "2026-08-29",
        "currency": "USD",
        "unit": "per 1,000,000 tokens",
    }
    entry.update(changes)
    return entry


# ---------------------------------------------------------------------------
# The two blocks, as committed
# ---------------------------------------------------------------------------


def test_the_voices_price_list_is_the_one_with_a_source():
    prices = load_provider_price_table("azure")

    assert PINNED_MODEL in prices
    assert prices[PINNED_MODEL].input_usd_per_million == Decimal("2.50")
    assert prices[PINNED_MODEL].output_usd_per_million == Decimal("15.00")


def test_the_sourced_rates_are_the_ones_in_the_committed_file():
    """Read straight out of the file, so this cannot pass on a stale constant."""
    document = json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))
    entry = document["providers"][f"azure:{PINNED_MODEL}"]

    assert entry["source"].startswith("https://prices.azure.com/")
    assert entry["last_reviewed"]
    assert set(entry["meters"]) == {"input", "cached_input", "output"}

    prices = load_provider_price_table("azure")
    assert prices[PINNED_MODEL].input_usd_per_million == Decimal(
        entry["input_usd_per_million"]
    )


def test_the_two_blocks_in_the_one_file_disagree():
    """The measurement the rest of this file rests on.

    If these ever come to agree the disagreement is over and several of the
    comments in this repository need rewriting -- so this test failing would be
    good news that still has to be read.
    """
    planning = load_price_table()[PINNED_MODEL]
    sourced = load_provider_price_table("azure")[PINNED_MODEL]

    assert planning.input_usd_per_million == Decimal("1.25")
    assert planning.output_usd_per_million == Decimal("5.00")
    assert sourced.input_usd_per_million == planning.input_usd_per_million * 2
    assert sourced.output_usd_per_million == planning.output_usd_per_million * 3


# ---------------------------------------------------------------------------
# What the two records now say about the same calls
# ---------------------------------------------------------------------------


def test_the_voice_and_the_ledger_reach_the_same_figure():
    """Two separate paths, same tokens, same amount.

    The voice multiplies through ``ModelPrice.cost_of``; the ledger goes
    through ``price_call``, which slices cached and audio tokens out first.
    The V2 voice reports neither, so the slices are empty and the two
    arithmetics have to land on the same Decimal -- not on a rounding of it.
    """
    usage = CallUsage(
        input_tokens=UNFILED_INPUT_TOKENS, output_tokens=UNFILED_OUTPUT_TOKENS
    )

    by_the_voice = load_provider_price_table("azure")[PINNED_MODEL].cost_of(
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
    )
    by_the_ledger = price_call(
        load_receipt_price_table().lookup("azure", PINNED_MODEL), usage
    )

    assert by_the_ledger.missing_reasons == ()
    assert by_the_ledger.cost_usd == by_the_voice


def test_the_old_list_would_have_reached_a_different_one():
    """What the disagreement was worth, on the tokens that were measured."""
    usage = CallUsage(
        input_tokens=UNFILED_INPUT_TOKENS, output_tokens=UNFILED_OUTPUT_TOKENS
    )
    by_the_ledger = price_call(
        load_receipt_price_table().lookup("azure", PINNED_MODEL), usage
    ).cost_usd
    by_the_planning_block = load_price_table()[PINNED_MODEL].cost_of(
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
    )

    assert by_the_planning_block < by_the_ledger
    # Stated rather than asserted to a rounded literal: the ratio moves if the
    # token mix moves, and the point is the direction and the order.
    assert by_the_ledger > by_the_planning_block * Decimal("1.9")


# ---------------------------------------------------------------------------
# What the loader refuses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["source", "last_reviewed"])
def test_a_rate_nobody_can_trace_is_refused(tmp_path, missing):
    path = a_price_list(
        tmp_path, {f"azure:{PINNED_MODEL}": a_sourced_entry(**{missing: ""})}
    )

    with pytest.raises(ValueError) as refusal:
        load_provider_price_table("azure", path)

    assert missing in str(refusal.value)


@pytest.mark.parametrize("field", ["input_usd_per_million", "output_usd_per_million"])
def test_a_rate_with_a_side_missing_is_refused(tmp_path, field):
    entry = a_sourced_entry()
    del entry[field]
    path = a_price_list(tmp_path, {f"azure:{PINNED_MODEL}": entry})

    with pytest.raises(ValueError) as refusal:
        load_provider_price_table("azure", path)

    assert field in str(refusal.value)


def test_a_provider_nobody_priced_is_refused_rather_than_guessed(tmp_path):
    path = a_price_list(tmp_path, {f"azure:{PINNED_MODEL}": a_sourced_entry()})

    with pytest.raises(ValueError) as refusal:
        load_provider_price_table("some-other-cloud", path)

    assert "some-other-cloud" in str(refusal.value)


def test_a_model_this_provider_does_not_price_is_left_out_not_borrowed(tmp_path):
    """The important negative: no fallback to the unsourced block.

    ``a-model`` is in the planning block of the stand-in file and in no
    provider's. Filling it in from there would turn a call this repository
    cannot price into a number, which is the whole defect wearing a different
    hat.
    """
    path = a_price_list(tmp_path, {f"azure:{PINNED_MODEL}": a_sourced_entry()})

    prices = load_provider_price_table("azure", path)

    assert "a-model" in load_price_table(path)
    assert "a-model" not in prices


def test_a_key_that_names_no_provider_is_refused(tmp_path):
    path = a_price_list(tmp_path, {PINNED_MODEL: a_sourced_entry()})

    with pytest.raises(ValueError) as refusal:
        load_provider_price_table("azure", path)

    assert "provider:model" in str(refusal.value)


@pytest.mark.parametrize("bad", ["", "  ", "azure:gpt-5.4"])
def test_the_argument_names_a_provider_not_a_price_key(bad):
    with pytest.raises(ValueError) as refusal:
        load_provider_price_table(bad)

    assert "provider" in str(refusal.value)


def test_a_file_written_for_another_schema_is_refused(tmp_path):
    document = json.loads(
        a_price_list(
            tmp_path, {f"azure:{PINNED_MODEL}": a_sourced_entry()}
        ).read_text(encoding="utf-8")
    )
    document["cost_receipt_schema_version"] = "something-else-v9"
    target = tmp_path / "wrong_schema.json"
    target.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError) as refusal:
        load_provider_price_table("azure", target)

    assert "something-else-v9" in str(refusal.value)


# ---------------------------------------------------------------------------
# That the paid stage is the thing that changed
# ---------------------------------------------------------------------------


def test_the_paid_stage_names_the_provider_it_is_billed_by():
    assert stage.PAID_VOICE_PRICE_PROVIDER == "azure"
    assert (
        stage.PAID_VOICE_PRICE_PROVIDER
        in load_receipt_price_table().models[f"azure:{PINNED_MODEL}"].key
    )


def test_the_constant_lives_beside_the_loader_and_is_not_copied():
    """One definition, imported by three scripts.

    It was a local in the V2 stage first. Two more scripts build the same Azure
    client and price their own calls, so a second and third copy of the string
    was the obvious next step and the wrong one: a copy is something that can
    disagree, which is the defect this whole file is about.
    """
    from core import execution_envelope_cost

    for script in PAID_VOICES:
        source = (SCRIPTS / script).read_text(encoding="utf-8")
        assert (
            'PAID_VOICE_PRICE_PROVIDER = "' not in source
        ), f"{script} defines its own copy of the constant"

    assert execution_envelope_cost.PAID_VOICE_PRICE_PROVIDER == "azure"


@pytest.mark.parametrize("script", PAID_VOICES)
def test_a_paid_voice_reads_the_sourced_block_and_not_the_planning_one(script):
    """A regression guard on the swap, not on the loader.

    The two loaders' names are close enough to swap back by accident -- the
    module docstring at the call site says so -- and the free job and the paid
    run have to move together, or the dry run certifies a loader the paid run
    does not use.

    Parametrised over all three because the defect was found in one of them and
    the other two had the same line. A fix applied to only the script that was
    being read at the time is how this shape keeps coming back.
    """
    source = (SCRIPTS / script).read_text(encoding="utf-8")

    assert "load_price_table()" not in source
    assert "load_provider_price_table(PAID_VOICE_PRICE_PROVIDER)" in source


def test_the_ceiling_still_reads_the_planning_block():
    """The negative half of the swap, and it is deliberate.

    ``estimate_cost_ceiling`` is a *pre-run* figure and the planning block is
    what the pre-registration's approved amounts were computed from. Swapping it
    here would move a number that has already been approved, which is a
    different decision from fixing what a run reports about calls it made. The
    block is wrong for that purpose too -- the file's own note says it
    understates a ceiling by between two and twelve times -- and that is
    recorded separately rather than folded in here.
    """
    from core import execution_envelope_cost

    source = Path(execution_envelope_cost.__file__).read_text(encoding="utf-8")
    ceiling = source[source.index("def estimate_cost_ceiling(") :]

    assert "else load_price_table()" in ceiling[: ceiling.index("\n    unpriced")]
