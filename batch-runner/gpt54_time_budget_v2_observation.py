"""Execute only the first registered V2 observation with an independent direction.

This is a callable consumer, not a workflow, preparation authority or grading
entrypoint. The caller supplies trusted digests/anchors separately from every
file they authenticate. No argument can replace a checker, factory or provider.
An admitted failure is retained; a refusal never becomes an admitted result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gpt54_time_budget_comparison as registration
from core.agentic_v2_contract import ERROR_TYPES, canonical_relative_path
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_instructions import resolve_instructions
from core.agentic_v2_model_voice import AzureFoundryVoice, _attribute
from core.agentic_v2_preregistration import seal
from core.agentic_v2_provenance import (
    verify_agentic_v2_failure_result, verify_agentic_v2_result,
)
from core.agentic_v2_route_check import check_route_is_the_one_the_plan_fixed
from core.azure_ai_clients import AzureAIRouteSettings, AzureAIWorkload
from core.inference_manifest import (
    STEP2_PROGRESS_SCHEMA, canonical_deliverable_path,
    canonicalize_inference_payload, validate_step2_progress_results,
)
from core.llm_client import create_typed_azure_client
from core.result_fingerprint import inference_result_fingerprint
from core.time_budget_observation_deadline import CLEANUP_UNCONFIRMED, TIMEOUT, ObservationIdentity
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object, _read_bytes, _same, _snapshot_deliverables

ENTRYPOINT = "batch-runner/gpt54_time_budget_v2_observation.py"
RUN = "gpt54_time_budget_v1_v2_r1"
TASK = "02aa1805-c658-4069-8a6a-02dec146063a"
DIRECTION_VERSION = "gpt54-time-budget-first-v2-direction-v1"
RESULT = "step2_inference_results.json"
RESERVATION_SUFFIX = ".time-budget-result-reserved.json"
WORK_SUFFIX = ".time-budget-v2-work"
MAX_DIRECTION_BYTES = 65_536


class FirstV2ObservationRefused(ValueError):
    """Static, nonsecret refusal; consumed/partial state must not be retried."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise FirstV2ObservationRefused(reason)


def _bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _sha256(value: str) -> str:
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             "independent_sha256_required")
    return value


def execution_host_identity(reviewed_source_sha: str) -> dict:
    """Local metadata only, not an ownership probe or an admission verdict.

    A leader can obtain this digest on the intended host before issuing a
    direction. It names the boot/namespace/user and, when present, the exact
    CI job instance. Raw environment values and boot IDs are never retained.
    Actual support still requires TimeBudgetObservation's kernel admission.
    """
    uname = os.uname()
    _require(uname.sysname == "Linux", "linux_host_required")
    with Path("/proc/sys/kernel/random/boot_id").open(encoding="ascii") as stream:
        boot = stream.read(64).strip()
    _require(re.fullmatch(r"[0-9a-f-]{36}", boot) is not None, "host_boot_identity_required")
    namespace = Path("/proc/self/ns/pid").stat()
    instance = {
        "boot_id": boot, "uname": list(uname), "uid": os.getuid(),
        "pid_namespace": [namespace.st_dev, namespace.st_ino],
    }
    ci = None
    if os.environ.get("GITHUB_ACTIONS") is not None:
        _require(os.environ.get("GITHUB_ACTIONS") == "true"
                 and os.environ.get("GITHUB_SHA") == reviewed_source_sha
                 and os.environ.get("RUNNER_OS") == "Linux", "ci_source_host_mismatch")
        keys = ("GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB",
                "GITHUB_WORKFLOW_REF", "RUNNER_NAME", "RUNNER_ARCH")
        ci = {name: os.environ.get(name) for name in keys}
        _require(all(type(value) is str and 0 < len(value) <= 512 for value in ci.values())
                 and ci["GITHUB_RUN_ID"].isdigit() and ci["GITHUB_RUN_ATTEMPT"].isdigit()
                 and int(ci["GITHUB_RUN_ATTEMPT"]) > 0, "ci_instance_required")
        instance["ci"] = ci
    return {"policy": "linux-boot-namespace-user-ci-instance-v1",
            "instance_sha256": seal(instance), "ci_instance_sha256": None if ci is None else seal(ci),
            "ownership_confirmed": False}


