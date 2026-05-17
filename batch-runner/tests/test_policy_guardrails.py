"""Tests for NEEDS_FILES_V2 policy snapshot guardrails.

Covers TASK_NEEDS_FILES_V2_GUARDRAILS conditions 1, 2 and 3:

* Condition 1 — :class:`core.needs_files.NeedsFilesManifest` warns (or raises
  under ``NEEDS_FILES_STRICT=1``) when the manifest's snapshot
  ``active_policy`` differs from the runtime ``NEEDS_FILES_POLICY``.
* Condition 2 — :meth:`NeedsFilesManifest.policy_result` raises
  ``ValueError`` when a v1 manifest is asked for a non-default policy
  (no precomputed ``policy_results`` block to read).
* Condition 3 — :mod:`step5_validate` emits a stderr ``[WARN]`` line and a
  ``policy_caveat`` key in ``validate_stats.json`` when the manifest's
  ``active_policy`` is not ``deliverable_only``.  Verified by subprocess.

Default-environment regression invariant: with ``NEEDS_FILES_POLICY`` unset
and a ``deliverable_only`` manifest, NO warning is emitted and NO raise
occurs.
"""

import json
import os
import subprocess
import sys
import textwrap
import warnings
from pathlib import Path

import pandas as pd
import pytest

from core.needs_files import NeedsFilesManifest

BATCH_ROOT = Path(__file__).resolve().parent.parent  # batch-runner/

_ALL_POLICIES = ("deliverable_only", "explicit_boost", "union", "intersection")


# ── Manifest fixtures ────────────────────────────────────────────────────


def _make_v2_manifest(active_policy: str = "deliverable_only", tasks=None) -> dict:
    """Build a minimal v2 manifest dict (with ``_summary.active_policy``)."""
    if tasks is None:
        tasks = {
            "task_a": {
                "needs_files": True,
                "original_file_count": 1,
                "original_files": ["x.docx"],
                "has_deliverable_files": True,
                "prompt_classification": {
                    "requires_file": True,
                    "explicit_exts": [".docx"],
                    "inferred_exts": [],
                    "confidence": "explicit",
                },
                "policy_results": {p: True for p in _ALL_POLICIES},
            },
        }
    return {
        "_schema_version": 2,
        "_total_tasks": len(tasks),
        "tasks": tasks,
        "_summary": {
            "needs_files": sum(1 for t in tasks.values() if t["needs_files"]),
            "text_only": sum(1 for t in tasks.values() if not t["needs_files"]),
            "active_policy": active_policy,
            "policy_counts": {p: 0 for p in _ALL_POLICIES},
            "confidence_distribution": {
                "explicit": 1, "inferred": 0, "ambiguous": 0, "text_only": 0,
            },
        },
    }


def _make_v1_manifest(tasks=None) -> dict:
    """Build a minimal v1 manifest dict (no active_policy / policy_results)."""
    if tasks is None:
        tasks = {
            "task_a": {
                "needs_files": True,
                "original_file_count": 1,
                "original_files": ["x.docx"],
            },
            "task_b": {
                "needs_files": False,
                "original_file_count": 0,
                "original_files": [],
            },
        }
    return {
        "_schema_version": 1,
        "_total_tasks": len(tasks),
        "tasks": tasks,
        "_summary": {
            "needs_files": sum(1 for t in tasks.values() if t["needs_files"]),
            "text_only": sum(1 for t in tasks.values() if not t["needs_files"]),
        },
    }


@pytest.fixture(autouse=True)
def _clean_policy_env(monkeypatch):
    """Each test starts with no NEEDS_FILES_* env vars set."""
    monkeypatch.delenv("NEEDS_FILES_POLICY", raising=False)
    monkeypatch.delenv("NEEDS_FILES_STRICT", raising=False)


# ──────────────────────────────────────────────────────────────────────────
# Condition 1 — active_policy snapshot mismatch
# ──────────────────────────────────────────────────────────────────────────


def test_default_env_default_manifest_silent():
    """REGRESSION INVARIANT: default env + deliverable_only manifest =>
    no warning, no raise."""
    data = _make_v2_manifest(active_policy="deliverable_only")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # turn any warning into an exception
        m = NeedsFilesManifest(data)
    assert m.summary.get("active_policy") == "deliverable_only"


