"""The fixed comparison validates, but its current adapters must not spend."""

import ast
import hashlib
import json
import socket
import subprocess
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.agentic_v2_model_voice import AzureFoundryVoice
from core.agentic_v2_conversation_runner import ceilings_from
from core.agentic_v2_stage_one_budget import load_stage_one_plan
from core.codex_runtime_config import CodexProviderSettings
from core.experiment_config import ExperimentConfig
from gpt54_comparison_preflight import (
    CODEX_TEMPLATE,
    V2_TEMPLATE,
    ComparisonDispatchPlan,
    ComparisonRunSpec,
    DispatchPlanRefused,
    LAUNCH_BLOCKERS,
    REQUIRED_SOURCES,
    ROOT,
    compile_dispatch_plan,
    inspect_plan,
    load_plan,
    main,
)


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
        "v2_request_effort", "v2_request_null", "v2_request_bool",
        "missing_v2_request", "missing_v2_stage_pin", "changed_v2_stage_pin",
        "missing_v2_plan_reader_pin", "changed_v2_plan_reader_pin",
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
    elif change in {"v2_request_effort", "v2_request_null", "v2_request_bool"}:
        plan["conditions"]["sandbox_v2"]["request"]["reasoning_effort"] = {
            "v2_request_effort": "high", "v2_request_null": None,
            "v2_request_bool": True,
        }[change]
    elif change == "missing_v2_request":
        plan["conditions"]["sandbox_v2"].pop("request")
    elif change in {
        "missing_v2_stage_pin", "changed_v2_stage_pin",
        "missing_v2_plan_reader_pin", "changed_v2_plan_reader_pin",
    }:
        source = (
            "batch-runner/scripts/run_agentic_v2_stage.py"
            if "stage_pin" in change
            else "batch-runner/core/agentic_v2_stage_one_budget.py"
        )
        if change.startswith("missing_"):
            plan["source_pins"].pop(source)
        else:
            plan["source_pins"][source] = "0" * 64

    result = inspect_plan(plan)
    assert result["configuration_valid"] is (change == "unchanged"), result
    assert result["launch_allowed"] is False
    assert result["launch_blockers"] == list(LAUNCH_BLOCKERS)
    assert result["requested_v2_responses_fields"] == (
        {"reasoning": {"effort": "xhigh"}} if change == "unchanged" else None
    )
    assert result["requested_codex_config_overrides"] == (
        ['model_reasoning_effort="xhigh"'] if change == "unchanged" else None
    )
    if change in {"missing_step2_pin", "changed_step2_pin"}:
        assert result["configuration_problems"] == [
            "source_pin_set" if change == "missing_step2_pin"
            else "source_pin:batch-runner/step2_run_inference.py"
        ]
    if change in {
        "missing_v2_stage_pin", "changed_v2_stage_pin",
        "missing_v2_plan_reader_pin", "changed_v2_plan_reader_pin",
    }:
        assert result["configuration_problems"] == [
            "source_pin_set" if change.startswith("missing_")
            else f"source_pin:{source}"
        ]

    # Exercise the real CLI entry point in process. JSON is valid YAML, too.
    path = tmp_path / "plan.yaml"
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["--plan", str(path)]) == 2
    assert json.loads(capsys.readouterr().out) == result

    if change == "unchanged":
        # Read actual adapter surfaces, not a mock declaration of readiness.
        voice_fields = {field.name: field for field in fields(AzureFoundryVoice)}
        assert voice_fields["reasoning_effort"].default is None
        assert len(REQUIRED_SOURCES) == 21
        assert set(plan["source_pins"]) == REQUIRED_SOURCES
        # Sol imports this module's plan reader. Refresh its existing digest
        # without changing its contract or running an additional selector.
        parser_source = "batch-runner/gpt54_comparison_preflight.py"
        sol = load_plan(ROOT / (
            "batch-runner/experiments/execution_envelope/"
            "gpt56_sol_copilot_codex_pilot.yaml"
        ))
        assert sol["source_pins"][parser_source] == hashlib.sha256(
            (ROOT / parser_source).read_bytes()
        ).hexdigest()
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
            "v2_reasoning_effort_capability_unverified",
            "codex_reasoning_effort_capability_unverified",
            "codex_native_model_call_and_token_limits_unenforced",
            "live_deployment_identity_and_input_bytes_not_verified",
            "comparison_pinned_grading_not_wired",
            "comparison_usage_and_tariff_evidence_unverified",
        } <= set(result["launch_blockers"])
        assert "v2_reasoning_effort_unwired" not in result["launch_blockers"]


