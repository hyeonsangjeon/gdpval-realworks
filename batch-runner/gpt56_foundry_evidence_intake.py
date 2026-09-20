"""Bind privacy-screened, externally acquired Foundry evidence offline.

Only the fixed JSON export vocabulary is accepted, never arbitrary response
bodies, credentials, endpoints or personal identifiers. Source kinds and
resource-ID hashes remain external claims. Consistency is not authenticity,
capability approval, an inference identity or permission to launch a pilot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

import gpt56_sol_codex_pilot_preflight as pilot
from core.cost_receipts import (
    REASON_CALL_REACHABILITY_UNKNOWN, REASON_PRICE_MISSING,
    REASON_USAGE_ABSENT, REASON_USAGE_PARTIAL,
)
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _object, _read_bytes

SCHEMA_PATH = "batch-runner/schemas/foundry-pilot-evidence.schema.json"
INTAKE_PATH = "foundry-pilot-evidence-intake.json"
READY_PATH = "foundry-pilot-evidence-ready.json"
ROLES = ("identity", "reasoning", "context", "native_caps", "usage", "tariff")
KINDS = dict(zip(ROLES, (
    "foundry_identity_export", "foundry_response_export", "foundry_response_export",
    "codex_native_enforcement_export", "foundry_usage_export", "foundry_tariff_export",
)))
METERS = ("input_tokens", "cached_input_tokens", "output_tokens")


class EvidenceIntakeRefused(ValueError):
    """A static refusal code; never include untrusted content or paths."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default error includes unrecognized values. They might be
        # credentials supplied in error; this CLI must never repeat them.
        raise EvidenceIntakeRefused("invalid_cli_arguments")


@dataclass(frozen=True)
class FoundryEvidenceBundle:
    """An immutable local snapshot; only complete snapshots can be published."""

    document_json: str
    files: tuple[tuple[str, bytes], ...]
    missing: tuple[str, ...]

    def canonical_bytes(self) -> bytes:
        return self.document_json.encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.document_json)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EvidenceIntakeRefused(code)


def _identity(data: bytes) -> dict[str, Any]:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _strict_scalars(value: Any) -> None:
    # JSON Schema considers 1.0 an integer. Evidence must not coerce it, or a
    # capability boolean, into a count. Rates use decimal strings, not floats.
    _require(not isinstance(value, (float, bool)), "non_exact_scalar")
    if isinstance(value, dict):
        for child in value.values():
            _strict_scalars(child)
    elif isinstance(value, list):
        for child in value:
            _strict_scalars(child)


def _json(data: bytes) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"), object_pairs_hook=_object)
    _require(type(value) is dict, "object_required")
    _strict_scalars(value)
    _canonical_json(value)
    return value


def _time(value: str) -> datetime:
    _require(type(value) is str and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value) is not None,
             "utc_time_required")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _validate(schema: dict[str, Any], value: Any, definition: str | None = None) -> None:
    selected = schema if definition is None else {"$defs": schema["$defs"], "$ref": "#/$defs/" + definition}
    _require(Draft202012Validator(selected).is_valid(value), "evidence_schema_mismatch")


def _nulls(value: Any, path: str) -> list[str]:
    if value is None:
        return [path]
    if isinstance(value, dict):
        return [name for key, item in sorted(value.items()) for name in _nulls(item, path + "." + key)]
    return []


def _local_file(path: Path, **expected: Any) -> bytes:
    metadata = path.lstat()
    _require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
             and 0 < metadata.st_size <= 65536, "unsafe_or_oversize_evidence_file")
    return _read_bytes(path, **expected)


def _active_plan() -> tuple[dict[str, Any], dict[str, Any]]:
    # The verifier is deliberately tied to its own source checkout. The caller's
    # SHA is a separate externally reviewed binding, not Git discovery here.
    plan = yaml.safe_load(_read_bytes(pilot.ROOT / pilot.ACTIVE_PLAN))
    _require(type(plan) is dict and set(plan.get("source_pins", {})) == pilot.REQUIRED_SOURCES,
             "active_source_pin_set")
    for name, digest in plan["source_pins"].items():
        _read_bytes(_path(pilot.ROOT, name), sha256=digest)
    _require(pilot.inspect_plan(plan)["configuration_valid"], "active_plan_invalid")
    _require(plan["launch_enabled"] is False and plan["pilot"]["full_220_enabled"] is False,
             "launch_flags_changed")
    # A schema contains booleans such as additionalProperties: false; those
    # are not evidence values and must not pass through the scalar checker.
    return plan, json.loads(_read_bytes(pilot.ROOT / SCHEMA_PATH), object_pairs_hook=_object)


