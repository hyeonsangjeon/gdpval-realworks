import json
import hashlib
import os
import stat
import tempfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
from huggingface_hub import CommitOperationAdd, CommitOperationDelete

import core.hf_publication as hf_publication
from core.hf_publication import (
    PublicationFileRecord,
    PublicationIdentity,
    PublicationReceipt,
    PublicationResult,
    PublicationTaskResult,
    load_publication_identity,
    load_publication_receipt,
    publish_dataset,
    publish_dataset_with_receipt,
    verify_publication_finality,
    write_publication_receipt,
)
from core.inference_manifest import (
    build_inference_provenance,
    canonical_deliverable_uris,
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
            "inference_provenance.json": b"old-provenance",
            "self_report.json": b"old-report",
            "step2_inference_results.json": b"stale-full-results",
        }
        self.revision_files = {self.parent: dict(self.remote_files)}
        self.commit_history = {}
        self.lfs_paths = set()
        self.tree_mutation = None
        self.tree_mutations = {}
        self.marker_override = None
        self.parent_override = None
        self.final_head = None
        self.repo_info_sequence = []
        self.fail_tree = False
        self.download_symlinks = False
        self.remote_dir = tempfile.TemporaryDirectory()
        self.before_first_remote_call = None

    def list_repo_files(self, **kwargs):
        self.calls.append(("list_repo_files", kwargs))
        files = self.revision_files.get(
            kwargs.get("revision"), self.remote_files
        )
        return sorted(files)

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
                source = operation.path_or_fileobj
                assert not isinstance(source, (str, Path))
                source.seek(0)
                destination = Path(self.remote_dir.name) / operation.path_in_repo
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as materialized:
                    while chunk := source.read(1024 * 1024):
                        materialized.write(chunk)
                self.remote_files[operation.path_in_repo] = destination
                self.revision_files[self.candidate] = dict(self.remote_files)
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
        history = self.commit_history.get(kwargs["revision"])
        if history is not None:
            return [
                SimpleNamespace(
                    commit_id=commit_id,
                    title=title,
                    message=message,
                )
                for commit_id, title, message in history
            ]
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
        remote_files = dict(self.revision_files.get(
            kwargs.get("revision"), self.remote_files
        ))
        mutation = self.tree_mutations.get(
            kwargs.get("revision"), self.tree_mutation
        )
        if mutation == "missing":
            remote_files.pop("self_report.json", None)
        elif mutation == "missing_provenance":
            remote_files.pop("inference_provenance.json", None)
        elif mutation == "extra":
            remote_files["data/extra.parquet"] = b"extra"
        elif mutation == "stale_step2":
            remote_files["step2_inference_results.json"] = b"stale-full-results"
        entries = []
        for path, value in sorted(remote_files.items()):
            content = value.read_bytes() if isinstance(value, Path) else value
            size = len(content)
            if mutation == "size" and path == "self_report.json":
                size += 1
            lfs = None
            if path in self.lfs_paths:
                sha256 = hashlib.sha256(content).hexdigest()
                if mutation == "lfs_hash" and path == "self_report.json":
                    sha256 = "0" * 64
                lfs = SimpleNamespace(size=len(content), sha256=sha256)
            entries.append(SimpleNamespace(path=path, size=size, lfs=lfs))
        return entries

    def hf_hub_download(self, **kwargs):
        self.calls.append(("hf_hub_download", kwargs))
        remote_files = self.revision_files.get(
            kwargs.get("revision"), self.remote_files
        )
        value = remote_files[kwargs["filename"]]
        path = value if isinstance(value, Path) else None
        if path is None:
            raise AssertionError("test requested an unmaterialized remote file")
        download_source = path
        mutation = self.tree_mutations.get(
            kwargs.get("revision"), self.tree_mutation
        )
        if mutation == "download_hash" and kwargs["filename"] == "self_report.json":
            corrupt = path.with_name("corrupt-self-report.json")
            corrupt.write_bytes(b"corrupt")
            download_source = corrupt
        elif (
            mutation == "provenance_hash"
            and kwargs["filename"] == "inference_provenance.json"
        ):
            content = path.read_bytes()
            corrupt = path.with_name("corrupt-inference-provenance.json")
            corrupt.write_bytes(content.replace(b"exp-test", b"exp-tost", 1))
            download_source = corrupt
        if self.download_symlinks:
            cache_root = Path(self.remote_dir.name) / "cache"
            blob = cache_root / "blobs" / hashlib.sha256(
                download_source.read_bytes()
            ).hexdigest()
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(download_source.read_bytes())
            link = cache_root / "snapshots" / kwargs["revision"] / kwargs["filename"]
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(os.path.relpath(blob, start=link.parent))
            return str(link)
        return str(download_source)

    def repo_info(self, **kwargs):
        callback = self.before_first_remote_call
        self.before_first_remote_call = None
        if callback is not None:
            callback()
        self.calls.append(("repo_info", kwargs))
        if self.repo_info_sequence:
            return SimpleNamespace(sha=self.repo_info_sequence.pop(0))
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
        expected_narrative_model="gpt-5.6-sol",
        expected_narrative_reasoning_effort="max",
        expected_narrative_runtime_fingerprint="d" * 64,
    )


def _narrative_identity_kwargs() -> dict:
    return {
        "expected_narrative_model": "gpt-5.6-sol",
        "expected_narrative_reasoning_effort": "max",
        "expected_narrative_runtime_fingerprint": "d" * 64,
    }


def _report_summary(**overrides) -> dict:
    summary = {
        "total_tasks": 1,
        "success_count": 1,
        "success_rate_pct": 100.0,
        "error_count": 0,
        "retried_count": 0,
        "avg_qa_score": 0.0,
        "min_qa_score": 0,
        "max_qa_score": 0,
        "avg_latency_ms": 0,
        "max_latency_ms": 0,
        "total_latency_ms": 0,
    }
    summary.update(overrides)
    return summary


