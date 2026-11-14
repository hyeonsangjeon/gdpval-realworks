"""Scheduled capture admission to the existing, once-only frozen-F executor.

No alternate judge, config, permission switch, network intake or automatic
direction issuer. The controller's verified storage bytes are checked again;
an independently supplied, exact execution direction is still mandatory.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import http.client
import json
import os
from pathlib import Path
import re
import socket
from urllib.parse import urlencode

from core.agentic_v2_preregistration import seal
from core.result_fingerprint import inference_result_fingerprint, validate_inference_result_fingerprint
from core.runner_environment import require_execution
from core.tools import get_renderer_fingerprint
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_grading_execution as execution
import gpt54_time_budget_grading_preparation as preparation
import gpt54_time_budget_paired_readout as paired
import gpt54_time_budget_schedule as schedule
from gpt54_prepared_input_attestation import _identity
from gpt54_time_budget_serial_capture import CaptureBundle, FrozenInputQueue, decoded_arguments
from gpt54_time_budget_serial_controller import document, require, same
from gpt54_v2_grading_input import _read_bytes

HELPER = "batch-runner/gpt54_time_budget_common_grading.py"
# Existing grade-run/native-task3 image, not a new grading environment.
GRADING_IMAGE = "ghcr.io/hyeonsangjeon/gdpval-grading@sha256:0f6782c056e31e1ea1d693fc2f8f873da160b232926fa1b6cde75c24e5344a04"
SOURCE_ROLES = {HELPER, "batch-runner/gpt54_time_budget_serial_capture.py",
    "batch-runner/gpt54_time_budget_serial_controller.py", "batch-runner/gpt54_time_budget_paired_readout.py",
    "batch-runner/gpt54_time_budget_schedule.py", "batch-runner/core/runner_environment.py",
    ".github/workflows/gpt54-time-budget-native-task3-grade.yml"}
EVIDENCE = "retained_capture_and_frozen_step8_execution"


def reject_synthetic(value):
    """Reject explicit test/stub provenance, including nested metadata.

Do not search task prose for words: a deliverable may legitimately discuss
synthetic data. Absence of a marker is not evidence; source/capture/claim checks
are independently required below.
"""
    if isinstance(value, dict):
        require(not ({"fixture_evidence_kind", "synthetic", "is_fixture", "stub_grades"} & value.keys()),
                "synthetic_evidence_forbidden")
        if "evidence_kind" in value:
            kind = value["evidence_kind"]
            require(type(kind) is str and not any(word in kind.lower() for word in ("synthetic", "fixture", "stub")),
                    "synthetic_evidence_forbidden")
        for item in value.values():
            reject_synthetic(item)
    elif isinstance(value, list):
        for item in value:
            reject_synthetic(item)


class _DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect("/var/run/docker.sock")


def _docker(kind, target):
    # Summary endpoints omit Config.Env. No full inspect, credentials, login,
    # remote TCP or image pull. The pinned image need not install Docker CLI.
    resource, key = ("containers", "id") if kind == "container" else ("images", "reference")
    query = urlencode({"filters": json.dumps({key: [target]})})
    connection = _DockerConnection("localhost", timeout=10)
    try:
        connection.request("GET", f"/{resource}/json?{query}")
        response = connection.getresponse()
        require(response.status == 200, "grading_image_inspection_failed")
        data = response.read(1024 * 1024 + 1)
        require(len(data) <= 1024 * 1024, "grading_image_inspection_size")
        values = json.loads(data)
        require(type(values) is list and len(values) == 1, "grading_image_inspection_schema")
        return values[0]
    finally:
        connection.close()


def inspect_runtime():
    """Require Ubuntu24 hosted execution *inside* the existing pinned image.

    Fail closed if the job container cannot inspect its image via the Docker
    socket. These are operational observations, not remote attestation.
