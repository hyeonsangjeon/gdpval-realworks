"""Pin the requested Copilot identity without pretending Foundry can serve it."""

import json
from dataclasses import fields

import pytest

from core.codex_runtime_config import (
    CodexProviderConfigurationError,
    CodexProviderSettings,
)
from core.experiment_config import ExperimentConfig
from gpt56_sol_codex_pilot_preflight import (
    BASELINE,
    LAUNCH_BLOCKERS,
    PLAN,
    REQUIRED_SOURCES,
    ROOT,
    inspect_plan,
    load_plan,
    main,
)

PLAN_READER_SOURCE = "batch-runner/gpt54_comparison_preflight.py"


@pytest.mark.parametrize(
    "path,value",
    [
        ((), None),
        (("identity", "model"), "gpt-5.6-sol-fast"),
        (("identity", "model"), "gpt-6-astra"),
        (("identity", "model"), "gpt-5.4"),
        (("identity", "provider"), "openai"),
        (("identity", "provider"), "azure"),
        (("identity", "harness"), "copilot_cli"),
        (("identity", "reasoning_effort"), "xhigh"),
        (("identity", "context_tier"), "standard"),
        (("identity", "nominal_context_tokens"), 272000),
        (("identity", "cli_version"), "unreviewed"),
        (("identity", "automatic_fallback_allowed"), True),
        (("identity", "fallbacks"), ["gpt-6-astra"]),
        (("identity", "verified_route"), "an_unverified_claim"),
        (("dataset", "tasks"), "reverse_tasks"),
        (("dataset", "tasks", 0, "prompt_sha256"), "0" * 64),
        (("dataset", "input_file_versions"), {}),
        (("developer_instructions",), "A different instruction."),
        (("pilot", "task_count"), 220),
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
        (("cost", "use_foundry_or_openai_tariff_for_copilot"), True),
        (("source_pins",), {}),
        pytest.param(
            ("source_pins", PLAN_READER_SOURCE), "remove_pin",
            id="plan-reader-pin-required",
        ),
        pytest.param(
            ("source_pins", PLAN_READER_SOURCE), "0" * 64,
            id="plan-reader-digest-checked",
        ),
        (("launch_enabled",), True),
    ],
)
def test_gpt56_sol_copilot_pilot_is_pinned_and_fails_closed(
    path, value, tmp_path, capsys
):
    plan = load_plan(PLAN)
    if path:
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
    if path == ("source_pins", PLAN_READER_SOURCE):
        assert result["configuration_problems"] == [
            "source_pin_set"
            if value == "remove_pin"
            else f"source_pin:{PLAN_READER_SOURCE}"
        ]
    assert result["launch_allowed"] is False
    assert result["full_220_allowed"] is False
    assert result["launch_blockers"] == list(LAUNCH_BLOCKERS)

    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["--plan", str(plan_path)]) == 2
    assert json.loads(capsys.readouterr().out) == result

    if not path:
        assert PLAN_READER_SOURCE in REQUIRED_SOURCES
        assert PLAN_READER_SOURCE in plan["source_pins"]
        # These are real adapter/config checks, with no SDK or auth execution.
        baseline = ExperimentConfig.from_yaml(str(ROOT / BASELINE))
        assert baseline.validate() == []
        baseline.condition_a.model.provider = "github_copilot"
        assert any("provider" in error for error in baseline.validate())
        with pytest.raises(CodexProviderConfigurationError):
            CodexProviderSettings(
                endpoint="https://copilot.fixture.invalid/openai/v1/",
                model="gpt-5.6-sol",
            )
        provider_fields = {field.name for field in fields(CodexProviderSettings)}
        assert not {
            "reasoning_effort", "context_tier", "model_context_window"
        } & provider_fields
