"""Bind local resource-ID bytes to verified Foundry evidence, without launching.

The candidate is parser-compatible, not an approved execution. Full resource
IDs and their host paths are never published. Only the deployment's final path
segment enters the candidate; source identities are role/size/SHA256 records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_config_bundle as configs
import gpt56_pilot_identity_plan as identity
import gpt56_pilot_input_bundle as inputs
import gpt56_sol_codex_pilot_preflight as pilot
from core.experiment_config import ExperimentConfig
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _read_bytes

CANDIDATE_PATH = "pilot-runtime-candidate.json"
BINDING_PATH = "pilot-deployment-binding.json"
READY_PATH = "pilot-deployment-binding-ready.json"
RESERVATION_SUFFIX = ".pilot-deployment-binding-reservation.json"
BOUNDARY = "offline_deployment_resource_binding_not_launch_or_execution"
RESOURCE_ROLES = ("account", "project", "deployment")
REMAINING_WORK = (
    "live_inference_identity_and_wire_unverified",
    "native_sandbox_and_result_bundle_host_unverified",
    "actual_pilot_execution_and_runtime_receipts_unverified",
)
_SECRET = re.compile(
    r"authorization|bearer|credential|password|api[-_]?key|client[-_]?secret|"
    r"(?:access|refresh|session|auth)[-_]?token|(?:^|[/._-])(?:sig|sas|token|secret)(?:$|[/._-])|"
    r"(?:^|/)sk-|gh[opusr]_|github_pat_|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.|"
    r"(?:^|/)[A-Fa-f0-9]{32,}(?:$|/)", re.IGNORECASE,
)


class PilotDeploymentBindingRefused(ValueError):
    """Static refusal codes only, never resource bytes, paths or parser text."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PilotDeploymentBindingRefused("invalid_cli_arguments")


@dataclass(frozen=True)
class PilotDeploymentBinding:
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
        raise PilotDeploymentBindingRefused(code)


def _bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _digest(data: bytes) -> dict[str, Any]:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _resource_path(path: Path) -> Path:
    path = Path(path)
    _require(".." not in path.parts and bool(path.name), "unsafe_resource_file_path")
    path = Path(os.path.abspath(path))
    _root(path.parent)
    return path


def _resource_bytes(path: Path) -> bytes:
    metadata = path.lstat()
    _require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
             and 0 < metadata.st_size <= 4096, "unsafe_resource_file")
    return _read_bytes(path, size=metadata.st_size)


def _resource_parts(data: bytes, role: str) -> tuple[str, ...]:
    """Validate a closed ARM path vocabulary without normalizing its identity."""
    text = data.decode("utf-8")
    _require(text.startswith("/") and not _SECRET.search(text), "invalid_resource_id")
    # A trailing slash is allowed, but its original byte still participates in
    # the evidence digest. Interior empty segments and traversal are forbidden.
    parts = tuple(text.removesuffix("/").split("/")[1:])
    _require(all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.()-]{0,127}", part)
                 and part not in (".", "..") for part in parts), "invalid_resource_id")
    _require(len(parts) >= 8 and parts[0] == "subscriptions"
             and re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", parts[1]) is not None
             and parts[2] == "resourceGroups" and parts[4:7] == (
                 "providers", "Microsoft.CognitiveServices", "accounts"), "invalid_resource_id")
    valid = (role == "account" and len(parts) == 8
             or role == "project" and len(parts) == 10 and parts[8] == "projects"
             or role == "deployment" and len(parts) == 10 and parts[8] == "deployments")
    _require(valid, "resource_role_mismatch")
    return parts


