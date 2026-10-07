"""One independently directed registered native r1 observation, never a scheduler.

Only one selected task in the fixed native r1 run can acquire its permanent
private claim. Originals and the full canonical Step0 come from the accepted
input-only primitives; neither a local marker nor the closed pilot supplies authority.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
from pathlib import Path
import re
import stat
import sys
import time
from contextlib import ExitStack, contextmanager
from dataclasses import asdict

import codex_budget_pilot_output as storage
import codex_ci_input_bundle as originals
import codex_ci_input_intake as intake
import gpt54_time_budget_codex_observation as observation
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_v2_ci as shared
from codex_budget_pilot_retention import _control, _encoded, _object, _objects, _session
from core.agentic_v2_preregistration import seal
from core.codex_runtime_config import resolve_run_root_base
from core.hf_publication import _PublicationFile, _publication_additions
from core.inference_manifest import (
    STEP2_PROGRESS_SCHEMA, canonicalize_inference_payload, validate_step2_progress_results,
)
from core.result_fingerprint import validate_inference_result_fingerprint
from core.time_budget_observation_deadline import ObservationIdentity, TIMEOUT
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_disposable_checkout import _git, _repository
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object as _json_object, _read_bytes, _same, _snapshot_deliverables

HELPER = "batch-runner/gpt54_time_budget_codex_ci.py"
WORKFLOW = ".github/workflows/gpt54-time-budget-first-codex.yml"
REPOSITORY, OWNER, JOB = shared.REPOSITORY, shared.OWNER, "observation"
TARGET, TARGET_SHA256, BRANCH = shared.TARGET, shared.TARGET_SHA256, "main"
REQUEST_VERSION = "gpt54-time-budget-first-codex-ci-request-v1"
ENVELOPE_VERSION = "gpt54-time-budget-first-codex-ci-completion-v1"
PURPOSE = "execute_and_privately_retain_first_codex_observation"
# Legacy Task1 identities also serve the fixed historical uncertainty reader.
CELL = {"study_id": registration.STUDY_ID, "run_id": "gpt54_time_budget_v1_codex_r1",
        "condition": "codex", "repeat": 1, "task_id": "02aa1805-c658-4069-8a6a-02dec146063a"}
PREFIX, CLAIM, MANIFEST = shared._namespace(CELL)
ROOT_NAMES = {"runtime_root": "time-budget-codex-runtime", "frozen_root": "time-budget-codex-frozen",
              "state_root": "time-budget-first-codex", "native_root": "time-budget-codex-native",
              "login_root": "time-budget-codex-azure-login"}
SOURCE_ROLES = {
    HELPER, WORKFLOW, observation.ENTRYPOINT, observation.host_identity.ENTRYPOINT, shared.HELPER,
    "batch-runner/codex_ci_input_intake.py", "batch-runner/codex_ci_input_bundle.py",
    "batch-runner/codex_budget_pilot_output.py", "batch-runner/codex_budget_pilot_retention.py",
    "batch-runner/scripts/azure_oidc_identity_preflight.py", "batch-runner/requirements.txt",
}
_canonical_path, _write, _read = shared._canonical_path, shared._write, shared._read


class FirstCodexCIRefused(shared.FirstV2CIRefused):
    """Static refusal only; a missing result says nothing about paid effects."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise FirstCodexCIRefused(reason)


def _bytes(value) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _selected_cell(compiled: registration.CompiledTimeBudgetRegistration, requested: dict) -> dict:
    """Bind one requested task to the already source-verified native r1 run."""
    runs = [run for run in compiled.runs if run.run_id == CELL["run_id"]
            and run.condition == "codex" and run.repeat == 1]
    _require(compiled.runtime_bound and len(runs) == 1 and type(requested) is dict
             and type(requested.get("task_id")) is str and requested["task_id"] in runs[0].task_ids,
             "registered_first_codex_task_required")
    run = runs[0]
    cell = {"study_id": registration.STUDY_ID, "run_id": run.run_id, "condition": run.condition,
            "repeat": run.repeat, "task_id": requested["task_id"]}
    _same("request cell", requested, cell)
    return cell


