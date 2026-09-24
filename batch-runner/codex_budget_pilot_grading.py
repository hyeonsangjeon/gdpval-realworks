"""One retained pilot cell, the fixed Step8 grader, and a separate private branch.

Plan is local and free of credential lookup. Live phases are explicit, one-use
host operations; they are not a launcher or permission grant. Inference main is
read-only here. A publication-derived identity is not independent provider
authentication of the original inputs. No inference completion-v1 is emitted.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import gpt54_run_config_bundle as configs
import gpt54_v2_grading_input as primitives
from core.hf_publication import _PublicationFile, _publication_additions, _remote_download_file
from core.result_fingerprint import validate_inference_result_fingerprint

BRANCH = "pilot-grades-20260923"
WORKFLOW = ".github/workflows/grade-run.yml"
CLAIM_FORMAT = "codex-pilot-grade-claim-v1"
RESULT_FORMAT = "codex-pilot-grade-terminal-v1"
PROOF = "verified_publication_derived_not_independent_provider_authentication"
# Step8 keeps its compiled command and default 14,400-second budget. This host
# ceiling leaves two minutes to stop/reap its owned tree, not another attempt.
CHILD_SECONDS = 14_520
require = output._require


_INSPECTION_REASONS = output.TARGET_CHECK_REASONS | frozenset({
    "selected_private_target_mismatch", "explicit_first_attempt_reviewed_grading_context_required",
    "grading_run_identity_required", "pilot_grade_override_refused", "reviewed_grading_source_required",
    "branch_inspection_has_no_inference_revision", "pilot_grade_mode_conflict",
    "grading_source_preflight_refused", "hf_revision_not_found", "grading_branch_absent",
    "grading_branch_identity_mismatch", "grading_branch_privacy_unavailable",
    "private_grading_branch_required", "grading_branch_head_unavailable",
    "recorded_bootstrap_required", "grading_branch_seed_mismatch",
})
_INSPECTION_DRIFT = frozenset({
    "grading_branch_identity_mismatch", "private_grading_branch_required",
    "recorded_bootstrap_required", "grading_branch_seed_mismatch",
})


_ENTRY_REFUSALS = {
    "source_preflight": ("grading_source_preflight_refused", False),
    "branch_root": ("grading_root_refused", False),
    "branch_receipt": ("grading_receipt_refused", True),
}


class _EntryRefused(ValueError):
    def __init__(self, stage: str):
        super().__init__(_ENTRY_REFUSALS[stage][0])
        self.stage = stage


@contextmanager
def _entry_boundary(stage: str):
    """Closed local diagnostics, never exception text or retry authority."""
    try:
        yield
    except (Exception, KeyboardInterrupt) as error:
        raise _EntryRefused(stage) from error


@dataclass
class Context:
    plan: dict
    cell: dict
    grading: object
    terminal_revision: str

    @property
    def run(self):
        return self.grading.runs[0]


def compile_request(selector: str, source: str, terminal: str = "") -> Context | None:
    retained._target()  # Fixed tracked namespace/fingerprint, never an endpoint input.
    require(output._hash(source, 40), "reviewed_grading_source_required")
    if selector in {"pilot/branch-setup", "pilot/branch-inspect"}:
        require(terminal == "", "branch_setup_has_no_inference_revision" if selector == "pilot/branch-setup"
                else "branch_inspection_has_no_inference_revision")
        return None
    require(selector.startswith("pilot/"), "canonical_pilot_selector_required")
    plan, cell, grading = adapter.compile_cell_grading_plan(ci.CAMPAIGN, selector[6:], source)
    require(terminal == "" or output._hash(terminal, 40), "immutable_terminal_revision_required")
    require(terminal not in {source, retained.BOOTSTRAP, plan["dataset"]["revision"]},
            "inference_terminal_revision_required")
    return Context(plan, cell, grading, terminal)


def _ci_authority(source: str) -> dict:
    expected = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "PILOT_GRADE_PAID_APPROVAL": "true", "PILOT_GRADE_DRY_RUN": "false",
    }
    require(all(os.environ.get(name) == value for name, value in expected.items()),
            "explicit_first_attempt_reviewed_grading_context_required")
    run = {"id": os.environ.get("GITHUB_RUN_ID"), "job": os.environ.get("GITHUB_JOB"), "attempt": 1}
    require(type(run["id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run["id"]) is not None
            and type(run["job"]) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,99}", run["job"]) is not None,
            "grading_run_identity_required")
    return run


def _root(path: Path, *, new: bool = False) -> Path:
    require(".." not in path.parts, "unsafe_grading_root")
    root = pilot._assert_no_symlink_ancestors(Path(os.path.abspath(path)))
    if new:
        root.mkdir(mode=0o700, exist_ok=False)
        output._write_no_clobber(root / "lock", b"")
    require(root.is_dir() and root.stat().st_mode & 0o777 == 0o700, "private_grading_root_required")
    return root


@contextmanager
def _lock(root: Path):
    pilot._regular_private(root / "lock")
    with os.fdopen(os.open(root / "lock", os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield stream.fileno()


def _cache(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(mode=0o700, exist_ok=False)
    return path


def _put(path: Path, data: bytes) -> None:
    pilot._assert_no_symlink_ancestors(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output._write_no_clobber(path, data)


def _record(path: Path, value: dict) -> None:
    _put(path, retained._encoded(value))
    output._fsync_directory(path.parent)


def _paths(cell: dict) -> tuple[str, str]:
    prefix = f"cell-grades/{ci.CAMPAIGN}/{cell['cell_id']}"
    return prefix + "/claim.json", prefix + "/terminal.json"


def _observation(outcome="unresolved", *, stage: str) -> dict:
    return {"outcome": outcome, "stage": stage, "reason": None, "http_status": None,
            "returned_commit": None}


def _failed(observed: dict, error: BaseException) -> None:
    observed["reason"], observed["http_status"] = output._error_context(error)


def _inspection_observation() -> dict:
    return {"role": "fixed_private_pilot_grading_branch_inspection", "repository_name_sha256": retained.TARGET_SHA256,
            "outcome": "plan_only", "stage": "plan", "reason": None, "http_status": None,
            "branch_state": "inaccessible_or_unknown", "head": None, "matches_bootstrap": None,
            "exact_identity_match": False, "private": None, "bootstrap_access_verified": False,
            "observed_at": None, "remote_mutation_possible": False, "judge_entry_requested": False,
            "inference_requested": False, "grade_success": False, "automatic_retry": False}


def _inspection_failed(observed: dict, reason: str) -> None:
    observed["reason"] = ({"publication_timeout": "grading_branch_inspection_timeout",
                           "publication_interrupted": "grading_branch_inspection_interrupted"}.get(reason)
                          or (reason if reason in _INSPECTION_REASONS else "grading_branch_inspection_failed"))
    observed["outcome"] = "blocked_drift" if reason in _INSPECTION_DRIFT else "refused"


def inspect_branch(source: str) -> dict:
    """Two bounded metadata reads, never setup replay or historical acknowledgment.

    No grading root or receipt is opened. These responses are not an atomic
    snapshot, write permission, grading readiness, or authority to create/reset.
    """
    observed = _inspection_observation()
    observed.update(outcome="refused", stage="inspection_preflight")
    try:
        _ci_authority(source)
        repo = retained._target()
        token = os.environ.get("HF_TOKEN", "")
        require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
                "explicit_hf_token_required")
        from codex_ci_input_intake import _hf_environment

        with output._time_bound(output.TARGET_CHECK_SECONDS) as deadline, _hf_environment(online=True):
            for revision, stage in ((retained.BOOTSTRAP, "bootstrap_metadata"), (BRANCH, "branch_metadata")):
                observed.update(stage=stage, http_status=None)
                with output._hf_client(token, deadline, metadata_repo=repo, metadata_revision=revision,
                                       observation=observed) as api:
                    metadata = api.repo_info(repo_id=repo, repo_type="dataset", revision=revision, token=token,
                                             timeout=output._remaining(deadline))
                observed["exact_identity_match"] = getattr(metadata, "id", None) == repo
                private = getattr(metadata, "private", None)
                observed["private"] = private if type(private) is bool else None
                require(observed["exact_identity_match"], "grading_branch_identity_mismatch")
                require(type(private) is bool, "grading_branch_privacy_unavailable")
                require(private is True, "private_grading_branch_required")
                head = getattr(metadata, "sha", None)
                require(output._hash(head, 40), "grading_branch_head_unavailable")
                if stage == "bootstrap_metadata":
                    require(head == retained.BOOTSTRAP, "recorded_bootstrap_required")
                    observed["bootstrap_access_verified"] = True
                else:
                    observed.update(branch_state="present", head=head, matches_bootstrap=head == retained.BOOTSTRAP)
                    require(observed["matches_bootstrap"], "grading_branch_seed_mismatch")
                output._remaining(deadline)
            observed["outcome"] = "observed"
    except (Exception, KeyboardInterrupt) as error:
        reason, status = output._error_context(error)
        if (observed["bootstrap_access_verified"] and observed["stage"] == "branch_metadata"
                and reason == "hf_revision_not_found" and status == 404):
            observed.update(outcome="observed", branch_state="absent", reason="grading_branch_absent")
        else:
            _inspection_failed(observed, reason)
    observed["observed_at"] = datetime.now(timezone.utc).isoformat()
    return observed


def setup(root: Path, source: str, *, _test_api=None) -> dict:
    """Explicit branch creation only, never implicit in preparation/grading."""
    github_run = _ci_authority(source)
    result = _observation(stage="branch_setup")
    with ExitStack() as stack:
        with _entry_boundary("branch_root"):
            root = _root(root, new=True)
            stack.enter_context(_lock(root))
        try:
            with retained._session(_test_api) as (api, token, deadline):
                repo = retained._target()
                require(output._metadata(api, repo, retained.BOOTSTRAP, token, deadline)["sha"]
                        == retained.BOOTSTRAP, "recorded_bootstrap_required")
                try:
                    output._metadata(api, repo, BRANCH, token, deadline)
                except output.OutputPublicationRefused as error:
                    require(error.http_status == 404, "grading_branch_absence_not_established")
                else:
                    raise output.OutputPublicationRefused("grading_branch_already_exists")
                _record(root / "branch-reserved.json", {
                    "repository_name_sha256": retained.TARGET_SHA256, "branch": BRANCH,
                    "bootstrap": retained.BOOTSTRAP, "source_sha": source, "github_run": github_run,
                })
                output._remaining(deadline)
                api.create_branch(repo_id=repo, repo_type="dataset", branch=BRANCH,
                                  revision=retained.BOOTSTRAP, exist_ok=False, token=token)
                head = output._metadata(api, repo, BRANCH, token, deadline)["sha"]
                result["returned_commit"] = head
                require(head == retained.BOOTSTRAP, "grading_branch_seed_mismatch")
                result.update(outcome="acknowledged", stage="branch_verified")
        except (Exception, KeyboardInterrupt) as error:
            _failed(result, error)
        with _entry_boundary("branch_receipt"):
            _record(root / "branch-receipt.json", result)
    return result


def _retained_input(context: Context, api, repo: str, cache: Path, token: str, deadline: float) -> dict:
    require(output._hash(context.terminal_revision, 40), "immutable_terminal_revision_required")
    revision, cell = context.terminal_revision, context.cell
    require(output._metadata(api, repo, revision, token, deadline)["sha"] == revision,
            "retained_terminal_metadata_mismatch")
    preliminary = _cache(cache, "binding")
    claim_path, terminal_path, _ = retained._paths(cell)
    terminal, _ = retained._control(api, repo, revision, terminal_path, preliminary, token, deadline,
                                    written_at=revision)
    claim, _ = retained._control(api, repo, terminal["claim_commit"], claim_path, preliminary, token, deadline,
                                 expected=terminal["claim_identity"], written_at=terminal["claim_commit"])
    binding = claim["binding"]
    require(binding["host"]["workflow"] == ci.WORKFLOW, "retained_inference_workflow_mismatch")
    # These are the prior host's recorded input attestations, not freshly
    # authenticated originals. The existing validator binds all of them to
    # the real compiler, immutable claim, manifest and completion projection.
    inputs = {"files_sha256": binding["verified_inputs_sha256"],
              "source_projection_sha256": binding["source_projection_sha256"]}
    require(all(output._hash(value) for value in inputs.values()), "retained_input_hashes_required")
    plan = {**context.plan, "ci": {
        "registration_sha256": hashlib.sha256(pilot._read_bytes(ci.REGISTRATION)).hexdigest(),
        "selected_cell_id": cell["cell_id"], "host": binding["host"],
    }}
    return retained._terminal(api, repo, revision, plan, cell, inputs,
                              _cache(cache, "verified"), token, deadline)


def _fetch(api, repo: str, revision: str, member: str, expected: dict, cache: Path,
           token: str, deadline: float) -> bytes:
    require(output._hash(revision, 40) and output._hash(expected["sha256"])
            and (expected.get("size") is None or 0 <= expected["size"] <= output.MAX_FILE_BYTES),
            "bounded_immutable_file_required")
    require(member and not member.startswith("/") and ".." not in Path(member).parts
            and "\\" not in member and Path(member).as_posix() == member, "unsafe_retained_member")
    directory = _cache(cache, hashlib.sha256((repo + revision + member).encode()).hexdigest())
    downloaded = api.hf_hub_download(repo_id=repo, repo_type="dataset", revision=revision,
        filename=member, token=token, cache_dir=directory, force_download=True,
        local_files_only=False, etag_timeout=output._remaining(deadline))
    resolved = _remote_download_file(Path(downloaded))
    require(resolved.is_relative_to(directory), "grading_download_cache_escape")
    data = output._bytes(resolved, limit=output.MAX_FILE_BYTES)
    require(hashlib.sha256(data).hexdigest() == expected["sha256"]
            and (expected.get("size") is None or len(data) == expected["size"]),
            "retained_file_identity_mismatch")
    output._remaining(deadline)
    return data


def _inference_identity(context: Context, evidence: dict, files: dict[str, bytes], repo: str) -> dict:
    payload = pilot._json_object(files["step2_inference_results.json"])
    ledger = payload.get("cost_ledger")
    ledger_binding = None
    if ledger is not None:
        require(ledger["path"] == Path(pilot.LEDGER).name and ledger["path"] in files,
                "bound_inference_ledger_required")
        data = files[ledger["path"]]
        require(hashlib.sha256(data).hexdigest() == ledger["sha256"], "inference_ledger_digest_mismatch")
        output._ledger(data, context.cell)
        ledger_binding = {**ledger, "size": len(data)}
    run, grading = context.run, context.grading
    return {
        "source_repo_id": repo, "source_revision": evidence["terminal"]["output_commit"],
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "task_ids": list(run.task_ids), "producer_results_path": run.producer_results_path,
        "producer_rows_pointer": run.producer_rows_pointer,
        "manifest_sha256": grading.dispatch.manifest_sha256,
        "grading_plan_sha256": hashlib.sha256(grading.canonical_bytes()).hexdigest(),
        "config_sha256": context.cell["config_sha256"],
        "source_pins_sha256": hashlib.sha256(grading.dispatch.source_pins_json.encode()).hexdigest(),
        "inference_results_sha256": hashlib.sha256(files["step2_inference_results.json"]).hexdigest(),
        "result_fingerprint": validate_inference_result_fingerprint(payload),
        "producer_run_id": payload["run_id"], "publication_generation": payload["publication_generation"],
        "prepared_fingerprint": payload["prepared_fingerprint"],
        "deliverables": [{"task_id": row["task_id"], "files": row["deliverable_file_records"]}
                         for row in payload["results"]], "cost_ledger": ledger_binding,
    }


@contextmanager
def _cwd(path: Path):
    previous = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(previous)


def _stage_rubric(context: Context, checkout: Path, api, cache: Path, token: str, deadline: float) -> dict:
    """Only registered parquet and this task's pinned references; no Step0/gold."""
    from codex_ci_input_intake import _hf_origins, HFRole
    from core.rubric_loader import RubricLoader

    config = json.loads(context.run.grader_config_json)
    rubric = config["rubric"]
    revision, specs, origins = _hf_origins()
    require(rubric["revision"] == revision and rubric["repo_id"] == "openai/gdpval",
            "fixed_rubric_identity_mismatch")
    data_root = (checkout / "batch-runner" / rubric["cache_dir"]).resolve()
    require(data_root.is_relative_to(checkout), "rubric_cache_escape")
    loader = RubricLoader(rubric["repo_id"], revision, str(data_root))
    snapshot = data_root / loader.SNAPSHOT_DIRNAME / revision
    members = {origin[3]: (origin, specs[origin[0]]) for origin in origins if origin[4] != HFRole.STEP0}
    parquet = next((origin, specs[origin[0]]) for origin in origins if origin[4] == HFRole.PARQUET)
    (name, repo, ref, member, _), identity = parquet
    data = _fetch(api, repo, ref, member, identity, cache, token, deadline)
    _put(snapshot / member, data)
    _record(snapshot / loader.MANIFEST_FILENAME, loader._build_snapshot_manifest(snapshot))
    loader._validate_snapshot(snapshot)
    task = loader.load(context.cell["task_id"])
    require(len(task.reference_files) == len(set(task.reference_files)) <= len(members) - 1,
            "registered_rubric_references_required")
    bindings = {str((snapshot / member).relative_to(checkout)): pilot._identity(data)}
    bindings[str((snapshot / loader.MANIFEST_FILENAME).relative_to(checkout))] = pilot._identity(
        output._bytes(snapshot / loader.MANIFEST_FILENAME, limit=output.MAX_MANIFEST_BYTES))
    for member in task.reference_files:
        require(member in members and members[member][0][4] != HFRole.PARQUET,
                "unregistered_rubric_reference")
        (_, repo, ref, _, _), identity = members[member]
        data = _fetch(api, repo, ref, member, identity, cache, token, deadline)
        # The supported offline HF cache layout is read by RubricLoader's
        # unchanged hf_hub_download call; no token/cache discovery is required.
        destination = data_root / ("datasets--" + repo.replace("/", "--")) / "snapshots" / ref / member
        _put(destination, data)
        bindings[str(destination.relative_to(checkout))] = pilot._identity(data)
    from core.task_checkpoint import rubric_order_fingerprint
    return {"files": bindings, "rubric_item_ids": [item.rubric_item_id for item in task.rubric_items],
            "rubric_fingerprint": rubric_order_fingerprint([item.rubric_item_id for item in task.rubric_items])}


