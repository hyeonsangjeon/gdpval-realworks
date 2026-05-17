"""Tests for STEP6_V2_FIELDS — v2 manifest fields surface in self_report.json.

Covers:

* When the workspace manifest is **v2** (has ``_summary.active_policy``),
  ``step6_report._build_task_results`` adds ``prompt_classification``,
  ``policy_results`` (all 4 policies) and ``has_deliverable_files`` to every
  task entry, and ``_v2_summary_fields`` exposes ``active_policy``,
  ``policy_counts`` and ``confidence_distribution`` for injection into the
  ``file_generation`` block.
* When the manifest is **v1** (no ``active_policy``) — or absent —
  none of the new keys appear in any task entry, the v2 summary dict is
  empty, and existing v1 fields keep their values unchanged.
* The end-to-end ``generate_report`` flow writes ``report_data.json`` with
  the v2 fields present (v2 case) / absent (v1 case), and the summary,
  sector_breakdown and existing task_results counts/keys are unchanged
  across both branches.
"""

import json
import sys
import warnings
from pathlib import Path

import pytest

# Add parent directory to path for ``step6_report`` and ``core`` imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import step6_report
from core.needs_files import NeedsFilesManifest

_ALL_POLICIES = ("deliverable_only", "explicit_boost", "union", "intersection")


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_policy_env(monkeypatch):
    """Each test starts with no NEEDS_FILES_* env vars set so the manifest's
    snapshot policy never disagrees with the runtime default."""
    monkeypatch.delenv("NEEDS_FILES_POLICY", raising=False)
    monkeypatch.delenv("NEEDS_FILES_STRICT", raising=False)


def _make_v2_manifest_data() -> dict:
    """Two-task v2 manifest covering the on/off axis for each v2 field."""
    return {
        "_schema_version": 2,
        "_total_tasks": 2,
        "tasks": {
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
                "policy_results": {
                    "deliverable_only": True,
                    "explicit_boost": True,
                    "union": True,
                    "intersection": True,
                },
            },
            "task_b": {
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
                "policy_results": {
                    "deliverable_only": False,
                    "explicit_boost": False,
                    "union": False,
                    "intersection": False,
                },
            },
        },
        "_summary": {
            "needs_files": 1,
            "text_only": 1,
            "active_policy": "deliverable_only",
            "policy_counts": {
                "deliverable_only": 1,
                "explicit_boost": 1,
                "union": 1,
                "intersection": 1,
            },
            "confidence_distribution": {
                "explicit": 1,
                "inferred": 0,
                "ambiguous": 0,
                "text_only": 1,
            },
        },
    }


def _make_v1_manifest_data() -> dict:
    """Two-task v1 manifest (no ``active_policy`` / ``policy_results``)."""
    return {
        "_schema_version": 1,
        "_total_tasks": 2,
        "tasks": {
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
        },
        "_summary": {
            "needs_files": 1,
            "text_only": 1,
        },
    }


def _make_result_payload() -> dict:
    """Minimal step3 ``result.json`` shape with two tasks matching the fixtures."""
    return {
        "experiment_id": "exp_test",
        "experiment_name": "v2-fields-test",
        "condition_name": "default",
        "model": "test-model",
        "execution_mode": "test",
        "started_at": "2026-05-17T00:00:00Z",
        "duration": "0s",
        "results": [
            {
                "task_id": "task_a",
                "sector": "Tech",
                "occupation": "Engineer",
                "status": "success",
                "retried": False,
                "deliverable_files": ["out.docx"],
                "deliverable_files_count": 1,
                "qa_score": 8,
                "qa_passed": True,
                "qa_issues": [],
                "qa_suggestion": "",
                "latency_ms": 1234,
                "deliverable_text": "ok",
                "instruction": "do the thing",
                "reference_file_urls": [],
            },
            {
                "task_id": "task_b",
                "sector": "Tech",
                "occupation": "Analyst",
                "status": "success",
                "retried": False,
                "deliverable_files": [],
                "deliverable_files_count": 0,
                "qa_score": 9,
                "qa_passed": True,
                "qa_issues": [],
                "qa_suggestion": "",
                "latency_ms": 567,
                "deliverable_text": "ok",
                "instruction": "answer the question",
                "reference_file_urls": [],
            },
        ],
    }


# ──────────────────────────────────────────────────────────────────────────
# _manifest_v2_available / _v2_summary_fields
# ──────────────────────────────────────────────────────────────────────────


def test_manifest_v2_available_true_for_v2():
    manifest = NeedsFilesManifest(_make_v2_manifest_data())
    assert step6_report._manifest_v2_available(manifest) is True


def test_manifest_v2_available_false_for_v1():
    manifest = NeedsFilesManifest(_make_v1_manifest_data())
    assert step6_report._manifest_v2_available(manifest) is False


def test_manifest_v2_available_false_for_none():
    assert step6_report._manifest_v2_available(None) is False


