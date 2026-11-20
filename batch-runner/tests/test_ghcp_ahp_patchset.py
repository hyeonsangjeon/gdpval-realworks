"""Two-patch provenance and build-manifest fixtures; no build or live host execution."""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

import ghcp_ahp_bundle_manifest as bundle
import ghcp_ahp_patched_runtime as runtime
from ghcp_ahp_errors import Refused
from tests.test_ghcp_ahp_patched_runtime import BODY, bind, build_value, encode, fixture_tree, node_copy, sha
from tests.test_ghcp_ahp_patched_runtime_rejections import chain


def local_patchset(tmp_path, monkeypatch):
    folder = tmp_path / "isolated-loader"
    (folder / "patches").mkdir(parents=True)
    for path in (runtime.PATCH_SET, *(runtime.PATCH_SET.parent / name for name, _ in runtime.PATCH_COMPONENTS)):
        shutil.copyfile(path, folder / "patches" / path.name)
    shutil.copyfile(runtime.LOADER, folder / runtime.LOADER.name)
    monkeypatch.setattr(runtime, "PATCH_SET", folder / "patches" / runtime.PATCH_SET.name)
    monkeypatch.setattr(runtime, "LOADER", folder / runtime.LOADER.name)
    return folder


def test_patch_sha_is_the_ordered_full_manifest_not_either_component():
    value = runtime.verify_patch_set()
    assert sha(runtime.PATCH_SET.read_bytes()) == runtime.PATCH_SHA256 == "6d869d65ec18a5aba93528f27e1277ac37b48a7da439065911e11e6c71f33856"
    assert value == {"schema": "ghcp-prewarm-patchset-v1", "upstream_commit": runtime.PIN,
                     "patches": [{"file": name, "sha256": digest} for name, digest in runtime.PATCH_COMPONENTS]}
    assert len(value["patches"]) == 2
    assert runtime.PATCH_SHA256 not in {runtime.BASE_PATCH_SHA256, runtime.CORRECTION_SHA256}
    assert runtime.PATCHED_SOURCES["src/vs/platform/agentHost/node/agentService.ts"] == "209a699ee4138a822a2aaa5a1146066d937d5526a826846106debb8b9d34a49c"


@pytest.mark.parametrize("component", [0, 1])
@pytest.mark.parametrize("damage", ["missing", "tampered", "symlink"])
def test_build_receipt_cannot_accept_missing_or_changed_patch_bytes(tmp_path, monkeypatch, component, damage):
    local_patchset(tmp_path, monkeypatch)
    value = build_value()
    target = runtime.PATCH_SET.parent / runtime.PATCH_COMPONENTS[component][0]
    if damage == "missing":
        target.rename(target.with_suffix(".removed"))
    elif damage == "tampered":
        target.write_bytes(target.read_bytes() + b"# altered fixture\n")
    else:
        saved = target.with_suffix(".saved")
        target.rename(saved)
        target.symlink_to(saved)
    with pytest.raises(Refused, match="patched_patchset_component_"):
        runtime.validate_build_receipt(value)


@pytest.mark.parametrize("damage", ["omit_followup", "omit_base", "reverse_order", "self_reseal"])
def test_patchset_manifest_cannot_omit_reorder_or_reseal_components(tmp_path, monkeypatch, damage):
    local_patchset(tmp_path, monkeypatch)
    value = json.loads(runtime.PATCH_SET.read_text())
    if damage == "omit_followup":
        value["patches"].pop()
    elif damage == "omit_base":
        value["patches"].pop(0)
    elif damage == "reverse_order":
        value["patches"].reverse()
    else:
        target = runtime.PATCH_SET.parent / value["patches"][1]["file"]
        target.write_bytes(target.read_bytes() + b"# tampered fixture\n")
        value["patches"][1]["sha256"] = sha(target.read_bytes())
    runtime.PATCH_SET.write_bytes(encode(value))
    with pytest.raises(Refused, match="^patched_patchset_manifest_refused$"):
        runtime.verify_patch_set()


@pytest.mark.parametrize("damage", ["base_only", "correction_only", "old_schema", "old_source"])
def test_old_single_patch_receipts_are_not_promoted(damage):
    value = build_value()
    if damage in ("base_only", "correction_only"):
        value["patch_sha256"] = runtime.BASE_PATCH_SHA256 if damage == "base_only" else runtime.CORRECTION_SHA256
    elif damage == "old_schema":
        value["schema"] = "ghcp-patched-host-build-candidate-v2"
    else:
        value["patched_source_sha256"]["src/vs/platform/agentHost/node/agentService.ts"] = "280f71720d83a4326a514c16cb1d08c6ca9e4430fdb58fc98c40afc33bebb682"
    with pytest.raises(Refused, match="^patched_build_receipt_refused$"):
        runtime.validate_build_receipt(value)


