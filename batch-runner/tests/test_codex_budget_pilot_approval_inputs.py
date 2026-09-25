"""Captured dispatch representation, actual approval script, real CLI authority.

Only the JSON shape comes from the reported run; all execution below is offline.
The existing synthetic retained/source fixtures forbid external boundaries.
"""

import json
import re
import sys

import pytest

import codex_budget_pilot_grading as connector
from . import test_codex_budget_pilot_grading as base
from .test_codex_budget_pilot_grading_oidc import (
    CONTROLLER, PRODUCER, RUN, SELECTOR, TERMINAL,
    boundaries, case, compilations, compiled_cells, workflow,  # noqa: F401
)


@pytest.mark.parametrize("change,value,outcome", [
    pytest.param("captured", None, "match", id="captured-live-shape"),
    pytest.param("canonical", None, "match", id="canonical-integers"),
    pytest.param("mixed", None, "match", id="mixed-supported-numbers"),
    pytest.param("tasks", "", "match", id="explicit-empty-tasks"),
    pytest.param("branch", None, "match", id="absent-optional-branch-strings"),
    pytest.param("tasks_limit", False, "input_refused", id="numeric-bool"),
    pytest.param("shard_count", 1.0, "input_refused", id="numeric-float"),
    *[pytest.param("tasks_limit", value, "input_refused", id="numeric-" + label)
      for label, value in (("whitespace", " 0"), ("sign", "+0"), ("leading-zero", "00"),
                           ("fraction", "0.0"), ("exponent", "0e0"), ("negative", -1))],
    pytest.param("integer_limit", None, "input_refused", id="integer-conversion-limit"),
    pytest.param("force", "false", "input_refused", id="boolean-string"),
    pytest.param("tasks", None, "input_refused", id="explicit-null-tasks"),
    pytest.param("inference_revision", None, "input_refused", id="explicit-null-terminal"),
    pytest.param("producer_source_sha", "PRIVATE-unknown-input", "input_refused", id="unknown-field"),
    pytest.param("omit", "experiment_yaml", "input_refused", id="missing-required-selector"),
    pytest.param("omit", "tasks_limit", "input_refused", id="missing-required-control"),
    *[pytest.param("document", value, "input_refused", id="document-" + label)
      for label, value in (("empty-object", {}), ("empty-list", []), ("false", False),
                           ("zero", 0), ("null", None))],
    *[pytest.param(key, value, "binding_refused", id="changed-" + key)
      for key, value in (("tasks_limit", "1"), ("resume_chunk", "1"), ("shard_count", "2"),
                         ("shard_index", "1"), ("run_ordinal", "2"), ("force", True),
                         ("tasks", "PRIVATE-changed-task"), ("inference_revision", "e" * 40))],
    pytest.param("omit", "inference_revision", "binding_refused", id="missing-bound-cell-terminal"),
    pytest.param("controller", "e" * 40, "binding_refused", id="different-controller"),
    pytest.param("run", "12346", "binding_refused", id="different-run"),
    pytest.param("skipped", None, "approval_refused", id="skipped-approval"),
])
def test_dispatch_inputs_bind_actual_approval_to_connector(
    case, workflow, tmp_path, monkeypatch, capsys, change, value, outcome,
):
    # This is the captured LIVE-shaped JSON, not _inputs()'s integer fixture:
    # tasks is absent, numeric controls are strings, booleans remain booleans.
    inputs = {"experiment_yaml": SELECTOR, "inference_revision": TERMINAL,
        "grading_config": "default_v2_sol_max.yaml", "force": False, "tasks_limit": "0",
        "dry_run": False, "paid_approval": True, "resume": False, "resume_chunk": "0",
        "shard_count": "1", "shard_index": "0", "run_ordinal": "1"}
    selection = {}
    approval_env = {}
    if change == "canonical":
        inputs.update(tasks="", tasks_limit=0, resume_chunk=0, shard_count=1, shard_index=0, run_ordinal=1)
    elif change == "mixed":
        inputs.update(resume_chunk=0, shard_count=1)
    elif change == "branch":
        inputs["experiment_yaml"] = "pilot/branch-setup"
        inputs.pop("inference_revision")
        selection = {"selector": "pilot/branch-setup", "terminal": "", "producer": ""}
    elif change == "integer_limit":
        # Exercise a real conversion refusal without changing the host's limit.
        limit = sys.get_int_max_str_digits()
        assert limit > 0
        inputs["tasks_limit"] = "9" * (limit + 1)
    elif change == "omit":
        inputs.pop(value)
    elif change == "document":
        inputs = value
    elif change == "controller":
        approval_env = {"GITHUB_SHA": value, "PILOT_WORKFLOW_SHA": value}
    elif change == "run":
        approval_env = {"GITHUB_RUN_ID": value}
    elif change not in {"captured", "skipped"}:
        inputs[change] = value

    approval = workflow["jobs"]["pilot-approve-paid"]
    live = workflow["jobs"]["pilot-live"]
    assert approval["environment"] == {"name": "grading"} and approval["permissions"] == {}
    assert len(approval["steps"]) == 1 and "uses" not in approval["steps"][0]
    assert live["needs"] == ["pilot-approve-paid"] and "environment" not in live
    assert "needs.pilot-approve-paid.result == 'success'" in live["if"]
    script = approval["steps"][0]["run"].removeprefix("python3 - <<'PY'\n").removesuffix("PY\n")
    destination = tmp_path / "captured-approval-output"
    with monkeypatch.context() as approved:
        approved.setenv("PILOT_GRADE_INPUTS_JSON", json.dumps(inputs))
        approved.setenv("GITHUB_OUTPUT", str(destination))
        approved.setenv("GITHUB_JOB", "pilot-approve-paid")
        for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
                    "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN"):
            approved.delenv(key, raising=False)
        for key, item in approval_env.items():
            approved.setenv(key, item)
        if outcome == "input_refused":
            with pytest.raises(SystemExit) as refusal:
                exec(compile(script, "<actual-protected-approval>", "exec"), {})
            assert refusal.value.code == "pilot_grade_approval_inputs_refused"
            assert not destination.exists()
        else:
            exec(compile(script, "<actual-protected-approval>", "exec"), {})

    if outcome == "input_refused":
        # A failed normalization cannot authorize execution with a stale digest.
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "failure")
    else:
        text = destination.read_text()
        assert re.fullmatch(r"request_sha256=[0-9a-f]{64}\n", text)
        digest = text.strip().split("=", 1)[1]
        expected = connector._approval_request_sha256(CONTROLLER,
            selection.get("selector", SELECTOR), selection.get("terminal", TERMINAL), RUN,
            producer_source_sha=selection.get("producer", PRODUCER))
        assert (digest == expected) is (outcome != "binding_refused")
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", digest)
        if change == "skipped":
            monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped")
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    code, observed = base.invoke(case, capsys, **selection)
    if outcome == "match":
        assert code == 0 and observed["outcome"] == "plan_only"
        assert observed["controller_source_sha"] == CONTROLLER
        assert observed["source_sha"] == (CONTROLLER if selection else PRODUCER)
        assert not observed["judge_entry_requested"] and not observed["inference_requested"]
    else:
        assert code == 2 and observed["outcome"] == "refused"
        assert observed["reason"] == ("pilot_grading_approval_request_mismatch"
            if outcome == "binding_refused" else "same_run_pilot_grading_approval_required")
    assert "PRIVATE" not in json.dumps(observed)
    assert case.api.calls == [] and case.transport.calls == 0 and not case.root.exists()
