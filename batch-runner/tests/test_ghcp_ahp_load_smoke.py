"""Offline data/guard fixtures only. Never load the real GHCP build on NAS."""

import copy
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tarfile

import pytest

import ghcp_ahp_bundle_manifest as bundle
import ghcp_ahp_load_smoke as smoke
import ghcp_ahp_patched_runtime as runtime
from ghcp_ahp_errors import Refused
from tests.test_ghcp_ahp_patched_runtime import BODY, bind, encode, fixture_tree, node_copy, sha
from tests.test_ghcp_ahp_patchset import bundle_fixture
from tests.test_ghcp_ahp_patched_runtime_rejections import chain as synthetic_chain

IDENTITY = {"github_run_id": "12345", "github_run_attempt": "1", "github_sha": "a" * 40}


def test_real_bundle_baseline_and_public_activation_lock_remain_exact():
    assert smoke.BASELINE_SHA256 == "5006baa5e4e032cf28f47de802b386ebed6b2c3616943943b3cfa06fce4a7c43"
    assert smoke.BASELINE_BYTES == 5193139
    assert runtime.PATCH_SHA256 == "6d869d65ec18a5aba93528f27e1277ac37b48a7da439065911e11e6c71f33856"
    with pytest.raises(Refused, match="^patched_runtime_activation_pending_owner$"):
        runtime.require_activation()


def test_cli_refuses_nas_before_payload_work_or_process_launch(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(smoke, "run_smoke", lambda *args: pytest.fail("must not launch a smoke on NAS"))
    with pytest.raises(Refused, match="execution_environment_refused"):
        smoke.main(["run", "--prepared", str(tmp_path), "--evidence", str(tmp_path / "evidence"),
                    "--outside-netns", "net:[1]", "--outside-pidns", "pid:[1]"])


def test_empty_smoke_profile_seeds_only_the_pinned_copilot_payload_marker(tmp_path):
    value = smoke.seed_smoke_profile(tmp_path)
    assert smoke.PROFILE_DATABASE == "User/globalStorage/agent-host.db"
    assert smoke.PROFILE_MARKER == "sessionsV2PayloadBackfilled:copilotcli:v2"
    assert value["metadata"] == [[smoke.PROFILE_MARKER, "true"]]
    assert value["initial_user_version"] == 0 and value["initial_tables"] == ["metadata"]
    assert value["synthetic"] is True and value["execution_allowed"] is False
    assert value["evidence_kind"] == "synthetic_empty_profile_not_measured_migration"
    assert value["database_sha256"] == sha((tmp_path / smoke.PROFILE_DATABASE).read_bytes())
    assert smoke.profile_seed_receipt(tmp_path) == value


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "existing_profile"])
def test_profile_seed_refuses_reuse_or_nonempty_user_data_without_modifying_it(tmp_path, kind):
    data = tmp_path / "data"
    data.mkdir()
    if kind == "file": (data / "owned.txt").write_text("leave unchanged")
    elif kind == "directory": (data / "existing").mkdir()
    elif kind == "symlink":
        (tmp_path / "elsewhere").mkdir()
        (data / "existing").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    else: smoke.seed_smoke_profile(data)
    before = sorted((str(path.relative_to(data)), path.read_bytes()) for path in data.rglob("*") if path.is_file())
    with pytest.raises(Refused, match="^load_smoke_profile_not_empty$"):
        smoke.seed_smoke_profile(data)
    assert before == sorted((str(path.relative_to(data)), path.read_bytes()) for path in data.rglob("*") if path.is_file())


@pytest.mark.parametrize("sql", ["DELETE FROM metadata", "UPDATE metadata SET value='false'",
    "UPDATE metadata SET key='sessionsV2PayloadBackfilled:copilotcli:v1'", "CREATE TABLE sessions (id TEXT)", "PRAGMA user_version=1"])
def test_profile_readback_rejects_missing_wrong_or_nonempty_seed(tmp_path, sql):
    smoke.seed_smoke_profile(tmp_path)
    database = sqlite3.connect(tmp_path / smoke.PROFILE_DATABASE)
    try:
        database.execute(sql)
        database.commit()
    finally:
        database.close()
    with pytest.raises(Refused, match="^load_smoke_profile_receipt_refused$"):
        smoke.profile_seed_receipt(tmp_path)