def test_v2_summary_fields_v2_returns_all_three_keys():
    manifest = NeedsFilesManifest(_make_v2_manifest_data())
    fields = step6_report._v2_summary_fields(manifest)
    assert set(fields.keys()) == {
        "active_policy",
        "policy_counts",
        "confidence_distribution",
    }
    assert fields["active_policy"] == "deliverable_only"
    assert fields["policy_counts"] == {
        "deliverable_only": 1,
        "explicit_boost": 1,
        "union": 1,
        "intersection": 1,
    }
    assert fields["confidence_distribution"] == {
        "explicit": 1,
        "inferred": 0,
        "ambiguous": 0,
        "text_only": 1,
    }


def test_v2_summary_fields_v1_returns_empty():
    manifest = NeedsFilesManifest(_make_v1_manifest_data())
    assert step6_report._v2_summary_fields(manifest) == {}


def test_v2_summary_fields_none_manifest_returns_empty():
    assert step6_report._v2_summary_fields(None) == {}


# ──────────────────────────────────────────────────────────────────────────
# _build_task_results with v2 manifest
# ──────────────────────────────────────────────────────────────────────────


def test_build_task_results_v2_adds_per_task_fields():
    manifest = NeedsFilesManifest(_make_v2_manifest_data())
    data = _make_result_payload()
    task_results, error_tasks = step6_report._build_task_results(
        data, manifest=manifest
    )

    assert len(task_results) == 2
    assert error_tasks == []

    by_id = {t["task_id"]: t for t in task_results}

    # task_a: has deliverable, explicit confidence, all 4 policies True
    a = by_id["task_a"]
    assert a["has_deliverable_files"] is True
    assert a["prompt_classification"] == {
        "requires_file": True,
        "explicit_exts": [".docx"],
        "inferred_exts": [],
        "confidence": "explicit",
    }
    assert a["policy_results"] == {
        "deliverable_only": True,
        "explicit_boost": True,
        "union": True,
        "intersection": True,
    }
    assert set(a["policy_results"].keys()) == set(_ALL_POLICIES)

    # task_b: no deliverable, text_only, all 4 policies False
    b = by_id["task_b"]
    assert b["has_deliverable_files"] is False
    assert b["prompt_classification"] == {
        "requires_file": False,
        "explicit_exts": [],
        "inferred_exts": [],
        "confidence": "text_only",
    }
    assert b["policy_results"] == {
        "deliverable_only": False,
        "explicit_boost": False,
        "union": False,
        "intersection": False,
    }


def test_build_task_results_v2_preserves_existing_fields():
    """The append-only invariant: v2 must not change any v1 field value."""
    data = _make_result_payload()
    manifest = NeedsFilesManifest(_make_v2_manifest_data())

    v1_results, _ = step6_report._build_task_results(data, manifest=None)
    v2_results, _ = step6_report._build_task_results(data, manifest=manifest)

    assert len(v1_results) == len(v2_results)
    v1_keys = {"prompt_classification", "policy_results", "has_deliverable_files"}
    for v1, v2 in zip(v1_results, v2_results):
        # Every v1 key/value MUST be preserved verbatim.
        for k, expected in v1.items():
            assert v2[k] == expected, f"v2 changed v1 key {k!r}"
        # The only difference between branches: appended v2 keys.
        added = set(v2.keys()) - set(v1.keys())
        assert added == v1_keys


# ──────────────────────────────────────────────────────────────────────────
# _build_task_results with v1 manifest (and with no manifest) — backward-compat
# ──────────────────────────────────────────────────────────────────────────


def test_build_task_results_v1_omits_v2_fields():
    manifest = NeedsFilesManifest(_make_v1_manifest_data())
    data = _make_result_payload()
    task_results, _ = step6_report._build_task_results(data, manifest=manifest)

    for entry in task_results:
        assert "prompt_classification" not in entry
        assert "policy_results" not in entry
        assert "has_deliverable_files" not in entry


def test_build_task_results_no_manifest_omits_v2_fields():
    data = _make_result_payload()
    task_results, _ = step6_report._build_task_results(data, manifest=None)

    for entry in task_results:
        assert "prompt_classification" not in entry
        assert "policy_results" not in entry
        assert "has_deliverable_files" not in entry


# ──────────────────────────────────────────────────────────────────────────
# generate_report end-to-end: v2 fields land in report_data.json
# ──────────────────────────────────────────────────────────────────────────


