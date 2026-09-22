"""Keep one Foundry-only Sol contract without claiming a served capability."""

import json
import os
import shutil
import socket
import subprocess
from copy import deepcopy
from dataclasses import fields
from types import SimpleNamespace

import pytest

from core import azure_ai_clients, codex_azure_token, codex_runtime_config
from core.codex_runtime_config import (
    CodexProviderConfigurationError,
    CodexProviderSettings,
    resolve_endpoint_setting,
)
from core.experiment_config import ExperimentConfig
import gpt56_sol_codex_pilot_preflight as preflight
from gpt56_sol_codex_pilot_preflight import (
    ACTIVE_PLAN,
    BASELINE,
    ENVELOPE,
    EVIDENCE_SOURCES,
    HISTORICAL_PLAN,
    LAUNCH_BLOCKERS,
    PLAN,
    REQUIRED_SOURCES,
    ROOT,
    RUN_ID,
    inspect_plan,
    load_plan,
    main,
)

PLAN_READER_SOURCE = "batch-runner/gpt54_comparison_preflight.py"
ADDED_SOURCES = (
    *sorted(EVIDENCE_SOURCES),
    HISTORICAL_PLAN,
    "batch-runner/gpt56_sol_codex_pilot_preflight.py",
    "batch-runner/core/agentic_v2_preregistration.py",
    "batch-runner/core/execution_envelope_tasks.py",
    "batch-runner/core/azure_ai_clients.py",
    "batch-runner/core/codex_azure_token.py",
    "batch-runner/requirements.txt",
)


@pytest.fixture
def offline_only(monkeypatch):
    """No subprocess, network, live credential lookup, or provider client."""
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("forbidden boundary")
        raise AssertionError("offline preregistration crossed an execution boundary")

    for name in ("Popen", "run", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    for module in (azure_ai_clients, codex_azure_token):
        monkeypatch.setattr(module, "DefaultAzureCredential", forbidden)
        monkeypatch.setattr(module, "get_bearer_token_provider", forbidden)
    for name in ("OpenAI", "AzureOpenAI", "AzureAIClientFactory"):
        monkeypatch.setattr(azure_ai_clients, name, forbidden)
    monkeypatch.setattr(codex_azure_token, "acquire_token", forbidden)
    # Only the non-secret argv builder is exercised, never live sign-in discovery.
    monkeypatch.setattr(codex_runtime_config, "discover_azure_cli_config_dir", lambda *_: None)
    yield calls
    assert calls == []


@pytest.mark.parametrize(
    "path,value",
    [
        ((), None),
        (("identity", "model"), "gpt-5.6-sol-fast"),
        (("identity", "model"), "gpt-6-astra"),
        (("identity", "model"), "gpt-5.4"),
        (("identity", "provider"), "openai"),
        (("identity", "provider"), "github_copilot"),
        (("identity", "provider"), "azure_openai"),
        (("identity", "fast_mode"), True),
        (("identity", "harness"), "copilot_cli"),
        (("identity", "reasoning_effort"), "xhigh"),
        (("identity", "context_tier"), "standard"),
        (("identity", "nominal_context_tokens"), 272000),
        (("identity", "cli_version"), "unreviewed"),
        (("identity", "automatic_fallback_allowed"), True),
        (("identity", "fallbacks"), ["gpt-6-astra"]),
        (("identity", "verified_route"), "an_unverified_claim"),
        (("identity", "verified_model_id"), "gpt-5.6-sol"),
        (("identity", "verified_context_tokens"), 1000000),
        (("foundry_route", "execution_mode"), "openai"),
        (("foundry_route", "route_profile"), "legacy-rollback"),
        (("foundry_route", "endpoint_from_route"), False),
        (("foundry_route", "provider_id"), "github-copilot"),
        (("foundry_route", "auth_module"), "copilot_auth_bridge"),
        (("foundry_route", "auth_module"), "personal_openai_auth"),
        (("foundry_route", "auth_scope"), "unreviewed-audience"),
        (("foundry_route", "credential_policy"), "api_key"),
        (("foundry_route", "require_expected_identities"), False),
        (("foundry_route", "endpoint"), "https://guessed.invalid/openai/v1/"),
        *[
            pytest.param(("foundry_identity", key), "self-asserted", id=f"no-unverified-{key}")
            for key in ("account", "project", "deployment", "served_model", "served_model_version",
                        "identity_evidence_sha256", "capability_evidence_sha256")
        ],
        (("codex_request",), {}),
        (("codex_request", "reasoning_effort"), "xhigh"),
        (("codex_request", "model_context_window"), None),
        (("codex_request", "model_context_window"), "1000000"),
        (("codex_request", "model_context_window"), 999999),
        (("dataset", "tasks"), "reverse_tasks"),
        (("dataset", "tasks", 0, "prompt_sha256"), "0" * 64),
        (("dataset", "input_file_versions"), {}),
        (("developer_instructions",), "A different instruction."),
        (("pilot", "task_count"), 220),
        (("pilot", "run_id"), "gpt56_sol_copilot_codex_pilot5_v1"),
        (("pilot", "full_220_enabled"), True),
        (("pilot", "auto_escalation"), True),
        (("pilot", "repeats"), 2),
        (("pilot", "relay_max_runs"), 10),
        (("limits", "infrastructure_retries_per_task"), 4),
        (("limits", "request_max_retries"), 1),
        (("limits", "logical_turns_per_attempt"), 2),
        (("limits", "timeout_seconds_per_attempt"), 1801),
        (("limits", "native_output_tokens_per_attempt"), 0),
        (("limits", "inactive_generic_token_settings", "code_generation"), 1),
        (("grading", "rubric_revision"), "main"),
        (("grading", "pilot_expected_task_count"), 220),
        (("grading", "reuse_baseline_rerun_identity"), True),
        (("results", "receipt_schema"), "another-schema"),
        (("results", "projector"), "another-projector"),
        (("results", "missing_or_unpriced_usage"), "zero"),
        (("cost", "use_openai_or_copilot_tariff_for_foundry"), True),
        (("cost", "usage_adapter"), "copilot_usage"),
        (("cost", "foundry_tariff_evidence_sha256"), "0" * 64),
        (("cost", "approved_maximum_usd"), 0),
        (("source_pins",), {}),
        pytest.param(
            ("source_pins", PLAN_READER_SOURCE), "remove_pin",
            id="plan-reader-pin-required",
        ),
        pytest.param(
            ("source_pins", PLAN_READER_SOURCE), "0" * 64,
            id="plan-reader-digest-checked",
        ),
        pytest.param(
            ("source_pins", "batch-runner/step2_run_inference.py"), "remove_pin",
            id="step2-pin-required",
        ),
        pytest.param(
            ("source_pins", "batch-runner/step2_run_inference.py"), "0" * 64,
            id="step2-digest-checked",
        ),
        *[
            pytest.param(("source_pins", source), change, id=f"{source}-{change}")
            for source in ADDED_SOURCES
            for change in ("remove_pin", "0" * 64)
        ],
        (("status",), "superseded"),
        (("supersedes",), "unrelated-plan.yaml"),
        (("launch_enabled",), True),
        (("launch_allowed",), True),
        (("full_220_allowed",), True),
        (("historical_plan",), None),
        *[
            pytest.param(("registrations", case), None, id=case)
            for case in ("missing_history", "duplicate_active", "revive_history",
                         "wrong_supersession", "wrong_registered_id")
        ],
    ],
)
def test_gpt56_sol_foundry_pilot_is_pinned_and_fails_closed(
    path, value, tmp_path, capsys, monkeypatch, offline_only
):
    plan = load_plan(PLAN)
    if path == ("historical_plan",):
        plan = load_plan(ROOT / HISTORICAL_PLAN)
    elif path and path[0] == "registrations":
        # Real isolated files, not mocked validators or shared mutable state.
        repository = tmp_path / "repository"
        for name in REQUIRED_SOURCES | {ACTIVE_PLAN}:
            if path[1] == "missing_history" and name == HISTORICAL_PLAN:
                continue
            target = repository / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        if path[1] == "duplicate_active":
            shutil.copyfile(repository / ACTIVE_PLAN,
                            repository / ENVELOPE / "gpt56_sol_duplicate_codex_pilot.yaml")
        elif path[1] != "missing_history":
            target = repository / (ACTIVE_PLAN if path[1] == "wrong_registered_id" else HISTORICAL_PLAN)
            registered = load_plan(target)
            if path[1] == "revive_history":
                registered["status"] = "active"
            elif path[1] == "wrong_supersession":
                registered["superseded_by"] = "another-contract.yaml"
            else:
                registered["pilot"]["run_id"] = "another-run"
            target.write_text(json.dumps(registered), encoding="utf-8")
        monkeypatch.setattr(preflight, "ROOT", repository)
    elif path:
        target = plan
        for key in path[:-1]:
            target = target[key]
        if value == "remove_pin":
            del target[path[-1]]
        else:
            target[path[-1]] = (
                list(reversed(target[path[-1]])) if value == "reverse_tasks" else value
            )

    result = inspect_plan(plan)
    assert result["configuration_valid"] is (not path), result
    if len(path) == 2 and path[0] == "source_pins":
        assert result["configuration_problems"] == [
            "source_pin_set"
            if value == "remove_pin"
            else f"source_pin:{path[1]}"
        ]
    if path and path[0] == "registrations":
        assert any(problem in result["configuration_problems"] for problem in (
            "pilot_registration_set", "active_pilot_identity", "historical_pilot_not_retired",
        ))
    assert result["launch_allowed"] is False
    assert result["full_220_allowed"] is False
    assert result["launch_blockers"] == list(LAUNCH_BLOCKERS)
    assert not any("copilot" in blocker for blocker in result["launch_blockers"])
    assert result["requested_codex_config_overrides"] == (
        None if path else [
            'model_reasoning_effort="max"', "model_context_window=1000000"
        ]
    )

    plan_path = ROOT / HISTORICAL_PLAN if path == ("historical_plan",) else tmp_path / "plan.yaml"
    if path != ("historical_plan",):
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["--plan", str(plan_path)]) == 2
    assert json.loads(capsys.readouterr().out) == result

    if not path:
        assert main([]) == 2
        assert json.loads(capsys.readouterr().out) == result
        assert len(REQUIRED_SOURCES) == 58
        assert set(plan["source_pins"]) == REQUIRED_SOURCES
        assert PLAN_READER_SOURCE in REQUIRED_SOURCES
        assert PLAN_READER_SOURCE in plan["source_pins"]
        registrations = [load_plan(file) for file in (ROOT / ENVELOPE).glob("gpt56_sol_*_codex_pilot.yaml")]
        assert [record["pilot"]["run_id"] for record in registrations if record["status"] == "active"] == [RUN_ID]
        historical = load_plan(ROOT / HISTORICAL_PLAN)
        assert historical["status"] == "superseded"
        assert historical["superseded_by"] == ACTIVE_PLAN
        assert historical["launch_enabled"] is historical["pilot"]["full_220_enabled"] is False
        # Preserve all existing task/content, deliverable/result, grader and limits.
        for section in ("dataset", "developer_instructions", "limits", "grading", "results", "codex_request"):
            assert plan[section] == historical[section]
        assert {key: value for key, value in plan["pilot"].items() if key != "run_id"} == {
            key: value for key, value in historical["pilot"].items() if key != "run_id"
        }
        # These are real adapter/config checks, with no SDK or auth execution.
        baseline = ExperimentConfig.from_yaml(str(ROOT / BASELINE))
        assert baseline.validate() == []
        configured = deepcopy(baseline)
        configured.condition_a.model.deployment = "fixture-reviewed-sol-deployment"
        configured.execution.codex.update({
            "model": configured.condition_a.model.deployment,
            "provider_id": plan["foundry_route"]["provider_id"],
            **plan["codex_request"],
        })
        assert configured.validate() == []
        for provider_name in ("github_copilot", "openai"):
            configured.condition_a.model.provider = provider_name
            assert any("provider" in error for error in configured.validate())
        configured.condition_a.model.provider = "azure"
        route = {
            "AZURE_AI_ROUTE_PROFILE": plan["foundry_route"]["route_profile"],
            "AZURE_OPENAI_V1_ENDPOINT": "https://fixture.openai.azure.com/openai/v1/",
            "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": "fixture",
            "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES": "1",
        }
        provider = CodexProviderSettings(
            endpoint=resolve_endpoint_setting(configured.execution.codex, route),
            model=configured.execution.codex["model"],
            **plan["codex_request"],
        )
        assert provider.auth_module == plan["foundry_route"]["auth_module"]
        assert provider.auth_scope == plan["foundry_route"]["auth_scope"]
        overrides = provider.config_overrides()
        assert overrides[-2:] == ('model_reasoning_effort="max"', "model_context_window=1000000")
        assert 'model_providers.gdpval-foundry.wire_api="responses"' in overrides
        assert any("codex_azure_token.py" in value and provider.auth_scope in value for value in overrides)
        # The auth argv contains the checkout path, which may itself include
        # "copilot". Provider/auth identity comes from fields, not path words.
        assert provider.provider_id == plan["foundry_route"]["provider_id"] == "gdpval-foundry"
        assert all(value.startswith("model_providers.gdpval-foundry.") for value in overrides[:-2])
        assert not any(".api_key=" in value or ".env_key=" in value for value in overrides)
        with pytest.raises(CodexProviderConfigurationError):
            resolve_endpoint_setting(configured.execution.codex, {})
        for endpoint in ("https://copilot.fixture.invalid/openai/v1/", "https://api.openai.com/v1/"):
            with pytest.raises(CodexProviderConfigurationError):
                CodexProviderSettings(endpoint=endpoint, model="gpt-5.6-sol")
        provider_fields = {field.name for field in fields(CodexProviderSettings)}
        assert {"reasoning_effort", "model_context_window"} <= provider_fields
        assert "context_tier" not in provider_fields
        assert {
            "foundry_account_project_deployment_identity_unverified",
            "foundry_served_model_version_unverified",
            "max_and_long_1m_capability_unverified",
            "native_call_and_token_limits_unresolved",
            "prepared_input_bytes_unverified",
            "live_inference_identity_and_wire_unverified",
            "pilot_dispatch_and_grading_identity_not_wired",
            "foundry_usage_and_tariff_mapping_unverified",
            "native_sandbox_and_result_bundle_host_unverified",
            "actual_pilot_deployment_not_prepared",
        } <= set(result["launch_blockers"])
        assert offline_only == []


