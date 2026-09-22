"""Publish pinned comparison inputs locally, without creating or launching a run.

The retained reservation prevents adoption after even the first directory write
fails. Only the last ready marker denotes a complete, revalidated local bundle;
neither document grants launch permission or an inference publication identity.
"""

from __future__ import annotations

import json
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

import yaml

from core.agentic_v2_manifest_binding import ManifestRefused
from core.inference_manifest import _assert_no_symlink_ancestors
from gpt54_codex_input_capture import DATASET_ROOT, PARQUET_NAME
from gpt54_comparison_preflight import (
    ComparisonGradingPlan, ComparisonRunSpec, _canonical_json, compile_grading_plan,
)
from gpt54_prepared_input_attestation import _SourceSnapshot, _identity, _json_object, _same, _source_snapshot
from gpt54_run_config_bundle import (
    MANIFEST_PATH, READY_PATH as CONFIG_READY_PATH, _held_parents, _path, _root,
    verify_run_config_bundle,
)
from gpt54_v2_grading_input import _read_bytes

READY_PATH = "comparison-inputs-ready.json"
RESERVATION_PATH = "comparison-inputs-reserved.json"
PARQUET_PATH = DATASET_ROOT + "/data/" + PARQUET_NAME
STEP0_MANIFEST_PATH = "batch-runner/workspace/step0_needs_files_manifest.json"


class RunInputBundleRefused(ValueError):
    """The local inputs cannot be published or used as a comparison bundle."""


def _configuration(root: Path, run_id: str, condition: str) -> tuple[
    ComparisonGradingPlan, ComparisonRunSpec, dict[str, Any], dict[str, Any],
]:
    config = verify_run_config_bundle(checkout=root, run_id=run_id, condition=condition)
    identity = _identity(_canonical_json(config).encode("utf-8"))
    _read_bytes(root / CONFIG_READY_PATH, **identity)
    manifest = yaml.safe_load(_read_bytes(root / MANIFEST_PATH))
    plan = compile_grading_plan(manifest)
    run = next(run for run in plan.dispatch.runs if run.run_id == run_id)
    _same("input bundle condition", condition, run.condition)
    return plan, run, manifest, {"path": CONFIG_READY_PATH, **identity}


def _step0_source(run: ComparisonRunSpec, source: Path | None) -> Path | None:
    """Require an explicit source only for the condition whose Step 1 consumes it."""
    if run.condition != "codex":
        if source is not None:
            raise RunInputBundleRefused("Step 0 manifest is a Codex-only input")
        return None
    if source is None:
        raise RunInputBundleRefused("Codex requires an explicit local canonical Step 0 manifest")
    path = Path(source)
    if ".." in path.parts:
        raise RunInputBundleRefused("Step 0 source parent traversal is forbidden")
    path = Path(os.path.abspath(path))
    _assert_no_symlink_ancestors(path)
    return path


def _step0_bytes(source: Path | None, snapshot: _SourceSnapshot) -> bytes | None:
    """Read canonical full-manifest bytes, never regenerate a cohort substitute."""
    if source is None:
        return None
    from core import repo_bootstrapper
    from core.needs_files import NeedsFilesManifest

    try:
        policy = snapshot.shared_binding["needs_files_policy"]
        _same("Step 0 active policy", repo_bootstrapper.NEEDS_FILES_POLICY, policy)
        _same("Step 1 active policy", os.environ.get("NEEDS_FILES_POLICY", "deliverable_only"), policy)
        data = _read_bytes(source)
        repo_bootstrapper.require_canonical_manifest_bytes(data)
        manifest = NeedsFilesManifest(_json_object(data))
        manifest.require_schema(4)
        _same("Step 0 manifest policy", manifest.summary.get("active_policy"), policy)
        for row in snapshot.sources:
            task_id = row["projection"]["task_id"]
            _same("Step 0 task source projection", manifest.source_projection_sha256(task_id),
                  row["source_projection_sha256"])
            _same("Step 0 task references", manifest.reference_records(
                task_id, row["projection"]["reference_files"],
            ), row["reference_file_records"])
            _same("Step 0 task deliverable policy", manifest.needs_files(task_id), snapshot.needs_files[task_id])
        return data
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise RunInputBundleRefused("canonical Step 0 manifest refused") from error


def _file_identities(snapshot: _SourceSnapshot, step0: bytes | None) -> dict[str, dict[str, Any]]:
    return {
        PARQUET_PATH: snapshot.shared_binding["dataset"]["parquet"],
        **{DATASET_ROOT + "/" + name: identity for name, identity in snapshot.references.items()},
        **({STEP0_MANIFEST_PATH: _identity(step0)} if step0 is not None else {}),
    }


