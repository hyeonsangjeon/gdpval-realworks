"""Execute the first registered observation's prepared F grader once.

Preparation is not permission. A separately digest-bound direction and an
exclusive, durable claim in the caller's named local attempt store precede
every child/provider effect. This is not distributed once-only admission.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from typing import Any, Iterator

import codex_budget_pilot as owned
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_grading_preparation as preparation
import step8_grade as step8
from core.agentic_v2_preregistration import seal
from core.cost_projection import project_cost_ledger_reference, verify_cost_ledger
from core.cost_receipts import ledger_reference
from core.experiment_config import ExperimentConfig
from core.grade_payload import validate_grade_payload
from core.rubric_loader import RubricLoader
from core.task_checkpoint import checkpoint_path, load_checkpoint
from core.time_budget_observation_deadline import ObservationIdentity
from ghcp_vm_input_bundle import _held_parents, _publication_parents, _write_no_clobber
from gpt54_comparison_preflight import GRADER, load_plan
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _path
from gpt54_v2_grading_input import _object, _read_bytes, _same

HELPER = "batch-runner/gpt54_time_budget_grading_execution.py"
FIRST_RUN = "gpt54_time_budget_v1_v2_r1"
FIRST_TASK = "02aa1805-c658-4069-8a6a-02dec146063a"
EXPERIMENT = "source/batch-runner/experiments/" + FIRST_RUN + ".yaml"
DIRECTION_VERSION = "time-budget-first-f-grading-direction-v1"
RESULT = "grading-execution.json"
RESERVATION_SUFFIX = ".time-budget-grade-execution-reserved.json"
# Reuse the existing Step8/owned-grader envelope, not the generation deadline.
STEP8_SECONDS = 14_400
CHILD_SECONDS = 14_520
MAX_METADATA_BYTES = 8 * 1024 * 1024
MAX_GRADE_BYTES = 16 * 1024 * 1024


class GradingExecutionRefused(ValueError):
    """No new attempt is authorized; retain any claim or partial state."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise GradingExecutionRefused(reason)


def _encoded(value: Any) -> bytes:
    return preparation._json_bytes(value)


def _expected(value: dict, *, maximum: int = MAX_METADATA_BYTES) -> dict:
    identity = preparation._expected_file(value)
    _require(identity["size"] <= maximum, "metadata_size_bound")
    return identity


def _document(path: Path, identity: dict) -> tuple[bytes, dict]:
    data = _read_bytes(path, **_expected(identity))
    value = json.loads(data, object_pairs_hook=_object)
    _require(type(value) is dict, "object_required")
    _encoded(value)  # Reject non-finite/duplicate JSON, not just matching bytes.
    return data, value


def _absolute(value: Path) -> Path:
    path = registration._handoff_path(value)
    _require(Path(value).is_absolute() and str(value) == str(path), "canonical_absolute_path_required")
    return path


def execution_context_sha256() -> str:
    """Hash local boot/namespace/user/interpreter/CI metadata, never credentials.

    This describes the intended process context, not provider authentication or
    kernel cleanup capability. The owned child's actual handshake is separate.
    """
    _require(sys.platform == "linux", "linux_execution_context_required")
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    _require(re.fullmatch(r"[0-9a-f-]{36}", boot) is not None, "execution_context_unavailable")
    namespaces = {name: os.readlink("/proc/self/ns/" + name) for name in ("pid", "mnt", "user")}
    ci = {name: os.environ.get(name) for name in
          ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "RUNNER_NAME")}
    _require(not any(ci.values()) or all(ci.values()), "incomplete_ci_execution_context")
    return seal({"boot": boot, "namespaces": namespaces, "uid": os.getuid(),
                 "python": sys.executable, "python_version": list(sys.version_info[:3]), "ci": ci})


def _observation_key(observation: ObservationIdentity) -> str:
    # Do not let new source/input bytes, a copy or a destination fork a repeat.
    return seal({name: getattr(observation, name) for name in
                 ("study_id", "run_id", "condition", "repeat", "task_id")})


@dataclass(frozen=True)
class GradingExecutionBinding:
    """Checked facts for the concrete direction checker, not permission."""

    canonical_json: str

    def as_dict(self) -> dict:
        return json.loads(self.canonical_json)