def _grade_path(context: Context, config_hash: str, source_hash: str, revision: str) -> Path:
    import step8_grade as step8

    config = json.loads(context.run.grader_config_json)
    path = step8.resolve_grade_output_path(config, experiment_id=context.run.command[2],
        judge_slug=step8._judge_slug(config["judge"]["model"]), config_hash=config_hash,
        rubric_sha=config["rubric"]["revision"], rubric_short_sha=config["rubric"]["revision"][:7],
        prompt_version=config["prompt"]["version"], inference_sha=revision, grader_source_hash=source_hash,
        diagnostic_task_scope_sha=step8._ordered_task_ids_sha256([context.cell["task_id"]]))
    relative = Path(os.path.normpath(str(Path("batch-runner") / path)))
    require(not relative.is_absolute() and relative.parts[:2] == ("data", "grades") and ".." not in relative.parts,
            "grading_output_path_escape")
    return relative


def _entry_contract(context: Context, checkout: Path, revision: str) -> dict:
    """Real local entry validation and actual materialized source/path hashes."""
    import step8_grade as step8
    from core.tools import ReadDeliverableError, get_renderer_fingerprint

    run = context.run
    with _cwd(checkout / "batch-runner"):
        config = json.loads(run.grader_config_json)
        step8.validate_grading_config(config)
        experiment = step8.load_experiment_yaml(run.command[2])
        result = step8.load_local_inference_results()
        repo, actual_revision = step8.resolve_source_inference_identity(result, config["schema_version"])
        require(repo == retained._target() and actual_revision == revision, "materialized_inference_identity_mismatch")
        tasks, _ = step8.filter_tasks_for_config(result, config, tasks_csv=context.cell["task_id"], limit=1)
        require([row["task_id"] for row in tasks] == [context.cell["task_id"]], "fixed_grade_task_required")
        step8.validate_local_deliverables(tasks, Path("workspace/upload"))
        require(experiment.name == json.loads(run.experiment_config_json)["experiment"]["name"],
                "materialized_experiment_mismatch")
        config_hash = step8.hash_config("comparison-grading.json")
        source_hash = step8.compute_grader_source_hash("comparison-grading.json", config)
        path = _grade_path(context, config_hash, source_hash, revision)
        from core.task_checkpoint import checkpoint_path
        names = [path.name, path.stem + ".cost_ledger.jsonl", checkpoint_path(path, context.cell["task_id"]).name]
        names += [path.stem + ".cost_ledger.sqlite3" + suffix for suffix in ("", "-wal", "-shm", "-journal")]
        limit = os.pathconf(checkout, "PC_NAME_MAX")
        require(all(len(name.encode()) <= limit for name in names), "grading_filename_capacity_refused")
        try:
            renderer = get_renderer_fingerprint() if step8.requires_track2_office_renderer(config) else None
        except ReadDeliverableError as error:
            raise output.OutputPublicationRefused("fixed_renderer_readiness_refused") from error
        return {"grade_path": str(path), "config_hash": config_hash,
                "grader_source_hash": source_hash, "renderer_fingerprint": renderer,
                "cost_run_id": step8.make_cost_run_id(experiment_yaml_name=run.command[2],
                    config_hash=config_hash, grader_source_hash=source_hash)}


