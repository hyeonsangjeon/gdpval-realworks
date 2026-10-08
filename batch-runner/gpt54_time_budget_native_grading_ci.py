"""A directed retained native r1 Task3 grade, or a separate preparation probe.

The authenticated native context stays open in this process. A permanent remote
claim supplements (never replaces) the accepted executor's local once-store.
There is no resume, claim adoption, observation execution or next-cell operation.
The opt-in probe closes the authenticated context without grading authority.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import io
import json
import logging
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time

import gpt54_time_budget_grading_execution as execution
from codex_budget_pilot_retention import _control, _encoded, _object, _objects, _session
from core.agentic_v2_preregistration import seal
from core.azure_ai_clients import AzureAIRouteSettings, grader_route_workloads, preflight_routes
from core.hf_publication import _PublicationFile, _publication_additions
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_disposable_checkout import _git, _registered_gitdir, _repository
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object as _json_object, _read_bytes, _same

bridge, preparation = execution.native_intake, execution.preparation
native, registration, storage, intake = bridge.native, execution.registration, bridge.storage, bridge.intake
shared = native.shared
HELPER = "batch-runner/gpt54_time_budget_native_grading_ci.py"
WORKFLOW = ".github/workflows/gpt54-time-budget-native-task3-grade.yml"
JOB = "grade"
REQUEST_FORMAT = "gpt54-time-budget-native-task3-grade-request-v1"
PURPOSE = "grade_retained_native_r1_task3_once"
FORMAT = "gpt54-time-budget-native-task3-grade-completion-v1"
PROBE_REQUEST_FORMAT = "gpt54-time-budget-native-task3-preparation-request-v1"
PROBE_PURPOSE = "prepare_retained_native_r1_task3_without_grading"
PROBE_FORMAT = "gpt54-time-budget-native-task3-preparation-completion-v1"
PROBE_SECONDS = 300
PROBE_POLICY = {"permission": "model_free_preparation_only", "preparation_seconds": PROBE_SECONDS,
                "grading_allowed": False, "private_writes_allowed": False, "handle_reuse_allowed": False,
                "retry_allowed": False}
PROBE_STAGES = ("environment", "originals", "intake_preparation", "context_exit")
CELL = dict(bridge.CELL)
GRADING_IMAGE = "ghcr.io/hyeonsangjeon/gdpval-grading@sha256:0f6782c056e31e1ea1d693fc2f8f873da160b232926fa1b6cde75c24e5344a04"
ROOT_NAMES = {"controller_root": "time-budget-task3-grade-controller", "runtime_root": "time-budget-task3-grade-runtime",
              "frozen_root": "time-budget-task3-grade-frozen", "state_root": "time-budget-task3-grade",
              "login_root": "time-budget-task3-grade-azure-login"}
# Independently verified generation anchors, not a mutable latest-result lookup.
RETAINED = {
    "source": {"sha": "33e24e9c1402ec0b7c92a71222998d1407646a92", "tree": "6e67da4e12169b41a837d92eaf946db15e71010e"},
    "ci": {"run_id": "37631184801", "run_number": 5, "attempt": 1, "job": "observation"},
    "claim_commit": "08e485281f25ea06311305e7a4add721a68ba9ea",
    "output_commit": "d5aeecec1394fb44d4b1da33b1be38a39acdb89a",
    "result_identity": {"size": 8518, "sha256": "4ae3ea3d0dbe6ee540b86e3db17085e3a4d6f73afaf035c7f6f659f99b4601a4"},
    "result_fingerprint": "4a62be1df3e21eae52bd7814359887c5f774200948ba67fc15ca62bf2f4b2967",
    "request_sha256": "3d2bbe5f55f0f0558f8e38bf53ebaa22f722b60b55b2338df465196b278ffc98",
}
POLICY = {"permission": "one_frozen_F_grading_attempt", "external_attempts": 1,
          "step8_seconds": execution.STEP8_SECONDS, "child_seconds": execution.CHILD_SECONDS,
          "job_minutes": 270, "preclaim_seconds": 300, "retention_seconds": storage.PUBLICATION_SECONDS,
          "retry_allowed": False, "resume_allowed": False, "regrade_for_score": False}
PRECLAIM_SECONDS = 300
SOURCE_ROLES = bridge.SOURCE_ROLES | {HELPER, WORKFLOW, execution.HELPER, "batch-runner/codex_budget_pilot.py",
    "batch-runner/scripts/azure_oidc_identity_preflight.py", "batch-runner/scripts/preflight_grading_renderer.py"}
DIAGNOSTIC_STAGES = ("environment", "originals", "intake_preparation", "direction", "claim", "executor",
                     "retention", "context_exit")
DIAGNOSTIC_STATES = frozenset({"unknown", "started", "completed"})
# Closed, type-only categories reused from the observation controller.
# No exception message, args, type name, traceback or provider body is public.
FAILURE_CATEGORIES = frozenset({"controller_refused", "interrupted", "io_error", "validation_refused",
                               "type_error", "attribute_error", "key_error", "unexpected_error"})
_write, _read, _canonical_path = shared._write, shared._read, shared._canonical_path


class NativeGradingCIRefused(ValueError):
    """Static refusal only; all claim/reservation/partial state is nonrenewable."""


def _require(condition, reason):
    if not condition:
        raise NativeGradingCIRefused(reason)


def _diagnostics():
    return {stage: {"state": "unknown", "category": None} for stage in DIAGNOSTIC_STAGES}


def _failure(diagnostics, stage, error):
    """Keep the first safe category at this boundary, never private error text."""
    if diagnostics is None or diagnostics[stage]["category"] is not None:
        return
    category = "unexpected_error"
    for kind, name in ((NativeGradingCIRefused, "controller_refused"), (KeyboardInterrupt, "interrupted"),
                       (OSError, "io_error"), (ValueError, "validation_refused"), (TypeError, "type_error"),
                       (AttributeError, "attribute_error"), (KeyError, "key_error")):
        if isinstance(error, kind):
            category = name
            break
    diagnostics[stage]["category"] = category


def _namespace() -> tuple[str, str, str]:
    # C, Actions run and destination are deliberately absent from this key.
    prefix = "time-budget-grading/" + CELL["study_id"] + "/" + CELL["run_id"] + "/" + CELL["task_id"]
    prefix += "/" + registration.ACCEPTED_BASE_SHA
    return prefix, prefix + "/admission.json", prefix + "/output-manifest.json"


def _paths() -> dict[str, Path]:
    temporary = _canonical_path(os.environ.get("RUNNER_TEMP", ""))
    paths = {name: temporary / basename for name, basename in ROOT_NAMES.items()}
    root = paths["state_root"]
    paths.update(bootstrap_root=_canonical_path(os.environ.get("GITHUB_WORKSPACE", "")),
        input_registration_root=paths["frozen_root"], dataset_parquet=root / "originals" / native.originals.PARQUET,
        reference_root=root / "originals" / native.originals.REFERENCES,
        step0_manifest=root / "originals" / native.originals.STEP0,
        hydration_root=root / "hydration", preparation_root=root / "preparation",
        execution_input_directory=root / "grading-input", attempt_store=root / "attempt-store",
        destination=root / "grade", direction_file=root / "direction.json")
    return paths


def _public_request(request_json, expected_request_sha256, controller_sha, controller_tree, *, admission=True,
                    preparation_only=False):
    """The same exact public gates run again in the credentialed process."""
    data = request_json.encode("utf-8")
    _require(0 < len(data) <= shared.MAX_REQUEST_BYTES and storage._hash(expected_request_sha256)
             and _identity(data)["sha256"] == expected_request_sha256, "independent_request_digest_required")
    request = json.loads(data, object_pairs_hook=_json_object)
    bridge.reader._keys(request, {"format", "purpose", "controller", "completion", "cell", "ci", "frozen_source",
        "input_registration", "registration_sha256", "dataset_sha256", "step0", "deliverables", "paths",
        "policy", "not_before_unix", "expires_unix"} | (set() if preparation_only else {"storage"}))
    _same("request format and purpose", [request["format"], request["purpose"]],
          [PROBE_REQUEST_FORMAT, PROBE_PURPOSE] if preparation_only else [REQUEST_FORMAT, PURPOSE])
    _require(storage._hash(controller_sha, 40) and storage._hash(controller_tree, 40), "independent_controller_required")
    _same("controller", request["controller"], {"sha": controller_sha, "tree": controller_tree})
    _same("fixed native Task3", request["cell"], CELL)
    native.validate_envelope(request["completion"], expected_cell=CELL)
    _require(request["completion"]["status"] == "success" and request["completion"]["retention"] == "acknowledged",
             "retained_native_success_required")
    _same("original retained generation", {key: request["completion"][key] for key in RETAINED}, RETAINED)
    _same("frozen source", request["frozen_source"], {"sha": registration.ACCEPTED_BASE_SHA, "tree": registration.ACCEPTED_BASE_TREE})
    _same("input registration", request["input_registration"], {**request["frozen_source"],
        "path": registration.SOURCE_PROFILE, "sha256": registration.SOURCE_PROFILE_SHA256})
    _same("declared contents", request["deliverables"], bridge.DELIVERABLES)
    _same("model-free preparation permission" if preparation_only else "finite grading permission",
          request["policy"], PROBE_POLICY if preparation_only else POLICY)
    begin, end = request["not_before_unix"], request["expires_unix"]
    _require(type(begin) is int and type(end) is int and 0 <= begin < end and end - begin <= 2700,
             "finite_admission_required")
    if admission:
        _require(begin <= time.time() < end, "current_admission_required")
    ci = request["ci"]
    _require(type(ci) is dict and type(ci.get("run_number")) is int and ci["run_number"] > 0,
             "actual_all_event_run_number_required")
    _same("Actions request", ci, {"repository": shared.REPOSITORY, "workflow": WORKFLOW, "ref": "refs/heads/main",
        "actor": shared.OWNER, "job": JOB, "attempt": 1, "run_number": ci["run_number"],
        "runner": "ubuntu-24.04", "runner_os": "Linux", "runner_arch": "X64", "image": GRADING_IMAGE})
    environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": shared.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": shared.OWNER, "GITHUB_TRIGGERING_ACTOR": shared.OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_NUMBER": str(ci["run_number"]), "GITHUB_JOB": JOB,
        "GITHUB_SHA": controller_sha, "TIME_BUDGET_GRADE_WORKFLOW_SHA": controller_sha,
        "GITHUB_WORKFLOW_REF": shared.REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_ENVIRONMENT": "github-hosted",
        "JE_ARROW_MALLOC_CONF": "background_thread:false"}
    _require(all(os.environ.get(key) == value for key, value in environment.items()), "Actions_source_caller_or_attempt_refused")
    _require(re.fullmatch(r"[1-9][0-9]{0,19}", os.environ.get("GITHUB_RUN_ID", "")) is not None
             and sys.version_info[:3] == (3, 10, 12), "Actions_runtime_required")
    paths = _paths()
    _same("canonical private paths", request["paths"], {key: str(value) for key, value in paths.items()})
    for path in paths.values():
        _canonical_path(str(path))
    roots = [paths["bootstrap_root"], *(paths[key] for key in ROOT_NAMES)]
    _require(all(not a.is_relative_to(b) and not b.is_relative_to(a)
                 for index, a in enumerate(roots) for b in roots[index + 1:]), "source_state_overlap")
    if not preparation_only:
        prefix, _, _ = _namespace()
        parent = request["storage"].get("expected_parent")
        _require(storage._hash(parent, 40), "independent_private_parent_required")
        _same("private grading target", request["storage"], {"repository_name_sha256": shared.TARGET_SHA256,
            "branch": shared.BRANCH, "prefix": prefix, "expected_parent": parent})
    return request, paths, _identity(data)


def _checked_bootstrap(bootstrap: Path, controller_sha: str, controller_tree: str) -> tuple[Path, Path]:
    """Read only this live linked controller's exact ordinary bootstrap."""
    _require(_canonical_path(str(bootstrap)) == bootstrap and (bootstrap / ".git").is_dir()
             and not (bootstrap / ".git").is_symlink(), "ordinary_Actions_bootstrap_required")
    _require(not any(char == "*" or ord(char) < 32 or ord(char) == 127 for char in str(bootstrap)),
             "bootstrap_path_refused")
    linked, common = _repository(Path(__file__).resolve().parents[1])
    _registered_gitdir(linked, common)
    _require(common == bootstrap / ".git", "bootstrap_not_controller_common")
    # Keep the shared pinned helper unchanged. Its closed environment and local
    # Git protections still apply; only these fixed reads gain exact-path trust.
    for arguments, value in (
        (("--show-toplevel",), str(bootstrap)),
        (("--path-format=absolute", "--git-common-dir"), str(common)),
        (("--verify", "--end-of-options", "HEAD^{commit}"), controller_sha),
        (("--verify", "--end-of-options", "HEAD^{tree}"), controller_tree),
    ):
        _require(_git(bootstrap, "-c", "safe.directory=" + str(bootstrap), "rev-parse", *arguments).stdout
                 == (value + "\n").encode(), "bootstrap_identity_mismatch")
    return bootstrap, common


