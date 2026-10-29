"""Fake host metadata/clients only; no model, login, Azure or token lookup."""

import copy
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from core import runner_environment as host
from core.codex_runner import CodexAgentRunner
from core.grade_payload import validate_grade_payload
from scripts import diagnose_codex_foundry_connection as diagnostic
import gpt56_pilot_wire_receipt as wire
import step8_grade as step8
import step2_run_inference as step2
from .test_gpt56_pilot_provider_observation import UPSTREAM, _upstream, _post, loopback_only


@pytest.mark.parametrize("version,image", [("22.04", "ubuntu22"), ("24.04", "ubuntu24")])
@pytest.mark.parametrize("machine,architecture", [("x86_64", "X64"), ("aarch64", "ARM64")])
def test_hosted_ubuntu_metadata_is_preserved(native_hosted_runner, monkeypatch, version, image, machine, architecture):
    monkeypatch.setenv("ImageOS", image)
    monkeypatch.setenv("RUNNER_ARCH", architecture)
    monkeypatch.setattr(host.platform, "freedesktop_os_release", lambda: {"ID": "ubuntu", "VERSION_ID": version})
    monkeypatch.setattr(host.platform, "machine", lambda: machine)
    observed = host.require_execution()
    assert observed["eligible_for_execution"] is True and observed["github_hosted"] is True
    assert observed["runner_environment"] == "github-hosted"
    assert observed["image_os"] == image and observed["image_version"] == "20261026.354.1"
    assert observed["runner_os"] == "Linux" and observed["runner_arch"] == architecture
    assert (observed["run_id"], observed["run_attempt"]) == ("123456789", "1")
    for stage in ("diagnostic", "inference", "grading"):
        host.validate_receipt(host.receipt(stage, observed))


@pytest.mark.parametrize("name,value", [
    ("GITHUB_ACTIONS", None), ("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted"),
    ("RUNNER_OS", "Windows"), ("RUNNER_ARCH", "ARM64"), ("ImageOS", "ubuntu24"),
    ("ImageVersion", None), ("ImageVersion", "not available"), ("RUNNER_NAME", None),
    ("GITHUB_RUN_ID", "0"), ("GITHUB_RUN_ID", None), ("GITHUB_RUN_ATTEMPT", "0"),
])
def test_absent_inconsistent_or_self_hosted_metadata_refuses(native_hosted_runner, monkeypatch, name, value):
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(host.ExecutionEnvironmentRefused, match="^execution_environment_refused$"):
        host.require_execution()
    assert host.observe()["eligible_for_execution"] is False


def test_labels_do_not_override_actual_os(native_hosted_runner, monkeypatch):
    monkeypatch.setattr(host.platform, "freedesktop_os_release", lambda: {"ID": "debian", "VERSION_ID": "12"})
    assert host.observe()["eligible_for_execution"] is False


@pytest.mark.parametrize("case", ["missing_marker", "missing_approval", "wrong_vm", "valid"])
def test_azure_vm_requires_explicit_approval_and_matching_dmi(native_hosted_runner, monkeypatch, case):
    for name in native_hosted_runner:
        monkeypatch.delenv(name)
    vm_id = "12345678-1234-1234-1234-123456789012"
    monkeypatch.setenv("NATIVE_AZURE_VM_APPROVAL", "owner-approved")
    monkeypatch.setenv("NATIVE_AZURE_VM_APPROVAL_SHA256", "a" * 64)
    monkeypatch.setenv("NATIVE_AZURE_VM_ID", vm_id)
    monkeypatch.setattr(host, "_azure_dmi", lambda: vm_id)
    if case == "missing_marker": monkeypatch.delenv("NATIVE_AZURE_VM_APPROVAL")
    if case == "missing_approval": monkeypatch.delenv("NATIVE_AZURE_VM_APPROVAL_SHA256")
    if case == "wrong_vm": monkeypatch.setattr(host, "_azure_dmi", lambda: None)
    observed = host.observe()
    assert observed["approved_azure_vm"] is (case == "valid")
    assert observed["eligible_for_execution"] is (case == "valid")
    assert observed["github_hosted"] is False


def test_capture_never_reads_a_credential_value(native_hosted_runner, monkeypatch):
    fields = dict(native_hosted_runner)
    class MetadataOnly:
        def get(self, key, default=None):
            assert key in fields or key.startswith("NATIVE_AZURE_VM_"), "unapproved environment lookup"
            return fields.get(key, default)
    with monkeypatch.context() as isolated:
        isolated.setattr(os, "environ", MetadataOnly())
        assert host.require_execution()["eligible_for_execution"] is True


def test_receipt_tampering_and_mid_run_drift_are_refused(native_hosted_runner, monkeypatch):
    first = host.require_execution()
    record = host.receipt("grading", first)
    record["observation"] = copy.deepcopy(record["observation"])
    record["observation"]["run_attempt"] = "2"
    with pytest.raises(ValueError, match="runner_receipt_refused"):
        host.validate_receipt(record)
    monkeypatch.setenv("ImageVersion", "20261029.1.0")
    with pytest.raises(host.ExecutionEnvironmentRefused, match="execution_environment_changed"):
        host.require_execution(first)


