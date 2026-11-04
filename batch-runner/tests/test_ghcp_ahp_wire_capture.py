"""Offline wire capture tests. Only fake Node transports, never a real host/SDK."""

import copy
import io
import json
from pathlib import Path
import subprocess
import tarfile

import pytest
import yaml

import ghcp_ahp_probe as probe
import ghcp_ahp_wire_capture as wire

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name("fixtures") / "ghcp_ahp_wire_observer_fixture.cjs"


def run_fixture(case):
    process = subprocess.run(["node", str(FIXTURE), case], capture_output=True, text=True, timeout=20,
                             env={"PATH": "/usr/bin:/bin:/usr/local/bin"})
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


@pytest.mark.parametrize("case", ["match", "plain", "mismatch_model", "mismatch_effort", "missing", "echo_only",
    "headers_only", "usage_only", "native_only", "conflict", "http_error", "fetch_error", "truncated",
    "model_free", "redaction", "unrelated", "binary_drift", "unsafe_endpoint", "fork"])
def test_passive_node_hooks_forward_exact_bytes_or_refuse_before_fake_transport(case):
    records = run_fixture(case)
    result = wire.analyze(records, synthetic=True)
    assert result["synthetic"] is True
    assert result["admission_allowed"] is result["connection_verified"] is result["gate_ready"] is False
    assert all(row["proven_for_live_gate"] is False for row in result["field_verdicts"].values())
    if case == "model_free":
        assert not result["capi_requests"] and not result["native_requests"]
        assert result["capture_errors"]
    if case in {"match", "plain"}:
        assert all(row["matches_requested"] is True for row in result["field_verdicts"].values())
    if case == "mismatch_model":
        assert result["field_verdicts"]["served_model"]["matches_requested"] is False
    if case == "mismatch_effort":
        assert result["field_verdicts"]["reasoning_effort"]["matches_requested"] is False
    if case in {"missing", "headers_only", "usage_only", "echo_only"}:
        assert all(row["classification"] == "request_only" for row in result["field_verdicts"].values())
        assert all(row["matches_requested"] is None for row in result["field_verdicts"].values())
    if case == "conflict":
        assert result["field_verdicts"]["reasoning_effort"]["conflicting"] is True
    if case == "http_error":
        assert all(row["classification"] == "invalid_or_incomplete_response" and row["matches_requested"] is None
                   for row in result["field_verdicts"].values())
    if case in {"truncated", "echo_only", "fetch_error"}:
        assert "wire_capi_stream_incomplete" in result["capture_errors"]


def test_thread_start_final_thread_event_sdk_context_and_request_web_search_stay_separate():
    result = wire.analyze(run_fixture("match"), synthetic=True)
    initial, updated = result["native_applied_snapshots"]
    assert initial["values"]["reasoning_effort"] == "medium"
    assert initial["scope"] == "thread_start_not_final_turn"
    assert updated["values"]["reasoning_effort"] == "max"
    assert updated["scope"] == "thread_event_not_per_turn_attestation"
    assert updated["values"]["approval"] == "untrusted"
    assert updated["values"]["sandbox"] == "readOnly"
    assert updated["values"]["network"] is False
    assert updated["values"]["web_search"] == updated["values"]["context_window"] == "not_reported"
    assert result["native_context_reports"][0]["context_window"] == 1000000
    request = result["native_requests"][0]
    assert request["source"] == "native_client_request_only"
    assert request["request"]["params"]["config"]["web_search"] == "disabled"
    report, = result["capi_response_reports"]
    assert report["source"] == "capi_upstream_response_body_not_request_echo"
    assert report["independent_attestation"] is False


def test_missing_context_and_false_are_not_coerced_to_zero_or_true():
    records = [{"kind": "ipc_response", "value": {"method": "thread/tokenUsage/updated",
        "params": {"tokenUsage": {"modelContextWindow": False}}}}]
    assert wire.analyze(records, synthetic=True)["native_context_reports"][0]["context_window"] == "not_reported"


