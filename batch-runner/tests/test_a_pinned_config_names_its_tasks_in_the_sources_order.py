"""A pinned grading config must name its tasks in the source's own order.

`rerun_identity.task_ids` is an ordered list, not a set. `step8_grade.py`'s
`filter_tasks_for_config` rebuilds the pinned selection from the source and
refuses the config when the two orders differ:

    if canonical_pinned_ids != pinned_ids:
        raise ValueError(
            "config pinned task selection must follow canonical source order"
        )

That guard runs at `step8_grade.py:2528`, which is *before* any judge call, so
a wrong order already fails without spending anything on grading. What it does
not do is fail cheaply: it fails inside a dispatched workflow, after checkout,
setup and download, and burning a dispatch plus its wall-clock is expensive
while a relay is holding the schedule. This sweep moves the same failure to
test time, where it costs nothing at all.

The canonical order is the source parquet's own row order.
`core/repo_bootstrapper.py` refuses to bootstrap unless the concatenated
shards hash to `CANONICAL_ORDERED_TASK_IDS_SHA256`, so that constant *is* the
row order and this file imports it rather than restating the literal.

The trap is live and it is not subtle in its cause, only in its appearance:
`experiments/exp035_codex_foundry_full220.yaml` pins the same 220 task ids in
a *different* order (they hash to `fa0e5d32...`). Copying that list into a
grading config produces a file that is wrong from element 0 while looking
completely correct — same count, same ids, no duplicates.
"""

from pathlib import Path

import pytest
import yaml

from core.inference_manifest import _ordered_task_ids_sha256
from core.repo_bootstrapper import CANONICAL_ORDERED_TASK_IDS_SHA256

BATCH_ROOT = Path(__file__).resolve().parents[1]
GRADING_CONFIGS = BATCH_ROOT / "grading_configs"

# The committed full-220 config doubles as this file's order reference. Every
# test below first proves it still hashes to the bootstrapper's constant, so a
# drifted reference fails loudly instead of silently redefining "canonical".
CANONICAL_ORDER_REFERENCE = "regrade_exp003_v2_sol_max_score_excluded.yaml"

EXPECTED_SOURCE_TASK_COUNT = 220


def _pinned_task_ids(config_name: str) -> list[str] | None:
    path = GRADING_CONFIGS / config_name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    identity = data.get("rerun_identity")
    if not isinstance(identity, dict):
        return None
    task_ids = identity.get("task_ids")
    if task_ids is None:
        return None
    assert isinstance(task_ids, list), f"{config_name}: task_ids must be a list"
    return task_ids


def _canonical_order() -> list[str]:
    task_ids = _pinned_task_ids(CANONICAL_ORDER_REFERENCE)
    assert task_ids is not None, (
        f"{CANONICAL_ORDER_REFERENCE} no longer pins task_ids, so this file has "
        "lost its order reference. Point CANONICAL_ORDER_REFERENCE at another "
        "committed config whose task_ids hash to "
        f"{CANONICAL_ORDERED_TASK_IDS_SHA256}."
    )
    assert _ordered_task_ids_sha256(task_ids) == CANONICAL_ORDERED_TASK_IDS_SHA256, (
        f"{CANONICAL_ORDER_REFERENCE} no longer matches the source parquet's row "
        "order, so it cannot define canonical order for the other configs."
    )
    return task_ids


def test_the_order_reference_is_the_sources_own_row_order() -> None:
    """The reference config must still be the parquet order, not merely a list.

    `repo_bootstrapper` raises when the concatenated source shards do not hash
    to this constant, so matching it means matching the row order the grader,
    the sharder and the report position labels all count from.
    """
    order = _canonical_order()
    assert len(order) == EXPECTED_SOURCE_TASK_COUNT
    assert len(set(order)) == EXPECTED_SOURCE_TASK_COUNT


@pytest.mark.parametrize(
    "config_name",
    sorted(p.name for p in GRADING_CONFIGS.glob("*.yaml")),
)
def test_a_pinned_config_follows_the_sources_order(config_name: str) -> None:
    """Every pinned list is an ordered subsequence of the canonical 220.

    A config may pin any subset — the anchor and cohort configs pin 3, 4 and 10
    tasks, the ceiling configs pin 30 and 185 — but it may not reorder them.
    `filter_tasks_for_config` rebuilds the selection by walking the source in
    row order, so anything but a strictly increasing subsequence is rejected.
    """
    task_ids = _pinned_task_ids(config_name)
    if task_ids is None:
        pytest.skip(f"{config_name} does not pin task_ids")

    canonical = _canonical_order()
    position = {task_id: index for index, task_id in enumerate(canonical)}

    unknown = [task_id for task_id in task_ids if task_id not in position]
    assert not unknown, (
        f"{config_name} pins {len(unknown)} task id(s) that are not in the fixed "
        f"{EXPECTED_SOURCE_TASK_COUNT}-task source: {unknown[:3]}"
    )

    positions = [position[task_id] for task_id in task_ids]
    out_of_order = [
        (index, task_ids[index])
        for index in range(1, len(positions))
        if positions[index] <= positions[index - 1]
    ]
    assert not out_of_order, (
        f"{config_name} pins task ids out of canonical source order, first at "
        f"index {out_of_order[0][0]} ({out_of_order[0][1]}). step8_grade rejects "
        "this in the dispatched run; reorder the list to follow the source. Note "
        "that experiments/exp035_codex_foundry_full220.yaml holds the same 220 "
        "ids in a different order — do not copy a task list from an experiment "
        "YAML into a grading config."
    )


@pytest.mark.parametrize(
    "config_name",
    sorted(p.name for p in GRADING_CONFIGS.glob("*.yaml")),
)
def test_a_full_length_pin_matches_the_canonical_digest_exactly(
    config_name: str,
) -> None:
    """A config pinning all 220 must hash to the constant, not merely contain them.

    The subsequence check above already forbids a reordering, but a full-length
    pin can be compared against the bootstrapper's digest directly, which is the
    same comparison `repo_bootstrapper` makes against the parquet itself.
    """
    task_ids = _pinned_task_ids(config_name)
    if task_ids is None or len(task_ids) != EXPECTED_SOURCE_TASK_COUNT:
        pytest.skip(f"{config_name} does not pin the full source")

    digest = _ordered_task_ids_sha256(task_ids)
    assert digest == CANONICAL_ORDERED_TASK_IDS_SHA256, (
        f"{config_name} pins {EXPECTED_SOURCE_TASK_COUNT} task ids that hash to "
        f"{digest}, not the source's {CANONICAL_ORDERED_TASK_IDS_SHA256}."
    )
