"""One read-only gate selector; use the real intake verifier, not its old suite."""

import builtins
import hashlib
import json
import os
import shutil
from copy import deepcopy
from functools import lru_cache

import pytest

import gpt56_foundry_evidence_intake as evidence
import gpt56_sol_codex_pilot_preflight as pilot
from .test_gpt56_foundry_evidence_intake import (
    AS_OF, OPTIONS, REVIEWED, _json, _offline, _parse_cache, _read, _seed,
    _tree, _update_artifact, _update_intake,
)
from .test_gpt56_sol_codex_pilot_preflight import offline_only


# Closed order, independent of production constants; local inputs and live
# consumption now retain the two parts of the former combined requirement.
ALL_BLOCKERS = [
    "foundry_account_project_deployment_identity_unverified",
    "foundry_served_model_version_unverified",
    "max_and_long_1m_capability_unverified",
    "native_call_and_token_limits_unresolved",
    "prepared_input_bytes_unverified",
    "live_inference_identity_and_wire_unverified",
    "pilot_dispatch_and_grading_identity_not_wired",
    "foundry_usage_and_tariff_mapping_unverified",
    "native_sandbox_and_result_bundle_host_unverified",
    "actual_pilot_deployment_not_prepared",
    "prepared_request_capture_unverified",
]
CLEARED = [ALL_BLOCKERS[index] for index in (0, 1, 2)]
REMAINING = [ALL_BLOCKERS[index] for index in (3, 4, 5, 6, 7, 8, 9, 10)]
SENTINEL = "private-evidence-value-DO-NOT-ECHO"


@pytest.fixture(scope="module")
def published_seed(tmp_path_factory, _seed):
    """Prepare once under the requesting case's offline guards; share bytes only."""
    @lru_cache(maxsize=1)
    def prepare():
        parent = tmp_path_factory.mktemp("foundry-gate-seed")
        source = parent / "source"
        for name, data in _seed:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        destination = parent / "bundle"
        evidence.publish_foundry_evidence(source=source, destination=destination, **OPTIONS)
        reserved = parent / "bundle.foundry-evidence-reservation.json"
        return (*(("bundle/" + name, data) for name, data in _tree(destination)),
                (reserved.name, reserved.read_bytes()))
    return prepare


@pytest.fixture
def bundle(tmp_path, _offline, published_seed):
    for name, data in published_seed():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        assert path.stat().st_nlink == 1
    return tmp_path / "bundle"


@pytest.fixture
def plan():
    return pilot.load_plan(pilot.PLAN)


def _reservation(bundle):
    return bundle.with_name(bundle.name + ".foundry-evidence-reservation.json")


def _expected_legacy(plan, problems=()):
    return {
        "configuration_valid": not problems,
        "configuration_problems": list(problems),
        "plan_sha256": pilot.seal(plan),
        "requested_codex_config_overrides": None if problems else [
            'model_reasoning_effort="max"', "model_context_window=1000000",
        ],
        "launch_allowed": False,
        "full_220_allowed": False,
        "launch_blockers": ALL_BLOCKERS,
    }


def _assert_refused(report):
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert report["launch_blockers"] == ALL_BLOCKERS
    assert report["evidence_gate"] == {
        "evidence_complete": False,
        "consumed_bundle_sha256": None,
        "reviewed_source_sha": None,
        "evaluated_at": None,
        "cleared_blockers": [],
        "remaining_blockers": ALL_BLOCKERS,
        "evidence_boundary": "offline_local_consistency",
        "refusal_code": "foundry_evidence_gate_refused",
    }
    assert SENTINEL not in json.dumps(report)


def _field_names(value):
    if isinstance(value, dict):
        return set(value) | {name for child in value.values() for name in _field_names(child)}
    if isinstance(value, list):
        return {name for child in value for name in _field_names(child)}
    return set()


@pytest.mark.parametrize("mode", ["absent", "null", "invalid-plan"])
def test_no_bundle_preserves_legacy_bytes_and_never_imports_verifier(plan, mode, tmp_path, monkeypatch, capsys):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name != "gpt56_foundry_evidence_intake", "no-bundle path imported verifier"
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    problems = ()
    if mode == "invalid-plan":
        plan["identity"]["model"] = "gpt-5.6-sol-fast"
        problems = ("identity",)
    options = {} if mode == "absent" else {
        "evidence_bundle": None, "reviewed_source_sha": None, "as_of": None,
    }
    expected = _expected_legacy(plan, problems)
    assert pilot.inspect_plan(plan, **options) == expected
    local_plan = tmp_path / "plan.yaml"
    local_plan.write_bytes(_json(plan))
    assert pilot.main(["--plan", str(local_plan)]) == 2
    # Same fields, key order and formatting as #630/#631 for this sealed plan.
    # Repinning the changed checker necessarily changes only the plan seal.
    assert capsys.readouterr().out == json.dumps(expected, indent=2, ensure_ascii=False) + "\n"


