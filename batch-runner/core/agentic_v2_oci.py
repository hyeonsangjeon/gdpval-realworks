"""Host-owned OCI identity for local Agentic Sandbox V2 candidates."""

from __future__ import annotations

import hashlib
import json
import math
import os
import posixpath
import shutil
import stat
import tarfile
import tempfile
from pathlib import Path
from typing import Any, BinaryIO


OCI_LAYOUT_VERSION = "1.0.0"
OCI_MANIFEST_MEDIA_TYPE = "application/vnd.oci.image.manifest.v1+json"
OCI_CONFIG_MEDIA_TYPE = "application/vnd.oci.image.config.v1+json"
OCI_LAYER_MEDIA_TYPE = "application/vnd.oci.image.layer.v1.tar"
MAX_LAYER_BYTES = 16 * 1024 * 1024 * 1024
MAX_TOTAL_LAYER_BYTES = 64 * 1024 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10000


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def export_docker_archive_to_oci(
    archive_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    archive = Path(archive_path)
    output = Path(output_path)
    if output.exists() or output.is_symlink():
        raise ValueError("OCI output path must not already exist")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        blobs = temporary / "blobs" / "sha256"
        blobs.mkdir(parents=True)
        with _open_regular_archive(archive) as archive_stream, tarfile.open(
            fileobj=archive_stream, mode="r:"
        ) as source:
            members = source.getmembers()
            names = [member.name for member in members]
            if (
                len(members) > MAX_ARCHIVE_MEMBERS
                or len(names) != len(set(names))
                or any(
                    not name or len(name.encode("utf-8")) > 4096
                    for name in names
                )
            ):
                raise ValueError("Docker archive member inventory is invalid")
            manifest_bytes = _read_regular_member(source, "manifest.json", 16 * 1024 * 1024)
            manifest_list = _json_loads(manifest_bytes)
            if not isinstance(manifest_list, list) or len(manifest_list) != 1:
                raise ValueError("Docker archive must contain exactly one image")
            docker_manifest = manifest_list[0]
            if not isinstance(docker_manifest, dict) or set(docker_manifest) != {
                "Config", "RepoTags", "Layers"
            }:
                raise ValueError("Docker archive manifest is invalid")
            config_name = _safe_member_name(docker_manifest["Config"])
            layer_names = docker_manifest["Layers"]
            if (
                not isinstance(layer_names, list)
                or not layer_names
                or len(layer_names) != len(set(layer_names))
            ):
                raise ValueError("Docker archive layers are invalid")
            config_bytes = _read_regular_member(source, config_name, 64 * 1024 * 1024)
            config_digest = sha256_bytes(config_bytes)
            if Path(config_name).stem != config_digest:
                raise ValueError("Docker config filename does not match its digest")
            config = _json_loads(config_bytes)
            diff_ids = (config.get("rootfs") or {}).get("diff_ids")
            if not isinstance(diff_ids, list) or len(diff_ids) != len(layer_names):
                raise ValueError("Docker config rootfs identity is invalid")
            _write_blob(blobs, config_digest, config_bytes)
            layers = []
            total_layer_bytes = 0
            for index, raw_name in enumerate(layer_names):
                name = _safe_member_name(raw_name)
                member = _resolved_regular_member(source, name)
                if not member.isfile() or member.size < 0:
                    raise ValueError("Docker layer member is invalid")
                if member.size > MAX_LAYER_BYTES:
                    raise ValueError("Docker layer exceeds size limit")
                total_layer_bytes += member.size
                if total_layer_bytes > MAX_TOTAL_LAYER_BYTES:
                    raise ValueError("Docker layers exceed aggregate size limit")
                stream = source.extractfile(member)
                if stream is None:
                    raise ValueError("Docker layer cannot be opened")
                digest, size = _copy_blob(stream, blobs)
                if size != member.size:
                    raise ValueError("Docker layer byte count is invalid")
                if diff_ids[index] != f"sha256:{digest}":
                    raise ValueError("Docker layer digest differs from config diff ID")
                layers.append({
                    "mediaType": OCI_LAYER_MEDIA_TYPE,
                    "digest": f"sha256:{digest}",
                    "size": size,
                })
        oci_manifest = {
            "schemaVersion": 2,
            "mediaType": OCI_MANIFEST_MEDIA_TYPE,
            "config": {
                "mediaType": OCI_CONFIG_MEDIA_TYPE,
                "digest": f"sha256:{config_digest}",
                "size": len(config_bytes),
            },
            "layers": layers,
        }
        oci_manifest_bytes = canonical_json(oci_manifest)
        manifest_digest = sha256_bytes(oci_manifest_bytes)
        _write_blob(blobs, manifest_digest, oci_manifest_bytes)
        index = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [{
                "mediaType": OCI_MANIFEST_MEDIA_TYPE,
                "digest": f"sha256:{manifest_digest}",
                "size": len(oci_manifest_bytes),
            }],
        }
        (temporary / "oci-layout").write_bytes(canonical_json({
            "imageLayoutVersion": OCI_LAYOUT_VERSION,
        }))
        (temporary / "index.json").write_bytes(canonical_json(index))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return verify_oci_layout(output, expected_manifest_digest=f"sha256:{manifest_digest}")


