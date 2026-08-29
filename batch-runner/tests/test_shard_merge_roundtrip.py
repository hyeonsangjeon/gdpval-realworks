"""End-to-end proof that sharded grading reassembles into a serial-identical run.

``tests/test_step8_grade.py`` pins step8's slicing and ``tests/test_step9_merge_shards.py``
pins step9's merge algebra, but each does so against payloads the other never
produced. This module closes that gap: it drives real ``step8_grade.main()``
invocations with ``--shard-count``, feeds the resulting partials to real
``step9_merge_shards.main()``, and diffs the merged payload against a serial run
of the same corpus. Sharding is only worth doing if that diff is empty, because
the whole premise is that splitting the 220-task corpus across N relays changes
wall-clock only -- never a score, an aggregate, or an identity field.

Layout note: each run gets its own ``<parent>/batch-runner`` directory rather
than ``<parent>/shard0``. ``compute_grader_source_hash`` folds the
*repository-relative* config path into the digest, so a run rooted at
``.../shard0`` hashes ``shard0/grading_configs/default.yaml`` while one rooted at
``.../shard1`` hashes ``shard1/...`` -- different hashes for identical bytes, and
step9 rightly rejects the merge. Real shards all check out to the same
``$GITHUB_WORKSPACE/batch-runner``, so the harness has to mirror that or it tests
a layout that never ships.
"""

import json
from pathlib import Path

import pytest

import step8_grade as s8
import step9_merge_shards as s9
from core.cost_receipts import verify_export
from core.grade_payload import validate_grade_payload
from tests.test_step8_grade import (  # noqa: F401 -- _typed_azure_ai_route is an autouse fixture
    _FakeGrader,
    _FakeLoader,
    _setup_workspace,
    _typed_azure_ai_route,
)

# Absolute, because every test here chdirs into a throwaway workspace that has
# no schemas/ of its own.
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "grade.schema.json"

_CORPUS = ["task-001", "task-002", "task-003"]
_CANONICAL_STEM = "exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1"
_CANONICAL_GRADE = f"data/grades/{_CANONICAL_STEM}.json"


def _grade_path(root: Path, index: int, count: int) -> Path:
    """Where step8 leaves its payload, serial or sharded.

    Shards fork below the canonical name (``_shards/<stem>/shard-i-of-n.json``)
    so that N concurrent jobs never contend for one file and so the dashboard's
    non-recursive ``data/grades/*.json`` glob cannot mistake an unfinished slice
    for a graded run.
    """
    if count <= 1:
        return root / _CANONICAL_GRADE
    return (
        root
        / "data"
        / "grades"
        / "_shards"
        / _CANONICAL_STEM
        / f"shard-{index:03d}-of-{count:03d}.json"
    )

# Fields a merged payload is *expected* to differ on. Everything else must match
# a serial run exactly.
#   shard_provenance -- merge-only provenance block (step9 docstring, section D)
#   grading_wall_time_ms -- per-task elapsed measurement; N concurrent shards
#     each keep their own timeline, so this is the one number sharding really
#     does change. Sub-ms jitter makes it differ even under a fake grader.
#   graded_at -- second-resolution wall clock. Shards finish at different
#     moments by construction, and even this harness drifts by a second when a
#     run straddles a second boundary. Its merge rule is asserted directly in
#     test_merge_takes_the_last_shard_completion_time rather than diffed here.
#   cost_ledger -- a pointer to the audit file sitting beside *this* grade, so a
#     serial run and a merged run necessarily spell the path differently. What
#     has to hold is asserted directly below: the merged grade points at a real
#     trail that matches the digest it publishes for it.
_EXPECTED_DIVERGENCE = {
    "shard_provenance",
    "grading_wall_time_ms",
    "graded_at",
    "cost_ledger",
}


def _run_grade(
    monkeypatch, root: Path, index: int = 0, count: int = 1
) -> tuple[dict, Path]:
    """Run step8 to completion in a fresh workspace; return (payload, path)."""
    root.mkdir(parents=True)
    _setup_workspace(root)
    monkeypatch.chdir(root)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    shard_flags = (
        []
        if count <= 1
        else ["--shard-index", str(index), "--shard-count", str(count)]
    )
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force", *shard_flags,
    ])
    assert s8.main() == 0
    path = _grade_path(root, index, count)
    return json.loads(path.read_text(encoding="utf-8")), path


def _strip(value):
    """Drop the fields sharding is allowed to change, recursively."""
    if isinstance(value, dict):
        return {
            key: _strip(item)
            for key, item in value.items()
            if key not in _EXPECTED_DIVERGENCE
        }
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value


