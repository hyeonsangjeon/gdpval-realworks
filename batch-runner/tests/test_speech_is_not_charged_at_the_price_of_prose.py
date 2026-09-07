"""Audio tokens are part of a call, priced at their own rate or not at all.

The grading ledger holds 176 settled calls to a speech model. Every one of
them is ``price_missing``, which is correct — Azure publishes no meter for that
model — but it is correct for a reason that would stop protecting anything the
moment somebody sourced a rate. Nothing refused those calls; the lookup simply
returned nothing, and :func:`price_call` never reached the arithmetic. Add one
price entry with the ordinary text fields and the same code would multiply the
whole input by the text rate, speech included, and return a confident number
that no invoice would agree with.

That is what these tests close. Two independent things had to be established
before the rule could be written, and both came out of stored evidence rather
than assumption:

*Where audio sits.* The sixty stored calls of the 331 speech diagnostic record
the usage block beside the audio each request carried. Subtracting the reported
audio tokens from the reported input collapses the input's correlation with
clip length and sharpens its correlation with prompt length. Audio is inside
the input, not beside it.

*How much of the call it is.* 1,848 tokens of 18,924. A total built from the
audio count alone would price a tenth of the work.

So: an entry that does not price audio refuses audio, an entry that does prices
each share once, and no arrangement of the two produces a number by accident.
Every test runs on mock responses and a temporary table. Nothing here calls a
provider.
"""

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.cost_metering import CostRecorder, extract_usage
from core.cost_receipts import (
    AUDIO_BILLED_SEPARATELY,
    AUDIO_BILLED_UNPRICED,
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    REASON_PRICE_MISSING,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    RETRY_INFRASTRUCTURE,
    RETRY_NONE,
    STAGE_PERCEPTION,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    CallUsage,
    CostReceiptLedger,
    LedgerIntegrityError,
    build_receipt,
    load_receipt_price_table,
    make_call_id,
    price_call,
)

# ── tables ───────────────────────────────────────────────────────────────

#: What every entry in the committed table looks like today: text rates only.
#: It does not mention audio, which means it does not price audio.
TEXT_ONLY = {
    "input_usd_per_million": "2.50",
    "cached_input_usd_per_million": "0.25",
    "output_usd_per_million": "15.00",
    "reasoning_billed_as": "output",
    "source": "https://example.invalid/prices",
    "last_reviewed": "2026-09-07",
    "currency": "USD",
    "unit": "per 1,000,000 tokens",
}

#: What an entry would look like if a rate were ever published. The numbers are
#: invented for the test and are never written to the committed table; what is
#: under test is the arithmetic they drive, not the amounts.
WITH_AUDIO = {
    **TEXT_ONLY,
    "audio_billed_as": AUDIO_BILLED_SEPARATELY,
    "audio_input_usd_per_million": "40.00",
    "audio_output_usd_per_million": "80.00",
}


def _table(tmp_path, entries, *, name="prices.json"):
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "cost_receipt_schema_version": "cost-receipt-price-table-v1",
                "providers": entries,
            }
        ),
        encoding="utf-8",
    )
    return load_receipt_price_table(path)


@pytest.fixture
def text_only_table(tmp_path):
    return _table(tmp_path, {"azure:a-speech-model": dict(TEXT_ONLY)})


@pytest.fixture
def audio_table(tmp_path):
    return _table(tmp_path, {"azure:a-speech-model": dict(WITH_AUDIO)})


def _price(table, usage):
    return price_call(table.lookup("azure", "a-speech-model"), usage)


# ── the refusal ──────────────────────────────────────────────────────────


def test_a_call_that_carried_audio_is_not_priced_from_text_rates(text_only_table):
    """The defect this file exists for, in one assertion.

    Same call, same tokens, but part of the input was speech. An entry holding
    only text rates has no rate for that part, so the call has no price — not a
    price computed from the part it does have a rate for.
    """
    priced = _price(
        text_only_table,
        CallUsage(
            input_tokens=415,
            cached_input_tokens=0,
            output_tokens=67,
            reasoning_tokens=0,
            audio_input_tokens=30,
            audio_output_tokens=0,
        ),
    )
    assert priced.cost_usd is None
    assert priced.missing_reasons == (REASON_PRICE_MISSING,)


