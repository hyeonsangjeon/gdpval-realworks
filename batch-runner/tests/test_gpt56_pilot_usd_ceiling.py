"""Synthetic USD admission only, not a live tariff, bill or grading proof."""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal

import pytest

pytestmark = pytest.mark.usefixtures("native_hosted_runner")
import yaml

import gpt56_pilot_wire_receipt as wire
import step2_run_inference as step2
from .test_gpt56_pilot_provider_observation import (
    CANARY, UPSTREAM, _post, _upstream, loopback_only,
)
from .test_gpt56_pilot_remaining_caps import TASKS
from .test_gpt56_pilot_token_precheck import _request, _response


def _capture(budget, task=TASKS[0]):
    observer = wire._ProviderHTTPObservation(UPSTREAM, 60)
    observer.bind_budget(budget, task)
    return observer


def _summary(observer):
    result = observer.summary()
    assert wire.bounded_provider_observation(result) == result
    assert step2._bounded_codex_diagnostics({"provider_observation": result}) == {"provider_observation": result}
    assert CANARY not in json.dumps(result) and UPSTREAM not in json.dumps(result)
    money = result["runtime_caps"]["usd_ceiling"]
    assert money["approved_maximum_usd"] == "200"
    assert money["actual_billing_hard_limit_verified"] is money["effective_tariff_verified"] is False
    assert money["grading_included"] is False
    assert money["grading_usd"] is money["actual_total_pilot_usd"] is None
    assert observer.closed and observer.server.socket.fileno() == -1 and not observer.thread.is_alive()
    return result, money


def _seed_boundary(budget, offset=0):
    """Artificial lower-level ledger floor, NOT a valid native pilot history.

    USD 192.80 plus the unchanged next-request reserve of USD 7.20 equals 200.
    The seed exercises exact currency boundaries without changing approved caps,
    prices or spending anything. It is not injected through the guarded SDK.
    """
    key = budget.usd.begin(TASKS[-1])
    assert budget.usd.observe_sdk(key, {"inputTokens": 0, "outputTokens": 0,
                                      "cacheWriteInputTokens": 15_424_000 + offset}) is None


