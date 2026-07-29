from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from core.agentic_v2_microvm import (
    inspect_microvm_readiness,
    validate_microvm_readiness_report,
)
from core.agentic_v2_substrate import (
    AgenticV2SubstrateManifest,
    canonical_sha256,
)
from core.agentic_v2_supply_chain import (
    CandidateSubject,
    SupplyChainPolicy,
    build_blocked_evidence_report,
    build_candidate_receipt,
    build_evidence_report,
    evidence_item,
    validate_candidate_receipt,
    validate_effective_sbom,
    validate_evidence_directory,
    validate_evidence_report,
    evaluate_license_policy,
)


MANIFEST = Path("sandbox/agentic_v2_capabilities.json")
POLICY = Path("security/agentic-v2-supply-chain-policy.json")


def _subject(manifest):
    return CandidateSubject.from_mapping({
        "schema_version": "1.0",
        "substrate_id": "professional-work-v1",
        "image_id": "sha256:" + "1" * 64,
        "oci_manifest_digest": "sha256:" + "2" * 64,
        "parent_manifest_digest": "sha256:" + "3" * 64,
        "platform": "linux/amd64",
        "source_revision": "4" * 40,
        "dockerfile_sha256": "5" * 64,
        "manifest_sha256": manifest.sha256,
        "probe_sha256": "6" * 64,
        "embedded_source_sha256": "f" * 64,
        "verifier_sha256": "7" * 64,
        "oci_exporter_sha256": "8" * 64,
        "sbom_generator_sha256": "a" * 64,
        "lock_set_sha256": "9" * 64,
    })


def _observation(manifest):
    return {
        "schema_version": "1.0",
        "substrate_id": "professional-work-v1",
        "manifest_sha256": manifest.sha256,
        "commands": [
            {"name": item["name"], "version": "observed", "sha256": "a" * 64}
            for item in manifest.document["commands"]
        ],
        "python_modules": [
            {"name": item["name"], "version": "observed", "sha256": "b" * 64}
            for item in manifest.document["python_modules"]
        ],
        "font_families": [
            {"name": name, "version": "observed.ttf", "sha256": "c" * 64}
            for name in manifest.document["font_families"]
        ],
        "smokes": [
            {"id": item["id"], "status": "pass", "artifact_sha256": "d" * 64}
            for item in manifest.document["smoke_matrix"]
        ],
        "package_inventory": {
            name: {
                "count": 1,
                "records": [f"{name}=1"],
                "sha256": __import__("hashlib").sha256(
                    (f'["{name}=1"]').encode("utf-8")
                ).hexdigest(),
            }
            for name in ("debian", "python", "r", "npm")
        },
    }


