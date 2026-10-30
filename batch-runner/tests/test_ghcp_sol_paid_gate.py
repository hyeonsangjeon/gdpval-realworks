"""Dispatch/source/secret/capture tests: fake executable and fake credential only."""

import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import ghcp_sol_actions_gate as gate
import ghcp_sol_execution_adapter as adapter
import ghcp_sol_grader_contract as bridge
import ghcp_sol_paid_gate as paid

ROOT = Path(__file__).resolve().parents[2]
CANARY = "FAKE_PAID_AUTH_CANARY_97531_NOT_A_CREDENTIAL"
CONDITION = "github.event_name == 'workflow_dispatch' && inputs.execute_paid == true && inputs.dry_run == false"
TASK_CONDITION = ("always() && !cancelled() && " + CONDITION + " && inputs.connection_only != true && "
                  "needs.plan.result == 'success' && (inputs.execution_adapter != 'ahp-draft' || "
                  "(needs.ahp-connection.result == 'success' && needs.ahp-connection.outputs.verified == 'true'))")


def _workflow():
    return yaml.load((ROOT / ".github/workflows/agentic-v2-ghcp-sol-gate.yml").read_text(), Loader=yaml.BaseLoader)


@pytest.mark.parametrize("event", ["push", "pull_request", "workflow_dispatch", "workflow_run", "schedule"])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("dry", [False, True])
def test_paid_job_event_truth_table_from_yaml(event, enabled, dry):
    job = _workflow()["jobs"]["paid-task"]
    expression = job["if"].removeprefix("${{ ").removesuffix(" }}")
    assert expression == TASK_CONDITION
    # Only this exact three-clause expression is accepted; no general YAML eval.
    observed = all((event == "workflow_dispatch", enabled is True, dry is False))
    assert observed is (event == "workflow_dispatch" and enabled and not dry)
    if event in {"push", "pull_request"}:
        assert observed is False


def test_secret_references_only_in_protected_connection_and_task_runtime_steps():
    workflow = _workflow()
    assert workflow["on"]["workflow_dispatch"]["inputs"]["execute_paid"]["default"] == "false"
    jobs = workflow["jobs"]
    secret_jobs = [name for name, job in jobs.items() if "secrets." in yaml.dump(job)]
    assert secret_jobs == ["ahp-connection", "paid-task"]
    job = jobs["paid-task"]
    assert job["environment"] == "ghcp-sol-gate" and job["runs-on"] == "ubuntu-24.04"
    assert job["needs"] == ["plan", "ahp-connection"] and job["timeout-minutes"] == "25"
    assert job["strategy"] == {"fail-fast": "true", "max-parallel": "1",
                               "matrix": "${{ fromJSON(needs.plan.outputs.matrix) }}"}
    selected = [step for step in job["steps"] if "secrets." in yaml.dump(step)]
    assert len(selected) == 1
    assert selected[0]["env"] == {"COPILOT_GITHUB_TOKEN": "${{ secrets.COPILOT_GITHUB_TOKEN }}",
                                   "TASK_ID": "${{ matrix.task_id }}"}
    assert "ghcp_sol_paid_gate.py --task-id" in selected[0]["run"]
    assert "1230s" in selected[0]["run"]
    for other in ("offline-ci", "plan", "task", "grader-contract"):
        assert jobs[other]["steps"][0]["env"] == {"DRY_RUN": "true"}
        assert "secrets." not in yaml.dump(jobs[other])
    assert jobs["grader-contract"]["needs"] == ["task", "paid-task"]
    assert job["steps"][-1]["with"]["path"] == "${{ runner.temp }}/ghcp-paid-export"


@pytest.fixture
def runtime(tmp_path, monkeypatch, github_hosted_ubuntu_2404):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GHCP_PAID_EXECUTION", "true")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", CANARY)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "parent-home")
    for name in ("GH_TOKEN", "GITHUB_TOKEN", "COPILOT_HOME", "COPILOT_MODEL"):
        monkeypatch.delenv(name, raising=False)
    def no_network(*args, **kwargs):
        pytest.fail("offline test attempted network")
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    materials = {"prompt": "EXACT DEVELOPER\nEXACT TASK", "references": {},
                 "identity": {"reference_sha256": {}, "prompt_sha256": "a" * 64}}
    monkeypatch.setattr(paid, "task_materials", lambda *args: materials)
    binary = tmp_path / "fake-copilot"
    binary.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
