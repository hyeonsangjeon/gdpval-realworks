"""Collect deterministic package-license evidence from the candidate image."""

from __future__ import annotations

import errno
import hashlib
from email.header import Header
from email.parser import BytesParser
from email.policy import compat32
import json
import os
import re
import stat
import sysconfig
from pathlib import Path
from urllib.parse import quote


MAX_EVIDENCE_FILE_BYTES = 64 * 1024 * 1024
PYTHON_PURELIB_PATH = "/usr/local/lib/python3.11/site-packages"
DEBIAN_STATUS_PATH = Path("/var/lib/dpkg/status")
DEBIAN_DOCUMENTATION_ROOT = Path("/usr/share/doc")
R_LIBRARY_ROOT = Path("/usr/lib/R/library")
R_RUNTIME_COPYRIGHT_PATH = Path("/usr/share/doc/r-base-core/copyright")
R_SHARED_LICENSE_ROOT = Path("/usr/share/R/share/licenses")
NPM_PACKAGE_PATH = Path("/usr/share/nodejs/npm/package.json")
DEP5_FORMAT_URI = (
    "https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
)
_DEBIAN_FIELD_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*\Z", re.ASCII)
_DEBIAN_COPYRIGHT_FIELD_LIKE = re.compile(
    r"^\s*(?:Format|Upstream-Name|Upstream-Contact|Source|Disclaimer|Comment|"
    r"License|Copyright|Files|Files-Excluded(?:-[A-Za-z0-9.+-]+)?)\s*:",
    re.IGNORECASE | re.ASCII,
)
_R_FIELD_NAME = re.compile(r"[A-Za-z][A-Za-z0-9._-]*\Z", re.ASCII)
_R_LICENSE_REFERENCE = re.compile(
    r"file ([A-Za-z0-9][A-Za-z0-9._+-]*)\Z", re.ASCII
)
_NPM_LICENSE_REFERENCE = re.compile(
    r"SEE LICENSE IN ([A-Za-z0-9][A-Za-z0-9._+-]*)\Z", re.ASCII
)
_LICENSE_FILE_TOKEN = re.compile(
    rb"(?<![A-Za-z0-9.+-])"
    rb"([A-Za-z0-9](?:[A-Za-z0-9.+-]{0,126}[A-Za-z0-9+])?)"
    rb"(?![A-Za-z0-9+-])"
)
_LICENSE_FILE_TOKEN_TEXT = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9.+-]{0,126}[A-Za-z0-9+])?\Z",
    re.ASCII,
)
MAX_LICENSE_FILE_TOKENS = 4096
MAX_DEBIAN_FIELD_CHARS = 1024 * 1024


class _UnavailableEvidencePath(RuntimeError):
    def __init__(self, path: Path, error_number: int):
        super().__init__(f"license evidence path is not symlink-free: {path}")
        self.error_number = error_number


def _split_debian_stanzas(value: str) -> list[str]:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return re.split(r"\n[ \t]*\n+", normalized)


