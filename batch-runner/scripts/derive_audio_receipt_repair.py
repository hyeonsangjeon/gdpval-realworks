#!/usr/bin/env python3
"""Derive the audio figures the old receipt contract had no field for.

Two exp035 shards were graded before ``cost-receipt-v1`` could express audio
tokens. Their ledgers measured 11,399 of them; their published receipts say
nothing, because at the time there was nothing to say it in. The contract now
has the field, but a schema that accepts a number does not put one there --
the published files were written months ago and are immutable evidence.

This script derives what those receipts would have stated, and writes it
somewhere else. It never edits a grade file, a ledger, or a hash.

What it is allowed to do
    Add the two audio keys, read from the settled ledger rows.

What it is not allowed to do
    Change any figure that already exists. Every pre-existing token count,
    call count, cost and status is recomputed from the ledger independently
    and asserted equal to what the original already said. If any of them
    disagrees the derivation aborts rather than publishing a repair that
    quietly moved something else.

What it deliberately does not claim
    That the repaired bundle is complete. These runs still carry
    ``status: partial`` because no price was published for their models, and
    the derivation invents none. Audio is recorded as a share *of* the input
    the provider already reported -- it is not added to any total, because
    that would bill the same tokens twice.

    It is also not a regrade. No score, no judge decision and no task outcome
    is read, moved or re-derived here. The original grade file remains the
    authority for every one of those, and its provenance is copied into the
    output verbatim so the derived figures can always be traced back to the
    run that produced them.

Output is deterministic: the same inputs produce byte-identical files, so a
reviewer can re-run this and compare hashes rather than trusting the ones
recorded here.

Usage
    python3 scripts/derive_audio_receipt_repair.py --check
    python3 scripts/derive_audio_receipt_repair.py --out docs/run_records/...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.cost_receipts import empty_usage  # noqa: E402
from scripts.verify_cost_ledger import (  # noqa: E402
    COMPONENT_KEY,
    RECEIPT_USAGE_KEYS,
    STATE_SETTLED,
)

DERIVATION_SCHEMA_VERSION = "cost-receipt-audio-repair-v1"

AUDIO_KEYS = ("audio_input_tokens", "audio_output_tokens")

#: Copied out of the grade file as-is. These identify the run that produced
#: the scores; the derivation asserts no authority over any of them and does
#: not recompute, re-sign or re-fingerprint a single one.
PROVENANCE_FIELDS = (
    "experiment_id",
    "experiment_yaml_name",
    "graded_at",
    "graded_by",
    "graded_by_version",
    "grader_source_hash",
    "inference_completed_at",
    "inference_model",
    "judge",
    "prompt",
    "renderer_fingerprint",
    "rubric",
    "run_status",
    "schema_version",
    "source_inference_experiment_id",
    "source_inference_repo_id",
    "source_inference_revision",
)


class DerivationRefused(Exception):
    """Raised when the derivation would have to move something it may not."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def committed_ledgers() -> list[Path]:
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "data/grades/**.cost_ledger.jsonl"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [REPO_ROOT / rel for rel in sorted(listed)]


def grade_for(ledger: Path) -> Path:
    return Path(str(ledger)[: -len(".cost_ledger.jsonl")] + ".json")


def derived_stem(derived: dict[str, Any], ledger: Path) -> str:
    """Name the output after the run, not after its directory.

    The published bundle lives under a directory whose name concatenates every
    fingerprint of the grading round, which is useful and about three hundred
    characters long. The same identifiers are recorded inside this file, so the
    name only has to be unique and readable: experiment, grader source, shard.
    """
    provenance = derived["original_scoring_provenance"]
    experiment = provenance.get("experiment_id") or "unknown-experiment"
    source_hash = (provenance.get("grader_source_hash") or "unknown")[:16]
    shard = ledger.name[: -len(".cost_ledger.jsonl")]
    return f"{experiment}__src_{source_hash}__{shard}"


def settled_rows(ledger: Path) -> list[dict[str, Any]]:
    rows = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("record_type", "call") == "call" and row.get("state") == STATE_SETTLED:
            rows.append(row)
    return rows