def _runtime(template: dict[str, Any], deployment: str) -> dict[str, Any]:
    """Fill the sealed request with a hash-bound deployment, not a model label."""
    dispatch, limits = template["dispatch"], template["dispatch"]["limits"]
    request, route = dispatch["codex_request"], dispatch["foundry_route"]
    _require(template["deployment"] is template["execution"] is None
             and template["runnable"] is False, "inert_template_required")
    candidate = {
        "experiment": {"id": dispatch["run_id"], "name": "Foundry GPT-5.6 Sol five-task candidate"},
        "data": {"source": template["dataset"]["repo_id"], "filter": {"task_ids": dispatch["task_ids"]}},
        "condition_a": {
            "name": dispatch["condition"],
            "model": {"provider": dispatch["identity"]["provider"], "deployment": deployment,
                      "reasoning_effort": request["reasoning_effort"]},
            "prompt": {"system": template["developer_instructions"]},
            "qa": {"enabled": limits["self_qa_enabled"]},
        },
        "execution": {
            "mode": route["execution_mode"], "timeout": limits["timeout_seconds_per_attempt"],
            "max_retries": limits["infrastructure_retries_per_task"],
            "resume_max_rounds": limits["resume_max_rounds"],
            "tokens": limits["inactive_generic_token_settings"],
            "codex": {"endpoint_from_route": route["endpoint_from_route"],
                      "provider_id": route["provider_id"], "model": deployment,
                      **request, "request_max_retries": limits["request_max_retries"],
                      "stream_max_retries": limits["stream_max_retries"]},
        },
        "output": {"publish_to_hf": dispatch["results"]["publish_to_hf"],
                   "submit_to_evals": dispatch["results"]["submit_to_evals"],
                   "save_path": "results/" + dispatch["run_id"]},
    }
    # This is only parsing and static validation. In the route-deferred branch
    # the parser does not read credentials, resolve an endpoint or build a client.
    parsed = ExperimentConfig.from_dict(json.loads(_bytes(candidate)))
    _require(not parsed.validate(), "runtime_candidate_invalid")
    _require(parsed.experiment_id == dispatch["run_id"] and parsed.condition_b is None
             and parsed.data_filter.task_ids == dispatch["task_ids"]
             and len(parsed.data_filter.task_ids) == 5 and parsed.data_filter.sample_size is None
             and parsed.condition_a.model.provider == "azure"
             and parsed.condition_a.model.deployment == parsed.execution.codex["model"] == deployment
             and parsed.execution.mode == "codex_foundry"
             and parsed.condition_a.model.reasoning_effort == parsed.execution.codex["reasoning_effort"] == "max"
             and parsed.execution.codex["model_context_window"] == 1_000_000
             and parsed.execution.resume_max_rounds == 0 and parsed.condition_a.qa.enabled is False
             and dispatch["identity"]["model"] == "gpt-5.6-sol" and dispatch["identity"]["fast_mode"] is False
             and dispatch["logical_attempts_per_task"] == dispatch["repeat"] == 1
             and dispatch["pilot_controls"]["fresh_session_per_attempt"] is True
             and dispatch["pilot_controls"]["relay_max_runs"] == 0
             and dispatch["pilot_controls"]["auto_escalation"] is False, "runtime_candidate_contract_mismatch")
    return candidate