def prepare(context: Context, root: Path, *, _test_api=None, _test_transport=None) -> dict:
    _ci_authority(context.plan["reviewed_source_sha"])
    root = _root(root, new=True)
    transport = _test_transport or pilot.LocalTransport()
    transport.require_source(context.plan, pilot.compile_pilot(ci.CAMPAIGN, context.plan["reviewed_source_sha"])[1])
    with _lock(root):
        cache = _cache(root, "fetch")
        with retained._session(_test_api, response_bytes_limit=output.MAX_FILE_BYTES) as (api, token, deadline):
            repo = retained._target()
            evidence = _retained_input(context, api, repo, cache, token, deadline)
            manifest = evidence["manifest"]
            prepared = {"cell_id": context.cell["cell_id"], "source_sha": context.plan["reviewed_source_sha"],
                "terminal_revision": context.terminal_revision, "evidence": evidence,
                "proof_boundary": PROOF, "grading_state": "UNRUN", "judge_ready": False}
            if "bound_inference_result" in manifest["missing"]:
                prepared["reason"] = "retained_result_missing_ungraded"
            else:
                files = {}
                _, _, prefix = retained._paths(context.cell)
                for record in manifest["files"]:
                    files[record["path"]] = _fetch(api, repo, evidence["terminal"]["output_commit"],
                        prefix + "/" + record["path"], record, cache, token, deadline)
                identity = _inference_identity(context, evidence, files, repo)
                for name, data in files.items():
                    base = root / "original" / ("upload" if name.startswith("deliverable_files/") else "")
                    _put(base / name, data)
                (root / "original/upload").mkdir(mode=0o700, exist_ok=True)
                _record(root / "inference-identity.json", identity)
                identity_sha = pilot._identity(retained._encoded(identity))["sha256"]
                # This invokes the mandatory native atomic install on this
                # actual host. No rename fallback, adopted tree, or retry.
                try:
                    materialized = adapter.materialize_pilot_grading_input(
                        campaign_id=ci.CAMPAIGN, cell_id=context.cell["cell_id"],
                        reviewed_source_sha=context.plan["reviewed_source_sha"],
                        inference_results=root / "original/step2_inference_results.json",
                        source_upload=root / "original/upload", inference_identity=root / "inference-identity.json",
                        approved_identity_sha256=identity_sha, destination=root / "inputs")
                except adapter.PilotGradingInputRefused as error:
                    raise output.OutputPublicationRefused("grading_input_materialization_refused") from error
                if materialized["task_status"] != "success":
                    prepared.update(materialization=materialized, identity_sha256=identity_sha,
                                    reason="retained_result_unsuccessful_ungraded")
                    _record(root / "prepared.json", prepared)
                    return prepared  # Existing failed evidence, no invented verdict or paid claim.
                checkout = root / "source"
                transport.checkout(checkout, context.plan["reviewed_source_sha"])
                configs._sources(checkout, pilot.load_plan())
                immutable = {}
                for name, data in configs._files(context.grading, context.run.run_id).items():
                    _put(checkout / name, data)
                    immutable[name] = pilot._identity(data)
                for record in manifest["files"]:
                    name = record["path"]
                    relative = "batch-runner/workspace/" + ("upload/" if name.startswith("deliverable_files/") else "") + name
                    data = primitives._read_bytes(root / "inputs" / relative)
                    _put(checkout / relative, data)
                    immutable[relative] = pilot._identity(data)
                rubric = _stage_rubric(context, checkout, api, cache, token, deadline)
                immutable.update(rubric["files"])
                prepared.update(materialization=materialized, identity_sha256=identity_sha,
                    immutable_files=immutable, rubric=rubric,
                    entry=_entry_contract(context, checkout, identity["source_revision"]), judge_ready=True)
        _record(root / "prepared.json", prepared)  # Ready last; partial roots are never adopted.
    return prepared


