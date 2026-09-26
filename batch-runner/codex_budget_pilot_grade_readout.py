"""Closed task2 grade readout, not admission, publication or regrading."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as grading
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained

SELECTOR = "pilot/grade-readout"
WRITER_SOURCE = "6ed0139195c4ebf27bfb63d14b2c8d8c92f8f379"
WRITER_RUN = {"id": "36161541597", "job": "pilot-live", "attempt": 1}
# Derived offline at WRITER_SOURCE with the genuine compiler and
# step8.compute_grader_source_hash, including batch-runner/comparison-grading.json.
# Never use a remote terminal's self-reported hash as the expected source hash.
CONFIG_SHA256 = "62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0"
GRADER_SOURCE_HASH = "0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df"
# The ecbe writer's actual grader closure and compiled config are unchanged
# from the independently derived A1 closure above, not read from HF metadata.
B1_WRITER_SOURCE = "ecbe297e7dc2d798a834091f14da3ae486172a43"
B1_WRITER_RUN = {"id": "36202409134", "job": "pilot-live", "attempt": 1}
B1_GRADER_SOURCE_HASH = "0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df"
# The A5 compiler/config and grader closure retain the independently derived
# hashes above. Neither the observer's source nor remote claims supply them.
TASK2_WRITER_SOURCE = "a5e5d2589caff21309f0a1c21bb7d9d333ad47c6"
TASK2_GRADER_SOURCE_HASH = "0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df"
TASK2_GRADE_RUNS = {
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_C_r1": "36209654516",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_C_r2": "36211281528",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_B_r2": "36212846089",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r2": "36214413190",
}
# These additional observed pins apply only to C1's predecessor proof. The
# already-delivered B1 reader and production grading helpers keep their route.
B1_PREDECESSOR_GRADE = "887c2373d456efc1eabf29a8bf3d3d7de12e43fe"
B1_PREDECESSOR_INFERENCE = "0a9a8b3263f41d86d723f84a723c9b467f04dea5"
require = output._require


def _task2_cell(request):
    return next((cell for cell in TASK2_GRADE_RUNS if grading.TASK2_RETAINED[cell][1] == request), None)


def _task2_run(cell):
    run = TASK2_GRADE_RUNS[cell]
    return None if run is None else {"id": run, "job": "pilot-live", "attempt": 1}


def _writer_context(request):
    require(ci.CAMPAIGN == "budget_pilot_ci_20260925_04"
            and grading.BRANCH == "pilot-grades-20260925-04"
            and retained.BRANCH == "pilot-inference-20260925-04", "grade_readout_epoch_refused")
    if request == grading.RETAINED_TERMINAL:
        context = grading.compile_request("pilot/" + grading.RETAINED_CELL, WRITER_SOURCE,
            request, producer_source_sha=grading.RETAINED_PRODUCER_SOURCE)
    elif request == grading.TASK2_RETAINED[grading.B1_CELL][1]:
        context = grading.compile_request("pilot/" + grading.B1_CELL, B1_WRITER_SOURCE,
            request, producer_source_sha=grading.B1_PRODUCER_SOURCE)
    else:
        cell = _task2_cell(request)
        require(cell is not None, "grade_readout_route_refused")
        require(_task2_run(cell) is not None, "grade_readout_writer_unconfigured")
        context = grading.compile_request("pilot/" + cell, TASK2_WRITER_SOURCE,
            request, producer_source_sha=grading.B1_PRODUCER_SOURCE)
    require(hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == CONFIG_SHA256,
            "grade_readout_config_refused")
    return context


def _writer_run(context):
    if context.cell["cell_id"] in TASK2_GRADE_RUNS:
        return _task2_run(context.cell["cell_id"])
    return B1_WRITER_RUN if context.cell["cell_id"] == grading.B1_CELL else WRITER_RUN


def _writer_entry(context, renderer):
    require(type(renderer) is dict and set(renderer) == {
        "libreoffice_binary", "libreoffice_version", "pymupdf_version"}
        and all(type(value) is str and 0 < len(value) <= 1024 for value in renderer.values()),
        "grade_readout_renderer_identity_refused")
    source_hash = (TASK2_GRADER_SOURCE_HASH if context.cell["cell_id"] in TASK2_GRADE_RUNS else
                   B1_GRADER_SOURCE_HASH if context.cell["cell_id"] == grading.B1_CELL else GRADER_SOURCE_HASH)
    return {"config_hash": CONFIG_SHA256[:16], "renderer_fingerprint": renderer, "grader_source_hash": source_hash}


def _context(args):
    require(args.phase in {"plan", "readout"} and args.producer_source_sha == "", "grade_readout_route_refused")
    context = _writer_context(args.terminal_revision)
    require(output._hash(args.reviewed_source_sha, 40)
            and args.reviewed_source_sha not in {context.controller_source_sha, context.plan["reviewed_source_sha"]},
            "distinct_reviewed_observer_required")
    return context


def _authority(source: str, *, live: bool):
    grading._workflow_inputs()
    if not live and os.environ.get("GITHUB_ACTIONS") != "true":
        return  # Local plan: no token lookup, source checkout or network.
    expected = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + grading.WORKFLOW + "@refs/heads/main",
        "GITHUB_JOB": "pilot-readout", "PILOT_GRADE_PAID_APPROVAL": "false"}
    require(all(os.environ.get(key) == value for key, value in expected.items())
            and os.environ.get("PILOT_GRADE_DRY_RUN") in ({"false"} if live else {"true", "false"})
            and re.fullmatch(r"[1-9][0-9]{0,19}", os.environ.get("GITHUB_RUN_ID", "")) is not None,
            "grade_readout_observer_authority_refused")


class _ReadOnlyGrade:
    """Only exact-target metadata and staged immutable file reads are exposed.

    paths-info uses the SDK's read-only POST. There is no generic forwarding,
    listing, branch/claim creation, commit, upload, delete or retry surface.
    """

    def __init__(self, api, repo, token, context):
        self._api, self._repo, self._token = api, repo, token
        self._claim, self._terminal = grading._paths(context.cell)
        self._metadata_open = True
        self._metadata_paths, self._downloads = {}, set()
        self._inference_metadata, self._inference_revisions = set(), set()
        self.revision = None

    def _target(self, repo_id, repo_type, token):
        require(repo_id == self._repo and repo_type == "dataset" and token == self._token,
                "grade_readout_target_refused")

    def repo_info(self, *, repo_id, repo_type, revision, token, timeout):
        self._target(repo_id, repo_type, token)
        if revision in self._inference_metadata:
            self._inference_metadata.remove(revision)
        else:
            require(self._metadata_open and revision == grading.BRANCH, "grade_readout_metadata_refused")
            self._metadata_open = False
        return self._api.repo_info(repo_id=repo_id, repo_type=repo_type, revision=revision, token=token, timeout=timeout)

    def get_paths_info(self, *, repo_id, repo_type, revision, paths, expand, token):
        self._target(repo_id, repo_type, token)
        limit = output.MAX_FILES + 3 if revision in self._inference_revisions else 3
        require(expand is True and type(paths) is list and 0 < len(paths) <= limit
                and len(paths) == len(set(paths))
                and set(paths) <= self._metadata_paths.get(revision, set()), "grade_readout_paths_refused")
        return self._api.get_paths_info(repo_id=repo_id, repo_type=repo_type, revision=revision,
                                       paths=paths, expand=True, token=token)

    def hf_hub_download(self, *, repo_id, repo_type, revision, filename, token, cache_dir,
                        force_download, local_files_only, etag_timeout):
        self._target(repo_id, repo_type, token)
        require((revision, filename) in self._downloads and force_download is True and local_files_only is False,
                "grade_readout_download_refused")
        return self._api.hf_hub_download(repo_id=repo_id, repo_type=repo_type, revision=revision,
            filename=filename, token=token, cache_dir=cache_dir, force_download=True,
            local_files_only=False, etag_timeout=etag_timeout)

    def locate(self, deadline):
        from huggingface_hub import RepoFile

        head = output._metadata(self, self._repo, grading.BRANCH, self._token, deadline)["sha"]
        self._metadata_paths[head] = {self._terminal}
        found = self.get_paths_info(repo_id=self._repo, repo_type="dataset", revision=head,
            paths=[self._terminal], expand=True, token=self._token)
        require(type(found) is list and len(found) == 1 and isinstance(found[0], RepoFile)
                and found[0].path == self._terminal, "grade_terminal_not_established")
        revision = getattr(found[0].last_commit, "oid", None)
        require(output._hash(revision, 40), "grade_terminal_revision_required")
        self.revision = revision
        self._metadata_paths[revision] = {self._terminal}
        self._downloads.add((revision, self._terminal))
        return head

    def bind(self, terminal, context, entry):
        grading._validate_binding(terminal["binding"], context, entry)
        require(terminal["binding"]["github_run"] == _writer_run(context), "grade_readout_writer_run_refused")
        revision = terminal["claim_commit"]
        require(output._hash(revision, 40) and revision != self.revision, "grade_readout_claim_refused")
        self._metadata_paths[revision] = {self._claim}
        self._downloads.add((revision, self._claim))
        self._metadata_paths[self.revision].update({self._claim, *grading._grade_artifact_paths(
            context, entry, terminal["binding"]["retained"]["output_commit"]).values()})

    def bind_retained(self, binding, context, cache, deadline):
        """Only the registered cell's inference controls, never payloads."""
        require(context.cell["cell_id"] in grading.TASK2_RETAINED and context.terminal_request is not None,
                "grade_readout_retained_route_refused")
        revision = binding["retained"]["terminal_commit"]
        require(output._hash(revision, 40) and revision != self.revision, "grade_readout_retained_revision_refused")
        claim, terminal_path, prefix = retained._paths(context.cell)
        self._metadata_paths[revision] = {terminal_path}
        self._downloads.add((revision, terminal_path))
        terminal, _ = retained._control(self, self._repo, revision, terminal_path,
            grading._cache(cache, "candidate"), self._token, deadline, written_at=revision)
        claim_revision, output_revision = terminal["claim_commit"], terminal["output_commit"]
        require(all(output._hash(value, 40) for value in (claim_revision, output_revision))
                and len({revision, claim_revision, output_revision, self.revision}) == 4,
                "grade_readout_retained_revision_refused")
        objects = terminal["output_objects"]
        require(type(objects) is list and 0 < len(objects) <= output.MAX_FILES + 3,
                "grade_readout_retained_paths_refused")
        paths = {record["path"] for record in objects}
        require(len(paths) == len(objects) and all(type(path) is str and path.startswith(prefix + "/")
                and ".." not in path.split("/") and "\\" not in path for path in paths),
                "grade_readout_retained_paths_refused")
        manifest = prefix + "/" + output.MANIFEST
        require(manifest in paths, "grade_readout_retained_paths_refused")
        self._inference_revisions.update({revision, claim_revision, output_revision})
        self._inference_metadata.add(revision)
        self._metadata_paths[revision].update({claim, *paths})
        self._metadata_paths[claim_revision] = {claim}
        self._metadata_paths[output_revision] = paths
        self._downloads.update({(claim_revision, claim), (output_revision, manifest)})
        grading._grade_retained_input(context, binding, self, self._repo,
            grading._cache(cache, "verified"), self._token, deadline)
        if context.cell["cell_id"] in TASK2_GRADE_RUNS:
            original, _ = retained._control(self, self._repo, claim_revision, claim,
                grading._cache(cache, "predecessor"), self._token, deadline,
                expected=terminal["claim_identity"], written_at=claim_revision)
            return original["predecessor"]

    def allow_verified_files(self, records):
        # Called only after _grade_terminal checked the role/path/hash/history.
        self._downloads.update((self.revision, record["path"]) for record in records)