def _canonical_json(value) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _read_regular_file(
    source: str,
    path: Path,
    *,
    allowed_roots: tuple[Path, ...],
) -> tuple[dict, bytes]:
    lexical = Path(path)
    roots = [Path(root) for root in allowed_roots]
    if (
        not lexical.is_absolute()
        or ".." in lexical.parts
        or any(not root.is_absolute() or ".." in root.parts for root in roots)
    ):
        raise RuntimeError(f"license evidence path is not absolute: {lexical}")
    if not any(root in (lexical, *lexical.parents) for root in roots):
        raise RuntimeError(f"license evidence escapes allowlisted root: {lexical}")
    required_flags = ("O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK", "O_DIRECTORY")
    if any(not isinstance(getattr(os, name, None), int) for name in required_flags):
        raise RuntimeError("secure Unix open flags are required for license evidence")
    directory_flags = (
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    )
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    directory_descriptor = None
    descriptor = None
    try:
        directory_descriptor = os.open("/", directory_flags)
        for component in lexical.parts[1:-1]:
            next_descriptor = os.open(
                component,
                directory_flags,
                dir_fd=directory_descriptor,
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        descriptor = os.open(
            lexical.name,
            file_flags,
            dir_fd=directory_descriptor,
        )
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ELOOP, errno.ENOTDIR}:
            raise _UnavailableEvidencePath(lexical, exc.errno) from exc
        raise RuntimeError(f"license evidence path cannot be opened: {lexical}") from exc
    finally:
        if directory_descriptor is not None:
            os.close(directory_descriptor)
    if descriptor is None:
        raise RuntimeError(f"license evidence path cannot be opened: {lexical}")
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size < 0
            or before.st_size > MAX_EVIDENCE_FILE_BYTES
        ):
            raise RuntimeError(f"license evidence file is invalid: {lexical}")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, MAX_EVIDENCE_FILE_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_EVIDENCE_FILE_BYTES:
                raise RuntimeError(f"license evidence file is too large: {lexical}")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    def identity(value):
        return (
            value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns,
        )
    if identity(before) != identity(after) or total != before.st_size:
        raise RuntimeError(f"license evidence file changed while reading: {lexical}")
    value = b"".join(chunks)
    evidence = {
        "source": source,
        "path": str(lexical),
        "resolved_path": str(lexical),
        "sha256": hashlib.sha256(value).hexdigest(),
        "size": total,
    }
    return evidence, value


def _regular_file_evidence(
    source: str,
    path: Path,
    *,
    allowed_roots: tuple[Path, ...] | None = None,
) -> dict:
    evidence, _value = _read_regular_file(
        source,
        path,
        allowed_roots=allowed_roots or (path.parent,),
    )
    return evidence


def _virtual_evidence(source: str, value: dict) -> dict:
    encoded = _canonical_json(value)
    return {
        "source": source,
        "path": None,
        "resolved_path": None,
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size": len(encoded),
    }


def _unverifiable_path_evidence(source: str, path: Path) -> dict:
    encoded = _canonical_json({
        "path": str(path),
        "reason": "symlink-or-nondirectory",
    })
    return {
        "source": source,
        "path": str(path),
        "resolved_path": None,
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size": len(encoded),
    }


def _license_file_tokens(value: bytes) -> list[str]:
    tokens = sorted({
        match.group(1).decode("ascii")
        for match in _LICENSE_FILE_TOKEN.finditer(value)
        if b"-" in match.group(1)
    })
    if len(tokens) > MAX_LICENSE_FILE_TOKENS:
        raise RuntimeError("license evidence file has too many identifier tokens")
    return tokens


def _debian_fields(
    stanza: str,
    source: str,
    *,
    allow_noncritical_duplicates: bool = False,
) -> dict[str, str]:
    fields = {}
    current = None
    for line in stanza.splitlines():
        if line.startswith("#"):
            continue
        if line[:1].isspace():
            if current is None:
                raise RuntimeError(f"Debian {source} metadata is malformed")
            fields[current] += "\n" + line.strip()
            if len(fields[current]) > MAX_DEBIAN_FIELD_CHARS:
                raise RuntimeError(f"Debian {source} field is too large")
            continue
        if ":" not in line:
            if line:
                raise RuntimeError(f"Debian {source} metadata is malformed")
            continue
        key, value = line.split(":", 1)
        normalized = key.casefold()
        if _DEBIAN_FIELD_NAME.fullmatch(key) is None:
            raise RuntimeError(f"Debian {source} field name is malformed")
        if normalized in fields:
            if not allow_noncritical_duplicates or normalized in {"format", "license"}:
                raise RuntimeError(f"Debian {source} field is duplicated")
            fields[normalized] += "\n" + value.strip()
        else:
            fields[normalized] = value.strip()
        if len(fields[normalized]) > MAX_DEBIAN_FIELD_CHARS:
            raise RuntimeError(f"Debian {source} field is too large")
        current = normalized
    return {key: value.strip() for key, value in fields.items()}


def _debian_license_values(value: bytes, source: str) -> list[str]:
    text = value.decode("utf-8", errors="strict")
    return sorted({
        fields["license"]
        for stanza in _split_debian_stanzas(text)
        for fields in [_debian_fields(stanza, source)]
        if fields.get("license")
    })


