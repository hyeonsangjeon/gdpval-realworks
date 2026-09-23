"""Local reader CLI only: real compiler/validator, explicitly synthetic evidence."""

from __future__ import annotations

import copy
from decimal import Decimal
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.request

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_results as results
from core.cost_receipts import CostReceipt

SOURCE = "0f0911b435d7f704db8e2f2131a00ade310d5c1f"
INPUTS = pilot._digest({"synthetic_verified_inputs": True})


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("reader crossed an original-input / execution / network boundary")

    for target, names in (
        (pilot, ("dispatch", "_source_snapshot", "_step0_bytes")),
        (pilot.LocalTransport, ("require_source", "inputs", "checkout", "child", "require_execution")),
        (ci, ("compile_ci_cell", "_require_ci_context")),
        (subprocess, ("Popen", "run")), (socket, ("create_connection",)),
        (socket.socket, ("connect", "connect_ex")), (urllib.request, ("urlopen",)),
        (time, ("sleep",)),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)


@pytest.fixture
def records(tmp_path):
    # The compiler really checks registered cohort/config/source pins. Only the
    # observation/host-instance/input fingerprints below are synthetic, never
    # real data, native execution, credentials or a fabricated live receipt.
    plan, _, _ = pilot.compile_pilot(ci.CAMPAIGN, SOURCE)
    registration = hashlib.sha256(pilot._read_bytes(ci.REGISTRATION)).hexdigest()
    written = []

    def make(index=0, *, verified=INPUTS, status="succeeded", receipt=None,
             cleanup=True, reason=None, execute=True, mutate=None):
        per_job = copy.deepcopy(plan)
        cell = per_job["cells"][index]
        per_job["ci"] = {
            "registration_sha256": registration, "selected_cell_id": cell["cell_id"],
            "host": {"policy": ci.HOST_POLICY, "instance_sha256": pilot._digest({"synthetic_job": index})},
        }
        state = pilot._cell_state(per_job, cell)
        state.update(status=status, phase="pending" if status == "pending" else "finished",
                     reason=reason, child_invocations=1 if execute else 0,
                     exit_code=0 if status == "succeeded" else 1 if status == "failed" else None,
                     receipt=receipt, result=None if not execute else {
                         "sha256": "b" * 64, "size": 11, "path": "/private/synthetic/result-never-published"},
                     artifacts={} if not execute else {"deliverable_files": [
                         {"sha256": "c" * 64, "size": 3, "path": "secret-file-name.txt"}]})
        payload = ci.completion(per_job, cell, execute=execute, state=state,
                                inputs=None if verified is None else {"files_sha256": verified},
                                cleanup=cleanup)
        ci.validate_completion(payload)
        if mutate:
            mutate(payload)  # Explicit malformed-envelope boundary, after genuine projection.
        path = tmp_path / f"private-synthetic-envelope-{len(written)}.json"
        pilot._save(path, payload)
        written.append(path)
        return path, payload

    return plan, make


def invoke(tmp_path, capsys, paths=(), *, expected=INPUTS, source=SOURCE, out=None, extra=()):
    out = out or tmp_path / "result.json"
    argv = ["--reviewed-source-sha", source, "--out", str(out)]
    for path in paths:
        argv += ["--envelope", str(path)]
    if expected is not None:
        argv += ["--expected-verified-inputs-sha256", expected]
    code = results.main([*argv, *extra])
    capture = capsys.readouterr()
    if code == 0:
        assert not capture.err
        assert capture.out.encode() == out.read_bytes()
        assert len(out.read_bytes()) <= results.MAX_RESULT_BYTES
        assert out.stat().st_mode & 0o777 == 0o600 and out.stat().st_nlink == 1
        result = json.loads(capture.out)
        assert result["denominator"] == len(result["cells"]) == 30
        assert sum(result["status_counts"].values()) == 30
        assert result["remote_execution_deduplicated"] is False
        assert result["grading_launched"] is False and result["invoice_complete"] is False
        assert result["http_request_count"] is None
        assert result["usage_and_cost"] == "per_cell_only_no_totals"
        assert result["proof_limits"]["plan_and_runner_instance_binding"] == "unavailable_in_completion_v1"
        for private in (str(tmp_path), "private-synthetic", "secret-file-name", "CODEX_HOME", "bearer"):
            assert private not in capture.out
        return result
    assert code == 2 and not capture.out
    assert "Pilot results refused:" in capture.err
    assert str(tmp_path) not in capture.err and "secret" not in capture.err
    return capture.err