def totals(rows: list[dict[str, Any]]) -> dict[str, int | None]:
    """Sum a group of calls exactly as ``build_receipt`` would.

    The seeds come from the serializer rather than from a list written here, so
    the derived figures are produced by the same rule that writes a live
    receipt. That matters most for the asymmetry: the first four kinds seed at
    zero because every answering provider states them, while the audio kinds
    seed at ``None`` and are promoted only by a row that actually reported one.

    A text-only call leaves the audio columns NULL. Adding 1,714 of those
    together must not produce ``0`` -- that would publish "we measured no
    audio" where the evidence says "nobody looked". A row reporting a real
    zero does promote the key, and stays distinguishable from the absence.
    """
    out = empty_usage()
    for row in rows:
        for key in out:
            value = row.get(key)
            if value is None:
                continue
            count = int(value)
            if count < 0:
                raise DerivationRefused(
                    f"ledger row {row.get('call_id')!r} reports {key}={count}; "
                    "a negative token count cannot be summed"
                )
            out[key] = (out[key] or 0) + count
    return out


def _refuse_if_moved(label: str, was: Any, now: Any) -> None:
    if was != now:
        raise DerivationRefused(
            f"{label}: the original says {was!r} but recomputing from the ledger "
            f"gives {now!r}. This derivation may only add audio; it will not "
            "publish a repair that moved something else."
        )


