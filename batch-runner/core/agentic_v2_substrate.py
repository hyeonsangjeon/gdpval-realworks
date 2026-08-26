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


# NOTHING MAY BE INSERTED ABOVE THIS POINT WITHOUT REPINNING THE LICENCE
# EVALUATOR. core/agentic_v2_license.py freezes the exact bytecode identity of
# canonical_sha256 above, and that identity includes the line it starts on. Add
# a line anywhere before it and every licence report stops validating, with an
# error that names the licence evaluator and never mentions this file. New
# constants for this module therefore go here, below it, not up with the others.

# ── The containment rules ─────────────────────────────────────────────────
#
# What a command is allowed to touch when Agentic Sandbox V2 eventually runs
# one. A substrate manifest promising anything different fails to validate.
#
# Six things have to be stated for this to be a containment rather than a
# gesture: where it may write, whether it can reach the network, how much
# memory it gets, how long it may run, who it runs as, and what happens when it
# exceeds any of them. Until 2026-08-26 only the first two were written down,
# and the working directory said "there is a quota" without ever saying what
# the quota was. A limit with no number is not a limit.
#
# Every value here is a *chosen* limit rather than a measured one, and for a
# containment that is the right kind of number — the point is to decide what is
# allowed, not to record what happened. Where a value is derived from something
# else in this repository, a test fails if the two stop agreeing; where it was
# simply picked, it says so.
#
# **One other file still states these rules, and it has to.**
# security/agentic-v2-supply-chain-policy.json is a signed artefact, so it
# physically carries its own copy of the values in its own published wording —
# it says ``read_only_rootfs: true`` where this file says
# ``rootfs: "read-only"``. There was a third copy, hand-written into
# core/agentic_v2_supply_chain.py's validator, and nothing compared any two of
# the three; a rule could be weakened in one and left standing in the others
# with every check still passing. The validator's copy is gone as of
# 2026-08-26 — it derives what it requires from
# :func:`supply_chain_microvm_block` — and :func:`containment_rules_that_disagree`
# compares the signed file against this one, so drift is refused by name.
#
# core/agentic_v2_containment_readiness.py reads this to report which of these
# a given machine could actually meet.

MICROVM_WORKDIR_QUOTA_MIB = 256
"""How much the command may write, in mebibytes.

Derived, not picked. core/agentic_v2_fixture_backend.py already lets a model
hold 64 MiB of workspace and hand back 64 MiB of finished files, so a disk
below 128 MiB would let the tool layer accept a write the disk cannot hold —
the failure would surface as a disk error rather than as the ceiling the tool
layer meant to apply. This is twice that, so the disk is not the first thing to
fail. ``test_the_disk_is_not_smaller_than_the_tools_already_allow`` fails if
either backend ceiling is raised past it.
"""

MICROVM_MEMORY_MIB = 4096
"""How much memory the command gets, in mebibytes.

Picked, not derived, and this is the only rule here with nothing behind it to
derive from. 4 GiB is enough to open the spreadsheets and documents these tasks
involve with a library like pandas loaded, and small enough that a runaway
process stops instead of taking the host down with it.

**A difference between run places worth knowing about.** None of the three run
places in the comparison caps memory at all. Applying a cap here makes this
column stricter than the others on an axis the comparison does not otherwise
control, so a task that fails here for memory would not have failed elsewhere
for that reason. Recorded rather than hidden, because a comparison that is
uneven in a way nobody wrote down is worse than one that is uneven on purpose.
"""

MICROVM_WALL_CLOCK_SECONDS = 1200
"""How long the command may run, in seconds.

Derived from ``per_task_timeout_seconds`` in
experiments/execution_envelope/agentic_stage_one_plan.yaml, which is the same
figure the other run places are held to. A containment that cut a task off
earlier than the other columns do would make this run place look worse for a
reason that had nothing to do with the model.
``test_the_clock_matches_the_one_the_other_run_places_are_held_to`` fails if the
plan and this stop agreeing.
"""

