"""Tests for the preregistered outcome-free 5/20 selector."""

from __future__ import annotations

import random
import subprocess

import pytest

from core.agentic_selector import (
    SEED,
    assert_outcome_free_checkout,
    build_selection_manifest,
    select_agentic_tasks,
    resolve_outcome_free_file,
)


def _clean_repository(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    return repository


def _commit(repository):
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(
        [
            "git", "-c", "user.name=Agentic Test",
            "-c", "user.email=agentic@example.invalid",
            "commit", "-qm", "fixture",
        ],
        cwd=repository,
        check=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _fixture():
    records = []
    rubrics = {}
    strata = [
        ("Finance", "xlsx", 12),
        ("Health", "pdf", 9),
        ("Media", "mp4", 7),
        ("Technology", "", 5),
    ]
    index = 0
    for sector, suffix, count in strata:
        for _ in range(count):
            task_id = f"task-{index:03d}"
            references = [] if not suffix else [{
                "path": f"input-{index}.{suffix}",
                "size_bytes": 100 + index,
            }]
            records.append({
                "task_id": task_id,
                "sector": sector,
                "occupation": f"Occupation {index}",
                "prompt": "Create a professional deliverable",
                "reference_files": references,
            })
            rubrics[task_id] = {
                "rubric_items": [{"score": 5}, {"score": 3}]
            }
            index += 1
    return records, rubrics


def test_selector_is_shuffle_invariant_and_exactly_disjoint_5_20():
    records, rubrics = _fixture()
    dataset_sha = "a" * 40
    first = select_agentic_tasks(
        records, rubrics, dataset_sha=dataset_sha
    )
    shuffled = list(records)
    random.Random(42).shuffle(shuffled)
    second = select_agentic_tasks(
        shuffled, rubrics, dataset_sha=dataset_sha
    )

    assert first == second
    assert first["seed"] == SEED
    assert len(first["canary_task_ids"]) == 5
    assert len(first["diagnostic_task_ids"]) == 20
    assert not (
        set(first["canary_task_ids"]) & set(first["diagnostic_task_ids"])
    )
    assert sum(item["selected_quota"] for item in first["strata"]) == 25
    assert sum(item["canary_quota"] for item in first["strata"]) == 5
    assert {
        item["sector"]: item["selected_quota"] for item in first["strata"]
    } == {
        "Finance": 9,
        "Health": 7,
        "Media": 5,
        "Technology": 4,
    }


def test_selector_domains_and_metadata_are_frozen():
    records, rubrics = _fixture()
    result = select_agentic_tasks(records, rubrics, dataset_sha="b" * 40)

    assert result["selection_domains"] == {
        "select": "agentic-select-v1",
        "canary": "agentic-canary-v1",
        "order_canary": "agentic-order-canary-v1",
        "order_diagnostic": "agentic-order-diagnostic-v1",
    }
    by_id = {item["task_id"]: item for item in result["selected_tasks"]}
    assert set(by_id) == set(result["canary_task_ids"] + result["diagnostic_task_ids"])
    assert all(item["positive_rubric_max"] == 8 for item in by_id.values())
    assert {item["input_class"] for item in by_id.values()} <= {
        "none", "tabular", "document", "media"
    }


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda records, rubrics: records[0].update({"grade": 100}), "outcome"),
        (lambda records, rubrics: records[0].update({"task_id": ""}), "task_id"),
        (lambda records, rubrics: rubrics.pop("task-000"), "missing rubric"),
        (
            lambda records, rubrics: records[0]["reference_files"][0].update(
                {"size_bytes": 600 * 1024 * 1024}
            ),
            "input limit",
        ),
    ],
)
def test_selector_rejects_structural_and_outcome_inputs(mutation, match):
    records, rubrics = _fixture()
    mutation(records, rubrics)

    with pytest.raises(ValueError, match=match):
        select_agentic_tasks(records, rubrics, dataset_sha="c" * 40)


@pytest.mark.parametrize("revision", ["main", "abc1234", "A" * 40, "g" * 40])
def test_selector_rejects_mutable_or_noncanonical_dataset_revision(revision):
    records, rubrics = _fixture()

    with pytest.raises(ValueError, match="full immutable dataset revision"):
        select_agentic_tasks(records, rubrics, dataset_sha=revision)


def test_manifest_records_selector_hash_and_recomputation_identity(tmp_path):
    records, rubrics = _fixture()
    selection = select_agentic_tasks(records, rubrics, dataset_sha="d" * 40)
    repository = _clean_repository(tmp_path)
    selector = repository / "selector.py"
    selector.write_text("print('selector')\n", encoding="utf-8")
    commit = _commit(repository)

    manifest = build_selection_manifest(
        selection,
        dataset_repo="owner/dataset",
        dataset_sha="d" * 40,
        rubric_repo="owner/rubric",
        rubric_sha="e" * 40,
        selector_path=selector,
        repository_root=repository,
        source_commit=commit,
    )

    assert len(manifest["selector"]["sha256"]) == 64
    assert manifest["selector"]["path"] == "selector.py"
    assert len(manifest["recomputation_sha256"]) == 64
    assert manifest["selected_before_outcomes"] is True


def test_manifest_rejects_mutable_rubric_revision_and_invalid_repository(
    tmp_path
):
    records, rubrics = _fixture()
    selection = select_agentic_tasks(records, rubrics, dataset_sha="d" * 40)
    repository = _clean_repository(tmp_path)
    selector = repository / "selector.py"
    selector.write_text("print('selector')\n", encoding="utf-8")
    commit = _commit(repository)

    with pytest.raises(ValueError, match="rubric revision"):
        build_selection_manifest(
            selection,
            dataset_repo="owner/dataset",
            dataset_sha="d" * 40,
            rubric_repo="owner/rubric",
            rubric_sha="main",
            selector_path=selector,
            repository_root=repository,
            source_commit=commit,
        )
    with pytest.raises(ValueError, match="dataset repository"):
        build_selection_manifest(
            selection,
            dataset_repo="https://example.test/dataset",
            dataset_sha="d" * 40,
            rubric_repo="owner/rubric",
            rubric_sha="e" * 40,
            selector_path=selector,
            repository_root=repository,
            source_commit=commit,
        )


def test_outcome_free_checkout_rejects_forbidden_paths(tmp_path):
    repository = _clean_repository(tmp_path)
    (repository / "README.md").write_text("fixture\n", encoding="utf-8")
    commit = _commit(repository)
    assert assert_outcome_free_checkout(repository) == commit
    forbidden = repository / "data" / "grades"
    forbidden.mkdir(parents=True)

    with pytest.raises(ValueError, match="forbidden outcome paths"):
        assert_outcome_free_checkout(repository)


def test_outcome_free_file_rejects_escape_and_symlink(tmp_path):
    repository = _clean_repository(tmp_path)
    source = repository / "dataset.json"
    source.write_text("[]", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text("[]", encoding="utf-8")
    link = repository / "link.json"
    link.symlink_to(outside)

    with pytest.raises(ValueError, match="escapes"):
        resolve_outcome_free_file(repository, outside, "dataset JSON")
    with pytest.raises(ValueError, match="symlink"):
        resolve_outcome_free_file(repository, link, "dataset JSON")