class _ExecutionDirection:
    """Concrete read-only checker installed at ObservationExecutionBinding."""

    def __init__(self, *, path: Path, expected_sha256: str, expected_host_sha256: str,
                 binding: registration.ObservationExecutionBinding, paths: dict[str, str],
                 reviewed_source_sha: str):
        self.path, self.expected = path, _sha256(expected_sha256)
        self.expected_host = _sha256(expected_host_sha256)
        self.binding, self.paths, self.source = binding, paths, reviewed_source_sha
        size = path.lstat().st_size
        _require(0 < size <= MAX_DIRECTION_BYTES, "direction_size_bound")
        self.data = _read_bytes(path, sha256=self.expected, size=size)
        value = json.loads(self.data, object_pairs_hook=_object)
        _require(type(value) is dict and set(value) == {
            "direction_version", "purpose", "execution_binding", "paths", "host_sha256",
            "not_before_unix", "expires_unix",
        }, "direction_schema")
        _same("direction version", value["direction_version"], DIRECTION_VERSION)
        _same("direction purpose", value["purpose"], "execute_one_registered_observation")
        _same("direction execution binding", value["execution_binding"], asdict(binding))
        _same("direction paths", value["paths"], paths)
        _same("direction host", value["host_sha256"], self.expected_host)
        self.begin, self.end = value["not_before_unix"], value["expires_unix"]
        _require(type(self.begin) is int and type(self.end) is int
                 and 0 <= self.begin < self.end, "direction_admission_window")
        self.check(admission=True)

    def check(self, *, admission: bool) -> None:
        _read_bytes(self.path, **_identity(self.data))
        self.host = execution_host_identity(self.source)
        _same("independent execution host", self.host["instance_sha256"], self.expected_host)
        # This window authorizes admission, not a resettable generation clock.
        if admission:
            _require(self.begin <= time.time() < self.end, "direction_not_current")

    def require_execution_direction(self, binding: registration.ObservationExecutionBinding) -> None:
        _require(type(binding) is registration.ObservationExecutionBinding, "execution_binding_type")
        _same("independent execution binding", asdict(binding), asdict(self.binding))
        self.check(admission=True)


