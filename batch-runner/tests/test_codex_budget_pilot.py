"""The real dispatcher CLI with synthetic inputs and one fake child boundary.

No production pin is changed. The transport explicitly substitutes original
input provenance and reviewed-source/host capability, not the config parser,
byte reader, preparation/result validators, checkpoints or deadline store.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import step8_grade  # Import real types before offline constructor guards.
import codex_budget_pilot as pilot
from core import azure_ai_clients, codex_azure_token
from core.codex_task_deadline import CodexTaskDeadlineControl, CodexTaskDeadlineStore, TOTAL_SECONDS
from core.cost_receipts import CostReceipt
from core.experiment_config import ExperimentConfig
from core.prepared_fingerprint import prepared_fingerprint
from core.result_fingerprint import inference_result_fingerprint
from core.source_identity import source_task_projection_sha256
from gpt54_prepared_input_attestation import _dataset_tasks, _prepared_condition, _reference_snapshot
from step1_prepare_tasks import _public_codex_config


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("dispatcher regression crossed a live boundary")

    for name in ("run", "Popen", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(pilot.time, "sleep", forbidden)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential):
        monkeypatch.setattr(constructor, "__init__", forbidden)
    monkeypatch.setattr(codex_azure_token, "acquire_token", forbidden)
    monkeypatch.setattr(codex_azure_token, "get_bearer_token_provider", forbidden)
    monkeypatch.setattr(step8_grade.Grader, "__init__", forbidden)
    from openai_codex import Codex
    from openai_codex.client import CodexClient

    monkeypatch.setattr(Codex, "__init__", forbidden)
    monkeypatch.setattr(CodexClient, "__init__", forbidden)


def prepared_output(config, snapshot, generation):
    parsed = ExperimentConfig.from_dict(config)
    assert parsed.validate() == []
    task_id = parsed.data_filter.task_ids[0]
    row = next(row for row in snapshot.projections if row["task_id"] == task_id)
    execution = parsed.to_dict()["execution"]
    execution = {key: execution[key] for key in ("mode", "max_retries", "resume_max_rounds", "tokens", "timeout", "sandbox")}
    execution["codex"] = _public_codex_config(parsed.execution.codex)
    result = {
        "experiment_id": parsed.experiment_id, "experiment_name": parsed.name,
        "description": parsed.description, "source": parsed.data_filter.source,
        "publication_generation": generation, "config_path": "pilot-run.json",
        "task_scope": {"mode": "explicit_ids", "expected_count": 1, "task_ids": [task_id]},
        "execution": execution, "total_tasks": 1,
        "needs_files_count": int(snapshot.needs_files[task_id]), "text_only_count": int(not snapshot.needs_files[task_id]),
        "condition_a": _prepared_condition(parsed.condition_a), "condition_b": None,
        "tasks": [{
            "task_id": task_id, "sector": row["sector"], "occupation": row["occupation"],
            "instruction": row["prompt"], "reference_files": row["reference_files"],
            "reference_file_records": [{"path": name, **snapshot.references[name]} for name in row["reference_files"]],
            "reference_file_urls": row["reference_file_urls"], "needs_files": snapshot.needs_files[task_id],
            "source_projection_sha256": source_task_projection_sha256(**row),
        }],
    }
    result["prepared_fingerprint"] = prepared_fingerprint(result)
    return result


class FakeChildren(pilot.LocalTransport):
    """Leave CLI, command construction and host state real; no native process."""

    def __init__(self, sources, task_ids):
        self.sources, self.task_ids = sources, task_ids
        self.expected = {"parquet": pilot._identity(pilot._read_bytes(sources.parquet)),
                         "manifest": pilot._identity(pilot._read_bytes(sources.manifest))}
        self.reference_name = "reference_files/synthetic.txt"
        self.reference_identity = pilot._identity(pilot._read_bytes(sources.references / self.reference_name))
        self.clock = Clock()
        self.capability = True
        self.reviewed = True
        self.calls = []
        self.active = 0
        self.peak = 0
        self.interrupt = None
        self.outcomes = {}
        self.receipts = {}
        self.snapshot = None
        self.model_admissions = []
        self.restore_snapshots = []

    def feedback_available(self):
        return self.capability

    def require_execution(self, plan, parent):
        if not self.feedback_available():
            raise pilot.PilotDispatchRefused("c_host_feedback_capability_missing")
        if not self.reviewed:
            raise pilot.PilotDispatchRefused("reviewed_clean_source_required")
        return {"tree_sha": "b" * 40, "routes": [{"synthetic": True}], "common": "synthetic-local-git"}

    def inputs(self, parent, sources):
        parquet = pilot._read_bytes(sources.parquet, **self.expected["parquet"])
        manifest = pilot._read_bytes(sources.manifest, **self.expected["manifest"])
        projections, needs = _dataset_tasks(parquet, tuple(self.task_ids))
        refs = _reference_snapshot(sources.references, {self.reference_name: self.reference_identity["sha256"]})
        self.snapshot = pilot._SourceSnapshot(
            {"synthetic": True, "ordered_task_ids": self.task_ids}, [], projections, refs, needs, None,
        )
        return pilot.VerifiedInputs(self.snapshot, {
            pilot.PARQUET_PATH: parquet, pilot.STEP0_MANIFEST_PATH: manifest,
            "data/gdpval-local/" + self.reference_name: pilot._read_bytes(sources.references / self.reference_name, **self.reference_identity),
        })

    def checkout(self, destination, sha):
        destination.mkdir(mode=0o700)
        (destination / "batch-runner").mkdir()
        pilot._write_file(destination / "synthetic-source", sha.encode())

    def verify_checkout(self, destination, sha):
        assert pilot._read_bytes(destination / "synthetic-source") == sha.encode()

    def process(self, command, **options):
        self.active += 1
        self.peak = max(self.peak, self.active)
        assert self.active == 1
        try:
            return self._process(command, **options)
        finally:
            self.active -= 1

    def _process(self, command, **options):
        cwd, env = options["cwd"], options["env"]
        cell_root = cwd.parent.parent
        dispatch_root = cell_root.parent.parent
        lock = os.open(dispatch_root / "lock", os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(lock)
        assert len(options["pass_fds"]) == 1  # Survives parent death in the real child path.
        for name in ("HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK", "PYTHONDONTWRITEBYTECODE"):
            assert env[name] == "1"
        assert "PYTHONPATH" not in env and "PYTHONHOME" not in env
        assert command[0] == pilot.sys.executable
        config = json.loads((cwd / "pilot-run.json").read_text())
        cell_id = cell_root.name
        task_id = config["data"]["filter"]["task_ids"][0]
        stage = "prepare" if command[1] == "step1_prepare_tasks.py" else "infer"
        self.calls.append((stage, cell_id, tuple(command)))
        self.clock.now += 1
        workspace = cwd / "workspace"
        if stage == "prepare":
            assert command[2:] == ["--config", "pilot-run.json"]
            if self.interrupt == (cell_id, "prepare"):
                self.interrupt = None
                raise KeyboardInterrupt
            prepared = prepared_output(config, self.snapshot, env["GDPVAL_RELAY_LINEAGE_ID"])
            pilot._write_file(workspace / "step1_tasks_prepared.json", json.dumps(prepared).encode())
            return subprocess.CompletedProcess(command, 0)
        assert command[1:4] == ["step2_run_inference.py", "--condition", "condition_a"]
        assert command[4:] == ["--codex-deadline-state", str(cell_root / "deadline")]
        assert "--initialize-codex-deadlines" not in command and "--no-resume" not in command
        prepared = json.loads((workspace / "step1_tasks_prepared.json").read_text())
        store = CodexTaskDeadlineStore(
            cell_root / "deadline", run_id=env["GDPVAL_RELAY_LINEAGE_ID"], experiment_id=config["experiment"]["id"],
            condition_key="condition_a", control=CodexTaskDeadlineControl.from_mapping(config["execution"]["codex"]["task_deadline"]),
            task_ids=[task_id], prepared_fingerprint=prepared["prepared_fingerprint"], clock=self.clock,
        )
        try:
            before = store._read()["cells"][task_id]
            self.restore_snapshots.append((cell_id, before))
            remaining = store.for_task(task_id).remaining_seconds()
            outcome = self.outcomes.get(cell_id, "success")
            if remaining:
                assert store.for_task(task_id).bound_timeout(1800) == min(1800, remaining)
                native = Path(env["GDPVAL_CODEX_RUN_ROOT"]) / f"attempt-{len(before['attempts'])}"
                native.mkdir(parents=True)
                index = store.for_task(task_id).admit_attempt(native)
                self.model_admissions.append((cell_id, index))
                pilot._write_file(native / "partial.txt", b"synthetic partial; never a model result")
                if self.interrupt == (cell_id, "attempt"):
                    self.interrupt = None
                    raise KeyboardInterrupt
                if outcome == "filtered":
                    store.for_task(task_id).stop_content_filter()
            else:
                outcome = "expired"
            if outcome == "missing_result":
                return subprocess.CompletedProcess(command, 0)
            result_row = {"task_id": task_id, "status": "success" if outcome == "success" else "error",
                          "deliverable_files": [], "deliverable_file_records": [],
                          "observability": {"error_category": None if outcome == "success" else outcome}}
            if self.receipts.get(cell_id) == "unavailable":
                result_row["problem_solving_cost"] = CostReceipt.unavailable().as_dict()
            payload = {
                "experiment_id": config["experiment"]["id"], "run_id": env["GDPVAL_RELAY_LINEAGE_ID"],
                "publication_generation": prepared["publication_generation"],
                "condition_identity": "condition_a", "execution_mode": "codex_foundry",
                "ordered_task_ids": [task_id], "prepared_fingerprint": prepared["prepared_fingerprint"],
                "model": "gpt-5.4", "results": [result_row],
            }
            payload["result_fingerprint"] = inference_result_fingerprint(payload)
            pilot._write_file(workspace / Path(pilot.RESULT).name, json.dumps(payload).encode())
            if self.interrupt == (cell_id, "result"):
                self.interrupt = None
                raise KeyboardInterrupt
            return subprocess.CompletedProcess(command, 0 if outcome == "success" else 1)
        finally:
            store.close()


@pytest.fixture
def scenario(monkeypatch):
    from core.execution_envelope_tasks import load_task_catalog, select_advance_check_tasks

    task_ids = list(select_advance_check_tasks(load_task_catalog()).task_ids)
    # Synthetic host state must not be inside /tmp (a real native writable carve-out).
    with tempfile.TemporaryDirectory(prefix=".pilot-dispatch-test-", dir=pilot.ROOT.parent) as directory:
        host = Path(directory)
        monkeypatch.setenv("GDPVAL_CODEX_RUN_ROOT", str(host / "unrelated-native-root"))
        monkeypatch.setenv("TMPDIR", str(host / "agent-temp"))
        sources = pilot.InputSources(host / "original.parquet", host / "references", host / "manifest.json")
        pilot._write_file(sources.references / "reference_files/synthetic.txt", b"synthetic reference")
        pilot._write_file(sources.manifest, b'{"synthetic":true}')
        rows = [{
            "task_id": task_id, "sector": "Synthetic sector", "occupation": "Synthetic job",
            "prompt": f"Synthetic dispatch input {index}", "rubric_pretty": "Not supplied to the agent",
            "rubric_json": "{}", "reference_files": ["reference_files/synthetic.txt"] if index == 0 else [],
            "reference_file_urls": [], "reference_file_hf_uris": [], "deliverable_files": [],
        } for index, task_id in enumerate(task_ids)]
        pq.write_table(pa.Table.from_pylist(rows), sources.parquet)
        transport = FakeChildren(sources, task_ids)
        argv = ["--run-id", "synthetic_pilot", "--reviewed-source-sha", "1" * 40,
                "--output", str(host / "dispatch"), "--dataset-parquet", str(sources.parquet),
                "--reference-root", str(sources.references), "--step0-manifest", str(sources.manifest)]
        yield SimpleNamespace(host=host, root=host / "dispatch", sources=sources, transport=transport,
                              argv=argv, ids=task_ids)


def invoke(scenario, *options):
    return pilot.main([*scenario.argv, *options], _test_transport=scenario.transport)


def read_plan(scenario):
    return pilot._load(scenario.root / "plan.json")


def read_state(scenario, key):
    return pilot._load(scenario.root / "cells" / key / "cell.json")


def test_pilot_dispatcher_plan_only_exact_matrix_and_common_profile(scenario):
    assert invoke(scenario) == 0
    plan = read_plan(scenario)
    assert scenario.transport.calls == [] and scenario.transport.model_admissions == []
    assert len(set(plan["order"])) == 30
    expected = [f"{task}_{arm}_r{repeat}" for task in scenario.ids for arm, repeat in pilot.ORDER]
    assert plan["order"] == expected
    configs = [json.loads((scenario.root / cell["roles"]["config"]).read_text()) for cell in plan["cells"]]
    assert all(config["condition_a"] == configs[0]["condition_a"] for config in configs)
    assert configs[0]["condition_a"]["model"]["deployment"] == "gpt-5.4"
    assert configs[0]["condition_a"]["model"]["reasoning_effort"] == "xhigh"
    for config, cell in zip(configs, plan["cells"]):
        assert ExperimentConfig.from_dict(config).validate() == []
        assert config["execution"]["timeout"] == 1800
        assert config["execution"]["max_retries"] == 3
        assert config["execution"]["resume_max_rounds"] == 0
        assert config["execution"]["codex"]["task_deadline"] == {"condition": cell["condition"], "repetition": cell["repetition"]}
        assert config["output"] == {"publish_to_hf": False, "submit_to_evals": False}
    assert plan["launch_authorized_by_plan"] is False and plan["grading_launched"] is False


def test_pilot_dispatcher_cli_executes_thirty_serial_isolated_cells_once(scenario):
    assert invoke(scenario, "--execute") == 0
    plan = read_plan(scenario)
    transport = scenario.transport
    assert [(stage, key) for stage, key, _ in transport.calls] == [
        (stage, key) for key in plan["order"] for stage in ("prepare", "infer")
    ]
    assert transport.peak == 1
    identities, expiries, inputs = set(), [], []
    for cell in plan["cells"]:
        state = read_state(scenario, cell["cell_id"])
        assert state["status"] == "succeeded" and state["child_invocations"] == 1
        assert state["receipt"] is None and state["accounting"] == "missing"
        identities.add(pilot._digest(state["deadline_identity"]))
        deadline = pilot._load(scenario.root / cell["roles"]["deadline"] / "deadlines.json")
        held = deadline["cells"][cell["task_id"]]
        assert held["expires_unix"] - held["started_unix"] == 10800
        expiries.append(held["expires_unix"])
        inputs.append((cell["task_id"], pilot._identity(pilot._read_bytes(
            scenario.root / cell["roles"]["checkout"] / "data/gdpval-local/reference_files/synthetic.txt"))))
        assert (scenario.root / cell["roles"]["native_workspaces"] / "attempt-0/partial.txt").is_file()
    assert len(identities) == 30 and len(set(expiries)) == 30
    assert len({entry[1]["sha256"] for entry in inputs}) == 1
    before = list(transport.calls)
    assert invoke(scenario, "--execute", "--resume") == 0
    assert transport.calls == before
    summary = pilot._load(scenario.root / "dispatch-result.json")
    assert summary["denominator"] == 30 and summary["counts"]["succeeded"] == 30


@pytest.mark.parametrize("window", ["attempt", "result", "expired"])
def test_pilot_dispatcher_interrupt_restore_preserves_clock_and_completed_cells(scenario, window):
    key = f"{scenario.ids[0]}_B_r1"
    scenario.transport.interrupt = (key, "attempt" if window == "expired" else window)
    assert invoke(scenario, "--execute") == 130
    state = read_state(scenario, key)
    before = pilot._load(scenario.root / "cells" / key / "deadline/deadlines.json")["cells"][scenario.ids[0]]
    partial = scenario.root / "cells" / key / "native-workspaces/attempt-0/partial.txt"
    assert partial.read_bytes() == b"synthetic partial; never a model result"
    calls_before = list(scenario.transport.calls)
    if window == "expired":
        scenario.transport.clock.now += TOTAL_SECONDS
    assert invoke(scenario, "--execute", "--resume") == (1 if window == "expired" else 0)
    after = pilot._load(scenario.root / "cells" / key / "deadline/deadlines.json")["cells"][scenario.ids[0]]
    assert after["started_unix"] == before["started_unix"] and after["expires_unix"] == before["expires_unix"]
    assert len(after["attempts"]) == (2 if window == "attempt" else 1)
    assert partial.exists()
    a_key = f"{scenario.ids[0]}_A_r1"
    assert sum(stage == "infer" and cell == a_key for stage, cell, _ in scenario.transport.calls) == 1
    if window == "result":
        assert sum(stage == "infer" and cell == key for stage, cell, _ in scenario.transport.calls) == 1
        assert read_state(scenario, key)["exit_code"] is None  # Lost exit is not fabricated.
    else:
        assert read_state(scenario, key)["child_invocations"] == state["child_invocations"] + 1
    assert scenario.transport.calls[:len(calls_before)] == calls_before


@pytest.mark.parametrize("reason", ["feedback", "review", "missing_parquet", "changed_parquet", "changed_manifest", "changed_reference", "linked_reference"])
def test_pilot_dispatcher_source_and_capability_refusal_precedes_any_child(scenario, reason):
    if reason == "feedback":
        scenario.transport.capability = False
    elif reason == "review":
        scenario.transport.reviewed = False
    elif reason == "missing_parquet":
        scenario.sources.parquet.unlink()
    elif reason == "changed_parquet":
        scenario.sources.parquet.write_bytes(b"changed synthetic source")
    elif reason == "changed_manifest":
        scenario.sources.manifest.write_bytes(b"changed synthetic manifest")
    else:
        path = scenario.sources.references / "reference_files/synthetic.txt"
        if reason == "changed_reference":
            path.write_bytes(b"changed synthetic reference")
        else:
            target = scenario.host / "linked-target"
            path.rename(target)
            path.symlink_to(target)
    assert invoke(scenario, "--execute") == 2
    assert scenario.transport.calls == []
    assert not scenario.root.exists()


def test_pilot_dispatcher_real_capability_gate_before_source_or_process(monkeypatch, scenario):
    # Explicit capability boundary; the real require_execution path must fail
    # before the forbidden Git/child/provider operations, even on a later main.
    monkeypatch.setattr(pilot, "_feedback_available", lambda: False)
    assert pilot.main([*scenario.argv, "--execute"]) == 2
    assert not scenario.root.exists()


@pytest.mark.parametrize("collision", ["root", "checkout", "deadline", "native_workspaces", "config", "checkpoint"])
def test_pilot_dispatcher_no_clobber_or_silent_adoption(scenario, collision):
    assert invoke(scenario) == 0
    if collision == "root":
        assert invoke(scenario) == 2
    else:
        cell = read_plan(scenario)["cells"][0]
        path = scenario.root / cell["roles"][collision]
        if collision in {"config", "checkpoint"}:
            path.write_bytes(b"corrupt synthetic record")
        else:
            path.mkdir()
            (path / "partial").write_bytes(b"retain")
        before = path.read_bytes() if path.is_file() else (path / "partial").read_bytes()
        assert invoke(scenario, "--execute", "--resume") == 2
        assert (path.read_bytes() if path.is_file() else (path / "partial").read_bytes()) == before
    assert scenario.transport.calls == []


def test_pilot_dispatcher_partial_preparation_is_quarantined_not_retried(scenario):
    key = f"{scenario.ids[0]}_A_r1"
    scenario.transport.interrupt = (key, "prepare")
    assert invoke(scenario, "--execute") == 130
    before = list(scenario.transport.calls)
    assert invoke(scenario, "--execute", "--resume") == 2
    assert scenario.transport.calls == before
    assert read_state(scenario, key)["phase"] == "preparing"


@pytest.mark.parametrize("change", ["missing_deadline", "prepared", "cross_cell", "original_input"])
def test_pilot_dispatcher_restore_refuses_changed_state_before_another_child(scenario, change):
    key = f"{scenario.ids[0]}_A_r1"
    scenario.transport.interrupt = (key, "attempt")
    assert invoke(scenario, "--execute") == 130
    cell_root = scenario.root / "cells" / key
    if change == "missing_deadline":
        (cell_root / "deadline/deadlines.json").unlink()
    elif change == "prepared":
        (cell_root / "checkout" / pilot.PREPARED).write_bytes(b"{}")
    elif change == "cross_cell":
        state = read_state(scenario, key)
        state["cell_id"] = f"{scenario.ids[0]}_B_r1"
        pilot._save(cell_root / "cell.json", state)
    else:
        scenario.sources.manifest.write_bytes(b"changed during downtime")
    before = list(scenario.transport.calls)
    assert invoke(scenario, "--execute", "--resume") == 2
    assert scenario.transport.calls == before


def test_pilot_dispatcher_failed_filtered_and_missing_receipts_stay_in_denominator(scenario):
    failed, filtered, absent = [f"{scenario.ids[0]}_{arm}_r1" for arm in "ABC"]
    scenario.transport.outcomes.update({failed: "error", filtered: "filtered", absent: "missing_result"})
    scenario.transport.receipts[failed] = "unavailable"
    assert invoke(scenario, "--execute") == 1
    summary = pilot._load(scenario.root / "dispatch-result.json")
    assert summary["denominator"] == 30 and sum(summary["counts"].values()) == 30
    assert summary["counts"] == {"pending": 0, "running": 0, "succeeded": 27, "failed": 3, "stopped": 0}
    assert read_state(scenario, failed)["receipt"]["estimated_cost_usd"] is None
    assert read_state(scenario, failed)["accounting"] == "unavailable"
    assert read_state(scenario, absent)["reason"] == "missing_result"
    assert read_state(scenario, absent)["receipt"] is None
    deadline = pilot._load(scenario.root / "cells" / filtered / "deadline/deadlines.json")
    assert deadline["cells"][scenario.ids[0]]["terminal_reason"] == "content_filtered"
    before = list(scenario.transport.calls)
    assert invoke(scenario, "--execute", "--resume") == 1
    assert scenario.transport.calls == before
