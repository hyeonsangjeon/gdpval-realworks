"""Tiny model-free JUnit/receipt fixtures; never execute the real platform probe."""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import xml.etree.ElementTree as ET

import pytest
import yaml

from . import test_a_test_file_nobody_runs_is_not_a_test as contracts

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_time_budget_owned_host_ci.py"
SPEC = importlib.util.spec_from_file_location("owned_host_ci", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
SHA = "1" * 40
TREE = "2" * 40
POSITIVE = {"platform_result": "real_reparenting_confirmed", "host_reusable": True}
REFUSED = {"platform_result": "admission_refused", "host_reusable": False,
           "reason": "time_budget_owned_process_host_required", "cause_type": "FileNotFoundError", "errno": 2}


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("synthetic CI receipt test attempted a process or network operation")

    for name in ("run", "Popen", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def junit(case="positive"):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", tests="1", errors="0", failures="0", skipped="0")
    node = ET.SubElement(suite, "testcase", classname=gate.CASE_CLASS, name=gate.CASE_NAME, time="0.01")
    properties = ET.SubElement(node, "properties")
    prop = ET.SubElement(properties, "property", name=gate.PROPERTY,
                         value=json.dumps(REFUSED if case == "refused" else POSITIVE))
    ET.SubElement(node, "system-out").text = "FAKE_BODY_MUST_NOT_BE_RETAINED"
    if case == "missing":
        suite.remove(node)
    elif case == "duplicate":
        suite.append(deepcopy(node))
    elif case == "missing_property":
        properties.remove(prop)
    elif case == "duplicate_property":
        properties.append(deepcopy(prop))
    elif case == "wrong_case":
        node.set("classname", "other_source")
    elif case in {"skipped", "error", "failure"}:
        ET.SubElement(node, case).text = "FAKE_ERROR_MUST_NOT_BE_RETAINED"
    elif case == "missing_time":
        del node.attrib["time"]
    elif case == "malformed":
        prop.set("value", "not-json FAKE_SECRET")
    elif case == "extra_field":
        prop.set("value", json.dumps({**POSITIVE, "private_body": "FAKE_SECRET"}))
    elif case == "false_reusable":
        prop.set("value", json.dumps({**POSITIVE, "host_reusable": False}))
    elif case == "string_reusable":
        prop.set("value", json.dumps({**POSITIVE, "host_reusable": "true"}))
    elif case == "duplicate_json_key":
        prop.set("value", '{"platform_result":"real_reparenting_confirmed","host_reusable":false,"host_reusable":true}')
    return ET.tostring(root)


@pytest.mark.parametrize("case,reason", [
    ("positive", None), ("refused", None),
    ("missing", "platform_case_count"), ("duplicate", "platform_case_count"),
    ("missing_property", "platform_property_count"), ("duplicate_property", "platform_property_count"),
    ("wrong_case", "platform_case_identity"),
    ("skipped", "platform_case_not_completed"), ("error", "platform_case_not_completed"),
    ("failure", "platform_case_not_completed"), ("missing_time", "platform_case_not_completed"),
    ("malformed", "platform_outcome_malformed"), ("extra_field", "platform_outcome_malformed"),
    ("false_reusable", "platform_outcome_malformed"), ("string_reusable", "platform_outcome_malformed"),
    ("duplicate_json_key", "platform_outcome_malformed"),
])
def test_owned_host_ci_outcome(case, reason):
    if reason:
        with pytest.raises(gate.PlatformEvidenceRefused, match="^" + reason + "$"):
            gate.extract_outcome(junit(case))
    else:
        assert gate.extract_outcome(junit(case)) == (REFUSED if case == "refused" else POSITIVE)


@pytest.mark.parametrize("report", [b"not-xml", b"<!DOCTYPE x><testsuites/>", b"\x00<testsuites/>"])
def test_owned_host_ci_malformed_xml(report):
    with pytest.raises(gate.PlatformEvidenceRefused, match="^junit_malformed$"):
        gate.extract_outcome(report)


def arguments(tmp_path):
    report, summary = tmp_path / "report.xml", tmp_path / "summary.md"
    return ["--junit", str(report), "--summary", str(summary), "--expected-sha", SHA,
            "--run-id", "123", "--run-attempt", "2", "--job", "comparison-contracts",
            "--test-outcome", "success", "--runner-name", "Synthetic Runner",
            "--runner-os", "Linux", "--runner-arch", "X64", "--runner-environment", "github-hosted"]


@pytest.mark.parametrize("case", ["positive", "refused", "missing", "duplicate", "malformed", "error"])
def test_owned_host_ci_receipt(case, tmp_path, monkeypatch, capsys):
    (tmp_path / "report.xml").write_bytes(junit(case))
    anchors = []

    def source(expected):
        anchors.append(expected)
        return {"commit": SHA, "tree": TREE}

    monkeypatch.setattr(gate, "checked_source", source)
    assert gate.main(arguments(tmp_path)) == (0 if case == "positive" else 1)
    printed = capsys.readouterr().out
    receipt = json.loads(printed)
    assert anchors and set(anchors) == {SHA}
    assert receipt["gate_passed"] is receipt["host_reusable"] is (case == "positive")
    assert receipt["synthetic"] is receipt["model_free"] is True
    assert receipt["study_observation"] is receipt["live_authorization"] is False
    assert receipt["provenance"] == {
        "source": {"commit": SHA, "tree": TREE}, "run_id": "123", "run_attempt": "2",
        "job": "comparison-contracts", "runner": {"os": "Linux", "arch": "X64",
        "environment": "github-hosted", "name_sha256": hashlib.sha256(b"Synthetic Runner").hexdigest()},
    }
    summary = (tmp_path / "summary.md").read_text()
    assert summary == "```json\n" + printed.rstrip() + "\n```\n"
    assert len(summary.encode()) < gate.RECEIPT_LIMIT
    assert "FAKE_" not in summary and "Synthetic Runner" not in summary and str(tmp_path) not in summary
    if case == "refused":
        assert receipt["platform_outcome"] == REFUSED
        assert receipt["refusal_reason"] == "platform_admission_refused"


@pytest.mark.parametrize("case,reason", [
    ("positive", None), ("anchor", "source_anchor_mismatch"),
    ("malformed_anchor", "source_anchor_invalid"), ("tree", "source_tree_invalid"),
    ("dirty", "source_verification_failed"), ("race", "source_identity_changed"),
    ("timeout", "source_verification_failed"),
])
def test_owned_host_ci_source(case, reason, monkeypatch):
    commands = []

    def git(command, **kwargs):
        commands.append(command)
        assert command[:2] == ["/usr/bin/git", "--no-replace-objects"]
        assert command[2:6] == ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null"]
        assert kwargs["timeout"] == 5 and kwargs["env"]["GIT_ALLOW_PROTOCOL"] == ""
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        assert "FAKE_CREDENTIAL" not in kwargs["env"]
        tail = command[command.index("-C") + 2:]
        if case == "timeout":
            raise subprocess.TimeoutExpired(command, 5, output=b"FAKE_SECRET")
        if tail == ["rev-parse", "--verify", "HEAD^{commit}"]:
            value = "3" * 40 if case == "anchor" or case == "race" and len(commands) == 4 else SHA
        elif tail == ["rev-parse", "--verify", SHA + "^{tree}"]:
            value = "invalid" if case == "tree" else TREE
        else:
            assert tail == ["diff", "--quiet", "--no-ext-diff", "--no-textconv", SHA, "--"]
            return subprocess.CompletedProcess(command, 1 if case == "dirty" else 0, b"", b"FAKE_SECRET")
        return subprocess.CompletedProcess(command, 0, (value + "\n").encode(), b"")

    monkeypatch.setenv("FAKE_CREDENTIAL", "not-for-receipt-or-git")
    monkeypatch.setattr(gate.subprocess, "run", git)
    expected = "main" if case == "malformed_anchor" else SHA
    if reason:
        with pytest.raises(gate.PlatformEvidenceRefused, match="^" + reason + "$"):
            gate.checked_source(expected)
    else:
        assert gate.checked_source(expected) == {"commit": SHA, "tree": TREE}
        assert len(commands) == 4
    if case == "malformed_anchor":
        assert commands == []


@pytest.mark.parametrize("option,value,reason", [
    ("--run-id", "0", "ci_identity_invalid"),
    ("--runner-os", "Windows", "ci_identity_invalid"),
    ("--test-outcome", "failure", "comparison_step_not_successful"),
    ("--test-outcome", "skipped", "comparison_step_not_successful"),
])
def test_owned_host_ci_invalid_provenance_or_uncompleted_step(option, value, reason, tmp_path, monkeypatch, capsys):
    args = arguments(tmp_path)
    args[args.index(option) + 1] = value
    monkeypatch.setattr(gate, "checked_source", lambda expected: {"commit": SHA, "tree": TREE})
    monkeypatch.setattr(gate, "read_report", lambda path: pytest.fail("must refuse before reading a report"))
    assert gate.main(args) == 1
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["refusal_reason"] == reason
    assert receipt["gate_passed"] is receipt["host_reusable"] is False
    assert "platform_outcome" not in receipt


def test_owned_host_ci_final_source_reread(tmp_path, monkeypatch, capsys):
    (tmp_path / "report.xml").write_bytes(junit())
    sources = iter(({"commit": SHA, "tree": TREE}, {"commit": "3" * 40, "tree": TREE}))
    monkeypatch.setattr(gate, "checked_source", lambda expected: next(sources))
    assert gate.main(arguments(tmp_path)) == 1
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["refusal_reason"] == "source_identity_changed"
    assert receipt["gate_passed"] is receipt["host_reusable"] is False
    assert "platform_outcome" not in receipt


def test_owned_host_ci_report_bounds_and_missing_file(tmp_path, monkeypatch):
    path = tmp_path / "report.xml"
    with pytest.raises(gate.PlatformEvidenceRefused, match="^junit_unavailable$"):
        gate.read_report(path)
    path.write_bytes(b"123456789")
    monkeypatch.setattr(gate, "JUNIT_LIMIT", 8)
    with pytest.raises(gate.PlatformEvidenceRefused, match="^junit_size_limit$"):
        gate.read_report(path)
    link = tmp_path / "report-link.xml"
    link.symlink_to(path)
    with pytest.raises(gate.PlatformEvidenceRefused, match="^junit_unavailable$"):
        gate.read_report(link)


def test_owned_host_ci_workflow_one_probe_and_exact_reconstruction():
    workflow = yaml.safe_load(contracts.WORKFLOW.read_text())
    previous = contracts._without_owned_host_ci_evidence(workflow)
    current_steps = workflow["jobs"]["comparison-contracts"]["steps"]
    old_steps = previous["jobs"]["comparison-contracts"]["steps"]
    assert current_steps[:6] == old_steps[:6]
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["comparison-contracts"]["timeout-minutes"] == 45
    assert sum("python -m pytest" in step.get("run", "") for step in current_steps) == 1
    selected = contracts._pytest_target_arguments(contracts.shlex.split(current_steps[6]["run"].splitlines()[2])[3:])
    assert selected.count("tests/test_gpt54_time_budget_comparison.py") == 1
    assert len(selected) == len(set(selected)) == 12
    assert contracts._pytest_target_arguments(["--junitxml", "report.xml", "-o", "junit_family=xunit1"]) == []
    for option in ("--junitxml", "-o"):
        with pytest.raises(AssertionError, match="missing pytest option value"):
            contracts._pytest_target_arguments([option])
    assert "--ignore=tests/test_gpt54_time_budget_comparison.py" in workflow["jobs"]["pytest"]["steps"][6]["run"]
    for job in workflow["jobs"]:
        if job != "comparison-contracts":
            assert workflow["jobs"][job] == previous["jobs"][job]
    probe_path = contracts.REPO_ROOT / "batch-runner/tests/test_gpt54_time_budget_comparison.py"
    probe = next(node for node in ast.parse(probe_path.read_text()).body
                 if isinstance(node, ast.FunctionDef) and node.name == gate.CASE_NAME)
    assert "record_property" in [argument.arg for argument in probe.args.args]
    calls = [node for node in ast.walk(probe) if isinstance(node, ast.Call)]
    assert sum(isinstance(call.func, ast.Name) and call.func.id == "_REAL_POPEN" for call in calls) == 1
    properties = [call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "record_property"]
    assert len(properties) == 1 and properties[0].args[0].value == gate.PROPERTY
    assert sorted(keyword.value.value for call in calls for keyword in call.keywords
                  if keyword.arg == "timeout") == [2, 10]
    assert any(isinstance(node, ast.Constant) and isinstance(node.value, str)
               and "signal.alarm(5)" in node.value for node in ast.walk(probe))


@pytest.mark.parametrize("case", ["duplicate_step", "weaken_condition", "extra_junit_option", "lost_no_clobber"])
def test_owned_host_ci_reconstruction_refuses_unreviewed_changes(case):
    workflow = yaml.safe_load(contracts.WORKFLOW.read_text())
    steps = workflow["jobs"]["comparison-contracts"]["steps"]
    if case == "duplicate_step":
        steps.append(deepcopy(steps[-1]))
    elif case == "weaken_condition":
        steps[-1]["if"] = "false"
    elif case == "extra_junit_option":
        steps[-2]["run"] += " --junitxml=other.xml\n"
    else:
        steps[-2]["run"] = steps[-2]["run"].replace(contracts.OWNED_HOST_JUNIT_GUARD + "\n", "")
    with pytest.raises(AssertionError):
        contracts._without_owned_host_ci_evidence(workflow)