def require_execution_direction(binding: GradingExecutionBinding, *, direction_file: Path,
                                expected_direction_sha256: str) -> None:
    """Require an independently supplied digest and a current exact binding."""
    _require(type(binding) is GradingExecutionBinding, "checked_grading_binding_required")
    _require(type(expected_direction_sha256) is str and
             re.fullmatch(r"[0-9a-f]{64}", expected_direction_sha256) is not None,
             "independent_direction_digest_required")
    path = _absolute(direction_file)
    size = path.lstat().st_size
    _require(0 < size <= 64 * 1024, "direction_size_bound")
    _, direction = _document(path, {"sha256": expected_direction_sha256, "size": size})
    _require(set(direction) == {"direction_version", "binding", "not_before", "expires_at"},
             "direction_schema_refused")
    _require(direction["direction_version"] == DIRECTION_VERSION and
             direction["binding"] == binding.as_dict(), "direction_binding_mismatch")
    start, end = direction["not_before"], direction["expires_at"]
    _require(type(start) is int and type(end) is int and 0 <= start < end and
             start <= time.time() < end, "direction_admission_window_refused")
    _require(binding.as_dict()["execution_context_sha256"] == execution_context_sha256(),
             "actual_execution_context_mismatch")


def _experiment(plan: dict, observation: ObservationIdentity) -> bytes:
    # Same grading-only ExperimentConfig mapping as the existing V2 compiler;
    # no legacy dispatch/grading plan and no alternate generation recipe.
    config = {
        "experiment": {"id": observation.run_id, "name": "Time-budget V2 grading metadata",
                       "description": "Grading metadata only; not an inference recipe."},
        "data": {"source": plan["shared"]["dataset"]["repo_id"], "filter": {"task_ids": [FIRST_TASK]}},
        "condition_a": {"name": "sandbox_v2", "model": {"provider": "azure",
            "deployment": plan["shared"]["model"]["deployment"], "reasoning_effort": "xhigh"},
            "qa": {"enabled": False}},
        "execution": {"mode": "agentic_sandbox_v2", "agentic_v2": {
            "tool_contract_version": "2.0", "policy_profile_id": "offline-full-v1", "foundation_only": True}},
        "output": {"publish_to_hf": False, "submit_to_evals": False},
    }
    _require(not ExperimentConfig.from_dict(config).validate(), "grading_experiment_metadata_refused")
    return _encoded(config)


