"""Recorded failed task4 A1/A2 and task5 A1/B1/C2: UNGRADED, never a judge.

This is not the ordinary judged-terminal format or a failed-input fallback.
The two CAS writes use the existing grading namespace and one-use guards.
Server verification does not establish receipt of a lost writer response.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as grading
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from core.result_fingerprint import inference_result_fingerprint

CLAIM_FORMAT = "codex-pilot-model-free-ungraded-claim-v1"
TERMINAL_FORMAT = "codex-pilot-model-free-ungraded-terminal-v1"
POLICY = "recorded_task4_failed_a1_no_judge"
A2_POLICY = "recorded_task4_failed_a2_no_judge"
TASK5_POLICY = "task5-a1-model-free-ungraded"
TASK5_B1_POLICY = "task5-b1-model-free-ungraded"
TASK5_C2_POLICY = "task5-c2-model-free-ungraded"
require = output._require


def _scope(context):
    recorded = (grading.TASK4_RETAINED.get(context.cell["cell_id"])
                or grading.TASK5_RETAINED.get(context.cell["cell_id"]))
    require(grading._model_free_context(context)
            and ci.CAMPAIGN == "budget_pilot_ci_20260925_04"
            and context.plan["reviewed_source_sha"] == grading.TASK3_A1_PRODUCER_SOURCE
            and context.controller_source_sha != grading.TASK3_A1_PRODUCER_SOURCE
            and recorded is not None and context.requested_terminal == recorded[1]
            and context.plan["order"][18:20] == [grading.TASK4_A1_CELL, grading.TASK4_B1_CELL]
            and retained.BRANCH == "pilot-inference-20260925-04"
            and grading.BRANCH == "pilot-grades-20260925-04", "fixed_model_free_a1_required")
    if context.cell["cell_id"] == grading.TASK4_A2_CELL:
        require(context.plan["order"][22:24] == [
            "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2", grading.TASK4_A2_CELL],
            "fixed_model_free_a2_predecessor_required")
    if context.cell["cell_id"] == grading.TASK5_A1_CELL:
        require(context.plan["order"][23:25] == [grading.TASK4_A2_CELL, grading.TASK5_A1_CELL]
                and context.plan["order"].index(context.cell["cell_id"]) == 24,
                "fixed_model_free_task5_predecessor_required")
    if context.cell["cell_id"] == grading.TASK5_B1_CELL:
        require(context.plan["order"][22:26] == [
            "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2", grading.TASK4_A2_CELL,
            grading.TASK5_A1_CELL, grading.TASK5_B1_CELL]
            and context.plan["order"].index(context.cell["cell_id"]) == 25,
            "fixed_model_free_task5_b1_predecessor_required")
    if context.cell["cell_id"] == grading.TASK5_C2_CELL:
        require(context.plan["order"][22:28] == [
            "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2", grading.TASK4_A2_CELL,
            grading.TASK5_A1_CELL, grading.TASK5_B1_CELL, grading.TASK5_C1_CELL, grading.TASK5_C2_CELL]
            and context.plan["order"].index(context.cell["cell_id"]) == 27,
            "fixed_model_free_task5_c2_predecessor_required")


def fixed_failure(context, evidence):
    _scope(context)
    grading._task2_resolution(context, evidence, evidence["observation"]["terminal_commit"])
    completed = ci.validate_completion(evidence["terminal"]["completion"])
    require(completed["status"] == "failed" and completed["exit_code"] == 1
            and completed["reason"] == "child_nonzero_exit" and completed["child_invocations"] == 1
            and completed["cleanup_confirmed"] is True and completed["timeout"] is False
            and completed["artifacts"]["deliverables"] == []
            and completed["artifacts"]["result"] is not None and completed["artifacts"]["ledger"] is not None
            and {row["role"] for row in evidence["manifest"]["files"]} == {
                "inference_result", "cost_ledger_export"}
            and "bound_inference_result" not in evidence["manifest"]["missing"]
            and "withheld" not in evidence["manifest"], "fixed_failed_inference_required")


def _original(context, evidence, files, repo):
    fixed_failure(context, evidence)
    payload = pilot._json_object(files["step2_inference_results.json"])
    output._safe_record(payload)
    require(set(payload) <= output.RESULT_FIELDS and len(payload["results"]) == 1,
            "unsafe_result_fields")
    row = payload["results"][0]
    require(set(row) <= output.ROW_FIELDS and not row.get("failure_evidence")
            and row["status"] == "error" and row["deliverable_files"] == []
            and row["deliverable_file_records"] == [], "fixed_failed_result_required")
    if "reflection_history" in row or "reflection_attempts" in row:
        require(type(row.get("reflection_history")) is list and not row["reflection_history"]
                and type(row.get("reflection_attempts")) is int and row["reflection_attempts"] == 0,
                "unsafe_result_fields")
    from gpt54_codex_grading_input import _validate_producer

    _validate_producer(payload, context.run, json.loads(context.grading.dispatch.runs[0].config_json))
    output._receipt_fields(row.get("problem_solving_cost"))
    identity = grading._inference_identity(context, evidence, files, repo)
    return payload, identity


def _predecessor_entry(context, checkout):
    # Pure hashes and pinned renderer capability, not _entry_contract/Step8
    # execution. These failed inputs have no successful judge-entry contract.
    import step8_grade as step8
    from core.tools import get_renderer_fingerprint

    config_path = checkout / "batch-runner/comparison-grading.json"
    require(output._bytes(config_path, limit=output.MAX_RECORD_BYTES) == context.run.grader_config_json.encode(),
            "model_free_fixed_config_changed")
    config = json.loads(context.run.grader_config_json)
    return {"config_hash": step8.hash_config(str(config_path)),
        "grader_source_hash": step8.compute_grader_source_hash(config_path, config,
            batch_root=checkout / "batch-runner"),
        "renderer_fingerprint": get_renderer_fingerprint() if step8.requires_track2_office_renderer(config) else None}


def prepare_record(context, root, prepared, transport):
    fixed_failure(context, prepared["evidence"])
    require(prepared["materialization"]["task_status"] == "error"
            and prepared["judge_ready"] is False, "model_free_failed_materialization_required")
    checkout = root / "source"
    transport.checkout(checkout, context.controller_source_sha)
    grading.configs._sources(checkout, pilot.load_plan())
    for name, data in grading.configs._files(context.grading, context.run.run_id).items():
        grading._put(checkout / name, data)
    prepared.update(predecessor_entry=_predecessor_entry(context, checkout), model_free_record_ready=True)


def _ready(context, root, transport):
    _scope(context)
    prepared = retained._read(root / "prepared.json")
    expected = {"cell_id": context.cell["cell_id"], "campaign_id": ci.CAMPAIGN,
        "source_sha": context.plan["reviewed_source_sha"], "controller_source_sha": context.controller_source_sha,
        "inference_branch": retained.BRANCH, "grading_branch": grading.BRANCH,
        "approval_request_sha256": grading._context_approval(context, grading._context_authority(context)),
        "proof_boundary": grading.PROOF, "grading_state": "UNRUN", "judge_ready": False,
        "model_free_record_ready": True, "reason": "retained_result_unsuccessful_ungraded",
        "terminal_request": context.requested_terminal}
    require(set(prepared) == set(expected) | {"terminal_revision", "evidence", "materialization",
            "identity_sha256", "predecessor_entry"}
            and all(type(prepared[key]) is type(value) and prepared[key] == value for key, value in expected.items()),
            "bound_model_free_preparation_required")
    require(retained._read(root / "retained-resolution.json") == {
        "request_sha256": prepared["approval_request_sha256"], "terminal_revision": prepared["terminal_revision"],
        "evidence_sha256": pilot._digest(prepared["evidence"])}, "recorded_b1_resolution_changed")
    fixed_failure(context, prepared["evidence"])
    require(prepared["terminal_revision"] == prepared["evidence"]["observation"]["terminal_commit"],
            "model_free_resolution_changed")
    context.terminal_revision = prepared["terminal_revision"]
    files = {row["path"]: output._bytes(root / "original" / row["path"], limit=output.MAX_FILE_BYTES, expected=row)
             for row in prepared["evidence"]["manifest"]["files"]}
    original, identity = _original(context, prepared["evidence"], files, retained._target())
    identity_sha = pilot._identity(retained._encoded(identity))["sha256"]
    require(prepared["identity_sha256"] == identity_sha
            and retained._read(root / "inference-identity.json") == identity,
            "model_free_original_identity_changed")
    materialized = prepared["materialization"]
    require(materialized["task_status"] == "error" and materialized["successful_deliverable_present"] is False
            and materialized["source_identity"] == identity
            and materialized["source_identity_sha256"] == identity_sha,
            "model_free_failed_materialization_required")
    # Reproduce only the existing deterministic source-identity augmentation,
    # using its serializer/fingerprint; never alter or adopt original bytes.
    derived = {**original, "source_repo_id": identity["source_repo_id"], "source_revision": identity["source_revision"],
               "source_identity_document_sha256": identity_sha}
    derived["result_fingerprint"] = inference_result_fingerprint(derived)
    derived_bytes = (grading.primitives._canonical_json(derived) + "\n").encode()
    require(materialized["materialized_result"] == {"path": context.run.inference_results_path,
        **pilot._identity(derived_bytes), "result_fingerprint": derived["result_fingerprint"]}
        and output._bytes(root / "inputs" / context.run.inference_results_path,
                          limit=output.MAX_RECORD_BYTES) == derived_bytes,
        "model_free_materialized_bytes_changed")
    transport.verify_checkout(root / "source", context.controller_source_sha)
    grading.configs._sources(root / "source", pilot.load_plan())
    require(prepared["predecessor_entry"] == _predecessor_entry(context, root / "source"),
            "model_free_predecessor_source_changed")
    return prepared


def _binding(context, evidence, identity_sha, entry, run):
    require(type(run) is dict and set(run) == {"id", "job", "attempt"}
            and type(run["id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run["id"]) is not None
            and run["job"] == "pilot-live" and type(run["attempt"]) is int and run["attempt"] == 1,
            "model_free_run_required")
    policy = TASK5_C2_POLICY if context.cell["cell_id"] == grading.TASK5_C2_CELL else (
        TASK5_B1_POLICY if context.cell["cell_id"] == grading.TASK5_B1_CELL else (
            TASK5_POLICY if context.cell["cell_id"] == grading.TASK5_A1_CELL else (
                POLICY if context.cell["cell_id"] == grading.TASK4_A1_CELL else A2_POLICY)))
    return {"policy": policy,
        "repository_name_sha256": retained.TARGET_SHA256,
        "campaign_id": ci.CAMPAIGN, "branch": grading.BRANCH, "inference_branch": retained.BRANCH,
        "cell_id": context.cell["cell_id"], "task_id": context.cell["task_id"], "run_id": context.cell["run_id"],
        "source_sha": context.plan["reviewed_source_sha"], "controller_source_sha": context.controller_source_sha,
        "completion_request_sha256": context.requested_terminal, "config_sha256": context.cell["config_sha256"],
        "order_sha256": pilot._digest(context.plan["order"]),
        "grading_plan_sha256": hashlib.sha256(context.grading.canonical_bytes()).hexdigest(),
        "grader_config_sha256": hashlib.sha256(context.run.grader_config_json.encode()).hexdigest(),
        "retained": evidence["observation"],
        "publication_receipt_sha256": evidence["terminal"]["publication_receipt_sha256"],
        "inference_identity_sha256": identity_sha, "predecessor_entry": {
            key: entry[key] for key in ("config_hash", "grader_source_hash", "renderer_fingerprint")},
        "github_run": run, "approval_request_sha256": grading._context_approval(context, run),
        "proof_boundary": grading.PROOF}


def _terminal(binding, admission, evidence):
    return {"format": TERMINAL_FORMAT, "binding": binding, "claim_commit": admission["returned_commit"],
        "claim_identity": admission["claim_identity"], "outcome": "ungraded", "model_invoked": False,
        "reason": "retained_inference_failed_no_judge", "inference_completion": evidence["terminal"]["completion"],
        "inference_missing": evidence["manifest"]["missing"],
        "recorder_accounting": {"status": "not_measured", "known_cost_usd": None, "estimated_cost_usd": None,
                                "invoice_complete": False, "http_request_count": None}}


def _task5_b1_revisions(api, repo, parent, previous, cache, token, deadline, *, record_revisions=()):
    """Fixed 24 -> 23 -> 22 before CAS; include 25's pair on terminal readback."""
    require(type(record_revisions) is tuple and len(record_revisions) in {0, 2},
            "model_free_task5_b1_chain_revision_changed")
    revisions = [*record_revisions, parent, previous["claim_commit"]]
    require(all(output._hash(value, 40) for value in revisions) and len(set(revisions)) == len(revisions),
            "model_free_task5_b1_chain_revision_changed")
    previous_claim, claim_bytes = retained._control(api, repo, previous["claim_commit"],
        grading._paths({"cell_id": grading.TASK5_A1_CELL,
                        "run_id": ci.CAMPAIGN + "__" + grading.TASK5_A1_CELL})[0], grading._cache(cache, "a1-claim"),
        token, deadline, expected=previous["claim_identity"], written_at=previous["claim_commit"])
    require(claim_bytes == retained._encoded({**previous_claim, "format": CLAIM_FORMAT,
                                              "binding": previous["binding"]}), "model_free_claim_changed")
    # The targets and formats are fixed here, not supplied by a record or tag.
    for cell_id, claim_format in (
        (grading.TASK4_A2_CELL, CLAIM_FORMAT),
        ("3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2", grading.CLAIM_FORMAT),
    ):
        link = previous_claim.get("predecessor")
        parent = previous_claim.get("expected_parent")
        require(type(link) is dict and set(link) == {"cell_id", "revision", "size", "sha256"}
                and link["cell_id"] == cell_id and link["revision"] == parent and output._hash(parent, 40)
                and output._hash(link["sha256"]) and type(link["size"]) is int
                and 0 < link["size"] <= output.MAX_MANIFEST_BYTES,
                "fixed_model_free_task5_b1_predecessor_required")
        require(parent not in revisions, "model_free_task5_b1_chain_revision_changed")
        revisions.append(parent)
        claim_path, terminal_path = grading._paths({"cell_id": cell_id, "run_id": ci.CAMPAIGN + "__" + cell_id})
        previous, _ = retained._control(api, repo, parent, terminal_path,
            grading._cache(cache, cell_id + "-terminal"), token, deadline,
            expected={key: link[key] for key in ("size", "sha256")}, written_at=parent)
        require(output._hash(previous.get("claim_commit"), 40) and previous["claim_commit"] not in revisions,
                "model_free_task5_b1_chain_revision_changed")
        revisions.append(previous["claim_commit"])
        previous_claim, claim_bytes = retained._control(api, repo, previous["claim_commit"], claim_path,
            grading._cache(cache, cell_id + "-claim"), token, deadline,
            expected=previous["claim_identity"], written_at=previous["claim_commit"])
        require(claim_bytes == retained._encoded({**previous_claim, "format": claim_format,
                                                  "binding": previous["binding"]}), "model_free_claim_changed")
    require(len(revisions) == len(set(revisions)) == 6 + len(record_revisions),
            "model_free_task5_b1_chain_revision_changed")


