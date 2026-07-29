"""Fail-closed Phase 1B candidate and supply-chain evidence contracts."""

from __future__ import annotations

import json
import hashlib
import os
import re
import stat
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, unquote

from packaging.licenses import (
    InvalidLicenseExpression,
    canonicalize_license_expression,
)

from core.agentic_v2_substrate import (
    AgenticV2SubstrateManifest,
    canonical_sha256,
    validate_capability_receipt,
)


EVIDENCE_NAMES = frozenset({
    "capability_receipt",
    "containment",
    "cve",
    "license",
    "microvm",
    "oci_layout",
    "provenance",
    "sbom",
    "signature",
})
EVIDENCE_STATUSES = frozenset({"verified", "failed", "not_run"})
IMPLEMENTED_EVIDENCE_STATUSES = {
    "capability_receipt": frozenset({"verified", "failed", "not_run"}),
    "containment": frozenset({"verified", "failed", "not_run"}),
    "cve": frozenset({"not_run"}),
    "license": frozenset({"verified", "failed", "not_run"}),
    "microvm": frozenset({"not_run"}),
    "oci_layout": frozenset({"verified", "failed", "not_run"}),
    "provenance": frozenset({"not_run"}),
    "sbom": frozenset({"verified", "failed", "not_run"}),
    "signature": frozenset({"not_run"}),
}
EVIDENCE_COLLECTION_CHECKS = frozenset({
    "cap_drop_all",
    "memory_limit",
    "network_none",
    "no_new_privileges",
    "non_root_uid",
    "read_only_rootfs",
})
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_SOURCE_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class CandidateSubject:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def from_mapping(cls, value: Any) -> "CandidateSubject":
        document = _validate_subject(value)
        return cls(document=document, sha256=canonical_sha256(document))


@dataclass(frozen=True)
class SupplyChainPolicy:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: str | Path) -> "SupplyChainPolicy":
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_mapping(document)

    @classmethod
    def from_mapping(cls, value: Any) -> "SupplyChainPolicy":
        document = _validate_policy(value)
        return cls(document=document, sha256=canonical_sha256(document))


def build_candidate_receipt(
    subject: CandidateSubject,
    observation: Any,
    manifest: AgenticV2SubstrateManifest,
) -> dict[str, Any]:
    validated = validate_capability_receipt(observation, manifest)
    if subject.document["manifest_sha256"] != manifest.sha256:
        raise ValueError("candidate subject differs from capability manifest")
    receipt = {
        "schema_version": "1.0",
        "foundation_only": True,
        "production_activation": "disabled",
        "subject": deepcopy(subject.document),
        "subject_sha256": subject.sha256,
        "observation": validated,
        "observation_sha256": canonical_sha256(validated),
        "status": "candidate_observed",
    }
    validate_candidate_receipt(receipt, manifest)
    return receipt


def validate_candidate_receipt(
    value: Any,
    manifest: AgenticV2SubstrateManifest,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "foundation_only",
        "production_activation",
        "subject",
        "subject_sha256",
        "observation",
        "observation_sha256",
        "status",
    }:
        raise ValueError("agentic v2 candidate receipt fields are invalid")
    document = deepcopy(dict(value))
    if (
        document["schema_version"] != "1.0"
        or document["foundation_only"] is not True
        or document["production_activation"] != "disabled"
        or document["status"] != "candidate_observed"
    ):
        raise ValueError("agentic v2 candidate receipt status is invalid")
    subject = CandidateSubject.from_mapping(document["subject"])
    if document["subject_sha256"] != subject.sha256:
        raise ValueError("agentic v2 candidate receipt subject hash mismatch")
    observation = validate_capability_receipt(document["observation"], manifest)
    if document["observation_sha256"] != canonical_sha256(observation):
        raise ValueError("agentic v2 candidate receipt observation hash mismatch")
    if subject.document["manifest_sha256"] != manifest.sha256:
        raise ValueError("agentic v2 candidate receipt manifest mismatch")
    return document


