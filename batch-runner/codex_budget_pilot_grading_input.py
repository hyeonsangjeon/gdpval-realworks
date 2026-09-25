"""Prepare one registered pilot cell for the unchanged local grader; never grade.

The caller supplies an externally approved inference-identity document and its
SHA256. For live use it must name the actual output HF repository and immutable
publication revision. This offline reader cannot authenticate that publication.
Its JSON return is a private preparation manifest, not a public CI completion.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
from gpt54_codex_grading_input import _materialize_bound_codex_grading_input
import gpt54_v2_grading_input as primitives
from gpt54_comparison_preflight import (
    ComparisonGradingPlan, _canonical_json, _compile_grading_plan, load_plan,
)

MAX_PREPARATION_BYTES = 64 * 1024


class PilotGradingInputRefused(ValueError):
    """Closed errors; never expose source contents or private filesystem paths."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PilotGradingInputRefused("invalid_arguments")


def compile_cell_grading_plan(
    campaign_id: str, cell_id: str, reviewed_source_sha: str,
) -> tuple[dict, dict, ComparisonGradingPlan]:
    """Select an exact compiler member, not a run-ID prefix or a live CI host."""
    if campaign_id != ci.CAMPAIGN:
        raise PilotGradingInputRefused("registered_ci_campaign_required")
    try:
        plan, parent, specs = pilot.compile_pilot(campaign_id, reviewed_source_sha)
        cells = [cell for cell in plan["cells"] if cell["cell_id"] == cell_id]
        if len(cells) != 1 or plan["order"].count(cell_id) != 1:
            raise PilotGradingInputRefused("canonical_selected_cell_required")
        ci._eligible_ordinal(plan, cell_id)
        registration_bytes = ci._registration_bytes()
        # Bind the real pilot's inputs, order, source and controls, plus the
        # recorded common host policy. No live-runner identity is invented.
        binding = {
            "pilot": plan, "ci_registration_sha256": pilot._identity(registration_bytes)["sha256"],
            "host_policy": ci.HOST_POLICY,
        }
        dispatch = replace(
            parent.dispatch, manifest_sha256=pilot._digest(binding),
            source_base_sha=reviewed_source_sha, runs=(specs[cell_id],),
        )
        grading = _compile_grading_plan(dispatch)  # Same fixed grader/config validator.
        run = grading.runs[0]
        command = list(run.command)
        command[command.index("--limit") + 1] = str(len(run.task_ids))
        # Step8 deliberately refuses '__' in its config pathname. The producer
        # run ID contains it, and is NOT the pathname: keep that identity and
        # --source-experiment-id intact. A short canonical-index alias also
        # leaves room for Step8's ledger/checkpoint suffixes without changing
        # the fixed filename template or grading policy.
        alias = f"pilot/cell-{plan['order'].index(cell_id):02d}"
        command[2] = alias
        run = replace(
            run, producer_results_path=pilot.RESULT, command=tuple(command),
            experiment_config_path=f"batch-runner/experiments/{alias}.yaml",
            input_materialization="codex_budget_pilot_grading_input.materialize_pilot_grading_input",
        )
        return plan, cells[0], replace(grading, runs=(run,))
    except PilotGradingInputRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise PilotGradingInputRefused("registered_cell_controls_refused") from error


def materialize_pilot_grading_input(
    *, campaign_id: str, cell_id: str, reviewed_source_sha: str,
    inference_results: Path, source_upload: Path, inference_identity: Path,
    approved_identity_sha256: str, destination: Path,
) -> dict:
    """Install validated bytes atomically into an absent private tree.

    The existing identity schema is unchanged: ``condition`` remains ``codex``;
    the A/B/C treatment, one task, repetition, settings and declared originals
    are bound by the compiler-derived run/config/manifest/grading-plan hashes.
    Original-input provenance remains the external issuer's responsibility.
    Only the derived result gets the existing source-identity augmentation and
    new fingerprint. No input checkout, grader config or grade is materialized.
    """
    plan, cell, grading = compile_cell_grading_plan(campaign_id, cell_id, reviewed_source_sha)
    run = grading.runs[0]
    try:
        if any(".." in Path(path).parts for path in (
            inference_results, source_upload, inference_identity, destination,
        )):
            raise PilotGradingInputRefused("parent_traversal_refused")
        # This same externally pinned document is read/checked by the shared
        # materializer below. A changed file between reads fails its digest.
        identity = primitives._read_object(inference_identity, sha256=approved_identity_sha256)
        primitives._same("canonical producer run", identity["producer_run_id"], cell["run_id"])
        if identity["source_revision"] == reviewed_source_sha:
            raise PilotGradingInputRefused("git_revision_is_not_inference_identity")
        preparation = {
            "format": "codex-pilot-grading-input-v1", "campaign_id": campaign_id,
            "cell_id": cell_id, "run_id": cell["run_id"], "task_id": cell["task_id"],
            "condition": cell["condition"], "repetition": cell["repetition"],
            "reviewed_source_sha": reviewed_source_sha,
            "manifest_sha256": grading.dispatch.manifest_sha256,
            "grading_plan_sha256": hashlib.sha256(grading.canonical_bytes()).hexdigest(),
            "config_sha256": cell["config_sha256"],
            "declared_inputs_sha256": pilot._digest(plan["dataset"]),
            "source_identity_sha256": approved_identity_sha256,
            "source_identity": identity,
            "grading": {
                "state": "UNRUN", "template": plan["grading"]["config"],
                "template_source_sha256": plan["grading"]["template_source_sha256"],
                "config_sha256": run.output.config_sha256,
            },
            "proof_boundary": "caller_approved_identity_not_provider_authentication",
        }
        # Bound the returned metadata before installing anything. The shared
        # exact-schema check rejects extra/raw identity fields before success.
        if len(_canonical_json(preparation).encode("utf-8")) > MAX_PREPARATION_BYTES - 1024:
            raise PilotGradingInputRefused("preparation_manifest_too_large")
        result = _materialize_bound_codex_grading_input(
            run, plan=grading, manifest=load_plan(), inference_results=inference_results,
            source_upload=source_upload, inference_identity=inference_identity,
            approved_identity_sha256=approved_identity_sha256, destination=destination,
        )
        data = primitives._read_bytes(result)
        output = json.loads(data)
        preparation["materialized_result"] = {
            "path": run.inference_results_path, **pilot._identity(data),
            "result_fingerprint": output["result_fingerprint"],
        }
        preparation["task_status"] = output["results"][0]["status"]
        preparation["successful_deliverable_present"] = preparation["task_status"] == "success"
        return preparation
    except PilotGradingInputRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise PilotGradingInputRefused("cell_grading_inputs_refused") from error


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--inference-results", required=True, type=Path)
    parser.add_argument("--source-upload", required=True, type=Path)
    parser.add_argument("--inference-identity", required=True, type=Path)
    parser.add_argument("--approved-identity-sha256", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    try:
        args = parser.parse_args(argv)
        result = materialize_pilot_grading_input(
            campaign_id=args.campaign_id, cell_id=args.cell, reviewed_source_sha=args.reviewed_source_sha,
            inference_results=args.inference_results, source_upload=args.source_upload,
            inference_identity=args.inference_identity, approved_identity_sha256=args.approved_identity_sha256,
            destination=args.destination,
        )
        print(_canonical_json(result))
        return 0
    except PilotGradingInputRefused as error:
        print(f"Pilot grading input refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
