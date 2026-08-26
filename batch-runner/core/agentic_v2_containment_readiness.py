"""Whether the containment Agentic Sandbox V2 requires exists on any machine here.

The specification for Agentic Sandbox V2 has carried one open question since it
was written: the substrate manifest insists that commands run inside a small
isolated virtual machine, and nobody had established whether such a thing is
available on the machines this repository actually runs on. Stage three — the
stage that lets a model's chosen commands really run — cannot be designed while
that is unknown, because the containment is the whole of its safety.

This module answers that question, and answers it by reading the machine rather
than by asserting something in prose. Nothing here calls a model, signs in to an
account, runs a command, installs anything, or spends money. Every reading is a
file this process may already open or a lookup on the program search path.

**A readiness report already existed and was not enough.**
:func:`core.agentic_v2_microvm.inspect_microvm_readiness` checks four things:
the two Firecracker programs, ``/dev/kvm``, and whether a kernel image and a
root filesystem image were handed to it. Those facts are reused here rather than
read a second time. But two readings decide the answer on every real machine and
that report takes neither of them:

* **the version of the kernel this machine is running**, which is what rules out
  an older host outright, and
* **whether the processor offers hardware virtualisation at all**, which is what
  separates "this machine could do it once configured" from "this machine never
  can".

It also reports only ``ready_for_boot_test`` or ``not_run``, which tells a reader
that something is missing without telling them what or whether it is fixable.

**Three machines are in play, and only one can be read from here.** The other
two are recorded in :data:`RECORDED_FINDINGS` with the source and the date they
were established, kept deliberately separate from anything probed, so a reader
is never left guessing which kind of evidence they are looking at.
"""

from __future__ import annotations

import platform
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from core.agentic_v2_microvm import inspect_microvm_readiness
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY

# ── What Firecracker itself says it needs ─────────────────────────────────

OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES = (5, 10)
"""The oldest host kernel Firecracker's own kernel policy lists.

Read on 2026-08-26 from Firecracker's ``docs/kernel-policy.md``, which gives
v5.10, v6.1 and v6.18 as the host kernels it validates against and says of
anything else that it "might work" but is "not periodically validated in our
test suite".

That wording matters for how this is used below. A kernel older than this is not
reported as *forbidden*, because Firecracker does not forbid it; it is reported
as *outside what its own project tests*, which for a containment boundary is
reason enough not to rely on it. The distinction is kept because overstating a
requirement is its own kind of wrong answer.
"""

FIRECRACKER_KERNEL_POLICY_URL = (
    "https://github.com/firecracker-microvm/firecracker/blob/main/docs/"
    "kernel-policy.md"
)

PROCESSOR_VIRTUALISATION_FLAGS = ("vmx", "svm")
"""The processor flags that mean hardware virtualisation exists — Intel, AMD."""


# ── The four readings that can be taken here ──────────────────────────────
#
# Written as statements that are either true or false about a machine, so a
# report reads as a list of plain claims rather than a list of setting names.

NEEDS_A_PROCESSOR_THAT_CAN = "the processor offers hardware virtualisation"
NEEDS_TO_REACH_THE_HARDWARE = "this machine can reach hardware virtualisation"
NEEDS_A_KERNEL_FIRECRACKER_TESTS = (
    "the kernel is one Firecracker validates against"
)
NEEDS_THE_PROGRAMS_INSTALLED = "the Firecracker programs are installed"

READINGS_TAKEN_HERE = (
    NEEDS_A_PROCESSOR_THAT_CAN,
    NEEDS_TO_REACH_THE_HARDWARE,
    NEEDS_A_KERNEL_FIRECRACKER_TESTS,
    NEEDS_THE_PROGRAMS_INSTALLED,
)

# How each setting in the manifest's containment policy reads as a claim about a
# running virtual machine. These cannot be checked without one, and saying so is
# the honest report; quietly leaving them out would read as though the manifest
# asked for less than it does.
_POLICY_SETTING_AS_A_CLAIM = {
    "runtime": "the small isolated virtual machine is run by {value}",
    "network": "the small isolated virtual machine's network is {value}",
    "rootfs": "the small isolated virtual machine's root filesystem is {value}",
    "workdir": "the small isolated virtual machine's working directory is "
    "{value}",
    "workdir_quota_mib": "the command may write at most {value} mebibytes",
    "memory_mib": "the command is given at most {value} mebibytes of memory",
    "wall_clock_seconds": "the command is stopped after {value} seconds",
    "user": "the command runs as {value} rather than as a privileged user",
    "on_breach": "exceeding any rule above results in {value}",
}

