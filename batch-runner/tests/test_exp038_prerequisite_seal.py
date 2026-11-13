"""The new registration advances data, never the hash algorithm or paid rights."""

import ast
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import socket

import pytest

import gpt56_pilot_grader_prereqs_seal as current
import gpt56_pilot_grader_reseal as previous
import gpt56_pilot_grader_seal as original
import gpt56_sol_codex_pilot_preflight as pilot
import ghcp_vm_gate_preflight as ghcp
import step8_grade as step8
from .test_gpt56_grader_successor_seal import archived, fingerprint


ROOT = Path(__file__).resolve().parents[2]
BASE_MAIN = "e33cf06bc633d803f7985290bf671097ed7ca6d3"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("network forbidden in prerequisite seal tests")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(socket, "getaddrinfo", refused)


def test_hash_verifier_and_scope_are_unchanged():
    assert current.source_files is previous.source_files is original.source_files
    assert ast.dump(ast.parse(inspect.getsource(current.verify))) == ast.dump(
        ast.parse(inspect.getsource(previous.verify))
    )
    old_step8 = archived(BASE_MAIN, {"batch-runner/step8_grade.py"})["batch-runner/step8_grade.py"]
    old_functions = {node.name: node for node in ast.parse(old_step8).body if isinstance(node, ast.FunctionDef)}
    new_functions = {node.name: node for node in ast.parse((ROOT / "batch-runner/step8_grade.py").read_bytes()).body
                     if isinstance(node, ast.FunctionDef)}
    for name in ("_requirements_closure", "compute_grader_source_hash"):
        assert ast.dump(old_functions[name]) == ast.dump(new_functions[name])
    immutable = {
        "batch-runner/gpt56_pilot_grader_seal.py", "batch-runner/gpt56_pilot_grader_reseal.py",
        "batch-runner/scripts/check_grader_hash_freeze.py", original.RECORD, previous.RECORD,
        pilot.SOURCE_PROFILE_SELECTOR_RESEAL,
    }
    for name, body in archived(BASE_MAIN, immutable).items():
        assert (ROOT / name).read_bytes() == body


def test_new_record_holds_both_git_closures_and_only_reviewed_changes():
    encoded = (ROOT / current.RECORD).read_bytes()
    assert hashlib.sha256(encoded).hexdigest() == current.RECORD_SHA256
    record = json.loads(encoded)
    prior = json.loads((ROOT / previous.RECORD).read_bytes())
    assert record["predecessor_seal"] == {"path": previous.RECORD, "sha256": previous.RECORD_SHA256}
    assert record["previous"] == {"source_sha": previous.REVIEWED_BASE,
                                   "grader_source_hash": previous.GRADER_HASH, "files": prior["files"]}
    before = archived(previous.REVIEWED_BASE, prior["files"])
    after = archived(current.REVIEWED_BASE, record["files"])
    assert fingerprint(before) == previous.GRADER_HASH
    assert fingerprint(after) == current.GRADER_HASH
    assert {name: hashlib.sha256(body).hexdigest() for name, body in after.items()} == record["files"]
    assert set(after) - set(before) == {"batch-runner/core/grading_retry.py"}
    assert not set(before) - set(after)
    changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
    assert changed == set(record["changes"]) == current.CHANGED_FILES
    assert len(changed) == 7
    assert sum(row["kind"] == "added" for row in record["changes"].values()) == 1
    assert all(row["classification"] == "impact" for row in record["changes"].values())
    assert record["preserved_conditions"] == prior["preserved_conditions"]
    assert record["launch_authority"] is record["owner_decision"]["paid_execution_authorized"] is False
    report, sources = current.verify(ROOT)
    assert report["grader_source_hash"] == current.GRADER_HASH
    assert report["previous_grader_source_hash"] == previous.GRADER_HASH
    assert report["launch_authority"] is False
    assert set(sources) == set(after) | {current.RECORD, previous.RECORD}
    with pytest.raises(original.GraderSealRefused, match="^grader_successor_seal_refused$"):
        previous.verify(ROOT)


