"""Prepare one frozen-source grader configuration and local inputs, never grade.

R binds the registration and this helper. F independently supplies every copied
grader source byte. The materialized configuration is hashed at its actual path
against that F-derived source, not the running process's changed runtime core.
No command, provider, grading admission or execution permission is produced.
"""

from __future__ import annotations

import json
import os
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

import gpt54_time_budget_comparison as registration
from core.agentic_v2_preregistration import seal
from core.inference_manifest import canonicalize_inference_payload
from core.reference_integrity import validate_reference_record
from core.result_fingerprint import validate_inference_result_fingerprint
from core.time_budget_observation_deadline import TIMEOUT, ObservationIdentity
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_comparison_preflight import GRADER, _canonical_json, load_plan
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object, _read_bytes, _same, _snapshot_deliverables
from step8_grade import compute_grader_source_hash, validate_grading_config

HELPER = "batch-runner/gpt54_time_budget_grading_preparation.py"
READY = "grading-preparation.json"
RESERVATION_SUFFIX = ".time-budget-grading-reserved.json"
CONFIG = "source/batch-runner/time-budget-grading.json"
MATERIALIZED_FILENAME_TEMPLATE = (
    "{exp_id}__{judge_slug}__{config_name}__{config_hash}__{rubric_sha}__"
    "{inference_sha}__{grader_source_hash_short}__{prompt_v}.json"
)
RESULT = "source/batch-runner/workspace/step2_inference_results.json"
UPLOAD = "source/batch-runner/workspace/upload"
CACHE = "source/data/gdpval-local"
MAX_RESULT_BYTES = 8 * 1024 * 1024


