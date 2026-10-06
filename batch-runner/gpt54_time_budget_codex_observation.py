"""Consume one registered Codex handoff and capture its actual Step2 result.

This callable is not a controller or a launch authorization. A trusted caller
must independently supply the source/input/preparation identities, direction
digest, host identity and canonical paths. Existing consumed or partial state
is never adopted. No workflow, native retry, grading or publication is added.
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
import gpt54_time_budget_v2_observation as host_identity
from core.agentic_v2_contract import canonical_relative_path
from core.agentic_v2_preregistration import seal
from core.agentic_v2_route_check import check_route_is_the_one_the_plan_fixed
from core.azure_ai_clients import AzureAIRouteSettings, AzureAIWorkload
from core.codex_runtime_config import (
    CodexProviderSettings, PINNED_CODEX_CLI_VERSION, PINNED_CODEX_SDK_VERSION,
    resolve_endpoint_setting, resolve_run_root_base,
)
from core.inference_manifest import (
    STEP2_PROGRESS_SCHEMA, canonical_deliverable_path,
    canonicalize_inference_payload, validate_step2_progress_results,
)
from core.result_fingerprint import inference_result_fingerprint
from core.time_budget_observation_deadline import (
    CLEANUP_UNCONFIRMED, TIMEOUT, ObservationCleanupExpired, ObservationIdentity,
    ObservationTimedOut,
)
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object, _read_bytes, _same, _snapshot_deliverables

ENTRYPOINT = "batch-runner/gpt54_time_budget_codex_observation.py"
DIRECTION_VERSION = "gpt54-time-budget-codex-direction-v1"
RESULT = "step2_inference_results.json"
RESERVATION_SUFFIX = ".time-budget-result-reserved.json"
MAX_DIRECTION_BYTES = 65_536


class CodexObservationRefused(ValueError):
    """Static refusal; absence of a result is not evidence of no paid effect."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CodexObservationRefused(reason)


def _bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _sha256(value: str) -> str:
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             "independent_sha256_required")
    return value


def _expected_identity(value: dict) -> dict:
    _require(type(value) is dict and set(value) == {"sha256", "size"}, "independent_identity_required")
    _sha256(value["sha256"])
    _require(type(value["size"]) is int and 0 < value["size"] <= registration.MAX_MANIFEST_BYTES,
             "independent_identity_size_bound")
    return dict(value)


def _provider(config: dict, model_binding: dict) -> CodexProviderSettings:
    """Resolve the registered Foundry route without creating a client or token."""
    settings = AzureAIRouteSettings.from_env(os.environ)
    route = settings.select(AzureAIWorkload.INFERENCE)
    _require(not check_route_is_the_one_the_plan_fixed(route, model_binding, settings=settings),
             "registered_codex_route_required")
    block = config["execution"]["codex"]
    endpoint = resolve_endpoint_setting(block, os.environ)
    _same("resolved Codex route", endpoint, route.endpoint.url)
    return CodexProviderSettings(
        endpoint=endpoint, model=block["model"], provider_id=block["provider_id"],
        query_params=dict(block.get("query_params") or {}),
        reasoning_effort=block["reasoning_effort"], model_context_window=block["model_context_window"],
        request_max_retries=block["request_max_retries"], stream_max_retries=block["stream_max_retries"],
    )


def _provider_binding(provider: CodexProviderSettings) -> dict:
    # Only digests leave the callable. The existing auth argv names the isolated
    # token helper and approved login location; this does not run that command.
    return {"settings_sha256": seal(asdict(provider)),
            "config_overrides_sha256": seal(provider.config_overrides()),
            "sdk_version": PINNED_CODEX_SDK_VERSION, "cli_version": PINNED_CODEX_CLI_VERSION}


