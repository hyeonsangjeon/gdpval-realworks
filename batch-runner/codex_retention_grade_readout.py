"""Fixed, unpaid readout of the first retention grade's recorded publication.

This authenticates immutable publication bytes and available recorded bindings,
not intermediate-input reconstruction or fresh provider authentication. Nothing
here grants the writer's preparation, admission, judge or publication authority.
"""

from __future__ import annotations

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
require = output._require


def _context(args):
    require(args.selector == SELECTOR and args.phase in {"plan", "readout"}
            and args.terminal_revision == TERMINAL and args.producer_source_sha == "",
            "retention_grade_readout_route_refused")
    require(output._hash(args.reviewed_source_sha, 40)
            and args.reviewed_source_sha not in {WRITER_SOURCE, bridge.RESULT["producer_source_sha"]},
            "distinct_reviewed_observer_required")
    return bridge.compile_request(WRITER_SOURCE)


def _entry(context, recorded):
    import step8_grade as step8

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
    step8.validate_grading_config(json.loads(context.run.grader_config_json))
    config_hash = hashlib.sha256(context.run.grader_config_json.encode()).hexdigest()[:16]
    path = grade._grade_path(context, config_hash, bridge.GRADER_SHA256, bridge.RESULT["output_commit"])
    expected = {"grade_path": str(path), "config_hash": config_hash,
        "grader_source_hash": bridge.GRADER_SHA256, "renderer_fingerprint": renderer,
        "cost_run_id": step8.make_cost_run_id(experiment_yaml_name=bridge.SELECTOR,
            config_hash=config_hash, grader_source_hash=bridge.GRADER_SHA256)}
    bridge._same(recorded, expected, "retention_grade_readout_entry_mismatch")
    return expected


