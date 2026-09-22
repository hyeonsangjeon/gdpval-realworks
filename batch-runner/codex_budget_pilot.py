"""Serial, local A/B/C pilot dispatcher. The CLI defaults to plan-only.

Every cell owns a detached source checkout because Step 1/2 resolve their paths
relative to source. Host checkpoints and deadlines are outside native writable
workspaces. No dataset download, grading, upload or workflow is dispatched.
An explicit reviewed SHA is a caller assertion, not approval issued here.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import os
import re
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

import yaml

from core.codex_task_deadline import (
    ATTEMPT_SECONDS, TOTAL_SECONDS, CodexTaskDeadlineControl,
    CodexTaskDeadlineStore, _regular_private,
)
from core.experiment_config import ExperimentConfig
from core.hf_publication import (
    _assert_no_symlink_ancestors, _load_private_json_object, _write_private_json,
)
from core.result_fingerprint import validate_inference_result_fingerprint
from core.result_projection import project_result_row
from core.inference_manifest import bind_deliverable_file_records
from gpt54_comparison_preflight import (
    CODEX_TEMPLATE, GRADER, ROOT, ComparisonRunSpec, _canonical_json,
    compile_grading_plan, load_plan,
)
from gpt54_disposable_checkout import _git, _repository, _reviewed_commit, _safe_checkout_configuration
from gpt54_prepared_input_attestation import (
    _SourceSnapshot, _check_prepared, _identity, _json_object, _same, _source_snapshot,
)
from gpt54_run_input_bundle import PARQUET_PATH, STEP0_MANIFEST_PATH, _step0_bytes
from gpt54_v2_grading_input import _read_bytes, _write_file

REGISTRATION = ROOT / "batch-runner/experiments/execution_envelope/codex_external_budget_pilot.yaml"
FORMAT = "codex-external-budget-dispatch-v1"
ORDER = (("A", 1), ("B", 1), ("C", 1), ("C", 2), ("B", 2), ("A", 2))
TERMINAL = frozenset({"succeeded", "failed", "stopped"})
PREPARED = "batch-runner/workspace/step1_tasks_prepared.json"
RESULT = "batch-runner/workspace/step2_inference_results_condition_a.json"
LEDGER = "batch-runner/workspace/cost_ledger_condition_a.jsonl"
LOG = logging.getLogger(__name__)


class PilotDispatchRefused(ValueError):
    """No child may be admitted; retain any reserved or partial output."""


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _feedback_available() -> bool:
    # This is a required, reviewed source contract, never a user-editable flag.
    # v1 on the preceding main supports continuation but not C feedback.
    from core.codex_task_deadline import CONTINUATION_FORMAT

    return CONTINUATION_FORMAT == "codex-native-continuation-v2"


def compile_pilot(run_id: str, reviewed_source_sha: str) -> tuple[dict, Any, dict[str, ComparisonRunSpec]]:
    """Compile the fixed matrix using the existing score-free, pinned profile."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", run_id) is None:
        raise PilotDispatchRefused("invalid_run_identity")
    if re.fullmatch(r"[0-9a-f]{40}", reviewed_source_sha) is None:
        raise PilotDispatchRefused("explicit_reviewed_source_sha_required")
    registration = yaml.safe_load(_read_bytes(REGISTRATION))
    required = {
        "plan_version": "codex-external-budget-pilot-v1",
        "source_baseline": "149d89afd43e54a46b6f172b71c2cf23d0cb7a17",
        "parent_profile": CODEX_TEMPLATE,
        "profile_controls": "batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml",
        "cohort": "advance_check_5",
        "order_per_task": [{"condition": arm, "repetition": repeat} for arm, repeat in ORDER],
        "cell_count": 30, "active_children": 1, "cumulative_seconds": TOTAL_SECONDS,
        "attempt_seconds": ATTEMPT_SECONDS, "a_max_attempts": 4, "bc_max_attempts": None,
        "cost_policy": "observed_usage_no_automatic_monetary_cutoff", "default_mode": "plan_only",
        "c_required_continuation_format": "codex-native-continuation-v2",
        "grading": {"template": GRADER, "grades_per_task": 1, "launch": "separately_directed"},
        "analysis": {
            "denominator": "all_30_declared_cells_including_failed_filtered_expired",
            "missing_usage": "preserve_missing_and_partial_not_zero",
            "quality": "dispatch_and_files_are_not_grades",
            "stopping": "finite_matrix_no_low_score_retries",
        },
    }
    _same("pilot registration", {key: value for key, value in registration.items() if key != "description"}, required)
    parent = compile_grading_plan(load_plan())  # Genuine closure/pin/selector checks, not launch permission.
    profile = next(run for run in parent.dispatch.runs if run.condition == "codex")
    shared = json.loads(parent.dispatch.controls_json)
    if len(profile.task_ids) != 5:
        raise PilotDispatchRefused("advance_check_five_required")
    cells, specs = [], {}
    for task_id in profile.task_ids:
        for arm, repetition in ORDER:
            key = f"{task_id}_{arm}_r{repetition}"
            cell_run = f"{run_id}__{key}"
            config = load_plan(ROOT / CODEX_TEMPLATE)
            config["experiment"].update(
                id=cell_run, name="GPT-5.4 Codex external-budget pilot",
                description="One fixed pilot cell; dispatch is not model consumption or graded quality.",
            )
            config["data"]["source"] = shared["dataset"]["repo_id"]
            config["data"]["filter"]["task_ids"] = [task_id]
            # Read the reviewed GPT-5.4 profile; do not inherit the supervisor model.
            compiled_profile = json.loads(profile.config_json)
            config["condition_a"] = compiled_profile["condition_a"]
            config["execution"]["codex"] = compiled_profile["execution"]["codex"]
            config["execution"]["codex"]["task_deadline"] = {"condition": arm, "repetition": repetition}
            config["execution"].update(timeout=ATTEMPT_SECONDS, max_retries=3, resume_max_rounds=0)
            errors = ExperimentConfig.from_dict(config).validate()
            if errors:
                raise PilotDispatchRefused("compiled_config_refused")
            specs[key] = replace(
                profile, run_id=cell_run, repeat=repetition, task_ids=(task_id,),
                config_json=_canonical_json(config), config_path="batch-runner/pilot-run.json",
                checkout_directory=f"cells/{key}/checkout",
                commands=(("step1_prepare_tasks.py", "--config", "pilot-run.json"),
                          ("step2_run_inference.py", "--condition", "condition_a")),
            )
            cells.append({
                "cell_id": key, "run_id": cell_run, "task_id": task_id,
                "condition": arm, "repetition": repetition, "index": len(cells),
                "config_sha256": hashlib.sha256(specs[key].config_json.encode()).hexdigest(),
                "roles": {role: f"cells/{key}/{suffix}" for role, suffix in {
                    "config": "config.json", "checkout": "checkout", "deadline": "deadline",
                    "native_workspaces": "native-workspaces", "checkpoint": "cell.json",
                    "result": "checkout/" + RESULT, "ledger": "checkout/" + LEDGER,
                }.items()},
            })
    return ({
        "format": FORMAT, "run_id": run_id, "reviewed_source_sha": reviewed_source_sha,
        "registration_sha256": _identity(_read_bytes(REGISTRATION))["sha256"],
        "dispatcher_sha256": _identity(_read_bytes(Path(__file__)))["sha256"],
        "profile_manifest_sha256": parent.dispatch.manifest_sha256,
        "source_pins": json.loads(parent.dispatch.source_pins_json),
        "dataset": shared["dataset"], "model": shared["model"], "grading": shared["grading"],
        "order": [cell["cell_id"] for cell in cells], "cells": cells,
        "execution_requirements": ["reviewed_clean_source", "c_host_feedback_v2", "canonical_original_inputs",
                                   "pinned_sdk_and_cli", "confirmed_codex_connection", "registered_host_and_route"],
        "source_capability": {"c_host_feedback_present": _feedback_available(),
                              "unmet": [] if _feedback_available() else ["c_host_feedback_capability_missing"]},
        "launch_authorized_by_plan": False, "grading_launched": False,
    }, parent, specs)


