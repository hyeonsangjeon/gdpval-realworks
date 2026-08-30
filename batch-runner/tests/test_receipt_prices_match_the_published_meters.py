"""Price real grading usage without calling a model.

Every token count below was read out of a Stage 3 shard artifact — the same
files the grading workflow published — and is named with the shard and task it
came from. Nothing here is invented, and nothing here calls a provider.

Two halves, and the difference between them matters:

* The first half prices those tasks under the model that actually graded them,
  ``gpt-5.6-sol``, which this repository deliberately does not price. It asserts
  that the receipt says so: partial, ``price_missing``, no dollar figure, and
  every call and every token still there. That is what today's published grading
  payloads really contain.
* The second half re-labels the same token counts to ``gpt-5.4``, which the
  table does cover, and asserts the arithmetic to the cent. **Those dollar
  figures are not what the grading run cost.** They are what these tokens would
  have cost had they gone to a model with published rates, and they exist to
  prove the pricing path is right, not to price a run that was never priced.

One structural note on aggregation. Each row below carries a stage's whole
token count rather than its individual calls, because the per-call breakdown
lives in the cost ledger and the grading workflow never publishes it. Charging
a stage's tokens in one row gives the identical figure only because pricing is
linear in tokens. The single thing that would break that linearity is a
context-length tier, where a large call crosses onto a different rate — which
is precisely the axis ``model_price_table.json`` records as an open premise for
``gpt-5.4`` and as the reason ``gpt-5.6-sol`` stays unpriced. So this test is
exact under the table's own stated assumption, and no more exact than that.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from core.cost_receipts import (
    REASON_PRICE_MISSING,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    STATE_SETTLED,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    CallUsage,
    build_receipt,
    load_receipt_price_table,
    price_call,
)

PRICE_TABLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "execution_envelope"
    / "model_price_table.json"
)

# The published meters, restated here so the table cannot be edited and this
# file still pass. Retrieved 2026-08-29 from the Azure Retail Prices API,
# productName "Azure OpenAI GPT5", type Consumption, Standard Global
# deployments at the short-context tier. USD per 1,000,000 tokens.
PUBLISHED_METERS = {
    "azure:gpt-5.4": {
        "input": Decimal("2.50"),
        "cached_input": Decimal("0.25"),
        "output": Decimal("15.00"),
    },
    # The snapshot a request for deployment "gpt-5.4" actually resolves to. It
    # bills on the family meters above, because Azure publishes no dated meter
    # for 5.4 at all -- see test_a_5_4_snapshot_has_no_meter_of_its_own.
    "azure:gpt-5.4-2026-03-05": {
        "input": Decimal("2.50"),
        "cached_input": Decimal("0.25"),
        "output": Decimal("15.00"),
    },
    "azure:gpt-5.4-mini": {
        "input": Decimal("0.75"),
        "cached_input": Decimal("0.075"),
        "output": Decimal("4.50"),
    },
    "azure:gpt-5.4-nano": {
        "input": Decimal("0.20"),
        "cached_input": Decimal("0.02"),
        "output": Decimal("1.25"),
    },
}

# Models this repository is not willing to guess at. Each is absent for its own
# reason, recorded in the table under models_deliberately_not_priced.
UNPRICED = ("gpt-5.6-sol", "gpt-audio-1.5", "gpt-5.4-pro")

MILLION = Decimal(1_000_000)


class RealTask:
    """One task's real published usage, split by the stage that spent it."""

    def __init__(self, label, shard, task_id, calls, stages):
        self.label = label
        self.shard = shard
        self.task_id = task_id
        self.calls = calls
        self.stages = stages  # ((stage, input, cached, output, reasoning), ...)

    @property
    def totals(self):
        return {
            "input_tokens": sum(s[1] for s in self.stages),
            "cached_input_tokens": sum(s[2] for s in self.stages),
            "output_tokens": sum(s[3] for s in self.stages),
            "reasoning_tokens": sum(s[4] for s in self.stages),
        }

    def __repr__(self):  # keeps pytest ids readable
        return self.label