def _degraded_evidence_directory(
    tmp_path,
    monkeypatch,
    *,
    collection_allowed=False,
):
    manifest = AgenticV2SubstrateManifest.load(MANIFEST)
    subject = _subject(manifest)
    policy = SupplyChainPolicy.load(POLICY)
    oci_report = {
        "schema_version": "1.0",
        "manifest_digest": subject.document["oci_manifest_digest"],
        "config_digest": subject.document["image_id"],
        "layer_count": 1,
        "platform": {"os": "linux", "architecture": "amd64"},
        "index_sha256": "b" * 64,
    }
    monkeypatch.setattr(
        "core.agentic_v2_oci.verify_oci_layout",
        lambda *_args, **_kwargs: deepcopy(oci_report),
    )
    checks = {
        "cap_drop_all": True,
        "cpu_quota": False,
        "memory_limit": True,
        "network_none": collection_allowed,
        "no_new_privileges": True,
        "non_root_uid": True,
        "pids_limit": False,
        "read_only_rootfs": True,
    }
    collection_checks = {
        "cap_drop_all": True,
        "memory_limit": True,
        "network_none": collection_allowed,
        "no_new_privileges": True,
        "non_root_uid": True,
        "read_only_rootfs": True,
    }
    containment = {
        "schema_version": "1.1",
        "status": "failed",
        "checks": checks,
        "required": sorted(checks),
        "collection_status": "verified" if collection_allowed else "failed",
        "collection_checks": collection_checks,
        "host_scope": "exact-docker-daemon",
    }
    containment["report_sha256"] = canonical_sha256(containment)
    microvm = inspect_microvm_readiness(
        path_lookup=lambda _name: None,
        kvm_path=tmp_path / "missing-kvm",
        asset_paths={},
    )
    evidence = {
        name: evidence_item(subject, name=name, status="not_run")
        for name in (
            "capability_receipt", "containment", "cve", "license", "microvm",
            "oci_layout", "provenance", "sbom", "signature",
        )
    }
    evidence["oci_layout"] = evidence_item(
        subject,
        name="oci_layout",
        status="verified",
        tool_name="gdpval-agentic-v2-oci-exporter",
        tool_version="1.0",
        tool_sha256=subject.document["oci_exporter_sha256"],
        report_sha256=canonical_sha256(oci_report),
    )
    evidence["containment"] = evidence_item(
        subject,
        name="containment",
        status="failed",
        tool_name="gdpval-agentic-v2-docker-containment",
        tool_version="1.0",
        tool_sha256=subject.document["verifier_sha256"],
        report_sha256=canonical_sha256(containment),
    )
    receipt = None
    sbom = None
    license_report = None
    if collection_allowed:
        inventory_observation, sbom = _effective_sbom_fixture()
        observation = _observation(manifest)
        observation["package_inventory"] = inventory_observation[
            "package_inventory"
        ]
        receipt = build_candidate_receipt(subject, observation, manifest)
        license_report = evaluate_license_policy(sbom, policy)
        evidence["capability_receipt"] = evidence_item(
            subject,
            name="capability_receipt",
            status="verified",
            tool_name="gdpval-agentic-v2-host-verifier",
            tool_version="1.0",
            tool_sha256=subject.document["verifier_sha256"],
            report_sha256=canonical_sha256(receipt),
        )
        evidence["sbom"] = evidence_item(
            subject,
            name="sbom",
            status="verified",
            tool_name="gdpval-agentic-v2-effective-sbom",
            tool_version="1.0",
            tool_sha256=subject.document["sbom_generator_sha256"],
            report_sha256=canonical_sha256(sbom),
        )
        evidence["license"] = evidence_item(
            subject,
            name="license",
            status=license_report["status"],
            tool_name="gdpval-agentic-v2-license-policy",
            tool_version="1.0",
            tool_sha256=policy.sha256,
            report_sha256=canonical_sha256(license_report),
        )
    gate = build_evidence_report(subject, policy, evidence)
    root = tmp_path / "evidence"
    root.mkdir()
    documents = {
        "candidate-subject.json": subject.document,
        "containment-report.json": containment,
        "gate-report.json": gate,
        "microvm-readiness.json": microvm,
        "oci-report.json": oci_report,
    }
    if collection_allowed:
        documents.update({
            "candidate-receipt.json": receipt,
            "effective-sbom.spdx.json": sbom,
            "license-report.json": license_report,
        })
    for name, value in documents.items():
        (root / name).write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    return root, subject, policy, manifest


def _validate_directory(root, subject, policy, manifest):
    return validate_evidence_directory(
        root,
        subject=subject,
        policy=policy,
        manifest=manifest,
        oci_layout=root.parent / "oci",
    )


def test_candidate_receipt_binds_subject_manifest_and_observation():
    manifest = AgenticV2SubstrateManifest.load(MANIFEST)
    subject = _subject(manifest)
    receipt = build_candidate_receipt(subject, _observation(manifest), manifest)

    assert validate_candidate_receipt(receipt, manifest) == receipt

    tampered = deepcopy(receipt)
    tampered["observation"]["commands"][0]["version"] = "forged"
    with pytest.raises(ValueError, match="observation hash mismatch"):
        validate_candidate_receipt(tampered, manifest)


def test_evidence_directory_reopens_degraded_host_reports(tmp_path, monkeypatch):
    arguments = _degraded_evidence_directory(tmp_path, monkeypatch)

    gate = _validate_directory(*arguments)

    assert gate["gate_status"] == "blocked"
    assert gate["evidence"]["containment"]["status"] == "failed"
    assert gate["evidence"]["capability_receipt"]["status"] == "not_run"


def test_evidence_directory_accepts_resource_only_containment_degradation(
    tmp_path,
    monkeypatch,
):
    arguments = _degraded_evidence_directory(
        tmp_path,
        monkeypatch,
        collection_allowed=True,
    )

    gate = _validate_directory(*arguments)

    assert gate["gate_status"] == "blocked"
    assert gate["evidence"]["containment"]["status"] == "failed"
    assert gate["evidence"]["capability_receipt"]["status"] == "verified"
    assert gate["evidence"]["sbom"]["status"] == "verified"
    assert gate["evidence"]["license"]["status"] == "verified"


@pytest.mark.parametrize(
    "name",
    [
        "cap_drop_all", "memory_limit", "network_none", "no_new_privileges",
        "non_root_uid", "read_only_rootfs",
    ],
)
def test_containment_report_rejects_collection_runtime_contradiction(
    tmp_path,
    monkeypatch,
    name,
):
    root, subject, policy, manifest = _degraded_evidence_directory(
        tmp_path,
        monkeypatch,
        collection_allowed=True,
    )
    path = root / "containment-report.json"
    containment = json.loads(path.read_text(encoding="utf-8"))
    containment["checks"][name] = False
    unsigned = dict(containment)
    unsigned.pop("report_sha256")
    containment["status"] = "failed"
    containment["report_sha256"] = canonical_sha256({
        key: value for key, value in containment.items()
        if key != "report_sha256"
    })
    path.write_text(json.dumps(containment), encoding="utf-8")

    with pytest.raises(ValueError, match="containment report identity"):
        _validate_directory(root, subject, policy, manifest)


