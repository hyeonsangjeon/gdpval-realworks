"""Emit a deterministic SPDX 2.3 SBOM from image-local package metadata."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path


def _spdx_id(kind: str, name: str, version: str) -> str:
    digest = hashlib.sha256(f"{kind}\0{name}\0{version}".encode("utf-8")).hexdigest()
    return f"SPDXRef-Package-{digest[:24]}"


def _package(kind: str, name: str, version: str) -> dict:
    return {
        "SPDXID": _spdx_id(kind, name, version),
        "name": name,
        "versionInfo": version,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "supplier": "NOASSERTION",
        "externalRefs": [{
            "referenceCategory": "PACKAGE-MANAGER",
            "referenceType": "purl",
            "referenceLocator": f"pkg:{kind}/{name}@{version}",
        }],
    }


def _python_packages() -> list[dict]:
    packages = {
        (distribution.metadata.get("Name") or distribution.name, distribution.version)
        for distribution in importlib.metadata.distributions()
    }
    return [
        _package("pypi", name, version)
        for name, version in sorted(packages, key=lambda item: item[0].lower())
    ]


def _debian_packages() -> list[dict]:
    status_path = Path("/var/lib/dpkg/status")
    if not status_path.is_file():
        return []
    packages = []
    for stanza in status_path.read_text(encoding="utf-8", errors="replace").split("\n\n"):
        fields = {}
        for line in stanza.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                fields[key] = value
        if fields.get("Status") == "install ok installed" and fields.get("Package"):
            packages.append(_package(
                "deb/debian",
                fields["Package"],
                fields.get("Version", "NOASSERTION"),
            ))
    return sorted(packages, key=lambda package: package["name"])


def main() -> None:
    packages = _debian_packages() + _python_packages()
    namespace_digest = hashlib.sha256(
        json.dumps(packages, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "gdpval-agentic-sandbox",
        "documentNamespace": (
            "https://github.com/hyeonsangjeon/gdpval-realworks/"
            f"sbom/gdpval-agentic-sandbox/{namespace_digest}"
        ),
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: gdpval-agentic-sbom-v1"],
        },
        "packages": packages,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": package["SPDXID"],
            }
            for package in packages
        ],
    }
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()