def _validate_unstructured_debian_field_names(text: str) -> None:
    for line in text.splitlines():
        if (
            line
            and not line[0].isspace()
            and _DEBIAN_COPYRIGHT_FIELD_LIKE.match(line)
            and _DEBIAN_FIELD_NAME.fullmatch(line.split(":", 1)[0]) is None
        ):
            raise RuntimeError("Debian copyright field name is malformed")


def _debian_copyright_metadata(
    value: bytes,
    *,
    require_canonical_format: bool = False,
) -> tuple[str | None, list[str]]:
    text = value.decode("utf-8", errors="strict")
    stanzas = _split_debian_stanzas(text)
    first_lines = stanzas[0].splitlines()
    format_lines = [
        line for line in first_lines
        if line.casefold().startswith("format:")
    ]
    if not format_lines:
        if require_canonical_format:
            raise RuntimeError("Debian copyright DEP-5 Format header is invalid")
        _validate_unstructured_debian_field_names(text)
        return None, []
    preliminary_format = format_lines[0].split(":", 1)[1].strip()
    if not preliminary_format:
        raise RuntimeError("Debian copyright DEP-5 Format header is invalid")
    if preliminary_format != DEP5_FORMAT_URI:
        if require_canonical_format:
            raise RuntimeError("Debian copyright DEP-5 Format header is invalid")
        _validate_unstructured_debian_field_names(text)
        return None, []
    if any(
        lines and all(line[0].isspace() for line in lines)
        for stanza in stanzas
        for lines in [[
            line for line in stanza.splitlines()
            if line and not line.startswith("#")
        ]]
    ):
        if require_canonical_format:
            raise RuntimeError("Debian copyright metadata is malformed")
        return None, []
    first_fields = _debian_fields(
        stanzas[0],
        "copyright",
        allow_noncritical_duplicates=True,
    )
    format_value = first_fields.get("format")
    if format_value != DEP5_FORMAT_URI:
        raise RuntimeError("Debian copyright DEP-5 Format header is invalid")
    license_fields = []
    for index, stanza in enumerate(stanzas):
        fields = _debian_fields(
            stanza,
            "copyright",
            allow_noncritical_duplicates=True,
        )
        if "format" in fields:
            if index != 0 or fields["format"] != format_value:
                raise RuntimeError("Debian copyright Format field is duplicated")
        if fields.get("license"):
            license_fields.append(fields["license"])
    return format_value, sorted(set(license_fields))


def _debian_records() -> list[dict]:
    status_path = DEBIAN_STATUS_PATH
    status_evidence, status_bytes = _read_regular_file(
        "debian-status", status_path, allowed_roots=(status_path.parent,)
    )
    status = status_bytes.decode("utf-8", errors="strict")
    records = []
    for stanza in _split_debian_stanzas(status):
        fields = _debian_fields(stanza, "status")
        if fields.get("status") != "install ok installed" or not fields.get("package"):
            continue
        name = fields["package"]
        version = fields.get("version")
        architecture = fields.get("architecture")
        if not version or not architecture:
            raise RuntimeError(f"Debian package identity is incomplete: {name}")
        copyright_path = DEBIAN_DOCUMENTATION_ROOT / name / "copyright"
        evidence = []
        license_fields = []
        format_value = None
        try:
            copyright_evidence, copyright_bytes = _read_regular_file(
                "debian-copyright",
                copyright_path,
                allowed_roots=(DEBIAN_DOCUMENTATION_ROOT,),
            )
        except _UnavailableEvidencePath as exc:
            if exc.error_number in {errno.ELOOP, errno.ENOTDIR}:
                evidence.append(_unverifiable_path_evidence(
                    "debian-copyright-path-unverifiable",
                    copyright_path,
                ))
            elif exc.error_number != errno.ENOENT:
                raise
        else:
            evidence.append(copyright_evidence)
            format_value, license_fields = _debian_copyright_metadata(
                copyright_bytes
            )
        records.append({
            "ecosystem": "debian",
            "package": name,
            "version": version,
            "purl": (
                f"pkg:deb/debian/{quote(name, safe='')}@{quote(version, safe='')}"
                f"?arch={quote(architecture, safe='')}"
            ),
            "raw_values": license_fields,
            "metadata": {
                "architecture": architecture,
                "copyright_format": format_value,
            },
            "evidence": evidence,
        })
        records[-1]["evidence"].insert(0, status_evidence)
    return records


