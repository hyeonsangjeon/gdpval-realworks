"""A backend whose ``exec_run`` boots a real machine, and refuses what it lacks.

Stage D1 built the pure half — the guest command, and the reading of one boot.
This is the object the conversation loop actually holds: it keeps a workspace on
the host between calls, and each ``exec_run`` turns into one microVM that runs
one command and is destroyed.

**Why this subclasses the fixture backend.** ``AgenticV2FixtureBackend`` is not
only a stub. Most of it is roughly four hundred lines of workspace path safety —
a directory descriptor pinned by device and inode, every open done relative to
it with ``O_NOFOLLOW``, every resulting descriptor checked back against the root
before a byte is read or written, and quotas on entries, file size and total
size. That code is the reason a model cannot write through a symlink into the
host, and it is identical whether the command afterwards runs in a fixture or in
a machine. Copying it would mean maintaining two versions of the part that must
never drift; so it is inherited, and what makes the fixture a fixture is
overridden away:

- ``start`` returns this backend's own identity, never the fixture's.
- ``state_sha256`` covers the guest image, because with a real guest the image
  is part of what determines what a command does.
- ``exec_run`` boots instead of upper-casing a file.
- ``environment_resolve``, ``environment_activate`` and ``browser_run`` refuse.
- the fixture's package catalogue is emptied, so nothing can advertise it.

A test pins the exact set of inherited public methods. Without it, a convenience
added to the fixture years from now would silently become a production
capability, and nothing would fail.

**What this deliberately does not do.** ``core/agentic_v2_runner.py`` checks at
startup that the backend's identity is the one the runner was told to admit, and
fails anything else with ``compute_start_failed``. Nothing admits this backend:
the declaration defaults to the foundation fixture's identity, no caller in this
repository passes anything else, and the substrate manifests still carry
``production_activation: "disabled"``. The admission is deliberately a value a
caller has to supply rather than a comparison someone can loosen, so that the
day this backend does run, a diff says which identity was let in and who let it
in. Opening it quietly from here would be the one move that makes every other
honest thing in this file worthless. So the backend is proven directly by its
tests, and no run admits it yet.

**The capability gaps are gaps, and are reported as such.** ``environment_*``
cannot work: the machine has no route off itself, which is stage C's fourth
attack, so there is no index to resolve a requirement against. ``browser_run``
could in principle open a local file — the image carries chromium — but nothing
here drives it, so it refuses rather than pretending. Both will change the
outcome of some tasks, and a task that fails for want of a browser must read as
that and not as a model that could not do the work.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from core.agentic_v2_contract import AgenticV2Profile, MICROVM_BACKEND_ID
from core.agentic_v2_exec_boot import (
    EXEC_RECORD_DIR,
    INTERPRETERS,
    ExecRefused,
    command_script,
    effective_deadline,
    read_the_boot,
)
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_microvm import REQUIRED_MICROVM_POLICY
from core.agentic_v2_substrate import AgenticV2SubstrateManifest
from core.agentic_v2_provenance import canonical_sha256


#: Re-exported so that the many uses below read as they always did, while the
#: value itself lives beside the foundation's id in the contract.
BACKEND_ID = MICROVM_BACKEND_ID

MANIFEST_COMMAND_FOR_INTERPRETER = {
    "python": "python",
    "node": "node",
    "r": "Rscript",
    "bash": "bash",
}
"""Contract interpreter name to the command name the substrate manifest uses.

