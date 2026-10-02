"""One ordinal-two proof: real predicates, synthetic controls and owned child only."""

from copy import deepcopy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import codex_retention_task4_fresh_r2 as successor
import gpt54_disposable_checkout as checkout
from . import test_codex_retention_task4_fresh_r1 as base
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN, offline  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_fresh_r1_terminal_observation import TerminalHF
from .test_codex_retention_result_intake import TERMINAL_HEAD

fresh, reader, ci = successor.fresh, successor.reader, successor.ci
controller, preparation, registration = successor.controller, successor.preparation, successor.registration
owned, retained, output, historical = successor.owned, successor.retained, successor.output, successor.historical
REAL_ROOT, SOURCE, TREE = base.REAL_ROOT, base.SOURCE, base.TREE
positive, _write = base.positive, base._write


class SuccessorHF(MemoryHF):
    """Authored controls at fixed synthetic revisions; never prior payload downloads."""

    def __init__(self, plan, *, binding=reader.FRESH_R1, successor_adapter=successor):
        super().__init__()
        producer = TerminalHF(plan, exit_code=1, binding=binding)
        self.producer_paths = (producer.producer.CLAIM, producer.producer.TERMINAL, producer.producer.OUTPUT)
        self.successor_paths = (successor_adapter.CLAIM, successor_adapter.TERMINAL, successor_adapter.OUTPUT)
        self.preceding_terminal = producer.producer.PREDECESSOR["terminal_commit"]
        self.claim, self.summary, self.terminal, self.files = (
            deepcopy(getattr(producer, name)) for name in ("claim", "summary", "terminal", "files"))
        self.pins = deepcopy(successor_adapter.PREDECESSOR)
        self.terminal.update(claim_commit=self.pins["claim_commit"], output_commit=self.pins["output_commit"])
        self.downloads = []
        self.seed()

    def seed(self):
        claim_path, terminal_path, output_path = self.producer_paths
        claim, outputs, terminal = (self.pins[key] for key in ("claim_commit", "output_commit", "terminal_commit"))
        self.summary["files"] = [{"path": name, **owned._identity(data)} for name, data in sorted(self.files.items())]
        claim_bytes = retained._encoded(self.claim)
        self.terminal.update(claim_identity=owned._identity(claim_bytes), completion=self.summary)
        payloads = {output_path + "/" + name: data for name, data in self.files.items()}
        payloads[output_path + "/" + output.MANIFEST] = retained._encoded(self.summary)
        self.terminal["output_objects"] = [retained._object(name, data) for name, data in sorted(payloads.items())]
        self.trees[claim] = {claim_path: claim_bytes}
        self.trees[outputs] = {**self.trees[claim], **payloads}
        self.trees[terminal] = {**self.trees[outputs], terminal_path: retained._encoded(self.terminal)}
        self.writers[claim] = {claim_path: claim}
        self.writers[outputs] = {**self.writers[claim], **{name: outputs for name in payloads}}
        self.writers[terminal] = {**self.writers[outputs], terminal_path: terminal}
        self.parents.update({claim: self.preceding_terminal, outputs: claim, terminal: outputs})
        self.head = terminal

    def synthetic_identities(self):
        # Bind the authored synthetic bytes, not any validator result. Fixed
        # production source/run/cell/request/revision literals stay unchanged.
        return {**self.pins, "terminal_identity": owned._identity(retained._encoded(self.terminal)),
            "claim_identity": owned._identity(retained._encoded(self.claim)),
            "output_manifest_identity": owned._identity(retained._encoded(self.summary)),
            "output_objects_sha256": owned._digest(self.terminal["output_objects"])}

    def hf_hub_download(self, **kwargs):
        self.downloads.append((kwargs["revision"], kwargs["filename"]))
        assert kwargs["filename"] in {path for claim, terminal, outputs in (self.producer_paths, self.successor_paths)
                                      for path in (claim, terminal, outputs + "/" + output.MANIFEST)}
        return super().hf_hub_download(**kwargs)


