"""One ordinal-three proof: real predicates, synthetic controls and owned child."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import codex_retention_task4_keep_r2 as successor
import gpt54_comparison_preflight as comparison
from core.codex_runner import CodexWorkspace
from core.codex_task_deadline import TaskDeadlineRefused
from . import test_codex_retention_task4_fresh_r2 as prior
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN, offline  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_fresh_r1_terminal_observation import TerminalHF
from .test_codex_retention_result_intake import TERMINAL_HEAD

previous, fresh, reader, ci = successor.previous, successor.fresh, successor.reader, successor.ci
controller, preparation, registration = successor.controller, successor.preparation, successor.registration
owned, retained, output = successor.owned, successor.retained, successor.output
base, REAL_ROOT, SOURCE = prior.base, prior.REAL_ROOT, prior.SOURCE
positive, _write = prior.positive, prior._write


def _source_tree(root):
    prior._source_tree(root)
    _write(root / successor.FACADE, (REAL_ROOT / successor.FACADE).read_bytes())


def _runtime(monkeypatch, root):
    prior._runtime(monkeypatch, root)
    monkeypatch.setattr(successor, "ROOT", root)


class KeepTransport(prior.R2Transport):
    ordinal, repetition, cell_id, bundle = 3, 2, successor.CELL_ID, "keep"
    recovery_request = None
    keep_record = None

    def owned_process(self, command, **options):
        result = super().owned_process(command, **options)
        if self.recovery_request is not None:
            self._keep_recovery(options["ownership"][0].parent)
        return result

    def _keep_recovery(self, host):
        """Durable native metadata/workspace recovery, never an SDK/model call."""
        request = self.recovery_request
        context, stage = controller._context(request), controller.verify_staged_runtime(request)
        old = CodexWorkspace.create(task_id="synthetic-preceding-fresh-cell")
        _write(old.workspace / "previous-cell-only.txt", b"NEVER ADOPT")
        workspace = CodexWorkspace.create(task_id=registration.TASK4)
        assert workspace.root != old.root and list(workspace.workspace.iterdir()) == []
        layout = workspace.continuation_binding()
        markers = {directory / "keep-marker.txt": ("synthetic-" + role).encode()
                   for role, directory in (("workspace", workspace.workspace), ("HOME", workspace.home),
                                           ("CODEX_HOME", workspace.codex_home))}
        for path, data in markers.items():
            _write(path, data)
        deliverable = controller.ROOT / "batch-runner/workspace/upload/deliverable_files" / registration.TASK4 / "report.txt"
        markers[deliverable] = deliverable.read_bytes()  # Already produced by the synthetic owned child.
        identity = owned._digest({"cell_id": successor.CELL_ID, "request_sha256": owned._digest(self.document)})
        store = controller._deadline(host, context, stage, self)
        try:
            task = store.for_task(registration.TASK4)
            assert task.retains_thread and not task.fresh_bundle and store.control.max_attempts is None
            assert task.continuation() is None and task.remaining_seconds() == 10800
            original = task.as_record()
            assert task.admit_attempt(workspace.root) == 0
            task.bind_workspace(identity, owned._digest(self.document), layout)
            task.thread_starting()
            task.bind_thread("synthetic-keep-r2-thread", resumed=False)
            assert task.recovery_context(0) is None
            task.begin_turn(0, "synthetic-turn-0", input_sha256=owned._digest(self.document), recovery_context=None)
            task.observe_turn_start_failure(0)

            def advance(seconds):
                self.clock.now += seconds  # Synthetic wait; no sleeping.

            task.wait(30, advance)
        finally:
            store.close()
        self.clock.now += 45  # Synthetic process downtime is charged to the same expiry.
        store = controller._deadline(host, context, stage, self)
        try:
            task = store.for_task(registration.TASK4)
            task.require_resumable()
            bound = task.continuation(identity)
            restored = CodexWorkspace.restore(bound["workspace"])
            assert restored.continuation_binding() == layout and restored.root == workspace.root
            assert bound["thread_id"] == "synthetic-keep-r2-thread"
            assert all(path.read_bytes() == data for path, data in markers.items())
            assert not (restored.workspace / "previous-cell-only.txt").exists()
            with pytest.raises(TaskDeadlineRefused, match="^native continuation request/runtime identity mismatch$"):
                task.continuation(owned._digest({"cell_id": previous.CELL_ID}))
            with pytest.raises(TaskDeadlineRefused, match="^native continuation cannot replace an admitted workspace$"):
                task.bind_workspace(identity, owned._digest(self.document), old.continuation_binding())
            with pytest.raises(TaskDeadlineRefused, match="^native resume returned a different thread identifier$"):
                task.bind_thread("synthetic-previous-cell-thread", resumed=True)
            assert task.admit_attempt(restored.root) == 1 and task.bound_timeout(1800) == 1800
            task.bind_thread(bound["thread_id"], resumed=True)
            assert task.recovery_context(1) is None  # Mechanical B, no C feedback.
            task.begin_turn(1, "synthetic-turn-1", input_sha256=owned._digest(self.document), recovery_context=None)
            task.observe_turn(1, dict.fromkeys(bound["usage_boundary"]), terminal_reason="completed")
            task.acknowledge_usage(1)
            self.keep_record = task.as_record()
            assert self.keep_record["started_unix"] == original["started_unix"]
            assert self.keep_record["expires_unix"] == original["expires_unix"]
            assert self.keep_record["remaining_seconds"] == 10725 and self.keep_record["wait_seconds"] == 30
            assert self.keep_record["attempts_admitted"] == 2 and self.keep_record["native_resumes"] == 1
            assert self.keep_record["session_policy"] == "retained_native_thread"
            assert self.keep_record["total_seconds"] == 10800 and self.keep_record["attempt_seconds"] == 1800
            assert all(path.read_bytes() == data for path, data in markers.items())
        finally:
            store.close()


def test_task4_keep_r2_advances_failed_fresh_r2_without_cross_cell_state(
        tmp_path, monkeypatch, capsys, approved_pilot_source):
    production_plan = registration.compile_plan()
    pins = deepcopy(successor.PREDECESSOR)
    assert pins == {
        "cell_id": "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_fresh_r2",
        "producer_source_sha": "5a9614ac04464c4e0a5e80297f54c3a5c9443bae",
        "run_id": "36907894862", "execution_job_id": 110535767415,
        "request_sha256": "4798c119ea2d06c7c902ae51638bdba25c5bfaf683a2223d286fd7e652d3b317",
        "terminal_commit": "1d5133590911f3704fc2a65279d4b64bee77c1d6",
        "terminal_identity": {"sha256": "c1ab656b3ee0556aa5934dc976dfa6086ac59f4f3e2abf936a600a9fcb7fda2b", "size": 4200},
        "claim_commit": "98724c1fc83af2b45f65533648162692ba8d12b0",
        "claim_identity": {"sha256": "d2718f7635870efbb3edefaf7d38ed20691fed40c1c39389b93e53947a6ceeb4", "size": 1889},
        "output_commit": "46fff9e31bc844a55ced352926aba49479869624",
        "output_manifest_identity": {"sha256": "f44c09d86d48d59579ff6ae3355633740b5d2888c7b38e33cd6c132bb45cf882", "size": 2119},
        "output_objects_sha256": "029c0b29cd7e3b593fb28ec0dfe4a6c3d6999b8867f980496cde1da335d18c3a",
        "status": "failed", "exit_code": 1, "cleanup_confirmed": True,
    }
    assert [(item.cell_id, item.ordinal, item.bundle, item.repetition) for item in controller.CELL_BINDINGS] == [
        (production_plan["order"][0], 0, "keep", 1), (production_plan["order"][1], 1, "fresh", 1),
        (production_plan["order"][2], 2, "fresh", 2), (production_plan["order"][3], 3, "keep", 2),
        (production_plan["order"][4], 4, "fresh", 1), (production_plan["order"][5], 5, "keep", 1)]
    assert reader.intake.reader_identity() == {
        "module_sha256": "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196",
        "terminal_verifier_sha256": "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c"}
    source = reader.reader_identity(binding=reader.FRESH_R2)
    assert source["producer_r2_sha256"] == "8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f"
    assert {key: source[key] for key in reader.FROZEN} == {key: pair[1] for key, pair in reader.FROZEN.items()}
    assert reader.FRESH_R1.expectation is reader.EXPECTATION
    assert (reader.RUN_ID, reader.EXPECTED_EXECUTION_JOB_ID) == ("36845127347", 110323708382)
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("ordinal-three proof crossed a forbidden boundary")

    for name in ("core.executor.TaskExecutor.__init__", "step8_grade.main", "step8_grade.RubricLoader.load",
                 "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset"):
        monkeypatch.setattr(name, forbidden)
    # Current helper migration is exact and refuses stale/wrong bytes before
    # transport/credentials or destination creation; no permissive pin list.
    with monkeypatch.context() as no_credentials:
        no_credentials.setattr(retained, "_session", forbidden)
        for binding in (reader.FRESH_R1, reader.FRESH_R2):
            for wrong_hash in ("0" * 64, "5bfba1a2cb4d4f5190b0d146fd7b2b890c72ecf3904974d37babfea9ed8661f0"):
                with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_reader_bytes_mismatch$"):
                    reader.observe_terminal(expectation=binding.expectation, binding=binding,
                        destination=tmp_path / "never-read", expected_reader_sha256=wrong_hash,
                        terminal_revision=pins["terminal_commit"])
        for role, pair in reader.FROZEN.items():
            with monkeypatch.context() as bad_pin:
                bad_pin.setitem(reader.FROZEN, role, (pair[0], "0" * 64))
                with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_reader_bytes_mismatch$"):
                    reader._binding(reader.FRESH_R2.expectation, source["module_sha256"], pins["terminal_commit"],
                                    False, binding=reader.FRESH_R2)
        with monkeypatch.context() as bad_r2:
            bad_r2.setattr(reader, "R2_PRODUCER_PIN", (reader.R2_PRODUCER_PIN[0], "0" * 64))
            with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_reader_bytes_mismatch$"):
                reader._binding(reader.FRESH_R2.expectation, source["module_sha256"], pins["terminal_commit"],
                                False, binding=reader.FRESH_R2)
    assert not (tmp_path / "never-read").exists() and effects == []
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    with monkeypatch.context() as read_only:
        for owner, name in ((ci, "verify_approval"), (controller, "_deadline"), (owned.LocalTransport, "child"),
                            (ci, "execute"), (fresh, "execute"), (previous, "execute"), (successor, "execute"),
                            (MemoryHF, "create_commit")):
            read_only.setattr(owner, name, forbidden)
        for binding in (reader.FRESH_R1, reader.FRESH_R2):
            transport = FreshResultHF(production_plan, binding=binding)
            kwargs = {} if binding is reader.FRESH_R1 else {"binding": binding}
            checked = positive("old_result_current_pins", lambda: reader.read_result(expectation=binding.expectation,
                destination=tmp_path / ("old-result-" + str(binding.ordinal)), expected_reader_sha256=source["module_sha256"],
                terminal_revision=TERMINAL_HEAD, _test_api=transport, **kwargs))
            assert checked["intake_verified"] is True and checked["grade"] is None and transport.commits == []
        default_failed = TerminalHF(production_plan, exit_code=1)
        checked = reader.observe_terminal(expectation=reader.EXPECTATION, destination=tmp_path / "default-r1-controls",
            expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=default_failed)
        assert checked["outcome"] == "terminal_verified" and checked["cell_id"] == fresh.CELL_ID
        assert default_failed.commits == []  # Omitted binding still observes r1, not r2.

    seed = prior.SuccessorHF(production_plan, binding=reader.FRESH_R2, successor_adapter=successor)
    synthetic_pins = seed.synthetic_identities()  # Expected authored bytes, not a validator's returned controls.
    monkeypatch.setattr(successor, "PREDECESSOR", synthetic_pins)
    comparison_roots = comparison.ROOT, comparison.PLAN
    plan, root, archive, sources = prior._scenario(tmp_path, monkeypatch, approved_pilot_source)
    assert (comparison.ROOT, comparison.PLAN) == comparison_roots
    _write(root / successor.FACADE, (REAL_ROOT / successor.FACADE).read_bytes())
    with tempfile.TemporaryDirectory(prefix=".retention-keep-r2-offline-", dir=REAL_ROOT.parent) as host_directory:
        host_parent = Path(host_directory)
        base._environment(monkeypatch, host_parent)
        _runtime(monkeypatch, root)
        request = controller.Request(successor.CELL_ID, sources, root / successor.PACKET_ROLE, root,
            preparation.source_identity()["sha256"], controller.source_identity()["sha256"], plan)
        packet = positive("keep_r2_packet", lambda: preparation.prepare_packet(cell_id=request.cell_id,
            sources=sources, output=request.packet, expected_preparer_sha256=request.expected_preparer_sha256, plan=plan))
        stage = positive("keep_r2_stage", lambda: controller.stage_runtime(request))
        assert controller.verify_staged_runtime(request) == stage
        assert stage["ordinal"] == 3 and stage["cell_id"] == successor.CELL_ID and stage["commands"] == []
        assert not any(stage[key] for key in ("launch_authorized", "inference_slot_reserved", "deadline_started"))
        assert stage["config_sha256"] == plan["cells"][3]["config_sha256"]
        assert (request.packet / preparation.INFERENCE).read_bytes() == controller._encoded(plan["cells"][3]["config"])
        assert stage["input_roles_sha256"] == packet["input_verification"]["original_input_roles_sha256"]
        assert controller.read_codex_prepared(controller.PREPARED)["execution"]["codex"]["task_deadline"] == {
            "condition": "retention_bundle_v1", "retention_bundle": "keep", "repetition": 2}
        assert controller._stage_paths(successor.CELL_ID) == tuple(root / "batch-runner/workspace" / name for name in (
            "retention-task4-keep-r2-staging.json", "retention-task4-keep-r2-staged.json"))
        with pytest.raises(controller.RetentionControllerRefused, match="^runtime_path_already_used_or_partial$"):
            controller.stage_runtime(request)
        document, observation = positive("keep_r2_request", lambda: successor.canonical_request(request,
            reviewed_source_sha=SOURCE, run_id="700000001", historical_root=archive))
        assert document["scope"] == successor.SCOPE and document["serial_domain"]["predecessor"] == synthetic_pins
        assert document["format"] == successor.REQUEST_FORMAT and document["provider"]["attempt"] == 1
        assert set(document["source"]["successor_adapter"]["files"]) == set(successor.SOURCE_PATHS)
        assert document["grading"] == stage["grading"]
        for cell, scope in ((controller.FIRST_CELL_ID, ci.SCOPE), (fresh.CELL_ID, fresh.SCOPE),
                            (previous.CELL_ID, previous.SCOPE), (successor.CELL_ID, successor.SCOPE)):
            with monkeypatch.context() as script:
                script.setattr(sys, "argv", [str(REAL_ROOT / successor.FACADE), "--cell", cell,
                                             "--reviewed-source-sha", SOURCE])
                with pytest.raises(SystemExit) as stopped:
                    runpy.run_path(str(REAL_ROOT / successor.FACADE), run_name="__main__")
                assert stopped.value.code == 0
            receipt = json.loads(capsys.readouterr().out)
            assert receipt["mode"] == "plan_only" and receipt["scope"] == scope and receipt["commands"] == []
        with monkeypatch.context() as before_source:
            before_source.setattr(ci, "require_source", forbidden)
            assert previous.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE]) == 2
            assert json.loads(capsys.readouterr().out)["reason"] == "only_registered_task4_fresh_r2_supported"
            assert successor.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE, "--observe-locator"]) == 2
            assert json.loads(capsys.readouterr().out)["reason"] == "keep_r2_locator_observation_not_supported"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        api = deepcopy(seed)
        child = KeepTransport(document, api, key)
        child.recovery_request = request
        grant = ci.ExecutionGrantRequest(SOURCE, owned._digest(document), archive)
        denied = host_parent / "not-admitted"
        for wrong in ("unregistered", *plan["order"][6:]):
            with pytest.raises(controller.RetentionControllerRefused, match="^only_first_or_task4_fresh_r1_supported$"):
                controller.execute_first_cell(replace(request, cell_id=wrong), host_state=denied, grant=grant)
        for old_cell in (controller.FIRST_CELL_ID, fresh.CELL_ID, previous.CELL_ID):
            with pytest.raises(preparation.RetentionPreparationRefused, match="^emitted_config_or_task_bytes_mismatch$"):
                controller.execute_first_cell(replace(request, cell_id=old_cell), host_state=denied, grant=grant)
        with pytest.raises(controller.RetentionControllerRefused, match="^controller_source_mismatch$"):
            controller.execute_first_cell(replace(request, expected_controller_sha256="0" * 64), host_state=denied, grant=grant)
        malformed_plan = deepcopy(plan)
        malformed_plan["cells"][3]["control"]["repetition"] = 1
        with pytest.raises(registration.RetentionRegistrationRefused, match="^compiled_plan_mismatch$"):
            controller.execute_first_cell(replace(request, plan=malformed_plan), host_state=denied, grant=grant)
        for malformed, reason in ((replace(grant, reviewed_source_sha="f" * 40), "clean_exact_retention_source_required"),
                                  (replace(grant, request_sha256="0" * 64), "approved_retention_request_changed")):
            with pytest.raises(ci.RetentionCIRefused, match="^" + reason + "$"):
                successor.execute(request, host_state=denied, grant=malformed, _test_transport=child, _test_api=api)
        with monkeypatch.context() as wrong_run:
            wrong_run.setenv("GITHUB_RUN_ID", "700000002")
            with pytest.raises(ci.RetentionCIRefused, match="^approved_retention_request_changed$"):
                successor.execute(request, host_state=denied, grant=grant, _test_transport=child, _test_api=api)
        pairs = ((ci._Admission, controller.FIRST_CELL_ID), (fresh._FreshAdmission, fresh.CELL_ID),
                 (previous._FreshR2Admission, previous.CELL_ID), (successor._KeepR2Admission, successor.CELL_ID))
        with monkeypatch.context() as before_context:
            before_context.setattr(controller, "_context", forbidden)
            for admission_class, expected_cell in pairs:
                for _, selected_cell in pairs:
                    if expected_cell == selected_cell:
                        continue
                    crossed = replace(request, cell_id=selected_cell)
                    candidate = admission_class(crossed, document, observation, {}, child, api)
                    with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
                        controller._run_post_authority_cell(crossed, host_state=denied, _admission=candidate)
                candidate = admission_class(None, document, observation, {}, child, api)
                with pytest.raises(controller.RetentionControllerRefused, match="^explicit_retention_request_required$"):
                    controller._run_post_authority_cell(None, host_state=denied, _admission=candidate)
            class Noncanonical(successor._KeepR2Admission):
                pass
            for candidate, selected, mixed in (
                    (Noncanonical(None, None, None, None, None, None), None, None),
                    (successor._KeepR2Admission(None, None, None, None, None, None), request, None),
                    (successor._KeepR2Admission(request, None, None, None, None, None), request, child)):
                with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
                    controller._run_post_authority_cell(selected, host_state=denied, _admission=candidate, _test_transport=mixed)
        assert not denied.exists() and api.calls == [] and child.children == [] and child.github_calls == 0
        bad_approval = KeepTransport(document, deepcopy(seed), key)
        bad_approval.provider[2][0]["comment"] = ci.APPROVAL_PREFIX + "0" * 64
        with pytest.raises(ci.RetentionCIRefused, match="^owner_environment_request_approval_mismatch$"):
            successor.execute(request, host_state=denied, grant=grant, _test_transport=bad_approval, _test_api=bad_approval.api)
        assert not denied.exists() and bad_approval.api.calls == []

        cases = {"head": "keep_r2_predecessor_head_mismatch", "terminal_hash": "keep_r2_predecessor_identity_mismatch",
            "claim_hash": "keep_r2_predecessor_identity_mismatch", "manifest_hash": "keep_r2_predecessor_identity_mismatch",
            "objects_hash": "keep_r2_predecessor_identity_mismatch", "source": "fresh_result_completion_mismatch",
            "run": "fresh_result_authority_binding_mismatch", "job": "fresh_terminal_execution_job_mismatch",
            "request": "fresh_result_terminal_binding_mismatch", "cell": "fresh_result_completion_mismatch",
            "predecessor": "fresh_result_predecessor_mismatch", "status": "fresh_terminal_unsuccessful_required",
            "stopped": "keep_r2_predecessor_identity_mismatch", "exit": "keep_r2_predecessor_identity_mismatch",
            "cleanup": "fresh_result_completion_mismatch", "history": "retention_control_history_mismatch",
            "claim_history": "retention_control_history_mismatch", "object_history": "remote_output_history_mismatch",
            "namespace": "retention_namespace_already_used", "cas_race": "hf_http_failed", "lost_claim": "hf_transport_failed"}
        for fault, reason in cases.items():
            server, expected = deepcopy(seed), deepcopy(synthetic_pins)
            if fault == "source":
                server.summary["source_sha"] = "0" * 40
            elif fault in ("run", "job"):
                for authority in (server.claim["authority"], server.terminal["authority"]):
                    authority["provider_run_id" if fault == "run" else "provider_job_id"] = "700000009" if fault == "run" else 700000009
            elif fault == "request":
                server.terminal["request_sha256"] = "0" * 64
            elif fault == "cell":
                server.summary["cell_id"] = successor.CELL_ID
            elif fault == "predecessor":
                server.claim["expected_parent"] = "0" * 40
            elif fault in ("status", "stopped"):
                server.summary["status"] = "succeeded" if fault == "status" else "stopped"
            elif fault == "exit":
                server.summary["exit_code"] = 0
            elif fault == "cleanup":
                server.summary["cleanup_confirmed"] = False
            server.seed()
            if fault == "head":
                server.head = pins["output_commit"]
            elif fault in ("terminal_hash", "claim_hash", "manifest_hash"):
                field = {"terminal_hash": "terminal_identity", "claim_hash": "claim_identity",
                         "manifest_hash": "output_manifest_identity"}[fault]
                expected[field]["sha256"] = "0" * 64
            elif fault == "objects_hash":
                expected["output_objects_sha256"] = "0" * 64
            elif fault == "history":
                server.writers[server.head][previous.TERMINAL] = pins["output_commit"]
            elif fault == "claim_history":
                server.writers[pins["claim_commit"]][previous.CLAIM] = pins["terminal_commit"]
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
            authority = ci.verify_approval(document, transport)
            admission = successor._KeepR2Admission(request, document, observation, authority, transport, server)
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

        snapshot = tmp_path / "staged-snapshot"
        shutil.copytree(root, snapshot)
        host = host_parent / "completed"
        result = positive("keep_r2_claim_child_output_terminal", lambda: controller.execute_first_cell(request,
            host_state=host, grant=grant, _test_transport=child, _test_api=api))
        assert result == {"cell_id": successor.CELL_ID, "status": "succeeded", "request_sha256": grant.request_sha256,
            "cleanup_confirmed": True, "remote_terminal": "acknowledged", "grade": None,
            "grading_launched": False, "invoice_complete": False}
        assert child.keep_record["retention_bundle"] == "keep" and child.keep_record["repetition"] == 2
        assert api.events == ["admission", "child", "output", "terminal"]
        assert api.parents[api.parents[api.parents[api.head]]] == pins["terminal_commit"]
        assert all(name in {previous.CLAIM, previous.TERMINAL, previous.OUTPUT + "/" + output.MANIFEST}
                   for revision, name in api.downloads if revision in (pins["terminal_commit"], pins["claim_commit"], pins["output_commit"]))
        claim = retained._read(host / "remote-admission-receipt.json")["claim"]
        terminal = retained._read(host / "remote-terminal-expected.json")
        assert claim["expected_parent"] == pins["terminal_commit"] and claim["predecessor"] == synthetic_pins
        assert terminal["format"] == successor.TERMINAL_FORMAT and terminal["completion"]["format"] == successor.OUTPUT_FORMAT
        assert terminal["completion"]["receipt"] is None and terminal["completion"]["grade"] is None
        held = (host / "remote-terminal-receipt.json").read_bytes()
        with retained._session(api) as (server, token, deadline):
            reconciled = positive("keep_r2_immutable_reconciliation", lambda: successor.verify_terminal(server, server.repo,
                server.head, terminal, claim, ci._cache(host, "reconcile"), token, deadline))
        assert reconciled["writer_acknowledgment"] == "not_established" and reconciled["replay_authorized"] is False
        assert (host / "remote-terminal-receipt.json").read_bytes() == held
        with pytest.raises(controller.RetentionControllerRefused, match="^first_cell_already_reserved_or_partial_no_replay$"):
            successor.execute(request, host_state=host, grant=grant, _test_transport=child, _test_api=api)
        assert len(child.children) == 1 and api.commits == ["admission", "output", "terminal"]
        duplicate = successor._KeepR2Admission(request, document, observation, claim["authority"], child, api)
        duplicate.receipt = retained._read(host / "remote-admission-receipt.json")
        with pytest.raises(FileExistsError):
            duplicate.finish(host, owned._load(host / "cell.json"))
        for fault in ("lost_output", "lost_terminal", "cleanup", "timeout", "remote_no_replay"):
            trial_root = tmp_path / fault
            shutil.copytree(snapshot, trial_root)
            with monkeypatch.context() as trial:
                _runtime(trial, trial_root)
                selected = replace(request, packet=trial_root / successor.PACKET_ROLE, runtime_checkout=trial_root)
                current, _ = successor.canonical_request(selected, reviewed_source_sha=SOURCE,
                    run_id="700000001", historical_root=archive)
                assert current == document
                server = deepcopy(api if fault == "remote_no_replay" else seed)
                server.lost = "output" if fault == "lost_output" else "terminal" if fault == "lost_terminal" else None
                transport = KeepTransport(current, server, key, mode=fault if fault in ("cleanup", "timeout") else "ordinary")
                private = host_parent / fault
                if fault == "timeout":
                    stopped = positive("keep_r2_timeout_cleanup_publication", lambda: successor.execute(selected,
                        host_state=private, grant=grant, _test_transport=transport, _test_api=server))
                    assert stopped["status"] == "stopped" and stopped["cleanup_confirmed"] is True
                    timed = owned._load(private / "cell.json")
                    assert timed["reason"] == "child_timeout_partial_accounting" and timed["exit_code"] is None
                    clock = controller._deadline(private, controller._context(selected), stage, transport)
                    try:
                        assert clock.for_task(registration.TASK4).remaining_seconds() == 0
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
                        refusal = retained._read(private / "remote-admission-receipt.json")
                        assert refusal["reason"] == "keep_r2_predecessor_head_mismatch" and transport.children == []
                        assert not (private / "deadline").exists()
                    else:
                        refusal = retained._read(private / "remote-terminal-receipt.json")
                        assert refusal["outcome"] == "unresolved" and refusal["reason"] == "hf_transport_failed"
                        if fault == "lost_terminal":
                            unresolved = (private / "remote-terminal-receipt.json").read_bytes()
                            expected_terminal = retained._read(private / "remote-terminal-expected.json")
                            expected_claim = retained._read(private / "remote-admission-receipt.json")["claim"]
                            with retained._session(server) as (memory, token, deadline):
                                view = successor.verify_terminal(memory, memory.repo, memory.head, expected_terminal,
                                    expected_claim, ci._cache(private, "lost-ack-observation"), token, deadline)
                            assert view["writer_acknowledgment"] == "not_established" and view["observation_only"] is True
                            assert (private / "remote-terminal-receipt.json").read_bytes() == unresolved
                assert len(transport.children) == (0 if fault == "remote_no_replay" else 1)
                assert server.commits == (["admission"] if fault == "cleanup" else ["admission", "output"]
                    if fault == "lost_output" else ["admission", "output", "terminal"])

        for ordinal, adapter, namespace in ((0, ci, "retention-first-cell"), (1, fresh, "retention-task4-fresh-r1"),
                                             (2, previous, "retention-task4-fresh-r2")):
            old_root = tmp_path / namespace
            _source_tree(old_root)
            with monkeypatch.context() as old:
                _runtime(old, old_root)
                old_request = replace(request, cell_id=plan["order"][ordinal], packet=old_root / adapter.PACKET_ROLE,
                                      runtime_checkout=old_root)
                preparation.prepare_packet(cell_id=old_request.cell_id, sources=sources, output=old_request.packet,
                    expected_preparer_sha256=old_request.expected_preparer_sha256, plan=plan)
                old_stage = controller.stage_runtime(old_request)
                assert old_stage["format"] == "codex-" + namespace + "-v1" and old_stage["ordinal"] == ordinal
                assert controller.read_codex_prepared(controller.PREPARED)["execution"]["codex"]["task_deadline"] == plan["cells"][ordinal]["control"]
                assert controller._stage_paths(old_request.cell_id) == tuple(old_root / "batch-runner/workspace" / (namespace + suffix)
                    for suffix in ("-staging.json", "-staged.json"))
                old_document, _ = adapter.canonical_request(old_request, reviewed_source_sha=SOURCE,
                    run_id="700000001", historical_root=archive)
                assert old_document["format"] == adapter.REQUEST_FORMAT and old_document["scope"] == adapter.SCOPE
                assert old_document["serial_domain"]["prefix"] == adapter.PREFIX
                consumed = deepcopy(seed)
                old_child = base.Transport(old_document, consumed, key)
                old_host = host_parent / ("consumed-" + str(ordinal))
                reason = ("terminal_or_claim_missing", "fresh_predecessor_head_mismatch", "fresh_r2_predecessor_head_mismatch")[ordinal]
                with pytest.raises(ci.RetentionCIRefused, match="^retention_claim_unresolved:" + reason + "$"):
                    controller.execute_first_cell(old_request, host_state=old_host,
                        grant=ci.ExecutionGrantRequest(SOURCE, owned._digest(old_document), archive),
                        _test_transport=old_child, _test_api=consumed)
                assert old_child.children == [] and consumed.commits == [] and not (old_host / "deadline").exists()
        assert all(api.trees[revision] == tree for revision, tree in seed.trees.items())
        assert effects == [] and base.PRIVATE.decode() not in capsys.readouterr().out
    print(json.dumps({"scope": "synthetic_task4_keep_r2_only", "predecessor_cases": len(cases),
        "route": "failed_fresh_r2_claim_keep_child_output_terminal", "old_schema_and_current_pins_checked": True,
        "within_cell_keep_recovery_checked": True, "no_cross_cell_adoption_or_replay": True,
        "inference_launched": False, "grading_launched": False}, sort_keys=True))
