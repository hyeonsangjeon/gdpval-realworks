import json
import inspect
import shutil
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from core.prepared_fingerprint import prepared_fingerprint
from scripts import relay_checkpoint as relay
import step2_run_inference as step2
from huggingface_hub import HfApi
from huggingface_hub.utils import hf_raise_for_status

SOURCE_SHA = "c" * 40
LINEAGE_ID = "lineage"
SANDBOX_DIGEST = (
    "ghcr.io/hyeonsangjeon/gdpval-sandbox@sha256:" + "d" * 64
)
_FAKE_SNAPSHOT_ROOT = None


@pytest.fixture(autouse=True)
def _fake_uploaded_snapshots(tmp_path, monkeypatch):
    global _FAKE_SNAPSHOT_ROOT
    _FAKE_SNAPSHOT_ROOT = tmp_path / "hf-snapshots"

    def fake_snapshot_download(**kwargs):
        snapshot = _FAKE_SNAPSHOT_ROOT / kwargs["revision"]
        if not snapshot.is_dir():
            raise AssertionError(f"fake HF revision is unavailable: {kwargs['revision']}")
        return str(snapshot)

    monkeypatch.setattr(relay, "snapshot_download", fake_snapshot_download)
    yield
    _FAKE_SNAPSHOT_ROOT = None


def _hf_error(status):
    response = httpx.Response(
        status,
        request=httpx.Request("GET", "https://huggingface.co/datasets/owner/repository"),
    )
    try:
        hf_raise_for_status(response)
    except Exception as exc:
        return exc
    raise AssertionError("expected HF HTTP error")


class FakeApi:
    def __init__(self, *, oid="a" * 40):
        self.calls = []
        self.oid = oid
        self.files_by_revision = {}
        self.marker = None
        self.fail_upload_folder = False
        self.corrupt_snapshot_path = None
        self.head = "f" * 40
        self.fail_create_commit = False

    def auth_check(self, **kwargs):
        self.calls.append(("auth_check", kwargs))

    def upload_folder(self, **kwargs):
        self.calls.append(("upload_folder", kwargs))
        if self.fail_upload_folder:
            raise RuntimeError("partial payload upload")
        root = Path(kwargs["folder_path"])
        prefix = kwargs["path_in_repo"]
        self._store_snapshot(root, prefix, self.oid)
        self.files_by_revision[self.oid] = sorted(
            f"{prefix}/{path.relative_to(root).as_posix()}"
            for path in root.rglob("*")
            if path.is_file()
        )
        return SimpleNamespace(oid=self.oid)

    def _store_snapshot(self, root, prefix, revision):
        assert _FAKE_SNAPSHOT_ROOT is not None
        destination = _FAKE_SNAPSHOT_ROOT / revision / prefix
        shutil.copytree(root, destination)
        if self.corrupt_snapshot_path is not None:
            (destination / self.corrupt_snapshot_path).write_bytes(b"corrupt")

    def list_repo_files(self, **kwargs):
        self.calls.append(("list_repo_files", kwargs))
        return self.files_by_revision[kwargs["revision"]]

    def upload_file(self, **kwargs):
        self.calls.append(("upload_file", kwargs))
        if kwargs["path_in_repo"].endswith("/current.json"):
            self.marker = bytes(kwargs["path_or_fileobj"])
        return SimpleNamespace(oid="b" * 40)

    def repo_info(self, **kwargs):
        self.calls.append(("repo_info", kwargs))
        return SimpleNamespace(sha=self.head)

    def create_commit(self, **kwargs):
        self.calls.append(("create_commit", kwargs))
        if self.fail_create_commit:
            raise RuntimeError("parent commit mismatch")
        return SimpleNamespace(oid="e" * 40)


