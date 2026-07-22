import inspect
import json
import shutil
import sys
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
_FAKE_DOWNLOAD_CALLS = None


@pytest.fixture(autouse=True)
def _fake_uploaded_snapshots(tmp_path, monkeypatch):
    global _FAKE_DOWNLOAD_CALLS, _FAKE_SNAPSHOT_ROOT
    _FAKE_SNAPSHOT_ROOT = tmp_path / "hf-snapshots"
    _FAKE_DOWNLOAD_CALLS = []

    def fake_snapshot_download(**kwargs):
        snapshot = _FAKE_SNAPSHOT_ROOT / kwargs["revision"]
        if not snapshot.is_dir():
            raise AssertionError(f"fake HF revision is unavailable: {kwargs['revision']}")
        return str(snapshot)

    def fake_hf_hub_download(**kwargs):
        _FAKE_DOWNLOAD_CALLS.append(kwargs)
        revision = kwargs.get("revision")
        if revision is None:
            raise AssertionError("fake HF file download requires an exact revision")
        path = _FAKE_SNAPSHOT_ROOT / revision / kwargs["filename"]
        if not path.is_file():
            raise _hf_error(404)
        return str(path)

    monkeypatch.setattr(relay, "snapshot_download", fake_snapshot_download)
    monkeypatch.setattr(relay, "hf_hub_download", fake_hf_hub_download)
    monkeypatch.setattr(
        relay, "LOCAL_GENERATION", tmp_path / "local/relay_checkpoint_generation"
    )
    yield
    _FAKE_SNAPSHOT_ROOT = None
    _FAKE_DOWNLOAD_CALLS = None


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
        self.commit_parents = {}
        self.commit_metadata = {}
        self.current_files = set()
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
        parent = self.head
        self._store_snapshot(root, prefix, self.oid)
        self.current_files.update(
            f"{prefix}/{path.relative_to(root).as_posix()}"
            for path in root.rglob("*")
            if path.is_file()
        )
        self.files_by_revision[self.oid] = sorted(self.current_files)
        self.commit_parents[self.oid] = parent
        self.head = self.oid
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

    def list_repo_commits(self, **kwargs):
        self.calls.append(("list_repo_commits", kwargs))
        commits = []
        revision = kwargs["revision"]
        while revision is not None:
            title, message = self.commit_metadata.get(revision, ("", ""))
            commits.append(SimpleNamespace(
                commit_id=revision,
                title=title,
                message=message,
            ))
            revision = self.commit_parents.get(revision)
        return commits

    def upload_file(self, **kwargs):
        self.calls.append(("upload_file", kwargs))
        if kwargs["parent_commit"] != self.head:
            raise RuntimeError("parent commit mismatch")
        oid = "b" * 40
        if kwargs["path_in_repo"].endswith("/current.json"):
            self.marker = bytes(kwargs["path_or_fileobj"])
        self.current_files.add(kwargs["path_in_repo"])
        self.files_by_revision[oid] = sorted(self.current_files)
        self.commit_parents[oid] = self.head
        self.head = oid
        assert _FAKE_SNAPSHOT_ROOT is not None
        marker_path = _FAKE_SNAPSHOT_ROOT / oid / kwargs["path_in_repo"]
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_bytes(bytes(kwargs["path_or_fileobj"]))
        return SimpleNamespace(oid=oid)

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
        parent = self.head
        files = {
            f"{prefix}/{path.relative_to(root).as_posix()}"
            for path in root.rglob("*")
            if path.is_file()
        }
        self.current_files.update(files)
        oid = self._oid()
        self.commit_parents[oid] = parent
        self._store_snapshot(root, prefix, oid)
        self.files_by_revision[oid] = sorted(self.current_files)
        return SimpleNamespace(oid=oid)

    def upload_file(self, **kwargs):
        self.calls.append(("upload_file", kwargs))
        if kwargs["parent_commit"] != self.head:
            raise RuntimeError("parent commit mismatch")
        parent = self.head
        self.current_files.add(kwargs["path_in_repo"])
        self.marker = bytes(kwargs["path_or_fileobj"])
        oid = self._oid()
        self.commit_parents[oid] = parent
        self.files_by_revision[oid] = sorted(self.current_files)
        assert _FAKE_SNAPSHOT_ROOT is not None
        marker_path = _FAKE_SNAPSHOT_ROOT / oid / kwargs["path_in_repo"]
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_bytes(self.marker)
        return SimpleNamespace(oid=oid)

    def repo_info(self, **kwargs):
        self.calls.append(("repo_info", kwargs))
        return SimpleNamespace(sha=self.head)

    def create_commit(self, **kwargs):
        self.calls.append(("create_commit", kwargs))
        if kwargs["parent_commit"] != self.head:
            raise RuntimeError("parent commit mismatch")
        parent = self.head
        for operation in kwargs["operations"]:
            if operation.is_folder:
                prefix = operation.path_in_repo.rstrip("/") + "/"
                self.current_files = {
                    path for path in self.current_files if not path.startswith(prefix)
                }
            else:
                self.current_files.discard(operation.path_in_repo)
        oid = self._oid()
        self.commit_parents[oid] = parent
        self.commit_metadata[oid] = (
            kwargs["commit_message"],
            kwargs.get("commit_description", ""),
        )
        self.files_by_revision[oid] = sorted(self.current_files)
        return SimpleNamespace(oid=oid)


