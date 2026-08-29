"""A receipt has to name who was called, or it cannot be priced.

Three failures found in real Stage 3 output, all of them the same failure seen
from three distances:

1. A row recorded ``requested_model`` and nothing else. On Azure that string is
   a deployment alias; on a direct provider it is a model name; and nothing in
   the string says which. So the price table could not be looked up without
   guessing, and a guess in a cost report is worse than a gap.

2. ``perception`` arrived as one line no matter how many models had run under
   it. Grading a deliverable containing a picture and a recording calls a
   vision model and an audio model, and their tokens were summed into a single
   row — a row belonging to two price rates, which no table can price and no
   reader can take apart afterwards.

3. The experiment-level summary carried no component lines at all. The
   per-task breakdown existed; the rollup silently dropped it.

The tests below fix all three as behaviour. No provider is contacted: every
client here is local and returns a fixed object.
"""

import json
from decimal import Decimal

import pytest

from core.cost_metering import (
    CostRecorder,
    api_version_of,
    deployment_of,
)
from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    RETRY_NONE,
    RETRY_SEMANTIC,
    STAGE_GENERATION,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    CallUsage,
    CostReceiptLedger,
    ReceiptComponent,
    load_receipt_price_table,
    make_call_id,
    summarise_receipts,
)

PRICE_TABLE = {
    "cost_receipt_schema_version": "cost-receipt-price-table-v1",
    "providers": {
        name: {
            "input_usd_per_million": rate,
            "cached_input_usd_per_million": "1",
            "output_usd_per_million": "20",
            "reasoning_billed_as": "output",
            "source": "fixture",
            "last_reviewed": "2026-08-28",
            "currency": "USD",
            "unit": "per 1,000,000 tokens",
        }
        # Two rates on purpose: a line that merged these two models would land
        # on a number that is neither, and the test could not tell.
        for name, rate in (("azure:sees-things", "10"), ("azure:hears-things", "40"))
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
    """An object whose attributes are whatever it was handed."""

    def __init__(self, **fields):
        for name, value in fields.items():
            setattr(self, name, value)


def _reply(model, *, prompt=100_000, completion=10_000):
    return _Bag(
        model=model,
        usage=_Bag(prompt_tokens=prompt, completion_tokens=completion),
    )


class FakeClient:
    """A client that answers, and optionally looks like an Azure one.

    ``_azure_endpoint`` is set to a sentinel rather than a URL and is only ever
    tested for presence — the value is never read out, recorded, or asserted
    on, here or in the code under test.
    """

    def __init__(self, reply, *, azure=False, deployment=None, api_version=None):
        self._reply = reply
        self.seen: list[dict] = []
        self.chat = _Bag(completions=_Bag(create=self._create))
        if azure:
            self._azure_endpoint = object()
            self._azure_deployment = deployment
            self._api_version = api_version

    def _create(self, **kwargs):
        self.seen.append(kwargs)
        return self._reply


class HostileClient:
    """A client that raises on any attribute it does not recognise.

    Not a hypothetical. Step 2's typed Azure route wraps its client in a proxy
    that converts every failed lookup into a ``RuntimeError``, so that provider
    exceptions cannot leak details into a log. That defeats ``getattr``'s
    default, and asking such a client an innocent question used to kill the
    call it was asked about.
    """

    def __init__(self, reply):
        self._reply = reply
        self.chat = _Bag(completions=_Bag(create=self._create))

    def _create(self, **kwargs):
        return self._reply

    def __getattr__(self, name):
        raise RuntimeError(f"typed provider error ({name})")


def _usage(input_tokens=100_000, output_tokens=10_000):
    return CallUsage(
        input_tokens=input_tokens,
        cached_input_tokens=0,
        output_tokens=output_tokens,
        reasoning_tokens=0,
    )


def _spend(ledger, task_id, *, stage, model, sequence=0, **identity):
    """One settled call, written straight to the ledger."""
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage=stage,
        retry_kind=RETRY_NONE,
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=stage,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model=identity.pop("requested_model", model),
        **identity,
    )
    ledger.settle(call_id, usage=_usage(), resolved_model=model)
    return call_id


def _line(receipt, resolved_model):
    found = [
        component
        for component in receipt.components
        if component.resolved_model == resolved_model
    ]
    assert len(found) == 1, [component.resolved_model for component in receipt.components]
    return found[0]


# ── 1. every call records who it went to ─────────────────────────────────


def test_a_metered_call_records_the_route_it_took(recorder, ledger, tmp_path):
    client = recorder.meter(
        FakeClient(
            _reply("sees-things"), azure=True, api_version="2026-01-01"
        ),
        provider="azure",
    )

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(model="gold-judge", messages=[])

    export = tmp_path / "ledger.jsonl"
    ledger.export_jsonl(export)
    (row,) = [
        json.loads(line)
        for line in export.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("record_type", "call") == "call"
    ]

    assert row["provider"] == "azure"
    assert row["requested_model"] == "gold-judge"
    assert row["resolved_model"] == "sees-things"
    assert row["api_version"] == "2026-01-01"
    # The SDK builds …/openai/deployments/{model} when the client pins no
    # deployment of its own, so on Azure the requested name *is* the route.
    assert row["deployment"] == "gold-judge"


def test_a_client_level_deployment_wins_over_the_request(recorder, ledger, tmp_path):
    client = recorder.meter(
        FakeClient(_reply("sees-things"), azure=True, deployment="pinned-route"),
        provider="azure",
    )

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(model="ignored-by-the-sdk", messages=[])

    export = tmp_path / "ledger.jsonl"
    ledger.export_jsonl(export)
    (row,) = [
        json.loads(line)
        for line in export.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("record_type", "call") == "call"
    ]
    # When the client pins one, the SDK ignores the per-request name for
    # routing. Recording the request's name as the deployment would be a lie
    # about where the tokens were billed.
    assert row["deployment"] == "pinned-route"
    assert row["requested_model"] == "ignored-by-the-sdk"


def test_a_provider_with_no_deployments_says_so_rather_than_guessing():
    plain = FakeClient(_reply("sees-things"))
    # Not "": absent means the concept does not apply here, and an empty
    # string would read as a deployment whose name nobody wrote down.
    assert deployment_of(plain, "some-model") is None
    assert api_version_of(plain) is None


def test_asking_a_hostile_client_does_not_break_the_call(recorder, ledger, tmp_path):
    client = recorder.meter(HostileClient(_reply("sees-things")), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GENERATION):
        client.chat.completions.create(model="gold-judge", messages=[])

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)
    # The call went through and was priced. Metering watches; it does not get
    # a vote on whether the work happens.
    assert receipt.status == STATUS_COMPLETE
    assert receipt.model_calls == 1
    line = _line(receipt, "sees-things")
    # And what could not be observed is recorded as unobserved.
    assert line.deployment is None
    assert line.api_version is None


