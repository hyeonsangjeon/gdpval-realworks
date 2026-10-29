"""Synthetic shared money admission; no tariff, provider or study execution."""

import json
import hashlib
import multiprocessing
import os
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures("native_hosted_runner")
import yaml

import gpt56_pilot_usd_budget as usd
import gpt56_pilot_wire_receipt as wire
import step8_grade as step8
from core.cost_metering import CostRecorder
from core import runner_environment
from core.cost_receipts import CostReceiptLedger, STAGE_GRADING, STAGE_PERCEPTION
from .test_gpt56_pilot_remaining_caps import TASKS
from .test_gpt56_pilot_provider_observation import _post, _upstream, UPSTREAM
from .test_gpt56_pilot_token_precheck import _response

CAPTURE = "b" * 64
MODEL = "gpt-5.6-sol"
CONFIG = {"config_name": usd.RUN_ID + "_v2_sol_max", "judge": {
    "provider": "azure_openai", "model": MODEL, "deployment": MODEL}}
PRICE_FIXTURE = {"providers": {"azure:" + MODEL: {
    "input_usd_per_million": "10", "cached_input_usd_per_million": "1",
    "output_usd_per_million": "45", "cache_write_usd_per_million": "0",
    "cache_write_billed_as": "none", "reasoning_billed_as": "output",
    "source": "offline fixture, not an approved tariff", "last_reviewed": "fixture",
    "currency": "USD", "unit": "per 1,000,000 tokens"}}}


def _ledger(workspace, *, create=False):
    return usd.PilotUsdLedger(workspace, capture_sha256=CAPTURE, task_ids=list(TASKS), create=create)


@pytest.fixture
def ledger(tmp_path):
    instance = _ledger(tmp_path, create=True)
    yield instance
    instance.close()


@pytest.fixture
def priced(monkeypatch, ledger):
    monkeypatch.setattr(usd, "price_document", lambda: deepcopy(PRICE_FIXTURE))
    return usd.GradingUsdAdmission(ledger, CONFIG)


def _reply(**overrides):
    return {"status": "completed", "model": MODEL, "usage": {"input_tokens": 10, "output_tokens": 2}, **overrides}


def _kwargs():
    return {"model": MODEL, "input": "synthetic " * 20, "max_output_tokens": 10}


