"""The backend that boots: what it claims, what it refuses, what one call costs.

Three things are being checked here and they are not the same kind of thing.

The first is **what it says it is**. A backend's identity is what the run record
is built on, so a backend that describes itself wrongly poisons everything
downstream of it quietly. The tests below insist the description is derived from
the image and the manifest, and that with no manifest it declines to describe
itself at all.

The second is **that the fixture underneath it stays underneath it**. This class
inherits from a deliberately non-production backend for its workspace path
safety. Everything else about the parent is a thing that must not be reachable,
and the way that is kept true over time is a test that pins the inherited
surface — so that a convenience added to the fixture later cannot become a
production capability by accident.

The third is **that one call is one machine**. No microVM boots in these tests;
the launcher is a callable the backend is handed, exactly as stage C's attacks
were injected. What is being proven is the part around the boot: that a bad path
never spends one, that a refusal never spends one, and that when a machine does
come back the workspace is left holding what it produced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.agentic_v2_contract import (
    FOUNDATION_BACKEND_ID,
    TOOL_CONTRACT_VERSION,
    AgenticV2Profile,
)
from core.agentic_v2_exec_boot import EXEC_RECORD_DIR, INTERPRETERS
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_microvm import REQUIRED_MICROVM_POLICY
from core.agentic_v2_microvm_backend import (
    BACKEND_ID,
    MANIFEST_COMMAND_FOR_INTERPRETER,
    AgenticV2MicroVMBackend,
    GuestImage,
)
from core.agentic_v2_substrate import AgenticV2SubstrateManifest


MANIFEST_PATH = Path("sandbox/agentic_v2_capabilities.json")

AN_IMAGE = GuestImage(
    reference="ghcr.io/hyeonsangjeon/gdpval-sandbox",
    digest="sha256:ee6ef798631d3c3aeaed28658c640e6f5d021677449852bf2e1f18be5bd24edb",
    kernel_sha256="a" * 64,
    rootfs_sha256="b" * 64,
)

ANOTHER_IMAGE = GuestImage(
    reference=AN_IMAGE.reference,
    digest=AN_IMAGE.digest,
    kernel_sha256="a" * 64,
    rootfs_sha256="c" * 64,
)


class Launcher:
    """Stands in for the thing that would boot a machine, and remembers.

    ``writes`` lets a call leave files behind in the workspace, which is what a
    real session does when it reads the changed work disk back out afterwards.
    """

    def __init__(self, *, outcome="booted", status=0, stdout="", stderr="", writes=None):
        self.outcome = outcome
        self.status = status
        self.stdout = stdout
        self.stderr = stderr
        self.writes = dict(writes or {})
        self.calls: list[dict] = []

    def __call__(self, *, command_sh, workspace, deadline_seconds):
        self.calls.append(
            {
                "command_sh": command_sh,
                "workspace": workspace,
                "deadline_seconds": deadline_seconds,
            }
        )
        for relative, content in self.writes.items():
            target = Path(workspace) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return {
            "outcome": self.outcome,
            "command_exit_status": self.status,
            "results": {"/out/stdout": self.stdout, "/out/stderr": self.stderr},
        }


def _manifest() -> AgenticV2SubstrateManifest:
    return AgenticV2SubstrateManifest.load(MANIFEST_PATH)


def _backend(tmp_path, *, launcher=None, manifest="real", image=AN_IMAGE, **kwargs):
    return AgenticV2MicroVMBackend(
        root=tmp_path / "session",
        profile=AgenticV2Profile(
            tool_contract_version=TOOL_CONTRACT_VERSION,
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        ),
        image=image,
        boot_one_command=launcher or Launcher(),
        substrate_manifest=_manifest() if manifest == "real" else manifest,
        **kwargs,
    )


def _ok(arguments=None):
    base = {"argv": ["true"], "cwd": ".", "timeout_seconds": 60}
    base.update(arguments or {})
    return base


class TestWhatItSaysItIs:
    def test_with_no_manifest_it_declines_to_describe_itself(self, tmp_path):
        # The tempting alternative is a placeholder digest, which would put a
        # hash into the run record that no file on disk corresponds to.
        backend = _backend(tmp_path, manifest=None)
        started = backend.start(30.0)
        assert started == {"ok": False, "error_type": "substrate_manifest_missing"}
        backend.close()

    def test_it_never_answers_with_the_fixtures_identity(self, tmp_path):
        backend = _backend(tmp_path)
        identity = backend.start(30.0)["data"]["backend_identity"]
        assert identity["backend_id"] == BACKEND_ID
        assert identity["backend_id"] != FOUNDATION_BACKEND_ID
        backend.close()

    def test_the_runner_still_refuses_this_backend_and_that_is_the_point(
        self, tmp_path
    ):
        # core/agentic_v2_runner.py compares the startup identity against the
        # foundation fixture's and fails anything else. This asserts the guard
        # is untouched by this module: opening it is its own change, with its
        # own review, once the pieces under it have evidence.
        backend = _backend(tmp_path)
        identity = backend.start(30.0)["data"]["backend_identity"]
        assert identity["backend_id"] != FOUNDATION_BACKEND_ID
        backend.close()

    def test_a_different_root_filesystem_is_a_different_backend(self, tmp_path):
        one = _backend(tmp_path / "one", image=AN_IMAGE)
        two = _backend(tmp_path / "two", image=ANOTHER_IMAGE)
        assert (
            one.backend_identity()["implementation_sha256"]
            != two.backend_identity()["implementation_sha256"]
        )
        one.close()
        two.close()

    def test_pinning_a_different_python_binary_is_a_different_backend(self, tmp_path):
        # Because it is: the same request runs a different program.
        one = _backend(tmp_path / "one")
        two = _backend(
            tmp_path / "two",
            interpreter_binaries={**INTERPRETERS, "python": "python"},
        )
        assert (
            one.backend_identity()["implementation_sha256"]
            != two.backend_identity()["implementation_sha256"]
        )
        one.close()
        two.close()

    def test_foundation_only_is_read_from_the_manifest_not_asserted_here(
        self, tmp_path
    ):
        backend = _backend(tmp_path)
        assert (
            backend.backend_identity()["foundation_only"]
            is backend.manifest.document["foundation_only"]
        )
        backend.close()

    def test_the_three_startup_digests_are_shaped_like_digests(self, tmp_path):
        # The runner checks all three with is_sha256 and reports
        # substrate_manifest_missing when any of them is not one.
        backend = _backend(tmp_path)
        data = backend.start(30.0)["data"]
        for value in (
            data["substrate_manifest"]["sha256"],
            data["package_snapshot_sha256"],
            data["browser_build_sha256"],
        ):
            assert isinstance(value, str) and len(value) == 64
            assert set(value) <= set("0123456789abcdef")
        backend.close()

    def test_the_browser_digest_follows_the_image_it_came_from(self, tmp_path):
        one = _backend(tmp_path / "one", image=AN_IMAGE)
        two = _backend(
            tmp_path / "two",
            image=GuestImage(
                reference=AN_IMAGE.reference,
                digest="sha256:" + "d" * 64,
                kernel_sha256=AN_IMAGE.kernel_sha256,
                rootfs_sha256=AN_IMAGE.rootfs_sha256,
            ),
        )
        assert one.browser_build_sha256() != two.browser_build_sha256()
        one.close()
        two.close()


class TestWhatItAdvertisesComesFromTheManifest:
    def test_the_commands_are_the_manifests_commands(self, tmp_path):
        backend = _backend(tmp_path)
        declared = sorted(
            item["name"] for item in backend.manifest.document["commands"]
        )
        assert backend._capabilities()["commands"] == declared
        assert "fixture-upper" not in declared
        backend.close()

    def test_a_runtime_is_advertised_only_if_the_manifest_declares_it(self, tmp_path):
        backend = _backend(tmp_path)
        declared = {item["name"] for item in backend.manifest.document["commands"]}
        expected = sorted(
            name
            for name, command in MANIFEST_COMMAND_FOR_INTERPRETER.items()
            if command in declared
        )
        assert backend._capabilities()["runtimes"] == expected
        assert expected, "the manifest declares none of the four interpreters"
        backend.close()

    def test_no_packages_are_advertised_because_none_can_be_had(self, tmp_path):
        backend = _backend(tmp_path)
        assert backend._capabilities()["packages"] == []
        backend.close()

    def test_the_budgets_are_the_caps_this_backend_was_given(self, tmp_path):
        backend = _backend(tmp_path, budget_caps={"tool_calls": 8, "wall_seconds": 300})
        assert backend._capabilities()["budgets"] == [
            "tool_calls=8",
            "wall_seconds=300",
        ]
        backend.close()

    def test_what_start_reports_is_what_expected_capabilities_returns(self, tmp_path):
        # The runner compares the two and fails startup if they differ, so a
        # backend whose two answers drift never starts at all.
        backend = _backend(tmp_path)
        assert backend.start(30.0)["data"]["capabilities"] == dict(
            backend.expected_capabilities()
        )
        backend.close()


class TestTheFixtureUnderneathStaysUnderneath:
    def test_the_inherited_surface_is_exactly_this_and_no_more(self, tmp_path):
        # If this fails because the fixture grew a method, that is the test
        # doing its job: decide deliberately whether the new thing should be
        # reachable in production, then change this list.
        expected = {
            "backend_identity",
            "best_result",
            "browser_build_sha256",
            "browser_run",
            "capabilities_query",
            "close",
            "environment_activate",
            "environment_resolve",
            "exec_run",
            "expected_capabilities",
            "finalize",
            "initial_workspace_declaration",
            "package_snapshot_sha256",
            "start",
            "state_sha256",
            "verify_public",
            "workspace_apply",
            "workspace_state_sha256",
        }
        public = {
            name
            for name in dir(AgenticV2MicroVMBackend)
            if not name.startswith("_") and callable(
                getattr(AgenticV2MicroVMBackend, name, None)
            )
        }
        assert public == expected

    def test_every_fixture_method_is_either_inherited_on_purpose_or_overridden(self):
        fixture = {
            name for name in dir(AgenticV2FixtureBackend) if not name.startswith("_")
        }
        mine = set(vars(AgenticV2MicroVMBackend))
        inherited_on_purpose = {
            "best_result",
            "capabilities_query",
            "close",
            "expected_capabilities",
            "finalize",
            # Reads the same host-side tree `workspace_apply` writes to and
            # `_workspace_snapshot` walks, both of which are inherited here for
            # the same reason: the machine gets that tree shared into it, so
            # what the workspace held at startup is the same question on either
            # backend and has the same answer. An override would be a second
            # walk of one directory.
            "initial_workspace_declaration",
            "verify_public",
            "workspace_apply",
            "workspace_state_sha256",
        }
        assert fixture - mine - {"closed"} == inherited_on_purpose

    def test_the_fixtures_own_command_does_nothing_here(self, tmp_path):
        launcher = Launcher(status=0)
        backend = _backend(tmp_path, launcher=launcher)
        backend.workspace_apply(
            {"operation": "write", "path": "a.txt", "content": "quiet"}
        )
        result = backend.exec_run(_ok({"argv": ["fixture-upper", "a.txt", "b.txt"]}))
        # It is not special-cased: it becomes an ordinary command in a machine,
        # which is where "fixture-upper: not found" belongs.
        assert launcher.calls, "the request never reached the launcher"
        assert "fixture-upper" in launcher.calls[0]["command_sh"]
        assert result["ok"] is True
        backend.close()

    def test_the_demonstration_package_catalogue_is_emptied(self, tmp_path):
        backend = _backend(tmp_path)
        assert dict(backend.package_catalog) == {}
        backend.close()


class TestWhatItCannotDoItSaysItCannotDo:
    def test_resolving_a_requirement_is_refused(self, tmp_path):
        backend = _backend(tmp_path)
        assert backend.environment_resolve(
            {"ecosystem": "python", "requirements": ["numpy"]}
        ) == {"ok": False, "error_type": "capability_unavailable"}
        backend.close()

    def test_activating_a_lock_is_refused(self, tmp_path):
        backend = _backend(tmp_path)
        assert backend.environment_activate({"lock_sha256": "0" * 64})["ok"] is False
        backend.close()

    @pytest.mark.parametrize("operation", ["search", "open_url", "open_local"])
    def test_the_browser_is_refused_including_the_local_one(self, tmp_path, operation):
        # open_local needs no network and the image has chromium, so this is a
        # missing harness rather than a closed door. Hashing the file the model
        # already has would read as a browser having run, which is worse than
        # an error.
        backend = _backend(tmp_path)
        backend.workspace_apply(
            {"operation": "write", "path": "page.html", "content": "<p>hi</p>"}
        )
        assert backend.browser_run({"operation": operation, "path": "page.html"}) == {
            "ok": False,
            "error_type": "capability_unavailable",
        }
        backend.close()


class TestOneCallIsOneMachine:
    def test_a_command_that_ran_comes_back_as_its_returncode(self, tmp_path):
        backend = _backend(tmp_path, launcher=Launcher(status=7))
        assert backend.exec_run(_ok()) == {
            "ok": True,
            "error_type": None,
            "data": {"returncode": 7},
        }
        backend.close()

    def test_the_launcher_is_given_the_deadline_that_was_applied(self, tmp_path):
        launcher = Launcher()
        backend = _backend(tmp_path, launcher=launcher)
        backend.exec_run(_ok({"timeout_seconds": 2700}))
        assert launcher.calls[0]["deadline_seconds"] == REQUIRED_MICROVM_POLICY[
            "wall_clock_seconds"
        ]
        assert backend.boots[0]["deadline"]["requested_seconds"] == 2700
        assert backend.boots[0]["deadline"]["capped_by_the_policy"] is True
        backend.close()

    def test_a_directory_that_is_not_there_never_spends_a_boot(self, tmp_path):
        launcher = Launcher()
        backend = _backend(tmp_path, launcher=launcher)
        assert backend.exec_run(_ok({"cwd": "nowhere"})) == {
            "ok": False,
            "error_type": "path_not_directory",
        }
        assert launcher.calls == []
        backend.close()

    def test_a_request_that_cannot_be_written_never_spends_a_boot(self, tmp_path):
        launcher = Launcher()
        backend = _backend(tmp_path, launcher=launcher)
        result = backend.exec_run(
            {"interpreter": "perl", "script": "x", "cwd": ".", "timeout_seconds": 60}
        )
        assert result == {"ok": False, "error_type": "invalid_arguments"}
        assert launcher.calls == []
        assert backend.boots[0]["booted"] is False
        assert "perl" in backend.boots[0]["refused_before_launch"]
        backend.close()

    def test_a_launcher_that_comes_apart_is_a_backend_error_not_a_returncode(
        self, tmp_path
    ):
        def explode(**_):
            raise RuntimeError("the jailer is not installed")

        backend = _backend(tmp_path, launcher=explode)
        assert backend.exec_run(_ok()) == {
            "ok": False,
            "error_type": "compute_backend_error",
        }
        assert "jailer" in backend.boots[0]["launcher_error"]
        backend.close()

    def test_the_workspace_is_the_same_directory_between_calls(self, tmp_path):
        launcher = Launcher(writes={"made-inside": "by the machine"})
        backend = _backend(tmp_path, launcher=launcher)
        backend.exec_run(_ok())
        assert launcher.calls[0]["workspace"] == backend.work
        # The second call sees what the first one left, which is the whole
        # reason the workspace lives on the host rather than in the machine.
        assert backend.workspace_apply(
            {"operation": "read", "path": "made-inside"}
        )["data"]["content"] == "by the machine"
        backend.close()


class TestAHostThisRunLeftRunningIsNotBootedOnAgain:
    """The ending evidence of one call has to reach the next one.

    ``the_host_was_left_running`` decided this per boot and
    ``_how_the_machine_ended`` filed the answer in every record, and until this
    was added nothing read either. A call that leaked a machine was written
    down and then the next call booted onto the same host anyway.

    The two questions are different. Whether the command worked is about the
    command; whether the host is free afterwards is about the host. Folding
    them together is how a leaked machine reaches the model as an ordinary
    success — and, worse, how the task after it gets measured on a host this
    run no longer has to itself.
    """

    def test_a_leaked_machine_refuses_the_next_call_before_it_costs_a_boot(
        self, tmp_path
    ):
        launcher = Launcher(outcome="overran_and_did_not_stop")
        backend = _backend(tmp_path, launcher=launcher)
        backend.exec_run(_ok())
        assert backend.boots[0]["machine"]["host_left_running"] is True

        assert backend.exec_run(_ok()) == {
            "ok": False,
            "error_type": "compute_cleanup_failed",
        }
        # Refused before launch, so it costs nothing: the launcher was called
        # once, for the boot that leaked, and not again.
        assert len(launcher.calls) == 1
        backend.close()

    def test_the_refusal_names_the_call_that_left_the_machine(self, tmp_path):
        backend = _backend(
            tmp_path, launcher=Launcher(outcome="overran_and_was_left_alone")
        )
        backend.exec_run(_ok())
        backend.exec_run(_ok())
        refusal = backend.boots[1]
        assert refusal["booted"] is False
        assert refusal["host_left_running_by_call"] == 0
        # Which call, and which ending — without those the record says only
        # that something was refused, and the reason has to be guessed later.
        assert "call 0" in refusal["refused_before_launch"]
        assert "overran_and_was_left_alone" in refusal["refused_before_launch"]
        backend.close()

    def test_the_error_type_is_one_the_run_driver_already_stops_on(self, tmp_path):
        # Not a new error type. ``compute_cleanup_failed`` is already mapped to
        # a stop reason by the conversation and already stops the whole run at
        # the driver's rule 7, precisely because the next task would otherwise
        # inherit a guest that was not cleaned up. That is this situation.
        from core.agentic_v2_contract import ERROR_TYPES
        from core.agentic_v2_conversation import _ENDS_THE_RUN

        assert "compute_cleanup_failed" in ERROR_TYPES
        assert "compute_cleanup_failed" in _ENDS_THE_RUN

    def test_a_host_that_was_given_back_does_not_refuse_anything(self, tmp_path):
        # The control. A guard that refuses everything would pass the three
        # tests above and be worse than no guard at all, so the ordinary case
        # is asserted here: two clean calls, two boots, nothing refused.
        launcher = Launcher()
        backend = _backend(tmp_path, launcher=launcher)
        assert backend.exec_run(_ok())["ok"] is True
        assert backend.boots[0]["machine"]["host_left_running"] is False
        assert backend.exec_run(_ok())["ok"] is True
        assert len(launcher.calls) == 2
        assert all(record["booted"] is True for record in backend.boots)
        backend.close()


class TestTheOutputGoesWhereTheModelCanReadIt:
    def test_what_the_command_printed_lands_in_the_workspace(self, tmp_path):
        backend = _backend(tmp_path, launcher=Launcher(stdout="the answer is 4"))
        backend.exec_run(_ok())
        read = backend.workspace_apply(
            {"operation": "read", "path": f"{EXEC_RECORD_DIR}/0000/stdout"}
        )
        assert read["ok"] is True
        assert read["data"]["content"] == "the answer is 4"
        backend.close()

    def test_each_call_gets_its_own_place_and_does_not_overwrite_the_last(
        self, tmp_path
    ):
        backend = _backend(tmp_path, launcher=Launcher(stdout="first"))
        backend.exec_run(_ok())
        backend._boot_one_command = Launcher(stdout="second")
        backend.exec_run(_ok())
        first = backend.workspace_apply(
            {"operation": "read", "path": f"{EXEC_RECORD_DIR}/0000/stdout"}
        )
        second = backend.workspace_apply(
            {"operation": "read", "path": f"{EXEC_RECORD_DIR}/0001/stdout"}
        )
        assert (first["data"]["content"], second["data"]["content"]) == (
            "first",
            "second",
        )
        backend.close()

    def test_the_record_beside_the_output_says_how_the_call_ended(self, tmp_path):
        backend = _backend(
            tmp_path, launcher=Launcher(outcome="stopped_by_the_deadline", status=None)
        )
        backend.exec_run(_ok({"timeout_seconds": 30}))
        meta = json.loads(
            backend.workspace_apply(
                {"operation": "read", "path": f"{EXEC_RECORD_DIR}/0000/meta.json"}
            )["data"]["content"]
        )
        assert meta["result"]["error_type"] == "cancelled"
        assert meta["deadline"]["applied_seconds"] == 30
        assert meta["grounds"].strip()
        backend.close()

    def test_a_machine_that_wrote_nothing_leaves_a_record_saying_so(self, tmp_path):
        backend = _backend(
            tmp_path,
            launcher=Launcher(outcome="booted_but_wrote_nothing", status=None),
        )
        result = backend.exec_run(_ok())
        assert result["error_type"] == "compute_backend_error"
        assert result["data"] == {}
        assert backend.boots[0]["boot_outcome"] == "booted_but_wrote_nothing"
        backend.close()

    def test_the_boot_record_names_the_image_the_answer_came_from(self, tmp_path):
        backend = _backend(tmp_path)
        backend.exec_run(_ok())
        assert backend.boots[0]["image"] == AN_IMAGE.as_record()
        backend.close()

    def test_output_that_cannot_be_kept_does_not_take_the_answer_with_it(
        self, tmp_path
    ):
        backend = _backend(tmp_path, launcher=Launcher(status=3, stdout="printed"))

        def refuse(*_args, **_kwargs):
            raise OSError("workspace is full")

        backend._write_bytes = refuse
        result = backend.exec_run(_ok())
        assert result == {"ok": True, "error_type": None, "data": {"returncode": 3}}
        assert backend.boots[0]["output_files"]["kept"] == []
        assert "full" in backend.boots[0]["output_files"]["not_kept"]
        backend.close()


class TestStateCoversWhatWouldRunInIt:
    def test_writing_a_file_changes_the_state(self, tmp_path):
        backend = _backend(tmp_path)
        before = backend.state_sha256()
        backend.workspace_apply(
            {"operation": "write", "path": "note.txt", "content": "x"}
        )
        assert backend.state_sha256() != before
        backend.close()

    def test_the_same_workspace_under_a_different_guest_is_not_the_same_state(
        self, tmp_path
    ):
        one = _backend(tmp_path / "one", image=AN_IMAGE)
        two = _backend(tmp_path / "two", image=ANOTHER_IMAGE)
        for backend in (one, two):
            backend.workspace_apply(
                {"operation": "write", "path": "note.txt", "content": "identical"}
            )
        assert one.workspace_state_sha256() == two.workspace_state_sha256()
        assert one.state_sha256() != two.state_sha256()
        one.close()
        two.close()


class TestTheRealPathWhenTheBootComesApart:
    """The whole chain, from ``exec_run`` to the jail on the disk.

    Every other test in this file hands the backend a stand-in launcher, which
    is right for what those check and is exactly why they could not have caught
    the thing this one does. A stand-in never places an image, so it never
    leaves one behind; the defect lived in the seam between the backend, the
    per-call machine and the launcher, and a test that replaces the middle of
    that seam cannot see it.

    So here the chain is real: ``AgenticV2MicroVMBackend.exec_run`` ->
    ``OneCallMachine.__call__`` -> a genuine work disk built by ``mke2fs`` ->
    the real plan builder -> ``first_boot`` -> ``place_the_images``. Two host
    facilities are stood in for, and neither is code under test: running the
    jailer, which is the failure being injected, and ``os.chown``, which needs
    root and this box does not have. ``chroot_base`` is redirected into the
    temp directory through ``build_plan``, the field that exists for it, rather
    than writing under /srv on a developer's machine.

    No machine boots. This box runs kernel 3.10 and cannot.
    """

    def test_a_boot_that_comes_apart_takes_its_jail_with_it(
        self, tmp_path, monkeypatch
    ):
        import functools
        import os as os_module

        from core.agentic_v2_microvm_launch import build_launch_plan
        from core.agentic_v2_one_call_machine import OneCallMachine

        host = tmp_path / "host"
        host.mkdir()
        for name in ("firecracker", "vmlinux", "rootfs.ext4"):
            image = host / name
            image.write_bytes(b"not really an image, but a readable file")
            image.chmod(0o755)
        jail_base = tmp_path / "jail"

        # Root, which this box is not. The plan chowns the placed images to the
        # account the jailer drops to; whether that call happens is C1's test,
        # not this one's.
        monkeypatch.setattr(os_module, "chown", lambda *a, **k: None)

        # The injection, and the observation, in one place. FileNotFoundError
        # out of the jailer is not hypothetical -- it is what a host without
        # firecracker installed does, which is every host in this repository
        # today. What it sees is recorded so that the assertion about the jail
        # being gone afterwards cannot pass by it never having been there.
        seen: dict = {}

        def no_jailer_on_this_host(argv, timeout=300.0):
            chroot = jail_base / "firecracker"
            seen["jails"] = sorted(p.name for p in chroot.iterdir()) if chroot.exists() else []
            seen["work_disk_inside"] = sorted(
                str(p.relative_to(jail_base)) for p in jail_base.rglob("work.ext4")
            )
            raise FileNotFoundError(2, "No such file or directory", argv[0])

        monkeypatch.setattr(
            "core.agentic_v2_first_boot._run", no_jailer_on_this_host
        )

        machine = OneCallMachine(
            kernel=host / "vmlinux",
            rootfs=host / "rootfs.ext4",
            firecracker_binary=host / "firecracker",
            uid=997,
            gid=997,
            vcpu_count=1,
            cgroup_version=2,
            scratch=tmp_path / "scratch",
            build_plan=functools.partial(build_launch_plan, chroot_base=jail_base),
        )
        backend = _backend(tmp_path, launcher=machine)
        try:
            result = backend.exec_run(_ok())

            # The model is told the backend broke, not that its command
            # returned something.
            assert result == {"ok": False, "error_type": "compute_backend_error"}

            # The injection really did land after placement, so the two
            # assertions below are about something that existed.
            assert seen["jails"], "the jail was never built; nothing was placed"
            assert seen["work_disk_inside"], "no work disk reached the jail"

            record = backend.boots[0]
            assert record["booted"] is False

            # Two failures, two records. The run failed because the jailer is
            # not installed; the cleanup that followed is a separate outcome
            # with its own answer. Read as one sentence, a launch that failed
            # and left a chroot holding the work image is indistinguishable
            # from one that failed and cleaned up after itself.
            assert "FileNotFoundError" in record["original_error"]
            assert "BootAbandoned" in record["launcher_error"]
            teardown = record["teardown"]
            assert teardown["after_a_failure"] is True
            assert teardown["all_gone"] is True
            assert teardown["failures"] == []

            # The guest's disk is kept before the jail goes, so a failed call
            # is not also a lost workspace.
            salvaged = teardown["salvaged"]
            assert salvaged["returned_copy"] is not None
            assert Path(salvaged["returned_copy"]).exists()

            # And the jail itself is off the disk. What is left is the jailer's
            # per-machine directory, empty: the plan names the chroot in
            # `destroy_after_the_run` and names nothing else, and removing a
            # named path's parent is exactly how one run on a shared host
            # deletes another run's work. An empty directory costs an inode;
            # the rule it would cost is worth more than that.
            assert not (jail_base / "firecracker" / seen["jails"][0] / "root").exists()
            assert [p for p in jail_base.rglob("*") if p.is_file()] == []
        finally:
            backend.close()