def test_current_and_historical_auxiliary_bytes_are_both_checked():
    record = json.loads((ROOT / current.RECORD).read_bytes())["source_auxiliary"]
    assert record["previous_source_sha"] == BASE_MAIN
    assert record["reviewed_source_sha"] == current.REVIEWED_BASE
    assert record["previous"] == pilot.SOURCE_PROFILE_SELECTOR_AUXILIARY
    assert record["files"] == pilot.SOURCE_PROFILE_AUXILIARY
    assert set(record["previous"]) == set(record["files"])
    before = archived(BASE_MAIN, record["previous"])
    after = archived(current.REVIEWED_BASE, record["files"])
    for name in record["files"]:
        assert hashlib.sha256(before[name]).hexdigest() == record["previous"][name]
        assert hashlib.sha256(after[name]).hexdigest() == record["files"][name]
        assert (ROOT / name).read_bytes() == after[name]
    assert {name for name in before if before[name] != after[name]} == {".github/workflows/batch-run.yml"}
    assert set(record["changes"]) == {".github/workflows/batch-run.yml"}


def test_registration_changes_no_model_limits_money_or_approval_registry():
    prior = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE_SELECTOR_RESEAL)
    active = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE)
    expected = deepcopy(prior)
    expected["dispatch_grading_identity"]["grader_template_source_hash"] = current.GRADER_HASH
    for name in pilot.SOURCE_PROFILE_PREREQS_DELTA:
        expected["source_pins"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    assert active == expected
    assert set(active["source_pins"]) == set(prior["source_pins"]) == pilot.REQUIRED_SOURCES
    assert pilot._inspect_plan_only(active)["configuration_valid"] is True
    assert pilot._inspect_plan_only(active)["launch_allowed"] is False
    immutable = {
        "batch-runner/sol_batch_controls.py", "batch-runner/sol_batch_grading.py",
        "batch-runner/core/cost_metering.py", "batch-runner/core/runner_environment.py",
        "batch-runner/experiments/exp037_sol_first25.yaml",
        "batch-runner/experiments/exp038_sol_rest195.yaml",
        "batch-runner/grading_configs/exp037_v2_sol_max.yaml",
        "batch-runner/grading_configs/exp038_v2_sol_max.yaml",
        pilot.ENVELOPE + "gpt56_sol_native_usd_cap_20261027.yaml",
        pilot.ENVELOPE + "model_price_table.json",
    }
    for name, body in archived(BASE_MAIN, immutable).items():
        assert (ROOT / name).read_bytes() == body


def test_dependent_model_free_profile_keeps_its_policy_and_verifier():
    registration = json.loads((ROOT / current.RECORD).read_bytes())["dependent_source_profile"]
    old_bytes = (ROOT / ghcp.PREVIOUS_SOURCE_PROFILE_PATH).read_bytes()
    new_bytes = (ROOT / ghcp.SOURCE_PROFILE_PATH).read_bytes()
    assert old_bytes == archived(BASE_MAIN, {ghcp.PREVIOUS_SOURCE_PROFILE_PATH})[ghcp.PREVIOUS_SOURCE_PROFILE_PATH]
    assert hashlib.sha256(old_bytes).hexdigest() == ghcp.PREVIOUS_SOURCE_PROFILE_SHA256
    assert registration["previous"] == {"path": ghcp.PREVIOUS_SOURCE_PROFILE_PATH,
                                         "sha256": ghcp.PREVIOUS_SOURCE_PROFILE_SHA256,
                                         "source_sha": BASE_MAIN}
    assert registration["current"] == {"path": ghcp.SOURCE_PROFILE_PATH,
                                        "sha256": hashlib.sha256(new_bytes).hexdigest()}
    assert registration["reader"] == {"path": ghcp.SELF,
                                       "sha256": hashlib.sha256((ROOT / ghcp.SELF).read_bytes()).hexdigest()}
    old = ghcp.load_plan(ROOT / ghcp.PREVIOUS_SOURCE_PROFILE_PATH)
    new = ghcp.load_plan(ROOT / ghcp.SOURCE_PROFILE_PATH)
    assert {k: v for k, v in old.items() if k != "source_pins"} == {
        k: v for k, v in new.items() if k != "source_pins"}
    assert set(new["source_pins"]) == set(old["source_pins"]) == ghcp.REQUIRED_SOURCES
    assert {name for name in new["source_pins"] if new["source_pins"][name] != old["source_pins"][name]} == {
        ghcp.SELF, "batch-runner/step8_grade.py", "batch-runner/core/grader.py"}
    assert set(ghcp.SOURCE_PROFILE_UPDATES) == set(ghcp.PREVIOUS_SOURCE_PROFILE_UPDATES)
    assert ghcp.inspect_plan(old)["configuration_valid"] is False
    report = ghcp.inspect_plan(new)
    assert report["configuration_valid"] is True
    assert all(report[flag] is False for flag in ghcp.FALSE_FLAGS)
    assert report["source_registration"]["scope"] == registration["scope"] == (
        "source_consistency_only_not_grader_seal_or_launch_approval")
    assert registration["execution_allowed"] is False
    old_reader = archived(BASE_MAIN, {ghcp.SELF})[ghcp.SELF]
    old_functions = {node.name: node for node in ast.parse(old_reader).body if isinstance(node, ast.FunctionDef)}
    for function in (ghcp._sources, ghcp.inspect_plan):
        assert ast.dump(ast.parse(inspect.getsource(function)).body[0]) == ast.dump(old_functions[function.__name__])


@pytest.fixture
def sealed_tree(tmp_path, monkeypatch):
    record = json.loads((ROOT / current.RECORD).read_bytes())
    target = tmp_path / "sealed"
    for name, body in archived(current.REVIEWED_BASE, record["files"]).items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    for name in (current.RECORD, previous.RECORD):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    monkeypatch.setattr(step8, "__file__", str(target / "batch-runner/step8_grade.py"))
    assert current.verify(target)[0]["grader_source_hash"] == current.GRADER_HASH
    return target


@pytest.mark.parametrize("name", ["batch-runner/core/grading_retry.py", "batch-runner/requirements-renderer.txt"])
@pytest.mark.parametrize("mutation", ["modified", "missing", "added", "symlink", "hardlink"])
def test_changed_added_or_unsafe_closure_is_still_refused(sealed_tree, name, mutation):
    path = sealed_tree / name
    if mutation == "modified":
        path.write_bytes(path.read_bytes() + b"\n# fixture drift\n")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "added":
        (sealed_tree / "batch-runner/core/unreviewed.py").write_text("# fixture\n")
    else:
        retained = sealed_tree / "retained.txt"
        path.rename(retained)
        if mutation == "symlink":
            path.symlink_to(retained)
        else:
            os.link(retained, path)
    with pytest.raises(original.GraderSealRefused, match="^grader_successor_seal_refused$"):
        current.verify(sealed_tree)


@pytest.mark.parametrize("mutation", ["previous_hash", "previous_files", "changed_file_omitted", "raised_usd",
                                      "new_seal_hash", "predecessor_record", "launch_authority"])
def test_no_manifest_edit_can_waive_the_closed_hash(sealed_tree, mutation):
    path = sealed_tree / current.RECORD
    record = json.loads(path.read_bytes())
    if mutation == "previous_hash":
        record["previous"]["grader_source_hash"] = "0" * 64
    elif mutation == "previous_files":
        record["previous"]["files"]["batch-runner/core/grader.py"] = "0" * 64
    elif mutation == "changed_file_omitted":
        del record["changes"]["batch-runner/core/grading_retry.py"]
    elif mutation == "raised_usd":
        record["preserved_conditions"]["combined_usd_ceiling"] = 1000
    elif mutation == "new_seal_hash":
        record["grader_source_hash"] = "0" * 64
    elif mutation == "launch_authority":
        record["launch_authority"] = True
    else:
        predecessor = sealed_tree / previous.RECORD
        predecessor.write_bytes(predecessor.read_bytes() + b"\n")
    if mutation != "predecessor_record":
        path.write_text(json.dumps(record))
    with pytest.raises(original.GraderSealRefused, match="^grader_successor_seal_refused$"):
        current.verify(sealed_tree)
