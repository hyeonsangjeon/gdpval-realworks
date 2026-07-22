import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from huggingface_hub import CommitOperationAdd, CommitOperationDelete

from core.hf_publication import (
    PublicationIdentity,
    PublicationResult,
    PublicationTaskResult,
    load_publication_identity,
    publish_dataset,
)
from core.prepared_fingerprint import prepared_fingerprint
from core.result_fingerprint import inference_result_fingerprint


class FakeApi:
    def __init__(self, head="a" * 40, *, create_mode="success"):
        self.head = head
        self.parent = head
        self.candidate = "b" * 40
        self.create_mode = create_mode
        self.calls = []
        self.marker = ""
        self.remote_files = {
            "README.md": b"readme",
            "reference_files/task/input.xlsx": b"reference",
            "data/train-00000-of-00001.parquet": b"old-parquet",
            "data/old.parquet": b"old",
            "deliverable_files/task/old.pdf": b"old-pdf",
            "self_report.json": b"old-report",
        }
        self.lfs_paths = set()
        self.tree_mutation = None
        self.marker_override = None
        self.parent_override = None
        self.final_head = None
        self.fail_tree = False
        self.download_symlinks = False

    def list_repo_files(self, **kwargs):
        self.calls.append(("list_repo_files", kwargs))
        return sorted(self.remote_files)

    def create_commit(self, **kwargs):
        self.calls.append(("create_commit", kwargs))
        if self.create_mode == "before_failure":
            raise OSError("commit failed before mutation")
        self.parent = kwargs["parent_commit"]
        self.marker = kwargs.get("commit_description", "")
        for operation in kwargs["operations"]:
            if isinstance(operation, CommitOperationDelete):
                self.remote_files.pop(operation.path_in_repo, None)
            else:
                self.remote_files[operation.path_in_repo] = Path(
                    operation.path_or_fileobj
                )
        if self.create_mode == "concurrent_different":
            self.head = "c" * 40
            self.marker = "publication-plan-sha256: " + "0" * 64
            raise RuntimeError("CAS conflict")
        self.head = self.candidate
        if self.create_mode == "response_lost":
            raise OSError("response lost")
        if self.create_mode == "malformed_response":
            return SimpleNamespace(oid="not-a-full-oid")
        return SimpleNamespace(oid=self.candidate)

    def list_repo_commits(self, **kwargs):
        self.calls.append(("list_repo_commits", kwargs))
        message = self.marker_override or self.marker
        return [
            SimpleNamespace(commit_id=kwargs["revision"], message=message),
            SimpleNamespace(
                commit_id=self.parent_override or self.parent,
                message="parent",
            ),
        ]

    def list_repo_tree(self, **kwargs):
        self.calls.append(("list_repo_tree", kwargs))
        if self.fail_tree:
            raise OSError("tree verification unavailable")
        remote_files = dict(self.remote_files)
        if self.tree_mutation == "missing":
            remote_files.pop("self_report.json", None)
        elif self.tree_mutation == "extra":
            remote_files["data/extra.parquet"] = b"extra"
        entries = []
        for path, value in sorted(remote_files.items()):
            content = value.read_bytes() if isinstance(value, Path) else value
            size = len(content)
            if self.tree_mutation == "size" and path == "self_report.json":
                size += 1
            lfs = None
            if path in self.lfs_paths:
                sha256 = hashlib.sha256(content).hexdigest()
                if self.tree_mutation == "lfs_hash" and path == "self_report.json":
                    sha256 = "0" * 64
                lfs = SimpleNamespace(size=len(content), sha256=sha256)
            entries.append(SimpleNamespace(path=path, size=size, lfs=lfs))
        return entries

    def hf_hub_download(self, **kwargs):
        self.calls.append(("hf_hub_download", kwargs))
        value = self.remote_files[kwargs["filename"]]
        path = value if isinstance(value, Path) else None
        if path is None:
            raise AssertionError("test requested an unmaterialized remote file")
        if self.tree_mutation == "download_hash" and kwargs["filename"] == "self_report.json":
            corrupt = path.with_name("corrupt-self-report.json")
            corrupt.write_bytes(b"corrupt")
            return str(corrupt)
        if self.download_symlinks:
            link = path.with_name(f"cache-link-{path.name}")
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(path)
            return str(link)
        return str(path)

    def repo_info(self, **kwargs):
        self.calls.append(("repo_info", kwargs))
        repo_info_calls = sum(name == "repo_info" for name, _ in self.calls)
        if self.final_head is not None and repo_info_calls >= 3:
            return SimpleNamespace(sha=self.final_head)
        return SimpleNamespace(sha=self.head)