def _verified_grade(api, context, cache, deadline):
    terminal, _ = retained._control(api, api._repo, api.revision, grading._paths(context.cell)[1],
        grading._cache(cache, "terminal"), api._token, deadline, written_at=api.revision)
    entry = _writer_entry(context, terminal["binding"]["renderer_fingerprint"])
    previous = None
    if context.terminal_request is not None:
        previous = api.bind_retained(terminal["binding"], context, grading._cache(cache, "inference-proof"), deadline)
    api.bind(terminal, context, entry)
    verified = grading._grade_terminal(api, api._repo, api.revision, context, entry,
        grading._cache(cache, "verified"), api._token, deadline)
    require(verified["terminal"] == terminal, "grade_readout_terminal_changed")
    return verified, entry, previous


def _verify_predecessor(api, context, verified, inference_previous, cache, deadline):
    """Verify one logical predecessor, not recursive history or Git topology."""
    terminal = verified["terminal"]
    claim, _ = retained._control(api, api._repo, terminal["claim_commit"], grading._paths(context.cell)[0],
        grading._cache(cache, "claim"), api._token, deadline,
        expected=terminal["claim_identity"], written_at=terminal["claim_commit"])
    ordinal = context.plan["order"].index(context.cell["cell_id"])
    cell = context.plan["order"][ordinal - 1]
    other = _writer_context(grading.TASK2_RETAINED[cell][1])
    revision = claim["expected_parent"]
    require(len({revision, api.revision, terminal["claim_commit"]}) == 3,
            "grade_readout_predecessor_revision_refused")
    if cell == grading.B1_CELL:
        require(revision == B1_PREDECESSOR_GRADE, "grade_readout_original_b1_required")
    prior = _ReadOnlyGrade(api._api, api._repo, api._token, other)
    prior._metadata_open = False  # No second branch snapshot or moving-tip lookup.
    prior.revision = revision
    path = grading._paths(other.cell)[1]
    prior._metadata_paths[revision] = {path}
    prior._downloads.add((revision, path))
    previous, _, _ = _verified_grade(prior, other, grading._cache(cache, "previous"), deadline)
    require(claim["predecessor"] == {"cell_id": cell, "revision": revision, **previous["identity"]},
            "grade_readout_predecessor_identity_refused")
    observed = previous["terminal"]["binding"]["retained"]
    require(inference_previous == observed, "grade_readout_inference_predecessor_refused")
    if cell == grading.B1_CELL:
        require(observed["terminal_commit"] == B1_PREDECESSOR_INFERENCE, "grade_readout_original_b1_required")
    api._metadata_paths[terminal["claim_commit"]].add(path)
    retained._objects(api, api._repo, terminal["claim_commit"],
        [retained._object(path, retained._encoded(previous["terminal"]))], api._token, deadline, written_at=revision)
    # Predecessor grade files have metadata proofs only. Never open their downloads.


