"""Read one bound retained result or native uncertainty; publish no private prose.

The leader's digest-bound request supplies an already verified completion
envelope, not authority discovered in storage. C is this readout's source; R is
the retained observation's source. No input, claim, admission or grader runs.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from functools import partial
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs

import yaml

import codex_budget_pilot_output as storage
import gpt54_time_budget_codex_ci as native_execution
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_storage_metadata as metadata
import gpt54_time_budget_v2_ci as execution
from codex_ci_input_intake import _hf_environment
from core.agentic_v2_contract import ERROR_TYPES
from core.agentic_v2_preregistration import seal
from core.inference_manifest import (
    STEP2_PROGRESS_SCHEMA, canonicalize_inference_payload, validate_step2_progress_results,
)
from core.reference_integrity import validate_reference_record
from core.result_fingerprint import validate_inference_result_fingerprint
from core.time_budget_observation_deadline import CLEANUP_UNCONFIRMED, TIMEOUT, ObservationIdentity
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_disposable_checkout import _git, _repository
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _held_parents, _root
from gpt54_v2_grading_input import _object, _read_bytes, _same

HELPER = "batch-runner/gpt54_time_budget_result_readout.py"
WORKFLOW = ".github/workflows/gpt54-time-budget-result-readout.yml"
JOB = "readout"
SOURCE_BASENAME = "time-budget-readout-source"
BASENAME = "time-budget-result-readout.json"
FORMAT = "gpt54-time-budget-result-readout-v1"
REQUEST_FORMAT = "gpt54-time-budget-result-readout-request-v1"
PURPOSE = "read_one_retained_canonical_result"
UNCERTAINTY_FORMAT = "gpt54-time-budget-native-uncertainty-readout-v1"
UNCERTAINTY_REQUEST_FORMAT = "gpt54-time-budget-native-uncertainty-readout-request-v1"
UNCERTAINTY_PURPOSE = "read_one_retained_native_uncertainty_manifest"
# The fixed private format written by native_execution.retain, not a result row.
UNCERTAINTY_MANIFEST_FORMAT = "gpt54-time-budget-first-codex-private-output-v1"
SECONDS = metadata.SECONDS
MAX_ENVELOPE_BYTES = 65536
SOURCE_ROLES = metadata.SOURCE_ROLES | execution.SOURCE_ROLES | native_execution.SOURCE_ROLES | {
    HELPER, WORKFLOW, registration.REGISTRATION_PATH, "batch-runner/ghcp_vm_input_bundle.py",
}
CELL_KEYS = {"study_id", "run_id", "condition", "repeat", "task_id"}
ERRORS = frozenset(ERROR_TYPES) | {TIMEOUT, CLEANUP_UNCONFIRMED}
CONTROL_FLAGS = {
    "admitted", "interruption_attempted", "interruption_acknowledged", "cleanup_complete",
    "cleanup_expired", "owned_processes_stopped", "host_reusable", "remote_cancellation_confirmed",
    "remote_billing_bound",
}
CONTROL_TIMES = {
    "first_start_monotonic", "generation_elapsed_seconds", "cleanup_deadline_monotonic",
    "cleanup_finished_monotonic", "cleanup_elapsed_seconds",
}
CONTROL_STATIC = {
    "policy": "time_budget_observation_deadline_v1",
    "process_ownership": "linux_exclusive_subreaper_pidfd_waitid",
    "interruption_acknowledgement_scope": "local_runtime_only_not_remote_cancellation",
}


class ResultReadoutRefused(ValueError):
    """Static refusal only; transport or result text is never public output."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ResultReadoutRefused(reason)


def _keys(value: object, keys: set[str]) -> None:
    _require(type(value) is dict and set(value) == keys, "readout_schema_refused")


