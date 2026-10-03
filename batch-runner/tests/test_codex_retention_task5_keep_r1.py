"""Closed ordinal-five proof; real validators, synthetic controls/owned child.

No live source, original payload, provider, model, grader or HF is accessed.
All helper imports happen during collection, before the offline process guards.
"""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric import rsa

import codex_retention_task5_keep_r1 as successor
import codex_retention_grade_readout as observer
import gpt54_disposable_checkout as source_checkout
from core.codex_cost import CodexTokenTotals, settle_codex_turn, turn_usage_delta
from core.codex_runner import CodexWorkspace
from core.codex_task_deadline import TaskDeadlineRefused
from core.cost_receipts import CostReceiptLedger
from . import test_codex_retention_task5_fresh_r1 as prior
from . import test_codex_retention_ci_observation as workflow_contract
from .test_codex_retention_task5_fresh_r1_read import _task5_fixture
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN, offline  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_result_intake import TERMINAL_HEAD

previous, fresh, reader, ci = successor.previous, successor.fresh, successor.reader, successor.ci
controller, preparation, registration = successor.controller, successor.preparation, successor.registration
owned, retained, output = successor.owned, successor.retained, successor.output
shared, base = prior.prior.prior, prior.base
REAL_ROOT, SOURCE, positive, _write = prior.REAL_ROOT, prior.SOURCE, prior.positive, prior._write


class FailedPredecessorHF(shared.SuccessorHF):
    def __init__(self, plan, *, binding=reader.TASK5_FRESH_R1, successor_adapter=successor):
        MemoryHF.__init__(self)
        producer = _task5_fixture(plan, terminal=True, exit_code=1, binding=binding)
        # Authored failed controls declare result/ledger only. No payload read
        # is needed to prove the predecessor's cleanup or publication history.
        row = producer.payload["results"][0]
        row["deliverable_files"], row["deliverable_file_records"] = [], []
        producer.files = {name: data for name, data in producer.files.items()
                          if name in (reader.intake.RESULT, reader.intake.LEDGER)}
        producer.bind_payload()
        producer.seed()
        self.producer_paths = (producer.producer.CLAIM, producer.producer.TERMINAL, producer.producer.OUTPUT)
        self.successor_paths = (successor_adapter.CLAIM, successor_adapter.TERMINAL, successor_adapter.OUTPUT)
        self.preceding_terminal = producer.producer.PREDECESSOR["terminal_commit"]
        self.claim, self.summary, self.terminal, self.files = (
            deepcopy(getattr(producer, name)) for name in ("claim", "summary", "terminal", "files"))
        self.pins = deepcopy(successor_adapter.PREDECESSOR)
        self.terminal.update(claim_commit=self.pins["claim_commit"], output_commit=self.pins["output_commit"])
        self.downloads = []
        self.seed()


def _runtime(monkeypatch, root):
    prior._runtime(monkeypatch, root)
    monkeypatch.setattr(successor, "ROOT", root)