# What has to exist before any of the settings above can be reported as met.
#
# Nothing in this repository turns a containment rule into an argument for
# starting a virtual machine. core/agentic_v2_microvm.py looks for the
# Firecracker programs on the search path and stops there; no module reads
# REQUIRED_MICROVM_POLICY and produces a start-up configuration from it.
#
# This matters more than it sounds. Until 2026-08-26 this report marked every
# one of those settings as met the moment a machine could start a virtual
# machine at all — as though being able to start one meant the rules had been
# applied to it. On the three machines in play that never showed, because none
# of them can start one. On the first machine that could, the report would have
# said the containment was in place while nothing carried it there.
#
# A rule nobody applies is not met. It is unenforced, which is a different
# answer, and the report now gives that one.
NOTHING_APPLIES_THESE_RULES_YET = (
    "no module turns core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY into "
    "arguments for starting a virtual machine, so this rule is written down "
    "and unenforced rather than met. core.agentic_v2_microvm only looks for "
    "the Firecracker programs; it applies nothing"
)


@dataclass(frozen=True)
class MachineFacts:
    """What was read off one machine. Nothing here is a judgement."""

    kernel_release: str
    processor_flags: tuple[str, ...]
    processor_flags_were_readable: bool
    hardware_virtualisation_reachable: bool
    firecracker_programs_found: tuple[str, ...]
    firecracker_programs_missing: tuple[str, ...]
    inside_a_container: bool
    container_evidence: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "kernel_release": self.kernel_release,
            "processor_flags": list(self.processor_flags),
            "processor_flags_were_readable": self.processor_flags_were_readable,
            "hardware_virtualisation_reachable": (
                self.hardware_virtualisation_reachable
            ),
            "firecracker_programs_found": list(self.firecracker_programs_found),
            "firecracker_programs_missing": list(
                self.firecracker_programs_missing
            ),
            "inside_a_container": self.inside_a_container,
            "container_evidence": self.container_evidence,
        }


@dataclass(frozen=True)
class Requirement:
    """One claim about containment, judged, with what was read beside it."""

    claim: str
    met: bool | None
    """``True`` yes, ``False`` no, ``None`` it could not be established here."""

    because: str

    @property
    def verdict(self) -> str:
        if self.met is True:
            return "met"
        if self.met is False:
            return "not met"
        return "cannot be established here"

    def as_dict(self) -> dict[str, Any]:
        return {"claim": self.claim, "verdict": self.verdict, "because": self.because}


@dataclass(frozen=True)
class RecordedFinding:
    """An answer for a machine that cannot be read from this one.

    What is recorded is whether the machine *could host* the containment, which
    is the only one of the two questions below anybody has established about
    these machines. Whether the rules would then be applied to it is not a
    property of a machine at all — it is a property of this repository, and the
    answer is the same everywhere.
    """

    machine: str
    could_host_the_containment: bool | None
    finding: str
    established_by: str
    on_date: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "machine": self.machine,
            "could_host_the_containment": self.could_host_the_containment,
            "finding": self.finding,
            "established_by": self.established_by,
            "on_date": self.on_date,
        }