def _ready(context: Context, root: Path) -> dict:
    prepared = retained._read(root / "prepared.json")
    require(prepared["cell_id"] == context.cell["cell_id"]
            and prepared["source_sha"] == context.plan["reviewed_source_sha"]
            and prepared["terminal_revision"] == context.terminal_revision
            and prepared["proof_boundary"] == PROOF and prepared["grading_state"] == "UNRUN"
            and prepared["judge_ready"] is True, "bound_native_materialization_required")
    for name, identity in prepared["immutable_files"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "unsafe_prepared_member")
        output._bytes(root / "source" / name, limit=output.MAX_FILE_BYTES, expected=identity)
    configs._sources(root / "source", pilot.load_plan())
    require(_entry_contract(context, root / "source", prepared["evidence"]["terminal"]["output_commit"])
            == prepared["entry"], "prepared_grader_entry_changed")
    return prepared


def _binding(context: Context, prepared: dict, run: dict) -> dict:
    evidence = prepared["evidence"]
    return {
        "repository_name_sha256": retained.TARGET_SHA256, "branch": BRANCH,
        "campaign_id": ci.CAMPAIGN, "cell_id": context.cell["cell_id"], "run_id": context.cell["run_id"],
        "task_id": context.cell["task_id"], "source_sha": context.plan["reviewed_source_sha"],
        "config_sha256": context.cell["config_sha256"], "order_sha256": pilot._digest(context.plan["order"]),
        "grading_plan_sha256": hashlib.sha256(context.grading.canonical_bytes()).hexdigest(),
        "grader_config_sha256": hashlib.sha256(context.run.grader_config_json.encode()).hexdigest(),
        "alias": context.run.command[2], "grader_source_hash": prepared["entry"]["grader_source_hash"],
        "config_hash": prepared["entry"]["config_hash"],
        "renderer_fingerprint": prepared["entry"]["renderer_fingerprint"],
        "retained": evidence["observation"],
        "publication_receipt_sha256": evidence["terminal"]["publication_receipt_sha256"],
        "inference_identity_sha256": prepared["identity_sha256"],
        "materialized_result": prepared["materialization"]["materialized_result"],
        "proof_boundary": PROOF, "github_run": run,
    }