def _report_task_row(**overrides) -> dict:
    row = {
        "task_id": "task-1",
        "sector": "",
        "occupation": "",
        "status": "success",
        "retried": False,
        "files_count": 0,
        "qa_score": None,
        "qa_passed": None,
        "qa_issues": [],
        "qa_suggestion": "",
        "latency_ms": 0,
        "observability": {},
        "deliverable_summary": "",
        "instruction": "",
        "reference_file_urls": [],
        "deliverable_files": [],
    }
    row.update(overrides)
    return row


def _upload_root(
    tmp_path: Path,
    *,
    report_overrides=None,
    provenance_task_ids=("task-1",),
) -> Path:
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
            "narrative_model": "gpt-5.6-sol",
            "narrative_reasoning_effort": "max",
            "narrative_runtime_fingerprint": "d" * 64,
        },
        "narrative": {
            "overview": "overview",
            "quality_analysis": "quality",
            "failure_patterns": "failures",
            "recommendations": "recommendations",
        },
        "summary": _report_summary(),
        "task_results": [_report_task_row()],
        "error_tasks": [],
    }
    for key, value in (report_overrides or {}).items():
        if key in {
            "summary",
            "task_results",
            "error_tasks",
            "narrative",
            "cost_ledger",
        }:
            report[key] = value
        else:
            report["meta"][key] = value
    (root / "self_report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    provenance = build_inference_provenance({
        "experiment_id": "exp-test",
        "source_repo_id": "owner/repository",
        "prepared_fingerprint": "f" * 64,
        "execution_mode": "subprocess",
        "azure_ai_routes": [],
        "results": [
            {"task_id": task_id, "deliverable_files": []}
            for task_id in provenance_task_ids
        ],
    })
    (root / "inference_provenance.json").write_text(
        json.dumps(provenance), encoding="utf-8"
    )
    data = root / "data"
    data.mkdir()
    (data / "train-00000-of-00001.parquet").write_bytes(b"parquet")
    return root


def _receipt_result() -> PublicationResult:
    return PublicationResult(
        oid="b" * 40,
        plan_sha256="c" * 64,
        reconciled=False,
    )


def _published_state(tmp_path: Path, *, include_readme: bool = False):
    api = FakeApi()
    root = _upload_root(tmp_path)
    if include_readme:
        (root / "README.md").write_bytes(b"planned-readme")
    receipt_path = tmp_path / "publication-receipt.json"
    publication = publish_dataset_with_receipt(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        receipt_path=receipt_path,
        api=api,
    )
    api.calls.clear()
    return api, root, receipt_path, publication


def _add_cleanup_commit(
    api: FakeApi,
    generation: str,
    *,
    head: str = "c" * 40,
    parent: str | None = None,
    title: str | None = None,
    description: str | None = None,
    first_commit: str | None = None,
) -> str:
    api.head = head
    api.revision_files[head] = dict(api.revision_files[api.candidate])
    api.commit_history[head] = [
        (
            first_commit or head,
            (
                title
                if title is not None
                else f"Clean relay checkpoint {generation[:12]}"
            ),
            (
                description
                if description is not None
                else f"relay-cleanup-generation: {generation}"
            ),
        ),
        (parent or api.candidate, "publication", ""),
    ]
    return head


