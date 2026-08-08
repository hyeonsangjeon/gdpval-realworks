import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from core.grade_payload import validate_grade_payload


def _load_schema() -> dict:
    return json.loads(Path("schemas/grade.schema.json").read_text(encoding="utf-8"))


def _minimal_payload() -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "exp998_smoke_baseline_sample",
        "experiment_yaml_name": "exp998_smoke_baseline_sample",
        "inference_model": "gpt-5.2-chat",
        "inference_completed_at": "2026-05-20T00:00:00Z",
        "judge": {
            "provider": "azure_openai",
            "api": "responses",
            "model": "gpt-5.4-pro",
            "deployment": "gpt-5.4-pro",
            "api_version": "2025-04-01-preview",
            "reasoning_effort": "high",
            "temperature": 0,
            "seed": 42,
            "config_name": "default_gpt5pro",
            "config_hash": "0123456789abcdef",
        },
        "rubric": {
            "source": "huggingface",
            "repo_id": "openai/gdpval",
            "revision": "main",
            "commit_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
            "short_sha": "11e7900",
        },
        "prompt": {"template": "prompts/grader_judge.md", "version": "v1"},
        "graded_at": "2026-05-20T00:00:00Z",
        "graded_by": "step8_grade.py",
        "graded_by_version": "0.1.0",
        "tasks": [
            {
                "task_id": "task-1",
                "sector": "s",
                "occupation": "o",
                "items": [
                    {
                        "rubric_item_id": "ri-1",
                        "criterion": "criterion",
                        "max_score": 2,
                        "awarded_score": 2,
                        "verdict": "pass",
                        "decided_by": "precheck",
                        "required": None,
                        "evidence": "evidence",
                        "judge_confidence": None,
                        "judge_latency_ms": None,
                        "precheck_pattern_id": "file_exists_or_name",
                        "judge_raw_response": None,
                    }
                ],
                "total_awarded": 2,
                "total_max": 2,
                "pct": 100,
                "critical_fail": False,
                "gold_referenced": False,
                "judge_call_count": 0,
                "precheck_count": 1,
                "judge_total_latency_ms": 0,
                "judge_input_tokens": 0,
                "judge_output_tokens": 0,
                "error": None,
                "graded_at": "2026-05-20T00:00:00Z",
            }
        ],
        "summary": {
            "total_tasks": 1,
            "graded_tasks": 1,
            "error_tasks": 0,
            "openai_compat": {
                "avg_score_pct": 100,
                "ci_pct": 0,
                "perfect_count": 1,
                "zero_count": 0,
                "partial_count": 0,
                "inconsistent_count": 0,
            },
            "wow": {
                "rubric_item_coverage_avg": 1,
                "critical_item_pass_rate": 1,
                "precheck_pass_rate": 1,
                "judge_pass_rate": 0,
                "judge_error_rate": 0,
                "by_sector": {},
                "by_rubric_category": {},
                "score_density_histogram": [],
                "rubric_severity_curve": [],
            },
            "cost": {
                "total_judge_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "estimated_cost_usd": 0,
                "total_judge_latency_sec": 0,
            },
        },
    }


def _valid_visual_provenance() -> dict:
    return {
        "path": "slides/report.pptx",
        "source_sha256": "a" * 64,
        "scope": {"slide": 1},
        "renderer_metadata": {
            "kind": "image_png_base64",
            "source_kind": "pptx",
            "source_slide_count": 4,
            "converted_page_count": 4,
            "renderer": {
                "converter": "libreoffice",
                "rasterizer": "pymupdf",
                "dpi": 150,
                "libreoffice_binary": "soffice",
                "libreoffice_version": "LibreOffice 24.2.7.2",
                "pymupdf_version": "1.26.3",
            },
            "byte_size": 1024,
        },
        "coverage_metadata": {
            "coverage_mode": "sampled_first_surface",
            "criterion_scope": "overall_style",
            "sampled_surface_count": 1,
            "total_surface_count": 4,
        },
        "vision": {
            "verdict": "pass",
            "evidence": "title is visible",
            "confidence": 0.9,
            "reasoning": "render inspected",
            "judge_error": None,
        },
    }