def test_disk_config_read_is_never_promoted_to_effective_thread_web_search():
    result = wire.analyze([
        {"kind": "ipc_request", "value": {"id": 9, "method": "config/read"}},
        {"kind": "ipc_response", "value": {"id": 9, "result": {"config": {"web_search": "disabled"}}}},
    ], synthetic=True)
    assert result["native_applied_snapshots"] == []
    assert result["native_base_configuration"][0]["scope"] == "disk_layers_not_thread_override"


@pytest.mark.parametrize("damage", ["missing_request", "missing_headers", "duplicate_request", "duplicate_headers", "duplicate_rpc"])
def test_unbound_or_duplicate_evidence_refuses(damage):
    records = run_fixture("match")
    if damage == "missing_request":
        records = [row for row in records if row["kind"] != "capi_request"]
    if damage == "missing_headers":
        records = [row for row in records if row["kind"] != "capi_headers"]
    if damage.startswith("duplicate"):
        kind = {"duplicate_request": "capi_request", "duplicate_headers": "capi_headers", "duplicate_rpc": "ipc_request"}[damage]
        at = next(i for i, row in enumerate(records) if row["kind"] == kind)
        records.insert(at, copy.deepcopy(records[at]))
    with pytest.raises(probe.Refused, match="wire_"):
        wire.analyze(records, synthetic=True)


def test_synthetic_marker_cannot_be_removed_by_calling_live_analysis():
    assert wire.analyze(run_fixture("match"), synthetic=False)["synthetic"] is True


def test_sse_event_type_mismatch_never_counts_as_response_proof():
    records = run_fixture("match")
    next(row for row in records if row["kind"] == "capi_event")["value"]["type"] = "response.failed"
    result = wire.analyze(records, synthetic=True)
    assert "wire_capi_event_type_mismatch" in result["capture_errors"]
    assert result["field_verdicts"]["served_model"]["matches_requested"] is None


def test_zero_session_probe_allowlist_stops_before_transport():
    class Transport:
        def __init__(self): self.sent = []
        def send(self, value): self.sent.append(value)
        def receive(self):
            return {"jsonrpc": "2.0", "id": len(self.sent), "result": {"protocolVersion": "1.1.0"}}
    transport = Transport()
    rpc = probe.Rpc(transport, "ahp-session:/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa", "file:///fixture", capability_only=True)
    results = probe.exercise_rpc(rpc)
    assert list(results) == ["initialize", "resolveSessionConfig"]
    for method in ("createSession", "subscribe", "turn/start", "disposeSession", "authenticate"):
        with pytest.raises(probe.Refused, match="zero_session_probe_rpc_refused"):
            rpc.request(method, {})
    assert len(transport.sent) == 2


def _archive(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, content in members.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))


@pytest.fixture
def prepared_fixture(tmp_path, monkeypatch):
    root = tmp_path / "prepared"
    downloads = root / "downloads"
    downloads.mkdir(parents=True)
    native_name = "node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/codex/codex"
    native = root / "codex-sdk" / native_name
    native.parent.mkdir(parents=True)
    native.write_bytes(b"not executable - offline fixture only")
    _archive(downloads / "codex_sdk.tgz", {native_name: native.read_bytes()})
    sources = {}
    for relative, anchor in wire.SOURCES.values():
        key = f"vscode-{wire.PIN}/{relative}"
        sources[key] = sources.get(key, b"") + (anchor + "\n").encode()
    _archive(downloads / "source.tgz", sources)
    manifest = probe.load_manifest()
    for kind in ("source", "codex_sdk"):
        manifest["artifacts"][kind]["sha256"] = probe.digest(downloads / (kind + ".tgz"))
    monkeypatch.setattr(wire, "load_manifest", lambda: manifest)
    state = tmp_path / "state"
    state.mkdir()
    return root, state, native, manifest


def test_install_checks_archive_binary_and_pinned_source_without_executing_them(prepared_fixture):
    root, state, native, manifest = prepared_fixture
    env = wire.install(root, state, {"PATH": "/fixture"}, model_free=True, credential="SYNTHETIC_SECRET_XYZ")
    assert env["GHCP_AHP_WIRE_MODE"] == "model-free"
    assert env["GHCP_AHP_WIRE_NATIVE"] == str(native)
    assert env["GHCP_AHP_WIRE_NATIVE_SHA256"] == probe.digest(native)
    assert env["NODE_OPTIONS"].startswith('--require="')
    for file in (state / "wire").iterdir():
        assert "SYNTHETIC_SECRET_XYZ" not in file.read_text()
    sources = json.loads((state / "wire/sources.json").read_text())
    assert len(sources["citations"]) == len(wire.SOURCES)
    assert all(wire.PIN in row["url"] and row["line"] > 0 for row in sources["citations"])