@dataclass(frozen=True)
class InputSources:
    parquet: Path
    references: Path
    manifest: Path


@dataclass(frozen=True)
class VerifiedInputs:
    snapshot: _SourceSnapshot
    files: dict[str, bytes]

    def identities(self) -> dict:
        return {role: _identity(data) for role, data in self.files.items()}


class LocalTransport:
    """The narrow local child boundary. Tests supply a synthetic subclass only."""

    clock: Callable[[], float] = staticmethod(time.time)

    def feedback_available(self) -> bool:
        return _feedback_available()

    def require_execution(self, plan: dict, parent: Any) -> dict:
        if not self.feedback_available():
            raise PilotDispatchRefused("c_host_feedback_capability_missing")
        _, common = _repository(ROOT)
        _safe_checkout_configuration(ROOT)
        sha = plan["reviewed_source_sha"]
        if (_git(ROOT, "rev-parse", "HEAD").stdout.decode().strip() != sha
                or _git(ROOT, "status", "--porcelain", "--untracked-files=normal").stdout):
            raise PilotDispatchRefused("reviewed_clean_source_required")
        reviewed = _reviewed_commit(ROOT, sha, load_plan(), parent)
        from core.codex_runtime_config import require_pinned_runtime
        from core.azure_ai_clients import AzureAIRouteSettings
        import step2_run_inference as step2

        require_pinned_runtime()
        step2._require_runnable_execution_mode("codex_foundry")
        step2._require_host_may_carry_a_benchmark_run("codex_foundry")
        settings = AzureAIRouteSettings.from_env()
        if (settings.profile.value != plan["model"]["route_profile"] or settings.direct_v1 is None
                or settings.direct_v1.account != plan["model"]["account"]):
            raise PilotDispatchRefused("registered_route_required")
        condition = json.loads(next(run for run in parent.dispatch.runs if run.condition == "codex").config_json)["condition_a"]
        routes = step2.preflight_routes(step2.inference_route_workloads(condition, "codex_foundry"), settings=settings)
        return {"tree_sha": reviewed["tree_sha"], "routes": routes, "common": str(common)}

    def inputs(self, parent: Any, sources: InputSources) -> VerifiedInputs:
        snapshot = _source_snapshot(parent, sources.parquet, sources.references)
        manifest = _step0_bytes(sources.manifest, snapshot)
        files = {
            PARQUET_PATH: _read_bytes(sources.parquet, **snapshot.shared_binding["dataset"]["parquet"]),
            STEP0_MANIFEST_PATH: manifest,
        }
        files.update({"data/gdpval-local/" + name: _read_bytes(sources.references / name, **identity)
                      for name, identity in snapshot.references.items()})
        return VerifiedInputs(snapshot, files)

    def checkout(self, destination: Path, sha: str) -> None:
        _git(ROOT, "worktree", "add", "--detach", str(destination), sha)
        self.verify_checkout(destination, sha)

    def verify_checkout(self, destination: Path, sha: str) -> None:
        _repository(destination)
        if (_git(destination, "rev-parse", "HEAD").stdout.decode().strip() != sha
                or _git(destination, "diff", "--name-only", "HEAD", "--").stdout
                or _git(destination, "symbolic-ref", "--quiet", "HEAD", ok=(0, 1)).returncode != 1):
            raise PilotDispatchRefused("cell_source_drift")

    def process(self, command: list[str], **options: Any) -> subprocess.CompletedProcess:
        """Only process boundary; the offline transport replaces this method."""
        return subprocess.run(command, **options)

    def child(self, *, stage: str, cell: dict, root: Path, lock: int, timeout: float) -> int:
        checkout = root / cell["roles"]["checkout"]
        environment = dict(os.environ, HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1",
                           HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1", PYTHONDONTWRITEBYTECODE="1",
                           GDPVAL_RELAY_LINEAGE_ID=cell["run_id"],
                           GDPVAL_CODEX_RUN_ROOT=str(root / cell["roles"]["native_workspaces"]))
        # Never inherit a Python search path pointing at a different feature checkout.
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        command = [sys.executable]
        if stage == "prepare":
            command += ["step1_prepare_tasks.py", "--config", "pilot-run.json"]
        else:
            command += ["step2_run_inference.py", "--condition", "condition_a",
                        "--codex-deadline-state", str(root / cell["roles"]["deadline"])]
        # Inherit the serial lock: a surviving child blocks a second dispatcher
        # even if its parent is killed. Logs remain in the private cell directory.
        log_path = root / "cells" / cell["cell_id"] / f"{stage}-{time.time_ns()}.log"
        with log_path.open("xb") as stream:
            os.chmod(log_path, 0o600)
            result = self.process(command, cwd=checkout / "batch-runner", env=environment,
                                  stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                  pass_fds=(lock,), timeout=timeout, check=False)
        return result.returncode


