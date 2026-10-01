"""One fixed successor, real predicates and synthetic byte/transport boundaries."""

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import codex_retention_task4_fresh_r1 as fresh
import gpt54_disposable_checkout as checkout
import gpt54_prepared_input_attestation as attester
from core.needs_files import NeedsFilesManifest
from core.result_fingerprint import inference_result_fingerprint
from . import test_gpt54_prepared_input_attestation as original_fixture
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN, offline  # noqa: F401
from .test_codex_retention_ci import Transport
from .test_codex_retention_result_intake import ResultHF, CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD

ci, controller, preparation, registration = fresh.ci, fresh.controller, fresh.preparation, fresh.registration
owned, retained, output, historical = fresh.owned, fresh.retained, fresh.output, fresh.historical
SOURCE, TREE = "a" * 40, "b" * 40
REAL_ROOT = fresh.ROOT
PRIVATE = b"SYNTHETIC fresh deliverable; never public logs\n"


def positive(stage, operation):
    try:
        return operation()
    except Exception as error:
        reason = str(error) if isinstance(error, (ci.RetentionCIRefused,
            controller.RetentionControllerRefused, preparation.RetentionPreparationRefused,
            registration.RetentionRegistrationRefused,
            output.OutputPublicationRefused)) else ""
        if re.fullmatch(r"[a-zA-Z0-9_:.]+", reason or "") is None:
            reason = type(error).__name__
        trace = error.__traceback__
        while trace.tb_next:
            trace = trace.tb_next
        pytest.fail(stage + ":" + reason + ":" + trace.tb_frame.f_code.co_name, pytrace=False)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def _originals(tmp_path, monkeypatch):
    """Change synthetic input pins at loading seams, never a validation verdict."""
    load = registration.load_plan
    registered = load(registration.ROOT / registration.REGISTRATION)
    real_manifest_loader = NeedsFilesManifest.__dict__["load"]
    with redirect_stdout(io.StringIO()):
        inputs, captures, _, _, references = original_fixture._fixture(tmp_path, monkeypatch, "valid")
    monkeypatch.setattr(NeedsFilesManifest, "load", real_manifest_loader)
    catalog, catalog_digest = attester.load_task_catalog(), attester.catalog_sha256()
    profile = inputs["manifest"]

    def fixture_plan(path):
        if Path(path).as_posix().endswith("/" + registration.ORIGINAL_PROFILE):
            return deepcopy(profile)
        if Path(path).as_posix().endswith("/" + registration.REGISTRATION):
            return deepcopy(registered)
        return load(path)

    for module in (registration, preparation):
        monkeypatch.setattr(module, "load_plan", fixture_plan)
        monkeypatch.setattr(module, "load_task_catalog", lambda *args, **kwargs: catalog)
        monkeypatch.setattr(module, "catalog_sha256", lambda *args, **kwargs: catalog_digest)
    registered["inputs"] = registration._inputs()
    manifest = tmp_path / "canonical-step0-manifest.json"
    snapshot = SimpleNamespace(shared_binding={"dataset": {
        "parquet": owned._identity(inputs["dataset_parquet"].read_bytes())}}, references=references)
    roles = preparation._file_identities(snapshot, manifest.read_bytes())
    monkeypatch.setattr(preparation, "ORIGINAL_INPUT_ROLES_SHA256", owned._digest(roles))
    run = next(item for item in inputs["runs"] if item.prepared_tasks is not None)
    return inputs, captures, run, manifest, roles


def _source_tree(destination):
    # Exact controller/admission/grader closure only. No Git worktree, private
    # input tree, native state, or installed package is copied.
    roles = {*controller.SOURCE_PATHS, *preparation.SOURCE_PATHS, *ci.SOURCE_PATHS, fresh.FACADE,
        "batch-runner/step8_grade.py", "batch-runner/schemas/grade.schema.json",
        "batch-runner/requirements.txt", "batch-runner/requirements-renderer.txt",
        "batch-runner/scripts/download_inference_from_hf.py", "batch-runner/prompts/grader_judge.md",
        "batch-runner/prompts/grader_judge_v2.md"}
    roles.update(path.relative_to(REAL_ROOT).as_posix() for path in (REAL_ROOT / "batch-runner/core").rglob("*.py"))
    for role in sorted(roles):
        _write(destination / role, preparation._read(REAL_ROOT / role, "synthetic_source_copy"))
    (destination / "batch-runner/workspace").mkdir(exist_ok=True)
    (destination / "data").mkdir(exist_ok=True)


