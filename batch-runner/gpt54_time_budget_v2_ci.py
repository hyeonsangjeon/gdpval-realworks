"""One directed Actions observation, with private, permanent cell admission.

This controller has no scheduler, recovery, grading or storage setup operation.
The independently digest-bound dispatch request is authority; local preparations,
remote receipts and host metadata are evidence, never independent permission.
Only storage/process transports are test seams. No serialized callback is loaded.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
import time
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from pathlib import Path

import codex_budget_pilot_output as storage
import codex_ci_input_intake as intake
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_v2_observation as observation
from codex_budget_pilot_retention import _control, _encoded, _object, _objects, _session
from core.agentic_v2_preregistration import seal
from core.hf_publication import _PublicationFile, _publication_additions
from core.reference_integrity import validate_reference_relative_path
from core.time_budget_observation_deadline import (
    CLEANUP_UNCONFIRMED, OWNERSHIP_REQUIRED, REFUSED, TIMEOUT,
    ObservationDeadlineRefused, ObservationIdentity,
)
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_disposable_checkout import _git, _repository
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_time_budget_grading_preparation import _result
from gpt54_v2_grading_input import _object as _json_object, _read_bytes, _same

HELPER = "batch-runner/gpt54_time_budget_v2_ci.py"
WORKFLOW = ".github/workflows/gpt54-time-budget-first-v2.yml"
REPOSITORY = "hyeonsangjeon/gdpval-realworks"
OWNER = "hyeonsangjeon"
JOB = "observation"
RUNTIME_BASENAME = "time-budget-v2-runtime"
FROZEN_BASENAME = "time-budget-v2-frozen"
REQUEST_VERSION = "gpt54-time-budget-first-v2-ci-request-v1"
ENVELOPE_VERSION = "gpt54-time-budget-first-v2-ci-completion-v1"
FAILURE_EVENT_VERSION = "gpt54-time-budget-first-v2-ci-failure-v1"
# Existing verified private target, not its closed pilot's admission authority.
TARGET = "HyeonSang/gdpval-codex-budget-pilot-ci-20260923"
TARGET_SHA256 = "a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44"
BRANCH = "main"
CELL = {"study_id": registration.STUDY_ID, "run_id": observation.RUN,
        "condition": "sandbox_v2", "repeat": 1, "task_id": observation.TASK}
PREFIX = "time-budget/" + registration.STUDY_ID + "/" + observation.RUN + "/" + observation.TASK
CLAIM = PREFIX + "/admission.json"
MANIFEST = PREFIX + "/output-manifest.json"
MAX_REQUEST_BYTES = 16384
MAX_INPUT_BYTES = 36 * 1024 * 1024
TOKEN_KEYS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
              "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL")
SOURCE_ROLES = {
    HELPER, WORKFLOW, observation.ENTRYPOINT, "batch-runner/codex_ci_input_intake.py",
    "batch-runner/codex_budget_pilot_output.py", "batch-runner/codex_budget_pilot_retention.py",
    "batch-runner/gpt54_time_budget_grading_preparation.py",
    "batch-runner/scripts/azure_oidc_identity_preflight.py", "batch-runner/requirements.txt",
}
FAILURE_STAGES = frozenset({
    "claim_admission", "execution_consumption", "direction_binding",
    "execution_reservation", "execution_source_reread", "observation_callable", "execution_receipt",
})
FAILURE_CATEGORIES = frozenset({
    "controller_refused", "observation_refused", "registration_refused", "deadline_refused",
    "interrupted", "io_error", "validation_refused", "type_error", "attribute_error", "key_error",
    "unexpected_error",
})
# Exact existing static codes only. Exception messages, paths and tracebacks
# are never serialized, even privately; an unknown reason stays unknown.
FAILURE_REASONS = frozenset({
    "execution_refused_or_uncertain", "acknowledged_same_host_claim_required", "execution_already_consumed",
    "direction_not_current", "direction_schema", "direction_size_bound", "direction_admission_window",
    "result_destination_exists", "backend_workspace_exists", "direction_observation_already_consumed",
    "returned_terminal_required", "observation_handoff_consumption_refused", "prepared_observation_binding",
    "source_bound_execution_direction_required", "observation_handoff_already_consumed",
    REFUSED, OWNERSHIP_REQUIRED, CLEANUP_UNCONFIRMED,
})


class FirstV2CIRefused(ValueError):
    """A nonsecret refusal; no raw transport/provider exceptions are published."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise FirstV2CIRefused(reason)


def _bytes(value) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _canonical_path(value: str) -> Path:
    _require(type(value) is str and Path(value).is_absolute()
             and str(Path(value)) == value and ".." not in Path(value).parts, "canonical_path_required")
    path = registration._handoff_path(value)
    _require(str(path) == value and str(path.resolve()) == value, "path_alias_refused")
    return path