def _python_license_files(
    distribution_root: Path,
    declared_files: list[str],
    site_root: Path,
) -> tuple[list[dict], list[str], list[dict]]:
    if (
        not distribution_root.is_absolute()
        or ".." in distribution_root.parts
        or site_root not in (distribution_root, *distribution_root.parents)
    ):
        raise RuntimeError("Python distribution metadata root is invalid")
    records = []
    tokens = set()
    selections = []
    seen = set()
    for raw_path in declared_files:
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
            raise RuntimeError("Python License-File metadata is invalid")
        for candidate in (
            distribution_root / "licenses" / raw_path,
            distribution_root / raw_path,
        ):
            if ".." in candidate.parts:
                raise RuntimeError("Python license evidence escapes distribution metadata")
            if str(candidate) in seen:
                continue
            try:
                evidence, file_bytes = _read_regular_file(
                    "python-license-file", candidate, allowed_roots=(distribution_root,)
                )
            except _UnavailableEvidencePath as exc:
                if exc.error_number == errno.ENOENT:
                    continue
                raise
            seen.add(str(candidate))
            records.append(evidence)
            tokens.update(_license_file_tokens(file_bytes))
            selections.append({
                "declared": raw_path,
                "path": str(candidate),
            })
            break
        else:
            raise RuntimeError(f"Python License-File is missing: {raw_path}")
    return (
        sorted(records, key=lambda item: (item["path"], item["sha256"])),
        sorted(tokens),
        sorted(selections, key=lambda item: (item["declared"], item["path"])),
    )


def _python_records() -> list[dict]:
    records = []
    seen = set()
    if sysconfig.get_path("purelib") != PYTHON_PURELIB_PATH:
        raise RuntimeError("Python purelib root differs from candidate contract")
    site_root = Path(PYTHON_PURELIB_PATH)
    if not site_root.is_dir() or site_root.is_symlink():
        raise RuntimeError("Python site-packages root is missing")
    metadata_paths = []
    for child in sorted(site_root.iterdir(), key=lambda value: value.name):
        if child.name.endswith(".dist-info"):
            metadata_paths.append(child / "METADATA")
        elif child.name.endswith(".egg-info"):
            metadata_paths.append(child / "PKG-INFO")
    for metadata_path in metadata_paths:
        metadata_evidence, metadata_bytes = _read_regular_file(
            "python-metadata", metadata_path, allowed_roots=(site_root,)
        )
        metadata_bytes.decode("utf-8", errors="strict")
        metadata = BytesParser(policy=compat32).parsebytes(metadata_bytes, headersonly=True)
        if metadata.defects or any(
            _DEBIAN_FIELD_NAME.fullmatch(key) is None for key in metadata.keys()
        ):
            raise RuntimeError(f"Python package metadata is malformed: {metadata_path}")
        def metadata_values(key):
            values = metadata.get_all(key, [])
            if any(not isinstance(value, (str, Header)) for value in values):
                raise RuntimeError(
                    f"Python package metadata value is invalid: {metadata_path}"
                )
            return [str(value) for value in values]

        names = metadata_values("Name")
        versions = metadata_values("Version")
        licenses = metadata_values("License")
        expressions = metadata_values("License-Expression")
        if (
            len(names) != 1
            or len(versions) != 1
            or len(licenses) > 1
            or len(expressions) > 1
        ):
            raise RuntimeError(f"Python single-use metadata is duplicated: {metadata_path}")
        name = names[0].strip()
        version = versions[0].strip()
        if not name or not version:
            raise RuntimeError(f"Python package identity is missing: {metadata_path}")
        identity = (name.lower(), version)
        if identity in seen:
            raise RuntimeError(f"Python distribution identity is duplicated: {name}=={version}")
        seen.add(identity)
        license_expression = expressions[0] if expressions else None
        license_value = licenses[0] if licenses else None
        classifiers = sorted({
            value
            for value in metadata_values("Classifier")
            if value.startswith("License ::")
        })
        declared_files = metadata_values("License-File")
        raw_values = []
        if isinstance(license_expression, str) and license_expression.strip():
            raw_values.append(license_expression.strip())
        if isinstance(license_value, str) and license_value.strip():
            raw_values.append(license_value.strip())
        raw_values.extend(classifiers)
        evidence = [metadata_evidence]
        license_evidence, license_file_tokens, license_file_selections = (
            _python_license_files(
            metadata_path.parent, declared_files, site_root
            )
        )
        evidence.extend(license_evidence)
        raw_values.extend(license_file_tokens)
        records.append({
            "ecosystem": "python",
            "package": name,
            "version": version,
            "purl": f"pkg:pypi/{quote(name, safe='')}@{quote(version, safe='')}",
            "raw_values": raw_values,
            "metadata": {
                "license_expression": license_expression,
                "license": license_value,
                "classifiers": classifiers,
                "license_file_tokens": license_file_tokens,
                "license_files": license_file_selections,
            },
            "evidence": evidence,
        })
    return records


