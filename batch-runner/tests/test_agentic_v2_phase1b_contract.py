from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from core.agentic_v2_substrate import (
    REQUIRED_COMMANDS,
    REQUIRED_FONT_FAMILIES,
    REQUIRED_PYTHON_MODULES,
    REQUIRED_SMOKES,
    AgenticV2SubstrateManifest,
    validate_capability_receipt,
)


MANIFEST_PATH = Path("sandbox/agentic_v2_capabilities.json")


def _manifest():
    return AgenticV2SubstrateManifest.load(MANIFEST_PATH)


def _receipt(manifest):
    return {
        "schema_version": "1.0",
        "substrate_id": "professional-work-v1",
        "manifest_sha256": manifest.sha256,
        "commands": [
            {"name": name, "version": "fixture-1.0", "sha256": "a" * 64}
            for name in sorted(REQUIRED_COMMANDS)
        ],
        "python_modules": [
            {"name": item["name"], "version": "fixture-1.0", "sha256": "b" * 64}
            for item in manifest.document["python_modules"]
        ],
        "font_families": [
            {"name": name, "version": "fixture-font.ttf", "sha256": "d" * 64}
            for name in manifest.document["font_families"]
        ],
        "smokes": [
            {"id": name, "status": "pass", "artifact_sha256": "c" * 64}
            for name in sorted(REQUIRED_SMOKES)
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


def test_phase1b_manifest_is_strict_canonical_and_foundation_only():
    manifest = _manifest()

    assert len(manifest.sha256) == 64
    assert manifest.document["foundation_only"] is True
    assert manifest.document["production_activation"] == "disabled"
    assert {item["name"] for item in manifest.document["commands"]} == REQUIRED_COMMANDS
    assert {item["name"] for item in manifest.document["python_modules"]} == REQUIRED_PYTHON_MODULES
    assert tuple(manifest.document["font_families"]) == REQUIRED_FONT_FAMILIES
    assert {item["id"] for item in manifest.document["smoke_matrix"]} == REQUIRED_SMOKES
    assert manifest.document["microvm"]["required"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"unexpected": True}),
        lambda value: value.update({"foundation_only": False}),
        lambda value: value["commands"].pop(),
        lambda value: value["commands"].append(deepcopy(value["commands"][0])),
        lambda value: value["smoke_matrix"].pop(),
        lambda value: value["microvm"].update({"network": "allowlist"}),
    ],
)
def test_phase1b_manifest_rejects_policy_drift(mutation):
    value = deepcopy(_manifest().document)
    mutation(value)

    with pytest.raises(ValueError, match="agentic v2 substrate"):
        AgenticV2SubstrateManifest.from_mapping(value)


def test_phase1b_manifest_rejects_numeric_microvm_required():
    value = deepcopy(_manifest().document)
    value["microvm"]["required"] = 1

    with pytest.raises(ValueError, match="microvm policy"):
        AgenticV2SubstrateManifest.from_mapping(value)


def test_phase1b_capability_receipt_binds_inventory_and_manifest():
    manifest = _manifest()
    receipt = _receipt(manifest)

    assert validate_capability_receipt(receipt, manifest) == receipt

    drifted = deepcopy(receipt)
    drifted["commands"][0]["sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="capability receipt command"):
        validate_capability_receipt(drifted, manifest)

    missing = deepcopy(receipt)
    missing["smokes"].pop()
    with pytest.raises(ValueError, match="smoke matrix"):
        validate_capability_receipt(missing, manifest)


@pytest.mark.parametrize(
    ("section", "digest_field"),
    [
        ("commands", "sha256"),
        ("python_modules", "sha256"),
        ("font_families", "sha256"),
        ("smokes", "artifact_sha256"),
        ("package_inventory", "sha256"),
    ],
)
def test_phase1b_capability_receipt_rejects_numeric_digests(
    section,
    digest_field,
):
    manifest = _manifest()
    receipt = _receipt(manifest)
    if section == "package_inventory":
        receipt[section]["debian"][digest_field] = int("1" * 64)
    else:
        receipt[section][0][digest_field] = int("1" * 64)

    with pytest.raises(ValueError, match="capability receipt"):
        validate_capability_receipt(receipt, manifest)