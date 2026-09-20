"""Publish exact local pilot inputs, not evidence of model consumption.

The parquet is copied byte-for-byte, never filtered or re-encoded. Only the
registered five-task reference closure is accepted. The ready document contains
run-relative roles and byte identities, not host paths, prompts or launch
permission. Partial publications are retained and cannot be adopted on retry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import gpt56_pilot_config_bundle as configs
import gpt56_sol_codex_pilot_preflight as pilot
from core.reference_integrity import validate_reference_relative_path
from core.source_identity import ordered_source_projection_sha256, source_task_projection_sha256
from gpt54_codex_input_capture import PARQUET_NAME, _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_prepared_input_attestation import _dataset_tasks, _reference_snapshot
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_run_input_bundle import _publication_parents
from gpt54_v2_grading_input import _read_bytes

PARQUET_PATH = "data/" + PARQUET_NAME
READY_PATH = "pilot-input-bundle-ready.json"
RESERVATION_SUFFIX = ".pilot-input-bundle-reservation.json"
BOUNDARY = "local_prepared_input_consistency_not_model_consumption"


class PilotInputBundleRefused(ValueError):
    """Static refusal codes only; caller paths and source contents stay private."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PilotInputBundleRefused("invalid_cli_arguments")


@dataclass(frozen=True)
class PilotInputBundle:
    document_json: str
    files: tuple[tuple[str, bytes], ...]

    def canonical_bytes(self) -> bytes:
        return self.document_json.encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.document_json)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PilotInputBundleRefused(code)


def _bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _digest(data: bytes) -> dict[str, Any]:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _absolute(path: Path) -> Path:
    path = Path(path)
    _require(".." not in path.parts, "source_parent_traversal")
    return Path(os.path.abspath(path))


def _overlap(first: Path, second: Path) -> bool:
    return first.is_relative_to(second) or second.is_relative_to(first)


def _destination(destination: Path) -> tuple[Path, Path]:
    root, _ = configs._destination(destination)
    return root, root.with_name(root.name + RESERVATION_SUFFIX)


def _reference_versions(plan: dict[str, Any]) -> dict[str, str]:
    dataset = plan["dataset"]
    versions = dict(dataset["input_file_versions"])
    _require(versions.pop(dataset["repo_id"] + "@" + dataset["revision"]) == dataset["parquet_sha256"],
             "dataset_version_mismatch")
    for role in versions:
        relative = validate_reference_relative_path(role)
        _require(relative.parts[0] == "reference_files" and len(relative.parts) > 1,
                 "reference_role_outside_closure")
    return versions


def _snapshot(
    plan: dict[str, Any], verified: configs.PilotConfigBundle, parquet: Path, references: Path,
    *, installed: bool = False,
) -> PilotInputBundle:
    """Use held bytes and the real source/reference validators, never live data."""
    prepared = json.loads(dict(verified.files)[configs.PREPARED_PATH])
    document = verified.as_dict()
    scope_keys = ("run_id", "condition", "repeat", "task_ids", "expected_task_count",
                  "ordered_task_ids_sha256", "tasks")
    scope = {key: prepared[key] for key in scope_keys}
    _require(_bytes(scope) == _bytes({key: document[key] for key in scope_keys})
             and _bytes(prepared["dataset"]) == _bytes(plan["dataset"]), "prepared_scope_mismatch")
    task_ids = tuple(scope["task_ids"])
    _require(len(task_ids) == len(set(task_ids)) == 5
             and list(task_ids) == [row["task_id"] for row in plan["dataset"]["tasks"]]
             and scope["run_id"] == pilot.RUN_ID and scope["condition"] == "codex_foundry"
             and scope["repeat"] == 1, "pilot_scope_mismatch")
    versions = _reference_versions(plan)
    data = _read_bytes(parquet, sha256=plan["dataset"]["parquet_sha256"])
    projections, needs_files = _dataset_tasks(data, task_ids)
    roles = [role for row in projections for role in row["reference_files"]]
    _require(len(roles) == len(set(roles)) and set(roles) == set(versions), "reference_ownership_mismatch")
    records = _reference_snapshot(references, versions, reference_subtree=installed)
    files = {PARQUET_PATH: data}
    for role, record in records.items():
        files[role] = _read_bytes(_path(references, role), **record)
    task_bindings = []
    for row, registered in zip(projections, scope["tasks"]):
        observed = {"task_id": row["task_id"], "prompt_sha256": _digest(row["prompt"].encode("utf-8"))["sha256"],
                    "reference_files": [{"path": role, "sha256": records[role]["sha256"]}
                                        for role in row["reference_files"]]}
        _require(_bytes(observed) == _bytes(registered), "task_projection_mismatch")
        task_bindings.append({
            "task_id": row["task_id"], "source_projection_sha256": source_task_projection_sha256(**row),
            "text_bytes": {key: _digest(row[key].encode("utf-8")) for key in ("prompt", "rubric_json", "rubric_pretty")},
            "reference_files": [{"path": role, **records[role]} for role in row["reference_files"]],
            "needs_files": needs_files[row["task_id"]],
        })
    ready = {
        "bundle_version": "foundry-pilot-input-bundle-v1", "evidence_boundary": BOUNDARY,
        **scope, "contract_sha256": document["contract_sha256"],
        "identity_plan_sha256": document["identity_plan_sha256"], "source_pins": document["source_pins"],
        "evidence_linkage": document["evidence_linkage"],
        "dataset": {**plan["dataset"], "parquet": {"path": PARQUET_PATH, **_digest(data)}},
        "config_bundle": {"path": configs.READY_PATH, **_digest(verified.canonical_bytes())},
        "config_reservation": _digest(configs._reservation(verified)),
        "prepared_manifest": {"path": configs.PREPARED_PATH, **_digest(dict(verified.files)[configs.PREPARED_PATH])},
        "source_tasks": task_bindings,
        "ordered_source_projection_sha256": ordered_source_projection_sha256(
            row["source_projection_sha256"] for row in task_bindings),
        "files": {role: _digest(content) for role, content in files.items()},
        "launch_allowed": False, "full_220_allowed": False,
    }
    return PilotInputBundle(_canonical_json(ready), tuple(files.items()))