def _write(path: Path, value) -> None:
    with _publication_parents(path.parent) as (check, _, descriptor):
        _write_no_clobber(path, _bytes(value), parent_fd=descriptor(path.parent))
        storage._fsync_directory(path.parent)
        check()


def _read(path: Path) -> dict:
    data = storage._bytes(path, limit=storage.MAX_MANIFEST_BYTES)
    value = json.loads(data, object_pairs_hook=_json_object)
    _require(type(value) is dict and data == _bytes(value), "canonical_private_record_required")
    return value


def _execution_failure(stage: str, error: BaseException) -> dict:
    category = "unexpected_error"
    for kind, name in (
        (FirstV2CIRefused, "controller_refused"),
        (observation.FirstV2ObservationRefused, "observation_refused"),
        (registration.TimeBudgetRegistrationRefused, "registration_refused"),
        (ObservationDeadlineRefused, "deadline_refused"),
        (KeyboardInterrupt, "interrupted"), (OSError, "io_error"),
        (ValueError, "validation_refused"), (TypeError, "type_error"),
        (AttributeError, "attribute_error"), (KeyError, "key_error"),
    ):
        if isinstance(error, kind):
            category = name
            break
    reason = "execution_refused_or_uncertain"
    if isinstance(error, (FirstV2CIRefused, observation.FirstV2ObservationRefused,
                          registration.TimeBudgetRegistrationRefused, ObservationDeadlineRefused)):
        if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in FAILURE_REASONS:
            reason = error.args[0]
    return {"outcome": "refused_or_uncertain", "returned": None,
            "failure": {"stage": stage, "category": category, "reason": reason}}


def _check_execution_failure(receipt: dict) -> None:
    _require(set(receipt) in ({"outcome", "returned"}, {"outcome", "returned", "failure"})
             and receipt["outcome"] == "refused_or_uncertain" and receipt["returned"] is None,
             "execution_receipt_schema")
    if "failure" in receipt:
        failure = receipt["failure"]
        _require(type(failure) is dict and set(failure) == {"stage", "category", "reason"}
                 and all(type(failure[key]) is str for key in failure)
                 and failure["stage"] in FAILURE_STAGES and failure["category"] in FAILURE_CATEGORIES
                 and failure["reason"] in FAILURE_REASONS, "execution_failure_schema")


def _emit_execution_failure(receipt: dict) -> None:
    """Emit only the validated current failure, never a receipt read from disk."""
    _check_execution_failure(receipt)
    if "failure" in receipt:
        sys.stderr.write(_canonical_json({"format": FAILURE_EVENT_VERSION, **receipt["failure"]}) + "\n")


