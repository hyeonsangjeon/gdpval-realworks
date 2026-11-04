"""Approved configured route only: no provider, authentication or capability proof."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt56_pilot_deployment_binding as binding
import gpt56_pilot_wire_receipt as wire
import gpt56_pilot_usd_budget as usd
import gpt56_sol_codex_pilot_preflight as pilot
from .test_gpt56_pilot_wire_receipt import case, _session, _begin, _task, _transport, _start, _turn
from .test_gpt56_pilot_input_capture import (
    _no_execution, _offline, _parse_cache, _seed,
    capture_seed, deployment_seeds, input_seeds, no_runtime, offline_only,
    runtime_guards, source_seed,
)
from .test_gpt56_pilot_shared_usd import CONFIG

CANARY = "private-reference-value-MUST-NOT-APPEAR"


def test_actual_retained_reference_is_pinned_and_never_promotes_requested_capabilities():
    path = pilot.ROOT / binding.CONNECTION_REFERENCE_PATH
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == binding.CONNECTION_REFERENCE_SHA256
    record = binding.approved_connection_reference()
    assert record["retained_diagnostic"]["run_id"] == 39407062120
    assert record["retained_diagnostic"]["artifact_id"] == 12257312458
    assert record["retained_diagnostic"]["plan"]["sha256"] == "79145baff122ee14341d9c4930e668ddb26869a1461bbb0e0c8a0e76655e8ada"
    assert record["retained_diagnostic"]["result"]["sha256"] == "f3e9705bc1a2f934e3c5523638a127fc464bbc9be267e3bf09a38c525b7c6913"
    assert record["route"]["deployment"] == "gpt-5.6-sol"
    assert record["route"]["diagnostic_host_fingerprint"] == "sha256:69057d59166a82e3"
    old = record["historical_observation"]
    assert old["verdict"] == "connected" and old["provider_answered"] is True
    assert old["input_tokens"] == 9444 and old["output_tokens"] == 5
    assert old["cache_write_input_tokens"] == 9441 and old["reasoning_output_tokens"] == 0
    assert old["model_context_window"] == 258400
    for key in ("runtime_model", "runtime_model_provider", "served_model", "served_model_version", "reasoning_effort"):
        assert old[key] is None
    assert record["clears_only"] == [binding.CONNECTION_BLOCKER]
    for key in ("served_model_verified", "reasoning_max_verified", "long_1m_verified", "launch_authority", "new_study_or_retry_right"):
        assert record[key] is False


@pytest.mark.parametrize("requested", ["gpt-5.6-sol", "gpt-5.6-sol-fast", CANARY])
def test_observation_projection_never_fills_from_request_or_owner_inventory(requested):
    document = {"schema": "codex_foundry_connection/3",
                "settings": {"deployment": requested, "reasoning_effort": "max", "model_context_window": 1000000},
                "observed": {"runtime_model": None, "runtime_model_provider": None, "served_model": None,
                             "usage": {"model_context_window": 258400, "thread_total": {
                                 "input_tokens": 9444, "output_tokens": 5, "reasoning_output_tokens": 0}}}}
    result = binding.retained_connection_observation(document)
    assert result["served_model"] is result["served_model_version"] is result["reasoning_effort"] is None
    assert result["model_context_window"] == 258400 and result["reasoning_output_tokens"] == 0
    assert result["provider_response_body_retained"] is False
    assert requested not in json.dumps(result)


@pytest.mark.parametrize("value", [True, -1, "1000000", 1000000.0])
def test_observed_window_cannot_be_coerced(value):
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        binding.retained_connection_observation({"schema": "codex_foundry_connection/3", "observed": {
            "usage": {"model_context_window": value}}})


@pytest.mark.parametrize("damage", ["missing", "drift", "symlink"])
def test_missing_or_changed_reference_cannot_start_a_route_binding(tmp_path, monkeypatch, damage):
    real = pilot.ROOT / binding.CONNECTION_REFERENCE_PATH
    copied = tmp_path / binding.CONNECTION_REFERENCE_PATH
    copied.parent.mkdir(parents=True)
    if damage == "drift":
        copied.write_bytes(real.read_bytes() + b"\n")
    elif damage == "symlink":
        copied.symlink_to(real)
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    with pytest.raises(binding.PilotDeploymentBindingRefused) as refused:
        binding.approved_connection_reference()
    assert CANARY not in str(refused.value)


@pytest.mark.parametrize("change", ["same_account_other_host", "port", "http", "userinfo", "query", "fragment",
                                   "wrong_approved_account", "wrong_approved_deployment"])
def test_real_session_rejects_route_mismatch_before_observer_effect(case, monkeypatch, change):
    record = binding.approved_connection_reference()
    if change == "wrong_approved_account":
        record["route"]["account_resource_id_sha256"] = "0" * 64
    if change == "wrong_approved_deployment":
        record["route"]["deployment_resource_id_sha256"] = "0" * 64
    monkeypatch.setattr(binding, "approved_connection_reference", lambda: deepcopy(record))
    session = _session(case)
    endpoints = {
        "same_account_other_host": "https://fixture-foundry.cognitiveservices.azure.com/openai/v1/",
        "port": "https://fixture-foundry.services.ai.azure.com:444/openai/v1/",
        "http": "http://fixture-foundry.services.ai.azure.com/openai/v1/",
        "userinfo": "https://" + CANARY + "@fixture-foundry.services.ai.azure.com/openai/v1/",
        "query": "https://fixture-foundry.services.ai.azure.com/openai/v1/?private=" + CANARY,
        "fragment": "https://fixture-foundry.services.ai.azure.com/openai/v1/#" + CANARY,
    }
    effects = []
    def forbidden(*args, **kwargs):
        effects.append("observer construction")
        raise AssertionError("route check must precede effects")
    monkeypatch.setattr(wire, "_TransportObservation", forbidden)
    provider = SimpleNamespace(model=record["route"]["deployment"], provider_id="gdpval-foundry", reasoning_effort="max",
        model_context_window=1000000, request_max_retries=0, stream_max_retries=0, query_params={},
        auth_module=pilot.DEFAULT_AUTH_MODULE, auth_scope=pilot.DIRECT_TOKEN_SCOPE,
        endpoint=endpoints.get(change, "https://fixture-foundry.services.ai.azure.com/openai/v1/"))
    with pytest.raises(wire.PilotWireReceiptRefused) as refused:
        _begin(session, session.document["task_ids"][0], override={"provider": provider})
    assert effects == [] and session.active == {} and session.files == {}
    assert CANARY not in str(refused.value)


def test_accepted_receipt_carries_bound_reference_without_private_values(case):
    session = _session(case)
    task = session.document["task_ids"][0]
    result = _task(session, task)
    receipt = json.loads((case.workspace / result["pilot_wire_receipt"]["path"]).read_bytes())
    proof = receipt["approved_connection_reference"]
    assert proof["configured_route_matched"] is True
    assert proof["diagnostic_run_id"] == 39407062120 and proof["artifact_id"] == 12257312458
    assert proof["sha256"] == binding.CONNECTION_REFERENCE_SHA256
    assert proof["served_model_verified"] is proof["reasoning_max_verified"] is proof["long_1m_verified"] is False
    public = json.dumps(proof)
    assert "fixture-foundry" not in public and "/subscriptions/" not in public and "https://" not in public
    assert session.bound_connections == {}


def test_bound_receipt_metadata_cannot_be_forged_after_admission(case):
    session = _session(case)
    task = session.document["task_ids"][0]
    observer = _begin(session, task)
    fake = _transport(observer)
    _start(fake); _turn(fake)
    session.bound_connections[task] = wire._bytes({"private": CANARY})
    with pytest.raises(wire.PilotWireReceiptRefused) as refused:
        session.finish_task(observer, success=True, thread_id=fake.thread_id, turn_id=fake.turn_id)
    assert session.files == {} and CANARY not in str(refused.value)


def test_reference_drift_after_admission_is_refused_before_receipt(case, monkeypatch):
    session = _session(case)
    task = session.document["task_ids"][0]
    observer = _begin(session, task)
    fake = _transport(observer)
    _start(fake); _turn(fake)
    changed = deepcopy(session.connection_reference)
    changed["route"]["host_sha256"] = "0" * 64
    monkeypatch.setattr(binding, "approved_connection_reference", lambda: changed)
    with pytest.raises(wire.PilotWireReceiptRefused):
        session.finish_task(observer, success=True, thread_id=fake.thread_id, turn_id=fake.turn_id)
    assert session.files == {} and session.failed is True


def test_public_reference_prices_are_the_grading_list_price():
    # Owner decision 2026-10-30: no settled tariff is no longer a refusal. Sol is
    # booked at the published long-context Standard Global meter (not a tariff).
    assert usd.grading_prices(CONFIG)["gpt-5.6-sol"] == usd.SOL_LIST_USD_PER_MILLION


def test_connection_cli_failure_never_echoes_a_private_path(capsys):
    assert pilot.main(["--plan", "/missing/" + CANARY,
                       "--retained-connection-reference", "/private/" + CANARY]) == 2
    output = capsys.readouterr().out
    assert CANARY not in output
    assert json.loads(output)["approved_connection_gate"]["refusal_code"] == "approved_connection_reference_refused"
