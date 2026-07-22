import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from huggingface_hub.utils import hf_raise_for_status

import core.repo_bootstrapper as bootstrapper
from core.needs_files import NeedsFilesManifest
from core.prepared_fingerprint import prepared_fingerprint
from core.source_identity import (
    ordered_source_projection_sha256,
    source_task_projection_sha256,
)


def _hf_error(status, code=None):
    headers = {"X-Error-Code": code} if code else {}
    response = httpx.Response(
        status,
        request=httpx.Request(
            "GET", "https://huggingface.co/api/datasets/owner/disposable"
        ),
        headers=headers,
    )
    try:
        hf_raise_for_status(response)
    except Exception as exc:
        return exc
    raise AssertionError("expected HF HTTP error")


class Frame:
    def __init__(self, references):
        self.columns = ["reference_files"]
        self.references = references

    def __getitem__(self, key):
        assert key == "reference_files"
        return self.references


class TaskFrame:
    columns = [
        "task_id",
        "sector",
        "occupation",
        "prompt",
        "rubric_pretty",
        "rubric_json",
        "reference_files",
        "reference_file_urls",
        "reference_file_hf_uris",
    ]

    def __init__(self, task_ids):
        self.task_ids = task_ids

    def __getitem__(self, key):
        if key == "task_id":
            return self.task_ids
        if key in {
            "reference_files",
            "reference_file_urls",
            "reference_file_hf_uris",
        }:
            return [[] for _task_id in self.task_ids]
        values = {
            "sector": "sector",
            "occupation": "occupation",
            "prompt": "prompt",
            "rubric_pretty": "rubric pretty",
            "rubric_json": "{}",
        }
        return [values[key] for _task_id in self.task_ids]


def _canonical_manifest(total=220, needs_count=185):
    tasks = {}
    source_hashes = []
    for index in range(total):
        task_id = f"task-{index:03d}"
        source_hash = source_task_projection_sha256(
            task_id=task_id,
            sector="sector",
            occupation="occupation",
            prompt="prompt",
            rubric_pretty="rubric pretty",
            rubric_json="{}",
            reference_files=[],
            reference_file_urls=[],
            reference_file_hf_uris=[],
        )
        source_hashes.append(source_hash)
        needs_files = index < needs_count
        original_files = [f"deliverable_files/{task_id}/result.txt"] if needs_files else []
        tasks[task_id] = {
            "needs_files": needs_files,
            "original_file_count": len(original_files),
            "original_files": original_files,
            "has_deliverable_files": needs_files,
            "prompt_classification": {
                "requires_file": needs_files,
                "explicit_exts": [],
                "inferred_exts": [],
                "confidence": "explicit" if needs_files else "text_only",
            },
            "policy_results": {
                policy: needs_files
                for policy in bootstrapper.NEEDS_FILES_POLICIES_KNOWN
            },
            "source_projection_sha256": source_hash,
        }
    task_ids = list(tasks)
    return {
        "_description": "test manifest",
        "_schema_version": 4,
        "_source": bootstrapper.DATASET_ID,
        "_source_revision": bootstrapper.SOURCE_REVISION,
        "_total_tasks": total,
        "_ordered_task_ids_sha256": bootstrapper._compact_json_sha256(task_ids),
        "_source_projection_sha256": ordered_source_projection_sha256(
            source_hashes
        ),
        "reference_files": {},
        "tasks": tasks,
        "_summary": {
            "needs_files": needs_count,
            "text_only": total - needs_count,
            "active_policy": "deliverable_only",
            "policy_counts": {
                policy: needs_count
                for policy in bootstrapper.NEEDS_FILES_POLICIES_KNOWN
            },
            "confidence_distribution": {
                "explicit": needs_count,
                "inferred": 0,
                "ambiguous": 0,
                "text_only": total - needs_count,
            },
        },
    }


def _manifest_bytes(manifest):
    return json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")


def _anchor_test_manifest(monkeypatch, manifest, encoded=None):
    encoded = encoded or _manifest_bytes(manifest)
    ordered_digest = bootstrapper._compact_json_sha256(list(manifest["tasks"]))
    monkeypatch.setattr(
        bootstrapper, "CANONICAL_ORDERED_TASK_IDS_SHA256", ordered_digest
    )
    monkeypatch.setattr(
        bootstrapper,
        "CANONICAL_SOURCE_PROJECTION_SHA256",
        manifest["_source_projection_sha256"],
    )
    monkeypatch.setattr(
        bootstrapper,
        "CANONICAL_MANIFEST_SHA256_BY_POLICY",
        {
            "deliverable_only": hashlib.sha256(encoded).hexdigest(),
        },
    )
    return encoded


def _anchor_manifest_bytes(monkeypatch, encoded):
    monkeypatch.setattr(
        bootstrapper,
        "CANONICAL_MANIFEST_SHA256_BY_POLICY",
        {"deliverable_only": hashlib.sha256(encoded).hexdigest()},
    )