def _private_root(path: Path) -> Path:
    if ".." in path.parts:
        raise PilotDispatchRefused("unsafe_output_path")
    path = _assert_no_symlink_ancestors(path)
    from core.codex_runtime_config import path_is_within, resolve_run_root_base, system_temporary_directory

    for unsafe in (ROOT, resolve_run_root_base(), system_temporary_directory(), Path("/tmp")):
        if path_is_within(path, unsafe) or path_is_within(unsafe, path):
            raise PilotDispatchRefused("output_overlaps_source_or_agent_writable_root")
    return path


def _save(path: Path, payload: dict) -> None:
    if os.path.lexists(path):
        _regular_private(path)
    _write_private_json(path, {"payload": payload, "sha256": _digest(payload)})


def _load(path: Path) -> dict:
    _regular_private(path)
    value = _load_private_json_object(path, "pilot checkpoint")
    if set(value) != {"payload", "sha256"} or value["sha256"] != _digest(value["payload"]):
        raise PilotDispatchRefused("checkpoint_checksum_mismatch")
    return value["payload"]


def _cell_state(plan: dict, cell: dict) -> dict:
    return {"plan_sha256": _digest(plan), "cell_id": cell["cell_id"], "status": "pending",
            "phase": "pending", "prepared": None, "deadline_identity": None,
            "child_invocations": 0, "exit_code": None, "reason": None,
            "result": None, "receipt": None, "accounting": "missing", "artifacts": {}}


