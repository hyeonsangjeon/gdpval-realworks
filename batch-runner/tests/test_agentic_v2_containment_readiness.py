"""What containment this repository can actually get, and what follows from it.

These tests pin the answer to the question the Agentic Sandbox V2 specification
left open: is the small isolated virtual machine its substrate manifest requires
available on any machine this repository runs on?

Nothing here calls a model, runs a command, signs in to anything, or spends
money. Every machine below is either described to the code as a set of readings
or is this machine, read the same read-only way the check itself reads it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.agentic_v2_containment_readiness import (
    FIRECRACKER_KERNEL_POLICY_URL,
    NEEDS_A_KERNEL_FIRECRACKER_TESTS,
    NEEDS_A_PROCESSOR_THAT_CAN,
    NEEDS_THE_PROGRAMS_INSTALLED,
    NEEDS_TO_REACH_THE_HARDWARE,
    NOTHING_APPLIES_THESE_RULES_YET,
    OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES,
    RECORDED_FINDINGS,
    MachineFacts,
    check_every_machine_has_a_containment_finding,
    containment_answer_everywhere,
    describe_containment,
    judge_containment,
    read_this_machine,
    refuse_command_execution,
    runner_labels_used_by_workflows,
)
from core.agentic_v2_substrate import (
    MICROVM_MEMORY_MIB,
    MICROVM_WALL_CLOCK_SECONDS,
    MICROVM_WORKDIR_QUOTA_MIB,
    REQUIRED_MICROVM_POLICY,
)

WORKFLOWS_DIRECTORY = Path(__file__).resolve().parents[2] / ".github" / "workflows"


# ── Describing a machine to the code ──────────────────────────────────────


def a_machine(**changes) -> MachineFacts:
    """A machine that meets every requirement, unless a test takes one away."""
    settings = {
        "kernel_release": "6.1.0-generic",
        "processor_flags": ("fpu", "vmx", "aes"),
        "processor_flags_were_readable": True,
        "hardware_virtualisation_reachable": True,
        "firecracker_programs_found": ("firecracker", "jailer"),
        "firecracker_programs_missing": (),
        "inside_a_container": False,
        "container_evidence": "",
    }
    settings.update(changes)
    return MachineFacts(**settings)


def claim(answer, wanted: str):
    """The one judged claim whose wording starts with ``wanted``."""
    matches = [item for item in answer.requirements if item.claim.startswith(wanted)]
    assert matches, f"no claim starting {wanted!r} in {[i.claim for i in answer.requirements]}"
    return matches[0]


def a_microvm_report(*, kvm: bool = False, programs: tuple[str, ...] = ()) -> dict:
    """The shape core.agentic_v2_microvm.inspect_microvm_readiness hands back."""
    return {
        "checks": {"kvm": kvm},
        "tools": {
            name: {
                "status": "present" if name in programs else "missing",
                "sha256": None,
                "size": None,
            }
            for name in ("firecracker", "jailer")
        },
    }


# ── A machine that has everything ─────────────────────────────────────────


def test_a_machine_with_everything_could_host_the_containment():
    answer = judge_containment(a_machine())

    assert answer.machine_could_host_it is True


def test_a_machine_with_everything_still_does_not_have_the_containment():
    """Being able to start a machine is not the same as the rules being applied.

    These were one field until 2026-08-26, and that is how a rule nothing
    applies came to be reported as met. On the three machines in play it never
    showed, because none of them can start a virtual machine at all. On the
    first machine that could, the old report would have said the containment was
    in place while nothing carried a single rule to it.
    """
    answer = judge_containment(a_machine())

    assert answer.required_containment_available is False
    assert answer.whats_missing(), "a rule nobody applies is not nothing missing"
    assert all(
        "unenforced rather than met" in line for line in answer.whats_missing()
    )


def test_every_setting_the_manifest_asks_for_appears_in_the_answer():
    """The report covers the whole policy, not the part that is easy to check.

    Three of the manifest's settings — no network, a read-only root filesystem,
    a temporary working directory — are things you configure on a virtual
    machine rather than things a host has or lacks. Leaving them out of the
    report would make it read as though the manifest asked for less than it
    does, so each one gets a line either way.
    """
    answer = judge_containment(a_machine())
    wording = " ".join(item.claim for item in answer.requirements)

    for value in REQUIRED_MICROVM_POLICY.values():
        if value is True:
            continue
        assert str(value) in wording, f"the answer never mentions {value!r}"


def test_the_configured_settings_are_not_claimed_to_have_been_checked():
    """Nothing boots a virtual machine here, and the wording must not imply it."""
    answer = judge_containment(a_machine())
    network = claim(answer, "the small isolated virtual machine's network")

    assert network.met is None
    assert network.verdict == "cannot be established here"
    assert NOTHING_APPLIES_THESE_RULES_YET in network.because


def test_the_report_names_the_module_that_would_have_to_apply_the_rules():
    """A reader who wants to fix this has to be told where the gap is.

    "Cannot be established" with no address sends somebody looking for a better
    machine, which is the wrong work: the rules would go unapplied on the best
    machine in the world.
    """
    answer = judge_containment(a_machine())
    quota = claim(answer, "the command may write at most")

    assert "core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY" in quota.because
    assert "core.agentic_v2_microvm" in quota.because
    assert "it applies nothing" in quota.because


# ── Each requirement, taken away one at a time ────────────────────────────


def test_a_processor_that_cannot_do_it_is_a_permanent_no():
    answer = judge_containment(a_machine(processor_flags=("fpu", "aes")))
    judged = claim(answer, NEEDS_A_PROCESSOR_THAT_CAN)

    assert answer.machine_could_host_it is False
    assert judged.met is False
    assert "no amount of configuration would make this work here" in judged.because


def test_a_processor_whose_capabilities_could_not_be_read_is_not_called_a_no():
    """An unread fact and a fact that came back negative are different answers.

    Reporting "the processor cannot do it" when the truth is "nobody managed to
    look" would send somebody to buy hardware they may already own.
    """
    answer = judge_containment(
        a_machine(processor_flags=(), processor_flags_were_readable=False)
    )
    judged = claim(answer, NEEDS_A_PROCESSOR_THAT_CAN)

    assert judged.met is None
    assert judged.verdict == "cannot be established here"
    assert answer.machine_could_host_it is False


def test_an_amd_processor_counts_as_well_as_an_intel_one():
    answer = judge_containment(a_machine(processor_flags=("fpu", "svm")))

    assert claim(answer, NEEDS_A_PROCESSOR_THAT_CAN).met is True


def test_hardware_the_machine_cannot_reach_is_a_no():
    answer = judge_containment(a_machine(hardware_virtualisation_reachable=False))
    judged = claim(answer, NEEDS_TO_REACH_THE_HARDWARE)

    assert answer.machine_could_host_it is False
    assert judged.met is False
    assert "core.agentic_v2_microvm.inspect_microvm_readiness" in judged.because


def test_the_programs_being_absent_names_which_ones():
    answer = judge_containment(
        a_machine(
            firecracker_programs_found=("firecracker",),
            firecracker_programs_missing=("jailer",),
        )
    )
    judged = claim(answer, NEEDS_THE_PROGRAMS_INSTALLED)

    assert judged.met is False
    assert "jailer" in judged.because


def test_not_having_looked_for_the_programs_is_not_the_same_as_their_being_absent():
    answer = judge_containment(
        a_machine(firecracker_programs_found=(), firecracker_programs_missing=())
    )
    judged = claim(answer, NEEDS_THE_PROGRAMS_INSTALLED)

    assert judged.met is None
    assert "unknown" in judged.because


# ── The kernel, which is the reading the existing report never took ───────


@pytest.mark.parametrize(
    "release",
    ["5.10", "5.10.0-generic", "5.15.0-91-generic", "6.1.0", "6.18.2-aws"],
)
def test_a_kernel_at_or_above_what_firecracker_validates_is_accepted(release):
    answer = judge_containment(a_machine(kernel_release=release))

    assert claim(answer, NEEDS_A_KERNEL_FIRECRACKER_TESTS).met is True


@pytest.mark.parametrize("release", ["3.10.102", "4.14.0", "4.19.2", "5.9.16"])
def test_a_kernel_below_what_firecracker_validates_is_refused(release):
    answer = judge_containment(a_machine(kernel_release=release))
    judged = claim(answer, NEEDS_A_KERNEL_FIRECRACKER_TESTS)

    assert answer.machine_could_host_it is False
    assert judged.met is False
    assert release in judged.because


def test_the_kernel_requirement_says_where_it_came_from_and_does_not_overstate_it():
    """Firecracker does not forbid an older kernel, and neither does this.

    Its kernel policy says untabled versions "might work" but are not validated
    in its test suite. Reporting that as a prohibition would be a different
    claim from the one the source makes, so the reason says which it is.
    """
    answer = judge_containment(a_machine(kernel_release="4.19.2"))
    judged = claim(answer, NEEDS_A_KERNEL_FIRECRACKER_TESTS)

    assert FIRECRACKER_KERNEL_POLICY_URL in judged.because
    assert "does not forbid" in judged.because
    assert "not validated in its test suite" in judged.because


def test_a_kernel_that_reports_no_version_number_is_an_unknown_not_a_no():
    answer = judge_containment(a_machine(kernel_release="unknown"))
    judged = claim(answer, NEEDS_A_KERNEL_FIRECRACKER_TESTS)

    assert judged.met is None
    assert "'unknown'" in judged.because


def test_the_kernel_floor_is_the_one_firecracker_publishes():
    assert OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES == (5, 10)


# ── What the report says when it cannot answer ────────────────────────────


def test_a_claim_that_could_not_be_established_counts_against_availability():
    """The rule the container run place already follows, applied here.

    When the intended isolation cannot be shown to be present, the answer is
    no. Treating "could not tell" as "probably fine" is how a task ends up
    running somewhere weaker than anybody agreed to.
    """
    answer = judge_containment(a_machine(kernel_release="unknown"))

    assert answer.machine_could_host_it is False
    assert answer.required_containment_available is False


def test_the_settings_say_both_reasons_while_no_virtual_machine_can_start():
    """Two things are wrong at once here, and the report says both.

    There is no machine to apply the rule to, *and* nothing that would apply it
    if there were. Naming only the first would send a reader to find a machine
    and leave them surprised when the rule still went unapplied on it.
    """
    answer = judge_containment(a_machine(hardware_virtualisation_reachable=False))
    rootfs = claim(answer, "the small isolated virtual machine's root filesystem")

    assert rootfs.met is None
    assert "no small isolated virtual machine on this machine" in rootfs.because
    assert NOTHING_APPLIES_THESE_RULES_YET in rootfs.because


def test_whats_missing_lists_only_what_is_wrong_and_why():
    answer = judge_containment(
        a_machine(
            kernel_release="3.10.102",
            hardware_virtualisation_reachable=False,
            firecracker_programs_found=(),
            firecracker_programs_missing=("firecracker", "jailer"),
        )
    )
    missing = answer.whats_missing()

    assert any("3.10.102" in line for line in missing)
    assert any("firecracker, jailer" in line for line in missing)
    assert not any(NEEDS_A_PROCESSOR_THAT_CAN in line for line in missing)
    assert all(" — " in line and ": " in line for line in missing)


def test_an_answer_with_no_requirements_in_it_is_not_treated_as_available():
    """An empty report is the absence of evidence, not evidence of readiness."""
    from core.agentic_v2_containment_readiness import ContainmentAnswer

    empty = ContainmentAnswer(machine="nowhere")

    assert empty.machine_could_host_it is False
    assert empty.required_containment_available is False


# ── The manifest is read, not copied ──────────────────────────────────────


def test_a_new_setting_in_the_manifest_is_reported_rather_than_ignored(monkeypatch):
    """The drift guard. A requirement nobody checks is worse than none at all.

    If the manifest starts demanding something this report does not understand,
    the honest output is to say so. The alternative — quietly reporting on the
    settings it happens to know about — would let the answer stay green while
    the requirement it answers about had changed underneath it.

    The setting below is invented for this test and deliberately unlike any real
    one, so that adding it here can never be mistaken for adding it to the
    manifest.
    """
    monkeypatch.setitem(
        REQUIRED_MICROVM_POLICY, "there_is_no_such_rule", "invented-for-a-test"
    )
    try:
        answer = judge_containment(a_machine())
    finally:
        REQUIRED_MICROVM_POLICY.pop("there_is_no_such_rule", None)

    unknown = claim(
        answer, "the manifest's containment setting 'there_is_no_such_rule'"
    )
    assert unknown.met is None
    assert "does not know how to describe or check" in unknown.because
    assert answer.required_containment_available is False


def test_the_report_says_containment_is_mandatory_and_reads_that_from_the_manifest():
    answer = judge_containment(a_machine())
    premise = claim(answer, "containment is mandatory")

    assert premise.met is True
    assert "REQUIRED_MICROVM_POLICY" in premise.because


def test_a_manifest_that_stopped_requiring_containment_would_show_up(monkeypatch):
    monkeypatch.setitem(REQUIRED_MICROVM_POLICY, "required", False)
    try:
        answer = judge_containment(a_machine())
    finally:
        REQUIRED_MICROVM_POLICY["required"] = True

    assert claim(answer, "containment is mandatory").met is False
    assert any("containment is mandatory" in line for line in answer.whats_missing())


def test_the_premise_is_stated_before_the_details_of_it():
    answer = judge_containment(a_machine())
    claims = [item.claim for item in answer.requirements]
    premise = next(
        index for index, item in enumerate(claims)
        if item.startswith("containment is mandatory")
    )
    detail = next(
        index for index, item in enumerate(claims) if "root filesystem" in item
    )

    assert premise < detail


def test_nothing_was_added_above_the_frozen_function_in_the_substrate_module():
    """A trap this change walked into, left pinned so nobody walks into it twice.

    core/agentic_v2_license.py freezes the exact bytecode identity of
    core.agentic_v2_substrate.canonical_sha256, and that identity includes the
    line the function starts on. A single blank line added anywhere above it
    breaks ninety-one licence tests, none of which mention the substrate module
    in their failure message. Reading REQUIRED_MICROVM_POLICY from that module
    meant putting a constant in it, which is exactly how one arrives here.

    This test fails on its own, with a message that names the cause.
    """
    from core.agentic_v2_license import license_evaluator_runtime_identity
    from core.agentic_v2_substrate import canonical_sha256

    try:
        license_evaluator_runtime_identity()
    except RuntimeError as error:
        pytest.fail(
            "the licence evaluator no longer recognises its own frozen "
            "identity. If core/agentic_v2_substrate.py was edited, check "
            "whether a line was added above canonical_sha256, which now starts "
            f"on line {canonical_sha256.__code__.co_firstlineno}. Its starting "
            "line is part of the frozen identity, so moving it down by even "
            "one blank line breaks every licence report. New constants in that "
            f"module go below it, not above. Underlying error: {error}"
        )


# ── Reading a machine ─────────────────────────────────────────────────────


def test_reading_a_machine_takes_the_program_and_hardware_facts_from_one_place():
    """Two ways of reading one fact is how two answers start to disagree."""
    facts = read_this_machine(
        kernel_release="6.1.0",
        microvm_report=a_microvm_report(kvm=True, programs=("firecracker",)),
    )

    assert facts.hardware_virtualisation_reachable is True
    assert facts.firecracker_programs_found == ("firecracker",)
    assert facts.firecracker_programs_missing == ("jailer",)


def test_reading_a_machine_finds_the_processor_capabilities(tmp_path):
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text(
        "processor\t: 0\nvendor_id\t: AuthenticAMD\nflags\t\t: fpu vme svm aes\n",
        encoding="utf-8",
    )
    facts = read_this_machine(
        cpuinfo_path=cpuinfo,
        docker_marker_path=tmp_path / "absent",
        cgroup_path=tmp_path / "absent",
        kernel_release="6.1.0",
        microvm_report=a_microvm_report(),
    )

    assert facts.processor_flags_were_readable is True
    assert "svm" in facts.processor_flags


def test_a_processor_capability_list_that_cannot_be_read_is_reported_as_such(tmp_path):
    facts = read_this_machine(
        cpuinfo_path=tmp_path / "there-is-no-such-file",
        docker_marker_path=tmp_path / "absent",
        cgroup_path=tmp_path / "absent",
        kernel_release="6.1.0",
        microvm_report=a_microvm_report(),
    )

    assert facts.processor_flags_were_readable is False
    assert facts.processor_flags == ()


def test_a_processor_capability_list_written_the_other_way_round_is_read(tmp_path):
    """Some machines label the same list Features rather than flags."""
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("Features\t: fp asimd vmx\n", encoding="utf-8")
    facts = read_this_machine(
        cpuinfo_path=cpuinfo,
        docker_marker_path=tmp_path / "absent",
        cgroup_path=tmp_path / "absent",
        kernel_release="6.1.0",
        microvm_report=a_microvm_report(),
    )

    assert "vmx" in facts.processor_flags


def test_being_inside_a_container_is_noticed_from_the_marker_file(tmp_path):
    marker = tmp_path / ".dockerenv"
    marker.write_text("", encoding="utf-8")
    facts = read_this_machine(
        cpuinfo_path=tmp_path / "absent",
        docker_marker_path=marker,
        cgroup_path=tmp_path / "absent",
        kernel_release="6.1.0",
        microvm_report=a_microvm_report(),
    )

    assert facts.inside_a_container is True
    assert str(marker) in facts.container_evidence


def test_being_inside_a_container_is_noticed_from_the_process_groups(tmp_path):
    cgroup = tmp_path / "cgroup"
    cgroup.write_text("7:memory:/docker/f1e2da85\n", encoding="utf-8")
    facts = read_this_machine(
        cpuinfo_path=tmp_path / "absent",
        docker_marker_path=tmp_path / "absent",
        cgroup_path=cgroup,
        kernel_release="6.1.0",
        microvm_report=a_microvm_report(),
    )

    assert facts.inside_a_container is True
    assert "/docker/" in facts.container_evidence


def test_a_machine_that_is_not_in_a_container_says_so(tmp_path):
    cgroup = tmp_path / "cgroup"
    cgroup.write_text("0::/init.scope\n", encoding="utf-8")
    facts = read_this_machine(
        cpuinfo_path=tmp_path / "absent",
        docker_marker_path=tmp_path / "absent",
        cgroup_path=cgroup,
        kernel_release="6.1.0",
        microvm_report=a_microvm_report(),
    )

    assert facts.inside_a_container is False
    assert facts.container_evidence == ""


def test_being_inside_a_container_is_explained_rather_than_held_against_the_machine():
    """Firecracker can run inside a container. The note must not say otherwise.

    Being in a container explains why the hardware is out of reach here; it is
    not itself a reason the containment could never work.
    """
    answer = judge_containment(
        a_machine(
            hardware_virtualisation_reachable=False,
            inside_a_container=True,
            container_evidence="/.dockerenv exists",
        )
    )

    assert any("not disqualifying by itself" in note for note in answer.notes)
    assert not any(item.claim.startswith("this is not a container") for item in answer.requirements)


# ── This machine, read for real ───────────────────────────────────────────


def test_reading_this_machine_costs_nothing_and_answers():
    """The live reading. It opens files this process may already open."""
    facts = read_this_machine()
    answer = judge_containment(facts)

    assert isinstance(facts.kernel_release, str) and facts.kernel_release
    assert [item.claim for item in answer.requirements]
    assert isinstance(answer.machine_could_host_it, bool)
    assert isinstance(answer.required_containment_available, bool)


def test_the_check_never_runs_a_command_to_find_any_of_this_out():
    """Reading a machine must not become running things on it.

    A readiness check that shells out is a readiness check that can have side
    effects, and this one is meant to be safe to run anywhere, including on a
    machine where running things is exactly what is not allowed.
    """
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "agentic_v2_containment_readiness.py"
    ).read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess." not in source
    assert "os.system" not in source


# ── The machines that cannot be read from here ────────────────────────────


def test_every_recorded_finding_says_where_it_came_from_and_when():
    assert RECORDED_FINDINGS
    for finding in RECORDED_FINDINGS:
        assert finding.machine
        assert finding.established_by
        assert finding.on_date == "2026-08-26"
        assert len(finding.finding) > 80, "a finding with no reasoning in it"


def test_no_recorded_finding_claims_the_containment_is_available():
    """The answer as it stands. This test changes on the day the answer does."""
    assert all(
        finding.could_host_the_containment is not True
        for finding in RECORDED_FINDINGS
    )


def test_the_github_runner_finding_rests_on_githubs_own_documentation():
    github = next(
        finding for finding in RECORDED_FINDINGS if "github-hosted" in finding.machine
    )

    assert github.could_host_the_containment is False
    assert "docs.github.com" in github.established_by
    assert "not officially supported" in github.finding


def test_the_self_hosted_machine_is_an_unknown_because_it_does_not_exist():
    """A machine nobody has registered has no containment answer either way.

    Recording this as "not available" would be wrong in a way that matters: it
    would read as though somebody had looked at a machine and found it wanting,
    when the truth is that the machine has never been built.
    """
    self_hosted = next(
        finding for finding in RECORDED_FINDINGS if "self-hosted" in finding.machine
    )

    assert self_hosted.could_host_the_containment is None
    assert "there is no such machine" in self_hosted.finding
    assert "total_count 0" in self_hosted.established_by


# ── Which machines the workflows actually ask for ─────────────────────────


def test_the_machines_the_workflows_ask_for_are_read_from_the_workflow_files(tmp_path):
    (tmp_path / "one.yml").write_text(
        "jobs:\n  build:\n    runs-on: ubuntu-latest\n", encoding="utf-8"
    )
    (tmp_path / "two.yaml").write_text(
        "jobs:\n  test:\n    runs-on: [self-hosted, linux, x64, agentic-sandbox]\n",
        encoding="utf-8",
    )

    assert runner_labels_used_by_workflows(tmp_path) == (
        "agentic-sandbox",
        "ubuntu-latest",
    )


def test_a_machine_chosen_while_the_workflow_runs_is_not_guessed_at(tmp_path):
    (tmp_path / "one.yml").write_text(
        "jobs:\n  build:\n    runs-on: ${{ inputs.runner }}\n", encoding="utf-8"
    )

    assert runner_labels_used_by_workflows(tmp_path) == ()


def test_a_workflow_running_somewhere_new_is_reported_as_a_gap(tmp_path):
    (tmp_path / "one.yml").write_text(
        "jobs:\n  build:\n    runs-on: macos-14\n", encoding="utf-8"
    )
    problems = check_every_machine_has_a_containment_finding(tmp_path)

    assert len(problems) == 1
    assert "macos-14" in problems[0]
    assert "Establish it before that machine is counted" in problems[0]


def test_every_machine_this_repository_uses_today_has_an_answer_recorded():
    """The live guard against the answer going stale.

    This reads the real workflow files. Adding one that runs somewhere new
    fails here rather than letting the new machine quietly inherit a finding
    that was established about a different one.
    """
    assert check_every_machine_has_a_containment_finding(WORKFLOWS_DIRECTORY) == []


# ── The whole answer, and the refusal that follows ────────────────────────


def test_the_whole_answer_covers_this_machine_and_the_recorded_ones():
    report = containment_answer_everywhere(
        facts=a_machine(hardware_virtualisation_reachable=False),
        workflows_directory=WORKFLOWS_DIRECTORY,
    )

    assert report["required_containment"] == dict(REQUIRED_MICROVM_POLICY)
    assert report["this_machine"]["machine_could_host_it"] is False
    assert report["this_machine"]["required_containment_available"] is False
    assert len(report["recorded_findings"]) == len(RECORDED_FINDINGS)
    assert report["machines_without_a_finding"] == []
    assert report["could_be_hosted_on_any_machine_in_play"] is False
    assert report["available_on_any_machine_in_play"] is False


def test_the_whole_answer_can_be_written_down_as_it_stands():
    report = containment_answer_everywhere(workflows_directory=WORKFLOWS_DIRECTORY)

    assert json.loads(json.dumps(report)) == report


def test_a_machine_here_that_could_do_it_changes_one_answer_and_not_the_other():
    """The distinction the whole report now turns on.

    A machine that has everything moves the hosting question and nothing else.
    The containment still is not in place, because no code applies its rules,
    and the refusal must stay standing on that second ground rather than lifting
    because the first was cleared.
    """
    report = containment_answer_everywhere(facts=a_machine())

    assert report["could_be_hosted_on_any_machine_in_play"] is True
    assert report["anything_applies_the_containment_rules"] is False
    assert report["available_on_any_machine_in_play"] is False
    assert refuse_command_execution(report) is not None


def test_the_refusal_on_a_capable_machine_names_the_rules_nobody_applies():
    """Two grounds for refusing, and the sentence says which one it is on.

    Repeating "no machine can host it" to somebody standing in front of a
    machine that can would read as a bug in the report rather than as the real
    remaining gap.
    """
    refusal = refuse_command_execution(containment_answer_everywhere(facts=a_machine()))

    assert refusal is not None
    assert "could be started on a machine in play" in refusal
    assert NOTHING_APPLIES_THESE_RULES_YET in refusal
    assert "is not available on any machine in play" not in refusal


def test_an_unanswered_machine_is_reported_beside_the_answer_not_folded_into_it(
    tmp_path,
):
    """A gap and a no are different things, and the report keeps them apart.

    ``scripts/check_agentic_containment.py`` passes only when both hold, so a
    workflow that starts running somewhere nobody has answered for fails the
    check even on a machine that could itself host the containment. The two
    are separate keys rather than one, because folding them together would
    report an unanswered machine as though it had been answered no.
    """
    (tmp_path / "somewhere-new.yml").write_text(
        "jobs:\n  build:\n    runs-on: macos-15\n", encoding="utf-8"
    )

    report = containment_answer_everywhere(
        facts=a_machine(), workflows_directory=tmp_path
    )

    assert report["could_be_hosted_on_any_machine_in_play"] is True
    assert report["every_machine_in_play_has_an_answer"] is False
    assert len(report["machines_without_a_finding"]) == 1
    assert "macos-15" in report["machines_without_a_finding"][0]


def test_every_machine_this_repository_uses_today_is_answered_in_the_report():
    report = containment_answer_everywhere(
        facts=a_machine(), workflows_directory=WORKFLOWS_DIRECTORY
    )

    assert report["every_machine_in_play_has_an_answer"] is True


def test_not_looking_at_the_workflows_is_reported_as_not_looked_not_as_yes():
    """The distinction the script's exit code depends on.

    With no workflows directory, nothing inspected which machines are in play.
    Saying "every machine has an answer" then would be a claim nobody checked,
    and it is exactly the sort of unasked question this module refuses to let
    pass as a cleared one.
    """
    report = containment_answer_everywhere(facts=a_machine())

    assert report["every_machine_in_play_has_an_answer"] is None
    assert report["machines_without_a_finding"] == []


def test_commands_a_model_chose_are_refused_today_and_the_reason_is_the_containment():
    report = containment_answer_everywhere(
        facts=a_machine(hardware_virtualisation_reachable=False)
    )
    refusal = refuse_command_execution(report)

    assert refusal is not None
    assert "must not run" in refusal
    assert REQUIRED_MICROVM_POLICY["runtime"] in refusal
    assert "the substitution the specification forbids" in refusal


def test_the_refusal_reads_this_machine_when_it_is_given_nothing():
    refusal = refuse_command_execution()

    assert refusal is not None, (
        "this machine cannot provide the containment, so the refusal must stand"
    )


def test_answering_the_containment_question_opens_none_of_the_three_blocks():
    """The point of instruction six, checked rather than promised.

    Establishing that containment is unavailable is not permission to run
    anything, and it must not have loosened the refusals that were already
    holding command execution shut. Those three are run, not read.
    """
    from core.execution_environment_readiness import (
        check_agentic_sandbox_v2_blocks_are_intact,
    )

    assert check_agentic_sandbox_v2_blocks_are_intact() == []


# ── The printed report ────────────────────────────────────────────────────


def test_the_printed_report_states_the_requirement_the_verdict_and_the_sources():
    report = containment_answer_everywhere(
        facts=a_machine(kernel_release="3.10.102", hardware_virtualisation_reachable=False),
        workflows_directory=WORKFLOWS_DIRECTORY,
    )
    printed = "\n".join(describe_containment(report))

    assert "What the substrate manifest requires" in printed
    assert "runtime: firecracker" in printed
    assert "3.10.102" in printed
    assert "docs.github.com" in printed
    assert "there is no such machine" in printed
    assert "must not run" in printed


def test_the_printed_report_says_which_rules_nobody_applies():
    report = containment_answer_everywhere(facts=a_machine())
    printed = "\n".join(describe_containment(report))

    assert "Whether anything applies the rules, on any machine" in printed
    assert "Nothing does:" in printed
    assert "a fact about this repository rather than about any machine" in printed
    assert "The required containment is available" not in printed


def test_the_printed_report_shows_a_machine_nobody_has_an_answer_for(tmp_path):
    (tmp_path / "one.yml").write_text(
        "jobs:\n  build:\n    runs-on: windows-2022\n", encoding="utf-8"
    )
    report = containment_answer_everywhere(
        facts=a_machine(hardware_virtualisation_reachable=False),
        workflows_directory=tmp_path,
    )
    printed = "\n".join(describe_containment(report))

    assert "Gap: a workflow now runs on 'windows-2022'" in printed


def test_the_printed_report_uses_no_symbols_or_shorthand():
    """It is read by somebody deciding whether to build a machine, not by a tool."""
    report = containment_answer_everywhere(workflows_directory=WORKFLOWS_DIRECTORY)

    for line in describe_containment(report):
        assert "✓" not in line and "✗" not in line and "❌" not in line
        assert "N/A" not in line and "TBD" not in line