def test_evidence_directory_rejects_report_tampering(tmp_path, monkeypatch):
    root, *arguments = _degraded_evidence_directory(tmp_path, monkeypatch)
    path = root / "containment-report.json"
    containment = json.loads(path.read_text(encoding="utf-8"))
    containment["checks"]["cpu_quota"] = True
    path.write_text(json.dumps(containment), encoding="utf-8")

    with pytest.raises(ValueError, match="containment report identity"):
        _validate_directory(root, *arguments)


def test_evidence_directory_rejects_symlinked_report(tmp_path, monkeypatch):
    root, *arguments = _degraded_evidence_directory(tmp_path, monkeypatch)
    path = root / "containment-report.json"
    target = tmp_path / "outside-containment.json"
    path.rename(target)
    path.symlink_to(target)

    with pytest.raises((OSError, ValueError)):
        _validate_directory(root, *arguments)


def test_evidence_directory_rejects_unverified_artifact(tmp_path, monkeypatch):
    root, *arguments = _degraded_evidence_directory(tmp_path, monkeypatch)
    (root / "candidate-receipt.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="directory inventory"):
        _validate_directory(root, *arguments)


def test_missing_supply_chain_evidence_keeps_candidate_blocked():
    manifest = AgenticV2SubstrateManifest.load(MANIFEST)
    subject = _subject(manifest)
    policy = SupplyChainPolicy.load(POLICY)

    report = build_blocked_evidence_report(
        subject,
        policy,
        capability_receipt_sha256="a" * 64,
        oci_layout_report_sha256="b" * 64,
    )

    assert report["gate_status"] == "blocked"
    assert report["blocking_evidence"] == [
        "containment", "cve", "license", "microvm", "provenance", "sbom", "signature"
    ]
    assert validate_evidence_report(report, subject, policy) == report

    forged = deepcopy(report)
    forged["gate_status"] = "candidate_complete"
    with pytest.raises(ValueError, match="gate result"):
        validate_evidence_report(forged, subject, policy)


def test_evidence_subject_mismatch_is_rejected():
    manifest = AgenticV2SubstrateManifest.load(MANIFEST)
    subject = _subject(manifest)
    policy = SupplyChainPolicy.load(POLICY)
    report = build_blocked_evidence_report(
        subject,
        policy,
        capability_receipt_sha256="a" * 64,
        oci_layout_report_sha256="b" * 64,
    )
    report["evidence"]["capability_receipt"]["subject_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="evidence identity"):
        validate_evidence_report(report, subject, policy)


@pytest.mark.parametrize("name", ["cve", "microvm", "provenance", "signature"])
def test_unimplemented_evidence_cannot_be_forged_verified(name):
    manifest = AgenticV2SubstrateManifest.load(MANIFEST)
    subject = _subject(manifest)
    policy = SupplyChainPolicy.load(POLICY)
    report = build_blocked_evidence_report(
        subject,
        policy,
        capability_receipt_sha256="a" * 64,
        oci_layout_report_sha256="b" * 64,
    )
    report["evidence"][name] = {
        "status": "verified",
        "subject_sha256": subject.sha256,
        "tool": {"name": "forged", "version": "1", "sha256": "c" * 64},
        "report_sha256": "d" * 64,
    }
    report["blocking_evidence"].remove(name)

    with pytest.raises(ValueError, match="status is not implemented"):
        validate_evidence_report(report, subject, policy)


def test_microvm_missing_runtime_is_explicit_not_run(tmp_path):
    report = inspect_microvm_readiness(
        path_lookup=lambda _name: None,
        kvm_path=tmp_path / "missing-kvm",
        asset_paths={
            "kernel": tmp_path / "missing-kernel",
            "rootfs": tmp_path / "missing-rootfs",
        },
    )

    assert report["status"] == "not_run"
    assert not any(report["checks"].values())
    assert validate_microvm_readiness_report(report) == report


def test_microvm_ready_report_binds_asset_hashes(tmp_path):
    kernel = tmp_path / "vmlinux"
    rootfs = tmp_path / "rootfs.ext4"
    kvm = tmp_path / "kvm"
    firecracker = tmp_path / "firecracker"
    jailer = tmp_path / "jailer"
    kernel.write_bytes(b"kernel")
    rootfs.write_bytes(b"rootfs")
    kvm.write_bytes(b"kvm")
    firecracker.write_bytes(b"firecracker")
    jailer.write_bytes(b"jailer")
    kvm.chmod(0o600)
    report = inspect_microvm_readiness(
        path_lookup=lambda name: str({
            "firecracker": firecracker,
            "jailer": jailer,
        }[name]),
        kvm_path=kvm,
        asset_paths={"kernel": kernel, "rootfs": rootfs},
        kvm_probe=lambda path: path == kvm,
    )

    assert report["status"] == "ready_for_boot_test"
    validate_microvm_readiness_report(report)
    report["assets"]["kernel"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="readiness identity"):
        validate_microvm_readiness_report(report)


def _effective_sbom_fixture():
    observation = {"package_inventory": {
        "debian": {"count": 1, "records": ["bash:amd64=1"], "sha256": ""},
        "python": {"count": 1, "records": ["pandas=1"], "sha256": ""},
        "r": {"count": 1, "records": ["base=1"], "sha256": ""},
        "npm": {"count": 1, "records": ["npm=1"], "sha256": ""},
    }}
    from core.agentic_v2_substrate import canonical_sha256
    for item in observation["package_inventory"].values():
        item["sha256"] = canonical_sha256(item["records"])
    packages = []
    for index, purl in enumerate((
        "pkg:deb/debian/bash@1?arch=amd64",
        "pkg:pypi/pandas@1",
        "pkg:cran/base@1",
        "pkg:npm/npm@1",
    )):
        ecosystem = ("deb", "pypi", "cran", "npm")[index]
        name = ("bash", "pandas", "base", "npm")[index]
        spdx_id = "SPDXRef-Package-" + hashlib.sha256(
            f"{ecosystem}\0{name}\0{1}".encode("utf-8")
        ).hexdigest()[:24]
        packages.append({
            "SPDXID": spdx_id,
            "name": name,
            "versionInfo": "1",
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "MIT",
            "supplier": "NOASSERTION",
            "externalRefs": [{
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": purl,
            }],
        })
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "gdpval-agentic-v2-professional-work-candidate",
        "documentNamespace": (
            "https://github.com/hyeonsangjeon/gdpval-realworks/"
            "sbom/agentic-v2-phase1b/" + canonical_sha256(packages)
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
    return observation, sbom


def test_effective_sbom_reconciles_ecosystem_counts():
    observation, sbom = _effective_sbom_fixture()

    assert validate_effective_sbom(sbom, observation) == sbom
    sbom["packages"].pop()
    with pytest.raises(ValueError, match="inventory mismatch"):
        validate_effective_sbom(sbom, observation)


def test_effective_sbom_rejects_purl_package_mismatch():
    observation, sbom = _effective_sbom_fixture()
    sbom["packages"][1]["externalRefs"][0]["referenceLocator"] = (
        "pkg:pypi/numpy@1"
    )

    with pytest.raises(ValueError, match="package purl"):
        validate_effective_sbom(sbom, observation)


def test_license_policy_uses_exact_spdx_identifiers():
    policy = SupplyChainPolicy.load(POLICY)
    sbom = {"packages": [
        {
            "licenseDeclared": "MIT OR Apache-2.0",
            "externalRefs": [{"referenceLocator": "pkg:pypi/good@1"}],
        },
        {
            "licenseDeclared": "SSPL-1.0",
            "externalRefs": [{"referenceLocator": "pkg:pypi/denied@1"}],
        },
        {
            "licenseDeclared": "MIT License",
            "externalRefs": [{"referenceLocator": "pkg:pypi/unknown@1"}],
        },
    ]}

    report = evaluate_license_policy(sbom, policy)

    assert report["status"] == "failed"
    assert report["denied_count"] == 1
    assert report["unknown_count"] == 1


def test_license_policy_does_not_use_substring_matching():
    policy = SupplyChainPolicy.load(POLICY)
    sbom = {"packages": [{
        "licenseDeclared": "MIT-SSPL-1.0-compatible",
        "externalRefs": [{"referenceLocator": "pkg:pypi/not-denied@1"}],
    }]}

    report = evaluate_license_policy(sbom, policy)

    assert report["denied_count"] == 0
    assert report["unknown_count"] == 1


def test_license_policy_denies_exact_nonstandard_policy_identifier():
    policy = SupplyChainPolicy.load(POLICY)
    sbom = {"packages": [{
        "licenseDeclared": "Commons-Clause",
        "externalRefs": [{"referenceLocator": "pkg:pypi/denied@1"}],
    }]}

    report = evaluate_license_policy(sbom, policy)

    assert report["denied_count"] == 1
    assert report["unknown_count"] == 1