class ResponseLossApi(StatefulApi):
    def __init__(self):
        super().__init__()
        self.lose_commit_response = False
        self.lose_upload_file_response = False
        self.fail_upload_file_before_mutation = False
        self.malformed_upload_file_response = False

    def upload_file(self, **kwargs):
        if self.fail_upload_file_before_mutation:
            self.calls.append(("upload_file", kwargs))
            raise RuntimeError("marker upload failed before mutation")
        result = super().upload_file(**kwargs)
        if self.lose_upload_file_response:
            self.lose_upload_file_response = False
            raise RuntimeError("marker upload response lost")
        if self.malformed_upload_file_response:
            self.malformed_upload_file_response = False
            return SimpleNamespace(oid="not-a-full-revision")
        return result

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
        marker_path.write_bytes(api.marker)
        return str(marker_path)

    monkeypatch.setattr(relay, "hf_hub_download", marker_download)
    return api


def _write_prepared_checkpoint(tmp_path, monkeypatch, *, run_id="lineage"):
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(step2, "WORKSPACE_DIR", workspace)
    monkeypatch.setenv("GDPVAL_RELAY_LINEAGE_ID", "lineage")
    prepared = {
        "experiment_id": "exp-test",
        "publication_generation": "lineage",
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

    restored_generation = relay.restore_checkpoint(
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
    generation = json.loads(marker.read_text(encoding="utf-8"))["generation"]
    assert restored_generation == generation
    assert relay.LOCAL_GENERATION.read_bytes() == generation.encode("ascii")
    list_call = next(call for call in api.calls if call[0] == "list_repo_files")
    assert list_call[1]["repo_id"] == "openai/gdpval"
    assert list_call[1]["revision"] == revision


def test_restore_commits_outputs_before_generation_state(tmp_path, monkeypatch):
    marker, snapshot, revision, remote_paths = _remote_checkpoint(
        tmp_path, ["deliverable_files/task-1/result.xlsx"]
    )
    _patch_remote(monkeypatch, marker, snapshot)
    api = FakeApi()
    api.files_by_revision[revision] = remote_paths
    progress = tmp_path / "restored/progress.json"
    upload = tmp_path / "restored/upload"
    generation_path = tmp_path / "restored/generation"
    original_write_generation_state = relay._write_generation_state
    observed_generation = []

    def assert_outputs_committed(path, generation):
        assert progress.is_file()
        assert (upload / "deliverable_files/task-1/result.xlsx").is_file()
        observed_generation.append(generation)
        original_write_generation_state(path, generation)

    monkeypatch.setattr(
        relay, "_write_generation_state", assert_outputs_committed
    )

    restored_generation = relay.restore_checkpoint(
        "owner/repository",
        token="token",
        source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID,
        progress_path=progress,
        upload_root=upload,
        generation_path=generation_path,
        api=api,
    )

    assert observed_generation == [restored_generation]
    assert generation_path.read_bytes() == restored_generation.encode("ascii")


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


def test_restore_rejects_generation_state_symlink_before_remote_access(
    tmp_path, monkeypatch
):
    target = tmp_path / "outside-generation"
    target.write_text("0" * 64, encoding="ascii")
    generation_path = tmp_path / "generation"
    generation_path.symlink_to(target)
    api = FakeApi()

    with pytest.raises(ValueError, match="generation state path is a symlink"):
        relay.restore_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            progress_path=tmp_path / "progress.json",
            upload_root=tmp_path / "upload",
            generation_path=generation_path,
            api=api,
        )

    assert api.calls == []


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


def test_upload_marker_response_loss_reconciles_without_retry(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = ResponseLossApi()
    api.lose_upload_file_response = True

    relay.upload_checkpoint(
        "owner/repository",
        token="token",
        source_sha=SOURCE_SHA,
        progress_path=progress,
        upload_root=upload,
        api=api,
    )

    assert [name for name, _kwargs in api.calls].count("upload_file") == 1
    assert [name for name, _kwargs in api.calls].count("list_repo_commits") == 1


def test_upload_marker_failure_before_mutation_propagates_without_retry(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = ResponseLossApi()
    api.fail_upload_file_before_mutation = True

    with pytest.raises(RuntimeError, match="failed before mutation"):
        relay.upload_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            progress_path=progress,
            upload_root=upload,
            api=api,
        )

    assert [name for name, _kwargs in api.calls].count("upload_file") == 1
    assert [name for name, _kwargs in api.calls].count("list_repo_commits") == 0
    assert api.head == f"{1:040x}"


def test_upload_marker_malformed_response_reconciles_without_retry(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = ResponseLossApi()
    api.malformed_upload_file_response = True

    relay.upload_checkpoint(
        "owner/repository",
        token="token",
        source_sha=SOURCE_SHA,
        progress_path=progress,
        upload_root=upload,
        api=api,
    )

    assert [name for name, _kwargs in api.calls].count("upload_file") == 1
    assert [name for name, _kwargs in api.calls].count("list_repo_commits") == 1


def test_upload_marker_rejects_unrelated_concurrent_commit(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = StatefulApi()
    original_upload_file = api.upload_file

    def upload_then_advance(**kwargs):
        result = original_upload_file(**kwargs)
        parent = api.head
        unrelated = api._oid()
        api.commit_parents[unrelated] = parent
        api.files_by_revision[unrelated] = sorted(api.current_files)
        return result

    api.upload_file = upload_then_advance

    with pytest.raises(RuntimeError, match="HEAD does not match the candidate"):
        relay.upload_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            progress_path=progress,
            upload_root=upload,
            api=api,
        )

    assert [name for name, _kwargs in api.calls].count("upload_file") == 1


def test_upload_marker_rejects_different_remote_bytes(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = StatefulApi()
    original_upload_file = api.upload_file

    def upload_then_corrupt(**kwargs):
        result = original_upload_file(**kwargs)
        assert _FAKE_SNAPSHOT_ROOT is not None
        marker_path = _FAKE_SNAPSHOT_ROOT / result.oid / kwargs["path_in_repo"]
        marker_path.write_bytes(b"not-the-intended-marker")
        return result

    api.upload_file = upload_then_corrupt

    with pytest.raises(RuntimeError, match="current.json bytes"):
        relay.upload_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            progress_path=progress,
            upload_root=upload,
            api=api,
        )

    assert [name for name, _kwargs in api.calls].count("upload_file") == 1


def test_upload_marker_rejects_wrong_direct_parent(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = StatefulApi()
    original_upload_file = api.upload_file

    def upload_with_wrong_parent(**kwargs):
        result = original_upload_file(**kwargs)
        api.commit_parents[result.oid] = "e" * 40
        return result

    api.upload_file = upload_with_wrong_parent

    with pytest.raises(RuntimeError, match="direct parent"):
        relay.upload_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            progress_path=progress,
            upload_root=upload,
            api=api,
        )

    assert [name for name, _kwargs in api.calls].count("upload_file") == 1


def test_upload_marker_rejects_final_head_advance(tmp_path):
    progress, upload = _write_local_checkpoint(tmp_path)
    api = StatefulApi()
    repo_info_calls = 0

    def advancing_repo_info(**kwargs):
        nonlocal repo_info_calls
        api.calls.append(("repo_info", kwargs))
        repo_info_calls += 1
        if repo_info_calls == 2:
            parent = api.head
            unrelated = api._oid()
            api.commit_parents[unrelated] = parent
            api.files_by_revision[unrelated] = sorted(api.current_files)
        return SimpleNamespace(sha=api.head)

    api.repo_info = advancing_repo_info

    with pytest.raises(RuntimeError, match="advanced during verification"):
        relay.upload_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            progress_path=progress,
            upload_root=upload,
            api=api,
        )

    assert [name for name, _kwargs in api.calls].count("upload_file") == 1


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
    assert [name for name, _kwargs in api.calls].count("upload_file") == 1
    history_call = next(call for call in api.calls if call[0] == "list_repo_commits")
    assert history_call[1]["revision"] == api.head
    assert [name for name, _kwargs in api.calls].count("repo_info") == 2
    assert _FAKE_DOWNLOAD_CALLS[-1]["revision"] == api.head
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
        expected_generation=marker["generation"],
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
    assert cleanup[1]["commit_message"] == (
        f"Clean relay checkpoint {marker['generation'][:12]}"
    )
    assert cleanup[1]["commit_description"] == (
        f"relay-cleanup-generation: {marker['generation']}"
    )
    operations = cleanup[1]["operations"]
    assert [operation.path_in_repo for operation in operations] == [
        relay._lineage_root(SOURCE_SHA, LINEAGE_ID),
    ]


def test_cleanup_rejects_newer_generation_before_delete(tmp_path, monkeypatch):
    marker_path, _snapshot, _revision, _remote_paths = _remote_checkpoint(tmp_path)
    monkeypatch.setattr(relay, "hf_hub_download", lambda **_kwargs: str(marker_path))
    api = FakeApi()
    current_generation = json.loads(marker_path.read_text())["generation"]
    expected_generation = "0" * 64
    assert expected_generation != current_generation

    with pytest.raises(ValueError, match="newer or different generation"):
        relay.cleanup_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            expected_generation=expected_generation,
            api=api,
        )

    assert [name for name, _kwargs in api.calls] == ["repo_info"]


@pytest.mark.parametrize("expected_generation", ["A" * 64, "a" * 63, "a" * 65])
def test_cleanup_rejects_invalid_expected_generation_before_remote_access(
    expected_generation,
):
    api = FakeApi()

    with pytest.raises(ValueError, match="generation is invalid"):
        relay.cleanup_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            expected_generation=expected_generation,
            api=api,
        )

    assert api.calls == []


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
            expected_generation=json.loads(marker_path.read_text())["generation"],
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
            expected_generation=json.loads(marker_path.read_text())["generation"],
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
        expected_generation=second_generation,
        api=api,
    )

    assert not any(
        path == lineage_root or path.startswith(lineage_root + "/")
        for path in api.current_files
    )