def _input_contract(plan: dict, frozen: Path) -> tuple[dict, list[tuple]]:
    """Reuse only original-data facts, never the historical dispatch compiler."""
    dataset = plan["shared"]["dataset"]
    revision, specs = originals._original_specs(dataset)
    _same("original dataset", (dataset["repo_id"], revision),
          (intake.HF_ORIGINAL_REPO, intake.HF_ORIGINAL_REVISION))
    template = registration.CODEX_TEMPLATE
    source = registration.load_plan(frozen / template)
    _read_bytes(frozen / template, sha256=plan["source_pins"][template])
    repo = source["data"]["source"]
    _require(type(repo) is str and _identity(repo.encode())["sha256"] == intake.HF_STEP0_REPO_SHA256,
             "registered_step0_origin_required")
    step0 = {"repository_name_sha256": intake.HF_STEP0_REPO_SHA256,
             "revision": intake.HF_STEP0_REVISION, "member": Path(originals.STEP0_MANIFEST_PATH).name,
             "identity": dict(originals.STEP0_PIN)}
    operations = []
    for name, role in zip(specs, intake.HFRole, strict=True):
        member = (originals.PARQUET_PATH.removeprefix(originals.DATASET_ROOT + "/")
                  if role == intake.HFRole.PARQUET else step0["member"] if role == intake.HFRole.STEP0
                  else name.removeprefix(originals.REFERENCES + "/"))
        operations.append((name, repo if role == intake.HFRole.STEP0 else dataset["repo_id"],
                           step0["revision"] if role == intake.HFRole.STEP0 else revision,
                           member, role, specs[name]))
    return step0, operations


