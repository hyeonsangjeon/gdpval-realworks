"""Only the fixed historical task2 A2 may precede current-source task3 A1.

The existing fake children/HF generate a synthetic six-cell task2 history with
real compilation, serialization, admission, deadlines and retention. These are
not recovered historical bytes. Only the expected completion digest is replaced
by that synthetic writer's digest, after asserting every production pin.
"""

import copy
import json
import time

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retention
import codex_ci_input_intake as intake
from core.codex_task_deadline import CodexTaskDeadlineControl
from . import test_codex_budget_pilot_retention as base
from .test_codex_budget_pilot_retention import offline, scenario  # noqa: F401

PRODUCER = "e7a28db07ebe10d6508b9256137763cc82f9a1d1"
SOURCE = "d" * 40  # Synthetic new execution source, never a future merge SHA.
PREDECESSOR = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r2"
SELECTED = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r1"
RECORDED_RUN = {"id": "36202190875", "job": "cell", "attempt": 1}


@pytest.fixture(scope="module")
def compiled_contracts():
    return {source: pilot.compile_pilot(ci.CAMPAIGN, source) for source in (PRODUCER, SOURCE)}


@pytest.mark.parametrize("change", [
    "accepted", "historical_source", "inference_run", "completion", "config", "inputs", "bytes",
    "cleanup", "publication", "advanced_head", "unretained_predecessor", "wrong_predecessor", "other_cell",
    "wrong_ref", "public_target", "foreign_target", "compiler_drift", "cas_race", "claim_lost",
    "output_lost", "terminal_lost", "current_source", "rerun",
])
def test_fixed_task3_a1_historical_predecessor(scenario, compiled_contracts, capsys, monkeypatch, change):
    assert retention.TASK3_A1_PREDECESSOR == {
        "cell_id": PREDECESSOR, "source_sha": PRODUCER, "github_run": RECORDED_RUN,
        "completion_sha256": "d6d1309c2c81ef17ce18158bc9014ce962ce7dcd267f95f328b279050d4fd15e",
    }
    real_compile = pilot.compile_pilot

    def compile_contract(campaign, source):
        if campaign == ci.CAMPAIGN and source in compiled_contracts:
            return copy.deepcopy(compiled_contracts[source])
        return real_compile(campaign, source)

    monkeypatch.setattr(pilot, "compile_pilot", compile_contract)
    monkeypatch.setattr(base, "SOURCE", PRODUCER)
    s = base.case.__wrapped__(scenario, monkeypatch)
    s.argv[s.argv.index("--reviewed-source-sha") + 1] = PRODUCER
    old_local = {}
    for ordinal in range(6, 12):
        if ordinal != 6:
            base.select_fresh(s, monkeypatch, ordinal=ordinal)
        s.api.calls.clear()
        s.api.commits.clear()
        s.api.events.clear()
        if ordinal == 11:
            monkeypatch.setenv("GITHUB_RUN_ID", RECORDED_RUN["id"])
        base.finalized(s, capsys, monkeypatch)
        assert base.boundary(s, capsys, monkeypatch, "--retain")[0] == 0
        assert s.api.commits == ["admission", "output", "terminal"]
        old_local.update({path: path.read_bytes() for path in s.root.rglob("*") if path.is_file()})
    old_plan, old_head = base.read_plan(s), s.api.head
    old_cell = old_plan["cells"][11]
    assert old_cell["cell_id"] == s.selected == PREDECESSOR
    claim_path, terminal_path, _ = retention._paths(old_cell)
    terminal = json.loads(s.api.trees[old_head][terminal_path])
    original_claim = json.loads(s.api.trees[terminal["claim_commit"]][claim_path])
    assert original_claim["binding"]["source_sha"] == PRODUCER
    assert original_claim["binding"]["github_run"] == RECORDED_RUN
    synthetic_completion = pilot._load(s.envelope)
    assert terminal["completion"] == synthetic_completion
    monkeypatch.setitem(retention.TASK3_A1_PREDECESSOR, "completion_sha256", pilot._digest(synthetic_completion))

    # New local roots, source, run and clock; no predecessor state is adopted.
    monkeypatch.setattr(base, "SOURCE", SOURCE)
    for key in ("GITHUB_SHA", "PILOT_WORKFLOW_SHA"):
        monkeypatch.setenv(key, SOURCE)
    s.argv[s.argv.index("--reviewed-source-sha") + 1] = SOURCE
    base.select_fresh(s, monkeypatch, ordinal=13 if change == "other_cell" else 12)
    s.transport.clock.now += 1000
    plan = base.read_plan(s)
    cell = next(row for row in plan["cells"] if row["cell_id"] == s.selected)
    assert len(plan["order"]) == 30 and plan["order"] == old_plan["order"]
    assert plan["order"][11:13] == [PREDECESSOR, SELECTED]
    assert all(plan[key] == old_plan[key] for key in ("source_pins", "dataset", "model", "grading"))
    assert plan["reviewed_source_sha"] == plan["ci"]["host"]["workflow_sha"] == SOURCE
    assert ci.CAMPAIGN == "budget_pilot_ci_20260925_04"
    assert retention.BRANCH == "pilot-inference-20260925-04" and ci.GRADING_BRANCH == "pilot-grades-20260925-04"
    assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
    assert plan["model"]["deployment"] == "gpt-5.4" and plan["model"]["reasoning_effort"] == "xhigh"
    assert plan["model"]["route_profile"] == "direct-v1"
    assert intake.BUNDLE_SHA256 == "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3"
    config = json.loads(pilot._read_bytes(s.root / cell["roles"]["config"]))
    assert config["execution"]["timeout"] == 1800 and config["execution"]["max_retries"] == 3
    assert config["execution"]["resume_max_rounds"] == 0
    assert config["output"] == {"publish_to_hf": False, "submit_to_evals": False}
    if change != "other_cell":
        assert cell["cell_id"] == SELECTED and cell["index"] == 12
        assert cell["config_sha256"] == "35a23a8842d378a8326ec8483553145ee5c63c9c63a383be3eb903bda77136a3"
        assert config["execution"]["codex"]["task_deadline"] == {"condition": "A", "repetition": 1}
        assert CodexTaskDeadlineControl("A", 1).max_attempts == 4

    if change == "accepted":
        # The known old same-source path must still reject this historical A2.
        cache = s.host / "same-source-refusal"
        cache.mkdir(mode=0o700)
        with pytest.raises(output.OutputPublicationRefused, match="^claim_host_policy_mismatch$"):
            retention._terminal(s.api, s.api.repo, old_head, plan, old_cell,
                retention._local(plan, cell, s.root)[0], cache, base.TOKEN, time.monotonic() + 60)
        assert base.cli(s, "--resume", "--execute") == 2 and not s.transport.calls
        capsys.readouterr()

    if change in {"historical_source", "inference_run", "config"}:
        claim = copy.deepcopy(original_claim)
        if change == "historical_source":
            claim["binding"]["source_sha"] = claim["binding"]["host"]["workflow_sha"] = "e" * 40
        elif change == "inference_run":
            claim["binding"]["github_run"]["id"] = "999999"
        else:
            claim["binding"]["config_sha256"] = "e" * 64
        data = retention._encoded(claim)
        s.api.trees[terminal["claim_commit"]][claim_path] = s.api.trees[old_head][claim_path] = data
        terminal["claim_identity"] = pilot._identity(data)
    elif change == "completion":
        terminal["completion"]["child_invocations"] = 2  # Valid shape, different fixed content.
    elif change == "cleanup":
        terminal["completion"]["cleanup_confirmed"] = False
    elif change == "publication":
        terminal["publication_acknowledged"] = False
    elif change == "wrong_predecessor":
        terminal["completion"]["cell_id"] = SELECTED
    elif change == "bytes":
        name = next(row["path"] for row in terminal["output_objects"] if row["path"].endswith(".txt"))
        s.api.trees[terminal["output_commit"]][name] += b"changed synthetic bytes"
    elif change == "inputs":
        path = s.root / "ci-inputs.json"
        inputs = pilot._load(path)
        inputs["files_sha256"] = "e" * 64
        pilot._save(path, inputs)
    elif change == "compiler_drift":
        def drift(campaign, source):
            compiled, parent, specs = compile_contract(campaign, source)
            if source == PRODUCER:
                compiled["dispatcher_sha256"] = "e" * 64
            return compiled, parent, specs
        monkeypatch.setattr(pilot, "compile_pilot", drift)
    s.api.trees[old_head][terminal_path] = retention._encoded(terminal)
    if change == "advanced_head":
        s.api.head = "e" * 40
        s.api.trees[s.api.head] = dict(s.api.trees[old_head])
        s.api.writers[s.api.head] = dict(s.api.writers[old_head])
        s.api.parents[s.api.head] = old_head
    elif change == "unretained_predecessor":
        s.api.head = terminal["output_commit"]
    elif change == "wrong_ref":
        monkeypatch.setattr(retention, "BRANCH", ci.GRADING_BRANCH)
    elif change == "public_target":
        s.api.private = False
    elif change == "foreign_target":
        s.api.id_matches = False
    elif change == "current_source":
        monkeypatch.setenv("GITHUB_SHA", PRODUCER)
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")

    remote_before = copy.deepcopy((s.api.trees, s.api.parents, s.api.writers))
    s.api.calls.clear()
    s.api.commits.clear()
    s.api.events.clear()
    s.api.move_before_commit = change == "cas_race"
    s.api.lost = "admission" if change == "claim_lost" else None
    accepted = change in {"accepted", "output_lost", "terminal_lost"}
    code, record = base.boundary(s, capsys, monkeypatch, "--admit")
    assert code == (0 if accepted else 2) and not s.transport.calls
    if accepted:
        assert record["outcome"] == "acknowledged" and record["source_sha"] == SOURCE
        receipt = retention._read(base.cell_root(s) / retention.ADMISSION_RECEIPT)
        claim = receipt["claim"]
        assert claim["binding"]["source_sha"] == claim["binding"]["host"]["workflow_sha"] == SOURCE
        assert claim["binding"]["cell_id"] == SELECTED and claim["binding"]["ordinal"] == 12
        assert claim["binding"]["github_run"] != original_claim["binding"]["github_run"]
        assert claim["expected_parent"] == claim["predecessor"]["terminal_commit"] == old_head
        assert claim["predecessor"]["cell_id"] == PREDECESSOR
        assert s.api.parents[receipt["returned_commit"]] == old_head
        observed = retention._read(base.cell_root(s) / retention.SERVER_OBSERVATION)
        assert observed == {"observation": "verified_server_terminal_state", "predecessor": claim["predecessor"],
                            "writer_response_delivery": "not_asserted"}
        assert base.cli(s, "--resume", "--execute") == 0
        assert s.transport.model_admissions == [(SELECTED, 0)] and s.transport.peak == 1
        assert set(s.transport.source_checks) == {SOURCE}
        assert (s.root / cell["roles"]["checkout"] / "synthetic-source").read_bytes() == SOURCE.encode()
        state = base.read_state(s, SELECTED)
        store = pilot._deadline(s.root, cell, state, s.transport)
        try:
            deadline = store.for_task(cell["task_id"]).as_record()
            assert deadline["condition"] == "A" and deadline["repetition"] == 1
            assert deadline["total_seconds"] == 10800 and deadline["attempt_seconds"] == 1800
            assert deadline["started_unix"] == 1_001_000 and deadline["expires_unix"] == 1_011_800
            assert deadline["session_policy"] == "fresh_session" and deadline["attempts_admitted"] == 1
        finally:
            store.close()
        completion_bytes = s.envelope.read_bytes()
        s.api.lost = {"output_lost": "output", "terminal_lost": "terminal"}.get(change)
        assert base.boundary(s, capsys, monkeypatch, "--retain")[0] == (0 if change == "accepted" else 2)
        assert s.envelope.read_bytes() == completion_bytes and base.read_state(s, SELECTED) == state
        assert s.api.commits == ["admission", "output"] + ([] if change == "output_lost" else ["terminal"])
        if change == "accepted":
            cache = s.host / "verify-task3-terminal"
            cache.mkdir(mode=0o700)
            evidence = retention._terminal(s.api, s.api.repo, s.api.head, plan, cell,
                retention._local(plan, cell, s.root)[0], cache, base.TOKEN, time.monotonic() + 60)
            assert evidence["terminal"]["completion"] == pilot._load(s.envelope)
            assert evidence["manifest"]["source_sha"] == SOURCE and evidence["claim"] == claim
        else:
            path = base.cell_root(s) / retention.TERMINAL_RECEIPT
            before = (path.read_bytes(), list(s.api.calls))
            assert json.loads(before[0])["outcome"] == "unresolved"
            assert json.loads(before[0])["terminal_commit"] is None
            assert base.boundary(s, capsys, monkeypatch, "--retain")[0] == 2
            assert (path.read_bytes(), s.api.calls) == before
    else:
        assert base.cli(s, "--resume", "--execute") == 2 and not s.transport.calls
        if change in {"current_source", "rerun"}:
            assert s.api.calls == [] and not (base.cell_root(s) / retention.ADMISSION_RESERVED).exists()
        else:
            expected = {
                "historical_source": "claim_host_policy_mismatch", "inference_run": "recorded_task3_predecessor_run_mismatch",
                "completion": "recorded_task3_predecessor_completion_mismatch", "config": "claim_identity_mismatch",
                "inputs": "claim_identity_mismatch", "bytes": "remote_output_size_mismatch",
                "cleanup": "hf_operation_failed", "publication": "terminal_confirmation_contract_mismatch",
                "advanced_head": "retention_control_history_mismatch", "unretained_predecessor": "terminal_or_claim_missing",
                "wrong_predecessor": "terminal_completion_identity_mismatch", "other_cell": "terminal_or_claim_missing",
                "wrong_ref": "terminal_confirmation_contract_mismatch", "public_target": "existing_exact_private_repository_required",
                "foreign_target": "existing_exact_private_repository_required", "compiler_drift": "claim_identity_mismatch",
                "cas_race": "hf_http_failed", "claim_lost": "hf_transport_failed",
            }
            assert record["reason"] == expected[change]
            assert record["outcome"] == ("unresolved" if change in {"cas_race", "claim_lost"} else "refused")
            reserved = base.cell_root(s) / retention.ADMISSION_RESERVED
            path = base.cell_root(s) / retention.ADMISSION_RECEIPT
            before = (reserved.read_bytes(), path.read_bytes(), list(s.api.calls))
            assert base.boundary(s, capsys, monkeypatch, "--admit")[0] == 2
            assert (reserved.read_bytes(), path.read_bytes(), s.api.calls) == before
        assert s.api.commits == (["admission"] if change in {"cas_race", "claim_lost"} else [])
    assert all(base.read_state(s, row["cell_id"]) == pilot._cell_state(plan, row)
               for row in plan["cells"] if row["cell_id"] != s.selected)
    assert all(path.read_bytes() == data for path, data in old_local.items())
    for current, previous in zip((s.api.trees, s.api.parents, s.api.writers), remote_before):
        assert all(current[key] == value for key, value in previous.items())
