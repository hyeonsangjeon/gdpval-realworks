"""Model-free synthetic capture -> frozen-F input -> paired grade readout.

This deliberately has no live intake, dispatcher, grader callback or CLI. The
caller supplies local fixture bytes and stub grade files. Existing preparation
and grade validators run normally; no execution permission is issued. Published
numbers are fixture wiring evidence, never model quality or billing evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

from core.agentic_v2_preregistration import seal
from core.rubric_loader import RubricLoader
from core.time_budget_observation_deadline import ObservationIdentity, TASK_IDS
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_grading_execution as grading
import gpt54_time_budget_grading_preparation as preparation
import gpt54_time_budget_schedule as scheduling
from gpt54_time_budget_v2_observation import RUNNER_HOST_POLICY, validate_runner_image
from gpt54_prepared_input_attestation import _identity
from gpt54_run_config_bundle import _path
from gpt54_v2_grading_input import _object, _read_bytes

FORMAT = "gpt54-time-budget-fixture-paired-readout-v1"
EVIDENCE = "synthetic_fixture_not_model_quality_or_billing"


class PairedReadoutRefused(ValueError):
    """Fixed reason only. No permission to retry, regrade, or adopt a claim."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise PairedReadoutRefused(reason)


def _same(actual: object, expected: object, reason: str) -> None:
    # Canonical comparison also distinguishes bools from integer cell indices.
    _require(registration._canonical_json(actual) == registration._canonical_json(expected), reason)


def _schedule(plan: dict) -> tuple[scheduling.ScheduledObservation, ...]:
    for name in ("grading_policy", "decision_rule", "generation_budget", "native_measurements"):
        _same(plan[name], registration._policy()[name], "study_contract_changed")
    original = registration.load_registration()
    for name in ("model", "grading"):
        _same(plan["shared"][name], original["shared"][name], "study_contract_changed")
    return scheduling.build_schedule(plan)


def _selected(order: tuple, binding: dict):
    matches = [item for item in order if item.observation_id == binding.get("observation_id")]
    _require(len(matches) == 1, "observation_not_registered")
    item = matches[0]
    _same(binding, item.binding(order), "observation_binding_mismatch")
    return item


def _unique(values: list[str], reason: str) -> None:
    _require(len(values) <= scheduling.MAX_OBSERVATIONS, "observation_limit_exceeded")
    _require(len(set(values)) == len(values), reason)


def _image(payload: dict) -> dict:
    try:
        host = payload["observation_execution"]["host"]
        _require(host["policy"] == RUNNER_HOST_POLICY, "runner_image_mismatch")
        validate_runner_image(host["runner_image"])
        return host["runner_image"]
    except (KeyError, TypeError, ValueError):
        raise PairedReadoutRefused("runner_image_mismatch") from None


@dataclass(frozen=True)
class FixtureCapture:
    binding: dict
    # The existing F preparer's full, independent R/F/input/result arguments.
    arguments: dict
    evidence_kind: str = EVIDENCE


@dataclass(frozen=True)
class PreparedFixture:
    binding: dict
    directory: Path
    marker_identity: dict
    runner_image: dict
    evidence_kind: str = EVIDENCE


@dataclass(frozen=True)
class StubGrade:
    observation_id: str
    preparation_sha256: str
    path: Path
    identity: dict
    evidence_kind: str = EVIDENCE


