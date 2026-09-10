"""A run that reached a model must be recordable in the mode that ran.

Run `34485072751` was the first `codex_foundry` dispatch to get past the
config check, the isolation probe, the pinned-runtime check, OIDC, and the
route validation. Step 2a succeeded: five tasks were attempted, one was
solved end to end, and its deliverable was collected into
`workspace/upload/deliverable_files/`. Then Step 3 died:

    File ".../batch-runner/step3_format_results.py", line 337
        provenance = build_inference_provenance(final_json)
    File ".../batch-runner/core/inference_manifest.py", line 285
        raise ValueError("inference execution mode is invalid")
    ValueError: inference execution mode is invalid

The mode was `codex_foundry`, which is a mode an experiment file may name and
which `ExperimentConfig.validate` had already accepted four steps earlier.
`INFERENCE_EXECUTION_MODES` had simply never heard of it -- it was typed out
by hand in #140 and two modes were added to the platform afterwards without
it. Nothing caught the drift because that list is not read until Step 3, which
runs after the inference it describes has already been paid for.

So these tests hold two things:

* the mode that ran can be recorded -- for every mode, not just this one; and
* the list cannot drift away from `ExecutionConfig.mode` again, because it is
  no longer a second list.
"""

from __future__ import annotations

import json
from typing import get_args, get_type_hints

import pytest

from core.experiment_config import ExecutionConfig
from core.inference_manifest import (
    INFERENCE_EXECUTION_MODES,
    LEGACY_INFERENCE_EXECUTION_MODE,
    build_inference_provenance,
    canonical_execution_mode,
    validate_execution_route_binding,
)


EVERY_MODE_AN_EXPERIMENT_CAN_ASK_FOR = get_args(
    get_type_hints(ExecutionConfig)["mode"]
)

#: What Codex recorded on run `34485072751`: one direct-v1 route, serving
#: inference. Codex signs in for itself, so there is no separate client route
#: and no Code Interpreter route. The fingerprint is stand-in; its real value
#: is a hash of resolved route settings and nothing here depends on which.
THE_ROUTE_CODEX_RECORDED = {
    "endpoint_kind": "direct-v1",
    "profile": "direct-v1",
    "runtime_fingerprint": "f" * 64,
    "workload": "inference",
}

#: The five tasks of `exp033_codex_foundry_fixed5`, in the order the run put
#: them in. `0112fc9b...` is the one that was solved.
THE_FIVE_TASKS = [
    "02aa1805-c658-4069-8a6a-02dec146063a",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",
]


def a_results_file(mode, *, routes=None, results=None):
    """The shape Step 3 hands `build_inference_provenance`."""
    return {
        "experiment_id": "exp033_codex_foundry_fixed5",
        "source_repo_id": "owner/exp033_codex_foundry_fixed5",
        "prepared_fingerprint": "e" * 64,
        "execution_mode": mode,
        "azure_ai_routes": (
            [THE_ROUTE_CODEX_RECORDED] if routes is None else routes
        ),
        "results": (
            [{"task_id": task_id, "deliverable_files": []}
             for task_id in THE_FIVE_TASKS]
            if results is None else results
        ),
    }


def the_run_that_died_at_step_three():
    """Run `34485072751`'s own result file, down to what Step 3 reads.

    One task solved with one deliverable, four errored, and the single
    direct-v1 inference route the run recorded.
    """
    solved = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1"
    return a_results_file(
        "codex_foundry",
        results=[
            {
                "task_id": task_id,
                "deliverable_files": (
                    [f"deliverable_files/{task_id}/soap_note_2024-03-01_CS.md"]
                    if task_id == solved else []
                ),
            }
            for task_id in THE_FIVE_TASKS
        ],
    )


def test_the_run_that_solved_a_task_can_now_be_recorded():
    provenance = build_inference_provenance(the_run_that_died_at_step_three())

    assert provenance["execution_mode"] == "codex_foundry"
    assert provenance["task_count"] == 5
    assert provenance["azure_ai_routes"] == [THE_ROUTE_CODEX_RECORDED]


