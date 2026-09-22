"""Lightweight offline GHCP VM gate checks; this file stays in core pytest."""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import shlex
import socket
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ENVELOPE = "batch-runner/experiments/execution_envelope/"
HISTORICAL = ENVELOPE + "gpt56_sol_copilot_codex_pilot.yaml"
HISTORICAL_SHA256 = "47799d3f61374679722df32c67de14f9d0d56bd6586cf7b28c10076fd41d1901"
FOUNDRY = ENVELOPE + "gpt56_sol_foundry_codex_pilot.yaml"
FOUNDRY_SHA256 = "aa8d3c1a3e5cc0a7f8aeb86d12c88fd5a0b40155d97bc479d84041b94349beab"
WORKFLOW = ".github/workflows/backend-tests.yml"
WORKFLOW_SHA256 = "a0cc6b2b76c43a143a73ef40da3cf8088b85a6c01b0f509a5606b91bb7b1fd8c"
FALSE_FLAGS = (
    "launch_enabled", "launch_allowed", "paid_execution_enabled",
    "paid_execution_allowed", "full_220_enabled", "full_220_allowed",
)
EXPECTED_BLOCKERS = [
    "ghcp_route_served_identity_unverified",
    "max_long_1m_capability_unverified",
    "ghcp_codex_versions_unresolved",
    "authentication_supply_disposal_unresolved",
    "vm_image_os_packages_version_policy_unresolved",
    "fresh_task_vm_reset_unverified",
    "network_permission_policy_unresolved",
    "native_execution_limits_unresolved",
    "repeat_and_variance_plan_unresolved",
    "five_task_time_cost_caps_unresolved",
    "native_ghcp_usage_and_missing_usage_policy_unresolved",
    "original_task_input_materialization_unverified",
    "transcript_tool_command_file_exit_capture_unverified",
    "grading_result_runtime_unwired",
    "grader_validation_unverified",
]


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    """Refuse process, network, provider/auth and grader entrypoints."""
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("execution_boundary")
        raise AssertionError("GHCP VM contract must remain offline")

    real_import = builtins.__import__
    forbidden_imports = (
        "azure", "openai", "huggingface_hub", "datasets", "requests", "httpx",
        "step8_grade", "core.codex_runner", "core.codex_azure_token",
        "core.azure_ai_clients", "core.executor", "core.llm_client",
    )

    def guarded_import(name, *args, **kwargs):
        if any(name == prefix or name.startswith(prefix + ".")
               for prefix in forbidden_imports):
            return forbidden()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    for name in ("Popen", "run", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    yield
    assert calls == []


@pytest.fixture
def gate(offline_only):
    import ghcp_vm_gate_preflight

    return ghcp_vm_gate_preflight


@pytest.fixture
def plan(gate):
    return gate.load_plan()


def assert_refused(report):
    assert report["configuration_valid"] is False
    assert report["configuration_problems"] == ["ghcp_vm_gate_refused"]
    assert report["plan_sha256"] is None
    assert report["launch_blockers"] == EXPECTED_BLOCKERS
    assert report["eligible_facts"] == []
    assert report["cleared_blockers"] == []
    assert report["task_ids"] == report["tasks"] == []
    assert report["input_file_versions"] == {}
    for name in FALSE_FLAGS:
        assert report[name] is False


def leaf_items(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaf_items(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaf_items(child, path + (index,))
    else:
        yield path, value


def replace_at(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


def test_ghcp_vm_gate_contract_preserves_history_foundry_and_backend_partition():
    for relative, expected in (
        (HISTORICAL, HISTORICAL_SHA256),
        (FOUNDRY, FOUNDRY_SHA256),
        (WORKFLOW, WORKFLOW_SHA256),
    ):
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    historical = yaml.safe_load((ROOT / HISTORICAL).read_bytes())
    assert historical["status"] == "superseded"
    assert historical["launch_enabled"] is False
    assert historical["superseded_by"] == FOUNDRY

    jobs = yaml.safe_load((ROOT / WORKFLOW).read_bytes())["jobs"]
    test_path = "tests/" + Path(__file__).name
    core_step = next(step for step in jobs["pytest"]["steps"]
                     if step["name"] == "Run tests")
    arguments = shlex.split(core_step["run"].splitlines()[1])
    assert "--ignore=" + test_path not in arguments
    assert Path(__file__).name.startswith("test_ghcp_")
    for name in ("comparison-contracts", "pilot-contracts", "wire-contracts", "native-host-contracts"):
        assert test_path not in jobs[name]["steps"][-1]["run"]


def test_ghcp_vm_gate_contract_valid_fixed_five_is_still_blocked(gate, plan):
    from core.execution_envelope_tasks import load_task_catalog, select_advance_check_tasks

    before = deepcopy(plan)
    historical = yaml.safe_load((ROOT / HISTORICAL).read_bytes())
    catalog = load_task_catalog(ROOT / ENVELOPE / "gdpval_task_catalog.json")
    expected_ids = list(select_advance_check_tasks(catalog).task_ids)
    assert expected_ids == [task["task_id"] for task in historical["dataset"]["tasks"]]
    assert len(expected_ids) == len(set(expected_ids)) == 5

    report = gate.inspect_plan(plan)
    assert report["configuration_valid"] is True
    assert report["configuration_problems"] == []
    assert report["task_ids"] == expected_ids
    assert report["launch_blockers"] == EXPECTED_BLOCKERS
    assert report["eligible_facts"] == report["cleared_blockers"] == []
    for name in FALSE_FLAGS:
        assert plan[name] is False
        assert report[name] is False
    assert plan["base_sha"] == "99e62ed5d4f1b1506841dd70a66c2696ac95b4c6"
    assert plan["condition_id"] != historical["pilot"]["run_id"]
    assert "ghcp" in plan["condition_id"] and "vm" in plan["condition_id"]
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    assert report["plan_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()
    assert plan == before


def test_ghcp_vm_gate_contract_request_is_not_an_observation(gate, plan):
    assert plan["identity"] == {
        "provider": "github_copilot",
        "model": "gpt-5.6-sol",
        "model_label": "GPT-5.6 Sol",
        "fast_mode": False,
        "harness": "codex",
        "reasoning_effort": "max",
        "context_tier": "long",
        "context_label": "Long (1M)",
        "nominal_context_tokens": 1000000,
        "capability_semantics": "request_not_served_evidence",
        "ghcp_cli_version": None,
        "codex_cli_version": None,
        "codex_sdk_version": None,
        "automatic_fallback_allowed": False,
        "fallbacks": [],
    }
    report = gate.inspect_plan(plan)
    assert report["observed"] == plan["observed"] == {
        "verified_served": None,
        "verified_capability": None,
        "verified_auth": None,
        "verified_reset": None,
        "verified_capture": None,
        "verified_enforced_limits": None,
        "verified_usage": None,
        "verified_task_inputs": None,
        "grader_validation": None,
    }
    assert report["cleared_blockers"] == report["eligible_facts"] == []
    assert report["evidence_boundary"] == (
        "offline_source_consistency_not_observed_execution_or_launch_approval"
    )


def test_ghcp_vm_gate_contract_original_input_deliverable_and_grader_pins(gate, plan):
    from core.execution_envelope_tasks import load_task_catalog, select_advance_check_tasks

    catalog = load_task_catalog(ROOT / ENVELOPE / "gdpval_task_catalog.json")
    by_id = {task.task_id: task for task in catalog.tasks}
    selected = [by_id[task_id] for task_id in select_advance_check_tasks(catalog).task_ids]
    historical = yaml.safe_load((ROOT / HISTORICAL).read_bytes())
    report = gate.inspect_plan(plan)
    assert report["tasks"] == [
        {
            "task_id": task.task_id,
            "prompt_sha256": task.prompt_sha256,
            "reference_file_paths": list(task.reference_file_paths),
            "deliverable_file_extensions": list(task.deliverable_file_extensions),
            "deliverable_formats": list(task.deliverable_formats),
        }
        for task in selected
    ]
    assert historical["dataset"]["tasks"] == [
        {"task_id": task["task_id"], "prompt_sha256": task["prompt_sha256"]}
        for task in report["tasks"]
    ]
    versions = report["input_file_versions"]
    dataset_key = catalog.dataset_repo_id + "@" + catalog.dataset_revision
    reference_paths = {path for task in selected for path in task.reference_file_paths}
    assert set(versions) == reference_paths | {dataset_key}
    assert versions == historical["dataset"]["input_file_versions"]
    assert versions[dataset_key] == plan["dataset"]["parquet_sha256"] == catalog.dataset_file_sha256
    assert plan["dataset"]["revision"] == catalog.dataset_revision
    for path in reference_paths:
        assert path.startswith("reference_files/")
        assert not Path(path).is_absolute() and ".." not in Path(path).parts
        assert len(versions[path]) == 64
    assert report["developer_instructions_sha256"] == hashlib.sha256(
        historical["developer_instructions"].encode("utf-8")
    ).hexdigest()
    assert plan["instructions"] == {
        "source": HISTORICAL, "field": "developer_instructions", "policy": "copy_exactly",
    }
    assert plan["grading"] == {
        **historical["grading"],
        "policy_scope": "policy_blocks_not_full220_rerun_identity",
        "pin_semantics": "source_consistency_not_judge_accuracy",
    }
    assert plan["grading"]["pilot_expected_task_count"] == 5
    assert plan["grading"]["inference_revision"] is None
    assert plan["grading"]["reuse_baseline_rerun_identity"] is False
    assert plan["results"] == historical["results"]
    assert plan["results"]["publish_to_hf"] is False
    assert plan["results"]["submit_to_evals"] is False


def test_ghcp_vm_gate_contract_reset_capture_limits_and_cost_remain_unresolved(gate, plan):
    assert plan["vm"] == {
        "fresh_snapshot_per_task": True,
        "fresh_workdir_per_task": True,
        "prior_conversations_allowed": False,
        "prior_caches_allowed": False,
        "prior_outputs_allowed": False,
        "image_sha256": None,
        "os_sha256": None,
        "package_manifest_sha256": None,
        "version_policy": None,
    }
    assert plan["authentication"] == {
        "supply_method": None, "disposal_method": None, "identity_scope": None,
    }
    assert plan["execution"] == dict.fromkeys([
        "network_policy", "permission_policy", "timeout_seconds_per_task",
        "tool_calls_per_task", "turns_per_task", "retry_limit",
        "native_input_tokens_per_task", "native_output_tokens_per_task",
    ])
    assert plan["capture"] == {
        "required": ["transcript", "tool_calls", "commands", "input_file_hashes",
                     "output_file_hashes", "exit_status"],
        "credential_capture_allowed": False,
        "private_host_path_capture_allowed": False,
        "storage_policy": None,
    }
    assert plan["study"] == {
        "performance_comparison": False,
        "pool_with_foundry": False,
        "environment_only_causality": False,
        "repeats": None,
        "within_condition_spread": None,
        "pass_decision": "fresh_immutable_review_only_not_launch_approval",
        "failure_decision": "stop_before_spend",
    }
    assert plan["cost"] == {
        "policy": "record_cost_findings_only",
        "five_task_wallclock_seconds": None,
        "approved_maximum_usd": None,
    }
    assert plan["usage"] == {
        "source": "github_copilot_native_only",
        "missing_usage_execution_policy": None,
        "missing_or_unpriced": "preserve_null_and_partial_reasons",
        "infer_missing_as_zero": False,
        "use_foundry_or_openai_tariff": False,
        "invent_currency_conversion": False,
    }
    assert plan["results"]["missing_or_unpriced_usage"] == "preserve_null_and_partial_reasons"
    report = gate.inspect_plan(plan)
    assert report["observed"]["verified_usage"] is None
    assert report["launch_blockers"] == EXPECTED_BLOCKERS


@pytest.mark.parametrize(("section", "field", "replacement"), [
    ("identity", "provider", "azure_ai_foundry"),
    ("identity", "provider", "openai"),
    ("identity", "model", "gpt-5.6-fast"),
    ("identity", "model_label", "GPT-5.6 Fast"),
    ("identity", "fast_mode", True),
    ("identity", "harness", "personal_codex_login"),
    ("identity", "reasoning_effort", "high"),
    ("identity", "context_tier", "standard"),
    ("identity", "nominal_context_tokens", 1000000.0),
    ("identity", "capability_semantics", "verified"),
    ("identity", "fallbacks", ["personal_openai"]),
    ("dataset", "task_count", 220),
    ("dataset", "selector", "new_unreviewed_selector"),
    ("dataset", "revision", "0" * 40),
    ("dataset", "parquet_sha256", "0" * 64),
    ("dataset", "catalog_sha256", "0" * 64),
    ("dataset", "reference_policy", "optional"),
    ("dataset", "deliverable_policy", "modified"),
    ("instructions", "policy", "paraphrase"),
    ("grading", "source_sha", "0" * 40),
    ("grading", "rubric_revision", "0" * 40),
    ("grading", "prompt_version", "new_prompt"),
    ("grading", "judge_model", "gpt-5.6-fast"),
    ("grading", "judge_effort", "low"),
    ("grading", "passes_per_task", 2),
    ("grading", "pilot_expected_task_count", 220),
    ("vm", "fresh_snapshot_per_task", False),
    ("vm", "fresh_workdir_per_task", False),
    ("vm", "prior_conversations_allowed", True),
    ("vm", "prior_caches_allowed", True),
    ("vm", "prior_outputs_allowed", True),
    ("capture", "required", ["exit_status"]),
    ("capture", "credential_capture_allowed", True),
    ("capture", "private_host_path_capture_allowed", True),
    ("study", "pool_with_foundry", True),
    ("cost", "approved_maximum_usd", 0),
    ("usage", "source", "foundry"),
    ("usage", "missing_or_unpriced", "estimate"),
    ("usage", "infer_missing_as_zero", True),
    ("usage", "use_foundry_or_openai_tariff", True),
    ("usage", "invent_currency_conversion", True),
    ("results", "publish_to_hf", True),
])
def test_ghcp_vm_gate_contract_fixed_fields_refuse_drift(gate, plan, section, field, replacement):
    plan[section][field] = replacement
    assert_refused(gate.inspect_plan(plan))


def test_ghcp_vm_gate_contract_cli_is_canonical_read_only_and_nonzero(gate, plan, capsys):
    expected = gate.inspect_plan(plan)
    assert gate.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == json.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    assert captured.err == ""
    assert str(ROOT) not in captured.out
    assert "https://" not in captured.out
    assert "Authorization" not in captured.out
    assert "launch_command" not in expected


@pytest.mark.parametrize("value", [None, [], "invalid", 1, True])
def test_ghcp_vm_gate_contract_non_object_refusal(gate, value):
    assert_refused(gate.inspect_plan(value))


@pytest.mark.parametrize("name", FALSE_FLAGS)
def test_ghcp_vm_gate_contract_launch_flags_cannot_be_enabled(gate, plan, name):
    assert plan[name] is False
    plan[name] = True
    assert_refused(gate.inspect_plan(plan))


def test_ghcp_vm_gate_contract_missing_and_extra_root_fields(gate, plan):
    for key in tuple(plan):
        changed = deepcopy(plan)
        del changed[key]
        assert_refused(gate.inspect_plan(changed))
    plan["unreviewed_waiver"] = True
    assert_refused(gate.inspect_plan(plan))


@pytest.mark.parametrize("secret", [
    "sk-private-test-value", "Authorization: Bearer private-test-value",
    "https://private.invalid/api?token=private-test-value",
    "/home/private-user/credential.json",
])
def test_ghcp_vm_gate_contract_private_fields_are_refused_without_echo(gate, plan, secret):
    plan["private_input"] = secret
    report = gate.inspect_plan(plan)
    assert_refused(report)
    encoded = json.dumps(report)
    assert secret not in encoded
    assert "private-test-value" not in encoded
    assert "private-user" not in encoded


@pytest.mark.parametrize("arguments", [
    ["--token", "sk-private-test-value"],
    ["--plan"],
    ["--plan", "/private/missing/credential.json"],
    ["--endpoint=https://private.invalid/?token=private-test-value"],
])
def test_ghcp_vm_gate_contract_cli_refuses_without_argument_or_path_echo(gate, capsys, arguments):
    assert gate.main(arguments) == 2
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert_refused(report)
    assert captured.err == ""
    for forbidden_text in ("private", "sk-", "Authorization", "Traceback", str(ROOT)):
        assert forbidden_text not in captured.out


@pytest.mark.parametrize("payload", [
    b"", b"null\n", b"[]\n", b"plan_version: [unterminated\n",
    b"launch_enabled: true\nlaunch_enabled: false\n",
    b"identity: {model: first, model: second}\n",
    b"private: \xff\n", b"a: &loop {b: *loop}\n",
    b"a: &shared [1, 2]\nb: *shared\n",
    b"private: .nan\n", b"private: .inf\n", b"0: private\n",
    pytest.param(b"private: " + b"x" * 65536, id="oversize-plan"),
    b"private: !!python/object/apply:os.system ['private-command']\n",
])
def test_ghcp_vm_gate_contract_malformed_yaml_refusal(gate, tmp_path, capsys, payload):
    path = tmp_path / "private-plan.yaml"
    path.write_bytes(payload)
    assert gate.main(["--plan", str(path)]) == 2
    captured = capsys.readouterr()
    assert_refused(json.loads(captured.out))
    assert captured.err == ""
    for forbidden_text in ("private", str(tmp_path), "Traceback", "unterminated"):
        assert forbidden_text not in captured.out


def test_ghcp_vm_gate_contract_duplicate_yaml_keys_rejected_by_loader(gate, tmp_path):
    path = tmp_path / "duplicate.yaml"
    path.write_text("identity: {model: first, model: second}\n", encoding="utf-8")
    with pytest.raises(gate.GHCPVMGateRefused, match="^ghcp_vm_gate_refused$"):
        gate.load_plan(path)


@pytest.mark.parametrize("value", [0, None, "false"])
def test_ghcp_vm_gate_contract_false_flag_types_are_exact(gate, plan, value):
    plan["launch_enabled"] = value
    assert_refused(gate.inspect_plan(plan))


def test_ghcp_vm_gate_contract_source_pin_set_is_closed(gate, plan):
    assert set(plan["source_pins"]) == gate.REQUIRED_SOURCES
    assert plan["source_pins"][HISTORICAL] == HISTORICAL_SHA256
    first = next(iter(plan["source_pins"]))
    for mutation in ("missing", "extra", "digest"):
        changed = deepcopy(plan)
        if mutation == "missing":
            del changed["source_pins"][first]
        elif mutation == "extra":
            changed["source_pins"]["../../private/credential.json"] = "0" * 64
        else:
            changed["source_pins"][first] = "0" * 64
        report = gate.inspect_plan(changed)
        assert_refused(report)
        assert "private" not in json.dumps(report)


def test_ghcp_vm_gate_contract_bad_source_bytes_refused(gate, plan, tmp_path, monkeypatch):
    """Use fresh small source copies, never mutate a repository source."""
    source_root = tmp_path / "sources"
    for relative in gate.REQUIRED_SOURCES:
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    monkeypatch.setattr(gate, "ROOT", source_root)
    assert gate.inspect_plan(plan)["configuration_valid"] is True
    source = source_root / HISTORICAL
    before = source.read_bytes()
    source.write_bytes(before + b"\n# private-source-drift\n")
    report = gate.inspect_plan(plan)
    assert_refused(report)
    assert str(source_root) not in json.dumps(report)
    assert "private-source-drift" not in json.dumps(report)
    repinned = deepcopy(plan)
    repinned["source_pins"][HISTORICAL] = hashlib.sha256(source.read_bytes()).hexdigest()
    assert_refused(gate.inspect_plan(repinned))
    source.unlink()
    assert_refused(gate.inspect_plan(plan))
    assert hashlib.sha256((ROOT / HISTORICAL).read_bytes()).hexdigest() == HISTORICAL_SHA256


def test_ghcp_vm_gate_contract_unknowns_cannot_be_self_asserted(gate, plan):
    null_fields = [path for path, value in leaf_items(plan) if value is None]
    assert null_fields
    for path in null_fields:
        changed = deepcopy(plan)
        replace_at(changed, path, True)
        report = gate.inspect_plan(changed)
        assert report["configuration_valid"] is False, path
        assert_refused(report)


@pytest.mark.parametrize("relative_kind", ["symlink", "hardlink", "directory", "fifo"])
def test_ghcp_vm_gate_contract_non_regular_plan_refusal(gate, tmp_path, capsys, relative_kind):
    source = tmp_path / "source.yaml"
    source.write_bytes(gate.PLAN.read_bytes())
    path = tmp_path / "private-input"
    if relative_kind == "symlink":
        path.symlink_to(source)
    elif relative_kind == "hardlink":
        os.link(source, path)
    elif relative_kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path)
    assert gate.main(["--plan", str(path)]) == 2
    captured = capsys.readouterr()
    assert_refused(json.loads(captured.out))
    assert captured.err == ""
    assert "private-input" not in captured.out
    assert str(tmp_path) not in captured.out