@contextmanager
def checked_request(*, request_json: str, expected_request_sha256: str,
                    reviewed_source_sha: str, reviewed_source_tree: str,
                    runtime_root: Path, frozen_root: Path, state_root: Path,
                    native_root: Path, admission: bool = True):
    """Bind actual Actions, ordinary bootstrap, linked R/F and input-only F."""
    data = request_json.encode("utf-8")
    _require(0 < len(data) <= shared.MAX_REQUEST_BYTES and storage._hash(expected_request_sha256)
             and _identity(data)["sha256"] == expected_request_sha256, "independent_request_digest_required")
    request = json.loads(data, object_pairs_hook=_json_object)
    _require(type(request) is dict and set(request) == {
        "format", "purpose", "source", "frozen_source", "input_registration", "cell", "ci",
        "registration_sha256", "dataset_sha256", "step0", "paths", "storage", "not_before_unix", "expires_unix",
    }, "request_schema")
    _same("request format", request["format"], REQUEST_VERSION)
    _same("request purpose", request["purpose"], PURPOSE)
    _require(type(request["cell"]) is dict and type(request["cell"].get("repeat")) is int,
             "fixed_cell_schema")
    _require(storage._hash(reviewed_source_sha, 40) and storage._hash(reviewed_source_tree, 40),
             "independent_reviewed_commit_and_tree_required")
    _same("request source", request["source"], {"sha": reviewed_source_sha, "tree": reviewed_source_tree})
    _same("frozen source", request["frozen_source"], {
        "sha": registration.ACCEPTED_BASE_SHA, "tree": registration.ACCEPTED_BASE_TREE})
    _same("input registration", request["input_registration"], {
        "source_sha": registration.ACCEPTED_BASE_SHA, "source_tree": registration.ACCEPTED_BASE_TREE,
        "path": registration.SOURCE_PROFILE, "sha256": registration.SOURCE_PROFILE_SHA256})
    begin, end = request["not_before_unix"], request["expires_unix"]
    _require(type(begin) is int and type(end) is int and 0 <= begin < end and end - begin <= 2700,
             "finite_admission_window_required")
    if admission:
        _require(begin <= time.time() < end, "request_not_current")
    ci = request["ci"]
    _require(type(ci) is dict and type(ci.get("run_number")) is int and ci["run_number"] > 0
             and type(ci.get("attempt")) is int,
             "independent_dispatch_number_required")
    _same("intended Actions context", ci, {
        "repository": REPOSITORY, "workflow": WORKFLOW, "ref": "refs/heads/main", "actor": OWNER,
        "job": JOB, "attempt": 1, "run_number": ci["run_number"], "runner": "ubuntu-22.04",
        "runner_os": "Linux", "runner_arch": "X64"})
    required = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": OWNER, "GITHUB_TRIGGERING_ACTOR": OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_NUMBER": str(ci["run_number"]), "GITHUB_JOB": JOB,
        "GITHUB_SHA": reviewed_source_sha, "TIME_BUDGET_CODEX_WORKFLOW_SHA": reviewed_source_sha,
        "GITHUB_WORKFLOW_REF": REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_ENVIRONMENT": "github-hosted", "ImageOS": "ubuntu22",
        "JE_ARROW_MALLOC_CONF": "background_thread:false",
    }
    _require(all(os.environ.get(key) == value for key, value in required.items()), "ci_source_cell_or_attempt_refused")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    _require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None
             and sys.version_info[:3] == (3, 10, 12), "ci_runtime_identity_required")
    runner_temp = _canonical_path(os.environ.get("RUNNER_TEMP", ""))
    bootstrap = _canonical_path(os.environ.get("GITHUB_WORKSPACE", ""))
    roots = {name: _canonical_path(str(value)) for name, value in {
        "runtime_root": runtime_root, "frozen_root": frozen_root, "state_root": state_root,
        "native_root": native_root, "login_root": runner_temp / ROOT_NAMES["login_root"],
    }.items()}
    _same("request canonical paths", request["paths"], {
        "bootstrap_root": str(bootstrap), **{name: str(value) for name, value in roots.items()}})
    _require(all(roots[name] == runner_temp / basename for name, basename in ROOT_NAMES.items()),
             "ci_canonical_roots_required")
    source_paths = [bootstrap, *roots.values()]
    _require(all(not a.is_relative_to(b) and not b.is_relative_to(a)
                 for index, a in enumerate(source_paths) for b in source_paths[index + 1:]), "source_state_overlap")
    common = bootstrap / ".git"

    def check_layout():
        _same("actual bootstrap path", os.environ.get("GITHUB_WORKSPACE"), str(bootstrap))
        _same("actual runner temporary path", os.environ.get("RUNNER_TEMP"), str(runner_temp))
        _require(common.is_dir() and _repository(bootstrap) == (bootstrap, common), "ordinary_actions_bootstrap_required")
        for revision, expected in (("HEAD^{commit}", reviewed_source_sha), ("HEAD^{tree}", reviewed_source_tree)):
            _require(_git(bootstrap, "rev-parse", "--verify", "--end-of-options", revision).stdout
                     == (expected + "\n").encode("ascii"), "actions_bootstrap_commit_or_tree_changed")
        _require(all(_repository(roots[name])[1] == common for name in ("runtime_root", "frozen_root")),
                 "actions_linked_common_git_required")
        _same("native environment root", os.environ.get("GDPVAL_CODEX_RUN_ROOT"), str(roots["native_root"]))
        _require(_canonical_path(str(resolve_run_root_base())) == roots["native_root"], "validated_native_root_required")
        _same("approved login directory", os.environ.get("AZURE_CONFIG_DIR"), str(roots["login_root"]))
        for name in ("native_root", "login_root"):
            info = roots[name].stat()
            _require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                     and stat.S_IMODE(info.st_mode) == 0o700, "owned_native_login_roots_required")

    target = request["storage"]
    _require(type(target) is dict and storage._hash(target.get("expected_parent"), 40),
             "independent_private_parent_required")
    _same("fixed private target", _identity(TARGET.encode())["sha256"], TARGET_SHA256)
    with ExitStack() as sources:
        parents = [
            sources.enter_context(_held_parents(bootstrap, (".git/HEAD",))),
            sources.enter_context(_held_parents(runner_temp, tuple(ROOT_NAMES.values()))),
        ]
        if roots["state_root"].exists():
            parents.append(sources.enter_context(_held_parents(roots["state_root"], ("request.json",))))
        check_layout()
        _, tree, identities = sources.enter_context(registration._reviewed_source(
            roots["runtime_root"], reviewed_source_sha, SOURCE_ROLES))
        _same("reviewed runtime tree", tree, reviewed_source_tree)
        for role, module in (
            (HELPER, sys.modules[__name__]), (observation.ENTRYPOINT, observation), (shared.HELPER, shared),
            (observation.host_identity.ENTRYPOINT, observation.host_identity),
            ("batch-runner/codex_ci_input_intake.py", intake), ("batch-runner/codex_ci_input_bundle.py", originals),
            ("batch-runner/codex_budget_pilot_output.py", storage),
        ):
            _read_bytes(Path(module.__file__), **identities[role])
        plan = registration.load_registration(roots["runtime_root"] / registration.REGISTRATION_PATH)
        compiled = registration._compile_registration(plan, (
            roots["runtime_root"], reviewed_source_sha, roots["frozen_root"], registration.ACCEPTED_BASE_SHA), True, sources)
        cell = _selected_cell(compiled, request["cell"])
        _same("private study storage", target, {"repository_name_sha256": TARGET_SHA256, "branch": BRANCH,
              "prefix": shared._namespace(cell)[0], "expected_parent": target["expected_parent"]})
        _same("request registration", request["registration_sha256"], compiled.manifest_sha256)
        _same("request dataset facts", request["dataset_sha256"], seal(plan["shared"]["dataset"]))
        sources.enter_context(registration._observation_input_registration(
            roots["frozen_root"], registration.ACCEPTED_BASE_SHA, registration.SOURCE_PROFILE, plan["shared"]["dataset"]))
        step0, input_specs = _input_contract(plan, roots["frozen_root"])
        _same("independent full Step0 provenance", request["step0"], step0)
        host = observation.host_identity.execution_host_identity(reviewed_source_sha)
        context = {"request": request, "request_identity": _identity(data), "plan": plan, "roots": roots,
                   "cell": cell, "host": host, "input_specs": input_specs,
                   "ci": {"run_id": run_id, "run_number": ci["run_number"], "job": JOB, "attempt": 1}}
        for check in parents:
            check()
        check_layout()
        yield context
        check_layout()
        _require(_input_contract(plan, roots["frozen_root"]) == (step0, input_specs), "input_provenance_changed")
        _same("final live host", observation.host_identity.execution_host_identity(reviewed_source_sha), host)
        for check in parents:
            check()