@pytest.fixture(scope="module")
def runtime_caps_usage_seed(tmp_path_factory):
    # Late imports avoid the existing fixture modules' plan-reader cycle.
    # Only immutable byte tuples are shared; every case copies fresh files.
    from . import test_gpt56_pilot_wire_receipt as wire_cases

    evidence_bytes = wire_cases._seed.__wrapped__()
    source_bytes = wire_cases.source_seed.__wrapped__()
    input_factory = wire_cases.input_seeds.__wrapped__(tmp_path_factory, source_bytes, evidence_bytes)
    deployment_factory = wire_cases.deployment_seeds.__wrapped__(tmp_path_factory, input_factory, evidence_bytes)
    return wire_cases.capture_seed.__wrapped__(tmp_path_factory, deployment_factory)


@pytest.fixture(scope="module")
def runtime_caps_usage_parse_cache():
    from . import test_gpt56_pilot_wire_receipt as wire_cases

    return wire_cases._parse_cache.__wrapped__()


@pytest.fixture
def runtime_caps_usage_offline(monkeypatch, offline_only, runtime_caps_usage_parse_cache):
    from . import test_gpt56_pilot_wire_receipt as wire_cases
    import gpt56_pilot_runtime_caps_usage as caps

    # Keep all existing network, auth, client and grader construction guards.
    # The cache parses current bytes and never memoizes a verifier's verdict.
    wire_cases._offline.__wrapped__(monkeypatch, offline_only, runtime_caps_usage_parse_cache)
    wire_cases._no_execution.__wrapped__(None, monkeypatch, offline_only)
    wire_cases.no_runtime.__wrapped__(None, monkeypatch, offline_only)
    wire_cases.runtime_guards.__wrapped__(None, monkeypatch, offline_only)
    return wire_cases, caps


@pytest.fixture
def runtime_caps_usage_case(runtime_caps_usage_offline, runtime_caps_usage_seed, tmp_path, monkeypatch):
    wire_cases, _ = runtime_caps_usage_offline
    return wire_cases._fresh(runtime_caps_usage_seed, tmp_path, monkeypatch)


def test_runtime_caps_usage_active_contract_and_offline_gates_keep_unobserved_requirements(
    runtime_caps_usage_case, runtime_caps_usage_offline,
):
    case = runtime_caps_usage_case
    plan_only = inspect_plan(case.plan)
    complete = inspect_plan(case.plan, **vars(case.context), capture_workspace=case.workspace)
    assert plan_only["configuration_valid"] is complete["configuration_valid"] is True
    assert plan_only["launch_blockers"] == list(LAUNCH_BLOCKERS)
    assert complete["launch_blockers"] == [
        "native_call_and_token_limits_unresolved", "live_inference_identity_and_wire_unverified",
        "foundry_usage_and_tariff_mapping_unverified", LAUNCH_BLOCKERS[8],
    ]
    assert set(preflight.EVIDENCE_BLOCKER_ROLES) == set(LAUNCH_BLOCKERS[:3])
    assert preflight.EVIDENCE_INTAKE["required_roles"] == [
        "identity", "reasoning", "context", "native_caps", "usage", "tariff",
    ]
    assert case.plan["runtime_caps_usage"] == preflight.RUNTIME_CAPS_USAGE
    assert preflight.RUNTIME_CAPS_USAGE["recorder"] in REQUIRED_SOURCES
    assert len(REQUIRED_SOURCES) == 58
    assert preflight.RUNTIME_CAPS_USAGE["requires_live_host_session_witness"] is True
    assert preflight.RUNTIME_CAPS_USAGE["offline_preflight_consumption"] is False
    assert preflight.RUNTIME_CAPS_USAGE["clears_native_call_or_billing_blockers"] is False
    assert case.plan["launch_enabled"] is case.plan["pilot"]["full_220_enabled"] is False
    for report in (plan_only, complete):
        assert report["launch_allowed"] is report["full_220_allowed"] is False


def _runtime_caps_usage_transport(modules):
    wire_cases, caps = modules
    # A bounded owner stand-in for the pure notification validator, never a
    # receipt witness. Integration cases below use the actual session owner.
    owner = SimpleNamespace(
        approved_limits={"model_calls": 16, "input_tokens": 2_000_000, "output_tokens": 64_000},
        wire=SimpleNamespace(document={"requested": {"context_tokens": 1_000_000}}), failed=False,
    )
    owner._poison = lambda: setattr(owner, "failed", True)
    observer = wire_cases.wire._TransportObservation(deepcopy(wire_cases.REQUESTED))
    observer.caps_usage_observer = caps._UsageObservation(owner, observer)
    fake = wire_cases._transport(observer)
    wire_cases._start(fake)
    return fake, owner