def build_blocked_evidence_report(
    subject: CandidateSubject,
    policy: SupplyChainPolicy,
    *,
    capability_receipt_sha256: str,
    oci_layout_report_sha256: str,
) -> dict[str, Any]:
    if _HEX_DIGEST.fullmatch(capability_receipt_sha256) is None:
        raise ValueError("capability receipt evidence digest is invalid")
    if _HEX_DIGEST.fullmatch(oci_layout_report_sha256) is None:
        raise ValueError("OCI evidence digest is invalid")
    evidence = {
        name: _not_run_evidence(subject.sha256)
        for name in EVIDENCE_NAMES
    }
    evidence["capability_receipt"] = _verified_evidence(
        subject.sha256,
        tool_name="gdpval-agentic-v2-host-verifier",
        tool_version="1.0",
        tool_sha256=subject.document["verifier_sha256"],
        report_sha256=capability_receipt_sha256,
    )
    evidence["oci_layout"] = _verified_evidence(
        subject.sha256,
        tool_name="gdpval-agentic-v2-oci-exporter",
        tool_version="1.0",
        tool_sha256=subject.document["oci_exporter_sha256"],
        report_sha256=oci_layout_report_sha256,
    )
    report = {
        "schema_version": "1.0",
        "foundation_only": True,
        "production_activation": "disabled",
        "subject_sha256": subject.sha256,
        "policy_sha256": policy.sha256,
        "evidence": evidence,
        "gate_status": "blocked",
        "blocking_evidence": sorted(
            name for name, item in evidence.items()
            if item["status"] != "verified"
        ),
    }
    validate_evidence_report(report, subject, policy)
    return report