def _receipt(value):
    from core.cost_projection import ESTIMATE_BASIS, project_cost_receipt
    from core.cost_receipts import MISSING_REASONS, empty_usage

    output._receipt_fields(value)
    receipt = project_cost_receipt(value)
    if receipt is None:
        return None
    for part in [receipt, *receipt["components"]]:
        require(set(part["usage"]) <= set(empty_usage()) and set(part["missing_reasons"]) <= set(MISSING_REASONS),
                "grade_readout_accounting_refused")
    # No component identities, provider/deployment labels, price URLs or notes.
    return {**{key: receipt[key] for key in ("status", "currency", "estimated_cost_usd", "known_cost_usd",
        "model_cost_usd", "runtime_cost_usd", "model_calls", "usage", "missing_reasons", "price_table_sha256")},
        "estimate_basis": ESTIMATE_BASIS, "invoice_complete": False, "http_request_count": None}


def _projection(context, terminal, files, entry):
    import step8_grade as step8
    from core.cost_receipts import build_receipt, ledger_reference
    from core.task_checkpoint import CHECKPOINT_FORMAT

    payload = pilot._json_object(files["grade_result"]) if "grade_result" in files else None
    if payload is not None:
        with grading._cwd(pilot.ROOT / "batch-runner"):
            grading._validate_grade_identity(payload, context, entry, terminal["binding"]["retained"]["output_commit"])
    ledger_receipt = None
    if "grade_cost_ledger" in files:
        data = files["grade_cost_ledger"]
        cost_run_id = step8.make_cost_run_id(experiment_yaml_name=context.run.command[2],
            config_hash=entry["config_hash"], grader_source_hash=entry["grader_source_hash"])
        output._ledger(data, context.cell, grading_run_id=cost_run_id)
        if payload is not None and payload.get("cost_ledger") is not None:
            path = grading._grade_path(context, entry["config_hash"], entry["grader_source_hash"],
                                       terminal["binding"]["retained"]["output_commit"])
            require(payload["cost_ledger"] == ledger_reference(str(path.with_name(path.stem + ".cost_ledger.jsonl")),
                    hashlib.sha256(data).hexdigest()), "grade_ledger_pointer_mismatch")
        rows = [pilot._json_object(line.encode()) for line in data.decode("utf-8").splitlines()]
        # Existing aggregation of recorded rows, never repricing or new usage.
        ledger_receipt = _receipt(build_receipt((row for row in rows if row["record_type"] == "call"),
            (row for row in rows if row["record_type"] == "runtime")).as_dict())
    elif payload is not None:
        require(payload.get("cost_ledger") is None, "bound_grade_ledger_missing")
    if "grade_task_progress" in files:
        raw = pilot._json_object(files["grade_task_progress"])
        grading._no_raw_grade(raw)
        require(raw.get("format") == CHECKPOINT_FORMAT and raw.get("task_id") == context.cell["task_id"]
                and raw.get("grader_source_hash") == entry["grader_source_hash"], "grade_readout_progress_refused")
        # The original writer validated rubric order. Do not invent an original
        # rubric from this checkpoint or expose its content as a completed score.
    require(grading._grade_outcome(payload, terminal["child"], progress="grade_task_progress" in files)
            == terminal["outcome"], "grade_readout_outcome_mismatch")
    tasks = payload["tasks"] if payload is not None else []
    task = tasks[0] if tasks else None
    scored = task is not None and not task.get("error")
    counters = step8._new_item_counters()
    for item in task["items"] if task is not None else []:
        step8._tally_item(counters, item)
    return {"grade_state": terminal["outcome"], "payload_run_status": None if payload is None else payload["run_status"],
        "task_rows": len(tasks), "expected_tasks": 1, "scored_tasks": int(scored),
        "task_error_recorded": None if task is None else bool(task.get("error")),
        "score": None if not scored else {"earned": task["total_awarded"], "possible": task["total_max"],
            "pct": task["pct"], **step8._score_exclusion_stats([task], task["pct"])},
        "coverage": {"passed_items": counters["all_pass"], **step8._wow_item_counts(counters),
            "rubric_item_coverage": step8._rate(counters["all_pass"], counters["all_items"]),
            "basis": "retained_items_excluding_score_excluded_not_independent_rubric_revalidation"},
        "partial_progress_retained": "grade_task_progress" in files,
        "ledger_state": "present" if "grade_cost_ledger" in files else "missing",
        "recorded_task_cost": _receipt(task.get("grading_cost")) if task is not None else None,
        "recorded_summary_cost": _receipt(payload["summary"].get("grading_cost")) if payload is not None else None,
        "ledger_derived_cost": ledger_receipt}


