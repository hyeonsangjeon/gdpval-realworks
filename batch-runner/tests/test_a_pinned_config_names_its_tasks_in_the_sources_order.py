"""A pinned grading config must name its tasks in its own source's order.

`rerun_identity.task_ids` is an ordered list, not a set. `step8_grade.py`'s
`filter_tasks_for_config` rebuilds the pinned selection from the source and
refuses the config when the two orders differ:

    if canonical_pinned_ids != pinned_ids:
        raise ValueError(
            "config pinned task selection must follow canonical source order"
        )

That guard runs before any judge call, so a wrong order already fails without
spending anything on grading. What it does not do is fail cheaply: it fails
inside a dispatched workflow, after checkout, setup and download, and burning a
dispatch plus its wall-clock is expensive while a relay is holding the
schedule. This sweep moves the same failure to test time, where it costs
nothing at all.

The order it rebuilds is the order of the rows the experiment actually
uploaded, and that is not one fixed order for every experiment.
`filter_tasks` walks `inference_results["results"]` and keeps the members of
the pinned set; `download_inference_from_hf.py` builds that array from the
uploaded parquet row by row. So the reference is the uploaded parquet, and
`fill_parquet.py`'s compact branch writes it two different ways:

    if selected_task_ids is not None:
        df = parquet_index.loc[selected_task_ids].reset_index(drop=True)   # reorders
    else:
        df = df[df["task_id"].isin(filled_task_ids)]                       # keeps row order

An experiment that pins `data.filter.task_ids` takes the first path —
`step1_prepare_tasks.py` carries the YAML order verbatim into
`task_scope.task_ids`, `step4_fill_parquet.py` passes it through as
`selected_task_ids`, and `.loc[...]` reorders the frame to match it. An
experiment that pins nothing takes the second path, where a boolean mask leaves
the base parquet's own row order intact. Both were measured, not inferred: the
step-4 output parquets kept in the exp033 and exp034 run artifacts each come
back in their own prepared order (`23ede7c5...` for exp033's five,
`82f1d83c...` for exp034's thirty), not in base order.

So the rule is per-experiment, and this file resolves it per-experiment via
`rerun_identity.experiment_id`. Getting that wrong is expensive in both
directions. All four experiments that pin ids today — exp027, exp033, exp034
and exp035 — pin them out of base order, so holding their grading configs to
the base order would reject the only pin that can actually work. exp035 is the
sharpest case: it pins the same 220 ids as the base corpus, as the same set,
with no duplicates, differing from index 0 onward. Copied either way round the
file looks completely correct.
"""

from pathlib import Path

import pytest
import yaml

from core.inference_manifest import _ordered_task_ids_sha256
from core.repo_bootstrapper import CANONICAL_ORDERED_TASK_IDS_SHA256

BATCH_ROOT = Path(__file__).resolve().parents[1]
GRADING_CONFIGS = BATCH_ROOT / "grading_configs"
EXPERIMENTS = BATCH_ROOT / "experiments"

# The committed full-220 config doubles as this file's base-order reference.
# Every test that falls back to it first proves it still hashes to the
# bootstrapper's constant, so a drifted reference fails loudly instead of
# silently redefining "the source's order".
BASE_ORDER_REFERENCE = "regrade_exp003_v2_sol_max_score_excluded.yaml"

EXPECTED_SOURCE_TASK_COUNT = 220

# Every experiment whose YAML pins an explicit task list, and therefore uploads
# a parquet in that list's order rather than the base corpus order.
EXPERIMENTS_THAT_PIN_IDS = (
    "exp027_GPT54_default_subprocess_bridge50",
    "exp033_codex_foundry_fixed5",
    "exp034_codex_foundry_trial30",
    "exp035_codex_foundry_full220",
)


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


def _config_experiment_id(config_name: str) -> str | None:
    data = yaml.safe_load((GRADING_CONFIGS / config_name).read_text(encoding="utf-8"))
    identity = data.get("rerun_identity")
    if not isinstance(identity, dict):
        return None
    return identity.get("experiment_id")


