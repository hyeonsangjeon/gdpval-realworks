"""Tests for fixed-denominator paired Agentic Sandbox endpoints."""

import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from core.agentic_budget import AgenticBudgetLedger, BudgetCaps
from core.agentic_endpoints import WALL_CAP_MS, compute_paired_endpoints


def _fixture():
    task_ids = [f"task-{index:02d}" for index in range(20)]
    baseline = []
    treatment = []
    maxima = {
        task_id: [
            {"rubric_item_id": "quality", "max_score": 5},
            {"rubric_item_id": "accuracy", "max_score": 5},
        ]
        for task_id in task_ids
    }
    grades = {
        "schema_version": "1.1",
        "tasks": [
            {
                "task_id": task_id,
                "error": None,
                "items": [
                    {
                        "rubric_item_id": "accuracy",
                        "verdict": "pass",
                        "awarded_score": 5,
                        "score_excluded": False,
                    },
                    {
                        "rubric_item_id": "quality",
                        "verdict": "pass",
                        "awarded_score": 5,
                        "score_excluded": False,
                    },
                ],
            }
            for task_id in task_ids
        ],
    }
    for index, task_id in enumerate(task_ids):
        baseline.append({
            "task_id": task_id,
            "status": "success",
            "deliverable_files": ["report.txt"],
            "observability": {
                "substrate": {"sha256": "a" * 64},
                "sandbox": {"final_status": "ok"},
                "execution_metrics": {
                    "time_to_valid_artifact_ms": (index + 1) * 100,
                },
                "budget_metrics": {"conservative_cost_usd": 0.1},
            },
        })
        treatment.append({
            "task_id": task_id,
            "status": "error" if index == 19 else "success",
            "deliverable_files": [] if index == 19 else ["report.txt"],
            "observability": {
                "substrate": {"sha256": "a" * 64},
                "agentic_metrics": {
                    "usage_complete": True,
                    "terminal_error_category": (
                        "finalize_not_called" if index == 19 else None
                    ),
                    "finalize_attempts": 0 if index == 19 else 1,
                    "conservative_cost_usd": 0.2,
                },
                "execution_metrics": {
                    "time_to_valid_artifact_ms": (
                        None if index == 19 else (index + 1) * 100
                    ),
                },
            },
        })
        baseline[-1]["observability"]["budget_metrics"][
            "usage_complete"
        ] = True
    return task_ids, baseline, treatment, maxima, grades


def _ledger_inputs(tmp_path, task_ids, baseline_cost="0.1", treatment_cost="0.2"):
    ledger = AgenticBudgetLedger(tmp_path / "budget.sqlite3")
    caps = BudgetCaps(100, 1_000_000, 1_000_000, Decimal("100"))
    scope_maps = {}
    for condition, cost in (
        ("baseline", baseline_cost), ("treatment", treatment_cost)
    ):
        scopes = {}
        for task_id in task_ids:
            scope = json.dumps(["paired-run", condition, task_id], separators=(",", ":"))
            ledger.reserve_many(
                scopes={
                    scope: caps,
                    json.dumps(
                        ["condition", "paired-run", condition],
                        separators=(",", ":"),
                    ): caps,
                    json.dumps(
                        ["paired_run", "paired-run"], separators=(",", ":")
                    ): caps,
                },
                request_id=f"{condition}:{task_id}",
                input_tokens=0,
                output_tokens=0,
                cost_usd=Decimal(cost),
            )
            scopes[task_id] = scope
        scope_maps[condition] = scopes
    return ledger, scope_maps["baseline"], scope_maps["treatment"]


