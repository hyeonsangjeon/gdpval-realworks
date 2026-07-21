#!/usr/bin/env python3
"""Validate the hermetic deliverable-selector contract fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    ROOT
    / "batch-runner"
    / "tests"
    / "fixtures"
    / "deliverable_selector_contract_v1.json"
)
SCHEMA_VERSION = "deliverable-selector-contract-v1"
SOURCE_FIELDS = {
    "repository",
    "revision",
    "parquet_path",
    "parquet_sha256",
    "row_count",
    "projection_policy",
    "source_content_included",
}
TASK_FIELDS = {
    "task_id",
    "source_selector_input_sha256",
    "instruction",
    "rubric_items",
}
RUBRIC_FIELDS = {"criterion", "score"}
ALLOWED_SYNTHETIC_INSTRUCTIONS = {
    "",
    "Provide two separate deliverable files: one Word document and one PDF.",
    "Provide one Excel workbook and one Word document as separate files.",
    "Deliver a final MP4 video.",
    "The final deliverable consists of a single PDF report with supporting images and workbook.",
    "Provide one PDF and one spreadsheet as separate files.",
    "Provide two distinct .pptx files and a supporting image.",
    "Provide three separate PDF files.",
    "Deliver a Python notebook (.ipynb).",
    "Deliver a final MP4 video and a final PDF.",
    "Deliver a final .pdf file.",
    "Deliver a final audio file.",
}
ALLOWED_ROUTING_CRITERIA = {
    "Provides two distinct .pptx files: one presentation for Session 13 and one for Session 14.",
    "Session 14 deck includes a title slide indicating it is Session 14 (wording may vary).",
    "Every assigned table ID in the spreadsheet also appears with the same ID labeled on the corresponding updated layout PDF",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
SHORT_ID_RE = re.compile(r"^[0-9a-f]{8}$")


class FixtureValidationError(ValueError):
    """Raised when the selector fixture contract is invalid."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def fixture_sha256(document: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in document.items() if key != "sha256"}
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def load_and_validate_fixture(path: str | Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    fixture_path = Path(path)
    try:
        document = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureValidationError("fixture_unreadable") from exc
    validate_fixture(document)
    return document


def validate_fixture(document: Any) -> None:
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "source",
        "tasks",
        "sha256",
    }:
        raise FixtureValidationError("fixture_fields_invalid")
    if document["schema_version"] != SCHEMA_VERSION:
        raise FixtureValidationError("fixture_schema_invalid")
    if document["sha256"] != fixture_sha256(document):
        raise FixtureValidationError("fixture_hash_mismatch")

    source = document["source"]
    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        raise FixtureValidationError("fixture_source_fields_invalid")
    if (
        source["repository"] != "openai/gdpval"
        or FULL_SHA_RE.fullmatch(str(source["revision"])) is None
        or source["parquet_path"] != "data/train-00000-of-00001.parquet"
        or SHA256_RE.fullmatch(str(source["parquet_sha256"])) is None
        or source["row_count"] != 220
        or source["projection_policy"] != "synthetic-minimal-selector-signals-v1"
        or source["source_content_included"] is not False
    ):
        raise FixtureValidationError("fixture_source_identity_invalid")

    tasks = document["tasks"]
    if not isinstance(tasks, dict) or len(tasks) != 28:
        raise FixtureValidationError("fixture_task_count_invalid")
    full_ids: set[str] = set()
    for short_id, task in tasks.items():
        if SHORT_ID_RE.fullmatch(str(short_id)) is None:
            raise FixtureValidationError("fixture_short_id_invalid")
        if not isinstance(task, dict) or set(task) != TASK_FIELDS:
            raise FixtureValidationError("fixture_task_fields_invalid")
        task_id = task["task_id"]
        if (
            not isinstance(task_id, str)
            or UUID_RE.fullmatch(task_id) is None
            or not task_id.startswith(f"{short_id}-")
            or task_id in full_ids
        ):
            raise FixtureValidationError("fixture_task_identity_invalid")
        full_ids.add(task_id)
        if SHA256_RE.fullmatch(str(task["source_selector_input_sha256"])) is None:
            raise FixtureValidationError("fixture_source_selector_hash_invalid")
        instruction = task["instruction"]
        if instruction not in ALLOWED_SYNTHETIC_INSTRUCTIONS:
            raise FixtureValidationError("fixture_instruction_invalid")
        rubric_items = task["rubric_items"]
        if not isinstance(rubric_items, list) or len(rubric_items) > 8:
            raise FixtureValidationError("fixture_rubrics_invalid")
        for item in rubric_items:
            if not isinstance(item, dict) or set(item) != RUBRIC_FIELDS:
                raise FixtureValidationError("fixture_rubric_fields_invalid")
            criterion = item["criterion"]
            score = item["score"]
            if (
                not isinstance(criterion, str)
                or criterion not in ALLOWED_ROUTING_CRITERIA
                or isinstance(score, bool)
                or not isinstance(score, (int, float))
            ):
                raise FixtureValidationError("fixture_rubric_invalid")