@pytest.mark.parametrize("change", ["partial", "null-context", "absent-context", "all-fields", "exact-input-cap", "exact-output-cap"])
def test_runtime_caps_usage_observed_boundaries_preserve_null_absent_and_native_snapshots(
    runtime_caps_usage_offline, change,
):
    wire_cases, _ = runtime_caps_usage_offline
    fake, owner = _runtime_caps_usage_transport(runtime_caps_usage_offline)
    usage = deepcopy(wire_cases.USAGE)
    if change == "null-context":
        usage["modelContextWindow"] = None
    elif change == "absent-context":
        del usage["modelContextWindow"]
    elif change == "all-fields":
        usage["total"].update(cachedInputTokens=20, cacheWriteInputTokens=3, reasoningOutputTokens=4)
        usage["last"].update(cachedInputTokens=2, cacheWriteInputTokens=1, reasoningOutputTokens=2)
    elif change == "exact-input-cap":
        usage["total"].update(inputTokens=2_000_000, totalTokens=2_000_009)
    elif change == "exact-output-cap":
        usage["total"].update(outputTokens=64_000, totalTokens=64_071)
    wire_cases._turn(fake, usage=usage)
    wire_cases._finish(fake)
    record = fake.observer.caps_usage_observer.verified()
    assert [row["native"] for row in record["snapshots"]] == [usage]
    assert record["source"] == "app_server_thread_usage_not_provider_billing"
    assert record["counter_semantics"] == "total_cumulative_per_thread_last_latest_model_request"
    assert record["unit"] == "tokens" and owner.failed is False
    assert fake.observer.usage[0]["native"] == usage


@pytest.mark.parametrize("change", [
    "missing", "missing-total", "missing-input", "missing-output", "missing-sum", "null-input", "null-output",
    "negative", "boolean", "string", "input-cap", "output-cap", "context", "total-too-small", "total-inconsistent",
    "cached-too-large", "cache-write-too-large", "reasoning-too-large", "last-too-large", "unknown-quantity",
    "currency", "private-value", "model-call-count",
])
def test_runtime_caps_usage_missing_inconsistent_over_cap_or_private_usage_refuses(
    runtime_caps_usage_offline, capsys, change,
):
    wire_cases, caps = runtime_caps_usage_offline
    fake, owner = _runtime_caps_usage_transport(runtime_caps_usage_offline)
    usage = deepcopy(wire_cases.USAGE)
    if change == "missing":
        usage = None
    elif change == "missing-total":
        del usage["total"]
    elif change in ("missing-input", "missing-output", "missing-sum"):
        del usage["total"][{"missing-input": "inputTokens", "missing-output": "outputTokens", "missing-sum": "totalTokens"}[change]]
    elif change in ("null-input", "null-output"):
        usage["total"]["inputTokens" if change == "null-input" else "outputTokens"] = None
    elif change in ("negative", "boolean", "string", "private-value"):
        usage["total"]["inputTokens"] = {"negative": -1, "boolean": True, "string": "71", "private-value": wire_cases.PRIVATE_TEXT}[change]
    elif change == "input-cap":
        usage["total"].update(inputTokens=2_000_001, totalTokens=2_000_010)
    elif change == "output-cap":
        usage["total"].update(outputTokens=64_001, totalTokens=64_072)
    elif change == "context":
        usage["modelContextWindow"] = 999_999
    elif change == "total-too-small":
        usage["total"]["totalTokens"] = 70
    elif change == "total-inconsistent":
        usage["total"]["totalTokens"] = 81
    elif change == "cached-too-large":
        usage["total"]["cachedInputTokens"] = 72
    elif change == "cache-write-too-large":
        usage["total"]["cacheWriteInputTokens"] = 72
    elif change == "reasoning-too-large":
        usage["total"]["reasoningOutputTokens"] = 10
    elif change == "last-too-large":
        usage["last"]["inputTokens"] = 72
    elif change == "model-call-count":
        usage["modelCalls"] = 1
    else:
        usage["quantity" if change == "unknown-quantity" else "currency"] = 100 if change == "unknown-quantity" else "USD"
    with pytest.raises((wire_cases.wire.PilotWireReceiptRefused, caps.PilotRuntimeCapsUsageRefused)) as refusal:
        wire_cases._turn(fake, usage=usage)
        wire_cases._finish(fake)
    assert str(refusal.value) in (wire_cases.wire.REFUSAL, caps.REFUSAL)
    assert refusal.value.__suppress_context__ and fake.observer.invalid
    output = capsys.readouterr()
    assert wire_cases.PRIVATE_TEXT not in output.out + output.err + str(refusal.value)


@pytest.mark.parametrize("field", ["inputTokens", "cachedInputTokens", "cacheWriteInputTokens", "outputTokens", "reasoningOutputTokens", "totalTokens"])
@pytest.mark.parametrize("gap", [False, True])
def test_runtime_caps_usage_cumulative_counters_cannot_decrease_even_across_null_gap(
    runtime_caps_usage_offline, field, gap,
):
    wire_cases, caps = runtime_caps_usage_offline
    fake, _ = _runtime_caps_usage_transport(runtime_caps_usage_offline)
    usage = deepcopy(wire_cases.USAGE)
    usage["total"].update(cachedInputTokens=20, cacheWriteInputTokens=3, reasoningOutputTokens=4)
    wire_cases._turn(fake, usage=usage)
    if gap:
        middle = deepcopy(usage)
        # Required totals cannot disappear; optional subcounts remain nullable.
        if field not in ("inputTokens", "outputTokens", "totalTokens"):
            middle["total"][field] = None
        fake.client._coerce_notification("thread/tokenUsage/updated", {
            "threadId": fake.thread_id, "turnId": fake.turn_id, "tokenUsage": middle,
        })
    changed = deepcopy(usage)
    changed["total"][field] -= 1
    if field in ("inputTokens", "outputTokens"):
        changed["total"]["totalTokens"] -= 1
    with pytest.raises((wire_cases.wire.PilotWireReceiptRefused, caps.PilotRuntimeCapsUsageRefused)):
        fake.client._coerce_notification("thread/tokenUsage/updated", {
            "threadId": fake.thread_id, "turnId": fake.turn_id, "tokenUsage": changed,
        })
    assert fake.observer.invalid


def test_runtime_caps_usage_monotonic_totals_do_not_sum_snapshots_or_last_values(runtime_caps_usage_offline):
    wire_cases, _ = runtime_caps_usage_offline
    fake, _ = _runtime_caps_usage_transport(runtime_caps_usage_offline)
    first, later = deepcopy(wire_cases.USAGE), deepcopy(wire_cases.USAGE)
    later["total"].update(inputTokens=100, outputTokens=12, totalTokens=112)
    later["last"] = {"inputTokens": 8, "outputTokens": 1}
    wire_cases._turn(fake, usage=first)
    fake.client._coerce_notification("thread/tokenUsage/updated", {
        "threadId": fake.thread_id, "turnId": fake.turn_id, "tokenUsage": later,
    })
    wire_cases._finish(fake)
    observed = fake.observer.caps_usage_observer.verified()
    assert [row["native"] for row in observed["snapshots"]] == [first, later]
    assert observed["snapshots"][-1]["native"]["total"]["totalTokens"] == 112
    assert "model_call_count" not in observed and "price" not in observed and "cost" not in observed


@pytest.mark.parametrize("change", ["different-observer", "snapshot-drift", "wire-snapshot-drift", "duplicate-finish", "unsealed", "wrong-thread", "wrong-turn"])
def test_runtime_caps_usage_observation_is_owned_and_single_use(runtime_caps_usage_offline, change):
    wire_cases, caps = runtime_caps_usage_offline
    fake, _ = _runtime_caps_usage_transport(runtime_caps_usage_offline)
    wire_cases._turn(fake)
    observed = fake.observer.caps_usage_observer
    if change in ("wrong-thread", "wrong-turn"):
        fake.observer.usage[0]["thread_id_sha256" if change == "wrong-thread" else "turn_id_sha256"] = "f" * 64
    elif change == "wire-snapshot-drift":
        fake.observer.usage[0]["native"]["total"]["inputTokens"] = 72
    elif change == "snapshot-drift":
        observed.snapshots[0] += b" "
    with pytest.raises((wire_cases.wire.PilotWireReceiptRefused, caps.PilotRuntimeCapsUsageRefused)):
        if change == "different-observer":
            observed.finish(wire_cases.wire._TransportObservation(deepcopy(wire_cases.REQUESTED)))
        elif change == "unsealed":
            observed.verified()
        elif change == "duplicate-finish":
            wire_cases._finish(fake)
            observed.finish(fake.observer)
        else:
            wire_cases._finish(fake)


