"""Compile and seal an inert Foundry pilot dispatch/grading identity offline.

No argv, runnable experiment or grader config is emitted. The fixed grader
template is a historical identity, not a five-task config ready for execution.
Local consistency grants neither inference identity nor launch authorization.
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

import gpt56_foundry_evidence_intake as evidence
import gpt56_sol_codex_pilot_preflight as pilot
from core.execution_envelope_tasks import (
    FULL_RUN_TASK_COUNT, TaskCatalog, reference_files_for, select_advance_check_tasks,
)
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _object, _read_bytes

PLAN_PATH = "foundry-pilot-identity-plan.json"
READY_PATH = "foundry-pilot-identity-ready.json"
RESERVATION_SUFFIX = ".foundry-pilot-identity-reservation.json"
BOUNDARY = "offline_dispatch_grading_identity"
BLOCKER = "pilot_dispatch_and_grading_identity_not_wired"


class PilotIdentityRefused(ValueError):
    """Static refusal codes only; never render input paths or evidence values."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PilotIdentityRefused("invalid_cli_arguments")


@dataclass(frozen=True)
class PilotIdentityPlan:
    """Immutable canonical recipes, not an executable or approved run."""

    document_json: str

    def canonical_bytes(self) -> bytes:
        return self.document_json.encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.document_json)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PilotIdentityRefused(code)


def _bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _identity(data: bytes) -> dict[str, Any]:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _grader_identity(plan: dict[str, Any]) -> dict[str, Any]:
    # Only the real parser/validator, source hash and static prompt-version
    # helper are used. No Grader, RubricLoader or provider is constructed.
    import step8_grade as step8

    root = _root(pilot.ROOT)
    batch = _root(root / "batch-runner")
    contract = plan["grading"]
    config_path = _path(root, contract["template"])
    config_data = _read_bytes(config_path, sha256=plan["source_pins"][contract["template"]])
    config = yaml.safe_load(config_data)
    validation_copy = json.loads(_canonical_json(config))
    for key in ("template", "tool_template"):
        if key in config["prompt"]:
            validation_copy["prompt"][key] = str(_path(batch, config["prompt"][key]))
    step8.validate_grading_config(validation_copy)

    # Match step8's source closure and reuse its hashing algorithm. The extra
    # reads enforce single-link safety, which the runtime source hash alone
    # does not promise. No dependency or downloaded rubric is fetched here.
    core = _root(batch / "core")
    sources = [
        batch / "step8_grade.py", *sorted(core.rglob("*.py")),
        _path(root, plan["results"]["grade_schema"]),
        *step8._requirements_closure(batch, batch / "requirements.txt"),
        batch / "scripts/download_inference_from_hf.py",
        _path(batch, config["prompt"]["template"]),
        _path(batch, step8.resolve_tool_prompt_path(config).as_posix()),
    ]
    checked = dict(step8._checked_grader_source_file(batch, path) for path in sources)
    checked[contract["template"]] = config_path
    with _held_parents(root, tuple(checked)) as check:
        snapshot = {
            name: _read_bytes(path, sha256=plan["source_pins"].get(name))
            for name, path in checked.items()
        }
        source_hash = step8.compute_grader_source_hash(config_path, config, batch_root=batch)
        _require(source_hash == plan["dispatch_grading_identity"]["grader_template_source_hash"],
                 "grader_template_source_drift")
        for name, data in snapshot.items():
            _require(_read_bytes(checked[name], **_identity(data)) == data, "grader_source_changed")
        check()

    tool_role = "batch-runner/" + step8.resolve_tool_prompt_path(config).as_posix()
    prompt_version = step8.Grader._extract_prompt_version(snapshot[tool_role].decode("utf-8"))
    _require(prompt_version == config["prompt"]["version"] == contract["prompt_version"],
             "grader_prompt_version_mismatch")
    _require(config["judge"]["model"] == contract["judge_model"]
             and config["judge"]["reasoning"]["effort"] == contract["judge_effort"]
             and config["rubric"]["revision"] == contract["rubric_revision"], "grader_contract_mismatch")
    schema_role = plan["results"]["grade_schema"]
    schema = json.loads(snapshot[schema_role], object_pairs_hook=_object)
    _require(step8.SCHEMA_VERSION == plan["results"]["grade_schema_version"]
             and step8.SCHEMA_VERSION in schema["properties"]["schema_version"]["enum"],
             "grade_schema_version_mismatch")
    return {
        "entrypoint": "batch-runner/step8_grade.py",
        "template": {"path": contract["template"], **_identity(config_data),
                     "config_schema_version": config["schema_version"]},
        "historical_source_sha": contract["source_sha"],
        "template_source_hash": source_hash,
        "rubric": {key: config["rubric"][key] for key in ("source", "repo_id", "revision")},
        "prompt": {"version": prompt_version, "path": tool_role, **_identity(snapshot[tool_role])},
        "judge": {"model": contract["judge_model"], "reasoning_effort": contract["judge_effort"]},
        "grade_schema": {"path": schema_role, "version": step8.SCHEMA_VERSION,
                         **_identity(snapshot[schema_role])},
        "passes_per_task": contract["passes_per_task"],
        "inference_repo_id": None,
        "inference_revision": contract["inference_revision"],
        "reuse_baseline_rerun_identity": contract["reuse_baseline_rerun_identity"],
        "runnable_config": False,
    }