@dataclass
class ContainmentAnswer:
    """What one machine can and cannot provide, and what follows from it."""

    machine: str
    requirements: list[Requirement] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def machine_could_host_it(self) -> bool:
        """True when the four readings taken on this machine all hold.

        Not the same question as :attr:`required_containment_available`, and
        until 2026-08-26 they were one field, which is how a rule nothing
        applies came to be reported as met. This one asks whether the machine
        could start a small isolated virtual machine at all. That one asks
        whether the containment is actually in place.

        They are kept apart because they are fixed by different things. This one
        is fixed by finding, configuring or building a machine. That one is
        additionally fixed by writing the code that turns the containment rules
        into arguments for starting the machine — which nobody has written.
        """
        taken_here = [
            requirement
            for requirement in self.requirements
            if requirement.claim in READINGS_TAKEN_HERE
        ]
        return len(taken_here) == len(READINGS_TAKEN_HERE) and all(
            requirement.met is True for requirement in taken_here
        )

    @property
    def required_containment_available(self) -> bool:
        """True only when every claim was established and every one holds.

        A claim that could not be established counts against availability. The
        rule the specification already sets for the container run place applies
        here too: when the intended isolation cannot be shown to be present, the
        answer is no, not "probably".

        This is false on every machine today, including one that has everything,
        and it stays false until two separate things change: some machine has to
        be able to host the containment, and something has to apply the rules to
        it. See :data:`NOTHING_APPLIES_THESE_RULES_YET` for the second.
        """
        return bool(self.requirements) and all(
            requirement.met is True for requirement in self.requirements
        )

    def whats_missing(self) -> list[str]:
        """Every claim that does not hold, said as a sentence with its reason."""
        return [
            f"{requirement.claim} — {requirement.verdict}: {requirement.because}"
            for requirement in self.requirements
            if requirement.met is not True
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            "machine": self.machine,
            "machine_could_host_it": self.machine_could_host_it,
            "required_containment_available": self.required_containment_available,
            "requirements": [item.as_dict() for item in self.requirements],
            "whats_missing": self.whats_missing(),
            "notes": list(self.notes),
        }


# ── Reading one machine ───────────────────────────────────────────────────


def read_this_machine(
    *,
    cpuinfo_path: str | Path = "/proc/cpuinfo",
    docker_marker_path: str | Path = "/.dockerenv",
    cgroup_path: str | Path = "/proc/1/cgroup",
    kernel_release: str | None = None,
    microvm_report: Mapping[str, Any] | None = None,
) -> MachineFacts:
    """Read the machine this process is on. Free, read-only, and offline.

    The Firecracker programs and the hardware-virtualisation device are not read
    again here: :func:`core.agentic_v2_microvm.inspect_microvm_readiness`
    already does that, and reading them a second way is how two answers to one
    question start to disagree. Pass ``microvm_report`` to supply that reading
    instead of taking it, which is what the tests do.
    """
    report = (
        inspect_microvm_readiness(asset_paths={})
        if microvm_report is None
        else microvm_report
    )
    tools = report.get("tools", {})
    found = tuple(
        sorted(
            name
            for name, item in tools.items()
            if isinstance(item, Mapping) and item.get("status") == "present"
        )
    )
    missing = tuple(sorted(set(tools) - set(found)))

    flags, flags_readable = _read_processor_flags(Path(cpuinfo_path))
    inside, evidence = _read_container_markers(
        Path(docker_marker_path), Path(cgroup_path)
    )
    return MachineFacts(
        kernel_release=(
            platform.release() if kernel_release is None else kernel_release
        ),
        processor_flags=flags,
        processor_flags_were_readable=flags_readable,
        hardware_virtualisation_reachable=bool(
            report.get("checks", {}).get("kvm")
        ),
        firecracker_programs_found=found,
        firecracker_programs_missing=missing,
        inside_a_container=inside,
        container_evidence=evidence,
    )


def _read_processor_flags(cpuinfo_path: Path) -> tuple[tuple[str, ...], bool]:
    try:
        text = cpuinfo_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return (), False
    for line in text.splitlines():
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() in {"flags", "features"}:
            return tuple(value.split()), True
    return (), False


def _read_container_markers(
    docker_marker_path: Path, cgroup_path: Path
) -> tuple[bool, str]:
    if docker_marker_path.exists():
        return True, f"{docker_marker_path} exists"
    try:
        text = cgroup_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, ""
    for marker in ("/docker/", "/kubepods", "/lxc/", "/containerd"):
        if marker in text:
            return True, f"{cgroup_path} mentions {marker}"
    return False, ""


# ── Judging what was read ─────────────────────────────────────────────────


