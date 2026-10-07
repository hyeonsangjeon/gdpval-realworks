"""Privately hydrate retained native Task3 bytes for model-free F preparation.

A digest-bound caller request supplies C, original R, completion and input
anchors. Storage supplies bytes, never authority. This callable has no workflow,
grading admission, inference publication association or execution operation.
"""

from __future__ import annotations

from contextlib import ExitStack
from functools import partial
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, quote

import codex_budget_pilot_output as storage
import codex_ci_input_intake as intake
import gpt54_time_budget_codex_ci as native
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_grading_preparation as preparation
import gpt54_time_budget_result_readout as reader
from core.agentic_v2_preregistration import seal
from core.codex_runtime_config import CREDENTIAL_ENV_NAMES
from core.inference_manifest import canonical_deliverable_path
from core.time_budget_observation_deadline import ObservationIdentity
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object, _read_bytes, _same

HELPER = "batch-runner/gpt54_time_budget_native_grading_intake.py"
REQUEST_FORMAT = "gpt54-time-budget-native-grading-intake-request-v1"
PURPOSE = "prepare_retained_native_task3_for_frozen_grading"
FORMAT = "gpt54-time-budget-native-grading-intake-v1"
READY = "native-grading-intake.json"
RESERVATION_SUFFIX = ".native-grading-intake-reserved.json"
CELL = {**native.CELL, "task_id": "2ea2e5b5-257f-42e6-a7dc-93763f28b19d"}
DELIVERABLES = {"count": 2, "bytes": 408601}
SECONDS = 60
SOURCE_ROLES = reader.SOURCE_ROLES | {
    HELPER, preparation.HELPER, "batch-runner/gpt54_run_input_bundle.py",
    "batch-runner/gpt54_run_config_bundle.py", "batch-runner/gpt54_v2_grading_input.py",
    "batch-runner/gpt54_prepared_input_attestation.py", "batch-runner/gpt54_comparison_preflight.py",
    "batch-runner/gpt54_disposable_checkout.py",
}
PATH_KEYS = {"controller_root", "runtime_root", "frozen_root", "input_registration_root",
             "dataset_parquet", "reference_root", "step0_manifest", "hydration_root", "destination"}
OTHER_CREDENTIALS = (set(CREDENTIAL_ENV_NAMES) | set(native.shared.TOKEN_KEYS) | {
    "CODEX_API_KEY", "AZURE_FEDERATED_TOKEN_FILE", "IDENTITY_HEADER",
}) - {"HF_TOKEN"}