def _evidence_link(
    plan: dict[str, Any], bundle_root: Path | None, reviewed_source_sha: str | None, as_of: str | None,
) -> dict[str, Any] | None:
    if bundle_root is None and reviewed_source_sha is None and as_of is None:
        return None
    _require(bundle_root is not None and type(reviewed_source_sha) is str and type(as_of) is str,
             "complete_evidence_arguments_required")
    bundle = evidence.verify_foundry_evidence(
        bundle_root=bundle_root, reviewed_source_sha=reviewed_source_sha, as_of=as_of,
    )
    document = bundle.as_dict()
    _require(not bundle.missing and document["evidence_complete"] is True
             and document["plan_sha256"] == pilot.seal(plan)
             and document["run_id"] == plan["pilot"]["run_id"]
             and document["reviewed_source_sha"] == reviewed_source_sha
             and _bytes(document["source_pins"]) == _bytes(plan["source_pins"]), "evidence_link_mismatch")
    return {
        "ready_bundle_sha256": bundle.sha256,
        "reviewed_source_sha": reviewed_source_sha,
        # The bundle's sealed evaluation time is stable. Each verification
        # still uses the caller's current as_of for freshness, never this time.
        "as_of": document["evaluated_at"],
    }


def compile_pilot_identity(
    plan: dict[str, Any], *, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotIdentityPlan:
    """Read pinned local contracts; return canonical recipes without executing."""
    try:
        active, _ = evidence._active_plan()
        _require(_bytes(plan) == _bytes(active), "active_contract_mismatch")
        plan = active
        catalog_role = pilot.ENVELOPE + "gdpval_task_catalog.json"
        catalog_data = _read_bytes(_path(pilot.ROOT, catalog_role), sha256=plan["dataset"]["catalog_sha256"])
        catalog = TaskCatalog.from_mapping(json.loads(catalog_data, object_pairs_hook=_object))
        _require(catalog.dataset_repo_id == plan["dataset"]["repo_id"]
                 and catalog.dataset_revision == plan["dataset"]["revision"]
                 and catalog.dataset_file_sha256 == plan["dataset"]["parquet_sha256"]
                 and len(catalog.tasks) == len(catalog.by_task_id()) == FULL_RUN_TASK_COUNT,
                 "catalog_identity_mismatch")
        selected = select_advance_check_tasks(catalog, catalog_fingerprint=plan["dataset"]["catalog_sha256"])
        task_ids = list(selected.task_ids)
        _require(task_ids == [task["task_id"] for task in plan["dataset"]["tasks"]]
                 and len(task_ids) == len(set(task_ids)) == 5, "ordered_task_scope_mismatch")
        versions = plan["dataset"]["input_file_versions"]
        dataset_key = plan["dataset"]["repo_id"] + "@" + plan["dataset"]["revision"]
        _require(set(versions) == {dataset_key, *reference_files_for(task_ids, catalog)}
                 and versions[dataset_key] == plan["dataset"]["parquet_sha256"], "input_version_set_mismatch")
        tasks = []
        for task_id in task_ids:
            task = catalog.by_task_id()[task_id]
            references = []
            for role in task.reference_file_paths:
                _path(pilot.ROOT, role)
                references.append({"path": role, "sha256": versions[role]})
            tasks.append({"task_id": task_id, "prompt_sha256": task.prompt_sha256,
                          "reference_files": references})
        grading = _grader_identity(plan)
        from step8_grade import _ordered_task_ids_sha256

        scope = {"run_id": plan["pilot"]["run_id"], "condition": "codex_foundry",
                 "repeat": 1, "task_ids": task_ids, "expected_task_count": 5,
                 "ordered_task_ids_sha256": _ordered_task_ids_sha256(task_ids), "tasks": tasks}
        dispatch = {
            **scope, "logical_attempts_per_task": 1,
            "identity": plan["identity"], "foundry_route": plan["foundry_route"],
            "codex_request": plan["codex_request"], "pilot_controls": plan["pilot"],
            "developer_instructions": _identity(plan["developer_instructions"].encode("utf-8")),
            "limits": plan["limits"], "results": plan["results"], "cost": plan["cost"],
        }
        grading = {**scope, **grading, "receipt_contract": plan["results"]}
        _require(_bytes(dispatch["tasks"]) == _bytes(grading["tasks"])
                 and _bytes(dispatch["task_ids"]) == _bytes(grading["task_ids"]), "dispatch_grading_scope_mismatch")
        linkage = _evidence_link(plan, evidence_bundle, reviewed_source_sha, as_of)
        document = {
            "plan_version": "foundry-pilot-dispatch-grading-identity-v1", "evidence_boundary": BOUNDARY,
            "contract_path": pilot.ACTIVE_PLAN, "contract_sha256": pilot.seal(plan),
            "contract_base_sha": plan["base_sha"],
            "compiler_source_base_sha": plan["dispatch_grading_identity"]["source_base_sha"],
            "run_id": plan["pilot"]["run_id"], "source_pins": plan["source_pins"],
            "dataset": plan["dataset"], "dispatch": dispatch, "grading": grading,
            "evidence_linkage": linkage, "launch_allowed": False, "full_220_allowed": False,
        }
        current, _ = evidence._active_plan()
        _require(_bytes(current) == _bytes(plan), "contract_changed_during_compile")
        return PilotIdentityPlan(_canonical_json(document))
    except PilotIdentityRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError, yaml.YAMLError):
        raise PilotIdentityRefused("pilot_identity_compile_refused") from None