def test_runtime_caps_usage_five_real_attempts_bind_accepted_results_and_publish_ready_last(
    runtime_caps_usage_case, runtime_caps_usage_offline, monkeypatch, capsys,
):
    case = runtime_caps_usage_case
    wire_cases, caps = runtime_caps_usage_offline
    host = wire_cases.native.PilotNativeResultHostSession(wire_cases._session(case))
    owner = host.runtime_caps_usage
    writes, write = [], wire_cases.wire._write_no_clobber

    def tracked(path, data):
        if path.parent == owner.root:
            assert not (owner.root / caps.READY_PATH).exists()
            if path.name == caps.READY_PATH:
                assert host.ready is not None and len(host.results) == 2
                assert len(owner.files) == len(wire_cases.TASK_IDS)
            writes.append(path.name)
        write(path, data)

    monkeypatch.setattr(wire_cases.wire, "_write_no_clobber", tracked)
    payload = wire_cases._native_payload(case, host)
    saved = wire_cases._native_publish(case, host, payload)
    document = caps.verify_pilot_runtime_caps_usage(owner)
    assert owner.ready == caps._bytes(document)
    assert writes == [*owner.files, caps.READY_PATH]
    assert document["task_ids"] == wire_cases.TASK_IDS and document["run_id"] == RUN_ID
    assert document["prepared_capture"] == host.wire.linkage
    assert document["accepted_results"] == {
        path.name: {**caps._digest(data), "result_fingerprint": saved["result_fingerprint"]}
        for path, data in host.results.items()
    }
    assert document["remaining_launch_blockers"] == list(caps.BLOCKERS) and document["cleared_blockers"] == []
    assert document["cost"] is None and document["cost_state"] == "partial"
    assert document["thread_count"] == document["turn_count"] == 5
    assert document["infrastructure_retry_count"] == 0
    assert document["count_boundary"] == "app_server_sessions_not_model_calls"
    for field in ("model_call_count", "native_spend_enforcement", "foundry_http_payload", "foundry_request_id",
                  "served_model", "served_model_version", "served_deployment", "billing_quantity", "currency_conversion"):
        assert document["not_available"][field] == wire_cases.wire._unavailable()
    evidence_document = json.loads((case.context.evidence_bundle / "foundry-pilot-evidence-ready.json").read_bytes())
    reviewed = document["reviewed_evidence"]
    for role in ("native_caps", "usage", "tariff"):
        raw = (case.context.evidence_bundle / "artifacts" / (role + ".json")).read_bytes()
        assert reviewed["roles"][role] == caps._digest(raw)
    assert reviewed["approved_limits"] == {"model_calls": 16, "input_tokens": 2_000_000, "output_tokens": 64_000}
    assert reviewed["meter_ids"] == {
        name: meter["meter_id"] for name, meter in evidence_document["claims"]["usage"]["evidence"]["observed"]["meters"].items()
    }
    for index, task_id in enumerate(wire_cases.TASK_IDS):
        entries = document["receipts"][task_id]
        assert len(entries) == 1 and entries[0]["attempt_index"] == 0
        receipt = json.loads((case.workspace / entries[0]["path"]).read_bytes())
        assert receipt["task_id"] == task_id and receipt["task_index"] == index
        assert receipt["task_order"] == wire_cases.TASK_IDS and receipt["logical_turn"] == 1
        assert receipt["retry_kind"] == "initial" and receipt["attempt_index"] == 0
        assert receipt["infrastructure_retry_count"] == 0
        assert receipt["thread_count"] == receipt["turn_count"] == 1
        assert receipt["prepared_capture"] == host.wire.linkage
        assert receipt["usage"]["snapshots"][0]["native"] == wire_cases.USAGE
        assert receipt["reviewed_evidence"] == reviewed
        assert receipt["launch_allowed"] is receipt["full_220_allowed"] is False
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    public = owner.reservation + owner.ready + b"".join(owner.files.values())
    for private in (wire_cases.PRIVATE_TEXT.encode(), wire_cases.PRIVATE.encode(), str(case.parent).encode(), *wire_cases.RAW_IDS):
        assert private not in public
    for key in (b'"quantity"', b'"amount"', b'"currency"', b'"endpoint"', b'"token"', b'"Authorization"'):
        assert key not in public
    assert all(path.stat().st_nlink == 1 and not path.is_symlink() for path in owner.root.iterdir())
    assert capsys.readouterr().out == ""
    # Files alone never become a live owner, even if they are canonical.
    for forged in (None, document, owner.ready, owner.root, SimpleNamespace(ready=owner.ready)):
        with pytest.raises(caps.PilotRuntimeCapsUsageRefused, match="^pilot_runtime_caps_usage_refused$"):
            caps.verify_pilot_runtime_caps_usage(forged)
    # Current saved-output bytes are part of verification, not just old hashes.
    output = next(iter(host.results))
    output.write_bytes(output.read_bytes() + b" ")
    with pytest.raises(caps.PilotRuntimeCapsUsageRefused):
        caps.verify_pilot_runtime_caps_usage(owner)
    assert owner.failed and host.failed and host.wire.failed


@pytest.mark.parametrize("change", ["wrong-first-task", "wrong-run", "skipped-retry", "boolean-retry", "negative-retry", "above-retry-cap"])
def test_runtime_caps_usage_attempt_order_and_retry_identity_refuse(runtime_caps_usage_case, runtime_caps_usage_offline, change):
    wire_cases, caps = runtime_caps_usage_offline
    host = wire_cases.native.PilotNativeResultHostSession(wire_cases._session(runtime_caps_usage_case))
    with pytest.raises((wire_cases.wire.PilotWireReceiptRefused, caps.PilotRuntimeCapsUsageRefused)):
        if change == "wrong-run":
            wire_cases._begin(host.wire, wire_cases.TASK_IDS[0], override={"run_id": "another-run"})
        elif change == "wrong-first-task":
            host.wire.arm_task(wire_cases.TASK_IDS[1], 0)
        else:
            attempt = {"skipped-retry": 1, "boolean-retry": True, "negative-retry": -1, "above-retry-cap": 4}[change]
            host.wire.arm_task(wire_cases.TASK_IDS[0], attempt)
    assert not host.runtime_caps_usage.files


def test_runtime_caps_usage_infrastructure_retry_is_not_model_calls_and_cannot_replay(
    runtime_caps_usage_case, runtime_caps_usage_offline,
):
    case = runtime_caps_usage_case
    wire_cases, caps = runtime_caps_usage_offline
    host = wire_cases.native.PilotNativeResultHostSession(wire_cases._session(case))
    for attempt in (0, 1, 2, 3):
        state = wire_cases._native_start(case, host, attempt=attempt)
        result = wire_cases._native_finish(state, success=attempt == 3)
        wire_cases._native_accept(case, state, result)
    receipts = [json.loads(data) for data in host.runtime_caps_usage.files.values()]
    assert [row["attempt_index"] for row in receipts] == [0, 1, 2, 3]
    assert [row["infrastructure_retry_count"] for row in receipts] == [0, 1, 2, 3]
    assert [row["retry_kind"] for row in receipts] == ["initial", "infrastructure", "infrastructure", "infrastructure"]
    assert [row["step2_status"] for row in receipts] == ["error", "error", "error", "success"]
    assert all(row["not_available"]["model_call_count"] == wire_cases.wire._unavailable() for row in receipts)
    with pytest.raises(caps.PilotRuntimeCapsUsageRefused):
        host.runtime_caps_usage.record_step2_result(state.witness)
    assert host.runtime_caps_usage.failed and host.failed and host.wire.failed


@pytest.mark.parametrize("change", ["directory", "reservation", "symlink-directory", "symlink-reservation", "hardlink-reservation"])
def test_runtime_caps_usage_existing_partial_or_link_is_never_adopted(
    runtime_caps_usage_case, runtime_caps_usage_offline, change,
):
    case = runtime_caps_usage_case
    wire_cases, caps = runtime_caps_usage_offline
    root, reserved = case.workspace / caps.DIRECTORY, case.workspace / caps.RESERVATION
    if change == "directory":
        root.mkdir()
    elif change == "reservation":
        reserved.write_bytes(b"{}")
    elif change == "symlink-directory":
        root.symlink_to(case.parent, target_is_directory=True)
    else:
        source = case.parent / "private-caps-reservation.json"
        source.write_bytes(b"{}")
        if change == "symlink-reservation":
            reserved.symlink_to(source)
        else:
            os.link(source, reserved)
    before = os.path.lexists(root), os.path.lexists(reserved)
    session = wire_cases._session(case)
    with pytest.raises(wire_cases.native.PilotNativeResultHostRefused) as refusal:
        wire_cases.native.PilotNativeResultHostSession(session)
    assert (os.path.lexists(root), os.path.lexists(reserved)) == before
    assert not (root / caps.READY_PATH).exists()
    assert str(case.parent) not in str(refusal.value) and session.failed


@pytest.mark.parametrize("change", ["capture", "prepared", "native_caps", "usage", "tariff", "forged-limit", "forged-meter", "missing-owner", "duplicate-owner"])
def test_runtime_caps_usage_upstream_and_reviewed_mapping_drift_refuses_before_transport(
    runtime_caps_usage_case, runtime_caps_usage_offline, change,
):
    case = runtime_caps_usage_case
    wire_cases, caps = runtime_caps_usage_offline
    host = wire_cases.native.PilotNativeResultHostSession(wire_cases._session(case))
    owner = host.runtime_caps_usage
    if change in ("capture", "prepared"):
        path = case.workspace / (wire_cases.capture.CAPTURE_PATH if change == "capture" else wire_cases.capture.PREPARED_PATH)
        path.write_bytes(path.read_bytes() + b" ")
    elif change in ("native_caps", "usage", "tariff"):
        path = case.context.evidence_bundle / "artifacts" / (change + ".json")
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "forged-limit":
        owner.approved_limits["input_tokens"] += 1
    elif change == "forged-meter":
        owner.reviewed_evidence["meter_ids"]["input_tokens"] = "00000000-0000-0000-0000-000000000099"
    elif change == "missing-owner":
        host.runtime_caps_usage = None
    with pytest.raises((wire_cases.wire.PilotWireReceiptRefused, caps.PilotRuntimeCapsUsageRefused)) as refusal:
        if change == "duplicate-owner":
            caps.PilotRuntimeCapsUsageSession(host)
        else:
            host.wire.arm_task(wire_cases.TASK_IDS[0], 0)
    assert str(refusal.value) in (wire_cases.wire.REFUSAL, caps.REFUSAL)
    assert not owner.files and not host.wire.active


@pytest.mark.parametrize("change", ["wire-bytes", "wire-link", "attempt", "result", "missing-observer", "forged-snapshot"])
def test_runtime_caps_usage_acceptance_rejects_stale_or_forged_attempts(
    runtime_caps_usage_case, runtime_caps_usage_offline, change,
):
    case = runtime_caps_usage_case
    wire_cases, _ = runtime_caps_usage_offline
    host = wire_cases.native.PilotNativeResultHostSession(wire_cases._session(case))
    state = wire_cases._native_start(case, host)
    result = wire_cases._native_finish(state)
    if change == "wire-bytes":
        path = case.workspace / state.witness.linkage["path"]
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "wire-link":
        state.witness.linkage = {**state.witness.linkage, "sha256": "0" * 64}
    elif change == "attempt":
        state.witness.attempt += 1
    elif change == "result":
        result["text"] += " forged"
    elif change == "missing-observer":
        state.observer.caps_usage_observer = None
    else:
        state.observer.usage[0]["native"]["total"]["inputTokens"] += 1
    with pytest.raises(wire_cases.native.PilotNativeResultHostRefused):
        wire_cases._native_accept(case, state, result)
    assert not host.runtime_caps_usage.files and host.failed and host.wire.failed


