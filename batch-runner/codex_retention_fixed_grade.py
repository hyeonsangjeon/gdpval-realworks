"""Two closed retained-result bindings, one existing fixed judge each, no replay.

Default planning is inert. Live phases require the existing same-run protected
grading approval and exact source. The retained producer, later reader, prior
grading observer and this grading controller are separate identities.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as pilot_ci
import codex_budget_pilot_grading as grade
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_budget_pilot_ungraded as ungraded
import codex_retention_diagnostic as registration
import codex_retention_result_intake as reader
import gpt54_run_config_bundle as configs
from core.result_fingerprint import inference_result_fingerprint
from gpt54_codex_grading_input import _materialize_bound_codex_grading_input
from gpt54_comparison_preflight import (
    ComparisonDispatchPlan, ComparisonRunSpec, _canonical_json, _compile_grading_plan, load_plan,
)

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = "retention/first-cell"
ORDINAL, REPETITION = 0, 1
CELL = reader.EXPECTATION.cell_id
PREFIX = "retention-cell-grades/" + registration.CAMPAIGN + "/" + CELL
CLAIM_PATH, TERMINAL_PATH = PREFIX + "/claim.json", PREFIX + "/terminal.json"
CLAIM_FORMAT = "retention-first-cell-grade-claim-v1"
TERMINAL_FORMAT = "retention-first-cell-grade-terminal-v1"
GRADER_PATH = "batch-runner/workspace/retention-ci-first/grader-config.json"
INFERENCE_CONFIG_PATH = "batch-runner/workspace/retention-ci-first/inference-config.json"
PREPARATION_FORMAT = "retention-first-cell-grade-preparation-v1"
MARKER = reader.MARKER
GRADER_SHA256 = "c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320"
READER = {
    "module_sha256": "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196",
    "terminal_verifier_sha256": "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c",
}
READER_FILES = {"module_sha256": "codex_retention_result_intake.py",
                "terminal_verifier_sha256": "codex_retention_ci.py"}
# Leader's actual successful immutable intake; never a mutable latest selector.
RESULT = {
    "producer_source_sha": "e355faf9a6212175a288e8473968915ffb2408d0",
    "request_sha256": "ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68",
    "cell_id": CELL,
    "provider_run_id": "36696961231", "provider_job_id": 109837605787, "provider_run_attempt": 1,
    "terminal_commit": "de50ff0aa6037c0ef6e3b713da519359abd1d08d",
    "terminal_identity": {"sha256": "0821af11393cab65d1e14259e43b14872b94a431496e8c1e3c38e719f33f21b8", "size": 6449},
    "claim_commit": "3fc283087a020caec574e8c9b8e9bc3ca593e88a",
    "output_commit": "43cbf8e265297813857172ecee51256cc17f2d36",
    "output_manifest_identity": {"sha256": "5e2ac668409fe760631ee13fc0bd9a1652bd604f8702bb18606683a2570ce977", "size": 2852},
    "intake_sha256": "dbdb64c0ea4769c37b1954c972823777dbd90bf6dbde77ddbcef2e169eb4eb32",
    "result": {
        "sha256": "07f335a07ffc8d921a0cfa0c7ab6bbc3728d704adc7c31f7ac1d3594728e3f67", "size": 10972,
        "result_fingerprint": "3441f200e6e4c53faf1b36f216283c80eee68e5d3e7d827587ba6c3135c7d200",
        "recorded_prepared_fingerprint": "e9ffd87a8da6f06e26449b7f8d68468e674ea241e787a84568dace72774a2247",
        "registered_config_sha256": "08b29f44cb57312fd5757a3192c1a64855922bcd3d48d8e02fed96c4160683cb",
    },
}
# Saved VERIFIED observer receipt, not fresh provider authentication or current
# branch-head evidence. Both exact objects and bounded history are read again.
PARENT = {
    "branch": "pilot-grades-20260925-04", "campaign_id": "budget_pilot_ci_20260925_04",
    "cell_id": grade.TASK5_A2_CELL,
    "revision": "b057ed17849c0ab31b0adfb8c28109d4d34a50f7",
    "terminal_identity": {"sha256": "1443d6f9271c25d8ed27ea7179292ea43c790d26b4a37b079f6620b8ca25cd84", "size": 4260},
    "claim_revision": "41729a5caf6307a200921fc2c06a8b8e860ab95b",
    "claim_identity": {"sha256": "81f1f8aa632145055b79b7d4b9cdfba7248b8f95b7f9caf552062e6854621d86", "size": 2425},
    "writer_source_sha": "69e56fc58daf50af2ac9e8b52691ffcbf5af4f96",
    "writer_run": {"id": "36306339791", "job": "pilot-live", "attempt": 1},
    "observer_source_sha": "74ae7277a636643d37c4a7e854728df1aec83676", "observer_run_id": "36337865696",
    "proof_boundary": grade.PROOF,
}
require = output._require


def _same(actual, expected, reason):
    require(retained._encoded(actual) == retained._encoded(expected), reason)


def _fixed(selector=SELECTOR):
    require(type(selector) is str and selector in {SELECTOR, "retention/keep-r2"},
            "fixed_retention_grade_selector_required")
    if selector == SELECTOR:
        return sys.modules[__name__]
    import codex_retention_keep_r2_grade
    return codex_retention_keep_r2_grade


def _fixed_inputs(selector=SELECTOR):
    fixed = _fixed(selector)
    return {"experiment_yaml": fixed.SELECTOR, "inference_revision": fixed.RESULT["terminal_commit"],
        "grading_config": "default_v2_sol_max.yaml", "force": False, "tasks_limit": 0, "tasks": "",
        "dry_run": False, "paid_approval": True, "resume": False, "resume_chunk": 0,
        "shard_count": 1, "shard_index": 0, "run_ordinal": 1}


def fixed_evidence_sha256(selector=SELECTOR):
    fixed = _fixed(selector)
    evidence = {"result": fixed.RESULT, "grading_parent": fixed.PARENT, "reader": fixed.READER,
                "grader_path": fixed.GRADER_PATH, "grader_sha256": fixed.GRADER_SHA256}
    if selector != SELECTOR:
        # Bind the new route explicitly without changing historical first-cell evidence.
        evidence["selector"] = fixed.SELECTOR
    return pilot._digest(evidence)


@dataclass(frozen=True)
class Context:
    plan: dict
    cell: dict
    grading: object
    controller_source_sha: str
    selector: str = SELECTOR

    @property
    def run(self):
        return self.grading.runs[0]


def compile_request(source: str, *, selector=SELECTOR, terminal="", producer="") -> Context:
    fixed = _fixed(selector)
    require(terminal in {"", fixed.RESULT["terminal_commit"]}
            and producer in {"", fixed.RESULT["producer_source_sha"]}, "fixed_retention_grade_selector_required")
    require(output._hash(source, 40) and source not in {fixed.RESULT["producer_source_sha"], fixed.PARENT["writer_source_sha"],
            fixed.PARENT["observer_source_sha"]}, "distinct_reviewed_grading_source_required")
    require(grade.BRANCH == fixed.PARENT["branch"], "fixed_retention_grade_branch_required")
    plan = registration.compile_plan()
    cell = reader.controller._adapted_cell(plan["cells"][fixed.ORDINAL])
    require(cell["cell_id"] == fixed.CELL and cell["index"] == fixed.ORDINAL
            and cell["control"] == {"condition": "retention_bundle_v1", "retention_bundle": "keep",
                                   "repetition": fixed.REPETITION}
            and cell["config_sha256"] == fixed.RESULT["result"]["registered_config_sha256"],
            "registered_retention_grade_cell_required")
    config = cell["config"]
    model = config["condition_a"]["model"]
    spec = ComparisonRunSpec(cell["run_id"], "codex", fixed.REPETITION, "codex", model["provider"], model["deployment"],
        model["reasoning_effort"], "advance_check_5", (cell["task_id"],), "source", "batch-runner",
        fixed.INFERENCE_CONFIG_PATH, _canonical_json(config), ())
    shared = load_plan(ROOT / registration.ORIGINAL_PROFILE)["shared"]
    dispatch = ComparisonDispatchPlan(pilot._digest({"registration": plan, "evidence": fixed_evidence_sha256(selector)}),
        fixed.RESULT["producer_source_sha"], _canonical_json(plan["source_pins"]), _canonical_json(shared), (spec,))
    grading = _compile_grading_plan(dispatch)
    run = grading.runs[0]
    command = list(run.command)
    command[2] = selector
    command[command.index("--config") + 1] = str(Path(fixed.GRADER_PATH).relative_to("batch-runner"))
    command[command.index("--limit") + 1] = "1"
    _same(json.loads(run.grader_config_json), plan["grading"]["generated_config"], "fixed_grader_config_changed")
    run = replace(run, command=tuple(command), experiment_config_path="batch-runner/experiments/" + selector + ".yaml",
        grader_config_path=fixed.GRADER_PATH, producer_results_path=pilot.RESULT,
        input_materialization="codex_retention_fixed_grade.prepare")
    return Context(plan, cell, replace(grading, runs=(run,)), source, selector)


def _context(context):
    require(type(context) is Context, "canonical_retention_grade_context_required")
    expected = compile_request(context.controller_source_sha, selector=context.selector)
    _same({"plan": context.plan, "cell": context.cell, "grading": context.grading.as_dict()},
          {"plan": expected.plan, "cell": expected.cell, "grading": expected.grading.as_dict()},
          "retention_grade_context_changed")


def approval_request(source, run, *, selector=SELECTOR):
    fixed = _fixed(selector)
    return {"workflow": grade.WORKFLOW, "repository": pilot_ci.REPOSITORY, "ref": "refs/heads/main",
        "controller_source_sha": source, "producer_source_sha": fixed.RESULT["producer_source_sha"],
        "cell_id": fixed.CELL, "campaign_id": registration.CAMPAIGN,
        "repository_name_sha256": retained.TARGET_SHA256, "inference_branch": retained.BRANCH,
        "grading_branch": grade.BRANCH, "github_run_id": run["id"], "github_run_attempt": run["attempt"],
        "inputs": _fixed_inputs(selector), "retention_evidence_sha256": fixed_evidence_sha256(selector)}


def _authority(context):
    _context(context)
    fixed = _fixed(context.selector)
    grade._workflow_inputs()
    expected = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": pilot_ci.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": context.controller_source_sha, "PILOT_WORKFLOW_SHA": context.controller_source_sha,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "pilot-live",
        "GITHUB_WORKFLOW_REF": pilot_ci.REPOSITORY + "/" + grade.WORKFLOW + "@refs/heads/main",
        "PILOT_GRADE_PAID_APPROVAL": "true", "PILOT_GRADE_DRY_RUN": "false",
        "PILOT_GRADE_APPROVAL_RESULT": "success", "GRADE_SELECTOR": context.selector,
        "GRADE_TERMINAL": fixed.RESULT["terminal_commit"]}
    require(all(os.environ.get(key) == value for key, value in expected.items()),
            "protected_retention_grade_context_required")
    run = {"id": os.environ.get("GITHUB_RUN_ID"), "job": "pilot-live", "attempt": 1}
    require(type(run["id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run["id"]) is not None,
            "retention_grade_run_identity_required")
    require(os.environ.get("PILOT_GRADE_APPROVAL_REQUEST_SHA256") == pilot._digest(
            approval_request(context.controller_source_sha, run, selector=context.selector)), "retention_grade_approval_mismatch")
    return run


def _source_checkout(context, checkout=ROOT):
    """Exact safe source checkout, shared without changing historical evidence."""
    pilot._repository(checkout)
    pilot._safe_checkout_configuration(checkout)
    require(pilot._git(checkout, "rev-parse", "HEAD").stdout == (context.controller_source_sha + "\n").encode()
            and not pilot._git(checkout, "diff", "--name-only", "HEAD", "--").stdout,
            "retention_grade_source_changed")
    if checkout == ROOT:
        require(not pilot._git(checkout, "status", "--porcelain", "--untracked-files=normal").stdout,
                "clean_retention_grade_source_required")


def _source(context, checkout=ROOT):
    fixed = _fixed(context.selector)
    _source_checkout(context, checkout)
    for key, name in fixed.READER_FILES.items():
        data = output._bytes(checkout / "batch-runner" / name, limit=output.MAX_RECORD_BYTES)
        require(pilot._identity(data)["sha256"] == fixed.READER[key], "reviewed_retention_reader_required")


def _intake(record, destination, *, selector=SELECTOR):
    """Actual receipt plus evidence-marker and declared-role readback, not a flag."""
    require(type(record) is dict and record.get("intake_verified") is True, "verified_retention_intake_required")
    fixed = _fixed(selector)
    for key, value in fixed.RESULT.items():
        actual = record.get(key)
        if key == "result" and type(actual) is dict:
            actual = {name: actual.get(name) for name in value}
        _same(actual, value, "fixed_retention_result_mismatch")
    boundary = {"remote_terminal": "acknowledged"} if selector == SELECTOR else fixed.intake_boundary()
    for key, value in {"reader": fixed.READER, "status": "succeeded", "cleanup_confirmed": True,
            "grade": None, "invoice_complete": False,
            "evidence_only": True, "consumer_readback_required": True, **boundary}.items():
        _same(record.get(key), value, "retention_intake_boundary_mismatch")
    marker = output._bytes(destination / fixed.MARKER, limit=output.MAX_MANIFEST_BYTES)
    require(pilot._identity(marker)["sha256"] == fixed.RESULT["intake_sha256"], "retention_intake_marker_changed")
    _same(pilot._json_object(marker), {key: value for key, value in record.items()
          if key not in {"intake_verified", "intake_sha256"}}, "retention_intake_receipt_changed")
    manifest = output._bytes(destination / output.MANIFEST, limit=output.MAX_MANIFEST_BYTES,
                             expected=fixed.RESULT["output_manifest_identity"])
    summary = pilot._json_object(manifest)
    roles, deliverables = reader._roles(summary)
    files = {name: output._bytes(reader._path(destination, name), limit=output.MAX_FILE_BYTES, expected=identity)
             for name, identity in roles.items()}
    plan = registration.compile_plan()
    _, result = reader._payload(files, summary, plan, reader.controller._adapted_cell(plan["cells"][fixed.ORDINAL]), roles, deliverables)
    _same(result, record["result"], "retention_intake_readback_changed")
    _same(summary["files"], record["files"], "retention_intake_manifest_changed")
    return files


def _origins(context):
    from codex_ci_input_intake import HFRole
    from gpt54_run_input_bundle import DATASET_ROOT, PARQUET_PATH

    inputs = context.plan["inputs"]
    task, = [row for row in inputs["tasks"] if row["task_id"] == context.cell["task_id"]]
    specs = {PARQUET_PATH: {"sha256": inputs["parquet_sha256"]}}
    origins = [(PARQUET_PATH, inputs["repo_id"], inputs["revision"],
                PARQUET_PATH.removeprefix(DATASET_ROOT + "/"), HFRole.PARQUET)]
    for member, digest in sorted(task["reference_files"].items()):
        specs[member] = {"sha256": digest}
        origins.append((member, inputs["repo_id"], inputs["revision"], member, HFRole.REFERENCE_1))
    return inputs["revision"], specs, origins


def _derived_inputs(context, files, identity):
    """Recompute the materializer's three provenance additions, not its verdict."""
    identity_sha = pilot._identity(retained._encoded(identity))["sha256"]
    payload = pilot._json_object(files[reader.RESULT])
    payload.update(source_repo_id=identity["source_repo_id"], source_revision=identity["source_revision"],
                   source_identity_document_sha256=identity_sha)
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    data = (_canonical_json(payload) + "\n").encode()
    members = {context.run.inference_results_path: data}
    for name, value in files.items():
        if name != reader.RESULT:
            relative = "batch-runner/workspace/" + ("upload/" if name.startswith("deliverable_files/") else "") + name
            members[relative] = value
    return members, {"materialized_result": {"path": context.run.inference_results_path,
        **pilot._identity(data), "result_fingerprint": payload["result_fingerprint"]},
        "task_status": payload["results"][0]["status"]}


