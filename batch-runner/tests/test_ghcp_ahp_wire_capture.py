"""Offline wire capture tests. Only fake Node transports, never a real host/SDK."""

import copy
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import tarfile
from types import SimpleNamespace

import pytest
import yaml

import ghcp_ahp_probe as probe
import ghcp_ahp_wire_capture as wire

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name("fixtures") / "ghcp_ahp_wire_observer_fixture.cjs"
FORK_FIXTURE = FIXTURE.with_name("ghcp_ahp_agent_fork_fixture.cjs")
POLICY_FIXTURE = FIXTURE.with_name("ghcp_ahp_thread_policy_fixture.cjs")


def run_fixture(case):
    process = subprocess.run(["node", str(FIXTURE), case], capture_output=True, text=True, timeout=20,
                             env={"PATH": "/usr/bin:/bin:/usr/local/bin"})
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


def run_policy_fixture(case):
    result = subprocess.run(["node", str(POLICY_FIXTURE), case], capture_output=True, text=True, timeout=20,
                            env={"PATH": "/usr/bin:/bin:/usr/local/bin"})
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("case", ["valid", "http_response", "http_models", "http_auth", "http_local", "http_other",
    "launch_wrong", "launch_duplicate", "bad_model", "bad_provider", "bad_approval", "bad_permissions",
    "bad_web", "bad_context", "bad_effort", "bad_fallback", "bad_mcp", "bad_reply", "turn", "resume", "fork",
    "exec", "reply", "partial", "batch", "end", "claim_used", "duplicate", "second_process", "incoming_turn",
    "incoming_tool", "foreign_cleanup"])
def test_session_policy_guards_stop_at_fake_native_or_http_boundary(case):
    rows = run_policy_fixture(case)
    assert all(row["synthetic"] is True for row in rows)
    sent = [row["value"]["method"] for row in rows if row["kind"] == "ipc_request"]
    assert set(sent) <= {"thread/start", "thread/unsubscribe"}
    assert sent.count("thread/start") <= 1
    assert not any(row["kind"] == "capi_request" for row in rows)
    assert any(row["kind"] == "blocked" for row in rows) == (case != "valid")


def test_session_policy_cannot_be_enabled_with_a_paid_observer_mode():
    assert run_policy_fixture("mode_mismatch") == []


def test_session_policy_native_reports_never_fill_missing_fields_from_echoes_or_process_config():
    import ghcp_ahp_thread_policy as policy

    rows = run_policy_fixture("valid")
    rows.extend([
        {"kind": "ipc_request", "value": {"id": 99, "method": "config/read"}},
        {"kind": "ipc_response", "value": {"id": 99, "result": {"config": {
            "web_search": "disabled", "model_context_window": 1000000, "model_reasoning_effort": "max"}}}},
        {"kind": "ipc_response", "value": {"method": "thread/tokenUsage/updated", "params": {
            "threadId": "foreign-thread", "tokenUsage": {"modelContextWindow": 1000000}}}},
    ])
    capture = wire.analyze(rows, synthetic=True)
    result = policy.assess(capture, {"createSession": {"result": None},
        "resolveSessionConfig": {"result": {"values": policy.POLICY}}})
    assert result["session_created"] is True and result["native_thread_responses"] == 1
    assert result["observed"]["model"] == "gpt-5.6-sol"
    assert result["observed"]["reasoning_effort"] == "max"
    assert result["observed"]["network"] is False
    for key in ("context_window", "web_search", "served_model"):
        assert result["observed"][key] == "not_reported"
    assert result["admission_allowed"] is False
    assert result["model_turn_start_requests"] == result["model_turn_events"] == result["capi_requests"] == 0