@pytest.fixture
def payload_fixture(bundle_fixture, tmp_path, monkeypatch):
    """Tiny fake vendor archive; its node member is NOT executable code."""
    source, outputs, inputs_path, receipt_path, manifest_path = bundle_fixture
    archive_path = tmp_path / "server.tgz"
    members = {"node": b"not executable: synthetic node identity", "package.json": b'{"type":"module"}',
               "product.json": encode({"commit": runtime.PIN}),
               "out/bootstrap-fork.js": b"synthetic bootstrap, never executed", "out/server-main.js": b"synthetic parent",
               runtime.RUNTIME_RELATIVE: b"synthetic original vendor bundle"}
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, data in members.items():
            item = tarfile.TarInfo("vscode-server-linux-x64/" + name)
            item.size, item.mode = len(data), 0o755 if name == "node" else 0o644
            archive.addfile(item, io.BytesIO(data))
    manifest = json.loads(runtime.MANIFEST.read_text())
    manifest["artifacts"]["server"]["sha256"] = sha(archive_path.read_bytes())
    runtime.MANIFEST.write_bytes(encode(manifest))
    monkeypatch.setattr(runtime, "MANIFEST_SHA256", sha(runtime.MANIFEST.read_bytes()))
    inputs = json.loads(inputs_path.read_text())
    inputs["server_archive_sha256"] = manifest["artifacts"]["server"]["sha256"]
    inputs_path.write_bytes(encode(inputs) + b"\n")
    bundle.record_manifest(*bundle_fixture)
    assert sha(BODY) != smoke.BASELINE_SHA256  # no real GHCP artifact in this local fixture
    monkeypatch.setattr(smoke, "BASELINE_SHA256", sha(BODY))
    monkeypatch.setattr(smoke, "BASELINE_BYTES", len(BODY))
    transfer = tmp_path / "transfer"
    smoke.pack_payload(outputs / bundle.ENTRY, manifest_path, archive_path, transfer, IDENTITY)
    return transfer, tmp_path / "consumer"


def test_same_run_payload_is_staged_in_two_separate_verified_copies_without_execution(payload_fixture):
    transfer, output = payload_fixture
    value = smoke.prepare_payload(transfer, output, IDENTITY)
    assert value["transfer"]["identity"] == IDENTITY and value["execution_allowed"] is False
    relative = Path("cli-data/servers") / ("Stable-" + runtime.PIN) / "server" / runtime.RUNTIME_RELATIVE
    assert (output / "base" / relative).read_bytes() != BODY
    assert (output / "positive" / relative).read_bytes() == (output / "negative" / relative).read_bytes() == BODY
    assert not list(output.rglob("load-*.json"))


def test_profile_seed_is_only_in_load_cases_not_shared_bundle_or_readiness(payload_fixture):
    transfer, output = payload_fixture
    smoke.prepare_payload(transfer, output, IDENTITY)
    assert not list(output.rglob("agent-host.db"))
    receipt = output / "build-receipt.json"
    state, _, config = smoke.case_config(output, "positive", receipt, sha(receipt.read_bytes()))
    assert list(output.rglob("agent-host.db")) == [state / "data" / smoke.PROFILE_DATABASE]
    assert config["data"] == str(state / "data")
    assert config["profile_seed"] == smoke.profile_seed_receipt(state / "data")


@pytest.mark.parametrize("field", ["github_run_id", "github_run_attempt", "github_sha"])
def test_a_different_run_attempt_or_head_cannot_supply_the_payload(payload_fixture, field):
    transfer, output = payload_fixture
    identity = {**IDENTITY, field: "2" if field != "github_sha" else "b" * 40}
    with pytest.raises(Refused, match="^load_smoke_same_run_transfer_refused$"):
        smoke.prepare_payload(transfer, output, identity)
    assert not output.exists()


@pytest.mark.parametrize("field,value", [("patch_sha256", "0" * 64), ("bundle_sha256", "0" * 64), ("bundle_bytes", 1),
    ("synthetic", False), ("model_free", False), ("execution_allowed", True), ("payload_bytes", True), ("payload_sha256", "bad")])
def test_transfer_contract_is_fail_closed(payload_fixture, field, value):
    transfer, output = payload_fixture
    data = json.loads((transfer / "transfer.json").read_text())
    data[field] = value
    (transfer / "transfer.json").write_bytes(encode(data))
    with pytest.raises(Refused, match="^load_smoke_same_run_transfer_refused$"):
        smoke.prepare_payload(transfer, output, IDENTITY)
    assert not output.exists()