def prepare_fixture_captures(plan: dict, captures: list[FixtureCapture]) -> tuple[PreparedFixture, ...]:
    """Prepare each available scheduled capture once, in ABBA order.

    Validate the whole supplied inventory before publishing any input. Failed
    and interrupted captures still pass through the same F input preparation.
    Existing no-clobber reservations prohibit preparing a destination twice;
    this is not a distributed live grading-attempt store.
    """
    try:
        order = _schedule(plan)
        _require(all(type(capture) is FixtureCapture and capture.evidence_kind == EVIDENCE
                     for capture in captures), "fixture_evidence_required")
        _unique([capture.binding.get("observation_id") for capture in captures], "duplicate_observation")
        selected, common_source, common_image, destinations = [], None, None, set()
        for capture in captures:
            item = _selected(order, capture.binding)
            arguments = capture.arguments
            observation = arguments["observation"]
            _require(type(observation) is ObservationIdentity, "capture_identity_required")
            _same({key: asdict(observation)[key] for key in item.cell}, item.cell, "capture_cell_mismatch")
            _same(observation.registration_sha256, seal(plan), "capture_registration_mismatch")
            source = [observation.reviewed_source_sha, observation.reviewed_source_tree]
            _same(source, common_source or source, "capture_source_mismatch")
            common_source = source
            data = _read_bytes(arguments["result_path"], **preparation._expected_file(
                arguments["expected_result_identity"]))
            payload = json.loads(data, object_pairs_hook=_object)
            _require(payload.get("fixture_evidence_kind") == EVIDENCE, "fixture_evidence_required")
            _same(payload["time_budget_observation"]["identity"], asdict(observation), "capture_identity_mismatch")
            image = _image(payload)  # From digest-bound capture bytes, not a caller label.
            _same(image, common_image or image, "runner_image_mismatch")
            common_image = image
            destination = registration._handoff_path(arguments["destination"])
            _require(destination not in destinations, "duplicate_grading_destination")
            destinations.add(destination)
            # Reuse the actual canonical-payload/fingerprint/terminal/deliverable checks.
            preparation._result(arguments["result_path"], arguments["expected_result_identity"],
                                observation, plan, arguments["deliverables_root"])
            selected.append((item, capture, image))
        prepared = []
        for item, capture, image in sorted(selected, key=lambda row: row[0].sequence):
            marker = preparation.prepare_observation_grading(plan, **capture.arguments)
            directory = capture.arguments["destination"]
            marker_data = _read_bytes(directory / preparation.READY)
            _same(json.loads(marker_data, object_pairs_hook=_object), marker, "preparation_marker_changed")
            _same(_image(json.loads(_read_bytes(directory / preparation.RESULT))), image,
                  "runner_image_mismatch")
            prepared.append(PreparedFixture(item.binding(order), directory, _identity(marker_data), image))
        return tuple(prepared)
    except PairedReadoutRefused:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise PairedReadoutRefused("capture_preparation_refused") from None


def _checked_preparation(prepared: PreparedFixture, item, plan: dict) -> dict:
    marker = json.loads(_read_bytes(prepared.directory / preparation.READY,
                                   **grading._expected(prepared.marker_identity)), object_pairs_hook=_object)
    observation = ObservationIdentity(**marker["observation"])
    _same({key: asdict(observation)[key] for key in item.cell}, item.cell, "prepared_cell_mismatch")
    _same(observation.registration_sha256, seal(plan), "capture_registration_mismatch")
    _same(marker["grading_policy"], plan["grading_policy"], "study_contract_changed")
    _same([marker["grading_attempt"], marker["launch_allowed"], marker["execution_enabled"]],
          [1, False, False], "preparation_is_not_execution_authority")
    _same(marker["grader"]["template_source_sha256"], registration.FROZEN_TEMPLATE_SHA256,
          "frozen_grader_mismatch")
    # Recheck every materialized source, input, schema and config byte before
    # consuming a stub; a stored preparation marker is not a waived hash guard.
    files = {name: _read_bytes(_path(prepared.directory, name), **identity)
             for name, identity in marker["files"].items()}
    config = json.loads(files[preparation.CONFIG], object_pairs_hook=_object)
    result = json.loads(files[preparation.RESULT], object_pairs_hook=_object)
    _require(result.get("fixture_evidence_kind") == EVIDENCE, "fixture_evidence_required")
    _same(_image(result), prepared.runner_image, "runner_image_mismatch")
    _same(result["time_budget_observation"]["identity"], marker["observation"], "capture_identity_mismatch")
    _same(_identity(files[preparation.RESULT]), marker["result_identity"], "capture_result_mismatch")
    rubric = config["rubric"]
    loader = RubricLoader(rubric["repo_id"], rubric["revision"], str(prepared.directory / preparation.CACHE))
    snapshot = prepared.directory / preparation.CACHE / "rubric_snapshots" / rubric["revision"]
    loader._validate_snapshot(snapshot)
    # Local parquet parser only: never load()/download(), even on a cold cache.
    task = loader._load_tasks_from_parquet(snapshot)[item.task_id]
    return {"marker": marker, "files": files, "config": config, "result": result,
            "rubric_item_ids": [row.rubric_item_id for row in task.rubric_items]}