def _paths(context: dict) -> dict:
    root = context["roots"]["state_root"]
    return {"root": root, "inputs": root / "inputs", "parquet": root / "inputs" / originals.PARQUET,
            "references": root / "inputs" / originals.REFERENCES, "step0": root / "inputs" / originals.STEP0,
            "preparation": root / "preparation", "observation": root / "observation",
            "direction": root / "direction.json", "destination": root / "result"}


def _common(context: dict) -> dict:
    roots, paths = context["roots"], _paths(context)
    return {"runtime_root": roots["runtime_root"], "expected_reviewed_source_sha": context["request"]["source"]["sha"],
            "frozen_grader_root": roots["frozen_root"], "expected_grader_source_sha": registration.ACCEPTED_BASE_SHA,
            "input_registration_root": roots["frozen_root"], "expected_input_source_sha": registration.ACCEPTED_BASE_SHA,
            "input_registration_path": registration.SOURCE_PROFILE, "dataset_parquet": paths["parquet"],
            "reference_root": paths["references"], "step0_manifest": paths["step0"]}


def _reconstruct(context: dict, sources: ExitStack):
    _read_bytes(_paths(context)["step0"], **context["request"]["step0"]["identity"])
    return registration._observation_handoff_data(context["plan"], sources=sources,
        run_id=context["cell"]["run_id"], task_id=context["cell"]["task_id"],
        destination=_paths(context)["preparation"], **_common(context))


