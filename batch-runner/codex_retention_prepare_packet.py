"""Prepare one registered retention cell locally; never admit or launch it.

The caller supplies an existing five-task prepared checkout, the original
parquet/reference root and the full canonical schema4 manifest. None is found,
downloaded, reconstructed or edited here. Only a verified selected task row is
copied; reference payloads remain in the verified original root, not staged for
execution. No publication generation, deadline or inference slot is allocated.

Output must be a NEW directory under this source checkout's existing
batch-runner/workspace directory, disjoint from every input. The real grader
fingerprint binds the emitted config's repository-relative path as well as its
bytes and source closure. Moving the packet changes that identity. The packet
does not make a separately materialized runtime checkout or authorize a grader.
An interrupted output is retained and must never be overwritten or adopted.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import codex_retention_diagnostic as registration
from core.agentic_v2_manifest_binding import bind_stage
from core.agentic_v2_preregistration import seal
from core.execution_envelope_tasks import catalog_sha256, load_task_catalog, select_advance_check_tasks
from core.experiment_config import ExperimentConfig
from core.inference_manifest import _assert_no_symlink_ancestors
from core.source_identity import source_task_projection_sha256
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_codex_input_capture import CONFIG_PATH, PREPARED_PATH
from gpt54_comparison_preflight import _canonical_json, load_plan
from gpt54_prepared_input_attestation import (
    _SourceSnapshot, _check_prepared, _dataset_tasks, _identity, _json_object,
    _reference_snapshot,
)
from gpt54_run_config_bundle import _held_parents
from gpt54_run_input_bundle import _file_identities, _step0_bytes
from gpt54_v2_grading_input import _read_bytes
from step8_grade import compute_grader_source_hash, validate_grading_config

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_SCOPE = ROOT / "batch-runner/workspace"
PREPARER = "batch-runner/codex_retention_prepare_packet.py"
SOURCE_PATHS = (
    PREPARER,
    "batch-runner/ghcp_vm_input_bundle.py",
    "batch-runner/gpt54_prepared_input_attestation.py",
    "batch-runner/gpt54_run_input_bundle.py",
    "batch-runner/gpt54_run_config_bundle.py",
    "batch-runner/gpt54_codex_input_capture.py",
    "batch-runner/gpt54_v2_grading_input.py",
)
ORIGINAL_INPUT_ROLES_SHA256 = "40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38"
INFERENCE = "inference-config.json"
GRADER = "grader-config.json"
TASK = "selected-task.json"
PACKET = "preparation.json"
MEMBERS = (INFERENCE, GRADER, TASK, PACKET)


class RetentionPreparationRefused(ValueError):
    """A structural refusal code, without input contents or private paths."""


@dataclass(frozen=True)
class PreparedInputs:
    prepared_root: Path
    dataset_parquet: Path
    reference_root: Path
    step0_manifest: Path


def _same(reason: str, actual, expected) -> None:
    equal = (actual == expected if type(actual) is bytes and type(expected) is bytes
             else _canonical_json(actual) == _canonical_json(expected))
    if not equal:
        raise RetentionPreparationRefused(reason)


def _path(value: Path) -> Path:
    path = Path(value)
    if ".." in path.parts:
        raise RetentionPreparationRefused("parent_traversal_refused")
    path = Path(os.path.abspath(path))
    try:
        _assert_no_symlink_ancestors(path)
    except (OSError, ValueError) as error:
        raise RetentionPreparationRefused(f"unsafe_path:{type(error).__name__}") from None
    return path


def _read(path: Path, role: str, **identity) -> bytes:
    try:
        return _read_bytes(_path(path), **identity)
    except (OSError, ValueError) as error:
        raise RetentionPreparationRefused(f"{role}_bytes_refused:{type(error).__name__}") from None


def source_identity() -> dict:
    """Actual preparer/helper bytes, not a claim of review or launch approval.

    The unchanged plan separately binds compiler/runtime pins and the entire
    core/grader closure. These are the additional preparation entrypoints.
    """
    files = {name: _identity(_read(ROOT / name, "preparer_source")) for name in SOURCE_PATHS}
    return {"files": files, "sha256": seal(files), "reviewed": False}


def _inputs(plan: dict, sources: PreparedInputs) -> tuple[dict, list[dict]]:
    """Reuse the real byte, source, schema4 and prepared-projection validators."""
    if type(sources) is not PreparedInputs:
        raise RetentionPreparationRefused("explicit_prepared_inputs_required")
    original = load_plan(ROOT / registration.ORIGINAL_PROFILE)["shared"]["dataset"]
    catalog = load_task_catalog(ROOT / registration.CATALOG)
    digest = catalog_sha256(ROOT / registration.CATALOG)
    task_ids = select_advance_check_tasks(catalog, catalog_fingerprint=digest).task_ids
    _same("original_five_task_order_mismatch", list(task_ids), [row["task_id"] for row in original["tasks"]])
    _same("original_dataset_revision_mismatch", original["revision"], plan["inputs"]["revision"])
    _same("original_catalog_mismatch", digest, plan["inputs"]["catalog_sha256"])
    parquet = _read(sources.dataset_parquet, "original_parquet", sha256=plan["inputs"]["parquet_sha256"])
    projections, needs = _dataset_tasks(parquet, task_ids)
    bound = bind_stage(original["cohort"], dataset_tasks=[SimpleNamespace(**row) for row in projections],
                       catalog=catalog, catalog_digest=digest)
    versions = dict(original["input_file_versions"])
    _same("original_parquet_version_mismatch", versions.pop(original["repo_id"] + "@" + original["revision"]),
          _identity(parquet)["sha256"])
    reference_names = [name for row in projections for name in row["reference_files"]]
    _same("original_reference_set_mismatch", sorted(reference_names), sorted(versions))
    try:
        references = _reference_snapshot(_path(sources.reference_root), versions)
    except (OSError, ValueError) as error:
        raise RetentionPreparationRefused(f"original_reference_bytes_refused:{type(error).__name__}") from None
    projected = [{
        "projection": row, "source_projection_sha256": source_task_projection_sha256(**row),
        "reference_file_records": [{"path": name, **references[name]} for name in row["reference_files"]],
    } for row in projections]
    # This is an input-only snapshot, not a manufactured historical dispatch or
    # attestation. The canonical Step0 helper consumes these real projections.
    snapshot = _SourceSnapshot({"needs_files_policy": "deliverable_only",
                                "dataset": {"parquet": _identity(parquet)}},
                               projected, projections, references, needs, bound)
    try:
        step0 = _step0_bytes(_path(sources.step0_manifest), snapshot)
    except (OSError, ValueError) as error:
        raise RetentionPreparationRefused(f"original_schema4_refused:{type(error).__name__}") from None
    identities = _file_identities(snapshot, step0)
    _same("original_input_roles_mismatch", seal(identities), ORIGINAL_INPUT_ROLES_SHA256)

    config_bytes = _read(sources.prepared_root / CONFIG_PATH, "original_prepared_config")
    config = _json_object(config_bytes)
    errors = ExperimentConfig.from_dict(config).validate()
    if errors:
        raise RetentionPreparationRefused("original_prepared_config_invalid")
    prepared_bytes = _read(sources.prepared_root / PREPARED_PATH, "original_prepared_tasks")
    # Only these two fields are consumed by the existing projection checker;
    # this adapter carries no run commands, source approval or ABBA attestation.
    projection_recipe = SimpleNamespace(config_json=_canonical_json(config), task_ids=task_ids)
    try:
        consumer = _check_prepared(prepared_bytes, projection_recipe, projections, references, needs)
    except (ValueError, KeyError, TypeError) as error:
        raise RetentionPreparationRefused(f"original_prepared_projection_refused:{type(error).__name__}") from None
    for selected in plan["inputs"]["tasks"]:
        row = next(row for row in projections if row["task_id"] == selected["task_id"])
        _same("registered_task_prompt_mismatch", hashlib.sha256(row["prompt"].encode()).hexdigest(), selected["prompt_sha256"])
        _same("registered_task_references_mismatch", {name: references[name]["sha256"] for name in row["reference_files"]},
              selected["reference_files"])
    return {
        "verification": "original_bytes_and_five_task_prepared_projection",
        "dataset_revision": original["revision"], "task_ids": list(task_ids),
        "original_files": identities, "original_input_roles_sha256": seal(identities),
        "prepared_file": _identity(prepared_bytes), "prepared_fingerprint": consumer["prepared_fingerprint"],
        "original_config_file": _identity(config_bytes),
    }, consumer["tasks"]


def _context(plan: dict | None, cell_id: str, sources: PreparedInputs,
             expected_preparer_sha256: str) -> tuple[dict, dict, dict, dict, dict]:
    plan = registration.compile_plan() if plan is None else registration.validate_plan(plan)
    selected = [row for row in plan["cells"] if row["cell_id"] == cell_id]
    if type(cell_id) is not str or len(selected) != 1:
        raise RetentionPreparationRefused("exact_registered_cell_required")
    source = source_identity()
    _same("preparer_source_mismatch", source["sha256"], expected_preparer_sha256)
    try:
        inputs, tasks = _inputs(plan, sources)
    except RetentionPreparationRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise RetentionPreparationRefused(f"original_inputs_refused:{type(error).__name__}") from None
    cell = selected[0]
    task = next(row for row in tasks if row["task_id"] == cell["task_id"])
    return plan, cell, source, inputs, task


def _output(output: Path, sources: PreparedInputs, *, new: bool) -> Path:
    output = _path(output)
    if output == OUTPUT_SCOPE or not output.is_relative_to(OUTPUT_SCOPE):
        raise RetentionPreparationRefused("output_outside_source_workspace")
    for path in (sources.prepared_root, sources.dataset_parquet, sources.reference_root, sources.step0_manifest):
        path = _path(path)
        if output.is_relative_to(path) or path.is_relative_to(output):
            raise RetentionPreparationRefused("output_input_overlap")
    if not output.parent.is_dir() or (new and os.path.lexists(output)):
        raise RetentionPreparationRefused("output_collision_or_missing_parent")
    if not new and not output.is_dir():
        raise RetentionPreparationRefused("output_directory_required")
    return output


def _files(cell: dict, plan: dict, task: dict) -> dict[str, bytes]:
    return {INFERENCE: _canonical_json(cell["config"]).encode(),
            GRADER: _canonical_json(plan["grading"]["generated_config"]).encode(),
            TASK: _canonical_json(task).encode()}


def _packet(output: Path, context: tuple) -> dict:
    plan, cell, source, inputs, task = context
    files = _files(cell, plan, task)
    for name, expected in files.items():
        _same("emitted_config_or_task_bytes_mismatch", _read(output / name, "emitted_member"), expected)
    grader = _json_object(_read(output / GRADER, "materialized_grader_config"))
    checked = json.loads(_canonical_json(grader))
    for key in ("template", "tool_template"):
        if key in checked["prompt"]:
            checked["prompt"][key] = str(ROOT / "batch-runner" / checked["prompt"][key])
    validate_grading_config(checked)
    actual_grader = compute_grader_source_hash(output / GRADER, grader, batch_root=ROOT / "batch-runner")
    return {
        "packet_version": "codex-retention-preparation-v1", "cell_id": cell["cell_id"],
        "campaign_id": plan["campaign_id"], "plan_sha256": seal(plan),
        "registration_sha256": plan["registration_canonical_sha256"],
        "runtime_baseline": plan["runtime_baseline"], "compiler_source": plan["source_pins"]["compiler"],
        "preparer_source": source, "input_verification": inputs,
        "selected_task": {"task_id": task["task_id"], "sha256": seal(task),
                          "source_projection_sha256": task["source_projection_sha256"]},
        "files": {name: _identity(data) for name, data in files.items()},
        "grading": {"template_source_sha256": plan["grading"]["template_source_sha256"],
                    "materialized_grader_source_sha256": actual_grader,
                    "materialized_config_role": (output / GRADER).relative_to(ROOT).as_posix(),
                    "grades_per_produced_result": 1, "no_result_grade": None, "grading_done": False},
        "launch_authorized": False, "commands": [], "inference_slot_reserved": False,
        "deadline_started": False, "runtime_inputs_staged": False,
        "launch_blockers": [*plan["launch_blockers"], "preparer_source_not_reviewed_or_authorized",
                            "runtime_input_staging_and_before_admission_reverification_required"],
        "evidence_boundary": "local_original_input_and_materialized_config_consistency_not_admission",
    }


def verify_packet(*, cell_id: str, sources: PreparedInputs, output: Path,
                  expected_preparer_sha256: str, plan: dict | None = None) -> dict:
    """Reverify source, original inputs and every emitted byte; never write."""
    output = _output(output, sources, new=False)
    context = _context(plan, cell_id, sources, expected_preparer_sha256)
    with _held_parents(output, MEMBERS) as check:
        _same("unexpected_packet_members", sorted(path.name for path in output.iterdir()), sorted(MEMBERS))
        expected = _packet(output, context)
        _same("packet_readback_mismatch", _read(output / PACKET, "packet"), _canonical_json(expected).encode())
        check()
        return expected


def prepare_packet(*, cell_id: str, sources: PreparedInputs, output: Path,
                   expected_preparer_sha256: str, plan: dict | None = None) -> dict:
    """Exclusive local materialization; no source authority, launch or cleanup.

    The expected preparer digest is an external byte anchor, not approval.
    All preflight refusals precede mkdir. Publication failures retain an owned
    partial directory; a marker's mere presence never substitutes for readback.
    """
    output = _output(output, sources, new=True)
    context = _context(plan, cell_id, sources, expected_preparer_sha256)
    with _publication_parents(output.parent) as (check_parent, mkdir, directory_fd):
        _output(output, sources, new=True)
        mkdir(output)
        # Use the descriptor held at exclusive creation, never a writer's
        # fresh lookup of a pathname that could now name a replacement.
        output_fd = directory_fd(output)
        with _held_parents(output, MEMBERS) as check:
            for name, data in _files(context[1], context[0], context[4]).items():
                check_parent()
                check()
                _write_no_clobber(output / name, data, parent_fd=output_fd)
            # Recheck held inputs and source after publication, before the final
            # packet. Original five-task bytes are never changed or reissued.
            fresh = _context(context[0], cell_id, sources, expected_preparer_sha256)
            _same("input_or_source_changed_during_preparation", fresh, context)
            _same("unexpected_packet_members", sorted(path.name for path in output.iterdir()),
                  sorted((INFERENCE, GRADER, TASK)))
            packet = _packet(output, fresh)
            check_parent()
            check()
            _write_no_clobber(output / PACKET, _canonical_json(packet).encode(), parent_fd=output_fd)
            _same("packet_readback_mismatch", _read(output / PACKET, "packet"), _canonical_json(packet).encode())
            _same("unexpected_packet_members", sorted(path.name for path in output.iterdir()), sorted(MEMBERS))
            check_parent()
            check()
            return packet


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RetentionPreparationRefused("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _Parser(description=__doc__)
        for name in ("prepared-root", "dataset-parquet", "reference-root", "step0-manifest", "output"):
            parser.add_argument("--" + name, required=True, type=Path)
        parser.add_argument("--cell-id", required=True)
        parser.add_argument("--expected-preparer-sha256", required=True)
        parser.add_argument("--plan", type=Path)
        parser.add_argument("--verify", action="store_true")
        args = parser.parse_args(argv)
        sources = PreparedInputs(args.prepared_root, args.dataset_parquet, args.reference_root, args.step0_manifest)
        plan = _json_object(_read(args.plan, "compiled_plan")) if args.plan else None
        packet = (verify_packet if args.verify else prepare_packet)(
            cell_id=args.cell_id, sources=sources, output=args.output,
            expected_preparer_sha256=args.expected_preparer_sha256, plan=plan,
        )
        print(_canonical_json({"prepared": True, "launch_authorized": False, "commands": [],
                               "cell_id": packet["cell_id"], "packet_sha256": seal(packet),
                               "input_roles_sha256": packet["input_verification"]["original_input_roles_sha256"],
                               "materialized_grader_source_sha256": packet["grading"]["materialized_grader_source_sha256"]}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, StopIteration) as error:
        reason = (str(error) if isinstance(error, (RetentionPreparationRefused, registration.RetentionRegistrationRefused))
                  else type(error).__name__)
        print(_canonical_json({"prepared": False, "launch_authorized": False, "commands": [], "reason": reason}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