@contextmanager
def checked_request(*, request_json: str, expected_request_sha256: str,
                    reviewed_source_sha: str, reviewed_source_tree: str,
                    runtime_root: Path, frozen_root: Path, state_root: Path,
                    admission: bool = True):
    """Validate authority and genuine R/F/input registrations before credentials."""
    data = request_json.encode("utf-8")
    _require(0 < len(data) <= MAX_REQUEST_BYTES and storage._hash(expected_request_sha256)
             and _identity(data)["sha256"] == expected_request_sha256, "independent_request_digest_required")
    request = json.loads(data, object_pairs_hook=_json_object)
    _require(type(request) is dict and set(request) == {
        "format", "purpose", "source", "frozen_source", "input_registration", "cell", "ci",
        "registration_sha256", "dataset_sha256", "paths", "storage", "not_before_unix", "expires_unix",
    }, "request_schema")
    _same("request format", request["format"], REQUEST_VERSION)
    _same("request purpose", request["purpose"], "execute_and_privately_retain_first_v2_observation")
    _same("request cell", request["cell"], CELL)
    _require(storage._hash(reviewed_source_sha, 40) and storage._hash(reviewed_source_tree, 40),
             "independent_reviewed_commit_and_tree_required")
    _same("request source", request["source"], {"sha": reviewed_source_sha, "tree": reviewed_source_tree})
    _same("frozen source", request["frozen_source"], {
        "sha": registration.ACCEPTED_BASE_SHA, "tree": registration.ACCEPTED_BASE_TREE})
    _same("input registration", request["input_registration"], {
        "source_sha": registration.ACCEPTED_BASE_SHA, "source_tree": registration.ACCEPTED_BASE_TREE,
        "path": registration.SOURCE_PROFILE, "sha256": registration.SOURCE_PROFILE_SHA256})
    begin, end = request["not_before_unix"], request["expires_unix"]
    _require(type(begin) is int and type(end) is int and 0 <= begin < end
             and end - begin <= 2700, "finite_admission_window_required")
    if admission:
        _require(begin <= time.time() < end, "request_not_current")
    ci = request["ci"]
    _require(type(ci) is dict and type(ci.get("run_number")) is int and ci["run_number"] > 0,
             "independent_dispatch_number_required")
    _same("intended Actions context", ci, {
        "repository": REPOSITORY, "workflow": WORKFLOW, "ref": "refs/heads/main",
        "actor": OWNER, "job": JOB, "attempt": 1, "run_number": ci["run_number"],
        "runner": "ubuntu-22.04", "runner_os": "Linux", "runner_arch": "X64",
    })
    required = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": OWNER, "GITHUB_TRIGGERING_ACTOR": OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_NUMBER": str(ci["run_number"]), "GITHUB_JOB": JOB,
        "GITHUB_SHA": reviewed_source_sha, "TIME_BUDGET_WORKFLOW_SHA": reviewed_source_sha,
        "GITHUB_WORKFLOW_REF": REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_ENVIRONMENT": "github-hosted", "ImageOS": "ubuntu22",
    }
    _require(all(os.environ.get(key) == value for key, value in required.items()), "ci_source_cell_or_attempt_refused")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    _require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None
             and sys.version_info[:3] == (3, 10, 12), "ci_runtime_identity_required")
    roots = {"runtime_root": _canonical_path(str(runtime_root)), "frozen_root": _canonical_path(str(frozen_root)),
             "state_root": _canonical_path(str(state_root))}
    _same("request canonical paths", request["paths"], {name: str(path) for name, path in roots.items()})
    bootstrap = _canonical_path(os.environ.get("GITHUB_WORKSPACE", ""))
    runner_temp = _canonical_path(os.environ.get("RUNNER_TEMP", ""))
    common = bootstrap / ".git"
    _require(roots["runtime_root"] == runner_temp / RUNTIME_BASENAME
             and roots["frozen_root"] == runner_temp / FROZEN_BASENAME
             and roots["state_root"].parent == runner_temp,
             "ci_canonical_roots_required")
    source_paths = [bootstrap, *roots.values()]
    _require(all(not a.is_relative_to(b) and not b.is_relative_to(a)
                 for index, a in enumerate(source_paths) for b in source_paths[index + 1:]),
             "source_state_overlap")

    def check_bootstrap() -> None:
        _require(os.environ.get("GITHUB_WORKSPACE") == str(bootstrap)
                 and os.environ.get("RUNNER_TEMP") == str(runner_temp), "actions_bootstrap_path_changed")
        _require(common.is_dir() and _repository(bootstrap) == (bootstrap, common),
                 "ordinary_actions_bootstrap_required")
        for revision, expected in (("HEAD^{commit}", reviewed_source_sha), ("HEAD^{tree}", reviewed_source_tree)):
            _require(_git(bootstrap, "rev-parse", "--verify", "--end-of-options", revision).stdout
                     == (expected + "\n").encode("ascii"), "actions_bootstrap_commit_or_tree_changed")
        _require(all(_repository(roots[name])[1] == common for name in ("runtime_root", "frozen_root")),
                 "actions_linked_common_git_required")

    target = request["storage"]
    _require(type(target) is dict and storage._hash(target.get("expected_parent"), 40),
             "independent_private_parent_required")
    _same("private study storage", target, {"repository_name_sha256": TARGET_SHA256, "branch": BRANCH,
          "prefix": PREFIX, "expected_parent": target["expected_parent"]})
    _require(_identity(TARGET.encode())["sha256"] == TARGET_SHA256, "fixed_private_target_identity")
    with ExitStack() as sources:
        check_bootstrap_parents = sources.enter_context(_held_parents(bootstrap, (".git/HEAD",)))
        check_bootstrap()
        check_parent = sources.enter_context(_held_parents(roots["state_root"].parent, (roots["state_root"].name,)))
        check_state = (sources.enter_context(_held_parents(roots["state_root"], ("request.json",)))
                       if roots["state_root"].exists() else None)
        _, tree, identities = sources.enter_context(registration._reviewed_source(
            roots["runtime_root"], reviewed_source_sha, SOURCE_ROLES))
        _same("reviewed runtime tree", tree, reviewed_source_tree)
        # Actual loaded controller/dependencies must be the reviewed R bytes.
        for name, module in ((HELPER, sys.modules[__name__]), (observation.ENTRYPOINT, observation),
                             ("batch-runner/codex_ci_input_intake.py", intake),
                             ("batch-runner/codex_budget_pilot_output.py", storage)):
            _read_bytes(Path(module.__file__), **identities[name])
        plan = registration.load_registration(roots["runtime_root"] / registration.REGISTRATION_PATH)
        anchors = (roots["runtime_root"], reviewed_source_sha, roots["frozen_root"], registration.ACCEPTED_BASE_SHA)
        compiled = registration._compile_registration(plan, anchors, True, sources)
        _same("request registration", request["registration_sha256"], compiled.manifest_sha256)
        _same("request dataset facts", request["dataset_sha256"], seal(plan["shared"]["dataset"]))
        sources.enter_context(registration._observation_input_registration(
            roots["frozen_root"], registration.ACCEPTED_BASE_SHA, registration.SOURCE_PROFILE,
            plan["shared"]["dataset"]))
        host = observation.execution_host_identity(reviewed_source_sha)
        context = {"request": request, "request_identity": _identity(data), "plan": plan, "roots": roots,
                   "host": host, "ci": {"run_id": run_id, "run_number": ci["run_number"], "job": JOB, "attempt": 1}}
        check_bootstrap_parents()
        check_bootstrap()
        yield context
        check_bootstrap_parents()
        check_bootstrap()
        _same("final live host", observation.execution_host_identity(reviewed_source_sha), host)
        check_parent()
        if check_state is not None:
            check_state()