@pytest.mark.parametrize("entry", ["library", "cli"])
@pytest.mark.parametrize("evaluated", [AS_OF, "2026-09-25T00:00:00Z"])
def test_complete_bundle_clears_exactly_three_local_evidence_requirements(
    plan, bundle, entry, evaluated, monkeypatch, capsys,
):
    before = _tree(bundle.parent)
    original_plan = deepcopy(plan)
    calls = []
    real_verify = evidence.verify_foundry_evidence

    def traced_verify(**kwargs):
        calls.append(kwargs)
        return real_verify(**kwargs)

    def no_write(*args, **kwargs):
        pytest.fail("preflight attempted publication")

    monkeypatch.setattr(evidence, "verify_foundry_evidence", traced_verify)
    monkeypatch.setattr(evidence, "_write_no_clobber", no_write)
    if entry == "library":
        report = pilot.inspect_plan(plan, evidence_bundle=bundle, reviewed_source_sha=REVIEWED, as_of=evaluated)
    else:
        assert pilot.main([
            "--evidence-bundle", str(bundle), "--reviewed-source-sha", REVIEWED, "--as-of", evaluated,
        ]) == 2
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert captured.out == evidence._canonical_json(report) + "\n"
        assert captured.err == ""
    assert calls == [{"bundle_root": bundle, "reviewed_source_sha": REVIEWED, "as_of": evaluated}]
    assert report == {
        **_expected_legacy(plan),
        "launch_blockers": REMAINING,
        "evidence_gate": {
            "evidence_complete": True,
            "consumed_bundle_sha256": hashlib.sha256((bundle / evidence.READY_PATH).read_bytes()).hexdigest(),
            "reviewed_source_sha": REVIEWED,
            "evaluated_at": evaluated,
            "cleared_blockers": CLEARED,
            "remaining_blockers": REMAINING,
            "evidence_boundary": "offline_local_consistency",
        },
    }
    assert pilot.EVIDENCE_BLOCKER_ROLES == {
        ALL_BLOCKERS[0]: ("identity",), ALL_BLOCKERS[1]: ("identity",),
        ALL_BLOCKERS[2]: ("reasoning", "context"),
    }
    assert set(CLEARED).isdisjoint(REMAINING)
    assert plan == original_plan
    assert plan["launch_enabled"] is plan["pilot"]["full_220_enabled"] is False
    assert _tree(bundle.parent) == before
    # A literal blocker name contains "served_model_version". Inspect JSON
    # field names, not substrings of the required closed blocker vocabulary.
    assert _field_names(report).isdisjoint({
        "resource_id_sha256", "subject", "served_model_version", "meter_id", "amount",
    })
    encoded = json.dumps(report)
    for raw in ("artifacts/", str(bundle), "a" * 64, "b" * 64, "c" * 64, "e" * 64, "2026-09-01"):
        assert raw not in encoded


@pytest.mark.parametrize("present", [1, 2, 3, 4, 5, 6])
def test_partial_argument_groups_fail_closed(plan, bundle, present):
    names = ("evidence_bundle", "reviewed_source_sha", "as_of")
    values = (bundle, REVIEWED, AS_OF)
    options = {name: value for index, (name, value) in enumerate(zip(names, values)) if present & (1 << index)}
    _assert_refused(pilot.inspect_plan(plan, **options))


@pytest.mark.parametrize("field,value", [
    ("reviewed_source_sha", "main"), ("reviewed_source_sha", "c" * 8),
    ("reviewed_source_sha", "C" * 40), ("reviewed_source_sha", REVIEWED + "\n"),
    ("reviewed_source_sha", "d" * 40), ("reviewed_source_sha", "0" * 40),
    ("reviewed_source_sha", pilot.BASE_SHA), ("reviewed_source_sha", pilot.EVIDENCE_INTAKE["source_base_sha"]),
    ("reviewed_source_sha", True), ("reviewed_source_sha", SENTINEL),
    ("as_of", "2026-09-20"), ("as_of", "2026-09-20T03:00:00+00:00"),
    ("as_of", AS_OF + "\n"), ("as_of", "2026-09-31T03:00:00Z"),
    ("as_of", "2026-09-20T02:59:59Z"), ("as_of", "2026-10-01T00:00:01Z"),
    ("as_of", True), ("as_of", SENTINEL),
])
def test_invalid_or_stale_explicit_controls(plan, bundle, field, value):
    options = {**OPTIONS, field: value}
    _assert_refused(pilot.inspect_plan(plan, evidence_bundle=bundle, **options))