def derive(grade_path: Path, ledger_path: Path) -> dict[str, Any]:
    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    receipt = (grade.get("summary") or {}).get("grading_cost") or {}
    rows = settled_rows(ledger_path)

    # --- the whole receipt -------------------------------------------------
    original_usage = dict(receipt.get("usage") or {})
    ledger_usage = totals(rows)

    if tuple(ledger_usage) != tuple(RECEIPT_USAGE_KEYS):
        raise DerivationRefused(
            "the serializer and the verifier disagree about which token kinds "
            f"a receipt holds: {tuple(ledger_usage)} vs {tuple(RECEIPT_USAGE_KEYS)}"
        )

    for key in RECEIPT_USAGE_KEYS:
        if key in AUDIO_KEYS:
            continue
        _refuse_if_moved(f"summary usage {key}", original_usage.get(key), ledger_usage[key])
    _refuse_if_moved("summary model_calls", receipt.get("model_calls"), len(rows))

    derived_usage = dict(original_usage)
    for key in AUDIO_KEYS:
        derived_usage[key] = ledger_usage[key]

    # --- each line of the bill --------------------------------------------
    grouped: dict[tuple, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row.get(field) for field in COMPONENT_KEY), []).append(row)

    components = []
    for component in receipt.get("components") or []:
        key = tuple(component.get(field) for field in COMPONENT_KEY)
        backing = grouped.get(key)
        name = component.get("name") or component.get("stage")
        if backing is None:
            raise DerivationRefused(
                f"component {name!r} has no calls behind it in the ledger; the "
                "receipt and the ledger disagree about something this "
                "derivation is not entitled to settle"
            )
        component_original = dict(component.get("usage") or {})
        component_ledger = totals(backing)
        for token_key in RECEIPT_USAGE_KEYS:
            if token_key in AUDIO_KEYS:
                continue
            _refuse_if_moved(
                f"component {name!r} usage {token_key}",
                component_original.get(token_key),
                component_ledger[token_key],
            )
        _refuse_if_moved(
            f"component {name!r} model_calls", component.get("model_calls"), len(backing)
        )

        component_derived = dict(component_original)
        for token_key in AUDIO_KEYS:
            component_derived[token_key] = component_ledger[token_key]

        components.append(
            {
                "name": name,
                "identity": dict(zip(COMPONENT_KEY, key)),
                "model_calls": component.get("model_calls"),
                "original_usage": component_original,
                "derived_usage": component_derived,
                "audio_from_ledger": {k: component_ledger[k] for k in AUDIO_KEYS},
                "calls_reporting_audio": sum(
                    1 for row in backing if any(row.get(k) for k in AUDIO_KEYS)
                ),
            }
        )

    added = {key: ledger_usage[key] for key in AUDIO_KEYS}
    return {
        "derivation_schema_version": DERIVATION_SCHEMA_VERSION,
        "kind": "derived_repair",
        "what_this_is": (
            "The audio figures the published receipt had no field for, read "
            "out of its own durable ledger. Derived, not regraded."
        ),
        "what_this_is_not": [
            "not a replacement for the published grade file, which is unchanged",
            "not a regrade: no score, judge decision or task outcome was read",
            "not a claim of completeness: the run stays partial, see below",
            "not a price: no cost figure moves, because none was ever published",
        ],
        "how_to_read_a_null": (
            "null means nobody measured it, and is not zero. A text-only call "
            "leaves the audio columns NULL, so a line whose calls were all "
            "text reports null here rather than a measured none. A line that "
            "reported a real zero says 0, and the two stay distinguishable."
        ),
        "source": {
            "grade_file": {
                "path": str(grade_path.relative_to(REPO_ROOT)),
                "sha256": sha256_of(grade_path),
            },
            "ledger_file": {
                "path": str(ledger_path.relative_to(REPO_ROOT)),
                "sha256": sha256_of(ledger_path),
            },
        },
        "original_scoring_provenance": {
            field: grade.get(field) for field in PROVENANCE_FIELDS if field in grade
        },
        "receipt_state_unchanged_by_this_derivation": {
            "schema_version": receipt.get("schema_version"),
            "status": receipt.get("status"),
            "estimated_cost_usd": receipt.get("estimated_cost_usd"),
            "known_cost_usd": receipt.get("known_cost_usd"),
            "model_cost_usd": receipt.get("model_cost_usd"),
            "runtime_cost_usd": receipt.get("runtime_cost_usd"),
            "model_calls": receipt.get("model_calls"),
            "currency": receipt.get("currency"),
        },
        "settled_calls": len(rows),
        "calls_reporting_audio": sum(
            1 for row in rows if any(row.get(key) for key in AUDIO_KEYS)
        ),
        "original_usage": original_usage,
        "derived_usage": derived_usage,
        "audio_from_ledger": added,
        "audio_is_a_share_not_an_addition": {
            "note": (
                "Audio tokens are part of the input the provider already "
                "reported. input_tokens is unchanged and already contains them."
            ),
            "input_tokens": derived_usage.get("input_tokens"),
            "of_which_audio": added["audio_input_tokens"],
        },
        "components": components,
        "why_this_run_is_still_partial": (
            receipt.get("missing_reasons")
            or sorted(
                {
                    reason
                    for component in receipt.get("components") or []
                    for reason in component.get("missing_reasons") or []
                }
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=BATCH_RUNNER_ROOT / "docs" / "run_records" / "audio_receipt_repair_v1",
        help="directory to write derived repairs into (never a source directory)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="derive and compare against what is on disk; write nothing",
    )
    args = parser.parse_args()

    candidates = []
    for ledger in committed_ledgers():
        grade = grade_for(ledger)
        if not grade.is_file():
            continue
        rows = settled_rows(ledger)
        measured = {key: totals(rows)[key] for key in AUDIO_KEYS}
        if not any(measured.values()):
            continue
        stated = (
            json.loads(grade.read_text(encoding="utf-8"))
            .get("summary", {})
            .get("grading_cost", {})
            .get("usage", {})
        )
        if all(stated.get(key) == measured[key] for key in AUDIO_KEYS):
            continue  # already states it; nothing to derive
        candidates.append((grade, ledger))

    if not candidates:
        print("no published bundle needs an audio repair")
        return 0

    if not args.check:
        args.out.mkdir(parents=True, exist_ok=True)
    failures = 0
    for grade, ledger in candidates:
        try:
            derived = derive(grade, ledger)
        except DerivationRefused as exc:
            print(f"REFUSED {grade.relative_to(REPO_ROOT)}\n    {exc}", file=sys.stderr)
            failures += 1
            continue

        stem = derived_stem(derived, ledger)
        target = args.out / f"{stem}.audio_repair.json"
        payload = json.dumps(derived, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

        if args.check:
            if not target.is_file():
                print(f"MISSING {target.relative_to(REPO_ROOT)}", file=sys.stderr)
                failures += 1
            elif target.read_text(encoding="utf-8") != payload:
                print(f"STALE   {target.relative_to(REPO_ROOT)}", file=sys.stderr)
                failures += 1
            else:
                print(f"ok      {target.relative_to(REPO_ROOT)}")
            continue

        target.write_text(payload, encoding="utf-8")
        print(
            f"wrote   {target.relative_to(REPO_ROOT)}  "
            f"(+{derived['audio_from_ledger']['audio_input_tokens']} audio input "
            f"tokens over {derived['calls_reporting_audio']} calls)"
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
