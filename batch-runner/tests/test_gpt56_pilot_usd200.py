"""USD 200 admission scenarios, not provider usage, a tariff or a paid pilot.

The card reports USD 0.06..0.99 per solving attempt and USD 2..6 per grade.
No per-task raw usage or request sizes accompany those ranges. Replay their
endpoints as synthetic settled USD, never reverse-engineer observed tokens.
"""

import hashlib
import json
from copy import deepcopy
from decimal import Decimal

import pytest
import yaml

import gpt56_pilot_usd_budget as usd
import gpt56_pilot_wire_receipt as wire
import gpt56_sol_codex_pilot_preflight as pilot
from .test_gpt56_pilot_shared_usd import CAPTURE, CONFIG, PRICE_FIXTURE


def _scenario(tmp_path, monkeypatch):
    plan = pilot.load_plan(pilot.ROOT / pilot.SOURCE_PROFILE)
    tasks = [row["task_id"] for row in plan["dataset"]["tasks"]]
    ledger = usd.PilotUsdLedger(tmp_path, capture_sha256=CAPTURE, task_ids=tasks, create=True)
    native = wire._PilotUsdLedger(ledger)
    limits = wire._native_caps()["per_attempt"]
    native_io = native._value(limits["input_tokens"], limits["output_tokens"], 0)
    native_cache = native._value(0, 0, limits["input_tokens"])
    assert native_io == Decimal("3.45") and native_cache == Decimal("3.75")
    assert native_io + native_cache == Decimal("7.20")

    # Explicit fixture only. Do not price the real deliberately-unpriced Sol.
    prices = deepcopy(PRICE_FIXTURE)
    entry = prices["providers"]["azure:gpt-5.6-sol"]
    entry.update(cache_write_usd_per_million="12.50", cache_write_billed_as="input_tokens")
    monkeypatch.setattr(usd, "price_document", lambda: deepcopy(prices))
    admission = usd.GradingUsdAdmission(ledger, CONFIG)
    frozen = yaml.safe_load((pilot.ROOT / pilot.GRADER).read_bytes())
    output = frozen["judge"]["generation"]["max_output_tokens"]
    assert output == frozen["grader"]["per_item_max_output_tokens"] == 2400
    kwargs = {"model": "gpt-5.6-sol", "input": "", "max_output_tokens": output}
    empty_bytes = len(json.dumps(kwargs, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    kwargs["input"] = "x" * (1024 * 1024 - empty_bytes)
    inputs, outputs = usd._request_allowance(kwargs)
    assert inputs == 1048576 and outputs == output
    grade_io = (Decimal(inputs) * Decimal(10) + Decimal(outputs) * Decimal(45)) / Decimal(1_000_000)
    grade_cache = Decimal(inputs) * Decimal("12.50") / Decimal(1_000_000)
    assert grade_io == Decimal("10.59376") and grade_cache == Decimal("13.10720")
    assert grade_io + grade_cache == Decimal("23.70096")
    return plan, tasks, ledger, admission, kwargs, native_io, native_cache, grade_io, grade_cache


@pytest.mark.parametrize("solver,grade", [("0.06", "2"), ("0.99", "6")])
@pytest.mark.parametrize("attempts", [1, 4])
@pytest.mark.parametrize("grade_calls", [1, 2])
@pytest.mark.parametrize("extra_write_factor", ["0", "1.25"])
def test_five_task_owner_reported_cost_range_fits_usd200(
        tmp_path, monkeypatch, request, solver, grade, attempts, grade_calls, extra_write_factor):
    plan, tasks, ledger, admission, kwargs, nio, ncache, gio, gcache = _scenario(tmp_path, monkeypatch)
    assert attempts <= 1 + plan["limits"]["infrastructure_retries_per_task"] == 4
    assert len(tasks) == plan["pilot"]["task_count"] == 5
    solver, grade, write = Decimal(solver), Decimal(grade), Decimal(extra_write_factor)
    peak, gross = Decimal(0), Decimal(0)
    try:
        for task in tasks:
            for _ in range(attempts):
                account = ledger.begin("inference", task)
                ticket = ledger.reserve(account, nio + ncache)
                peak = max(peak, Decimal(ledger.snapshot()["combined_modeled_usd"]))
                gross += nio + ncache
                assert ledger.settle(ticket, solver, solver * write) is None
            for _ in range(grade_calls):
                ticket = admission.reserve(task_id=task, provider="azure", kwargs=kwargs)
                snapshot = ledger.snapshot()
                assert Decimal(snapshot["pending_usd"]) == gio + gcache
                peak = max(peak, Decimal(snapshot["combined_modeled_usd"]))
                gross += gio + gcache
                # Monetary replay only; these are not fabricated provider tokens.
                io = grade / grade_calls
                assert ledger.settle(ticket["reservation"], io, io * write) is None
        result = ledger.snapshot()
        total = 5 * (attempts * solver + grade) * (1 + write)
        assert Decimal(result["combined_modeled_usd"]) == total <= Decimal("112.05")
        assert peak == total - grade / grade_calls * (1 + write) + gio + gcache
        assert peak <= Decimal("129.00096") < Decimal(200)
        assert result["pending_requests"] == result["unknown_requests"] == 0
        assert result["stop_reason"] is None and usd.checked_snapshot(result)
        request.node.user_properties.append(("usd200_simulation", json.dumps({
            "evidence": "synthetic_replay_of_card_reported_ranges_not_raw_usage",
            "task_ids": tasks, "attempts_per_task": attempts, "grading_calls_per_task_fixture": grade_calls,
            "solver_usd_per_attempt": str(solver), "grade_usd_per_task": str(grade),
            "extra_cache_write_factor_scenario": str(write),
            "native_request_reserve_usd": str(nio + ncache), "grading_request_reserve_usd": str(gio + gcache),
            "gross_reservations_over_time_usd_not_simultaneous": str(gross),
            "peak_accounted_plus_pending_usd": str(peak), "final_modeled_usd": str(total),
            "actual_usage_or_tariff_verified": False,
        }, sort_keys=True)))
    finally:
        ledger.close()


def test_full_cap_stress_stops_third_grading_request_without_weakening_reserves(tmp_path, monkeypatch, request):
    plan, tasks, ledger, admission, kwargs, nio, ncache, gio, gcache = _scenario(tmp_path, monkeypatch)
    try:
        for task in tasks:
            for _ in range(1 + plan["limits"]["infrastructure_retries_per_task"]):
                account = ledger.begin("inference", task)
                ticket = ledger.reserve(account, nio + ncache)
                assert ledger.settle(ticket, nio, ncache) is None
        assert Decimal(ledger.snapshot()["combined_modeled_usd"]) == Decimal(144)
        for task in tasks[:2]:
            ticket = admission.reserve(task_id=task, provider="azure", kwargs=kwargs)
            assert ledger.settle(ticket["reservation"], gio, gcache) is None
        with pytest.raises(usd.PilotUsdRefused, match=usd.CEILING) as refused:
            admission.reserve(task_id=tasks[2], provider="azure", kwargs=kwargs)
        assert refused.value.source == "grading"
        result = ledger.snapshot()
        assert result["stop_source"] == "grading" and result["stop_reason"] == usd.CEILING
        assert Decimal(result["combined_modeled_usd"]) == Decimal("191.40192")
        assert Decimal(result["combined_modeled_usd"]) + gio + gcache == Decimal("215.10288")
        assert result["pending_requests"] == 0 and result["blocked_grading"] == 1
        request.node.user_properties.append(("usd200_worst_reservation", json.dumps({
            "solver_full_cap_attempts": 20, "settled_solver_usd": "144",
            "blocked_origin": "grading", "blocked_request_index_one_based": 3,
            "accounted_usd": "191.40192", "next_reserve_usd": "23.70096",
            "would_total_usd": "215.10288", "reason": usd.CEILING,
            "evidence": "synthetic_maximum_stress_not_normal_observed_usage",
        }, sort_keys=True)))
    finally:
        ledger.close()


def test_superseded_decision_cannot_reopen_or_refill_an_old_ledger(tmp_path, monkeypatch):
    decision = yaml.safe_load(usd.CAP_PATH.read_bytes())
    previous = decision["supersedes_monetary_decision"]
    tasks = [row["task_id"] for row in pilot.load_plan(pilot.ROOT / pilot.SOURCE_PROFILE)["dataset"]["tasks"]]
    with monkeypatch.context() as patch:
        patch.setattr(usd, "CAP_SHA256", previous["sha256"])
        patch.setattr(usd, "APPROVED_MAXIMUM_USD", Decimal(previous["previous_value"]))
        patch.setattr(usd, "price_document", lambda: deepcopy(PRICE_FIXTURE))
        old = usd.PilotUsdLedger(tmp_path, capture_sha256=CAPTURE, task_ids=tasks, create=True)
        account = old.begin("inference", tasks[0])
        ticket = old.reserve(account, Decimal(10))
        assert old.settle(ticket, Decimal(5), Decimal(0)) is None
        snapshot = old.snapshot()
        old.close()
    paths = [tmp_path / usd.DIRECTORY / name for name in (usd.IDENTITY, usd.DATABASE)]
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    assert not usd.checked_snapshot(snapshot)
    with pytest.raises(usd.PilotUsdRefused, match=usd.UNVERIFIED):
        usd.PilotUsdLedger(tmp_path, capture_sha256=CAPTURE, task_ids=tasks, create=True)
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == before