@contextmanager
def checked_request(*, request_json: str, expected_request_sha256: str, controller_sha: str, controller_tree: str,
                    completion_only: bool = False, preparation_only: bool = False):
    request, paths, identity = _public_request(request_json, expected_request_sha256, controller_sha, controller_tree,
                                              admission=not completion_only, preparation_only=preparation_only)
    bootstrap, common = paths["bootstrap_root"], paths["bootstrap_root"] / ".git"

    def layout():
        _require(_checked_bootstrap(bootstrap, controller_sha, controller_tree) == (bootstrap, common),
                 "ordinary_Actions_bootstrap_required")
        _require(all(_repository(paths[key])[1] == common for key in ("controller_root", "runtime_root", "frozen_root")),
                 "linked_C_R_F_required")
        _same("approved login path", os.environ.get("AZURE_CONFIG_DIR"), str(paths["login_root"]))
        info = paths["login_root"].stat()
        _require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid == os.getuid(),
                 "private_login_directory_required")

    with ExitStack() as sources:
        sources.enter_context(_held_parents(bootstrap, (".git/HEAD",)))
        sources.enter_context(_held_parents(paths["state_root"].parent, tuple(ROOT_NAMES.values())))
        layout()
        _, tree, files = sources.enter_context(registration._reviewed_source(paths["controller_root"], controller_sha, SOURCE_ROLES))
        _same("controller tree", tree, controller_tree)
        live = Path(__file__).resolve().parents[1]
        for role, file_identity in files.items():
            _read_bytes(live / role, **file_identity)
        plan = bridge.reader._result_registration(paths["runtime_root"], request["completion"]["source"])
        compiled = registration._compile_registration(plan, (paths["runtime_root"], RETAINED["source"]["sha"],
            paths["frozen_root"], registration.ACCEPTED_BASE_SHA), True, sources)
        _require(any(run.run_id == CELL["run_id"] and run.condition == CELL["condition"] and run.repeat == 1
                     and CELL["task_id"] in run.task_ids for run in compiled.runs), "registered_Task3_required")
        _same("original R registration", seal(plan), request["registration_sha256"])
        _same("original dataset", seal(plan["shared"]["dataset"]), request["dataset_sha256"])
        step0, specs = native._input_contract(plan, paths["frozen_root"])
        _same("original whole Step0", request["step0"], step0)
        if not completion_only:
            _require(not os.path.lexists(paths["state_root"]), "prior_state_never_adopted")
        yield {"request": request, "request_identity": identity, "paths": paths, "plan": plan, "input_specs": specs,
               "completion_only": completion_only,
               "ci": {"run_id": os.environ["GITHUB_RUN_ID"], "run_number": request["ci"]["run_number"], "attempt": 1, "job": JOB}}
        layout()
        for role, file_identity in files.items():
            _read_bytes(live / role, **file_identity)