def _rubric_readback(context, checkout):
    """Rebind original bytes and the real local rubric, without a download."""
    from codex_ci_input_intake import HFRole
    from core.rubric_loader import RubricLoader
    from core.task_checkpoint import rubric_order_fingerprint

    rubric = json.loads(context.run.grader_config_json)["rubric"]
    revision, specs, origins = _origins(context)
    require(rubric["revision"] == revision and rubric["repo_id"] == "openai/gdpval",
            "fixed_rubric_identity_mismatch")
    data_root = (checkout / "batch-runner" / rubric["cache_dir"]).resolve()
    require(data_root.is_relative_to(checkout), "rubric_cache_escape")
    loader = RubricLoader(rubric["repo_id"], revision, str(data_root))
    snapshot = data_root / loader.SNAPSHOT_DIRNAME / revision
    (name, _, _, member, _), = [origin for origin in origins if origin[4] == HFRole.PARQUET]
    parquet = output._bytes(snapshot / member, limit=output.MAX_FILE_BYTES)
    require(pilot._identity(parquet)["sha256"] == specs[name]["sha256"], "original_rubric_bytes_changed")
    manifest_path = snapshot / loader.MANIFEST_FILENAME
    manifest = output._bytes(manifest_path, limit=output.MAX_MANIFEST_BYTES)
    _same(pilot._json_object(manifest), loader._build_snapshot_manifest(snapshot), "original_rubric_manifest_changed")
    loader._validate_snapshot(snapshot)  # Present and valid before load can consider a download.
    task = loader.load(context.cell["task_id"])
    allowed = {origin[3]: origin for origin in origins if origin[4] != HFRole.PARQUET}
    require(len(task.reference_files) == len(set(task.reference_files)) and set(task.reference_files) <= allowed.keys(),
            "registered_rubric_references_required")
    bindings = {str((snapshot / member).relative_to(checkout)): pilot._identity(parquet),
                str(manifest_path.relative_to(checkout)): pilot._identity(manifest)}
    for member in task.reference_files:
        name, repo, ref, _, _ = allowed[member]
        path = data_root / ("datasets--" + repo.replace("/", "--")) / "snapshots" / ref / member
        data = output._bytes(path, limit=output.MAX_FILE_BYTES)
        require(pilot._identity(data)["sha256"] == specs[name]["sha256"], "original_reference_bytes_changed")
        bindings[str(path.relative_to(checkout))] = pilot._identity(data)
    item_ids = [item.rubric_item_id for item in task.rubric_items]
    return {"files": bindings, "rubric_item_ids": item_ids, "rubric_fingerprint": rubric_order_fingerprint(item_ids)}