def main(args, *, _test_api=None, _test_transport=None):
    public = {"role": "fixed_private_pilot_grade_readout", "outcome": "plan_only", "stage": "plan",
        "reason": None, "http_status": None, "repository_name_sha256": retained.TARGET_SHA256,
        "campaign_id": "budget_pilot_ci_20260925_04", "cell_id": grading.RETAINED_CELL,
        "branch": "pilot-grades-20260925-04", "grade_writer_source_sha": WRITER_SOURCE,
        "grade_writer_run": WRITER_RUN, "inference_producer_source_sha": grading.RETAINED_PRODUCER_SOURCE,
        "inference_terminal": grading.RETAINED_TERMINAL,
        "observer_source_sha": args.reviewed_source_sha if output._hash(args.reviewed_source_sha, 40) else None,
        "remote_mutation_possible": False, "inference_requested": False, "judge_entry_requested": False,
        "automatic_retry": False, "invoice_complete": False, "http_request_count": None}
    try:
        cell = _task2_cell(args.terminal_revision)
        if cell is not None:
            public.update(cell_id=cell, grade_writer_source_sha=TASK2_WRITER_SOURCE,
                grade_writer_run=_task2_run(cell), inference_producer_source_sha=grading.B1_PRODUCER_SOURCE,
                inference_terminal=None, inference_request_checksum=args.terminal_revision)
        context = _context(args)
        if context.terminal_request is not None:
            public.update(cell_id=context.cell["cell_id"], grade_writer_source_sha=context.controller_source_sha,
                grade_writer_run=_writer_run(context), inference_producer_source_sha=context.plan["reviewed_source_sha"],
                inference_terminal=None, inference_request_checksum=context.terminal_request)
        public["stage"] = "observer_authority"
        _authority(args.reviewed_source_sha, live=args.phase == "readout")
        if args.phase == "plan":
            public["stage"] = "plan"
            print(pilot._canonical_json(public))
            return 0
        public["stage"] = "source_preflight"
        with grading._entry_boundary("source_preflight"):
            plan, parent, _ = pilot.compile_pilot(ci.CAMPAIGN, args.reviewed_source_sha)
            (_test_transport or pilot.LocalTransport()).require_source(plan, parent)
        public["stage"] = "read_cache"
        root = grading._root(args.root, new=True)
        with retained._session(_test_api) as (raw_api, token, deadline):
            repo = retained._target()
            api = _ReadOnlyGrade(raw_api, repo, token, context)
            public["stage"] = "grade_snapshot"
            head = api.locate(deadline)
            public["stage"] = "grade_terminal"
            verified, entry, previous = _verified_grade(api, context, root, deadline)
            terminal = verified["terminal"]
            renderer = entry["renderer_fingerprint"]
            if context.cell["cell_id"] in TASK2_GRADE_RUNS:
                _verify_predecessor(api, context, verified, previous, grading._cache(root, "predecessor"), deadline)
            api.allow_verified_files(terminal["files"])
            public["stage"] = "grade_payload"
            cache = grading._cache(root, "payload")
            files = {record["role"]: grading._fetch(api, repo, api.revision, record["path"], record, cache, token, deadline)
                     for record in terminal["files"]}
            summary = _projection(context, terminal, files, entry)
        public.update(outcome="verified_retained_grade", stage="verified", **summary,
            observed_branch_head=head, grade_revision=verified["revision"], terminal_identity=verified["identity"],
            claim_revision=terminal["claim_commit"], claim_identity=terminal["claim_identity"],
            file_identities=[{key: record[key] for key in ("role", "size", "sha256")} for record in terminal["files"]],
            inference_output_commit=terminal["binding"]["retained"]["output_commit"],
            inference_terminal=context.terminal_revision,
            grader_source_hash=entry["grader_source_hash"], grader_config_sha256=CONFIG_SHA256,
            rubric_revision=json.loads(context.run.grader_config_json)["rubric"]["revision"],
            renderer_fingerprint_sha256=pilot._digest(renderer), proof_boundary=grading.PROOF)
        print(pilot._canonical_json(public))
        return 0  # Readout succeeded; grade_state may still be partial/failed/ungraded.
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError,
            subprocess.SubprocessError, ImportError, KeyboardInterrupt) as error:
        reason, status = output._error_context(error)
        public.update(outcome="refused", reason=(reason if reason == "grade_readout_writer_unconfigured"
                                                else "grade_readout_contract_refused"),
                      http_status=status if type(status) is int and 100 <= status <= 599 else None)
        print(pilot._canonical_json(public), file=sys.stderr)
        return 2
