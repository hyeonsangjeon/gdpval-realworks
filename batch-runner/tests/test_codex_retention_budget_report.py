"""One offline metadata/report proof; no old budget or lifecycle selector runs."""

import ast
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time

# Reuse the established collection-time imports and autouse offline boundary.
from .test_codex_budget_pilot_retention import offline  # noqa: F401
from .retention_budget_report_evidence import (
    BUDGET_POINTS, MEASUREMENT_LIMITS, PRIOR_CODE_ONLY_ARTIFACTS, PROJECTOR_SHA256,
    assert_consolidated_report, before_success_budget_observations, canonical_digest, expected_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
TASK4 = "3baa0009-5a60-4ae8-ae99-4955cb328ff3"
TASK5 = "0818571f-5ff7-4d39-9d2c-ced5ae44299e"
FROZEN_SOURCE = {
    ".github/workflows/codex-retention-first-cell.yml": "d9f2f5cd2b8789721f76bb7384f11f17c05594536c7cc70ab5050179043f382c",
    "batch-runner/codex_retention_first_cell_budget.py": "043100017cb1db06f74b562b5feca1a6de8e3eed99ff153645e9a33b3481d975",
    "batch-runner/codex_retention_fresh_r1_result_intake.py": "631dd2a76faecd28ae65bdbe69d755f598aa4b025cfc66a8280872c2f3a2bc96",
    "batch-runner/codex_retention_result_intake.py": "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196",
    "batch-runner/codex_budget_pilot_grade_readout.py": "96d0dd63f5d67aa9f54e95615b4467357aa65ea5223418be47e120cc3ad5e815",
    # Current-checkout observer facade, not a historical writer/receipt binding.
    "batch-runner/codex_retention_grade_readout.py": "0e2b920875fb5597406e267a8b838e80fcd55d6958ded1e4286516036cb44038",
    "batch-runner/codex_retention_fixed_grade.py": "3d771582eaaf0d4cfab8e8858db1c7e557473459c2dd5769a837f059f516a684",
    "batch-runner/codex_retention_keep_r2_grade.py": "bb8d1b3a46824a2597f31fe6567531fc59deabb79af87e85d98fd1a08ae3988e",
    "batch-runner/core/codex_task_deadline.py": "7af4af22903af0a97fdcfb33c318616f105bc50ae1cd8054daeb55e75989550f",
    "batch-runner/core/codex_runner.py": "b2324e8193754d6bf88242463b8327f9560d5e4c480066182a42b57fc4b23232",
}


def test_consolidated_budget_report_preserves_all_eight_observations(monkeypatch):
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("metadata/report selector crossed a live or process boundary")

    assert subprocess.Popen.__name__ == socket.create_connection.__name__ == "blocked"
    assert socket.socket.connect.__name__ == "blocked"
    assert not {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN",
                "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY"}.intersection(os.environ)
    for owner, names in (
        (subprocess, ("run", "Popen", "check_call", "check_output")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (os, ("system",)), (time, ("sleep",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)

    readout_bytes = (ROOT / "tasks/codex_budget_pilot/retention_diagnostic_readout.json").read_bytes()
    report_bytes = (ROOT / "tasks/codex_budget_pilot/RETENTION_DIAGNOSTIC_REPORT.md").read_bytes()
    readout, report = json.loads(readout_bytes), report_bytes.decode("utf-8")
    prior = before_success_budget_observations(readout)
    print("BOUNDARY only cells[0]/cells[3] observations added; accepted prior semantic identity and exact supplied success receipts preserved")

    # Reconcile every older canonical comparison at its original scope. These
    # metadata operations do not invoke any of the consumed budget selectors.
    historical_scopes = (
        ((1, 2, 4, 5, 6, 7), "aaea03354686ada4e716b4eb0eb24b9c1ab964d8e4e4e4210e5b960519dfdd89"),
        ((1, 2, 4, 5), "eaefa00b1a8db81b9a12dd914135c0fbf2c279d09697b4cb1cb499e983d369de"),
        ((1, 2, 4, 5, 6), "bb8749e42de933000f126299616bdc2235c63bf420f6a4ebf5a7c16512924965"),
        ((1, 2), "6b3830c740ffe6a540990c299887eb4f205e82eb42e71cce8b99e8c3e7feeffe"),
    )
    for removed, digest in historical_scopes:
        older = deepcopy(prior)
        for index in removed:
            older["cells"][index].pop("current_budget_observation")
        assert canonical_digest(older) == digest
    for name in ("task5_fresh_r2", "task5_keep_r2", "task5_r1", "task4_fresh", "task4_keep_r2", "first_cell"):
        source = (ROOT / f"batch-runner/tests/test_codex_retention_{name}_budget.py").read_text()
        ast.parse(source)  # Parse the coupled edits without collecting/running old tests.
        assert "before_success_budget_observations" in source
        assert "successful_task4_keep_budgets_unobserved" not in source
        assert "Both successful Task4 KEEP budgets remain unobserved" not in source
    legacy_source = (ROOT / "batch-runner/tests/test_codex_retention_first_cell_budget.py").read_text()
    for digest in PRIOR_CODE_ONLY_ARTIFACTS.values():
        assert digest in legacy_source  # Keep old raw identities explicitly historical.
    assert "current_artifact_hashes.items()" in legacy_source

    cells = readout["cells"]
    assert len(cells) == len({row["cell_id"] for row in cells}) == 8
    labels = ((TASK4, "keep", 1), (TASK4, "fresh", 1), (TASK4, "fresh", 2), (TASK4, "keep", 2),
              (TASK5, "fresh", 1), (TASK5, "keep", 1), (TASK5, "keep", 2), (TASK5, "fresh", 2))
    expected_calls = (10, 39, 39, 6, 18, 13, 38, 1)
    expected_costs = ("0.409894", "0.303358", "0.29944", "0.22195", "2.576093", "0.413364", "0.847605", "0.13489")
    for index, (row, (task, retention, repetition)) in enumerate(zip(cells, labels)):
        assert (row["ordinal"], row["task_id"], row["retention_bundle"], row["repetition"]) == (index, task, retention, repetition)
        assert row["cell_id"] == f"{task}_retention_bundle_v1_{retention}_r{repetition}"
        assert row["status"] == ("succeeded" if index in (0, 3) else "failed")
        assert row["cleanup_confirmed"] is True and row["producer_grade"] is None
        assert row["producer"]["attempt"] == 1
        assert row["preceding_registered_inference_terminal"] == (None if index == 0 else cells[index - 1]["terminal"]["revision"])
        observation = row["current_budget_observation"]
        assert observation["mode"] == "observe_budget" and observation["outcome"] == "budget_observation_verified"
        assert observation["approval_execution_skipped"] is True
        assert observation["terminal_commit"] == row["terminal"]["revision"]
        assert observation["output_commit"] == row["output_manifest"]["revision"]
        assert observation["budget_projector_sha256"] == PROJECTOR_SHA256
        assert observation["status"] == row["status"] and observation["grade"] is None
        assert type(observation["exit_code"]) is int and observation["exit_code"] == (0 if index in (0, 3) else 1)
        assert observation["result_body_verified"] is True and observation["payload_verification_scope"] == "inference_result_only"
        assert observation["writer_acknowledgment"] == "not_established"
        assert observation["recorded_publication_acknowledged"] is True
        for key in ("payload_bodies_verified", "ledger_body_verified", "deliverable_bodies_verified", "grading_input_ready",
                    "fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                    "live_read_repeated_here", "replay_authorized"):
            assert observation[key] is False
        assert observation["measurement_limits"] == MEASUREMENT_LIMITS
        for key in ("detailed_failure", "recovery_exposure"):
            assert observation["unavailable"][key] == {
                "status": "unavailable", "value": None, "reason": "not_recorded_in_terminal_controls"}
        snapshot = observation["inference_budget_snapshot"]
        assert snapshot == expected_snapshot(index)
        for field in ("total_seconds", "attempts_admitted", "native_resumes"):
            assert type(snapshot[field]) is int
        for field in ("started_unix", "expires_unix", "remaining_seconds", "wait_seconds"):
            assert type(snapshot[field]) is float
        if index not in (0, 3):
            assert row["grade"] is None and row["grade_missing_reason"] == "failed_no_successful_intake_or_grade"
            assert row["terminal_details"]["budget"] is None
            assert row["terminal_details"]["missing_reason"] == "not_recorded_in_terminal_controls"
            assert row["read"]["payload_bodies_verified"] is False
        accounting = row["inference"]
        assert (accounting["model_calls"], accounting["known_cost_usd"]) == (expected_calls[index], expected_costs[index])
        assert type(accounting["model_calls"]) is int and accounting["invoice_complete"] is False
        assert "call_reachability_unknown" in accounting["missing_reasons"]
        for field in ("estimated_cost_usd", "runtime_cost_usd", "http_request_count"):
            assert accounting[field] is None
    assert cells[5]["current_budget_observation"]["supplied_request_binding"]["materialized_grader_source_sha256"] is None
    # Older r2 receipts were not supplied with the later source/reader keys.
    for index in (6, 7):
        assert "source_sha" not in cells[index]["current_budget_observation"]
        assert "historical_reader_sha256" not in cells[index]["current_budget_observation"]
    assert cells[0]["inference"]["usage"] is None
    assert cells[0]["inference"]["usage_missing_reason"] == "not_in_current_retained_summary"
    assert sum(row["inference"]["model_calls"] for row in cells) == readout["totals"]["recorded_inference_model_calls"] == 164
    assert sum(Decimal(row["inference"]["known_cost_usd"]) for row in cells) == Decimal("5.206594")
    assert readout["totals"]["known_partial_inference_usd"] == "5.206594"
    assert (readout["totals"]["cells"], readout["totals"]["succeeded"], readout["totals"]["failed"],
            readout["totals"]["numeric_grades"], readout["totals"]["null_failure_grades"]) == (8, 2, 6, 2, 6)
    for index, values in ((0, ("30.6", "68.0", "54.64", 93)), (3, ("30.35", "67.44", "54.20", 91))):
        grade = cells[index]["grade"]
        assert (grade["score"], grade["included_percent"], grade["full_percent"], grade["accounting"]["model_calls"]) == values
        assert (grade["included_max"], grade["full_max"], grade["excluded_items"], grade["excluded_max"]) == ("45", "56", 9, "11")
        assert grade["accounting"]["missing_reasons"] == ["price_missing"]
        assert grade["accounting"]["invoice_complete"] is False
        for key in ("known_cost_usd", "model_cost_usd", "estimated_cost_usd", "runtime_cost_usd", "http_request_count"):
            assert grade["accounting"][key] is None
    print("BOUNDARY eight actual native-budget snapshots; two successes/six null failure grades; 164 calls/partial USD5.206594; historical missingness retained")

    assert_consolidated_report(report, readout)
    for key in ("complete_costs", "causal_question_resolved", "all_Project5_work_complete", "new_live_authority"):
        assert readout["closeout"][key] is False
    assert readout["closeout"]["original_pilot"] == {
        "state": "closed_unchanged", "original_cell_ids": 30, "epoch04_outcomes": 24,
        "epoch04_graded": 18, "epoch04_model_free_ungraded": 6, "frozen_epoch03_failures": 6}
    pilot = "tasks/codex_budget_pilot/REPORT.md"
    assert hashlib.sha256((ROOT / pilot).read_bytes()).hexdigest() == PRIOR_CODE_ONLY_ARTIFACTS[pilot]
    for path, digest in FROZEN_SOURCE.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert not effects
    print(json.dumps({
        "scope": "consolidated_retention_budget_metadata_report_only", "budget_observations": len(BUDGET_POINTS),
        "new_observation_ordinals": [0, 3], "historical_snapshots_preserved": len(historical_scopes),
        "frozen_source_files": len(FROZEN_SOURCE), "old_selectors_invoked": 0,
        "network_model_writer_child_paid_effects": len(effects),
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "readout_sha256": hashlib.sha256(readout_bytes).hexdigest(),
    }, sort_keys=True))