class StatefulApi(FakeApi):
    def __init__(self):
        super().__init__()
        self.current_files = set()
        self.next_oid = 1

    def _oid(self):
        oid = f"{self.next_oid:040x}"
        self.next_oid += 1
        self.head = oid
        return oid

    def upload_folder(self, **kwargs):
        self.calls.append(("upload_folder", kwargs))
        root = Path(kwargs["folder_path"])
        prefix = kwargs["path_in_repo"]
        files = {
            f"{prefix}/{path.relative_to(root).as_posix()}"
            for path in root.rglob("*")
            if path.is_file()
        }
        self.current_files.update(files)
        oid = self._oid()
        self._store_snapshot(root, prefix, oid)
        self.files_by_revision[oid] = sorted(self.current_files)
        return SimpleNamespace(oid=oid)

    def upload_file(self, **kwargs):
        self.calls.append(("upload_file", kwargs))
        self.current_files.add(kwargs["path_in_repo"])
        self.marker = bytes(kwargs["path_or_fileobj"])
        oid = self._oid()
        self.files_by_revision[oid] = sorted(self.current_files)
        return SimpleNamespace(oid=oid)

    def repo_info(self, **kwargs):
        self.calls.append(("repo_info", kwargs))
        return SimpleNamespace(sha=self.head)

    def create_commit(self, **kwargs):
        self.calls.append(("create_commit", kwargs))
        if kwargs["parent_commit"] != self.head:
            raise RuntimeError("parent commit mismatch")
        for operation in kwargs["operations"]:
            if operation.is_folder:
                prefix = operation.path_in_repo.rstrip("/") + "/"
                self.current_files = {
                    path for path in self.current_files if not path.startswith(prefix)
                }
            else:
                self.current_files.discard(operation.path_in_repo)
        oid = self._oid()
        self.files_by_revision[oid] = sorted(self.current_files)
        return SimpleNamespace(oid=oid)


class ResponseLossApi(StatefulApi):
    def __init__(self):
        super().__init__()
        self.lose_commit_response = False

    def create_commit(self, **kwargs):
        result = super().create_commit(**kwargs)
        if self.lose_commit_response:
            self.lose_commit_response = False
            raise RuntimeError("commit response lost")
        return result


