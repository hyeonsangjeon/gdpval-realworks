"""The fixed 220 the records agree on is the benchmark's own list.

:mod:`scripts.roll_up_round` refuses to combine run records that describe
different task lists, comparing position and id across every record it is
given. That check is real, and it is also circular on its own: three records
built from one dispatch inherit whatever list that dispatch used, so they would
agree just as firmly about a list nobody sanctioned. "All our records match"
says the round is internally consistent, not that it measured the benchmark.

This file closes that loop by anchoring the list outside the records:

    openai/gdpval @ 11e7900c…  (revision and file digest recorded in the catalog)
        -> experiments/execution_envelope/gdpval_task_catalog.json   220 tasks
        -> exp035's data.filter.task_ids                             220 tasks
        -> every committed exp035 run record's outcomes.json         220 rows

Order is compared, not just membership. Every report of this round counts by
position -- "tasks 59 to 102" -- so two lists holding the same ids in a
different order are two different benchmarks wearing the same name, and the
positional claims in three ``report.md`` files would silently move.

Sector and occupation come along for the same reason. A record can hold the
right ids and still label them wrong, and a mislabelled row survives every
id-based check while making the per-sector reading of the round false.

The YAML pins all 220 ids literally, under a comment saying they are the
catalog's ids sorted. That comment is the claim this file turns into a check,
because the list is edited by hand and nothing else recomputes it.

Offline: reads committed YAML and JSON. No network, no provider, no model call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER = Path(__file__).resolve().parents[1]
CATALOG = BATCH_RUNNER / "experiments" / "execution_envelope" / "gdpval_task_catalog.json"
EXPERIMENT = BATCH_RUNNER / "experiments" / "exp035_codex_foundry_full220.yaml"
RECORDS = BATCH_RUNNER / "docs" / "run_records"

#: The upstream this round is measuring. Pinned so that a catalog rebuilt
#: against a different dataset revision cannot pass as the same benchmark.
UPSTREAM_REPO = "openai/gdpval"
UPSTREAM_REVISION = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
UPSTREAM_FILE_SHA256 = (
    "f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202"
)
TASK_COUNT = 220


@pytest.fixture(scope="module")
def catalog() -> dict:
    return json.loads(CATALOG.read_text())


@pytest.fixture(scope="module")
def catalog_ids(catalog: dict) -> list[str]:
    return [row["task_id"] for row in catalog["tasks"]]


@pytest.fixture(scope="module")
def pinned_ids() -> list[str]:
    document = yaml.safe_load(EXPERIMENT.read_text())
    return list(document["data"]["filter"]["task_ids"])


def _record_directories() -> list[Path]:
    """Every committed exp035 run record, oldest-named first.

    Scoped to exp035 deliberately: a later experiment may pin a different
    subset, and this file is about one round's list, not about every list the
    repository will ever hold.
    """
    return sorted(
        directory
        for directory in RECORDS.glob("exp035_*")
        if (directory / "outcomes.json").is_file()
    )


def test_there_are_records_to_check() -> None:
    """A glob that matches nothing would let every check below pass vacuously."""
    assert _record_directories(), f"no exp035 run record under {RECORDS}"


def test_the_catalog_names_the_upstream_it_was_built_from(catalog: dict) -> None:
    assert catalog["dataset_repo_id"] == UPSTREAM_REPO
    assert catalog["dataset_revision"] == UPSTREAM_REVISION
    assert catalog["dataset_file_sha256"] == UPSTREAM_FILE_SHA256
    assert len(catalog["tasks"]) == TASK_COUNT


def test_the_catalog_carries_no_answers(catalog: dict) -> None:
    """It is committed, so it must hold task metadata and no gold content.

    The one field a scoring artefact would need is the expert deliverable
    itself; the catalog records the file *extensions* and a digest of the
    prompt instead. If a rubric or answer ever lands here, grading could read
    the answer key out of the repository.
    """
    assert catalog["holds_no_scores"]
    forbidden = {
        "deliverable_files",
        "reference_files",
        "prompt",
        "rubric",
        "rubric_items",
        "answer",
        "grade",
        "score",
    }
    for row in catalog["tasks"]:
        assert not forbidden & set(row), f"{row['task_id']} holds {forbidden & set(row)}"


def test_the_experiment_pins_the_catalogs_ids_in_sorted_order(
    pinned_ids: list[str], catalog_ids: list[str]
) -> None:
    """The YAML says "every task id in the catalog, sorted". Check both halves."""
    assert len(pinned_ids) == TASK_COUNT
    assert len(set(pinned_ids)) == TASK_COUNT, "the pinned list repeats an id"
    assert set(pinned_ids) == set(catalog_ids)
    assert pinned_ids == sorted(pinned_ids), "the pinned list is not sorted"


@pytest.mark.parametrize(
    "directory", _record_directories(), ids=lambda p: p.name
)
def test_each_run_record_holds_that_same_list_in_that_same_order(
    directory: Path, pinned_ids: list[str]
) -> None:
    rows = json.loads((directory / "outcomes.json").read_text())
    assert len(rows) == TASK_COUNT

    positions = [row["n"] for row in rows]
    assert positions == list(range(1, TASK_COUNT + 1)), (
        f"{directory.name} does not number its rows 1..{TASK_COUNT}; the "
        "positional claims in its report cannot be trusted"
    )

    ids = [row["task_id"] for row in rows]
    assert ids == pinned_ids, (
        f"{directory.name} describes a different fixed list from the one "
        "exp035 dispatched"
    )


@pytest.mark.parametrize(
    "directory", _record_directories(), ids=lambda p: p.name
)
def test_each_run_record_labels_those_tasks_the_way_the_catalog_does(
    directory: Path, catalog: dict
) -> None:
    """Right ids, wrong labels still breaks every per-sector reading."""
    expected = {row["task_id"]: row for row in catalog["tasks"]}
    rows = json.loads((directory / "outcomes.json").read_text())
    wrong = [
        {
            "task_id": row["task_id"],
            "record_sector": row.get("sector"),
            "catalog_sector": expected[row["task_id"]]["sector"],
            "record_occupation": row.get("occupation"),
            "catalog_occupation": expected[row["task_id"]]["occupation"],
        }
        for row in rows
        if row.get("sector") != expected[row["task_id"]]["sector"]
        or row.get("occupation") != expected[row["task_id"]]["occupation"]
    ]
    assert not wrong, f"{directory.name} mislabels {len(wrong)} task(s): {wrong[:2]}"


def test_every_record_agrees_with_every_other_one() -> None:
    """The property the roll-up relies on, stated where it can be seen fail.

    ``roll_up_round`` raises ``RollUpRefused`` on a mismatch, which is the
    right runtime behaviour and a poor signal at rest: it only fires when
    somebody rolls up. Asserting it here means a record that drifts is caught
    by the suite rather than by the next round-state build.
    """
    directories = _record_directories()
    lists = {
        directory.name: [
            row["task_id"]
            for row in json.loads((directory / "outcomes.json").read_text())
        ]
        for directory in directories
    }
    first, reference = next(iter(lists.items()))
    for name, ids in lists.items():
        assert ids == reference, f"{name} and {first} hold different task lists"