def test_owner_decision_and_reference_rates_do_not_reprice_history():
    decision = yaml.safe_load(wire._USD_CAPS_PATH.read_bytes())
    assert decision["cost"] == {
        "approved_maximum_usd": 200, "currency": "USD",
        "scope": "five_task_pilot_inference_and_grading_combined",
        "approval_source": "owner_card_record", "approved_at_utc": "2026-10-27T01:56:00Z",
        "approved_at_local": "2026-10-27T10:56:00+09:00",
        "decision_summary": "USD 200 combined inference and grading ceiling for the five-task pilot",
    }
    assert decision["supersedes_monetary_decision"] == {
        "path": "batch-runner/experiments/execution_envelope/gpt56_sol_native_usd_cap_20261027.yaml",
        "git_commit": "32c79f6774a9b4620c9fbf77f9756e32c30f6c0b",
        "sha256": "df64cdb0d1e1f242b7500debbca2ca5dac0eab988783e2a03da80c57a940992f",
        "field": "cost.approved_maximum_usd", "previous_value": 1000,
        "approved_at_utc": "2026-10-26T23:09:00Z", "approval_source": "owner_desk_message",
    }
    assert hashlib.sha256(wire._USD_CAPS_PATH.read_bytes()).hexdigest() == wire.USD_CAPS_SHA256
    assert hashlib.sha256(wire._USD_PRICE_PATH.read_bytes()).hexdigest() == wire.USD_PRICE_TABLE_SHA256
    old = yaml.safe_load(wire._NATIVE_CAPS_PATH.read_bytes())
    assert old["cost"]["approved_maximum_usd"] is None
    assert hashlib.sha256(wire._NATIVE_CAPS_PATH.read_bytes()).hexdigest() == wire.NATIVE_CAPS_SHA256
    policy = wire._native_usd_caps()
    assert policy == {"maximum": Decimal(200), "rates": {
        "input": Decimal("10.00"), "output": Decimal("45.00"), "cache_write": Decimal("12.50"),
    }}
    assert "azure:gpt-5.6-sol" in json.loads(wire._USD_PRICE_PATH.read_bytes())["models_deliberately_not_priced"]
    assert decision["launch_enabled"] is decision["new_study_or_retry_right"] is False


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_usd_boundary_blocks_before_upstream_construction(monkeypatch, offset, capsys):
    budget = wire._NativeRequestBudget(TASKS)
    _seed_boundary(budget, offset)
    with _upstream(monkeypatch, [_response()]) as (received, connections):
        capture = _capture(budget)
        try:
            assert _post(capture.base_url)[0] == (400 if offset > 0 else 200)
        finally:
            capture.close()
    result, money = _summary(capture)
    assert len(received) == len(connections) == int(offset <= 0)
    assert result["native_request_count"] == int(offset <= 0)
    assert money["next_input_reserve_tokens"] == 300000
    assert money["next_output_reserve_tokens"] == 10000
    assert Decimal(money["next_request_reserve_usd"]) == Decimal("7.20")
    assert result["runtime_caps"]["stop_reason"] == (wire.USD_CEILING_EXCEEDED if offset > 0 else None)
    assert money["blocked_requests"] == int(offset > 0)
    if offset > 0:
        assert result["native_request_cap_reason"] == wire.USD_CEILING_EXCEEDED
        assert Decimal(money["modeled_total_usd"]) + Decimal(money["next_request_reserve_usd"]) > Decimal(200)
        for task in TASKS:
            with pytest.raises(wire.PilotWireReceiptRefused):
                budget.require_available(task)
    assert CANARY not in "".join(capsys.readouterr())


def test_cumulative_usage_and_sdk_floor_are_not_added_twice(monkeypatch):
    budget = wire._NativeRequestBudget(TASKS)
    with _upstream(monkeypatch, [_response(30, 6), _response(20, 4)]) as (received, _):
        capture = _capture(budget)
        try:
            assert _post(capture.base_url)[0] == 200
            capture.report_usage({"inputTokens": 30, "outputTokens": 6})
            assert _post(capture.base_url)[0] == 200
            capture.report_usage({"inputTokens": 50, "outputTokens": 10, "cacheWriteInputTokens": 12})
        finally:
            capture.close()
    _, money = _summary(capture)
    assert len(received) == 2
    assert Decimal(money["inference_input_output_usd"]) == Decimal("0.000950")
    assert Decimal(money["cache_write_reserve_usd"]) == Decimal("0.000625")
    assert Decimal(money["modeled_total_usd"]) == Decimal("0.001575")
    assert money["cache_write_tokens_observed"] == 12
    assert money["pending_requests"] == 0


def test_sdk_floor_during_response_reduces_pending_reserve_not_double_cost():
    ledger = wire._PilotUsdLedger()
    attempt = ledger.begin(TASKS[0])
    reservation, reason = ledger.reserve(attempt, 300000, 10000)
    assert reason is None
    assert ledger.observe_sdk(attempt, {"inputTokens": 100, "outputTokens": 10}) is None
    during = ledger.snapshot(attempt)
    assert Decimal(during["modeled_total_usd"]) == Decimal("7.20")
    assert ledger.finish(reservation, 100, 10) is None
    final = ledger.snapshot(attempt)
    assert Decimal(final["modeled_total_usd"]) == Decimal("0.002700")
    assert final["cache_write_tokens_observed"] is None  # Not an invented 0.
    assert wire._checked_usd_summary(final)