def _install_fake_snapshot_contract(
    instance,
    monkeypatch,
    *,
    target_data=b"approved",
    source_data=b"approved",
    target_manifest=b"manifest",
    source_manifest=b"manifest",
    omit_target_manifest=False,
):
    _anchor_manifest_bytes(monkeypatch, source_manifest)
    downloads = []

    def download(**kwargs):
        downloads.append(kwargs)
        root = Path(kwargs["local_dir"])
        (root / "data").mkdir()
        (root / "data/train-00000-of-00001.parquet").write_bytes(target_data)
        (root / "reference_files").mkdir()
        if not omit_target_manifest:
            (root / bootstrapper.MANIFEST_FILENAME).write_bytes(target_manifest)

    def validation_errors(root, manifest_path):
        try:
            content = Path(manifest_path).read_bytes()
        except FileNotFoundError:
            return ["Canonical needs-files manifest not found"]
        digest_error = bootstrapper._canonical_manifest_digest_error(content)
        if digest_error:
            return [digest_error]
        data = Path(root) / "data/train-00000-of-00001.parquet"
        if data.read_bytes() != source_data:
            return ["source projection differs from pinned source"]
        return []

    monkeypatch.setattr(bootstrapper, "snapshot_download", download)
    monkeypatch.setattr(instance, "_snapshot_validation_errors", validation_errors)
    return downloads


class FakeApi:
    def __init__(self):
        self.whoami_error = None
        self.create_error = None
        self.list_error = None
        self.list_responses = []
        self.files = []
        self.calls = []
        self.uploaded_manifest = None
        self.uploaded_digest = None
        self.upload_error = None
        self.head = "d" * 40
        self.repo_info_error = None

    def whoami(self, **kwargs):
        self.calls.append(("whoami", kwargs))
        if self.whoami_error is not None:
            raise self.whoami_error
        return {"name": "owner"}

    def create_repo(self, **kwargs):
        self.calls.append(("create_repo", kwargs))
        if self.create_error is not None:
            raise self.create_error
        return object()

    def list_repo_files(self, **kwargs):
        self.calls.append(("list_repo_files", kwargs))
        if self.list_responses:
            response = self.list_responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        if self.list_error is not None:
            raise self.list_error
        return self.files

    def delete_repo(self, **kwargs):
        self.calls.append(("delete_repo", kwargs))

    def upload_folder(self, **kwargs):
        self.calls.append(("upload_folder", kwargs))
        if self.upload_error is not None:
            raise self.upload_error
        self.uploaded_manifest = (
            Path(kwargs["folder_path"]) / bootstrapper.MANIFEST_FILENAME
        ).read_bytes()
        self.uploaded_digest = bootstrapper.RepoBootstrapper._snapshot_payload_sha256(
            Path(kwargs["folder_path"])
        )
        return object()

    def repo_info(self, **kwargs):
        self.calls.append(("repo_info", kwargs))
        if self.repo_info_error is not None:
            raise self.repo_info_error
        return SimpleNamespace(sha=self.head)


def _bootstrapper(api):
    instance = bootstrapper.RepoBootstrapper.__new__(bootstrapper.RepoBootstrapper)
    instance.submission_repo_id = "owner/disposable"
    instance.token = "token"
    instance.private = False
    instance.api = api
    return instance


def _install_prepared_source(instance, monkeypatch, *, content=b"approved"):
    prepared = []

    def prepare(root):
        source_root = Path(root)
        data = source_root / "data"
        data.mkdir()
        (data / bootstrapper.CANONICAL_PARQUET_FILENAME).write_bytes(content)
        manifest = source_root / bootstrapper.MANIFEST_FILENAME
        manifest.write_bytes(b"manifest")
        (source_root / ".gitattributes").write_text("*.parquet filter=lfs\n")
        prepared.append(
            bootstrapper.RepoBootstrapper._snapshot_payload_sha256(source_root)
        )
        return manifest

    monkeypatch.setattr(instance, "_prepare_pinned_source_snapshot", prepare)
    return prepared


def test_valid_identity_and_missing_repo_create_then_bootstrap(monkeypatch):
    api = FakeApi()
    api.list_error = _hf_error(404, "RepoNotFound")
    instance = _bootstrapper(api)
    prepared = _install_prepared_source(instance, monkeypatch)

    instance._ensure_remote_repo()

    assert [name for name, _kwargs in api.calls] == [
        "whoami", "list_repo_files", "create_repo", "upload_folder"
    ]
    create = api.calls[2][1]
    assert create["exist_ok"] is False
    assert create["private"] is False
    assert prepared == [api.uploaded_digest]
    assert not any(name == "delete_repo" for name, _kwargs in api.calls)