def test_the_same_call_without_audio_is_priced_normally(text_only_table):
    """The refusal is about audio, not about the model or the token counts."""
    priced = _price(
        text_only_table,
        CallUsage(input_tokens=415, cached_input_tokens=0, output_tokens=67),
    )
    assert priced.is_priced
    # 415 at 2.50 + 67 at 15.00, per million.
    assert priced.cost_usd == (
        Decimal(415) * Decimal("2.50") + Decimal(67) * Decimal("15.00")
    ) / Decimal(1_000_000)


def test_an_audio_only_output_also_refuses(text_only_table):
    """Speech coming back is as unpriceable as speech going out."""
    priced = _price(
        text_only_table,
        CallUsage(
            input_tokens=100,
            output_tokens=50,
            audio_input_tokens=0,
            audio_output_tokens=50,
        ),
    )
    assert priced.cost_usd is None
    assert REASON_PRICE_MISSING in priced.missing_reasons


def test_a_zero_audio_count_is_not_audio(text_only_table):
    """A reported zero says speech did not happen. It must not trip the rule.

    A deployment that can accept audio reports the split on every call,
    including the text-only ones. Treating a reported zero as "this call had
    audio" would make every text call to such a deployment unpriceable.
    """
    priced = _price(
        text_only_table,
        CallUsage(
            input_tokens=415,
            output_tokens=67,
            audio_input_tokens=0,
            audio_output_tokens=0,
        ),
    )
    assert priced.is_priced


def test_the_committed_table_prices_no_audio_at_all():
    """Every entry in the real file is text-only, and that is deliberate.

    If this ever fails, a rate was added — which is allowed, but only with a
    source, and only after checking that the arithmetic below is what should
    apply to it.
    """
    table = load_receipt_price_table()
    assert table.models, "the committed table has no entries at all"
    for key, price in table.models.items():
        assert price.audio_billed_as == AUDIO_BILLED_UNPRICED, key
        assert price.prices_audio is False, key


def test_the_speech_model_is_still_absent_from_the_committed_table():
    """No rate was invented for it while writing the contract that would hold one."""
    table = load_receipt_price_table()
    assert table.lookup("azure", "gpt-audio-1.5") is None


# ── the arithmetic, once a rate exists ───────────────────────────────────


def test_audio_inside_the_input_is_charged_once_at_its_own_rate(audio_table):
    """The containment the stored calls established, made arithmetic.

    1,000 input tokens of which 100 were speech is 900 text tokens and 100
    audio tokens — not 1,000 text tokens, and not 1,100 tokens of anything.
    """
    priced = _price(
        audio_table,
        CallUsage(
            input_tokens=1000,
            cached_input_tokens=0,
            output_tokens=200,
            audio_input_tokens=100,
            audio_output_tokens=0,
        ),
    )
    expected = (
        Decimal(900) * Decimal("2.50")
        + Decimal(100) * Decimal("40.00")
        + Decimal(200) * Decimal("15.00")
    ) / Decimal(1_000_000)
    assert priced.cost_usd == expected


def test_the_audio_share_is_not_added_on_top_of_a_full_text_charge(audio_table):
    """The double-billing this is really about, stated as an inequality.

    Charging the whole input at the text rate and the audio share again at the
    audio rate bills those 100 tokens twice. The result must be strictly less
    than that.
    """
    usage = CallUsage(
        input_tokens=1000,
        output_tokens=200,
        audio_input_tokens=100,
        audio_output_tokens=0,
    )
    priced = _price(audio_table, usage)
    double_billed = (
        Decimal(1000) * Decimal("2.50")
        + Decimal(100) * Decimal("40.00")
        + Decimal(200) * Decimal("15.00")
    ) / Decimal(1_000_000)
    assert priced.cost_usd < double_billed
    assert double_billed - priced.cost_usd == (
        Decimal(100) * Decimal("2.50")
    ) / Decimal(1_000_000)


