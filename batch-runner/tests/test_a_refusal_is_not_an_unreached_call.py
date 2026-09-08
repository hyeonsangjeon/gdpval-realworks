"""A status code is an answer, so reachability is not what is unknown.

`MeteredClient` writes the ledger row *before* the request and settles it after
the reply. When the call raised, there was no `except`, so `settle` was never
reached and the row stayed `reserved` — the state whose whole meaning is *"a
request went out and we never learned what became of it"*, reported to a reader
as `call_reachability_unknown`.

For a provider refusal that sentence is false in the one way that matters. A
`400` is not a silence; it is the API replying, and replying is the proof the
request arrived. `core/perception/audio.py` already knows this about eight
statuses and acts on it — it hands the task's attempt back — but the ledger was
never told, so the same eight came out filed under a doubt about whether the
request ever landed.

The amount was never wrong. `reserved` claims nothing, which is far safer than
claiming `$0`. What was wrong is the label, and the label is the part a person
acts on: `call_reachability_unknown` means *go and find out whether this was
billed*. Fifty rate-limit bounces produce fifty of those, all certainly free,
and the genuinely unknown ones — a `5xx`, a timeout — disappear into the pile.

So this file pins the distinction, in both directions:

* a refusal is recorded as `refused`, is still **counted** as a call, still
  claims **no amount**, and still holds the receipt at `partial`. Knowing the
  model did not run is not the provider's word that the account was untouched,
  and this change was never licensed to turn a `400` into a complete, free
  receipt;
* a `5xx`, a timeout and a dropped connection keep their reservations exactly
  as before. If any of those moved, the fix would have reached past the thing
  it was for.

Nothing here contacts a provider. Every client is local and raises on demand.
"""

import json
from decimal import Decimal

import pytest

from core.cost_metering import (
    FAILURE_ANSWERED,
    FAILURE_REFUSED,
    FAILURE_TIMEOUT,
    FAILURE_UNKNOWN,
    UNBILLED_STATUSES,
    CostRecorder,
    classify_call_failure,
)
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    REASON_CALL_REACHABILITY_UNKNOWN,
    REASON_CALL_REFUSED_UNPRICED,
    REASON_USAGE_ABSENT,
    MISSING_REASONS,
    STAGE_GENERATION,
    STATE_ABANDONED,
    STATE_REFUSED,
    STATE_RESERVED,
    STATE_SETTLED,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    CostReceiptLedger,
    LedgerIntegrityError,
    load_receipt_price_table,
)

REFUSAL_STATUSES = sorted(UNBILLED_STATUSES)

PRICE_TABLE = {
    "cost_receipt_schema_version": "cost-receipt-price-table-v1",
    "providers": {
        "azure:test-model": {
            "input_usd_per_million": "10",
            "cached_input_usd_per_million": "1",
            "output_usd_per_million": "20",
            "reasoning_billed_as": "output",
            "source": "fixture",
            "last_reviewed": "2026-08-28",
            "currency": "USD",
            "unit": "per 1,000,000 tokens",
        }
    },
    "runtime": {},
}


@pytest.fixture
def price_table(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(PRICE_TABLE), encoding="utf-8")
    return load_receipt_price_table(path)


@pytest.fixture
def ledger(tmp_path, price_table):
    with CostReceiptLedger(
        tmp_path / "cost.sqlite3", run_id="run-1", price_table=price_table
    ) as opened:
        yield opened


@pytest.fixture
def recorder(ledger):
    return CostRecorder(ledger)


# ── stand-in clients ─────────────────────────────────────────────────────


class _Bag:
    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)


def _reply(prompt=100_000, completion=10_000):
    return _Bag(
        model="test-model",
        usage=_Bag(prompt_tokens=prompt, completion_tokens=completion),
    )


class Refused(Exception):
    """The shape an SDK raises when the provider answers with a rejection."""

    def __init__(self, status, message="refused"):
        super().__init__(message)
        self.status_code = status