@pytest.mark.parametrize("field", ["model", "model_provider", "reasoning_effort", "context_window", "approval", "sandbox", "network", "web_search", "served_model"])
def test_session_policy_conjunction_requires_every_exact_typed_observation(field):
    import ghcp_ahp_thread_policy as policy

    observed = copy.deepcopy(policy.EXPECTED)
    assert policy.matches_all(observed) is True
    observed[field] = "not_reported"
    assert policy.matches_all(observed) is False
    observed[field] = None
    assert policy.matches_all(observed) is False
    del observed[field]
    assert policy.matches_all(observed) is False


@pytest.mark.parametrize("change", [{"network": 0}, {"context_window": "1000000"}, {"reasoning_effort": "xhigh"},
                                    {"model": "gpt-5.6-sol-fast"}, {"model_provider": "openai"}])
def test_session_policy_no_numeric_boolean_or_effort_alias_admission(change):
    import ghcp_ahp_thread_policy as policy

    assert policy.matches_all({**policy.EXPECTED, **change}) is False


def test_session_policy_native_fallback_or_turn_is_not_hidden_by_matching_resolver_echo():
    import ghcp_ahp_thread_policy as policy

    capture = wire.analyze(run_policy_fixture("valid"), synthetic=True)
    capture["native_applied_snapshots"][0]["values"]["model"] = "gpt-5.6-sol-fast"
    capture["native_requests"].append({"request": {"method": "turn/start"}})
    result = policy.assess(capture, {"resolveSessionConfig": {"result": {"values": policy.POLICY}}})
    assert result["verdicts"]["model"] == "mismatch"
    assert result["model_turn_start_requests"] == 1
    assert result["safety_violation"] is True and result["admission_allowed"] is False


@pytest.mark.parametrize("case", ["valid", "module_js_alias", "module_other", "module_dotdot", "not_array",
    "missing_arg", "extra_arg", "reordered", "logs_foreign", "data_foreign", "telemetry", "logs_ambiguous",
    "logs_symlink", "exec_argv", "exec_path", "runtime_node", "entrypoint", "node_options", "socket_env",
    "socket_foreign", "sdk_root", "module_drift", "node_drift", "parent_drift", "parent_path", "module_symlink",
    "credential_args", "module_shadow"])
def test_exact_pinned_agent_host_fork_contract_at_fake_process_boundary(case):
    result = subprocess.run(["node", str(FORK_FIXTURE), case], capture_output=True, text=True, timeout=20,
                            env={"PATH": "/usr/bin:/bin:/usr/local/bin"})
    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)
    assert all(row["synthetic"] is True for row in rows)
    request, = [row for row in rows if row["kind"] == "agent_fork_attempt"]
    assert (request["mismatches"] == []) == (case == "valid")
    assert len([row for row in rows if row["kind"] == "agent_fork_instrumented"]) == (case == "valid")


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
            entry.mode = 0o755 if content.startswith(b"\x7fELF") or Path(name).name == "codex" else 0o644
            archive.addfile(entry, io.BytesIO(content))