class NativeGradingIntakeRefused(ValueError):
    """Static refusal; keep every reservation/partial file, never adopt or retry."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise NativeGradingIntakeRefused(reason)


def _fresh(paths: dict) -> None:
    for name, suffix in (("hydration_root", RESERVATION_SUFFIX),
                         ("destination", preparation.RESERVATION_SUFFIX)):
        target = paths[name]
        _require(not os.path.lexists(target)
                 and not os.path.lexists(target.with_name(target.name + suffix)),
                 "destination_or_reservation_exists")
        _require(target.parent.is_dir(), "private_parent_required")


def _checked_request(request_json: str, expected_request_sha256: str, sources: ExitStack):
    data = request_json.encode("utf-8")
    _require(0 < len(data) <= native.shared.MAX_REQUEST_BYTES and storage._hash(expected_request_sha256)
             and _identity(data)["sha256"] == expected_request_sha256, "independent_request_digest_required")
    request = json.loads(data, object_pairs_hook=_object)
    reader._keys(request, {"format", "purpose", "controller", "completion", "cell", "registration_sha256",
                           "frozen_source", "input_registration", "dataset_sha256", "step0", "deliverables", "paths"})
    _same("intake purpose", [request["format"], request["purpose"]], [REQUEST_FORMAT, PURPOSE])
    _same("fixed native Task3", request["cell"], CELL)
    _same("independent declared totals", request["deliverables"], DELIVERABLES)
    completion = request["completion"]
    native.validate_envelope(completion, expected_cell=CELL)
    _require(completion["retention"] == "acknowledged" and completion["status"] == "success",
             "acknowledged_successful_native_result_required")
    reader._keys(request["controller"], {"sha", "tree"})
    _require(all(storage._hash(value, 40) for value in request["controller"].values()),
             "controller_commit_and_tree_required")
    _same("frozen F", request["frozen_source"], {
        "sha": registration.ACCEPTED_BASE_SHA, "tree": registration.ACCEPTED_BASE_TREE})
    _same("original input registration", request["input_registration"], {
        **request["frozen_source"], "path": registration.SOURCE_PROFILE})
    reader._keys(request["paths"], PATH_KEYS)
    paths = {}
    for name, value in request["paths"].items():
        _require(type(value) is str, "explicit_local_paths_required")
        paths[name] = registration._handoff_path(Path(value))
        _require(str(paths[name]) == value, "canonical_local_paths_required")
    _require(paths["controller_root"] != paths["runtime_root"], "distinct_C_and_R_roots_required")
    targets = [paths["hydration_root"], paths["destination"]]
    targets += [targets[0].with_name(targets[0].name + RESERVATION_SUFFIX),
                targets[1].with_name(targets[1].name + preparation.RESERVATION_SUFFIX)]
    for index, target in enumerate(targets):
        for other in targets[index + 1:] + [paths[name] for name in PATH_KEYS - {"hydration_root", "destination"}]:
            _require(not target.is_relative_to(other) and not other.is_relative_to(target), "local_path_overlap")
    _fresh(paths)
    for name in ("hydration_root", "destination"):
        sources.enter_context(_held_parents(paths[name].parent, (paths[name].name,)))
    controller = request["controller"]
    _, tree, files = sources.enter_context(registration._reviewed_source(
        paths["controller_root"], controller["sha"], SOURCE_ROLES))
    _same("controller tree", tree, controller["tree"])
    # C supplies these statically imported implementations, not old R code.
    local = Path(__file__).resolve().parents[1]
    for role in SOURCE_ROLES:
        if role.endswith(".py"):
            _read_bytes(local / role, **files[role])
    registration._require_running_observation_sources(paths["controller_root"])
    plan = reader._result_registration(paths["runtime_root"], completion["source"])
    _same("original R registration", seal(plan), request["registration_sha256"])
    _same("original dataset", seal(plan["shared"]["dataset"]), request["dataset_sha256"])
    arguments = {
        "runtime_root": paths["runtime_root"], "expected_reviewed_source_sha": completion["source"]["sha"],
        "frozen_grader_root": paths["frozen_root"], "expected_grader_source_sha": request["frozen_source"]["sha"],
        "input_registration_root": paths["input_registration_root"],
        "expected_input_source_sha": request["input_registration"]["sha"],
        "input_registration_path": registration.SOURCE_PROFILE, "dataset_parquet": paths["dataset_parquet"],
        "reference_root": paths["reference_root"], "step0_manifest": paths["step0_manifest"],
    }
    marker, _, _ = registration._observation_handoff_data(plan, sources=sources, **arguments,
        run_id=CELL["run_id"], task_id=CELL["task_id"], destination=paths["hydration_root"] / "unpublished-handoff")
    _same("reconstructed R", marker["runtime_source"], {
        "source_sha": completion["source"]["sha"], "source_tree": completion["source"]["tree"]})
    _same("input registration tree", marker["inputs"]["registration"]["source_tree"],
          request["input_registration"]["tree"])
    step0, _ = native._input_contract(plan, paths["frozen_root"])
    _same("original full Step0 provenance", request["step0"], step0)
    _same("actual whole Step0", marker["inputs"]["step0_manifest"], step0["identity"])
    return request, paths, plan, marker, arguments, _identity(data)


def _hydrate(request: dict, plan: dict, marker: dict, token: str, publish):
    """Four ordered GETs at one immutable revision; file routes start sealed."""
    import httpx
    from huggingface_hub import constants
    from huggingface_hub.utils import _http

    completion = request["completion"]
    revision = completion["output_commit"]
    prefix, _, _ = native.shared._namespace(CELL)
    result_member = prefix + "/result/" + native.observation.RESULT
    target = reader.metadata.TARGET
    base = f"/datasets/{target}/raw/{revision}/"
    routes = [f"/api/datasets/{target}/revision/{revision}", base + result_member]
    limits = [storage.MAX_MANIFEST_BYTES, completion["result_identity"]["size"]]
    context = {"request": {**request, "purpose": reader.NATIVE_PURPOSE}, "plan": plan}
    with storage._time_bound(SECONDS) as deadline, intake._hf_environment(online=True):
        _require(constants.HF_HUB_DISABLE_TELEMETRY, "telemetry_must_be_disabled")
        with storage._hf_client(token, deadline, response_bytes_limit=max(*limits, DELIVERABLES["bytes"])) as api:
            session, attempts = _http.get_session(), 0
            session.follow_redirects = False
            session.headers["Accept-Encoding"] = "identity"

            class LimitedStream(httpx.SyncByteStream):
                def __init__(self, stream, limit):
                    self.stream, self.limit = stream, limit

                def __iter__(self):
                    size = 0
                    for chunk in self.stream:
                        storage._remaining(deadline)
                        size += len(chunk)
                        _require(size <= self.limit, "response_size_bound")
                        yield chunk

                def close(self):
                    self.stream.close()

            def request_guard(outgoing):
                nonlocal attempts
                storage._remaining(deadline)
                _require(attempts < len(routes) <= 4 and outgoing.method == "GET"
                         and outgoing.url.scheme == "https" and outgoing.url.host == "huggingface.co"
                         and outgoing.url.port in (None, 443) and outgoing.url.userinfo == b""
                         and not outgoing.content and outgoing.url.path == routes[attempts]
                         and outgoing.headers.get("authorization") == "Bearer " + token
                         and outgoing.headers.get("accept-encoding") == "identity", "bounded_read_target_required")
                _require((parse_qs(outgoing.url.query.decode()) == {"expand": ["private", "sha"]})
                         if attempts == 0 else not outgoing.url.query, "bounded_read_query_required")
                attempts += 1

            def response_guard(response):
                _require(response.status_code == 200
                         and response.headers.get("content-encoding") in (None, "identity"), "encoded_or_failed_response")
                response.stream = LimitedStream(response.stream, limits[attempts - 1])

            session.event_hooks = {"request": [request_guard], "response": [response_guard]}
            found = storage._metadata(SimpleNamespace(repo_info=partial(api.repo_info, expand=["private", "sha"])),
                                      target, revision, token, deadline)
            _same("immutable private output", found["sha"], revision)

            def read(member, identity):
                with session.stream("GET", storage.HF_ENDPOINT + base + quote(member, safe="/"),
                                    headers={"authorization": "Bearer " + token, "Accept-Encoding": "identity"}) as response:
                    data = response.read()
                storage._remaining(deadline)
                _same("retained member identity", _identity(data), identity)
                _require(token.encode() not in data, "credential_in_retained_bytes")
                return data

            data = read(result_member, completion["result_identity"])
            reader.project_result(data, context)
            payload = json.loads(data, object_pairs_hook=_object)
            _same("independent reconstructed observation", payload["time_budget_observation"]["identity"], marker["observation"])
            _same("independent reconstructed inputs", payload["observation_execution"]["inputs"], marker["inputs"])
            records = payload["results"][0]["deliverable_file_records"]
            _same("independently expected content totals", {"count": len(records), "bytes": sum(r["size"] for r in records)},
                  request["deliverables"])
            names = [canonical_deliverable_path(CELL["task_id"], r["path"]) for r in records]
            _require(len(set(names)) == 2 and all(0 <= r["size"] <= storage.MAX_FILE_BYTES for r in records)
                     and DELIVERABLES["bytes"] <= storage.MAX_TOTAL_BYTES, "deliverable_bounds_refused")
            members = [prefix + "/result/upload/" + name for name in names]
            for member in members:
                _require(intake._hf_path_bytes(quote(member, safe="/")) == member.encode(), "retained_member_encoding_refused")
            routes.extend(base + member for member in members)
            limits.extend(r["size"] for r in records)
            publish(native.observation.RESULT, data)
            for member, record in zip(members, records, strict=True):
                data = read(member, {key: record[key] for key in ("sha256", "size")})
                publish("upload/" + record["path"], data)
            storage._remaining(deadline)
            _require(attempts == 4, "four_read_operations_required")


def prepare_retained_native_task3_grading(*, request_json: str, expected_request_sha256: str) -> dict:
    """Use explicit request paths/anchors and the sole in-memory HF_TOKEN.

    This is a callable, not a live authorization or grading executor. The caller
    must supply genuine local originals and an independently approved request
    digest. Only a safe content-verification summary is returned. Private
    hydration and F preparation remain separate fresh directories; failures
    retain partial state and cannot be retried into either directory.
    """
    try:
        _require(not any(os.environ.get(key) for key in OTHER_CREDENTIALS), "unexpected_credential_environment")
        token = os.environ.get("HF_TOKEN", "")
        _require(bool(token) and token.strip() == token and not any(ord(c) < 33 or ord(c) > 126 for c in token),
                 "explicit_hf_token_required")
        _require(token not in request_json, "credential_in_request")
        with intake._hf_environment(online=False), ExitStack() as sources:
            request, paths, plan, marker, arguments, request_identity = _checked_request(
                request_json, expected_request_sha256, sources)
            output = paths["hydration_root"]
            reservation = output.with_name(output.name + RESERVATION_SUFFIX)
            reserved = reader._bytes({"format": FORMAT, "request_identity": request_identity,
                                      "output_commit": request["completion"]["output_commit"], "cell": CELL})
            with _publication_parents(output.parent) as (check, mkdir, descriptor):
                _fresh(paths)
                _write_no_clobber(reservation, reserved, parent_fd=descriptor(output.parent))
                mkdir(output)
                directories, files = set(), {}

                def publish(role, data):
                    path = _path(output, role)
                    for parent in reversed(path.parents):
                        if parent != output and parent.is_relative_to(output) and parent not in directories:
                            mkdir(parent)
                            directories.add(parent)
                    _write_no_clobber(path, data, parent_fd=descriptor(path.parent))
                    files[role] = data

                _hydrate(request, plan, marker, token, publish)
                token = None  # Neither argument nor environment supplies credentials to the preparer.
                prepared = preparation.prepare_observation_grading(plan, **arguments,
                    observation=ObservationIdentity(**marker["observation"]), expected_input_binding=marker["inputs"],
                    result_path=output / native.observation.RESULT,
                    expected_result_identity=request["completion"]["result_identity"], deliverables_root=output / "upload",
                    destination=paths["destination"])
                prepared_identity = _identity(reader._bytes(prepared))
                _read_bytes(paths["destination"] / preparation.READY, **prepared_identity)
                _read_bytes(reservation, **_identity(reserved))
                sources.close()  # Source/input rereads precede this adapter's ready publication.
                preparation._members(output, files, directories)
                summary = {
                    "format": FORMAT, "status": "prepared", "cell": CELL, "controller": request["controller"],
                    "observation_source": request["completion"]["source"], "frozen_source": request["frozen_source"],
                    "registration_sha256": request["registration_sha256"], "request_identity": request_identity,
                    "execution_request_sha256": request["completion"]["request_sha256"],
                    "output_commit": request["completion"]["output_commit"], "claim_commit": request["completion"]["claim_commit"],
                    "result_identity": request["completion"]["result_identity"],
                    "result_fingerprint": request["completion"]["result_fingerprint"],
                    "input_binding_sha256": marker["observation"]["input_sha256"],
                    "deliverables": {"verified_count": 2, "verified_bytes": 408601,
                                     "basis": "full_contents_verified_against_authenticated_result"},
                    "preparation_identity": prepared_identity,
                    "materialized_grader_source_sha256": prepared["grader"]["materialized_source_sha256"],
                    "launch_allowed": False, "execution_enabled": False, "grading_performed": False,
                }
                check()
                _write_no_clobber(output / READY, reader._bytes(summary), parent_fd=descriptor(output))
                return summary
    except NativeGradingIntakeRefused:
        raise
    except (Exception, KeyboardInterrupt):
        raise NativeGradingIntakeRefused("native_grading_intake_refused") from None