class GradingPreparationRefused(ValueError):
    """No grading readiness is published; reserved/partial state is not reusable."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise GradingPreparationRefused(reason)


def _json_bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _expected_file(value: dict[str, Any]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == {"sha256", "size"},
             "independent_result_digest_and_size_required")
    validate_reference_record(value)
    _require(0 < value["size"] <= MAX_RESULT_BYTES, "result_metadata_size_bound")
    return json.loads(_json_bytes(value))


def _inputs(plan: dict, run: registration.TimeBudgetRunSpec, observation: ObservationIdentity,
            input_source: dict, snapshot: Any, step0_identity: dict | None) -> dict:
    source = next(row for row in snapshot.sources
                  if row["projection"]["task_id"] == observation.task_id)
    dataset = plan["shared"]["dataset"]
    binding = {
        "registration": input_source,
        "dataset": {**snapshot.shared_binding["dataset"], "repo_id": dataset["repo_id"],
                    "revision": dataset["revision"], "catalog_sha256": dataset["catalog_sha256"]},
        "task_id": observation.task_id,
        "source_projection_sha256": source["source_projection_sha256"],
        "text_bytes": source["text_bytes"],
        "reference_file_records": source["reference_file_records"],
        "needs_files_policy": "deliverable_only",
        "needs_files": snapshot.needs_files[observation.task_id],
        "step0_manifest": step0_identity,
        "verification": "local_bytes_against_independently_anchored_input_registration",
    }
    _same("observation input identity", seal(binding), observation.input_sha256)
    _same("observation repeat/condition", (run.repeat, run.condition),
          (observation.repeat, observation.condition))
    return binding


def _result(path: Path, identity: dict, observation: ObservationIdentity,
            plan: dict, upload: Path) -> tuple[bytes, dict, dict[str, bytes], str]:
    _require(path.lstat().st_size == identity["size"], "result_size_changed")
    data = _read_bytes(path, **identity)
    payload = json.loads(data, object_pairs_hook=_object)
    _same("canonical result semantics", canonicalize_inference_payload(payload), payload)
    fingerprint = validate_inference_result_fingerprint(payload)
    for field, expected in {
        "experiment_id": observation.run_id,
        "condition": observation.condition,
        "model": plan["shared"]["model"]["deployment"],
        "source": plan["shared"]["dataset"]["repo_id"],
        "execution_mode": "codex" if observation.condition == "codex" else "agentic_sandbox_v2",
    }.items():
        _same("result " + field, payload[field], expected)
    control = payload["time_budget_observation"]
    _same("result observation", control["identity"], asdict(observation))
    _same("result deadline policy", control["policy"], "time_budget_observation_deadline_v1")
    _same("result admission", control["admitted"], True)
    _require(type(control["terminal_reason"]) is str and control["terminal_reason"] in {
        "completed", "failed", "cancelled", "abandoned", TIMEOUT},
             "terminal_observation_required")
    rows = payload["results"]
    _same("result task scope", [row["task_id"] for row in rows], [observation.task_id])
    row = rows[0]
    _require(row["status"] in ("success", "error"), "terminal_result_required")
    _same("result retry", row.get("retried", False), False)
    _same("result resume", row.get("resume_round"), None)
    _require(row["status"] != "success" or row.get("error") is None,
             "successful_result_carries_error")
    if row["status"] == "success":
        _same("successful observation terminal", control["terminal_reason"], "completed")
        _same("successful observation cleanup", control["cleanup_complete"], True)
        _same("successful observation host", control["host_reusable"], True)
    # An error/missing-output row is retained, not discarded or regenerated.
    # Hashes must already be bound by the independently expected result bytes.
    _require("deliverable_file_records" in row, "result_deliverable_identities_required")
    bound, files = _snapshot_deliverables(rows, upload)
    _same("result deliverable bindings", bound, rows)
    return data, payload, files, fingerprint


def _validate_config(config: dict, source: Path) -> None:
    validation = json.loads(_json_bytes(config))
    for name in ("template", "tool_template"):
        if name in validation["prompt"]:
            validation["prompt"][name] = str(_path(source / "batch-runner", config["prompt"][name]))
    validate_grading_config(validation)


def _materialized_config(plan: dict[str, Any], frozen: Path) -> dict[str, Any]:
    """Derive the fixed rubric/cache/filename changes without altering F."""
    config = load_plan(frozen / GRADER)
    config["rubric"].update(revision=plan["shared"]["grading"]["rubric_revision"],
                            cache_dir="../data/gdpval-local")
    # Only literal labels are removed; every identity value and separator stays.
    config["output"]["filename_template"] = MATERIALIZED_FILENAME_TEMPLATE
    _validate_config(config, frozen)
    return config


def _members(output: Path, files: dict[str, bytes], directories: set[Path]) -> None:
    members = tuple(output.rglob("*"))
    _require(not any(path.is_symlink() for path in members), "grading_member_symlink")
    _same("grading members", sorted(path.relative_to(output).as_posix() for path in members),
          sorted([*files, *(path.relative_to(output).as_posix() for path in directories)]))
    for role, data in files.items():
        _read_bytes(_path(output, role), **_identity(data))


def prepare_observation_grading(
    plan: dict[str, Any], *, observation: ObservationIdentity,
    expected_input_binding: dict[str, Any],
    runtime_root: Path, expected_reviewed_source_sha: str,
    frozen_grader_root: Path, expected_grader_source_sha: str,
    input_registration_root: Path, expected_input_source_sha: str,
    input_registration_path: str, dataset_parquet: Path, reference_root: Path,
    result_path: Path, expected_result_identity: dict[str, Any],
    deliverables_root: Path, destination: Path, step0_manifest: Path | None = None,
) -> dict[str, Any]:
    """Materialize one F-derived grader, with explicit source/input/result anchors.

    Args:
        observation: Independently supplied, genuine registered observation.
        expected_input_binding: Its sealed preparation input binding, reverified
            against local originals. V2 must not supply or read Codex Step0.
        result_path, expected_result_identity: Explicit local canonical Step2
            payload and independently supplied full digest/size. It must contain
            this observation's terminal control identity and one terminal row.
        destination: New private directory with an existing parent, disjoint from
            all sources/inputs/results. No original checkout is mutated.
        Remaining arguments: The existing registration/preparation API's explicit
            independent R/F/input source roots, full commits and local locators.

    Returns:
        Final preparation metadata: exact config path/bytes, actual materialized
        whole-source hash, F-derived Step8 source, observation/input/result and
        exact output members. All execution authority remains false. This is not
        grading admission and does not implement an executor's one-attempt gate.

    Raises:
        GradingPreparationRefused: Invalid bindings, unsafe paths, collisions,
            source drift or partial publication. Keep every partial/reservation;
            never repair, adopt, overwrite or select another grading attempt.
    """
    from core.rubric_loader import RubricLoader

    try:
        _require(type(observation) is ObservationIdentity, "independent_observation_required")
        observation = ObservationIdentity(**asdict(observation))
        expected_result_identity = _expected_file(expected_result_identity)
        _require(type(expected_input_binding) is dict, "independent_input_binding_required")
        expected_input_binding = json.loads(_json_bytes(expected_input_binding))
        _same("independent input binding", seal(expected_input_binding), observation.input_sha256)
        plan = json.loads(_json_bytes(plan))
        anchors = (runtime_root, expected_reviewed_source_sha, frozen_grader_root, expected_grader_source_sha)
        _require(all(value is not None for value in (*anchors, input_registration_root,
                     expected_input_source_sha, input_registration_path)), "explicit_source_anchors_required")
        output = registration._handoff_path(destination)
        reservation = output.with_name(output.name + RESERVATION_SUFFIX)

        def absent() -> None:
            _require(not os.path.lexists(output) and not os.path.lexists(reservation),
                     "grading_destination_or_reservation_exists")

        absent()
        _require(output.parent.is_dir(), "grading_parent_required")
        parquet, references, result, upload = map(registration._handoff_path,
            (dataset_parquet, reference_root, result_path, deliverables_root))
        step0 = None if step0_manifest is None else registration._handoff_path(step0_manifest)
        _require((observation.condition == "codex") == (step0 is not None), "condition_specific_step0_required")
        for value in (runtime_root, frozen_grader_root, input_registration_root,
                      parquet, references, result, upload, *(() if step0 is None else (step0,))):
            source = registration._handoff_path(value)
            _require(not any(target.is_relative_to(source) or source.is_relative_to(target)
                             for target in (output, reservation)), "grading_source_overlap")

        with ExitStack() as sources:
            compiled = registration._compile_registration(plan, anchors, True, sources)
            runs = [run for run in compiled.runs if run.run_id == observation.run_id
                    and observation.task_id in run.task_ids]
            _require(len(runs) == 1, "exactly_one_registered_observation_required")
            run = runs[0]
            evidence = json.loads(compiled.source_evidence_json)
            _same("observation registration", observation.registration_sha256, compiled.manifest_sha256)
            _same("observation runtime commit", observation.reviewed_source_sha, expected_reviewed_source_sha)
            _same("observation runtime tree", observation.reviewed_source_tree, evidence["runtime"]["source_tree"])
            _, _, helper_files = sources.enter_context(registration._reviewed_source(
                runtime_root, expected_reviewed_source_sha, {HELPER}))
            _same("running grading preparation helper", _identity(_read_bytes(Path(__file__))), helper_files[HELPER])
            frozen, frozen_tree, frozen_files = sources.enter_context(registration._reviewed_source(
                frozen_grader_root, expected_grader_source_sha, registration._frozen_roles()))
            catalog, task_ids, input_source = sources.enter_context(registration._observation_input_registration(
                input_registration_root, expected_input_source_sha, input_registration_path, plan["shared"]["dataset"]))
            versions = tuple(name for name in plan["shared"]["dataset"]["input_file_versions"]
                             if name.startswith("reference_files/"))
            checks = [sources.enter_context(_held_parents(parquet.parent, (parquet.name,))),
                      sources.enter_context(_held_parents(references, versions)),
                      sources.enter_context(_held_parents(result.parent, (result.name,)))]
            if step0 is not None:
                checks.append(sources.enter_context(_held_parents(step0.parent, (step0.name,))))

            def read_inputs() -> dict:
                snapshot, step0_identity = registration._observation_inputs(
                    plan["shared"]["dataset"], catalog, task_ids, parquet=parquet,
                    references=references, step0=step0)
                return _inputs(plan, run, observation, input_source, snapshot, step0_identity)

            inputs = read_inputs()
            _same("expected input binding", inputs, expected_input_binding)
            result_data, payload, deliverables, result_fingerprint = _result(
                result, expected_result_identity, observation, plan, upload)
            checks.append(sources.enter_context(_held_parents(upload, tuple(deliverables))))

            # All copied Python/core/prompt/schema/requirements/config bytes are
            # regular tracked F blobs. No archive extraction, .git, credentials,
            # workflow or historical data/result files are copied.
            files = {"source/" + role: _read_bytes(frozen / role, **identity)
                     for role, identity in frozen_files.items() if role.startswith("batch-runner/")}
            config = _materialized_config(plan, frozen)
            files[CONFIG] = _json_bytes(config)
            files[RESULT] = result_data
            files.update({UPLOAD + "/" + role: data for role, data in deliverables.items()})
            rubric = config["rubric"]
            _same("rubric and input revision", rubric["revision"], plan["shared"]["dataset"]["revision"])
            _same("rubric and input repository", rubric["repo_id"], plan["shared"]["dataset"]["repo_id"])
            snapshot_role = CACHE + "/rubric_snapshots/" + rubric["revision"]
            files[snapshot_role + "/data/registered.parquet"] = _read_bytes(parquet, **inputs["dataset"]["parquet"])
            reference_cache = CACHE + "/datasets--" + rubric["repo_id"].replace("/", "--") + "/snapshots/" + rubric["revision"]
            for item in inputs["reference_file_records"]:
                files[reference_cache + "/" + item["path"]] = _read_bytes(
                    _path(references, item["path"]), sha256=item["sha256"], size=item["size"])
            intent = {
                "observation": asdict(observation), "input_binding_sha256": seal(inputs),
                "result_identity": expected_result_identity,
                "runtime_source": {key: evidence["runtime"][key] for key in ("source_sha", "source_tree")},
                "frozen_grader_source": {"source_sha": expected_grader_source_sha, "source_tree": frozen_tree},
                "config": {"path": CONFIG, **_identity(files[CONFIG])},
                "grading_policy": plan["grading_policy"], "grading_attempt": 1,
                "launch_allowed": False, "execution_enabled": False,
            }
            reservation_data = _json_bytes({"reservation_version": "time-budget-f-grading-v1",
                                            "intent": intent, "ready_path": READY})

            def reread() -> None:
                _same("grading inputs changed", read_inputs(), inputs)
                _require(_result(result, expected_result_identity, observation, plan, upload)
                         == (result_data, payload, deliverables, result_fingerprint), "grading_result_changed")
                for check in checks:
                    check()

            reread()
            with _publication_parents(output.parent) as (check, mkdir, descriptor):
                absent()
                _write_no_clobber(reservation, reservation_data, parent_fd=descriptor(output.parent))
                mkdir(output)
                directories = {parent for role in files for parent in _path(output, role).parents
                               if parent != output and parent.is_relative_to(output)}
                for directory in sorted(directories, key=lambda path: (len(path.parts), path.as_posix())):
                    mkdir(directory)
                for role, data in files.items():
                    path = _path(output, role)
                    _write_no_clobber(path, data, parent_fd=descriptor(path.parent))
                loader = RubricLoader(rubric["repo_id"], rubric["revision"], str(output / CACHE))
                manifest_role = snapshot_role + "/" + loader.MANIFEST_FILENAME
                files[manifest_role] = _json_bytes(loader._build_snapshot_manifest(output / snapshot_role))
                path = output / manifest_role
                _write_no_clobber(path, files[manifest_role], parent_fd=descriptor(path.parent))
                loader._validate_snapshot(output / snapshot_role)
                _validate_config(config, output / "source")
                materialized = compute_grader_source_hash(
                    config_path=output / CONFIG, config=config, batch_root=output / "source/batch-runner")
                _require(materialized != registration.FROZEN_TEMPLATE_SHA256,
                         "materialized_config_is_not_the_frozen_template")
                marker = {
                    "preparation_version": "time-budget-f-derived-grading-v1", **intent,
                    "reservation": {"path": reservation.name, **_identity(reservation_data)},
                    "registration_file": evidence["runtime"]["manifest_file"],
                    "preparation_helper": {"path": HELPER, **helper_files[HELPER]},
                    "grader": {
                        "template_path": GRADER,
                        "template_source_sha256": registration.FROZEN_TEMPLATE_SHA256,
                        "config_path": str(output / CONFIG), "config_file": intent["config"],
                        "materialized_source_sha256": materialized,
                        "execution_source": "source", "working_directory": "source/batch-runner",
                        "entrypoint": "source/batch-runner/step8_grade.py",
                        "derivation": "regular_tracked_F_source_blobs_not_a_runtime_checkout",
                    },
                    "inputs": inputs,
                    "result": {"original_path": str(result), "file": {"path": RESULT, **expected_result_identity},
                               "result_fingerprint": result_fingerprint, "status": payload["results"][0]["status"],
                               "terminal_reason": payload["time_budget_observation"]["terminal_reason"]},
                    "files": {role: _identity(data) for role, data in sorted(files.items())},
                    "evidence_boundary": "model_free_grading_preparation_not_attempt_or_execution_authority",
                }
                reread()
                _read_bytes(reservation, **_identity(reservation_data))
                sources.close()  # Final held Git/blob/source rereads before publication.
                _members(output, files, directories)
                check()
                _write_no_clobber(output / READY, _json_bytes(marker), parent_fd=descriptor(output))
            return marker
    except GradingPreparationRefused:
        raise
    except registration.TimeBudgetRegistrationRefused as error:
        raise GradingPreparationRefused(str(error)) from None
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration,
            yaml.YAMLError, RecursionError):
        raise GradingPreparationRefused("time_budget_grading_preparation_refused") from None
