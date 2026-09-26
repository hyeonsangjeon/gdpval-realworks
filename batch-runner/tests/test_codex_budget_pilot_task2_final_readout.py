"""Finite offline readout proof, not a read or reconstruction of live grades.

Reuse genuine inference/Step8/ledger/publication fixtures. Only synthetic commit
addresses and generated completion digests replace recorded fixture identities.
After publication, every external mutation, auth and judge boundary is closed.
"""

import copy
from functools import lru_cache
import hashlib
import json
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from . import test_codex_budget_pilot_b1_grading as b1
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as chain
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — forbid all live boundaries

PREFIX = chain.PREFIX
OBSERVER = "d" * 40
PRIVATE = "PRIVATE https://private.invalid/path?token=PRIVATE"


@pytest.fixture(scope="module")
def compilations():
    return {source: pilot.compile_pilot(ci.CAMPAIGN, source) for source in (
        grading.RETAINED_PRODUCER_SOURCE, readout.WRITER_SOURCE, grading.B1_PRODUCER_SOURCE,
        readout.B1_WRITER_SOURCE, readout.TASK2_WRITER_SOURCE, OBSERVER)}


@pytest.fixture(scope="module")
def compiled_cells():
    return lru_cache(maxsize=32)(adapter.compile_cell_grading_plan)


@pytest.fixture
def case(tmp_path, monkeypatch, capsys, compilations, compiled_cells):
    return chain.case.__wrapped__(tmp_path, monkeypatch, capsys, compilations, compiled_cells)


def _selected(case, suffix, tmp_path, monkeypatch):
    cell = PREFIX + suffix
    request = grading.TASK2_RETAINED[cell][1]
    current = SimpleNamespace(context=readout._writer_context(request), request=request,
        api=case.api, workflow=case.workflow, root=tmp_path / (suffix + "-grade"))
    current.transport = base.Child(current)
    monkeypatch.setattr(base, "OUTPUT", case.inferences[cell][1])
    chain._authorize(current, tmp_path, monkeypatch, readout.TASK2_GRADE_RUNS[cell])
    return current