@pytest.mark.parametrize(
    "error",
    [
        _hf_error(401, "RepoNotFound"),
        _hf_error(403, "GatedRepo"),
        _hf_error(429),
        _hf_error(500),
        TimeoutError("timeout"),
    ],
)
def test_identity_errors_are_fatal_before_create(error):
    api = FakeApi()
    api.whoami_error = error
    instance = _bootstrapper(api)

    with pytest.raises(type(error)) as captured:
        instance._ensure_remote_repo()
    assert captured.value is error
    assert [name for name, _kwargs in api.calls] == ["whoami"]


@pytest.mark.parametrize(
    "error",
    [
        _hf_error(401, "RepoNotFound"),
        _hf_error(403, "GatedRepo"),
        _hf_error(429),
        _hf_error(500),
        TimeoutError("timeout"),
    ],
)
def test_create_errors_other_than_conflict_are_fatal_without_followup(error):
    api = FakeApi()
    api.list_error = _hf_error(404, "RepoNotFound")
    api.create_error = error
    instance = _bootstrapper(api)
    instance._prepare_pinned_source_snapshot = lambda root: (
        Path(root, "data").mkdir(),
        Path(root, "data", bootstrapper.CANONICAL_PARQUET_FILENAME).write_bytes(b"data"),
    )[-1]

    with pytest.raises(type(error)) as captured:
        instance._ensure_remote_repo()
    assert captured.value is error
    assert [name for name, _kwargs in api.calls] == [
        "whoami", "list_repo_files", "create_repo"
    ]


def test_existing_empty_repo_is_never_deleted():
    api = FakeApi()
    api.create_error = _hf_error(409)
    instance = _bootstrapper(api)

    with pytest.raises(RuntimeError, match="refusing automatic repository deletion"):
        instance._ensure_remote_repo()

    assert [name for name, _kwargs in api.calls] == [
        "whoami", "list_repo_files"
    ]


def test_existing_data_repo_is_reused(monkeypatch):
    api = FakeApi()
    api.files = ["README.md", "data/train-00000-of-00001.parquet"]
    instance = _bootstrapper(api)
    monkeypatch.setattr(
        instance,
        "_prepare_pinned_source_snapshot",
        lambda: pytest.fail("existing data repo must not be recreated"),
    )

    instance._ensure_remote_repo()

    assert [name for name, _kwargs in api.calls] == [
        "whoami", "list_repo_files"
    ]


@pytest.mark.parametrize(
    "error",
    [_hf_error(401, "RepoNotFound"), _hf_error(403, "GatedRepo")],
)
def test_inaccessible_existing_repo_does_not_fall_through_to_content(error):
    api = FakeApi()
    api.list_error = error
    instance = _bootstrapper(api)

    with pytest.raises(type(error)) as captured:
        instance._ensure_remote_repo()
    assert captured.value is error
    assert [name for name, _kwargs in api.calls] == ["whoami", "list_repo_files"]


@pytest.mark.parametrize(
    "error",
    [_hf_error(401, "RepoNotFound"), _hf_error(403, "GatedRepo"), _hf_error(429), _hf_error(500), TimeoutError("timeout")],
)
def test_existing_repo_content_lookup_errors_are_fatal(error):
    api = FakeApi()
    api.list_error = error
    instance = _bootstrapper(api)

    with pytest.raises(type(error)) as captured:
        instance._ensure_remote_repo()
    assert captured.value is error
    assert [name for name, _kwargs in api.calls] == [
        "whoami", "list_repo_files"
    ]


def test_new_target_upload_persists_source_manifest(tmp_path, monkeypatch):
    api = FakeApi()
    api.list_error = _hf_error(404, "RepoNotFound")
    instance = _bootstrapper(api)
    instance.manifest_path = tmp_path / "workspace" / bootstrapper.MANIFEST_FILENAME
    canonical = _canonical_manifest()
    encoded = json.dumps(canonical, sort_keys=True).encode()

    def prepare(source_dir):
        manifest_path = Path(source_dir) / bootstrapper.MANIFEST_FILENAME
        manifest_path.write_bytes(encoded)
        return manifest_path

    monkeypatch.setattr(instance, "_prepare_pinned_source_snapshot", prepare)

    instance._ensure_remote_repo()

    assert api.uploaded_manifest == encoded


def test_source_prepare_failure_never_creates_or_uploads(monkeypatch):
    api = FakeApi()
    api.list_error = _hf_error(404, "RepoNotFound")
    instance = _bootstrapper(api)
    monkeypatch.setattr(
        instance,
        "_prepare_pinned_source_snapshot",
        lambda _root: (_ for _ in ()).throw(ValueError("source invalid")),
    )

    with pytest.raises(ValueError, match="source invalid"):
        instance._ensure_remote_repo()

    assert [name for name, _kwargs in api.calls] == [
        "whoami", "list_repo_files"
    ]