def test_the_audio_share_alone_is_not_the_call(audio_table):
    """1,848 tokens of 18,924 — the number the whole task warned against.

    Pricing the audio count on its own and calling it the cost of the run is
    the failure mode this contract exists to make impossible. The real total is
    strictly larger, because the other 90.2% of the input still happened.
    """
    usage = CallUsage(
        input_tokens=18924,
        cached_input_tokens=0,
        output_tokens=4223,
        audio_input_tokens=1848,
        audio_output_tokens=0,
    )
    priced = _price(audio_table, usage)
    audio_only = (Decimal(1848) * Decimal("40.00")) / Decimal(1_000_000)
    assert priced.cost_usd > audio_only
    # The text remainder is 17,076 tokens — the part an audio-only figure drops.
    assert priced.cost_usd - audio_only == (
        Decimal(17076) * Decimal("2.50") + Decimal(4223) * Decimal("15.00")
    ) / Decimal(1_000_000)


def test_audio_in_the_output_is_charged_once_at_its_own_rate(audio_table):
    priced = _price(
        audio_table,
        CallUsage(
            input_tokens=1000,
            output_tokens=200,
            audio_input_tokens=0,
            audio_output_tokens=50,
        ),
    )
    expected = (
        Decimal(1000) * Decimal("2.50")
        + Decimal(150) * Decimal("15.00")
        + Decimal(50) * Decimal("80.00")
    ) / Decimal(1_000_000)
    assert priced.cost_usd == expected


def test_a_text_call_on_an_audio_capable_entry_costs_what_it_used_to(audio_table):
    """Adding audio rates must not change what a text call costs.

    The audio branch reduces to the text arithmetic when nothing was spoken,
    which is what lets a rate be added to an entry without silently re-pricing
    every text call already settled against it.
    """
    usage = CallUsage(
        input_tokens=1000,
        cached_input_tokens=400,
        output_tokens=200,
        audio_input_tokens=0,
        audio_output_tokens=0,
    )
    expected = (
        Decimal(600) * Decimal("2.50")
        + Decimal(400) * Decimal("0.25")
        + Decimal(200) * Decimal("15.00")
    ) / Decimal(1_000_000)
    assert _price(audio_table, usage).cost_usd == expected


def test_reasoning_inside_the_output_is_still_not_charged_twice(audio_table):
    """Two containment rules on one call, and neither one double-bills.

    Audio is a share of the output and so is reasoning, and the entry bills
    reasoning inside the output. The audio share comes out at the audio rate;
    the reasoning share does not come out at all, because it is already paid
    for by whichever rate covers the tokens it sits in.
    """
    usage = CallUsage(
        input_tokens=1000,
        output_tokens=200,
        reasoning_tokens=120,
        audio_input_tokens=0,
        audio_output_tokens=50,
    )
    without_reasoning = CallUsage(
        input_tokens=1000,
        output_tokens=200,
        audio_input_tokens=0,
        audio_output_tokens=50,
    )
    assert _price(audio_table, usage).cost_usd == _price(
        audio_table, without_reasoning
    ).cost_usd


# ── the refusals that are about the numbers, not the rates ───────────────


def test_more_audio_than_input_is_a_contradiction(audio_table):
    """A share larger than the whole. Neither number can be trusted after that."""
    priced = _price(
        audio_table,
        CallUsage(input_tokens=100, output_tokens=50, audio_input_tokens=500),
    )
    assert priced.cost_usd is None
    assert REASON_USAGE_PARTIAL in priced.missing_reasons


def test_more_audio_than_output_is_a_contradiction(audio_table):
    priced = _price(
        audio_table,
        CallUsage(input_tokens=100, output_tokens=50, audio_output_tokens=90),
    )
    assert priced.cost_usd is None
    assert REASON_USAGE_PARTIAL in priced.missing_reasons


def test_a_contradiction_is_caught_even_where_no_audio_rate_exists(text_only_table):
    """The check is on the reported usage, so it does not need a price to fire."""
    priced = _price(
        text_only_table,
        CallUsage(input_tokens=100, output_tokens=50, audio_input_tokens=500),
    )
    assert priced.cost_usd is None
    assert REASON_USAGE_PARTIAL in priced.missing_reasons
    assert REASON_PRICE_MISSING in priced.missing_reasons