def test_the_record_is_still_a_json_document():
    """Nothing in the new constant leaks a frozenset into the sidecar."""
    provenance = build_inference_provenance(the_run_that_died_at_step_three())

    assert json.loads(json.dumps(provenance)) == provenance


@pytest.mark.parametrize("mode", EVERY_MODE_AN_EXPERIMENT_CAN_ASK_FOR)
def test_every_mode_an_experiment_can_ask_for_can_be_recorded(mode):
    """The general form of the defect, not just the mode that hit it.

    `agentic_sandbox_v2` was missing from the old list too, and would have
    died at the same line on the first V2 run to reach Step 3.
    """
    routes = (
        [{
            "endpoint_kind": "project",
            "profile": "project-ci",
            "runtime_fingerprint": "a" * 64,
            "workload": "code-interpreter",
        }]
        if mode == "code_interpreter" else None
    )

    provenance = build_inference_provenance(a_results_file(mode, routes=routes))

    assert provenance["execution_mode"] == mode


def test_the_two_lists_cannot_drift_again():
    """Not "these seven names", which is what drifted. One list, plus legacy."""
    assert INFERENCE_EXECUTION_MODES == (
        frozenset(EVERY_MODE_AN_EXPERIMENT_CAN_ASK_FOR)
        | {LEGACY_INFERENCE_EXECUTION_MODE}
    )


def test_the_modes_that_were_missing_are_the_ones_added_after_the_list():
    """Names the drift, so a future reader sees what was lost and when."""
    assert {"agentic_sandbox_v2", "codex_foundry"} <= INFERENCE_EXECUTION_MODES


def test_the_legacy_path_is_still_recordable():
    provenance = build_inference_provenance(
        a_results_file(LEGACY_INFERENCE_EXECUTION_MODE)
    )

    assert provenance["execution_mode"] == "legacy"


def test_legacy_is_not_something_an_experiment_can_ask_for():
    """Why it has to be added by hand rather than read off the annotation.

    `step2_run_inference.py` still has a `legacy` branch, so records naming it
    must stay readable -- but no experiment YAML can select it.
    """
    assert LEGACY_INFERENCE_EXECUTION_MODE not in EVERY_MODE_AN_EXPERIMENT_CAN_ASK_FOR


@pytest.mark.parametrize(
    "mode",
    ["", None, "Codex_Foundry", "codex", "codex_foundry ", 7, ["codex_foundry"]],
)
def test_a_mode_no_experiment_can_name_is_still_refused(mode):
    """Including the unhashable one: a record is arbitrary JSON.

    `["codex_foundry"]` used to reach the membership test and raise
    `TypeError: unhashable type: 'list'`, which is not what any caller here
    catches -- `step3_format_results.py` and `core/hf_publication.py` both
    handle `ValueError` and would have crashed instead of reporting.
    """
    with pytest.raises(ValueError, match="inference execution mode is invalid"):
        canonical_execution_mode(mode)


def test_a_codex_run_carrying_a_code_interpreter_route_is_still_refused():
    """Admitting the mode did not loosen what the record may claim.

    Codex reaches the direct v1 endpoint and signs in for itself; a
    `codex_foundry` record naming a Code Interpreter route describes a run
    that cannot have happened.
    """
    with pytest.raises(
        ValueError,
        match="non-Code-Interpreter provenance contains a Code Interpreter route",
    ):
        validate_execution_route_binding("codex_foundry", [{
            "endpoint_kind": "project",
            "profile": "project-ci",
            "runtime_fingerprint": "a" * 64,
            "workload": "code-interpreter",
        }])


def test_code_interpreter_still_needs_its_project_route():
    with pytest.raises(
        ValueError,
        match="Code Interpreter provenance requires one project-ci route",
    ):
        validate_execution_route_binding(
            "code_interpreter", [THE_ROUTE_CODEX_RECORDED]
        )


def test_the_publication_path_asks_the_same_question():
    """`hf_publication` calls the same function, so Step 7 was blocked too.

    Step 3 is only where it was first reached; `build_publication_identity`
    would have refused the same run at upload.
    """
    from core import hf_publication

    assert hf_publication.canonical_execution_mode is canonical_execution_mode