def _bytes(value: object) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _result_registration(root: Path, source: dict) -> dict:
    """Read only the constant registration blob at independently bound R.

    C supplies the validators, not a replacement seal for historical results.
    The existing Git guard forbids transport, replacements and caller hooks;
    no historical code is checked out or executed.
    """
    for suffix, expected in (("^{commit}", source["sha"]), ("^{tree}", source["tree"])):
        _require(_git(root, "rev-parse", "--verify", "--end-of-options", source["sha"] + suffix).stdout
                 == (expected + "\n").encode("ascii"), "result_source_identity_refused")
    entry = _git(root, "ls-tree", "-z", "--full-tree", source["sha"], "--", registration.REGISTRATION_PATH).stdout
    match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t"
                         + re.escape(registration.REGISTRATION_PATH.encode("utf-8")) + b"\0", entry)
    _require(match is not None, "result_registration_blob_required")
    blob = match.group(1).decode("ascii")
    size = int(_git(root, "cat-file", "-s", blob).stdout)
    _require(0 < size <= registration.MAX_MANIFEST_BYTES, "result_registration_size_refused")
    data = _git(root, "cat-file", "blob", blob).stdout
    _require(len(data) == size, "result_registration_size_refused")
    plan = yaml.load(data.decode("utf-8"), Loader=registration._RegistrationLoader)
    _require(type(plan) is dict, "result_registration_schema_refused")
    return plan