def _write_progress(path: Path, deliverables=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "step2-progress-v2",
                "run_id": LINEAGE_ID,
                "ordered_task_ids": ["task-1"],
                "total_tasks": 1,
                "results": [
                    {
                        "task_id": "task-1",
                        "status": "success",
                        "deliverable_files": deliverables or [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_local_checkpoint(tmp_path, deliverables=None):
    progress = tmp_path / "progress.json"
    upload = tmp_path / "upload"
    _write_progress(progress, deliverables)
    for value in deliverables or []:
        path = upload / value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode("utf-8"))
    return progress, upload


def _remote_checkpoint(tmp_path, deliverables=None, sandbox_image_digest=""):
    progress, upload = _write_local_checkpoint(tmp_path / "source", deliverables)
    payload = relay._load_progress(progress)
    required = relay._required_deliverables(payload)
    files = relay._validate_exact_local_deliverables(upload, required)
    records = [
        relay._file_record(path, relative)
        for path, relative in zip(files, required, strict=True)
    ]
    progress_bytes = progress.read_bytes()
    generation = relay._generation(
        progress_bytes, records, sandbox_image_digest
    )
    revision = "a" * 40
    snapshot = tmp_path / "snapshot"
    generation_remote = relay._generation_root(SOURCE_SHA, LINEAGE_ID, generation)
    generation_root = snapshot / generation_remote
    generation_root.mkdir(parents=True)
    (generation_root / "progress.json").write_bytes(progress_bytes)
    for source, relative in zip(files, required, strict=True):
        destination = generation_root.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    marker = {
        "schema_version": relay.CHECKPOINT_SCHEMA,
        "generation": generation,
        "payload_revision": revision,
        "source_sha": SOURCE_SHA,
        "lineage_id": LINEAGE_ID,
        "sandbox_image_digest": sandbox_image_digest,
        "progress": {
            "path": "progress.json",
            "sha256": relay.hashlib.sha256(progress_bytes).hexdigest(),
            "size": len(progress_bytes),
        },
        "deliverables": records,
    }
    marker_path = tmp_path / "current.json"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    remote_paths = sorted(
        f"{generation_remote}/{record['path']}"
        for record in [marker["progress"], *records]
    )
    return marker_path, snapshot, revision, remote_paths


def _patch_remote(monkeypatch, marker_path, snapshot):
    monkeypatch.setattr(relay, "hf_hub_download", lambda **_kwargs: str(marker_path))
    monkeypatch.setattr(relay, "snapshot_download", lambda **_kwargs: str(snapshot))


def _uploaded_stateful_checkpoint(tmp_path, monkeypatch, api=None):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = api or StatefulApi()
    relay.upload_checkpoint(
        "owner/repository",
        token="token",
        source_sha=SOURCE_SHA,
        progress_path=progress,
        upload_root=upload,
        api=api,
    )
    marker_path = tmp_path / "current.json"
    marker_path.write_bytes(api.marker)
    marker_remote = relay._marker_path(SOURCE_SHA, LINEAGE_ID)

    def marker_download(**_kwargs):
        if marker_remote not in api.current_files:
            raise _hf_error(404)
        return str(marker_path)

    monkeypatch.setattr(relay, "hf_hub_download", marker_download)
    return api


def _write_prepared_checkpoint(tmp_path, monkeypatch, *, run_id="lineage"):
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(step2, "WORKSPACE_DIR", workspace)
    monkeypatch.setenv("GDPVAL_RELAY_LINEAGE_ID", "lineage")
    prepared = {
        "experiment_id": "exp-test",
        "source": "owner/repository",
        "tasks": [{"task_id": "task-1"}],
        "condition_a": {"name": "Baseline"},
        "condition_b": None,
        "execution": {"mode": "subprocess"},
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)
    workspace.mkdir(parents=True)
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    step2._save_progress(
        "exp-test",
        "Baseline",
        "subprocess",
        1,
        [{"task_id": "task-1", "status": "pending"}],
        "2026-07-22T00:00:00+00:00",
        workspace / "step2_inference_progress_condition_a.json",
        run_id=run_id,
        condition_identity="condition_a",
        ordered_task_ids=["task-1"],
        prepared_fingerprint=prepared["prepared_fingerprint"],
    )
    return prepared, workspace


def test_write_access_preflight_uses_exact_repo_id():
    api = FakeApi()

    relay.verify_write_access("openai/gdpval", token="token", api=api)

    assert api.calls == [
        (
            "auth_check",
            {
                "repo_id": "openai/gdpval",
                "repo_type": "dataset",
                "token": "token",
                "write": True,
            },
        )
    ]


def test_hf_sdk_exposes_required_write_revision_and_cas_parameters():
    assert "write" in inspect.signature(HfApi.auth_check).parameters
    assert "revision" in inspect.signature(HfApi.list_repo_files).parameters
    assert "parent_commit" in inspect.signature(HfApi.upload_file).parameters
    assert "parent_commit" in inspect.signature(HfApi.create_commit).parameters


def test_restore_uses_exact_repo_revision_and_manifest(tmp_path, monkeypatch):
    marker, snapshot, revision, remote_paths = _remote_checkpoint(
        tmp_path, ["deliverable_files/task-1/result.xlsx"]
    )
    _patch_remote(monkeypatch, marker, snapshot)
    api = FakeApi()
    api.files_by_revision[revision] = remote_paths
    progress = tmp_path / "restored" / "progress.json"
    upload = tmp_path / "restored" / "upload"

    relay.restore_checkpoint(
        "openai/gdpval",
        token="token",
        source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID,
        progress_path=progress,
        upload_root=upload,
        api=api,
    )

    assert json.loads(progress.read_text(encoding="utf-8"))["results"][0]["task_id"] == "task-1"
    assert (upload / "deliverable_files/task-1/result.xlsx").is_file()
    list_call = next(call for call in api.calls if call[0] == "list_repo_files")
    assert list_call[1]["repo_id"] == "openai/gdpval"
    assert list_call[1]["revision"] == revision


def test_restore_download_failure_is_fatal_before_local_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(
        relay,
        "hf_hub_download",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("HF unavailable")),
    )
    progress = tmp_path / "workspace" / "progress.json"

    with pytest.raises(RuntimeError, match="HF unavailable"):
        relay.restore_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            progress_path=progress,
            upload_root=tmp_path / "upload",
            api=FakeApi(),
        )

    assert not progress.exists()


def test_restore_rejects_remote_generation_extra(tmp_path, monkeypatch):
    marker, snapshot, revision, remote_paths = _remote_checkpoint(tmp_path)
    _patch_remote(monkeypatch, marker, snapshot)
    api = FakeApi()
    generation = json.loads(marker.read_text(encoding="utf-8"))["generation"]
    generation_remote = relay._generation_root(SOURCE_SHA, LINEAGE_ID, generation)
    api.files_by_revision[revision] = [
        *remote_paths,
        f"{generation_remote}/extra",
    ]
    progress = tmp_path / "restored.json"

    with pytest.raises(ValueError, match="remote generation tree mismatch"):
        relay.restore_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            progress_path=progress,
            upload_root=tmp_path / "upload",
            api=api,
        )

    assert not progress.exists()