def test_one_ledger_spans_tasks_attempts_and_closed_receipts_stay_fixed(monkeypatch):
    budget = wire._NativeRequestBudget(TASKS)
    summaries = []
    with _upstream(monkeypatch, [_response(10, 2)] * 3):
        for task in (TASKS[0], TASKS[0], TASKS[1]):
            capture = _capture(budget, task)
            try:
                assert _post(capture.base_url)[0] == 200
            finally:
                capture.close()
            summaries.append(_summary(capture)[1])
    unit = Decimal("0.000315")
    assert [Decimal(row["modeled_accounted_usd"]) for row in summaries] == [unit, 2 * unit, 3 * unit]
    assert [Decimal(row["task_accounted_usd"]) for row in summaries] == [unit, 2 * unit, unit]
    assert all(Decimal(row["attempt_accounted_usd"]) == unit for row in summaries)
    assert budget.snapshot(TASKS[0]) == {"task_requests": 2, "pilot_requests": 3}


@pytest.mark.parametrize("damage", ["missing", "partial", "malformed", "http_error", "truncated"])
def test_unknown_response_keeps_reserve_and_next_task_proceeds(monkeypatch, damage):
    # Owner decision 2026-10-30: the unknown reply keeps its whole reservation
    # booked, and the pilot is not stopped by it.
    row = _response()
    document = json.loads(row["body"])
    if damage == "missing":
        document.pop("usage")
    elif damage == "partial":
        document["status"] = "incomplete"
    elif damage == "malformed":
        document["usage"]["input_tokens"] = True
    elif damage == "http_error":
        row["status"] = 500
    else:
        row["missing"] = 8
    row["body"] = json.dumps(document).encode()
    budget = wire._NativeRequestBudget(TASKS)
    with _upstream(monkeypatch, [row, _response()]) as (received, connections):
        first = _capture(budget)
        try:
            _post(first.base_url)
        finally:
            first.close()
        first_result, first_money = _summary(first)
        next_task = _capture(budget, TASKS[1])
        try:
            assert _post(next_task.base_url)[0] == 200
        finally:
            next_task.close()
        _, later = _summary(next_task)
    assert len(received) == len(connections) == 2
    assert first_result["runtime_caps"]["stop_reason"] not in wire._USD_STOPS
    assert first_money["stop_reason"] is None and later["stop_reason"] is None
    assert first_money["pending_requests"] == later["pending_requests"] == 1
    assert Decimal(first_money["pending_reserve_usd"]) == Decimal("7.20")
    assert first_money["cache_write_tokens_observed"] is None


def test_failed_connection_retains_money_and_next_task_may_try_again(monkeypatch):
    calls = []
    def fail(*_args, **_kwargs):
        calls.append(True)
        raise OSError(CANARY)
    monkeypatch.setattr(wire, "HTTPSConnection", fail)
    budget = wire._NativeRequestBudget(TASKS)
    for index, task in enumerate(TASKS[:2], start=1):
        capture = _capture(budget, task)
        try:
            assert _post(capture.base_url)[0] == 502
        finally:
            capture.close()
        _, money = _summary(capture)
        assert money["stop_reason"] is None and money["pending_requests"] == index
        assert Decimal(money["modeled_total_usd"]) == Decimal("7.20") * index  # Each failure stays booked.
    assert len(calls) == 2 and budget.total == 2


def test_concurrent_last_usd_reservation_has_only_one_upstream(monkeypatch):
    budget = wire._NativeRequestBudget(TASKS)
    _seed_boundary(budget)
    entered, release = threading.Event(), threading.Event()
    def hold():
        entered.set()
        assert release.wait(3)
    captures = [_capture(budget, task) for task in TASKS[:2]]
    with _upstream(monkeypatch, [_response()], on_request=hold) as (received, connections):
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(_post, captures[0].base_url)
                assert entered.wait(3)
                try:
                    assert _post(captures[1].base_url) == (400, b"")
                finally:
                    release.set()
                assert first.result(timeout=3)[0] == 200
        finally:
            release.set()
            for capture in captures:
                capture.close()
    assert len(received) == len(connections) == budget.total == 1
    assert _summary(captures[1])[1]["stop_reason"] == wire.USD_CEILING_EXCEEDED