def test_cleanup_retry_after_success_is_idempotent(tmp_path, monkeypatch):
    api = _uploaded_stateful_checkpoint(tmp_path, monkeypatch)
    generation = json.loads(api.marker)["generation"]

    relay.cleanup_checkpoint(
        "owner/repository", token="token", source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID, expected_generation=generation, api=api
    )
    cleaned_head = api.head
    relay.cleanup_checkpoint(
        "owner/repository", token="token", source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID, expected_generation=generation, api=api
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
    generation = json.loads(api.marker)["generation"]
    api.lose_commit_response = True
    repo_info_calls = [name for name, _kwargs in api.calls].count("repo_info")

    relay.cleanup_checkpoint(
        "owner/repository", token="token", source_sha=SOURCE_SHA,
        lineage_id=LINEAGE_ID, expected_generation=generation, api=api
    )
    assert [name for name, _kwargs in api.calls].count("create_commit") == 1
    assert (
        [name for name, _kwargs in api.calls].count("repo_info")
        - repo_info_calls
        == 2
    )


def test_cleanup_response_loss_rejects_full_generation_marker_drift(
    tmp_path, monkeypatch
):
    api = _uploaded_stateful_checkpoint(tmp_path, monkeypatch, ResponseLossApi())
    generation = json.loads(api.marker)["generation"]
    api.lose_commit_response = True
    original_create_commit = api.create_commit

    def commit_with_tampered_description(**kwargs):
        try:
            return original_create_commit(**kwargs)
        except RuntimeError:
            title, _description = api.commit_metadata[api.head]
            api.commit_metadata[api.head] = (
                title,
                f"relay-cleanup-generation: {'f' * 64}",
            )
            raise

    api.create_commit = commit_with_tampered_description

    with pytest.raises(ValueError, match="cleanup commit identity mismatch"):
        relay.cleanup_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            expected_generation=generation,
            api=api,
        )

    assert [name for name, _kwargs in api.calls].count("create_commit") == 1