def test_publication_receipt_roundtrip_is_private_and_atomic(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "state" / "publication_receipt.json"
    replace_calls = []
    fsync_calls = []
    real_replace = hf_publication.os.replace
    real_fsync = hf_publication.os.fsync

    def tracked_replace(source, destination):
        replace_calls.append((Path(source), Path(destination)))
        return real_replace(source, destination)

    def tracked_fsync(descriptor):
        fsync_calls.append(descriptor)
        return real_fsync(descriptor)

    monkeypatch.setattr(hf_publication.os, "replace", tracked_replace)
    monkeypatch.setattr(hf_publication.os, "fsync", tracked_fsync)

    written = write_publication_receipt(
        _receipt_result(),
        expected_head="a" * 40,
        identity=_identity(),
        path=path,
    )

    assert written == PublicationReceipt(
        repo_id="owner/repository",
        parent_head="a" * 40,
        publication_revision="b" * 40,
        plan_sha256="c" * 64,
        prepared_fingerprint="f" * 64,
        result_fingerprint="e" * 64,
        publication_generation="exp-test:100:1",
        ordered_task_ids=("task-1",),
    )
    assert load_publication_receipt(_identity(), path) == written
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert len(replace_calls) == 1
    assert replace_calls[0][1] == path
    assert len(fsync_calls) >= 2
    assert not list(path.parent.glob(f".{path.name}.*"))


@pytest.mark.parametrize("symlink_kind", ["path", "ancestor"])
def test_publication_receipt_rejects_symlink_state_path_or_ancestor(
    tmp_path,
    symlink_kind,
):
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    target = real_parent / "target.json"
    target.write_text("unchanged", encoding="utf-8")
    if symlink_kind == "path":
        path = real_parent / "receipt.json"
        path.symlink_to(target)
    else:
        linked_parent = tmp_path / "linked"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        path = linked_parent / "receipt.json"

    with pytest.raises(ValueError, match="symlink"):
        write_publication_receipt(
            _receipt_result(),
            expected_head="a" * 40,
            identity=_identity(),
            path=path,
        )

    assert target.read_text(encoding="utf-8") == "unchanged"


@pytest.mark.parametrize(
    "tamper",
    ["extra", "missing", "plan", "prepared", "task_order"],
)
def test_publication_receipt_rejects_schema_or_identity_tamper(
    tmp_path,
    tamper,
):
    path = tmp_path / "receipt.json"
    write_publication_receipt(
        _receipt_result(),
        expected_head="a" * 40,
        identity=_identity(),
        path=path,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if tamper == "extra":
        payload["unexpected"] = True
    elif tamper == "missing":
        payload.pop("repo_id")
    elif tamper == "plan":
        payload["plan_sha256"] = "not-a-plan"
    elif tamper == "prepared":
        payload["prepared_fingerprint"] = "d" * 64
    else:
        payload["ordered_task_ids"] = ["task-2"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="publication receipt"):
        load_publication_receipt(_identity(), path)


def test_publication_receipt_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / "receipt.json"
    write_publication_receipt(
        _receipt_result(),
        expected_head="a" * 40,
        identity=_identity(),
        path=path,
    )
    encoded = path.read_text(encoding="utf-8").rstrip()
    path.write_text(
        encoded[:-1] + ',"repo_id":"owner/repository"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON keys"):
        load_publication_receipt(_identity(), path)


def test_failed_publication_removes_stale_receipt_and_writes_no_new_one(tmp_path):
    receipt_path = tmp_path / "publication-receipt.json"
    receipt_path.write_text("stale", encoding="utf-8")

    with pytest.raises(OSError, match="failed before mutation"):
        publish_dataset_with_receipt(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            receipt_path=receipt_path,
            api=FakeApi(create_mode="before_failure"),
        )

    assert not receipt_path.exists()


def test_publication_finality_accepts_normal_publication_without_cleanup(tmp_path):
    api, root, receipt_path, publication = _published_state(tmp_path)

    final_head = verify_publication_finality(
        "owner/repository",
        root,
        token="token",
        identity=_identity(),
        receipt_path=receipt_path,
        api=api,
    )

    assert final_head == publication.oid
    revisions = [
        kwargs.get("revision")
        for name, kwargs in api.calls
        if name in {"list_repo_files", "list_repo_commits", "list_repo_tree"}
    ]
    assert "a" * 40 in revisions
    assert "b" * 40 in revisions
    assert [
        kwargs["revision"]
        for name, kwargs in api.calls
        if name == "list_repo_tree"
    ] == [publication.oid]
    assert Counter(
        (kwargs["revision"], kwargs["filename"])
        for name, kwargs in api.calls
        if name == "hf_hub_download"
    ) == Counter({
        (publication.oid, "data/train-00000-of-00001.parquet"): 1,
        (publication.oid, "inference_provenance.json"): 1,
        (publication.oid, "self_report.json"): 1,
    })


def test_publication_finality_accepts_exact_cleanup_child(tmp_path):
    generation = "1" * 64
    api, root, receipt_path, _publication = _published_state(tmp_path)
    cleanup_head = _add_cleanup_commit(api, generation)

    assert verify_publication_finality(
        "owner/repository",
        root,
        token="token",
        identity=_identity(),
        expected_generation=generation,
        receipt_path=receipt_path,
        api=api,
    ) == cleanup_head


def test_publication_finality_rejects_readme_drift_after_cleanup(tmp_path):
    generation = "1" * 64
    api, root, receipt_path, _publication = _published_state(
        tmp_path, include_readme=True
    )
    cleanup_head = _add_cleanup_commit(api, generation)
    original = api.revision_files[cleanup_head]["README.md"]
    assert isinstance(original, Path)
    drift = original.with_name("drift-readme.md")
    drift.write_bytes(b"x" * original.stat().st_size)
    api.revision_files[cleanup_head]["README.md"] = drift

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            expected_generation=generation,
            receipt_path=receipt_path,
            api=api,
        )


@pytest.mark.parametrize("generation", ["1" * 63, "A" * 64, 123])
def test_publication_finality_rejects_malformed_cleanup_generation(
    tmp_path,
    generation,
):
    api, root, receipt_path, _publication = _published_state(tmp_path)

    with pytest.raises(ValueError, match="cleanup generation is invalid"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            expected_generation=generation,
            receipt_path=receipt_path,
            api=api,
        )

    assert api.calls == []


@pytest.mark.parametrize(
    ("title", "description"),
    [
        (
            f"Clean relay checkpoint {'2' * 12}",
            f"relay-cleanup-generation: {'1' * 64}",
        ),
        (
            f"prefix Clean relay checkpoint {'1' * 12}",
            f"relay-cleanup-generation: {'1' * 64}",
        ),
        (
            f"Clean relay checkpoint {'1' * 12}",
            f"relay-cleanup-generation: {'2' * 64}",
        ),
        (
            f"Clean relay checkpoint {'1' * 12}",
            "",
        ),
    ],
)
def test_publication_finality_rejects_cleanup_metadata_or_generation_mismatch(
    tmp_path,
    title,
    description,
):
    generation = "1" * 64
    api, root, receipt_path, _publication = _published_state(tmp_path)
    _add_cleanup_commit(
        api,
        generation,
        title=title,
        description=description,
    )

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            expected_generation=generation,
            receipt_path=receipt_path,
            api=api,
        )


@pytest.mark.parametrize("relationship", ["unrelated-child", "grandchild"])
def test_publication_finality_rejects_unrelated_child_or_grandchild(
    tmp_path,
    relationship,
):
    generation = "1" * 64
    api, root, receipt_path, _publication = _published_state(tmp_path)
    if relationship == "unrelated-child":
        _add_cleanup_commit(api, generation, title="Unrelated commit")
    else:
        _add_cleanup_commit(api, generation, parent="d" * 40)

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            expected_generation=generation,
            receipt_path=receipt_path,
            api=api,
        )


@pytest.mark.parametrize("drift", ["parent", "marker"])
def test_publication_finality_rejects_publication_parent_or_marker_drift(
    tmp_path,
    drift,
):
    api, root, receipt_path, _publication = _published_state(tmp_path)
    if drift == "parent":
        api.parent_override = "d" * 40
    else:
        api.marker_override = "publication-plan-sha256: " + "0" * 64

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            receipt_path=receipt_path,
            api=api,
        )