def _paths(context: dict) -> dict[str, Path]:
    root = context["roots"]["state_root"]
    return {"root": root, "parquet": root / "inputs/original.parquet", "references": root / "inputs/reference-only",
            "preparation": root / "preparation", "observation": root / "observation",
            "direction": root / "direction.json", "destination": root / "result"}


def _common(context: dict) -> dict:
    roots, paths = context["roots"], _paths(context)
    return {"runtime_root": roots["runtime_root"], "expected_reviewed_source_sha": context["request"]["source"]["sha"],
            "frozen_grader_root": roots["frozen_root"], "expected_grader_source_sha": registration.ACCEPTED_BASE_SHA,
            "input_registration_root": roots["frozen_root"], "expected_input_source_sha": registration.ACCEPTED_BASE_SHA,
            "input_registration_path": registration.SOURCE_PROFILE, "dataset_parquet": paths["parquet"],
            "reference_root": paths["references"]}


def _reconstruct(context: dict, sources: ExitStack):
    return registration._observation_handoff_data(
        context["plan"], sources=sources, run_id=observation.RUN, task_id=observation.TASK,
        destination=_paths(context)["preparation"], step0_manifest=None, **_common(context))


def _direction(context: dict, marker: dict) -> tuple[dict, dict]:
    paths, common = _paths(context), _common(context)
    expected = _identity(_bytes(marker))
    binding = registration.ObservationExecutionBinding(
        expected["sha256"], expected["size"], _canonical_json(marker["observation"]),
        registration.ACCEPTED_BASE_SHA, registration.ACCEPTED_BASE_TREE, registration.FROZEN_TEMPLATE_SHA256,
        str(paths["preparation"]), str(paths["observation"]))
    bound_paths = {"direction": str(paths["direction"]), "preparation": str(paths["preparation"]),
        **{name: str(common[name]) for name in ("runtime_root", "frozen_grader_root", "input_registration_root",
                                               "dataset_parquet", "reference_root")},
        "observation_directory": str(paths["observation"]), "destination": str(paths["destination"]),
        "input_source_sha": common["expected_input_source_sha"], "input_registration_path": registration.SOURCE_PROFILE,
        "backend_workspace": str(paths["destination"].with_name(paths["destination"].name + observation.WORK_SUFFIX))}
    direction = {"direction_version": observation.DIRECTION_VERSION, "purpose": "execute_one_registered_observation",
        "execution_binding": asdict(binding), "paths": bound_paths, "host_sha256": context["host"]["instance_sha256"],
        "not_before_unix": context["request"]["not_before_unix"], "expires_unix": context["request"]["expires_unix"]}
    return direction, expected


def _claim(context: dict, marker: dict) -> dict:
    direction, expected = _direction(context, marker)
    return {"format": "gpt54-time-budget-first-v2-admission-v1", "observation": marker["observation"],
            "source": context["request"]["source"], "request_identity": context["request_identity"],
            "preparation_identity": expected, "input_binding_sha256": seal(marker["inputs"]),
            "host": context["host"], "ci": context["ci"], "direction_identity": _identity(_bytes(direction)),
            "paths": direction["paths"], "expected_parent": context["request"]["storage"]["expected_parent"],
            "storage": {"repository_name_sha256": TARGET_SHA256, "branch": BRANCH, "prefix": PREFIX},
            "state": "permanently_consumed_not_completion"}