def _cell_result(item, checked: dict | None, stub: StubGrade | None) -> dict:
    value = {"evidence_kind": EVIDENCE, "observation_id": item.observation_id, "sequence": item.sequence,
             "abba_position": item.abba_position, "cell": item.cell,
             "capture_status": "missing", "terminal_reason": None, "grade_status": "missing",
             "missing_reasons": [], "score_pct": None, "reported_grade": None,
             "runner_image": None, "capture_identity": None, "grade_identity": None}
    if checked is None:
        value["missing_reasons"] = ["capture_missing"]
        return value
    marker, payload = checked["marker"], checked["result"]
    control, row = payload["time_budget_observation"], payload["results"][0]
    value.update(capture_status=row["status"], terminal_reason=control["terminal_reason"],
                 runner_image=_image(payload), capture_identity=marker["result_identity"],
                 runtime_source=marker["runtime_source"], frozen_grader_source=marker["frozen_grader_source"],
                 materialized_grader_sha256=marker["grader"]["materialized_source_sha256"])
    if row["status"] != "success" or control["terminal_reason"] != "completed":
        value["missing_reasons"].append("generation_not_successful")
    if control["cleanup_complete"] is not True or control["host_reusable"] is not True:
        value["missing_reasons"].append("capture_cleanup_unconfirmed")
    if stub is None:
        value["missing_reasons"].append("grade_missing")
        return value
    data = _read_bytes(stub.path, **grading._expected(stub.identity, maximum=grading.MAX_GRADE_BYTES))
    _require(len(data) <= grading.MAX_GRADE_BYTES, "stub_grade_size_bound")
    validated, grade = grading._grade(stub.path, checked)  # Read/validate only, never execute.
    _same(_identity(validated), _identity(data), "stub_grade_changed")
    value["grade_identity"] = _identity(data)
    value["grade_status"] = grade["run_status"]
    task = grade["tasks"][0] if grade["tasks"] else None
    if task is not None:
        value["reported_grade"] = {key: task.get(key) for key in (
            "total_awarded", "total_max", "pct", "error", "score_excluded_items", "score_excluded_max")}
        value["reported_grade"]["verdicts"] = [entry["verdict"] for entry in task["items"]]
    if grade["run_status"] == "partial":
        value["missing_reasons"].append("grading_incomplete")
    if task is None or task.get("error"):
        value["missing_reasons"].append("grade_missing_or_error")
    elif any(entry["verdict"] == "judge_error" or entry.get("score_excluded") is True
             for entry in task["items"]) or task.get("score_excluded_items", 0):
        # Keep the recorded reduced denominator, but never compare its inflated
        # percentage against a fully read rubric as if coverage were equal.
        value["missing_reasons"].append("grade_coverage_incomplete")
    if task is not None:
        for key in ("total_awarded", "total_max", "pct"):
            _require(type(task[key]) in (int, float) and math.isfinite(task[key]), "grade_nonfinite")
        if task["total_max"] <= 0:
            value["missing_reasons"].append("grade_denominator_unavailable")
        if not value["missing_reasons"]:
            value["score_pct"] = task["pct"]  # A genuine zero is retained, not imputed.
    return value


