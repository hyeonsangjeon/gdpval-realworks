from __future__ import annotations

import io
import json
import os
import tarfile
from pathlib import Path

import pytest

from core.agentic_v2_oci import (
    export_docker_archive_to_oci,
    verify_oci_layout,
)


def _archive(path: Path) -> None:
    layer = _tar_bytes({"work/report.txt": b"done"})
    import hashlib

    diff_id = hashlib.sha256(layer).hexdigest()
    config = json.dumps({
        "architecture": "amd64",
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": [f"sha256:{diff_id}"]},
        "config": {"Labels": {"foundation-only": "true"}},
    }, sort_keys=True, separators=(",", ":")).encode()
    config_digest = hashlib.sha256(config).hexdigest()
    manifest = json.dumps([{
        "Config": f"{config_digest}.json",
        "RepoTags": ["candidate:test"],
        "Layers": ["layer/layer.tar"],
    }], separators=(",", ":")).encode()
    with tarfile.open(path, "w") as archive:
        _add(archive, "manifest.json", manifest)
        _add(archive, f"{config_digest}.json", config)
        _add(archive, "layer/layer.tar", layer)


def _tar_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, value in files.items():
            _add(archive, name, value)
    return output.getvalue()


def _add(archive: tarfile.TarFile, name: str, value: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(value)
    info.mtime = 0
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(value))


def _reseal_manifest(output: Path, mutate) -> str:
    import hashlib

    index_path = output / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    descriptor = index["manifests"][0]
    old_digest = descriptor["digest"].removeprefix("sha256:")
    old_path = output / "blobs" / "sha256" / old_digest
    manifest = json.loads(old_path.read_text(encoding="utf-8"))
    mutate(manifest)
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), allow_nan=True
    ).encode("utf-8")
    new_digest = hashlib.sha256(manifest_bytes).hexdigest()
    (output / "blobs" / "sha256" / new_digest).write_bytes(manifest_bytes)
    old_path.unlink()
    descriptor["digest"] = f"sha256:{new_digest}"
    descriptor["size"] = len(manifest_bytes)
    index_path.write_text(
        json.dumps(index, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return descriptor["digest"]


def test_docker_archive_exports_to_verified_oci_layout(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)

    identity = export_docker_archive_to_oci(archive, output)

    assert identity["manifest_digest"].startswith("sha256:")
    assert identity["config_digest"].startswith("sha256:")
    assert identity["layer_count"] == 1
    assert identity["platform"] == {"os": "linux", "architecture": "amd64"}
    assert verify_oci_layout(
        output,
        expected_manifest_digest=identity["manifest_digest"],
    ) == identity


def test_oci_verifier_rejects_blob_tampering(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    identity = export_docker_archive_to_oci(archive, output)
    index = json.loads((output / "index.json").read_text())
    digest = index["manifests"][0]["digest"].removeprefix("sha256:")
    (output / "blobs" / "sha256" / digest).write_bytes(b"tampered")

    with pytest.raises(ValueError, match="OCI blob identity mismatch"):
        verify_oci_layout(output, expected_manifest_digest=identity["manifest_digest"])


def test_oci_verifier_rejects_resealed_wrong_config_media_type(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    export_docker_archive_to_oci(archive, output)
    index_path = output / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    descriptor = index["manifests"][0]
    old_manifest_digest = descriptor["digest"].removeprefix("sha256:")
    old_manifest_path = output / "blobs" / "sha256" / old_manifest_digest
    manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    manifest["config"]["mediaType"] = "application/octet-stream"
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    import hashlib

    new_manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    (output / "blobs" / "sha256" / new_manifest_digest).write_bytes(
        manifest_bytes
    )
    old_manifest_path.unlink()
    descriptor["digest"] = f"sha256:{new_manifest_digest}"
    descriptor["size"] = len(manifest_bytes)
    index_path.write_text(
        json.dumps(index, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="OCI config descriptor is invalid"):
        verify_oci_layout(
            output,
            expected_manifest_digest=descriptor["digest"],
        )


@pytest.mark.parametrize("target", ["index", "manifest"])
def test_oci_verifier_rejects_float_schema_version(tmp_path, target):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    identity = export_docker_archive_to_oci(archive, output)
    if target == "index":
        index_path = output / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["schemaVersion"] = 2.0
        index_path.write_text(json.dumps(index), encoding="utf-8")
        expected = identity["manifest_digest"]
    else:
        expected = _reseal_manifest(
            output, lambda manifest: manifest.update({"schemaVersion": 2.0})
        )

    with pytest.raises(ValueError, match="OCI (index identity|image manifest)"):
        verify_oci_layout(output, expected_manifest_digest=expected)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "1e400"])
def test_oci_verifier_rejects_nonfinite_config_json(tmp_path, constant):
    import hashlib

    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    export_docker_archive_to_oci(archive, output)
    index = json.loads((output / "index.json").read_text())
    manifest_digest = index["manifests"][0]["digest"].removeprefix("sha256:")
    manifest = json.loads(
        (output / "blobs" / "sha256" / manifest_digest).read_text()
    )
    config_digest = manifest["config"]["digest"].removeprefix("sha256:")
    config_path = output / "blobs" / "sha256" / config_digest
    config_bytes = config_path.read_bytes()
    assert config_bytes.endswith(b"}")
    config_bytes = (
        config_bytes[:-1]
        + b',"invalid":'
        + constant.encode("ascii")
        + b"}"
    )
    new_config_digest = hashlib.sha256(config_bytes).hexdigest()
    (output / "blobs" / "sha256" / new_config_digest).write_bytes(config_bytes)
    config_path.unlink()
    expected_manifest = _reseal_manifest(
        output,
        lambda value: value["config"].update({
            "digest": f"sha256:{new_config_digest}",
            "size": len(config_bytes),
        }),
    )

    with pytest.raises(
        ValueError,
        match="JSON (constant is invalid|float is not finite)",
    ):
        verify_oci_layout(
            output,
            expected_manifest_digest=expected_manifest,
        )


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b'{"value":' + b"9" * 101 + b'}', "integer is too large"),
        (b'{"value":1e400}', "float is not finite"),
        (("[" * 65 + "0" + "]" * 65).encode("utf-8"), "structure exceeds"),
        (json.dumps("x" * (1024 * 1024 + 1)).encode(), "string exceeds"),
    ],
)
def test_oci_json_parser_rejects_large_or_deep_values(raw, message):
    import core.agentic_v2_oci as module

    with pytest.raises(ValueError, match=message):
        module._json_loads(raw)