def test_cache_and_audio_together_are_left_unsplit(audio_table):
    """The axis that stored evidence does not settle, refused rather than guessed.

    Two rates would apply to this input and nothing says whether the cached
    tokens are the spoken ones. Choosing an overlap would be inventing the one
    fact the data does not contain, so no number is produced.
    """
    priced = _price(
        audio_table,
        CallUsage(
            input_tokens=1000,
            cached_input_tokens=400,
            output_tokens=200,
            audio_input_tokens=100,
            audio_output_tokens=0,
        ),
    )
    assert priced.cost_usd is None
    assert REASON_USAGE_PARTIAL in priced.missing_reasons


def test_an_audio_priced_entry_needs_the_split_to_be_reported(audio_table):
    """Two rates and no boundary between them is not something to assume.

    A provider that bills audio separately reports the split on every call. An
    absent split against such an entry is therefore a breakdown that was not
    read, not one that was not sent — and reading it as "no audio" would charge
    speech at the text rate by the back door.
    """
    priced = _price(
        audio_table, CallUsage(input_tokens=1000, output_tokens=200)
    )
    assert priced.cost_usd is None
    assert priced.missing_reasons == (REASON_USAGE_PARTIAL,)


def test_a_reply_with_no_usage_at_all_is_still_simply_absent(audio_table):
    """The new rules do not reclassify an empty usage block as a partial one."""
    priced = _price(audio_table, CallUsage())
    assert priced.cost_usd is None
    assert REASON_USAGE_ABSENT in priced.missing_reasons


# ── what the table will and will not accept ──────────────────────────────


def test_an_audio_rate_that_would_never_apply_is_rejected(tmp_path):
    """A rate sitting in an entry that does not bill audio separately.

    It would never be used, and an entry carrying one reads as a priced model
    to anyone opening the file. Loudly wrong beats quietly ignored.
    """
    entry = {**TEXT_ONLY, "audio_input_usd_per_million": "40.00"}
    with pytest.raises(ValueError, match="audio_billed_as"):
        _table(tmp_path, {"azure:a-speech-model": entry})


def test_half_an_audio_rate_is_rejected(tmp_path):
    """Input priced and output not is not a price for a call that has both."""
    entry = {
        **TEXT_ONLY,
        "audio_billed_as": AUDIO_BILLED_SEPARATELY,
        "audio_input_usd_per_million": "40.00",
    }
    with pytest.raises(ValueError, match="audio_output_usd_per_million"):
        _table(tmp_path, {"azure:a-speech-model": entry})


def test_an_unrecognised_audio_billing_mode_is_rejected(tmp_path):
    """Including the one that sounds most reasonable.

    "text" — audio billed at the text rate — is exactly the assumption this
    contract exists to refuse, so it is not a value the table can express.
    """
    entry = {**TEXT_ONLY, "audio_billed_as": "text"}
    with pytest.raises(ValueError, match="audio"):
        _table(tmp_path, {"azure:a-speech-model": entry})


def test_an_audio_rate_still_needs_a_source(tmp_path):
    """The existing rule covers the new fields; a rate nobody can trace is not one."""
    entry = {**WITH_AUDIO}
    entry.pop("source")
    with pytest.raises(ValueError, match="source"):
        _table(tmp_path, {"azure:a-speech-model": entry})


# ── reading the split off a reply ────────────────────────────────────────


def _response(**details):
    return SimpleNamespace(usage=SimpleNamespace(**details))


def test_the_audio_split_is_read_from_a_responses_reply():
    usage = extract_usage(
        _response(
            input_tokens=415,
            output_tokens=67,
            input_tokens_details=SimpleNamespace(audio_tokens=30, cached_tokens=0),
            output_tokens_details=SimpleNamespace(audio_tokens=0),
        )
    )
    assert usage.audio_input_tokens == 30
    assert usage.audio_output_tokens == 0
    assert usage.input_tokens == 415


def test_the_audio_split_is_read_from_a_chat_completions_reply():
    usage = extract_usage(
        _response(
            prompt_tokens=415,
            completion_tokens=67,
            prompt_tokens_details={"audio_tokens": 30, "cached_tokens": 0},
            completion_tokens_details={"audio_tokens": 12},
        )
    )
    assert usage.audio_input_tokens == 30
    assert usage.audio_output_tokens == 12