@pytest.mark.parametrize("suffix,scenario", [
    ("C_r1", "graded"), ("C_r2", "graded"), ("C_r1", "partial"), ("C_r2", "failed"),
    ("C_r1", "ungraded"), ("C_r2", "missing_ledger"), ("C_r1", "partial_cost"),
    ("C_r2", "advanced"), ("C_r1", "writer"), ("C_r2", "run"), ("C_r1", "source"),
    ("C_r2", "inference_run"), ("C_r1", "completion"), ("C_r2", "receipt"),
    ("C_r1", "hash"), ("C_r2", "bytes"), ("C_r1", "raw_judge"),
    ("C_r2", "private_cost_reason"), ("C_r1", "path"), ("C_r2", "cleanup"),
    ("C_r1", "claim"), ("C_r2", "outcome"), ("C_r1", "previous_grade_pin"),
    ("C_r1", "previous_inference_pin"), ("C_r2", "previous_run"),
    ("C_r2", "previous_source"), ("C_r2", "previous_hash"), ("C_r2", "previous_carried"),
    ("C_r2", "previous_inference_link"), ("C_r2", "skipped_predecessor"),
    ("C_r1", "ref"), ("C_r2", "observer"), ("C_r1", "absent"), ("C_r1", "plan"),
    ("B_r2", "unconfigured_plan"), ("B_r2", "unconfigured_readout"),
    ("A_r2", "unconfigured_plan"), ("A_r2", "unconfigured_readout"),
])
def test_task2_final_grade_readout(request, tmp_path, monkeypatch, capsys, suffix, scenario):
    assert readout.TASK2_WRITER_SOURCE == "a5e5d2589caff21309f0a1c21bb7d9d333ad47c6"
    assert readout.TASK2_GRADE_RUNS == {PREFIX + cell: run for cell, run in {
        "C_r1": "36209654516", "C_r2": "36211281528", "B_r2": None, "A_r2": None}.items()}
    assert readout.B1_PREDECESSOR_GRADE == "887c2373d456efc1eabf29a8bf3d3d7de12e43fe"
    assert readout.B1_PREDECESSOR_INFERENCE == "0a9a8b3263f41d86d723f84a723c9b467f04dea5"
    assert grading.TASK2_RETAINED == {PREFIX + cell: values for cell, values in chain.RECORDED.items()}

    def forbidden(*args, **kwargs):
        pytest.fail("readout crossed a forbidden auth, preparation, mutation or judge boundary")

    if scenario.startswith("unconfigured_"):
        for target, name in ((retained, "_session"), (grading, "_root"), (pilot, "compile_pilot")):
            monkeypatch.setattr(target, name, forbidden)
        code = grading.main(["--selector", readout.SELECTOR, "--reviewed-source-sha", OBSERVER,
            "--terminal-revision", grading.TASK2_RETAINED[PREFIX + suffix][1],
            "--phase", scenario.removeprefix("unconfigured_"), "--root", str(tmp_path / "PRIVATE-unconfigured")])
        capture = capsys.readouterr()
        assert capture.out == "" and "PRIVATE" not in capture.err
        public = json.loads(capture.err)
        assert code == 2 and public["outcome"] == "refused" and public["stage"] == "plan"
        assert public["reason"] == "grade_readout_writer_unconfigured"
        assert public["cell_id"] == PREFIX + suffix and public["grade_writer_run"] is None
        assert public["grade_writer_source_sha"] == readout.TASK2_WRITER_SOURCE
        assert public["inference_producer_source_sha"] == grading.B1_PRODUCER_SOURCE
        assert public["remote_mutation_possible"] is public["judge_entry_requested"] is False
        assert not (tmp_path / "PRIVATE-unconfigured").exists()
        return

    state = request.getfixturevalue("case")
    api = state.api
    previous_revision, previous_path, previous = chain._publish(
        state, capsys, tmp_path / "b1-writer", monkeypatch)
    # Only synthetic identities are substituted; no historical bytes are recreated.
    monkeypatch.setattr(readout, "B1_PREDECESSOR_GRADE", previous_revision)
    monkeypatch.setattr(readout, "B1_PREDECESSOR_INFERENCE", b1.B1_TERMINAL)
    if suffix == "C_r2":
        c1 = _selected(state, "C_r1", tmp_path, monkeypatch)
        previous_revision, previous_path, previous = chain._publish(
            c1, capsys, tmp_path / "c1-writer", monkeypatch)
    current = _selected(state, suffix, tmp_path, monkeypatch)
    revision, terminal_path, terminal = chain._publish(current, capsys, tmp_path / "selected-writer", monkeypatch, scenario)
    prepared = retained._read(current.root / "prepared.json")
    assert prepared["entry"]["grader_source_hash"] == readout.TASK2_GRADER_SOURCE_HASH
    assert hashlib.sha256(current.context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert terminal["binding"]["controller_source_sha"] == readout.TASK2_WRITER_SOURCE
    assert terminal["binding"]["github_run"] == readout._writer_run(current.context)
    assert current.context.run.grader_config_json == state.context.run.grader_config_json
    assert current.context.plan["source_pins"] == state.context.plan["source_pins"]
    assert len(current.context.plan["order"]) == 30 and ci.HOST_POLICY["sdk"] == "0.147.0"
    assert pilot.TOTAL_SECONDS == 10800
    claim_path = grading._paths(current.context.cell)[0]
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
    assert claim["predecessor"] == {"cell_id": previous["binding"]["cell_id"],
        "revision": previous_revision, **pilot._identity(retained._encoded(previous))}
    record = next((row for row in terminal["files"] if row["role"] == "grade_result"), None)

    if scenario == "advanced":
        api.seed("f" * 40, revision, {"unrelated/PRIVATE": b"PRIVATE unrelated object"})
        api.branches[grading.BRANCH] = "f" * 40
    elif scenario in {"writer", "source", "hash", "receipt"}:
        key = {"writer": "controller_source_sha", "source": "source_sha", "hash": "grader_source_hash",
               "receipt": "publication_receipt_sha256"}[scenario]
        terminal["binding"][key] = "9" * (40 if scenario in {"writer", "source"} else 64)
    elif scenario == "run":
        terminal["binding"]["github_run"]["id"] = "36211281529"
        terminal["binding"]["approval_request_sha256"] = grading._context_approval(current.context, terminal["binding"]["github_run"])
    elif scenario in {"completion", "inference_run", "previous_inference_link"}:
        inference_revision, output_revision = state.inferences[current.context.cell["cell_id"]]
        input_claim_path, input_terminal_path, _ = retained._paths(current.context.cell)
        input_terminal = pilot._json_object(api.trees[inference_revision][input_terminal_path])
        input_claim = pilot._json_object(api.trees[input_terminal["claim_commit"]][input_claim_path])
        if scenario == "completion":
            input_terminal["completion"]["child_invocations"] = 2
        else:
            if scenario == "inference_run":
                input_claim["binding"]["github_run"]["id"] = "36198090627"
            else:
                input_claim["predecessor"]["manifest_sha256"] = "9" * 64
            for commit in (input_terminal["claim_commit"], output_revision, inference_revision):
                api.trees[commit][input_claim_path] = retained._encoded(input_claim)
            input_terminal["claim_identity"] = pilot._identity(retained._encoded(input_claim))
        api.trees[inference_revision][input_terminal_path] = retained._encoded(input_terminal)
        terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(retained._encoded(input_terminal))["sha256"]
        claim["binding"] = copy.deepcopy(terminal["binding"])
    elif scenario == "bytes":
        api.trees[revision][record["path"]] += b"PRIVATE"
    elif scenario in {"raw_judge", "private_cost_reason"}:
        payload = pilot._json_object(api.trees[revision][record["path"]])
        if scenario == "raw_judge":
            payload["tasks"][0]["items"][0]["judge_raw_response"] = PRIVATE
        else:
            payload["tasks"][0]["grading_cost"]["missing_reasons"] = [PRIVATE]
        data = base._json(payload)
        api.trees[revision][record["path"]] = data
        record.update(retained._object(record["path"], data))
    elif scenario == "path":
        record["path"] = "PRIVATE/foreign.json"
    elif scenario == "cleanup":
        terminal["child"]["cleanup_confirmed"] = False
    elif scenario == "claim":
        terminal["claim_identity"]["sha256"] = "9" * 64
    elif scenario == "outcome":
        terminal["outcome"] = "failed"
    elif scenario == "previous_grade_pin":
        monkeypatch.setattr(readout, "B1_PREDECESSOR_GRADE", "9" * 40)
    elif scenario == "previous_inference_pin":
        monkeypatch.setattr(readout, "B1_PREDECESSOR_INFERENCE", "9" * 40)
    elif scenario in {"previous_run", "previous_source"}:
        if scenario == "previous_run":
            previous["binding"]["github_run"]["id"] = "36209654517"
        else:
            previous["binding"]["controller_source_sha"] = OBSERVER
        api.trees[previous_revision][previous_path] = retained._encoded(previous)
    elif scenario == "previous_hash":
        claim["predecessor"]["sha256"] = "9" * 64
    elif scenario == "previous_carried":
        api.writers[terminal["claim_commit"]][previous_path] = terminal["claim_commit"]
    elif scenario == "skipped_predecessor":
        claim["predecessor"]["cell_id"] = grading.B1_CELL
    elif scenario == "ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    if scenario in {"completion", "inference_run", "previous_inference_link", "previous_hash", "skipped_predecessor"}:
        data = retained._encoded(claim)
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][claim_path] = data
        terminal["claim_identity"] = pilot._identity(data)
    api.trees[revision][terminal_path] = retained._encoded(terminal)
    if scenario == "absent":
        api.trees[revision].pop(terminal_path)

    for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "_entry_contract", "_ready"):
        monkeypatch.setattr(grading, name, forbidden)
    for name in ("create_commit", "create_branch"):
        monkeypatch.setattr(api, name, forbidden)
    monkeypatch.setattr(output, "_hf_client", forbidden)
    readers = []
    refused_checks = []
    original_require = readout.require

    def checked(condition, reason):
        if not condition:
            refused_checks.append(reason)
        original_require(condition, reason)

    monkeypatch.setattr(readout, "require", checked)
    original_init = readout._ReadOnlyGrade.__init__

    def remember(reader, *args, **kwargs):
        original_init(reader, *args, **kwargs)
        readers.append(reader)

    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    source = readout.TASK2_WRITER_SOURCE if scenario == "observer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
                       "GITHUB_RUN_ID": "900020", "PILOT_GRADE_PAID_APPROVAL": "false"}.items():
        monkeypatch.setenv(key, value)
    for key in ("PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256"):
        monkeypatch.delenv(key, raising=False)
    phase = "plan" if scenario == "plan" else "readout"
    if phase == "plan":
        writer._workflow_contract()
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        monkeypatch.setattr(retained, "_session", forbidden)
    api.calls.clear()
    api.reads.clear()
    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches, api.events))
    code = grading.main(["--selector", readout.SELECTOR, "--reviewed-source-sha", source,
        "--terminal-revision", current.request, "--root", str(tmp_path / "readout"), "--phase", phase],
        _test_api=api, _test_transport=SimpleNamespace(require_source=lambda plan, parent:
            None if plan["reviewed_source_sha"] == OBSERVER else forbidden()))
    capture = capsys.readouterr()
    text = capture.out + capture.err
    assert len(text.splitlines()) == 1
    for private in ("PRIVATE", base.TOKEN, api.repo, str(tmp_path), "https://", "Traceback"):
        assert private not in text
    public = json.loads(text)
    assert (api.trees, api.writers, api.parents, api.branches, api.events) == frozen
    assert public["remote_mutation_possible"] is public["judge_entry_requested"] is False
    assert public["invoice_complete"] is False and public["http_request_count"] is None
    accepted = {"graded", "partial", "failed", "ungraded", "missing_ledger", "partial_cost", "advanced"}
    if scenario == "plan":
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls
    elif scenario in accepted:
        assert code == 0 and public["outcome"] == "verified_retained_grade", public
        assert public["grade_state"] == (scenario if scenario in {"partial", "failed", "ungraded"} else "graded")
        assert public["grade_revision"] == revision and public["inference_terminal"] == state.inferences[PREFIX + suffix][0]
        assert public["inference_request_checksum"] == current.request
        assert public["grade_writer_source_sha"] == readout.TASK2_WRITER_SOURCE
        assert public["grade_writer_run"] == readout._writer_run(current.context)
        assert public["observer_source_sha"] == OBSERVER and public["inference_producer_source_sha"] == grading.B1_PRODUCER_SOURCE
        assert public["grader_source_hash"] == readout.TASK2_GRADER_SOURCE_HASH
        assert public["expected_tasks"] == 1 and public["proof_boundary"] == grading.PROOF
        if scenario in {"partial", "failed", "ungraded"}:
            assert public["score"] is None and public["scored_tasks"] == 0
        else:
            assert public["score"]["earned"] == public["score"]["possible"] == 4
            assert public["score"]["pct"] == 100 and public["coverage"]["rubric_items"] == 2
        if scenario in {"missing_ledger", "ungraded"}:
            assert public["ledger_state"] == "missing" and public["ledger_derived_cost"] is None
        elif scenario == "partial_cost":
            receipt = public["ledger_derived_cost"]
            assert receipt["known_cost_usd"] > 0 and receipt["model_calls"] == 2
            assert receipt["usage"] == {"input_tokens": 111, "output_tokens": 23,
                "cached_input_tokens": 17, "reasoning_tokens": 8, "audio_input_tokens": None, "audio_output_tokens": None}
            assert "call_reachability_unknown" in receipt["missing_reasons"]
            assert receipt["invoice_complete"] is False and receipt["http_request_count"] is None
        assert len(readers) == 2  # Exactly one predecessor; no recursive chain.
        assert ("metadata", grading.BRANCH) in api.calls
        assert sum(call == ("metadata", grading.BRANCH) for call in api.calls) == 1
        previous_cell = current.context.plan["cells"][current.context.plan["order"].index(PREFIX + suffix) - 1]
        controls = set()
        for cell in (current.context.cell, previous_cell):
            path, endpoint, prefix = retained._paths(cell)
            controls.update({path, endpoint, prefix + "/" + output.MANIFEST})
        downloads = {path for operation, _, path, _ in api.reads if operation == "download"}
        assert downloads == controls | {record["path"] for record in terminal["files"]} | {
            claim_path, terminal_path, grading._paths(previous_cell)[0], previous_path}
        for reader in readers:
            assert not hasattr(reader, "create_commit") and not hasattr(reader, "create_branch")
            with pytest.raises(output.OutputPublicationRefused):
                reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=previous_revision, filename=previous["files"][0]["path"],
                    cache_dir=tmp_path, force_download=True, local_files_only=False, etag_timeout=1)
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        expected_refusal = {
            "previous_grade_pin": "grade_readout_original_b1_required",
            "previous_inference_pin": "grade_readout_original_b1_required",
            "previous_hash": "grade_readout_predecessor_identity_refused",
            "previous_inference_link": "grade_readout_inference_predecessor_refused",
        }.get(scenario)
        if expected_refusal is not None:
            assert refused_checks == [expected_refusal]
    assert all(revision != retained.BRANCH for operation, revision in api.calls if operation == "metadata")