class RefusedViaResponse(Exception):
    """The other shape: the status hangs off a `response` object."""

    def __init__(self, status):
        super().__init__("refused")
        self.response = _Bag(status_code=status)


class Client:
    def __init__(self, reply=None, *, raises=None):
        self._reply = reply if reply is not None else _reply()
        self._raises = raises
        self.calls = []
        self.chat = _Bag(completions=_Bag(create=self._create))
        self.api_version = "2026-01-01"

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return self._reply


def _call(recorder, error, task_id="task-a"):
    """Drive one metered call that fails, and hand back its row."""
    client = recorder.meter(Client(raises=error), provider="azure")
    with recorder.attributed(task_id=task_id, stage=STAGE_GENERATION):
        with pytest.raises(type(error)):
            client.chat.completions.create(model="a-deployment", messages=[])
    rows = recorder.ledger.calls_for(task_id)
    return rows[-1], recorder.receipt_for(task_id, BUCKET_PROBLEM_SOLVING)


# ── the defect ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("status", REFUSAL_STATUSES)
def test_a_refusal_is_not_recorded_as_a_call_that_might_never_have_arrived(
    recorder, status
):
    row, receipt = _call(recorder, Refused(status))

    assert row["state"] == STATE_REFUSED, (
        f"a {status} left the row {row['state']!r}: the provider answered, so "
        "this is not a call whose arrival is in doubt"
    )
    assert REASON_CALL_REACHABILITY_UNKNOWN not in receipt.missing_reasons
    assert REASON_CALL_REFUSED_UNPRICED in receipt.missing_reasons
    assert row["note"] == f"provider_refused_{status}"


@pytest.mark.parametrize("status", REFUSAL_STATUSES)
def test_a_refusal_still_costs_the_receipt_its_certainty(recorder, status):
    """The reason was wrong. The amount was not, and does not move.

    A refusal says the model did not run. It is not the provider stating that
    nothing was charged, and the ledger only ever reports what it was told —
    so the receipt claims no figure and stays `partial`, exactly as the
    reservation did. Turning `400` into a complete, free receipt would fix a
    label by inventing a fact.
    """
    _, receipt = _call(recorder, Refused(status))

    assert receipt.status == STATUS_PARTIAL
    assert receipt.estimated_cost_usd is None
    assert receipt.known_cost_usd == Decimal(0)


@pytest.mark.parametrize("status", REFUSAL_STATUSES)
def test_a_refusal_is_still_a_call_that_was_made(recorder, status):
    """Counted, unlike an abandoned row, because a request really went out.

    `build_receipt` drops abandoned rows wholesale. Routing a refusal there —
    the obvious cheap fix — would quietly take the task's `model_calls` down by
    one and say no call was made, of a call the provider has a record of.
    """
    _, receipt = _call(recorder, Refused(status))

    assert receipt.model_calls == 1


def test_the_status_is_read_from_a_response_object_too(recorder):
    row, _ = _call(recorder, RefusedViaResponse(400))

    assert row["state"] == STATE_REFUSED
    assert row["note"] == "provider_refused_400"


# ── the four failures that must not move ─────────────────────────────────


@pytest.mark.parametrize("status", [500, 502, 503, 504, 408, 409, 418])
def test_any_other_status_keeps_its_reservation(recorder, status):
    """A `5xx` may be a gateway that never reached the model, or a model that
    ran and then failed to deliver. This layer cannot tell, and an unsettled
    reservation is what "cannot tell" looks like."""
    row, receipt = _call(recorder, Refused(status))

    assert row["state"] == STATE_RESERVED
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt.missing_reasons
    assert REASON_CALL_REFUSED_UNPRICED not in receipt.missing_reasons
    assert receipt.estimated_cost_usd is None
    assert row["note"] == f"provider_status_{status}"