def test_upload_failure_is_not_retried_or_deleted(monkeypatch):
    api = FakeApi()
    api.list_error = _hf_error(404, "RepoNotFound")
    api.upload_error = TimeoutError("upload outcome unknown")
    instance = _bootstrapper(api)
    prepared = _install_prepared_source(instance, monkeypatch)

    with pytest.raises(RuntimeError, match="incomplete or unverified"):
        instance._ensure_remote_repo()

    assert len(prepared) == 1
    assert [name for name, _kwargs in api.calls].count("create_repo") == 1
    assert [name for name, _kwargs in api.calls].count("upload_folder") == 1
    assert [name for name, _kwargs in api.calls].count("delete_repo") == 0


def test_post_create_payload_drift_never_uploads_retries_or_deletes(monkeypatch):
    api = FakeApi()
    api.list_error = _hf_error(404, "RepoNotFound")
    instance = _bootstrapper(api)
    _install_prepared_source(instance, monkeypatch)
    digests = iter(("a" * 64, "b" * 64))
    monkeypatch.setattr(instance, "_snapshot_payload_sha256", lambda _root: next(digests))

    with pytest.raises(RuntimeError, match="changed after validation"):
        instance._ensure_remote_repo()

    assert [name for name, _kwargs in api.calls].count("create_repo") == 1
    assert [name for name, _kwargs in api.calls].count("upload_folder") == 0
    assert [name for name, _kwargs in api.calls].count("delete_repo") == 0


@pytest.mark.parametrize(
    ("race_response", "message"),
    [
        (["data/train-00000-of-00001.parquet"], None),
        ([], "concurrently created without a data"),
        (_hf_error(404, "RepoNotFound"), "could not be reconciled"),
    ],
)
def test_create_conflict_is_reclassified_read_only(
    monkeypatch, race_response, message
):
    api = FakeApi()
    api.list_responses = [_hf_error(404, "RepoNotFound"), race_response]
    api.create_error = _hf_error(409)
    instance = _bootstrapper(api)
    prepared = _install_prepared_source(instance, monkeypatch)

    if message is None:
        instance._ensure_remote_repo()
    else:
        with pytest.raises(RuntimeError, match=message):
            instance._ensure_remote_repo()

    assert len(prepared) == 1
    assert [name for name, _kwargs in api.calls].count("create_repo") == 1
    assert [name for name, _kwargs in api.calls].count("upload_folder") == 0
    assert [name for name, _kwargs in api.calls].count("delete_repo") == 0


def test_prepare_pinned_source_downloads_only_data_then_declared_references(
    tmp_path, monkeypatch
):
    import pandas as pd

    instance = _bootstrapper(FakeApi())
    root = tmp_path / "source"
    root.mkdir()
    reference = "reference_files/task/file.txt"
    dataframe = pd.DataFrame({
        "task_id": ["task"],
        "sector": ["sector"],
        "occupation": ["occupation"],
        "prompt": ["prompt"],
        "reference_files": [[reference]],
        "reference_file_urls": [["https://example.invalid/reference"]],
        "reference_file_hf_uris": [["hf://datasets/example/reference"]],
        "deliverable_files": [[]],
        "deliverable_file_urls": [[]],
        "deliverable_file_hf_uris": [[]],
        "rubric_pretty": ["rubric"],
        "rubric_json": ["{}"],
    })
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        destination = Path(kwargs["local_dir"])
        if len(calls) == 1:
            (destination / "data").mkdir()
            (
                destination / "data" / bootstrapper.CANONICAL_PARQUET_FILENAME
            ).write_bytes(b"parquet")
        else:
            path = destination / reference
            path.parent.mkdir(parents=True)
            path.write_bytes(b"reference")

    def generate(_root, *, output_path=None):
        destination = Path(output_path)
        destination.write_bytes(b"manifest")
        return destination

    monkeypatch.setattr(bootstrapper, "snapshot_download", download)
    monkeypatch.setattr(bootstrapper.pd, "read_parquet", lambda _path: dataframe)
    monkeypatch.setattr(instance, "_generate_manifest_from_dir", generate)
    monkeypatch.setattr(instance, "_strip_deliverables_in_dir", lambda _root: None)
    monkeypatch.setattr(instance, "_snapshot_validation_errors", lambda *_args: [])

    assert instance._prepare_pinned_source_snapshot(root) == (
        root / bootstrapper.MANIFEST_FILENAME
    )
    assert len(calls) == 2
    assert calls[0]["repo_id"] == bootstrapper.DATASET_ID
    assert calls[0]["revision"] == bootstrapper.SOURCE_REVISION
    assert calls[0]["allow_patterns"] == [
        ".gitattributes",
        "README.md",
        "data/**",
    ]
    assert calls[1]["repo_id"] == bootstrapper.DATASET_ID
    assert calls[1]["revision"] == bootstrapper.SOURCE_REVISION
    assert calls[1]["allow_patterns"] == [reference]