class _FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = 0
        self.max_retries = 0
        self.responses = SimpleNamespace(create=self.create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls += 1
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


@pytest.mark.parametrize("first,second", [("inference", "grading"), ("grading", "inference")])
@pytest.mark.parametrize("amount,allowed", [("79.99", True), ("80", True), ("80.01", False)])
def test_combined_ceiling_reserves_before_either_origin(ledger, first, second, amount, allowed):
    one = ledger.begin(first, TASKS[0])
    ticket = ledger.reserve(one, Decimal(120))
    assert ledger.settle(ticket, Decimal(120), Decimal(0)) is None
    two = ledger.begin(second, TASKS[1])
    if allowed:
        ledger.reserve(two, Decimal(amount))
    else:
        with pytest.raises(usd.PilotUsdRefused) as refused:
            ledger.reserve(two, Decimal(amount))
        assert refused.value.code == usd.CEILING and refused.value.source == second
    snapshot = ledger.snapshot()
    assert usd.checked_snapshot(snapshot)
    assert snapshot["stop_source"] == (None if allowed else second)
    assert Decimal(snapshot["combined_modeled_usd"]) == Decimal(120) + (Decimal(amount) if allowed else 0)
    assert snapshot["actual_billing_hard_limit_verified"] is False


@pytest.mark.parametrize("origin", ["inference", "grading"])
def test_clean_reopen_and_idempotent_settlement_never_refill(tmp_path, origin):
    first = _ledger(tmp_path, create=True)
    account = first.begin(origin, TASKS[0])
    ticket = first.reserve(account, Decimal(140))
    first.settle(ticket, Decimal(130), Decimal(0))
    binding = first.binding()
    first.close()
    reopened = _ledger(tmp_path)
    try:
        assert reopened.binding() == binding
        assert reopened.settle(ticket, Decimal(130), Decimal(0)) is None
        assert reopened.snapshot()["remaining_modeled_usd"] == "70"
        other = reopened.begin("grading" if origin == "inference" else "inference", TASKS[1])
        with pytest.raises(usd.PilotUsdRefused, match=usd.CEILING):
            reopened.reserve(other, Decimal(71))
    finally:
        reopened.close()


@pytest.mark.parametrize("origin", ["inference", "grading"])
def test_unknown_usage_consumes_reservation_and_blocks_other_origin(tmp_path, origin):
    first = _ledger(tmp_path, create=True)
    account = first.begin(origin, TASKS[0])
    first.reserve(account, Decimal(120))
    first.observe(account, Decimal(20), Decimal(0))
    first.abandon(account)
    snapshot = first.snapshot()
    assert snapshot["combined_modeled_usd"] == "120"
    assert snapshot["unknown_consumed_usd"] == "100"
    assert snapshot["unknown_requests"] == 1 and snapshot["stop_reason"] == usd.UNKNOWN
    first.close()
    reopened = _ledger(tmp_path)
    try:
        other = reopened.begin("grading" if origin == "inference" else "inference", TASKS[1])
        with pytest.raises(usd.PilotUsdRefused, match=usd.UNKNOWN):
            reopened.reserve(other, Decimal(1))
        assert reopened.snapshot()["combined_modeled_usd"] == "120"
    finally:
        reopened.close()


def test_close_with_pending_and_duplicate_request_id_are_fail_closed(tmp_path):
    instance = _ledger(tmp_path, create=True)
    a, b = [instance.begin(origin, TASKS[0]) for origin in ("inference", "grading")]
    instance.reserve(a, Decimal(100), request_id="c" * 32)
    with pytest.raises(usd.PilotUsdRefused, match=usd.UNVERIFIED):
        instance.reserve(b, Decimal(100), request_id="c" * 32)
    assert instance.snapshot()["pending_requests"] == 1
    instance.close()
    reopened = _ledger(tmp_path)
    try:
        snapshot = reopened.snapshot()
        assert snapshot["unknown_requests"] == 1
        assert snapshot["combined_modeled_usd"] == "100"
    finally:
        reopened.close()


def _reserve_worker(workspace, role, pipe, release):
    instance = _ledger(workspace)
    account = instance.begin(role, TASKS[0])
    try:
        ticket = instance.reserve(account, Decimal(20))
        pipe.send((True, role))
        if not release.wait(10):
            raise RuntimeError("synthetic coordinator timeout")
        instance.settle(ticket, Decimal(20), Decimal(0))
    except usd.PilotUsdRefused as refused:
        pipe.send((False, refused.code))
    finally:
        instance.close()
        pipe.close()


def test_process_concurrency_never_reserves_more_than_combined_ceiling(tmp_path):
    instance = _ledger(tmp_path, create=True)
    context = multiprocessing.get_context("fork")
    release = context.Event()
    jobs = []
    try:
        for i in range(12):
            parent, child = context.Pipe(duplex=False)
            process = context.Process(target=_reserve_worker, args=(str(tmp_path), "grading" if i % 2 else "inference", child, release))
            process.start()
            child.close()
            jobs.append((process, parent))
        replies = []
        for process, pipe in jobs:
            assert pipe.poll(15)
            replies.append(pipe.recv())
        assert sum(success for success, _ in replies) == 10
        assert all(value == usd.CEILING for success, value in replies if not success)
        assert instance.snapshot()["combined_modeled_usd"] == "200"
        release.set()
        for process, pipe in jobs:
            process.join(10)
            assert process.exitcode == 0
            pipe.close()
        snapshot = instance.snapshot()
        assert snapshot["pending_requests"] == snapshot["unknown_requests"] == 0
        assert snapshot["combined_modeled_usd"] == "200"
    finally:
        release.set()
        for process, pipe in jobs:
            if process.is_alive():
                process.terminate()
                process.join(5)
            pipe.close()
        instance.close()


def _crash_worker(workspace, pipe):
    instance = _ledger(workspace)
    account = instance.begin("inference", TASKS[0])
    instance.reserve(account, Decimal(120))
    pipe.send("reserved")
    pipe.close()
    os._exit(0)


def test_process_restart_consumes_lost_reply_without_reset(tmp_path):
    instance = _ledger(tmp_path, create=True)
    instance.close()
    context = multiprocessing.get_context("fork")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_crash_worker, args=(str(tmp_path), child))
    process.start()
    child.close()
    try:
        assert parent.poll(10) and parent.recv() == "reserved"
        process.join(10)
        assert process.exitcode == 0
        reopened = _ledger(tmp_path)
        try:
            snapshot = reopened.snapshot()
            assert snapshot["unknown_consumed_usd"] == "120"
            assert snapshot["stop_reason"] == usd.UNKNOWN and snapshot["stop_source"] == "inference"
            account = reopened.begin("grading", TASKS[1])
            with pytest.raises(usd.PilotUsdRefused, match=usd.UNKNOWN):
                reopened.reserve(account, Decimal(1))
        finally:
            reopened.close()
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        parent.close()


