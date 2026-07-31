from __future__ import annotations

import inspect
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import venv

import pytest

import sandbox.v2.build_candidate as builder
import sandbox.v2.verify_candidate as verifier
from core.agentic_v2_supply_chain import evidence_collection_allowed


_DISABLED_ENTRYPOINT_STDERR = (
    b'{"error":"agentic_v2_phase1b_candidate_not_activated",'
    b'"foundation_only":true,"production_activation":"disabled"}\n'
)


def _session():
    return verifier.VerificationSession("a" * 32)


def test_verification_sessions_are_explicit_and_independent(monkeypatch):
    first = verifier.VerificationSession("a" * 32)
    second = verifier.VerificationSession("b" * 32)
    monkeypatch.setattr(verifier.uuid, "uuid4", lambda: SimpleNamespace(hex="c" * 32))

    assert first.label_arguments() != second.label_arguments()
    assert first.container_name("evidence") != second.container_name("evidence")
    with pytest.raises(ValueError, match="session identity"):
        verifier.VerificationSession("missing")


def test_verify_candidate_requires_explicit_session_id(tmp_path):
    with pytest.raises(TypeError):
        verifier.verify_candidate(
            image="candidate:test",
            source_revision="a" * 40,
            oci_layout=tmp_path / "oci",
            output_directory=tmp_path / "evidence",
        )


def test_candidate_verifier_refuses_credential_environment(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "must-not-be-consumed")

    with pytest.raises(RuntimeError, match="credential-bearing"):
        verifier._require_no_credentials()


def test_containment_report_separates_collection_from_production(monkeypatch):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    checks["cpu_quota"] = False
    checks["pids_limit"] = False
    collection = {
        "cap_drop_all": True,
        "memory_limit": True,
        "network_none": True,
        "no_new_privileges": True,
        "non_root_uid": True,
        "read_only_rootfs": True,
    }
    monkeypatch.setattr(
        verifier.subprocess,
        "run", lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        verifier,
        "_docker_base_isolation_probe",
        lambda _image, *, session: (dict(checks), dict(collection)),
    )
    monkeypatch.setattr(
        verifier,
        "_docker_resource_limit_probe",
        lambda _image, *, name, arguments, session: False,
    )

    report = verifier._inspect_containment("candidate:test", session=_session())

    assert report["schema_version"] == "1.1"
    assert report["status"] == "failed"
    assert report["collection_status"] == "verified"
    assert report["checks"] == checks
    assert report["collection_checks"] == collection


def test_evidence_collection_allows_only_resource_limit_degradation():
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    checks["cpu_quota"] = False
    checks["pids_limit"] = False
    report = {
        "schema_version": "1.1",
        "status": "failed",
        "checks": checks,
        "required": sorted(checks),
        "collection_status": "verified",
        "collection_checks": {
            "cap_drop_all": True,
            "memory_limit": True,
            "network_none": True,
            "no_new_privileges": True,
            "non_root_uid": True,
            "read_only_rootfs": True,
        },
        "host_scope": "exact-docker-daemon",
    }
    report["report_sha256"] = verifier.canonical_sha256(report)

    assert evidence_collection_allowed(report) is True

    report["collection_checks"]["network_none"] = False
    report["collection_status"] = "failed"
    report_without_hash = dict(report)
    report_without_hash.pop("report_sha256")
    report["report_sha256"] = verifier.canonical_sha256(report_without_hash)
    assert evidence_collection_allowed(report) is False


def test_containment_probe_rejects_incomplete_runtime_observation(monkeypatch):
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier,
        "_docker_json",
        lambda _command: [{"Config": {}, "HostConfig": {}}],
    )
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=b'{"memory_limit":true}',
            stderr=b"",
        ),
    )

    checks, collection = verifier._docker_base_isolation_probe(
        "candidate:test", session=_session()
    )

    assert not any(checks.values())
    assert not any(collection.values())