def test_oci_json_parser_rejects_node_limit():
    import core.agentic_v2_oci as module

    raw = ("[" + ",".join("0" for _ in range(500_000)) + "]").encode()
    with pytest.raises(ValueError, match="structure exceeds"):
        module._json_loads(raw)


def test_oci_export_rejects_layer_diff_id_mismatch(tmp_path):
    archive = tmp_path / "candidate.tar"
    _archive(archive)
    with tarfile.open(archive, "r") as source:
        manifest = json.loads(source.extractfile("manifest.json").read())[0]
        config_name = manifest["Config"]
        config = json.loads(source.extractfile(config_name).read())
        layer = source.extractfile(manifest["Layers"][0]).read()
    config["rootfs"]["diff_ids"] = ["sha256:" + "0" * 64]
    config_bytes = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    import hashlib

    config_name = f"{hashlib.sha256(config_bytes).hexdigest()}.json"
    manifest["Config"] = config_name
    broken = tmp_path / "broken.tar"
    with tarfile.open(broken, "w") as target:
        _add(target, "manifest.json", json.dumps([manifest], separators=(",", ":")).encode())
        _add(target, config_name, config_bytes)
        _add(target, manifest["Layers"][0], layer)

    with pytest.raises(ValueError, match="layer digest differs"):
        export_docker_archive_to_oci(broken, tmp_path / "broken-oci")


def test_oci_export_resolves_internal_docker_layer_symlink(tmp_path):
    archive = tmp_path / "candidate.tar"
    layer = _tar_bytes({"work/report.txt": b"done"})
    import hashlib

    diff_id = hashlib.sha256(layer).hexdigest()
    config = json.dumps({
        "architecture": "amd64",
        "os": "linux",
        "rootfs": {
            "type": "layers",
            "diff_ids": [f"sha256:{diff_id}", f"sha256:{diff_id}"],
        },
        "config": {},
    }, sort_keys=True, separators=(",", ":")).encode()
    config_digest = hashlib.sha256(config).hexdigest()
    manifest = json.dumps([{
        "Config": f"{config_digest}.json",
        "RepoTags": ["candidate:test"],
        "Layers": ["one/layer.tar", "two/layer.tar"],
    }], separators=(",", ":")).encode()
    with tarfile.open(archive, "w") as target:
        _add(target, "manifest.json", manifest)
        _add(target, f"{config_digest}.json", config)
        _add(target, "one/layer.tar", layer)
        link = tarfile.TarInfo("two/layer.tar")
        link.type = tarfile.SYMTYPE
        link.linkname = "../one/layer.tar"
        link.mtime = 0
        target.addfile(link)

    identity = export_docker_archive_to_oci(archive, tmp_path / "oci")

    assert identity["layer_count"] == 2


