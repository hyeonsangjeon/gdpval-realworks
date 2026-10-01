"""Read only the fixed Task4 fresh/r1 inference publication; never execute it.

One terminal-path discovery is allowed, then only immutable declared reads.
The fixed producer/request expectations are independent of fetched records.
This is publication-derived evidence, not provider authentication, a writer
acknowledgment, original-input verification, execution authority or a grade.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import codex_retention_result_intake as intake
import codex_retention_task4_fresh_r1 as fresh
from core.inference_manifest import bind_deliverable_file_records
from ghcp_vm_input_bundle import _destination, _path, _publication_parents, _write_no_clobber

ci, retained, output, owned = intake.ci, intake.retained, intake.output, intake.owned
PRODUCER_SOURCE = "e39d8d1aadcb816d09588829a5ec4929b33083e6"
REQUEST_SHA256 = "5bbb0e4cb5ae9444eac9c804ac3c8d2f6d39acbec63e7f7de78d7f2ee35fcf02"
RUN_ID = "36845127347"
EXPECTATION = ci.TerminalExpectation(REQUEST_SHA256, PRODUCER_SOURCE, fresh.CELL_ID)
EXPECTED_PROVIDER = {"workflow_id": 370228282, "workflow": ci.WORKFLOW, "run_id": RUN_ID, "attempt": 1}
SUPPLIED_REQUEST_BINDING = {
    "original_input_bundle_sha256": "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3",
    "materialized_grader_source_sha256": "298da1d3a36482cf87e7f896d47c8c6c64bf5e1df91dd244847640d9d00a3689",
}
FROZEN = {
    "intake_sha256": (intake.__file__, "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196"),
    "ci_sha256": (ci.__file__, "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c"),
    "producer_facade_sha256": (fresh.__file__, "0cf9fdabd985ba4b5c838c3b661317efd1eb6ee6163463b49585a720b7ae6d76"),
    "controller_sha256": (intake.controller.__file__, "57f463c7e1e079b2e87248af87885ffb7d927f13ec32a107f0f3da41a9971fab"),
}
FORMAT = "retention-task4-fresh-r1-result-intake-v1"
MARKER = "retention-fresh-r1-result-intake.json"
TERMINAL_FORMAT = "retention-task4-fresh-r1-terminal-observation-v1"
TERMINAL_MARKER = "retention-fresh-r1-terminal-observation.json"
EXPECTED_EXECUTION_JOB_ID = 110323708382
require = output._require


def reader_identity() -> dict:
    return {name: hashlib.sha256(output._bytes(Path(path), limit=output.MAX_RECORD_BYTES)).hexdigest()
            for name, path in {"module_sha256": __file__, **{key: pair[0] for key, pair in FROZEN.items()}}.items()}


def _binding(expectation, expected_reader_sha256, terminal_revision, discover_terminal):
    require(type(expectation) is ci.TerminalExpectation, "fresh_result_expectation_required")
    require(output._hash(expectation.source_sha, 40) and expectation.source_sha == PRODUCER_SOURCE,
            "fresh_result_expected_producer_mismatch")
    require(output._hash(expectation.request_sha256) and expectation.request_sha256 == REQUEST_SHA256,
            "fresh_result_expected_request_mismatch")
    require(type(expectation.cell_id) is str and expectation.cell_id == fresh.CELL_ID, "fresh_result_expected_cell_mismatch")
    require(type(discover_terminal) is bool and (
        (discover_terminal and terminal_revision is None)
        or (not discover_terminal and output._hash(terminal_revision, 40))),
        "one_terminal_revision_or_discovery_required")
    source = reader_identity()
    require(output._hash(expected_reader_sha256) and source["module_sha256"] == expected_reader_sha256
            and all(source[name] == pair[1] for name, pair in FROZEN.items()), "fresh_result_reader_bytes_mismatch")
    plan = intake.registration.compile_plan()
    cell = intake.controller._adapted_cell(plan["cells"][1])
    require(plan["campaign_id"] == intake.registration.CAMPAIGN
            and cell["cell_id"] == fresh.CELL_ID and cell["index"] == 1
            and cell["control"] == {"condition": "retention_bundle_v1", "retention_bundle": "fresh", "repetition": 1},
            "fresh_result_registered_cell_mismatch")
    return source, plan, cell


def _terminal_revision(api, repo, revision, discover, token, deadline):
    from huggingface_hub import RepoFile

    if not discover:
        return revision
    output._remaining(deadline)
    found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=retained.BRANCH,
                              paths=[fresh.TERMINAL], expand=True, token=token)
    require(type(found) is list and len(found) == 1 and isinstance(found[0], RepoFile),
            "fresh_result_terminal_not_ready")
    item = found[0]
    require(item.path == fresh.TERMINAL and item.lfs is None and output._hash(item.blob_id, 40)
            and type(item.size) is int and 0 < item.size <= output.MAX_MANIFEST_BYTES,
            "fresh_result_terminal_metadata_refused")
    revision = getattr(item.last_commit, "oid", None)
    require(output._hash(revision, 40), "fresh_result_terminal_revision_missing")
    output._remaining(deadline)
    return revision


def _authority(authority):
    require(type(authority) is dict and set(authority) == {
        "request_sha256", "provider_run_id", "provider_job_id", "runner_id", "host_instance_sha256",
        "job_origin", "review_sha256", "reviewer", "environment"}, "fresh_result_authority_schema_refused")
    require(authority["request_sha256"] == REQUEST_SHA256 and authority["provider_run_id"] == RUN_ID
            and type(authority["provider_job_id"]) is int and authority["provider_job_id"] > 0
            and type(authority["runner_id"]) is int and authority["runner_id"] > 0
            and authority["reviewer"] == ci.OWNER and authority["environment"] == ci.ENVIRONMENT
            and output._hash(authority["host_instance_sha256"]) and output._hash(authority["review_sha256"]),
            "fresh_result_authority_binding_mismatch")
    origin = authority["job_origin"]
    require(type(origin) is dict and set(origin) == {"issuer", "scope_sha256", "host_instance_sha256"}
            and origin["issuer"] == ci.OIDC_ISSUER and output._hash(origin["scope_sha256"])
            and origin["host_instance_sha256"] == authority["host_instance_sha256"], "fresh_result_origin_mismatch")


def _summary_identity(summary):
    require(type(summary) is dict and set(summary) == {"format", "request_sha256", "source_sha", "cell_id",
        "status", "exit_code", "cleanup_confirmed", "accounting", "receipt", "grade", "grading_launched",
        "invoice_complete", "missing", "files"}
        and summary["format"] == fresh.OUTPUT_FORMAT and summary["request_sha256"] == REQUEST_SHA256
        and summary["source_sha"] == PRODUCER_SOURCE and summary["cell_id"] == fresh.CELL_ID
        and summary["cleanup_confirmed"] is True and summary["grade"] is None
        and summary["grading_launched"] is False and summary["invoice_complete"] is False,
        "fresh_result_completion_mismatch")


def _summary_files(summary):
    receipt = ci.project_cost_receipt(summary["receipt"])
    require(owned._canonical_json(summary["receipt"]) == owned._canonical_json(receipt) and summary["accounting"] == (
        "missing" if receipt is None else receipt["status"]), "fresh_result_accounting_mismatch")
    files = summary["files"]
    require(type(files) is list and len(files) <= output.MAX_FILES + 2, "fresh_result_output_bounds_exceeded")
    for record in files:
        require(type(record) is dict and set(record) == {"path", "size", "sha256"}
                and type(record["path"]) is str and type(record["size"]) is int
                and 0 <= record["size"] <= output.MAX_FILE_BYTES and output._hash(record["sha256"]),
                "fresh_result_output_identity_refused")
    names = [record["path"] for record in files]
    require(names == sorted(set(names)) and sum(item["size"] for item in files) <= output.MAX_TOTAL_BYTES,
            "fresh_result_output_bounds_exceeded")
    return receipt, names


def _summary(summary):
    _summary_identity(summary)
    require(summary["status"] == "succeeded" and (summary["exit_code"] is None
            or (type(summary["exit_code"]) is int and summary["exit_code"] == 0)), "fresh_result_success_required")
    receipt, names = _summary_files(summary)
    roles, deliverables = intake._roles(summary)
    missing = ([] if intake.LEDGER in names else ["bound_ledger_export"])
    missing += ([] if receipt is not None and receipt["usage"] is not None else ["usage"])
    require(summary["missing"] == missing, "fresh_result_missing_accounting_mismatch")
    return roles, deliverables


def _terminal_summary(summary):
    """Validate unsuccessful declarations, never the contents of their payloads."""
    _summary_identity(summary)
    require(summary["status"] in {"failed", "stopped"} and (summary["exit_code"] is None
            or type(summary["exit_code"]) is int), "fresh_terminal_unsuccessful_required")
    receipt, names = _summary_files(summary)
    roles = {item["path"]: item for item in summary["files"]}
    deliverables = []
    for name, record in roles.items():
        if name in (intake.RESULT, intake.LEDGER):
            require((1 if name == intake.RESULT else 0) <= record["size"] <= output.MAX_RECORD_BYTES,
                    "retention_result_record_bounds_exceeded")
        else:
            require(intake.canonical_deliverable_path(intake.registration.TASK4, name) == name,
                    "retention_result_role_refused")
            require(not {part.lower() for part in Path(name).parts} & intake.PRIVATE_PARTS
                    and Path(name).suffix.lower() not in {".sqlite", ".sqlite3", ".db"},
                    "retention_result_private_state_refused")
            deliverables.append(name)
    require(len(deliverables) <= output.MAX_FILES, "retention_result_deliverable_count_exceeded")
    missing = [] if intake.RESULT in roles else ["bound_inference_result", "validated_deliverables"]
    require(not missing or not roles, "fresh_terminal_missing_result_roles")
    missing += ([] if intake.LEDGER in names else ["bound_ledger_export"])
    missing += ([] if receipt is not None and receipt["usage"] is not None else ["usage"])
    require(summary["missing"] == missing, "fresh_result_missing_accounting_mismatch")
    return roles, deliverables


def _verify_terminal(api, repo, head, cache, token, deadline, *, terminal_only=False):
    """Independent fixed-record checks, not the writer's expected-byte verifier."""
    require(type(terminal_only) is bool, "explicit_terminal_observation_required")
    terminal, terminal_bytes = retained._control(api, repo, head, fresh.TERMINAL, cache, token, deadline,
                                                 written_at=head)
    require(set(terminal) == {"format", "request_sha256", "authority", "scope", "claim_commit", "claim_identity",
        "output_commit", "output_objects", "completion", "publication_acknowledged"}
        and terminal["format"] == fresh.TERMINAL_FORMAT and terminal["request_sha256"] == REQUEST_SHA256
        and terminal["scope"] == "existing_inference_branch_one_use_remote_cas"
        and terminal["publication_acknowledged"] is True, "fresh_result_terminal_binding_mismatch")
    _authority(terminal["authority"])
    if terminal_only:
        require(terminal["authority"]["provider_job_id"] == EXPECTED_EXECUTION_JOB_ID,
                "fresh_terminal_execution_job_mismatch")
        roles, deliverables = _terminal_summary(terminal["completion"])
    else:
        roles, deliverables = _summary(terminal["completion"])
    claim_head, output_head = terminal["claim_commit"], terminal["output_commit"]
    require(all(output._hash(value, 40) for value in (claim_head, output_head))
            and len({head, claim_head, output_head, fresh.PREDECESSOR["terminal_commit"]}) == 4,
            "fresh_result_publication_revisions_mismatch")
    claim, claim_bytes = retained._control(api, repo, claim_head, fresh.CLAIM, cache, token, deadline,
        expected=terminal["claim_identity"], written_at=claim_head)
    require(set(claim) == {"format", "request_sha256", "authority", "scope", "expected_parent", "predecessor",
                          "model_result", "grade"} and claim["format"] == fresh.CLAIM_FORMAT
            and claim["model_result"] is False and claim["grade"] is None, "fresh_result_claim_schema_refused")
    require(all(owned._canonical_json(claim[key]) == owned._canonical_json(terminal[key])
                for key in ("request_sha256", "authority", "scope")),
            "fresh_result_terminal_claim_mismatch")
    require(owned._canonical_json(claim["predecessor"]) == owned._canonical_json(fresh.PREDECESSOR)
            and claim["expected_parent"] == fresh.PREDECESSOR["terminal_commit"], "fresh_result_predecessor_mismatch")
    summary, summary_bytes = retained._control(api, repo, output_head, fresh.OUTPUT + "/" + output.MANIFEST,
                                               cache, token, deadline, written_at=output_head)
    require(summary_bytes == retained._encoded(terminal["completion"]), "fresh_result_summary_readback_mismatch")
    expected = {fresh.OUTPUT + "/" + name: {key: item[key] for key in ("size", "sha256")}
                for name, item in roles.items()}
    expected[fresh.OUTPUT + "/" + output.MANIFEST] = owned._identity(summary_bytes)
    objects = terminal["output_objects"]
    require(type(objects) is list and len(objects) == len(expected), "fresh_result_output_objects_mismatch")
    for item in objects:
        require(type(item) is dict and set(item) == {"path", "size", "sha256", "git_blob_sha1"}
                and type(item["path"]) is str and type(item["size"]) is int
                and 0 <= item["size"] <= output.MAX_FILE_BYTES and output._hash(item["sha256"])
                and output._hash(item["git_blob_sha1"], 40), "fresh_result_output_objects_mismatch")
    require([item["path"] for item in objects] == sorted(expected)
            and {item["path"]: {key: item[key] for key in ("size", "sha256")} for item in objects} == expected,
            "fresh_result_output_objects_mismatch")
    for revision in (output_head, head):
        retained._objects(api, repo, revision, objects, token, deadline, written_at=output_head)
    retained._objects(api, repo, head, [retained._object(fresh.CLAIM, claim_bytes)], token, deadline,
                      written_at=claim_head)
    return terminal, terminal_bytes, roles, deliverables