@pytest.mark.parametrize(
    "mutation",
    ["missing", "extra", "size", "download_hash", "lfs_hash"],
)
def test_publication_finality_rejects_final_managed_tree_or_hash_drift(
    tmp_path,
    mutation,
):
    generation = "1" * 64
    api, root, receipt_path, _publication = _published_state(tmp_path)
    cleanup_head = _add_cleanup_commit(api, generation)
    api.tree_mutations[cleanup_head] = mutation
    if mutation == "lfs_hash":
        api.lfs_paths.add("self_report.json")

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            expected_generation=generation,
            receipt_path=receipt_path,
            api=api,
        )


@pytest.mark.parametrize("after_cleanup", [False, True])
@pytest.mark.parametrize(
    "mutation",
    ["missing_provenance", "provenance_hash", "stale_step2"],
)
def test_publication_finality_rejects_provenance_or_stale_step2_drift(
    tmp_path,
    after_cleanup,
    mutation,
):
    generation = "1" * 64
    api, root, receipt_path, publication = _published_state(tmp_path)
    revision = publication.oid
    expected_generation = None
    if after_cleanup:
        revision = _add_cleanup_commit(api, generation)
        expected_generation = generation
    api.tree_mutations[revision] = mutation

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            expected_generation=expected_generation,
            receipt_path=receipt_path,
            api=api,
        )


def test_publication_finality_revalidates_downloaded_self_report(
    tmp_path,
    monkeypatch,
):
    generation = "1" * 64
    api, root, receipt_path, _publication = _published_state(tmp_path)
    cleanup_head = _add_cleanup_commit(api, generation)
    original_path = api.revision_files[cleanup_head]["self_report.json"]
    assert isinstance(original_path, Path)
    original = original_path.read_bytes()
    drift = original.replace(b"exp-test", b"exp-tost", 1)
    assert len(drift) == len(original)
    drift_path = Path(api.remote_dir.name) / "drift-self-report.json"
    drift_path.write_bytes(drift)
    api.revision_files[cleanup_head]["self_report.json"] = drift_path
    expected_hash = hashlib.sha256(original).hexdigest()
    real_sha256_file = hf_publication._sha256_file

    def trusted_transport_hash(path):
        if path == drift_path:
            return len(original), expected_hash
        return real_sha256_file(path)

    monkeypatch.setattr(
        hf_publication,
        "_sha256_file",
        trusted_transport_hash,
    )

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            expected_generation=generation,
            receipt_path=receipt_path,
            api=api,
        )


def test_publication_finality_rejects_head_advance_during_verification(tmp_path):
    api, root, receipt_path, publication = _published_state(tmp_path)
    api.repo_info_sequence = [publication.oid, "c" * 40]

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            receipt_path=receipt_path,
            api=api,
        )


@pytest.mark.parametrize("tamper", ["plan", "identity"])
def test_publication_finality_rejects_receipt_plan_or_identity_tamper(
    tmp_path,
    tamper,
):
    api, root, receipt_path, _publication = _published_state(tmp_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if tamper == "plan":
        payload["plan_sha256"] = "0" * 64
    else:
        payload["result_fingerprint"] = "d" * 64
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    error = RuntimeError if tamper == "plan" else ValueError
    with pytest.raises(error):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            receipt_path=receipt_path,
            api=api,
        )


def test_publication_finality_fails_closed_on_api_error_and_closes_streams(
    tmp_path,
    monkeypatch,
):
    api, root, receipt_path, _publication = _published_state(tmp_path)
    api.fail_tree = True
    staged = []
    real_publication_files = hf_publication._publication_files

    def capture_publication_files(upload_root):
        files = real_publication_files(upload_root)
        staged.extend(files)
        return files

    monkeypatch.setattr(
        hf_publication,
        "_publication_files",
        capture_publication_files,
    )

    with pytest.raises(RuntimeError, match="finality is unverified"):
        verify_publication_finality(
            "owner/repository",
            root,
            token="token",
            identity=_identity(),
            receipt_path=receipt_path,
            api=api,
        )

    assert staged
    assert all(record.stream.closed for record in staged)


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
        operation
        for operation in commit["operations"]
        if isinstance(operation, CommitOperationAdd)
    ]
    deletions = [
        operation.path_in_repo
        for operation in commit["operations"]
        if isinstance(operation, CommitOperationDelete)
    ]
    assert [operation.path_in_repo for operation in additions] == [
        "data/train-00000-of-00001.parquet",
        "inference_provenance.json",
        "self_report.json",
    ]
    assert all(
        not isinstance(operation.path_or_fileobj, (str, Path))
        for operation in additions
    )
    assert deletions == [
        "data/old.parquet",
        "deliverable_files/task/old.pdf",
        "step2_inference_results.json",
    ]
    assert not {operation.path_in_repo for operation in additions} & set(deletions)
    assert "reference_files/task/input.xlsx" not in deletions


def test_publication_plan_and_receipt_bind_provenance_bytes(tmp_path):
    root = _upload_root(tmp_path)
    first_receipt_path = tmp_path / "first-publication-receipt.json"
    first = publish_dataset_with_receipt(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        receipt_path=first_receipt_path,
        api=FakeApi(),
    )
    first_receipt = load_publication_receipt(_identity(), first_receipt_path)

    provenance_path = root / "inference_provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance_path.write_text(
        json.dumps(provenance, indent=2) + "\n",
        encoding="utf-8",
    )
    second_receipt_path = tmp_path / "second-publication-receipt.json"
    second = publish_dataset_with_receipt(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        receipt_path=second_receipt_path,
        api=FakeApi(),
    )
    second_receipt = load_publication_receipt(_identity(), second_receipt_path)

    assert first.plan_sha256 != second.plan_sha256
    assert first_receipt.plan_sha256 == first.plan_sha256
    assert second_receipt.plan_sha256 == second.plan_sha256


