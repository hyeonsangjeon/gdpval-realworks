"""The fixed comparison validates, but its current adapters must not spend."""

import ast
import hashlib
import json
import socket
import subprocess
import sys
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
    GRADER,
    V2_TEMPLATE,
    ComparisonDispatchPlan,
    ComparisonRunSpec,
    ComparisonGradingPlan,
    ComparisonGradingRunSpec,
    DispatchPlanRefused,
    LAUNCH_BLOCKERS,
    REQUIRED_SOURCES,
    ROOT,
    compile_dispatch_plan,
    compile_grading_plan,
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
        assert len(REQUIRED_SOURCES) == 23
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
            "comparison_materialization_and_workflow_gates_not_wired",
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
        assert len(REQUIRED_SOURCES) == 23
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
    assert "comparison_pinned_grading_not_wired" not in LAUNCH_BLOCKERS
    assert "comparison_materialization_and_workflow_gates_not_wired" in LAUNCH_BLOCKERS
    assert "comparison_dispatch_and_pinned_grading_not_wired" not in LAUNCH_BLOCKERS
    assert capsys.readouterr().out == ""
    manifest_path, dispatch_path = tmp_path / "manifest.json", tmp_path / "dispatch.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    dispatch_path.write_bytes(compiled.canonical_bytes())
    assert main(["--plan", str(manifest_path), "--dispatch-plan", str(dispatch_path)]) == 2
    assert json.loads(capsys.readouterr().out) == result
    sol = load_plan(ROOT / "batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml")
    assert sol["source_pins"][compiler_source] == hashlib.sha256((ROOT / compiler_source).read_bytes()).hexdigest()