def test_collection_checks_bind_host_config_and_runtime():
    runtime = {name: False for name in verifier._CONTAINMENT_CHECKS}
    runtime.update({
        "cap_drop_all": True,
        "memory_limit": True,
        "network_none": True,
        "no_new_privileges": True,
        "non_root_uid": True,
        "read_only_rootfs": True,
    })
    inspected = [{
        "Config": {"User": "65532:65532"},
        "HostConfig": {
            "CapDrop": ["ALL"],
            "Memory": 64 * 1024 * 1024,
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "SecurityOpt": ["no-new-privileges"],
        },
        "NetworkSettings": {
            "Networks": {
                "none": {
                    "Gateway": "",
                    "GlobalIPv6Address": "",
                    "IPAddress": "",
                    "IPv6Gateway": "",
                },
            },
        },
    }]

    assert all(
        verifier._collection_checks_from_inspect(inspected, runtime).values()
    )

    inspected[0]["HostConfig"]["NetworkMode"] = "bridge"
    assert verifier._collection_checks_from_inspect(
        inspected, runtime
    )["network_none"] is False


def test_containment_probe_uses_prctl_and_route_tables():
    assert "prctl(39, 0, 0, 0, 0) == 1" in verifier._CONTAINMENT_PROBE
    assert 'open("/proc/net/route"' in verifier._CONTAINMENT_PROBE
    assert 'open("/proc/net/ipv6_route"' in verifier._CONTAINMENT_PROBE


def test_containment_probe_requires_all_capability_sets():
    for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        assert name in verifier._CONTAINMENT_PROBE
    assert '"CapAmb" not in status' in verifier._CONTAINMENT_PROBE
    assert 'for name in ("CapInh", "CapPrm", "CapEff", "CapBnd")' in (
        verifier._CONTAINMENT_PROBE
    )


def test_resource_warning_overrides_forged_runtime_check(monkeypatch):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(checks).encode("utf-8"),
            stderr=b"WARNING: PIDs limit discarded",
        ),
    )

    assert verifier._docker_resource_limit_probe(
        "candidate:test",
        name="pids_limit",
        arguments=["--pids-limit", "16"],
        session=_session(),
    ) is False


def test_unknown_docker_warning_blocks_evidence_collection(monkeypatch):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(checks).encode("utf-8"),
            stderr=b"WARNING: capability option not supported",
        ),
    )

    assert verifier._docker_resource_limit_probe(
        "candidate:test",
        name="pids_limit",
        arguments=["--pids-limit", "16"],
        session=_session(),
    ) is False


def test_mixed_resource_and_unknown_warning_blocks_evidence_collection(monkeypatch):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(checks).encode("utf-8"),
            stderr=b"WARNING: capability option not supported; PIDs limit discarded",
        ),
    )

    assert verifier._docker_resource_limit_probe(
        "candidate:test",
        name="pids_limit",
        arguments=["--pids-limit", "16"],
        session=_session(),
    ) is False


def test_candidate_runs_use_predeclared_names_instead_of_cidfiles():
    run_source = inspect.getsource(verifier._run_image_json)
    isolation_source = inspect.getsource(verifier._docker_base_isolation_probe)
    resource_source = inspect.getsource(verifier._docker_resource_limit_probe)

    assert '"--name", container' in run_source
    assert '"--name", container' in isolation_source
    assert '"--name", container' in resource_source
    assert "cidfile" not in run_source
    assert "cidfile" not in isolation_source
    assert "cidfile" not in resource_source


def test_verifier_uses_inspected_image_id_for_candidate_operations():
    source = inspect.getsource(verifier.verify_candidate)

    assert "_verify_embedded_files(\n        image_id" in source
    assert source.count("_run_image_json(\n            image_id") == 3


def test_container_cleanup_accepts_confirmed_absence(monkeypatch):
    container = "a" * 64
    results = iter([
        SimpleNamespace(returncode=1, stderr=b"already absent"),
        SimpleNamespace(
            returncode=1,
            stderr=f"Error: No such object: {container}".encode("utf-8"),
        ),
    ])
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: next(results),
    )

    verifier._remove_container(container)


