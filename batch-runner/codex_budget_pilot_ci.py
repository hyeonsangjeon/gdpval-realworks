"""Plan-first, one registered CI cell; no scheduler or cross-runner restore."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import logging
import math
import os
from pathlib import Path
import re
import sys
from typing import Any

import yaml

import codex_budget_pilot as pilot
from core.cost_projection import COST_STATUSES, project_cost_receipt
from core.result_projection import project_result_row

CAMPAIGN = "budget_pilot_ci_20260924_03"
INFERENCE_BRANCH = "pilot-inference-20260924-03"
GRADING_BRANCH = "pilot-grades-20260924-03"
STORAGE = {
    "repository_name_sha256": "a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44",
    "bootstrap": "bfc7ae01ed14490817ceb7cb406adcb9bb95f557",
    "inference_branch": INFERENCE_BRANCH, "grading_branch": GRADING_BRANCH,
}
REPOSITORY = "hyeonsangjeon/gdpval-realworks"
WORKFLOW = ".github/workflows/codex-budget-pilot-ci-cell.yml"
REGISTRATION = pilot.REGISTRATION.with_name("codex_external_budget_ci_pilot_epoch03.yaml")
HOST_POLICY = {
    "runner": "ubuntu-22.04", "python": "3.10.12", "sdk": "0.147.0", "cli": "0.147.0",
    "identity": "existing_repository_oidc", "job_ceiling_minutes": 240,
    "same_policy_all_conditions": True, "cross_runner_restore": False,
    "automatic_rerun": "refuse_run_attempt_above_one",
}
INPUT_ROLES = ("normalized_parquet", "reference_only_root", "canonical_step0_manifest")
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens",
              "audio_input_tokens", "audio_output_tokens")
PUBLIC_REASONS = frozenset({
    "execution_not_finalized", "interrupted_same_host_state_retained", "ci_execution_refused",
    "missing_original_inputs", "canonical_original_inputs_refused", "ci_input_identity_changed",
    "owned_child_cleanup_unconfirmed", "missing_result", "child_nonzero_exit", "step1_refused",
    "preparation_timeout_partial_output", "child_timeout_partial_accounting",
    "recorded_task_non_success", "c_host_feedback_capability_missing", "registered_route_required",
    "reviewed_clean_source_required", "unselected_cell_has_activity",
})
# Exact existing Codex runner/deadline and execution_errors categories. Step2's
# observability projection bounds length, not vocabulary: never publish it raw
# or classify private error text here. New producer values require review.
RECORDED_FAILURE_CATEGORIES = frozenset({
    "model_mismatch", "workspace_error", "reference_error", "runtime_unavailable",
    "runtime_start_failed", "session_start_failed", "turn_start_failed", "turn_failed",
    "task_deadline_exhausted", "task_attempt_budget_exhausted", "task_deadline_state_refused",
    "rate_limited", "content_filtered", "transport_error", "timeout", "out_of_memory",
    "binary_decode_error", "syntax_error", "schema_error", "api_compatibility",
    "import_error", "permission_error", "file_not_found", "type_error", "value_error",
})
PUBLIC_FIXED = {
    "format": "codex-budget-ci-cell-completion-v1", "campaign_id": CAMPAIGN,
    "denominator": 30, "other_cells_not_run": 29, "native_state_archived": False,
    "grading_launched": False, "invoice_complete": False, "http_request_count": None,
}
HASH_FIELDS = ("plan_sha256", "config_sha256", "order_sha256", "registration_sha256",
               "host_policy_sha256", "declared_inputs_sha256", "verified_inputs_sha256")
LOG = logging.getLogger(__name__)


class CICellRefused(pilot.PilotDispatchRefused):
    """A closed, nonsecret refusal code, not a provider exception message."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CICellRefused("invalid_arguments")


