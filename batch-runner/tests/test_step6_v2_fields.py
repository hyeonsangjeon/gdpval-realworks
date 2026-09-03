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
from unittest.mock import MagicMock

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
        "source_repo_id": "student/v2-fields-test",
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


def test_public_error_tasks_exclude_raw_provider_details():
    payload = _make_result_payload()
    payload["results"][0]["error"] = (
        "BadRequestError: https://secret.services.ai.azure.com/api/projects/private"
    )

    _task_results, error_tasks = step6_report._build_task_results(payload)

    assert error_tasks == [{
        "task_id": "task_a",
        "sector": "Tech",
        "occupation": "Engineer",
        "error_code": "task_execution_error",
        "error_type": "BadRequestError",
    }]
    assert "secret.services.ai.azure.com" not in str(error_tasks)


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


def _write_workspace(
    tmp_path: Path,
    manifest_data: dict | None,
    result_payload: dict | None = None,
) -> tuple[Path, Path]:
    """Lay out a minimal workspace and return (result_json, output_dir)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    result_payload = result_payload or _make_result_payload()
    result_json = tmp_path / "result.json"
    result_json.write_text(json.dumps(result_payload), encoding="utf-8")

    output_dir = tmp_path / "report"
    output_dir.mkdir()

    if manifest_data is not None:
        (tmp_path / "step0_needs_files_manifest.json").write_text(
            json.dumps(manifest_data), encoding="utf-8"
        )
    return result_json, output_dir


def _run_step6(
    monkeypatch,
    tmp_path: Path,
    manifest_data: dict | None,
    result_payload: dict | None = None,
    dry_run: bool = False,
) -> dict:
    """Run ``generate_report`` against an isolated workspace and return the
    parsed ``report_data.json`` dict."""
    monkeypatch.setattr(step6_report, "WORKSPACE_DIR", tmp_path)
    # The manifest loader (core.needs_files) and core.config both keep their
    # own bindings of WORKSPACE_DIR; patch all three to fully isolate.
    import core.config as core_config
    import core.needs_files as core_needs_files
    monkeypatch.setattr(core_config, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(core_needs_files, "WORKSPACE_DIR", tmp_path)

    result_json, output_dir = _write_workspace(
        tmp_path,
        manifest_data,
        result_payload=result_payload,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        step6_report.generate_report(
            result_json_path=result_json,
            output_dir=output_dir,
            no_narrative=True,
            dry_run=dry_run,
        )

    return json.loads((output_dir / "report_data.json").read_text(encoding="utf-8"))


def test_primary_narrative_failure_uses_sanitized_model_free_fallback(
    monkeypatch, tmp_path
):
    import core.azure_ai_clients as azure_ai_clients
    import core.llm_client as llm_client
    import core.narrative_analyzer as narrative_analyzer

    secret = "private endpoint and credential detail"
    monkeypatch.setattr(
        narrative_analyzer,
        "expected_narrative_publication_identity",
        lambda: ("gpt-5.6-sol", "max", "f" * 64),
    )
    monkeypatch.setattr(
        narrative_analyzer,
        "create_narrative_analyzer",
        lambda: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    monkeypatch.setattr(
        llm_client,
        "create_client",
        lambda **_kwargs: pytest.fail("secondary narrative client was created"),
    )
    monkeypatch.setattr(step6_report, "WORKSPACE_DIR", tmp_path)
    result_json, output_dir = _write_workspace(tmp_path, None)

    step6_report.generate_report(result_json, output_dir, no_narrative=False)

    report = json.loads(
        (output_dir / "report_data.json").read_text(encoding="utf-8")
    )
    assert report["narrative_error"] == "RuntimeError"
    assert all(not value for value in report["narrative"].values() if value)
    assert secret not in json.dumps(report)


def test_narrative_route_drift_falls_back_before_api_call(
    monkeypatch, tmp_path
):
    import core.azure_ai_clients as azure_ai_clients
    import core.narrative_analyzer as narrative_analyzer

    analyzer = MagicMock(
        model="gpt-5.6-sol",
        reasoning_effort="max",
        runtime_fingerprint="a" * 64,
    )
    analyzer.__enter__.return_value = analyzer
    analyzer.__exit__.return_value = None
    monkeypatch.setattr(
        narrative_analyzer,
        "create_narrative_analyzer",
        lambda: analyzer,
    )
    captured = {}

    def preflight(workloads, **kwargs):
        captured.update(kwargs)
        return [{"runtime_fingerprint": "e" * 64}]

    monkeypatch.setattr(azure_ai_clients, "preflight_routes", preflight)
    monkeypatch.setattr(step6_report, "WORKSPACE_DIR", tmp_path)
    result_json, output_dir = _write_workspace(tmp_path, None)

    step6_report.generate_report(result_json, output_dir, no_narrative=False)

    analyzer.analyze.assert_not_called()
    assert captured == {
        "timeout": narrative_analyzer.NarrativeAnalyzer.DEFAULT_TIMEOUT,
        "legacy_api_version": (
            narrative_analyzer.NarrativeAnalyzer.DEFAULT_API_VERSION
        ),
    }
    report = json.loads(
        (output_dir / "report_data.json").read_text(encoding="utf-8")
    )
    assert report["narrative_error"] == "ValueError"


def test_dry_run_report_marks_hf_target_as_unpublished(monkeypatch, tmp_path):
    rd = _run_step6(
        monkeypatch,
        tmp_path,
        _make_v1_manifest_data(),
        dry_run=True,
    )
    markdown = step6_report._build_markdown(rd)

    assert rd["meta"]["source_repo_id"] == "student/v2-fields-test"
    assert rd["meta"]["publication_plan"] == "dry_run_no_step7"
    assert "HF Target (bootstrap)" in markdown
    assert "student/v2-fields-test" in markdown
    assert "Self-Report" in markdown
    assert "not published" in markdown
    assert "/blob/main/self_report.json" not in markdown


def test_markdown_reports_failed_files_without_claiming_dummy_creation():
    report = step6_report._build_report_data(
        _make_result_payload(),
        {"grading_referenced": False},
        {
            "total_tasks": 2,
            "success_count": 1,
            "success_rate_pct": 50.0,
            "error_count": 1,
            "retried_count": 0,
            "avg_qa_score": 0,
            "min_qa_score": 0,
            "max_qa_score": 0,
            "avg_latency_ms": 0,
            "max_latency_ms": 0,
            "total_latency_ms": 0,
        },
        [],
        [],
        [],
    )
    report["file_generation"] = {
        "needs_files_total": 2,
        "files_succeeded": 1,
        "files_failed": 1,
        "dummy_files_created": 0,
        "dummy_task_ids": [],
    }

    markdown = step6_report._build_markdown(report)

    assert "Failed (empty outputs preserved)" in markdown
    assert "dummy created" not in markdown


def _markdown_for_file_generation(file_generation: dict) -> str:
    """Render the report markdown for one ``file_generation`` block."""
    report = step6_report._build_report_data(
        _make_result_payload(),
        {"grading_referenced": False},
        {
            "total_tasks": 2,
            "success_count": 1,
            "success_rate_pct": 50.0,
            "error_count": 1,
            "retried_count": 0,
            "avg_qa_score": 0,
            "min_qa_score": 0,
            "max_qa_score": 0,
            "avg_latency_ms": 0,
            "max_latency_ms": 0,
            "total_latency_ms": 0,
        },
        [],
        [],
        [],
    )
    report["file_generation"] = file_generation
    return step6_report._build_markdown(report)


def _file_generation_section(markdown: str) -> str:
    """The ``## File Generation`` block alone — the rest carries a timestamp."""
    lines = markdown.splitlines()
    start = lines.index("## File Generation")
    end = next(
        (
            index
            for index, line in enumerate(lines[start + 1:], start + 1)
            if line.startswith("## ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_markdown_names_the_tasks_that_were_never_checked():
    """A task with no row in the submission is in the denominator of the rate
    printed above it, so the report has to say it was never looked at."""
    markdown = _markdown_for_file_generation({
        "needs_files_total": 2,
        "files_succeeded": 1,
        "files_failed": 0,
        "files_absent": 1,
        "dummy_files_created": 0,
        "dummy_task_ids": [],
    })

    assert "| Successfully generated | 1 (50.0%) |" in markdown
    assert "| Absent from submission (never checked) | 1 |" in markdown
    assert "> 1 of these 2 tasks have no row in the submission at all" in markdown
    assert "The 50.0% above is out of a denominator that includes them." in markdown


def test_markdown_is_unchanged_when_no_task_was_absent():
    """Nothing absent, and a report written before step5 counted them, render
    exactly as they did before — no empty row, no note about a zero."""
    counted = _markdown_for_file_generation({
        "needs_files_total": 2,
        "files_succeeded": 1,
        "files_failed": 1,
        "files_absent": 0,
        "dummy_files_created": 0,
        "dummy_task_ids": [],
    })
    legacy = _markdown_for_file_generation({
        "needs_files_total": 2,
        "files_succeeded": 1,
        "files_failed": 1,
        "dummy_files_created": 0,
        "dummy_task_ids": [],
    })

    section = _file_generation_section(counted)
    assert section == _file_generation_section(legacy)
    assert "never checked" not in section
    assert "no row in the submission" not in section
    assert "| Failed (empty outputs preserved) | 1 |" in section


def test_report_preserves_current_pipeline_publication_identity(
    monkeypatch, tmp_path
):
    payload = _make_result_payload()
    payload["publication_generation"] = "exp_test:100:1"
    payload["prepared_fingerprint"] = "f" * 64
    payload["result_fingerprint"] = "e" * 64
    payload["ordered_task_ids"] = ["task_a", "task_b"]

    rd = _run_step6(
        monkeypatch,
        tmp_path,
        _make_v1_manifest_data(),
        result_payload=payload,
    )

    assert rd["meta"]["publication_generation"] == "exp_test:100:1"
    assert rd["meta"]["prepared_fingerprint"] == "f" * 64
    assert rd["meta"]["result_fingerprint"] == "e" * 64
    assert rd["meta"]["ordered_task_ids"] == ["task_a", "task_b"]
    assert rd["meta"]["publication_plan"] == "step7_upload_requested"


def test_report_rejects_result_task_order_outside_pipeline_identity(
    monkeypatch, tmp_path
):
    payload = _make_result_payload()
    payload["publication_generation"] = "exp_test:100:1"
    payload["prepared_fingerprint"] = "f" * 64
    payload["result_fingerprint"] = "e" * 64
    payload["ordered_task_ids"] = ["task_b", "task_a"]

    with pytest.raises(ValueError, match="task set differs"):
        _run_step6(
            monkeypatch,
            tmp_path,
            _make_v1_manifest_data(),
            result_payload=payload,
        )


def test_default_output_dir_uses_selected_result_json_not_stale_workspace(
    monkeypatch, tmp_path
):
    selected = tmp_path / "selected.json"
    selected.write_text(
        json.dumps({"experiment_id": "selected_exp"}),
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "step2_inference_results.json").write_text(
        json.dumps({"experiment_id": "../stale"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(step6_report, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step6_report, "_SCRIPT_DIR", tmp_path)

    output = step6_report._resolve_output_dir(None, selected)

    assert output == tmp_path / "results" / "selected_exp" / "report"


@pytest.mark.parametrize("experiment_id", ["../outside", "nested/path", ""])
def test_default_output_dir_rejects_unsafe_selected_result_id(
    monkeypatch, tmp_path, experiment_id
):
    selected = tmp_path / "selected.json"
    selected.write_text(
        json.dumps({"experiment_id": experiment_id}),
        encoding="utf-8",
    )
    monkeypatch.setattr(step6_report, "_SCRIPT_DIR", tmp_path)

    with pytest.raises(ValueError, match="experiment identifier"):
        step6_report._resolve_output_dir(None, selected)


def test_external_result_does_not_mix_workspace_auxiliary_data(
    monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "validate_stats.json").write_text(
        json.dumps({"needs_files_total": 999}), encoding="utf-8"
    )
    (workspace / "step2_inference_results.json").write_text(
        json.dumps({
            "experiment_id": "other",
            "results": [{"task_id": "other", "status": "error"}],
        }),
        encoding="utf-8",
    )
    (workspace / "step0_needs_files_manifest.json").write_text(
        json.dumps(_make_v2_manifest_data()), encoding="utf-8"
    )
    monkeypatch.setattr(step6_report, "WORKSPACE_DIR", workspace)
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    result_json = external_dir / "result.json"
    result_json.write_text(
        json.dumps(_make_result_payload()), encoding="utf-8"
    )
    output_dir = external_dir / "report"

    step6_report.generate_report(
        result_json_path=result_json,
        output_dir=output_dir,
        no_narrative=True,
    )
    report = json.loads(
        (output_dir / "report_data.json").read_text(encoding="utf-8")
    )

    assert report["file_generation"]["needs_files_total"] is None
    assert report["recovery_stats"]["resume_rounds"]["rounds_used"] == 0
    assert all(
        "prompt_classification" not in task
        for task in report["task_results"]
    )


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
    assert "execution_metrics" not in rd


def test_generate_report_adds_execution_metrics_only_when_measured(monkeypatch, tmp_path):
    payload = _make_result_payload()
    payload["results"][0]["observability"] = {
        "execution_metrics": {
            "schema_version": "1.0",
            "task_wall_time_ms": 100,
            "time_to_valid_artifact_ms": 90,
            "model_time_ms": 40,
            "tool_time_ms": 20,
            "verification_time_ms": 10,
            "dependency_time_ms": 5,
            "self_qa_time_ms": 8,
            "orchestration_time_ms": 17,
            "execution_attempt_count": 1,
            "sandbox_attempt_count": 1,
            "tool_call_count": 1,
            "self_qa_call_count": 1,
            "job_run_count": 1,
            "validated_artifact_count": 1,
        }
    }
    payload["results"][1]["status"] = "error"
    payload["results"][1]["observability"] = {
        "execution_metrics": {
            "schema_version": "1.0",
            "task_wall_time_ms": 300,
            "time_to_valid_artifact_ms": None,
            "model_time_ms": 100,
            "tool_time_ms": 80,
            "verification_time_ms": 20,
            "dependency_time_ms": 7,
            "self_qa_time_ms": 15,
            "orchestration_time_ms": 78,
            "execution_attempt_count": 2,
            "sandbox_attempt_count": 3,
            "tool_call_count": 3,
            "self_qa_call_count": 2,
            "job_run_count": 2,
            "validated_artifact_count": 0,
        }
    }

    rd = _run_step6(
        monkeypatch,
        tmp_path,
        manifest_data=None,
        result_payload=payload,
    )

    metrics = rd["execution_metrics"]
    assert metrics["measured_tasks"] == 2
    assert metrics["total_tasks"] == 2
    assert metrics["coverage_pct"] == 100.0
    assert metrics["avg_task_wall_time_ms"] == 200
    assert metrics["p50_task_wall_time_ms"] == 200
    assert metrics["p95_task_wall_time_ms"] == 290
    assert metrics["max_task_wall_time_ms"] == 300
    assert metrics["avg_successful_task_wall_time_ms"] == 100
    assert metrics["avg_failed_task_wall_time_ms"] == 300
    assert metrics["avg_time_to_valid_artifact_ms"] == 90
    assert metrics["total_model_time_ms"] == 140
    assert metrics["total_tool_time_ms"] == 100
    assert metrics["total_verification_time_ms"] == 30
    assert metrics["total_dependency_time_ms"] == 12
    assert metrics["total_self_qa_time_ms"] == 23
    assert metrics["total_orchestration_time_ms"] == 95
    assert metrics["total_execution_attempts"] == 3
    assert metrics["total_sandbox_attempts"] == 4
    assert metrics["total_tool_calls"] == 4
    assert metrics["total_self_qa_calls"] == 3
    assert metrics["total_job_runs"] == 3
    assert rd["task_results"][0]["observability"]["execution_metrics"]["task_wall_time_ms"] == 100


def test_generate_report_adds_agentic_metrics_only_when_measured(monkeypatch, tmp_path):
    payload = _make_result_payload()
    payload["results"][0]["observability"] = {
        "agentic_metrics": {
            "schema_version": "1.0",
            "task_wall_time_ms": 100,
            "model_api_calls": 3,
            "model_iterations": 3,
            "tool_calls": 4,
            "tool_errors": 1,
            "tool_calls_by_name": {
                "inspect_workspace": 1,
                "run_python": 1,
                "inspect_artifacts": 1,
                "finalize": 1,
            },
            "tool_time_ms": 20,
            "finalize_attempts": 1,
            "finalize_required_corrections": 0,
            "capability_misses": 0,
            "recovered_after_tool_error": True,
            "input_tokens": 100,
            "output_tokens": 20,
            "cached_tokens": 10,
            "usage_complete": True,
            "conservative_cost_usd": 0.25,
            "terminal_error_category": None,
        }
    }
    payload["results"][1]["status"] = "error"
    payload["results"][1]["observability"] = {
        "agentic_metrics": {
            "schema_version": "1.0",
            "task_wall_time_ms": 300,
            "model_api_calls": 2,
            "model_iterations": 2,
            "tool_calls": 2,
            "tool_errors": 1,
            "tool_calls_by_name": {
                "inspect_environment": 1,
                "run_ffmpeg": 1,
            },
            "tool_time_ms": 80,
            "finalize_attempts": 0,
            "finalize_required_corrections": 1,
            "capability_misses": 1,
            "recovered_after_tool_error": False,
            "input_tokens": 200,
            "output_tokens": 40,
            "cached_tokens": 20,
            "usage_complete": False,
            "conservative_cost_usd": 0.5,
            "terminal_error_category": "capability_missing",
        }
    }

    rd = _run_step6(
        monkeypatch,
        tmp_path,
        manifest_data=None,
        result_payload=payload,
    )

    metrics = rd["agentic_metrics"]
    assert metrics["measured_tasks"] == 2
    assert metrics["coverage_pct"] == 100.0
    assert metrics["total_model_api_calls"] == 5
    assert metrics["total_model_iterations"] == 5
    assert metrics["total_tool_calls"] == 6
    assert metrics["total_tool_errors"] == 2
    assert metrics["tool_error_rate_pct"] == 33.33
    assert metrics["tasks_with_tool_errors"] == 2
    assert metrics["recovered_tasks"] == 1
    assert metrics["recovery_rate_pct"] == 50.0
    assert metrics["total_finalize_attempts"] == 1
    assert metrics["total_finalize_required_corrections"] == 1
    assert metrics["total_capability_misses"] == 1
    assert metrics["p50_tool_time_ms"] == 50
    assert metrics["p95_tool_time_ms"] == 77
    assert metrics["total_input_tokens"] == 300
    assert metrics["total_output_tokens"] == 60
    assert metrics["total_cached_tokens"] == 30
    assert metrics["usage_complete_tasks"] == 1
    assert metrics["usage_coverage_pct"] == 50.0
    assert metrics["conservative_cost_usd"] == 0.75
    assert metrics["tool_calls_by_name"] == {
        "inspect_workspace": 1,
        "inspect_environment": 1,
        "run_python": 1,
        "run_ffmpeg": 1,
        "inspect_artifacts": 1,
        "finalize": 1,
    }
    assert metrics["terminal_error_categories"] == {"capability_missing": 1}
    assert rd["task_results"][0]["observability"]["agentic_metrics"][
        "model_api_calls"
    ] == 3


def test_compute_agentic_metrics_omits_unmeasured_and_rejects_nonfinite():
    payload = _make_result_payload()
    assert step6_report._compute_agentic_metrics(payload) is None

    payload["results"][0]["observability"] = {
        "agentic_metrics": {
            "task_wall_time_ms": float("nan"),
            "conservative_cost_usd": float("inf"),
        }
    }
    assert step6_report._compute_agentic_metrics(payload) is None


def test_compute_execution_metrics_ignores_giant_json_integer():
    payload = _make_result_payload()
    payload["results"][0]["observability"] = {
        "execution_metrics": {
            "schema_version": "1.0",
            "task_wall_time_ms": 10**400,
        }
    }

    assert step6_report._compute_execution_metrics(payload) is None


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
