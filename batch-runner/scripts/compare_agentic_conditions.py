#!/usr/bin/env python3
"""Compute preregistered paired Agentic Sandbox endpoints from frozen JSON."""

import argparse
import json
from pathlib import Path

from core.agentic_budget import AgenticBudgetLedger
from core.agentic_endpoints import compute_paired_endpoints


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-manifest", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--treatment-results", required=True)
    parser.add_argument("--rubric-maxima", required=True)
    parser.add_argument("--baseline-grades", required=True)
    parser.add_argument("--treatment-grades", required=True)
    parser.add_argument("--budget-ledger", required=True)
    parser.add_argument("--scope-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = _load(args.task_manifest)
    baseline = _load(args.baseline_results)
    treatment = _load(args.treatment_results)
    scopes = _load(args.scope_manifest)
    if not isinstance(scopes, dict) or set(scopes) != {
        "schema_version", "paired_run_id", "baseline_task_scopes",
        "treatment_task_scopes",
    }:
        raise ValueError("budget scope manifest fields are invalid")
    if scopes["schema_version"] != "agentic-budget-scope-manifest-v1":
        raise ValueError("budget scope manifest version is invalid")
    endpoints = compute_paired_endpoints(
        expected_task_ids=manifest["diagnostic_task_ids"],
        baseline_results=baseline["results"],
        treatment_results=treatment["results"],
        rubric_maxima=_load(args.rubric_maxima),
        baseline_grades=_load(args.baseline_grades),
        treatment_grades=_load(args.treatment_grades),
        budget_ledger=AgenticBudgetLedger(args.budget_ledger),
        paired_run_id=scopes["paired_run_id"],
        baseline_task_scopes=scopes["baseline_task_scopes"],
        treatment_task_scopes=scopes["treatment_task_scopes"],
    )
    Path(args.output).write_text(
        json.dumps(endpoints, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()