def test_a_timeout_keeps_its_reservation(recorder):
    row, receipt = _call(recorder, TimeoutError("no reply"))

    assert row["state"] == STATE_RESERVED
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt.missing_reasons
    assert row["note"] == "provider_timeout"


def test_a_dropped_connection_keeps_its_reservation(recorder):
    class Dropped(Exception):
        pass

    row, receipt = _call(recorder, Dropped("connection reset"))

    assert row["state"] == STATE_RESERVED
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt.missing_reasons
    assert row["note"] == "provider_error_Dropped"


def test_a_message_that_mentions_a_timeout_is_not_a_timeout(recorder):
    """Classified on the failure's shape, never on the provider's prose.

    A message is attacker- and vendor-controlled text. Reading "gateway
    timeout" out of a `RuntimeError` would let wording decide a bookkeeping
    state, and would have quietly reclassified an existing test's error.
    """
    row, _ = _call(recorder, RuntimeError("gateway timeout"))

    assert row["note"] == "provider_error_RuntimeError"


# ── the five cases the record has to tell apart ──────────────────────────


def test_the_five_endings_a_call_can_have_are_five_different_records(
    recorder, tmp_path
):
    """One row each, and no two of them say the same thing.

    A verifiable answer, a failure known to predate the request, a call whose
    fate is unknown, a reply that carried no usage, and a timeout. Before this
    change three of the five were the same row: `reserved` with
    `call_reachability_unknown`.
    """
    endings = {}

    row, _ = _call(recorder, Refused(400), task_id="answered")
    endings["a verifiable refusal"] = (row["state"], row["note"])

    client = recorder.meter(
        Client(raises=ValueError("prompt could not be assembled")),
        provider="azure",
    )
    with recorder.attributed(task_id="unsent", stage=STAGE_GENERATION):
        with pytest.raises(ValueError):
            client.chat.completions.create(model="a-deployment", messages=[])
        recorder.abandon_call(client.last_call_id, note="request never built")
    row = recorder.ledger.calls_for("unsent")[-1]
    endings["known not to have left"] = (row["state"], row["note"])

    class Dropped(Exception):
        pass

    row, _ = _call(recorder, Dropped("reset"), task_id="unknown")
    endings["may or may not have arrived"] = (row["state"], row["note"])

    client = recorder.meter(
        Client(reply=_Bag(model="test-model")), provider="azure"
    )
    with recorder.attributed(task_id="silent", stage=STAGE_GENERATION):
        client.chat.completions.create(model="a-deployment", messages=[])
    row = recorder.ledger.calls_for("silent")[-1]
    endings["answered without usage"] = (row["state"], row["note"])

    row, _ = _call(recorder, TimeoutError("no reply"), task_id="timeout")
    endings["timed out"] = (row["state"], row["note"])

    assert len(set(endings.values())) == 5, endings
    assert endings["answered without usage"][0] == STATE_SETTLED
    assert REASON_USAGE_ABSENT in recorder.receipt_for(
        "silent", BUCKET_PROBLEM_SOLVING
    ).missing_reasons
    assert endings["known not to have left"][0] == STATE_ABANDONED


# ── what the note may contain ────────────────────────────────────────────


def test_a_note_never_carries_the_providers_own_words(recorder):
    """The ledger is committed to disk and shipped between shards.

    Provider error messages routinely quote the request URL, and can quote a
    header. A note built from `str(error)` would make the ledger a place
    secrets end up, for the sake of a diagnostic string.
    """
    secret = "sk-live-0123456789abcdef"
    endpoint = "https://an-account.openai.azure.com/openai/v1/"
    message = f"401 from {endpoint} using {secret}"

    for error in (
        Refused(401, message),
        TimeoutError(message),
        RuntimeError(message),
    ):
        row, _ = _call(recorder, error, task_id=f"task-{type(error).__name__}")
        recorded = json.dumps(dict(row))
        assert secret not in recorded
        assert endpoint not in recorded
        assert "an-account" not in recorded