class _V2Dependencies:
    """Install the registered backend, voice and existing typed Azure client.

    Only client construction/transport are ordinary test seams. Lazy creation
    occurs inside the first supervised responses.create, so authentication and
    SDK waits consume the existing observation deadline. Both close paths use
    the runner's original cleanup control, never an outside finally/join.
    """

    def __init__(self, workspace: Path, publication):
        self.workspace, self.publication = workspace, publication
        self.managed = self.voice = self.config = None
        self.responses = self
        self.calls: list[dict] = []
        self.route_sha256 = None
        self.client_construction_attempts = 0
        self.closed = False

    def backend_factory(self, **kwargs):
        check, mkdir, _ = self.publication
        check()
        mkdir(self.workspace)  # no adoption of an existing backend directory
        backend = AgenticV2FixtureBackend(root=self.workspace, **kwargs)
        original_close = backend.close

        def close():
            # Sequential work under the SAME remaining cleanup allowance. If
            # either step is interrupted, no successful cleanup is fabricated.
            original_close()
            self.close()

        backend.close = close
        return backend

    def voice_for(self, config, budget):
        _require(self.voice is None, "one_voice_only")
        self.config = config
        self.instructions = resolve_instructions(config, AgenticV2FixtureBackend)
        self.voice = AzureFoundryVoice(
            client=self, deployment=config["model"]["deployment"],
            resource=config["azure_connection"]["account"], budget=budget,
            instructions=self.instructions.text,
            max_output_tokens_per_turn=config["cost"]["chosen_settings"]["max_output_tokens_per_turn"],
            request_timeout_seconds=1200, prices={}, replay_format="faithful",
            reasoning_effort=config["model"]["reasoning_effort"],
        )
        return self.voice

    def create(self, **kwargs):
        _require(not self.closed and self.config is not None, "provider_lifecycle")
        if self.managed is None:
            self.client_construction_attempts += 1
            settings = AzureAIRouteSettings.from_env()
            route = settings.select(AzureAIWorkload.INFERENCE)
            _require(not check_route_is_the_one_the_plan_fixed(
                route, self.config["azure_connection"], settings=settings), "registered_route_required")
            self.managed = create_typed_azure_client(
                AzureAIWorkload.INFERENCE, self.config["model"]["deployment"],
                settings=settings, timeout=1200, max_retries=0,
            )
            _require(not check_route_is_the_one_the_plan_fixed(
                self.managed.route, self.config["azure_connection"], settings=settings),
                "registered_route_required")
            self.route_sha256 = self.managed.runtime_fingerprint
        call = {"response_returned": False, "usage": None, "model_binding": "unavailable"}
        self.calls.append(call)
        response = self.managed.client.responses.create(**kwargs)
        call["response_returned"] = True
        reported = _attribute(response, "usage")
        input_tokens, output_tokens = (_attribute(reported, name) for name in ("input_tokens", "output_tokens"))
        if all(type(value) is int and value >= 0 for value in (input_tokens, output_tokens)):
            usage = {"input_tokens": input_tokens, "output_tokens": output_tokens}
            for name, detail, field, ceiling in (
                ("cached_input_tokens", "input_tokens_details", "cached_tokens", input_tokens),
                ("reasoning_output_tokens", "output_tokens_details", "reasoning_tokens", output_tokens),
            ):
                value = _attribute(_attribute(reported, detail), field)
                usage[name] = value if type(value) is int and 0 <= value <= ceiling else None
            call["usage"] = usage
        matches = _attribute(response, "model") == self.config["model"]["resolved_model"]
        call["model_binding"] = "matched" if matches else "unreported_or_mismatched"
        _require(matches, "served_model_mismatch")  # before any returned tool is dispatched
        return response

    def close(self):
        if not self.closed:
            self.closed = True
            if self.managed is not None:
                self.managed.close()

    def usage(self):
        complete = bool(self.calls) and all(row["usage"] is not None for row in self.calls)
        totals = {name: sum(row["usage"][name] for row in self.calls if row["usage"] is not None)
                  for name in ("input_tokens", "output_tokens")}
        return ({**totals} if complete else None), {
            "client_construction_attempts": self.client_construction_attempts,
            "responses_create_invocations": len(self.calls),
            "completed_responses": sum(row["response_returned"] for row in self.calls),
            "response_records": self.calls, "usage_complete": complete,
            "reported_token_subtotals": totals if any(row["usage"] is not None for row in self.calls) else None,
            "native_model_attempts": None, "repeated_request_count": None, "written_tokens": None,
            "unavailable_counters_are_not_zero": True,
            "cached_and_reasoning_tokens_are_subsets": True, "money_hard_cap": False,
            "route_fingerprint": self.route_sha256,
        }