def compile_pilot_deployment_binding(
    plan: dict[str, Any], *, evidence_bundle: Path, identity_bundle: Path,
    config_bundle: Path, input_bundle: Path, reviewed_source_sha: str, as_of: str,
    account_resource_id_file: Path, project_resource_id_file: Path, deployment_resource_id_file: Path,
) -> PilotDeploymentBinding:
    """Read all real verifiers and exact ID files; return private canonical bytes."""
    try:
        plan = json.loads(_canonical_json(plan))
        paths = tuple(_resource_path(path) for path in (
            account_resource_id_file, project_resource_id_file, deployment_resource_id_file,
        ))
        _require(len(set(paths)) == 3, "distinct_resource_files_required")
        with ExitStack() as held:
            checks = [held.enter_context(_held_parents(path.parent, (path.name,))) for path in paths]
            raw = tuple(_resource_bytes(path) for path in paths)
            parts = tuple(_resource_parts(data, role) for role, data in zip(RESOURCE_ROLES, raw))
            account, project, deployment = parts
            _require(project[:8] == deployment[:8] == account, "resource_hierarchy_mismatch")
            options = {"evidence_bundle": evidence_bundle, "reviewed_source_sha": reviewed_source_sha, "as_of": as_of}
            ev = evidence.verify_foundry_evidence(bundle_root=evidence_bundle, reviewed_source_sha=reviewed_source_sha, as_of=as_of)
            ident = identity.verify_pilot_identity(plan, bundle_root=identity_bundle, **options)
            config = configs.verify_pilot_config_bundle(plan, bundle_root=config_bundle, identity_bundle=identity_bundle, **options)
            prepared = inputs.verify_pilot_input_bundle(
                plan, bundle_root=input_bundle, config_bundle=config_bundle, identity_bundle=identity_bundle, **options,
            )
            ev_doc, ident_doc, config_doc, input_doc = ev.as_dict(), ident.as_dict(), config.as_dict(), prepared.as_dict()
            linkage = {"ready_bundle_sha256": ev.sha256, "reviewed_source_sha": reviewed_source_sha,
                       "as_of": ev_doc["evaluated_at"]}
            _require(not ev.missing and ev_doc["evidence_complete"] is True
                     and ev_doc["plan_sha256"] == pilot.seal(plan) and ev_doc["run_id"] == plan["pilot"]["run_id"]
                     and all(_bytes(doc["evidence_linkage"]) == _bytes(linkage) for doc in (ident_doc, config_doc, input_doc))
                     and config_doc["identity_plan_sha256"] == input_doc["identity_plan_sha256"] == ident.sha256
                     and input_doc["config_bundle"] == {"path": configs.READY_PATH, **_digest(config.canonical_bytes())},
                     "upstream_bundle_linkage_mismatch")
            subject = ev_doc["claims"]["identity"]["evidence"]["subject"]
            resources = {}
            for role, data in zip(RESOURCE_ROLES, raw):
                record = {"role": role + "_resource_id", "encoding": "utf-8", **_digest(data)}
                _require(record["sha256"] == subject[role]["resource_id_sha256"], "resource_digest_mismatch")
                resources[role] = record
            template = json.loads(dict(config.files)[configs.RUNTIME_PATH])
            manifest = json.loads(dict(config.files)[configs.PREPARED_PATH])
            dispatch = ident_doc["dispatch"]
            scope_keys = ("run_id", "condition", "repeat", "task_ids", "expected_task_count", "ordered_task_ids_sha256", "tasks")
            scope = {key: dispatch[key] for key in scope_keys}
            _require(all(_bytes(scope) == _bytes({key: doc[key] for key in scope_keys})
                         for doc in (manifest, config_doc, input_doc, ident_doc["grading"]))
                     and _bytes(template["dispatch"]) == _bytes(dispatch), "five_task_scope_mismatch")
            runtime_data = _bytes(_runtime(template, parts[2][-1]))
            upstream = {
                "evidence": {"ready_sha256": ev.sha256, "reservation": _digest(evidence._reservation(ev))},
                "identity": {"plan_sha256": ident.sha256, "ready": _digest(identity._ready(ident)),
                             "reservation": _digest(identity._reservation(ident))},
                "config": {"ready_sha256": config.sha256, "reservation": _digest(configs._reservation(config))},
                "input": {"ready_sha256": prepared.sha256, "reservation": _digest(inputs._reservation(prepared))},
            }
            binding = {
                "binding_version": "foundry-pilot-deployment-binding-v1", "evidence_boundary": BOUNDARY,
                **scope, "contract_sha256": pilot.seal(plan), "source_pins": plan["source_pins"],
                "resource_files": resources, "upstream_bundles": upstream, "evidence_linkage": linkage,
                "dispatch": dispatch, "dataset": plan["dataset"],
                "candidate": {"path": CANDIDATE_PATH, **_digest(runtime_data)},
                "remaining_work": list(REMAINING_WORK), "launch_allowed": False, "full_220_allowed": False,
            }
            files = ((CANDIDATE_PATH, runtime_data), (BINDING_PATH, _bytes(binding)))
            ready = {
                "bundle_version": "foundry-pilot-deployment-binding-ready-v1", "evidence_boundary": BOUNDARY,
                **scope, "contract_sha256": pilot.seal(plan), "source_pins": plan["source_pins"],
                "evidence_linkage": linkage, "upstream_bundles": upstream, "resource_files": resources,
                "files": {name: _digest(data) for name, data in files}, "remaining_work": list(REMAINING_WORK),
                "launch_allowed": False, "full_220_allowed": False,
            }
            # Recheck the upstream chain after deriving the candidate. This
            # also catches changes during parsing, not only between publish
            # phases. The input verifier invokes the real config, identity and
            # evidence verifiers again; no cached verdict can waive drift.
            _require(inputs.verify_pilot_input_bundle(
                plan, bundle_root=input_bundle, config_bundle=config_bundle, identity_bundle=identity_bundle, **options,
            ) == prepared, "upstream_changed_during_compile")
            for path, data, check in zip(paths, raw, checks):
                _read_bytes(path, **_digest(data))
                check()
            return PilotDeploymentBinding(_canonical_json(ready), files)
    except PilotDeploymentBindingRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, yaml.YAMLError):
        raise PilotDeploymentBindingRefused("pilot_deployment_compile_refused") from None


def _destination(destination: Path) -> tuple[Path, Path]:
    root, _ = configs._destination(destination)
    return root, root.with_name(root.name + RESERVATION_SUFFIX)


def _reservation(bundle: PilotDeploymentBinding) -> bytes:
    return _bytes({"reservation_version": "foundry-pilot-deployment-reservation-v1",
                   "ready_path": READY_PATH, "intended_ready": _digest(bundle.canonical_bytes())})