def _identity() -> PublicationIdentity:
    return PublicationIdentity(
        experiment_id="exp-test",
        repo_id="owner/repository",
        publication_generation="exp-test:100:1",
        prepared_fingerprint="f" * 64,
        result_fingerprint="e" * 64,
        ordered_task_ids=("task-1",),
        results=(PublicationTaskResult("task-1", "", (), (), ()),),
    )


def _upload_root(tmp_path: Path, *, report_overrides=None) -> Path:
    root = tmp_path / "upload"
    root.mkdir()
    report = {
        "meta": {
            "experiment_id": "exp-test",
            "source_repo_id": "owner/repository",
            "publication_generation": "exp-test:100:1",
            "prepared_fingerprint": "f" * 64,
            "result_fingerprint": "e" * 64,
            "ordered_task_ids": ["task-1"],
            "publication_plan": "step7_upload_requested",
        },
        "task_results": [{"task_id": "task-1"}],
    }
    for key, value in (report_overrides or {}).items():
        if key == "task_results":
            report[key] = value
        else:
            report["meta"][key] = value
    (root / "self_report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    data = root / "data"
    data.mkdir()
    (data / "train-00000-of-00001.parquet").write_bytes(b"parquet")
    return root


def test_publication_uses_step0_head_as_cas_parent(tmp_path):
    api = FakeApi()
    root = _upload_root(tmp_path)

    result = publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=api,
    )

    assert [name for name, _kwargs in api.calls[:3]] == [
        "repo_info",
        "list_repo_files",
        "create_commit",
    ]
    assert result == PublicationResult(
        oid="b" * 40,
        plan_sha256=result.plan_sha256,
        reconciled=False,
    )
    assert len(result.plan_sha256) == 64
    commit = api.calls[2][1]
    assert commit["revision"] == "main"
    assert commit["parent_commit"] == "a" * 40
    assert commit["commit_description"] == (
        f"publication-plan-sha256: {result.plan_sha256}"
    )
    additions = [
        operation.path_in_repo
        for operation in commit["operations"]
        if isinstance(operation, CommitOperationAdd)
    ]
    deletions = [
        operation.path_in_repo
        for operation in commit["operations"]
        if isinstance(operation, CommitOperationDelete)
    ]
    assert additions == ["data/train-00000-of-00001.parquet", "self_report.json"]
    assert deletions == [
        "data/old.parquet",
        "deliverable_files/task/old.pdf",
    ]
    assert not set(additions) & set(deletions)
    assert "reference_files/task/input.xlsx" not in deletions


@pytest.mark.parametrize("mode", ["response_lost", "malformed_response"])
def test_publication_reconciles_ambiguous_create_response_without_retry(
    tmp_path, mode
):
    api = FakeApi(create_mode=mode)

    result = publish_dataset(
        "owner/repository",
        _upload_root(tmp_path),
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=api,
    )

    assert result.oid == "b" * 40
    assert result.reconciled is True
    assert len([call for call in api.calls if call[0] == "create_commit"]) == 1


def test_publication_propagates_failure_before_commit_without_retry(tmp_path):
    api = FakeApi(create_mode="before_failure")

    with pytest.raises(OSError, match="failed before mutation"):
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.head == "a" * 40
    assert len([call for call in api.calls if call[0] == "create_commit"]) == 1


def test_publication_rejects_different_concurrent_commit_without_retry(tmp_path):
    api = FakeApi(create_mode="concurrent_different")

    with pytest.raises(RuntimeError, match="outcome is unverified"):
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.head == "c" * 40
    assert len([call for call in api.calls if call[0] == "create_commit"]) == 1


@pytest.mark.parametrize("mutation", ["marker", "parent"])
def test_publication_requires_direct_parent_and_exact_plan_marker(tmp_path, mutation):
    api = FakeApi()
    if mutation == "marker":
        api.marker_override = "publication-plan-sha256: " + "0" * 64
    else:
        api.parent_override = "d" * 40

    with pytest.raises(RuntimeError, match="outcome is unverified"):
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )


