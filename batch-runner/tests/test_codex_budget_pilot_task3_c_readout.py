"""Only C1/C2 readouts, with one shared genuine synthetic writer prefix.

The immediate predecessor is fully verified; its older terminal is only the
intrinsic control/history proof required by the unchanged ordinary verifier.
Synthetic payloads and revisions are not actual grade or provider evidence.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest
import yaml

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
from . import test_codex_budget_pilot_task3_a1_readout as a1_reader
from . import test_codex_budget_pilot_task3_b1_readout as b1_reader
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — live boundaries blocked

PREFIX = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_"
WRITER = "69e56fc58daf50af2ac9e8b52691ffcbf5af4f96"
PRODUCER = "78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e"
OBSERVER = b1_reader.OBSERVER  # Synthetic, never a future observer authorization.
RECORDED = {
    "C_r1": (14, "36285446183", "36228331579",
             "9574cb08f562e1fc38bc1c9412793140586f5a335a4b0781af98b2c3ca3f9940", "B_r1"),
    "C_r2": (15, "36286719528", "36229800066",
             "1ae30db0cdb3f51e6a37dccaa04bfd7c376497556501802ddc505899f4a78f04", "C_r1"),
}
VARIANTS = ("graded", "partial", "failed", "ungraded", "missing_ledger", "partial_cost", "price_missing")
PRIVATE = "PRIVATE https://private.invalid/path?token=PRIVATE"


@pytest.fixture(scope="module")
def history(tmp_path_factory, *, _scenarios=VARIANTS):
    expected = {b1_reader.CELL: (13, grading.TASK3_A1_CELL, readout.TASK3_B1_WRITER_RUN),
                readout.TASK3_B2_CELL: (16, readout.TASK3_C2_CELL,
                                      {"id": "36288201352", "job": "pilot-live", "attempt": 1})}
    for suffix, (ordinal, grade_run, inference_run, request, prior) in RECORDED.items():
        cell = PREFIX + suffix
        expected[cell] = (ordinal, PREFIX + prior, {"id": grade_run, "job": "pilot-live", "attempt": 1})
        assert grading.TASK3_SUCCESSORS[cell] == (inference_run, request)
        context = readout._writer_context(request)
        assert context.cell["cell_id"] == cell and context.controller_source_sha == WRITER
        assert context.plan["reviewed_source_sha"] == PRODUCER
        assert context.terminal_revision == "" and context.terminal_request == request
        assert context.plan["order"][ordinal - 1:ordinal + 1] == [PREFIX + prior, cell]
        assert len(context.plan["order"]) == 30
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
        assert readout._writer_run(context) == expected[cell][2]
    assert readout.TASK3_SUCCESSOR_READOUTS == expected
    assert readout.TASK3_C1_CELL == PREFIX + "C_r1" and readout.TASK3_C2_CELL == PREFIX + "C_r2"
    assert readout.TASK3_A1_WRITER_SOURCE == WRITER and grading.TASK3_A1_PRODUCER_SOURCE == PRODUCER
    assert readout.TASK3_A1_WRITER_RUN == {"id": "36282221138", "job": "pilot-live", "attempt": 1}
    assert readout.TASK3_B1_WRITER_RUN == {"id": "36283710283", "job": "pilot-live", "attempt": 1}
    assert readout.CONFIG_SHA256 == "62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0"
    assert readout.TASK3_A1_GRADER_SOURCE_HASH == "0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df"

    # Build only B1's graded prefix, not its seven variants or any old test node.
    prefix = b1_reader.history.__wrapped__(tmp_path_factory, _scenarios=("graded",))
    initial = next(prefix)
    directory = tmp_path_factory.mktemp("task3-c-readout-history")
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    capture, shared = _Capture(), {}
    try:
        with pytest.MonkeyPatch.context() as patch:
            previous = initial.rows["graded"]
            input_parent = b1_reader.TERMINAL
            with redirect_stdout(capture.out), redirect_stderr(capture.err):
                for suffix, (ordinal, grade_run, inference_run, _, prior) in RECORDED.items():
                    local = directory / suffix
                    local.mkdir()
                    cell = PREFIX + suffix
                    input_claim, input_output, input_terminal, advanced = (
                        f"{50_000 + ordinal * 10 + offset:040x}" for offset in (1, 2, 3, 4))
                    api = copy.deepcopy(previous.api)
                    assert not {input_claim, input_output, input_terminal, advanced}.intersection(api.trees)
                    seed_context = grading.compile_request("pilot/" + cell, PRODUCER, input_terminal)
                    seeded = SimpleNamespace(context=seed_context, api=api)
                    with patch.context() as seed:
                        for key, value in {"SOURCE": PRODUCER, "CLAIM": input_claim,
                                           "OUTPUT": input_output, "TERMINAL": input_terminal}.items():
                            seed.setattr(base, key, value)
                        base._seed_outputs(seeded, local, extra_deliverable=True)
                    claim_path, terminal_path, input_prefix = retained._paths(seed_context.cell)
                    prior_bytes = api.trees[input_parent][retained._paths(previous.context.cell)[1]]
                    prior_inference = pilot._json_object(prior_bytes)
                    seeded.claim["binding"]["github_run"] = {"id": inference_run, "job": "cell", "attempt": 1}
                    seeded.claim["expected_parent"] = input_parent
                    seeded.claim["predecessor"] = {"cell_id": PREFIX + prior, "terminal_commit": input_parent,
                        "terminal_sha256": pilot._identity(prior_bytes)["sha256"],
                        "output_commit": prior_inference["output_commit"],
                        "manifest_sha256": prior_inference["manifest_identity"]["sha256"]}
                    seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
                    files = {name: data for name, data in api.trees[input_output].items()
                             if name.startswith(input_prefix + "/")}
                    api.seed(input_claim, input_parent, {claim_path: retained._encoded(seeded.claim)})
                    api.seed(input_output, input_claim, files)
                    api.seed(input_terminal, input_output, {terminal_path: retained._encoded(seeded.terminal)})
                    api.branches[retained.BRANCH] = input_terminal
                    api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
                    request = pilot._digest(seeded.terminal["completion"])
                    patch.setitem(grading.TASK3_SUCCESSORS, cell, (inference_run, request))
                    previous_claim = pilot._json_object(api.trees[previous.terminal["claim_commit"]][
                        grading._paths(previous.context.cell)[0]])
                    backing_cell = previous.context.plan["cells"][ordinal - 2]
                    assert previous_claim["predecessor"]["cell_id"] == backing_cell["cell_id"]
                    row = SimpleNamespace(rows={}, request=request, cell=cell, ordinal=ordinal,
                        input_claim=input_claim, input_output=input_output, input_terminal=input_terminal,
                        advanced=advanced, previous_context=copy.deepcopy(previous.context),
                        previous_revision=previous.revision, previous_path=previous.path,
                        backing_cell=backing_cell, backing_revision=previous_claim["expected_parent"],
                        backing_path=grading._paths(backing_cell)[1], historical_path=initial.historical_path)
                    for scenario in _scenarios:
                        destination = local / scenario
                        destination.mkdir()
                        current = SimpleNamespace(api=copy.deepcopy(api), workflow=workflow,
                            context=readout._writer_context(request), request=request, root=destination / "grade")
                        current.transport = base.Child(current)
                        current.api.calls.clear()
                        current.api.reads.clear()
                        current.api.events.clear()
                        with patch.context() as selected:
                            selected.setattr(base, "OUTPUT", input_output)
                            selected.setenv("HF_TOKEN", base.TOKEN)
                            task2._authorize(current, destination, selected, grade_run)
                            revision, path, terminal = writer._writer(current, capture, destination, selected, scenario)
                        claim = retained._read(current.root / "claim-receipt.json")["claim"]
                        assert claim["expected_parent"] == previous.revision
                        assert claim["predecessor"] == {"cell_id": PREFIX + prior, "revision": previous.revision,
                                                      **pilot._identity(retained._encoded(previous.terminal))}
                        assert terminal["binding"]["github_run"] == expected[cell][2]
                        assert terminal["binding"]["controller_source_sha"] == WRITER
                        assert current.transport.calls == 1 and current.api.events == ["grade_claim", "judge", "grade_output"]
                        assert all(current.api.trees[rev] == data for rev, data in api.trees.items())
                        row.rows[scenario] = SimpleNamespace(api=current.api, context=current.context,
                                                            revision=revision, path=path, terminal=terminal)
                    shared[suffix] = row
                    previous, input_parent = row.rows["graded"], input_terminal
            yield shared
    finally:
        prefix.close()


SCENARIOS = (
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
    "rerun", "private_target", "lost_response", "backing_missing", "backing_bytes", "backing_hash",
    "backing_history", "backing_carried", "backing_carried_bytes", "backing_cell", "backing_size",
    "backing_claim_alias", "backing_terminal_alias",
)


@pytest.mark.parametrize("suffix", tuple(RECORDED))
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_fixed_task3_c_grade_readouts(history, tmp_path, monkeypatch, capsys, suffix, scenario):
    _check_successor_readout(history[suffix], RECORDED[suffix], tmp_path, monkeypatch, capsys, scenario)


def _check_successor_readout(selected, recorded, tmp_path, monkeypatch, capsys, scenario):
    """Shared isolated assertions; callers supply only their fixed recorded cell."""
    row = selected.rows.get(scenario, selected.rows["graded"])
    api, terminal = copy.deepcopy(row.api), copy.deepcopy(row.terminal)
    context, revision, path = copy.deepcopy(row.context), row.revision, row.path
    claim_path = grading._paths(context.cell)[0]
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
    previous_revision, previous_path = selected.previous_revision, selected.previous_path
    previous = pilot._json_object(api.trees[previous_revision][previous_path])
    previous_claim_path = grading._paths(selected.previous_context.cell)[0]
    previous_claim = pilot._json_object(api.trees[previous["claim_commit"]][previous_claim_path])
    record = next((item for item in terminal["files"] if item["role"] == "grade_result"), None)
    grade_run = {"id": recorded[1], "job": "pilot-live", "attempt": 1}

    if scenario == "advanced":
        api.seed(selected.advanced, revision, {"unrelated/PRIVATE": b"PRIVATE unrelated later write"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = selected.advanced
    elif scenario in {"writer", "producer", "grader_hash", "config_hash", "grader_config", "approval"}:
        key = {"writer": "controller_source_sha", "producer": "source_sha", "grader_hash": "grader_source_hash",
               "config_hash": "config_hash", "grader_config": "grader_config_sha256",
               "approval": "approval_request_sha256"}[scenario]
        terminal["binding"][key] = "9" * (40 if scenario in {"writer", "producer"} else 16 if scenario == "config_hash" else 64)
    elif scenario in {"run", "job", "attempt", "typed_attempt"}:
        run = terminal["binding"]["github_run"]
        key, value = {"run": ("id", str(int(grade_run["id"]) + 1)), "job": ("job", "grade"),
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
        input_claim_path, input_path, input_prefix = retained._paths(context.cell)
        input_terminal = pilot._json_object(api.trees[selected.input_terminal][input_path])
        input_claim = pilot._json_object(api.trees[selected.input_claim][input_claim_path])
        if scenario == "inference_completion":
            input_terminal["completion"]["child_invocations"] = 2
        elif scenario == "inference_run":
            input_claim["binding"]["github_run"]["id"] = str(int(recorded[2]) + 1)
        elif scenario == "inference_source":
            input_claim["binding"]["source_sha"] = "9" * 40
        elif scenario == "inference_config":
            input_claim["binding"]["config_sha256"] = "9" * 64
        elif scenario == "inference_predecessor":
            input_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif scenario == "inference_parent":
            input_claim["expected_parent"] = "9" * 40
        elif scenario == "inference_history":
            api.writers[selected.input_terminal][input_claim_path] = selected.input_terminal
        elif scenario == "inference_bytes":
            api.trees[selected.input_output][input_prefix + "/" + output.MANIFEST] += b"PRIVATE"
        else:
            input_terminal["publication_receipt_sha256"] = "9" * 64
        data = retained._encoded(input_claim)
        for commit in (selected.input_claim, selected.input_output, selected.input_terminal):
            api.trees[commit][input_claim_path] = data
        input_terminal["claim_identity"] = pilot._identity(data)
        data = retained._encoded(input_terminal)
        api.trees[selected.input_terminal][input_path] = data
        terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
    elif scenario in {"previous_run", "previous_writer", "previous_source", "previous_grader_hash",
                      "previous_config", "previous_renderer", "previous_cleanup", "previous_inference",
                      "previous_receipt", "previous_no_child", "previous_handoff"}:
        if scenario == "previous_run":
            previous["binding"]["github_run"]["id"] = str(int(previous["binding"]["github_run"]["id"]) + 1)
            previous["binding"]["approval_request_sha256"] = grading._context_approval(
                selected.previous_context, previous["binding"]["github_run"])
        elif scenario in {"previous_writer", "previous_source", "previous_grader_hash", "previous_config"}:
            key = {"previous_writer": "controller_source_sha", "previous_source": "source_sha",
                   "previous_grader_hash": "grader_source_hash", "previous_config": "config_hash"}[scenario]
            previous["binding"][key] = "9" * (40 if scenario in {"previous_writer", "previous_source"}
                                              else 16 if scenario == "previous_config" else 64)
        elif scenario == "previous_renderer":
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
        claim["predecessor"]["cell_id"] = grading.TASK3_A1_CELL
    elif scenario == "previous_size":
        claim["predecessor"]["size"] = True
    elif scenario == "previous_type":
        claim["predecessor"] = []
    elif scenario == "previous_absent":
        api.trees[previous_revision].pop(previous_path)
    elif scenario == "previous_claim":
        api.trees[previous["claim_commit"]][previous_claim_path] += b" "
    elif scenario.startswith("backing_"):
        backing_revision, backing_path = selected.backing_revision, selected.backing_path
        if scenario == "backing_missing":
            api.trees[backing_revision].pop(backing_path)
        elif scenario == "backing_bytes":
            api.trees[backing_revision][backing_path] += b" "
        elif scenario == "backing_history":
            api.writers[backing_revision][backing_path] = previous["claim_commit"]
        elif scenario == "backing_carried":
            api.writers[previous["claim_commit"]][backing_path] = previous["claim_commit"]
        elif scenario == "backing_carried_bytes":
            api.trees[previous["claim_commit"]][backing_path] += b" "
        elif scenario == "backing_hash":
            previous_claim["predecessor"]["sha256"] = "9" * 64
        elif scenario == "backing_cell":
            previous_claim["predecessor"]["cell_id"] = selected.cell
        elif scenario == "backing_size":
            previous_claim["predecessor"]["size"] = True
        else:
            parent = previous["claim_commit"] if scenario == "backing_claim_alias" else previous_revision
            previous_claim["expected_parent"] = previous_claim["predecessor"]["revision"] = parent
    elif scenario == "ordinal":
        compile_writer = readout._writer_context

        def wrong_ordinal(request):
            other = compile_writer(request)
            if other.cell["cell_id"] == selected.cell:
                other.plan["order"][selected.ordinal - 1:selected.ordinal + 1] = [selected.cell, PREFIX + recorded[4]]
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

    if scenario in {"previous_run", "previous_writer", "previous_source", "previous_grader_hash", "previous_config",
                    "previous_renderer", "previous_cleanup", "previous_inference", "previous_receipt", "previous_no_child",
                    "previous_handoff", "backing_hash", "backing_cell", "backing_size", "backing_claim_alias", "backing_terminal_alias"}:
        data = a1_reader._store_grade(api, previous_revision, previous_path, previous, previous_claim)
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][previous_path] = data
        claim["predecessor"].update(pilot._identity(data))
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
        pytest.fail("Successor reader crossed a model, rubric, auth, admission or remote-write boundary")

    for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "inspect_branch", "_entry_contract", "_ready"):
        monkeypatch.setattr(grading, name, forbidden)
    for name in ("create_commit", "create_branch"):
        monkeypatch.setattr(api, name, forbidden)
    monkeypatch.setattr(adapter, "materialize_pilot_grading_input", forbidden)
    monkeypatch.setattr(output, "_hf_client", forbidden)
    monkeypatch.setattr(step8, "main", forbidden)
    monkeypatch.setattr("codex_budget_pilot_ungraded.record", forbidden)
    monkeypatch.setattr(base.Child, "process", forbidden)
    readers, proofs, ordinary = [], [], []
    initialize, verify_predecessor = readout._ReadOnlyGrade.__init__, readout._verify_predecessor
    grade_terminal = grading._grade_terminal

    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)

    def one_predecessor(api, current, *args, **kwargs):
        assert current.cell["cell_id"] == selected.cell, "No recursive logical predecessor verification"
        proofs.append(current.cell["cell_id"])
        return verify_predecessor(api, current, *args, **kwargs)

    def ordinary_only(api, repo, revision, current, *args, **kwargs):
        ordinary.append(current.cell["cell_id"])
        assert current.cell["cell_id"] in {selected.cell, selected.previous_context.cell["cell_id"]}
        return grade_terminal(api, repo, revision, current, *args, **kwargs)

    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    monkeypatch.setattr(readout, "_verify_predecessor", one_predecessor)
    monkeypatch.setattr(grading, "_grade_terminal", ordinary_only)
    source = WRITER if scenario == "observer_writer" else PRODUCER if scenario == "observer_producer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
                       "GITHUB_RUN_ID": "900031", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
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
            "--terminal-revision", selected.request, "--root", str(root), "--phase", phase]
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
    assert public["cell_id"] == selected.cell and public["grade_writer_run"] == grade_run
    assert public["grade_writer_source_sha"] == WRITER and public["inference_producer_source_sha"] == PRODUCER
    accepted = {"graded", "advanced", "partial", "failed", "ungraded", "missing_ledger", "partial_cost",
                "price_missing", "exclusions", "redacted_text", "replay"}
    downloads = {(operation, commit, member) for operation, commit, member, _ in api.reads if operation == "download"}
    selected_files = {("download", revision, item["path"]) for item in terminal["files"]}
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        assert public["inference_terminal"] is None and public["observer_source_sha"] == OBSERVER
        if scenario == "closed_registry":
            requests = a1_reader._unregistered_requests()
            assert len(requests) == 16 and selected.request not in requests
            assert grading.TASK3_A1_COMPLETION_SHA256 not in requests
            assert all(grading.TASK3_SUCCESSORS[cell][1] not in requests for cell in readout.TASK3_SUCCESSOR_READOUTS)
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
        assert public["grade_revision"] == revision and public["inference_terminal"] == selected.input_terminal
        assert public["inference_request_checksum"] == selected.request and public["observer_source_sha"] == OBSERVER
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
        assert len(readers) == 2 and proofs == [selected.cell]
        assert ordinary == [selected.cell, selected.previous_context.cell["cell_id"]]
        assert readers[1].revision == previous_revision
        assert sum(call == ("metadata", grading.BRANCH) for call in api.calls) == 1
        head = selected.advanced if scenario == "advanced" else revision
        assert public["observed_branch_head"] == head
        expected_downloads = selected_files | {("download", selected.backing_revision, selected.backing_path)}
        allowed_paths = {("paths", head, path)}
        expected_metadata = {("metadata", grading.BRANCH)}
        for current, current_terminal, current_revision in (
                (context, terminal, revision), (selected.previous_context, previous, previous_revision)):
            grade_claim, grade_path = grading._paths(current.cell)
            claim_revision = current_terminal["claim_commit"]
            original = pilot._json_object(api.trees[claim_revision][grade_claim])
            parent_cell = current.plan["cells"][current.plan["order"].index(current.cell["cell_id"]) - 1]
            parent_path = grading._paths(parent_cell)[1]
            expected_downloads.update({("download", current_revision, grade_path), ("download", claim_revision, grade_claim)})
            allowed_paths.update(("paths", current_revision, name) for name in (
                grade_path, grade_claim, *(item["path"] for item in current_terminal["files"])))
            allowed_paths.update({("paths", claim_revision, grade_claim), ("paths", claim_revision, parent_path),
                                  ("paths", original["expected_parent"], parent_path)})
            input_claim_path, input_path, input_prefix = retained._paths(current.cell)
            input_revision = current_terminal["binding"]["retained"]["terminal_commit"]
            input_record = pilot._json_object(api.trees[input_revision][input_path])
            expected_metadata.add(("metadata", input_revision))
            expected_downloads.update({("download", input_revision, input_path),
                ("download", input_record["claim_commit"], input_claim_path),
                ("download", input_record["output_commit"], input_prefix + "/" + output.MANIFEST)})
            allowed_paths.update({("paths", input_revision, input_path), ("paths", input_revision, input_claim_path),
                                  ("paths", input_record["claim_commit"], input_claim_path)})
            for item in input_record["output_objects"]:
                allowed_paths.update({("paths", input_revision, item["path"]),
                                      ("paths", input_record["output_commit"], item["path"])})
        actual_paths = {("paths", commit, name) for operation, commit, _, members in api.reads
                        if operation == "paths" for name in members}
        assert downloads == expected_downloads
        assert actual_paths <= allowed_paths
        assert {call for call in api.calls if call[0] == "metadata"} == expected_metadata
        assert all(operation in {"metadata", "paths", "download"} for operation, *_ in api.reads)
        assert ("paths", previous["claim_commit"], selected.backing_path) in actual_paths
        backing = pilot._json_object(api.trees[selected.backing_revision][selected.backing_path])
        for reader in readers:
            assert not hasattr(reader, "create_commit") and not hasattr(reader, "create_branch")
            for commit, forbidden_path in (
                    (previous_revision, previous["files"][0]["path"]),
                    (selected.backing_revision, grading._paths(selected.backing_cell)[0]),
                    (selected.backing_revision, retained._paths(selected.backing_cell)[1]),
                    *((selected.backing_revision, item["path"]) for item in backing["files"]),
            ):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=commit, filename=forbidden_path, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
        if scenario == "replay":
            calls = list(api.calls)
            assert grading.main(args, _test_api=api, _test_transport=transport) == 2
            repeated = capsys.readouterr()
            assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused"
            assert api.calls == calls and (api.trees, api.writers, api.parents, api.branches, api.events) == frozen
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        if scenario.startswith(("previous_", "parent_", "backing_")) or scenario in {
                "renderer", "claim_extra", "claim_format", "ordinal", "inference_predecessor"}:
            assert not downloads.intersection(selected_files)
        if scenario == "lost_response":
            assert public["http_status"] == 503
    assert all(commit != retained.BRANCH for operation, commit in api.calls if operation == "metadata")
    assert not {member for _, _, member in downloads}.intersection(
        {selected.historical_path, *(item["path"] for item in previous["files"])})