@pytest.mark.parametrize("change", ["partial", "hardlink", "write-failure", "mid-write-evidence", "mid-write-host"])
def test_runtime_caps_usage_publication_drift_quarantines_partials(runtime_caps_usage_case, runtime_caps_usage_offline, monkeypatch, change):
    case = runtime_caps_usage_case
    wire_cases, caps = runtime_caps_usage_offline
    host = wire_cases.native.PilotNativeResultHostSession(wire_cases._session(case))
    owner = host.runtime_caps_usage
    state = wire_cases._native_start(case, host)
    result = wire_cases._native_finish(state)
    if change == "partial":
        (owner.root / "unexpected.json").write_bytes(b"{}")
    elif change == "hardlink":
        os.link(owner.reserved, case.parent / "private-hardlink.json")
    else:
        write = wire_cases.wire._write_no_clobber

        def drift(path, data):
            write(path, data)
            if path.parent == owner.root:
                if change == "write-failure":
                    raise OSError(wire_cases.PRIVATE_TEXT)
                target = (case.context.evidence_bundle / "artifacts" / "tariff.json" if change == "mid-write-evidence"
                          else host.root / path.name)
                target.write_bytes(target.read_bytes() + b" ")

        monkeypatch.setattr(wire_cases.wire, "_write_no_clobber", drift)
    with pytest.raises(wire_cases.native.PilotNativeResultHostRefused) as refusal:
        wire_cases._native_accept(case, state, result)
    assert owner.reserved.exists() and owner.root.exists() and not (owner.root / caps.READY_PATH).exists()
    assert wire_cases.PRIVATE_TEXT not in str(refusal.value) and str(case.parent) not in str(refusal.value)
    with pytest.raises(caps.PilotRuntimeCapsUsageRefused):
        caps.verify_pilot_runtime_caps_usage(owner)


@pytest.mark.parametrize("kwargs", [{}, {"pilot_wire_receipts": None}])
def test_runtime_caps_usage_legacy_absent_null_no_owner_and_unchanged_output(runtime_caps_usage_offline, kwargs):
    wire_cases, caps = runtime_caps_usage_offline
    assert caps.runtime_caps_usage_for(None) is None
    runner = object.__new__(wire_cases.codex_runner.CodexAgentRunner)
    wire_cases.REAL_INIT(runner, object.__new__(wire_cases.CodexProviderSettings),
                        verify_runtime=False, preflight_auth=False, run_id="legacy", **kwargs)
    assert runner.pilot_wire_receipts is None
    runner.provider = SimpleNamespace(model="legacy")
    result = runner.run("text", model="different")
    assert result == runner._failure(
        "this Codex run place is configured for deployment 'legacy' and was asked for 'different'; "
        "refusing rather than calling a different model than the one the run will be recorded against",
        category="model_mismatch")
    assert "runtime_caps_usage" not in result
    fake = wire_cases._transport()
    wire_cases._start(fake)
    wire_cases._turn(fake, usage=None)
    record = wire_cases._finish(fake)
    assert fake.observer.caps_usage_observer is None and record["usage"]["snapshots"] == []


def test_runtime_caps_usage_ready_publication_drift_poisons_owner_without_deleting_quarantine(
    runtime_caps_usage_case, runtime_caps_usage_offline, monkeypatch,
):
    case = runtime_caps_usage_case
    wire_cases, caps = runtime_caps_usage_offline
    host = wire_cases.native.PilotNativeResultHostSession(wire_cases._session(case))
    owner = host.runtime_caps_usage
    payload = wire_cases._native_payload(case, host)
    write = wire_cases.wire._write_no_clobber

    def drift(path, data):
        write(path, data)
        if path == owner.root / caps.READY_PATH:
            saved = next(iter(host.results))
            saved.write_bytes(saved.read_bytes() + b" ")

    monkeypatch.setattr(wire_cases.wire, "_write_no_clobber", drift)
    with pytest.raises(wire_cases.native.PilotNativeResultHostRefused):
        wire_cases._native_publish(case, host, payload)
    assert owner.failed and host.failed and host.wire.failed
    assert owner.reserved.exists() and (owner.root / caps.READY_PATH).exists()
    with pytest.raises(caps.PilotRuntimeCapsUsageRefused):
        caps.verify_pilot_runtime_caps_usage(owner)


def _external_live_receipt_owner(case, wire_cases):
    """Build the actual owner chain with synthetic transport, never a client."""
    import gpt56_pilot_external_live_receipt as external

    host = wire_cases.native.PilotNativeResultHostSession(wire_cases._session(case))
    payload = wire_cases._native_payload(case, host)
    wire_cases._native_publish(case, host, payload)
    runtime = host.runtime_caps_usage
    snapshot = external._snapshot(runtime, reviewed_source_sha=case.context.reviewed_source_sha)
    return runtime, snapshot


def _external_live_receipt_artifact(snapshot):
    # This is synthetic input to a consistency validator, not provider evidence.
    # A provider label cannot authenticate the fixture or make it launchable.
    return {
        "schema_version": "pilot-external-live-receipt-v1",
        "binding": deepcopy(snapshot["binding"]),
        "attempts": [
            {
                "binding": deepcopy(attempt),
                "source_kind": "foundry_response_export",
                "issuer": "microsoft_foundry",
                "window_started_at": "2026-09-20T00:00:00Z",
                "window_ended_at": "2026-09-20T00:00:00Z",
                "observed_at": "2026-09-20T00:00:00Z",
                "issued_at": "2026-09-20T00:02:00Z",
                "valid_until": "2026-10-01T00:00:00Z",
                "provider_request_id_sha256": None,
                "provider_response_id_sha256": None,
                "served": None,
                "usage": None,
                "billing": None,
                "tariff": None,
            }
            for attempt in snapshot["attempt_bindings"]
        ],
    }


@pytest.fixture(scope="module")
def external_live_receipt_samples(
    runtime_caps_usage_seed, runtime_caps_usage_parse_cache, tmp_path_factory,
):
    """Share immutable inputs, not mutable owners or a cached verifier result."""
    import gpt56_pilot_external_live_receipt as external

    with pytest.MonkeyPatch.context() as setup:
        guard = offline_only.__wrapped__(setup)
        calls = next(guard)
        try:
            wire_cases, _ = runtime_caps_usage_offline.__wrapped__(
                setup, calls, runtime_caps_usage_parse_cache,
            )
            parent = tmp_path_factory.mktemp("external-live-receipt-samples")
            case = wire_cases._fresh(runtime_caps_usage_seed, parent, setup)
            _, snapshot = _external_live_receipt_owner(case, wire_cases)
            schema = (preflight.ROOT / external.evidence.SCHEMA_PATH).read_bytes()
            return (schema, external._bytes(snapshot),
                    external._bytes(_external_live_receipt_artifact(snapshot)))
        finally:
            next(guard, None)


@pytest.fixture
def external_live_receipt_documents(external_live_receipt_samples, runtime_caps_usage_offline):
    import gpt56_pilot_external_live_receipt as external

    schema, snapshot, artifact = map(json.loads, external_live_receipt_samples)
    return SimpleNamespace(module=external, schema=schema, snapshot=snapshot,
                           artifact=artifact, as_of="2026-09-20T03:00:00Z")


def _external_live_receipt_validate(sample, artifact=None, *, as_of=None):
    return sample.module._validate_artifact(
        sample.module._bytes(sample.artifact if artifact is None else artifact),
        schema=sample.schema, snapshot=sample.snapshot,
        as_of=sample.as_of if as_of is None else as_of,
    )


def test_external_live_receipt_complete_synthetic_shape_is_consistency_only(
    external_live_receipt_documents,
):
    sample = external_live_receipt_documents
    assert _external_live_receipt_validate(sample) == sample.artifact
    assert len(sample.artifact["attempts"]) == 5
    assert sample.artifact["binding"] == sample.snapshot["binding"]
    assert [row["binding"] for row in sample.artifact["attempts"]] == sample.snapshot["attempt_bindings"]
    assert all(row[name] is None for row in sample.artifact["attempts"]
               for name in ("provider_request_id_sha256", "provider_response_id_sha256",
                            "served", "usage", "billing", "tariff"))
    # A caller-authored JSON document, even with a provider label, is not a live
    # owner and cannot be used to publish or verify a receipt on its own.
    for value in (None, sample.artifact, sample.module._bytes(sample.artifact),
                  SimpleNamespace(ready=sample.module._bytes(sample.artifact))):
        with pytest.raises(sample.module.PilotExternalLiveReceiptRefused):
            sample.module.verify_pilot_external_live_receipt(value)