# Five real tasks spanning the whole observed range: the smallest by input, the
# largest, and three in between. Two of them ran perception calls as well as
# judge calls, which is what gives this file a genuine multi-component case.
REAL_TASKS = (
    RealTask(
        "smallest-a328feea",
        "shard-006-of-011",
        "a328feea-47db-4856-b4be-2bdc63dd88fb",
        32,
        ((STAGE_GRADING, 76_600, 58_831, 6_138, 4_058),),
    ),
    RealTask(
        "judge-only-f84ea6ac",
        "shard-005-of-011",
        "f84ea6ac-8f9f-428c-b96c-d0884e30f7c7",
        75,
        ((STAGE_GRADING, 225_011, 160_679, 28_631, 23_878),),
    ),
    RealTask(
        "two-stage-83d10b06",
        "shard-000-of-011",
        "83d10b06-26d1-4636-a32c-23f92c57f30b",
        114,
        (
            (STAGE_GRADING, 3_139_951, 1_096_158, 45_791, 39_050),
            (STAGE_PERCEPTION, 2_777, 0, 454, 0),
        ),
    ),
    RealTask(
        "two-stage-b5d2e6f1",
        "shard-010-of-011",
        "b5d2e6f1-62a2-433a-bcdd-95b260cdd860",
        98,
        (
            (STAGE_GRADING, 4_087_698, 1_931_251, 56_575, 50_359),
            (STAGE_PERCEPTION, 2_777, 0, 300, 0),
        ),
    ),
    RealTask(
        "largest-19403010",
        "shard-010-of-011",
        "19403010-3e5c-494e-a6d3-13594e99f6af",
        177,
        (
            (STAGE_GRADING, 6_144_751, 1_392_720, 68_010, 55_122),
            (STAGE_PERCEPTION, 5_411, 0, 608, 0),
        ),
    ),
)

# What each task's tokens come to under azure:gpt-5.4, worked from the meters
# above. Hard-coded rather than recomputed so that a change to the formula which
# is merely self-consistent still fails. Worked for judge-only-f84ea6ac:
#   billable input = 225,011 - 160,679       = 64,332
#   64,332 x 2.50 + 160,679 x 0.25 + 28,631 x 15.00
#     = 160,830.00 + 40,169.75 + 429,465.00 = 630,464.75 per million
#     = $0.63046475
EXPECTED_UNDER_GPT_5_4 = {
    "smallest-a328feea": Decimal("0.15120025"),
    "judge-only-f84ea6ac": Decimal("0.63046475"),
    "two-stage-83d10b06": Decimal("6.0841395"),
    "two-stage-b5d2e6f1": Decimal("6.73399775"),
    "largest-19403010": Decimal("13.271055"),
}


@pytest.fixture(scope="module")
def table():
    return load_receipt_price_table(PRICE_TABLE_PATH)


def _row(stage, usage, priced):
    """One settled ledger row, shaped the way build_receipt reads them."""
    return {
        "state": STATE_SETTLED,
        "stage": stage,
        "retry_kind": "none",
        "model_cost_usd": None if priced is None else str(priced.cost_usd),
        "missing_reasons": json.dumps(
            list(priced.missing_reasons) if priced else [REASON_PRICE_MISSING]
        ),
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
    }


def _receipt_for(task, model, tbl):
    price = tbl.lookup("azure", model)
    rows = []
    for stage, inp, cached, out, reasoning in task.stages:
        usage = CallUsage(
            input_tokens=inp,
            cached_input_tokens=cached,
            output_tokens=out,
            reasoning_tokens=reasoning,
        )
        rows.append(_row(stage, usage, price_call(price, usage) if price else None))
    return build_receipt(rows, price_table_sha256=tbl.sha256)


# ── What the table says ──────────────────────────────────────────────────


def test_every_rate_is_the_meter_it_claims_to_be(table):
    """A rate that drifts off its published meter fails here, loudly."""
    assert set(table.models) == set(PUBLISHED_METERS)
    for key, meters in PUBLISHED_METERS.items():
        entry = table.models[key]
        assert entry.input_usd_per_million == meters["input"], key
        assert entry.cached_input_usd_per_million == meters["cached_input"], key
        assert entry.output_usd_per_million == meters["output"], key
        # Reasoning is inside the completion count on these deployments, so it
        # must not carry a rate of its own. See the double-charge test below.
        assert entry.reasoning_billed_as == "output", key


