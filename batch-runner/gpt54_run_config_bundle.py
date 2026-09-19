"""Install exact comparison configs in an existing disposable source checkout.

This module never creates a checkout, stages data, dispatches a command or grants
launch permission. Complete individual files are published without replacement;
the ready marker is last, not a claim of a multi-file filesystem transaction.
"""

from __future__ import annotations

import json
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator

import yaml

from core.inference_manifest import _assert_no_symlink_ancestors
from gpt54_comparison_preflight import (
    ENVELOPE,
    ComparisonGradingPlan,
    ComparisonGradingRunSpec,
    ComparisonRunSpec,
    _canonical_json,
    compile_grading_plan,
)
from gpt54_prepared_input_attestation import _identity, _same
from gpt54_v2_grading_input import _read_bytes

READY_PATH = "comparison-bundle-ready.json"
MANIFEST_PATH = ENVELOPE + "gpt54_sandboxv2_codex_comparison.yaml"
COMBINED_PLAN_PATH = "comparison-plan.json"


class RunConfigBundleRefused(ValueError):
    """The disposable checkout is not the exact, complete compiled run bundle."""


def _root(checkout: Path) -> Path:
    path = Path(checkout)
    if ".." in path.parts:
        raise RunConfigBundleRefused("checkout parent traversal is forbidden")
    path = Path(os.path.abspath(path))
    _assert_no_symlink_ancestors(path)
    if not path.is_dir():
        raise RunConfigBundleRefused("a pre-existing checkout directory is required")
    return path


def _path(root: Path, role: str) -> Path:
    relative = PurePosixPath(role)
    if (type(role) is not str or relative.is_absolute() or ".." in relative.parts
            or not relative.parts or relative.as_posix() != role or "\\" in role):
        raise RunConfigBundleRefused("invalid run-relative bundle role")
    return root / role


@contextmanager
def _held_parents(root: Path, roles: tuple[str, ...]) -> Iterator[Callable[[], None]]:
    """Hold existing parent directories; refuse replacement before publication."""
    parents = {root}
    for role in roles:
        parent = _path(root, role).parent
        while parent != root:
            parents.add(parent)
            parent = parent.parent
    with ExitStack() as stack:
        opened = []
        for parent in sorted(parents):
            _assert_no_symlink_ancestors(parent)
            descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, descriptor)
            metadata = os.fstat(descriptor)
            opened.append((parent, metadata.st_dev, metadata.st_ino))

        def check() -> None:
            for parent, device, inode in opened:
                _assert_no_symlink_ancestors(parent)
                current = parent.stat()
                if (current.st_dev, current.st_ino) != (device, inode):
                    raise RunConfigBundleRefused("bundle parent changed")

        check()
        yield check


def _compiled(
    dispatch_run: ComparisonRunSpec, grading_run: ComparisonGradingRunSpec,
    manifest: dict[str, Any], combined_plan: dict[str, Any],
) -> ComparisonGradingPlan:
    if type(dispatch_run) is not ComparisonRunSpec or type(grading_run) is not ComparisonGradingRunSpec:
        raise RunConfigBundleRefused("exact typed dispatch and grading recipes are required")
    plan = compile_grading_plan(manifest)
    _same("combined dispatch/grading plan", combined_plan, plan.as_dict())
    index = next(index for index, run in enumerate(plan.dispatch.runs) if run.run_id == dispatch_run.run_id)
    _same("dispatch run recipe", dispatch_run.as_dict(), plan.dispatch.runs[index].as_dict())
    _same("grading run recipe", grading_run.as_dict(), plan.runs[index].as_dict())
    return plan


def _files(plan: ComparisonGradingPlan, run_id: str) -> dict[str, bytes]:
    index = next(index for index, run in enumerate(plan.dispatch.runs) if run.run_id == run_id)
    run, grading = plan.dispatch.runs[index], plan.runs[index]
    return {
        COMBINED_PLAN_PATH: plan.canonical_bytes(),
        run.config_path: run.config_json.encode("utf-8"),
        grading.grader_config_path: grading.grader_config_json.encode("utf-8"),
        grading.experiment_config_path: grading.experiment_config_json.encode("utf-8"),
    }