def _capture(raw: dict, marker: dict, dependencies: _V2Dependencies, direction: _ExecutionDirection):
    observation = marker["observation"]
    control = raw["time_budget_observation"]
    _same("returned control identity", control["identity"], observation)
    _same("returned admission", control["admitted"], True)
    _same("returned policy", control["policy"], "time_budget_observation_deadline_v1")
    _require(control["terminal_reason"] in {"completed", "failed", "cancelled", "abandoned", TIMEOUT},
             "returned_terminal_required")
    _same("returned preparation", raw["handoff_preparation_identity"],
          {"sha256": direction.binding.preparation_sha256, "size": direction.binding.preparation_size})
    files, text, valid = {}, "", False
    # Validate the runner's real artifact/audit bytes before publishing them.
    # A timeout may have changed success/error after a valid finalize; this
    # verifies artifacts without promoting that late outcome back to success.
    try:
        base = {name: raw[name] for name in ("text", "deliverable_text", "files", "agentic_v2")}
        verify_agentic_v2_result({**base, "success": True})
        for item in base["files"]:
            name = canonical_relative_path(item["filename"])
            role = canonical_deliverable_path(TASK, f"deliverable_files/{TASK}/{name}")
            _require(role not in files and 0 < len(item["content"]) <= 64 * 1024 * 1024,
                     "deliverable_size_or_duplicate")
            files[role] = item["content"]
        text, valid = base["text"], True
    except (KeyError, TypeError, ValueError):
        files = {}
        try:
            verify_agentic_v2_failure_result({name: raw[name] for name in (
                "success", "text", "deliverable_text", "files", "error", "agentic_v2")})
            valid = True
        except (KeyError, TypeError, ValueError):
            pass  # Retained as an invalid/error outcome, never a successful fallback.
    success = (valid and raw.get("success") is True and control["terminal_reason"] == "completed"
               and control["cleanup_complete"] is True and control["host_reusable"] is True
               and bool(files or text) and (not marker["inputs"]["needs_files"] or bool(files)))
    usage, available = dependencies.usage()
    elapsed = control["generation_elapsed_seconds"]
    error = raw.get("error")
    safe_error = error if type(error) is str and error in {*ERROR_TYPES, TIMEOUT, CLEANUP_UNCONFIRMED} else None
    row = {
        "task_id": TASK, "status": "success" if success else "error",
        "error": None if success else safe_error or "time_budget_observation_non_success",
        "content": text, "deliverable_text": text, "deliverable_files": sorted(files),
        "deliverable_file_records": [{"path": name, **_identity(files[name])} for name in sorted(files)],
        "model": "gpt-5.4",
        "usage": usage, "observability": {
            "runner_success": raw.get("success") is True,
            "runner_result_verified": valid, "runner_error": safe_error,
            "runner_error_sha256": None if error is None else seal(error),
            "v2_audit_sha256": seal(raw.get("agentic_v2")), "usage_availability": available,
            "required_deliverable_missing": marker["inputs"]["needs_files"] and not bool(files),
        },
        "latency_ms": None if elapsed is None else elapsed * 1000,
        "timestamp": datetime.now(timezone.utc).isoformat(), "retried": False, "resume_round": None,
    }
    validate_step2_progress_results([row], schema_version=STEP2_PROGRESS_SCHEMA)
    payload = canonicalize_inference_payload({
        "experiment_id": RUN, "condition": "sandbox_v2", "execution_mode": "agentic_sandbox_v2",
        "model": "gpt-5.4", "source": "openai/gdpval", "results": [row],
        "time_budget_observation": control,
        "observation_execution": {
            "direction_sha256": direction.expected, "host": direction.host,
            "preparation_identity": raw["handoff_preparation_identity"],
            "runtime_source": marker["runtime_source"], "frozen_grader": marker["frozen_grader"],
            "inputs": marker["inputs"], "condition_template": marker["condition_template"],
            "configuration": marker["files"][registration.HANDOFF_CONFIG],
            "resolved_instructions": dependencies.instructions.identity(),
            "entrypoint": ENTRYPOINT, "paths_sha256": seal(direction.paths),
            "grading_performed": False, "upload_performed": False,
        },
    })
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    return payload, files