@pytest.mark.parametrize("failure", ["missing", "symlink", "wrong_capture", "wrong_tasks"])
def test_persistence_never_adopts_missing_or_foreign_state(tmp_path, failure):
    if failure == "missing":
        with pytest.raises(usd.PilotUsdRefused):
            _ledger(tmp_path)
        assert not (tmp_path / usd.DIRECTORY).exists()
        return
    instance = _ledger(tmp_path, create=True)
    instance.close()
    if failure == "symlink":
        database = tmp_path / usd.DIRECTORY / usd.DATABASE
        moved = database.with_name("retained.sqlite3")
        database.rename(moved)
        database.symlink_to(moved)
    with pytest.raises(usd.PilotUsdRefused):
        usd.PilotUsdLedger(tmp_path, capture_sha256="d" * 64 if failure == "wrong_capture" else CAPTURE,
                           task_ids=list(reversed(TASKS)) if failure == "wrong_tasks" else list(TASKS))


@pytest.mark.parametrize("stage", [STAGE_GRADING, STAGE_PERCEPTION])
def test_actual_metered_client_reserves_before_call_and_settles(ledger, priced, tmp_path, stage):
    audit = CostReceiptLedger(tmp_path / "audit.sqlite3", run_id="synthetic-grading")
    recorder = CostRecorder(audit, usd_admission=priced)
    client = _FakeClient(_reply())
    wrapped = recorder.meter(client, provider="azure", model=MODEL, stage=stage)
    original = client.create

    def observed(**kwargs):
        assert ledger.snapshot()["pending_requests"] == 1
        return original(**kwargs)

    client.responses.create = observed
    try:
        with recorder.attributed(task_id=TASKS[0], stage=STAGE_GRADING):
            assert wrapped.responses.create(**_kwargs()) == _reply()
        snapshot = ledger.snapshot()
        assert client.calls == 1 and snapshot["pending_requests"] == 0
        assert Decimal(snapshot["grading_known_usd"]) == Decimal("0.00019")
        assert snapshot["stop_reason"] is None
    finally:
        audit.close()