def _validate_binding(value: dict, context: Context, entry: dict) -> None:
    # For a preceding grading-branch tip, only host metadata/object proofs are
    # read. No other cell's grade/deliverable payload is downloaded.
    run = value["github_run"]
    require(set(run) == {"id", "job", "attempt"} and type(run["attempt"]) is int and run["attempt"] == 1
            and type(run["id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", run["id"]) is not None
            and type(run["job"]) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,99}", run["job"]) is not None,
            "grade_claim_run_mismatch")
    observed = value["retained"]
    require(set(observed) == {"cell_id", "terminal_commit", "terminal_sha256", "output_commit", "manifest_sha256"}
            and observed["cell_id"] == context.cell["cell_id"]
            and all(output._hash(observed[key], 40 if key.endswith("commit") else 64)
                    for key in ("terminal_commit", "terminal_sha256", "output_commit", "manifest_sha256"))
            and observed["terminal_commit"] == context.terminal_revision
            and observed["output_commit"] not in {context.terminal_revision, retained.BOOTSTRAP,
                 context.plan["reviewed_source_sha"], context.plan["dataset"]["revision"]},
            "grade_claim_retained_identity_mismatch")
    materialized = value["materialized_result"]
    require(set(materialized) == {"path", "size", "sha256", "result_fingerprint"}
            and materialized["path"] == context.run.inference_results_path
            and type(materialized["size"]) is int and 0 < materialized["size"] <= output.MAX_RECORD_BYTES
            and output._hash(materialized["sha256"]) and output._hash(materialized["result_fingerprint"])
            and output._hash(value["publication_receipt_sha256"]) and output._hash(value["inference_identity_sha256"]),
            "grade_claim_source_proof_mismatch")
    reconstructed = {"evidence": {"observation": observed,
                      "terminal": {"publication_receipt_sha256": value["publication_receipt_sha256"]}},
        "identity_sha256": value["inference_identity_sha256"], "entry": entry,
        "materialization": {"materialized_result": materialized}}
    require(value == _binding(context, reconstructed, run), "grade_claim_contract_mismatch")


def _grade_terminal(api, repo: str, revision: str, context: Context, entry: dict,
                    cache: Path, token: str, deadline: float) -> dict:
    claim_path, terminal_path = _paths(context.cell)
    terminal, data = retained._control(api, repo, revision, terminal_path, cache, token, deadline,
                                       written_at=revision)
    require(set(terminal) == {"format", "binding", "claim_commit", "claim_identity", "outcome",
            "child", "files", "missing", "invoice_complete", "http_request_count"}
            and terminal["format"] == RESULT_FORMAT and terminal["invoice_complete"] is False
            and terminal["http_request_count"] is None and terminal["outcome"] in {"graded", "partial", "failed", "ungraded"}
            and output._hash(terminal["claim_commit"], 40) and terminal["claim_commit"] != revision,
            "grade_terminal_contract_mismatch")
    _validate_binding(terminal["binding"], context, entry)
    claim, claim_data = retained._control(api, repo, terminal["claim_commit"], claim_path, cache, token, deadline,
        expected=terminal["claim_identity"], written_at=terminal["claim_commit"])
    require(set(claim) == {"format", "binding", "expected_parent", "predecessor"}
            and claim["format"] == CLAIM_FORMAT and claim["binding"] == terminal["binding"]
            and output._hash(claim["expected_parent"], 40), "grade_terminal_claim_mismatch")
    previous = claim["predecessor"]
    if claim["expected_parent"] == retained.BOOTSTRAP:
        require(previous is None, "grade_bootstrap_claim_mismatch")
    else:
        require(type(previous) is dict and set(previous) == {"cell_id", "revision", "size", "sha256"}
                and previous["cell_id"] in context.plan["order"] and previous["cell_id"] != context.cell["cell_id"]
                and previous["revision"] == claim["expected_parent"] and output._hash(previous["sha256"])
                and type(previous["size"]) is int and 0 < previous["size"] <= output.MAX_MANIFEST_BYTES,
                "grade_predecessor_binding_mismatch")
    child = terminal["child"]
    require(set(child) == {"entry_invoked", "exit_code", "timed_out", "cleanup_confirmed"}
            and child["entry_invoked"] is True and child["cleanup_confirmed"] is True
            and type(child["timed_out"]) is bool
            and (child["exit_code"] is None or type(child["exit_code"]) is int), "grade_cleanup_unconfirmed")
    records, roles, total = terminal["files"], [], 0
    require(type(records) is list and len(records) <= 3, "grade_artifact_roles_refused")
    prefix = terminal_path.rsplit("/", 1)[0] + "/"
    from core.task_checkpoint import checkpoint_path
    path = _grade_path(context, entry["config_hash"], entry["grader_source_hash"],
                       terminal["binding"]["retained"]["output_commit"])
    allowed = {"grade_result": prefix + str(path),
               "grade_cost_ledger": prefix + str(path.with_name(path.stem + ".cost_ledger.jsonl")),
               "grade_task_progress": prefix + str(checkpoint_path(path, context.cell["task_id"]))}
    for record in records:
        require(set(record) == {"role", "path", "size", "sha256", "git_blob_sha1"}
                and record["role"] in {"grade_result", "grade_cost_ledger", "grade_task_progress"}
                and type(record["path"]) is str and record["path"] == allowed[record["role"]]
                and type(record["size"]) is int and 0 <= record["size"] <= output.MAX_RECORD_BYTES
                and output._hash(record["sha256"]) and output._hash(record["git_blob_sha1"], 40),
                "grade_artifact_roles_refused")
        roles.append(record["role"])
        total += record["size"]
    require(len(set(roles)) == len(roles) and total <= output.MAX_TOTAL_BYTES, "grade_artifact_roles_refused")
    require(terminal["missing"] == [role for role in ("grade_result", "grade_cost_ledger") if role not in roles],
            "grade_missing_accounting_mismatch")
    require(terminal["outcome"] != "graded" or ("grade_result" in roles and child["exit_code"] == 0
            and not child["timed_out"]), "unobserved_grade_not_success")
    if records:
        retained._objects(api, repo, revision, [{k: v for k, v in row.items() if k != "role"} for row in records],
                          token, deadline, written_at=revision)
    retained._objects(api, repo, revision, [retained._object(claim_path, claim_data)],
                      token, deadline, written_at=terminal["claim_commit"])
    return {"terminal": terminal, "identity": pilot._identity(data), "revision": revision}


def _branch_tip(api, repo: str, context: Context, prepared: dict, cache: Path, token: str, deadline: float) -> tuple[str, dict | None]:
    from huggingface_hub import RepoFile

    head = output._metadata(api, repo, BRANCH, token, deadline)["sha"]
    if head == retained.BOOTSTRAP:
        return head, None
    # Exactly thirty canonical control paths, not an inventory or payload read.
    paths = {_paths(cell)[1]: cell for cell in context.plan["cells"]}
    found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=head,
                               paths=sorted(paths), expand=True, token=token)
    require(type(found) is list and len(found) <= 30, "unknown_grading_branch_tip")
    candidates = [item for item in found if isinstance(item, RepoFile)
                  and item.path in paths and getattr(item.last_commit, "oid", None) == head]
    require(len(candidates) == 1, "unknown_or_unfinished_grading_branch_tip")
    cell = paths[candidates[0].path]
    preliminary = _cache(cache, "tip_binding")
    value, _ = retained._control(api, repo, head, candidates[0].path, preliminary, token, deadline, written_at=head)
    other = compile_request("pilot/" + cell["cell_id"], context.plan["reviewed_source_sha"],
                            value["binding"]["retained"]["terminal_commit"])
    verified = _grade_terminal(api, repo, head, other, prepared["entry"], _cache(cache, "tip_verified"), token, deadline)
    return head, {"cell_id": cell["cell_id"], "revision": head, **verified["identity"]}