def _commit(api, token, deadline, *, parent: str, files: dict[str, bytes], control_path: str,
            control: dict, cache: Path) -> str:
    """One add-only study CAS and immutable byte/object readback. Never retry."""
    _require(files.get(control_path) == _encoded(control)
             and all(name.startswith(PREFIX + "/") for name in files), "private_namespace_required")
    staged = [_PublicationFile(name, io.BytesIO(data), len(data), _identity(data)["sha256"])
              for name, data in sorted(files.items())]
    try:
        operations = _publication_additions(tuple(staged))
        storage._remaining(deadline)
        response = api.create_commit(repo_id=TARGET, repo_type="dataset", revision=BRANCH, token=token,
            parent_commit=parent, operations=operations, commit_message="Record first time-budget V2 observation boundary",
            num_threads=1, run_as_future=False, create_pr=False)
        revision = getattr(response, "oid", None)
        _require(storage._hash(revision, 40) and revision != parent
                 and not any(getattr(item, "_should_ignore", False) for item in operations), "commit_identity_unavailable")
        _same("private returned revision", storage._metadata(api, TARGET, revision, token, deadline)["sha"], revision)
        _objects(api, TARGET, revision, [_object(name, data) for name, data in sorted(files.items())],
                 token, deadline, written_at=revision)
        found, _ = _control(api, TARGET, revision, control_path, cache, token, deadline,
                            expected=_identity(_encoded(control)), written_at=revision)
        _same("immutable private control", found, control)
        return revision
    finally:
        for item in staged:
            item.stream.close()


def prepare_and_claim(context: dict) -> dict:
    """Credentialed V2-only original intake, genuine handoff, durable admission."""
    paths, root = _paths(context), _paths(context)["root"]
    _require(not os.path.lexists(root), "partial_or_consumed_state_refused")
    dataset = context["plan"]["shared"]["dataset"]
    versions = dict(dataset["input_file_versions"])
    _same("dataset byte registration", versions.pop(dataset["repo_id"] + "@" + dataset["revision"]),
          dataset["parquet_sha256"])
    _require(len(versions) == 2, "two_registered_references_required")
    for name in versions:
        validate_reference_relative_path(name)
        _require(name.startswith("reference_files/"), "registered_reference_role_required")
    with _held_parents(root.parent, (root.name,)), _publication_parents(root.parent) as publication:
        check, mkdir, descriptor = publication
        mkdir(root)
        _write(root / "request.json", context["request"])
        mkdir(root / "inputs")
        mkdir(paths["references"])
        specs = [(paths["parquet"], "data/train-00000-of-00001.parquet", dataset["parquet_sha256"], intake.HFRole.PARQUET)]
        for (name, digest), role in zip(sorted(versions.items()), (intake.HFRole.REFERENCE_1, intake.HFRole.REFERENCE_2), strict=True):
            path = _path(paths["references"], name)
            for parent in reversed(path.parents):
                if parent.is_relative_to(paths["references"]) and not parent.exists():
                    mkdir(parent)
            specs.append((path, name, digest, role))
        token = os.environ.get("HF_TOKEN", "")
        _require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
                 "existing_hf_token_required")
        # No legacy credentialed registration bypass and no Codex Step0 call.
        with storage._time_bound() as deadline, intake._hf_environment(online=True):
            remaining = MAX_INPUT_BYTES
            for target, member, digest, role in specs:
                data = intake._hf_read(dataset["repo_id"], dataset["revision"], member,
                    role=role, token=token, limit=min(16 * 1024 * 1024, remaining), deadline=deadline)
                _same("original byte identity", _identity(data)["sha256"], digest)
                _require(0 < len(data) <= remaining, "original_input_size_bound")
                check()
                _write_no_clobber(target, data, parent_fd=descriptor(target.parent))
                remaining -= len(data)
        token = None
        marker = registration.prepare_observation_handoff(context["plan"], **_common(context),
            run_id=observation.RUN, task_id=observation.TASK, destination=paths["preparation"])
        with ExitStack() as sources:
            rebuilt, _, reread = _reconstruct(context, sources)
            _same("independently reconstructed preparation", marker, rebuilt)
            direction, expected = _direction(context, rebuilt)
            _read_bytes(paths["preparation"] / registration.HANDOFF_READY, **expected)
            mkdir(paths["observation"])
            _write(paths["direction"], direction)
            claim = _claim(context, rebuilt)
            _write(root / "claim-reserved.json", claim)
            reread()
        receipt = {"outcome": "unresolved", "claim": claim, "claim_identity": _identity(_encoded(claim)),
                   "returned_commit": None}
        cache = root / "claim-readback"
        mkdir(cache)
        try:
            with _session(None) as (api, token, deadline):
                parent = context["request"]["storage"]["expected_parent"]
                _same("independent private parent", storage._metadata(api, TARGET, BRANCH, token, deadline)["sha"], parent)
                _require(api.get_paths_info(repo_id=TARGET, repo_type="dataset", revision=parent,
                         paths=[PREFIX], token=token) == [], "observation_already_claimed_or_retained")
                receipt["returned_commit"] = _commit(api, token, deadline, parent=parent,
                    files={CLAIM: _encoded(claim)}, control_path=CLAIM, control=claim, cache=cache)
                receipt["outcome"] = "acknowledged"
        except (Exception, KeyboardInterrupt):
            # No server-state adoption after a lost response, and no second CAS.
            _write(root / "claim-receipt.json", receipt)
            raise FirstV2CIRefused("claim_unconfirmed_permanently_reserved") from None
        _write(root / "claim-receipt.json", receipt)
        check()
        return receipt