@pytest.mark.parametrize("change", [
    "missing-binding", "missing-attempts", "missing-attempt", "extra-attempt", "duplicate-attempt", "task-order",
    "missing-issuer", "missing-source", "null-issuer", "self-issued", "synthetic-source", "documentation",
    "missing-observed", "null-observed", "before-run", "after-run", "issued-before-observed", "future-issued",
    "expired", "invalid-date", "offset-time", "fractional-time", "wrong-version", "wrong-source-sha",
    "prompt", "output", "endpoint", "account", "project", "resource_id", "Authorization", "api_key",
    "private_path", "exception", "model_call_count", "price", "cost", "request-text", "raw-request-id",
    "raw-response-id", "provider-id-too-long", "provider-id-newline", "boolean-provider-id",
])
def test_external_live_receipt_closed_privacy_time_source_and_exact_attempt_set_refuse(
    external_live_receipt_documents, capsys, change,
):
    sample = external_live_receipt_documents
    artifact = sample.artifact
    row = artifact["attempts"][0]
    private = "Authorization: Bearer private-secret /private/receipt https://private.invalid/?token=secret"
    if change == "missing-binding":
        del artifact["binding"]
    elif change == "missing-attempts":
        del artifact["attempts"]
    elif change == "missing-attempt":
        artifact["attempts"].pop()
    elif change == "extra-attempt":
        artifact["attempts"].append(deepcopy(row))
    elif change == "duplicate-attempt":
        artifact["attempts"][1] = deepcopy(row)
    elif change == "task-order":
        artifact["attempts"].reverse()
    elif change in ("missing-issuer", "missing-source", "missing-observed"):
        del row[{"missing-issuer": "issuer", "missing-source": "source_kind",
                 "missing-observed": "observed_at"}[change]]
    elif change in ("null-issuer", "self-issued"):
        row["issuer"] = None if change == "null-issuer" else "operator"
    elif change in ("synthetic-source", "documentation"):
        row["source_kind"] = "synthetic" if change == "synthetic-source" else "documentation"
    elif change in ("null-observed", "before-run", "after-run", "invalid-date", "offset-time", "fractional-time"):
        row["observed_at"] = {
            "null-observed": None, "before-run": "2026-09-19T23:59:59Z", "after-run": "2026-09-20T00:01:01Z",
            "invalid-date": "2026-02-30T00:00:00Z", "offset-time": "2026-09-20T00:00:00+00:00",
            "fractional-time": "2026-09-20T00:00:00.001Z",
        }[change]
    elif change in ("issued-before-observed", "future-issued"):
        row["issued_at"] = "2026-09-19T23:59:59Z" if change == "issued-before-observed" else "2026-09-20T03:00:01Z"
    elif change == "expired":
        row["valid_until"] = "2026-09-20T02:59:59Z"
    elif change == "wrong-version":
        artifact["schema_version"] = "external-live-receipt-unknown"
    elif change == "wrong-source-sha":
        artifact["binding"]["reviewed_source_sha"] = "0" * 40
    elif change in ("raw-request-id", "provider-id-too-long", "provider-id-newline", "boolean-provider-id"):
        row["provider_request_id_sha256"] = {
            "raw-request-id": private, "provider-id-too-long": "a" * 65,
            "provider-id-newline": "a" * 64 + "\n", "boolean-provider-id": True,
        }[change]
    elif change == "raw-response-id":
        row["provider_response_id"] = private
    elif change == "request-text":
        row["binding"]["serialized_request"] = private
    else:
        row[change] = private
    with pytest.raises(sample.module.PilotExternalLiveReceiptRefused) as refusal:
        _external_live_receipt_validate(sample)
    assert str(refusal.value) == sample.module.REFUSAL
    output = capsys.readouterr()
    assert output.out == output.err == ""
    assert private not in str(refusal.value)


@pytest.mark.parametrize("as_of", [
    None, "", "2026-09-20", "2026-09-20T03:00:00+00:00", "2026-09-20T03:00:00Z\n",
    "2026-09-20T00:00:00Z", "2026-10-01T00:00:01Z", "private-token",
])
def test_external_live_receipt_requires_explicit_bounded_current_utc_time(
    external_live_receipt_documents, as_of,
):
    sample = external_live_receipt_documents
    with pytest.raises(sample.module.PilotExternalLiveReceiptRefused):
        sample.module._validate_artifact(sample.module._bytes(sample.artifact), schema=sample.schema,
                                         snapshot=sample.snapshot, as_of=as_of)


@pytest.mark.parametrize("data", [b"", b"[]", b"null", b"{", b"\xff", b'{"binding":{},"binding":{}}'])
def test_external_live_receipt_strict_json_rejects_duplicate_keys_and_malformed_bytes(
    external_live_receipt_documents, data,
):
    sample = external_live_receipt_documents
    with pytest.raises(sample.module.PilotExternalLiveReceiptRefused):
        sample.module._validate_artifact(data, schema=sample.schema, snapshot=sample.snapshot, as_of=sample.as_of)


def test_external_live_receipt_active_plan_keeps_all_offline_blockers_and_false_flags(
    runtime_caps_usage_case, runtime_caps_usage_offline, capsys,
):
    import gpt56_pilot_external_live_receipt as external

    case = runtime_caps_usage_case
    plan_only = inspect_plan(case.plan)
    prepared = inspect_plan(case.plan, **vars(case.context), capture_workspace=case.workspace)
    assert plan_only["configuration_valid"] is prepared["configuration_valid"] is True
    assert plan_only["launch_blockers"] == list(LAUNCH_BLOCKERS)
    assert prepared["launch_blockers"] == [LAUNCH_BLOCKERS[index] for index in (3, 5, 7, 8)]
    assert set(preflight.EVIDENCE_BLOCKER_ROLES) == set(LAUNCH_BLOCKERS[:3])
    assert case.plan["external_live_receipt"] == preflight.EXTERNAL_LIVE_RECEIPT
    assert preflight.EXTERNAL_LIVE_RECEIPT["recorder"] in REQUIRED_SOURCES
    assert set(case.plan["source_pins"]) == REQUIRED_SOURCES and len(REQUIRED_SOURCES) == 58
    assert preflight.EXTERNAL_LIVE_RECEIPT["requires_live_caps_usage_witness"] is True
    assert preflight.EXTERNAL_LIVE_RECEIPT["offline_preflight_consumption"] is False
    assert preflight.EXTERNAL_LIVE_RECEIPT["clears_current_blockers"] is False
    assert case.plan["launch_enabled"] is case.plan["pilot"]["full_220_enabled"] is False
    for report in (plan_only, prepared):
        assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert main([]) == 2
    assert json.loads(capsys.readouterr().out) == plan_only
    for key in ("requires_live_caps_usage_witness", "offline_preflight_consumption", "clears_current_blockers"):
        changed = deepcopy(case.plan)
        changed["external_live_receipt"][key] = not changed["external_live_receipt"][key]
        refusal = inspect_plan(changed)
        assert refusal["configuration_valid"] is False
        assert refusal["launch_blockers"] == list(LAUNCH_BLOCKERS)
        assert refusal["launch_allowed"] is refusal["full_220_allowed"] is False
    assert external.external_live_receipt_for(None) is None
    for value in ({}, b"{}", SimpleNamespace(ready=b"{}")):
        with pytest.raises(external.PilotExternalLiveReceiptRefused):
            external.external_live_receipt_for(value)


@pytest.mark.parametrize("path,value", [
    (("binding", "run_id"), "another-run"),
    (("binding", "reviewed_source_sha"), "C" * 40),
    (("binding", "task_ids"), []),
    (("binding", "run_started_at"), "2026-09-19T23:59:59Z"),
    (("binding", "capture", "sha256"), "0" * 64),
    (("binding", "capture_linkage_sha256"), "0" * 64),
    (("binding", "prepared", "sha256"), "0" * 64),
    (("binding", "upstream_bundles_sha256"), "0" * 64),
    *[(("binding", role, "sha256"), "0" * 64)
      for role in ("caps_ready", "caps_reservation", "wire_ready", "wire_reservation",
                   "host_ready", "host_reservation", "evidence_ready")],
    (("binding", "evidence_roles", "native_caps", "sha256"), "0" * 64),
    (("binding", "accepted_results", "step2_inference_results.json", "result_fingerprint"), "0" * 64),
    (("attempts", 0, "binding", "task_id"), "00000000-0000-0000-0000-000000000000"),
    (("attempts", 0, "binding", "attempt_index"), 1),
    (("attempts", 0, "binding", "attempt_index"), True),
    (("attempts", 0, "binding", "attempt_index"), -1),
    (("attempts", 0, "binding", "attempt_index"), 4),
    (("attempts", 0, "binding", "retry_kind"), "infrastructure"),
    (("attempts", 0, "binding", "retry_kind"), "resume"),
    (("attempts", 0, "binding", "logical_turn"), 2),
    (("attempts", 0, "binding", "accepted_row_sha256"), "0" * 64),
    *[(("attempts", 0, "binding", role, "sha256"), "0" * 64)
      for role in ("caps_receipt", "wire_receipt", "host_receipt")],
    *[(("attempts", 0, "binding", role, "serialized_utf8", "sha256"), "0" * 64)
      for role in ("thread_start", "turn_start")],
    (("attempts", 0, "binding", "turn_start", "serialized_utf8", "size"), 1),
    (("attempts", 0, "binding", "turn_start", "request_id_sha256"), "0" * 64),
    (("attempts", 0, "binding", "thread_id_sha256"), "0" * 64),
    (("attempts", 0, "binding", "turn_id_sha256"), "0" * 64),
    (("attempts", 0, "window_started_at"), "2026-09-19T23:59:59Z"),
    (("attempts", 0, "window_ended_at"), "2026-09-20T00:00:01Z"),
])
def test_external_live_receipt_exact_chain_request_correlation_and_attempt_binding(
    external_live_receipt_documents, path, value,
):
    sample = external_live_receipt_documents
    target = sample.artifact
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(sample.module.PilotExternalLiveReceiptRefused):
        _external_live_receipt_validate(sample)


def _external_live_receipt_populated(sample):
    artifact = deepcopy(sample.artifact)
    for index, record in enumerate(artifact["attempts"]):
        for name in ("request", "response"):
            record[f"provider_{name}_id_sha256"] = sample.module._digest(
                f"synthetic-provider-{name}-{index}".encode(),
            )["sha256"]
        record["served"] = deepcopy(sample.snapshot["reviewed"]["subject"])
        record["tariff"] = deepcopy(sample.snapshot["reviewed"]["tariff"])
        record["usage"] = deepcopy(sample.snapshot["reviewed"]["usage"])
        record["billing"] = deepcopy(sample.snapshot["reviewed"]["usage"])
        for role, counts in (("usage", (71, None, 9)), ("billing", (37, None, 4))):
            record[role]["partial_reasons"] = ["usage_partial"]
            for meter, count in zip(sample.module.evidence.METERS, counts):
                record[role]["meters"][meter]["quantity"] = count
    return artifact