def test_diagnostic_refuses_before_settings_auth_or_runtime(tmp_path, monkeypatch, native_hosted_runner, capsys):
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    def forbidden(*args, **kwargs):
        pytest.fail("unapproved diagnostic reached settings/auth/runtime")
    monkeypatch.setattr(diagnostic, "settings_from_environment", forbidden)
    monkeypatch.setattr(diagnostic, "build_redactor", forbidden)
    out = tmp_path / "diagnostic.json"
    assert diagnostic.main(["--deployment", "gpt-5.6-sol", "--send-request", "--out", str(out)]) == 2
    record = json.loads(out.read_text())
    assert record["verdict"] == host.REFUSED and record["observed"]["turn_sent"] is False
    host.validate_receipt(record["runner_evidence"])
    assert record["runner_evidence"]["observation"]["eligible_for_execution"] is False


def test_native_run_and_open_runtime_stop_before_auth_or_sdk(native_hosted_runner, monkeypatch):
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    runner = CodexAgentRunner.__new__(CodexAgentRunner)
    monkeypatch.setattr(runner, "_run", lambda **kw: pytest.fail("unapproved host began a task"))
    monkeypatch.setattr(runner, "require_a_usable_auth_command", lambda *a: pytest.fail("auth ran"))
    result = runner.run("synthetic task")
    assert result["success"] is False and result["error_category"] == host.REFUSED
    host.validate_receipt(result["runner_evidence"])
    with pytest.raises(host.ExecutionEnvironmentRefused):
        runner.open_runtime(SimpleNamespace())


def test_native_result_binds_the_observed_host(native_hosted_runner, monkeypatch):
    runner = CodexAgentRunner.__new__(CodexAgentRunner)
    monkeypatch.setattr(runner, "_run", lambda **kw: {"success": True})
    result = runner.run("synthetic task")
    assert result["success"] is True
    assert result["runner_evidence"] == host.receipt("inference")


def test_upstream_guard_stops_before_a_model_request(native_hosted_runner, monkeypatch):
    with _upstream(monkeypatch, []) as (received, _):
        observer = wire._ProviderHTTPObservation(UPSTREAM, 60)
        try:
            monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
            code, _ = _post(observer.base_url)
            assert code == 400 and received == []
        finally:
            observer.close()
        result = observer.summary()
    assert result["native_request_count"] == 0
    assert result["runtime_caps"]["stop_reason"] == host.REFUSED
    assert result["native_request_blocked_count"] == 1


@pytest.mark.parametrize("surface", ["responses", "chat", "normalized"])
def test_grading_guard_cannot_be_swallowed_as_judge_error(native_hosted_runner, monkeypatch, surface):
    seen = []
    create = lambda **kwargs: seen.append(kwargs) or "synthetic response"
    inner = SimpleNamespace(responses=SimpleNamespace(create=create),
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)), chat_complete=create)
    client = host.GuardedGradingClient(inner)
    call = {"responses": client.responses.create, "chat": client.chat.completions.create,
            "normalized": client.chat_complete}[surface]
    assert call(model="fake") == "synthetic response"
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    with pytest.raises(host.GradingEnvironmentStopped) as caught:
        try:
            call(model="fake")
        except Exception:
            pytest.fail("host stop could become a rubric verdict")
    assert len(seen) == 1 and caught.value.code == host.REFUSED
    host.validate_receipt(caught.value.runner_evidence)


def test_step8_refuses_before_config_or_judge_and_writes_only_a_receipt(native_hosted_runner, monkeypatch, tmp_path):
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(step8, "parse_args", lambda: SimpleNamespace(dry_run=False))
    monkeypatch.setattr(step8, "Grader", lambda *a, **kw: pytest.fail("judge initialized"))
    assert step8.main() == 4
    reports = list((tmp_path / "workspace/runner-receipts").glob("*.json"))
    assert len(reports) == 1
    record = json.loads(reports[0].read_text())
    assert record["status"] == "refused" and record["reason"] == host.REFUSED
    assert "tasks" not in record and not (tmp_path / "data/grades").exists()
    host.validate_receipt(record["runner_evidence"])


def test_grade_payload_validates_added_evidence_without_changing_legacy_cost_schema(native_hosted_runner):
    # Isolate the additive receipt check; other legacy validations remain intact.
    value = {"runner_evidence": host.receipt("grading")}
    validate_grade_payload(value, {})
    value["runner_evidence"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="runner_receipt_refused"):
        validate_grade_payload(value, {})


def test_step2_preserves_inference_runner_receipt_and_rejects_wrong_stage(native_hosted_runner):
    record = host.receipt("inference")
    assert step2._build_execution_observability({"runner_evidence": record}, [])["runner_evidence"] == record
    with pytest.raises(ValueError, match="inference runner receipt stage"):
        step2._build_execution_observability({"runner_evidence": host.receipt("grading")}, [])


def test_receipt_shape_is_checked_even_with_a_recomputed_hash(native_hosted_runner):
    observation = host.observe()
    observation["runner_os"] = True
    with pytest.raises(ValueError, match="runner_receipt_refused"):
        host.validate_receipt(host.receipt("inference", observation))