def _task5_c2_predecessor(api, repo, revision, context, entry, cache, token, deadline, *, record_revisions=()):
    """Only C2: ordinary 26 backed by fixed UNGRADED 25 -> 24 -> 23 -> ordinary 22."""
    _scope(context)
    require(context.cell["cell_id"] == grading.TASK5_C2_CELL,
            "fixed_model_free_task5_c2_predecessor_required")
    require(type(record_revisions) is tuple and len(record_revisions) in {0, 2},
            "model_free_task5_c2_chain_revision_changed")
    previous = grading.compile_request("pilot/" + grading.TASK5_C1_CELL, context.controller_source_sha,
        grading.TASK5_RETAINED[grading.TASK5_C1_CELL][1], producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    claim_path, terminal_path = grading._paths(previous.cell)
    value, original_bytes = retained._control(api, repo, revision, terminal_path,
        grading._cache(cache, "c1-terminal"), token, deadline, written_at=revision)
    evidence = grading._retained_input(previous, api, repo, grading._cache(cache, "c1-input"), token, deadline,
        candidate_revision=value["binding"]["retained"]["terminal_commit"])
    require(value["binding"]["retained"] == evidence["observation"]
            and value["binding"]["publication_receipt_sha256"] == evidence["terminal"]["publication_receipt_sha256"],
            "recorded_grade_input_binding_mismatch")
    verified = grading._grade_terminal(api, repo, revision, previous, entry,
        grading._cache(cache, "ordinary-c1"), token, deadline)
    require(verified["identity"] == pilot._identity(original_bytes), "model_free_task5_c2_backing_changed")
    claim, _ = retained._control(api, repo, value["claim_commit"], claim_path,
        grading._cache(cache, "c1-claim"), token, deadline, expected=value["claim_identity"],
        written_at=value["claim_commit"])
    b1 = grading.compile_request("pilot/" + grading.TASK5_B1_CELL, context.controller_source_sha,
        grading.TASK5_RETAINED[grading.TASK5_B1_CELL][1], producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    backing = verify_terminal(api, repo, claim["expected_parent"], b1, entry,
        grading._cache(cache, "fixed-b1"), token, deadline)
    require(claim["predecessor"] == {"cell_id": grading.TASK5_B1_CELL,
                "revision": backing["revision"], **backing["identity"]}
            and evidence["claim"]["predecessor"] == backing["terminal"]["binding"]["retained"],
            "model_free_task5_c2_backing_changed")
    # Collect only these five immutable pairs. Neither depth nor format is
    # selected by remote tags; B1's existing verifier remains unchanged.
    cells = (grading.TASK5_C1_CELL, grading.TASK5_B1_CELL, grading.TASK5_A1_CELL,
             grading.TASK4_A2_CELL, "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2")
    revisions, expected = list(record_revisions), verified["identity"]
    for index, cell_id in enumerate(cells):
        claim_path, terminal_path = grading._paths({"cell_id": cell_id, "run_id": ci.CAMPAIGN + "__" + cell_id})
        terminal, _ = retained._control(api, repo, revision, terminal_path,
            grading._cache(cache, cell_id + "-terminal"), token, deadline, expected=expected, written_at=revision)
        revisions.extend((revision, terminal["claim_commit"]))
        require(all(output._hash(item, 40) for item in revisions) and len(set(revisions)) == len(revisions),
                "model_free_task5_c2_chain_revision_changed")
        linked, data = retained._control(api, repo, terminal["claim_commit"], claim_path,
            grading._cache(cache, cell_id + "-claim"), token, deadline,
            expected=terminal["claim_identity"], written_at=terminal["claim_commit"])
        claim_format = grading.CLAIM_FORMAT if index in {0, 4} else CLAIM_FORMAT
        require(data == retained._encoded({**linked, "format": claim_format, "binding": terminal["binding"]}),
                "model_free_claim_changed")
        if index < 4:
            link = linked["predecessor"]
            require(type(link) is dict and set(link) == {"cell_id", "revision", "size", "sha256"}
                    and link["cell_id"] == cells[index + 1] and link["revision"] == linked["expected_parent"]
                    and type(link["size"]) is int and 0 < link["size"] <= output.MAX_MANIFEST_BYTES
                    and output._hash(link["sha256"]), "fixed_model_free_task5_c2_predecessor_required")
            revision, expected = linked["expected_parent"], {key: link[key] for key in ("size", "sha256")}
    require(len(revisions) == 10 + len(record_revisions), "model_free_task5_c2_chain_revision_changed")
    return verified


def verify_terminal(api, repo, revision, context, entry, cache, token, deadline):
    _scope(context)
    require(output._hash(revision, 40), "model_free_terminal_revision_required")
    claim_path, terminal_path = grading._paths(context.cell)
    terminal, data = retained._control(api, repo, revision, terminal_path, cache, token, deadline, written_at=revision)
    require(terminal.get("format") == TERMINAL_FORMAT and terminal.get("model_invoked") is False,
            "model_free_terminal_type_required")
    binding = terminal["binding"]
    evidence = grading._retained_input(context, api, repo, grading._cache(cache, "inference"), token, deadline,
        candidate_revision=binding["retained"]["terminal_commit"])
    fixed_failure(context, evidence)
    prefix = retained._paths(context.cell)[2]
    originals = grading._cache(cache, "original")
    files = {row["path"]: grading._fetch(api, repo, evidence["terminal"]["output_commit"], prefix + "/" + row["path"],
             row, originals, token, deadline) for row in evidence["manifest"]["files"]}
    _, identity = _original(context, evidence, files, repo)
    expected_binding = _binding(context, evidence, pilot._identity(retained._encoded(identity))["sha256"], entry,
                                binding["github_run"])
    require(binding == expected_binding, "model_free_binding_changed")
    claim, claim_bytes = retained._control(api, repo, terminal["claim_commit"], claim_path,
        grading._cache(cache, "claim"), token, deadline, expected=terminal["claim_identity"],
        written_at=terminal["claim_commit"])
    require(set(claim) == {"format", "binding", "expected_parent", "predecessor"}
            and claim["format"] == CLAIM_FORMAT and claim["binding"] == binding, "model_free_claim_changed")
    grading._task3_grade_predecessor(context, claim)
    require(len({claim["expected_parent"], terminal["claim_commit"], revision}) == 3,
            "model_free_terminal_parent_changed")
    task5 = context.cell["cell_id"] == grading.TASK5_A1_CELL
    task5_b1 = context.cell["cell_id"] == grading.TASK5_B1_CELL
    task5_c2 = context.cell["cell_id"] == grading.TASK5_C2_CELL
    previous_cell = context.plan["order"][26 if task5_c2 else 24 if task5_b1 else 23 if task5 else
                                           17 if context.cell["cell_id"] == grading.TASK4_A1_CELL else 22]
    recorded = (grading._task3_recorded(previous_cell) or grading.TASK4_RETAINED.get(previous_cell)
                or grading.TASK5_RETAINED.get(previous_cell))
    previous = grading.compile_request("pilot/" + previous_cell, context.controller_source_sha,
        recorded[1], producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    previous_path = grading._paths(previous.cell)[1]
    previous_value, previous_data = retained._control(api, repo, claim["expected_parent"], previous_path,
        grading._cache(cache, "predecessor"), token, deadline,
        expected={key: claim["predecessor"][key] for key in ("size", "sha256")}, written_at=claim["expected_parent"])
    grading._grade_retained_input(previous, previous_value["binding"], api, repo,
                                 grading._cache(cache, "previous-input"), token, deadline)
    if task5_c2:
        require(claim_bytes == retained._encoded({**claim, "binding": expected_binding}), "model_free_claim_changed")
        verified = _task5_c2_predecessor(api, repo, claim["expected_parent"], context, entry,
            grading._cache(cache, "c2-predecessor"), token, deadline,
            record_revisions=(revision, terminal["claim_commit"]))
    elif task5_b1:
        require(previous.cell["cell_id"] == grading.TASK5_A1_CELL,
                "fixed_model_free_task5_b1_predecessor_required")
        require(claim_bytes == retained._encoded({**claim, "binding": expected_binding}), "model_free_claim_changed")
        _task5_b1_revisions(api, repo, claim["expected_parent"], previous_value,
                           grading._cache(cache, "fixed-b1-chain"), token, deadline,
                           record_revisions=(revision, terminal["claim_commit"]))
        verified = verify_terminal(api, repo, claim["expected_parent"], previous, entry,
                                   grading._cache(cache, "previous-grade"), token, deadline)
    elif task5:
        # One explicit 24 -> 23 -> ordinary 22 boundary, never tag-driven or
        # data-driven recursion. A2 retains its original ordinary B2 verifier.
        require(previous.cell["cell_id"] == grading.TASK4_A2_CELL
                and previous.plan["order"][22:24] == [
                    "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2", grading.TASK4_A2_CELL],
                "fixed_model_free_task5_predecessor_required")
        previous_claim, _ = retained._control(api, repo, previous_value["claim_commit"],
            grading._paths(previous.cell)[0], grading._cache(cache, "previous-claim"), token, deadline,
            expected=previous_value["claim_identity"], written_at=previous_value["claim_commit"])
        require(len({revision, terminal["claim_commit"], claim["expected_parent"],
                     previous_value["claim_commit"], previous_claim["expected_parent"]}) == 5,
                "model_free_task5_chain_revision_changed")
        verified = verify_terminal(api, repo, claim["expected_parent"], previous, entry,
                                   grading._cache(cache, "previous-grade"), token, deadline)
    else:
        verified = grading._grade_terminal(api, repo, claim["expected_parent"], previous, entry,
                                           grading._cache(cache, "previous-grade"), token, deadline)
    require(evidence["claim"]["predecessor"] == verified["terminal"]["binding"]["retained"],
            "model_free_inference_predecessor_changed")
    retained._objects(api, repo, terminal["claim_commit"], [retained._object(previous_path, previous_data)],
                      token, deadline, written_at=claim["expected_parent"])
    retained._objects(api, repo, revision, [retained._object(claim_path, claim_bytes)],
                      token, deadline, written_at=terminal["claim_commit"])
    expected_terminal = _terminal(expected_binding, {"returned_commit": terminal["claim_commit"],
        "claim_identity": pilot._identity(claim_bytes)}, evidence)
    # Canonical bytes preserve types too: Python would otherwise equate 1 and
    # True inside the copied original completion or accounting projection.
    require(data == retained._encoded(expected_terminal), "model_free_terminal_changed")
    return {"terminal": terminal, "identity": pilot._identity(data), "revision": revision}


def record(context, root: Path, *, _test_api=None, _test_transport=None):
    _scope(context)
    run = grading._context_authority(context)
    root = grading._root(root)
    transport = _test_transport or pilot.LocalTransport()
    source_plan, source_parent, _ = pilot.compile_pilot(ci.CAMPAIGN, context.controller_source_sha)
    transport.require_source(source_plan, source_parent)
    with grading._lock(root):
        prepared = _ready(context, root, transport)
        binding = _binding(context, prepared["evidence"], prepared["identity_sha256"], prepared["predecessor_entry"], run)
        grading._record(root / "model-free-claim-reserved.json", binding)
        admission = grading._observation(stage="model_free_ungraded_claim")
        try:
            with retained._session(_test_api) as (api, token, deadline):
                repo = retained._target()
                evidence = grading._retained_input(context, api, repo, grading._cache(root, "model-free-input"),
                    token, deadline, candidate_revision=context.terminal_revision)
                require(evidence == prepared["evidence"], "model_free_retained_observation_changed")
                head, previous = grading._branch_tip(api, repo, context, prepared,
                    grading._cache(root, "model-free-tip"), token, deadline)
                grading._absent(api, repo, head, context.cell, token, deadline)
                claim = {"format": CLAIM_FORMAT, "binding": binding, "expected_parent": head, "predecessor": previous}
                claim_path, terminal_path = grading._paths(context.cell)
                claim_bytes = retained._encoded(claim)
                claim_revision = grading._commit(api, repo, head, {claim_path: claim_bytes}, token, deadline, admission)
                confirmed, confirmed_bytes = retained._control(api, repo, claim_revision, claim_path,
                    grading._cache(root, "model-free-claim"), token, deadline,
                    expected=pilot._identity(claim_bytes), written_at=claim_revision)
                require(confirmed == claim and confirmed_bytes == claim_bytes, "model_free_claim_readback_changed")
                grading._put(root / "model-free-claim-verified.json", confirmed_bytes)
                admission.update(outcome="acknowledged", claim=claim, claim_identity=pilot._identity(confirmed_bytes))
        except (Exception, KeyboardInterrupt) as error:
            grading._failed(admission, error)
        grading._record(root / "model-free-claim-receipt.json", admission)
        if admission["outcome"] != "acknowledged":
            return admission  # No terminal attempt after an uncertain claim.
        terminal = _terminal(binding, admission, prepared["evidence"])
        terminal_bytes = retained._encoded(terminal)
        grading._record(root / "model-free-publication-reserved.json", {
            "expected_parent": admission["returned_commit"], "terminal_identity": pilot._identity(terminal_bytes)})
        result = grading._observation(stage="model_free_ungraded_publication")
        try:
            require(retained._read(root / "model-free-claim-reserved.json") == binding
                    and retained._read(root / "model-free-claim-receipt.json") == admission
                    and output._bytes(root / "model-free-claim-verified.json", limit=output.MAX_MANIFEST_BYTES,
                        expected=admission["claim_identity"]) == retained._encoded(admission["claim"]),
                    "model_free_admission_changed")
            if context.cell["cell_id"] == grading.TASK5_C2_CELL:
                require(output._bytes(root / "model-free-claim-reserved.json", limit=output.MAX_MANIFEST_BYTES)
                            == retained._encoded(binding)
                        and output._bytes(root / "model-free-claim-receipt.json", limit=output.MAX_MANIFEST_BYTES)
                            == retained._encoded(admission), "model_free_admission_changed")
            with retained._session(_test_api) as (api, token, deadline):
                repo = retained._target()
                require(output._metadata(api, repo, grading.BRANCH, token, deadline)["sha"] == admission["returned_commit"],
                        "grade_publication_parent_changed")
                require(api.get_paths_info(repo_id=repo, repo_type="dataset", revision=admission["returned_commit"],
                    paths=[terminal_path], token=token) == [], "grade_payload_already_exists")
                revision = grading._commit(api, repo, admission["returned_commit"], {terminal_path: terminal_bytes},
                                           token, deadline, result)
                verified = verify_terminal(api, repo, revision, context, prepared["predecessor_entry"],
                                            grading._cache(root, "model-free-published"), token, deadline)
                require(verified["terminal"] == terminal, "model_free_publication_changed")
                result.update(outcome="acknowledged", terminal_identity=verified["identity"], grading_state="ungraded")
        except (Exception, KeyboardInterrupt) as error:
            grading._failed(result, error)
        grading._record(root / "model-free-publication-receipt.json", result)
        return result