@contextmanager
def _checked_preparation(plan: dict, arguments: dict) -> Iterator[dict]:
    """Reconstruct the accepted preparation's exact files using real validators."""
    a = arguments
    observation = a["observation"]
    _require(type(observation) is ObservationIdentity, "independent_observation_required")
    _require((observation.run_id, observation.condition, observation.repeat, observation.task_id) ==
             (FIRST_RUN, "sandbox_v2", 1, FIRST_TASK), "first_registered_v2_observation_only")
    _same("independent observation bytes", _identity(_encoded(asdict(observation))),
          _expected(a["expected_observation_identity"]))
    _same("independent input bytes", _identity(_encoded(a["expected_input_binding"])),
          _expected(a["expected_input_binding_identity"]))
    _same("independent input binding", seal(a["expected_input_binding"]), observation.input_sha256)
    anchors = tuple(a[name] for name in ("runtime_root", "expected_reviewed_source_sha",
                                       "frozen_grader_root", "expected_grader_source_sha"))
    output = a["preparation_directory"]
    ready_data, marker = _document(output / preparation.READY, a["expected_preparation_identity"])
    reservation = output.with_name(output.name + preparation.RESERVATION_SUFFIX)
    with ExitStack() as sources:
        compiled = registration._compile_registration(plan, anchors, True, sources)
        runs = [run for run in compiled.runs if run.run_id == observation.run_id and FIRST_TASK in run.task_ids]
        _require(len(runs) == 1, "registered_observation_required")
        run = runs[0]
        evidence = json.loads(compiled.source_evidence_json)
        _same("observation registration", observation.registration_sha256, compiled.manifest_sha256)
        _same("observation R", (observation.reviewed_source_sha, observation.reviewed_source_tree),
              (a["expected_reviewed_source_sha"], evidence["runtime"]["source_tree"]))
        _, _, helper = sources.enter_context(registration._reviewed_source(
            a["runtime_root"], a["expected_reviewed_source_sha"], {preparation.HELPER}))
        _same("preparation helper source", helper[preparation.HELPER], _identity(_read_bytes(Path(preparation.__file__))))
        frozen, tree, frozen_files = sources.enter_context(registration._reviewed_source(
            a["frozen_grader_root"], a["expected_grader_source_sha"], registration._frozen_roles()))
        catalog, task_ids, input_source = sources.enter_context(registration._observation_input_registration(
            a["input_registration_root"], a["expected_input_source_sha"], a["input_registration_path"],
            plan["shared"]["dataset"]))
        controller_roles = (registration.REQUIRED_SOURCES | registration.RUNTIME_ADDITIONS |
                            registration._frozen_roles() | {HELPER, preparation.HELPER,
                            "batch-runner/codex_budget_pilot.py", "batch-runner/step8_grade.py"})
        controller, controller_tree, controller_files = sources.enter_context(registration._reviewed_source(
            a["controller_root"], a["expected_controller_source_sha"], controller_roles))
        _same("controller tree", controller_tree, a["expected_controller_source_tree"])
        live_root = Path(__file__).resolve().parents[1]
        live_check = sources.enter_context(_held_parents(live_root, tuple(controller_files)))
        for role, identity in controller_files.items():
            _read_bytes(_path(live_root, role), **identity)

        def inputs() -> dict:
            snapshot, step0 = registration._observation_inputs(plan["shared"]["dataset"], catalog,
                task_ids, parquet=a["dataset_parquet"], references=a["reference_root"], step0=None)
            value = preparation._inputs(plan, run, observation, input_source, snapshot, step0)
            _same("independent inputs", value, a["expected_input_binding"])
            return value

        verified_inputs = inputs()
        result_identity = _expected(a["expected_result_identity"])
        result_data, result, deliverables, fingerprint = preparation._result(
            a["result_path"], result_identity, observation, plan, a["deliverables_root"])
        # F Step8's real Track-2 contract, with no invented inference revision.
        repo_id, revision = step8.resolve_source_inference_identity(result, "2.0")
        _same("canonical inference source", (result.get("source_repo_id"), result.get("source_revision")),
              (repo_id, revision))
        _require(repo_id != plan["shared"]["dataset"]["repo_id"] and revision not in {
            plan["shared"]["dataset"]["revision"], a["expected_reviewed_source_sha"],
            a["expected_grader_source_sha"]}, "dataset_or_runtime_is_not_inference_revision")
        files = {"source/" + role: _read_bytes(frozen / role, **identity)
                 for role, identity in frozen_files.items() if role.startswith("batch-runner/")}
        config = load_plan(frozen / GRADER)
        config["rubric"].update(revision=plan["shared"]["grading"]["rubric_revision"],
                                cache_dir="../data/gdpval-local")
        preparation._validate_config(config, frozen)
        files[preparation.CONFIG] = _encoded(config)
        files[preparation.RESULT] = result_data
        files.update({preparation.UPLOAD + "/" + role: data for role, data in deliverables.items()})
        rubric = config["rubric"]
        snapshot_role = preparation.CACHE + "/rubric_snapshots/" + rubric["revision"]
        files[snapshot_role + "/data/registered.parquet"] = _read_bytes(
            a["dataset_parquet"], **verified_inputs["dataset"]["parquet"])
        cache = preparation.CACHE + "/datasets--" + rubric["repo_id"].replace("/", "--") + "/snapshots/" + rubric["revision"]
        for row in verified_inputs["reference_file_records"]:
            files[cache + "/" + row["path"]] = _read_bytes(
                _path(a["reference_root"], row["path"]), sha256=row["sha256"], size=row["size"])
        loader = RubricLoader(rubric["repo_id"], rubric["revision"], str(output / preparation.CACHE))
        files[snapshot_role + "/" + loader.MANIFEST_FILENAME] = _encoded(
            loader._build_snapshot_manifest(output / snapshot_role))
        loader._validate_snapshot(output / snapshot_role)
        rubric_task = loader.load(FIRST_TASK)
        preparation._validate_config(config, output / "source")
        materialized = step8.compute_grader_source_hash(output / preparation.CONFIG, config,
                                                       batch_root=output / "source/batch-runner")
        _require(materialized != registration.FROZEN_TEMPLATE_SHA256, "template_is_not_materialized_grader")
        intent = {
            "observation": asdict(observation), "input_binding_sha256": seal(verified_inputs),
            "result_identity": result_identity,
            "runtime_source": {name: evidence["runtime"][name] for name in ("source_sha", "source_tree")},
            "frozen_grader_source": {"source_sha": a["expected_grader_source_sha"], "source_tree": tree},
            "config": {"path": preparation.CONFIG, **_identity(files[preparation.CONFIG])},
            "grading_policy": plan["grading_policy"], "grading_attempt": 1,
            "launch_allowed": False, "execution_enabled": False,
        }
        reservation_data = _encoded({"reservation_version": "time-budget-f-grading-v1", "intent": intent,
                                     "ready_path": preparation.READY})
        expected_marker = {
            "preparation_version": "time-budget-f-derived-grading-v1", **intent,
            "reservation": {"path": reservation.name, **_identity(reservation_data)},
            "registration_file": evidence["runtime"]["manifest_file"],
            "preparation_helper": {"path": preparation.HELPER, **helper[preparation.HELPER]},
            "grader": {"template_path": GRADER, "template_source_sha256": registration.FROZEN_TEMPLATE_SHA256,
                "config_path": str(output / preparation.CONFIG), "config_file": intent["config"],
                "materialized_source_sha256": materialized, "execution_source": "source",
                "working_directory": "source/batch-runner", "entrypoint": "source/batch-runner/step8_grade.py",
                "derivation": "regular_tracked_F_source_blobs_not_a_runtime_checkout"},
            "inputs": verified_inputs,
            "result": {"original_path": str(a["result_path"]),
                "file": {"path": preparation.RESULT, **result_identity}, "result_fingerprint": fingerprint,
                "status": result["results"][0]["status"],
                "terminal_reason": result["time_budget_observation"]["terminal_reason"]},
            "files": {role: _identity(data) for role, data in sorted(files.items())},
            "evidence_boundary": "model_free_grading_preparation_not_attempt_or_execution_authority",
        }
        _same("exact grading preparation", marker, expected_marker)
        files[preparation.READY] = ready_data
        directories = {parent for role in files for parent in _path(output, role).parents
                       if parent != output and parent.is_relative_to(output)}
        held = sources.enter_context(_held_parents(output, tuple(files)))
        external = [(a["dataset_parquet"].parent, (a["dataset_parquet"].name,)),
                    (a["result_path"].parent, (a["result_path"].name,)),
                    (reservation.parent, (reservation.name,)),
                    (a["reference_root"], tuple(row["path"] for row in verified_inputs["reference_file_records"])),
                    (a["deliverables_root"], tuple(deliverables))]
        checks = [sources.enter_context(_held_parents(root, roles)) for root, roles in external]

        def reread(*, initial: bool = False, installed: bool = False) -> None:
            _same("input final reread", inputs(), verified_inputs)
            _require(preparation._result(a["result_path"], result_identity,
                     observation, plan, a["deliverables_root"])
                     == (result_data, result, deliverables, fingerprint), "grading_result_changed")
            _read_bytes(reservation, **_identity(reservation_data))
            for role, data in files.items():
                _read_bytes(_path(output, role), **_identity(data))
            for role, identity in controller_files.items():
                _read_bytes(_path(live_root, role), **identity)
            live_check()
            _same("executing materialized grader", step8.compute_grader_source_hash(
                output / preparation.CONFIG, config, batch_root=output / "source/batch-runner"), materialized)
            held()
            for check in checks:
                check()
            if initial:
                preparation._members(output, files, directories)
            if installed:
                preparation._members(output, {**files, EXPERIMENT: _experiment(plan, observation)}, directories)

        reread(initial=True)
        experiment = _experiment(plan, observation)
        batch = output / "source/batch-runner"
        grade = step8.resolve_grade_output_path(config, experiment_id=FIRST_RUN,
            judge_slug=step8._judge_slug(config["judge"]["model"]), config_hash=_identity(files[preparation.CONFIG])["sha256"][:16],
            rubric_sha=rubric["revision"], rubric_short_sha=rubric["revision"][:7],
            prompt_version=config["prompt"]["version"], inference_sha=revision,
            grader_source_hash=materialized, diagnostic_task_scope_sha=step8._ordered_task_ids_sha256([FIRST_TASK]))
        grade = (batch / grade).resolve()
        _require(grade.is_relative_to(output / "source/data/grades"), "grade_output_path_refused")
        yield {"marker": marker, "config": config, "files": files, "result": result, "grade_path": grade,
            "experiment": experiment, "reread": reread, "batch": batch,
            "rubric_item_ids": [item.rubric_item_id for item in rubric_task.rubric_items],
            "controller": {"source_sha": a["expected_controller_source_sha"], "source_tree": controller_tree,
                           "helper": {"path": HELPER, **controller_files[HELPER]}}}