def _absent(api, repo: str, revision: str, cell: dict, token: str, deadline: float) -> None:
    output._remaining(deadline)
    prefix = _paths(cell)[0].rsplit("/", 1)[0]
    require(api.get_paths_info(repo_id=repo, repo_type="dataset", revision=revision,
                              paths=[prefix], token=token) == [], "cell_already_claimed_for_grading")


def _commit(api, repo: str, parent: str, files: dict[str, bytes], token: str, deadline: float, observed: dict) -> str:
    """One add-only CAS, ALWAYS the fixed grading branch, NEVER inference main."""
    staged = tuple(_PublicationFile(name, io.BytesIO(data), len(data), hashlib.sha256(data).hexdigest())
                   for name, data in sorted(files.items()))
    try:
        output._remaining(deadline)
        operations = _publication_additions(staged)
        response = api.create_commit(repo_id=repo, repo_type="dataset", revision=BRANCH, token=token,
            parent_commit=parent, operations=operations, commit_message="Retain one private pilot grading boundary",
            num_threads=1, run_as_future=False, create_pr=False)
        revision = getattr(response, "oid", None)
        require(output._hash(revision, 40) and revision != parent, "grade_commit_identity_unavailable")
        observed["returned_commit"] = revision
        require(not any(getattr(operation, "_should_ignore", False) for operation in operations), "grade_commit_ignored")
        require(output._metadata(api, repo, revision, token, deadline)["sha"] == revision,
                "grade_returned_metadata_mismatch")
        retained._objects(api, repo, revision, [retained._object(name, data) for name, data in files.items()],
                          token, deadline, written_at=revision)
        return revision
    finally:
        for item in staged:
            item.stream.close()


def claim(context: Context, root: Path, *, _test_api=None) -> dict:
    github_run = _ci_authority(context.plan["reviewed_source_sha"])
    root = _root(root)
    with _lock(root):
        prepared = _ready(context, root)
        binding = _binding(context, prepared, github_run)
        _record(root / "claim-reserved.json", binding)
        result = _observation(stage="grade_claim")
        try:
            with retained._session(_test_api) as (api, token, deadline):
                repo = retained._target()
                head, previous = _branch_tip(api, repo, context, prepared, _cache(root, "claim-read"), token, deadline)
                _absent(api, repo, head, context.cell, token, deadline)
                value = {"format": CLAIM_FORMAT, "binding": binding, "expected_parent": head, "predecessor": previous}
                name = _paths(context.cell)[0]
                revision = _commit(api, repo, head, {name: retained._encoded(value)}, token, deadline, result)
                confirmed, _ = retained._control(api, repo, revision, name, _cache(root, "claim-verified"), token, deadline,
                                                 expected=pilot._identity(retained._encoded(value)), written_at=revision)
                require(confirmed == value, "grade_claim_verification_failed")
                result.update(outcome="acknowledged", claim=value, claim_identity=pilot._identity(retained._encoded(value)))
        except (Exception, KeyboardInterrupt) as error:
            _failed(result, error)
        _record(root / "claim-receipt.json", result)
        return result


def _admission(context: Context, root: Path, prepared: dict) -> dict:
    value = retained._read(root / "claim-receipt.json")
    require(value["outcome"] == "acknowledged" and output._hash(value["returned_commit"], 40)
            and value["claim"]["binding"] == _binding(context, prepared, _ci_authority(context.plan["reviewed_source_sha"]))
            and value["claim_identity"] == pilot._identity(retained._encoded(value["claim"]))
            and retained._read(root / "claim-reserved.json") == value["claim"]["binding"],
            "acknowledged_grade_admission_required")
    return value


def _judge_environment(root: Path) -> dict:
    # HF cannot consult ambient or cached credentials, and Step8 cannot write
    # private paths/payloads through GitHub's public-output channels.
    removed = {"GITHUB_TOKEN", "GH_TOKEN", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "GITHUB_ENV",
               "ACTIONS_RUNTIME_TOKEN", "ACTIONS_RUNTIME_URL", "ACTIONS_CACHE_URL", "ACTIONS_RESULTS_URL",
               "CODEX_HOME", "HF_TOKEN_PATH"}
    env = {key: value for key, value in os.environ.items() if key not in removed
           and not ("TOKEN" in key.upper() and (key.upper().startswith("HF_") or "HUGGING" in key.upper()))}
    env.update(HF_HUB_OFFLINE="1", HF_DATASETS_OFFLINE="1", HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
               HF_HOME=str(root / "empty-hf-home"), PYTHONDONTWRITEBYTECODE="1")
    return env


def judge(context: Context, root: Path, *, _test_transport=None) -> dict:
    root = _root(root)
    with _lock(root) as descriptor:
        prepared = _ready(context, root)
        admitted = _admission(context, root, prepared)
        # The local reservation is additional to, not a substitute for, CAS.
        _record(root / "judge-reserved.json", {"claim_commit": admitted["returned_commit"],
                                              "claim_identity": admitted["claim_identity"]})
        checkout = root / "source"
        grade_path = checkout / prepared["entry"]["grade_path"]
        from core.task_checkpoint import checkpoint_path
        forbidden = [grade_path, checkpoint_path(grade_path, context.cell["task_id"])]
        forbidden += [grade_path.with_name(grade_path.stem + ".cost_ledger." + suffix) for suffix in ("jsonl", "sqlite3")]
        require(not any(os.path.lexists(path) for path in forbidden), "existing_grade_or_ledger_refused")
        result = {"entry_invoked": False, "exit_code": None, "timed_out": False, "cleanup_confirmed": False}
        owner_binding = {"plan_sha256": hashlib.sha256(context.grading.canonical_bytes()).hexdigest(),
                         "cell_id": context.cell["cell_id"], "stage": "fixed_grading", "attempt": 1}
        transport = _test_transport or pilot.LocalTransport()
        for name in ("judge.stdout", "judge.stderr"):
            output._write_no_clobber(root / name, b"")
        with (root / "judge.stdout").open("ab") as stdout, (root / "judge.stderr").open("ab") as stderr:
            try:
                result["entry_invoked"] = True
                completed = transport.process(list(context.run.command), ownership=(root / "judge-owner.json", owner_binding),
                    cwd=checkout / "batch-runner", env=_judge_environment(root), stdout=stdout, stderr=stderr,
                    timeout=CHILD_SECONDS, check=False, pass_fds=(descriptor,))
                result["exit_code"] = completed.returncode
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
            except (Exception, KeyboardInterrupt):
                pass  # Owned cleanup state below is authoritative; never retry.
        if (root / "judge-owner.json").exists():
            owner = output._checkpoint(root / "judge-owner.json")
            result["cleanup_confirmed"] = all(owner.get(key) == value for key, value in owner_binding.items()) and (
                owner.get("phase") == "reaped" and owner.get("tree_reaped") is True and owner.get("owner_reaped") is True)
        _record(root / "judge-receipt.json", result)
        return result


