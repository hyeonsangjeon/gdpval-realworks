"""Materialize inert pilot configs from an exact, verified identity bundle.

These files are not a checkout, prepared input bytes, an inference identity or
launch permission. The runtime template is deliberately not an ExperimentConfig:
a requested model label is not a reviewed deployment name. The existing step8
validator accepts the derived grading template; its future five-task execution
scope is sealed separately, not smuggled into an ignored grader setting or a
fabricated rerun revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import gpt56_pilot_identity_plan as identity
import gpt56_sol_codex_pilot_preflight as pilot
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _read_bytes

RUNTIME_PATH = "pilot-runtime-config.json"
PREPARED_PATH = "pilot-prepared-task-manifest.json"
GRADING_PATH = "pilot-grading-config.json"
LINKAGE_PATH = "pilot-identity-linkage.json"
READY_PATH = "pilot-config-bundle-ready.json"
RESERVATION_SUFFIX = ".pilot-config-bundle-reservation.json"
BOUNDARY = "offline_pilot_config_bundle"
RUNTIME_TEMPLATE_VERSION = "foundry-pilot-runtime-template-v1"
DEPLOYMENT_BLOCKER = "actual_pilot_deployment_not_prepared"


class PilotConfigBundleRefused(ValueError):
    """Static codes only; input paths and external evidence are never echoed."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PilotConfigBundleRefused("invalid_cli_arguments")


@dataclass(frozen=True)
class PilotConfigBundle:
    """Immutable file bytes and their canonical ready document, never commands."""

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
        raise PilotConfigBundleRefused(code)


def _bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _digest(data: bytes) -> dict[str, Any]:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _validate_runtime_template(
    template: dict[str, Any], plan: dict[str, Any], dispatch: dict[str, Any],
) -> None:
    """Check a closed local template, not an executable runner configuration."""
    _require(type(template) is dict and set(template) == {
        "template_version", "runnable", "deployment", "execution", "dispatch", "dataset",
        "developer_instructions", "deployment_blocker", "launch_allowed", "full_220_allowed",
    }, "runtime_template_shape_invalid")
    _require(template["template_version"] == RUNTIME_TEMPLATE_VERSION
             and template["runnable"] is False
             and template["deployment"] is plan["foundry_identity"]["deployment"] is None
             and template["execution"] is None
             and template["deployment_blocker"] == DEPLOYMENT_BLOCKER
             and template["launch_allowed"] is template["full_220_allowed"] is False
             and _bytes(template["dispatch"]) == _bytes(dispatch)
             and _bytes(template["dataset"]) == _bytes(plan["dataset"])
             and template["developer_instructions"] == plan["developer_instructions"],
             "runtime_template_contract_mismatch")


def _runtime(plan: dict[str, Any], dispatch: dict[str, Any]) -> dict[str, Any]:
    """Keep requested model identity separate from a future reviewed deployment."""
    # The legacy parser supplies runnable defaults for absent blocks. Explicit
    # null execution makes it reject this template before provider/auth setup,
    # independently of the bundle's outer launch flags.
    template = {
        "template_version": RUNTIME_TEMPLATE_VERSION, "runnable": False,
        "deployment": None, "execution": None, "dispatch": dispatch, "dataset": plan["dataset"],
        "developer_instructions": plan["developer_instructions"],
        "deployment_blocker": DEPLOYMENT_BLOCKER,
        "launch_allowed": False, "full_220_allowed": False,
    }
    _validate_runtime_template(template, plan, dispatch)
    return template


def _grading(document: dict[str, Any]) -> dict[str, Any]:
    import step8_grade as step8

    recipe = document["grading"]
    template = recipe["template"]
    data = _read_bytes(_path(_root(pilot.ROOT), template["path"]),
                       size=template["size"], sha256=template["sha256"])
    original = yaml.safe_load(data)
    _require(set(original) == {"schema_version", "config_name", "description", "rerun_identity",
                               "judge", "rubric", "grader", "tpm_guard", "prompt", "output"},
             "grader_template_keys_changed")
    config = {key: value for key, value in original.items()
              if key not in {"config_name", "description", "rerun_identity"}}
    config["config_name"] = document["run_id"] + "_v2_sol_max"
    config["description"] = (
        "Inert pilot grader template. The bundle seals five-task scope; "
        "real inference identity and execution-time scope binding are still required."
    )
    # The filename contract is unchanged; a future output stays run-local.
    config["output"] = {**original["output"], "directory": "workspace/pilot-grades"}
    _require(recipe["inference_repo_id"] is None and recipe["inference_revision"] is None
             and recipe["reuse_baseline_rerun_identity"] is False, "future_inference_identity_required")

    # This validates the actual emitted config through the real YAML parser and
    # step8 validator. Only the validation copy resolves prompt paths; no host
    # absolute path or fabricated revision enters the canonical output.
    validation = yaml.safe_load(_bytes(config))
    batch = _root(pilot.ROOT / "batch-runner")
    for key in ("template", "tool_template"):
        if key in validation["prompt"]:
            validation["prompt"][key] = str(_path(batch, validation["prompt"][key]))
    step8.validate_grading_config(validation)
    return config