def _execution_binding(checked: dict, arguments: dict) -> GradingExecutionBinding:
    """Describe checked facts; only the concrete direction checker can admit."""
    a = arguments
    metadata = a["attempt_store"].stat()
    command = [sys.executable, str(checked["batch"] / "step8_grade.py"), FIRST_RUN,
        "--config", str(a["preparation_directory"] / preparation.CONFIG),
        "--source", "local", "--tasks", FIRST_TASK, "--limit", "1", "--source-experiment-id", FIRST_RUN]
    value = {
        "observation": asdict(a["observation"]), "registered_observation_key": _observation_key(a["observation"]),
        "observation_file": _expected(a["expected_observation_identity"]),
        "input_binding_file": _expected(a["expected_input_binding_identity"]),
        "preparation_file": _expected(a["expected_preparation_identity"]),
        "controller": checked["controller"], "runtime_source": checked["marker"]["runtime_source"],
        "frozen_grader_source": checked["marker"]["frozen_grader_source"], "grader": checked["marker"]["grader"],
        "result": checked["marker"]["result"], "inputs": checked["marker"]["inputs"],
        "execution_context_sha256": a["expected_execution_context_sha256"],
        "paths": {name: str(a[name]) for name in ("runtime_root", "frozen_grader_root", "input_registration_root",
            "controller_root", "dataset_parquet", "reference_root", "result_path", "deliverables_root",
            "preparation_directory", "attempt_store", "destination", "direction_file")},
        "attempt_store_identity": {"device": metadata.st_dev, "inode": metadata.st_ino},
        "experiment_file": {"path": EXPERIMENT, **_identity(checked["experiment"])}, "command": command,
        "working_directory": str(checked["batch"]), "grade_path": str(checked["grade_path"]),
        "step8_seconds": STEP8_SECONDS, "child_seconds": CHILD_SECONDS, "external_grading_attempts": 1,
        "once_only_scope": "this_independently_named_local_attempt_store_not_distributed_global",
    }
    return GradingExecutionBinding(_encoded(value).decode())