@pytest.mark.parametrize(
    "mutation",
    ["missing", "extra", "size", "download_hash", "lfs_hash"],
)
def test_publication_rejects_remote_tree_or_hash_mismatch(tmp_path, mutation):
    api = FakeApi()
    api.tree_mutation = mutation
    if mutation == "lfs_hash":
        api.lfs_paths.add("self_report.json")

    with pytest.raises(RuntimeError, match="outcome is unverified"):
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )


def test_publication_uses_lfs_hash_without_downloading_large_file(tmp_path):
    api = FakeApi()
    api.lfs_paths.add("data/train-00000-of-00001.parquet")

    publish_dataset(
        "owner/repository",
        _upload_root(tmp_path),
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=api,
    )

    downloads = [
        kwargs["filename"]
        for name, kwargs in api.calls
        if name == "hf_hub_download"
    ]
    assert "self_report.json" in downloads
    assert "data/train-00000-of-00001.parquet" not in downloads


def test_publication_accepts_revision_pinned_hf_cache_symlinks(tmp_path):
    api = FakeApi()
    api.download_symlinks = True

    result = publish_dataset(
        "owner/repository",
        _upload_root(tmp_path),
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=api,
    )

    assert result.oid == "b" * 40


def test_publication_still_rejects_local_upload_symlink(tmp_path):
    root = _upload_root(tmp_path)
    self_report = root / "self_report.json"
    target = root / "report-target.json"
    self_report.rename(target)
    self_report.symlink_to(target)

    with pytest.raises(ValueError, match="must be a regular file"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=FakeApi(),
        )


def test_publication_fails_closed_when_verification_api_is_unavailable(tmp_path):
    api = FakeApi()
    api.fail_tree = True

    with pytest.raises(RuntimeError, match="outcome is unverified"):
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )


def test_publication_rejects_final_head_advance(tmp_path):
    api = FakeApi()
    api.final_head = "c" * 40

    with pytest.raises(RuntimeError, match="outcome is unverified"):
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )


def test_publication_rejects_changed_head_before_upload(tmp_path):
    api = FakeApi(head="b" * 40)

    with pytest.raises(RuntimeError, match="HEAD changed"):
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert [name for name, _kwargs in api.calls] == ["repo_info"]


def test_publication_requires_local_self_report_before_remote_call(tmp_path):
    root = tmp_path / "upload"
    root.mkdir()
    api = FakeApi()

    with pytest.raises(ValueError, match="self_report.json is required"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"experiment_id": "other-experiment"}, "experiment identity mismatch"),
        ({"source_repo_id": "other/repository"}, "repository identity mismatch"),
        ({"publication_generation": "exp-test:200:1"}, "generation mismatch"),
        ({"prepared_fingerprint": "e" * 64}, "prepared fingerprint mismatch"),
        ({"result_fingerprint": "d" * 64}, "result fingerprint mismatch"),
        ({"publication_plan": "dry_run_no_step7"}, "plan is not publishable"),
        ({"ordered_task_ids": ["task-2"]}, "task order mismatch"),
        ({"task_results": [{"task_id": "task-2"}]}, "result task set mismatch"),
    ],
)
def test_publication_rejects_stale_self_report_identity(
    tmp_path, overrides, message
):
    api = FakeApi()

    with pytest.raises(ValueError, match=message):
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path, report_overrides=overrides),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_sends_more_than_250_files_in_one_create_commit(tmp_path):
    api = FakeApi()
    root = _upload_root(tmp_path)
    deliverables = root / "deliverable_files" / "task"
    deliverables.mkdir(parents=True)
    for index in range(251):
        (deliverables / f"result-{index:03d}.txt").write_text(
            str(index),
            encoding="utf-8",
        )

    publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=api,
    )

    create_calls = [kwargs for name, kwargs in api.calls if name == "create_commit"]
    assert len(create_calls) == 1
    additions = [
        operation
        for operation in create_calls[0]["operations"]
        if isinstance(operation, CommitOperationAdd)
    ]
    assert len(additions) == 253


