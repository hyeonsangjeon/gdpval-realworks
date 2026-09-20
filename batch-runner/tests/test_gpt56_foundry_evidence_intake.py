"""One offline selector for the externally supplied Foundry evidence boundary."""

import hashlib
import json
import os
import shutil
import socket
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

from core import grader, llm_client
import gpt56_foundry_evidence_intake as evidence
import gpt56_sol_codex_pilot_preflight as pilot
from .test_gpt56_sol_codex_pilot_preflight import offline_only

REVIEWED = "c" * 40
AS_OF = "2026-09-20T03:00:00Z"
OPTIONS = {"reviewed_source_sha": REVIEWED, "as_of": AS_OF}


def _json(value):
    return evidence._canonical_json(value).encode("utf-8")


def _digest(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _read(path):
    return json.loads(path.read_bytes())


def _update_intake(root, mutate):
    path = root / evidence.INTAKE_PATH
    document = _read(path)
    mutate(document)
    path.write_bytes(_json(document))


def _update_artifact(root, role, mutate):
    path = root / "artifacts" / (role + ".json")
    document = _read(path)
    mutate(document)
    path.write_bytes(_json(document))
    _update_intake(root, lambda intake: intake["claims"][evidence.ROLES.index(role)].update({
        "artifact": {"path": "artifacts/" + role + ".json", **_digest(path.read_bytes())},
    }))


def _set(document, keys, value):
    for key in keys[:-1]:
        document = document[key]
    document[keys[-1]] = value


def _tree(root):
    return tuple((path.relative_to(root).as_posix(), path.read_bytes())
                 for path in sorted(root.rglob("*")) if path.is_file())


@pytest.fixture(scope="module")
def _seed():
    """Only immutable small bytes are shared, not trees or validator verdicts."""
    plan = pilot.load_plan(pilot.PLAN)
    subject = {
        "provider": "azure", "account": {"resource_id_sha256": "a" * 64},
        "project": {"resource_id_sha256": "b" * 64},
        "deployment": {"resource_id_sha256": "c" * 64},
        "served_model": "gpt-5.6-sol", "served_model_version": "2026-09-01",
    }
    meters = {name: f"00000000-0000-0000-0000-{index:012d}"
              for index, name in enumerate(evidence.METERS, 1)}
    observations = {
        "identity": subject,
        "reasoning": {"reasoning_effort": "max", "response_status": "completed", "response_id_sha256": "e" * 64},
        "context": {"scope": "single_response", "accepted_input_tokens": 999000, "accepted_output_tokens": 1000,
                    "unit": "tokens", "response_status": "completed", "response_id_sha256": "e" * 64},
        "native_caps": {"scope": "per_attempt", "enforcement": "native", "model_calls": 16,
                        "input_tokens": 2000000, "output_tokens": 64000, "call_unit": "calls", "token_unit": "tokens"},
        "usage": {"currency": "USD", "region": "eastus", "partial_reasons": [],
                  "meters": {name: {"meter_id": meters[name], "quantity": quantity, "unit": "tokens"}
                             for name, quantity in zip(evidence.METERS, (1000000, 0, 1000))}},
        "tariff": {"currency": "USD", "region": "eastus", "effective_at": "2026-09-01T00:00:00Z",
                   "expires_at": "2026-10-01T00:00:00Z", "tariff_source": "azure_price_sheet",
                   "rates": {name: {"meter_id": meters[name], "amount": "2.50", "per_tokens": 1000000}
                             for name in evidence.METERS}},
    }
    files, claims = {}, []
    for role in evidence.ROLES:
        name = "artifacts/" + role + ".json"
        files[name] = _json({
            "role": role, "source_kind": evidence.KINDS[role],
            "issued_at": "2026-09-20T02:05:00Z", "observed_at": "2026-09-20T02:00:00Z",
            "valid_until": "2026-10-01T00:00:00Z", "subject": subject,
            "documented": None, "observed": observations[role],
        })
        claims.append({"role": role, "artifact": {"path": name, **_digest(files[name])}})
    files[evidence.INTAKE_PATH] = _json({
        "schema_version": "foundry-pilot-evidence-intake-v1", "reviewed_source_sha": REVIEWED,
        "plan_base_sha": plan["base_sha"], "plan_sha256": pilot.seal(plan),
        "run_id": pilot.RUN_ID, "evaluated_at": AS_OF,
        "requested": {"provider": "azure", "model": "gpt-5.6-sol", "harness": "codex",
                      "reasoning_effort": "max", "model_context_window": 1000000,
                      "credential_policy": "repository_approved_entra_only"},
        "claims": claims,
    })
    return tuple(sorted(files.items()))


@pytest.fixture(scope="module")
def _parse_cache():
    # Same byte-keyed immutable parse pattern as #626. Every real source file,
    # digest, link count and validator is still checked on every invocation.
    real = yaml.safe_load

    @lru_cache(maxsize=32)
    def parse(data):
        return real(data)

    def cached(data):
        return deepcopy(parse(data)) if type(data) in (str, bytes) else real(data)

    return cached


@pytest.fixture(autouse=True)
def _offline(monkeypatch, offline_only, _parse_cache):
    def forbidden(*args, **kwargs):
        offline_only.append("forbidden boundary")
        raise AssertionError("evidence intake attempted live work")

    monkeypatch.setattr(yaml, "safe_load", _parse_cache)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(grader, "Grader", forbidden)
    for name in ("create_client", "create_typed_azure_client", "create_provider_client"):
        monkeypatch.setattr(llm_client, name, forbidden)


@pytest.fixture
def source(tmp_path, _seed):
    root = tmp_path / "source"
    for name, data in _seed:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        assert path.stat().st_nlink == 1
    return root


def _destination(source):
    target = source.parent / "installed"
    return target, target.with_name(target.name + ".foundry-evidence-reservation.json")


def _refused_before_write(source):
    target, reservation = _destination(source)
    with pytest.raises(evidence.EvidenceIntakeRefused):
        evidence.publish_foundry_evidence(source=source, destination=target, **OPTIONS)
    assert not os.path.lexists(target)
    assert not os.path.lexists(reservation)


@pytest.mark.parametrize("mode", ["compile", "publish", "verify-later", "cli", "independent-copy"])
def test_complete_evidence_binds_only_local_consistency(source, mode, capsys, _seed):
    before = _tree(source)
    result = evidence.compile_foundry_evidence(source=source, **OPTIONS)
    document = result.as_dict()
    assert not result.missing
    assert document["launch_enabled"] is document["full_220_enabled"] is False
    assert document["remaining_launch_blockers"] == list(pilot.LAUNCH_BLOCKERS)
    assert document["evidence_boundary"] == "offline_local_consistency"
    assert document["requested"]["model_context_window"] == 1000000
    assert document["claims"]["context"]["evidence"]["observed"]["accepted_input_tokens"] == 999000
    assert document["claims"]["context"]["evidence"]["documented"] is None
    assert document["plan_sha256"] == pilot.seal(pilot.load_plan(pilot.PLAN))
    assert document["source_pins"] == pilot.load_plan(pilot.PLAN)["source_pins"]
    assert str(source).encode() not in result.canonical_bytes()
    target, reservation = _destination(source)
    if mode != "compile":
        if mode == "cli":
            assert evidence.main(["--source", str(source), "--destination", str(target),
                                  "--reviewed-source-sha", REVIEWED, "--as-of", AS_OF]) == 0
            status = json.loads(capsys.readouterr().out)
            assert status == {"evidence_complete": True, "bundle_sha256": result.sha256, "ready_present": True,
                              "missing_evidence": [], "launch_enabled": False, "full_220_enabled": False}
        else:
            assert evidence.publish_foundry_evidence(source=source, destination=target, **OPTIONS) == result
        assert (target / evidence.READY_PATH).read_bytes() == result.canonical_bytes()
        assert reservation.read_bytes() == evidence._reservation(result)
        for name, data in result.files:
            assert (target / name).read_bytes() == data
            assert (target / name).stat().st_nlink == 1
        now = "2026-09-20T04:00:00Z" if mode == "verify-later" else AS_OF
        assert evidence.verify_foundry_evidence(bundle_root=target, reviewed_source_sha=REVIEWED, as_of=now) == result
        if mode == "independent-copy":
            _update_artifact(source, "usage", lambda row: row["observed"]["meters"]["input_tokens"].update(quantity=42))
            assert evidence.verify_foundry_evidence(bundle_root=target, **OPTIONS) == result
            assert _seed == before  # No mutable seed tree was shared.
    else:
        assert _tree(source) == before and not target.exists() and not reservation.exists()


@pytest.mark.parametrize("role,field", [
    *((role, "artifact") for role in evidence.ROLES),
    *((role, "observed") for role in evidence.ROLES),
    *(("identity", field) for field in ("issued_at", "observed_at", "valid_until")),
    ("reasoning", "documentation"), ("context", "source_kind"),
    ("usage", "quantity"), ("usage", "currency"), ("usage", "unit"),
    ("usage", "partial_reasons"), ("tariff", "amount"), ("tariff", "currency"),
    ("native_caps", "model_calls"), ("identity", "subject"),
])
def test_unknown_evidence_is_preserved_but_cannot_publish(source, role, field, capsys):
    if field == "artifact":
        (source / "artifacts" / (role + ".json")).unlink()
        _update_intake(source, lambda row: row["claims"][evidence.ROLES.index(role)].update(artifact=None))
    elif field == "subject":
        for item in evidence.ROLES:
            def change(record):
                record["subject"]["account"] = None
                if record["role"] == "identity":
                    record["observed"]["account"] = None
            _update_artifact(source, item, change)
    else:
        def change(record):
            if field in ("observed", "documentation", "source_kind"):
                record["documented"], record["observed"] = record["observed"], None
                if field != "observed":
                    record["source_kind"] = "documentation" if field == "documentation" else None
            elif field in ("issued_at", "observed_at", "valid_until"):
                record[field] = None
            elif field in ("quantity", "unit"):
                record["observed"]["meters"]["input_tokens"][field] = None
            elif field == "amount":
                record["observed"]["rates"]["input_tokens"][field] = None
            elif field == "partial_reasons":
                record["observed"][field] = ["price_missing"]
            else:
                record["observed"][field] = None
        _update_artifact(source, role, change)
    result = evidence.compile_foundry_evidence(source=source, **OPTIONS)
    assert result.missing and result.as_dict()["evidence_complete"] is False
    record = result.as_dict()["claims"][role]["evidence"]
    if field == "quantity":
        assert record["observed"]["meters"]["input_tokens"]["quantity"] is None
    if field == "amount":
        assert record["observed"]["rates"]["input_tokens"]["amount"] is None
    if field == "observed":
        assert record["observed"] is None and record["documented"] is not None
    assert evidence.main(["--source", str(source), "--reviewed-source-sha", REVIEWED, "--as-of", AS_OF]) == 2
    status = json.loads(capsys.readouterr().out)
    assert status["missing_evidence"] == list(result.missing) and status["ready_present"] is False
    _refused_before_write(source)


@pytest.mark.parametrize("role,path,value", [
    (None, ("reviewed_source_sha",), "a" * 40),
    (None, ("plan_sha256",), "0" * 64), (None, ("plan_base_sha",), "0" * 40),
    (None, ("run_id",), "gpt56_sol_copilot_codex_pilot5_v1"),
    (None, ("requested", "provider"), "github_copilot"), (None, ("requested", "provider"), "openai"),
    (None, ("requested", "model"), "gpt-5.6-sol-fast"),
    (None, ("requested", "reasoning_effort"), "xhigh"),
    (None, ("requested", "model_context_window"), 1000000.0),
    (None, ("requested", "fallback"), "personal_openai"),
    (None, ("evaluated_at",), "2026-09-20T04:00:00Z"),
    (None, ("claims", 0, "artifact", "sha256"), "0" * 64),
    (None, ("claims", 0, "artifact", "size"), 1),
    (None, ("claims", 0, "artifact", "path"), "../identity.json"),
    (None, ("claims", 0, "artifact", "path"), "/tmp/identity.json"),
    (None, ("claims", 0, "artifact", "path"), "artifacts/reasoning.json"),
    ("identity", ("subject", "served_model"), "gpt-5.6-sol-fast"),
    ("identity", ("subject", "provider"), "openai"),
    ("reasoning", ("subject", "account", "resource_id_sha256"), "d" * 64),
    ("identity", ("observed", "served_model_version"), "2026-08-01"),
    ("reasoning", ("source_kind",), "documentation"),
    ("reasoning", ("source_kind",), "foundry_usage_export"),
    ("reasoning", ("observed",), True),
    ("reasoning", ("observed", "reasoning_effort"), "Max"),
    ("context", ("observed", "accepted_input_tokens"), 10),
    ("context", ("observed", "accepted_input_tokens"), True),
    ("context", ("observed", "unit"), "bytes"),
    ("context", ("observed", "scope"), "thread_total"),
    ("context", ("observed", "response_id_sha256"), "f" * 64),
    ("native_caps", ("observed", "scope"), "per_minute"),
    ("native_caps", ("observed", "enforcement"), "requested"),
    *(("native_caps", ("observed", "model_calls"), value) for value in (0, -1, "16", 16.0, True)),
    ("usage", ("observed", "currency"), "ZZZ"),
    ("usage", ("observed", "currency"), "unknown"),
    ("usage", ("observed", "region"), "unknown"),
    ("usage", ("observed", "meters", "input_tokens", "unit"), "unknown"),
    ("usage", ("observed", "meters", "cached_input_tokens", "quantity"), 1000001),
    ("usage", ("observed", "meters", "cached_input_tokens", "meter_id"), "00000000-0000-0000-0000-000000000001"),
    ("tariff", ("observed", "currency"), "EUR"),
    ("tariff", ("observed", "region"), "westus"),
    ("tariff", ("observed", "rates", "input_tokens", "meter_id"), "00000000-0000-0000-0000-000000000999"),
    ("tariff", ("observed", "rates", "input_tokens", "per_tokens"), 0),
    ("tariff", ("observed", "rates", "input_tokens", "amount"), "NaN"),
    ("tariff", ("observed", "rates", "input_tokens", "amount"), "2.50\n"),
    ("usage", ("observed", "meters", "input_tokens", "meter_id"), "00000000-0000-0000-0000-000000000001\n"),
    ("identity", ("subject", "account", "resource_id_sha256"), "a" * 64 + "\n"),
    ("identity", ("subject", "served_model_version"), "2026-09-01\n"),
    ("identity", ("issued_at",), "2026-09-21T00:00:00Z"),
    ("identity", ("observed_at",), "2026-09-20T02:06:00Z"),
    ("identity", ("valid_until",), "2026-09-19T00:00:00Z"),
    ("identity", ("issued_at",), "2026-99-01T00:00:00Z"),
    ("tariff", ("observed", "effective_at"), "2026-10-01T00:00:00Z"),
    ("tariff", ("observed", "effective_at"), "2026-09-20T03:00:00Z"),
    ("tariff", ("observed", "expires_at"), "2026-09-19T00:00:00Z"),
])
def test_mismatches_refuse_before_any_write(source, role, path, value):
    if role is None:
        _update_intake(source, lambda document: _set(document, path, value))
    else:
        _update_artifact(source, role, lambda document: _set(document, path, value))
    _refused_before_write(source)


@pytest.mark.parametrize("case", ["missing-role", "duplicate-role", "extra-role", "reordered-role",
                                  "missing-key", "duplicate-json-key", "extra-file", "missing-file"])
def test_exact_inventory_and_json_contract(source, case):
    if case in ("missing-role", "duplicate-role", "extra-role", "reordered-role", "missing-key"):
        def change(document):
            if case == "missing-role":
                document["claims"].pop()
            elif case == "duplicate-role":
                document["claims"][1] = deepcopy(document["claims"][0])
            elif case == "extra-role":
                document["claims"].append(deepcopy(document["claims"][0]))
            elif case == "reordered-role":
                document["claims"].reverse()
            else:
                del document["requested"]
        _update_intake(source, change)
    elif case == "duplicate-json-key":
        path = source / evidence.INTAKE_PATH
        path.write_bytes(path.read_bytes().replace(b'{', b'{"run_id":"duplicate",', 1))
    elif case == "extra-file":
        (source / "artifacts" / "extra.json").write_bytes(b"{}")
    else:
        (source / "artifacts" / "identity.json").unlink()
    _refused_before_write(source)


@pytest.mark.parametrize("field,value", [
    ("credential", "SENSITIVE-fixture-credential"), ("token", "SENSITIVE-fixture-token"),
    ("api_key", "SENSITIVE-fixture-key"), ("Authorization", "Bearer SENSITIVE-fixture"),
    ("endpoint", "https://fixture.invalid/?key=SENSITIVE-fixture"),
    ("email", "SENSITIVE-fixture@example.invalid"), ("name", "SENSITIVE Fixture Person"),
])
def test_secret_and_personal_fields_are_never_published_or_echoed(source, field, value, capsys):
    _update_artifact(source, "identity", lambda document: document.update({field: value}))
    target, reservation = _destination(source)
    assert evidence.main(["--source", str(source), "--destination", str(target),
                          "--reviewed-source-sha", REVIEWED, "--as-of", AS_OF]) == 2
    output = capsys.readouterr()
    assert value not in output.out + output.err and "SENSITIVE" not in output.out + output.err
    assert not target.exists() and not reservation.exists()
    assert json.loads(output.out)["ready_present"] is False


def test_cli_parse_errors_do_not_echo_values(capsys):
    assert evidence.main(["--api-key", "SENSITIVE-not-a-real-key"]) == 2
    captured = capsys.readouterr()
    assert "SENSITIVE" not in captured.out + captured.err
    assert json.loads(captured.out)["error"] == "invalid_cli_arguments"


@pytest.mark.parametrize("case", ["file-symlink", "file-hardlink", "root-symlink", "directory-symlink", "parent-traversal"])
def test_unsafe_source_paths_are_refused(source, case):
    item = source / "artifacts" / "identity.json"
    if case in ("file-symlink", "file-hardlink"):
        outside = source.parent / "outside.json"
        item.rename(outside)
        if case == "file-symlink":
            item.symlink_to(outside)
        else:
            os.link(outside, item)
    elif case == "root-symlink":
        alias = source.parent / "alias"
        alias.symlink_to(source, target_is_directory=True)
        source = alias
    elif case == "directory-symlink":
        outside = source.parent / "outside-artifacts"
        (source / "artifacts").rename(outside)
        (source / "artifacts").symlink_to(outside, target_is_directory=True)
    else:
        source = source / ".." / "source"
    _refused_before_write(source)


@pytest.mark.parametrize("case", ["destination", "reservation", "destination-symlink", "parent-symlink", "overlap"])
def test_collision_and_reservation_cannot_be_reused(source, case):
    target, reservation = _destination(source)
    if case == "destination":
        target.mkdir()
    elif case == "reservation":
        reservation.write_bytes(b"partial-intent")
    elif case == "destination-symlink":
        target.symlink_to(source, target_is_directory=True)
    elif case == "parent-symlink":
        alias = source.parent / "alias"
        alias.symlink_to(source.parent, target_is_directory=True)
        target = alias / "installed"
    else:
        target = source / "installed"
    before = _tree(source)
    with pytest.raises(evidence.EvidenceIntakeRefused):
        evidence.publish_foundry_evidence(source=source, destination=target, **OPTIONS)
    assert _tree(source) == before
    assert not (target / evidence.READY_PATH).exists()


@pytest.mark.parametrize("failed_write", range(1, 10))
def test_every_publication_failure_retains_no_ready_and_refuses_reuse(source, failed_write, monkeypatch):
    target, reservation = _destination(source)
    real_writer, calls = evidence._write_no_clobber, []

    def fail(path, data):
        calls.append(path)
        if len(calls) == failed_write:
            raise OSError("injected I/O failure")
        real_writer(path, data)

    with monkeypatch.context() as patch:
        patch.setattr(evidence, "_write_no_clobber", fail)
        with pytest.raises(evidence.EvidenceIntakeRefused):
            evidence.publish_foundry_evidence(source=source, destination=target, **OPTIONS)
    assert len(calls) == failed_write
    assert not (target / evidence.READY_PATH).exists()
    assert reservation.exists() is (failed_write > 1)
    if failed_write > 1:
        before = _tree(target)
        with pytest.raises(evidence.EvidenceIntakeRefused):
            evidence.publish_foundry_evidence(source=source, destination=target, **OPTIONS)
        with pytest.raises(evidence.EvidenceIntakeRefused):
            evidence.verify_foundry_evidence(bundle_root=target, **OPTIONS)
        assert _tree(target) == before


def test_atomic_writer_does_not_overwrite_a_racing_member(source, monkeypatch):
    target, reservation = _destination(source)
    real_writer = evidence._write_no_clobber
    occupied = target / "artifacts" / "identity.json"

    def collide(path, data):
        if path == occupied:
            path.write_bytes(b"pre-existing-member")
        real_writer(path, data)

    monkeypatch.setattr(evidence, "_write_no_clobber", collide)
    with pytest.raises(evidence.EvidenceIntakeRefused):
        evidence.publish_foundry_evidence(source=source, destination=target, **OPTIONS)
    assert occupied.read_bytes() == b"pre-existing-member"
    assert reservation.exists() and not (target / evidence.READY_PATH).exists()


@pytest.mark.parametrize("case", ["ready-missing", "ready-whitespace", "reservation-missing", "reservation-altered",
                                  "artifact-drift", "rehash-drift", "ready-hardlink", "reservation-hardlink",
                                  "ready-symlink", "late-expiry"])
def test_published_evidence_must_be_reverified(source, case):
    target, reservation = _destination(source)
    evidence.publish_foundry_evidence(source=source, destination=target, **OPTIONS)
    ready = target / evidence.READY_PATH
    if case == "ready-missing":
        ready.unlink()
    elif case == "ready-whitespace":
        ready.write_bytes(ready.read_bytes() + b"\n")
    elif case == "reservation-missing":
        reservation.unlink()
    elif case == "reservation-altered":
        reservation.write_bytes(b"{}")
    elif case == "artifact-drift":
        path = target / "artifacts" / "usage.json"
        path.write_bytes(path.read_bytes() + b"\n")
    elif case == "rehash-drift":
        _update_artifact(target, "usage", lambda record: record["observed"]["meters"]["input_tokens"].update(quantity=42))
    elif case == "ready-hardlink":
        os.link(ready, target.parent / "ready-hardlink.json")
    elif case == "reservation-hardlink":
        os.link(reservation, target.parent / "reservation-hardlink.json")
    elif case == "ready-symlink":
        moved = target.parent / "moved-ready.json"
        ready.rename(moved)
        ready.symlink_to(moved)
    options = {**OPTIONS, "as_of": "2026-10-02T00:00:00Z"} if case == "late-expiry" else OPTIONS
    with pytest.raises(evidence.EvidenceIntakeRefused):
        evidence.verify_foundry_evidence(bundle_root=target, **options)


@pytest.mark.parametrize("case", ["source-drift", "installed-drift", "parent-replacement"])
def test_changes_during_publication_never_receive_ready(source, case, monkeypatch):
    target, reservation = _destination(source)
    real_writer, calls = evidence._write_no_clobber, []

    def mutate(path, data):
        real_writer(path, data)
        calls.append(path)
        if len(calls) == 8:
            if case == "parent-replacement":
                target.rename(target.with_name("displaced"))
                target.mkdir()
            else:
                root = source if case == "source-drift" else target
                _update_artifact(root, "usage", lambda record: record["observed"]["meters"]["input_tokens"].update(quantity=42))

    monkeypatch.setattr(evidence, "_write_no_clobber", mutate)
    with pytest.raises(evidence.EvidenceIntakeRefused):
        evidence.publish_foundry_evidence(source=source, destination=target, **OPTIONS)
    assert reservation.exists() and not (target / evidence.READY_PATH).exists()
    assert not (target.with_name("displaced") / evidence.READY_PATH).exists()


@pytest.mark.parametrize("reviewed", ["main", "c" * 12, "C" * 40, "0" * 40,
                                     pilot.BASE_SHA, pilot.GRADER_SOURCE_SHA,
                                     "d8fd52d9c75687a8e088748c589f9a9a07834a41",
                                     "11e7900cdcac61bc4daf59e65feb238acda98fbf"])
def test_historical_or_nonimmutable_values_are_not_external_review(source, reviewed):
    _update_intake(source, lambda record: record.update(reviewed_source_sha=reviewed))
    with pytest.raises(evidence.EvidenceIntakeRefused):
        evidence.compile_foundry_evidence(source=source, reviewed_source_sha=reviewed, as_of=AS_OF)


@pytest.mark.parametrize("case", ["contract", "missing-source-pin", "digest-drift", "source-byte-drift",
                                  "schema-byte-drift", "intake-contract-drift", "launch-flag"])
def test_active_registration_seals_the_intake_boundary(source, tmp_path, monkeypatch, case):
    plan = pilot.load_plan(pilot.PLAN)
    if case == "contract":
        result = pilot.inspect_plan(plan)
        assert result["configuration_valid"] is True
        assert set(plan["source_pins"]) == pilot.REQUIRED_SOURCES
        assert len(pilot.REQUIRED_SOURCES) == 38
        assert set(pilot.EVIDENCE_SOURCES) <= set(plan["source_pins"])
        assert plan["evidence_intake"] == pilot.EVIDENCE_INTAKE
        assert result["launch_allowed"] is result["full_220_allowed"] is False
        assert result["launch_blockers"] == list(pilot.LAUNCH_BLOCKERS)
        assert plan["foundry_identity"]["account"] is None
        assert plan["limits"]["native_model_calls_per_attempt"] is None
        history = pilot.load_plan(pilot.ROOT / pilot.HISTORICAL_PLAN)
        assert history["status"] == "superseded"
        for section in ("dataset", "developer_instructions", "limits", "grading", "results", "codex_request"):
            assert plan[section] == history[section]
        return
    repository = tmp_path / "repository"
    for name in pilot.REQUIRED_SOURCES | {pilot.ACTIVE_PLAN}:
        target = repository / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pilot.ROOT / name, target)
    if case == "missing-source-pin":
        del plan["source_pins"][pilot.EVIDENCE_INTAKE["compiler"]]
    elif case == "digest-drift":
        plan["source_pins"][pilot.EVIDENCE_INTAKE["compiler"]] = "0" * 64
    elif case in ("source-byte-drift", "schema-byte-drift"):
        key = "compiler" if case == "source-byte-drift" else "schema"
        target = repository / pilot.EVIDENCE_INTAKE[key]
        target.write_bytes(target.read_bytes() + b"\n")
    elif case == "intake-contract-drift":
        plan["evidence_intake"]["evidence_boundary"] = "launch_approval"
    else:
        plan["launch_enabled"] = True
    (repository / pilot.ACTIVE_PLAN).write_bytes(_json(plan))
    monkeypatch.setattr(pilot, "ROOT", repository)
    _refused_before_write(source)
