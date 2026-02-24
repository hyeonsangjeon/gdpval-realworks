"""Manifest-based needs_files lookup.

Step 0 (repo_bootstrapper) generates ``step0_needs_files_manifest.json`` from the
original openai/gdpval dataset.  This module provides a thin loader so that
steps 2–8 can ask "does task X require file output?" without touching the
source dataset again.

Usage:
    from core.needs_files import NeedsFilesManifest

    manifest = NeedsFilesManifest.load()          # default path
    manifest = NeedsFilesManifest.load("/path/to/manifest.json")

    manifest.needs_files("task_042")               # → True / False
    manifest.original_file_count("task_042")       # → 3
    manifest.original_files("task_042")            # → ["file1.xlsx", ...]
    manifest.summary                               # → {"needs_files": 185, "text_only": 35}
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from core.config import WORKSPACE_DIR


class NeedsFilesManifest:
    """Read-only accessor for step0_needs_files_manifest.json."""

    def __init__(self, data: dict):
        self._data = data
        self._tasks: Dict[str, dict] = data.get("tasks", {})

    # ── Constructors ──────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Optional[str] = None) -> "NeedsFilesManifest":
        """Load manifest from disk.

        Args:
            path: Explicit path to the JSON file.  Defaults to
                  ``<WORKSPACE_DIR>/step0_needs_files_manifest.json``.

        Raises:
            FileNotFoundError: If the manifest does not exist (Step 0 not run).
        """
        if path is None:
            path = str(WORKSPACE_DIR / "step0_needs_files_manifest.json")
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"Manifest not found: {p}\n"
                "Run Step 0 (bootstrap) first to generate it."
            )
        with open(p, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    # ── Queries ───────────────────────────────────────────────────────

    def needs_files(self, task_id: str) -> bool:
        """Does this task require file deliverables?"""
        entry = self._tasks.get(task_id)
        if entry is None:
            # Unknown task → conservative default: assume yes
            return True
        return entry.get("needs_files", False)

    def original_file_count(self, task_id: str) -> int:
        """How many files did the original dataset expect for this task?"""
        entry = self._tasks.get(task_id)
        if entry is None:
            return 0
        return entry.get("original_file_count", 0)

    def original_files(self, task_id: str) -> List[str]:
        """List of original deliverable file paths for this task."""
        entry = self._tasks.get(task_id)
        if entry is None:
            return []
        return entry.get("original_files", [])

    @property
    def summary(self) -> dict:
        """Summary counts: {"needs_files": N, "text_only": M}."""
        return self._data.get("_summary", {})

    @property
    def total_tasks(self) -> int:
        return self._data.get("_total_tasks", len(self._tasks))

    def __len__(self) -> int:
        return len(self._tasks)

    def __contains__(self, task_id: str) -> bool:
        return task_id in self._tasks

    def __repr__(self) -> str:
        s = self.summary
        return (
            f"NeedsFilesManifest("
            f"tasks={len(self._tasks)}, "
            f"needs_files={s.get('needs_files', '?')}, "
            f"text_only={s.get('text_only', '?')})"
        )
