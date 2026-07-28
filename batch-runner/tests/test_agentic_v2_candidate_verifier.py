from __future__ import annotations

from types import SimpleNamespace

import pytest

import sandbox.v2.build_candidate as builder
import sandbox.v2.verify_candidate as verifier


def test_candidate_verifier_refuses_credential_environment(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "must-not-be-consumed")

    with pytest.raises(RuntimeError, match="credential-bearing"):
        verifier._require_no_credentials()


@pytest.mark.parametrize(
    ("returncode", "stderr", "expected_status"),
    [
        (0, b"", "verified"),
        (0, b"WARNING: PIDs limit discarded", "failed"),
        (0, b"kernel does not support CPU CFS", "failed"),
        (1, b"runtime error", "failed"),
    ],
)
def test_containment_probe_rejects_silent_degradation(
    monkeypatch, returncode, stderr, expected_status
):
    checks = {name: True for name in verifier._CONTAINMENT_CHECKS}
    monkeypatch.setattr(verifier, "_remove_cidfile_container", lambda _path: None)
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
    assert all(report["checks"].values()) is (expected_status == "verified")


def test_containment_probe_rejects_incomplete_runtime_observation(monkeypatch):
    monkeypatch.setattr(verifier, "_remove_cidfile_container", lambda _path: None)
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