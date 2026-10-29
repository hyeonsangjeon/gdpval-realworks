"""A chosen image is not a sandbox-readiness measurement.

The owner now requires hosted 24.04. Its historical unprepared failure remains
in the host table, separate from the new binary-scoped preparation policy.
Same-job probes must succeed before credentials; no sysctl, capability or
sandbox-backend shortcut substitutes for executing an isolated command.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
BATCH_WORKFLOW = ROOT / ".github" / "workflows" / "batch-run.yml"
BATCH_RUNNER = ROOT / "batch-runner"
HOST_RECORD = BATCH_RUNNER / "docs" / "codex_sandbox_hosts.json"
DIAGNOSTIC = BATCH_RUNNER / "scripts" / "diagnose_codex_sandbox_host.py"

#: Installation and pin verification precede the version-bound sandbox probe.
HOST_STEPS = (
    "Codex: install bubblewrap",
    "Codex: refuse to continue unless the pinned runtime is installed",
    "Codex: refuse to continue unless this host can isolate",
)

#: Every one of these would turn a red host green by taking the isolation away.
#: They are named rather than described so that adding one is a test failure
#: rather than a judgement call in review.
WAYS_TO_CHEAT = (
    "--privileged",
    "--cap-add",
    "--security-opt",
    "--userns=host",
    "sysctl",
    "apparmor_restrict_unprivileged_userns",
    "setcap",
    "unprivileged_userns_clone",
)


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(BATCH_WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def batch_job(workflow):
    return workflow["jobs"]["batch-run"]


@pytest.fixture(scope="module")
def step_names(batch_job):
    return [step.get("name") for step in batch_job["steps"]]


@pytest.fixture(scope="module")
def host_record():
    return json.loads(HOST_RECORD.read_text(encoding="utf-8"))["hosts"]


def _named_step(batch_job, name):
    for step in batch_job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r} in the batch-run job")


def test_the_batch_job_picks_its_host_from_the_mode(batch_job, host_record):
    policy = json.loads(HOST_RECORD.read_text())["execution_policy"]
    runner = policy["github_hosted_runner"]
    assert runner == "ubuntu-24.04"
    assert policy["required_same_job_readiness"] == "ready"
    assert policy["prepared_host_observation"] == "not_yet_measured_on_Actions"
    assert host_record[f"{runner}-host"]["readiness"] == "user_namespaces_restricted_by_security_policy"
    assert batch_job["runs-on"] == (
        "${{ needs.inspect-mode.outputs.uses_codex_foundry == 'true' "
        f"&& '{runner}' || 'ubuntu-latest' }}}}"
    )


def test_every_other_mode_keeps_the_host_it_always_had(batch_job):
    # The half that is not about Codex at all. This job runs every experiment
    # this repository has; moving all of them to a different image to fix one
    # mode would be a change nobody asked for, on a shared file, in a PR about
    # something else.
    assert "|| 'ubuntu-latest' }}" in batch_job["runs-on"]


def test_preparation_does_not_rewrite_the_historical_unprepared_host(host_record):
    assert host_record["ubuntu-24.04-host"]["readiness"] == "user_namespaces_restricted_by_security_policy"
    assert "ubuntu-latest" in host_record["ubuntu-24.04-host"]["os"]
    assert host_record["ubuntu-24.04-host"]["measured_by"] == "codex-sandbox-host-survey.yml, run 34202380505"
    assert host_record["ubuntu-22.04-host"]["readiness"] == "ready"


def test_the_host_steps_run_only_for_this_mode(batch_job):
    for name in HOST_STEPS:
        step = _named_step(batch_job, name)
        assert step["if"] == (
            "needs.inspect-mode.outputs.uses_codex_foundry == 'true'"
        ), name


def test_the_host_steps_run_after_the_refusals(step_names):
    # A dispatch that is about to be refused should install nothing and probe
    # nothing. Both block steps decide before any of this runs.
    blocks = (
        "Block agentic modes in credentialed general workflow",
        "Block unconfirmed codex_foundry in credentialed general workflow",
    )
    for block in blocks:
        for name in HOST_STEPS:
            assert step_names.index(block) < step_names.index(name), (block, name)


def test_the_host_steps_run_before_the_first_credential(step_names):
    # The whole value of these checks is that they are cheap and early. Placed
    # after the Azure steps they would still be true and would still be useless.
    first_credential = step_names.index(
        "Validate Azure OIDC identity before remote access"
    )
    for name in HOST_STEPS:
        assert step_names.index(name) < first_credential, name


def test_they_run_in_the_only_order_that_works(step_names):
    assert [step_names.index(name) for name in HOST_STEPS] == sorted(
        step_names.index(name) for name in HOST_STEPS
    )


def test_the_install_does_not_run_twice_over(batch_job):
    # A hosted image gaining bubblewrap should make this step do nothing, not
    # make it fetch a package that is already there.
    install = _named_step(batch_job, HOST_STEPS[0])
    assert "if command -v bwrap" in install["run"]


def test_the_install_carries_the_same_stall_guard_as_its_neighbour(batch_job):
    # batch-run.yml's own comment: the 2026-08-19 mirror outage hung five jobs
    # for 5h18m apiece, and "the same defect lives in every bare apt-get call in
    # this repo, so it gets the same guard". A new apt call is a new instance of
    # that defect unless it is guarded too.
    install = _named_step(batch_job, HOST_STEPS[0])["run"]
    for guard in (
        "Acquire::Retries=3",
        "DPkg::Lock::Timeout=60",
        "timeout 240 apt-get",
        "timeout 420 apt-get",
    ):
        assert guard in install, guard
    assert "for attempt in 1 2 3" in install


def test_installed_is_not_accepted_as_working(batch_job):
    probe = _named_step(batch_job, HOST_STEPS[2])
    assert probe["run"].index("scripts/prepare_codex_sandbox_host.py") < probe["run"].index("scripts/diagnose_codex_sandbox_host.py")
    assert "scripts/diagnose_codex_sandbox_host.py" in probe["run"]
    assert probe["working-directory"] == "batch-runner"
    # The survey workflow reads this diagnostic's verdict and carries on;
    # `continue-on-error` there is right because its job is to report. Here its
    # job is to stop, so the same flag would undo the step entirely.
    assert "continue-on-error" not in probe
    assert "|| true" not in probe["run"]
    assert "set -euo pipefail" in probe["run"]


def test_the_pinned_runtime_is_required_rather_than_hoped_for(batch_job):
    step = _named_step(batch_job, HOST_STEPS[1])
    assert "require_pinned_runtime" in step["run"]
    assert step["working-directory"] == "batch-runner"


def test_no_step_here_buys_a_pass_by_removing_the_isolation(batch_job):
    for name in HOST_STEPS:
        body = _named_step(batch_job, name)["run"]
        for shortcut in WAYS_TO_CHEAT:
            assert shortcut not in body, (name, shortcut)


def test_the_diagnostic_this_leans_on_actually_refuses(tmp_path):
    """Run it here, and hold its exit status to its own verdict.

    Every static assertion above is about a step that calls this script. If the
    script exited zero regardless, all of them would pass and none of them would
    mean anything. This runs on whatever host the suite is on: the development
    box (which is not ready, and must exit non-zero) and ubuntu-22.04 in the
    survey workflow (which is, and must exit zero) are both covered by the same
    equivalence, so neither needs to be named here.
    """
    report = tmp_path / "probe.json"
    finished = subprocess.run(
        [sys.executable, str(DIAGNOSTIC), "--json", "--out", str(report)],
        cwd=BATCH_RUNNER,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert report.exists(), finished.stderr
    readiness = json.loads(report.read_text(encoding="utf-8"))["readiness"]
    assert (finished.returncode == 0) == (readiness == "ready"), (
        f"exit {finished.returncode} for verdict {readiness!r}"
    )


def test_the_record_and_the_workflow_are_not_two_copies_of_one_claim():
    """The record is evidence; the workflow is a consequence of it.

    Written down twice, they drift. This asserts the direction of the
    dependency by reading the workflow's comment: whoever changes the runner
    should be sent to the measurement rather than left to reason about images.
    """
    text = BATCH_WORKFLOW.read_text(encoding="utf-8")
    assert "codex_sandbox_hosts.json" in text
