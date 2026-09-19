"""One free selector for exact inputs, no-clobber publication and runtime gates."""

import json
import os
import stat
import sys
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import gpt54_codex_input_capture as writer
import gpt54_comparison_preflight as preflight
import gpt54_prepared_input_attestation as attester
import gpt54_run_config_bundle as config_bundle
import gpt54_run_input_bundle as bundle
import step1_prepare_tasks as step1
import step2_run_inference as step2
import step8_grade as grading
from core.needs_files import NeedsFilesManifest
from core.source_identity import source_task_projection_sha256
from scripts import run_agentic_v2_stage as runner
from . import test_gpt54_codex_input_capture as codex_cases
from . import test_gpt54_v2_input_capture as v2_cases
from .test_gpt54_codex_input_capture import (
    _runtime_fixture as _codex_fixture,
    test_codex_comparison_capture_gates_real_step1_and_step2 as _codex_regression,
)
from .test_gpt54_prepared_input_attestation import (
    _bundle_fixture, _fixture, _identity, _json, _tree_snapshot,
)
from .test_gpt54_run_config_bundle import _forge_member, _guards
from .test_gpt54_v2_input_capture import (
    _runtime_fixture as _v2_fixture,
    test_v2_comparison_capture_gates_stage_before_provider as _v2_regression,
)


def _compiler_cache():
    """Memoize byte-derived preparation, never a validator's verdict.

    The grader closure is hashed by the real helper once. Reuse requires the
    same arguments, complete core inventory, path types/link counts and every
    dependency's actual bytes. Drift delegates to the real helper. Disposable
    checkout/data reads, source-pin comparisons and all validators stay real.
    """
    read_yaml, hash_source = yaml.safe_load, grading.compute_grader_source_hash
    sha256 = preflight.hashlib.sha256
    config_path = preflight.ROOT / preflight.GRADER
    batch_root = preflight.ROOT / "batch-runner"
    config = preflight.load_plan(config_path)
    config_bytes = _json(config)
    dependencies = {}
    read_bytes = Path.read_bytes

    def observed_read(path):
        data = read_bytes(path)
        dependencies[path] = data
        return data

    with pytest.MonkeyPatch.context() as observe:
        observe.setattr(Path, "read_bytes", observed_read)
        digest = hash_source(config_path, config, batch_root=batch_root)

    def source_state():
        # Include directories and non-Python entries: the real helper refuses
        # links anywhere in core, and a new Python file must invalidate reuse.
        paths = set((batch_root / "core").rglob("*")) | set(dependencies)
        paths.update(parent for path in tuple(paths) for parent in path.parents)
        topology = []
        try:
            for path in sorted(paths):
                info = path.lstat()
                if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                    return None
                topology.append((path, info.st_mode, info.st_nlink))
            return tuple(topology), tuple((path, read_bytes(path)) for path in dependencies)
        except OSError:
            return None

    sealed_state = source_state()
    assert sealed_state is not None and dict(sealed_state[1]) == dependencies

    def cached_source(config_file, value, *, batch_root=None):
        if (config_file == config_path and batch_root == preflight.ROOT / "batch-runner"
                and _json(value) == config_bytes and source_state() == sealed_state):
            return digest
        return hash_source(config_file, value, batch_root=batch_root)

    @lru_cache(maxsize=128)
    def parsed(data):
        return read_yaml(data)

    def cached_yaml(data):
        if type(data) not in (str, bytes):
            return read_yaml(data)
        # Compilers edit loaded configs. Never expose the cached object itself.
        return deepcopy(parsed(data))

    @lru_cache(maxsize=128)
    def hashed(data):
        return sha256(data)

    def install(monkeypatch):
        monkeypatch.setattr(yaml, "safe_load", cached_yaml)
        monkeypatch.setattr(grading, "compute_grader_source_hash", cached_source)
        # Only the compiler's byte-keyed hashes; mutable target validators keep
        # their original readers/hashers. Return a copy of the mutable hasher.
        monkeypatch.setattr(preflight, "hashlib", SimpleNamespace(sha256=lambda data: hashed(data).copy()))

    return install


