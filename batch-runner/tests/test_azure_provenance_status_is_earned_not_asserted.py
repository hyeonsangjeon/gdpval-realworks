"""``runtime-verified`` must be earned by a served response, not asserted.

Why this exists
---------------
Step 3 wrote the provenance status as a literal::

    "azure_ai_provenance_status": "runtime-verified",

so it was true of every run it was ever written about, including the runs where
no Azure route answered at all.

exp032 is the run that proves it. All five of its tasks came back
``PermissionDeniedError (http 403)`` from the project-scoped Code Interpreter
route -- GitHub runs 33464316741 and 33468138329, both `failure`, five
``task_execution_error:PermissionDeniedError`` records apiece -- and the
``result.json`` Step 3 wrote still said the Azure route had been verified at
runtime. Zero calls served, and the provenance record said the opposite.

``azure_ai_routes`` cannot catch this, which is the part worth spelling out.
Those records are assembled from resolved settings in
``core/azure_ai_clients.py`` (``"Validate routes and return endpoint-free,
redacted provenance records"``), so they describe the route that was
*selected*. A run with five refusals emits exactly the same array as a run with
five successes. Only the outcome tells them apart.

The literal was also wrong in the other direction. ``step2_run_inference.py``
requires a legacy run to carry *no* Azure routes -- ``"legacy Step 2 must not
contain Azure AI routes"`` -- so Step 3 was certifying Azure route verification
for runs that made no Azure claim whatsoever.

What this file pins is the direction of the inference: a completed task implies
a served response, so success count is evidence and route configuration is not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import step3_format_results as step3
from core.inference_manifest import (
    GOLD_PROVENANCE_STATUS,
    LOCAL_RUNTIME_PROVENANCE_STATUS,
    RUNTIME_UNVERIFIED_PROVENANCE_STATUS,
    RUNTIME_VERIFIED_PROVENANCE_STATUS,
    azure_ai_provenance_status,
)
from core.prepared_fingerprint import prepared_fingerprint
from core.result_fingerprint import inference_result_fingerprint

BATCH_ROOT = Path(__file__).resolve().parents[1]

# Synthetic, like the price-table digest in
# test_step3_cost_summary_does_not_shadow_task_counts.py. The real exp032
# fingerprints are stable identifiers of two specific routes on the owner's
# account, and no assertion here needs their actual bytes -- only that routes
# of this *shape* are present.
_FINGERPRINTS = ("4b" * 32, "7c" * 32)

# The exp032 route pair, field for field from the ``azure_ai_routes`` its
# result.json carries (fingerprints substituted as above). Both routes are
# ``project-ci``; only Code Interpreter goes through the project-scoped
# endpoint, and that is the endpoint that answered 403.
CODE_INTERPRETER_ROUTES = [
    {
        "endpoint_kind": "direct-v1",
        "profile": "project-ci",
        "runtime_fingerprint": _FINGERPRINTS[0],
        "workload": "inference",
    },
    {
        "endpoint_kind": "project",
        "profile": "project-ci",
        "runtime_fingerprint": _FINGERPRINTS[1],
        "workload": "code-interpreter",
    },
]


# ── The decision itself ────────────────────────────────────────────────────


def test_routes_plus_a_completed_task_is_runtime_verified():
    """The one case that earns the claim: a task finished, so a call was served."""
    status = azure_ai_provenance_status(
        CODE_INTERPRETER_ROUTES, {"total": 5, "success": 5, "error": 0}
    )
    assert status == RUNTIME_VERIFIED_PROVENANCE_STATUS


def test_the_exp032_shape_is_not_runtime_verified():
    """Five tasks, five 403s, zero served responses -- the case that was wrong.

    This is the whole point of the change, written in the numbers run
    33468138329 actually produced.
    """
    status = azure_ai_provenance_status(
        CODE_INTERPRETER_ROUTES, {"total": 5, "success": 0, "error": 5}
    )
    assert status == RUNTIME_UNVERIFIED_PROVENANCE_STATUS


def test_a_partial_run_is_verified_because_something_was_served():
    """One success is enough. This is a provenance record, not a quality score.

    Deliberate: a run that served four responses and failed one has a route
    that demonstrably answers, and saying otherwise would make the field mean
    "did every task pass", which is what ``summary`` is already for.
    """
    status = azure_ai_provenance_status(
        CODE_INTERPRETER_ROUTES, {"total": 5, "success": 1, "error": 4}
    )
    assert status == RUNTIME_VERIFIED_PROVENANCE_STATUS


@pytest.mark.parametrize("routes", [None, []], ids=["absent", "empty"])
def test_no_routes_is_local_runtime_not_a_failed_azure_run(routes):
    """A run with no typed routes made no Azure claim to verify or refute.

    ``local-runtime`` is already what ``step8_grade.py`` assumes when the key is
    missing, so this keeps one meaning for one situation instead of two.
    """
    status = azure_ai_provenance_status(routes, {"total": 5, "success": 5, "error": 0})
    assert status == LOCAL_RUNTIME_PROVENANCE_STATUS


@pytest.mark.parametrize(
    "summary",
    [
        {"total": 5, "error": 5},
        {"total": 5, "success": None, "error": 5},
        {"total": 5, "success": True, "error": 0},
        {"total": 5, "success": "5", "error": 0},
        {"total": 5, "success": 5.0, "error": 0},
        {"total": 5, "success": -1, "error": 0},
        None,
        [],
        "5 succeeded",
    ],
    ids=[
        "missing",
        "null",
        "bool_true",
        "string",
        "float",
        "negative",
        "none",
        "list",
        "string_summary",
    ],
)
def test_an_unreadable_success_count_fails_closed(summary):
    """Anything that is not a positive integer count is not evidence.

    ``bool_true`` is the trap worth naming: ``isinstance(True, int)`` is True in
    Python and ``True > 0``, so a summary carrying ``success: true`` would sail
    through a naive check as though one task had completed.
    """
    status = azure_ai_provenance_status(CODE_INTERPRETER_ROUTES, summary)
    assert status == RUNTIME_UNVERIFIED_PROVENANCE_STATUS


@pytest.mark.parametrize(
    "routes",
    [{"workload": "code-interpreter"}, "code-interpreter", 1],
    ids=["dict", "string", "int"],
)
def test_a_malformed_route_record_fails_closed(routes):
    """A route field of the wrong type is not an empty route list."""
    status = azure_ai_provenance_status(routes, {"total": 1, "success": 1, "error": 0})
    assert status == RUNTIME_UNVERIFIED_PROVENANCE_STATUS


# ── The same decision, through the real Step 3 ─────────────────────────────


def _write_workspace(workspace, *, routes, execution_mode, success_tasks):
    task_ids = [f"task-{index}" for index in range(5)]
    prepared = {
        "experiment_id": "exp998",
        "experiment_name": "provenance regression",
        "publication_generation": "exp998:100:1",
        "source": "student/exp998",
        "task_scope": {"task_ids": task_ids},
        "tasks": [
            {"task_id": tid, "sector": "Finance", "occupation": "Accountants"}
            for tid in task_ids
        ],
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)

    results = []
    for index, tid in enumerate(task_ids):
        succeeded = index < success_tasks
        results.append(
            {
                "task_id": tid,
                "status": "success" if succeeded else "error",
                "deliverable_text": "a deliverable" if succeeded else "",
                "deliverable_files": [],
                "latency_ms": 1000,
                # Verbatim from the exp032 per-task records.
                "error": None if succeeded else "task_execution_error:PermissionDeniedError",
            }
        )

    inference = {
        "experiment_id": "exp998",
        "experiment_name": "provenance regression",
        "publication_generation": "exp998:100:1",
        "source": "student/exp998",
        "prepared_fingerprint": prepared["prepared_fingerprint"],
        "ordered_task_ids": task_ids,
        "condition": "condition_a",
        "execution_mode": execution_mode,
        "model": "gpt-5.4",
        "started_at": "2026-08-30T08:00:00Z",
        "completed_at": "2026-08-30T08:10:00Z",
        "resume_rounds_used": 0,
        "results": results,
        "summary": {
            "total": len(task_ids),
            "success": success_tasks,
            "error": len(task_ids) - success_tasks,
            "qa_failed": 0,
        },
    }
    if routes is not None:
        inference["azure_ai_routes"] = routes
    inference["result_fingerprint"] = inference_result_fingerprint(inference)

    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    (workspace / "step2_inference_results.json").write_text(
        json.dumps(inference), encoding="utf-8"
    )


def _run(tmp_path, monkeypatch, *, routes, execution_mode, success_tasks) -> dict:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    root = tmp_path / "batch-runner"
    root.mkdir()
    _write_workspace(
        workspace,
        routes=routes,
        execution_mode=execution_mode,
        success_tasks=success_tasks,
    )
    monkeypatch.setattr(step3, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step3, "BATCH_RUNNER_ROOT", root)
    step3.format_results()
    return json.loads(
        (root / "results" / "exp998" / "exp998.json").read_text(encoding="utf-8")
    )


def test_step3_records_a_wholly_refused_run_as_unverified(tmp_path, monkeypatch):
    """End to end on the exp032 shape, since the literal lived in Step 3.

    The route list is asserted alongside the status: the fix must keep
    publishing which route was selected while stopping the claim that it
    replied. Dropping the routes would also make this pass, and would be wrong.
    """
    payload = _run(
        tmp_path,
        monkeypatch,
        routes=CODE_INTERPRETER_ROUTES,
        execution_mode="code_interpreter",
        success_tasks=0,
    )

    assert payload["azure_ai_provenance_status"] == RUNTIME_UNVERIFIED_PROVENANCE_STATUS
    assert payload["azure_ai_routes"] == CODE_INTERPRETER_ROUTES
    assert payload["summary"]["success_count"] == 0


def test_step3_still_records_a_working_run_as_verified(tmp_path, monkeypatch):
    """The healthy path must not regress: same routes, tasks completed."""
    payload = _run(
        tmp_path,
        monkeypatch,
        routes=CODE_INTERPRETER_ROUTES,
        execution_mode="code_interpreter",
        success_tasks=5,
    )

    assert payload["azure_ai_provenance_status"] == RUNTIME_VERIFIED_PROVENANCE_STATUS


def test_step3_stops_claiming_azure_verification_for_a_routeless_run(
    tmp_path, monkeypatch
):
    """A legacy run carries no routes by construction, so it certified nothing."""
    payload = _run(
        tmp_path,
        monkeypatch,
        routes=None,
        execution_mode="sandbox",
        success_tasks=5,
    )

    assert payload["azure_ai_provenance_status"] == LOCAL_RUNTIME_PROVENANCE_STATUS
    assert payload["azure_ai_routes"] == []


def test_the_literal_is_gone_from_step3():
    """A regression lock on the shape of the defect, not just its effect.

    The status is one line in a dict literal, and re-hardcoding it would be a
    one-word edit that every behavioural test above would still pass on the
    happy path.
    """
    source = (BATCH_ROOT / "step3_format_results.py").read_text(encoding="utf-8")
    assert '"runtime-verified"' not in source
    assert "azure_ai_provenance_status(" in source


# ── The schema has to accept what the producer can emit ────────────────────


def test_every_status_step3_can_emit_is_a_legal_schema_value():
    schema = json.loads(
        (BATCH_ROOT / "schemas" / "grade.schema.json").read_text(encoding="utf-8")
    )
    enum = set(schema["properties"]["source_azure_ai_provenance_status"]["enum"])

    assert {
        RUNTIME_VERIFIED_PROVENANCE_STATUS,
        RUNTIME_UNVERIFIED_PROVENANCE_STATUS,
        LOCAL_RUNTIME_PROVENANCE_STATUS,
    } <= enum


def test_the_new_value_is_additive_only():
    """Nothing already published may stop validating because of this change.

    Grades written before today carry one of these five, and the enum is the
    gate they are checked against on re-validation.
    """
    schema = json.loads(
        (BATCH_ROOT / "schemas" / "grade.schema.json").read_text(encoding="utf-8")
    )
    enum = set(schema["properties"]["source_azure_ai_provenance_status"]["enum"])

    assert {
        "runtime-verified",
        "verified-sidecar",
        "legacy-missing",
        "local-runtime",
        GOLD_PROVENANCE_STATUS,
    } <= enum