def _require_ci_context(reviewed_sha: str) -> dict:
    # Check attempts before inspecting/initializing any cell state. A new runner
    # cannot restore the previous runner's inodes or grant another deadline.
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise CICellRefused("ci_rerun_refused")
    required = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": reviewed_sha, "PILOT_WORKFLOW_SHA": reviewed_sha,
        "RUNNER_OS": "Linux", "ImageOS": "ubuntu22",
    }
    if any(os.environ.get(key) != value for key, value in required.items()):
        raise CICellRefused("ci_source_ref_or_host_mismatch")
    workflow_ref = os.environ.get("GITHUB_WORKFLOW_REF", "")
    match = re.fullmatch(re.escape(REPOSITORY) + r"/(\.github/workflows/[A-Za-z0-9_-]+\.yml)@refs/heads/main", workflow_ref)
    if match is None:
        raise CICellRefused("ci_workflow_source_binding_required")
    caller = match.group(1)
    if caller != WORKFLOW:
        # GitHub resolves a relative reusable workflow at the caller's commit.
        # For this first slice accept only one same-commit, single-job caller;
        # arbitrary external/@ref callers and a multi-job chain are not supported.
        document = yaml.safe_load(pilot._read_bytes(pilot.ROOT / caller))
        jobs = document.get("jobs", {})
        if len(jobs) != 1 or next(iter(jobs.values())).get("uses") != "./" + WORKFLOW:
            raise CICellRefused("ci_reusable_caller_not_same_commit_single_cell")
    try:
        versions = (sys.version_info[:3], importlib.metadata.version("openai-codex"),
                    importlib.metadata.version("openai-codex-cli-bin"))
    except importlib.metadata.PackageNotFoundError as error:
        raise CICellRefused("ci_pinned_runtime_required") from error
    if versions != ((3, 10, 12), HOST_POLICY["sdk"], HOST_POLICY["cli"]):
        raise CICellRefused("ci_pinned_runtime_required")
    instance = {key: os.environ.get(key) for key in ("GITHUB_RUN_ID", "GITHUB_JOB", "RUNNER_NAME")}
    if not all(instance.values()) or not str(instance["GITHUB_RUN_ID"]).isdigit():
        raise CICellRefused("ci_live_host_identity_required")
    # Metadata only: never an auth store. No native state is copied between hosts.
    instance["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    if re.fullmatch(r"[0-9a-f-]{36}", instance["boot_id"]) is None:
        raise CICellRefused("ci_live_host_identity_required")
    return {"policy": HOST_POLICY, "instance_sha256": pilot._digest(instance),
            "workflow": caller, "workflow_sha": reviewed_sha, "run_attempt": 1}


def _registration_bytes() -> bytes:
    """One closed active epoch; historical registrations remain untouched."""
    registration_bytes = pilot._read_bytes(REGISTRATION)
    registration = yaml.safe_load(registration_bytes)
    expected = {
        "plan_version": "codex-external-budget-ci-cell-v1", "campaign_id": CAMPAIGN,
        "source_baseline": "c739e5596cf874ef3f48d0943404101f10500372",
        "parent_registration": str(pilot.REGISTRATION.relative_to(pilot.ROOT)),
        "host": HOST_POLICY, "default_mode": "plan_only", "selection": "one_explicit_canonical_cell",
        "controls": "inherit_parent_unchanged", "input_transfer": "explicit_approved_handoff_required",
        "publication": "private_cell_outputs_and_nonsecret_completion_envelope", "ordered_30_cell_scheduler": "not_implemented",
        "separate_manual_run_deduplication": "fixed_private_claim_cas_canonical_successor_only",
        "storage": STORAGE,
    }
    pilot._same("CI registration", {key: value for key, value in registration.items() if key != "description"}, expected)
    return registration_bytes


def compile_ci_cell(campaign: str, cell_id: str, reviewed_sha: str) -> tuple[dict, Any, dict, dict]:
    """Reuse the genuine 30-cell compiler; bind the separate host decision."""
    if campaign != CAMPAIGN:
        raise CICellRefused("registered_ci_campaign_required")
    registration_bytes = _registration_bytes()
    plan, parent, specs = pilot.compile_pilot(campaign, reviewed_sha)
    matches = [cell for cell in plan["cells"] if cell["cell_id"] == cell_id]
    if len(matches) != 1 or plan["order"].count(cell_id) != 1:
        raise CICellRefused("canonical_selected_cell_required")
    plan["ci"] = {"registration_sha256": hashlib.sha256(registration_bytes).hexdigest(),
                  "selected_cell_id": cell_id, "host": _require_ci_context(reviewed_sha)}
    return plan, parent, specs, matches[0]


def _inputs(parent: Any, sources: pilot.InputSources | None, transport: pilot.LocalTransport) -> dict:
    values = (None, None, None) if sources is None else (sources.parquet, sources.references, sources.manifest)
    missing = [role for role, path in zip(INPUT_ROLES, values)
               if path is None or not (path.is_dir() if role == "reference_only_root" else path.is_file())]
    if missing:
        LOG.error("Missing original input roles: %s", ", ".join(missing))
        raise CICellRefused("missing_original_inputs")
    try:
        verified = transport.inputs(parent, sources)
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise CICellRefused("canonical_original_inputs_refused") from error
    return {"files_sha256": pilot._digest(verified.identities()),
            "source_projection_sha256": pilot._digest(verified.snapshot.shared_binding)}


def _identity_only(value: dict | None) -> dict | None:
    return None if value is None else {key: value[key] for key in ("sha256", "size")}


def completion(plan: dict, cell: dict, *, execute: bool, state: dict | None = None,
               inputs: dict | None = None, cleanup: bool | None = None, reason: str | None = None) -> dict:
    """Project validated host facts. Never copy names, paths or free text."""
    receipt = project_cost_receipt(None if state is None else state["receipt"])
    observed_receipt = None if receipt is None else {
        "sha256": pilot._digest(receipt), "status": receipt["status"],
        "usage": {key: receipt["usage"].get(key) for key in USAGE_KEYS} if receipt["usage"] else None,
        "estimated_cost_usd": receipt["estimated_cost_usd"], "known_cost_usd": receipt["known_cost_usd"],
    }
    artifacts = {} if state is None else state["artifacts"]
    outcome = state["status"] if state is not None else "unresolved" if execute else "pending"
    if reason is not None or outcome == "running" or (execute and cleanup is not True):
        outcome = "unresolved"
    recorded_reason = reason or (None if state is None else state["reason"])
    if recorded_reason is not None and recorded_reason not in PUBLIC_REASONS:
        recorded_reason = "recorded_task_non_success"
    payload = {
        **PUBLIC_FIXED, "cell_id": cell["cell_id"], "source_sha": plan["reviewed_source_sha"],
        "plan_sha256": pilot._digest(plan), "config_sha256": cell["config_sha256"],
        "order_sha256": pilot._digest(plan["order"]), "registration_sha256": plan["ci"]["registration_sha256"],
        "host_policy_sha256": pilot._digest(HOST_POLICY), "declared_inputs_sha256": pilot._digest(plan["dataset"]),
        "verified_inputs_sha256": None if inputs is None else inputs["files_sha256"],
        "execution_requested": execute, "status": outcome, "reason": recorded_reason,
        "child_invocations": None if state is None else state["child_invocations"],
        "exit_code": None if state is None else state["exit_code"],
        "timeout": None if state is None else state["reason"] in {
            "preparation_timeout_partial_output", "child_timeout_partial_accounting"},
        "cleanup_confirmed": cleanup, "receipt": observed_receipt,
        "artifacts": {"result": _identity_only(None if state is None else state["result"]),
                      "ledger": _identity_only(artifacts.get("ledger")),
                      "deliverables": [_identity_only(row) for row in artifacts.get("deliverable_files", [])]},
    }
    return validate_completion(payload)


def validate_completion(value: dict) -> dict:
    """Closed publication vocabulary, including nested fields and numeric usage."""
    dynamic = {"cell_id", "source_sha", *HASH_FIELDS, "execution_requested", "status", "reason",
               "child_invocations", "exit_code", "timeout", "cleanup_confirmed", "receipt", "artifacts"}
    def require(condition: bool) -> None:
        if not condition:
            raise CICellRefused("unsafe_completion_envelope")

    def digest(item: Any, width: int = 64) -> bool:
        return type(item) is str and re.fullmatch(r"[0-9a-f]{" + str(width) + "}", item) is not None

    def count(item: Any) -> bool:
        return item is None or (type(item) is int and item >= 0)

    require(type(value) is dict and set(value) == set(PUBLIC_FIXED) | dynamic)
    require(all(type(value[key]) is type(expected) and value[key] == expected for key, expected in PUBLIC_FIXED.items()))
    require(type(value["cell_id"]) is str and re.fullmatch(r"[0-9a-f-]{36}_[ABC]_r[12]", value["cell_id"]) is not None)
    require(digest(value["source_sha"], 40))
    require(all(digest(value[key]) or (key == "verified_inputs_sha256" and value[key] is None) for key in HASH_FIELDS))
    require(value["host_policy_sha256"] == pilot._digest(HOST_POLICY))
    require(type(value["execution_requested"]) is bool)
    require(value["status"] in {"pending", "succeeded", "failed", "stopped", "unresolved"})
    require(value["reason"] is None or value["reason"] in PUBLIC_REASONS)
    require(count(value["child_invocations"]))
    require(value["exit_code"] is None or (type(value["exit_code"]) is int and -255 <= value["exit_code"] <= 255))
    require(all(value[key] is None or type(value[key]) is bool for key in ("timeout", "cleanup_confirmed")))
    require(value["status"] != "succeeded" or value["cleanup_confirmed"] is True)
    receipt = value["receipt"]
    if receipt is not None:
        require(type(receipt) is dict and set(receipt) == {"sha256", "status", "usage", "estimated_cost_usd", "known_cost_usd"})
        require(digest(receipt["sha256"]) and receipt["status"] in COST_STATUSES)
        usage = receipt["usage"]
        require(usage is None or (type(usage) is dict and set(usage) == set(USAGE_KEYS) and all(count(item) for item in usage.values())))
        for key in ("estimated_cost_usd", "known_cost_usd"):
            amount = receipt[key]
            require(amount is None or (type(amount) in (int, float) and math.isfinite(amount) and amount >= 0))
        require(receipt["status"] == "complete" or receipt["estimated_cost_usd"] is None)
        if receipt["status"] == "complete":
            require(receipt["estimated_cost_usd"] is not None and receipt["known_cost_usd"] == receipt["estimated_cost_usd"])
        elif receipt["status"] != "partial":
            require(receipt["known_cost_usd"] is None)
    artifacts = value["artifacts"]
    require(type(artifacts) is dict and set(artifacts) == {"result", "ledger", "deliverables"})
    require(type(artifacts["deliverables"]) is list)
    for identity in (artifacts["result"], artifacts["ledger"], *artifacts["deliverables"]):
        require(identity is None or (type(identity) is dict and set(identity) == {"sha256", "size"}
                and digest(identity["sha256"]) and type(identity["size"]) is int and identity["size"] >= 0))
    return value


def _publish(path: Path, root: Path, payload: dict) -> None:
    path = pilot._assert_no_symlink_ancestors(path)
    if path.is_relative_to(root) or root.is_relative_to(path) or path.is_relative_to(pilot.ROOT):
        raise CICellRefused("completion_must_be_separate_from_private_state_and_source")
    if os.path.lexists(path):
        prior = validate_completion(pilot._load(path))
        for key in ("campaign_id", "cell_id", "source_sha", "plan_sha256", "config_sha256"):
            if prior[key] != payload[key]:
                raise CICellRefused("completion_identity_changed")
    pilot._save(path, validate_completion(payload))


def _log_failure_category(root: Path, plan: dict, cell: dict, state: dict, record: dict) -> None:
    """One non-authoritative CLI observation with bounded failure handling."""
    evidence_unavailable = (
        'CI cell diagnostic unavailable: '
        '{"authoritative":false,"reason":"diagnostic_evidence_unavailable"}'
    )
    try:
        validate_completion(record)
        pilot._validate_state(plan, cell, state)
        if (record["cleanup_confirmed"] is not True or state["status"] not in {"failed", "stopped"}
                or state["result"] is None or state["child_invocations"] < 1):
            return
        binding = {"source_sha": plan["reviewed_source_sha"], "cell_id": cell["cell_id"], "status": state["status"]}
        pilot._same("diagnostic public binding", {key: record[key] for key in binding}, binding)
        pilot._same("diagnostic selected cell", plan["ci"]["selected_cell_id"], cell["cell_id"])
        pilot._require_quiet_owner(root, plan)
        owner = pilot._load(root / "owned-child.json")
        if owner["phase"] != "reaped" or owner["cell_id"] != cell["cell_id"] or owner["stage"] != "infer":
            return
        pilot._same("diagnostic result role", state["result"]["path"], cell["roles"]["result"])
        data = pilot._read_bytes(root / cell["roles"]["result"],
                                 sha256=state["result"]["sha256"], size=state["result"]["size"])
        checked = copy.deepcopy(state)
        pilot._finish(root, cell, checked, state["exit_code"])
        for key in ("result", "receipt", "accounting", "artifacts"):
            pilot._same("diagnostic recorded evidence", checked[key], state[key])
        # The exact bytes above are bound to the revalidated result. Discard
        # _finish's status/reason updates, including its timeout projection.
        row = project_result_row({}, pilot._json_object(data)["results"][0])
        observed = row["observability"]
        if type(observed) is not dict or row["status"] not in {"success", "error", "pending", "qa_failed"}:
            return
        category = observed.get("error_category")
        if row["status"] == "success" or category is None:
            category = "unavailable"  # A successful row cannot explain a nonzero child exit.
        elif type(category) is not str or category not in RECORDED_FAILURE_CATEGORIES:
            category = "unclassified"
        message = "CI cell recorded failure category: " + pilot._canonical_json({
            **binding, "error_category": category,
        })
    except (OSError, ValueError, TypeError, KeyError, IndexError):
        message = evidence_unavailable
    except AssertionError:
        # The supported internal assertion is distinct from unavailable input;
        # no assertion details escape. Other programming faults are not caught.
        message = (
            'CI cell diagnostic unavailable: '
            '{"authoritative":false,"reason":"diagnostic_internal_unavailable"}'
        )
    try:
        LOG.warning("%s", message)
    except (OSError, RuntimeError):
        # Supported logger failures get one fixed stderr attempt, never a
        # category retry or exception text. Only fallback I/O failure is caught.
        try:
            sys.stderr.write(
                'CI cell diagnostic unavailable: '
                '{"authoritative":false,"reason":"diagnostic_emission_unavailable"}\n'
            )
        except OSError:
            pass


def main(argv: list[str] | None = None, *, _test_transport: pilot.LocalTransport | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--campaign-id", default=CAMPAIGN)
    parser.add_argument("--cell")
    parser.add_argument("--reviewed-source-sha")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--completion-out", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Same live job/host only, never a workflow rerun")
    parser.add_argument("--check-inputs", action="store_true", help="Verify explicit originals without auth or a child")
    parser.add_argument("--output-target-check", action="store_true",
                        help="Inspect only the fixed output candidate's metadata; no inputs, model or publication")
    parser.add_argument("--output-target-setup", action="store_true",
                        help="Plan the fixed new private output target; no token or network by default")
    parser.add_argument("--create-output-target", action="store_true",
                        help="Explicit setup mutation only; requires --output-target-setup and --setup-state")
    parser.add_argument("--setup-state", type=Path, help="New absent private setup reservation/receipt directory")
    parser.add_argument("--dataset-parquet", type=Path)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--step0-manifest", type=Path)
    parser.add_argument("--verify-envelope", type=Path, help="Validate only the exact nonsecret publication file")
    plan, cell, root, inputs = None, None, None, None
    record_started = False
    try:
        args = parser.parse_args(argv)
        if ((args.create_output_target or args.setup_state is not None) and not args.output_target_setup
                or args.output_target_setup and any((args.output_target_check, args.execute, args.check_inputs,
                    args.resume, args.verify_envelope, args.dataset_parquet, args.reference_root,
                    args.step0_manifest, args.output, args.completion_out))):
            raise CICellRefused("output_target_setup_mode_conflict")
        if args.output_target_setup and args.create_output_target != (args.setup_state is not None):
            raise CICellRefused("output_target_setup_state_required")
        if args.output_target_check and any((args.execute, args.check_inputs, args.resume, args.verify_envelope,
                                            args.dataset_parquet, args.reference_root, args.step0_manifest,
                                            args.output, args.completion_out)):
            raise CICellRefused("output_target_check_mode_conflict")
        if args.verify_envelope is not None:
            validate_completion(pilot._load(args.verify_envelope))
            return 0
        if not all((args.cell, args.reviewed_source_sha)):
            raise CICellRefused("explicit_cell_and_source_required" if args.output_target_check or args.output_target_setup
                                else "explicit_cell_source_output_and_completion_required")
        if not (args.output_target_check or args.output_target_setup) and not all((args.output, args.completion_out)):
            raise CICellRefused("explicit_cell_source_output_and_completion_required")
        plan, parent, specs, cell = compile_ci_cell(args.campaign_id, args.cell, args.reviewed_source_sha)
        transport = _test_transport or pilot.LocalTransport()
        transport.require_source(plan, parent)
        if args.output_target_setup:
            from codex_budget_pilot_output import setup_output_target

            observed = setup_output_target(create=args.create_output_target, state_root=args.setup_state,
                                           source_sha=args.reviewed_source_sha)
            print(pilot._canonical_json(observed))
            return 0 if observed["outcome"] in {"plan_only", "created"} else 2
        if args.output_target_check:
            from codex_budget_pilot_output import inspect_output_target

            observed = inspect_output_target()
            print(pilot._canonical_json(observed))
            return 0 if observed["eligible_private_target"] else 2
        root = pilot._private_root(args.output)
        # The ordinary dispatcher remains responsible for ready-last creation,
        # no-clobber, the serial lock, checkpoints and the full denominator.
        summary = pilot.dispatch(plan, parent, specs, root=root, execute=False, resume=args.resume,
                                 sources=None, transport=transport, selected_cell_id=cell["cell_id"])
        previous = next(row for row in summary["cells"] if row["cell_id"] == cell["cell_id"])
        _publish(args.completion_out, root, completion(plan, cell, execute=args.execute,
                 reason="execution_not_finalized" if args.execute else None))
        record_started = True
        sources = pilot.InputSources(args.dataset_parquet, args.reference_root, args.step0_manifest)
        if args.check_inputs or args.execute:
            inputs = _inputs(parent, sources, transport)
            binding = {"plan_sha256": pilot._digest(plan), **inputs}
            admission = root / "ci-inputs.json"
            if os.path.lexists(admission):
                if pilot._load(admission) != binding:
                    raise CICellRefused("ci_input_identity_changed")
            else:
                pilot._save(admission, binding)
        if args.execute:
            from codex_budget_pilot_retention import require_admission

            # A workflow condition is not execution authority. The token-free
            # CLI checks the same-host, acknowledged remote claim before child
            # admission, including same-live-host restores of the original clock.
            if any(os.environ.get(key) for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")):
                raise CICellRefused("input_or_output_token_in_execution_environment")
            require_admission(plan, cell, root, inputs)
            summary = pilot.dispatch(plan, parent, specs, root=root, execute=True, resume=True,
                                     sources=sources, transport=transport, selected_cell_id=cell["cell_id"])
        state = next(row for row in summary["cells"] if row["cell_id"] == cell["cell_id"])
        owner = pilot._load(root / "owned-child.json")
        cleanup = owner["tree_reaped"] and owner["owner_reaped"] if owner["phase"] == "reaped" else None
        record = completion(plan, cell, execute=args.execute, state=state, inputs=inputs, cleanup=cleanup)
        _publish(args.completion_out, root, record)
        if args.execute and previous["phase"] != "finished":
            _log_failure_category(root, plan, cell, state, record)
        return int(args.execute and state["status"] != "succeeded")
    except (KeyboardInterrupt, OSError, ValueError, TypeError, KeyError) as error:
        reason = "interrupted_same_host_state_retained" if isinstance(error, KeyboardInterrupt) else (
            str(error) if isinstance(error, pilot.PilotDispatchRefused) and str(error) in PUBLIC_REASONS
            else "ci_execution_refused")
        # Do not publish a raw exception, host path, private checkpoint or argv.
        code = str(error) if isinstance(error, CICellRefused) else reason
        LOG.error("CI cell refused: %s", code)
        if record_started:
            try:
                # Host-only reporting of already persisted facts, never result
                # reconstruction, accounting replay, or native admission.
                state, cleanup = None, None
                try:
                    pilot._same("CI retained plan", pilot._load(root / "plan.json"), plan)
                    retained = pilot._load(root / cell["roles"]["checkpoint"])
                    pilot._validate_state(plan, cell, retained)
                    state = retained
                    try:
                        pilot._require_quiet_owner(root, plan)
                        owner = pilot._load(root / "owned-child.json")
                        cleanup = True if owner["phase"] == "reaped" else None
                    except pilot.OwnedChildCleanupRefused:
                        cleanup = False
                except (OSError, ValueError, TypeError, KeyError):
                    state, cleanup = None, None
                _publish(args.completion_out, root, completion(plan, cell, execute=args.execute,
                         state=state, inputs=inputs, cleanup=cleanup, reason=reason))
            except (OSError, ValueError, TypeError, KeyError):
                LOG.error("Completion unavailable; retain private state without publishing it")
        return 130 if isinstance(error, KeyboardInterrupt) else 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