def _snapshot_files(root):
    return tuple((path.relative_to(root).as_posix(), path.read_bytes())
                 for path in sorted(root.rglob("*")) if path.is_file())


def _copy_files(root, files):
    """Fresh single-link files per case; no shared mutable tree or hardlinks."""
    for name, data in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        assert not path.is_symlink() and path.stat().st_nlink == 1


@pytest.fixture(scope="module")
def _input_bundle_seed(tmp_path_factory):
    """Build the independent five-task oracle and four config bundles once.

    Only immutable bytes and frozen typed plans cross case boundaries. The
    existing runtime fixtures still call the real input materializer, Step 1
    serializer, capture writer and Step 2/V2 gates in every applicable case.
    """
    root = tmp_path_factory.mktemp("run-input-bundle-seed")
    oracle = root / "oracle"
    oracle.mkdir()
    with pytest.MonkeyPatch.context() as setup:
        forbidden = _guards(setup)
        install_cache = _compiler_cache()
        install_cache(setup)
        inputs, captures, prepared, projections, records = _fixture(oracle, setup, "identical")
        plan = preflight.compile_grading_plan(inputs["manifest"])
        oracle_files = _snapshot_files(oracle)
        documents = _json([inputs["manifest"], inputs["combined_plan"], captures, prepared, projections, records])
        run_roles = tuple((row.run_id, row.generated_config.relative_to(oracle),
                           row.input_binding.relative_to(oracle),
                           row.prepared_tasks.relative_to(oracle) if row.prepared_tasks else None)
                          for row in inputs["runs"])
        catalog, catalog_digest = preflight.load_task_catalog(), preflight.catalog_sha256()
        fixture_plan = preflight.load_plan
        rows = _json([vars(row) for row in step1.GDPValDataLoader(auto_download=False).load()])
        needs = _json(NeedsFilesManifest.load()._data)
        last_workspace = step1.WORKSPACE_DIR.relative_to(oracle)
        config_files, config_markers = {}, {}
        for run in plan.dispatch.runs:
            checkout = root / run.run_id
            config_markers[run.run_id] = _json(_bundle_fixture(
                checkout, manifest=inputs["manifest"], combined_plan=inputs["combined_plan"], run=run,
            ))
            config_files[run.run_id] = _snapshot_files(checkout)
        assert forbidden == []
    original = _tree_snapshot(root)

    def copy_inputs(directory, monkeypatch, case):
        assert case == "identical"  # Invalid oracle variants must never use this seed.
        _copy_files(directory, oracle_files)
        manifest, combined, bindings, payloads, sources, references = json.loads(documents)
        monkeypatch.setattr(preflight, "load_plan", lambda path=preflight.PLAN: deepcopy(fixture_plan(path)))
        for module in (preflight, attester):
            monkeypatch.setattr(module, "load_task_catalog", lambda: catalog)
            monkeypatch.setattr(module, "catalog_sha256", lambda: catalog_digest)
        monkeypatch.setenv("NEEDS_FILES_POLICY", "deliverable_only")

        def dataset_loader(*, auto_download):
            assert auto_download is False
            return SimpleNamespace(load=lambda: [SimpleNamespace(**row) for row in json.loads(rows)])

        monkeypatch.setattr(step1, "GDPValDataLoader", dataset_loader)
        monkeypatch.setattr(NeedsFilesManifest, "load", classmethod(lambda cls: NeedsFilesManifest(json.loads(needs))))
        monkeypatch.setattr(step1, "resolve_publication_generation", lambda experiment: "offline-fixture." + experiment)
        monkeypatch.setattr(step1, "WORKSPACE_DIR", directory / last_workspace)
        copied = {
            "manifest": manifest, "combined_plan": combined,
            "dataset_parquet": directory / "source.parquet", "reference_root": directory / "references",
            "runs": tuple(attester.PreparedRunInputs(run_id, directory / config, directory / binding,
                                                     directory / tasks if tasks else None)
                          for run_id, config, binding, tasks in run_roles),
        }
        return copied, bindings, payloads, sources, references

    def copy_config(checkout, *, manifest, combined_plan, run, materialize=True):
        assert materialize is True
        assert _json(manifest) == _json(json.loads(documents)[0])
        assert _json(combined_plan) == plan.canonical_bytes()
        assert run == next(row for row in plan.dispatch.runs if row.run_id == run.run_id)
        _copy_files(checkout, config_files[run.run_id])
        return json.loads(config_markers[run.run_id])

    def install(monkeypatch):
        install_cache(monkeypatch)
        # These are fixture suppliers, not runtime/compiler validators. Other
        # selectors get their unmodified helpers back at each case's teardown.
        for module in (codex_cases, v2_cases):
            monkeypatch.setattr(module, "_fixture", copy_inputs)
            monkeypatch.setattr(module, "_bundle_fixture", copy_config)

    yield SimpleNamespace(plan=plan, inputs=copy_inputs, config=copy_config, install=install)
    assert _tree_snapshot(root) == original


