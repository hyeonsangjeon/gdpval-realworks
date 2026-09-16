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

#: The one place a guest is booted and admitted, called by both jobs.
BOOT_ACTION = "./.github/actions/boot-a-guest-on-this-runner"
ACTION_FILE = BATCH_RUNNER_ROOT.parent / BOOT_ACTION.removeprefix("./") / "action.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def boot_action() -> dict:
    return yaml.safe_load(ACTION_FILE.read_text(encoding="utf-8"))


def the_step(workflow: dict, job: str, name: str) -> dict:
    for step in workflow["jobs"][job]["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"{job} has no step named {name!r}")


def where(workflow: dict, job: str, name: str) -> int:
    for index, step in enumerate(workflow["jobs"][job]["steps"]):
        if step.get("name") == name:
            return index
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


# ── the rehearsal and the real thing are one thing ────────────────────────


def test_both_jobs_boot_through_the_same_action(workflow: dict) -> None:
    """A rehearsal that is a copy stops being a rehearsal on the first edit.

    The free job exists to find out, for nothing, whether the paid job's
    arrangement works. If the two were written out separately, the free leg
    would keep passing about an arrangement the paid leg no longer had, and
    the first anybody heard of it would be a charged run.
    """
    free = the_step(workflow, "free", "Boot a guest and admit it, on this runner")
    paid = the_step(workflow, "paid", "Boot a guest and admit it, on this runner")

    assert free["uses"] == BOOT_ACTION
    assert paid["uses"] == BOOT_ACTION
    assert ACTION_FILE.is_file(), (
        "a local action is resolved from the checkout, so a workflow naming a "
        "path that is not there fails at parse time on the runner and nowhere "
        "before it"
    )


def test_neither_job_boots_a_guest_for_a_fixture_dispatch(workflow: dict) -> None:
    """The pre-registered arrangement boots nothing and needs none of this."""
    for job in ("free", "paid"):
        step = the_step(workflow, job, "Boot a guest and admit it, on this runner")
        assert step["if"] == "${{ inputs.isolation == 'same-host' }}"


def test_the_paid_job_boots_before_it_holds_a_session(workflow: dict) -> None:
    """Pulling an image and running a privileged launcher on a box that is
    already holding a federated session buys nothing and widens what a failure
    there is next to. The login adds the credential to a proven machine."""
    boot = where(workflow, "paid", "Boot a guest and admit it, on this runner")
    login = where(workflow, "paid", "Azure Login (OIDC)")

    assert boot < login


def test_the_paid_job_is_granted_the_device_on_its_own_machine(
    workflow: dict,
) -> None:
    """The free job's grant was on the free job's runner.

    These are two machines. A grant taken in the job that spends nothing says
    nothing about the one that spends, and the device is root:kvm 0660 on both.
    """
    grant = where(workflow, "paid", "Let this job open the hardware virtualisation device")
    boot = where(workflow, "paid", "Boot a guest and admit it, on this runner")

    assert grant < boot
    step = the_step(
        workflow, "paid", "Let this job open the hardware virtualisation device"
    )
    assert step["if"] == "${{ inputs.isolation == 'same-host' }}"


# ── the flag is passed, or the run stops ──────────────────────────────────


@pytest.mark.parametrize("job, name", [("free", "Dry run"), ("paid", "Run")])
def test_a_same_host_run_refuses_to_start_without_an_approval(
    workflow: dict, job: str, name: str
) -> None:
    """The one substitution this whole path exists to prevent.

    Appending the flag only when the file happens to be there would turn a
    guest that did not boot into a run on the fixture backend. Every task would
    answer, the paid one would be charged, and the record would say isolation.
    """
    run = the_step(workflow, job, name)["run"]

    assert 'if [ ! -f "$APPROVAL" ]' in run
    assert "--isolated-approval" in run
    guard = run.index('if [ ! -f "$APPROVAL" ]')
    passes = run.index("--isolated-approval")
    assert guard < passes, "the refusal comes before the flag, not after it"


@pytest.mark.parametrize("job, name", [("free", "Dry run"), ("paid", "Run")])
def test_the_approval_the_run_reads_is_the_one_the_boot_wrote(
    workflow: dict, job: str, name: str
) -> None:
    """Two paths that drift apart fail closed, which is safe and baffling."""
    written = the_step(workflow, job, "Boot a guest and admit it, on this runner")
    read = the_step(workflow, job, name)

    assert read["env"]["APPROVAL"] == written["with"]["approval"]


@pytest.mark.parametrize("job, name", [("free", "Dry run"), ("paid", "Run")])
def test_a_fixture_dispatch_passes_no_flag_and_takes_no_privilege(
    workflow: dict, job: str, name: str
) -> None:
    """``fixture`` runs exactly as it did before any of this existed.

    Both the flag and the account are decided inside one condition, so there is
    no arrangement in which a fixture dispatch picks up half of it.
    """
    run = the_step(workflow, job, name)["run"]

    for line in run.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if "--isolated-approval" in stripped or "sudo" in stripped:
            assert 'ISOLATION" = "same-host"' in run[: run.index(stripped)], (
                f"{stripped!r} is reached without checking what was dispatched"
            )


def test_the_run_step_hands_across_every_variable_it_names(workflow: dict) -> None:
    """``sudo env VAR=…`` rather than ``-E``, and for two reasons.

    ``sudo -E`` needs a SETENV tag nobody here can confirm without dispatching,
    and it keeps the whole environment, so what crosses the boundary is
    whatever happened to be set. Naming them makes the list readable and makes
    an omission a failure rather than a surprise.
    """
    step = the_step(workflow, "paid", "Run")
    run = step["run"]

    assert "sudo -E" not in run
    assert 'sudo env "PATH=$PATH"' in run
    # Everything the stage reads out of the environment, and nothing else. The
    # rest of the step's env block is read by the shell, not by the process.
    for name in (
        "AZURE_AI_ROUTE_PROFILE",
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES",
        "AZURE_AI_EXPECTED_DIRECT_ACCOUNT",
        "AZURE_AI_EXPECTED_PROJECT_ACCOUNT",
        "AZURE_AI_EXPECTED_PROJECT_NAME",
    ):
        assert name in step["env"], f"{name} is not given to the step at all"
        assert f'"{name}=${name}"' in run, (
            f"{name} is in the step's environment and does not cross into the "
            "run, so the stage would see it unset and refuse -- or worse, "
            "default"
        )


def test_the_credential_is_pointed_at_the_session_the_login_wrote(
    workflow: dict,
) -> None:
    """Root has a different ``$HOME``, and the CLI credential reads ``$HOME``.

    Nothing is copied and nothing is exported: the session stays where
    ``azure/login`` put it. What this does is name the one directory the
    privileged process may look in, instead of letting it look in the job's
    whole home by accident of ``$HOME``.
    """
    run = the_step(workflow, "paid", "Run")["run"]

    assert '"AZURE_CONFIG_DIR=${AZURE_CONFIG_DIR:-$HOME/.azure}"' in run


def test_the_same_question_is_asked_at_the_privilege_that_will_ask_it(
    workflow: dict,
) -> None:
    """The one thing about the sudo arrangement the free job cannot rehearse.

    It has no federated session to acquire against. So the paid job asks -- for
    a token and no model call -- before the dataset and well before task one.
    """
    step = the_step(workflow, "paid", "Verify the same-host run can reach that session")

    assert step["if"] == "${{ inputs.isolation == 'same-host' }}"
    assert "sudo env" in step["run"]
    assert "--verify-session" in step["run"]
    assert where(workflow, "paid", "Verify the same-host run can reach that session") < where(
        workflow, "paid", "Run"
    )


# ── what the run leaves behind ────────────────────────────────────────────


def test_the_exit_code_is_recorded_before_anything_else_can_fail(
    workflow: dict,
) -> None:
    """``set +e`` and the capture are the reason a charged failure is a finding.

    Handing the output back to the job's account is housekeeping and is allowed
    to fail. Letting it run first would replace the stage's exit code with
    ``chown``'s, and a cohort that failed would report success.
    """
    run = the_step(workflow, "paid", "Run")["run"]

    assert "STAGE_EXIT=$?" in run
    assert 'echo "stage_exit=$STAGE_EXIT"' in run
    assert run.index('echo "stage_exit=$STAGE_EXIT"') < run.index("chown")


def test_the_proof_is_kept_whatever_it_said(workflow: dict) -> None:
    """The case worth keeping it for is the one where the boot failed."""
    for job, name in (
        ("free", "Keep what the rehearsal found"),
        ("paid", "Keep what this runner was shown to be"),
    ):
        step = the_step(workflow, job, name)
        assert step["if"].startswith("${{ always()")
        assert "same-host" in step["if"]
        assert step["with"]["if-no-files-found"] == "warn", (
            "an approval is absent by design on the path where admission was "
            "refused, and going red for that would report the wrong thing"
        )


def test_the_proof_is_not_named_like_a_shard_record(workflow: dict) -> None:
    """``agentic-v2-<stage>-shard-*`` is a pattern two other steps download.

    A shard fetches it to find out whether a sibling halted the run, and the
    collect job fetches it to add up what the stage spent. Handing either of
    them a bundle of boot artefacts to read as stage records would break a
    check that has nothing to do with isolation.
    """
    proof = the_step(workflow, "paid", "Keep what this runner was shown to be")
    record = the_step(workflow, "paid", "Keep the record, the journal and what was written")

    assert not proof["with"]["name"].startswith("agentic-v2-")
    assert record["with"]["name"].startswith("agentic-v2-")
    assert proof["with"]["name"] != record["with"]["name"]


# ── the action itself ─────────────────────────────────────────────────────


def test_the_action_names_the_interpreter_absolutely(boot_action: dict) -> None:
    """``sudo`` resets PATH to ``secure_path``, which has no setup-python in it.

    A bare ``sudo python`` finds the system interpreter, which has none of the
    dependencies installed, and the failure reads like a missing package. The
    one privileged step that does not do this runs ``install``, which is on
    ``secure_path`` on every image and needs no PATH of its own.
    """
    privileged = 0
    for step in boot_action["runs"]["steps"]:
        run = step.get("run", "")
        for line in run.splitlines():
            stripped = line.strip()
            if not stripped.startswith("sudo ") or ".py" not in stripped:
                continue
            privileged += 1
            assert 'env "PATH=$PATH"' in stripped, step["name"]
            assert '"$PYTHON"' in stripped, step["name"]
            assert 'PYTHON="$(command -v python)"' in run, step["name"]

    assert privileged == 2, (
        "the boot and the approval, and nothing else in this action, run a "
        "program of ours as root -- if that count changes somebody widened it"
    )


def test_the_action_asks_again_whether_the_launcher_landed(
    boot_action: dict,
) -> None:
    """The only place ``--require-programs`` belongs.

    The free job's first reading leaves the programs out because their absence
    from a bare runner image is a fact about the image. This one runs after the
    install and asks the question the boot will ask, with the same
    ``shutil.which`` -- rather than trusting the install step's exit code.
    """
    steps = [step.get("name") for step in boot_action["runs"]["steps"]]
    install = steps.index("Install the pinned launcher programs")
    reading = steps.index("Read the runner again, now that the launcher is on it")
    boot = steps.index("Boot one guest on this runner")

    assert install < reading < boot
    run = boot_action["runs"]["steps"][reading]["run"]
    assert "--require-programs" in run
    assert CHECK_SCRIPT in run


def test_the_approval_is_written_after_the_guest_has_booted(
    boot_action: dict,
) -> None:
    """It re-hashes the images the boot wrote, so there is nothing to admit
    before then, and the selector would refuse an artefact that is not there."""
    steps = [step.get("name") for step in boot_action["runs"]["steps"]]

    assert steps.index("Boot one guest on this runner") < steps.index(
        "Write the approval this runner will admit"
    )


def test_the_action_reads_no_secret(boot_action: dict) -> None:
    """It runs before ``azure/login`` in the paid job, and holds nothing.

    A privileged step is a poor place to widen what a job can see. This one
    takes an artefact path, a scratch directory and two strings for the record.
    """
    text = ACTION_FILE.read_text(encoding="utf-8")

    assert "secrets." not in text
    assert set(boot_action["inputs"]) == {
        "artefact",
        "approval",
        "scratch",
        "workdir",
        "approved-by",
        "session",
        "vcpu-count",
        "install-report",
    }


def _claim(report: dict, claim: str) -> dict:
    for one in report["claims"]:
        if one["claim"] == claim:
            return one
    raise AssertionError(f"no claim {claim!r} in {[o['claim'] for o in report['claims']]}")
