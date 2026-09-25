"""The fixed historical A1 may precede only its current-source B1.

Real compiler, CLI, serialization, publication and byte/CAS validators; fake
input provenance, reviewed host/runtime, children and HF. The A1 payload below
is newly generated synthetic evidence, never recovered historical content.
"""

from __future__ import annotations

import copy
import json
import time

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retention
from core.codex_task_deadline import CodexTaskDeadlineControl
from . import test_codex_budget_pilot_retention as base
from .test_codex_budget_pilot_retention import offline, scenario  # noqa: F401

PRODUCER = "b4c95f8eaee16ae2226f3bf6e0493051fa91d770"
CONTROLLER = "66e7ad05975ddf704b9e2aab2b1efce5cd533cef"
TERMINAL = "8083504edf4ceb63f3c4929aac57e0f4b6741593"
A1 = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r1"
B1 = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_B_r1"


class FixedPredecessorHF(base.MemoryHF):
    def create_commit(self, **kwargs):
        response = super().create_commit(**kwargs)
        if self.commits == ["admission", "output", "terminal"] and self.parents[self.head] == f"{2:040x}":
            # Only the fake server's first terminal address is fixed. Its
            # original claim, output identities and serialized bytes are real.
            previous = self.head
            self.trees[TERMINAL] = self.trees.pop(previous)
            self.writers[TERMINAL] = {
                name: TERMINAL if writer == previous else writer
                for name, writer in self.writers.pop(previous).items()
            }
            self.parents[TERMINAL] = self.parents.pop(previous)
            self.head = response.oid = TERMINAL
        return response


@pytest.fixture(scope="module")
def compiled_contracts():
    # Cache genuine compilation, not validators or an invented plan. Each
    # caller gets a deep copy, including the unchanged 30-cell specifications.
    return {source: pilot.compile_pilot(ci.CAMPAIGN, source) for source in (PRODUCER, CONTROLLER)}