def _inventory(root: Path, names: set[str], *, published: bool) -> None:
    expected_top = {INTAKE_PATH, "artifacts"} | ({READY_PATH} if published else set())
    _require({path.name for path in root.iterdir()} == expected_top, "unexpected_bundle_member")
    artifacts = _root(root / "artifacts")
    _require({"artifacts/" + path.name for path in artifacts.iterdir()} == names,
             "artifact_set_mismatch")


def _compile(root: Path, reviewed_source_sha: str, as_of: str, *, published: bool = False) -> FoundryEvidenceBundle:
    root = _root(root)
    plan, schema = _active_plan()
    _require(type(reviewed_source_sha) is str and re.fullmatch(r"[0-9a-f]{40}", reviewed_source_sha) is not None,
             "reviewed_full_sha_required")
    _require(reviewed_source_sha not in {
        plan["base_sha"], plan["evidence_intake"]["source_base_sha"],
        plan["dataset"]["revision"], plan["grading"]["source_sha"], "0" * 40,
    }, "historical_sha_is_not_reviewed_source")
    evaluated = _time(as_of)
    intake_data = _local_file(root / INTAKE_PATH)
    intake = _json(intake_data)
    _validate(schema, intake)
    _require(intake["reviewed_source_sha"] == reviewed_source_sha, "reviewed_sha_mismatch")
    _require(intake["plan_base_sha"] == plan["base_sha"] and intake["plan_sha256"] == pilot.seal(plan)
             and intake["run_id"] == plan["pilot"]["run_id"], "stale_plan_binding")
    _require(_time(intake["evaluated_at"]) <= evaluated, "evaluation_time_mismatch")
    if not published:
        _require(intake["evaluated_at"] == as_of, "evaluation_time_mismatch")
    _require([claim["role"] for claim in intake["claims"]] == list(ROLES), "exact_ordered_roles_required")
    names = {"artifacts/" + claim["role"] + ".json" for claim in intake["claims"] if claim["artifact"] is not None}
    _inventory(root, names, published=published)
    files = {INTAKE_PATH: intake_data}
    claims: dict[str, Any] = {}
    missing: list[str] = []
    with _held_parents(root, (INTAKE_PATH, *sorted(names))) as check:
        for claim in intake["claims"]:
            role, reference = claim["role"], claim["artifact"]
            if reference is None:
                missing.append(role + ".artifact")
                claims[role] = {"artifact": None, "evidence": None}
                continue
            name = "artifacts/" + role + ".json"
            _require(reference["path"] == name, "artifact_role_path_mismatch")
            data = _local_file(_path(root, name), size=reference["size"], sha256=reference["sha256"])
            record = _json(data)
            _validate(schema, record, "artifact")
            _require(record["role"] == role, "artifact_role_mismatch")
            definition = "subject" if role == "identity" else role
            for field in ("documented", "observed"):
                if record[field] is not None:
                    _validate(schema, record[field], definition)
            _require(record["source_kind"] in (None, "documentation", KINDS[role]), "source_kind_mismatch")
            if record["source_kind"] != KINDS[role]:
                _require(record["observed"] is None, "declaration_is_not_observation")
                missing.append(role + ".observed_source")
            for field in ("issued_at", "observed_at", "valid_until"):
                if record[field] is not None:
                    _time(record[field])
            for field in ("issued_at", "observed_at"):
                if record[field] is not None:
                    _require(_time(record[field]) <= evaluated, "future_evidence_time")
            if record["issued_at"] is not None and record["observed_at"] is not None:
                _require(_time(record["observed_at"]) <= _time(record["issued_at"]) <= evaluated,
                         "future_or_contradictory_evidence_time")
            if record["valid_until"] is not None:
                _require(evaluated <= _time(record["valid_until"]), "expired_evidence")
            for field in ("source_kind", "issued_at", "observed_at", "valid_until", "subject", "observed"):
                missing.extend(_nulls(record[field], role + "." + field))
            files[name] = data
            claims[role] = {"artifact": reference, "evidence": record}
        _check_observations(claims, evaluated, missing)
        check()
        _inventory(root, names, published=published)
        for name, data in files.items():
            _require(_local_file(root / name, **_identity(data)) == data, "evidence_changed_during_snapshot")
        check()
    document = {
        "bundle_version": "foundry-pilot-evidence-ready-v1",
        "evidence_boundary": "offline_local_consistency",
        "reviewed_source_sha": reviewed_source_sha, "plan_base_sha": plan["base_sha"],
        "plan_sha256": pilot.seal(plan), "run_id": intake["run_id"],
        "evaluated_at": intake["evaluated_at"], "requested": intake["requested"],
        "claims": claims, "source_pins": plan["source_pins"],
        "receipt_schema": plan["results"]["receipt_schema"], "cost_policy": plan["cost"]["policy"],
        "files": {name: _identity(data) for name, data in sorted(files.items())},
        "missing_evidence": sorted(set(missing)), "evidence_complete": not missing,
        "launch_enabled": False, "full_220_enabled": False,
        "remaining_launch_blockers": list(pilot.LAUNCH_BLOCKERS),
    }
    return FoundryEvidenceBundle(_canonical_json(document), tuple(sorted(files.items())), tuple(document["missing_evidence"]))