def _terminal_contract(context, terminal):
    """Reconstruct only recorded writer fields; never invent the missing input."""
    bridge._context(context)
    require(context.controller_source_sha == WRITER_SOURCE, "retention_grade_readout_writer_refused")
    require(type(terminal) is dict and set(terminal) == {
        "format", "binding", "claim_commit", "claim_identity", "outcome", "child", "files", "missing",
        "invoice_complete", "http_request_count"}
        and terminal["format"] == bridge.TERMINAL_FORMAT and terminal["outcome"] == "graded"
        and terminal["claim_commit"] == CLAIM and terminal["invoice_complete"] is False
        and terminal["http_request_count"] is None, "retention_grade_readout_terminal_refused")
    binding = terminal["binding"]
    require(type(binding) is dict and output._hash(binding.get("preparation_sha256")),
            "retention_grade_readout_preparation_identity_refused")
    entry = _entry(context, binding.get("entry"))
    expected = {"source_sha": WRITER_SOURCE, "selector": bridge.SELECTOR, "cell_id": bridge.CELL,
        "fixed_evidence_sha256": bridge.fixed_evidence_sha256(), "intake_sha256": bridge.RESULT["intake_sha256"],
        "approval_sha256": pilot._digest(bridge.approval_request(WRITER_SOURCE, WRITER_RUN)),
        "github_run": WRITER_RUN, "entry": entry, "grading_plan_sha256": pilot._digest(context.grading.as_dict()),
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
    allowed = {"grade_result": bridge.PREFIX + "/" + str(path),
        "grade_cost_ledger": bridge.PREFIX + "/" + str(path.with_name(path.stem + ".cost_ledger.jsonl"))}
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
    claim = {"format": bridge.CLAIM_FORMAT, "binding": expected,
             "expected_parent": bridge.PARENT["revision"], "predecessor": bridge.PARENT}
    return entry, claim


class _ReadOnlyGrade:
    """One pinned terminal, its claim and at most two declared grade roles.

    No mutable-head resolution, listings, inference reads or mutation methods.
    The SDK paths-info POST is read-only. Failed reads consume their allowance.
    """

    def __init__(self, api, repo, token):
        self._api, self._repo, self._token = api, repo, token
        self._metadata_open = True
        self._paths = {TERMINAL: {bridge.TERMINAL_PATH}}
        self._downloads = {(TERMINAL, bridge.TERMINAL_PATH): 2}
        self._path_reads = 5

    def _target(self, repo_id, repo_type, token):
        require(repo_id == self._repo and repo_type == "dataset" and token == self._token,
                "grade_readout_target_refused")

    def repo_info(self, *, repo_id, repo_type, revision, token, timeout):
        self._target(repo_id, repo_type, token)
        require(self._metadata_open and revision == TERMINAL, "grade_readout_metadata_refused")
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
        require(output._metadata(self, self._repo, TERMINAL, self._token, deadline)["sha"] == TERMINAL,
                "retention_grade_readout_revision_mismatch")
        terminal, data = retained._control(self, self._repo, TERMINAL, bridge.TERMINAL_PATH,
            grade._cache(root, "terminal"), self._token, deadline,
            expected=TERMINAL_IDENTITY, written_at=TERMINAL)
        entry, claim = _terminal_contract(context, terminal)
        # Only the pinned, semantically checked terminal can open these reads.
        self._paths[TERMINAL].update({bridge.CLAIM_PATH, *(row["path"] for row in terminal["files"])})
        self._paths[CLAIM] = {bridge.CLAIM_PATH}
        self._downloads[(CLAIM, bridge.CLAIM_PATH)] = 1
        admission = {"returned_commit": CLAIM, "claim": claim, "claim_identity": terminal["claim_identity"]}
        identity = bridge._terminal(self, self._repo, TERMINAL, terminal, admission,
            grade._cache(root, "verified"), self._token, deadline)
        bridge._same(identity, pilot._identity(data), "retention_grade_readout_terminal_changed")
        # Payload reads remain closed until claim bytes and inherited history pass.
        for record in terminal["files"]:
            self._downloads[(TERMINAL, record["path"])] = 1
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
        context = _context(args)
        public["stage"] = "observer_authority"
        readout._authority(args.reviewed_source_sha, live=args.phase == "readout")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            require(os.environ.get("GRADE_SELECTOR") == SELECTOR and os.environ.get("GRADE_TERMINAL") == TERMINAL,
                    "retention_grade_readout_route_refused")
        if args.phase == "plan":
            public["stage"] = "plan"
            print(pilot._canonical_json(public))
            return 0
        public["stage"] = "source_preflight"
        with grade._entry_boundary("source_preflight"):
            bridge._source(bridge.compile_request(args.reviewed_source_sha))
        public["stage"] = "read_cache"
        root = grade._root(args.root, new=True)
        with grade._lock(root), retained._session(_test_api, response_bytes_limit=output.MAX_RECORD_BYTES) as (
                raw_api, token, deadline):
            repo = retained._target()
            api = _ReadOnlyGrade(raw_api, repo, token)
            public["stage"] = "grade_terminal"
            terminal, entry, identity = api.verify(context, root, deadline)
            public["stage"] = "grade_payload"
            cache = grade._cache(root, "payload")
            files = {row["role"]: grade._fetch(api, repo, TERMINAL, row["path"], row, cache, token, deadline)
                     for row in terminal["files"]}
            summary = readout._recorded_projection(context, terminal, files, entry,
                inference_revision=bridge.RESULT["output_commit"],
                retention_first_cell_binding=output.RetentionFirstCellLedgerBinding(
                    entry["config_hash"], entry["grader_source_hash"]))
        public.update(outcome="verified_writer_recorded_grade", stage="verified", **summary,
            grade_revision=TERMINAL, terminal_identity=identity, claim_revision=CLAIM,
            claim_identity=terminal["claim_identity"],
            file_identities=[{key: row[key] for key in ("role", "size", "sha256")} for row in terminal["files"]],
            missing=terminal["missing"], proof_boundary=grade.PROOF,
            fixed_evidence_sha256=bridge.fixed_evidence_sha256(), intake_sha256=bridge.RESULT["intake_sha256"],
            original_result_fingerprint=bridge.RESULT["result"]["result_fingerprint"],
            inference_terminal=bridge.RESULT["terminal_commit"], inference_output=bridge.RESULT["output_commit"],
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
        print(pilot._canonical_json(public), file=sys.stderr)
        return 2