@contextmanager
def _storage_credential(token):
    """Only the next intake/storage call sees this in-memory credential."""
    _require(not any(os.environ.get(key) for key in bridge.OTHER_CREDENTIALS | {"HF_TOKEN", "HF_TOKEN_PATH"}), "unexpected_credentials")
    os.environ["HF_TOKEN"] = token
    try:
        yield
    finally:
        os.environ.pop("HF_TOKEN", None)


def _originals(context, token):
    paths = context["paths"]
    root = paths["state_root"] / "originals"
    with _publication_parents(root.parent) as (check, mkdir, descriptor):
        mkdir(root)
        with storage._time_bound(intake.TRANSFER_TIMEOUT_SECONDS) as deadline, intake._hf_environment(online=True):
            remaining = shared.MAX_INPUT_BYTES
            for name, repo, revision, member, role, spec in context["input_specs"]:
                path = _path(root, name)
                for parent in reversed(path.parents):
                    if parent.is_relative_to(root) and not parent.exists():
                        mkdir(parent)
                data = intake._hf_read(repo, revision, member, role=role, token=token,
                    limit=min(spec["size"] or native.originals.MAX_REFERENCE_BYTES, remaining), deadline=deadline)
                _same("original digest", _identity(data)["sha256"], spec["sha256"])
                _require(0 < len(data) <= remaining and (spec["size"] is None or len(data) == spec["size"]), "original_size_bound")
                _require(token.encode() not in data, "credential_in_original")
                _write_no_clobber(path, data, parent_fd=descriptor(path.parent))
                remaining -= len(data)
        check()


def _intake_request(context):
    request, paths = context["request"], context["paths"]
    value = {key: request[key] for key in ("controller", "completion", "cell", "registration_sha256", "frozen_source",
        "dataset_sha256", "step0", "deliverables")}
    value.update(format=bridge.REQUEST_FORMAT, purpose=bridge.PURPOSE,
        input_registration={key: request["input_registration"][key] for key in ("sha", "tree", "path")},
        paths={**{key: str(paths[key]) for key in bridge.PATH_KEYS - {"destination"}},
               "destination": str(paths["preparation_root"])})
    return bridge.reader._bytes(value)