def test_results_empty_cli_retains_all_registered_rows(tmp_path, capsys, records):
    plan, _ = records
    result = invoke(tmp_path, capsys, expected=None)
    assert result["observed_envelopes"] == 0
    assert result["status_counts"] == {"NOT_OBSERVED": 30}
    assert result["expected_verified_inputs_sha256"] is None
    assert result["order_sha256"] == pilot._digest(plan["order"])
    assert [row["cell_id"] for row in result["cells"]] == plan["order"]
    for cell, row in zip(plan["cells"], result["cells"]):
        assert row["config_sha256"] == cell["config_sha256"]
        assert row["completion_payload_sha256"] is None
        assert all(row[key] is None for key in results.OBSERVED_FIELDS if key != "status")


def test_results_missing_cli_does_not_sum_local_unrun_declarations(tmp_path, capsys, records):
    plan, make = records
    later, _ = make(8, status="failed", reason="child_nonzero_exit")
    earlier, _ = make(0, verified=None, status="pending", cleanup=None, execute=False)
    result = invoke(tmp_path, capsys, [later, earlier])
    assert result["observed_envelopes"] == 2
    assert result["status_counts"] == {"pending": 1, "failed": 1, "NOT_OBSERVED": 28}
    assert [row["cell_id"] for row in result["cells"]] == plan["order"]
    assert result["other_cells_not_run"] == "local_declaration_not_summed"
    assert result["cells"][0]["verified_inputs_sha256"] is None  # Do not fill from expected hash.
    assert result["cells"][8]["exit_code"] == 1
    assert result["cells"][8]["receipt"] is None


def test_results_full_cli_uses_compiler_order_with_distinct_ci_instances(tmp_path, capsys, records):
    plan, make = records
    pairs = [make(index) for index in range(len(plan["cells"]))]
    result = invoke(tmp_path, capsys, [path for path, _ in reversed(pairs)])
    assert result["observed_envelopes"] == 30 and result["status_counts"] == {"succeeded": 30}
    assert [row["cell_id"] for row in result["cells"]] == plan["order"]
    assert len({row["plan_sha256"] for row in result["cells"]}) == 30
    for row, (_, envelope) in zip(result["cells"], pairs):
        assert row["completion_payload_sha256"] == pilot._digest(envelope)
        assert row["receipt"] is None  # Success is not cost completeness or graded quality.
        assert row["cleanup_confirmed"] is True


def test_results_failed_partial_missing_accounting_and_no_double_counting(tmp_path, capsys, records):
    _, make = records
    receipt = CostReceipt(
        status="partial", known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        model_calls=1, usage={"input_tokens": 10982, "output_tokens": 29, "reasoning_tokens": 22},
        missing_reasons=("synthetic_missing_cost",),
    ).as_dict()
    failed, original = make(0, status="failed", reason="child_nonzero_exit", receipt=receipt)
    unresolved, _ = make(1, status="stopped", cleanup=False, reason="child_timeout_partial_accounting")
    stopped, _ = make(2, status="stopped", receipt=CostReceipt(status="not_run").as_dict())
    zero, _ = make(3, receipt=CostReceipt.free().as_dict())
    result = invoke(tmp_path, capsys, [unresolved, failed, stopped, zero])
    first, second, third, fourth = result["cells"][:4]
    assert first["receipt"] == original["receipt"]
    assert first["receipt"]["status"] == "partial"
    assert first["receipt"]["known_cost_usd"] == 0.01 and first["receipt"]["estimated_cost_usd"] is None
    assert first["receipt"]["usage"] == {
        "input_tokens": 10982, "output_tokens": 29, "reasoning_tokens": 22,
        "cached_input_tokens": None, "audio_input_tokens": None, "audio_output_tokens": None,
    }
    assert second["status"] == "unresolved" and second["cleanup_confirmed"] is False
    assert second["timeout"] is True and second["exit_code"] is None and second["receipt"] is None
    assert third["status"] == "stopped" and third["receipt"]["status"] == "not_run"
    assert third["receipt"]["usage"] is None and third["receipt"]["known_cost_usd"] is None
    assert fourth["receipt"]["estimated_cost_usd"] == 0
    assert all(row["receipt"] is None for row in result["cells"][4:])
    assert "thread_total" not in json.dumps(result) and "most_recent_request" not in json.dumps(result)