def prepare(context, root, *, _test_api=None, _test_transport=None):
    run = _authority(context)
    _source(context)
    fixed = _fixed(context.selector)
    root = grade._root(root, new=True)
    transport = _test_transport or pilot.LocalTransport()
    with grade._lock(root):
        if context.selector == SELECTOR:
            record = reader.read_result(expectation=reader.EXPECTATION, destination=root / "retained",
                expected_reader_sha256=READER["module_sha256"], terminal_revision=RESULT["terminal_commit"],
                discover_terminal=False, _test_api=_test_api)
        else:
            record = fixed.read_result(root / "retained", _test_api=_test_api)
        files = _intake(record, root / "retained", selector=context.selector)
        grade._record(root / "intake-receipt.json", record)
        # This is a derived materializer identity, not an original pilot claim.
        evidence = {"terminal": {"output_commit": record["output_commit"]}}
        identity = grade._inference_identity(context, evidence, files, retained._target())
        grade._record(root / "inference-identity.json", identity)
        identity_sha = pilot._identity(retained._encoded(identity))["sha256"]
        upload = grade._cache(root, "original-upload")
        for name, data in files.items():
            if name.startswith("deliverable_files/"):
                grade._put(configs._path(upload, name), data)
        materialized_path = _materialize_bound_codex_grading_input(context.run, plan=context.grading,
            manifest=load_plan(ROOT / registration.ORIGINAL_PROFILE), inference_results=root / "retained" / reader.RESULT,
            source_upload=upload, inference_identity=root / "inference-identity.json",
            approved_identity_sha256=identity_sha, destination=root / "inputs")
        members, materialized = _derived_inputs(context, files, identity)
        require(materialized_path == root / "inputs" / context.run.inference_results_path,
                "retention_materialization_path_changed")
        require(materialized["task_status"] == "success", "retention_grade_successful_input_required")
        checkout = root / "source"
        transport.checkout(checkout, context.controller_source_sha)
        _source(context, checkout)
        immutable = {}
        for name, data in configs._files(context.grading, context.run.run_id).items():
            grade._put(checkout / name, data)
            immutable[name] = pilot._identity(data)
        for relative, expected in members.items():
            data = output._bytes(configs._path(root / "inputs", relative), limit=output.MAX_FILE_BYTES,
                                 expected=pilot._identity(expected))
            grade._put(checkout / relative, data)
            immutable[relative] = pilot._identity(data)
        with retained._session(_test_api, response_bytes_limit=output.MAX_FILE_BYTES) as (api, token, deadline):
            rubric = grade._stage_rubric(context, checkout, api, grade._cache(root, "rubric"), token, deadline,
                                        original_origins=_origins(context))
        _same(_rubric_readback(context, checkout), rubric, "original_rubric_readback_changed")
        immutable.update(rubric["files"])
        entry = grade._entry_contract(context, checkout, record["output_commit"])
        require(entry["grader_source_hash"] == fixed.GRADER_SHA256, "retention_materialized_grader_mismatch")
        prepared = {"format": fixed.PREPARATION_FORMAT, "source_sha": context.controller_source_sha,
            "fixed_evidence_sha256": fixed_evidence_sha256(context.selector), "approval_sha256": pilot._digest(
                approval_request(context.controller_source_sha, run, selector=context.selector)), "intake_sha256": record["intake_sha256"],
            "entry": entry, "rubric": rubric, "immutable_files": immutable, "identity_sha256": identity_sha,
            "materialization": materialized, "evidence": evidence, "judge_ready": True}
        grade._record(root / "prepared.json", prepared)
        return prepared


