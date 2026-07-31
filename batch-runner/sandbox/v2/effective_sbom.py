"""Emit deterministic SPDX 2.3 for the full Phase 1B candidate inventory."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote


DEBIAN_STATUS_PATH = Path("/var/lib/dpkg/status")
_DEBIAN_FIELD_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*\Z", re.ASCII)
MAX_DEBIAN_FIELD_CHARS = 1024 * 1024


def _split_debian_stanzas(value: str) -> list[str]:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return re.split(r"\n[ \t]*\n+", normalized)


def _debian_fields(stanza: str) -> dict[str, str]:
    fields = {}
    current = None
    for line in stanza.splitlines():
        if line[:1].isspace():
            if current is None:
                raise RuntimeError("Debian status metadata is malformed")
            fields[current] += "\n" + line.strip()
            if len(fields[current]) > MAX_DEBIAN_FIELD_CHARS:
                raise RuntimeError("Debian status field is too large")
            continue
        if ":" not in line:
            if line:
                raise RuntimeError("Debian status metadata is malformed")
            continue
        key, value = line.split(":", 1)
        normalized = key.casefold()
        if _DEBIAN_FIELD_NAME.fullmatch(key) is None or normalized in fields:
            raise RuntimeError("Debian status field is invalid")
        fields[normalized] = value.strip()
        if len(fields[normalized]) > MAX_DEBIAN_FIELD_CHARS:
            raise RuntimeError("Debian status field is too large")
        current = normalized
    return fields


def _spdx_id(ecosystem: str, name: str, version: str) -> str:
    digest = hashlib.sha256(
        f"{ecosystem}\0{name}\0{version}".encode("utf-8")
    ).hexdigest()
    return f"SPDXRef-Package-{digest[:24]}"


def _package(
    ecosystem: str,
    name: str,
    version: str,
    license_value: str,
    purl: str,
) -> dict:
    return {
        "SPDXID": _spdx_id(ecosystem, name, version),
        "name": name,
        "versionInfo": version,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": license_value or "NOASSERTION",
        "supplier": "NOASSERTION",
        "externalRefs": [{
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceType": "purl",
            "referenceLocator": purl,
        }],
    }


def _debian_packages() -> list[dict]:
    status = DEBIAN_STATUS_PATH.read_text(
        encoding="utf-8", errors="strict"
    )
    packages = []
    for stanza in _split_debian_stanzas(status):
        fields = _debian_fields(stanza)
        if fields.get("status") != "install ok installed" or not fields.get("package"):
            continue
        name = fields["package"]
        version = fields.get("version")
        architecture = fields.get("architecture")
        if not version or not architecture:
            raise RuntimeError(f"Debian package identity is incomplete: {name}")
        purl = (
            f"pkg:deb/debian/{quote(name, safe='')}@{quote(version, safe='')}"
            f"?arch={quote(architecture, safe='')}"
        )
        packages.append(_package("deb", name, version, "NOASSERTION", purl))
    return packages


def _python_packages() -> list[dict]:
    packages = []
    seen = set()
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name") or distribution.name
        version = distribution.version
        identity = (name.lower(), version)
        if identity in seen:
            continue
        seen.add(identity)
        license_value = (
            distribution.metadata.get("License-Expression")
            or distribution.metadata.get("License")
            or "NOASSERTION"
        ).strip() or "NOASSERTION"
        packages.append(_package(
            "pypi",
            name,
            version,
            license_value[:500],
            f"pkg:pypi/{quote(name, safe='')}@{quote(version, safe='')}",
        ))
    return packages


def _r_packages() -> list[dict]:
    expression = (
        "p<-installed.packages();"
        "cat(apply(p[,c('Package','Version','License'),drop=FALSE],1,"
        "function(x) paste(x,collapse='\\t')),sep='\\n')"
    )
    completed = subprocess.run(
        ["Rscript", "--vanilla", "-e", expression],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=True,
    )
    packages = []
    for line in completed.stdout.decode("utf-8").splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            raise RuntimeError("R package inventory is malformed")
        name, version, license_value = parts
        packages.append(_package(
            "cran",
            name,
            version,
            license_value or "NOASSERTION",
            f"pkg:cran/{quote(name, safe='')}@{quote(version, safe='')}",
        ))
    return packages


def _npm_packages() -> list[dict]:
    package_path = Path("/usr/share/nodejs/npm/package.json")
    if not package_path.is_file():
        raise RuntimeError("npm package metadata is missing")
    document = json.loads(package_path.read_text(encoding="utf-8"))
    name = document.get("name")
    version = document.get("version")
    license_value = document.get("license") or "NOASSERTION"
    if not isinstance(name, str) or not isinstance(version, str):
        raise RuntimeError("npm package metadata is invalid")
    return [_package(
        "npm",
        name,
        version,
        str(license_value),
        f"pkg:npm/{quote(name, safe='')}@{quote(version, safe='')}",
    )]


def build_document() -> dict:
    packages = sorted(
        _debian_packages() + _python_packages() + _r_packages() + _npm_packages(),
        key=lambda item: item["SPDXID"],
    )
    namespace_digest = hashlib.sha256(
        json.dumps(packages, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "gdpval-agentic-v2-professional-work-candidate",
        "documentNamespace": (
            "https://github.com/hyeonsangjeon/gdpval-realworks/"
            f"sbom/agentic-v2-phase1b/{namespace_digest}"
        ),
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: gdpval-agentic-v2-effective-sbom-v1"],
        },
        "packages": packages,
        "relationships": [{
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": package["SPDXID"],
        } for package in packages],
    }


def main() -> None:
    print(json.dumps(build_document(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()