def verify_oci_layout(
    layout_path: str | Path,
    *,
    expected_manifest_digest: str | None = None,
) -> dict[str, Any]:
    root = Path(layout_path)
    _require_directory(root)
    _require_directory(root / "blobs")
    _require_directory(root / "blobs" / "sha256")
    if _directory_names(root) != {"blobs", "index.json", "oci-layout"}:
        raise ValueError("OCI layout inventory is invalid")
    if _directory_names(root / "blobs") != {"sha256"}:
        raise ValueError("OCI blob directory inventory is invalid")
    layout = _json_loads(_read_regular_path(root / "oci-layout", 1024))
    if layout != {"imageLayoutVersion": OCI_LAYOUT_VERSION}:
        raise ValueError("OCI layout version is invalid")
    index_bytes = _read_regular_path(root / "index.json", 16 * 1024 * 1024)
    index = _json_loads(index_bytes)
    if not isinstance(index, dict) or set(index) != {
        "schemaVersion", "mediaType", "manifests"
    } or type(index["schemaVersion"]) is not int or index["schemaVersion"] != 2 or index["mediaType"] != (
        "application/vnd.oci.image.index.v1+json"
    ):
        raise ValueError("OCI index identity is invalid")
    manifests = index["manifests"]
    if not isinstance(manifests, list) or len(manifests) != 1:
        raise ValueError("OCI index must contain exactly one manifest")
    descriptor = manifests[0]
    if not isinstance(descriptor, dict) or set(descriptor) != {
        "mediaType", "digest", "size"
    } or descriptor["mediaType"] != OCI_MANIFEST_MEDIA_TYPE:
        raise ValueError("OCI manifest descriptor is invalid")
    manifest_bytes = _read_verified_blob(
        root, descriptor, maximum=16 * 1024 * 1024
    )
    if expected_manifest_digest is not None and descriptor["digest"] != expected_manifest_digest:
        raise ValueError("OCI manifest digest differs from expected identity")
    manifest = _json_loads(manifest_bytes)
    if not isinstance(manifest, dict) or set(manifest) != {
        "schemaVersion", "mediaType", "config", "layers"
    } or type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 2 or manifest["mediaType"] != OCI_MANIFEST_MEDIA_TYPE:
        raise ValueError("OCI image manifest is invalid")
    config_descriptor = manifest["config"]
    if (
        not isinstance(config_descriptor, dict)
        or set(config_descriptor) != {"mediaType", "digest", "size"}
        or config_descriptor["mediaType"] != OCI_CONFIG_MEDIA_TYPE
    ):
        raise ValueError("OCI config descriptor is invalid")
    config_bytes = _read_verified_blob(
        root, config_descriptor, maximum=64 * 1024 * 1024
    )
    config = _json_loads(config_bytes)
    layers = manifest["layers"]
    if (
        not isinstance(config, dict)
        or config.get("os") != "linux"
        or config.get("architecture") != "amd64"
        or not isinstance(layers, list)
        or not layers
    ):
        raise ValueError("OCI image layers are missing")
    rootfs = config.get("rootfs")
    if not isinstance(rootfs, dict) or rootfs.get("type") != "layers" or (
        rootfs.get("diff_ids") != [layer.get("digest") for layer in layers]
    ):
        raise ValueError("OCI config layer identity is invalid")
    total_layer_bytes = 0
    referenced_digests = {
        descriptor["digest"].removeprefix("sha256:"),
        config_descriptor["digest"].removeprefix("sha256:"),
    }
    for layer in layers:
        if not isinstance(layer, dict) or layer.get("mediaType") != OCI_LAYER_MEDIA_TYPE:
            raise ValueError("OCI layer media type is invalid")
        total_layer_bytes += _verify_blob(root, layer, maximum=MAX_LAYER_BYTES)
        referenced_digests.add(layer["digest"].removeprefix("sha256:"))
        if total_layer_bytes > MAX_TOTAL_LAYER_BYTES:
            raise ValueError("OCI layers exceed aggregate size limit")
    if _directory_names(root / "blobs" / "sha256") != referenced_digests:
        raise ValueError("OCI blob inventory differs from descriptors")
    return {
        "schema_version": "1.0",
        "manifest_digest": descriptor["digest"],
        "config_digest": manifest["config"]["digest"],
        "layer_count": len(layers),
        "platform": {
            "os": config.get("os"),
            "architecture": config.get("architecture"),
        },
        "index_sha256": sha256_bytes(index_bytes),
    }


