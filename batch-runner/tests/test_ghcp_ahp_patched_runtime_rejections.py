"""Adversarial provenance consumers; inert loader fixtures, never a live host.

The fast chain fixture is deliberately synthetic. Native-process byte loading is
tested separately with the existing inert Node module, not a GHCP/SDK process.
"""

import copy
import json

import pytest

import ghcp_ahp_patched_runtime as patched
import ghcp_ahp_probe as probe
import ghcp_ahp_wire_capture as wire
from tests.test_ghcp_ahp_patched_runtime import (
    bind, encode, fixture_tree, node_copy, records_for, run_loader, save_records, sha,
)
from tests.test_ghcp_ahp_probe import backend_probe_fixture


JSON_DOCUMENTS = ("wire-capture.json", "probe.json", "summary.json", "handshake.json", "thread-policy.json")
REQUIRED_LABELS = ("patched_ghcp", "patch_sha256", "loaded_bundle_sha256", "load_evidence_sha256")


@pytest.fixture
def chain(tmp_path):
    """Consumer fixture only; all process records/proofs are explicitly synthetic."""
    tree = fixture_tree(tmp_path)
    environment = bind(tree)
    contract = json.loads(environment["GHCP_AHP_PATCHED_RUNTIME_CONTRACT"])
    child, parent = 4242, 4200
    proof = {"schema": "ghcp-patched-runtime-load-v2", "patched_ghcp": True,
        "upstream_commit": patched.PIN, "patch_sha256": patched.PATCH_SHA256,
        "build_receipt_sha256": contract["build_receipt_sha256"],
        "runtime_contract_sha256": environment["GHCP_AHP_PATCHED_RUNTIME_CONTRACT_SHA256"],
        "loaded_relative_path": patched.RUNTIME_RELATIVE, "loaded_source_sha256": contract["runtime_bundle_sha256"],
        "disk_before_sha256": contract["runtime_bundle_sha256"], "disk_after_sha256": contract["runtime_bundle_sha256"],
        "node_sha256": contract["node_sha256"], "loader_sha256": contract["loader_sha256"],
        "challenge_sha256": sha(contract["challenge"].encode()), "synthetic": True,
        "phase": "node_load_hook_before_evaluation", "execution_allowed": False, "pid": child, "ppid": parent}
    proof_file = tree["state"] / f"wire/patched-runtime/load-{child}.json"
    proof_file.write_bytes(encode(proof))
    rows = records_for(json.dumps({"pid": child, "ppid": parent, "synthetic": True,
        "sessions": 0, "turns": 0, "model_calls": 0}), environment)
    save_records(tree, rows)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    pointer = wire.export(tree["state"], evidence)
    provenance = pointer["patched_runtime"]
    assert provenance["runtime_evidence_synthetic"] is True
    assert provenance["execution_allowed"] is False
    for name in JSON_DOCUMENTS[1:]:
        value = patched.stamp({"schema": "synthetic-" + name, "synthetic": True,
            "model_calls": 0, "admission_allowed": False, "launch_allowed": False}, provenance)
        (evidence / name).write_bytes(encode(value))
    patched.write_summary(evidence, handshake=True, policy=True)
    assert patched.verify_artifact_chain(evidence, handshake=True, policy=True)["execution_allowed"] is False
    return tree, evidence, provenance, rows


def change_json(file, field, damage):
    value = json.loads(file.read_text())
    if damage == "missing":
        del value[field]
    else:
        value[field] = False if field == "patched_ghcp" else "0" * 64
    file.write_bytes(encode(value))


@pytest.mark.parametrize("document", ["wire-capture.json", "probe.json", "summary.json", "summary.md"])
@pytest.mark.parametrize("field", REQUIRED_LABELS)
@pytest.mark.parametrize("damage", ["missing", "mismatch"])
def test_required_labels_cannot_be_dropped_or_changed_in_any_persisted_output(chain, document, field, damage):
    _, evidence, provenance, _ = chain
    target = evidence / document
    if document.endswith(".json"):
        change_json(target, field, damage)
    else:
        text = target.read_text()
        line = f"- {field}: `{json.dumps(provenance[field])}`\n"
        assert text.count(line) == 1
        replacement = "" if damage == "missing" else f"- {field}: `{json.dumps(False if field == 'patched_ghcp' else '0' * 64)}`\n"
        target.write_text(text.replace(line, replacement))
    with pytest.raises(probe.Refused):
        patched.verify_artifact_chain(evidence, handshake=True, policy=True)