def _direction(context, handle):
    """Derive a concrete direction only from approved request + real validators."""
    paths, request = context["paths"], context["request"]
    _require(os.environ.get("GRADER_TIME_BUDGET_SEC", str(execution.STEP8_SECONDS)) == str(execution.STEP8_SECONDS),
             "frozen_step8_time_budget_required")
    arguments = execution._native_arguments(handle)
    arguments.update(attempt_store=paths["attempt_store"], destination=paths["destination"], direction_file=paths["direction_file"],
        expected_execution_context_sha256=execution.execution_context_sha256())
    with execution._checked_preparation(context["plan"], arguments) as checked:
        _require(os.environ.get("AZURE_AI_REQUIRE_EXPECTED_IDENTITIES") == "1" and
                 os.environ.get("AZURE_AI_EXPECTED_DIRECT_ACCOUNT") == context["plan"]["shared"]["model"]["account"],
                 "approved_grading_account_required")
        routes = preflight_routes(grader_route_workloads(checked["config"]))
        settings = AzureAIRouteSettings.from_env()
        _require(settings.profile.value == "direct-v1", "approved_grading_route_required")
        binding = execution._execution_binding(checked, arguments)
        direction = {"direction_version": execution.DIRECTION_VERSION, "binding": binding.as_dict(),
                     "not_before": request["not_before_unix"], "expires_at": request["expires_unix"]}
        _write(paths["direction_file"], direction)
        arguments["expected_direction_sha256"] = _identity(execution._encoded(direction))["sha256"]
        execution.require_execution_direction(binding, direction_file=paths["direction_file"],
            expected_direction_sha256=arguments["expected_direction_sha256"])
        checked["reread"](initial=True)
    return arguments, binding, seal(routes)


def _commit(api, token, deadline, *, parent, files, control_path, control, cache):
    """Existing add-only CAS/object/control checks in a grading-only namespace."""
    prefix, _, _ = _namespace()
    _require(files.get(control_path) == _encoded(control) and all(name.startswith(prefix + "/") for name in files),
             "grading_only_namespace_required")
    staged = [_PublicationFile(name, io.BytesIO(data), len(data), _identity(data)["sha256"]) for name, data in sorted(files.items())]
    try:
        operations = _publication_additions(tuple(staged))
        storage._remaining(deadline)
        response = api.create_commit(repo_id=shared.TARGET, repo_type="dataset", revision=shared.BRANCH, token=token,
            parent_commit=parent, operations=operations, commit_message="Record one frozen native Task3 grading boundary",
            num_threads=1, run_as_future=False, create_pr=False)
        revision = getattr(response, "oid", None)
        _require(storage._hash(revision, 40) and revision != parent and not any(
            getattr(item, "_should_ignore", False) for item in operations), "commit_identity_unavailable")
        _same("immutable private commit", storage._metadata(api, shared.TARGET, revision, token, deadline)["sha"], revision)
        _objects(api, shared.TARGET, revision, [_object(name, data) for name, data in sorted(files.items())],
                 token, deadline, written_at=revision)
        found, _ = _control(api, shared.TARGET, revision, control_path, cache, token, deadline,
                            expected=_identity(_encoded(control)), written_at=revision)
        _same("private control readback", found, control)
        return revision
    finally:
        for item in staged:
            item.stream.close()


def _claim(context, binding, routes_sha256, token, *, diagnostics=None):
    paths, request = context["paths"], context["request"]
    prefix, claim_path, _ = _namespace()
    claim = {"format": "gpt54-time-budget-native-task3-grade-admission-v1", "cell": CELL,
        "frozen_source": request["frozen_source"], "original_output_commit": request["completion"]["output_commit"],
        "request_identity": context["request_identity"], "binding": binding.as_dict(), "ci": context["ci"],
        "grading_routes_sha256": routes_sha256, "expected_parent": request["storage"]["expected_parent"],
        "state": "permanently_consumed_not_completion"}
    _write(paths["state_root"] / "claim-reserved.json", claim)
    cache = paths["state_root"] / "claim-readback"
    cache.mkdir(mode=0o700)
    receipt = {"outcome": "uncertain", "returned_commit": None, "claim_identity": _identity(_encoded(claim))}
    try:
        with _storage_credential(token), _session(None) as (api, credential, deadline):
            parent = request["storage"]["expected_parent"]
            _same("independent private parent", storage._metadata(api, shared.TARGET, shared.BRANCH, credential, deadline)["sha"], parent)
            _require(api.get_paths_info(repo_id=shared.TARGET, repo_type="dataset", revision=parent,
                paths=[prefix], token=credential) == [], "grading_observation_already_occupied")
            receipt["returned_commit"] = _commit(api, credential, deadline, parent=parent, files={claim_path: _encoded(claim)},
                control_path=claim_path, control=claim, cache=cache)
            receipt["outcome"] = "acknowledged"
    except (Exception, KeyboardInterrupt) as error:
        _failure(diagnostics, "claim", error)
        _write(paths["state_root"] / "claim-receipt.json", receipt)
        raise NativeGradingCIRefused("claim_unconfirmed_never_adopt_or_retry") from None
    _write(paths["state_root"] / "claim-receipt.json", receipt)
    return claim, receipt