@pytest.mark.parametrize("damage", ["binary", "archive", "source", "node_options", "symlink"])
def test_bootstrap_refuses_identity_or_environment_drift(prepared_fixture, damage):
    root, state, native, manifest = prepared_fixture
    env = {}
    if damage == "binary": native.write_bytes(b"tampered")
    if damage in {"archive", "source"}:
        (root / "downloads" / ("source.tgz" if damage == "source" else "codex_sdk.tgz")).write_bytes(b"tampered")
    if damage == "node_options": env["NODE_OPTIONS"] = "--require=unreviewed"
    if damage == "symlink": (state / "wire").symlink_to(root, target_is_directory=True)
    with pytest.raises(probe.Refused, match="wire_"):
        wire.install(root, state, env, model_free=True)


def test_export_redacts_and_binds_fixture_artifact_without_promoting_it(prepared_fixture, tmp_path):
    root, state, _, _ = prepared_fixture
    wire.install(root, state, {}, model_free=True)
    records = run_fixture("match")
    records[0]["observer_sha256"] = probe.digest(wire.PRELOAD)
    (state / "wire/wire-1.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
    output = tmp_path / "export"
    receipt = wire.export(state, output)
    assert receipt["sha256"] == probe.digest(output / "wire-capture.json")
    value = json.loads((output / "wire-capture.json").read_text())
    assert value["synthetic"] is True and value["admission_allowed"] is False
    assert value["capture_status"] == "captured"


@pytest.mark.parametrize("damage", ["sequence", "duplicate_json", "symlink", "oversize", "observer_hash"])
def test_export_integrity_refusals(prepared_fixture, tmp_path, damage):
    root, state, _, _ = prepared_fixture
    wire.install(root, state, {}, model_free=True)
    file = state / "wire/wire-1.jsonl"
    row = {"sequence": 1, "kind": "observer_installed", "observer_sha256": probe.digest(wire.PRELOAD)}
    if damage == "sequence": row["sequence"] = 2
    if damage == "observer_hash": row["observer_sha256"] = "0" * 64
    if damage == "symlink": file.symlink_to(state / "wire/bootstrap.json")
    elif damage == "duplicate_json": file.write_text('{"sequence":1,"sequence":1}\n')
    elif damage == "oversize":
        with file.open("wb") as stream: stream.truncate(wire.MAX_BYTES + 1)
    else: file.write_text(json.dumps(row) + "\n")
    with pytest.raises(probe.Refused): wire.export(state, tmp_path / "export")
    assert not (tmp_path / "export/wire-capture.json").exists()


def test_push_workflow_is_zero_session_zero_secret_and_exports_both_real_empty_and_synthetic_evidence():
    text = (ROOT / ".github/workflows/ghcp-ahp-model-free-probe.yml").read_text()
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert workflow["on"] == {"push": {"branches": ["leader/ghcp-ahp-probe-20261030"]}}
    assert workflow["jobs"]["probe"]["runs-on"] == "ubuntu-24.04"
    assert "secrets." not in text and "COPILOT_GITHUB_TOKEN" not in text
    assert "--capability-only" in text and "wire-fixture.json" in text
    assert "test_ghcp_ahp_wire_capture.py" in text
    # No extra workflow or model-turn admission is introduced by this collector.
    import ghcp_ahp_connection_transport as transport
    assert transport.CONFIG == {"codex.approvalPolicy": "untrusted", "codex.sandboxMode": "read-only",
        "codex.networkAccessEnabled": False, "codex.webSearchMode": "disabled", "codex.modelReasoningEffort": "max"}
    assert probe.DESIRED_MODEL == {"id": "@provider=vscode-proxy:gpt-5.6-sol",
                                   "config": {"thinkingLevel": "max", "contextSize": 1000000}}
