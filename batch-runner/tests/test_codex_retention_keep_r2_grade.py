"""One offline KEEP/r2 grade proof and its coupled routing/ledger contract.

Immutable synthetic controls, payloads and an owned-child transport reach the
real validators. Fixture-only byte pins are rebound after checking production
constants; they are not observed publications, paid results or provider proof.
"""

from copy import deepcopy
from dataclasses import replace
import ctypes
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest
import yaml

import codex_retention_fixed_grade as bridge
import codex_retention_keep_r2_grade as fixed
import codex_retention_fresh_r1_result_intake as reader
import codex_retention_grade_readout as parent_reader
import gpt54_disposable_checkout as checkout
import gpt54_v2_grading_input as materializer
from core.result_fingerprint import inference_result_fingerprint
from core.task_checkpoint import (TaskProgressDraft, build_progress, checkpoint_path,
                                 load_checkpoint, write_checkpoint)
from step2_run_inference import _build_execution_observability
from . import test_codex_budget_pilot_grading as base
from . import test_codex_retention_fixed_grade as first
from . import test_codex_retention_grade_readout as parent_fixture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401
from .test_codex_budget_pilot_retention import offline, TOKEN  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_result_intake import TERMINAL_HEAD, PRIVATE

grade, pilot, retained, output = bridge.grade, bridge.pilot, bridge.retained, bridge.output
SOURCE, RUN = first.SOURCE, first.RUN
EVIDENCE = "25d2591a2b53d3055a7efb46b55ce86bab811a702e6598b7119f0625784b6ca0"
FIRST_EVIDENCE = "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"


def _filename_leaves(grade_path, task_id):
    path = Path(grade_path)
    checkpoint = checkpoint_path(path, task_id)
    sqlite = path.stem + ".cost_ledger.sqlite3"
    return {"grade": path.name, "jsonl_ledger": path.stem + ".cost_ledger.jsonl",
        "sqlite": sqlite, "sqlite_wal": sqlite + "-wal", "sqlite_shm": sqlite + "-shm",
        "sqlite_journal": sqlite + "-journal", "checkpoint": checkpoint.name,
        "checkpoint_tmp": checkpoint.with_suffix(".json.tmp").name}


def _environment(monkeypatch, selector=fixed.SELECTOR):
    first._environment(monkeypatch)
    selected = bridge._fixed(selector)
    monkeypatch.setenv("GRADE_SELECTOR", selector)
    monkeypatch.setenv("GRADE_TERMINAL", selected.RESULT["terminal_commit"])
    monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", pilot._digest(
        bridge.approval_request(SOURCE, RUN, selector=selector)))


class GradeHF(base.GradeHF):
    def __init__(self):
        super().__init__()
        self.downloads, self.path_reads = [], []
        self.drift_after_parent = False

    def hf_hub_download(self, **kwargs):
        self.downloads.append((kwargs["repo_id"], kwargs["revision"], kwargs["filename"]))
        # Previous grades may be inspected only through their two controls.
        if kwargs["revision"] in {parent_reader.TERMINAL, parent_reader.CLAIM}:
            assert kwargs["filename"] in {bridge.CLAIM_PATH, bridge.TERMINAL_PATH}
        return super().hf_hub_download(**kwargs)

    def get_paths_info(self, **kwargs):
        self.path_reads.append((kwargs["revision"], tuple(kwargs["paths"])))
        found = super().get_paths_info(**kwargs)
        if self.drift_after_parent and kwargs["paths"] == [fixed.PREFIX]:
            self.branches[grade.BRANCH] = retained.BOOTSTRAP
        return found


class OwnedJudge(base.Child):
    def checkout(self, destination, sha):
        super().checkout(destination, sha)
        for name in fixed.READER_FILES.values():
            shutil.copyfile(bridge.ROOT / "batch-runner" / name, destination / "batch-runner" / name)


