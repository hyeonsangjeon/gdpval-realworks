"""Ordinal-four proof with real validators and synthetic controls/owned child.

No original payload, provider, SDK, model, grader or live HF operation is used.
Authored synthetic byte identities are distinct from asserted production pins.
"""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import codex_retention_task5_fresh_r1 as successor
from core.codex_cost import CodexTokenTotals, settle_codex_turn, turn_usage_delta
from core.codex_runner import CodexWorkspace
from core.codex_task_deadline import TaskDeadlineRefused
from core.cost_receipts import CostReceiptLedger
from . import test_codex_retention_task4_keep_r2 as prior
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN, offline  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_fresh_r1_terminal_observation import TerminalHF
from .test_codex_retention_result_intake import TERMINAL_HEAD

previous, fresh, reader, ci = successor.previous, successor.fresh, successor.reader, successor.ci
controller, preparation, registration = successor.controller, successor.preparation, successor.registration
owned, retained, output = successor.owned, successor.retained, successor.output
base, REAL_ROOT, SOURCE = prior.base, prior.REAL_ROOT, prior.SOURCE
positive, _write = prior.positive, prior._write


class SuccessfulPredecessorHF(prior.prior.SuccessorHF):
    def __init__(self, plan):
        MemoryHF.__init__(self)
        producer = FreshResultHF(plan, binding=reader.KEEP_R2)
        self.producer_paths = (previous.CLAIM, previous.TERMINAL, previous.OUTPUT)
        self.successor_paths = (successor.CLAIM, successor.TERMINAL, successor.OUTPUT)
        self.preceding_terminal = previous.PREDECESSOR["terminal_commit"]
        self.claim, self.summary, self.terminal, self.files = (
            deepcopy(getattr(producer, name)) for name in ("claim", "summary", "terminal", "files"))
        self.pins = deepcopy(successor.PREDECESSOR)
        self.terminal.update(claim_commit=self.pins["claim_commit"], output_commit=self.pins["output_commit"])
        self.downloads = []
        self.seed()


def _runtime(monkeypatch, root):
    prior._runtime(monkeypatch, root)
    monkeypatch.setattr(successor, "ROOT", root)