@contextmanager
def checked_request(*, request_json: str, expected_request_sha256: str,
                    reviewed_source_sha: str, reviewed_source_tree: str, runtime_root: Path):
    """Bind a trusted request and actual Actions C before any credential use."""
    data = request_json.encode("utf-8")
    _require(0 < len(data) <= execution.MAX_REQUEST_BYTES and storage._hash(expected_request_sha256)
             and _identity(data)["sha256"] == expected_request_sha256, "independent_request_digest_required")
    request = json.loads(data, object_pairs_hook=_object)
    uncertainty = type(request) is dict and request.get("purpose") == UNCERTAINTY_PURPOSE
    _keys(request, {"format", "purpose", "controller", "ci", "registration_sha256", "cell", "completion"}
          | ({"execution_request_identity"} if uncertainty else set()))
    _require((request["format"], request["purpose"]) == (
        (UNCERTAINTY_REQUEST_FORMAT, UNCERTAINTY_PURPOSE) if uncertainty else (REQUEST_FORMAT, PURPOSE)),
             "readout_request_required")
    _require(storage._hash(reviewed_source_sha, 40) and storage._hash(reviewed_source_tree, 40),
             "independent_controller_identity_required")
    _same("readout controller", request["controller"], {"sha": reviewed_source_sha, "tree": reviewed_source_tree})
    ci = request["ci"]
    _require(type(ci) is dict and type(ci.get("run_number")) is int and ci["run_number"] > 0,
             "independent_dispatch_number_required")
    _same("readout Actions request", ci, {
        "repository": metadata.REPOSITORY, "workflow": WORKFLOW, "ref": "refs/heads/main",
        "actor": metadata.OWNER, "job": JOB, "attempt": 1, "run_number": ci["run_number"],
        "runner": "ubuntu-22.04", "runner_os": "Linux", "runner_arch": "X64",
    })
    expected = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": metadata.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": metadata.OWNER,
        "GITHUB_TRIGGERING_ACTOR": metadata.OWNER, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": JOB,
        "GITHUB_RUN_NUMBER": str(ci["run_number"]), "GITHUB_SHA": reviewed_source_sha,
        "READOUT_WORKFLOW_SHA": reviewed_source_sha,
        "GITHUB_WORKFLOW_REF": metadata.REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
        "ImageOS": "ubuntu22", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
    }
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    _require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None
             and sys.version_info[:3] == (3, 10, 12), "readout_runtime_identity_required")
    expected["GITHUB_RUN_ID"] = run_id
    root = _root(runtime_root)
    bootstrap, common = _repository(Path(os.environ.get("GITHUB_WORKSPACE", "")))
    runner_temp = _root(Path(os.environ.get("RUNNER_TEMP", "")))

    def check_bootstrap():
        _require(all(os.environ.get(key) == value for key, value in expected.items()), "actions_context_refused")
        _require(str(bootstrap) == os.environ.get("GITHUB_WORKSPACE") and bootstrap.resolve() == bootstrap
                 and common == bootstrap / ".git" and common.is_dir()
                 and str(runner_temp) == os.environ.get("RUNNER_TEMP") and runner_temp.resolve() == runner_temp
                 and root == runner_temp / SOURCE_BASENAME and str(root) == str(runtime_root)
                 and root.resolve() == root and _repository(root)[1] == common, "canonical_linked_source_required")
        for revision, identity in (("HEAD^{commit}", reviewed_source_sha), ("HEAD^{tree}", reviewed_source_tree)):
            _require(_git(bootstrap, "rev-parse", "--verify", revision).stdout == (identity + "\n").encode(),
                     "actions_checkout_identity_changed")

    check_bootstrap()
    with registration._reviewed_source(root, reviewed_source_sha, SOURCE_ROLES) as (_, tree, identities):
        _same("controller tree", tree, reviewed_source_tree)
        for name, identity in identities.items():
            module_name = name.removeprefix("batch-runner/").removesuffix(".py").replace("/", ".")
            module = sys.modules[__name__] if name == HELPER else sys.modules.get(module_name)
            if name.endswith(".py") and module is not None:
                _read_bytes(Path(module.__file__), **identity)
        cell = request["cell"]
        _keys(cell, CELL_KEYS)
        completion = request["completion"]
        if uncertainty:
            _same("fixed native uncertainty cell", cell, native_execution.CELL)
            native_execution.validate_envelope(completion)
            _require(completion["retention"] == "acknowledged" and completion["status"] == "uncertain",
                     "retained_native_uncertainty_required")
            identity = request["execution_request_identity"]
            _keys(identity, {"sha256", "size"})
            validate_reference_record(identity)
            _require(0 < identity["size"] <= execution.MAX_REQUEST_BYTES, "execution_request_size_refused")
            _same("independent execution request hash", identity["sha256"], completion["request_sha256"])
        else:
            execution.validate_envelope(completion, expected_cell=cell)
            _require(completion["retention"] == "acknowledged" and completion["status"] in ("success", "error"),
                     "retained_canonical_result_required")
        plan = _result_registration(root, completion["source"])
        _same("source-bound registration", request["registration_sha256"], seal(plan))
        # Canonical rows remain V2-only. The native branch reads no result row.
        _require(cell["study_id"] == registration.STUDY_ID
                 and cell["condition"] == ("codex" if uncertainty else "sandbox_v2")
                 and type(cell["repeat"]) is int and any(
                     all(cell[key] == run[key] for key in ("run_id", "condition", "repeat")) for run in plan["runs"])
                 and cell["task_id"] in [row["task_id"] for row in plan["shared"]["dataset"]["tasks"]],
                 "registered_observation_required")
        if uncertainty:
            _same("registered first native task", cell["task_id"], plan["shared"]["dataset"]["tasks"][0]["task_id"])
        yield {"request": request, "request_sha256": expected_request_sha256, "plan": plan,
               "ci": {"run_id": run_id, "run_number": ci["run_number"], "job": JOB, "attempt": 1}}
    check_bootstrap()


def _tokens(value: object, *, details: bool = False) -> None:
    if value is None:
        return
    _keys(value, {"input_tokens", "output_tokens"} | (
        {"cached_input_tokens", "reasoning_output_tokens"} if details else set()))
    _require(all(type(value[name]) is int and value[name] >= 0 for name in ("input_tokens", "output_tokens")),
             "reported_usage_refused")
    if details:
        for name, total in (("cached_input_tokens", "input_tokens"), ("reasoning_output_tokens", "output_tokens")):
            _require(value[name] is None or type(value[name]) is int and 0 <= value[name] <= value[total],
                     "reported_usage_subset_refused")