def verify_source_snapshot(
    document: Mapping[str, Any],
    parquet_path: str | Path,
    *,
    source_revision: str,
) -> None:
    """Verify public source identity without importing pandas during test collection."""
    validate_fixture(document)
    source = document["source"]
    if source_revision != source["revision"]:
        raise FixtureValidationError("source_revision_mismatch")
    path = Path(parquet_path)
    if _sha256_file(path) != source["parquet_sha256"]:
        raise FixtureValidationError("source_parquet_hash_mismatch")
    try:
        import pandas as pd
    except ImportError as exc:
        raise FixtureValidationError("source_reader_unavailable") from exc
    frame = pd.read_parquet(path, columns=["task_id", "prompt", "rubric_json"])
    if len(frame) != source["row_count"]:
        raise FixtureValidationError("source_row_count_mismatch")
    source_rows = {row["task_id"]: row for row in frame.to_dict("records")}
    fixture_ids = {task["task_id"] for task in document["tasks"].values()}
    if not fixture_ids <= set(source_rows):
        raise FixtureValidationError("source_task_set_mismatch")
    for task in document["tasks"].values():
        row = source_rows[task["task_id"]]
        if _source_selector_input_sha256(
            row.get("prompt"), row.get("rubric_json")
        ) != task["source_selector_input_sha256"]:
            raise FixtureValidationError("source_selector_input_mismatch")


def _source_selector_input_sha256(prompt: Any, rubric: Any) -> str:
    if isinstance(rubric, str):
        try:
            rubric = json.loads(rubric)
        except json.JSONDecodeError as exc:
            raise FixtureValidationError("source_rubric_invalid") from exc
    if not isinstance(prompt, str) or not isinstance(rubric, list):
        raise FixtureValidationError("source_selector_input_invalid")
    criteria = []
    for item in rubric:
        if not isinstance(item, Mapping) or not isinstance(item.get("criterion"), str):
            raise FixtureValidationError("source_rubric_invalid")
        criteria.append(item["criterion"])
    return hashlib.sha256(canonical_json({
        "prompt": prompt,
        "rubric_criteria": criteria,
    })).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise FixtureValidationError("source_parquet_unreadable") from exc
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--source-parquet")
    parser.add_argument("--source-revision")
    args = parser.parse_args()

    document = load_and_validate_fixture(args.fixture)
    if bool(args.source_parquet) != bool(args.source_revision):
        parser.error("--source-parquet and --source-revision must be provided together")
    if args.source_parquet:
        verify_source_snapshot(
            document,
            args.source_parquet,
            source_revision=args.source_revision,
        )
    print(json.dumps({
        "fixture": "valid",
        "schema_version": document["schema_version"],
        "task_count": len(document["tasks"]),
        "source_verified": bool(args.source_parquet),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