def _snapshot(context, token):
    """Private bytes only; even unvalidated partial grade files remain evidence."""
    paths = context["paths"]
    files, originals = {}, {}
    candidates = {"request.json": paths["state_root"] / "request.json",
        "direction.json": paths["direction_file"], "claim-reserved.json": paths["state_root"] / "claim-reserved.json",
        "claim-receipt.json": paths["state_root"] / "claim-receipt.json",
        "intake.json": paths["hydration_root"] / bridge.READY,
        "preparation.json": paths["preparation_root"] / preparation.READY}
    for label, root in (("execution", paths["destination"]), ("local-attempt", paths["attempt_store"]),
                        ("F-partial", paths["execution_input_directory"] / "source/data/grades")):
        if not os.path.lexists(root):
            continue
        _canonical_path(str(root))
        for directory, directories, names in os.walk(root, followlinks=False):
            for name in directories + names:
                member = Path(directory) / name
                _require(not member.is_symlink(), "retention_symlink_refused")
            for name in names:
                member = Path(directory) / name
                relative = member.relative_to(root).as_posix()
                candidates[label + "/" + relative] = _path(root, relative)
                _require(len(candidates) <= storage.MAX_FILES, "retention_file_bound")
    for role, path in sorted(candidates.items()):
        data = storage._bytes(path, limit=execution.MAX_GRADE_BYTES)
        _require(token.encode() not in data, "credential_in_private_output")
        files[role], originals[path] = data, _identity(data)
    _require(sum(map(len, files.values())) <= storage.MAX_TOTAL_BYTES, "retention_total_bound")
    for path, identity in originals.items():
        _read_bytes(path, **identity)
    return files


def _retain(context, claim, receipt, outcome, token, *, diagnostics=None):
    root = context["paths"]["state_root"]
    prefix, claim_path, manifest_path = _namespace()
    files = _snapshot(context, token)
    manifest = {"format": "gpt54-time-budget-native-task3-grade-private-output-v1", "cell": CELL,
        "request_identity": context["request_identity"], "claim_commit": receipt["returned_commit"],
        "claim_identity": receipt["claim_identity"], "execution_receipt": outcome,
        "files": {name: _identity(data) for name, data in sorted(files.items())},
        "stdout_stderr": "discarded_by_accepted_executor_not_available", "retry_allowed": False}
    _write(root / "retention-reserved.json", {"manifest_identity": _identity(_encoded(manifest)), "outcome": "unresolved"})
    cache = root / "retention-readback"
    cache.mkdir(mode=0o700)
    result = {"outcome": "uncertain", "returned_commit": None, "manifest_identity": _identity(_encoded(manifest)),
              "file_count": len(files), "file_bytes": sum(map(len, files.values()))}
    try:
        _require(_snapshot(context, token) == files, "retained_local_bytes_changed")
        with _storage_credential(token), _session(None) as (api, credential, deadline):
            parent = receipt["returned_commit"]
            _same("claim remains branch parent", storage._metadata(api, shared.TARGET, shared.BRANCH, credential, deadline)["sha"], parent)
            _objects(api, shared.TARGET, parent, [_object(claim_path, _encoded(claim))], credential, deadline, written_at=parent)
            payload = {prefix + "/evidence/" + name: data for name, data in files.items()}
            payload[manifest_path] = _encoded(manifest)
            _require(api.get_paths_info(repo_id=shared.TARGET, repo_type="dataset", revision=parent,
                paths=list(payload), token=credential) == [], "retention_destination_occupied")
            result["returned_commit"] = _commit(api, credential, deadline, parent=parent, files=payload,
                control_path=manifest_path, control=manifest, cache=cache)
            _objects(api, shared.TARGET, result["returned_commit"], [_object(claim_path, _encoded(claim))],
                     credential, deadline, written_at=parent)
        _require(_snapshot(context, token) == files, "retained_local_bytes_changed")
        result["outcome"] = "acknowledged"
    except (Exception, KeyboardInterrupt) as error:
        _failure(diagnostics, "retention", error)
        result["returned_commit"] = None  # Never adopt a lost response or repeat a write.
    _write(root / "retention-receipt.json", result)
    return result


def _completion(context, *, binding=None, receipt=None, outcome=None, retained=None, diagnostics=None):
    request = context["request"]
    diagnostics = _diagnostics() if diagnostics is None else diagnostics
    acknowledged = retained is not None and retained["outcome"] == "acknowledged"
    terminal = outcome["terminal_reason"] if outcome is not None else None
    status = "uncertain"
    if acknowledged and outcome is not None:
        status = "success" if terminal == "completed" and outcome["grade_file"] is not None and outcome["cleanup_confirmed"] else (
            "timeout" if terminal == "timeout" else "partial")
    if status == "success" and any(item["category"] is not None for item in diagnostics.values()):
        status = "uncertain"  # A later context-exit refusal cannot certify success.
    origin = binding.as_dict()["grading_input_origin"] if binding is not None else None
    return {"format": FORMAT, "cell": CELL, "controller": request["controller"], "observation_source": request["completion"]["source"],
        "frozen_source": request["frozen_source"], "request_identity": context["request_identity"], "ci": context["ci"],
        "original_output_commit": request["completion"]["output_commit"], "original_result_identity": request["completion"]["result_identity"],
        "original_result_fingerprint": request["completion"]["result_fingerprint"],
        "derived_result_identity": origin["derived_result_identity"] if origin else None,
        "derived_result_fingerprint": origin["derived_result_fingerprint"] if origin else None,
        "preparation_identity": origin["preparation_identity"] if origin else None,
        "execution_binding_sha256": seal(binding.as_dict()) if binding else None,
        "claim_commit": receipt["returned_commit"] if receipt else None, "retention_commit": retained["returned_commit"] if acknowledged else None,
        "retention": "acknowledged" if acknowledged else "uncertain", "status": status, "terminal_reason": terminal,
        "entry_invoked": outcome["entry_invoked"] if outcome else None, "cleanup_confirmed": outcome["cleanup_confirmed"] if outcome else None,
        "grade_identity": {key: outcome["grade_file"][key] for key in ("sha256", "size")} if outcome and outcome["grade_file"] else None,
        "retained_manifest_identity": retained["manifest_identity"] if acknowledged else None,
        "retained_file_count": retained["file_count"] if acknowledged else None, "retained_file_bytes": retained["file_bytes"] if acknowledged else None,
        "stdout_stderr": "discarded_by_accepted_executor_not_available", "usage": None, "cost": None, "quality_score": None,
        "retry_allowed": False, "other_cells_graded": 0, "diagnostics": diagnostics}