def test_v1_manifest_skips_policy_check(monkeypatch):
    """v1 manifests (no active_policy) must NOT raise/warn even under
    strict + non-default runtime policy."""
    monkeypatch.setenv("NEEDS_FILES_POLICY", "union")
    monkeypatch.setenv("NEEDS_FILES_STRICT", "1")
    data = _make_v1_manifest()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        m = NeedsFilesManifest(data)
    assert m.summary.get("active_policy") is None


def test_matching_policy_silent(monkeypatch):
    """v2 manifest whose snapshot equals the runtime policy => silent."""
    monkeypatch.setenv("NEEDS_FILES_POLICY", "union")
    data = _make_v2_manifest(active_policy="union")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        NeedsFilesManifest(data)


def test_mismatch_warns_in_lax_mode(monkeypatch):
    """Default (non-strict) mode emits a RuntimeWarning on mismatch."""
    monkeypatch.setenv("NEEDS_FILES_POLICY", "union")
    data = _make_v2_manifest(active_policy="deliverable_only")
    with pytest.warns(RuntimeWarning, match="active_policy"):
        NeedsFilesManifest(data)


def test_mismatch_raises_in_strict_mode(monkeypatch):
    """NEEDS_FILES_STRICT=1 promotes the mismatch warning to ValueError."""
    monkeypatch.setenv("NEEDS_FILES_POLICY", "union")
    monkeypatch.setenv("NEEDS_FILES_STRICT", "1")
    data = _make_v2_manifest(active_policy="deliverable_only")
    with pytest.raises(ValueError, match="active_policy"):
        NeedsFilesManifest(data)


def test_strict_env_with_match_silent(monkeypatch):
    """Strict mode must still be silent when snapshot == runtime."""
    monkeypatch.setenv("NEEDS_FILES_POLICY", "intersection")
    monkeypatch.setenv("NEEDS_FILES_STRICT", "1")
    data = _make_v2_manifest(active_policy="intersection")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        NeedsFilesManifest(data)


# ──────────────────────────────────────────────────────────────────────────
# Condition 2 — v1 manifest policy_result for non-default policy
# ──────────────────────────────────────────────────────────────────────────


def test_v1_policy_result_deliverable_only_returns_recorded():
    """v1's recorded needs_files IS the deliverable_only resolution."""
    m = NeedsFilesManifest(_make_v1_manifest())
    assert m.policy_result("task_a", "deliverable_only") is True
    assert m.policy_result("task_b", "deliverable_only") is False


@pytest.mark.parametrize("policy", ["explicit_boost", "union", "intersection"])
def test_v1_policy_result_non_default_raises(policy):
    """v1 manifest has no policy_results block → non-default policies raise."""
    m = NeedsFilesManifest(_make_v1_manifest())
    with pytest.raises(ValueError, match="v1"):
        m.policy_result("task_a", policy)


@pytest.mark.parametrize("policy", _ALL_POLICIES)
def test_v2_policy_result_returns_precomputed(policy):
    """v2 manifests with a policy_results block are looked up directly."""
    m = NeedsFilesManifest(_make_v2_manifest())
    assert m.policy_result("task_a", policy) is True


def test_policy_result_unknown_task_returns_conservative_default():
    """Unknown task_id → conservative True (preserves prior behaviour)."""
    m = NeedsFilesManifest(_make_v2_manifest())
    assert m.policy_result("does_not_exist", "deliverable_only") is True


def test_policy_result_unknown_policy_raises():
    m = NeedsFilesManifest(_make_v2_manifest())
    with pytest.raises(ValueError, match="unknown policy"):
        m.policy_result("task_a", "majority_vote")


# ──────────────────────────────────────────────────────────────────────────
# Condition 3 — step5_validate WARNING + JSON policy_caveat (subprocess)
# ──────────────────────────────────────────────────────────────────────────


def _write_parquet(path: Path, task_ids):
    """Write a minimal parquet with the columns step5_validate inspects."""
    rows = []
    for tid in task_ids:
        rows.append({
            "task_id": tid,
            "sector": "Information",
            "occupation": "test",
            "prompt": "test prompt",
            "deliverable_text": "x",
            "deliverable_files": [],
            "deliverable_file_urls": [],
            "deliverable_file_hf_uris": [],
            "reference_files": [],
            "reference_file_urls": [],
            "reference_file_hf_uris": [],
        })
    pd.DataFrame(rows).to_parquet(path, index=False)


