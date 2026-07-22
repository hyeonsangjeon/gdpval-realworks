from core.source_identity import source_task_projection_sha256


def _projection(**overrides):
    values = {
        "task_id": "task-1",
        "sector": "sector",
        "occupation": "occupation",
        "prompt": "prompt",
        "rubric_pretty": "rubric pretty",
        "rubric_json": "{}",
        "reference_files": ["reference_files/task/a.pdf"],
        "reference_file_urls": ["https://example.test/a.pdf"],
        "reference_file_hf_uris": ["hf://datasets/source/a.pdf"],
    }
    values.update(overrides)
    return source_task_projection_sha256(**values)


def test_source_projection_binds_prompt_rubric_and_taxonomy():
    baseline = _projection()

    assert _projection(prompt="changed") != baseline
    assert _projection(rubric_json='{"changed":true}') != baseline
    assert _projection(sector="changed") != baseline
    assert _projection(occupation="changed") != baseline


def test_source_projection_binds_reference_assignment_and_uris():
    baseline = _projection()

    assert _projection(
        reference_files=["reference_files/task/b.pdf"]
    ) != baseline
    assert _projection(
        reference_file_urls=["https://example.test/b.pdf"]
    ) != baseline
    assert _projection(
        reference_file_hf_uris=["hf://datasets/source/b.pdf"]
    ) != baseline