def _files(inputs, records):
    return {
        bundle.PARQUET_PATH: inputs["dataset_parquet"].read_bytes(),
        **{writer.DATASET_ROOT + "/" + name: (inputs["reference_root"] / name).read_bytes()
           for name in records},
    }


def _reservation(marker):
    return {
        "reservation_version": "gpt54-run-input-reservation-v1",
        "ready_path": bundle.READY_PATH,
        "intended_bundle": _identity(_json(marker)),
    }


def _assert_complete(root, marker, plan, index, oracle, projections, records, files):
    """Use the independent #622 oracle, not the new marker's private helpers."""
    run = plan.dispatch.runs[index]
    expected = {
        "bundle_version": "gpt54-run-input-bundle-v1",
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "abba_index": index, "dataset_root": writer.DATASET_ROOT,
        "input_identity": {key: oracle[key] for key in (
            "binding_version", "manifest_sha256", "combined_plan_sha256",
            "source_pins_sha256", "dataset", "task_ids",
            "ordered_source_projection_sha256", "needs_files_policy",
        )},
        "tasks": [{
            "task_id": row["task_id"],
            "source_projection_sha256": source_task_projection_sha256(**row),
            "text_bytes": {key: _identity(row[key].encode("utf-8"))
                           for key in ("prompt", "rubric_json", "rubric_pretty")},
            "reference_file_records": [{"path": name, **records[name]}
                                       for name in row["reference_files"]],
        } for row in projections],
        "files": {name: _identity(data) for name, data in files.items()},
        "config_bundle": {"path": config_bundle.READY_PATH,
                          **_identity((root / config_bundle.READY_PATH).read_bytes())},
        "evidence_boundary": "local_input_bundle_consistency",
    }
    assert marker == expected
    assert [row["task_id"] for row in marker["tasks"]] == list(run.task_ids)
    assert len(marker["tasks"]) == 5
    assert str(root).encode() not in _json(marker)
    assert (root / bundle.READY_PATH).read_bytes() == _json(expected)
    assert (root / bundle.RESERVATION_PATH).read_bytes() == _json(_reservation(expected))
    # The pinned parquet is copied intact despite its reversed physical order;
    # only registered references appear, and no prompt/rubric text is published.
    assert {path.relative_to(root).as_posix()
            for path in (root / writer.DATASET_ROOT).rglob("*") if path.is_file()} == set(files)
    for name, data in {
        **files, bundle.READY_PATH: _json(expected),
        bundle.RESERVATION_PATH: _json(_reservation(expected)),
    }.items():
        path = root / name
        assert path.read_bytes() == data
        assert not path.is_symlink() and path.stat().st_nlink == 1
    assert not (root / "batch-runner/workspace").exists()
    assert not (root / ".git").exists()
    before = _tree_snapshot(root)
    assert bundle.verify_run_input_bundle(
        checkout=root, run_id=run.run_id, condition=run.condition,
    ) == expected
    assert _tree_snapshot(root) == before
    assert plan.as_dict()["launch_allowed"] is plan.as_dict()["full_220_allowed"] is False


def _link(path, moved, *, hard=False):
    path.rename(moved)
    if hard:
        os.link(moved, path)
    else:
        path.symlink_to(moved, target_is_directory=moved.is_dir())


