"""Closed Task5 fresh/r1 admission after the consumed, cleaned-up keep/r2 result.

This is registered ordinal four, not a retry or another experimental condition.
Old selectors delegate unchanged. The shared controller owns staging, the
cumulative clock, fresh within-cell recovery and owned-child cleanup. Only the
fixed predecessor's controls/metadata are read before one-use serial CAS.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys

import codex_retention_task4_keep_r2 as previous

fresh, reader = previous.fresh, previous.reader
ci, controller, preparation, registration = previous.ci, previous.controller, previous.preparation, previous.registration
owned, retained, output, historical = previous.owned, previous.retained, previous.output, previous.historical
ROOT = preparation.ROOT
FACADE = "batch-runner/codex_retention_task5_fresh_r1.py"
SOURCE_PATHS = (FACADE, *previous.SOURCE_PATHS)
CELL_ID = controller.TASK5_FRESH_R1_CELL_ID
PREFIX = "retention-diagnostics/" + registration.CAMPAIGN + "/" + CELL_ID
CLAIM, TERMINAL, OUTPUT = (PREFIX + suffix for suffix in ("/admission.json", "/terminal.json", "/outputs"))
PACKET_ROLE = "batch-runner/workspace/retention-ci-task5-fresh-r1"
REQUEST_FORMAT = "retention-task5-fresh-r1-execution-request-v1"
CLAIM_FORMAT = "retention-task5-fresh-r1-claim-v1"
TERMINAL_FORMAT = "retention-task5-fresh-r1-terminal-v1"
OUTPUT_FORMAT = "retention-task5-fresh-r1-output-v1"
SCOPE = {**ci.SCOPE, "cell_id": CELL_ID, "ordinal": 4, "retention_bundle": "fresh"}
PREDECESSOR = {
    "cell_id": "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2",
    "producer_source_sha": "b8351e561acb9675a4993419e819c12787b5b305",
    "run_id": "36947454688", "execution_job_id": 110660390316,
    "request_sha256": "8a06cc7df34cbf10896b635f6c8d9ad4e91313d3c685511f8fc5c159cb6ddec1",
    "terminal_commit": "e55fac5d60191167dd66688510ec0fef472e594d",
    "terminal_identity": {"sha256": "70fb8778ae15e369ef1ac4d03dbe4fa6f5d9852966b250fa812695d6bd77bf91", "size": 5885},
    "claim_commit": "f29f8d4a19710aa0e832dba720ff7d32701c309c",
    "claim_identity": {"sha256": "4af63e82ddcaf2b795595081c59d29369e2bf2a4bb2c37f81eb7f5409cd6b363", "size": 1888},
    "output_commit": "54a4362ce3554b7c71b5ada00802efc9521038e6",
    "output_manifest_identity": {"sha256": "93e1dada24779909cfc593dff7507b7f9c6452c6f36c12b2c5e86305e35d9a8c", "size": 2679},
    "output_objects_sha256": "4bda1c0d48a5dd980bd683a6f8316b3d52808e95dca68099b86ad4de2d3e03b2",
    "status": "succeeded", "exit_code": 0, "cleanup_confirmed": True,
}


def source_identity():
    files = {role: owned._identity(preparation._read(ROOT / role, "successor_source")) for role in SOURCE_PATHS}
    return {"files": files, "sha256": owned._digest(files), "reviewed": False}


def canonical_request(request, *, reviewed_source_sha, run_id, historical_root):
    ci.require(type(request) is controller.Request and request.cell_id == CELL_ID,
               "only_registered_task5_fresh_r1_supported")
    ci.require(type(run_id) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None,
               "exact_github_run_required")
    source = ci.require_source(reviewed_source_sha)
    source["successor_adapter"] = source_identity()
    stage = controller.verify_staged_runtime(request)
    observation = historical.observe(historical_root, request.sources)
    ci.require(request.packet == ROOT / PACKET_ROLE, "fixed_materialized_packet_role_required")
    ci.same("task5_fresh_r1_stage_cell_mismatch", [stage["cell_id"], stage["ordinal"]], [CELL_ID, 4])
    document = {
        "format": REQUEST_FORMAT, "scope": SCOPE, "source": source,
        **{key: stage[key] for key in ("plan_sha256", "packet_sha256", "config_sha256", "input_roles_sha256",
            "selected_task", "grading", "compiler_source", "preparer_source", "controller_source")},
        "stage_sha256": owned._digest(stage),
        "historical_observer_sha256": owned._digest(observation),
        "historical_observer_source": historical.SOURCE, "historical_producer_source": historical.PRODUCER,
        "provider": {"repository": ci.REPOSITORY, "workflow": ci.WORKFLOW, "run_id": run_id,
            "attempt": 1, "event": "workflow_dispatch", "ref": "refs/heads/main",
            "approval_environment": ci.ENVIRONMENT, "execution_job": ci.EXECUTE_JOB},
        "host": {"runner_label": "ubuntu-22.04", "python": "3.10.12", "sdk": "0.147.0", "cli": "0.147.0",
            "identity": "provider_authenticated_same_run_execution_job",
            "origin_witness": "github_rs256_job_oidc_request_job_and_local_boot_audience",
            "trust_boundary": "github_job_scoped_issuance_credential_not_hardware_attestation",
            "cross_runner_restore": False, "job_minutes": 240},
        "deployment": registration.compile_plan()["common"]["model"],
        "azure_identity_sha256": owned._digest(ci.azure_identity.expected_identity(os.environ)),
        "serial_domain": {"repository_name_sha256": retained.TARGET_SHA256, "branch": ci.BRANCH,
            "prefix": PREFIX, "predecessor": PREDECESSOR},
        "preparation_is_admission": False,
    }
    return document, observation


def _predecessor(api, repo, parent, cache, token, deadline):
    ci.same("task5_fresh_r1_predecessor_head_mismatch", parent, PREDECESSOR["terminal_commit"])
    terminal, data, _, _ = reader._verify_terminal(
        api, repo, parent, cache, token, deadline, binding=reader.KEEP_R2)
    summary = terminal["completion"]
    # Successful control verification is not result intake: the shared verifier
    # reads terminal/claim/manifest bodies and object metadata/history only.
    # Independent expectations stay fixed; neither grade terminal is a parent.
    ci.same("task5_fresh_r1_predecessor_identity_mismatch", {
        "cell_id": summary["cell_id"], "producer_source_sha": summary["source_sha"],
        "run_id": terminal["authority"]["provider_run_id"],
        "execution_job_id": terminal["authority"]["provider_job_id"],
        "request_sha256": terminal["request_sha256"],
        "terminal_commit": parent, "terminal_identity": owned._identity(data),
        "claim_commit": terminal["claim_commit"], "claim_identity": terminal["claim_identity"],
        "output_commit": terminal["output_commit"],
        "output_manifest_identity": owned._identity(retained._encoded(summary)),
        "output_objects_sha256": owned._digest(terminal["output_objects"]),
        "status": summary["status"], "exit_code": summary["exit_code"],
        "cleanup_confirmed": summary["cleanup_confirmed"],
    }, PREDECESSOR)
    return dict(PREDECESSOR)


def _publication_binding():
    return fresh._PublicationBinding(CELL_ID, CLAIM, TERMINAL, OUTPUT, CLAIM_FORMAT, TERMINAL_FORMAT,
        OUTPUT_FORMAT, retained._encoded(PREDECESSOR), "Retain Task5 fresh/r1 output")


def verify_terminal(api, repo, revision, expected_terminal, expected_claim, cache, token, deadline):
    return fresh._verify_publication(api, repo, revision, expected_terminal, expected_claim, cache, token, deadline,
                                     _publication_binding())


class _Task5FreshR1Admission(ci._Admission):
    """Exact successful keep/r2 parent; shared one-use continuation/publication."""

    def admit(self, host):
        ci.same("external_grant_changed_before_claim", ci.verify_approval(self.document, self.transport), self.authority)
        retained._write(host / "remote-admission-reserved.json", {"outcome": "unresolved", **self.binding})
        cache = ci._cache(host, "claim-verification")
        result = {"outcome": "unresolved", "stage": "predecessor", "reason": None,
                  "returned_commit": None, "claim": None}
        try:
            with retained._session(self.api, response_bytes_limit=output.MAX_MANIFEST_BYTES) as (api, token, deadline):
                repo = retained._target()
                parent = output._metadata(api, repo, ci.BRANCH, token, deadline)["sha"]
                predecessor = _predecessor(api, repo, parent, cache, token, deadline)
                ci._absent(api, repo, parent, [PREFIX], token)
                claim = {"format": CLAIM_FORMAT, **self.binding, "expected_parent": parent,
                         "predecessor": predecessor, "model_result": False, "grade": None}
                result.update(stage="claim", claim=claim)
                result["returned_commit"] = retained._commit(api, repo, parent, CLAIM, claim, cache, token, deadline)
                result.update(outcome="acknowledged", stage="claim_verified")
        except (Exception, KeyboardInterrupt) as error:
            result["reason"] = str(error) if isinstance(error, ci.RetentionCIRefused) else output._error_context(error)[0]
        retained._write(host / "remote-admission-receipt.json", result)
        ci.require(result["outcome"] == "acknowledged", "retention_claim_unresolved:" + str(result["reason"]))
        self.receipt = result

    def finish(self, host, state):
        return fresh._finish_publication(self, host, state, _publication_binding())


def execute(request, *, host_state, grant, _test_transport=None, _test_api=None):
    controller._context(request)
    ci.require(type(grant) is ci.ExecutionGrantRequest, "retention_execution_grant_required")
    ci.require(output._hash(grant.request_sha256), "exact_retention_request_digest_required")
    document, observation = canonical_request(request, reviewed_source_sha=grant.reviewed_source_sha,
        run_id=os.environ.get("GITHUB_RUN_ID", ""), historical_root=grant.historical_root)
    ci.same("approved_retention_request_changed", owned._digest(document), grant.request_sha256)
    transport = ci.LocalTransport() if _test_transport is None else _test_transport
    ci.require(isinstance(transport, ci.LocalTransport) and type(transport).child is owned.LocalTransport.child,
               "retention_owned_child_transport_required")
    authority = ci.verify_approval(document, transport)
    ci.require_runtime(document, request, transport)
    admission = _Task5FreshR1Admission(request, document, observation, authority, transport, _test_api)
    state = controller._run_post_authority_cell(request, host_state=host_state, _admission=admission)
    with retained._lock(Path(host_state)):
        terminal = admission.finish(Path(host_state), state)
    return {"cell_id": request.cell_id, "status": state["status"], "request_sha256": grant.request_sha256,
            "cleanup_confirmed": True, "remote_terminal": terminal["outcome"],
            "grade": None, "grading_launched": False, "invoice_complete": False}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = output._Parser(description=__doc__)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--cell", default=controller.FIRST_CELL_ID)
    for name in ("historical-root", "original-root", "request-out", "host-state"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--request-sha256")
    mode = parser.add_mutually_exclusive_group()
    for name in ("prepare", "verify-approval", "execute", "observe-locator"):
        mode.add_argument("--" + name, action="store_true")
    try:
        args = parser.parse_args(argv)
        controller.cell_binding(args.cell)
        if args.cell in (controller.FIRST_CELL_ID, fresh.CELL_ID, previous.previous.CELL_ID, previous.CELL_ID):
            return previous.main(argv)
        ci.require(args.cell == CELL_ID, "only_registered_task5_fresh_r1_supported")
        ci.require(not args.observe_locator, "task5_fresh_r1_locator_observation_not_supported")
        source = ci.require_source(args.reviewed_source_sha)
        source["successor_adapter"] = source_identity()
        registration.compile_plan()
        if not (args.prepare or args.verify_approval or args.execute):
            print(owned._canonical_json({"mode": "plan_only", "source": source, "scope": SCOPE,
                "commands": [], "launch_authorized": False, "transfer_attempted": False}))
            return 0
        ci.require(args.historical_root is not None and args.original_root is not None,
                   "explicit_prepared_originals_required")
        original = preparation._path(args.original_root)
        request = controller.Request(CELL_ID, preparation.PreparedInputs(preparation._path(args.historical_root),
            original / "original.parquet", original / "reference-only", original / "step0-manifest.json"),
            ROOT / PACKET_ROLE, ROOT, preparation.source_identity()["sha256"], controller.source_identity()["sha256"])
        if args.prepare:
            ci.require(args.request_out is not None, "explicit_request_record_required")
            preparation.prepare_packet(cell_id=CELL_ID, sources=request.sources, output=request.packet,
                expected_preparer_sha256=request.expected_preparer_sha256)
            controller.stage_runtime(request)
            document, _ = canonical_request(request, reviewed_source_sha=args.reviewed_source_sha,
                run_id=os.environ.get("GITHUB_RUN_ID", ""), historical_root=args.historical_root)
            destination = preparation._path(args.request_out)
            with ci._publication_parents(destination.parent) as (_, _, directory_fd):
                ci._write_no_clobber(destination, retained._encoded(document), parent_fd=directory_fd(destination.parent))
            print(owned._canonical_json({"mode": "prepared_not_admitted", "request_sha256": owned._digest(document),
                "launch_authorized": False, "source_sha": args.reviewed_source_sha, "scope": SCOPE,
                "materialized_grader_source_sha256": document["grading"]["materialized_grader_source_sha256"]}))
        elif args.verify_approval:
            document, _ = canonical_request(request, reviewed_source_sha=args.reviewed_source_sha,
                run_id=os.environ.get("GITHUB_RUN_ID", ""), historical_root=args.historical_root)
            ci.same("approved_retention_request_changed", owned._digest(document), args.request_sha256)
            ci.verify_approval(document, ci.LocalTransport())
            print(owned._canonical_json({"approval_verified": True, "admission_attempted": False,
                                        "request_sha256": args.request_sha256}))
        else:
            ci.require(args.host_state is not None, "explicit_host_state_required")
            result = execute(request, host_state=args.host_state, grant=ci.ExecutionGrantRequest(
                args.reviewed_source_sha, args.request_sha256, args.historical_root))
            print(owned._canonical_json(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(owned._canonical_json(ci._refusal_payload(error)))
        return 2


if __name__ == "__main__":
    from codex_retention_task5_fresh_r1 import main as canonical_main

    raise SystemExit(canonical_main())