def test_strip_adds_and_clears_every_submitter_column(tmp_path):
    import pandas as pd

    data = tmp_path / "data"
    data.mkdir()
    parquet = data / "train-000.parquet"
    pd.DataFrame({
        "task_id": ["task-1"],
        "deliverable_files": [["deliverable_files/task-1/stale.pdf"]],
        "deliverable_file_urls": [["https://example.invalid/stale.pdf"]],
    }).to_parquet(parquet, index=False)
    instance = _bootstrapper(FakeApi())

    instance._strip_deliverables_in_dir(str(tmp_path))

    row = pd.read_parquet(parquet).iloc[0]
    assert row["deliverable_text"] == ""
    assert list(row["deliverable_files"]) == []
    assert list(row["deliverable_file_urls"]) == []
    assert list(row["deliverable_file_hf_uris"]) == []


def test_source_revision_matches_tracked_selector_fixture():
    fixture_path = Path(__file__).parent / "fixtures/deliverable_selector_contract_v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    source = fixture["source"]

    assert source == {
        "repository": bootstrapper.DATASET_ID,
        "revision": bootstrapper.SOURCE_REVISION,
        "parquet_path": "data/train-00000-of-00001.parquet",
        "parquet_sha256": "f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202",
        "row_count": bootstrapper.EXPECTED_TASK_COUNT,
        "projection_policy": "synthetic-minimal-selector-signals-v1",
        "source_content_included": False,
    }
    assert bootstrapper.CANONICAL_ORDERED_TASK_IDS_SHA256 == (
        "df1fcd6415c55a17e4f39a254aaf0f0f9f2f55c751189f74d2713a873373aa3c"
    )
    assert bootstrapper.CANONICAL_MANIFEST_SHA256_BY_POLICY["deliverable_only"] == (
        "463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512"
    )
    assert bootstrapper.CANONICAL_SOURCE_PROJECTION_SHA256 == (
        "ed8f68a4af63a1094d9bbe0fe0e83398941634a9994b4b2124dc6d0d6fbc5d4a"
    )


def test_fresh_and_relay_legs_restore_same_185_35_manifest_and_fingerprint(
    tmp_path, monkeypatch
):
    canonical = _canonical_manifest()
    encoded = _manifest_bytes(canonical)
    _anchor_manifest_bytes(monkeypatch, encoded)
    fingerprints = []

    for leg in ("fresh", "relay"):
        api = FakeApi()
        instance = _bootstrapper(api)
        instance.local_path = tmp_path / leg / "snapshot"
        instance.manifest_path = tmp_path / leg / "workspace" / bootstrapper.MANIFEST_FILENAME
        instance.local_path.mkdir(parents=True)
        (instance.local_path / bootstrapper.MANIFEST_FILENAME).write_bytes(encoded)

        instance._restore_manifest_from_snapshot()
        restored = NeedsFilesManifest.load(str(instance.manifest_path))
        task_ids = list(canonical["tasks"])
        needs = [restored.needs_files(task_id) for task_id in task_ids]
        assert sum(needs) == 185
        assert len(needs) - sum(needs) == 35
        fingerprints.append(
            prepared_fingerprint({
                "tasks": [
                    {"task_id": task_id, "needs_files": needs_files}
                    for task_id, needs_files in zip(task_ids, needs, strict=True)
                ]
            })
        )

    assert fingerprints == [
        "e48984b0c98fe03202409876fafacbde121776a1adf6db2b50d67b23329f7cca",
        "e48984b0c98fe03202409876fafacbde121776a1adf6db2b50d67b23329f7cca",
    ]


def test_existing_target_without_canonical_manifest_is_rejected(tmp_path):
    instance = _bootstrapper(FakeApi())
    instance.local_path = tmp_path / "snapshot"
    instance.manifest_path = tmp_path / "workspace" / bootstrapper.MANIFEST_FILENAME
    instance.local_path.mkdir()

    with pytest.raises(RuntimeError, match="no canonical needs-files manifest"):
        instance._restore_manifest_from_snapshot()


def test_manifest_validation_accepts_exact_anchored_bytes(tmp_path, monkeypatch):
    canonical = _canonical_manifest(total=2, needs_count=1)
    task_ids = list(canonical["tasks"])
    encoded = _anchor_test_manifest(monkeypatch, canonical)
    path = tmp_path / bootstrapper.MANIFEST_FILENAME
    path.write_bytes(encoded)

    assert bootstrapper.validate_needs_files_manifest(TaskFrame(task_ids), path) == []


@pytest.mark.parametrize(
    "mutation",
    ["top_level", "task_order", "active_policy", "prompt", "summary"],
)
def test_manifest_validation_rejects_semantic_drift(
    tmp_path, monkeypatch, mutation
):
    canonical = _canonical_manifest(total=2, needs_count=1)
    task_ids = list(canonical["tasks"])
    if mutation == "top_level":
        canonical["unexpected"] = True
    elif mutation == "task_order":
        canonical["tasks"] = {
            task_id: canonical["tasks"][task_id]
            for task_id in reversed(task_ids)
        }
    elif mutation == "active_policy":
        canonical["_summary"]["active_policy"] = "union"
    elif mutation == "prompt":
        canonical["tasks"][task_ids[0]]["prompt_classification"][
            "requires_file"
        ] = False
    else:
        canonical["_summary"]["confidence_distribution"]["explicit"] = 0
    encoded = _manifest_bytes(canonical)
    _anchor_test_manifest(monkeypatch, canonical, encoded)
    path = tmp_path / bootstrapper.MANIFEST_FILENAME
    path.write_bytes(encoded)

    errors = bootstrapper.validate_needs_files_manifest(TaskFrame(task_ids), path)

    assert errors


