"""The 5.6-sol entry says the grading ledger survives now. It has to be true.

``models_deliberately_not_priced["azure:gpt-5.6-sol"]`` used to name two things
that would settle the model's price, the first being *publish the grading-side
per-call cost ledger*, which it described as written next to the grade file and
then dying with the runner. That stopped being true when PRs #272 and #327 added
the two ``git add`` calls that stage a ledger beside its grade. The entry now
says so, and records what reading those ledgers bought.

Every figure it records is recomputed here from the ledgers themselves, because
a measurement written into a file by hand is exactly the kind of number that
goes quietly stale -- which is the failure this whole entry is about.

Three things this file is careful about.

**Committed means tracked, not present.** The claim is about what someone gets
from a clone. A directory walk would also pass on a ledger that exists only in
this working tree, so the ledgers are checked with ``git ls-files``.

**Calls are counted by call_id, not by row.** Both the eleven per-shard ledgers
and the merged ledger built from them are committed, so every call in the merged
run is on disk twice and a row count overstates the calls by half. Counting rows
here would have reported 67,378 sol calls where there are 44,875. The duplication
is itself checked: the duplicate total has to be exactly the merged ledger's row
count, which is what "the merge neither invented a call nor dropped one" means.

**The measurement bounds the tier; it does not settle it.** Azure publishes no
context threshold for 5.6-sol, so this file asserts the model is still *unpriced*
alongside asserting the numbers. A future change that used these figures to give
5.6-sol a rate would fail here, which is the point.
"""

import json
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

from core.cost_receipts import load_receipt_price_table


REPO_ROOT = Path(__file__).resolve().parents[2]
PRICE_TABLE_PATH = (
    REPO_ROOT / "batch-runner/experiments/execution_envelope/model_price_table.json"
)
GRADES = REPO_ROOT / "data" / "grades"

#: The model this file is about. Unpriced, and expected to stay that way.
MODEL = "gpt-5.6-sol"

#: The split Azure publishes for the 5.4 sibling. 5.6-sol has no published
#: threshold; this is the only nearby figure any measurement can be held against,
#: and the entry's bound is stated in terms of it.
SIBLING_CONTEXT_SPLIT = 272_000

MILLION = Decimal(1_000_000)


def _load_table():
    return json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def entry():
    return _load_table()["models_deliberately_not_priced"][f"azure:{MODEL}"]


@pytest.fixture(scope="module")
def measured(entry):
    return entry["measured_from_committed_ledgers"]


@pytest.fixture(scope="module")
def ledger_paths():
    """Every committed grading cost ledger, located by shape rather than name."""
    found = sorted(GRADES.rglob("*.cost_ledger.jsonl"))
    assert found, "no grading cost ledgers under data/grades"
    return found


@pytest.fixture(scope="module")
def calls(ledger_paths):
    """Distinct calls across every committed ledger, keyed by call_id."""
    by_id: dict[str, dict] = {}
    duplicates = 0
    rows = 0
    for path in ledger_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows += 1
            record = json.loads(line)
            call_id = record["call_id"]
            if call_id in by_id:
                duplicates += 1
            else:
                by_id[call_id] = record
    return {"by_id": by_id, "rows": rows, "duplicates": duplicates}


def test_the_ledgers_are_committed_and_not_merely_on_disk(ledger_paths):
    """A clone has to get these files, or the entry's first condition is unmet."""
    for path in ledger_paths:
        relative = str(path.relative_to(REPO_ROOT))
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"not tracked by git: {relative}"


def test_the_entry_no_longer_says_the_ledger_dies_with_the_runner(entry):
    """The sentence this change exists to retire must not come back.

    Checked against the live wording rather than a stored copy: the claim is
    stale for as long as the ledgers are committed, whoever rewrites the text.
    """
    settle = entry["what_would_settle_it"]
    assert "dies with the runner" not in settle.replace("described as dying", "")
    # It has to acknowledge the condition is met rather than silently dropping it.
    assert "now met" in settle


def test_the_recorded_counts_recompute_from_the_ledgers(measured, calls, ledger_paths):
    """Hand-written figures are checked against the files they came from."""
    assert measured["ledgers"] == len(ledger_paths)
    assert measured["rows"] == calls["rows"]
    assert measured["distinct_calls"] == len(calls["by_id"])
    assert measured["duplicate_rows"] == calls["duplicates"]