class _ExecutionDirection:
    """Concrete digest-bound check, installed at the existing consumer seam."""

    def __init__(self, *, path, expected_sha256, expected_host_sha256, binding, paths,
                 provider_binding, step0_identity, reviewed_source_sha):
        self.path, self.expected = path, _sha256(expected_sha256)
        self.expected_host = _sha256(expected_host_sha256)
        self.binding, self.paths, self.source = binding, paths, reviewed_source_sha
        size = path.lstat().st_size
        _require(0 < size <= MAX_DIRECTION_BYTES, "direction_size_bound")
        self.data = _read_bytes(path, sha256=self.expected, size=size)
        value = json.loads(self.data, object_pairs_hook=_object)
        _require(type(value) is dict and set(value) == {
            "direction_version", "purpose", "execution_binding", "paths", "host_sha256",
            "provider_binding", "step0_identity", "not_before_unix", "expires_unix",
        }, "direction_schema")
        _same("direction version", value["direction_version"], DIRECTION_VERSION)
        _same("direction purpose", value["purpose"], "execute_one_registered_observation")
        _same("direction execution binding", value["execution_binding"], asdict(binding))
        _same("direction paths", value["paths"], paths)
        _same("direction host", value["host_sha256"], self.expected_host)
        _same("direction provider", value["provider_binding"], provider_binding)
        _same("direction Step0", value["step0_identity"], step0_identity)
        self.begin, self.end = value["not_before_unix"], value["expires_unix"]
        _require(type(self.begin) is int and type(self.end) is int and 0 <= self.begin < self.end,
                 "direction_admission_window")
        self.check(admission=True)

    def check(self, *, admission: bool) -> None:
        _read_bytes(self.path, **_identity(self.data))
        self.host = host_identity.execution_host_identity(self.source)
        _same("independent execution host", self.host["instance_sha256"], self.expected_host)
        if admission:
            _require(self.begin <= time.time() < self.end, "direction_not_current")

    def require_execution_direction(self, binding: registration.ObservationExecutionBinding) -> None:
        _require(type(binding) is registration.ObservationExecutionBinding, "execution_binding_type")
        _same("independent execution binding", asdict(binding), asdict(self.binding))
        self.check(admission=True)


def _capture(raw: dict, marker: dict, direction: _ExecutionDirection, provider_binding: dict):
    observation = marker["observation"]
    task = observation["task_id"]
    control = raw["time_budget_observation"]
    _same("returned control identity", control["identity"], observation)
    _same("returned admission", control["admitted"], True)
    _same("returned policy", control["policy"], "time_budget_observation_deadline_v1")
    _require(control["terminal_reason"] in {"completed", "failed", "cancelled", "abandoned", TIMEOUT},
             "returned_terminal_required")
    _same("returned preparation", raw["handoff_preparation_identity"],
          {"sha256": direction.binding.preparation_sha256, "size": direction.binding.preparation_size})
    _require(type(raw["success"]) is bool and type(raw["text"]) is str and type(raw["files"]) is list,
             "codex_runner_result_shape")
    files = {}
    for item in raw["files"]:
        _require(type(item) is dict and set(item) == {"filename", "content"}
                 and type(item["content"]) is bytes, "codex_deliverable_shape")
        name = canonical_relative_path(item["filename"])
        role = canonical_deliverable_path(task, f"deliverable_files/{task}/{name}")
        _require(role not in files, "codex_deliverable_duplicate")
        files[role] = item["content"]
    diagnostics = raw.get("codex_diagnostics")
    if diagnostics is not None:
        _require(type(diagnostics) is dict and set(diagnostics) == {
            "items_seen", "http_status_code", "rate_limit_kind"}, "codex_diagnostics_shape")
        _require(type(diagnostics["items_seen"]) is int and diagnostics["items_seen"] >= 0,
                 "codex_items_seen")
        status = diagnostics["http_status_code"]
        _require(status is None or type(status) is int and 100 <= status <= 599, "codex_http_status")
        from core.codex_runner import RATE_LIMIT_KINDS
        _require(diagnostics["rate_limit_kind"] is None or diagnostics["rate_limit_kind"] in RATE_LIMIT_KINDS,
                 "codex_rate_limit_kind")
    success = (raw["success"] and control["terminal_reason"] == "completed"
               and control["cleanup_complete"] is True and control["host_reusable"] is True
               and bool(files or raw["text"]) and (not marker["inputs"]["needs_files"] or bool(files)))
    error = raw.get("error")
    safe_error = error if type(error) is str and error in {TIMEOUT, CLEANUP_UNCONFIRMED} else None
    elapsed = control["generation_elapsed_seconds"]
    row = {
        "task_id": task, "status": "success" if success else "error",
        "error": None if success else safe_error or "time_budget_observation_non_success",
        "content": raw["text"], "deliverable_text": raw["text"], "deliverable_files": sorted(files),
        "deliverable_file_records": [{"path": name, **_identity(files[name])} for name in sorted(files)],
        "model": "gpt-5.4", "usage": None,
        "observability": {
            "runner_success": raw["success"], "codex_diagnostics": diagnostics,
            "runner_error_sha256": _identity(error.encode())["sha256"] if type(error) is str else None,
            "required_deliverable_missing": marker["inputs"]["needs_files"] and not bool(files),
            "usage_availability": {"usage_complete": False, "reason": "consumer_does_not_export_native_usage"},
            "native_measurements": {name: None for name in (
                "model_attempt_count", "repeated_request_count", "input_tokens", "output_tokens",
                "written_tokens", "native_retries", "cost_usd")},
        },
        "latency_ms": None if elapsed is None else elapsed * 1000,
        "timestamp": datetime.now(timezone.utc).isoformat(), "retried": False, "resume_round": None,
    }
    validate_step2_progress_results([row], schema_version=STEP2_PROGRESS_SCHEMA)
    payload = canonicalize_inference_payload({
        "experiment_id": observation["run_id"], "condition": "codex", "execution_mode": "codex_foundry",
        "model": "gpt-5.4", "source": "openai/gdpval", "results": [row], "time_budget_observation": control,
        "observation_execution": {
            "direction_sha256": direction.expected, "host": direction.host, "provider_binding": provider_binding,
            "preparation_identity": raw["handoff_preparation_identity"],
            "runtime_source": marker["runtime_source"], "frozen_grader": marker["frozen_grader"],
            "inputs": marker["inputs"], "condition_template": marker["condition_template"],
            "configuration": marker["files"][registration.HANDOFF_CONFIG], "entrypoint": ENTRYPOINT,
            "paths_sha256": seal(direction.paths), "grading_performed": False, "upload_performed": False,
        },
    })
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    return payload, files