def _check_observations(claims: dict[str, Any], evaluated: datetime, missing: list[str]) -> None:
    records = {role: value["evidence"] for role, value in claims.items()}
    identity = records["identity"]
    if identity is not None:
        for record in records.values():
            if record is not None:
                _require(_canonical_json(record["subject"]) == _canonical_json(identity["subject"]), "deployment_subject_mismatch")
        if identity["observed"] is not None:
            _require(_canonical_json(identity["observed"]) == _canonical_json(identity["subject"]), "observed_identity_mismatch")
    observed = {role: record["observed"] if record else None for role, record in records.items()}
    context = observed["context"]
    if context is not None and not _nulls(context, "context"):
        _require(context["accepted_input_tokens"] + context["accepted_output_tokens"] >= 1_000_000,
                 "observed_context_below_request")
    reasoning = observed["reasoning"]
    if context is not None and reasoning is not None:
        left, right = context["response_id_sha256"], reasoning["response_id_sha256"]
        if left is not None and right is not None:
            _require(left == right, "max_and_context_response_mismatch")
    usage, tariff = observed["usage"], observed["tariff"]
    if usage is not None:
        _require(set(usage["partial_reasons"]) <= {
            REASON_USAGE_ABSENT, REASON_USAGE_PARTIAL, REASON_PRICE_MISSING,
            REASON_CALL_REACHABILITY_UNKNOWN,
        }, "receipt_reason_mismatch")
        if usage["partial_reasons"]:
            missing.append("usage.partial_reasons")
        total, cached = (usage["meters"][name]["quantity"] for name in ("input_tokens", "cached_input_tokens"))
        if total is not None and cached is not None:
            _require(cached <= total, "cached_tokens_exceed_input")
        meter_ids = [usage["meters"][meter]["meter_id"] for meter in METERS]
        _require(len([item for item in meter_ids if item is not None]) == len({item for item in meter_ids if item is not None}),
                 "duplicate_usage_meter")
    if tariff is not None:
        for field in ("effective_at", "expires_at"):
            if tariff[field] is not None:
                _time(tariff[field])
        if tariff["effective_at"] is not None and tariff["expires_at"] is not None:
            _require(_time(tariff["effective_at"]) <= evaluated <= _time(tariff["expires_at"]), "tariff_not_effective")
            usage_time = records["usage"]["observed_at"] if records["usage"] else None
            if usage_time is not None:
                _require(_time(tariff["effective_at"]) <= _time(usage_time) <= _time(tariff["expires_at"]),
                         "tariff_not_effective_for_usage")
    if usage is not None and tariff is not None:
        for field in ("currency", "region"):
            if usage[field] is not None and tariff[field] is not None:
                _require(usage[field] == tariff[field], "tariff_usage_mapping_mismatch")
        for meter in METERS:
            left, right = usage["meters"][meter]["meter_id"], tariff["rates"][meter]["meter_id"]
            if left is not None and right is not None:
                _require(left == right, "tariff_usage_mapping_mismatch")


def compile_foundry_evidence(*, source: Path, reviewed_source_sha: str, as_of: str) -> FoundryEvidenceBundle:
    """Read all bytes without writes. Null evidence stays null and cannot be ready.

    The SHA and UTC evaluation time come from the caller, not Git, Azure or the
    clock. Exceptions carry static codes only; malformed exports are never echoed.
    """
    try:
        return _compile(source, reviewed_source_sha, as_of)
    except EvidenceIntakeRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise EvidenceIntakeRefused("evidence_read_or_validation_refused") from None


def _destination(destination: Path) -> tuple[Path, Path]:
    path = Path(destination)
    _require(".." not in path.parts, "destination_traversal")
    path = Path(os.path.abspath(path))
    _require(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}", path.name) is not None, "destination_name_refused")
    _root(path.parent)
    return path, path.with_name(path.name + ".foundry-evidence-reservation.json")