def test_minimal_valid_grade_passes_schema():
    validate(instance=_minimal_payload(), schema=_load_schema())


@pytest.mark.parametrize("schema_version", ["1.2", "1.3"])
def test_current_grade_requires_explicit_unpriced_cost_provenance(
    schema_version
):
    payload = _minimal_payload()
    payload.update({
        "schema_version": schema_version,
        "run_status": "final",
        "expected_task_count": 1,
        "expected_ordered_task_ids_sha256": "a" * 64,
        "azure_ai_routes": [{
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "workload": "grader",
            "runtime_fingerprint": "b" * 64,
        }],
        "azure_ai_runtime_fingerprint": "b" * 64,
    })
    payload["summary"]["cost"].update({
        "estimated_cost_usd": None,
        "pricing_complete": False,
        "unpriced_models": ["gpt-5.4-pro"],
    })

    validate_grade_payload(payload, _load_schema())

    for field, value in (
        ("estimated_cost_usd", 0.0),
        ("pricing_complete", True),
        ("unpriced_models", []),
    ):
        invalid = deepcopy(payload)
        invalid["summary"]["cost"][field] = value
        with pytest.raises((ValidationError, ValueError)):
            validate_grade_payload(invalid, _load_schema())

    for field in (
        "estimated_cost_usd",
        "pricing_complete",
        "unpriced_models",
    ):
        invalid = deepcopy(payload)
        del invalid["summary"]["cost"][field]
        with pytest.raises(ValidationError):
            validate_grade_payload(invalid, _load_schema())

    invalid = deepcopy(payload)
    invalid["summary"]["cost"]["unpriced_models"] = ["gpt-audio-1.5"]
    with pytest.raises(ValueError, match="persisted model identity"):
        validate_grade_payload(invalid, _load_schema())

    invalid = deepcopy(payload)
    del invalid["run_status"]
    invalid["summary"]["cost"]["unpriced_models"] = ["wrong-model"]
    with pytest.raises((ValidationError, ValueError)):
        validate_grade_payload(invalid, _load_schema())


@pytest.mark.parametrize("schema_version", ["1.0", "1.1"])
def test_previous_lifecycle_grade_keeps_numeric_cost_compatibility(
    schema_version
):
    payload = _minimal_payload()
    payload.update({
        "schema_version": schema_version,
        "run_status": "final",
        "expected_task_count": 1,
        "expected_ordered_task_ids_sha256": "a" * 64,
        "azure_ai_routes": [{
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "workload": "grader",
            "runtime_fingerprint": "b" * 64,
        }],
        "azure_ai_runtime_fingerprint": "b" * 64,
    })

    validate_grade_payload(payload, _load_schema())


def test_missing_required_field_fails():
    payload = _minimal_payload()
    del payload["judge"]
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def test_unknown_verdict_fails():
    payload = _minimal_payload()
    payload["tasks"][0]["items"][0]["verdict"] = "unknown"
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def test_pct_must_be_0_to_100():
    payload = _minimal_payload()
    payload["tasks"][0]["pct"] = 101
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def test_actual_smoke_output_passes_schema(tmp_path):
    payload = _minimal_payload()
    p = tmp_path / "grade.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    loaded = json.loads(p.read_text(encoding="utf-8"))
    validate(instance=loaded, schema=_load_schema())


def test_pinned_inference_and_grader_source_identity_pass_schema():
    payload = _minimal_payload()
    payload["source_inference_repo_id"] = "owner/repo"
    payload["source_inference_revision"] = "a" * 40
    payload["grader_source_hash"] = "b" * 64

    validate(instance=payload, schema=_load_schema())