def _availability(value: dict, usage: dict | None) -> None:
    counters = {"client_construction_attempts", "responses_create_invocations", "completed_responses"}
    unavailable = {"native_model_attempts", "repeated_request_count", "written_tokens"}
    constants = {"unavailable_counters_are_not_zero": True, "cached_and_reasoning_tokens_are_subsets": True,
                 "money_hard_cap": False}
    _keys(value, counters | unavailable | set(constants) | {
        "response_records", "usage_complete", "reported_token_subtotals", "route_fingerprint"})
    _require(all(type(value[name]) is int and value[name] >= 0 for name in counters)
             and all(value[name] is None for name in unavailable), "availability_counters_refused")
    _same("availability constants", {name: value[name] for name in constants}, constants)
    records = value["response_records"]
    _require(type(records) is list and len(records) <= 128
             and len(records) == value["responses_create_invocations"], "response_records_refused")
    for record in records:
        _keys(record, {"response_returned", "usage", "model_binding"})
        _require(type(record["response_returned"]) is bool and record["model_binding"] in {
            "unavailable", "matched", "unreported_or_mismatched"}, "response_category_refused")
        _tokens(record["usage"], details=True)
        _require(record["response_returned"] or record["usage"] is None, "response_usage_refused")
    _same("completed response count", value["completed_responses"], sum(row["response_returned"] for row in records))
    complete = bool(records) and all(row["usage"] is not None for row in records)
    _same("usage availability", value["usage_complete"], complete)
    totals = {name: sum(row["usage"][name] for row in records if row["usage"] is not None)
              for name in ("input_tokens", "output_tokens")}
    _same("reported subtotals", value["reported_token_subtotals"],
          totals if any(row["usage"] is not None for row in records) else None)
    _same("complete reported usage", usage, totals if complete else None)
    _require(value["route_fingerprint"] is None or storage._hash(value["route_fingerprint"]), "route_hash_refused")


def _summary(value: dict, completion: dict) -> None:
    _keys(value, {"status", "error", "runner_success", "runner_result_verified", "runner_error",
                  "required_deliverable_missing", "control", "usage", "usage_availability", "deliverables"})
    _require(value["status"] in ("success", "error") and (
        value["error"] is None if value["status"] == "success" else
        value["error"] in ERRORS | {"time_budget_observation_non_success"}), "result_error_enum_refused")
    _require(value["runner_error"] is None or value["runner_error"] in ERRORS, "runner_error_enum_refused")
    _require(all(type(value[name]) is bool for name in (
        "runner_success", "runner_result_verified", "required_deliverable_missing")), "runner_flags_refused")
    control = value["control"]
    _keys(control, CONTROL_FLAGS | set(CONTROL_STATIC) | {"terminal_reason"})
    _same("control constants", {name: control[name] for name in CONTROL_STATIC}, CONTROL_STATIC)
    _require(all(type(control[name]) is bool for name in CONTROL_FLAGS) and control["admitted"]
             and control["terminal_reason"] in {"completed", "failed", "cancelled", "abandoned", TIMEOUT}
             and not control["remote_cancellation_confirmed"] and not control["remote_billing_bound"],
             "terminal_control_refused")
    _tokens(value["usage"])
    _availability(value["usage_availability"], value["usage"])
    _keys(value["deliverables"], {"count", "bytes"})
    _require(all(type(item) is int and item >= 0 for item in value["deliverables"].values()), "deliverable_totals_refused")
    for name in ("status", "usage"):
        _same("completion " + name, value[name], completion[name])
    for name in ("terminal_reason", "cleanup_complete", "host_reusable"):
        _same("completion " + name, control[name], completion[name])