def test_a_text_reply_reports_no_audio_rather_than_zero_audio():
    """Absent is not zero here either, and the difference is load-bearing.

    ``None`` against an audio-pricing entry means the split was not read and
    the call stays unpriced. ``0`` means the provider said there was no speech.
    A normaliser that flattened one into the other would decide that question
    for every call at once.
    """
    usage = extract_usage(_response(input_tokens=415, output_tokens=67))
    assert usage.audio_input_tokens is None
    assert usage.audio_output_tokens is None
    assert usage.has_audio is False


def test_a_reply_carrying_only_an_audio_count_is_not_read_as_no_usage():
    usage = extract_usage(
        _response(input_tokens_details=SimpleNamespace(audio_tokens=30))
    )
    assert usage.is_empty is False
    assert usage.audio_input_tokens == 30


# ── the ledger keeps it ──────────────────────────────────────────────────


@pytest.fixture
def ledger(tmp_path, text_only_table):
    with CostReceiptLedger(
        tmp_path / "cost.sqlite3", run_id="run-1", price_table=text_only_table
    ) as opened:
        yield opened


def _speech_call(ledger, task_id, *, retry_kind=RETRY_NONE, sequence=0):
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage=STAGE_PERCEPTION,
        retry_kind=retry_kind,
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=STAGE_PERCEPTION,
        retry_kind=retry_kind,
        provider="azure",
        requested_model="a-speech-model",
    )
    return call_id


SPOKEN = CallUsage(
    input_tokens=415,
    cached_input_tokens=0,
    output_tokens=67,
    reasoning_tokens=0,
    audio_input_tokens=30,
    audio_output_tokens=0,
)


def test_the_ledger_records_which_part_of_the_call_was_speech(ledger):
    """The gap in the 176 rows already committed, closed for the next run.

    Those rows record an input count and no indication that any of it was
    audio, because the split was dropped at the normaliser before the ledger
    ever saw it. Nothing can reconstruct it from them afterwards.
    """
    ledger.settle(
        _speech_call(ledger, "task-1"), usage=SPOKEN, resolved_model="a-speech-model"
    )
    row = ledger.calls_for("task-1")[0]
    assert row["audio_input_tokens"] == 30
    assert row["audio_output_tokens"] == 0
    assert row["input_tokens"] == 415
    assert row["model_cost_usd"] is None
    assert row["missing_reasons"] == [REASON_PRICE_MISSING]


def test_a_speech_call_holds_its_receipt_partial(ledger):
    ledger.settle(
        _speech_call(ledger, "task-1"), usage=SPOKEN, resolved_model="a-speech-model"
    )
    receipt = ledger.receipt_for("task-1", BUCKET_GRADING)
    assert receipt.status == STATUS_PARTIAL
    assert receipt.estimated_cost_usd is None
    assert REASON_PRICE_MISSING in receipt.missing_reasons


def test_a_speech_call_stays_out_of_the_problem_solving_ledger(ledger):
    """Reading a deliverable aloud is part of marking it, not part of making it.

    Perception is grading cost. An unpriceable speech call must therefore hold
    the grading receipt partial and leave the problem-solving receipt alone —
    the two are never added together, so a doubt in one is not a doubt in the
    other.
    """
    ledger.settle(
        _speech_call(ledger, "task-1"), usage=SPOKEN, resolved_model="a-speech-model"
    )
    assert ledger.receipt_for("task-1", BUCKET_GRADING).model_calls == 1
    solving = ledger.receipt_for("task-1", BUCKET_PROBLEM_SOLVING)
    assert solving.model_calls == 0
    assert solving.missing_reasons == ()


def test_the_published_receipt_still_reports_exactly_four_token_counts(ledger):
    """The ledger gained columns; the published contract did not gain keys.

    ``cost-receipt-v1``'s usage block is closed — grade.schema.json declares it
    ``additionalProperties: false`` — so a receipt that grew two keys would
    stop validating everywhere it is already published. The split lives in the
    ledger, which is the audit trail, and reaches a reader through it.
    """
    ledger.settle(
        _speech_call(ledger, "task-1"), usage=SPOKEN, resolved_model="a-speech-model"
    )
    assert set(ledger.receipt_for("task-1", BUCKET_GRADING).usage) == {
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
    }