def test_cleanup_response_loss_rejects_newer_lineage(tmp_path, monkeypatch):
    api = _uploaded_stateful_checkpoint(tmp_path, monkeypatch, ResponseLossApi())
    expected_generation = json.loads(api.marker)["generation"]
    marker_remote = relay._marker_path(SOURCE_SHA, LINEAGE_ID)
    original_create_commit = api.create_commit

    def commit_then_publish_newer_lineage(**kwargs):
        original_create_commit(**kwargs)
        newer_marker = json.loads(api.marker)
        newer_marker["generation"] = "e" * 64
        api.marker = json.dumps(
            newer_marker, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        newer_payload = (
            relay._generation_root(SOURCE_SHA, LINEAGE_ID, "e" * 64)
            + "/progress.json"
        )
        api.current_files.update({marker_remote, newer_payload})
        parent = api.head
        newer_revision = api._oid()
        api.commit_parents[newer_revision] = parent
        api.files_by_revision[newer_revision] = sorted(api.current_files)
        raise RuntimeError("cleanup response lost")

    api.create_commit = commit_then_publish_newer_lineage

    with pytest.raises(ValueError, match="newer or different generation"):
        relay.cleanup_checkpoint(
            "owner/repository",
            token="token",
            source_sha=SOURCE_SHA,
            lineage_id=LINEAGE_ID,
            expected_generation=expected_generation,
            api=api,
        )

    assert [name for name, _kwargs in api.calls].count("create_commit") == 1
    assert marker_remote in api.current_files


def test_cleanup_cli_reads_default_generation_state(tmp_path, monkeypatch):
    generation = "a" * 64
    generation_path = tmp_path / "relay_checkpoint_generation"
    generation_path.write_bytes(generation.encode("ascii"))
    captured = {}

    def capture_cleanup(repo_id, **kwargs):
        captured["repo_id"] = repo_id
        captured.update(kwargs)

    monkeypatch.setattr(relay, "LOCAL_GENERATION", generation_path)
    monkeypatch.setattr(relay, "cleanup_checkpoint", capture_cleanup)
    monkeypatch.setenv("HF_TOKEN", "token")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "relay_checkpoint.py",
            "cleanup",
            "--repo-id",
            "owner/repository",
            "--source-sha",
            SOURCE_SHA,
            "--lineage-id",
            LINEAGE_ID,
        ],
    )

    relay.main()

    assert captured["expected_generation"] == generation


