"""Immutable source lineage and synthetic equivalence; no provider is called."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile

import pytest
import yaml

import gpt56_pilot_grader_reseal as reseal
import gpt56_pilot_grader_prereqs_seal as prereqs
import gpt56_pilot_grader_seal as successor
import gpt56_sol_codex_pilot_preflight as pilot
import step8_grade as step8


ROOT = Path(__file__).resolve().parents[2]
PRICING_CONTEXT_MAIN = "c6fcacaf1e9d52e9dfc94a625ddfa0a694eb45df"
#: The main commit this reseal branched from: still the 20261030 closure.
RESEAL_BASE_MAIN = "cc256a5015bfb57996769c17e4aa52c26788f940"
PREREQS_BASE_MAIN = "e33cf06bc633d803f7985290bf671097ed7ca6d3"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("network forbidden in successor seal tests")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(socket, "getaddrinfo", refused)


def archived(sha, names):
    data = subprocess.run(
        ["/usr/bin/git", "archive", "--format=tar", sha, "--", *sorted(names)],
        cwd=ROOT, env={"PATH": os.defpath, "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
                       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": ""},
        capture_output=True, check=True, timeout=30,
    ).stdout
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        assert archive.pax_headers["comment"] == sha
        for member in archive.getmembers():
            if member.isdir():
                continue
            assert member.isfile() and member.name in names and member.name not in result
            result[member.name] = archive.extractfile(member).read()
    assert set(result) == set(names)
    return result


def fingerprint(blobs):
    digest = hashlib.sha256(b"gdpval-grader-source-v1\x00")
    for name, data in sorted(blobs.items()):
        encoded = name.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _materialize(target, blobs, record, monkeypatch):
    for name, data in blobs.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    path = target / record
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / record, path)
    monkeypatch.setattr(step8, "__file__", str(target / "batch-runner/step8_grade.py"))
    return target


def test_seal_matches_both_immutable_git_sources_and_exact_delta(tmp_path, monkeypatch):
    record = json.loads((ROOT / successor.RECORD).read_bytes())
    before = archived(successor.HISTORICAL_SOURCE, record["previous"]["files"])
    after = archived(successor.REVIEWED_BASE, record["files"])
    assert fingerprint(before) == successor.HISTORICAL_HASH
    assert fingerprint(after) == successor.GRADER_HASH
    assert {name: hashlib.sha256(data).hexdigest() for name, data in before.items()} == record["previous"]["files"]
    assert {name: hashlib.sha256(data).hexdigest() for name, data in after.items()} == record["files"]
    changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
    assert changed == set(record["changes"])
    assert len(changed) == 11
    assert sum(row["classification"] == "impact" for row in record["changes"].values()) == 6
    assert sum(row["kind"] == "added" for row in record["changes"].values()) == 2
    # The 20261030 successor verifies its own reviewed source, and refuses
    # today's tree, whose selector bytes only the 20261106 reseal admits.
    sealed_root = _materialize(tmp_path / "sealed", after, successor.RECORD, monkeypatch)
    report, sources = successor.verify(sealed_root)
    assert report["grader_source_hash"] == successor.GRADER_HASH
    assert report["previous_grader_source_hash"] == successor.HISTORICAL_HASH
    assert report["launch_authority"] is False
    assert set(sources) == set(after) | {successor.RECORD}
    monkeypatch.undo()
    with pytest.raises(successor.GraderSealRefused, match="^grader_successor_seal_refused$"):
        successor.verify(ROOT)


def test_only_grader_identity_and_reader_pin_change_not_fixed_conditions():
    old = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE_LONG_CONTEXT)
    grader_seal_path = ROOT / pilot.SOURCE_PROFILE_GRADER_SEAL
    assert hashlib.sha256(grader_seal_path.read_bytes()).hexdigest() == pilot.SOURCE_PROFILE_GRADER_SEAL_SHA256
    new = pilot.load_plan(grader_seal_path)
    expected = deepcopy(old)
    expected["dispatch_grading_identity"]["grader_template_source_hash"] = successor.GRADER_HASH
    reader = "batch-runner/gpt56_sol_codex_pilot_preflight.py"
    # The #794 reader bytes; the 11-05 batch-path successor re-pins the reader.
    expected["source_pins"][reader] = "9b9dc5417ff33eaa534bab368b4e50489a3336fab13ba5da9c69755f83d05e2f"
    assert new == expected
    batch_path_file = ROOT / pilot.SOURCE_PROFILE_BATCH_PATH
    assert hashlib.sha256(batch_path_file.read_bytes()).hexdigest() == pilot.SOURCE_PROFILE_BATCH_PATH_SHA256
    batch_path = pilot.load_plan(batch_path_file)
    expected_batch_path = deepcopy(new)
    expected_batch_path["source_pins"].update({
        "batch-runner/step2_run_inference.py": "e6afe287b2533e460ae5329423e78e0da0754a49f1f4e6c0824b2af9c3ece623",
        reader: "ad14c0ea0ea3efdd124a7c5e85892c8f96e87f13cabcd73a0df47ef45fb62570",
    })
    assert batch_path == expected_batch_path
    selector = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE_SELECTOR_RESEAL)
    expected_active = deepcopy(batch_path)
    expected_active["dispatch_grading_identity"]["grader_template_source_hash"] = reseal.GRADER_HASH
    held_selector_reader = archived(PREREQS_BASE_MAIN, pilot.SOURCE_PROFILE_SELECTOR_RESEAL_DELTA)
    for name in pilot.SOURCE_PROFILE_SELECTOR_RESEAL_DELTA:
        expected_active["source_pins"][name] = hashlib.sha256(held_selector_reader[name]).hexdigest()
    assert selector == expected_active
    active = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE)
    expected_active = deepcopy(selector)
    expected_active["dispatch_grading_identity"]["grader_template_source_hash"] = prereqs.GRADER_HASH
    for name in pilot.SOURCE_PROFILE_PREREQS_DELTA:
        expected_active["source_pins"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    assert active == expected_active
    assert pilot.DISPATCH_GRADING_IDENTITY["grader_template_source_hash"] == successor.HISTORICAL_HASH
    record = json.loads((ROOT / successor.RECORD).read_bytes())
    config = yaml.safe_load((ROOT / successor.TEMPLATE).read_bytes())
    fixed = record["preserved_conditions"]
    assert config["judge"]["model"] == fixed["model"] == "gpt-5.6-sol"
    assert config["judge"]["reasoning"]["effort"] == fixed["reasoning_effort"] == "max"
    assert config["prompt"]["version"] == fixed["prompt_version"] == "v2.2"
    assert config["rubric"]["revision"] == fixed["rubric_revision"]
    assert new["pilot"]["task_count"] == fixed["task_count"] == 5
    import gpt56_pilot_usd_budget as money
    assert money.CEILING == "usd_ceiling_exceeded"
    assert fixed["combined_usd_ceiling"] == 200
    # Historical review statement: the original #794 did not change that
    # policy. #795 subsequently changes it outside this sealed closure; this
    # field must never restore old runtime behavior or rewrite the old record.
    assert fixed["missing_price_or_usage_refusals_unchanged"] is True
    assert hashlib.sha256((ROOT / fixed["usd_record"]).read_bytes()).hexdigest() == pilot.SOURCE_PROFILE_AUXILIARY[fixed["usd_record"]]


def test_merged_pricing_context_head_keeps_the_reviewed_sealed_closure():
    record = json.loads((ROOT / successor.RECORD).read_bytes())
    latest = archived(PRICING_CONTEXT_MAIN, record["files"])
    assert fingerprint(latest) == successor.GRADER_HASH
    assert {name: hashlib.sha256(data).hexdigest() for name, data in latest.items()} == record["files"]
    assert hashlib.sha256((ROOT / successor.RECORD).read_bytes()).hexdigest() == successor.RECORD_SHA256


def test_pricing_context_implementations_and_predecessors_are_not_reverted():
    roles = {"batch-runner/gpt56_pilot_usd_budget.py", "batch-runner/gpt56_pilot_wire_receipt.py",
             "batch-runner/gpt56_native_response_capture.py", pilot.CODEX_LONG_CONTEXT_CATALOG,
             pilot.SOURCE_PROFILE_CAPTURE_COUNTERS, pilot.SOURCE_PROFILE_LIST_PRICES,
             pilot.SOURCE_PROFILE_LONG_CONTEXT,
             pilot.ENVELOPE + "gpt56_sol_native_usd_cap_20261027.yaml"}
    latest = archived(PRICING_CONTEXT_MAIN, roles)
    for name, data in latest.items():
        assert (ROOT / name).read_bytes() == data
    # All changed implementations retain #796's held hashes; only the source
    # reader pin and grader identity are changed by this branch.
    new = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE)
    previous = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE_LONG_CONTEXT)
    for name in roles:
        if name in previous["source_pins"]:
            assert new["source_pins"][name] == previous["source_pins"][name]
        if name in pilot.SOURCE_PROFILE_AUXILIARY:
            assert hashlib.sha256(latest[name]).hexdigest() == pilot.SOURCE_PROFILE_AUXILIARY[name]


@pytest.fixture
def copied_source(tmp_path, monkeypatch):
    record = json.loads((ROOT / successor.RECORD).read_bytes())
    root = _materialize(tmp_path / "source", archived(successor.REVIEWED_BASE, record["files"]),
                        successor.RECORD, monkeypatch)
    assert successor.verify(root)[0]["grader_source_hash"] == successor.GRADER_HASH
    return root


@pytest.mark.parametrize("mutation", ["modified", "missing", "added", "symlink", "hardlink"])
def test_changed_core_set_or_unsafe_source_refuses(copied_source, mutation):
    root = copied_source
    path = root / "batch-runner/core/grader.py"
    if mutation == "modified":
        path.write_bytes(path.read_bytes() + b"\n# fixture drift\n")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "added":
        (path.parent / "unreviewed.py").write_text("# fixture\n")
    else:
        moved = root / "retained.py"
        path.rename(moved)
        if mutation == "symlink":
            path.symlink_to(moved)
        else:
            os.link(moved, path)
    with pytest.raises(successor.GraderSealRefused, match="^grader_successor_seal_refused$"):
        successor.verify(root)


@pytest.mark.parametrize("mutation", ["previous_hash", "changed_file_omitted", "raised_usd", "new_seal_hash"])
def test_manifest_edits_never_waive_a_hash(copied_source, mutation):
    path = copied_source / successor.RECORD
    record = json.loads(path.read_bytes())
    if mutation == "previous_hash":
        record["previous"]["grader_source_hash"] = "0" * 64
    elif mutation == "changed_file_omitted":
        del record["changes"]["batch-runner/core/grader.py"]
    elif mutation == "raised_usd":
        record["preserved_conditions"]["combined_usd_ceiling"] = 1000
    else:
        record["grader_source_hash"] = "0" * 64
    path.write_text(json.dumps(record))
    with pytest.raises(successor.GraderSealRefused, match="^grader_successor_seal_refused$"):
        successor.verify(copied_source)


def test_a_new_grader_hash_without_valid_manifest_is_not_accepted(monkeypatch):
    plan = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE)
    def refused(_root):
        raise successor.GraderSealRefused("PRIVATE-fixture-value")
    monkeypatch.setattr(reseal, "verify", refused)
    monkeypatch.setattr(prereqs, "verify", refused)
    result = pilot._inspect_plan_only(plan)
    assert result["configuration_valid"] is False
    assert "grader_successor_seal_refused" in result["configuration_problems"]
    assert "PRIVATE-fixture-value" not in json.dumps(result)
    assert result["launch_allowed"] is False


@pytest.mark.parametrize("bad", [None, False, "not-an-identity", []])
def test_malformed_grader_identity_is_refused_without_throwing(bad):
    plan = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE)
    plan["dispatch_grading_identity"] = bad
    result = pilot._inspect_plan_only(plan)
    assert result["configuration_valid"] is False
    assert "dispatch_grading_identity" in result["configuration_problems"]
    assert result["launch_allowed"] is False


@pytest.mark.parametrize("scenario", ["pass", "fail", "partial"])
def test_old_and_successor_requests_verdict_denominator_scores_summary_equal(approved_pilot_source, tmp_path, scenario):
    helper = Path(__file__).with_name("grader_guard_scope_probe.py")
    shared = tmp_path / "shared"
    env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
           "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TMPDIR": str(tmp_path)}
    observations = []
    for batch, extra in ((approved_pilot_source / "batch-runner", []), (ROOT / "batch-runner", ["--guarded"])):
        result = subprocess.run([sys.executable, "-B", str(helper), "--batch", str(batch),
                                 "--fixture", str(shared), "--scenario", scenario, *extra],
                                cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        observations.append(json.loads(result.stdout))
    assert observations[0] == observations[1]
    assert observations[1]["judged"]["verdict"] == scenario
    assert observations[1]["request"]["tools"][0]["parameters"]["properties"]["scope"]["type"] == ["object", "null"]
    assert observations[1]["tasks"][0]["total_max"] == 10


# ---------------------------------------------------------------------------
# 20261106 selector reseal: chained to the untouched 20261030 record.


def test_reseal_matches_immutable_sources_and_exact_selector_delta(tmp_path, monkeypatch):
    record = json.loads((ROOT / reseal.RECORD).read_bytes())
    sealed = json.loads((ROOT / successor.RECORD).read_bytes())
    assert hashlib.sha256((ROOT / reseal.RECORD).read_bytes()).hexdigest() == reseal.RECORD_SHA256
    assert record["predecessor_seal"] == {"path": successor.RECORD, "sha256": successor.RECORD_SHA256}
    assert record["previous"] == {"files": sealed["files"], "grader_source_hash": successor.GRADER_HASH,
                                  "source_sha": successor.REVIEWED_BASE}
    assert record["preserved_conditions"] == sealed["preserved_conditions"]
    before = archived(reseal.PREVIOUS_SOURCE, record["previous"]["files"])
    after = archived(reseal.REVIEWED_BASE, record["files"])
    assert fingerprint(before) == reseal.PREVIOUS_HASH == successor.GRADER_HASH
    assert fingerprint(after) == reseal.GRADER_HASH
    assert {name: hashlib.sha256(data).hexdigest() for name, data in after.items()} == record["files"]
    changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
    assert changed == set(record["changes"]) == reseal.CHANGED_FILES
    assert all(row["classification"] == "impact" and row["kind"] == "modified"
               for row in record["changes"].values())
    # Keep the positive proof on the exact historical bytes, not on a newer
    # closure which this unchanged predecessor is required to reject.
    with monkeypatch.context() as held:
        root = _materialize(tmp_path / "selector", after, reseal.RECORD, held)
        shutil.copyfile(ROOT / successor.RECORD, root / successor.RECORD)
        report, sources = reseal.verify(root)
        assert report["grader_source_hash"] == reseal.GRADER_HASH
        assert report["previous_grader_source_hash"] == successor.GRADER_HASH
        assert report["launch_authority"] is False
        assert set(sources) == set(after) | {reseal.RECORD, successor.RECORD}
    with pytest.raises(successor.GraderSealRefused, match="^grader_successor_seal_refused$"):
        reseal.verify(ROOT)


def test_reseal_base_main_still_held_the_20261030_closure():
    sealed = json.loads((ROOT / successor.RECORD).read_bytes())
    base = archived(RESEAL_BASE_MAIN, sealed["files"])
    assert {name: hashlib.sha256(data).hexdigest() for name, data in base.items()} == sealed["files"]
    assert fingerprint(base) == successor.GRADER_HASH


@pytest.fixture
def resealed_source(tmp_path, monkeypatch):
    record = json.loads((ROOT / reseal.RECORD).read_bytes())
    root = _materialize(tmp_path / "resealed", archived(reseal.REVIEWED_BASE, record["files"]),
                        reseal.RECORD, monkeypatch)
    for record in (reseal.RECORD, successor.RECORD):
        target = root / record
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / record, target)
    monkeypatch.setattr(step8, "__file__", str(root / "batch-runner/step8_grade.py"))
    assert reseal.verify(root)[0]["grader_source_hash"] == reseal.GRADER_HASH
    return root


@pytest.mark.parametrize("target", ["batch-runner/core/deliverable_selector.py", "batch-runner/core/grader.py"])
@pytest.mark.parametrize("mutation", ["modified", "missing", "added", "symlink", "hardlink"])
def test_reseal_refuses_any_other_or_further_change(resealed_source, target, mutation):
    path = resealed_source / target
    if mutation == "modified":
        path.write_bytes(path.read_bytes() + b"\n# fixture drift\n")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "added":
        (path.parent / "unreviewed.py").write_text("# fixture\n")
    else:
        moved = resealed_source / "retained.py"
        path.rename(moved)
        if mutation == "symlink":
            path.symlink_to(moved)
        else:
            os.link(moved, path)
    with pytest.raises(successor.GraderSealRefused, match="^grader_successor_seal_refused$"):
        reseal.verify(resealed_source)


@pytest.mark.parametrize("mutation", ["previous_hash", "previous_files", "changed_file_omitted", "raised_usd",
                                      "new_seal_hash", "predecessor_record", "launch_authority"])
def test_reseal_manifest_edits_never_waive_a_hash(resealed_source, mutation):
    path = resealed_source / reseal.RECORD
    record = json.loads(path.read_bytes())
    if mutation == "previous_hash":
        record["previous"]["grader_source_hash"] = "0" * 64
    elif mutation == "previous_files":
        record["previous"]["files"]["batch-runner/core/grader.py"] = "0" * 64
    elif mutation == "changed_file_omitted":
        del record["changes"]["batch-runner/core/deliverable_selector.py"]
    elif mutation == "raised_usd":
        record["preserved_conditions"]["combined_usd_ceiling"] = 1000
    elif mutation == "new_seal_hash":
        record["grader_source_hash"] = "0" * 64
    elif mutation == "launch_authority":
        record["launch_authority"] = True
    else:
        predecessor = resealed_source / successor.RECORD
        predecessor.write_bytes(predecessor.read_bytes() + b"\n")
    if mutation != "predecessor_record":
        path.write_text(json.dumps(record))
    with pytest.raises(successor.GraderSealRefused, match="^grader_successor_seal_refused$"):
        reseal.verify(resealed_source)


def test_superseded_successor_profile_refuses_the_resealed_bytes():
    for name in (pilot.SOURCE_PROFILE_BATCH_PATH, pilot.SOURCE_PROFILE_GRADER_SEAL,
                 pilot.SOURCE_PROFILE_SELECTOR_RESEAL):
        result = pilot._inspect_plan_only(pilot.load_plan(ROOT / name))
        assert result["configuration_valid"] is False
        assert "grader_successor_seal_refused" in result["configuration_problems"]
        assert result["launch_allowed"] is False
    active = pilot._inspect_plan_only(pilot.load_plan(ROOT / pilot.SOURCE_PROFILE))
    assert active["configuration_valid"] is True and active["configuration_problems"] == []
