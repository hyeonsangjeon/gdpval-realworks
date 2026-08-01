"""Strict identity contracts for the Agentic Sandbox V2 Phase 1B substrate."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SUBSTRATE_SCHEMA_VERSION = "1.0"
SUBSTRATE_ID = "professional-work-v1"
AGENTIC_V2_IMAGE_PROBE_COUNT = 3
AGENTIC_V2_IMAGE_PROBE_TIMEOUT_SECONDS = 900
AGENTIC_V2_SHORT_DOCKER_COMMAND_LIMIT = 64
AGENTIC_V2_SHORT_DOCKER_TIMEOUT_SECONDS = 60
AGENTIC_V2_GIT_COMMAND_LIMIT = 64
AGENTIC_V2_GIT_TIMEOUT_SECONDS = 30
AGENTIC_V2_EVIDENCE_ROOT_COPY_LIMIT = 6
AGENTIC_V2_EVIDENCE_ROOT_COPY_TIMEOUT_SECONDS = 900
AGENTIC_V2_VERIFICATION_SESSION_MAX_CONTAINERS = 16
AGENTIC_V2_VERIFICATION_SESSION_SWEEP_LIMIT = 3
AGENTIC_V2_VERIFICATION_SESSION_INVENTORY_TIMEOUT_SECONDS = 60
AGENTIC_V2_VERIFICATION_SESSION_REMOVE_TIMEOUT_SECONDS = 30
AGENTIC_V2_HOST_VALIDATION_BUDGET_SECONDS = 1800
AGENTIC_V2_VERIFIER_OVERHEAD_SECONDS = (
    AGENTIC_V2_SHORT_DOCKER_COMMAND_LIMIT
    * AGENTIC_V2_SHORT_DOCKER_TIMEOUT_SECONDS
    + AGENTIC_V2_GIT_COMMAND_LIMIT * AGENTIC_V2_GIT_TIMEOUT_SECONDS
    + AGENTIC_V2_EVIDENCE_ROOT_COPY_LIMIT
    * AGENTIC_V2_EVIDENCE_ROOT_COPY_TIMEOUT_SECONDS
    + (AGENTIC_V2_VERIFICATION_SESSION_SWEEP_LIMIT + 1)
    * AGENTIC_V2_VERIFICATION_SESSION_INVENTORY_TIMEOUT_SECONDS
    + AGENTIC_V2_VERIFICATION_SESSION_MAX_CONTAINERS
    * AGENTIC_V2_VERIFICATION_SESSION_SWEEP_LIMIT
    * AGENTIC_V2_VERIFICATION_SESSION_REMOVE_TIMEOUT_SECONDS
    + AGENTIC_V2_HOST_VALIDATION_BUDGET_SECONDS
)
AGENTIC_V2_VERIFIER_TIMEOUT_SECONDS = (
    AGENTIC_V2_IMAGE_PROBE_COUNT * AGENTIC_V2_IMAGE_PROBE_TIMEOUT_SECONDS
    + AGENTIC_V2_VERIFIER_OVERHEAD_SECONDS
)
REQUIRED_CAPABILITY_FAMILIES = frozenset({
    "browser-local",
    "cad-dxf",
    "compilers",
    "data-science",
    "documents",
    "fonts",
    "gis",
    "machine-learning",
    "media",
    "ocr",
    "pdf",
    "presentations",
    "programming",
    "shell",
    "spreadsheets",
})
REQUIRED_COMMANDS = frozenset({
    "Rscript",
    "bash",
    "chromium",
    "cmake",
    "ffmpeg",
    "ffprobe",
    "g++",
    "gcc",
    "gdalinfo",
    "gfortran",
    "libreoffice",
    "make",
    "node",
    "npm",
    "ogr2ogr",
    "pandoc",
    "pdftoppm",
    "pdftotext",
    "python",
    "tesseract",
})
REQUIRED_PYTHON_MODULES = frozenset({
    "PIL",
    "av",
    "ezdxf",
    "geopandas",
    "matplotlib",
    "numpy",
    "openpyxl",
    "pandas",
    "pptx",
    "reportlab",
    "scipy",
    "sklearn",
    "weasyprint",
})
REQUIRED_FONT_FAMILIES = (
    "DejaVu Sans",
    "Liberation Sans",
    "Noto Sans CJK KR",
)
REQUIRED_SMOKES = frozenset({
    "browser-local-screenshot",
    "compiler-matrix",
    "data-ml-fit",
    "dxf-roundtrip",
    "gis-geopackage",
    "media-generate-probe",
    "ocr-local-image",
    "office-pdf-roundtrip",
    "spreadsheet-formula-roundtrip",
})
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class AgenticV2SubstrateManifest:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def from_mapping(cls, value: Any) -> "AgenticV2SubstrateManifest":
        document = _validate_manifest(value)
        return cls(document=document, sha256=canonical_sha256(document))

    @classmethod
    def load(cls, path: str | Path) -> "AgenticV2SubstrateManifest":
        source = Path(path)
        document = json.loads(source.read_text(encoding="utf-8"))
        return cls.from_mapping(document)


def validate_capability_receipt(
    value: Any,
    manifest: AgenticV2SubstrateManifest,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("agentic v2 capability receipt must be an object")
    expected = {
        "schema_version",
        "substrate_id",
        "manifest_sha256",
        "commands",
        "python_modules",
        "font_families",
        "smokes",
        "package_inventory",
    }
    if set(value) != expected:
        raise ValueError("agentic v2 capability receipt fields are invalid")
    if (
        value.get("schema_version") != SUBSTRATE_SCHEMA_VERSION
        or value.get("substrate_id") != SUBSTRATE_ID
        or value.get("manifest_sha256") != manifest.sha256
    ):
        raise ValueError("agentic v2 capability receipt identity mismatch")
    document = dict(value)
    commands = _receipt_records(document["commands"], "command")
    modules = _receipt_records(document["python_modules"], "python module")
    expected_commands = {
        item["name"] for item in manifest.document["commands"]
    }
    expected_modules = {
        item["name"] for item in manifest.document["python_modules"]
    }
    if set(commands) != expected_commands or set(modules) != expected_modules:
        raise ValueError("agentic v2 capability receipt inventory mismatch")
    fonts = _receipt_records(document["font_families"], "font family")
    if set(fonts) != set(manifest.document["font_families"]):
        raise ValueError("agentic v2 capability receipt fonts mismatch")
    smokes = document["smokes"]
    if (
        not isinstance(smokes, list)
        or len(smokes) != len(REQUIRED_SMOKES)
        or {item.get("id") for item in smokes if isinstance(item, Mapping)}
        != REQUIRED_SMOKES
        or any(
            set(item) != {"id", "status", "artifact_sha256"}
            or item.get("status") != "pass"
            or not isinstance(item.get("artifact_sha256"), str)
            or _DIGEST.fullmatch(item["artifact_sha256"]) is None
            for item in smokes
            if isinstance(item, Mapping)
        )
        or any(not isinstance(item, Mapping) for item in smokes)
    ):
        raise ValueError("agentic v2 capability receipt smoke matrix is invalid")
    inventory = document["package_inventory"]
    if (
        not isinstance(inventory, dict)
        or set(inventory) != {"debian", "python", "r", "npm"}
        or any(
            not isinstance(item, dict)
            or set(item) != {"count", "sha256", "records"}
            or type(item.get("count")) is not int
            or item["count"] <= 0
            or not isinstance(item.get("sha256"), str)
            or _DIGEST.fullmatch(item["sha256"]) is None
            or not isinstance(item.get("records"), list)
            or item["records"] != sorted(set(item["records"]))
            or len(item["records"]) != item["count"]
            or canonical_sha256(item["records"]) != item["sha256"]
            or any(
                not isinstance(record, str)
                or not record
                or len(record) > 512
                for record in item["records"]
            )
            for item in inventory.values()
        )
    ):
        raise ValueError("agentic v2 capability receipt package inventory is invalid")
    return document


def _validate_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("agentic v2 substrate manifest must be an object")
    expected = {
        "schema_version",
        "substrate_id",
        "foundation_only",
        "production_activation",
        "platform",
        "capability_families",
        "commands",
        "python_modules",
        "font_families",
        "smoke_matrix",
        "supply_chain",
        "microvm",
    }
    if set(value) != expected:
        raise ValueError("agentic v2 substrate manifest fields are invalid")
    document = json.loads(json.dumps(value, allow_nan=False))
    if (
        document["schema_version"] != SUBSTRATE_SCHEMA_VERSION
        or document["substrate_id"] != SUBSTRATE_ID
        or document["foundation_only"] is not True
        or document["production_activation"] != "disabled"
    ):
        raise ValueError("agentic v2 substrate manifest identity is invalid")
    if document["platform"] != {
        "os": "linux",
        "architecture": "amd64",
        "python": "3.11",
    }:
        raise ValueError("agentic v2 substrate platform is invalid")
    families = document["capability_families"]
    if families != sorted(REQUIRED_CAPABILITY_FAMILIES):
        raise ValueError("agentic v2 substrate capability families are invalid")
    commands = _manifest_records(document["commands"], "command")
    modules = _manifest_records(document["python_modules"], "python module")
    if set(commands) != REQUIRED_COMMANDS:
        raise ValueError("agentic v2 substrate command inventory is invalid")
    if any(item["probe"][0] != item["name"] for item in commands.values()):
        raise ValueError("agentic v2 substrate command probe is invalid")
    if set(modules) != REQUIRED_PYTHON_MODULES:
        raise ValueError("agentic v2 substrate Python module inventory is invalid")
    if any(item["capability"] not in REQUIRED_CAPABILITY_FAMILIES for item in modules.values()):
        raise ValueError("agentic v2 substrate module capability is invalid")
    fonts = document["font_families"]
    if fonts != list(REQUIRED_FONT_FAMILIES):
        raise ValueError("agentic v2 substrate font inventory is invalid")
    smoke_matrix = _manifest_records(document["smoke_matrix"], "smoke")
    if set(smoke_matrix) != REQUIRED_SMOKES:
        raise ValueError("agentic v2 substrate smoke matrix is invalid")
    supply_chain = document["supply_chain"]
    if supply_chain != {
        "sbom_format": "SPDX-2.3",
        "provenance_profile": "buildkit-max-v1",
        "signature_profile": "cosign-offline-v1",
        "cve_policy_id": "agentic-v2-cve-v1",
        "license_policy_id": "agentic-v2-license-v2",
    }:
        raise ValueError("agentic v2 substrate supply-chain policy is invalid")
    if document["microvm"] != {
        "required": True,
        "runtime": "firecracker",
        "network": "none",
        "rootfs": "read-only",
        "workdir": "ephemeral-quota",
    } or document["microvm"].get("required") is not True:
        raise ValueError("agentic v2 substrate microvm policy is invalid")
    return document


def _manifest_records(value: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"agentic v2 substrate {label} records are invalid")
    records: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"agentic v2 substrate {label} record is invalid")
        if label == "command":
            expected = {"name", "capability", "probe"}
            probe = item.get("probe")
            if (
                set(item) != expected
                or not isinstance(probe, list)
                or not 1 <= len(probe) <= 8
                or any(not isinstance(part, str) or not part for part in probe)
            ):
                raise ValueError("agentic v2 substrate command record is invalid")
        else:
            expected = {"name", "capability"} if label == "python module" else {"id", "capability"}
            if set(item) != expected:
                raise ValueError(f"agentic v2 substrate {label} record is invalid")
        name = item.get("name") if label != "smoke" else item.get("id")
        if not isinstance(name, str) or _IDENTIFIER.fullmatch(name) is None or name in records:
            raise ValueError(f"agentic v2 substrate {label} identity is invalid")
        capability = item.get("capability")
        if capability not in REQUIRED_CAPABILITY_FAMILIES:
            raise ValueError(f"agentic v2 substrate {label} capability is invalid")
        records[name] = item
    return records


def _receipt_records(value: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"agentic v2 capability receipt {label}s are invalid")
    records: dict[str, dict[str, Any]] = {}
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "version", "sha256"}
            or not isinstance(item.get("name"), str)
            or not isinstance(item.get("version"), str)
            or not item["version"]
            or not isinstance(item.get("sha256"), str)
            or _DIGEST.fullmatch(item["sha256"]) is None
            or item["name"] in records
        ):
            raise ValueError(f"agentic v2 capability receipt {label} is invalid")
        records[item["name"]] = item
    return records