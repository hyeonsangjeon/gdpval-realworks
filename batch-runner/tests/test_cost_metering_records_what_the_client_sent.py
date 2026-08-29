"""The wrapper: what the client actually sent is what gets recorded.

Instrumentation that reads its numbers from anywhere but the provider's own
reply is guessing. These tests drive the wrapper with stand-in clients of each
API shape the pipeline meets, and check that the row written afterwards says
what the reply said — including when the reply says nothing.

No provider is contacted. Every client here is local and returns a fixed
object.
"""

import json
from decimal import Decimal

import pytest

from core.cost_metering import (
    Attribution,
    CostRecorder,
    extract_usage,
    read_reported_usage,
    resolved_model_of,
)
from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    REASON_CALL_REACHABILITY_UNKNOWN,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    RETRY_SEMANTIC,
    STAGE_GENERATION,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    STAGE_SELF_QA,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    CostReceiptLedger,
    load_receipt_price_table,
    price_call,
)

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
def recorder(tmp_path, price_table):
    with CostReceiptLedger(
        tmp_path / "cost.sqlite3", run_id="run-1", price_table=price_table
    ) as ledger:
        yield CostRecorder(ledger)


# ── stand-in clients ─────────────────────────────────────────────────────


class _Bag:
    """An object whose attributes are whatever it was handed."""

    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)


def _chat_reply(prompt=100_000, completion=10_000, cached=None, reasoning=None):
    """The Chat Completions shape."""
    usage = _Bag(prompt_tokens=prompt, completion_tokens=completion)
    if cached is not None:
        usage.prompt_tokens_details = _Bag(cached_tokens=cached)
    if reasoning is not None:
        usage.completion_tokens_details = _Bag(reasoning_tokens=reasoning)
    return _Bag(model="test-model", usage=usage)


def _responses_reply(input_tokens=100_000, output_tokens=10_000, cached=None):
    """The Responses shape."""
    usage = _Bag(input_tokens=input_tokens, output_tokens=output_tokens)
    if cached is not None:
        usage.input_tokens_details = _Bag(cached_tokens=cached)
    return _Bag(model="test-model", usage=usage)


class FakeClient:
    """Answers on all three surfaces the pipeline uses."""

    def __init__(self, reply=None, *, raises=None):
        self._reply = reply if reply is not None else _chat_reply()
        self._raises = raises
        self.seen: list[dict] = []
        self.chat = _Bag(completions=_Bag(create=self._create))
        self.responses = _Bag(create=self._create)
        self.api_version = "2026-01-01"

    def _create(self, **kwargs):
        self.seen.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return self._reply

    def chat_complete(self, **kwargs):
        return self._create(**kwargs)

    def close(self):
        self.closed = True


# ── the three surfaces ───────────────────────────────────────────────────