# ── 2. two models under one stage are two lines ──────────────────────────


def test_two_models_read_under_one_stage_stay_two_lines(ledger):
    _spend(ledger, "task-a", stage=STAGE_PERCEPTION, model="sees-things")
    _spend(ledger, "task-a", stage=STAGE_PERCEPTION, model="hears-things", sequence=1)

    receipt = ledger.receipt_for("task-a", BUCKET_GRADING)

    assert len(receipt.components) == 2
    # 100_000 × $10/M + 10_000 × $20/M, and the same input at $40/M.
    assert _line(receipt, "sees-things").known_cost_usd == Decimal("1.20")
    assert _line(receipt, "hears-things").known_cost_usd == Decimal("4.20")
    # Summed, the two lines still add up to the receipt. Splitting the
    # breakdown does not change the bill, only whether it can be read.
    assert receipt.known_cost_usd == Decimal("5.40")


def test_one_model_called_twice_at_one_stage_is_still_one_line(ledger):
    _spend(ledger, "task-a", stage=STAGE_PERCEPTION, model="sees-things")
    _spend(ledger, "task-a", stage=STAGE_PERCEPTION, model="sees-things", sequence=1)

    receipt = ledger.receipt_for("task-a", BUCKET_GRADING)

    # Identity is what splits a line, not the number of calls. Two calls that
    # agree on all of it are one line reporting two calls — otherwise every
    # judged rubric item would get its own row.
    assert len(receipt.components) == 1
    assert receipt.components[0].model_calls == 2


def test_a_retry_and_a_first_attempt_remain_separable(ledger):
    _spend(ledger, "task-a", stage=STAGE_GENERATION, model="sees-things")
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id="task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_SEMANTIC,
        attempt_index=1,
        sequence=0,
    )
    ledger.reserve(
        call_id=call_id,
        task_id="task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_SEMANTIC,
        provider="azure",
        requested_model="sees-things",
    )
    ledger.settle(call_id, usage=_usage(), resolved_model="sees-things")

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    # Same model, same stage, different retry kind. "What did retrying cost"
    # stays answerable after identity became part of the key.
    assert sorted(line.retry_kind for line in receipt.components) == [
        RETRY_NONE,
        RETRY_SEMANTIC,
    ]


# ── 3. the summary keeps its lines ───────────────────────────────────────