def _ready(context, root):
    run = _authority(context)
    _source(context)
    fixed = _fixed(context.selector)
    prepared = retained._read(root / "prepared.json")
    for key, value in {"format": fixed.PREPARATION_FORMAT, "source_sha": context.controller_source_sha,
            "fixed_evidence_sha256": fixed_evidence_sha256(context.selector), "approval_sha256": pilot._digest(
                approval_request(context.controller_source_sha, run, selector=context.selector)), "intake_sha256": fixed.RESULT["intake_sha256"],
            "judge_ready": True}.items():
        _same(prepared.get(key), value, "bound_retention_grade_preparation_required")
    files = _intake(retained._read(root / "intake-receipt.json"), root / "retained", selector=context.selector)
    evidence = {"terminal": {"output_commit": fixed.RESULT["output_commit"]}}
    _same(prepared["evidence"], evidence, "retention_prepared_output_changed")
    identity = grade._inference_identity(context, evidence, files, retained._target())
    _same(retained._read(root / "inference-identity.json"), identity, "retention_inference_identity_changed")
    _same(prepared["identity_sha256"], pilot._identity(retained._encoded(identity))["sha256"],
          "retention_inference_identity_changed")
    members, materialized = _derived_inputs(context, files, identity)
    _same(prepared["materialization"], materialized, "retention_materialized_result_changed")
    _source(context, root / "source")
    require(prepared["entry"]["grader_source_hash"] == fixed.GRADER_SHA256, "retention_materialized_grader_mismatch")
    expected_files = {name: pilot._identity(data) for name, data in
                      {**configs._files(context.grading, context.run.run_id), **members}.items()}
    rubric = _rubric_readback(context, root / "source")
    _same(prepared["rubric"], rubric, "retention_prepared_rubric_changed")
    expected_files.update(rubric["files"])
    _same(prepared["immutable_files"], expected_files, "retention_prepared_file_set_changed")
    for name, expected in expected_files.items():
        output._bytes(configs._path(root / "source", name), limit=output.MAX_FILE_BYTES, expected=expected)
    _same(grade._entry_contract(context, root / "source", fixed.RESULT["output_commit"]), prepared["entry"],
          "retention_prepared_entry_changed")
    return prepared


