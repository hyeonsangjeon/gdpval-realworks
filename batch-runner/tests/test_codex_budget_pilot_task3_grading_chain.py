"""One offline successor chain with a shared genuine synthetic history.

Build the historical task2 grades and task3 A1/B1/C1/C2/B2 once. Mutations get
isolated copies, not a repeated full-history writer fixture. Synthetic completion
digests, commit addresses and grade run IDs are never claimed as live evidence.
All external, credential and model boundaries remain fake or blocked.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
import shutil
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_grading as grading
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as chain
from . import test_codex_budget_pilot_task3_a1_grading as a1
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — forbid every live boundary

PREFIX = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_"
RECORDED = {
    "B_r1": ("36226798976", "d2fa808126be82fd9ae6af0b154c9730825acef665151869a47c13e4574147ec"),
    "C_r1": ("36228331579", "9574cb08f562e1fc38bc1c9412793140586f5a335a4b0781af98b2c3ca3f9940"),
    "C_r2": ("36229800066", "1ae30db0cdb3f51e6a37dccaa04bfd7c376497556501802ddc505899f4a78f04"),
    "B_r2": ("36231296576", "a0e78310c78314b456c472e6f88c4d8542caf88b4c82c6b245c9fca8814f51be"),
}
FOREIGN = "e" * 40
PRIVATE = "PRIVATE https://private.invalid/path?token=PRIVATE"


class _Capture:
    """The existing CLI fixture's capture interface, scoped to history setup."""

    def __init__(self):
        self.out, self.err = io.StringIO(), io.StringIO()

    def readouterr(self):
        captured = SimpleNamespace(out=self.out.getvalue(), err=self.err.getvalue())
        for stream in (self.out, self.err):
            stream.seek(0)
            stream.truncate()
        return captured