def project_result(data: bytes, context: dict) -> dict:
    """Validate authenticated canonical bytes, then return only typed fields."""
    request, plan = context["request"], context["plan"]
    completion, cell = request["completion"], request["cell"]
    _same("independent result bytes", _identity(data), completion["result_identity"])
    payload = json.loads(data, object_pairs_hook=_object)
    _keys(payload, {"experiment_id", "condition", "execution_mode", "model", "source", "results",
                    "time_budget_observation", "observation_execution", "result_fingerprint"})
    _require(data == _bytes(payload), "canonical_result_bytes_required")
    _same("canonical result semantics", canonicalize_inference_payload(payload), payload)
    _same("independent result fingerprint", validate_inference_result_fingerprint(payload), completion["result_fingerprint"])
    validate_step2_progress_results(payload["results"], schema_version=STEP2_PROGRESS_SCHEMA)
    _require(len(payload["results"]) == 1, "single_result_required")
    row, control, captured = payload["results"][0], payload["time_budget_observation"], payload["observation_execution"]
    for name, expected in {"experiment_id": cell["run_id"], "condition": cell["condition"],
                           "execution_mode": "agentic_sandbox_v2", "model": plan["shared"]["model"]["deployment"],
                           "source": plan["shared"]["dataset"]["repo_id"]}.items():
        _same("result " + name, payload[name], expected)
    _keys(row, {"task_id", "status", "error", "content", "deliverable_text", "deliverable_files",
                "deliverable_file_records", "model", "usage", "observability", "latency_ms", "timestamp",
                "retried", "resume_round"})
    _same("selected task", row["task_id"], cell["task_id"])
    _same("row model", row["model"], payload["model"])
    _same("no replay", [row["retried"], row["resume_round"]], [False, None])
    _keys(control, CONTROL_FLAGS | CONTROL_TIMES | set(CONTROL_STATIC) | {"identity", "terminal_reason"})
    _require(all(control[name] is None or type(control[name]) in (int, float)
                 and math.isfinite(control[name]) and control[name] >= 0 for name in CONTROL_TIMES), "control_times_refused")
    identity = asdict(ObservationIdentity(**control["identity"]))
    _same("result cell", {name: identity[name] for name in CELL_KEYS}, cell)
    _same("result R", {"sha": identity["reviewed_source_sha"], "tree": identity["reviewed_source_tree"]}, completion["source"])
    _same("result registration", identity["registration_sha256"], request["registration_sha256"])
    _keys(captured, {"direction_sha256", "host", "preparation_identity", "runtime_source", "frozen_grader", "inputs",
                     "condition_template", "configuration", "resolved_instructions", "entrypoint", "paths_sha256",
                     "grading_performed", "upload_performed"})
    _same("captured R", captured["runtime_source"], {
        "source_sha": identity["reviewed_source_sha"], "source_tree": identity["reviewed_source_tree"]})
    _same("captured input seal", seal(captured["inputs"]), identity["input_sha256"])
    _same("captured input task", captured["inputs"]["task_id"], cell["task_id"])
    _same("frozen grader binding", captured["frozen_grader"], {
        "source_sha": registration.ACCEPTED_BASE_SHA, "source_tree": registration.ACCEPTED_BASE_TREE,
        "template_source_sha256": registration.FROZEN_TEMPLATE_SHA256, "template_config_path": registration.GRADER,
        "materialized_config_path": None, "materialized_grader_source_sha256": None,
        "execution_source": "frozen_source_only_not_runtime_root",
    })
    for name in ("preparation_identity", "configuration"):
        validate_reference_record(captured[name])
    _keys(captured["host"], {"policy", "instance_sha256", "ci_instance_sha256", "ownership_confirmed"})
    _same("host evidence policy", captured["host"]["policy"], "linux-boot-namespace-user-ci-instance-v1")
    _same("host metadata is not ownership", captured["host"]["ownership_confirmed"], False)
    _same("captured host", captured["host"]["instance_sha256"], completion["host_sha256"])
    _same("captured entrypoint", captured["entrypoint"], execution.observation.ENTRYPOINT)
    _same("no grading or upload by callable", [captured["grading_performed"], captured["upload_performed"]], [False, False])
    _require(all(storage._hash(captured[name]) for name in ("direction_sha256", "paths_sha256")), "capture_hash_refused")
    observability = row["observability"]
    _keys(observability, {"runner_success", "runner_result_verified", "runner_error", "runner_error_sha256",
                         "v2_audit_sha256", "usage_availability", "required_deliverable_missing"})
    _require(storage._hash(observability["v2_audit_sha256"]) and (observability["runner_error_sha256"] is None
             or storage._hash(observability["runner_error_sha256"])), "audit_digest_refused")
    records = row["deliverable_file_records"]
    _require(type(records) is list and len(records) <= 120, "deliverable_records_refused")
    for record in records:
        _keys(record, {"path", "sha256", "size"})
        validate_reference_record({name: record[name] for name in ("sha256", "size")})
    _same("deliverable identities", [item["path"] for item in records], row["deliverable_files"])
    summary = {"status": row["status"], "error": row["error"], "usage": row["usage"],
               **{name: observability[name] for name in ("runner_success", "runner_result_verified", "runner_error",
                                                        "required_deliverable_missing", "usage_availability")},
               "control": {name: control[name] for name in CONTROL_FLAGS | set(CONTROL_STATIC) | {"terminal_reason"}},
               "deliverables": {"count": len(records), "bytes": sum(item["size"] for item in records)}}
    _summary(summary, completion)
    return summary