class KeepTransport(shared.R2Transport):
    ordinal, repetition, cell_id, bundle = 5, 1, successor.CELL_ID, "keep"
    recovery_request = None
    keep_record = None

    def owned_process(self, command, **options):
        result = super().owned_process(command, **options)
        if self.recovery_request is not None:
            self._keep_recovery(options["ownership"][0].parent)
        return result

    def _keep_recovery(self, host):
        """Retain one owned native bundle through a real settled B recovery."""
        request = self.recovery_request
        context, stage = controller._context(request), controller.verify_staged_runtime(request)
        old = CodexWorkspace.create(task_id="synthetic-preceding-cell")
        _write(old.workspace / "previous-cell-only.txt", b"never adopt")
        workspace = CodexWorkspace.create(task_id=registration.TASK5)
        assert workspace.root != old.root and list(workspace.workspace.iterdir()) == []
        layout = workspace.continuation_binding()
        markers = {folder / "keep-marker.txt": role.encode() for role, folder in (
            ("workspace", workspace.workspace), ("HOME", workspace.home), ("CODEX_HOME", workspace.codex_home))}
        for path, data in markers.items():
            _write(path, data)
        deliverable = controller.ROOT / "batch-runner/workspace/upload/deliverable_files" / registration.TASK5 / "report.txt"
        markers[deliverable] = deliverable.read_bytes()
        identity = owned._digest({"cell_id": self.cell_id, "request_sha256": owned._digest(self.document)})
        receipt_path, receipt_run = host / "synthetic-keep-recovery.sqlite", "synthetic-task5-keep-recovery"
        store = controller._deadline(host, context, stage, self)
        try:
            task = store.for_task(registration.TASK5)
            assert task.retains_thread and not task.fresh_bundle and store.control.max_attempts is None
            assert task.continuation() is None and task.remaining_seconds() == 10800
            original = task.as_record()
            assert task.admit_attempt(workspace.root) == 0
            task.bind_workspace(identity, owned._digest(self.document), layout)
            task.thread_starting()
            with pytest.raises(TaskDeadlineRefused,
                    match="^native thread creation was interrupted before its identifier was bound$"):
                task.continuation(identity)
            assert all(path.read_bytes() == data for path, data in markers.items())
            task.bind_thread("synthetic-" + self.cell_id + "-thread", resumed=False)
            assert task.recovery_context(0) is None  # Mechanical B, no C feedback.
            with CostReceiptLedger(receipt_path, run_id=receipt_run) as ledger:
                call_id = ledger.reserve(call_id="synthetic-turn-0", task_id=registration.TASK5,
                    stage="generation", retry_kind="none", provider="synthetic", requested_model="synthetic",
                    request_sha256=owned._digest(self.document))
                before = task.begin_turn(0, call_id, input_sha256=owned._digest(self.document), recovery_context=None)
                after = dict.fromkeys(before)  # This synthetic failed turn reports no usage.
                task.observe_turn(0, after, failure_observation={
                    "category": "rate_limited", "http_status_code": 429, "retry_guidance": None})
                settle_codex_turn(ledger, call_id,
                    totals=turn_usage_delta(CodexTokenTotals(**before), CodexTokenTotals(**after)))
                task.acknowledge_usage(0)
                receipts = ledger.calls_for(registration.TASK5)
                assert len(receipts) == 1 and receipts[0]["call_id"] == call_id and receipts[0]["state"] == "settled"
            task.wait(30, lambda seconds: setattr(self.clock, "now", self.clock.now + seconds))
        finally:
            store.close()
        self.clock.now += 45  # Simulated downtime; the cumulative clock is not reset.
        store = controller._deadline(host, context, stage, self)
        try:
            task = store.for_task(registration.TASK5)
            task.require_resumable()
            bound = task.continuation(identity)
            restored = CodexWorkspace.restore(bound["workspace"])
            assert restored.root == workspace.root and restored.continuation_binding() == layout
            assert bound["thread_id"] == "synthetic-" + self.cell_id + "-thread"
            assert bound["turns"][0]["phase"] == "settled"
            assert bound["turns"][0]["failure_observation"]["category"] == "rate_limited"
            assert all(path.read_bytes() == data for path, data in markers.items())
            assert not (restored.workspace / "previous-cell-only.txt").exists()
            for method in (task.require_fresh_retirement, task.retire_fresh_bundle):
                with pytest.raises(TaskDeadlineRefused, match="^fresh retirement binding changed$"):
                    method(bound)
            with pytest.raises(TaskDeadlineRefused, match="^output reset requires the fresh bundle identity$"):
                task.bind_fresh_output_directory(deliverable.parent)
            with pytest.raises(TaskDeadlineRefused, match="^native continuation request/runtime identity mismatch$"):
                task.continuation(owned._digest({"cell_id": self.document["serial_domain"]["predecessor"]["cell_id"]}))
            with pytest.raises(TaskDeadlineRefused, match="^native continuation cannot replace an admitted workspace$"):
                task.bind_workspace(identity, owned._digest(self.document), old.continuation_binding())
            with pytest.raises(TaskDeadlineRefused, match="^native resume returned a different thread identifier$"):
                task.bind_thread("synthetic-failed-fresh-thread", resumed=True)
            with CostReceiptLedger(receipt_path, run_id=receipt_run) as ledger:
                assert ledger.calls_for(registration.TASK5) == receipts
                assert task.admit_attempt(restored.root) == 1 and task.bound_timeout(1800) == 1800
                task.bind_thread(bound["thread_id"], resumed=True)
                assert task.recovery_context(1) is None
                call_id = ledger.reserve(call_id="synthetic-turn-1", task_id=registration.TASK5,
                    stage="generation", retry_kind="none", provider="synthetic", requested_model="synthetic",
                    request_sha256=owned._digest(self.document))
                before = task.begin_turn(1, call_id, input_sha256=owned._digest(self.document), recovery_context=None)
                after = dict.fromkeys(before)
                task.observe_turn(1, after, terminal_reason="completed")
                settle_codex_turn(ledger, call_id,
                    totals=turn_usage_delta(CodexTokenTotals(**before), CodexTokenTotals(**after)))
                task.acknowledge_usage(1)
                assert len(ledger.calls_for(registration.TASK5)) == 2
            self.keep_record = task.as_record()
            assert self.keep_record["started_unix"] == original["started_unix"]
            assert self.keep_record["expires_unix"] == original["expires_unix"]
            assert self.keep_record["remaining_seconds"] == 10725 and self.keep_record["wait_seconds"] == 30
            assert self.keep_record["attempts_admitted"] == 2 and self.keep_record["native_resumes"] == 1
            assert self.keep_record["session_policy"] == "retained_native_thread"
            assert self.keep_record["total_seconds"] == 10800 and self.keep_record["attempt_seconds"] == 1800
            assert task.retired_continuations(identity) == []
            assert all(path.read_bytes() == data for path, data in markers.items())
            assert (old.workspace / "previous-cell-only.txt").read_bytes() == b"never adopt"
        finally:
            store.close()