@pytest.mark.parametrize("bad", ["absent_usage", "partial_usage", "partial_response", "other_model", "exception", "no_output_limit"])
def test_grading_unknown_never_egresses_a_followup(ledger, priced, tmp_path, bad):
    responses = {"absent_usage": _reply(usage=None), "partial_usage": _reply(usage={"input_tokens": 10}),
                 "partial_response": _reply(status="incomplete"), "other_model": _reply(model="gpt-5.6-sol-fast"),
                 "exception": RuntimeError("synthetic"), "no_output_limit": _reply()}
    audit = CostReceiptLedger(tmp_path / "audit.sqlite3", run_id="synthetic-grading")
    recorder = CostRecorder(audit, usd_admission=priced)
    client = _FakeClient(responses[bad])
    wrapped = recorder.meter(client, provider="azure", model=MODEL)
    kwargs = _kwargs()
    if bad == "no_output_limit":
        del kwargs["max_output_tokens"]
    try:
        with recorder.attributed(task_id=TASKS[0], stage=STAGE_GRADING):
            with pytest.raises(RuntimeError if bad == "exception" else usd.GradingUsdStopped):
                wrapped.responses.create(**kwargs)
            with pytest.raises(usd.GradingUsdStopped):
                wrapped.responses.create(**_kwargs())
        assert client.calls == int(bad != "no_output_limit")
        snapshot = ledger.snapshot()
        assert snapshot["stop_reason"] == usd.UNKNOWN
        if bad != "no_output_limit":
            assert Decimal(snapshot["unknown_consumed_usd"]) > 0
    finally:
        audit.close()


def test_shared_grade_spend_blocks_real_native_forward_seam(monkeypatch, ledger):
    grade = ledger.begin("grading", TASKS[0])
    ledger.observe(grade, Decimal(195), Decimal(0))
    budget = wire._NativeRequestBudget(TASKS, usd_ledger=ledger)
    with _upstream(monkeypatch, [_response()]) as (received, connections):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 60)
        capture.bind_budget(budget, TASKS[1])
        try:
            assert _post(capture.base_url)[0] == 400
        finally:
            capture.close()
    assert received == connections == []
    raw = capture.summary()
    assert wire.bounded_provider_observation(raw) == raw
    shared = raw["runtime_caps"]["usd_ceiling"]["shared_budget"]
    assert shared["stop_reason"] == usd.CEILING and shared["stop_source"] == "inference"
    assert shared["grading_known_usd"] == "195"
    assert capture.server.socket.fileno() == -1 and not capture.thread.is_alive()


def test_inference_spend_blocks_actual_grading_wrapper(ledger, priced, tmp_path):
    account = ledger.begin("inference", TASKS[0])
    ledger.observe(account, Decimal(200), Decimal(0))
    audit = CostReceiptLedger(tmp_path / "audit.sqlite3", run_id="synthetic")
    recorder = CostRecorder(audit, usd_admission=priced)
    client = _FakeClient(_reply())
    try:
        wrapped = recorder.meter(client, provider="azure", model=MODEL)
        with recorder.attributed(task_id=TASKS[1], stage=STAGE_GRADING):
            with pytest.raises(usd.GradingUsdStopped, match=usd.CEILING) as error:
                wrapped.responses.create(**_kwargs())
        assert error.value.source == "grading" and client.calls == 0
        assert ledger.snapshot()["stop_source"] == "grading"
    finally:
        audit.close()


@pytest.mark.parametrize("retries", [None, True, 1, 2])
def test_hidden_sdk_retries_cannot_bypass_grading_reservations(ledger, priced, tmp_path, retries):
    audit = CostReceiptLedger(tmp_path / "audit.sqlite3", run_id="synthetic")
    recorder = CostRecorder(audit, usd_admission=priced)
    client = _FakeClient(_reply())
    client.max_retries = retries
    try:
        with pytest.raises(usd.PilotUsdRefused, match=usd.UNKNOWN):
            recorder.meter(client, provider="azure", model=MODEL)
        assert client.calls == 0 and ledger.snapshot()["stop_source"] == "grading"
    finally:
        audit.close()


def test_changed_transport_is_rechecked_before_each_grading_call(ledger, priced, tmp_path):
    audit = CostReceiptLedger(tmp_path / "audit.sqlite3", run_id="synthetic")
    recorder = CostRecorder(audit, usd_admission=priced)
    client = _FakeClient(_reply())
    wrapped = recorder.meter(client, provider="azure", model=MODEL)
    client.max_retries = 2
    try:
        with recorder.attributed(task_id=TASKS[0], stage=STAGE_GRADING):
            with pytest.raises(usd.GradingUsdStopped, match=usd.UNKNOWN):
                wrapped.responses.create(**_kwargs())
        assert client.calls == 0 and ledger.snapshot()["pending_requests"] == 0
    finally:
        audit.close()


