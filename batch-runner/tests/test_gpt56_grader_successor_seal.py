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

import gpt56_pilot_grader_seal as successor
import gpt56_sol_codex_pilot_preflight as pilot
import step8_grade as step8


ROOT = Path(__file__).resolve().parents[2]
PRICING_CONTEXT_MAIN = "c6fcacaf1e9d52e9dfc94a625ddfa0a694eb45df"


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


def test_seal_matches_both_immutable_git_sources_and_exact_delta():
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
    report, sources = successor.verify(ROOT)
    assert report["grader_source_hash"] == successor.GRADER_HASH
    assert report["previous_grader_source_hash"] == successor.HISTORICAL_HASH
    assert report["launch_authority"] is False
    assert set(sources) == set(after) | {successor.RECORD}


def test_only_grader_identity_and_reader_pin_change_not_fixed_conditions():
    old = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE_LONG_CONTEXT)
    new = pilot.load_plan(ROOT / pilot.SOURCE_PROFILE)
    expected = deepcopy(old)
    expected["dispatch_grading_identity"]["grader_template_source_hash"] = successor.GRADER_HASH
    reader = "batch-runner/gpt56_sol_codex_pilot_preflight.py"
    expected["source_pins"][reader] = hashlib.sha256((ROOT / reader).read_bytes()).hexdigest()
    assert new == expected
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
    root = tmp_path / "source"
    for name, path in successor.source_files(ROOT).items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    target = root / successor.RECORD
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / successor.RECORD, target)
    monkeypatch.setattr(step8, "__file__", str(root / "batch-runner/step8_grade.py"))
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
    monkeypatch.setattr(successor, "verify", refused)
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