def test_manifest_validation_rejects_internally_consistent_signal_rewrite(
    tmp_path, monkeypatch
):
    canonical = _canonical_manifest(total=2, needs_count=1)
    original = _anchor_test_manifest(monkeypatch, canonical)
    task_ids = list(canonical["tasks"])
    for entry in canonical["tasks"].values():
        entry["needs_files"] = False
        entry["original_file_count"] = 0
        entry["original_files"] = []
        entry["has_deliverable_files"] = False
        entry["prompt_classification"] = {
            "requires_file": False,
            "explicit_exts": [],
            "inferred_exts": [],
            "confidence": "text_only",
        }
        entry["policy_results"] = {
            policy: False for policy in bootstrapper.NEEDS_FILES_POLICIES_KNOWN
        }
    canonical["_summary"] = {
        "needs_files": 0,
        "text_only": 2,
        "active_policy": "deliverable_only",
        "policy_counts": {
            policy: 0 for policy in bootstrapper.NEEDS_FILES_POLICIES_KNOWN
        },
        "confidence_distribution": {
            "explicit": 0,
            "inferred": 0,
            "ambiguous": 0,
            "text_only": 2,
        },
    }
    path = tmp_path / bootstrapper.MANIFEST_FILENAME
    path.write_bytes(_manifest_bytes(canonical))

    errors = bootstrapper.validate_needs_files_manifest(TaskFrame(task_ids), path)

    assert hashlib.sha256(original).hexdigest() != hashlib.sha256(path.read_bytes()).hexdigest()
    assert any("canonical digest" in error for error in errors)


def test_manifest_validation_rejects_prompt_mutation(
    tmp_path, monkeypatch
):
    canonical = _canonical_manifest(total=2, needs_count=1)
    encoded = _anchor_test_manifest(monkeypatch, canonical)
    path = tmp_path / bootstrapper.MANIFEST_FILENAME
    path.write_bytes(encoded)

    class MutatedFrame(TaskFrame):
        def __getitem__(self, key):
            values = super().__getitem__(key)
            if key == "prompt":
                values[0] = "mutated prompt"
            return values

    errors = bootstrapper.validate_needs_files_manifest(
        MutatedFrame(list(canonical["tasks"])),
        path,
    )

    assert any("source projection" in error for error in errors)


def test_reused_snapshot_rejects_all_stale_submitter_state(tmp_path):
    import pandas as pd

    frame = pd.DataFrame({
        "deliverable_text": ["stale"],
        "deliverable_files": [["deliverable_files/task/out.pdf"]],
        "deliverable_file_urls": [["https://example.invalid/out.pdf"]],
        "deliverable_file_hf_uris": [["hf://invalid/out.pdf"]],
    })
    physical = tmp_path / "deliverable_files/task/out.pdf"
    physical.parent.mkdir(parents=True)
    physical.write_bytes(b"stale")

    errors = bootstrapper.validate_cleared_submitter_state(frame, tmp_path)

    assert any("deliverable_text must be exact empty strings" in error for error in errors)
    assert any("deliverable_files must be empty list-like" in error for error in errors)
    assert any("deliverable_file_urls must be empty list-like" in error for error in errors)
    assert any("deliverable_file_hf_uris must be empty list-like" in error for error in errors)
    assert any("stale submitter output" in error for error in errors)


@pytest.mark.parametrize(
    "invalid_value",
    [None, float("nan"), "scalar", b"bytes", 7, ["stale"], ("stale",)],
)
def test_reused_snapshot_rejects_nonempty_or_wrong_list_cell(
    tmp_path, invalid_value
):
    import pandas as pd

    frame = pd.DataFrame({
        "deliverable_text": [""],
        "deliverable_files": [invalid_value],
        "deliverable_file_urls": [[]],
        "deliverable_file_hf_uris": [[]],
    })

    errors = bootstrapper.validate_cleared_submitter_state(frame, tmp_path)

    assert any("deliverable_files must be empty list-like" in error for error in errors)


def test_reused_snapshot_accepts_empty_numpy_submitter_arrays(tmp_path):
    import numpy as np
    import pandas as pd

    frame = pd.DataFrame({
        "deliverable_text": [""],
        "deliverable_files": [np.array([], dtype=object)],
        "deliverable_file_urls": [np.array([], dtype=object)],
        "deliverable_file_hf_uris": [np.array([], dtype=object)],
    })

    assert bootstrapper.validate_cleared_submitter_state(frame, tmp_path) == []