UNCERTAINTY_SUMMARY = {
    "status": "uncertain", "result": "unavailable_no_fabricated_study_row", "retained_files": "empty",
    "terminal_reason": None, "usage": None, "cleanup_complete": None, "host_reusable": None,
    "native_model_calls_and_cost": "unavailable",
    "manifest_identity_basis": "observed_not_independently_expected",
    "claim_and_request_objects": "not_reread",
    "failure_authority": "retained_static_diagnostic_only",
}


def _uncertainty_summary(value: dict) -> None:
    _keys(value, set(UNCERTAINTY_SUMMARY) | {"failure", "observed_manifest_identity"})
    _same("uncertainty classifications", {name: value[name] for name in UNCERTAINTY_SUMMARY}, UNCERTAINTY_SUMMARY)
    identity = value["observed_manifest_identity"]
    _keys(identity, {"sha256", "size"})
    validate_reference_record(identity)
    _require(0 < identity["size"] <= storage.MAX_MANIFEST_BYTES, "observed_manifest_size_refused")
    execution._check_execution_failure({"outcome": "refused_or_uncertain", "returned": None,
                                       "failure": value["failure"]})


def project_uncertainty_manifest(data: bytes, context: dict) -> dict:
    """Bind the immutable manifest without inventing an independent byte hash."""
    request, completion = context["request"], context["request"]["completion"]
    _require(0 < len(data) <= storage.MAX_MANIFEST_BYTES, "uncertainty_manifest_size_refused")
    manifest = json.loads(data, object_pairs_hook=_object)
    _keys(manifest, {"format", "observation", "request_identity", "claim_commit", "claim_identity",
                     "execution_receipt", "result", "files", "grading_performed"})
    _require(data == native_execution._encoded(manifest), "canonical_uncertainty_manifest_required")
    _same("native uncertainty format", manifest["format"], UNCERTAINTY_MANIFEST_FORMAT)
    identity = asdict(ObservationIdentity(**manifest["observation"]))
    _same("manifest cell", {name: identity[name] for name in CELL_KEYS}, request["cell"])
    _same("manifest R", {"sha": identity["reviewed_source_sha"], "tree": identity["reviewed_source_tree"]},
          completion["source"])
    _same("manifest registration", identity["registration_sha256"], request["registration_sha256"])
    _same("manifest execution request", manifest["request_identity"], request["execution_request_identity"])
    _same("manifest claim commit", manifest["claim_commit"], completion["claim_commit"])
    _keys(manifest["claim_identity"], {"sha256", "size"})
    validate_reference_record(manifest["claim_identity"])
    _require(0 < manifest["claim_identity"]["size"] <= storage.MAX_MANIFEST_BYTES, "manifest_claim_size_refused")
    _same("manifest absent result", manifest["result"], "unavailable_no_fabricated_study_row")
    _keys(manifest["files"], set())
    _require(manifest["grading_performed"] is False, "manifest_grading_refused")
    receipt = manifest["execution_receipt"]
    _require(type(receipt) is dict, "retained_failure_receipt_required")
    execution._check_execution_failure(receipt)
    _require("failure" in receipt, "retained_failure_codes_unavailable")
    summary = {**UNCERTAINTY_SUMMARY, "failure": dict(receipt["failure"]),
               "observed_manifest_identity": _identity(data)}
    _uncertainty_summary(summary)
    return summary