def _admission(context: dict, sources: ExitStack) -> tuple[dict, dict]:
    paths = _paths(context)
    _same("retained request", _read(paths["root"] / "request.json"), context["request"])
    marker, _, _ = _reconstruct(context, sources)
    claim = _claim(context, marker)
    _same("same-host permanent claim", _read(paths["root"] / "claim-reserved.json"), claim)
    receipt = _read(paths["root"] / "claim-receipt.json")
    _require(type(receipt) is dict and set(receipt) == {"outcome", "claim", "claim_identity", "returned_commit"}
             and receipt["outcome"] == "acknowledged" and storage._hash(receipt["returned_commit"], 40)
             and receipt["returned_commit"] != claim["expected_parent"], "acknowledged_same_host_claim_required")
    _same("acknowledged claim bytes", receipt["claim"], claim)
    _same("acknowledged claim identity", receipt["claim_identity"], _identity(_encoded(claim)))
    direction, expected = _direction(context, marker)
    _read_bytes(paths["direction"], **_identity(_bytes(direction)))
    _read_bytes(paths["preparation"] / registration.HANDOFF_READY, **expected)
    return marker, receipt


def execute(context: dict) -> dict:
    """Pass the reconstructed direction to the real callable without storage tokens."""
    paths = _paths(context)
    reserved = False
    stage = "claim_admission"
    try:
        with ExitStack() as sources:
            marker, receipt = _admission(context, sources)
            stage = "execution_consumption"
            _require(not any(os.path.lexists(paths["root"] / name) for name in
                             ("execution-reserved.json", "execution-receipt.json")), "execution_already_consumed")
            stage = "direction_binding"
            direction, expected = _direction(context, marker)
            # Reserve once before admission/provider effects, including unsupported hosts.
            stage = "execution_reservation"
            _write(paths["root"] / "execution-reserved.json", {"claim_commit": receipt["returned_commit"],
                   "observation": marker["observation"], "outcome": "uncertain_until_returned"})
            reserved = True
            stage = "execution_source_reread"
        for key in TOKEN_KEYS:
            os.environ.pop(key, None)
        os.environ["HF_HUB_OFFLINE"] = os.environ["HF_DATASETS_OFFLINE"] = "1"
        stage = "observation_callable"
        returned = observation.run_first_v2_observation(
            context["plan"], **_common(context), observation=ObservationIdentity(**marker["observation"]),
            direction_path=paths["direction"], expected_direction_sha256=_identity(_bytes(direction))["sha256"],
            expected_host_sha256=context["host"]["instance_sha256"], preparation_directory=paths["preparation"],
            expected_preparation_identity=expected, observation_directory=paths["observation"], destination=paths["destination"])
        result = {"outcome": "returned", "returned": returned}
        stage = "execution_receipt"
        _write(paths["root"] / "execution-receipt.json", result)
    except (Exception, KeyboardInterrupt) as error:
        # Refusal/abrupt control loss cannot be manufactured into an admitted row.
        # Never annotate/adopt a previous partial attempt or overwrite its receipt.
        if reserved and stage != "execution_receipt":
            try:
                failure = _execution_failure(stage, error)
                _write(paths["root"] / "execution-receipt.json", failure)
                # One non-authoritative event after this invocation's receipt write.
                _emit_execution_failure(failure)
            except (Exception, KeyboardInterrupt):
                pass  # Receipt/event I/O uncertainty is not a retry or cleanup extension.
        if stage not in {"observation_callable", "execution_receipt"}:
            raise
        raise FirstV2CIRefused("execution_refused_or_uncertain") from None
    return result