@pytest.fixture
def prepared_fixture(tmp_path, monkeypatch):
    root = tmp_path / "prepared"
    downloads = root / "downloads"
    downloads.mkdir(parents=True)
    inventory = json.loads(FIXTURE.with_name("ghcp_codex_sdk_0163_inventory.json").read_text())
    original = probe.load_manifest()
    assert inventory["archive_sha256"] == original["artifacts"]["codex_sdk"]["sha256"]
    native_name, = inventory["native_members"]
    native = root / "codex-sdk" / native_name
    native.parent.mkdir(parents=True)
    native.write_bytes(b"\x7fELFnot executable - offline fixture only")
    native.chmod(0o755)
    members = {native_name: native.read_bytes()}
    for relative, metadata in {**inventory["packages"], **inventory["layouts"]}.items():
        package = root / "codex-sdk" / relative
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_text(json.dumps(metadata))
        members[relative] = package.read_bytes()
    _archive(downloads / "codex_sdk.tgz", members)
    sources = {}
    for relative, anchor in wire.SOURCES.values():
        key = f"vscode-{wire.PIN}/{relative}"
        sources[key] = sources.get(key, b"") + (anchor + "\n").encode()
    _archive(downloads / "source.tgz", sources)
    server = root / "cli-data/servers" / ("Stable-" + wire.PIN) / "server"
    server_members = {}
    for relative in ("node", "out/bootstrap-fork.js", "out/server-main.js"):
        path = server / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"inert fixture file; never execute " + relative.encode())
        server_members["vscode-server-linux-x64/" + relative] = path.read_bytes()
    _archive(downloads / "server.tgz", server_members)
    manifest = probe.load_manifest()
    for kind in ("source", "codex_sdk", "server"):
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
    contract = json.loads(env["GHCP_AHP_WIRE_FORK_CONTRACT"])
    assert contract["module_request"].endswith("/out/bootstrap-fork")
    assert contract["files"]["module"]["path"] == contract["module_request"] + ".js"
    assert contract["data_path"] == str(state / "server-data/data")
    assert contract["exec_argv"] == [] and contract["telemetry"] == "off"
    assert env["GHCP_AHP_WIRE_FORK_SHA256"] == hashlib.sha256(env["GHCP_AHP_WIRE_FORK_CONTRACT"].encode()).hexdigest()


def test_session_policy_install_binds_the_exact_supported_native_configuration(prepared_fixture):
    import ghcp_ahp_thread_policy as policy

    root, state, _, _ = prepared_fixture
    env = wire.install(root, state, {"VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS": json.dumps(policy.NATIVE_ARGS)},
                       model_free=True, session_policy=True)
    assert env["GHCP_AHP_WIRE_MODE"] == "session-only"
    bootstrap = json.loads((state / "wire/bootstrap.json").read_text())
    assert bootstrap["model_free"] is bootstrap["session_policy"] is True
    assert json.loads(env["VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS"]) == policy.NATIVE_ARGS


def test_authenticated_zero_turn_install_seeds_mask_only_and_keeps_model_free_guards(prepared_fixture, monkeypatch):
    import ghcp_ahp_thread_policy as policy

    for key, value in {"GITHUB_EVENT_NAME": "workflow_dispatch", "GHCP_AUTHENTICATED_ZERO_TURN": "true",
                       "GHCP_PAID_EXECUTION": "false", "GHCP_CONNECTION_ONLY": "false"}.items():
        monkeypatch.setenv(key, value)
    root, state, _, _ = prepared_fixture
    secret = "SYNTHETIC_zero_turn_seed_NOT_REAL"
    env = wire.install(root, state, {"VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS": json.dumps(policy.NATIVE_ARGS)},
                       model_free=True, session_policy=True, credential=secret, authenticated_zero_turn=True)
    assert env["GHCP_AHP_WIRE_MODE"] == "session-only"
    assert json.loads(env["GHCP_AHP_WIRE_SEEDS"]) == [secret]
    assert "COPILOT_GITHUB_TOKEN" not in env
    metadata = json.loads((state / "wire/bootstrap.json").read_text())
    assert metadata["model_free"] is metadata["session_policy"] is metadata["authenticated_zero_turn"] is True
    for path in (state / "wire").glob("*.json"):
        assert secret not in path.read_text()


@pytest.mark.parametrize("case,expected", [("http_auth", "copilot_auth_token_exchange"),
    ("http_models", "capi_models_catalog"), ("http_response", "capi_responses"), ("http_other", "other_http")])
def test_zero_turn_http_denial_records_only_destination_category_never_secrets(case, expected):
    rows = run_policy_fixture(case)
    denied = [row for row in rows if row["kind"] == "blocked"]
    assert len(denied) == 1 and denied[0]["destination"] == expected
    assert denied[0]["forwarded"] is False
    assert not any(row["kind"] == "capi_request" for row in rows)