def _binding(context: dict) -> dict:
    request, completion = context["request"], context["request"]["completion"]
    binding = {"format": FORMAT, "controller": request["controller"], "ci": context["ci"],
            "request_sha256": context["request_sha256"], "target_identity_sha256": metadata.TARGET_SHA256,
            "cell": request["cell"], "result_source": completion["source"],
            "execution_request_sha256": completion["request_sha256"], "output_commit": completion["output_commit"],
            "result_identity": completion["result_identity"], "result_fingerprint": completion["result_fingerprint"],
            "retry_allowed": False, "grading_performed": False}
    if request["purpose"] == UNCERTAINTY_PURPOSE:
        binding.update(format=UNCERTAINTY_FORMAT, observation_source=binding.pop("result_source"),
                       execution_request_identity=request["execution_request_identity"],
                       registration_sha256=request["registration_sha256"], claim_commit=completion["claim_commit"],
                       host_sha256=completion["host_sha256"])
    return binding


def validate_envelope(value: dict, context: dict) -> None:
    binding = _binding(context)
    _keys(value, set(binding) | {"timestamp_utc", "verified_private", "outcome", "summary"})
    _same("readout binding", {name: value[name] for name in binding}, binding)
    stamp = value["timestamp_utc"]
    _require(type(stamp) is str and datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").strftime(
        "%Y-%m-%dT%H:%M:%SZ") == stamp, "readout_timestamp_refused")
    _require(value["verified_private"] is None or value["verified_private"] is True, "readout_privacy_refused")
    _require(value["outcome"] in ("read", "refused"), "readout_outcome_refused")
    if value["outcome"] == "read":
        _require(value["verified_private"] is True, "private_result_required")
        if context["request"]["purpose"] == UNCERTAINTY_PURPOSE:
            _uncertainty_summary(value["summary"])
        else:
            _summary(value["summary"], context["request"]["completion"])
    else:
        _require(value["summary"] is None, "refusal_has_no_result")
    _require(len(_bytes(value)) <= MAX_ENVELOPE_BYTES, "readout_envelope_bound")


