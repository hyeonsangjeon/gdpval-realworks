"""One closed reader over genuine synthetic writers, never live grade evidence.

Build the historical task2 sequence once, then publish isolated A1 fixtures with
the existing writers. Synthetic bytes and private revisions do not reconstruct
the actual result. The reader has no model, rubric-fetch or remote-write path.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
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
import step8_grade as step8
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as task2
from . import test_codex_budget_pilot_task3_a1_grading as a1
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — all live boundaries blocked

OBSERVER = "e" * 40  # Synthetic observer, not a future source authorization.
PRIVATE = "PRIVATE https://private.invalid/path?token=PRIVATE"
WRITER = "69e56fc58daf50af2ac9e8b52691ffcbf5af4f96"
REQUEST = "1fb1bc33acab5b2bdefd70744a899c808d984e9c231deded4217ad92d4dc7e3d"
PREVIOUS_CELL = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r2"


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    assert readout.TASK3_A1_WRITER_SOURCE == WRITER
    assert readout.TASK3_A1_WRITER_RUN == {"id": "36282221138", "job": "pilot-live", "attempt": 1}
    assert grading.TASK3_A1_COMPLETION_SHA256 == REQUEST
    actual = readout._writer_context(REQUEST)
    assert actual.cell["cell_id"] == "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r1"
    assert actual.plan["order"][11:13] == [PREVIOUS_CELL, actual.cell["cell_id"]]
    assert len(actual.plan["order"]) == 30
    assert actual.controller_source_sha == WRITER
    assert actual.plan["reviewed_source_sha"] == "78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e"
    assert actual.cell["config_sha256"] == "35a23a8842d378a8326ec8483553145ee5c63c9c63a383be3eb903bda77136a3"
    assert actual.terminal_revision == "" and actual.terminal_request == REQUEST
    assert hashlib.sha256(actual.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert readout.CONFIG_SHA256 == "62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0"
    assert readout.TASK3_A1_GRADER_SOURCE_HASH == "0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df"
    assert readout.TASK2_WRITER_SOURCE == "a5e5d2589caff21309f0a1c21bb7d9d333ad47c6"
    assert readout.TASK2_GRADE_RUNS[PREVIOUS_CELL] == "36214413190"
    assert grading.TASK3_A1_PREVIOUS_GRADE == "3a8e135cd232ab900e003fc6d9c459957a0b990e"
    assert grading.TASK3_A1_PREVIOUS_TERMINAL == "e22f0c3de79bbfce084aedde64fa56c40959fde0"

    directory = tmp_path_factory.mktemp("task3-a1-readout-history")
    capture = _Capture()
    with pytest.MonkeyPatch.context() as patch:
        base.boundaries.__wrapped__(patch)
        patch.setattr(a1, "CONTROLLER", WRITER)
        compilations = a1.compilations.__wrapped__()
        compilations[OBSERVER] = pilot.compile_pilot(ci.CAMPAIGN, OBSERVER)
        compiled_cells = a1.compiled_cells.__wrapped__()
        with redirect_stdout(capture.out), redirect_stderr(capture.err):
            first = a1.case.__wrapped__(directory, patch, capture, compilations, compiled_cells)
            shared = SimpleNamespace(rows={}, request=first.request, context=first.context,
                previous_context=first.previous_context, previous_path=first.previous_path)
            before = copy.deepcopy(first.api)
            for scenario in ("graded", "partial", "failed", "ungraded", "missing_ledger", "partial_cost"):
                local = directory / scenario
                local.mkdir()
                current = SimpleNamespace(api=copy.deepcopy(before), workflow=first.workflow,
                    context=readout._writer_context(first.request), request=first.request, root=local / "grade")
                current.transport = base.Child(current)
                with patch.context() as selected:
                    selected.setattr(base, "OUTPUT", a1.OUTPUT)
                    selected.setenv("HF_TOKEN", base.TOKEN)
                    task2._authorize(current, local, selected, readout.TASK3_A1_WRITER_RUN["id"])
                    revision, path, terminal = writer._writer(current, capture, local, selected, scenario)
                ready = retained._read(current.root / "prepared.json")
                # Real entry-contract hashing includes generated comparison-grading.json.
                assert ready["entry"]["grader_source_hash"] == readout.TASK3_A1_GRADER_SOURCE_HASH
                assert ready["entry"]["config_hash"] == readout.CONFIG_SHA256[:16]
                assert terminal["binding"]["controller_source_sha"] == WRITER
                assert terminal["binding"]["github_run"] == readout.TASK3_A1_WRITER_RUN
                assert current.transport.calls == 1
                assert current.api.events == ["grade_claim", "judge", "grade_output"]
                assert all(current.api.trees[rev] == data for rev, data in before.trees.items())
                shared.rows[scenario] = SimpleNamespace(api=current.api, revision=revision, path=path,
                    terminal=terminal, context=current.context)
        yield shared


def _store_grade(api, revision, path, terminal, claim):
    """Rehash an isolated adversarial control pair, retaining its fake history."""
    claim_path = path.rsplit("/", 1)[0] + "/claim.json"
    claim["binding"] = copy.deepcopy(terminal["binding"])
    encoded = retained._encoded(claim)
    terminal["claim_identity"] = pilot._identity(encoded)
    for commit in (terminal["claim_commit"], revision):
        api.trees[commit][claim_path] = encoded
    data = retained._encoded(terminal)
    api.trees[revision][path] = data
    return data


def _unregistered_requests():
    # Task3/task4 have exact recorded readouts; all task5 readers stay closed.
    registered = {readout.TASK3_B1_CELL, readout.TASK3_C1_CELL, readout.TASK3_C2_CELL,
                  readout.TASK3_B2_CELL, readout.TASK3_A2_CELL}
    assert set(readout.TASK3_SUCCESSOR_READOUTS) == registered
    assert registered == set(grading.TASK3_SUCCESSORS)
    task4 = {
        "3baa0009-5a60-4ae8-ae99-4955cb328ff3_C_r1": (20, grading.TASK4_B1_CELL,
            {"id": "36294081159", "job": "pilot-live", "attempt": 1}),
        "3baa0009-5a60-4ae8-ae99-4955cb328ff3_C_r2": (21, readout.TASK4_C1_CELL,
            {"id": "36295603145", "job": "pilot-live", "attempt": 1}),
        "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2": (22, readout.TASK4_C2_CELL,
            {"id": "36297122393", "job": "pilot-live", "attempt": 1}),
    }
    assert readout.TASK4_SUCCESSOR_READOUTS == task4
    requests = [value[1] for cell, value in grading.TASK3_SUCCESSORS.items() if cell not in registered]
    closed = [value[1] for cell, value in {**grading.TASK4_RETAINED, **grading.TASK5_RETAINED}.items()
              if cell not in {grading.TASK4_A1_CELL, grading.TASK4_A2_CELL, grading.TASK4_B1_CELL, *task4}]
    requests.extend(closed)
    requests.extend(["9" * 64, "9" * 40, ""])
    assert len(requests) == len(set(requests)) == 9
    assert all(request in requests for request in closed)
    actual = readout._writer_context(grading.TASK4_RETAINED[grading.TASK4_A1_CELL][1])
    assert actual.cell["cell_id"] == grading.TASK4_A1_CELL
    assert readout._writer_run(actual) == {"id": "36291118506", "job": "pilot-live", "attempt": 1}
    assert actual.requested_terminal not in requests
    ordinary = readout._writer_context(grading.TASK4_RETAINED[grading.TASK4_B1_CELL][1])
    assert ordinary.cell["cell_id"] == grading.TASK4_B1_CELL
    assert ordinary.plan["order"][18:20] == [grading.TASK4_A1_CELL, grading.TASK4_B1_CELL]
    assert readout._writer_run(ordinary) == {"id": "36292532223", "job": "pilot-live", "attempt": 1}
    assert ordinary.requested_terminal not in requests
    for cell, (ordinal, parent, run) in task4.items():
        current = readout._writer_context(grading.TASK4_RETAINED[cell][1])
        assert current.cell["cell_id"] == cell
        assert current.plan["order"][ordinal - 1:ordinal + 1] == [parent, cell]
        assert readout._writer_run(current) == run and current.requested_terminal not in requests
    assert ordinary.plan["order"][20:23] == list(task4)
    final = readout._writer_context(grading.TASK4_RETAINED[grading.TASK4_A2_CELL][1])
    assert final.cell["cell_id"] == grading.TASK4_A2_CELL
    assert final.plan["order"][22:24] == [readout.TASK4_B2_CELL, grading.TASK4_A2_CELL]
    assert readout._writer_run(final) == {"id": "36298545498", "job": "pilot-live", "attempt": 1}
    assert final.requested_terminal not in requests
    assert set(final.plan["order"][18:24]) == {grading.TASK4_A1_CELL, grading.TASK4_B1_CELL,
                                             *task4, grading.TASK4_A2_CELL}
    assert [grading.TASK5_RETAINED[cell][1] for cell in ordinary.plan["order"][24:]] == closed
    assert all(grading.TASK3_SUCCESSORS[cell][1] not in requests for cell in registered)
    return requests


@pytest.mark.parametrize("scenario", [
    "graded", "advanced", "partial", "failed", "ungraded", "missing_ledger", "partial_cost",
    "exclusions", "redacted_text", "plan", "closed_registry", "writer", "run", "job", "attempt",
    "typed_attempt", "producer", "grader_hash", "config_hash", "grader_config", "renderer", "approval", "claim_hash",
    "claim_bytes", "claim_history", "terminal_history", "artifact_history", "bytes", "path", "raw_judge",
    "private_cost_reason", "denominator_type", "payload_source", "ledger_pointer", "ledger_bytes", "cleanup", "no_child",
    "outcome", "record_type", "absent", "unfinished", "inference_completion", "inference_run",
    "inference_source", "inference_config", "inference_predecessor", "inference_parent", "inference_history",
    "inference_bytes", "inference_receipt", "previous_grade", "previous_run", "previous_writer",
    "previous_source", "previous_grader_hash", "previous_config", "previous_renderer", "previous_cleanup",
    "previous_receipt", "previous_claim", "previous_no_child",
    "previous_inference", "previous_hash", "previous_carried", "previous_cell", "previous_absent",
    "ref", "inference_ref", "observer_writer", "observer_producer", "observer_source", "source_preflight",
    "producer_override", "wrong_phase", "paid", "rerun", "private_target", "lost_response",
])
def test_fixed_task3_a1_grade_readout(history, tmp_path, monkeypatch, capsys, scenario):
    row = history.rows.get(scenario, history.rows["graded"])
    api, terminal = copy.deepcopy(row.api), copy.deepcopy(row.terminal)
    context, revision, path = copy.deepcopy(row.context), row.revision, row.path
    claim_path = grading._paths(context.cell)[0]
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
    previous_revision = grading.TASK3_A1_PREVIOUS_GRADE
    previous_path = history.previous_path
    previous = pilot._json_object(api.trees[previous_revision][previous_path])
    previous_claim_path = grading._paths(history.previous_context.cell)[0]
    previous_claim = pilot._json_object(api.trees[previous["claim_commit"]][previous_claim_path])
    record = next((item for item in terminal["files"] if item["role"] == "grade_result"), None)

    if scenario == "advanced":
        api.seed(a1.ADVANCED, revision, {"unrelated/PRIVATE": b"PRIVATE unrelated later cell"})
        api.branches[grading.BRANCH] = a1.ADVANCED
        api.branches[retained.BRANCH] = a1.ADVANCED
    elif scenario in {"writer", "producer", "grader_hash", "config_hash", "grader_config", "approval"}:
        key = {"writer": "controller_source_sha", "producer": "source_sha", "grader_hash": "grader_source_hash",
               "config_hash": "config_hash", "grader_config": "grader_config_sha256",
               "approval": "approval_request_sha256"}[scenario]
        terminal["binding"][key] = "9" * (40 if scenario in {"writer", "producer"} else 16 if scenario == "config_hash" else 64)
    elif scenario in {"run", "job", "attempt", "typed_attempt"}:
        run = terminal["binding"]["github_run"]
        key, value = {"run": ("id", "36282221139"), "job": ("job", "grade"),
                      "attempt": ("attempt", 2), "typed_attempt": ("attempt", True)}[scenario]
        run[key] = value
        terminal["binding"]["approval_request_sha256"] = grading._context_approval(context, run)
    elif scenario == "renderer":
        terminal["binding"]["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE other renderer"
    elif scenario in {"exclusions", "redacted_text", "raw_judge", "private_cost_reason", "denominator_type",
                      "payload_source", "ledger_pointer"}:
        payload = pilot._json_object(api.trees[revision][record["path"]])
        task = payload["tasks"][0]
        if scenario == "exclusions":
            task["items"][1].update(score_excluded=True, verdict="judge_error", awarded_score=0,
                                    model_did_right=False, decided_by="judge")
            task.update(total_awarded=2, total_max=2, pct=100, score_excluded_items=1, score_excluded_max=2,
                        pct_full_denominator=50)
            payload["summary"] = step8._compute_summary(payload["tasks"],
                unpriced_models=step8._unpriced_models(json.loads(context.run.grader_config_json)))
        elif scenario == "redacted_text":
            task["sector"] = PRIVATE
            task["items"][0].update(criterion=PRIVATE, evidence=PRIVATE)
            task["grading_cost"]["components"][0]["provider"] = PRIVATE
        elif scenario == "raw_judge":
            task["items"][0]["judge_raw_response"] = PRIVATE
        elif scenario == "private_cost_reason":
            task["grading_cost"]["missing_reasons"] = [PRIVATE]
        elif scenario == "denominator_type":
            task["total_max"] = "PRIVATE"
        elif scenario == "payload_source":
            payload["source_inference_revision"] = "9" * 40
        else:
            payload["cost_ledger"]["sha256"] = "9" * 64
        data = base._json(payload)
        api.trees[revision][record["path"]] = data
        record.update(retained._object(record["path"], data))
    elif scenario == "bytes":
        api.trees[revision][record["path"]] += b"PRIVATE"
    elif scenario == "ledger_bytes":
        ledger = next(item for item in terminal["files"] if item["role"] == "grade_cost_ledger")
        api.trees[revision][ledger["path"]] += b"PRIVATE"
    elif scenario == "path":
        record["path"] = "PRIVATE/foreign.json"
    elif scenario == "cleanup":
        terminal["child"]["cleanup_confirmed"] = False
    elif scenario == "no_child":
        terminal["child"]["entry_invoked"] = False
    elif scenario == "outcome":
        terminal["outcome"] = "failed"
    elif scenario == "record_type":
        terminal["format"] = "model-free-ungraded"
    elif scenario in {"claim_history", "terminal_history", "artifact_history"}:
        if scenario == "claim_history":
            api.writers[revision][claim_path] = revision
        elif scenario == "terminal_history":
            api.writers[revision][path] = terminal["claim_commit"]
        else:
            api.writers[revision][record["path"]] = terminal["claim_commit"]
    elif scenario.startswith("inference_") and scenario != "inference_ref":
        input_claim_path, input_path, prefix = retained._paths(context.cell)
        input_terminal = pilot._json_object(api.trees[a1.TERMINAL][input_path])
        input_claim = pilot._json_object(api.trees[a1.CLAIM][input_claim_path])
        if scenario == "inference_completion":
            input_terminal["completion"]["child_invocations"] = 2
        elif scenario == "inference_run":
            input_claim["binding"]["github_run"]["id"] = "36225255533"
        elif scenario == "inference_source":
            input_claim["binding"]["source_sha"] = "9" * 40
        elif scenario == "inference_config":
            input_claim["binding"]["config_sha256"] = "9" * 64
        elif scenario == "inference_predecessor":
            input_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif scenario == "inference_parent":
            input_claim["expected_parent"] = "9" * 40
        elif scenario == "inference_history":
            api.writers[a1.TERMINAL][input_claim_path] = a1.TERMINAL
        elif scenario == "inference_bytes":
            api.trees[a1.OUTPUT][prefix + "/" + output.MANIFEST] += b"PRIVATE"
        else:
            input_terminal["publication_receipt_sha256"] = "9" * 64
        data = retained._encoded(input_claim)
        for commit in (a1.CLAIM, a1.OUTPUT, a1.TERMINAL):
            api.trees[commit][input_claim_path] = data
        input_terminal["claim_identity"] = pilot._identity(data)
        data = retained._encoded(input_terminal)
        api.trees[a1.TERMINAL][input_path] = data
        terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
    elif scenario in {"previous_run", "previous_writer", "previous_source", "previous_grader_hash",
                      "previous_config", "previous_renderer", "previous_cleanup", "previous_inference",
                      "previous_receipt", "previous_no_child"}:
        if scenario == "previous_run":
            previous["binding"]["github_run"]["id"] = "36214413191"
            previous["binding"]["approval_request_sha256"] = grading._context_approval(
                history.previous_context, previous["binding"]["github_run"])
        elif scenario in {"previous_writer", "previous_source", "previous_grader_hash", "previous_config"}:
            key = {"previous_writer": "controller_source_sha", "previous_source": "source_sha",
                   "previous_grader_hash": "grader_source_hash", "previous_config": "config_hash"}[scenario]
            previous["binding"][key] = "9" * (40 if scenario in {"previous_writer", "previous_source"}
                                              else 16 if scenario == "previous_config" else 64)
        elif scenario == "previous_renderer":
            previous["binding"]["renderer_fingerprint"]["pymupdf_version"] = True
        elif scenario == "previous_cleanup":
            previous["child"]["cleanup_confirmed"] = False
        elif scenario == "previous_no_child":
            previous["child"]["entry_invoked"] = False
        elif scenario == "previous_receipt":
            previous["binding"]["publication_receipt_sha256"] = "9" * 64
        else:
            previous["binding"]["retained"]["terminal_commit"] = "9" * 40
        data = _store_grade(api, previous_revision, previous_path, previous, previous_claim)
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][previous_path] = data
        claim["predecessor"].update(pilot._identity(data))
    elif scenario == "previous_grade":
        claim["expected_parent"] = claim["predecessor"]["revision"] = "9" * 40
    elif scenario == "previous_hash":
        claim["predecessor"]["sha256"] = "9" * 64
    elif scenario == "previous_carried":
        api.writers[terminal["claim_commit"]][previous_path] = terminal["claim_commit"]
    elif scenario == "previous_cell":
        claim["predecessor"]["cell_id"] = task2.PREFIX + "B_r2"
    elif scenario == "previous_absent":
        api.trees[previous_revision].pop(previous_path)
    elif scenario == "previous_claim":
        api.trees[previous["claim_commit"]][previous_claim_path] += b" "
    elif scenario == "ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif scenario == "inference_ref":
        monkeypatch.setattr(retained, "BRANCH", "pilot-inference-20260924-03")
    elif scenario == "private_target":
        api.private = False
    elif scenario == "lost_response":
        api.read_fail = True

    _store_grade(api, revision, path, terminal, claim)
    if scenario == "claim_hash":
        terminal["claim_identity"]["sha256"] = "9" * 64
        api.trees[revision][path] = retained._encoded(terminal)
    elif scenario == "claim_bytes":
        api.trees[terminal["claim_commit"]][claim_path] += b" "
    elif scenario == "absent":
        api.trees[revision].pop(path)
    elif scenario == "unfinished":
        api.branches[grading.BRANCH] = terminal["claim_commit"]

    def forbidden(*args, **kwargs):
        pytest.fail("A1 reader crossed a model, rubric, auth, admission or remote-write boundary")

    for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "inspect_branch",
                 "_entry_contract", "_ready"):
        monkeypatch.setattr(grading, name, forbidden)
    for name in ("create_commit", "create_branch"):
        monkeypatch.setattr(api, name, forbidden)
    monkeypatch.setattr(adapter, "materialize_pilot_grading_input", forbidden)
    monkeypatch.setattr(output, "_hf_client", forbidden)
    monkeypatch.setattr(step8, "main", forbidden)
    monkeypatch.setattr(base.Child, "process", forbidden)
    readers = []
    initialize = readout._ReadOnlyGrade.__init__

    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)

    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    source = (WRITER if scenario == "observer_writer" else grading.TASK3_A1_PRODUCER_SOURCE
              if scenario == "observer_producer" else OBSERVER)
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
                       "GITHUB_RUN_ID": "900020", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
        monkeypatch.setenv(key, value)
    for key in ("PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256"):
        monkeypatch.delenv(key, raising=False)
    if scenario == "observer_source":
        monkeypatch.setenv("PILOT_WORKFLOW_SHA", "9" * 40)
    elif scenario == "paid":
        monkeypatch.setenv("PILOT_GRADE_PAID_APPROVAL", "true")
    elif scenario == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    phase = "plan" if scenario in {"plan", "closed_registry"} else "readout"
    if phase == "plan":
        writer._workflow_contract()
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        monkeypatch.setattr(retained, "_session", forbidden)
    if scenario == "wrong_phase":
        phase = "claim"
    api.calls.clear()
    api.reads.clear()
    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches, api.events))
    root = tmp_path / "readout"
    args = ["--selector", readout.SELECTOR, "--reviewed-source-sha", source,
            "--terminal-revision", history.request, "--root", str(root), "--phase", phase]
    if scenario == "producer_override":
        args.extend(["--producer-source-sha", grading.TASK3_A1_PRODUCER_SOURCE])

    def source_check(plan, parent):
        assert plan["reviewed_source_sha"] == OBSERVER
        if scenario == "source_preflight":
            raise ValueError(PRIVATE)

    code = grading.main(args, _test_api=api, _test_transport=SimpleNamespace(require_source=source_check))
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert len(text.splitlines()) == 1
    for private in ("PRIVATE", base.TOKEN, api.repo, str(tmp_path), "https://", "Traceback"):
        assert private not in text
    public = json.loads(text)
    assert (api.trees, api.writers, api.parents, api.branches, api.events) == frozen
    assert public["remote_mutation_possible"] is public["judge_entry_requested"] is False
    assert public["inference_requested"] is public["automatic_retry"] is False
    assert public["invoice_complete"] is False and public["http_request_count"] is None
    accepted = {"graded", "advanced", "partial", "failed", "ungraded", "missing_ledger", "partial_cost",
                "exclusions", "redacted_text"}
    downloaded = {member for operation, _, member, _ in api.reads if operation == "download"}
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        assert public["inference_terminal"] is None
        assert public["grade_writer_source_sha"] == WRITER and public["observer_source_sha"] == OBSERVER
        if scenario == "closed_registry":
            for request in _unregistered_requests():
                closed = list(args)
                closed[5] = request
                assert grading.main(closed, _test_api=api) == 2
                refused = capsys.readouterr()
                assert not refused.out and json.loads(refused.err)["outcome"] == "refused"
                assert not api.calls and not root.exists()
    elif scenario in accepted:
        assert code == 0 and public["outcome"] == "verified_retained_grade", public
        assert public["grade_state"] == (scenario if scenario in {"partial", "failed", "ungraded"} else "graded")
        assert public["grade_revision"] == revision and public["inference_terminal"] == a1.TERMINAL
        assert public["inference_request_checksum"] == history.request
        assert public["grade_writer_source_sha"] == WRITER
        assert public["grade_writer_run"] == readout.TASK3_A1_WRITER_RUN
        assert public["inference_producer_source_sha"] == grading.TASK3_A1_PRODUCER_SOURCE
        assert public["observer_source_sha"] == OBSERVER and len({OBSERVER, WRITER, grading.TASK3_A1_PRODUCER_SOURCE}) == 3
        assert public["grader_source_hash"] == readout.TASK3_A1_GRADER_SOURCE_HASH
        assert public["grader_config_sha256"] == readout.CONFIG_SHA256
        assert public["expected_tasks"] == 1 and public["proof_boundary"] == grading.PROOF
        if scenario in {"partial", "failed", "ungraded"}:
            assert public["score"] is None and public["scored_tasks"] == 0
        else:
            score = public["score"]
            assert score["earned"] == score["possible"] == (2 if scenario == "exclusions" else 4)
            assert score["pct"] == 100 and public["coverage"]["rubric_items"] == (1 if scenario == "exclusions" else 2)
            assert score["excluded_items"] == (1 if scenario == "exclusions" else 0)
            assert score["excluded_max_score"] == (2 if scenario == "exclusions" else 0)
            assert score["avg_score_pct_full_denominator"] == (50 if scenario == "exclusions" else 100)
            assert score["avg_score_pct_lift"] == (50 if scenario == "exclusions" else 0)
            assert score["possible"] + score["excluded_max_score"] == 4
        if scenario in {"missing_ledger", "ungraded"}:
            assert public["ledger_state"] == "missing" and public["ledger_derived_cost"] is None
        elif scenario == "partial_cost":
            receipt = public["ledger_derived_cost"]
            assert receipt["known_cost_usd"] > 0 and receipt["model_calls"] == 2
            assert receipt["usage"] == {"input_tokens": 111, "output_tokens": 23, "cached_input_tokens": 17,
                                        "reasoning_tokens": 8, "audio_input_tokens": None, "audio_output_tokens": None}
            assert "call_reachability_unknown" in receipt["missing_reasons"]
        else:
            assert public["ledger_derived_cost"]["estimated_cost_usd"] is None
            # The genuine fixture reserved this call but never settled it.
            assert public["ledger_derived_cost"]["missing_reasons"] == ["call_reachability_unknown"]
        for receipt in (public["recorded_task_cost"], public["recorded_summary_cost"], public["ledger_derived_cost"]):
            if receipt is not None:
                assert receipt["invoice_complete"] is False and receipt["http_request_count"] is None
        assert len(readers) == 2  # Selected A1 plus immediate historical A2, never B2 recursion.
        assert readers[1].revision == previous_revision
        assert sum(call == ("metadata", grading.BRANCH) for call in api.calls) == 1
        assert public["observed_branch_head"] == (a1.ADVANCED if scenario == "advanced" else revision)
        controls = {claim_path, path, previous_claim_path, previous_path}
        for cell in (context.cell, history.previous_context.cell):
            input_claim, input_terminal, prefix = retained._paths(cell)
            controls.update({input_claim, input_terminal, prefix + "/" + output.MANIFEST})
        assert downloaded == controls | {item["path"] for item in terminal["files"]}
        for reader in readers:
            assert not hasattr(reader, "create_commit") and not hasattr(reader, "create_branch")
            with pytest.raises(output.OutputPublicationRefused):
                reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=previous_revision, filename=previous["files"][0]["path"], cache_dir=tmp_path,
                    force_download=True, local_files_only=False, etag_timeout=1)
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        if scenario.startswith("previous_"):
            assert not downloaded.intersection(item["path"] for item in terminal["files"])
        if scenario == "lost_response":
            assert public["http_status"] == 503
    assert all(revision != retained.BRANCH for operation, revision in api.calls if operation == "metadata")
    assert not downloaded.intersection(item["path"] for item in previous["files"])
