"""Read only the first successful retention result, never admit or grade a cell.

Default CLI use is local planning. Explicit reading requires the supplied exact
producer/request/cell expectations and a fresh private destination. These are
byte bindings, not execution authority or fresh authentication of retained CI
evidence. Only the fixed terminal path may be discovered; all subsequent reads
use immutable revisions. Partial destinations are retained and cannot be reused.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import codex_budget_pilot as owned
import codex_budget_pilot_grading as retained_reader
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_retention_ci as ci
import codex_retention_diagnostic as registration
import codex_retention_first_cell as controller
from core.inference_manifest import bind_deliverable_file_records, canonical_deliverable_path
from core.publication_generation import validate_publication_generation
from core.result_fingerprint import validate_inference_result_fingerprint
from core.result_projection import project_result_row
from ghcp_vm_input_bundle import _destination, _path, _publication_parents, _write_no_clobber

# Supplied successful producer observation, not a new launch registration.
PRODUCER_SOURCE = "e355faf9a6212175a288e8473968915ffb2408d0"
REQUEST_SHA256 = "ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68"
RUN_ID = "36696961231"
JOB_ID = 109837605787
EXPECTATION = ci.TerminalExpectation(REQUEST_SHA256, PRODUCER_SOURCE, controller.FIRST_CELL_ID)
RESULT = "step2_inference_results.json"
LEDGER = Path(owned.LEDGER).name
MARKER = "retention-result-intake.json"
CACHE = ".retained-read-cache"
FORMAT = "retention-first-cell-result-intake-v1"
PRIVATE_PARTS = frozenset({
    "home", "codex_home", "native_home", ".codex", ".ssh", ".azure",
    "auth.json", "credentials", "credentials.json", "transcripts",
    "transcript.jsonl", "native-transcript.jsonl", "native-transcript.json",
})
require = output._require


def reader_identity() -> dict:
    """Actual reader/verifier bytes, separate from the original producer SHA."""
    return {name: hashlib.sha256(output._bytes(Path(path), limit=output.MAX_RECORD_BYTES)).hexdigest()
            for name, path in (("module_sha256", __file__), ("terminal_verifier_sha256", ci.__file__))}


def _binding(expectation, expected_reader_sha256, terminal_revision, discover_terminal):
    require(type(expectation) is ci.TerminalExpectation, "retention_result_expectation_required")
    require(output._hash(expectation.source_sha, 40) and expectation.source_sha == PRODUCER_SOURCE,
            "retention_result_expected_producer_mismatch")
    require(output._hash(expectation.request_sha256) and expectation.request_sha256 == REQUEST_SHA256,
            "retention_result_expected_request_mismatch")
    require(type(expectation.cell_id) is str and expectation.cell_id == controller.FIRST_CELL_ID,
            "retention_result_expected_cell_mismatch")
    require(type(discover_terminal) is bool and (
        (discover_terminal and terminal_revision is None)
        or (not discover_terminal and output._hash(terminal_revision, 40))),
        "one_terminal_revision_or_discovery_required")
    source = reader_identity()
    require(output._hash(expected_reader_sha256) and source["module_sha256"] == expected_reader_sha256,
            "retention_result_reader_bytes_mismatch")
    plan = registration.compile_plan()
    cell = controller._adapted_cell(plan["cells"][0])
    require(cell["cell_id"] == expectation.cell_id and cell["index"] == 0,
            "retention_result_registered_cell_mismatch")
    return source, plan, cell


def _terminal_revision(api, repo, revision, discover, token, deadline):
    """One exact path lookup, not a mutable listing or a history search."""
    from huggingface_hub import RepoFile

    if not discover:
        return revision
    output._remaining(deadline)
    found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=retained.BRANCH,
                              paths=[ci.TERMINAL], expand=True, token=token)
    require(type(found) is list and len(found) == 1 and isinstance(found[0], RepoFile),
            "retention_result_terminal_missing")
    item = found[0]
    require(item.path == ci.TERMINAL and item.lfs is None and output._hash(item.blob_id, 40)
            and type(item.size) is int and 0 < item.size <= output.MAX_MANIFEST_BYTES,
            "retention_result_terminal_metadata_refused")
    revision = getattr(item.last_commit, "oid", None)
    require(output._hash(revision, 40), "retention_result_terminal_revision_missing")
    output._remaining(deadline)
    return revision


def _authority(terminal):
    """Check retained hash-only origin evidence, not a fresh signed-token grant."""
    authority = terminal["authority"]
    require(type(authority) is dict and set(authority) == {
        "request_sha256", "provider_run_id", "provider_job_id", "runner_id", "host_instance_sha256",
        "job_origin", "review_sha256", "reviewer", "environment"}, "retention_result_authority_schema_refused")
    require(authority["request_sha256"] == REQUEST_SHA256 and authority["provider_run_id"] == RUN_ID
            and type(authority["provider_job_id"]) is int and authority["provider_job_id"] == JOB_ID
            and type(authority["runner_id"]) is int and authority["runner_id"] > 0
            and authority["reviewer"] == ci.OWNER and authority["environment"] == ci.ENVIRONMENT
            and output._hash(authority["host_instance_sha256"]) and output._hash(authority["review_sha256"]),
            "retention_result_authority_binding_mismatch")
    origin = authority["job_origin"]
    require(type(origin) is dict and set(origin) == {"issuer", "scope_sha256", "host_instance_sha256"}
            and origin["issuer"] == ci.OIDC_ISSUER and output._hash(origin["scope_sha256"])
            and origin["host_instance_sha256"] == authority["host_instance_sha256"],
            "retention_result_job_origin_mismatch")


def _roles(summary):
    require(summary["status"] == "succeeded" and summary["exit_code"] in (None, 0),
            "retention_result_success_required")
    records = summary["files"]
    roles = {record["path"]: record for record in records}
    require(RESULT in roles, "retention_result_payload_required")
    deliverables = []
    for name, record in roles.items():
        if name in (RESULT, LEDGER):
            require((1 if name == RESULT else 0) <= record["size"] <= output.MAX_RECORD_BYTES,
                    "retention_result_record_bounds_exceeded")
        else:
            require(canonical_deliverable_path(registration.TASK4, name) == name,
                    "retention_result_role_refused")
            require(not {part.lower() for part in Path(name).parts} & PRIVATE_PARTS
                    and Path(name).suffix.lower() not in {".sqlite", ".sqlite3", ".db"},
                    "retention_result_private_state_refused")
            deliverables.append(name)
    require(len(deliverables) <= output.MAX_FILES, "retention_result_deliverable_count_exceeded")
    # verify_terminal already enforces canonical unique paths, per-file 64 MiB,
    # aggregate 128 MiB, output-object identity and history at both revisions.
    return roles, deliverables


def _payload(files, summary, plan, cell, roles, deliverables):
    value = owned._json_object(files[RESULT])
    fingerprint = validate_inference_result_fingerprint(value)
    output._safe_record(value)
    require(set(value) <= output.RESULT_FIELDS, "unsafe_result_fields")
    for key, expected in {
        "run_id": cell["run_id"], "experiment_id": cell["run_id"], "condition_identity": "condition_a",
        "execution_mode": "codex_foundry", "ordered_task_ids": [cell["task_id"]], "model": "gpt-5.4",
    }.items():
        require(value.get(key) == expected, "retention_result_runtime_identity_mismatch")
    require(output._hash(value.get("prepared_fingerprint")), "retention_result_prepared_identity_refused")
    generation = validate_publication_generation(value.get("publication_generation"))
    require(type(value.get("results")) is list and len(value["results"]) == 1
            and type(value["results"][0]) is dict, "retention_result_one_row_required")
    row = value["results"][0]
    require(row.get("task_id") == cell["task_id"] and set(row) <= output.ROW_FIELDS
            and not row.get("failure_evidence") and row.get("usage") is None
            and not row.get("reflection_history") and row.get("reflection_attempts", 0) == 0,
            "unsafe_result_fields")
    output._receipt_fields(row.get("problem_solving_cost"))
    projected = project_result_row({}, row)
    require(projected["status"] == "success" and projected.get("problem_solving_cost") == summary["receipt"],
            "retention_result_status_or_receipt_mismatch")
    names = row.get("deliverable_files")
    require(type(names) is list and all(type(name) is str for name in names)
            and len(names) == len(deliverables) and set(names) == set(deliverables)
            and row.get("deliverable_file_records", []) == [roles[name] for name in names],
            "retention_result_deliverable_binding_mismatch")
    if "source" in value:
        require(value["source"] == plan["inputs"]["repo_id"], "result_source_mismatch")
    if "summary" in value:
        require(type(value["summary"]) is dict and set(value["summary"]) <= {
            "total", "success", "error", "qa_failed", "problem_solving_cost"}, "unsafe_result_summary")
        output._receipt_fields(value["summary"].get("problem_solving_cost"))
    if "azure_ai_routes" in value:
        require(output.canonicalize_azure_ai_routes(value["azure_ai_routes"]) == value["azure_ai_routes"],
                "unsafe_result_routes")
    if "observability" in row:
        from step2_run_inference import _build_execution_observability

        observed = row["observability"]
        require(type(observed) is dict and observed.get("preprocessors", []) == [], "unsafe_result_observability")
        require(observed == _build_execution_observability({
            "error_category": observed.get("error_category"), "execution_metrics": observed.get("execution_metrics"),
            "codex_diagnostics": observed.get("codex"), "task_deadline": observed.get("task_deadline"),
            "budget_metrics": observed.get("budget_metrics"), "substrate_manifest": observed.get("substrate"),
        }, []), "unsafe_result_observability")
    require(not row.get("error") or row["error"] == output.public_task_error_text(row["error"]), "unsafe_result_error")
    ledger = value.get("cost_ledger")
    require((ledger is not None) == (LEDGER in files), "retention_result_ledger_binding_mismatch")
    if ledger is not None:
        require(type(ledger) is dict and set(ledger) == {"path", "sha256"}
                and ledger["path"] == LEDGER and ledger["sha256"] == roles[LEDGER]["sha256"],
                "retention_result_ledger_binding_mismatch")
        output._ledger(files[LEDGER], cell)
    require(all(not data.startswith(b"SQLite format 3\0") for data in files.values()),
            "retention_result_private_state_refused")
    return value, {**owned._identity(files[RESULT]), "result_fingerprint": fingerprint,
                   "recorded_prepared_fingerprint": value["prepared_fingerprint"],
                   "recorded_publication_generation": generation, "registered_config_sha256": cell["config_sha256"]}


def read_result(*, expectation: ci.TerminalExpectation, destination: Path, expected_reader_sha256: str,
                terminal_revision: str | None = None, discover_terminal: bool = False, _test_api=None) -> dict:
    """Explicit, bounded immutable intake. No remote mutation or execution path."""
    source, plan, cell = _binding(expectation, expected_reader_sha256, terminal_revision, discover_terminal)
    require(isinstance(destination, Path) and destination.is_absolute(), "explicit_absolute_destination_required")
    destination, _ = _destination(destination)
    require(not os.path.lexists(destination), "new_result_destination_required")
    with _publication_parents(destination.parent) as (check, mkdir, directory_fd):
        mkdir(destination)
        cache = destination / CACHE
        mkdir(cache)
        # The existing SDK caches are pathname-based, with post-download
        # containment checks, not an FD-confined downloader. Hold/check each
        # fresh sub-cache root; final publication is caller-held-FD anchored.
        for name in ("verification", "evidence", "payloads"):
            mkdir(cache / name)
        with retained._session(_test_api, response_bytes_limit=output.MAX_FILE_BYTES) as (api, token, deadline):
            repo = retained._target()
            head = _terminal_revision(api, repo, terminal_revision, discover_terminal, token, deadline)
            check()
            verified = ci.verify_terminal(api, repo, head, None, cache / "verification", token, deadline,
                                          expectation=expectation)
            check()
            terminal, terminal_bytes = retained._control(api, repo, head, ci.TERMINAL, cache / "evidence",
                                                        token, deadline, written_at=head)
            check()
            require(terminal["request_sha256"] == verified["request_sha256"]
                    and terminal["completion"] == verified["completion"], "retention_result_evidence_changed")
            _authority(terminal)
            summary = verified["completion"]
            roles, deliverables = _roles(summary)
            files = {}
            for name, identity in roles.items():
                check()
                files[name] = retained_reader._fetch(api, repo, head, ci.OUTPUT + "/" + name, identity,
                                                     cache / "payloads", token, deadline)
                check()
            value, result = _payload(files, summary, plan, cell, roles, deliverables)
            output._remaining(deadline)
        # No more remote reads. Verify every published byte before evidence, using
        # the same held output-directory identities from exclusive creation.
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
                == value["results"][0].get("deliverable_file_records", []), "retention_result_readback_mismatch")
        require(reader_identity() == source, "retention_result_reader_changed")
        record = {
            "format": FORMAT, "evidence_only": True, "consumer_readback_required": True,
            "producer_source_sha": PRODUCER_SOURCE,
            "request_sha256": REQUEST_SHA256, "cell_id": controller.FIRST_CELL_ID,
            "provider_run_id": RUN_ID, "provider_job_id": JOB_ID, "provider_run_attempt": 1,
            "reader": source, "terminal_commit": head, "terminal_identity": owned._identity(terminal_bytes),
            "claim_commit": terminal["claim_commit"], "claim_identity": terminal["claim_identity"],
            "output_commit": terminal["output_commit"], "output_manifest_identity": owned._identity(files[output.MANIFEST]),
            "output_objects_sha256": owned._digest(terminal["output_objects"]),
            "retained_authority_sha256": owned._digest(terminal["authority"]),
            "fresh_origin_authentication": False, "prepared_input_independently_verified": False,
            "result": result, "files": summary["files"], "status": summary["status"],
            "cleanup_confirmed": True, "remote_terminal": "acknowledged",
            "accounting": summary["accounting"], "receipt": summary["receipt"], "missing": summary["missing"],
            "grade": None, "grading_launched": False, "invoice_complete": False,
            "launch_authorized": False, "admission_attempted": False, "replay_authorized": False, "commands": [],
        }
        encoded = retained._encoded(record)
        check()
        for directory in directories | {destination.parent}:
            os.fsync(directory_fd(directory))
        # The marker contains evidence, not a readiness assertion. A link may
        # succeed before fsync/readback fails. Retain that ambiguous partial;
        # only a separately returned, hash-bound receipt acknowledges intake.
        try:
            _write_no_clobber(destination / MARKER, encoded, parent_fd=directory_fd(destination))
            os.fsync(directory_fd(destination))
            output._bytes(destination / MARKER, limit=output.MAX_MANIFEST_BYTES, expected=owned._identity(encoded))
            check()
        except (OSError, ValueError, KeyboardInterrupt) as error:
            raise output.OutputPublicationRefused("retention_result_completion_acknowledgment_unconfirmed") from error
        return {**record, "intake_verified": True, "intake_sha256": owned._identity(encoded)["sha256"]}


def main(argv=None, *, _test_api=None) -> int:
    try:
        parser = output._Parser(description=__doc__)
        parser.add_argument("--read", action="store_true")
        parser.add_argument("--output", type=Path)
        parser.add_argument("--expected-producer-source")
        parser.add_argument("--expected-request-sha256")
        parser.add_argument("--cell-id")
        parser.add_argument("--expected-reader-sha256")
        selection = parser.add_mutually_exclusive_group()
        selection.add_argument("--terminal-revision")
        selection.add_argument("--discover-terminal", action="store_true")
        args = parser.parse_args(argv)
        if not args.read:
            require(not any((args.output, args.expected_producer_source, args.expected_request_sha256,
                             args.cell_id, args.expected_reader_sha256, args.terminal_revision, args.discover_terminal)),
                    "explicit_retention_result_read_required")
            result = {"mode": "plan", "read_attempted": False, "producer_source_sha": PRODUCER_SOURCE,
                      "request_sha256": REQUEST_SHA256, "cell_id": controller.FIRST_CELL_ID,
                      "reader": reader_identity(), "grade": None, "invoice_complete": False}
        else:
            record = read_result(expectation=ci.TerminalExpectation(args.expected_request_sha256,
                args.expected_producer_source, args.cell_id), destination=args.output,
                expected_reader_sha256=args.expected_reader_sha256, terminal_revision=args.terminal_revision,
                discover_terminal=args.discover_terminal, _test_api=_test_api)
            result = {key: record[key] for key in ("producer_source_sha", "request_sha256", "cell_id", "reader",
                "terminal_commit", "terminal_identity", "claim_commit", "output_commit", "output_manifest_identity",
                "result", "status", "accounting", "receipt", "missing",
                "grade", "invoice_complete", "cleanup_confirmed", "remote_terminal")}
            result["result"] = {key: value for key, value in record["result"].items()
                                if key != "recorded_publication_generation"}
            result.update(mode="read", intake_verified=True, intake_sha256=record["intake_sha256"])
        result.update(launch_authorized=False, grading_launched=False, admission_attempted=False,
                      replay_authorized=False, commands=[])
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, KeyboardInterrupt) as error:
        reason = (str(error) if isinstance(error, (output.OutputPublicationRefused, ci.RetentionCIRefused))
                  else "retention_result_intake_refused:" + type(error).__name__)
        print(json.dumps({"intake_verified": False, "reason": reason, "launch_authorized": False,
                          "grading_launched": False, "admission_attempted": False,
                          "grade": None, "invoice_complete": False, "commands": []}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