def judge_containment(
    facts: MachineFacts, *, machine: str = "this machine"
) -> ContainmentAnswer:
    """Turn readings into claims that hold or do not, each with its reason."""
    answer = ContainmentAnswer(machine=machine)

    answer.requirements.append(_judge_processor(facts))
    answer.requirements.append(_judge_reach(facts))
    answer.requirements.append(_judge_kernel(facts))
    answer.requirements.append(_judge_programs(facts))
    answer.requirements.extend(_judge_policy_settings(answer.requirements))

    if facts.inside_a_container:
        answer.notes.append(
            "this is running inside a container "
            f"({facts.container_evidence}), which is why the hardware "
            "virtualisation device is not reachable. That is not disqualifying "
            "by itself — Firecracker can run inside a container when the "
            "device is passed through to it — but nothing here passes it "
            "through, and the machine outside would still have to meet the "
            "other claims"
        )
    return answer


def _judge_processor(facts: MachineFacts) -> Requirement:
    if not facts.processor_flags_were_readable:
        return Requirement(
            claim=NEEDS_A_PROCESSOR_THAT_CAN,
            met=None,
            because=(
                "the processor's capability list could not be read on this "
                "machine, so whether the hardware can do it at all is unknown"
            ),
        )
    present = sorted(
        set(facts.processor_flags) & set(PROCESSOR_VIRTUALISATION_FLAGS)
    )
    if present:
        return Requirement(
            claim=NEEDS_A_PROCESSOR_THAT_CAN,
            met=True,
            because=(
                "the processor reports "
                + ", ".join(present)
                + ", so the hardware itself can do it"
            ),
        )
    return Requirement(
        claim=NEEDS_A_PROCESSOR_THAT_CAN,
        met=False,
        because=(
            "the processor reports neither "
            + " nor ".join(PROCESSOR_VIRTUALISATION_FLAGS)
            + ", so no amount of configuration would make this work here"
        ),
    )


def _judge_reach(facts: MachineFacts) -> Requirement:
    if facts.hardware_virtualisation_reachable:
        return Requirement(
            claim=NEEDS_TO_REACH_THE_HARDWARE,
            met=True,
            because=(
                "core.agentic_v2_microvm.inspect_microvm_readiness found the "
                "hardware virtualisation device present and usable by this user"
            ),
        )
    return Requirement(
        claim=NEEDS_TO_REACH_THE_HARDWARE,
        met=False,
        because=(
            "core.agentic_v2_microvm.inspect_microvm_readiness found no usable "
            "hardware virtualisation device, so nothing here can start a small "
            "isolated virtual machine even if everything else were in place"
        ),
    )


def _judge_kernel(facts: MachineFacts) -> Requirement:
    version = _kernel_version(facts.kernel_release)
    oldest = ".".join(str(part) for part in OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES)
    if version is None:
        return Requirement(
            claim=NEEDS_A_KERNEL_FIRECRACKER_TESTS,
            met=None,
            because=(
                f"the kernel reports itself as {facts.kernel_release!r}, which "
                "this check could not read a version number out of"
            ),
        )
    if version >= OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES:
        return Requirement(
            claim=NEEDS_A_KERNEL_FIRECRACKER_TESTS,
            met=True,
            because=(
                f"the kernel is {facts.kernel_release}, at or above the {oldest} "
                f"that Firecracker's own kernel policy lists "
                f"({FIRECRACKER_KERNEL_POLICY_URL})"
            ),
        )
    return Requirement(
        claim=NEEDS_A_KERNEL_FIRECRACKER_TESTS,
        met=False,
        because=(
            f"the kernel is {facts.kernel_release}, below the {oldest} that "
            "Firecracker's own kernel policy lists. Firecracker does not forbid "
            "an older one, but says untabled versions are not validated in its "
            "test suite, and an unvalidated containment boundary is not one to "
            f"rely on ({FIRECRACKER_KERNEL_POLICY_URL})"
        ),
    )


def _judge_programs(facts: MachineFacts) -> Requirement:
    if facts.firecracker_programs_missing:
        return Requirement(
            claim=NEEDS_THE_PROGRAMS_INSTALLED,
            met=False,
            because=(
                "not on the program search path: "
                + ", ".join(facts.firecracker_programs_missing)
            ),
        )
    if not facts.firecracker_programs_found:
        return Requirement(
            claim=NEEDS_THE_PROGRAMS_INSTALLED,
            met=None,
            because=(
                "nothing looked for the Firecracker programs, so whether they "
                "are installed is unknown"
            ),
        )
    return Requirement(
        claim=NEEDS_THE_PROGRAMS_INSTALLED,
        met=True,
        because=(
            "found on the program search path: "
            + ", ".join(facts.firecracker_programs_found)
        ),
    )