@pytest.mark.parametrize("change", [
    "accepted", "historical_source", "terminal_revision", "predecessor_cell",
    "plan", "config", "inputs", "bytes", "manifest_hash", "cleanup",
    "publication", "lost_output", "compiler_drift", "other_cell", "cas_race",
    "claim_lost", "terminal_lost", "current_source", "rerun",
])
def test_fixed_task2_b1_historical_predecessor(scenario, compiled_contracts, capsys, monkeypatch, change):
    real_compile = pilot.compile_pilot

    def compile_contract(campaign, source):
        if campaign == ci.CAMPAIGN and source in compiled_contracts:
            return copy.deepcopy(compiled_contracts[source])
        return real_compile(campaign, source)

    monkeypatch.setattr(pilot, "compile_pilot", compile_contract)
    monkeypatch.setattr(base, "SOURCE", PRODUCER)
    s = base.case.__wrapped__(scenario, monkeypatch)
    s.argv[s.argv.index("--reviewed-source-sha") + 1] = PRODUCER
    s.api = FixedPredecessorHF()
    s.transport = base.RetainedChildren(s.sources, s.ids, s.api)
    assert s.selected == A1
    base.finalized(s, capsys, monkeypatch)
    if change == "lost_output":
        s.api.lost = "output"
    assert base.boundary(s, capsys, monkeypatch, "--retain")[0] == (2 if change == "lost_output" else 0)
    old_plan = base.read_plan(s)
    old_cell = old_plan["cells"][6]
    old_root = base.cell_root(s)
    old_local = {path: path.read_bytes() for path in old_root.rglob("*") if path.is_file()}
    claim_path, terminal_path, _ = retention._paths(old_cell)
    if change != "lost_output":
        assert s.api.head == TERMINAL
        terminal = json.loads(s.api.trees[TERMINAL][terminal_path])
        assert terminal["completion"]["source_sha"] == PRODUCER
        if change in {"historical_source", "plan", "config"}:
            claim = json.loads(s.api.trees[terminal["claim_commit"]][claim_path])
            if change == "historical_source":
                claim["binding"]["source_sha"] = "e" * 40
                claim["binding"]["host"]["workflow_sha"] = "e" * 40
            else:
                claim["binding"][change + "_sha256"] = "e" * 64
            data = retention._encoded(claim)
            s.api.trees[terminal["claim_commit"]][claim_path] = data
            s.api.trees[TERMINAL][claim_path] = data
            terminal["claim_identity"] = pilot._identity(data)
        elif change == "predecessor_cell":
            terminal["completion"]["cell_id"] = B1
        elif change == "manifest_hash":
            terminal["manifest_identity"]["sha256"] = "e" * 64
        elif change == "cleanup":
            terminal["completion"]["cleanup_confirmed"] = False
        elif change == "publication":
            terminal["publication_acknowledged"] = False
        elif change == "bytes":
            name = next(row["path"] for row in terminal["output_objects"] if row["path"].endswith(".txt"))
            s.api.trees[terminal["output_commit"]][name] += b"changed synthetic bytes"
        s.api.trees[TERMINAL][terminal_path] = retention._encoded(terminal)
        if change == "terminal_revision":
            s.api.head = "e" * 40
            s.api.trees[s.api.head] = dict(s.api.trees[TERMINAL])
            s.api.writers[s.api.head] = dict(s.api.writers[TERMINAL])
    if change == "inputs":
        s.sources.manifest.write_bytes(b'{"synthetic":"changed original identity"}')
    if change == "compiler_drift":
        def drift(campaign, source):
            plan, parent, specs = compile_contract(campaign, source)
            if source == PRODUCER:
                plan["dispatcher_sha256"] = "e" * 64
            return plan, parent, specs
        monkeypatch.setattr(pilot, "compile_pilot", drift)

    # New job coordinates and clock only for B1; never copy/adopt A1 state.
    monkeypatch.setattr(base, "SOURCE", CONTROLLER)
    for key in ("GITHUB_SHA", "PILOT_WORKFLOW_SHA"):
        monkeypatch.setenv(key, CONTROLLER)
    s.argv[s.argv.index("--reviewed-source-sha") + 1] = CONTROLLER
    base.select_fresh(s, monkeypatch, ordinal=8 if change == "other_cell" else 7)
    plan = base.read_plan(s)
    cell = next(row for row in plan["cells"] if row["cell_id"] == s.selected)
    assert plan["order"] == old_plan["order"] and len(plan["cells"]) == 30
    assert plan["model"] == old_plan["model"]
    assert plan["dataset"] == old_plan["dataset"] and plan["source_pins"] == old_plan["source_pins"]
    assert plan["grading"] == old_plan["grading"]
    assert plan["reviewed_source_sha"] == plan["ci"]["host"]["workflow_sha"] == CONTROLLER
    assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
    assert plan["model"]["deployment"] == "gpt-5.4"
    assert plan["model"]["route_profile"] == "direct-v1" and plan["model"]["reasoning_effort"] == "xhigh"
    if change != "other_cell":
        assert s.selected == B1 and cell["index"] == 7
        assert cell["config_sha256"] == "85852f9b8bdbfa66e5c775283ca1fe092e60af21f51eafe82b0021b83109c049"
        config = json.loads(pilot._read_bytes(s.root / cell["roles"]["config"]))
        assert config["execution"]["timeout"] == 1800
        assert config["execution"]["max_retries"] == 3 and config["execution"]["resume_max_rounds"] == 0
        assert config["execution"]["codex"]["task_deadline"] == {"condition": "B", "repetition": 1}
        assert config["output"] == {"publish_to_hf": False, "submit_to_evals": False}
        assert CodexTaskDeadlineControl("B", 1).max_attempts is None

    remote_before = copy.deepcopy((s.api.trees, s.api.parents, s.api.writers))
    s.api.calls.clear()
    s.api.commits.clear()
    s.api.events.clear()
    s.api.lost = "admission" if change == "claim_lost" else None
    s.api.move_before_commit = change == "cas_race"
    if change == "current_source":
        monkeypatch.setenv("GITHUB_SHA", PRODUCER)
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")

    accepted = change in {"accepted", "terminal_lost"}
    code, record = base.boundary(s, capsys, monkeypatch, "--admit")
    assert code == (0 if accepted else 2)
    assert not s.transport.calls
    if accepted:
        assert record["source_sha"] == CONTROLLER and record["outcome"] == "acknowledged"
        receipt = retention._read(base.cell_root(s) / retention.ADMISSION_RECEIPT)
        claim = receipt["claim"]
        assert claim["binding"]["source_sha"] == claim["binding"]["host"]["workflow_sha"] == CONTROLLER
        assert claim["binding"]["cell_id"] == B1 and claim["binding"]["ordinal"] == 7
        assert claim["expected_parent"] == claim["predecessor"]["terminal_commit"] == TERMINAL
        assert claim["predecessor"]["cell_id"] == A1
        observed = retention._read(base.cell_root(s) / retention.SERVER_OBSERVATION)
        assert observed == {"observation": "verified_server_terminal_state", "predecessor": claim["predecessor"],
                            "writer_response_delivery": "not_asserted"}
        assert base.cli(s, "--resume", "--execute") == 0
        assert s.transport.model_admissions == [(B1, 0)] and s.transport.peak == 1
        assert set(s.transport.source_checks) == {CONTROLLER}
        assert (s.root / cell["roles"]["checkout"] / "synthetic-source").read_bytes() == CONTROLLER.encode()
        state = base.read_state(s, B1)
        store = pilot._deadline(s.root, cell, state, s.transport)
        try:
            deadline = store.for_task(cell["task_id"]).as_record()
            assert deadline["condition"] == "B" and deadline["repetition"] == 1
            assert deadline["total_seconds"] == 10800 and deadline["attempt_seconds"] == 1800
            assert deadline["expires_unix"] - deadline["started_unix"] == 10800
            assert deadline["session_policy"] == "retained_native_thread"
            assert deadline["attempts_admitted"] == 1 and deadline["native_resumes"] == 0
        finally:
            store.close()
        completion_bytes = s.envelope.read_bytes()
        s.api.lost = "terminal" if change == "terminal_lost" else None
        assert base.boundary(s, capsys, monkeypatch, "--retain")[0] == (2 if change == "terminal_lost" else 0)
        assert s.envelope.read_bytes() == completion_bytes and base.read_state(s, B1) == state
        assert s.api.commits == ["admission", "output", "terminal"]
        if change == "accepted":
            cache = s.host / "verify-b1-terminal"
            cache.mkdir(mode=0o700)
            evidence = retention._terminal(s.api, s.api.repo, s.api.head, plan, cell,
                retention._local(plan, cell, s.root)[0], cache, base.TOKEN, time.monotonic() + 60)
            assert evidence["terminal"]["completion"] == pilot._load(s.envelope)
            assert evidence["manifest"]["source_sha"] == CONTROLLER
            assert evidence["manifest"]["inference_branch"] == "pilot-inference-20260925-04"
            assert evidence["manifest"]["status"] == "succeeded" and evidence["manifest"]["grade_ready"] is False
            assert evidence["claim"] == claim
        else:
            lost = base.cell_root(s) / retention.TERMINAL_RECEIPT
            original = lost.read_bytes()
            assert json.loads(original)["outcome"] == "unresolved" and json.loads(original)["terminal_commit"] is None
            before = list(s.api.calls)
            assert base.boundary(s, capsys, monkeypatch, "--retain")[0] == 2
            assert s.api.calls == before and lost.read_bytes() == original
    else:
        assert base.cli(s, "--resume", "--execute") == 2 and not s.transport.calls
        if change in {"current_source", "rerun"}:
            assert s.api.calls == [] and not (base.cell_root(s) / retention.ADMISSION_RESERVED).exists()
        else:
            expected = {
                "historical_source": "claim_host_policy_mismatch", "terminal_revision": "retention_control_history_mismatch",
                "predecessor_cell": "terminal_completion_identity_mismatch", "plan": "claim_identity_mismatch",
                "config": "claim_identity_mismatch", "inputs": "claim_identity_mismatch",
                "manifest_hash": "payload_identity_mismatch", "publication": "terminal_confirmation_contract_mismatch",
                "bytes": "remote_output_size_mismatch", "cleanup": "hf_operation_failed",
                "lost_output": "terminal_or_claim_missing", "compiler_drift": "claim_identity_mismatch",
                "other_cell": "terminal_or_claim_missing", "cas_race": "hf_http_failed", "claim_lost": "hf_transport_failed",
            }
            if change in expected:
                assert record["reason"] == expected[change]
            assert record["outcome"] == ("unresolved" if change in {"cas_race", "claim_lost"} else "refused")
            reserved = base.cell_root(s) / retention.ADMISSION_RESERVED
            receipt_path = base.cell_root(s) / retention.ADMISSION_RECEIPT
            before = (list(s.api.calls), reserved.read_bytes(), receipt_path.read_bytes())
            assert base.boundary(s, capsys, monkeypatch, "--admit")[0] == 2
            assert (s.api.calls, reserved.read_bytes(), receipt_path.read_bytes()) == before
        assert s.api.commits == (["admission"] if change in {"cas_race", "claim_lost"} else [])
    assert all(base.read_state(s, row["cell_id"]) == pilot._cell_state(plan, row)
               for row in plan["cells"] if row["cell_id"] != s.selected)
    assert all(path.read_bytes() == data for path, data in old_local.items())
    for current, previous in zip((s.api.trees, s.api.parents, s.api.writers), remote_before):
        assert all(current[key] == value for key, value in previous.items())