def compile_pilot_config_bundle(
    plan: dict[str, Any], *, identity_bundle: Path, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotConfigBundle:
    """Reverify #633 and derive four canonical local files without execution."""
    try:
        plan = json.loads(_canonical_json(plan))
        verified = identity.verify_pilot_identity(
            plan, bundle_root=identity_bundle, evidence_bundle=evidence_bundle,
            reviewed_source_sha=reviewed_source_sha, as_of=as_of,
        )
        document = verified.as_dict()
        dispatch, grading = document["dispatch"], document["grading"]
        scope_keys = ("run_id", "condition", "repeat", "task_ids", "expected_task_count",
                      "ordered_task_ids_sha256", "tasks")
        scope = {key: dispatch[key] for key in scope_keys}
        _require(_bytes(scope) == _bytes({key: grading[key] for key in scope_keys}),
                 "dispatch_grading_scope_mismatch")
        runtime = _runtime(plan, dispatch)
        grader = _grading(document)
        prepared = {
            "manifest_version": "foundry-pilot-prepared-task-manifest-v1", **scope,
            "dataset": document["dataset"], "developer_instructions": dispatch["developer_instructions"],
            "evidence_boundary": "registered_inputs_not_consumed_bytes",
        }
        files = {RUNTIME_PATH: _bytes(runtime), PREPARED_PATH: _bytes(prepared), GRADING_PATH: _bytes(grader)}
        linkage = {
            "linkage_version": "foundry-pilot-config-identity-v1", "evidence_boundary": BOUNDARY,
            "identity_plan": {"path": identity.PLAN_PATH, **_digest(verified.canonical_bytes())},
            "identity_ready": {"path": identity.READY_PATH, **_digest(identity._ready(verified))},
            "identity_reservation": _digest(identity._reservation(verified)),
            "contract_path": document["contract_path"], "contract_sha256": document["contract_sha256"],
            "contract_base_sha": document["contract_base_sha"],
            "source_pins": document["source_pins"], "evidence_linkage": document["evidence_linkage"],
            "dispatch": dispatch, "grading": grading,
            "files": {name: _digest(data) for name, data in files.items()},
            # The step8 config has no ignored task keys or historical rerun
            # identity. The bundle owns scope until real inference is bound.
            "grading_scope_binding": "inert_bundle_only_requires_future_inference_identity",
            "materialized_grader_source_hash": None,
            "launch_allowed": False, "full_220_allowed": False,
        }
        files[LINKAGE_PATH] = _bytes(linkage)
        ready = {
            "bundle_version": "foundry-pilot-config-bundle-v1", "evidence_boundary": BOUNDARY,
            **scope, "contract_sha256": document["contract_sha256"],
            "identity_plan_sha256": verified.sha256, "source_pins": document["source_pins"],
            "evidence_linkage": document["evidence_linkage"],
            "files": {name: _digest(data) for name, data in files.items()},
            "launch_allowed": False, "full_220_allowed": False,
        }
        return PilotConfigBundle(_canonical_json(ready), tuple(files.items()))
    except PilotConfigBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, yaml.YAMLError):
        raise PilotConfigBundleRefused("pilot_config_compile_refused") from None


def _destination(destination: Path) -> tuple[Path, Path]:
    root, _ = identity._destination(destination)
    return root, root.with_name(root.name + RESERVATION_SUFFIX)


def _reservation(bundle: PilotConfigBundle) -> bytes:
    return _bytes({"reservation_version": "foundry-pilot-config-reservation-v1",
                   "ready_path": READY_PATH, "intended_ready": _digest(bundle.canonical_bytes())})


def _members(root: Path, files: tuple[tuple[str, bytes], ...], *, published: bool) -> None:
    expected = {name for name, _ in files} | ({READY_PATH} if published else set())
    _require({path.name for path in root.iterdir()} == expected, "config_bundle_member_set_mismatch")
    for name, data in files:
        _require(_read_bytes(_path(root, name), **_digest(data)) == data, "config_bundle_bytes_mismatch")