def _setup_step5_fixtures(tmp_path: Path, active_policy: str) -> Path:
    """Lay out a workspace/upload tree with a manifest+parquet for step5."""
    ws = tmp_path / "ws"
    upload = ws / "upload"
    (upload / "data").mkdir(parents=True, exist_ok=True)
    (upload / "deliverable_files").mkdir(parents=True, exist_ok=True)

    task_ids = ["task_a", "task_b"]
    tasks = {
        tid: {
            "needs_files": False,
            "original_file_count": 0,
            "original_files": [],
            "has_deliverable_files": False,
            "prompt_classification": {
                "requires_file": False,
                "explicit_exts": [],
                "inferred_exts": [],
                "confidence": "text_only",
            },
            "policy_results": {p: False for p in _ALL_POLICIES},
        }
        for tid in task_ids
    }
    manifest = _make_v2_manifest(active_policy=active_policy, tasks=tasks)
    (ws / "step0_needs_files_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False)
    )
    _write_parquet(upload / "data" / "train-000.parquet", task_ids)
    return ws


def _build_step5_wrapper(tmp_path: Path) -> Path:
    """Wrapper script that patches WORKSPACE_DIR/UPLOAD_DIR before validate()."""
    wrapper = tmp_path / "run_step5.py"
    wrapper.write_text(textwrap.dedent(f"""
        import sys
        from pathlib import Path
        sys.path.insert(0, {str(BATCH_ROOT)!r})

        import core.config as cfg
        ws = Path({str(tmp_path)!r}) / "ws"
        upload = ws / "upload"
        deliverable = upload / "deliverable_files"
        (upload / "data").mkdir(parents=True, exist_ok=True)
        deliverable.mkdir(parents=True, exist_ok=True)
        cfg.WORKSPACE_DIR = ws
        cfg.UPLOAD_DIR = upload
        cfg.DELIVERABLE_DIR = deliverable
        cfg.DEFAULT_LOCAL_PATH = ws / "local"

        # step5_validate binds these names at import time, so patch the
        # module-level constants too.
        import step5_validate as s5
        s5.WORKSPACE_DIR = ws
        s5.UPLOAD_DIR = upload
        s5.DELIVERABLE_DIR = deliverable
        s5.DEFAULT_LOCAL_PATH = ws / "local"

        s5.validate()  # we ignore validate's return code in these tests
    """))
    return wrapper


def _run_step5(tmp_path: Path, env_overrides: dict) -> subprocess.CompletedProcess:
    wrapper = _build_step5_wrapper(tmp_path)
    env = os.environ.copy()
    env.pop("NEEDS_FILES_POLICY", None)
    env.pop("NEEDS_FILES_STRICT", None)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(wrapper)],
        capture_output=True, text=True, env=env, cwd=str(BATCH_ROOT),
    )


def test_step5_non_default_policy_emits_warning_and_caveat(tmp_path):
    """active_policy='union' => stderr [WARN] line + policy_caveat=='union'."""
    ws = _setup_step5_fixtures(tmp_path, active_policy="union")
    # Match runtime policy to manifest snapshot so Condition 1 stays silent
    # — we want to test Condition 3 in isolation.
    result = _run_step5(tmp_path, env_overrides={"NEEDS_FILES_POLICY": "union"})

    assert result.returncode == 0, (
        f"wrapper failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "[WARN] step5_validate" in result.stderr, result.stderr
    assert "active_policy='union'" in result.stderr, result.stderr

    stats_path = ws / "validate_stats.json"
    assert stats_path.exists(), "validate_stats.json was not written"
    stats = json.loads(stats_path.read_text())
    assert stats.get("policy_caveat") == "union", stats


def test_step5_default_policy_no_warning_no_caveat(tmp_path):
    """REGRESSION INVARIANT: default policy manifest => no WARN, caveat is None."""
    ws = _setup_step5_fixtures(tmp_path, active_policy="deliverable_only")
    result = _run_step5(tmp_path, env_overrides={})

    assert result.returncode == 0, (
        f"wrapper failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "[WARN] step5_validate" not in result.stderr, result.stderr

    stats_path = ws / "validate_stats.json"
    assert stats_path.exists(), "validate_stats.json was not written"
    stats = json.loads(stats_path.read_text())
    assert stats.get("policy_caveat") is None, stats