def _marker(
    plan: ComparisonGradingPlan, run: ComparisonRunSpec, snapshot: _SourceSnapshot,
    config_bundle: dict[str, Any], step0: bytes | None,
) -> dict[str, Any]:
    return {
        "bundle_version": "gpt54-run-input-bundle-v1",
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "abba_index": next(index for index, row in enumerate(plan.dispatch.runs) if row.run_id == run.run_id),
        "dataset_root": DATASET_ROOT,
        "input_identity": snapshot.shared_binding,
        "tasks": [{
            "task_id": source["projection"]["task_id"],
            "source_projection_sha256": source["source_projection_sha256"],
            "text_bytes": source["text_bytes"],
            "reference_file_records": source["reference_file_records"],
        } for source in snapshot.sources],
        "files": _file_identities(snapshot, step0),
        "config_bundle": config_bundle,
        "evidence_boundary": "local_input_bundle_consistency",
    }


def _reservation(marker_data: bytes) -> bytes:
    return _canonical_json({
        "reservation_version": "gpt54-run-input-reservation-v1",
        "ready_path": READY_PATH,
        "intended_bundle": _identity(marker_data),
    }).encode("utf-8")


def _absent(root: Path, run: ComparisonRunSpec) -> None:
    roles = (DATASET_ROOT, READY_PATH, RESERVATION_PATH)
    if run.condition == "codex":
        roles += (str(Path(STEP0_MANIFEST_PATH).parent),)
    if any(os.path.lexists(root / role) for role in roles):
        raise RunInputBundleRefused("input target exists; completed or partial checkouts cannot be reused")


def _source_paths(root: Path, parquet: Path, references: Path, step0: Path | None) -> tuple[Path, Path]:
    paths = [Path(parquet), Path(references)]
    if any(".." in path.parts for path in paths):
        raise RunInputBundleRefused("source parent traversal is forbidden")
    paths = [Path(os.path.abspath(path)) for path in paths]
    targets = [root / DATASET_ROOT]
    if step0 is not None:
        targets.append((root / STEP0_MANIFEST_PATH).parent)
    for source in [*paths, *([step0] if step0 is not None else [])]:
        _assert_no_symlink_ancestors(source)
        if any(target.is_relative_to(source) or source.is_relative_to(target) for target in targets):
            raise RunInputBundleRefused("source and input target overlap")
    return paths[0], paths[1]