def read_result(*, expectation: ci.TerminalExpectation, destination: Path, expected_reader_sha256: str,
                terminal_revision: str | None = None, discover_terminal: bool = False, _test_api=None) -> dict:
    source, plan, cell = _binding(expectation, expected_reader_sha256, terminal_revision, discover_terminal)
    require(isinstance(destination, Path) and destination.is_absolute(), "explicit_absolute_destination_required")
    destination, _ = _destination(destination)
    require(not os.path.lexists(destination), "new_result_destination_required")
    with _publication_parents(destination.parent) as (check, mkdir, directory_fd):
        mkdir(destination)
        cache = destination / intake.CACHE
        mkdir(cache)
        for name in ("controls", "payloads"):
            mkdir(cache / name)
        with retained._session(_test_api, response_bytes_limit=output.MAX_FILE_BYTES) as (api, token, deadline):
            repo = retained._target()
            head = _terminal_revision(api, repo, terminal_revision, discover_terminal, token, deadline)
            check()
            terminal, terminal_bytes, roles, deliverables = _verify_terminal(
                api, repo, head, cache / "controls", token, deadline)
            check()
            summary, files = terminal["completion"], {}
            for name, identity in roles.items():
                check()
                files[name] = intake.retained_reader._fetch(api, repo, head, fresh.OUTPUT + "/" + name, identity,
                                                            cache / "payloads", token, deadline)
                check()
            value, result = intake._payload(files, summary, plan, cell, roles, deliverables)
            output._remaining(deadline)
        # Held-directory, no-clobber publication and exact readback, as in the
        # frozen first intake. Any failed/ambiguous destination remains private.
        files[output.MANIFEST] = retained._encoded(summary)
        directories = {destination}
        for name, data in sorted(files.items()):
            target = _path(destination, name)
            for parent in reversed(target.parents):
                if parent.is_relative_to(destination) and parent not in directories:
                    mkdir(parent)
                    directories.add(parent)
            check()
            _write_no_clobber(target, data, parent_fd=directory_fd(target.parent))
            os.fsync(directory_fd(target.parent))
        for name, data in files.items():
            check()
            output._bytes(_path(destination, name), limit=output.MAX_FILE_BYTES, expected=owned._identity(data))
        require(bind_deliverable_file_records(value["results"], destination)[0]["deliverable_file_records"]
                == value["results"][0].get("deliverable_file_records", []), "fresh_result_readback_mismatch")
        require(reader_identity() == source, "fresh_result_reader_changed")
        record = {
            "format": FORMAT, "evidence_only": True, "consumer_readback_required": True,
            "campaign": intake.registration.CAMPAIGN, "ordinal": 1, "cell_id": fresh.CELL_ID,
            "producer_source_sha": PRODUCER_SOURCE, "request_sha256": REQUEST_SHA256, "reader": source,
            "expected_provider": EXPECTED_PROVIDER, "supplied_request_binding": SUPPLIED_REQUEST_BINDING,
            "recorded_provider_run_id": terminal["authority"]["provider_run_id"],
            "recorded_provider_job_id": terminal["authority"]["provider_job_id"],
            "terminal_commit": head, "terminal_identity": owned._identity(terminal_bytes),
            "claim_commit": terminal["claim_commit"], "claim_identity": terminal["claim_identity"],
            "output_commit": terminal["output_commit"], "output_manifest_identity": owned._identity(files[output.MANIFEST]),
            "output_objects_sha256": owned._digest(terminal["output_objects"]),
            "retained_authority_sha256": owned._digest(terminal["authority"]), "predecessor": fresh.PREDECESSOR,
            "proof": "verified_publication_derived_not_independent_provider_authentication",
            "fresh_origin_authentication": False, "prepared_input_independently_verified": False,
            "git_parent_cas_independently_verified": False, "writer_acknowledgment": "not_established",
            "recorded_publication_acknowledged": True, "cleanup_confirmed": True,
            "result": result, "files": summary["files"], "status": summary["status"],
            "accounting": summary["accounting"], "receipt": summary["receipt"], "missing": summary["missing"],
            "http_request_count": None, "grade": None, "grading_launched": False, "invoice_complete": False,
            "launch_authorized": False, "admission_attempted": False, "replay_authorized": False, "commands": [],
        }
        encoded = retained._encoded(record)
        check()
        for directory in directories | {destination.parent}:
            os.fsync(directory_fd(directory))
        try:
            _write_no_clobber(destination / MARKER, encoded, parent_fd=directory_fd(destination))
            os.fsync(directory_fd(destination))
            output._bytes(destination / MARKER, limit=output.MAX_MANIFEST_BYTES, expected=owned._identity(encoded))
            check()
        except (OSError, ValueError, KeyboardInterrupt) as error:
            raise output.OutputPublicationRefused("fresh_result_completion_acknowledgment_unconfirmed") from error
        return {**record, "intake_verified": True, "intake_sha256": owned._identity(encoded)["sha256"]}


