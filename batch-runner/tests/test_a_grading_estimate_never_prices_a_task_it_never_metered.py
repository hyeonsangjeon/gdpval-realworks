"""A grading estimate may not price a task it never metered.

`scripts/estimate_grading_cost_range.py` bounds what it will cost to grade a
run record. The judge `azure:gpt-5.6-sol` is in `models_deliberately_not_priced`,
so the answer is a range built from Azure's published meters, and two things
about that construction are easy to get quietly wrong.

**The rule can stop holding without anyone noticing.** The bound is only
meaningful if the published meters still reproduce the figures
`PR3_COST_BUDGET.md` recorded for the run it measured. If a rate moves, the
script must refuse rather than emit a number computed from a stale table. The
mutation case below moves one rate by a cent and requires the refusal.

**Three states get collapsed into two.** A reaching task can be one the
reference metered, one the reference took zero judge calls on, or one the
reference does not contain at all. The third has no token history — it is not
"metered at zero" — and folding it into the zero-call row would invent one.
The split test below keeps all three apart.

Nothing here contacts a provider or downloads a snapshot. It reads the meters
from the price table and the committed reference payload, both already in the
tree, and builds the rest by hand.
"""

from __future__ import annotations

import copy
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from estimate_grading_cost_range import (  # noqa: E402
    PUBLISHED_LOWER,
    PUBLISHED_UPPER,
    check_rule,
    meters,
    price,
    split_by_metering,
    usd,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The committed full-220 regrade the published bounds were measured on.
REFERENCE = (
    REPO_ROOT / "data" / "grades" /
    "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_6-sol"
    "__regrade_exp003_v2_sol_max_score_excluded__cfg_71c325eee0e48c13"
    "__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf"
    "__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f"
    "__src_1c967673eb8081a6__v2.2.json"
)


@pytest.fixture(scope="module")
def reference() -> dict:
    if not REFERENCE.exists():
        pytest.skip(f"reference payload not in the tree: {REFERENCE.name}")
    return json.loads(REFERENCE.read_text())


def test_the_published_meters_still_reproduce_the_recorded_bounds(reference):
    """The rule holds on the payload it was recorded against."""
    low, high = meters()
    check_rule(reference, low, high)  # raises SystemExit if it no longer does

    cost = reference["summary"]["cost"]
    triple = (
        cost["total_input_tokens"],
        cost["total_cached_tokens"],
        cost["total_output_tokens"],
    )
    assert usd(price(*triple, low)) == PUBLISHED_LOWER
    assert usd(price(*triple, high)) == PUBLISHED_UPPER


def test_a_rate_that_drifts_by_a_cent_stops_the_estimate(reference):
    """A self-check that never fires is decoration. This one fires."""
    low, high = meters()
    drifted = copy.deepcopy(low)
    drifted["output"] = str(Decimal(low["output"]) + Decimal("0.01"))

    with pytest.raises(SystemExit) as caught:
        check_rule(reference, drifted, high)
    assert "REFUSED" in str(caught.value)


def test_cache_write_is_left_out_of_the_bill():
    """The meter exists; the write-token count does not.

    `gpt-5.6-sol` does bill cache-write, but no receipt records how many tokens
    were written, so pricing it would be invention rather than measurement. The
    rate sits in the table and must stay unread.
    """
    low, _ = meters()
    assert "cache_write" in low, "the table still publishes the meter"

    # 1M uncached input, no cached tokens, no output.
    assert price(1_000_000, 0, 0, low) == Decimal(low["input"])

    # Moving only the cache-write rate changes nothing.
    inflated = dict(low, cache_write="9999.00")
    assert price(400_000, 150_000, 20_000, inflated) == price(
        400_000, 150_000, 20_000, low
    )


def _row(task_id: str, items: list[tuple[int, int, int]]) -> dict:
    return {
        "task_id": task_id,
        "items": [
            {
                "judge_input_tokens": inp,
                "judge_cached_tokens": cached,
                "judge_output_tokens": out,
            }
            for inp, cached, out in items
        ],
    }


def test_a_task_missing_from_the_reference_is_priced_in_neither_row():
    """Absent is not zero. It goes in its own list and buys no items."""
    reference = {
        "tasks": [
            _row("metered", [(1_000, 100, 50), (2_000, 200, 80)]),
            _row("zero-call", [(0, 0, 0), (0, 0, 0), (0, 0, 0)]),
        ]
    }
    measured, converted, absent = split_by_metering(
        ["metered", "zero-call", "never-graded"], reference
    )

    assert absent == ["never-graded"]
    assert measured == {
        "tasks": 1, "items": 2, "input": 3_000, "cached": 300, "output": 130,
    }
    assert converted == {"tasks": 1, "items": 3}

    # The absent task contributed to no row at all, so the two rows still
    # account for exactly the tasks the reference knew about.
    assert measured["tasks"] + converted["tasks"] == 2


def test_a_partly_metered_task_counts_as_measured_not_converted():
    """One item with tokens makes the task measured; its zero items come too.

    The converted row exists for tasks with *no* token history. A task that was
    graded and happens to have a zero-token item is not one of those, and
    splitting it across both rows would double-count its task.
    """
    reference = {"tasks": [_row("partly", [(5_000, 0, 200), (0, 0, 0)])]}
    measured, converted, absent = split_by_metering(["partly"], reference)

    assert absent == []
    assert converted == {"tasks": 0, "items": 0}
    assert measured["tasks"] == 1
    assert measured["items"] == 2, "both items belong to the measured row"
    assert measured["input"] == 5_000