def test_restore_rejects_hash_mismatch(tmp_path, monkeypatch):
    marker, snapshot, revision, remote_paths = _remote_checkpoint(
        tmp_path, ["deliverable_files/task-1/result.xlsx"]
    )
    marker_payload = json.loads(marker.read_text(encoding="utf-8"))
    generation_root = snapshot / relay._generation_root(
        SOURCE_SHA, LINEAGE_ID, marker_payload["generation"]
    )
    (generation_root / "deliverable_files/task-1/result.xlsx").write_bytes(b"corrupt")
    _patch_remote(monkeypatch, marker, snapshot)
    api = FakeApi()
    api.files_by_revision[revision] = remote_paths

    with pytest.raises(ValueError, match="file hash mismatch"):
        relay.restore_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            progress_path=tmp_path / "restored.json",
            upload_root=tmp_path / "upload",
            api=api,
        )


def test_restore_rejects_cross_run_marker_before_payload_download(tmp_path, monkeypatch):
    marker, snapshot, revision, remote_paths = _remote_checkpoint(tmp_path)
    _patch_remote(monkeypatch, marker, snapshot)
    api = FakeApi()
    api.files_by_revision[revision] = remote_paths

    with pytest.raises(ValueError, match="source or lineage mismatch"):
        relay.restore_checkpoint(
            "owner/repository",
            token="token",
            source_sha="d" * 40,
            lineage_id=LINEAGE_ID,
            progress_path=tmp_path / "restored.json",
            upload_root=tmp_path / "upload",
            api=api,
        )

    assert api.calls == []


def test_restore_rejects_sandbox_digest_mismatch_before_payload_download(
    tmp_path, monkeypatch
):
    marker, snapshot, revision, remote_paths = _remote_checkpoint(
        tmp_path, sandbox_image_digest=SANDBOX_DIGEST
    )
    _patch_remote(monkeypatch, marker, snapshot)
    api = FakeApi()
    api.files_by_revision[revision] = remote_paths

    with pytest.raises(ValueError, match="sandbox image digest mismatch"):
        relay.restore_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            sandbox_image_digest=(
                "ghcr.io/hyeonsangjeon/gdpval-sandbox@sha256:" + "e" * 64
            ),
            progress_path=tmp_path / "restored.json",
            upload_root=tmp_path / "upload",
            api=api,
        )

    assert api.calls == []


def test_restore_empty_generation_removes_local_stale_tree(tmp_path, monkeypatch):
    marker, snapshot, revision, remote_paths = _remote_checkpoint(tmp_path)
    _patch_remote(monkeypatch, marker, snapshot)
    api = FakeApi()
    api.files_by_revision[revision] = remote_paths
    upload = tmp_path / "restored" / "upload"
    stale = upload / "deliverable_files/task-1/stale.xlsx"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale")

    relay.restore_checkpoint(
        "owner/repository",
        token="token",
        source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID,
        progress_path=tmp_path / "restored/progress.json",
        upload_root=upload,
        api=api,
    )

    assert not (upload / "deliverable_files").exists()


def test_upload_rejects_missing_or_extra_files_before_hf_write(tmp_path):
    progress, upload = _write_local_checkpoint(
        tmp_path, ["deliverable_files/task-1/result.xlsx"]
    )
    api = FakeApi()
    (upload / "deliverable_files/task-1/result.xlsx").unlink()
    with pytest.raises(ValueError, match="tree mismatch"):
        relay.upload_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            progress_path=progress, upload_root=upload, api=api
        )
    assert api.calls == []

    required = upload / "deliverable_files/task-1/result.xlsx"
    required.parent.mkdir(parents=True, exist_ok=True)
    required.write_bytes(b"required")
    (upload / "deliverable_files/task-1/stale.xlsx").write_bytes(b"stale")
    with pytest.raises(ValueError, match="tree mismatch"):
        relay.upload_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            progress_path=progress, upload_root=upload, api=api
        )
    assert api.calls == []


