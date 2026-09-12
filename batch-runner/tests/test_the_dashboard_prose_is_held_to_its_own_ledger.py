"""The dashboard module's prose is held to the same rule as a run record's.

`test_a_run_record_note_may_not_deny_its_own_row.py` refuses to let a note say
the request never reached the deployment while the row beside it records the
deployment answering. Its phrase list carries English wordings, and its own
docstring says why:

    the English forms are here because the dashboard module carried the same
    sentence.

They were added for `src/lib/failureReason.ts`, and that file was never
scanned. The list reached the dashboard's wording; the check did not reach the
dashboard's file. That is the same shape of gap the file was written about --
the numbers were checked and the prose sitting beside them was not -- one
directory over.

So this closes it, and pins the reading the corrected sentence rests on.

The figures come from two committed sources that were recorded separately and
are joined here for the first time:

  * `results/exp034_codex_foundry_trial30/report/report_data.json` says which
    tasks the run filed as `rate_limited`;
  * `tests/fixtures/run_record/exp034_turn_ledger.json` is run 34540053904's
    cost ledger, verbatim -- its own note says "no value here is constructed or
    recomputed".

Neither was written to answer this question, which is what makes the join
worth having. A refusal that ended a turn the model was already answering
leaves settled calls, output tokens and stream items behind, and all five of
these tasks carry all three. The per-task assertions matter more than the
totals: an aggregate can be carried by one busy task while the rest arrived at
nothing, and that would be a different finding than the one the comment states.

Nothing here contacts a provider.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_a_run_record_note_may_not_deny_its_own_row import (
    NON_ARRIVAL_PHRASES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_MODULE = REPO_ROOT / "src" / "lib" / "failureReason.ts"

REPORT_DATA = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "exp034_codex_foundry_trial30"
    / "report"
    / "report_data.json"
)
TURN_LEDGER = (
    Path(__file__).parent / "fixtures" / "run_record" / "exp034_turn_ledger.json"
)


def _refused_task_ids() -> list[str]:
    """The tasks exp034 filed as `rate_limited`, in the order it recorded them."""
    results = json.loads(REPORT_DATA.read_text(encoding="utf-8"))["task_results"]
    return [
        row["task_id"]
        for row in results
        if (row.get("observability") or {}).get("error_category") == "rate_limited"
    ]


def _ledger_rows() -> list[dict]:
    return json.loads(TURN_LEDGER.read_text(encoding="utf-8"))["rows"]


def test_the_dashboard_module_does_not_assert_non_arrival() -> None:
    """The check the phrase list was extended for, finally pointed at the file."""
    if not DASHBOARD_MODULE.is_file():
        pytest.skip("dashboard module not present in this checkout")

    found = []
    for line_no, line in enumerate(
        DASHBOARD_MODULE.read_text(encoding="utf-8").splitlines(), start=1
    ):
        for phrase in NON_ARRIVAL_PHRASES:
            if phrase in line:
                found.append((line_no, phrase, line.strip()))

    assert found == [], (
        f"{DASHBOARD_MODULE.name} says the request never reached the "
        f"deployment, which exp034's own ledger refutes:\n"
        + "\n".join(f"  line {n}: {phrase!r} in {line!r}" for n, phrase, line in found)
        + "\n\nA refusal is an answer -- see "
        "test_a_refusal_is_not_an_unreached_call.py."
    )


def test_every_refused_task_individually_shows_the_model_answering() -> None:
    """Per task, not in total: each of the five had work under way when it died.

    Four attempts each, the retry ladder run to its end. The one unsettled row
    belongs to the task whose last attempt was cut off before it reported
    usage; the other nineteen all settled, and all nineteen name `gpt-5.4`.
    """
    refused = set(_refused_task_ids())
    assert len(refused) == 5

    by_task: dict[str, list[dict]] = {}
    for row in _ledger_rows():
        if row["task_id"] in refused:
            by_task.setdefault(row["task_id"], []).append(row)

    assert set(by_task) == refused, "a refused task left no ledger row at all"

    for task_id, rows in by_task.items():
        settled = [r for r in rows if r["state"] == "settled"]
        assert len(rows) == 4, f"{task_id}: {len(rows)} attempts"
        assert settled, f"{task_id} settled nothing -- nothing reached it"
        assert sum(r["output_tokens"] or 0 for r in settled) > 0, (
            f"{task_id} produced no output tokens, which would mean the "
            "refusal did arrive before the model wrote anything"
        )
        assert {r["resolved_model"] for r in settled} == {"gpt-5.4"}


def test_the_comment_in_the_dashboard_module_matches_the_ledger() -> None:
    """The four figures the module states, recomputed from the two sources.

    Pinned because the sentence is prose in a TypeScript file that no Python
    test would otherwise read, and prose is exactly what drifted last time.
    """
    refused = set(_refused_task_ids())
    rows = [r for r in _ledger_rows() if r["task_id"] in refused]
    settled = [r for r in rows if r["state"] == "settled"]

    assert len(rows) == 20
    assert len(settled) == 19
    assert sum(r["input_tokens"] or 0 for r in settled) == 898_085
    assert sum(r["output_tokens"] or 0 for r in settled) == 46_693

    if not DASHBOARD_MODULE.is_file():
        pytest.skip("dashboard module not present in this checkout")

    text = DASHBOARD_MODULE.read_text(encoding="utf-8")
    for literal in ("20 ledger rows", "898,085", "46,693", "`gpt-5.4`"):
        assert literal in text, (
            f"{DASHBOARD_MODULE.name} no longer states {literal!r}. If the "
            "sentence was rewritten, update this test with it; if a figure "
            "changed, the ledger did not."
        )


def test_the_run_this_was_measured_on_is_still_the_run_named() -> None:
    """Guards the guard: a renamed fixture would turn the joins above green.

    Both files name the same run in their own words. If one is ever replaced
    with another run's data, the figures above stop describing exp034 and the
    comment they defend stops being about anything.
    """
    ledger = json.loads(TURN_LEDGER.read_text(encoding="utf-8"))
    assert ledger["_run_id"] == "exp034_codex_foundry_trial30:34540053904:1"
    assert len(ledger["rows"]) == 59

    results = json.loads(REPORT_DATA.read_text(encoding="utf-8"))["task_results"]
    assert len(results) == 30
    # Two failure kinds, and they are not the same finding: one is the run
    # place, one is the benchmark working. The comment exists to keep the
    # dashboard from painting them identically.
    categories = [
        (row.get("observability") or {}).get("error_category")
        for row in results
        if row["status"] == "error"
    ]
    assert sorted(categories) == ["content_filtered"] * 3 + ["rate_limited"] * 5
