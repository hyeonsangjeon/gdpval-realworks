"""Pinned private capture -> common frozen-F inputs, with a fixture-only grader.

No HF client or grader is constructed here. The approved store owns hydration
at the exact completion.output_commit. Its local bytes and original-input
arguments are rechecked here; metadata alone never becomes a gradeable capture.
The immutable live execution guard is still limited to its registered cells.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from core.time_budget_observation_deadline import ObservationIdentity
from core.agentic_v2_preregistration import seal
from codex_budget_pilot_retention import _encoded, _object as retained_object
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_grading_preparation as preparation
import gpt54_time_budget_schedule as schedule
import gpt54_time_budget_paired_readout as paired
from gpt54_prepared_input_attestation import _identity
from gpt54_v2_grading_input import _read_bytes
from gpt54_time_budget_serial_controller import ControllerRefused, document, require, same

PATH_ARGUMENTS = {"runtime_root", "frozen_grader_root", "input_registration_root", "dataset_parquet",
                  "reference_root", "result_path", "deliverables_root", "destination", "step0_manifest"}
STRING_ARGUMENTS = {"expected_reviewed_source_sha", "expected_grader_source_sha", "expected_input_source_sha",
                    "input_registration_path"}
ARGUMENTS = PATH_ARGUMENTS | STRING_ARGUMENTS | {"observation", "expected_input_binding", "expected_result_identity"}


@dataclass(frozen=True)
class CaptureBundle:
    repository: str
    revision: str
    claim: Path
    manifest: Path
    schedule_capture: Path
    arguments: dict


def encoded_arguments(arguments):
    require(set(arguments) <= ARGUMENTS and ARGUMENTS - {"step0_manifest"} <= set(arguments), "capture_arguments_schema")
    return {key: asdict(value) if key == "observation" else str(value) if key in PATH_ARGUMENTS and value is not None
            else value for key, value in arguments.items()}


def decoded_arguments(value):
    require(set(value) <= ARGUMENTS and ARGUMENTS - {"step0_manifest"} <= set(value), "capture_arguments_schema")
    return {key: ObservationIdentity(**item) if key == "observation" else Path(item)
            if key in PATH_ARGUMENTS and item is not None else item for key, item in value.items()}


class FrozenInputQueue:
    """All twenty cells can prepare F inputs; this grants no live grading authority."""
    synthetic = False
    live_execution_supported = False

    def validate_capture(self, plan, item, envelope, bundle):
        from gpt54_time_budget_v2_ci import TARGET

        require(type(bundle) is CaptureBundle, "capture_bundle_required")
        same(bundle.repository, TARGET, "capture_repository_mismatch")
        same(bundle.revision, envelope["output_commit"], "capture_revision_mismatch")
        arguments = bundle.arguments
        encoded = encoded_arguments(arguments)
        observation = arguments["observation"]
        require(type(observation) is ObservationIdentity, "capture_identity_required")
        same(observation.registration_sha256, seal(plan), "capture_registration_mismatch")
        same({key: asdict(observation)[key] for key in item.cell}, item.cell, "capture_cell_mismatch")
        same({"sha": observation.reviewed_source_sha, "tree": observation.reviewed_source_tree},
             envelope["source"], "capture_source_mismatch")
        same(arguments["expected_reviewed_source_sha"], envelope["source"]["sha"], "capture_source_mismatch")
        same(arguments["expected_result_identity"], envelope["result_identity"], "capture_digest_mismatch")
        _, payload, files, fingerprint = preparation._result(arguments["result_path"], envelope["result_identity"],
                                                             observation, plan, arguments["deliverables_root"])
        same(fingerprint, envelope["result_fingerprint"], "capture_fingerprint_mismatch")
        same(payload["time_budget_observation"]["identity"], asdict(observation), "capture_identity_mismatch")
        same(paired._image(payload), envelope["runner_image"], "capture_runner_mismatch")
        same(payload["observation_execution"]["host"]["instance_sha256"], envelope["host_sha256"], "capture_host_mismatch")
        same(payload["observation_execution"]["runtime_source"],
             {"source_sha": envelope["source"]["sha"], "source_tree": envelope["source"]["tree"]},
             "capture_runtime_source_mismatch")
        for key in ("terminal_reason", "cleanup_complete", "host_reusable"):
            same(payload["time_budget_observation"][key], envelope[key], "capture_terminal_mismatch")
        same(payload["results"][0]["status"], envelope["status"], "capture_status_mismatch")
        if self.synthetic:
            same(payload.get("fixture_evidence_kind"), paired.EVIDENCE, "fixture_capture_required")
        else:
            require("fixture_evidence_kind" not in payload, "fixture_cannot_be_live")
        claim, manifest, recorded = (document(path) for path in (bundle.claim, bundle.manifest, bundle.schedule_capture))
        suffix = "v2" if item.condition == "sandbox_v2" else "codex"
        same(claim["format"], f"gpt54-time-budget-first-{suffix}-admission-v1", "claim_format_mismatch")
        for key, expected_value in {"observation": asdict(observation), "source": envelope["source"],
                "ci": envelope["ci"], "state": "permanently_consumed_not_completion",
                "input_binding_sha256": observation.input_sha256}.items():
            same(claim[key], expected_value, "claim_binding_mismatch")
        same(claim["request_identity"]["sha256"], envelope["request_sha256"], "claim_request_mismatch")
        same(claim["host"], payload["observation_execution"]["host"], "claim_host_mismatch")
        same(manifest["format"], f"gpt54-time-budget-first-{suffix}-private-output-v1", "manifest_format_mismatch")
        same(manifest["observation"], asdict(observation), "manifest_observation_mismatch")
        same(manifest["claim_commit"], envelope["claim_commit"], "manifest_claim_mismatch")
        same(manifest["claim_identity"], _identity(_read_bytes(bundle.claim)), "manifest_claim_digest_mismatch")
        same(manifest["request_identity"]["sha256"], envelope["request_sha256"], "manifest_request_mismatch")
        same(manifest["result"], "canonical_step2", "manifest_result_unavailable")
        same(manifest["grading_performed"], False, "manifest_grading_changed")
        expected_files = {"result/step2_inference_results.json": envelope["result_identity"],
                          **{"result/upload/" + name: _identity(data) for name, data in files.items()}}
        same(manifest["files"], expected_files, "manifest_files_mismatch")
        expected = schedule.capture_record({"plan": plan, "cell": item.cell, "request": {"source": envelope["source"]}},
            {"claim": claim, "returned_commit": envelope["claim_commit"]}, manifest, payload)
        same(recorded, expected, "schedule_capture_mismatch")
        same(recorded["state"], "captured", "schedule_capture_uncertain")
        for path, key, role in ((bundle.claim, "claim", "admission.json"), (bundle.manifest, "output", "output-manifest.json")):
            require(_read_bytes(path) == _encoded(document(path)), "noncanonical_storage_bytes")
            same(recorded[key], retained_object(item.prefix + "/" + role, _read_bytes(path)), "storage_object_changed")
        return {"binding": item.binding(schedule.build_schedule(plan)), "arguments": encoded,
                "storage": {"repository": bundle.repository, "revision": bundle.revision},
                "controls": [{"path": str(path), "identity": _identity(_read_bytes(path))}
                             for path in (bundle.claim, bundle.manifest, bundle.schedule_capture)],
                "runner_image": envelope["runner_image"]}

    def _arguments(self, capture):
        for entry in capture["controls"]:
            _read_bytes(Path(entry["path"]), **entry["identity"])
        return decoded_arguments(capture["arguments"])

    def prepare(self, plan, item, capture):
        arguments = self._arguments(capture)
        marker = preparation.prepare_observation_grading(plan, **arguments)
        require(marker["launch_allowed"] is False and marker["execution_enabled"] is False,
                "preparation_is_not_authority")
        return {"binding": item.binding(schedule.build_schedule(plan)), "directory": str(arguments["destination"]),
                "marker_identity": _identity(_read_bytes(arguments["destination"] / preparation.READY)),
                "runner_image": capture["runner_image"]}

    def grade(self, *args):
        raise ControllerRefused("common_live_grading_admission_not_implemented")


class FixtureFrozenPipeline(FrozenInputQueue):
    """Existing real F preparation/validation and paired readout; explicit stub only."""
    synthetic = True

    def __init__(self, grade_stub):
        self.grade_stub = grade_stub

    @staticmethod
    def prepared(value):
        return paired.PreparedFixture(value["binding"], Path(value["directory"]), value["marker_identity"], value["runner_image"])

    @staticmethod
    def graded(value):
        return paired.StubGrade(value["observation_id"], value["preparation_sha256"], Path(value["path"]), value["identity"])

    def prepare(self, plan, item, capture):
        arguments = self._arguments(capture)
        (prepared,) = paired.prepare_fixture_captures(plan, [paired.FixtureCapture(capture["binding"], arguments)])
        return {**asdict(prepared), "directory": str(prepared.directory)}

    def grade(self, plan, item, prepared):
        value = self.prepared(prepared)
        result = self.grade_stub(value, plan)
        require(type(result) is paired.StubGrade, "explicit_stub_grade_required")
        same(result.observation_id, item.observation_id, "grade_observation_mismatch")
        same(result.preparation_sha256, value.marker_identity["sha256"], "grade_preparation_mismatch")
        # Preserve F schema, denominator, rubric and judge identity checks.
        paired.aggregate_fixture_pairs(plan, (value,), [result])
        return {**asdict(result), "path": str(result.path)}

    def recheck(self, plan, rows):
        for row in rows:
            if "capture" in row:
                arguments = self._arguments(row["capture"])
                preparation._result(arguments["result_path"], arguments["expected_result_identity"],
                    arguments["observation"], plan, arguments["deliverables_root"])
            if "prepared" in row:
                item = schedule.select(schedule.build_schedule(plan), row["binding"]["cell"])
                paired._checked_preparation(self.prepared(row["prepared"]), item, plan)
            if "grade" in row:
                grade = self.graded(row["grade"])
                _read_bytes(grade.path, **grade.identity)

    def readout(self, plan, rows):
        self.recheck(plan, rows)
        prepared = tuple(self.prepared(row["prepared"]) for row in rows if "prepared" in row)
        grades = [self.graded(row["grade"]) for row in rows if "grade" in row]
        return paired.aggregate_fixture_pairs(plan, prepared, grades)