def test_upload_partial_failure_never_advances_marker(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = FakeApi()
    api.fail_upload_folder = True
    api.marker = b"old-marker"

    with pytest.raises(RuntimeError, match="partial payload upload"):
        relay.upload_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            progress_path=progress, upload_root=upload, api=api
        )

    assert [call[0] for call in api.calls] == ["upload_folder"]
    assert api.marker == b"old-marker"


def test_upload_rejects_missing_result_task_before_hf_write(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    payload = json.loads(progress.read_text(encoding="utf-8"))
    payload["ordered_task_ids"].append("task-2")
    payload["total_tasks"] = 2
    progress.write_text(json.dumps(payload), encoding="utf-8")
    api = FakeApi()

    with pytest.raises(ValueError, match="result task IDs differ"):
        relay.upload_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            progress_path=progress, upload_root=upload, api=api
        )

    assert api.calls == []


def test_upload_rejects_incomplete_or_extra_payload_commit(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = FakeApi()
    api.files_by_revision[api.oid] = ["unexpected"]
    original_upload = api.upload_folder

    def upload_with_extra(**kwargs):
        result = original_upload(**kwargs)
        api.files_by_revision[api.oid].append(f"{kwargs['path_in_repo']}/extra")
        return result

    api.upload_folder = upload_with_extra

    with pytest.raises(ValueError, match="incomplete or contains extras"):
        relay.upload_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            progress_path=progress, upload_root=upload, api=api
        )

    assert api.marker is None
    assert [call[0] for call in api.calls] == ["upload_folder", "list_repo_files"]


@pytest.mark.parametrize(
    "remote_path",
    ["progress.json", "deliverable_files/task-1/result.xlsx"],
)
def test_upload_remote_byte_mismatch_never_advances_marker(tmp_path, remote_path):
    progress, upload = _write_local_checkpoint(
        tmp_path, ["deliverable_files/task-1/result.xlsx"]
    )
    api = FakeApi()
    api.marker = b"old-marker"
    api.corrupt_snapshot_path = remote_path

    with pytest.raises(ValueError, match="file hash mismatch"):
        relay.upload_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            progress_path=progress, upload_root=upload, api=api
        )

    assert api.marker == b"old-marker"
    assert [call[0] for call in api.calls] == ["upload_folder", "list_repo_files"]


def test_upload_marker_binds_payload_revision_and_cleanup_generation(tmp_path, monkeypatch):
    progress, upload = _write_local_checkpoint(
        tmp_path, ["deliverable_files/task-1/result.xlsx"]
    )
    api = FakeApi()

    relay.upload_checkpoint(
        "custom-owner/not-the-yaml-stem",
        token="token",
        source_sha=SOURCE_SHA,
        sandbox_image_digest=SANDBOX_DIGEST,
        progress_path=progress,
        upload_root=upload,
        api=api,
    )

    marker = json.loads(api.marker)
    assert marker["payload_revision"] == api.oid
    assert marker["sandbox_image_digest"] == SANDBOX_DIGEST
    marker_upload = next(call for call in api.calls if call[0] == "upload_file")
    assert marker_upload[1]["parent_commit"] == api.oid
    marker_path = tmp_path / "current.json"
    marker_path.write_bytes(api.marker)
    download_calls = []
    def marker_download(**kwargs):
        download_calls.append(kwargs)
        return str(marker_path)
    monkeypatch.setattr(relay, "hf_hub_download", marker_download)
    relay.cleanup_checkpoint(
        "custom-owner/not-the-yaml-stem", token="token",
        source_sha=SOURCE_SHA, lineage_id=LINEAGE_ID,
        sandbox_image_digest=SANDBOX_DIGEST, api=api
    )

    assert all(
        call[1]["repo_id"] == "custom-owner/not-the-yaml-stem"
        for call in api.calls
        if "repo_id" in call[1]
    )
    assert download_calls[0]["revision"] == api.head
    cleanup = next(call for call in api.calls if call[0] == "create_commit")
    assert cleanup[1]["parent_commit"] == api.head
    operations = cleanup[1]["operations"]
    assert [operation.path_in_repo for operation in operations] == [
        relay._lineage_root(SOURCE_SHA, LINEAGE_ID),
    ]