Worth writing down because the two vocabularies disagree in one place and the
disagreement is not visible from either side alone. The manifest requires a
command called ``python``; the guest binary D1 invokes is ``python3``. On a
Debian image both normally exist, but *normally* is not evidence, and a guest
with only one of them would fail every Python call with "not found" while the
manifest went on saying the capability was present. Resolving it is a job for
the capability probe, which runs both and records the answer; until then the
binary names are an argument to this backend rather than a constant, so the
probe's result can be pinned here without touching D1.
"""

BROWSER_OPERATIONS_THAT_NEED_A_NETWORK = frozenset({"search", "open_url"})


@dataclass(frozen=True)
class GuestImage:
    """What was booted, named so that two runs can be told apart.

    The reference and digest identify the container image the guest filesystem
    was built from; the two hashes identify the kernel and root filesystem that
    were actually placed in the jail. All four go into the backend's identity,
    because with a real guest the image *is* the behaviour: the same command in
    two different images is two different commands.
    """

    reference: str
    digest: str
    kernel_sha256: str
    rootfs_sha256: str

    def as_record(self) -> dict[str, str]:
        return {
            "reference": self.reference,
            "digest": self.digest,
            "kernel_sha256": self.kernel_sha256,
            "rootfs_sha256": self.rootfs_sha256,
        }


class AgenticV2MicroVMBackend(AgenticV2FixtureBackend):
    """A backend that runs commands in one throwaway machine per call."""

    def __init__(
        self,
        *,
        root: str | Path,
        profile: AgenticV2Profile,
        image: GuestImage,
        boot_one_command: Callable[..., Mapping[str, Any]],
        substrate_manifest: AgenticV2SubstrateManifest | None = None,
        budget_caps: Mapping[str, Any] | None = None,
        policy: Mapping[str, Any] = REQUIRED_MICROVM_POLICY,
        interpreter_binaries: Mapping[str, str] | None = None,
        **_: Any,
    ):
        super().__init__(root=root, profile=profile, budget_caps=budget_caps)
        # The parent seeds a demonstration catalogue so its own identity check
        # passes. Nothing here may advertise it, so it is emptied rather than
        # left to be found by something later.
        self._package_records = ()
        self.package_catalog = MappingProxyType({})
        self.image = image
        self.manifest = substrate_manifest
        self.policy = dict(policy)
        self.interpreter_binaries = dict(interpreter_binaries or INTERPRETERS)
        self._boot_one_command = boot_one_command
        self.boots: list[dict[str, Any]] = []

    # -- identity ---------------------------------------------------------

    def start(self, timeout_seconds: float) -> Mapping[str, Any]:
        """Report what this is, or say plainly that it cannot be established.

        A real backend with no verified substrate manifest has no honest way to
        describe itself, and inventing a description is worse than failing: it
        would put a hash into the run record that nothing on disk corresponds
        to. ``substrate_manifest_missing`` is already an error the contract
        knows, and it is the true one.
        """
        del timeout_seconds
        if self.manifest is None:
            return {"ok": False, "error_type": "substrate_manifest_missing"}
        return {
            "ok": True,
            "data": {
                "substrate_manifest": {
                    "schema_version": self.manifest.document["schema_version"],
                    "sha256": self.manifest.sha256,
                },
                "backend_identity": self.backend_identity(),
                "package_snapshot_sha256": self.package_snapshot_sha256(),
                "browser_build_sha256": self.browser_build_sha256(),
                "capabilities": self._capabilities(),
            },
        }

    def backend_identity(self) -> dict[str, Any]:
        """Identity derived from the image, not from this file's source text.

        The fixture hashes its own implementation, which is right for something
        whose behaviour is entirely its own code. Here the code decides very
        little: the same wrapper in a different guest is a different machine
        with different programs in it. So the implementation hash covers the
        image, the kernel, the root filesystem and the manifest — change any of
        them and the identity changes, which is what an identity is for.
        """
        return {
            "backend_id": BACKEND_ID,
            "foundation_only": bool(self.manifest.document["foundation_only"])
            if self.manifest is not None
            else True,
            "implementation_sha256": canonical_sha256(
                {
                    "image": self.image.as_record(),
                    "substrate_manifest_sha256": (
                        self.manifest.sha256 if self.manifest is not None else None
                    ),
                    "interpreter_binaries": dict(
                        sorted(self.interpreter_binaries.items())
                    ),
                    "policy": dict(sorted(self.policy.items())),
                }
            ),
        }

    def package_snapshot_sha256(self) -> str:
        """The hash of an empty inventory, which is a fact rather than a filler.

        Nothing can be installed: resolving a requirement needs an index, and
        the machine has no route to one. So the snapshot is empty, and its hash
        is the hash of that. It is a real digest of a real state, and it will
        change the day a snapshot is put into the image.
        """
        return canonical_sha256({"package_records": list(self._package_records)})

    def browser_build_sha256(self) -> str:
        """An identity for the browser *in this image*, and nothing more.

        The image carries chromium, so there is a browser and it has an
        identity; what there is not is an attestation from whoever built it.
        This digest is derived from the image and the manifest's own record of
        the command, so it distinguishes one image's browser from another's.
        Calling it a build signature would be a claim nobody here can support.
        """
        record = None
        if self.manifest is not None:
            for item in self.manifest.document["commands"]:
                if item.get("name") == "chromium":
                    record = item
                    break
        return canonical_sha256(
            {
                "image_digest": self.image.digest,
                "manifest_command": record,
                "driven_by_this_backend": False,
            }
        )

    def state_sha256(self) -> str:
        """The workspace, plus what would run in it.

        The parent's version covers the workspace and the fixture's catalogue.
        Here the image belongs in it too: an identical workspace under a
        different guest is not the same state, and a resume that treated it as
        one would carry a run across a change it should have noticed.
        """
        root_mode, entries, _ = self._workspace_snapshot()
        return canonical_sha256(
            {
                "root_mode": root_mode,
                "profile": self.profile.policy_profile_id,
                "backend_identity": self.backend_identity(),
                "budget_caps": self.budget_caps,
                "entries": entries,
                "active_locks": sorted(self._active_locks),
                "boots": len(self.boots),
                "terminal_result_sha256": (
                    canonical_sha256(self._result) if self._result is not None else None
                ),
            }
        )

    def _capabilities(self) -> dict:
        """What the manifest says is there, filtered by what this can reach.

        Every list is read out of the manifest rather than written here. The two
        empty ones are empty for stated reasons, not for want of filling in:
        packages because nothing can be resolved, and formats because the
        manifest describes capability families rather than a list of formats,
        and turning one into the other would be this file's guess.
        """
        if self.manifest is None:
            return {
                "commands": [],
                "runtimes": [],
                "packages": [],
                "formats": [],
                "budgets": self._budget_items(),
            }
        document = self.manifest.document
        commands = sorted(str(item["name"]) for item in document["commands"])
        declared = set(commands)
        runtimes = sorted(
            name
            for name, command in MANIFEST_COMMAND_FOR_INTERPRETER.items()
            if command in declared
        )
        return {
            "commands": commands,
            "runtimes": runtimes,
            "packages": [],
            "formats": sorted(str(item) for item in document["capability_families"]),
            "budgets": self._budget_items(),
        }

    def _budget_items(self) -> list[str]:
        return [f"{name}={self.budget_caps[name]}" for name in sorted(self.budget_caps)]

    # -- the one call that costs a machine --------------------------------

    def exec_run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Boot one machine, run one command in it, and read back what it did.

        The order matters and is chosen so that nothing is paid for twice. The
        directory is checked on the host first, because a bad path is the one
        failure that can be established without spending a boot on it. Then the
        deadline is reconciled and the wrapper is built — both of which can
        refuse, and refusing before launch costs nothing.

        Output does not come back in the result. ``exec_run``'s data schema is a
        returncode and nothing else with ``additionalProperties`` false, so the
        streams are written into the workspace where the model reads them with
        ``workspace_apply``, the same way it reads anything else.
        """
        try:
            descriptor = self._open_directory(str(arguments.get("cwd", "")))
        except (FileNotFoundError, NotADirectoryError, ValueError, OSError):
            return {"ok": False, "error_type": "path_not_directory"}
        os.close(descriptor)

        try:
            deadline = effective_deadline(
                arguments.get("timeout_seconds"), policy=self.policy
            )
            script = command_script(
                arguments, interpreters=self.interpreter_binaries
            )
        except ExecRefused as refusal:
            self.boots.append(
                {
                    "call": len(self.boots),
                    "refused_before_launch": str(refusal),
                    "booted": False,
                }
            )
            return {"ok": False, "error_type": "invalid_arguments"}

        try:
            boot = self._boot_one_command(
                command_sh=script,
                workspace=self.work,
                deadline_seconds=deadline["applied_seconds"],
            )
        except Exception as failure:  # the launcher itself came apart
            self.boots.append(
                {
                    "call": len(self.boots),
                    "booted": False,
                    "launcher_error": f"{type(failure).__name__}: {failure}",
                    "deadline": deadline,
                }
            )
            return {"ok": False, "error_type": "compute_backend_error"}

        reading = read_the_boot(boot, deadline=deadline)
        record = {
            "call": len(self.boots),
            "booted": True,
            "boot_outcome": reading["boot_outcome"],
            "deadline": reading["deadline"],
            "truncated": reading["truncated"],
            "grounds": reading["grounds"],
            "result": reading["result"],
            "image": self.image.as_record(),
        }
        record["output_files"] = self._keep_the_output(record["call"], reading)
        self.boots.append(record)
        return reading["result"]

    def _keep_the_output(self, call: int, reading: Mapping[str, Any]) -> dict[str, Any]:
        """Put the streams where the model can ask for them.

        If this fails — a full workspace, most likely — the command's own
        answer is still the answer. Losing the returncode because its transcript
        would not fit would turn a finished piece of work into a failure, so the
        loss is recorded and the result is left alone. The model is told nothing
        about it directly, which is honest: from where it sits the files simply
        are not there, and reading a file that is not there already has a
        meaning.
        """
        where = f"{EXEC_RECORD_DIR}/{call:04d}"
        written: dict[str, Any] = {"directory": where, "kept": [], "not_kept": None}
        payloads = {
            "stdout": reading["stdout"].encode("utf-8"),
            "stderr": reading["stderr"].encode("utf-8"),
            "meta.json": json.dumps(
                {
                    "boot_outcome": reading["boot_outcome"],
                    "deadline": reading["deadline"],
                    "truncated": reading["truncated"],
                    "result": reading["result"],
                    "grounds": reading["grounds"],
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
        }
        for leaf, content in payloads.items():
            try:
                self._write_bytes(f"{where}/{leaf}", content)
            except Exception as failure:
                written["not_kept"] = f"{type(failure).__name__}: {failure}"
                break
            written["kept"].append(leaf)
        return written

    # -- what this cannot do ----------------------------------------------

    def environment_resolve(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Refused: resolving needs an index, and the machine has no route out.

        Stage C's fourth attack established that there is exactly one network
        interface in the guest and it is the loopback. That is the containment
        working, and this refusal is its consequence rather than a missing
        feature. A task that needed a package the image does not carry fails
        here, and that failure is about the image, not about the model.
        """
        del arguments
        return {"ok": False, "error_type": "capability_unavailable"}

    def environment_activate(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Refused: there is no lock to activate, because none can be made."""
        del arguments
        return {"ok": False, "error_type": "capability_unavailable"}

    def browser_run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Refused, including ``open_local``, and the two reasons differ.

        ``search`` and ``open_url`` need a network the machine does not have.
        ``open_local`` needs no network — the image has chromium and the file is
        on the work disk — but nothing here starts it, collects what it rendered
        or bounds how long it runs. Returning a hash of the file the model
        already has would look like a browser having run, which is the kind of
        result that is worse than an error.
        """
        operation = str(arguments.get("operation", ""))
        del operation  # both branches refuse; named so the distinction is read
        return {"ok": False, "error_type": "capability_unavailable"}