def _synthetic_case(tmp_path, monkeypatch):
    # Production's consumed receipt keeps its historical READER and refuses the
    # migrated current helper. This authored fixture, like its RESULT below,
    # binds its own current bytes before compiling a synthetic grading context.
    monkeypatch.setattr(fixed, "READER", reader.reader_identity(binding=reader.KEEP_R2))
    original = bridge.compile_request(SOURCE, selector=fixed.SELECTOR)
    assert bridge._origins(original)[0] == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    synthetic = FreshResultHF(original.plan, binding=reader.KEEP_R2, with_ledger=True)
    config = json.loads(original.grading.dispatch.runs[0].config_json)
    synthetic.payload.update(experiment_name=config["experiment"]["name"],
        condition=config["condition_a"]["name"], started_at="2026-10-02T00:00:00Z",
        completed_at="2026-10-02T00:01:00Z", resume_rounds_used=0,
        summary={"total": 1, "success": 1, "error": 0, "qa_failed": 0})
    synthetic.payload["results"][0].update(deliverable_text="synthetic answer", latency_ms=1.0,
        timestamp="2026-10-02T00:01:00Z", error=None, observability=_build_execution_observability({}, []))
    synthetic.bind_payload()
    synthetic.seed()
    record = reader.read_result(expectation=reader.KEEP_R2.expectation, binding=reader.KEEP_R2,
        destination=tmp_path / "synthetic-marker", expected_reader_sha256=fixed.READER["module_sha256"],
        terminal_revision=TERMINAL_HEAD, discover_terminal=False, _test_api=synthetic)
    expected = {key: deepcopy(record[key]) for key in fixed.RESULT}
    expected["result"] = {key: record["result"][key] for key in fixed.RESULT["result"]}
    monkeypatch.setattr(fixed, "RESULT", expected)

    parent_context = bridge.compile_request(parent_reader.WRITER_SOURCE)
    terminal, claim, payload, ledger = parent_fixture._fixture(parent_context)
    previous = parent_fixture._seed(monkeypatch, terminal, claim, payload, ledger)
    monkeypatch.setattr(fixed, "PARENT", {**fixed.PARENT,
        "terminal_identity": parent_reader.TERMINAL_IDENTITY,
        "claim_identity": pilot._identity(retained._encoded(claim))})
    api = GradeHF()
    for source in (synthetic, previous):
        for name in ("trees", "writers", "parents"):
            getattr(api, name).update(deepcopy(getattr(source, name)))
    api.head = TERMINAL_HEAD
    api.main_snapshot = deepcopy(api.trees[TERMINAL_HEAD])
    api.branches[grade.BRANCH] = fixed.PARENT["revision"]
    context = bridge.compile_request(SOURCE, selector=fixed.SELECTOR)
    case = SimpleNamespace(root=tmp_path / "new-grade", context=context, api=api)
    _environment(monkeypatch)
    base._synthetic_rubric(case, monkeypatch)
    origins = base.intake._hf_origins()
    monkeypatch.setattr(bridge, "_origins", lambda supplied: origins if supplied is context else
                        pytest.fail("unexpected original-input scope"))

    def rename(src_fd, src, dest_fd, dest, flags):
        assert flags == 1
        if os.path.lexists(Path(f"/proc/self/fd/{dest_fd}") / os.fsdecode(dest)):
            ctypes.set_errno(errno.EEXIST)
            return -1
        os.rename(src, dest, src_dir_fd=src_fd, dst_dir_fd=dest_fd)
        return 0

    monkeypatch.setattr(materializer, "_no_replace_rename", lambda: rename)
    common = tmp_path / "synthetic-git-metadata"
    common.mkdir()
    state = {"head": SOURCE}

    def git(path, *command, ok=(0,)):
        path = Path(path)
        assert path == bridge.ROOT or (path.name == "source" and path.parent.parent == tmp_path)
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(path) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (state["head"] + "\n").encode(),
            ("diff", "--name-only", "HEAD", "--"): b"",
            ("status", "--porcelain", "--untracked-files=normal"): b"",
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): b""}
        assert command in answers, "only allowlisted source metadata"
        return SimpleNamespace(stdout=answers[command], returncode=0)

    monkeypatch.setattr(pilot, "_git", git)
    monkeypatch.setattr(checkout, "_git", git)
    return case, OwnedJudge(case), record, state


def _capture(capsys, tmp_path):
    text = capsys.readouterr()
    assert not text.err
    for private in (TOKEN, PRIVATE.decode().strip(), str(tmp_path), retained._target()):
        assert private not in text.out
    return json.loads(text.out)