def test_cleanup_rejects_cross_run_marker_before_delete(tmp_path, monkeypatch):
    marker_path, _snapshot, _revision, _remote_paths = _remote_checkpoint(tmp_path)
    monkeypatch.setattr(relay, "hf_hub_download", lambda **_kwargs: str(marker_path))
    api = FakeApi()

    with pytest.raises(ValueError, match="source or lineage mismatch"):
        relay.cleanup_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id="different-lineage",
            api=api,
        )

    assert [call[0] for call in api.calls] == ["repo_info"]


def test_cleanup_head_race_fails_single_cas_without_separate_delete(tmp_path, monkeypatch):
    marker_path, _snapshot, _revision, _remote_paths = _remote_checkpoint(tmp_path)
    monkeypatch.setattr(relay, "hf_hub_download", lambda **_kwargs: str(marker_path))
    api = FakeApi()
    api.fail_create_commit = True

    with pytest.raises(RuntimeError, match="parent commit mismatch"):
        relay.cleanup_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            api=api,
        )

    assert [call[0] for call in api.calls] == [
        "repo_info", "create_commit", "repo_info"
    ]


def test_two_generations_then_cleanup_removes_lineage_current_tree(tmp_path, monkeypatch):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = StatefulApi()
    lineage_root = relay._lineage_root(SOURCE_SHA, LINEAGE_ID)

    relay.upload_checkpoint(
        "owner/repository",
        token="token",
        source_sha=SOURCE_SHA,
        progress_path=progress,
        upload_root=upload,
        api=api,
    )
    first_generation = json.loads(api.marker)["generation"]
    _write_progress(progress, ["deliverable_files/task-1/second.xlsx"])
    second = upload / "deliverable_files/task-1/second.xlsx"
    second.parent.mkdir(parents=True, exist_ok=True)
    second.write_bytes(b"second")
    relay.upload_checkpoint(
        "owner/repository",
        token="token",
        source_sha=SOURCE_SHA,
        progress_path=progress,
        upload_root=upload,
        api=api,
    )
    second_generation = json.loads(api.marker)["generation"]
    assert first_generation != second_generation
    assert any(first_generation in path for path in api.current_files)
    assert any(second_generation in path for path in api.current_files)

    marker_path = tmp_path / "current.json"
    marker_path.write_bytes(api.marker)
    monkeypatch.setattr(relay, "hf_hub_download", lambda **_kwargs: str(marker_path))
    relay.cleanup_checkpoint(
        "owner/repository",
        token="token",
        source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID,
        api=api,
    )

    assert not any(
        path == lineage_root or path.startswith(lineage_root + "/")
        for path in api.current_files
    )


def test_cleanup_retry_after_success_is_idempotent(tmp_path, monkeypatch):
    api = _uploaded_stateful_checkpoint(tmp_path, monkeypatch)

    relay.cleanup_checkpoint(
        "owner/repository", token="token", source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID, api=api
    )
    cleaned_head = api.head
    relay.cleanup_checkpoint(
        "owner/repository", token="token", source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID, api=api
    )

    assert [name for name, _kwargs in api.calls].count("create_commit") == 1
    assert api.calls[-1] == (
        "list_repo_files",
        {
            "repo_id": "owner/repository",
            "repo_type": "dataset",
            "revision": cleaned_head,
            "token": "token",
        },
    )


def test_cleanup_retry_after_commit_response_loss_is_idempotent(tmp_path, monkeypatch):
    api = _uploaded_stateful_checkpoint(tmp_path, monkeypatch, ResponseLossApi())
    api.lose_commit_response = True

    relay.cleanup_checkpoint(
        "owner/repository", token="token", source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID, api=api
    )
    assert [name for name, _kwargs in api.calls].count("create_commit") == 1
    assert [name for name, _kwargs in api.calls].count("repo_info") == 2


