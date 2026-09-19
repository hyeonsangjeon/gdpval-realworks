"""One free selector: five-row snapshots, real producers/helpers, no execution."""

import hashlib
import json
import os
import shutil
import socket
import stat
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import gpt54_comparison_preflight as preflight
import gpt54_prepared_input_attestation as attester
import step1_prepare_tasks as step1
import step8_grade as grading
from core.agentic_v2_manifest_binding import bind_stage, binding_record
from core.codex_runtime_config import CodexProviderSettings
from core.needs_files import NeedsFilesManifest, resolve_needs_files
from core.prepared_fingerprint import prepared_fingerprint
from core.source_identity import (
    SOURCE_PROJECTION_FIELDS, ordered_source_projection_sha256, source_task_projection,
    source_task_projection_sha256,
)


def _json(value):
    return preflight._canonical_json(value).encode("utf-8")


def _identity(data):
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def _write(path, value):
    path.write_bytes(_json(value) + b"\n")


def _fixture(tmp_path, monkeypatch, case):
    """Use synthetic data pins only; production has no bypass or pin override.

    Real catalog selection supplies the five prompts/taxonomies/reference paths.
    Rubrics and reference contents are deliberately tiny synthetic bytes. Only
    trusted catalog/envelope loading seams are replaced, never a validator,
    fingerprint, binding helper, compiler, source hash or reference reader.
    """
    read_plan = preflight.load_plan
    manifest = json.loads(json.dumps(read_plan()))
    catalog = preflight.load_task_catalog()
    task_ids = preflight.select_advance_check_tasks(catalog).task_ids
    by_id = catalog.by_task_id()
    previous = json.loads((preflight.ROOT / "batch-runner/tests/fixtures/run_record/step1_tasks_prepared.json").read_text())
    assert [row["task_id"] for row in previous["tasks"]] == list(task_ids)
    rows = []
    reference_root = tmp_path / "references"
    reference_root.mkdir()
    records = {}
    for index, task in enumerate(previous["tasks"]):
        files = task["reference_files"]
        for name in files:
            path = reference_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"small offline reference {index}\n".encode())
            records[name] = _identity(path.read_bytes())
        rows.append({
            "task_id": task["task_id"], "prompt": task["instruction"],
            "sector": task["sector"], "occupation": task["occupation"],
            "rubric_json": '[\n  {"criterion": "fixture only — not a grading result"}\n]\n',
            "rubric_pretty": "Fixture rubric only.\nPreserve these bytes.\n",
            "reference_files": files, "reference_file_urls": task["reference_file_urls"],
            "reference_file_hf_uris": [f"hf://datasets/openai/gdpval@{catalog.dataset_revision}/{name}" for name in files],
            "deliverable_files": ["withheld-gold-answer"] if by_id[task["task_id"]].deliverable_file_extensions else [],
        })
    parquet_rows = json.loads(json.dumps(rows))
    if case == "parquet_missing_task":
        parquet_rows.pop()
    elif case == "parquet_duplicate_task":
        parquet_rows.append(parquet_rows[0])
    elif case in {"parquet_prompt", "parquet_taxonomy", "parquet_rubric", "parquet_rubric_json", "parquet_reference"}:
        field = {
            "parquet_prompt": "prompt", "parquet_taxonomy": "occupation",
            "parquet_rubric": "rubric_pretty", "parquet_rubric_json": "rubric_json",
            "parquet_reference": "reference_files",
        }[case]
        parquet_rows[0][field] = ["reference_files/other.txt"] if field == "reference_files" else "changed"
    dataset = tmp_path / "source.parquet"
    # Deliberately reversed physical order: the real cohort selector orders it.
    pq.write_table(pa.Table.from_pylist(list(reversed(parquet_rows))), dataset)
    dataset_identity = _identity(dataset.read_bytes())
    if case != "production_pins_reject_fixture":
        catalog = replace(
            catalog, tasks=tuple(by_id[task_id] for task_id in task_ids),
            dataset_file_sha256=dataset_identity["sha256"],
        )
        catalog_digest = _identity(_json(asdict(catalog)))["sha256"]
        versions = {catalog.dataset_repo_id + "@" + catalog.dataset_revision: dataset_identity["sha256"],
                    **{name: record["sha256"] for name, record in records.items()}}
        envelope_path = preflight.ROOT / preflight.ENVELOPE / "advance_check_plan.yaml"
        envelope = read_plan(envelope_path)
        envelope["model_run_conditions"]["shared"]["input_file_versions"] = versions

        def fixture_plan(path=preflight.PLAN):
            return envelope if path == envelope_path else read_plan(path)

        monkeypatch.setattr(preflight, "load_plan", fixture_plan)
        for module in (preflight, attester):
            monkeypatch.setattr(module, "load_task_catalog", lambda: catalog)
            monkeypatch.setattr(module, "catalog_sha256", lambda: catalog_digest)
        manifest["shared"]["dataset"].update(
            parquet_sha256=dataset_identity["sha256"], catalog_sha256=catalog_digest,
            input_file_versions=versions,
        )
        for condition in manifest["conditions"].values():
            condition["controls"] = manifest["shared"]
    else:
        catalog_digest = preflight.catalog_sha256()
    plan = preflight.compile_grading_plan(manifest)
    projections = [source_task_projection(**{key: row[key] for key in SOURCE_PROJECTION_FIELDS}) for row in rows]
    projection_hashes = [source_task_projection_sha256(**row) for row in projections]
    bound = bind_stage("advance_check_5", dataset_tasks=[SimpleNamespace(**row) for row in rows],
                       catalog=catalog, catalog_digest=catalog_digest)
    monkeypatch.setenv("NEEDS_FILES_POLICY", "deliverable_only")
    needs = NeedsFilesManifest({
        "_schema_version": 4, "_summary": {"active_policy": "deliverable_only"},
        "tasks": {row["task_id"]: {
            "needs_files": resolve_needs_files(bool(row["deliverable_files"]), None, "deliverable_only"),
            "source_projection_sha256": digest,
        } for row, digest in zip(rows, projection_hashes)},
        "reference_files": records,
    })

    def dataset_loader(*, auto_download):
        assert auto_download is False
        return SimpleNamespace(load=lambda: [SimpleNamespace(**row) for row in reversed(rows)])

    monkeypatch.setattr(step1, "GDPValDataLoader", dataset_loader)
    monkeypatch.setattr(NeedsFilesManifest, "load", classmethod(lambda cls: needs))
    monkeypatch.setattr(step1, "resolve_publication_generation", lambda experiment: "offline-fixture." + experiment)
    run_inputs = []
    captures = []
    prepared = {}
    for run in plan.dispatch.runs:
        directory = tmp_path / run.run_id
        directory.mkdir()
        config_path = directory / "comparison-run.json"
        config_path.write_bytes(run.config_json.encode("utf-8"))
        prepared_path = None
        if run.condition == "codex":
            workspace = directory / "workspace"
            monkeypatch.setattr(step1, "WORKSPACE_DIR", workspace)
            # The real producer serializes conditions/execution/tasks and calls
            # the real fingerprint helper. Only its local data suppliers above
            # are fixtures; no Step 2, client, model or download is invoked.
            # This fixture supplies captures to the offline attester, including
            # deliberately invalid data. The new runtime writer has its own
            # direct Step 1/Step 2 selector; do not run it while assembling this
            # independent test oracle. Keep the real Step 1 serializer here.
            import gpt54_codex_input_capture as capture_runtime

            def store_prepared_fixture(_control, *, workspace, prepared_data, **_kwargs):
                (workspace / "step1_tasks_prepared.json").write_bytes(prepared_data)

            with monkeypatch.context() as setup:
                setup.setattr(capture_runtime, "write_codex_prepared_and_capture", store_prepared_fixture)
                payload = step1.prepare_tasks(str(config_path))
            prepared_path = workspace / "step1_tasks_prepared.json"
            prepared[run.run_id] = payload
            consumer = {
                "kind": "codex_step1_tasks", "prepared_fingerprint": payload["prepared_fingerprint"],
                "publication_generation": payload["publication_generation"],
                "prepared_file": _identity(prepared_path.read_bytes()), "tasks": payload["tasks"],
            }
        else:
            consumer = {
                "kind": "sandbox_v2_task_to_run", "manifest_binding": binding_record(bound),
                "tasks": [{
                    "task_id": task.task_id, "prompt": task.prompt,
                    "sector": task.sector, "occupation": task.occupation,
                    "reference_files": list(task.reference_files),
                    "reference_file_records": [{"path": name, **records[name]} for name in task.reference_files],
                } for task in bound.tasks],
            }
        capture = {
            "binding_version": "gpt54-pre-execution-input-v1", "run_id": run.run_id,
            "condition": run.condition, "repeat": run.repeat, "harness": run.harness,
            "provider": run.provider, "model": run.model, "reasoning_effort": run.reasoning_effort,
            "manifest_sha256": plan.dispatch.manifest_sha256,
            "combined_plan_sha256": _identity(plan.canonical_bytes())["sha256"],
            "source_pins_sha256": _identity(plan.dispatch.source_pins_json.encode())["sha256"],
            "config_sha256": _identity(config_path.read_bytes())["sha256"],
            "dataset": {"repo_id": catalog.dataset_repo_id, "revision": catalog.dataset_revision,
                        "catalog_sha256": catalog_digest, "parquet": dataset_identity},
            "task_ids": list(task_ids),
            "ordered_source_projection_sha256": ordered_source_projection_sha256(projection_hashes),
            "needs_files_policy": "deliverable_only", "consumer": consumer,
        }
        binding_path = directory / "pre-execution-input.json"
        _write(binding_path, capture)
        captures.append(capture)
        run_inputs.append(attester.PreparedRunInputs(run.run_id, config_path, binding_path, prepared_path))
    inputs = {
        "manifest": manifest, "combined_plan": plan.as_dict(), "dataset_parquet": dataset,
        "reference_root": reference_root, "runs": tuple(run_inputs),
    }
    return inputs, captures, prepared, projections, records