def _tamper_document(root, role, change, tmp_path):
    path = root / (bundle.READY_PATH if role == "marker" else bundle.RESERVATION_PATH)
    if change == "missing":
        path.unlink()
    elif change == "noncanonical":
        path.write_bytes(path.read_bytes() + b"\n")
    elif change in {"symlink", "hardlink"}:
        _link(path, tmp_path / "untrusted-document", hard=change == "hardlink")
    else:
        payload = json.loads(path.read_bytes())
        if change == "extra":
            payload["approved"] = True
        elif change == "removed":
            payload.pop("files" if role == "marker" else "intended_bundle")
        elif change == "null":
            payload = None
        else:
            assert change == "digest"
            identity = (payload["input_identity"]["dataset"]["parquet"]
                        if role == "marker" else payload["intended_bundle"])
            identity["sha256"] = "0" * 64
        path.write_bytes(_json(payload))


def _forge_inputs(root, *, parquet=False):
    """Rewrite target bytes and both documents; source pins must still win."""
    marker_path = root / bundle.READY_PATH
    marker = json.loads(marker_path.read_bytes())
    name = bundle.PARQUET_PATH if parquet else next(
        name for name in marker["files"] if name != bundle.PARQUET_PATH
    )
    path = root / name
    path.write_bytes(path.read_bytes() + b"attacker-supplied replacement")
    identity = _identity(path.read_bytes())
    marker["files"][name] = identity
    if parquet:
        marker["input_identity"]["dataset"]["parquet"] = identity
    else:
        relative = name.removeprefix(writer.DATASET_ROOT + "/")
        for task in marker["tasks"]:
            for record in task["reference_file_records"]:
                if record["path"] == relative:
                    record.update(identity)
    marker_path.write_bytes(_json(marker))
    (root / bundle.RESERVATION_PATH).write_bytes(_json(_reservation(marker)))


def _runtime_rejection(case, tmp_path, monkeypatch):
    condition, mutation = case.removeprefix("gate_").split("_", 1)
    if condition == "codex":
        root, run, _, _, _ = _codex_fixture(tmp_path, monkeypatch, 1)
    else:
        root, run, _, _, _ = _v2_fixture(tmp_path, monkeypatch, 1)
    if mutation == "config_missing":
        (root / config_bundle.READY_PATH).unlink()
    elif mutation == "config_forged":
        _forge_member(root, run)
    elif mutation == "forged":
        _forge_inputs(root)
    elif mutation == "reservation_missing":
        (root / bundle.RESERVATION_PATH).unlink()
    else:
        _tamper_document(root, "marker", mutation, tmp_path)
    before = _tree_snapshot(root)
    if condition == "codex":
        refused = (bundle.RunInputBundleRefused, writer.CodexInputCaptureRefused)
        with pytest.raises(refused):
            step2.run_inference(
                comparison_run_id=run.run_id, resume=False, max_retries=0, resume_max_rounds=0,
            )
        with pytest.raises(refused):
            step2.validate_restored_checkpoint(comparison_run_id=run.run_id)
        assert _tree_snapshot(root) == before
        # Also exercise the real Step 1 serializer: neither prepared bytes nor
        # capture may be published when the input/config marker gate refuses.
        (root / writer.PREPARED_PATH).unlink()
        (root / writer.CAPTURE_PATH).unlink()
        before = _tree_snapshot(root)
        with pytest.raises(refused):
            step1.prepare_tasks(str(root / writer.CONFIG_PATH))
        assert not (root / writer.PREPARED_PATH).exists()
        assert not (root / writer.CAPTURE_PATH).exists()
    else:
        monkeypatch.setattr(sys, "argv", [
            "run_agentic_v2_stage.py", "--stage", "advance_check_5",
            "--plan", str(root / writer.CONFIG_PATH), "--run-id", run.run_id,
            "--parquet", str(root / bundle.PARQUET_PATH),
            "--dataset-root", str(root / writer.DATASET_ROOT),
            "--into", str(root / "batch-runner/workspace"),
        ])
        assert runner.main() == 1
        assert not (root / writer.CAPTURE_PATH).exists()
    assert _tree_snapshot(root) == before


