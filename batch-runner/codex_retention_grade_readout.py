"""Fixed, unpaid readouts of the two KEEP grades' recorded publications.

This authenticates immutable publication bytes and available recorded bindings,
not intermediate-input reconstruction or fresh provider authentication. Nothing
here grants the writer's preparation, admission, judge or publication authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import subprocess

import codex_budget_pilot as pilot
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_grading as grade
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_retention_fixed_grade as bridge

SELECTOR = "retention/grade-readout"
WRITER_SOURCE = "29e0353f1539265b1741e71be894fedf9be32a8b"
WRITER_RUN = {"id": "36776393736", "job": "pilot-live", "attempt": 1}
TERMINAL = "40712e0980cc05c31688fdbb98c693774fb90c0d"
TERMINAL_IDENTITY = {
    "sha256": "11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234", "size": 3119}
CLAIM = "dec305d669e3ca2e53c7f7b9ebfbe7974d661350"

KEEP_R2_SELECTOR = "retention/keep-r2-readout"
KEEP_R2_WRITER_SOURCE = "b99a28a4c0ec0ed961a2a8ddcaa886462beb0691"
KEEP_R2_WRITER_RUN = {"id": "36984239149", "job": "pilot-live", "attempt": 1}
KEEP_R2_WRITER_JOB_ID = 110766211046
KEEP_R2_TERMINAL = "76f51d0464b3c90d9ff80b78b656b9e7d45a0b6e"
KEEP_R2_TERMINAL_IDENTITY = {
    "sha256": "d1f2a48d392044937a904243feb5ab0d320d271f1082806ac2aa9e927cb3c66c", "size": 3107}
KEEP_R2_CLAIM = "f8d5189a86c297499c77084aeeb697aea15aad00"
KEEP_R2_ADAPTER_SHA256 = "bb8d1b3a46824a2597f31fe6567531fc59deabb79af87e85d98fd1a08ae3988e"
# Executable dependencies of this model-free observer, not historical grading
# evidence. Both readouts use this one closed current set. The observer itself
# and the remaining source tree are bound by the exact clean reviewed checkout.
# Paid bridge._source still requires each grading adapter's historical READER.
CURRENT_DEPENDENCIES = {
    "codex_retention_fresh_r1_result_intake.py": "631dd2a76faecd28ae65bdbe69d755f598aa4b025cfc66a8280872c2f3a2bc96",
    "codex_retention_result_intake.py": "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196",
    "codex_retention_ci.py": "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c",
    "codex_retention_task4_fresh_r1.py": "75a183f632df17a16f66df4745e01b696f1538b4285f3f11e51fc784c92c15c1",
    "codex_retention_first_cell.py": "c42c8bb3e521c10a5d48680918978a3b9269468a724cd127109f8f4898fe2e6b",
    "codex_retention_task4_fresh_r2.py": "8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f",
    "codex_retention_task4_keep_r2.py": "12106b5423e25ffefa1b04023e2e98742861762762966a04bf17fe3da1851450",
    "codex_retention_keep_r2_grade.py": "bb8d1b3a46824a2597f31fe6567531fc59deabb79af87e85d98fd1a08ae3988e",
    "codex_retention_fixed_grade.py": "3d771582eaaf0d4cfab8e8858db1c7e557473459c2dd5769a837f059f516a684",
    "codex_budget_pilot.py": "ba12e15002b4126fa550c76ba86f61333baf74e1622cc1adcd2b069c2014c398",
    "codex_budget_pilot_grade_readout.py": "96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815",
    "codex_budget_pilot_grading.py": "7ae99e053d11f9a21d6b4db27f390366e70df278a414b0f78db0fe82344bf989",
    "codex_budget_pilot_output.py": "635966f42c0310c9093d59e8f417259a0625b847c52f73342c07ec6c64fa2fdb",
    "codex_budget_pilot_retention.py": "147f3a03b5efeb86e9d0fabe8abbf7c41302816fa136548d512a8f67e97c5bcd",
    "gpt54_disposable_checkout.py": "77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62",
}
require = output._require


@dataclass(frozen=True)
class _ReadBinding:
    selector: str
    grading_selector: str
    writer_source: str
    writer_run: dict
    terminal: str
    terminal_identity: dict
    claim: str


def _fixed(selector=SELECTOR):
    """Two closed routes only; omitted calls retain the historical parent reader."""
    require(type(selector) is str and selector in {SELECTOR, KEEP_R2_SELECTOR},
            "retention_grade_readout_route_refused")
    if selector == SELECTOR:
        return _ReadBinding(SELECTOR, bridge.SELECTOR, WRITER_SOURCE, WRITER_RUN,
                            TERMINAL, TERMINAL_IDENTITY, CLAIM)
    # Check the unchanged evidence adapter before bridge._fixed lazily imports
    # it, and before this readout can acquire a private cache or credential.
    from pathlib import Path

    data = output._bytes(Path(__file__).with_name("codex_retention_keep_r2_grade.py"),
                         limit=output.MAX_RECORD_BYTES)
    require(pilot._identity(data)["sha256"] == KEEP_R2_ADAPTER_SHA256,
            "reviewed_retention_grade_adapter_required")
    return _ReadBinding(KEEP_R2_SELECTOR, "retention/keep-r2", KEEP_R2_WRITER_SOURCE, KEEP_R2_WRITER_RUN,
                        KEEP_R2_TERMINAL, KEEP_R2_TERMINAL_IDENTITY, KEEP_R2_CLAIM)


def _source_current(source_sha, *, selector=SELECTOR):
    """Current executable closure before private effects; never repin a receipt."""
    profile = _fixed(selector)  # Keeps the exact keep/r2 adapter pre-import check.
    context = bridge.compile_request(source_sha, selector=profile.grading_selector)
    bridge._source_checkout(context)
    for name, digest in CURRENT_DEPENDENCIES.items():
        data = output._bytes(bridge.ROOT / "batch-runner" / name, limit=output.MAX_RECORD_BYTES)
        require(pilot._identity(data)["sha256"] == digest, "reviewed_retention_observer_dependency_required")


# Diagnostics identify attempted work, not successful terminal verification.
_TERMINAL_SUBSTAGES = ("metadata", "terminal_control", "terminal_binding", "claim_history", "terminal_identity")
_TERMINAL_REFUSALS = (
    "existing_exact_private_repository_required", "repository_revision_unavailable",
    "retention_grade_readout_revision_mismatch", "immutable_retention_revision_required",
    "retention_control_identity_refused", "terminal_or_claim_missing", "retention_control_file_refused",
    "retention_control_history_mismatch", "retention_control_cache_escape", "retention_control_blob_mismatch",
    "payload_file_or_size_refused", "payload_file_changed", "payload_identity_mismatch",
    "noncanonical_retention_record", "retention_record_too_large",
    "canonical_retention_grade_context_required", "retention_grade_context_changed",
    "retention_grade_readout_writer_refused", "retention_grade_readout_terminal_refused",
    "retention_grade_readout_preparation_identity_refused", "retention_grade_readout_entry_refused",
    "grade_readout_renderer_identity_refused", "retention_grade_readout_entry_mismatch",
    "retention_grade_readout_writer_binding_mismatch", "grade_cleanup_unconfirmed",
    "grade_artifact_roles_refused", "grade_missing_accounting_mismatch",
    "retention_grade_terminal_changed", "retention_grade_terminal_claim_changed",
    "retention_grade_terminal_cleanup_required", "output_objects_refused", "remote_output_objects_missing",
    "remote_output_size_mismatch", "remote_output_blob_mismatch", "remote_output_lfs_mismatch",
    "remote_output_history_mismatch", "retention_grade_readout_terminal_changed",
    "grade_readout_target_refused", "grade_readout_metadata_refused", "grade_readout_paths_refused",
    "grade_readout_download_refused", "publication_timeout", "hf_http_failed", "hf_transport_failed", "hf_response_bytes_exceeded",
    "hf_insecure_request_refused", "hf_credential_forwarding_refused",
)


def _terminal_diagnostic(error, substage):
    """Project enumerated constants only; do not stringify errors or follow causes."""
    reason = "unclassified_verification_error"
    if type(error) is output.OutputPublicationRefused and len(error.args) == 1 and type(error.args[0]) is str:
        reason = next((code for code in _TERMINAL_REFUSALS if error.args[0] == code), reason)
    stage = next((value for value in _TERMINAL_SUBSTAGES if type(substage) is str and substage == value),
                 "unclassified_verification_substage")
    return {"verification_substage": stage, "verification_reason": reason}


def _context(args):
    profile = _fixed(args.selector)
    fixed = bridge._fixed(profile.grading_selector)
    require(args.phase in {"plan", "readout"}
            and args.terminal_revision == profile.terminal and args.producer_source_sha == "",
            "retention_grade_readout_route_refused")
    require(output._hash(args.reviewed_source_sha, 40)
            and args.reviewed_source_sha not in {profile.writer_source, fixed.RESULT["producer_source_sha"]},
            "distinct_reviewed_observer_required")
    return bridge.compile_request(profile.writer_source, selector=profile.grading_selector)


def _entry(context, recorded, *, selector=SELECTOR):
    import step8_grade as step8

    profile = _fixed(selector)
    fixed = bridge._fixed(profile.grading_selector)
    require(context.selector == profile.grading_selector, "retention_grade_readout_writer_refused")
    require(type(recorded) is dict and set(recorded) == {
        "grade_path", "config_hash", "grader_source_hash", "renderer_fingerprint", "cost_run_id"},
        "retention_grade_readout_entry_refused")
    renderer = recorded["renderer_fingerprint"]
    require(type(renderer) is dict and set(renderer) == {
        "libreoffice_binary", "libreoffice_version", "pymupdf_version"}
        and all(type(value) is str and 0 < len(value) <= 1024 for value in renderer.values()),
        "grade_readout_renderer_identity_refused")
    # The writer checked the actual materialized closure. Its fixed hash is an
    # expectation here; this reader never re-renders or materializes inputs.
    with grade._cwd(pilot.ROOT / "batch-runner"):
        step8.validate_grading_config(json.loads(context.run.grader_config_json))
    config_hash = hashlib.sha256(context.run.grader_config_json.encode()).hexdigest()[:16]
    path = grade._grade_path(context, config_hash, fixed.GRADER_SHA256, fixed.RESULT["output_commit"])
    expected = {"grade_path": str(path), "config_hash": config_hash,
        "grader_source_hash": fixed.GRADER_SHA256, "renderer_fingerprint": renderer,
        "cost_run_id": step8.make_cost_run_id(experiment_yaml_name=fixed.SELECTOR,
            config_hash=config_hash, grader_source_hash=fixed.GRADER_SHA256)}
    bridge._same(recorded, expected, "retention_grade_readout_entry_mismatch")
    return expected


def _terminal_contract(context, terminal, *, selector=SELECTOR):
    """Reconstruct only recorded writer fields; never invent the missing input."""
    bridge._context(context)
    profile = _fixed(selector)
    fixed = bridge._fixed(profile.grading_selector)
    require(context.controller_source_sha == profile.writer_source and context.selector == profile.grading_selector,
            "retention_grade_readout_writer_refused")
    require(type(terminal) is dict and set(terminal) == {
        "format", "binding", "claim_commit", "claim_identity", "outcome", "child", "files", "missing",
        "invoice_complete", "http_request_count"}
        and terminal["format"] == fixed.TERMINAL_FORMAT and terminal["outcome"] == "graded"
        and terminal["claim_commit"] == profile.claim and terminal["invoice_complete"] is False
        and terminal["http_request_count"] is None, "retention_grade_readout_terminal_refused")
    binding = terminal["binding"]
    require(type(binding) is dict and output._hash(binding.get("preparation_sha256")),
            "retention_grade_readout_preparation_identity_refused")
    entry = _entry(context, binding.get("entry"), selector=selector)
    expected = {"source_sha": profile.writer_source, "selector": fixed.SELECTOR, "cell_id": fixed.CELL,
        "fixed_evidence_sha256": bridge.fixed_evidence_sha256(fixed.SELECTOR), "intake_sha256": fixed.RESULT["intake_sha256"],
        "approval_sha256": pilot._digest(bridge.approval_request(profile.writer_source, profile.writer_run,
                                                              selector=fixed.SELECTOR)),
        "github_run": profile.writer_run, "entry": entry, "grading_plan_sha256": pilot._digest(context.grading.as_dict()),
        "preparation_sha256": binding["preparation_sha256"], "proof_boundary": grade.PROOF}
    bridge._same(binding, expected, "retention_grade_readout_writer_binding_mismatch")
    identity = terminal["claim_identity"]
    require(type(identity) is dict and set(identity) == {"sha256", "size"}
            and output._hash(identity["sha256"]) and type(identity["size"]) is int
            and 0 < identity["size"] <= output.MAX_MANIFEST_BYTES,
            "retention_control_identity_refused")
    bridge._same(terminal["child"], {"entry_invoked": True, "exit_code": 0,
        "timed_out": False, "cleanup_confirmed": True}, "grade_cleanup_unconfirmed")
    from pathlib import Path

    path = Path(entry["grade_path"])
    allowed = {"grade_result": fixed.PREFIX + "/" + str(path),
        "grade_cost_ledger": fixed.PREFIX + "/" + str(path.with_name(path.stem + ".cost_ledger.jsonl"))}
    records = terminal["files"]
    require(type(records) is list and 1 <= len(records) <= 2, "grade_artifact_roles_refused")
    roles, names, total = [], [], 0
    for record in records:
        require(type(record) is dict and set(record) == {"role", "path", "size", "sha256", "git_blob_sha1"}
                and type(record["role"]) is str and record["role"] in allowed
                and record["path"] == allowed[record["role"]]
                and type(record["size"]) is int and 0 <= record["size"] <= output.MAX_RECORD_BYTES
                and output._hash(record["sha256"]) and output._hash(record["git_blob_sha1"], 40),
                "grade_artifact_roles_refused")
        roles.append(record["role"])
        names.append(record["path"])
        total += record["size"]
    require("grade_result" in roles and len(set(roles)) == len(roles)
            and names == sorted(set(names)) and total <= output.MAX_TOTAL_BYTES, "grade_artifact_roles_refused")
    require(terminal["missing"] == [role for role in ("grade_result", "grade_cost_ledger") if role not in roles],
            "grade_missing_accounting_mismatch")
    claim = {"format": fixed.CLAIM_FORMAT, "binding": expected,
             "expected_parent": fixed.PARENT["revision"], "predecessor": fixed.PARENT}
    return entry, claim


class _ReadOnlyGrade:
    """One pinned terminal, its claim and at most two declared grade roles.

    No mutable-head resolution, listings, inference reads or mutation methods.
    The SDK paths-info POST is read-only. Failed reads consume their allowance.
    """

    def __init__(self, api, repo, token, *, selector=SELECTOR):
        self._api, self._repo, self._token = api, repo, token
        self._profile = profile = _fixed(selector)
        self._fixed = fixed = bridge._fixed(profile.grading_selector)
        self._metadata_open = True
        self._paths = {profile.terminal: {fixed.TERMINAL_PATH}}
        self._downloads = {(profile.terminal, fixed.TERMINAL_PATH): 2}
        self._path_reads = 5
        self._verification_substage = None

    def _target(self, repo_id, repo_type, token):
        require(repo_id == self._repo and repo_type == "dataset" and token == self._token,
                "grade_readout_target_refused")

    def repo_info(self, *, repo_id, repo_type, revision, token, timeout):
        self._target(repo_id, repo_type, token)
        require(self._metadata_open and revision == self._profile.terminal, "grade_readout_metadata_refused")
        self._metadata_open = False
        return self._api.repo_info(repo_id=repo_id, repo_type=repo_type, revision=revision,
                                   token=token, timeout=timeout)

    def get_paths_info(self, *, repo_id, repo_type, revision, paths, expand, token):
        self._target(repo_id, repo_type, token)
        require(not self._metadata_open and self._path_reads > 0 and expand is True
                and type(paths) is list and 0 < len(paths) <= 2 and len(set(paths)) == len(paths)
                and set(paths) <= self._paths.get(revision, set()), "grade_readout_paths_refused")
        self._path_reads -= 1
        return self._api.get_paths_info(repo_id=repo_id, repo_type=repo_type, revision=revision,
                                       paths=paths, expand=True, token=token)

    def hf_hub_download(self, *, repo_id, repo_type, revision, filename, token, cache_dir,
                        force_download, local_files_only, etag_timeout):
        self._target(repo_id, repo_type, token)
        key = (revision, filename)
        require(not self._metadata_open and self._downloads.get(key, 0) > 0
                and force_download is True and local_files_only is False, "grade_readout_download_refused")
        self._downloads[key] -= 1
        return self._api.hf_hub_download(repo_id=repo_id, repo_type=repo_type, revision=revision,
            filename=filename, token=token, cache_dir=cache_dir, force_download=True,
            local_files_only=False, etag_timeout=etag_timeout)

    def verify(self, context, root, deadline):
        profile, fixed = self._profile, self._fixed
        self._verification_substage = "metadata"
        require(output._metadata(self, self._repo, profile.terminal, self._token, deadline)["sha"] == profile.terminal,
                "retention_grade_readout_revision_mismatch")
        self._verification_substage = "terminal_control"
        terminal, data = retained._control(self, self._repo, profile.terminal, fixed.TERMINAL_PATH,
            grade._cache(root, "terminal"), self._token, deadline,
            expected=profile.terminal_identity, written_at=profile.terminal)
        self._verification_substage = "terminal_binding"
        entry, claim = _terminal_contract(context, terminal, selector=profile.selector)
        # Only the pinned, semantically checked terminal can open these reads.
        self._paths[profile.terminal].update({fixed.CLAIM_PATH, *(row["path"] for row in terminal["files"])})
        self._paths[profile.claim] = {fixed.CLAIM_PATH}
        self._downloads[(profile.claim, fixed.CLAIM_PATH)] = 1
        admission = {"returned_commit": profile.claim, "claim": claim, "claim_identity": terminal["claim_identity"]}
        # Includes the existing terminal reread, claim bytes and object history.
        self._verification_substage = "claim_history"
        identity = bridge._terminal(self, self._repo, profile.terminal, terminal, admission,
            grade._cache(root, "verified"), self._token, deadline, selector=fixed.SELECTOR)
        self._verification_substage = "terminal_identity"
        bridge._same(identity, pilot._identity(data), "retention_grade_readout_terminal_changed")
        # Payload reads remain closed until claim bytes and inherited history pass.
        for record in terminal["files"]:
            self._downloads[(profile.terminal, record["path"])] = 1
        return terminal, entry, identity


def main(args, *, _test_api=None):
    public = {"role": "fixed_private_retention_grade_readout", "record_kind": "writer_recorded_grade",
        "outcome": "plan_only", "stage": "plan", "reason": None, "http_status": None,
        "repository_name_sha256": retained.TARGET_SHA256, "branch": grade.BRANCH,
        "selector": SELECTOR, "cell_id": bridge.CELL, "grade_writer_source_sha": WRITER_SOURCE,
        "grade_writer_run": WRITER_RUN, "inference_producer_source_sha": bridge.RESULT["producer_source_sha"],
        "observer_source_sha": args.reviewed_source_sha if output._hash(args.reviewed_source_sha, 40) else None,
        "remote_mutation_possible": False, "inference_requested": False, "judge_entry_requested": False,
        "automatic_retry": False, "invoice_complete": False, "http_request_count": None,
        "mutable_branch_head_observed": False,
        "materialized_input_fingerprint": {"status": "unavailable", "value": None, "comparison": None,
            "reason": "materialized_input_fingerprint_not_recorded"}}
    try:
        profile = _fixed(args.selector)
        fixed = bridge._fixed(profile.grading_selector)
        public.update(selector=profile.selector, cell_id=fixed.CELL, grade_writer_source_sha=profile.writer_source,
            grade_writer_run=profile.writer_run, inference_producer_source_sha=fixed.RESULT["producer_source_sha"])
        if profile.selector == KEEP_R2_SELECTOR:
            # The terminal records the logical job name, not the provider's
            # numeric job ID. Preserve that independently supplied limit.
            public.update(supplied_grade_writer_job_id=KEEP_R2_WRITER_JOB_ID,
                          provider_job_identity_independently_verified=False)
        context = _context(args)
        public["stage"] = "observer_authority"
        readout._authority(args.reviewed_source_sha, live=args.phase == "readout")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            require(os.environ.get("GRADE_SELECTOR") == profile.selector and os.environ.get("GRADE_TERMINAL") == profile.terminal,
                    "retention_grade_readout_route_refused")
        if args.phase == "plan":
            public["stage"] = "plan"
            print(pilot._canonical_json(public))
            return 0
        public["stage"] = "source_preflight"
        with grade._entry_boundary("source_preflight"):
            _source_current(args.reviewed_source_sha, selector=profile.selector)
        public["stage"] = "read_cache"
        root = grade._root(args.root, new=True)
        with grade._lock(root), retained._session(_test_api, response_bytes_limit=output.MAX_RECORD_BYTES) as (
                raw_api, token, deadline):
            repo = retained._target()
            api = _ReadOnlyGrade(raw_api, repo, token, selector=profile.selector)
            public["stage"] = "grade_terminal"
            terminal, entry, identity = api.verify(context, root, deadline)
            public["stage"] = "grade_payload"
            cache = grade._cache(root, "payload")
            files = {row["role"]: grade._fetch(api, repo, profile.terminal, row["path"], row, cache, token, deadline)
                     for row in terminal["files"]}
            ledger_type = (output.RetentionFirstCellLedgerBinding if profile.selector == SELECTOR
                           else output.RetentionKeepR2LedgerBinding)
            summary = readout._recorded_projection(context, terminal, files, entry,
                inference_revision=fixed.RESULT["output_commit"],
                retention_first_cell_binding=ledger_type(
                    entry["config_hash"], entry["grader_source_hash"]))
        public.update(outcome="verified_writer_recorded_grade", stage="verified", **summary,
            grade_revision=profile.terminal, terminal_identity=identity, claim_revision=profile.claim,
            claim_identity=terminal["claim_identity"],
            file_identities=[{key: row[key] for key in ("role", "size", "sha256")} for row in terminal["files"]],
            missing=terminal["missing"], proof_boundary=grade.PROOF,
            fixed_evidence_sha256=bridge.fixed_evidence_sha256(fixed.SELECTOR), intake_sha256=fixed.RESULT["intake_sha256"],
            original_result_fingerprint=fixed.RESULT["result"]["result_fingerprint"],
            inference_terminal=fixed.RESULT["terminal_commit"], inference_output=fixed.RESULT["output_commit"],
            writer_preparation_sha256=terminal["binding"]["preparation_sha256"],
            config_sha256=hashlib.sha256(context.run.grader_config_json.encode()).hexdigest(),
            config_hash=entry["config_hash"], grader_source_hash=entry["grader_source_hash"],
            rubric_revision=json.loads(context.run.grader_config_json)["rubric"]["revision"],
            renderer_fingerprint_sha256=pilot._digest(entry["renderer_fingerprint"]))
        print(pilot._canonical_json(public))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError,
            subprocess.SubprocessError, ImportError, KeyboardInterrupt) as error:
        import sys

        _, status = output._error_context(error)
        public.update(outcome="refused", reason="retention_grade_readout_contract_refused",
                      http_status=status if type(status) is int and 100 <= status <= 599 else None)
        if public["stage"] == "grade_terminal":
            public.update(_terminal_diagnostic(error, api._verification_substage))
        print(pilot._canonical_json(public), file=sys.stderr)
        return 2
