from pathlib import Path

import pytest
import yaml

from step8_grade import (
    _config_name_slug,
    hash_config,
    resolve_grade_output_path,
    validate_grading_config,
)


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
            "endpoint_env": "AZURE_OPENAI_ENDPOINT",
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
    with pytest.raises(ValueError, match="missing 'model'"):
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
        rubric_sha="rubric",
        rubric_short_sha="rubric",
        prompt_version="v1",
    )

    assert output.name == "Candidate-A-tight__0123456789abcdef.json"


@pytest.mark.parametrize("config_name", ["bad/name", "bad\\name", "bad\nname"])
def test_config_name_rejects_path_and_newline_injection(config_name):
    with pytest.raises(ValueError, match="newlines or path separators"):
        _config_name_slug(config_name)
