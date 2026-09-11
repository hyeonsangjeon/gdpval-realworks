"""The run's own record contradicts what its config says a rate refusal is.

`experiments/exp035_codex_foundry_full220.yaml` carries a mechanism note,
written before the 220-task run, that dismisses a hypothesis by asserting:

    a rate refusal arrives before the model has produced anything at all.
    The length of the statement cannot be a cause of 5 of the 8.

Run 34571840967 answers that, and the answer is no. Two independent parts of
what the run left behind say so:

  * The cost ledger prices $3.0306 of tokens against the ten tasks that ended
    in a rate refusal -- a fifth of everything the run spent, on tasks that
    produced no file. Tokens are not consumed by a request that was turned
    away before the model ran.

  * The checkpoint records `observability.codex.items_seen` per task: how many
    items the Codex stream delivered before the task ended. Every one of the
    ten rate-refused tasks has a non-zero count, and their median is 35 --
    against 34.5 for the thirty that succeeded. A refused task had got as far
    as a successful one before the refusal landed.

The note's *conclusion* about statement length may still stand; the run's own
statistics rejected that hypothesis separately and on their own evidence. What
is refuted is the mechanism offered for it, and mechanisms get reused. Left
unchallenged, "the refusal arrives before anything happens" also implies the
refused attempts were free, and implies the limit is reached at the start of a
turn rather than during it -- both of which would send the next fix in the
wrong direction.

The config file is deliberately not edited here. It is the record of how a run
that is still relaying was launched, and this repository's rule is that a
stage is a separate run with its own record, not an edit to the stage before
it. So the correction lives with the run that produced it, and this test is
what keeps it from being quietly dropped.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import pytest

RECORD = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "run_records"
    / "exp035_run34571840967_partial"
    / "outcomes.json"
)

SEEN = "codex_items_seen"


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def _by_reason(rows: list[dict], reason: str) -> list[dict]:
    return [r for r in rows if r.get("attempted") and r.get("reason") == reason]


def test_no_rate_refused_task_was_turned_away_empty_handed(rows):
    """The claim under test, stated as the data would have to look for it.

    If a rate refusal really arrived before the model produced anything, every
    one of these tasks would carry a zero. Not one does.
    """
    refused = _by_reason(rows, "rate_limit")
    assert len(refused) == 10

    empty = [r["task_id"] for r in refused if r[SEEN] == 0]
    assert empty == [], (
        f"{len(empty)} rate-refused task(s) produced nothing before the "
        "refusal. If this ever becomes true, the config's mechanism note is "
        "right after all and this test should be deleted rather than fixed."
    )
    assert min(r[SEEN] for r in refused) >= 1


def test_a_refused_task_had_got_as_far_as_a_successful_one(rows):
    """Not merely non-zero -- indistinguishable from the tasks that finished.

    This is the part that rules out "it produced a little, then was refused
    early". The two groups sit on top of each other.
    """
    refused = [r[SEEN] for r in _by_reason(rows, "rate_limit")]
    finished = [r[SEEN] for r in rows if r.get("outcome") == "ok"]
    assert len(finished) == 30

    assert statistics.median(refused) == 35
    assert statistics.median(finished) == 34.5
    # The refused group is not a truncated prefix of the successful one: its
    # median is higher, and its span sits inside the successful span.
    assert statistics.median(refused) >= statistics.median(finished)
    assert min(finished) < min(refused)
    assert max(refused) <= max(finished)


def test_the_refused_tasks_spent_real_money_for_no_file(rows):
    """The ledger's half of the same answer, from a different file entirely."""
    refused = _by_reason(rows, "rate_limit")
    spent = sum(
        r["derived_cost_usd_from_measured_tokens"]
        for r in refused
        if r["derived_cost_usd_from_measured_tokens"] is not None
    )
    assert spent == pytest.approx(3.0306, abs=5e-4)
    # Nothing to show for it. If a refusal came before the model ran, this
    # would be the contradiction on its own.
    assert all(r["deliverable_file_count"] == 0 for r in refused)
    assert all(r["input_tokens"] > 0 for r in refused)


def test_the_count_is_recorded_for_every_task_that_was_attempted(rows):
    """A per-task fact belongs on the task, not only in the prose."""
    attempted = [r for r in rows if r.get("attempted")]
    assert len(attempted) == 45
    assert all(isinstance(r[SEEN], int) for r in attempted)

    # A task that never ran has no stream to have seen anything on. It must
    # not carry a zero, which would read as "it ran and produced nothing".
    never = [r for r in rows if not r.get("attempted")]
    assert len(never) == 175
    assert all(SEEN not in r for r in never)


def test_the_record_states_the_contradiction_in_words(rows):
    """Data nobody explains gets re-explained wrongly by the next reader."""
    report = (RECORD.parent / "report.md").read_text(encoding="utf-8")
    assert SEEN in report
    assert "$3.0306" in report