def _runtime(monkeypatch, root):
    for module in (fresh, ci, controller, preparation):
        monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(preparation, "OUTPUT_SCOPE", root / "batch-runner/workspace")
    monkeypatch.setattr(controller, "WORKSPACE_DIR", root / "batch-runner/workspace")
    monkeypatch.setattr(controller, "DEFAULT_LOCAL_PATH", root / "data/gdpval-local")
    monkeypatch.setattr(controller, "PREPARED", root / owned.PREPARED)
    monkeypatch.setattr(controller, "MANIFEST", root / controller.STEP0_MANIFEST_PATH)


def _environment(monkeypatch, host_parent):
    values = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": SOURCE,
        "RETENTION_WORKFLOW_SHA": SOURCE, "GITHUB_RUN_ID": "700000001", "GITHUB_JOB": ci.EXECUTE_JOB,
        "RUNNER_OS": "Linux", "ImageOS": "ubuntu22", "RUNNER_NAME": "retention-synthetic-runner",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + ci.WORKFLOW + "@refs/heads/main",
        "CODEX_FOUNDRY_CONNECTION_CONFIRMED": "1", "AZURE_AI_ROUTE_PROFILE": "direct-v1",
        "FOUNDRY_PROJECT_ENDPOINT": "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/api/projects/synthetic",
        "HF_TOKEN": TOKEN, "GITHUB_TOKEN": "synthetic-not-a-credential",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "synthetic-never-passed-to-child",
        "ACTIONS_ID_TOKEN_REQUEST_URL": "https://pipelines.actions.githubusercontent.com/00000000-0000-4000-8000-000000000001"
            "/_apis/distributedtask/hubs/build/plans/00000000-0000-4000-8000-000000000002"
            "/jobs/00000000-0000-4000-8000-000000000003/idtoken?api-version=2.0",
        "GDPVAL_CODEX_RUN_ROOT": str(host_parent / "agent-native"), "TMPDIR": str(host_parent / "agent-temp"),
        "GDPVAL_DEV_HOST_MARKER": str(host_parent / "synthetic-ordinary-host-no-marker")}
    for index, role in enumerate(("CLIENT", "TENANT", "SUBSCRIPTION"), 1):
        values["AZURE_AI_EXPECTED_" + role + "_ID"] = f"0000000{index}-0000-4000-8000-00000000000{index}"
    for name, value in values.items():
        monkeypatch.setenv(name, value)