def test_the_duplication_is_the_merge_and_nothing_else(calls, ledger_paths):
    """Every duplicated row is the merged ledger re-stating a shard's call.

    If the duplicate count ever stops equalling the merged ledger's size, either
    the merge dropped a call or something other than the merge is duplicating
    rows. Both are worth failing on.
    """
    merged = [p for p in ledger_paths if "gold_ceiling_185" in p.name]
    assert len(merged) == 1, [p.name for p in merged]
    merged_rows = sum(
        1 for line in merged[0].read_text(encoding="utf-8").splitlines() if line.strip()
    )
    assert calls["duplicates"] == merged_rows


def test_the_per_call_figures_recompute(measured, calls):
    """The numbers that narrowed the tier question."""
    sol = [r for r in calls["by_id"].values() if r.get("resolved_model") == MODEL]
    assert measured["gpt_5_6_sol_calls"] == len(sol)
    inputs = [r["input_tokens"] for r in sol]
    assert measured["max_single_request_input_tokens"] == max(inputs)
    assert measured["calls_over_128k"] == sum(1 for v in inputs if v > 128_000)
    assert measured["calls_over_200k"] == sum(1 for v in inputs if v > 200_000)
    assert measured["calls_over_272k"] == sum(1 for v in inputs if v > 272_000)


def test_no_committed_request_reaches_the_sibling_split(measured, calls):
    """The bound the entry states, held against the data rather than the prose.

    This is the assertion that would break first if a later run sent a request
    large enough to make the tier matter. Breaking is correct: the entry's
    ``what_it_bounds`` sentence would no longer be true.
    """
    sol = [r for r in calls["by_id"].values() if r.get("resolved_model") == MODEL]
    biggest = max(r["input_tokens"] for r in sol)
    assert biggest < SIBLING_CONTEXT_SPLIT
    assert measured["calls_over_272k"] == 0
    assert str(SIBLING_CONTEXT_SPLIT) in measured["what_it_bounds"].replace(",", "")


def test_the_stated_dollar_bound_recomputes_from_the_published_meters(measured):
    """$549.50 to $980.84 is arithmetic on the merged run, not an estimate."""
    raw = _load_table()
    meters = raw["azure_published_meters"][MODEL]
    merged = sorted(GRADES.rglob("*gold_ceiling_185*.cost_ledger.jsonl"))
    assert len(merged) == 1
    rows = [
        json.loads(line)
        for line in merged[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    sol = [r for r in rows if r.get("resolved_model") == MODEL]
    cached = sum(r["cached_input_tokens"] for r in sol)
    uncached = sum(r["input_tokens"] for r in sol) - cached
    output = sum(r["output_tokens"] for r in sol)

    def total(tier):
        rate = meters[tier]
        return (
            Decimal(uncached) / MILLION * Decimal(rate["input"])
            + Decimal(cached) / MILLION * Decimal(rate["cached_input"])
            + Decimal(output) / MILLION * Decimal(rate["output"])
        )

    low = total("short_context_standard_global")
    high = total("long_context_standard_global")
    assert f"${low:,.2f}" in measured["what_it_bounds"]
    assert f"${high:,.2f}" in measured["what_it_bounds"]
    # The bound is only a bound if the two ends really differ.
    assert low < high


def test_the_measurement_did_not_become_a_price():
    """Bounding the tier is not settling it. The model stays unpriced.

    The whole risk of writing these numbers down is that a later reader treats a
    narrow range as licence to pick a rate. ``ReceiptPriceTable`` is asked
    directly, so this fails on the behaviour and not on the JSON shape.
    """
    table = load_receipt_price_table(PRICE_TABLE_PATH)
    assert table.lookup("azure", MODEL) is None
    entry = _load_table()["models_deliberately_not_priced"][f"azure:{MODEL}"]
    assert "unpriced" in entry["measured_from_committed_ledgers"]["what_it_settles"]


def test_the_two_axes_the_measurement_cannot_touch_are_still_named(entry):
    """Zone and cache writes are untouched by any token count.

    The tier was the axis a measurement could speak to. These two are not, and
    an entry that quietly stopped naming them would read as though committing
    the ledgers had settled more than it did.
    """
    why = entry["why_unpriced"]
    assert "zone" in why
    assert "cache write" in why
    # The count is stated twice, opening and closing. Checking only one of them
    # let a negative control through: rewriting "Three axes are open." to "One
    # axis is open." left the closing "three open axes" intact and passed.
    assert "Three axes are open" in why
    assert "three open axes" in why
