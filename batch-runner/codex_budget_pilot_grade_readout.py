"""Closed recorded-grade readout, not admission, publication or regrading."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
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
# Only the issued task3 A1 grade. Writer69's compiled config and grader closure
# retain the independently derived hashes above; the observer supplies neither.
TASK3_A1_WRITER_SOURCE = "69e56fc58daf50af2ac9e8b52691ffcbf5af4f96"
TASK3_A1_WRITER_RUN = {"id": "36282221138", "job": "pilot-live", "attempt": 1}
TASK3_A1_GRADER_SOURCE_HASH = "0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df"
# Only these five recorded successors share the immutable writer/config.
TASK3_B1_CELL = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_B_r1"
TASK3_B1_WRITER_RUN = {"id": "36283710283", "job": "pilot-live", "attempt": 1}
TASK3_C1_CELL = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_C_r1"
TASK3_C2_CELL = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_C_r2"
TASK3_B2_CELL = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_B_r2"
TASK3_A2_CELL = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r2"
TASK3_SUCCESSOR_READOUTS = {
    TASK3_B1_CELL: (13, grading.TASK3_A1_CELL, TASK3_B1_WRITER_RUN),
    TASK3_C1_CELL: (14, TASK3_B1_CELL, {"id": "36285446183", "job": "pilot-live", "attempt": 1}),
    TASK3_C2_CELL: (15, TASK3_C1_CELL, {"id": "36286719528", "job": "pilot-live", "attempt": 1}),
    TASK3_B2_CELL: (16, TASK3_C2_CELL, {"id": "36288201352", "job": "pilot-live", "attempt": 1}),
    TASK3_A2_CELL: (17, TASK3_B2_CELL, {"id": "36289615941", "job": "pilot-live", "attempt": 1}),
}
# Only this published model-free record, never an ordinary judged successor.
TASK4_A1_WRITER_RUN = {"id": "36291118506", "job": "pilot-live", "attempt": 1}
# Only this ordinary grade consumes the recorded model-free A1 predecessor.
TASK4_B1_WRITER_RUN = {"id": "36292532223", "job": "pilot-live", "attempt": 1}
# Only these three published ordinary successors; A2 and task5 stay closed.
TASK4_C1_CELL = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_C_r1"
TASK4_C2_CELL = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_C_r2"
TASK4_B2_CELL = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2"
TASK4_SUCCESSOR_READOUTS = {
    TASK4_C1_CELL: (20, grading.TASK4_B1_CELL, {"id": "36294081159", "job": "pilot-live", "attempt": 1}),
    TASK4_C2_CELL: (21, TASK4_C1_CELL, {"id": "36295603145", "job": "pilot-live", "attempt": 1}),
    TASK4_B2_CELL: (22, TASK4_C2_CELL, {"id": "36297122393", "job": "pilot-live", "attempt": 1}),
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


def _task3_successor_cell(request):
    return next((cell for cell in TASK3_SUCCESSOR_READOUTS if grading.TASK3_SUCCESSORS[cell][1] == request), None)


def _task4_successor_cell(request):
    return next((cell for cell in TASK4_SUCCESSOR_READOUTS if grading.TASK4_RETAINED[cell][1] == request), None)


def _writer_context(request):
    require(ci.CAMPAIGN == "budget_pilot_ci_20260925_04"
            and grading.BRANCH == "pilot-grades-20260925-04"
            and retained.BRANCH == "pilot-inference-20260925-04", "grade_readout_epoch_refused")
    task3_cell = _task3_successor_cell(request)
    task4_cell = _task4_successor_cell(request)
    if request == grading.RETAINED_TERMINAL:
        context = grading.compile_request("pilot/" + grading.RETAINED_CELL, WRITER_SOURCE,
            request, producer_source_sha=grading.RETAINED_PRODUCER_SOURCE)
    elif request == grading.TASK2_RETAINED[grading.B1_CELL][1]:
        context = grading.compile_request("pilot/" + grading.B1_CELL, B1_WRITER_SOURCE,
            request, producer_source_sha=grading.B1_PRODUCER_SOURCE)
    elif request == grading.TASK3_A1_COMPLETION_SHA256:
        context = grading.compile_request("pilot/" + grading.TASK3_A1_CELL, TASK3_A1_WRITER_SOURCE,
            request, producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    elif task3_cell is not None:
        context = grading.compile_request("pilot/" + task3_cell, TASK3_A1_WRITER_SOURCE,
            request, producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    elif request == grading.TASK4_RETAINED[grading.TASK4_A1_CELL][1]:
        context = grading.compile_request("pilot/" + grading.TASK4_A1_CELL, TASK3_A1_WRITER_SOURCE,
            request, producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    elif request == grading.TASK4_RETAINED[grading.TASK4_B1_CELL][1]:
        context = grading.compile_request("pilot/" + grading.TASK4_B1_CELL, TASK3_A1_WRITER_SOURCE,
            request, producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    elif task4_cell is not None:
        context = grading.compile_request("pilot/" + task4_cell, TASK3_A1_WRITER_SOURCE,
            request, producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
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
    if context.cell["cell_id"] in TASK4_SUCCESSOR_READOUTS:
        return TASK4_SUCCESSOR_READOUTS[context.cell["cell_id"]][2]
    if context.cell["cell_id"] == grading.TASK4_B1_CELL:
        return TASK4_B1_WRITER_RUN
    if context.cell["cell_id"] == grading.TASK4_A1_CELL:
        return TASK4_A1_WRITER_RUN
    if context.cell["cell_id"] in TASK3_SUCCESSOR_READOUTS:
        return TASK3_SUCCESSOR_READOUTS[context.cell["cell_id"]][2]
    if context.cell["cell_id"] == grading.TASK3_A1_CELL:
        return TASK3_A1_WRITER_RUN
    if context.cell["cell_id"] in TASK2_GRADE_RUNS:
        return _task2_run(context.cell["cell_id"])
    return B1_WRITER_RUN if context.cell["cell_id"] == grading.B1_CELL else WRITER_RUN


def _writer_entry(context, renderer):
    require(type(renderer) is dict and set(renderer) == {
        "libreoffice_binary", "libreoffice_version", "pymupdf_version"}
        and all(type(value) is str and 0 < len(value) <= 1024 for value in renderer.values()),
        "grade_readout_renderer_identity_refused")
    source_hash = (TASK3_A1_GRADER_SOURCE_HASH if context.cell["cell_id"] in {
                   grading.TASK3_A1_CELL, *TASK3_SUCCESSOR_READOUTS, grading.TASK4_A1_CELL,
                   grading.TASK4_B1_CELL, *TASK4_SUCCESSOR_READOUTS} else
                   TASK2_GRADER_SOURCE_HASH if context.cell["cell_id"] in TASK2_GRADE_RUNS else
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
        require(context.cell["cell_id"] in {*grading.TASK2_RETAINED, grading.TASK3_A1_CELL,
                *TASK3_SUCCESSOR_READOUTS, grading.TASK4_A1_CELL, grading.TASK4_B1_CELL, *TASK4_SUCCESSOR_READOUTS}
                and context.terminal_request is not None,
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
        if context.cell["cell_id"] in {*TASK2_GRADE_RUNS, grading.TASK3_A1_CELL,
                *TASK3_SUCCESSOR_READOUTS, grading.TASK4_A1_CELL, grading.TASK4_B1_CELL, *TASK4_SUCCESSOR_READOUTS}:
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
    task4_b1 = context.cell["cell_id"] == grading.TASK4_B1_CELL
    task4_successor = context.cell["cell_id"] in TASK4_SUCCESSOR_READOUTS
    if context.cell["cell_id"] in TASK3_SUCCESSOR_READOUTS or task4_b1 or task4_successor:
        # Also needed for an immediate predecessor's intrinsic ordinary check;
        # this grants its older terminal control, not another semantic proof.
        # Full writer/input/entry equality still precedes selected payload access.
        ordinal, cell, _ = ((19, grading.TASK4_A1_CELL, TASK4_B1_WRITER_RUN) if task4_b1 else
                            TASK4_SUCCESSOR_READOUTS[context.cell["cell_id"]] if task4_successor else
                            TASK3_SUCCESSOR_READOUTS[context.cell["cell_id"]])
        claim, claim_bytes = retained._control(api, api._repo, terminal["claim_commit"], grading._paths(context.cell)[0],
            grading._cache(cache, "parent-grant"), api._token, deadline,
            expected=terminal["claim_identity"], written_at=terminal["claim_commit"])
        require(set(claim) == {"format", "binding", "expected_parent", "predecessor"}
                and claim["format"] == grading.CLAIM_FORMAT and claim["binding"] == terminal["binding"],
                "grade_terminal_claim_mismatch")
        if task4_b1 or task4_successor:
            require(claim_bytes == retained._encoded({**claim, "binding": terminal["binding"]}),
                    "grade_readout_typed_claim_refused")
        grading._task3_grade_predecessor(context, claim)
        require(context.plan["order"].index(context.cell["cell_id"]) == ordinal
                and context.plan["order"][ordinal - 1] == cell
                and len({claim["expected_parent"], terminal["claim_commit"], api.revision}) == 3,
                "grade_readout_predecessor_revision_refused")
        path = grading._paths(context.plan["cells"][ordinal - 1])[1]
        api._metadata_paths[claim["expected_parent"]] = {path}
        api._downloads.add((claim["expected_parent"], path))
        api._metadata_paths[terminal["claim_commit"]].add(path)
    verified = grading._grade_terminal(api, api._repo, api.revision, context, entry,
        grading._cache(cache, "verified"), api._token, deadline)
    require(verified["terminal"] == terminal, "grade_readout_terminal_changed")
    return verified, entry, previous


def _verify_predecessor(api, context, verified, inference_previous, cache, deadline):
    """One parent; only C1 also reuses the fixed B1-after-NG proof below."""
    terminal = verified["terminal"]
    claim, _ = retained._control(api, api._repo, terminal["claim_commit"], grading._paths(context.cell)[0],
        grading._cache(cache, "claim"), api._token, deadline,
        expected=terminal["claim_identity"], written_at=terminal["claim_commit"])
    ordinal = context.plan["order"].index(context.cell["cell_id"])
    cell = context.plan["order"][ordinal - 1]
    task4_b1 = context.cell["cell_id"] == grading.TASK4_B1_CELL
    task4_successor = context.cell["cell_id"] in TASK4_SUCCESSOR_READOUTS
    if task4_b1:
        require(ordinal == 19 and context.plan["order"][17:20] == [
            TASK3_A2_CELL, grading.TASK4_A1_CELL, grading.TASK4_B1_CELL],
            "grade_readout_original_task4_a1_required")
        other = _writer_context(grading.TASK4_RETAINED[grading.TASK4_A1_CELL][1])
    elif task4_successor:
        expected_ordinal, expected_cell, _ = TASK4_SUCCESSOR_READOUTS[context.cell["cell_id"]]
        require(ordinal == expected_ordinal and cell == expected_cell,
                "grade_readout_original_task4_predecessor_required")
        other = _writer_context(grading.TASK4_RETAINED[cell][1])
    elif context.cell["cell_id"] in TASK3_SUCCESSOR_READOUTS:
        expected_ordinal, expected_cell, _ = TASK3_SUCCESSOR_READOUTS[context.cell["cell_id"]]
        require(ordinal == expected_ordinal and cell == expected_cell, "grade_readout_original_task3_predecessor_required")
        other = _writer_context(grading.TASK3_A1_COMPLETION_SHA256 if cell == grading.TASK3_A1_CELL
                                else grading.TASK3_SUCCESSORS[cell][1])
    else:
        other = _writer_context(grading.TASK2_RETAINED[cell][1])
    revision = claim["expected_parent"]
    require(len({revision, api.revision, terminal["claim_commit"]}) == 3,
            "grade_readout_predecessor_revision_refused")
    if cell == grading.B1_CELL:
        require(revision == B1_PREDECESSOR_GRADE, "grade_readout_original_b1_required")
    if context.cell["cell_id"] == grading.TASK3_A1_CELL:
        require(ordinal == 12 and cell == "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r2"
                and revision == grading.TASK3_A1_PREVIOUS_GRADE, "grade_readout_original_task2_a2_required")
    prior = _ReadOnlyGrade(api._api, api._repo, api._token, other)
    prior._metadata_open = False  # No second branch snapshot or moving-tip lookup.
    prior.revision = revision
    path = grading._paths(other.cell)[1]
    prior._metadata_paths[revision] = {path}
    prior._downloads.add((revision, path))
    if task4_b1:
        # A1 stays model-free. Its existing verifier alone opens the two
        # verified failure inputs, ordinary A2 proof and intrinsic B2 control.
        previous, previous_entry, _ = _verified_ungraded(prior, other, grading._cache(cache, "previous"), deadline)
        require({api.revision, terminal["claim_commit"]}.isdisjoint(prior._metadata_paths),
                "grade_readout_predecessor_revision_refused")
        require(retained._encoded(previous_entry) == retained._encoded(
                    _writer_entry(context, terminal["binding"]["renderer_fingerprint"]))
                and retained._encoded(claim["predecessor"]) == retained._encoded(
                    {"cell_id": cell, "revision": revision, **previous["identity"]})
                and retained._encoded(inference_previous) == retained._encoded(previous["terminal"]["binding"]["retained"]),
                "grade_readout_ungraded_predecessor_refused")
    else:
        previous, previous_entry, previous_inference = _verified_grade(
            prior, other, grading._cache(cache, "previous"), deadline)
    if task4_successor:
        selected_revisions = {api.revision, terminal["claim_commit"]}
        if context.cell["cell_id"] == TASK4_C1_CELL:
            # Only this exact link reuses B1's NG semantics. C2/B2 never walk it.
            require(other.cell["cell_id"] == grading.TASK4_B1_CELL,
                    "grade_readout_original_task4_predecessor_required")
            ng_revisions = _verify_predecessor(prior, other, previous, previous_inference,
                grading._cache(cache, "b1-ungraded-proof"), deadline)
            require(type(ng_revisions) is frozenset and selected_revisions.isdisjoint(ng_revisions),
                    "grade_readout_predecessor_revision_refused")
        require(selected_revisions.isdisjoint(prior._metadata_paths),
                "grade_readout_predecessor_revision_refused")
        require(retained._encoded(previous_entry) == retained._encoded(
                    _writer_entry(context, terminal["binding"]["renderer_fingerprint"]))
                and retained._encoded(claim["predecessor"]) == retained._encoded(
                    {"cell_id": cell, "revision": revision, **previous["identity"]})
                and retained._encoded(inference_previous) == retained._encoded(previous["terminal"]["binding"]["retained"]),
                "grade_readout_typed_predecessor_refused")
    if context.cell["cell_id"] in TASK3_SUCCESSOR_READOUTS:
        require(previous_entry == _writer_entry(context, terminal["binding"]["renderer_fingerprint"]),
                "grade_readout_predecessor_entry_refused")
    require(claim["predecessor"] == {"cell_id": cell, "revision": revision, **previous["identity"]},
            "grade_readout_predecessor_identity_refused")
    observed = previous["terminal"]["binding"]["retained"]
    require(inference_previous == observed, "grade_readout_inference_predecessor_refused")
    if cell == grading.B1_CELL:
        require(observed["terminal_commit"] == B1_PREDECESSOR_INFERENCE, "grade_readout_original_b1_required")
    if context.cell["cell_id"] == grading.TASK3_A1_CELL:
        require(observed["terminal_commit"] == grading.TASK3_A1_PREVIOUS_TERMINAL,
                "grade_readout_original_task2_a2_required")
    api._metadata_paths[terminal["claim_commit"]].add(path)
    retained._objects(api, api._repo, terminal["claim_commit"],
        [retained._object(path, retained._encoded(previous["terminal"]))], api._token, deadline, written_at=revision)
    # Predecessor grade files have metadata proofs only. Never open their downloads.
    if task4_b1:
        return frozenset(prior._metadata_paths)  # Revision footprint only, not read authority.


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


def _verified_ungraded(api, context, cache, deadline):
    """Only recorded task4 A1, with ordinary A2 and intrinsic B2 control proof."""
    import codex_budget_pilot_ungraded as ungraded

    ungraded._scope(context)
    require(context.cell["cell_id"] == grading.TASK4_A1_CELL
            and context.plan["order"][17:19] == [TASK3_A2_CELL, grading.TASK4_A1_CELL],
            "grade_readout_ungraded_route_refused")
    terminal, data = retained._control(api, api._repo, api.revision, api._terminal,
        grading._cache(cache, "terminal"), api._token, deadline, written_at=api.revision)
    require(terminal.get("format") == ungraded.TERMINAL_FORMAT and terminal.get("model_invoked") is False,
            "model_free_terminal_type_required")
    binding = terminal["binding"]
    entry = _writer_entry(context, binding["predecessor_entry"]["renderer_fingerprint"])
    expected = ungraded._binding(context, {"observation": binding["retained"], "terminal": {
        "publication_receipt_sha256": binding["publication_receipt_sha256"]}},
        binding["inference_identity_sha256"], entry, TASK4_A1_WRITER_RUN)
    require(retained._encoded(binding) == retained._encoded(expected), "grade_readout_ungraded_binding_refused")
    claim_revision = terminal["claim_commit"]
    require(output._hash(claim_revision, 40) and claim_revision != api.revision, "grade_readout_claim_refused")
    api._metadata_paths[claim_revision] = {api._claim}
    api._downloads.add((claim_revision, api._claim))
    claim, claim_bytes = retained._control(api, api._repo, claim_revision, api._claim,
        grading._cache(cache, "claim"), api._token, deadline,
        expected=terminal["claim_identity"], written_at=claim_revision)
    require(set(claim) == {"format", "binding", "expected_parent", "predecessor"}
            and claim_bytes == retained._encoded({**claim, "format": ungraded.CLAIM_FORMAT, "binding": expected}),
            "model_free_claim_changed")
    grading._task3_grade_predecessor(context, claim)
    require(len({api.revision, claim_revision, claim["expected_parent"]}) == 3,
            "grade_readout_predecessor_revision_refused")
    observed = api.bind_retained(binding, context, grading._cache(cache, "input"), deadline)
    other = _writer_context(grading.TASK3_SUCCESSORS[TASK3_A2_CELL][1])
    prior = _ReadOnlyGrade(api._api, api._repo, api._token, other)
    prior._metadata_open = False
    prior.revision = claim["expected_parent"]
    prior._metadata_paths[prior.revision] = {prior._terminal}
    prior._downloads.add((prior.revision, prior._terminal))
    previous, previous_entry, _ = _verified_grade(prior, other, grading._cache(cache, "previous"), deadline)
    require(previous_entry == entry
            and claim["predecessor"] == {"cell_id": TASK3_A2_CELL, "revision": prior.revision, **previous["identity"]}
            and observed == previous["terminal"]["binding"]["retained"], "grade_readout_predecessor_identity_refused")
    parent_claim_revision = previous["terminal"]["claim_commit"]
    parent_claim, parent_bytes = retained._control(prior, api._repo, parent_claim_revision, prior._claim,
        grading._cache(cache, "parent-claim"), api._token, deadline,
        expected=previous["terminal"]["claim_identity"], written_at=parent_claim_revision)
    require(parent_bytes == retained._encoded({**parent_claim, "format": grading.CLAIM_FORMAT,
                "binding": previous["terminal"]["binding"]})
            and len({api.revision, claim_revision, prior.revision, parent_claim_revision,
                     parent_claim["expected_parent"]}) == 5
            and set(api._metadata_paths).isdisjoint(prior._metadata_paths),
            "grade_readout_predecessor_revision_refused")
    api._metadata_paths[claim_revision].add(prior._terminal)
    api._metadata_paths[api.revision].add(api._claim)
    retained._objects(api, api._repo, claim_revision,
        [retained._object(prior._terminal, retained._encoded(previous["terminal"]))],
        api._token, deadline, written_at=prior.revision)
    retained._objects(api, api._repo, api.revision, [retained._object(api._claim, claim_bytes)],
        api._token, deadline, written_at=claim_revision)
    # Transfer only A2's validated capabilities, including B2 terminal control.
    # The native verifier rechecks A2; it never recursively verifies B2.
    api._metadata_paths.update(prior._metadata_paths)
    api._downloads.update(prior._downloads)
    api._inference_revisions.update(prior._inference_revisions)
    api._inference_metadata.update({context.terminal_revision, other.terminal_revision})
    prefix = retained._paths(context.cell)[2]
    names = ("step2_inference_results.json", Path(pilot.LEDGER).name)
    output_revision = binding["retained"]["output_commit"]
    api._downloads.update((output_revision, prefix + "/" + name) for name in names)
    verified = ungraded.verify_terminal(api, api._repo, api.revision, context, entry,
        grading._cache(cache, "verified"), api._token, deadline)
    require(verified["identity"] == pilot._identity(data), "grade_readout_terminal_changed")
    artifacts = verified["terminal"]["inference_completion"]["artifacts"]
    projection = grading._cache(cache, "projection")
    files = {name: grading._fetch(api, api._repo, output_revision, prefix + "/" + name, artifacts[role],
             projection, api._token, deadline)
             for name, role in zip(names, ("result", "ledger"))}
    return verified, entry, files


def _ungraded_projection(context, terminal, files):
    from core.cost_receipts import build_receipt

    payload = pilot._json_object(files["step2_inference_results.json"])
    ledger = files[Path(pilot.LEDGER).name]
    output._ledger(ledger, context.cell)
    rows = [pilot._json_object(line.encode()) for line in ledger.decode("utf-8").splitlines()]
    return {"record_kind": "model_free_ungraded", "grade_state": "ungraded", "grade_success": False,
        "model_requested": False, "model_invoked": False, "payload_run_status": None,
        "task_rows": 0, "expected_tasks": 1, "scored_tasks": 0, "task_error_recorded": None,
        "score": None, "coverage": None, "partial_progress_retained": False, "ledger_state": "not_applicable",
        "recorded_task_cost": None, "recorded_summary_cost": None, "ledger_derived_cost": None,
        "inference_task_status": payload["results"][0]["status"],
        "inference_completion": ci.validate_completion(terminal["inference_completion"]),
        "inference_missing": terminal["inference_missing"],
        "inference_accounting": {
            "recorded_task_cost": _receipt(payload["results"][0].get("problem_solving_cost")),
            "recorded_summary_cost": _receipt(payload["summary"].get("problem_solving_cost")),
            "ledger_derived_cost": _receipt(build_receipt((row for row in rows if row["record_type"] == "call"),
                (row for row in rows if row["record_type"] == "runtime")).as_dict())},
        "recorder_accounting": terminal["recorder_accounting"]}


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
        task3_cell = _task3_successor_cell(args.terminal_revision)
        task4_cell = _task4_successor_cell(args.terminal_revision)
        if args.terminal_revision == grading.TASK4_RETAINED[grading.TASK4_A1_CELL][1]:
            public.update(cell_id=grading.TASK4_A1_CELL, grade_writer_source_sha=TASK3_A1_WRITER_SOURCE,
                grade_writer_run=TASK4_A1_WRITER_RUN, inference_producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE,
                inference_terminal=None, inference_request_checksum=args.terminal_revision)
        elif args.terminal_revision == grading.TASK4_RETAINED[grading.TASK4_B1_CELL][1]:
            public.update(cell_id=grading.TASK4_B1_CELL, grade_writer_source_sha=TASK3_A1_WRITER_SOURCE,
                grade_writer_run=TASK4_B1_WRITER_RUN, inference_producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE,
                inference_terminal=None, inference_request_checksum=args.terminal_revision)
        elif task4_cell is not None:
            public.update(cell_id=task4_cell, grade_writer_source_sha=TASK3_A1_WRITER_SOURCE,
                grade_writer_run=TASK4_SUCCESSOR_READOUTS[task4_cell][2],
                inference_producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE,
                inference_terminal=None, inference_request_checksum=args.terminal_revision)
        elif args.terminal_revision == grading.TASK3_A1_COMPLETION_SHA256:
            public.update(cell_id=grading.TASK3_A1_CELL, grade_writer_source_sha=TASK3_A1_WRITER_SOURCE,
                grade_writer_run=TASK3_A1_WRITER_RUN, inference_producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE,
                inference_terminal=None, inference_request_checksum=args.terminal_revision)
        elif task3_cell is not None:
            public.update(cell_id=task3_cell, grade_writer_source_sha=TASK3_A1_WRITER_SOURCE,
                grade_writer_run=TASK3_SUCCESSOR_READOUTS[task3_cell][2], inference_producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE,
                inference_terminal=None, inference_request_checksum=args.terminal_revision)
        elif cell is not None:
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
            model_free = context.cell["cell_id"] == grading.TASK4_A1_CELL
            if model_free:
                public["stage"] = "ungraded_terminal"
                verified, entry, files = _verified_ungraded(api, context, root, deadline)
                terminal, records = verified["terminal"], []
                public["stage"] = "ungraded_projection"
                summary = _ungraded_projection(context, terminal, files)
            else:
                public["stage"] = "grade_terminal"
                verified, entry, previous = _verified_grade(api, context, root, deadline)
                terminal = verified["terminal"]
                if context.cell["cell_id"] in {*TASK2_GRADE_RUNS, grading.TASK3_A1_CELL,
                        *TASK3_SUCCESSOR_READOUTS, grading.TASK4_B1_CELL, *TASK4_SUCCESSOR_READOUTS}:
                    _verify_predecessor(api, context, verified, previous, grading._cache(root, "predecessor"), deadline)
                records = terminal["files"]
                api.allow_verified_files(records)
                public["stage"] = "grade_payload"
                cache = grading._cache(root, "payload")
                files = {record["role"]: grading._fetch(api, repo, api.revision, record["path"], record, cache, token, deadline)
                         for record in records}
                summary = _projection(context, terminal, files, entry)
            renderer = entry["renderer_fingerprint"]
        public.update(outcome="verified_retained_ungraded" if model_free else "verified_retained_grade", stage="verified", **summary,
            observed_branch_head=head, grade_revision=verified["revision"], terminal_identity=verified["identity"],
            claim_revision=terminal["claim_commit"], claim_identity=terminal["claim_identity"],
            file_identities=[{key: record[key] for key in ("role", "size", "sha256")} for record in records],
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
