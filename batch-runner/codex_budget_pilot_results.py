"""Read local CI completions into the registered 30-cell order; never dispatch.

The reviewed source and (when present) verified-input fingerprint are external
expectations, not approvals issued by this reader. No originals are opened.
Usage/cost stay per cell: no token totals, prices, grades or remote deduplication.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
from gpt54_codex_input_capture import _write_no_clobber

MAX_ENVELOPE_BYTES = 64 * 1024
MAX_RESULT_BYTES = 2 * 1024 * 1024
OBSERVED_FIELDS = (
    "plan_sha256", "verified_inputs_sha256", "status", "reason",
    "execution_requested", "child_invocations", "exit_code", "timeout",
    "cleanup_confirmed", "receipt", "artifacts",
)


class PilotResultsRefused(ValueError):
    """Closed errors: never include an input filename or exception body."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PilotResultsRefused("invalid_arguments")


def _hash(value: str | None, width: int = 64) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(width) + "}", value) is not None


def _read_completion(path: Path) -> dict:
    """Bound the read before parsing; keep the producer's checksum and validator."""
    try:
        if ".." in path.parts:
            raise PilotResultsRefused("completion_file_refused")
        pilot._assert_no_symlink_ancestors(path)
        # NONBLOCK prevents a substituted FIFO from blocking before fstat.
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or not 0 < before.st_size <= MAX_ENVELOPE_BYTES):
                raise PilotResultsRefused("completion_file_refused")
            data = stream.read(MAX_ENVELOPE_BYTES + 1)
            after = os.fstat(stream.fileno())
            pilot._assert_no_symlink_ancestors(path)
            current = path.lstat()
            fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
            if (len(data) != before.st_size or any(
                    getattr(before, key) != getattr(item, key)
                    for key in fields for item in (after, current))):
                raise PilotResultsRefused("completion_file_changed")
        document = pilot._json_object(data)  # Also refuses duplicate keys / nonfinite numbers.
        if (set(document) != {"payload", "sha256"}
                or document["sha256"] != pilot._digest(document["payload"])):
            raise PilotResultsRefused("completion_checksum_mismatch")
        return ci.validate_completion(document["payload"])
    except PilotResultsRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        raise PilotResultsRefused("invalid_completion_envelope") from error


def aggregate(reviewed_source_sha: str, envelopes: list[Path], *,
              expected_verified_inputs_sha256: str | None = None) -> dict:
    """Validate every envelope before producing rows, including unobserved cells."""
    if not _hash(reviewed_source_sha, 40):
        raise PilotResultsRefused("explicit_reviewed_source_sha_required")
    if expected_verified_inputs_sha256 is not None and not _hash(expected_verified_inputs_sha256):
        raise PilotResultsRefused("invalid_verified_inputs_expectation")
    try:
        plan, _, _ = pilot.compile_pilot(ci.CAMPAIGN, reviewed_source_sha)
        registration_sha = hashlib.sha256(pilot._read_bytes(ci.REGISTRATION)).hexdigest()
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise PilotResultsRefused("registered_controls_refused") from error
    cells = {cell["cell_id"]: cell for cell in plan["cells"]}
    denominator = ci.PUBLIC_FIXED["denominator"]
    if len(cells) != denominator or list(cells) != plan["order"]:
        raise PilotResultsRefused("registered_order_refused")
    if len(envelopes) > denominator:
        raise PilotResultsRefused("too_many_completion_envelopes")
    bindings = {
        "campaign_id": ci.CAMPAIGN, "source_sha": reviewed_source_sha,
        "order_sha256": pilot._digest(plan["order"]), "registration_sha256": registration_sha,
        "host_policy_sha256": pilot._digest(ci.HOST_POLICY),
        "declared_inputs_sha256": pilot._digest(plan["dataset"]),
    }
    observed = {}
    for path in envelopes:
        envelope = _read_completion(path)
        key = envelope["cell_id"]
        if key not in cells:
            raise PilotResultsRefused("foreign_cell")
        if key in observed:
            raise PilotResultsRefused("duplicate_cell")
        expected = {**bindings, "config_sha256": cells[key]["config_sha256"]}
        if any(envelope[field] != value for field, value in expected.items()):
            raise PilotResultsRefused("completion_binding_mismatch")
        verified = envelope["verified_inputs_sha256"]
        if verified is not None:
            if expected_verified_inputs_sha256 is None:
                raise PilotResultsRefused("external_verified_inputs_expectation_required")
            if verified != expected_verified_inputs_sha256:
                raise PilotResultsRefused("verified_inputs_mismatch")
        observed[key] = envelope

    rows = []
    for key in plan["order"]:
        cell, envelope = cells[key], observed.get(key)
        row = {field: cell[field] for field in (
            "cell_id", "task_id", "condition", "repetition", "config_sha256")}
        row.update({field: None for field in OBSERVED_FIELDS})
        row.update(status="NOT_OBSERVED", completion_payload_sha256=None)
        if envelope is not None:
            row.update({field: envelope[field] for field in OBSERVED_FIELDS})
            row["completion_payload_sha256"] = pilot._digest(envelope)
        rows.append(row)
    return {
        "format": "codex-budget-pilot-results-v1", **bindings, "denominator": denominator,
        "observed_envelopes": len(observed), "status_counts": dict(Counter(row["status"] for row in rows)),
        "expected_verified_inputs_sha256": expected_verified_inputs_sha256,
        "proof_limits": {
            "reviewed_source": "caller_assertion",
            "plan_and_runner_instance_binding": "unavailable_in_completion_v1",
            "receipt_preimage": "unavailable_in_completion_v1",
            "original_input_bytes": "not_read",
        },
        "usage_and_cost": "per_cell_only_no_totals",
        "other_cells_not_run": "local_declaration_not_summed",
        "remote_execution_deduplicated": False, "grading_launched": False,
        "invoice_complete": False, "http_request_count": None, "cells": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--envelope", type=Path, action="append", default=[],
                        help="Explicit local one-cell completion file; repeat at most 30 times")
    parser.add_argument("--expected-verified-inputs-sha256",
                        help="External expected files_sha256; required for any non-null verified-input binding")
    parser.add_argument("--out", required=True, type=Path, help="Absent result file in an existing local directory")
    try:
        args = parser.parse_args(argv)
        if ".." in args.out.parts:
            raise PilotResultsRefused("output_path_refused")
        if os.path.lexists(args.out):
            raise PilotResultsRefused("output_exists")
        result = aggregate(args.reviewed_source_sha, args.envelope,
                           expected_verified_inputs_sha256=args.expected_verified_inputs_sha256)
        data = (pilot._canonical_json(result) + "\n").encode("utf-8")
        if len(data) > MAX_RESULT_BYTES:
            raise PilotResultsRefused("result_size_limit")
        # Complete one-file publication is the ready marker. The existing atomic
        # no-replace helper holds its parent; no directory bundle or adoption.
        _write_no_clobber(args.out, data)
    except PilotResultsRefused as error:
        print(f"Pilot results refused: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print("Pilot results refused: result_publication_refused", file=sys.stderr)
        return 2
    sys.stdout.write(data.decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
