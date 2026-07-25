import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


FULL_SHA = "a" * 40


def test_direct_script_entrypoint_resolves_core_import():
    batch_root = Path(__file__).resolve().parents[1]
    script = batch_root / "scripts" / "download_inference_from_hf.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=batch_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0
    assert "--revision" in completed.stdout
    assert "--allow-legacy-missing-provenance" in completed.stdout
    assert completed.stderr == ""
    assert "No module named 'core'" not in completed.stdout


def _load_module():
    path = Path("scripts/download_inference_from_hf.py")
    spec = importlib.util.spec_from_file_location("download_inference_from_hf", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_inference_from_uploaded_parquet(monkeypatch):
    module = _load_module()
    frame = pd.DataFrame(
        [
            {
                "task_id": "task-1",
                "deliverable_text": "hello",
                "deliverable_files": ["deliverable_files/task-1/out.txt"],
            },
            {
                "task_id": "task-2",
                "deliverable_text": "",
                "deliverable_files": [],
            },
        ]
    )
    monkeypatch.setattr(module.pd, "read_parquet", lambda path: frame)

    payload = module._build_inference_from_parquet("unused.parquet", "exp", "owner/repo")

    assert payload["experiment_id"] == "exp"
    assert payload["source"] == "owner/repo"
    assert [row["task_id"] for row in payload["results"]] == ["task-1", "task-2"]
    assert payload["results"][0]["status"] == "success"
    assert payload["results"][0]["deliverable_files"] == ["deliverable_files/task-1/out.txt"]
    assert payload["results"][1]["status"] == "error"


def test_full_sha_is_normalized_without_hf_api(monkeypatch):
    module = _load_module()

    class UnexpectedApi:
        def __init__(self):
            raise AssertionError("HfApi must not be constructed for a full SHA")

    monkeypatch.setattr(module, "HfApi", UnexpectedApi)
    assert module.resolve_immutable_revision("owner/repo", FULL_SHA.upper()) == FULL_SHA


def test_alias_revision_resolves_to_full_sha(monkeypatch):
    module = _load_module()
    calls = []

    class FakeApi:
        def dataset_info(self, repo_id, revision):
            calls.append((repo_id, revision))
            return SimpleNamespace(sha=FULL_SHA.upper())

    monkeypatch.setattr(module, "HfApi", FakeApi)
    assert module.resolve_immutable_revision("owner/repo", "release") == FULL_SHA
    assert calls == [("owner/repo", "release")]


def test_whitespace_wrapped_sha_does_not_bypass_resolution(monkeypatch):
    module = _load_module()
    calls = []

    class FakeApi:
        def dataset_info(self, repo_id, revision):
            calls.append((repo_id, revision))
            return SimpleNamespace(sha=FULL_SHA)

    monkeypatch.setattr(module, "HfApi", FakeApi)
    explicit = f" {FULL_SHA} "
    assert module.resolve_immutable_revision("owner/repo", explicit) == FULL_SHA
    assert calls == [("owner/repo", explicit)]


@pytest.mark.parametrize("resolved", [None, "", "abc", "g" * 40, "a" * 39])
def test_invalid_resolved_revision_fails_closed(monkeypatch, resolved):
    module = _load_module()

    class FakeApi:
        def dataset_info(self, repo_id, revision):
            return SimpleNamespace(sha=resolved)

    monkeypatch.setattr(module, "HfApi", FakeApi)
    with pytest.raises(ValueError, match="full commit SHA"):
        module.resolve_immutable_revision("owner/repo", "")


def test_revision_resolution_error_propagates(monkeypatch):
    module = _load_module()

    class FailingApi:
        def dataset_info(self, repo_id, revision):
            raise RuntimeError("offline")

    monkeypatch.setattr(module, "HfApi", FailingApi)
    with pytest.raises(RuntimeError, match="offline"):
        module.resolve_immutable_revision("owner/repo", "main")


def test_downloaded_json_metadata_overrides_stale_values(monkeypatch, tmp_path):
    module = _load_module()
    downloaded = tmp_path / "downloaded.json"
    downloaded.write_text(
        json.dumps(
            {
                "source": "legacy/source",
                "source_repo_id": "stale/repo",
                "source_revision": "b" * 40,
                "results": [],
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_hf_hub_download(**kwargs):
        calls.append(kwargs)
        if kwargs["filename"] == "inference_provenance.json":
            raise module.EntryNotFoundError("legacy revision")
        return str(downloaded)

    monkeypatch.setenv("HF_TOKEN", "secret-token")
    monkeypatch.setattr(module, "hf_hub_download", fake_hf_hub_download)
    out = tmp_path / "step2_inference_results.json"

    module._download_or_reconstruct_inference(
        "exp",
        "owner/repo",
        FULL_SHA,
        out,
        allow_legacy_missing_provenance=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["source_repo_id"] == "owner/repo"
    assert payload["source_revision"] == FULL_SHA
    assert payload["source"] == "legacy/source"
    assert payload["azure_ai_provenance_status"] == "legacy-missing"
    assert calls == [
        {
            "repo_id": "owner/repo",
            "repo_type": "dataset",
            "filename": "step2_inference_results.json",
            "revision": FULL_SHA,
            "token": "secret-token",
        },
        {
            "repo_id": "owner/repo",
            "repo_type": "dataset",
            "filename": "inference_provenance.json",
            "revision": FULL_SHA,
            "token": "secret-token",
        },
    ]


def test_verified_sidecar_restores_endpoint_free_routes(monkeypatch, tmp_path):
    module = _load_module()
    route = {
        "endpoint_kind": "direct-v1",
        "profile": "direct-v1",
        "runtime_fingerprint": "f" * 64,
        "workload": "inference",
    }
    downloaded = tmp_path / "downloaded.json"
    downloaded.write_text(
        json.dumps({
            "experiment_id": "exp",
            "prepared_fingerprint": "e" * 64,
              "execution_mode": "subprocess",
            "azure_ai_routes": [route],
            "results": [{"task_id": "task-1", "deliverable_files": []}],
        }),
        encoding="utf-8",
    )
    provenance = tmp_path / "inference_provenance.json"
    provenance.write_text(
        json.dumps({
              "schema_version": "azure-ai-inference-provenance-v2",
            "experiment_id": "exp",
            "source_repo_id": "owner/repo",
            "prepared_fingerprint": "e" * 64,
              "execution_mode": "subprocess",
            "task_count": 1,
            "ordered_task_ids_sha256": hashlib.sha256(
                b'["task-1"]'
            ).hexdigest(),
            "azure_ai_routes": [route],
        }),
        encoding="utf-8",
    )

    def fake_download(**kwargs):
        return str(
            provenance
            if kwargs["filename"] == "inference_provenance.json"
            else downloaded
        )

    monkeypatch.setattr(module, "hf_hub_download", fake_download)
    out = tmp_path / "output.json"

    module._download_or_reconstruct_inference(
        "exp", "owner/repo", FULL_SHA, out
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["azure_ai_routes"] == [route]
    assert payload["azure_ai_provenance_status"] == "verified-sidecar"
    assert payload["prepared_fingerprint"] == "e" * 64


def test_missing_sidecar_is_rejected_without_explicit_legacy_override(
    monkeypatch,
):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "hf_hub_download",
        lambda **kwargs: (_ for _ in ()).throw(
            module.EntryNotFoundError("missing")
        ),
    )

    with pytest.raises(ValueError, match="provenance sidecar is missing"):
        module._attach_inference_provenance(
            {"results": [{"task_id": "task-1", "deliverable_files": []}]},
            experiment="exp",
            repo_id="owner/repo",
            revision=FULL_SHA,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("prepared_fingerprint", "d" * 64, "prepared fingerprint mismatch"),
        (
            "azure_ai_routes",
            [{
                "endpoint_kind": "direct-v1",
                "profile": "direct-v1",
                "runtime_fingerprint": "d" * 64,
                "workload": "inference",
            }],
            "Azure AI routes mismatch",
        ),
    ],
)
def test_verified_sidecar_rejects_embedded_identity_mismatch(
    monkeypatch, tmp_path, field, value, message
):
    module = _load_module()
    route = {
        "endpoint_kind": "direct-v1",
        "profile": "direct-v1",
        "runtime_fingerprint": "f" * 64,
        "workload": "inference",
    }
    provenance = tmp_path / "inference_provenance.json"
    provenance.write_text(json.dumps({
          "schema_version": "azure-ai-inference-provenance-v2",
        "experiment_id": "exp",
        "source_repo_id": "owner/repo",
        "prepared_fingerprint": "e" * 64,
          "execution_mode": "subprocess",
        "task_count": 1,
        "ordered_task_ids_sha256": hashlib.sha256(
            b'["task-1"]'
        ).hexdigest(),
        "azure_ai_routes": [route],
    }), encoding="utf-8")
    monkeypatch.setattr(
        module, "hf_hub_download", lambda **kwargs: str(provenance)
    )
    payload = {
        "prepared_fingerprint": "e" * 64,
          "execution_mode": "subprocess",
        "azure_ai_routes": [route],
        "results": [{"task_id": "task-1", "deliverable_files": []}],
    }
    payload[field] = value

    with pytest.raises(ValueError, match=message):
        module._attach_inference_provenance(
            payload,
            experiment="exp",
            repo_id="owner/repo",
            revision=FULL_SHA,
        )


def test_expected_leading_tasks_preserve_exact_source_prefix():
    module = _load_module()
    payload = {
        "results": [
            {"task_id": "task-1", "deliverable_files": []},
            {"task_id": "task-2", "deliverable_files": []},
            {"task_id": "task-3", "deliverable_files": []},
        ]
    }

    selected = module._select_expected_leading_tasks(
        payload, ["task-1", "task-2"]
    )

    assert [row["task_id"] for row in selected["results"]] == [
        "task-1",
        "task-2",
    ]
    assert len(payload["results"]) == 3


@pytest.mark.parametrize(
    "expected",
    [
        ["task-2"],
        ["task-1", "task-3"],
        ["task-1", "task-1"],
    ],
)
def test_expected_leading_tasks_reject_order_drift_and_duplicates(expected):
    module = _load_module()
    payload = {
        "results": [
            {"task_id": "task-1", "deliverable_files": []},
            {"task_id": "task-2", "deliverable_files": []},
        ]
    }

    with pytest.raises(ValueError, match="expected leading task IDs"):
        module._select_expected_leading_tasks(payload, expected)


@pytest.mark.parametrize("payload", [[], {}, {"results": None}, {"results": {}}])
def test_invalid_inference_json_fails_closed(monkeypatch, tmp_path, payload):
    module = _load_module()
    downloaded = tmp_path / "downloaded.json"
    downloaded.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(module, "hf_hub_download", lambda **kwargs: str(downloaded))

    with pytest.raises(ValueError, match="object with a results array"):
        module._download_or_reconstruct_inference(
            "exp", "owner/repo", FULL_SHA, tmp_path / "output.json"
        )


def test_main_pins_all_downloads_and_removes_stale_deliverables(monkeypatch, tmp_path):
    module = _load_module()
    frame = pd.DataFrame(
        [{"task_id": "task-1", "deliverable_text": "hello", "deliverable_files": []}]
    )
    monkeypatch.setattr(module.pd, "read_parquet", lambda path: frame)
    calls = []

    class FakeApi:
        def dataset_info(self, repo_id, revision):
            assert (repo_id, revision) == ("owner/repo", "main")
            return SimpleNamespace(sha=FULL_SHA)

    def fake_hf_hub_download(**kwargs):
        calls.append(("file", kwargs))
        if kwargs["filename"] == "step2_inference_results.json":
            raise module.EntryNotFoundError("missing")
        if kwargs["filename"] == "inference_provenance.json":
            raise module.EntryNotFoundError("legacy revision")
        return "unused.parquet"

    def fake_snapshot_download(**kwargs):
        calls.append(("snapshot", kwargs))
        return str(kwargs["local_dir"])

    monkeypatch.chdir(tmp_path)
    stale = Path("workspace/upload/deliverable_files/stale/task.txt")
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")
    monkeypatch.setattr(module, "HfApi", FakeApi)
    monkeypatch.setattr(module, "hf_hub_download", fake_hf_hub_download)
    monkeypatch.setattr(module, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(module, "resolve_repo_id", lambda experiment: "owner/repo")
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: SimpleNamespace(
            experiment="exp",
            output="workspace/inference.json",
            revision="",
            expected_leading_task_id=[],
            allow_legacy_missing_provenance=True,
        ),
    )
    monkeypatch.setenv("HF_TOKEN", "secret-token")

    assert module.main() == 0

    payload = json.loads(Path("workspace/inference.json").read_text(encoding="utf-8"))
    assert payload["results"][0]["task_id"] == "task-1"
    assert payload["results"][0]["status"] == "success"
    assert payload["source"] == "owner/repo"
    assert payload["source_repo_id"] == "owner/repo"
    assert payload["source_revision"] == FULL_SHA
    assert list(Path("workspace/upload/deliverable_files").iterdir()) == []
    assert len(calls) == 4
    assert all(call[1]["revision"] == FULL_SHA for call in calls)
    assert all(call[1]["token"] == "secret-token" for call in calls)
    assert calls[-1][1]["allow_patterns"] == [
        "deliverable_files/task-1/**"
    ]


def test_main_filters_manifest_and_snapshot_to_expected_leading_tasks(
    monkeypatch, tmp_path
):
    module = _load_module()
    source_payload = {
        "results": [
            {
                "task_id": task_id,
                "deliverable_files": [
                    f"deliverable_files/{task_id}/out.txt"
                ],
            }
            for task_id in ("task-1", "task-2", "task-3")
        ]
    }
    downloaded = tmp_path / "downloaded.json"
    downloaded.write_text(json.dumps(source_payload), encoding="utf-8")
    snapshot_calls = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "resolve_repo_id", lambda experiment: "owner/repo")
    monkeypatch.setattr(module, "resolve_immutable_revision", lambda *args: FULL_SHA)
    def fake_download(**kwargs):
        if kwargs["filename"] == "inference_provenance.json":
            raise module.EntryNotFoundError("legacy revision")
        return str(downloaded)

    monkeypatch.setattr(module, "hf_hub_download", fake_download)

    def fake_snapshot_download(**kwargs):
        snapshot_calls.append(kwargs)
        root = Path(kwargs["local_dir"])
        for task_id in ("task-1", "task-2"):
            task_root = root / "deliverable_files" / task_id
            task_root.mkdir(parents=True)
            (task_root / "out.txt").write_text(task_id, encoding="utf-8")

    monkeypatch.setattr(module, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: SimpleNamespace(
            experiment="exp",
            output="workspace/inference.json",
            revision=FULL_SHA,
            expected_leading_task_id=["task-1", "task-2"],
            allow_legacy_missing_provenance=True,
        ),
    )

    assert module.main() == 0

    output = json.loads(
        Path("workspace/inference.json").read_text(encoding="utf-8")
    )
    assert [row["task_id"] for row in output["results"]] == [
        "task-1",
        "task-2",
    ]
    assert snapshot_calls[0]["allow_patterns"] == [
        "deliverable_files/task-1/**",
        "deliverable_files/task-2/**",
    ]
    assert not Path(
        "workspace/upload/deliverable_files/task-3"
    ).exists()


def test_deliverable_promotion_failure_restores_previous_destination(
    monkeypatch, tmp_path
):
    module = _load_module()
    monkeypatch.chdir(tmp_path)
    destination = Path("workspace/upload/deliverable_files")
    destination.mkdir(parents=True)
    (destination / "previous.txt").write_text("previous", encoding="utf-8")

    def fake_snapshot_download(**kwargs):
        staged = Path(kwargs["local_dir"]) / "deliverable_files"
        task_dir = staged / "task-1"
        task_dir.mkdir(parents=True)
        (task_dir / "current.txt").write_text("current", encoding="utf-8")
        return str(kwargs["local_dir"])

    real_replace = module.os.replace

    def fail_promotion(source, target):
        if ".deliverable_files.staging-" in str(source) and Path(target) == destination:
            raise OSError("promotion failed")
        return real_replace(source, target)

    monkeypatch.setattr(module, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(module.os, "replace", fail_promotion)

    with pytest.raises(OSError, match="promotion failed"):
        module._download_and_replace_deliverables(
            "owner/repo",
            FULL_SHA,
            [{
                "task_id": "task-1",
                "deliverable_files": [
                    "deliverable_files/task-1/current.txt"
                ],
            }],
        )

    assert (destination / "previous.txt").read_text(encoding="utf-8") == "previous"
    assert not (destination / "task-1" / "current.txt").exists()
    assert list(destination.parent.glob(".deliverable_files.staging-*")) == []
    assert list(destination.parent.glob(".deliverable_files.backup-*")) == []


def test_unsafe_manifest_fails_before_replacing_existing_deliverables(
    monkeypatch, tmp_path
):
    module = _load_module()
    monkeypatch.chdir(tmp_path)
    destination = Path("workspace/upload/deliverable_files")
    destination.mkdir(parents=True)
    (destination / "previous.txt").write_text("previous", encoding="utf-8")

    def fake_snapshot_download(**kwargs):
        staged = Path(kwargs["local_dir"]) / "deliverable_files" / "task-1"
        staged.mkdir(parents=True)
        (staged / "out.txt").write_text("current", encoding="utf-8")

    monkeypatch.setattr(module, "snapshot_download", fake_snapshot_download)

    with pytest.raises(ValueError):
        module._download_and_replace_deliverables(
            "owner/repo",
            FULL_SHA,
            [{
                "task_id": "task-1",
                "deliverable_files": ["../outside.txt"],
            }],
        )

    assert (destination / "previous.txt").read_text(encoding="utf-8") == "previous"
    assert list(destination.parent.glob(".deliverable_files.staging-*")) == []