@pytest.mark.parametrize("damage", ["missing", "wrong_model", "credential", "paid_mode", "flag_type"])
def test_session_policy_install_refuses_unbound_or_authenticated_environment(prepared_fixture, damage):
    import ghcp_ahp_thread_policy as policy

    root, state, _, _ = prepared_fixture
    env = {"VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS": json.dumps(policy.NATIVE_ARGS)}
    if damage == "missing": env.clear()
    if damage == "wrong_model": env["VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS"] = '[]'
    with pytest.raises(wire.Refused, match="wire_(session_policy_environment|mode)_refused"):
        wire.install(root, state, env, model_free=damage != "paid_mode",
                     credential="SYNTHETIC_DO_NOT_USE" if damage == "credential" else "",
                     session_policy="true" if damage == "flag_type" else True)


@pytest.mark.parametrize("damage", ["archive", "missing", "module", "node", "parent", "symlink"])
def test_agent_fork_contract_refuses_server_archive_or_installed_file_drift(prepared_fixture, damage):
    root, state, _, manifest = prepared_fixture
    server = root / "cli-data/servers" / ("Stable-" + wire.PIN) / "server"
    module = server / "out/bootstrap-fork.js"
    if damage == "archive":
        (root / "downloads/server.tgz").write_bytes(b"not the pinned archive")
    elif damage == "missing":
        module.unlink()  # Inert, test-owned text only.
    elif damage == "symlink":
        module.rename(server / "out/foreign.js")
        module.symlink_to(server / "out/foreign.js")
    else:
        relative = {"module": "out/bootstrap-fork.js", "node": "node", "parent": "out/server-main.js"}[damage]
        (server / relative).write_bytes(b"changed inert file")
    with pytest.raises(wire.Refused, match="^wire_(agent_fork_file|server_archive)_"):
        wire.agent_fork_contract(root, state, manifest)


def test_prior_fork_fixture_never_claims_an_unrecorded_request_was_observed():
    fixture = json.loads(FIXTURE.with_name("ghcp_ahp_agent_fork_41941392305.json").read_text())
    assert fixture["provenance"]["fork_request_recorded_in_that_run"] is False
    assert fixture["provenance"]["kind"] == "pinned_source_reconstruction_with_observed_directory_values"
    assert fixture["provenance"]["vscode_commit"] == wire.PIN
    assert fixture["request"]["args"][2].endswith(fixture["observed_logs_directory"])


def test_standalone_probe_and_imported_collector_share_refusal_type():
    # Load definitions under a CLI-like second module name, without executing
    # its __main__ entry or any host process on NAS.
    standalone = runpy.run_path(str(ROOT / "batch-runner/ghcp_ahp_probe.py"), run_name="offline_cli_loading_fixture")
    assert standalone["Refused"] is probe.Refused is wire.Refused


def test_standalone_bootstrap_preserves_original_code_and_all_attempted_paths(tmp_path, monkeypatch):
    standalone = runpy.run_path(str(ROOT / "batch-runner/ghcp_ahp_probe.py"), run_name="offline_cli_loading_fixture")
    run = standalone["run_probe"]
    scope = run.__globals__
    manifest = probe.load_manifest()
    monkeypatch.setitem(scope, "require_runner", lambda: {"synthetic": True})
    monkeypatch.setitem(scope, "require_isolation", lambda *args: {"synthetic": True})
    monkeypatch.setitem(scope, "verify_prepared", lambda *args: ({"artifacts": {}, "binary_sha256": {}, "source_evidence_sha256": "0" * 64}, {}))
    monkeypatch.setitem(scope, "child_environment", lambda *args: {})
    attempts = ["node_modules/@openai/codex-linux-x64/vendor/fixture/bin/codex",
                "node_modules/@openai/codex-linux-x64/alternate/codex"]
    def fake_process(command, *args, **kwargs):
        assert command[1:] in (["--version"], ["agent", "host", "--help"])
        text = (manifest["vscode_version"] + " " + manifest["vscode_commit"] if command[-1] == "--version"
                else "--foreground --new-instance --without-connection-token")
        return SimpleNamespace(finish=lambda: {"exit_code": 0, "stdout": text})
    def refused_install(*args, **kwargs):
        error = wire.Refused("wire_native_binary_not_found")
        error.native_binary_discovery = {"attempted_candidates": [{"path": name, "status": "missing"} for name in attempts],
                                         "search_complete": True}
        raise error
    monkeypatch.setitem(scope, "CapturedProcess", fake_process)
    monkeypatch.setattr(wire, "install", refused_install)
    output = tmp_path / "output"
    assert run(manifest, tmp_path / "prepared", output, "fixture", "fixture", capability_only=True) == 2
    receipt = json.loads((output / "probe.json").read_text())
    assert receipt["reason_codes"] == ["wire_native_binary_not_found"]
    assert [row["path"] for row in receipt["native_binary_discovery"]["attempted_candidates"]] == attempts
    assert receipt["session_create_requests"] == receipt["model_calls"] == 0