def test_external_live_receipt_present_claims_preserve_independent_billing_and_unknowns(
    external_live_receipt_documents,
):
    sample = external_live_receipt_documents
    artifact = _external_live_receipt_populated(sample)
    assert _external_live_receipt_validate(sample, artifact) == artifact
    row = artifact["attempts"][0]
    assert row["usage"]["meters"]["input_tokens"]["quantity"] == 71
    assert row["billing"]["meters"]["input_tokens"]["quantity"] == 37
    for role in ("usage", "billing"):
        assert row[role]["meters"]["cached_input_tokens"]["quantity"] is None
    row["served"]["served_model_version"] = None
    row["billing"]["currency"] = None
    row["billing"]["meters"]["cached_input_tokens"]["quantity"] = 38
    row["tariff"] = None
    assert _external_live_receipt_validate(sample, artifact) == artifact
    assert "model_call_count" not in row


@pytest.mark.parametrize("change", [
    "fast-model", "guessed-model", "version", "deployment", "raw-deployment", "openai-provider", "raw-account",
    "usage-drift", "usage-guessed-cache", "usage-negative", "usage-boolean", "usage-float", "usage-overflow",
    "usage-meter", "billing-meter", "duplicate-meter", "billing-currency", "billing-region", "billing-unit",
    "unknown-currency", "cached-exceeds-input", "missing-meter", "tariff-rate", "openai-tariff", "copilot-tariff",
    "tariff-time", "duplicate-provider-request", "duplicate-provider-response", "rpc-as-provider-request",
    "turn-as-provider-response", "served-extra", "billing-extra",
])
def test_external_live_receipt_served_usage_meter_and_provider_namespaces_fail_closed(
    external_live_receipt_documents, change,
):
    sample = external_live_receipt_documents
    artifact = _external_live_receipt_populated(sample)
    row = artifact["attempts"][0]
    if change in ("fast-model", "guessed-model", "version", "deployment", "raw-deployment", "openai-provider", "raw-account"):
        key, value = {
            "fast-model": ("served_model", "gpt-5.6-sol-fast"), "guessed-model": ("served_model", "gpt56"),
            "version": ("served_model_version", "2026-09-02"),
            "deployment": ("deployment", {"resource_id_sha256": "0" * 64}),
            "raw-deployment": ("deployment", "/subscriptions/private/deployments/private"),
            "openai-provider": ("provider", "openai"), "raw-account": ("account", "private-account"),
        }[change]
        row["served"][key] = value
    elif change.startswith("usage-") and change != "usage-meter":
        row["usage"]["meters"]["cached_input_tokens" if change == "usage-guessed-cache" else "input_tokens"]["quantity"] = {
            "usage-drift": 72, "usage-guessed-cache": 0, "usage-negative": -1,
            "usage-boolean": True, "usage-float": 71.0, "usage-overflow": 2 ** 63,
        }[change]
    elif change in ("usage-meter", "billing-meter"):
        row[change.split("-")[0]]["meters"]["input_tokens"]["meter_id"] = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    elif change == "duplicate-meter":
        row["billing"]["meters"]["output_tokens"]["meter_id"] = row["billing"]["meters"]["input_tokens"]["meter_id"]
    elif change in ("billing-currency", "billing-region", "unknown-currency"):
        row["billing"]["region" if change == "billing-region" else "currency"] = {
            "billing-currency": "EUR", "billing-region": "westus", "unknown-currency": "UNKNOWN",
        }[change]
    elif change == "billing-unit":
        row["billing"]["meters"]["input_tokens"]["unit"] = "requests"
    elif change == "cached-exceeds-input":
        row["usage"]["meters"]["cached_input_tokens"]["quantity"] = 72
    elif change == "missing-meter":
        del row["billing"]["meters"]["output_tokens"]
    elif change == "tariff-rate":
        row["tariff"]["rates"]["input_tokens"]["amount"] = "0.01"
    elif change in ("openai-tariff", "copilot-tariff"):
        row["tariff"]["tariff_source"] = "openai" if change == "openai-tariff" else "github_copilot"
    elif change == "tariff-time":
        row["tariff"]["effective_at"] = "2026-09-19T00:00:00Z"
    elif change.startswith("duplicate-provider-"):
        field = "provider_" + change.rsplit("-", 1)[1] + "_id_sha256"
        artifact["attempts"][1][field] = row[field]
    elif change == "rpc-as-provider-request":
        row["provider_request_id_sha256"] = row["binding"]["turn_start"]["request_id_sha256"]
    elif change == "turn-as-provider-response":
        row["provider_response_id_sha256"] = row["binding"]["turn_id_sha256"]
    else:
        row["served" if change == "served-extra" else "billing"]["Authorization"] = "Bearer private-token"
    with pytest.raises(sample.module.PilotExternalLiveReceiptRefused):
        _external_live_receipt_validate(sample, artifact)


@pytest.fixture
def external_live_receipt_case(runtime_caps_usage_case, runtime_caps_usage_offline):
    import gpt56_pilot_external_live_receipt as external

    case = runtime_caps_usage_case
    wire_cases, _ = runtime_caps_usage_offline
    runtime, snapshot = _external_live_receipt_owner(case, wire_cases)
    source = case.parent / "private-provider-export.json"
    data = external._bytes(_external_live_receipt_artifact(snapshot))
    source.write_bytes(data)
    pin = external._digest(data)
    return SimpleNamespace(
        case=case, wire_cases=wire_cases, module=external, runtime=runtime, snapshot=snapshot,
        source=source, data=data,
        options={"artifact_path": source, "artifact_sha256": pin["sha256"], "artifact_size": pin["size"],
                 "reviewed_source_sha": case.context.reviewed_source_sha, "as_of": case.context.as_of},
    )


def test_external_live_receipt_real_owners_ready_last_and_no_disk_adoption_or_reuse(
    external_live_receipt_case, monkeypatch, capsys,
):
    sample = external_live_receipt_case
    external, runtime, case = sample.module, sample.runtime, sample.case
    upstream = (runtime.ready, runtime.host.ready, runtime.wire.ready, dict(runtime.host.results))
    writes, original = [], sample.wire_cases.wire._write_no_clobber

    def tracked(path, data):
        assert not (case.workspace / external.DIRECTORY / external.READY_PATH).exists()
        if path.name == external.READY_PATH:
            assert (path.parent / external.ARTIFACT_PATH).read_bytes() == sample.data
        writes.append(path.name)
        original(path, data)

    monkeypatch.setattr(sample.wire_cases.wire, "_write_no_clobber", tracked)
    owner = external.PilotExternalLiveReceiptSession(runtime, **sample.options)
    document = owner.publish()
    assert external.verify_pilot_external_live_receipt(owner) == document
    assert external.external_live_receipt_for(runtime) is owner
    assert writes == [external.RESERVATION, external.ARTIFACT_PATH, external.READY_PATH]
    assert owner.ready == external._bytes(document)
    assert document["binding"] == sample.snapshot["binding"]
    assert document["artifact"] == {"path": external.ARTIFACT_PATH, **external._digest(sample.data)}
    assert document["reviewed_source_sha"] == case.context.reviewed_source_sha
    assert document["evaluated_at"] == case.context.as_of
    assert document["provenance_status"] == "unverified"
    assert document["authenticity"] == "not_authenticated_offline"
    assert document["eligible_facts"] == document["cleared_blockers"] == []
    assert document["cost"] is None and document["cost_state"] == "partial"
    assert document["remaining_launch_blockers"] == [LAUNCH_BLOCKERS[index] for index in (3, 5, 7, 8)]
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    assert document["not_available"]["model_call_count"] == sample.wire_cases.wire._unavailable()
    assert document["not_available"]["billing_quantity"] == sample.wire_cases.wire._unavailable()
    assert upstream == (runtime.ready, runtime.host.ready, runtime.wire.ready, dict(runtime.host.results))
    for path, data in runtime.host.results.items():
        assert path.read_bytes() == data
    assert sample.source.read_bytes() == sample.data
    public = owner.reservation + owner.ready + b"".join(owner.files.values())
    for value in (sample.wire_cases.PRIVATE_TEXT.encode(), sample.wire_cases.PRIVATE.encode(),
                  str(case.parent).encode(), *sample.wire_cases.RAW_IDS):
        assert value not in public
    for path in (owner.reserved, *owner.root.iterdir()):
        assert path.stat().st_nlink == 1 and not path.is_symlink()
    report = inspect_plan(case.plan, **vars(case.context), capture_workspace=case.workspace)
    assert report["configuration_valid"] is True
    assert report["launch_blockers"] == document["remaining_launch_blockers"]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert capsys.readouterr().out == ""
    for forged in (document, owner.ready, owner.root, SimpleNamespace(ready=owner.ready)):
        with pytest.raises(external.PilotExternalLiveReceiptRefused):
            external.verify_pilot_external_live_receipt(forged)
    before = tuple((path, path.read_bytes()) for path in (owner.reserved, *owner.root.iterdir()))
    with pytest.raises(external.PilotExternalLiveReceiptRefused):
        external.PilotExternalLiveReceiptSession(runtime, **sample.options)
    assert external.verify_pilot_external_live_receipt(owner) == document
    with pytest.raises(external.PilotExternalLiveReceiptRefused):
        owner.publish()
    assert owner.failed and runtime.failed
    assert all(path.read_bytes() == data for path, data in before)
    with pytest.raises(external.PilotExternalLiveReceiptRefused):
        external.verify_pilot_external_live_receipt(owner)