def test_a_chat_completion_writes_the_row_the_reply_supports(recorder):
    client = recorder.meter(FakeClient(), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(model="a-deployment", messages=[])

    receipt = recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_COMPLETE
    assert receipt.model_calls == 1
    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_a_responses_call_writes_the_same_kind_of_row(recorder):
    client = recorder.meter(
        FakeClient(reply=_responses_reply()), provider="azure"
    )

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.responses.create(model="a-deployment", input="hello")

    receipt = recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_the_normalised_entry_point_is_metered_too(recorder):
    """Non-OpenAI providers reach the model through ``chat_complete``."""
    client = recorder.meter(FakeClient(), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat_complete(model="a-deployment", messages=[])

    assert recorder.receipt_for(
        "task-a", BUCKET_PROBLEM_SOLVING
    ).model_calls == 1


def test_the_wrapper_passes_the_request_through_unchanged(recorder):
    """Metering must not alter what the provider is asked."""
    inner = FakeClient()
    client = recorder.meter(inner, provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(
            model="a-deployment", messages=[{"role": "user"}], temperature=0.2
        )

    assert inner.seen == [
        {
            "model": "a-deployment",
            "messages": [{"role": "user"}],
            "temperature": 0.2,
        }
    ]


def test_everything_else_on_the_client_still_works(recorder):
    """The wrapper has to stand in wherever the real client stood."""
    inner = FakeClient()
    client = recorder.meter(inner, provider="azure")

    client.close()

    assert client.api_version == "2026-01-01"
    assert client.inner is inner
    assert client.provider == "azure"
    assert inner.closed is True


# ── attribution ──────────────────────────────────────────────────────────


def test_a_call_outside_any_task_scope_is_not_filed_under_one(recorder):
    """Report writing belongs to neither pipeline; it gets no home."""
    client = recorder.meter(FakeClient(), provider="azure")

    reply = client.chat.completions.create(model="a-deployment", messages=[])

    assert reply is not None
    assert recorder.ledger.task_ids() == []


def test_calls_land_in_the_stage_that_was_in_scope(recorder):
    client = recorder.meter(FakeClient(), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(model="a-deployment", messages=[])
    with recorder.attributed(
        task_id="task-a", stage=STAGE_SELF_QA, retry_kind=RETRY_SEMANTIC
    ):
        client.chat.completions.create(model="a-deployment", messages=[])

    receipt = recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert {component.stage for component in receipt.components} == {
        STAGE_GENERATION,
        STAGE_SELF_QA,
    }
    assert receipt.estimated_cost_usd == Decimal("2.40")


def test_a_nested_scope_returns_to_the_one_around_it(recorder):
    """A perception read during marking is its own component, not a takeover."""
    client = recorder.meter(FakeClient(), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
        client.chat.completions.create(model="a-deployment", messages=[])
        with recorder.attributed(task_id="task-a", stage=STAGE_PERCEPTION):
            client.chat.completions.create(model="a-deployment", messages=[])
        client.chat.completions.create(model="a-deployment", messages=[])

    receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
    by_stage = {
        component.stage: component.model_calls for component in receipt.components
    }

    assert by_stage == {STAGE_GRADING: 2, STAGE_PERCEPTION: 1}
    assert recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING).model_calls == 0


def test_two_calls_in_one_scope_are_two_rows_not_one(recorder):
    client = recorder.meter(FakeClient(), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(model="a-deployment", messages=[])
        client.chat.completions.create(model="a-deployment", messages=[])

    rows = recorder.ledger.calls_for("task-a")

    assert len({row["call_id"] for row in rows}) == 2


def test_a_stage_nobody_defined_is_refused_at_the_boundary(recorder):
    with pytest.raises(ValueError):
        Attribution(task_id="task-a", stage="invoicing")


def test_a_call_that_belongs_to_no_task_is_refused(recorder):
    with pytest.raises(ValueError):
        Attribution(task_id="", stage=STAGE_GENERATION)


# ── failure ──────────────────────────────────────────────────────────────


def test_a_call_that_raised_leaves_the_receipt_open(recorder):
    """A timeout may have been served and billed. It is not written off."""
    client = recorder.meter(
        FakeClient(raises=TimeoutError("no reply")), provider="azure"
    )

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        with pytest.raises(TimeoutError):
            client.chat.completions.create(model="a-deployment", messages=[])

    receipt = recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt.missing_reasons
    assert receipt.estimated_cost_usd is None
    assert receipt.model_calls == 1


def test_a_failure_known_to_predate_the_request_is_written_off(recorder):
    """Only a caller that knows nothing left the process may say so."""
    client = recorder.meter(
        FakeClient(raises=ValueError("prompt too long to build")),
        provider="azure",
    )

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        with pytest.raises(ValueError):
            client.chat.completions.create(model="a-deployment", messages=[])
        recorder.abandon_call(client.last_call_id, note="request never built")

    receipt = recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_COMPLETE
    assert receipt.model_calls == 0
    assert receipt.estimated_cost_usd == Decimal(0)


# ── reading the reply ────────────────────────────────────────────────────


def test_usage_is_read_from_the_chat_shape():
    usage = extract_usage(
        _chat_reply(prompt=500, completion=60, cached=100, reasoning=40)
    )

    assert usage.input_tokens == 500
    assert usage.output_tokens == 60
    assert usage.cached_input_tokens == 100
    assert usage.reasoning_tokens == 40


def test_usage_is_read_from_the_responses_shape():
    usage = extract_usage(_responses_reply(500, 60, cached=100))

    assert usage.input_tokens == 500
    assert usage.output_tokens == 60
    assert usage.cached_input_tokens == 100


def test_usage_is_read_from_a_plain_dictionary():
    """Some providers are normalised into dicts before they get here."""
    usage = extract_usage(
        {
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 60,
                "cached_tokens": 100,
            }
        }
    )

    assert usage.input_tokens == 500
    assert usage.cached_input_tokens == 100


def test_a_reply_with_no_usage_reports_nothing_rather_than_zero():
    usage = extract_usage(_Bag(model="test-model"))

    assert usage.is_empty
    assert usage.input_tokens is None
    assert usage.output_tokens is None


def test_a_field_the_provider_omitted_stays_absent():
    """Absent is not zero, and the difference decides the receipt's status."""
    usage = extract_usage(_chat_reply(prompt=500, completion=60))

    assert usage.input_tokens == 500
    assert usage.cached_input_tokens is None
    assert usage.reasoning_tokens is None


def test_a_flag_arriving_where_a_count_belongs_is_not_read_as_one():
    """``True`` is an ``int`` in Python. It is not one token."""
    usage = extract_usage({"usage": {"prompt_tokens": True, "completion_tokens": 5}})

    assert usage.input_tokens is None
    assert usage.output_tokens == 5


def test_a_negative_count_is_not_believed():
    usage = extract_usage({"usage": {"prompt_tokens": -5, "completion_tokens": 5}})

    assert usage.input_tokens is None


# ── what a running tally is allowed to publish ───────────────────────────


def _responses_bag(**usage_fields):
    """A Responses-shaped reply whose usage block is exactly what was asked for."""
    return _Bag(model="test-model", usage=_Bag(**usage_fields))


def test_a_reply_without_a_cache_breakdown_is_still_a_complete_count():
    """The bug this helper exists to fix.

    ``gpt-audio-1.5`` answers without ``input_tokens_details``. Both counts
    that decide the bill are present, so the tally is publishable — the reply
    simply says nothing was served from cache. Reading that as *unknown usage*
    is what failed a whole 17-task shard on rc=6 after it had already been
    paid for.
    """
    reported = read_reported_usage(
        _responses_bag(input_tokens=900, output_tokens=120)
    )

    assert reported.usage_complete is True
    assert reported.input_tokens == 900
    assert reported.output_tokens == 120
    assert reported.cached_tokens == 0


def test_a_breakdown_that_arrived_empty_is_read_the_same_way():
    """An older SDK hands back the details object with nothing in it."""
    reported = read_reported_usage(
        _responses_bag(
            input_tokens=900, output_tokens=120, input_tokens_details=_Bag()
        )
    )

    assert reported.usage_complete is True
    assert reported.cached_tokens == 0


def test_a_breakdown_that_did_arrive_is_counted():
    reported = read_reported_usage(
        _responses_bag(
            input_tokens=900,
            output_tokens=120,
            input_tokens_details=_Bag(cached_tokens=300),
        )
    )

    assert reported.usage_complete is True
    assert reported.cached_tokens == 300


@pytest.mark.parametrize(
    "usage_fields",
    [
        {"output_tokens": 120},                    # no input count
        {"input_tokens": 900},                     # no output count
        {"input_tokens": None, "output_tokens": 120},
        {"input_tokens": True, "output_tokens": 120},   # a flag, not a count
        {"input_tokens": -5, "output_tokens": 120},
    ],
    ids=["no-input", "no-output", "input-null", "input-flag", "input-negative"],
)
def test_a_missing_or_unbelievable_count_is_not_publishable(usage_fields):
    assert read_reported_usage(_responses_bag(**usage_fields)).usage_complete is False


def test_a_reply_with_no_usage_block_at_all_is_not_publishable():
    assert read_reported_usage(_Bag(model="test-model")).usage_complete is False
    assert read_reported_usage(_Bag(model="test-model", usage=None)).usage_complete is (
        False
    )


def test_more_served_from_cache_than_was_sent_is_a_contradiction():
    """Cached input is a part of the input, so it cannot exceed it.

    One of the two numbers is wrong and there is no way to tell which, so
    neither is trusted. ``price_call`` makes the same check before it will put
    a number on a call.
    """
    reported = read_reported_usage(
        _responses_bag(
            input_tokens=10,
            output_tokens=120,
            input_tokens_details=_Bag(cached_tokens=99),
        )
    )

    assert reported.usage_complete is False


def test_the_helper_agrees_with_the_ledger_about_what_is_publishable(price_table):
    """The anti-drift check, and the reason the rule lives in one place.

    Three call sites keep running token totals, and each used to decide for
    itself when a total was still worth publishing. All three invented a rule
    stricter than the one the receipt ledger actually applies, which is how a
    missing cache breakdown came to mean *unknown usage* in the judge while
    meaning *nothing was cached* in the bill.

    So the rule is not merely restated here — it is checked against
    ``price_call``, the function that decides whether a call can be charged.
    A shape the ledger is willing to price must be a shape the tally is
    willing to publish, and the reverse. If either side moves, this fails.
    """
    price = price_table.lookup("azure", "test-model")
    assert price is not None

    shapes = [
        _responses_bag(input_tokens=900, output_tokens=120),
        _responses_bag(
            input_tokens=900,
            output_tokens=120,
            input_tokens_details=_Bag(cached_tokens=300),
        ),
        _responses_bag(
            input_tokens=900, output_tokens=120, input_tokens_details=_Bag()
        ),
        _responses_bag(input_tokens=900, output_tokens=0),
        _responses_bag(output_tokens=120),
        _responses_bag(input_tokens=900),
        _responses_bag(
            input_tokens=10,
            output_tokens=120,
            input_tokens_details=_Bag(cached_tokens=99),
        ),
        _Bag(model="test-model"),
        _chat_reply(prompt=500, completion=60),
    ]

    for shape in shapes:
        priced = price_call(price, extract_usage(shape))
        ledger_is_happy = not {
            REASON_USAGE_ABSENT,
            REASON_USAGE_PARTIAL,
        } & set(priced.missing_reasons)

        assert read_reported_usage(shape).usage_complete is ledger_is_happy, (
            f"the tally and the ledger disagree about {vars(shape)}: "
            f"reasons={priced.missing_reasons}"
        )


def test_the_reply_names_the_model_that_is_priced():
    assert resolved_model_of(_Bag(model="what-answered"), "what-was-asked") == (
        "what-answered"
    )


def test_a_reply_that_names_no_model_falls_back_to_the_request():
    assert resolved_model_of(_Bag(), "what-was-asked") == "what-was-asked"
    assert resolved_model_of(_Bag(model="   "), "what-was-asked") == (
        "what-was-asked"
    )


def test_the_deployment_alias_is_kept_beside_the_model_that_answered(recorder):
    client = recorder.meter(FakeClient(), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(model="a-deployment", messages=[])

    row = recorder.ledger.calls_for("task-a")[0]

    assert row["requested_model"] == "a-deployment"
    assert row["resolved_model"] == "test-model"


# ── paths that own their transport ───────────────────────────────────────


def test_a_call_made_elsewhere_can_still_be_filed(recorder):
    """For the paths that cannot be wrapped, but do hold a reply."""
    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        call_id = recorder.record_call(
            provider="azure",
            requested_model="a-deployment",
            response=_chat_reply(),
        )

    receipt = recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert call_id is not None
    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_filing_a_call_with_no_task_in_scope_files_nothing(recorder):
    call_id = recorder.record_call(
        provider="azure", requested_model="a-deployment", response=_chat_reply()
    )

    assert call_id is None
    assert recorder.ledger.task_ids() == []


def test_a_default_model_covers_a_request_that_names_none(recorder):
    """Some call sites set the deployment on the client, not the request."""
    client = recorder.meter(
        FakeClient(), provider="azure", model="a-default-deployment"
    )

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(messages=[])

    assert recorder.ledger.calls_for("task-a")[0]["requested_model"] == (
        "a-default-deployment"
    )