def _durable_write(path: Path, data: bytes, descriptor: int) -> None:
    _write_no_clobber(path, data, parent_fd=descriptor)
    os.fsync(descriptor)  # The exclusive link itself must be durable before launch.
    _read_bytes(path, **_identity(data))


def _environment(destination: Path) -> dict[str, str]:
    # Same private/local-only child channel policy as the existing owned grader.
    removed = {"GITHUB_TOKEN", "GH_TOKEN", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "GITHUB_ENV",
        "ACTIONS_RUNTIME_TOKEN", "ACTIONS_RUNTIME_URL", "ACTIONS_CACHE_URL", "ACTIONS_RESULTS_URL",
        "CODEX_HOME", "HF_TOKEN_PATH", "PYTHONPATH", "PYTHONHOME"}
    env = {key: value for key, value in os.environ.items() if key not in removed and not
           ("TOKEN" in key.upper() and (key.upper().startswith("HF_") or "HUGGING" in key.upper()))}
    env.update(HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
               HF_HOME=str(destination / "empty-hf-home"), PYTHONDONTWRITEBYTECODE="1",
               GRADER_TIME_BUDGET_SEC=str(STEP8_SECONDS))
    return env


def _grade(path: Path, checked: dict) -> tuple[bytes, dict]:
    _require(path.lstat().st_size <= MAX_GRADE_BYTES, "grade_size_bound")
    data = _read_bytes(path)
    payload = json.loads(data, object_pairs_hook=_object)
    schema = json.loads(checked["files"]["source/batch-runner/schemas/grade.schema.json"])
    validate_grade_payload(payload, schema)
    marker, config, result = checked["marker"], checked["config"], checked["result"]
    step8._validate_grade_resume_identity(payload, experiment_id=FIRST_RUN,
        rubric_commit_sha=config["rubric"]["revision"], prompt_version=config["prompt"]["version"],
        config_hash=marker["config"]["sha256"][:16], source_inference_repo_id=result["source_repo_id"],
        source_inference_revision=result["source_revision"],
        grader_source_hash=marker["grader"]["materialized_source_sha256"], renderer_fingerprint=None,
        anchor_projection=config.get("anchor_projection"))
    _require(payload["experiment_yaml_name"] == FIRST_RUN and payload["source_inference_experiment_id"] == FIRST_RUN
             and payload["expected_task_count"] == 1 and payload["expected_ordered_task_ids_sha256"] ==
             step8._ordered_task_ids_sha256([FIRST_TASK]) and payload["run_status"] in {"partial", "diagnostic"},
             "grade_scope_mismatch")
    _require([row["task_id"] for row in payload["tasks"]] in ([FIRST_TASK], []) and
             (payload["tasks"] or payload["run_status"] == "partial"), "grade_task_mismatch")
    expected_judge = {key: config["judge"][key] for key in ("provider", "api", "model", "deployment", "api_version")}
    expected_judge.update(reasoning_effort=config["judge"]["reasoning"]["effort"],
        temperature=config["judge"]["generation"]["temperature"], seed=config["judge"]["generation"]["seed"],
        perception=config["judge"]["perception"], config_name=config["config_name"], config_hash=marker["config"]["sha256"][:16])
    _require(all(payload["judge"].get(key) == value for key, value in expected_judge.items()), "grade_judge_mismatch")
    _same("grade inference model", payload["inference_model"], result["model"])
    _require(not step8.requires_track2_office_renderer(config) or
             type(payload.get("renderer_fingerprint")) is dict, "grade_renderer_metadata_missing")
    for row in payload["tasks"]:
        if not row.get("error"):
            _same("grade rubric coverage", [item["rubric_item_id"] for item in row["items"]], checked["rubric_item_ids"])
    return data, payload