def test_a_note_is_a_slug_whatever_the_exception_is_called(recorder):
    hostile = type("Bad Name https://x.example/y", (Exception,), {})

    row, _ = _call(recorder, hostile("boom"))

    assert row["note"] == "provider_error_BadNamehttpsxexampley"
    assert " " not in row["note"] and "/" not in row["note"]


# ── the ledger's own contract ────────────────────────────────────────────


def test_a_settled_call_cannot_be_refused_afterwards(ledger):
    call_id = _reserve(ledger)
    ledger.settle(call_id, usage=_usage(), resolved_model="test-model")

    with pytest.raises(LedgerIntegrityError):
        ledger.refuse(call_id, status=400)


def test_a_refused_call_cannot_report_usage_afterwards(ledger):
    call_id = _reserve(ledger)
    ledger.refuse(call_id, status=400)

    with pytest.raises(LedgerIntegrityError):
        ledger.settle(call_id, usage=_usage(), resolved_model="test-model")


def test_a_refused_call_cannot_then_be_called_one_that_never_left(ledger):
    call_id = _reserve(ledger)
    ledger.refuse(call_id, status=400)

    with pytest.raises(LedgerIntegrityError):
        ledger.abandon(call_id, note="never built")


def test_an_abandoned_call_cannot_then_have_been_answered(ledger):
    call_id = _reserve(ledger)
    ledger.abandon(call_id, note="never built")

    with pytest.raises(LedgerIntegrityError):
        ledger.refuse(call_id, status=400)


def test_refusing_a_call_that_was_never_reserved_is_an_error(ledger):
    with pytest.raises(LedgerIntegrityError):
        ledger.refuse("never-seen", status=400)


def test_the_same_refusal_twice_is_the_same_row(ledger):
    """Resume re-plays work; a repeat of the same fact is not a contradiction."""
    call_id = _reserve(ledger)
    ledger.refuse(call_id, status=429)
    ledger.refuse(call_id, status=429)

    rows = ledger.calls_for("task-a")
    assert len(rows) == 1
    assert rows[0]["missing_reasons"] == [REASON_CALL_REFUSED_UNPRICED]


def test_two_different_refusals_for_one_call_are_a_contradiction(ledger):
    call_id = _reserve(ledger)
    ledger.refuse(call_id, status=429)

    with pytest.raises(LedgerIntegrityError):
        ledger.refuse(call_id, status=400)


def test_an_open_question_may_only_be_annotated_while_it_is_open(ledger):
    call_id = _reserve(ledger)
    ledger.settle(call_id, usage=_usage(), resolved_model="test-model")

    with pytest.raises(LedgerIntegrityError):
        ledger.leave_unresolved(call_id, note="provider_timeout")


def test_the_first_note_on_an_open_question_is_the_one_kept(ledger):
    """The first failure is the one that explains the reservation."""
    call_id = _reserve(ledger)
    ledger.leave_unresolved(call_id, note="provider_timeout")
    ledger.leave_unresolved(call_id, note="provider_error_Later")

    assert ledger.calls_for("task-a")[0]["note"] == "provider_timeout"


# ── resume, merge, and files written before this existed ─────────────────


def test_a_merged_shard_does_not_put_the_false_reason_back(tmp_path, price_table):
    """The local row knows the request left; the export knows how it ended.

    Leaving `refused` out of the promotion would have restored, through the
    merge path, the exact sentence this change retires.
    """
    export = tmp_path / "shard.jsonl"

    with CostReceiptLedger(
        tmp_path / "shard.sqlite3", run_id="run-1", price_table=price_table
    ) as shard:
        call_id = _reserve(shard)
        shard.refuse(call_id, status=400)
        shard.export_jsonl(export)

    with CostReceiptLedger(
        tmp_path / "merged.sqlite3", run_id="run-1", price_table=price_table
    ) as merged:
        _reserve(merged, call_id=call_id)
        assert merged.receipt_for("task-a", BUCKET_PROBLEM_SOLVING).missing_reasons == (
            REASON_CALL_REACHABILITY_UNKNOWN,
        )

        merged.import_jsonl(export)

        receipt = merged.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)
        assert merged.calls_for("task-a")[0]["state"] == STATE_REFUSED
        assert receipt.missing_reasons == (REASON_CALL_REFUSED_UNPRICED,)
        assert receipt.model_calls == 1