def test_payload_byte_corruption_is_rejected_before_extraction(payload_fixture):
    transfer, output = payload_fixture
    path = transfer / "payload.tar"
    path.write_bytes(smoke.one_byte_mutant(path.read_bytes()))
    with pytest.raises(Refused, match="^load_smoke_payload_hash_refused$"):
        smoke.prepare_payload(transfer, output, IDENTITY)
    assert not output.exists()


@pytest.mark.parametrize("damage", ["traversal", "symlink", "duplicate", "bundle_corruption"])
def test_even_a_rehashed_payload_cannot_add_special_members_or_change_the_bundle(payload_fixture, damage):
    transfer, output = payload_fixture
    path = transfer / "payload.tar"
    with tarfile.open(path, "r:") as archive:
        data = {item.name: archive.extractfile(item).read() for item in archive.getmembers()}
    with tarfile.open(path, "w") as archive:
        for name, raw in data.items():
            item = tarfile.TarInfo(name)
            if name == "agentHostMain.js":
                if damage == "traversal": item.name = "../escape.js"
                elif damage == "symlink": item.type, item.linkname = tarfile.SYMTYPE, "/tmp/outside"
                elif damage == "bundle_corruption": raw = smoke.one_byte_mutant(raw)
            item.size = len(raw) if item.isfile() else 0
            archive.addfile(item, io.BytesIO(raw) if item.isfile() else None)
            if damage == "duplicate" and name == "agentHostMain.js": archive.addfile(item, io.BytesIO(raw))
    value = json.loads((transfer / "transfer.json").read_text())
    value["payload_sha256"], value["payload_bytes"] = sha(path.read_bytes()), path.stat().st_size
    (transfer / "transfer.json").write_bytes(encode(value))
    with pytest.raises(Refused, match="load_smoke_(payload_members|transfer_member|received_bundle)_refused"):
        smoke.prepare_payload(transfer, output, IDENTITY)
    assert not (output.parent / "escape.js").exists()


@pytest.mark.parametrize("data", [b"a", b"\x00abc", b"\xff\x00xyz", BODY])
def test_negative_probe_changes_exactly_one_byte_without_changing_size(data):
    changed = smoke.one_byte_mutant(data)
    assert len(changed) == len(data)
    assert sum(a != b for a, b in zip(data, changed, strict=True)) == 1
    assert sha(changed) != sha(data)


def test_empty_negative_source_cannot_be_claimed_as_a_mutation():
    with pytest.raises(Refused, match="^load_smoke_empty_mutant_source$"):
        smoke.one_byte_mutant(b"")


