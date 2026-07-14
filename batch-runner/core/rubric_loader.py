"""Rubric loader for openai/gdpval dataset.

Loads task-level rubric_json from HuggingFace parquet files with local cache.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
from huggingface_hub import HfApi, hf_hub_download, snapshot_download

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RubricItem:
    rubric_item_id: str
    criterion: str
    score: int
    required: Optional[bool]


@dataclass(frozen=True)
class TaskRubric:
    task_id: str
    sector: str
    occupation: str
    prompt: str
    rubric_items: list[RubricItem]
    rubric_pretty: str
    reference_files: list[str]
    gold_deliverable_files: list[str]

    @property
    def max_score(self) -> int:
        """Maximum achievable positive score on this task.

        PR1 task 102 — was `sum(it.score for it in rubric_items)`, which
        arithmetically summed positive AND negative item scores and
        produced `total_max <= 0` for 4 of 220 exp003 tasks (one as low
        as -330). That collapsed pct into mathematical nonsense which
        the downstream [0,100] clamp silently hid.

        New definition: sum of POSITIVE item scores only. Negative
        penalty items still subtract from `total_awarded` (via the judge's
        emitted awarded_score), so the resulting pct sits in
        `[-penalty_ceiling, 100]` — the clamp then correctly floors
        catastrophic violations at 0 while preserving the raw value in
        `TaskGrade.pct_raw` for diagnostics.
        See: data/grades/_validation/SCORE_MATH_AUDIT.md (Option 1).
        """
        return sum(max(0, it.score) for it in self.rubric_items)


class RubricLoader:
    """openai/gdpval HF rubric loader with local cache."""

    DEFAULT_REPO_ID = "openai/gdpval"
    DEFAULT_CACHE_DIR = "data/gdpval-local"
    SNAPSHOT_DIRNAME = "rubric_snapshots"
    MANIFEST_FILENAME = "rubric_snapshot_manifest.json"

    def __init__(
        self,
        repo_id: str = DEFAULT_REPO_ID,
        revision: str = "main",
        cache_dir: str = DEFAULT_CACHE_DIR,
    ):
        self.repo_id = repo_id
        self.revision = revision
        self.cache_dir = Path(cache_dir)
        self._tasks: dict[str, TaskRubric] | None = None
        self._sha: str | None = None

    def load_all(self) -> list[TaskRubric]:
        self._ensure_loaded()
        assert self._tasks is not None
        return list(self._tasks.values())

    def load(self, task_id: str) -> TaskRubric:
        self._ensure_loaded()
        assert self._tasks is not None
        if task_id not in self._tasks:
            raise KeyError(task_id)
        return self._tasks[task_id]

    @property
    def rubric_sha(self) -> str:
        if self._sha is not None:
            return self._sha

        if isinstance(self.revision, str) and re.fullmatch(
            r"[0-9a-fA-F]{40}", self.revision
        ):
            self._sha = self.revision.lower()
            return self._sha

        try:
            info = HfApi().dataset_info(self.repo_id, revision=self.revision)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to resolve rubric revision {self.revision!r} to an immutable SHA: {exc}"
            ) from exc

        resolved_sha = getattr(info, "sha", None)
        if not isinstance(resolved_sha, str) or not re.fullmatch(
            r"[0-9a-fA-F]{40}", resolved_sha
        ):
            raise RuntimeError(
                "Resolved rubric revision did not return a full 40-character HF commit SHA"
            )
        self._sha = resolved_sha.lower()
        return self._sha

    @property
    def rubric_short_sha(self) -> str:
        return self.rubric_sha[:7]

    def download_reference_files(self, task: TaskRubric) -> dict[str, str]:
        return self._download_hf_paths(task.reference_files)

    def download_gold_files(self, task: TaskRubric) -> dict[str, str]:
        return self._download_hf_paths(task.gold_deliverable_files)

    def _download_hf_paths(self, paths: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for hf_path in paths:
            try:
                local = hf_hub_download(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    filename=hf_path,
                    revision=self.rubric_sha,
                    cache_dir=str(self.cache_dir),
                )
                result[hf_path] = str(Path(local).resolve())
            except Exception as exc:
                logger.warning("Failed to download %s: %s", hf_path, exc)
        return result

    def _ensure_loaded(self) -> None:
        if self._tasks is not None:
            return

        snapshot_root = self._ensure_pinned_snapshot()
        self._tasks = self._load_tasks_from_parquet(snapshot_root)

    def _ensure_pinned_snapshot(self) -> Path:
        rubric_sha = self.rubric_sha
        snapshots_dir = self.cache_dir / self.SNAPSHOT_DIRNAME
        snapshot_root = snapshots_dir / rubric_sha

        if snapshot_root.exists() or snapshot_root.is_symlink():
            self._validate_snapshot(snapshot_root)
            return snapshot_root

        snapshots_dir.mkdir(parents=True, exist_ok=True)
        staging_root = Path(
            tempfile.mkdtemp(
                prefix=f".{rubric_sha}.staging-",
                dir=str(snapshots_dir),
            )
        )
        try:
            try:
                download_kwargs = {
                    "repo_id": self.repo_id,
                    "repo_type": "dataset",
                    "revision": rubric_sha,
                    "local_dir": str(staging_root),
                    "allow_patterns": ["data/*.parquet"],
                }
                if "local_dir_use_symlinks" in inspect.signature(
                    snapshot_download
                ).parameters:
                    download_kwargs["local_dir_use_symlinks"] = False
                snapshot_download(**download_kwargs)
            except Exception as exc:
                if snapshot_root.exists() or snapshot_root.is_symlink():
                    self._validate_snapshot(snapshot_root)
                    return snapshot_root
                raise RuntimeError(
                    f"Failed to download rubric snapshot at {rubric_sha}: {exc}"
                ) from exc

            manifest = self._build_snapshot_manifest(staging_root)
            manifest_path = staging_root / self.MANIFEST_FILENAME
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            if snapshot_root.exists() or snapshot_root.is_symlink():
                self._validate_snapshot(snapshot_root)
                return snapshot_root
            try:
                staging_root.rename(snapshot_root)
            except OSError as exc:
                if not (snapshot_root.exists() or snapshot_root.is_symlink()):
                    raise RuntimeError(
                        f"Failed to promote rubric snapshot at {rubric_sha}: {exc}"
                    ) from exc
                self._validate_snapshot(snapshot_root)
                return snapshot_root

            self._validate_snapshot(snapshot_root)
            return snapshot_root
        finally:
            if staging_root.exists():
                shutil.rmtree(staging_root)

    def _build_snapshot_manifest(self, snapshot_root: Path) -> dict:
        parquet_files = self._snapshot_parquet_files(snapshot_root)
        if not parquet_files:
            raise RuntimeError(
                f"Downloaded rubric snapshot contains no parquet files for {self.rubric_sha}"
            )

        files = []
        for parquet_path in parquet_files:
            relative_path = parquet_path.relative_to(snapshot_root).as_posix()
            sha256, size = self._hash_file(parquet_path)
            files.append(
                {
                    "path": relative_path,
                    "sha256": sha256,
                    "size": size,
                }
            )
        return {
            "schema_version": 1,
            "repo_id": self.repo_id,
            "rubric_sha": self.rubric_sha,
            "parquet_files": files,
        }

    def _validate_snapshot(self, snapshot_root: Path) -> None:
        manifest_path = snapshot_root / self.MANIFEST_FILENAME
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise RuntimeError(
                f"Rubric snapshot manifest is missing or invalid for {self.rubric_sha}"
            )

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Rubric snapshot manifest is malformed for {self.rubric_sha}: {exc}"
            ) from exc

        if not isinstance(manifest, dict):
            raise RuntimeError(
                f"Rubric snapshot manifest is malformed for {self.rubric_sha}"
            )
        if manifest.get("schema_version") != 1:
            raise RuntimeError(
                f"Rubric snapshot manifest version mismatch for {self.rubric_sha}"
            )
        if manifest.get("repo_id") != self.repo_id:
            raise RuntimeError(
                f"Rubric snapshot repo identity mismatch for {self.rubric_sha}"
            )
        if manifest.get("rubric_sha") != self.rubric_sha:
            raise RuntimeError(
                f"Rubric snapshot commit identity mismatch for {self.rubric_sha}"
            )

        file_entries = manifest.get("parquet_files")
        if not isinstance(file_entries, list) or not file_entries:
            raise RuntimeError(
                f"Rubric snapshot parquet manifest is missing for {self.rubric_sha}"
            )

        expected_paths: list[str] = []
        entries_by_path: dict[str, dict] = {}
        for entry in file_entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size"}:
                raise RuntimeError(
                    f"Rubric snapshot parquet manifest is malformed for {self.rubric_sha}"
                )
            relative_path = entry.get("path")
            expected_hash = entry.get("sha256")
            expected_size = entry.get("size")
            if (
                not isinstance(relative_path, str)
                or not re.fullmatch(r"data/[^/]+\.parquet", relative_path)
                or not isinstance(expected_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
                or not isinstance(expected_size, int)
                or isinstance(expected_size, bool)
                or expected_size < 0
                or relative_path in entries_by_path
            ):
                raise RuntimeError(
                    f"Rubric snapshot parquet manifest is malformed for {self.rubric_sha}"
                )
            expected_paths.append(relative_path)
            entries_by_path[relative_path] = entry

        actual_files = self._snapshot_parquet_files(snapshot_root)
        actual_paths = [
            path.relative_to(snapshot_root).as_posix() for path in actual_files
        ]
        if sorted(expected_paths) != actual_paths:
            raise RuntimeError(
                f"Rubric snapshot parquet set mismatch for {self.rubric_sha}"
            )

        for parquet_path in actual_files:
            if parquet_path.is_symlink():
                raise RuntimeError(
                    f"Rubric snapshot parquet file is not regular for {self.rubric_sha}"
                )
            relative_path = parquet_path.relative_to(snapshot_root).as_posix()
            actual_hash, actual_size = self._hash_file(parquet_path)
            entry = entries_by_path[relative_path]
            if entry["sha256"] != actual_hash or entry["size"] != actual_size:
                raise RuntimeError(
                    f"Rubric snapshot parquet integrity mismatch for {self.rubric_sha}"
                )

    @staticmethod
    def _snapshot_parquet_files(snapshot_root: Path) -> list[Path]:
        if not snapshot_root.is_dir() or snapshot_root.is_symlink():
            raise RuntimeError("Rubric snapshot root is not a regular directory")
        if (snapshot_root / "data").is_symlink():
            raise RuntimeError("Rubric snapshot data directory is not regular")
        parquet_files = sorted(snapshot_root.rglob("*.parquet"))
        for parquet_path in parquet_files:
            relative_path = parquet_path.relative_to(snapshot_root).as_posix()
            if not re.fullmatch(r"data/[^/]+\.parquet", relative_path):
                raise RuntimeError(
                    f"Rubric snapshot contains parquet outside data/: {relative_path}"
                )
            if parquet_path.is_symlink() or not parquet_path.is_file():
                raise RuntimeError(
                    f"Rubric snapshot parquet is not a regular file: {relative_path}"
                )
        return parquet_files

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def _load_tasks_from_parquet(
        self, snapshot_root: Path
    ) -> dict[str, TaskRubric]:
        parquet_files = sorted(snapshot_root.glob("data/*.parquet"))
        if not parquet_files:
            raise RuntimeError(
                f"No parquet files found in pinned rubric snapshot: {self.rubric_sha}"
            )

        rows = []
        for pq in parquet_files:
            df = pd.read_parquet(pq)
            rows.extend(df.to_dict("records"))

        tasks: dict[str, TaskRubric] = {}
        for row in rows:
            task_id = str(row.get("task_id", "")).strip()
            if not task_id:
                continue

            rubric_items_raw = row.get("rubric_json")
            rubric_items = self._parse_rubric_items(task_id, rubric_items_raw)

            reference_files = self._coerce_list(row.get("reference_files"))
            gold_files = self._coerce_list(row.get("deliverable_files"))

            task = TaskRubric(
                task_id=task_id,
                sector=str(row.get("sector") or ""),
                occupation=str(row.get("occupation") or ""),
                prompt=str(row.get("prompt") or ""),
                rubric_items=rubric_items,
                rubric_pretty=str(row.get("rubric_pretty") or ""),
                reference_files=reference_files,
                gold_deliverable_files=gold_files,
            )
            tasks[task_id] = task

        return tasks

    def _parse_rubric_items(self, task_id: str, raw: object) -> list[RubricItem]:
        if raw is None:
            return []

        parsed = raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"rubric_json parse failed: {task_id}") from exc

        if isinstance(parsed, np.ndarray):
            parsed = parsed.tolist()

        if not isinstance(parsed, list):
            raise ValueError(f"rubric_json parse failed: {task_id}")

        items: list[RubricItem] = []
        for idx, entry in enumerate(parsed):
            if not isinstance(entry, dict):
                continue
            rid = str(entry.get("rubric_item_id") or entry.get("id") or f"{task_id}:{idx}")
            criterion = str(entry.get("criterion") or "")
            score = int(entry.get("score", 0))
            required = entry.get("required")
            if required not in (True, False, None):
                required = None
            items.append(
                RubricItem(
                    rubric_item_id=rid,
                    criterion=criterion,
                    score=score,
                    required=required,
                )
            )
        return items

    @staticmethod
    def _coerce_list(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if v is not None]
        if isinstance(value, tuple):
            return [str(v) for v in value if v is not None]
        if isinstance(value, np.ndarray):
            return [str(v) for v in value.tolist() if v is not None]
        if isinstance(value, str):
            return [value]
        try:
            if pd.isna(value):
                return []
        except Exception:
            pass
        return []