def _result_snapshot(context: dict, marker: dict):
    paths = _paths(context)
    receipt_path = paths["root"] / "execution-receipt.json"
    receipt = _read(receipt_path) if receipt_path.exists() else None
    if receipt is None:
        return None, {}, None, None
    if receipt.get("outcome") == "refused_or_uncertain":
        _check_execution_failure(receipt)
        return None, {}, receipt, None
    _require(set(receipt) == {"outcome", "returned"} and receipt["outcome"] == "returned", "execution_receipt_schema")
    returned = receipt["returned"]
    _same("returned observation", returned["observation"], marker["observation"])
    result_path = paths["destination"] / observation.RESULT
    _same("returned canonical path", returned["result_path"], str(result_path))
    snapshot = _result(result_path, returned["result_identity"], ObservationIdentity(**marker["observation"]),
                       context["plan"], paths["destination"] / "upload")
    data, payload, files, fingerprint = snapshot
    _require(data == _bytes(payload), "canonical_first_v2_result_bytes_required")
    _same("returned result fingerprint", fingerprint, returned["result_fingerprint"])
    _same("returned result status", payload["results"][0]["status"], returned["status"])
    execution = payload["observation_execution"]
    direction, expected = _direction(context, marker)
    for key, value in {"preparation_identity": expected, "inputs": marker["inputs"],
                       "runtime_source": marker["runtime_source"], "host": context["host"],
                       "direction_sha256": _identity(_bytes(direction))["sha256"]}.items():
        _same("captured " + key, execution[key], value)
    _require(len(files) <= 120 and sum(map(len, files.values())) <= storage.MAX_TOTAL_BYTES,
             "private_output_size_bound")
    return snapshot, {"result/" + observation.RESULT: data, **{"result/upload/" + name: value for name, value in files.items()}}, receipt, payload


def _envelope(context: dict, claim: dict, payload: dict | None, *, commit: str | None, outcome: str) -> dict:
    control = None if payload is None else payload["time_budget_observation"]
    row = None if payload is None else payload["results"][0]
    usage = None if row is None else row.get("usage")
    if not (type(usage) is dict and set(usage) == {"input_tokens", "output_tokens"}
            and all(type(value) is int and value >= 0 for value in usage.values())):
        usage = None
    return {"format": ENVELOPE_VERSION, **CELL, "source": context["request"]["source"], "ci": context["ci"],
        "request_sha256": context["request_identity"]["sha256"], "host_sha256": context["host"]["instance_sha256"],
        "claim_commit": claim["returned_commit"], "output_commit": commit, "retention": outcome,
        "result_identity": None if payload is None else _identity(_bytes(payload)),
        "result_fingerprint": None if payload is None else payload["result_fingerprint"],
        "status": "uncertain" if row is None else row["status"], "usage": usage,
        "terminal_reason": None if control is None else control["terminal_reason"],
        "cleanup_complete": None if control is None else control["cleanup_complete"],
        "host_reusable": None if control is None else control["host_reusable"],
        "grading_performed": False, "retry_allowed": False, "other_cells_executed": 0}


