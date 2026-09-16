"""Choosing the isolated backend, in the one place that refuses by default.

The cohort runner and the single-task probe want the same thing and only one of
them can ask for it. ``scripts/run_agentic_stage_d_probe.py`` knows how to turn
stage C2's artefact into a guest image and a launcher; ``run_agentic_v2_stage.py``
pins ``BACKEND_IN_USE = AgenticV2FixtureBackend`` and its factory passes
``root=`` plus whatever the runner handed it. Measured rather than assumed:

    AgenticV2MicroVMBackend(root=..., **what_the_runner_passes)
    -> TypeError: missing 3 required keyword-only arguments:
       'profile', 'image', and 'boot_one_command'

``profile`` is already supplied — ``core/agentic_v2_runner.py`` passes it, and
``budget_caps``, into every factory call. So the cohort path is short of exactly
**two** arguments, and both of them are the ones that cannot exist without a
host that has booted a guest. That is the whole gap, and this module is the
place it is closed.

**Why a module in ``core`` rather than an import from the script.** A function
living in ``scripts/`` is reachable by one entry point. The refusals in
:func:`what_a_booted_host_left` are the part worth sharing — four separate
reasons, each asking a different thing of whoever reads them — and a second copy
of them is a second copy to keep right.

**Fail-closed is the default and is not a flag.** :func:`select_backend` called
with no approval returns the fixture and declares no identity, which is what
every caller in this repository does today. There is no argument that means
"use the isolated one anyway": it takes an :class:`IsolationApproval` naming a
person, and an artefact in which a guest really booted — on this kernel, with
the binaries still present and the kernel and rootfs still hashing to what they
hashed then. On a host that never booted one, every one of those refuses, and
the refusal names which. Every way out of this module is
:class:`IsolatedBackendRefused`, so a caller needs one ``except``.

**What this deliberately does not do.** It does not touch
``production_activation``, which stays ``"disabled"`` in every manifest; it does
not loosen ``environment_note``, it supplies the handwritten sentences that
function has always asked for; and it does not widen the workspace file limit,
which starves three of the thirty trial tasks and is a property of the
environment that must keep reading as one.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from core.agentic_v2_contract import MICROVM_BACKEND_ID
from core.agentic_v2_exec_boot import INTERPRETERS
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_guest_image import sha256_file
from core.agentic_v2_microvm import REQUIRED_MICROVM_POLICY
from core.agentic_v2_microvm_backend import AgenticV2MicroVMBackend, GuestImage
from core.agentic_v2_one_call_machine import OneCallMachine
from core.agentic_v2_provenance import (
    canonical_sha256,
    result_verification_standard,
)
from core.agentic_v2_substrate import AgenticV2SubstrateManifest
from core.agentic_v2_tool_availability import availability_for


class IsolatedBackendRefused(RuntimeError):
    """The isolated backend was asked for and the grounds were not there."""


@dataclass(frozen=True)
class BackendChoice:
    """One backend, the arguments it needs, and what it would be admitted as.

    ``extra_kwargs`` is merged into the factory's call rather than replacing it,
    so the runner keeps supplying ``profile`` and ``budget_caps`` and this only
    adds what it cannot know about.

    ``identity_to_declare`` is the value ``AgenticV2ScriptedRunner`` takes as
    ``admitted_identity``. It is ``None`` for the fixture, which is what makes
    the default path byte-identical to the one every existing run took: the
    runner falls back to the foundation's own identity exactly as before.

    There is no ``environment_note`` field. Those sentences are handwritten per
    backend and live beside the backend they describe —
    :func:`isolated_environment_note` here, the fixture's in the stage script —
    rather than being carried around as data, which is how one set ends up
    describing the other.
    """

    backend_class: type
    extra_kwargs: Mapping[str, Any]
    identity_to_declare: Optional[Mapping[str, Any]]
    grounds: Mapping[str, Any]

    @property
    def is_isolated(self) -> bool:
        return self.backend_class is not AgenticV2FixtureBackend


def _the_honest_sentence(census: Mapping[str, int] | None) -> str:
    """The isolated backend's summary line, written from what was counted.

    Four outcomes, and the two in the middle are the reason this is not a
    boolean.

    "Nobody counted" is not "nothing booted". A run whose guests went uncounted
    may have exercised the isolation perfectly; what is missing is the
    evidence, and a record that reported it as zero would invent a failure
    exactly as surely as the old constant invented a success.

    "The model never asked" is not "the backend could not". Both come back with
    no guests, and they are opposite faults: the first is the instruction
    paragraph or the plan, the second is the launcher. If a run returns zero
    guests, that distinction is the whole diagnosis, and a single number
    collapses it.

    The clause about boot cost is on all four. It was true before any of this
    and nothing here measured it. A leaked machine is added on top rather than
    replacing anything, because a command can run perfectly in a guest that
    then refuses to go: the isolation *was* exercised and the host is *not*
    clean, and the record has to carry both.
    """
    unpriced = " What it cost to boot is not known, so no total here is complete."
    if census is None:
        return (
            "a real model drove a real tool loop with the V2 tool contract "
            "enforced, on the backend that boots. Nothing counted the guests, "
            "so whether the isolation was exercised is not answered here."
        ) + unpriced

    booted = census.get("guests_that_actually_booted", 0)
    asked = census.get("exec_run_calls", 0)
    left_running = census.get("guests_that_left_a_machine_running", 0)

    if booted == 0 and asked == 0:
        return (
            "a real model drove a real tool loop with the V2 tool contract "
            "enforced, on the backend that boots — and it never asked it to. "
            "No exec_run call was made, so the isolation was mounted and not "
            "exercised. This is not evidence that the sandbox runs anything."
        ) + unpriced
    if booted == 0:
        return (
            f"a real model drove a real tool loop with the V2 tool contract "
            f"enforced, and asked the isolation to run something "
            f"{asked} times. No machine started on any of them, so the "
            f"isolation was mounted and not exercised. The model did its part "
            f"here; look at the backend, not at the plan."
        ) + unpriced

    leaked = (
        ""
        if left_running == 0
        else (
            f" {left_running} of them left a machine running on the host, so "
            f"the host was not clean afterwards and this run does not show "
            f"teardown working."
        )
    )
    return (
        f"a real model drove a real tool loop inside a guest that really "
        f"booted, one machine per command, with the V2 tool contract "
        f"enforced. {booted} of {asked} exec_run calls entered a guest, "
        f"counted, so the isolation was exercised.{leaked}"
    ) + unpriced


#: What the isolated backend is, in words that survive being quoted.
#:
#: Written by hand, because ``environment_note`` in the stage script refuses to
#: adapt the fixture's — and is right to. The shape is the fixture's shape, key
#: for key, so that switching backends changes what the record says and never
#: how much it says.
#:
#: The second entry under ``what_was_not_real`` is the one that will be quoted
#: back. ``browser_run`` refuses *every* operation here, including
#: ``open_local``, which the fixture served. In the one paid cohort that has
#: run, all twelve ``browser_run`` calls asked for ``search`` or ``open_url`` —
#: eight and four — and none asked for ``open_local``, so those twelve tasks
#: fail here too, for the same reason. Booting a real guest does not recover
#: them, and a record that let someone infer otherwise would be the expensive
#: kind of wrong.
#:
#: ``guest_booted`` and ``exec_run_open`` are constants here and are meant to
#: be. They say what this backend *is* — it boots, and its ``exec_run`` serves
#: — which is a property of the class and true before any task runs.
#:
#: What they are not is a reading of the run, and the sentence underneath them
#: used to be written as though they were: "a guest that really booted ... The
#: isolation was exercised", emitted whether or not one ever did. Every way a
#: cohort can finish with no boot in it leaves that claim standing — a model
#: that never calls ``exec_run``, an instruction paragraph that tells it not
#: to, every task ending on an earlier refusal. The first of those was the
#: live case: on ``agentic_stage_one_plan.yaml`` the model is told ``exec_run``
#: refuses every time, so it does not ask, and the record would have reported
#: exercised isolation over a cohort that never entered a machine.
#:
#: So the counts are passed in by whoever ran the tasks, read off the backends
#: that served them, and the honest sentence is written from them. ``None``
#: means nobody counted, and is not read as zero: an uncounted run and an
#: unexercised one are different failures and the record says which it had.
#:
#: Three numbers rather than one, because ``exec_run_calls`` and
#: ``guests_that_actually_booted`` come apart. A call refused before launch is
#: in the first and not the second, so a run where the model asked five times
#: and no machine started reads differently from one where it never asked —
#: the launcher in the first case, the plan in the second.
#: ``guests_that_left_a_machine_running`` is the only line in the whole record
#: that answers whether the host was clean when the run finished.
def isolated_environment_note(
    profile: Mapping[str, Any], *, census: Mapping[str, int] | None = None
) -> dict[str, Any]:
    booted = None if census is None else census.get("guests_that_actually_booted", 0)
    asked = None if census is None else census.get("exec_run_calls", 0)
    left_running = (
        None
        if census is None
        else census.get("guests_that_left_a_machine_running", 0)
    )

    # ``None`` belongs with the counts that booted, not with zero: an uncounted
    # run is not a run that is known to have entered no guest.
    if booted != 0:
        about_the_isolation = (
            "nothing about the isolation: this is the backend that boots"
        )
    elif asked == 0:
        about_the_isolation = (
            "the isolation, in the end: the backend that boots was mounted "
            "and no exec_run call asked it to, so nothing ran in a guest"
        )
    else:
        about_the_isolation = (
            "the isolation, in the end: the backend that boots was mounted, "
            f"exec_run was called {asked} times and no machine started, so "
            "nothing ran in a guest"
        )

    return {
        "backend": AgenticV2MicroVMBackend.__name__,
        "guest_booted": True,
        "exec_run_open": True,
        "exec_run_calls": asked,
        "guests_that_actually_booted": booted,
        "guests_that_left_a_machine_running": left_running,
        "policy_profile_id": profile.get("policy_profile_id"),
        "tool_availability": [
            {
                "tool": entry.tool,
                "verdict": entry.verdict,
                "how_we_know": entry.evidence,
            }
            for entry in availability_for(AgenticV2MicroVMBackend)
        ],
        "what_was_real": [
            "the model, the deployment and the charge for every call",
            "the tool choices the model made, turn by turn",
            *(
                []
                if booted == 0
                else [
                    "one microVM per exec_run call, destroyed when the "
                    "command returned",
                    "the exit status, stdout and stderr of every command "
                    "that ran",
                ]
            ),
            "the files workspace_apply wrote, and the deliverables collected",
            "the per-task ceilings, which stopped tasks that reached them",
        ],
        "what_was_not_real": [
            about_the_isolation,
            "browser_run, which refuses every operation here including "
            "open_local; the fixture served open_local and this does not, so "
            "a task that needs a browser fails harder here, not less",
            "environment_resolve and environment_activate, which cannot work: "
            "the guest has one interface and it is the loopback",
            "the cost of a boot, which nothing in this repository has measured",
        ],
        "so_the_honest_sentence_is": _the_honest_sentence(census),
    }


#: Which backend has sentences, keyed by class name rather than by class.
#:
#: Keyed by name on purpose. ``scripts/run_agentic_v2_stage.py`` is held to
#: naming exactly one concrete backend class — the fixture — by a test that
#: parses it, because a script that can name a second one can mount a second one
#: by a one-word edit and nothing downstream would notice. Looking the writer up
#: by ``backend.__name__`` lets the stage script dispatch without acquiring that
#: ability, and a backend with no entry here still gets the refusal it always
#: got: the sentences are written per backend, or the run does not start.
HANDWRITTEN_NOTES: Mapping[str, Any] = {
    AgenticV2MicroVMBackend.__name__: isolated_environment_note,
}


def what_a_booted_host_left(path: str | Path) -> dict[str, Any]:
    """Stage C2's artefact, or a refusal that says which thing is missing.

    A refusal per thing that can be wrong, rather than one for all of them,
    because they ask different things of whoever reads them: run C2, run C2
    *here*, fix the host, re-run the boot that failed, or go and look at what
    wrote this file. A single "the isolated backend is unavailable" would hide
    which, and the difference is the difference between a five-minute fix and a
    re-provisioned machine.

    **Absent evidence is refused, not skipped.** Until 2026-09-14 the kernel
    check read ``host.kernel_release`` with ``or ""`` and then compared only if
    the result was non-empty, so an artefact with no ``host`` block, no
    ``kernel_release``, or an empty one passed the check that exists to catch
    exactly that. An artefact that says nothing about the machine it ran on is
    the case this check is for, not an exemption from it.

    **What a matching release does and does not establish.** Two hosts
    provisioned from one image report the same release, so equality here is not
    a host identity and must not be read as one. What it rules out is an
    artefact carried over from a *differently* provisioned machine. The host is
    pinned by the other checks — the recorded binaries still being where they
    were, and the images still hashing to what they hashed to — and by the
    approval naming the artefact.

    Lifted from ``scripts/run_agentic_stage_d_probe.py`` so the cohort path gets
    the same refusals rather than a second set that drifts from them.
    """
    path = Path(path)
    if not path.is_file():
        raise IsolatedBackendRefused(
            f"there is no first-boot artefact at {path}. The isolated backend "
            "runs on a host that has already booted a guest, and this host has "
            "not been shown to have done so. Run "
            "scripts/run_agentic_c2_first_boot.py first"
        )
    artefact = json.loads(path.read_text(encoding="utf-8"))

    outcome = str(artefact.get("outcome") or "")
    if outcome != "booted":
        raise IsolatedBackendRefused(
            f"the artefact records {outcome!r}, not a boot"
            + (f" — {artefact['reason']}" if artefact.get("reason") else "")
            + ". A cohort started now would be paid for and then have nothing "
            "to run its commands on"
        )

    host = artefact.get("host")
    if host is None:
        raise IsolatedBackendRefused(
            "the artefact carries no host block, so nothing in it says which "
            "machine the guest booted on. That is the case this check exists "
            "for, and it is refused rather than waved through"
        )
    if not isinstance(host, dict):
        raise IsolatedBackendRefused(
            f"the artefact's host is a {type(host).__name__} rather than a "
            "block of host facts, so it was not written by the first-boot "
            "script and nothing in it can be read as evidence"
        )
    recorded = host.get("kernel_release")
    if recorded is None:
        raise IsolatedBackendRefused(
            "the artefact's host block records no kernel_release, so there is "
            "no evidence that the machine about to be paid for is the machine "
            "that booted a guest"
        )
    if not isinstance(recorded, str):
        raise IsolatedBackendRefused(
            f"the artefact's host.kernel_release is a {type(recorded).__name__} "
            "rather than a release string, so it names no kernel"
        )
    if not recorded.strip():
        raise IsolatedBackendRefused(
            "the artefact's host.kernel_release is empty, which is not a kernel "
            "this host can be compared against"
        )
    running = os.uname().release
    if recorded.strip() != running:
        raise IsolatedBackendRefused(
            f"the guest booted on kernel {recorded.strip()} and this host is "
            f"running {running}, so the artefact describes a different machine "
            "than the one about to be paid for"
        )

    for binary in ("firecracker", "jailer"):
        where = host.get(binary)
        if not where or not Path(str(where)).exists():
            raise IsolatedBackendRefused(
                f"{binary} was recorded at {where!r} and it is not there now"
            )
    return artefact


def the_images_are_unchanged(
    artefact: Mapping[str, Any], *, sha256: Any = None
) -> dict[str, Any]:
    """Re-hash the kernel and rootfs, and refuse if they moved.

    Expected to pass, which is not a reason to skip it. A re-provisioned disk, a
    truncated download and a rootfs somebody rebuilt between stages all look
    like a healthy host until the first ``exec_run`` — and for a cohort that is
    220 tasks after the money started.

    The work disk is deliberately not checked. Every call builds its own, which
    is the ``workdir: ephemeral`` obligation; pinning one would assert exactly
    the thing that must not be true.
    """
    measure = sha256 or sha256_file
    images = artefact["images"]
    checked: dict[str, Any] = {}
    for which in ("kernel", "rootfs"):
        recorded = images[which]
        where = Path(str(recorded["path"]))
        if not where.is_file():
            raise IsolatedBackendRefused(
                f"the {which} booted at {where} and it is not there now. The "
                "host has been re-provisioned or the file was removed; boot a "
                "guest again before paying for anything on it"
            )
        found = measure(where)
        if found != str(recorded["sha256"]):
            raise IsolatedBackendRefused(
                f"the {which} at {where} hashes {found}, and the guest booted "
                f"{recorded['sha256']}. These are different bytes, so that "
                "record is not evidence about the machine this run would use"
            )
        checked[which] = {"path": where.as_posix(), "sha256": found}
    checked["matches_the_guest_that_booted"] = True
    checked["work_disk"] = (
        "not checked, deliberately — every call builds its own, which is the "
        "workdir: ephemeral obligation"
    )
    return checked


def the_guest_that_booted(artefact: Mapping[str, Any]) -> GuestImage:
    """The four identifiers that make one guest distinguishable from another."""
    images = artefact["images"]
    pulled = images["image"]
    return GuestImage(
        reference=str(pulled["repository"]),
        digest=str(pulled.get("pinned_digest") or pulled["manifest_digest"]),
        kernel_sha256=str(images["kernel"]["sha256"]),
        rootfs_sha256=str(images["rootfs"]["sha256"]),
    )


def one_machine_per_call(
    artefact: Mapping[str, Any],
    *,
    scratch: str | Path,
    session: str,
    vcpu_count: int,
) -> OneCallMachine:
    """The launcher, on the binaries and the account the first boot used."""
    host = artefact["host"]
    account = artefact["jail_account"]
    images = artefact["images"]
    return OneCallMachine(
        kernel=Path(images["kernel"]["path"]),
        rootfs=Path(images["rootfs"]["path"]),
        firecracker_binary=Path(str(host["firecracker"])),
        jailer_binary=str(host["jailer"]),
        uid=int(account["uid"]),
        gid=int(account["gid"]),
        vcpu_count=vcpu_count,
        cgroup_version=int(host["cgroup_version"]),
        scratch=Path(scratch),
        session=session,
    )


def the_fixture() -> BackendChoice:
    """What every run has used, unchanged and declaring nothing.

    ``identity_to_declare`` is ``None`` rather than the foundation's identity
    spelled out again. The runner already falls back to exactly that value, and
    writing it here would be a second place for it to be right.
    """
    return BackendChoice(
        backend_class=AgenticV2FixtureBackend,
        extra_kwargs={},
        identity_to_declare=None,
        grounds={"selected": "the default, which needs no grounds"},
    )


@dataclass(frozen=True)
class IsolationApproval:
    """A reviewable document saying who allowed a run onto a real guest.

    A file rather than a set of command-line flags, for three reasons that all
    point the same way. It can be read before it is used; it can be committed
    beside the run it authorised; and the approver's name ends up in the run
    record instead of in one person's shell history.

    Unknown keys are refused rather than ignored. A misspelt ``approved_by``
    that is silently dropped becomes an unapproved run that believes it was
    approved, and that is the one failure this document exists to prevent.
    """

    approved_by: str
    first_boot_artefact: Path
    substrate_manifest: Path
    scratch: Path
    vcpu_count: int = 2

    @classmethod
    def from_mapping(cls, value: Any) -> "IsolationApproval":
        if not isinstance(value, Mapping):
            raise IsolatedBackendRefused(
                "an isolation approval must be an object with "
                "approved_by, first_boot_artefact, substrate_manifest and "
                "scratch in it"
            )
        required = {
            "approved_by", "first_boot_artefact", "substrate_manifest", "scratch"
        }
        unknown = set(value) - required - {"vcpu_count"}
        if unknown:
            raise IsolatedBackendRefused(
                f"unknown isolation approval setting(s): {sorted(unknown)}. A "
                "key nobody reads is a condition somebody thinks they set"
            )
        missing = sorted(k for k in required if not str(value.get(k) or "").strip())
        if missing:
            raise IsolatedBackendRefused(
                f"the isolation approval says nothing about {missing}. "
                "An approver with no artefact is a claim about a machine "
                "nobody checked; an artefact with no approver is a "
                "configuration that drifted into being"
            )
        count = value.get("vcpu_count", 2)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise IsolatedBackendRefused(
                f"vcpu_count is {count!r}, and it is a whole number of "
                "processors of at least one"
            )
        return cls(
            approved_by=str(value["approved_by"]).strip(),
            first_boot_artefact=Path(str(value["first_boot_artefact"])),
            substrate_manifest=Path(str(value["substrate_manifest"])),
            scratch=Path(str(value["scratch"])),
            vcpu_count=count,
        )

    @classmethod
    def load(cls, path: str | Path) -> "IsolationApproval":
        source = Path(path)
        if not source.is_file():
            raise IsolatedBackendRefused(
                f"there is no isolation approval at {source}"
            )
        return cls.from_mapping(json.loads(source.read_text(encoding="utf-8")))


def select_backend(
    *,
    approval: IsolationApproval | None = None,
    session: str | None = None,
    sha256: Any = None,
) -> BackendChoice:
    """The fixture, unless an approval and a booted host both say otherwise.

    Called with no approval — which is every caller in this repository today —
    this returns the fixture and declares no identity, so the default path is
    the one every existing run took.
    """
    if approval is None:
        return the_fixture()
    if not session:
        raise IsolatedBackendRefused(
            "the launcher needs a session name, which is the run id; without "
            "one two runs would build their jails on top of each other"
        )

    # Wrapped, because every way out of this module has to be the one exception
    # the caller catches. A manifest that is missing or malformed raises
    # OSError or ValueError from deep inside the validator, and an uncaught one
    # ends the stage in a stack trace where a sentence belongs.
    try:
        substrate_manifest = AgenticV2SubstrateManifest.load(
            approval.substrate_manifest
        )
    except (OSError, ValueError) as exc:
        raise IsolatedBackendRefused(
            f"the substrate manifest at {approval.substrate_manifest} could "
            f"not be read as one: {exc}. Without it the backend cannot "
            "describe itself, and start() would answer "
            "substrate_manifest_missing on every task"
        ) from exc
    first_boot_artefact = approval.first_boot_artefact
    scratch = approval.scratch
    approved_by = approval.approved_by
    vcpu_count = approval.vcpu_count

    if substrate_manifest.document.get("foundation_only") is not True:
        raise IsolatedBackendRefused(
            "this manifest is not foundation-only, and admitting a second "
            "backend is a change of which substrate may run — it is not "
            "permission to leave the foundation. The runner's own validator "
            "would raise on the identity built from it"
        )
    # Raises for a backend the verifier has no standard for, which is the one
    # condition that must not be discovered at startup: a run that admits a
    # backend whose results nothing knows how to judge would look verified.
    result_verification_standard(MICROVM_BACKEND_ID)

    artefact = what_a_booted_host_left(first_boot_artefact)
    images = the_images_are_unchanged(artefact, sha256=sha256)
    image = the_guest_that_booted(artefact)
    machine = one_machine_per_call(
        artefact, scratch=scratch, session=session, vcpu_count=vcpu_count
    )

    return BackendChoice(
        backend_class=AgenticV2MicroVMBackend,
        extra_kwargs={
            "image": image,
            "boot_one_command": machine,
            "substrate_manifest": substrate_manifest,
        },
        identity_to_declare=_identity_of(
            image=image, manifest=substrate_manifest
        ),
        grounds={
            "approved_by": approved_by,
            "first_boot_artefact": Path(first_boot_artefact).as_posix(),
            "images_rechecked": images,
            "kernel_release": os.uname().release,
            "what_the_kernel_release_shows": (
                "that this host and the artefact's host report the same "
                "release, which rules out an artefact carried over from a "
                "differently provisioned machine. It is not a host identity — "
                "two machines built from one image report the same string — "
                "and it is recorded next to the value so that nobody reads the "
                "value as more than it is"
            ),
        },
    )


def _identity_of(
    *,
    image: GuestImage,
    manifest: AgenticV2SubstrateManifest,
) -> Mapping[str, Any]:
    """What the runner would have to admit for this backend to start.

    Rebuilt from the recipe rather than read off a backend instance, and that
    is the whole point of it. Asking ``AgenticV2MicroVMBackend.backend_identity``
    would produce a value that agrees with the backend by construction and could
    therefore never disagree with it — a check that cannot fail is not a check.
    Computing the four ingredients here means
    :func:`the_declared_identity_matches_a_real_backend` compares two
    independent derivations, and anyone who changes the ingredients on one side
    gets a red test instead of a run that dies at ``compute_start_failed`` on
    every task.

    The constants come from where the backend gets them — the contract, the
    exec-boot interpreter table, the microVM policy — rather than from the
    backend module, so this does not import the thing it is checking.
    """
    return {
        "backend_id": MICROVM_BACKEND_ID,
        "foundation_only": bool(manifest.document["foundation_only"]),
        "implementation_sha256": canonical_sha256(
            {
                "image": image.as_record(),
                "substrate_manifest_sha256": manifest.sha256,
                "interpreter_binaries": dict(sorted(INTERPRETERS.items())),
                "policy": dict(sorted(REQUIRED_MICROVM_POLICY.items())),
            }
        ),
    }