def test_snapshot_validation_requires_exact_v4_target_schema(tmp_path, monkeypatch):
    import pandas as pd

    row_count = bootstrapper.EXPECTED_TASK_COUNT
    dataframe = pd.DataFrame({
        "task_id": [f"task-{index}" for index in range(row_count)],
        "sector": ["sector"] * row_count,
        "occupation": ["occupation"] * row_count,
        "prompt": ["prompt"] * row_count,
        "reference_files": [[] for _ in range(row_count)],
        "reference_file_urls": [[] for _ in range(row_count)],
        "reference_file_hf_uris": [[] for _ in range(row_count)],
        "deliverable_files": [[] for _ in range(row_count)],
        "deliverable_file_urls": [[] for _ in range(row_count)],
        "deliverable_file_hf_uris": [[] for _ in range(row_count)],
        "rubric_pretty": ["rubric"] * row_count,
        "rubric_json": ["{}"] * row_count,
        "deliverable_text": [""] * row_count,
    })
    root = tmp_path / "snapshot"
    data_dir = root / "data"
    data_dir.mkdir(parents=True)
    (data_dir / bootstrapper.CANONICAL_PARQUET_FILENAME).write_bytes(b"parquet")
    (root / "reference_files").mkdir()
    instance = _bootstrapper(FakeApi())
    monkeypatch.setattr(bootstrapper.pd, "read_parquet", lambda _path: dataframe)
    monkeypatch.setattr(
        bootstrapper, "validate_reference_snapshot", lambda *_args: []
    )
    monkeypatch.setattr(
        bootstrapper, "validate_needs_files_manifest", lambda *_args, **_kwargs: []
    )

    assert instance._snapshot_validation_errors(
        root,
        root / bootstrapper.MANIFEST_FILENAME,
    ) == []

    dataframe["unexpected"] = "value"
    errors = instance._snapshot_validation_errors(
        root,
        root / bootstrapper.MANIFEST_FILENAME,
    )
    assert any("canonical target columns" in error for error in errors)


def test_download_snapshot_refreshes_stale_local_from_exact_head(tmp_path, monkeypatch):
    api = FakeApi()
    instance = _bootstrapper(api)
    instance.local_path = tmp_path / "target"
    instance.local_path.mkdir()
    (instance.local_path / "stale.txt").write_text("stale", encoding="utf-8")
    downloaded = _install_fake_snapshot_contract(
        instance,
        monkeypatch,
        target_data=b"new",
        source_data=b"new",
    )

    instance._download_snapshot()

    assert not (instance.local_path / "stale.txt").exists()
    assert (instance.local_path / "data/train-00000-of-00001.parquet").read_bytes() == b"new"
    identity_path = instance.local_path / bootstrapper.TARGET_HEAD_FILENAME
    assert bootstrapper.load_target_head_identity(
        identity_path,
        "owner/disposable",
    ) == api.head
    assert downloaded[0]["repo_id"] == "owner/disposable"
    assert downloaded[0]["revision"] == api.head
    assert downloaded[0]["allow_patterns"] == [
        ".gitattributes",
        "README.md",
        "data/**",
        "reference_files/**",
        "deliverable_files/**",
        bootstrapper.MANIFEST_FILENAME,
    ]
    assert api.calls == [
        (
            "repo_info",
            {
                "repo_id": "owner/disposable",
                "repo_type": "dataset",
                "token": "token",
            },
        )
    ]


def test_target_head_identity_rejects_repo_or_sha_drift(tmp_path):
    identity_path = tmp_path / bootstrapper.TARGET_HEAD_FILENAME
    identity_path.write_text(json.dumps({
        "schema_version": "step0-target-head-v1",
        "repo_id": "owner/repository",
        "head": "a" * 40,
    }), encoding="utf-8")

    with pytest.raises(RuntimeError, match="repository identity mismatch"):
        bootstrapper.load_target_head_identity(identity_path, "other/repository")

    payload = json.loads(identity_path.read_text(encoding="utf-8"))
    payload["head"] = "main"
    identity_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="HEAD is invalid"):
        bootstrapper.load_target_head_identity(identity_path, "owner/repository")


def test_download_snapshot_missing_manifest_preserves_previous_local(
    tmp_path, monkeypatch
):
    instance = _bootstrapper(FakeApi())
    instance.local_path = tmp_path / "target"
    instance.local_path.mkdir()
    previous = instance.local_path / "previous.txt"
    previous.write_text("previous", encoding="utf-8")

    _install_fake_snapshot_contract(
        instance,
        monkeypatch,
        target_data=b"legacy",
        source_data=b"approved",
        omit_target_manifest=True,
    )

    with pytest.raises(ValueError, match="Canonical needs-files manifest not found"):
        instance._download_snapshot()

    assert previous.read_text(encoding="utf-8") == "previous"