@pytest.mark.parametrize("member", [evidence.INTAKE_PATH, evidence.READY_PATH, "reservation",
                                    *("artifacts/" + role + ".json" for role in evidence.ROLES)])
@pytest.mark.parametrize("mutation", ["missing", "bytes"])
def test_every_current_member_and_reservation_is_reverified(plan, bundle, member, mutation):
    target = _reservation(bundle) if member == "reservation" else bundle / member
    if mutation == "missing":
        target.unlink()
    else:
        target.write_bytes(target.read_bytes() + b"\n")
    before = _tree(bundle.parent)
    _assert_refused(pilot.inspect_plan(plan, evidence_bundle=bundle, **OPTIONS))
    assert _tree(bundle.parent) == before


@pytest.mark.parametrize("role", evidence.ROLES)
def test_null_required_observation_cannot_use_an_old_complete_marker(plan, bundle, role):
    _update_artifact(bundle, role, lambda record: record.update({"observed": None}))
    _assert_refused(pilot.inspect_plan(plan, evidence_bundle=bundle, **OPTIONS))


@pytest.mark.parametrize("case", ["partial-usage", "missing-artifact", "documentation-only", "claimed-ready"])
def test_partial_evidence_cannot_clear_any_blocker(plan, bundle, case):
    if case == "partial-usage":
        _update_artifact(bundle, "usage", lambda record: record["observed"].update({"partial_reasons": ["usage_partial"]}))
    elif case == "missing-artifact":
        _update_intake(bundle, lambda record: record["claims"][0].update({"artifact": None}))
        (bundle / "artifacts/identity.json").unlink()
    elif case == "documentation-only":
        _update_artifact(bundle, "reasoning", lambda record: record.update({
            "source_kind": "documentation", "documented": record["observed"], "observed": None,
        }))
    else:
        ready = _read(bundle / evidence.READY_PATH)
        ready["evidence_complete"] = 1
        (bundle / evidence.READY_PATH).write_bytes(_json(ready))
    _assert_refused(pilot.inspect_plan(plan, evidence_bundle=bundle, **OPTIONS))


@pytest.mark.parametrize("field,value", [
    ("plan_sha256", "0" * 64), ("plan_base_sha", "f" * 40),
    ("run_id", "gpt56_sol_copilot_codex_pilot5_v1"), ("reviewed_source_sha", "f" * 40),
])
def test_stale_bundle_plan_run_or_review_binding(plan, bundle, field, value):
    _update_intake(bundle, lambda record: record.update({field: value}))
    _assert_refused(pilot.inspect_plan(plan, evidence_bundle=bundle, **OPTIONS))


@pytest.mark.parametrize("case", ["launch", "full-220", "model", "pin", "tasks"])
def test_evidence_cannot_waive_invalid_plan_controls(plan, bundle, case, monkeypatch):
    if case == "launch":
        plan["launch_enabled"] = True
    elif case == "full-220":
        plan["pilot"]["full_220_enabled"] = True
    elif case == "model":
        plan["identity"]["verified_model_id"] = "self-asserted"
    elif case == "pin":
        plan["source_pins"]["batch-runner/gpt56_foundry_evidence_intake.py"] = "0" * 64
    else:
        plan["dataset"]["tasks"].reverse()

    def should_not_verify(**kwargs):
        pytest.fail("invalid plan reached evidence verification")

    monkeypatch.setattr(evidence, "verify_foundry_evidence", should_not_verify)
    result = pilot.inspect_plan(plan, evidence_bundle=bundle, **OPTIONS)
    assert result["configuration_valid"] is False
    _assert_refused(result)