def _read_result(context: dict) -> dict:
    value = {**_binding(context), "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "verified_private": None, "outcome": "refused", "summary": None}
    completion, cell = context["request"]["completion"], context["request"]["cell"]
    revision = completion["output_commit"]
    uncertainty = context["request"]["purpose"] == UNCERTAINTY_PURPOSE
    member = native_execution.MANIFEST if uncertainty else execution._namespace(cell)[0] + "/result/" + execution.observation.RESULT
    limit = storage.MAX_MANIFEST_BYTES if uncertainty else max(65536, completion["result_identity"]["size"])
    try:
        _require(_identity(metadata.TARGET.encode())["sha256"] == metadata.TARGET_SHA256, "fixed_target_identity")
        token = os.environ.get("HF_TOKEN", "")
        _require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
                 "explicit_hf_token_required")
        with storage._time_bound(SECONDS) as deadline, _hf_environment(online=True):
            from huggingface_hub import constants
            from huggingface_hub.utils import _http

            _require(constants.HF_HUB_DISABLE_TELEMETRY, "sdk_telemetry_must_be_disabled")
            with storage._hf_client(token, deadline, response_bytes_limit=limit) as api:
                session, attempts = _http.get_session(), 0
                session.follow_redirects = False
                session.headers["Accept-Encoding"] = "identity"

                def request_guard(request):
                    nonlocal attempts
                    storage._remaining(deadline)
                    _require(request.method == "GET" and request.url.scheme == "https"
                             and request.url.host == "huggingface.co" and request.url.port in (None, 443)
                             and request.url.userinfo == b"" and not request.content
                             and request.headers.get("authorization") == "Bearer " + token, "read_only_target_required")
                    if attempts == 0:
                        _require(request.url.path == f"/api/datasets/{metadata.TARGET}/revision/{revision}"
                                 and parse_qs(request.url.query.decode()) == {"expand": ["private", "sha"]},
                                 "immutable_private_metadata_only")
                    else:
                        _require(attempts == 1 and request.url.path == f"/datasets/{metadata.TARGET}/raw/{revision}/{member}"
                                 and not request.url.query, "exact_result_object_only")
                    attempts += 1

                def response_guard(response):
                    _require(response.status_code == 200 and response.headers.get("content-encoding") in (None, "identity"),
                             "readout_http_refused")

                session.event_hooks = {"request": [request_guard], "response": [response_guard]}
                found = storage._metadata(SimpleNamespace(repo_info=partial(api.repo_info, expand=["private", "sha"])),
                                          metadata.TARGET, revision, token, deadline)
                _same("immutable output revision", found["sha"], revision)
                value["verified_private"] = True
                # A raw immutable Git object needs one GET, no HEAD, cache,
                # redirect or LFS request. A pointer/body mismatch refuses.
                with session.stream("GET", f"{storage.HF_ENDPOINT}/datasets/{metadata.TARGET}/raw/{revision}/{member}",
                                    headers={"authorization": "Bearer " + token, "Accept-Encoding": "identity"}) as response:
                    data = response.read()
                storage._remaining(deadline)
                _require(attempts == 2, "two_read_operations_required")
                value["summary"] = (project_uncertainty_manifest if uncertainty else project_result)(data, context)
                storage._remaining(deadline)
                value["outcome"] = "read"
    except (Exception, KeyboardInterrupt):
        value.update(outcome="refused", summary=None)
    validate_envelope(value, context)
    return value


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ResultReadoutRefused("invalid_arguments")


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("operation", choices=("validate-request", "read", "verify-envelope"))
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--reviewed-source-tree", required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    logging.disable(logging.CRITICAL)
    try:
        arguments = vars(parser.parse_args(argv))
        operation = arguments.pop("operation")
        destination = _root(Path(os.environ.get("RUNNER_TEMP", ""))) / BASENAME
        with _held_parents(destination.parent, (destination.name,)) as held:
            with checked_request(**arguments) as context:
                if operation == "read":
                    _require(not os.path.lexists(destination), "readout_already_exists")
                    envelope = _read_result(context)
                elif operation == "verify-envelope":
                    _require(destination.lstat().st_size <= MAX_ENVELOPE_BYTES, "readout_envelope_bound")
                    validate_envelope(json.loads(_read_bytes(destination), object_pairs_hook=_object), context)
            held()  # Both final source and parent rereads precede publication.
            if operation == "read":
                _write_no_clobber(destination, _bytes(envelope))
                held()
                sys.stdout.write(_canonical_json(envelope) + "\n")
                return 0 if envelope["outcome"] == "read" else 2
        return 0
    except (Exception, KeyboardInterrupt):
        sys.stdout.write("result_readout_refused\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