def test_every_retry_of_a_speech_call_keeps_its_own_split(ledger):
    """Retries are separate calls that were separately billed.

    A first attempt and its infrastructure retry are two rows with two audio
    counts, and the receipt carries both — not the last one, and not one row
    holding their sum under a single identity.
    """
    ledger.settle(
        _speech_call(ledger, "task-1"), usage=SPOKEN, resolved_model="a-speech-model"
    )
    ledger.settle(
        _speech_call(
            ledger, "task-1", retry_kind=RETRY_INFRASTRUCTURE, sequence=1
        ),
        usage=CallUsage(
            input_tokens=512,
            cached_input_tokens=0,
            output_tokens=96,
            reasoning_tokens=0,
            audio_input_tokens=41,
            audio_output_tokens=0,
        ),
        resolved_model="a-speech-model",
    )
    rows = ledger.calls_for("task-1")
    assert sorted(row["audio_input_tokens"] for row in rows) == [30, 41]
    assert ledger.receipt_for("task-1", BUCKET_GRADING).model_calls == 2


def test_the_split_survives_export_and_reimport(ledger, tmp_path, text_only_table):
    """Shard merge and resume both go through this path.

    A ledger exported by one shard and imported by the merge must arrive with
    the same counts it left with, or the merged run's audit trail is thinner
    than the shards' were.
    """
    ledger.settle(
        _speech_call(ledger, "task-1"), usage=SPOKEN, resolved_model="a-speech-model"
    )
    exported = tmp_path / "shard.jsonl"
    ledger.export_jsonl(exported)
    line = json.loads(exported.read_text(encoding="utf-8").splitlines()[0])
    assert line["audio_input_tokens"] == 30
    assert line["audio_output_tokens"] == 0

    with CostReceiptLedger(
        tmp_path / "merged.sqlite3", run_id="run-2", price_table=text_only_table
    ) as merged:
        merged.import_jsonl(exported)
        row = merged.calls_for("task-1")[0]
        assert row["audio_input_tokens"] == 30
        assert row["audio_output_tokens"] == 0


def test_settling_the_same_speech_call_twice_is_a_no_op(ledger):
    call_id = _speech_call(ledger, "task-1")
    ledger.settle(call_id, usage=SPOKEN, resolved_model="a-speech-model")
    ledger.settle(call_id, usage=SPOKEN, resolved_model="a-speech-model")
    assert ledger.call_count() == 1
    assert ledger.calls_for("task-1")[0]["audio_input_tokens"] == 30


def test_settling_it_again_with_a_different_split_is_corruption(ledger):
    """A disagreement about how much of a call was speech is a disagreement.

    Every other token count already raises here. The audio counts are part of
    what the row asserts about the call, so they have to be part of what makes
    two settlements the same settlement.
    """
    call_id = _speech_call(ledger, "task-1")
    ledger.settle(call_id, usage=SPOKEN, resolved_model="a-speech-model")
    with pytest.raises(LedgerIntegrityError):
        ledger.settle(
            call_id,
            usage=CallUsage(
                input_tokens=415,
                cached_input_tokens=0,
                output_tokens=67,
                reasoning_tokens=0,
                audio_input_tokens=99,
                audio_output_tokens=0,
            ),
            resolved_model="a-speech-model",
        )


def test_a_ledger_that_gained_the_columns_by_migration_reads_them_back(
    tmp_path, text_only_table
):
    """The resumed-round path, where the columns arrive as TEXT.

    ``_migrate_columns`` can only add a column as ``TEXT``, so a ledger written
    before these columns existed stores ``'30'`` where a fresh one stores
    ``30``. Left uncoerced, re-settling the same call on a resumed ledger would
    compare a string against a number, find them different, and report
    corruption — which is the one thing that comparison must never invent.
    """
    path = tmp_path / "old.sqlite3"
    with CostReceiptLedger(
        path, run_id="run-1", price_table=text_only_table
    ) as opened:
        call_id = _speech_call(opened, "task-1")
        opened._connection.execute(
            "UPDATE cost_calls SET audio_input_tokens = '30', "
            "audio_output_tokens = '0', input_tokens = '415', "
            "cached_input_tokens = '0', output_tokens = '67', "
            "reasoning_tokens = '0', state = 'settled', "
            "resolved_model = 'a-speech-model', "
            "missing_reasons = ?, price_table_sha256 = ? WHERE call_id = ?",
            (
                json.dumps([REASON_PRICE_MISSING]),
                text_only_table.sha256,
                call_id,
            ),
        )
        opened._connection.commit()

        assert opened.calls_for("task-1")[0]["audio_input_tokens"] == 30
        # Re-settling with the same usage must be recognised as the same usage.
        opened.settle(call_id, usage=SPOKEN, resolved_model="a-speech-model")