def _members(root: Path, bundle: PilotDeploymentBinding, *, published: bool) -> None:
    expected = {name for name, _ in bundle.files} | ({READY_PATH} if published else set())
    _require({path.name for path in root.iterdir()} == expected, "deployment_member_set_mismatch")
    for name, data in bundle.files:
        _read_bytes(_path(root, name), **_digest(data))


def materialize_pilot_deployment_binding(
    plan: dict[str, Any], *, destination: Path, **options: Any,
) -> PilotDeploymentBinding:
    """Reserve, exclusively publish, reverify, write ready last; never clean up."""
    try:
        root, reserved = _destination(destination)
        for source in (pilot.ROOT, *(options[key] for key in ("evidence_bundle", "identity_bundle", "config_bundle", "input_bundle"))):
            source = _root(source)
            _require(not inputs._overlap(root, source), "source_destination_overlap")
        for role in RESOURCE_ROLES:
            source = _resource_path(options[role + "_resource_id_file"])
            _require(not inputs._overlap(root, source) and source != reserved, "source_destination_overlap")
        with ExitStack() as held, _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            held.callback(os.close, parent_fd)
            check_parent()
            _require(not os.path.lexists(root) and not os.path.lexists(reserved), "destination_or_reservation_exists")
            bundle = compile_pilot_deployment_binding(plan, **options)
            check_parent()
            _write_no_clobber(reserved, _reservation(bundle))
            check_parent()
            os.mkdir(root.name, mode=0o700, dir_fd=parent_fd)
            check_parent()
            with _held_parents(root, (CANDIDATE_PATH, BINDING_PATH, READY_PATH)) as check_root:
                for name, data in bundle.files:
                    check_parent()
                    check_root()
                    _write_no_clobber(_path(root, name), data)
                _members(root, bundle, published=False)
                _require(compile_pilot_deployment_binding(plan, **options) == bundle, "binding_changed_before_ready")
                _members(root, bundle, published=False)
                _read_bytes(reserved, **_digest(_reservation(bundle)))
                check_root()
                check_parent()
                _write_no_clobber(root / READY_PATH, bundle.canonical_bytes())
                return bundle
    except PilotDeploymentBindingRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise PilotDeploymentBindingRefused("pilot_deployment_publication_refused_no_reuse") from None


def verify_pilot_deployment_binding(
    plan: dict[str, Any], *, bundle_root: Path, **options: Any,
) -> PilotDeploymentBinding:
    """Recompute from current verified upstreams and private resource files."""
    try:
        root, reserved = _destination(bundle_root)
        roles = (CANDIDATE_PATH, BINDING_PATH, READY_PATH)
        with _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            with _held_parents(_root(root), roles) as check_root:
                observed = tuple(_read_bytes(_path(root, name)) for name in roles)
                reservation = _read_bytes(reserved)
                bundle = compile_pilot_deployment_binding(plan, **options)
                _require(observed == tuple(data for _, data in bundle.files) + (bundle.canonical_bytes(),)
                         and reservation == _reservation(bundle), "deployment_binding_bytes_mismatch")
                _members(root, bundle, published=True)
                _read_bytes(root / READY_PATH, **_digest(bundle.canonical_bytes()))
                _read_bytes(reserved, **_digest(_reservation(bundle)))
                check_root()
                check_parent()
                return bundle
    except PilotDeploymentBindingRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise PilotDeploymentBindingRefused("pilot_deployment_verification_refused") from None


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=pilot.PLAN)
    for name in ("evidence-bundle", "identity-bundle", "config-bundle", "input-bundle",
                 *(role + "-resource-id-file" for role in RESOURCE_ROLES)):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--as-of", required=True)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--destination", type=Path)
    output.add_argument("--verify-bundle", type=Path)
    try:
        args = parser.parse_args(argv)
        options = {name: value for name, value in vars(args).items() if name not in ("plan", "destination", "verify_bundle")}
        plan = yaml.safe_load(_read_bytes(args.plan))
        bundle = (materialize_pilot_deployment_binding(plan, destination=args.destination, **options)
                  if args.destination is not None else verify_pilot_deployment_binding(plan, bundle_root=args.verify_bundle, **options))
        print(_canonical_json({"deployment_binding_complete": True, "bundle_sha256": bundle.sha256,
                               "evidence_boundary": BOUNDARY, "launch_allowed": False, "full_220_allowed": False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        print(_canonical_json({"deployment_binding_complete": False, "refusal_code": "pilot_deployment_binding_refused",
                               "launch_allowed": False, "full_220_allowed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