def compile_pilot_input_bundle(
    plan: dict[str, Any], *, config_bundle: Path, identity_bundle: Path,
    dataset_parquet: Path, reference_root: Path, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotInputBundle:
    """Read and validate a complete local input closure; do not publish files."""
    try:
        plan = json.loads(_canonical_json(plan))
        parquet, references = _absolute(dataset_parquet), _root(reference_root)
        _require(not _overlap(parquet, references), "input_sources_overlap")
        with _held_parents(parquet.parent, (parquet.name,)) as check_parquet:
            with _held_parents(references, tuple(_reference_versions(plan))) as check_references:
                verified = configs.verify_pilot_config_bundle(
                    plan, bundle_root=config_bundle, identity_bundle=identity_bundle,
                    evidence_bundle=evidence_bundle, reviewed_source_sha=reviewed_source_sha, as_of=as_of,
                )
                result = _snapshot(plan, verified, parquet, references)
                check_parquet()
                check_references()
                return result
    except PilotInputBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, yaml.YAMLError):
        raise PilotInputBundleRefused("pilot_input_compile_refused") from None


def _reservation(bundle: PilotInputBundle) -> bytes:
    return _bytes({"reservation_version": "foundry-pilot-input-reservation-v1",
                   "ready_path": READY_PATH, "intended_ready": _digest(bundle.canonical_bytes())})


def _directories(files: tuple[tuple[str, bytes], ...]) -> tuple[str, ...]:
    roles = {parent.as_posix() for name, _ in files for parent in Path(name).parents if parent != Path(".")}
    return tuple(sorted(roles, key=lambda role: (len(Path(role).parts), role)))


def _members(root: Path, bundle: PilotInputBundle, *, published: bool) -> None:
    directories = set(_directories(bundle.files))
    expected_files = {name for name, _ in bundle.files} | ({READY_PATH} if published else set())
    found = set()
    for current, children, files in os.walk(root, followlinks=False):
        for name in children:
            path = Path(current) / name
            _require(stat.S_ISDIR(path.lstat().st_mode) and path.relative_to(root).as_posix() in directories,
                     "input_directory_set_mismatch")
        found.update((Path(current) / name).relative_to(root).as_posix() for name in files)
    _require(found == expected_files, "input_file_set_mismatch")
    for name, data in bundle.files:
        _require(_read_bytes(_path(root, name), **_digest(data)) == data, "input_bytes_mismatch")