def test_a_run_of_speech_calls_never_produces_a_total(ledger):
    """The whole point, at the level a reader sees.

    Sixty unpriced calls do not average into a number, do not fall back to
    zero, and do not become a total because most of the tokens were text. The
    run reports what it knows — the calls and the counts — and says the amount
    is not known.
    """
    for index in range(5):
        ledger.settle(
            _speech_call(ledger, "task-1", sequence=index),
            usage=SPOKEN,
            resolved_model="a-speech-model",
        )
    receipt = build_receipt(ledger.calls_for("task-1"))
    assert receipt.status == STATUS_PARTIAL
    assert receipt.estimated_cost_usd is None
    assert receipt.known_cost_usd == Decimal(0)
    assert receipt.model_calls == 5
    assert receipt.usage["input_tokens"] == 415 * 5


# ── the connection ───────────────────────────────────────────────────────
#
# Everything above tests the pricing rule in isolation. These test the path a
# real speech call actually travels, because the rule only protects anything if
# the counts reach it.
#
# The path was already built. `core/grader.py` wraps its client in
# `cost_recorder.meter(..., stage=STAGE_PERCEPTION)`, and that wrapper reserves
# a row, calls `extract_usage` on the reply, and settles. Every piece of that is
# in this session's own files. The reader in `core/perception/audio.py` needs no
# change to carry the split: it hands its client to the wrapper and the wrapper
# does the recording. Its own `read_reported_usage` tally is a separate running
# count for reporting and is not what feeds the ledger.


class _Bag:
    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)


class _FakeClient:
    """Answers on the surface the perception readers call."""

    def __init__(self, reply):
        self._reply = reply
        self.chat = _Bag(completions=_Bag(create=self._create))
        self.responses = _Bag(create=self._create)
        self.api_version = "2026-01-01"

    def _create(self, **kwargs):
        return self._reply


def _spoken_reply(*, prompt=415, completion=96, audio_in=30, audio_out=0):
    """A reply from a speech model, in the shape the provider sends one.

    The audio count arrives in the prompt-token *details*, one level under the
    total it is part of — which is the provider saying, in its own layout, that
    this is a share of the input rather than an addition to it.
    """
    usage = _Bag(prompt_tokens=prompt, completion_tokens=completion)
    usage.prompt_tokens_details = _Bag(cached_tokens=0, audio_tokens=audio_in)
    usage.completion_tokens_details = _Bag(
        reasoning_tokens=0, audio_tokens=audio_out
    )
    return _Bag(model="a-speech-model", usage=usage)


@pytest.fixture
def recorder(tmp_path, text_only_table):
    with CostReceiptLedger(
        tmp_path / "wired.sqlite3", run_id="run-1", price_table=text_only_table
    ) as opened:
        yield CostRecorder(opened)


def test_a_metered_speech_call_lands_in_the_ledger_with_its_split(recorder):
    """The split survives the whole trip, with no reader-side change.

    This is the test that says the plumbing is connected. A call goes out
    through the same wrapper the grader builds, and the row it leaves behind
    knows how much of that input was speech.
    """
    client = recorder.meter(_FakeClient(_spoken_reply()), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_PERCEPTION):
        client.chat.completions.create(model="a-speech-deployment", messages=[])

    row = recorder.ledger.calls_for("task-a")[0]
    assert row["stage"] == STAGE_PERCEPTION
    assert row["input_tokens"] == 415
    assert row["audio_input_tokens"] == 30
    assert row["audio_output_tokens"] == 0


