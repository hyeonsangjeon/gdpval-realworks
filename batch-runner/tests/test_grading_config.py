from pathlib import Path

import pytest
import yaml

from step8_grade import hash_config, validate_grading_config


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
