"""Keep #810's placement transport out of the exact comparison request.

Only the shipped, isolated JSON adapter and the model-free request validator
run here. The subsequent checkout preparation command is never executed.
"""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

import gpt54_workflow_gate as gate
from . import test_workflow_ubuntu_runner_pins as seals


ROOT = Path(__file__).resolve().parents[2]
ROLE = ".github/workflows/batch-run.yml"
BASE = "bdb6e00b48f2a0733629437b0d555a7c73f2c4e8"
REVIEWED = "a" * 40
CONSUMER = "env -u PYTHONPATH python3 -I batch-runner/gpt54_workflow_gate.py"


def base_bytes():
    return subprocess.run(
        ["git", "show", f"{BASE}:{ROLE}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        env={"PATH": os.defpath, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
             "GIT_NO_LAZY_FETCH": "1"},
    ).stdout


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load((ROOT / ROLE).read_bytes())


@pytest.fixture
def dispatched(workflow):
    values = {key: declaration.get("default", "")
              for key, declaration in workflow[True]["workflow_dispatch"]["inputs"].items()}
    values.update(experiment_yaml="execution_envelope/gpt54_v2_codex_v1_codex_r1",
                  codex_foundry_confirmed=True, comparison_reviewed_source_sha=REVIEWED)
    return values


def request(values):
    return gate.request_from_inputs(
        "batch-run", values, event_name="workflow_dispatch", event_ref="refs/heads/main",
        event_sha=REVIEWED, workflow_sha=REVIEWED,
    )


def project(workflow, raw):
    step = workflow["jobs"]["comparison-admission"]["steps"][-1]
    assert step["env"]["COMPARISON_INPUTS"] == "${{ toJSON(inputs) }}"
    assert step["run"].count(CONSUMER) == 1
    prefix, consumer_arguments = step["run"].split(CONSUMER)
    assert '--workflow batch-run --inputs-json "$COMPARISON_INPUTS"' in consumer_arguments
    assert "python3 -I - <<'PY'" in prefix
    return subprocess.run(
        ["bash", "-c", prefix + 'printf "%s\\n" "$COMPARISON_INPUTS"\n'],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
        env={"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "COMPARISON_INPUTS": raw,
             "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_the_main_810_regression_is_an_extra_input_not_a_new_permission(dispatched):
    declared = yaml.safe_load(base_bytes())[True]["workflow_dispatch"]["inputs"]
    assert set(declared) == set(dispatched) and len(dispatched) == 11
    with pytest.raises(gate.WorkflowExecutionRefused):
        request(dispatched)
    previous = {key: value for key, value in dispatched.items() if key != "placement_attempt"}
    assert len(previous) == 10 and request(previous).condition == "codex"


@pytest.mark.parametrize("placement", [1, "1"])
def test_only_the_default_transport_counter_is_removed(workflow, dispatched, placement):
    dispatched["placement_attempt"] = placement
    result = project(workflow, json.dumps(dispatched))
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    expected = {key: value for key, value in dispatched.items() if key != "placement_attempt"}
    assert len(actual) == 10 and actual == expected
    assert {key: type(value) for key, value in actual.items()} == {
        key: type(value) for key, value in expected.items()}
    assert request(actual).condition == "codex"


@pytest.mark.parametrize("placement", [None, True, False, 0, 2, 20, 1.0, "01", "1.0", "", [], {}])
def test_a_nondefault_or_invalid_counter_cannot_reach_the_consumer(workflow, dispatched, placement):
    dispatched["placement_attempt"] = placement
    result = project(workflow, json.dumps(dispatched))
    assert result.returncode != 0 and result.stdout == ""
    assert "comparison_placement_attempt_refused" in result.stderr


def test_a_missing_counter_is_not_inferred(workflow, dispatched):
    del dispatched["placement_attempt"]
    result = project(workflow, json.dumps(dispatched))
    assert result.returncode != 0 and result.stdout == ""


@pytest.mark.parametrize("raw", ["[]", "null", '"text"', "true", "{", '{"placement_attempt":1,"placement_attempt":1}',
                                  '{"placement_attempt":1,"wall_timeout":NaN}'])
def test_malformed_or_duplicate_json_is_not_repaired(workflow, raw):
    result = project(workflow, raw)
    assert result.returncode != 0 and result.stdout == ""


@pytest.mark.parametrize("field,value", [
    ("unexpected_input", True), ("wall_timeout", "290"), ("relay_run", 0.0),
    ("dry_run", 0), ("codex_foundry_confirmed", False),
])
def test_old_types_values_and_unknown_fields_still_reach_the_strict_validator(workflow, dispatched, field, value):
    dispatched[field] = value
    result = project(workflow, json.dumps(dispatched))
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    assert actual[field] == value and type(actual[field]) is type(value)
    with pytest.raises(gate.WorkflowExecutionRefused):
        request(actual)


def test_an_old_required_field_is_not_defaulted(workflow, dispatched):
    del dispatched["wall_timeout"]
    result = project(workflow, json.dumps(dispatched))
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    assert "wall_timeout" not in actual
    with pytest.raises(gate.WorkflowExecutionRefused):
        request(actual)


def test_the_successor_restores_exact_main_and_leaves_exp039_jobs_unchanged(workflow):
    previous = base_bytes()
    assert seals.restore_pre_comparison_input_projection_bytes((ROOT / ROLE).read_bytes()) == previous
    before = yaml.safe_load(previous)
    assert workflow[True] == before[True] and workflow["permissions"] == before["permissions"]
    assert set(workflow["jobs"]) == set(before["jobs"])
    for name, job in before["jobs"].items():
        if name != "comparison-admission":
            assert workflow["jobs"][name] == job, name
    old_steps, new_steps = before["jobs"]["comparison-admission"]["steps"], workflow["jobs"]["comparison-admission"]["steps"]
    assert new_steps[:-1] == old_steps[:-1]
    assert {k: v for k, v in new_steps[-1].items() if k != "run"} == {
        k: v for k, v in old_steps[-1].items() if k != "run"}
    assert new_steps[-1]["run"].split(CONSUMER)[1] == old_steps[-1]["run"].split(CONSUMER)[1]