def test_container_cleanup_rejects_remaining_container(monkeypatch):
    results = iter([
        SimpleNamespace(returncode=0, stderr=b""),
        SimpleNamespace(returncode=0, stderr=b""),
    ])
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: next(results),
    )

    with pytest.raises(RuntimeError, match="did not remove"):
        verifier._remove_container("a" * 64)


def test_container_cleanup_rejects_ambiguous_daemon_failure(monkeypatch):
    results = iter([
        SimpleNamespace(returncode=1, stderr=b"daemon unavailable"),
        SimpleNamespace(returncode=1, stderr=b"connection refused"),
    ])
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: next(results),
    )

    with pytest.raises(RuntimeError, match="could not be verified"):
        verifier._remove_container("a" * 64)


def test_container_cleanup_rejects_wrong_object_name(monkeypatch):
    results = iter([
        SimpleNamespace(returncode=1, stderr=b"already absent"),
        SimpleNamespace(returncode=1, stderr=b"Error: No such object: other"),
    ])
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: next(results),
    )

    with pytest.raises(RuntimeError, match="could not be verified"):
        verifier._remove_container("a" * 64)


@pytest.mark.parametrize(
    "message",
    [
        "ERROR: No such object: {name}",
        "Error: No such object:{name}",
        "Error: No such object: {upper_name}",
        "Error: No such object: {name}\nadditional error",
        "Error: No such object: {name} trailing",
    ],
)
def test_container_absence_requires_exact_message(message):
    container = "gdpval-agentic-v2-evidence-abcdef"
    rendered = message.format(
        name=container,
        upper_name=container.upper(),
    ).encode("utf-8")

    assert verifier._container_absence_confirmed(rendered, container) is False


@pytest.mark.parametrize(
    "message",
    [
        "Error: No such object: {name}",
        "Error: No such container: {name}\n",
        "Error response from daemon: No such object: {name}",
        "Error response from daemon: No such container: {name}\n",
    ],
)
def test_container_absence_accepts_only_known_exact_messages(message):
    container = "gdpval-agentic-v2-evidence-abcdef"
    rendered = message.format(name=container).encode("utf-8")

    assert verifier._container_absence_confirmed(rendered, container) is True


def test_container_cleanup_inspects_after_remove_timeout(monkeypatch):
    container = "a" * 64
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[2] == "rm":
            raise verifier.subprocess.TimeoutExpired(command, 60)
        return SimpleNamespace(
            returncode=1,
            stderr=f"Error: No such object: {container}".encode("utf-8"),
        )

    monkeypatch.setattr(verifier, "_run_bounded_command", run)

    verifier._remove_container(container)

    assert calls[-1][:3] == [verifier._TRUSTED_DOCKER, "container", "inspect"]


def test_container_cleanup_inspects_after_remove_output_overflow(monkeypatch):
    container = "a" * 64
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[2] == "rm":
            raise RuntimeError("candidate stderr exceeds size limit")
        return SimpleNamespace(
            returncode=1,
            stdout=b"",
            stderr=f"Error: No such object: {container}".encode("utf-8"),
        )

    monkeypatch.setattr(verifier, "_run_bounded_command", run)

    verifier._remove_container(container)

    assert calls[-1][:3] == [verifier._TRUSTED_DOCKER, "container", "inspect"]


