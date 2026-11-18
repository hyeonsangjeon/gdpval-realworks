"""Exact five-task inputs and pre-send capture for a single-task Sol owner.

This is a new input/capture schema, not a fabricated complete Foundry evidence
bundle. Requested settings never fill observed fields. No model, credentials,
deployment probe, wallet creation or old five-task witness is involved here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import weakref

import yaml

import gpt56_sol_pilot_launch as launch
from gpt56_pilot_input_bundle import PARQUET_PATH, _reference_versions
from gpt54_prepared_input_attestation import _dataset_tasks, _reference_snapshot
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_v2_grading_input import _read_bytes
from core.source_identity import source_task_projection_sha256

READY = "sol-pilot-input-ready.json"
CAPTURE = "sol-pilot-request-capture.json"
SCHEMA = "sol-pilot-exact-inputs-v1"
CAPTURE_SCHEMA = "sol-pilot-presend-capture-v1"
BOUNDARY = "verified_registered_input_and_requested_settings_not_model_consumption"
_ISSUED = weakref.WeakSet()


class InputRefused(ValueError):
    def __init__(self, code="sol_pilot_inputs_refused"):
        self.code = code
        super().__init__(code)


def _require(value, code="sol_pilot_inputs_refused"):
    if not value:
        raise InputRefused(code)


def _bytes(value):
    return launch.canonical(value)


def _digest(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _plan():
    raw = _read_bytes(launch.ROOT / launch.PROFILE, sha256=launch.PROFILE_SHA256)
    plan = yaml.safe_load(raw)
    _require(tuple(row["task_id"] for row in plan["dataset"]["tasks"]) == launch.TASKS)
    _require(plan["pilot"]["task_count"] == 5 and plan["pilot"]["repeats"] == 1)
    return plan


def _lineage(value):
    from gpt56_pilot_ledger_handoff import checked_lineage

    return checked_lineage(value)


def _read_inputs(directory, plan):
    root = _root(Path(directory))
    data = _read_bytes(_path(root, PARQUET_PATH), sha256=plan["dataset"]["parquet_sha256"])
    projections, needs_files = _dataset_tasks(data, launch.TASKS, synchronous=True)
    references = _reference_snapshot(root, _reference_versions(plan), reference_subtree=True)
    expected = {row["task_id"]: row["prompt_sha256"] for row in plan["dataset"]["tasks"]}
    for row in projections:
        _require(hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest() == expected[row["task_id"]],
                 "registered_task_prompt_mismatch")
        _require(set(row["reference_files"]) <= set(references), "task_reference_not_registered")
    roles = {PARQUET_PATH: data}
    roles.update({name: _read_bytes(_path(root, name), **description)
                  for name, description in references.items()})
    return roles, projections, needs_files, references


def _documents(plan, lineage, files, projections, needs_files, references):
    tasks = [{"task_id": row["task_id"], "prompt_sha256": hashlib.sha256(row["prompt"].encode()).hexdigest(),
              "source_projection_sha256": source_task_projection_sha256(**row),
              "reference_files": [{"path": name, **references[name]} for name in row["reference_files"]],
              "needs_files": needs_files[row["task_id"]]}
             for row in projections]
    capture = {
        "schema": CAPTURE_SCHEMA, "evidence_boundary": BOUNDARY,
        "experiment_id": plan["pilot"]["run_id"], "lineage": lineage,
        "task_ids": list(launch.TASKS), "tasks": tasks,
        "source_profile": {"path": launch.PROFILE, "sha256": launch.PROFILE_SHA256},
        "dataset": {"repo_id": plan["dataset"]["repo_id"], "revision": plan["dataset"]["revision"],
                    "parquet": {"path": PARQUET_PATH, **_digest(files[PARQUET_PATH])}},
        "requested": {"provider": "azure", "provider_id": "gdpval-foundry", "deployment": "gpt-5.6-sol",
                      "model": "gpt-5.6-sol", "reasoning_effort": "max", "context_tokens": 1_000_000,
                      "sdk_version": "0.147.0", "cli_version": "0.147.0", "logical_turns": 1},
        "developer_instructions_sha256": hashlib.sha256(plan["developer_instructions"].encode()).hexdigest(),
        "response_policy": {"served_model_missing": "stop", "served_model_mismatch": "stop",
                            "reasoning_effort_missing": "stop", "reasoning_effort_mismatch": "stop",
                            "context_not_reported": "record_and_continue", "reported_context_mismatch": "stop"},
        "observed": {"served_model": "not_observed", "reasoning_effort": "not_observed",
                     "context_tokens": "not_observed", "usage": "not_observed"},
        "full_five_task_witness": False, "model_calls": 0,
    }
    capture_bytes = _bytes(capture)
    ready = {"schema": SCHEMA, "evidence_boundary": BOUNDARY, "lineage": lineage,
             "experiment_id": plan["pilot"]["run_id"], "task_ids": list(launch.TASKS),
             "files": {name: _digest(data) for name, data in sorted(files.items())},
             "capture": {"path": CAPTURE, **_digest(capture_bytes)}}
    return capture_bytes, _bytes(ready)


@dataclass(frozen=True, eq=False, repr=False)
class VerifiedInputs:
    """Only the verifier issues an instance; documents cannot recreate it."""

    root: Path
    ready_bytes: bytes
    capture_bytes: bytes
    lineage_json: bytes

    @property
    def capture_sha256(self):
        return hashlib.sha256(self.capture_bytes).hexdigest()

    @property
    def ready_sha256(self):
        return hashlib.sha256(self.ready_bytes).hexdigest()

    @property
    def lineage(self):
        return json.loads(self.lineage_json)

    @property
    def capture(self):
        return json.loads(self.capture_bytes)

    def require_current(self):
        _require(self in _ISSUED, "unissued_input_witness")
        current = _verify(self.root, self.lineage, self.ready_sha256)
        _require(current == (self.capture_bytes, self.ready_bytes), "input_changed_after_admission")

    def task(self, task_index):
        _require(type(task_index) is int and 0 <= task_index < 5, "task_index_outside_pilot")
        self.require_current()
        plan = _plan()
        _, projections, needs_files, references = _read_inputs(self.root, plan)
        row = projections[task_index]
        return {"task_id": row["task_id"], "sector": row["sector"], "occupation": row["occupation"],
                "instruction": row["prompt"], "reference_files": list(row["reference_files"]),
                "reference_file_records": [{"path": name, **references[name]} for name in row["reference_files"]],
                "needs_files": needs_files[row["task_id"]],
                "source_projection_sha256": source_task_projection_sha256(**row)}


def _verify(directory, lineage, expected_sha256):
    _lineage(lineage)
    _require(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256),
             "independent_input_digest_required")
    root = _root(Path(directory))
    ready = _read_bytes(_path(root, READY), sha256=expected_sha256)
    plan = _plan()
    files, projections, needs_files, references = _read_inputs(root, plan)
    expected_capture, expected_ready = _documents(plan, lineage, files, projections, needs_files, references)
    _require(ready == expected_ready, "input_ready_mismatch")
    _require(_read_bytes(_path(root, CAPTURE), **_digest(expected_capture)) == expected_capture)
    members = {*files, CAPTURE, READY}
    directories = {parent.as_posix() for name in members for parent in Path(name).parents
                   if parent != Path(".")}
    actual_files, actual_directories = set(), set()
    for path in root.rglob("*"):
        name, mode = path.relative_to(root).as_posix(), path.lstat().st_mode
        if stat.S_ISDIR(mode):
            actual_directories.add(name)
        else:
            _require(stat.S_ISREG(mode), "linked_or_special_input_bundle_member")
            actual_files.add(name)
    _require(actual_files == members and actual_directories == directories,
             "unexpected_input_bundle_member")
    return expected_capture, ready


def verify_input_bundle(directory, *, lineage, expected_sha256):
    try:
        capture, ready = _verify(directory, lineage, expected_sha256)
        instance = VerifiedInputs(_root(Path(directory)), ready, capture, _bytes(_lineage(lineage)))
        _ISSUED.add(instance)
        return instance
    except Exception as error:
        raise InputRefused(error.code if isinstance(error, InputRefused) else "sol_pilot_inputs_refused") from None


def prepare_input_bundle(source_directory, destination, *, lineage):
    """Copy exact bytes and publish capture/ready last, without live assertions."""
    try:
        lineage = _lineage(lineage)
        plan = _plan()
        files, projections, needs_files, references = _read_inputs(source_directory, plan)
        capture, ready = _documents(plan, lineage, files, projections, needs_files, references)
        destination = Path(os.path.abspath(destination))
        source = _root(Path(source_directory))
        _require(not destination.is_relative_to(source) and not source.is_relative_to(destination), "input_role_overlap")
        _require(not os.path.lexists(destination), "input_destination_not_fresh")
        _root(destination.parent)
        with _held_parents(destination.parent, (destination.name,)) as check:
            check()
            os.mkdir(destination, 0o700)
            for role, data in (*sorted(files.items()), (CAPTURE, capture), (READY, ready)):
                path = _path(destination, role)
                for parent in reversed(path.parent.parents):
                    if parent.is_relative_to(destination) and not parent.exists():
                        os.mkdir(parent, 0o700)
                if not path.parent.exists():
                    os.mkdir(path.parent, 0o700)
                _write_no_clobber(path, data)
                check()
        return verify_input_bundle(destination, lineage=lineage, expected_sha256=hashlib.sha256(ready).hexdigest())
    except Exception as error:
        raise InputRefused(error.code if isinstance(error, InputRefused) else "sol_pilot_inputs_refused") from None