class FreshTransport(Transport):
    def owned_process(self, command, **options):
        assert self.api.commits == ["admission"]
        assert command == [sys.executable, "step2_run_inference.py", "--condition", "condition_a",
                           "--codex-deadline-state", str(options["ownership"][0].parent / "deadline")]
        assert options["cwd"] == controller.ROOT / "batch-runner" and options["timeout"] == 10860
        assert not {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "PYTHONPATH", "PYTHONHOME",
                    "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL"} & options["env"].keys()
        cell = controller._adapted_cell(registration.compile_plan()["cells"][1])
        prepared = controller.read_codex_prepared(controller.PREPARED)
        assert prepared["execution"]["codex"]["task_deadline"] == cell["control"] == {
            "condition": "retention_bundle_v1", "retention_bundle": "fresh", "repetition": 1}
        assert options["env"]["GDPVAL_RELAY_LINEAGE_ID"] == cell["run_id"]
        self.children.append(tuple(command))
        self.api.events.append("child")
        path, binding = options["ownership"]
        assert binding["cell_id"] == fresh.CELL_ID
        if self.mode == "cleanup":
            owned._save(path, {**owned._owner_state(binding["plan_sha256"]), **binding,
                "phase": "running", "pid": 4242, "tree_reaped": False, "owner_reaped": False})
            raise owned.OwnedChildCleanupRefused("owned_child_cleanup_unconfirmed")
        owned._save(path, {**owned._owner_state(binding["plan_sha256"]), **binding,
            "phase": "reaped", "pid": 4242, "tree_reaped": True, "owner_reaped": True, "exit_code": 0})
        name = "deliverable_files/" + cell["task_id"] + "/report.txt"
        ledger = {column: None for column in output._CALL_COLUMNS}
        ledger.update(record_type="call", call_id="synthetic-fresh-call", run_id=cell["run_id"],
            task_id=cell["task_id"], stage="generation", retry_kind="none", state="settled",
            missing_reasons=["price_missing"])
        ledger_bytes = (json.dumps(ledger) + "\n").encode()
        payload = {"run_id": cell["run_id"], "experiment_id": cell["run_id"], "condition_identity": "condition_a",
            "execution_mode": "codex_foundry", "ordered_task_ids": [cell["task_id"]], "model": "gpt-5.4",
            "source": registration.compile_plan()["inputs"]["repo_id"], "publication_generation": cell["run_id"],
            "prepared_fingerprint": prepared["prepared_fingerprint"], "results": [{
                "task_id": cell["task_id"], "status": "success", "model": "gpt-5.4", "usage": None,
                "content": PRIVATE.decode(), "deliverable_files": [name],
                "deliverable_file_records": [{"path": name, **owned._identity(PRIVATE)}]}],
            "cost_ledger": {"path": Path(owned.LEDGER).name, "sha256": owned._identity(ledger_bytes)["sha256"]}}
        payload["result_fingerprint"] = inference_result_fingerprint(payload)
        _write(controller.ROOT / "batch-runner/workspace/upload" / name, PRIVATE)
        _write(controller.ROOT / owned.LEDGER, ledger_bytes)
        _write(controller.ROOT / owned.RESULT, (json.dumps(payload, sort_keys=True) + "\n").encode())
        return subprocess.CompletedProcess(command, 0)