@pytest.mark.parametrize("kind", ["positive", "negative", "auth_stop"])
def test_driver_uses_the_real_loader_but_only_an_inert_local_module(tmp_path, node_copy, kind):
    tree = fixture_tree(tmp_path, node_copy)
    state, server = tree["state"], tree["node"].parent
    for name in ("logs", "data", "tmp"):
        (state / name).mkdir()
    smoke.seed_smoke_profile(state / "data")
    bootstrap = server / "out/bootstrap-fork.js"
    body = 'await import("./vs/platform/agentHost/node/agentHostMain.js");\n'
    if kind == "auth_stop":
        body += 'console.error("Authentication is required (-32007), connectionToken=fake-fixture-secret"); process.exit(1);\n'
    else:
        body += 'console.log("Agent host server listening on inert-fixture"); setInterval(() => {}, 1000);\n'
    bootstrap.write_text(body)
    environment = bind(tree)
    config_path = state / "config.json"
    config = {"environment": environment, "config_path": str(config_path), "bootstrap": str(bootstrap),
              "bootstrap_sha256": sha(bootstrap.read_bytes()), "logs": str(state / "logs"), "data": str(state / "data"),
              "socket": str(state / "tmp/socket"), "process_report": str(state / "process.json")}
    config_path.write_bytes(encode(config))
    if kind == "negative": tree["bundle"].write_bytes(smoke.one_byte_mutant(BODY))
    result = subprocess.run([str(tree["node"]), str(smoke.DRIVER), str(config_path)],
                            cwd=server, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    process = json.loads((state / "process.json").read_text())
    assert process["ipc_messages_sent"] == process["sessions_created"] == process["turns_sent"] == 0
    if kind == "positive":
        smoke.check_process(process)
        assert process["readiness_observed"] is True
        value = runtime.collect(state, None, process["records"])
        assert value["loaded_bundle_sha256"] == sha(BODY) != smoke.BASELINE_SHA256
        assert value["runtime_evidence_synthetic"] is True and value["execution_allowed"] is False
    elif kind == "negative":
        smoke.check_process(process, negative=True)
        assert not list((state / "wire/patched-runtime").glob("load-*.json"))
    else:
        assert process["authentication_required"] is True
        assert "fake-fixture-secret" not in (state / "process.json").read_text()
        with pytest.raises(Refused, match="^load_smoke_import_not_confirmed$"):
            smoke.check_process(process)


@pytest.mark.parametrize("force_migration", [False, True])
def test_seeded_catalog_does_not_spawn_but_forced_migration_is_still_refused(tmp_path, node_copy, force_migration):
    """Use pinned SQL semantics in an inert module, never the vendor bundle/SDK."""
    tree = fixture_tree(tmp_path, node_copy)
    state, server = tree["state"], tree["node"].parent
    for name in ("logs", "data", "tmp"):
        (state / name).mkdir()
    smoke.seed_smoke_profile(state / "data")
    bootstrap = server / "out/bootstrap-fork.js"
    bootstrap.write_text(
        'await import("./vs/platform/agentHost/node/agentHostMain.js");\n'
        'const {DatabaseSync} = await import("node:sqlite");\n'
        'const path = await import("node:path"); const cp = await import("node:child_process");\n'
        'const data = process.argv[process.argv.indexOf("--user-data-dir") + 1];\n'
        f'const db = new DatabaseSync(path.join(data, {json.dumps(smoke.PROFILE_DATABASE)}));\n'
        f'const marker = {json.dumps(smoke.PROFILE_MARKER)};\n'
        + ('db.prepare("DELETE FROM metadata WHERE key = ?").run(marker);\n' if force_migration else '')
        + 'const row = db.prepare("SELECT value FROM metadata WHERE key = ?").get(marker); db.close();\n'
        'if (row?.value !== "true") { try { cp.spawn("/inert/copilot-runtime", ["--headless", "--stdio", "--no-auto-login"]); } catch {} }\n'
        'console.log("inert catalog checked"); setInterval(() => {}, 1000);\n'
    )
    environment = bind(tree)
    config_path = state / "config.json"
    config = {"environment": environment, "config_path": str(config_path), "bootstrap": str(bootstrap),
              "bootstrap_sha256": sha(bootstrap.read_bytes()), "logs": str(state / "logs"), "data": str(state / "data"),
              "socket": str(state / "tmp/socket"), "process_report": str(state / "process.json")}
    config_path.write_bytes(encode(config))
    completed = subprocess.run([str(tree["node"]), str(smoke.DRIVER), str(config_path)], cwd=server,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    process = json.loads((state / "process.json").read_text())
    assert process["import_resolved"] is True and process["observation_ms"] == 1000
    assert process["ipc_messages_sent"] == process["sessions_created"] == process["turns_sent"] == 0
    assert runtime.collect(state, None, process["records"])["loaded_bundle_sha256"] == sha(BODY) != smoke.BASELINE_SHA256
    blocked = [row for row in process["events"] if row["kind"] == "boundary_refused"]
    if force_migration:
        assert len(blocked) == 1 and blocked[0]["method"] == "spawn" and blocked[0]["executable"] == "/inert/copilot-runtime"
        with pytest.raises(Refused, match="^load_smoke_process_boundary_refused$"):
            smoke.check_process(process)
    else:
        assert blocked == []
        smoke.check_process(process)


@pytest.mark.parametrize("operation", ["fetch", "http_request", "http_get", "https_request", "tls", "socket", "tcp_listen", "spawn"])
def test_smoke_network_and_child_process_guards_refuse_before_effects(operation, node_copy):
    calls = {"fetch": "globalThis.fetch('http://127.0.0.1:9/')", "http_request": "require('node:http').request('http://127.0.0.1:9/')",
             "http_get": "require('node:http').get('http://127.0.0.1:9/')", "https_request": "require('node:https').request('https://127.0.0.1:9/')",
             "tls": "require('node:tls').connect(9)", "socket": "new (require('node:net').Socket)().connect(9)",
             "tcp_listen": "require('node:net').createServer().listen(0)", "spawn": "require('node:child_process').spawn('never-run')"}
    script = f"const events=[]; require({json.dumps(str(smoke.DRIVER))}).boundaryGuards(row=>events.push(row)); "
    script += f"try {{ {calls[operation]}; process.exitCode=3; }} catch(error) {{ console.log(JSON.stringify({{events, reason:error.message}})); }}"
    result = subprocess.run([str(node_copy), "-e", script], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert len(value["events"]) == 1 and value["events"][0]["kind"] == "boundary_refused"
    assert value["reason"].startswith("load_smoke_") and value["reason"].endswith("_refused")


@pytest.mark.parametrize("method", ["spawn", "spawnSync", "fork", "exec", "execSync", "execFile", "execFileSync"])
def test_child_process_refusal_retains_sanitized_method_and_callsite_without_running_it(method, node_copy):
    script = f"const rows=[]; require({json.dumps(str(smoke.DRIVER))}).boundaryGuards(row=>rows.push(row)); "
    script += f"try {{ require('node:child_process')[{json.dumps(method)}]('never-execute-fixture', ['--token', 'fixture-private-value']); }} "
    script += "catch(error) { console.log(JSON.stringify({rows, reason:error.message})); }"
    process = subprocess.run([str(node_copy), "-e", script], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=5)
    assert process.returncode == 0, process.stderr
    value = json.loads(process.stdout)
    assert value["reason"] == "load_smoke_child_process_refused"
    assert len(value["rows"]) == 1
    row = value["rows"][0]
    assert row["kind"] == "boundary_refused" and row["method"] == method and row["executable"] == "never-execute-fixture"
    assert row["args"] == ["--token", "[REDACTED]"] and len(row["stack"]) >= 2
    assert "fixture-private-value" not in process.stdout


def process_value():
    return {"schema": "ghcp-load-smoke-process-v1", "synthetic": True, "model_free": True, "execution_allowed": False,
            "timed_out": False, "launch_error": None, "parent_pid": 2, "child_pid": 3, "ipc_messages_sent": 0,
            "sessions_created": 0, "turns_sent": 0, "import_resolved": True, "stop_requested": True,
            "signal": "SIGTERM", "exit_code": None, "events": [],
            "records": [{"kind": "patched_runtime_child", "parent_pid": 2, "child_pid": 3}]}


@pytest.mark.parametrize("field,value", [("synthetic", False), ("model_free", False), ("execution_allowed", True),
    ("timed_out", True), ("ipc_messages_sent", 1), ("sessions_created", 1), ("turns_sent", 1),
    ("import_resolved", False), ("stop_requested", False), ("exit_code", 1), ("child_pid", 4)])
def test_bad_process_outcomes_cannot_be_labeled_success(field, value):
    data = process_value()
    data[field] = value
    with pytest.raises(Refused):
        smoke.check_process(data)


@pytest.fixture
def smoke_receipt(bundle_fixture, tmp_path, monkeypatch):
    """Synthetic consumer data; real Node source loading is tested by the inert driver above."""
    chain_root = tmp_path / "chain"
    chain_root.mkdir()
    _, evidence, provenance, records = synthetic_chain.__wrapped__(chain_root)
    manifest = bundle.record_manifest(*bundle_fixture)
    manifest_raw = encode(manifest) + b"\n"
    monkeypatch.setattr(smoke, "BASELINE_SHA256", sha(BODY))
    monkeypatch.setattr(smoke, "BASELINE_BYTES", len(BODY))
    transfer = {"schema": "ghcp-load-smoke-transfer-v1", "identity": IDENTITY, "upstream_commit": runtime.PIN,
                "patch_sha256": runtime.PATCH_SHA256, "bundle_sha256": sha(BODY), "bundle_bytes": len(BODY),
                "server_archive_sha256": bundle.base_manifest()["artifacts"]["server"]["sha256"],
                "bundle_manifest_sha256": sha(manifest_raw), "build_receipt_sha256": manifest["build_receipt_sha256"],
                "payload_sha256": "f" * 64, "payload_bytes": 1, "synthetic": True, "model_free": True, "execution_allowed": False}
    positive = process_value()
    positive.update(parent_pid=records[0]["parent_pid"], child_pid=records[0]["child_pid"], records=records)
    negative = process_value()
    negative.update(import_resolved=False, exit_code=2, signal=None, stop_requested=False,
                    events=[{"kind": "import_error", "message": "patched_runtime_hash_mismatch"}])
    profiles = {}
    for name in ("positive", "negative"):
        data = tmp_path / (name + "-data")
        data.mkdir()
        profiles[name] = smoke.seed_smoke_profile(data)
    result = {"schema": "ghcp-real-bundle-load-smoke-v1", "synthetic": True, "model_free": True,
              "execution_allowed": False, "admission_allowed": False, "authentication_supplied": False,
              "model_calls": 0, "sessions_created": 0, "turns_sent": 0, "negative_load_evidence_files": 0,
              "patch_sha256": runtime.PATCH_SHA256, "expected_bundle_sha256": sha(BODY), "identity": IDENTITY,
              "driver_sha256": sha(smoke.DRIVER.read_bytes()), "bundle_manifest_sha256": sha(manifest_raw),
              "isolation": {"interfaces": ["lo"], "pid_one": True, "unprivileged": True, "no_new_privileges": True,
                            "network_namespace": "net:[2]", "outside_network_namespace": "net:[1]",
                            "pid_namespace": "pid:[2]", "outside_pid_namespace": "pid:[1]"},
              "cases": {"positive": positive, "negative": negative}, "runtime_provenance": provenance, "profile_seeds": profiles,
              "mutation": {"offset": 0, "changed_bytes": 1, "bytes": len(BODY), "original_sha256": sha(BODY),
                           "mutant_sha256": sha(smoke.one_byte_mutant(BODY))}, "status": "success", "failures": []}
    (evidence / "load-smoke.json").write_bytes(encode(result))
    (evidence / "server-bundle-manifest.json").write_bytes(manifest_raw)
    (evidence / "transfer.json").write_bytes(encode(transfer))
    return evidence


def test_smoke_receipt_requires_existing_loader_artifacts_and_full_same_run_chain(smoke_receipt):
    result = smoke.verify_smoke_evidence(smoke_receipt, IDENTITY)
    assert result["runtime_provenance"]["loaded_bundle_sha256"] == sha(BODY)
    assert result["synthetic"] is True and result["execution_allowed"] is False


@pytest.mark.parametrize("damage", ["synthetic", "execution", "model_calls", "same_namespace", "wrong_head",
    "mutation_count", "negative_proof", "load_hash", "missing_proof", "negative_not_refused", "schema", "unknown_field",
    "missing_marker", "extra_case", "mutation_bool", "mutation_offset_bool", "mutation_size_bool", "model_calls_bool",
    "profile_missing", "profile_not_synthetic", "profile_claimed_measured", "profile_wrong_marker"])
def test_smoke_receipt_cannot_hide_failed_or_unmeasured_work(smoke_receipt, damage):
    target = smoke_receipt / "load-smoke.json"
    value = json.loads(target.read_text())
    if damage == "synthetic": value["synthetic"] = False
    elif damage == "execution": value["execution_allowed"] = True
    elif damage == "model_calls": value["model_calls"] = 1
    elif damage == "same_namespace": value["isolation"]["network_namespace"] = "net:[1]"
    elif damage == "wrong_head": value["identity"]["github_sha"] = "b" * 40
    elif damage == "mutation_count": value["mutation"]["changed_bytes"] = 2
    elif damage == "negative_proof": value["negative_load_evidence_files"] = 1
    elif damage == "load_hash": value["runtime_provenance"]["loaded_bundle_sha256"] = "0" * 64
    elif damage == "negative_not_refused": value["cases"]["negative"]["events"] = []
    elif damage == "schema": value["schema"] = "ghcp-real-bundle-load-smoke-v0"
    elif damage == "unknown_field": value["unrecognized"] = True
    elif damage == "missing_marker": del value["synthetic"]
    elif damage == "extra_case": value["cases"]["unrecognized"] = value["cases"]["positive"]
    elif damage == "mutation_bool": value["mutation"]["changed_bytes"] = True
    elif damage == "mutation_offset_bool": value["mutation"]["offset"] = False
    elif damage == "mutation_size_bool": value["mutation"]["bytes"] = True
    elif damage == "model_calls_bool": value["model_calls"] = False
    elif damage == "profile_missing": del value["profile_seeds"]["positive"]
    elif damage == "profile_not_synthetic": value["profile_seeds"]["positive"]["synthetic"] = False
    elif damage == "profile_claimed_measured": value["profile_seeds"]["positive"]["evidence_kind"] = "measured"
    elif damage == "profile_wrong_marker": value["profile_seeds"]["positive"]["metadata"] = [["unrelated", "true"]]
    else: (smoke_receipt / "patched-load-evidence.json").rename(smoke_receipt / "removed-proof.json")
    target.write_bytes(encode(value))
    with pytest.raises(Refused):
        smoke.verify_smoke_evidence(smoke_receipt, IDENTITY)