def test_importing_the_same_refusal_twice_settles_nothing_twice(
    tmp_path, price_table
):
    export = tmp_path / "shard.jsonl"

    with CostReceiptLedger(
        tmp_path / "shard.sqlite3", run_id="run-1", price_table=price_table
    ) as shard:
        call_id = _reserve(shard)
        shard.refuse(call_id, status=400)
        shard.export_jsonl(export)

    with CostReceiptLedger(
        tmp_path / "merged.sqlite3", run_id="run-1", price_table=price_table
    ) as merged:
        assert merged.import_jsonl(export) == 1
        assert merged.import_jsonl(export) == 0
        assert len(merged.calls_for("task-a")) == 1
        assert merged.receipt_for(
            "task-a", BUCKET_PROBLEM_SOLVING
        ).model_calls == 1


def test_a_refused_row_is_not_overwritten_by_one_claiming_usage(
    tmp_path, price_table
):
    """Two records of one call that cannot both be true.

    The token comparison that guards every other merge cannot see this: a
    refused row holds no counts, so its silence would read as agreement.
    """
    export = tmp_path / "settled.jsonl"

    with CostReceiptLedger(
        tmp_path / "other.sqlite3", run_id="run-1", price_table=price_table
    ) as other:
        call_id = _reserve(other)
        other.settle(call_id, usage=_usage(), resolved_model="test-model")
        other.export_jsonl(export)

    with CostReceiptLedger(
        tmp_path / "local.sqlite3", run_id="run-1", price_table=price_table
    ) as local:
        _reserve(local, call_id=call_id)
        local.refuse(call_id, status=400)

        with pytest.raises(LedgerIntegrityError):
            local.import_jsonl(export)

        assert local.calls_for("task-a")[0]["state"] == STATE_REFUSED


def test_a_ledger_written_before_refusals_existed_reads_exactly_as_it_did(
    tmp_path, price_table
):
    """No migration, no rewrite, no new column: only a value that never occurs.

    A resumed run reopens its predecessor's file. Every row in one written
    yesterday is `reserved`, `settled` or `abandoned`, and each still means
    what it meant.
    """
    path = tmp_path / "yesterday.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=price_table) as old:
        settled = _reserve(old, call_id="call-settled")
        old.settle(settled, usage=_usage(), resolved_model="test-model")
        _reserve(old, call_id="call-open")
        abandoned = _reserve(old, call_id="call-unsent")
        old.abandon(abandoned, note="never built")
        before = old.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    with CostReceiptLedger(path, run_id="run-2", price_table=price_table) as today:
        after = today.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)
        states = {row["call_id"]: row["state"] for row in today.calls_for("task-a")}

    assert after.status == before.status == STATUS_PARTIAL
    assert after.model_calls == before.model_calls == 2
    assert after.missing_reasons == before.missing_reasons
    assert REASON_CALL_REACHABILITY_UNKNOWN in after.missing_reasons
    assert states == {
        "call-settled": STATE_SETTLED,
        "call-open": STATE_RESERVED,
        "call-unsent": STATE_ABANDONED,
    }


def test_a_task_whose_only_call_was_refused_does_not_report_a_free_receipt(
    recorder,
):
    """The whole constraint, on the smallest possible receipt.

    One call, refused. `complete` here would be the ledger stating that the
    task cost nothing, on the strength of a status code that says only that a
    model did not run.
    """
    _, receipt = _call(recorder, Refused(429))

    assert receipt.status != STATUS_COMPLETE
    assert receipt.estimated_cost_usd is None