def _judge_policy_settings(
    already_judged: Sequence[Requirement],
) -> list[Requirement]:
    """The manifest's own containment settings, which need a machine to check.

    Read from :data:`core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY` rather
    than listed again here, so that a setting added to the manifest turns into a
    line in this report instead of being silently left out of it.

    None of them is ever reported as met. Two separate things would have to be
    true for that, and only one of them is even about the machine: something
    would have to apply the rule, and the machine would have to be able to hold
    it. Nothing applies any of them — see
    :data:`NOTHING_APPLIES_THESE_RULES_YET` — so the second question does not
    arise yet.
    """
    can_start_one = all(item.met is True for item in already_judged)
    settings: list[Requirement] = []

    # The premise first: the manifest does not merely prefer containment, it
    # refuses to validate without it. Everything below is a detail of a thing
    # that is mandatory.
    mandatory = REQUIRED_MICROVM_POLICY.get("required")
    settings.append(
        Requirement(
            claim=(
                "containment is mandatory rather than optional, so a machine "
                "without it must refuse rather than run"
            ),
            met=mandatory is True,
            because=(
                "core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY sets "
                f"required to {mandatory!r}, and a manifest that says "
                "otherwise fails to validate"
            ),
        )
    )

    for name, value in sorted(REQUIRED_MICROVM_POLICY.items()):
        if name == "required":
            continue
        wording = _POLICY_SETTING_AS_A_CLAIM.get(name)
        if wording is None:
            settings.append(
                Requirement(
                    claim=(
                        f"the manifest's containment setting {name!r} "
                        f"({value!r}) holds"
                    ),
                    met=None,
                    because=(
                        "the manifest has gained a containment setting this "
                        "report does not know how to describe or check. Add it "
                        "to core.agentic_v2_containment_readiness before "
                        "relying on this answer"
                    ),
                )
            )
            continue
        settings.append(
            Requirement(
                claim=wording.format(value=value),
                met=None,
                because=(
                    NOTHING_APPLIES_THESE_RULES_YET
                    if can_start_one
                    else "there is no small isolated virtual machine on this "
                    "machine to apply this to, and "
                    + NOTHING_APPLIES_THESE_RULES_YET
                ),
            )
        )
    return settings


def _kernel_version(release: str) -> tuple[int, int] | None:
    match = re.match(r"\s*(\d+)\.(\d+)", release or "")
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


# ── The machines that cannot be read from here ────────────────────────────

RECORDED_FINDINGS: tuple[RecordedFinding, ...] = (
    RecordedFinding(
        machine="github-hosted runner (ubuntu-latest, ubuntu-24.04)",
        could_host_the_containment=False,
        finding=(
            "GitHub's own documentation says that running a virtual machine "
            "inside one of its runners, which is what this containment would "
            "require, is \"technically possible\" but \"not officially "
            "supported\": experimental, at the user's own risk, with no "
            "guarantee of stability, performance or compatibility. A "
            "containment boundary offered with no guarantee is not a "
            "containment boundary, so this is a no rather than an unknown"
        ),
        established_by=(
            "https://docs.github.com/en/actions/using-github-hosted-runners/"
            "using-github-hosted-runners/about-github-hosted-runners"
        ),
        on_date="2026-08-26",
    ),
    RecordedFinding(
        machine="self-hosted runner labelled agentic-sandbox",
        could_host_the_containment=None,
        finding=(
            "there is no such machine. No self-hosted runner is registered to "
            "this repository, and .github/workflows/agentic-sandbox-preflight."
            "yml, the one workflow that asks for this label, has never run. So "
            "the question cannot be answered for it: a machine that does not "
            "exist has no containment either way, and whether a future one "
            "would have it is a decision nobody has taken yet"
        ),
        established_by=(
            "gh api repos/hyeonsangjeon/gdpval-realworks/actions/runners "
            "returned total_count 0, and gh run list --workflow "
            "agentic-sandbox-preflight.yml returned nothing"
        ),
        on_date="2026-08-26",
    ),
)