class R2Transport(base.FreshTransport):
    ordinal, repetition, cell_id = 2, 2, successor.CELL_ID

    def owned_process(self, command, **options):
        result = super().owned_process(command, **options)
        if self.mode == "timeout":
            self.clock.now += 10860  # Synthetic elapsed time, including the cleanup allowance; never sleep.
            raise subprocess.TimeoutExpired(command, options["timeout"])
        return result


def _source_tree(root):
    base._source_tree(root)
    for role in (successor.FACADE, "batch-runner/codex_retention_fresh_r1_result_intake.py",
                 "batch-runner/codex_retention_result_intake.py"):
        _write(root / role, (REAL_ROOT / role).read_bytes())


def _runtime(monkeypatch, root):
    base._runtime(monkeypatch, root)
    monkeypatch.setattr(successor, "ROOT", root)


def _scenario(tmp_path, monkeypatch, approved_pilot_source):
    inputs, captures, original_run, manifest, roles = positive("synthetic_original_serializer",
        lambda: base._originals(tmp_path, monkeypatch, approved_pilot_source))
    plan = positive("registered_original_bindings", registration.compile_plan)
    root, archive, common = (tmp_path / name for name in ("runtime-source", "historical-observer", "git-metadata"))
    _source_tree(root)
    common.mkdir()
    archive_buffer = io.BytesIO()
    archive_manifest = registration.load_plan(registration.ROOT / registration.ORIGINAL_PROFILE)
    with tarfile.open(fileobj=archive_buffer, mode="w", format=tarfile.PAX_FORMAT,
                      pax_headers={"comment": historical.SOURCE}) as tar:
        data = owned._canonical_json(archive_manifest).encode()
        member = tarfile.TarInfo(historical.MANIFEST_PATH)
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    old_cells = base._historical_cells(original_run, captures, approved_pilot_source)
    assert old_cells[-1]["run_id"] != plan["cells"][2]["config"]["experiment"]["id"]
    observer = {"format": historical.FORMAT, "observer_source_sha": historical.SOURCE,
        "producer_source_sha": historical.PRODUCER,
        "plan": {"reviewed_source_sha": historical.PRODUCER, "run_id": "budget_pilot_ci_20260925_04",
            "cells": old_cells, "order": [cell["cell_id"] for cell in old_cells], "launch_authorized_by_plan": False},
        "inputs": {"files_sha256": owned._digest(roles),
            "source_projection_sha256": captures[0]["ordered_source_projection_sha256"]}}

    def git(path, *command, ok=(0,)):
        if command == ("archive", "--format=tar", historical.SOURCE, "batch-runner", ".github/workflows"):
            assert path == historical.ROOT
            return SimpleNamespace(stdout=archive_buffer.getvalue(), returncode=0)
        assert Path(path) == ci.ROOT
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(path) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (SOURCE + "\n").encode(),
            ("rev-parse", "HEAD^{tree}"): (TREE + "\n").encode(),
            ("status", "--porcelain", "--untracked-files=normal"): b"",
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): b""}
        assert command in answers, "only fixed Git metadata is simulated"
        return SimpleNamespace(stdout=answers[command], returncode=0)

    def metadata_process(command, **options):
        assert command == [sys.executable, "-c", historical.SAFE_ERROR + historical.OBSERVE,
                           str(inputs["dataset_parquet"]), str(inputs["reference_root"]), str(manifest)]
        assert options["cwd"] == archive / "batch-runner" and options["timeout"] == 90
        assert set(options["env"]) == {"PATH", "LANG", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE",
            "HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE", "TRANSFORMERS_OFFLINE", "GDPVAL_RELAY_LINEAGE_ID"}
        assert options["env"]["GDPVAL_RELAY_LINEAGE_ID"] == historical.INPUT_LINEAGE
        return SimpleNamespace(stdout=retained._encoded(observer), stderr=b"", returncode=0)

    monkeypatch.setattr(owned, "_git", git)
    monkeypatch.setattr(checkout, "_git", git)
    monkeypatch.setattr(subprocess, "run", metadata_process)
    positive("historical_archive_transport", lambda: historical.materialize_archive(archive))
    _write(archive / preparation.CONFIG_PATH, original_run.generated_config.read_bytes())
    _write(archive / preparation.PREPARED_PATH, original_run.prepared_tasks.read_bytes())
    sources = preparation.PreparedInputs(archive, inputs["dataset_parquet"], inputs["reference_root"], manifest)
    return plan, root, archive, sources


