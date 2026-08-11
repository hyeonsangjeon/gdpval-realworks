from pathlib import Path

import pytest
import yaml

from step8_grade import (
    _config_name_slug,
    hash_config,
    resolve_grade_output_path,
    validate_grading_config,
)
from core.azure_ai_clients import AzureAIWorkload, grader_route_workloads


INFERENCE_SHA = "a" * 40
GRADER_SOURCE_HASH = "b" * 64


def _valid_config(tmp_path: Path) -> dict:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("x", encoding="utf-8")
    return {
        "schema_version": "1.0",
        "config_name": "default_gpt5pro",
        "judge": {
            "provider": "azure_openai",
            "api": "responses",
            "model": "gpt-5.4-pro",
            "deployment": "gpt-5.4-pro",
        },
        "rubric": {
            "repo_id": "openai/gdpval",
            "revision": "main",
            "cache_dir": "data/gdpval-local",
        },
        "prompt": {
            "template": str(prompt),
            "version": "v1",
        },
        "output": {
            "directory": "data/grades",
            "filename_template": "{exp_id}__{judge_slug}__{rubric_short_sha}__{prompt_v}.json",
        },
    }


def test_default_config_loads_and_validates():
    path = Path("grading_configs/default_gpt5pro.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_grading_config(data)
    assert data["output"]["directory"] == "../data/grades"


def test_missing_required_key_fails(tmp_path):
    cfg = _valid_config(tmp_path)
    del cfg["judge"]["model"]
    with pytest.raises(ValueError):
        validate_grading_config(cfg)


def test_schema_version_mismatch_fails(tmp_path):
    cfg = _valid_config(tmp_path)
    # 1.0 and 2.0 are both valid post-PR2; an unknown version still fails.
    cfg["schema_version"] = "3.0"
    with pytest.raises(ValueError):
        validate_grading_config(cfg)


def test_schema_version_2_0_passes_when_valid(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    validate_grading_config(cfg)


def test_default_v2_config_loads_and_validates():
    """The PR2 task 208 default_v2.yaml must validate as a v2 config."""
    path = Path("grading_configs/default_v2.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_grading_config(data)
    assert data["schema_version"] == "2.0"
    assert "tools" in data["judge"]
    assert "read_deliverable" in data["judge"]["tools"]
    assert "perception" in data["judge"]
    assert data["judge"]["critical"]["rule"] == "abs_max_score_threshold"


def test_default_v2_sol_max_config_is_complete_production_identity():
    path = Path("grading_configs/default_v2_sol_max.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    validate_grading_config(data)

    judge = data["judge"]
    assert judge["model"] == judge["deployment"] == "gpt-5.6-sol"
    assert judge["reasoning"] == {"effort": "max"}
    assert judge["generation"]["finalization_reasoning_effort"] == "max"
    assert judge["perception"]["visual"]["model"] == "gpt-5.6-sol"
    assert judge["perception"]["visual"]["deployment"] == "gpt-5.6-sol"
    assert judge["perception"]["visual"]["reasoning_effort"] == "max"
    assert judge["perception"]["audio"]["deployment"] == "gpt-audio-1.5"
    assert "context_window" not in path.read_text(encoding="utf-8")
    assert grader_route_workloads(data) == [
        (AzureAIWorkload.GRADER, "gpt-5.6-sol"),
        (AzureAIWorkload.GRADER, "gpt-5.6-sol"),
        (AzureAIWorkload.GRADER, "gpt-audio-1.5"),
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("main", None, "judge.reasoning.effort is invalid"),
        ("main", "maximum", "judge.reasoning.effort is invalid"),
        (
            "finalization",
            None,
            "judge.generation.finalization_reasoning_effort is invalid",
        ),
        (
            "finalization",
            "maximum",
            "judge.generation.finalization_reasoning_effort is invalid",
        ),
        (
            "visual",
            None,
            "judge.perception.visual.reasoning_effort is invalid",
        ),
        (
            "visual",
            "maximum",
            "judge.perception.visual.reasoning_effort is invalid",
        ),
    ],
)
def test_reasoning_efforts_reject_null_and_unknown_values(
    tmp_path, field, value, message
):
    cfg = _valid_config(tmp_path)
    if field == "main":
        cfg["judge"]["reasoning"] = {"effort": value}
    elif field == "finalization":
        cfg["judge"]["generation"] = {
            "finalization_reasoning_effort": value,
        }
    else:
        cfg["judge"]["perception"] = {
            "visual": {
                "model": "gpt-5.6-sol",
                "reasoning_effort": value,
            },
        }

    with pytest.raises(ValueError, match=message):
        validate_grading_config(cfg)


def test_grade_workflow_defaults_to_v2_sol_max():
    workflow = yaml.safe_load(
        Path("../.github/workflows/grade-run.yml").read_text(encoding="utf-8")
    )
    triggers = workflow.get("on") or workflow.get(True)
    assert (
        triggers["workflow_dispatch"]["inputs"]["grading_config"]["default"]
        == "default_v2_sol_max.yaml"
    )


@pytest.mark.parametrize(
    "filename",
    [
        "default_gpt5pro.yaml",
        "default_v2.yaml",
        "default_v2_sol_max.yaml",
        "default_v2_mini.yaml",
        "default_v2_tight.yaml",
        "regrade_exp003_v2_mini_score_excluded.yaml",
        "regrade_exp003_v2_sol_max_score_excluded.yaml",
        "validation_exp003_v2_sol_max_anchor4.yaml",
        "validation_v2_mini_cohort3.yaml",
        "validation_v2_mini_cohort10.yaml",
    ],
)
def test_active_configs_declare_safe_precheck_v2(filename: str):
    path = Path("grading_configs") / filename
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    validate_grading_config(data)

    assert data["grader"]["precheck_patterns_version"] == "v2"
    assert "grades_per_task" not in data["grader"]


@pytest.mark.parametrize(
    ("filename", "config_name"),
    [
        ("validation_v2_mini_cohort3.yaml", "validation_v2_mini_cohort3"),
        ("validation_v2_mini_cohort10.yaml", "validation_v2_mini_cohort10"),
    ],
)
def test_cohort_configs_only_change_baseline_identity(
    filename: str, config_name: str
):
    baseline_path = Path("grading_configs/default_v2_mini.yaml")
    candidate_path = Path("grading_configs") / filename
    baseline = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
    candidate = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))

    validate_grading_config(candidate)
    assert candidate["config_name"] == config_name
    baseline_hash = hash_config(str(baseline_path))
    candidate_hash = hash_config(str(candidate_path))
    assert candidate_hash != baseline_hash

    common = {
        "experiment_id": "exp003_GPT52Chat_baseline_runner_exec",
        "judge_slug": "gpt-5_4-mini",
        "rubric_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
        "rubric_short_sha": "11e7900",
        "prompt_version": "v2.2",
        "inference_sha": INFERENCE_SHA,
        "grader_source_hash": GRADER_SOURCE_HASH,
    }
    baseline_output = resolve_grade_output_path(
        baseline, config_hash=baseline_hash, **common
    )
    candidate_output = resolve_grade_output_path(
        candidate, config_hash=candidate_hash, **common
    )
    assert candidate_output != baseline_output
    assert f"__{config_name}__cfg_{candidate_hash}__" in candidate_output.name

    for key in ("config_name", "description"):
        baseline.pop(key)
        candidate.pop(key)
    assert candidate == baseline


def test_exp003_score_excluded_rerun_identity_is_pinned():
    baseline_path = Path("grading_configs/default_v2_mini.yaml")
    rerun_path = Path(
        "grading_configs/regrade_exp003_v2_mini_score_excluded.yaml"
    )
    baseline = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
    rerun = yaml.safe_load(rerun_path.read_text(encoding="utf-8"))

    validate_grading_config(rerun)

    identity = rerun["rerun_identity"]
    assert identity == {
        "experiment_id": "exp003_GPT52Chat_baseline_runner_exec",
        "expected_task_count": 220,
        "rubric_commit_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
        "inference_revision": "9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f",
    }
    assert rerun["rubric"]["revision"] == identity["rubric_commit_sha"]
    assert hash_config(str(rerun_path)) == "55a7dc5cfb8023fe"

    for key in ("config_name", "description"):
        baseline.pop(key)
        rerun.pop(key)
    rerun.pop("rerun_identity")
    baseline["rubric"]["revision"] = identity["rubric_commit_sha"]
    assert rerun == baseline


@pytest.mark.parametrize(
    ("filename", "expected_task_count", "expected_hash"),
    [
        (
            "regrade_exp003_v2_sol_max_score_excluded.yaml",
            220,
            "14fc577ea39d98c5",
        ),
        (
            "validation_exp003_v2_sol_max_anchor4.yaml",
            4,
            "6dcff620fbe8dbf3",
        ),
    ],
)
def test_exp003_sol_max_configs_are_pinned_and_preserve_modalities(
    filename: str,
    expected_task_count: int,
    expected_hash: str,
):
    baseline_path = Path("grading_configs/default_v2_sol_max.yaml")
    candidate_path = Path("grading_configs") / filename
    baseline = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
    candidate = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))

    validate_grading_config(candidate)

    identity = candidate["rerun_identity"]
    expected_identity = {
        "experiment_id": "exp003_GPT52Chat_baseline_runner_exec",
        "expected_task_count": expected_task_count,
        "rubric_commit_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
        "inference_revision": "9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f",
    }
    if expected_task_count == 4:
        expected_identity["task_ids"] = [
            "99ac6944-4ec6-4848-959c-a460ac705c6f",
            "4c18ebae-dfaa-4b76-b10c-61fcdf26734c",
            "40a8c4b1-b169-4f92-a38b-7f79685037ec",
            "a73fbc98-90d4-4134-a54f-2b1d0c838791",
        ]
    assert identity == expected_identity
    assert candidate["rubric"]["revision"] == identity["rubric_commit_sha"]
    assert hash_config(str(candidate_path)) == expected_hash
    assert candidate["judge"]["perception"]["audio"] == (
        baseline["judge"]["perception"]["audio"]
    )
    assert candidate["judge"]["perception"]["visual"]["call_cap_per_task"] == 72
    if expected_task_count == 220:
        assert "task_ids" not in identity
        assert "anchor_projection" not in candidate
    else:
        assert candidate["anchor_projection"] == {
            "method": "modality_normalized_v1",
            "anchor_config_name": "validation_exp003_v2_sol_max_anchor4",
            "anchor_task_count": 4,
            "anchor_ordered_task_ids_sha256": (
                "29d5623a5cec85eb38f21fb73a2f3b06c66ed6a5fd6fd95948b979cd70a70bc9"
            ),
            "anchor_source_inference_repo_id": (
                "HyeonSang/exp003_GPT52Chat_baseline_runner_exec"
            ),
            "baseline_payload_sha256": (
                "b5cbb6a80c776b458f99f007841a946c1c5f9ec8bf60be052500713dd6f13570"
            ),
            "baseline_schema_version": "1.0",
            "baseline_perception_wired": False,
            "baseline_main_calls": 234,
            "baseline_main_latency_ms": 2449199.44,
            "baseline_final_json_parse_failed": 13,
            "baseline_empty_final_text": 9,
            "anchor_visual_criteria": 43,
            "anchor_audio_criteria": 13,
            "full_task_count": 220,
            "full_visual_criteria": 337,
            "full_audio_criteria": 58,
            "chunk_envelope_hours": 44,
        }

    for key in ("config_name", "description"):
        baseline.pop(key)
        candidate.pop(key)
    candidate.pop("rerun_identity")
    candidate.pop("anchor_projection", None)
    baseline["rubric"]["revision"] = identity["rubric_commit_sha"]
    assert candidate == baseline


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("expected_task_count", 0, "expected_task_count"),
        ("expected_task_count", 221, "expected_task_count"),
        ("inference_revision", "main", "inference_revision"),
    ],
)
def test_sol_max_rerun_identity_rejects_invalid_values(
    field: str,
    value,
    message: str,
):
    path = Path("grading_configs/regrade_exp003_v2_sol_max_score_excluded.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["rerun_identity"][field] = value

    with pytest.raises(ValueError, match=message):
        validate_grading_config(config)


def test_sol_max_anchor_acceptance_is_preregistered():
    readme = Path("grading_configs/README.md").read_text(encoding="utf-8")

    for task_id in (
        "99ac6944-4ec6-4848-959c-a460ac705c6f",
        "40a8c4b1-b169-4f92-a38b-7f79685037ec",
        "4c18ebae-dfaa-4b76-b10c-61fcdf26734c",
        "a73fbc98-90d4-4134-a54f-2b1d0c838791",
    ):
        assert task_id in readme
    for expected in (
        "final_json_parse_failed",
        "empty_final_text",
        "2,449.19944",
        "6dcff620fbe8dbf3",
        "337 / 43",
        "58 / 13",
        "44-hour",
        "main-judge-only reference",
        "task_visual_budget_exceeded",
    ):
        assert expected in readme


def test_anchor_task_ids_are_unique_and_match_expected_count():
    path = Path("grading_configs/validation_exp003_v2_sol_max_anchor4.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    identity = config["rerun_identity"]

    assert identity["task_ids"] == [
        "99ac6944-4ec6-4848-959c-a460ac705c6f",
        "4c18ebae-dfaa-4b76-b10c-61fcdf26734c",
        "40a8c4b1-b169-4f92-a38b-7f79685037ec",
        "a73fbc98-90d4-4134-a54f-2b1d0c838791",
    ]
    assert len(identity["task_ids"]) == identity["expected_task_count"] == 4
    assert len(set(identity["task_ids"])) == 4


@pytest.mark.parametrize(
    ("task_ids", "expected_task_count", "message"),
    [
        (["task-a", "task-a"], 2, "duplicate"),
        (["task-a", "task-b"], 3, "expected_task_count"),
        (["task-a,b", "task-c"], 2, "task_ids"),
    ],
)
def test_rerun_identity_rejects_invalid_task_ids(
    task_ids: list[str],
    expected_task_count: int,
    message: str,
):
    path = Path("grading_configs/validation_exp003_v2_sol_max_anchor4.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["rerun_identity"]["task_ids"] = task_ids
    config["rerun_identity"]["expected_task_count"] = expected_task_count

    with pytest.raises(ValueError, match=message):
        validate_grading_config(config)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda config: config.pop("rerun_identity"), "requires pinned"),
        (
            lambda config: config["anchor_projection"].__setitem__(
                "baseline_perception_wired",
                True,
            ),
            "perception",
        ),
        (
            lambda config: config["anchor_projection"].__setitem__(
                "anchor_audio_criteria",
                0,
            ),
            "positive integers",
        ),
        (
            lambda config: config["anchor_projection"].__setitem__(
                "anchor_task_count",
                3,
            ),
            "must match pinned task_ids",
        ),
        (
            lambda config: config["anchor_projection"].__setitem__(
                "anchor_config_name",
                "wrong_config",
            ),
            "must match config_name",
        ),
        (
            lambda config: config["anchor_projection"].__setitem__(
                "anchor_ordered_task_ids_sha256",
                "0" * 64,
            ),
            "must match pinned task_ids",
        ),
        (
            lambda config: config["anchor_projection"].__setitem__(
                "anchor_source_inference_repo_id",
                "other/repo",
            ),
            "must match experiment source",
        ),
        (
            lambda config: config["anchor_projection"].pop(
                "full_visual_criteria"
            ),
            "versioned contract",
        ),
    ],
)
def test_anchor_projection_rejects_invalid_contract(mutation, message):
    path = Path("grading_configs/validation_exp003_v2_sol_max_anchor4.yaml")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutation(config)

    with pytest.raises(ValueError, match=message):
        validate_grading_config(config)