def test_external_live_receipt_caller_pins_paths_links_and_private_errors_refuse_before_attachment(
    external_live_receipt_case, capsys,
):
    sample = external_live_receipt_case
    external, runtime, case = sample.module, sample.runtime, sample.case
    linked = case.parent / "private-symlink.json"
    linked.symlink_to(sample.source)
    parent_link = case.parent / "private-parent-link"
    parent_link.symlink_to(sample.source.parent, target_is_directory=True)
    hard_source, hard = case.parent / "private-hard-source.json", case.parent / "private-hardlink.json"
    hard_source.write_bytes(sample.data)
    os.link(hard_source, hard)
    fifo = case.parent / "private-fifo"
    os.mkfifo(fifo)
    options = [
        {"artifact_path": case.parent / "missing-private.json"}, {"artifact_path": linked},
        {"artifact_path": parent_link / sample.source.name}, {"artifact_path": hard},
        {"artifact_path": fifo}, {"artifact_path": case.parent},
        {"artifact_path": case.parent / "untrusted" / ".." / sample.source.name},
        {"artifact_sha256": "0" * 64}, {"artifact_sha256": "F" * 64},
        {"artifact_size": len(sample.data) + 1}, {"artifact_size": True}, {"artifact_size": 1.0},
        {"artifact_size": external.MAX_ARTIFACT_SIZE + 1},
        {"reviewed_source_sha": "main"}, {"reviewed_source_sha": "0" * 40},
        {"as_of": "2026-10-01T00:00:01Z"},
    ]
    for changed in options:
        with pytest.raises(external.PilotExternalLiveReceiptRefused) as refusal:
            external.PilotExternalLiveReceiptSession(runtime, **{**sample.options, **changed})
        assert str(refusal.value) == external.REFUSAL and refusal.value.__suppress_context__
        assert getattr(runtime, "external_live_receipt", None) is None and not runtime.failed
        assert not os.path.lexists(case.workspace / external.RESERVATION)
        assert not os.path.lexists(case.workspace / external.DIRECTORY)
    assert sample.source.read_bytes() == sample.data
    output = capsys.readouterr()
    assert output.out == output.err == ""
    # A syntactically valid but different reviewer pin cannot bind this owner.
    with pytest.raises(external.PilotExternalLiveReceiptRefused):
        external.PilotExternalLiveReceiptSession(runtime, **{**sample.options, "reviewed_source_sha": "d" * 40})
    assert not os.path.lexists(case.workspace / external.RESERVATION)


@pytest.mark.parametrize("collision", ["reservation", "partial-directory"])
def test_external_live_receipt_no_clobber_preserves_existing_reservation_or_partial(
    external_live_receipt_case, collision,
):
    sample = external_live_receipt_case
    external, case = sample.module, sample.case
    if collision == "reservation":
        path = case.workspace / external.RESERVATION
    else:
        root = case.workspace / external.DIRECTORY
        root.mkdir()
        path = root / "partial.json"
    path.write_bytes(b"retain-for-quarantine")
    with pytest.raises(external.PilotExternalLiveReceiptRefused):
        external.PilotExternalLiveReceiptSession(sample.runtime, **sample.options)
    assert path.read_bytes() == b"retain-for-quarantine"
    assert not (case.workspace / external.DIRECTORY / external.READY_PATH).exists()
    assert getattr(sample.runtime, "external_live_receipt", None) is None


@pytest.mark.parametrize("change", ["source-during-write", "result-after-ready", "write-failure", "partial-extra"])
def test_external_live_receipt_mid_publication_drift_and_partials_cannot_be_adopted(
    external_live_receipt_case, monkeypatch, change,
):
    sample = external_live_receipt_case
    external = sample.module
    owner = external.PilotExternalLiveReceiptSession(sample.runtime, **sample.options)
    original = sample.wire_cases.wire._write_no_clobber

    def drift(path, data):
        original(path, data)
        if path.name == external.ARTIFACT_PATH:
            if change == "source-during-write":
                sample.source.write_bytes(sample.data + b" ")
            elif change == "write-failure":
                raise OSError(sample.wire_cases.PRIVATE_TEXT)
            elif change == "partial-extra":
                (owner.root / "unexpected.json").write_bytes(b"{}")
        elif path.name == external.READY_PATH and change == "result-after-ready":
            saved = next(iter(sample.runtime.host.results))
            saved.write_bytes(saved.read_bytes() + b" ")

    monkeypatch.setattr(sample.wire_cases.wire, "_write_no_clobber", drift)
    with pytest.raises(external.PilotExternalLiveReceiptRefused) as refusal:
        owner.publish()
    assert str(refusal.value) == external.REFUSAL
    assert owner.failed and sample.runtime.failed and sample.runtime.host.failed and sample.runtime.wire.failed
    assert owner.reserved.exists() and owner.root.exists()
    assert (owner.root / external.ARTIFACT_PATH).exists()
    assert (owner.root / external.READY_PATH).exists() is (change == "result-after-ready")
    for operation in (owner.publish, lambda: external.verify_pilot_external_live_receipt(owner),
                      lambda: external.PilotExternalLiveReceiptSession(sample.runtime, **sample.options)):
        with pytest.raises(external.PilotExternalLiveReceiptRefused):
            operation()
    assert owner.reserved.exists() and owner.root.exists()


def test_external_live_receipt_current_file_identity_and_review_pin_are_not_saved_verdicts(
    external_live_receipt_case,
):
    sample = external_live_receipt_case
    external = sample.module
    owner = external.PilotExternalLiveReceiptSession(sample.runtime, **sample.options)
    owner.publish()
    # Content is unchanged, but a new hardlink makes the source unsafe now.
    os.link(sample.source, sample.case.parent / "late-private-hardlink.json")
    with pytest.raises(external.PilotExternalLiveReceiptRefused):
        external.verify_pilot_external_live_receipt(owner)
    assert owner.failed and owner.reserved.exists() and (owner.root / external.READY_PATH).exists()


@pytest.mark.parametrize("change", ["unchanged-bounded", "legacy-unbounded", "replaced-before-open", "grows-during-read"])
def test_external_live_receipt_actual_descriptor_and_read_loop_enforce_artifact_bound(
    runtime_caps_usage_offline, tmp_path, monkeypatch, change,
):
    wire_cases, _ = runtime_caps_usage_offline
    reader = wire_cases.native
    source = tmp_path / "private-export.json"
    source.write_bytes(b"body")
    pin = wire_cases.wire._digest(b"body")
    identity = reader._identity(tmp_path)
    original_open, original_read = os.open, os.read
    reads = []

    def raced_open(path, *args, **kwargs):
        if change == "replaced-before-open" and path == source.name and kwargs.get("dir_fd") is not None:
            source.write_bytes(b"x" * 64)
        return original_open(path, *args, **kwargs)

    def bounded_read(descriptor, count):
        if change == "grows-during-read" and not reads:
            with source.open("ab") as stream:
                stream.write(b"x" * 64)
        reads.append(count)
        return original_read(descriptor, count)

    monkeypatch.setattr(os, "open", raced_open)
    monkeypatch.setattr(os, "read", bounded_read)
    options = {} if change == "legacy-unbounded" else {"max_bytes": 4}
    if change in ("unchanged-bounded", "legacy-unbounded"):
        assert reader._workspace_bytes(tmp_path, source.relative_to(tmp_path), identity, pin, **options) == b"body"
    else:
        with pytest.raises(reader.PilotNativeResultHostRefused):
            reader._workspace_bytes(tmp_path, source.relative_to(tmp_path), identity, pin, **options)
    if change == "legacy-unbounded":
        assert reads == [1024 * 1024, 1024 * 1024]
    elif change == "replaced-before-open":
        assert reads == []
    else:
        assert reads and max(reads) <= 5


def test_external_live_receipt_every_real_infrastructure_attempt_is_bound_without_inferred_calls(
    runtime_caps_usage_case, runtime_caps_usage_offline, monkeypatch,
):
    import gpt56_pilot_external_live_receipt as external

    case = runtime_caps_usage_case
    wire_cases, _ = runtime_caps_usage_offline
    original_start = wire_cases._native_start

    def start_with_one_failure(case, host, task_id):
        if task_id == wire_cases.TASK_IDS[0]:
            failed = original_start(case, host, task_id, attempt=0)
            result = wire_cases._native_finish(failed, success=False, output=False)
            wire_cases._native_accept(case, failed, result)
            return original_start(case, host, task_id, attempt=1)
        return original_start(case, host, task_id, attempt=0)

    # Only the existing synthetic input factory changes. Every arm, transport,
    # acceptance, result publication and parent verifier still runs for real.
    monkeypatch.setattr(wire_cases, "_native_start", start_with_one_failure)
    runtime, snapshot = _external_live_receipt_owner(case, wire_cases)
    assert snapshot["binding"]["task_ids"] == wire_cases.TASK_IDS
    assert [(row["task_id"], row["attempt_index"], row["retry_kind"]) for row in snapshot["attempt_bindings"]] == [
        (wire_cases.TASK_IDS[0], 0, "initial"), (wire_cases.TASK_IDS[0], 1, "infrastructure"),
        *[(task, 0, "initial") for task in wire_cases.TASK_IDS[1:]],
    ]
    artifact = _external_live_receipt_artifact(snapshot)
    schema = json.loads((preflight.ROOT / external.evidence.SCHEMA_PATH).read_bytes())
    incomplete = deepcopy(artifact)
    incomplete["attempts"].pop(0)
    with pytest.raises(external.PilotExternalLiveReceiptRefused):
        external._validate_artifact(external._bytes(incomplete), schema=schema, snapshot=snapshot,
                                    as_of=case.context.as_of)
    source = case.parent / "private-retried-export.json"
    data = external._bytes(artifact)
    source.write_bytes(data)
    owner = external.PilotExternalLiveReceiptSession(
        runtime, artifact_path=source, artifact_sha256=external._digest(data)["sha256"],
        artifact_size=len(data), reviewed_source_sha=case.context.reviewed_source_sha, as_of=case.context.as_of,
    )
    document = owner.publish()
    assert external.verify_pilot_external_live_receipt(owner) == document
    assert document["not_available"]["model_call_count"] == wire_cases.wire._unavailable()
    assert document["eligible_facts"] == document["cleared_blockers"] == []