def test_cleanup_missing_marker_rejects_remaining_lineage(monkeypatch):
    api = StatefulApi()
    lineage_root = relay._lineage_root(SOURCE_SHA, LINEAGE_ID)
    remaining = f"{lineage_root}/generations/orphan/progress.json"
    api.current_files.add(remaining)
    api.files_by_revision[api.head] = [remaining]
    monkeypatch.setattr(
        relay, "hf_hub_download", lambda **_kwargs: (_ for _ in ()).throw(_hf_error(404))
    )

    with pytest.raises(RuntimeError, match="marker is missing while lineage files remain"):
        relay.cleanup_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID, api=api
        )

    assert [name for name, _kwargs in api.calls] == ["repo_info", "list_repo_files"]


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_cleanup_marker_remote_errors_are_fatal(status, monkeypatch):
    api = StatefulApi()
    error = _hf_error(status)
    monkeypatch.setattr(
        relay, "hf_hub_download", lambda **_kwargs: (_ for _ in ()).throw(error)
    )

    with pytest.raises(type(error)) as captured:
        relay.cleanup_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID, api=api
        )

    assert captured.value is error
    assert [name for name, _kwargs in api.calls] == ["repo_info"]


def test_upload_rejects_symlink_ancestor(tmp_path):
    progress, upload = _write_local_checkpoint(
        tmp_path, ["deliverable_files/task-1/result.xlsx"]
    )
    task_dir = upload / "deliverable_files/task-1"
    target = tmp_path / "outside"
    target.mkdir()
    (task_dir / "result.xlsx").unlink()
    task_dir.rmdir()
    task_dir.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        relay.upload_checkpoint(
            "owner/repository", token="token", source_sha=SOURCE_SHA,
            progress_path=progress, upload_root=upload, api=FakeApi()
        )


@pytest.mark.parametrize(
    "path",
    [
        "../escape.txt",
        "/absolute.txt",
        "deliverable_files/../escape.txt",
        "other/task.txt",
    ],
)
def test_relay_manifest_rejects_unsafe_paths(path):
    with pytest.raises(ValueError, match="relay deliverable path"):
        relay._required_deliverables({"results": [{"deliverable_files": [path]}]})


def test_checkpoint_identity_validation_never_constructs_model_client(tmp_path, monkeypatch):
    _write_prepared_checkpoint(tmp_path, monkeypatch)
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *_args, **_kwargs: pytest.fail("model client must not be constructed"),
    )

    progress = step2.validate_restored_checkpoint("condition_a")

    assert progress["run_id"] == "lineage"


def test_checkpoint_identity_rejects_lineage_before_model_client(tmp_path, monkeypatch):
    _write_prepared_checkpoint(tmp_path, monkeypatch, run_id="wrong-lineage")
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *_args, **_kwargs: pytest.fail("model client must not be constructed"),
    )

    with pytest.raises(ValueError, match="progress checkpoint identity mismatch"):
        step2.validate_restored_checkpoint("condition_a")


def test_checkpoint_identity_rejects_missing_result_before_model_client(tmp_path, monkeypatch):
    _prepared, workspace = _write_prepared_checkpoint(tmp_path, monkeypatch)
    progress_path = workspace / "step2_inference_progress_condition_a.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    progress["results"] = []
    progress_path.write_text(json.dumps(progress), encoding="utf-8")
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *_args, **_kwargs: pytest.fail("model client must not be constructed"),
    )

    with pytest.raises(ValueError, match="final result task IDs differ"):
        step2.validate_restored_checkpoint("condition_a")


def test_checkpoint_identity_rejects_prepared_fingerprint_drift(tmp_path, monkeypatch):
    prepared, workspace = _write_prepared_checkpoint(tmp_path, monkeypatch)
    prepared["tasks"].append({"task_id": "task-2"})
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *_args, **_kwargs: pytest.fail("model client must not be constructed"),
    )

    with pytest.raises(ValueError, match="prepared task fingerprint does not match payload"):
        step2.validate_restored_checkpoint("condition_a")


def test_checkpoint_identity_requires_restored_progress(tmp_path, monkeypatch):
    _prepared, workspace = _write_prepared_checkpoint(tmp_path, monkeypatch)
    (workspace / "step2_inference_progress_condition_a.json").unlink()

    with pytest.raises(FileNotFoundError, match="restored relay progress checkpoint is missing"):
        step2.validate_restored_checkpoint("condition_a")
