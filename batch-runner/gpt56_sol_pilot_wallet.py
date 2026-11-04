"""Single real PilotUsdLedger checkpoint, not model-free synthetic wallets.

No model/grader call or invented debit is made here. A producer supplies its
owned ledger, settles or abandons actual reservations, then closes and exports
it. Each next current-run stage requires an independent predecessor digest.
This financial checkpoint is NOT a serialized live wire/session witness.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from decimal import Decimal
from functools import wraps
from pathlib import Path

import gpt56_pilot_usd_budget as usd
from gpt56_pilot_ledger_handoff import (
    TASKS, MAX_DB, MAX_JSON, _read, _write, _new_directory, _unique,
    checked_lineage,
)
from core import runner_environment as host
from gpt56_sol_pilot_launch import canonical, execution_stages

SCHEMA = "sol-pilot-single-wallet-checkpoint-v1"
MANIFEST = "wallet-checkpoint.json"
BOUNDARY = "modeled_usd_checkpoint_not_live_execution_or_billing_evidence"
FILES = frozenset((usd.DATABASE, usd.IDENTITY, MANIFEST))


class WalletRefused(ValueError):
    def __init__(self, code="sol_pilot_wallet_refused"):
        self.code = code
        super().__init__(code)


def _require(value, code="sol_pilot_wallet_refused"):
    if not value:
        raise WalletRefused(code)


def _closed(function):
    @wraps(function)
    def invoke(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except WalletRefused:
            raise
        except Exception as error:
            code = error.code if isinstance(error, usd.PilotUsdRefused) else "sol_pilot_wallet_refused"
            raise WalletRefused(code) from None
    return invoke


def _same(first, second):
    _require(canonical(first) == canonical(second))


def _digest(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _scope(lineage, capture_sha256, stage_index):
    checked_lineage(lineage)
    _require(type(capture_sha256) is str and
             re.fullmatch(r"[0-9a-f]{64}", capture_sha256) is not None)
    _require(type(stage_index) is int and 0 <= stage_index < 10)
    return execution_stages()[stage_index]


def _check_snapshot(snapshot, binding):
    _require(usd.checked_snapshot(snapshot))
    _same(snapshot["ledger_id"], binding["ledger_id"])
    _require(snapshot["pending_requests"] == 0, "pending_reservation_checkpoint_refused")


def _check_runner(receipt, lineage, stage):
    host.validate_receipt(receipt)
    _same(receipt["stage"], "inference" if stage["phase"] == "solve" else "grading")
    observed = receipt["observation"]
    for key, value in {"github_actions": "true", "github_hosted": True,
                       "eligible_for_execution": True, "runner_environment": "github-hosted",
                       "os_id": "ubuntu", "os_version_id": "24.04", "image_os": "ubuntu24",
                       "run_id": lineage["run_id"], "run_attempt": lineage["run_attempt"]}.items():
        _same(observed[key], value)


def _check_history(history, lineage, stage_index, binding):
    _require(type(history) is list and len(history) == stage_index + 1)
    previous_amount = Decimal(0)
    for index, row in enumerate(history):
        _same(sorted(row), sorted(("stage", "snapshot", "outcome", "runner")))
        _same(row["stage"], execution_stages()[index])
        _require(row["outcome"] in ("success", "failed", "stopped"))
        if index < stage_index:
            _require(row["outcome"] == "success", "failed_predecessor_refused")
        _check_runner(row["runner"], lineage, row["stage"])
        _check_snapshot(row["snapshot"], binding)
        amount = Decimal(row["snapshot"]["combined_modeled_usd"])
        _require(amount >= previous_amount, "wallet_balance_rollback_refused")
        previous_amount = amount


@_closed
def read_checkpoint(directory, *, expected_sha256, lineage, capture_sha256, next_stage):
    """Read exact files before any destination/ledger/model can be created."""
    _scope(lineage, capture_sha256, next_stage - 1)
    _require(type(expected_sha256) is str and
             re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
             "independent_predecessor_digest_required")
    root = Path(directory)
    _same(sorted(path.name for path in root.iterdir()), sorted(FILES))
    raw = _read(root / MANIFEST, MAX_JSON)
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, "predecessor_digest_mismatch")
    document = json.loads(raw, object_pairs_hook=_unique)
    _same(sorted(document), sorted(("schema", "lineage", "capture_sha256", "task_ids", "stage",
        "previous_sha256", "binding", "snapshot", "outcome", "history", "files", "evidence_boundary")))
    _same(document["schema"], SCHEMA)
    _same(document["evidence_boundary"], BOUNDARY)
    _same(document["lineage"], lineage)
    _same(document["capture_sha256"], capture_sha256)
    _same(document["task_ids"], list(TASKS))
    _same(document["stage"], execution_stages()[next_stage - 1])
    if next_stage == 1:
        _require(document["previous_sha256"] is None)
    else:
        _require(type(document["previous_sha256"]) is str and
                 re.fullmatch(r"[0-9a-f]{64}", document["previous_sha256"]) is not None)
    binding = document["binding"]
    _same(binding["capture_sha256"], capture_sha256)
    _same(binding["task_ids"], list(TASKS))
    _check_snapshot(document["snapshot"], binding)
    _check_history(document["history"], lineage, next_stage - 1, binding)
    _same(document["history"][-1]["snapshot"], document["snapshot"])
    _same(document["history"][-1]["outcome"], document["outcome"])
    _same(sorted(document["files"]), sorted((usd.DATABASE, usd.IDENTITY)))
    files = {}
    for role in (usd.DATABASE, usd.IDENTITY):
        data = _read(root / role, MAX_DB if role == usd.DATABASE else MAX_JSON)
        _same(document["files"][role], _digest(data))
        files[role] = data
    _same(json.loads(files[usd.IDENTITY], object_pairs_hook=_unique), binding)
    return document, files


@_closed
def publish_checkpoint(ledger, destination, *, lineage, capture_sha256, stage_index,
                       outcome, runner_receipt, predecessor=None, predecessor_sha256=None):
    """Close the real ledger and publish ready-last; never mint a replacement."""
    stage = _scope(lineage, capture_sha256, stage_index)
    _require(type(ledger) is usd.PilotUsdLedger and not ledger.closed)
    _require(outcome in ("success", "failed", "stopped"))
    _check_runner(runner_receipt, lineage, stage)
    destination = Path(destination)
    _require(not destination.is_relative_to(ledger.workspace) and
             not ledger.workspace.is_relative_to(destination), "wallet_export_overlap_refused")
    _require(not os.path.lexists(destination), "wallet_export_not_fresh")
    history = []
    previous = None
    if stage_index == 0:
        _require(predecessor is None and predecessor_sha256 is None)
    else:
        _require(predecessor is not None, "predecessor_required")
        previous, _ = read_checkpoint(predecessor, expected_sha256=predecessor_sha256,
            lineage=lineage, capture_sha256=capture_sha256, next_stage=stage_index)
        _require(previous["outcome"] == "success" and previous["snapshot"]["stop_reason"] is None,
                 "stopped_predecessor_refused")
        history = previous["history"]
    binding, snapshot = ledger.binding(), ledger.snapshot()
    _same(binding["capture_sha256"], capture_sha256)
    _same(binding["task_ids"], list(TASKS))
    _check_snapshot(snapshot, binding)
    if previous is not None:
        _same(binding, previous["binding"])
    _require(snapshot["stop_reason"] is None or outcome != "success", "stopped_wallet_not_success")
    history = [*history, {"stage": stage, "snapshot": snapshot,
                          "outcome": outcome, "runner": runner_receipt}]
    _check_history(history, lineage, stage_index, binding)
    ledger.close()
    _require(ledger.closed, "wallet_not_closed")
    # The ledger remains on disk if export fails. No automatic deletion/refund.
    files = {role: _read(ledger.directory / role, MAX_DB if role == usd.DATABASE else MAX_JSON)
             for role in (usd.DATABASE, usd.IDENTITY)}
    _new_directory(destination)
    for role, data in files.items():
        _write(destination / role, data)
    document = {"schema": SCHEMA, "lineage": lineage, "capture_sha256": capture_sha256,
        "task_ids": list(TASKS), "stage": stage, "previous_sha256": predecessor_sha256,
        "binding": binding, "snapshot": snapshot, "outcome": outcome, "history": history,
        "files": {role: _digest(data) for role, data in files.items()}, "evidence_boundary": BOUNDARY}
    raw = canonical(document)
    _require(len(raw) <= MAX_JSON)
    _write(destination / MANIFEST, raw)
    fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return document, hashlib.sha256(raw).hexdigest()


@_closed
def restore_checkpoint(destination, predecessor, *, expected_sha256, lineage,
                       capture_sha256, stage_index):
    """Reopen exactly the predecessor's wallet, rejecting stopped state first."""
    _scope(lineage, capture_sha256, stage_index)
    _require(stage_index > 0, "first_stage_restore_refused")
    document, files = read_checkpoint(predecessor, expected_sha256=expected_sha256,
        lineage=lineage, capture_sha256=capture_sha256, next_stage=stage_index)
    snapshot = document["snapshot"]
    _require(document["outcome"] == "success" and snapshot["stop_reason"] is None and
             Decimal(snapshot["remaining_modeled_usd"]) > 0, "stopped_wallet_cannot_start_next_stage")
    destination, predecessor = Path(destination), Path(predecessor)
    _require(not destination.is_relative_to(predecessor) and
             not predecessor.is_relative_to(destination), "wallet_restore_overlap_refused")
    _new_directory(destination)
    _new_directory(destination / usd.DIRECTORY)
    for role, data in files.items():
        _write(destination / usd.DIRECTORY / role, data)
    ledger = usd.PilotUsdLedger(destination, capture_sha256=capture_sha256,
                                task_ids=list(TASKS), create=False)
    try:
        _same(ledger.binding(), document["binding"])
        _same(ledger.snapshot(), snapshot)
    except BaseException:
        ledger.close()
        raise
    return ledger