def test_a_rate_nobody_can_trace_is_not_a_rate():
    """Every entry has to say where it came from and when that was checked."""
    raw = json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))
    for key, entry in raw["providers"].items():
        assert entry["currency"] == "USD", key
        assert entry["last_reviewed"], key
        assert "prices.azure.com" in entry["source"], key
        # The meter name is what makes the number checkable by someone who does
        # not trust this file. A rate without one is just a number.
        assert set(entry["meters"]) == {"input", "cached_input", "output"}, key
        for kind, meter in entry["meters"].items():
            assert meter.strip(), f"{key}:{kind}"


@pytest.mark.parametrize("model", UNPRICED)
def test_the_models_we_refuse_to_guess_at_stay_absent(table, model):
    """Absence here is the feature. Exact-match lookup, no nearest neighbour."""
    assert table.lookup("azure", model) is None
    raw = json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))
    entry = raw["models_deliberately_not_priced"][f"azure:{model}"]
    assert entry["why_unpriced"].strip()
    assert entry["what_would_settle_it"].strip()


def test_the_resolved_snapshot_is_priceable_and_prices_as_its_family(table):
    """A request for 'gpt-5.4' comes back naming a snapshot, and lookup is exact.

    Run 33302056462 -- the exp026c cost smoke -- asked for deployment
    ``gpt-5.4``, and the reply named ``gpt-5.4-2026-03-05``. Pricing reads the
    model the *reply* reports, and ``ReceiptPriceTable.lookup`` matches the whole
    string with no prefix rule, so the snapshot fell through to
    ``price_missing`` and two paid calls produced no figure.

    The fix is a key, not a rule. Stripping a date suffix in code would make the
    table silently price any future snapshot off its family, which is exactly
    the nearest-neighbour behaviour the table exists to refuse.
    """
    family = table.lookup("azure", "gpt-5.4")
    snapshot = table.lookup("azure", "gpt-5.4-2026-03-05")
    assert snapshot is not None, "the snapshot the deployment resolves to must be priceable"
    assert (
        snapshot.input_usd_per_million,
        snapshot.cached_input_usd_per_million,
        snapshot.output_usd_per_million,
        snapshot.reasoning_billed_as,
    ) == (
        family.input_usd_per_million,
        family.cached_input_usd_per_million,
        family.output_usd_per_million,
        family.reasoning_billed_as,
    )
    # Still exact-match: a neighbouring snapshot nobody has evidence for stays
    # unpriced rather than inheriting these rates.
    assert table.lookup("azure", "gpt-5.4-2026-03-06") is None
    assert table.lookup("azure", "gpt-5.4-2027-01-01") is None


def test_a_5_4_snapshot_has_no_meter_of_its_own(table):
    """The snapshot key is evidence-backed, not a convenience alias.

    Azure publishes 76 meters in the 5.4 family and none of them carries a date.
    That absence only means something because the same product does carry dated
    meters where a snapshot bills separately -- 18 of them, all ``chat-latest``.
    So the family meter is not a substitute for a snapshot meter; it is the only
    published meter a 5.4 snapshot call can bill against.

    Asserted on the recorded reasoning rather than by calling the API, because a
    test that reaches the network would fail for reasons that have nothing to do
    with this repository. The query that re-checks it is written in the entry.
    """
    raw = json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))
    entry = raw["providers"]["azure:gpt-5.4-2026-03-05"]
    assert entry["resolved_snapshot_of"] == "gpt-5.4"
    assert entry["why_this_key_exists"].strip()
    assert "chat-latest" in entry["why_the_family_meter_is_the_right_one"]
    # The meters named must be the family's, not invented snapshot-shaped ones.
    assert entry["meters"] == raw["providers"]["azure:gpt-5.4"]["meters"]


