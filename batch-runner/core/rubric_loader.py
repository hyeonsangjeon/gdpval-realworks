"""Rubric loader for openai/gdpval dataset.

Loads task-level rubric_json from HuggingFace parquet files with local cache.
"""

from __future__ import annotations

import json
import logging
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
        if self._sha:
            return self._sha
        try:
            info = HfApi().dataset_info(self.repo_id, revision=self.revision)
            self._sha = info.sha
        except Exception as exc:
            if self._has_local_parquet():
                logger.warning("Failed to resolve rubric SHA from HF, fallback to revision: %s", exc)
                self._sha = self.revision
            else:
                raise RuntimeError(f"Failed to fetch rubric SHA: {exc}") from exc
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
                    revision=self.revision,
                    cache_dir=str(self.cache_dir),
                )
                result[hf_path] = str(Path(local).resolve())
            except Exception as exc:
                logger.warning("Failed to download %s: %s", hf_path, exc)
        return result

    def _ensure_loaded(self) -> None:
        if self._tasks is not None:
            return

        if not self._has_local_parquet():
            try:
                snapshot_download(
                    repo_id=self.repo_id,
                    repo_type="dataset",
                    revision=self.revision,
                    cache_dir=str(self.cache_dir),
                    local_dir=str(self.cache_dir),
                    allow_patterns=["data/*.parquet"],
                )
            except Exception as exc:
                if not self._has_local_parquet():
                    raise RuntimeError(f"Failed to download rubric parquet: {exc}") from exc
                logger.warning("Download failed; using local cache: %s", exc)

        self._tasks = self._load_tasks_from_parquet()

    def _has_local_parquet(self) -> bool:
        return any(self.cache_dir.rglob("data/*.parquet"))

    def _load_tasks_from_parquet(self) -> dict[str, TaskRubric]:
        parquet_files = sorted(self.cache_dir.rglob("data/*.parquet"))
        if not parquet_files:
            raise RuntimeError(f"No parquet files found under cache_dir: {self.cache_dir}")

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