def test_task5_keep_r1_is_the_closed_sixth_cell(tmp_path, monkeypatch, capsys, approved_pilot_source):
    production_plan = registration.compile_plan()
    pins = deepcopy(successor.PREDECESSOR)
    assert successor.CELL_ID == "0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_keep_r1"
    assert [(item.cell_id, item.ordinal, item.bundle, item.repetition) for item in controller.CELL_BINDINGS] == [
        (production_plan["order"][0], 0, "keep", 1), (production_plan["order"][1], 1, "fresh", 1),
        (production_plan["order"][2], 2, "fresh", 2), (production_plan["order"][3], 3, "keep", 2),
        (production_plan["order"][4], 4, "fresh", 1), (production_plan["order"][5], 5, "keep", 1),
        (production_plan["order"][6], 6, "keep", 2), (production_plan["order"][7], 7, "fresh", 2)]
    assert pins == {"cell_id": previous.CELL_ID,
        "producer_source_sha": "e5e338aa22c247133936fa075c2def7bffb95173", "run_id": "37032230813",
        "execution_job_id": 110933285330,
        "request_sha256": "9a53e9c0ae7b50400f2b27d514207e489b237cc5b5195ff8e36fcc4ea920370b",
        "terminal_commit": "94628d12162da2e00cace216fdda5ce41f57e47f",
        "terminal_identity": {"sha256": "5bc2eb37dd4ab83cd7653106166cc18d36c193eec12e2bc99b9bf429be6942cf", "size": 4188},
        "claim_commit": "fb39a92ccbaf26f1ab698510cf0914f73b17cb0e",
        "claim_identity": {"sha256": "6e06ae9c9e79201ec7eb28019de56ffa1d63b2cc6c8ab9569a267791733d260e", "size": 1891},
        "output_commit": "70a69c818be5c7d751a0481808dbba86aa983b19",
        "output_manifest_identity": {"sha256": "dff85ecf69ee2c38bbfe40280099d87ecd3989969512307671ac3e8a15e60cf4", "size": 2107},
        "output_objects_sha256": "6c7ea668caa8cf39569a1848a025bc534bb406c46b46874ea7fdd584870a24e2",
        "status": "failed", "exit_code": 1, "cleanup_confirmed": True}
    assert reader.TASK5_FRESH_R1.expectation == ci.TerminalExpectation(
        pins["request_sha256"], pins["producer_source_sha"], pins["cell_id"])
    assert reader.TASK5_FRESH_R1.run_id == pins["run_id"] and reader.TASK5_FRESH_R1.execution_job_id == pins["execution_job_id"]
    assert previous.PREDECESSOR["terminal_commit"] == "e55fac5d60191167dd66688510ec0fef472e594d"
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        pytest.fail("ordinal-five proof crossed a live, payload, grading or early-admission boundary")

    for name in ("core.executor.TaskExecutor.__init__", "step8_grade.main", "step8_grade.RubricLoader.load",
                 "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset"):
        monkeypatch.setattr(name, forbidden)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    # Exact old/new task discrimination uses actual canonical path/history
    # validation, not a patched verdict or replay of an older cell test suite.
    for binding in (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2, reader.TASK5_FRESH_R1):
        server = (_task5_fixture(production_plan) if binding is reader.TASK5_FRESH_R1
                  else FreshResultHF(production_plan, binding=binding))
        task_id = registration.TASK5 if binding is reader.TASK5_FRESH_R1 else registration.TASK4
        foreign = registration.TASK4 if task_id == registration.TASK5 else registration.TASK5
        publication = server.producer._publication_binding()
        assert fresh._publication_task_id(publication) == task_id
        with retained._session(server) as (api, token, deadline):
            verified = fresh._verify_publication(api, api.repo, TERMINAL_HEAD, server.terminal, server.claim,
                ci._cache(tmp_path, "path-" + str(binding.ordinal)), token, deadline, publication)
            assert verified["writer_acknowledgment"] == "not_established" and not verified["replay_authorized"]
            wrong = deepcopy(server.terminal)
            entry = next(item for item in wrong["completion"]["files"] if item["path"].startswith("deliverable_files/"))
            entry["path"] = "deliverable_files/" + foreign + "/report.txt"
            before = list(server.calls)
            with pytest.raises(ValueError, match="^deliverable path must stay under deliverable_files/" + task_id + "/$") as refused:
                fresh._verify_publication(api, api.repo, TERMINAL_HEAD, wrong, server.claim,
                    tmp_path / "never-cross-task", token, deadline, publication)
            assert type(refused.value) is ValueError and server.calls == before
        assert server.commits == []
    publication = successor._publication_binding()
    assert fresh._publication_task_id(publication) == registration.TASK5

    class ForeignPublication(fresh._PublicationBinding):
        pass

    for malformed in (None, True, {}, ForeignPublication(**vars(publication)), *(
            replace(publication, cell_id=cell) for cell in (
                None, True, 5, b"unknown", "unknown", successor.CELL_ID + "\n",
                controller.FIRST_CELL_ID, production_plan["order"][7] + "_unsupported"))):
        with pytest.raises(ci.RetentionCIRefused, match="^fixed_retention_publication_binding_required$"):
            fresh._verify_publication(None, None, TERMINAL_HEAD, {}, {},
                tmp_path / "never-unsupported-publication", None, 0, malformed)
    assert not (tmp_path / "never-cross-task").exists()
    assert not (tmp_path / "never-unsupported-publication").exists()

    seed = FailedPredecessorHF(production_plan)
    synthetic_pins = seed.synthetic_identities()  # Authored bytes, before any validator read.
    monkeypatch.setattr(successor, "PREDECESSOR", synthetic_pins)
    with tempfile.TemporaryDirectory(prefix=".retention-task5-keep-offline-", dir=REAL_ROOT.parent) as directory:
        host_parent = Path(directory)
        case = host_parent / "scenario"
        case.mkdir()
        plan, root, archive, sources = shared._scenario(case, monkeypatch, approved_pilot_source)
        scenario_roles = (shared.successor.FACADE, fresh.FACADE,
            "batch-runner/codex_retention_fresh_r1_result_intake.py")
        additional_roles = (successor.FACADE, previous.FACADE, previous.previous.FACADE)
        assert set(successor.SOURCE_PATHS) == {*scenario_roles, *additional_roles}
        # The shared scenario owns these copies; verify their current bytes.
        for role in (*scenario_roles, "batch-runner/codex_retention_result_intake.py"):
            assert (root / role).read_bytes() == (REAL_ROOT / role).read_bytes()
        for role in additional_roles:
            _write(root / role, (REAL_ROOT / role).read_bytes())
        _runtime(monkeypatch, root)
        base._environment(monkeypatch, host_parent)
        request = controller.Request(successor.CELL_ID, sources, root / successor.PACKET_ROLE, root,
            preparation.source_identity()["sha256"], controller.source_identity()["sha256"])
        packet = positive("task5_keep_packet", lambda: preparation.prepare_packet(cell_id=request.cell_id,
            sources=sources, output=request.packet, expected_preparer_sha256=request.expected_preparer_sha256, plan=plan))
        stage = positive("task5_keep_staging", lambda: controller.stage_runtime(request))
        assert stage["ordinal"] == 5 and stage["cell_id"] == successor.CELL_ID and stage["commands"] == []
        assert not any(stage[key] for key in ("launch_authorized", "inference_slot_reserved", "deadline_started"))
        assert stage["config_sha256"] == plan["cells"][5]["config_sha256"]
        assert (request.packet / preparation.INFERENCE).read_bytes() == controller._encoded(plan["cells"][5]["config"])
        assert stage["input_roles_sha256"] == packet["input_verification"]["original_input_roles_sha256"]
        assert controller.read_codex_prepared(controller.PREPARED)["execution"]["codex"]["task_deadline"] == {
            "condition": "retention_bundle_v1", "retention_bundle": "keep", "repetition": 1}
        assert controller._stage_paths(successor.CELL_ID) == tuple(root / "batch-runner/workspace" / name for name in (
            "retention-task5-keep-r1-staging.json", "retention-task5-keep-r1-staged.json"))
        with pytest.raises(controller.RetentionControllerRefused, match="^runtime_path_already_used_or_partial$"):
            controller.stage_runtime(request)
        document, observation = positive("task5_keep_request", lambda: successor.canonical_request(request,
            reviewed_source_sha=SOURCE, run_id="700000001", historical_root=archive))
        assert document["scope"] == successor.SCOPE and document["serial_domain"]["predecessor"] == synthetic_pins
        assert document["format"] == successor.REQUEST_FORMAT and document["provider"]["attempt"] == 1
        assert document["host"]["sdk"] == document["host"]["cli"] == "0.147.0"
        assert set(document["source"]["successor_adapter"]["files"]) == set(successor.SOURCE_PATHS)
        adapters = (fresh, previous.previous.previous, previous.previous, previous, successor)
        for cell, scope in ((None, ci.SCOPE), *((adapter.CELL_ID, adapter.SCOPE) for adapter in adapters)):
            argv = ["--reviewed-source-sha", SOURCE] + ([] if cell is None else ["--cell", cell])
            assert successor.main(argv) == 0
            result = json.loads(capsys.readouterr().out)
            assert result["mode"] == "plan_only" and result["scope"] == scope and result["commands"] == []
        with monkeypatch.context() as before_source:
            before_source.setattr(ci, "require_source", forbidden)
            for adapter, reason in ((fresh, "only_first_or_task4_fresh_r1_supported"),
                    (previous.previous.previous, "only_registered_task4_fresh_r2_supported"),
                    (previous.previous, "only_registered_task4_keep_r2_supported"),
                    (previous, "only_registered_task5_fresh_r1_supported")):
                assert adapter.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE]) == 2
                assert json.loads(capsys.readouterr().out)["reason"] == reason
            assert successor.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE, "--observe-locator"]) == 2
            assert json.loads(capsys.readouterr().out)["reason"] == "task5_keep_r1_locator_observation_not_supported"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        api = deepcopy(seed)
        child = KeepTransport(document, api, key)
        child.recovery_request = request
        grant = ci.ExecutionGrantRequest(SOURCE, owned._digest(document), archive)
        denied = host_parent / "not-admitted"
        for wrong in ("unregistered", True, 5, plan["order"][7] + "_unsupported"):
            with pytest.raises(controller.RetentionControllerRefused, match="^only_first_or_task4_fresh_r1_supported$"):
                controller.execute_first_cell(replace(request, cell_id=wrong), host_state=denied, grant=grant)
        with pytest.raises(controller.RetentionControllerRefused, match="^controller_source_mismatch$"):
            successor.execute(replace(request, expected_controller_sha256="0" * 64), host_state=denied, grant=grant)
        for malformed, reason in ((replace(grant, reviewed_source_sha="f" * 40), "clean_exact_retention_source_required"),
                                  (replace(grant, request_sha256="0" * 64), "approved_retention_request_changed")):
            with pytest.raises(ci.RetentionCIRefused, match="^" + reason + "$"):
                successor.execute(request, host_state=denied, grant=malformed, _test_transport=child, _test_api=api)
        with monkeypatch.context() as wrong_run:
            wrong_run.setenv("GITHUB_RUN_ID", "700000002")
            with pytest.raises(ci.RetentionCIRefused, match="^approved_retention_request_changed$"):
                successor.execute(request, host_state=denied, grant=grant, _test_transport=child, _test_api=api)
        pairs = ((ci._Admission, controller.FIRST_CELL_ID), (fresh._FreshAdmission, fresh.CELL_ID),
                 (previous.previous.previous._FreshR2Admission, previous.previous.previous.CELL_ID),
                 (previous.previous._KeepR2Admission, previous.previous.CELL_ID),
                 (previous._Task5FreshR1Admission, previous.CELL_ID), (successor._Task5KeepR1Admission, successor.CELL_ID))
        with monkeypatch.context() as before_context:
            before_context.setattr(controller, "_context", forbidden)
            for admission_class, expected_cell in pairs:
                for _, selected_cell in pairs:
                    if expected_cell == selected_cell:
                        continue
                    crossed = replace(request, cell_id=selected_cell)
                    admission = admission_class(crossed, document, observation, {}, child, api)
                    with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
                        controller._run_post_authority_cell(crossed, host_state=denied, _admission=admission)
            class Noncanonical(successor._Task5KeepR1Admission):
                pass
            with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
                controller._run_post_authority_cell(request, host_state=denied,
                    _admission=Noncanonical(request, document, observation, {}, child, api))
        assert not denied.exists() and api.calls == [] and child.children == [] and child.github_calls == 0
        bad_approval = KeepTransport(document, deepcopy(seed), key)
        bad_approval.provider[2][0]["comment"] = ci.APPROVAL_PREFIX + "0" * 64
        with pytest.raises(ci.RetentionCIRefused, match="^owner_environment_request_approval_mismatch$"):
            successor.execute(request, host_state=denied, grant=grant, _test_transport=bad_approval, _test_api=bad_approval.api)
        assert not denied.exists() and bad_approval.api.calls == []

        original_error_context = output._error_context
        diagnostic = {"api": api, "child": child}

        def observe_error(error):
            """Preserve an unexpected original cause without printing its body."""
            classification = original_error_context(error)
            if classification[0] == "hf_operation_failed":
                chain, current = [], error
                while current is not None and len(chain) < 8:
                    frames, trace = [], current.__traceback__
                    while trace is not None and len(frames) < 32:
                        path = Path(trace.tb_frame.f_code.co_filename)
                        if path.is_relative_to(REAL_ROOT):
                            frames.append({"file": path.relative_to(REAL_ROOT).as_posix(), "line": trace.tb_lineno,
                                           "operation": trace.tb_frame.f_code.co_name})
                        trace = trace.tb_next
                    chain.append({"exception_class": type(current).__name__, "frames": frames})
                    current = current.__cause__ or current.__context__
                server = diagnostic["api"]
                print(json.dumps({"diagnostic": "task5_keep_original_exception", "chain": chain,
                    "state_counts": {"commit_attempts": len(server.commits),
                        "committed_terminal_controls": sum(server.writers[head].get(successor.TERMINAL) == head
                                                           for head in server.parents),
                        "owned_children": len(diagnostic["child"].children)}}, sort_keys=True))
            return classification

        monkeypatch.setattr(output, "_error_context", observe_error)
        cases = {"grade_parent": "task5_keep_r1_predecessor_head_mismatch",
            "task4_parent": "task5_keep_r1_predecessor_head_mismatch",
            "terminal_hash": "task5_keep_r1_predecessor_identity_mismatch",
            "claim_hash": "task5_keep_r1_predecessor_identity_mismatch",
            "manifest_hash": "task5_keep_r1_predecessor_identity_mismatch",
            "objects_hash": "task5_keep_r1_predecessor_identity_mismatch",
            "source": "fresh_result_completion_mismatch", "run": "fresh_result_authority_binding_mismatch",
            "job": "fresh_terminal_execution_job_mismatch", "bool_job": "fresh_result_authority_binding_mismatch",
            "request": "fresh_result_terminal_binding_mismatch", "cell": "fresh_result_completion_mismatch",
            "predecessor": "fresh_result_predecessor_mismatch", "status": "fresh_terminal_unsuccessful_required",
            "stopped": "task5_keep_r1_predecessor_identity_mismatch",
            "cleanup": "fresh_result_completion_mismatch", "history": "retention_control_history_mismatch",
            "object_history": "remote_output_history_mismatch", "namespace": "retention_namespace_already_used",
            "cas_race": "hf_http_failed", "lost_claim": "hf_transport_failed"}
        for fault, reason in cases.items():
            server, expected = deepcopy(seed), deepcopy(synthetic_pins)
            if fault == "source":
                server.summary["source_sha"] = "0" * 40
            elif fault in ("run", "job", "bool_job"):
                for authority in (server.claim["authority"], server.terminal["authority"]):
                    authority["provider_run_id" if fault == "run" else "provider_job_id"] = (
                        "700000009" if fault == "run" else True if fault == "bool_job" else 700000009)
            elif fault == "request":
                server.terminal["request_sha256"] = "0" * 64
            elif fault == "cell":
                server.summary["cell_id"] = successor.CELL_ID
            elif fault == "predecessor":
                server.claim["expected_parent"] = "0" * 40
            elif fault in ("status", "stopped"):
                server.summary["status"] = "succeeded" if fault == "status" else "stopped"
            elif fault == "cleanup":
                server.summary["cleanup_confirmed"] = False
            server.seed()
            if fault in ("grade_parent", "task4_parent"):
                server.head = ("76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e" if fault == "grade_parent"
                               else previous.PREDECESSOR["terminal_commit"])
                server.trees[server.head] = {}
            elif fault in ("terminal_hash", "claim_hash", "manifest_hash"):
                expected[{"terminal_hash": "terminal_identity", "claim_hash": "claim_identity",
                          "manifest_hash": "output_manifest_identity"}[fault]]["sha256"] = "0" * 64
            elif fault == "objects_hash":
                expected["output_objects_sha256"] = "0" * 64
            elif fault == "history":
                server.writers[server.head][previous.TERMINAL] = pins["output_commit"]
            elif fault == "object_history":
                server.writers[pins["output_commit"]][previous.OUTPUT + "/" + reader.intake.RESULT] = pins["claim_commit"]
            elif fault == "namespace":
                server.trees[server.head][successor.CLAIM] = b"already used"
                server.writers[server.head][successor.CLAIM] = server.head
            elif fault == "cas_race":
                server.move_before_commit = True
            elif fault == "lost_claim":
                server.lost = "admission"
            transport = KeepTransport(document, server, key)
            diagnostic.update(api=server, child=transport)
            authority = ci.verify_approval(document, transport)
            admission = successor._Task5KeepR1Admission(request, document, observation, authority, transport, server)
            private = host_parent / ("refused-" + fault)
            private.mkdir(mode=0o700)
            with monkeypatch.context() as synthetic:
                synthetic.setattr(successor, "PREDECESSOR", expected)
                with pytest.raises(ci.RetentionCIRefused, match="^retention_claim_unresolved:"):
                    admission.admit(private)
            receipt = retained._read(private / "remote-admission-receipt.json")
            assert receipt["outcome"] == "unresolved" and receipt["reason"] == reason, fault
            assert transport.children == [] and not (private / "deadline").exists()
            assert server.commits == (["admission"] if fault in ("cas_race", "lost_claim") else [])
            with pytest.raises(FileExistsError):
                admission.admit(private)
        print("BOUNDARY ordinal5: exact authority, predecessor/control/history, CAS and uncertain-claim refusals passed")
        snapshot = host_parent / "staged-snapshot"
        shutil.copytree(root, snapshot)
        host = host_parent / "completed"
        diagnostic.update(api=api, child=child)
        result = positive("task5_keep_claim_recovery_child_output_terminal", lambda: controller.execute_first_cell(request,
            host_state=host, grant=grant, _test_transport=child, _test_api=api))
        assert result == {"cell_id": successor.CELL_ID, "status": "succeeded", "request_sha256": grant.request_sha256,
            "cleanup_confirmed": True, "remote_terminal": "acknowledged", "grade": None,
            "grading_launched": False, "invoice_complete": False}
        assert child.keep_record["retention_bundle"] == "keep" and child.keep_record["repetition"] == 1
        assert api.events == ["admission", "child", "output", "terminal"]
        assert api.parents[api.parents[api.parents[api.head]]] == pins["terminal_commit"]
        assert all(name in {previous.CLAIM, previous.TERMINAL, previous.OUTPUT + "/" + output.MANIFEST}
                   for revision, name in api.downloads if revision in (
                       pins["terminal_commit"], pins["claim_commit"], pins["output_commit"]))
        claim = retained._read(host / "remote-admission-receipt.json")["claim"]
        terminal = retained._read(host / "remote-terminal-expected.json")
        assert claim["expected_parent"] == pins["terminal_commit"] and claim["predecessor"] == synthetic_pins
        assert terminal["format"] == successor.TERMINAL_FORMAT and terminal["completion"]["format"] == successor.OUTPUT_FORMAT
        held = (host / "remote-terminal-receipt.json").read_bytes()
        with retained._session(api) as (server, token, deadline):
            wrong = deepcopy(terminal)
            deliverable = next(item for item in wrong["completion"]["files"] if item["path"].startswith("deliverable_files/"))
            assert deliverable["path"].startswith("deliverable_files/" + registration.TASK5 + "/")
            deliverable["path"] = "deliverable_files/" + registration.TASK4 + "/report.txt"
            before = list(api.calls)
            with pytest.raises(ValueError,
                    match="^deliverable path must stay under deliverable_files/" + registration.TASK5 + "/$") as refused:
                successor.verify_terminal(server, server.repo, server.head, wrong, claim,
                    host / "never-task5-path-read", token, deadline)
            assert type(refused.value) is ValueError and api.calls == before
            reconciled = successor.verify_terminal(server, server.repo, server.head, terminal, claim,
                ci._cache(host, "reconcile"), token, deadline)
        assert reconciled["writer_acknowledgment"] == "not_established" and reconciled["replay_authorized"] is False
        assert (host / "remote-terminal-receipt.json").read_bytes() == held
        with pytest.raises(controller.RetentionControllerRefused, match="^first_cell_already_reserved_or_partial_no_replay$"):
            successor.execute(request, host_state=host, grant=grant, _test_transport=child, _test_api=api)
        assert len(child.children) == 1 and api.commits == ["admission", "output", "terminal"]
        print("BOUNDARY ordinal5: KEEP receipt/recovery/cumulative clock, execute-return and terminal acknowledgment passed")
        for fault in ("lost_terminal", "cleanup", "timeout", "remote_no_replay"):
            trial_root = host_parent / ("source-" + fault)
            shutil.copytree(snapshot, trial_root)
            with monkeypatch.context() as trial:
                _runtime(trial, trial_root)
                selected = replace(request, packet=trial_root / successor.PACKET_ROLE, runtime_checkout=trial_root)
                current, _ = successor.canonical_request(selected, reviewed_source_sha=SOURCE,
                    run_id="700000001", historical_root=archive)
                assert current == document
                server = deepcopy(api if fault == "remote_no_replay" else seed)
                server.lost = "terminal" if fault == "lost_terminal" else None
                transport = KeepTransport(current, server, key, mode=fault if fault in ("cleanup", "timeout") else "ordinary")
                diagnostic.update(api=server, child=transport)
                private = host_parent / fault
                if fault == "timeout":
                    stopped = positive("task5_keep_timeout_cleanup_publication", lambda: successor.execute(selected,
                        host_state=private, grant=grant, _test_transport=transport, _test_api=server))
                    assert stopped["status"] == "stopped" and stopped["cleanup_confirmed"] is True
                    timed = owned._load(private / "cell.json")
                    assert timed["reason"] == "child_timeout_partial_accounting" and timed["exit_code"] is None
                    clock = controller._deadline(private, controller._context(selected), stage, transport)
                    try:
                        assert clock.for_task(registration.TASK5).remaining_seconds() == 0
                    finally:
                        clock.close()
                else:
                    error_type = owned.OwnedChildCleanupRefused if fault == "cleanup" else ci.RetentionCIRefused
                    with pytest.raises(error_type):
                        successor.execute(selected, host_state=private, grant=grant, _test_transport=transport, _test_api=server)
                    if fault == "cleanup":
                        assert not (private / "remote-terminal-reserved.json").exists()
                        assert owned._load(private / "owned-child.json")["phase"] == "running"
                    elif fault == "remote_no_replay":
                        assert retained._read(private / "remote-admission-receipt.json")["reason"] == "task5_keep_r1_predecessor_head_mismatch"
                        assert transport.children == [] and not (private / "deadline").exists()
                    else:
                        receipt = retained._read(private / "remote-terminal-receipt.json")
                        assert receipt["outcome"] == "unresolved" and receipt["reason"] == "hf_transport_failed"
                        held = (private / "remote-terminal-receipt.json").read_bytes()
                        expected_terminal = retained._read(private / "remote-terminal-expected.json")
                        expected_claim = retained._read(private / "remote-admission-receipt.json")["claim"]
                        before = (list(server.commits), len(transport.children))
                        with retained._session(server) as (memory, token, deadline):
                            view = successor.verify_terminal(memory, memory.repo, memory.head, expected_terminal,
                                expected_claim, ci._cache(private, "lost-ack-observation"), token, deadline)
                        assert view["writer_acknowledgment"] == "not_established" and view["observation_only"] is True
                        assert (private / "remote-terminal-receipt.json").read_bytes() == held
                        assert (server.commits, len(transport.children)) == before
                assert len(transport.children) == (0 if fault == "remote_no_replay" else 1)
                assert server.commits == (["admission"] if fault == "cleanup" else ["admission", "output", "terminal"])
        assert effects == [] and base.PRIVATE.decode() not in capsys.readouterr().out
    print("OFFLINE ordinal5: exact failed TASK5_FRESH_R1 controls-only parent; canonical Task4/Task5 paths; authority/CAS, own KEEP recovery, receipts/cumulative clock, acknowledgment/reconciliation/lost-ack/no-replay/timeout/cleanup passed; no live effects")