def test_data_zone_is_recorded_as_two_price_points(table):
    """Each Data Zone row must be a pairing some region actually bills.

    Before 2026-08-30 this block held one 5.4 Data Zone row reading 3.00 input /
    0.30 cached / 16.50 output. Azure publishes two Data Zone price points for
    5.4 -- 2.75 / 0.275 / 16.50 across 14 AMER and EMEA regions, and 3.00 / 0.30
    / 18.00 across 9 APAC regions -- and that row took its input from one group
    and its output from the other. No region bills that combination.

    It changed no published figure, because every priced entry here is Global
    and every Global rate re-verified exact. It is the fallback a reader would
    apply the moment the open zone premise resolves, which is the one time a
    wrong alternative does damage.
    """
    meters = json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))["azure_published_meters"]
    rows = meters["gpt-5.4"]
    assert "standard_data_zone" not in rows, "the mixed row must not come back"
    assert rows["standard_data_zone_amer_emea"] == {
        "input": "2.75",
        "cached_input": "0.275",
        "output": "16.50",
    }
    assert rows["standard_data_zone_apac"] == {
        "input": "3.00",
        "cached_input": "0.30",
        "output": "18.00",
    }
    # Both Data Zone groups are a flat multiple of Global. A row that is not a
    # flat multiple is the signature of the defect this test was written for.
    glob = rows["standard_global"]
    for row, factor in (
        (rows["standard_data_zone_amer_emea"], Decimal("1.1")),
        (rows["standard_data_zone_apac"], Decimal("1.2")),
    ):
        for kind in ("input", "cached_input", "output"):
            assert Decimal(row[kind]) == Decimal(glob[kind]) * factor, kind
    # The live entries are Global, so nothing above is what anything was billed
    # at. Guard that, so a future edit cannot quietly move an entry to a zone.
    for key, entry in json.loads(
        PRICE_TABLE_PATH.read_text(encoding="utf-8")
    )["providers"].items():
        assert entry["zone"] == "global", key


def test_the_runtime_block_is_empty_and_says_why():
    """A sourced rate we cannot express is still not a rate we may invent."""
    raw = json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))
    assert raw["runtime"] == {}
    assert "per session" in raw["cost_receipt_caveats"]["runtime"]


# ── The half that reflects what really happened ──────────────────────────


@pytest.mark.parametrize("task", REAL_TASKS, ids=repr)
def test_real_grading_usage_is_recorded_but_not_priced(table, task):
    """The judge model has no published rate here, and the receipt admits it.

    This is the state every published Stage 3 payload is actually in. The point
    of checking it is that "we do not know" has to survive as a distinct answer
    from "it cost nothing".
    """
    receipt = _receipt_for(task, "gpt-5.6-sol", table)

    assert receipt.status == STATUS_PARTIAL
    assert REASON_PRICE_MISSING in receipt.missing_reasons
    assert receipt.known_cost_usd == Decimal(0)
    assert receipt.model_cost_usd == Decimal(0)

    # Nothing that happened may go missing just because it could not be priced.
    assert receipt.usage == task.totals
    assert receipt.model_calls == len(task.stages)
    assert {c.stage for c in receipt.components} == {s[0] for s in task.stages}
    for component in receipt.components:
        assert component.status == STATUS_PARTIAL
        assert REASON_PRICE_MISSING in component.missing_reasons


# ── The half that proves the arithmetic ──────────────────────────────────


@pytest.mark.parametrize("task", REAL_TASKS, ids=repr)
def test_the_same_tokens_price_exactly_under_a_model_we_do_cover(table, task):
    """Re-label to gpt-5.4 and the receipt has to land on the cent.

    Again: this figure is not what grading cost. It is proof that when a model
    IS covered, the number the receipt produces is the number the meters imply.
    """
    receipt = _receipt_for(task, "gpt-5.4", table)

    assert receipt.status == STATUS_COMPLETE
    assert receipt.missing_reasons == ()
    assert receipt.model_cost_usd == EXPECTED_UNDER_GPT_5_4[task.label]

    # Independently of the hard-coded figure, the meters have to reproduce it.
    meters = PUBLISHED_METERS["azure:gpt-5.4"]
    by_hand = sum(
        (
            Decimal(inp - cached) * meters["input"]
            + Decimal(cached) * meters["cached_input"]
            + Decimal(out) * meters["output"]
        )
        for _stage, inp, cached, out, _reasoning in task.stages
    ) / MILLION
    assert receipt.model_cost_usd == by_hand

    assert receipt.usage == task.totals


