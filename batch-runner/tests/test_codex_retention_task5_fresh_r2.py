"""One ordinal-seven lifecycle proof with real guards and synthetic owned effects."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric import rsa

import codex_retention_task5_fresh_r2 as successor
import codex_retention_grade_readout as observer
from core.codex_cost import CodexTokenTotals, settle_codex_turn, turn_usage_delta
from core.codex_runner import CodexWorkspace
from core.codex_task_deadline import TaskDeadlineRefused
from core.cost_receipts import CostReceiptLedger
from . import test_codex_retention_task5_keep_r2 as prior
from . import test_codex_retention_ci_observation as workflow_contract
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
from .test_codex_retention_result_intake import TERMINAL_HEAD

previous, fresh, reader, ci = successor.previous, successor.fresh, successor.reader, successor.ci
controller, preparation, registration = successor.controller, successor.preparation, successor.registration
owned, retained, output = successor.owned, successor.retained, successor.output
shared, base = prior.shared, prior.base
REAL_ROOT, SOURCE, _write = prior.REAL_ROOT, prior.SOURCE, prior._write


def _runtime(monkeypatch, root):
    prior._runtime(monkeypatch, root)
    monkeypatch.setattr(successor, "ROOT", root)


class FreshTransport(shared.R2Transport):
    ordinal, repetition, cell_id, bundle = 7, 2, successor.CELL_ID, "fresh"
    recovery_request = None
    fresh_record = None

    def owned_process(self, command, **options):
        if self.recovery_request is not None:
            self._fresh_recovery(options["ownership"][0].parent)
        return super().owned_process(command, **options)

    def _fresh_recovery(self, host):
        """Use real store/receipts and guarded cleanup; no native/model call."""
        request = self.recovery_request
        context, stage = controller._context(request), controller.verify_staged_runtime(request)
        predecessor = CodexWorkspace.create(task_id="synthetic-prior-keep-r2-cell")
        _write(predecessor.workspace / "prior-only.txt", b"never import")
        workspace = CodexWorkspace.create(task_id=registration.TASK5)
        assert workspace.root != predecessor.root and list(workspace.workspace.iterdir()) == []
        outputs = controller.ROOT / "batch-runner/workspace/upload/deliverable_files" / registration.TASK5
        outputs.mkdir(parents=True)
        neighbor = host / "synthetic-prior-output" / "prior-only.txt"
        _write(neighbor, b"unrelated output")
        identity = owned._digest({"cell_id": self.cell_id, "request_sha256": owned._digest(self.document)})
        store = controller._deadline(host, context, stage, self)
        try:
            task = store.for_task(registration.TASK5)
            assert task.fresh_bundle and not task.retains_thread and store.control.max_attempts is None
            assert task.continuation() is None and task.remaining_seconds() == 10800
            original = task.as_record()
            task.bind_fresh_output_directory(outputs)
            assert task.admit_attempt(workspace.root) == 0
            task.bind_workspace(identity, owned._digest(self.document), workspace.continuation_binding())
            owned_folders = (workspace.workspace, workspace.home, workspace.codex_home, outputs)
            for folder in owned_folders:
                _write(folder / "fresh-only.txt", b"discard only this owned bundle")
            task.thread_starting()
            with pytest.raises(TaskDeadlineRefused,
                    match="^native thread creation was interrupted before its identifier was bound$"):
                task.require_fresh_retirement(task.continuation(identity))
            assert task.retired_continuations(identity) == []
            assert all((folder / "fresh-only.txt").read_bytes() == b"discard only this owned bundle"
                       for folder in owned_folders)
            task.bind_thread("synthetic-task5-fresh-r2-first-thread", resumed=False)
            bound = task.continuation(identity)
            assert bound["phase"] == "bound" and bound["thread_id"] == "synthetic-task5-fresh-r2-first-thread"
            for retirement in (task.require_fresh_retirement, task.retire_fresh_bundle):
                with pytest.raises(TaskDeadlineRefused, match="^fresh bundle lacks a reconciled eligible recovery$"):
                    retirement(bound)
            assert task.continuation(identity) == bound and task.retired_continuations(identity) == []
            assert all((folder / "fresh-only.txt").read_bytes() == b"discard only this owned bundle"
                       for folder in owned_folders)
            assert task.recovery_context(0) is None  # Mechanical B, no C feedback.
            receipt_path = host / "synthetic-fresh-recovery.sqlite"
            with CostReceiptLedger(receipt_path, run_id="synthetic-task5-fresh-r2-recovery") as ledger:
                call_id = ledger.reserve(call_id="synthetic-turn-0", task_id=registration.TASK5,
                    stage="generation", retry_kind="none", provider="synthetic", requested_model="synthetic",
                    request_sha256=owned._digest(self.document))
                before = task.begin_turn(0, call_id, input_sha256=owned._digest(self.document), recovery_context=None)
                after = dict.fromkeys(before)  # Missing usage is not zero cost.
                task.observe_turn(0, after, failure_observation={
                    "category": "rate_limited", "http_status_code": 429, "retry_guidance": None})
                with pytest.raises(TaskDeadlineRefused, match="^fresh bundle lacks a reconciled eligible recovery$"):
                    task.require_fresh_retirement(task.continuation(identity))
                settle_codex_turn(ledger, call_id,
                    totals=turn_usage_delta(CodexTokenTotals(**before), CodexTokenTotals(**after)))
                task.acknowledge_usage(0)
                receipts = ledger.calls_for(registration.TASK5)
                assert len(receipts) == 1 and receipts[0]["call_id"] == call_id and receipts[0]["state"] == "settled"
            task.wait(30, lambda seconds: setattr(self.clock, "now", self.clock.now + seconds))
        finally:
            store.close()
        self.clock.now += 45  # Synthetic downtime; no sleep or clock reset.
        store = controller._deadline(host, context, stage, self)
        try:
            task = store.for_task(registration.TASK5)
            with pytest.raises(TaskDeadlineRefused, match="^native continuation request/runtime identity mismatch$"):
                task.continuation(owned._digest({"cell_id": previous.CELL_ID}))
            bound = task.continuation(identity)
            assert bound["phase"] == "bound" and bound["native_resumes"] == 0 and bound["terminal_reason"] is None
            assert len(bound["turns"]) == 1 and bound["turns"][0]["phase"] == "settled"
            assert bound["turns"][0]["before"] == dict.fromkeys(before, 0)
            assert bound["turns"][0]["failure_observation"] == {
                "category": "rate_limited", "http_status_code": 429, "retry_guidance": None}
            with CostReceiptLedger(receipt_path, run_id="synthetic-task5-fresh-r2-recovery") as ledger:
                assert ledger.calls_for(registration.TASK5) == receipts
                assert bound["turns"][0]["call_id"] == receipts[0]["call_id"]
            task.require_fresh_retirement(bound)
            with pytest.raises(TaskDeadlineRefused, match="^retired native workspace is still present or unsafe$"):
                task.retire_fresh_bundle(bound)
            assert task.continuation(identity) == bound and task.retired_continuations(identity) == []
            assert all((folder / "fresh-only.txt").read_bytes() == b"discard only this owned bundle"
                       for folder in owned_folders)
            task.clear_fresh_outputs()
            assert list(outputs.iterdir()) == [] and neighbor.read_bytes() == b"unrelated output"
            CodexWorkspace.remove_owned_bundle(bound["workspace"])
            task.retire_fresh_bundle(bound)
            assert not workspace.root.exists() and predecessor.workspace.joinpath("prior-only.txt").read_bytes() == b"never import"
            assert task.continuation(identity) is None and task.retired_continuations(identity) == [bound]
            replacement = CodexWorkspace.create(task_id=registration.TASK5)
            assert replacement.root not in (workspace.root, predecessor.root)
            assert all(not (folder / "fresh-only.txt").exists()
                       for folder in (replacement.workspace, replacement.home, replacement.codex_home))
            assert task.admit_attempt(replacement.root) == 1 and task.bound_timeout(1800) == 1800
            task.bind_workspace(identity, owned._digest(self.document), replacement.continuation_binding())
            task.thread_starting()
            task.bind_thread("synthetic-task5-fresh-r2-second-thread", resumed=False)
            assert task.recovery_context(1) is None
            with CostReceiptLedger(receipt_path, run_id="synthetic-task5-fresh-r2-recovery") as ledger:
                assert ledger.calls_for(registration.TASK5) == receipts
                call_id = ledger.reserve(call_id="synthetic-turn-1", task_id=registration.TASK5,
                    stage="generation", retry_kind="infrastructure", provider="synthetic", requested_model="synthetic",
                    request_sha256=owned._digest(self.document))
                before = task.begin_turn(1, call_id, input_sha256=owned._digest(self.document), recovery_context=None)
                after = dict.fromkeys(before)
                task.observe_turn(1, after, terminal_reason="completed")
                settle_codex_turn(ledger, call_id,
                    totals=turn_usage_delta(CodexTokenTotals(**before), CodexTokenTotals(**after)))
                task.acknowledge_usage(1)
                settled = ledger.calls_for(registration.TASK5)
                assert settled[0] == receipts[0] and [row["state"] for row in settled] == ["settled", "settled"]
            self.fresh_record = task.as_record()
            assert self.fresh_record["started_unix"] == original["started_unix"]
            assert self.fresh_record["expires_unix"] == original["expires_unix"]
            assert self.fresh_record["remaining_seconds"] == 10725 and self.fresh_record["wait_seconds"] == 30
            assert self.fresh_record["attempts_admitted"] == 2 and self.fresh_record["native_resumes"] == 0
            assert self.fresh_record["retired_attempts"] == 1 and self.fresh_record["session_policy"] == "fresh_owned_bundle"
            assert self.fresh_record["total_seconds"] == 10800 and self.fresh_record["attempt_seconds"] == 1800
        finally:
            store.close()


def test_task5_fresh_r2_is_the_closed_eighth_cell(tmp_path, monkeypatch, capsys, approved_pilot_source):
    production_plan = registration.compile_plan()
    pins = deepcopy(successor.PREDECESSOR)
    assert successor.CELL_ID == "0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_fresh_r2"
    assert [(item.cell_id, item.ordinal, item.bundle, item.repetition) for item in controller.CELL_BINDINGS] == [
        (production_plan["order"][0], 0, "keep", 1), (production_plan["order"][1], 1, "fresh", 1),
        (production_plan["order"][2], 2, "fresh", 2), (production_plan["order"][3], 3, "keep", 2),
        (production_plan["order"][4], 4, "fresh", 1), (production_plan["order"][5], 5, "keep", 1),
        (production_plan["order"][6], 6, "keep", 2), (production_plan["order"][7], 7, "fresh", 2)]
    assert pins == {"cell_id": previous.CELL_ID,
        "producer_source_sha": "bdb7c21111a4c86136b6158f4969a39a9950acb3", "run_id": "37081963299",
        "execution_job_id": 111085094584,
        "request_sha256": "1b042b77fcc80b8c1a1c21fdd73feeefbcb80ce7f505b7c842aba496419386ac",
        "terminal_commit": "3be1c0b892a199fdfccf3d5c4379d40c782119e5",
        "terminal_identity": {"sha256": "7510ea45f39271a751e7c2805a5b2048b83c5f31e5f7f48e7afeff2091e77885", "size": 4179},
        "claim_commit": "e7db56481f7cb2d908a9362ad1091022237afd21",
        "claim_identity": {"sha256": "bc3ad16ea05ed02a1fb3b0fd082b10abdad4bf90103fbfd7ade69e4bce55e4a3", "size": 1887},
        "output_commit": "3984e404ba59e0b7f356ca5d0426b57d4477ea50",
        "output_manifest_identity": {"sha256": "bfb8ad4caddc0625dd9e9f92f7f67df5d465b160e69adc28f844f13d163673cb", "size": 2102},
        "output_objects_sha256": "4104dd725feac4591c05436ca03a4fe3aca9be8a2cf9e82a484f3ef62b1e3670",
        "status": "failed", "exit_code": 1, "cleanup_confirmed": True}
    assert reader.TASK5_KEEP_R2.expectation == ci.TerminalExpectation(
        pins["request_sha256"], pins["producer_source_sha"], pins["cell_id"])
    assert reader.TASK5_KEEP_R2.run_id == pins["run_id"] and reader.TASK5_KEEP_R2.execution_job_id == pins["execution_job_id"]
    assert reader.TASK5_KEEP_R2.materialized_grader_source_sha256 == "81bfae73b21f260ffd4985d701631f53c4ee7cb67e4d1a7ff39a7563598bbc6f"
    assert previous.PREDECESSOR["terminal_commit"] == "33278d9c26e8c8e8cfe68649e482e01f684d7705"
    assert successor.PACKET_ROLE == "batch-runner/workspace/retention-ci-task5-fresh-r2"
    assert successor.PACKET_ROLE != previous.PACKET_ROLE and successor.PREFIX != previous.PREFIX
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        pytest.fail("ordinal-seven proof crossed a live, payload, grading or early-admission boundary")

    for name in ("core.executor.TaskExecutor.__init__", "step8_grade.main", "step8_grade.RubricLoader.load",
                 "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset"):
        monkeypatch.setattr(name, forbidden)
    with monkeypatch.context() as no_private:
        for owner, name in ((retained, "_session"), (observer.grade, "_root"),
                            (observer.bridge, "prepare"), (observer.bridge, "judge")):
            no_private.setattr(owner, name, forbidden)
        prior._routes_and_current_sources(tmp_path, no_private)
        workflow = yaml.safe_load((REAL_ROOT / ci.WORKFLOW).read_bytes())
        steps = workflow["jobs"][ci.PREPARE_JOB]["steps"]
        for index in (9, 10, 13, 14):
            assert successor.CELL_ID in steps[index]["if"]
            assert successor.CELL_ID in steps[index]["run"]
        for index in (11, 12):
            assert successor.CELL_ID not in steps[index]["if"]
            assert successor.CELL_ID not in steps[index]["run"]
        assert successor.CELL_ID + ') retention_host="$RUNNER_TEMP/retention-task5-fresh-r2-host" ;;' in workflow["jobs"][ci.EXECUTE_JOB]["steps"][-1]["run"]
        assert subprocess.Popen is not workflow_contract._assert_retention_execution_workflow_contract.__globals__["REAL_POPEN"]
        with pytest.raises(output.OutputPublicationRefused, match="^fixed_fresh_read_binding_required$"):
            reader._fixed_binding(replace(reader.TASK5_KEEP_R2,
                expectation=replace(reader.TASK5_KEEP_R2.expectation, cell_id=successor.CELL_ID),
                ordinal=7, retention_bundle="fresh"))
    with capsys.disabled():
        print("BOUNDARY ordinal7: 288 closed mode cases; eight execution/eight result/seven terminal routes; current dependency bytes and frozen grading evidence passed")
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    # The unchanged canonical predicate remains task-specific for every closed
    # publication binding. Full publication/history is reached below for ordinal7.
    old_adapters = (fresh, previous.previous.previous.previous.previous, previous.previous.previous.previous, previous.previous.previous,
                    previous.previous, previous)
    for adapter in (*old_adapters, successor):
        task_id = registration.TASK4 if adapter in old_adapters[:3] else registration.TASK5
        foreign = registration.TASK4 if task_id == registration.TASK5 else registration.TASK5
        publication = adapter._publication_binding()
        assert fresh._publication_task_id(publication) == task_id
        canonical = "deliverable_files/" + task_id + "/report.txt"
        assert ci.canonical_deliverable_path(fresh._publication_task_id(publication), canonical) == canonical
        with pytest.raises(ValueError, match="^deliverable path must stay under deliverable_files/" + task_id + "/$"):
            ci.canonical_deliverable_path(fresh._publication_task_id(publication), "deliverable_files/" + foreign + "/report.txt")
    publication = successor._publication_binding()
    assert fresh._publication_task_id(publication) == registration.TASK5

    class ForeignPublication(fresh._PublicationBinding):
        pass

    for malformed in (None, True, {}, ForeignPublication(**vars(publication)), *(
            replace(publication, cell_id=cell) for cell in (
                None, True, 5, b"unknown", "unknown", successor.CELL_ID + "\n",
                controller.FIRST_CELL_ID, successor.CELL_ID + "_unsupported"))):
        with pytest.raises(ci.RetentionCIRefused, match="^fixed_retention_publication_binding_required$"):
            fresh._verify_publication(None, None, TERMINAL_HEAD, {}, {},
                tmp_path / "never-unsupported-publication", None, 0, malformed)
    assert not (tmp_path / "never-cross-task").exists()
    assert not (tmp_path / "never-unsupported-publication").exists()

    seed = prior.prior.FailedPredecessorHF(production_plan, binding=reader.TASK5_KEEP_R2, successor_adapter=successor)
    synthetic_pins = seed.synthetic_identities()  # Authored bytes, before any validator read.
    monkeypatch.setattr(successor, "PREDECESSOR", synthetic_pins)
    with tempfile.TemporaryDirectory(prefix=".retention-task5-fresh-r2-offline-", dir=REAL_ROOT.parent) as directory:
        host_parent = Path(directory)
        case = host_parent / "scenario"
        case.mkdir()
        plan, root, archive, sources = shared._scenario(case, monkeypatch, approved_pilot_source)
        scenario_roles = (shared.successor.FACADE, fresh.FACADE,
            "batch-runner/codex_retention_fresh_r1_result_intake.py")
        additional_roles = (successor.FACADE, previous.FACADE, previous.previous.FACADE,
                            previous.previous.previous.FACADE, previous.previous.previous.previous.FACADE)
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
        packet = preparation.prepare_packet(cell_id=request.cell_id, sources=sources, output=request.packet,
            expected_preparer_sha256=request.expected_preparer_sha256, plan=plan)
        stage = controller.stage_runtime(request)
        assert stage["ordinal"] == 7 and stage["cell_id"] == successor.CELL_ID and stage["commands"] == []
        assert not any(stage[key] for key in ("launch_authorized", "inference_slot_reserved", "deadline_started"))
        assert stage["config_sha256"] == plan["cells"][7]["config_sha256"]
        assert (request.packet / preparation.INFERENCE).read_bytes() == controller._encoded(plan["cells"][7]["config"])
        assert stage["input_roles_sha256"] == packet["input_verification"]["original_input_roles_sha256"]
        assert controller.read_codex_prepared(controller.PREPARED)["execution"]["codex"]["task_deadline"] == {
            "condition": "retention_bundle_v1", "retention_bundle": "fresh", "repetition": 2}
        assert controller._stage_paths(successor.CELL_ID) == tuple(root / "batch-runner/workspace" / name for name in (
            "retention-task5-fresh-r2-staging.json", "retention-task5-fresh-r2-staged.json"))
        with pytest.raises(controller.RetentionControllerRefused, match="^runtime_path_already_used_or_partial$"):
            controller.stage_runtime(request)
        document, observation = successor.canonical_request(request,
            reviewed_source_sha=SOURCE, run_id="700000001", historical_root=archive)
        assert document["scope"] == successor.SCOPE and document["serial_domain"]["predecessor"] == synthetic_pins
        assert document["format"] == successor.REQUEST_FORMAT and document["provider"]["attempt"] == 1
        assert document["host"]["sdk"] == document["host"]["cli"] == "0.147.0"
        assert set(document["source"]["successor_adapter"]["files"]) == set(successor.SOURCE_PATHS)
        adapters = (*old_adapters, successor)
        for cell, scope in ((None, ci.SCOPE), *((adapter.CELL_ID, adapter.SCOPE) for adapter in adapters)):
            argv = ["--reviewed-source-sha", SOURCE] + ([] if cell is None else ["--cell", cell])
            assert successor.main(argv) == 0
            result = json.loads(capsys.readouterr().out)
            assert result["mode"] == "plan_only" and result["scope"] == scope and result["commands"] == []
        with monkeypatch.context() as before_source:
            before_source.setattr(ci, "require_source", forbidden)
            for adapter, reason in ((ci, "only_registered_ordinal_zero_supported"),
                    (fresh, "only_first_or_task4_fresh_r1_supported"),
                    (previous.previous.previous.previous.previous, "only_registered_task4_fresh_r2_supported"),
                    (previous.previous.previous.previous, "only_registered_task4_keep_r2_supported"),
                    (previous.previous.previous, "only_registered_task5_fresh_r1_supported"),
                    (previous.previous, "only_registered_task5_keep_r1_supported"),
                    (previous, "only_registered_task5_keep_r2_supported")):
                assert adapter.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE]) == 2
                assert json.loads(capsys.readouterr().out)["reason"] == reason
            assert successor.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE, "--observe-locator"]) == 2
            assert json.loads(capsys.readouterr().out)["reason"] == "task5_fresh_r2_locator_observation_not_supported"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        api = deepcopy(seed)
        child = FreshTransport(document, api, key)
        child.recovery_request = request
        grant = ci.ExecutionGrantRequest(SOURCE, owned._digest(document), archive)
        denied = host_parent / "not-admitted"
        for wrong in ("unregistered", True, 7, successor.CELL_ID + "_unsupported"):
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
                 (previous.previous.previous.previous.previous._FreshR2Admission, previous.previous.previous.previous.previous.CELL_ID),
                 (previous.previous.previous.previous._KeepR2Admission, previous.previous.previous.previous.CELL_ID),
                 (previous.previous.previous._Task5FreshR1Admission, previous.previous.previous.CELL_ID),
                 (previous.previous._Task5KeepR1Admission, previous.previous.CELL_ID),
                 (previous._Task5KeepR2Admission, previous.CELL_ID), (successor._Task5FreshR2Admission, successor.CELL_ID))
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
            class Noncanonical(successor._Task5FreshR2Admission):
                pass
            with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
                controller._run_post_authority_cell(request, host_state=denied,
                    _admission=Noncanonical(request, document, observation, {}, child, api))
        assert not denied.exists() and api.calls == [] and child.children == [] and child.github_calls == 0
        bad_approval = FreshTransport(document, deepcopy(seed), key)
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
                print(json.dumps({"diagnostic": "task5_fresh_original_exception", "chain": chain,
                    "state_counts": {"commit_attempts": len(server.commits),
                        "committed_terminal_controls": sum(server.writers[head].get(successor.TERMINAL) == head
                                                           for head in server.parents),
                        "owned_children": len(diagnostic["child"].children)}}, sort_keys=True))
            return classification

        monkeypatch.setattr(output, "_error_context", observe_error)
        cases = {"grade_parent": "task5_fresh_r2_predecessor_head_mismatch",
            "task4_parent": "task5_fresh_r2_predecessor_head_mismatch",
            "keep_r1_parent": "task5_fresh_r2_predecessor_head_mismatch",
            "terminal_hash": "task5_fresh_r2_predecessor_identity_mismatch",
            "claim_hash": "task5_fresh_r2_predecessor_identity_mismatch",
            "manifest_hash": "task5_fresh_r2_predecessor_identity_mismatch",
            "objects_hash": "task5_fresh_r2_predecessor_identity_mismatch",
            "source": "fresh_result_completion_mismatch", "run": "fresh_result_authority_binding_mismatch",
            "job": "fresh_terminal_execution_job_mismatch", "bool_job": "fresh_result_authority_binding_mismatch",
            "request": "fresh_result_terminal_binding_mismatch", "cell": "fresh_result_completion_mismatch",
            "predecessor": "fresh_result_predecessor_mismatch", "status": "fresh_terminal_unsuccessful_required",
            "stopped": "task5_fresh_r2_predecessor_identity_mismatch",
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
            if fault in ("grade_parent", "task4_parent", "keep_r1_parent"):
                server.head = ("76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e" if fault == "grade_parent"
                               else "e55fac5d60191167dd66688510ec0fef472e594d" if fault == "task4_parent"
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
            transport = FreshTransport(document, server, key)
            diagnostic.update(api=server, child=transport)
            authority = ci.verify_approval(document, transport)
            admission = successor._Task5FreshR2Admission(request, document, observation, authority, transport, server)
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
        with capsys.disabled():
            print("BOUNDARY ordinal7: exact authority, predecessor/control/history, CAS and uncertain-claim refusals passed")
        snapshot = host_parent / "staged-snapshot"
        shutil.copytree(root, snapshot)
        host = host_parent / "completed"
        diagnostic.update(api=api, child=child)
        result = controller.execute_first_cell(request,
            host_state=host, grant=grant, _test_transport=child, _test_api=api)
        assert result == {"cell_id": successor.CELL_ID, "status": "succeeded", "request_sha256": grant.request_sha256,
            "cleanup_confirmed": True, "remote_terminal": "acknowledged", "grade": None,
            "grading_launched": False, "invoice_complete": False}
        assert child.fresh_record["retention_bundle"] == "fresh" and child.fresh_record["repetition"] == 2
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
        with capsys.disabled():
            print("BOUNDARY ordinal7: FRESH eligibility/owned reset/settled receipts/cumulative clock, execute-return and terminal acknowledgment passed")
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
                transport = FreshTransport(current, server, key, mode=fault if fault in ("cleanup", "timeout") else "ordinary")
                diagnostic.update(api=server, child=transport)
                private = host_parent / fault
                if fault == "timeout":
                    stopped = successor.execute(selected,
                        host_state=private, grant=grant, _test_transport=transport, _test_api=server)
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
                        assert retained._read(private / "remote-admission-receipt.json")["reason"] == "task5_fresh_r2_predecessor_head_mismatch"
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
    print("OFFLINE ordinal7: exact failed TASK5_KEEP_R2 controls-only parent; canonical Task4/Task5 paths; authority/CAS, own FRESH reset, settled receipts/cumulative clock, acknowledgment/reconciliation/lost-ack/no-replay/timeout/cleanup passed; no live effects")