@pytest.mark.parametrize("change", [
    "unchanged", "key_order", "missing_manifest", "missing_control",
    "provider", "effort", "task_order", "input_fingerprint", "limit", "grader",
    "matrix_order", "repeat_bool", "run_id", "cohort_220",
    "missing_pin", "changed_pin", "source_bytes",
    "compiled_argv", "compiled_config", "compiled_order", "compiled_repeat",
    "compiled_sources", "compiled_controls", "compiled_workspace", "compiled_launch",
])
def test_gpt54_offline_dispatch_plan_is_bound_and_non_executing(
    change, monkeypatch, tmp_path, capsys,
):
    """Compile real pinned templates, not a second dispatcher or a paid rehearsal."""
    def forbidden(*args, **kwargs):
        pytest.fail("offline compilation attempted execution, auth, or network access")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(CodexProviderSettings, "auth_command", forbidden)
    monkeypatch.setattr("core.codex_runtime_config.AzureAIRouteSettings.from_env", forbidden)

    manifest = json.loads(json.dumps(load_plan()))
    original = json.dumps(manifest, sort_keys=True)
    compiler_source = "batch-runner/gpt54_comparison_preflight.py"
    if change in {"missing_pin", "changed_pin"}:
        # Every dependency is required and digest-checked, including this
        # compiler, the shared parser, source-relative paths, and task helper.
        assert len(REQUIRED_SOURCES) == 21
        for source in REQUIRED_SOURCES:
            broken = json.loads(original)
            if change == "missing_pin":
                broken["source_pins"].pop(source)
            else:
                broken["source_pins"][source] = "0" * 64
            with pytest.raises(DispatchPlanRefused):
                compile_dispatch_plan(broken)
            rejected = inspect_plan(broken)
            assert rejected["configuration_valid"] is False
            assert rejected["dispatch_plan"] is None
            assert rejected["launch_allowed"] is False
        return
    if change == "source_bytes":
        read_bytes = Path.read_bytes
        monkeypatch.setattr(Path, "read_bytes", lambda path: (
            read_bytes(path) + b"\n# drift"
            if path == ROOT / compiler_source else read_bytes(path)
        ))
    elif change == "missing_manifest":
        manifest = None
    elif change == "missing_control":
        manifest.pop("shared")
    elif change in {"provider", "effort"}:
        manifest["shared"]["model"][
            "provider" if change == "provider" else "reasoning_effort"
        ] = "openai" if change == "provider" else "high"
    elif change == "task_order":
        manifest["shared"]["dataset"]["tasks"].reverse()
    elif change == "input_fingerprint":
        manifest["shared"]["dataset"]["input_file_versions"] = {}
    elif change == "limit":
        manifest["shared"]["limits"]["max_model_calls"] += 1
    elif change == "grader":
        manifest["shared"]["grading"]["rubric_revision"] = "main"
    elif change == "matrix_order":
        manifest["runs"].reverse()
    elif change == "repeat_bool":
        manifest["runs"][0]["repeat"] = True
    elif change == "run_id":
        manifest["runs"][1]["run_id"] = manifest["runs"][0]["run_id"]
    elif change == "cohort_220":
        manifest["runs"][0]["task_count"] = 220

    if change not in {"unchanged", "key_order"} and not change.startswith("compiled_"):
        with pytest.raises(DispatchPlanRefused):
            compile_dispatch_plan(manifest)
        refused = inspect_plan(manifest)
        assert refused["configuration_valid"] is False
        assert refused["dispatch_plan"] is None
        assert refused["requested_v2_responses_fields"] is None
        assert refused["requested_codex_config_overrides"] is None
        assert refused["launch_allowed"] is False
        return

    compiled = compile_dispatch_plan(manifest)
    assert isinstance(compiled, ComparisonDispatchPlan)
    document = compiled.as_dict()
    if change.startswith("compiled_"):
        if change == "compiled_argv":
            document["runs"][0]["commands"][0][3] = "full_220"
        elif change == "compiled_config":
            document["runs"][1]["config_json"] = document["runs"][1]["config_json"].replace("xhigh", "high")
        elif change == "compiled_order":
            document["runs"].reverse()
        elif change == "compiled_repeat":
            document["runs"][0]["repeat"] = True
        elif change == "compiled_sources":
            document["source_pins"].pop(compiler_source)
        elif change == "compiled_controls":
            document["shared_controls"]["limits"]["attempts_per_task"] = 2
        elif change == "compiled_workspace":
            document["runs"][2]["checkout_directory"] = document["runs"][1]["checkout_directory"]
        elif change == "compiled_launch":
            document["launch_allowed"] = True
        refused = inspect_plan(manifest, dispatch_plan=document)
        assert refused["configuration_problems"] == ["dispatch_plan_mismatch"]
        assert refused["configuration_valid"] is False
        assert refused["dispatch_plan"] is None
        assert refused["launch_allowed"] is False
        return

    # Key order and invocation count cannot alter any config or argument byte.
    reordered = json.loads(json.dumps(manifest, sort_keys=True))
    assert compile_dispatch_plan(reordered).canonical_bytes() == compiled.canonical_bytes()
    assert json.dumps(manifest, sort_keys=True) == original
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    assert document["shared_controls"] == manifest["shared"]
    assert document["source_pins"] == manifest["source_pins"]
    assert len(compiled.runs) == 4
    assert [(run.condition, run.repeat) for run in compiled.runs] == [
        ("sandbox_v2", 1), ("codex", 1), ("codex", 2), ("sandbox_v2", 2),
    ]
    assert len({run.checkout_directory for run in compiled.runs}) == 4
    expected_tasks = tuple(task["task_id"] for task in manifest["shared"]["dataset"]["tasks"])
    for run, row in zip(compiled.runs, manifest["runs"]):
        assert isinstance(run, ComparisonRunSpec)
        with pytest.raises(FrozenInstanceError):
            run.repeat = 220
        assert run.run_id == row["run_id"]
        assert run.task_ids == expected_tasks and len(run.task_ids) == 5
        assert (run.provider, run.model, run.reasoning_effort) == ("azure", "gpt-5.4", "xhigh")
        assert run.cohort == "advance_check_5"
        assert run.checkout_directory == f"comparison-runs/{run.run_id}"
        assert run.working_directory == "batch-runner"
        assert run.config_path == "batch-runner/comparison-run.json"
        config = json.loads(run.config_json)
        config_file = tmp_path / f"{run.run_id}.json"
        config_file.write_text(run.config_json, encoding="utf-8")
        if run.condition == "sandbox_v2":
            assert run.harness == "agentic_sandbox_v2"
            assert load_stage_one_plan(config_file) == config
            assert config["model"] == {"deployment": "gpt-5.4", "resolved_model": "gpt-5.4", "reasoning_effort": "xhigh"}
            assert config["task_ids"] == list(expected_tasks)
            assert config["azure_connection"]["account"] == manifest["shared"]["model"]["account"]
            assert config["azure_connection"]["route_profile"] == "direct-v1"
            assert config["cost"] == load_plan(ROOT / V2_TEMPLATE)["cost"]
            ceilings = ceilings_from(config, SimpleNamespace(**config["cost"]["chosen_settings"])).as_dict()
            assert all(manifest["shared"]["limits"][key] == value for key, value in ceilings.items())
            assert run.commands == ((
                "python3", "scripts/run_agentic_v2_stage.py", "--stage", "advance_check_5",
                "--plan", "comparison-run.json", "--parquet",
                "../data/gdpval-local/data/train-00000-of-00001.parquet",
                "--dataset-root", "../data/gdpval-local", "--run-id", run.run_id,
                "--into", "workspace",
            ),)
        else:
            assert run.harness == "codex"
            parsed = ExperimentConfig.from_yaml(str(config_file))
            assert parsed.validate() == []
            assert parsed.experiment_id == run.run_id
            assert parsed.data_filter.task_ids == list(expected_tasks)
            assert parsed.condition_a.model.reasoning_effort == "xhigh"
            assert parsed.execution.mode == "codex_foundry"
            assert parsed.execution.timeout == 1200.0
            assert parsed.execution.max_retries == parsed.execution.resume_max_rounds == 0
            assert parsed.execution.codex["endpoint_from_route"] is True
            assert parsed.execution.codex["reasoning_effort"] == "xhigh"
            assert parsed.execution.codex["model_context_window"] is None
            assert config["condition_a"]["prompt"] == load_plan(ROOT / CODEX_TEMPLATE)["condition_a"]["prompt"]
            assert config["output"] == {"publish_to_hf": False, "submit_to_evals": False}
            assert run.commands == (
                ("python3", "step1_prepare_tasks.py", "--config", "comparison-run.json"),
                ("python3", "step2_run_inference.py", "--condition", "condition_a",
                 "--max-retries", "0", "--resume-max-rounds", "0", "--no-resume"),
            )
        # Check real parser option declarations without importing or running
        # either execution entrypoint, even in its dry-run mode.
        for command in run.commands:
            tree = ast.parse((ROOT / "batch-runner" / command[1]).read_text(encoding="utf-8"))
            options = {
                arg.value for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
                for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            }
            assert {arg for arg in command[2:] if arg.startswith("--")} <= options

    result = inspect_plan(manifest, dispatch_plan=document)
    assert result["configuration_valid"] is True
    assert result["dispatch_plan"] == document
    assert result["dispatch_plan_sha256"] == hashlib.sha256(compiled.canonical_bytes()).hexdigest()
    assert result["launch_allowed"] is False
    assert result["launch_blockers"] == list(LAUNCH_BLOCKERS)
    assert "comparison_pinned_grading_not_wired" in LAUNCH_BLOCKERS
    assert "comparison_dispatch_and_pinned_grading_not_wired" not in LAUNCH_BLOCKERS
    assert capsys.readouterr().out == ""
    manifest_path, dispatch_path = tmp_path / "manifest.json", tmp_path / "dispatch.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    dispatch_path.write_bytes(compiled.canonical_bytes())
    assert main(["--plan", str(manifest_path), "--dispatch-plan", str(dispatch_path)]) == 2
    assert json.loads(capsys.readouterr().out) == result
    sol = load_plan(ROOT / "batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml")
    assert sol["source_pins"][compiler_source] == hashlib.sha256((ROOT / compiler_source).read_bytes()).hexdigest()