def _parent(api, repo, cache, token, deadline, *, selector=SELECTOR):
    fixed = _fixed(selector)
    if selector != SELECTOR:
        return fixed.parent_controls(api, repo, cache, token, deadline)
    cell = {"cell_id": PARENT["cell_id"], "run_id": PARENT["campaign_id"] + "__" + PARENT["cell_id"]}
    claim_path, terminal_path = grade._paths(cell)
    terminal, data = retained._control(api, repo, PARENT["revision"], terminal_path,
        grade._cache(cache, "a2-terminal"), token, deadline, expected=PARENT["terminal_identity"], written_at=PARENT["revision"])
    binding = terminal["binding"]
    for key, value in {"campaign_id": PARENT["campaign_id"], "branch": PARENT["branch"], "cell_id": PARENT["cell_id"],
            "controller_source_sha": PARENT["writer_source_sha"], "source_sha": grade.TASK3_A1_PRODUCER_SOURCE,
            "github_run": PARENT["writer_run"], "policy": ungraded.TASK5_A2_POLICY,
            "proof_boundary": grade.PROOF, "repository_name_sha256": retained.TARGET_SHA256}.items():
        _same(binding.get(key), value, "fixed_grading_parent_binding_mismatch")
    _same(terminal.get("claim_commit"), PARENT["claim_revision"], "fixed_grading_parent_claim_mismatch")
    _same(terminal.get("claim_identity"), PARENT["claim_identity"], "fixed_grading_parent_claim_mismatch")
    claim, claim_data = retained._control(api, repo, PARENT["claim_revision"], claim_path,
        grade._cache(cache, "a2-claim"), token, deadline, expected=PARENT["claim_identity"], written_at=PARENT["claim_revision"])
    require(set(claim) == {"format", "binding", "expected_parent", "predecessor"}, "fixed_grading_parent_claim_mismatch")
    _same(claim, {**claim, "format": ungraded.CLAIM_FORMAT, "binding": binding}, "fixed_grading_parent_claim_mismatch")
    expected_terminal = ungraded._terminal(binding, {"returned_commit": PARENT["claim_revision"],
        "claim_identity": PARENT["claim_identity"]}, {"terminal": {"completion": terminal["inference_completion"]},
        "manifest": {"missing": terminal["inference_missing"]}})
    require(data == retained._encoded(expected_terminal), "completed_model_free_parent_required")
    link = claim["predecessor"]
    require(type(link) is dict and set(link) == {"cell_id", "revision", "sha256", "size"}
            and link["cell_id"] == grade.TASK5_B2_CELL and link["revision"] == claim["expected_parent"]
            and len({PARENT["revision"], PARENT["claim_revision"], link["revision"]}) == 3,
            "fixed_grading_parent_predecessor_mismatch")
    identity = {key: link[key] for key in ("sha256", "size")}
    ungraded._task5_a2_history(api, repo, link["revision"], identity, grade._cache(cache, "bounded-history"), token, deadline,
                              record_revisions=(PARENT["revision"], PARENT["claim_revision"]))
    previous_path = grade._paths({"cell_id": grade.TASK5_B2_CELL,
                                 "run_id": PARENT["campaign_id"] + "__" + grade.TASK5_B2_CELL})[1]
    _, previous = retained._control(api, repo, link["revision"], previous_path, grade._cache(cache, "b2"), token, deadline,
                                    expected=identity, written_at=link["revision"])
    retained._objects(api, repo, PARENT["claim_revision"], [retained._object(previous_path, previous)],
                      token, deadline, written_at=link["revision"])
    inherited = [(retained._object(terminal_path, data), PARENT["revision"]),
                 (retained._object(claim_path, claim_data), PARENT["claim_revision"])]
    retained._objects(api, repo, PARENT["revision"], [inherited[1][0]], token, deadline, written_at=PARENT["claim_revision"])
    return inherited