def test_workflow_passes_validated_restored_generation_to_cleanup():
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/batch-run.yml"
    ).read_text(encoding="utf-8")

    assert "id: restore_checkpoint" in workflow
    assert '[[ "$RESTORED_GENERATION" =~ ^[0-9a-f]{64}$ ]]' in workflow
    assert (
        "printf 'generation=%s\\n' \"$RESTORED_GENERATION\" >> \"$GITHUB_OUTPUT\""
        in workflow
    )
    assert (
        "EXPECTED_GENERATION: ${{ steps.restore_checkpoint.outputs.generation }}"
        in workflow
    )
    assert '--expected-generation "$EXPECTED_GENERATION"' in workflow


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
            lineage_id=LINEAGE_ID, expected_generation="a" * 64, api=api
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
            lineage_id=LINEAGE_ID, expected_generation="a" * 64, api=api
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


@pytest.mark.parametrize("status", sorted(relay.RESULT_STATUSES))
def test_relay_progress_accepts_only_known_result_statuses(status):
    payload = {
        "ordered_task_ids": ["task-1"],
        "results": [{"task_id": "task-1", "status": status}],
    }

    relay._validate_complete_task_set(payload)


def test_relay_progress_rejects_unknown_result_status():
    payload = {
        "ordered_task_ids": ["task-1"],
        "results": [{"task_id": "task-1", "status": "unknown"}],
    }

    with pytest.raises(ValueError, match="result status"):
        relay._validate_complete_task_set(payload)