def _check_diagnostics(value):
    diagnostics = value["diagnostics"]
    _require(type(diagnostics) is dict and set(diagnostics) == set(DIAGNOSTIC_STAGES), "public_diagnostics_schema_refused")
    for item in diagnostics.values():
        _require(type(item) is dict and set(item) == {"state", "category"}
                 and type(item["state"]) is str and item["state"] in DIAGNOSTIC_STATES
                 and (item["category"] is None or type(item["category"]) is str
                      and item["category"] in FAILURE_CATEGORIES)
                 and (item["category"] is None or item["state"] == "started"), "public_diagnostics_value_refused")
    states = {stage: item["state"] for stage, item in diagnostics.items()}
    for previous, current in zip(DIAGNOSTIC_STAGES[:5], DIAGNOSTIC_STAGES[1:6]):
        _require(states[current] == "unknown" or states[previous] == "completed", "public_diagnostics_order_refused")
    if states["retention"] != "unknown":
        _require(states["claim"] == "completed" and (states["executor"] == "completed"
                 or states["executor"] == "started" and diagnostics["executor"]["category"] is not None),
                 "public_diagnostics_order_refused")
    _require(states["context_exit"] == "unknown" or states["retention"] != "unknown", "public_diagnostics_order_refused")
    _require(states["claim"] != "completed" or value["claim_commit"] is not None, "public_diagnostics_claim_refused")
    _require(value["claim_commit"] is None or states["claim"] in {"unknown", "completed"}, "public_diagnostics_claim_refused")
    _require(states["executor"] != "completed" or value["terminal_reason"] is not None, "public_diagnostics_executor_refused")
    _require(states["retention"] != "completed" or value["retention"] == "acknowledged", "public_diagnostics_retention_refused")
    _require(value["retention"] != "acknowledged" or states["retention"] in {"unknown", "completed"},
             "public_diagnostics_retention_refused")
    _require(value["status"] != "success" or all(state == "completed" for state in states.values()),
             "success_requires_completed_stages")


def validate_completion(value, context):
    # Build the exact fixed binding portion; no received envelope selects scope.
    baseline = _completion(context)
    _require(type(value) is dict and set(value) == set(baseline), "public_completion_schema_refused")
    mutable = {"derived_result_identity", "derived_result_fingerprint", "preparation_identity", "execution_binding_sha256",
        "claim_commit", "retention_commit", "retention", "status", "terminal_reason", "entry_invoked", "cleanup_confirmed",
        "grade_identity", "retained_manifest_identity", "retained_file_count", "retained_file_bytes", "diagnostics"}
    _same("public independent bindings", {key: value[key] for key in value.keys() - mutable},
          {key: baseline[key] for key in baseline.keys() - mutable})
    for key in ("derived_result_identity", "preparation_identity", "grade_identity", "retained_manifest_identity"):
        if value[key] is not None:
            identity = value[key]
            _require(type(identity) is dict and set(identity) == {"size", "sha256"} and storage._hash(identity["sha256"])
                     and type(identity["size"]) is int and 0 < identity["size"] <= execution.MAX_GRADE_BYTES, "public_identity_refused")
    for key, width in (("derived_result_fingerprint", 64), ("execution_binding_sha256", 64), ("claim_commit", 40), ("retention_commit", 40)):
        _require(value[key] is None or storage._hash(value[key], width), "public_hash_refused")
    _require(value["status"] in {"success", "partial", "timeout", "uncertain"} and value["retention"] in {"acknowledged", "uncertain"},
             "public_status_refused")
    _require(value["terminal_reason"] in {None, "completed", "failed", "timeout", "cancelled", "cleanup_unconfirmed", "missing_grade"},
             "public_terminal_refused")
    _require(all(value[key] is None or type(value[key]) is bool for key in ("entry_invoked", "cleanup_confirmed")), "public_flag_refused")
    for key, maximum in (("retained_file_count", storage.MAX_FILES), ("retained_file_bytes", storage.MAX_TOTAL_BYTES)):
        _require(value[key] is None or type(value[key]) is int and 0 < value[key] <= maximum, "public_count_refused")
    retained = value["retention"] == "acknowledged"
    _require(all((value[key] is not None) == retained for key in
                 ("retention_commit", "retained_manifest_identity", "retained_file_count", "retained_file_bytes")), "public_retention_refused")
    _require(retained or value["status"] == "uncertain", "unconfirmed_retention_is_uncertain")
    if retained:
        _require(all(value[key] is not None for key in ("claim_commit", "execution_binding_sha256", "preparation_identity",
                 "derived_result_identity", "derived_result_fingerprint")), "retention_binding_required")
    if value["status"] == "success":
        _require(retained and value["claim_commit"] is not None and value["grade_identity"] is not None
                 and value["terminal_reason"] == "completed" and value["entry_invoked"] is True
                 and value["cleanup_confirmed"] is True, "success_requires_valid_grade_and_retention")
    _check_diagnostics(value)


