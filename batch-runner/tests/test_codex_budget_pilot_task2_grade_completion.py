"""One finite task2 handoff selection; no live grades or historical payload recovery.

Existing genuine inference/grade writers, ledger export, compiler, materializer
and validators use synthetic external boundaries. Commit labels and generated
completion digests identify only this fixture, never reconstructed live bytes.
"""

import copy
from functools import lru_cache
import json
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from . import test_codex_budget_pilot_b1_grading as b1
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_grading_oidc as approval
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — all live boundaries forbidden

CONTROLLER, FOREIGN = "d" * 40, "e" * 40
PREFIX = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_"
RECORDED = {
    "B_r1": ("36192851762", "6a23d38158e81cd5ed184a05a7871545d140bb1d92dc1131326d96df29c236f8"),
    "C_r1": ("36195731407", "f3d1d3420b4dc23c018aa8b55ac1f4653a64e92b85eac50268e80aea55f2fbef"),
    "C_r2": ("36198090626", "1823893b4b4dfbce02b5b07d48f164cdd6228c3c38afd9608bb934c3e9bf417c"),
    "B_r2": ("36200320037", "b85346c5ee226bf1bfe2a34386394d4abea4617c408bedf2c3afe7016f9f904c"),
    "A_r2": ("36202190875", "d6d1309c2c81ef17ce18158bc9014ce962ce7dcd267f95f328b279050d4fd15e"),
}


@pytest.fixture(scope="module")
def compilations():
    return {source: pilot.compile_pilot(ci.CAMPAIGN, source) for source in (
        grading.RETAINED_PRODUCER_SOURCE, readout.WRITER_SOURCE, grading.B1_PRODUCER_SOURCE,
        readout.B1_WRITER_SOURCE, CONTROLLER, FOREIGN)}


@pytest.fixture(scope="module")
def compiled_cells():
    return lru_cache(maxsize=32)(adapter.compile_cell_grading_plan)


def _authorize(case, tmp_path, monkeypatch, run_id):
    context = case.context
    for key, value in {"GITHUB_SHA": context.controller_source_sha, "PILOT_WORKFLOW_SHA": context.controller_source_sha,
                       "GITHUB_RUN_ID": run_id, "GITHUB_JOB": "pilot-live", "GITHUB_RUN_ATTEMPT": "1",
                       "PILOT_GRADE_PAID_APPROVAL": "true", "PILOT_GRADE_DRY_RUN": "false",
                       "PILOT_GRADE_APPROVAL_RESULT": "success"}.items():
        monkeypatch.setenv(key, value)
    inputs = approval._inputs("pilot/" + context.cell["cell_id"], context.requested_terminal)
    inputs.pop("tasks")
    for name in ("tasks_limit", "resume_chunk", "shard_count", "shard_index", "run_ordinal"):
        inputs[name] = str(inputs[name])
    digest = approval._approved_digest(case.workflow, tmp_path, monkeypatch, inputs=inputs)
    assert digest == grading._context_approval(context, {"id": run_id, "job": "pilot-live", "attempt": 1})
    monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", digest)