assert args[args.index('-p') + 1] == 'EXACT DEVELOPER\\nEXACT TASK'
assert args[args.index('--model')+1] == 'gpt-5.6-sol'
assert args[args.index('--reasoning-effort')+1] == 'max'
assert args[args.index('--context')+1] == 'long_context'
assert '--allow-all-tools' in args and '--allow-all-paths' not in args
assert 'GH_TOKEN' not in os.environ and 'GITHUB_TOKEN' not in os.environ
assert '--secret-env-vars=COPILOT_GITHUB_TOKEN,GH_TOKEN,GITHUB_TOKEN' in args
def event(kind, data, **more):
    print(json.dumps(dict(type=kind, data=data, **more)), flush=True)
event('session.start', {'sessionId':'fake'})
event('session.usage_info', {'tokenLimit':1000000})
event('assistant.turn_start', {'turnId':'1'})
event('tool.execution_start', {'toolCallId':'1'})
Path('answer.txt').write_text('synthetic deliverable')
event('assistant.message', {'content':'SYNTHETIC FINISHED TASK'})
event('assistant.usage', {'model':'gpt-5.6-sol', 'reasoningEffort':'max', 'inputTokens':4, 'outputTokens':1}, id='call1')
Path(args[args.index('--usage-output-file')+1]).write_text('{"inputTokens":4,"outputTokens":1}')
print(json.dumps({'type':'result', 'timestamp':'2026-10-29T00:00:00Z', 'sessionId':'fake', 'exitCode':0, 'usage':{}}), flush=True)
''')
    binary.chmod(0o700)
    monkeypatch.setattr(adapter, "COPILOT_CLI_SHA256", hashlib.sha256(binary.read_bytes()).hexdigest())
    original = subprocess.Popen
    def fake_only(command, *args, **kwargs):
        assert command[0] == str(binary), "non-fixture executable refused"
        return original(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", fake_only)
    return binary


def _run(binary, tmp_path, task=gate.TASK_IDS[0], name="export"):
    return paid.execute_task(task, binary, tmp_path / "bundle", tmp_path / (name + "-state"), tmp_path / name)


@pytest.mark.parametrize("task", gate.TASK_IDS)
def test_each_fixed_task_uses_real_supervisor_and_captures_without_secret(runtime, tmp_path, task):
    record = _run(runtime, tmp_path, task)
    assert record["ready_for_contract"] is True, record
    receipt = record["execution_receipt"]
    assert receipt["settings_verification"] == "verified" and receipt["metadata_gate_passed"] is True
    assert receipt["limits"]["timeout_seconds"] == 1200 and receipt["limits"]["max_turns"] == 64
    assert receipt["limits"]["max_tool_calls"] == 32
    assert receipt["cleanup"]["leader_reaped"] is True
    assert record["output_files"] == [{"path": "answer.txt", **paid._identity(b"synthetic deliverable")}]
    for path in (tmp_path / "export").rglob("*"):
        if path.is_file():
            assert CANARY.encode() not in path.read_bytes()


@pytest.mark.parametrize("value", [None, "", " " ])
def test_missing_or_empty_secret_refuses_before_cli(runtime, tmp_path, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN")
    else:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", value)
    monkeypatch.setattr(adapter, "run_task", lambda *a, **kw: pytest.fail("missing secret reached supervisor"))
    record = _run(runtime, tmp_path)
    assert record["ready_for_contract"] is False and record["reason_codes"] == ["auth_source_unavailable"]
    assert not (tmp_path / "export-state").exists()


@pytest.mark.parametrize("value", [None, "", " ", CANARY])
def test_ahp_draft_never_starts_a_host_or_falls_back_to_copilot(runtime, tmp_path, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN")
    else:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", value)
    def forbidden(*args, **kwargs):
        pytest.fail("AHP draft attempted a CLI, input load or real host")
    monkeypatch.setattr(adapter, "run_task", forbidden)
    monkeypatch.setattr(paid, "task_materials", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    record = paid.execute_task(gate.TASK_IDS[0], runtime, tmp_path / "absent-bundle",
                               tmp_path / "absent-state", tmp_path / "export", execution_adapter="ahp-draft")
    assert not record["ready_for_contract"]
    expected = "connection_verification_required" if value == CANARY else "auth_source_unavailable"
    assert record["reason_codes"] == [expected]
    assert not (tmp_path / "absent-state").exists()
    assert CANARY not in (tmp_path / "export/capture.json").read_text()
    if value == CANARY:
        assert "execution_receipt" not in record  # No task adapter entered before connection admission.


@pytest.mark.parametrize("name,value", [("GITHUB_EVENT_NAME", "push"), ("GITHUB_EVENT_NAME", "pull_request"),
    ("GHCP_PAID_EXECUTION", "false"), ("GITHUB_RUN_ATTEMPT", "2"), ("RUNNER_ENVIRONMENT", "self-hosted")])
def test_unapproved_event_or_host_cannot_reach_auth(runtime, tmp_path, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(adapter, "_selected_auth_environment", lambda *a, **kw: pytest.fail("reached auth"))
    record = _run(runtime, tmp_path)
    assert record["ready_for_contract"] is False and record["reason_codes"]
    assert not (tmp_path / "export-state").exists() and not (tmp_path / "export").exists()


def test_existing_output_not_adopted(runtime, tmp_path):
    (tmp_path / "export").mkdir()
    assert _run(runtime, tmp_path)["reason_codes"] == ["paid_capture_destination_refused"]
    assert list((tmp_path / "export").iterdir()) == []


@pytest.mark.parametrize("case", ["secret_file", "symlink", "missing_settings"])
def test_bad_paid_outputs_are_not_published(runtime, tmp_path, monkeypatch, case):
    original = adapter.run_task
    def changed(*args, **kwargs):
        receipt = original(*args, **kwargs)
        work = tmp_path / "export-state" / gate.TASK_IDS[0] / "private/files"
        if case == "secret_file": (work / "answer.txt").write_text(CANARY)
        elif case == "symlink": (work / "linked.txt").symlink_to(work / "answer.txt")
        else: receipt["metadata_gate_passed"] = False
        return receipt
    monkeypatch.setattr(adapter, "run_task", changed)
    record = _run(runtime, tmp_path)
    assert record["ready_for_contract"] is False
    assert not (tmp_path / "export/files").exists()
    for path in (tmp_path / "export").rglob("*"):
        if path.is_file(): assert CANARY.encode() not in path.read_bytes()


def test_paid_captures_reach_existing_step8_validators_without_judge(runtime, tmp_path):
    captures = tmp_path / "captures"
    captures.mkdir()
    for index, task in enumerate(gate.TASK_IDS):
        record = _run(runtime, tmp_path, task, "task-" + str(index))
        assert record["ready_for_contract"] is True, record
        (tmp_path / ("task-" + str(index))).rename(captures / ("ghcp-sol-paid-capture-" + task))
    result = bridge.convert_and_validate(captures, tmp_path / "step8", mode="paid")
    assert result["exit_status"] == 0, result
    assert result["status"] == "paid_capture_layout_verified"
    assert result["step8_layout_valid"] is result["grader_policy_valid"] is True
    assert result["ready_for_grading"] is result["gate5_passed"] is False
    manifest = json.loads((tmp_path / "step8" / bridge.MANIFEST).read_text())
    assert manifest["inference_performed"] is True and manifest["source_revision"] is None
    assert all(row["status"] == "success" and len(row["deliverable_files"]) == 1 for row in manifest["results"])
    (captures / ("ghcp-sol-paid-capture-" + gate.TASK_IDS[0]) / "files/answer.txt").write_text("changed")
    refused = bridge.convert_and_validate(captures, tmp_path / "step8-bad", mode="paid")
    assert refused["exit_status"] == 2 and refused["step8_layout_valid"] is False


def test_public_input_preparation_is_exactly_revision_and_hash_bound(runtime, tmp_path, monkeypatch):
    downloads = []
    monkeypatch.setattr(paid, "_download", lambda url, destination, digest: downloads.append((url, digest)))
    called = []
    monkeypatch.setattr(paid.inputs, "materialize_ghcp_input_bundle", lambda *a, **kw: called.append(kw))
    paid.prepare_inputs(tmp_path / "inputs")
    assert len(downloads) == 3 and len(called) == 1
    assert all(url.startswith("https://huggingface.co/datasets/openai/gdpval/resolve/11e7900cdcac61bc4daf59e65feb238acda98fbf/")
               and len(digest) == 64 for url, digest in downloads)
    assert called[0]["reviewed_plan_sha256"] == paid._plan()[1]["plan_sha256"]
