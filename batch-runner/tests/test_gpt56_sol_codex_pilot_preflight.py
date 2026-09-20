"""Keep one Foundry-only Sol contract without claiming a served capability."""

import json
import shutil
import socket
import subprocess
from copy import deepcopy
from dataclasses import fields

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
        assert len(REQUIRED_SOURCES) == 38
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
            "live_identity_and_input_bytes_unverified",
            "pilot_dispatch_and_grading_identity_not_wired",
            "foundry_usage_and_tariff_mapping_unverified",
            "native_sandbox_and_result_bundle_host_unverified",
            "actual_pilot_deployment_not_prepared",
        } <= set(result["launch_blockers"])
        assert offline_only == []