def run_first_v2_observation(
    plan: dict, *, observation: ObservationIdentity, direction_path: Path,
    expected_direction_sha256: str, expected_host_sha256: str,
    preparation_directory: Path, expected_preparation_identity: dict,
    runtime_root: Path, expected_reviewed_source_sha: str,
    frozen_grader_root: Path, expected_grader_source_sha: str,
    input_registration_root: Path, expected_input_source_sha: str, input_registration_path: str,
    dataset_parquet: Path, reference_root: Path, observation_directory: Path, destination: Path,
) -> dict:
    """One nonrenewable first-cell call, no outer retry or grading.

    Expected identities are caller authority, not values inferred from markers,
    direction bytes or HEAD. A new result destination and adjacent backend work
    directory are required. A consumed handoff, result reservation or partial
    workspace is never repaired/adopted. Construction/interruption without a
    returned terminal control remains uncertainty, not a fabricated study row.
    """
    _require(type(observation) is ObservationIdentity and observation.run_id == RUN
             and observation.condition == "sandbox_v2" and observation.repeat == 1
             and observation.task_id == TASK, "first_registered_v2_cell_only")
    observation = ObservationIdentity(**asdict(observation))
    _same("independent runtime source", observation.reviewed_source_sha, expected_reviewed_source_sha)
    _same("independent frozen source", expected_grader_source_sha, registration.ACCEPTED_BASE_SHA)
    _require(type(expected_preparation_identity) is dict
             and set(expected_preparation_identity) == {"sha256", "size"}, "preparation_identity_required")
    expected = json.loads(_bytes(expected_preparation_identity))
    _sha256(expected["sha256"])
    _require(type(expected["size"]) is int and 0 < expected["size"] <= registration.MAX_MANIFEST_BYTES,
             "preparation_size_bound")
    paths = {name: registration._handoff_path(value) for name, value in {
        "direction": direction_path, "preparation": preparation_directory,
        "runtime_root": runtime_root, "frozen_grader_root": frozen_grader_root,
        "input_registration_root": input_registration_root, "dataset_parquet": dataset_parquet,
        "reference_root": reference_root, "observation_directory": observation_directory,
        "destination": destination,
    }.items()}
    output = paths["destination"]
    reservation = output.with_name(output.name + RESERVATION_SUFFIX)
    workspace = output.with_name(output.name + WORK_SUFFIX)
    _require(output.parent.is_dir(), "result_parent_required")
    for source in (value for name, value in paths.items() if name != "destination"):
        _require(not any(target.is_relative_to(source) or source.is_relative_to(target)
                         for target in (output, reservation, workspace)), "result_source_overlap")
    _require(type(input_registration_path) is str
             and _path(paths["input_registration_root"], input_registration_path).relative_to(
                 paths["input_registration_root"]).as_posix() == input_registration_path,
             "input_registration_path_alias")

    def absent(*, before_generation):
        _require(not any(os.path.lexists(path) for path in (output, reservation)), "result_destination_exists")
        if before_generation:
            _require(not os.path.lexists(workspace), "backend_workspace_exists")
            consumed = paths["preparation"].with_name(paths["preparation"].name + registration.HANDOFF_CONSUMED_SUFFIX)
            _require(not os.path.lexists(consumed), "direction_observation_already_consumed")

    absent(before_generation=True)
    binding = registration.ObservationExecutionBinding(
        expected["sha256"], expected["size"], _canonical_json(asdict(observation)),
        expected_grader_source_sha, registration.ACCEPTED_BASE_TREE, registration.FROZEN_TEMPLATE_SHA256,
        str(paths["preparation"]), str(paths["observation_directory"]),
    )
    direction_paths = {**{name: str(path) for name, path in paths.items()},
                       "input_source_sha": expected_input_source_sha,
                       "input_registration_path": input_registration_path,
                       "backend_workspace": str(workspace)}
    with ExitStack() as held, ExitStack() as sources:
        check_direction_parent = held.enter_context(_held_parents(paths["direction"].parent, (paths["direction"].name,)))
        direction = _ExecutionDirection(
            path=paths["direction"], expected_sha256=expected_direction_sha256,
            expected_host_sha256=expected_host_sha256, binding=binding, paths=direction_paths,
            reviewed_source_sha=expected_reviewed_source_sha,
        )
        _, tree, entries = sources.enter_context(registration._reviewed_source(
            paths["runtime_root"], expected_reviewed_source_sha, {ENTRYPOINT}))
        _same("independent runtime tree", tree, observation.reviewed_source_tree)
        _same("running entrypoint", _identity(_read_bytes(Path(__file__))), entries[ENTRYPOINT])
        common = dict(
            run_id=observation.run_id, task_id=observation.task_id,
            runtime_root=paths["runtime_root"], expected_reviewed_source_sha=expected_reviewed_source_sha,
            frozen_grader_root=paths["frozen_grader_root"], expected_grader_source_sha=expected_grader_source_sha,
            input_registration_root=paths["input_registration_root"], expected_input_source_sha=expected_input_source_sha,
            input_registration_path=input_registration_path, dataset_parquet=paths["dataset_parquet"],
            reference_root=paths["reference_root"], step0_manifest=None,
        )
        marker, handoff_files, reread_inputs = registration._observation_handoff_data(
            plan, sources=sources, destination=paths["preparation"], **common)
        _same("independent observation", marker["observation"], asdict(observation))
        _same("independent preparation", _identity(_bytes(marker)), expected)
        prep = paths["preparation"]
        prep_reservation = prep.with_name(prep.name + registration.HANDOFF_RESERVATION_SUFFIX)
        consumed = prep.with_name(prep.name + registration.HANDOFF_CONSUMED_SUFFIX)
        check_preparation = held.enter_context(_held_parents(prep, (*handoff_files, registration.HANDOFF_READY)))
        check_preparation_parent = held.enter_context(_held_parents(prep.parent, (
            prep_reservation.name, consumed.name, prep.name + "/" + registration.HANDOFF_READY)))

        def reread_consumed_handoff():
            members = {*handoff_files, registration.HANDOFF_READY}
            for role in handoff_files:
                members.update(parent.relative_to(prep).as_posix() for parent in _path(prep, role).parents
                               if parent != prep and parent.is_relative_to(prep))
                _read_bytes(_path(prep, role), **_identity(handoff_files[role]))
            actual = tuple(prep.rglob("*"))
            _require(not any(path.is_symlink() for path in actual), "handoff_member_symlink")
            _same("final handoff members", sorted(path.relative_to(prep).as_posix() for path in actual), sorted(members))
            _read_bytes(prep / registration.HANDOFF_READY, **expected)
            _read_bytes(prep_reservation, **_identity(_bytes({
                "reservation_version": "gpt54-time-budget-preparation-reservation-v1",
                "intended_preparation": expected, "ready_path": registration.HANDOFF_READY})))
            _read_bytes(consumed, **_identity(_bytes({
                "consumption_version": "gpt54-time-budget-observation-consumption-v1",
                "preparation_identity": expected, "observation": asdict(observation),
                "state": "consumed_not_completion_or_launch_authority"})))
            check_preparation()
            check_preparation_parent()

        check_result_parent = held.enter_context(_held_parents(output.parent, (output.name, workspace.name, reservation.name)))
        publication = held.enter_context(_publication_parents(output.parent))
        dependencies = _V2Dependencies(workspace, publication)

        def require_execution_direction(actual):
            direction.require_execution_direction(actual)
            check_direction_parent()
            check_result_parent()
            absent(before_generation=True)

        raw = registration.consume_observation_handoff(
            plan, **common, preparation_directory=paths["preparation"], expected_preparation_identity=expected,
            observation_directory=paths["observation_directory"], require_execution_direction=require_execution_direction,
            v2_backend_factory=dependencies.backend_factory, v2_voice_for=dependencies.voice_for,
        )
        payload, files = _capture(raw, marker, dependencies, direction)
        reread_inputs()
        reread_consumed_handoff()
        direction.check(admission=False)
        check_direction_parent()
        check_result_parent()
        check, mkdir, descriptor = publication
        check()
        absent(before_generation=False)
        reservation_data = _bytes({"reservation_version": "gpt54-time-budget-v2-result-v1",
                                   "observation": asdict(observation), "direction_sha256": direction.expected,
                                   "result_identity": _identity(_bytes(payload))})
        _write_no_clobber(reservation, reservation_data, parent_fd=descriptor(output.parent))
        mkdir(output)
        mkdir(output / "upload")
        directories = {parent for name in files for parent in _path(output / "upload", name).parents
                       if parent != output / "upload" and parent.is_relative_to(output / "upload")}
        for directory in sorted(directories, key=lambda path: (len(path.parts), path.as_posix())):
            mkdir(directory)
        for name, data in files.items():
            target = _path(output / "upload", name)
            _write_no_clobber(target, data, parent_fd=descriptor(target.parent))
        bound, actual = _snapshot_deliverables(payload["results"], output / "upload")
        _same("captured deliverable rows", bound, payload["results"])
        _require(actual == files, "captured_deliverable_bytes")
        # All source/input contexts perform their final rereads before the
        # canonical result. This metadata phase does not renew cleanup or alter
        # the runner's terminal/host record. Publication failure stays partial.
        reread_consumed_handoff()
        sources.close()
        _read_bytes(Path(__file__), **entries[ENTRYPOINT])
        registration._require_running_observation_sources(paths["runtime_root"])
        direction.check(admission=False)
        check_direction_parent()
        check_result_parent()
        _read_bytes(reservation, **_identity(reservation_data))
        members = tuple(output.rglob("*"))
        _require(not any(path.is_symlink() for path in members), "result_member_symlink")
        _same("result members", sorted(path.relative_to(output).as_posix() for path in members),
              sorted(["upload", *("upload/" + name for name in files),
                      *(path.relative_to(output).as_posix() for path in directories)]))
        check()
        _write_no_clobber(output / RESULT, _bytes(payload), parent_fd=descriptor(output))
        return {"result_path": str(output / RESULT), "result_identity": _identity(_bytes(payload)),
                "result_fingerprint": payload["result_fingerprint"], "status": payload["results"][0]["status"],
                "observation": asdict(observation), "grading_performed": False, "upload_performed": False}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise FirstV2ObservationRefused("invalid_arguments")