def test_a_metered_speech_call_refuses_to_price_itself_from_text_rates(recorder):
    """And the refusal holds at the far end of the path, not just in the unit.

    The table this recorder holds is today's table: text rates, no audio rates.
    A tenth of that input was speech, so the row is unpriceable and says so.
    """
    client = recorder.meter(_FakeClient(_spoken_reply()), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_PERCEPTION):
        client.chat.completions.create(model="a-speech-deployment", messages=[])

    receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
    assert receipt.status == STATUS_PARTIAL
    assert receipt.estimated_cost_usd is None
    assert REASON_PRICE_MISSING in receipt.missing_reasons

    # …and the other half of the task is not implicated by it.
    assert recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING).model_calls == 0


def test_a_text_only_reply_through_the_same_wrapper_still_prices(recorder):
    """The guard is aimed at speech, not at everything that passes.

    A reply carrying no audio tokens goes through the identical wrapper, the
    identical table and the identical code, and comes out with a number. If
    this ever goes partial, the audio rule has become a blanket refusal.
    """
    reply = _Bag(
        model="a-speech-model",
        usage=_Bag(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            prompt_tokens_details=_Bag(cached_tokens=0, audio_tokens=0),
            completion_tokens_details=_Bag(reasoning_tokens=0, audio_tokens=0),
        ),
    )
    client = recorder.meter(_FakeClient(reply), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_PERCEPTION):
        client.chat.completions.create(model="a-deployment", messages=[])

    receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
    assert receipt.status == STATUS_COMPLETE
    assert receipt.estimated_cost_usd == Decimal("2.50") + Decimal("15.00")


# ── the rows that are already committed ──────────────────────────────────
#
# Everything above runs on rows this file wrote. These read the ones that were
# written before any of it existed, because a schema change that only works on
# new rows silently orphans the old ones — and the old ones here are the whole
# reason the work was done.


def _committed_audio_ledgers():
    root = Path(__file__).resolve().parents[2]
    for path in sorted(root.glob("data/grades/**/*.cost_ledger.jsonl")):
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if any(
            "audio" in str(row.get("resolved_model") or "").lower() for row in rows
        ):
            yield path, rows


def test_the_committed_speech_rows_predate_the_split_and_say_so():
    """176 rows, no split, no price. That is the state being fixed, on record.

    They were written before the counts were captured, so the breakdown is not
    in them and cannot be put in them — a share recovered by multiplying by
    today's ratio would be a number this repository made up about calls it
    already paid for. They stay as they are: usage recorded, price refused.
    """
    audio_rows = [
        row
        for _, rows in _committed_audio_ledgers()
        for row in rows
        if "audio" in str(row.get("resolved_model") or "").lower()
    ]
    assert audio_rows, "no committed speech rows found to check"

    for row in audio_rows:
        assert "audio_input_tokens" not in row
        assert "audio_output_tokens" not in row
        assert row.get("model_cost_usd") is None
        if row.get("state") == "settled":
            reasons = row["missing_reasons"]
            if isinstance(reasons, str):
                reasons = json.loads(reasons)
            assert REASON_PRICE_MISSING in reasons


def test_a_committed_ledger_still_imports_after_the_columns_were_added(
    tmp_path, text_only_table
):
    """Old bytes through new code: absent stays absent, and does not become 0.

    Resume and shard merge both re-import ledgers written by earlier rounds. A
    row with no audio keys has to come back with ``None`` in those columns —
    ``0`` there would be this code asserting that no speech was in a call it
    has no information about, which is the exact substitution the rest of this
    file exists to prevent.
    """
    path, rows = next(_committed_audio_ledgers())
    with CostReceiptLedger(
        tmp_path / "reimported.sqlite3", run_id="run-x", price_table=text_only_table
    ) as ledger:
        ledger.import_jsonl(path)
        seen = 0
        for row in rows:
            if "audio" not in str(row.get("resolved_model") or "").lower():
                continue
            stored = ledger.calls_for(row["task_id"])
            match = [r for r in stored if r["call_id"] == row["call_id"]]
            assert match, row["call_id"]
            assert match[0]["audio_input_tokens"] is None
            assert match[0]["audio_output_tokens"] is None
            assert match[0]["input_tokens"] == row["input_tokens"]
            seen += 1
    assert seen, f"{path} named a speech model but held no rows for it"