@pytest.mark.parametrize("shard_count", [2, 3])
def test_sharded_run_merges_into_a_serial_identical_payload(
    monkeypatch, tmp_path, shard_count
):
    shard_files = []
    for index in range(shard_count):
        root = tmp_path / f"shard{index}" / "batch-runner"
        payload, path = _run_grade(monkeypatch, root, index, shard_count)
        assert payload["run_status"] == "partial"
        assert payload["expected_task_count"] == len(_CORPUS)
        # A shard must never land on the canonical name; that file is reserved
        # for the merged final and is what the dashboard aggregates.
        assert not (root / _CANONICAL_GRADE).exists()
        shard_files.append(str(path))

    serial, _ = _run_grade(monkeypatch, tmp_path / "serial" / "batch-runner")
    assert serial["run_status"] == "final"

    merged_path = tmp_path / "merged.json"
    assert s9.main([*shard_files, "--output", str(merged_path)]) == 0
    merged = json.loads(merged_path.read_text(encoding="utf-8"))

    assert merged["run_status"] == "final"
    assert [task["task_id"] for task in merged["tasks"]] == _CORPUS
    assert _strip(merged) == _strip(serial)

    # Stripped from the diff above, so pin it here instead: the merged grade
    # must name an audit trail that actually sits beside it and still matches
    # the digest it published. A pointer to a file nobody can check is the same
    # as no pointer, and worse, because it reads like one.
    trail = merged_path.with_name(merged["cost_ledger"]["path"])
    assert trail.is_file()
    assert verify_export(trail, merged["cost_ledger"]["sha256"])

    # The exact gate the workflow's merge step applies before it will publish a
    # merged file to data/grades/. Pinning it here means a drift in either step8
    # or step9 fails a test instead of a paid 220-task run's final commit.
    validate_grade_payload(
        merged, json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    )
    assert len(merged["tasks"]) == merged["expected_task_count"]


def test_merge_records_every_shard_in_provenance(monkeypatch, tmp_path):
    """The merged artifact must be self-describing: which shards produced it,
    and whether they agreed on config. Otherwise drift is only visible in CI
    logs that expire."""
    shard_files = []
    for index in range(3):
        root = tmp_path / f"shard{index}" / "batch-runner"
        _, path = _run_grade(monkeypatch, root, index, 3)
        shard_files.append(str(path))

    merged_path = tmp_path / "merged.json"
    assert s9.main([*shard_files, "--output", str(merged_path)]) == 0
    provenance = json.loads(merged_path.read_text(encoding="utf-8"))["shard_provenance"]

    assert [entry["index"] for entry in provenance] == [0, 1, 2]
    assert {entry["count"] for entry in provenance} == {3}
    assert len({entry["config_hash"] for entry in provenance}) == 1
    assert len({entry["grade_file_sha256"] for entry in provenance}) == 3


def test_merge_refuses_an_incomplete_shard_set(monkeypatch, tmp_path):
    """Dropping a shard must fail loudly. A 220-task run that silently
    publishes 195 graded tasks as 'final' is the worst outcome this whole
    design has to prevent."""
    shard_files = []
    for index in range(3):
        root = tmp_path / f"shard{index}" / "batch-runner"
        _, path = _run_grade(monkeypatch, root, index, 3)
        shard_files.append(str(path))

    merged_path = tmp_path / "merged.json"
    assert s9.main([*shard_files[:2], "--output", str(merged_path)]) != 0
    assert not merged_path.exists()


def test_merge_takes_the_last_shard_completion_time(monkeypatch, tmp_path):
    """`graded_at` on the merged payload is the moment the run actually
    finished -- i.e. the slowest shard -- not whichever file was listed first.
    Per-task timestamps stay exactly as the grading shard recorded them."""
    shard_files = []
    per_task_graded_at = {}
    for index in range(3):
        root = tmp_path / f"shard{index}" / "batch-runner"
        payload, path = _run_grade(monkeypatch, root, index, 3)
        for task in payload["tasks"]:
            per_task_graded_at[task["task_id"]] = task["graded_at"]
        shard_files.append((payload["graded_at"], str(path)))

    merged_path = tmp_path / "merged.json"
    # Reversed on purpose: command-line order must not influence the result.
    assert s9.main(
        [path for _, path in reversed(shard_files)] + ["--output", str(merged_path)]
    ) == 0
    merged = json.loads(merged_path.read_text(encoding="utf-8"))

    assert merged["graded_at"] == max(stamp for stamp, _ in shard_files)
    assert {
        task["task_id"]: task["graded_at"] for task in merged["tasks"]
    } == per_task_graded_at