def build_evidence_report(
    subject: CandidateSubject,
    policy: SupplyChainPolicy,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(evidence, Mapping) or set(evidence) != EVIDENCE_NAMES:
        raise ValueError("agentic v2 evidence set is invalid")
    copied = deepcopy(dict(evidence))
    blocking = sorted(
        name for name in policy.document["required_evidence"]
        if copied[name].get("status") != "verified"
    )
    report = {
        "schema_version": "1.0",
        "foundation_only": True,
        "production_activation": "disabled",
        "subject_sha256": subject.sha256,
        "policy_sha256": policy.sha256,
        "evidence": copied,
        "gate_status": "candidate_complete" if not blocking else "blocked",
        "blocking_evidence": blocking,
    }
    validate_evidence_report(report, subject, policy)
    return report


def evidence_item(
    subject: CandidateSubject,
    *,
    name: str,
    status: str,
    tool_name: str | None = None,
    tool_version: str | None = None,
    tool_sha256: str | None = None,
    report_sha256: str | None = None,
) -> dict[str, Any]:
    if name not in EVIDENCE_NAMES:
        raise ValueError("agentic v2 evidence name is invalid")
    if status == "not_run":
        return _not_run_evidence(subject.sha256)
    if status not in {"verified", "failed"}:
        raise ValueError("agentic v2 evidence status is invalid")
    item = {
        "status": status,
        "subject_sha256": subject.sha256,
        "tool": {
            "name": tool_name,
            "version": tool_version,
            "sha256": tool_sha256,
        },
        "report_sha256": report_sha256,
    }
    _validate_evidence_item(name, item, subject.sha256)
    return item


def validate_effective_sbom(
    value: Any,
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("agentic v2 effective SBOM must be an object")
    document = deepcopy(dict(value))
    if (
        set(document) != {
            "spdxVersion", "dataLicense", "SPDXID", "name",
            "documentNamespace", "creationInfo", "packages", "relationships",
        }
        or document.get("spdxVersion") != "SPDX-2.3"
        or document.get("dataLicense") != "CC0-1.0"
        or document.get("SPDXID") != "SPDXRef-DOCUMENT"
        or document.get("name") != "gdpval-agentic-v2-professional-work-candidate"
        or document.get("creationInfo") != {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: gdpval-agentic-v2-effective-sbom-v1"],
        }
        or not isinstance(document.get("packages"), list)
        or not document["packages"]
    ):
        raise ValueError("agentic v2 effective SBOM identity is invalid")
    records: dict[str, set[str]] = {
        "debian": set(),
        "python": set(),
        "r": set(),
        "npm": set(),
    }
    package_ids = set()
    purls = set()
    for package in document["packages"]:
        if (
            not isinstance(package, dict)
            or set(package) != {
                "SPDXID", "name", "versionInfo", "downloadLocation",
                "filesAnalyzed", "licenseConcluded", "licenseDeclared",
                "supplier", "externalRefs",
            }
            or package.get("SPDXID") in package_ids
            or package.get("filesAnalyzed") is not False
            or package.get("licenseConcluded") != "NOASSERTION"
            or package.get("downloadLocation") != "NOASSERTION"
            or package.get("supplier") != "NOASSERTION"
            or not isinstance(package.get("name"), str) or not package["name"]
            or not isinstance(package.get("versionInfo"), str)
            or not package["versionInfo"]
            or not isinstance(package.get("licenseDeclared"), str)
            or not package["licenseDeclared"]
            or len(package["licenseDeclared"]) > 500
        ):
            raise ValueError("agentic v2 effective SBOM package identity is invalid")
        references = package.get("externalRefs")
        if (
            not isinstance(references, list)
            or len(references) != 1
            or not isinstance(references[0], dict)
            or set(references[0]) != {
                "referenceCategory", "referenceType", "referenceLocator"
            }
            or references[0]["referenceCategory"] != "PACKAGE-MANAGER"
            or references[0]["referenceType"] != "purl"
        ):
            raise ValueError("agentic v2 effective SBOM package purl is invalid")
        purl = references[0].get("referenceLocator")
        if not isinstance(purl, str) or purl in purls:
            raise ValueError("agentic v2 effective SBOM package purl is invalid")
        purls.add(purl)
        ecosystem, inventory_name, package_record = _spdx_package_identity(
            package, purl
        )
        expected_id = "SPDXRef-Package-" + hashlib.sha256(
            f"{ecosystem}\0{package['name']}\0{package['versionInfo']}".encode("utf-8")
        ).hexdigest()[:24]
        if package["SPDXID"] != expected_id:
            raise ValueError("agentic v2 effective SBOM SPDXID is invalid")
        package_ids.add(package["SPDXID"])
        records[inventory_name].add(package_record)
    inventory = observation.get("package_inventory")
    if not isinstance(inventory, Mapping):
        raise ValueError("agentic v2 observation package inventory is missing")
    if any(
        sorted(records[name]) != inventory[name]["records"]
        or len(records[name]) != inventory[name]["count"]
        or canonical_sha256(sorted(records[name])) != inventory[name]["sha256"]
        for name in records
    ):
        raise ValueError("agentic v2 effective SBOM inventory mismatch")
    relationships = document.get("relationships")
    expected_relationships = [{
        "spdxElementId": "SPDXRef-DOCUMENT",
        "relationshipType": "DESCRIBES",
        "relatedSpdxElement": package_id,
    } for package_id in sorted(package_ids)]
    if not isinstance(relationships, list) or sorted(
        relationships,
        key=lambda item: (
            item.get("relatedSpdxElement", "") if isinstance(item, dict) else ""
        ),
    ) != expected_relationships:
        raise ValueError("agentic v2 effective SBOM relationships are invalid")
    expected_namespace = (
        "https://github.com/hyeonsangjeon/gdpval-realworks/"
        "sbom/agentic-v2-phase1b/" + canonical_sha256(document["packages"])
    )
    if document["documentNamespace"] != expected_namespace:
        raise ValueError("agentic v2 effective SBOM namespace is invalid")
    return document


def _spdx_package_identity(
    package: Mapping[str, Any],
    purl: str,
) -> tuple[str, str, str]:
    name = package["name"]
    version = package["versionInfo"]
    identities = (
        ("pypi", "python", "pkg:pypi/"),
        ("cran", "r", "pkg:cran/"),
        ("npm", "npm", "pkg:npm/"),
    )
    if purl.startswith("pkg:deb/debian/"):
        payload = purl.removeprefix("pkg:deb/debian/")
        encoded_name, separator, remainder = payload.partition("@")
        encoded_version, query_separator, query = remainder.partition("?")
        encoded_architecture = query.removeprefix("arch=")
        architecture = unquote(encoded_architecture)
        expected = (
            f"pkg:deb/debian/{quote(name, safe='')}@{quote(version, safe='')}"
            f"?arch={quote(architecture, safe='')}"
        )
        if (
            not separator
            or not query_separator
            or not query.startswith("arch=")
            or not encoded_architecture
            or unquote(encoded_name) != name
            or unquote(encoded_version) != version
            or purl != expected
        ):
            raise ValueError("agentic v2 effective SBOM Debian purl is invalid")
        return "deb", "debian", f"{name}:{architecture}={version}"
    for ecosystem, inventory_name, prefix in identities:
        if purl.startswith(prefix):
            payload = purl.removeprefix(prefix)
            encoded_name, separator, encoded_version = payload.partition("@")
            expected = f"{prefix}{quote(name, safe='')}@{quote(version, safe='')}"
            if (
                not separator
                or unquote(encoded_name) != name
                or unquote(encoded_version) != version
                or purl != expected
            ):
                raise ValueError("agentic v2 effective SBOM package purl is invalid")
            return ecosystem, inventory_name, f"{name}={version}"
    raise ValueError("agentic v2 effective SBOM ecosystem is invalid")


def evaluate_license_policy(
    sbom: Mapping[str, Any],
    policy: SupplyChainPolicy,
) -> dict[str, Any]:
    denied_identifiers = set(policy.document["license"]["denied_identifiers"])
    unknown = []
    denied = []
    for package in sbom["packages"]:
        license_value = package.get("licenseDeclared")
        purl = package["externalRefs"][0]["referenceLocator"]
        try:
            identifiers = _spdx_identifiers(license_value)
        except ValueError:
            identifiers = None
        try:
            policy_identifiers = _parse_spdx_tokens(license_value)
        except ValueError:
            policy_identifiers = set()
        if not identifiers:
            unknown.append(purl)
        if denied_identifiers.intersection(policy_identifiers):
            denied.append({"purl": purl, "license": license_value})
    report = {
        "schema_version": "1.0",
        "policy_id": policy.document["license"]["policy_id"],
        "status": "failed" if unknown or denied else "verified",
        "package_count": len(sbom["packages"]),
        "unknown_count": len(unknown),
        "unknown_purls_sha256": canonical_sha256(sorted(unknown)),
        "denied_count": len(denied),
        "denied_sha256": canonical_sha256(denied),
        "exceptions": [],
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


_SPDX_TOKEN = re.compile(
    r"\s*(\(|\)|AND\b|OR\b|WITH\b|[A-Za-z0-9][A-Za-z0-9.+-]*)"
)


def _spdx_identifiers(value: Any) -> set[str]:
    if not isinstance(value, str) or value in {"", "NOASSERTION", "NONE"}:
        raise ValueError("SPDX expression is unknown")
    try:
        normalized = canonicalize_license_expression(value)
    except InvalidLicenseExpression as exc:
        raise ValueError("SPDX expression is unknown") from exc
    return _parse_spdx_tokens(normalized)


def _parse_spdx_tokens(value: Any) -> set[str]:
    if not isinstance(value, str) or value in {"", "NOASSERTION", "NONE"}:
        raise ValueError("SPDX expression is unknown")
    tokens = []
    position = 0
    while position < len(value):
        match = _SPDX_TOKEN.match(value, position)
        if match is None:
            raise ValueError("SPDX expression token is invalid")
        tokens.append(match.group(1))
        position = match.end()
    identifiers: set[str] = set()
    index = 0

    def parse_expression():
        nonlocal index
        parse_term()
        while index < len(tokens) and tokens[index] == "OR":
            index += 1
            parse_term()

    def parse_term():
        nonlocal index
        parse_factor()
        while index < len(tokens) and tokens[index] == "AND":
            index += 1
            parse_factor()

    def parse_factor():
        nonlocal index
        if index >= len(tokens):
            raise ValueError("SPDX expression ended unexpectedly")
        token = tokens[index]
        if token == "(":
            index += 1
            parse_expression()
            if index >= len(tokens) or tokens[index] != ")":
                raise ValueError("SPDX expression parenthesis is invalid")
            index += 1
        elif token not in {"AND", "OR", "WITH", ")"}:
            identifiers.add(token)
            index += 1
        else:
            raise ValueError("SPDX expression factor is invalid")
        if index < len(tokens) and tokens[index] == "WITH":
            index += 1
            if index >= len(tokens) or tokens[index] in {"AND", "OR", "WITH", "(", ")"}:
                raise ValueError("SPDX exception is invalid")
            identifiers.add(tokens[index])
            index += 1

    parse_expression()
    if index != len(tokens):
        raise ValueError("SPDX expression has trailing tokens")
    return identifiers


def validate_evidence_report(
    value: Any,
    subject: CandidateSubject,
    policy: SupplyChainPolicy,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "foundation_only",
        "production_activation",
        "subject_sha256",
        "policy_sha256",
        "evidence",
        "gate_status",
        "blocking_evidence",
    }:
        raise ValueError("agentic v2 evidence report fields are invalid")
    document = deepcopy(dict(value))
    if (
        document["schema_version"] != "1.0"
        or document["foundation_only"] is not True
        or document["production_activation"] != "disabled"
        or document["subject_sha256"] != subject.sha256
        or document["policy_sha256"] != policy.sha256
    ):
        raise ValueError("agentic v2 evidence report identity mismatch")
    evidence = document["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != EVIDENCE_NAMES:
        raise ValueError("agentic v2 evidence set is invalid")
    for name, item in evidence.items():
        _validate_evidence_item(name, item, subject.sha256)
    blocking = sorted(
        name for name in policy.document["required_evidence"]
        if evidence[name]["status"] != "verified"
    )
    expected_status = "candidate_complete" if not blocking else "blocked"
    if (
        document["blocking_evidence"] != blocking
        or document["gate_status"] != expected_status
    ):
        raise ValueError("agentic v2 evidence gate result is invalid")
    return document


def validate_evidence_directory(
    directory: str | Path,
    *,
    subject: CandidateSubject,
    policy: SupplyChainPolicy,
    manifest: AgenticV2SubstrateManifest,
    oci_layout: str | Path,
) -> dict[str, Any]:
    root = Path(directory)
    metadata = root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or root.is_symlink():
        raise ValueError("agentic v2 evidence directory is invalid")
    gate = validate_evidence_report(
        _read_json(root / "gate-report.json", 4 * 1024 * 1024),
        subject,
        policy,
    )
    subject_document = _read_json(root / "candidate-subject.json", 1024 * 1024)
    if CandidateSubject.from_mapping(subject_document) != subject:
        raise ValueError("agentic v2 evidence subject file mismatch")

    from core.agentic_v2_oci import verify_oci_layout

    oci_report = _read_json(root / "oci-report.json", 1024 * 1024)
    verified_oci = verify_oci_layout(
        oci_layout,
        expected_manifest_digest=subject.document["oci_manifest_digest"],
    )
    if oci_report != verified_oci:
        raise ValueError("agentic v2 OCI evidence report mismatch")
    _match_report_evidence(gate, "oci_layout", oci_report)

    containment = validate_containment_report(
        _read_json(root / "containment-report.json", 1024 * 1024)
    )
    _match_report_evidence(gate, "containment", containment)

    from core.agentic_v2_microvm import validate_microvm_readiness_report

    microvm = validate_microvm_readiness_report(
        _read_json(root / "microvm-readiness.json", 1024 * 1024)
    )
    if gate["evidence"]["microvm"]["status"] != "not_run" or microvm[
        "status"
    ] not in {"not_run", "ready_for_boot_test"}:
        raise ValueError("agentic v2 microvm evidence state mismatch")

    receipt_path = root / "candidate-receipt.json"
    sbom_path = root / "effective-sbom.spdx.json"
    license_path = root / "license-report.json"
    capability_status = gate["evidence"]["capability_receipt"]["status"]
    expected_files = {
        "candidate-subject.json",
        "containment-report.json",
        "gate-report.json",
        "microvm-readiness.json",
        "oci-report.json",
    }
    if capability_status == "verified":
        expected_files.update({
            "candidate-receipt.json",
            "effective-sbom.spdx.json",
            "license-report.json",
        })
    if _regular_directory_files(root) != expected_files:
        raise ValueError("agentic v2 evidence directory inventory is invalid")

    _require_evidence_binding(
        gate,
        "oci_layout",
        status="verified",
        tool_name="gdpval-agentic-v2-oci-exporter",
        tool_sha256=subject.document["oci_exporter_sha256"],
    )
    _require_evidence_binding(
        gate,
        "containment",
        status=containment["status"],
        tool_name="gdpval-agentic-v2-docker-containment",
        tool_sha256=subject.document["verifier_sha256"],
    )
    if capability_status == "verified":
        if not evidence_collection_allowed(containment):
            raise ValueError(
                "agentic v2 capability evidence requires collection isolation"
            )
        receipt = validate_candidate_receipt(
            _read_json(receipt_path, 16 * 1024 * 1024), manifest
        )
        if receipt["subject"] != subject.document:
            raise ValueError("agentic v2 capability evidence subject mismatch")
        _match_report_evidence(gate, "capability_receipt", receipt)
        _require_evidence_binding(
            gate,
            "capability_receipt",
            status="verified",
            tool_name="gdpval-agentic-v2-host-verifier",
            tool_sha256=subject.document["verifier_sha256"],
        )
        sbom = validate_effective_sbom(
            _read_json(sbom_path, 128 * 1024 * 1024),
            receipt["observation"],
        )
        _match_report_evidence(gate, "sbom", sbom)
        _require_evidence_binding(
            gate,
            "sbom",
            status="verified",
            tool_name="gdpval-agentic-v2-effective-sbom",
            tool_sha256=subject.document["sbom_generator_sha256"],
        )
        license_report = _read_json(license_path, 4 * 1024 * 1024)
        expected_license = evaluate_license_policy(sbom, policy)
        if license_report != expected_license:
            raise ValueError("agentic v2 license evidence report mismatch")
        _match_report_evidence(gate, "license", license_report)
        _require_evidence_binding(
            gate,
            "license",
            status=license_report["status"],
            tool_name="gdpval-agentic-v2-license-policy",
            tool_sha256=policy.sha256,
        )
    elif (
        evidence_collection_allowed(containment)
        or containment["status"] != "failed"
        or any(
            gate["evidence"][name]["status"] != "not_run"
            for name in ("capability_receipt", "sbom", "license")
        )
    ):
        raise ValueError("agentic v2 degraded containment evidence state is invalid")

    for name in ("cve", "provenance", "signature"):
        if gate["evidence"][name]["status"] != "not_run":
            raise ValueError(f"agentic v2 {name} evidence must remain not-run")
        if (root / f"{name}-report.json").exists():
            raise ValueError(f"agentic v2 unsupported {name} report is present")
    return gate


def evidence_collection_allowed(value: Any) -> bool:
    report = validate_containment_report(value)
    return report["collection_status"] == "verified"


def validate_containment_report(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version", "status", "checks", "required", "host_scope",
        "collection_status", "collection_checks", "report_sha256",
    }:
        raise ValueError("agentic v2 containment report fields are invalid")
    document = deepcopy(dict(value))
    claimed = document.pop("report_sha256")
    checks = document["checks"]
    required = document["required"]
    collection_checks = document["collection_checks"]
    expected_checks = {
        "cap_drop_all",
        "cpu_quota",
        "memory_limit",
        "network_none",
        "no_new_privileges",
        "non_root_uid",
        "pids_limit",
        "read_only_rootfs",
    }
    if (
        document["schema_version"] != "1.1"
        or document["host_scope"] != "exact-docker-daemon"
        or not isinstance(checks, dict)
        or set(checks) != expected_checks
        or any(type(item) is not bool for item in checks.values())
        or required != sorted(checks)
        or document["status"] != ("verified" if all(checks.values()) else "failed")
        or not isinstance(collection_checks, dict)
        or set(collection_checks) != EVIDENCE_COLLECTION_CHECKS
        or any(type(item) is not bool for item in collection_checks.values())
        or document["collection_status"] != (
            "verified" if all(collection_checks.values()) else "failed"
        )
        or any(
            collection_checks[name] and not checks[name]
            for name in EVIDENCE_COLLECTION_CHECKS
        )
        or claimed != canonical_sha256(document)
    ):
        raise ValueError("agentic v2 containment report identity is invalid")
    return dict(value)


def _validate_subject(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "substrate_id",
        "image_id",
        "oci_manifest_digest",
        "parent_manifest_digest",
        "platform",
        "source_revision",
        "dockerfile_sha256",
        "manifest_sha256",
        "probe_sha256",
        "embedded_source_sha256",
        "verifier_sha256",
        "oci_exporter_sha256",
        "sbom_generator_sha256",
        "lock_set_sha256",
    }:
        raise ValueError("agentic v2 candidate subject fields are invalid")
    document = deepcopy(dict(value))
    if (
        document["schema_version"] != "1.0"
        or document["substrate_id"] != "professional-work-v1"
        or any(
            _DIGEST.fullmatch(str(document[name])) is None
            for name in ("image_id", "oci_manifest_digest", "parent_manifest_digest")
        )
        or any(
            _HEX_DIGEST.fullmatch(str(document[name])) is None
            for name in (
                "dockerfile_sha256",
                "manifest_sha256",
                "probe_sha256",
                "embedded_source_sha256",
                "verifier_sha256",
                "oci_exporter_sha256",
                "sbom_generator_sha256",
                "lock_set_sha256",
            )
        )
        or document["platform"] != "linux/amd64"
        or _SOURCE_SHA.fullmatch(str(document["source_revision"])) is None
    ):
        raise ValueError("agentic v2 candidate subject identity is invalid")
    return document


def _validate_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("agentic v2 supply-chain policy must be an object")
    expected = {
        "schema_version",
        "policy_id",
        "foundation_only",
        "production_activation",
        "required_evidence",
        "cve",
        "license",
        "signature",
        "provenance",
        "microvm",
    }
    if set(value) != expected:
        raise ValueError("agentic v2 supply-chain policy fields are invalid")
    document = deepcopy(dict(value))
    if (
        document["schema_version"] != "1.0"
        or document["policy_id"] != "agentic-v2-phase1b-candidate-v1"
        or document["foundation_only"] is not True
        or document["production_activation"] != "disabled"
        or document["required_evidence"] != sorted(EVIDENCE_NAMES)
        or document["cve"]["policy_id"] != "agentic-v2-cve-v1"
        or document["license"]["policy_id"] != "agentic-v2-license-v1"
        or document["signature"] != {
            "profile": "cosign-offline-v1",
            "trusted_key_required": True,
            "bundle_required": True,
        }
        or document["microvm"] != {
            "runtime": "firecracker",
            "jailer_required": True,
            "kvm_required": True,
            "network": "none",
            "read_only_rootfs": True,
            "ephemeral_work_disk": True,
        }
    ):
        raise ValueError("agentic v2 supply-chain policy is invalid")
    return document


def _not_run_evidence(subject_sha256: str) -> dict[str, Any]:
    return {
        "status": "not_run",
        "subject_sha256": subject_sha256,
        "tool": None,
        "report_sha256": None,
    }


def _verified_evidence(
    subject_sha256: str,
    *,
    tool_name: str,
    tool_version: str,
    tool_sha256: str,
    report_sha256: str,
) -> dict[str, Any]:
    return {
        "status": "verified",
        "subject_sha256": subject_sha256,
        "tool": {
            "name": tool_name,
            "version": tool_version,
            "sha256": tool_sha256,
        },
        "report_sha256": report_sha256,
    }


def _validate_evidence_item(name: str, value: Any, subject_sha256: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "status", "subject_sha256", "tool", "report_sha256"
    }:
        raise ValueError(f"agentic v2 {name} evidence fields are invalid")
    if value["status"] not in EVIDENCE_STATUSES or value["subject_sha256"] != subject_sha256:
        raise ValueError(f"agentic v2 {name} evidence identity is invalid")
    if value["status"] not in IMPLEMENTED_EVIDENCE_STATUSES[name]:
        raise ValueError(f"agentic v2 {name} evidence status is not implemented")
    if value["status"] == "not_run":
        if value["tool"] is not None or value["report_sha256"] is not None:
            raise ValueError(f"agentic v2 {name} not-run evidence is invalid")
        return
    tool = value["tool"]
    if (
        not isinstance(tool, dict)
        or set(tool) != {"name", "version", "sha256"}
        or not all(isinstance(tool[key], str) and tool[key] for key in ("name", "version"))
        or _HEX_DIGEST.fullmatch(str(tool.get("sha256", ""))) is None
        or _HEX_DIGEST.fullmatch(str(value.get("report_sha256", ""))) is None
    ):
        raise ValueError(f"agentic v2 {name} evidence tool identity is invalid")


def _match_report_evidence(
    gate: Mapping[str, Any],
    name: str,
    report: Mapping[str, Any],
) -> None:
    evidence = gate["evidence"][name]
    if (
        evidence["status"] not in {"verified", "failed"}
        or evidence["report_sha256"] != canonical_sha256(report)
    ):
        raise ValueError(f"agentic v2 {name} evidence report hash mismatch")


def _require_evidence_binding(
    gate: Mapping[str, Any],
    name: str,
    *,
    status: str,
    tool_name: str,
    tool_sha256: str,
) -> None:
    evidence = gate["evidence"][name]
    if evidence["status"] != status or evidence["tool"] != {
        "name": tool_name,
        "version": "1.0",
        "sha256": tool_sha256,
    }:
        raise ValueError(f"agentic v2 {name} evidence binding mismatch")


def _regular_directory_files(root: Path) -> set[str]:
    result = set()
    with os.scandir(root) as entries:
        for entry in entries:
            metadata = entry.stat(follow_symlinks=False)
            if (
                entry.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
            ):
                raise ValueError("agentic v2 evidence directory entry is invalid")
            result.add(entry.name)
    return result


def _read_json(path: Path, maximum: int):
    descriptor = os.open(
        path,
        _secure_read_flags(),
    )
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size < 0
            or metadata.st_size > maximum
        ):
            raise ValueError("agentic v2 evidence file is invalid")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise ValueError("agentic v2 evidence file exceeds size limit")
        if total != metadata.st_size:
            raise ValueError("agentic v2 evidence file changed during read")
        value = b"".join(chunks)
    finally:
        os.close(descriptor)

    def reject_duplicates(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("agentic v2 evidence JSON contains duplicate keys")
            result[key] = item
        return result

    try:
        return json.loads(value, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("agentic v2 evidence JSON is invalid") from exc


def _secure_read_flags() -> int:
    required = ("O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    if os.name != "posix" or any(
        not isinstance(getattr(os, name, None), int)
        or getattr(os, name) <= 0
        for name in required
    ):
        raise RuntimeError("agentic v2 evidence requires secure Unix open flags")
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK