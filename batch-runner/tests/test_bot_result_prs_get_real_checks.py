"""A bot-authored result PR is checked, and an unchecked one cannot pass.

``batch-run.yml`` ends a successful experiment by opening a pull request that
carries one file, ``report.md``. It opens it with
``peter-evans/create-pull-request`` authenticated as ``GITHUB_TOKEN``, and
GitHub will not start a ``pull_request`` run for a pull request opened that way
— the rule that stops a workflow looping by writing to its own repository. It
does not decline quietly. A run row is created, it dies at startup with zero
jobs, and the API reports ``conclusion=failure`` with "This run likely failed
because of a workflow file issue."

Six for six on the result PRs measured — 33464032707, 33464032741 (#337),
33464910416, 33464910554 (#339), 33308414611, 33308414607 — while every
human-authored pull request touching the same paths ran normally, and the
workflow files were byte-identical between the two. So the message named a
defect that was not there, and the result PR showed an empty Checks list. An
empty list reads as "nothing to report". The truth was "never ran": the suite
had not seen the branch at all, and the experiment's own run still reported
success.

``workflow_dispatch`` is exempt from that rule and was already proven here —
``batch-run.yml`` has dispatched ``deploy.yml`` for the same reason since #303,
with ``actions: write`` already granted. But dispatching is not checking. A
dispatch that fails, or never starts, left the job green exactly as before.

So the runner now dispatches both required workflows against the PR head and
refuses to finish unless both come back successful, treating a check that never
reported as a failure rather than as an absence. These tests hold that. They
read the required list and the dispatches out of the workflow rather than
restating them, so adding a dispatch without requiring it — or requiring one
without dispatching it — fails here instead of at the next result PR. The last
two run the workflow's own shell against a scripted ``gh`` and assert what it
does, because the point of the change is a verdict, not a paragraph.

Nothing here calls a model, signs in to a cloud account, or spends anything.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
WORKFLOWS = REPOSITORY_ROOT / ".github" / "workflows"
BATCH_RUN = WORKFLOWS / "batch-run.yml"
BACKEND_TESTS = WORKFLOWS / "backend-tests.yml"

# The two steps the change turns on, named as the workflow names them.
DISPATCH_STEP = "Dispatch exact result PR validation"
VERIFY_STEP = "Verify dispatched result PR checks"
CONTRACT_STEP = "Verify dispatch contract"

# The input both sides agree on. A dispatch resolves a branch, and a branch
# moves; this is the commit the caller measured.
PIN_INPUT = "expected_sha"

# What a pinned dispatch must refuse. The same three the validation dispatch in
# deploy.yml refuses, asserted as written so dropping one fails here.
PIN_ASSERTIONS = (
    '[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]',
    '[[ "$GITHUB_SHA" == "$EXPECTED_SHA" ]]',
    '[[ "$WORKFLOW_SHA" == "$EXPECTED_SHA" ]]',
)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(document: dict) -> dict:
    # PyYAML resolves an unquoted `on:` key to the boolean True.
    return document.get("on", document.get(True, {})) or {}


def _steps(document: dict, job: str) -> list[dict]:
    return document["jobs"][job]["steps"]


def _step(document: dict, job: str, name: str) -> dict:
    for step in _steps(document, job):
        if step.get("name") == name:
            return step
    raise AssertionError(f"{job} has no step named {name!r}")


@pytest.fixture(scope="module")
def batch_run() -> dict:
    return _load(BATCH_RUN)


@pytest.fixture(scope="module")
def backend_tests() -> dict:
    return _load(BACKEND_TESTS)


@pytest.fixture(scope="module")
def verify_script(batch_run: dict) -> str:
    return _step(batch_run, "batch-run", VERIFY_STEP)["run"]


def test_the_suite_can_be_dispatched_at_a_named_commit(backend_tests: dict) -> None:
    """The trigger the bot PR can actually reach, with the pin required."""
    triggers = _triggers(backend_tests)
    assert "workflow_dispatch" in triggers, (
        "backend-tests.yml is reachable only through pull_request and push. "
        "A bot-authored result PR gets no pull_request run, so without a "
        "dispatch trigger the suite can never see it."
    )
    pin = triggers["workflow_dispatch"]["inputs"][PIN_INPUT]
    assert pin["required"] is True
    assert pin["type"] == "string"


def test_a_dispatched_run_refuses_to_be_a_different_commit(backend_tests: dict) -> None:
    """Reading the pin is not enough; the run must decline when it disagrees."""
    contract = _step(backend_tests, "pytest", CONTRACT_STEP)
    assert contract["if"] == "github.event_name == 'workflow_dispatch'"
    script = contract["run"]
    for assertion in PIN_ASSERTIONS:
        assert assertion in script, f"dispatch contract no longer checks: {assertion}"
    assert "set -euo pipefail" in script

    # The contract reads what GitHub said the run is for. Something has to read
    # what landed on disk, or a push racing the dispatch is tested silently
    # under the pinned commit's name.
    checkout_check = _step(backend_tests, "pytest", "Verify exact checkout")
    assert '[[ "$(git rev-parse HEAD)" == "$EXPECTED_SHA" ]]' in checkout_check["run"]


def test_being_dispatchable_did_not_cost_it_a_permission(backend_tests: dict) -> None:
    """The suite still runs from a fork PR, where no token and no secret exist."""
    assert backend_tests["permissions"] == {"contents": "read"}
    assert "secrets." not in BACKEND_TESTS.read_text(encoding="utf-8")


def test_every_required_check_is_one_the_runner_actually_dispatches(
    batch_run: dict, verify_script: str
) -> None:
    """The list that is waited on and the list that is asked for are the same.

    This is the coupling that keeps the rest honest. Requiring a workflow that
    is never dispatched hangs until the timeout and fails closed — noisy, but
    safe. Dispatching one that is never required is the dangerous direction:
    it runs, it can fail, and nothing reads the verdict.
    """
    dispatch_script = _step(batch_run, "batch-run", DISPATCH_STEP)["run"]
    dispatched = set(re.findall(r"gh workflow run (\S+\.yml)", dispatch_script))
    required = set(
        _step(batch_run, "batch-run", VERIFY_STEP)["env"]["REQUIRED_WORKFLOWS"].split()
    )

    assert dispatched, "the dispatch step no longer dispatches anything"
    assert required == dispatched, (
        f"dispatched {sorted(dispatched)} but waits on {sorted(required)}; "
        "a dispatched workflow nobody waits on can fail unnoticed"
    )
    assert "backend-tests.yml" in required

    # Both dispatches pin the same commit the PR was verified at.
    for workflow in dispatched:
        block = dispatch_script.split(f"gh workflow run {workflow}")[1]
        assert f'{PIN_INPUT}="$PR_HEAD_SHA"' in block.split("gh workflow run")[0]


def test_the_verdict_is_read_and_never_written(verify_script: str) -> None:
    """Fail closed, and do not manufacture the thing being checked.

    A shortcut exists here that would make every result PR look green: post a
    passing status or check-run from the runner. It would also make this whole
    file decorative. The step may read a conclusion; it may not create one.
    """
    assert "exit 1" in verify_script
    assert "::error::" in verify_script

    forbidden = (
        "/statuses/",  # POST a commit status
        "/check-runs",  # POST a check run
        "gh pr merge",
        "gh pr review",
        "--admin",
        "--auto",
    )
    for token in forbidden:
        assert token not in verify_script, (
            f"the verification step must not use {token!r} — it reports a "
            "verdict it read, it does not create or act on one"
        )

    # The failure path may swallow errors from its own reporting calls, but the
    # exit that fails the job must not be guarded.
    assert not re.search(r"exit 1\s*\|\|", verify_script)
    assert "continue-on-error" not in verify_script


def test_a_check_that_never_reported_is_treated_as_a_failure(verify_script: str) -> None:
    """Absence is the symptom, so absence cannot be the pass condition."""
    assert "never-reported" in verify_script
    assert 'verdict=${conclusion[$wf]:-never-reported}' in verify_script
    assert '[[ "$verdict" != "success" ]]' in verify_script, (
        "an allow-list of bad conclusions would let a new GitHub conclusion "
        "value through; only success may pass"
    )
    assert "timed out after" in verify_script


def test_the_wait_pins_the_head_sha_it_was_given(verify_script: str) -> None:
    """A dispatch names a branch; only the SHA identifies the tree."""
    assert "head_sha=$PR_HEAD_SHA" in verify_script
    assert "event=workflow_dispatch" in verify_script
    assert 'select(.status == "completed")' in verify_script


# --------------------------------------------------------------------------
# What it does, not what it says. The two below run the workflow's own shell.
# --------------------------------------------------------------------------

GH_STUB = """#!/usr/bin/env bash
echo "GH_CALL $*" >> "$SIM_LOG"
case "$1" in
  api)
    case "$2" in
      *backend-tests.yml*) v="$SIM_BACKEND" ;;
      *deploy.yml*)        v="$SIM_DEPLOY" ;;
      *)                   v="" ;;
    esac
    [[ -z "$v" ]] && exit 0
    printf '%s\\thttps://example.invalid/run\\n' "$v"
    ;;
  *) : ;;