def _direction(context: dict, marker: dict) -> tuple[dict, dict]:
    paths, common = _paths(context), _common(context)
    _same("selected observation cell", {key: marker["observation"][key] for key in context["cell"]}, context["cell"])
    expected = _identity(_bytes(marker))
    binding = registration.ObservationExecutionBinding(
        expected["sha256"], expected["size"], _canonical_json(marker["observation"]),
        registration.ACCEPTED_BASE_SHA, registration.ACCEPTED_BASE_TREE, registration.FROZEN_TEMPLATE_SHA256,
        str(paths["preparation"]), str(paths["observation"]))
    config = json.loads(_read_bytes(paths["preparation"] / registration.HANDOFF_CONFIG,
                                  **marker["files"][registration.HANDOFF_CONFIG]))["configuration"]
    provider = observation._provider(config, context["plan"]["shared"]["model"])
    bound_paths = {"direction": str(paths["direction"]), "preparation": str(paths["preparation"]),
        **{name: str(common[name]) for name in ("runtime_root", "frozen_grader_root", "input_registration_root",
                                               "dataset_parquet", "reference_root", "step0_manifest")},
        "observation_directory": str(paths["observation"]), "destination": str(paths["destination"]),
        "native_run_root": str(context["roots"]["native_root"]),
        "input_source_sha": registration.ACCEPTED_BASE_SHA, "input_registration_path": registration.SOURCE_PROFILE}
    direction = {"direction_version": observation.DIRECTION_VERSION, "purpose": "execute_one_registered_observation",
        "execution_binding": asdict(binding), "paths": bound_paths, "host_sha256": context["host"]["instance_sha256"],
        "provider_binding": observation._provider_binding(provider), "step0_identity": context["request"]["step0"]["identity"],
        "not_before_unix": context["request"]["not_before_unix"], "expires_unix": context["request"]["expires_unix"]}
    return direction, expected


def _claim(context: dict, marker: dict) -> dict:
    direction, expected = _direction(context, marker)
    return {"format": "gpt54-time-budget-first-codex-admission-v1", "observation": marker["observation"],
        "source": context["request"]["source"], "request_identity": context["request_identity"],
        "preparation_identity": expected, "input_binding_sha256": seal(marker["inputs"]),
        "step0_provenance": context["request"]["step0"], "host": context["host"], "ci": context["ci"],
        "direction_identity": _identity(_bytes(direction)), "paths": direction["paths"],
        "expected_parent": context["request"]["storage"]["expected_parent"],
        "storage": {"repository_name_sha256": TARGET_SHA256, "branch": BRANCH,
                    "prefix": shared._namespace(context["cell"])[0]},
        "state": "permanently_consumed_not_completion"}