def test_publication_plan_binds_stale_step2_deletion(tmp_path):
    root = _upload_root(tmp_path)
    stale_api = FakeApi()
    with_stale = publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=stale_api,
    )
    commit = next(
        kwargs for name, kwargs in stale_api.calls if name == "create_commit"
    )
    deletion_paths = {
        operation.path_in_repo
        for operation in commit["operations"]
        if isinstance(operation, CommitOperationDelete)
    }
    addition_paths = {
        operation.path_in_repo
        for operation in commit["operations"]
        if isinstance(operation, CommitOperationAdd)
    }

    clean_api = FakeApi()
    clean_api.remote_files.pop("step2_inference_results.json")
    clean_api.revision_files[clean_api.parent] = dict(clean_api.remote_files)
    without_stale = publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=clean_api,
    )

    assert "step2_inference_results.json" in deletion_paths
    assert "step2_inference_results.json" not in addition_paths
    assert with_stale.plan_sha256 != without_stale.plan_sha256


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


def test_publication_rejects_revision_pinned_cache_symlink_with_wrong_bytes(
    tmp_path,
):
    api = FakeApi()
    api.download_symlinks = True
    api.tree_mutation = "download_hash"

    with pytest.raises(RuntimeError, match="outcome is unverified") as captured:
        publish_dataset(
            "owner/repository",
            _upload_root(tmp_path),
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )
    assert isinstance(captured.value.__cause__, ValueError)
    assert "remote file hash mismatch" in str(captured.value.__cause__)


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


@pytest.mark.parametrize("mutation", ["replace", "rewrite"])
def test_publication_uploads_held_bytes_after_source_changes(
    tmp_path,
    mutation,
):
    root = _upload_root(tmp_path)
    source = root / "data" / "train-00000-of-00001.parquet"
    original = source.read_bytes()
    api = FakeApi()

    def change_source():
        if mutation == "replace":
            replacement = source.with_name("replacement.parquet")
            replacement.write_bytes(b"replacement bytes")
            replacement.replace(source)
        else:
            source.write_bytes(b"rewritten bytes")

    api.before_first_remote_call = change_source

    publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=api,
    )

    uploaded = api.remote_files["data/train-00000-of-00001.parquet"]
    assert isinstance(uploaded, Path)
    assert uploaded.read_bytes() == original
    assert source.read_bytes() != original


def test_publication_opens_each_source_once_with_nofollow_and_cloexec(
    tmp_path,
    monkeypatch,
):
    root = _upload_root(tmp_path)
    readme = root / "README.md"
    readme.write_text("readme", encoding="utf-8")
    real_open = hf_publication.os.open
    source_calls = []

    def tracked_open(path, flags, *args, **kwargs):
        candidate = Path(path)
        if candidate == root or root in candidate.parents:
            source_calls.append((candidate, flags))
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(hf_publication.os, "open", tracked_open)

    publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=FakeApi(),
    )

    counts = Counter(path for path, _flags in source_calls)
    assert counts == Counter({
        root / "README.md": 1,
        root / "data" / "train-00000-of-00001.parquet": 1,
        root / "inference_provenance.json": 1,
        root / "self_report.json": 1,
    })
    for _path, flags in source_calls:
        assert flags & os.O_NOFOLLOW
        assert flags & os.O_CLOEXEC
        assert flags & os.O_ACCMODE == os.O_RDONLY


@pytest.mark.parametrize(
    "relative_path",
    [
        "data/train-00000-of-00001.parquet",
        "inference_provenance.json",
    ],
)
def test_publication_rejects_hardlinked_source_before_remote_call(
    tmp_path,
    relative_path,
):
    root = _upload_root(tmp_path)
    source = root / relative_path
    os.link(source, tmp_path / f"{source.name}-hardlink")
    api = FakeApi()

    with pytest.raises(ValueError, match="single-link regular file"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_rejects_symlink_ancestor_above_upload_root(tmp_path):
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    real_root = _upload_root(real_parent)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    api = FakeApi()

    with pytest.raises(ValueError, match="symlink component"):
        publish_dataset(
            "owner/repository",
            linked_parent / real_root.name,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_streams_large_source_without_path_read_bytes(
    tmp_path,
    monkeypatch,
):
    root = _upload_root(tmp_path)
    source = root / "data" / "train-00000-of-00001.parquet"
    source.write_bytes(b"x" * (3 * 1024 * 1024 + 17))
    real_read_bytes = Path.read_bytes

    def guarded_read_bytes(path):
        if path == source:
            raise AssertionError("publication source must not use Path.read_bytes")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)

    publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=FakeApi(),
    )