@pytest.mark.parametrize("damage", ["absent", "duplicate_label", "additional_permission", "synthetic_erased", "execution_enabled"])
def test_markdown_is_a_required_exact_projection_not_an_unchecked_sidecar(chain, damage):
    _, evidence, _, _ = chain
    target = evidence / "summary.md"
    if damage == "absent":
        target.rename(evidence / "removed-summary.md")
    else:
        text = target.read_text()
        if damage == "duplicate_label":
            text += "- patched_ghcp: `false`\n"
        elif damage == "additional_permission":
            text += "- admission_allowed: `true`\n"
        elif damage == "synthetic_erased":
            assert text.count("runtime_evidence_synthetic: `true`") == 1
            text = text.replace("runtime_evidence_synthetic: `true`", "runtime_evidence_synthetic: `false`")
        else:
            assert text.count("execution_allowed: `false`") == 1
            text = text.replace("execution_allowed: `false`", "execution_allowed: `true`")
        target.write_text(text)
    with pytest.raises(probe.Refused):
        patched.verify_artifact_chain(evidence)


def test_summary_writer_reads_back_what_was_actually_persisted(chain, monkeypatch):
    _, evidence, _, _ = chain
    (evidence / "summary.md").rename(evidence / "original-summary.md")
    original = patched._write
    def corrupted_write(path, data):
        assert path == evidence / "summary.md"
        original(path, data.replace(b"execution_allowed: `false`", b"execution_allowed: `true`"))
    monkeypatch.setattr(patched, "_write", corrupted_write)
    with pytest.raises(probe.Refused, match="^patched_runtime_markdown_mismatch$"):
        patched.write_summary(evidence)


@pytest.mark.parametrize("document", JSON_DOCUMENTS)
@pytest.mark.parametrize("field", [field for field in patched.PROVENANCE_FIELDS if field not in REQUIRED_LABELS])
def test_other_required_provenance_keys_cannot_disappear(chain, document, field):
    _, evidence, _, _ = chain
    change_json(evidence / document, field, "missing")
    with pytest.raises(probe.Refused, match="patched_runtime_provenance_missing_or_invalid"):
        patched.verify_artifact_chain(evidence, handshake=True, policy=True)


@pytest.mark.parametrize("field,value", [
    ("patched_ghcp", False), ("patched_ghcp", 1), ("patch_sha256", "0" * 64),
    ("execution_allowed", True), ("execution_allowed", 0),
])
def test_provenance_root_predicates_are_enforced_before_any_cross_document_check(chain, field, value):
    _, _, provenance, _ = chain
    forged = {**provenance, field: value}
    with pytest.raises(probe.Refused, match="^patched_runtime_provenance_missing_or_invalid$"):
        patched.validate_provenance(forged)


@pytest.mark.parametrize("field", REQUIRED_LABELS)
def test_agreeing_forged_labels_in_every_document_are_not_authority(chain, field):
    _, evidence, provenance, _ = chain
    for document in JSON_DOCUMENTS:
        change_json(evidence / document, field, "mismatch")
    path = evidence / "summary.md"
    old = f"- {field}: `{json.dumps(provenance[field])}`"
    new = f"- {field}: `{json.dumps(False if field == 'patched_ghcp' else '0' * 64)}`"
    text = path.read_text()
    assert text.count(old) == 1
    path.write_text(text.replace(old, new))
    with pytest.raises(probe.Refused):
        patched.verify_artifact_chain(evidence, handshake=True, policy=True)


@pytest.mark.parametrize("field", patched.PROVENANCE_FIELDS)
def test_stamp_does_not_silently_repair_conflicting_labels(chain, field):
    _, _, provenance, _ = chain
    conflict = not provenance[field] if type(provenance[field]) is bool else "conflicting-value"
    with pytest.raises(probe.Refused, match="^patched_runtime_provenance_conflict$"):
        patched.stamp({field: conflict}, provenance)