def test_download_snapshot_rejects_symlink_tree_without_replacing_local(
    tmp_path, monkeypatch
):
    instance = _bootstrapper(FakeApi())
    instance.local_path = tmp_path / "target"
    instance.local_path.mkdir()
    previous = instance.local_path / "previous.txt"
    previous.write_text("previous", encoding="utf-8")

    def download(**kwargs):
        root = Path(kwargs["local_dir"])
        (root / bootstrapper.MANIFEST_FILENAME).write_bytes(b"manifest")
        (root / "linked").symlink_to(previous)

    monkeypatch.setattr(bootstrapper, "snapshot_download", download)

    with pytest.raises(RuntimeError, match="contains a symlink"):
        instance._download_snapshot()

    assert previous.read_text(encoding="utf-8") == "previous"


def test_download_snapshot_invalid_manifest_preserves_previous_local(
    tmp_path, monkeypatch
):
    instance = _bootstrapper(FakeApi())
    instance.local_path = tmp_path / "target"
    instance.local_path.mkdir()
    previous = instance.local_path / "previous.txt"
    previous.write_text("previous", encoding="utf-8")

    _install_fake_snapshot_contract(
        instance,
        monkeypatch,
        target_manifest=b"tampered",
    )

    with pytest.raises(ValueError, match="canonical digest"):
        instance._download_snapshot()

    assert previous.read_text(encoding="utf-8") == "previous"


def test_download_snapshot_byte_mismatch_preserves_previous_local(
    tmp_path, monkeypatch
):
    instance = _bootstrapper(FakeApi())
    instance.local_path = tmp_path / "target"
    instance.local_path.mkdir()
    previous = instance.local_path / "previous.txt"
    previous.write_text("previous", encoding="utf-8")
    _install_fake_snapshot_contract(
        instance,
        monkeypatch,
        target_data=b"tampered",
        source_data=b"approved",
    )

    with pytest.raises(ValueError, match="source projection differs"):
        instance._download_snapshot()

    assert previous.read_text(encoding="utf-8") == "previous"


def test_restore_manifest_rejects_workspace_symlink(tmp_path, monkeypatch):
    instance = _bootstrapper(FakeApi())
    instance.local_path = tmp_path / "snapshot"
    instance.local_path.mkdir()
    (instance.local_path / bootstrapper.MANIFEST_FILENAME).write_bytes(b"manifest")
    _anchor_manifest_bytes(monkeypatch, b"manifest")
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"outside")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    instance.manifest_path = workspace / bootstrapper.MANIFEST_FILENAME
    instance.manifest_path.symlink_to(outside)

    with pytest.raises(RuntimeError, match="Workspace manifest is a symlink"):
        instance._restore_manifest_from_snapshot()

    assert outside.read_bytes() == b"outside"


def test_reference_snapshot_accepts_exact_regular_tree(tmp_path):
    path = tmp_path / "reference_files/task/file.txt"
    path.parent.mkdir(parents=True)
    path.write_text("reference", encoding="utf-8")

    assert bootstrapper.validate_reference_snapshot(
        Frame([["reference_files/task/file.txt"]]), tmp_path
    ) == []


def test_reference_manifest_records_and_rejects_byte_mutation(tmp_path):
    path = tmp_path / "reference_files/task/file.txt"
    path.parent.mkdir(parents=True)
    path.write_text("reference", encoding="utf-8")
    frame = Frame([["reference_files/task/file.txt"]])

    records, errors = bootstrapper.build_reference_manifest(frame, tmp_path)

    assert errors == []
    assert records == {
        "reference_files/task/file.txt": {
            "sha256": hashlib.sha256(b"reference").hexdigest(),
            "size": 9,
        }
    }
    path.write_text("mutated", encoding="utf-8")
    assert records["reference_files/task/file.txt"] != (
        bootstrapper.build_reference_manifest(frame, tmp_path)[0][
            "reference_files/task/file.txt"
        ]
    )


@pytest.mark.parametrize(
    ("references", "message"),
    [
        ([["reference_files/task/missing.txt"]], "Missing reference file"),
        ([["../escape.txt"]], "unsafe path"),
        ([["/absolute.txt"]], "unsafe path"),
        ([["reference_files/task/../escape.txt"]], "unsafe path"),
        (
            [["reference_files/task/file.txt", "reference_files/task/file.txt"]],
            "Duplicate reference file path",
        ),
    ],
)
def test_reference_snapshot_rejects_invalid_manifest(tmp_path, references, message):
    errors = bootstrapper.validate_reference_snapshot(Frame(references), tmp_path)

    assert any(message in error for error in errors)


def test_reference_snapshot_rejects_symlink_ancestor(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file.txt").write_text("reference", encoding="utf-8")
    reference_root = tmp_path / "reference_files"
    reference_root.mkdir()
    (reference_root / "task").symlink_to(outside, target_is_directory=True)

    errors = bootstrapper.validate_reference_snapshot(
        Frame([["reference_files/task/file.txt"]]), tmp_path
    )

    assert any("symlink" in error for error in errors)
