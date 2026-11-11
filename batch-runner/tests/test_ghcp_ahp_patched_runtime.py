"""Patched load/receipt contracts. Only inert Node fixture modules are executed."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

import ghcp_ahp_patched_runtime as patched
import ghcp_ahp_probe as probe
import ghcp_ahp_wire_capture as wire

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name("fixtures") / "ghcp_ahp_patched_runtime_fixture.cjs"
BODY = b'export const fixtureOnly = true; const onChatConfigurationReady = "inert fixture only";\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def build_value(bundle_sha=sha(BODY)):
    return {"schema": "ghcp-patched-host-build-candidate-v3", "patched_ghcp": True,
            "upstream_commit": patched.PIN, "patch_sha256": patched.PATCH_SHA256,
            "source_archive_sha256": patched.SOURCE_SHA256, "base_manifest_sha256": patched.MANIFEST_SHA256,
            "patched_source_sha256": dict(patched.PATCHED_SOURCES), "runtime_relative_path": patched.RUNTIME_RELATIVE,
            "runtime_bundle_sha256": bundle_sha, "evidence_kind": "source-build-no-execution",
            "execution_allowed": False, "admission_allowed": False, "model_calls": 0,
            "load_evidence_sha256": None, "runtime_load_status": "not_executed"}


@pytest.fixture(scope="session")
def node_copy(tmp_path_factory):
    source = shutil.which("node")
    assert source, "Node is required; do not skip loader verification"
    folder = tmp_path_factory.mktemp("patched-node")
    target = folder / "node"
    shutil.copyfile(Path(source).resolve(), target)
    target.chmod(0o755)
    return target


def fixture_tree(tmp_path, node=None, *, wire_directory=True):
    prepared = tmp_path / "prepared"
    server = prepared / "cli-data/servers" / ("Stable-" + patched.PIN) / "server"
    bundle = server / patched.RUNTIME_RELATIVE
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(BODY)
    (server / "package.json").write_text('{"type":"module"}')
    executable = server / "node"
    if node is None:
        executable.write_bytes(b"not executed: synthetic node identity")
    else:
        os.link(node, executable)
    receipt = tmp_path / "build-receipt.json"
    receipt.write_bytes(encode(build_value()) + b"\n")
    state = tmp_path / "state"
    (state / "wire" if wire_directory else state).mkdir(parents=True)
    fork = {"vscode_commit": patched.PIN, "entrypoint": patched.ENTRYPOINT,
            "files": {"node": {"path": str(executable), "sha256": sha(executable.read_bytes())}}}
    request = {"path": receipt, "sha256": sha(receipt.read_bytes())}
    return {"prepared": prepared, "state": state, "bundle": bundle, "node": executable,
            "receipt": receipt, "request": request, "fork": fork}


def bind(tree):
    return patched.prepare_binding(tree["prepared"], tree["state"], tree["request"], tree["fork"], synthetic=True)


def run_loader(tree, environment, scenario="valid"):
    return subprocess.run([str(tree["node"]), str(FIXTURE), scenario],
                          env={"PATH": "/usr/bin:/bin", **environment}, cwd=tree["prepared"],
                          capture_output=True, text=True, timeout=30)


def records_for(output, environment):
    value = json.loads(output)
    assert value["synthetic"] is True and value["sessions"] == value["turns"] == value["model_calls"] == 0
    parent, child = value["ppid"], value["pid"]
    return [{"kind": "patched_runtime_child", "sequence": 1, "synthetic": True,
             "child_pid": child, "parent_pid": parent, "process": f"wire-{parent}.jsonl",
             "runtime_contract_sha256": environment["GHCP_AHP_PATCHED_RUNTIME_CONTRACT_SHA256"]},
            {"kind": "observer_installed", "sequence": 1, "synthetic": True, "model_free": True, "session_only": True,
             "process": f"wire-{child}.jsonl", "entrypoint": patched.ENTRYPOINT,
             "observer_sha256": sha(wire.PRELOAD.read_bytes())}]


def save_records(tree, records):
    directory = tree["state"] / "wire"
    for row in records:
        (directory / row["process"]).write_bytes(encode({key: value for key, value in row.items() if key != "process"}) + b"\n")
    (directory / "bootstrap.json").write_bytes(encode({"observer_sha256": sha(wire.PRELOAD.read_bytes()),
        "vscode_commit": patched.PIN, "patched_runtime_requested": True,
        "patched_build_receipt_sha256": tree["request"]["sha256"]}))
    (directory / "sources.json").write_bytes(encode({"scope": "synthetic base-source quote, not an applied-setting proof"}))


@pytest.fixture
def measured_json(tmp_path, node_copy):
    tree = fixture_tree(tmp_path, node_copy)
    environment = bind(tree)
    result = run_loader(tree, environment)
    assert result.returncode == 0, result.stderr
    rows = records_for(result.stdout, environment)
    save_records(tree, rows)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    pointer = wire.export(tree["state"], evidence)
    metadata = pointer["patched_runtime"]
    for name in ("probe.json", "summary.json", "handshake.json", "thread-policy.json"):
        probe.save_json(evidence / name, patched.stamp({"schema": "fixture-" + name, "status": "fixture_load_verified",
            "synthetic": True, "probe_exit": 0, "launch_allowed": False, "admission_allowed": False, "model_calls": 0}, metadata))
    return tree, evidence, metadata, rows


@pytest.fixture
def measured(measured_json):
    _, evidence, _, _ = measured_json
    patched.write_summary(evidence, handshake=True, policy=True)
    return measured_json


def test_original_manifest_patch_and_owner_lock_are_exact():
    assert patched.PIN == "2c33b50b16c472efe58357d1d2a8a5414bc23fbf"
    assert sha(patched.MANIFEST.read_bytes()) == "cd5ff8f2e1ad1f140892febdc75f288adfe8e3c96bd4d3b8e9a4078a90ef5049"
    assert sha(patched.PATCH.read_bytes()) == "a4e8d0fad6bc37b73b8dc2731be6914d07e0af6460ccb7bcf6749a48f8c3bceb"
    with pytest.raises(probe.Refused, match="patched_runtime_activation_pending_owner"):
        patched.require_activation()


@pytest.mark.parametrize("field,value", [
    ("patched_ghcp", False), ("patched_ghcp", 1), ("patch_sha256", "0" * 64), ("upstream_commit", "0" * 40),
    ("source_archive_sha256", "0" * 64), ("base_manifest_sha256", "0" * 64), ("patched_source_sha256", {}),
    ("runtime_relative_path", "out/other.js"), ("runtime_bundle_sha256", "short"), ("execution_allowed", True),
    ("admission_allowed", True), ("model_calls", False), ("load_evidence_sha256", "0" * 64),
    ("runtime_load_status", "measured"), ("extra", "unreviewed"),
])
def test_build_receipt_refuses_changed_contracts(field, value):
    receipt = build_value()
    receipt[field] = value
    with pytest.raises(probe.Refused, match="patched_build_receipt_refused"):
        patched.validate_build_receipt(receipt)


@pytest.mark.parametrize("field", list(build_value()))
def test_build_receipt_requires_every_field(field):
    receipt = build_value()
    del receipt[field]
    with pytest.raises(probe.Refused, match="patched_build_receipt_refused"):
        patched.validate_build_receipt(receipt)


@pytest.mark.parametrize("damage", ["receipt_hash", "bundle_hash", "node_hash", "fork_entrypoint", "bundle_symlink", "duplicate_key"])
def test_pre_launch_binding_refuses_drift(tmp_path, damage):
    tree = fixture_tree(tmp_path)
    if damage == "receipt_hash":
        tree["request"]["sha256"] = "0" * 64
    elif damage == "bundle_hash":
        tree["bundle"].write_text("changed")
    elif damage == "node_hash":
        tree["fork"]["files"]["node"]["sha256"] = "0" * 64
    elif damage == "fork_entrypoint":
        tree["fork"]["entrypoint"] = "other"
    elif damage == "bundle_symlink":
        original = tree["bundle"].with_suffix(".original")
        tree["bundle"].rename(original)
        tree["bundle"].symlink_to(original)
    else:
        tree["receipt"].write_bytes(b'{"schema":"duplicate",' + encode(build_value())[1:])
        tree["request"]["sha256"] = sha(tree["receipt"].read_bytes())
    with pytest.raises(probe.Refused):
        bind(tree)
    assert not (tree["state"] / "wire/patched-runtime").exists()


def test_staged_bytes_alone_are_not_load_evidence(tmp_path):
    tree = fixture_tree(tmp_path)
    bind(tree)
    with pytest.raises(probe.Refused, match="patched_runtime_load_unmeasured_or_duplicate"):
        patched.verify_live_ready(tree["state"])


def test_missing_observer_result_remains_labeled_as_an_unmeasured_patch_refusal(tmp_path):
    state, evidence = tmp_path / "state", tmp_path / "evidence"
    state.mkdir()
    evidence.mkdir()
    request = {"path": tmp_path / "not-read", "sha256": "a" * 64}
    pointer = wire.export(state, evidence, patched_request=request)
    report = json.loads((evidence / "wire-capture.json").read_text())
    assert report["patched_ghcp"] is True and report["patch_sha256"] == patched.PATCH_SHA256
    assert report["load_evidence_sha256"] is None and report["execution_allowed"] is False
    assert pointer["patched_runtime"] == patched.refusal_fields(request)
    with pytest.raises(probe.Refused, match="patched_runtime_provenance_unmeasured"):
        patched.validate_provenance(report)


@pytest.mark.parametrize("scenario,reason", [
    ("before_load_drift", "patched_runtime_before_load_mismatch"),
    ("rewrite_source", "patched_runtime_loaded_source_mismatch"),
    ("missing_source", "patched_runtime_load_unmeasured"), ("wrong_format", "patched_runtime_load_unmeasured"),
    ("no_hooks", "patched_runtime_loader_unavailable"), ("paid_mode", "patched_runtime_mode_or_contract_refused"),
    ("query_alias", "patched_runtime_load_alias_or_duplicate"),
])
def test_node_loader_rejects_before_returning_unverified_source(tmp_path, node_copy, scenario, reason):
    tree = fixture_tree(tmp_path, node_copy)
    environment = bind(tree)
    result = run_loader(tree, environment, scenario)
    assert result.returncode == 2 and reason in result.stderr
    assert result.stdout == ""
    assert list((tree["state"] / "wire/patched-runtime").glob("load-*.json")) == []


@pytest.mark.parametrize("scenario", ["no_load", "wrong_entrypoint", "after_load_drift"])
def test_missing_or_changed_runtime_is_refused_after_process_exit(tmp_path, node_copy, scenario):
    tree = fixture_tree(tmp_path, node_copy)
    environment = bind(tree)
    result = run_loader(tree, environment, scenario)
    assert result.returncode == 0, result.stderr
    rows = records_for(result.stdout, environment)
    with pytest.raises(probe.Refused, match="patched_runtime_(load_unmeasured_or_duplicate|post_load_drift)"):
        patched.collect(tree["state"], None, rows)


def test_real_node_loaded_bytes_are_bound_through_result_receipt_and_summary(measured):
    tree, evidence, metadata, _ = measured
    summary = patched.verify_artifact_chain(evidence, handshake=True, policy=True)
    assert metadata["loaded_bundle_sha256"] == sha(BODY)
    assert metadata["load_evidence_sha256"] == sha((evidence / "patched-load-evidence.json").read_bytes())
    assert metadata["runtime_evidence_synthetic"] is True
    assert summary["patched_ghcp"] is True and summary["execution_allowed"] is False
    assert patched.verify_live_ready(tree["state"]) == metadata


def test_human_summary_preserves_every_provenance_field_and_disabled_execution(measured_json):
    _, evidence, metadata, _ = measured_json
    patched.write_summary(evidence, handshake=True, policy=True)
    text = (evidence / "summary.md").read_text()
    assert "not native-policy or served-model attestation" in text
    for key, value in metadata.items():
        assert f"- {key}: `{json.dumps(value)}`" in text
    assert "execution_allowed: `false`" in text


def scoped_chain(measured_json):
    import ghcp_ahp_thread_policy as policy
    import ghcp_ahp_zero_turn_admission as scoped
    _, evidence, metadata, _ = measured_json
    capture = json.loads((evidence / "wire-capture.json").read_text())
    capture["bootstrap"].update(session_policy=True, authenticated_zero_turn=True)
    (evidence / "wire-capture.json").write_bytes(encode(capture))
    results = {"authenticate": {"result": None}, "createSession": {"result": None}}
    assessment = policy.assess(capture, results)
    assert assessment["admission_allowed"] is False and assessment["synthetic"] is True
    fields = {key: assessment[key] for key in scoped.FIELDS}
    (evidence / "thread-policy.json").write_bytes(encode(patched.stamp(assessment, metadata)))
    (evidence / "handshake.json").write_bytes(encode(patched.stamp({"schema": "ghcp-ahp-authenticated-zero-turn-v1",
        "rpc_results": results, **fields}, metadata)))
    (evidence / "summary.json").write_bytes(encode(patched.stamp({"schema": "ghcp-ahp-patched-summary-v1",
        "status": "fixture", "probe_exit": 2, **fields}, metadata)))
    patched.write_summary(evidence, handshake=True, policy=True)
    return evidence


def test_zero_turn_deferred_scope_is_bound_across_policy_handshake_json_and_markdown(measured_json):
    evidence = scoped_chain(measured_json)
    result = patched.verify_artifact_chain(evidence, handshake=True, policy=True)
    assert result["settings_verified"] is False and result["execution_allowed"] is False
    assert result["deferred_fields"] == ["served_model", "context_window", "web_search"]
    text = (evidence / "summary.md").read_text()
    assert "deferred_to_first_turn" in text and "sandbox_scope" in text
    assert "NOT passed" in text


@pytest.mark.parametrize("name", ["thread-policy.json", "handshake.json", "summary.json"])
@pytest.mark.parametrize("field", ["admission_scope", "sandbox_scope", "deferred_fields", "first_turn_required", "settings_verified", "verdicts"])
def test_zero_turn_scope_cannot_drop_a_field_or_use_an_unrelated_receipt(measured_json, name, field):
    evidence = scoped_chain(measured_json)
    value = json.loads((evidence / name).read_text())
    del value[field]
    (evidence / name).write_bytes(encode(value))
    with pytest.raises(probe.Refused, match="zero_turn_scope_chain_mismatch"):
        patched.verify_artifact_chain(evidence, handshake=True, policy=True)


def test_human_summary_cannot_render_a_dropped_receipt_marker(measured_json):
    _, evidence, _, _ = measured_json
    receipt = evidence / "probe.json"
    value = json.loads(receipt.read_text())
    del value["load_evidence_sha256"]
    receipt.write_bytes(encode(value))
    with pytest.raises(probe.Refused, match="patched_runtime_provenance_missing_or_invalid"):
        patched.write_summary(evidence)
    assert not (evidence / "summary.md").exists()


@pytest.mark.parametrize("name", ["wire-capture.json", "probe.json", "summary.json", "handshake.json", "thread-policy.json"])
@pytest.mark.parametrize("field", ["patched_ghcp", "patch_sha256", "load_evidence_sha256"])
def test_any_missing_propagated_field_refuses_the_whole_chain(measured, name, field):
    _, evidence, _, _ = measured
    target = evidence / name
    value = json.loads(target.read_text())
    del value[field]
    target.write_bytes(encode(value))
    with pytest.raises(probe.Refused, match="patched_runtime_provenance_missing_or_invalid"):
        patched.verify_artifact_chain(evidence, handshake=True, policy=True)


@pytest.mark.parametrize("field,value", [
    ("patch_sha256", "0" * 64), ("load_evidence_sha256", "0" * 64), ("build_receipt_sha256", "0" * 64),
    ("loaded_bundle_sha256", "0" * 64), ("runtime_contract_sha256", "0" * 64), ("execution_allowed", True),
    ("launch_allowed", True), ("admission_allowed", True), ("model_calls", 1), ("synthetic", False),
])
def test_summary_mismatch_or_execution_opt_in_is_refused(measured, field, value):
    _, evidence, _, _ = measured
    target = evidence / "summary.json"
    report = json.loads(target.read_text())
    report[field] = value
    target.write_bytes(encode(report))
    with pytest.raises(probe.Refused):
        patched.verify_artifact_chain(evidence)


@pytest.mark.parametrize("damage", ["foreign_pid", "wrong_parent", "missing_observer", "second_fork", "wrong_nonce", "duplicate_proof"])
def test_process_and_single_load_identity_cannot_be_substituted(measured, damage):
    tree, _, _, original = measured
    rows = copy.deepcopy(original)
    directory = tree["state"] / "wire/patched-runtime"
    file = next(directory.glob("load-*.json"))
    if damage == "foreign_pid":
        rows[0]["child_pid"] += 1
    elif damage == "wrong_parent":
        rows[0]["parent_pid"] += 1
    elif damage == "missing_observer":
        rows.pop()
    elif damage == "second_fork":
        rows.append(dict(rows[0]))
    elif damage == "wrong_nonce":
        value = json.loads(file.read_text())
        value["challenge_sha256"] = "0" * 64
        file.write_bytes(encode(value))
    else:
        (directory / "load-999999999.json").write_bytes(file.read_bytes())
    with pytest.raises(probe.Refused):
        patched.collect(tree["state"], None, rows)


def test_identical_forged_hashes_in_all_documents_do_not_repair_proof(measured):
    _, evidence, _, _ = measured
    for name in ("wire-capture.json", "probe.json", "summary.json"):
        target = evidence / name
        value = json.loads(target.read_text())
        value["load_evidence_sha256"] = "0" * 64
        target.write_bytes(encode(value))
    with pytest.raises(probe.Refused, match="patched_runtime_artifact_hash_mismatch"):
        patched.verify_artifact_chain(evidence)


def test_public_patched_entry_refuses_before_credentials_files_or_process(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(probe, "require_runner", lambda: {"eligible_for_execution": True})
    def forbidden(*args, **kwargs):
        raise AssertionError("must not launch or enter authenticated probe")
    monkeypatch.setattr(probe, "run_probe", forbidden)
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "SYNTHETIC_UNREAD_CREDENTIAL")
    result = probe.main(["probe", "--prepared", str(tmp_path / "absent"), "--evidence", str(tmp_path / "evidence"),
                         "--authenticated-zero-turn", "--patched-build-receipt", str(tmp_path / "absent-receipt"),
                         "--patched-build-receipt-sha256", "a" * 64])
    report = json.loads(capsys.readouterr().out)
    assert result == 2 and report["reason_code"] == "patched_runtime_activation_pending_owner"
    assert report["patched_ghcp"] is True and report["patch_sha256"] == patched.PATCH_SHA256
    assert report["load_evidence_sha256"] is None and report["execution_allowed"] is False
    assert os.environ["COPILOT_GITHUB_TOKEN"] == "SYNTHETIC_UNREAD_CREDENTIAL"
    assert not (tmp_path / "absent").exists()
    with pytest.raises(probe.Refused, match="patched_runtime_provenance_unmeasured"):
        patched.validate_provenance(report)


def test_internal_probe_entry_cannot_bypass_owner_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "require_runner", lambda: (_ for _ in ()).throw(AssertionError("too late")))
    with pytest.raises(probe.Refused, match="patched_runtime_activation_pending_owner"):
        probe.run_probe({}, tmp_path, tmp_path, "", "", session_policy=True,
                        patched_request={"path": tmp_path / "missing", "sha256": "a" * 64})


def test_candidate_workflow_has_no_dispatch_or_model_activation():
    path = ROOT / ".github/workflows/ghcp-ahp-patched-host-build-draft.yml"
    text = path.read_text()
    workflow = yaml.safe_load(text)
    assert set(workflow.get("on", workflow.get(True))) == {"workflow_call"}
    assert workflow["jobs"]["build-candidate"]["runs-on"] == "ubuntu-24.04"
    assert "secrets." not in text and "gh workflow run" not in text
    assert "--authenticated-zero-turn" not in text and "--session-policy-probe" not in text
    assert "continue-on-error" not in text and "|| true" not in text


def test_wire_install_carries_the_bound_loader_contract_without_changing_guard_inputs(tmp_path, monkeypatch):
    from ghcp_ahp_thread_policy import NATIVE_ARGS
    tree = fixture_tree(tmp_path, wire_directory=False)
    monkeypatch.setattr(wire, "discover_native_binary", lambda *_: (tree["node"], sha(tree["node"].read_bytes()), {"synthetic": True}))
    monkeypatch.setattr(wire, "source_evidence", lambda *_: {"synthetic": True})
    monkeypatch.setattr(wire, "agent_fork_contract", lambda *_: tree["fork"])
    environment = wire.install(tree["prepared"], tree["state"],
        {"VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS": json.dumps(NATIVE_ARGS)},
        model_free=True, session_policy=True, patched_request=tree["request"])
    contract_raw = environment["GHCP_AHP_PATCHED_RUNTIME_CONTRACT"].encode()
    contract = json.loads(contract_raw)
    assert environment["GHCP_AHP_PATCHED_RUNTIME_CONTRACT_SHA256"] == sha(contract_raw)
    assert contract["runtime_bundle_sha256"] == sha(BODY) and contract["execution_allowed"] is False
    assert environment["NODE_OPTIONS"] == "--require=" + json.dumps(str(wire.PRELOAD))
    assert json.loads(environment["GHCP_AHP_WIRE_FORK_CONTRACT"]) == tree["fork"]
    bootstrap = json.loads((tree["state"] / "wire/bootstrap.json").read_text())
    assert bootstrap["patched_runtime_requested"] is True


def test_wire_export_cannot_drop_the_patch_marker_while_a_binding_exists(measured, tmp_path):
    tree, _, _, _ = measured
    bootstrap = tree["state"] / "wire/bootstrap.json"
    value = json.loads(bootstrap.read_text())
    del value["patched_runtime_requested"]
    bootstrap.write_bytes(encode(value))
    other = tmp_path / "other-export"
    other.mkdir()
    with pytest.raises(probe.Refused, match="patched_runtime_marker_drift"):
        wire.export(tree["state"], other)
    assert list(other.iterdir()) == []


@pytest.mark.parametrize("drop", [False, True])
def test_probe_stdout_summary_consumes_the_persisted_chain_without_repair(measured, monkeypatch, capsys, drop):
    tree, evidence, metadata, _ = measured
    # Simulate the future owner decision ONLY with a fake run_probe. No host starts.
    monkeypatch.setattr(patched, "require_activation", lambda: None)
    monkeypatch.setattr(probe, "require_runner", lambda: {"eligible_for_execution": True})
    calls = []
    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        if drop:
            target = evidence / "summary.json"
            value = json.loads(target.read_text())
            del value["patch_sha256"]
            target.write_bytes(encode(value))
        return 0
    monkeypatch.setattr(probe, "run_probe", fake_run)
    result = probe.main(["probe", "--prepared", str(tree["prepared"]), "--evidence", str(evidence),
        "--session-policy-probe", "--patched-build-receipt", str(tree["receipt"]),
        "--patched-build-receipt-sha256", tree["request"]["sha256"]])
    report = json.loads(capsys.readouterr().out)
    assert len(calls) == 1 and calls[0]["patched_request"] == tree["request"]
    assert report["execution_allowed"] is False and report["model_calls"] == 0
    if drop:
        assert result == 2 and report["reason_code"] == "patched_runtime_provenance_missing_or_invalid"
        assert report["load_evidence_sha256"] is None
    else:
        assert result == 0
        assert patched.validate_provenance(report) == metadata


def test_build_receipt_measures_source_and_bundle_without_running_them(tmp_path, monkeypatch):
    # Tiny synthetic source inputs; the real immutable constants are checked separately.
    source = tmp_path / "source"
    source.mkdir()
    expected = {}
    for name in ("agent.ts", "codexAgent.ts", "agentService.ts"):
        (source / name).write_bytes(b"synthetic compile input")
        expected[name] = sha(b"synthetic compile input")
    monkeypatch.setattr(patched, "PATCHED_SOURCES", expected)
    bundle = tmp_path / "bundle.js"
    bundle.write_bytes(BODY)
    target = tmp_path / "receipt.json"
    value = patched.build_receipt(source, bundle, target)
    assert value["runtime_bundle_sha256"] == sha(BODY)
    assert value["load_evidence_sha256"] is None and value["execution_allowed"] is False
    assert patched.validate_build_receipt(json.loads(target.read_text())) == value
    (source / "agent.ts").write_bytes(b"tampered")
    with pytest.raises(probe.Refused, match="patched_source_hash_refused"):
        patched.build_receipt(source, bundle, tmp_path / "refused.json")
    assert not (tmp_path / "refused.json").exists()


def test_staging_uses_a_new_copy_and_is_not_load_proof(tmp_path, monkeypatch):
    tree = fixture_tree(tmp_path)
    original = b"synthetic original vendor bundle"
    tree["bundle"].write_bytes(original)
    candidate = tmp_path / "candidate.js"
    candidate.write_bytes(BODY)
    monkeypatch.setattr(patched, "_verified_base_bundle", lambda base: sha((base / tree["bundle"].relative_to(tree["prepared"])).read_bytes()))
    runtime = tmp_path / "separate-runtime"
    report = patched.stage_runtime(tree["prepared"], runtime, candidate, tree["request"])
    assert tree["bundle"].read_bytes() == original
    assert (runtime / tree["bundle"].relative_to(tree["prepared"])).read_bytes() == BODY
    assert report["runtime_load_status"] == "staged_not_loaded" and report["load_evidence_sha256"] is None
    assert report["execution_allowed"] is False
    with pytest.raises(probe.Refused):
        patched.validate_provenance(report)


@pytest.mark.parametrize("target", ["base", "inside", "existing"])
def test_staging_cannot_overwrite_or_nest_in_the_base(tmp_path, target):
    tree = fixture_tree(tmp_path)
    runtime = {"base": tree["prepared"], "inside": tree["prepared"] / "new", "existing": tree["state"]}[target]
    with pytest.raises(probe.Refused, match="patched_runtime_staging_target_refused"):
        patched.stage_runtime(tree["prepared"], runtime, tree["bundle"], tree["request"])
    assert tree["bundle"].read_bytes() == BODY


def test_staging_refuses_unverified_base_archive_before_copy(tmp_path):
    tree = fixture_tree(tmp_path)
    (tree["prepared"] / "downloads").mkdir()
    (tree["prepared"] / "downloads/server.tgz").write_bytes(b"not the pinned vendor archive")
    runtime = tmp_path / "not-created"
    with pytest.raises(probe.Refused, match="patched_base_server_archive_refused"):
        patched.stage_runtime(tree["prepared"], runtime, tree["bundle"], tree["request"])
    assert not runtime.exists()