class Task5Transport(prior.prior.R2Transport):
    ordinal, repetition, cell_id, bundle = 4, 1, successor.CELL_ID, "fresh"
    recovery_request = None
    fresh_record = None

    def owned_process(self, command, **options):
        if self.recovery_request is not None:
            self._fresh_recovery(options["ownership"][0].parent)
        return super().owned_process(command, **options)

    def _fresh_recovery(self, host):
        """Use the existing durable fresh reset operations, without a native call."""
        request = self.recovery_request
        context, stage = controller._context(request), controller.verify_staged_runtime(request)
        predecessor = CodexWorkspace.create(task_id="synthetic-prior-keep-cell")
        _write(predecessor.workspace / "prior-only.txt", b"never import")
        workspace = CodexWorkspace.create(task_id=registration.TASK5)
        assert workspace.root != predecessor.root and list(workspace.workspace.iterdir()) == []
        outputs = controller.ROOT / "batch-runner/workspace/upload/deliverable_files" / registration.TASK5
        outputs.mkdir(parents=True)
        neighbor = host / "synthetic-prior-output" / "prior-only.txt"
        _write(neighbor, b"unrelated output")
        identity = owned._digest({"cell_id": successor.CELL_ID, "request_sha256": owned._digest(self.document)})
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
            # An ambiguous start is not authority to discard state and try again.
            with pytest.raises(TaskDeadlineRefused,
                    match="^native thread creation was interrupted before its identifier was bound$"):
                task.require_fresh_retirement(task.continuation(identity))
            assert task.retired_continuations(identity) == []
            assert all((folder / "fresh-only.txt").read_bytes() == b"discard only this owned bundle"
                       for folder in owned_folders)
            task.bind_thread("synthetic-task5-first-thread", resumed=False)
            bound = task.continuation(identity)
            assert bound["phase"] == "bound" and bound["thread_id"] == "synthetic-task5-first-thread"
            for retirement in (task.require_fresh_retirement, task.retire_fresh_bundle):
                with pytest.raises(TaskDeadlineRefused, match="^fresh bundle lacks a reconciled eligible recovery$"):
                    retirement(bound)
            assert task.continuation(identity) == bound and task.retired_continuations(identity) == []
            assert all((folder / "fresh-only.txt").read_bytes() == b"discard only this owned bundle"
                       for folder in owned_folders)
            assert task.recovery_context(0) is None  # Mechanical B, no C feedback.
            receipt_path = host / "synthetic-fresh-recovery.sqlite"
            with CostReceiptLedger(receipt_path, run_id="synthetic-task5-fresh-recovery") as ledger:
                call_id = ledger.reserve(call_id="synthetic-turn-0", task_id=registration.TASK5,
                    stage="generation", retry_kind="none", provider="synthetic", requested_model="synthetic",
                    request_sha256=owned._digest(self.document))
                before = task.begin_turn(0, call_id, input_sha256=owned._digest(self.document), recovery_context=None)
                after = dict.fromkeys(before)  # The synthetic failed turn reports no usage.
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
        self.clock.now += 45  # Synthetic downtime; never sleep or restart the clock.
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
            with CostReceiptLedger(receipt_path, run_id="synthetic-task5-fresh-recovery") as ledger:
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
            task.bind_thread("synthetic-task5-second-thread", resumed=False)
            assert task.recovery_context(1) is None
            with CostReceiptLedger(receipt_path, run_id="synthetic-task5-fresh-recovery") as ledger:
                call_id = ledger.reserve(call_id="synthetic-turn-1", task_id=registration.TASK5,
                    stage="generation", retry_kind="infrastructure", provider="synthetic", requested_model="synthetic",
                    request_sha256=owned._digest(self.document))
                before = task.begin_turn(1, call_id, input_sha256=owned._digest(self.document), recovery_context=None)
                after = dict.fromkeys(before)
                task.observe_turn(1, after, terminal_reason="completed")
                settle_codex_turn(ledger, call_id,
                    totals=turn_usage_delta(CodexTokenTotals(**before), CodexTokenTotals(**after)))
                task.acknowledge_usage(1)
                assert [row["state"] for row in ledger.calls_for(registration.TASK5)] == ["settled", "settled"]
            self.fresh_record = task.as_record()
            assert self.fresh_record["started_unix"] == original["started_unix"]
            assert self.fresh_record["expires_unix"] == original["expires_unix"]
            assert self.fresh_record["remaining_seconds"] == 10725 and self.fresh_record["wait_seconds"] == 30
            assert self.fresh_record["attempts_admitted"] == 2 and self.fresh_record["native_resumes"] == 0
            assert self.fresh_record["retired_attempts"] == 1 and self.fresh_record["session_policy"] == "fresh_owned_bundle"
            assert self.fresh_record["total_seconds"] == 10800 and self.fresh_record["attempt_seconds"] == 1800
        finally:
            store.close()