_LABELS_COVERED_BY_A_FINDING = {
    "ubuntu-latest": RECORDED_FINDINGS[0],
    "ubuntu-24.04": RECORDED_FINDINGS[0],
    "ubuntu-22.04": RECORDED_FINDINGS[0],
    "ubuntu-20.04": RECORDED_FINDINGS[0],
    "agentic-sandbox": RECORDED_FINDINGS[1],
}

_IGNORED_RUNNER_LABELS = frozenset({"self-hosted", "linux", "x64", "x86_64"})


def runner_labels_used_by_workflows(
    workflows_directory: str | Path,
) -> tuple[str, ...]:
    """Every machine label the workflows ask for. Read from the files, offline.

    Reading these rather than listing them means that adding a workflow which
    runs somewhere new makes :func:`check_every_machine_has_a_containment_finding`
    report a gap, instead of the new machine quietly inheriting an answer that
    was established about a different one.
    """
    directory = Path(workflows_directory)
    labels: set[str] = set()
    for path in sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover - defensive
            continue
        for match in re.finditer(r"^\s*runs-on:\s*(.+?)\s*$", text, re.MULTILINE):
            labels.update(_split_runner_labels(match.group(1)))
    return tuple(sorted(labels - _IGNORED_RUNNER_LABELS))


def _split_runner_labels(raw: str) -> Iterable[str]:
    stripped = raw.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    for part in stripped.split(","):
        label = part.strip().strip("\"'")
        # A label written as ${{ ... }} is chosen when the workflow runs, so
        # there is nothing to look up here.
        if label and not label.startswith("${{"):
            yield label


def check_every_machine_has_a_containment_finding(
    workflows_directory: str | Path,
) -> list[str]:
    """Report any machine the workflows use that no finding covers."""
    problems: list[str] = []
    for label in runner_labels_used_by_workflows(workflows_directory):
        if label not in _LABELS_COVERED_BY_A_FINDING:
            problems.append(
                f"a workflow now runs on {label!r}, and no finding records "
                "whether the containment Agentic Sandbox V2 requires is "
                "available there. Establish it before that machine is counted "
                "as a place stage three could run"
            )
    return problems


# ── The answer, and the refusal that follows from it ──────────────────────


def containment_answer_everywhere(
    *,
    facts: MachineFacts | None = None,
    workflows_directory: str | Path | None = None,
) -> dict[str, Any]:
    """The whole answer: this machine read live, the others from record.

    Three answers come back rather than one, because three different things
    would have to be done about them:

    ``could_be_hosted_on_any_machine_in_play``
        Is there a machine that could start the containment? Fixed by finding,
        configuring or building one.
    ``anything_applies_the_containment_rules``
        Does any code turn the rules into arguments for starting it? Fixed by
        writing that code. False today, on every machine, for the reason in
        :data:`NOTHING_APPLIES_THESE_RULES_YET`.
    ``available_on_any_machine_in_play``
        Is the containment actually in place anywhere? Needs both of the above,
        so it is false today and would stay false if a perfect machine appeared
        tomorrow.

    ``every_machine_in_play_has_an_answer`` is ``None`` rather than ``True``
    when no workflows directory was given, because in that case nothing looked.
    A check that treats "nobody asked" as "the answer is yes" is the failure
    this whole module exists to avoid making.
    """
    here = judge_containment(
        facts if facts is not None else read_this_machine(),
        machine="the machine this check is running on",
    )
    could_be_hosted_anywhere = here.machine_could_host_it or any(
        finding.could_host_the_containment is True for finding in RECORDED_FINDINGS
    )
    # Not a machine fact and so not read off one. A rule is applied by code, and
    # no code here applies these; if that changes, this changes with it and so
    # does everything below.
    anything_applies_the_rules = False
    gaps = (
        check_every_machine_has_a_containment_finding(workflows_directory)
        if workflows_directory is not None
        else []
    )
    return {
        "required_containment": dict(REQUIRED_MICROVM_POLICY),
        "this_machine": here.as_dict(),
        "recorded_findings": [finding.as_dict() for finding in RECORDED_FINDINGS],
        "machines_without_a_finding": gaps,
        "every_machine_in_play_has_an_answer": (
            None if workflows_directory is None else not gaps
        ),
        "could_be_hosted_on_any_machine_in_play": could_be_hosted_anywhere,
        "anything_applies_the_containment_rules": anything_applies_the_rules,
        "available_on_any_machine_in_play": (
            could_be_hosted_anywhere and anything_applies_the_rules
        ),
    }


