import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.rubric_loader as rubric_loader_module
from core.rubric_loader import RubricLoader


RUBRIC_SHA = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
PARQUET_PATH = "data/train-00000-of-00001.parquet"


def _write_parquet_bytes(root: Path, payload: bytes = b"fake parquet bytes") -> Path:
    parquet_path = root / PARQUET_PATH
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_path.write_bytes(payload)
    return parquet_path


def _write_valid_snapshot(
    cache_dir: Path,
    *,
    payload: bytes = b"verified parquet bytes",
    repo_id: str = "openai/gdpval",
    rubric_sha: str = RUBRIC_SHA,
) -> Path:
    snapshot_root = cache_dir / RubricLoader.SNAPSHOT_DIRNAME / rubric_sha
    parquet_path = _write_parquet_bytes(snapshot_root, payload)
    manifest = {
        "schema_version": 1,
        "repo_id": repo_id,
        "rubric_sha": rubric_sha,
        "parquet_files": [
            {
                "path": PARQUET_PATH,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        ],
    }
    (snapshot_root / RubricLoader.MANIFEST_FILENAME).write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return snapshot_root


def _mock_task_loading(monkeypatch, loaded_roots: list[Path]) -> None:
    monkeypatch.setattr(
        RubricLoader,
        "_load_tasks_from_parquet",
        lambda self, root: loaded_roots.append(root) or {},
    )


def test_explicit_full_sha_is_normalized_without_hf_api(monkeypatch, tmp_path):
    monkeypatch.setattr(
        rubric_loader_module,
        "HfApi",
        lambda: pytest.fail("HfApi must not resolve an explicit full SHA"),
    )

    loader = RubricLoader(revision=RUBRIC_SHA.upper(), cache_dir=str(tmp_path))

    assert loader.rubric_sha == RUBRIC_SHA
    assert loader.rubric_short_sha == RUBRIC_SHA[:7]


def test_mutable_revision_resolves_and_normalizes_full_sha(monkeypatch, tmp_path):
    calls = []

    class FakeApi:
        def dataset_info(self, repo_id, revision):
            calls.append((repo_id, revision))
            return SimpleNamespace(sha=RUBRIC_SHA.upper())

    monkeypatch.setattr(rubric_loader_module, "HfApi", FakeApi)
    loader = RubricLoader(revision="main", cache_dir=str(tmp_path))

    assert loader.rubric_sha == RUBRIC_SHA
    assert loader.rubric_sha == RUBRIC_SHA
    assert calls == [("openai/gdpval", "main")]


@pytest.mark.parametrize("resolved_sha", [None, "11e7900", "g" * 40, "a" * 39])
def test_invalid_resolved_sha_fails_closed(monkeypatch, tmp_path, resolved_sha):
    class FakeApi:
        def dataset_info(self, repo_id, revision):
            return SimpleNamespace(sha=resolved_sha)

    monkeypatch.setattr(rubric_loader_module, "HfApi", FakeApi)

    with pytest.raises(RuntimeError, match="full 40-character"):
        RubricLoader(revision="main", cache_dir=str(tmp_path)).rubric_sha


def test_mutable_revision_never_falls_back_to_legacy_parquet(monkeypatch, tmp_path):
    legacy_path = _write_parquet_bytes(tmp_path, b"stale legacy parquet")

    class FailingApi:
        def dataset_info(self, repo_id, revision):
            raise ConnectionError("offline")

    monkeypatch.setattr(rubric_loader_module, "HfApi", FailingApi)
    monkeypatch.setattr(
        rubric_loader_module,
        "snapshot_download",
        lambda **kwargs: pytest.fail("download must not run without a resolved SHA"),
    )

    loader = RubricLoader(revision="main", cache_dir=str(tmp_path))
    with pytest.raises(RuntimeError, match="immutable SHA"):
        loader.load_all()

    assert legacy_path.read_bytes() == b"stale legacy parquet"


def test_first_download_uses_full_sha_and_promotes_manifest_snapshot(
    monkeypatch, tmp_path
):
    legacy_path = _write_parquet_bytes(tmp_path, b"stale legacy parquet")
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        _write_parquet_bytes(Path(kwargs["local_dir"]))

    monkeypatch.setattr(
        rubric_loader_module, "snapshot_download", fake_snapshot_download
    )
    loaded_roots = []
    _mock_task_loading(monkeypatch, loaded_roots)

    loader = RubricLoader(revision=RUBRIC_SHA, cache_dir=str(tmp_path))

    assert loader.load_all() == []
    snapshot_root = tmp_path / RubricLoader.SNAPSHOT_DIRNAME / RUBRIC_SHA
    assert loaded_roots == [snapshot_root]
    assert calls == [
        {
            "repo_id": "openai/gdpval",
            "repo_type": "dataset",
            "revision": RUBRIC_SHA,
            "local_dir": calls[0]["local_dir"],
            "allow_patterns": ["data/*.parquet"],
        }
    ]
    assert Path(calls[0]["local_dir"]).parent == snapshot_root.parent
    assert Path(calls[0]["local_dir"]).name.startswith(f".{RUBRIC_SHA}.staging-")
    assert not Path(calls[0]["local_dir"]).exists()
    manifest = json.loads(
        (snapshot_root / RubricLoader.MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["repo_id"] == "openai/gdpval"
    assert manifest["rubric_sha"] == RUBRIC_SHA
    assert manifest["parquet_files"] == [
        {
            "path": PARQUET_PATH,
            "sha256": hashlib.sha256(b"fake parquet bytes").hexdigest(),
            "size": len(b"fake parquet bytes"),
        }
    ]
    assert legacy_path.read_bytes() == b"stale legacy parquet"


def test_legacy_hf_download_disables_local_dir_symlinks(monkeypatch, tmp_path):
    calls = []

    def legacy_snapshot_download(*, local_dir_use_symlinks="auto", **kwargs):
        calls.append(local_dir_use_symlinks)
        _write_parquet_bytes(Path(kwargs["local_dir"]))

    monkeypatch.setattr(
        rubric_loader_module, "snapshot_download", legacy_snapshot_download
    )
    loaded_roots = []
    _mock_task_loading(monkeypatch, loaded_roots)

    RubricLoader(revision=RUBRIC_SHA, cache_dir=str(tmp_path)).load_all()

    assert calls == [False]


def test_valid_manifest_reuse_avoids_download_and_uses_pinned_root(
    monkeypatch, tmp_path
):
    snapshot_root = _write_valid_snapshot(tmp_path)
    monkeypatch.setattr(
        rubric_loader_module,
        "snapshot_download",
        lambda **kwargs: pytest.fail("valid pinned snapshot must not redownload"),
    )
    loaded_roots = []
    _mock_task_loading(monkeypatch, loaded_roots)

    loader = RubricLoader(revision=RUBRIC_SHA, cache_dir=str(tmp_path))

    assert loader.load_all() == []
    assert loaded_roots == [snapshot_root]


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_manifest",
        "malformed_manifest",
        "wrong_repo",
        "wrong_sha",
        "missing_file",
        "wrong_hash",
        "wrong_size",
        "extra_parquet",
        "symlink_data_directory",
    ],
)
def test_corrupted_snapshot_fails_without_redownload(
    monkeypatch, tmp_path, corruption
):
    snapshot_root = _write_valid_snapshot(tmp_path)
    manifest_path = snapshot_root / RubricLoader.MANIFEST_FILENAME
    parquet_path = snapshot_root / PARQUET_PATH

    if corruption == "missing_manifest":
        manifest_path.unlink()
    elif corruption == "malformed_manifest":
        manifest_path.write_text("{not-json", encoding="utf-8")
    elif corruption in {"wrong_repo", "wrong_sha", "wrong_size"}:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if corruption == "wrong_repo":
            manifest["repo_id"] = "other/repo"
        elif corruption == "wrong_sha":
            manifest["rubric_sha"] = "f" * 40
        else:
            manifest["parquet_files"][0]["size"] += 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif corruption == "missing_file":
        parquet_path.unlink()
    elif corruption == "wrong_hash":
        parquet_path.write_bytes(b"corrupted parquet bytes")
    elif corruption == "extra_parquet":
        (snapshot_root / "data" / "extra.parquet").write_bytes(
            b"second parquet"
        )
    else:
        external_data = tmp_path / "external-data"
        external_data.mkdir()
        (external_data / parquet_path.name).write_bytes(parquet_path.read_bytes())
        parquet_path.unlink()
        parquet_path.parent.rmdir()
        parquet_path.parent.symlink_to(external_data, target_is_directory=True)

    download_calls = []
    monkeypatch.setattr(
        rubric_loader_module,
        "snapshot_download",
        lambda **kwargs: download_calls.append(kwargs),
    )

    with pytest.raises(RuntimeError, match="Rubric snapshot"):
        RubricLoader(revision=RUBRIC_SHA, cache_dir=str(tmp_path)).load_all()

    assert download_calls == []


def test_failed_first_download_cleans_only_its_staging_directory(
    monkeypatch, tmp_path
):
    user_file = tmp_path / "user-owned.txt"
    user_file.write_text("keep", encoding="utf-8")
    legacy_path = _write_parquet_bytes(tmp_path, b"keep legacy")
    staging_paths = []

    def failing_download(**kwargs):
        staging_root = Path(kwargs["local_dir"])
        staging_paths.append(staging_root)
        _write_parquet_bytes(staging_root, b"partial")
        raise ConnectionError("interrupted")

    monkeypatch.setattr(rubric_loader_module, "snapshot_download", failing_download)

    with pytest.raises(RuntimeError, match="Failed to download rubric snapshot"):
        RubricLoader(revision=RUBRIC_SHA, cache_dir=str(tmp_path)).load_all()

    assert len(staging_paths) == 1
    assert not staging_paths[0].exists()
    assert user_file.read_text(encoding="utf-8") == "keep"
    assert legacy_path.read_bytes() == b"keep legacy"


def test_concurrent_valid_winner_is_reused_and_only_staging_is_discarded(
    monkeypatch, tmp_path
):
    staging_paths = []

    def concurrent_download(**kwargs):
        staging_root = Path(kwargs["local_dir"])
        staging_paths.append(staging_root)
        _write_parquet_bytes(staging_root, b"losing staged bytes")
        _write_valid_snapshot(tmp_path, payload=b"winning verified bytes")

    monkeypatch.setattr(
        rubric_loader_module, "snapshot_download", concurrent_download
    )
    loaded_roots = []
    _mock_task_loading(monkeypatch, loaded_roots)

    loader = RubricLoader(revision=RUBRIC_SHA, cache_dir=str(tmp_path))

    assert loader.load_all() == []
    winner_root = tmp_path / RubricLoader.SNAPSHOT_DIRNAME / RUBRIC_SHA
    assert loaded_roots == [winner_root]
    assert (winner_root / PARQUET_PATH).read_bytes() == b"winning verified bytes"
    assert len(staging_paths) == 1
    assert not staging_paths[0].exists()


def test_reference_download_uses_resolved_full_sha(monkeypatch, tmp_path):
    class FakeApi:
        def dataset_info(self, repo_id, revision):
            return SimpleNamespace(sha=RUBRIC_SHA)

    calls = []

    def fake_hf_hub_download(**kwargs):
        calls.append(kwargs)
        return str(tmp_path / "reference.xlsx")

    monkeypatch.setattr(rubric_loader_module, "HfApi", FakeApi)
    monkeypatch.setattr(
        rubric_loader_module, "hf_hub_download", fake_hf_hub_download
    )
    loader = RubricLoader(revision="main", cache_dir=str(tmp_path))

    result = loader._download_hf_paths(["reference_files/reference.xlsx"])

    assert result == {
        "reference_files/reference.xlsx": str(
            (tmp_path / "reference.xlsx").resolve()
        )
    }
    assert calls[0]["revision"] == RUBRIC_SHA