def test_publication_rejects_source_mutation_during_staging(
    tmp_path,
    monkeypatch,
):
    root = _upload_root(tmp_path)
    source = root / "data" / "train-00000-of-00001.parquet"
    source.write_bytes(b"x" * (2 * 1024 * 1024))
    real_read = hf_publication.os.read
    mutated = False

    def mutating_read(descriptor, size):
        nonlocal mutated
        chunk = real_read(descriptor, size)
        if chunk and not mutated:
            mutated = True
            with source.open("r+b") as stream:
                stream.seek(0)
                stream.write(b"changed")
                stream.flush()
                os.fsync(stream.fileno())
        return chunk

    monkeypatch.setattr(hf_publication.os, "read", mutating_read)
    api = FakeApi()

    with pytest.raises(ValueError, match="changed while staging"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


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
    data = root / "data"
    data.mkdir(parents=True)
    (data / "train-00000-of-00001.parquet").write_bytes(b"parquet")
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


def test_publication_requires_local_inference_provenance_before_remote_call(
    tmp_path,
):
    root = _upload_root(tmp_path)
    (root / "inference_provenance.json").unlink()
    api = FakeApi()

    with pytest.raises(ValueError, match="inference_provenance.json is required"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_rejects_symlinked_inference_provenance_before_remote_call(
    tmp_path,
):
    root = _upload_root(tmp_path)
    provenance = root / "inference_provenance.json"
    target = root / "provenance-target.json"
    provenance.rename(target)
    provenance.symlink_to(target)
    api = FakeApi()

    with pytest.raises(ValueError, match="must be a regular file"):
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
    "mutation",
    ["malformed_json", "experiment", "repository", "task_order"],
)
def test_publication_rejects_invalid_inference_provenance_before_remote_call(
    tmp_path,
    mutation,
):
    root = _upload_root(tmp_path)
    provenance_path = root / "inference_provenance.json"
    if mutation == "malformed_json":
        provenance_path.write_text("{", encoding="utf-8")
    else:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if mutation == "experiment":
            provenance["experiment_id"] = "other-experiment"
        elif mutation == "repository":
            provenance["source_repo_id"] = "other/repository"
        else:
            provenance["ordered_task_ids_sha256"] = "0" * 64
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    api = FakeApi()

    with pytest.raises(ValueError, match="inference provenance is invalid"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_rejects_same_path_byte_drift_before_remote_call(tmp_path):
    api = FakeApi()
    root = _upload_root(tmp_path)
    relative = "deliverable_files/task-1/report.pdf"
    original = b"original"
    output = root / relative
    output.parent.mkdir(parents=True)
    output.write_bytes(original)
    urls, uris = canonical_deliverable_uris([relative], "owner/repository")
    identity = PublicationIdentity(
        experiment_id="exp-test",
        repo_id="owner/repository",
        publication_generation="exp-test:100:1",
        prepared_fingerprint="f" * 64,
        result_fingerprint="e" * 64,
        ordered_task_ids=("task-1",),
        results=(PublicationTaskResult(
            "task-1",
            "",
            (relative,),
            tuple(urls),
            tuple(uris),
            (PublicationFileRecord(
                relative,
                hashlib.sha256(original).hexdigest(),
                len(original),
            ),),
            status="success",
        ),),
        **_narrative_identity_kwargs(),
    )
    report_path = root / "self_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["task_results"][0]["deliverable_files"] = [relative]
    report["task_results"][0]["files_count"] = 1
    report_path.write_text(json.dumps(report), encoding="utf-8")
    output.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="bytes differ from Step 2"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=identity,
            api=api,
        )

    assert api.calls == []


def _cost_ledger_root(tmp_path: Path, *, declare=True, body=b'{"task_id": "task-1"}\n'):
    """Stage an upload root carrying the audit sidecar and its declaration."""
    digest = hashlib.sha256(body).hexdigest()
    overrides = (
        {"cost_ledger": {"path": "cost_ledger.jsonl", "sha256": digest}}
        if declare
        else None
    )
    root = _upload_root(tmp_path, report_overrides=overrides)
    (root / "cost_ledger.jsonl").write_bytes(body)
    return root, digest


def test_publication_carries_a_declared_cost_ledger(tmp_path):
    api = FakeApi()
    root, _ = _cost_ledger_root(tmp_path)

    publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=api,
    )

    additions = [
        operation.path_in_repo
        for operation in api.calls[2][1]["operations"]
        if isinstance(operation, CommitOperationAdd)
    ]
    assert "cost_ledger.jsonl" in additions


def test_publication_rejects_an_undeclared_cost_ledger(tmp_path):
    # A sidecar nobody vouched for would go up under a digest nobody checked.
    api = FakeApi()
    root, _ = _cost_ledger_root(tmp_path, declare=False)

    with pytest.raises(ValueError, match="declares none"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_rejects_a_declared_cost_ledger_that_is_missing(tmp_path):
    # The other direction: readers would chase a receipt that never shipped.
    api = FakeApi()
    root, _ = _cost_ledger_root(tmp_path)
    (root / "cost_ledger.jsonl").unlink()

    with pytest.raises(ValueError, match="declares a cost ledger that is missing"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_rejects_a_cost_ledger_whose_bytes_drifted(tmp_path):
    api = FakeApi()
    root, _ = _cost_ledger_root(tmp_path)
    (root / "cost_ledger.jsonl").write_bytes(b'{"task_id": "task-2"}\n')

    with pytest.raises(ValueError, match="does not match self_report.json"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_rejects_a_cost_ledger_declared_under_another_path(tmp_path):
    # Managed paths drive remote deletion, so the payload never gets to name
    # the file it is published — or deleted — as.
    api = FakeApi()
    body = b'{"task_id": "task-1"}\n'
    root = _upload_root(
        tmp_path,
        report_overrides={
            "cost_ledger": {
                "path": "self_report.json",
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        },
    )
    (root / "cost_ledger.jsonl").write_bytes(body)

    with pytest.raises(ValueError, match="must be published as cost_ledger.jsonl"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_without_a_cost_ledger_stays_unchanged(tmp_path):
    # Uninstrumented runs publish exactly what they published before.
    api = FakeApi()
    root = _upload_root(tmp_path)

    publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=api,
    )

    operations = api.calls[2][1]["operations"]
    assert not any(
        operation.path_in_repo == "cost_ledger.jsonl" for operation in operations
    )


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
        ({
            "task_results": [_report_task_row(task_id="task-2")],
        }, "result task set mismatch"),
        ({
            "task_results": [_report_task_row(deliverable_summary="stale")],
        }, "deliverable summary mismatch"),
        ({
            "task_results": [_report_task_row(
                deliverable_files=["deliverable_files/task-1/stale.pdf"],
            )],
        }, "deliverable files mismatch"),
        ({
            "task_results": [_report_task_row(status="error")],
        }, "result status mismatch"),
        ({
            "task_results": [_report_task_row(qa_score=1)],
        }, "task result projection mismatch"),
        ({
            "summary": _report_summary(success_count=0),
        }, "summary mismatch"),
        ({
            "error_tasks": [{
                "task_id": "task-1",
                "sector": "",
                "occupation": "",
                "error": "stale error",
            }],
        }, "error task projection mismatch"),
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


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"narrative_model": "gpt-5.4-pro"}, "narrative model mismatch"),
        ({"narrative_reasoning_effort": "high"}, "narrative reasoning mismatch"),
        ({"narrative_runtime_fingerprint": "c" * 64}, "narrative fingerprint mismatch"),
        ({"narrative_runtime_fingerprint": None}, "narrative identity is incomplete"),
    ],
)
def test_publication_rejects_wrong_or_partial_narrative_identity(
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


def test_publication_rejects_missing_narrative_identity_keys(tmp_path):
    api = FakeApi()
    root = _upload_root(tmp_path)
    report_path = root / "self_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for field in (
        "narrative_model",
        "narrative_reasoning_effort",
        "narrative_runtime_fingerprint",
    ):
        del report["meta"][field]
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="narrative identity is incomplete"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