def _parse_r_dcf(value: bytes) -> dict[str, str]:
    fields: dict[str, str] = {}
    identities = set()
    known_fields = {
        "license": "License",
        "package": "Package",
        "priority": "Priority",
        "version": "Version",
    }
    key = None
    record_ended = False
    for line in value.decode("utf-8", errors="strict").splitlines():
        if not line:
            record_ended = True
            key = None
            continue
        if record_ended:
            raise RuntimeError("R DESCRIPTION contains multiple records")
        if line[:1].isspace() and key is not None:
            fields[key] += "\n" + line.strip()
        elif line[:1].isspace():
            raise RuntimeError("R DESCRIPTION metadata is malformed")
        elif ":" in line:
            raw_key, raw = line.split(":", 1)
            if _R_FIELD_NAME.fullmatch(raw_key) is None:
                raise RuntimeError("R DESCRIPTION field name is malformed")
            identity = raw_key.casefold()
            if identity in identities:
                raise RuntimeError("R DESCRIPTION field is duplicated")
            identities.add(identity)
            key = known_fields.get(identity, raw_key)
            fields[key] = raw.strip()
        elif line:
            raise RuntimeError("R DESCRIPTION metadata is malformed")
    return fields


def _r_records() -> list[dict]:
    library_root = R_LIBRARY_ROOT
    if not library_root.is_dir():
        raise RuntimeError("R library root is missing")

    base_description_path = library_root / "base" / "DESCRIPTION"
    base_evidence, base_bytes = _read_regular_file(
        "r-runtime-description", base_description_path,
        allowed_roots=(library_root,)
    )
    base_fields = _parse_r_dcf(base_bytes)
    runtime_version = base_fields.get("Version")
    if not runtime_version:
        raise RuntimeError("R runtime version is missing")
    runtime_license = ""
    runtime_value = {"version": runtime_version, "license": runtime_license}
    runtime_copyright = R_RUNTIME_COPYRIGHT_PATH
    runtime_copyright_evidence, runtime_copyright_bytes = _read_regular_file(
        "r-runtime-copyright",
        runtime_copyright,
        allowed_roots=(runtime_copyright.parent,),
    )
    runtime_copyright_format, runtime_license_fields = (
        _debian_copyright_metadata(runtime_copyright_bytes)
    )
    shared = []
    shared_root = R_SHARED_LICENSE_ROOT
    if shared_root.is_dir():
        for path in sorted(shared_root.iterdir(), key=lambda value: value.name):
            if path.is_file():
                shared.append(_regular_file_evidence(
                    "r-shared-license", path, allowed_roots=(shared_root,)
                ))
    records = []
    for package_root in sorted(library_root.iterdir(), key=lambda value: value.name):
        description_path = package_root / "DESCRIPTION"
        if not description_path.is_file():
            continue
        description_evidence, description_bytes = _read_regular_file(
            "r-description", description_path, allowed_roots=(library_root,)
        )
        fields = _parse_r_dcf(description_bytes)
        name = fields.get("Package")
        version = fields.get("Version")
        license_value = fields.get("License")
        priority = fields.get("Priority")
        if not all(isinstance(item, str) and item for item in (name, version, license_value)):
            raise RuntimeError(f"R package license metadata is incomplete: {description_path}")
        evidence = [description_evidence, base_evidence]
        evidence.append(_virtual_evidence("r-runtime-license", runtime_value))
        evidence.append(runtime_copyright_evidence)
        evidence.extend(shared)
        license_file_tokens = []
        reference = _R_LICENSE_REFERENCE.fullmatch(license_value)
        if reference is not None:
            license_file_evidence, license_file_bytes = _read_regular_file(
                "r-license-file",
                package_root / reference.group(1),
                allowed_roots=(package_root,),
            )
            evidence.append(license_file_evidence)
            license_file_tokens = _license_file_tokens(license_file_bytes)
        records.append({
            "ecosystem": "r",
            "package": name,
            "version": version,
            "purl": f"pkg:cran/{quote(name, safe='')}@{quote(version, safe='')}",
            "raw_values": [
                value for value in [
                    license_value,
                    runtime_license,
                    *runtime_license_fields,
                    *license_file_tokens,
                ]
                if value
            ],
            "metadata": {
                "declared_license": license_value,
                "priority": priority or None,
                "runtime_license": runtime_license,
                "runtime_license_fields": runtime_license_fields,
                "runtime_copyright_format": runtime_copyright_format,
                "runtime_version": runtime_version,
                "license_file_tokens": license_file_tokens,
            },
            "evidence": evidence,
        })
    return records