def _select(history, suffix, api, directory, monkeypatch, *, source=a1.CONTROLLER):
    cell_id = PREFIX + suffix
    context = grading.compile_request("pilot/" + cell_id, source, grading._task3_recorded(cell_id)[1],
                                      producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    current = SimpleNamespace(api=api, workflow=history.workflow, context=context,
        request=context.requested_terminal, root=directory / "private-grade", inference=history.inferences[cell_id])
    current.transport = base.Child(current)
    monkeypatch.setattr(base, "OUTPUT", current.inference.output)
    monkeypatch.setenv("HF_TOKEN", base.TOKEN)
    # These future grading IDs are explicitly synthetic, not issued live IDs.
    chain._authorize(current, directory, monkeypatch, str(900000 + context.plan["order"].index(cell_id)))
    return current


def _invoke(current, capture, phase="plan", **changes):
    code, public = base.invoke(current, capture, phase, **{"terminal": current.request, **changes})
    assert "PRIVATE" not in json.dumps(public)
    return code, public


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    assert grading.TASK3_SUCCESSORS == {PREFIX + suffix: value for suffix, value in RECORDED.items()}
    directory = tmp_path_factory.mktemp("task3-shared-history")
    capture = _Capture()
    with pytest.MonkeyPatch.context() as patch:
        base.boundaries.__wrapped__(patch)
        compilations = a1.compilations.__wrapped__()
        compiled_cells = a1.compiled_cells.__wrapped__()
        with redirect_stdout(capture.out), redirect_stderr(capture.err):
            first = a1.case.__wrapped__(directory, patch, capture, compilations, compiled_cells)
            api = first.api
            shared = SimpleNamespace(workflow=first.workflow, rows={}, inferences={grading.TASK3_A1_CELL:
                SimpleNamespace(claim=a1.CLAIM, output=a1.OUTPUT, terminal=a1.TERMINAL,
                                claim_path=first.claim_path, terminal_path=first.terminal_path)})
            previous, previous_cell = a1.TERMINAL, first.context.cell
            for ordinal, suffix in enumerate(RECORDED, 13):
                cell_id = PREFIX + suffix
                claim_revision, output_revision, terminal_revision = (
                    f"{30_000 + ordinal * 10 + offset:040x}" for offset in (1, 2, 3))
                assert not {claim_revision, output_revision, terminal_revision}.intersection(api.trees)
                context = grading.compile_request("pilot/" + cell_id, grading.TASK3_A1_PRODUCER_SOURCE, terminal_revision)
                seeded = SimpleNamespace(context=context, api=api)
                with patch.context() as seed:
                    for key, value in {"SOURCE": grading.TASK3_A1_PRODUCER_SOURCE, "CLAIM": claim_revision,
                                       "OUTPUT": output_revision, "TERMINAL": terminal_revision}.items():
                        seed.setattr(base, key, value)
                    base._seed_outputs(seeded, directory, extra_deliverable=True)
                claim_path, terminal_path, prefix = retained._paths(context.cell)
                previous_bytes = api.trees[previous][retained._paths(previous_cell)[1]]
                previous_terminal = pilot._json_object(previous_bytes)
                seeded.claim["binding"]["github_run"] = {"id": RECORDED[suffix][0], "job": "cell", "attempt": 1}
                seeded.claim["expected_parent"] = previous
                seeded.claim["predecessor"] = {"cell_id": previous_cell["cell_id"], "terminal_commit": previous,
                    "terminal_sha256": pilot._identity(previous_bytes)["sha256"],
                    "output_commit": previous_terminal["output_commit"],
                    "manifest_sha256": previous_terminal["manifest_identity"]["sha256"]}
                seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
                files = {name: data for name, data in api.trees[output_revision].items() if name.startswith(prefix + "/")}
                api.seed(claim_revision, previous, {claim_path: retained._encoded(seeded.claim)})
                api.seed(output_revision, claim_revision, files)
                api.seed(terminal_revision, output_revision, {terminal_path: retained._encoded(seeded.terminal)})
                patch.setitem(grading.TASK3_SUCCESSORS, cell_id,
                              (RECORDED[suffix][0], pilot._digest(seeded.terminal["completion"])))
                shared.inferences[cell_id] = SimpleNamespace(claim=claim_revision, output=output_revision,
                    terminal=terminal_revision, claim_path=claim_path, terminal_path=terminal_path)
                previous, previous_cell = terminal_revision, context.cell
            api.branches[retained.BRANCH] = previous  # Every earlier selected terminal is behind this snapshot.
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            for suffix in ("A_r1", *RECORDED):
                local = directory / ("task3-" + suffix + "-writer")
                local.mkdir()
                current = _select(shared, suffix, api, local, patch)
                api.calls.clear()
                api.events.clear()
                api.reads.clear()
                before = copy.deepcopy(api)
                revision, path, terminal = writer._writer(current, capture, local, patch, "graded")
                ready = retained._read(current.root / "prepared.json")
                receipt = retained._read(current.root / "claim-receipt.json")
                assert api.events == ["grade_claim", "judge", "grade_output"] and current.transport.calls == 1
                assert all(api.trees[rev] == data for rev, data in before.trees.items())
                assert api.branches[retained.BRANCH] == previous
                shared.rows[suffix] = SimpleNamespace(before=before, revision=revision, path=path,
                    terminal=terminal, ready=ready, receipt=receipt, root=current.root, reads=list(api.reads))
            shared.api = copy.deepcopy(api)
        yield shared


@pytest.mark.parametrize("change", [
    "chain", "plan", "inference_run", "inference_source", "completion", "inference_bytes", "inference_cleanup",
    "wrong_ref", "snapshot_hash", "previous_observation", "previous_receipt", "previous_controller",
    "previous_grader_hash", "unfinished", "skipped", "controller_drift", "resolution", "restored_run",
    "missing_approval", "skipped_approval", "rerun", "approval_request", "admission_parent", "admission_hash",
    "admission_cell", "admission_cache_missing", "admission_cache_bytes", "admission_commit",
    "terminal_parent", "terminal_hash", "terminal_cell", "terminal_distinct", "predecessor_bytes",
    "predecessor_writer", "cas", "claim_lost", "publication_lost", "cleanup", "raw_output",
])
def test_recorded_task3_grading_chain(history, tmp_path, monkeypatch, capsys, change):
    row = history.rows["C_r1"]
    terminal_check = change.startswith("terminal_") or change.startswith("predecessor_")
    api = copy.deepcopy(history.api if terminal_check or change == "chain" else row.before)
    api.calls.clear()
    api.events.clear()
    api.reads.clear()
    current = _select(history, "C_r1", api, tmp_path, monkeypatch,
                      source=FOREIGN if change == "controller_drift" else a1.CONTROLLER)
    context, inference = current.context, current.inference
    assert context.plan["order"][12:17] == [grading.TASK3_A1_CELL, *grading.TASK3_SUCCESSORS]
    assert PREFIX + "A_r2" not in grading.TASK3_SUCCESSORS

    if change == "chain":
        previous_revision = grading.TASK3_A1_PREVIOUS_GRADE
        for suffix in ("A_r1", *RECORDED):
            item = history.rows[suffix]
            claim, binding = item.receipt["claim"], item.terminal["binding"]
            expected = history.inferences[PREFIX + suffix]
            ordinal = context.plan["order"].index(PREFIX + suffix)
            previous_cell = context.plan["cells"][ordinal - 1]
            assert claim["expected_parent"] == previous_revision
            assert claim["predecessor"]["revision"] == previous_revision
            assert claim["predecessor"]["cell_id"] == previous_cell["cell_id"]
            assert binding["source_sha"] == grading.TASK3_A1_PRODUCER_SOURCE
            assert binding["controller_source_sha"] == a1.CONTROLLER
            assert binding["retained"]["terminal_commit"] == expected.terminal
            assert item.ready["terminal_request"] == grading._task3_recorded(PREFIX + suffix)[1]
            assert item.ready["evidence"]["claim"]["binding"]["github_run"] == {
                "id": grading._task3_recorded(PREFIX + suffix)[0], "job": "cell", "attempt": 1}
            assert len(item.ready["evidence"]["terminal"]["completion"]["artifacts"]["deliverables"]) == 2
            assert item.terminal["outcome"] == "graded" and item.terminal["child"]["cleanup_confirmed"] is True
            assert item.terminal["invoice_complete"] is False and item.terminal["http_request_count"] is None
            assert item.ready["evidence"]["claim"]["predecessor"] == pilot._json_object(
                item.before.trees[previous_revision][grading._paths(previous_cell)[1]])["binding"]["retained"]
            if suffix != "A_r1":
                cached = item.root / "claim-verified" / (item.receipt["returned_commit"] + ".json")
                assert cached.read_bytes() == retained._encoded(claim)
            previous_revision = item.revision
        for key in ("model", "dataset", "source_pins", "grading", "order"):
            assert context.plan[key] == pilot.compile_pilot(ci.CAMPAIGN, grading.B1_PRODUCER_SOURCE)[0][key]
        assert len(context.plan["order"]) == 30
        assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
        assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
        jobs = history.workflow["jobs"]
        expression = jobs["pilot-live"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert jobs["pilot-plan"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"] == expression
        for suffix in RECORDED:
            assert expression.count('"pilot/' + PREFIX + suffix + '"') == 1
        assert '"pilot/' + PREFIX + 'A_r2"' not in expression
        assert jobs["pilot-approve-paid"]["environment"] == {"name": "grading"}
        assert jobs["pilot-approve-paid"]["permissions"] == {} and len(jobs["pilot-approve-paid"]["steps"]) == 1
        assert jobs["pilot-live"]["needs"] == ["pilot-approve-paid"] and "environment" not in jobs["pilot-live"]
        assert "needs.pilot-approve-paid.result == 'success'" in jobs["pilot-live"]["if"]
        assert jobs["pilot-live"]["permissions"] == {"contents": "read", "id-token": "write"}
        judge = next(step for step in jobs["pilot-live"]["steps"] if step.get("id") == "pilot_judge")
        assert "steps.pilot_claim.outcome == 'success'" in judge["if"]
        assert "steps.pilot_input.outputs.judge_ready == 'true'" in judge["if"] and "HF_TOKEN" not in judge.get("env", {})
        shutil.copytree(row.root, current.root)
        frozen = copy.deepcopy(api.trees)
        for phase in ("claim", "judge", "publish"):
            assert _invoke(current, capsys, phase)[0] == 2
        assert api.events == [] and current.transport.calls == 0 and api.trees == frozen
        return

    if change == "plan":
        for selector, source, producer, request in (
            ("pilot/" + PREFIX + "A_r2", a1.CONTROLLER, grading.TASK3_A1_PRODUCER_SOURCE, current.request),
            ("pilot/" + context.cell["cell_id"], a1.CONTROLLER, grading.B1_PRODUCER_SOURCE, current.request),
            ("pilot/" + context.cell["cell_id"], grading.TASK3_A1_PRODUCER_SOURCE, grading.TASK3_A1_PRODUCER_SOURCE, current.request),
            ("pilot/" + context.cell["cell_id"], a1.CONTROLLER, grading.TASK3_A1_PRODUCER_SOURCE, "9" * 64),
        ):
            with pytest.raises(output.OutputPublicationRefused):
                grading.compile_request(selector, source, request, producer_source_sha=producer)
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        assert _invoke(current, capsys)[0] == 0
        assert not current.root.exists() and api.calls == [] and current.transport.calls == 0
        return

    if terminal_check:
        terminal = copy.deepcopy(row.terminal)
        claim_revision = terminal["claim_commit"]
        claim_path = grading._paths(context.cell)[0]
        claim = pilot._json_object(api.trees[claim_revision][claim_path])
        previous_path = history.rows["B_r1"].path
        if change in {"terminal_parent", "terminal_distinct"}:
            claim["expected_parent"] = (history.rows["A_r1"].revision if change == "terminal_parent" else claim_revision)
            claim["predecessor"]["revision"] = claim["expected_parent"]
        elif change == "terminal_hash":
            claim["predecessor"]["sha256"] = "9" * 64
        elif change == "terminal_cell":
            claim["predecessor"]["cell_id"] = grading.TASK3_A1_CELL
        elif change == "predecessor_bytes":
            api.trees[claim_revision][previous_path] += b" "
        else:
            api.writers[claim_revision][previous_path] = claim_revision
        data = retained._encoded(claim)
        api.trees[claim_revision][claim_path] = api.trees[row.revision][claim_path] = data
        terminal["claim_identity"] = pilot._identity(data)  # Self-consistent tamper must still refuse.
        api.trees[row.revision][row.path] = retained._encoded(terminal)
        context.terminal_revision = inference.terminal
        frozen = copy.deepcopy(api.trees)
        with retained._session(api) as (session_api, token, deadline):
            with pytest.raises(output.OutputPublicationRefused):
                grading._grade_terminal(session_api, api.repo, row.revision, context, row.ready["entry"],
                    grading._cache(tmp_path, "terminal-proof"), token, deadline)
        assert api.trees == frozen and api.events == [] and current.transport.calls == 0
        return

    if change in {"inference_run", "inference_source"}:
        claim = pilot._json_object(api.trees[inference.claim][inference.claim_path])
        if change == "inference_run":
            claim["binding"]["github_run"]["id"] = "36228331580"
        else:
            claim["binding"]["source_sha"] = a1.CONTROLLER
        terminal = pilot._json_object(api.trees[inference.terminal][inference.terminal_path])
        terminal["claim_identity"] = pilot._identity(retained._encoded(claim))
        for tree in api.trees.values():
            if inference.claim_path in tree:
                tree[inference.claim_path] = retained._encoded(claim)
            if inference.terminal_path in tree:
                tree[inference.terminal_path] = retained._encoded(terminal)
    elif change in {"completion", "inference_cleanup"}:
        terminal = pilot._json_object(api.trees[inference.terminal][inference.terminal_path])
        terminal["completion"]["child_invocations" if change == "completion" else "cleanup_confirmed"] = (
            2 if change == "completion" else False)
        api.trees[inference.terminal][inference.terminal_path] = retained._encoded(terminal)
    elif change == "inference_bytes":
        name = retained._paths(context.cell)[2] + "/step2_inference_results.json"
        api.trees[inference.output][name] += b"PRIVATE"
    elif change == "wrong_ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif change == "snapshot_hash":
        api.trees[api.branches[retained.BRANCH]][inference.terminal_path] += b" "
    elif change.startswith("previous_"):
        item = history.rows["B_r1"]
        terminal = copy.deepcopy(item.terminal)
        binding = terminal["binding"]
        if change == "previous_observation":
            binding["retained"]["manifest_sha256"] = "9" * 64
        elif change == "previous_receipt":
            binding["publication_receipt_sha256"] = "9" * 64
        elif change == "previous_controller":
            binding["controller_source_sha"] = FOREIGN
            binding["approval_request_sha256"] = grading._approval_request_sha256(FOREIGN, "pilot/" + PREFIX + "B_r1",
                grading.TASK3_SUCCESSORS[PREFIX + "B_r1"][1], binding["github_run"],
                producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
        else:
            binding["grader_source_hash"] = "9" * 64
        name = grading._paths(context.plan["cells"][13])[0]
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][name])
        claim["binding"] = binding
        data = retained._encoded(claim)
        api.trees[terminal["claim_commit"]][name] = api.trees[item.revision][name] = data
        terminal["claim_identity"] = pilot._identity(data)
        api.trees[item.revision][item.path] = retained._encoded(terminal)
    elif change in {"unfinished", "skipped"}:
        api.branches[grading.BRANCH] = (history.rows["B_r1"].terminal["claim_commit"]
            if change == "unfinished" else history.rows["A_r1"].revision)
    elif change == "missing_approval":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    elif change == "skipped_approval":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped")
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif change == "approval_request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "9" * 64)

    frozen = copy.deepcopy(api.trees)
    code, observed = _invoke(current, capsys, "prepare")
    if change in {"inference_run", "inference_source", "completion", "inference_bytes", "inference_cleanup",
                  "wrong_ref", "snapshot_hash", "missing_approval", "skipped_approval", "rerun", "approval_request"}:
        assert code == 2 and observed["outcome"] == "refused", (observed, current.diagnostic)
        assert api.trees == frozen and api.events == [] and current.transport.calls == 0
        return
    assert code == 0 and observed["judge_ready"] is True, (observed, current.diagnostic)
    assert retained._read(current.root / "prepared.json")["terminal_revision"] == inference.terminal
    if change in {"resolution", "restored_run"}:
        path = current.root / "retained-resolution.json"
        resolution = retained._read(path)
        if change == "resolution":
            resolution["terminal_revision"] = history.inferences[PREFIX + "B_r2"].terminal
        else:
            prepared_path = current.root / "prepared.json"
            prepared = retained._read(prepared_path)
            prepared["evidence"]["claim"]["binding"]["github_run"]["id"] = "36228331580"
            resolution["evidence_sha256"] = pilot._digest(prepared["evidence"])
            prepared_path.write_bytes(retained._encoded(prepared))
        path.write_bytes(retained._encoded(resolution))
    elif change == "cas":
        api.move_before_commit = True
    elif change == "claim_lost":
        api.lost = "grade_claim"
    code, observed = _invoke(current, capsys, "claim")
    if change.startswith("previous_") or change in {
            "unfinished", "skipped", "controller_drift", "resolution", "restored_run", "cas", "claim_lost"}:
        assert code == 2 and observed["outcome"] in {"refused", "unresolved"}, (observed, current.diagnostic)
        events = list(api.events)
        assert events == (["grade_claim"] if change in {"cas", "claim_lost"} else [])
        assert _invoke(current, capsys, "judge")[0] == _invoke(current, capsys, "claim")[0] == 2
        assert api.events == events and current.transport.calls == 0
        assert all(api.trees[revision] == data for revision, data in frozen.items())
        return
    assert code == 0 and observed["outcome"] == "acknowledged", (observed, current.diagnostic)
    receipt_path = current.root / "claim-receipt.json"
    receipt = retained._read(receipt_path)
    assert receipt["claim"]["expected_parent"] == history.rows["B_r1"].revision
    if change.startswith("admission_"):
        claim = receipt["claim"]
        cache = current.root / "claim-verified" / (receipt["returned_commit"] + ".json")
        if change == "admission_parent":
            claim["expected_parent"] = claim["predecessor"]["revision"] = history.rows["A_r1"].revision
        elif change == "admission_hash":
            claim["predecessor"]["sha256"] = "9" * 64
        elif change == "admission_cell":
            claim["predecessor"]["cell_id"] = grading.TASK3_A1_CELL
        elif change == "admission_cache_missing":
            cache.rename(cache.with_suffix(".unavailable"))
        elif change == "admission_cache_bytes":
            cache.write_bytes(retained._encoded(claim) + b"PRIVATE")
        else:
            receipt["returned_commit"] = history.rows["B_r1"].revision
        receipt["claim_identity"] = pilot._identity(retained._encoded(claim))
        receipt_path.write_bytes(retained._encoded(receipt))
        reads = list(api.reads)
        assert _invoke(current, capsys, "judge")[0] == 2 and current.transport.calls == 0
        assert api.reads == reads and api.events == ["grade_claim"]
        assert all(api.trees[revision] == data for revision, data in frozen.items())
        return
    if change == "cleanup":
        current.transport.mode = "cleanup_lost"
    assert _invoke(current, capsys, "judge")[0] == (2 if change == "cleanup" else 0)
    assert current.transport.calls == 1
    if change == "publication_lost":
        api.lost = "grade_output"
    elif change == "raw_output":
        ready = retained._read(current.root / "prepared.json")
        path = current.root / "source" / ready["entry"]["grade_path"]
        payload = pilot._json_object(path.read_bytes())
        payload["judge_raw_response"] = PRIVATE
        path.write_bytes(base._json(payload))
    code, observed = _invoke(current, capsys, "publish")
    assert code == 2, (observed, current.diagnostic)
    assert observed["outcome"] == ("unresolved" if change == "publication_lost" else "refused")
    events = list(api.events)
    assert _invoke(current, capsys, "publish")[0] == _invoke(current, capsys, "judge")[0] == 2
    assert api.events == events and current.transport.calls == 1
    assert all(api.trees[revision] == data for revision, data in frozen.items())