@pytest.mark.parametrize("invalid_value", [None, 7, "", "   "])
def test_publication_rejects_invalid_model_backed_narrative(
    tmp_path, invalid_value
):
    api = FakeApi()
    root = _upload_root(tmp_path, report_overrides={
        "narrative": {
            "overview": invalid_value,
            "quality_analysis": "quality",
            "failure_patterns": "failures",
            "recommendations": "recommendations",
        },
    })

    with pytest.raises(ValueError, match="model-backed narrative is invalid"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=_identity(),
            api=api,
        )

    assert api.calls == []


def test_publication_accepts_exact_model_free_narrative_fallback(tmp_path):
    root = _upload_root(tmp_path, report_overrides={
        "narrative_model": None,
        "narrative_reasoning_effort": None,
        "narrative_runtime_fingerprint": None,
        "narrative": {
            "overview": "",
            "quality_analysis": "",
            "failure_patterns": "",
            "recommendations": "",
        },
    })

    result = publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=_identity(),
        api=FakeApi(),
    )

    assert result.oid == "b" * 40


def test_publication_accepts_exact_step6_projection_with_v2_task_fields(tmp_path):
    result = PublicationTaskResult(
        "task-1",
        "finished output",
        (),
        (),
        (),
        status="success",
        sector="Financial Services",
        occupation="Financial Analyst",
        retried=True,
        files_count=4,
        qa_score=7.25,
        qa_passed=True,
        qa_issues=["minor issue"],
        qa_suggestion="tighten formatting",
        latency_ms=100.6,
        observability={"trace_id": "trace-1"},
        instruction="review the workbook",
        reference_file_urls=["https://example.test/reference.xlsx"],
    )
    identity = PublicationIdentity(
        experiment_id="exp-test",
        repo_id="owner/repository",
        publication_generation="exp-test:100:1",
        prepared_fingerprint="f" * 64,
        result_fingerprint="e" * 64,
        ordered_task_ids=("task-1",),
        results=(result,),
        **_narrative_identity_kwargs(),
    )
    row = _report_task_row(
        sector="Financial Services",
        occupation="Financial Analyst",
        retried=True,
        files_count=4,
        qa_score=7.25,
        qa_passed=True,
        qa_issues=["minor issue"],
        qa_suggestion="tighten formatting",
        latency_ms=100.6,
        observability={"trace_id": "trace-1"},
        deliverable_summary="finished output",
        instruction="review the workbook",
        reference_file_urls=["https://example.test/reference.xlsx"],
        prompt_classification={"needs_files": True},
        policy_results={"strict": {"needs_files": True}},
    )
    root = _upload_root(tmp_path, report_overrides={
        "summary": _report_summary(
            retried_count=1,
            avg_qa_score=7.25,
            min_qa_score=7.25,
            max_qa_score=7.25,
            avg_latency_ms=101,
            max_latency_ms=101,
            total_latency_ms=101,
        ),
        "task_results": [row],
    })

    result = publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=identity,
        api=FakeApi(),
    )

    assert result.oid == "b" * 40


def test_publication_binds_exact_ordered_truthy_error_projection(tmp_path):
    results = (
        PublicationTaskResult(
            "task-1",
            "",
            (),
            (),
            (),
            status="error",
            sector="Sector A",
            occupation="Occupation A",
            error="first failure",
        ),
        PublicationTaskResult(
            "task-2",
            "",
            (),
            (),
            (),
            status="error",
            sector="Sector B",
            occupation="Occupation B",
            error="second failure",
        ),
    )
    identity = PublicationIdentity(
        experiment_id="exp-test",
        repo_id="owner/repository",
        publication_generation="exp-test:100:1",
        prepared_fingerprint="f" * 64,
        result_fingerprint="e" * 64,
        ordered_task_ids=("task-1", "task-2"),
        results=results,
        **_narrative_identity_kwargs(),
    )
    error_tasks = [
        {
            "task_id": "task-1",
            "sector": "Sector A",
            "occupation": "Occupation A",
            "error_code": "task_execution_error",
            "error_type": "TaskExecutionError",
        },
        {
            "task_id": "task-2",
            "sector": "Sector B",
            "occupation": "Occupation B",
            "error_code": "task_execution_error",
            "error_type": "TaskExecutionError",
        },
    ]
    root = _upload_root(
        tmp_path,
        report_overrides={
            "ordered_task_ids": ["task-1", "task-2"],
            "summary": _report_summary(
                total_tasks=2,
                success_count=0,
                success_rate_pct=0.0,
                error_count=2,
            ),
            "task_results": [
                _report_task_row(
                    status="error",
                    sector="Sector A",
                    occupation="Occupation A",
                ),
                _report_task_row(
                    task_id="task-2",
                    status="error",
                    sector="Sector B",
                    occupation="Occupation B",
                ),
            ],
            "error_tasks": error_tasks,
        },
        provenance_task_ids=("task-1", "task-2"),
    )

    publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=identity,
        api=FakeApi(),
    )

    report_path = root / "self_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["error_tasks"].reverse()
    report_path.write_text(json.dumps(report), encoding="utf-8")
    api = FakeApi()
    with pytest.raises(ValueError, match="error task projection mismatch"):
        publish_dataset(
            "owner/repository",
            root,
            token="token",
            expected_head="a" * 40,
            identity=identity,
            api=api,
        )
    assert api.calls == []