def main(argv=None):
    parser = _Parser(description=__doc__)
    for name in ("direction", "preparation-directory", "runtime-root", "frozen-grader-root",
                 "input-registration-root", "dataset-parquet", "reference-root", "observation-directory", "destination"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("direction-sha256", "host-sha256", "preparation-sha256", "reviewed-source-sha",
                 "reviewed-source-tree", "grader-source-sha", "input-source-sha", "input-registration-path",
                 "registration-sha256", "input-sha256", "run-id", "task-id"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--preparation-size", type=int, required=True)
    try:
        args = parser.parse_args(argv)
        observation = ObservationIdentity(
            registration.STUDY_ID, args.run_id, "sandbox_v2", 1, args.task_id,
            args.reviewed_source_sha, args.reviewed_source_tree, args.registration_sha256, args.input_sha256)
        result = run_first_v2_observation(
            registration.load_registration(args.runtime_root / registration.REGISTRATION_PATH),
            observation=observation, direction_path=args.direction, expected_direction_sha256=args.direction_sha256,
            expected_host_sha256=args.host_sha256, preparation_directory=args.preparation_directory,
            expected_preparation_identity={"sha256": args.preparation_sha256, "size": args.preparation_size},
            runtime_root=args.runtime_root, expected_reviewed_source_sha=args.reviewed_source_sha,
            frozen_grader_root=args.frozen_grader_root, expected_grader_source_sha=args.grader_source_sha,
            input_registration_root=args.input_registration_root, expected_input_source_sha=args.input_source_sha,
            input_registration_path=args.input_registration_path, dataset_parquet=args.dataset_parquet,
            reference_root=args.reference_root, observation_directory=args.observation_directory, destination=args.destination)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # No provider messages, original bodies, paths or credentials on stdout.
        # Absence of a result is NOT proof of no admission: keep durable claims.
        print(_canonical_json({"result_published": False, "reason": "first_v2_observation_refused_or_incomplete",
                               "retry_allowed": False}))
        return 2
    print(_canonical_json(result))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