def _base_order() -> list[str]:
    task_ids = _pinned_task_ids(BASE_ORDER_REFERENCE)
    assert task_ids is not None, (
        f"{BASE_ORDER_REFERENCE} no longer pins task_ids, so this file has lost "
        "its base-order reference. Point BASE_ORDER_REFERENCE at another "
        "committed config whose task_ids hash to "
        f"{CANONICAL_ORDERED_TASK_IDS_SHA256}."
    )
    assert _ordered_task_ids_sha256(task_ids) == CANONICAL_ORDERED_TASK_IDS_SHA256, (
        f"{BASE_ORDER_REFERENCE} no longer matches the source parquet's row "
        "order, so it cannot define the fallback order for the other configs."
    )
    return task_ids


def _experiment_pinned_ids(experiment_id: str) -> list[str] | None:
    """The task list an experiment YAML pins, or None when it pins nothing.

    Resolved by declared id rather than filename, because that is the only
    thing a grading config records. Two YAMLs claiming one id would make the
    resolution ambiguous, so that fails rather than picking one.
    """
    matches: list[tuple[str, list[str] | None]] = []
    for path in sorted(EXPERIMENTS.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        experiment = data.get("experiment")
        declared = experiment.get("id") if isinstance(experiment, dict) else None
        if declared != experiment_id:
            continue
        data_block = data.get("data")
        filters = data_block.get("filter") if isinstance(data_block, dict) else None
        pinned = filters.get("task_ids") if isinstance(filters, dict) else None
        matches.append((path.name, pinned))

    assert len(matches) <= 1, (
        f"{experiment_id} is declared by more than one experiment YAML "
        f"({[name for name, _ in matches]}), so a grading config naming it "
        "cannot be resolved to one upload order."
    )
    if not matches:
        return None
    return matches[0][1]


def _order_reference(config_name: str) -> tuple[list[str], str]:
    """The order this config's pin must follow, and where that order comes from.

    An experiment that pins ids uploads them in its own order; anything else
    uploads the base corpus in row order. An experiment_id with no YAML falls
    back to the base order, which is what every config in the repository today
    resolves to.
    """
    experiment_id = _config_experiment_id(config_name)
    if experiment_id is not None:
        pinned = _experiment_pinned_ids(experiment_id)
        if pinned:
            return pinned, f"experiments/{experiment_id}.yaml (data.filter.task_ids)"
    return _base_order(), f"the source parquet row order ({BASE_ORDER_REFERENCE})"


def test_the_default_order_reference_is_the_sources_own_row_order() -> None:
    """The fallback reference must still be the parquet order, not merely a list.

    `repo_bootstrapper` raises when the concatenated source shards do not hash
    to this constant, so matching it means matching the row order the grader,
    the sharder and the report position labels all count from.
    """
    order = _base_order()
    assert len(order) == EXPECTED_SOURCE_TASK_COUNT
    assert len(set(order)) == EXPECTED_SOURCE_TASK_COUNT


@pytest.mark.parametrize("experiment_id", EXPERIMENTS_THAT_PIN_IDS)
def test_an_experiment_that_pins_ids_does_not_pin_them_in_base_order(
    experiment_id: str,
) -> None:
    """The per-experiment rule exists because no pinning experiment uses base order.

    Each of these pins a strict subset of the fixed corpus with no duplicates,
    and none of them walks it in row order. Holding their grading configs to
    the base order would therefore reject the pin that actually matches what
    step 4 uploads, which is the opposite of what the guard is for.
    """
    pinned = _experiment_pinned_ids(experiment_id)
    assert pinned, f"{experiment_id} no longer pins data.filter.task_ids"

    base = _base_order()
    position = {task_id: index for index, task_id in enumerate(base)}

    assert len(set(pinned)) == len(pinned), f"{experiment_id} pins a duplicate id"
    unknown = [task_id for task_id in pinned if task_id not in position]
    assert not unknown, (
        f"{experiment_id} pins {len(unknown)} id(s) outside the fixed "
        f"{EXPECTED_SOURCE_TASK_COUNT}-task source: {unknown[:3]}"
    )

    positions = [position[task_id] for task_id in pinned]
    ascending = all(
        positions[index] > positions[index - 1] for index in range(1, len(positions))
    )
    assert not ascending, (
        f"{experiment_id} now pins its ids in base row order. If that is "
        "deliberate, the two orders have converged and this test should be "
        "narrowed rather than deleted — the per-experiment resolution below "
        "still has to hold for the experiments that have not converged."
    )


def test_the_order_reference_follows_the_experiment_a_config_names() -> None:
    """Resolution reaches the pinning branch, which no shipped config exercises yet.

    Every `rerun_identity` in the repository today names an experiment that
    pins nothing, so the branch that matters for exp035 would otherwise be
    unexercised until the config that depends on it lands. This calls the
    resolver directly instead.
    """
    pinned = _experiment_pinned_ids("exp035_codex_foundry_full220")
    assert pinned is not None
    assert len(pinned) == EXPECTED_SOURCE_TASK_COUNT
    assert set(pinned) == set(_base_order()), (
        "exp035 is expected to run the same fixed corpus, only in another order"
    )
    assert pinned != _base_order(), (
        "exp035's order has converged with the base order; the resolution rule "
        "is unchanged but this file's worked example no longer demonstrates it"
    )


@pytest.mark.parametrize(
    "config_name",
    sorted(p.name for p in GRADING_CONFIGS.glob("*.yaml")),
)
def test_a_pinned_config_follows_its_own_experiments_order(config_name: str) -> None:
    """Every pinned list is an ordered subsequence of what its experiment uploads.

    A config may pin any subset — the anchor and cohort configs pin 3, 4 and 10
    tasks, the ceiling configs pin 30 and 185 — but it may not reorder them.
    `filter_tasks` rebuilds the selection by walking the uploaded rows in order
    and keeping the pinned ones, so anything but a strictly increasing
    subsequence of that order is rejected.
    """
    task_ids = _pinned_task_ids(config_name)
    if task_ids is None:
        pytest.skip(f"{config_name} does not pin task_ids")

    reference, source = _order_reference(config_name)
    position = {task_id: index for index, task_id in enumerate(reference)}

    unknown = [task_id for task_id in task_ids if task_id not in position]
    assert not unknown, (
        f"{config_name} pins {len(unknown)} task id(s) that {source} does not "
        f"contain: {unknown[:3]}"
    )

    positions = [position[task_id] for task_id in task_ids]
    out_of_order = [
        (index, task_ids[index])
        for index in range(1, len(positions))
        if positions[index] <= positions[index - 1]
    ]
    assert not out_of_order, (
        f"{config_name} pins task ids out of the order of {source}, first at "
        f"index {out_of_order[0][0]} ({out_of_order[0][1]}). step8_grade rejects "
        "this in the dispatched run. Take the list from the experiment this "
        "config names, not from another config that grades a different "
        "experiment — the same 220 ids sit in different orders in each."
    )


@pytest.mark.parametrize(
    "config_name",
    sorted(p.name for p in GRADING_CONFIGS.glob("*.yaml")),
)
def test_a_full_length_pin_matches_its_experiments_digest_exactly(
    config_name: str,
) -> None:
    """A config pinning the whole corpus must hash to its own source's digest.

    The subsequence check above already forbids a reordering, but a full-length
    pin can be compared against a digest directly. For a config whose
    experiment pins nothing that digest is the bootstrapper's constant, which
    is the same comparison `repo_bootstrapper` makes against the parquet
    itself; for one whose experiment pins its own order it is the digest of
    that order.
    """
    task_ids = _pinned_task_ids(config_name)
    if task_ids is None or len(task_ids) != EXPECTED_SOURCE_TASK_COUNT:
        pytest.skip(f"{config_name} does not pin the full source")

    reference, source = _order_reference(config_name)
    expected = _ordered_task_ids_sha256(reference)
    digest = _ordered_task_ids_sha256(task_ids)
    assert digest == expected, (
        f"{config_name} pins {EXPECTED_SOURCE_TASK_COUNT} task ids that hash to "
        f"{digest}, not the {expected} of {source}."
    )