def _npm_records() -> list[dict]:
    package_path = NPM_PACKAGE_PATH
    package_evidence, package_bytes = _read_regular_file(
        "npm-package-json", package_path, allowed_roots=(package_path.parent,)
    )
    def reject_duplicates(pairs):
        document = {}
        for key, value in pairs:
            if key in document:
                raise RuntimeError("npm package metadata field is duplicated")
            document[key] = value
        return document

    package_text = package_bytes.decode("utf-8", errors="strict")
    document = json.loads(
        package_text,
        object_pairs_hook=reject_duplicates,
        parse_constant=lambda value: (_ for _ in ()).throw(
            RuntimeError(f"npm package metadata constant is invalid: {value}")
        ),
    )
    name = document.get("name")
    version = document.get("version")
    license_value = document.get("license")
    if not all(
        isinstance(value, str) and value and value == value.strip()
        for value in (name, version, license_value)
    ):
        raise RuntimeError("npm license metadata is invalid")
    evidence = [package_evidence]
    license_file_tokens = []
    reference = _NPM_LICENSE_REFERENCE.fullmatch(license_value)
    if reference is not None:
        license_file_evidence, license_file_bytes = _read_regular_file(
            "npm-license-file",
            package_path.parent / reference.group(1),
            allowed_roots=(package_path.parent,),
        )
        evidence.append(license_file_evidence)
        license_file_tokens = _license_file_tokens(license_file_bytes)
    return [{
        "ecosystem": "npm",
        "package": name,
        "version": version,
        "purl": f"pkg:npm/{quote(name, safe='')}@{quote(version, safe='')}",
        "raw_values": [license_value, *license_file_tokens],
        "metadata": {
            "license": license_value,
            "license_file_tokens": license_file_tokens,
        },
        "evidence": evidence,
    }]


def collect() -> dict:
    if os.geteuid() != 65532 or os.getegid() != 65532:
        raise RuntimeError("Phase 1C license evidence must run as UID/GID 65532")
    records = sorted(
        _debian_records() + _python_records() + _r_records() + _npm_records(),
        key=lambda item: item["purl"],
    )
    document = {
        "schema_version": "1.0",
        "collector": "gdpval-agentic-v2-license-evidence-v1",
        "records": records,
    }
    document["records_sha256"] = _canonical_sha256(records)
    return document


def main() -> None:
    print(json.dumps(collect(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()