Never query credentials or run a benchmark/preflight on a local/NAS host.
"""
    runner = require_execution()
    require(runner["github_hosted"] and runner["os_version_id"] == "24.04", "hosted_grader_required")
    hostname = socket.gethostname()
    require(re.fullmatch(r"[0-9a-f]{12,64}", hostname) is not None, "grading_job_container_required")
    container = _docker("container", hostname)
    image_id = container["ImageID"]
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is not None, "grading_image_id_required")
    require(container["Id"].startswith(hostname) and container["State"] == "running",
            "grading_container_identity_mismatch")
    same(container["Image"], GRADING_IMAGE, "grading_image_mismatch")
    image = _docker("image", GRADING_IMAGE)
    same(image["Id"], image_id, "grading_image_id_mismatch")
    require(GRADING_IMAGE in image["RepoDigests"], "grading_image_digest_mismatch")
    renderer = get_renderer_fingerprint()
    require(renderer["libreoffice_version"] == "LibreOffice 24.2.7.2 420(Build:2)", "grading_renderer_mismatch")
    return {"runner": runner, "image": GRADING_IMAGE, "image_id": image_id,
            "container_id": container["Id"], "renderer": renderer,
            "evidence_boundary": "local_docker_and_runner_metadata_not_remote_attestation"}


class ScheduledGradingPreparation:
    """Only a currently open checked intake scope may use this handle."""
    __slots__ = ()


_INTAKES = {}


def _intake(handle):
    require(type(handle) is ScheduledGradingPreparation and handle in _INTAKES,
            "current_scheduled_intake_required")
    return _INTAKES[handle]


def checked_capture(plan, capture):
    reject_synthetic(capture)
    item = paired._selected(paired._schedule(plan), capture["binding"])
    controls = capture["controls"]
    require(len(controls) == 3, "capture_controls_required")
    for row in controls:
        _read_bytes(Path(row["path"]), **row["identity"])
    bundle = CaptureBundle(capture["storage"]["repository"], capture["storage"]["revision"],
        *(Path(row["path"]) for row in controls), decoded_arguments(capture["arguments"]))
    same(FrozenInputQueue().validate_capture(plan, item, capture["completion"], bundle), capture,
         "checked_capture_changed")
    return item, bundle.arguments


def check_arguments(handle, arguments, plan):
    state = _intake(handle)
    same(seal(plan), state["plan_sha256"], "scheduled_registration_changed")
    checked_capture(plan, state["capture"])
    for name, value in state["arguments"].items():
        actual = arguments[name]
        if name == "observation":
            same(asdict(actual), asdict(value), "scheduled_observation_changed")
        elif isinstance(value, Path):
            same(str(execution._absolute(actual)), str(value), "scheduled_path_changed")
        else:
            same(actual, value, "scheduled_argument_changed")


def execution_paths(handle):
    state = _intake(handle)
    paths = [value for value in state["arguments"].values() if isinstance(value, Path)]
    paths += [Path(row["path"]) for row in state["capture"]["controls"]]
    return state["output"], paths


def admission_binding(handle):
    state = _intake(handle)
    return {"format": "time-budget-scheduled-grading-admission-v1", "binding": state["capture"]["binding"],
            "capture_sha256": seal(state["capture"]), "capture": state["capture"],
            "runtime": state["runtime"], "evidence_kind": EVIDENCE}


def require_runtime(handle):
    same(inspect_runtime(), _intake(handle)["runtime"], "grading_runtime_changed")


def grading_origin(handle, result, result_identity, fingerprint):
    capture = _intake(handle)["capture"]
    reject_synthetic(result)
    same(result_identity, capture["completion"]["result_identity"], "grading_origin_result_mismatch")
    same(fingerprint, capture["completion"]["result_fingerprint"], "grading_origin_fingerprint_mismatch")
    additions = {"source_repo_id": capture["storage"]["repository"],
                 "source_revision": capture["storage"]["revision"],
                 "source_identity_document_sha256": seal(capture)}
    for key in additions.keys() & result.keys():
        same(result[key], additions[key], "captured_origin_mismatch")
    derived = {**result, **additions}
    derived["result_fingerprint"] = inference_result_fingerprint(derived)
    validate_inference_result_fingerprint(derived)
    return derived, {"basis": "revalidated_serial_capture_at_exact_retained_commit",
        "capture_sha256": seal(capture), **additions,
        "original_result_identity": result_identity, "original_result_fingerprint": fingerprint,
        "derived_result_identity": _identity(execution._encoded(derived)),
        "derived_result_fingerprint": derived["result_fingerprint"]}


@contextmanager
def prepare_scheduled_grading(plan, *, capture, prepared, controller_root, controller_source_sha,
                             controller_source_tree, execution_input_directory):
    """Revalidate the whole real F preparation; do not claim or call a judge."""
    item, original = checked_capture(plan, capture)
    reject_synthetic(prepared)
    same(prepared["binding"], item.binding(schedule.build_schedule(plan)), "prepared_schedule_changed")
    same(prepared["directory"], str(original["destination"]), "prepared_directory_changed")
    same(prepared["runner_image"], capture["runner_image"], "prepared_runner_changed")
    marker = document(original["destination"] / preparation.READY, prepared["marker_identity"])
    same(marker["observation"], asdict(original["observation"]), "prepared_observation_changed")
    arguments = {key: value for key, value in original.items() if key != "destination"}
    arguments.update(preparation_directory=original["destination"],
        expected_preparation_identity=prepared["marker_identity"],
        expected_observation_identity=_identity(execution._encoded(asdict(original["observation"]))),
        expected_input_binding_identity=_identity(execution._encoded(original["expected_input_binding"])),
        controller_root=execution._absolute(controller_root), expected_controller_source_sha=controller_source_sha,
        expected_controller_source_tree=controller_source_tree)
    handle = ScheduledGradingPreparation()
    output = execution._absolute(execution_input_directory)
    require(output.parent.is_dir() and not os.path.lexists(output), "new_scheduled_grading_input_required")
    _INTAKES[handle] = {"plan_sha256": seal(plan), "capture": json.loads(execution._encoded(capture)),
        "arguments": arguments, "output": output, "runtime": inspect_runtime()}
    try:
        with execution._checked_preparation(plan, {**arguments, "scheduled_preparation": handle},
                                            materialize_native=True):
            pass
        yield handle
    finally:
        _INTAKES.pop(handle, None)


def execute_scheduled_grading(plan, *, preparation_handle, direction_file, expected_direction_sha256,
                              expected_execution_context_sha256, attempt_store, destination):
    """Actual F Step8, owned process, exact direction, permanent once-only claim."""
    arguments = dict(_intake(preparation_handle)["arguments"])
    return execution._execute_observation_grading(plan, **arguments, scheduled_preparation=preparation_handle,
        direction_file=direction_file, expected_direction_sha256=expected_direction_sha256,
        expected_execution_context_sha256=expected_execution_context_sha256,
        attempt_store=attempt_store, destination=destination)


def read_independent_direction(item, binding, path):
    """Read an issuer's adjacent .sha256; never compute an approval from JSON."""
    same(binding.as_dict()["scheduled_admission"]["binding"]["observation_id"], item.observation_id,
         "direction_observation_mismatch")
    digest = _read_bytes(path.with_suffix(".sha256")).decode("ascii").strip()
    require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "independent_direction_digest_required")
    return digest