def _validate_state(plan: dict, cell: dict, state: dict) -> None:
    if (set(state) != set(_cell_state(plan, cell)) or state["plan_sha256"] != _digest(plan)
            or state["cell_id"] != cell["cell_id"]
            or state["status"] not in {"pending", "running", *TERMINAL}
            or state["phase"] not in {"pending", "preparing", "prepared", "executing", "finished"}
            or type(state["child_invocations"]) is not int or state["child_invocations"] < 0):
        raise PilotDispatchRefused("cell_checkpoint_identity_mismatch")
    if state["status"] == "pending" and state != _cell_state(plan, cell):
        raise PilotDispatchRefused("pending_cell_has_activity")
    if state["status"] in TERMINAL and state["phase"] != "finished":
        raise PilotDispatchRefused("terminal_cell_phase_mismatch")


def _deadline(root: Path, cell: dict, state: dict, transport: LocalTransport, *, initialize: bool = False) -> CodexTaskDeadlineStore:
    return CodexTaskDeadlineStore(
        root / cell["roles"]["deadline"], run_id=cell["run_id"], experiment_id=cell["run_id"],
        condition_key="condition_a", control=CodexTaskDeadlineControl(cell["condition"], cell["repetition"]),
        task_ids=[cell["task_id"]], prepared_fingerprint=state["prepared"]["prepared_fingerprint"],
        initialize=initialize, clock=transport.clock,
    )