def test_present_grader_runtime_fingerprint_must_not_be_null():
    payload = _minimal_payload()
    payload["azure_ai_runtime_fingerprint"] = None

    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def _current_grade_payload(schema_version: str = "1.2") -> dict:
    payload = _minimal_payload()
    payload.update({
        "schema_version": schema_version,
        "run_status": "partial",
        "expected_task_count": 1,
        "expected_ordered_task_ids_sha256": "a" * 64,
        "azure_ai_routes": [
            {
                "endpoint_kind": "direct-v1",
                "profile": "direct-v1",
                "runtime_fingerprint": "b" * 64,
                "workload": "grader",
            },
            {
                "endpoint_kind": "direct-v1",
                "profile": "direct-v1",
                "runtime_fingerprint": "c" * 64,
                "workload": "grader",
            },
        ],
        "azure_ai_runtime_fingerprint": "b" * 64,
    })
    payload["summary"]["cost"].update({
        "estimated_cost_usd": None,
        "pricing_complete": False,
        "unpriced_models": ["gpt-5.4-pro"],
    })
    return payload


def test_schema_1_3_requires_judge_errors_to_be_score_excluded():
    payload = _current_grade_payload("1.3")
    item = payload["tasks"][0]["items"][0]
    scored_item = deepcopy(item)
    scored_item["rubric_item_id"] = "ri-scored"
    payload["tasks"][0]["items"].append(scored_item)
    item.update({
        "verdict": "judge_error",
        "decided_by": "judge",
        "awarded_score": 0,
        "score_excluded": True,
    })
    payload["summary"]["wow"]["judge_error_rate"] = 1.0

    validate_grade_payload(payload, _load_schema())

    for invalid_value in (False, None):
        invalid = deepcopy(payload)
        if invalid_value is None:
            del invalid["tasks"][0]["items"][0]["score_excluded"]
        else:
            invalid["tasks"][0]["items"][0]["score_excluded"] = invalid_value
        with pytest.raises(ValidationError):
            validate_grade_payload(invalid, _load_schema())


@pytest.mark.parametrize("schema_version", ["1.0", "1.1", "1.2"])
def test_previous_schemas_keep_historical_judge_error_compatibility(
    schema_version
):
    payload = _current_grade_payload(schema_version)
    payload["tasks"][0]["items"][0].update({
        "verdict": "judge_error",
        "decided_by": "judge",
        "awarded_score": 0,
        "score_excluded": False,
    })

    validate_grade_payload(payload, _load_schema())

    payload["summary"]["openai_compat"]["avg_score_pct"] = None
    payload["summary"]["openai_compat"]["ci_pct"] = None
    with pytest.raises(ValidationError):
        validate_grade_payload(payload, _load_schema())


def test_schema_1_3_requires_visible_judge_error_rate():
    payload = _current_grade_payload("1.3")
    del payload["summary"]["wow"]["judge_error_rate"]

    with pytest.raises(ValidationError):
        validate_grade_payload(payload, _load_schema())

    previous = deepcopy(payload)
    previous["schema_version"] = "1.2"
    validate_grade_payload(previous, _load_schema())


def test_schema_1_3_rejects_all_excluded_task_as_zero_score():
    payload = _current_grade_payload("1.3")
    item = payload["tasks"][0]["items"][0]
    item.update({
        "verdict": "judge_error",
        "decided_by": "judge",
        "awarded_score": 0,
        "score_excluded": True,
    })
    payload["summary"].update({"graded_tasks": 0, "error_tasks": 1})
    payload["summary"]["wow"]["judge_error_rate"] = 1.0
    payload["summary"]["openai_compat"].update({
        "avg_score_pct": None,
        "ci_pct": None,
        "perfect_count": 0,
        "zero_count": 0,
        "partial_count": 0,
    })

    invalid = deepcopy(payload)
    invalid["tasks"][0]["error"] = None
    invalid["summary"]["openai_compat"]["avg_score_pct"] = 0.0
    invalid["summary"]["openai_compat"]["ci_pct"] = 0.0
    invalid["summary"]["openai_compat"]["zero_count"] = 1
    with pytest.raises((ValidationError, ValueError)):
        validate_grade_payload(invalid, _load_schema())

    payload["tasks"][0]["error"] = "all_items_score_excluded"
    validate_grade_payload(payload, _load_schema())

    payload["summary"]["total_tasks"] = 999
    with pytest.raises(ValueError, match="task counts"):
        validate_grade_payload(payload, _load_schema())

    payload["summary"]["total_tasks"] = 1
    payload["summary"]["openai_compat"]["inconsistent_count"] = 7
    with pytest.raises(ValueError, match="headline scores"):
        validate_grade_payload(payload, _load_schema())