esac
"""


def _run_verification(script: str, tmp_path: Path, backend: str, deploy: str):
    root = Path(tempfile.mkdtemp(dir=tmp_path))
    stub_dir = root / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "gh"
    stub.write_text(GH_STUB, encoding="utf-8")
    stub.chmod(0o755)
    log = root / "calls.log"
    log.touch()

    environment = dict(os.environ)
    environment.update(
        PATH=f"{stub_dir}{os.pathsep}{environment['PATH']}",
        SIM_LOG=str(log),
        SIM_BACKEND=backend,
        SIM_DEPLOY=deploy,
        GITHUB_REPOSITORY="owner/repo",
        PR_NUMBER="999",
        PR_HEAD_SHA="a" * 40,
        REQUIRED_WORKFLOWS="backend-tests.yml deploy.yml",
        WAIT_SECONDS="2",
        POLL_SECONDS="1",
    )
    completed = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=environment,
        timeout=120,
    )
    return completed, log.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize(
    ("backend", "deploy", "expected_exit", "why"),
    [
        ("success", "success", 0, "both green"),
        ("failure", "success", 1, "the suite failed"),
        ("success", "failure", 1, "the dashboard validation failed"),
        ("success", "cancelled", 1, "a cancelled run is not a passing run"),
        ("timed_out", "success", 1, "a timed-out run is not a passing run"),
        ("", "success", 1, "the suite never reported — the original symptom"),
        ("", "", 1, "neither reported"),
    ],
)
def test_only_two_observed_successes_let_the_job_finish(
    verify_script: str, tmp_path: Path, backend, deploy, expected_exit, why
) -> None:
    completed, _ = _run_verification(verify_script, tmp_path, backend, deploy)
    assert completed.returncode == expected_exit, (
        f"{why}: expected exit {expected_exit}, got {completed.returncode}\n"
        f"{completed.stdout}\n{completed.stderr}"
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_a_failing_result_pr_is_put_back_into_draft(
    verify_script: str, tmp_path: Path
) -> None:
    """An empty Checks list must not be mistakable for a clean one."""
    completed, calls = _run_verification(verify_script, tmp_path, "", "success")
    assert completed.returncode == 1
    assert "pr ready 999" in calls and "--undo" in calls, (
        "a result PR whose checks did not pass stays open and mergeable"
    )
    assert "pr comment 999" in calls

    passing, quiet = _run_verification(verify_script, tmp_path, "success", "success")
    assert passing.returncode == 0
    assert "--undo" not in quiet and "pr comment" not in quiet, (
        "a passing run must not touch the pull request"
    )