def test_patchset_sha_survives_result_receipt_loader_evidence_and_markdown(chain):
    _, directory, provenance, _ = chain
    for name in (*runtime.ARTIFACTS, "wire-capture.json", "probe.json", "summary.json", "handshake.json", "thread-policy.json"):
        assert json.loads((directory / name).read_text())["patch_sha256"] == runtime.PATCH_SHA256
    assert f'- patch_sha256: `{json.dumps(runtime.PATCH_SHA256)}`' in (directory / "summary.md").read_text()
    assert runtime.verify_artifact_chain(directory, handshake=True, policy=True)["execution_allowed"] is False
    assert provenance["runtime_evidence_synthetic"] is True


@pytest.mark.parametrize("damage", ["missing", "tampered"])
def test_artifact_consumer_refuses_followup_drift_even_when_all_labels_agree(chain, tmp_path, monkeypatch, damage):
    _, directory, _, _ = chain
    local_patchset(tmp_path, monkeypatch)
    target = runtime.PATCH_SET.parent / runtime.PATCH_COMPONENTS[1][0]
    if damage == "missing":
        target.rename(target.with_suffix(".removed"))
    else:
        target.write_bytes(target.read_bytes() + b"# modified after evidence fixture\n")
    with pytest.raises(Refused, match="patched_patchset_component_"):
        runtime.verify_artifact_chain(directory, handshake=True, policy=True)


@pytest.mark.parametrize("phase,damage", [("initial", "valid"), ("initial", "missing"), ("initial", "tampered"),
                                         ("before_load", "missing"), ("before_load", "tampered")])
def test_native_observer_checks_followup_bytes_before_activation_and_before_loading(tmp_path, monkeypatch, node_copy, phase, damage):
    local_patchset(tmp_path, monkeypatch)
    tree = fixture_tree(tmp_path, node_copy)
    environment = bind(tree)
    target = runtime.PATCH_SET.parent / runtime.PATCH_COMPONENTS[1][0]
    mutate = (f"fs.unlinkSync({json.dumps(str(target))});" if damage == "missing" else
              f"fs.appendFileSync({json.dumps(str(target))}, '# changed fixture\\n');" if damage == "tampered" else "")
    script = """
      const fs = require('node:fs'); const {pathToFileURL} = require('node:url');
      const contract = JSON.parse(process.env.GHCP_AHP_PATCHED_RUNTIME_CONTRACT);
      (async () => {
    """ + (mutate if phase == "initial" else "") + f"""
      require({json.dumps(str(runtime.LOADER))}).activate({{modelFree: true, sessionOnly: true,
        entrypoint: contract.entrypoint, forkContract: {{vscode_commit: contract.upstream_commit,
          entrypoint: contract.entrypoint, files: {{node: {{path: contract.node_path, sha256: contract.node_sha256}}}}}}}});
    """ + (mutate if phase == "before_load" else "") + """
      const value = await import(pathToFileURL(contract.runtime_bundle_path).href);
      if (value.fixtureOnly !== true) throw new Error('invalid_inert_fixture');
      console.log('loaded-inert-fixture');
      })().catch(error => { console.error(error.message); process.exitCode = 2; });
    """
    result = subprocess.run([str(tree["node"]), "-e", script], env={"PATH": "/usr/bin:/bin", **environment},
                            cwd=tree["prepared"], capture_output=True, text=True, timeout=20)
    if damage == "valid":
        assert result.returncode == 0, result.stderr
        proof = json.loads(next((tree["state"] / "wire/patched-runtime").glob("load-*.json")).read_text())
        assert proof["patch_sha256"] == runtime.PATCH_SHA256 and proof["execution_allowed"] is False
        assert proof["synthetic"] is True
    else:
        assert result.returncode == 2 and "patched_patchset_component_" in result.stderr
        assert "loaded-inert-fixture" not in result.stdout
        assert not list((tree["state"] / "wire/patched-runtime").glob("load-*.json"))


def write_archive(path, name, data, *, stamp=1793318400):
    with tarfile.open(path, "w:gz") as archive:
        entry = tarfile.TarInfo(name)
        entry.size, entry.mtime = len(data), stamp
        archive.addfile(entry, io.BytesIO(data))