def refuse_command_execution(
    answer: Mapping[str, Any] | None = None,
) -> str | None:
    """The sentence explaining why a model's chosen commands may not run here.

    Returns ``None`` only if the required containment is genuinely available
    somewhere, which today it is not. This exists so that the reason is one
    value a caller can act on rather than something a reader has to infer from a
    report, and so that the day it changes, it changes here.

    There are two reasons it can refuse and the sentence says which, because
    they send a reader to different work. Until 2026-08-26 there was only one,
    and a machine that could host the containment would have cleared the refusal
    while nothing applied a single rule to it.

    It does not switch anything on or off by itself. The three refusals that
    keep command execution shut are unchanged and stay where they are; this is
    the containment answer they were waiting on, not a replacement for them.
    """
    report = answer if answer is not None else containment_answer_everywhere()
    if report.get("available_on_any_machine_in_play"):
        return None

    settings = (
        "a small isolated virtual machine run by "
        f"{REQUIRED_MICROVM_POLICY['runtime']}, with "
        f"network {REQUIRED_MICROVM_POLICY['network']} and a "
        f"{REQUIRED_MICROVM_POLICY['rootfs']} root filesystem"
    )
    if not report.get("could_be_hosted_on_any_machine_in_play"):
        why = f"— {settings} — is not available on any machine in play"
    else:
        why = (
            f"— {settings} — could be started on a machine in play, but "
            "nothing applies its rules: " + NOTHING_APPLIES_THESE_RULES_YET
        )
    return (
        "a model's chosen commands must not run: the containment the substrate "
        f"manifest requires {why}. Running them somewhere weaker instead is the "
        "substitution the specification forbids, so the answer is to leave the "
        "capability shut"
    )


def describe_containment(report: Mapping[str, Any]) -> list[str]:
    """The report as lines to print. No colour, no symbols, no abbreviations."""
    lines: list[str] = []
    required = report["required_containment"]
    lines.append("What the substrate manifest requires before a command may run")
    lines.append("-" * 74)
    lines.append("  a small isolated virtual machine, with these settings:")
    for name, value in sorted(required.items()):
        lines.append(f"      {name}: {value}")
    lines.append("")

    here = report["this_machine"]
    lines.append(f"On {here['machine']}")
    lines.append("-" * 74)
    for requirement in here["requirements"]:
        lines.append(f"  {requirement['claim']}")
        lines.append(f"      {requirement['verdict']}: {requirement['because']}")
    for note in here["notes"]:
        lines.append("")
        lines.append(f"  Worth knowing: {note}")
    lines.append("")

    lines.append("On the machines that cannot be read from here")
    lines.append("-" * 74)
    for finding in report["recorded_findings"]:
        could_host = finding["could_host_the_containment"]
        verdict = (
            "could host it"
            if could_host is True
            else "could not host it"
            if could_host is False
            else "cannot be answered"
        )
        lines.append(f"  {finding['machine']}: {verdict}")
        lines.append(f"      {finding['finding']}")
        lines.append(
            f"      established {finding['on_date']} from "
            f"{finding['established_by']}"
        )
    lines.append("")

    lines.append("Whether anything applies the rules, on any machine")
    lines.append("-" * 74)
    if report["anything_applies_the_containment_rules"]:
        lines.append(
            "  Something now turns the containment rules into arguments for "
            "starting the machine."
        )
    else:
        lines.append(f"  Nothing does: {NOTHING_APPLIES_THESE_RULES_YET}.")
        lines.append(
            "  This is the same on every machine, because it is a fact about "
            "this repository rather than about any machine."
        )
    lines.append("")

    for gap in report["machines_without_a_finding"]:
        lines.append(f"  Gap: {gap}")
    if report["machines_without_a_finding"]:
        lines.append("")

    lines.append("The answer")
    lines.append("-" * 74)
    refusal = refuse_command_execution(report)
    if refusal is None:
        lines.append(
            "  The required containment is available. That removes the "
            "specification's open question, and nothing else: opening command "
            "execution is a separate decision with its own approval."
        )
    else:
        lines.append(f"  {refusal}")
    return lines