def _no_raw_grade(value, depth=0) -> None:
    require(depth <= 24, "unsafe_grade_structure")
    if isinstance(value, dict):
        forbidden = output.FORBIDDEN_KEYS - {"prompt"}
        require(not {str(key).lower() for key in value} & forbidden, "unsafe_grade_fields")
        require(value.get("judge_raw_response") is None, "raw_judge_response_refused")
        for item in value.values():
            _no_raw_grade(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _no_raw_grade(item, depth + 1)


def _validate_grade(payload: dict, context: Context, prepared: dict, checkout: Path) -> None:
    import step8_grade as step8

    config = json.loads(context.run.grader_config_json)
    entry = prepared["entry"]
    _no_raw_grade(payload)
    with _cwd(checkout / "batch-runner"):
        try:
            step8._validate_schema(payload)
        except (step8.SchemaError, step8.ValidationError) as error:
            raise output.OutputPublicationRefused("fixed_grade_schema_refused") from error
        step8._validate_grade_resume_identity(payload, experiment_id=context.run.command[2],
            rubric_commit_sha=config["rubric"]["revision"], prompt_version=config["prompt"]["version"],
            config_hash=entry["config_hash"], source_inference_repo_id=retained._target(),
            source_inference_revision=prepared["evidence"]["terminal"]["output_commit"],
            grader_source_hash=entry["grader_source_hash"], renderer_fingerprint=entry["renderer_fingerprint"],
            anchor_projection=config.get("anchor_projection"))
    require(payload["experiment_yaml_name"] == context.run.command[2]
            and payload["source_inference_experiment_id"] == context.cell["run_id"]
            and payload["expected_task_count"] == 1
            and payload["expected_ordered_task_ids_sha256"] == step8._ordered_task_ids_sha256([context.cell["task_id"]])
            and payload["run_status"] in {"partial", "diagnostic"}, "grade_scope_identity_mismatch")
    ids = [row["task_id"] for row in payload["tasks"]]
    require(ids == [context.cell["task_id"]] or (ids == [] and payload["run_status"] == "partial"),
            "grade_task_set_mismatch")
    for task in payload["tasks"]:
        if not task.get("error"):
            require([item["rubric_item_id"] for item in task["items"]] == prepared["rubric"]["rubric_item_ids"],
                    "grade_rubric_coverage_mismatch")
    expected_judge = {key: config["judge"][key] for key in ("provider", "api", "model", "deployment", "api_version")}
    expected_judge.update(reasoning_effort=config["judge"]["reasoning"]["effort"],
        temperature=config["judge"]["generation"]["temperature"], seed=config["judge"]["generation"]["seed"],
        perception=config["judge"]["perception"], config_name=config["config_name"], config_hash=entry["config_hash"])
    require(all(payload["judge"].get(key) == value for key, value in expected_judge.items()),
            "fixed_judge_identity_mismatch")


def _grade_files(context: Context, root: Path, prepared: dict, child: dict) -> tuple[dict[str, bytes], dict[str, str], str]:
    import step8_grade as step8
    from core.task_checkpoint import checkpoint_path, load_checkpoint

    checkout = root / "source"
    path = checkout / prepared["entry"]["grade_path"]
    files, roles = {}, {}
    payload = None
    outcome = "ungraded"
    if os.path.lexists(path):
        data = output._bytes(path, limit=output.MAX_RECORD_BYTES)
        payload = pilot._json_object(data)
        _validate_grade(payload, context, prepared, checkout)
        relative = str(path.relative_to(checkout))
        files[relative], roles[relative] = data, "grade_result"
        runtime_error = any(step8._track2_task_runtime_error(row) is not None or row.get("error") for row in payload["tasks"])
        outcome = ("graded" if child["exit_code"] == 0 and not child["timed_out"] and not runtime_error
                   and payload["run_status"] == "diagnostic" and payload["tasks"] else "partial")
        if runtime_error:
            outcome = "failed"
    ledger_path = path.with_name(path.stem + ".cost_ledger.jsonl")
    if os.path.lexists(ledger_path):
        data = output._bytes(ledger_path, limit=output.MAX_RECORD_BYTES)
        output._ledger(data, context.cell, grading_run_id=prepared["entry"]["cost_run_id"])
        relative = str(ledger_path.relative_to(checkout))
        if payload is not None and payload.get("cost_ledger") is not None:
            from core.cost_receipts import ledger_reference
            require(payload["cost_ledger"] == ledger_reference(relative, hashlib.sha256(data).hexdigest()),
                    "grade_ledger_pointer_mismatch")
        files[relative], roles[relative] = data, "grade_cost_ledger"
    elif payload is not None:
        require(payload.get("cost_ledger") is None, "bound_grade_ledger_missing")
    progress_path = checkpoint_path(path, context.cell["task_id"])
    if os.path.lexists(progress_path):
        data = output._bytes(progress_path, limit=output.MAX_RECORD_BYTES)
        raw = pilot._json_object(data)
        progress = load_checkpoint(path, task_id=context.cell["task_id"],
            grader_source_hash=prepared["entry"]["grader_source_hash"],
            rubric_item_ids=prepared["rubric"]["rubric_item_ids"])
        require(progress is not None and progress.to_dict() == raw, "grade_progress_refused")
        _no_raw_grade(raw)
        relative = str(progress_path.relative_to(checkout))
        files[relative], roles[relative] = data, "grade_task_progress"
        require(outcome != "graded", "completed_grade_has_partial_checkpoint")
        outcome = "partial" if outcome == "ungraded" else outcome
    if child["exit_code"] not in (None, 0) and outcome == "ungraded":
        outcome = "failed"
    require(sum(map(len, files.values())) <= output.MAX_TOTAL_BYTES, "grade_payload_bytes_exceeded")
    return files, roles, outcome


def publish(context: Context, root: Path, *, _test_api=None) -> dict:
    root = _root(root)
    with _lock(root):
        prepared = _ready(context, root)
        admission = _admission(context, root, prepared)
        child = retained._read(root / "judge-receipt.json")
        require(child["cleanup_confirmed"] is True and child["entry_invoked"] is True,
                "grade_cleanup_unconfirmed")
        owner = output._checkpoint(root / "judge-owner.json")
        require(owner["phase"] == "reaped" and owner["tree_reaped"] is True and owner["owner_reaped"] is True,
                "grade_cleanup_unconfirmed")
        files, roles, outcome = _grade_files(context, root, prepared, child)
        _, terminal_path = _paths(context.cell)
        prefix = terminal_path.rsplit("/", 1)[0] + "/"
        terminal = {"format": RESULT_FORMAT, "binding": admission["claim"]["binding"],
            "claim_commit": admission["returned_commit"], "claim_identity": admission["claim_identity"],
            "outcome": outcome, "child": child,
            "files": [{"role": roles[name], **retained._object(prefix + name, data)} for name, data in sorted(files.items())],
            "missing": [role for role in ("grade_result", "grade_cost_ledger") if role not in roles.values()],
            "invoice_complete": False, "http_request_count": None}
        # The manifest binds its payload and prior claim, never its own future
        # commit. The actual returned commit lives only in the private receipt.
        payload = {prefix + name: data for name, data in files.items()}
        payload[terminal_path] = retained._encoded(terminal)
        _record(root / "publication-reserved.json", {"expected_parent": admission["returned_commit"],
            "terminal_identity": pilot._identity(payload[terminal_path])})
        result = _observation(stage="grade_publication")
        try:
            with retained._session(_test_api) as (api, token, deadline):
                repo = retained._target()
                require(output._metadata(api, repo, BRANCH, token, deadline)["sha"] == admission["returned_commit"],
                        "grade_publication_parent_changed")
                require(api.get_paths_info(repo_id=repo, repo_type="dataset", revision=admission["returned_commit"],
                    paths=sorted(payload), token=token) == [], "grade_payload_already_exists")
                revision = _commit(api, repo, admission["returned_commit"], payload, token, deadline, result)
                verified = _grade_terminal(api, repo, revision, context, prepared["entry"],
                                           _cache(root, "publication-verified"), token, deadline)
                require(verified["terminal"] == terminal, "grade_publication_verification_failed")
                result.update(outcome="acknowledged", terminal_identity=verified["identity"], grading_state=outcome)
        except (Exception, KeyboardInterrupt) as error:
            _failed(result, error)
        _record(root / "publication-receipt.json", result)
        return result


def reconcile(context: Context, root: Path, *, _test_api=None) -> dict:
    """Fresh server observation only; never repair a writer receipt or regrade."""
    _ci_authority(context.plan["reviewed_source_sha"])
    root = _root(root)
    with _lock(root):
        prepared = _ready(context, root)
        result = _observation(stage="grade_server_reconciliation")
        try:
            with retained._session(_test_api) as (api, token, deadline):
                repo = retained._target()
                head = output._metadata(api, repo, BRANCH, token, deadline)["sha"]
                # Locate this canonical cell's terminal at the observed branch
                # snapshot, then validate its own immutable writing revision.
                from huggingface_hub import RepoFile
                path = _paths(context.cell)[1]
                found = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=head,
                                           paths=[path], expand=True, token=token)
                require(len(found) == 1 and isinstance(found[0], RepoFile), "grade_terminal_not_established")
                revision = getattr(found[0].last_commit, "oid", None)
                require(output._hash(revision, 40), "grade_terminal_revision_required")
                verified = _grade_terminal(api, repo, revision, context, prepared["entry"],
                                           _cache(root, "reconciliation-read"), token, deadline)
                require(verified["terminal"]["binding"] == _binding(context, prepared,
                    verified["terminal"]["binding"]["github_run"]), "reconciled_grade_binding_mismatch")
                result.update(outcome="verified_server_state", returned_commit=revision,
                              terminal_identity=verified["identity"], writer_acknowledgment="not_established")
        except (Exception, KeyboardInterrupt) as error:
            _failed(result, error)
        _record(root / "grade-server-observation.json", result)
        return result


