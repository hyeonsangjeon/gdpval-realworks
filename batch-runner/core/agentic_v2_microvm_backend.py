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
fails anything else with ``compute_start_failed``. One caller can admit this
backend and only one: ``scripts/run_agentic_v2_stage.py`` passes whatever
``select_backend`` chose, which is this backend's identity when the run was
given ``--isolated-approval`` and the approval held up, and ``None`` — the
foundation fixture's identity, the path every run to date took — otherwise.
The substrate manifests still carry ``production_activation: "disabled"``, and
no real host has booted one of these. Until 2026-09-14 this paragraph opened by
ruling out any admitting caller at all, which was right when it was written and
wrong from the moment the flag was wired; a stale reassurance, in the file a
reader opens *to check*, is the worst place to leave one.

The admission is deliberately a value a caller has to supply rather than a
comparison someone can loosen, so that the day this backend does run, a diff
says which identity was let in and who let it in. Opening it quietly from here
would be the one move that makes every other honest thing in this file
worthless. So the backend is proven directly by its tests, and the one path
that admits it has to be asked for on the command line.

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
from core.agentic_v2_first_boot import the_host_was_left_running
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

UNRESOLVED_HOST_RECORD = "unresolved_host.json"
"""The file a run leaves behind when it could not give a host back.

One name, in a directory the caller passes in, read by the next backend before
it boots anything. It is deliberately a file and not a field on this class: the
class is rebuilt for every task, so a field could not have been the thing that
reaches task N+1, and neither could anything else held in this process.
"""

UNRESOLVED_HOST_SCHEMA = "agentic_v2_unresolved_host/1"
"""Stamped into the record so a reader can tell it is the thing it expects.

Versioned because the refusal it drives is fail-closed: a future reader that
does not recognise the shape has to keep refusing rather than treat an
unparsed record as an absent one.
"""

BROWSER_OPERATIONS_THAT_NEED_A_NETWORK = frozenset({"search", "open_url"})


def _how_the_machine_ended(boot: Mapping[str, Any]) -> dict[str, Any]:
    """Carry the launcher's ownership and shutdown evidence into the record.

    ``read_the_boot`` answers what the *command* did, which is what the model is
    told. It says nothing about what happened to the machine that ran it, and on
    a host running more than one of these at a time that is the half that matters
    afterwards: whether this run established the process was its own before it
    signalled anything, and whether the guest was confirmed gone rather than
    merely sent a signal. Sent and gone are separate observations, so they are
    kept under separate keys here as well; folding them into one boolean is how
    "SIGKILL was delivered" came to read as "the host is free again".

    Three axes, and they are kept apart on purpose. What the command did lives
    in ``result``. Whether the host is free again is ``host_left_running``.
    Whether the bytes the guest wrote may be read as an intact filesystem is
    ``copy_integrity``. All three can disagree — a command can exit 0 in a guest
    that then refuses to shut down, leaving a work disk copied out from under a
    live writer — and the record is where that disagreement has to survive,
    because the model is told only the first of the three.

    Every value is read with ``.get``. A launcher that does not report these is
    recorded as not having reported them, which is a different statement from
    reporting that nothing was owned, and neither one is worth an exception
    inside a boot that otherwise succeeded.
    """
    evidence = boot.get("pid_file") or {}
    salvaged = boot.get("salvaged") or {}
    return {
        "outcome": boot.get("outcome"),
        "vm_id": boot.get("vm_id"),
        "owned_by_this_run": evidence.get("owned_by_this_run"),
        "ownership_grounds": evidence.get("ownership_grounds"),
        "left_alone_because": evidence.get("left_alone_because"),
        "cannot_rule_out": evidence.get("cannot_rule_out"),
        "stop_signal_sent": boot.get("stop_signal_sent"),
        "guest_confirmed_stopped": boot.get("guest_confirmed_stopped"),
        "guest_last_seen_running": boot.get("guest_last_seen_running"),
        "host_left_running": the_host_was_left_running(boot),
        "copied_while_running": salvaged.get("copied_while_running"),
        "copy_integrity": salvaged.get("copy_integrity"),
        "copy_integrity_because": salvaged.get("copy_integrity_because"),
        "returned_copy": salvaged.get("returned_copy"),
        "teardown": boot.get("teardown"),
    }