@pytest.mark.parametrize("extra", [{"extra_body": {"max_output_tokens": 100000}},
                                   {"modalities": ["audio"]}, {"previous_response_id": "opaque"},
                                   {"stream": True}])
def test_hidden_request_overrides_are_refused_before_any_call(ledger, priced, tmp_path, extra):
    audit = CostReceiptLedger(tmp_path / "audit.sqlite3", run_id="synthetic")
    recorder = CostRecorder(audit, usd_admission=priced)
    client = _FakeClient(_reply())
    wrapped = recorder.meter(client, provider="azure", model=MODEL)
    try:
        with recorder.attributed(task_id=TASKS[0], stage=STAGE_GRADING):
            with pytest.raises(usd.GradingUsdStopped, match=usd.UNKNOWN):
                wrapped.responses.create(**{**_kwargs(), **extra})
        assert client.calls == 0
    finally:
        audit.close()


def test_sub_receipt_precision_cannot_round_a_request_inside_the_cap(ledger):
    account = ledger.begin("grading", TASKS[0])
    with pytest.raises(usd.PilotUsdRefused):
        ledger.reserve(account, Decimal("200.000000001"))
    assert ledger.snapshot()["pending_requests"] == 0
    ticket = ledger.reserve(account, Decimal("0.00000001"))
    assert ledger.settle(ticket, Decimal("0.00000001"), Decimal(0)) is None
    assert Decimal(ledger.snapshot()["combined_modeled_usd"]) == Decimal("0.00000001")


def test_sdk_floor_and_wire_settlement_share_one_reserved_amount(ledger):
    facade = wire._PilotUsdLedger(ledger)
    attempt = facade.begin(TASKS[0])
    ticket, reason = facade.reserve(attempt, 300000, 10000)
    assert reason is None and Decimal(ledger.snapshot()["combined_modeled_usd"]) == Decimal("7.20")
    assert facade.observe_sdk(attempt, {"inputTokens": 100, "outputTokens": 5}) is None
    assert Decimal(ledger.snapshot()["combined_modeled_usd"]) == Decimal("7.20")
    assert facade.finish(ticket, 100, 5) is None
    result = facade.close_attempt(attempt)
    assert wire._checked_usd_summary(result)
    assert Decimal(result["modeled_total_usd"]) == Decimal("0.002475")
    assert result["pending_requests"] == 0 and result["grading_included"] is True


def test_conflicting_or_late_usage_cannot_reopen_consumed_reservation(ledger):
    account = ledger.begin("grading", TASKS[0])
    ticket = ledger.reserve(account, Decimal(200))
    assert ledger.settle(ticket, Decimal(100), Decimal(0)) is None
    assert ledger.settle(ticket, Decimal(99), Decimal(0)) == usd.UNKNOWN
    assert ledger.snapshot()["combined_modeled_usd"] == "100"
    other = ledger.begin("inference", TASKS[1])
    with pytest.raises(usd.PilotUsdRefused, match=usd.UNKNOWN):
        ledger.reserve(other, Decimal(1))


@pytest.mark.parametrize("mutation", [None, "foreign_binding", "capture_drift", "wrong_task_order"])
def test_grading_opens_only_the_inference_bound_existing_ledger(monkeypatch, ledger, tmp_path, mutation):
    monkeypatch.setattr(usd, "price_document", lambda: deepcopy(PRICE_FIXTURE))
    ready = {"run_id": usd.RUN_ID, "task_ids": list(TASKS), "shared_usd_budget": ledger.binding()}
    if mutation == "foreign_binding":
        ready["shared_usd_budget"]["ledger_id"] = "1" * 32
    if mutation == "wrong_task_order":
        ready["task_ids"].reverse()
    directory = tmp_path / wire.DIRECTORY
    directory.mkdir()
    path = directory / wire.READY_PATH
    raw = json.dumps(ready).encode()
    path.write_bytes(raw + (b" " if mutation == "capture_drift" else b""))
    inference = {"experiment_id": usd.RUN_ID, "pilot_wire_receipts": {
        "path": wire.DIRECTORY + "/" + wire.READY_PATH, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}}
    if mutation:
        with pytest.raises((usd.PilotUsdRefused, ValueError)):
            usd.open_grading_admission(workspace=tmp_path, inference=inference, task_ids=list(TASKS), config=CONFIG)
    else:
        guard = usd.open_grading_admission(workspace=tmp_path, inference=inference, task_ids=list(TASKS), config=CONFIG)
        try:
            ticket = guard.reserve(task_id=TASKS[1], provider="azure", kwargs=_kwargs())
            assert ledger.snapshot()["pending_requests"] == 1
            guard.finish(ticket, _reply())
            assert ledger.snapshot()["grading_known_usd"] == "0.00019"
        finally:
            guard.ledger.close()


