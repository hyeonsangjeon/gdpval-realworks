"""Real staging/extraction on inert archives; never execute a vendor runtime."""

import copy
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tarfile

import pytest

import ghcp_ahp_bundle_manifest as bundle
import ghcp_ahp_load_smoke as load
import ghcp_ahp_patched_runtime as runtime
import ghcp_ahp_prewarm_zero_turn as prewarm
import ghcp_ahp_probe as probe
from .test_ghcp_ahp_patchset import bundle_fixture
from .test_ghcp_ahp_patched_runtime import BODY, encode, sha
from .test_ghcp_ahp_prewarm_zero_turn import IDENTITY, build, write


@pytest.fixture(autouse=True)
def no_execution_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("inert staging test attempted process/network execution")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(probe.urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def archive(path, members, *, sdk_link=False):
    with tarfile.open(path, "w:gz") as output:
        for name, data in members.items():
            item = tarfile.TarInfo(name)
            item.size, item.mode = len(data), 0o755
            output.addfile(item, io.BytesIO(data))
        if sdk_link:
            # Exact relative link shape found in the byte-pinned 0.163.0 SDK.
            item = tarfile.TarInfo("node_modules/.bin/codex")
            item.type, item.linkname = tarfile.SYMTYPE, "../@openai/codex/bin/codex.js"
            output.addfile(item)


@pytest.fixture
def prepared_tree(bundle_fixture, tmp_path, monkeypatch):
    source, outputs, inputs_path, receipt_path, manifest_path = bundle_fixture
    server_archive = tmp_path / "server.tgz"
    server_members = {"node": b"inert synthetic node, never execute",
        "bin/code-server": b"inert synthetic launcher, never execute", "package.json": b'{"type":"module"}',
        "product.json": encode({"commit": runtime.PIN}), "out/bootstrap-fork.js": b"inert bootstrap",
        "out/server-main.js": b"inert parent", runtime.RUNTIME_RELATIVE: b"inert original bundle"}
    archive(server_archive, {"vscode-server-linux-x64/" + key: value for key, value in server_members.items()})
    archive(tmp_path / "cli.tgz", {"code": b"inert synthetic CLI, never execute"})
    archive(tmp_path / "codex_sdk.tgz", {"node_modules/@openai/codex/bin/codex.js": b"inert SDK wrapper",
        "node_modules/@openai/codex/package.json": b'{"version":"0.163.0"}'}, sdk_link=True)
    manifest = {"vscode_commit": runtime.PIN, "artifacts": {
        name: {"sha256": probe.digest(tmp_path / (name + ".tgz")), "maximum_bytes": 1024 * 1024}
        for name in ("server", "cli", "codex_sdk", "source")}}
    runtime.MANIFEST.write_bytes(encode(manifest))
    monkeypatch.setattr(runtime, "MANIFEST_SHA256", probe.digest(runtime.MANIFEST))
    monkeypatch.setattr(probe, "load_manifest", lambda: copy.deepcopy(manifest))
    inputs = json.loads(inputs_path.read_text())
    inputs["server_archive_sha256"] = manifest["artifacts"]["server"]["sha256"]
    inputs_path.write_bytes(encode(inputs) + b"\n")
    bundle.record_manifest(*bundle_fixture)
    monkeypatch.setattr(load, "BASELINE_SHA256", sha(BODY))
    monkeypatch.setattr(load, "BASELINE_BYTES", len(BODY))
    transfer = tmp_path / "transfer"
    load.pack_payload(outputs / bundle.ENTRY, manifest_path, server_archive, transfer, prewarm.validate_build(build(), IDENTITY))
    selected = tmp_path / "build.json"
    write(selected, build())

    # Model the original probe's complete prepared tree, including the SDK link.
    base = tmp_path / "original"
    (base / "downloads").mkdir(parents=True)
    for name in manifest["artifacts"]:
        shutil.copyfile(tmp_path / (name + ".tgz"), base / "downloads" / (name + ".tgz"))
    cache = base / "cli-data/servers" / ("Stable-" + runtime.PIN)
    cache.mkdir(parents=True)
    probe.extract_archive(base / "downloads/server.tgz", cache)
    (cache / "vscode-server-linux-x64").rename(cache / "server")
    for name, relative in (("cli", "cli"), ("codex_sdk", "codex-sdk")):
        (base / relative).mkdir()
        probe.extract_archive(base / "downloads" / (name + ".tgz"), base / relative)
    evidence = tmp_path / "evidence"
    write(evidence / "source-evidence.json", {"synthetic": True, "source_archive_sha256": runtime.SOURCE_SHA256})
    server_relative = Path("cli-data/servers") / ("Stable-" + runtime.PIN) / "server"
    binaries = {"cli": Path("cli/code"), "node": server_relative / "node", "server_launcher": server_relative / "bin/code-server"}
    write(evidence / "prepared.json", {"vscode_commit": runtime.PIN, "runner": IDENTITY, "artifacts": manifest["artifacts"],
        "binary_sha256": {name: {"relative_path": str(path), "sha256": probe.digest(base / path)} for name, path in binaries.items()},
        "source_evidence_sha256": probe.digest(evidence / "source-evidence.json"), "authentication_supplied": False, "model_calls": 0})
    assert (base / "codex-sdk/node_modules/.bin/codex").is_symlink()
    return {"transfer": transfer, "build": selected, "base": base, "output": tmp_path / "prewarm",
            "evidence": evidence, "identity": IDENTITY}


def prepare(tree):
    return prewarm.prepare(tree["transfer"], tree["build"], tree["base"], tree["output"], tree["evidence"], tree["identity"])


def test_complete_preparation_keeps_sdk_link_out_of_staging_and_verifies_real_chain(prepared_tree):
    tree = prepared_tree
    before = probe.digest(tree["base"] / "downloads/codex_sdk.tgz")
    result = prepare(tree)  # No stubs for staging, extraction, manifest or receipt checks.
    root = tree["output"] / "runtime"
    link = root / "codex-sdk/node_modules/.bin/codex"
    assert link.is_symlink() and os.readlink(link) == "../@openai/codex/bin/codex.js"
    assert link.resolve() == root / "codex-sdk/node_modules/@openai/codex/bin/codex.js"
    assert link.read_bytes() == b"inert SDK wrapper"
    assert probe.digest(root / "downloads/codex_sdk.tgz") == before
    assert not list((tree["output"] / "payload/base").rglob("codex-sdk"))
    assert not any(path.is_symlink() for path in (tree["output"] / "payload/base").rglob("*"))
    request = prewarm.verify_preparation(tree["output"] / "preparation.json", root, tree["evidence"], IDENTITY)
    assert request["sha256"] == result["build_receipt_sha256"]
    probe.verify_prepared(probe.load_manifest(), root, tree["evidence"], IDENTITY)
    assert result["execution_allowed"] is result["admission_allowed"] is False
    assert result["applied_policy"] == "not_reported" and result["runtime_load_status"] == "staged_not_loaded"
    assert not list(tree["output"].rglob("load-*.json"))


def test_the_old_full_tree_composition_still_refuses_the_sdk_link(prepared_tree):
    tree = prepared_tree
    payload = tree["output"]
    value = load.prepare_payload(tree["transfer"], payload, prewarm.validate_build(build(), IDENTITY))
    request = {"path": payload / "build-receipt.json", "sha256": value["transfer"]["build_receipt_sha256"]}
    with pytest.raises(probe.Refused, match="^patched_runtime_staging_special_file$"):
        runtime.stage_runtime(tree["base"], payload / "must-not-exist", payload / "inputs/agentHostMain.js", request)
    assert not (payload / "must-not-exist").exists()


@pytest.mark.parametrize("kind", ["fifo", "file_symlink", "directory_symlink"])
def test_special_files_in_the_actual_server_staging_input_are_still_refused(prepared_tree, monkeypatch, kind):
    tree = prepared_tree
    original = load.prepare_payload
    def damaged_payload(*args):
        result = original(*args)
        base = args[1] / "base"
        target = base / "injected-special"
        if kind == "fifo":
            os.mkfifo(target)
        else:
            target.symlink_to(base / ("downloads/server.tgz" if kind == "file_symlink" else "downloads"),
                              target_is_directory=kind == "directory_symlink")
        return result
    monkeypatch.setattr(load, "prepare_payload", damaged_payload)
    monkeypatch.setattr(prewarm, "extract_runtime_inputs", lambda *args: pytest.fail("special file reached SDK extraction"))
    with pytest.raises(probe.Refused, match="^patched_runtime_staging_special_file$"):
        prepare(tree)
    assert not (tree["output"] / "runtime").exists()
    assert not (tree["evidence"] / "prewarm-zero-turn-preparation.json").exists()


@pytest.mark.parametrize("name", ["cli", "codex_sdk", "source"])
@pytest.mark.parametrize("damage", ["bytes", "symlink"])
def test_runtime_input_archives_must_remain_exact_regular_pinned_files(prepared_tree, name, damage):
    tree = prepared_tree
    path = tree["base"] / "downloads" / (name + ".tgz")
    if damage == "bytes":
        path.write_bytes(path.read_bytes() + b"changed")
    else:
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
    reason = "prewarm_runtime_input_hash_refused" if damage == "bytes" else "patched_runtime_path_refused"
    with pytest.raises(probe.Refused, match="^" + reason + "$"):
        prepare(tree)
    assert not (tree["output"] / "preparation.json").exists()


def test_original_preparation_receipt_is_still_checked_before_auth(prepared_tree):
    tree = prepared_tree
    path = tree["evidence"] / "prepared.json"
    value = json.loads(path.read_text())
    value["binary_sha256"]["cli"]["sha256"] = "0" * 64
    write(path, value)
    with pytest.raises(probe.Refused, match="^prepared_binary_drift$"):
        prepare(tree)
    assert not (tree["output"] / "preparation.json").exists()