def _sources(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Check the target's pinned bytes, not only the compiler's own checkout."""
    manifest_data = _read_bytes(_path(root, MANIFEST_PATH))
    _same("checkout manifest", yaml.safe_load(manifest_data), manifest)
    source_files = {
        name: _identity(_read_bytes(_path(root, name), sha256=digest))
        for name, digest in sorted(manifest["source_pins"].items())
    }
    return {
        "manifest_file": {"path": MANIFEST_PATH, **_identity(manifest_data)},
        "source_files": source_files,
    }


def _marker(
    plan: ComparisonGradingPlan, run_id: str, files: dict[str, bytes], sources: dict[str, Any],
) -> dict[str, Any]:
    index = next(index for index, run in enumerate(plan.dispatch.runs) if run.run_id == run_id)
    run = plan.dispatch.runs[index]
    linkage = {
        "attestation_version": "gpt54-prepared-input-attestation-v1",
        "binding_version": "gpt54-pre-execution-input-v1",
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "combined_plan_sha256": _identity(plan.canonical_bytes())["sha256"],
        "source_pins_sha256": _identity(plan.dispatch.source_pins_json.encode("utf-8"))["sha256"],
        "config_sha256": _identity(files[run.config_path])["sha256"],
        "capture_path": "batch-runner/workspace/pre-execution-input.json",
    }
    return {
        "bundle_version": "gpt54-run-config-bundle-v1",
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "abba_index": index, "task_ids": list(run.task_ids),
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "combined_plan_sha256": linkage["combined_plan_sha256"],
        "source_base_sha": plan.dispatch.source_base_sha,
        "source_pins": json.loads(plan.dispatch.source_pins_json),
        **sources,
        "files": {name: _identity(data) for name, data in files.items()},
        "attestation_linkage": linkage,
        "evidence_boundary": "local_config_bundle_consistency",
    }


def _check_members(root: Path, plan: ComparisonGradingPlan, files: dict[str, bytes]) -> None:
    for name, expected in files.items():
        if _read_bytes(_path(root, name), **_identity(expected)) != expected:
            raise RunConfigBundleRefused("compiled bundle bytes mismatch")
    # A partial bundle from a different repeat must not be adopted either.
    for grading in plan.runs:
        if grading.experiment_config_path not in files and os.path.lexists(_path(root, grading.experiment_config_path)):
            raise RunConfigBundleRefused("another run's generated config is present")


def materialize_run_config_bundle(
    dispatch_run: ComparisonRunSpec, grading_run: ComparisonGradingRunSpec, *,
    manifest: dict[str, Any], combined_plan: dict[str, Any], checkout: Path,
) -> dict[str, Any]:
    """Publish four exact files and the final marker, or refuse without overwrite.

    Args:
        checkout: An existing disposable source tree with all parent directories.
        dispatch_run, grading_run: The matching typed compiler recipes.
        manifest, combined_plan: The exact preregistration and combined document.

    Returns:
        The canonical ready document. It contains linkage, not an attestation or
        inference identity approval, and is not launch authorization.

    Raises:
        RunConfigBundleRefused: On drift, unsafe paths, any collision or I/O error.
        Complete members may remain after a write failure; never reuse that tree.
    """
    from gpt54_codex_input_capture import _write_no_clobber

    try:
        root = _root(checkout)
        # Retain the exact supplied values through all filesystem operations.
        manifest = json.loads(_canonical_json(manifest))
        plan = _compiled(dispatch_run, grading_run, manifest, combined_plan)
        files = _files(plan, dispatch_run.run_id)
        roles = tuple(files) + (READY_PATH,)
        with _held_parents(root, roles) as check_parents:
            sources = _sources(root, manifest)
            reserved = set(roles) | {run.experiment_config_path for run in plan.runs}
            if any(os.path.lexists(_path(root, name)) for name in reserved):
                raise RunConfigBundleRefused("bundle target already exists; partial trees cannot be reused")
            marker = _marker(plan, dispatch_run.run_id, files, sources)
            marker_data = _canonical_json(marker).encode("utf-8")
            for name, data in files.items():
                check_parents()
                _write_no_clobber(_path(root, name), data)
            check_parents()
            _check_members(root, plan, files)
            _same("checkout sources after publication", _sources(root, manifest), sources)
            check_parents()
            # The only completion signal is last. No in-place cleanup, adoption,
            # replace fallback, source edit or fallible verification follows it.
            _write_no_clobber(root / READY_PATH, marker_data)
            return marker
    except RunConfigBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, yaml.YAMLError) as error:
        raise RunConfigBundleRefused("run config bundle publication refused") from error


def verify_run_config_bundle(*, checkout: Path, run_id: str, condition: str) -> dict[str, Any]:
    """Recompile and check marker and every byte before a comparison capture.

    This is read-only. A forged marker with hashes matching altered files is not
    sufficient: all bytes must match the reviewed compiler and target source pins.
    """
    try:
        root = _root(checkout)
        manifest = yaml.safe_load(_read_bytes(root / MANIFEST_PATH))
        plan = compile_grading_plan(manifest)
        run = next(run for run in plan.dispatch.runs if run.run_id == run_id)
        _same("bundle condition", condition, run.condition)
        files = _files(plan, run.run_id)
        with _held_parents(root, tuple(files) + (READY_PATH,)) as check_parents:
            sources = _sources(root, manifest)
            marker = _marker(plan, run.run_id, files, sources)
            expected = _canonical_json(marker).encode("utf-8")
            if _read_bytes(root / READY_PATH, **_identity(expected)) != expected:
                raise RunConfigBundleRefused("ready marker bytes mismatch")
            _check_members(root, plan, files)
            _same("checkout sources during verification", _sources(root, manifest), sources)
            check_parents()
            return marker
    except RunConfigBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError, yaml.YAMLError) as error:
        raise RunConfigBundleRefused("run config bundle verification refused") from error