@pytest.mark.parametrize("code", ["wire_native_binary_not_found", "wire_sdk_metadata_drift", "wire_sdk_archive_drift"])
def test_standalone_main_exports_original_refusal_code(tmp_path, monkeypatch, code):
    standalone = runpy.run_path(str(ROOT / "batch-runner/ghcp_ahp_probe.py"), run_name="offline_cli_loading_fixture")
    main = standalone["main"]
    scope = main.__globals__
    monkeypatch.setitem(scope, "require_runner", lambda: {"synthetic": True})
    def refused(*args, **kwargs):
        error = wire.Refused(code)
        error.native_binary_discovery = {"attempted_candidates": [], "search_complete": False}
        raise error
    monkeypatch.setitem(scope, "run_probe", refused)
    output = tmp_path / "output"
    assert main(["probe", "--prepared", str(tmp_path / "prepared"), "--evidence", str(output), "--capability-only"]) == 2
    receipt = json.loads((output / "failure-probe.json").read_text())
    assert receipt["reason_code"] == code
    assert receipt["native_binary_discovery"]["attempted_candidates"] == []


def test_standalone_unknown_exception_never_exports_its_message(tmp_path, monkeypatch):
    standalone = runpy.run_path(str(ROOT / "batch-runner/ghcp_ahp_probe.py"), run_name="offline_cli_loading_fixture")
    main = standalone["main"]
    monkeypatch.setitem(main.__globals__, "require_runner", lambda: {"synthetic": True})
    def refused(*args, **kwargs):
        raise RuntimeError("SYNTHETIC_PRIVATE_ERROR_DO_NOT_EXPORT")
    monkeypatch.setitem(main.__globals__, "run_probe", refused)
    output = tmp_path / "output"
    assert main(["probe", "--prepared", str(tmp_path / "prepared"), "--evidence", str(output)]) == 2
    text = (output / "failure-probe.json").read_text()
    assert "SYNTHETIC_PRIVATE" not in text
    assert json.loads(text)["reason_code"] == "RuntimeError"


def _repack_sdk(root, manifest):
    sdk = root / "codex-sdk"
    members = {path.relative_to(sdk).as_posix(): path.read_bytes()
               for path in sdk.rglob("*") if path.is_file() and not path.is_symlink()}
    archive = root / "downloads/codex_sdk.tgz"
    _archive(archive, members)
    manifest["artifacts"]["codex_sdk"]["sha256"] = probe.digest(archive)


@pytest.mark.parametrize("relative", ["native/bin/codex", "alternate/deep/codex", "vendor/old-layout/codex/codex"])
def test_discovery_uses_package_inventory_not_a_vendor_suffix(prepared_fixture, relative):
    root, _, native, manifest = prepared_fixture
    destination = root / "codex-sdk/node_modules/@openai/codex-linux-x64" / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    native.rename(destination)
    layout = next((root / "codex-sdk").rglob("codex-package.json"))
    # Move the self-described layout alongside its entrypoint. No test creates
    # or executes a real SDK. Both paths remain inside the declared package.
    value = json.loads(layout.read_text())
    layout.unlink()
    value["entrypoint"] = destination.name
    (destination.parent / "codex-package.json").write_text(json.dumps(value))
    _repack_sdk(root, manifest)
    found, sha, report = wire.discover_native_binary(root, manifest)
    assert found == destination and sha == probe.digest(destination)
    assert report["selected"] == destination.relative_to(root / "codex-sdk").as_posix()
    assert report["search_complete"] is True