def _grade_sidecars(checked: dict, payload: dict | None) -> dict[str, bytes]:
    """Keep Step8's real ledger pointer and incomplete checkpoint, never resume."""
    path, source = checked["grade_path"], checked["batch"].parent
    ledger = path.with_name(path.stem + ".cost_ledger.jsonl")
    progress_path = checkpoint_path(path, FIRST_TASK)
    reference = project_cost_ledger_reference(payload.get("cost_ledger")) if payload is not None else None
    files = {}
    for member in (ledger, progress_path):
        if os.path.lexists(member):
            role = member.relative_to(source).as_posix()
            _require(member.lstat().st_size <= MAX_GRADE_BYTES, "grade_sidecar_size_bound")
            files[role] = _read_bytes(_path(source, role))
    if reference is not None:
        role = ledger.relative_to(source).as_posix()
        _require(role in files, "bound_grade_ledger_missing")
        _same("grade ledger pointer", reference, ledger_reference(role, _identity(files[role])["sha256"]))
        verify_cost_ledger(reference, ledger)
    progress_role = progress_path.relative_to(source).as_posix()
    if progress_role in files:
        progress = load_checkpoint(path, task_id=FIRST_TASK,
            grader_source_hash=checked["marker"]["grader"]["materialized_source_sha256"],
            rubric_item_ids=checked["rubric_item_ids"])
        _require(progress is not None, "grade_progress_missing")
        _same("grade progress", progress.to_dict(), json.loads(files[progress_role], object_pairs_hook=_object))
    for role, data in files.items():
        _read_bytes(_path(source, role), **_identity(data))
    return files