def materialize_pilot_config_bundle(
    plan: dict[str, Any], *, identity_bundle: Path, destination: Path,
    evidence_bundle: Path | None = None, reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotConfigBundle:
    """Reserve → publish files → reverify → ready last; never clean or reuse."""
    try:
        root, reserved = _destination(destination)
        for source in (pilot.ROOT, identity_bundle, evidence_bundle):
            if source is not None:
                source = _root(source)
                _require(not root.is_relative_to(source) and not source.is_relative_to(root),
                         "source_destination_overlap")
        options = {"identity_bundle": identity_bundle, "evidence_bundle": evidence_bundle,
                   "reviewed_source_sha": reviewed_source_sha, "as_of": as_of}
        with ExitStack() as descriptors, _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.callback(os.close, parent_fd)
            check_parent()
            _require(not os.path.lexists(root) and not os.path.lexists(reserved), "destination_or_reservation_exists")
            bundle = compile_pilot_config_bundle(plan, **options)
            check_parent()
            _write_no_clobber(reserved, _reservation(bundle))
            check_parent()
            os.mkdir(root.name, mode=0o700, dir_fd=parent_fd)
            check_parent()
            with _held_parents(root, tuple(name for name, _ in bundle.files) + (READY_PATH,)) as check_root:
                for name, data in bundle.files:
                    check_parent()
                    check_root()
                    _write_no_clobber(_path(root, name), data)
                _members(root, bundle.files, published=False)
                current = compile_pilot_config_bundle(plan, **options)
                _require(current == bundle, "identity_or_config_changed_before_ready")
                _members(root, bundle.files, published=False)
                _read_bytes(reserved, **_digest(_reservation(bundle)))
                check_root()
                check_parent()
                # Nothing fallible follows readiness. A failed publication
                # retains the reservation/partial files for manual disposition.
                _write_no_clobber(root / READY_PATH, bundle.canonical_bytes())
                return bundle
    except PilotConfigBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise PilotConfigBundleRefused("pilot_config_publication_refused_no_reuse") from None


def verify_pilot_config_bundle(
    plan: dict[str, Any], *, identity_bundle: Path, bundle_root: Path,
    evidence_bundle: Path | None = None, reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotConfigBundle:
    """Recompute from the current identity, never trust self-consistent hashes."""
    try:
        root, reserved = _destination(bundle_root)
        roles = (RUNTIME_PATH, PREPARED_PATH, GRADING_PATH, LINKAGE_PATH, READY_PATH)
        with _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            with _held_parents(_root(root), roles) as check_root:
                observed = tuple(_read_bytes(_path(root, name)) for name in roles)
                observed_reservation = _read_bytes(reserved)
                bundle = compile_pilot_config_bundle(
                    plan, identity_bundle=identity_bundle, evidence_bundle=evidence_bundle,
                    reviewed_source_sha=reviewed_source_sha, as_of=as_of,
                )
                _require(observed == tuple(data for _, data in bundle.files) + (bundle.canonical_bytes(),)
                         and observed_reservation == _reservation(bundle), "config_bundle_bytes_mismatch")
                _members(root, bundle.files, published=True)
                _read_bytes(root / READY_PATH, **_digest(bundle.canonical_bytes()))
                _read_bytes(reserved, **_digest(_reservation(bundle)))
                check_root()
                check_parent()
                return bundle
    except PilotConfigBundleRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise PilotConfigBundleRefused("pilot_config_verification_refused") from None


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=pilot.PLAN)
    parser.add_argument("--identity-bundle", type=Path, required=True)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--destination", type=Path)
    output.add_argument("--verify-bundle", type=Path)
    parser.add_argument("--evidence-bundle", type=Path)
    parser.add_argument("--reviewed-source-sha")
    parser.add_argument("--as-of")
    try:
        args = parser.parse_args(argv)
        plan = yaml.safe_load(_read_bytes(args.plan))
        options = {"identity_bundle": args.identity_bundle, "evidence_bundle": args.evidence_bundle,
                   "reviewed_source_sha": args.reviewed_source_sha, "as_of": args.as_of}
        if args.destination is not None:
            bundle = materialize_pilot_config_bundle(plan, destination=args.destination, **options)
        elif args.verify_bundle is not None:
            bundle = verify_pilot_config_bundle(plan, bundle_root=args.verify_bundle, **options)
        else:
            bundle = compile_pilot_config_bundle(plan, **options)
        print(_canonical_json({"bundle_sha256": bundle.sha256, "config_bundle_complete": True,
                               "evidence_boundary": BOUNDARY, "launch_allowed": False, "full_220_allowed": False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        print(_canonical_json({"refusal_code": "pilot_config_bundle_refused", "config_bundle_complete": False,
                               "launch_allowed": False, "full_220_allowed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