class CommonFrozenPipeline(FrozenInputQueue):
    """Production adapter. Direction supplier returns a digest, never a grade.

The supplier must read independently issued directions matching the supplied
binding; it must not mint/approve them. There is intentionally no default.
The existing controller durably records grade_intent before this method runs.
"""
    live_execution_supported = True

    def __init__(self, *, controller_root, controller_source_sha, controller_source_tree,
                 execution_root, attempt_store, directions):
        self.controller = dict(controller_root=controller_root, controller_source_sha=controller_source_sha,
                               controller_source_tree=controller_source_tree)
        self.root, self.attempt_store, self.directions = Path(execution_root), Path(attempt_store), directions

    def admit(self):
        inspect_runtime()  # No generation dispatch on an ungradeable host.

    def prepare(self, plan, item, capture):
        checked_capture(plan, capture)
        return {**super().prepare(plan, item, capture), "capture": capture}

    def grade(self, plan, item, prepared):
        prefix = self.root / f"{item.sequence:02d}"
        direction_path = prefix.with_suffix(".direction.json")
        destination = prefix.with_suffix(".execution")
        with prepare_scheduled_grading(plan, capture=prepared["capture"], prepared=prepared, **self.controller,
                                       execution_input_directory=prefix.with_suffix(".input")) as handle:
            context_sha = execution.execution_context_sha256()
            arguments = {**_intake(handle)["arguments"], "scheduled_preparation": handle,
                "attempt_store": self.attempt_store, "destination": destination, "direction_file": direction_path,
                "expected_execution_context_sha256": context_sha}
            with execution._checked_preparation(plan, arguments) as checked:
                binding = execution._execution_binding(checked, arguments)
            digest = self.directions(item, binding, direction_path)
            outcome = execute_scheduled_grading(plan, preparation_handle=handle, direction_file=direction_path,
                expected_direction_sha256=digest, expected_execution_context_sha256=context_sha,
                attempt_store=self.attempt_store, destination=destination)
            same(document(destination / execution.RESULT), outcome, "grading_receipt_changed")
            return {"observation_id": item.observation_id, "preparation_sha256": prepared["marker_identity"]["sha256"],
                "directory": str(destination), "identity": _identity(_read_bytes(destination / execution.RESULT)),
                "evidence_kind": EVIDENCE,
                "continuation_allowed": outcome["cleanup_confirmed"] is True and outcome["cancelled"] is False,
                "stop_reason": "grading_cancelled" if outcome["cancelled"] else
                               None if outcome["cleanup_confirmed"] else "grading_cleanup_unconfirmed"}

    def recheck(self, plan, rows):
        for row in rows:
            if "capture" in row:
                checked_capture(plan, row["capture"])
        self.readout(plan, rows)

    def readout(self, plan, rows):
        return paired.aggregate_observation_pairs(plan, [row["prepared"] for row in rows if "prepared" in row],
                                                   [row["grade"] for row in rows if "grade" in row])