def test_a_run_summary_carries_the_lines_its_tasks_carried(ledger):
    _spend(ledger, "task-a", stage=STAGE_PERCEPTION, model="sees-things")
    _spend(ledger, "task-b", stage=STAGE_PERCEPTION, model="sees-things")
    _spend(ledger, "task-b", stage=STAGE_PERCEPTION, model="hears-things", sequence=1)

    summary = summarise_receipts(
        [
            ledger.receipt_for("task-a", BUCKET_GRADING),
            ledger.receipt_for("task-b", BUCKET_GRADING),
        ]
    )

    # The rollup used to return with no lines at all, so an experiment-level
    # report could say what it cost but never what it was spent on.
    assert summary.components, "the summary dropped its breakdown"
    assert _line(summary, "sees-things").model_calls == 2
    assert _line(summary, "sees-things").known_cost_usd == Decimal("2.40")
    assert _line(summary, "hears-things").model_calls == 1


def test_a_summary_line_that_hides_an_unpriced_task_is_partial(ledger):
    _spend(ledger, "task-a", stage=STAGE_GRADING, model="sees-things")
    unpriced = make_call_id(
        run_id=ledger.run_id,
        task_id="task-b",
        stage=STAGE_GRADING,
        retry_kind=RETRY_NONE,
        attempt_index=0,
        sequence=0,
    )
    ledger.reserve(
        call_id=unpriced,
        task_id="task-b",
        stage=STAGE_GRADING,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model="sees-things",
    )
    # Settled, but the provider reported no usage, so nothing can be priced.
    ledger.settle(unpriced, usage=CallUsage(), resolved_model="sees-things")

    summary = summarise_receipts(
        [
            ledger.receipt_for("task-a", BUCKET_GRADING),
            ledger.receipt_for("task-b", BUCKET_GRADING),
        ]
    )

    line = _line(summary, "sees-things")
    # One priced task must not be allowed to present itself as the whole line.
    assert line.status == STATUS_PARTIAL
    assert line.known_cost_usd == Decimal("1.20")
    assert line.missing_reasons


# ── round-tripping and resume ────────────────────────────────────────────


def test_a_published_line_round_trips_its_identity():
    line = ReceiptComponent(
        stage=STAGE_PERCEPTION,
        retry_kind=RETRY_NONE,
        status=STATUS_COMPLETE,
        model_calls=1,
        known_cost_usd=Decimal("1.20"),
        usage={"input_tokens": 100_000},
        provider="azure",
        deployment="gold-judge",
        requested_model="gold-judge",
        resolved_model="sees-things",
        api_version="2026-01-01",
    )
    assert ReceiptComponent.from_dict(line.as_dict()) == line


def test_an_older_export_does_not_blank_out_a_recorded_route(
    tmp_path, price_table
):
    call_id = make_call_id(
        run_id="run-1",
        task_id="task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        attempt_index=0,
        sequence=0,
    )
    # An export from a build that predates these columns: it knows how the call
    # ended, and nothing about where it went.
    export = tmp_path / "old.jsonl"
    export.write_text(
        json.dumps(
            {
                "record_type": "call",
                "call_id": call_id,
                "run_id": "run-1",
                "task_id": "task-a",
                "stage": STAGE_GENERATION,
                "retry_kind": RETRY_NONE,
                "provider": "azure",
                "requested_model": "gold-judge",
                "resolved_model": "sees-things",
                "state": "settled",
                "input_tokens": 100_000,
                "cached_input_tokens": 0,
                "output_tokens": 10_000,
                "reasoning_tokens": 0,
                "model_cost_usd": "1.20",
                "missing_reasons": [],
                "price_table_sha256": price_table.sha256,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with CostReceiptLedger(
        tmp_path / "cost.sqlite3", run_id="run-1", price_table=price_table
    ) as ledger:
        # This process watched the request leave and recorded the route.
        ledger.reserve(
            call_id=call_id,
            task_id="task-a",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_NONE,
            provider="azure",
            requested_model="gold-judge",
            deployment="gold-judge",
            api_version="2026-01-01",
        )
        ledger.import_jsonl(export)
        receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    line = _line(receipt, "sees-things")
    # The import resolved how the call ended — that is what it knew more about.
    assert receipt.status == STATUS_COMPLETE
    # It did not overwrite what it knew nothing about. A blank must never win
    # against a recorded fact just because it arrived later.
    assert line.deployment == "gold-judge"
    assert line.api_version == "2026-01-01"


def test_identity_survives_a_resume(tmp_path, price_table):
    export = tmp_path / "round1.jsonl"
    with CostReceiptLedger(
        tmp_path / "round1.sqlite3", run_id="run-1", price_table=price_table
    ) as first:
        _spend(
            first,
            "task-a",
            stage=STAGE_GENERATION,
            model="sees-things",
            deployment="gold-judge",
            api_version="2026-01-01",
        )
        first.export_jsonl(export)

    with CostReceiptLedger(
        tmp_path / "round2.sqlite3", run_id="run-1", price_table=price_table
    ) as second:
        assert second.import_jsonl(export) == 1
        receipt = second.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    line = _line(receipt, "sees-things")
    assert (line.provider, line.deployment, line.api_version) == (
        "azure",
        "gold-judge",
        "2026-01-01",
    )