# ── the two lists that must not drift ────────────────────────────────────


def test_the_ledger_and_the_audio_reader_refuse_on_the_same_statuses():
    """One judgement about the same eight statuses, made in two places.

    The audio adapter decides whether a failed read costs the task one of its
    allowed attempts; the ledger decides whether a failure is an answer or a
    silence. Different questions, same evidence — and two copies of the
    evidence would drift with nothing red.
    """
    from core.perception.audio import _UNBILLED_STATUS

    assert set(_UNBILLED_STATUS) == set(UNBILLED_STATUSES)


def test_every_reason_the_ledger_can_write_is_one_a_grade_may_carry():
    """`grade.schema.json` closes its reason list with an `enum`.

    A reason added in Python and not there is not a lenient mismatch: the grade
    record fails validation at the end of a paid run, which is the worst moment
    to discover a vocabulary is out of step.
    """
    import pathlib

    schema = json.loads(
        (pathlib.Path(__file__).resolve().parents[1] / "schemas" / "grade.schema.json")
        .read_text(encoding="utf-8")
    )
    published = set(schema["$defs"]["costMissingReason"]["enum"])

    assert set(MISSING_REASONS) == published


# ── the classifier on its own ────────────────────────────────────────────


@pytest.mark.parametrize("status", REFUSAL_STATUSES)
def test_the_classifier_calls_a_refusal_a_refusal(status):
    failure = classify_call_failure(Refused(status))

    assert failure.kind == FAILURE_REFUSED
    assert failure.status == status
    assert failure.billing_is_known_absent


@pytest.mark.parametrize(
    "error, kind",
    [
        (Refused(500), FAILURE_ANSWERED),
        (TimeoutError("x"), FAILURE_TIMEOUT),
        (RuntimeError("x"), FAILURE_UNKNOWN),
    ],
)
def test_the_classifier_claims_nothing_about_the_rest(error, kind):
    failure = classify_call_failure(error)

    assert failure.kind == kind
    assert not failure.billing_is_known_absent


def test_a_status_that_is_not_a_number_is_not_a_status():
    class Odd(Exception):
        status_code = "four hundred"

    assert classify_call_failure(Odd()).status is None


def test_a_boolean_is_not_a_status():
    """`True` is an `int` in Python, and `int(True)` is 1, not a status."""

    class Odd(Exception):
        status_code = True

    assert classify_call_failure(Odd()).status is None


# ── the ledger verifier downstream ───────────────────────────────────────


def test_the_verifier_does_not_call_a_refused_row_a_missing_reply():
    """A false alarm here would bury the rows that are real, which is the same
    mistake one layer up."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from verify_cost_ledger import check_all_calls_settled

    finding = check_all_calls_settled(
        [
            {"call_id": "c1", "state": STATE_SETTLED},
            {"call_id": "c2", "state": STATE_REFUSED},
            {"call_id": "c3", "state": STATE_ABANDONED},
        ]
    )

    assert finding.ok is True
    assert finding.data["other_states"] == {STATE_ABANDONED: 1, STATE_REFUSED: 1}


def test_the_verifier_still_surfaces_a_reply_that_never_came():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from verify_cost_ledger import check_all_calls_settled

    finding = check_all_calls_settled(
        [
            {"call_id": "c1", "state": STATE_SETTLED},
            {"call_id": "c2", "state": STATE_RESERVED, "note": "provider_timeout"},
        ]
    )

    assert finding.ok is False
    assert finding.data["unsettled_count"] == 1
    assert finding.data["unsettled"][0]["note"] == "provider_timeout"


# ── helpers ──────────────────────────────────────────────────────────────


def _usage():
    from core.cost_receipts import CallUsage

    return CallUsage(input_tokens=100_000, output_tokens=10_000)


def _reserve(ledger, *, call_id="call-1", task_id="task-a"):
    from core.cost_receipts import RETRY_NONE

    return ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model="test-model",
    )