def _what_a_failed_launch_left_behind(
    teardown: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Say whether a launch that *raised* may have left a machine of ours up.

    The ordinary path answers this from a boot record. A launch that came apart
    never produced one, so the same question has to be answered from the
    teardown the failure carries — and until now it was not answered at all.
    The record kept ``launcher_error`` and no ``machine``, so
    ``host_left_running`` was never computed, and a launch that failed with a
    guest still up was indistinguishable, to both guards, from one that failed
    having started nothing.

    Every branch turns on a *positive* fact about this run's own launch, asked
    in the order the teardown establishes them — liveness before identity, the
    way ``_clean_up_after_a_failure`` asks them. Two of the branches are
    positive controls pointing the other way: a launch known to have started
    nothing, and a process confirmed stopped, must not be written down as a
    host left running, because a record that exists refuses the *next* task
    before it reaches a model.

    ``all_gone`` is deliberately not consulted. It is ``False`` for three
    unrelated reasons — the claim was lost to another run, a machine may still
    be up, or ``rmtree`` failed on a directory — so keying on it would turn an
    ordinary file-removal failure into a permanent run-wide refusal. For a
    related reason the answer does not turn on ``jail_held_by_this_run``: a jail
    now held by somebody else says nothing about whether *this* run's process is
    still up, and the record written here refuses this run's own next boot
    rather than reaching for anyone else's machine.

    A failure carrying no teardown is not a machine this run started.
    ``first_boot`` raises those *before* its launch block — an unusable plan, or
    a jail name already taken — refusals about the plan and about the claim,
    which its own docstring keeps apart from findings about a machine. That is
    recorded as the absence it is, under ``launch_facts``, and claims nothing in
    either direction.

    ``vm_id`` is ``None`` throughout: it is derived by the launcher and read off
    a boot record, and a launch that raised produced none. The jail it would
    have named is in ``teardown["process"]["pid_file"]``, which the boot record
    keeps.
    """
    if teardown is None:
        return {
            "launch_facts": "none: the failure carried no teardown",
            "outcome": "launch_failed_before_anything_started",
            "vm_id": None,
            "left_alone_because": (
                "the failure carried no teardown, so the launch block was never "
                "entered and there is no machine of this run's to account for"
            ),
            "cannot_rule_out": None,
            "stop_signal_sent": None,
            "guest_confirmed_stopped": None,
            "guest_last_seen_running": None,
            "host_left_running": False,
        }

    process = teardown.get("process") or {}
    reading = {
        "launch_facts": "read from the teardown the failure carried",
        "vm_id": None,
        "left_alone_because": process.get("left_alone_because"),
        "cannot_rule_out": process.get("cannot_rule_out"),
        "stop_signal_sent": process.get("signalled"),
        "guest_confirmed_stopped": process.get("confirmed_stopped"),
        "guest_last_seen_running": process.get("was_running"),
    }

    if process.get("confirmed_stopped") is True:
        # Stopped is stopped. Whether the directory came off the disk is a
        # separate outcome and an infrastructure error in its own right; it is
        # not grounds for telling the next task a process is running.
        reading["outcome"] = "launch_failed_after_the_process_was_confirmed_stopped"
        reading["host_left_running"] = False
    elif process.get("was_running") is True:
        reading["outcome"] = "launch_failed_with_the_process_still_running"
        reading["host_left_running"] = True
    elif process.get("launch_was_attempted") is not True:
        reading["outcome"] = "launch_failed_before_anything_started"
        reading["host_left_running"] = False
    elif (
        process.get("launch_spawned_nothing") is True
        and process.get("pid_file_appeared") is not True
    ):
        # The one launch failure that carries its own proof: the jailer never
        # exec'd, so the child was reaped before it became anything.
        reading["outcome"] = "launch_failed_without_starting_anything"
        reading["host_left_running"] = False
    else:
        reading["outcome"] = "launch_failed_and_what_it_started_is_unaccounted_for"
        reading["host_left_running"] = True
    return reading


def read_the_unresolved_host(
    host_state_dir: str | Path | None,
) -> Mapping[str, Any] | None:
    """A host an earlier task left running, read back from a run's own disk.

    Module level rather than a method because two very different callers have
    to get the same answer from it: the backend, deciding whether to boot, and
    the stage script, deciding whether to let another task start at all. A
    second implementation of "is the host still dirty" is the kind of thing
    that stays in agreement for about one change.

    ``None`` is not "the host is free". It is "no record of a leak was found",
    and with no directory to look in it is "there was nowhere to look". The
    caller that cares about that difference is the one that chose the
    directory.

    A record is still unresolved unless it carries a ``resolved`` block saying
    cleanup was confirmed. Nothing in a run writes that block, and nothing
    here deletes the file. Re-admission is meant to cost someone a deliberate
    act on the host: this code never removes a jail, never signals by number,
    and never decides on its own that a machine it could not stop has since
    stopped.

    A record that exists and cannot be read comes back as a record, carrying
    why. That is deliberate. It is the one state where refusing costs a task
    and proceeding could put a second machine on a host that already has one.
    """
    if host_state_dir is None:
        return None
    path = Path(host_state_dir) / UNRESOLVED_HOST_RECORD
    try:
        written = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as unreadable:
        return {
            "unreadable": f"{type(unreadable).__name__}: {unreadable}",
            "path": str(path),
        }
    if not isinstance(written, Mapping):
        return {"unreadable": "the record is not an object", "path": str(path)}
    if written.get("schema") != UNRESOLVED_HOST_SCHEMA:
        return {
            "unreadable": f"the record is stamped {written.get('schema')!r}, "
            f"which this reader does not know",
            "path": str(path),
        }
    resolved = written.get("resolved")
    if isinstance(resolved, Mapping) and resolved.get("cleanup_confirmed") is True:
        return None
    return written


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
        host_state_dir: str | Path | None = None,
        task_id: str | None = None,
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
        self.task_id = task_id
        # Where a host this run could not give back is written down, and the
        # one piece of state here that is meant to outlive the object. It is
        # passed in rather than derived — ``root`` is this *attempt's*
        # directory, so ``root.parent`` would be a different place on a retry
        # and, under pytest, a directory shared with every other test in the
        # session. A caller that wants the record across tasks says where.
        self.host_state_dir = None if host_state_dir is None else Path(host_state_dir)

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

    def _a_machine_this_session_left_running(self) -> Mapping[str, Any] | None:
        """The first earlier call that ended without giving the host back.

        ``the_host_was_left_running`` already decides this for a single boot,
        and ``_how_the_machine_ended`` already writes the answer into every
        record. Nothing read it. The reading was produced, filed, and then the
        next call booted onto the same host regardless.

        That gap matters because the two questions are not the same question.
        Whether a command succeeded is about the command; whether the host is
        free afterwards is about the host. A task can finish perfectly well and
        still leave a machine behind, and the next task would then be measured
        on a host that is no longer this run's alone.

        Returns the record, not a bool, so the refusal can name which call it
        was. The first one is enough: once the host is not free it does not
        become free again by itself, and a later leak adds nothing to the
        decision being made here.

        This reading is *this object's* calls only, which is one task's worth:
        the stage script builds a backend per task. The half that reaches the
        next task is :meth:`_a_host_left_unresolved_on_disk`.
        """
        for record in self.boots:
            machine = record.get("machine") or {}
            if machine.get("host_left_running") is True:
                return record
        return None

    def _a_host_left_unresolved_on_disk(self) -> Mapping[str, Any] | None:
        """A host an earlier task left running, read back from the run's own disk.

        The in-memory reading above cannot see across tasks, and not because it
        was written carelessly: the object it lives on is constructed once per
        task, so by the time the next task's first boot is decided, the record
        of the leak has been garbage collected along with the backend that made
        it. The missing thing was a lifetime, not a branch — no amount of
        checking ``self.boots`` reaches a list that no longer exists.

        So the fact is also written to a file in a directory the caller names,
        and read back from there. That is what survives the backend being
        rebuilt, and it is what survives the process ending and a resumed run
        starting a new one.

        ``None`` here is not the same as "the host is free". It is "no record
        of a leak was found", and when no ``host_state_dir`` was given it is
        "there was nowhere to look". The caller that cares about the difference
        is the one that passed the directory.

        The reading itself is :func:`read_the_unresolved_host`, module level,
        because the stage script has to get the same answer before it lets a
        task start at all — and two implementations of "is the host still
        dirty" stay in agreement for about one change.
        """
        return read_the_unresolved_host(self.host_state_dir)

    def _write_down_the_unresolved_host(self, record: Mapping[str, Any]) -> None:
        """Put a host this run could not give back where the next task will look.

        Called only when the boot that just finished left a machine running.
        Written once — the first leak is the one that matters, and a second
        would only move the blame off the task that caused it.

        A failure to write is recorded in the boot record rather than raised.
        The boot has already happened by this point and its result belongs to
        the task; what a raise would change is not whether the host is dirty
        but whether the task that paid for the work gets to keep it. The
        same-task guard still fires on ``self.boots`` either way, so the run
        still stops — it just stops without the record reaching the next
        process, which is exactly what the field says.
        """
        if self.host_state_dir is None:
            record["unresolved_host_record"] = None
            record["unresolved_host_record_error"] = (
                "no host_state_dir was given, so the leak is recorded for this "
                "task only and cannot reach the next one"
            )
            return
        path = self.host_state_dir / UNRESOLVED_HOST_RECORD
        machine = record.get("machine") or {}
        try:
            if path.exists():
                record["unresolved_host_record"] = str(path)
                return
            self.host_state_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "schema": UNRESOLVED_HOST_SCHEMA,
                        "task_id": self.task_id,
                        "call": record.get("call"),
                        "vm_id": machine.get("vm_id"),
                        "outcome": machine.get("outcome"),
                        "left_alone_because": machine.get("left_alone_because"),
                        "cannot_rule_out": machine.get("cannot_rule_out"),
                        "guest_last_seen_running": machine.get(
                            "guest_last_seen_running"
                        ),
                        "guest_confirmed_stopped": machine.get(
                            "guest_confirmed_stopped"
                        ),
                        "stop_signal_sent": machine.get("stop_signal_sent"),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError as failed:
            record["unresolved_host_record"] = None
            record["unresolved_host_record_error"] = f"{type(failed).__name__}: {failed}"
            return
        record["unresolved_host_record"] = str(path)

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

        Before any of that, the host itself is checked. An earlier call in this
        session may have finished while leaving a machine running, and the next
        boot would then be placed on a host this run no longer has to itself.
        That is refused here rather than launched.
        """
        left_running = self._a_machine_this_session_left_running()
        if left_running is not None:
            self.boots.append(
                {
                    "call": len(self.boots),
                    "refused_before_launch": (
                        "call {} left a machine running on this host ({}), so "
                        "the host is not free for another boot".format(
                            left_running.get("call"),
                            (left_running.get("machine") or {}).get("outcome"),
                        )
                    ),
                    "booted": False,
                    "host_left_running_by_call": left_running.get("call"),
                }
            )
            return {"ok": False, "error_type": "compute_cleanup_failed"}

        unresolved = self._a_host_left_unresolved_on_disk()
        if unresolved is not None:
            self.boots.append(
                {
                    "call": len(self.boots),
                    "refused_before_launch": (
                        "task {} left a machine running on this host ({}) and "
                        "no cleanup has been recorded since, so the host is "
                        "not free for another boot".format(
                            unresolved.get("task_id"),
                            unresolved.get("outcome")
                            or unresolved.get("unreadable")
                            or "no outcome recorded",
                        )
                    ),
                    "booted": False,
                    "host_left_unresolved_by_task": unresolved.get("task_id"),
                    "host_left_unresolved_record": dict(unresolved),
                }
            )
            return {"ok": False, "error_type": "compute_cleanup_failed"}

        try:
            descriptor = self._open_directory(str(arguments.get("cwd", "")))
        except (FileNotFoundError, NotADirectoryError, ValueError, OSError):
            # Recorded, though nothing was launched and nothing was spent. This
            # is the model asking the isolation to run something, and a refusal
            # ends its attempt — so a task can reach its end having called
            # `exec_run` and left no trace of having called it. A run record
            # reading that list back would report a model that never asked,
            # which is the opposite fault from a backend that could not answer
            # and wants the opposite repair.
            self.boots.append(
                {
                    "call": len(self.boots),
                    "refused_before_launch": (
                        "cwd {!r} is not a directory on the host".format(
                            arguments.get("cwd", "")
                        )
                    ),
                    "booted": False,
                }
            )
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
            gave_up = {
                "call": len(self.boots),
                "booted": False,
                "launcher_error": f"{type(failure).__name__}: {failure}",
                "deadline": deadline,
            }
            # A boot given up on after the images were placed carries two
            # outcomes, and they answer different questions. What went wrong
            # with the run is one; whether this run's jail and its process went
            # down with it is the other. Flattened into the single sentence
            # above they read as one event, and a launch that failed leaving a
            # chroot on the disk becomes indistinguishable from a launch that
            # failed and cleaned up after itself. So both are kept, under their
            # own keys, whenever the failure carries them. Each is kept on its
            # own terms, so that a failure carrying one and not the other keeps
            # the one it has — and so that what is written down below and what
            # is decided below rest on the same object.
            teardown = getattr(failure, "teardown", None)
            original = getattr(failure, "original", None)
            if original is not None:
                gave_up["original_error"] = f"{type(original).__name__}: {original}"
            if teardown is not None:
                gave_up["teardown"] = dict(teardown)
            # And the third question the two above do not answer: whether a
            # machine of ours may still be up. Until this was asked here, a
            # launch that came apart produced no `machine` key at all, so
            # `host_left_running` was never computed on this path and neither
            # guard could see it — the one failure most likely to leave a guest
            # behind was the one failure that never wrote it down.
            machine = _what_a_failed_launch_left_behind(teardown)
            gave_up["machine"] = machine
            if machine.get("host_left_running") is True:
                # Written before the record is filed and before the error goes
                # back, for the reason the ordinary path gives: a process that
                # ends here still leaves the next one something to find. The
                # error itself is unchanged, and so is what this call already
                # cost.
                self._write_down_the_unresolved_host(gave_up)
            self.boots.append(gave_up)
            return {"ok": False, "error_type": "compute_backend_error"}

        reading = read_the_boot(boot, deadline=deadline)
        machine = _how_the_machine_ended(boot)
        record = {
            "call": len(self.boots),
            "booted": True,
            "boot_outcome": reading["boot_outcome"],
            "deadline": reading["deadline"],
            "truncated": reading["truncated"],
            "grounds": reading["grounds"],
            "result": reading["result"],
            "image": self.image.as_record(),
            "machine": machine,
        }
        record["output_files"] = self._keep_the_output(
            record["call"], reading, machine=machine
        )
        if machine.get("host_left_running") is True:
            # Written before the record is filed and before the result goes
            # back, so that a process that ends here — a crash, a cancel, the
            # wall clock running out — still leaves the next one something to
            # find. The result itself is unchanged: the command did what it
            # did, and the task keeps it.
            self._write_down_the_unresolved_host(record)
        self.boots.append(record)
        return reading["result"]

    def _keep_the_output(
        self, call: int, reading: Mapping[str, Any], *, machine: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Put the streams where the model can ask for them.

        If this fails — a full workspace, most likely — the command's own
        answer is still the answer. Losing the returncode because its transcript
        would not fit would turn a finished piece of work into a failure, so the
        loss is recorded and the result is left alone. The model is told nothing
        about it directly, which is honest: from where it sits the files simply
        are not there, and reading a file that is not there already has a
        meaning.

        ``meta.json`` carries the machine's state as well as the command's
        result, and the two are not the same answer. The streams and the
        returncode beside them were read off a work disk that may have had a
        live writer attached; a transcript that records only "returncode 0"
        cannot be told apart afterwards from one taken off a machine that shut
        down cleanly. Whoever reads these files later is the last person in a
        position to notice, so the evidence goes where they are.
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
                    "host_left_running": machine.get("host_left_running"),
                    "copy_integrity": machine.get("copy_integrity"),
                    "copy_integrity_because": machine.get("copy_integrity_because"),
                    "guest_confirmed_stopped": machine.get("guest_confirmed_stopped"),
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