def _check_inputs(checkout: Path, inputs: VerifiedInputs) -> None:
    for role, identity in inputs.identities().items():
        _read_bytes(checkout / role, **identity)


def _prepared(checkout: Path, spec: ComparisonRunSpec, inputs: VerifiedInputs) -> dict:
    snapshot, task_id = inputs.snapshot, spec.task_ids[0]
    return _check_prepared(_read_bytes(checkout / PREPARED), spec,
                           [row for row in snapshot.projections if row["task_id"] == task_id],
                           snapshot.references, {task_id: snapshot.needs_files[task_id]})


def _finish(root: Path, cell: dict, state: dict, exit_code: int | None) -> None:
    """Project recorded facts; a zero exit without a result is not success."""
    state.update(status="failed", phase="finished", exit_code=exit_code, reason="missing_result")
    path = root / cell["roles"]["result"]
    if not os.path.lexists(path):
        return
    data = _read_bytes(path)
    result = _json_object(data)
    validate_inference_result_fingerprint(result)
    for key, expected in {
        "run_id": cell["run_id"], "experiment_id": cell["run_id"], "condition_identity": "condition_a",
        "execution_mode": "codex_foundry", "ordered_task_ids": [cell["task_id"]],
        "prepared_fingerprint": state["prepared"]["prepared_fingerprint"], "model": "gpt-5.4",
        "publication_generation": state["prepared"]["publication_generation"],
    }.items():
        _same("result " + key, result.get(key), expected)
    if len(result.get("results", [])) != 1 or result["results"][0].get("task_id") != cell["task_id"]:
        raise PilotDispatchRefused("result_cell_mismatch")
    projected = project_result_row({}, result["results"][0])
    bound_files = bind_deliverable_file_records(
        result["results"], root / cell["roles"]["checkout"] / "batch-runner/workspace/upload",
    )
    _same("result deliverable bytes", result["results"][0].get("deliverable_file_records", []),
          bound_files[0]["deliverable_file_records"])
    status = projected["status"]
    state.update(status="succeeded" if status == "success" else "stopped" if status == "pending" else "failed",
                 reason=None if status == "success" else "recorded_task_" + str(status),
                 result={"path": cell["roles"]["result"], **_identity(data)},
                 receipt=projected.get("problem_solving_cost"))
    if exit_code not in (None, 0):
        state.update(status="failed", reason="child_nonzero_exit")
    state["accounting"] = "missing" if state["receipt"] is None else state["receipt"]["status"]
    # Keep links to the producer evidence; do not inline prompts or model output.
    state["artifacts"] = {"result_fingerprint": result["result_fingerprint"],
                          "deliverable_files": bound_files[0]["deliverable_file_records"], "ledger": None}
    ledger = result.get("cost_ledger")
    if ledger is not None:
        from core.cost_projection import project_cost_ledger_reference

        ledger = project_cost_ledger_reference(ledger)
        if ledger["path"] != Path(LEDGER).name:
            raise PilotDispatchRefused("ledger_role_mismatch")
        ledger_data = _read_bytes(root / cell["roles"]["ledger"], sha256=ledger["sha256"])
        state["artifacts"]["ledger"] = {"path": cell["roles"]["ledger"], **_identity(ledger_data)}


