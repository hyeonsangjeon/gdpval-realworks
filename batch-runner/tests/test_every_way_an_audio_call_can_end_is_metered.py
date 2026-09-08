"""Every ending an audio call can have, from the request to the ninth condition.

``340`` found the audio diagnostic's calls leaving no ledger row at all, and
``342`` built the path that carries one. A path that carries the *happy* row is
half a path: the endings that matter to a bill are the ones where something
went wrong, because those are the ones where a number can quietly become zero.

``341`` argued for splitting one of them — a provider that answered ``400``
had demonstrably been reached, so publishing「도달 여부 불명확」about it was
doubt about a known fact — and shared metering code now has a state for it.
That split is the reason this file exists as a whole rather than as one more
case in ``test_the_metering_run_goes_end_to_end.py``: with a definitive
refusal now landing somewhere new, the useful question is no longer "does the
refusal work" but **"is every ending distinct, and does each one keep the
claim it is entitled to make"**.

Eight endings, each driven through the production diagnostic or the
production adapter rather than by writing rows::

    the provider refused, verifiably    -> refused,   claims nothing, is a call
    the request never left              -> no row,    and no wire record
    nobody knows if it left             -> reserved,  claims nothing, is a call
    it answered without a usage block   -> settled,   usage_absent
    it answered and nothing prices it   -> settled,   price_missing
    it answered unreadably              -> settled,   with usage, and was billed
    the export is read again            -> the same states and the same receipt
    the same call is settled twice      -> refused by the ledger, not overwritten

Two of those already have an end-to-end test next door — the ceiling that
stops a request before it leaves, and the reply that will not parse — and are
checked here only for what ``341``'s change makes newly non-obvious about
them. The rest are new.

Nothing here calls a model. Every row it produces says ``provider: stub``.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from core.cost_receipts import (
    BUCKET_GRADING,
    REASON_CALL_REACHABILITY_UNKNOWN,
    REASON_CALL_REFUSED_UNPRICED,
    REASON_PRICE_MISSING,
    REASON_USAGE_ABSENT,
    RETRY_NONE,
    STAGE_PERCEPTION,
    STATE_REFUSED,
    STATE_RESERVED,
    STATE_SETTLED,
    STATUS_PARTIAL,
    CallUsage,
    CostReceiptLedger,
    LedgerIntegrityError,
    load_receipt_price_table,
    make_call_id,
)

# The rehearsal corpus, the document builder and the two script modules are
# the ones the neighbouring file already builds. Imported rather than copied:
# a second corpus fixture would be a second thing to keep in step with
# ``load_speech_corpus``, and the point of these tests is the metering path.
from tests.test_the_metering_run_goes_end_to_end import (  # noqa: F401
    _condition,
    _document,
    _run,
    checker,
    corpus,
    measure,
)


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    export = Path(report["cost"]["ledger"]["path"])
    return [
        json.loads(line)
        for line in export.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _states(rows) -> list[str]:
    return [row["state"] for row in rows]


class _Refused(Exception):
    """What an SDK raises for a status the provider answered with.

    ``status_code`` is the attribute both ``core/perception/audio.py`` and
    ``core/cost_metering.py`` read, and it is the whole of what either of them
    reads. Neither touches the message, which in a real refusal quotes the
    request URL.
    """

    def __init__(self, status: int) -> None:
        super().__init__(f"the provider answered {status}")
        self.status_code = status


class _StubThatIsRefused:
    def __init__(self, claims, status: int = 400) -> None:
        self._status = status
        self.requests: list[dict[str, Any]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        raise _Refused(self._status)


class _StubThatBreaksInTransport:
    def __init__(self, claims) -> None:
        self.requests: list[dict[str, Any]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        raise TimeoutError("no answer came back")


class _StubWithNoUsage(measure.TruthfulStub):
    """Answers correctly and reports nothing about what it consumed."""

    def create(self, **kwargs: Any) -> Any:
        response = super().create(**kwargs)
        response.usage = None
        return response


# ── 1. the provider refused, verifiably ──────────────────────────────────


def test_a_refusal_is_a_counted_call_that_claims_no_amount(
    tmp_path, corpus, monkeypatch
):
    """An HTTP 400 costs nothing, and "nothing" is not the same as "$0".

    The two wrong answers are opposite and both were available. Dropping the
    row — recording the call as never sent — produces a *complete* receipt of
    zero dollars, which is a positive claim about a call whose body the
    provider read before declining. Settling it at zero claims the same thing
    with a settled row behind it. What is true is narrower than either: the
    request went out, a model did not run, and the provider says so.

    So the row exists, it is counted among ``model_calls``, it carries no
    amount, and the receipt stays ``partial`` naming ``call_refused_unpriced``
    — the reason ``341`` proposed and shared metering code implemented.
    """
    monkeypatch.setattr(measure, "TruthfulStub", _StubThatIsRefused)
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    code, report_path = _run(tmp_path, corpus, document)

    # 2: no verdict was reached. The accuracy question went unanswered, which
    # is what a refusal does to it, and it is not the cost question.
    assert code == 2

    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = _rows(report)
    assert _states(rows) == [STATE_REFUSED, STATE_REFUSED]
    assert [row["model_cost_usd"] for row in rows] == [None, None]
    assert [row["note"] for row in rows] == ["provider_refused_400"] * 2
    for row in rows:
        assert REASON_CALL_REFUSED_UNPRICED in row["missing_reasons"]
        # The one reason a refusal must *not* carry: reachability is the fact
        # a status establishes.
        assert REASON_CALL_REACHABILITY_UNKNOWN not in row["missing_reasons"]

    cost = report["cost"]
    assert cost["model_calls"] == 2, "a refused request is still a request made"
    assert cost["billable_calls"] == 0
    assert cost["estimated_cost_usd"] is None, "null, never 0"
    assert cost["pricing_complete"] is False
    assert cost["receipt"]["status"] == STATUS_PARTIAL


def test_the_checker_reads_a_refusal_as_a_refusal(tmp_path, corpus, monkeypatch):
    """All nine conditions on a run where every call was declined.

    Condition 7 is the one this test was written for. It asks whether a call
    whose verdict is missing still paid its way, and before ``341`` it had one
    idea of why a verdict goes missing: the reply came back unreadable, so it
    was billed, so it must be settled. Run against two refusals it said

        2 verdict(s) were unreadable and only 0 row(s) settled. A reply that
        could not be parsed was still a reply, and it was still billed.

    — three sentences about a reply that never arrived, on a run whose cost
    record was entirely correct. It now splits the two by the wire record and
    requires each to land in its own state.
    """
    monkeypatch.setattr(measure, "TruthfulStub", _StubThatIsRefused)
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    _, report_path = _run(tmp_path, corpus, document)
    outcome = checker.check(report_path)

    assert outcome["counts"]["failed"] == 0, [
        entry for entry in outcome["conditions"] if entry["result"] == "fail"
    ]

    seventh = _condition(outcome, 7)
    assert seventh["result"] == "pass"
    assert seventh["data"]["requests_that_raised"] == 2
    assert seventh["data"]["replies_that_came_back"] == 0
    assert seventh["data"]["refused_rows"] == 2
    assert seventh["data"]["settled_rows"] == 0

    # 3 and 4 pass on this run and would pass on an empty one too, so they are
    # required to say which rows they saw rather than to be silently vacuous.
    assert len(_condition(outcome, 3)["data"]["rows_refused"]) == 2
    assert _condition(outcome, 4)["data"]["refusal_defects"] == []
    assert "refused" in _condition(outcome, 4)["detail"]


# ── 2. the request never left ────────────────────────────────────────────


def test_a_request_stopped_before_it_left_leaves_no_row_and_no_record(
    tmp_path, corpus, monkeypatch
):
    """The ceiling refuses a request; the ledger has nothing to say about it.

    The neighbouring file checks that the request which *did* go out survives
    the stop. The complement matters to condition 1: the ceiling raises inside
    ``WireClient`` before the metered client underneath it is ever called, so
    the stopped request appends no wire record and reserves no row, and "rows
    equal requests sent" stays an equality rather than becoming a tolerance.
    """

    class _WireWithATighterCap(measure.WireClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["request_cap"] = 1
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(measure, "WireClient", _WireWithATighterCap)
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    code, report_path = _run(tmp_path, corpus, document)
    assert code == 3

    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = _rows(report)
    assert _states(rows) == [STATE_SETTLED], "only the request that went out"
    assert report["cost"]["model_calls"] == 1

    sent = sum(
        (call.get("wire") or {}).get("requests") or 0 for call in report["calls"]
    )
    assert sent == 1, "the stopped request is not a request sent"
    assert _condition(checker.check(report_path), 1)["result"] == "pass"


# ── 3. nobody knows whether it left ──────────────────────────────────────


def test_a_timeout_stays_reserved_because_it_may_have_been_served(
    tmp_path, corpus, monkeypatch
):
    """The ending that must *not* collapse into the refusal beside it.

    ``341``'s change is a narrowing, and the way a narrowing goes wrong is by
    taking more than it argued for. A timeout establishes nothing: the request
    may have been served in full and billed, and the answer may have been lost
    on the way back. So it keeps the reservation nobody closed and the reason
    that names the doubt, while the 400 next to it does not.
    """
    monkeypatch.setattr(measure, "TruthfulStub", _StubThatBreaksInTransport)
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    code, report_path = _run(tmp_path, corpus, document)
    assert code == 2

    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = _rows(report)
    assert _states(rows) == [STATE_RESERVED, STATE_RESERVED]
    for row in rows:
        assert row["model_cost_usd"] is None
        # The reason is not written onto the row here, and that asymmetry is
        # the states talking. ``refuse`` records a fact the provider stated,
        # so the reason is stored. An unclosed reservation states nothing; the
        # doubt is something the receipt works out from the row still being
        # open, and it appears there.
        assert REASON_CALL_REFUSED_UNPRICED not in (row["missing_reasons"] or [])

    receipt = report["cost"]["receipt"]
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt["missing_reasons"]
    assert REASON_CALL_REFUSED_UNPRICED not in receipt["missing_reasons"]
    assert report["cost"]["estimated_cost_usd"] is None
    assert receipt["status"] == STATUS_PARTIAL

    outcome = checker.check(report_path)
    assert outcome["counts"]["failed"] == 0, [
        entry for entry in outcome["conditions"] if entry["result"] == "fail"
    ]
    seventh = _condition(outcome, 7)
    assert seventh["data"]["reserved_rows"] == 2
    assert seventh["data"]["refused_rows"] == 0


# ── 4. it answered, and said nothing about what it consumed ──────────────


def test_a_reply_without_a_usage_block_settles_and_admits_the_gap(
    tmp_path, corpus, monkeypatch
):
    """A reply arrived, so the call was billed; how much is unknown.

    This is the ending that most resembles a correct one and is not: the
    verdicts parse, the accuracy figure is real, the run exits 0. Only the
    receipt knows that the amounts behind it are missing, and it has to keep
    saying so or the run reads as fully measured.
    """
    monkeypatch.setattr(measure, "TruthfulStub", _StubWithNoUsage)
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    code, report_path = _run(tmp_path, corpus, document)
    assert code == 0, "the accuracy question was answered; the cost one was not"

    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = _rows(report)
    assert _states(rows) == [STATE_SETTLED, STATE_SETTLED]
    for row in rows:
        assert REASON_USAGE_ABSENT in row["missing_reasons"]
        assert row["model_cost_usd"] is None

    assert report["cost"]["receipt"]["status"] == STATUS_PARTIAL
    assert report["cost"]["estimated_cost_usd"] is None

    outcome = checker.check(report_path)
    # A missing usage block and a missing price send a reader to different
    # files, so the checker keeps them in different lists.
    assert REASON_USAGE_ABSENT in outcome["missing"]["usage"]
    assert REASON_USAGE_ABSENT not in outcome["missing"]["price"]


# ── 5. it answered, and no table prices it ───────────────────────────────


def test_an_unpriced_model_is_reported_as_unknown_and_not_as_zero(tmp_path, corpus):
    """``340`` §2.2's original defect, checked from the other side.

    The old report printed ``$0`` and ``pricing_complete: true`` out of four
    constants, which would have printed identically had the model been priced.
    Here the amount is the ledger's answer, and the ledger's answer for a
    model with no published rate is that it does not know.
    """
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    code, report_path = _run(tmp_path, corpus, document)
    assert code == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert _states(_rows(report)) == [STATE_SETTLED, STATE_SETTLED]
    assert report["cost"]["estimated_cost_usd"] is None
    assert report["cost"]["pricing_complete"] is False
    assert report["cost"]["unpriced_models"]

    outcome = checker.check(report_path)
    assert REASON_PRICE_MISSING in outcome["missing"]["price"]
    assert REASON_PRICE_MISSING not in outcome["missing"]["usage"]
    assert _condition(outcome, 8)["result"] == "pass"


# ── 6. it answered unreadably ────────────────────────────────────────────


def test_an_unreadable_reply_is_a_settled_row_carrying_its_usage(
    tmp_path, corpus, monkeypatch
):
    """The ending condition 7 was originally written for, re-checked.

    Its neighbour already asserts the rows survive. What is asserted here is
    the half of condition 7 that ``341``'s change could have loosened: a
    verdict that went missing *after* a reply came back still has to be a
    settled row carrying usage, and must not be satisfied by a refusal.
    """
    from tests.test_the_metering_run_goes_end_to_end import _StubThatBreaks

    monkeypatch.setattr(measure, "TruthfulStub", _StubThatBreaks)
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    code, report_path = _run(tmp_path, corpus, document)
    assert code == 2

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert _states(_rows(report)) == [STATE_SETTLED, STATE_SETTLED]

    outcome = checker.check(report_path)
    seventh = _condition(outcome, 7)
    assert seventh["result"] == "pass"
    assert seventh["data"]["requests_that_raised"] == 0
    assert seventh["data"]["replies_that_came_back"] == 2
    assert seventh["data"]["broken_verdicts_that_got_a_reply"] == 2
    assert seventh["data"]["refused_rows"] == 0


def test_condition_7_fails_when_a_reply_that_came_back_lost_its_row(
    tmp_path, corpus, monkeypatch
):
    """The check that makes the test above worth having.

    Deleting a settled row from the export puts the run in exactly the shape
    ``340`` found: replies came back, and the ledger is one row short of the
    requests that produced them. Condition 7 has to be the one that says so —
    otherwise it passes on the defect it exists to catch.
    """
    from tests.test_the_metering_run_goes_end_to_end import _StubThatBreaks

    monkeypatch.setattr(measure, "TruthfulStub", _StubThatBreaks)
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    _, report_path = _run(tmp_path, corpus, document)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    export = Path(report["cost"]["ledger"]["path"])
    kept = _rows(report)[:1]
    export.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in kept),
        encoding="utf-8",
    )
    report["cost"]["ledger"]["sha256"] = hashlib.sha256(export.read_bytes()).hexdigest()
    report["cost"]["ledger"]["rows"] = len(kept)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    seventh = _condition(checker.check(report_path), 7)
    assert seventh["result"] == "fail"
    assert "still billed" in seventh["detail"]


# ── 7. the export is read again ──────────────────────────────────────────


def test_re_reading_the_export_reproduces_a_refusal_unchanged(
    tmp_path, corpus, monkeypatch
):
    """Resume, on the endings where a state could be lost in the round trip.

    Condition 9 already rebuilds the receipt from the export, and did so back
    when every row was settled. A refusal is a newer state with a reason and a
    note attached to it, and a reader that dropped either would rebuild a
    receipt that looked the same and meant less. So the states, the reasons
    and the receipt are all compared across ``import_jsonl``.
    """
    monkeypatch.setattr(measure, "TruthfulStub", _StubThatIsRefused)
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    _, report_path = _run(tmp_path, corpus, document)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    export = Path(report["cost"]["ledger"]["path"])
    original = _rows(report)
    task_id = report["cost"]["task_id"]

    with CostReceiptLedger(
        tmp_path / "resumed.sqlite3",
        run_id="resume-probe",
        price_table=load_receipt_price_table(),
    ) as resumed:
        resumed.import_jsonl(export)
        again = resumed.receipt_for(task_id, BUCKET_GRADING)
        second = tmp_path / "resumed.jsonl"
        resumed.export_jsonl(second)

    rebuilt = [
        json.loads(line)
        for line in second.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert _states(rebuilt) == [STATE_REFUSED, STATE_REFUSED]
    assert [row["missing_reasons"] for row in rebuilt] == [
        row["missing_reasons"] for row in original
    ]
    assert [row["note"] for row in rebuilt] == [row["note"] for row in original]

    published = report["cost"]["receipt"]
    assert again.status == published["status"]
    assert again.model_calls == published["model_calls"] == 2
    assert again.known_cost_usd == Decimal("0")

    assert _condition(checker.check(report_path), 9)["result"] == "pass"


# ── 8. the same call is settled twice ────────────────────────────────────


def test_a_recorded_cost_is_not_overwritten_by_a_second_settlement(tmp_path):
    """Resume's failure mode: the same call reported twice, differently.

    A resumed run that re-plays work it already did is the ordinary way a
    ledger comes to be told about one call twice. Adding both would inflate
    the bill; letting the second overwrite the first would let a retry's
    smaller reading erase the charge that actually happened. The ledger
    refuses, and — the part worth pinning — refuses *after* keeping the first
    reading, so the receipt still holds what was really spent.

    Driven against the ledger's own API because there is no way to make the
    production script send one call twice, which is itself the point.
    """
    table = load_receipt_price_table()
    with CostReceiptLedger(
        tmp_path / "twice.sqlite3", run_id="twice", price_table=table
    ) as ledger:
        call_id = make_call_id(
            run_id="twice",
            task_id="audio_metering_probe",
            stage=STAGE_PERCEPTION,
            retry_kind=RETRY_NONE,
            attempt_index=0,
            sequence=0,
        )
        ledger.reserve(
            call_id=call_id,
            task_id="audio_metering_probe",
            stage=STAGE_PERCEPTION,
            retry_kind=RETRY_NONE,
            provider="azure",
            requested_model="gpt-audio-1.5",
            deployment="gpt-audio-1.5",
            api_version="2025-04-01-preview",
            request_sha256="a" * 64,
        )
        ledger.settle(
            call_id,
            usage=CallUsage(input_tokens=412, output_tokens=55),
            resolved_model="gpt-audio-1.5",
        )
        with pytest.raises(LedgerIntegrityError) as raised:
            ledger.settle(
                call_id,
                usage=CallUsage(input_tokens=9, output_tokens=1),
                resolved_model="gpt-audio-1.5",
            )
        assert "will not overwrite" in str(raised.value)

        receipt = ledger.receipt_for("audio_metering_probe", BUCKET_GRADING)
        assert receipt.model_calls == 1, "one call, not two"
        assert receipt.usage["input_tokens"] == 412, "the first reading survived"


def test_a_refused_call_cannot_later_be_settled_into_a_paid_one(tmp_path):
    """The new state is a terminal one, and has to be.

    A refusal says no model ran. If a later ``settle`` could turn that row
    into a priced call, the ledger would accept an amount for a request the
    provider declined — the same wrong number as reporting ``$0``, arrived at
    from the opposite direction.
    """
    with CostReceiptLedger(
        tmp_path / "refused.sqlite3",
        run_id="refused",
        price_table=load_receipt_price_table(),
    ) as ledger:
        call_id = make_call_id(
            run_id="refused",
            task_id="audio_metering_probe",
            stage=STAGE_PERCEPTION,
            retry_kind=RETRY_NONE,
            attempt_index=0,
            sequence=0,
        )
        ledger.reserve(
            call_id=call_id,
            task_id="audio_metering_probe",
            stage=STAGE_PERCEPTION,
            retry_kind=RETRY_NONE,
            provider="azure",
            requested_model="gpt-audio-1.5",
            deployment="gpt-audio-1.5",
            api_version="2025-04-01-preview",
            request_sha256="b" * 64,
        )
        ledger.refuse(call_id, status=400)

        with pytest.raises(LedgerIntegrityError):
            ledger.settle(
                call_id,
                usage=CallUsage(input_tokens=412, output_tokens=55),
                resolved_model="gpt-audio-1.5",
            )
        # Nor may it be rewritten as a call that never left, which would drop
        # it from the receipt entirely and complete the total at $0.
        with pytest.raises(LedgerIntegrityError):
            ledger.abandon(call_id, note="tidying up")

        receipt = ledger.receipt_for("audio_metering_probe", BUCKET_GRADING)
        assert receipt.status == STATUS_PARTIAL
        assert receipt.model_calls == 1
        assert receipt.known_cost_usd == Decimal("0")
        assert REASON_CALL_REFUSED_UNPRICED in receipt.missing_reasons


# ── what a paid run of refusals is called ────────────────────────────────


def _paid_report_of_refusals(tmp_path: Path) -> Path:
    """A ``measured`` report whose every perception call was declined.

    Built through ``reserve``/``refuse`` rather than by writing rows, so what
    is being tested is a ledger state and not the test's spelling of one. The
    provider says ``azure`` because that is what marks a report as describing
    a paid run; nothing was bought to produce it.
    """
    table = load_receipt_price_table()
    task_id = "audio_accuracy_diagnostic"
    with CostReceiptLedger(
        tmp_path / "paid.sqlite3", run_id="paid-refusals", price_table=table
    ) as ledger:
        for index in range(2):
            call_id = make_call_id(
                run_id="paid-refusals",
                task_id=task_id,
                stage=STAGE_PERCEPTION,
                retry_kind=RETRY_NONE,
                attempt_index=0,
                sequence=index,
            )
            ledger.reserve(
                call_id=call_id,
                task_id=task_id,
                stage=STAGE_PERCEPTION,
                retry_kind=RETRY_NONE,
                provider="azure",
                requested_model="gpt-audio-1.5",
                deployment="gpt-audio-1.5",
                api_version="2025-04-01-preview",
                request_sha256=hashlib.sha256(str(index).encode()).hexdigest(),
            )
            ledger.refuse(call_id, status=400)
        export = tmp_path / "paid.jsonl"
        digest = ledger.export_jsonl(export)
        receipt = ledger.receipt_for(task_id, BUCKET_GRADING)

    report = {
        "measured": True,
        "calls": [
            {
                "claim_id": f"claim-{index}",
                "input_tokens": 0,
                "output_tokens": 0,
                "judge_error": "audio_unavailable:provider_400",
                "wire": {
                    "requests": 1,
                    "requests_with_audio": 1,
                    "requests_that_raised": 1,
                },
            }
            for index in range(2)
        ],
        "cost": {
            "record_kind": "measured",
            "task_id": task_id,
            "model_calls": 2,
            "billable_calls": 0,
            "models": ["gpt-audio-1.5"],
            "price_table": {
                "path": str(
                    Path("experiments/execution_envelope/model_price_table.json")
                ),
                "sha256": table.sha256,
            },
            "pricing_complete": False,
            "unpriced_models": ["gpt-audio-1.5"],
            "estimated_cost_usd": None,
            "receipt": receipt.as_dict(),
            "ledger": {
                "path": str(export),
                "sha256": digest,
                "rows": len(
                    [
                        line
                        for line in export.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]
                ),
            },
        },
    }
    report_path = tmp_path / "paid-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def test_a_paid_run_that_was_entirely_refused_is_inconclusive(tmp_path):
    """Not a rehearsal, not a measurement, and not a failure either.

    Every condition that can be answered passes: the rows are there, they are
    counted, they claim nothing, the receipt is partial and the report says
    ``null``. The cost record is exactly right. What the run was funded to
    find out — whether an audio token count survives the trip into the ledger
    — is untouched, because no model ran.

    Calling that ``rehearsal_ok`` would put the word *rehearsal* on an
    artifact that cost money, which is the single confusion this checker
    exists to prevent. Calling it ``measured_ok`` would claim a measurement
    nobody made. It gets its own word, and the exit code stays 0 because
    nothing about the *cost record* failed — the verdict carries the gap, and
    the printed line says which condition went unanswered.
    """
    report_path = _paid_report_of_refusals(tmp_path)
    outcome = checker.check(report_path)

    assert outcome["counts"]["failed"] == 0, [
        entry for entry in outcome["conditions"] if entry["result"] == "fail"
    ]
    assert _condition(outcome, 2)["result"] == "unanswerable"
    assert _condition(outcome, 2)["unanswerable_because"] == checker.UNANSWERABLE_NO_MODEL_RAN
    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE

    printed = checker.render(outcome)
    assert "inconclusive" in printed
    assert "condition 2" in printed
    assert "rehearsal_ok" not in printed
    assert checker.main([str(report_path)]) == 0


def test_the_word_rehearsal_is_kept_for_runs_that_spent_nothing(tmp_path, corpus):
    """The other half of the same distinction.

    A stub run is unanswerable on condition 2 as well, for a different reason
    — there is no provider present to report an audio token count — and that
    one keeps ``rehearsal_ok``. If both said ``inconclusive`` the verdict
    would stop distinguishing a free run from a paid one, which is the thing
    it is for.
    """
    document = _document(tmp_path / "prereg.md", corpus=corpus)
    _, report_path = _run(tmp_path, corpus, document)
    outcome = checker.check(report_path)

    assert _condition(outcome, 2)["unanswerable_because"] == checker.UNANSWERABLE_REHEARSAL
    assert outcome["verdict"] == checker.VERDICT_REHEARSAL_OK