def _destination(destination: Path) -> tuple[Path, Path]:
    # Reuse the strict absent-bundle path vocabulary; no evidence files are
    # created by this helper. This bundle has its own reservation role.
    root, _ = evidence._destination(destination)
    return root, root.with_name(root.name + RESERVATION_SUFFIX)


def _ready(plan: PilotIdentityPlan) -> bytes:
    document = plan.as_dict()
    return _bytes({
        "marker_version": "foundry-pilot-identity-ready-v1", "evidence_boundary": BOUNDARY,
        "plan": {"path": PLAN_PATH, **_identity(plan.canonical_bytes())},
        "run_id": document["run_id"], "contract_sha256": document["contract_sha256"],
        "source_pins": document["source_pins"], "evidence_linkage": document["evidence_linkage"],
        "launch_allowed": False, "full_220_allowed": False,
    })


def _reservation(plan: PilotIdentityPlan) -> bytes:
    return _bytes({"reservation_version": "foundry-pilot-identity-reservation-v1",
                   "ready_path": READY_PATH, "intended_ready": _identity(_ready(plan))})


def _members(root: Path, *, published: bool) -> None:
    _require({path.name for path in root.iterdir()} == {PLAN_PATH} | ({READY_PATH} if published else set()),
             "identity_bundle_member_set_mismatch")