def dispatch(plan: dict, parent: Any, specs: dict[str, ComparisonRunSpec], *, root: Path,
             execute: bool, resume: bool, sources: InputSources | None,
             transport: LocalTransport) -> dict:
    """Materialize or serially run the registered cells; restore is explicit."""
    root = _private_root(root)
    execution, inputs = None, None
    if execute:
        execution = transport.require_execution(plan, parent)
        if sources is None:
            raise PilotDispatchRefused("explicit_original_input_sources_required")
        for source in (sources.parquet, sources.references, sources.manifest):
            source = _assert_no_symlink_ancestors(source)
            if source.is_relative_to(root) or root.is_relative_to(source):
                raise PilotDispatchRefused("source_output_overlap")
        inputs = transport.inputs(parent, sources)
    if not resume:
        root.mkdir(mode=0o700, exist_ok=False)
    metadata = root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise PilotDispatchRefused("private_dispatch_root_required")
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(root / "lock", flags if resume else flags | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _regular_private(root / "lock")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if resume:
            _same("dispatch plan", _load(root / "plan.json"), plan)
            ready = _load(root / "ready.json")
            _same("ready plan", ready, {"plan_sha256": _digest(plan)})
        else:
            _save(root / "plan.json", plan)
            (root / "cells").mkdir(mode=0o700)
            for cell in plan["cells"]:
                (root / "cells" / cell["cell_id"]).mkdir(mode=0o700)
                _write_file(root / cell["roles"]["config"], specs[cell["cell_id"]].config_json.encode())
                os.chmod(root / cell["roles"]["config"], 0o600)
                _save(root / cell["roles"]["checkpoint"], _cell_state(plan, cell))
            _save(root / "ready.json", {"plan_sha256": _digest(plan)})  # Last; partial materialization refuses.
        if execute:
            binding = {"plan_sha256": _digest(plan), "execution": execution, "files": inputs.identities(),
                       "source_projection": inputs.snapshot.shared_binding}
            if os.path.lexists(root / "inputs.json"):
                _same("original inputs/runtime", _load(root / "inputs.json"), binding)
            else:
                # Only pending cells may acquire their initial source binding.
                if any(_load(root / cell["roles"]["checkpoint"])["status"] != "pending" for cell in plan["cells"]):
                    raise PilotDispatchRefused("missing_started_input_binding")
                _save(root / "inputs.json", binding)
        states = []
        for cell in plan["cells"]:
            state_path = root / cell["roles"]["checkpoint"]
            state = _load(state_path)
            _validate_state(plan, cell, state)
            _read_bytes(root / cell["roles"]["config"], sha256=cell["config_sha256"])
            if not execute or state["status"] in TERMINAL:
                if execute and state["result"] is not None:
                    if state["result"]["path"] != cell["roles"]["result"]:
                        raise PilotDispatchRefused("recorded_result_role_mismatch")
                    _read_bytes(root / state["result"]["path"],
                                sha256=state["result"]["sha256"], size=state["result"]["size"])
                states.append(state)
                continue
            checkout, spec = root / cell["roles"]["checkout"], specs[cell["cell_id"]]
            if state["status"] == "pending":
                if any(os.path.lexists(root / cell["roles"][role]) for role in ("checkout", "deadline", "native_workspaces")):
                    raise PilotDispatchRefused("unrecorded_cell_state_no_clobber")
                state.update(status="running", phase="preparing")
                _save(state_path, state)
                transport.checkout(checkout, plan["reviewed_source_sha"])
                for role in (PREPARED, RESULT, LEDGER, "batch-runner/workspace/cost_ledger_condition_a.sqlite3",
                             "batch-runner/workspace/step2_inference_progress_condition_a.json"):
                    if os.path.lexists(checkout / role):
                        raise PilotDispatchRefused("generated_cell_output_already_exists")
                for role, data in {**inputs.files, "batch-runner/pilot-run.json": spec.config_json.encode()}.items():
                    target = _assert_no_symlink_ancestors(checkout / role)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    _write_file(target, data)
                _check_inputs(checkout, inputs)
                code = transport.child(stage="prepare", cell=cell, root=root, lock=descriptor, timeout=300)
                if code:
                    state.update(status="failed", phase="finished", exit_code=code, reason="step1_refused")
                    _save(state_path, state)
                    states.append(state)
                    continue
                observed = _prepared(checkout, spec, inputs)
                state["prepared"] = {key: observed[key] for key in ("prepared_fingerprint", "publication_generation", "prepared_file")}
                store = _deadline(root, cell, state, transport, initialize=True)
                try:
                    state["deadline_identity"] = store.identity
                    # Start once before dispatch. No provider attempt is admitted here.
                    store.for_task(cell["task_id"]).remaining_seconds()
                finally:
                    store.close()
                state["phase"] = "prepared"
                _save(state_path, state)
            elif state["phase"] == "preparing":
                raise PilotDispatchRefused("incomplete_cell_preparation_retained")
            transport.verify_checkout(checkout, plan["reviewed_source_sha"])
            _check_inputs(checkout, inputs)
            _read_bytes(checkout / "batch-runner/pilot-run.json", sha256=cell["config_sha256"])
            prepared = _prepared(checkout, spec, inputs)
            _same("restored prepared", state["prepared"], {key: prepared[key] for key in state["prepared"]})
            store = _deadline(root, cell, state, transport)
            try:
                _same("deadline identity", state["deadline_identity"], store.identity)
                remaining = store.for_task(cell["task_id"]).remaining_seconds()
            finally:
                store.close()
            if os.path.lexists(root / cell["roles"]["result"]):
                # Child finished before its dispatcher checkpoint. Consume the
                # validated producer result, never repeat the completed cell.
                _finish(root, cell, state, state["exit_code"])
            else:
                state.update(phase="executing", child_invocations=state["child_invocations"] + 1)
                _save(state_path, state)
                try:
                    # Even an expired restore reaches Step 2 host-only accounting;
                    # its original deadline forbids a native request. Allow cleanup.
                    code = transport.child(stage="infer", cell=cell, root=root, lock=descriptor, timeout=remaining + 60)
                except subprocess.TimeoutExpired:
                    state.update(status="stopped", phase="finished", reason="child_timeout_partial_accounting", exit_code=None)
                else:
                    _finish(root, cell, state, code)
            _save(state_path, state)
            states.append(state)
        summary = {"plan_sha256": _digest(plan), "denominator": 30, "grading_launched": False,
                   "counts": {status: sum(row["status"] == status for row in states)
                              for status in ("pending", "running", "succeeded", "failed", "stopped")},
                   "cells": states}
        _save(root / "dispatch-result.json", summary)
        return summary
    finally:
        os.close(descriptor)


def main(argv: list[str] | None = None, *, _test_transport: LocalTransport | None = None) -> int:
    """Run the actual CLI path; transport injection is library-only for offline tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true", help="Explicit later launch direction; all guards still apply")
    parser.add_argument("--resume", action="store_true", help="Validate and reuse recorded cells; never reset clocks")
    parser.add_argument("--dataset-parquet", type=Path)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--step0-manifest", type=Path)
    args = parser.parse_args(argv)
    if any((args.dataset_parquet, args.reference_root, args.step0_manifest)) and not all((args.dataset_parquet, args.reference_root, args.step0_manifest)):
        parser.error("all three explicit input sources are required together")
    sources = InputSources(args.dataset_parquet, args.reference_root, args.step0_manifest) if args.dataset_parquet else None
    try:
        plan, parent, specs = compile_pilot(args.run_id, args.reviewed_source_sha)
        transport = _test_transport or LocalTransport()
        if not args.execute and not transport.feedback_available():
            LOG.warning("Plan only: execution requirement unmet: c_host_feedback_capability_missing")
        summary = dispatch(plan, parent, specs, root=args.output, execute=args.execute, resume=args.resume,
                           sources=sources, transport=transport)
    except KeyboardInterrupt:
        LOG.error("Interrupted: retain the running cell and resume its recorded state")
        return 130
    except (OSError, ValueError, TypeError, KeyError) as error:
        # No raw provider/host-path text in public diagnostics.
        LOG.error("Pilot refused (%s); retain all reserved/partial state", type(error).__name__)
        if isinstance(error, PilotDispatchRefused):
            LOG.error("Reason: %s", error)
        return 2
    LOG.info("Pilot record: %s; denominator=30; no grading launched", summary["counts"])
    return 1 if args.execute and (summary["counts"]["failed"] or summary["counts"]["stopped"]) else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