def observe_terminal(*, expectation: ci.TerminalExpectation, destination: Path, expected_reader_sha256: str,
                     terminal_revision: str | None = None, discover_terminal: bool = False, _test_api=None) -> dict:
    """Read three control bodies and declared-object metadata; no payload intake."""
    source, _, _ = _binding(expectation, expected_reader_sha256, terminal_revision, discover_terminal)
    require(isinstance(destination, Path) and destination.is_absolute(), "explicit_absolute_destination_required")
    destination, _ = _destination(destination)
    require(not os.path.lexists(destination), "new_result_destination_required")
    with _publication_parents(destination.parent) as (check, mkdir, directory_fd):
        mkdir(destination)
        cache = destination / intake.CACHE
        mkdir(cache)
        mkdir(cache / "controls")
        with retained._session(_test_api, response_bytes_limit=output.MAX_MANIFEST_BYTES) as (api, token, deadline):
            repo = retained._target()
            head = _terminal_revision(api, repo, terminal_revision, discover_terminal, token, deadline)
            check()
            terminal, terminal_bytes, roles, deliverables = _verify_terminal(
                api, repo, head, cache / "controls", token, deadline, terminal_only=True)
            check()
            output._remaining(deadline)
        require(reader_identity() == source, "fresh_result_reader_changed")
        summary = terminal["completion"]
        record = {
            "format": TERMINAL_FORMAT, "evidence_only": True, "observation_only": True,
            "campaign": intake.registration.CAMPAIGN, "ordinal": 1, "cell_id": fresh.CELL_ID,
            "producer_source_sha": PRODUCER_SOURCE, "request_sha256": REQUEST_SHA256, "reader": source,
            "expected_provider": EXPECTED_PROVIDER, "expected_execution_job_id": EXPECTED_EXECUTION_JOB_ID,
            "supplied_request_binding": SUPPLIED_REQUEST_BINDING,
            "recorded_provider_run_id": terminal["authority"]["provider_run_id"],
            "recorded_provider_job_id": terminal["authority"]["provider_job_id"],
            "terminal_commit": head, "terminal_identity": owned._identity(terminal_bytes),
            "claim_commit": terminal["claim_commit"], "claim_identity": terminal["claim_identity"],
            "output_commit": terminal["output_commit"],
            "output_manifest_identity": owned._identity(retained._encoded(summary)),
            "output_objects_sha256": owned._digest(terminal["output_objects"]),
            "retained_authority_sha256": owned._digest(terminal["authority"]), "predecessor": fresh.PREDECESSOR,
            "proof": "verified_publication_derived_not_independent_provider_authentication",
            "fresh_origin_authentication": False, "prepared_input_independently_verified": False,
            "git_parent_cas_independently_verified": False, "writer_acknowledgment": "not_established",
            "recorded_publication_acknowledged": True, "cleanup_confirmed": True,
            "status": summary["status"], "exit_code": summary["exit_code"],
            "declared_payload_roles": {"inference_result": int(intake.RESULT in roles),
                "ledger": int(intake.LEDGER in roles), "deliverables": len(deliverables)},
            "declared_output_object_count": len(terminal["output_objects"]),
            "payload_bodies_verified": False, "grading_input_ready": False,
            "accounting": summary["accounting"], "receipt": summary["receipt"], "missing": summary["missing"],
            "unavailable": {name: {"status": "unavailable", "value": None,
                "reason": "not_recorded_in_terminal_controls"} for name in ("detailed_failure", "budget", "recovery_exposure")},
            "http_request_count": None, "grade": None, "grading_launched": False, "invoice_complete": False,
            "launch_authorized": False, "admission_attempted": False, "replay_authorized": False, "commands": [],
        }
        encoded = retained._encoded(record)
        check()
        for directory in (destination.parent, destination, cache, cache / "controls"):
            os.fsync(directory_fd(directory))
        try:
            _write_no_clobber(destination / TERMINAL_MARKER, encoded, parent_fd=directory_fd(destination))
            os.fsync(directory_fd(destination))
            output._bytes(destination / TERMINAL_MARKER, limit=output.MAX_MANIFEST_BYTES, expected=owned._identity(encoded))
            check()
        except (OSError, ValueError, KeyboardInterrupt) as error:
            raise output.OutputPublicationRefused("fresh_terminal_observation_unconfirmed") from error
        return {**record, "outcome": "terminal_verified", "terminal_verified": True,
                "observation_sha256": owned._identity(encoded)["sha256"]}