def materialize_pilot_input_bundle(
    plan: dict[str, Any], *, config_bundle: Path, identity_bundle: Path,
    dataset_parquet: Path, reference_root: Path, destination: Path,
    evidence_bundle: Path | None = None, reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotInputBundle:
    """Reserve, exclusively publish, reverify, then write ready last.

    Only an absent destination with an existing safe parent is accepted. The
    caller retains every partial file/reservation after failure for manual
    disposition; this function never cleans, adopts or overwrites them.
    """
    try:
        plan = json.loads(_canonical_json(plan))
        root, reserved = _destination(destination)
        parquet, references = _absolute(dataset_parquet), _root(reference_root)
        for source in (pilot.ROOT, config_bundle, identity_bundle, evidence_bundle, parquet, references):
            if source is not None:
                source = _absolute(source)
                _require(not _overlap(root, source) and not _overlap(reserved, source), "source_destination_overlap")
        options = {"config_bundle": config_bundle, "identity_bundle": identity_bundle,
                   "dataset_parquet": parquet, "reference_root": references, "evidence_bundle": evidence_bundle,
                   "reviewed_source_sha": reviewed_source_sha, "as_of": as_of}
        with ExitStack() as descriptors, _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.callback(os.close, parent_fd)
            with _held_parents(parquet.parent, (parquet.name,)) as check_parquet:
                with _held_parents(references, tuple(_reference_versions(plan))) as check_references:
                    _require(not os.path.lexists(root) and not os.path.lexists(reserved), "destination_or_reservation_exists")
                    bundle = compile_pilot_input_bundle(plan, **options)
                    check_parent()
                    _write_no_clobber(reserved, _reservation(bundle))
                    check_parent()
                    os.mkdir(root.name, mode=0o700, dir_fd=parent_fd)
                    check_parent()
                    with _publication_parents(root) as (check_root, mkdir, data_existed):
                        _require(not data_existed, "input_directory_collision")
                        for role in _directories(bundle.files):
                            check_parent()
                            mkdir(_path(root, role))
                        for role, data in bundle.files:
                            check_parent()
                            check_root()
                            _write_no_clobber(_path(root, role), data)
                        _members(root, bundle, published=False)
                        current = compile_pilot_input_bundle(plan, **options)
                        _require(current == bundle, "input_or_config_changed_before_ready")
                        _members(root, bundle, published=False)
                        _read_bytes(reserved, **_digest(_reservation(bundle)))
                        check_parquet()
                        check_references()
                        check_root()
                        check_parent()
                        # No fallible verification follows ready publication.
                        _write_no_clobber(root / READY_PATH, bundle.canonical_bytes())
                        return bundle
    except PilotInputBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, yaml.YAMLError):
        raise PilotInputBundleRefused("pilot_input_publication_refused_no_reuse") from None


def verify_pilot_input_bundle(
    plan: dict[str, Any], *, config_bundle: Path, identity_bundle: Path, bundle_root: Path,
    evidence_bundle: Path | None = None, reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotInputBundle:
    """Recompute from installed bytes and real upstream verifiers, read-only."""
    try:
        plan = json.loads(_canonical_json(plan))
        root, reserved = _destination(bundle_root)
        roles = (PARQUET_PATH, *_reference_versions(plan), READY_PATH)
        options = {"bundle_root": config_bundle, "identity_bundle": identity_bundle,
                   "evidence_bundle": evidence_bundle, "reviewed_source_sha": reviewed_source_sha, "as_of": as_of}
        with _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            with _held_parents(_root(root), roles) as check_root:
                observed, reservation = _read_bytes(root / READY_PATH), _read_bytes(reserved)
                verified = configs.verify_pilot_config_bundle(plan, **options)
                bundle = _snapshot(plan, verified, root / PARQUET_PATH, root, installed=True)
                _require(observed == bundle.canonical_bytes() and reservation == _reservation(bundle),
                         "input_bundle_bytes_mismatch")
                _members(root, bundle, published=True)
                _require(configs.verify_pilot_config_bundle(plan, **options) == verified,
                         "config_changed_during_input_verification")
                _members(root, bundle, published=True)
                _read_bytes(root / READY_PATH, **_digest(bundle.canonical_bytes()))
                _read_bytes(reserved, **_digest(_reservation(bundle)))
                check_root()
                check_parent()
                return bundle
    except PilotInputBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, yaml.YAMLError):
        raise PilotInputBundleRefused("pilot_input_verification_refused") from None


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=pilot.PLAN)
    parser.add_argument("--config-bundle", type=Path, required=True)
    parser.add_argument("--identity-bundle", type=Path, required=True)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--destination", type=Path)
    output.add_argument("--verify-bundle", type=Path)
    parser.add_argument("--dataset-parquet", type=Path)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--evidence-bundle", type=Path)
    parser.add_argument("--reviewed-source-sha")
    parser.add_argument("--as-of")
    try:
        args = parser.parse_args(argv)
        plan = yaml.safe_load(_read_bytes(args.plan))
        options = {"config_bundle": args.config_bundle, "identity_bundle": args.identity_bundle,
                   "evidence_bundle": args.evidence_bundle, "reviewed_source_sha": args.reviewed_source_sha,
                   "as_of": args.as_of}
        if args.destination is not None:
            _require(args.dataset_parquet is not None and args.reference_root is not None, "source_inputs_required")
            bundle = materialize_pilot_input_bundle(
                plan, destination=args.destination, dataset_parquet=args.dataset_parquet,
                reference_root=args.reference_root, **options,
            )
        else:
            _require(args.dataset_parquet is None and args.reference_root is None, "unexpected_source_inputs")
            bundle = verify_pilot_input_bundle(plan, bundle_root=args.verify_bundle, **options)
        print(_canonical_json({"input_bundle_complete": True, "bundle_sha256": bundle.sha256,
                               "evidence_boundary": BOUNDARY, "launch_allowed": False, "full_220_allowed": False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        print(_canonical_json({"refusal_code": "pilot_input_bundle_refused", "input_bundle_complete": False,
                               "launch_allowed": False, "full_220_allowed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
