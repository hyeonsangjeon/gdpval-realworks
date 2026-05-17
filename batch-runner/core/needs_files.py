"""Manifest-based needs_files lookup.

Step 0 (repo_bootstrapper) generates ``step0_needs_files_manifest.json`` from the
original openai/gdpval dataset.  This module provides a thin loader so that
steps 2–8 can ask "does task X require file output?" without touching the
source dataset again.

Manifest schema versions
------------------------
* **v1**: each task entry has ``needs_files``, ``original_file_count``,
  ``original_files``.  ``_summary`` has ``needs_files`` + ``text_only``.
* **v2** (current): adds ``has_deliverable_files`` (dual-signal),
  ``prompt_classification`` (heuristic from ``prompt_classifier``), and
  ``policy_results`` per known policy.  ``_summary`` adds ``active_policy``,
  ``policy_counts``, and ``confidence_distribution``.

The loader is defensive: any v2 keys missing from a v1 manifest fall back to
sensible defaults so old workspaces keep working without regeneration.

Usage:
    from core.needs_files import NeedsFilesManifest, resolve_needs_files

    manifest = NeedsFilesManifest.load()          # default path
    manifest = NeedsFilesManifest.load("/path/to/manifest.json")

    manifest.needs_files("task_042")               # → True / False
    manifest.original_file_count("task_042")       # → 3
    manifest.original_files("task_042")            # → ["file1.xlsx", ...]
    manifest.has_deliverable_files("task_042")     # → True (V2; v1 falls back)
    manifest.prompt_classification("task_042")     # → {...} or None
    manifest.policy_result("task_042", "union")    # → True / False
    manifest.summary                               # → {"needs_files": 185, ...}
"""

import json
import os
import warnings
from pathlib import Path
from typing import Dict, List, Optional

from core.config import NEEDS_FILES_POLICIES_KNOWN, WORKSPACE_DIR


# ── Policy resolver ────────────────────────────────────────────────────────


def resolve_needs_files(
    has_deliverable: bool,
    prompt_classification,
    policy: str,
) -> bool:
    """Resolve the ``needs_files`` flag under a given policy.

    Args:
        has_deliverable: True if the source dataset ``deliverable_files``
            column is non-empty for this task.
        prompt_classification: A
            :class:`core.prompt_classifier.PromptClassification` (or any
            object exposing ``.requires_file`` and ``.explicit_exts``).
        policy: One of :data:`core.config.NEEDS_FILES_POLICIES_KNOWN`.

    Returns:
        True if the task should be treated as requiring file output under
        ``policy``.
    """
    if policy == "deliverable_only":
        return bool(has_deliverable)
    if policy == "explicit_boost":
        return bool(has_deliverable) or bool(
            getattr(prompt_classification, "explicit_exts", None) or []
        )
    if policy == "union":
        return bool(has_deliverable) or bool(
            getattr(prompt_classification, "requires_file", False)
        )
    if policy == "intersection":
        return bool(has_deliverable) and bool(
            getattr(prompt_classification, "requires_file", False)
        )
    raise ValueError(
        f"unknown policy: {policy!r} (known: {NEEDS_FILES_POLICIES_KNOWN})"
    )


# ── Manifest accessor ──────────────────────────────────────────────────────