def main(argv=None, *, _test_api=None) -> int:
    observing = False
    try:
        parser = output._Parser(description=__doc__)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--read", action="store_true")
        mode.add_argument("--observe-terminal", action="store_true")
        parser.add_argument("--output", type=Path)
        parser.add_argument("--expected-producer-source")
        parser.add_argument("--expected-request-sha256")
        parser.add_argument("--cell-id")
        parser.add_argument("--expected-reader-sha256")
        selection = parser.add_mutually_exclusive_group()
        selection.add_argument("--terminal-revision")
        selection.add_argument("--discover-terminal", action="store_true")
        args = parser.parse_args(argv)
        observing = args.observe_terminal
        if not (args.read or observing):
            require(not any((args.output, args.expected_producer_source, args.expected_request_sha256,
                args.cell_id, args.expected_reader_sha256, args.terminal_revision, args.discover_terminal)),
                "explicit_fresh_result_read_required")
            result = {"mode": "plan", "read_attempted": False, "producer_source_sha": PRODUCER_SOURCE,
                "request_sha256": REQUEST_SHA256, "cell_id": fresh.CELL_ID, "reader": reader_identity(),
                "expected_provider": EXPECTED_PROVIDER, "grade": None, "invoice_complete": False}
        elif observing:
            result = observe_terminal(expectation=ci.TerminalExpectation(args.expected_request_sha256,
                args.expected_producer_source, args.cell_id), destination=args.output,
                expected_reader_sha256=args.expected_reader_sha256, terminal_revision=args.terminal_revision,
                discover_terminal=args.discover_terminal, _test_api=_test_api)
            result["mode"] = "observe_terminal"
        else:
            record = read_result(expectation=ci.TerminalExpectation(args.expected_request_sha256,
                args.expected_producer_source, args.cell_id), destination=args.output,
                expected_reader_sha256=args.expected_reader_sha256, terminal_revision=args.terminal_revision,
                discover_terminal=args.discover_terminal, _test_api=_test_api)
            result = {key: value for key, value in record.items() if key not in {"files", "result"}}
            result["result"] = {key: value for key, value in record["result"].items()
                                if key != "recorded_publication_generation"}
            result["mode"] = "read"
        result.update(launch_authorized=False, grading_launched=False, admission_attempted=False,
                      replay_authorized=False, commands=[])
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, KeyboardInterrupt) as error:
        # Only these constant reasons may leave the private reader; never raw
        # exception text/arguments, payloads, paths or upstream HTTP bodies.
        public = {"invalid_arguments", "explicit_fresh_result_read_required", "explicit_hf_token_required",
                  "fresh_result_terminal_not_ready", "fresh_result_success_required",
                  "fresh_result_completion_acknowledgment_unconfirmed", "fresh_terminal_unsuccessful_required",
                  "fresh_terminal_observation_unconfirmed"}
        reason = error.args[0] if (type(error) is output.OutputPublicationRefused and len(error.args) == 1
            and type(error.args[0]) is str and error.args[0] in public) else (
                "fresh_terminal_observation_refused" if observing else "fresh_result_intake_refused")
        print(json.dumps({("terminal_verified" if observing else "intake_verified"): False,
            "reason": reason, "launch_authorized": False,
            "grading_launched": False, "admission_attempted": False, "replay_authorized": False,
            "grade": None, "invoice_complete": False, "commands": []}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