@pytest.mark.parametrize("case", ["pinned-bytes", "active-plan"])
def test_current_source_and_active_plan_drift_are_not_hidden_by_ready(plan, bundle, tmp_path, monkeypatch, case):
    repository = tmp_path / "repository"
    for name in pilot.REQUIRED_SOURCES | {pilot.ACTIVE_PLAN}:
        target = repository / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pilot.ROOT / name, target)
    target = repository / "batch-runner/gpt56_sol_codex_pilot_preflight.py"
    target.write_bytes(target.read_bytes() + b"\n# changed source\n")
    if case == "active-plan":
        updated = deepcopy(plan)
        updated["source_pins"]["batch-runner/gpt56_sol_codex_pilot_preflight.py"] = hashlib.sha256(target.read_bytes()).hexdigest()
        (repository / pilot.ACTIVE_PLAN).write_bytes(_json(updated))
        plan = updated
    monkeypatch.setattr(pilot, "ROOT", repository)
    _assert_refused(pilot.inspect_plan(plan, evidence_bundle=bundle, **OPTIONS))


@pytest.mark.parametrize("member", [evidence.READY_PATH, evidence.INTAKE_PATH, "artifacts/identity.json", "reservation"])
@pytest.mark.parametrize("link", ["symlink", "hardlink"])
def test_linked_members_refused(plan, bundle, member, link, tmp_path):
    target = _reservation(bundle) if member == "reservation" else bundle / member
    outside = tmp_path / "outside.json"
    target.rename(outside)
    if link == "symlink":
        target.symlink_to(outside)
    else:
        os.link(outside, target)
    _assert_refused(pilot.inspect_plan(plan, evidence_bundle=bundle, **OPTIONS))


@pytest.mark.parametrize("case", ["missing-root", "root-link", "ancestor-link", "artifacts-link", "traversal", "extra-role", "extra-file"])
def test_path_inventory_and_partial_destinations_fail_closed(plan, bundle, tmp_path, case):
    root = bundle
    if case == "missing-root":
        root = tmp_path / "never-created"
    elif case in ("root-link", "ancestor-link"):
        alias = tmp_path / "alias"
        alias.symlink_to(bundle if case == "root-link" else tmp_path, target_is_directory=True)
        root = alias if case == "root-link" else alias / bundle.name
    elif case == "artifacts-link":
        outside = tmp_path / "outside-artifacts"
        (bundle / "artifacts").rename(outside)
        (bundle / "artifacts").symlink_to(outside, target_is_directory=True)
    elif case == "traversal":
        root = bundle / ".." / bundle.name
    elif case == "extra-role":
        (bundle / "artifacts/extra.json").write_bytes(b"{}")
    else:
        (bundle / "extra.json").write_bytes(b"{}")
    _assert_refused(pilot.inspect_plan(plan, evidence_bundle=root, **OPTIONS))


@pytest.mark.parametrize("case", [
    "argument", "missing-value", "missing-group", "bad-plan", "missing-plan", "secret-artifact", "exception",
    "--evidence-bundlee", "--evidence-bundel", "--reviewed-source-shaa", "--as-off", "abbreviation",
])
def test_evidence_cli_refusals_never_echo_untrusted_values(plan, bundle, tmp_path, capsys, monkeypatch, case):
    arguments = ["--evidence-bundle", str(bundle), "--reviewed-source-sha", REVIEWED, "--as-of", AS_OF]
    if case == "argument":
        arguments += ["--unknown", SENTINEL]
    elif case.startswith("--"):
        arguments = [case, SENTINEL]
    elif case == "abbreviation":
        arguments = ["--evidence-bun=" + SENTINEL]
    elif case == "missing-value":
        arguments = ["--evidence-bundle", SENTINEL, "--as-of"]
    elif case == "missing-group":
        arguments = ["--reviewed-source-sha", SENTINEL]
    elif case in ("bad-plan", "missing-plan"):
        path = tmp_path / (SENTINEL + ".yaml")
        if case == "bad-plan":
            path.write_text("secret: [" + SENTINEL, encoding="utf-8")
        arguments += ["--plan", str(path)]
    elif case == "secret-artifact":
        _update_artifact(bundle, "identity", lambda record: record.update({"Authorization": SENTINEL}))
    else:
        def failed_verifier(**kwargs):
            raise RuntimeError(SENTINEL)
        monkeypatch.setattr(evidence, "verify_foundry_evidence", failed_verifier)
    assert pilot.main(arguments) == 2
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    _assert_refused(report)
    assert captured.out == evidence._canonical_json(report) + "\n"
    assert captured.err == ""
    assert SENTINEL not in captured.out
    assert str(bundle) not in captured.out