def _tree_snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        metadata = path.lstat()
        result[path.relative_to(root).as_posix()] = (
            metadata.st_mode, metadata.st_nlink,
            path.read_bytes() if stat.S_ISREG(metadata.st_mode) else
            os.readlink(path) if stat.S_ISLNK(metadata.st_mode) else None,
        )
    return result


@pytest.mark.parametrize("case", [
    "identical", "relocated", "production_pins_reject_fixture",
    "missing_pin", "changed_pin", "loader_pin", "control_drift", "combined_plan_drift", "launch_flag",
    "missing_run", "extra_run", "duplicate_run", "reordered_runs", "untyped_run",
    "config_bytes", "repeat_config_swap", "missing_capture", "capture_duplicate_key", "capture_null", "capture_nan",
    "capture_run", "capture_repeat", "capture_order", "capture_projection", "capture_dataset_revision",
    "capture_parquet_digest", "capture_config", "capture_plan", "capture_pins", "capture_verified", "capture_policy",
    "v2_prompt", "v2_metadata", "v2_reference", "v2_missing_task", "v2_duplicate_task", "v2_extra_task",
    "v2_manifest_binding", "v2_prepared_substitution", "codex_capture_prompt",
    "parquet_bytes", "parquet_symlink", "parquet_hardlink", "parquet_missing_task", "parquet_duplicate_task",
    "parquet_prompt", "parquet_taxonomy", "parquet_rubric", "parquet_rubric_json", "parquet_reference",
    "reference_bytes", "reference_missing", "reference_extra", "reference_extra_directory",
    "reference_symlink", "reference_hardlink", "reference_fifo", "reference_root_symlink", "reference_ancestor_symlink",
    "prepared_missing", "prepared_symlink", "prepared_hardlink", "prepared_fingerprint",
    "prepared_prompt_rehashed", "prepared_metadata", "prepared_source_projection", "prepared_url",
    "prepared_reference_path", "prepared_reference_hash", "prepared_reference_size", "prepared_reference_escape",
    "prepared_missing_task", "prepared_duplicate_task", "prepared_extra_task", "prepared_task_order",
    "prepared_needs_files", "prepared_count", "prepared_generation", "prepared_effort", "prepared_limit",
    "prepared_rubric_injection", "prepared_null_condition", "prepared_missing_config_path",
    "attestation_drift", "attestation_authorization", "attestation_noncanonical",
])
def test_prepared_input_attestation_binds_actual_bytes_without_execution(case, tmp_path, monkeypatch):
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("attestation attempted execution, network, authentication, client construction or writes")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(CodexProviderSettings, "auth_command", forbidden)
    monkeypatch.setattr("core.codex_runtime_config.AzureAIRouteSettings.from_env", forbidden)
    monkeypatch.setattr("core.agentic_v2_model_voice.AzureFoundryVoice.__post_init__", forbidden)
    monkeypatch.setattr("core.llm_client.create_typed_azure_client", forbidden)
    monkeypatch.setattr(grading.Grader, "__init__", forbidden)
    monkeypatch.setattr(grading.RubricLoader, "__init__", forbidden)
    monkeypatch.setattr(grading, "preflight_routes", forbidden)
    monkeypatch.setattr(grading, "open_cost_recorder", forbidden)
    monkeypatch.setattr("prepare_dataset.snapshot_download", forbidden)
    monkeypatch.setattr("prepare_dataset.load_dataset", forbidden)
    inputs, captures, prepared, projections, records = _fixture(tmp_path, monkeypatch, case)
    run_inputs = inputs["runs"]
    codex = run_inputs[1]
    reference_path = inputs["reference_root"] / next(iter(records))
    payload = prepared[codex.run_id]
    captured = captures[0]
    prepared_case = case.startswith("prepared_") and case not in {"prepared_missing", "prepared_symlink", "prepared_hardlink"}

    if case in {"missing_pin", "changed_pin", "loader_pin"}:
        source = "batch-runner/prepare_dataset.py" if case == "loader_pin" else "batch-runner/gpt54_prepared_input_attestation.py"
        if case == "missing_pin":
            inputs["manifest"]["source_pins"].pop(source)
        else:
            inputs["manifest"]["source_pins"][source] = "0" * 64
    elif case == "control_drift":
        inputs["manifest"]["shared"]["model"]["reasoning_effort"] = "high"
    elif case == "combined_plan_drift":
        inputs["combined_plan"]["grading_runs"][1]["task_ids"].reverse()
    elif case == "launch_flag":
        inputs["combined_plan"]["launch_allowed"] = True
    elif case == "missing_run":
        inputs["runs"] = run_inputs[:-1]
    elif case == "extra_run":
        inputs["runs"] += (run_inputs[0],)
    elif case == "duplicate_run":
        inputs["runs"] = (run_inputs[0], run_inputs[1], run_inputs[1], run_inputs[3])
    elif case == "reordered_runs":
        inputs["runs"] = tuple(reversed(run_inputs))
    elif case == "untyped_run":
        inputs["runs"] = (asdict(run_inputs[0]), *run_inputs[1:])
    elif case == "config_bytes":
        codex.generated_config.write_bytes(codex.generated_config.read_bytes() + b"\n")
    elif case == "repeat_config_swap":
        codex.generated_config.write_bytes(run_inputs[2].generated_config.read_bytes())
    elif case == "missing_capture":
        run_inputs[0].input_binding.unlink()
    elif case == "capture_duplicate_key":
        run_inputs[0].input_binding.write_bytes(b'{"binding_version":0,' + _json(captured)[1:])
    elif case == "capture_null":
        _write(run_inputs[0].input_binding, None)
    elif case == "capture_nan":
        run_inputs[0].input_binding.write_bytes(b'{"unused":NaN,' + _json(captured)[1:])
    elif case in {"capture_run", "capture_repeat", "capture_order", "capture_projection", "capture_dataset_revision",
                  "capture_parquet_digest", "capture_config", "capture_plan", "capture_pins", "capture_verified", "capture_policy"}:
        if case == "capture_run":
            captured["run_id"] = run_inputs[3].run_id
        elif case == "capture_repeat":
            captured["repeat"] = True
        elif case == "capture_order":
            captured["task_ids"].reverse()
        elif case == "capture_dataset_revision":
            captured["dataset"]["revision"] = inputs["manifest"]["base_sha"]
        elif case == "capture_parquet_digest":
            captured["dataset"]["parquet"]["sha256"] = inputs["manifest"]["base_sha"]
        elif case == "capture_verified":
            captured["verified"] = True
        elif case == "capture_policy":
            captured["needs_files_policy"] = "union"
        else:
            key = {"capture_projection": "ordered_source_projection_sha256", "capture_config": "config_sha256",
                   "capture_plan": "combined_plan_sha256", "capture_pins": "source_pins_sha256"}[case]
            captured[key] = "0" * 64
        _write(run_inputs[0].input_binding, captured)
    elif case.startswith("v2_") or case == "codex_capture_prompt":
        tasks = captured["consumer"]["tasks"]
        if case == "v2_prompt":
            tasks[0]["prompt"] += " "
        elif case == "v2_metadata":
            tasks[0]["sector"] = "changed"
        elif case == "v2_reference":
            next(row for row in tasks if row["reference_file_records"])["reference_file_records"][0]["sha256"] = "0" * 64
        elif case == "v2_missing_task":
            tasks.pop()
        elif case == "v2_duplicate_task":
            tasks[1] = tasks[0]
        elif case == "v2_extra_task":
            tasks.append(tasks[0])
        elif case == "v2_manifest_binding":
            captured["consumer"]["manifest_binding"]["binding_seal"] = "0" * 64
        elif case == "v2_prepared_substitution":
            inputs["runs"] = (replace(run_inputs[0], prepared_tasks=codex.prepared_tasks), *run_inputs[1:])
        else:
            captures[1]["consumer"]["tasks"][0]["instruction"] += " "
            _write(codex.input_binding, captures[1])
        _write(run_inputs[0].input_binding, captured)
    elif case == "parquet_bytes":
        inputs["dataset_parquet"].write_bytes(inputs["dataset_parquet"].read_bytes() + b"byte drift")
    elif case in {"parquet_symlink", "parquet_hardlink", "prepared_symlink", "prepared_hardlink"}:
        path = inputs["dataset_parquet"] if case.startswith("parquet") else codex.prepared_tasks
        other = tmp_path / "linked-input"
        if case.endswith("symlink"):
            path.rename(other)
            path.symlink_to(other)
        else:
            os.link(path, other)
    elif case == "reference_bytes":
        data = reference_path.read_bytes()
        reference_path.write_bytes(b"X" + data[1:])
    elif case == "reference_missing":
        reference_path.unlink()
    elif case == "reference_extra":
        (reference_path.parent / "extra.txt").write_bytes(b"extra")
    elif case == "reference_extra_directory":
        (reference_path.parent / "extra-task").mkdir()
    elif case in {"reference_symlink", "reference_hardlink", "reference_fifo"}:
        other = tmp_path / "linked-reference"
        if case == "reference_hardlink":
            os.link(reference_path, other)
        else:
            reference_path.rename(other)
            if case == "reference_symlink":
                reference_path.symlink_to(other)
            else:
                os.mkfifo(reference_path)
    elif case in {"reference_root_symlink", "reference_ancestor_symlink"}:
        path = inputs["reference_root"] if case == "reference_root_symlink" else reference_path.parent
        other = tmp_path / "linked-directory"
        path.rename(other)
        path.symlink_to(other, target_is_directory=True)
    elif case == "prepared_missing":
        inputs["runs"] = (run_inputs[0], replace(codex, prepared_tasks=None), *run_inputs[2:])
    elif prepared_case:
        task = payload["tasks"][0]
        if case == "prepared_prompt_rehashed":
            task["instruction"] += " "
        elif case == "prepared_metadata":
            task["occupation"] = "changed"
        elif case == "prepared_source_projection":
            task["source_projection_sha256"] = "0" * 64
        elif case == "prepared_url":
            task["reference_file_urls"] = ["https://fixture.invalid/not-fetched"]
        elif case.startswith("prepared_reference_"):
            task = next(row for row in payload["tasks"] if row["reference_files"])
            if case in {"prepared_reference_path", "prepared_reference_escape"}:
                task["reference_files"][0] = "reference_files/../escape" if case.endswith("escape") else "reference_files/other.txt"
            elif case == "prepared_reference_hash":
                task["reference_file_records"][0]["sha256"] = "0" * 64
            else:
                task["reference_file_records"][0]["size"] += 1
        elif case == "prepared_missing_task":
            payload["tasks"].pop()
        elif case == "prepared_duplicate_task":
            payload["tasks"][1] = task
        elif case == "prepared_extra_task":
            payload["tasks"].append(task)
        elif case == "prepared_task_order":
            payload["tasks"].reverse()
        elif case == "prepared_needs_files":
            # A reference-free task still requires a deliverable. Do not infer
            # needs_files from reference presence.
            assert task["needs_files"] is True and task["reference_files"] == []
            task["needs_files"] = False
        elif case == "prepared_count":
            payload["total_tasks"] = True
        elif case == "prepared_generation":
            payload["publication_generation"] = "not a valid lineage"
        elif case == "prepared_effort":
            payload["condition_a"]["model"]["reasoning_effort"] = "high"
        elif case == "prepared_limit":
            payload["execution"]["timeout"] += 1
        elif case == "prepared_rubric_injection":
            task["rubric_json"] = projections[0]["rubric_json"]
        elif case == "prepared_null_condition":
            payload.pop("condition_b")
        elif case == "prepared_missing_config_path":
            payload.pop("config_path")
        payload["prepared_fingerprint"] = "0" * 64 if case == "prepared_fingerprint" else prepared_fingerprint(payload)
        _write(codex.prepared_tasks, payload)
        # Even a matching capture and freshly recomputed fingerprint cannot
        # authorize prepared prompt/metadata/reference/config drift.
        captures[1]["consumer"].update(
            tasks=payload["tasks"], prepared_fingerprint=payload["prepared_fingerprint"],
            publication_generation=payload.get("publication_generation"),
            prepared_file=_identity(codex.prepared_tasks.read_bytes()),
        )
        _write(codex.input_binding, captures[1])
    elif case == "relocated":
        relocated = tmp_path / "relocated"
        relocated.mkdir()
        copied = []
        for index, item in enumerate(run_inputs):
            directory = relocated / str(index)
            directory.mkdir()
            config = directory / "config.json"
            binding = directory / "binding.json"
            shutil.copyfile(item.generated_config, config)
            shutil.copyfile(item.input_binding, binding)
            prepared_path = None
            if item.prepared_tasks:
                prepared_path = directory / "prepared.json"
                shutil.copyfile(item.prepared_tasks, prepared_path)
            copied.append(attester.PreparedRunInputs(item.run_id, config, binding, prepared_path))
        inputs["runs"] = tuple(copied)

    before = _tree_snapshot(tmp_path)
    with monkeypatch.context() as readonly:
        original_open = os.open

        def read_only_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                forbidden()
            return original_open(path, flags, *args, **kwargs)

        readonly.setattr(os, "open", read_only_open)
        for name in ("mkdir", "rename", "replace", "unlink", "rmdir"):
            readonly.setattr(os, name, forbidden)
        readonly.setattr(Path, "write_bytes", forbidden)
        readonly.setattr(Path, "write_text", forbidden)
        if case in {"identical", "relocated"} or case.startswith("attestation_"):
            result = attester.compile_prepared_input_attestation(**inputs)
            document = result.as_dict()
            assert result.canonical_bytes() == _json(document)
            assert result.sha256 == _identity(result.canonical_bytes())["sha256"]
            if case.startswith("attestation_"):
                if case == "attestation_authorization":
                    document["launch_allowed"] = True
                elif case == "attestation_drift":
                    document["source_tasks"][0]["projection"]["rubric_pretty"] += " "
                changed = _json(document) + (b"\n" if case == "attestation_noncanonical" else b"")
                with pytest.raises(attester.PreparedInputRefused, match="attestation bytes mismatch"):
                    attester.validate_prepared_input_attestation(changed, **inputs)
            else:
                assert attester.validate_prepared_input_attestation(result.canonical_bytes(), **inputs) == result
                if case == "relocated":
                    assert attester.compile_prepared_input_attestation(**{**inputs, "runs": run_inputs}) == result
                assert document["evidence_boundary"] == "offline_snapshot_and_supplied_capture_consistency"
                assert "launch_allowed" not in document and "full_220_allowed" not in document
                assert "source_revision" not in document and "verified" not in document
                assert [row["projection"] for row in document["source_tasks"]] == projections
                assert document["dataset"]["parquet"] == _identity(inputs["dataset_parquet"].read_bytes())
                assert [(row["binding"]["condition"], row["binding"]["repeat"]) for row in document["runs"]] == [
                    ("sandbox_v2", 1), ("codex", 1), ("codex", 2), ("sandbox_v2", 2),
                ]
                assert document["runs"][0]["generated_config"] == document["runs"][3]["generated_config"]
                assert document["runs"][1]["generated_config"]["sha256"] != document["runs"][2]["generated_config"]["sha256"]
                for source in document["source_tasks"]:
                    for field, identity in source["text_bytes"].items():
                        assert identity == _identity(source["projection"][field].encode("utf-8"))
                    for record in source["reference_file_records"]:
                        assert {key: record[key] for key in ("sha256", "size")} == records[record["path"]]
                for row in document["runs"]:
                    for task in row["binding"]["consumer"]["tasks"]:
                        assert not {"deliverable_files", "deliverable_text", "rubric_pretty", "rubric_json"} & task.keys()
                inspection = preflight.inspect_plan(inputs["manifest"], grading_plan=inputs["combined_plan"])
                assert inspection["configuration_valid"] is True
                assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
                assert "live_deployment_identity_and_input_bytes_not_verified" in inspection["launch_blockers"]
                assert "comparison_materialization_and_workflow_gates_not_wired" in inspection["launch_blockers"]
                assert len(preflight.REQUIRED_SOURCES) == 27
                assert set(inputs["manifest"]["source_pins"]) == preflight.REQUIRED_SOURCES
                sol = preflight.load_plan(preflight.ROOT / preflight.ENVELOPE / "gpt56_sol_copilot_codex_pilot.yaml")
                parser = "batch-runner/gpt54_comparison_preflight.py"
                assert sol["source_pins"][parser] == _identity((preflight.ROOT / parser).read_bytes())["sha256"]
        else:
            with pytest.raises(attester.PreparedInputRefused):
                attester.compile_prepared_input_attestation(**inputs)
    assert _tree_snapshot(tmp_path) == before
    assert forbidden_calls == []