@pytest.mark.parametrize(
    ("statuses", "exit_code", "expected"),
    [
        (["success"], "0", (0, False)),
        (["error"], "1", (0, False)),
        (["qa_failed"], "2", (0, False)),
        (["pending"], "42", (1, True)),
        (["success", "pending"], "42", (1, True)),
    ],
)
def test_relay_status_uses_validated_result_statuses(
    tmp_path, statuses, exit_code, expected
):
    progress = tmp_path / "progress.json"
    task_ids = [f"task-{index}" for index in range(len(statuses))]
    progress.write_text(json.dumps({
        "ordered_task_ids": task_ids,
        "total_tasks": len(task_ids),
        "results": [
            {"task_id": task_id, "status": status}
            for task_id, status in zip(task_ids, statuses, strict=True)
        ],
    }), encoding="utf-8")

    assert relay.resolve_relay_status(progress, exit_code) == expected


@pytest.mark.parametrize(
    ("status", "exit_code", "message"),
    [
        ("success", "42", "without pending tasks"),
        ("pending", "0", "without checkpoint exit code 42"),
        ("pending", "1", "without checkpoint exit code 42"),
    ],
)
def test_relay_status_rejects_exit_and_pending_mismatch(
    tmp_path, status, exit_code, message
):
    progress = tmp_path / "progress.json"
    progress.write_text(json.dumps({
        "ordered_task_ids": ["task-1"],
        "total_tasks": 1,
        "results": [{"task_id": "task-1", "status": status}],
    }), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        relay.resolve_relay_status(progress, exit_code)


@pytest.mark.parametrize(
    "exit_code",
    [None, True, 42, "", "-1", "1+1", "042", "256"],
)
def test_relay_status_rejects_noncanonical_exit_code(tmp_path, exit_code):
    progress = tmp_path / "progress.json"
    _write_progress(progress)

    with pytest.raises(ValueError, match="exit code"):
        relay.resolve_relay_status(progress, exit_code)


@pytest.mark.parametrize("status", [None, True, -1, "", "1+1", "unknown"])
def test_relay_status_rejects_malformed_pending_status(tmp_path, status):
    progress = tmp_path / "progress.json"
    progress.write_text(json.dumps({
        "ordered_task_ids": ["task-1"],
        "total_tasks": 1,
        "results": [{"task_id": "task-1", "status": status}],
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="result status is invalid"):
        relay.resolve_relay_status(progress, "0")


def test_relay_status_rejects_total_task_mismatch(tmp_path):
    progress = tmp_path / "progress.json"
    _write_progress(progress)
    payload = json.loads(progress.read_text(encoding="utf-8"))
    payload["total_tasks"] = 2
    progress.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="total task count"):
        relay.resolve_relay_status(progress, "0")


def test_relay_status_writes_only_validated_outputs(tmp_path):
    progress = tmp_path / "progress.json"
    output = tmp_path / "github-output"
    _write_progress(progress)

    assert relay.write_relay_status(progress, "0", output) == (0, False)
    assert output.read_text(encoding="utf-8") == (
        "pending_count=0\nneeds_relay=false\n"
    )


def test_relay_progress_rejects_cross_task_deliverable_path():
    payload = {
        "results": [{
            "task_id": "task-1",
            "deliverable_files": ["deliverable_files/task-2/result.xlsx"],
        }],
    }

    with pytest.raises(ValueError, match="not owned by result task"):
        relay._required_deliverables(payload)


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