def _binding(context, prepared):
    run = _authority(context)
    fixed = _fixed(context.selector)
    return {"source_sha": context.controller_source_sha, "selector": context.selector, "cell_id": fixed.CELL,
        "fixed_evidence_sha256": fixed_evidence_sha256(context.selector), "intake_sha256": prepared["intake_sha256"],
        "approval_sha256": pilot._digest(approval_request(context.controller_source_sha, run, selector=context.selector)), "github_run": run,
        "entry": prepared["entry"], "grading_plan_sha256": pilot._digest(context.grading.as_dict()),
        "preparation_sha256": pilot._digest(prepared), "proof_boundary": grade.PROOF}


def claim(context, root, *, _test_api=None):
    root = grade._root(root)
    with grade._lock(root):
        prepared = _ready(context, root)
        fixed = _fixed(context.selector)
        binding = _binding(context, prepared)
        require(not any(os.path.lexists(root / name) for name in ("claim-reserved.json", "claim-receipt.json")),
                "retention_grade_claim_already_reserved")
        result = grade._observation(stage="retention_grade_claim")
        try:
            with retained._session(_test_api) as (api, token, deadline):
                repo = retained._target()
                require(output._metadata(api, repo, grade.BRANCH, token, deadline)["sha"] == fixed.PARENT["revision"],
                        "fixed_grading_parent_drift")
                inherited = _parent(api, repo, grade._cache(root, "parent"), token, deadline, selector=context.selector)
                require(api.get_paths_info(repo_id=repo, repo_type="dataset", revision=fixed.PARENT["revision"],
                    paths=[fixed.PREFIX], token=token) == [], "retention_result_already_claimed_for_grading")
                require(output._metadata(api, repo, grade.BRANCH, token, deadline)["sha"] == fixed.PARENT["revision"],
                        "fixed_grading_parent_drift")
                value = {"format": fixed.CLAIM_FORMAT, "binding": binding, "expected_parent": fixed.PARENT["revision"],
                         "predecessor": fixed.PARENT}
                grade._record(root / "claim-reserved.json", value)
                revision = grade._commit(api, repo, fixed.PARENT["revision"], {fixed.CLAIM_PATH: retained._encoded(value)},
                                         token, deadline, result)
                confirmed, data = retained._control(api, repo, revision, fixed.CLAIM_PATH, grade._cache(root, "claim-verified"),
                    token, deadline, expected=pilot._identity(retained._encoded(value)), written_at=revision)
                _same(confirmed, value, "retention_grade_claim_readback_mismatch")
                for item, written_at in inherited:
                    retained._objects(api, repo, revision, [item], token, deadline, written_at=written_at)
                grade._put(root / "claim-verified.json", data)
                result.update(outcome="acknowledged", claim=value, claim_identity=pilot._identity(data))
        except (Exception, KeyboardInterrupt) as error:
            grade._failed(result, error)
        grade._record(root / "claim-receipt.json", result)
        return result