def execute_first_observation_grading(
    plan: dict, *, observation: ObservationIdentity, expected_observation_identity: dict,
    expected_input_binding: dict, expected_input_binding_identity: dict,
    runtime_root: Path, expected_reviewed_source_sha: str,
    frozen_grader_root: Path, expected_grader_source_sha: str,
    input_registration_root: Path, expected_input_source_sha: str, input_registration_path: str,
    dataset_parquet: Path, reference_root: Path, result_path: Path, expected_result_identity: dict,
    deliverables_root: Path, preparation_directory: Path, expected_preparation_identity: dict,
    controller_root: Path, expected_controller_source_sha: str, expected_controller_source_tree: str,
    direction_file: Path, expected_direction_sha256: str, expected_execution_context_sha256: str,
    attempt_store: Path, destination: Path,
) -> dict:
    """Validate, durably consume and invoke the actual prepared F Step8 once.

    All expected identities/paths are independent caller inputs. No marker,
    environment approval switch or serialized callback can authorize launch.
    Refusals before a claim emit no study/grade row. Claimed failures remain
    nonrenewable in this named local store, even with a different destination.
    """
    arguments = dict(locals())
    try:
        _require(type(observation) is ObservationIdentity, "independent_observation_required")
        observation = ObservationIdentity(**asdict(observation))
        arguments["observation"] = observation
        for name in ("runtime_root", "frozen_grader_root", "input_registration_root", "controller_root",
                     "dataset_parquet", "reference_root", "result_path", "deliverables_root",
                     "preparation_directory", "direction_file", "attempt_store", "destination"):
            arguments[name] = _absolute(arguments[name])
        attempt_store, destination = arguments["attempt_store"], arguments["destination"]
        _require(type(observation) is ObservationIdentity, "independent_observation_required")
        key = _observation_key(observation)
        claim = attempt_store / (key + ".json")
        _require(attempt_store.is_dir() and stat.S_IMODE(attempt_store.stat().st_mode) == 0o700 and
                 attempt_store.stat().st_uid == os.getuid(), "private_existing_attempt_store_required")
        _require(not os.path.lexists(claim), "grading_attempt_already_claimed")
        reservation = destination.with_name(destination.name + RESERVATION_SUFFIX)
        _require(destination.parent.is_dir() and not os.path.lexists(destination) and
                 not os.path.lexists(reservation), "new_grade_destination_required")
        for name in ("runtime_root", "frozen_grader_root", "input_registration_root", "controller_root",
                     "dataset_parquet", "reference_root", "result_path", "deliverables_root",
                     "preparation_directory", "direction_file"):
            source = arguments[name]
            for target in (attempt_store, destination, reservation):
                _require(not (target.is_relative_to(source) or source.is_relative_to(target)), "grading_path_overlap")
        _require(not (destination.is_relative_to(attempt_store) or attempt_store.is_relative_to(destination)),
                 "grading_path_overlap")
        _require(os.environ.get("GRADER_TIME_BUDGET_SEC", str(STEP8_SECONDS)) == str(STEP8_SECONDS),
                 "frozen_step8_time_budget_required")
        plan = json.loads(_encoded(plan))
        with ExitStack() as held, ExitStack() as source_hold:
            checked = source_hold.enter_context(_checked_preparation(plan, arguments))
            store_check = held.enter_context(_held_parents(attempt_store, ()))
            publication_check, mkdir, descriptor = held.enter_context(_publication_parents(destination.parent))
            binding = _execution_binding(checked, arguments)
            binding_value = binding.as_dict()
            command = binding_value["command"]
            direction = {"direction_file": arguments["direction_file"],
                         "expected_direction_sha256": expected_direction_sha256}
            require_execution_direction(binding, **direction)
            checked["reread"](initial=True)
            store_check()
            publication_check()
            claim_data = _encoded({"claim_version": "time-budget-first-f-grade-attempt-v1",
                "observation_key": key, "attempt": 1, "direction_sha256": expected_direction_sha256,
                "binding": binding_value, "state": "consumed_before_child_never_reusable"})
            with _publication_parents(attempt_store) as (store_publication_check, _, store_fd):
                _durable_write(claim, claim_data, store_fd(attempt_store))
                store_publication_check()
            # A slow durable reservation never extends the finite admission window.
            require_execution_direction(binding, **direction)
            _durable_write(reservation, _encoded({"claim": str(claim), "claim_file": _identity(claim_data)}),
                           descriptor(destination.parent))
            mkdir(destination)
            os.fsync(descriptor(destination.parent))
            outcome = {"execution_version": "time-budget-first-f-grading-result-v1", "binding": binding_value,
                "claim_file": {"path": str(claim), **_identity(claim_data)}, "entry_invoked": False,
                "exit_code": None, "terminal_reason": "failed", "timed_out": False,
                "cancelled": False, "cleanup_confirmed": False,
                "grade_file": None, "sidecar_files": [],
                "usage": {"available": False, "reason": "no_valid_step8_grade"},
                "retry_allowed": False}
            try:
                experiment_path = arguments["preparation_directory"] / EXPERIMENT
                with _publication_parents(experiment_path.parent) as (check, _, fd):
                    _durable_write(experiment_path, checked["experiment"], fd(experiment_path.parent))
                    check()
                # All original source/input/config bytes are still the validated bundle.
                checked["reread"](installed=True)
                store_check()
                _read_bytes(claim, **_identity(claim_data))
                require_execution_direction(binding, **direction)
                owner_binding = {"plan_sha256": seal(binding_value), "cell_id": key,
                                 "stage": "time_budget_f_grading", "attempt": 1}
                lock = os.open(claim, os.O_RDONLY | os.O_NOFOLLOW)
                held.callback(os.close, lock)
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                outcome["entry_invoked"] = True
                completed = owned.LocalTransport().process(command,
                    ownership=(destination / "grader-owner.json", owner_binding), cwd=checked["batch"],
                    env=_environment(destination), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=CHILD_SECONDS, check=False, pass_fds=(lock,))
                outcome["exit_code"] = completed.returncode
                outcome["terminal_reason"] = "completed" if completed.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                outcome["terminal_reason"] = "timeout"
                outcome["timed_out"] = True
            except KeyboardInterrupt:
                outcome["terminal_reason"] = "cancelled"
                outcome["cancelled"] = True
            except Exception:
                outcome["terminal_reason"] = "failed"
            try:
                owner = json.loads(_read_bytes(destination / "grader-owner.json"), object_pairs_hook=_object)
                outcome["cleanup_confirmed"] = all(owner.get(name) == value for name, value in owner_binding.items()) and (
                    owner.get("phase") == "reaped" and owner.get("tree_reaped") is True and owner.get("owner_reaped") is True)
            except (OSError, ValueError, UnboundLocalError):
                pass
            checked["reread"]()
            grade_path = checked["grade_path"]
            candidates = (grade_path, grade_path.with_name(grade_path.stem + ".cost_ledger.jsonl"),
                          checkpoint_path(grade_path, FIRST_TASK))
            grade_check = held.enter_context(_held_parents(checked["batch"].parent,
                tuple(path.relative_to(checked["batch"].parent).as_posix()
                      for path in candidates if os.path.lexists(path))))
            grade = None
            if os.path.lexists(checked["grade_path"]):
                data, grade = _grade(checked["grade_path"], checked)
                _durable_write(destination / "grade.json", data, descriptor(destination))
                outcome["grade_file"] = {"path": "grade.json", **_identity(data)}
                usage = grade.get("summary", {}).get("cost")
                if usage is not None:
                    outcome["usage"] = {"available": any(row.get("usage_complete") is True for row in grade["tasks"]),
                        "source": "unchanged_step8_summary.cost", "invoice_complete": False,
                        "complete": bool(grade["tasks"]) and usage.get("usage_complete") is True and
                                    all(row.get("usage_complete") is True for row in grade["tasks"]),
                        "value": usage, "task_grading_cost": [row.get("grading_cost") for row in grade["tasks"]]}
                if outcome["terminal_reason"] == "completed" and (grade["run_status"] != "diagnostic" or
                    not grade["tasks"] or any(row.get("error") or step8._track2_task_runtime_error(row)
                                             for row in grade["tasks"])):
                    outcome["terminal_reason"] = "failed"
            sidecars = _grade_sidecars(checked, grade)
            created = {destination}
            for role, data in sidecars.items():
                target = _path(destination, role)
                for parent in reversed(target.parents):
                    if parent != destination and parent.is_relative_to(destination) and parent not in created:
                        mkdir(parent)
                        os.fsync(descriptor(parent.parent))
                        created.add(parent)
                _durable_write(target, data, descriptor(target.parent))
                outcome["sidecar_files"].append({"path": role, **_identity(data)})
            if outcome["terminal_reason"] == "completed" and any("/_progress/" in role for role in sidecars):
                outcome["terminal_reason"] = "failed"
            if not outcome["cleanup_confirmed"]:
                outcome["terminal_reason"] = "cleanup_unconfirmed"
            elif outcome["grade_file"] is None and outcome["terminal_reason"] == "completed":
                outcome["terminal_reason"] = "missing_grade"
            store_check()
            publication_check()
            _read_bytes(claim, **_identity(claim_data))
            checked["reread"]()
            # Closing invokes every final held Git/blob/source reread before publication.
            source_hold.close()
            if grade is not None:
                _read_bytes(checked["grade_path"], **{name: outcome["grade_file"][name] for name in ("sha256", "size")})
            for role, data in sidecars.items():
                _read_bytes(_path(checked["batch"].parent, role), **_identity(data))
            grade_check()
            store_check()
            publication_check()
            _durable_write(destination / RESULT, _encoded(outcome), descriptor(destination))
        return outcome
    except GradingExecutionRefused:
        raise
    except (Exception, KeyboardInterrupt):
        raise GradingExecutionRefused("grading_execution_refused_retain_any_claim_or_partial_state") from None


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise GradingExecutionRefused("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    """Fixed CLI; no provider, callback, module, retry or approval-flag selection."""
    parser = _Parser(description=__doc__)
    for name in ("controller-root", "runtime-root", "frozen-grader-root", "input-registration-root",
                 "dataset-parquet", "reference-root", "result-path", "deliverables-root", "preparation-directory",
                 "attempt-store", "destination", "direction-file", "observation-file", "input-binding-file"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("controller-source-sha", "controller-source-tree", "reviewed-source-sha", "grader-source-sha",
                 "input-source-sha", "input-registration-path", "direction-sha256", "execution-context-sha256"):
        parser.add_argument("--" + name, required=True)
    for name in ("observation", "input-binding", "result", "preparation"):
        parser.add_argument("--" + name + "-sha256", required=True)
        parser.add_argument("--" + name + "-size", required=True, type=int)
    try:
        args = vars(parser.parse_args(argv))
        expected = {name: {"sha256": args.pop(name + "_sha256"), "size": args.pop(name + "_size")}
                    for name in ("observation", "input_binding", "result", "preparation")}
        _, observation = _document(_absolute(args.pop("observation_file")), expected["observation"])
        _, inputs = _document(_absolute(args.pop("input_binding_file")), expected["input_binding"])
        for name in ("controller_source_sha", "controller_source_tree", "reviewed_source_sha", "grader_source_sha",
                     "input_source_sha", "direction_sha256", "execution_context_sha256"):
            args["expected_" + name] = args.pop(name)
        plan = registration.load_registration(args["runtime_root"] / registration.REGISTRATION_PATH)
        result = execute_first_observation_grading(plan, observation=ObservationIdentity(**observation),
            expected_observation_identity=expected["observation"], expected_input_binding=inputs,
            expected_input_binding_identity=expected["input_binding"], expected_result_identity=expected["result"],
            expected_preparation_identity=expected["preparation"], **args)
        print(json.dumps({"terminal_reason": result["terminal_reason"], "retry_allowed": False}))
        return 0 if result["terminal_reason"] == "completed" else 1
    except (GradingExecutionRefused, ValueError, OSError, TypeError):
        print("grading execution refused; retain any claim or partial state", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