@pytest.mark.parametrize(
    "missing_field", ["azure_ai_routes", "azure_ai_runtime_fingerprint"]
)
def test_current_grade_requires_azure_runtime_identity(missing_field):
    payload = _current_grade_payload()
    del payload[missing_field]

    with pytest.raises(ValidationError):
        validate_grade_payload(payload, _load_schema())


def test_current_grade_binds_top_level_fingerprint_to_primary_route():
    payload = _current_grade_payload()
    validate_grade_payload(payload, _load_schema())
    payload["azure_ai_runtime_fingerprint"] = "c" * 64

    with pytest.raises(ValueError, match="primary grader route fingerprint"):
        validate_grade_payload(payload, _load_schema())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_inference_repo_id", "owner/repo/extra"),
        ("source_inference_revision", "A" * 40),
        ("source_inference_revision", "a" * 39),
        ("grader_source_hash", "B" * 64),
        ("grader_source_hash", "b" * 63),
    ],
)
def test_noncanonical_pinning_identity_fails_schema(field, value):
    payload = _minimal_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def test_track2_renderer_fingerprint_and_visual_provenance_pass_schema():
    payload = _minimal_payload()
    payload["renderer_fingerprint"] = {
        "libreoffice_binary": "soffice",
        "libreoffice_version": "LibreOffice 24.2.7.2",
        "pymupdf_version": "1.26.3",
    }
    payload["tasks"][0]["items"][0]["visual_provenance"] = [
        _valid_visual_provenance()
    ]

    validate(instance=payload, schema=_load_schema())


def test_visual_provenance_rejects_base64_field():
    payload = _minimal_payload()
    provenance = _valid_visual_provenance()
    provenance["base64"] = "must-not-persist"
    payload["tasks"][0]["items"][0]["visual_provenance"] = [provenance]

    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


@pytest.mark.parametrize(
    "bad_path",
    ["/absolute/report.pdf", "C:\\absolute\\report.pdf", "safe/../report.pdf"],
)
@pytest.mark.parametrize("location", ["parent", "child"])
def test_visual_provenance_rejects_unconfined_paths(bad_path, location):
    payload = _minimal_payload()
    provenance = _valid_visual_provenance()
    provenance["path"] = bad_path
    item = payload["tasks"][0]["items"][0]
    if location == "parent":
        item["visual_provenance"] = [provenance]
    else:
        item["child_grades"] = [{"visual_provenance": [provenance]}]

    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


@pytest.mark.parametrize("location", ["parent", "child"])
def test_visual_provenance_rejects_nested_renderer_base64(location):
    payload = _minimal_payload()
    provenance = _valid_visual_provenance()
    provenance["renderer_metadata"]["renderer"]["base64"] = "forbidden"
    item = payload["tasks"][0]["items"][0]
    if location == "parent":
        item["visual_provenance"] = [provenance]
    else:
        item["child_grades"] = [{"visual_provenance": [provenance]}]

    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def test_itemgrade_asdict_with_parent_and_child_provenance_passes_schema():
    from core.grader import ItemGrade

    payload = _minimal_payload()
    provenance = _valid_visual_provenance()
    item = ItemGrade(
        rubric_item_id="visual-1",
        criterion="Overall Style",
        max_score=4,
        awarded_score=4.0,
        verdict="pass",
        decided_by="judge",
        required=None,
        evidence="visible professional layout",
        routing_modality="mixed",
        perception_called=True,
        tools_used=["harness_render_to_image", "harness_vision_perception"],
        visual_provenance=[deepcopy(provenance)],
        child_grades=[
            {
                "target_id": "report",
                "visual_provenance": [deepcopy(provenance)],
            }
        ],
    )
    payload["tasks"][0]["items"][0] = asdict(item)

    validate(instance=payload, schema=_load_schema())


def test_legacy_child_without_visual_provenance_remains_schema_compatible():
    payload = _minimal_payload()
    payload["tasks"][0]["items"][0]["child_grades"] = [
        {"target_id": "legacy-child", "verdict": "pass"}
    ]

    validate(instance=payload, schema=_load_schema())