def test_v2_tools_block_requires_ops_list(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    cfg["judge"]["tools"] = {"read_deliverable": {"ops": []}}
    with pytest.raises(ValueError, match="non-empty list"):
        validate_grading_config(cfg)


def test_v2_tools_block_rejects_unknown_op(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    cfg["judge"]["tools"] = {"read_deliverable": {"ops": ["nuke_disk"]}}
    with pytest.raises(ValueError, match="unknown ops"):
        validate_grading_config(cfg)


def test_v2_tools_block_rejects_harness_owned_render_op(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    cfg["judge"]["tools"] = {
        "read_deliverable": {"ops": ["read_content", "render_to_image"]}
    }
    with pytest.raises(ValueError, match="harness-owned"):
        validate_grading_config(cfg)


def test_v2_perception_block_requires_model(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    cfg["judge"]["perception"] = {"visual": {"vision": True}}  # no model
    with pytest.raises(ValueError, match="missing model/deployment"):
        validate_grading_config(cfg)


def test_v2_critical_rule_enum(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    cfg["judge"]["critical"] = {"rule": "bogus_rule"}
    with pytest.raises(ValueError, match="critical.rule unknown"):
        validate_grading_config(cfg)


def test_tool_template_must_exist_if_set(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    cfg["prompt"]["tool_template"] = str(tmp_path / "missing_tool_prompt.md")
    with pytest.raises(ValueError, match="tool_template not found"):
        validate_grading_config(cfg)


def test_template_path_must_exist(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["prompt"]["template"] = str(tmp_path / "nope.md")
    with pytest.raises(ValueError):
        validate_grading_config(cfg)


def test_config_hash_is_stable(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("a: 1\n", encoding="utf-8")
    assert hash_config(str(p)) == hash_config(str(p))


def test_hash_changes_when_content_changes(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("a: 1\n", encoding="utf-8")
    h1 = hash_config(str(p))
    p.write_text("a: 2\n", encoding="utf-8")
    h2 = hash_config(str(p))
    assert h1 != h2


def test_all_active_v2_configs_resolve_distinct_versioned_names():
    standard_path = Path("grading_configs/default_v2.yaml")
    mini_path = Path("grading_configs/default_v2_mini.yaml")
    tight_path = Path("grading_configs/default_v2_tight.yaml")
    standard = yaml.safe_load(standard_path.read_text(encoding="utf-8"))
    mini = yaml.safe_load(mini_path.read_text(encoding="utf-8"))
    tight = yaml.safe_load(tight_path.read_text(encoding="utf-8"))

    standard_hash = hash_config(str(standard_path))
    mini_hash = hash_config(str(mini_path))
    tight_hash = hash_config(str(tight_path))
    rubric_sha = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    common = {
        "experiment_id": "exp003",
        "judge_slug": "gpt-5_4",
        "rubric_sha": rubric_sha,
        "rubric_short_sha": "11e7900",
        "prompt_version": "v2.2",
        "inference_sha": INFERENCE_SHA,
    }
    standard_output = resolve_grade_output_path(
        standard,
        config_hash=standard_hash,
        grader_source_hash="1" * 64,
        **common,
    )
    mini_output = resolve_grade_output_path(
        mini,
        config_hash=mini_hash,
        grader_source_hash="2" * 64,
        **{**common, "judge_slug": "gpt-5_4-mini"},
    )
    tight_output = resolve_grade_output_path(
        tight,
        config_hash=tight_hash,
        grader_source_hash="3" * 64,
        **common,
    )

    assert len({standard_output, mini_output, tight_output}) == 3
    assert f"__default_v2__cfg_{standard_hash}__" in standard_output.name
    assert f"__default_v2_mini__cfg_{mini_hash}__" in mini_output.name
    assert f"__default_v2_tight__cfg_{tight_hash}__" in tight_output.name
    assert standard_output.name.endswith(
        f"__rubric_{rubric_sha}__inference_{INFERENCE_SHA}__src_{'1' * 16}__v2.2.json"
    )
    assert mini_output.name.endswith(
        f"__rubric_{rubric_sha}__inference_{INFERENCE_SHA}__src_{'2' * 16}__v2.2.json"
    )
    assert tight_output.name.endswith(
        f"__rubric_{rubric_sha}__inference_{INFERENCE_SHA}__src_{'3' * 16}__v2.2.json"
    )


def test_track2_full_sha_prevents_same_short_prefix_collision(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    cfg["output"]["filename_template"] = "{exp_id}__rubric_{rubric_sha}.json"
    first_sha = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    second_sha = "11e7900fffffffffffffffffffffffffffffffff"
    common = {
        "experiment_id": "exp003",
        "judge_slug": "gpt-5_4",
        "config_hash": "0123456789abcdef",
        "rubric_short_sha": "11e7900",
        "prompt_version": "v2.2",
        "inference_sha": INFERENCE_SHA,
        "grader_source_hash": GRADER_SOURCE_HASH,
    }

    first = resolve_grade_output_path(cfg, rubric_sha=first_sha, **common)
    second = resolve_grade_output_path(cfg, rubric_sha=second_sha, **common)

    assert first != second
    assert first_sha in first.name
    assert second_sha in second.name


def test_track2_full_inference_sha_and_source_hash_route_distinct_outputs(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"
    cfg["output"]["filename_template"] = (
        "{exp_id}__{inference_sha}__src_{grader_source_hash_short}.json"
    )
    common = {
        "experiment_id": "exp003",
        "judge_slug": "gpt-5_4",
        "config_hash": "0123456789abcdef",
        "rubric_sha": "1" * 40,
        "rubric_short_sha": "1" * 7,
        "prompt_version": "v2.2",
    }

    first = resolve_grade_output_path(
        cfg,
        inference_sha="a" * 40,
        grader_source_hash="b" * 64,
        **common,
    )
    different_inference = resolve_grade_output_path(
        cfg,
        inference_sha="c" * 40,
        grader_source_hash="b" * 64,
        **common,
    )
    different_source = resolve_grade_output_path(
        cfg,
        inference_sha="a" * 40,
        grader_source_hash="d" * 64,
        **common,
    )

    assert len({first, different_inference, different_source}) == 3
    assert "a" * 40 in first.name
    assert "src_" + "b" * 16 in first.name


@pytest.mark.parametrize(
    "rubric_sha",
    ["11e7900", "G" * 40, "A" * 40, "a" * 39, "a" * 41],
)
def test_track2_output_rejects_noncanonical_full_sha(tmp_path, rubric_sha):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"

    with pytest.raises(ValueError, match="full 40-character lowercase"):
        resolve_grade_output_path(
            cfg,
            experiment_id="exp003",
            judge_slug="gpt-5_4",
            config_hash="0123456789abcdef",
            rubric_sha=rubric_sha,
            rubric_short_sha=rubric_sha[:7],
            prompt_version="v2.2",
            inference_sha=INFERENCE_SHA,
            grader_source_hash=GRADER_SOURCE_HASH,
        )


@pytest.mark.parametrize(
    ("inference_sha", "grader_source_hash", "message"),
    [
        ("A" * 40, GRADER_SOURCE_HASH, "inference_sha"),
        ("a" * 39, GRADER_SOURCE_HASH, "inference_sha"),
        (INFERENCE_SHA, "B" * 64, "grader_source_hash"),
        (INFERENCE_SHA, "b" * 63, "grader_source_hash"),
    ],
)
def test_track2_output_rejects_noncanonical_inference_or_source_hash(
    tmp_path, inference_sha, grader_source_hash, message
):
    cfg = _valid_config(tmp_path)
    cfg["schema_version"] = "2.0"

    with pytest.raises(ValueError, match=message):
        resolve_grade_output_path(
            cfg,
            experiment_id="exp003",
            judge_slug="gpt-5_4",
            config_hash="0123456789abcdef",
            rubric_sha="1" * 40,
            rubric_short_sha="1" * 7,
            prompt_version="v2.2",
            inference_sha=inference_sha,
            grader_source_hash=grader_source_hash,
        )


def test_config_name_is_slugged_for_filename_substitution(tmp_path):
    cfg = _valid_config(tmp_path)
    cfg["config_name"] = "Candidate A (tight)"
    cfg["output"]["filename_template"] = "{config_name}__{config_hash}.json"

    output = resolve_grade_output_path(
        cfg,
        experiment_id="exp",
        judge_slug="judge",
        config_hash="0123456789abcdef",
        rubric_sha="a" * 40,
        rubric_short_sha="a" * 7,
        prompt_version="v1",
        inference_sha="b" * 40,
        grader_source_hash="c" * 64,
    )

    assert output.name == "Candidate-A-tight__0123456789abcdef.json"


@pytest.mark.parametrize("config_name", ["bad/name", "bad\\name", "bad\nname"])
def test_config_name_rejects_path_and_newline_injection(config_name):
    with pytest.raises(ValueError, match="newlines or path separators"):
        _config_name_slug(config_name)
