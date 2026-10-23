"""Free plan/capture checks; no dataset, handoff, model or network access."""

import json
import socket
import subprocess
from pathlib import Path

import pytest
import yaml

import ghcp_sol_actions_gate as gate


def test_fixed_plan_and_all_five_captures(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("network or child process attempted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    read_bytes = Path.read_bytes

    def public_only(path):
        assert path == gate.CATALOG_PATH, "non-catalog input read attempted"
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", public_only)
    assert gate.main(["--matrix"]) == 0
    matrix = json.loads(capsys.readouterr().out)
    assert matrix == {"task_id": list(gate.TASK_IDS)}
    root = tmp_path / "capture"
    for task_id in matrix["task_id"]:
        assert gate.main(["--task-id", task_id, "--state-root", str(root)]) == 0
        task_root = root / task_id
        envelope = json.loads((task_root / "capture.json").read_text())
        assert envelope["requested"] == gate.REQUESTED
        assert set(envelope["actual_served"].values()) == {"not available"}
        assert envelope["model_calls"] == envelope["grader_calls"] == 0
        assert envelope["paid_execution_allowed"] is False
        assert envelope["limits"]["proposed_paid_timeout_seconds_per_task"] == 1200
        assert envelope["limits"]["proposed_paid_max_turns_per_task"] == 64
        assert envelope["limits"]["dry_run_max_model_turns"] == 0
        assert envelope["versions"]["ghcp_cli"] == "not available"
        assert envelope["versions"]["codex_cli"] == "not available"
        assert envelope["versions"]["python"]
        assert envelope["usage"] is envelope["cost"] is envelope["grade"] is None
        capture = envelope["capture"]
        assert capture["artifact_allowlist"] == ["capture.json"]
        assert capture["private_inputs_read"] is False
        assert capture["private_capture_upload_allowed"] is False
        assert capture["files_captured"] == 0
        for name, relative in capture["private_task_relative_paths"].items():
            path = task_root / relative
            assert path.exists() and not Path(relative).is_absolute()
            if name in ("transcript", "tool_calls", "commands"):
                assert path.read_text() == ""
        assert json.loads((task_root / gate.PRIVATE_PATHS["input_file_hashes"]).read_text()) == []
        assert json.loads((task_root / gate.PRIVATE_PATHS["output_file_hashes"]).read_text()) == []
        assert json.loads((task_root / gate.PRIVATE_PATHS["exit_status"]).read_text()) == {
            "dry_run": True, "model_started": False, "exit_status": 0,
        }
        # Synthetic private streams must never be copied into the public envelope.
        canary = "SYNTHETIC_PRIVATE_CANARY_DO_NOT_UPLOAD"
        (task_root / gate.PRIVATE_PATHS["transcript"]).write_text(canary)
        assert canary not in (task_root / "capture.json").read_text()
        assert str(tmp_path) not in (task_root / "capture.json").read_text()
    streams = capsys.readouterr()
    assert streams.out == "ghcp_sol_dry_capture_complete\n" * 5
    assert streams.err == ""


@pytest.mark.parametrize("matrix", [False, True])
def test_paid_mode_refuses_before_reads_or_writes(tmp_path, monkeypatch, matrix):
    def forbidden():
        pytest.fail("paid mode reached catalogue")

    monkeypatch.setattr(gate, "fixed_task_ids", forbidden)
    root = tmp_path / "must-not-exist"
    args = ["--matrix"] if matrix else [
        "--task-id", gate.TASK_IDS[0], "--state-root", str(root),
    ]
    with pytest.raises(SystemExit) as error:
        gate.main(["--dry-run", "false", *args])
    assert error.value.code == 2
    assert not root.exists()


def test_capture_refuses_reuse_and_symlink(tmp_path, capsys):
    root = tmp_path / "state"
    args = ["--task-id", gate.TASK_IDS[0], "--state-root", str(root)]
    assert gate.main(args) == 0
    capture = root / gate.TASK_IDS[0] / "capture.json"
    before = capture.read_text()
    with pytest.raises(SystemExit) as error:
        gate.main(args)
    assert error.value.code == 2
    assert capture.read_text() == before
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(SystemExit):
        gate.main(["--task-id", gate.TASK_IDS[1], "--state-root", str(link)])
    assert capsys.readouterr().err == "ghcp_sol_dry_capture_refused\n" * 2


def test_catalog_drift_refuses(tmp_path, monkeypatch):
    catalog = tmp_path / "public-catalog.json"
    catalog.write_text("{}")
    monkeypatch.setattr(gate, "CATALOG_PATH", catalog)
    with pytest.raises(ValueError, match="public_catalog_identity_refused"):
        gate.fixed_task_ids()


def test_workflow_contract():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/agentic-v2-ghcp-sol-gate.yml"
    text = path.read_text()
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert list(workflow["on"]) == ["workflow_dispatch"]
    assert workflow["on"]["workflow_dispatch"]["inputs"]["dry_run"]["default"] == "true"
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert set(jobs) == {"plan", "task"}
    for job in jobs.values():
        assert job["runs-on"] == "ubuntu-24.04"
        assert job["timeout-minutes"] == "5"
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] == "false"
    task = jobs["task"]
    assert task["needs"] == "plan"
    assert task["strategy"] == {
        "fail-fast": "false", "matrix": "${{ fromJSON(needs.plan.outputs.matrix) }}",
    }
    assert "Paid execution is not implemented or approved." in jobs["plan"]["steps"][0]["run"]
    upload = task["steps"][-1]["with"]
    assert upload["path"] == "${{ runner.temp }}/ghcp-sol-gate/${{ matrix.task_id }}/capture.json"
    assert upload["include-hidden-files"] == "false"
    assert upload["if-no-files-found"] == "error"
    assert "60s" in task["steps"][-2]["run"]
    for forbidden in ("secrets.", "id-token:", "/dev/kvm", "pip install", "azure/login", "hf download"):
        assert forbidden not in text