@pytest.mark.parametrize("change", [
    "unchanged", "key_order", "missing_manifest", "missing_grading",
    "grader_config", "grader_source", "closure_pin", "rubric_revision",
    "grade_schema", "receipt_schema", "task_mapping", "task_order",
    "matrix_order", "repeat_bool", "cohort_220", "missing_pin", "changed_pin",
    "closure_source_bytes", "grader_config_bytes",
    "compiled_dispatch", "compiled_grader_config", "compiled_experiment",
    "compiled_argv", "compiled_tasks", "compiled_condition", "compiled_repeat",
    "compiled_input", "compiled_output", "compiled_receipt", "compiled_checkout",
    "compiled_grader_source", "compiled_schema", "compiled_resolution",
    "compiled_missing_run", "compiled_null_config", "compiled_launch",
])
def test_gpt54_pinned_grading_plan_is_bound_and_non_executing(
    change, monkeypatch, tmp_path, capsys,
):
    """Bind four inert recipes to real step8 readers without constructing a judge."""
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("offline grading plan attempted execution, client construction, or auth")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(CodexProviderSettings, "auth_command", forbidden)
    monkeypatch.setattr("core.codex_runtime_config.AzureAIRouteSettings.from_env", forbidden)
    import step8_grade as grading
    from core.result_projection import project_result_row

    monkeypatch.setattr(grading.Grader, "__init__", forbidden)
    monkeypatch.setattr(grading.RubricLoader, "__init__", forbidden)
    monkeypatch.setattr(grading, "preflight_routes", forbidden)
    monkeypatch.setattr(grading, "open_cost_recorder", forbidden)
    monkeypatch.setattr("core.llm_client.create_typed_azure_client", forbidden)

    manifest = json.loads(json.dumps(load_plan()))
    original = json.dumps(manifest, sort_keys=True)

    def assert_refused(broken):
        with pytest.raises(DispatchPlanRefused):
            compile_grading_plan(broken)
        result = inspect_plan(broken)
        assert result["configuration_valid"] is False
        assert result["dispatch_plan"] is result["grading_plan"] is None
        assert result["launch_allowed"] is result["full_220_allowed"] is False
        assert forbidden_calls == []

    if change in {"missing_pin", "changed_pin"}:
        assert len(REQUIRED_SOURCES) == 23
        assert "batch-runner/step8_grade.py" in REQUIRED_SOURCES
        for source in REQUIRED_SOURCES:
            broken = json.loads(original)
            if change == "missing_pin":
                broken["source_pins"].pop(source)
            else:
                broken["source_pins"][source] = "0" * 64
            assert_refused(broken)
        return
    if change in {"closure_source_bytes", "grader_config_bytes"}:
        # These are actual byte changes, not just edits to the manifest hash.
        # Most closure dependencies are deliberately not individually listed:
        # the existing grader helper binds them all, including prompt/include drift.
        sources = [GRADER] if change == "grader_config_bytes" else [
            "batch-runner/core/grader.py", "batch-runner/core/rubric_loader.py",
            "batch-runner/core/inference_manifest.py", "batch-runner/core/cost_receipts.py",
            "batch-runner/prompts/grader_judge_v2.md", "batch-runner/requirements.txt",
        ]
        read_bytes = Path.read_bytes
        for source in sources:
            with monkeypatch.context() as patch:
                patch.setattr(Path, "read_bytes", lambda path: (
                    read_bytes(path) + b"\n# drift"
                    if path == ROOT / source else read_bytes(path)
                ))
                assert_refused(manifest)
        return
    if change == "missing_manifest":
        manifest = None
    elif change == "missing_grading":
        manifest["shared"].pop("grading")
    elif change in {"grader_config", "grader_source", "closure_pin", "rubric_revision"}:
        key, value = {
            "grader_config": ("config", "batch-runner/grading_configs/default_v2.yaml"),
            "grader_source": ("source_sha", "0" * 40),
            "closure_pin": ("template_source_sha256", "0" * 64),
            "rubric_revision": ("rubric_revision", "main"),
        }[change]
        manifest["shared"]["grading"][key] = value
    elif change in {"grade_schema", "receipt_schema"}:
        manifest["shared"]["results"][change] = "unreviewed-schema"
    elif change == "task_mapping":
        manifest["shared"]["dataset"]["tasks"][0]["task_id"] = "unregistered-task"
    elif change == "task_order":
        manifest["shared"]["dataset"]["tasks"].reverse()
    elif change == "matrix_order":
        manifest["runs"].reverse()
    elif change == "repeat_bool":
        manifest["runs"][0]["repeat"] = True
    elif change == "cohort_220":
        manifest["runs"][0]["task_count"] = 220

    if change not in {"unchanged", "key_order"} and not change.startswith("compiled_"):
        assert_refused(manifest)
        return

    dispatch = compile_dispatch_plan(manifest)
    compiled = compile_grading_plan(manifest, dispatch_plan=dispatch.as_dict())
    assert isinstance(compiled, ComparisonGradingPlan)
    document = compiled.as_dict()
    if change.startswith("compiled_"):
        row = document["grading_runs"][0]
        if change == "compiled_dispatch":
            document["dispatch_plan"]["runs"][0]["commands"][0][3] = "full_220"
            with pytest.raises(DispatchPlanRefused, match="dispatch_plan_mismatch"):
                compile_grading_plan(manifest, dispatch_plan=document["dispatch_plan"])
        elif change == "compiled_grader_config":
            row["grader_config_json"] = row["grader_config_json"].replace(
                manifest["shared"]["grading"]["rubric_revision"], "main",
            )
        elif change == "compiled_experiment":
            row["experiment_config_json"] = row["experiment_config_json"].replace("gpt-5.4", "gpt-5.4-mini")
        elif change == "compiled_argv":
            row["command"][row["command"].index("--limit") + 1] = "220"
        elif change == "compiled_tasks":
            row["task_ids"].reverse()
        elif change == "compiled_condition":
            row["condition"] = "codex"
        elif change == "compiled_repeat":
            row["repeat"] = True
        elif change == "compiled_input":
            row["inference_results_path"] = "another-run/workspace/step2_inference_results.json"
        elif change == "compiled_output":
            row["output"]["grade_path_template"] = "data/grades/shared.json"
        elif change == "compiled_receipt":
            row["output"]["ledger_jsonl_path_template"] = "data/grades/shared.cost_ledger.jsonl"
        elif change == "compiled_checkout":
            row["checkout_directory"] = document["grading_runs"][1]["checkout_directory"]
        elif change == "compiled_grader_source":
            row["grader_contract_json"] = row["grader_contract_json"].replace(
                manifest["shared"]["grading"]["template_source_sha256"], "0" * 64,
            )
        elif change == "compiled_schema":
            row["grader_contract_json"] = row["grader_contract_json"].replace("cost-receipt-v1", "cost-v0")
        elif change == "compiled_resolution":
            row["output"]["inference_revision"] = manifest["shared"]["dataset"]["revision"]
        elif change == "compiled_missing_run":
            document["grading_runs"].pop()
        elif change == "compiled_null_config":
            row["grader_config_json"] = None
        elif change == "compiled_launch":
            document["launch_allowed"] = True
        result = inspect_plan(manifest, dispatch_plan=dispatch.as_dict(), grading_plan=document)
        assert result["configuration_problems"] == ["grading_plan_mismatch"]
        assert result["dispatch_plan"] is result["grading_plan"] is None
        assert result["configuration_valid"] is result["launch_allowed"] is False
        assert forbidden_calls == []
        return

    assert compile_grading_plan(json.loads(json.dumps(manifest, sort_keys=True))).canonical_bytes() == compiled.canonical_bytes()
    assert json.dumps(manifest, sort_keys=True) == original
    assert document["dispatch_plan"] == dispatch.as_dict()
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    assert [(run.condition, run.repeat) for run in compiled.runs] == [
        ("sandbox_v2", 1), ("codex", 1), ("codex", 2), ("sandbox_v2", 2),
    ]
    assert len({run.grader_config_json for run in compiled.runs}) == 1
    assert len({run.grader_contract_json for run in compiled.runs}) == 1
    for field in ("grade_path_template", "ledger_sqlite_path_template", "ledger_jsonl_path_template"):
        assert len({f"{run.checkout_directory}/{getattr(run.output, field)}" for run in compiled.runs}) == 4

    template = load_plan(ROOT / GRADER)
    with monkeypatch.context() as patch:
        patch.chdir(ROOT / "batch-runner")
        # The optional root does not change the existing default hash behavior.
        assert grading.compute_grader_source_hash(ROOT / GRADER, template) == grading.compute_grader_source_hash(
            ROOT / GRADER, template, batch_root=ROOT / "batch-runner",
        ) == manifest["shared"]["grading"]["template_source_sha256"]
        grading.validate_grading_config(template)

    expected_config = json.loads(json.dumps(template))
    expected_config["rubric"].update(
        revision=manifest["shared"]["grading"]["rubric_revision"],
        cache_dir="../data/gdpval-local",
    )
    schema = json.loads((ROOT / manifest["shared"]["results"]["grade_schema"]).read_text())
    assert grading.SCHEMA_VERSION == manifest["shared"]["results"]["grade_schema_version"] == "1.4"
    assert grading.SCHEMA_VERSION in schema["properties"]["schema_version"]["enum"]
    assert schema["$defs"]["costReceipt"]["properties"]["schema_version"]["const"] == "cost-receipt-v1"

    for run, inferred in zip(compiled.runs, dispatch.runs, strict=True):
        assert isinstance(run, ComparisonGradingRunSpec)
        with pytest.raises(FrozenInstanceError):
            run.repeat = 220
        assert (run.run_id, run.condition, run.repeat, run.task_ids) == (
            inferred.run_id, inferred.condition, inferred.repeat, inferred.task_ids,
        )
        assert len(run.task_ids) == 5
        assert run.checkout_directory == inferred.checkout_directory
        assert run.working_directory == inferred.working_directory == "batch-runner"
        assert run.inference_results_path == "batch-runner/workspace/step2_inference_results.json"
        assert run.staged_deliverables_directory == "batch-runner/workspace/upload/deliverable_files"
        assert run.producer_rows_pointer == ("/run/results" if run.condition == "sandbox_v2" else "/results")
        assert run.producer_results_path == (
            "batch-runner/workspace/run_record.json" if run.condition == "sandbox_v2"
            else run.inference_results_path
        )
        assert run.output.inference_repo_id is run.output.inference_revision is None
        assert run.output.materialized_grader_source_hash is None
        assert run.output.resolution.startswith("blocked_until_")
        assert run.command == (
            "python3", "step8_grade.py", f"execution_envelope/{run.run_id}",
            "--config", "comparison-grading.json", "--source", "local",
            "--tasks", ",".join(run.task_ids), "--limit", "5",
            "--shard-count", "1", "--shard-index", "0", "--run-ordinal", "1",
            "--source-experiment-id", run.run_id,
        )

        checkout = tmp_path / run.checkout_directory
        experiment_file = checkout / run.experiment_config_path
        experiment_file.parent.mkdir(parents=True)
        experiment_file.write_text(run.experiment_config_json, encoding="utf-8")
        config_file = checkout / run.grader_config_path
        config_file.write_text(run.grader_config_json, encoding="utf-8")
        # Step8's real loader is YAML safe_load + validate_grading_config.
        config = grading.yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert config == expected_config  # All judge/perception/retry defaults preserved.
        for key in ("template", "tool_template"):
            config["prompt"][key] = str(ROOT / "batch-runner" / config["prompt"][key])
        grading.validate_grading_config(config)
        assert hashlib.sha256(config_file.read_bytes()).hexdigest() == run.output.config_sha256
        assert grading.hash_config(str(config_file)) == run.output.config_sha256[:16]

        # Fabricated source identity is confined to this compatibility fixture.
        # Neither these hashes nor any result is emitted into the compiled plan.
        fixture = {
            "source_repo_id": "fixture/future-inference", "source_revision": "a" * 40,
            "results": [project_result_row({}, {"task_id": task_id, "status": "success"})
                        for task_id in run.task_ids],
        }
        input_file = checkout / run.inference_results_path
        input_file.parent.mkdir(parents=True)
        input_file.write_text(json.dumps(fixture), encoding="utf-8")
        with monkeypatch.context() as patch:
            patch.chdir(checkout / run.working_directory)
            patch.setattr(sys, "argv", list(run.command[1:]))
            args = grading.parse_args()  # Real option types, choices and defaults.
            assert args.force is args.resume is args.dry_run is False
            assert args.limit == 5 and args.run_ordinal == 1 and args.source == "local"
            parsed = grading.load_experiment_yaml(args.experiment_yaml_name)
            assert parsed.validate() == []
            assert parsed.experiment_id == run.run_id
            assert parsed.data_filter.task_ids == list(run.task_ids)
            assert parsed.condition_a.model.deployment == "gpt-5.4"
            assert parsed.condition_a.model.reasoning_effort == "xhigh"
            assert parsed.execution.mode == ("agentic_sandbox_v2" if run.condition == "sandbox_v2" else "codex_foundry")
            loaded = grading.load_local_inference_results()
            selected, scope = grading.filter_tasks_for_config(
                loaded, config, tasks_csv=args.tasks, limit=args.limit,
            )
            assert [row["task_id"] for row in selected] == list(run.task_ids)
            assert scope is None and (args.tasks is not None or args.limit > 0)
            assert all(row["latency_ms"] is None and "problem_solving_cost" not in row for row in selected)
            assert grading.resolve_source_inference_identity(loaded, config["schema_version"]) == (
                fixture["source_repo_id"], fixture["source_revision"],
            )
            resolved = grading.resolve_grade_output_path(
                config, experiment_id=args.experiment_yaml_name,
                judge_slug=grading._judge_slug(config["judge"]["model"]),
                config_hash=grading.hash_config(str(config_file)),
                rubric_sha=config["rubric"]["revision"], rubric_short_sha=config["rubric"]["revision"][:7],
                prompt_version=config["prompt"]["version"], inference_sha=fixture["source_revision"],
                grader_source_hash="b" * 64, diagnostic_task_scope_sha=run.output.ordered_task_ids_sha256,
                shard_index=args.shard_index, shard_count=args.shard_count, run_ordinal=args.run_ordinal,
            )
            bindings = {
                "exp_id": grading._experiment_path_slug(args.experiment_yaml_name),
                "judge_slug": grading._judge_slug(config["judge"]["model"]),
                "config_name": grading._config_name_slug(config["config_name"]),
                "config_hash": grading.hash_config(str(config_file)),
                "rubric_sha": config["rubric"]["revision"], "inference_sha": "a" * 40,
                "grader_source_hash_short": "b" * 16, "prompt_v": config["prompt"]["version"],
            }
            assert resolved.resolve() == (checkout / run.output.grade_path_template.format(**bindings)).resolve()
            for field, suffix in (("ledger_jsonl_path_template", ".cost_ledger.jsonl"),
                                  ("ledger_sqlite_path_template", ".cost_ledger.sqlite3")):
                assert resolved.with_suffix(suffix).resolve() == (
                    checkout / getattr(run.output, field).format(**bindings)
                ).resolve()

    result = inspect_plan(manifest, dispatch_plan=dispatch.as_dict(), grading_plan=document)
    assert result["configuration_valid"] is True
    assert result["grading_plan"] == document
    assert result["grading_plan_sha256"] == hashlib.sha256(compiled.canonical_bytes()).hexdigest()
    assert result["launch_allowed"] is result["full_220_allowed"] is False
    assert "comparison_pinned_grading_not_wired" not in result["launch_blockers"]
    assert set(result["launch_blockers"]) == {
        "v2_reasoning_effort_capability_unverified", "codex_reasoning_effort_capability_unverified",
        "codex_native_model_call_and_token_limits_unenforced", "live_deployment_identity_and_input_bytes_not_verified",
        "comparison_materialization_and_workflow_gates_not_wired", "comparison_usage_and_tariff_evidence_unverified",
    }
    manifest_path, dispatch_path, grading_path = (tmp_path / name for name in ("manifest.json", "dispatch.json", "grading.json"))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    dispatch_path.write_bytes(dispatch.canonical_bytes())
    grading_path.write_bytes(compiled.canonical_bytes())
    assert main(["--plan", str(manifest_path), "--dispatch-plan", str(dispatch_path), "--grading-plan", str(grading_path)]) == 2
    assert json.loads(capsys.readouterr().out) == result
    sol = load_plan(ROOT / "batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml")
    compiler_source = "batch-runner/gpt54_comparison_preflight.py"
    assert sol["source_pins"][compiler_source] == hashlib.sha256((ROOT / compiler_source).read_bytes()).hexdigest()
    assert forbidden_calls == []