@contextmanager
def _publication_parents(
    root: Path, *, step0: bool = False,
) -> Iterator[tuple[Callable[[], None], Callable[[Path], None], bool]]:
    """Hold existing and exclusively created directories throughout publication."""
    with ExitStack() as stack:
        descriptors: dict[Path, int] = {}

        def hold(path: Path, parent: int | None = None) -> None:
            _assert_no_symlink_ancestors(path)
            descriptor = os.open(
                path if parent is None else path.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent,
            )
            stack.callback(os.close, descriptor)
            descriptors[path] = descriptor

        def check() -> None:
            for path, descriptor in descriptors.items():
                _assert_no_symlink_ancestors(path)
                held, current = os.fstat(descriptor), path.stat()
                if (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
                    raise RunInputBundleRefused("input publication parent changed")

        def mkdir(path: Path) -> None:
            check()
            parent = descriptors[path.parent]
            os.mkdir(path.name, mode=0o700, dir_fd=parent)
            hold(path, parent)
            check()

        hold(root)
        data_existed = os.path.lexists(root / "data")
        if data_existed:
            hold(root / "data", descriptors[root])
        if step0:
            hold(root / "batch-runner", descriptors[root])
        check()
        yield check, mkdir, data_existed


def _installed_snapshot(root: Path, plan: ComparisonGradingPlan) -> _SourceSnapshot:
    dataset = root / DATASET_ROOT
    for directory in (dataset, dataset / "data"):
        _assert_no_symlink_ancestors(directory)
    _same("input root entries", sorted(path.name for path in dataset.iterdir()), ["data", "reference_files"])
    _same("input parquet entries", sorted(path.name for path in (dataset / "data").iterdir()), [PARQUET_NAME])
    return _source_snapshot(plan, root / PARQUET_PATH, dataset, reference_subtree=True)


def materialize_run_input_bundle(
    dispatch_run: ComparisonRunSpec, *, manifest: dict[str, Any], combined_plan: dict[str, Any],
    checkout: Path, dataset_parquet: Path, reference_root: Path,
    step0_manifest: Path | None = None,
) -> dict[str, Any]:
    """Install exact local inputs, including Codex's full canonical Step 0 manifest.

    Args:
        dispatch_run: The exact typed recipe for one registered ABBA run.
        manifest, combined_plan: The same documents bound by its config bundle.
        checkout: A pre-existing source checkout with a verified config bundle.
        dataset_parquet, reference_root: Local pinned parquet and a cohort-only
            reference tree. They must not overlap the destination input tree.
        step0_manifest: Explicit local canonical manifest required for Codex;
            absent for V2. No bootstrap, download or manifest generation occurs.

    Returns:
        The canonical input-ready document, containing local identities only.

    Raises:
        RunInputBundleRefused: On drift, links, overlap, collision or I/O failure.
        After reservation, any partial files/directories remain and retries refuse.
    """
    from gpt54_codex_input_capture import _write_no_clobber

    try:
        root = _root(checkout)
        if type(dispatch_run) is not ComparisonRunSpec:
            raise RunInputBundleRefused("an exact typed dispatch recipe is required")
        manifest = json.loads(_canonical_json(manifest))
        plan, run, actual_manifest, config = _configuration(root, dispatch_run.run_id, dispatch_run.condition)
        _same("dispatch recipe", dispatch_run.as_dict(), run.as_dict())
        _same("input manifest", manifest, actual_manifest)
        _same("input combined plan", combined_plan, plan.as_dict())
        step0 = _step0_source(run, step0_manifest)
        parquet, references = _source_paths(root, dataset_parquet, reference_root, step0)
        with ExitStack() as held, _publication_parents(root, step0=step0 is not None) as (check, mkdir, data_existed):
            check_source = (held.enter_context(_held_parents(step0.parent, (step0.name,)))
                            if step0 is not None else lambda: None)
            _absent(root, run)
            snapshot = _source_snapshot(plan, parquet, references)
            step0_data = _step0_bytes(step0, snapshot)
            files = {PARQUET_PATH: _read_bytes(parquet, **snapshot.shared_binding["dataset"]["parquet"])}
            files.update({DATASET_ROOT + "/" + name: _read_bytes(references / name, **identity)
                          for name, identity in snapshot.references.items()})
            if step0_data is not None:
                files[STEP0_MANIFEST_PATH] = step0_data
            marker = _marker(plan, run, snapshot, config, step0_data)
            marker_data = _canonical_json(marker).encode("utf-8")
            _same("source snapshot before publication", _marker(
                plan, run, _source_snapshot(plan, parquet, references), config, _step0_bytes(step0, snapshot),
            ), marker)
            _same("config before input publication", _configuration(root, run.run_id, run.condition)[3], config)
            _absent(root, run)
            check_source()
            check()
            # This retained intent is not ready evidence. It also quarantines a
            # failure between creating data/ and creating data/gdpval-local/.
            _write_no_clobber(root / RESERVATION_PATH, _reservation(marker_data))
            directories: set[Path] = set()
            for name in files:
                parent = _path(root, name).parent
                while parent != root:
                    directories.add(parent)
                    parent = parent.parent
            for directory in sorted(directories, key=lambda path: (len(path.parts), path.as_posix())):
                if ((directory == root / "data" and data_existed)
                        or (directory == root / "batch-runner" and step0 is not None)):
                    # Only the data/ or source parent held before reservation may exist.
                    # If it appeared later, mkdir must refuse rather than adopt.
                    check()
                    continue
                mkdir(directory)
            for name, data in files.items():
                check()
                _write_no_clobber(_path(root, name), data)
            check()
            installed = _installed_snapshot(root, plan)
            installed_step0 = _step0_bytes(root / STEP0_MANIFEST_PATH if step0 is not None else None, installed)
            _same("installed inputs", _marker(plan, run, installed, config, installed_step0), marker)
            _same("source snapshot after publication", _marker(
                plan, run, _source_snapshot(plan, parquet, references), config, _step0_bytes(step0, snapshot),
            ), marker)
            _same("config after input publication", _configuration(root, run.run_id, run.condition)[3], config)
            _read_bytes(root / RESERVATION_PATH, **_identity(_reservation(marker_data)))
            check_source()
            check()
            _write_no_clobber(root / READY_PATH, marker_data)
            return marker
    except RunInputBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, ManifestRefused, yaml.YAMLError) as error:
        raise RunInputBundleRefused("run input bundle publication refused") from error


def verify_run_input_bundle(*, checkout: Path, run_id: str, condition: str) -> dict[str, Any]:
    """Require both ready markers and exact installed inputs before construction."""
    try:
        root = _root(checkout)
        plan, run, _, config = _configuration(root, run_id, condition)
        snapshot = _installed_snapshot(root, plan)
        step0 = root / STEP0_MANIFEST_PATH if run.condition == "codex" else None
        marker = _marker(plan, run, snapshot, config, _step0_bytes(step0, snapshot))
        expected = _canonical_json(marker).encode("utf-8")
        roles = tuple(marker["files"]) + (READY_PATH, RESERVATION_PATH)
        with _held_parents(root, roles) as check:
            if _read_bytes(root / READY_PATH, **_identity(expected)) != expected:
                raise RunInputBundleRefused("input-ready marker bytes mismatch")
            reserved = _reservation(expected)
            if _read_bytes(root / RESERVATION_PATH, **_identity(reserved)) != reserved:
                raise RunInputBundleRefused("input reservation bytes mismatch")
            current = _installed_snapshot(root, plan)
            _same("input snapshot during verification", _marker(
                plan, run, current, config, _step0_bytes(step0, current),
            ), marker)
            _same("config during input verification", _configuration(root, run_id, condition)[3], config)
            check()
            return marker
    except RunInputBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, ManifestRefused, yaml.YAMLError) as error:
        raise RunInputBundleRefused("run input bundle verification refused") from error