def _commit(api, token, deadline, *, cell, parent, files, control_path, control, cache):
    """Same add-only CAS/readback contract, restricted to the selected namespace."""
    prefix, _, _ = shared._namespace(cell)
    _same("private control cell", {key: control["observation"][key] for key in cell}, cell)
    _require(files.get(control_path) == _encoded(control) and all(name.startswith(prefix + "/") for name in files),
             "private_namespace_required")
    staged = [_PublicationFile(name, io.BytesIO(data), len(data), _identity(data)["sha256"])
              for name, data in sorted(files.items())]
    try:
        operations = _publication_additions(tuple(staged))
        storage._remaining(deadline)
        response = api.create_commit(repo_id=TARGET, repo_type="dataset", revision=BRANCH, token=token,
            parent_commit=parent, operations=operations, commit_message="Record time-budget native observation boundary",
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
    """Fetch the four pinned originals, validate one handoff, then claim once."""
    paths, root = _paths(context), _paths(context)["root"]
    prefix, claim_path, _ = shared._namespace(context["cell"])
    _require(not os.path.lexists(root), "partial_or_consumed_state_refused")
    _require(all(not any(context["roots"][name].iterdir()) for name in ("native_root", "login_root")),
             "fresh_native_login_roots_required")
    with _held_parents(root.parent, (root.name,)), _publication_parents(root.parent) as publication:
        check, mkdir, descriptor = publication
        mkdir(root)
        _write(root / "request.json", context["request"])
        mkdir(paths["inputs"])
        mkdir(paths["references"])
        token = os.environ.get("HF_TOKEN", "")
        _require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
                 "existing_hf_token_required")
        with storage._time_bound(intake.TRANSFER_TIMEOUT_SECONDS) as deadline, intake._hf_environment(online=True):
            remaining = shared.MAX_INPUT_BYTES
            for name, repo, revision, member, role, spec in context["input_specs"]:
                target = _path(paths["inputs"], name)
                for parent in reversed(target.parents):
                    if parent.is_relative_to(paths["inputs"]) and not parent.exists():
                        mkdir(parent)
                data = intake._hf_read(repo, revision, member, role=role, token=token,
                    limit=min(spec["size"] or originals.MAX_REFERENCE_BYTES, remaining), deadline=deadline)
                actual = _identity(data)
                _same("original byte identity", actual["sha256"], spec["sha256"])
                _require(0 < actual["size"] <= remaining and (spec["size"] is None or actual["size"] == spec["size"]),
                         "original_input_size_bound")
                check()
                _write_no_clobber(target, data, parent_fd=descriptor(target.parent))
                remaining -= len(data)
        token = None
        marker = registration.prepare_observation_handoff(context["plan"], **_common(context),
            run_id=context["cell"]["run_id"], task_id=context["cell"]["task_id"], destination=paths["preparation"])
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
                         paths=[prefix], token=token) == [], "observation_already_claimed_or_retained")
                receipt["returned_commit"] = _commit(api, token, deadline, cell=context["cell"], parent=parent,
                    files={claim_path: _encoded(claim)}, control_path=claim_path, control=claim, cache=cache)
                receipt["outcome"] = "acknowledged"
        except (Exception, KeyboardInterrupt):
            _write(root / "claim-receipt.json", receipt)
            raise FirstCodexCIRefused("claim_unconfirmed_permanently_reserved") from None
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
    """Reserve once, remove storage tokens and call the accepted native route."""
    paths, reserved, stage = _paths(context), False, "claim_admission"
    try:
        with ExitStack() as sources:
            marker, receipt = _admission(context, sources)
            stage = "execution_consumption"
            _require(not any(os.path.lexists(paths["root"] / name) for name in
                             ("execution-reserved.json", "execution-receipt.json")), "execution_already_consumed")
            stage = "direction_binding"
            direction, expected = _direction(context, marker)
            stage = "execution_reservation"
            _write(paths["root"] / "execution-reserved.json", {"claim_commit": receipt["returned_commit"],
                   "observation": marker["observation"], "outcome": "uncertain_until_returned"})
            reserved, stage = True, "execution_source_reread"
        for key in shared.TOKEN_KEYS:
            os.environ.pop(key, None)
        os.environ["HF_HUB_OFFLINE"] = os.environ["HF_DATASETS_OFFLINE"] = "1"
        stage = "observation_callable"
        returned = observation.run_codex_observation(context["plan"], **_common(context),
            observation=ObservationIdentity(**marker["observation"]), direction_path=paths["direction"],
            expected_direction_sha256=_identity(_bytes(direction))["sha256"],
            expected_host_sha256=context["host"]["instance_sha256"], preparation_directory=paths["preparation"],
            expected_preparation_identity=expected, expected_step0_identity=context["request"]["step0"]["identity"],
            observation_directory=paths["observation"], destination=paths["destination"])
        result = {"outcome": "returned", "returned": returned}
        stage = "execution_receipt"
        _write(paths["root"] / "execution-receipt.json", result)
        return result
    except (Exception, KeyboardInterrupt) as error:
        if reserved and stage != "execution_receipt":
            try:
                failure = shared._execution_failure(stage, error)
                shared._check_execution_failure(failure)
                _write(paths["root"] / "execution-receipt.json", failure)
                shared._emit_execution_failure(failure, format_version=shared.CODEX_FAILURE_EVENT_VERSION)
            except (Exception, KeyboardInterrupt):
                pass  # No receipt retry, deadline extension or invented result.
        raise FirstCodexCIRefused("execution_refused_or_uncertain") from None


