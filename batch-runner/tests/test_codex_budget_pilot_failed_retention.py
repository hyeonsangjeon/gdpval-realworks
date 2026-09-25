"""Future-code withholding, not reconstruction or recovery of the admitted A1.

Synthetic child outputs use real JSON/fingerprints, checkpoints, projections,
publisher/CAS and terminal validation. Existing fake child/HF boundaries forbid
native execution, credentials, network, model and grading calls.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retention
from core.result_fingerprint import inference_result_fingerprint
from step2_run_inference import _public_persisted_results
from .test_codex_budget_pilot_retention import (
    SOURCE, boundary, case, cell_root, finalized, offline, read_plan, read_state,
    scenario, select_fresh,
)  # noqa: F401 -- reuse the existing offline fixtures, not their test family.

CANARY = "SYNTHETIC_WITHHELD_PRIVATE_PAYLOAD_DO_NOT_PUBLISH"


def _serialize(payload):
    # Step2's existing public-row projection and strict final JSON encoding.
    # The field variants below are synthetic, not A1's unavailable raw result.
    payload["results"] = _public_persisted_results(payload["results"])
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str, allow_nan=False).encode()


def _producer(s, monkeypatch, *, fields="row", stopped=False, success=False, partial=True):
    s.transport.outcomes[s.selected] = "success" if stopped or success else "error"
    s.transport.stop = "timeout" if stopped else None
    s.transport.partial = partial
    original = s.transport._process

    def process(command, **options):
        result = original(command, **options)
        if command[1] == "step2_run_inference.py":
            path = options["cwd"] / "workspace" / Path(pilot.RESULT).name
            payload = json.loads(path.read_bytes())
            row = payload["results"][0]
            if fields == "top":
                payload["synthetic_unpublishable"] = CANARY
            elif fields == "recursive":
                row["content"] = {"token": CANARY}
            elif fields == "row":
                row["failure_evidence"] = {"path": "synthetic-private-evidence", "value": CANARY}
            else:
                assert fields is None
            path.write_bytes(_serialize(payload))
        return result

    monkeypatch.setattr(s.transport, "_process", process)


def _snapshot(s, *, withheld=False):
    cell = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    return output.prepare(root=s.root, campaign=ci.CAMPAIGN, cell_id=s.selected,
                          source_sha=SOURCE, config_sha=cell["config_sha256"],
                          _failure_metadata=withheld)


def _local_bytes(s):
    cell = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    state = read_state(s, s.selected)
    paths = [s.root / cell["roles"][role] for role in ("result", "ledger", "checkpoint")]
    paths += [s.envelope, cell_root(s) / retention.ADMISSION_RECEIPT]
    paths += [s.root / cell["roles"]["checkout"] / "batch-runner/workspace/upload" / row["path"]
              for row in state["artifacts"]["deliverable_files"]]
    return {path: path.read_bytes() for path in paths}


@pytest.mark.parametrize("fields", ["top", "recursive", "row"])
@pytest.mark.parametrize("stopped", [False, True])
def test_failed_retention_withholds_only_payload_and_preserves_recorded_facts(case, capsys, monkeypatch, fields, stopped):
    s = case
    _producer(s, monkeypatch, fields=fields, stopped=stopped)
    finalized(s, capsys, monkeypatch, expected=1)
    before, calls = _local_bytes(s), list(s.api.calls)
    completed = pilot._load(s.envelope)
    with pytest.raises(output.OutputPublicationRefused, match="^unsafe_result_fields$"):
        _snapshot(s)  # Standalone preparation has no withholding opt-in.
    assert s.api.calls == calls
    snapshot = _snapshot(s, withheld=True)
    manifest = snapshot.manifest
    assert s.api.calls == calls and snapshot.files == {}
    assert manifest["files"] == []
    assert manifest["missing"] == ["bound_inference_result", "validated_deliverables", "bound_ledger_export"]
    assert manifest["withheld"] == {"reason": "unsafe_result_fields", "artifacts": completed["artifacts"]}
    assert manifest["status"] == completed["status"] == ("stopped" if stopped else "failed")
    assert manifest["reason"] == completed["reason"] == (
        "child_timeout_partial_accounting" if stopped else "child_nonzero_exit")
    assert manifest["timeout"] is stopped and manifest["cleanup_confirmed"] is True
    assert manifest["receipt"] == completed["receipt"]
    assert manifest["accounting"] == manifest["receipt"]["status"] == "partial"
    assert manifest["receipt"]["known_cost_usd"] == 0.01
    assert manifest["receipt"]["estimated_cost_usd"] is None
    assert manifest["receipt"]["usage"]["input_tokens"] == 12
    assert manifest["receipt"]["usage"]["output_tokens"] == 3
    assert manifest["receipt"]["usage"]["reasoning_tokens"] == 2
    assert completed["invoice_complete"] is False and completed["http_request_count"] is None
    assert manifest["grade_ready"] is manifest["grading_launched"] is False
    assert completed["child_invocations"] == 1 and completed["other_cells_not_run"] == 29
    # Standalone publication also keeps its no-missing-payload gate.
    with pytest.raises(output.OutputPublicationRefused, match="^bound_inference_result_required$"):
        output.publish(snapshot, repo=s.api.repo, expected_parent=s.api.head, _test_api=s.api)
    assert s.api.calls == calls

    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0
    cell = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    claim_path, terminal_path, prefix = retention._paths(cell)
    terminal = json.loads(s.api.trees[s.api.head][terminal_path])
    receipt = retention._read(cell_root(s) / output.RECEIPT)
    assert receipt["outcome"] == "acknowledged"
    assert terminal["output_commit"] == receipt["returned_commit"]
    assert s.api.parents[terminal["output_commit"]] == terminal["claim_commit"]
    assert s.api.parents[s.api.head] == terminal["output_commit"]
    assert terminal["completion"] == completed
    assert terminal["publication_acknowledged"] is True
    assert set(s.api.trees[s.api.head]) == {claim_path, terminal_path, prefix + "/" + output.MANIFEST}
    published = s.api.trees[terminal["output_commit"]][prefix + "/" + output.MANIFEST]
    assert json.loads(published) == {**manifest, "inference_branch": retention.BRANCH}
    assert terminal["manifest_identity"] == pilot._identity(published)
    retention._manifest(json.loads(published), completed, cell)
    assert all(CANARY.encode() not in data for tree in s.api.trees.values() for data in tree.values())
    assert _local_bytes(s) == before
    assert s.api.events == ["admission", "child", "child", "output", "terminal"]


def test_failed_retention_safe_success_is_byte_identical(case, capsys, monkeypatch):
    s = case
    _producer(s, monkeypatch, fields=None, success=True)
    finalized(s, capsys, monkeypatch)
    before = _local_bytes(s)
    strict, opted_in = _snapshot(s), _snapshot(s, withheld=True)
    assert strict.manifest == opted_in.manifest and strict.files == opted_in.files
    assert "withheld" not in strict.manifest and strict.manifest["status"] == "succeeded"
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0
    cell = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    terminal = retention._read(cell_root(s) / retention.TERMINAL_RECEIPT)
    prefix = retention._paths(cell)[2]
    assert all(s.api.trees[terminal["output_commit"]][prefix + "/" + name] == data
               for name, data in strict.files.items())
    assert _local_bytes(s) == before


@pytest.mark.parametrize("fields", ["top", "recursive", "row"])
def test_failed_retention_unsafe_success_still_refuses(case, capsys, monkeypatch, fields):
    s = case
    _producer(s, monkeypatch, fields=fields, success=True)
    finalized(s, capsys, monkeypatch)
    before, calls = _local_bytes(s), list(s.api.calls)
    with pytest.raises(output.OutputPublicationRefused, match="^unsafe_result_fields$"):
        _snapshot(s, withheld=True)
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
    assert s.api.calls == calls and s.api.commits == ["admission"]
    assert not (cell_root(s) / retention.TERMINAL_RESERVED).exists()
    assert not (cell_root(s) / output.RESERVATION).exists()
    assert _local_bytes(s) == before


@pytest.mark.parametrize("change", ["identity", "source", "result_bytes", "result_role", "path",
                                    "deliverable", "ledger", "cleanup", "accounting", "structure", "total_bytes"])
def test_failed_retention_privacy_refusal_cannot_hide_invalid_evidence(case, capsys, monkeypatch, change):
    s = case
    _producer(s, monkeypatch)
    finalized(s, capsys, monkeypatch, expected=1)
    cell, state = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL], read_state(s, s.selected)
    path = s.root / cell["roles"]["result"]
    if change in {"identity", "source", "path", "structure"}:
        payload = json.loads(path.read_bytes())
        if change == "identity":
            payload["run_id"] = "synthetic-foreign-run"
        elif change == "source":
            payload["source"] = "synthetic-foreign/dataset"
        elif change == "path":
            payload["results"][0]["deliverable_file_records"][0]["path"] = "../original.parquet"
        else:
            nested = CANARY
            for _ in range(25):
                nested = [nested]
            # The forbidden key must not hide a later, too-deep branch.
            payload["results"][0]["content"] = {"token": CANARY, "nested": nested}
        data = _serialize(payload)
        path.write_bytes(data)
        state["result"].update(pilot._identity(data))
        state["artifacts"]["result_fingerprint"] = payload["result_fingerprint"]
        pilot._save(s.root / cell["roles"]["checkpoint"], state)
    elif change == "result_bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "result_role":
        state["result"]["path"] = "../foreign-result.json"
        pilot._save(s.root / cell["roles"]["checkpoint"], state)
    elif change == "deliverable":
        name = state["artifacts"]["deliverable_files"][0]["path"]
        (s.root / cell["roles"]["checkout"] / "batch-runner/workspace/upload" / name).write_bytes(b"changed")
    elif change == "ledger":
        (s.root / cell["roles"]["ledger"]).write_bytes(b"changed")
    elif change == "cleanup":
        owner = pilot._load(s.root / "owned-child.json")
        owner["phase"] = "cleanup_unresolved"
        pilot._save(s.root / "owned-child.json", owner)
    elif change == "total_bytes":
        # The valid bound ledger must still count toward the pre-withholding
        # payload ceiling, even though no payload will be uploaded.
        limit = state["result"]["size"] + sum(row["size"] for row in state["artifacts"]["deliverable_files"])
        monkeypatch.setattr(output, "MAX_TOTAL_BYTES", limit)
    else:
        state["receipt"]["known_cost_usd"] = state["receipt"]["model_cost_usd"] = 0.02
        pilot._save(s.root / cell["roles"]["checkpoint"], state)
    calls, raw = list(s.api.calls), path.read_bytes()
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
    assert s.api.calls == calls and s.api.commits == ["admission"]
    assert not (cell_root(s) / retention.TERMINAL_RESERVED).exists()
    assert not (cell_root(s) / output.RESERVATION).exists()
    assert path.read_bytes() == raw


def test_failed_retention_withheld_manifest_is_closed_and_identity_bound(case, capsys, monkeypatch):
    s = case
    _producer(s, monkeypatch)
    finalized(s, capsys, monkeypatch, expected=1)
    manifest = _snapshot(s, withheld=True).manifest
    completed, cell = pilot._load(s.envelope), read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    retention._manifest(manifest, completed, cell)
    for change in ("reason", "extra", "identity", "result_missing", "success", "cleanup", "files",
                   "missing", "too_many", "size", "total_size"):
        value, projected = copy.deepcopy(manifest), copy.deepcopy(completed)
        evidence = value["withheld"]
        if change == "reason":
            evidence["reason"] = "payload_identity_mismatch"
        elif change == "extra":
            evidence["detail"] = CANARY
        elif change == "identity":
            evidence["artifacts"]["result"]["sha256"] = "f" * 64
        elif change == "result_missing":
            evidence["artifacts"]["result"] = projected["artifacts"]["result"] = None
        elif change == "success":
            value["status"] = projected["status"] = "succeeded"
        elif change == "cleanup":
            value["cleanup_confirmed"] = projected["cleanup_confirmed"] = False
        elif change == "files":
            value["files"] = [{"role": "inference_result", "path": "step2_inference_results.json",
                               **projected["artifacts"]["result"]}]
        elif change == "missing":
            value["missing"] = []
        elif change == "too_many":
            evidence["artifacts"]["deliverables"] *= output.MAX_FILES + 1
            projected["artifacts"] = copy.deepcopy(evidence["artifacts"])
        elif change == "size":
            evidence["artifacts"]["result"]["size"] = output.MAX_RECORD_BYTES + 1
            projected["artifacts"] = copy.deepcopy(evidence["artifacts"])
        else:
            evidence["artifacts"]["deliverables"] = [{"size": output.MAX_FILE_BYTES, "sha256": "e" * 64}] * 3
            projected["artifacts"] = copy.deepcopy(evidence["artifacts"])
        with pytest.raises(ValueError):
            retention._manifest(value, projected, cell)
    assert s.api.commits == ["admission"]


def test_failed_retention_absent_result_keeps_existing_missing_contract(case, capsys, monkeypatch):
    s = case
    s.transport.outcomes[s.selected] = "missing_result"
    finalized(s, capsys, monkeypatch, expected=1)
    snapshot = _snapshot(s, withheld=True)
    assert snapshot.files == {} and "withheld" not in snapshot.manifest
    assert snapshot.manifest["missing"] == [
        "bound_inference_result", "validated_deliverables", "bound_ledger_export", "usage"]
    assert snapshot.manifest["status"] == "failed" and snapshot.manifest["accounting"] == "missing"
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0


def test_failed_retention_withheld_missing_accounting_stays_missing(case, capsys, monkeypatch):
    s = case
    _producer(s, monkeypatch, partial=False)
    finalized(s, capsys, monkeypatch, expected=1)
    before = _local_bytes(s)
    snapshot = _snapshot(s, withheld=True)
    assert snapshot.files == {} and snapshot.manifest["files"] == []
    assert snapshot.manifest["withheld"]["artifacts"]["result"] is not None
    assert snapshot.manifest["receipt"] is None and snapshot.manifest["accounting"] == "missing"
    assert snapshot.manifest["missing"] == [
        "bound_inference_result", "validated_deliverables", "bound_ledger_export", "usage"]
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0
    assert _local_bytes(s) == before


def test_failed_retention_lost_publication_cannot_replay_or_advance(case, capsys, monkeypatch):
    s = case
    _producer(s, monkeypatch)
    finalized(s, capsys, monkeypatch, expected=1)
    before = _local_bytes(s)
    s.api.lost = "output"
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
    receipt_path = cell_root(s) / retention.TERMINAL_RECEIPT
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    assert receipt["outcome"] == "unresolved" and receipt["output_commit"] is receipt["terminal_commit"] is None
    assert retention._read(cell_root(s) / output.RECEIPT)["outcome"] == "unresolved"
    assert (cell_root(s) / output.RESERVATION).exists()
    assert (cell_root(s) / retention.TERMINAL_RESERVED).exists()
    assert not any(name.endswith("/terminal.json") for name in s.api.trees[s.api.head])
    assert s.api.commits == ["admission", "output"] and _local_bytes(s) == before
    s.api.lost = None
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
    assert receipt_path.read_bytes() == receipt_bytes and s.api.commits == ["admission", "output"]
    select_fresh(s, monkeypatch)
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
    assert s.api.commits == ["admission", "output"] and not s.transport.calls
    assert not (cell_root(s) / retention.SERVER_OBSERVATION).exists()
    assert receipt_path.read_bytes() == receipt_bytes
