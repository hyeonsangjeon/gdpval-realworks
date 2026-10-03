"""Observe only the legacy first Task4 KEEP/r1 RESULT's retained budget.

This is not a successor ReadBinding, full intake, delivery or grading receipt.
The exact primary terminal seals older identities absent from the report. No
mutable discovery, ledger/deliverable body read, admission or replay is exposed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import codex_budget_pilot as owned
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from ghcp_vm_input_bundle import _destination, _publication_parents, _write_no_clobber

CELL_ID = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1"
PRODUCER_SOURCE = "e355faf9a6212175a288e8473968915ffb2408d0"
REQUEST_SHA256 = "ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68"
RUN_ID, JOB_ID = "36696961231", 109837605787
CONTROLS = {
    "terminal_commit": "de50ff0aa6037c0ef6e3b713da519359abd1d08d",
    "terminal_identity": {"sha256": "0821af11393cab65d1e14259e43b14872b94a431496e8c1e3c38e719f33f21b8", "size": 6449},
    "claim_commit": "3fc283087a020caec574e8c9b8e9bc3ca593e88a",
    "output_commit": "43cbf8e265297813857172ecee51256cc17f2d36",
    "output_manifest_identity": {"sha256": "5e2ac668409fe760631ee13fc0bd9a1652bd604f8702bb18606683a2570ce977", "size": 2852},
}
# No invented claim hash/size, object-set digest or numeric exit code. The exact
# terminal binds those embedded identities; only a new observation derives them.
CONFIG_SHA256 = "08b29f44cb57312fd5757a3192c1a64855922bcd3d48d8e02fed96c4160683cb"
FORMAT = "retention-first-cell-budget-observation-v1"
MARKER = "retention-first-cell-budget-observation.json"
FROZEN = {
    "intake_sha256": ("codex_retention_result_intake.py", "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196"),
    "terminal_verifier_sha256": ("codex_retention_ci.py", "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c"),
    "controller_sha256": ("codex_retention_first_cell.py", "c42c8bb3e521c10a5d48680918978a3b9269468a724cd127109f8f4898fe2e6b"),
    "compiler_sha256": ("codex_retention_diagnostic.py", "c8ac9d0ec3eca0d4251c345f733009f506d366d312c5357836e6c67332a76c53"),
    "budget_projector_sha256": ("codex_budget_pilot_grade_readout.py", "96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815"),
}
require = output._require


def reader_identity():
    return {key: hashlib.sha256(output._bytes(path, limit=output.MAX_RECORD_BYTES)).hexdigest()
            for key, path in {"module_sha256": Path(__file__), **{
                name: Path(__file__).with_name(pair[0]) for name, pair in FROZEN.items()}}.items()}


def _dependencies(expected_reader_sha256):
    source = reader_identity()
    require(output._hash(expected_reader_sha256) and source["module_sha256"] == expected_reader_sha256
            and all(source[key] == pair[1] for key, pair in FROZEN.items()), "first_cell_budget_current_bytes_mismatch")
    # Check current bytes before lazy imports, private directories or credentials.
    import codex_retention_result_intake as intake
    import codex_budget_pilot_grade_readout as projector

    require(Path(intake.__file__).resolve() == Path(__file__).with_name(FROZEN["intake_sha256"][0]).resolve()
            and Path(projector.__file__).resolve() == Path(__file__).with_name(FROZEN["budget_projector_sha256"][0]).resolve(),
            "first_cell_budget_current_bytes_mismatch")
    return source, intake, projector._budget_snapshot


def _result(data, summary, plan, cell, roles, deliverables, intake, projector):
    """Legacy metadata validation only, never _payload or file binding."""
    value = owned._json_object(data)
    fingerprint = intake.validate_inference_result_fingerprint(value)
    output._safe_record(value)
    require(set(value) <= output.RESULT_FIELDS, "unsafe_result_fields")
    for key, expected in {
        "run_id": cell["run_id"], "experiment_id": cell["run_id"], "condition_identity": "condition_a",
        "execution_mode": "codex_foundry", "ordered_task_ids": [cell["task_id"]], "model": "gpt-5.4",
    }.items():
        require(value.get(key) == expected, "retention_result_runtime_identity_mismatch")
    require(output._hash(value.get("prepared_fingerprint")), "retention_result_prepared_identity_refused")
    # The first intake accepts any legal generation, not just cell.run_id.
    intake.validate_publication_generation(value.get("publication_generation"))
    if "source" in value:
        require(value["source"] == plan["inputs"]["repo_id"], "result_source_mismatch")
    if "condition" in value:
        require(value["condition"] == cell["config"]["condition_a"]["name"], "first_cell_budget_config_mismatch")
    require(type(value.get("results")) is list and len(value["results"]) == 1
            and type(value["results"][0]) is dict, "retention_result_one_row_required")
    row = value["results"][0]
    require(row.get("task_id") == cell["task_id"] and set(row) <= output.ROW_FIELDS
            and not row.get("failure_evidence") and row.get("usage") is None
            and not row.get("reflection_history") and row.get("reflection_attempts", 0) == 0,
            "unsafe_result_fields")
    output._receipt_fields(row.get("problem_solving_cost"))
    projected = intake.project_result_row({}, row)
    require(projected["status"] == "success" and projected.get("problem_solving_cost") == summary["receipt"],
            "retention_result_status_or_receipt_mismatch")
    names, records = row.get("deliverable_files"), row.get("deliverable_file_records", [])
    require(type(names) is list and all(type(name) is str for name in names)
            and len(names) == len(deliverables) and set(names) == set(deliverables)
            and type(records) is list and all(type(item) is dict and type(item.get("size")) is int for item in records)
            and records == [roles[name] for name in names], "retention_result_deliverable_binding_mismatch")
    ledger = value.get("cost_ledger")
    require((ledger is not None) == (intake.LEDGER in roles), "retention_result_ledger_binding_mismatch")
    if ledger is not None:
        require(type(ledger) is dict and set(ledger) == {"path", "sha256"}
                and ledger["path"] == intake.LEDGER and ledger["sha256"] == roles[intake.LEDGER]["sha256"],
                "retention_result_ledger_binding_mismatch")
    snapshot = projector(value)
    stored = row.get("observability", {}).get("task_deadline", {})
    for key, expected in {"run_id": cell["run_id"], "task_id": cell["task_id"], **cell["control"],
                          "total_seconds": 10800, "attempt_seconds": 1800}.items():
        if key in stored:
            require(type(stored[key]) is type(expected) and stored[key] == expected, "first_cell_budget_config_mismatch")
    return {**owned._identity(data), "result_fingerprint": fingerprint,
            "recorded_prepared_fingerprint": value["prepared_fingerprint"],
            "registered_config_sha256": cell["config_sha256"]}, snapshot


def observe_budget(*, expectation, destination: Path, expected_reader_sha256: str,
                   terminal_revision: str | None = None, _test_api=None):
    source, intake, projector = _dependencies(expected_reader_sha256)
    ci = intake.ci
    require(terminal_revision == CONTROLS["terminal_commit"], "fixed_first_cell_budget_required")
    _, plan, cell = intake._binding(expectation, FROZEN["intake_sha256"][1], terminal_revision, False)
    require(plan["campaign_id"] == intake.registration.CAMPAIGN and cell["index"] == 0
            and cell["control"] == {"condition": "retention_bundle_v1", "retention_bundle": "keep", "repetition": 1}
            and cell["config_sha256"] == intake.registration.seal(cell["config"]) == CONFIG_SHA256,
            "first_cell_budget_config_mismatch")
    require(isinstance(destination, Path) and destination.is_absolute(), "explicit_absolute_destination_required")
    destination, _ = _destination(destination)
    require(not os.path.lexists(destination), "new_result_destination_required")
    with _publication_parents(destination.parent) as (check, mkdir, directory_fd):
        mkdir(destination)
        cache = destination / intake.CACHE
        mkdir(cache)
        for name in ("primary", "verification", "result"):
            mkdir(cache / name)
        with retained._session(_test_api, response_bytes_limit=output.MAX_RECORD_BYTES) as (api, token, deadline):
            repo = retained._target()
            head = CONTROLS["terminal_commit"]
            # No branch-tip discovery. The primary hash is checked before any
            # dependent control or declared-object metadata is requested.
            terminal, terminal_bytes = retained._control(api, repo, head, ci.TERMINAL, cache / "primary", token,
                deadline, expected=CONTROLS["terminal_identity"], written_at=head)
            check()
            require(terminal["claim_commit"] == CONTROLS["claim_commit"]
                    and terminal["output_commit"] == CONTROLS["output_commit"], "first_cell_budget_controls_mismatch")
            intake._authority(terminal)
            verified = ci.verify_terminal(api, repo, head, None, cache / "verification", token, deadline,
                                          expectation=expectation)
            require(verified["request_sha256"] == REQUEST_SHA256
                    and owned._canonical_json(verified["completion"]) == owned._canonical_json(terminal["completion"]),
                    "first_cell_budget_controls_mismatch")
            # Rebind the primary terminal's exact nested identities as well as
            # the verifier's controls. Separate caches avoid adopting partials;
            # these are fixed checks, not a retry or another discovery route.
            claim, claim_bytes = retained._control(api, repo, CONTROLS["claim_commit"], ci.CLAIM, cache / "primary",
                token, deadline, expected=terminal["claim_identity"], written_at=CONTROLS["claim_commit"])
            summary, summary_bytes = retained._control(api, repo, CONTROLS["output_commit"], ci.OUTPUT + "/" + output.MANIFEST,
                cache / "primary", token, deadline, expected=CONTROLS["output_manifest_identity"],
                written_at=CONTROLS["output_commit"])
            require(owned._canonical_json(summary) == owned._canonical_json(terminal["completion"])
                    and all(owned._canonical_json(claim[key]) == owned._canonical_json(terminal[key])
                            for key in ("request_sha256", "authority", "scope")), "first_cell_budget_controls_mismatch")
            for revision in (CONTROLS["output_commit"], head):
                retained._objects(api, repo, revision, terminal["output_objects"], token, deadline,
                                  written_at=CONTROLS["output_commit"])
            retained._objects(api, repo, head, [retained._object(ci.CLAIM, claim_bytes)], token, deadline,
                              written_at=CONTROLS["claim_commit"])
            check()
            roles, deliverables = intake._roles(summary)
            data = intake.retained_reader._fetch(api, repo, CONTROLS["output_commit"], ci.OUTPUT + "/" + intake.RESULT,
                roles[intake.RESULT], cache / "result", token, deadline)
            check()
            result, budget = _result(data, summary, plan, cell, roles, deliverables, intake, projector)
            output._remaining(deadline)
        require(reader_identity() == source, "first_cell_budget_reader_changed")
        record = {
            "format": FORMAT, "evidence_only": True, "observation_only": True,
            "campaign": intake.registration.CAMPAIGN, "ordinal": 0, "cell_id": CELL_ID,
            "producer_source_sha": PRODUCER_SOURCE, "request_sha256": REQUEST_SHA256, "reader": source,
            "expected_provider": {"workflow_id": 370228282, "workflow": ci.WORKFLOW, "run_id": RUN_ID, "attempt": 1},
            "expected_execution_job_id": JOB_ID, "recorded_provider_run_id": terminal["authority"]["provider_run_id"],
            "recorded_provider_job_id": terminal["authority"]["provider_job_id"],
            "terminal_commit": head, "terminal_identity": owned._identity(terminal_bytes),
            "claim_commit": terminal["claim_commit"], "claim_identity": owned._identity(claim_bytes),
            "output_commit": terminal["output_commit"], "output_manifest_identity": owned._identity(summary_bytes),
            "output_objects_sha256": owned._digest(terminal["output_objects"]),
            "retained_authority_sha256": owned._digest(terminal["authority"]),
            "proof": "verified_publication_derived_not_independent_provider_authentication",
            "fresh_origin_authentication": False, "prepared_input_independently_verified": False,
            "git_parent_cas_independently_verified": False, "writer_acknowledgment": "not_established",
            "recorded_publication_acknowledged": True, "cleanup_confirmed": True,
            "status": summary["status"], "exit_code": summary["exit_code"],
            "declared_payload_roles": {"inference_result": 1, "ledger": int(intake.LEDGER in roles),
                                       "deliverables": len(deliverables)},
            "declared_output_object_count": len(terminal["output_objects"]),
            "result": result, "inference_budget_snapshot": budget,
            "budget_projector_sha256": FROZEN["budget_projector_sha256"][1], "result_body_verified": True,
            "payload_verification_scope": "inference_result_only", "payload_bodies_verified": False,
            "ledger_body_verified": False, "deliverable_bodies_verified": False, "grading_input_ready": False,
            "full_intake_established_by_this_observation": False, "delivery_established_by_this_observation": False,
            "grade_established_by_this_observation": False,
            "accounting": summary["accounting"], "receipt": summary["receipt"], "missing": summary["missing"],
            "unavailable": {name: {"status": "unavailable", "value": None, "reason": "not_recorded_in_terminal_controls"}
                            for name in ("detailed_failure", "recovery_exposure")},
            "http_request_count": None, "grade": None, "grading_launched": False, "invoice_complete": False,
            "launch_authorized": False, "admission_attempted": False, "replay_authorized": False, "commands": [],
        }
        if summary["exit_code"] is None:
            record["exit_code_missing_reason"] = "not_recorded_in_terminal_controls"
        encoded = retained._encoded(record)
        check()
        for directory in (destination.parent, destination, cache, *(cache / name for name in ("primary", "verification", "result"))):
            os.fsync(directory_fd(directory))
        try:
            _write_no_clobber(destination / MARKER, encoded, parent_fd=directory_fd(destination))
            os.fsync(directory_fd(destination))
            output._bytes(destination / MARKER, limit=output.MAX_MANIFEST_BYTES, expected=owned._identity(encoded))
            check()
        except (OSError, ValueError, KeyboardInterrupt) as error:
            raise output.OutputPublicationRefused("first_cell_budget_observation_unconfirmed") from error
        return {**record, "outcome": "budget_observation_verified", "terminal_verified": True,
                "budget_observation_verified": True, "observation_sha256": owned._identity(encoded)["sha256"]}


def main(argv=None, *, _test_api=None):
    try:
        parser = output._Parser(description=__doc__)
        parser.add_argument("--observe-budget", action="store_true")
        parser.add_argument("--output", type=Path)
        parser.add_argument("--expected-producer-source")
        parser.add_argument("--expected-request-sha256")
        parser.add_argument("--cell-id")
        parser.add_argument("--expected-reader-sha256")
        parser.add_argument("--terminal-revision")
        args = parser.parse_args(argv)
        if not args.observe_budget:
            require(not any((args.output, args.expected_producer_source, args.expected_request_sha256, args.cell_id,
                args.expected_reader_sha256, args.terminal_revision)), "explicit_first_cell_budget_observation_required")
            result = {"mode": "plan", "read_attempted": False, "producer_source_sha": PRODUCER_SOURCE,
                "request_sha256": REQUEST_SHA256, "cell_id": CELL_ID, "reader": reader_identity()}
        else:
            _, intake, _ = _dependencies(args.expected_reader_sha256)
            result = observe_budget(expectation=intake.ci.TerminalExpectation(args.expected_request_sha256,
                args.expected_producer_source, args.cell_id), destination=args.output,
                expected_reader_sha256=args.expected_reader_sha256, terminal_revision=args.terminal_revision,
                _test_api=_test_api)
            result["mode"] = "observe_budget"
        result.update(launch_authorized=False, grading_launched=False, admission_attempted=False,
                      replay_authorized=False, grade=None, invoice_complete=False, commands=[])
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, KeyboardInterrupt) as error:
        public = {"invalid_arguments", "explicit_first_cell_budget_observation_required", "explicit_hf_token_required",
                  "first_cell_budget_observation_unconfirmed"}
        reason = error.args[0] if (type(error) is output.OutputPublicationRefused and len(error.args) == 1
            and type(error.args[0]) is str and error.args[0] in public) else "first_cell_budget_observation_refused"
        print(json.dumps({"budget_observation_verified": False, "reason": reason, "launch_authorized": False,
            "grading_launched": False, "admission_attempted": False, "replay_authorized": False,
            "grade": None, "invoice_complete": False, "commands": []}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