def _result_snapshot(context: dict, marker: dict):
    """Validate native capture directly; never reinterpret it as a V2 result."""
    paths = _paths(context)
    receipt_path = paths["root"] / "execution-receipt.json"
    receipt = _read(receipt_path) if receipt_path.exists() else None
    if receipt is None:
        return None, {}, None, None
    if receipt.get("outcome") == "refused_or_uncertain":
        shared._check_execution_failure(receipt)
        return None, {}, receipt, None
    _require(set(receipt) == {"outcome", "returned"} and receipt["outcome"] == "returned", "execution_receipt_schema")
    returned = receipt["returned"]
    _same("returned observation", returned["observation"], marker["observation"])
    result_path = paths["destination"] / observation.RESULT
    _same("returned canonical path", returned["result_path"], str(result_path))
    _require(0 < returned["result_identity"]["size"] <= storage.MAX_RECORD_BYTES, "result_size_bound")
    data = _read_bytes(result_path, **returned["result_identity"])
    payload = json.loads(data, object_pairs_hook=_json_object)
    _require(data == _bytes(payload), "canonical_native_result_bytes_required")
    _same("canonical result semantics", canonicalize_inference_payload(payload), payload)
    fingerprint = validate_inference_result_fingerprint(payload)
    _same("returned result fingerprint", fingerprint, returned["result_fingerprint"])
    for name, expected in {"experiment_id": context["cell"]["run_id"], "condition": "codex", "execution_mode": "codex_foundry",
                           "model": context["plan"]["shared"]["model"]["deployment"],
                           "source": context["plan"]["shared"]["dataset"]["repo_id"]}.items():
        _same("result " + name, payload[name], expected)
    rows, control = payload["results"], payload["time_budget_observation"]
    validate_step2_progress_results(rows, schema_version=STEP2_PROGRESS_SCHEMA)
    _same("single selected result", [row["task_id"] for row in rows], [context["cell"]["task_id"]])
    row = rows[0]
    _require(row["status"] in ("success", "error"), "terminal_result_required")
    _same("returned status", row["status"], returned["status"])
    _same("no retry or resume", [row["retried"], row["resume_round"]], [False, None])
    _same("native usage remains unavailable", row["usage"], None)
    _same("result observation", control["identity"], marker["observation"])
    _same("result deadline policy", control["policy"], "time_budget_observation_deadline_v1")
    _same("result admission", control["admitted"], True)
    _require(control["terminal_reason"] in {"completed", "failed", "cancelled", "abandoned", TIMEOUT},
             "terminal_observation_required")
    if row["status"] == "success":
        _same("successful terminal cleanup", [row["error"], control["terminal_reason"],
              control["cleanup_complete"], control["host_reusable"]], [None, "completed", True, True])
    bound, files = _snapshot_deliverables(rows, paths["destination"] / "upload")
    _same("result deliverable bindings", bound, rows)
    direction, expected = _direction(context, marker)
    for name, value in {"preparation_identity": expected, "inputs": marker["inputs"],
                       "runtime_source": marker["runtime_source"], "frozen_grader": marker["frozen_grader"],
                       "host": context["host"], "direction_sha256": _identity(_bytes(direction))["sha256"],
                       "provider_binding": direction["provider_binding"], "paths_sha256": seal(direction["paths"]),
                       "entrypoint": observation.ENTRYPOINT, "grading_performed": False, "upload_performed": False}.items():
        _same("captured " + name, payload["observation_execution"][name], value)
    _require(len(files) <= 120 and sum(map(len, files.values())) <= storage.MAX_TOTAL_BYTES, "private_output_size_bound")
    snapshot = (data, payload, files, fingerprint)
    return snapshot, {"result/" + observation.RESULT: data,
                      **{"result/upload/" + name: value for name, value in files.items()}}, receipt, payload