@pytest.fixture
def case(tmp_path, monkeypatch, capsys, compilations, compiled_cells):
    assert grading.TASK2_RETAINED == {PREFIX + suffix: values for suffix, values in RECORDED.items()}
    assert readout.B1_WRITER_SOURCE == "ecbe297e7dc2d798a834091f14da3ae486172a43"
    assert readout.B1_WRITER_RUN == {"id": "36202409134", "job": "pilot-live", "attempt": 1}
    state = b1.case.__wrapped__(tmp_path, monkeypatch, capsys, compilations, compiled_cells)
    api = state.api
    state.inferences = {grading.B1_CELL: (b1.B1_TERMINAL, b1.B1_OUTPUT)}
    previous, previous_cell = b1.B1_TERMINAL, state.context.cell
    for ordinal, suffix in enumerate(tuple(RECORDED)[1:], 8):
        cell_id = PREFIX + suffix
        claim_revision, output_revision, terminal_revision = (f"{ordinal * 10 + offset:040x}" for offset in (1, 2, 3))
        seed_context = grading.compile_request("pilot/" + cell_id, grading.B1_PRODUCER_SOURCE, terminal_revision)
        seeded = SimpleNamespace(context=seed_context, api=api)
        with monkeypatch.context() as patch:
            for name, value in {"SOURCE": grading.B1_PRODUCER_SOURCE, "CLAIM": claim_revision,
                                "OUTPUT": output_revision, "TERMINAL": terminal_revision}.items():
                patch.setattr(base, name, value)
            base._seed_outputs(seeded, tmp_path)
        claim_path, terminal_path, prefix = retained._paths(seed_context.cell)
        previous_bytes = api.trees[previous][retained._paths(previous_cell)[1]]
        previous_terminal = pilot._json_object(previous_bytes)
        claim = seeded.claim
        claim["binding"]["github_run"] = {"id": RECORDED[suffix][0], "job": "cell", "attempt": 1}
        claim["expected_parent"] = previous
        claim["predecessor"] = {"cell_id": previous_cell["cell_id"], "terminal_commit": previous,
            "terminal_sha256": pilot._identity(previous_bytes)["sha256"],
            "output_commit": previous_terminal["output_commit"],
            "manifest_sha256": previous_terminal["manifest_identity"]["sha256"]}
        seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(claim))
        files = {name: data for name, data in api.trees[output_revision].items() if name.startswith(prefix + "/")}
        api.seed(claim_revision, previous, {claim_path: retained._encoded(claim)})
        api.seed(output_revision, claim_revision, files)
        api.seed(terminal_revision, output_revision, {terminal_path: retained._encoded(seeded.terminal)})
        monkeypatch.setitem(grading.TASK2_RETAINED, cell_id,
                            (RECORDED[suffix][0], pilot._digest(seeded.terminal["completion"])))
        state.inferences[cell_id] = (terminal_revision, output_revision)
        previous, previous_cell = terminal_revision, seed_context.cell
    api.branches[retained.BRANCH] = previous  # B1/C1 are not the latest inference HEAD.
    api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
    state.context = readout._writer_context(state.request)
    _authorize(state, tmp_path, monkeypatch, readout.B1_WRITER_RUN["id"])
    original_invoke = base.invoke

    def invoke_current(current, capture, phase="plan", **changes):
        return original_invoke(current, capture, phase,
            **{"terminal": current.context.requested_terminal, **changes})

    monkeypatch.setattr(base, "invoke", invoke_current)
    state.frozen_inference = {rev: copy.deepcopy(api.trees[rev]) for rev, _ in state.inferences.values()}
    return state


def _select(case, suffix, tmp_path, monkeypatch, *, source=CONTROLLER):
    cell_id = PREFIX + suffix
    request = grading.TASK2_RETAINED[cell_id][1]
    context = grading.compile_request("pilot/" + cell_id, source, request, producer_source_sha=grading.B1_PRODUCER_SOURCE)
    current = SimpleNamespace(context=context, request=request, api=case.api, workflow=case.workflow,
                              root=tmp_path / (suffix + "-" + source[:1]))
    current.transport = base.Child(current)
    monkeypatch.setattr(base, "OUTPUT", case.inferences[cell_id][1])
    _authorize(current, tmp_path, monkeypatch, str(800000 + context.plan["order"].index(cell_id)))
    return current


def _publish(case, capsys, tmp_path, monkeypatch, mode="graded"):
    tmp_path.mkdir(exist_ok=True)
    revision, path, terminal = writer._writer(case, capsys, tmp_path, monkeypatch, mode)
    assert terminal["binding"]["source_sha"] == grading.B1_PRODUCER_SOURCE
    assert terminal["binding"]["controller_source_sha"] == case.context.controller_source_sha
    return revision, path, terminal