def _safe_member_name(value: Any) -> str:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ValueError("Docker archive member name is invalid")
    path = Path(value)
    if any(part in {"", ".", ".."} for part in path.parts) or path.as_posix() != value:
        raise ValueError("Docker archive member path is unsafe")
    return value


def _open_regular_archive(path: Path):
    descriptor = os.open(path, _secure_read_flags())
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size <= 0
            or metadata.st_size > MAX_ARCHIVE_BYTES
        ):
            raise ValueError("Docker archive must be a regular file")
        return os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise


def _read_regular_member(source: tarfile.TarFile, name: str, maximum: int) -> bytes:
    member = _resolved_regular_member(source, name)
    if not member.isfile() or member.size < 0 or member.size > maximum:
        raise ValueError("Docker archive member size is invalid")
    stream = source.extractfile(member)
    if stream is None:
        raise ValueError("Docker archive member cannot be opened")
    value = stream.read(maximum + 1)
    if len(value) != member.size or len(value) > maximum:
        raise ValueError("Docker archive member bytes are invalid")
    return value


def _resolved_regular_member(
    source: tarfile.TarFile,
    name: str,
) -> tarfile.TarInfo:
    current_name = _safe_member_name(name)
    seen = set()
    for _ in range(16):
        if current_name in seen:
            raise ValueError("Docker archive member link cycle detected")
        seen.add(current_name)
        member = source.getmember(current_name)
        if member.isfile():
            return member
        if not (member.issym() or member.islnk()) or not member.linkname:
            raise ValueError("Docker archive member is not a regular file")
        if member.linkname.startswith("/"):
            raise ValueError("Docker archive member link escapes archive")
        base = posixpath.dirname(current_name) if member.issym() else ""
        normalized = posixpath.normpath(posixpath.join(base, member.linkname))
        if normalized == ".." or normalized.startswith("../"):
            raise ValueError("Docker archive member link escapes archive")
        current_name = _safe_member_name(normalized)
    raise ValueError("Docker archive member link depth exceeded")