REQUIRED_MICROVM_POLICY: dict[str, Any] = {
    "required": True,
    "runtime": "firecracker",
    "network": "none",
    "rootfs": "read-only",
    "workdir": "ephemeral-quota",
    "workdir_quota_mib": MICROVM_WORKDIR_QUOTA_MIB,
    "memory_mib": MICROVM_MEMORY_MIB,
    "wall_clock_seconds": MICROVM_WALL_CLOCK_SECONDS,
    # Not a separate decision: Firecracker's jailer is what drops privileges,
    # and the signed policy already requires it. Written down anyway, because
    # "which user does the command run as" is one of the six questions, and
    # answering it by implication elsewhere is how it went unanswered here.
    "user": "jailer-unprivileged",
    # What happens on breach. Stop and say so — never carry on with the rule
    # relaxed, and never fail quietly. Section 7 of the specification asks for
    # exactly this: stage three must fail loudly when its containment is
    # unavailable, and a rule that has been exceeded is a containment that is
    # not holding.
    "on_breach": "stop-and-report",
}

# The same rules as the signed supply-chain policy states them. The key is that
# file's name for the rule; the value is what each side has to say for the two
# to be stating the same thing. The signed policy writes most of its rules as
# true/false, so the pair is not a comparison of like with like and cannot be
# left implicit.
_SUPPLY_CHAIN_RULE_NAMES: dict[str, tuple[str, Any, Any]] = {
    "runtime": ("runtime", "firecracker", "firecracker"),
    "network": ("network", "none", "none"),
    "read_only_rootfs": ("rootfs", "read-only", True),
    "ephemeral_work_disk": ("workdir", "ephemeral-quota", True),
}

# Two rules the signed policy states that have no counterpart above, because
# they are facts about the host rather than settings applied at start-up.
# core/agentic_v2_containment_readiness.py reads the machine for both.
SUPPLY_CHAIN_HOST_FACTS: dict[str, Any] = {
    "jailer_required": True,
    "kvm_required": True,
}


def supply_chain_microvm_block() -> dict[str, Any]:
    """Exactly what the signed policy's containment block has to say.

    Derived from the rules above rather than written out a third time.
    core/agentic_v2_supply_chain.py held its own hand-written copy of this until
    2026-08-26, which made three places stating one set of rules and no check
    that any two of them agreed.
    """
    block = dict(SUPPLY_CHAIN_HOST_FACTS)
    for their_name, (our_name, _, theirs_must_be) in _SUPPLY_CHAIN_RULE_NAMES.items():
        block[their_name] = theirs_must_be
    return block


def containment_rules_that_disagree(supply_chain_microvm: Any) -> list[str]:
    """Where the signed policy and the rules above stop saying the same thing.

    Two written-down copies of one rule is two chances to weaken it and one
    chance to notice. This is the noticing. Returns a description per rule that
    has drifted, and an empty list when they agree.
    """
    if not isinstance(supply_chain_microvm, Mapping):
        return ["the signed policy's containment block is not a set of rules"]

    drifted: list[str] = []
    for their_name, (our_name, ours_must_be, theirs_must_be) in sorted(
        _SUPPLY_CHAIN_RULE_NAMES.items()
    ):
        ours = REQUIRED_MICROVM_POLICY.get(our_name)
        theirs = supply_chain_microvm.get(their_name)
        if ours == ours_must_be and theirs == theirs_must_be:
            continue
        drifted.append(
            f"containment rule {our_name!r} disagrees between the two places "
            f"it is written down: core.agentic_v2_substrate says {ours!r} and "
            f"security/agentic-v2-supply-chain-policy.json says "
            f"{their_name}={theirs!r}"
        )
    return drifted


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
    if (
        document["microvm"] != REQUIRED_MICROVM_POLICY
        or document["microvm"].get("required") is not True
    ):
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