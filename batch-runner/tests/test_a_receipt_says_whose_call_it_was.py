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

A fourth turned up afterwards, in the first paid grading receipt: all 84
settled calls recorded no deployment and no API version whatsoever. Nothing was
wrong with the meter. The grader reaches Azure over the undated ``/openai/v1/``
route, which travels on the *plain* ``OpenAI`` class, and that class has
nowhere to keep either value — so asked, it truthfully answered that it did not
know. The route knows, and now says so at the point of construction.

The tests below fix all four as behaviour. No provider is contacted: every
client here is local and returns a fixed object.
"""

import json
from decimal import Decimal

import pytest

from core.cost_metering import (
    ROUTE_IDENTITY_ATTRIBUTE,
    CostRecorder,
    RouteCallIdentity,
    api_version_of,
    deployment_of,
    route_identity_of,
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


# ── 1b. a route the client cannot describe describes itself ──────────────


def _declaring(reply, *, names_deployments=True, declared_api_version="v1", **kwargs):
    """A client whose builder wrote down how the route it opened behaves.

    ``declared_api_version`` is what the *route* says. Any ``api_version``
    passed through to :class:`FakeClient` is what the *client* says, and the
    two are deliberately nameable apart so a test can set both and assert which
    one wins.
    """
    client = FakeClient(reply, **kwargs)
    setattr(
        client,
        ROUTE_IDENTITY_ATTRIBUTE,
        RouteCallIdentity(
            model_argument_names_deployment=names_deployments,
            api_version=declared_api_version,
        ),
    )
    return client


def test_the_undated_v1_route_says_nothing_until_it_declares_itself():
    # What the grader actually holds under AZURE_AI_ROUTE_PROFILE=direct-v1: a
    # plain OpenAI client pointed at …/openai/v1/. No Azure attribute exists on
    # it, so the meter — which asks the client, because the client is what puts
    # the value on the wire — is right to answer "unknown" twice. This is the
    # exact shape of what all 84 calls of the first paid grading run recorded.
    silent = FakeClient(_reply("sees-things"))
    assert deployment_of(silent, "sees-things") is None
    assert api_version_of(silent) is None

    # Same class, same call, same request. The only new thing is that whoever
    # opened the connection wrote down how it routes.
    declared = _declaring(_reply("sees-things"))
    assert deployment_of(declared, "sees-things") == "sees-things"
    assert api_version_of(declared) == "v1"


def test_one_declared_connection_can_address_two_deployments():
    # Grading a deliverable holding a picture and a recording runs both readers
    # over a single shared connection, each naming its own model. A deployment
    # fixed once at connection time would have billed the audio tokens to the
    # vision deployment — the merged-perception-line failure again, one layer
    # down.
    shared = _declaring(_reply("sees-things"))

    assert deployment_of(shared, "sees-things") == "sees-things"
    assert deployment_of(shared, "hears-things") == "hears-things"


def test_a_declaration_never_overrules_what_the_client_itself_reports():
    # A dated Azure client resolves and keeps both values, and those are the
    # ones that go out. A declaration is a fallback for a route that cannot
    # speak, never a second opinion about one that can. Both are set here, and
    # they disagree on purpose.
    pinned = _declaring(
        _reply("sees-things"),
        declared_api_version="v1",
        azure=True,
        deployment="pinned-route",
        api_version="2026-01-01",
    )

    assert deployment_of(pinned, "ignored-by-the-sdk") == "pinned-route"
    assert api_version_of(pinned) == "2026-01-01"


def test_a_route_that_does_not_name_deployments_declares_only_its_contract():
    # The flag is a routing fact, not a formality. A route carrying a fixed API
    # contract but taking a bare model name must not have that model name filed
    # as a deployment it never had.
    bare = _declaring(_reply("sees-things"), names_deployments=False)

    assert deployment_of(bare, "sees-things") is None
    assert api_version_of(bare) == "v1"


@pytest.mark.parametrize("impostor", ["v1", object(), None, {"api_version": "v1"}])
def test_something_that_is_not_a_declaration_is_not_read_as_one(impostor):
    # The attribute carries a promise about routing. Anything else found under
    # that name — a proxy that re-wrapped it, a leftover string — is discarded
    # rather than believed, because "unknown" is the safe direction to fail in.
    client = FakeClient(_reply("sees-things"))
    setattr(client, ROUTE_IDENTITY_ATTRIBUTE, impostor)

    assert route_identity_of(client) is None
    assert deployment_of(client, "sees-things") is None
    assert api_version_of(client) is None


def test_a_metered_call_on_a_declared_route_records_both(recorder, ledger, tmp_path):
    client = recorder.meter(_declaring(_reply("sees-things")), provider="azure")

    with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
        client.chat.completions.create(model="gold-judge", messages=[])

    export = tmp_path / "ledger.jsonl"
    ledger.export_jsonl(export)
    (row,) = [
        json.loads(line)
        for line in export.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("record_type", "call") == "call"
    ]

    assert row["deployment"] == "gold-judge"
    assert row["api_version"] == "v1"


def test_a_real_sdk_client_accepts_the_declaration():
    # The declaration is an ordinary attribute set on an SDK object this repo
    # does not own. If a future release gives OpenAI __slots__, that has to
    # fail here, loudly, rather than silently returning every v1-route receipt
    # to the state above. Constructing a client opens no connection: the key is
    # a placeholder and the host is unroutable by definition.
    from openai import OpenAI

    client = OpenAI(
        api_key="not-a-real-key",
        base_url="https://account.invalid/openai/v1/",
    )
    try:
        setattr(
            client,
            ROUTE_IDENTITY_ATTRIBUTE,
            RouteCallIdentity(model_argument_names_deployment=True, api_version="v1"),
        )
        assert deployment_of(client, "gold-judge") == "gold-judge"
        assert api_version_of(client) == "v1"
    finally:
        client.close()


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
