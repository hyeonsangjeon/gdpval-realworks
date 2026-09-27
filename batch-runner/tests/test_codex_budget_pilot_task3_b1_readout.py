"""One B1-only reader selector over shared genuine synthetic writer history.

Build task2's historical prefix and task3 A1 once, then isolated B1 variants.
Synthetic files, completion digests and commit addresses are not live evidence.
All external/model boundaries are fake or blocked, including after publication.
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
from . import test_codex_budget_pilot_task3_a1_readout as a1_reader
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — every live boundary blocked

CELL = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_B_r1"
REQUEST = "d2fa808126be82fd9ae6af0b154c9730825acef665151869a47c13e4574147ec"
WRITER = "69e56fc58daf50af2ac9e8b52691ffcbf5af4f96"
PRODUCER = "78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e"
OBSERVER = "e" * 40  # Synthetic observer, never a future source authorization.
CLAIM, OUTPUT, TERMINAL, ADVANCED = (f"{40_000 + offset:040x}" for offset in range(1, 5))
PRIVATE = "PRIVATE https://private.invalid/path?token=PRIVATE"


@pytest.fixture(scope="module")
def history(tmp_path_factory, *, _scenarios=(
        "graded", "partial", "failed", "ungraded", "missing_ledger", "partial_cost", "price_missing")):
    assert readout.TASK3_B1_CELL == CELL
    assert readout.TASK3_B1_WRITER_RUN == {"id": "36283710283", "job": "pilot-live", "attempt": 1}
    assert grading.TASK3_SUCCESSORS[CELL] == ("36226798976", REQUEST)
    assert readout.TASK3_A1_WRITER_SOURCE == WRITER
    assert readout.TASK3_A1_WRITER_RUN == {"id": "36282221138", "job": "pilot-live", "attempt": 1}
    assert grading.TASK3_A1_PRODUCER_SOURCE == PRODUCER
    assert grading.TASK3_A1_COMPLETION_SHA256 == a1_reader.REQUEST
    actual = readout._writer_context(REQUEST)
    original_a1 = readout._writer_context(a1_reader.REQUEST)
    assert actual.cell["cell_id"] == CELL and actual.controller_source_sha == WRITER
    assert actual.plan["reviewed_source_sha"] == PRODUCER
    assert actual.terminal_revision == "" and actual.terminal_request == REQUEST
    assert actual.plan["order"][11:14] == [a1_reader.PREVIOUS_CELL, grading.TASK3_A1_CELL, CELL]
    assert len(actual.plan["order"]) == 30
    assert actual.run.grader_config_json == original_a1.run.grader_config_json
    assert hashlib.sha256(actual.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert readout.CONFIG_SHA256 == "62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0"
    assert readout.TASK3_A1_GRADER_SOURCE_HASH == "0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df"

    directory = tmp_path_factory.mktemp("task3-b1-readout-history")
    capture = _Capture()
    with pytest.MonkeyPatch.context() as patch:
        base.boundaries.__wrapped__(patch)
        patch.setattr(a1, "CONTROLLER", WRITER)
        compilations = a1.compilations.__wrapped__()
        compilations[OBSERVER] = pilot.compile_pilot(ci.CAMPAIGN, OBSERVER)
        compiled_cells = a1.compiled_cells.__wrapped__()
        with redirect_stdout(capture.out), redirect_stderr(capture.err):
            first = a1.case.__wrapped__(directory, patch, capture, compilations, compiled_cells)
            local = directory / "a1-writer"
            local.mkdir()
            task2._authorize(first, local, patch, readout.TASK3_A1_WRITER_RUN["id"])
            previous_revision, previous_path, previous = writer._writer(first, capture, local, patch, "graded")
            assert first.transport.calls == 1 and first.api.events == ["grade_claim", "judge", "grade_output"]
            previous_claim = retained._read(first.root / "claim-receipt.json")["claim"]
            assert previous_claim["expected_parent"] == grading.TASK3_A1_PREVIOUS_GRADE
            assert previous_claim["predecessor"]["cell_id"] == a1_reader.PREVIOUS_CELL
            assert previous["binding"]["github_run"] == readout.TASK3_A1_WRITER_RUN
            api = first.api
            seed_context = grading.compile_request("pilot/" + CELL, PRODUCER, TERMINAL)
            seeded = SimpleNamespace(context=seed_context, api=api)
            with patch.context() as seed:
                for key, value in {"SOURCE": PRODUCER, "CLAIM": CLAIM, "OUTPUT": OUTPUT, "TERMINAL": TERMINAL}.items():
                    seed.setattr(base, key, value)
                base._seed_outputs(seeded, directory, extra_deliverable=True)
            claim_path, terminal_path, prefix = retained._paths(seed_context.cell)
            previous_bytes = api.trees[a1.TERMINAL][retained._paths(first.context.cell)[1]]
            previous_inference = pilot._json_object(previous_bytes)
            seeded.claim["binding"]["github_run"] = {"id": "36226798976", "job": "cell", "attempt": 1}
            seeded.claim["expected_parent"] = a1.TERMINAL
            seeded.claim["predecessor"] = {"cell_id": grading.TASK3_A1_CELL, "terminal_commit": a1.TERMINAL,
                "terminal_sha256": pilot._identity(previous_bytes)["sha256"],
                "output_commit": previous_inference["output_commit"],
                "manifest_sha256": previous_inference["manifest_identity"]["sha256"]}
            seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
            files = {name: data for name, data in api.trees[OUTPUT].items() if name.startswith(prefix + "/")}
            api.seed(CLAIM, a1.TERMINAL, {claim_path: retained._encoded(seeded.claim)})
            api.seed(OUTPUT, CLAIM, files)
            api.seed(TERMINAL, OUTPUT, {terminal_path: retained._encoded(seeded.terminal)})
            api.branches[retained.BRANCH] = TERMINAL
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            request = pilot._digest(seeded.terminal["completion"])
            patch.setitem(grading.TASK3_SUCCESSORS, CELL, ("36226798976", request))
            shared = SimpleNamespace(rows={}, request=request, previous_context=copy.deepcopy(first.context),
                previous_revision=previous_revision, previous_path=previous_path, historical_path=first.previous_path)
            before = copy.deepcopy(api)
            for scenario in _scenarios:
                local = directory / scenario
                local.mkdir()
                current = SimpleNamespace(api=copy.deepcopy(before), workflow=first.workflow,
                    context=readout._writer_context(request), request=request, root=local / "grade")
                current.transport = base.Child(current)
                current.api.calls.clear()
                current.api.reads.clear()
                current.api.events.clear()
                with patch.context() as selected:
                    selected.setattr(base, "OUTPUT", OUTPUT)
                    selected.setenv("HF_TOKEN", base.TOKEN)
                    task2._authorize(current, local, selected, readout.TASK3_B1_WRITER_RUN["id"])
                    revision, path, terminal = writer._writer(current, capture, local, selected, scenario)
                ready = retained._read(current.root / "prepared.json")
                claim = retained._read(current.root / "claim-receipt.json")["claim"]
                assert ready["entry"]["grader_source_hash"] == readout.TASK3_A1_GRADER_SOURCE_HASH
                assert ready["entry"]["config_hash"] == readout.CONFIG_SHA256[:16]
                assert terminal["binding"]["controller_source_sha"] == WRITER
                assert terminal["binding"]["github_run"] == readout.TASK3_B1_WRITER_RUN
                assert claim["expected_parent"] == previous_revision
                assert claim["predecessor"] == {"cell_id": grading.TASK3_A1_CELL, "revision": previous_revision,
                                               **pilot._identity(retained._encoded(previous))}
                assert current.transport.calls == 1 and current.api.events == ["grade_claim", "judge", "grade_output"]
                assert all(current.api.trees[rev] == data for rev, data in before.trees.items())
                shared.rows[scenario] = SimpleNamespace(api=current.api, revision=revision, path=path,
                    terminal=terminal, context=current.context)
        yield shared


@pytest.mark.parametrize("scenario", [
    "graded", "advanced", "partial", "failed", "ungraded", "missing_ledger", "partial_cost", "price_missing",
    "exclusions", "redacted_text", "plan", "closed_registry", "replay", "writer", "run", "job", "attempt",
    "typed_attempt", "producer", "grader_hash", "config_hash", "grader_config", "renderer", "approval",
    "claim_hash", "claim_bytes", "claim_history", "claim_format", "claim_extra", "terminal_history",
    "artifact_history", "bytes", "path", "raw_judge", "private_cost_reason", "denominator_type",
    "payload_source", "ledger_pointer", "ledger_bytes", "cleanup", "no_child", "outcome", "record_type",
    "absent", "unfinished", "inference_completion", "inference_run", "inference_source", "inference_config",
    "inference_predecessor", "inference_parent", "inference_history", "inference_bytes", "inference_receipt",
    "previous_grade", "previous_run", "previous_writer", "previous_source", "previous_grader_hash",
    "previous_config", "previous_renderer", "previous_cleanup", "previous_receipt", "previous_claim",
    "previous_no_child", "previous_inference", "previous_hash", "previous_carried", "previous_carried_bytes",
    "previous_cell", "previous_size", "previous_type", "previous_absent", "previous_handoff",
    "parent_claim_alias", "parent_terminal_alias", "ordinal", "ref", "inference_ref", "observer_writer",
    "observer_producer", "observer_source", "source_preflight", "producer_override", "wrong_phase", "paid",
    "rerun", "private_target", "lost_response",
])
def test_fixed_task3_b1_grade_readout(history, tmp_path, monkeypatch, capsys, scenario):
    row = history.rows.get(scenario, history.rows["graded"])
    api, terminal = copy.deepcopy(row.api), copy.deepcopy(row.terminal)
    context, revision, path = copy.deepcopy(row.context), row.revision, row.path
    claim_path = grading._paths(context.cell)[0]
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
    previous_revision, previous_path = history.previous_revision, history.previous_path
    previous = pilot._json_object(api.trees[previous_revision][previous_path])
    previous_claim_path = grading._paths(history.previous_context.cell)[0]
    previous_claim = pilot._json_object(api.trees[previous["claim_commit"]][previous_claim_path])
    record = next((item for item in terminal["files"] if item["role"] == "grade_result"), None)

    if scenario == "advanced":
        api.seed(ADVANCED, revision, {"unrelated/PRIVATE": b"PRIVATE unrelated later write"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = ADVANCED
    elif scenario in {"writer", "producer", "grader_hash", "config_hash", "grader_config", "approval"}:
        key = {"writer": "controller_source_sha", "producer": "source_sha", "grader_hash": "grader_source_hash",
               "config_hash": "config_hash", "grader_config": "grader_config_sha256",
               "approval": "approval_request_sha256"}[scenario]
        terminal["binding"][key] = "9" * (40 if scenario in {"writer", "producer"} else 16 if scenario == "config_hash" else 64)
    elif scenario in {"run", "job", "attempt", "typed_attempt"}:
        run = terminal["binding"]["github_run"]
        key, value = {"run": ("id", "36283710284"), "job": ("job", "grade"),
                      "attempt": ("attempt", 2), "typed_attempt": ("attempt", True)}[scenario]
        run[key] = value
        terminal["binding"]["approval_request_sha256"] = grading._context_approval(context, run)
    elif scenario == "renderer":
        terminal["binding"]["renderer_fingerprint"]["libreoffice_version"] = "synthetic different renderer"
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
    elif scenario == "claim_format":
        claim["format"] = "model-free-ungraded-claim"
    elif scenario == "claim_extra":
        claim["extra"] = "PRIVATE"
    elif scenario in {"claim_history", "terminal_history", "artifact_history"}:
        if scenario == "claim_history":
            api.writers[revision][claim_path] = revision
        elif scenario == "terminal_history":
            api.writers[revision][path] = terminal["claim_commit"]
        else:
            api.writers[revision][record["path"]] = terminal["claim_commit"]
    elif scenario.startswith("inference_") and scenario != "inference_ref":
        input_claim_path, input_path, prefix = retained._paths(context.cell)
        input_terminal = pilot._json_object(api.trees[TERMINAL][input_path])
        input_claim = pilot._json_object(api.trees[CLAIM][input_claim_path])
        if scenario == "inference_completion":
            input_terminal["completion"]["child_invocations"] = 2
        elif scenario == "inference_run":
            input_claim["binding"]["github_run"]["id"] = "36226798977"
        elif scenario == "inference_source":
            input_claim["binding"]["source_sha"] = "9" * 40
        elif scenario == "inference_config":
            input_claim["binding"]["config_sha256"] = "9" * 64
        elif scenario == "inference_predecessor":
            input_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif scenario == "inference_parent":
            input_claim["expected_parent"] = "9" * 40
        elif scenario == "inference_history":
            api.writers[TERMINAL][input_claim_path] = TERMINAL
        elif scenario == "inference_bytes":
            api.trees[OUTPUT][prefix + "/" + output.MANIFEST] += b"PRIVATE"
        else:
            input_terminal["publication_receipt_sha256"] = "9" * 64
        data = retained._encoded(input_claim)
        for commit in (CLAIM, OUTPUT, TERMINAL):
            api.trees[commit][input_claim_path] = data
        input_terminal["claim_identity"] = pilot._identity(data)
        data = retained._encoded(input_terminal)
        api.trees[TERMINAL][input_path] = data
        terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
    elif scenario in {"previous_run", "previous_writer", "previous_source", "previous_grader_hash",
                      "previous_config", "previous_renderer", "previous_cleanup", "previous_inference",
                      "previous_receipt", "previous_no_child", "previous_handoff"}:
        if scenario == "previous_run":
            previous["binding"]["github_run"]["id"] = "36282221139"
            previous["binding"]["approval_request_sha256"] = grading._context_approval(
                history.previous_context, previous["binding"]["github_run"])
        elif scenario in {"previous_writer", "previous_source", "previous_grader_hash", "previous_config"}:
            key = {"previous_writer": "controller_source_sha", "previous_source": "source_sha",
                   "previous_grader_hash": "grader_source_hash", "previous_config": "config_hash"}[scenario]
            previous["binding"][key] = "9" * (40 if scenario in {"previous_writer", "previous_source"}
                                              else 16 if scenario == "previous_config" else 64)
        elif scenario == "previous_renderer":
            # Valid on its own; same-controller B1 must still reject disagreement.
            previous["binding"]["renderer_fingerprint"]["pymupdf_version"] = "synthetic other version"
        elif scenario == "previous_cleanup":
            previous["child"]["cleanup_confirmed"] = False
        elif scenario == "previous_no_child":
            previous["child"]["entry_invoked"] = False
        elif scenario == "previous_receipt":
            previous["binding"]["publication_receipt_sha256"] = "9" * 64
        elif scenario == "previous_handoff":
            previous_claim["expected_parent"] = previous_claim["predecessor"]["revision"] = "9" * 40
        else:
            previous["binding"]["retained"]["terminal_commit"] = "9" * 40
        data = a1_reader._store_grade(api, previous_revision, previous_path, previous, previous_claim)
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][previous_path] = data
        claim["predecessor"].update(pilot._identity(data))
    elif scenario in {"previous_grade", "parent_claim_alias", "parent_terminal_alias"}:
        parent = {"previous_grade": "9" * 40, "parent_claim_alias": terminal["claim_commit"],
                  "parent_terminal_alias": revision}[scenario]
        claim["expected_parent"] = claim["predecessor"]["revision"] = parent
    elif scenario == "previous_hash":
        claim["predecessor"]["sha256"] = "9" * 64
    elif scenario == "previous_carried":
        api.writers[terminal["claim_commit"]][previous_path] = terminal["claim_commit"]
    elif scenario == "previous_carried_bytes":
        api.trees[terminal["claim_commit"]][previous_path] += b" "
    elif scenario == "previous_cell":
        claim["predecessor"]["cell_id"] = a1_reader.PREVIOUS_CELL
    elif scenario == "previous_size":
        claim["predecessor"]["size"] = True
    elif scenario == "previous_type":
        claim["predecessor"] = []
    elif scenario == "previous_absent":
        api.trees[previous_revision].pop(previous_path)
    elif scenario == "previous_claim":
        api.trees[previous["claim_commit"]][previous_claim_path] += b" "
    elif scenario == "ordinal":
        compile_writer = readout._writer_context

        def wrong_ordinal(request):
            other = compile_writer(request)
            if other.cell["cell_id"] == CELL:
                other.plan["order"][12:14] = [CELL, grading.TASK3_A1_CELL]
            return other

        monkeypatch.setattr(readout, "_writer_context", wrong_ordinal)
    elif scenario == "ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif scenario == "inference_ref":
        monkeypatch.setattr(retained, "BRANCH", "pilot-inference-20260924-03")
    elif scenario == "private_target":
        api.private = False
    elif scenario == "lost_response":
        api.read_fail = True

    a1_reader._store_grade(api, revision, path, terminal, claim)
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
        pytest.fail("B1 reader crossed a model, rubric, auth, admission or remote-write boundary")

    for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "inspect_branch",
                 "_entry_contract", "_ready"):
        monkeypatch.setattr(grading, name, forbidden)
    for name in ("create_commit", "create_branch"):
        monkeypatch.setattr(api, name, forbidden)
    monkeypatch.setattr(adapter, "materialize_pilot_grading_input", forbidden)
    monkeypatch.setattr(output, "_hf_client", forbidden)
    monkeypatch.setattr(step8, "main", forbidden)
    monkeypatch.setattr("codex_budget_pilot_ungraded.record", forbidden)
    monkeypatch.setattr(base.Child, "process", forbidden)
    readers, proofs = [], []
    initialize, verify_predecessor = readout._ReadOnlyGrade.__init__, readout._verify_predecessor

    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)

    def one_predecessor(api, selected, *args, **kwargs):
        assert selected.cell["cell_id"] == CELL, "No recursive A1-to-A2 proof in a B1 readout"
        proofs.append(selected.cell["cell_id"])
        return verify_predecessor(api, selected, *args, **kwargs)

    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    monkeypatch.setattr(readout, "_verify_predecessor", one_predecessor)
    source = WRITER if scenario == "observer_writer" else PRODUCER if scenario == "observer_producer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
                       "GITHUB_RUN_ID": "900021", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
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
        args.extend(["--producer-source-sha", PRODUCER])

    def source_check(plan, parent):
        assert plan["reviewed_source_sha"] == OBSERVER
        if scenario == "source_preflight":
            raise ValueError(PRIVATE)

    transport = SimpleNamespace(require_source=source_check)
    code = grading.main(args, _test_api=api, _test_transport=transport)
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
    assert public["cell_id"] == CELL and public["grade_writer_run"] == readout.TASK3_B1_WRITER_RUN
    assert public["grade_writer_source_sha"] == WRITER and public["inference_producer_source_sha"] == PRODUCER
    accepted = {"graded", "advanced", "partial", "failed", "ungraded", "missing_ledger", "partial_cost",
                "price_missing", "exclusions", "redacted_text", "replay"}
    downloaded = {member for operation, _, member, _ in api.reads if operation == "download"}
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        assert public["inference_terminal"] is None and public["observer_source_sha"] == OBSERVER
        if scenario == "closed_registry":
            requests = a1_reader._unregistered_requests()
            assert all(value[1] in requests for cell, value in {
                **grading.TASK4_RETAINED, **grading.TASK5_RETAINED}.items()
                if cell not in {grading.TASK4_A1_CELL, grading.TASK4_A2_CELL,
                                grading.TASK4_B1_CELL, *readout.TASK4_SUCCESSOR_READOUTS})
            assert history.request not in requests and grading.TASK3_A1_COMPLETION_SHA256 not in requests
            for request in requests:
                closed = list(args)
                closed[5] = request
                assert grading.main(closed, _test_api=api) == 2
                refused = capsys.readouterr()
                assert not refused.out and json.loads(refused.err)["outcome"] == "refused"
                assert not api.calls and not root.exists()
    elif scenario in accepted:
        assert code == 0 and public["outcome"] == "verified_retained_grade", public
        assert public["grade_state"] == (scenario if scenario in {"partial", "failed", "ungraded"} else "graded")
        assert public["grade_revision"] == revision and public["inference_terminal"] == TERMINAL
        assert public["inference_request_checksum"] == history.request and public["observer_source_sha"] == OBSERVER
        assert len({OBSERVER, WRITER, PRODUCER}) == 3
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
        elif scenario in {"partial_cost", "price_missing"}:
            receipt = public["ledger_derived_cost"]
            assert receipt["model_calls"] == (2 if scenario == "partial_cost" else 1)
            assert receipt["usage"] == {"input_tokens": 111, "output_tokens": 23, "cached_input_tokens": 17,
                                        "reasoning_tokens": 8, "audio_input_tokens": None, "audio_output_tokens": None}
            if scenario == "partial_cost":
                assert receipt["known_cost_usd"] > 0 and receipt["missing_reasons"] == ["call_reachability_unknown"]
            else:
                assert receipt["known_cost_usd"] is None and receipt["estimated_cost_usd"] is None
                assert receipt["missing_reasons"] == ["price_missing"]
        else:
            assert public["ledger_derived_cost"]["estimated_cost_usd"] is None
            assert public["ledger_derived_cost"]["missing_reasons"] == ["call_reachability_unknown"]
        for receipt in (public["recorded_task_cost"], public["recorded_summary_cost"], public["ledger_derived_cost"]):
            if receipt is not None:
                assert receipt["invoice_complete"] is False and receipt["http_request_count"] is None
        assert len(readers) == 2 and proofs == [CELL]  # B1 and immediate A1 only, no historical A2 reader.
        assert readers[1].revision == previous_revision
        assert sum(call == ("metadata", grading.BRANCH) for call in api.calls) == 1
        assert public["observed_branch_head"] == (ADVANCED if scenario == "advanced" else revision)
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
        if scenario == "replay":
            calls = list(api.calls)
            assert grading.main(args, _test_api=api, _test_transport=transport) == 2
            repeated = capsys.readouterr()
            assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused"
            assert api.calls == calls and (api.trees, api.writers, api.parents, api.branches, api.events) == frozen
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        if scenario.startswith("previous_") or scenario.startswith("parent_") or scenario in {
                "renderer", "claim_extra", "claim_format", "ordinal", "inference_predecessor"}:
            assert not downloaded.intersection(item["path"] for item in terminal["files"])
        if scenario == "lost_response":
            assert public["http_status"] == 503
    assert all(revision != retained.BRANCH for operation, revision in api.calls if operation == "metadata")
    assert history.historical_path not in downloaded
    assert not downloaded.intersection(item["path"] for item in previous["files"])