@pytest.mark.parametrize("task", REAL_TASKS, ids=repr)
def test_the_parts_add_up_to_the_whole(table, task):
    """Components sum to the model cost; model plus runtime is the known cost.

    A receipt whose parts do not add up invites a reader to trust whichever
    number suits them.
    """
    receipt = _receipt_for(task, "gpt-5.4", table)

    assert sum(
        (c.known_cost_usd for c in receipt.components), Decimal(0)
    ) == receipt.model_cost_usd
    assert receipt.known_cost_usd == receipt.model_cost_usd + receipt.runtime_cost_usd
    assert sum(c.model_calls for c in receipt.components) == receipt.model_calls
    for field in task.totals:
        assert (
            sum(c.usage[field] for c in receipt.components) == receipt.usage[field]
        ), field


# ── The two ways a token gets charged twice ──────────────────────────────


def test_cached_input_is_charged_once_and_at_the_cache_rate(table):
    """Cached tokens are part of the input count, not an addition to it.

    Uses judge-only-f84ea6ac's real numbers: 225,011 input of which 160,679 came
    from cache. If those 160,679 were charged at both rates the answer would be
    higher by exactly their cache rate, and if the split were ignored entirely
    it would be higher by the difference between the two rates.
    """
    meters = PUBLISHED_METERS["azure:gpt-5.4"]
    price = table.lookup("azure", "gpt-5.4")
    total, cached, out = 225_011, 160_679, 28_631

    with_cache = price_call(
        price,
        CallUsage(
            input_tokens=total, cached_input_tokens=cached, output_tokens=out
        ),
    ).cost_usd
    without_cache = price_call(
        price,
        CallUsage(input_tokens=total, cached_input_tokens=0, output_tokens=out),
    ).cost_usd

    # The saving is the whole cached block moving from the input rate to the
    # cache rate — no more, which would mean double-charging, and no less,
    # which would mean the cache rate was never applied.
    saving = Decimal(cached) * (meters["input"] - meters["cached_input"]) / MILLION
    assert without_cache - with_cache == saving
    assert with_cache < without_cache

    charged_twice = with_cache + Decimal(cached) * meters["cached_input"] / MILLION
    assert with_cache != charged_twice


def test_reasoning_tokens_do_not_add_a_second_charge(table):
    """These deployments count reasoning inside the completion tokens.

    So the cost has to be blind to the reasoning field. If it moves, the same
    tokens are being billed as output and then again as reasoning.
    """
    price = table.lookup("azure", "gpt-5.4")
    base = dict(input_tokens=225_011, cached_input_tokens=160_679, output_tokens=28_631)

    none_reported = price_call(price, CallUsage(**base, reasoning_tokens=None)).cost_usd
    real = price_call(price, CallUsage(**base, reasoning_tokens=23_878)).cost_usd
    absurd = price_call(price, CallUsage(**base, reasoning_tokens=10_000_000)).cost_usd

    assert none_reported == real == absurd
    assert real == EXPECTED_UNDER_GPT_5_4["judge-only-f84ea6ac"]


# ── The receipt has to name the table it used ────────────────────────────


def test_the_receipt_fingerprints_the_table_that_priced_it(table):
    """The fingerprint has to be the bytes on disk, or it traces to nothing."""
    on_disk = hashlib.sha256(PRICE_TABLE_PATH.read_bytes()).hexdigest()
    assert table.sha256 == on_disk

    receipt = _receipt_for(REAL_TASKS[1], "gpt-5.4", table)
    assert receipt.price_table_sha256 == on_disk
    assert receipt.as_dict()["price_table_sha256"] == on_disk


def test_changing_a_rate_changes_the_fingerprint(table, tmp_path):
    """Otherwise a receipt could name a table whose numbers had since moved."""
    raw = json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))
    raw["providers"]["azure:gpt-5.4"]["output_usd_per_million"] = "16.50"
    altered = tmp_path / "model_price_table.json"
    altered.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    other = load_receipt_price_table(altered)
    assert other.sha256 != table.sha256
    assert other.models["azure:gpt-5.4"].output_usd_per_million == Decimal("16.50")