def test_task5_keep_r1_routes_and_current_pins_preserve_fixed_readers(tmp_path, monkeypatch):
    # This import dependency was resolved at collection; real Popen stays blocked.
    assert subprocess.Popen is not workflow_contract._assert_retention_execution_workflow_contract.__globals__["REAL_POPEN"]
    workflow_contract._assert_retention_execution_workflow_contract()
    workflow_contract._assert_retention_mode_routes()
    workflow = yaml.safe_load((REAL_ROOT / ci.WORKFLOW).read_bytes())
    jobs = workflow["jobs"]
    steps = jobs[ci.PREPARE_JOB]["steps"]
    fixed_readers = (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2, reader.TASK5_FRESH_R1,
                     reader.TASK5_KEEP_R1, reader.TASK5_KEEP_R2, reader.TASK5_FRESH_R2)
    read_group = " && (" + " || ".join("inputs.cell_id == '" + binding.expectation.cell_id + "'" for binding in fixed_readers) + ")"
    assert steps[9]["if"] == steps[10]["if"] == (
        "inputs.read_result && !inputs.observe_terminal && !inputs.prepare && !inputs.execute && !inputs.observe_locator" + read_group)
    assert steps[13]["if"] == steps[14]["if"] == (
        "inputs.observe_terminal && !inputs.read_result && !inputs.prepare && !inputs.execute && !inputs.observe_locator" + read_group)
    assert steps[9]["run"] == steps[13]["run"]
    for index in (9, 13):
        assert "env" not in steps[index] and "secrets." not in steps[index]["run"]
        pins = re.findall(r"'([0-9a-f]{64})  (batch-runner/[^']+)'", steps[index]["run"])
        assert len(pins) == 11
        for digest, path in pins:
            assert hashlib.sha256((REAL_ROOT / path).read_bytes()).hexdigest() == digest
        assert steps[index + 1]["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
        assert successor.CELL_ID + ")" in steps[index + 1]["run"]
        assert "retention_read_source=" + reader.TASK5_KEEP_R1.expectation.source_sha in steps[index + 1]["run"]
        assert "retention_read_request=" + reader.TASK5_KEEP_R1.expectation.request_sha256 in steps[index + 1]["run"]
        assert "--expected-reader-sha256 " + reader.reader_identity()["module_sha256"] in steps[index + 1]["run"]
    assert jobs[ci.EXECUTE_JOB]["timeout-minutes"] == 240
    assert successor.CELL_ID + ') retention_host="$RUNNER_TEMP/retention-task5-keep-r1-host" ;;' in jobs[ci.EXECUTE_JOB]["steps"][-1]["run"]
    assert (REAL_ROOT / previous.FACADE).read_bytes() and hashlib.sha256((REAL_ROOT / previous.FACADE).read_bytes()).hexdigest() == reader.TASK5_PRODUCER_PIN[1]
    assert reader.FRESH_R1.expectation is reader.EXPECTATION
    for binding in fixed_readers:
        checked, plan, cell = reader._binding(binding.expectation, reader.reader_identity()["module_sha256"],
            TERMINAL_HEAD, False, **({} if binding is reader.FRESH_R1 else {"binding": binding}))
        assert cell["index"] == binding.ordinal and plan["order"][binding.ordinal] == binding.expectation.cell_id
        assert {name: checked[name] for name in reader._frozen(binding)} == {
            name: pair[1] for name, pair in reader._frozen(binding).items()}
    for invalid in (replace(reader.TASK5_FRESH_R1), None, True):
        with pytest.raises(output.OutputPublicationRefused, match="^fixed_fresh_read_binding_required$"):
            reader._fixed_binding(invalid)
    bridge = observer.bridge
    fixed = bridge._fixed("retention/keep-r2")
    historical = deepcopy((bridge.RESULT, bridge.PARENT, bridge.READER, fixed.RESULT, fixed.PARENT, fixed.READER))
    assert bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    assert bridge.fixed_evidence_sha256(fixed.SELECTOR) == "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
    assert fixed.RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    assert fixed.READER["module_sha256"] == "5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583"
    assert fixed.READER["controller_sha256"] == "957934b869ed5071923add7e9554aa68de941c9488f3e6d650557d27f6179601"
    assert observer.CURRENT_DEPENDENCIES["codex_retention_fresh_r1_result_intake.py"] == reader.reader_identity()["module_sha256"]
    for name, digest in observer.CURRENT_DEPENDENCIES.items():
        assert hashlib.sha256((REAL_ROOT / "batch-runner" / name).read_bytes()).hexdigest() == digest
    common = tmp_path / "git-common"
    common.mkdir()
    state = {"head": SOURCE, "diff": b"", "status": b"", "config": b""}

    def git(path, *command, ok=(0,)):
        assert Path(path) == REAL_ROOT
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(REAL_ROOT) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (state["head"] + "\n").encode(),
            ("diff", "--name-only", "HEAD", "--"): state["diff"],
            ("status", "--porcelain", "--untracked-files=normal"): state["status"],
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): state["config"]}
        assert command in answers  # Only Git metadata transport is synthetic, not the guards.
        return SimpleNamespace(stdout=answers[command], returncode=0)

    monkeypatch.setattr(source_checkout, "_git", git)
    monkeypatch.setattr(owned, "_git", git)
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        pytest.fail("current-source check reached a private, credential or paid boundary")

    for owner, name in ((retained, "_session"), (observer.grade, "_root"), (bridge, "prepare"), (bridge, "judge")):
        monkeypatch.setattr(owner, name, forbidden)
    for selector in (observer.SELECTOR, observer.KEEP_R2_SELECTOR):
        observer._source_current(SOURCE, selector=selector)
    bridge._source(bridge.compile_request(SOURCE))  # Historical first-cell behavior stays intact.
    with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_reader_required$"):
        bridge._source(bridge.compile_request(SOURCE, selector=fixed.SELECTOR))
    real_bytes = output._bytes
    for filename in ("codex_retention_first_cell.py", "codex_retention_task4_fresh_r1.py",
                     "codex_retention_fresh_r1_result_intake.py"):
        for missing in (False, True):
            with monkeypatch.context() as bad:
                def changed(path, **kwargs):
                    if Path(path).name == filename:
                        if missing:
                            raise FileNotFoundError("synthetic missing current dependency")
                        return real_bytes(path, **kwargs) + b"\n"
                    return real_bytes(path, **kwargs)
                bad.setattr(output, "_bytes", changed)
                with pytest.raises(FileNotFoundError if missing else output.OutputPublicationRefused,
                        match="^synthetic missing current dependency$" if missing else "^reviewed_retention_observer_dependency_required$"):
                    observer._source_current(SOURCE, selector=observer.KEEP_R2_SELECTOR)
    for name, value, reason in (("head", "e" * 40, "retention_grade_source_changed"),
            ("diff", b"tracked.py\n", "retention_grade_source_changed"),
            ("status", b"?? untracked.py\n", "clean_retention_grade_source_required"),
            ("config", b"include.path\n", "checkout filters, includes or partial-clone configuration are unsupported")):
        saved, state[name] = state[name], value
        with pytest.raises(ValueError, match="^" + reason + "$"):
            observer._source_current(SOURCE)
        state[name] = saved
    assert historical == (bridge.RESULT, bridge.PARENT, bridge.READER, fixed.RESULT, fixed.PARENT, fixed.READER)
    assert effects == []
    print("OFFLINE ordinal5 routing: exact eight-cell execution/seven-result/six-terminal allowlists; 288 mode cases; guarded helper imports; current pins/source refusals and immutable historical grading evidence preserved")