def _copy_blob(source: BinaryIO, root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    descriptor, temporary_name = tempfile.mkstemp(prefix=".blob-", dir=root)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                target.write(chunk)
                size += len(chunk)
        hexdigest = digest.hexdigest()
        destination = root / hexdigest
        if destination.exists():
            if destination.stat().st_size != size or _sha256_file(destination) != hexdigest:
                raise ValueError("OCI blob collision detected")
            temporary.unlink()
        else:
            os.replace(temporary, destination)
        return hexdigest, size
    finally:
        temporary.unlink(missing_ok=True)


def _write_blob(root: Path, digest: str, value: bytes) -> None:
    if sha256_bytes(value) != digest:
        raise ValueError("OCI blob digest is invalid")
    path = root / digest
    if path.exists() and path.read_bytes() != value:
        raise ValueError("OCI blob collision detected")
    path.write_bytes(value)


def _read_verified_blob(
    root: Path,
    descriptor: Any,
    *,
    maximum: int,
) -> bytes:
    value, _size = _verified_blob(root, descriptor, maximum=maximum, collect=True)
    return value


def _verify_blob(
    root: Path,
    descriptor: Any,
    *,
    maximum: int,
) -> int:
    _value, size = _verified_blob(root, descriptor, maximum=maximum, collect=False)
    return size


def _verified_blob(
    root: Path,
    descriptor: Any,
    *,
    maximum: int,
    collect: bool,
) -> tuple[bytes, int]:
    if not isinstance(descriptor, dict) or set(descriptor) != {
        "mediaType", "digest", "size"
    }:
        raise ValueError("OCI blob descriptor is invalid")
    digest_value = descriptor["digest"]
    if not isinstance(digest_value, str) or not digest_value.startswith("sha256:"):
        raise ValueError("OCI blob digest format is invalid")
    digest = digest_value.removeprefix("sha256:")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("OCI blob digest format is invalid")
    path = root / "blobs" / "sha256" / digest
    flags = _secure_read_flags()
    descriptor_fd = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor_fd)
        size = metadata.st_size
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or type(descriptor["size"]) is not int
            or descriptor["size"] < 0
            or size != descriptor["size"]
            or size > maximum
        ):
            raise ValueError("OCI blob identity mismatch")
        digest_state = hashlib.sha256()
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor_fd, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            digest_state.update(chunk)
            if collect:
                chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise ValueError("OCI blob exceeds size limit")
        if total != size or digest_state.hexdigest() != digest:
            raise ValueError("OCI blob identity mismatch")
        return b"".join(chunks), total
    finally:
        os.close(descriptor_fd)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_directory(path: Path) -> None:
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or path.is_symlink():
        raise ValueError("OCI directory identity is invalid")


def _directory_names(path: Path) -> set[str]:
    with os.scandir(path) as entries:
        return {entry.name for entry in entries}


def _secure_read_flags() -> int:
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    if os.name != "posix" or any(
        not isinstance(getattr(os, name, None), int)
        or getattr(os, name) <= 0
        for name in required
    ):
        raise RuntimeError("OCI verification requires secure Unix open flags")
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def _read_regular_path(path: Path, maximum: int) -> bytes:
    flags = _secure_read_flags()
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size < 0
            or metadata.st_size > maximum
        ):
            raise ValueError("OCI metadata file is invalid")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise ValueError("OCI metadata file exceeds size limit")
        if total != metadata.st_size:
            raise ValueError("OCI metadata file changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _json_loads(value: bytes):
    def reject_duplicates(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("JSON object contains duplicate keys")
            result[key] = item
        return result

    def bounded_int(raw):
        if len(raw.lstrip("-")) > 100:
            raise ValueError("JSON integer is too large")
        return int(raw)

    def reject_constant(raw):
        raise ValueError(f"JSON constant is invalid: {raw}")

    def bounded_float(raw):
        if len(raw) > 100:
            raise ValueError("JSON float is too large")
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("JSON float is not finite")
        return value

    try:
        document = json.loads(
            value,
            object_pairs_hook=reject_duplicates,
            parse_int=bounded_int,
            parse_float=bounded_float,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise ValueError("JSON document is invalid") from exc
    stack = [(document, 1)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > 500_000 or depth > 64:
            raise ValueError("JSON document structure exceeds limits")
        if isinstance(item, str) and len(item) > 1024 * 1024:
            raise ValueError("JSON string exceeds size limit")
        if isinstance(item, dict):
            stack.extend((key, depth + 1) for key in item)
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return document