def _workflow_inputs() -> None:
    """Existing workflow interface, no override of task/repeat/retry controls."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    required = {"GRADE_CONFIG": "default_v2_sol_max.yaml", "GRADE_FORCE": "false", "GRADE_TASKS_LIMIT": "0",
                "GRADE_TASKS": "", "GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0",
                "GRADE_SHARD_COUNT": "1", "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1"}
    require(all(os.environ.get(key) == value for key, value in required.items()), "pilot_grade_override_refused")


def main(argv=None, *, _test_api=None, _test_transport=None) -> int:
    parser = output._Parser(description=__doc__)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--terminal-revision", default="")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--phase", choices=("plan", "inspect", "setup", "prepare", "claim", "judge", "publish", "reconcile"), default="plan")
    args = None
    try:
        args = parser.parse_args(argv)
        _workflow_inputs()
        context = compile_request(args.selector, args.reviewed_source_sha, args.terminal_revision)
        reserved = {"pilot/branch-setup": {"plan", "setup"}, "pilot/branch-inspect": {"plan", "inspect"}}
        require(args.phase in reserved[args.selector] if args.selector in reserved
                else args.phase not in {"setup", "inspect"}, "pilot_grade_mode_conflict")
        if args.phase != "plan":
            with _entry_boundary("source_preflight"):
                source_plan, source_parent, _ = pilot.compile_pilot(ci.CAMPAIGN, args.reviewed_source_sha)
                (_test_transport or pilot.LocalTransport()).require_source(source_plan, source_parent)
        if args.selector == "pilot/branch-inspect":
            observed = _inspection_observation() if args.phase == "plan" else inspect_branch(args.reviewed_source_sha)
            print(pilot._canonical_json(observed))
            return 0 if observed["outcome"] in {"plan_only", "observed"} else 2
        observed = _observation("plan_only", stage="plan")
        ready = False
        if args.phase == "setup":
            observed = setup(args.root, args.reviewed_source_sha, _test_api=_test_api)
        elif args.phase == "prepare":
            prepared = prepare(context, args.root, _test_api=_test_api, _test_transport=_test_transport)
            ready = prepared["judge_ready"]
            observed.update(outcome="prepared" if ready else "ungraded", stage="preparation", reason=prepared.get("reason"))
        elif args.phase == "judge":
            child = judge(context, args.root, _test_transport=_test_transport)
            observed.update(outcome="owned_cleanup_confirmed" if child["cleanup_confirmed"] else "unresolved", stage="judge")
        elif args.phase in {"claim", "publish", "reconcile"}:
            observed = {"claim": claim, "publish": publish, "reconcile": reconcile}[args.phase](context, args.root, _test_api=_test_api)
        public = {"role": "fixed_private_pilot_grading", "repository_name_sha256": retained.TARGET_SHA256,
            "cell_id": None if context is None else context.cell["cell_id"], "judge_ready": ready,
            **{key: observed[key] for key in ("outcome", "stage", "reason", "http_status")},
            "inference_requested": False, "invoice_complete": False, "http_request_count": None,
            "judge_entry_requested": args.phase == "judge", "automatic_retry": False}
        print(pilot._canonical_json(public))
        if args.phase == "prepare" and os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                stream.write("judge_ready=" + str(ready).lower() + "\n")
                if ready:
                    from core.azure_ai_clients import grader_route_workloads
                    stream.write("azure_ai_workloads_json=" + json.dumps([
                        f"{workload.value}={deployment}" for workload, deployment in
                        grader_route_workloads(json.loads(context.run.grader_config_json))
                    ], separators=(",", ":")) + "\n")
        return 0 if observed["outcome"] in {"plan_only", "prepared", "ungraded", "acknowledged",
                "owned_cleanup_confirmed", "verified_server_state"} else 2
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError,
            subprocess.SubprocessError, ImportError, KeyboardInterrupt) as error:
        stage, mutation_possible = None, None
        if isinstance(error, _EntryRefused):
            stage = error.stage
            reason, mutation_possible = _ENTRY_REFUSALS[stage]
            status = None
        else:
            reason, status = output._error_context(error)
            if reason == "hf_operation_failed":
                reason = "grading_contract_refused"
        if args is not None and args.selector == "pilot/branch-inspect":
            observed = _inspection_observation()
            observed["stage"] = stage or "inspection_preflight"
            _inspection_failed(observed, reason)
            print(pilot._canonical_json(observed), file=sys.stderr)
            return 2
        print(pilot._canonical_json({"role": "fixed_private_pilot_grading", "outcome": "refused",
            "stage": stage, "reason": reason, "http_status": status,
            # Current invocation only: false never proves an absent remote
            # branch or an unused reservation from an earlier invocation.
            "remote_mutation_possible": mutation_possible, "inference_requested": False,
            "grade_success": False, "automatic_retry": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