def validate_envelope(value: dict, *, expected_cell: dict | None = None) -> None:
    """Bind an independently expected cell; default only to the legacy Task1 reader."""
    _same("native completion version", value["format"], ENVELOPE_VERSION)
    shared.validate_envelope({**value, "format": shared.ENVELOPE_VERSION},
                             expected_cell=CELL if expected_cell is None else expected_cell)
    _same("native completion unavailable usage", value["usage"], None)


def retain(context: dict) -> dict:
    paths = _paths(context)
    prefix, claim_path, manifest_path = shared._namespace(context["cell"])
    with ExitStack() as sources:
        marker, admission = _admission(context, sources)
        snapshot, files, execution_receipt, payload = _result_snapshot(context, marker)
        _write(paths["root"] / "retention-reserved.json", {"claim_commit": admission["returned_commit"],
               "outcome": "unresolved", "files": {name: _identity(data) for name, data in sorted(files.items())}})
        manifest = {"format": "gpt54-time-budget-first-codex-private-output-v1", "observation": marker["observation"],
            "request_identity": context["request_identity"], "claim_commit": admission["returned_commit"],
            "claim_identity": admission["claim_identity"], "execution_receipt": execution_receipt,
            "result": "unavailable_no_fabricated_study_row" if payload is None else "canonical_step2",
            "files": {name: _identity(data) for name, data in sorted(files.items())}, "grading_performed": False}
        if snapshot is not None:
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
            _objects(api, TARGET, parent, [_object(claim_path, _encoded(admission["claim"]))], token, deadline, written_at=parent)
            _require(api.get_paths_info(repo_id=TARGET, repo_type="dataset", revision=parent,
                     paths=[manifest_path, prefix + "/result"], token=token) == [], "output_already_retained")
            revision = _commit(api, token, deadline, cell=context["cell"], parent=parent,
                files={manifest_path: _encoded(manifest), **{prefix + "/" + name: data for name, data in files.items()}},
                control_path=manifest_path, control=manifest, cache=cache)
            _objects(api, TARGET, revision, [_object(claim_path, _encoded(admission["claim"]))], token, deadline, written_at=parent)
            outcome = "acknowledged"
    except (Exception, KeyboardInterrupt):
        revision = None  # No lost-response adoption, repeated CAS or new attempt.
    envelope = shared._envelope(context, admission, payload, commit=revision, outcome=outcome)
    envelope["format"] = ENVELOPE_VERSION
    validate_envelope(envelope, expected_cell=context["cell"])
    _write(paths["root"] / "completion.json", envelope)
    _require(outcome == "acknowledged", "private_retention_unconfirmed")
    return envelope


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise FirstCodexCIRefused("invalid_arguments")


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("operation", choices=("validate-request", "prepare-and-claim", "execute", "retain", "verify-envelope"))
    for name in ("reviewed-source-sha", "reviewed-source-tree", "expected-request-sha256"):
        parser.add_argument("--" + name, required=True)
    for name in ("runtime-root", "frozen-root", "state-root", "native-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    try:
        arguments = vars(parser.parse_args(argv))
        operation = arguments.pop("operation")
        logging.disable(logging.CRITICAL)
        os.umask(0o077)
        with checked_request(request_json=os.environ.get("TIME_BUDGET_CODEX_REQUEST_JSON", ""),
                             admission=operation not in ("retain", "verify-envelope"), **arguments) as context:
            if operation == "verify-envelope":
                value = _read(_paths(context)["root"] / "completion.json")
                validate_envelope(value, expected_cell=context["cell"])
                for name, expected in {"source": context["request"]["source"], "ci": context["ci"],
                                       "request_sha256": context["request_identity"]["sha256"],
                                       "host_sha256": context["host"]["instance_sha256"]}.items():
                    _same("completion " + name, value[name], expected)
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