def test_task5_fresh_r1_is_the_closed_fifth_cell(tmp_path, monkeypatch, capsys, approved_pilot_source):
    production_plan = registration.compile_plan()
    pins = deepcopy(successor.PREDECESSOR)
    assert successor.CELL_ID == "0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_fresh_r1"
    assert [(item.cell_id, item.ordinal, item.bundle, item.repetition) for item in controller.CELL_BINDINGS] == [
        (production_plan["order"][0], 0, "keep", 1), (production_plan["order"][1], 1, "fresh", 1),
        (production_plan["order"][2], 2, "fresh", 2), (production_plan["order"][3], 3, "keep", 2),
        (production_plan["order"][4], 4, "fresh", 1)]
    assert pins == {"cell_id": previous.CELL_ID,
        "producer_source_sha": "b8351e561acb9675a4993419e819c12787b5b305", "run_id": "36947454688",
        "execution_job_id": 110660390316,
        "request_sha256": "8a06cc7df34cbf10896b635f6c8d9ad4e91313d3c685511f8fc5c159cb6ddec1",
        "terminal_commit": "e55fac5d60191167dd66688510ec0fef472e594d",
        "terminal_identity": {"sha256": "70fb8778ae15e369ef1ac4d03dbe4fa6f5d9852966b250fa812695d6bd77bf91", "size": 5885},
        "claim_commit": "f29f8d4a19710aa0e832dba720ff7d32701c309c",
        "claim_identity": {"sha256": "4af63e82ddcaf2b795595081c59d29369e2bf2a4bb2c37f81eb7f5409cd6b363", "size": 1888},
        "output_commit": "54a4362ce3554b7c71b5ada00802efc9521038e6",
        "output_manifest_identity": {"sha256": "93e1dada24779909cfc593dff7507b7f9c6452c6f36c12b2c5e86305e35d9a8c", "size": 2679},
        "output_objects_sha256": "4bda1c0d48a5dd980bd683a6f8316b3d52808e95dca68099b86ad4de2d3e03b2",
        "status": "succeeded", "exit_code": 0, "cleanup_confirmed": True}
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        pytest.fail("ordinal-four proof crossed a live, payload, grading or early-admission boundary")

    for name in ("core.executor.TaskExecutor.__init__", "step8_grade.main", "step8_grade.RubricLoader.load",
                 "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset"):
        monkeypatch.setattr(name, forbidden)
    # Small old-reader compatibility checks: current bytes, old exact defaults
    # and predecessors; control bodies only, no delivered result-suite replay.
    source = reader.reader_identity(binding=reader.KEEP_R2)
    assert reader.FRESH_R1.expectation is reader.EXPECTATION
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    for binding in (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2):
        kwargs = {} if binding is reader.FRESH_R1 else {"binding": binding}
        checked_source, _, cell = reader._binding(binding.expectation, source["module_sha256"], TERMINAL_HEAD, False, **kwargs)
        assert checked_source["controller_sha256"] == reader.FROZEN["controller_sha256"][1]
        assert cell["index"] == binding.ordinal and cell["control"]["retention_bundle"] == binding.retention_bundle
        transport = (FreshResultHF(production_plan, binding=binding) if binding is reader.KEEP_R2
                     else TerminalHF(production_plan, exit_code=1, binding=binding))
        with retained._session(transport) as (api, token, deadline):
            terminal, _, _, _ = reader._verify_terminal(api, api.repo, TERMINAL_HEAD,
                ci._cache(tmp_path, "old-control-" + str(binding.ordinal)), token, deadline,
                terminal_only=binding is not reader.KEEP_R2, **kwargs)
        assert terminal["completion"]["cell_id"] == binding.expectation.cell_id and transport.commits == []
        with monkeypatch.context() as bad_bytes:
            bad_bytes.setattr(retained, "_session", forbidden)
            for digest in ("0" * 64, "5f4f6c8ae9e361760e9a76d12c95edd3237aac2714ab8767c640e80e78e24583"):
                with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_reader_bytes_mismatch$"):
                    reader.read_result(expectation=binding.expectation, binding=binding,
                        destination=tmp_path / "never-created", expected_reader_sha256=digest,
                        terminal_revision=TERMINAL_HEAD)
    assert not (tmp_path / "never-created").exists()
    for binding in (replace(reader.KEEP_R2), None, True):
        with pytest.raises(output.OutputPublicationRefused, match="^fixed_fresh_read_binding_required$"):
            reader._fixed_binding(binding)

    seed = SuccessfulPredecessorHF(production_plan)
    synthetic_pins = seed.synthetic_identities()  # Authored independently before any validator read.
    monkeypatch.setattr(successor, "PREDECESSOR", synthetic_pins)
    # Outside /tmp and outside the agent-owned temp/native roots, as the real
    # fresh-output ownership validator requires. Only this test owns these files.
    with tempfile.TemporaryDirectory(prefix=".retention-task5-offline-", dir=REAL_ROOT.parent) as directory:
        host_parent = Path(directory)
        case = host_parent / "scenario"
        case.mkdir()
        plan, root, archive, sources = prior.prior._scenario(case, monkeypatch, approved_pilot_source)
        for facade in (previous.FACADE, successor.FACADE):
            _write(root / facade, (REAL_ROOT / facade).read_bytes())
        _runtime(monkeypatch, root)
        base._environment(monkeypatch, host_parent)
        request = controller.Request(successor.CELL_ID, sources, root / successor.PACKET_ROLE, root,
            preparation.source_identity()["sha256"], controller.source_identity()["sha256"])
        packet = positive("task5_packet", lambda: preparation.prepare_packet(cell_id=request.cell_id,
            sources=sources, output=request.packet, expected_preparer_sha256=request.expected_preparer_sha256, plan=plan))
        stage = positive("task5_staging", lambda: controller.stage_runtime(request))
        assert stage["ordinal"] == 4 and stage["cell_id"] == successor.CELL_ID and stage["commands"] == []
        assert not any(stage[key] for key in ("launch_authorized", "inference_slot_reserved", "deadline_started"))
        assert stage["config_sha256"] == plan["cells"][4]["config_sha256"]
        assert (request.packet / preparation.INFERENCE).read_bytes() == controller._encoded(plan["cells"][4]["config"])
        assert stage["input_roles_sha256"] == packet["input_verification"]["original_input_roles_sha256"]
        assert controller.read_codex_prepared(controller.PREPARED)["execution"]["codex"]["task_deadline"] == {
            "condition": "retention_bundle_v1", "retention_bundle": "fresh", "repetition": 1}
        assert controller._stage_paths(successor.CELL_ID) == tuple(root / "batch-runner/workspace" / name for name in (
            "retention-task5-fresh-r1-staging.json", "retention-task5-fresh-r1-staged.json"))
        with pytest.raises(controller.RetentionControllerRefused, match="^runtime_path_already_used_or_partial$"):
            controller.stage_runtime(request)
        document, observation = positive("task5_request", lambda: successor.canonical_request(request,
            reviewed_source_sha=SOURCE, run_id="700000001", historical_root=archive))
        assert document["scope"] == successor.SCOPE and document["serial_domain"]["predecessor"] == synthetic_pins
        assert document["format"] == successor.REQUEST_FORMAT and document["provider"]["attempt"] == 1
        assert set(document["source"]["successor_adapter"]["files"]) == set(successor.SOURCE_PATHS)
        assert document["host"]["sdk"] == document["host"]["cli"] == "0.147.0"
        for cell, scope in ((None, ci.SCOPE), (fresh.CELL_ID, fresh.SCOPE),
                            (previous.previous.CELL_ID, previous.previous.SCOPE), (previous.CELL_ID, previous.SCOPE),
                            (successor.CELL_ID, successor.SCOPE)):
            argv = ["--reviewed-source-sha", SOURCE] + ([] if cell is None else ["--cell", cell])
            assert successor.main(argv) == 0
            result = json.loads(capsys.readouterr().out)
            assert result["mode"] == "plan_only" and result["scope"] == scope and result["commands"] == []
        with monkeypatch.context() as before_source:
            before_source.setattr(ci, "require_source", forbidden)
            for adapter, reason in ((fresh, "only_first_or_task4_fresh_r1_supported"),
                    (previous.previous, "only_registered_task4_fresh_r2_supported"),
                    (previous, "only_registered_task4_keep_r2_supported")):
                assert adapter.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE]) == 2
                assert json.loads(capsys.readouterr().out)["reason"] == reason
            assert successor.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE, "--observe-locator"]) == 2
            assert json.loads(capsys.readouterr().out)["reason"] == "task5_fresh_r1_locator_observation_not_supported"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        api = deepcopy(seed)
        child = Task5Transport(document, api, key)
        child.recovery_request = request
        grant = ci.ExecutionGrantRequest(SOURCE, owned._digest(document), archive)
        denied = host_parent / "not-admitted"
        for wrong in ("unregistered", True, 4, *plan["order"][5:]):
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
                 (previous.previous._FreshR2Admission, previous.previous.CELL_ID),
                 (previous._KeepR2Admission, previous.CELL_ID), (successor._Task5FreshR1Admission, successor.CELL_ID))
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
            class Noncanonical(successor._Task5FreshR1Admission):
                pass
            with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
                controller._run_post_authority_cell(request, host_state=denied,
                    _admission=Noncanonical(request, document, observation, {}, child, api))
        assert not denied.exists() and api.calls == [] and child.children == [] and child.github_calls == 0
        bad_approval = Task5Transport(document, deepcopy(seed), key)
        bad_approval.provider[2][0]["comment"] = ci.APPROVAL_PREFIX + "0" * 64
        with pytest.raises(ci.RetentionCIRefused, match="^owner_environment_request_approval_mismatch$"):
            successor.execute(request, host_state=denied, grant=grant, _test_transport=bad_approval, _test_api=bad_approval.api)
        assert not denied.exists() and bad_approval.api.calls == []

        cases = {"grade_parent": "task5_fresh_r1_predecessor_head_mismatch",
            "terminal_hash": "task5_fresh_r1_predecessor_identity_mismatch",
            "claim_hash": "task5_fresh_r1_predecessor_identity_mismatch",
            "manifest_hash": "task5_fresh_r1_predecessor_identity_mismatch",
            "objects_hash": "task5_fresh_r1_predecessor_identity_mismatch",
            "source": "fresh_result_completion_mismatch", "run": "fresh_result_authority_binding_mismatch",
            "job": "fresh_result_execution_job_mismatch", "bool_job": "fresh_result_authority_binding_mismatch",
            "request": "fresh_result_terminal_binding_mismatch", "cell": "fresh_result_completion_mismatch",
            "predecessor": "fresh_result_predecessor_mismatch", "status": "fresh_result_success_required",
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
            elif fault == "status":
                server.summary["status"] = "failed"
            elif fault == "cleanup":
                server.summary["cleanup_confirmed"] = False
            server.seed()
            if fault == "grade_parent":
                server.head = "76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e"
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
            transport = Task5Transport(document, server, key)
            authority = ci.verify_approval(document, transport)
            admission = successor._Task5FreshR1Admission(request, document, observation, authority, transport, server)
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
                admission.admit(private)  # An uncertain reservation cannot turn into a new attempt.

        snapshot = host_parent / "staged-snapshot"
        shutil.copytree(root, snapshot)
        host = host_parent / "completed"
        result = positive("task5_claim_fresh_recovery_child_output_terminal", lambda: controller.execute_first_cell(request,
            host_state=host, grant=grant, _test_transport=child, _test_api=api))
        assert result == {"cell_id": successor.CELL_ID, "status": "succeeded", "request_sha256": grant.request_sha256,
            "cleanup_confirmed": True, "remote_terminal": "acknowledged", "grade": None,
            "grading_launched": False, "invoice_complete": False}
        assert child.fresh_record["retention_bundle"] == "fresh" and child.fresh_record["repetition"] == 1
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
            reconciled = successor.verify_terminal(server, server.repo, server.head, terminal, claim,
                ci._cache(host, "reconcile"), token, deadline)
        assert reconciled["writer_acknowledgment"] == "not_established" and reconciled["replay_authorized"] is False
        assert (host / "remote-terminal-receipt.json").read_bytes() == held
        with pytest.raises(controller.RetentionControllerRefused, match="^first_cell_already_reserved_or_partial_no_replay$"):
            successor.execute(request, host_state=host, grant=grant, _test_transport=child, _test_api=api)
        assert len(child.children) == 1 and api.commits == ["admission", "output", "terminal"]
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
                transport = Task5Transport(current, server, key, mode=fault if fault in ("cleanup", "timeout") else "ordinary")
                private = host_parent / fault
                if fault == "timeout":
                    stopped = positive("task5_timeout_cleanup_publication", lambda: successor.execute(selected,
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
                        assert retained._read(private / "remote-admission-receipt.json")["reason"] == "task5_fresh_r1_predecessor_head_mismatch"
                        assert transport.children == [] and not (private / "deadline").exists()
                    else:
                        receipt = retained._read(private / "remote-terminal-receipt.json")
                        assert receipt["outcome"] == "unresolved" and receipt["reason"] == "hf_transport_failed"
                        held = (private / "remote-terminal-receipt.json").read_bytes()
                        expected_terminal = retained._read(private / "remote-terminal-expected.json")
                        expected_claim = retained._read(private / "remote-admission-receipt.json")["claim"]
                        with retained._session(server) as (memory, token, deadline):
                            view = successor.verify_terminal(memory, memory.repo, memory.head, expected_terminal,
                                expected_claim, ci._cache(private, "lost-ack-observation"), token, deadline)
                        assert view["writer_acknowledgment"] == "not_established" and view["observation_only"] is True
                        assert (private / "remote-terminal-receipt.json").read_bytes() == held
                assert len(transport.children) == (0 if fault == "remote_no_replay" else 1)
                assert server.commits == (["admission"] if fault == "cleanup" else ["admission", "output", "terminal"])
        assert effects == [] and base.PRIVATE.decode() not in capsys.readouterr().out
    print("OFFLINE ordinal4: fixed successful KEEP_R2 control-only predecessor, exact authority/CAS, fresh owned reset, unchanged cumulative clock, owned cleanup/publication/no-replay; no live effects")