def _admission(context, root, prepared):
    fixed = _fixed(context.selector)
    value = retained._read(root / "claim-receipt.json")
    require(value.get("outcome") == "acknowledged" and output._hash(value.get("returned_commit"), 40),
            "acknowledged_retention_grade_admission_required")
    require(value["returned_commit"] != fixed.PARENT["revision"], "retention_grade_claim_revision_changed")
    expected = {"format": fixed.CLAIM_FORMAT, "binding": _binding(context, prepared),
                "expected_parent": fixed.PARENT["revision"], "predecessor": fixed.PARENT}
    _same(value["claim"], expected, "retention_grade_admission_changed")
    _same(retained._read(root / "claim-reserved.json"), expected, "retention_grade_admission_changed")
    data = retained._encoded(expected)
    _same(value["claim_identity"], pilot._identity(data), "retention_grade_admission_changed")
    require(output._bytes(root / "claim-verified.json", limit=output.MAX_MANIFEST_BYTES,
                         expected=value["claim_identity"]) == data, "retention_grade_admission_changed")
    return value


def judge(context, root, *, _test_transport=None):
    root = grade._root(root)
    with grade._lock(root) as descriptor:
        prepared = _ready(context, root)
        admitted = _admission(context, root, prepared)
        return grade._owned_judge(context, root, prepared, admitted, descriptor, _test_transport=_test_transport)


def _terminal(api, repo, revision, expected, admission, cache, token, deadline, *, selector=SELECTOR):
    fixed = _fixed(selector)
    value, data = retained._control(api, repo, revision, fixed.TERMINAL_PATH, cache, token, deadline,
        expected=pilot._identity(retained._encoded(expected)), written_at=revision)
    _same(value, expected, "retention_grade_terminal_changed")
    claim, raw = retained._control(api, repo, admission["returned_commit"], fixed.CLAIM_PATH,
        grade._cache(cache, "claim"), token, deadline, expected=admission["claim_identity"],
        written_at=admission["returned_commit"])
    _same(claim, admission["claim"], "retention_grade_terminal_claim_changed")
    require(revision not in {fixed.PARENT["revision"], admission["returned_commit"]}
            and value["claim_commit"] == admission["returned_commit"] and value["child"]["cleanup_confirmed"] is True,
            "retention_grade_terminal_cleanup_required")
    retained._objects(api, repo, revision, [retained._object(fixed.CLAIM_PATH, raw)], token, deadline,
                      written_at=admission["returned_commit"])
    if value["files"]:
        retained._objects(api, repo, revision, [{key: item for key, item in row.items() if key != "role"}
                          for row in value["files"]], token, deadline, written_at=revision)
    return pilot._identity(data)


def publish(context, root, *, _test_api=None):
    root = grade._root(root)
    with grade._lock(root):
        prepared = _ready(context, root)
        fixed = _fixed(context.selector)
        admitted = _admission(context, root, prepared)
        child = retained._read(root / "judge-receipt.json")
        owner = output._checkpoint(root / "judge-owner.json")
        require(child["entry_invoked"] is True and child["cleanup_confirmed"] is True
                and all(owner.get(key) == value for key, value in {
                    "plan_sha256": hashlib.sha256(context.grading.canonical_bytes()).hexdigest(),
                    "cell_id": fixed.CELL, "stage": "fixed_grading", "attempt": 1, "phase": "reaped",
                    "tree_reaped": True, "owner_reaped": True}.items()), "grade_cleanup_unconfirmed")
        ledger_type = (output.RetentionFirstCellLedgerBinding if context.selector == SELECTOR
                       else output.RetentionKeepR2LedgerBinding)
        files, roles, outcome = grade._grade_files(context, root, prepared, child,
            retention_first_cell_binding=ledger_type(
                config_hash=prepared["entry"]["config_hash"],
                grader_source_hash=prepared["entry"]["grader_source_hash"]))
        terminal = {"format": fixed.TERMINAL_FORMAT, "binding": admitted["claim"]["binding"],
            "claim_commit": admitted["returned_commit"], "claim_identity": admitted["claim_identity"],
            "outcome": outcome, "child": child,
            "files": [{"role": roles[name], **retained._object(fixed.PREFIX + "/" + name, data)} for name, data in sorted(files.items())],
            "missing": [role for role in ("grade_result", "grade_cost_ledger") if role not in roles.values()],
            "invoice_complete": False, "http_request_count": None}
        payload = {fixed.PREFIX + "/" + name: data for name, data in files.items()}
        payload[fixed.TERMINAL_PATH] = retained._encoded(terminal)
        grade._record(root / "publication-reserved.json", {"terminal": terminal,
            "expected_parent": admitted["returned_commit"], "terminal_identity": pilot._identity(payload[fixed.TERMINAL_PATH])})
        result = grade._observation(stage="retention_grade_publication")
        try:
            with retained._session(_test_api) as (api, token, deadline):
                repo = retained._target()
                require(output._metadata(api, repo, grade.BRANCH, token, deadline)["sha"] == admitted["returned_commit"],
                        "retention_grade_publication_parent_changed")
                require(api.get_paths_info(repo_id=repo, repo_type="dataset", revision=admitted["returned_commit"],
                    paths=sorted(payload), token=token) == [], "retention_grade_payload_already_exists")
                revision = grade._commit(api, repo, admitted["returned_commit"], payload, token, deadline, result)
                identity = _terminal(api, repo, revision, terminal, admitted,
                    grade._cache(root, "publication-verified"), token, deadline, selector=context.selector)
                result.update(outcome="acknowledged", terminal_identity=identity, grading_state=outcome)
        except (Exception, KeyboardInterrupt) as error:
            grade._failed(result, error)
        grade._record(root / "publication-receipt.json", result)
        return result


