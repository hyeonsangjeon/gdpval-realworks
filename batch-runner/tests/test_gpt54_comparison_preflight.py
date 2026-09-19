"""The fixed comparison validates, but its current adapters must not spend."""

import json
from dataclasses import fields

import pytest

from core.agentic_v2_model_voice import AzureFoundryVoice
from core.codex_runtime_config import CodexProviderSettings
from gpt54_comparison_preflight import LAUNCH_BLOCKERS, inspect_plan, load_plan, main


@pytest.mark.parametrize(
    "change",
    [
        "unchanged", "model", "resolved_model", "account", "effort",
        "shared_lower_effort", "task_order", "task_content",
        "reference_fingerprint", "token_limit", "turn_limit", "time_limit",
        "retry_limit", "grader", "result_schema", "missing_repeat",
        "duplicate_repeat", "larger_cohort", "cost_policy", "launch_enabled",
        "missing_pin", "changed_pin", "environment_claim",
        "request_effort", "request_context", "missing_request",
        "missing_step2_pin", "changed_step2_pin",
    ],
)
def test_gpt54_comparison_is_fixed_and_fails_closed(change, tmp_path, capsys):
    # Break YAML aliases so mutations really change one condition only.
    plan = json.loads(json.dumps(load_plan()))
    controls = plan["conditions"]["codex"]["controls"]
    if change in {"model", "resolved_model", "account", "effort"}:
        key, value = {
            "model": ("deployment", "another-model"),
            "resolved_model": ("resolved_model", "another-model"),
            "account": ("account", "another-account"),
            "effort": ("reasoning_effort", "high"),
        }[change]
        controls["model"][key] = value
    elif change == "shared_lower_effort":
        # Matching effort is not enough: both must request the highest one.
        plan["shared"]["model"]["reasoning_effort"] = "high"
        for condition in plan["conditions"].values():
            condition["controls"]["model"]["reasoning_effort"] = "high"
    elif change == "task_order":
        controls["dataset"]["tasks"].reverse()
    elif change == "task_content":
        controls["dataset"]["tasks"][0]["prompt_sha256"] = "0" * 64
    elif change == "reference_fingerprint":
        name = next(
            name for name in controls["dataset"]["input_file_versions"]
            if name.startswith("reference_files/")
        )
        controls["dataset"]["input_file_versions"][name] = "0" * 64
    elif change in {"token_limit", "turn_limit", "time_limit", "retry_limit"}:
        key = {
            "token_limit": "max_input_tokens",
            "turn_limit": "max_model_turns",
            "time_limit": "max_seconds",
            "retry_limit": "request_max_retries",
        }[change]
        controls["limits"][key] += 1
    elif change == "grader":
        controls["grading"]["rubric_revision"] = "main"
    elif change == "result_schema":
        controls["results"]["receipt_schema"] = "another-schema"
    elif change == "missing_repeat":
        plan["runs"].pop()
    elif change == "duplicate_repeat":
        plan["runs"][2] = plan["runs"][1]
    elif change == "larger_cohort":
        plan["runs"][0]["task_count"] = 220
    elif change == "cost_policy":
        controls["cost"]["policy"] = "strict"
    elif change == "launch_enabled":
        plan["launch_enabled"] = True
    elif change == "missing_pin":
        plan["source_pins"].pop(next(iter(plan["source_pins"])))
    elif change == "changed_pin":
        plan["source_pins"][next(iter(plan["source_pins"]))] = "0" * 64
    elif change == "environment_claim":
        plan["comparison"] = "environment_only"
    elif change == "request_effort":
        plan["conditions"]["codex"]["request"]["reasoning_effort"] = "high"
    elif change == "request_context":
        plan["conditions"]["codex"]["request"]["model_context_window"] = 1_000_000
    elif change == "missing_request":
        plan["conditions"]["codex"].pop("request")
    elif change == "missing_step2_pin":
        plan["source_pins"].pop("batch-runner/step2_run_inference.py")
    elif change == "changed_step2_pin":
        plan["source_pins"]["batch-runner/step2_run_inference.py"] = "0" * 64

    result = inspect_plan(plan)
    assert result["configuration_valid"] is (change == "unchanged"), result
    assert result["launch_allowed"] is False
    assert result["launch_blockers"] == list(LAUNCH_BLOCKERS)
    assert result["requested_codex_config_overrides"] == (
        ['model_reasoning_effort="xhigh"'] if change == "unchanged" else None
    )
    if change in {"missing_step2_pin", "changed_step2_pin"}:
        assert result["configuration_problems"] == [
            "source_pin_set" if change == "missing_step2_pin"
            else "source_pin:batch-runner/step2_run_inference.py"
        ]

    # Exercise the real CLI entry point in process. JSON is valid YAML, too.
    path = tmp_path / "plan.yaml"
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["--plan", str(path)]) == 2
    assert json.loads(capsys.readouterr().out) == result

    if change == "unchanged":
        # Read actual adapter surfaces, not a mock declaration of readiness.
        voice_fields = {field.name for field in fields(AzureFoundryVoice)}
        assert "reasoning_effort" not in voice_fields
        provider = CodexProviderSettings(
            endpoint="https://fixture.openai.azure.com/openai/v1/", model="gpt-5.4",
            **plan["conditions"]["codex"]["request"],
        )
        overrides = provider.config_overrides()
        assert overrides[-1:] == ('model_reasoning_effort="xhigh"',)
        assert not any("model_context_window" in value for value in overrides)
        assert not any(
            "max_output_tokens" in value or "max_model_calls" in value
            for value in overrides
        )
        assert {
            "v2_reasoning_effort_unwired",
            "codex_reasoning_effort_capability_unverified",
            "codex_native_model_call_and_token_limits_unenforced",
            "live_deployment_identity_and_input_bytes_not_verified",
            "comparison_dispatch_and_pinned_grading_not_wired",
            "comparison_usage_and_tariff_evidence_unverified",
        } <= set(result["launch_blockers"])
