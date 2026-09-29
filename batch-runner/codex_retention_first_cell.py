"""Stage ordinal zero and provide its local, post-authority child protocol.

Default use verifies a no-launch packet and describes the selected cell. An
explicit staging call publishes the real Step2 layout in this dedicated source
checkout. Neither operation creates a host slot or starts a deadline.

Real execution is CLOSED. The existing remote claim/CI adapter binds the old
30-cell campaign, not this registration. No caller-supplied approval, receipt,
boolean or transport can open the public execution entrypoint. The private
post-authority protocol is exercised with an injected child transport offline;
it is not a substitute for reviewed-source/host/runtime/input/spend approval or
the remote CAS claim. Its flock covers only one explicit host-state directory,
never other runners. There is no campaign scheduler or automatic replay here.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import codex_budget_pilot as owned
import codex_retention_diagnostic as registration
import codex_retention_prepare_packet as preparation
from core.codex_task_deadline import CodexTaskDeadlineControl, CodexTaskDeadlineStore
from core.config import DEFAULT_LOCAL_PATH, WORKSPACE_DIR
from core.experiment_config import ExperimentConfig
from core.needs_files import NeedsFilesManifest
from core.prepared_fingerprint import prepared_fingerprint
from core.reference_integrity import resolve_verified_reference_paths
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_codex_input_capture import read_codex_prepared
from gpt54_prepared_input_attestation import (
    _check_prepared, _dataset_tasks, _identity, _json_object, _prepared_condition,
)
from gpt54_run_input_bundle import STEP0_MANIFEST_PATH
from step1_prepare_tasks import _public_codex_config

ROOT = preparation.ROOT
FIRST_CELL_ID = registration.TASK4 + "_retention_bundle_v1_keep_r1"
CONTROLLER = "batch-runner/codex_retention_first_cell.py"
SOURCE_PATHS = (CONTROLLER, "batch-runner/codex_budget_pilot.py",
                "batch-runner/core/config.py", "batch-runner/core/needs_files.py",
                "batch-runner/core/prepared_fingerprint.py",
                "batch-runner/core/reference_integrity.py")
STAGED = WORKSPACE_DIR / "retention-first-cell-staged.json"
STAGING = WORKSPACE_DIR / "retention-first-cell-staging.json"
PREPARED = ROOT / owned.PREPARED
MANIFEST = ROOT / STEP0_MANIFEST_PATH
LIVE_GATE = "retention_ci_cas_and_execution_approval_adapter_not_registered"
LIVE_BLOCKERS = [
    LIVE_GATE, "exact_controller_source_review_and_paid_cell_direction_required",
    "same_live_host_runtime_deployment_and_spend_approval_required",
    "remote_one_use_serial_claim_and_terminal_reconciliation_required",
]


class RetentionControllerRefused(ValueError):
    """A safe structural category, never private input content or paths."""


@dataclass(frozen=True)
class Request:
    cell_id: str
    sources: preparation.PreparedInputs
    packet: Path
    runtime_checkout: Path
    expected_preparer_sha256: str
    expected_controller_sha256: str
    plan: dict | None = None


def _same(reason: str, actual, expected) -> None:
    if (actual != expected if type(actual) is bytes and type(expected) is bytes
            else registration._canonical_json(actual) != registration._canonical_json(expected)):
        raise RetentionControllerRefused(reason)


def _encoded(value: dict) -> bytes:
    return registration._canonical_json(value).encode()


def source_identity() -> dict:
    """Additional controller bytes; a digest is an anchor, never review."""
    files = {role: _identity(preparation._read(ROOT / role, "controller_source"))
             for role in SOURCE_PATHS}
    return {"files": files, "sha256": registration.seal(files), "reviewed": False}


def _context(request: Request) -> dict:
    if type(request) is not Request or request.cell_id != FIRST_CELL_ID:
        raise RetentionControllerRefused("only_registered_ordinal_zero_supported")
    if preparation._path(request.runtime_checkout) != ROOT:
        raise RetentionControllerRefused("controller_must_run_from_explicit_runtime_checkout")
    _same("runtime_layout_mismatch", [str(path) for path in (DEFAULT_LOCAL_PATH, WORKSPACE_DIR, PREPARED, MANIFEST)],
          [str(ROOT / role) for role in ("data/gdpval-local", "batch-runner/workspace",
           "batch-runner/workspace/step1_tasks_prepared.json", "batch-runner/workspace/step0_needs_files_manifest.json")])
    plan = registration.compile_plan() if request.plan is None else registration.validate_plan(request.plan)
    cell = plan["cells"][0]
    _same("first_cell_binding_mismatch", [plan["order"][0], cell["index"], cell["cell_id"], cell["control"]],
          [FIRST_CELL_ID, 0, FIRST_CELL_ID,
           {"condition": "retention_bundle_v1", "retention_bundle": "keep", "repetition": 1}])
    source = source_identity()
    _same("controller_source_mismatch", source["sha256"], request.expected_controller_sha256)
    packet = preparation.verify_packet(
        cell_id=request.cell_id, sources=request.sources, output=request.packet,
        expected_preparer_sha256=request.expected_preparer_sha256, plan=plan,
    )
    return {"plan": plan, "cell": cell, "packet": packet, "controller_source": source}


def _runtime_files(request: Request, context: dict) -> dict[str, bytes]:
    """Project verified Step1 data with the existing serializers and validator.

    No new tasks format and no replacement Step0. The five-task original stays
    untouched. Only its selected row and required reference bytes are staged.
    The full original schema4 manifest is copied unchanged for Step2's reader.
    """
    packet, cell = context["packet"], context["cell"]
    originals = packet["input_verification"]
    prepared = _json_object(preparation._read(
        request.sources.prepared_root / preparation.PREPARED_PATH, "original_prepared_tasks",
        **originals["prepared_file"],
    ))
    task = _json_object(preparation._read(request.packet / preparation.TASK, "selected_task",
                                        **packet["files"][preparation.TASK]))
    config = ExperimentConfig.from_dict(cell["config"])
    execution = config.to_dict()["execution"]
    execution = {key: execution[key] for key in
                 ("mode", "max_retries", "resume_max_rounds", "tokens", "timeout", "sandbox")}
    execution["codex"] = _public_codex_config(config.execution.codex)
    if config.execution.metrics is not None:
        execution["metrics"] = config.execution.metrics
    prepared.update(
        experiment_id=config.experiment_id, experiment_name=config.name, description=config.description,
        source=config.data_filter.source, publication_generation=config.experiment_id,
        config_path=(preparation._path(request.packet) / preparation.INFERENCE).relative_to(ROOT / "batch-runner").as_posix(),
        task_scope={"mode": "explicit_ids", "expected_count": 1, "task_ids": [cell["task_id"]]},
        execution=execution, total_tasks=1, needs_files_count=int(task["needs_files"]),
        text_only_count=int(not task["needs_files"]), condition_a=_prepared_condition(config.condition_a),
        condition_b=_prepared_condition(config.condition_b), tasks=[task],
    )
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)
    data = _encoded(prepared)
    parquet = preparation._read(request.sources.dataset_parquet, "original_parquet",
                                sha256=context["plan"]["inputs"]["parquet_sha256"])
    projections, needs = _dataset_tasks(parquet, (cell["task_id"],))
    references = {row["path"]: {key: row[key] for key in ("size", "sha256")}
                  for row in task["reference_file_records"]}
    _check_prepared(data, SimpleNamespace(config_json=registration._canonical_json(cell["config"]),
                                         task_ids=[cell["task_id"]]), projections, references, needs)
    files = {
        owned.PREPARED: data,
        STEP0_MANIFEST_PATH: preparation._read(request.sources.step0_manifest, "original_schema4",
                                              **originals["original_files"][STEP0_MANIFEST_PATH]),
    }
    files.update({"data/gdpval-local/" + name: preparation._read(
        request.sources.reference_root / name, "selected_reference", **identity,
    ) for name, identity in references.items()})
    return files


def _description(context: dict) -> dict:
    cell, packet = context["cell"], context["packet"]
    return {
        "format": "codex-retention-first-cell-v1", "cell_id": cell["cell_id"], "ordinal": 0,
        "campaign_id": context["plan"]["campaign_id"], "plan_sha256": registration.seal(context["plan"]),
        "packet_sha256": registration.seal(packet), "runtime_baseline": packet["runtime_baseline"],
        "compiler_source": packet["compiler_source"], "preparer_source": packet["preparer_source"],
        "controller_source": context["controller_source"], "config_sha256": cell["config_sha256"],
        "input_roles_sha256": packet["input_verification"]["original_input_roles_sha256"],
        "selected_task": packet["selected_task"], "grading": packet["grading"],
        "launch_authorized": False, "commands": [], "inference_slot_reserved": False,
        "deadline_started": False, "runtime_inputs_staged": False,
        "launch_blockers": list(LIVE_BLOCKERS),
        "local_slot_scope": "one_explicit_host_state_root_not_cross_runner_exclusivity",
    }


def plan_first_cell(request: Request) -> dict:
    """Read and verify only. No stage publication, reservation or clock."""
    return _description(_context(request))


def _stage_record(context: dict, files: dict[str, bytes]) -> dict:
    result = _description(context)
    result.update(runtime_inputs_staged=True, files={name: _identity(data) for name, data in files.items()},
                  prepared_fingerprint=_json_object(files[owned.PREPARED])["prepared_fingerprint"])
    return result


def _require_no_runtime_output() -> None:
    for path in (WORKSPACE_DIR / "upload", WORKSPACE_DIR / "step2_inference_progress.json",
                 WORKSPACE_DIR / "step2_inference_progress_condition_a.json",
                 ROOT / owned.RESULT, ROOT / owned.LEDGER):
        preparation._path(path)
        if os.path.lexists(path):
            raise RetentionControllerRefused("runtime_output_already_present")


def _require_unused_runtime() -> None:
    # Exact consumer paths only; no campaign discovery or broad cleanup.
    _require_no_runtime_output()
    for path in (PREPARED, MANIFEST, STAGING, STAGED, DEFAULT_LOCAL_PATH):
        preparation._path(path)
        if os.path.lexists(path):
            raise RetentionControllerRefused("runtime_path_already_used_or_partial")


def verify_staged_runtime(request: Request) -> dict:
    """Reconcile real inputs, sources, path-specific grader and runtime bytes."""
    context = _context(request)
    files = _runtime_files(request, context)
    for role, expected in files.items():
        _same("staged_runtime_bytes_mismatch", preparation._read(ROOT / role, "staged_runtime"), expected)
    record = _stage_record(context, files)
    _same("staging_reservation_mismatch", preparation._read(STAGING, "staging_reservation"),
          _encoded({"stage_identity": registration.seal(record), "launch_authorized": False}))
    _same("staging_readback_mismatch", preparation._read(STAGED, "staging_record"), _encoded(record))
    # The same hardened reader/schema4/reference checks consumed by Step2.
    prepared = read_codex_prepared(PREPARED)
    manifest = NeedsFilesManifest.load(str(MANIFEST))
    manifest.require_schema(4)
    task, = prepared["tasks"]
    _same("staged_manifest_reference_mismatch", manifest.reference_records(task["task_id"], task["reference_files"]),
          task["reference_file_records"])
    _same("staged_manifest_projection_mismatch", manifest.source_projection_sha256(task["task_id"]),
          task["source_projection_sha256"])
    _same("staged_manifest_policy_mismatch", manifest.needs_files(task["task_id"]), task["needs_files"])
    resolve_verified_reference_paths(DEFAULT_LOCAL_PATH, task["reference_files"], task["reference_file_records"])
    return record


def stage_runtime(request: Request) -> dict:
    """No-clobber publication in the explicit dedicated runtime checkout.

    Caller-held parent descriptors cover every payload and both markers. A
    partial stage is retained and never overwritten/adopted. This reservation
    names file publication only; it is not an inference-slot reservation.
    """
    context = _context(request)
    files = _runtime_files(request, context)
    _require_unused_runtime()
    record = _stage_record(context, files)
    with ExitStack() as stack:
        check_workspace, _, workspace_fd = stack.enter_context(_publication_parents(WORKSPACE_DIR))
        check_data, mkdir, directory_fd = stack.enter_context(_publication_parents(DEFAULT_LOCAL_PATH.parent))
        _require_unused_runtime()
        _write_no_clobber(STAGING, _encoded({"stage_identity": registration.seal(record), "launch_authorized": False}),
                          parent_fd=workspace_fd(WORKSPACE_DIR))
        os.fsync(workspace_fd(WORKSPACE_DIR))
        mkdir(DEFAULT_LOCAL_PATH)
        parents = {Path(role).parent for role in files if role.startswith("data/gdpval-local/")}
        required = set()
        for parent in parents:
            while ROOT / parent != DEFAULT_LOCAL_PATH:
                required.add(ROOT / parent)
                parent = parent.parent
        for parent in sorted(required, key=lambda path: (len(path.parts), str(path))):
            mkdir(parent)
        for role, data in files.items():
            path = ROOT / role
            check_workspace()
            check_data()
            descriptor = workspace_fd(WORKSPACE_DIR) if path.parent == WORKSPACE_DIR else directory_fd(path.parent)
            _write_no_clobber(path, data, parent_fd=descriptor)
            os.fsync(descriptor)
        _same("input_or_source_changed_during_staging", _context(request), context)
        fresh_files = _runtime_files(request, context)
        if fresh_files != files:
            raise RetentionControllerRefused("runtime_recipe_changed_during_staging")
        for role, expected in files.items():
            _same("staged_runtime_bytes_mismatch", preparation._read(ROOT / role, "staged_runtime"), expected)
        check_workspace()
        check_data()
        _write_no_clobber(STAGED, _encoded(record), parent_fd=workspace_fd(WORKSPACE_DIR))
        os.fsync(workspace_fd(WORKSPACE_DIR))
        _same("staging_readback_mismatch", verify_staged_runtime(request), record)
        check_workspace()
        check_data()
        return record


def execute_first_cell(request: Request, *, host_state: Path) -> dict:
    """Closed before any slot, clock or child, even with a genuine packet.

    codex_budget_pilot_retention._binding/require_admission and
    codex_budget_pilot_ci.compile_ci_cell admit only their original campaign.
    LocalTransport.require_execution also binds that campaign's parent/C
    capability. None can currently attest this controller, cell or spend scope.
    Wiring those real contracts is a separate reviewed integration, not a bool
    or caller-provided receipt accepted by this library.
    """
    _context(request)
    raise RetentionControllerRefused(LIVE_GATE)


def _deadline(host: Path, context: dict, stage: dict, transport: owned.LocalTransport,
              *, initialize: bool = False) -> CodexTaskDeadlineStore:
    cell = context["cell"]
    run_id = cell["config"]["experiment"]["id"]
    return CodexTaskDeadlineStore(
        host / "deadline", run_id=run_id, experiment_id=run_id, condition_key="condition_a",
        control=CodexTaskDeadlineControl.from_mapping(cell["control"]), task_ids=[cell["task_id"]],
        prepared_fingerprint=stage["prepared_fingerprint"], initialize=initialize, clock=transport.clock,
    )


def _run_post_authority_cell(request: Request, *, host_state: Path,
                             _test_transport: owned.LocalTransport | None = None) -> dict:
    """Private local protocol, NOT an authority entrypoint or CLI test override.

    The real transport is refused here too, before any slot or clock. The
    library-only test seam follows the existing dispatcher convention: it must
    replace process transport while retaining the real child/command builder.
    It grants no authority and cannot open execute_first_cell. No validator is
    substituted. State/checksums, flock, owner checks and deadlines remain real.
    """
    if (_test_transport is None or not isinstance(_test_transport, owned.LocalTransport)
            or type(_test_transport).child is not owned.LocalTransport.child
            or type(_test_transport).process is owned.LocalTransport.process):
        raise RetentionControllerRefused(LIVE_GATE)
    transport = _test_transport
    context = _context(request)
    stage = verify_staged_runtime(request)
    plan, cell = context["plan"], context["cell"]
    host = owned._private_root(Path(host_state))
    for source in (request.packet, request.sources.prepared_root, request.sources.dataset_parquet,
                   request.sources.reference_root, request.sources.step0_manifest):
        source = preparation._path(source)
        if host.is_relative_to(source) or source.is_relative_to(host):
            raise RetentionControllerRefused("host_state_input_overlap")
    new = not os.path.lexists(host)
    if new:
        with _publication_parents(host.parent) as (_, mkdir, directory_fd):
            mkdir(host)
            os.fsync(directory_fd(host))
            os.fsync(directory_fd(host.parent))
    if not stat.S_ISDIR(host.lstat().st_mode) or stat.S_IMODE(host.stat().st_mode) != 0o700:
        raise RetentionControllerRefused("private_host_state_required")
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(host / "lock", flags | os.O_CREAT | os.O_EXCL if new else flags, 0o600)
    try:
        owned._regular_private(host / "lock")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RetentionControllerRefused("local_serial_slot_busy") from None
        binding = {"stage_sha256": registration.seal(stage), "cell_id": FIRST_CELL_ID,
                   "plan_sha256": registration.seal(plan), "scope": "local_one_use_not_remote_claim"}
        if not new:
            _same("local_slot_binding_mismatch", owned._load(host / "binding.json"), binding)
            owned._require_quiet_owner(host, plan)
            raise RetentionControllerRefused("first_cell_already_reserved_or_partial_no_replay")
        _require_no_runtime_output()
        owned._save(host / "binding.json", binding)
        owned._save(host / "ready.json", {"plan_sha256": registration.seal(plan)})
        owned._save(host / "owned-child.json", owned._owner_state(registration.seal(plan)))
        (host / "cells").mkdir(mode=0o700)
        (host / "cells" / FIRST_CELL_ID).mkdir(mode=0o700)
        adapted = {**cell, "run_id": cell["config"]["experiment"]["id"], "roles": {
            "checkout": str(ROOT), "native_workspaces": "native-workspaces", "deadline": "deadline",
            "result": str(ROOT / owned.RESULT), "ledger": str(ROOT / owned.LEDGER),
        }}
        state = owned._cell_state(plan, adapted)
        state.update(status="running", phase="prepared", prepared={
            "prepared_fingerprint": stage["prepared_fingerprint"], "publication_generation": adapted["run_id"],
        })
        owned._require_quiet_owner(host, plan)
        _same("runtime_changed_before_local_admission", verify_staged_runtime(request), stage)
        _require_no_runtime_output()
        # Reserve exactly once before the first clock or transport. Crash anywhere
        # after host creation is non-adoptable, including before this marker.
        with _publication_parents(host) as (_, _, directory_fd):
            _write_no_clobber(host / "reservation.json", _encoded(binding), parent_fd=directory_fd(host))
            os.fsync(directory_fd(host))
        store = _deadline(host, context, stage, transport, initialize=True)
        try:
            state["deadline_identity"] = store.identity
            # This is the post-authority cell admission, not plan/preparation.
            # Native attempt counters are still admitted only by the runtime.
            remaining = store.for_task(cell["task_id"]).remaining_seconds()
        finally:
            store.close()
        state.update(phase="executing", child_invocations=1)
        owned._save(host / "cell.json", state)
        try:
            code = transport.child(stage="infer", cell=adapted, root=host, lock=descriptor,
                                   timeout=remaining + 60)  # Existing dispatcher cleanup allowance.
            owned._require_quiet_owner(host, plan)
            owned._finish(host, adapted, state, code)
        except owned.OwnedChildCleanupRefused:
            state["reason"] = "owned_child_cleanup_unconfirmed"
            owned._save(host / "cell.json", state)
            raise
        except subprocess.TimeoutExpired:
            owned._require_quiet_owner(host, plan)
            owned._finish(host, adapted, state, None)
            state.update(status="stopped", phase="finished", reason="child_timeout_partial_accounting", exit_code=None)
        owned._save(host / "cell.json", state)
        return state
    finally:
        os.close(descriptor)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RetentionControllerRefused("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _Parser(description=__doc__)
        for name in ("prepared-root", "dataset-parquet", "reference-root", "step0-manifest", "packet", "runtime-checkout"):
            parser.add_argument("--" + name, type=Path, required=True)
        for name in ("cell-id", "expected-preparer-sha256", "expected-controller-sha256"):
            parser.add_argument("--" + name, required=True)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--stage-runtime", action="store_true")
        group.add_argument("--verify-stage", action="store_true")
        group.add_argument("--execute", action="store_true", help="Closed until the separate admission integration")
        parser.add_argument("--host-state", type=Path)
        args = parser.parse_args(argv)
        request = Request(args.cell_id, preparation.PreparedInputs(args.prepared_root, args.dataset_parquet,
                          args.reference_root, args.step0_manifest), args.packet, args.runtime_checkout,
                          args.expected_preparer_sha256, args.expected_controller_sha256)
        if args.execute:
            if args.host_state is None:
                raise RetentionControllerRefused("explicit_host_state_required")
            result = execute_first_cell(request, host_state=args.host_state)
        elif args.host_state is not None:
            raise RetentionControllerRefused("host_state_is_not_a_preparation_input")
        else:
            result = (stage_runtime if args.stage_runtime else verify_staged_runtime if args.verify_stage
                      else plan_first_cell)(request)
        # Public diagnostics never include the private packet location or
        # selected reference filenames. The local record retains those roles.
        print(registration._canonical_json({
            "cell_id": result["cell_id"], "ordinal": result["ordinal"],
            "launch_authorized": False, "commands": [], "inference_slot_reserved": False,
            "deadline_started": False, "runtime_inputs_staged": result["runtime_inputs_staged"],
            "record_sha256": registration.seal(result), "input_roles_sha256": result["input_roles_sha256"],
            "controller_source_sha256": result["controller_source"]["sha256"],
            "materialized_grader_source_sha256": result["grading"]["materialized_grader_source_sha256"],
            "launch_blockers": result["launch_blockers"],
        }))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        reason = (str(error) if isinstance(error, (RetentionControllerRefused,
                  preparation.RetentionPreparationRefused, registration.RetentionRegistrationRefused))
                  else type(error).__name__)
        print(registration._canonical_json({"launch_authorized": False, "commands": [], "reason": reason}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