def test_publication_sends_more_than_250_files_in_one_create_commit(tmp_path):
    api = FakeApi()
    root = _upload_root(tmp_path)
    deliverables = root / "deliverable_files" / "task-1"
    deliverables.mkdir(parents=True)
    files = []
    records = []
    for index in range(251):
        relative = f"deliverable_files/task-1/result-{index:03d}.txt"
        content = str(index).encode("utf-8")
        (root / relative).write_bytes(content)
        files.append(relative)
        records.append(PublicationFileRecord(
            path=relative,
            sha256=hashlib.sha256(content).hexdigest(),
            size=len(content),
        ))
    urls, uris = canonical_deliverable_uris(files, "owner/repository")
    identity = PublicationIdentity(
        experiment_id="exp-test",
        repo_id="owner/repository",
        publication_generation="exp-test:100:1",
        prepared_fingerprint="f" * 64,
        result_fingerprint="e" * 64,
        ordered_task_ids=("task-1",),
        results=(PublicationTaskResult(
            "task-1",
            "",
            tuple(files),
            tuple(urls),
            tuple(uris),
            tuple(records),
            status="success",
        ),),
        **_narrative_identity_kwargs(),
    )
    report_path = root / "self_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["task_results"][0]["deliverable_files"] = files
    report["task_results"][0]["files_count"] = len(files)
    report_path.write_text(json.dumps(report), encoding="utf-8")

    publish_dataset(
        "owner/repository",
        root,
        token="token",
        expected_head="a" * 40,
        identity=identity,
        api=api,
    )

    create_calls = [kwargs for name, kwargs in api.calls if name == "create_commit"]
    assert len(create_calls) == 1
    additions = [
        operation
        for operation in create_calls[0]["operations"]
        if isinstance(operation, CommitOperationAdd)
    ]
    assert len(additions) == 254


def _write_pipeline_identity(tmp_path: Path) -> tuple[Path, Path, dict]:
    prepared = {
        "experiment_id": "exp-test",
        "publication_generation": "exp-test:100:1",
        "source": "owner/repository",
        "task_scope": {
            "expected_count": 2,
            "task_ids": ["task-1", "task-2"],
        },
        "tasks": [
            {
                "task_id": "task-1",
                "sector": "Financial Services",
                "occupation": "Financial Analyst",
                "instruction": "I" * 2105,
                "reference_file_urls": [
                    "https://example.test/reference.xlsx"
                ],
            },
            {
                "task_id": "task-2",
                "sector": "Public Sector",
                "occupation": "Policy Analyst",
                "instruction": "",
                "reference_file_urls": [],
            },
        ],
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)
    inference = {
        "experiment_id": "exp-test",
        "publication_generation": "exp-test:100:1",
        "source": "owner/repository",
        "execution_mode": "subprocess",
        "prepared_fingerprint": prepared["prepared_fingerprint"],
        "ordered_task_ids": ["task-1", "task-2"],
        "results": [
            {
                "task_id": "task-1",
                "status": "success",
                "resume_round": 1,
                "qa": {
                    "score": 8.25,
                    "passed": True,
                    "issues": ["minor issue"],
                    "suggestion": "tighten formatting",
                },
                "latency_ms": 150.6,
                "observability": {"trace_id": "trace-1"},
                "error": "",
                "deliverable_text": "current text",
                "deliverable_files": ["deliverable_files/task-1/report.pdf"],
                "deliverable_file_records": [{
                    "path": "deliverable_files/task-1/report.pdf",
                    "sha256": "a" * 64,
                    "size": 7,
                }],
            },
            {
                "task_id": "task-2",
                "status": "error",
                "qa": {
                    "score": None,
                    "passed": False,
                    "issues": [],
                    "suggestion": "retry with source data",
                },
                "latency_ms": 0,
                "observability": {},
                "error": "inference failed",
                "deliverable_text": None,
                "deliverable_files": [],
                "deliverable_file_records": [],
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
                (PublicationFileRecord(
                    "deliverable_files/task-1/report.pdf",
                    "a" * 64,
                    7,
                ),),
                status="success",
                sector="Financial Services",
                occupation="Financial Analyst",
                retried=True,
                files_count=1,
                qa_score=8.25,
                qa_passed=True,
                qa_issues=["minor issue"],
                qa_suggestion="tighten formatting",
                latency_ms=150.6,
                observability={"trace_id": "trace-1"},
                instruction="I" * 2000,
                reference_file_urls=[
                    "https://example.test/reference.xlsx"
                ],
                error="",
            ),
            PublicationTaskResult(
                "task-2",
                "",
                (),
                (),
                (),
                status="error",
                sector="Public Sector",
                occupation="Policy Analyst",
                retried=False,
                files_count=0,
                qa_score=None,
                qa_passed=False,
                qa_issues=[],
                qa_suggestion="retry with source data",
                latency_ms=0,
                observability={},
                instruction="",
                reference_file_urls=[],
                error="inference failed",
            ),
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