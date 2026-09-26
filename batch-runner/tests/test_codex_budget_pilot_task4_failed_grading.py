"""Reproduce the failed-input policy gap, without enabling task4 grading.

The recorded future-controller requests remain unregistered. Separately, the
existing same-source/immutable-revision route diagnoses failed materialization.
It is not an executable future-controller request or proof that generic B1
admission enforces the recorded route's immediate-grade-predecessor rule.
All bytes/revisions below are synthetic; no live payload is reconstructed.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as grading
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import step2_run_inference as step2
from core import codex_runner
from core.codex_runtime_config import CodexProviderSettings
from core.cost_receipts import BUCKET_PROBLEM_SOLVING, CostReceiptLedger, load_receipt_price_table
from core.result_fingerprint import validate_inference_result_fingerprint
from . import test_codex_budget_pilot_failure_category as native
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as approval
from . import test_codex_budget_pilot_task3_grading_chain as chain
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block every live boundary

PRODUCER = "78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e"
FUTURE_CONTROLLER = "d" * 40  # Diagnostic refusal only, never a source to dispatch.
PREFIX = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_"
PREVIOUS = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r2"
RECORDED = {
    "A_r1": ("36234320019", "a913f0236e801e31ab7c0f58c8545ad6375d7092c06fa77f839225d03efe52d8"),
    "B_r1": ("36235926112", "f3546942ebac25c3c3cd1788dfb792a80e3e10f465999bebf7730fb651cb2bde"),
}


def _failed_row(context):
    """Real native error -> Step2 row/public serializer -> ledger; fake turn only."""
    config = json.loads(context.grading.dispatch.runs[0].config_json)
    captured = io.StringIO()
    with tempfile.TemporaryDirectory(prefix=".task4-error-writer-", dir=pilot.ROOT.parent) as directory, \
            pytest.MonkeyPatch.context() as patch, redirect_stdout(captured), redirect_stderr(captured):
        native.no_runtime_auth_or_publication.__wrapped__(patch)
        host = Path(directory)
        patch.setenv("GDPVAL_CODEX_RUN_ROOT", str(host / "native"))
        patch.setenv("TMPDIR", str(host / "tmp"))
        with CostReceiptLedger(host / "synthetic.sqlite3", run_id=context.cell["run_id"],
                               price_table=load_receipt_price_table()) as ledger:
            runner = codex_runner.CodexAgentRunner(
                CodexProviderSettings(endpoint="https://synthetic.openai.azure.com/openai/v1/", model="gpt-5.4"),
                cost_ledger=ledger, run_id=context.cell["run_id"], condition_name="condition_a", timeout=1800,
                verify_runtime=False, preflight_auth=False)
            runner.open_runtime = lambda _: SimpleNamespace(close=lambda: None)
            runner.start_thread = lambda *a, **k: SimpleNamespace(
                id="synthetic-thread", turn=lambda _: SimpleNamespace(id="synthetic-turn"))
            runner._await_turn = lambda _: codex_runner.TurnObservation(
                failure="synthetic unknown failure", usage=SimpleNamespace(total=SimpleNamespace(
                    input_tokens=17, output_tokens=9, cached_input_tokens=5,
                    reasoning_output_tokens=4, cache_write_input_tokens=0)))
            produced = []

            def execute(**kwargs):
                kwargs.pop("verbose")
                result = runner.run(**kwargs)
                produced.append(result)
                return result

            try:
                row = step2._execute_single_task(
                    {"task_id": context.cell["task_id"], "instruction": "Synthetic failed input.",
                     "reference_files": []}, config["condition_a"], SimpleNamespace(execute=execute),
                    "codex_foundry", None, "gpt-5.4", run_id=context.cell["run_id"],
                    condition_name="condition_a", upload_root=host / "upload")
            finally:
                runner.close()
            assert len(produced) == 1 and produced[0]["success"] is False
            assert row["status"] == "error" and row["deliverable_files"] == []
            row["problem_solving_cost"] = ledger.receipt_for(context.cell["task_id"], BUCKET_PROBLEM_SOLVING).as_dict()
            ledger_path = host / "synthetic.jsonl"
            ledger.export_jsonl(ledger_path)
            return step2._public_persisted_results([row])[0], ledger_path.read_bytes()


@pytest.fixture(scope="module")
def failed_pair(tmp_path_factory):
    # Build the error before the shared grading fixture blocks runner creation.
    # No successful A1 is produced and then relabeled as a failure.
    prototype = grading.compile_request("pilot/" + PREFIX + "A_r1", PRODUCER, "8" * 40)
    row, ledger = _failed_row(prototype)
    histories = chain.history.__wrapped__(tmp_path_factory)
    history = next(histories)  # Genuine historical writers once, not prior test selectors.
    try:
        with pytest.MonkeyPatch.context() as patch:
            directory = tmp_path_factory.mktemp("task4-failed-input-history")
            api = copy.deepcopy(history.api)
            old_trees, old_writers = copy.deepcopy(api.trees), copy.deepcopy(api.writers)
            previous = history.inferences[PREVIOUS].terminal
            previous_context = grading.compile_request("pilot/" + PREVIOUS, PRODUCER, previous)
            patch.setenv("HF_TOKEN", base.TOKEN)
            with retained._session(api) as (client, token, deadline):
                evidence = grading._retained_input(previous_context, client, api.repo,
                    grading._cache(directory, "previous"), token, deadline)
            assert evidence["claim"]["binding"]["github_run"] == {
                "id": "36232859421", "job": "cell", "attempt": 1}
            assert grading.TASK3_SUCCESSORS[PREVIOUS][0] == "36232859421"
            rows = {}
            for ordinal, suffix in enumerate(RECORDED, 18):
                claim_revision, output_revision, terminal_revision = (
                    f"{50_000 + ordinal * 10 + offset:040x}" for offset in (1, 2, 3))
                assert not {claim_revision, output_revision, terminal_revision}.intersection(api.trees)
                context = grading.compile_request("pilot/" + PREFIX + suffix, PRODUCER, terminal_revision)
                current = SimpleNamespace(context=context, api=api)
                failed = suffix == "A_r1"
                with patch.context() as seed:
                    for key, value in {"SOURCE": PRODUCER, "CLAIM": claim_revision,
                                       "OUTPUT": output_revision, "TERMINAL": terminal_revision}.items():
                        seed.setattr(base, key, value)
                    base._seed_outputs(current, directory, failed=failed,
                        producer_row=row if failed else None, producer_ledger=ledger if failed else None,
                        reason="child_nonzero_exit" if failed else None)
                claim_path, terminal_path, prefix = retained._paths(context.cell)
                # Replace only the fixture's initial bootstrap scaffold before
                # validation with the actual synthetic canonical predecessor.
                current.claim["binding"]["github_run"] = {"id": RECORDED[suffix][0], "job": "cell", "attempt": 1}
                current.claim["expected_parent"] = previous
                current.claim["predecessor"] = evidence["observation"]
                current.terminal["claim_identity"] = pilot._identity(retained._encoded(current.claim))
                files = {name: data for name, data in api.trees[output_revision].items() if name.startswith(prefix + "/")}
                api.seed(claim_revision, previous, {claim_path: retained._encoded(current.claim)})
                api.seed(output_revision, claim_revision, files)
                api.seed(terminal_revision, output_revision, {terminal_path: retained._encoded(current.terminal)})
                with retained._session(api) as (client, token, deadline):
                    evidence = grading._retained_input(context, client, api.repo,
                        grading._cache(directory, suffix), token, deadline)
                assert evidence["claim"] == current.claim
                assert pilot._digest(evidence["terminal"]["completion"]) != RECORDED[suffix][1]
                rows[suffix] = SimpleNamespace(context=context, claim=claim_revision, output=output_revision,
                    terminal=terminal_revision, claim_path=claim_path, terminal_path=terminal_path,
                    evidence=evidence, payload=current.payload, files=current.files)
                previous = terminal_revision
            assert all(api.trees[rev] == data for rev, data in old_trees.items())
            assert all(api.writers[rev] == data for rev, data in old_writers.items())
            api.branches[retained.BRANCH] = previous
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            yield SimpleNamespace(api=api, rows=rows, workflow=history.workflow)
    finally:
        histories.close()


@pytest.mark.parametrize("change", [
    "failed_prepare", "failed_claim", "failed_judge", "failed_publish", "failed_reprepare", "b1_prepare",
    "closed_a1", "closed_b1", "unregistered_others", "failed_source", "failed_bytes", "failed_cleanup",
    "failed_acknowledgment", "missing_approval", "changed_request", "workflow_guards",
])
def test_failed_task4_a1_grading_policy_gap(failed_pair, tmp_path, monkeypatch, capsys, change):
    api = copy.deepcopy(failed_pair.api)
    selected = "B_r1" if change in {"b1_prepare", "closed_b1"} else "A_r1"
    row = failed_pair.rows[selected]
    current = SimpleNamespace(api=api, context=copy.deepcopy(row.context), workflow=failed_pair.workflow,
                              root=tmp_path / "private-grade")
    current.transport = base.Child(current)
    base._synthetic_rubric(current, monkeypatch)
    monkeypatch.setenv("HF_TOKEN", base.TOKEN)
    approval._authorize(current, tmp_path, monkeypatch, "990018" if selected == "A_r1" else "990019")
    api.calls.clear()
    api.events.clear()
    api.reads.clear()
    context = current.context
    assert context.controller_source_sha == context.plan["reviewed_source_sha"] == PRODUCER
    assert context.terminal_request is None  # Generic diagnostic, not a closed source exception.
    assert context.plan["order"][17:20] == [PREVIOUS, PREFIX + "A_r1", PREFIX + "B_r1"]
    assert len(context.plan["order"]) == 30 and context.cell["cell_id"] == PREFIX + selected
    assert json.loads(context.run.grader_config_json)["judge"]["model"] == "gpt-5.6-sol"
    assert all(grading._paths(failed_pair.rows[suffix].context.cell)[1] not in api.trees[api.branches[grading.BRANCH]]
               for suffix in RECORDED)  # No fabricated A1/B1 grade terminal.

    if change.startswith("closed_") or change == "unregistered_others":
        cells = [PREFIX + selected] if change.startswith("closed_") else context.plan["order"][20:]
        for cell in cells:
            request = RECORDED[selected][1] if change.startswith("closed_") else "0" * 64
            code, public = base.invoke(current, capsys, "prepare", selector="pilot/" + cell,
                source=FUTURE_CONTROLLER, producer=PRODUCER, terminal=request)
            assert code == 2 and public["reason"] == "closed_retained_producer_binding_required"
        assert api.calls == [] and not current.root.exists() and current.transport.calls == 0
        return
    if change == "workflow_guards":
        steps = {step["name"]: step for step in failed_pair.workflow["jobs"]["pilot-live"]["steps"] if "name" in step}
        for name in ("Validate grading OIDC identity", "Validate fixed grader Azure route",
                     "Grading Azure login (OIDC)", "Verify grading OIDC session", "Verify fixed grader model connection",
                     "Claim one private grading admission with parent CAS", "Invoke exactly the compiled fixed Step8 command once"):
            assert "steps.pilot_input.outputs.judge_ready == 'true'" in steps[name]["if"]
        publication = steps["Retain validated private grade and accounting on the grading branch"]["if"]
        assert "steps.pilot_judge.outcome != 'skipped'" in publication
        assert "steps.pilot_claim.outcome == 'success'" in publication
        assert api.calls == [] and not current.root.exists()
        return

    if change == "failed_source":
        claim = pilot._json_object(api.trees[row.claim][row.claim_path])
        claim["binding"]["source_sha"] = FUTURE_CONTROLLER
        data = retained._encoded(claim)
        for revision in (row.claim, row.output, row.terminal):
            api.trees[revision][row.claim_path] = data
        terminal = pilot._json_object(api.trees[row.terminal][row.terminal_path])
        terminal["claim_identity"] = pilot._identity(data)
        api.trees[row.terminal][row.terminal_path] = retained._encoded(terminal)
    elif change == "failed_bytes":
        path = retained._paths(context.cell)[2] + "/step2_inference_results.json"
        for revision in (row.output, row.terminal):
            api.trees[revision][path] += b" "
    elif change in {"failed_cleanup", "failed_acknowledgment"}:
        terminal = pilot._json_object(api.trees[row.terminal][row.terminal_path])
        if change == "failed_cleanup":
            terminal["completion"]["cleanup_confirmed"] = False
        else:
            terminal["publication_acknowledged"] = False
        api.trees[row.terminal][row.terminal_path] = retained._encoded(terminal)
    elif change == "missing_approval":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped")
    elif change == "changed_request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64)
    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches))
    code, public = base.invoke(current, capsys, "prepare")
    if change in {"failed_source", "failed_bytes", "failed_cleanup", "failed_acknowledgment",
                  "missing_approval", "changed_request"}:
        assert code == 2 and public["outcome"] == "refused", (public, current.diagnostic)
    else:
        assert code == 0, (public, current.diagnostic)
        prepared = retained._read(current.root / "prepared.json")
        assert prepared["evidence"] == row.evidence
        if change == "b1_prepare":
            assert public["judge_ready"] is True and public["outcome"] == "prepared"
            assert prepared["evidence"]["claim"]["predecessor"] == failed_pair.rows["A_r1"].evidence["observation"]
            # No generic B1 claim: it would not prove recorded-route adjacency.
        else:
            assert public["outcome"] == "ungraded" and public["judge_ready"] is False
            assert public["reason"] == "retained_result_unsuccessful_ungraded"
            assert prepared["grading_state"] == "UNRUN" and "entry" not in prepared and "rubric" not in prepared
            assert not (current.root / "source").exists()
            assert prepared["materialization"]["task_status"] == "error"
            completion = prepared["evidence"]["terminal"]["completion"]
            assert completion["status"] == "failed" and completion["exit_code"] == 1
            assert completion["reason"] == "child_nonzero_exit"
            original = (current.root / "original/step2_inference_results.json").read_bytes()
            assert original == row.files["step2_inference_results.json"]
            payload = json.loads(original)
            validate_inference_result_fingerprint(payload)
            assert payload["results"][0]["status"] == "error" and payload["results"][0]["deliverable_files"] == []
            if change in {"failed_claim", "failed_judge", "failed_publish"}:
                before = list(api.calls)
                code, public = base.invoke(current, capsys, change.removeprefix("failed_"))
                assert code == 2 and public["reason"] == "bound_native_materialization_required"
                assert api.calls == before
            elif change == "failed_reprepare":
                before = (current.root / "prepared.json").read_bytes()
                assert base.invoke(current, capsys, "prepare")[0] == 2
                assert (current.root / "prepared.json").read_bytes() == before
    assert (api.trees, api.writers, api.parents, api.branches) == frozen
    assert api.events == [] and current.transport.calls == 0
    assert not any(name in {"commit", "branch"} for name, _ in api.calls)
    assert not any((current.root / name).exists() for name in (
        "claim-reserved.json", "claim-receipt.json", "judge-reserved.json", "judge-receipt.json",
        "publication-reserved.json", "publication-receipt.json"))
