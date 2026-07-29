from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

import sandbox.v2.build_candidate as builder
import sandbox.v2.verify_candidate as verifier
from core.agentic_v2_supply_chain import evidence_collection_allowed


def test_candidate_verifier_refuses_credential_environment(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "must-not-be-consumed")

    with pytest.raises(RuntimeError, match="credential-bearing"):
        verifier._require_no_credentials()


@pytest.mark.parametrize(
    ("returncode", "stderr", "failed_checks", "expected_status"),
    [
        (0, b"", (), "verified"),
        (0, b"WARNING: PIDs limit discarded", ("pids_limit",), "failed"),
        (
            0,
            b"WARNING: Your kernel does not support CPU CFS scheduler or the "
            b"cgroup is not mounted. Period/quota discarded.",
            ("cpu_quota",),
            "failed",
        ),
        (1, b"runtime error", (), "failed"),
    ],
)
def test_containment_probe_uses_effective_runtime_observation(
    monkeypatch, returncode, stderr, failed_checks, expected_status
):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    for name in failed_checks:
        checks[name] = False
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=returncode,
            stdout=__import__("json").dumps(checks).encode("utf-8"),
            stderr=stderr,
        ),
    )

    report = verifier._inspect_containment("candidate:test")

    assert report["status"] == expected_status
    if returncode == 0:
        assert report["checks"] == checks
    else:
        assert not any(report["checks"].values())


def test_evidence_collection_allows_only_resource_limit_degradation():
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    checks["cpu_quota"] = False
    checks["pids_limit"] = False
    report = {
        "schema_version": "1.0",
        "status": "failed",
        "checks": checks,
        "required": sorted(checks),
        "host_scope": "exact-docker-daemon",
    }
    report["report_sha256"] = verifier.canonical_sha256(report)

    assert evidence_collection_allowed(report) is True

    report["checks"]["network_none"] = False
    report_without_hash = dict(report)
    report_without_hash.pop("report_sha256")
    report["report_sha256"] = verifier.canonical_sha256(report_without_hash)
    assert evidence_collection_allowed(report) is False


def test_containment_probe_rejects_incomplete_runtime_observation(monkeypatch):
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=b'{"memory_limit":true}',
            stderr=b"",
        ),
    )

    assert not any(
        verifier._docker_containment_probe("candidate:test").values()
    )


def test_containment_probe_requires_all_capability_sets():
    for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        assert name in verifier._CONTAINMENT_PROBE


def test_resource_warning_overrides_forged_runtime_check(monkeypatch):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(checks).encode("utf-8"),
            stderr=b"WARNING: PIDs limit discarded",
        ),
    )

    observed = verifier._docker_containment_probe("candidate:test")

    assert observed["pids_limit"] is False
    assert all(value for name, value in observed.items() if name != "pids_limit")


def test_unknown_docker_warning_blocks_evidence_collection(monkeypatch):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(checks).encode("utf-8"),
            stderr=b"WARNING: capability option not supported",
        ),
    )

    assert not any(verifier._docker_containment_probe("candidate:test").values())


def test_mixed_resource_and_unknown_warning_blocks_evidence_collection(monkeypatch):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    monkeypatch.setattr(verifier, "_remove_container", lambda _name: None)
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(checks).encode("utf-8"),
            stderr=b"WARNING: capability option not supported; PIDs limit discarded",
        ),
    )

    assert not any(verifier._docker_containment_probe("candidate:test").values())


def test_candidate_runs_use_predeclared_names_instead_of_cidfiles():
    run_source = inspect.getsource(verifier._run_image_json)
    containment_source = inspect.getsource(verifier._docker_containment_probe)

    assert '"--name", container' in run_source
    assert '"--name", container' in containment_source
    assert "cidfile" not in run_source
    assert "cidfile" not in containment_source


def test_verifier_uses_inspected_image_id_for_candidate_operations():
    source = inspect.getsource(verifier.verify_candidate)

    assert "_verify_embedded_files(\n        image_id" in source
    assert source.count("_run_image_json(\n            image_id") == 2


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
        verifier.subprocess,
        "run",
        lambda *args, **kwargs: next(results),
    )

    verifier._remove_container(container)


def test_container_cleanup_rejects_remaining_container(monkeypatch):
    results = iter([
        SimpleNamespace(returncode=0, stderr=b""),
        SimpleNamespace(returncode=0, stderr=b""),
    ])
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
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
        verifier.subprocess,
        "run",
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
        verifier.subprocess,
        "run",
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
    assert builder._container_absence_confirmed(rendered, container) is False


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
    assert builder._container_absence_confirmed(rendered, container) is True


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

    monkeypatch.setattr(verifier.subprocess, "run", run)

    verifier._remove_container(container)

    assert calls[-1][:3] == ["docker", "container", "inspect"]


def test_builder_disabled_entrypoint_cleans_up_on_timeout(monkeypatch):
    cleaned = []
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        lambda command, **kwargs: (_ for _ in ()).throw(
            builder.subprocess.TimeoutExpired(command, 30)
        ),
    )
    monkeypatch.setattr(
        builder,
        "_remove_container",
        lambda container: cleaned.append(container),
    )

    with pytest.raises(builder.subprocess.TimeoutExpired):
        builder._verify_disabled_entrypoint("sha256:" + "a" * 64)

    assert len(cleaned) == 1
    assert cleaned[0].startswith("gdpval-agentic-v2-disabled-")


def test_embedded_inspection_cleans_up_malformed_create_output(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        verifier.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="malformed"),
    )
    monkeypatch.setattr(
        verifier,
        "_remove_container",
        lambda container: calls.append(container),
    )

    with pytest.raises(RuntimeError, match="inspection container identity"):
        verifier._verify_embedded_files("sha256:" + "a" * 64, "b" * 40, tmp_path)

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
        assert environment["GIT_CONFIG_NOSYSTEM"] == "1"