@pytest.mark.parametrize("field,value", [
    ("execution_allowed", True), ("admission_allowed", True), ("patched_ghcp", False),
    ("patch_sha256", "0" * 64), ("challenge", ""), ("synthetic", "false"), ("extra", True),
])
def test_persisted_contract_schema_is_checked_before_proof_or_hash_checks(chain, field, value):
    tree, _, _, _ = chain
    directory = tree["state"] / "wire/patched-runtime"
    contract = json.loads((directory / "contract.json").read_text())
    build = json.loads((directory / "build-receipt.json").read_text())
    contract[field] = value
    with pytest.raises(probe.Refused, match="^patched_runtime_contract_refused$"):
        patched._validate_contract(contract, build)


@pytest.mark.parametrize("field,value", [
    ("patched_ghcp", False), ("patch_sha256", "0" * 64), ("loaded_source_sha256", "0" * 64),
    ("synthetic", False), ("execution_allowed", True), ("pid", True), ("ppid", True),
])
def test_load_proof_requires_measured_identity_and_boolean_labels(chain, field, value):
    tree, _, _, rows = chain
    proof_file = tree["state"] / "wire/patched-runtime/load-4242.json"
    proof = json.loads(proof_file.read_text())
    proof[field] = value
    proof_file.write_bytes(encode(proof))
    with pytest.raises(probe.Refused):
        patched.collect(tree["state"], None, rows)


@pytest.mark.parametrize("which,field,value", [
    (0, "process", "wire-1.jsonl"), (1, "process", "wire-1.jsonl"),
    (0, "runtime_contract_sha256", "0" * 64), (0, "synthetic", False), (1, "synthetic", False),
    (1, "model_free", False), (1, "session_only", False),
    (0, "child_pid", 1), (0, "parent_pid", 1),
])
def test_process_binding_rejects_the_exact_wrong_observer_field(chain, which, field, value):
    tree, _, _, original = chain
    rows = copy.deepcopy(original)
    rows[which][field] = value
    with pytest.raises(probe.Refused, match="^patched_runtime_process_binding_refused$"):
        patched.collect(tree["state"], None, rows)


def test_load_filename_must_identify_the_only_proof_pid(chain):
    tree, _, _, rows = chain
    directory = tree["state"] / "wire/patched-runtime"
    (directory / "load-4242.json").rename(directory / "load-1.json")
    with pytest.raises(probe.Refused, match="^patched_runtime_load_path_refused$"):
        patched.collect(tree["state"], None, rows)


@pytest.mark.parametrize("component", ["bundle", "node"])
def test_post_load_file_tampering_is_rejected_without_copying_evidence(chain, component, tmp_path):
    tree, _, _, rows = chain
    tree[component].write_bytes(b"changed after the synthetic load")
    output = tmp_path / "must-stay-empty"
    output.mkdir()
    with pytest.raises(probe.Refused, match="^patched_runtime_post_load_drift$"):
        patched.collect(tree["state"], output, rows)
    assert list(output.iterdir()) == []


@pytest.mark.parametrize("field", ["build_receipt_sha256", "loader_sha256"])
def test_collector_revalidates_its_binding_before_proof_identity(chain, field):
    tree, _, _, rows = chain
    path = tree["state"] / "wire/patched-runtime/contract.json"
    contract = json.loads(path.read_text())
    contract[field] = "0" * 64
    path.write_bytes(encode(contract))
    with pytest.raises(probe.Refused, match="^patched_runtime_binding_drift$"):
        patched.collect(tree["state"], None, rows)


@pytest.mark.parametrize("site", ["bootstrap", "record"])
def test_receipt_requires_the_real_observer_code_identity(chain, site):
    _, evidence, _, _ = chain
    target = evidence / "wire-capture.json"
    capture = json.loads(target.read_text())
    if site == "bootstrap":
        capture["bootstrap"]["observer_sha256"] = "0" * 64
    else:
        installed = [row for row in capture["records"] if row["kind"] == "observer_installed"]
        assert len(installed) == 1
        installed[0]["observer_sha256"] = "0" * 64
    target.write_bytes(encode(capture))
    with pytest.raises(probe.Refused, match="^patched_runtime_observer_identity_mismatch$"):
        patched.verify_artifact_chain(evidence)


@pytest.mark.parametrize("field,value", [
    ("execution_allowed", True), ("launch_allowed", True), ("admission_allowed", True),
    ("gate_ready", True), ("connection_verified", True), ("model_calls", 1), ("model_calls", False),
])
@pytest.mark.parametrize("document", JSON_DOCUMENTS)
def test_no_result_receipt_or_summary_can_promote_execution(chain, document, field, value):
    _, evidence, _, _ = chain
    path = evidence / document
    record = json.loads(path.read_text())
    record[field] = value
    path.write_bytes(encode(record))
    with pytest.raises(probe.Refused):
        patched.verify_artifact_chain(evidence, handshake=True, policy=True)