def test_discovery_honors_verified_bin_declaration_without_assuming_the_basename(prepared_fixture):
    root, _, native, manifest = prepared_fixture
    package_root = root / "codex-sdk/node_modules/@openai/codex-linux-x64"
    destination = package_root / "dist/native-runtime"
    destination.parent.mkdir()
    native.rename(destination)
    next((root / "codex-sdk").rglob("codex-package.json")).unlink()
    package = package_root / "package.json"
    value = json.loads(package.read_text())
    value["bin"] = {"codex": "dist/native-runtime"}
    package.write_text(json.dumps(value))
    _repack_sdk(root, manifest)
    found, _, report = wire.discover_native_binary(root, manifest)
    assert found == destination
    assert report["attempted_candidates"][0]["sources"] == ["package_bin"]


def test_missing_installed_binary_reports_archive_candidate(prepared_fixture):
    root, _, native, manifest = prepared_fixture
    relative = native.relative_to(root / "codex-sdk").as_posix()
    native.unlink()  # Inert, test-owned ELF-prefixed bytes only.
    with pytest.raises(wire.Refused, match="^wire_native_binary_not_found$") as error:
        wire.discover_native_binary(root, manifest)
    report = error.value.native_binary_discovery
    assert report["attempted_candidates"] == [{"path": relative, "sources": ["native_package_entrypoint", "archive_inventory"], "status": "missing"}]
    assert report["search_complete"] is True and report["selected"] is None


def test_all_declared_missing_candidates_are_reported(prepared_fixture):
    root, _, native, manifest = prepared_fixture
    native.unlink()
    next((root / "codex-sdk").rglob("codex-package.json")).unlink()
    package = root / "codex-sdk/node_modules/@openai/codex-linux-x64/package.json"
    value = json.loads(package.read_text())
    value["bin"] = {"codex": "first/codex", "codex-alternate": "second/codex"}
    package.write_text(json.dumps(value))
    _repack_sdk(root, manifest)
    with pytest.raises(wire.Refused, match="^wire_native_binary_not_found$") as error:
        wire.discover_native_binary(root, manifest)
    attempts = error.value.native_binary_discovery["attempted_candidates"]
    assert [row["path"].split("codex-linux-x64/")[-1] for row in attempts] == ["first/codex", "second/codex"]
    assert all(row["status"] == "missing" for row in attempts)


def test_multiple_verified_native_candidates_refuse_instead_of_choosing_one(prepared_fixture):
    root, _, native, manifest = prepared_fixture
    other = native.parent.parent / "alternate/codex"
    other.parent.mkdir()
    other.write_bytes(native.read_bytes())
    other.chmod(0o755)
    _repack_sdk(root, manifest)
    with pytest.raises(wire.Refused, match="^wire_native_binary_ambiguous$") as error:
        wire.discover_native_binary(root, manifest)
    assert len(error.value.native_binary_discovery["attempted_candidates"]) == 2
    assert all(row["status"] == "verified_native" for row in error.value.native_binary_discovery["attempted_candidates"])


