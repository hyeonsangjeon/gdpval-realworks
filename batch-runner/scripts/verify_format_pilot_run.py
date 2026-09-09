#!/usr/bin/env python3
"""Judge the V3 format pilot against 344 section 6, from the run's own files.

344 asks one question: does the candidate observation header come back as
readable JSON where 337's did not. The answer is a count, and a count is easy
to read the way you were hoping. So the reading is written down here, before
the run, and done by a program afterwards.

It reads the run's JSON report and the ledger export beside it, and nothing
else. No model call, no credential, no network::

    cd batch-runner
    python scripts/verify_format_pilot_run.py path/to/report.json
    python scripts/verify_format_pilot_run.py path/to/report.json --json

Four things this tool refuses to do, each of which would turn a small format
test into a claim it cannot support:

**It will not let a rehearsal answer the question.** A ``--dry-run`` sends the
same ten requests through the same code to a stub, and the stub's replies are
canned: they say nothing about what ``gpt-audio-1.5`` does with the candidate
header. So on a rehearsal the two arm conditions are **unanswerable**, not
passed -- a free run that reported ``format_held`` would be the whole
experiment replaced by its own scaffolding. What a rehearsal *can* answer it
is still held to: the pins, the ten requests, one request per call and the
ledger are checked exactly as on a paid run, and a rehearsal that breaks one
of them is ``inconclusive`` rather than ``rehearsal_ok``. Free is not a reason
to wave it through -- clearing a paid dispatch is the only thing a rehearsal
is for.

**It will not lower the bar after seeing the number.** The candidate needs
5 of 5 readable. 4 of 5 is ``format_lost``, and this tool has no flag, no
environment variable and no rounding that makes it anything else. 344 section
6 says failure is not grounds for re-ordering, and a checker with a knob on it
is grounds for re-ordering.

**It will not read a collapsed control arm as a result.** If the production
arm came back under 4 of 5, the run says nothing about the candidate in either
direction -- the comparison it was built on is not there. That is
``inconclusive``, and so is a run whose ten planned requests did not all go
out. Inconclusive is not a pass: money was spent and the question is open.

**It will not judge the grading.** Whether a verdict was *right* is 337/338's
question and stays out of this. The gate is the envelope: did a reply parse.
The usable-verdict count is reported beside it, plainly marked as reported and
not gated, because a reader who wants it should not have to recompute it and a
reader who does not want it should not be able to mistake it for the gate.

Exit codes: ``0`` the run is sound and either held or was a rehearsal, ``1``
the candidate lost or the run could not answer, ``2`` the files could not be
read or do not describe this experiment. Read ``verdict``, not the status, for
what was actually learned.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "batch-runner" / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "batch-runner" / "scripts"))

#: The pre-registration this tool enforces. Overridable on the command line
#: only so the tests can point it at a fixture; the default is the document,
#: and a run judged against anything else says so in its own output.
PREREG = (
    REPO_ROOT / "tasks" / "rebuilding_grading_task"
    / "344-the-order-with-no-destination.md"
)

#: The header name the report has to carry for this to be the V3 pilot at all.
#: 337's report carries ``SPEECH_OBSERVATION_HEADER_V2`` in the same field, and
#: judging 337's numbers against 344's table is exactly the substitution a
#: pre-registration exists to prevent -- so that is a refusal, not a failure.
CANDIDATE_HEADER_NAME = "SPEECH_OBSERVATION_HEADER_V3"

CONTROL_ARM = "production"
CANDIDATE_ARM = "observation"

#: 344 section 2: five claims, one repeat, two arms.
PLANNED_ITEMS = 5
PLANNED_CALLS = 10

#: 344 section 6, and the reason each number is what it is.
#:
#: The candidate needs every one. That is 337's bar, restated: a header that
#: loses one envelope in five has not fixed the defect 337 found, it has moved
#: it. The control needs four of five because it is a sanity check on the run
#: and not a standard for the candidate -- 334 measured production at 59/60
#: and 339 at 5/5, so a control below four of five means something is wrong
#: with this run rather than with either prompt.
CANDIDATE_READABLE_REQUIRED = 5
CONTROL_READABLE_REQUIRED = 4

#: An answer that did not survive being read. These two are the failure 344 is
#: about: the reply came back and the envelope did not parse, or the provider
#: never produced one.
#:
#: ``declined_to_judge`` is deliberately **not** here. A judge that returns a
#: well-formed envelope saying it will not judge has kept the format contract,
#: which is the only thing this experiment measures. Counting it as a format
#: failure would have scored 337's observation arm 0/5 instead of 1/5 and
#: would score a candidate that declines five times as a loss when the
#: envelope held every time.
UNREADABLE_KINDS = ("read_failure", "provider_failure")

#: What ``verdict`` values mean an answer was actually produced. Reported, not
#: gated -- see the module docstring.
USABLE_VERDICTS = ("pass", "partial", "fail")

RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_UNANSWERABLE = "unanswerable"

#: Why a condition could not be answered. ``rehearsal`` is the only one that
#: is not a defect: it is the stub having nothing to say about a real model.
UNANSWERABLE_REHEARSAL = "rehearsal"
UNANSWERABLE_CONTROL_COLLAPSED = "control_collapsed"
UNANSWERABLE_RUN_INCOMPLETE = "run_incomplete"

VERDICT_FORMAT_HELD = "format_held"
VERDICT_FORMAT_LOST = "format_lost"
VERDICT_INCONCLUSIVE = "inconclusive"
VERDICT_REHEARSAL_OK = "rehearsal_ok"

_MARK = {
    RESULT_PASS: "PASS",
    RESULT_FAIL: "FAIL",
    RESULT_UNANSWERABLE: "N/A ",
}


class ReportUnreadable(Exception):
    """The report is not the run this tool was written to judge."""


class Condition:
    """One check, with the counts that decided it.

    ``data`` carries counts and digests only. No prompt text, no response
    body, no request identifier -- the report does not hold those in the
    fields this tool reads and it does not invent a place to put them.
    """

    def __init__(
        self,
        number: int,
        title: str,
        result: str,
        detail: str,
        data: Any = None,
        unanswerable_because: Optional[str] = None,
    ) -> None:
        self.number = number
        self.title = title
        self.result = result
        self.detail = detail
        self.data = data
        self.unanswerable_because = unanswerable_because

    def as_dict(self) -> dict[str, Any]:
        return {
            "condition": self.number,
            "title": self.title,
            "result": self.result,
            "detail": self.detail,
            "unanswerable_because": self.unanswerable_because,
            "data": self.data,
        }


def _passed(number: int, title: str, detail: str, data: Any = None) -> Condition:
    return Condition(number, title, RESULT_PASS, detail, data)


def _failed(number: int, title: str, detail: str, data: Any = None) -> Condition:
    return Condition(number, title, RESULT_FAIL, detail, data)


def _unanswerable(
    number: int, title: str, detail: str, because: str, data: Any = None
) -> Condition:
    return Condition(
        number, title, RESULT_UNANSWERABLE, detail, data,
        unanswerable_because=because,
    )


# ── reading the pair ─────────────────────────────────────────────────────


def load_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReportUnreadable(f"{path} could not be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReportUnreadable(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReportUnreadable(f"{path} is not a report object")

    pins = payload.get("pins")
    if not isinstance(pins, dict):
        raise ReportUnreadable(
            f"{path} has no pins block, so there is nothing in it that says "
            f"which experiment it is."
        )
    name = pins.get("observation_header_name")
    if name != CANDIDATE_HEADER_NAME:
        raise ReportUnreadable(
            f"{path} is not the V3 pilot: its pins name "
            f"{name!r} as the second arm's header, not "
            f"{CANDIDATE_HEADER_NAME!r}. 337's report carries "
            f"'SPEECH_OBSERVATION_HEADER_V2' in this field and its arm counts "
            f"look like the ones below; judging it against 344's table would "
            f"read one experiment's numbers off another's plan."
        )
    if not isinstance(payload.get("calls"), list):
        raise ReportUnreadable(f"{path} has no per-call list to count")
    return payload


def candidate_pin(prereg: Path) -> str:
    """The candidate header digest the pre-registration names.

    Read through the measurer's own reader rather than a second regex here.
    Two readers of one markdown table drift, and the one that drifts is
    always the one nobody dispatched with.

    Absent is refused rather than compared. ``candidate_pin_stated_in``
    returns ``None`` for the documents written before that row existed --
    333, 337, 338 -- and letting a ``None`` reach the comparison would turn
    "this is the wrong document" into "condition 1 failed", which sends the
    reader to the run instead of to the file they passed on the command line.
    """
    import measure_audio_grading_accuracy as probe  # noqa: PLC0415

    pinned = probe.candidate_pin_stated_in(prereg)
    if pinned is None:
        raise ReportUnreadable(
            f"{prereg} pins no candidate header, so it is not 344 and there "
            f"is nothing here to hold a run to"
        )
    return pinned


def grader_pin(prereg: Path) -> str:
    """The grader fingerprint the pre-registration names."""
    import measure_audio_grading_accuracy as probe  # noqa: PLC0415

    return probe.grader_pin_stated_in(prereg)


def _calls_of(report: dict[str, Any], arm: str) -> list[dict[str, Any]]:
    return [
        call for call in report.get("calls") or []
        if isinstance(call, dict) and call.get("arm") == arm
    ]


def readable_count(calls: Sequence[dict[str, Any]]) -> int:
    """How many replies parsed as the envelope the contract asks for."""
    return sum(1 for call in calls if call.get("unanswered_kind") not in UNREADABLE_KINDS)


def usable_count(calls: Sequence[dict[str, Any]]) -> int:
    """How many produced a verdict. Reported; never gated on."""
    return sum(1 for call in calls if call.get("verdict") in USABLE_VERDICTS)


def _kind_census(calls: Sequence[dict[str, Any]]) -> dict[str, int]:
    census: dict[str, int] = {}
    for call in calls:
        key = str(call.get("unanswered_kind") or "answered")
        census[key] = census.get(key, 0) + 1
    return census


def requests_sent(report: dict[str, Any]) -> Optional[int]:
    """How many requests left the process, from the run's own wire record.

    From the wire summaries and not from the number of calls, for the reason
    ``verify_audio_metering_run`` gives: one call can be two requests, and a
    request that raised in transport produced no call at all. Under 344 those
    are the same fact -- the request discipline says one request per call and
    nothing else -- so a mismatch here is what condition 3 is for.
    """
    total = 0
    seen = False
    for call in report.get("calls") or []:
        wire = call.get("wire")
        if not isinstance(wire, dict):
            continue
        count = wire.get("requests")
        if not isinstance(count, int):
            continue
        seen = True
        total += count
    return total if seen else None


# ── the conditions ───────────────────────────────────────────────────────


def condition_1(report: dict[str, Any], prereg: Path) -> Condition:
    """The header that went out is the one the document registered."""
    pins = report.get("pins") or {}
    sent = pins.get("observation_header_sha256")
    try:
        pinned = candidate_pin(prereg)
    except (OSError, ValueError) as exc:
        return _failed(
            1, "the candidate header is the registered one",
            f"the pre-registration could not be read for its candidate pin: "
            f"{type(exc).__name__}: {exc}",
        )
    data = {"report": sent, "prereg": pinned, "name": pins.get("observation_header_name")}
    if sent == pinned:
        return _passed(
            1, "the candidate header is the registered one",
            f"{CANDIDATE_HEADER_NAME}, {str(pinned)[:16]}…, in both places.",
            data,
        )
    return _failed(
        1, "the candidate header is the registered one",
        f"the run sent {str(sent)[:16]}… and {prereg.name} registered "
        f"{str(pinned)[:16]}…. The string was edited between registration and "
        f"dispatch, so whatever this run measured is not what was agreed to.",
        data,
    )


def condition_2(report: dict[str, Any], prereg: Path) -> Condition:
    """The grader is the one the document pinned."""
    pins = report.get("pins") or {}
    ran = pins.get("grader_source_sha256")
    try:
        pinned = grader_pin(prereg)
    except (OSError, ValueError) as exc:
        return _failed(
            2, "the grader is the pinned one",
            f"the pre-registration could not be read for its grader pin: "
            f"{type(exc).__name__}: {exc}",
        )
    data = {"report": ran, "prereg": pinned}
    if ran == pinned:
        return _passed(
            2, "the grader is the pinned one",
            f"{str(pinned)[:16]}… in both places.", data,
        )
    return _failed(
        2, "the grader is the pinned one",
        f"the run graded with {str(ran)[:16]}… and {prereg.name} pins "
        f"{str(pinned)[:16]}…. Something under core/ moved between the two, "
        f"and this run's numbers belong to code the document does not "
        f"describe.",
        data,
    )


def condition_3(report: dict[str, Any]) -> Condition:
    """All ten planned requests went out, one per call, and none was a retry."""
    planned = report.get("calls_planned")
    stopped = report.get("stopped")
    calls = report.get("calls") or []
    sent = requests_sent(report)
    retried = [
        {
            "arm": call.get("arm"),
            "claim_id": call.get("claim_id"),
            "requests": (call.get("wire") or {}).get("requests"),
        }
        for call in calls
        if isinstance(call.get("wire"), dict)
        and isinstance((call["wire"]).get("requests"), int)
        and call["wire"]["requests"] > 1
    ]
    data = {
        "calls_planned": planned,
        "calls_recorded": len(calls),
        "requests_sent": sent,
        "stopped": stopped,
        "calls_that_retried": retried,
    }
    if stopped is not None:
        return _failed(
            3, "the ten planned requests all went out",
            f"the run stopped early ({stopped}). 344 section 6 makes a "
            f"short run inconclusive rather than a result, because the arms "
            f"it did finish are not the comparison that was registered.",
            data,
        )
    if planned != PLANNED_CALLS or len(calls) != PLANNED_CALLS:
        return _failed(
            3, "the ten planned requests all went out",
            f"the plan was {PLANNED_CALLS} calls; the report says "
            f"{planned} planned and carries {len(calls)}.",
            data,
        )
    if sent is None:
        return _failed(
            3, "the ten planned requests all went out",
            "no wire record at all, so how many requests left the process is "
            "not recorded and cannot be reconstructed from the verdicts.",
            data,
        )
    if retried:
        return _failed(
            3, "the ten planned requests all went out",
            f"{len(retried)} call(s) sent more than one request. 344 section 2 "
            f"pins SDK retries to 0 and the failure budget to 1, which is one "
            f"request per call; a retried call means the discipline did not "
            f"hold and the arms were not asked the same number of times.",
            data,
        )
    if sent != PLANNED_CALLS:
        return _failed(
            3, "the ten planned requests all went out",
            f"{sent} request(s) left the process against {PLANNED_CALLS} "
            f"planned.",
            data,
        )
    return _passed(
        3, "the ten planned requests all went out",
        f"{sent} requests, {len(calls)} calls, one request each, no early stop.",
        data,
    )


def condition_4(report: dict[str, Any]) -> Condition:
    """Both arms are there, five items each, same five claims in both."""
    control = _calls_of(report, CONTROL_ARM)
    candidate = _calls_of(report, CANDIDATE_ARM)
    control_ids = [call.get("claim_id") for call in control]
    candidate_ids = [call.get("claim_id") for call in candidate]
    data = {
        "control_calls": len(control),
        "candidate_calls": len(candidate),
        "control_claims": control_ids,
        "candidate_claims": candidate_ids,
    }
    if len(control) != PLANNED_ITEMS or len(candidate) != PLANNED_ITEMS:
        return _failed(
            4, "both arms ran the same five items",
            f"{CONTROL_ARM} has {len(control)} call(s) and {CANDIDATE_ARM} has "
            f"{len(candidate)}; {PLANNED_ITEMS} each was registered.",
            data,
        )
    if sorted(str(i) for i in control_ids) != sorted(str(i) for i in candidate_ids):
        return _failed(
            4, "both arms ran the same five items",
            "the arms did not run the same claims, so the comparison between "
            "them is between two different questions.",
            data,
        )
    return _passed(
        4, "both arms ran the same five items",
        f"{PLANNED_ITEMS} claims, both arms, same five.",
        data,
    )


def condition_5(report: dict[str, Any], *, measured: bool) -> Condition:
    """The control arm still works -- the sanity check, not the question."""
    calls = _calls_of(report, CONTROL_ARM)
    readable = readable_count(calls)
    data = {
        "readable": readable,
        "of": len(calls),
        "required": CONTROL_READABLE_REQUIRED,
        "usable_reported_not_gated": usable_count(calls),
        "unanswered_by_kind": _kind_census(calls),
    }
    title = "the production arm came back readable at least 4 of 5"
    if not measured:
        return _unanswerable(
            5, title,
            "a rehearsal's replies come from the stub, so this says nothing "
            "about whether the production prompt still parses against "
            "gpt-audio-1.5.",
            UNANSWERABLE_REHEARSAL, data,
        )
    if readable >= CONTROL_READABLE_REQUIRED:
        return _passed(
            5, title,
            f"{readable}/{len(calls)} readable. The control arm behaved, so "
            f"the candidate's number below is about the candidate.",
            data,
        )
    return _failed(
        5, title,
        f"{readable}/{len(calls)} readable, under the {CONTROL_READABLE_REQUIRED} "
        f"this run needed to be a comparison at all. Something is wrong with "
        f"the run rather than with either prompt: 334 measured this arm at "
        f"59/60 and 339 at 5/5.",
        data,
    )


def condition_6(
    report: dict[str, Any], *, measured: bool, control_ok: bool
) -> Condition:
    """The question. Five of five, or the candidate is closed."""
    calls = _calls_of(report, CANDIDATE_ARM)
    readable = readable_count(calls)
    data = {
        "readable": readable,
        "of": len(calls),
        "required": CANDIDATE_READABLE_REQUIRED,
        "usable_reported_not_gated": usable_count(calls),
        "unanswered_by_kind": _kind_census(calls),
    }
    title = "the candidate arm came back readable 5 of 5"
    if not measured:
        return _unanswerable(
            6, title,
            "a rehearsal cannot answer this. The stub's replies are canned, "
            "and the whole question is what the real deployment does with the "
            "candidate header.",
            UNANSWERABLE_REHEARSAL, data,
        )
    if not control_ok:
        return _unanswerable(
            6, title,
            f"the control arm collapsed, so this run says nothing about the "
            f"candidate in either direction. The count was "
            f"{readable}/{len(calls)} and it is recorded rather than read.",
            UNANSWERABLE_CONTROL_COLLAPSED, data,
        )
    if readable >= CANDIDATE_READABLE_REQUIRED:
        return _passed(
            6, title,
            f"{readable}/{len(calls)} readable. 337's V2 arm was 1/5 on the "
            f"same five clips.",
            data,
        )
    return _failed(
        6, title,
        f"{readable}/{len(calls)} readable, under the "
        f"{CANDIDATE_READABLE_REQUIRED} registered. The candidate is closed: "
        f"344 section 6 says a near miss is a loss and is not grounds for "
        f"re-ordering.",
        data,
    )


def condition_7(report: dict[str, Any], *, measured: bool) -> Condition:
    """The spend was written down, whatever it came to."""
    cost = report.get("cost")
    ledger = (cost or {}).get("ledger") if isinstance(cost, dict) else None
    data = {"ledger": ledger}
    title = "the run wrote a cost ledger"
    if not isinstance(cost, dict):
        return _failed(
            7, title,
            "the report has no cost block at all, which is what 340 found on "
            "337: ten paid calls and no row anywhere.",
            data,
        )
    if not ledger:
        detail = (
            "no ledger reference in the cost block. 344 section 2 makes "
            "--cost-ledger required, so a run without one was not dispatched "
            "as registered."
        )
        return _failed(7, title, detail, data)
    receipt = cost.get("receipt") or {}
    amount = cost.get("estimated_cost_usd")
    data["receipt_status"] = receipt.get("status")
    data["estimated_cost_usd"] = amount
    if measured and amount == 0:
        return _failed(
            7, title,
            "the report puts this paid run's cost at exactly 0. gpt-audio-1.5 "
            "has no published rate, so the honest record is a partial receipt "
            "with a null amount. A zero is a price claim nobody can support.",
            data,
        )
    return _passed(
        7, title,
        f"ledger recorded, receipt {receipt.get('status')!r}, amount "
        f"{amount!r} (null is correct while gpt-audio-1.5 is unpriced).",
        data,
    )


# ── putting it together ──────────────────────────────────────────────────


def verdict_of(conditions: Sequence[Condition], *, measured: bool) -> str:
    """344 section 6's table, and nothing outside it.

    Order matters twice.

    The structural conditions are read **before** the rehearsal branch. A
    rehearsal exists to show the pipeline is sound before money goes near it,
    so a rehearsal whose requests did not go out one per call has shown the
    opposite and must not hand back the word that means "cleared to
    dispatch". It is ``inconclusive`` -- free, and still not a green light.

    ``format_lost`` is reachable only when condition 5 passed. A candidate
    that missed while the control was also broken is a run that failed, not a
    candidate that lost, and closing the candidate on it would close it on no
    evidence.
    """
    by_number = {condition.number: condition for condition in conditions}
    structural = [1, 2, 3, 4, 7]
    if any(by_number[n].result == RESULT_FAIL for n in structural if n in by_number):
        return VERDICT_INCONCLUSIVE
    if not measured:
        return VERDICT_REHEARSAL_OK
    control = by_number.get(5)
    candidate = by_number.get(6)
    if control is None or control.result != RESULT_PASS:
        return VERDICT_INCONCLUSIVE
    if candidate is None or candidate.result == RESULT_UNANSWERABLE:
        return VERDICT_INCONCLUSIVE
    return (
        VERDICT_FORMAT_HELD
        if candidate.result == RESULT_PASS
        else VERDICT_FORMAT_LOST
    )


def check(report_path: Path, prereg: Path = PREREG) -> dict[str, Any]:
    report = load_report(report_path)
    measured = bool(report.get("measured"))

    conditions = [
        condition_1(report, prereg),
        condition_2(report, prereg),
        condition_3(report),
        condition_4(report),
    ]
    control = condition_5(report, measured=measured)
    conditions.append(control)
    conditions.append(
        condition_6(
            report, measured=measured, control_ok=control.result == RESULT_PASS
        )
    )
    conditions.append(condition_7(report, measured=measured))

    counts = {
        "passed": sum(1 for c in conditions if c.result == RESULT_PASS),
        "failed": sum(1 for c in conditions if c.result == RESULT_FAIL),
        "unanswerable": sum(
            1 for c in conditions if c.result == RESULT_UNANSWERABLE
        ),
    }
    control_calls = _calls_of(report, CONTROL_ARM)
    candidate_calls = _calls_of(report, CANDIDATE_ARM)
    return {
        "report": str(report_path),
        "prereg": str(prereg),
        "measured": measured,
        "candidate_header": (report.get("pins") or {}).get(
            "observation_header_name"
        ),
        "arms": {
            CONTROL_ARM: {
                "calls": len(control_calls),
                "readable": readable_count(control_calls),
                "usable_reported_not_gated": usable_count(control_calls),
                "unanswered_by_kind": _kind_census(control_calls),
            },
            CANDIDATE_ARM: {
                "calls": len(candidate_calls),
                "readable": readable_count(candidate_calls),
                "usable_reported_not_gated": usable_count(candidate_calls),
                "unanswered_by_kind": _kind_census(candidate_calls),
            },
        },
        "conditions": [condition.as_dict() for condition in conditions],
        "counts": counts,
        "verdict": verdict_of(conditions, measured=measured),
    }


def render(outcome: dict[str, Any]) -> str:
    arms = outcome["arms"]
    lines = [
        "format pilot V3 — 344 §6",
        f"  report      {outcome['report']}",
        f"  prereg      {Path(outcome['prereg']).name}",
        f"  header      {outcome['candidate_header']}",
        f"  paid run    {'yes' if outcome['measured'] else 'no (rehearsal)'}",
        "",
    ]
    for entry in outcome["conditions"]:
        lines.append(
            f"  [{_MARK.get(entry['result'], '????')}] "
            f"{entry['condition']}. {entry['title']}"
        )
        lines.append(f"         {entry['detail']}")
    lines.append("")
    for arm in (CONTROL_ARM, CANDIDATE_ARM):
        stats = arms[arm]
        lines.append(
            f"  {arm:<11} readable {stats['readable']}/{stats['calls']}"
            f"   usable {stats['usable_reported_not_gated']}/{stats['calls']}"
            f" (reported, not gated)"
        )
    counts = outcome["counts"]
    lines.append(
        f"  {counts['passed']} passed, {counts['failed']} failed, "
        f"{counts['unanswerable']} unanswerable"
    )
    verdict = outcome["verdict"]
    if verdict == VERDICT_FORMAT_HELD:
        lines.append(
            "  VERDICT format_held — the candidate kept the envelope 5/5 with "
            "a working control arm. §7 has the next step; it is not a claim "
            "that the candidate grades better."
        )
    elif verdict == VERDICT_FORMAT_LOST:
        lines.append(
            "  VERDICT format_lost — the candidate is closed. Not re-ordered, "
            "not re-scored at a lower bar."
        )
    elif verdict == VERDICT_REHEARSAL_OK:
        lines.append(
            "  VERDICT rehearsal_ok — nothing answerable failed, and this is "
            "NOT evidence about the candidate header."
        )
    else:
        blocked = [
            entry for entry in outcome["conditions"]
            if entry["result"] != RESULT_PASS
        ]
        named = ", ".join(f"condition {entry['condition']}" for entry in blocked)
        if outcome["measured"]:
            lines.append(
                "  VERDICT inconclusive — this run spent money and settled "
                f"nothing about the candidate: {named}."
            )
        else:
            lines.append(
                "  VERDICT inconclusive — the rehearsal did not come out "
                f"clean ({named}), so it has NOT cleared a paid dispatch. "
                "Nothing was spent; fix it and rehearse again."
            )
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path, help="The run's JSON report.")
    parser.add_argument(
        "--prereg", type=Path, default=PREREG,
        help="The pre-registration whose pins the run is held to.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the findings as JSON."
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="Write the JSON findings here."
    )
    args = parser.parse_args(argv)

    try:
        outcome = check(args.report, args.prereg)
    except ReportUnreadable as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"::error::{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(outcome, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(outcome, indent=2, ensure_ascii=False))
    else:
        print(render(outcome))
    return 0 if outcome["verdict"] in (
        VERDICT_FORMAT_HELD, VERDICT_REHEARSAL_OK
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