def run_codex_observation(
    plan: dict, *, observation: ObservationIdentity, direction_path: Path,
    expected_direction_sha256: str, expected_host_sha256: str,
    preparation_directory: Path, expected_preparation_identity: dict,
    runtime_root: Path, expected_reviewed_source_sha: str,
    frozen_grader_root: Path, expected_grader_source_sha: str,
    input_registration_root: Path, expected_input_source_sha: str, input_registration_path: str,
    dataset_parquet: Path, reference_root: Path, step0_manifest: Path, expected_step0_identity: dict,
    observation_directory: Path, destination: Path,
) -> dict:
    """One registered r1/r2 task, using the existing nonrenewable local store.

    The independent direction names the store; this is not distributed/global
    once-only protection. A construction/interruption without a returned
    terminal record stays uncertain and cannot fabricate a canonical row.
    """
    _require(type(observation) is ObservationIdentity and observation.condition == "codex",
             "registered_codex_observation_only")
    observation = ObservationIdentity(**asdict(observation))
    _same("independent runtime source", observation.reviewed_source_sha, expected_reviewed_source_sha)
    _same("independent frozen source", expected_grader_source_sha, registration.ACCEPTED_BASE_SHA)
    expected = _expected_identity(expected_preparation_identity)
    step0_expected = _expected_identity(expected_step0_identity)
    paths = {name: registration._handoff_path(value) for name, value in {
        "direction": direction_path, "preparation": preparation_directory,
        "runtime_root": runtime_root, "frozen_grader_root": frozen_grader_root,
        "input_registration_root": input_registration_root, "dataset_parquet": dataset_parquet,
        "reference_root": reference_root, "step0_manifest": step0_manifest,
        "observation_directory": observation_directory, "destination": destination,
        "native_run_root": resolve_run_root_base(),
    }.items()}
    output, prep = paths["destination"], paths["preparation"]
    reservation = output.with_name(output.name + RESERVATION_SUFFIX)
    prep_reservation = prep.with_name(prep.name + registration.HANDOFF_RESERVATION_SUFFIX)
    consumed = prep.with_name(prep.name + registration.HANDOFF_CONSUMED_SUFFIX)
    _require(output.parent.is_dir(), "result_parent_required")
    for name, source in paths.items():
        if name != "destination":
            _require(not any(target.is_relative_to(source) or source.is_relative_to(target)
                             for target in (output, reservation)), "result_source_overlap")
        if name != "native_run_root":
            _require(not (source.is_relative_to(paths["native_run_root"])
                          or paths["native_run_root"].is_relative_to(source)), "native_source_overlap")
    _require(type(input_registration_path) is str
             and _path(paths["input_registration_root"], input_registration_path).relative_to(
                 paths["input_registration_root"]).as_posix() == input_registration_path,
             "input_registration_path_alias")

    def absent(*, before_generation):
        _require(not any(os.path.lexists(path) for path in (output, reservation)), "result_destination_exists")
        if before_generation:
            _require(not os.path.lexists(consumed), "direction_observation_already_consumed")

    absent(before_generation=True)
    binding = registration.ObservationExecutionBinding(
        expected["sha256"], expected["size"], _canonical_json(asdict(observation)),
        expected_grader_source_sha, registration.ACCEPTED_BASE_TREE, registration.FROZEN_TEMPLATE_SHA256,
        str(prep), str(paths["observation_directory"]),
    )
    direction_paths = {**{name: str(path) for name, path in paths.items()},
                       "input_source_sha": expected_input_source_sha, "input_registration_path": input_registration_path}
    with ExitStack() as held, ExitStack() as sources:
        local_files = {ENTRYPOINT: Path(__file__), host_identity.ENTRYPOINT: Path(host_identity.__file__)}
        _, tree, entries = sources.enter_context(registration._reviewed_source(
            paths["runtime_root"], expected_reviewed_source_sha, set(local_files)))
        _same("independent runtime tree", tree, observation.reviewed_source_tree)
        for role, local in local_files.items():
            _read_bytes(local, **entries[role])
        common = dict(
            run_id=observation.run_id, task_id=observation.task_id,
            runtime_root=paths["runtime_root"], expected_reviewed_source_sha=expected_reviewed_source_sha,
            frozen_grader_root=paths["frozen_grader_root"], expected_grader_source_sha=expected_grader_source_sha,
            input_registration_root=paths["input_registration_root"], expected_input_source_sha=expected_input_source_sha,
            input_registration_path=input_registration_path, dataset_parquet=paths["dataset_parquet"],
            reference_root=paths["reference_root"], step0_manifest=paths["step0_manifest"],
        )
        _read_bytes(paths["step0_manifest"], **step0_expected)
        marker, handoff_files, reread_inputs = registration._observation_handoff_data(
            plan, sources=sources, destination=prep, **common)
        _same("independent observation", marker["observation"], asdict(observation))
        _same("independent preparation", _identity(_bytes(marker)), expected)
        _same("independent Step0", marker["inputs"]["step0_manifest"], step0_expected)
        config = json.loads(handoff_files[registration.HANDOFF_CONFIG])["configuration"]
        provider_binding = _provider_binding(_provider(config, plan["shared"]["model"]))
        check_direction = held.enter_context(_held_parents(paths["direction"].parent, (paths["direction"].name,)))
        direction = _ExecutionDirection(
            path=paths["direction"], expected_sha256=expected_direction_sha256,
            expected_host_sha256=expected_host_sha256, binding=binding, paths=direction_paths,
            provider_binding=provider_binding, step0_identity=step0_expected,
            reviewed_source_sha=expected_reviewed_source_sha,
        )
        check_preparation = held.enter_context(_held_parents(prep, (*handoff_files, registration.HANDOFF_READY)))
        check_preparation_parent = held.enter_context(_held_parents(prep.parent, (
            prep_reservation.name, consumed.name, prep.name + "/" + registration.HANDOFF_READY)))
        check_output = held.enter_context(_held_parents(output.parent, (output.name, reservation.name)))
        check, mkdir, descriptor = held.enter_context(_publication_parents(output.parent))

        def reread_handoff():
            members = {*handoff_files, registration.HANDOFF_READY}
            for role, data in handoff_files.items():
                members.update(parent.relative_to(prep).as_posix() for parent in _path(prep, role).parents
                               if parent != prep and parent.is_relative_to(prep))
                _read_bytes(_path(prep, role), **_identity(data))
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

        provider_installed = False

        def codex_provider_for(actual):
            nonlocal provider_installed
            _require(not provider_installed, "codex_provider_already_installed")
            _same("consumer Codex configuration", actual, config)
            provider = _provider(actual, plan["shared"]["model"])
            _same("independent provider binding", _provider_binding(provider), provider_binding)
            _same("native run root", str(registration._handoff_path(resolve_run_root_base())), paths["native_run_root"].as_posix())
            provider_installed = True
            return provider

        def require_execution_direction(actual):
            direction.require_execution_direction(actual)
            for role, local in local_files.items():
                _read_bytes(local, **entries[role])
                _read_bytes(paths["runtime_root"] / role, **entries[role])
            _same("admission provider binding", _provider_binding(_provider(config, plan["shared"]["model"])),
                  provider_binding)
            _same("admission native run root", str(registration._handoff_path(resolve_run_root_base())),
                  direction_paths["native_run_root"])
            check_direction()
            check_output()
            absent(before_generation=True)

        raw = registration.consume_observation_handoff(
            plan, **common, preparation_directory=prep, expected_preparation_identity=expected,
            observation_directory=paths["observation_directory"],
            require_execution_direction=require_execution_direction, codex_provider_for=codex_provider_for,
        )
        _require(provider_installed, "codex_provider_not_installed")
        payload, files = _capture(raw, marker, direction, provider_binding)
        reread_inputs()
        reread_handoff()
        direction.check(admission=False)
        check_direction()
        check_output()
        check()
        absent(before_generation=False)
        reservation_data = _bytes({"reservation_version": "gpt54-time-budget-codex-result-v1",
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
        # Capture does not renew cleanup, change its outcome or allow a retry.
        reread_handoff()
        sources.close()
        for role, local in local_files.items():
            _read_bytes(local, **entries[role])
        registration._require_running_observation_sources(paths["runtime_root"])
        direction.check(admission=False)
        check_direction()
        check_output()
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
        raise CodexObservationRefused("invalid_arguments")


def main(argv=None):
    parser = _Parser(description=__doc__)
    for name in ("direction", "preparation-directory", "runtime-root", "frozen-grader-root",
                 "input-registration-root", "dataset-parquet", "reference-root", "step0-manifest",
                 "observation-directory", "destination"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("direction-sha256", "host-sha256", "preparation-sha256", "step0-sha256", "reviewed-source-sha",
                 "reviewed-source-tree", "grader-source-sha", "input-source-sha", "input-registration-path",
                 "registration-sha256", "input-sha256", "run-id", "task-id"):
        parser.add_argument("--" + name, required=True)
    for name in ("preparation-size", "step0-size", "repeat"):
        parser.add_argument("--" + name, type=int, required=True)
    try:
        args = parser.parse_args(argv)
        observation = ObservationIdentity(
            registration.STUDY_ID, args.run_id, "codex", args.repeat, args.task_id,
            args.reviewed_source_sha, args.reviewed_source_tree, args.registration_sha256, args.input_sha256)
        result = run_codex_observation(
            registration.load_registration(args.runtime_root / registration.REGISTRATION_PATH),
            observation=observation, direction_path=args.direction, expected_direction_sha256=args.direction_sha256,
            expected_host_sha256=args.host_sha256, preparation_directory=args.preparation_directory,
            expected_preparation_identity={"sha256": args.preparation_sha256, "size": args.preparation_size},
            runtime_root=args.runtime_root, expected_reviewed_source_sha=args.reviewed_source_sha,
            frozen_grader_root=args.frozen_grader_root, expected_grader_source_sha=args.grader_source_sha,
            input_registration_root=args.input_registration_root, expected_input_source_sha=args.input_source_sha,
            input_registration_path=args.input_registration_path, dataset_parquet=args.dataset_parquet,
            reference_root=args.reference_root, step0_manifest=args.step0_manifest,
            expected_step0_identity={"sha256": args.step0_sha256, "size": args.step0_size},
            observation_directory=args.observation_directory, destination=args.destination)
    except (Exception, KeyboardInterrupt, ObservationTimedOut, ObservationCleanupExpired):
        # No provider message, traceback, original input or credential on stdout.
        # Incomplete publication/cleanup cannot become success or retry authority.
        print(_canonical_json({"result_published": False, "reason": "codex_observation_refused_or_incomplete",
                               "retry_allowed": False}))
        return 2
    print(_canonical_json(result))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