@pytest.mark.parametrize("case", [
    "v2_r1", "codex_r1", "codex_r2", "v2_r2", "relocated_v2", "relocated_codex",
    "existing_data_parent", "dispatch_type", "dispatch_run", "dispatch_condition",
    "dispatch_repeat_bool", "dispatch_tasks", "dispatch_config", "manifest_control",
    "combined_plan", "combined_extra", "config_missing", "config_changed",
    "config_marker_missing", "config_marker_forged", "checkout_manifest_changed", "pinned_source_changed",
    *[f"source_parquet_{change}" for change in ("changed", "missing", "symlink", "hardlink", "escape")],
    *[f"source_reference_{change}" for change in (
        "changed", "missing", "extra", "directory", "symlink", "hardlink", "escape", "root_symlink",
    )],
    "source_overlap_equal", "source_overlap_ancestor", "source_overlap_descendant", "source_overlap_parquet",
    "checkout_missing", "checkout_symlink", "checkout_escape", "data_parent_file", "data_parent_symlink",
    "collision_dataset_empty", "collision_dataset_partial", "collision_dataset_file",
    "collision_dataset_symlink", "collision_dataset_hardlink", "collision_dataset_dangling",
    "collision_marker", "collision_reservation",
    "failure_after_reservation", "failure_after_data_parent", "failure_after_dataset_root",
    "failure_file_1", "failure_file_2", "failure_before_ready", "failure_file_race",
    "failure_data_parent_race", "failure_dataset_root_race", "failure_parent_swap",
    "failure_source_drift",
    *[f"{role}_{change}" for role in ("marker", "reservation") for change in (
        "missing", "extra", "removed", "null", "noncanonical", "digest", "symlink", "hardlink",
    )],
    "forged_parquet", "forged_reference",
    *[f"target_parquet_{change}" for change in ("changed", "missing", "symlink", "hardlink", "extra")],
    *[f"target_reference_{change}" for change in ("changed", "missing", "extra", "directory", "symlink", "hardlink")],
    "target_root_extra", "target_root_symlink", "target_root_file", "target_data_symlink",
    "verify_run", "verify_condition", "config_after_publication", "config_marker_after_publication",
    *[f"gate_{condition}_{change}" for condition in ("v2", "codex")
      for change in ("missing", "extra", "forged", "reservation_missing", "config_missing", "config_forged")],
    "runtime_v2", "runtime_codex", "legacy_v2_absent_null", "legacy_codex_absent_null",
])
def test_run_input_bundle_is_exact_atomic_and_gates_execution(case, tmp_path, monkeypatch, _input_bundle_seed):
    forbidden_calls = _guards(monkeypatch)
    _input_bundle_seed.install(monkeypatch)
    if case in {"runtime_v2", "runtime_codex", "legacy_v2_absent_null", "legacy_codex_absent_null"}:
        regression = _v2_regression if "v2" in case else _codex_regression
        regression("default_absent_and_null" if case.startswith("legacy_") else "r1", tmp_path, monkeypatch)
        assert forbidden_calls == []
        return
    if case.startswith("gate_"):
        _runtime_rejection(case, tmp_path, monkeypatch)
        assert forbidden_calls == []
        return

    oracle_root = tmp_path / "independent-oracle"
    oracle_root.mkdir()
    inputs, captures, _, projections, records = _input_bundle_seed.inputs(oracle_root, monkeypatch, "identical")
    manifest = json.loads(_json(inputs["manifest"]))
    plan = _input_bundle_seed.plan
    index = {"codex_r1": 1, "codex_r2": 2, "v2_r2": 3, "relocated_codex": 1}.get(case, 0)
    run = plan.dispatch.runs[index]
    supplied_run = run
    combined = plan.as_dict()
    root = tmp_path / "disposable-source"
    _input_bundle_seed.config(root, manifest=manifest, combined_plan=combined, run=run)
    files = _files(inputs, records)
    source_before = _tree_snapshot(oracle_root)
    target, parquet, references = root, inputs["dataset_parquet"], inputs["reference_root"]
    reference = references / next(iter(records))
    ready, reserved = root / bundle.READY_PATH, root / bundle.RESERVATION_PATH
    dataset = root / writer.DATASET_ROOT
    if case in {"existing_data_parent", "failure_parent_swap"}:
        (root / "data").mkdir()
        (root / "data/tracked-parent-note.txt").write_bytes(b"leave existing parent contents unchanged")

    def publish():
        return bundle.materialize_run_input_bundle(
            supplied_run, manifest=manifest, combined_plan=combined, checkout=target,
            dataset_parquet=parquet, reference_root=references,
        )

    if case in {"v2_r1", "codex_r1", "codex_r2", "v2_r2", "relocated_v2", "relocated_codex", "existing_data_parent"}:
        before = _tree_snapshot(root)
        marker = publish()
        _assert_complete(root, marker, plan, index, captures[index], projections, records, files)
        if case == "v2_r1":
            inspection = preflight.inspect_plan(manifest, grading_plan=combined)
            assert inspection["configuration_valid"] is True
            assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
            assert inspection["run_input_bundle"] == {
                "bundle_version": "gpt54-run-input-bundle-v1",
                "materializer": "gpt54_run_input_bundle.materialize_run_input_bundle",
                "ready_marker": "comparison-inputs-ready.json",
                "reservation": "comparison-inputs-reserved.json",
                "dataset_root": "data/gdpval-local",
                "reference_scope": "advance_check_5_only",
                "required_runs": [row.run_id for row in plan.dispatch.runs],
                "checkout_creation": False,
                "evidence_boundary": "local_input_bundle_consistency",
            }
            assert len(preflight.REQUIRED_SOURCES) == 30
            assert set(manifest["source_pins"]) == preflight.REQUIRED_SOURCES
            assert "comparison_materialization_and_workflow_gates_not_wired" in inspection["launch_blockers"]
        after = _tree_snapshot(root)
        assert all(after[name] == value for name, value in before.items() if name != "data")
        added_files = {name for name, value in after.items()
                       if stat.S_ISREG(value[0]) and name not in before}
        assert added_files == set(files) | {bundle.READY_PATH, bundle.RESERVATION_PATH}
        assert _tree_snapshot(oracle_root) == source_before
        if case.startswith("relocated_"):
            relocated = tmp_path / "different-location/same-run"
            _bundle_fixture(relocated, manifest=manifest, combined_plan=combined, run=run)
            other = bundle.materialize_run_input_bundle(
                run, manifest=manifest, combined_plan=combined, checkout=relocated,
                dataset_parquet=parquet, reference_root=references,
            )
            _assert_complete(relocated, other, plan, index, captures[index], projections, records, files)
            assert other == marker
        before_retry = _tree_snapshot(tmp_path)
        with pytest.raises(bundle.RunInputBundleRefused):
            publish()
        assert _tree_snapshot(tmp_path) == before_retry
    elif case.startswith("failure_"):
        real_write, real_mkdir = writer._write_no_clobber, os.mkdir
        written = []

        def interrupted_write(path, data):
            if path == ready and case == "failure_before_ready":
                raise OSError("fixture stops before publishing ready")
            if path == root / bundle.PARQUET_PATH and case == "failure_file_race":
                path.write_bytes(b"another publisher owns this member")
            real_write(path, data)
            if path == reserved:
                if case == "failure_after_reservation":
                    raise OSError("fixture stops after reserving the input role")
                if case == "failure_data_parent_race":
                    real_mkdir(root / "data")
                elif case == "failure_parent_swap":
                    (root / "data").rename(tmp_path / "displaced-data")
                    real_mkdir(root / "data")
            elif path != ready:
                written.append(path)
                if case in {"failure_file_1", "failure_file_2"} and len(written) == int(case[-1]):
                    raise OSError("fixture stops after a complete input file")
                if case == "failure_source_drift" and len(written) == 1:
                    reference.write_bytes(reference.read_bytes() + b"source changed during publication")

        def interrupted_mkdir(path, mode=0o777, *, dir_fd=None):
            if case == "failure_dataset_root_race" and path == "gdpval-local" and dir_fd is not None:
                real_mkdir(path, mode, dir_fd=dir_fd)
            result = real_mkdir(path, mode, dir_fd=dir_fd)
            if ((case == "failure_after_data_parent" and path == "data" and not dataset.exists())
                    or (case == "failure_after_dataset_root" and path == "gdpval-local")):
                raise OSError("fixture stops after creating a directory")
            return result

        with monkeypatch.context() as failure:
            failure.setattr(writer, "_write_no_clobber", interrupted_write)
            failure.setattr(bundle.os, "mkdir", interrupted_mkdir)
            with pytest.raises(bundle.RunInputBundleRefused):
                publish()
        assert reserved.is_file() and not ready.exists()
        intent = json.loads(reserved.read_bytes())
        assert intent["ready_path"] == bundle.READY_PATH
        assert set(intent["intended_bundle"]) == {"sha256", "size"}
        assert reserved.read_bytes() == _json(intent)
        assert not list(root.rglob(".input-capture-*"))
        for path in written:
            assert path.read_bytes() == files[path.relative_to(root).as_posix()]
        if case in {"failure_after_data_parent", "failure_data_parent_race", "failure_parent_swap"}:
            assert (root / "data").is_dir() and not dataset.exists()
        if case == "failure_after_reservation":
            assert not (root / "data").exists()
        if case == "failure_file_race":
            assert (root / bundle.PARQUET_PATH).read_bytes() == b"another publisher owns this member"
        if case != "failure_source_drift":
            assert _tree_snapshot(oracle_root) == source_before
        before_retry = _tree_snapshot(tmp_path)
        with pytest.raises(bundle.RunInputBundleRefused):
            bundle.verify_run_input_bundle(checkout=root, run_id=run.run_id, condition=run.condition)
        with pytest.raises(bundle.RunInputBundleRefused):
            publish()
        assert _tree_snapshot(tmp_path) == before_retry
    elif case.startswith(("marker_", "reservation_", "target_", "forged_", "verify_")) or case in {
        "config_after_publication", "config_marker_after_publication",
    }:
        publish()
        requested_run, requested_condition = run.run_id, run.condition
        if case.startswith(("marker_", "reservation_")):
            role, change = case.split("_", 1)
            _tamper_document(root, role, change, tmp_path)
        elif case.startswith("forged_"):
            _forge_inputs(root, parquet=case == "forged_parquet")
        elif case == "verify_run":
            requested_run = plan.dispatch.runs[3].run_id
        elif case == "verify_condition":
            requested_condition = "codex"
        elif case == "config_after_publication":
            (root / run.config_path).write_bytes(run.config_json.encode() + b"\n")
        elif case == "config_marker_after_publication":
            (root / config_bundle.READY_PATH).unlink()
        elif case == "target_root_extra":
            (dataset / "unexpected.txt").write_bytes(b"not an input")
        elif case == "target_root_file":
            dataset.rename(tmp_path / "displaced-inputs")
            dataset.write_bytes(b"not a directory")
        elif case in {"target_root_symlink", "target_data_symlink"}:
            _link(dataset if case == "target_root_symlink" else dataset / "data", tmp_path / "linked-inputs")
        else:
            _, kind, change = case.split("_", 2)
            path = root / bundle.PARQUET_PATH if kind == "parquet" else dataset / next(iter(records))
            if change == "changed":
                path.write_bytes(path.read_bytes() + b"drift")
            elif change == "missing":
                path.unlink()
            elif change in {"symlink", "hardlink"}:
                _link(path, tmp_path / "linked-input", hard=change == "hardlink")
            elif change == "extra":
                extra = dataset / ("data/extra.parquet" if kind == "parquet" else "reference_files/extra.txt")
                extra.write_bytes(b"unregistered")
            else:
                assert change == "directory"
                (dataset / "reference_files/unregistered").mkdir()
        before = _tree_snapshot(tmp_path)
        with pytest.raises(bundle.RunInputBundleRefused):
            bundle.verify_run_input_bundle(checkout=root, run_id=requested_run, condition=requested_condition)
        assert _tree_snapshot(tmp_path) == before
        assert _tree_snapshot(oracle_root) == source_before
    else:
        if case == "dispatch_type":
            supplied_run = run.as_dict()
        elif case.startswith("dispatch_"):
            supplied_run = replace(run, **{
                "dispatch_run": {"run_id": "unregistered"},
                "dispatch_condition": {"condition": "codex"},
                "dispatch_repeat_bool": {"repeat": True},
                "dispatch_tasks": {"task_ids": tuple(reversed(run.task_ids))},
                "dispatch_config": {"config_json": run.config_json + "\n"},
            }[case])
        elif case == "manifest_control":
            manifest["shared"]["model"]["reasoning_effort"] = "high"
        elif case == "combined_plan":
            combined["dispatch_plan"]["runs"][0]["task_ids"].reverse()
        elif case == "combined_extra":
            combined["approved"] = True
        elif case == "config_missing":
            (root / run.config_path).unlink()
        elif case == "config_changed":
            (root / run.config_path).write_bytes(run.config_json.encode() + b"\n")
        elif case == "config_marker_missing":
            (root / config_bundle.READY_PATH).unlink()
        elif case == "config_marker_forged":
            _forge_member(root, run)
        elif case == "checkout_manifest_changed":
            path = root / config_bundle.MANIFEST_PATH
            path.write_bytes(path.read_bytes() + b"\n")
        elif case == "pinned_source_changed":
            path = root / "batch-runner/gpt54_run_input_bundle.py"
            path.write_bytes(path.read_bytes() + b"\n")
        elif case.startswith("source_overlap_"):
            if case == "source_overlap_parquet":
                parquet = root / bundle.PARQUET_PATH
            else:
                references = {"source_overlap_equal": dataset, "source_overlap_ancestor": root,
                              "source_overlap_descendant": dataset / "reference_files"}[case]
        elif case.startswith("source_"):
            _, kind, change = case.split("_", 2)
            path = parquet if kind == "parquet" else reference
            if change == "changed":
                path.write_bytes(path.read_bytes() + b"source drift")
            elif change == "missing":
                path.unlink()
            elif change in {"symlink", "hardlink"}:
                _link(path, tmp_path / "linked-source", hard=change == "hardlink")
            elif change == "escape":
                if kind == "parquet":
                    parquet = references / ".." / parquet.name
                else:
                    references = references / "reference_files" / ".."
            elif change == "extra":
                (references / "reference_files/extra.txt").write_bytes(b"unregistered reference")
            elif change == "directory":
                (references / "reference_files/unregistered").mkdir()
            else:
                assert change == "root_symlink"
                _link(references, tmp_path / "linked-references")
        elif case == "checkout_missing":
            target = tmp_path / "must-not-be-created"
        elif case == "checkout_symlink":
            _link(root, tmp_path / "linked-checkout")
        elif case == "checkout_escape":
            target = root / "batch-runner" / ".."
        elif case == "data_parent_file":
            (root / "data").write_bytes(b"not a directory")
        elif case == "data_parent_symlink":
            outside = tmp_path / "linked-data"
            outside.mkdir()
            (root / "data").symlink_to(outside, target_is_directory=True)
        elif case in {"collision_marker", "collision_reservation"}:
            (ready if case == "collision_marker" else reserved).write_bytes(b"existing owner")
        else:
            assert case.startswith("collision_dataset_")
            (root / "data").mkdir()
            change = case.removeprefix("collision_dataset_")
            if change in {"empty", "partial"}:
                dataset.mkdir()
                if change == "partial":
                    (dataset / "partially-installed-input").write_bytes(b"never adopt this tree")
            elif change == "file":
                dataset.write_bytes(b"not a directory")
            else:
                existing = tmp_path / "untouched-collision"
                if change != "dangling":
                    existing.write_bytes(b"another owner")
                if change == "hardlink":
                    os.link(existing, dataset)
                else:
                    dataset.symlink_to(existing)
        before = _tree_snapshot(tmp_path)
        with pytest.raises(bundle.RunInputBundleRefused):
            publish()
        assert _tree_snapshot(tmp_path) == before
    assert forbidden_calls == []