def test_verifier_disabled_entrypoint_cleans_up_on_timeout(monkeypatch):
    cleaned = []
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda command, **kwargs: (_ for _ in ()).throw(
            verifier.subprocess.TimeoutExpired(command, 30)
        ),
    )
    monkeypatch.setattr(
        verifier,
        "_remove_container",
        lambda container: cleaned.append(container),
    )

    with pytest.raises(verifier.subprocess.TimeoutExpired):
        verifier._verify_disabled_entrypoint(
            "sha256:" + "a" * 64,
            containment_checks={name: False for name in verifier._CONTAINMENT_CHECKS},
            session=_session(),
        )

    assert len(cleaned) == 1
    assert cleaned[0].startswith("gdpval-agentic-v2-disabled-")


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr"),
    [
        (0, b"", _DISABLED_ENTRYPOINT_STDERR),
        (78, b"unexpected", _DISABLED_ENTRYPOINT_STDERR),
        (78, b"", b"prefix\n" + _DISABLED_ENTRYPOINT_STDERR),
        (78, b"", _DISABLED_ENTRYPOINT_STDERR + b"suffix\n"),
        (78, b"", _DISABLED_ENTRYPOINT_STDERR * 2),
    ],
)
def test_disabled_entrypoint_rejects_non_exact_output(
    monkeypatch,
    returncode,
    stdout,
    stderr,
):
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    with pytest.raises(RuntimeError, match="entrypoint is not fail-closed"):
        verifier._verify_disabled_entrypoint(
            "sha256:" + "a" * 64,
            containment_checks={name: False for name in verifier._CONTAINMENT_CHECKS},
            session=_session(),
        )


def test_disabled_entrypoint_accepts_exact_output(monkeypatch):
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=78,
            stdout=b"",
            stderr=_DISABLED_ENTRYPOINT_STDERR,
        ),
    )

    verifier._verify_disabled_entrypoint(
        "sha256:" + "a" * 64,
        containment_checks={name: False for name in verifier._CONTAINMENT_CHECKS},
        session=_session(),
    )


def test_candidate_runs_disable_pull_fallback():
    for function in (
        verifier._run_image_json,
        verifier._docker_base_isolation_probe,
        verifier._docker_resource_limit_probe,
        verifier._verify_disabled_entrypoint,
    ):
        assert '"--pull=never"' in inspect.getsource(function)


def test_all_docker_output_uses_bounded_runner():
    for function in (
        verifier._docker_base_isolation_probe,
        verifier._docker_resource_limit_probe,
        verifier._docker_json,
        verifier._verify_disabled_entrypoint,
        verifier._verify_embedded_files,
        verifier._require_local_docker,
        verifier._remove_container,
    ):
        source = inspect.getsource(function)
        assert "_run_bounded_command(" in source
        assert "subprocess.run(" not in source


def test_license_collector_uses_site_disabled_python(monkeypatch):
    commands = []
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda command, **kwargs: (
            commands.append(command)
            or SimpleNamespace(returncode=0, stdout=b"{}", stderr=b"")
        ),
    )
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)

    verifier._run_image_json(
        "sha256:" + "a" * 64,
        "/opt/gdpval/v2/license_evidence.py",
        1024,
        containment_checks={name: False for name in verifier._CONTAINMENT_CHECKS},
        include_purelib=False,
        session=_session(),
    )

    assert commands[0][-7:] == [
        "sha256:" + "a" * 64,
        "-I",
        "-S",
        "-B",
        "-c",
        verifier._IMAGE_STDLIB_SCRIPT_BOOTSTRAP,
        "/opt/gdpval/v2/license_evidence.py",
    ]


def test_all_image_json_probes_require_no_site(monkeypatch):
    commands = []
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda command, **kwargs: (
            commands.append(command)
            or SimpleNamespace(returncode=0, stdout=b"{}", stderr=b"")
        ),
    )
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)

    for script, include_purelib in (
        ("/opt/gdpval/v2/image_probe.py", True),
        ("/opt/gdpval/v2/effective_sbom.py", True),
        ("/opt/gdpval/v2/license_evidence.py", False),
    ):
        verifier._run_image_json(
            "sha256:" + "a" * 64,
            script,
            1024,
            containment_checks={
                name: False for name in verifier._CONTAINMENT_CHECKS
            },
            include_purelib=include_purelib,
            session=_session(),
        )

    assert all(command[-6:-3] == ["-I", "-S", "-B"] for command in commands)
    assert [command[-2] for command in commands] == [
        verifier._IMAGE_PURELIB_SCRIPT_BOOTSTRAP,
        verifier._IMAGE_PURELIB_SCRIPT_BOOTSTRAP,
        verifier._IMAGE_STDLIB_SCRIPT_BOOTSTRAP,
    ]