def test_keep_r2_fixed_grade_is_bound_one_use_and_private(tmp_path, monkeypatch, capsys):
    assert fixed.SELECTOR == "retention/keep-r2"
    assert bridge.fixed_evidence_sha256() == FIRST_EVIDENCE
    assert bridge.fixed_evidence_sha256(fixed.SELECTOR) == EVIDENCE
    assert fixed.RESULT["terminal_commit"] == "e55fac5d60191167dd66688510ec0fef472e594d"
    assert fixed.RESULT["intake_sha256"] == "4d33c1160fe27af76fa37cf1360d85e7cdeb92992ccfaf748ee65bb6c80c84a4"
    assert fixed.PARENT["revision"] == "40712e0980cc05c31688fdbb98c693774fb90c0d"
    assert fixed.PARENT["revision"] != fixed.RESULT["terminal_commit"]
    assert reader.reader_identity(binding=reader.KEEP_R2) != fixed.READER
    with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_reader_required$"):
        fixed._reader()
    assert bridge.fixed_evidence_sha256(fixed.SELECTOR) == EVIDENCE
    case, transport, record, source_state = _synthetic_case(tmp_path, monkeypatch)
    context, root, api = case.context, case.root, case.api
    assert context.cell["index"] == 3 and context.cell["control"] == {
        "condition": "retention_bundle_v1", "retention_bundle": "keep", "repetition": 2}
    assert context.run.command[2] == fixed.SELECTOR and context.run.grader_config_path == fixed.GRADER_PATH
    assert context.run.experiment_config_path == "batch-runner/experiments/retention/keep-r2.yaml"
    assert record["expected_execution_job_id"] == record["recorded_provider_job_id"] == 110660390316
    assert record["predecessor"]["terminal_commit"] == "1d5133590911f3704fc2a65279d4b64bee77c1d6"

    # Approval/source/hash failures precede private-root creation and transport.
    for variable, value in (("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64),
            ("PILOT_GRADE_APPROVAL_RESULT", "skipped"), ("GITHUB_RUN_ATTEMPT", "2"),
            ("GRADE_SELECTOR", bridge.SELECTOR), ("GRADE_FORCE", "true"),
            ("GRADE_RESUME", "true"), ("GRADE_SHARD_COUNT", "2")):
        with monkeypatch.context() as scoped:
            scoped.setenv(variable, value)
            with pytest.raises(output.OutputPublicationRefused):
                bridge.prepare(context, root, _test_api=api, _test_transport=transport)
        assert not root.exists() and not api.calls and transport.calls == 0
    source_state["head"] = "e" * 40
    with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_source_changed$"):
        bridge.prepare(context, root, _test_api=api, _test_transport=transport)
    source_state["head"] = SOURCE
    # Expected-pin mutation invalidates the compiled context before source reads.
    for key in fixed.READER:
        with monkeypatch.context() as scoped:
            scoped.setattr(fixed, "READER", {**fixed.READER, key: "0" * 64})
            with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_context_changed$"):
                bridge.prepare(context, root, _test_api=api, _test_transport=transport)
        assert not root.exists() and not api.calls and transport.calls == 0

    # Keep canonical expectations intact and corrupt only actual source bytes.
    real_bytes = output._bytes
    for name in fixed.READER_FILES.values():
        target, corrupted = bridge.ROOT / "batch-runner" / name, []

        def corrupt_reader_bytes(path, **arguments):
            data = real_bytes(path, **arguments)
            if Path(path) == target:
                corrupted.append(Path(path))
                return data + b"\n# synthetic reader-integrity corruption\n"
            return data

        with monkeypatch.context() as scoped:
            scoped.setattr(output, "_bytes", corrupt_reader_bytes)
            with pytest.raises(output.OutputPublicationRefused, match="^reviewed_retention_reader_required$"):
                bridge.prepare(context, root, _test_api=api, _test_transport=transport)
        assert corrupted == [target]
        assert not root.exists() and not api.calls and transport.calls == 0

    real_materialize, uploads = bridge._materialize_bound_codex_grading_input, []

    def materialize(run, **arguments):
        upload = arguments["source_upload"]
        staged = {path.relative_to(upload).as_posix(): path.read_bytes()
                  for path in upload.rglob("*") if path.is_file()}
        declared = {item["path"]: {key: item[key] for key in ("size", "sha256")}
                    for item in record["files"] if item["path"].startswith("deliverable_files/")}
        assert {name: pilot._identity(data) for name, data in staged.items()} == declared
        assert upload.stat().st_mode & 0o777 == 0o700 and bridge.reader.LEDGER not in staged
        assert arguments["inference_results"] == root / "retained" / bridge.reader.RESULT
        uploads.append(upload)
        return real_materialize(run, **arguments)

    monkeypatch.setattr(bridge, "_materialize_bound_codex_grading_input", materialize)
    prepared = bridge.prepare(context, root, _test_api=api, _test_transport=transport)
    assert prepared == bridge._ready(context, root) and prepared["judge_ready"] is True
    assert prepared["format"] == fixed.PREPARATION_FORMAT
    assert prepared["entry"]["grader_source_hash"] == fixed.GRADER_SHA256
    assert uploads == [root / "original-upload"] and api.events == [] and transport.calls == 0
    leaves = _filename_leaves(prepared["entry"]["grade_path"], context.cell["task_id"])
    leaf_bytes = {name: len(value.encode("utf-8")) for name, value in leaves.items()}
    assert leaf_bytes == {"grade": 213, "jsonl_ledger": 226, "sqlite": 228, "sqlite_wal": 232,
                          "sqlite_shm": 232, "sqlite_journal": 236, "checkpoint": 251, "checkpoint_tmp": 255}
    name_max = os.pathconf(root / "source", "PC_NAME_MAX")
    assert all(size <= name_max for size in leaf_bytes.values())
    checkpoint_root = tmp_path / "filename-checkpoint"
    checkpoint_root.mkdir(mode=0o700)
    checkpoint_name_max = os.pathconf(checkpoint_root, "PC_NAME_MAX")
    assert all(size <= checkpoint_name_max for size in leaf_bytes.values())
    partial = checkpoint_root / leaves["grade"]
    rubric_ids = prepared["rubric"]["rubric_item_ids"]
    progress = build_progress(task_id=context.cell["task_id"], grader_source_hash=fixed.GRADER_SHA256,
                              rubric_item_ids=rubric_ids, draft=TaskProgressDraft())
    checkpoint = write_checkpoint(partial, progress)
    assert checkpoint.name == leaves["checkpoint"] and checkpoint.is_file()
    assert not checkpoint.with_suffix(".json.tmp").exists()
    readback = load_checkpoint(partial, task_id=context.cell["task_id"],
                              grader_source_hash=fixed.GRADER_SHA256, rubric_item_ids=rubric_ids)
    assert readback is not None and readback.to_dict() == progress.to_dict()
    assert (root / "source" / context.run.experiment_config_path).is_file()
    assert not (root / "source/batch-runner/experiments/retention/task4-keep-r2.yaml").exists()
    derived = json.loads((root / "inputs" / context.run.inference_results_path).read_bytes())
    assert derived["result_fingerprint"] == inference_result_fingerprint(derived)
    assert derived["result_fingerprint"] != record["result"]["result_fingerprint"]
    assert derived["source_revision"] == record["output_commit"]
    assert derived["source_identity_document_sha256"] == prepared["identity_sha256"]
    assert prepared["materialization"]["materialized_result"]["result_fingerprint"] == derived["result_fingerprint"]
    assert not any(name == "commit" for name, _ in api.calls)
    with pytest.raises((output.OutputPublicationRefused, FileExistsError)):
        bridge.prepare(context, root, _test_api=api, _test_transport=transport)

    for key, value in (("producer_source_sha", "0" * 40), ("request_sha256", "0" * 64),
            ("cell_id", bridge.CELL), ("ordinal", True), ("terminal_commit", "0" * 40),
            ("claim_commit", "0" * 40), ("output_commit", "0" * 40),
            ("recorded_provider_run_id", "1"), ("recorded_provider_job_id", True),
            ("expected_execution_job_id", 110323708382),
            ("result", {**record["result"], "result_fingerprint": "0" * 64})):
        with pytest.raises(output.OutputPublicationRefused, match="^fixed_retention_result_mismatch$"):
            bridge._intake({**record, key: value}, root / "retained", selector=fixed.SELECTOR)
    for key, value in (("predecessor", {}), ("cleanup_confirmed", 1), ("status", "failed"),
            ("grade", 0), ("writer_acknowledgment", "acknowledged"), ("reader", {}),
            ("consumer_readback_required", False), ("supplied_request_binding", {})):
        with pytest.raises(output.OutputPublicationRefused, match="^retention_intake_boundary_mismatch$"):
            bridge._intake({**record, key: value}, root / "retained", selector=fixed.SELECTOR)
    marker = root / "retained" / fixed.MARKER
    marker_bytes = marker.read_bytes()
    marker.write_bytes(marker_bytes + b" ")
    with pytest.raises(output.OutputPublicationRefused, match="^retention_intake_marker_changed$"):
        bridge._ready(context, root)
    marker.write_bytes(marker_bytes)
    result_path = root / "retained" / bridge.reader.RESULT
    result_bytes = result_path.read_bytes()
    result_path.write_bytes(result_bytes + b" ")
    with pytest.raises(output.OutputPublicationRefused, match="^payload_identity_mismatch$"):
        bridge._ready(context, root)
    result_path.write_bytes(result_bytes)
    preparation_path = root / "prepared.json"
    for key, value in (("materialization", {**prepared["materialization"], "materialized_result": record["result"]}),
            ("identity_sha256", "0" * 64), ("entry", {**prepared["entry"], "grader_source_hash": "0" * 64})):
        preparation_path.write_bytes(retained._encoded({**prepared, key: value}))
        with pytest.raises(output.OutputPublicationRefused):
            bridge._ready(context, root)
        preparation_path.write_bytes(retained._encoded(prepared))
    reference = next(name for name in prepared["rubric"]["files"] if name.endswith("synthetic.txt"))
    reference_path = root / "source" / reference
    reference_bytes = reference_path.read_bytes()
    reference_path.write_bytes(reference_bytes + b"changed")
    with pytest.raises(output.OutputPublicationRefused, match="^original_reference_bytes_changed$"):
        bridge._ready(context, root)
    reference_path.write_bytes(reference_bytes)

    # The old route cannot consume this preparation or replay its result.
    with monkeypatch.context() as scoped:
        _environment(scoped, bridge.SELECTOR)
        old = bridge.compile_request(SOURCE)
        for action in (bridge.claim, bridge.judge):
            with pytest.raises(output.OutputPublicationRefused, match="^bound_retention_grade_preparation_required$"):
                action(old, root)
    assert transport.calls == 0 and api.events == []

    # Rebind only mutated synthetic byte identities to reach parent semantics.
    parent_raw = api.trees[parent_reader.TERMINAL][bridge.TERMINAL_PATH]
    parent = json.loads(parent_raw)
    changes = [(("binding", "source_sha"), "e" * 40), (("binding", "github_run"), {**parent_reader.WRITER_RUN, "id": "9"}),
        (("binding", "cell_id"), fixed.CELL), (("binding", "fixed_evidence_sha256"), "0" * 64),
        (("child", "cleanup_confirmed"), False), (("child", "exit_code"), True), (("outcome",), "failed")]
    for index, (keys, value) in enumerate(changes):
        changed = deepcopy(parent)
        target = changed if len(keys) == 1 else changed[keys[0]]
        target[keys[-1]] = value
        raw = retained._encoded(changed)
        with monkeypatch.context() as scoped:
            scoped.setattr(parent_reader, "TERMINAL_IDENTITY", pilot._identity(raw))
            scoped.setattr(fixed, "PARENT", {**fixed.PARENT, "terminal_identity": pilot._identity(raw)})
            api.trees[parent_reader.TERMINAL][bridge.TERMINAL_PATH] = raw
            with retained._session(api) as (client, token, deadline):
                with pytest.raises(output.OutputPublicationRefused):
                    bridge._parent(client, api.repo, grade._cache(tmp_path, f"bad-parent-{index}"), token, deadline,
                                   selector=fixed.SELECTOR)
        api.trees[parent_reader.TERMINAL][bridge.TERMINAL_PATH] = parent_raw
    writer = api.writers[parent_reader.TERMINAL][bridge.CLAIM_PATH]
    api.writers[parent_reader.TERMINAL][bridge.CLAIM_PATH] = parent_reader.TERMINAL
    with retained._session(api) as (client, token, deadline):
        with pytest.raises(output.OutputPublicationRefused, match="^remote_output_history_mismatch$"):
            bridge._parent(client, api.repo, grade._cache(tmp_path, "bad-parent-history"), token, deadline,
                           selector=fixed.SELECTOR)
    api.writers[parent_reader.TERMINAL][bridge.CLAIM_PATH] = writer
    assert api.events == []

    # Each branch refusal owns a separate unattempted synthetic preparation.
    for name in ("drift", "second-read-drift", "duplicate", "cas-race", "lost-claim"):
        refused_root = tmp_path / name
        shutil.copytree(root, refused_root)
        isolated = deepcopy(api)
        isolated.branches[grade.BRANCH] = retained.BOOTSTRAP if name == "drift" else fixed.PARENT["revision"]
        isolated.drift_after_parent = name == "second-read-drift"
        isolated.move_before_commit = name == "cas-race"
        isolated.lost = "grade_claim" if name == "lost-claim" else None
        if name == "duplicate":
            isolated.trees[fixed.PARENT["revision"]][fixed.CLAIM_PATH] = b"{}\n"
            isolated.writers[fixed.PARENT["revision"]][fixed.CLAIM_PATH] = fixed.PARENT["revision"]
        refused = bridge.claim(context, refused_root, _test_api=isolated)
        assert refused["outcome"] == "unresolved"
        assert refused["reason"] == {"drift": "fixed_grading_parent_drift", "second-read-drift": "fixed_grading_parent_drift",
            "duplicate": "retention_result_already_claimed_for_grading", "cas-race": "hf_http_failed",
            "lost-claim": "hf_transport_failed"}[name]
        with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_claim_already_reserved$"):
            bridge.claim(context, refused_root, _test_api=isolated)
        with pytest.raises(output.OutputPublicationRefused, match="^acknowledged_retention_grade_admission_required$"):
            bridge.judge(context, refused_root, _test_transport=transport)
        assert transport.calls == 0
        assert isolated.events == (["grade_claim"] if name in {"cas-race", "lost-claim"} else [])

    admission = bridge.claim(context, root, _test_api=api)
    assert admission["outcome"] == "acknowledged" and api.events == ["grade_claim"]
    assert admission["claim"]["expected_parent"] == fixed.PARENT["revision"]
    assert admission == bridge._admission(context, root, prepared)
    with pytest.raises(output.OutputPublicationRefused, match="^retention_grade_claim_already_reserved$"):
        bridge.claim(context, root, _test_api=api)
    # A separate admitted fixture exercises the unchanged owned-clock contract.
    timeout_root = tmp_path / "timed-out-child"
    shutil.copytree(root, timeout_root)
    timeout_case = SimpleNamespace(root=timeout_root, context=context, api=deepcopy(api))

    class TimedJudge(OwnedJudge):
        def process(self, command, **options):
            super().process(command, **options)
            raise subprocess.TimeoutExpired(command, grade.CHILD_SECONDS)

    timed = TimedJudge(timeout_case)
    timed.mode = "missing"
    timed_receipt = bridge.judge(context, timeout_root, _test_transport=timed)
    assert timed_receipt == {"entry_invoked": True, "exit_code": None, "timed_out": True, "cleanup_confirmed": True}
    with pytest.raises((output.OutputPublicationRefused, FileExistsError)):
        bridge.judge(context, timeout_root, _test_transport=timed)
    assert timed.calls == 1
    child = bridge.judge(context, root, _test_transport=transport)
    assert child == {"entry_invoked": True, "exit_code": 0, "timed_out": False, "cleanup_confirmed": True}
    assert transport.calls == 1 and api.events == ["grade_claim", "judge"]
    with pytest.raises((output.OutputPublicationRefused, FileExistsError)):
        bridge.judge(context, root, _test_transport=transport)
    child_path = root / "judge-receipt.json"
    child_path.write_bytes(retained._encoded({**child, "cleanup_confirmed": False}))
    with pytest.raises(output.OutputPublicationRefused, match="^grade_cleanup_unconfirmed$"):
        bridge.publish(context, root, _test_api=api)
    child_path.write_bytes(retained._encoded(child))
    grade_path = root / "source" / prepared["entry"]["grade_path"]
    grade_bytes = grade_path.read_bytes()
    payload = json.loads(grade_bytes)
    for changed in ({**payload, "grader_source_hash": "0" * 64},
                    {**payload, "cost_ledger": {**payload["cost_ledger"], "sha256": "0" * 64}}):
        grade_path.write_bytes(retained._encoded(changed))
        with pytest.raises(ValueError):
            bridge.publish(context, root, _test_api=api)
        assert not (root / "publication-reserved.json").exists()
    grade_path.write_bytes(grade_bytes)
    # Independent transport outcome fixtures, not repeated publication to one server.
    acknowledged_root = tmp_path / "acknowledged-publication"
    shutil.copytree(root, acknowledged_root)
    acknowledged_api = deepcopy(api)
    acknowledged = bridge.publish(context, acknowledged_root, _test_api=acknowledged_api)
    assert acknowledged["outcome"] == "acknowledged" and acknowledged["grading_state"] == "graded"
    with pytest.raises((output.OutputPublicationRefused, FileExistsError)):
        bridge.publish(context, acknowledged_root, _test_api=acknowledged_api)
    assert acknowledged_api.events == ["grade_claim", "judge", "grade_output"]
    api.lost = "grade_output"
    publication = bridge.publish(context, root, _test_api=api)
    assert publication["outcome"] == "unresolved" and publication["reason"] == "hf_transport_failed"
    writer_receipt = (root / "publication-receipt.json").read_bytes()
    ambiguous_root = tmp_path / "ambiguous-publication"
    shutil.copytree(root, ambiguous_root)
    ambiguous_api = deepcopy(api)
    ambiguous_api.writers[ambiguous_api.branches[grade.BRANCH]][fixed.CLAIM_PATH] = ambiguous_api.branches[grade.BRANCH]
    refused = bridge.reconcile(context, ambiguous_root, _test_api=ambiguous_api)
    assert refused["outcome"] == "unresolved" and refused["reason"] == "remote_output_history_mismatch"
    assert ambiguous_api.events == api.events
    assert (ambiguous_root / "publication-receipt.json").read_bytes() == writer_receipt
    observed = bridge.reconcile(context, root, _test_api=api)
    assert observed["outcome"] == "verified_server_state" and observed["writer_acknowledgment"] == "not_established"
    assert (root / "publication-receipt.json").read_bytes() == writer_receipt
    with pytest.raises((output.OutputPublicationRefused, FileExistsError)):
        bridge.publish(context, root, _test_api=api)
    assert transport.calls == 1 and api.events == ["grade_claim", "judge", "grade_output"]
    api.assert_main_unchanged()
    assert all(revision == grade.BRANCH for name, revision in api.calls if name == "commit")
    written = set(api.trees[api.branches[grade.BRANCH]]) - set(api.trees[fixed.PARENT["revision"]])
    assert written and all(name.startswith(fixed.PREFIX + "/") for name in written)
    assert all(not any(word in name for word in ("sqlite", "transcript", "judge.stdout", "judge.stderr", "prompt"))
               for name in written)
    assert bridge.fixed_evidence_sha256() == FIRST_EVIDENCE
    with pytest.raises(AssertionError):
        subprocess.run(["python", "-c", "pass"])
    assert not capsys.readouterr().out
    print("OFFLINE keep/r2: marker/payload/materializer/rubric, two-control grade parent, serial CAS, one owned judge, no replay, read-only lost-ack reconciliation; synthetic only")
    print("OFFLINE keep/r2 filenames: " + json.dumps({"leaf_bytes": leaf_bytes, "name_max": name_max,
        "checkpoint_name_max": checkpoint_name_max, "checkpoint_write_readback": True}, sort_keys=True))


def test_keep_r2_fixed_grade_workflow_approval_and_ledger_are_closed(tmp_path, monkeypatch, capsys):
    _environment(monkeypatch, bridge.SELECTOR)
    first._workflow_contract(tmp_path, monkeypatch)  # Existing pure assertions, not the old integration.
    workflow = yaml.safe_load((bridge.ROOT / grade.WORKFLOW).read_bytes())
    assert "retention/task4-keep-r2" not in (bridge.ROOT / grade.WORKFLOW).read_text()
    plan, approval, live = (workflow["jobs"][name] for name in ("pilot-plan", "pilot-approve-paid", "pilot-live"))
    assert "inputs.experiment_yaml != 'retention/keep-r2'" in plan["if"]
    for job in (approval, live):
        assert "|| inputs.experiment_yaml == 'retention/keep-r2'" in job["if"]
        assert "startsWith(inputs.experiment_yaml, 'retention/')" not in job["if"]
    assert "inputs.experiment_yaml == 'retention/keep-r2' && '" + fixed.RESULT["producer_source_sha"] + "'" in live["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
    publication = next(step for step in live["steps"] if "--phase publish" in step.get("run", ""))
    assert '"$GRADE_SELECTOR" == "retention/keep-r2"' in publication["run"]
    assert publication["run"].count("--phase reconcile") == 1
    assert 'exit "$publication_status"' in publication["run"]
    assert "--phase judge" not in publication["run"] and "--phase claim" not in publication["run"]
    config = json.loads(bridge.compile_request(SOURCE, selector=fixed.SELECTOR).run.grader_config_json)
    assert config["rubric"]["revision"] == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    assert config["judge"]["model"] == "gpt-5.6-sol" and config["judge"]["reasoning"]["effort"] == "max"
    assert grade.CHILD_SECONDS == 242 * 60 and live["timeout-minutes"] == 300
    assert bridge.fixed_evidence_sha256(fixed.SELECTOR) == EVIDENCE
    _environment(monkeypatch)
    script = approval["steps"][0]["run"].removeprefix("python3 - <<'PY'\n").removesuffix("PY\n")
    destination = tmp_path / "keep-r2-approval"

    def digest(inputs):
        with monkeypatch.context() as scoped:
            scoped.setenv("PILOT_GRADE_INPUTS_JSON", json.dumps(inputs))
            scoped.setenv("GITHUB_OUTPUT", str(destination))
            scoped.setenv("GITHUB_JOB", "pilot-approve-paid")
            exec(compile(script, "<closed-keep-r2-approval>", "exec"), {})
        return destination.read_text().splitlines()[-1].removeprefix("request_sha256=")

    inputs = bridge._fixed_inputs(fixed.SELECTOR)
    expected = pilot._digest(bridge.approval_request(SOURCE, RUN, selector=fixed.SELECTOR))
    assert digest(inputs) == expected
    assert digest({**inputs, "run_ordinal": "1", "tasks_limit": "0"}) == expected
    for key, value in (("inference_revision", bridge.RESULT["terminal_commit"]), ("grading_config", "other.yaml"),
            ("force", True), ("paid_approval", False), ("dry_run", True), ("resume", True),
            ("resume_chunk", 1), ("tasks", "other"), ("tasks_limit", 1), ("shard_count", 2),
            ("shard_index", 1), ("run_ordinal", 2), ("run_ordinal", True)):
        before = destination.read_bytes()
        with pytest.raises(SystemExit, match="^(fixed_retention_grade_inputs_refused|pilot_grade_approval_inputs_refused)$"):
            digest({**inputs, key: value})
        assert destination.read_bytes() == before

    context = bridge.compile_request(SOURCE, selector=fixed.SELECTOR)
    assert bridge._authority(context) == RUN
    for changed in (SimpleNamespace(**context.__dict__), replace(context, cell={**context.cell, "index": 0}),
            replace(context, selector=bridge.SELECTOR)):
        with pytest.raises(output.OutputPublicationRefused):
            bridge._authority(changed)
    args = ["--reviewed-source-sha", SOURCE, "--root", str(tmp_path / "inert")]
    with monkeypatch.context() as scoped:
        scoped.delenv("GITHUB_ACTIONS")
        for selector in (bridge.SELECTOR, fixed.SELECTOR):
            assert grade.main(args + ["--selector", selector]) == 0
            planned = _capture(capsys, tmp_path)
            assert planned["outcome"] == "plan_only" and planned["selector"] == selector
            assert planned["commands"] == [] and planned["grade"] is None and not planned["judge_ready"]
        for selector in ("retention/task4-keep-r2", "retention/keep-r2-extra",
                         "retention/task4-fresh-r2", "retention/task5-keep-r1"):
            assert grade.main(args + ["--selector", selector]) == 2
            assert _capture(capsys, tmp_path)["reason"] == "fixed_retention_grade_selector_required"
        for extra in (("--phase", "record-ungraded"), ("--phase", "setup"), ("--resume",),
                      ("--terminal-revision", bridge.RESULT["terminal_commit"])):
            assert bridge.main(args + ["--selector", fixed.SELECTOR, *extra]) == 2
            assert _capture(capsys, tmp_path)["outcome"] == "refused"
    assert not (tmp_path / "inert").exists()
    assert reader._fixed_binding(reader.FRESH_R1) is reader.FRESH_R1
    assert reader._fixed_binding(reader.FRESH_R2) is reader.FRESH_R2
    assert reader._producer(reader.KEEP_R2).PREDECESSOR["terminal_commit"] == "1d5133590911f3704fc2a65279d4b64bee77c1d6"

    for selector, binding_type in ((bridge.SELECTOR, output.RetentionFirstCellLedgerBinding),
                                    (fixed.SELECTOR, output.RetentionKeepR2LedgerBinding)):
        cell = bridge.compile_request(SOURCE, selector=selector).cell
        binding = binding_type("a" * 16, "b" * 64)
        run_id = selector + "|" + binding.config_hash + "|" + binding.grader_source_hash
        options = {"grading_run_id": run_id, "retention_first_cell_binding": binding}
        data = base._ledger(run_id, cell["task_id"], "grading")
        assert output._ledger(data, cell, **options) is None
        other_type = output.RetentionKeepR2LedgerBinding if selector == bridge.SELECTOR else output.RetentionFirstCellLedgerBinding
        for wrong in (other_type(binding.config_hash, binding.grader_source_hash), SimpleNamespace(**binding.__dict__)):
            with pytest.raises(output.OutputPublicationRefused, match="^fixed_retention_grading_ledger_binding_required$"):
                output._ledger(data, cell, grading_run_id=run_id, retention_first_cell_binding=wrong)
        for field, value in (("index", True), ("cell_id", "other"), ("run_id", cell["run_id"] + "-other"),
                ("control", {**cell["control"], "retention_bundle": "fresh"}),
                ("control", {**cell["control"], "repetition": True})):
            with pytest.raises(output.OutputPublicationRefused, match="^fixed_retention_grading_ledger_binding_required$"):
                output._ledger(data, {**cell, field: value}, **options)
        for bad_run in (None, run_id + "|run2", run_id.replace(selector, "pilot/cell-03"),
                        run_id.replace(selector, "retention/task4-keep-r2")):
            with pytest.raises(output.OutputPublicationRefused, match="^fixed_retention_grading_ledger_run_required$"):
                output._ledger(data, cell, grading_run_id=bad_run, retention_first_cell_binding=binding)
        row = json.loads(data)
        for key, value in (("task_id", "other"), ("input_tokens", True), ("model_cost_usd", "NaN"),
                           ("note", "PRIVATE/path?token=secret"), ("extra", "private")):
            with pytest.raises(output.OutputPublicationRefused):
                output._ledger(retained._encoded({**row, key: value}), cell, **options)
        with pytest.raises(output.OutputPublicationRefused, match="^ledger_duplicate_or_missing_identity$"):
            output._ledger(data + data, cell, **options)
        with pytest.raises(output.OutputPublicationRefused, match="^fixed_grading_ledger_run_required$"):
            output._ledger(data, cell, grading_run_id=run_id)
    assert bridge.fixed_evidence_sha256() == FIRST_EVIDENCE
    assert not capsys.readouterr().out
    print("OFFLINE keep/r2 routing: fixed same-run approval, unchanged old defaults, exact typed ledger binding, secret/job/time boundaries; no live effects")