@pytest.mark.parametrize("scenario", [
    "readout_graded", "readout_partial", "readout_failed", "readout_ungraded", "readout_missing_ledger",
    "readout_advanced", "readout_writer", "readout_run", "readout_completion", "readout_receipt",
    "readout_hash", "readout_bytes", "readout_raw", "readout_cleanup", "readout_target", "readout_plan",
    "chain", "intake_run", "intake_completion", "intake_ref", "intake_source", "previous_writer",
    "skip", "unfinished", "controller_drift", "resolution", "missing_approval", "claim_lost", "publication_lost",
])
def test_task2_grade_completion(case, tmp_path, monkeypatch, capsys, scenario):
    api = case.api
    mode = scenario.removeprefix("readout_")
    grade_revision, grade_path, terminal = _publish(case, capsys, tmp_path / "b1-writer", monkeypatch, mode)
    assert terminal["binding"]["github_run"] == readout.B1_WRITER_RUN
    assert terminal["binding"]["approval_request_sha256"] == grading._context_approval(case.context, readout.B1_WRITER_RUN)
    assert terminal["binding"]["retained"]["terminal_commit"] == b1.B1_TERMINAL
    if scenario.startswith("readout_"):
        record = next((item for item in terminal["files"] if item["role"] == "grade_result"), None)
        if mode == "advanced":
            api.seed("f" * 40, grade_revision, {"unrelated/PRIVATE": b"PRIVATE unrelated grade"})
            api.branches[grading.BRANCH] = "f" * 40
        elif mode == "writer":
            terminal["binding"]["controller_source_sha"] = CONTROLLER
        elif mode == "run":
            terminal["binding"]["github_run"]["id"] = "36202409135"
        elif mode == "completion":
            path = retained._paths(case.context.cell)[1]
            raw = pilot._json_object(api.trees[b1.B1_TERMINAL][path])
            raw["completion"]["child_invocations"] = 2
            api.trees[b1.B1_TERMINAL][path] = retained._encoded(raw)
        elif mode == "receipt":
            terminal["binding"]["publication_receipt_sha256"] = "9" * 64
        elif mode == "hash":
            terminal["binding"]["grader_source_hash"] = "9" * 64
        elif mode == "bytes":
            api.trees[grade_revision][record["path"]] += b"PRIVATE"
        elif mode == "raw":
            payload = pilot._json_object(api.trees[grade_revision][record["path"]])
            payload["tasks"][0]["items"][0]["judge_raw_response"] = "PRIVATE https://private.invalid/secret"
            data = base._json(payload)
            api.trees[grade_revision][record["path"]] = data
            record.update(retained._object(record["path"], data))
        elif mode == "cleanup":
            terminal["child"]["cleanup_confirmed"] = False
        elif mode == "target":
            api.private = False
        api.trees[grade_revision][grade_path] = retained._encoded(terminal)

        def forbidden(*args, **kwargs):
            pytest.fail("readout attempted preparation, mutation, auth or judge")

        for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "_entry_contract", "_ready"):
            monkeypatch.setattr(grading, name, forbidden)
        monkeypatch.setattr(api, "create_commit", forbidden)
        monkeypatch.setattr(api, "create_branch", forbidden)
        monkeypatch.setattr(output, "_hf_client", forbidden)
        original_bind = readout._ReadOnlyGrade.bind_retained

        def checked_bind(reader, binding, context, cache, deadline):
            original_bind(reader, binding, context, cache, deadline)
            assert not hasattr(reader, "create_commit") and not hasattr(reader, "create_branch")
            _, _, prefix = retained._paths(context.cell)
            with pytest.raises(output.OutputPublicationRefused):
                reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=binding["retained"]["output_commit"], filename=prefix + "/step2_inference_results.json",
                    cache_dir=cache, force_download=True, local_files_only=False, etag_timeout=1)

        monkeypatch.setattr(readout._ReadOnlyGrade, "bind_retained", checked_bind)
        for key, value in {"GITHUB_SHA": CONTROLLER, "PILOT_WORKFLOW_SHA": CONTROLLER, "GITHUB_JOB": "pilot-readout",
                           "GITHUB_RUN_ID": "900010", "PILOT_GRADE_PAID_APPROVAL": "false"}.items():
            monkeypatch.setenv(key, value)
        for key in ("PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256"):
            monkeypatch.delenv(key, raising=False)
        args = ["--selector", readout.SELECTOR, "--reviewed-source-sha", CONTROLLER,
                "--terminal-revision", case.request, "--root", str(tmp_path / "readout"), "--phase", "readout"]
        if mode == "plan":
            writer._workflow_contract()
            monkeypatch.setenv("GITHUB_ACTIONS", "false")
            monkeypatch.delenv("HF_TOKEN")
            args[-1] = "plan"
        api.calls.clear()
        api.reads.clear()
        frozen = copy.deepcopy((api.trees, api.writers, api.branches, api.events))
        code = grading.main(args, _test_api=api, _test_transport=SimpleNamespace(require_source=lambda plan, parent:
            None if plan["reviewed_source_sha"] == CONTROLLER else forbidden()))
        capture = capsys.readouterr()
        text = capture.out + capture.err
        assert len(text.splitlines()) == 1
        for private in ("PRIVATE", base.TOKEN, api.repo, str(tmp_path), "https://", "Traceback"):
            assert private not in text
        public = json.loads(text)
        assert (api.trees, api.writers, api.branches, api.events) == frozen
        assert public["remote_mutation_possible"] is public["judge_entry_requested"] is False
        assert public["invoice_complete"] is False and public["http_request_count"] is None
        if mode == "plan":
            assert code == 0 and public["outcome"] == "plan_only" and api.calls == []
        elif mode in {"graded", "partial", "failed", "ungraded", "missing_ledger", "advanced"}:
            assert code == 0, public
            assert public["grade_state"] == (mode if mode in {"partial", "failed", "ungraded"} else "graded")
            assert public["grade_revision"] == grade_revision and public["inference_terminal"] == b1.B1_TERMINAL
            assert public["inference_request_checksum"] == case.request
            assert public["grade_writer_source_sha"] == readout.B1_WRITER_SOURCE
            assert public["inference_producer_source_sha"] == grading.B1_PRODUCER_SOURCE
            assert public["observer_source_sha"] == CONTROLLER and public["expected_tasks"] == 1
            if mode in {"failed", "ungraded", "partial"}:
                assert public["score"] is None and public["scored_tasks"] == 0
            else:
                assert public["score"]["earned"] == public["score"]["possible"] == 4
                assert public["score"]["pct"] == 100 and public["scored_tasks"] == 1
            assert public["ledger_state"] == ("missing" if mode in {"ungraded", "missing_ledger"} else "present")
            if public["ledger_derived_cost"] is not None:
                assert public["ledger_derived_cost"]["estimated_cost_usd"] is None
        else:
            assert code == 2 and public["outcome"] == "refused" and "score" not in public
        inference_downloads = {path for operation, revision, path, _ in api.reads
                              if operation == "download" and path.startswith(("cell-claims/", "cell-outputs/"))}
        claim_path, terminal_path, prefix = retained._paths(case.context.cell)
        controls = {claim_path, terminal_path, prefix + "/" + output.MANIFEST}
        assert inference_downloads <= controls
        if code == 0 and mode != "plan":
            assert inference_downloads == controls
        assert all(revision != retained.BRANCH for operation, revision in api.calls if operation == "metadata")
        return

    current = _select(case, "C_r1", tmp_path, monkeypatch)
    if scenario == "chain":
        previous_grade = grade_revision
        frozen = copy.deepcopy(api.trees)
        for suffix in tuple(RECORDED)[1:]:
            current = _select(case, suffix, tmp_path, monkeypatch)
            config = json.loads(current.context.grading.dispatch.runs[0].config_json)
            assert len(current.context.plan["order"]) == 30 and current.context.plan["order"][6] == grading.RETAINED_CELL
            assert current.context.plan["model"] == case.context.plan["model"]
            assert current.context.plan["source_pins"] == case.context.plan["source_pins"]
            assert config["execution"]["timeout"] == 1800 and pilot.TOTAL_SECONDS == 10800
            assert ci.HOST_POLICY["sdk"] == "0.147.0"
            assert current.context.run.grader_config_json == case.context.run.grader_config_json
            revision, _, result = _publish(current, capsys, tmp_path / (suffix + "-writer"), monkeypatch)
            claim = retained._read(current.root / "claim-receipt.json")["claim"]
            assert claim["expected_parent"] == previous_grade
            assert claim["predecessor"]["cell_id"] == current.context.plan["order"][current.context.plan["order"].index(PREFIX + suffix) - 1]
            assert result["binding"]["retained"]["terminal_commit"] == case.inferences[PREFIX + suffix][0]
            assert current.transport.calls == 1
            previous_grade = revision
        assert all(api.trees[revision] == data for revision, data in frozen.items())
        assert api.branches[retained.BRANCH] == case.inferences[PREFIX + "A_r2"][0]
        assert set(grading.TASK2_RETAINED) == {PREFIX + suffix for suffix in RECORDED}
        return

    if scenario in {"skip", "unfinished", "controller_drift"}:
        if scenario == "unfinished":
            base.admitted(current, capsys)
        elif scenario == "controller_drift":
            _publish(current, capsys, tmp_path / "c1-writer", monkeypatch)
        current = _select(case, "C_r2", tmp_path, monkeypatch, source=FOREIGN if scenario == "controller_drift" else CONTROLLER)
    if scenario in {"intake_run", "intake_completion"}:
        revision, _ = case.inferences[PREFIX + "C_r1"]
        claim_path, path, _ = retained._paths(current.context.cell)
        value = pilot._json_object(api.trees[revision][path])
        if scenario == "intake_completion":
            value["completion"]["child_invocations"] = 2
        else:
            claim = pilot._json_object(api.trees[value["claim_commit"]][claim_path])
            claim["binding"]["github_run"]["id"] = "36195731408"
            for tree in (value["claim_commit"], value["output_commit"], revision):
                api.trees[tree][claim_path] = retained._encoded(claim)
            value["claim_identity"] = pilot._identity(retained._encoded(claim))
        api.trees[revision][path] = retained._encoded(value)
    elif scenario == "intake_ref":
        monkeypatch.setattr(retained, "BRANCH", "pilot-inference-20260924-03")
    elif scenario == "previous_writer":
        terminal["binding"]["controller_source_sha"] = CONTROLLER
        api.trees[grade_revision][grade_path] = retained._encoded(terminal)
    elif scenario == "missing_approval":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    changes = {"producer": FOREIGN} if scenario == "intake_source" else {}
    before = len(api.events)
    code, public = base.invoke(current, capsys, "prepare", **changes)
    if scenario.startswith("intake_") or scenario == "missing_approval":
        assert code == 2 and public["outcome"] == "refused"
        assert current.transport.calls == 0 and len(api.events) == before
        return
    assert code == 0 and public["judge_ready"] is True, (public, current.diagnostic)
    if scenario == "resolution":
        prepared = retained._read(current.root / "prepared.json")
        prepared["terminal_revision"] = "9" * 40
        (current.root / "prepared.json").write_bytes(retained._encoded(prepared))
    if scenario == "claim_lost":
        api.lost = "grade_claim"
    code, public = base.invoke(current, capsys, "claim")
    if scenario != "publication_lost":
        assert code == 2 and public["outcome"] in {"refused", "unresolved"}, (public, current.diagnostic)
        writes = len(api.events)
        assert base.invoke(current, capsys, "judge")[0] == 2 and current.transport.calls == 0
        assert base.invoke(current, capsys, "claim")[0] == 2 and len(api.events) == writes
        assert writes == before + (1 if scenario == "claim_lost" else 0)
        return
    assert code == 0
    assert base.invoke(current, capsys, "judge")[0] == 0
    api.lost = "grade_output"
    code, public = base.invoke(current, capsys, "publish")
    assert code == 2 and public["outcome"] == "unresolved" and current.transport.calls == 1
    writes = len(api.events)
    assert base.invoke(current, capsys, "publish")[0] == 2 and len(api.events) == writes