@pytest.mark.parametrize("role", ["_USD_CAPS_PATH", "_USD_PRICE_PATH"])
def test_price_or_approval_drift_refuses_before_upstream(monkeypatch, tmp_path, role):
    budget = wire._NativeRequestBudget(TASKS)
    bad = tmp_path / "drifted-public-contract"
    bad.write_bytes(getattr(wire, role).read_bytes() + b"\n")
    calls = []
    monkeypatch.setattr(wire, "HTTPSConnection", lambda *_a, **_k: calls.append(True))
    capture = _capture(budget)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(wire, role, bad)
            assert _post(capture.base_url) == (400, b"")
    finally:
        capture.close()
    assert calls == []
    assert _summary(capture)[1]["stop_reason"] == wire.USD_PRICE_CONTRACT_UNVERIFIED


@pytest.mark.parametrize("key,value", [
    ("approved_maximum_usd", "200.01"), ("actual_billing_hard_limit_verified", True),
    ("effective_tariff_verified", True), ("grading_included", True), ("grading_usd", "0"),
    ("actual_total_pilot_usd", "0"), ("modeled_total_usd", "NaN"),
    ("pending_reserve_usd", -1), ("remaining_modeled_usd", "999"),
    ("cache_write_tokens_observed", False), ("price_table_sha256", "0" * 64),
    ("private_text", CANARY),
])
def test_money_projection_rejects_bad_fields_and_never_upgrades_authority(key, value):
    ledger = wire._PilotUsdLedger()
    original = ledger.snapshot(ledger.begin(TASKS[0]))
    assert wire._checked_usd_summary(original)
    changed = deepcopy(original)
    changed[key] = value
    assert not wire._checked_usd_summary(changed)


def test_actual_usage_above_reserved_amount_is_booked_not_stopped():
    ledger = wire._PilotUsdLedger()
    attempt = ledger.begin(TASKS[0])
    reservation, reason = ledger.reserve(attempt, 1, 1)
    assert reason is None
    assert ledger.finish(reservation, 2, 1) is None
    receipt = ledger.snapshot(attempt)
    assert Decimal(receipt["modeled_accounted_usd"]) == Decimal("0.000090")  # The overrun is booked as observed.
    assert ledger.reserve(attempt, 1, 1)[1] is None
    assert wire._checked_usd_summary(ledger.snapshot(attempt))


@pytest.mark.parametrize("model", [None, "gpt-5.6-sol-fast", CANARY])
def test_unpriced_request_model_is_refused_before_any_upstream(monkeypatch, model):
    budget = wire._NativeRequestBudget(TASKS)
    with _upstream(monkeypatch, []) as (received, connections):
        capture = _capture(budget)
        try:
            assert _post(capture.base_url, body=_request(model=model)) == (400, b"")
        finally:
            capture.close()
    result, money = _summary(capture)
    assert received == connections == []
    assert result["runtime_caps"]["stop_reason"] == wire.NATIVE_TOKEN_REQUEST_UNVERIFIED
    assert money["pending_requests"] == 0


def test_fast_response_usage_keeps_its_reservation_instead_of_sol_reference_rates(monkeypatch):
    response = _response()
    document = json.loads(response["body"])
    document["model"] = "gpt-5.6-sol-fast"
    response["body"] = json.dumps(document).encode()
    budget = wire._NativeRequestBudget(TASKS)
    with _upstream(monkeypatch, [response]) as (received, _):
        capture = _capture(budget)
        try:
            assert _post(capture.base_url)[0] == 200
        finally:
            capture.close()
    result, money = _summary(capture)
    assert len(received) == 1
    assert result["served_model"] == "gpt-5.6-sol-fast"  # Observed, never substituted.
    assert money["stop_reason"] is None
    assert money["pending_requests"] == 1  # Booked at its whole reservation, not repriced.