def test_task4_fresh_r1_has_one_bound_predecessor_and_owned_route(tmp_path, monkeypatch, capsys):
    production_plan = registration.compile_plan()
    pins = deepcopy(fresh.PREDECESSOR)
    assert pins == {"cell_id": controller.FIRST_CELL_ID,
        "producer_source_sha": "e355faf9a6212175a288e8473968915ffb2408d0", "run_id": "36696961231",
        "request_sha256": "ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68",
        "terminal_commit": "de50ff0aa6037c0ef6e3b713da519359abd1d08d",
        "terminal_identity": {"sha256": "0821af11393cab65d1e14259e43b14872b94a431496e8c1e3c38e719f33f21b8", "size": 6449},
        "claim_commit": "3fc283087a020caec574e8c9b8e9bc3ca593e88a",
        "output_commit": "43cbf8e265297813857172ecee51256cc17f2d36"}
    assert ci.source_identity()["files"]["batch-runner/codex_retention_ci.py"]["sha256"] == \
        "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c"
    import codex_retention_result_intake as reader
    assert reader.reader_identity() == {"module_sha256": "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196",
        "terminal_verifier_sha256": "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c"}
    assert [(binding.cell_id, binding.ordinal, binding.bundle) for binding in controller.CELL_BINDINGS] == [
        (production_plan["order"][0], 0, "keep"), (production_plan["order"][1], 1, "fresh")]
    assert fresh.SCOPE == {**ci.SCOPE, "cell_id": fresh.CELL_ID, "ordinal": 1, "retention_bundle": "fresh"}
    frozen = {name: (REAL_ROOT / name).read_bytes() for name in (
        "batch-runner/codex_retention_fixed_grade.py", "batch-runner/codex_retention_grade_readout.py",
        registration.REGISTRATION, "batch-runner/step2_run_inference.py", "batch-runner/core/codex_runner.py")}
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        pytest.fail("successor crossed an unapproved process/model/grader boundary", pytrace=False)

    for name in ("core.executor.TaskExecutor.__init__", "step8_grade.main", "step8_grade.RubricLoader.load",
                 "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset"):
        monkeypatch.setattr(name, forbidden)
    inputs, captures, original_run, manifest, roles = positive("synthetic_original_serializer",
        lambda: _originals(tmp_path, monkeypatch))
    plan = positive("real_registered_synthetic_input_bindings", registration.compile_plan)
    source_root = tmp_path / "runtime-source"
    positive("source_fixture", lambda: _source_tree(source_root))
    common = tmp_path / "git-metadata"
    common.mkdir()
    archive = tmp_path / "historical-observer"
    archive_buffer = io.BytesIO()
    archive_manifest = registration.load_plan(registration.ROOT / registration.ORIGINAL_PROFILE)
    with tarfile.open(fileobj=archive_buffer, mode="w", format=tarfile.PAX_FORMAT,
                      pax_headers={"comment": historical.SOURCE}) as tar:
        data = owned._canonical_json(archive_manifest).encode()
        member = tarfile.TarInfo(historical.MANIFEST_PATH)
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    git_state = {"head": SOURCE, "dirty": b""}
    old_cells = [{"cell_id": "synthetic-original-" + str(index), "index": index} for index in range(29)]
    old_cells.append({"cell_id": historical.FINAL_CELL, "index": 29})
    observer_response = {"format": historical.FORMAT, "observer_source_sha": historical.SOURCE,
        "producer_source_sha": historical.PRODUCER,
        "plan": {"reviewed_source_sha": historical.PRODUCER, "run_id": "budget_pilot_ci_20260925_04",
            "cells": old_cells, "order": [cell["cell_id"] for cell in old_cells], "launch_authorized_by_plan": False},
        "inputs": {"files_sha256": owned._digest(roles), "source_projection_sha256": captures[0]["ordered_source_projection_sha256"]}}

    def git(path, *command, ok=(0,)):
        if command == ("archive", "--format=tar", historical.SOURCE, "batch-runner", ".github/workflows"):
            assert path == historical.ROOT
            return SimpleNamespace(stdout=archive_buffer.getvalue(), returncode=0)
        assert Path(path) == ci.ROOT
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(path) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (git_state["head"] + "\n").encode(),
            ("rev-parse", "HEAD^{tree}"): (TREE + "\n").encode(),
            ("status", "--porcelain", "--untracked-files=normal"): git_state["dirty"],
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
        return SimpleNamespace(stdout=retained._encoded(observer_response), stderr=b"", returncode=0)

    # Both defining-module Git lookups and the historical child return raw
    # synthetic external bytes. Archive/observer/source validators remain real.
    monkeypatch.setattr(owned, "_git", git)
    monkeypatch.setattr(checkout, "_git", git)
    monkeypatch.setattr(subprocess, "run", metadata_process)
    positive("historical_archive_transport", lambda: historical.materialize_archive(archive))
    _write(archive / preparation.CONFIG_PATH, original_run.generated_config.read_bytes())
    _write(archive / preparation.PREPARED_PATH, original_run.prepared_tasks.read_bytes())
    sources = preparation.PreparedInputs(archive, inputs["dataset_parquet"], inputs["reference_root"], manifest)
    host_parent = Path(tempfile.mkdtemp(prefix=".retention-fresh-offline-", dir=REAL_ROOT.parent))
    _environment(monkeypatch, host_parent)
    _runtime(monkeypatch, source_root)
    request = controller.Request(fresh.CELL_ID, sources, source_root / fresh.PACKET_ROLE, source_root,
        preparation.source_identity()["sha256"], controller.source_identity()["sha256"], plan)
    packet = positive("fresh_packet", lambda: preparation.prepare_packet(cell_id=request.cell_id, sources=sources,
        output=request.packet, expected_preparer_sha256=request.expected_preparer_sha256, plan=plan))
    stage = positive("fresh_stage", lambda: controller.stage_runtime(request))
    assert controller.verify_staged_runtime(request) == stage
    assert stage["ordinal"] == 1 and stage["cell_id"] == fresh.CELL_ID and stage["commands"] == []
    assert not stage["launch_authorized"] and not stage["inference_slot_reserved"] and not stage["deadline_started"]
    assert stage["config_sha256"] == plan["cells"][1]["config_sha256"]
    assert (request.packet / preparation.INFERENCE).read_bytes() == controller._encoded(plan["cells"][1]["config"])
    assert stage["input_roles_sha256"] == packet["input_verification"]["original_input_roles_sha256"] == owned._digest(roles)
    assert controller._stage_paths(fresh.CELL_ID) == tuple(source_root / "batch-runner/workspace" / name for name in (
        "retention-task4-fresh-r1-staging.json", "retention-task4-fresh-r1-staged.json"))
    assert not any(path.exists() for path in controller._stage_paths(controller.FIRST_CELL_ID))
    with pytest.raises(controller.RetentionControllerRefused, match="^runtime_path_already_used_or_partial$"):
        controller.stage_runtime(request)
    document, observation = positive("source_originals_and_successor_request", lambda: fresh.canonical_request(request,
        reviewed_source_sha=SOURCE, run_id="700000001", historical_root=archive))
    assert document["serial_domain"]["predecessor"] == pins and document["source"]["successor_adapter"] == fresh.source_identity()
    assert observation == observer_response and document["stage_sha256"] == owned._digest(stage)
    assert document["grading"]["materialized_grader_source_sha256"] == packet["grading"]["materialized_grader_source_sha256"]
    # Inert actual-script route and ordinal-zero delegation keep distinct scope.
    for cell, scope in ((fresh.CELL_ID, fresh.SCOPE), (controller.FIRST_CELL_ID, ci.SCOPE)):
        with monkeypatch.context() as script:
            script.setattr(sys, "argv", [str(REAL_ROOT / fresh.FACADE), "--cell", cell, "--reviewed-source-sha", SOURCE])
            with pytest.raises(SystemExit) as stopped:
                runpy.run_path(str(REAL_ROOT / fresh.FACADE), run_name="__main__")
            assert stopped.value.code == 0
        receipt = json.loads(capsys.readouterr().out)
        assert receipt["mode"] == "plan_only" and receipt["scope"] == scope and receipt["commands"] == []
    assert fresh.main(["--cell", fresh.CELL_ID, "--reviewed-source-sha", SOURCE, "--observe-locator"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "fresh_locator_observation_not_supported"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    predecessor_fixture = ResultHF(production_plan)
    seed = MemoryHF()
    seed.trees, seed.writers, seed.parents = (deepcopy(getattr(predecessor_fixture, name)) for name in ("trees", "writers", "parents"))
    seed.head = TERMINAL_HEAD
    # The old-pilot terminal may be inherited, but it was not written at this
    # consumed keep/r1 parent. Its history must refuse an ordinal-zero replay.
    old_terminal_path = retained._paths(old_cells[-1])[1]
    for revision in seed.trees:
        seed.trees[revision][old_terminal_path] = b"{}\n"
        seed.writers[revision][old_terminal_path] = "3" * 40
    synthetic_pins = {**pins, "terminal_commit": TERMINAL_HEAD, "claim_commit": CLAIM_HEAD,
        "output_commit": OUTPUT_HEAD, "terminal_identity": owned._identity(seed.trees[TERMINAL_HEAD][ci.TERMINAL])}
    monkeypatch.setattr(fresh, "PREDECESSOR", synthetic_pins)
    document, observation = fresh.canonical_request(request, reviewed_source_sha=SOURCE,
        run_id="700000001", historical_root=archive)
    grant = ci.ExecutionGrantRequest(SOURCE, owned._digest(document), archive)
    api = deepcopy(seed)
    transport = FreshTransport(document, api, key)
    denied = host_parent / "not-admitted"
    for wrong in ("unregistered", plan["order"][2], plan["order"][4]):
        with pytest.raises(controller.RetentionControllerRefused, match="^only_first_or_task4_fresh_r1_supported$"):
            controller.execute_first_cell(replace(request, cell_id=wrong), host_state=denied, grant=grant)
    with pytest.raises(preparation.RetentionPreparationRefused, match="^emitted_config_or_task_bytes_mismatch$"):
        controller.execute_first_cell(replace(request, cell_id=controller.FIRST_CELL_ID), host_state=denied, grant=grant)
    with pytest.raises(controller.RetentionControllerRefused, match="^controller_source_mismatch$"):
        controller.execute_first_cell(replace(request, expected_controller_sha256="0" * 64),
                                      host_state=denied, grant=grant)
    changed_plan = deepcopy(plan)
    changed_plan["cells"][1]["index"] = 0
    with pytest.raises(registration.RetentionRegistrationRefused, match="^compiled_plan_mismatch$"):
        controller.execute_first_cell(replace(request, plan=changed_plan), host_state=denied, grant=grant)
    for changed in (replace(grant, reviewed_source_sha="f" * 40), replace(grant, request_sha256="0" * 64)):
        with pytest.raises(ci.RetentionCIRefused):
            fresh.execute(request, host_state=denied, grant=changed, _test_transport=transport, _test_api=api)
    with monkeypatch.context() as wrong_run:
        wrong_run.setenv("GITHUB_RUN_ID", "700000002")
        with pytest.raises(ci.RetentionCIRefused, match="^approved_retention_request_changed$"):
            fresh.execute(request, host_state=denied, grant=grant, _test_transport=transport, _test_api=api)
    for admission, selected in ((ci._Admission, fresh.CELL_ID), (fresh._FreshAdmission, controller.FIRST_CELL_ID)):
        crossed = replace(request, cell_id=selected)
        candidate = admission(crossed, document, observation, {}, transport, api)
        with pytest.raises(controller.RetentionControllerRefused, match="^retention_execution_grant_required$"):
            controller._run_post_authority_cell(crossed, host_state=denied, _admission=candidate)
    assert not denied.exists() and api.calls == [] and transport.children == [] and transport.github_calls == 0
    bad_approval = FreshTransport(document, deepcopy(seed), key)
    bad_approval.provider[2][0]["comment"] = ci.APPROVAL_PREFIX + "0" * 64
    with pytest.raises(ci.RetentionCIRefused, match="^owner_environment_request_approval_mismatch$"):
        fresh.execute(request, host_state=denied, grant=grant, _test_transport=bad_approval, _test_api=bad_approval.api)
    assert not denied.exists() and bad_approval.api.calls == [] and bad_approval.children == []
    # Every negative starts from its own synthetic immutable server. No claim
    # is reset or adopted; no failed case runs a child or starts a deadline.
    cases = {"head": "fresh_predecessor_head_mismatch", "terminal_hash": "payload_identity_mismatch",
        "producer": "retention_completion_mismatch", "run": "fresh_predecessor_links_mismatch",
        "claim": "fresh_predecessor_links_mismatch", "cell": "retention_terminal_expectation_refused",
        "namespace": "retention_namespace_already_used", "lost_claim": "hf_transport_failed"}
    for fault in cases:
        server = deepcopy(seed)
        changed = deepcopy(synthetic_pins)
        if fault == "head":
            server.head = OUTPUT_HEAD
        elif fault == "terminal_hash":
            changed["terminal_identity"]["sha256"] = "0" * 64
        elif fault == "producer":
            changed["producer_source_sha"] = "0" * 40
        elif fault == "run":
            changed["run_id"] = "700000009"
        elif fault == "claim":
            changed["claim_commit"] = "0" * 40
        elif fault == "cell":
            changed["cell_id"] = fresh.CELL_ID
        elif fault == "namespace":
            server.trees[server.head][fresh.CLAIM] = b"already used"
            server.writers[server.head][fresh.CLAIM] = server.head
        elif fault == "lost_claim":
            server.lost = "admission"
        candidate = FreshTransport(document, server, key)
        authority = ci.verify_approval(document, candidate)
        admission = fresh._FreshAdmission(request, document, observation, authority, candidate, server)
        host = host_parent / ("refused-" + fault)
        host.mkdir(mode=0o700)
        with monkeypatch.context() as expected:
            expected.setattr(fresh, "PREDECESSOR", changed)
            with pytest.raises(ci.RetentionCIRefused, match="^retention_claim_unresolved:"):
                admission.admit(host)
        refusal = retained._read(host / "remote-admission-receipt.json")
        assert refusal["outcome"] == "unresolved" and refusal["reason"] == cases[fault]
        assert candidate.children == [] and not (host / "deadline").exists()
        assert server.commits == (["admission"] if fault == "lost_claim" else [])
    snapshot = tmp_path / "staged-snapshot"
    shutil.copytree(source_root, snapshot)
    state = positive("claim_owned_child_and_publication", lambda: controller.execute_first_cell(request,
        host_state=host_parent / "completed", grant=grant, _test_transport=transport, _test_api=api))
    assert state == {"cell_id": fresh.CELL_ID, "status": "succeeded", "request_sha256": grant.request_sha256,
        "cleanup_confirmed": True, "remote_terminal": "acknowledged", "grade": None,
        "grading_launched": False, "invoice_complete": False}
    assert api.events == ["admission", "child", "output", "terminal"]
    assert api.parents[api.parents[api.parents[api.head]]] == TERMINAL_HEAD
    host = host_parent / "completed"
    expected_terminal = retained._read(host / "remote-terminal-expected.json")
    claim_receipt = retained._read(host / "remote-admission-receipt.json")
    assert expected_terminal["completion"]["format"] == fresh.OUTPUT_FORMAT
    assert expected_terminal["completion"]["receipt"] is None and expected_terminal["completion"]["grade"] is None
    with pytest.raises(controller.RetentionControllerRefused, match="^first_cell_already_reserved_or_partial_no_replay$"):
        fresh.execute(request, host_state=host, grant=grant, _test_transport=transport, _test_api=api)
    assert api.commits == ["admission", "output", "terminal"] and len(transport.children) == 1
    frozen_receipt = (host / "remote-terminal-receipt.json").read_bytes()
    with retained._session(api) as (server, token, deadline):
        reconciled = positive("immutable_successor_reconciliation", lambda: fresh.verify_terminal(server, server.repo,
            server.head, expected_terminal, claim_receipt["claim"], ci._cache(host, "independent-read"), token, deadline))
    assert reconciled["writer_acknowledgment"] == "not_established" and reconciled["replay_authorized"] is False
    assert (host / "remote-terminal-receipt.json").read_bytes() == frozen_receipt
    duplicate = fresh._FreshAdmission(request, document, observation, claim_receipt["claim"]["authority"], transport, api)
    duplicate.receipt = claim_receipt
    with pytest.raises(FileExistsError):
        duplicate.finish(host, owned._load(host / "cell.json"))
    assert api.commits == ["admission", "output", "terminal"]
    with retained._session(api) as (server, token, deadline):
        for fault in ("cell", "role"):
            malformed = deepcopy(expected_terminal)
            if fault == "cell":
                malformed["completion"]["cell_id"] = controller.FIRST_CELL_ID
            else:
                malformed["completion"]["files"][0]["path"] = "private/native.sqlite"
            calls = list(server.calls)
            with pytest.raises((ci.RetentionCIRefused, ValueError)):
                fresh.verify_terminal(server, server.repo, server.head, malformed, claim_receipt["claim"],
                    ci._cache(host, "refused-reconciliation-" + fault), token, deadline)
            assert server.calls == calls
    # Separate owned runtime copies for ambiguous output/terminal responses and
    # unconfirmed child cleanup. Never reuse a consumed local or remote slot.
    for fault in ("lost_output", "lost_terminal", "cleanup"):
        root = tmp_path / fault
        shutil.copytree(snapshot, root)
        with monkeypatch.context() as local:
            _runtime(local, root)
            selected = replace(request, packet=root / fresh.PACKET_ROLE, runtime_checkout=root)
            current, observed = fresh.canonical_request(selected, reviewed_source_sha=SOURCE,
                run_id="700000001", historical_root=archive)
            assert current == document
            server = deepcopy(seed)
            server.lost = "output" if fault == "lost_output" else "terminal" if fault == "lost_terminal" else None
            child = FreshTransport(current, server, key, mode="cleanup" if fault == "cleanup" else "ordinary")
            private = host_parent / fault
            expected_error = owned.OwnedChildCleanupRefused if fault == "cleanup" else ci.RetentionCIRefused
            with pytest.raises(expected_error):
                fresh.execute(selected, host_state=private, grant=grant, _test_transport=child, _test_api=server)
            assert len(child.children) == 1
            assert server.commits == (["admission"] if fault == "cleanup" else ["admission", "output"] if
                fault == "lost_output" else ["admission", "output", "terminal"])
            if fault == "cleanup":
                assert not (private / "remote-terminal-reserved.json").exists()
                assert owned._load(private / "owned-child.json")["phase"] == "running"
            else:
                failed = retained._read(private / "remote-terminal-receipt.json")
                assert failed["outcome"] == "unresolved" and failed["reason"] == "hf_transport_failed"
                if fault == "lost_terminal":
                    held = (private / "remote-terminal-receipt.json").read_bytes()
                    terminal = retained._read(private / "remote-terminal-expected.json")
                    claim = retained._read(private / "remote-admission-receipt.json")["claim"]
                    with retained._session(server) as (memory, token, deadline):
                        view = fresh.verify_terminal(memory, memory.repo, memory.head, terminal, claim,
                            ci._cache(private, "lost-ack-observation"), token, deadline)
                    assert view["writer_acknowledgment"] == "not_established" and view["observation_only"] is True
                    assert (private / "remote-terminal-receipt.json").read_bytes() == held
    # Ordinal zero still stages exactly its original control/schema/local names.
    first_root = tmp_path / "first-runtime"
    _source_tree(first_root)
    with monkeypatch.context() as first:
        _runtime(first, first_root)
        first_request = replace(request, cell_id=controller.FIRST_CELL_ID, packet=first_root / ci.PACKET_ROLE,
                                runtime_checkout=first_root)
        preparation.prepare_packet(cell_id=first_request.cell_id, sources=sources, output=first_request.packet,
            expected_preparer_sha256=first_request.expected_preparer_sha256, plan=plan)
        first_stage = controller.stage_runtime(first_request)
        assert first_stage["format"] == "codex-retention-first-cell-v1" and first_stage["ordinal"] == 0
        assert controller.read_codex_prepared(controller.PREPARED)["execution"]["codex"]["task_deadline"] == plan["cells"][0]["control"]
        assert controller._stage_paths(controller.FIRST_CELL_ID) == tuple(first_root / "batch-runner/workspace" / name
            for name in ("retention-first-cell-staging.json", "retention-first-cell-staged.json"))
        first_document, _ = ci.canonical_request(first_request, reviewed_source_sha=SOURCE,
            run_id="700000001", historical_root=archive)
        assert first_document["format"] == ci.REQUEST_FORMAT and first_document["scope"] == ci.SCOPE
        assert "successor_adapter" not in first_document["source"] and first_document["serial_domain"]["prefix"] == ci.PREFIX
        consumed_server = deepcopy(seed)
        first_transport = Transport(first_document, consumed_server, key)
        consumed_host = host_parent / "consumed-first-cell-refused"
        with pytest.raises(ci.RetentionCIRefused, match="^retention_claim_unresolved:retention_control_history_mismatch$"):
            controller.execute_first_cell(first_request, host_state=consumed_host,
                grant=ci.ExecutionGrantRequest(SOURCE, owned._digest(first_document), archive),
                _test_transport=first_transport, _test_api=consumed_server)
        assert first_transport.children == [] and consumed_server.commits == []
        assert not (consumed_host / "deadline").exists()
    for revision, tree in seed.trees.items():
        assert api.trees[revision] == tree
    assert all((REAL_ROOT / name).read_bytes() == data for name, data in frozen.items())
    assert effects == [] and PRIVATE.decode() not in capsys.readouterr().out
    print(json.dumps({"scope": "synthetic_task4_fresh_r1_only", "predecessor_cases": len(cases),
        "ordinary_route": "admission_child_output_terminal", "lost_ack_is_not_writer_ack": True,
        "inference_launched": False, "grading_launched": False, "invoice_complete": False}, sort_keys=True))
