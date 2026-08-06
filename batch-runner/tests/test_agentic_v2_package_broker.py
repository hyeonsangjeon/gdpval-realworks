from __future__ import annotations

import base64
import csv
import fcntl
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import sandbox.v2.agentic_v2_package_broker as package_broker_module
from core.agentic_v2_contract import AgenticV2Lifecycle, AgenticV2Profile, LifecycleState
from sandbox.v2.agentic_v2_package_broker import (
    AgenticV2PackageBrokerCandidateBackend,
    OfflinePythonWheelBroker,
    PackageSnapshot,
)
from core.agentic_v2_tools import AgenticV2ToolDispatcher


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_hash(content: bytes) -> str:
    digest = hashlib.sha256(content).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _write_fixture_wheel(
    root: Path,
    *,
    distribution: str = "demo-pkg",
    version: str = "1.0.0",
    module_name: str | None = None,
    requires_dist: str | None = None,
    requires_python: str | None = None,
    corrupt_record: bool = False,
    dist_info: str | None = None,
    extra_files: dict[str, bytes] | None = None,
) -> Path:
    wheel_distribution = distribution.replace("-", "_")
    module_name = module_name or wheel_distribution
    dist_info = dist_info or f"{wheel_distribution}-{version}.dist-info"
    wheel = root / f"{wheel_distribution}-{version}-py3-none-any.whl"
    files = {
        f"{module_name}/__init__.py": (
            b'def message():\n    return "offline-package-ok"\n'
        ),
        f"{dist_info}/METADATA": (
            b"Metadata-Version: 2.1\n"
            + f"Name: {distribution}\n".encode("utf-8")
            + f"Version: {version}\n".encode("utf-8")
            + b"License-Expression: MIT\n"
            + (
                f"Requires-Dist: {requires_dist}\n".encode("utf-8")
                if requires_dist is not None
                else b""
            )
            + (
                f"Requires-Python: {requires_python}\n".encode("utf-8")
                if requires_python is not None
                else b""
            )
        ),
        f"{dist_info}/WHEEL": (
            b"Wheel-Version: 1.0\n"
            b"Generator: gdpval-tests\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
        ),
    }
    files.update(extra_files or {})
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for path, content in sorted(files.items()):
        writer.writerow((
            path,
            "sha256=" + "A" * 43 if corrupt_record and path.endswith("METADATA") else _record_hash(content),
            len(content),
        ))
    writer.writerow((f"{dist_info}/RECORD", "", ""))
    files[f"{dist_info}/RECORD"] = output.getvalue().encode("utf-8")
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(2020, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    return wheel


def _write_snapshot(root: Path, wheel: Path) -> Path:
    path = root / "snapshot.json"
    path.write_text(
        json.dumps(
            _snapshot_document(wheel),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _snapshot_document(wheel: Path) -> dict:
    return {
        "schema_version": "1.0",
        "policy_id": "agentic-v2-package-broker-candidate-v1",
        "foundation_only": True,
        "production_activation": "disabled",
        "platform": {
            "os": "linux",
            "architecture": "amd64",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
        "artifacts": [_artifact_document(wheel, "python:demo-pkg==1.0.0")],
    }


def _artifact_document(wheel: Path, coordinate: str) -> dict:
    return {
        "coordinate": coordinate,
        "filename": wheel.name,
        "sha256": _sha256(wheel),
        "size": wheel.stat().st_size,
        "dependencies": [],
    }


def _write_two_package_snapshot(root: Path, artifact_root: Path) -> Path:
    alpha = _write_fixture_wheel(
        artifact_root,
        distribution="alpha-pkg",
    )
    beta = _write_fixture_wheel(
        artifact_root,
        distribution="beta-pkg",
    )
    document = _snapshot_document(alpha)
    document["artifacts"] = [
        _artifact_document(alpha, "python:alpha-pkg==1.0.0"),
        _artifact_document(beta, "python:beta-pkg==1.0.0"),
    ]
    path = root / "two-package-snapshot.json"
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def test_local_snapshot_installs_python_wheel_then_imports_it(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot_path = _write_snapshot(tmp_path, wheel)
    snapshot = PackageSnapshot.load(snapshot_path, artifact_root=artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=snapshot,
        environment_root=tmp_path / "environments",
    )
    before = broker.state_sha256()

    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })

    assert resolved["ok"] is True
    assert broker.state_sha256() == before
    lock_digest = resolved["data"]["lock_digest"]

    activated = broker.activate({"lock_digest": lock_digest})

    assert activated == {
        "ok": True,
        "data": {"environment_id": lock_digest},
    }
    assert broker.state_sha256() != before
    environment = broker.environment_path(lock_digest)
    assert {path.name for path in environment.iterdir()} == {
        "environment.json",
        "site-packages",
    }
    site_packages = environment / "site-packages"
    probe = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys;"
                f"sys.path.insert(0,{str(site_packages)!r});"
                "import demo_pkg;"
                "print(demo_pkg.message())"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    assert probe.stdout.strip() == "offline-package-ok"
    assert not list(environment.parent.glob(".agentic-v2-staging-*"))

    repeated = broker.activate({"lock_digest": lock_digest})

    assert repeated == activated
    broker.close()
    assert not environment.exists()
    assert not list(environment.parent.iterdir())
    assert wheel.exists()


def test_resolved_digest_activates_after_broker_restart(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot = PackageSnapshot.load(
        _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
    )
    environment_root = tmp_path / "environments"
    resolver = OfflinePythonWheelBroker(
        snapshot=snapshot,
        environment_root=environment_root,
    )
    resolved = resolver.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]

    restarted = OfflinePythonWheelBroker(
        snapshot=snapshot,
        environment_root=environment_root,
    )
    activated = restarted.activate({"lock_digest": digest})

    assert activated == {
        "ok": True,
        "data": {"environment_id": digest},
    }
    restarted.close()
    resolver.close()


@pytest.mark.parametrize(
    ("ecosystem", "requirements", "error_type"),
    [
        ("npm", ["demo-pkg==1.0.0"], "capability_unavailable"),
        ("debian", ["demo-pkg==1.0.0"], "capability_unavailable"),
        ("python", ["demo-pkg"], "invalid_arguments"),
        ("python", ["demo-pkg @ https://example.test/pkg.whl"], "invalid_arguments"),
        ("python", ["missing-pkg==1.0.0"], "package_not_in_snapshot"),
    ],
)
def test_broker_rejects_live_or_unapproved_package_requests(
    tmp_path, ecosystem, requirements, error_type
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )

    result = broker.resolve({
        "ecosystem": ecosystem,
        "requirements": requirements,
    })

    assert result == {"ok": False, "error_type": error_type}


def test_activation_revalidates_artifact_bytes(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    wheel.write_bytes(wheel.read_bytes() + b"drift")

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "unapproved_lock"}
    assert not list((tmp_path / "environments").iterdir())


def test_activation_bounds_artifact_read_during_concurrent_growth(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    original_read = os.read
    mutated = False

    def read_then_grow(descriptor, size):
        nonlocal mutated
        content = original_read(descriptor, size)
        if content and not mutated:
            mutated = True
            wheel.write_bytes(wheel.read_bytes() + b"growth")
        return content

    monkeypatch.setattr(os, "read", read_then_grow)

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "unapproved_lock"}
    assert not list((tmp_path / "environments").iterdir())


def test_source_drift_during_install_prevents_publish(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot = PackageSnapshot.load(
        _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
    )
    broker = OfflinePythonWheelBroker(
        snapshot=snapshot,
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    original_install = package_broker_module._install_verified_wheel

    def mutate_source_after_verified_read(content, site_packages, artifact):
        assert hashlib.sha256(content).hexdigest() == artifact.sha256
        wheel.write_bytes(wheel.read_bytes() + b"source-drift")
        original_install(content, site_packages, artifact)

    monkeypatch.setattr(
        package_broker_module,
        "_install_verified_wheel",
        mutate_source_after_verified_read,
    )

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert not list((tmp_path / "environments").iterdir())
    broker.close()


def test_post_lease_artifact_drift_rolls_back_lease_and_staging(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    original_acquire = broker._acquire_environment_lease

    def acquire_then_drift(root_fd, selected_digest):
        original_acquire(root_fd, selected_digest)
        wheel.write_bytes(wheel.read_bytes() + b"post-lease-drift")

    monkeypatch.setattr(broker, "_acquire_environment_lease", acquire_then_drift)

    result = broker.activate({"lock_digest": digest})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert not broker.environment_path(digest).exists()
    assert not list(environment_root.iterdir())
    broker.close()


def test_snapshot_rejects_symlinked_artifact(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(tmp_path)
    linked = artifact_root / wheel.name
    linked.symlink_to(wheel)
    snapshot = _snapshot_document(wheel)
    snapshot["artifacts"][0]["size"] = wheel.stat().st_size
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(ValueError, match="unavailable or unsafe"):
        PackageSnapshot.load(path, artifact_root=artifact_root)


@pytest.mark.timeout(2)
def test_snapshot_manifest_fifo_fails_without_blocking(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    manifest_fifo = tmp_path / "snapshot.fifo"
    os.mkfifo(manifest_fifo)

    with pytest.raises(ValueError, match="bounded single-link file"):
        PackageSnapshot.load(manifest_fifo, artifact_root=artifact_root)


@pytest.mark.timeout(2)
def test_snapshot_artifact_fifo_fails_without_blocking(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    artifact_fifo = artifact_root / "demo_pkg-1.0.0-py3-none-any.whl"
    os.mkfifo(artifact_fifo)
    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()
    fixture = _write_fixture_wheel(fixture_root)
    document = _snapshot_document(fixture)
    document["artifacts"][0]["filename"] = artifact_fifo.name
    document["artifacts"][0]["sha256"] = "a" * 64
    document["artifacts"][0]["size"] = 1
    manifest = tmp_path / "snapshot.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="size or type drifted"):
        PackageSnapshot.load(manifest, artifact_root=artifact_root)


@pytest.mark.parametrize(
    ("wheel_kwargs", "message"),
    [
        ({"requires_dist": "other-pkg==1.0.0"}, "metadata identity"),
        ({"corrupt_record": True}, "RECORD identity"),
    ],
)
def test_snapshot_rejects_hidden_dependency_or_record_drift(
    tmp_path, wheel_kwargs, message
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root, **wheel_kwargs)

    with pytest.raises(ValueError, match=message):
        PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        )


@pytest.mark.parametrize("requires_python", ["<3", "not-a-specifier"])
def test_snapshot_rejects_incompatible_or_invalid_python_requirement(
    tmp_path, requires_python
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(
        artifact_root, requires_python=requires_python
    )

    with pytest.raises(ValueError, match="Python requirement|metadata identity"):
        PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        )


@pytest.mark.parametrize(
    "wheel_kwargs",
    [
        {"dist_info": "other-1.0.0.dist-info"},
        {"extra_files": {"../escape.py": b"unsafe\n"}},
        {"extra_files": {"startup.pth": b"import os\n"}},
        {"extra_files": {"sitecustomize/__init__.py": b"value = 1\n"}},
        {"extra_files": {"sitecustomize.pyc": b"bytecode"}},
        {"extra_files": {"pkg/usercustomize.py": b"value = 1\n"}},
        {"extra_files": {"shared": b"file", "shared/module.py": b"nested"}},
        {"extra_files": {"a" * 241: b"oversized"}},
    ],
)
def test_snapshot_rejects_mismatched_or_unsafe_wheel_entries(
    tmp_path, wheel_kwargs
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root, **wheel_kwargs)

    with pytest.raises(
        ValueError,
        match="metadata set|entry is unsafe|path kind collision",
    ):
        PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        )


def test_snapshot_rejects_cross_wheel_file_directory_collision(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    alpha = _write_fixture_wheel(
        artifact_root,
        distribution="alpha-pkg",
        extra_files={"shared": b"file"},
    )
    beta = _write_fixture_wheel(
        artifact_root,
        distribution="beta-pkg",
        extra_files={"shared/module.py": b"value = 1\n"},
    )
    document = _snapshot_document(alpha)
    document["artifacts"] = [
        _artifact_document(alpha, "python:alpha-pkg==1.0.0"),
        _artifact_document(beta, "python:beta-pkg==1.0.0"),
    ]
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="collision"):
        PackageSnapshot.load(snapshot_path, artifact_root=artifact_root)


def test_snapshot_rejects_wheel_before_extraction_when_unpacked_limit_exceeds(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    monkeypatch.setattr(package_broker_module, "MAX_ENVIRONMENT_BYTES", 128)

    with pytest.raises(ValueError, match="archive limits"):
        PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        )


def test_snapshot_bounds_wheel_control_metadata_before_parsing(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    monkeypatch.setattr(package_broker_module, "MAX_WHEEL_METADATA_BYTES", 32)

    with pytest.raises(ValueError, match="METADATA exceeds"):
        PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        )


@pytest.mark.parametrize(
    "wheel_control",
    [
        (
            b"Wheel-Version: 1.0\n"
            b"Wheel-Version: 2.0\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
        ),
        (
            b"Wheel-Version: 1.0\n"
            b"Root-Is-Purelib: true\n"
            b"Root-Is-Purelib: false\n"
            b"Tag: py3-none-any\n"
        ),
        (
            b"Wheel-Version: 1.0\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
            b"Tag: cp310-none-any\n"
        ),
        (
            b"wheel-version: 1.0\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
        ),
        (
            b"Wheel-Version: 1.0\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n"
            b"Unexpected: value\n"
        ),
    ],
)
def test_snapshot_rejects_duplicate_conflicting_or_unknown_wheel_headers(
    tmp_path, wheel_control
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(
        artifact_root,
        extra_files={"demo_pkg-1.0.0.dist-info/WHEEL": wheel_control},
    )

    with pytest.raises(ValueError, match="WHEEL|compatibility"):
        PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        )


def test_snapshot_accepts_standard_wheel_header_terminator(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(
        artifact_root,
        extra_files={
            "demo_pkg-1.0.0.dist-info/WHEEL": (
                b"Wheel-Version: 1.0\r\n"
                b"Generator: gdpval-tests\r\n"
                b"Root-Is-Purelib: true\r\n"
                b"Tag: py3-none-any\r\n"
                b"\r\n"
            ),
        },
    )

    snapshot = PackageSnapshot.load(
        _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
    )

    assert sorted(snapshot.artifacts) == ["python:demo-pkg==1.0.0"]


@pytest.mark.parametrize("separator", [b"\v", b"\f", b"\r"])
def test_snapshot_rejects_nonstandard_wheel_line_separators(
    tmp_path, separator
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(
        artifact_root,
        extra_files={
            "demo_pkg-1.0.0.dist-info/WHEEL": (
                b"Wheel-Version: 1.0"
                + separator
                + b"Root-Is-Purelib: true\n"
                + b"Tag: py3-none-any\n"
            ),
        },
    )

    with pytest.raises(ValueError, match="WHEEL is invalid"):
        PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        )


def test_failed_installation_leaves_no_partial_environment(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    monkeypatch.setattr(
        package_broker_module,
        "_install_verified_wheel",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("failed")),
    )

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert not list((tmp_path / "environments").iterdir())


def test_unexpected_staging_entry_is_rejected_before_publish(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    original_install = package_broker_module._install_verified_wheel

    def install_with_extra_entry(content, site_packages, artifact):
        original_install(content, site_packages, artifact)
        (site_packages.parent / "unexpected.txt").write_text(
            "unexpected", encoding="utf-8"
        )

    monkeypatch.setattr(
        package_broker_module,
        "_install_verified_wheel",
        install_with_extra_entry,
    )

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert not list((tmp_path / "environments").iterdir())


def test_oversized_receipt_is_rejected_before_publish(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    monkeypatch.setattr(package_broker_module, "MAX_RECEIPT_BYTES", 128)

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert not list((tmp_path / "environments").iterdir())


def test_malformed_lease_blocks_before_environment_publish(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    malformed_lease = environment_root / f".agentic-v2-lease-{digest}"
    malformed_lease.write_text("not-empty", encoding="utf-8")

    result = broker.activate({"lock_digest": digest})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert not broker.environment_path(digest).exists()
    assert not list(environment_root.glob(".agentic-v2-staging-*"))
    malformed_lease.unlink()
    broker.close()


def test_concurrent_activation_reuses_one_mode_sealed_environment(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    results = []

    def activate():
        results.append(broker.activate({"lock_digest": digest}))

    workers = [threading.Thread(target=activate) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert results == [
        {"ok": True, "data": {"environment_id": digest}},
        {"ok": True, "data": {"environment_id": digest}},
    ]
    assert [
        path.name
        for path in (tmp_path / "environments").iterdir()
        if len(path.name) == 64
    ] == [digest]


def test_distinct_brokers_serialize_activation_with_root_flock(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot = PackageSnapshot.load(
        _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
    )
    environment_root = tmp_path / "environments"
    brokers = [
        OfflinePythonWheelBroker(
            snapshot=snapshot,
            environment_root=environment_root,
        )
        for _ in range(2)
    ]
    resolved = brokers[0].resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    results = []

    workers = [
        threading.Thread(
            target=lambda broker=broker: results.append(
                broker.activate({"lock_digest": digest})
            )
        )
        for broker in brokers
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert results == [
        {"ok": True, "data": {"environment_id": digest}},
        {"ok": True, "data": {"environment_id": digest}},
    ]
    assert [
        path.name for path in environment_root.iterdir() if len(path.name) == 64
    ] == [digest]
    brokers[0].close()
    assert brokers[1].environment_path(digest).is_dir()
    assert brokers[1].activate({"lock_digest": digest})["ok"] is True
    brokers[1].close()
    assert not list(environment_root.iterdir())


def test_concurrent_close_cannot_remove_another_brokers_lease(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot = PackageSnapshot.load(
        _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
    )
    environment_root = tmp_path / "environments"
    brokers = [
        OfflinePythonWheelBroker(
            snapshot=snapshot,
            environment_root=environment_root,
        )
        for _ in range(2)
    ]
    resolved = brokers[0].resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert brokers[0].activate({"lock_digest": digest})["ok"] is True
    assert brokers[1].activate({"lock_digest": digest})["ok"] is True
    results = []
    workers = [
        threading.Thread(target=brokers[0].close),
        threading.Thread(
            target=lambda: results.append(
                brokers[1].activate({"lock_digest": digest})
            )
        ),
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert results == [{"ok": True, "data": {"environment_id": digest}}]
    assert brokers[1].environment_path(digest).is_dir()
    brokers[1].close()
    assert not list(environment_root.iterdir())


def test_separate_processes_serialize_activation_with_root_flock(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot_path = _write_snapshot(tmp_path, wheel)
    snapshot = PackageSnapshot.load(snapshot_path, artifact_root=artifact_root)
    environment_root = tmp_path / "environments"
    resolver = OfflinePythonWheelBroker(
        snapshot=snapshot,
        environment_root=environment_root,
    )
    resolved = resolver.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    script = (
        "import json;"
        "from sandbox.v2.agentic_v2_package_broker import "
        "OfflinePythonWheelBroker,PackageSnapshot;"
        f"snapshot=PackageSnapshot.load({str(snapshot_path)!r},"
        f"artifact_root={str(artifact_root)!r});"
        "broker=OfflinePythonWheelBroker(snapshot=snapshot,"
        f"environment_root={str(environment_root)!r});"
        f"print(json.dumps(broker.activate({{'lock_digest':{digest!r}}})))"
    )
    batch_root = Path(__file__).resolve().parents[1]
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=batch_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = []
    for worker in workers:
        stdout, stderr = worker.communicate(timeout=30)
        assert worker.returncode == 0, stderr
        results.append(json.loads(stdout))

    assert results == [
        {"ok": True, "data": {"environment_id": digest}},
        {"ok": True, "data": {"environment_id": digest}},
    ]
    assert [
        path.name for path in environment_root.iterdir() if len(path.name) == 64
    ] == [digest]
    resolver.close()


def test_root_environment_count_quota_rejects_second_digest(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    snapshot = PackageSnapshot.load(
        _write_two_package_snapshot(tmp_path, artifact_root),
        artifact_root=artifact_root,
    )
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=snapshot,
        environment_root=environment_root,
    )
    alpha = broker.resolve({
        "ecosystem": "python",
        "requirements": ["alpha-pkg==1.0.0"],
    })
    beta = broker.resolve({
        "ecosystem": "python",
        "requirements": ["beta-pkg==1.0.0"],
    })
    assert broker.activate({"lock_digest": alpha["data"]["lock_digest"]})[
        "ok"
    ] is True
    monkeypatch.setattr(package_broker_module, "MAX_ACTIVE_ENVIRONMENTS", 1)

    result = broker.activate({"lock_digest": beta["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert broker.environment_path(alpha["data"]["lock_digest"]).is_dir()
    assert not broker.environment_path(beta["data"]["lock_digest"]).exists()
    broker.close()


def test_root_environment_byte_quota_rejects_second_digest(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    snapshot = PackageSnapshot.load(
        _write_two_package_snapshot(tmp_path, artifact_root),
        artifact_root=artifact_root,
    )
    broker = OfflinePythonWheelBroker(
        snapshot=snapshot,
        environment_root=tmp_path / "environments",
    )
    alpha = broker.resolve({
        "ecosystem": "python",
        "requirements": ["alpha-pkg==1.0.0"],
    })
    beta = broker.resolve({
        "ecosystem": "python",
        "requirements": ["beta-pkg==1.0.0"],
    })
    assert broker.activate({"lock_digest": alpha["data"]["lock_digest"]})[
        "ok"
    ] is True
    alpha_bytes = snapshot.artifacts[
        "python:alpha-pkg==1.0.0"
    ].unpacked_size
    beta_bytes = snapshot.artifacts[
        "python:beta-pkg==1.0.0"
    ].unpacked_size
    monkeypatch.setattr(
        package_broker_module,
        "MAX_ACTIVE_ENVIRONMENT_BYTES",
        alpha_bytes + beta_bytes - 1,
    )

    result = broker.activate({"lock_digest": beta["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert broker.environment_path(alpha["data"]["lock_digest"]).is_dir()
    assert not broker.environment_path(beta["data"]["lock_digest"]).exists()
    broker.close()


def test_close_cleans_multiple_valid_environments_with_independent_budgets(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    snapshot = PackageSnapshot.load(
        _write_two_package_snapshot(tmp_path, artifact_root),
        artifact_root=artifact_root,
    )
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=snapshot,
        environment_root=environment_root,
    )
    digests = []
    for requirement in ("alpha-pkg==1.0.0", "beta-pkg==1.0.0"):
        resolved = broker.resolve({
            "ecosystem": "python",
            "requirements": [requirement],
        })
        digest = resolved["data"]["lock_digest"]
        assert broker.activate({"lock_digest": digest})["ok"] is True
        digests.append(digest)
    cleanup_costs = [
        2 + sum(1 for _ in broker.environment_path(digest).rglob("*"))
        for digest in digests
    ]
    per_environment_limit = max(cleanup_costs)
    assert sum(cleanup_costs) > per_environment_limit
    monkeypatch.setattr(
        package_broker_module,
        "MAX_CLEANUP_ENTRIES",
        per_environment_limit,
    )

    broker.close()

    assert not list(environment_root.iterdir())


def test_shared_root_changes_are_visible_in_every_broker_state(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    snapshot = PackageSnapshot.load(
        _write_two_package_snapshot(tmp_path, artifact_root),
        artifact_root=artifact_root,
    )
    environment_root = tmp_path / "environments"
    brokers = [
        OfflinePythonWheelBroker(
            snapshot=snapshot,
            environment_root=environment_root,
        )
        for _ in range(2)
    ]
    initial = brokers[0].state_sha256()
    assert brokers[1].state_sha256() == initial
    alpha = brokers[0].resolve({
        "ecosystem": "python",
        "requirements": ["alpha-pkg==1.0.0"],
    })
    beta = brokers[1].resolve({
        "ecosystem": "python",
        "requirements": ["beta-pkg==1.0.0"],
    })

    assert brokers[0].activate({"lock_digest": alpha["data"]["lock_digest"]})[
        "ok"
    ] is True
    after_alpha = brokers[1].state_sha256()
    assert after_alpha == brokers[0].state_sha256()
    assert after_alpha != initial
    assert brokers[1].activate({"lock_digest": beta["data"]["lock_digest"]})[
        "ok"
    ] is True
    after_beta = brokers[0].state_sha256()
    assert after_beta == brokers[1].state_sha256()
    assert after_beta != after_alpha

    brokers[0].close()
    brokers[1].close()


def test_unaccounted_root_entry_invalidates_global_state(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    unaccounted = environment_root / "unexpected.txt"
    unaccounted.write_text("unexpected", encoding="utf-8")

    with pytest.raises(ValueError, match="state drifted"):
        broker.state_sha256()

    unaccounted.unlink()
    broker.close()


def test_mode_or_content_drift_invalidates_state_and_reactivation(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert broker.activate({"lock_digest": digest})["ok"] is True
    environment = broker.environment_path(digest)
    for path in [environment, *environment.rglob("*")]:
        expected = 0o555 if path.is_dir() else 0o444
        assert path.stat().st_mode & 0o777 == expected
    assert len(broker.state_sha256()) == 64
    package_file = environment / "site-packages/demo_pkg/__init__.py"
    package_file.chmod(0o644)
    package_file.write_text("drifted = True\n", encoding="utf-8")

    with pytest.raises(ValueError, match="state drifted"):
        broker.state_sha256()
    repeated = broker.activate({"lock_digest": digest})

    assert repeated == {"ok": False, "error_type": "unapproved_lock"}
    broker.close()


def test_environment_growth_during_replay_fails_closed(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert broker.activate({"lock_digest": digest})["ok"] is True
    package_file = broker.environment_path(
        digest
    ) / "site-packages/demo_pkg/__init__.py"
    original_read = os.read
    mutated = False

    def read_then_grow(descriptor, size):
        nonlocal mutated
        content = original_read(descriptor, size)
        try:
            opened_path = os.readlink(f"/proc/self/fd/{descriptor}")
        except OSError:
            opened_path = ""
        if content and not mutated and opened_path == str(package_file):
            mutated = True
            package_file.chmod(0o644)
            with package_file.open("ab") as stream:
                stream.write(b"growth")
        return content

    monkeypatch.setattr(os, "read", read_then_grow)

    with pytest.raises(ValueError, match="state drifted"):
        broker.state_sha256()
    assert mutated is True
    broker.close()


def test_environment_entry_flood_is_bounded_during_replay(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert broker.activate({"lock_digest": digest})["ok"] is True
    site_packages = broker.environment_path(digest) / "site-packages"
    site_packages.chmod(0o755)
    for index in range(16):
        extra = site_packages / f"extra-{index}.txt"
        extra.write_text("x", encoding="utf-8")
        extra.chmod(0o444)
    site_packages.chmod(0o555)
    monkeypatch.setattr(package_broker_module, "MAX_ENVIRONMENT_ENTRIES", 8)

    with pytest.raises(ValueError, match="state drifted"):
        broker.state_sha256()
    broker.close()


def test_forged_receipt_cannot_approve_content_drift(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert broker.activate({"lock_digest": digest})["ok"] is True
    environment = broker.environment_path(digest)
    package_file = environment / "site-packages/demo_pkg/__init__.py"
    package_file.chmod(0o644)
    package_file.write_text("drifted = True\n", encoding="utf-8")
    package_file.chmod(0o444)
    lock = broker._validated_lock(digest)
    forged = package_broker_module._environment_receipt(
        environment / "site-packages",
        lock_digest=digest,
        snapshot_sha256=broker.snapshot.sha256,
        policy_sha256=broker.policy_sha256,
        installer_identity=broker.installer_identity,
        requirements=lock["requirements"],
    )
    receipt = environment / "environment.json"
    receipt.chmod(0o644)
    receipt.write_text(
        json.dumps(forged, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    receipt.chmod(0o444)

    repeated = broker.activate({"lock_digest": digest})

    assert repeated == {"ok": False, "error_type": "unapproved_lock"}
    broker.close()


@pytest.mark.parametrize("mutation", ["reformat", "duplicate", "boolean-as-int"])
def test_receipt_requires_exact_canonical_bytes(tmp_path, mutation):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert broker.activate({"lock_digest": digest})["ok"] is True
    receipt = broker.environment_path(digest) / "environment.json"
    original = receipt.read_bytes()
    if mutation == "reformat":
        changed = json.dumps(json.loads(original), indent=2).encode("utf-8")
    elif mutation == "duplicate":
        changed = b'{"schema_version":"1.0",' + original[1:]
    else:
        changed = original.replace(b'"foundation_only":true', b'"foundation_only":1')
    receipt.chmod(0o644)
    receipt.write_bytes(changed)
    receipt.chmod(0o444)

    assert broker.activate({"lock_digest": digest}) == {
        "ok": False,
        "error_type": "unapproved_lock",
    }
    with pytest.raises(ValueError, match="state drifted"):
        broker.state_sha256()
    broker.close()


def test_receipt_baseline_hash_cannot_be_replaced_in_memory(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert broker.activate({"lock_digest": digest})["ok"] is True
    broker._active[digest] = "0" * 64

    with pytest.raises(ValueError, match="state drifted"):
        broker.state_sha256()
    assert broker.activate({"lock_digest": digest}) == {
        "ok": False,
        "error_type": "unapproved_lock",
    }
    broker.close()


def test_active_lease_metadata_drift_invalidates_state(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert broker.activate({"lock_digest": digest})["ok"] is True
    lease = environment_root / f".agentic-v2-lease-{digest}"
    lease.write_text("drift", encoding="utf-8")

    with pytest.raises(ValueError, match="state drifted"):
        broker.state_sha256()
    assert broker.activate({"lock_digest": digest}) == {
        "ok": False,
        "error_type": "compute_backend_error",
    }
    lease.write_text("", encoding="utf-8")
    broker.close()


def test_unlocked_local_lease_is_reestablished_before_state_acceptance(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    assert broker.activate({"lock_digest": digest})["ok"] is True
    fcntl.flock(broker._leases[digest], fcntl.LOCK_UN)

    assert len(broker.state_sha256()) == 64
    probe = os.open(
        environment_root / f".agentic-v2-lease-{digest}",
        os.O_RDWR | os.O_NONBLOCK,
    )
    try:
        with pytest.raises(BlockingIOError):
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(probe)
    broker.close()


def test_abrupt_exit_orphan_lease_is_recovered_on_retry(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    lease = environment_root / f".agentic-v2-lease-{digest}"
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import fcntl,os;"
                f"fd=os.open({str(lease)!r},os.O_RDWR|os.O_CREAT,0o600);"
                "fcntl.flock(fd,fcntl.LOCK_SH)"
            ),
        ],
        check=True,
    )
    assert lease.is_file()
    assert not broker.environment_path(digest).exists()

    result = broker.activate({"lock_digest": digest})

    assert result == {"ok": True, "data": {"environment_id": digest}}
    assert broker.environment_path(digest).is_dir()
    broker.close()


def test_live_prepublish_lease_blocks_publish_until_holder_exits(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    lease = environment_root / f".agentic-v2-lease-{digest}"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl,os,sys;"
                f"fd=os.open({str(lease)!r},os.O_RDWR|os.O_CREAT,0o600);"
                "fcntl.flock(fd,fcntl.LOCK_SH);"
                "print('ready',flush=True);"
                "sys.stdin.readline()"
            ),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    assert holder.stdout.readline().strip() == "ready"

    blocked = broker.activate({"lock_digest": digest})

    assert blocked == {"ok": False, "error_type": "compute_backend_error"}
    assert not broker.environment_path(digest).exists()
    assert not list(environment_root.glob(".agentic-v2-staging-*"))
    assert holder.stdin is not None
    holder.stdin.write("release\n")
    holder.stdin.flush()
    stdout, stderr = holder.communicate(timeout=10)
    assert holder.returncode == 0, stdout + stderr

    recovered = broker.activate({"lock_digest": digest})

    assert recovered == {"ok": True, "data": {"environment_id": digest}}
    assert broker.environment_path(digest).is_dir()
    broker.close()


def test_digest_symlink_is_rejected_without_touching_external_target(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    digest = resolved["data"]["lock_digest"]
    external = tmp_path / "external-environment"
    external.mkdir(mode=0o755)
    canary = external / "keep.txt"
    canary.write_text("keep", encoding="utf-8")
    (environment_root / digest).symlink_to(external, target_is_directory=True)

    result = broker.activate({"lock_digest": digest})

    assert result == {"ok": False, "error_type": "unapproved_lock"}
    assert canary.read_text(encoding="utf-8") == "keep"
    assert external.stat().st_mode & 0o777 == 0o755
    broker.close()
    assert canary.exists()


def test_stale_staging_symlink_cleanup_never_touches_external_target(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    canary = tmp_path / "external-canary"
    canary.mkdir(mode=0o755)
    canary_file = canary / "keep.txt"
    canary_file.write_text("keep", encoding="utf-8")
    stale = environment_root / ".agentic-v2-stale"
    stale.symlink_to(canary, target_is_directory=True)
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result["ok"] is True
    assert not stale.exists()
    assert canary_file.read_text(encoding="utf-8") == "keep"
    assert canary.stat().st_mode & 0o777 == 0o755
    broker.close()


def test_stale_staging_hardlink_cleanup_preserves_external_inode(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    external = tmp_path / "external.txt"
    external.write_text("keep", encoding="utf-8")
    external.chmod(0o640)
    stale = environment_root / ".agentic-v2-stale"
    stale.mkdir()
    os.link(external, stale / "linked.txt")
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result["ok"] is True
    assert external.read_text(encoding="utf-8") == "keep"
    assert external.stat().st_mode & 0o777 == 0o640
    broker.close()


@pytest.mark.parametrize("shape", ["flood", "deep"])
def test_stale_cleanup_is_bounded_without_recursion(tmp_path, monkeypatch, shape):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    stale = environment_root / ".agentic-v2-stale"
    stale.mkdir()
    if shape == "flood":
        for index in range(16):
            (stale / f"entry-{index}.txt").write_text("x", encoding="utf-8")
        monkeypatch.setattr(package_broker_module, "MAX_CLEANUP_ENTRIES", 8)
    else:
        cursor = stale
        for index in range(12):
            cursor = cursor / f"d{index}"
            cursor.mkdir()
        monkeypatch.setattr(package_broker_module, "MAX_CLEANUP_DEPTH", 4)
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert not broker.environment_path(resolved["data"]["lock_digest"]).exists()


def test_multiple_stale_trees_share_one_cleanup_budget(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    for tree_index in range(2):
        stale = environment_root / f".agentic-v2-stale-{tree_index}"
        stale.mkdir()
        for entry_index in range(4):
            (stale / f"entry-{entry_index}.txt").write_text(
                "x", encoding="utf-8"
            )
    monkeypatch.setattr(package_broker_module, "MAX_CLEANUP_ENTRIES", 10)
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert list(environment_root.glob(".agentic-v2-stale-*"))


def test_environment_root_path_replacement_cannot_redirect_activation(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    environment_root = tmp_path / "environments"
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=environment_root,
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    moved_root = tmp_path / "moved-environments"
    environment_root.rename(moved_root)
    environment_root.mkdir(mode=0o700)
    canary = environment_root / "keep.txt"
    canary.write_text("keep", encoding="utf-8")

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result == {"ok": False, "error_type": "compute_backend_error"}
    assert canary.read_text(encoding="utf-8") == "keep"
    assert not list(moved_root.iterdir())
    broker.close()


def test_parent_fsync_failure_does_not_misreport_atomic_commit(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    broker = OfflinePythonWheelBroker(
        snapshot=PackageSnapshot.load(
            _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
        ),
        environment_root=tmp_path / "environments",
    )
    resolved = broker.resolve({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
    })
    monkeypatch.setattr(os, "fsync", lambda _descriptor: (_ for _ in ()).throw(
        OSError("unsupported")
    ))

    result = broker.activate({"lock_digest": resolved["data"]["lock_digest"]})

    assert result["ok"] is True
    assert broker.environment_path(resolved["data"]["lock_digest"]).is_dir()
    broker.close()


def test_candidate_backend_dispatches_broker_but_blocks_exec(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot = PackageSnapshot.load(
        _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
    )
    backend = AgenticV2PackageBrokerCandidateBackend(
        root=tmp_path / "candidate",
        profile=AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0",
            "policy_profile_id": "package-broker-v1",
            "foundation_only": True,
        }),
        snapshot=snapshot,
    )
    dispatcher = AgenticV2ToolDispatcher(
        backend,
        AgenticV2Lifecycle(LifecycleState.ACTIVE),
    )
    before = backend.state_sha256()
    started = backend.start(timeout_seconds=30)

    assert started["ok"] is True
    assert started["data"]["package_snapshot_sha256"] == snapshot.sha256
    assert started["data"]["package_policy_sha256"] == backend.broker.policy_sha256
    assert len(started["data"]["package_policy_sha256"]) == 64

    resolved = dispatcher.dispatch(
        call_id="resolve-1",
        name="environment_resolve",
        arguments={
            "ecosystem": "python",
            "requirements": ["demo-pkg==1.0.0"],
        },
    )

    assert resolved.result["ok"] is True
    assert resolved.result["state_after_sha256"] == before
    activated = dispatcher.dispatch(
        call_id="activate-1",
        name="environment_activate",
        arguments={"lock_digest": resolved.result["data"]["lock_digest"]},
    )
    assert activated.result["ok"] is True
    assert activated.result["state_after_sha256"] != before

    blocked = dispatcher.dispatch(
        call_id="exec-1",
        name="exec_run",
        arguments={"argv": ["python", "--version"], "cwd": ".", "timeout_seconds": 30},
    )

    assert blocked.result["ok"] is False
    assert blocked.result["error_type"] == "capability_unavailable"
    backend.close()


def test_candidate_backend_close_preserves_replacement_environment_path(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot = PackageSnapshot.load(
        _write_snapshot(tmp_path, wheel), artifact_root=artifact_root
    )
    backend = AgenticV2PackageBrokerCandidateBackend(
        root=tmp_path / "candidate",
        profile=AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0",
            "policy_profile_id": "package-broker-v1",
            "foundation_only": True,
        }),
        snapshot=snapshot,
    )
    environment_root = backend.broker.environment_root
    moved_root = tmp_path / "moved-environments"
    environment_root.rename(moved_root)
    environment_root.mkdir(mode=0o700)
    canary = environment_root / "keep.txt"
    canary.write_text("keep", encoding="utf-8")

    backend.close()

    assert canary.read_text(encoding="utf-8") == "keep"
    assert moved_root.is_dir()


def test_checked_in_snapshot_schema_and_policy_accept_candidate_fixture(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    wheel = _write_fixture_wheel(artifact_root)
    snapshot = _snapshot_document(wheel)
    batch_root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (batch_root / "schemas/agentic-v2-package-snapshot.schema.json")
        .read_text(encoding="utf-8")
    )
    policy = json.loads(
        (batch_root / "security/agentic-v2-package-broker-policy.json")
        .read_text(encoding="utf-8")
    )

    assert not list(Draft202012Validator(schema).iter_errors(snapshot))
    noncanonical = json.loads(json.dumps(snapshot))
    noncanonical["artifacts"][0]["coordinate"] = "python:demo_pkg==1.0.0"
    assert list(Draft202012Validator(schema).iter_errors(noncanonical))
    assert policy["foundation_only"] is True
    assert policy["production_activation"] == "disabled"
    assert policy["network"] == {
        "package_index": "disabled",
        "os_containment": "not_run",
    }
    assert set(policy["admission_evidence"].values()) == {"not_run"}
    assert policy["supported_ecosystems"] == ["python-wheel"]
    assert policy["exec_run"] == "blocked_pending_containment"
    assert policy["limits"]["active_environments"] == 8
    assert policy["limits"]["active_environment_payload_bytes"] == 536870912
    assert policy["limits"]["cleanup_entries"] == 4104
    assert policy["limits"]["cleanup_depth"] == 128
    assert policy["activation"] == {
        "concurrency": "linux-flock",
        "seal": "read-only-modes-with-drift-verification",
        "crash_durability": "not_claimed",
    }


def test_candidate_is_not_wired_into_paid_or_production_paths():
    batch_root = Path(__file__).resolve().parents[1]
    candidate_relative = "sandbox/v2/agentic_v2_package_broker.py"
    forbidden = [
        batch_root / "core/executor.py",
        batch_root / "core/llm_client.py",
        batch_root / "core/agentic_v2_runner.py",
        batch_root / "step2_run_inference.py",
        batch_root / "step7_upload_hf.sh",
        batch_root / "step8_grade.py",
        *sorted((batch_root.parent / ".github/workflows").glob("*.yml")),
        *sorted((batch_root / "experiments").glob("*.yaml")),
    ]

    for path in forbidden:
        assert "agentic_v2_package_broker" not in path.read_text(encoding="utf-8")

    candidate = batch_root / candidate_relative
    assert candidate.is_file()
    assert not (batch_root / "core/agentic_v2_package_broker.py").exists()
    build_surfaces = [
        batch_root / "sandbox/agentic.Dockerfile",
        batch_root / "sandbox/v2/professional-work.Dockerfile",
        batch_root / "sandbox/v2/build_candidate.py",
        batch_root / "sandbox/v2/verify_candidate.py",
        batch_root.parent / ".github/workflows/build-sandbox-image.yml",
    ]
    for path in build_surfaces:
        content = path.read_text(encoding="utf-8")
        assert candidate_relative not in content
        assert "agentic_v2_package_broker.py" not in content

    docker_context_exclusions = {
        line.strip()
        for line in (batch_root / ".dockerignore").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {
        candidate_relative,
        "sandbox/v2/README.md",
        "schemas/agentic-v2-package-snapshot.schema.json",
        "security/agentic-v2-package-broker-policy.json",
    } <= docker_context_exclusions
    assert "tests/" in docker_context_exclusions
    workflow = (
        batch_root.parent / ".github/workflows/build-sandbox-image.yml"
    ).read_text(encoding="utf-8")
    assert "context: batch-runner" in workflow