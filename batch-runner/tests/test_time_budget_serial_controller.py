"""Fake gh/storage/judge; real schedule, completion, F input and grade guards."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from core.agentic_v2_preregistration import seal
from core.time_budget_observation_deadline import TIMEOUT
from codex_budget_pilot_retention import _encoded
import gpt54_time_budget_serial_controller as serial
import gpt54_time_budget_serial_capture as intake
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_schedule as schedule
import gpt54_time_budget_v2_ci as v2
import gpt54_time_budget_codex_ci as codex
from gpt54_prepared_input_attestation import _identity
from .test_time_budget_paired_readout import (
    _capture, _store_capture, _stub, IMAGE, handoff_source_seed, handoff_sources, dual_roots, offline,
)


class Scenario:
    def __init__(self, seed, root, monkeypatch, *, fault=None, at=1):
        self.seed, self.root, self.monkeypatch = seed, root, monkeypatch
        root.mkdir()
        (root / "captures").mkdir()
        self.order = schedule.build_schedule(seed.plan)
        self.source = {"sha": seed.runtime_sha, "tree": seed.runtime_tree}
        self.now, self.fault, self.at = 10000, fault, at
        self.calls, self.dispatched, self.prepared, self.graded, self.downloads, self.storage_reads = [], [], [], [], [], []
        self.runs, self.requests, self.bundles = {}, {}, {}
        self.active, self.waited, self.interrupted = None, False, False
        self.names = {condition: yaml.safe_load((registration.ROOT / path).read_bytes())["name"]
                      for condition, path in schedule.WORKFLOWS.items()}
        self.pipeline = intake.FixtureFrozenPipeline(self.grade_stub)
        original_prepare = self.pipeline.prepare

        def prepare(plan, item, capture):
            self.prepared.append(item.observation_id)
            return original_prepare(plan, item, capture)

        self.pipeline.prepare = prepare

    def request(self, item, previous):
        module = v2 if item.condition == "sandbox_v2" else codex
        paths = {"runtime_root": "/home/runner/work/_temp/synthetic-runtime",
                 "frozen_root": "/home/runner/work/_temp/synthetic-frozen",
                 "state_root": "/home/runner/work/_temp/synthetic-state"}
        request = {"format": module.REQUEST_VERSION,
            "purpose": codex.PURPOSE if item.condition == "codex" else "execute_and_privately_retain_first_v2_observation",
            "source": self.source, "frozen_source": {"sha": registration.ACCEPTED_BASE_SHA, "tree": registration.ACCEPTED_BASE_TREE},
            "input_registration": {"source_sha": registration.ACCEPTED_BASE_SHA, "source_tree": registration.ACCEPTED_BASE_TREE,
                "path": registration.SOURCE_PROFILE, "sha256": registration.SOURCE_PROFILE_SHA256},
            "cell": item.cell, "ci": {"repository": serial.REPO, "workflow": schedule.WORKFLOWS[item.condition],
                "ref": "refs/heads/main", "actor": v2.OWNER, "job": "observation", "attempt": 1,
                "run_number": item.sequence, "runner": "ubuntu-24.04", "runner_os": "Linux", "runner_arch": "X64"},
            "registration_sha256": seal(self.seed.plan), "dataset_sha256": seal(self.seed.plan["shared"]["dataset"]),
            "paths": paths, "storage": {"expected_parent": "c" * 40 if previous is None else previous["output_commit"]},
            "not_before_unix": self.now - 1, "expires_unix": self.now + 2500}
        if item.condition == "codex":
            request["step0"] = {"synthetic_request_metadata_only": True}
        data = registration._canonical_json(request).encode()
        self.requests[item.sequence] = request
        return serial.ApprovedRequest(data, _identity(data)["sha256"])

    def execute(self, argv, *, input, timeout):
        assert argv[0] == "gh" and argv[-2:] == ["--repo", serial.REPO] and timeout == 60
        self.calls.append(argv)
        output = None
        if argv[1:3] == ["workflow", "run"]:
            fields = json.loads(input)
            assert set(fields) == {"reviewed_source_sha", "reviewed_source_tree", "request_sha256", "request_json"}
            request = json.loads(fields["request_json"])
            item = schedule.select(self.order, request["cell"])
            assert argv[3] == Path(schedule.WORKFLOWS[item.condition]).name
            assert argv[4:7] == ["--ref", "main", "--json"]
            assert fields["request_sha256"] == _identity(fields["request_json"].encode())["sha256"]
            assert self.active is None, "more than one Actions run in flight"
            self.active = item.sequence
            self.dispatched.append(item.observation_id)
            assert len(set(self.dispatched)) == len(self.dispatched), "a dispatch was repeated"
            self.runs[item.sequence] = {"databaseId": 1000 + item.sequence, "number": item.sequence, "attempt": 1,
                "event": "workflow_dispatch", "headSha": self.source["sha"], "headBranch": "main", "status": "queued",
                "conclusion": None, "workflowName": self.names[item.condition]}
            if self.fault == "interrupt_dispatch" and item.sequence == self.at and not self.interrupted:
                self.interrupted = True
                raise KeyboardInterrupt("synthetic interruption after accepted dispatch")
            if self.fault == "lost_dispatch_ack" and item.sequence == self.at:
                return SimpleNamespace(returncode=1, stdout="", stderr="synthetic-private-not-retained")
        elif argv[1:3] == ["run", "list"]:
            condition = next(name for name, path in schedule.WORKFLOWS.items() if Path(path).name == argv[4])
            output = [deepcopy(run) for seq, run in self.runs.items() if self.order[seq - 1].condition == condition]
            if self.fault == "duplicate_run" and self.at in self.runs:
                duplicate = deepcopy(self.runs[self.at])
                duplicate["databaseId"] += 9999
                output.append(duplicate)
            if self.fault == "missing_run":
                output = []
        elif argv[1:3] == ["run", "view"]:
            seq = int(argv[3]) - 1000
            output = deepcopy(self.runs[seq])
            if self.fault == "wait" and seq == self.at and not self.waited:
                self.waited = True
                output["status"] = "in_progress"
            elif self.fault == "active_timeout" and seq == self.at:
                output["status"] = "in_progress"
            else:
                output["status"] = "completed"
                output["conclusion"] = "failure" if self.fault == "run_failure" and seq == self.at else "success"
                output["jobs"] = [{"name": "observation", "status": "completed", "conclusion": output["conclusion"]}]
                self.active = None
            if self.fault == "run_sha" and seq == self.at:
                output["headSha"] = "0" * 40
        elif argv[1:3] == ["run", "download"]:
            seq = int(argv[3]) - 1000
            item = self.order[seq - 1]
            assert argv[4:6] == ["--name", serial.ARTIFACTS[item.condition]]
            self.downloads.append(seq)
            target = Path(argv[7])
            assert target.is_dir() and not list(target.iterdir())
            if self.fault != "missing_artifact" or seq != self.at:
                envelope = self.packet(seq)
                if seq == self.at:
                    if self.fault == "ubuntu22":
                        envelope["runner_image"].update(runner="ubuntu-22.04", image_os="ubuntu22", os_version_id="22.04")
                    if self.fault == "completion_sha": envelope["source"]["sha"] = "0" * 40
                    if self.fault == "request_digest": envelope["request_sha256"] = "0" * 64
                (target / "completion.json").write_bytes(_encoded(envelope))
        else:
            pytest.fail("unexpected fake gh command")
        return SimpleNamespace(returncode=0, stdout="" if output is None else json.dumps(output), stderr="")

    def packet(self, seq):
        item = self.order[seq - 1]
        terminal = TIMEOUT if self.fault == "clean_generation_timeout" and seq == self.at else "completed"
        fixture = _capture(self.seed, self.root / "captures", seq - 1, terminal=terminal)
        args = fixture.arguments
        payload = serial.document(args["result_path"])
        payload["observation_execution"]["runtime_source"] = {
            "source_sha": self.source["sha"], "source_tree": self.source["tree"]}
        _store_capture(fixture, payload)
        request_data = registration._canonical_json(self.requests[seq]).encode()
        identity = _identity(request_data)
        suffix = "v2" if item.condition == "sandbox_v2" else "codex"
        ci = {"run_id": str(1000 + seq), "run_number": seq, "job": "observation", "attempt": 1}
        claim = {"format": f"gpt54-time-budget-first-{suffix}-admission-v1", "observation": asdict(args["observation"]),
                 "source": self.source, "ci": ci, "state": "permanently_consumed_not_completion",
                 "input_binding_sha256": args["observation"].input_sha256, "request_identity": identity,
                 "host": payload["observation_execution"]["host"]}
        claim_path = args["result_path"].parent / "admission.json"
        claim_path.write_bytes(_encoded(claim))
        files = {"result/step2_inference_results.json": args["expected_result_identity"]}
        for record in payload["results"][0]["deliverable_file_records"]:
            files["result/upload/" + record["path"]] = {key: record[key] for key in ("sha256", "size")}
        manifest = {"format": f"gpt54-time-budget-first-{suffix}-private-output-v1",
            "observation": asdict(args["observation"]), "request_identity": identity,
            "claim_commit": "d" * 40, "claim_identity": _identity(_encoded(claim)),
            "execution_receipt": {"outcome": "returned"}, "result": "canonical_step2", "files": files,
            "grading_performed": False}
        manifest_path = claim_path.with_name("output-manifest.json")
        manifest_path.write_bytes(_encoded(manifest))
        record = schedule.capture_record({"plan": self.seed.plan, "cell": item.cell, "request": {"source": self.source}},
                                         {"claim": claim, "returned_commit": "d" * 40}, manifest, payload)
        if self.fault == "schedule_id" and seq == self.at:
            record["binding"]["observation_id"] = "0" * 64
        record_path = claim_path.with_name(schedule.CAPTURE_NAME)
        record_path.write_bytes(_encoded(record))
        revision = f"{seq:040x}"
        self.bundles[seq] = intake.CaptureBundle(v2.TARGET, revision, claim_path, manifest_path, record_path, args)
        return {"format": (v2 if item.condition == "sandbox_v2" else codex).RUNNER_ENVELOPE_VERSION,
            **item.cell, "source": deepcopy(self.source), "ci": ci, "runner_image": deepcopy(IMAGE),
            "request_sha256": identity["sha256"], "host_sha256": "f" * 64, "claim_commit": "d" * 40,
            "output_commit": revision, "retention": "acknowledged", "result_identity": args["expected_result_identity"],
            "result_fingerprint": payload["result_fingerprint"], "status": payload["results"][0]["status"],
            "usage": None, "terminal_reason": terminal, "cleanup_complete": True, "host_reusable": True,
            "grading_performed": False, "retry_allowed": False, "other_cells_executed": 0}

    def store(self, item, envelope):
        self.storage_reads.append(item.sequence)
        bundle = self.bundles[item.sequence]
        assert bundle.revision == envelope["output_commit"]
        return bundle

    def grade_stub(self, prepared, plan):
        oid = prepared.binding["observation_id"]
        self.graded.append(oid)
        assert self.graded.count(oid) == 1, "a judge attempt was repeated"
        result = _stub(prepared, plan, self.monkeypatch, points=2)
        if self.fault == "interrupt_grade" and prepared.binding["sequence"] == self.at:
            raise KeyboardInterrupt("synthetic lost grade acknowledgement")
        return result

    def controller(self):
        return serial.SerialController(plan=self.seed.plan, source=self.source, directory=self.root / "ledger",
            gh=serial.GhCommands(self.execute, synthetic=True), requests=self.request, store=self.store,
            pipeline=self.pipeline, clock=lambda: self.now)


@pytest.fixture
def scenario(handoff_sources, tmp_path, monkeypatch):
    return Scenario(handoff_sources, tmp_path / "scenario", monkeypatch)


def test_twenty_serial_dispatches_capture_F_inputs_stub_grades_and_ten_pairs(scenario, record_property):
    controller = scenario.controller()
    assert controller.run() == "complete"
    order = [item.observation_id for item in scenario.order]
    assert scenario.dispatched == scenario.prepared == scenario.graded == order
    assert scenario.downloads == scenario.storage_reads == list(range(1, 21))
    readout = controller.readout()
    assert (readout["prepared_observations"], readout["stub_grades"], readout["complete_pairs"], readout["missing_pairs"]) == (20, 20, 10, 0)
    assert readout["mean_score_difference_pp"] == 0  # Genuine equal fixture scores, not missing-value imputation.
    assert readout["launch_allowed"] is readout["execution_enabled"] is False
    before = len(scenario.calls)
    assert scenario.controller().run() == "complete"
    assert len(scenario.calls) == before and scenario.graded == order
    record_property("synthetic_serial_summary", json.dumps({"dispatches": 20, "captures": 20,
                    "frozen_inputs": 20, "stub_grades": 20, "pairs": 10, "actual_model_calls": 0}))


@pytest.mark.parametrize("fault", ["run_failure", "missing_artifact", "duplicate_run", "ubuntu22", "run_sha",
                                  "completion_sha", "request_digest", "schedule_id"])
def test_bad_run_or_capture_stops_without_next_dispatch_or_zero_fill(scenario, fault):
    scenario.fault = fault
    controller = scenario.controller()
    assert controller.run() == "stopped"
    assert len(scenario.dispatched) == 1 and not scenario.prepared and not scenario.graded
    result = controller.readout()
    assert result["complete_pairs"] == 0 and result["missing_pairs"] == 10
    assert result["mean_score_difference_pp"] is None
    assert all(row["score_pct"] is None for row in result["observations"])
    assert controller.ledger.read()["rows"][0]["state"] == "missing"
    before = len(scenario.calls)
    assert scenario.controller().run() == "stopped" and len(scenario.calls) == before


def test_mid_schedule_failure_retains_prior_results_and_stops(scenario):
    scenario.fault, scenario.at = "run_failure", 3
    controller = scenario.controller()
    assert controller.run() == "stopped"
    assert len(scenario.dispatched) == 3 and len(scenario.graded) == 2
    state = controller.ledger.read()
    assert [row["state"] for row in state["rows"][:4]] == ["complete", "complete", "missing", "pending"]
    report = controller.readout()
    assert report["observations"][0]["score_pct"] == 50
    assert report["observations"][2]["score_pct"] is None
    assert report["complete_pairs"] == 0 and report["missing_pairs"] == 10


@pytest.mark.parametrize("fault", ["interrupt_dispatch", "lost_dispatch_ack", "wait"])
def test_resume_discovers_the_same_run_and_skips_finished_observations(scenario, fault):
    controller = scenario.controller()
    assert controller.run(max_steps=5) == "paused"  # one finished observation
    scenario.fault, scenario.at = fault, 2
    if fault == "interrupt_dispatch":
        with pytest.raises(KeyboardInterrupt):
            controller.run()
    else:
        assert controller.run() == "waiting"
    assert len(scenario.dispatched) == 2 and len(scenario.graded) == 1
    resumed = scenario.controller()
    assert resumed.run(max_steps=4 if fault != "wait" else 3) == "paused"
    assert len(scenario.dispatched) == 2 and len(scenario.graded) == 2


@pytest.mark.parametrize("fault,seconds,reason", [
    ("missing_run", 121, "dispatch_confirmation_unknown"),
    ("active_timeout", 7201, "run_still_active_at_wait_limit"),
])
def test_uncertain_timeout_never_cancels_or_redispatches(scenario, fault, seconds, reason):
    scenario.fault = fault
    controller = scenario.controller()
    assert controller.run() == "waiting"
    scenario.now += seconds
    assert scenario.controller().run() == "stopped"
    assert controller.ledger.read()["stopped"]["reason"] == reason
    assert len(scenario.dispatched) == 1 and scenario.active == 1
    assert all(argv[1:3] != ["run", "cancel"] for argv in scenario.calls)


def test_lost_grade_acknowledgement_is_never_regraded(scenario):
    scenario.fault = "interrupt_grade"
    controller = scenario.controller()
    with pytest.raises(KeyboardInterrupt):
        controller.run()
    assert len(scenario.graded) == 1
    assert scenario.controller().run() == "stopped"
    assert len(scenario.graded) == len(scenario.dispatched) == 1
    assert controller.readout()["mean_score_difference_pp"] is None


def test_clean_generation_timeout_is_retained_and_can_advance_but_score_is_null(scenario):
    scenario.fault = "clean_generation_timeout"
    controller = scenario.controller()
    assert controller.run(max_steps=5) == "paused"
    assert len(scenario.graded) == 1
    report = controller.readout()
    assert report["observations"][0]["terminal_reason"] == TIMEOUT
    assert report["observations"][0]["score_pct"] is None
    assert controller.run(max_steps=1) == "paused" and len(scenario.dispatched) == 2


def test_file_lock_prevents_two_controllers_from_dispatching(scenario):
    first, second = scenario.controller(), scenario.controller()
    with first.ledger.lock():
        with pytest.raises(serial.ControllerRefused, match="already_running"):
            second.advance()
    assert not scenario.calls


def test_source_change_on_resume_does_not_create_new_observation_ids(scenario):
    controller = scenario.controller()
    assert controller.run(max_steps=1) == "paused"
    scenario.source = {"sha": "0" * 40, "tree": "1" * 40}
    with pytest.raises(serial.ControllerRefused, match="source_or_contract_changed"):
        scenario.controller().advance()
    assert len(scenario.dispatched) == 1


def test_preexisting_run_is_not_adopted_as_a_new_dispatch(scenario):
    scenario.runs[1] = {"number": 1}
    controller = scenario.controller()
    assert controller.run() == "stopped"
    assert controller.ledger.read()["stopped"]["reason"] == "run_preexists_dispatch"
    assert not scenario.dispatched


@pytest.mark.parametrize("change", ["digest", "source", "effort_contract", "ci_image", "attempt", "expired", "run_number_bool"])
def test_bad_request_approval_is_rejected_before_gh(scenario, change):
    controller = scenario.controller()
    original = scenario.request

    def request(item, previous):
        approved = original(item, previous)
        if change == "digest":
            return serial.ApprovedRequest(approved.data, "0" * 64)
        value = json.loads(approved.data)
        if change == "source": value["source"]["sha"] = "0" * 40
        if change == "effort_contract": value["registration_sha256"] = "0" * 64
        if change == "ci_image": value["ci"]["runner"] = "ubuntu-22.04"
        if change == "attempt": value["ci"]["attempt"] = 2
        if change == "expired": value["expires_unix"] = scenario.now - 1
        if change == "run_number_bool": value["ci"]["run_number"] = True
        data = registration._canonical_json(value).encode()
        return serial.ApprovedRequest(data, _identity(data)["sha256"])

    controller.requests = request
    assert controller.run() == "stopped"
    assert scenario.calls == []


@pytest.mark.parametrize("delay_at", ["request_read", "run_list", "intent_fsync"])
@pytest.mark.parametrize("io_finished_at,admitted", [
    pytest.param(1000.999, True, id="just-before-expiry"),
    pytest.param(1001, False, id="exact-expiry"),
    pytest.param(1002, False, id="expired-during-io"),
])
def test_dispatch_window_rechecked_after_final_io(
        scenario, monkeypatch, record_property, delay_at, io_finished_at, admitted):
    scenario.now = 1000
    controller = scenario.controller()
    actual_request, actual_runs = controller.requests, controller.gh.runs
    actual_write, actual_dispatch = controller.ledger.write, controller.gh.dispatch
    issued, intents, entry_times = [], [], []

    def request(item, previous):
        value = json.loads(actual_request(item, previous).data)
        value.update(not_before_unix=990, expires_unix=1001)
        scenario.requests[item.sequence] = value
        data = registration._canonical_json(value).encode()
        # Explicit fixture issuer, never a production approval-generation path.
        approved = serial.ApprovedRequest(data, _identity(data)["sha256"])
        issued.append(approved)
        if delay_at == "request_read":
            scenario.now = io_finished_at
        return approved

    def runs(item):
        found = actual_runs(item)  # Keep the actual gh argv/schema and fake transport.
        if delay_at == "run_list":
            scenario.now = io_finished_at
        return found

    def write(state):
        actual_write(state)  # Preserve real write-ahead serialization/fsync.
        if state["rows"][0]["state"] == "dispatch_intent":
            intents.append(deepcopy(state["rows"][0]))
            if delay_at == "intent_fsync":
                scenario.now = io_finished_at

    def dispatch(*args):
        entry_times.append(scenario.now)
        return actual_dispatch(*args)  # Scenario.execute is exclusively fake gh.

    monkeypatch.setattr(controller, "requests", request)
    monkeypatch.setattr(controller.gh, "runs", runs)
    monkeypatch.setattr(controller.ledger, "write", write)
    monkeypatch.setattr(controller.gh, "dispatch", dispatch)
    result = controller.advance()
    record_property("dispatch_window_boundary", json.dumps({"delay_at": delay_at,
        "io_finished_at": io_finished_at, "expires_at": 1001, "entry_times": entry_times,
        "actual_dispatches": 0, "actual_model_calls": 0}))
    assert entry_times == ([io_finished_at] if admitted else [])
    assert result == ("progress" if admitted else "stopped")
    assert scenario.dispatched == ([scenario.order[0].observation_id] if admitted else [])
    assert len(issued) == len(intents) == 1
    expected_request = {"sha256": issued[0].sha256, "size": len(issued[0].data), "run_number": 1}
    assert intents[0]["request"] == expected_request
    state = controller.ledger.read()
    assert state["rows"][0]["request"] == expected_request  # Never discard the consumed slot.
    with controller.ledger.lock():  # New open description proves prior lock release.
        pass
    if not admitted:
        assert state["stopped"]["reason"] == state["rows"][0]["issue"] == "request_window_invalid"
        assert state["rows"][0]["state"] == "missing" and state["rows"][0]["score_pct"] is None
        assert scenario.runs == {} and scenario.active is None
        assert scenario.downloads == scenario.storage_reads == scenario.prepared == scenario.graded == []
        readout = controller.readout()
        assert readout["observations"][0]["score_pct"] is None
        assert readout["mean_score_difference_pp"] is None and readout["complete_pairs"] == 0
        before = controller.ledger.path.read_bytes()
        # A current approval must not turn a stopped ledger into retry authority.
        scenario.now = 1000
        resumed = scenario.controller()
        monkeypatch.setattr(resumed, "requests", request)
        assert resumed.run() == "stopped"
        assert len(issued) == 1 and scenario.dispatched == []
        assert controller.ledger.path.read_bytes() == before


@pytest.mark.parametrize("clock_error", [
    pytest.param(RuntimeError, id="clock-error"),
    pytest.param(KeyboardInterrupt, id="interrupted-clock"),
])
def test_dispatch_final_clock_error_retains_intent_without_retry(
        scenario, monkeypatch, record_property, clock_error):
    scenario.now = 1000
    controller = scenario.controller()
    actual_clock, actual_write = controller.clock, controller.ledger.write
    phase = {"intent_saved": False, "clock_failed": False}

    def write(state):
        actual_write(state)
        if state["rows"][0]["state"] == "dispatch_intent":
            phase["intent_saved"] = True

    def clock():
        if phase["intent_saved"] and not phase["clock_failed"]:
            phase["clock_failed"] = True
            raise clock_error("synthetic final admission clock failure")
        return actual_clock()  # Reuse the pre-existing injected test clock.

    monkeypatch.setattr(controller.ledger, "write", write)
    monkeypatch.setattr(controller, "clock", clock)
    try:
        result = controller.advance()
    except KeyboardInterrupt:
        result = "interrupted"
    record_property("dispatch_clock_failure", json.dumps({"exception": clock_error.__name__,
        **phase, "fake_dispatches": len(scenario.dispatched), "actual_dispatches": 0, "actual_model_calls": 0}))
    assert scenario.dispatched == [] and phase == {"intent_saved": True, "clock_failed": True}
    assert result == ("interrupted" if clock_error is KeyboardInterrupt else "waiting")
    state = controller.ledger.read()
    assert state["stopped"] is None and state["rows"][0]["state"] == "dispatch_intent"
    assert state["rows"][0]["score_pct"] is None
    before = controller.ledger.path.read_bytes()
    with controller.ledger.lock():  # Exception/interrupt must close the original lock fd.
        pass
    resumed = scenario.controller()
    assert resumed.advance() == "waiting"  # Discovery only, never re-dispatch.
    assert controller.ledger.path.read_bytes() == before
    scenario.now = state["rows"][0]["discovery_deadline"]
    assert resumed.advance() == "stopped"
    stopped = controller.ledger.read()
    assert stopped["stopped"]["reason"] == "dispatch_confirmation_unknown"
    assert stopped["rows"][0]["request"] == state["rows"][0]["request"]
    assert stopped["rows"][0]["score_pct"] is None
    before = controller.ledger.path.read_bytes()
    scenario.now = 1000
    assert scenario.controller().advance() == "stopped"
    assert controller.ledger.path.read_bytes() == before
    assert scenario.dispatched == scenario.downloads == scenario.storage_reads == scenario.prepared == scenario.graded == []


@pytest.mark.parametrize("change", ["twenty_first", "out_of_order", "duplicate_binding", "checksum"])
def test_ledger_corruption_is_not_execution_or_retry_authority(scenario, change):
    controller = scenario.controller()
    state = controller.ledger.read()
    if change == "twenty_first": state["rows"].append(deepcopy(state["rows"][0]))
    if change == "out_of_order": state["rows"][1]["state"] = "complete"
    if change == "duplicate_binding": state["rows"][1]["binding"] = state["rows"][0]["binding"]
    if change == "checksum":
        serial.atomic_json(controller.ledger.path, {"state": state, "sha256": "0" * 64})
    else:
        controller.ledger.write(state)
    with pytest.raises(serial.ControllerRefused):
        controller.advance()
    assert scenario.calls == []


def test_live_path_is_closed_before_gh_until_common_grading_admission_exists(scenario):
    pipeline = intake.FrozenInputQueue()
    controller = serial.SerialController(plan=scenario.seed.plan, source=scenario.source,
        directory=scenario.root / "closed-ledger", gh=serial.GhCommands(scenario.execute),
        requests=scenario.request, store=scenario.store, pipeline=pipeline)
    with pytest.raises(serial.ControllerRefused, match="common_live_grading_admission_not_implemented"):
        controller.advance()
    assert scenario.calls == []


def test_original_registration_and_all_successor_hash_expectations_stay_unchanged():
    base = registration.ROOT / "batch-runner/experiments/execution_envelope"
    expected = {
        "gpt54_sandboxv2_codex_comparison.yaml": "3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1",
        "gpt54_sandboxv2_codex_time_budget_v1.yaml": "e1d16d350aeb21af34104cede0d3acc0f6dc8db134338708e70168fbd9642699",
        "gpt54_time_budget_source_20261030_schedule.yaml": "1e316eecccad614eba24034849a3bebf7bff549a59d7f6e127ac597192334dae",
    }
    for name, digest in expected.items():
        assert hashlib.sha256((base / name).read_bytes()).hexdigest() == digest
    profile = yaml.safe_load((base / "gpt54_time_budget_source_20261030_schedule.yaml").read_bytes())
    assert len(profile["helper_pins"]) == 8
    # D3 is additive: the historical bytes above stay pinned; exactly its V2
    # callback helper advances in the new independently source-bound record.
    _, sources = registration._runtime_source_followup(registration.ROOT, registration.load_registration())
    helpers = {path: identity["sha256"] for path, identity in sources["source_followup"]["helper_files"].items()}
    assert set(helpers) == set(profile["helper_pins"])
    assert {path for path in helpers if helpers[path] != profile["helper_pins"][path]} == {
        "batch-runner/gpt54_time_budget_v2_observation.py"}
    for path, digest in helpers.items():
        assert hashlib.sha256((registration.ROOT / path).read_bytes()).hexdigest() == digest