@pytest.mark.parametrize("bad", ["missing", "deliberate", "premise", "axes", "cache", "unit", "nan"])
def test_grading_prices_must_be_exact_and_unambiguous(monkeypatch, bad):
    document = deepcopy(PRICE_FIXTURE)
    entry = document["providers"]["azure:" + MODEL]
    if bad == "missing":
        document["providers"].clear()
    elif bad == "deliberate":
        document["models_deliberately_not_priced"] = {"azure:" + MODEL: {}}
    elif bad == "premise":
        entry["premises"] = ["unverified tier"]
    elif bad == "axes":
        document["pricing_axes"] = {"axes_open": {"zone": "unresolved"}}
    elif bad == "cache":
        del entry["cache_write_billed_as"]
    elif bad == "unit":
        entry["unit"] = "tokens"
    else:
        entry["input_usd_per_million"] = "NaN"
    monkeypatch.setattr(usd, "price_document", lambda: document)
    with pytest.raises(usd.PilotUsdRefused, match=usd.UNPRICED):
        usd.grading_prices(CONFIG)


@pytest.mark.parametrize("module_drift", [False, True])
def test_real_step8_refuses_unpriced_sol_before_input_auth_or_client(monkeypatch, tmp_path, capsys, module_drift):
    config = yaml.safe_load((Path(step8.__file__).parent / "grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml").read_bytes())
    config["config_name"] = CONFIG["config_name"]
    config.pop("rerun_identity")
    path = tmp_path / "grading.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(step8, "parse_args", lambda: SimpleNamespace(config=str(path), experiment_yaml_name=usd.RUN_ID,
                                                                    source="local", pilot_usd_workspace=None, dry_run=False))
    monkeypatch.setattr(step8, "load_experiment_yaml", lambda name: SimpleNamespace(experiment_id=usd.RUN_ID))

    def never(*args, **kwargs):
        pytest.fail("input/auth/client effect happened before price refusal")

    monkeypatch.setattr(step8, "load_local_inference_results", never)
    monkeypatch.setattr(step8, "Grader", never)
    if module_drift:
        monkeypatch.setattr(usd, "__file__", str(tmp_path / "foreign_usd.py"))
    assert step8.main() == 4
    result = json.loads(capsys.readouterr().err)
    assert result == {"status": "refused", "source": "grading", "reason": usd.UNVERIFIED if module_drift else usd.UNPRICED,
                      "actual_billing_hard_limit_verified": False,
                      "runner_evidence": runner_environment.receipt("grading")}


def test_pilot_grader_source_closure_binds_the_imported_amount_guard(monkeypatch, tmp_path):
    batch = Path(step8.__file__).parent
    config_path = batch / "grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml"
    config = yaml.safe_load(config_path.read_bytes())
    config["config_name"] = CONFIG["config_name"]
    assert len(step8.compute_grader_source_hash(config_path, config, batch_root=batch)) == 64
    monkeypatch.setattr(usd, "__file__", str(tmp_path / "foreign_usd.py"))
    with pytest.raises(ValueError, match="^pilot USD helper source path mismatch$"):
        step8.compute_grader_source_hash(config_path, config, batch_root=batch)