@pytest.mark.parametrize("conflicting", [False, True])
def test_results_duplicate_cell_refuses_even_identical_input(tmp_path, capsys, records, conflicting):
    _, make = records
    first, _ = make()
    second = make(status="failed", reason="child_nonzero_exit")[0] if conflicting else first
    assert "duplicate_cell" in invoke(tmp_path, capsys, [first, second])
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("field,value", [
    ("campaign_id", "foreign_campaign"), ("source_sha", "a" * 40),
    ("config_sha256", "a" * 64), ("declared_inputs_sha256", "a" * 64),
    ("verified_inputs_sha256", "a" * 64), ("order_sha256", "a" * 64),
    ("registration_sha256", "a" * 64), ("host_policy_sha256", "a" * 64),
    ("cell_id", "f" * 36 + "_A_r1"),
])
def test_results_foreign_or_mismatched_binding_refuses(tmp_path, capsys, records, field, value):
    _, make = records
    path, _ = make(mutate=lambda payload: payload.update({field: value}))
    invoke(tmp_path, capsys, [path])
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("source,expected,error", [
    (SOURCE, None, "external_verified_inputs_expectation_required"),
    (SOURCE, "not-a-hash", "invalid_verified_inputs_expectation"),
    ("not-a-sha", INPUTS, "explicit_reviewed_source_sha_required"),
])
def test_results_explicit_external_expectations(tmp_path, capsys, records, source, expected, error):
    _, make = records
    path, _ = make()
    assert error in invoke(tmp_path, capsys, [path], expected=expected, source=source)
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("corruption", ["checksum", "duplicate_key", "truncated", "private_field", "usage_totals", "nonfinite"])
def test_results_malformed_envelopes_refuse_without_private_output(tmp_path, capsys, records, corruption):
    _, make = records
    path, payload = make()
    if corruption == "checksum":
        document = {"payload": payload, "sha256": "0" * 64}
        path.write_text(json.dumps(document))
    elif corruption == "duplicate_key":
        path.write_text('{"payload":{},"payload":{},"sha256":"' + "0" * 64 + '"}')
    elif corruption == "truncated":
        path.write_text('{"payload":')
    elif corruption == "private_field":
        payload["CODEX_HOME"] = "/private/secret-auth"
        pilot._save(path, payload)
    elif corruption == "usage_totals":
        payload["receipt"] = {"sha256": "b" * 64, "status": "partial", "estimated_cost_usd": None,
                              "known_cost_usd": None, "usage": {"thread_total": 29, "most_recent_request": 29}}
        pilot._save(path, payload)
    else:
        path.write_text('{"payload":NaN,"sha256":"' + "0" * 64 + '"}')
    invoke(tmp_path, capsys, [path])
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("kind", ["oversized", "symlink", "hardlink", "missing", "too_many"])
def test_results_explicit_local_bounded_files_only(tmp_path, capsys, records, kind):
    _, make = records
    path, _ = make()
    paths = [path]
    if kind == "oversized":
        path.write_bytes(b" " * (results.MAX_ENVELOPE_BYTES + 1))
    elif kind == "symlink":
        paths = [tmp_path / "secret-linked-input.json"]
        paths[0].symlink_to(path)
    elif kind == "hardlink":
        os.link(path, tmp_path / "other-link.json")
    elif kind == "missing":
        paths = [tmp_path / "secret-missing-input.json"]
    elif kind == "too_many":
        paths *= 31
    invoke(tmp_path, capsys, paths)
    assert not (tmp_path / "result.json").exists()


def test_results_atomic_no_clobber_rejects_existing_partial_or_ready_file(tmp_path, capsys, records):
    _, make = records
    path, _ = make()
    out = tmp_path / "partial-result.json"
    out.write_bytes(b"partial publication remains")
    assert "output_exists" in invoke(tmp_path, capsys, [path], out=out)
    assert out.read_bytes() == b"partial publication remains"
    ready = tmp_path / "ready-result.json"
    invoke(tmp_path, capsys, [path], out=ready)
    original = ready.read_bytes()
    assert "output_exists" in invoke(tmp_path, capsys, [path], out=ready)
    assert ready.read_bytes() == original


def test_results_atomic_publication_collision_keeps_existing_bytes(tmp_path, capsys, monkeypatch):
    out = tmp_path / "result.json"
    original_link = os.link

    def race(source, destination, **kwargs):
        # Concrete final-link collision: validation passed, another publisher won.
        out.write_bytes(b"other publisher")
        return original_link(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", race)
    invoke(tmp_path, capsys)
    assert out.read_bytes() == b"other publisher"
    assert list(tmp_path.iterdir()) == [out]  # No falsely ready file or abandoned temporary link.
