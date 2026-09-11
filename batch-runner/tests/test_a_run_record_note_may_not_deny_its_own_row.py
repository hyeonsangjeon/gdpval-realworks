"""A run record's prose may not deny what the same row measured.

`test_a_rate_refusal_arrived_after_the_work_not_before.py` refuted one claim --
that a rate refusal arrives before the model has produced anything -- using
run 34571840967's own numbers. It read those numbers out of
`docs/run_records/exp035_run34571840967_partial/outcomes.json`.

That file was, at the time, asserting the refuted claim in Korean on all ten of
the rows the test was reading:

    요청이 배포에 닿지 못했습니다.   ("the request did not reach the deployment")

and `report.md` said the same thing six lines above the section that refutes
it. The test passed the whole time, because it checked the numbers and never
read the prose sitting beside them. So the refutation and the refuted claim
shipped in one commit, and a reader taking the note at face value concludes
the refused turns were free.

What this test adds is the check that one was missing: a note attached to a
row may not contradict the row it is attached to. It is about *internal*
consistency only. It cannot tell a true note from a false one in general --
that needs evidence from outside the file -- but a record that disagrees with
its own measurements is wrong no matter which half is right.

The phrase list below is a closed set, and a closed set over prose is not a
detector. A new way of wording "it never arrived" will pass this test. It is
worth having anyway: the wordings below are the ones this repository actually
produced, twice, and the failure message names the row's own refuting fields
so the next person fixes the sentence rather than deleting the check.

It also cannot tell an assertion from its negation -- it flagged the
correction notice's own counterfactual ("a request that never reached the
deployment could not have settled") and that sentence had to be reworded. That
cost is deliberate. An exemption for "but I meant the opposite" is exactly the
shape of hole the next occurrence would fit through, so the rule is lexical:
if a record needs to discuss non-arrival, it says so in words that are not the
words of the defect.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RECORDS_DIR = Path(__file__).resolve().parents[1] / "docs" / "run_records"

#: Wordings that assert the request never got to the deployment. Korean first,
#: because that is what the records are written in; the English forms are here
#: because the dashboard module carried the same sentence.
NON_ARRIVAL_PHRASES = (
    "닿지 못",
    "도달하지 못",
    "배포에 도달",
    "did not reach",
    "never reached",
    "never arrived",
    "could not get a call through",
)

#: Fields that, when non-zero, mean the deployment answered. Any one of them is
#: enough: a settled call is a priced reply, output tokens are text the model
#: produced, and a stream item is something the harness received.
ARRIVAL_EVIDENCE = ("calls_settled", "output_tokens", "codex_items_seen")

#: Every string field on a row that is prose rather than a recorded value.
NOTE_FIELDS = ("failure_class_note", "note", "cost_note", "message")


def _record_dirs() -> list[Path]:
    if not RECORDS_DIR.is_dir():
        return []
    return sorted(p for p in RECORDS_DIR.iterdir() if (p / "outcomes.json").is_file())


def _rows(record: Path) -> list[dict]:
    return json.loads((record / "outcomes.json").read_text(encoding="utf-8"))


def _arrival_evidence(row: dict) -> dict[str, int]:
    """The fields on this row that show the deployment answered."""
    return {
        field: row[field]
        for field in ARRIVAL_EVIDENCE
        if isinstance(row.get(field), int) and row[field] > 0
    }


@pytest.mark.parametrize("record", _record_dirs(), ids=lambda p: p.name)
def test_no_note_claims_non_arrival_on_a_row_that_answered(record: Path) -> None:
    offenders = []
    for row in _rows(record):
        evidence = _arrival_evidence(row)
        if not evidence:
            continue
        for field in NOTE_FIELDS:
            text = row.get(field)
            if not isinstance(text, str):
                continue
            hit = next((p for p in NON_ARRIVAL_PHRASES if p in text), None)
            if hit is not None:
                offenders.append((row.get("n"), field, hit, evidence))

    assert offenders == [], (
        f"{len(offenders)} row(s) in {record.name}/outcomes.json say the request "
        "never reached the deployment, on rows that record it answering:\n"
        + "\n".join(
            f"  row {n}: {field} contains {hit!r} but the row has {evidence}"
            for n, field, hit, evidence in offenders
        )
        + "\n\nFix the sentence. A refusal is an answer -- see "
        "test_a_refusal_is_not_an_unreached_call.py. Do not zero the fields to "
        "make the note true."
    )


@pytest.mark.parametrize("record", _record_dirs(), ids=lambda p: p.name)
def test_the_prose_report_does_not_carry_it_either(record: Path) -> None:
    """The same claim in `report.md`, which no per-row check would catch.

    Scoped to records whose rows show the deployment answering. A record of a
    run that genuinely never connected may need to say so.
    """
    report = record / "report.md"
    if not report.is_file():
        pytest.skip(f"{record.name} has no report.md")

    answered = [r for r in _rows(record) if _arrival_evidence(r)]
    if not answered:
        pytest.skip(f"{record.name} has no row showing the deployment answered")

    text = report.read_text(encoding="utf-8")
    found = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        # The correction notice quotes the old wording so the change is
        # legible. Quoted-in-a-table occurrences are the record of the fix,
        # not the claim, and are the one place it is allowed to survive.
        if line.lstrip().startswith("|"):
            continue
        for phrase in NON_ARRIVAL_PHRASES:
            if phrase in line:
                found.append((line_no, phrase, line.strip()))

    assert found == [], (
        f"{record.name}/report.md asserts non-arrival while "
        f"{len(answered)} of its rows record the deployment answering:\n"
        + "\n".join(f"  line {n}: {phrase!r} in {line!r}" for n, phrase, line in found)
    )


def test_the_case_this_was_written_for_is_covered() -> None:
    """Guards the guard: the ten rows it was written for are still findable.

    If the record is renamed or the field disappears, the parametrised tests
    above go green by having nothing to check, which is the failure mode this
    whole file exists to prevent.
    """
    leg1 = RECORDS_DIR / "exp035_run34571840967_partial"
    assert leg1.is_dir(), "the record this test was written against is gone"

    refused = [r for r in _rows(leg1) if r.get("reason") == "rate_limit"]
    assert len(refused) == 10

    # Each one individually refutes non-arrival -- not just the total.
    for row in refused:
        assert row["calls_settled"] >= 3, row["n"]
        assert row["output_tokens"] >= 3489, row["n"]
        assert row["codex_items_seen"] >= 23, row["n"]
        assert isinstance(row.get("failure_class_note"), str)

    assert sum(r["calls_settled"] for r in refused) == 35
    assert sum(r["input_tokens"] for r in refused) == 1_413_072
    assert sum(r["output_tokens"] for r in refused) == 70_573

    # The classification was not what was wrong, and must not be "fixed" by
    # reclassifying these as model failures.
    assert all(r["failure_class"] == "execution_environment" for r in refused)