def _reservation(bundle: FoundryEvidenceBundle) -> bytes:
    return _canonical_json({
        "reservation_version": "foundry-pilot-evidence-reservation-v1",
        "ready_path": READY_PATH, "intended_ready": _identity(bundle.canonical_bytes()),
    }).encode("utf-8")


def publish_foundry_evidence(*, source: Path, destination: Path, reviewed_source_sha: str, as_of: str) -> FoundryEvidenceBundle:
    """Reserve an absent destination, publish exact members and ready last.

    A failure retains its reservation and partial tree for manual disposition.
    Neither a retry nor this function may overwrite, reuse or delete them.
    """
    try:
        source = _root(source)
        root, reserved = _destination(destination)
        _require(not source.is_relative_to(root) and not root.is_relative_to(source), "source_destination_overlap")
        with ExitStack() as descriptors, _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            parent_fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.callback(os.close, parent_fd)
            check_parent()
            _require(not os.path.lexists(root) and not os.path.lexists(reserved), "destination_or_reservation_exists")
            bundle = compile_foundry_evidence(source=source, reviewed_source_sha=reviewed_source_sha, as_of=as_of)
            _require(not bundle.missing, "required_evidence_incomplete")
            check_parent()
            _write_no_clobber(reserved, _reservation(bundle))
            check_parent()
            os.mkdir(root.name, mode=0o700, dir_fd=parent_fd)
            check_parent()
            with _held_parents(root, (READY_PATH,)) as check_root:
                root_fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                descriptors.callback(os.close, root_fd)
                check_root()
                os.mkdir("artifacts", mode=0o700, dir_fd=root_fd)
                with _held_parents(root, tuple(name for name, _ in bundle.files)) as check_members:
                    for name, data in bundle.files:
                        check_parent()
                        check_root()
                        check_members()
                        _write_no_clobber(_path(root, name), data)
                    # No verification that can fail follows ready publication.
                    installed = _compile(root, reviewed_source_sha, as_of)
                    current = compile_foundry_evidence(source=source, reviewed_source_sha=reviewed_source_sha, as_of=as_of)
                    _require(installed == bundle == current, "bundle_changed_before_ready")
                    _read_bytes(reserved, **_identity(_reservation(bundle)))
                    check_parent()
                    check_root()
                    check_members()
                    _write_no_clobber(root / READY_PATH, bundle.canonical_bytes())
                    return bundle
    except EvidenceIntakeRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise EvidenceIntakeRefused("evidence_publication_refused_no_reuse") from None


def verify_foundry_evidence(*, bundle_root: Path, reviewed_source_sha: str, as_of: str) -> FoundryEvidenceBundle:
    """Recompute a published bundle and reservation without granting launch."""
    try:
        root, reserved = _destination(bundle_root)
        with _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
            with _held_parents(_root(root), (READY_PATH,)) as check_root:
                bundle = _compile(root, reviewed_source_sha, as_of, published=True)
                _require(not bundle.missing, "required_evidence_incomplete")
                _require(_local_file(root / READY_PATH, **_identity(bundle.canonical_bytes())) == bundle.canonical_bytes(), "ready_bytes_mismatch")
                _read_bytes(reserved, **_identity(_reservation(bundle)))
                check_parent()
                check_root()
                return bundle
    except EvidenceIntakeRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        raise EvidenceIntakeRefused("evidence_verification_refused") from None


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--source", type=Path)
    inputs.add_argument("--verify-bundle", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--as-of", required=True, help="Externally supplied UTC evaluation time, YYYY-MM-DDTHH:MM:SSZ")
    try:
        args = parser.parse_args(argv)
        _require(not (args.verify_bundle and args.destination), "verification_cannot_publish")
        options = {"reviewed_source_sha": args.reviewed_source_sha, "as_of": args.as_of}
        if args.verify_bundle:
            result = verify_foundry_evidence(bundle_root=args.verify_bundle, **options)
        elif args.destination:
            result = publish_foundry_evidence(source=args.source, destination=args.destination, **options)
        else:
            result = compile_foundry_evidence(source=args.source, **options)
        report = {"evidence_complete": not result.missing, "bundle_sha256": result.sha256,
                  "ready_present": bool(args.verify_bundle or args.destination), "missing_evidence": list(result.missing)}
        code = 2 if result.missing else 0
    except EvidenceIntakeRefused as error:
        report, code = {"error": str(error), "ready_present": False}, 2
    report.update({"launch_enabled": False, "full_220_enabled": False})
    sys.stdout.write(_canonical_json(report) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