def test_containment_probes_use_no_site_python():
    for function in (
        verifier._docker_base_isolation_probe,
        verifier._docker_resource_limit_probe,
    ):
        source = inspect.getsource(function)
        assert 'image, "-I", "-S", "-B", "-c"' in source


def test_site_disabled_python_ignores_hostile_startup(tmp_path):
    marker = tmp_path / "startup-ran"
    (tmp_path / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            (
                "import sys;"
                "assert sys.flags.isolated == 1;"
                "assert sys.flags.no_site == 1;"
                "assert sys.dont_write_bytecode"
            ),
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert not marker.exists()


def test_no_site_flag_blocks_global_pth_startup(tmp_path):
    environment_root = tmp_path / "venv"
    venv.EnvBuilder(with_pip=False).create(environment_root)
    python = environment_root / "bin" / "python"
    site_packages = (
        environment_root
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    marker = tmp_path / "global-pth-ran"
    (site_packages / "hostile.pth").write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )

    baseline = subprocess.run(
        [str(python), "-I", "-B", "-c", "pass"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )
    assert baseline.returncode == 0, baseline.stderr.decode(errors="replace")
    assert marker.exists()
    marker.unlink()

    isolated = subprocess.run(
        [str(python), "-I", "-S", "-B", "-c", "pass"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )
    assert isolated.returncode == 0, isolated.stderr.decode(errors="replace")
    assert not marker.exists()


@pytest.mark.parametrize("module_name", ["hashlib", "json", "email"])
def test_appended_purelib_cannot_shadow_stdlib(tmp_path, module_name):
    shadow_root = tmp_path / "site-packages"
    shadow_root.mkdir()
    marker = tmp_path / f"{module_name}-shadow-ran"
    if module_name == "email":
        module_path = shadow_root / "email" / "__init__.py"
        module_path.parent.mkdir()
    else:
        module_path = shadow_root / f"{module_name}.py"
    module_path.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            "import importlib,sys;sys.path.append(sys.argv[1]);"
            "module=importlib.import_module(sys.argv[2]);"
            "assert not module.__file__.startswith(sys.argv[1])",
            str(shadow_root),
            module_name,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert not marker.exists()


def test_host_reopens_copied_license_evidence_bytes(tmp_path):
    root = tmp_path / "root"
    path = root / "package" / "LICENSE"
    path.parent.mkdir(parents=True)
    value = b"SSPL-1.0\n"
    path.write_bytes(value)

    verifier._verify_copied_evidence_file(
        root,
        verifier.PurePosixPath("package/LICENSE"),
        expected_sha256=__import__("hashlib").sha256(value).hexdigest(),
        expected_size=len(value),
    )

    with pytest.raises(ValueError, match="digest differs"):
        verifier._verify_copied_evidence_file(
            root,
            verifier.PurePosixPath("package/LICENSE"),
            expected_sha256="0" * 64,
            expected_size=len(value),
        )


def test_host_rejects_symlinked_copied_license_evidence(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("MIT", encoding="utf-8")
    (root / "LICENSE").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        verifier._verify_copied_evidence_file(
            root,
            verifier.PurePosixPath("LICENSE"),
            expected_sha256="0" * 64,
            expected_size=3,
        )


def test_host_reopens_all_exact_image_evidence_roots(monkeypatch):
    import hashlib

    values = {
        "/var/lib/dpkg/status": b"status",
        (
            "/usr/local/lib/python3.11/site-packages/"
            "fixture-1.0.dist-info/METADATA"
        ): b"Name: fixture\nVersion: 1.0\n",
    }
    document = {
        "records": [{
            "evidence": [
                {
                    "source": "fixture",
                    "path": path,
                    "resolved_path": path,
                    "sha256": hashlib.sha256(value).hexdigest(),
                    "size": len(value),
                }
                for path, value in values.items()
            ],
        }],
    }
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command[1:3] == ["container", "create"]:
            return SimpleNamespace(
                returncode=0,
                stdout=("a" * 64 + "\n").encode(),
                stderr=b"",
            )
        assert command[1:3] == ["container", "cp"]
        source = command[-2].split(":", 1)[1].removesuffix("/.")
        destination = Path(command[-1])
        for path, value in values.items():
            if path == source or path.startswith(source + "/"):
                relative = Path(path.removeprefix(source + "/"))
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    removed = []
    monkeypatch.setattr(verifier, "_run_bounded_command", run)
    monkeypatch.setattr(
        verifier,
        "_remove_container",
        lambda container: removed.append(container),
    )
    session = verifier.VerificationSession("a" * 32)

    verifier._verify_license_evidence_files(
        "sha256:" + "b" * 64,
        document,
        session=session,
    )

    copied_roots = {
        command[-2].split(":", 1)[1].removesuffix("/.")
        for command in commands
        if command[1:3] == ["container", "cp"]
    }
    assert copied_roots == {
        "/var/lib/dpkg",
        "/usr/local/lib/python3.11/site-packages",
    }
    assert session.label_arguments()[1] in commands[0]
    assert len(removed) == 1


def test_image_json_overflow_still_removes_exact_named_container(monkeypatch):
    removed = []
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("candidate stdout exceeds size limit")
        ),
    )
    monkeypatch.setattr(
        verifier,
        "_remove_container",
        lambda container: removed.append(container),
    )

    with pytest.raises(RuntimeError, match="stdout exceeds size limit"):
        verifier._run_image_json(
            "sha256:" + "a" * 64,
            "/opt/gdpval/v2/license_evidence.py",
            1024,
            containment_checks={name: False for name in verifier._CONTAINMENT_CHECKS},
            include_purelib=False,
            session=_session(),
        )

    assert len(removed) == 1
    assert removed[0].startswith("gdpval-agentic-v2-evidence-")


def test_embedded_inspection_cleans_up_malformed_create_output(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=b"malformed", stderr=b""
        ),
    )
    monkeypatch.setattr(
        verifier,
        "_remove_container",
        lambda container: calls.append(container),
    )

    with pytest.raises(RuntimeError, match="inspection container identity"):
        verifier._verify_embedded_files(
            "sha256:" + "a" * 64,
            "b" * 40,
            tmp_path,
            session=_session(),
        )

    assert len(calls) == 1
    assert calls[0].startswith("gdpval-agentic-v2-inspect-")


def test_parent_lock_rejects_mutable_reference(tmp_path):
    path = tmp_path / "parent.json"
    path.write_text(
        '{"schema_version":"1.0","reference":"image:latest",'
        '"manifest_digest":"sha256:' + 'a' * 64 + '",'
        '"observed_local_image_id":"sha256:' + 'b' * 64 + '",'
        '"source_revision":"' + 'c' * 40 + '",'
        '"platform":"linux/amd64","v1_dockerfile_sha256":"' + 'd' * 64 + '"}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="parent lock identity"):
        verifier._load_parent_lock(path)


def test_builder_stages_only_requested_git_blobs(tmp_path, monkeypatch):
    paths = (
        "batch-runner/core/agentic_v2_oci.py",
        "batch-runner/sandbox/v2/verify_candidate.py",
    )
    monkeypatch.setattr(
        builder,
        "_git_blob",
        lambda revision, path: f"{revision}:{path}".encode("utf-8"),
    )

    builder._stage_git_files("a" * 40, tmp_path, paths)

    assert sorted(
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*")
        if path.is_file()
    ) == ["core/agentic_v2_oci.py", "sandbox/v2/verify_candidate.py"]
    assert (tmp_path / "sandbox/v2/verify_candidate.py").read_bytes() == (
        f"{'a' * 40}:batch-runner/sandbox/v2/verify_candidate.py".encode("utf-8")
    )


def test_builder_verifier_allowlist_is_exact():
    assert builder._VERIFIER_PATHS == (
        "batch-runner/core/agentic_v2_license.py",
        "batch-runner/core/agentic_v2_microvm.py",
        "batch-runner/core/agentic_v2_oci.py",
        "batch-runner/core/agentic_v2_substrate.py",
        "batch-runner/core/agentic_v2_supply_chain.py",
        "batch-runner/sandbox/v2/verify_candidate.py",
    )


def test_git_environments_drop_caller_injection(monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/tmp/forged")
    monkeypatch.setenv("PYTHONPATH", "/tmp/forged-python")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")

    for environment in (builder._git_environment(), verifier._git_environment()):
        assert "GIT_DIR" not in environment
        assert "PYTHONPATH" not in environment
        assert "GITHUB_TOKEN" not in environment
        assert environment["PATH"] == "/usr/bin:/bin"
        assert environment["GIT_CONFIG_NOSYSTEM"] == "1"


def test_verifier_ignores_hostile_path_for_repository_git(tmp_path, monkeypatch):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    marker = tmp_path / "fake-git-ran"
    fake_git = fake_bin / "git"
    fake_git.write_text(
        f"#!/bin/sh\ntouch {str(marker)!r}\nexit 99\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))

    root = verifier._require_repository_root(
        Path.cwd().parent,
        "3ecb8ded14b1cc8ab1725ceb41fcb23696a2c0fc",
    )

    assert root == Path.cwd().parent.resolve()
    assert not marker.exists()


def test_verifier_uses_absolute_trusted_docker(monkeypatch):
    commands = []
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda command, **kwargs: (
            commands.append(command)
            or SimpleNamespace(
                returncode=0,
                stdout=b'"unix:///var/run/docker.sock"\n',
                stderr=b"",
            )
        ),
    )
    monkeypatch.delenv("DOCKER_HOST", raising=False)

    verifier._require_local_docker()

    assert commands[0][0] == verifier._TRUSTED_DOCKER == "/usr/bin/docker"


def test_docker_environments_drop_caller_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "fake-bin"))
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    monkeypatch.setenv("DOCKER_CONFIG", str(tmp_path / "fake-config"))
    monkeypatch.setenv("DOCKER_CONTEXT", "remote")
    monkeypatch.setenv("DOCKER_CERT_PATH", str(tmp_path / "certs"))
    monkeypatch.setenv("DOCKER_TLS_VERIFY", "1")
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    config = tmp_path / "trusted-config"

    assert verifier._docker_environment() == {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "DOCKER_HOST": "unix:///var/run/docker.sock",
    }
    assert builder._docker_cli_environment() == {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "DOCKER_HOST": "unix:///var/run/docker.sock",
    }
    assert builder._docker_environment(config) == {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "DOCKER_CONFIG": str(config),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "DOCKER_HOST": "unix:///var/run/docker.sock",
    }


def test_bounded_docker_runner_injects_sanitized_environment(monkeypatch):
    captured = {}

    class Stop(RuntimeError):
        pass

    def popen(command, **kwargs):
        captured["command"] = command
        captured["environment"] = kwargs.get("env")
        raise Stop("captured")

    monkeypatch.setattr(verifier.subprocess, "Popen", popen)
    monkeypatch.setenv("PATH", "/tmp/fake")
    monkeypatch.setenv("HOME", "/tmp/fake-home")
    monkeypatch.setenv("DOCKER_CONFIG", "/tmp/fake-config")
    monkeypatch.delenv("DOCKER_HOST", raising=False)

    with pytest.raises(Stop, match="captured"):
        verifier._run_bounded_command(
            [verifier._TRUSTED_DOCKER, "version"],
            timeout=1,
            stdout_limit=1024,
            stderr_limit=1024,
        )

    assert captured["command"][0] == "/usr/bin/docker"
    assert captured["environment"] == {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def test_nonlocal_docker_host_is_rejected_before_command(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2376")
    monkeypatch.setattr(
        verifier,
        "_run_bounded_command",
        lambda *args, **kwargs: pytest.fail("Docker command should not run"),
    )

    with pytest.raises(RuntimeError, match="local Unix Docker daemon"):
        verifier._require_local_docker()
    with pytest.raises(RuntimeError, match="local Unix Docker daemon"):
        builder._docker_cli_environment()