def reconcile(context, root, *, _test_api=None):
    """Observe only this owner's reserved publication; never amend its receipt."""
    root = grade._root(root)
    with grade._lock(root):
        prepared = _ready(context, root)
        fixed = _fixed(context.selector)
        admitted = _admission(context, root, prepared)
        reservation = retained._read(root / "publication-reserved.json")
        _same(reservation["terminal_identity"], pilot._identity(retained._encoded(reservation["terminal"])),
              "retention_grade_reservation_changed")
        _same(reservation["terminal"]["binding"], admitted["claim"]["binding"], "retention_grade_reservation_changed")
        result = grade._observation(stage="retention_grade_server_reconciliation")
        try:
            with retained._session(_test_api) as (api, token, deadline):
                from huggingface_hub import RepoFile
                repo = retained._target()
                head = output._metadata(api, repo, grade.BRANCH, token, deadline)["sha"]
                found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=head,
                    paths=[fixed.TERMINAL_PATH], expand=True, token=token)
                require(len(found) == 1 and isinstance(found[0], RepoFile), "retention_grade_terminal_unresolved")
                revision = getattr(found[0].last_commit, "oid", None)
                require(output._hash(revision, 40), "retention_grade_terminal_unresolved")
                identity = _terminal(api, repo, revision, reservation["terminal"], admitted,
                    grade._cache(root, "reconciliation-read"), token, deadline, selector=context.selector)
                result.update(outcome="verified_server_state", returned_commit=revision,
                    terminal_identity=identity, writer_acknowledgment="not_established")
        except (Exception, KeyboardInterrupt) as error:
            grade._failed(result, error)
        grade._record(root / "grade-server-observation.json", result)
        return result


def main(argv=None, *, _test_api=None, _test_transport=None):
    try:
        parser = output._Parser(description=__doc__)
        parser.add_argument("--selector", default=SELECTOR)
        parser.add_argument("--reviewed-source-sha", required=True)
        parser.add_argument("--producer-source-sha", default="")
        parser.add_argument("--terminal-revision", default="")
        parser.add_argument("--root", required=True, type=Path)
        parser.add_argument("--phase", choices=("plan", "prepare", "claim", "judge", "publish", "reconcile"), default="plan")
        args = parser.parse_args(argv)
        grade._workflow_inputs()
        context = compile_request(args.reviewed_source_sha, selector=args.selector,
                                  terminal=args.terminal_revision, producer=args.producer_source_sha)
        fixed = _fixed(context.selector)
        if args.phase != "plan" or (os.environ.get("GITHUB_ACTIONS") == "true"
                                   and os.environ.get("PILOT_GRADE_DRY_RUN") == "false"):
            _authority(context)  # Before renderer, HF, OIDC, or any owned reservation.
        if args.phase == "plan":
            result = {"outcome": "plan_only", "judge_ready": False, "commands": [],
                "fixed_evidence_sha256": fixed_evidence_sha256(context.selector), "grading_parent": fixed.PARENT["revision"],
                "inference_terminal": fixed.RESULT["terminal_commit"], "grade": None}
        else:
            require(args.terminal_revision == fixed.RESULT["terminal_commit"], "explicit_retention_terminal_required")
            if args.phase == "prepare":
                prepared = prepare(context, args.root, _test_api=_test_api, _test_transport=_test_transport)
                from core.azure_ai_clients import grader_route_workloads
                result = {"outcome": "prepared", "judge_ready": True, "grade": None,
                          "intake_sha256": prepared["intake_sha256"]}
                if os.environ.get("GITHUB_OUTPUT"):
                    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                        stream.write("judge_ready=true\nazure_ai_workloads_json=" + json.dumps(
                            [f"{workload.value}={deployment}" for workload, deployment in
                             grader_route_workloads(json.loads(context.run.grader_config_json))],
                            separators=(",", ":")) + "\n")
            elif args.phase == "judge":
                result = judge(context, args.root, _test_transport=_test_transport)
                result["outcome"] = "child_reaped" if result["cleanup_confirmed"] else "unresolved"
            else:
                result = {"claim": claim, "publish": publish, "reconcile": reconcile}[args.phase](
                    context, args.root, _test_api=_test_api)
        safe = {key: value for key, value in result.items() if key in {
            "outcome", "stage", "reason", "http_status", "returned_commit", "terminal_identity", "grading_state",
            "cleanup_confirmed", "entry_invoked", "exit_code", "timed_out", "judge_ready", "grade", "commands",
            "fixed_evidence_sha256", "intake_sha256", "grading_parent", "inference_terminal", "writer_acknowledgment"}}
        safe.update(selector=context.selector, source_sha=context.controller_source_sha, invoice_complete=False,
                    inference_launched=False, automatic_retry=False)
        print(json.dumps(safe, sort_keys=True))
        return 0 if result["outcome"] in {"plan_only", "prepared", "acknowledged", "child_reaped", "verified_server_state"} else 2
    except (Exception, KeyboardInterrupt) as error:
        reason = str(error) if type(error) is output.OutputPublicationRefused else "retention_fixed_grade_refused:" + type(error).__name__
        print(json.dumps({"outcome": "refused", "reason": reason, "inference_launched": False,
                          "automatic_retry": False, "invoice_complete": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    from codex_retention_fixed_grade import main as canonical_main
    raise SystemExit(canonical_main())