def _write_workspace(tmp_path: Path, manifest_data: dict | None) -> tuple[Path, Path]:
    """Lay out a minimal workspace and return (result_json, output_dir)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    result_payload = _make_result_payload()
    result_json = tmp_path / "result.json"
    result_json.write_text(json.dumps(result_payload), encoding="utf-8")

    output_dir = tmp_path / "report"
    output_dir.mkdir()

    if manifest_data is not None:
        (tmp_path / "step0_needs_files_manifest.json").write_text(
            json.dumps(manifest_data), encoding="utf-8"
        )
    return result_json, output_dir


def _run_step6(monkeypatch, tmp_path: Path, manifest_data: dict | None) -> dict:
    """Run ``generate_report`` against an isolated workspace and return the
    parsed ``report_data.json`` dict."""
    monkeypatch.setattr(step6_report, "WORKSPACE_DIR", tmp_path)
    # The manifest loader (core.needs_files) and core.config both keep their
    # own bindings of WORKSPACE_DIR; patch all three to fully isolate.
    import core.config as core_config
    import core.needs_files as core_needs_files
    monkeypatch.setattr(core_config, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(core_needs_files, "WORKSPACE_DIR", tmp_path)

    result_json, output_dir = _write_workspace(tmp_path, manifest_data)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        step6_report.generate_report(
            result_json_path=result_json,
            output_dir=output_dir,
            no_narrative=True,
        )

    return json.loads((output_dir / "report_data.json").read_text(encoding="utf-8"))


def test_generate_report_v2_manifest_includes_v2_fields(monkeypatch, tmp_path):
    rd = _run_step6(monkeypatch, tmp_path, _make_v2_manifest_data())

    # Per-task v2 fields present on every entry.
    assert len(rd["task_results"]) == 2
    for entry in rd["task_results"]:
        assert "prompt_classification" in entry
        assert "policy_results" in entry
        assert "has_deliverable_files" in entry
        assert set(entry["policy_results"].keys()) == set(_ALL_POLICIES)

    # File-generation block surfaces the v2 summary fields.
    fg = rd["file_generation"]
    assert fg["active_policy"] == "deliverable_only"
    assert fg["policy_counts"] == {
        "deliverable_only": 1,
        "explicit_boost": 1,
        "union": 1,
        "intersection": 1,
    }
    assert fg["confidence_distribution"] == {
        "explicit": 1,
        "inferred": 0,
        "ambiguous": 0,
        "text_only": 1,
    }

    # Existing summary stats are unchanged by v2 augmentation.
    s = rd["summary"]
    assert s["total_tasks"] == 2
    assert s["success_count"] == 2
    assert s["success_rate_pct"] == 100.0
    assert s["error_count"] == 0


def test_generate_report_v1_manifest_omits_v2_fields(monkeypatch, tmp_path):
    rd = _run_step6(monkeypatch, tmp_path, _make_v1_manifest_data())

    # No v2 keys appear anywhere in task entries.
    for entry in rd["task_results"]:
        assert "prompt_classification" not in entry
        assert "policy_results" not in entry
        assert "has_deliverable_files" not in entry

    # file_generation must NOT pick up v2 summary fields for a v1 manifest.
    fg = rd["file_generation"]
    assert "active_policy" not in fg
    assert "policy_counts" not in fg
    assert "confidence_distribution" not in fg

    # Existing summary stats are still correct.
    s = rd["summary"]
    assert s["total_tasks"] == 2
    assert s["success_count"] == 2


def test_generate_report_no_manifest_omits_v2_fields(monkeypatch, tmp_path):
    """Missing manifest (Step 0 never run) must not crash and must not emit
    any v2 keys — full backward-compat with pre-v2 workspaces."""
    rd = _run_step6(monkeypatch, tmp_path, manifest_data=None)

    for entry in rd["task_results"]:
        assert "prompt_classification" not in entry
        assert "policy_results" not in entry
        assert "has_deliverable_files" not in entry

    fg = rd["file_generation"]
    assert "active_policy" not in fg
    assert "policy_counts" not in fg
    assert "confidence_distribution" not in fg


def test_generate_report_v2_vs_v1_preserves_v1_task_keys(monkeypatch, tmp_path):
    """REGRESSION INVARIANT: switching v1↔v2 must not change any v1 key value
    in the report.  Only new (v2) keys appear/disappear."""
    rd_v1 = _run_step6(monkeypatch, tmp_path / "v1", _make_v1_manifest_data())
    rd_v2 = _run_step6(monkeypatch, tmp_path / "v2", _make_v2_manifest_data())

    # Summary unchanged.
    assert rd_v1["summary"] == rd_v2["summary"]
    # Sector breakdown unchanged.
    assert rd_v1["sector_breakdown"] == rd_v2["sector_breakdown"]
    # Per-task v1 keys unchanged (compare by task_id).
    by_id_v1 = {t["task_id"]: t for t in rd_v1["task_results"]}
    by_id_v2 = {t["task_id"]: t for t in rd_v2["task_results"]}
    assert set(by_id_v1) == set(by_id_v2)
    v2_only = {"prompt_classification", "policy_results", "has_deliverable_files"}
    for tid, v1_entry in by_id_v1.items():
        v2_entry = by_id_v2[tid]
        for k, expected in v1_entry.items():
            assert v2_entry[k] == expected, (
                f"v2 manifest changed v1 task_results key {k!r} for {tid!r}"
            )
        added = set(v2_entry.keys()) - set(v1_entry.keys())
        assert added == v2_only