@pytest.mark.parametrize("document", JSON_DOCUMENTS)
def test_synthetic_capture_cannot_be_relabeled_as_live(chain, document):
    _, evidence, _, _ = chain
    path = evidence / document
    record = json.loads(path.read_text())
    record["synthetic"] = False
    path.write_bytes(encode(record))
    with pytest.raises(probe.Refused, match="^patched_runtime_fixture_cannot_be_live_evidence$"):
        patched.verify_artifact_chain(evidence, handshake=True, policy=True)


def test_agreeing_live_labels_cannot_erase_the_raw_synthetic_contract(chain):
    _, evidence, _, _ = chain
    for name in JSON_DOCUMENTS:
        target = evidence / name
        value = json.loads(target.read_text())
        value.update(runtime_evidence_synthetic=False, synthetic=False)
        target.write_bytes(encode(value))
    path = evidence / "summary.md"
    text = path.read_text()
    assert text.count("runtime_evidence_synthetic: `true`") == 1
    path.write_text(text.replace("runtime_evidence_synthetic: `true`", "runtime_evidence_synthetic: `false`"))
    with pytest.raises(probe.Refused, match="^patched_runtime_artifact_hash_mismatch$"):
        patched.verify_artifact_chain(evidence, handshake=True, policy=True)


@pytest.mark.parametrize("scenario,reason", [
    ("initial_bundle_drift", "patched_runtime_hash_mismatch"),
    ("initial_loader_hash", "patched_runtime_hash_mismatch"),
    ("initial_node_hash", "patched_runtime_hash_mismatch"),
    ("fork_binding", "patched_runtime_fork_binding_refused"),
    ("invalid_execution_flag", "patched_runtime_contract_refused"),
    ("invalid_admission_flag", "patched_runtime_contract_refused"),
    ("invalid_synthetic", "patched_runtime_contract_refused"),
    ("session_not_zero_turn", "patched_runtime_mode_or_contract_refused"),
    ("disk_during_load", "patched_runtime_loaded_source_mismatch"),
    ("source_and_disk_drift", "patched_runtime_loaded_source_mismatch"),
])
def test_independent_loader_boundaries_reject_before_returning_bytes(tmp_path, node_copy, scenario, reason):
    tree = fixture_tree(tmp_path, node_copy)
    environment = bind(tree)
    result = run_loader(tree, environment, scenario)
    assert result.returncode == 2 and reason in result.stderr
    assert result.stdout == ""
    assert list((tree["state"] / "wire/patched-runtime").glob("load-*.json")) == []


def test_unmeasured_patch_stops_before_rpc_even_if_owner_lock_is_stubbed_for_fixture(backend_probe_fixture, monkeypatch, tmp_path):
    # All process/transport calls are already inert fakes in backend_probe_fixture.
    # This never unlocks the real CLI and uses no credential or live SDK.
    def forbidden(*args, **kwargs):
        pytest.fail("offline fixture crossed a process or network boundary")
    monkeypatch.setattr(probe.subprocess, "Popen", forbidden)
    monkeypatch.setattr(probe.socket, "create_connection", forbidden)
    monkeypatch.setattr(probe.urllib.request, "build_opener", forbidden)
    request = {"path": tmp_path / "absent-receipt.json", "sha256": "a" * 64}
    original = probe.run_probe
    monkeypatch.setattr(patched, "require_activation", lambda: None)
    monkeypatch.setattr(probe, "run_probe", lambda *args, **kwargs: original(*args, **kwargs, patched_request=request))
    monkeypatch.setattr(wire, "export", lambda *args, **kwargs: {
        "capture_status": "observer_not_started", "patched_runtime": patched.refusal_fields(request)})
    receipt, calls, _ = backend_probe_fixture(session_policy=True)
    assert calls["exit_code"] == 2
    assert receipt["reason_codes"][0] == "patched_runtime_file_unavailable"
    assert calls["transport"].sent == []
    assert receipt["session_create_requests"] == receipt["model_calls"] == 0
    assert receipt["execution_allowed"] is False and receipt["load_evidence_sha256"] is None
    assert calls["stops"] >= 1