def test_task4_fresh_r2_advances_only_the_fixed_failed_predecessor(tmp_path, monkeypatch, capsys, approved_pilot_source):
    production_plan = registration.compile_plan()
    pins = deepcopy(successor.PREDECESSOR)
    assert pins == {
        "cell_id": "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_fresh_r1",
        "producer_source_sha": "e39d8d1aadcb816d09588829a5ec4929b33083e6",
        "run_id": "36845127347", "execution_job_id": 110323708382,
        "request_sha256": "5bbb0e4cb5ae9444eac9c804ac3c8d2f6d39acbec63e7f7de78d7f2ee35fcf02",
        "terminal_commit": "45f54eb0a24aee5d40dd41b276ff5df777f06d73",
        "terminal_identity": {"sha256": "2fa29205d842956fcbd857e4b1e1878af4551ebddc7573e480d7e17d01b63faa", "size": 4206},
        "claim_commit": "4bff20bdae3cddb28519eadec9f032af5b6843d5",
        "claim_identity": {"sha256": "0ed2ab8979fd918218415ee08eee5ad99d9d3a9e08b41695f0b30e2afd0cc1c4", "size": 1484},
        "output_commit": "3b27e0a7e9d05c9ecfb400040bd8c025bc7f2484",
        "output_manifest_identity": {"sha256": "f48abaab90af661811b257d709a0934819ef057854976694a543e4ed76cd3380", "size": 2125},
        "output_objects_sha256": "1ac663171c092a21edd0287e2749daab3e216dcbee1efa14b5ea70eab4853c1a",
        "status": "failed", "exit_code": 1, "cleanup_confirmed": True,
    }
    assert [(item.cell_id, item.ordinal, item.bundle, item.repetition) for item in controller.CELL_BINDINGS] == [
        (production_plan["order"][0], 0, "keep", 1), (production_plan["order"][1], 1, "fresh", 1),
        (production_plan["order"][2], 2, "fresh", 2), (production_plan["order"][3], 3, "keep", 2),
        (production_plan["order"][4], 4, "fresh", 1), (production_plan["order"][5], 5, "keep", 1)]
    assert reader.intake.reader_identity() == {
        "module_sha256": "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196",
        "terminal_verifier_sha256": "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c"}
    source = reader.reader_identity()
    assert {key: source[key] for key in reader.FROZEN} == {key: pair[1] for key, pair in reader.FROZEN.items()}
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("ordinal-two proof crossed a forbidden boundary")

    for name in ("core.executor.TaskExecutor.__init__", "step8_grade.main", "step8_grade.RubricLoader.load",
                 "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset"):
        monkeypatch.setattr(name, forbidden)
    # Changed CURRENT pins accept the unchanged old-result schema; stale/wrong
    # pins refuse before credential acquisition, destination creation or effects.
    with monkeypatch.context() as no_credentials:
        no_credentials.setattr(retained, "_session", forbidden)
        for wrong_hash in ("0" * 64, "bbb46c87ac840317a4f41959d2278677ed29e52e7ae28f49cf47db7a464eaafa"):
            with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_reader_bytes_mismatch$"):
                reader.observe_terminal(expectation=reader.EXPECTATION, destination=tmp_path / "never-read",
                    expected_reader_sha256=wrong_hash, terminal_revision=pins["terminal_commit"])
        for role, pair in reader.FROZEN.items():
            with monkeypatch.context() as bad_pin:
                bad_pin.setitem(reader.FROZEN, role, (pair[0], "0" * 64))
                with pytest.raises(output.OutputPublicationRefused, match="^fresh_result_reader_bytes_mismatch$"):
                    reader._binding(reader.EXPECTATION, source["module_sha256"], pins["terminal_commit"], False)
    assert not (tmp_path / "never-read").exists() and effects == []
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    old_success = FreshResultHF(production_plan)
    with monkeypatch.context() as read_only:
        for owner, name in ((ci, "verify_approval"), (controller, "_deadline"), (owned.LocalTransport, "child"),
                            (ci, "execute"), (fresh, "execute"), (successor, "execute"), (MemoryHF, "create_commit")):
            read_only.setattr(owner, name, forbidden)
        checked = positive("old_result_current_pins", lambda: reader.read_result(expectation=reader.EXPECTATION,
            destination=tmp_path / "old-result", expected_reader_sha256=source["module_sha256"],
            terminal_revision=TERMINAL_HEAD, _test_api=old_success))
    assert checked["intake_verified"] is True and checked["grade"] is None and old_success.commits == []
    with retained._session(old_success) as (server, token, deadline):
        old_view = fresh.verify_terminal(server, server.repo, TERMINAL_HEAD, old_success.terminal, old_success.claim,
            ci._cache(tmp_path, "old-writer-readback"), token, deadline)
    assert old_view["completion"] == old_success.summary and old_view["writer_acknowledgment"] == "not_established"

    seed = SuccessorHF(production_plan)
    synthetic_pins = seed.synthetic_identities()
    monkeypatch.setattr(successor, "PREDECESSOR", synthetic_pins)
    plan, root, archive, sources = _scenario(tmp_path, monkeypatch, approved_pilot_source)
    # A separate private host namespace, never the original/runtime inputs.
    with tempfile.TemporaryDirectory(prefix=".retention-r2-offline-", dir=REAL_ROOT.parent) as host_directory:
        host_parent = Path(host_directory)
        base._environment(monkeypatch, host_parent)
        _runtime(monkeypatch, root)
        request = controller.Request(successor.CELL_ID, sources, root / successor.PACKET_ROLE, root,
            preparation.source_identity()["sha256"], controller.source_identity()["sha256"], plan)
        packet = positive("fresh_r2_packet", lambda: preparation.prepare_packet(cell_id=request.cell_id,
            sources=sources, output=request.packet, expected_preparer_sha256=request.expected_preparer_sha256, plan=plan))
        stage = positive("fresh_r2_stage", lambda: controller.stage_runtime(request))
        assert controller.verify_staged_runtime(request) == stage
        assert stage["ordinal"] == 2 and stage["cell_id"] == successor.CELL_ID and stage["commands"] == []
        assert not any(stage[key] for key in ("launch_authorized", "inference_slot_reserved", "deadline_started"))
        assert stage["config_sha256"] == plan["cells"][2]["config_sha256"]
        assert (request.packet / preparation.INFERENCE).read_bytes() == controller._encoded(plan["cells"][2]["config"])
        assert stage["input_roles_sha256"] == packet["input_verification"]["original_input_roles_sha256"]
        assert controller.read_codex_prepared(controller.PREPARED)["execution"]["codex"]["task_deadline"] == {
            "condition": "retention_bundle_v1", "retention_bundle": "fresh", "repetition": 2}
        assert controller._stage_paths(successor.CELL_ID) == tuple(root / "batch-runner/workspace" / name for name in (
            "retention-task4-fresh-r2-staging.json", "retention-task4-fresh-r2-staged.json"))
        with pytest.raises(controller.RetentionControllerRefused, match="^runtime_path_already_used_or_partial$"):
            controller.stage_runtime(request)
        document, observation = positive("fresh_r2_request", lambda: successor.canonical_request(request,
            reviewed_source_sha=SOURCE, run_id="700000001", historical_root=archive))
        assert document["scope"] == successor.SCOPE and document["serial_domain"]["predecessor"] == synthetic_pins
        assert document["format"] == successor.REQUEST_FORMAT
        assert set(document["source"]["successor_adapter"]["files"]) == set(successor.SOURCE_PATHS)
        assert document["grading"] == stage["grading"]
        for cell, scope in ((controller.FIRST_CELL_ID, ci.SCOPE), (fresh.CELL_ID, fresh.SCOPE),
                            (successor.CELL_ID, successor.SCOPE)):
            with monkeypatch.context() as script:
                script.setattr(sys, "argv", [str(REAL_ROOT / successor.FACADE), "--cell", cell,
                                             "--reviewed-source-sha", SOURCE])
                with pytest.raises(SystemExit) as stopped:
                    runpy.run_path(str(REAL_ROOT / successor.FACADE), run_name="__main__")
                assert stopped.value.code == 0
            receipt = json.loads(capsys.readouterr().out)
            assert receipt["mode"] == "plan_only" and receipt["scope"] == scope and receipt["commands"] == []
        assert fresh.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE]) == 2
        assert json.loads(capsys.readouterr().out)["reason"] == "only_first_or_task4_fresh_r1_supported"
        assert successor.main(["--cell", successor.CELL_ID, "--reviewed-source-sha", SOURCE, "--observe-locator"]) == 2
        assert json.loads(capsys.readouterr().out)["reason"] == "fresh_locator_observation_not_supported"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        api = deepcopy(seed)
        child = R2Transport(document, api, key)
        grant = ci.ExecutionGrantRequest(SOURCE, owned._digest(document), archive)
        denied = host_parent / "not-admitted"
        for wrong in ("unregistered", *plan["order"][6:]):
            with pytest.raises(controller.RetentionControllerRefused, match="^only_first_or_task4_fresh_r1_supported$"):
                controller.execute_first_cell(replace(request, cell_id=wrong), host_state=denied, grant=grant)
        for old_cell in (controller.FIRST_CELL_ID, fresh.CELL_ID):
            with pytest.raises(preparation.RetentionPreparationRefused, match="^emitted_config_or_task_bytes_mismatch$"):
                controller.execute_first_cell(replace(request, cell_id=old_cell), host_state=denied, grant=grant)
        with pytest.raises(controller.RetentionControllerRefused, match="^controller_source_mismatch$"):
            controller.execute_first_cell(replace(request, expected_controller_sha256="0" * 64), host_state=denied, grant=grant)
        malformed_plan = deepcopy(plan)
        malformed_plan["cells"][2]["control"]["repetition"] = 1
        with pytest.raises(registration.RetentionRegistrationRefused, match="^compiled_plan_mismatch$"):
            controller.execute_first_cell(replace(request, plan=malformed_plan), host_state=denied, grant=grant)
        for malformed_grant, reason in (
                (replace(grant, reviewed_source_sha="f" * 40), "clean_exact_retention_source_required"),
                (replace(grant, request_sha256="0" * 64), "approved_retention_request_changed")):
            with pytest.raises(ci.RetentionCIRefused, match="^" + reason + "$"):
                successor.execute(request, host_state=denied, grant=malformed_grant, _test_transport=child, _test_api=api)
        with monkeypatch.context() as wrong_run:
            wrong_run.setenv("GITHUB_RUN_ID", "700000002")
            with pytest.raises(ci.RetentionCIRefused, match="^approved_retention_request_changed$"):
                successor.execute(request, host_state=denied, grant=grant, _test_transport=child, _test_api=api)
        # Real guard ordering before _context, inputs, host state, transport or clock.
        pairs = ((ci._Admission, controller.FIRST_CELL_ID), (fresh._FreshAdmission, fresh.CELL_ID),
                 (successor._FreshR2Admission, successor.CELL_ID))
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
            class Noncanonical(successor._FreshR2Admission):
                pass
            for candidate, selected, mixed in (
                    (Noncanonical(None, None, None, None, None, None), None, None),
                    (successor._FreshR2Admission(None, None, None, None, None, None), request, None),
                    (successor._FreshR2Admission(request, None, None, None, None, None), request, child)):
                with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
                    controller._run_post_authority_cell(selected, host_state=denied, _admission=candidate, _test_transport=mixed)
        assert not denied.exists() and api.calls == [] and child.children == [] and child.github_calls == 0
        bad_approval = R2Transport(document, deepcopy(seed), key)
        bad_approval.provider[2][0]["comment"] = ci.APPROVAL_PREFIX + "0" * 64
        with pytest.raises(ci.RetentionCIRefused, match="^owner_environment_request_approval_mismatch$"):
            successor.execute(request, host_state=denied, grant=grant, _test_transport=bad_approval, _test_api=bad_approval.api)
        assert not denied.exists() and bad_approval.api.calls == []

        cases = {"head": "fresh_r2_predecessor_head_mismatch", "terminal_hash": "fresh_r2_predecessor_identity_mismatch",
            "claim_hash": "fresh_r2_predecessor_identity_mismatch", "manifest_hash": "fresh_r2_predecessor_identity_mismatch",
            "objects_hash": "fresh_r2_predecessor_identity_mismatch", "source": "fresh_result_completion_mismatch",
            "run": "fresh_result_authority_binding_mismatch", "request": "fresh_result_terminal_binding_mismatch",
            "cell": "fresh_result_completion_mismatch", "predecessor": "fresh_result_predecessor_mismatch",
            "status": "fresh_terminal_unsuccessful_required", "stopped": "fresh_r2_predecessor_identity_mismatch",
            "exit": "fresh_r2_predecessor_identity_mismatch", "cleanup": "fresh_result_completion_mismatch",
            "history": "retention_control_history_mismatch", "namespace": "retention_namespace_already_used",
            "cas_race": "hf_http_failed", "lost_claim": "hf_transport_failed"}
        for fault, reason in cases.items():
            server, expected = deepcopy(seed), deepcopy(synthetic_pins)
            if fault == "source":
                server.summary["source_sha"] = "0" * 40
            elif fault == "run":
                for authority in (server.claim["authority"], server.terminal["authority"]):
                    authority["provider_run_id"] = "700000009"
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
                server.writers[server.head][fresh.TERMINAL] = pins["output_commit"]
            elif fault == "namespace":
                server.trees[server.head][successor.CLAIM] = b"already used"
                server.writers[server.head][successor.CLAIM] = server.head
            elif fault == "cas_race":
                server.move_before_commit = True
            elif fault == "lost_claim":
                server.lost = "admission"
            transport = R2Transport(document, server, key)
            authority = ci.verify_approval(document, transport)
            admission = successor._FreshR2Admission(request, document, observation, authority, transport, server)
            host = host_parent / ("refused-" + fault)
            host.mkdir(mode=0o700)
            with monkeypatch.context() as synthetic:
                synthetic.setattr(successor, "PREDECESSOR", expected)
                with pytest.raises(ci.RetentionCIRefused, match="^retention_claim_unresolved:"):
                    admission.admit(host)
            receipt = retained._read(host / "remote-admission-receipt.json")
            assert receipt["outcome"] == "unresolved" and receipt["reason"] == reason, fault
            assert transport.children == [] and not (host / "deadline").exists()
            assert server.commits == (["admission"] if fault in ("cas_race", "lost_claim") else [])

        snapshot = tmp_path / "staged-snapshot"
        shutil.copytree(root, snapshot)
        host = host_parent / "completed"
        result = positive("r2_claim_child_output_terminal", lambda: controller.execute_first_cell(request,
            host_state=host, grant=grant, _test_transport=child, _test_api=api))
        assert result == {"cell_id": successor.CELL_ID, "status": "succeeded", "request_sha256": grant.request_sha256,
            "cleanup_confirmed": True, "remote_terminal": "acknowledged", "grade": None,
            "grading_launched": False, "invoice_complete": False}
        assert api.events == ["admission", "child", "output", "terminal"]
        assert api.parents[api.parents[api.parents[api.head]]] == pins["terminal_commit"]
        assert all(name in {fresh.CLAIM, fresh.TERMINAL, fresh.OUTPUT + "/" + output.MANIFEST}
                   for revision, name in api.downloads if revision in (pins["terminal_commit"], pins["claim_commit"], pins["output_commit"]))
        claim = retained._read(host / "remote-admission-receipt.json")["claim"]
        terminal = retained._read(host / "remote-terminal-expected.json")
        assert claim["expected_parent"] == pins["terminal_commit"] and claim["predecessor"] == synthetic_pins
        assert terminal["format"] == successor.TERMINAL_FORMAT and terminal["completion"]["format"] == successor.OUTPUT_FORMAT
        assert terminal["completion"]["receipt"] is None and terminal["completion"]["grade"] is None
        held_receipt = (host / "remote-terminal-receipt.json").read_bytes()
        with retained._session(api) as (server, token, deadline):
            reconciled = positive("r2_immutable_reconciliation", lambda: successor.verify_terminal(server, server.repo,
                server.head, terminal, claim, ci._cache(host, "reconcile"), token, deadline))
        assert reconciled["writer_acknowledgment"] == "not_established" and reconciled["replay_authorized"] is False
        assert (host / "remote-terminal-receipt.json").read_bytes() == held_receipt
        with pytest.raises(controller.RetentionControllerRefused, match="^first_cell_already_reserved_or_partial_no_replay$"):
            successor.execute(request, host_state=host, grant=grant, _test_transport=child, _test_api=api)
        assert len(child.children) == 1 and api.commits == ["admission", "output", "terminal"]
        duplicate = successor._FreshR2Admission(request, document, observation, claim["authority"], child, api)
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
                transport = R2Transport(current, server, key, mode=fault if fault in ("cleanup", "timeout") else "ordinary")
                private = host_parent / fault
                if fault == "timeout":
                    stopped = positive("r2_timeout_cleanup_publication", lambda: successor.execute(selected,
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
                        assert refusal["reason"] == "fresh_r2_predecessor_head_mismatch" and transport.children == []
                        assert not (private / "deadline").exists()
                    else:
                        refusal = retained._read(private / "remote-terminal-receipt.json")
                        assert refusal["outcome"] == "unresolved" and refusal["reason"] == "hf_transport_failed"
                        if fault == "lost_terminal":
                            held = (private / "remote-terminal-receipt.json").read_bytes()
                            expected_terminal = retained._read(private / "remote-terminal-expected.json")
                            expected_claim = retained._read(private / "remote-admission-receipt.json")["claim"]
                            with retained._session(server) as (memory, token, deadline):
                                view = successor.verify_terminal(memory, memory.repo, memory.head, expected_terminal,
                                    expected_claim, ci._cache(private, "lost-ack-observation"), token, deadline)
                            assert view["writer_acknowledgment"] == "not_established" and view["observation_only"] is True
                            assert (private / "remote-terminal-receipt.json").read_bytes() == held
                assert len(transport.children) == (0 if fault == "remote_no_replay" else 1)
                assert server.commits == (["admission"] if fault == "cleanup" else ["admission", "output"]
                    if fault == "lost_output" else ["admission", "output", "terminal"])

        # Old schemas/paths/control values remain exact. Each prior adapter
        # still refuses the consumed chain before a child or deadline can start.
        for ordinal, adapter, namespace in ((0, ci, "retention-first-cell"), (1, fresh, "retention-task4-fresh-r1")):
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
                expected_reason = "terminal_or_claim_missing" if ordinal == 0 else "fresh_predecessor_head_mismatch"
                with pytest.raises(ci.RetentionCIRefused, match="^retention_claim_unresolved:" + expected_reason + "$"):
                    controller.execute_first_cell(old_request, host_state=old_host,
                        grant=ci.ExecutionGrantRequest(SOURCE, owned._digest(old_document), archive),
                        _test_transport=old_child, _test_api=consumed)
                assert old_child.children == [] and consumed.commits == [] and not (old_host / "deadline").exists()
        assert all(api.trees[revision] == tree for revision, tree in seed.trees.items())
        assert effects == [] and base.PRIVATE.decode() not in capsys.readouterr().out
    print(json.dumps({"scope": "synthetic_task4_fresh_r2_only", "predecessor_cases": len(cases),
        "route": "failed_predecessor_claim_child_output_terminal", "old_schema_and_pins_checked": True,
        "no_replay_or_adoption": True, "inference_launched": False, "grading_launched": False}, sort_keys=True))