@pytest.fixture
def bundle_fixture(tmp_path, monkeypatch):
    """Exercise real manifest adapters on tiny inert bytes; do not run a compiler."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "product.json").write_text('{"name":"synthetic original"}')
    expected = {}
    for name in runtime.PATCHED_SOURCES:
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"synthetic source, never compiled")
        expected[name] = sha(file.read_bytes())
    monkeypatch.setattr(runtime, "PATCHED_SOURCES", expected)
    source_archive, server_archive = tmp_path / "source.tgz", tmp_path / "server.tgz"
    write_archive(source_archive, "vscode-" + runtime.PIN + "/package.json", b'{}')
    write_archive(server_archive, "vscode-server-linux-x64/product.json", encode({"commit": runtime.PIN}))
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(encode({"artifacts": {"server": {"sha256": sha(server_archive.read_bytes()), "maximum_bytes": 1024 * 1024}}}))
    monkeypatch.setattr(runtime, "MANIFEST", manifest)
    monkeypatch.setattr(runtime, "MANIFEST_SHA256", sha(manifest.read_bytes()))
    monkeypatch.setattr(runtime, "SOURCE_SHA256", sha(source_archive.read_bytes()))
    inputs_path = tmp_path / "inputs.json"
    inputs = bundle.prepare_inputs(source, source_archive, server_archive, inputs_path)
    output = source / "out-patched"
    (output / Path(bundle.ENTRY).parent).mkdir(parents=True)
    (output / bundle.ENTRY).write_bytes(BODY)
    (output / "date").write_text(inputs["build_date"])
    (output / "empty-resource.txt").write_bytes(b"")
    return source, output, inputs_path, tmp_path / "receipt.json", tmp_path / "bundle-manifest.json"


def test_bundle_manifest_uses_both_patches_and_records_only_hashes_and_sizes(bundle_fixture):
    value = bundle.record_manifest(*bundle_fixture)
    assert value["patch_sha256"] == runtime.PATCH_SHA256
    assert value["entrypoint"] == {"path": bundle.ENTRY, "sha256": sha(BODY), "bytes": len(BODY)}
    assert value["file_count"] == 3 and value["total_bytes"] > len(BODY)
    assert value["execution_allowed"] is False and value["runtime_load_status"] == "not_executed"
    assert value["build_receipt"]["patch_sha256"] == runtime.PATCH_SHA256
    assert b"export const fixtureOnly" not in bundle_fixture[-1].read_bytes()
    assert bundle.validate_manifest(json.loads(bundle_fixture[-1].read_text())) == value


@pytest.mark.parametrize("field,new_value", [("patch_sha256", "base_only"), ("execution_allowed", True), ("model_calls", 1),
    ("runtime_load_status", "measured"), ("file_count", 999), ("total_bytes", 0), ("file_manifest_sha256", "0" * 64),
    ("build_inputs_sha256", "0" * 64), ("build_receipt_sha256", "0" * 64), ("entrypoint", {})])
def test_bundle_manifest_rejects_tampered_contract_or_counts(bundle_fixture, field, new_value):
    value = bundle.record_manifest(*bundle_fixture)
    value[field] = runtime.BASE_PATCH_SHA256 if new_value == "base_only" else new_value
    with pytest.raises(Refused):
        bundle.validate_manifest(value)


@pytest.mark.parametrize("damage", ["missing_followup", "product_drift", "symlink_output", "source_drift", "fifo_output"])
def test_build_manifest_generation_refuses_incomplete_or_changed_inputs(bundle_fixture, tmp_path, monkeypatch, damage):
    source, output, *_ = bundle_fixture
    if damage == "missing_followup":
        local_patchset(tmp_path, monkeypatch)
        target = runtime.PATCH_SET.parent / runtime.PATCH_COMPONENTS[1][0]
        target.rename(target.with_suffix(".removed"))
    elif damage == "product_drift":
        (source / "product.json").write_text('{}')
    elif damage == "source_drift":
        (source / next(iter(runtime.PATCHED_SOURCES))).write_text('changed synthetic source')
    elif damage == "fifo_output":
        os.mkfifo(output / "not-a-regular-output")
    else:
        (output / "linked-output.js").symlink_to(output / bundle.ENTRY)
    with pytest.raises(Refused):
        bundle.record_manifest(*bundle_fixture)
    assert not bundle_fixture[-1].exists()