@pytest.mark.parametrize("damage", ["metadata", "metadata_identity", "wrong_cpu", "non_elf", "non_executable", "unsigned_extra", "symlink"])
def test_discovery_never_weakens_identity_platform_or_native_checks(prepared_fixture, damage):
    root, _, native, manifest = prepared_fixture
    package = root / "codex-sdk/node_modules/@openai/codex-linux-x64/package.json"
    code = "wire_native_binary_not_found"
    if damage in {"metadata", "metadata_identity", "wrong_cpu"}:
        value = json.loads(package.read_text())
        value["cpu" if damage == "wrong_cpu" else "version"] = ["arm64"] if damage == "wrong_cpu" else "0.999.0-linux-x64"
        package.write_text(json.dumps(value))
        if damage != "metadata": _repack_sdk(root, manifest)
        if damage == "metadata": code = "wire_sdk_metadata_drift"
        if damage == "metadata_identity": code = "wire_sdk_dependency_identity_refused"
    if damage == "non_elf":
        native.write_bytes(b"not a native executable")
        _repack_sdk(root, manifest)
    if damage == "non_executable": native.chmod(0o600)
    if damage == "unsigned_extra":
        other = native.parent.parent / "unsigned/codex"
        other.parent.mkdir()
        other.write_bytes(native.read_bytes())
        other.chmod(0o755)
        code = "wire_native_binary_drift"
    if damage == "symlink":
        other = native.parent / "other"
        native.rename(other)
        native.symlink_to(other)
        code = "wire_native_binary_drift"
    with pytest.raises(wire.Refused, match="^" + code + "$") as error:
        wire.discover_native_binary(root, manifest)
    assert error.value.native_binary_discovery["selected"] is None


def test_real_pinned_binary_size_is_bound_by_archive_not_compressed_download_limit():
    inventory = json.loads(FIXTURE.with_name("ghcp_codex_sdk_0163_inventory.json").read_text())
    size, = inventory["native_member_sizes"].values()
    assert size == 296865480 and size > 256 * 1024**2
    assert wire._native_size_matches(size, size)
    assert not wire._native_size_matches(size, size + 1)
    assert not wire._native_size_matches(size, size - 1)
    assert wire.MAX_ARCHIVE_EXPANSION_BYTES == probe.MAX_ARCHIVE_EXPANSION_BYTES == 2 * 1024**3
    assert not wire._native_size_matches(0, 0)
    assert not wire._native_size_matches(probe.MAX_ARCHIVE_EXPANSION_BYTES + 1, probe.MAX_ARCHIVE_EXPANSION_BYTES + 1)


def test_declared_native_entrypoint_cannot_be_substituted_by_another_inventory_match(prepared_fixture):
    root, _, native, manifest = prepared_fixture
    other = native.parent / "moved/codex"
    other.parent.mkdir()
    native.rename(other)
    _repack_sdk(root, manifest)
    with pytest.raises(wire.Refused, match="^wire_native_entrypoint_missing$") as error:
        wire.discover_native_binary(root, manifest)
    assert len(error.value.native_binary_discovery["attempted_candidates"]) == 2
    assert error.value.native_binary_discovery["selected"] is None


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


def test_push_workflow_is_bounded_session_zero_secret_and_exports_real_and_synthetic_evidence():
    text = (ROOT / ".github/workflows/ghcp-ahp-model-free-probe.yml").read_text()
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert workflow["on"] == {"push": {"branches": ["leader/ghcp-ahp-probe-20261030"]}}
    assert workflow["jobs"]["probe"]["runs-on"] == "ubuntu-24.04"
    assert "secrets." not in text and "COPILOT_GITHUB_TOKEN" not in text
    assert "--session-policy-probe" in text and "wire-fixture.json" in text
    assert "test_ghcp_ahp_wire_capture.py" in text
    # No extra workflow or model-turn admission is introduced by this collector.
    import ghcp_ahp_connection_transport as transport
    assert transport.CONFIG == {"codex.approvalPolicy": "untrusted", "codex.sandboxMode": "read-only",
        "codex.networkAccessEnabled": False, "codex.webSearchMode": "disabled", "codex.modelReasoningEffort": "max"}
    assert probe.DESIRED_MODEL == {"id": "@provider=vscode-proxy:gpt-5.6-sol",
                                   "config": {"thinkingLevel": "max", "contextSize": 1000000}}