def test_fixed_denominator_completion_quality_timing_and_cost(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(
        tmp_path, task_ids
    )

    result = compute_paired_endpoints(
        expected_task_ids=task_ids,
        baseline_results=baseline,
        treatment_results=treatment,
        rubric_maxima=maxima,
        baseline_grades=grades,
        treatment_grades=grades,
        budget_ledger=ledger,
        paired_run_id="paired-run",
        baseline_task_scopes=baseline_scopes,
        treatment_task_scopes=treatment_scopes,
    )

    assert result["denominator_tasks"] == 20
    assert result["common_substrate_sha256"] == "a" * 64
    assert result["completion"]["baseline"] == 1.0
    assert result["completion"]["treatment"] == 0.95
    assert result["completion"]["delta_percentage_points"] == -5.0
    assert result["quality"]["baseline"]["task_macro"] == 100.0
    assert result["quality"]["treatment"]["task_macro"] == 95.0
    assert result["quality"]["treatment"]["expected_item_denominator"] == 40
    assert result["timing"]["treatment_values_ms"][-1] == WALL_CAP_MS
    assert result["timing"]["baseline_p95_ms"] == 1900
    assert result["timing"]["treatment_p95_ms"] == 1900
    assert result["timing"]["p95_ratio"] == 1.0
    assert result["cost"]["baseline_mean_usd"] == 0.1
    assert result["cost"]["treatment_mean_usd"] == 0.2
    assert result["cost"]["ratio"] == 2.0


def test_missing_grade_items_remain_in_fixed_item_denominator(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(
        tmp_path, task_ids
    )
    treatment_grades = json.loads(json.dumps(grades))
    treatment_grades["tasks"][0]["items"] = []

    result = compute_paired_endpoints(
        expected_task_ids=task_ids,
        baseline_results=baseline,
        treatment_results=treatment,
        rubric_maxima=maxima,
        baseline_grades=grades,
        treatment_grades=treatment_grades,
        budget_ledger=ledger,
        paired_run_id="paired-run",
        baseline_task_scopes=baseline_scopes,
        treatment_task_scopes=treatment_scopes,
    )

    quality = result["quality"]["treatment"]
    assert quality["expected_item_denominator"] == 40
    assert quality["item_state_counts"]["missing"] == 2
    assert quality["task_macro"] == 90.0


def test_incomplete_usage_forces_completion_to_zero(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(tmp_path, task_ids)
    baseline[0]["observability"]["budget_metrics"]["usage_complete"] = False
    treatment[1]["observability"]["agentic_metrics"]["usage_complete"] = False

    result = compute_paired_endpoints(
        expected_task_ids=task_ids,
        baseline_results=baseline,
        treatment_results=treatment,
        rubric_maxima=maxima,
        baseline_grades=grades,
        treatment_grades=grades,
        budget_ledger=ledger,
        paired_run_id="paired-run",
        baseline_task_scopes=baseline_scopes,
        treatment_task_scopes=treatment_scopes,
    )

    assert result["completion"]["baseline_by_task"][task_ids[0]] == 0
    assert result["completion"]["treatment_by_task"][task_ids[1]] == 0


def test_condition_specific_first_valid_timing_is_authoritative(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(tmp_path, task_ids)
    baseline[0]["observability"]["execution_metrics"] = {}
    baseline[0]["observability"]["budget_metrics"][
        "time_to_valid_artifact_ms"
    ] = 321
    treatment[0]["observability"]["execution_metrics"] = {}
    treatment[0]["observability"]["agentic_metrics"][
        "time_to_valid_artifact_ms"
    ] = 654

    result = compute_paired_endpoints(
        expected_task_ids=task_ids,
        baseline_results=baseline,
        treatment_results=treatment,
        rubric_maxima=maxima,
        baseline_grades=grades,
        treatment_grades=grades,
        budget_ledger=ledger,
        paired_run_id="paired-run",
        baseline_task_scopes=baseline_scopes,
        treatment_task_scopes=treatment_scopes,
    )

    assert result["timing"]["baseline_values_ms"][0] == 321
    assert result["timing"]["treatment_values_ms"][0] == 654

    treatment[0]["observability"]["execution_metrics"] = {
        "time_to_valid_artifact_ms": 999,
    }
    with pytest.raises(ValueError, match="timing metrics disagree"):
        compute_paired_endpoints(
            expected_task_ids=task_ids,
            baseline_results=baseline,
            treatment_results=treatment,
            rubric_maxima=maxima,
            baseline_grades=grades,
            treatment_grades=grades,
            budget_ledger=ledger,
            paired_run_id="paired-run",
            baseline_task_scopes=baseline_scopes,
            treatment_task_scopes=treatment_scopes,
        )


def test_endpoint_rejects_intersection_or_duplicate_denominators(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(
        tmp_path, task_ids
    )
    with pytest.raises(ValueError, match="differ from frozen"):
        compute_paired_endpoints(
            expected_task_ids=task_ids,
            baseline_results=baseline[:-1],
            treatment_results=treatment,
            rubric_maxima=maxima,
            baseline_grades=grades,
            treatment_grades=grades,
            budget_ledger=ledger,
            paired_run_id="paired-run",
            baseline_task_scopes=baseline_scopes,
            treatment_task_scopes=treatment_scopes,
        )
    with pytest.raises(ValueError, match="20 unique"):
        compute_paired_endpoints(
            expected_task_ids=task_ids[:-1] + [task_ids[0]],
            baseline_results=baseline,
            treatment_results=treatment,
            rubric_maxima=maxima,
            baseline_grades=grades,
            treatment_grades=grades,
            budget_ledger=ledger,
            paired_run_id="paired-run",
            baseline_task_scopes=baseline_scopes,
            treatment_task_scopes=treatment_scopes,
        )


def test_zero_baseline_cost_ratio_is_json_safe(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(
        tmp_path, task_ids, baseline_cost="0"
    )

    endpoints = compute_paired_endpoints(
        expected_task_ids=task_ids,
        baseline_results=baseline,
        treatment_results=treatment,
        rubric_maxima=maxima,
        baseline_grades=grades,
        treatment_grades=grades,
        budget_ledger=ledger,
        paired_run_id="paired-run",
        baseline_task_scopes=baseline_scopes,
        treatment_task_scopes=treatment_scopes,
    )

    assert endpoints["cost"]["ratio"] == "infinity"


def test_endpoint_rejects_substrate_parity_drift(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(
        tmp_path, task_ids
    )
    treatment[0]["observability"]["substrate"]["sha256"] = "b" * 64

    with pytest.raises(ValueError, match="not byte-identical"):
        compute_paired_endpoints(
            expected_task_ids=task_ids,
            baseline_results=baseline,
            treatment_results=treatment,
            rubric_maxima=maxima,
            baseline_grades=grades,
            treatment_grades=grades,
            budget_ledger=ledger,
            paired_run_id="paired-run",
            baseline_task_scopes=baseline_scopes,
            treatment_task_scopes=treatment_scopes,
        )


def test_endpoint_rejects_cross_run_scope_and_missing_aggregate_link(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(tmp_path, task_ids)
    cross_run = dict(treatment_scopes)
    cross_run[task_ids[0]] = json.dumps(
        ["other-run", "treatment", task_ids[0]], separators=(",", ":")
    )
    with pytest.raises(ValueError, match="ledger scope is invalid"):
        compute_paired_endpoints(
            expected_task_ids=task_ids,
            baseline_results=baseline,
            treatment_results=treatment,
            rubric_maxima=maxima,
            baseline_grades=grades,
            treatment_grades=grades,
            budget_ledger=ledger,
            paired_run_id="paired-run",
            baseline_task_scopes=baseline_scopes,
            treatment_task_scopes=cross_run,
        )

    unlinked_scope = json.dumps(
        ["paired-run", "treatment", task_ids[0]], separators=(",", ":")
    )
    unlinked_ledger = AgenticBudgetLedger(tmp_path / "unlinked.sqlite3")
    unlinked_ledger.reserve(
        scope=unlinked_scope,
        request_id="unlinked",
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal("0.2"),
        caps=BudgetCaps(1, 1, 1, Decimal("1")),
    )
    with pytest.raises(ValueError, match="treatment aggregate reservations"):
        from core.agentic_endpoints import _validate_aggregate_reservation_sets

        _validate_aggregate_reservation_sets(
            unlinked_ledger,
            "paired-run",
            {},
            {task_ids[0]: unlinked_scope},
        )


def test_endpoint_rejects_extra_aggregate_reservation(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(tmp_path, task_ids)
    caps = BudgetCaps(100, 1_000_000, 1_000_000, Decimal("100"))
    ledger.reserve_many(
        scopes={
            json.dumps(
                ["condition", "paired-run", "baseline"], separators=(",", ":")
            ): caps,
            json.dumps(["paired_run", "paired-run"], separators=(",", ":")): caps,
        },
        request_id="unapproved-extra-task-request",
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal("0.1"),
    )

    with pytest.raises(ValueError, match="baseline aggregate reservations"):
        compute_paired_endpoints(
            expected_task_ids=task_ids,
            baseline_results=baseline,
            treatment_results=treatment,
            rubric_maxima=maxima,
            baseline_grades=grades,
            treatment_grades=grades,
            budget_ledger=ledger,
            paired_run_id="paired-run",
            baseline_task_scopes=baseline_scopes,
            treatment_task_scopes=treatment_scopes,
        )


def test_quality_joins_item_ids_and_handles_penalty_and_grade_errors(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(tmp_path, task_ids)
    maxima[task_ids[0]].append({
        "rubric_item_id": "penalty",
        "max_score": -5,
    })
    for document in (grades,):
        document["tasks"][0]["items"].insert(1, {
            "rubric_item_id": "penalty",
            "verdict": "pass",
            "awarded_score": -5,
            "score_excluded": False,
        })
    treatment_grades = json.loads(json.dumps(grades))
    treatment_grades["tasks"][1]["error"] = "judge transport failed"
    treatment_grades["tasks"][1]["items"][0]["verdict"] = "judge_error"

    result = compute_paired_endpoints(
        expected_task_ids=task_ids,
        baseline_results=baseline,
        treatment_results=treatment,
        rubric_maxima=maxima,
        baseline_grades=grades,
        treatment_grades=treatment_grades,
        budget_ledger=ledger,
        paired_run_id="paired-run",
        baseline_task_scopes=baseline_scopes,
        treatment_task_scopes=treatment_scopes,
    )

    baseline_quality = result["quality"]["baseline"]
    treatment_quality = result["quality"]["treatment"]
    assert baseline_quality["task_scores"][0] == 50.0
    assert treatment_quality["task_error_count"] == 1
    assert treatment_quality["item_state_counts"]["judge_error"] == 2
    assert treatment_quality["task_errors_by_task"] == {
        task_ids[1]: "judge transport failed"
    }


def test_compare_cli_reads_authoritative_ledger_and_scope_manifest(tmp_path):
    task_ids, baseline, treatment, maxima, grades = _fixture()
    ledger, baseline_scopes, treatment_scopes = _ledger_inputs(tmp_path, task_ids)
    dataset_revision = "a" * 40
    rubric_commit = "b" * 40
    baseline_revision = "c" * 40
    treatment_revision = "d" * 40
    grader_source_hash = "e" * 64

    def inference(experiment_id, condition, mode, results):
        return {
            "experiment_id": experiment_id,
            "condition_identity": condition,
            "execution_mode": mode,
            "run_id": "paired-run",
            "ordered_task_ids": task_ids,
            "results": results,
        }

    def grade(experiment_id, revision):
        return {
            **json.loads(json.dumps(grades)),
            "experiment_id": experiment_id,
            "source_inference_experiment_id": experiment_id,
            "source_inference_revision": revision,
            "grader_source_hash": grader_source_hash,
            "rubric": {"commit_sha": rubric_commit},
            "judge": {"config_hash": "track2-config"},
            "prompt": {"version": "track2-prompt-v1"},
        }

    inputs = {
        "task-manifest": {
            "diagnostic_task_ids": task_ids,
            "dataset": {"revision": dataset_revision},
            "rubric": {"revision": rubric_commit},
        },
        "baseline-results": inference(
            "exp029", "baseline", "sandbox", baseline
        ),
        "treatment-results": inference(
            "exp030", "treatment", "agentic_sandbox",
            treatment,
        ),
        "rubric-maxima": {
            "schema_version": "agentic-rubric-maxima-v1",
            "rubric_commit": rubric_commit,
            "tasks": maxima,
        },
        "baseline-grades": grade("exp029", baseline_revision),
        "treatment-grades": grade("exp030", treatment_revision),
    }
    arguments = []
    artifact_hashes = {}
    for name, value in inputs.items():
        path = tmp_path / f"{name}.json"
        content = json.dumps(value)
        path.write_text(content, encoding="utf-8")
        artifact_hashes[name.replace("-", "_")] = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()
        arguments.extend([f"--{name}", str(path)])
    scope = {
        "schema_version": "agentic-budget-scope-manifest-v2",
        "paired_run_id": "paired-run",
        "ordered_task_ids": task_ids,
        "dataset_revision": dataset_revision,
        "rubric_commit": rubric_commit,
        "baseline_inference_revision": baseline_revision,
        "treatment_inference_revision": treatment_revision,
        "judge_config_hash": "track2-config",
        "prompt_version": "track2-prompt-v1",
        "grader_source_hash": grader_source_hash,
        "baseline_task_scopes": baseline_scopes,
        "treatment_task_scopes": treatment_scopes,
        "artifact_sha256": artifact_hashes,
    }
    scope["sha256"] = hashlib.sha256(json.dumps(
        scope, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    scope_path = tmp_path / "scope-manifest.json"
    scope_path.write_text(json.dumps(scope), encoding="utf-8")
    arguments.extend(["--scope-manifest", str(scope_path)])
    output = tmp_path / "endpoints.json"
    script = Path(__file__).resolve().parents[1] / "scripts" / (
        "compare_agentic_conditions.py"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            *arguments,
            "--budget-ledger",
            ledger.path,
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    endpoints = json.loads(output.read_text(encoding="utf-8"))
    assert endpoints["cost"]["baseline_mean_usd"] == 0.1
    assert endpoints["cost"]["treatment_mean_usd"] == 0.2
    assert endpoints["provenance"]["artifact_sha256"] == artifact_hashes
    assert endpoints["provenance"]["rubric_commit"] == rubric_commit

    swapped = json.loads(
        (tmp_path / "baseline-grades.json").read_text(encoding="utf-8")
    )
    swapped["experiment_id"] = "exp030"
    (tmp_path / "baseline-grades.json").write_text(
        json.dumps(swapped), encoding="utf-8"
    )
    rejected = subprocess.run(
        [
            sys.executable,
            str(script),
            *arguments,
            "--budget-ledger",
            ledger.path,
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert rejected.returncode != 0
    assert "artifact byte identity mismatch" in rejected.stderr