def aggregate_fixture_pairs(plan: dict, prepared: tuple[PreparedFixture, ...],
                            grades: list[StubGrade]) -> dict:
    """Return all ten registered pairs. Missing values are null, never zero.

    The difference is V2 minus Codex, in percentage points. A descriptive mean
    uses only complete pairs and explicitly reports its denominator out of ten.
    Failure/outcome counts and all twenty slots are retained independently.
    """
    try:
        order = _schedule(plan)
        _require(all(type(value) is PreparedFixture and value.evidence_kind == EVIDENCE for value in prepared)
                 and all(type(value) is StubGrade and value.evidence_kind == EVIDENCE for value in grades),
                 "fixture_evidence_required")
        _unique([value.binding.get("observation_id") for value in prepared], "duplicate_observation")
        _unique([value.observation_id for value in grades], "duplicate_grade")
        prepared_by_id, checked_by_id, common = {}, {}, None
        for value in prepared:
            item = _selected(order, value.binding)
            checked = _checked_preparation(value, item, plan)
            current = {"runner_image": value.runner_image, **{name: checked["marker"][name]
                       for name in ("runtime_source", "frozen_grader_source", "config")},
                       "grader_source_sha256": checked["marker"]["grader"]["materialized_source_sha256"]}
            _same(current, common or current, "paired_environment_or_source_mismatch")
            common = current
            prepared_by_id[item.observation_id], checked_by_id[item.observation_id] = value, checked
        grades_by_id = {}
        for value in grades:
            _require(value.observation_id in {item.observation_id for item in order}, "observation_not_registered")
            _require(value.observation_id in prepared_by_id, "grade_without_capture")
            _same(value.preparation_sha256, prepared_by_id[value.observation_id].marker_identity["sha256"],
                  "grade_preparation_mismatch")
            grades_by_id[value.observation_id] = value
        observations = [_cell_result(item, checked_by_id.get(item.observation_id),
                                     grades_by_id.get(item.observation_id)) for item in order]
        by_cell = {(value["cell"]["task_id"], value["cell"]["repeat"], value["cell"]["condition"]): value
                   for value in observations}
        pairs = []
        for task in TASK_IDS:
            for repeat in (1, 2):
                left, right = (by_cell[task, repeat, condition] for condition in ("sandbox_v2", "codex"))
                complete = left["score_pct"] is not None and right["score_pct"] is not None
                pairs.append({"evidence_kind": EVIDENCE, "task_id": task, "repeat": repeat,
                              "status": "complete" if complete else "missing",
                              "sandbox_v2": left, "codex": right,
                              "score_difference_pp": left["score_pct"] - right["score_pct"] if complete else None})
        differences = [pair["score_difference_pp"] for pair in pairs if pair["status"] == "complete"]
        return {"format": FORMAT, "evidence_kind": EVIDENCE, "launch_allowed": False, "execution_enabled": False,
                "registration_sha256": seal(plan), "schedule_sha256": order[0].binding(order)["schedule_sha256"],
                "helper_sha256": _identity(_read_bytes(Path(__file__)))["sha256"],
                "expected_observations": 20, "prepared_observations": len(prepared), "stub_grades": len(grades),
                "expected_pairs": 10, "complete_pairs": len(differences), "missing_pairs": 10 - len(differences),
                "score_difference_definition": "sandbox_v2_minus_codex_percentage_points",
                "mean_difference_denominator": len(differences),
                "mean_score_difference_pp": sum(differences) / len(differences) if differences else None,
                "observations": observations, "pairs": pairs,
                "outcome_counts": {condition: {status: sum(value["cell"]["condition"] == condition
                    and value["capture_status"] == status for value in observations)
                    for status in ("success", "error", "missing")} for condition in ("sandbox_v2", "codex")},
                "measurement_boundary": "No model, judge, remote intake, actual usage or hosted-kernel proof."}
    except PairedReadoutRefused:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise PairedReadoutRefused("paired_readout_refused") from None