def validate_envelope(value: dict) -> None:
    """Exact metadata allowlist: never upload a raw receipt, exception or body."""
    fixed = {"format": ENVELOPE_VERSION, **CELL, "grading_performed": False, "retry_allowed": False,
             "other_cells_executed": 0}
    _same("completion constants", {name: value[name] for name in fixed}, fixed)
    _require(set(value) == {*fixed, "source", "ci", "request_sha256", "host_sha256", "claim_commit",
        "output_commit", "retention", "result_identity", "result_fingerprint", "status", "usage",
        "terminal_reason", "cleanup_complete", "host_reusable"}, "completion_schema")
    _require(set(value["source"]) == {"sha", "tree"}
             and all(storage._hash(item, 40) for item in value["source"].values()), "completion_source")
    ci = value["ci"]
    _require(set(ci) == {"run_id", "run_number", "job", "attempt"} and ci["job"] == JOB
             and type(ci["attempt"]) is int and ci["attempt"] == 1
             and type(ci["run_number"]) is int and ci["run_number"] > 0
             and type(ci["run_id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", ci["run_id"]) is not None,
             "completion_ci")
    _require(all(storage._hash(value[key]) for key in ("request_sha256", "host_sha256"))
             and storage._hash(value["claim_commit"], 40)
             and (value["output_commit"] is None or storage._hash(value["output_commit"], 40)), "completion_hashes")
    _require(value["retention"] in {"acknowledged", "unresolved"}
             and (value["retention"] == "acknowledged") == (value["output_commit"] is not None)
             and value["status"] in {"success", "error", "uncertain"}
             and value["terminal_reason"] in {None, "completed", "failed", "cancelled", "abandoned", TIMEOUT}
             and all(value[key] is None or type(value[key]) is bool for key in ("cleanup_complete", "host_reusable")),
             "completion_outcome")
    identity = value["result_identity"]
    _require(identity is None or type(identity) is dict and set(identity) == {"sha256", "size"}
             and storage._hash(identity["sha256"]) and type(identity["size"]) is int
             and 0 < identity["size"] <= storage.MAX_RECORD_BYTES, "completion_result_identity")
    fingerprint = value["result_fingerprint"]
    _require(fingerprint is None or storage._hash(fingerprint), "completion_result_fingerprint")
    usage = value["usage"]
    _require(usage is None or type(usage) is dict and set(usage) == {"input_tokens", "output_tokens"}
             and all(type(item) is int and item >= 0 for item in usage.values()), "completion_usage")
    if value["status"] == "uncertain":
        _require(all(value[key] is None for key in ("result_identity", "result_fingerprint", "terminal_reason",
                                                   "cleanup_complete", "host_reusable", "usage")), "uncertainty_is_not_a_study_row")
    else:
        _require(identity is not None and fingerprint is not None and value["terminal_reason"] is not None,
                 "terminal_result_identity_required")
    if value["status"] == "success":
        _require(value["terminal_reason"] == "completed" and value["cleanup_complete"] is True
                 and value["host_reusable"] is True, "completion_success_requires_cleanup")


def retain(context: dict) -> dict:
    """Add only this observation's real output or an explicit uncertainty record."""
    paths = _paths(context)
    with ExitStack() as sources:
        marker, admission = _admission(context, sources)
        snapshot, files, execution_receipt, payload = _result_snapshot(context, marker)
        _write(paths["root"] / "retention-reserved.json", {"claim_commit": admission["returned_commit"],
               "outcome": "unresolved", "files": {name: _identity(data) for name, data in sorted(files.items())}})
        manifest = {"format": "gpt54-time-budget-first-v2-private-output-v1", "observation": marker["observation"],
            "request_identity": context["request_identity"], "claim_commit": admission["returned_commit"],
            "claim_identity": admission["claim_identity"], "execution_receipt": execution_receipt,
            "result": "unavailable_no_fabricated_study_row" if payload is None else "canonical_step2",
            "files": {name: _identity(data) for name, data in sorted(files.items())}, "grading_performed": False}
        if snapshot is not None:
            # All four components, including actual result/deliverable bytes.
            _require(_result_snapshot(context, marker)[0] == snapshot, "result_changed_before_publication")
        else:
            _same("final uncertainty receipt", _result_snapshot(context, marker)[2], execution_receipt)
    cache = paths["root"] / "retention-readback"
    cache.mkdir(mode=0o700)
    outcome, revision = "unresolved", None
    try:
        with _session(None) as (api, token, deadline):
            parent = admission["returned_commit"]
            _same("retention parent", storage._metadata(api, TARGET, BRANCH, token, deadline)["sha"], parent)
            _objects(api, TARGET, parent, [_object(CLAIM, _encoded(admission["claim"]))], token, deadline, written_at=parent)
            _require(api.get_paths_info(repo_id=TARGET, repo_type="dataset", revision=parent,
                     paths=[MANIFEST, PREFIX + "/result"], token=token) == [], "output_already_retained")
            revision = _commit(api, token, deadline, parent=parent,
                files={MANIFEST: _encoded(manifest), **{PREFIX + "/" + name: data for name, data in files.items()}},
                control_path=MANIFEST, control=manifest, cache=cache)
            _objects(api, TARGET, revision, [_object(CLAIM, _encoded(admission["claim"]))], token, deadline, written_at=parent)
            outcome = "acknowledged"
    except (Exception, KeyboardInterrupt):
        revision = None  # Lost response is uncertainty, never retry/adoption.
    envelope = _envelope(context, admission, payload, commit=revision, outcome=outcome)
    validate_envelope(envelope)
    _write(paths["root"] / "completion.json", envelope)
    _require(outcome == "acknowledged", "private_retention_unconfirmed")
    return envelope


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise FirstV2CIRefused("invalid_arguments")


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("operation", choices=("validate-request", "prepare-and-claim", "execute", "retain", "verify-envelope"))
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--reviewed-source-tree", required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    for name in ("runtime-root", "frozen-root", "state-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        kwargs = vars(args).copy()
        operation = kwargs.pop("operation")
        # Never print request bytes, private paths, exceptions or provider logs.
        logging.disable(logging.CRITICAL)
        os.umask(0o077)
        with checked_request(request_json=os.environ.get("TIME_BUDGET_REQUEST_JSON", ""),
                             admission=operation not in ("retain", "verify-envelope"), **kwargs) as context:
            if operation == "verify-envelope":
                envelope = _read(_paths(context)["root"] / "completion.json")
                validate_envelope(envelope)
                for name, expected in {"source": context["request"]["source"], "ci": context["ci"],
                                       "request_sha256": context["request_identity"]["sha256"],
                                       "host_sha256": context["host"]["instance_sha256"]}.items():
                    _same("completion " + name, envelope[name], expected)
            elif operation != "validate-request":
                result = {"prepare-and-claim": prepare_and_claim, "execute": execute, "retain": retain}[operation](context)
                if operation == "execute" and result["returned"]["status"] != "success":
                    return 1
        sys.stdout.write(_canonical_json({"operation": operation, "outcome": "completed"}) + "\n")
        return 0
    except (Exception, KeyboardInterrupt):
        sys.stdout.write('{"outcome":"refused_or_uncertain"}\n')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
