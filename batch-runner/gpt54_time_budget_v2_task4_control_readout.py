"""Fixed native r1 Task4 control evidence, never completion or admission authority.

Only the private head and two immutable control JSONs are read. Result files,
cleanup evidence and credentials are not copied into the companion report.
Missing or conflicting controls remain unknown; they never make a cell unspent.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import sys
from types import SimpleNamespace
from urllib.parse import parse_qsl

import codex_budget_pilot_output as storage
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_storage_metadata as metadata
from codex_ci_input_intake import _hf_environment
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_disposable_checkout import _git, _repository
from gpt54_run_config_bundle import _held_parents, _root
from gpt54_v2_grading_input import _object, _read_bytes

HELPER = "batch-runner/gpt54_time_budget_v2_task4_control_readout.py"
WORKFLOW = ".github/workflows/gpt54-time-budget-task4-control-readout.yml"
REPOSITORY, OWNER = metadata.REPOSITORY, metadata.OWNER
JOB = "control-readout"
FORMAT = "gpt54-time-budget-native-task4-control-readout-v1"
BASENAME = "time-budget-task4-control-readout.json"
SOURCE_BASENAME = "time-budget-task4-control-source"
TARGET, TARGET_SHA256 = metadata.TARGET, metadata.TARGET_SHA256
CELL = {"study_id": "gpt54_sandboxv2_codex_time_budget_v1", "run_id": "gpt54_time_budget_v1_codex_r1",
        "condition": "codex", "repeat": 1, "task_id": "3baa0009-5a60-4ae8-ae99-4955cb328ff3"}
PREFIX = "time-budget/" + CELL["study_id"] + "/" + CELL["run_id"] + "/" + CELL["task_id"]
PATHS = {"admission": PREFIX + "/admission.json", "output_manifest": PREFIX + "/output-manifest.json"}
HISTORICAL_SOURCE = {"sha": "f997b5e005bb1c49421e8e32cfa3040fa4266ae9",
                     "tree": "ea1ba7b15863ec5f3b2a21accd9859568a561ee2"}
HISTORICAL_RUN = "37651514733"
HISTORICAL_JOB_ID = "112895771026"  # Leader binding; not a field in either private control.
REQUEST_SHA256 = "a740f0d84a84342580679c3bb95e782f55b55e4fc0f9cd70d74e84f5b71c7697"
SECONDS, MAX_HTTP_REQUESTS, MAX_BYTES = 60, 3, 64 * 1024
REPORT_MAX_BYTES = 8192
SOURCE_ROLES = metadata.SOURCE_ROLES | {HELPER, WORKFLOW}
RESULT_MEMBER = "result/step2_inference_results.json"
FAILURE_STAGES = ("environment", "head", "admission", "output_manifest", "control_binding")
PATH_FIELDS = {"direction", "preparation", "runtime_root", "frozen_grader_root", "input_registration_root",
               "dataset_parquet", "reference_root", "step0_manifest", "observation_directory", "destination",
               "native_run_root", "input_source_sha", "input_registration_path"}


class ControlReadoutRefused(ValueError):
    """Only program-selected codes may leave the private read boundary."""


def _require(condition: bool, code: str = "control_schema_refused") -> None:
    if not condition:
        raise ControlReadoutRefused(code)


def _keys(value, names) -> None:
    _require(type(value) is dict and set(value) == set(names))


def _identity(data: bytes) -> dict:
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def _check_identity(value, limit: int = storage.MAX_FILE_BYTES, *, nonempty: bool = False) -> None:
    _keys(value, ("sha256", "size"))
    _require(storage._hash(value["sha256"]) and type(value["size"]) is int
             and int(nonempty) <= value["size"] <= limit)


def _path(value, *, absolute: bool) -> None:
    # Lexical checks only. Private path declarations never trigger filesystem IO.
    _require(type(value) is str and 0 < len(value) <= 4096 and "\\" not in value
             and all(ord(char) >= 32 and ord(char) != 127 for char in value))
    path = PurePosixPath(value)
    _require(path.is_absolute() is absolute and str(path) == value and ".." not in path.parts
             and not value.startswith("//") and value not in (".", "/"))


def _observation(value) -> None:
    _keys(value, set(CELL) | {"reviewed_source_sha", "reviewed_source_tree", "registration_sha256", "input_sha256"})
    _require({name: value[name] for name in CELL} == CELL and type(value["repeat"]) is int
             and value["reviewed_source_sha"] == HISTORICAL_SOURCE["sha"]
             and value["reviewed_source_tree"] == HISTORICAL_SOURCE["tree"]
             and storage._hash(value["registration_sha256"]) and storage._hash(value["input_sha256"]))


def _controls(admission: dict, manifest: dict, admission_bytes: bytes) -> dict:
    """Check producer schemas and cross-record bindings, not unrequested results."""
    _keys(admission, ("format", "observation", "source", "request_identity", "preparation_identity",
                      "input_binding_sha256", "step0_provenance", "host", "ci", "direction_identity", "paths",
                      "expected_parent", "storage", "state"))
    _require(admission["format"] == "gpt54-time-budget-first-codex-admission-v1"
             and admission["source"] == HISTORICAL_SOURCE
             and admission["state"] == "permanently_consumed_not_completion")
    _observation(admission["observation"])
    _check_identity(admission["request_identity"], 16384, nonempty=True)
    _require(admission["request_identity"]["sha256"] == REQUEST_SHA256)
    for key in ("preparation_identity", "direction_identity"):
        _check_identity(admission[key], nonempty=True)
    _require(storage._hash(admission["input_binding_sha256"]) and storage._hash(admission["expected_parent"], 40))
    _require(admission["storage"] == {"repository_name_sha256": TARGET_SHA256, "branch": "main", "prefix": PREFIX})
    ci = admission["ci"]
    _keys(ci, ("run_id", "run_number", "job", "attempt"))
    _require(ci["run_id"] == HISTORICAL_RUN and ci["job"] == "observation"
             and type(ci["attempt"]) is int and ci["attempt"] == 1
             and type(ci["run_number"]) is int and 0 < ci["run_number"] < 2**63)
    host = admission["host"]
    _keys(host, ("policy", "instance_sha256", "ci_instance_sha256", "ownership_confirmed"))
    _require(host["policy"] == "linux-boot-namespace-user-ci-instance-v1" and host["ownership_confirmed"] is False
             and all(storage._hash(host[name]) for name in ("instance_sha256", "ci_instance_sha256")))
    step0 = admission["step0_provenance"]
    _keys(step0, ("repository_name_sha256", "revision", "member", "identity"))
    _require(storage._hash(step0["repository_name_sha256"]) and storage._hash(step0["revision"], 40))
    _path(step0["member"], absolute=False)
    _check_identity(step0["identity"], nonempty=True)
    _keys(admission["paths"], PATH_FIELDS)
    for name in PATH_FIELDS - {"input_source_sha", "input_registration_path"}:
        _path(admission["paths"][name], absolute=True)
    _require(admission["paths"]["input_source_sha"] == registration.ACCEPTED_BASE_SHA
             and admission["paths"]["input_registration_path"] == registration.SOURCE_PROFILE)

    _keys(manifest, ("format", "observation", "request_identity", "claim_commit", "claim_identity",
                     "execution_receipt", "result", "files", "grading_performed"))
    _observation(manifest["observation"])
    _check_identity(manifest["request_identity"], 16384, nonempty=True)
    _check_identity(manifest["claim_identity"], MAX_BYTES, nonempty=True)
    _require(manifest["format"] == "gpt54-time-budget-first-codex-private-output-v1"
             and manifest["observation"] == admission["observation"]
             and manifest["request_identity"] == admission["request_identity"]
             and manifest["claim_identity"] == _identity(admission_bytes)
             and storage._hash(manifest["claim_commit"], 40)
             and manifest["claim_commit"] != admission["expected_parent"]
             and manifest["grading_performed"] is False)
    files, receipt = manifest["files"], manifest["execution_receipt"]
    _require(type(files) is dict and len(files) <= 121)
    for name, identity in files.items():
        _path(name, absolute=False)
        _require(name == RESULT_MEMBER or name.startswith("result/upload/"))
        _check_identity(identity)
    _require(sum(item["size"] for item in files.values()) <= storage.MAX_TOTAL_BYTES + storage.MAX_RECORD_BYTES)
    result_status = None
    if receipt is None or (type(receipt) is dict and receipt.get("outcome") == "refused_or_uncertain"):
        _require(manifest["result"] == "unavailable_no_fabricated_study_row" and files == {})
        if receipt is not None:
            _require(set(receipt) in ({"outcome", "returned"}, {"outcome", "returned", "failure"})
                     and receipt["returned"] is None)
            if "failure" in receipt:
                _keys(receipt["failure"], ("stage", "category", "reason"))
                # These private producer diagnostics are not public fields or authority.
                # Check their shape only; no exception-derived text is emitted.
                _require(all(type(value) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", value)
                             for value in receipt["failure"].values()))
    else:
        _keys(receipt, ("outcome", "returned"))
        _require(receipt["outcome"] == "returned" and manifest["result"] == "canonical_step2")
        returned = receipt["returned"]
        _keys(returned, ("result_path", "result_identity", "result_fingerprint", "status", "observation",
                        "grading_performed", "upload_performed"))
        _observation(returned["observation"])
        _check_identity(returned["result_identity"], storage.MAX_RECORD_BYTES, nonempty=True)
        _require(returned["observation"] == admission["observation"] and returned["status"] in ("success", "error")
                 and returned["grading_performed"] is False and returned["upload_performed"] is False
                 and storage._hash(returned["result_fingerprint"])
                 and returned["result_identity"] == files.get(RESULT_MEMBER)
                 and returned["result_path"] == admission["paths"]["destination"] + "/step2_inference_results.json")
        result_status = returned["status"]
    return {"claim_state": "permanently_consumed_not_completion", "declared_claim_commit": manifest["claim_commit"],
            "observed_run_number": ci["run_number"], "declared_execution_outcome": None if receipt is None else receipt["outcome"],
            "declared_result_status": result_status}


@contextmanager
def checked_source(*, runtime_root: Path, reviewed_source_sha: str, reviewed_source_tree: str):
    """Hold the accepted reader closure and actual owner/main/attempt1 identity."""
    _require(storage._hash(reviewed_source_sha, 40) and storage._hash(reviewed_source_tree, 40), "reader_source_required")
    expected = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": OWNER, "GITHUB_TRIGGERING_ACTOR": OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": JOB, "GITHUB_SHA": reviewed_source_sha,
        "CONTROL_WORKFLOW_SHA": reviewed_source_sha,
        "GITHUB_WORKFLOW_REF": REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
        "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
    }
    _require(all(os.environ.get(key) == value for key, value in expected.items()), "actions_context_refused")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    _require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None and sys.version_info[:3] == (3, 10, 12),
             "reader_runtime_identity_refused")
    root, runner_temp = _root(runtime_root), _root(Path(os.environ.get("RUNNER_TEMP", "")))
    workspace, common = _repository(Path(os.environ.get("GITHUB_WORKSPACE", "")))
    _require(str(workspace) == os.environ.get("GITHUB_WORKSPACE") and workspace.resolve() == workspace
             and (workspace / ".git").is_dir() and not (workspace / ".git").is_symlink()
             and common == workspace / ".git" and _repository(root)[1] == common
             and str(runner_temp) == os.environ.get("RUNNER_TEMP") and runner_temp.resolve() == runner_temp
             and root == runner_temp / SOURCE_BASENAME and root != workspace and str(root) == str(runtime_root)
             and root.resolve() == root and (root / ".git").is_file(), "canonical_linked_source_required")

    def checkout_identity():
        for revision, expected_sha in (("HEAD^{commit}", reviewed_source_sha), ("HEAD^{tree}", reviewed_source_tree)):
            _require(_git(workspace, "rev-parse", "--verify", revision).stdout == (expected_sha + "\n").encode(),
                     "actions_checkout_identity_changed")

    checkout_identity()
    with registration._reviewed_source(root, reviewed_source_sha, SOURCE_ROLES) as (_, tree, identities):
        _require(tree == reviewed_source_tree, "reviewed_tree_mismatch")
        for name in SOURCE_ROLES:
            if name.endswith(".py"):
                module = sys.modules[__name__] if name == HELPER else sys.modules[Path(name).stem]
                _read_bytes(Path(module.__file__), **identities[name])
        yield {"source": {"sha": reviewed_source_sha, "tree": tree},
               "ci": {"run_id": run_id, "job": JOB, "attempt": 1}}
    checkout_identity()


def _blank_control() -> dict:
    return dict.fromkeys(("claim_state", "declared_claim_commit", "observed_run_number",
                          "declared_execution_outcome", "declared_result_status"))


def _historical_binding() -> dict:
    return {"source": dict(HISTORICAL_SOURCE), "request_sha256": REQUEST_SHA256, "run_id": HISTORICAL_RUN,
            "attempt": 1, "job": "observation", "leader_job_id": HISTORICAL_JOB_ID,
            "job_id_verification": "not_serialized_in_control_records"}


def validate_report(value: dict, identity: dict) -> None:
    """Independent fixed-scope allowlist, not a legacy completion validator."""
    _keys(identity, ("source", "ci"))
    _keys(identity["source"], ("sha", "tree"))
    _keys(identity["ci"], ("run_id", "job", "attempt"))
    _require(all(storage._hash(item, 40) for item in identity["source"].values())
             and re.fullmatch(r"[1-9][0-9]{0,19}", identity["ci"]["run_id"]) is not None
             and identity["ci"]["job"] == JOB and type(identity["ci"]["attempt"]) is int
             and identity["ci"]["attempt"] == 1)
    _keys(value, ("format", "purpose", "source", "ci", "timestamp_utc", "target_identity_sha256", "prefix", "cell",
                  "historical", "verified_private", "parent_commit", "read_outcome", "failure_stage", "records",
                  "control", "terminal_reason", "cleanup_confirmed", "host_reusable", "retry_allowed",
                  "completion_authority", "admission_authority", "execution_authority", "result_contents_verified"))
    _require(value["format"] == FORMAT and value["purpose"] == "companion_evidence_only"
             and value["source"] == identity["source"] and value["ci"] == identity["ci"]
             and type(value["ci"]["attempt"]) is int and value["target_identity_sha256"] == TARGET_SHA256
             and value["prefix"] == PREFIX and value["cell"] == CELL and type(value["cell"]["repeat"]) is int
             and value["historical"] == _historical_binding() and type(value["historical"]["attempt"]) is int)
    stamp = value["timestamp_utc"]
    _require(type(stamp) is str and datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%SZ") == stamp)
    _require(all(value[key] is None for key in ("terminal_reason", "cleanup_confirmed", "host_reusable"))
             and all(value[key] is False for key in ("retry_allowed", "completion_authority", "admission_authority",
                                                    "execution_authority", "result_contents_verified")))
    _require((value["parent_commit"] is None and value["verified_private"] is None)
             or (storage._hash(value["parent_commit"], 40) and value["verified_private"] is True))
    _keys(value["records"], PATHS)
    for name, item in value["records"].items():
        _keys(item, ("path", "identity"))
        _require(item["path"] == PATHS[name])
        if value["read_outcome"] == "verified":
            _check_identity(item["identity"], MAX_BYTES, nonempty=True)
        else:
            _require(item["identity"] is None)
    _keys(value["control"], _blank_control())
    control = value["control"]
    if value["read_outcome"] == "unknown":
        _require(value["failure_stage"] in FAILURE_STAGES and control == _blank_control())
    else:
        _require(value["read_outcome"] == "verified" and value["parent_commit"] is not None
                 and value["failure_stage"] is None and control["claim_state"] == "permanently_consumed_not_completion"
                 and storage._hash(control["declared_claim_commit"], 40)
                 and type(control["observed_run_number"]) is int and 0 < control["observed_run_number"] < 2**63
                 and control["declared_execution_outcome"] in (None, "returned", "refused_or_uncertain")
                 and (control["declared_result_status"] in ("success", "error")
                      if control["declared_execution_outcome"] == "returned" else control["declared_result_status"] is None))


def _read_controls(identity: dict) -> dict:
    report = {"format": FORMAT, "purpose": "companion_evidence_only", **identity,
              "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "target_identity_sha256": TARGET_SHA256, "prefix": PREFIX, "cell": dict(CELL),
              "historical": _historical_binding(), "verified_private": None, "parent_commit": None,
              "read_outcome": "unknown", "failure_stage": "environment", "control": _blank_control(),
              "records": {name: {"path": path, "identity": None} for name, path in PATHS.items()},
              "terminal_reason": None, "cleanup_confirmed": None, "host_reusable": None,
              "retry_allowed": False, "completion_authority": False, "admission_authority": False,
              "execution_authority": False, "result_contents_verified": False}
    stage = "environment"
    try:
        _require(hashlib.sha256(TARGET.encode()).hexdigest() == TARGET_SHA256)
        token = os.environ.get("HF_TOKEN", "")
        _require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
                 "explicit_hf_token_required")
        with storage._time_bound(SECONDS) as deadline, _hf_environment(online=True):
            from huggingface_hub import constants
            from huggingface_hub.utils import _http

            _require(constants.HF_HUB_DISABLE_TELEMETRY, "sdk_telemetry_must_be_disabled")
            with storage._hf_client(token, deadline, response_bytes_limit=MAX_BYTES) as api:
                session = _http.get_session()
                session.follow_redirects = False
                session.headers["accept-encoding"] = "identity"
                attempts, parent = 0, None
                bodies, objects = {}, {}

                def request_guard(request):
                    nonlocal attempts
                    storage._remaining(deadline)
                    _require(attempts < MAX_HTTP_REQUESTS and request.method == "GET" and not request.content
                             and request.url.scheme == "https" and request.url.host == "huggingface.co"
                             and request.url.port in (None, 443) and request.url.userinfo == b"" and not request.url.fragment
                             and request.headers.get("authorization") == "Bearer " + token
                             and request.headers.get("accept-encoding") == "identity" and not request.headers.get("cookie"),
                             "fixed_read_transport_refused")
                    if attempts == 0:
                        _require(request.url.raw_path.split(b"?", 1)[0] == f"/api/datasets/{TARGET}/revision/main".encode()
                                 and sorted(parse_qsl(request.url.query.decode(), strict_parsing=True))
                                 == [("expand", "private"), ("expand", "sha")], "private_head_only")
                    else:
                        path = tuple(PATHS.values())[attempts - 1]
                        _require(parent is not None and not request.url.query
                                 and request.url.raw_path == f"/datasets/{TARGET}/raw/{parent}/{path}".encode(),
                                 "immutable_fixed_control_only")
                    attempts += 1

                def response_guard(response):
                    _require(response.status_code == 200
                             and response.headers.get("content-encoding", "").lower().strip() in ("", "identity"),
                             "control_http_refused")
                    length = response.headers.get("content-length")
                    _require(length is None or (re.fullmatch(r"[0-9]{1,10}", length) is not None
                                               and int(length) <= MAX_BYTES), "control_bytes_bound")
                    response.read()  # Existing stream wrapper enforces size/time BEFORE yielding each chunk.
                    data = response.content
                    _require(0 < len(data) <= MAX_BYTES and (length is None or len(data) == int(length)))
                    value = json.loads(data, object_pairs_hook=_object)
                    _require(type(value) is dict)
                    _canonical_json(value)  # Refuse non-finite JSON values even in unused metadata.
                    if attempts == 1:
                        _require(value.get("id") == TARGET and value.get("private") is True
                                 and storage._hash(value.get("sha"), 40))
                    else:
                        _require(data == (_canonical_json(value) + "\n").encode(), "canonical_control_required")
                    bodies[attempts], objects[attempts] = data, value

                session.event_hooks = {"request": [request_guard], "response": [response_guard]}
                stage = "head"
                head = storage._metadata(SimpleNamespace(repo_info=partial(api.repo_info, expand=["private", "sha"])),
                                         TARGET, "main", token, deadline)
                _require(head["sha"] == objects[1]["sha"])
                parent = head["sha"]
                report.update(verified_private=True, parent_commit=parent)
                for stage, path in PATHS.items():
                    session.get(f"{storage.HF_ENDPOINT}/datasets/{TARGET}/raw/{parent}/{path}",
                                headers={"authorization": "Bearer " + token}, follow_redirects=False)
                storage._remaining(deadline)
                stage = "control_binding"
                _require(attempts == MAX_HTTP_REQUESTS and set(bodies) == {1, 2, 3})
                control = _controls(objects[2], objects[3], bodies[2])
                report.update(read_outcome="verified", failure_stage=None, control=control,
                              records={name: {"path": path, "identity": _identity(bodies[index])}
                                       for index, (name, path) in enumerate(PATHS.items(), 2)})
    except (Exception, KeyboardInterrupt):
        # Never serialize exceptions, URLs, private paths/payloads, or credentials.
        # Even a verified admission alone cannot turn missing/conflicting data into absence.
        report.update(read_outcome="unknown", failure_stage=stage, control=_blank_control(),
                      records={name: {"path": path, "identity": None} for name, path in PATHS.items()})
    validate_report(report, identity)
    return report


def inspect_controls(**source) -> dict:
    with checked_source(**source) as identity:
        report = _read_controls(identity)
    return report  # Publication follows the final held-source rereads.


def _destination() -> Path:
    value = os.environ.get("RUNNER_TEMP", "")
    _require(bool(value) and Path(value).is_absolute(), "runner_temp_required")
    root = _root(Path(value))
    _require(str(root) == value and root.resolve() == root, "canonical_runner_temp_required")
    return root / BASENAME


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ControlReadoutRefused("invalid_arguments")


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("operation", choices=("validate-source", "inspect", "verify-report"))
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--reviewed-source-tree", required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    logging.disable(logging.CRITICAL)
    try:
        args = vars(parser.parse_args(argv))
        operation = args.pop("operation")
        destination = _destination()
        with _held_parents(destination.parent, (destination.name,)) as held:
            if operation == "inspect":
                _require(not destination.exists() and not destination.is_symlink(), "report_already_exists")
                report = inspect_controls(**args)
                data = _canonical_json(report).encode()
                _require(len(data) <= REPORT_MAX_BYTES)
                held()
                _write_no_clobber(destination, data)
                held()
                sys.stdout.write(data.decode() + "\n")
                return 0 if report["read_outcome"] == "verified" else 2
            with checked_source(**args) as identity:
                if operation == "verify-report":
                    _require(destination.lstat().st_size <= REPORT_MAX_BYTES, "report_bytes_bound")
                    data = _read_bytes(destination)
                    report = json.loads(data, object_pairs_hook=_object)
                    _require(data == _canonical_json(report).encode(), "canonical_report_required")
                    validate_report(report, identity)
            held()
        return 0
    except (Exception, KeyboardInterrupt):
        sys.stdout.write("task4_control_readout_refused\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