def publish_pilot_identity(
    plan: dict[str, Any], *, destination: Path, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotIdentityPlan:
    """Reserve an absent destination and publish ready last; never clean or reuse."""
    try:
        root, reserved = _destination(destination)
        source_root = _root(pilot.ROOT)
        _require(not root.is_relative_to(source_root) and not source_root.is_relative_to(root),
                 "source_destination_overlap")
        if evidence_bundle is not None:
            external = _root(evidence_bundle)
            _require(not root.is_relative_to(external) and not external.is_relative_to(root),
                     "evidence_destination_overlap")
        options = {"evidence_bundle": evidence_bundle, "reviewed_source_sha": reviewed_source_sha, "as_of": as_of}
        with ExitStack() as descriptors, _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.callback(os.close, parent_fd)
            _require(not os.path.lexists(root) and not os.path.lexists(reserved), "destination_or_reservation_exists")
            compiled = compile_pilot_identity(plan, **options)
            check_parent()
            _write_no_clobber(reserved, _reservation(compiled))
            check_parent()
            os.mkdir(root.name, mode=0o700, dir_fd=parent_fd)
            check_parent()
            with _held_parents(root, (PLAN_PATH, READY_PATH)) as check_root:
                _write_no_clobber(root / PLAN_PATH, compiled.canonical_bytes())
                _members(root, published=False)
                _read_bytes(root / PLAN_PATH, **_identity(compiled.canonical_bytes()))
                current = compile_pilot_identity(plan, **options)
                _require(current == compiled, "identity_changed_before_ready")
                _read_bytes(root / PLAN_PATH, **_identity(compiled.canonical_bytes()))
                _read_bytes(reserved, **_identity(_reservation(compiled)))
                _members(root, published=False)
                check_root()
                check_parent()
                _write_no_clobber(root / READY_PATH, _ready(compiled))
                return compiled
    except PilotIdentityRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise PilotIdentityRefused("pilot_identity_publication_refused_no_reuse") from None


def verify_pilot_identity(
    plan: dict[str, Any], *, bundle_root: Path, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> PilotIdentityPlan:
    """Recompute exact recipes, sources, evidence and all published marker bytes."""
    try:
        root, reserved = _destination(bundle_root)
        with _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            with _held_parents(_root(root), (PLAN_PATH, READY_PATH)) as check_root:
                _members(root, published=True)
                # Unsafe, missing or linked members fail before compiling the
                # grader identity. Hold their bytes, then exact-match recipes.
                files = (root / PLAN_PATH, root / READY_PATH, reserved)
                observed = tuple(_read_bytes(path) for path in files)
                compiled = compile_pilot_identity(
                    plan, evidence_bundle=evidence_bundle, reviewed_source_sha=reviewed_source_sha, as_of=as_of,
                )
                expected = (compiled.canonical_bytes(), _ready(compiled), _reservation(compiled))
                _require(observed == expected, "identity_bundle_bytes_mismatch")
                for path, data in zip(files, expected):
                    _read_bytes(path, **_identity(data))
                _members(root, published=True)
                check_root()
                check_parent()
                return compiled
    except PilotIdentityRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise PilotIdentityRefused("pilot_identity_verification_refused") from None


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=pilot.PLAN)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--destination", type=Path)
    output.add_argument("--verify-bundle", type=Path)
    parser.add_argument("--evidence-bundle", type=Path)
    parser.add_argument("--reviewed-source-sha")
    parser.add_argument("--as-of")
    try:
        args = parser.parse_args(argv)
        plan = yaml.safe_load(_read_bytes(args.plan))
        options = {"evidence_bundle": args.evidence_bundle, "reviewed_source_sha": args.reviewed_source_sha,
                   "as_of": args.as_of}
        if args.destination is not None:
            compiled = publish_pilot_identity(plan, destination=args.destination, **options)
        elif args.verify_bundle is not None:
            compiled = verify_pilot_identity(plan, bundle_root=args.verify_bundle, **options)
        else:
            compiled = compile_pilot_identity(plan, **options)
        print(_canonical_json({"plan_sha256": compiled.sha256, "identity_complete": True,
                               "evidence_boundary": BOUNDARY, "launch_allowed": False, "full_220_allowed": False}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        print(_canonical_json({"refusal_code": "pilot_identity_refused", "identity_complete": False,
                               "launch_allowed": False, "full_220_allowed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