def _write_pipeline_identity(tmp_path: Path) -> tuple[Path, Path, dict]:
    prepared = {
        "experiment_id": "exp-test",
        "publication_generation": "exp-test:100:1",
        "source": "owner/repository",
        "task_scope": {
            "expected_count": 2,
            "task_ids": ["task-1", "task-2"],
        },
        "tasks": [{"task_id": "task-1"}, {"task_id": "task-2"}],
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)
    inference = {
        "experiment_id": "exp-test",
        "publication_generation": "exp-test:100:1",
        "source": "owner/repository",
        "prepared_fingerprint": prepared["prepared_fingerprint"],
        "ordered_task_ids": ["task-1", "task-2"],
        "results": [
            {
                "task_id": "task-1",
                "deliverable_text": "current text",
                "deliverable_files": ["deliverable_files/task-1/report.pdf"],
            },
            {
                "task_id": "task-2",
                "deliverable_text": None,
                "deliverable_files": [],
            },
        ],
    }
    inference["result_fingerprint"] = inference_result_fingerprint(inference)
    prepared_path = tmp_path / "step1.json"
    inference_path = tmp_path / "step2.json"
    prepared_path.write_text(json.dumps(prepared), encoding="utf-8")
    inference_path.write_text(json.dumps(inference), encoding="utf-8")
    return prepared_path, inference_path, prepared


def test_load_publication_identity_binds_exact_step1_step2_scope(tmp_path):
    prepared_path, inference_path, prepared = _write_pipeline_identity(tmp_path)

    identity = load_publication_identity(prepared_path, inference_path)

    assert identity == PublicationIdentity(
        experiment_id="exp-test",
        repo_id="owner/repository",
        publication_generation="exp-test:100:1",
        prepared_fingerprint=prepared["prepared_fingerprint"],
        result_fingerprint=json.loads(
            inference_path.read_text(encoding="utf-8")
        )["result_fingerprint"],
        ordered_task_ids=("task-1", "task-2"),
        results=(
            PublicationTaskResult(
                "task-1",
                "current text",
                ("deliverable_files/task-1/report.pdf",),
                (
                    "https://huggingface.co/datasets/owner/repository/resolve/"
                    "main/deliverable_files/task-1/report.pdf",
                ),
                (
                    "hf://datasets/owner/repository@main/"
                    "deliverable_files/task-1/report.pdf",
                ),
            ),
            PublicationTaskResult("task-2", "", (), (), ()),
        ),
    )


def test_load_publication_identity_rejects_same_scope_stale_result(tmp_path):
    prepared_path, inference_path, _prepared = _write_pipeline_identity(tmp_path)
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    inference["results"][0]["deliverable_text"] = "stale run text"
    inference_path.write_text(json.dumps(inference), encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint does not match payload"):
        load_publication_identity(prepared_path, inference_path)


def test_load_publication_identity_rejects_valid_prior_run_after_step1_rerun(
    tmp_path,
):
    prepared_path, inference_path, _prepared = _write_pipeline_identity(tmp_path)
    prior_inference = json.loads(inference_path.read_text(encoding="utf-8"))
    assert prior_inference["result_fingerprint"] == inference_result_fingerprint(
        prior_inference
    )

    rerun_prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    rerun_prepared["publication_generation"] = "exp-test:200:1"
    rerun_prepared["prepared_fingerprint"] = prepared_fingerprint(rerun_prepared)
    prepared_path.write_text(json.dumps(rerun_prepared), encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        load_publication_identity(prepared_path, inference_path)


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("prepared", "expected_count", 1, "task count"),
        ("inference", "source", "other/repository", "repository identity"),
        ("inference", "prepared_fingerprint", "e" * 64, "fingerprint"),
        ("inference", "ordered_task_ids", ["task-2", "task-1"], "task order"),
        ("inference", "results", [{"task_id": "task-1"}], "result task set"),
    ],
)
def test_load_publication_identity_rejects_mixed_scope(
    tmp_path, target, field, value, message
):
    prepared_path, inference_path, _prepared = _write_pipeline_identity(tmp_path)
    path = prepared_path if target == "prepared" else inference_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    if target == "prepared" and field == "expected_count":
        payload["task_scope"][field] = value
        payload["prepared_fingerprint"] = prepared_fingerprint(payload)
    else:
        payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_publication_identity(prepared_path, inference_path)