def run(context):
    """All model-free checks, remote ACK and one native call share this scope."""
    started = time.monotonic()
    _require(context["completion_only"] is False, "completion_is_not_execution_authority")
    _same("grading operation", [context["request"]["format"], context["request"]["purpose"], context["request"]["policy"]],
          [REQUEST_FORMAT, PURPOSE, POLICY])
    token = os.environ.pop("HF_TOKEN", "")
    _require(bool(token) and len(token) <= 4096 and all(33 <= ord(c) <= 126 for c in token), "explicit_hf_token_required")
    _require(token not in bridge.reader._bytes(context["request"]).decode(), "credential_in_request")
    _require(not any(os.environ.get(key) for key in bridge.OTHER_CREDENTIALS | {"HF_TOKEN_PATH"}), "unexpected_credentials")
    paths = context["paths"]
    with _publication_parents(paths["state_root"].parent) as (_, mkdir, _):
        mkdir(paths["state_root"])
    _write(paths["state_root"] / "request.json", context["request"])
    paths["attempt_store"].mkdir(mode=0o700)
    binding = receipt = outcome = retained = None
    # In-memory observations only; never request, claim or retry authority.
    diagnostics = _diagnostics()
    stage = "environment"
    diagnostics[stage]["state"] = "started"
    try:
        with intake._hf_environment(online=False), ExitStack() as live:
            diagnostics[stage]["state"] = "completed"
            stage = "originals"
            diagnostics[stage]["state"] = "started"
            _originals(context, token)
            diagnostics[stage]["state"] = "completed"
            stage = "intake_preparation"
            diagnostics[stage]["state"] = "started"
            request = _intake_request(context)
            with _storage_credential(token):
                handle = live.enter_context(execution.prepare_native_task3_grading_execution(request_json=request.decode(),
                    expected_request_sha256=_identity(request)["sha256"], execution_input_directory=paths["execution_input_directory"]))
            diagnostics[stage]["state"] = "completed"
            stage = "direction"
            diagnostics[stage]["state"] = "started"
            arguments, binding, routes_sha256 = _direction(context, handle)
            _require(time.monotonic() - started < PRECLAIM_SECONDS, "setup_budget_exhausted_before_claim")
            diagnostics[stage]["state"] = "completed"
            stage = "claim"
            diagnostics[stage]["state"] = "started"
            claim, receipt = _claim(context, binding, routes_sha256, token, diagnostics=diagnostics)
            diagnostics[stage]["state"] = "completed"
            stage = "executor"
            diagnostics[stage]["state"] = "started"
            try:
                _require(time.monotonic() - started < PRECLAIM_SECONDS, "setup_budget_exhausted_after_claim")
                # The actual executor rechecks direction, source, origin, bytes,
                # local once-store and admission time before its own durable claim.
                outcome = execution.execute_native_task3_grading(context["plan"], **arguments)
                diagnostics[stage]["state"] = "completed"
            except (Exception, KeyboardInterrupt) as error:
                _failure(diagnostics, stage, error)
                outcome = None  # Available private partial files still survive below.
            stage = "retention"
            diagnostics[stage]["state"] = "started"
            retained = _retain(context, claim, receipt, outcome, token, diagnostics=diagnostics)
            if retained["outcome"] == "acknowledged":
                diagnostics[stage]["state"] = "completed"
            stage = "context_exit"
            diagnostics[stage]["state"] = "started"
        diagnostics[stage]["state"] = "completed"
    except (Exception, KeyboardInterrupt) as error:
        _failure(diagnostics, stage, error)  # Never format private errors or infer absent effects.
    finally:
        os.environ.pop("HF_TOKEN", None)
    completion = _completion(context, binding=binding, receipt=receipt, outcome=outcome, retained=retained,
                             diagnostics=diagnostics)
    validate_completion(completion, context)
    return completion


@contextmanager
def _probe_bound():
    # The hosted command has one 300s TERM/5s KILL bound. Do not nest an
    # ITIMER_REAL around the accepted 120s originals and 60s hydration timers.
    # Their SIGTERM handlers restore this handler before model-free F staging.
    previous = signal.getsignal(signal.SIGTERM)

    def stop(signum, frame):
        raise NativeGradingCIRefused("preparation_probe_interrupted")

    try:
        signal.signal(signal.SIGTERM, stop)
        yield time.monotonic() + PROBE_SECONDS
    finally:
        signal.signal(signal.SIGTERM, previous)


def _probe_completion(context, *, verified=None, diagnostics=None, refusal_point=None):
    request = context["request"]
    diagnostics = ({stage: {"state": "unknown", "category": None} for stage in PROBE_STAGES}
                   if diagnostics is None else diagnostics)
    ready = all(item == {"state": "completed", "category": None} for item in diagnostics.values())
    return {"format": PROBE_FORMAT, "purpose": PROBE_PURPOSE, "cell": CELL,
        "controller": request["controller"], "observation_source": request["completion"]["source"],
        "frozen_source": request["frozen_source"], "request_identity": context["request_identity"], "ci": context["ci"],
        "original_output_commit": request["completion"]["output_commit"],
        "expected_result_identity": request["completion"]["result_identity"],
        "expected_result_fingerprint": request["completion"]["result_fingerprint"],
        "verified_preparation": verified, "status": "ready" if ready else "refused", "diagnostics": diagnostics,
        "refusal_point": refusal_point,
        "grading_authority": False, "handle_reusable": False, "retry_allowed": False}


def validate_probe_completion(value, context):
    _same("preparation operation", [context["request"]["format"], context["request"]["purpose"], context["request"]["policy"]],
          [PROBE_REQUEST_FORMAT, PROBE_PURPOSE, PROBE_POLICY])
    baseline = _probe_completion(context)
    _require(type(value) is dict and set(value) == set(baseline), "public_probe_schema_refused")
    mutable = {"verified_preparation", "status", "diagnostics", "refusal_point"}
    _same("public independent probe bindings", {key: value[key] for key in value.keys() - mutable},
          {key: baseline[key] for key in baseline.keys() - mutable})
    diagnostics = value["diagnostics"]
    _require(type(diagnostics) is dict and set(diagnostics) == set(PROBE_STAGES), "public_probe_diagnostics_refused")
    for stage, item in diagnostics.items():
        _require(type(item) is dict and set(item) == {"state", "category"}
                 and type(item["state"]) is str and item["state"] in DIAGNOSTIC_STATES
                 and (item["category"] is None or type(item["category"]) is str
                      and item["category"] in FAILURE_CATEGORIES)
                 and (item["category"] is None or item["state"] == "started"), "public_probe_diagnostics_refused")
    for previous, current in zip(PROBE_STAGES, PROBE_STAGES[1:]):
        _require(diagnostics[current]["state"] == "unknown" or diagnostics[previous]["state"] == "completed",
                 "public_probe_stage_order_refused")
    point = value["refusal_point"]
    _require(point is None or (type(point) is str
             and point in {item.value for item in bridge.NativePreparationRefusalPoint}
             and diagnostics["intake_preparation"]["state"] == "started"
             and diagnostics["intake_preparation"]["category"] is not None), "public_probe_refusal_point_refused")
    verified = value["verified_preparation"]
    _require((verified is not None) == (diagnostics["intake_preparation"]["state"] == "completed"),
             "public_probe_preparation_required")
    if verified is not None:
        _require(type(verified) is dict and set(verified) == {"result_identity", "preparation_identity",
                 "derived_result_identity", "derived_result_fingerprint"}, "public_probe_preparation_schema_refused")
        _same("verified original result", verified["result_identity"], value["expected_result_identity"])
        for name in ("result_identity", "preparation_identity", "derived_result_identity"):
            identity = verified[name]
            _require(type(identity) is dict and set(identity) == {"size", "sha256"}
                     and type(identity["size"]) is int and 0 < identity["size"] <= execution.MAX_METADATA_BYTES
                     and storage._hash(identity["sha256"]), "public_probe_identity_refused")
        _require(storage._hash(verified["derived_result_fingerprint"]), "public_probe_identity_refused")
    ready = all(item == {"state": "completed", "category": None} for item in diagnostics.values())
    _require(value["status"] == ("ready" if ready else "refused"), "public_probe_status_refused")