def test_oci_export_rejects_layer_symlink_escape(tmp_path):
    archive = tmp_path / "candidate.tar"
    config = json.dumps({
        "architecture": "amd64",
        "os": "linux",
        "rootfs": {"type": "layers", "diff_ids": ["sha256:" + "0" * 64]},
        "config": {},
    }, sort_keys=True, separators=(",", ":")).encode()
    import hashlib

    config_digest = hashlib.sha256(config).hexdigest()
    manifest = json.dumps([{
        "Config": f"{config_digest}.json",
        "RepoTags": ["candidate:test"],
        "Layers": ["layer/layer.tar"],
    }], separators=(",", ":")).encode()
    with tarfile.open(archive, "w") as target:
        _add(target, "manifest.json", manifest)
        _add(target, f"{config_digest}.json", config)
        link = tarfile.TarInfo("layer/layer.tar")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside.tar"
        target.addfile(link)

    with pytest.raises(ValueError, match="escapes archive"):
        export_docker_archive_to_oci(archive, tmp_path / "oci")


def test_oci_verifier_rejects_layer_size_limit(tmp_path, monkeypatch):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    import core.agentic_v2_oci as module

    monkeypatch.setattr(module, "MAX_LAYER_BYTES", 1)
    with pytest.raises(ValueError, match="layer exceeds size limit"):
        export_docker_archive_to_oci(archive, output)


def test_oci_verifier_rejects_symlinked_index(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    export_docker_archive_to_oci(archive, output)
    target = tmp_path / "index.json"
    (output / "index.json").rename(target)
    (output / "index.json").symlink_to(target)

    with pytest.raises((OSError, ValueError)):
        verify_oci_layout(output)


def test_oci_verifier_rejects_hardlinked_blob(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    export_docker_archive_to_oci(archive, output)
    index = json.loads((output / "index.json").read_text())
    digest = index["manifests"][0]["digest"].removeprefix("sha256:")
    blob = output / "blobs" / "sha256" / digest
    os.link(blob, tmp_path / "linked-blob")

    with pytest.raises(ValueError, match="OCI blob identity mismatch"):
        verify_oci_layout(output)


def test_oci_export_rejects_duplicate_archive_member(tmp_path):
    archive = tmp_path / "duplicate.tar"
    with tarfile.open(archive, "w") as target:
        _add(target, "manifest.json", b"[]")
        _add(target, "manifest.json", b"[]")

    with pytest.raises(ValueError, match="member inventory"):
        export_docker_archive_to_oci(archive, tmp_path / "oci")


def test_oci_verifier_rejects_duplicate_json_key(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    export_docker_archive_to_oci(archive, output)
    index = output / "index.json"
    value = index.read_text(encoding="utf-8").replace(
        '"schemaVersion":2', '"schemaVersion":2,"schemaVersion":2', 1
    )
    index.write_text(value, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate keys"):
        verify_oci_layout(output)


def test_oci_verifier_rejects_symlinked_intermediate_directory(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    export_docker_archive_to_oci(archive, output)
    target = tmp_path / "blobs"
    (output / "blobs").rename(target)
    (output / "blobs").symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="directory identity"):
        verify_oci_layout(output)


def test_oci_verifier_rejects_fifo_metadata_without_blocking(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    export_docker_archive_to_oci(archive, output)
    (output / "index.json").unlink()
    os.mkfifo(output / "index.json")

    with pytest.raises(ValueError, match="metadata file"):
        verify_oci_layout(output)


def test_oci_verifier_rejects_unreferenced_blob(tmp_path):
    archive = tmp_path / "candidate.tar"
    output = tmp_path / "oci"
    _archive(archive)
    export_docker_archive_to_oci(archive, output)
    (output / "blobs" / "sha256" / ("f" * 64)).write_bytes(b"extra")

    with pytest.raises(ValueError, match="blob inventory"):
        verify_oci_layout(output)


def test_oci_verifier_fails_closed_without_no_follow(monkeypatch):
    import core.agentic_v2_oci as module

    monkeypatch.setattr(module.os, "O_NOFOLLOW", 0)

    with pytest.raises(RuntimeError, match="secure Unix open flags"):
        module._secure_read_flags()


def test_oci_export_rejects_symlinked_archive(tmp_path):
    archive = tmp_path / "candidate.tar"
    _archive(archive)
    link = tmp_path / "candidate-link.tar"
    link.symlink_to(archive)

    with pytest.raises((OSError, ValueError)):
        export_docker_archive_to_oci(link, tmp_path / "oci")


def test_oci_export_rejects_hardlinked_archive(tmp_path):
    archive = tmp_path / "candidate.tar"
    _archive(archive)
    link = tmp_path / "candidate-hardlink.tar"
    os.link(archive, link)

    with pytest.raises(ValueError, match="regular file"):
        export_docker_archive_to_oci(link, tmp_path / "oci")


def test_oci_export_rejects_fifo_archive_without_blocking(tmp_path):
    archive = tmp_path / "candidate.tar"
    os.mkfifo(archive)

    with pytest.raises(ValueError, match="regular file"):
        export_docker_archive_to_oci(archive, tmp_path / "oci")