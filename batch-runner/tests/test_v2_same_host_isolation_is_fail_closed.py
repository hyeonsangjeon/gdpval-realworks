"""Asking for isolation and not getting it has to stop the run, not soften it.

The arrangement this guards is new and the failure it guards against is old.
Until now no workflow passed ``--isolated-approval`` at all, so ``select_backend``
took ``AgenticV2FixtureBackend`` and ``exec_run`` answered
``capability_unavailable`` to everything. That was correct, because the
pre-registered stage said so. It stops being correct the moment a dispatch asks
for ``same-host``: from then on, falling back to the fixture would produce a run
that looks like every other run, costs what every other run costs, and reports
isolation it never had. A reader comparing it against a fixture run would be
comparing two fixture runs.

So the gate is in the free job, which spends nothing, and it fails the dispatch
rather than downgrading it. These tests hold that shape in place: the input
exists, the free job takes the reading, a runner that cannot host stops a
``same-host`` dispatch, a ``capability-check`` never reaches the job that
spends, and a ``fixture`` dispatch is not failed by a reading it never needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_containment_readiness import (  # noqa: E402
    NEEDS_THE_PROGRAMS_INSTALLED,
)
from core.agentic_v2_kvm_probe import KvmProbe  # noqa: E402
from scripts.check_runner_can_host_a_guest import (  # noqa: E402
    HARDWARE_ACTUALLY_WORKS,
    look,
)

WORKFLOW = BATCH_RUNNER_ROOT.parent / ".github" / "workflows" / "agentic-v2-stage-run.yml"
CHECK_SCRIPT = "check_runner_can_host_a_guest.py"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def the_step(workflow: dict, job: str, name: str) -> dict:
    for step in workflow["jobs"][job]["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"{job} has no step named {name!r}")


def a_probe(*, usable: bool) -> KvmProbe:
    return KvmProbe(
        device="/dev/kvm",
        present=usable,
        opened=usable or None,
        api_version=12 if usable else None,
        made_a_machine=usable or None,
        because="a reading taken by a test",
    )


# ── the dispatch surface ──────────────────────────────────────────────────


def test_the_dispatch_offers_the_three_arrangements_and_defaults_to_fixture(
    workflow: dict,
) -> None:
    """Defaulting anywhere else would change what an unchanged dispatch does."""
    isolation = workflow[True]["workflow_dispatch"]["inputs"]["isolation"]

    assert isolation["options"] == ["fixture", "capability-check", "same-host"]
    assert isolation["default"] == "fixture", (
        "every dispatch that predates this input has to keep meaning what it "
        "meant, and what it meant was the fixture backend"
    )


def test_the_free_job_takes_the_reading(workflow: dict) -> None:
    """A guard nobody calls is the defect this repository keeps rediscovering."""
    step = the_step(workflow, "free", "Read whether this runner could host a guest")

    assert CHECK_SCRIPT in step["run"]
    assert "if:" not in step, (
        "the reading is free and is taken on every mode, so that a log always "
        "records what the runner could do"
    )


def test_the_free_reading_does_not_gate_on_what_a_step_installs(
    workflow: dict,
) -> None:
    """``--require-programs`` here would fail every runner, always.

    firecracker and jailer are not on a bare runner image. Gating the free
    reading on them would report every GitHub runner as unable to host a guest,
    which is a fact about the image and not about the machine.
    """
    step = the_step(workflow, "free", "Read whether this runner could host a guest")

    assert "--require-programs" not in step["run"]


# ── the permission the runner image withholds ─────────────────────────────


def test_the_device_is_granted_before_it_is_asked_about(workflow: dict) -> None:
    """A reading taken before the grant answers a question nobody asked.

    Run 35072131325 found /dev/kvm present on ubuntu-24.04 and the open refused
    with Permission denied, because udev ships the node as root:kvm 0660 and
    the account a job runs as is not in the kvm group. Granting after the
    reading would leave the gate refusing a runner that could in fact host.
    """
    steps = [step.get("name") for step in workflow["jobs"]["free"]["steps"]]

    grant = steps.index("Let this job open the hardware virtualisation device")
    reading = steps.index("Read whether this runner could host a guest")
    assert grant < reading


def test_a_fixture_dispatch_has_its_permissions_left_alone(workflow: dict) -> None:
    """That arrangement boots no guest, so it needs nothing widened."""
    step = the_step(
        workflow, "free", "Let this job open the hardware virtualisation device"
    )

    assert step["if"] == "${{ inputs.isolation != 'fixture' }}"


def test_the_grant_is_narrow_and_is_not_the_recipe_that_circulates() -> None:
    """``chmod 0666`` opens the device to every account on the machine."""
    script = (
        BATCH_RUNNER_ROOT / "scripts" / "allow_this_job_to_open_kvm.sh"
    ).read_text(encoding="utf-8")

    commands = [
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    ]
    assert not any("0666" in line or "a+rw" in line for line in commands)
    assert any("setfacl" in line for line in commands)


def test_the_grant_never_decides_whether_the_runner_is_capable() -> None:
    """It exits 0 on failure so that the probe, not the grant, is the gate."""
    script = (
        BATCH_RUNNER_ROOT / "scripts" / "allow_this_job_to_open_kvm.sh"
    ).read_text(encoding="utf-8")

    exits = {
        line.split()[1]
        for line in script.splitlines()
        if line.strip().startswith("exit ")
    }
    assert exits == {"0"}, (
        "a grant that failed is reported by the reading below it; failing here "
        "would stop a fixture run for a permission it never needed"
    )


# ── what happens when the answer is no ────────────────────────────────────


def test_a_runner_that_cannot_host_stops_a_same_host_dispatch(workflow: dict) -> None:
    step = the_step(workflow, "free", "Read whether this runner could host a guest")
    run = step["run"]

    assert 'if [ "$ISOLATION" = "same-host" ]' in run
    assert "exit 1" in run
    assert step["env"]["ISOLATION"] == "${{ inputs.isolation }}"


def test_a_fixture_dispatch_is_not_failed_by_a_reading_it_never_needed(
    workflow: dict,
) -> None:
    """The refusal is conditional on what was asked for, not on the reading.

    The pre-registered stage-one arrangement boots no guest. Failing it because
    the runner could not have booted one would refuse the runs that work, which
    is the shape of mistake this file exists to prevent in the other direction
    as well.
    """
    run = the_step(
        workflow, "free", "Read whether this runner could host a guest"
    )["run"]

    exits = [line.strip() for line in run.splitlines() if line.strip() == "exit 1"]
    assert len(exits) == 1, "there is one refusal and it is the same-host one"
    before_the_exit = run[: run.index("exit 1")]
    assert '"$ISOLATION" = "same-host"' in before_the_exit


def test_the_reading_is_kept_whatever_it_said(workflow: dict) -> None:
    """A no is the evidence for the finding and is the thing to compare against."""
    step = the_step(workflow, "free", "Keep the capability reading")

    assert step["if"].startswith("always()")
    assert step["with"]["if-no-files-found"] == "error"


def test_keeping_the_reading_does_not_ask_hashfiles_about_runner_temp(
    workflow: dict,
) -> None:
    """``hashFiles()`` only sees inside ``GITHUB_WORKSPACE``.

    Asked about a path under ``RUNNER_TEMP`` it answers the empty string on
    every runner, so the condition is never true and the step silently skips.
    Run 35072131325 took the reading and then did not keep it, and the job was
    green either way, which is the shape of failure that survives a review.
    """
    step = the_step(workflow, "free", "Keep the capability reading")

    assert "hashFiles" not in step["if"]
    assert "steps.capability.outcome" in step["if"], (
        "the upload follows the step that writes the file, so that a run which "
        "never reached the reading does not go red for not having one"
    )


def test_asking_whether_it_is_possible_never_reaches_the_job_that_spends(
    workflow: dict,
) -> None:
    condition = workflow["jobs"]["paid"]["if"]

    assert "inputs.mode == 'paid'" in condition
    assert "inputs.isolation != 'capability-check'" in condition


def test_nothing_is_accounted_for_when_nothing_was_meant_to_run(
    workflow: dict,
) -> None:
    """The accounting job follows the job it accounts for.

    Left running, it would fetch a shard record that was never written and go
    red, which a reader would take for a broken run rather than the empty one
    it was asked for.
    """
    condition = workflow["jobs"]["collect"]["if"]

    assert "inputs.isolation != 'capability-check'" in condition
    assert "always()" in condition, (
        "a shard that failed is still the shard whose bill someone needs"
    )


# ── the verdict the script forms ──────────────────────────────────────────


def test_hardware_that_does_not_work_blocks_whatever_else_holds() -> None:
    report = look(probe=a_probe(usable=False))

    assert report["could_host_a_guest"] is False
    assert HARDWARE_ACTUALLY_WORKS in [
        one["claim"] for one in report["blocked_by"]
    ]


def test_the_programs_do_not_gate_until_a_job_says_they_should() -> None:
    """Before the install step their absence is about the image, not the host."""
    without = look(probe=a_probe(usable=True))
    with_them = look(probe=a_probe(usable=True), require_programs=True)

    programs_without = _claim(without, NEEDS_THE_PROGRAMS_INSTALLED)
    programs_with = _claim(with_them, NEEDS_THE_PROGRAMS_INSTALLED)

    assert programs_without["gates"] is False
    assert programs_with["gates"] is True
    assert programs_without["verdict"] == programs_with["verdict"], (
        "the flag changes what the verdict counts for, never what it is"
    )


def test_the_new_claim_always_gates() -> None:
    for require in (False, True):
        report = look(probe=a_probe(usable=True), require_programs=require)
        assert _claim(report, HARDWARE_ACTUALLY_WORKS)["gates"] is True


def test_the_policy_claims_are_left_out_of_a_capability_reading() -> None:
    """They ask whether the rules are applied, which needs a running machine.

    Including them would make this refuse on every host — a true sentence about
    containment and a useless one about whether a runner could host a guest.
    """
    report = look(probe=a_probe(usable=True))

    claims = [one["claim"] for one in report["claims"]]
    assert not any("the small isolated virtual machine" in one for one in claims)
    assert HARDWARE_ACTUALLY_WORKS in claims
    assert len(claims) == 5, "four readings that existed, and the one that did not"


def _claim(report: dict, claim: str) -> dict:
    for one in report["claims"]:
        if one["claim"] == claim:
            return one
    raise AssertionError(f"no claim {claim!r} in {[o['claim'] for o in report['claims']]}")