def prepare_probe(context):
    """Validate/hydrate/stage and close the native handle; never issue a direction.

    Local partial input/preparation files are preserved. There is deliberately
    no attempt-store, grading namespace read, claim, executor or retention path.
    """
    _require(context["completion_only"] is False, "completion_is_not_preparation_authority")
    _same("preparation operation", [context["request"]["format"], context["request"]["purpose"], context["request"]["policy"]],
          [PROBE_REQUEST_FORMAT, PROBE_PURPOSE, PROBE_POLICY])
    token = os.environ.pop("HF_TOKEN", "")
    _require(bool(token) and len(token) <= 4096 and all(33 <= ord(c) <= 126 for c in token), "explicit_hf_token_required")
    _require(token not in bridge.reader._bytes(context["request"]).decode(), "credential_in_request")
    _require(not any(os.environ.get(key) for key in bridge.OTHER_CREDENTIALS | {"HF_TOKEN_PATH"}), "unexpected_credentials")
    paths = context["paths"]
    with _publication_parents(paths["state_root"].parent) as (_, mkdir, _):
        mkdir(paths["state_root"])
    diagnostics = {stage: {"state": "unknown", "category": None} for stage in PROBE_STAGES}
    verified, stage, refusal_point = None, "environment", None
    diagnostics[stage]["state"] = "started"
    try:
        with _probe_bound() as deadline, intake._hf_environment(online=False), ExitStack() as live:
            diagnostics[stage]["state"] = "completed"
            stage = "originals"
            diagnostics[stage]["state"] = "started"
            _originals(context, token)
            _require(time.monotonic() < deadline, "preparation_probe_budget_exhausted")
            diagnostics[stage]["state"] = "completed"
            stage = "intake_preparation"
            diagnostics[stage]["state"] = "started"
            refusal_point = bridge.NativePreparationRefusalPoint.INTAKE_REQUEST
            request = _intake_request(context)
            refusal_point = bridge.NativePreparationRefusalPoint.NATIVE_CONTEXT
            with _storage_credential(token):
                handle = live.enter_context(execution.prepare_native_task3_grading_execution(request_json=request.decode(),
                    expected_request_sha256=_identity(request)["sha256"], execution_input_directory=paths["execution_input_directory"]))
            # Reuse the real source/input/origin/derived-byte rereads, without
            # constructing an execution binding or consulting a grading route.
            refusal_point = bridge.NativePreparationRefusalPoint.MATERIALIZED_NATIVE_REREAD
            with execution._checked_preparation(context["plan"], execution._native_arguments(handle)) as checked:
                origin = checked["origin"]
                observed = {"result_identity": origin["original_result_identity"],
                    **{key: origin[key] for key in ("preparation_identity", "derived_result_identity", "derived_result_fingerprint")}}
                checked["reread"](initial=True)
            refusal_point = None
            _require(time.monotonic() < deadline, "preparation_probe_budget_exhausted")
            verified = observed
            diagnostics[stage]["state"] = "completed"
            stage = "context_exit"
            diagnostics[stage]["state"] = "started"
        _require(time.monotonic() < deadline, "preparation_probe_budget_exhausted")
        diagnostics[stage]["state"] = "completed"
    except (Exception, KeyboardInterrupt) as error:
        _failure(diagnostics, stage, error)
        if (stage == "intake_preparation"
                and type(error) in (execution.GradingExecutionRefused, bridge.NativeGradingIntakeRefused)
                and type(error.refusal_point) is bridge.NativePreparationRefusalPoint):
            refusal_point = error.refusal_point
    finally:
        os.environ.pop("HF_TOKEN", None)
    completion = _probe_completion(context, verified=verified, diagnostics=diagnostics,
        refusal_point=refusal_point.value if type(refusal_point) is bridge.NativePreparationRefusalPoint else None)
    validate_probe_completion(completion, context)
    return completion


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise NativeGradingCIRefused("invalid_arguments")


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument("operation", choices=("validate-request", "run", "verify-completion",
        "validate-probe-request", "prepare-probe", "verify-probe-completion"))
    for name in ("controller-sha", "controller-tree", "expected-request-sha256"):
        parser.add_argument("--" + name, required=True)
    try:
        arguments = vars(parser.parse_args(argv))
        operation = arguments.pop("operation")
        probe = operation in {"validate-probe-request", "prepare-probe", "verify-probe-completion"}
        verifying = operation in {"verify-completion", "verify-probe-completion"}
        validate = validate_probe_completion if probe else validate_completion
        logging.disable(logging.CRITICAL)
        os.umask(0o077)
        with checked_request(request_json=os.environ.get("TIME_BUDGET_GRADE_REQUEST_JSON", ""),
                             completion_only=verifying, preparation_only=probe, **arguments) as context:
            if verifying:
                validate(_read(context["paths"]["state_root"] / "completion.json"), context)
                completion = None
            else:
                completion = prepare_probe(context) if operation == "prepare-probe" else run(context) if operation == "run" else None
        if completion is not None:
            validate(completion, context)
            _write(context["paths"]["state_root"] / "completion.json", completion)
            return 0 if completion["status"] == ("ready" if probe else "success") else 2
        print('{"outcome":"validated_not_execution_authority"}')
        return 0
    except (Exception, KeyboardInterrupt):
        print('{"outcome":"refused_or_uncertain"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