class NeedsFilesManifest:
    """Read-only accessor for step0_needs_files_manifest.json.

    Policy snapshot semantics
    -------------------------
    The manifest's ``_summary.active_policy`` field is a snapshot taken at
    manifest generation time (Step 0).  Runtime changes to
    ``NEEDS_FILES_POLICY`` do NOT automatically re-evaluate the manifest:
    each task's top-level ``needs_files`` boolean reflects the policy under
    which the manifest was generated.  If you change the policy you must
    regenerate the manifest (re-run Step 0).

    On load, a mismatch between ``_summary.active_policy`` and the runtime
    ``NEEDS_FILES_POLICY`` environment variable emits a ``RuntimeWarning``.
    Setting ``NEEDS_FILES_STRICT=1`` upgrades the warning to a ``ValueError``.
    v1 manifests (no ``active_policy`` field) skip the check entirely so
    legacy workspaces keep working.
    """

    def __init__(self, data: dict):
        self._data = data
        self._tasks: Dict[str, dict] = data.get("tasks", {})
        self._check_policy_snapshot()

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

    # ── Guardrail ─────────────────────────────────────────────────────

    def _check_policy_snapshot(self) -> None:
        """Verify the manifest's active_policy snapshot matches the runtime env.

        v1 manifests (no ``active_policy``) are skipped.  When the snapshot
        and ``NEEDS_FILES_POLICY`` disagree, emit a ``RuntimeWarning`` by
        default or raise ``ValueError`` if ``NEEDS_FILES_STRICT=1``.
        """
        manifest_policy = self.summary.get("active_policy")
        if manifest_policy is None:
            return  # v1 manifest — no snapshot recorded
        runtime_policy = os.environ.get("NEEDS_FILES_POLICY", "deliverable_only")
        if manifest_policy == runtime_policy:
            return
        msg = (
            f"Manifest active_policy={manifest_policy!r} != "
            f"runtime NEEDS_FILES_POLICY={runtime_policy!r}. "
            "Manifest is a snapshot taken at Step 0 generation time; "
            "regenerate the manifest (re-run Step 0) or unset "
            "NEEDS_FILES_POLICY to match the snapshot."
        )
        strict = os.environ.get("NEEDS_FILES_STRICT", "0") == "1"
        if strict:
            raise ValueError(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)

    # ── Queries ───────────────────────────────────────────────────────

    def needs_files(self, task_id: str) -> bool:
        """Does this task require file deliverables (resolved by active policy)?"""
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

    # ── V2 queries (defensive for v1 manifests) ──────────────────────

    def has_deliverable_files(self, task_id: str) -> bool:
        """Did the source dataset record any ``deliverable_files`` for this task?

        Defensive default for v1 manifests: falls back to ``needs_files``
        because v1's ``needs_files`` was computed solely from ``has_deliverable``.
        Returns False for unknown tasks (no signal available).
        """
        entry = self._tasks.get(task_id)
        if entry is None:
            return False
        if "has_deliverable_files" in entry:
            return bool(entry["has_deliverable_files"])
        # v1 fallback: original needs_files == has_deliverable
        return bool(entry.get("needs_files", False))

    def prompt_classification(self, task_id: str) -> Optional[dict]:
        """Return the prompt classification dict for this task.

        Returns ``None`` for unknown tasks or v1 manifests that lack the
        ``prompt_classification`` block.
        """
        entry = self._tasks.get(task_id)
        if entry is None:
            return None
        pc = entry.get("prompt_classification")
        if pc is None:
            return None
        return pc

    def policy_result(self, task_id: str, policy: str) -> bool:
        """Return the resolved ``needs_files`` value under ``policy``.

        For v2 manifests, reads from the precomputed ``policy_results`` block.
        For v1 manifests (no ``policy_results``), only ``deliverable_only`` is
        reconstructible — the recorded ``needs_files`` flag IS the
        ``deliverable_only`` resolution.  Any other policy raises
        ``ValueError`` because v1 lacks the classifier signal needed to
        compute it; callers should regenerate the manifest (re-run Step 0).
        """
        if policy not in NEEDS_FILES_POLICIES_KNOWN:
            raise ValueError(
                f"unknown policy: {policy!r} (known: {NEEDS_FILES_POLICIES_KNOWN})"
            )
        entry = self._tasks.get(task_id)
        if entry is None:
            return True  # match needs_files() conservative default
        pr = entry.get("policy_results")
        if pr is None:
            # v1 fallback: only deliverable_only is reliable.
            if policy == "deliverable_only":
                return bool(entry.get("needs_files", False))
            raise ValueError(
                f"policy_result({policy!r}) unavailable on v1 manifest "
                f"(task_id={task_id!r}); regenerate the manifest "
                "(re-run Step 0) to obtain policy_results."
            )
        return bool(pr.get(policy, False))

    @property
    def summary(self) -> dict:
        """Summary counts.

        v2 manifests include ``active_policy``, ``policy_counts`` and
        ``confidence_distribution`` in addition to the v1 ``needs_files`` /
        ``text_only`` keys.  v1 manifests omit them; callers can use
        ``dict.get`` with defaults.
        """
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
