#!/usr/bin/env python3
"""Judge an audio diagnostic's cost record against 340 section 6.2's nine conditions.

340 found that the ten paid audio calls of 337 recorded their usage and then
dropped it: the diagnostic script never wrapped its client in the metering
path, so there was no ledger row, no price lookup and no receipt. The fix is
in ``measure_audio_grading_accuracy.py``. This is the check that says whether
the fix actually held on a given run -- written *before* the run, so the
conditions are the ones the plan named rather than the ones the result made
convenient.

It reads two files that already exist and nothing else. No model call, no
credential, no network. Every number it prints comes out of the run's own
report and the ledger export beside it::

    cd batch-runner
    python scripts/verify_audio_metering_run.py path/to/report.json
    python scripts/verify_audio_metering_run.py path/to/report.json --json

Three things this tool refuses to do, each of which would make it useless:

**It will not call a rehearsal a measurement.** A ``--dry-run`` produces the
same ledger rows through the same code, which is worth checking and is not
evidence about ``gpt-audio-1.5``. The stub declines to invent an
``audio_tokens`` count -- there is no provider present to report one -- so the
condition that audio tokens survived is not *failed* on a rehearsal, it is
**unanswerable**, and it is reported as its own third state. A rehearsal that
passes everything answerable exits 0 under the verdict ``rehearsal_ok``, never
``measured_ok``.

**It will not turn an absent price into a zero.** ``gpt-audio-1.5`` has no
published rate, so a correct receipt is ``partial`` with ``price_missing`` and
an amount of ``null``. A run whose receipt says ``complete`` while a settled
call names an unpriced model fails condition 4, and a report showing ``$0``
fails condition 8. Both directions of that mistake are checked, because both
have been made.

**It will not judge the grading.** Whether the sub-judge heard the clip is
337/338's question and is not this one. A run in which every verdict was
unreadable can pass all nine conditions here -- that is condition 7, and it is
the point. Condition 7 does separate an unreadable *reply*, which was billed
and must settle, from a request that *raised*, which must be a refused or an
unresolved row and never a settled one.

Exit codes: ``0`` every answerable condition passed, ``1`` at least one
failed, ``2`` the files could not be read or do not describe each other. Note
what ``0`` does *not* say: a paid run in which nothing failed and something
was unanswerable also exits 0, under the verdict ``inconclusive``. The exit
code answers "is this cost record sound", and the verdict word answers "was
the question the run was funded to settle actually settled". Reading the
first as the second is the mistake this tool exists to prevent, so a caller
that cares about the second must read ``verdict``, not the status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "batch-runner") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "batch-runner"))

from core.cost_receipts import (  # noqa: E402
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    REASON_CALL_REFUSED_UNPRICED,
    REASON_PRICE_MISSING,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    STAGE_BUCKET,
    STAGE_PERCEPTION,
    STATE_ABANDONED,
    STATE_REFUSED,
    STATE_RESERVED,
    STATE_SETTLED,
    STATUS_COMPLETE,
    STATUS_NOT_RUN,
    CostReceipt,
    CostReceiptLedger,
    load_receipt_price_table,
)

#: The three verdicts a single condition can carry.
#:
#: ``unanswerable`` is not a softer ``fail``. It is the tool declining to
#: convert absence of evidence into either direction, and it exists because
#: the rehearsal path genuinely cannot produce the evidence condition 2 asks
#: for: the stub will not fabricate an audio token count. Folding it into
#: ``pass`` would let a free run stand in for a paid one, which is the exact
#: substitution 340 was written about; folding it into ``fail`` would make
#: every rehearsal look like a defect and train a reader to ignore red.
RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_UNANSWERABLE = "unanswerable"

#: Why a condition could not be answered. Recorded rather than left implicit,
#: because "nobody metered this run" and "this run was a rehearsal" call for
#: different next actions and both otherwise print as a blank.
UNANSWERABLE_REHEARSAL = "rehearsal"
UNANSWERABLE_NOT_METERED = "not_metered"
#: The provider refused every request, so no model ran and no reply carried
#: usage. Distinct from the two above: the path was exercised and the rows are
#: on the ledger, but the evidence condition 2 asks for was never produced by
#: anyone. Failing on it would blame the ledger for the provider's answer.
UNANSWERABLE_NO_MODEL_RAN = "no_model_ran"

VERDICT_MEASURED_OK = "measured_ok"
VERDICT_REHEARSAL_OK = "rehearsal_ok"
#: A paid run that failed nothing and answered less than everything.
#:
#: It exists because the alternative was worse in both directions. Reporting
#: such a run as ``rehearsal_ok`` puts the word *rehearsal* on an artifact that
#: cost money -- the exact confusion this whole tool is built to prevent --
#: and reporting it as ``measured_ok`` claims a measurement that was not made.
#: The live case is a paid run every one of whose calls came back refused: the
#: cost record is correct and complete, and nothing at all was learned about
#: whether audio token counts survive the trip.
VERDICT_INCONCLUSIVE = "inconclusive"
VERDICT_FAILED = "failed"

#: Reasons that describe a *price* that does not exist, as against usage that
#: went missing. The distinction decides who has to do something: an absent
#: price is a line to add to the price table, a missing usage block is a
#: defect in the request or the provider's reply. They are reported apart for
#: that reason and not summed into a single "incomplete" count, which would
#: send a reader to the wrong file.
PRICE_REASONS = (REASON_PRICE_MISSING,)
USAGE_REASONS = (REASON_USAGE_ABSENT, REASON_USAGE_PARTIAL)


def split_reasons(reasons: Iterable[str]) -> dict[str, list[str]]:
    """Sort a receipt's doubts into price-shaped, usage-shaped and other."""
    seen = sorted(set(str(reason) for reason in reasons))
    return {
        "price": [reason for reason in seen if reason in PRICE_REASONS],
        "usage": [reason for reason in seen if reason in USAGE_REASONS],
        "other": [
            reason
            for reason in seen
            if reason not in PRICE_REASONS and reason not in USAGE_REASONS
        ],
    }


