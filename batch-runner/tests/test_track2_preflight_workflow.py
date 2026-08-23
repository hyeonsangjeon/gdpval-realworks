import json
import os
from pathlib import Path
import re
import subprocess

import yaml


WORKFLOW_PATH = Path("../.github/workflows/preflight-track2-cohort.yml")


def _workflow() -> tuple[str, dict]:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def _valid_plan() -> dict:
    return {
        "source_repo": "owner/repo",
        "source_revision": "a" * 40,
        "tasks_limit": 2,
        "planner_source_hash": "b" * 64,
        "config_hash": "c" * 16,
        "grader_source_hash": "d" * 64,
        "rubric_sha": "e" * 40,
        "task_ids": ["task-1", "task-2"],
    }


def _validation_script(parsed: dict) -> str:
    job = parsed["jobs"]["preflight"]
    steps = {step.get("name"): step for step in job["steps"] if step.get("name")}
    return steps["Validate workflow inputs"]["run"]


def test_track2_preflight_workflow_is_model_free_and_fail_closed():
    workflow, parsed = _workflow()
    triggers = parsed.get("on", parsed.get(True))
    inputs = triggers["workflow_dispatch"]["inputs"]
    job = parsed["jobs"]["preflight"]
    steps = {step.get("name"): step for step in job["steps"] if step.get("name")}

    assert parsed["permissions"] == {"contents": "read"}
    assert len(inputs) == 4
    assert "concurrency" not in parsed
    assert "azure/login" not in workflow
    assert "AZURE_" not in workflow
    assert "step8_grade.py" not in workflow
    assert "gh workflow run" not in workflow
    assert "id-token" not in workflow
    assert "contents: write" not in workflow

    checkout = steps["Checkout exact repository commit"]
    assert checkout["with"]["ref"] == "${{ inputs.expected_repository_commit }}"
    assert checkout["with"]["persist-credentials"] is False

    validate = steps["Validate workflow inputs"]["run"]
    assert 'repository_commit != os.environ["GITHUB_SHA"].lower()' in validate
    assert 'os.environ["GITHUB_REF"] != "refs/heads/main"' in validate
    assert 'set(plan) != expected_keys' in validate

    local_identity = steps["Verify source and local planner identities"]["run"]
    assert local_identity.index("actual_source_repo") < local_identity.index(
        "_planner_source_hash()"
    )
    assert "experiment source mismatch before HF download" in local_identity

    download = steps["Download pinned inference and deliverables"]
    assert download["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert "scripts/download_inference_from_hf.py" in download["run"]
    assert 'os.environ["PREFLIGHT_INFERENCE_REVISION"]' in download["run"]
    assert 'command.extend(("--expected-leading-task-id", task_id))' in download[
        "run"
    ]

    planner = steps["Run exact model-free cohort planner"]["run"]
    assert "scripts/preflight_track2_cohort.py" in planner
    for option in (
        "--expected-source-repo",
        "--expected-source-revision",
        "--expected-repository-commit",
        "--expected-planner-source-hash",
        "--expected-config-hash",
        "--expected-grader-source-hash",
        "--expected-rubric-sha",
        "--expected-task-id",
    ):
        assert option in planner
    assert "subprocess.run(command, check=True)" in planner

    upload = steps["Upload exact cohort plan"]
    assert upload["if"] == "always()"
    assert upload["uses"] == (
        "actions/upload-artifact@"
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    )
    assert upload["with"]["if-no-files-found"] == "warn"
    assert "batch-runner/workspace/track2_cohort_plan.json" in upload["with"]["path"]
    assert "batch-runner/workspace/track2_preflight_environment.txt" in upload["with"]["path"]
    assert steps["Publish plan summary"]["if"] == "always()"
    assert "Checkout was not completed" in steps["Publish plan summary"]["run"]
    assert "planner succeeded without producing a plan" in steps[
        "Publish plan summary"
    ]["run"]


def test_track2_preflight_workflow_requires_strict_identity_inputs():
    workflow, _ = _workflow()

    for name in (
        "experiment_yaml",
        "grading_config",
        "expected_repository_commit",
        "expected_plan_json",
    ):
        assert f"      {name}:\n" in workflow
    assert 'set(plan) != expected_keys' in workflow
    assert 'limit <= 0' in workflow
    assert 'if len(task_ids) != limit:' in workflow
    assert 'if len(set(task_ids)) != len(task_ids):' in workflow
    assert 'ref: ${{ inputs.expected_repository_commit }}' in workflow
    assert "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert "--require-hashes" in workflow
    assert "--only-binary=:all:" in workflow
    assert workflow.index("Verify source and local planner identities") < workflow.index(
        "HF_TOKEN: ${{ secrets.HF_TOKEN }}"
    )


def test_workflow_input_validation_writes_only_validated_environment(tmp_path):
    _, parsed = _workflow()
    github_env = tmp_path / "github-env"
    commit = "f" * 40
    env = {
        **os.environ,
        "PREFLIGHT_EXPERIMENT": "exp003_test",
        "PREFLIGHT_CONFIG": "validation.yaml",
        "EXPECTED_REPOSITORY_COMMIT": commit,
        "EXPECTED_PLAN_JSON": json.dumps(_valid_plan()),
        "GITHUB_SHA": commit,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_ENV": str(github_env),
    }

    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _validation_script(parsed)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    values = dict(
        line.split("=", 1)
        for line in github_env.read_text(encoding="utf-8").splitlines()
    )
    assert values == {
        "PREFLIGHT_INFERENCE_REVISION": "a" * 40,
        "PREFLIGHT_TASKS_LIMIT": "2",
        "EXPECTED_SOURCE_REPO": "owner/repo",
        "EXPECTED_PLANNER_SOURCE_HASH": "b" * 64,
        "EXPECTED_CONFIG_HASH": "c" * 16,
        "EXPECTED_GRADER_SOURCE_HASH": "d" * 64,
        "EXPECTED_RUBRIC_SHA": "e" * 40,
        "EXPECTED_TASK_IDS_JSON": '["task-1","task-2"]',
    }


def test_workflow_input_validation_rejects_commit_and_key_drift(tmp_path):
    _, parsed = _workflow()
    script = _validation_script(parsed)
    commit = "f" * 40
    base_env = {
        **os.environ,
        "PREFLIGHT_EXPERIMENT": "exp003_test",
        "PREFLIGHT_CONFIG": "validation.yaml",
        "EXPECTED_REPOSITORY_COMMIT": commit,
        "GITHUB_SHA": "0" * 40,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_ENV": str(tmp_path / "commit-env"),
        "EXPECTED_PLAN_JSON": json.dumps(_valid_plan()),
    }
    commit_result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        env=base_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert commit_result.returncode != 0
    assert "must equal GITHUB_SHA" in commit_result.stderr

    drifted = {**_valid_plan(), "unexpected": "value"}
    key_result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        env={
            **base_env,
            "GITHUB_SHA": commit,
            "GITHUB_ENV": str(tmp_path / "key-env"),
            "EXPECTED_PLAN_JSON": json.dumps(drifted),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert key_result.returncode != 0
    assert "invalid key set" in key_result.stderr

    branch_result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        env={
            **base_env,
            "GITHUB_SHA": commit,
            "GITHUB_REF": "refs/heads/feature",
            "GITHUB_ENV": str(tmp_path / "branch-env"),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert branch_result.returncode != 0
    assert "must be dispatched from main" in branch_result.stderr

    duplicate_json = json.dumps(_valid_plan()).replace(
        '"source_repo":', '"source_repo":"other/repo","source_repo":', 1
    )
    duplicate_result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        env={
            **base_env,
            "GITHUB_SHA": commit,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_ENV": str(tmp_path / "duplicate-env"),
            "EXPECTED_PLAN_JSON": duplicate_json,
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert duplicate_result.returncode != 0
    assert "expected_plan_json must be valid JSON" in duplicate_result.stderr


def test_track2_preflight_workflow_scripts_are_syntactically_valid():
    _, parsed = _workflow()
    scripts = [
        step["run"]
        for step in parsed["jobs"]["preflight"]["steps"]
        if "run" in step
    ]

    for script in scripts:
        shell_check = subprocess.run(
            ["bash", "-n"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        assert shell_check.returncode == 0, shell_check.stderr
        for match in re.finditer(
            r"(?:python|python3) - <<'PY'\n(?P<code>.*?)\nPY(?:\n|$)",
            script,
            re.DOTALL,
        ):
            compile(match.group("code"), "<workflow-heredoc>", "exec")


def test_early_failure_summary_does_not_require_checkout(tmp_path):
    _, parsed = _workflow()
    steps = {
        step.get("name"): step
        for step in parsed["jobs"]["preflight"]["steps"]
        if step.get("name")
    }
    summary_path = tmp_path / "summary.md"
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", steps["Publish plan summary"]["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "GITHUB_STEP_SUMMARY": str(summary_path),
            "PLANNER_OUTCOME": "skipped",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Checkout was not completed" in summary_path.read_text(encoding="utf-8")


def test_preflight_lock_is_hashed_and_excludes_paid_runtime_clients():
    lock = Path("requirements-track2-preflight.lock").read_text(encoding="utf-8")
    starts = list(re.finditer(r"(?m)^(?P<name>[A-Za-z0-9_.-]+)==", lock))
    requirements = [
        (
            match.group("name"),
            lock[match.start() : starts[index + 1].start()]
            if index + 1 < len(starts)
            else lock[match.start() :],
        )
        for index, match in enumerate(starts)
    ]

    assert len(requirements) == 27
    assert all("--hash=sha256:" in block for _, block in requirements)
    names = {name.lower() for name, _ in requirements}
    assert "azure-identity" not in names
    assert "openai" not in names
    assert "pytest" not in names
