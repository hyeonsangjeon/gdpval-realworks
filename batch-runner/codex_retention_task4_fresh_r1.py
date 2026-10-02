"""Closed Task4 fresh/r1 successor on the existing one-use inference branch.

The ordinal-zero CLI delegates unchanged. This facade adds only ordinal one;
neither planning nor predecessor observation authorizes an execution. The
same-run owner approval, source/runtime checks and owned child remain shared.
There is no scheduler, claim adoption, retry, grading or mutable-head fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
import re
import sys

import codex_retention_ci as ci

controller, preparation, registration = ci.controller, ci.preparation, ci.registration
owned, retained, output, historical = ci.owned, ci.retained, ci.output, ci.historical
ROOT = preparation.ROOT
FACADE = "batch-runner/codex_retention_task4_fresh_r1.py"
CELL_ID = controller.FRESH_CELL_ID
PREFIX = "retention-diagnostics/" + registration.CAMPAIGN + "/" + CELL_ID
CLAIM, TERMINAL, OUTPUT = (PREFIX + suffix for suffix in ("/admission.json", "/terminal.json", "/outputs"))
PACKET_ROLE = "batch-runner/workspace/retention-ci-task4-fresh-r1"
REQUEST_FORMAT = "retention-task4-fresh-r1-execution-request-v1"
CLAIM_FORMAT = "retention-task4-fresh-r1-claim-v1"
TERMINAL_FORMAT = "retention-task4-fresh-r1-terminal-v1"
OUTPUT_FORMAT = "retention-task4-fresh-r1-output-v1"
SCOPE = {**ci.SCOPE, "cell_id": CELL_ID, "ordinal": 1, "retention_bundle": "fresh"}
PREDECESSOR = {
    "cell_id": controller.FIRST_CELL_ID,
    "producer_source_sha": "e355faf9a6212175a288e8473968915ffb2408d0",
    "run_id": "36696961231",
    "request_sha256": "ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68",
    "terminal_commit": "de50ff0aa6037c0ef6e3b713da519359abd1d08d",
    "terminal_identity": {"sha256": "0821af11393cab65d1e14259e43b14872b94a431496e8c1e3c38e719f33f21b8", "size": 6449},
    "claim_commit": "3fc283087a020caec574e8c9b8e9bc3ca593e88a",
    "output_commit": "43cbf8e265297813857172ecee51256cc17f2d36",
}


def source_identity():
    files = {FACADE: owned._identity(preparation._read(ROOT / FACADE, "successor_source"))}
    return {"files": files, "sha256": owned._digest(files), "reviewed": False}


def canonical_request(request, *, reviewed_source_sha, run_id, historical_root):
    ci.require(type(request) is controller.Request and request.cell_id == CELL_ID,
               "only_registered_task4_fresh_r1_supported")
    ci.require(type(run_id) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None,
               "exact_github_run_required")
    source = ci.require_source(reviewed_source_sha)
    source["successor_adapter"] = source_identity()
    stage = controller.verify_staged_runtime(request)
    observation = historical.observe(historical_root, request.sources)
    ci.require(request.packet == ROOT / PACKET_ROLE, "fixed_materialized_packet_role_required")
    ci.same("fresh_stage_cell_mismatch", [stage["cell_id"], stage["ordinal"]], [CELL_ID, 1])
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
    ci.same("fresh_predecessor_head_mismatch", parent, PREDECESSOR["terminal_commit"])
    terminal, _ = retained._control(api, repo, parent, ci.TERMINAL,
        ci._cache(cache, "pinned-terminal"), token, deadline,
        expected=PREDECESSOR["terminal_identity"], written_at=parent)
    ci.same("fresh_predecessor_links_mismatch",
        [terminal["claim_commit"], terminal["output_commit"], terminal["authority"]["provider_run_id"],
         terminal["authority"]["request_sha256"]],
        [PREDECESSOR["claim_commit"], PREDECESSOR["output_commit"], PREDECESSOR["run_id"],
         PREDECESSOR["request_sha256"]])
    observed = ci.verify_terminal(api, repo, parent, None, ci._cache(cache, "terminal-contract"), token, deadline,
        expectation=ci.TerminalExpectation(PREDECESSOR["request_sha256"], PREDECESSOR["producer_source_sha"],
                                           PREDECESSOR["cell_id"]))
    ci.require(observed["completion"]["status"] == "succeeded"
               and observed["completion"]["exit_code"] == 0, "successful_predecessor_required")
    return dict(PREDECESSOR)


@dataclass(frozen=True)
class _PublicationBinding:
    """Source-defined publication values only; no admission policy or callbacks."""

    cell_id: str
    claim: str
    terminal: str
    output: str
    claim_format: str
    terminal_format: str
    output_format: str
    predecessor: bytes
    commit_message: str


def _publication_binding():
    return _PublicationBinding(CELL_ID, CLAIM, TERMINAL, OUTPUT, CLAIM_FORMAT, TERMINAL_FORMAT,
                               OUTPUT_FORMAT, retained._encoded(PREDECESSOR), "Retain Task4 fresh/r1 output")


def _publication_task_id(binding):
    """Only these source-defined successor cells use this publication verifier."""
    tasks = {
        controller.FRESH_CELL_ID: registration.TASK4,
        controller.FRESH_R2_CELL_ID: registration.TASK4,
        controller.KEEP_R2_CELL_ID: registration.TASK4,
        controller.TASK5_FRESH_R1_CELL_ID: registration.TASK5,
        controller.TASK5_KEEP_R1_CELL_ID: registration.TASK5,
    }
    ci.require(type(binding) is _PublicationBinding and type(binding.cell_id) is str
               and binding.cell_id in tasks, "fixed_retention_publication_binding_required")
    return tasks[binding.cell_id]


def verify_terminal(api, repo, revision, expected_terminal, expected_claim, cache, token, deadline):
    return _verify_publication(api, repo, revision, expected_terminal, expected_claim, cache, token, deadline,
                               _publication_binding())


def _verify_publication(api, repo, revision, expected_terminal, expected_claim, cache, token, deadline, binding):
    """Reconcile exact writer bytes/history, never turn observation into an ack.

    Expected controls come from the owner's retained local publication records,
    not a newly adopted claim or a mutable latest lookup. This cannot run a child.
    """
    task_id = _publication_task_id(binding)
    CELL_ID, CLAIM, TERMINAL, OUTPUT = binding.cell_id, binding.claim, binding.terminal, binding.output
    CLAIM_FORMAT, TERMINAL_FORMAT, OUTPUT_FORMAT = binding.claim_format, binding.terminal_format, binding.output_format
    PREDECESSOR = owned._json_object(binding.predecessor)
    ci.require(output._hash(revision, 40), "immutable_fresh_terminal_required")
    ci.require(set(expected_terminal) == {"format", "request_sha256", "authority", "scope", "claim_commit",
               "claim_identity", "output_commit", "output_objects", "completion", "publication_acknowledged"}
               and set(expected_claim) == {"format", "request_sha256", "authority", "scope", "expected_parent",
                                          "predecessor", "model_result", "grade"}
               and expected_terminal["format"] == TERMINAL_FORMAT
               and expected_claim["format"] == CLAIM_FORMAT
               and expected_claim["predecessor"] == PREDECESSOR
               and expected_claim["expected_parent"] == PREDECESSOR["terminal_commit"]
               and expected_claim["model_result"] is False and expected_claim["grade"] is None
               and expected_claim["scope"] == "existing_inference_branch_one_use_remote_cas"
               and expected_terminal["publication_acknowledged"] is True,
               "fresh_publication_binding_mismatch")
    summary = expected_terminal["completion"]
    ci.require(set(summary) == {"format", "request_sha256", "source_sha", "cell_id", "status", "exit_code",
        "cleanup_confirmed", "accounting", "receipt", "grade", "grading_launched", "invoice_complete", "missing", "files"}
        and summary["cell_id"] == CELL_ID and summary["format"] == OUTPUT_FORMAT
        and summary["request_sha256"] == expected_claim["request_sha256"]
        and output._hash(summary["request_sha256"]) and output._hash(summary["source_sha"], 40)
        and summary["status"] in owned.TERMINAL and summary["cleanup_confirmed"] is True
        and summary["grade"] is None and summary["grading_launched"] is False and summary["invoice_complete"] is False
        and (summary["exit_code"] is None or type(summary["exit_code"]) is int), "fresh_completion_mismatch")
    receipt = ci.project_cost_receipt(summary["receipt"])
    ci.same("fresh_accounting_mismatch", summary["receipt"], receipt)
    ci.require(summary["accounting"] == ("missing" if receipt is None else receipt["status"]), "fresh_accounting_mismatch")
    files = summary["files"]
    ci.require(type(files) is list and len(files) <= output.MAX_FILES + 2, "fresh_output_bounds_exceeded")
    for record in files:
        ci.require(type(record) is dict and set(record) == {"path", "size", "sha256"}
            and type(record["size"]) is int and 0 <= record["size"] <= output.MAX_FILE_BYTES
            and output._hash(record["sha256"]), "fresh_output_identity_refused")
        name = record["path"]
        ci.require(name in {"step2_inference_results.json", Path(owned.LEDGER).name}
            or ci.canonical_deliverable_path(task_id, name) == name, "fresh_output_role_refused")
    names = [record["path"] for record in files]
    ci.require(names == sorted(set(names)) and sum(item["size"] for item in files) <= output.MAX_TOTAL_BYTES,
               "fresh_output_bounds_exceeded")
    missing = ([] if "step2_inference_results.json" in names else ["bound_inference_result", "validated_deliverables"])
    if missing:
        ci.require(summary["status"] in {"failed", "stopped"} and files == [], "missing_result_not_success")
    missing += ([] if Path(owned.LEDGER).name in names else ["bound_ledger_export"])
    missing += ([] if receipt is not None and receipt["usage"] is not None else ["usage"])
    ci.same("fresh_missing_accounting_mismatch", summary["missing"], missing)
    terminal, _ = retained._control(api, repo, revision, TERMINAL, cache, token, deadline, written_at=revision)
    ci.same("fresh_terminal_readback_mismatch", terminal, expected_terminal)
    claim_revision, output_revision = terminal["claim_commit"], terminal["output_commit"]
    ci.require(all(output._hash(value, 40) for value in (claim_revision, output_revision))
               and len({revision, claim_revision, output_revision, PREDECESSOR["terminal_commit"]}) == 4,
               "fresh_publication_revisions_mismatch")
    claim, claim_bytes = retained._control(api, repo, claim_revision, CLAIM, cache, token, deadline,
        expected=terminal["claim_identity"], written_at=claim_revision)
    ci.same("fresh_claim_readback_mismatch", claim, expected_claim)
    for key in ("request_sha256", "authority", "scope"):
        ci.same("fresh_terminal_claim_mismatch", terminal[key], claim[key])
    summary, summary_bytes = retained._control(api, repo, output_revision, OUTPUT + "/" + output.MANIFEST,
        cache, token, deadline, written_at=output_revision)
    ci.same("fresh_summary_readback_mismatch", summary, terminal["completion"])
    expected = {OUTPUT + "/" + item["path"]: {key: item[key] for key in ("size", "sha256")}
                for item in summary["files"]}
    expected[OUTPUT + "/" + output.MANIFEST] = owned._identity(summary_bytes)
    objects = terminal["output_objects"]
    ci.require(len(objects) == len(expected)
               and {item["path"]: {key: item[key] for key in ("size", "sha256")} for item in objects} == expected,
               "fresh_output_objects_mismatch")
    for head in (output_revision, revision):
        retained._objects(api, repo, head, objects, token, deadline, written_at=output_revision)
    retained._objects(api, repo, revision, [retained._object(CLAIM, claim_bytes)], token, deadline,
                      written_at=claim_revision)
    return {"terminal_commit": revision, "completion": summary, "observation_only": True,
            "writer_acknowledgment": "not_established", "replay_authorized": False}


class _FreshAdmission(ci._Admission):
    """Fixed successor CAS/publication; reuse the existing grant continuation."""

    def admit(self, host):
        ci.same("external_grant_changed_before_claim", ci.verify_approval(self.document, self.transport), self.authority)
        retained._write(host / "remote-admission-reserved.json", {"outcome": "unresolved", **self.binding})
        cache = ci._cache(host, "claim-verification")
        result = {"outcome": "unresolved", "stage": "predecessor", "reason": None,
                  "returned_commit": None, "claim": None}
        try:
            with retained._session(self.api) as (api, token, deadline):
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
        return _finish_publication(self, host, state, _publication_binding())


def _finish_publication(self, host, state, binding):
    """Shared unchanged writer sequence; fixed adapters supply only publication values."""
    CLAIM, TERMINAL, OUTPUT = binding.claim, binding.terminal, binding.output
    TERMINAL_FORMAT, OUTPUT_FORMAT = binding.terminal_format, binding.output_format
    summary, files = ci._snapshot(host, self.request, self.document, state)
    summary["format"] = OUTPUT_FORMAT
    retained._write(host / "remote-terminal-reserved.json", {"outcome": "unresolved", **self.binding})
    cache = ci._cache(host, "terminal-verification")
    result = {"outcome": "unresolved", "stage": "output", "reason": None,
              "output_commit": None, "terminal_commit": None, "completion": summary}
    try:
        with retained._session(self.api) as (api, token, deadline):
            repo, parent = retained._target(), self.receipt["returned_commit"]
            ci.require(output._metadata(api, repo, ci.BRANCH, token, deadline)["sha"] == parent,
                       "retention_output_parent_changed")
            ci._absent(api, repo, parent, [OUTPUT, TERMINAL], token)
            claim, _ = retained._control(api, repo, parent, CLAIM, cache, token, deadline, written_at=parent)
            ci.same("retention_claim_changed", claim, self.receipt["claim"])
            payloads = {**files, output.MANIFEST: retained._encoded(summary)}
            staged = tuple(ci._PublicationFile(OUTPUT + "/" + name, io.BytesIO(data), len(data),
                hashlib.sha256(data).hexdigest()) for name, data in payloads.items())
            objects = [retained._object(OUTPUT + "/" + name, data) for name, data in sorted(payloads.items())]
            try:
                operations = ci._publication_additions(staged)
                response = api.create_commit(repo_id=repo, repo_type="dataset", revision=ci.BRANCH, token=token,
                    parent_commit=parent, operations=operations, commit_message=binding.commit_message,
                    num_threads=1, run_as_future=False, create_pr=False)
                revision = getattr(response, "oid", None)
                ci.require(output._hash(revision, 40) and revision != parent
                           and not any(getattr(item, "_should_ignore", False) for item in operations),
                           "retention_output_acknowledgment_missing")
            finally:
                for item in staged:
                    item.stream.close()
            result["output_commit"] = revision
            retained._objects(api, repo, revision, objects, token, deadline, written_at=revision)
            ci.require(output._metadata(api, repo, ci.BRANCH, token, deadline)["sha"] == revision,
                       "retention_terminal_parent_changed")
            terminal = {"format": TERMINAL_FORMAT, **self.binding, "claim_commit": parent,
                "claim_identity": owned._identity(retained._encoded(claim)), "output_commit": revision,
                "output_objects": objects, "completion": summary, "publication_acknowledged": True}
            # Retain the exact expected bytes before the single terminal write.
            # A lost response remains unresolved even if a later read sees them.
            retained._write(host / "remote-terminal-expected.json", terminal)
            result["stage"] = "terminal"
            result["terminal_commit"] = retained._commit(api, repo, revision, TERMINAL, terminal, cache, token, deadline)
            observed = _verify_publication(api, repo, result["terminal_commit"], terminal, claim,
                ci._cache(host, "terminal-readback"), token, deadline, binding)
            ci.same("retention_terminal_readback_changed", observed["completion"], summary)
            result.update(outcome="acknowledged", stage="terminal_verified")
    except (Exception, KeyboardInterrupt) as error:
        result["reason"] = str(error) if isinstance(error, ci.RetentionCIRefused) else output._error_context(error)[0]
    retained._write(host / "remote-terminal-receipt.json", result)
    ci.require(result["outcome"] == "acknowledged", "retention_terminal_unresolved:" + str(result["reason"]))
    return result


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
    admission = _FreshAdmission(request, document, observation, authority, transport, _test_api)
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
        if args.cell not in (controller.FIRST_CELL_ID, CELL_ID):
            raise controller.RetentionControllerRefused("only_first_or_task4_fresh_r1_supported")
        if args.cell == controller.FIRST_CELL_ID:
            return ci.main(argv)
        ci.require(not args.observe_locator, "fresh_locator_observation_not_supported")
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
    from codex_retention_task4_fresh_r1 import main as canonical_main

    raise SystemExit(canonical_main())