class ReportUnreadable(Exception):
    """The report or the ledger is not the pair this tool was given."""


class Condition:
    """One of the nine, with the evidence that decided it.

    ``data`` carries digests and counts only. No prompt text, no response
    body, no request identifier from the provider -- the ledger does not hold
    those and this tool does not invent a place to put them.
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

    @property
    def ok(self) -> bool:
        """Whether this condition blocks a green verdict.

        Unanswerable does not block. What it does instead is stop the verdict
        being ``measured_ok`` -- see :func:`verdict_of`.
        """
        return self.result != RESULT_FAIL

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
        number, title, RESULT_UNANSWERABLE, detail, data, unanswerable_because=because
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
    if "cost" not in payload:
        raise ReportUnreadable(
            f"{path} has no cost block at all. A report written before the "
            f"metering path was wired carries no ledger reference, and there "
            f"is nothing here to check it against -- which is 340's finding, "
            f"not a fault in this tool."
        )
    return payload


def resolve_ledger_path(
    report: dict[str, Any], report_path: Path, override: Optional[Path]
) -> Optional[Path]:
    """Where the ledger export is, preferring what the report itself says.

    An override is honoured because a CI artifact may land the two files in a
    different directory than the one the run wrote them to. It does not
    loosen the digest check below: the file still has to be the one the report
    hashed, wherever it now sits.
    """
    if override is not None:
        return override
    reference = (report.get("cost") or {}).get("ledger") or {}
    stated = reference.get("path")
    if not stated:
        return None
    candidate = Path(str(stated))
    if candidate.is_file():
        return candidate
    beside = report_path.parent / candidate.name
    return beside if beside.is_file() else candidate


def load_ledger_rows(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Read a ledger export and return its rows and the file's digest."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReportUnreadable(f"the ledger at {path} could not be read: {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReportUnreadable(
                f"{path} line {number} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise ReportUnreadable(f"{path} line {number} is not a record")
        rows.append(record)
    return rows, digest


def _calls(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("record_type", "call") == "call"]


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _reasons(row: dict[str, Any]) -> tuple[str, ...]:
    raw = row.get("missing_reasons")
    if raw is None:
        return ()
    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split(",")]
        return tuple(part for part in parts if part)
    if isinstance(raw, (list, tuple)):
        return tuple(str(part) for part in raw if str(part).strip())
    return ()


# ── the nine ─────────────────────────────────────────────────────────────


def condition_1(
    report: dict[str, Any], perception_rows: Sequence[dict[str, Any]]
) -> Condition:
    """One ledger row per request that went out, and no row twice.

    The count is taken from the wire record rather than from the number of
    verdicts, because a call that raised produced no verdict and still cost a
    request. Uniqueness of ``call_id`` is checked in the same condition: a
    duplicated row would make the count too high, but reporting it as "the
    count is wrong" would send a reader looking for a missing request.
    """
    title = "원장 행 수 = 보낸 요청 수 (중복 없음)"
    sent = requests_sent(report)
    rows = list(perception_rows)
    identifiers = [str(row.get("call_id")) for row in rows]
    duplicates = sorted({key for key in identifiers if identifiers.count(key) > 1})
    data = {
        "requests_sent": sent,
        "perception_rows": len(rows),
        "duplicate_call_ids": duplicates,
        "states": _state_census(rows),
    }
    if duplicates:
        return _failed(
            1,
            title,
            f"{len(duplicates)} call identifier(s) appear more than once. The "
            f"same call is on the bill twice.",
            data,
        )
    if sent is None:
        return _failed(
            1,
            title,
            "the report does not say how many requests left the process, so "
            "the row count has nothing to be equal to",
            data,
        )
    if len(rows) != sent:
        return _failed(
            1,
            title,
            f"{sent} request(s) went out and the ledger holds {len(rows)} "
            f"perception row(s). A request without a row is spend without a "
            f"record; a row without a request is a charge that never happened.",
            data,
        )
    return _passed(
        1, title, f"{sent} request(s), {len(rows)} row(s), no repeated identifier", data
    )


def condition_2(
    perception_rows: Sequence[dict[str, Any]], *, measured: bool
) -> Condition:
    """Every row that carried sound reports audio input tokens.

    Unanswerable on a rehearsal by construction. ``TruthfulStub`` sets
    ``prompt_tokens`` from the base64 it was handed but leaves ``audio_tokens``
    alone, because that field is a provider stating it read the part as audio
    and there is no provider in a rehearsal to state it. A rehearsal that
    reported audio tokens would be reporting a number this repository wrote,
    which is worth less than nothing.

    Unanswerable a second way, and this one can happen on a paid run: if the
    provider refused every request there is no reply for a token count to have
    come back on. That is the provider's answer, not the ledger dropping
    something, and it is the reason the run's verdict is ``inconclusive``
    rather than either ``measured_ok`` or a failure.
    """
    title = "소리를 실은 행마다 audio_input_tokens > 0"
    settled = [row for row in perception_rows if row.get("state") == STATE_SETTLED]
    refused = [row for row in perception_rows if row.get("state") == STATE_REFUSED]
    counts = {
        str(row.get("call_id")): _int_or_none(row.get("audio_input_tokens"))
        for row in settled
    }
    data = {
        "settled_rows": len(settled),
        "refused_rows": len(refused),
        "audio_input_tokens": counts,
    }
    if not measured:
        return _unanswerable(
            2,
            title,
            "this was a rehearsal. The stub does not invent an audio token "
            "count, so the absence of one here is the stub being honest and "
            "not the ledger losing anything. Only a paid run answers this.",
            UNANSWERABLE_REHEARSAL,
            data,
        )
    if not settled and refused:
        # Not a pass: nothing here shows an audio token count surviving the
        # trip, which is the whole of what this condition asks. Not a fail
        # either: a refusal is the provider declining before any model ran, so
        # there was never a reply carrying the count that could have been
        # lost. The rows are on the ledger, counted and claiming nothing --
        # that is conditions 1, 4 and 5, and they answer for themselves.
        return _unanswerable(
            2,
            title,
            f"all {len(refused)} perception row(s) were refused by the "
            f"provider, so no model ran and no reply carried an audio token "
            f"count. The cost of those calls is recorded; whether audio "
            f"usage survives metering is untested by this run.",
            UNANSWERABLE_NO_MODEL_RAN,
            data,
        )
    if not settled:
        return _failed(
            2,
            title,
            "no settled perception row at all, so nothing reported audio tokens",
            data,
        )
    silent = sorted(key for key, value in counts.items() if not value)
    if silent:
        return _failed(
            2,
            title,
            f"{len(silent)} of {len(settled)} settled row(s) report no audio "
            f"input tokens. Either the request carried no sound or the count "
            f"was dropped between the reply and the row; the delivery section "
            f"of the report tells the two apart.",
            data,
        )
    return _passed(
        2,
        title,
        f"all {len(settled)} settled row(s) carry an audio input token count",
        data,
    )


def condition_3(
    report: dict[str, Any], perception_rows: Sequence[dict[str, Any]]
) -> Condition:
    """What the adapter reported equals what the ledger kept.

    Two independent readings of the same replies: ``AudioPerception`` sums
    them into its verdicts, and ``MeteredClient`` writes them into rows. They
    are compared in total rather than call by call, because the adapter's
    verdicts and the ledger's rows are not ordered against each other -- but a
    settle that was skipped, or a row written from the wrong response, moves
    the total.
    """
    title = "어댑터가 보고한 토큰 = 원장 행의 토큰"
    settled = [row for row in perception_rows if row.get("state") == STATE_SETTLED]
    ledger_input = sum(_int_or_none(row.get("input_tokens")) or 0 for row in settled)
    ledger_output = sum(_int_or_none(row.get("output_tokens")) or 0 for row in settled)
    adapter_input = sum(
        int(call.get("input_tokens") or 0) for call in report.get("calls") or []
    )
    adapter_output = sum(
        int(call.get("output_tokens") or 0) for call in report.get("calls") or []
    )
    unsettled = [
        str(row.get("call_id"))
        for row in perception_rows
        if row.get("state") == STATE_RESERVED
    ]
    refused = [
        str(row.get("call_id"))
        for row in perception_rows
        if row.get("state") == STATE_REFUSED
    ]
    # A refused row holds no counts to compare, which is why it is listed
    # rather than left to show up as a silent zero on the ledger side. The
    # adapter's own figure for that call is zero too -- nothing came back to
    # count -- so the totals still agree, and a reader seeing 0 in / 0 out
    # needs to be able to tell "the provider refused" from "the usage was
    # dropped between the reply and the row".
    carrying_tokens = [
        str(row.get("call_id"))
        for row in perception_rows
        if row.get("state") == STATE_REFUSED
        and (
            _int_or_none(row.get("input_tokens"))
            or _int_or_none(row.get("output_tokens"))
        )
    ]
    data = {
        "adapter_input_tokens": adapter_input,
        "adapter_output_tokens": adapter_output,
        "ledger_input_tokens": ledger_input,
        "ledger_output_tokens": ledger_output,
        "rows_left_reserved": unsettled,
        "rows_refused": refused,
    }
    if carrying_tokens:
        return _failed(
            3,
            title,
            f"{len(carrying_tokens)} row(s) recorded as refused before any "
            f"model ran still carry token counts. A refusal reports no usage, "
            f"so a count on one came from somewhere other than the reply.",
            data,
        )
    if adapter_input != ledger_input or adapter_output != ledger_output:
        return _failed(
            3,
            title,
            f"the adapter reported {adapter_input} in / {adapter_output} out "
            f"and the ledger holds {ledger_input} in / {ledger_output} out. "
            f"The two read the same replies, so a gap is a reply whose usage "
            f"reached one of them and not the other.",
            data,
        )
    return _passed(
        3,
        title,
        f"{ledger_input} in / {ledger_output} out on both sides"
        + (f", with {len(refused)} refused row(s) carrying none" if refused else ""),
        data,
    )


def condition_4(
    receipt: CostReceipt,
    perception_rows: Sequence[dict[str, Any]],
    price_table: Any,
    *,
    table_moved: Optional[dict[str, str]] = None,
) -> Condition:
    """An unpriced model produces ``price_missing`` and a null amount.

    The check runs in both directions. A settled row naming a model the table
    does not price must carry ``price_missing`` -- otherwise something put a
    number on it. And the receipt must not be ``complete`` while such a row is
    in it -- otherwise the run is claiming a total it cannot support. 340
    section 2.2 is the reason the second half exists: the old report printed
    ``pricing_complete`` from whether the run was paid for, so a free run of
    an unpriced model announced that its prices were complete.

    If the table on disk is not the one the run priced against, this fails
    rather than re-pricing quietly. The digest is in the report so that the
    claim can be reproduced; a mismatch means it cannot be, and answering from
    today's rates would produce a verdict about a table the run never saw.
    """
    title = "가격 없는 모델 → price_missing, 금액은 null"
    if table_moved is not None:
        return _failed(
            4,
            title,
            f"the run priced against a table hashing "
            f"{table_moved['stated'][:16]}… and the table read here hashes "
            f"{table_moved['local'][:16]}…. Point --price-table at the file "
            f"the run used; re-pricing against a different one would answer "
            f"about rates this run never saw.",
            table_moved,
        )
    settled = [row for row in perception_rows if row.get("state") == STATE_SETTLED]
    refused_rows = [row for row in perception_rows if row.get("state") == STATE_REFUSED]
    # A refusal is the second way a call ends up with no rate on it, and it is
    # the one that most easily turns into a clean bill of $0: the provider said
    # no model ran, and "no model ran" reads a great deal like "nothing was
    # charged". It is not the same statement. The row has to say so by name and
    # claim nothing, exactly as an unpriced settled row does.
    refusal_defects = [
        {
            "call_id": str(row.get("call_id")),
            "state": row.get("state"),
            "reasons": list(_reasons(row)),
            "model_cost_usd": row.get("model_cost_usd"),
            "why": (
                "amount_on_a_refusal"
                if row.get("model_cost_usd") not in (None, "")
                else "refusal_not_named"
            ),
        }
        for row in refused_rows
        if row.get("model_cost_usd") not in (None, "")
        or REASON_CALL_REFUSED_UNPRICED not in _reasons(row)
    ]
    unpriced: list[dict[str, Any]] = []
    for row in settled:
        provider = str(row.get("provider") or "")
        model = str(row.get("resolved_model") or row.get("requested_model") or "")
        price = price_table.lookup(provider, model) if price_table else None
        audio = _int_or_none(row.get("audio_input_tokens")) or 0
        if price is None:
            why = "absent_from_table"
        elif audio and not price.prices_audio:
            why = "priced_text_only_but_call_carried_audio"
        else:
            continue
        unpriced.append(
            {
                "call_id": str(row.get("call_id")),
                "provider": provider,
                "model": model,
                "why": why,
                "reasons": list(_reasons(row)),
                "model_cost_usd": row.get("model_cost_usd"),
            }
        )
    data = {
        "unpriced_rows": unpriced,
        "refused_rows": len(refused_rows),
        "refusal_defects": refusal_defects,
        "receipt_status": receipt.status,
        "estimated_cost_usd": (
            None
            if receipt.estimated_cost_usd is None
            else float(receipt.estimated_cost_usd)
        ),
        "receipt_reasons": list(receipt.missing_reasons),
    }
    if refusal_defects:
        named = ", ".join(sorted({entry["why"] for entry in refusal_defects}))
        return _failed(
            4,
            title,
            f"{len({entry['call_id'] for entry in refusal_defects})} refused "
            f"row(s) do not record the refusal the way the receipt reads it "
            f"({named}). A refusal that carries an amount was priced from "
            f"something, and one that does not carry "
            f"{REASON_CALL_REFUSED_UNPRICED} drops out of the receipt's "
            f"reasons and leaves it looking settled.",
            data,
        )
    if not unpriced:
        return _passed(
            4,
            title,
            "every settled row names a model this table prices, so there is "
            "no absent price for the receipt to have to admit to"
            + (
                f"; the {len(refused_rows)} refused row(s) claim no amount and "
                f"say {REASON_CALL_REFUSED_UNPRICED}"
                if refused_rows
                else ""
            ),
            data,
        )
    unrecorded = [
        entry for entry in unpriced if REASON_PRICE_MISSING not in entry["reasons"]
    ]
    if unrecorded:
        return _failed(
            4,
            title,
            f"{len(unrecorded)} row(s) name an unpriced model without "
            f"recording {REASON_PRICE_MISSING}. A row that was priced from a "
            f"table that has no rate for it was priced from something else.",
            data,
        )
    priced_anyway = [
        entry
        for entry in unpriced
        if entry["model_cost_usd"] not in (None, "", 0, 0.0, "0")
    ]
    if priced_anyway:
        return _failed(
            4,
            title,
            f"{len(priced_anyway)} unpriced row(s) still carry an amount",
            data,
        )
    # No check here that the receipt is not ``complete`` while holding these
    # rows. It cannot be: the receipt is rebuilt from these same rows, and a
    # row carrying ``price_missing`` makes it partial by construction. A guard
    # that can never fire reads as protection that is not there. What the
    # *report* claims about completeness is a separate matter and is condition
    # 8's, which compares the claim against this receipt.
    return _passed(
        4,
        title,
        f"{len(unpriced)} unpriced row(s), each carrying "
        f"{REASON_PRICE_MISSING}; the receipt is {receipt.status} and states "
        f"no total",
        data,
    )


def condition_5(
    receipt: CostReceipt,
    perception_rows: Sequence[dict[str, Any]],
    all_call_rows: Sequence[dict[str, Any]],
    task_id: str,
) -> Condition:
    """The task's ``grading_cost`` holds these perception calls, and only this task's.

    Attribution is checked here rather than assumed, because the failure it
    catches is silent: a perception read filed under the wrong task moves
    money between two receipts that both still add up.
    """
    title = "grading_cost가 그 지각 호출들을 담는다 (귀속 포함)"
    stray = sorted(
        {
            str(row.get("task_id"))
            for row in all_call_rows
            if row.get("stage") == STAGE_PERCEPTION
            and str(row.get("task_id")) != task_id
        }
    )
    counted = sum(
        component.model_calls
        for component in receipt.components
        if component.stage == STAGE_PERCEPTION
    )
    billable_rows = [
        row for row in perception_rows if row.get("state") != STATE_ABANDONED
    ]
    data = {
        "task_id": task_id,
        "perception_rows_for_this_task": len(perception_rows),
        "rows_counted_by_receipt": counted,
        "perception_rows_under_other_tasks": stray,
        "bucket": STAGE_BUCKET.get(STAGE_PERCEPTION),
    }
    if stray:
        return _failed(
            5,
            title,
            f"perception rows are filed under {len(stray)} other task id(s): "
            f"{', '.join(stray)}. This run graded one task.",
            data,
        )
    if STAGE_BUCKET.get(STAGE_PERCEPTION) != BUCKET_GRADING:
        return _failed(
            5,
            title,
            f"perception is mapped to {STAGE_BUCKET.get(STAGE_PERCEPTION)}, "
            f"not {BUCKET_GRADING}",
            data,
        )
    if counted != len(billable_rows):
        return _failed(
            5,
            title,
            f"{len(billable_rows)} perception row(s) are on the ledger and "
            f"the grading receipt counts {counted}. A row the receipt does "
            f"not count is spend the receipt does not show.",
            data,
        )
    return _passed(
        5,
        title,
        f"{counted} perception call(s) counted in {BUCKET_GRADING} for {task_id}",
        data,
    )


def condition_6(problem_solving: CostReceipt, task_id: str) -> Condition:
    """Nothing landed in the task's ``problem_solving_cost``.

    This run solved nothing -- it listened. A perception read that reached
    the problem-solving bucket would make the grader's own spend look like the
    model's work, which is the mixing 340 section 3.2 checked for in the mock
    and this checks for in the real thing.
    """
    title = "같은 작업의 problem_solving_cost가 안 움직인다"
    data = {
        "task_id": task_id,
        "bucket": BUCKET_PROBLEM_SOLVING,
        "status": problem_solving.status,
        "model_calls": problem_solving.model_calls,
        "known_cost_usd": float(problem_solving.known_cost_usd),
    }
    if problem_solving.status != STATUS_NOT_RUN or problem_solving.model_calls:
        return _failed(
            6,
            title,
            f"the problem-solving receipt is {problem_solving.status} with "
            f"{problem_solving.model_calls} call(s). A listening diagnostic "
            f"put something in the bucket that pays for the model's work.",
            data,
        )
    return _passed(
        6,
        title,
        f"{BUCKET_PROBLEM_SOLVING} is {STATUS_NOT_RUN} with no calls",
        data,
    )


def condition_7(
    report: dict[str, Any],
    perception_rows: Sequence[dict[str, Any]],
    *,
    measured: bool,
) -> Condition:
    """The calls whose verdicts were unreadable are metered like the rest.

    This is the condition 337 left the ground clear for. Its replies mostly
    came back in a shape the parser could not read, and a metering path that
    settles after parsing would have lost every one of them. Here the run is
    *expected* to contain unreadable verdicts and they are expected to have
    cost exactly as much as readable ones.

    A verdict can also be missing for a reason that is not a parse failure at
    all: the request raised. Those two have to land in different ledger states
    and the difference is not cosmetic -- a reply that came back was billed
    and must settle, while a request the provider refused ran no model and
    must be a ``refused`` row claiming nothing. Treating them alike in either
    direction is a way to lose a charge, so they are counted apart here, from
    the wire record rather than from the error text.

    A run in which every verdict parsed is not a failure of this condition --
    it just has nothing to say about it.
    """
    title = "판정이 깨진 문항의 호출도 1·2·3을 만족한다"
    calls = report.get("calls") or []
    broken = [call for call in calls if call.get("judge_error")]
    settled = [row for row in perception_rows if row.get("state") == STATE_SETTLED]
    refused = [row for row in perception_rows if row.get("state") == STATE_REFUSED]
    reserved = [row for row in perception_rows if row.get("state") == STATE_RESERVED]
    abandoned = [row for row in perception_rows if row.get("state") == STATE_ABANDONED]
    wired = [call for call in calls if isinstance(call.get("wire"), dict)]
    raised_per_call = [
        _int_or_none((call.get("wire") or {}).get("requests_that_raised"))
        for call in wired
    ]
    raised_known = wired and all(count is not None for count in raised_per_call)
    data = {
        "calls": len(calls),
        "calls_with_judge_error": len(broken),
        "settled_rows": len(settled),
        "refused_rows": len(refused),
        "reserved_rows": len(reserved),
        "abandoned_rows": len(abandoned),
        "broken_kinds": sorted({str(call.get("judge_error")) for call in broken}),
    }
    if not broken:
        return _passed(
            7,
            title,
            "no verdict was unreadable in this run, so no call needed the "
            "protection this condition names",
            data,
        )
    if not raised_known:
        # An older wire record does not say which requests raised, so the two
        # shapes of broken verdict cannot be told apart here. Say so rather
        # than pick one: the weaker comparison below is what this condition
        # could check before the field existed, and reporting it as though it
        # were the stronger one would overstate what was verified.
        data["wire_records_say_which_requests_raised"] = False
        if len(settled) < len(broken):
            return _failed(
                7,
                title,
                f"{len(broken)} verdict(s) were unreadable and only "
                f"{len(settled)} row(s) settled. A reply that could not be "
                f"parsed was still a reply, and it was still billed.",
                data,
            )
        return _passed(
            7,
            title,
            f"{len(broken)} unreadable verdict(s) against {len(settled)} "
            f"settled row(s). This run's wire records do not say which "
            f"requests raised, so a refusal and an unreadable reply are not "
            f"told apart here.",
            data,
        )

    raised = sum(count or 0 for count in raised_per_call)
    replies = sum(_int_or_none((c.get("wire") or {}).get("requests")) or 0 for c in wired)
    replies -= raised
    data["requests_that_raised"] = raised
    data["replies_that_came_back"] = replies
    if len(settled) != replies:
        return _failed(
            7,
            title,
            f"{replies} request(s) came back with a reply and {len(settled)} "
            f"row(s) settled. A reply that could not be parsed was still a "
            f"reply, and it was still billed.",
            data,
        )
    if len(refused) + len(reserved) != raised:
        return _failed(
            7,
            title,
            f"{raised} request(s) raised and the ledger holds "
            f"{len(refused)} refused plus {len(reserved)} reserved row(s) for "
            f"them"
            + (
                f", with {len(abandoned)} filed as never sent. A request that "
                f"raised on the way back had already gone out, and an "
                f"abandoned row is dropped from the receipt entirely."
                if abandoned
                else ". A request that raised is either one the provider "
                "answered or one whose fate is unknown, and both are rows."
            ),
            data,
        )
    answered = [
        call
        for call in broken
        if (_int_or_none((call.get("wire") or {}).get("requests")) or 0)
        > (_int_or_none((call.get("wire") or {}).get("requests_that_raised")) or 0)
    ]
    tokens_on_answered = sum(int(call.get("input_tokens") or 0) for call in answered)
    data["broken_verdicts_that_got_a_reply"] = len(answered)
    data["adapter_input_tokens_on_broken_calls"] = tokens_on_answered
    if measured and answered and not tokens_on_answered:
        return _failed(
            7,
            title,
            f"{len(answered)} unreadable verdict(s) got a reply and report no "
            f"input tokens at all, so the usage was lost on exactly the calls "
            f"this condition exists to protect",
            data,
        )
    return _passed(
        7,
        title,
        f"{len(broken)} verdict(s) without a judgement: {len(answered)} got a "
        f"reply and settled carrying usage, {raised} raised and are on the "
        f"ledger as {len(refused)} refused / {len(reserved)} unresolved",
        data,
    )


def condition_8(report: dict[str, Any], receipt: CostReceipt) -> Condition:
    """The report shows the grading cost as undetermined, not as zero.

    Two failures, one condition, because they are the same mistake seen from
    either side: a report that prints ``$0`` for an unpriced model, and a
    report whose ``pricing_complete`` was written from something other than a
    price lookup. The second is what 340 section 2.2 measured -- the old
    field was ``not billable``, so a free run announced complete pricing for a
    model that has no price at all.
    """
    title = "보고서의 grading_cost가 $0이 아니라 미확정으로 나온다"
    cost = report.get("cost") or {}
    stated_complete = cost.get("pricing_complete")
    stated_total = cost.get("estimated_cost_usd")
    unpriced = list(cost.get("unpriced_models") or [])
    data = {
        "pricing_complete": stated_complete,
        "estimated_cost_usd": stated_total,
        "unpriced_models": unpriced,
        "receipt_status": receipt.status,
        "record_kind": cost.get("record_kind"),
    }
    if unpriced and stated_complete:
        return _failed(
            8,
            title,
            f"the report says pricing is complete while naming "
            f"{len(unpriced)} unpriced model(s): {', '.join(unpriced)}",
            data,
        )
    if receipt.status != STATUS_COMPLETE and stated_complete:
        return _failed(
            8,
            title,
            f"the report says pricing is complete and its own receipt is "
            f"{receipt.status}",
            data,
        )
    if receipt.status != STATUS_COMPLETE and stated_total is not None:
        return _failed(
            8,
            title,
            f"the receipt is {receipt.status} and the report still states a "
            f"total of {stated_total}. An unpriced run costs an unknown "
            f"amount, and the only honest field for it is null.",
            data,
        )
    if stated_total == 0 and unpriced:
        return _failed(
            8,
            title,
            "the report states $0 for a run containing an unpriced model",
            data,
        )
    return _passed(
        8,
        title,
        f"the report states {stated_total!r} against a {receipt.status} "
        f"receipt",
        data,
    )


def condition_9(
    receipt: CostReceipt, rebuilt: CostReceipt, task_id: str
) -> Condition:
    """Re-reading the ledger reproduces the receipt the run published.

    The rebuild goes back through ``CostReceiptLedger.import_jsonl`` and
    ``receipt_for``, which is the same reader the run used. That is the point:
    a second implementation agreeing with the first proves the second
    implementation, whereas the same reader on the exported bytes proves the
    export.
    """
    title = "원장을 다시 읽어 만든 합 = 실행 중 영수증"
    published = receipt.as_dict()
    again = rebuilt.as_dict()
    differing = sorted(
        key
        for key in ("status", "known_cost_usd", "model_calls", "usage")
        if published.get(key) != again.get(key)
    )
    data = {
        "task_id": task_id,
        "published": {key: published.get(key) for key in ("status", "known_cost_usd", "model_calls")},
        "rebuilt": {key: again.get(key) for key in ("status", "known_cost_usd", "model_calls")},
        "differing_fields": differing,
    }
    if differing:
        return _failed(
            9,
            title,
            f"the receipt in the report and the receipt rebuilt from the "
            f"exported ledger disagree on {', '.join(differing)}",
            data,
        )
    return _passed(
        9,
        title,
        f"the export reproduces the published receipt "
        f"({again.get('status')}, {again.get('model_calls')} call(s))",
        data,
    )


# ── assembling ───────────────────────────────────────────────────────────


def requests_sent(report: dict[str, Any]) -> Optional[int]:
    """How many requests left the process, from the run's own wire record.

    Read from the wire summaries rather than from the number of verdicts,
    because one verdict can be two requests when the sub-judge retries a
    malformed envelope, and a request that raised in transport produced no
    verdict at all. ``WireClient`` appends a record for both of those and
    appends nothing for a request the ceiling refused before it went out --
    which is exactly the set the metering wrapper inside it reserves a row for.
    """
    total = 0
    seen = False
    for call in report.get("calls") or []:
        wire = call.get("wire")
        if not isinstance(wire, dict):
            continue
        count = _int_or_none(wire.get("requests"))
        if count is None:
            continue
        seen = True
        total += count
    return total if seen else None


def _state_census(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    census: dict[str, int] = {}
    for row in rows:
        state = str(row.get("state") or "unknown")
        census[state] = census.get(state, 0) + 1
    return census


def rebuild_receipt(
    rows: Sequence[dict[str, Any]],
    ledger_path: Path,
    task_id: str,
    bucket: str,
    price_table: Any,
) -> CostReceipt:
    """Import the export into a throwaway ledger and ask it for the receipt."""
    with tempfile.TemporaryDirectory() as workspace:
        mirror = Path(workspace) / "rebuilt.sqlite3"
        with CostReceiptLedger(
            mirror, run_id="verify-audio-metering", price_table=price_table
        ) as ledger:
            ledger.import_jsonl(ledger_path)
            return ledger.receipt_for(task_id, bucket)


def verdict_of(conditions: Sequence[Condition], *, measured: bool) -> str:
    if any(condition.result == RESULT_FAIL for condition in conditions):
        return VERDICT_FAILED
    if not measured:
        return VERDICT_REHEARSAL_OK
    if any(condition.result == RESULT_UNANSWERABLE for condition in conditions):
        # A paid run that still could not answer something is not a clean
        # measurement. It is not a rehearsal either -- that word belongs to
        # runs that spent nothing, and a paid run wearing it reads as free.
        return VERDICT_INCONCLUSIVE
    return VERDICT_MEASURED_OK


def check(
    report_path: Path,
    ledger_override: Optional[Path] = None,
    price_table_override: Optional[Path] = None,
) -> dict[str, Any]:
    report = load_report(report_path)
    cost = report.get("cost") or {}
    measured = bool(report.get("measured"))
    record_kind = str(cost.get("record_kind") or ("measured" if measured else "rehearsal"))
    task_id = str(cost.get("task_id") or "")
    if not task_id:
        raise ReportUnreadable(
            f"{report_path} names no cost task id, so there is no receipt to "
            f"look up. A metered run records the task its calls were filed "
            f"under."
        )

    ledger_path = resolve_ledger_path(report, report_path, ledger_override)
    if ledger_path is None or not ledger_path.is_file():
        raise ReportUnreadable(
            f"no ledger export beside {report_path.name}"
            + (f" (looked at {ledger_path})" if ledger_path else "")
            + ". The report states what it cost; the ledger is what that "
            "statement is checked against, and without it this tool would be "
            "reading the claim back to itself."
        )

    rows, digest = load_ledger_rows(ledger_path)
    stated_digest = (cost.get("ledger") or {}).get("sha256")
    if stated_digest and stated_digest != digest:
        raise ReportUnreadable(
            f"{report_path.name} was written against a ledger with digest "
            f"{str(stated_digest)[:16]}… and {ledger_path.name} hashes to "
            f"{digest[:16]}…. These two files do not describe each other."
        )

    price_table_path = price_table_override or (
        (cost.get("price_table") or {}).get("path")
    )
    table = load_receipt_price_table(
        Path(price_table_path) if price_table_path else None
    )
    stated_table_digest = (cost.get("price_table") or {}).get("sha256")
    table_moved = (
        {"stated": str(stated_table_digest), "local": table.sha256}
        if stated_table_digest and str(stated_table_digest) != table.sha256
        else None
    )

    call_rows = _calls(rows)
    perception_rows = [
        row
        for row in call_rows
        if row.get("stage") == STAGE_PERCEPTION and str(row.get("task_id")) == task_id
    ]

    published = CostReceipt.from_dict(cost.get("receipt"))
    rebuilt = rebuild_receipt(rows, ledger_path, task_id, BUCKET_GRADING, table)
    problem_solving = rebuild_receipt(
        rows, ledger_path, task_id, BUCKET_PROBLEM_SOLVING, table
    )

    conditions = [
        condition_1(report, perception_rows),
        condition_2(perception_rows, measured=measured),
        condition_3(report, perception_rows),
        condition_4(rebuilt, perception_rows, table, table_moved=table_moved),
        condition_5(rebuilt, perception_rows, call_rows, task_id),
        condition_6(problem_solving, task_id),
        condition_7(report, perception_rows, measured=measured),
        condition_8(report, rebuilt),
        condition_9(published, rebuilt, task_id),
    ]

    return {
        "what_this_is": (
            "340 section 6.2's nine conditions, judged from a run's own ledger "
            "and receipt. It says whether the spend was recorded, never "
            "whether the grading was right."
        ),
        "report": str(report_path),
        "ledger": {"path": str(ledger_path), "sha256": digest, "rows": len(rows)},
        "price_table_sha256": table.sha256,
        "record_kind": record_kind,
        "measured": measured,
        "task_id": task_id,
        "receipt_status": rebuilt.status,
        "missing": split_reasons(rebuilt.missing_reasons),
        "verdict": verdict_of(conditions, measured=measured),
        "conditions": [condition.as_dict() for condition in conditions],
        "counts": {
            "passed": sum(1 for c in conditions if c.result == RESULT_PASS),
            "failed": sum(1 for c in conditions if c.result == RESULT_FAIL),
            "unanswerable": sum(
                1 for c in conditions if c.result == RESULT_UNANSWERABLE
            ),
        },
    }


_MARK = {
    RESULT_PASS: "PASS",
    RESULT_FAIL: "FAIL",
    RESULT_UNANSWERABLE: "N/A ",
}


def render(outcome: dict[str, Any]) -> str:
    lines = [
        "audio metering — 340 §6.2",
        f"  report      {outcome['report']}",
        f"  ledger      {Path(outcome['ledger']['path']).name} "
        f"({outcome['ledger']['rows']} row(s), {outcome['ledger']['sha256'][:16]}…)",
        f"  record kind {outcome['record_kind']}",
        f"  task        {outcome['task_id']}",
        "",
    ]
    for entry in outcome["conditions"]:
        lines.append(
            f"  [{_MARK.get(entry['result'], '????')}] "
            f"{entry['condition']}. {entry['title']}"
        )
        lines.append(f"         {entry['detail']}")
    counts = outcome["counts"]
    missing = outcome["missing"]
    lines.append("")
    lines.append(
        f"  receipt     {outcome['receipt_status']}"
        f"   price gaps: {', '.join(missing['price']) or 'none'}"
        f"   usage gaps: {', '.join(missing['usage']) or 'none'}"
    )
    if missing["other"]:
        lines.append(f"  other       {', '.join(missing['other'])}")
    lines.append(
        f"  {counts['passed']} passed, {counts['failed']} failed, "
        f"{counts['unanswerable']} unanswerable"
    )
    verdict = outcome["verdict"]
    if verdict == VERDICT_MEASURED_OK:
        lines.append("  VERDICT measured_ok — a paid run answered all nine.")
    elif verdict == VERDICT_REHEARSAL_OK:
        lines.append(
            "  VERDICT rehearsal_ok — nothing failed, and this is NOT evidence "
            "that a paid audio call was metered."
        )
    elif verdict == VERDICT_INCONCLUSIVE:
        unanswered = [
            entry for entry in outcome["conditions"]
            if entry["result"] == RESULT_UNANSWERABLE
        ]
        lines.append(
            "  VERDICT inconclusive — this run spent money and still could "
            "not answer "
            + ", ".join(f"condition {entry['condition']}" for entry in unanswered)
            + ". What it did spend is recorded; the question it was run to "
            "settle is not settled."
        )
    else:
        lines.append("  VERDICT failed")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path, help="The run's JSON report.")
    parser.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help=(
            "The ledger export, when it is not where the report says. Its "
            "digest is still checked against the report."
        ),
    )
    parser.add_argument(
        "--price-table",
        type=Path,
        default=None,
        help=(
            "The price table the run used, when it is not where the report "
            "says. A table whose digest does not match the report's fails "
            "condition 4 rather than being re-priced quietly."
        ),
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the findings as JSON."
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="Write the JSON findings here."
    )
    args = parser.parse_args(argv)

    try:
        outcome = check(args.report, args.ledger, args.price_table)
    except ReportUnreadable as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"::error::{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(outcome, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(outcome, indent=2, ensure_ascii=False))
    else:
        print(render(outcome))
    return 0 if outcome["verdict"] != VERDICT_FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())
