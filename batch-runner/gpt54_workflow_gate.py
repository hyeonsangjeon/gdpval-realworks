"""Bind a workflow request to local comparison preparation, never execution.

The compiler owns every command and control. Commands returned here are inert
argv data with a cwd inside the prepared checkout; this module has no dispatcher,
shell evaluation, provider construction or authentication path. Local lineage
does not prove external review, served capabilities or permission to spend.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

# The workflows use ``env -u PYTHONPATH python3 -I``. Isolated mode omits the
# script directory too, so admit only this script's own source checkout.
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml

from gpt54_comparison_preflight import (
    ROOT,
    ComparisonGradingPlan,
    ComparisonRunSpec,
    _canonical_json,
    compile_grading_plan,
)
from gpt54_disposable_checkout import (
    READY_PATH,
    DisposableCheckoutRefused,
    _common,
    _destination,
    _git,
    _sidecars,
    prepare_disposable_checkout,
    verify_runtime_checkout,
)
from gpt54_prepared_input_attestation import _json_object, _same
from gpt54_run_config_bundle import MANIFEST_PATH, _held_parents, _root, _sources
from gpt54_v2_grading_input import _read_bytes

OWNER_CONDITIONS: dict[str, Literal["sandbox_v2", "codex"]] = {
    "agentic-v2-stage-run": "sandbox_v2", "batch-run": "codex",
}


class WorkflowExecutionRefused(ValueError):
    """The local admission request is invalid, or launch remains prohibited."""


@dataclass(frozen=True)
class WorkflowRequest:
    """Exact dispatch inputs and caller-supplied review/event identity."""

    workflow: str
    run_id: str
    condition: Literal["sandbox_v2", "codex"]
    reviewed_source_sha: str
    event_name: str
    event_ref: str
    event_sha: str
    workflow_sha: str
    inputs_json: str


@dataclass(frozen=True)
class PreparedWorkflowExecution:
    """Inert command bindings, not an execution result or launch permission."""

    request: WorkflowRequest
    repository: Path
    checkout: Path
    cwd: Path
    commands: tuple[tuple[str, ...], ...]
    checkout_ready_json: str


def request_from_inputs(
    workflow: str, inputs: dict[str, Any], *, event_name: str, event_ref: str,
    event_sha: str, workflow_sha: str,
) -> WorkflowRequest:
    """Accept only one owner's exact comparison inputs on the reviewed main SHA.

    No defaults, overrides, relay state or opposite-harness ID are inferred.
    GitHub's typed ``inputs`` object must include every declared input.
    """
    try:
        if type(workflow) is not str or workflow not in OWNER_CONDITIONS:
            raise WorkflowExecutionRefused("an exact comparison workflow owner is required")
        if type(inputs) is not dict:
            raise WorkflowExecutionRefused("workflow inputs must be an object")
        sha = inputs.get("comparison_reviewed_source_sha")
        if type(sha) is not str or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
            raise WorkflowExecutionRefused("an explicit full lowercase reviewed SHA is required")
        _same("workflow event", {"name": event_name, "ref": event_ref}, {
            "name": "workflow_dispatch", "ref": "refs/heads/main",
        })
        _same("event/reviewed/workflow SHA", [event_sha, workflow_sha], [sha, sha])
        condition = OWNER_CONDITIONS[workflow]
        if condition == "sandbox_v2":
            run_id = inputs.get("run_id")
            expected = {
                "stage": "advance_check_5", "mode": "paid", "isolation": "same-host",
                "plan": "experiments/execution_envelope/agentic_corrected_harness_plan.yaml",
                "run_id": run_id, "resume_from_github_run": "",
                "comparison_reviewed_source_sha": sha,
            }
            suffix = "v2"
        else:
            experiment = inputs.get("experiment_yaml")
            prefix = "execution_envelope/"
            if type(experiment) is not str or not experiment.startswith(prefix):
                raise WorkflowExecutionRefused("batch comparison requires execution_envelope/<run_id>")
            run_id = experiment[len(prefix):]
            expected = {
                "experiment_yaml": prefix + run_id, "experiment_name": "", "dry_run": False,
                "relay_run": 0, "relay_lineage_id": "", "source_sha": "",
                # This legacy default is acknowledged, never applied to compiled argv.
                "wall_timeout": 290, "sandbox_image_digest": "",
                "codex_foundry_confirmed": True, "comparison_reviewed_source_sha": sha,
            }
            suffix = "codex"
        if type(run_id) is not str or re.fullmatch(rf"gpt54_v2_codex_v1_{suffix}_r[12]", run_id) is None:
            raise WorkflowExecutionRefused("registered run ID must belong to the workflow owner")
        _same("comparison workflow inputs", inputs, expected)
        return WorkflowRequest(
            workflow=workflow, run_id=run_id, condition=condition, reviewed_source_sha=sha,
            event_name=event_name, event_ref=event_ref, event_sha=event_sha,
            workflow_sha=workflow_sha, inputs_json=_canonical_json(inputs),
        )
    except WorkflowExecutionRefused:
        raise
    except (ValueError, TypeError, KeyError) as error:
        raise WorkflowExecutionRefused("comparison workflow inputs or source identities disagree") from error


def _compiled_request(
    request: WorkflowRequest, manifest: dict[str, Any], combined_plan: dict[str, Any],
) -> tuple[ComparisonGradingPlan, ComparisonRunSpec]:
    if type(request) is not WorkflowRequest:
        raise WorkflowExecutionRefused("an exact typed workflow request is required")
    expected = request_from_inputs(
        request.workflow, _json_object(request.inputs_json.encode("utf-8")),
        event_name=request.event_name, event_ref=request.event_ref,
        event_sha=request.event_sha, workflow_sha=request.workflow_sha,
    )
    _same("held workflow request", asdict(request), asdict(expected))
    plan = compile_grading_plan(manifest)
    _same("combined dispatch/grading plan", combined_plan, plan.as_dict())
    run = next((row for row in plan.dispatch.runs if row.run_id == request.run_id), None)
    if run is None:
        raise WorkflowExecutionRefused("workflow run is absent from the compiled comparison")
    _same("compiled workflow condition", request.condition, run.condition)
    _same("compiled workflow owner", manifest["conditions"][run.condition]["workflow"],
          f".github/workflows/{request.workflow}.yml")
    return plan, run


def _source_root(request: WorkflowRequest, repository: Path) -> Path:
    root, _ = _common(repository)
    if root != _root(ROOT):
        raise WorkflowExecutionRefused("workflow helper must be loaded from the explicit source repository")
    actual = _git(root, "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}").stdout
    if actual != request.reviewed_source_sha.encode("ascii") + b"\n":
        raise WorkflowExecutionRefused("source HEAD differs from reviewed/event/workflow SHA")
    return root


def prepare_workflow_execution(
    request: WorkflowRequest, *, repository: Path, destination: Path,
    manifest: dict[str, Any], combined_plan: dict[str, Any],
    dataset_parquet: Path, reference_root: Path,
) -> PreparedWorkflowExecution:
    """Reuse local checkout preparation and runtime lineage without launching.

    Raises:
        WorkflowExecutionRefused: Invalid inputs or retained failed preparation.
            No error path deletes, repairs, retries or adopts an old checkout.
            A failed final handoff best-effort quarantines the prepared checkout.
    """
    from gpt54_codex_input_capture import _write_no_clobber

    try:
        _, run = _compiled_request(request, manifest, combined_plan)
        source = _source_root(request, repository)
        _sources(source, manifest)
        _source_root(request, source)
        destination = _destination(destination, source)
        reservation, quarantine = _sidecars(destination)
        # Hold the original parent before preparation, not after the verifier
        # fails: a moved/replaced parent must not receive our quarantine write.
        with _held_parents(destination.parent, (destination.name,)) as check_parent:
            marker = prepare_disposable_checkout(
                run, repository=source, reviewed_source_sha=request.reviewed_source_sha,
                destination=destination, manifest=manifest, combined_plan=combined_plan,
                dataset_parquet=dataset_parquet, reference_root=reference_root,
            )
            try:
                check_parent()
                checkout = _root(destination)
                prepared = PreparedWorkflowExecution(
                    request=request, repository=source, checkout=checkout,
                    cwd=checkout / run.working_directory, commands=run.commands,
                    checkout_ready_json=_canonical_json(marker),
                )
                verify_workflow_execution(prepared, manifest=manifest, combined_plan=combined_plan)
                check_parent()
            except Exception as error:
                quarantine_written = False
                try:
                    check_parent()
                    _write_no_clobber(quarantine, _canonical_json({
                        "quarantine_version": "gpt54-disposable-checkout-quarantine-v1",
                        "reservation": reservation.name, "ready_path": READY_PATH,
                        "phase": "workflow_handoff", "failure_type": type(error).__name__,
                        "disposition": "manual_disposal_required_no_reuse",
                    }).encode("utf-8"))
                    quarantine_written = True
                except Exception:
                    # Keep every existing path. A changed parent or failed write
                    # cannot be repaired; reservation still prevents preparation.
                    pass
                raise WorkflowExecutionRefused(
                    "workflow handoff failed at workflow_handoff; do not reuse or overwrite; "
                    f"remaining checkout={destination} (exists={os.path.lexists(destination)}); "
                    f"reservation={reservation} (exists={os.path.lexists(reservation)}); "
                    f"quarantine={quarantine} (written={quarantine_written}, exists={os.path.lexists(quarantine)}); "
                    "manual disposal required; no cleanup performed"
                ) from error
            return prepared
    except WorkflowExecutionRefused:
        raise
    except DisposableCheckoutRefused as error:
        # The preparer includes reservation/quarantine paths after a partial write.
        raise WorkflowExecutionRefused(str(error)) from error
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as error:
        raise WorkflowExecutionRefused("local workflow preparation refused") from error


def verify_workflow_execution(
    prepared: PreparedWorkflowExecution, *, manifest: dict[str, Any], combined_plan: dict[str, Any],
) -> dict[str, Any]:
    """Return canonical JSON-native local evidence after real lineage validation.

    Recompute both the exact plan and source identity. Neither a modified argv,
    source cwd, swapped ready marker nor caller-supplied launch flag is accepted.
    """
    try:
        if type(prepared) is not PreparedWorkflowExecution:
            raise WorkflowExecutionRefused("an exact typed prepared workflow is required")
        request = prepared.request
        plan, run = _compiled_request(request, manifest, combined_plan)
        source = _source_root(request, prepared.repository)
        _sources(source, manifest)
        checkout = _root(prepared.checkout)
        cwd = _root(prepared.cwd)
        if checkout == source or cwd != checkout / run.working_directory:
            raise WorkflowExecutionRefused("workflow cwd must be the prepared checkout's batch-runner")
        if type(prepared.commands) is not tuple or any(type(row) is not tuple for row in prepared.commands):
            raise WorkflowExecutionRefused("workflow argv must remain immutable command tuples")
        _same("workflow command argv", prepared.commands, run.commands)
        marker = verify_runtime_checkout(checkout=checkout, run_id=run.run_id, condition=run.condition)
        if prepared.checkout_ready_json != _canonical_json(marker):
            raise WorkflowExecutionRefused("prepared checkout-ready evidence changed")
        _same("workflow checkout reviewed SHA", marker["reviewed_source_sha"], request.reviewed_source_sha)
        _same("workflow checkout source pins", marker["source_pins"], manifest["source_pins"])
        _sources(source, manifest)
        _source_root(request, source)
        return json.loads(_canonical_json({
            "gate_version": "gpt54-workflow-execution-gate-v1",
            "workflow_request": asdict(request), "run_id": run.run_id,
            "condition": run.condition, "repeat": run.repeat,
            "repository": str(source), "checkout": str(checkout), "cwd": str(cwd),
            "commands": run.commands, "checkout_ready": marker,
            "launch_allowed": plan.as_dict()["launch_allowed"],
            "dispatch_launch_allowed": plan.dispatch.as_dict()["launch_allowed"],
            "full_220_allowed": plan.as_dict()["full_220_allowed"],
            "commands_executed": False,
            "evidence_boundary": "local_workflow_request_and_prepared_checkout_only",
        }))
    except WorkflowExecutionRefused:
        raise
    except DisposableCheckoutRefused as error:
        raise WorkflowExecutionRefused(str(error)) from error
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as error:
        raise WorkflowExecutionRefused("prepared workflow lineage or command binding refused") from error


def require_workflow_launch(
    prepared: PreparedWorkflowExecution, *, manifest: dict[str, Any], combined_plan: dict[str, Any],
) -> None:
    """Revalidate, then refuse false compiler flags; this module cannot launch."""
    evidence = verify_workflow_execution(prepared, manifest=manifest, combined_plan=combined_plan)
    if evidence["launch_allowed"] is not True or evidence["dispatch_launch_allowed"] is not True:
        raise WorkflowExecutionRefused("canonical compiler launch flags are false; local preparation is not launch permission")
    raise WorkflowExecutionRefused("workflow command execution is not implemented in this gate")


def main(argv: list[str] | None = None) -> int:
    """Prepare locally, print evidence, and fail closed at mandatory launch check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True, choices=tuple(OWNER_CONDITIONS))
    parser.add_argument("--inputs-json", required=True)
    for name in ("event-name", "event-ref", "event-sha", "workflow-sha"):
        parser.add_argument("--" + name, required=True)
    for name in ("repository", "destination", "dataset-parquet", "reference-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request = request_from_inputs(
            args.workflow, _json_object(args.inputs_json.encode("utf-8")),
            event_name=args.event_name, event_ref=args.event_ref,
            event_sha=args.event_sha, workflow_sha=args.workflow_sha,
        )
        source = _source_root(request, args.repository)
        manifest = yaml.safe_load(_read_bytes(source / MANIFEST_PATH))
        combined = compile_grading_plan(manifest).as_dict()
        prepared = prepare_workflow_execution(
            request, repository=source, destination=args.destination,
            manifest=manifest, combined_plan=combined,
            dataset_parquet=args.dataset_parquet, reference_root=args.reference_root,
        )
        print(_canonical_json(verify_workflow_execution(prepared, manifest=manifest, combined_plan=combined)))
        require_workflow_launch(prepared, manifest=manifest, combined_plan=combined)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as error:
        detail = str(error) if isinstance(error, WorkflowExecutionRefused) else "invalid local workflow inputs"
        print(_canonical_json({"launch_allowed": False, "error": detail}))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
