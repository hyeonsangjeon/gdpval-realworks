"""Can a catalogue say the work is smaller than it is and be believed?

The task catalogue is where the cost ceiling gets its numbers. How many scoring
lines a task is marked against, how long its wording is, how many reference
files it ships with — every dollar in the ceiling is worked out from those three
columns of the benchmark dataset.

The builder used to read four of those columns like this::

    rubric_json = row.get("rubric_json")
    try:
        rubric_items = json.loads(rubric_json) if rubric_json else []
    except (TypeError, ValueError):
        rubric_items = []

A column renamed upstream, or arriving empty, or holding text that will not
parse, became an empty list. An empty list became a count of zero. And a count
of zero is not carried onward as *unknown*: it is carried as a real, small
measurement, which is precisely the thing nothing complains about.

The measurement that made this worth doing: set every ``rubric_item_count`` in
the committed catalogue to zero and the ceiling for the planned comparison falls
from **364.00 to 94.16 United States dollars** — 269.84 of it gone, about three
quarters — because marking is charged per scoring line and a task with no
scoring lines is marked for free. Four things had a chance to notice and none
did. The loader takes any whole number. The no-scores check is asked a different
question and answers it correctly. Its test suite states outright that a zero is
fine. And ``--check`` rebuilds with the same code, so it reproduces the same
zeros and reports a match.

This is the mirror image of the reference-file work next door. That one was an
over-charge, which is the safe direction. This one is an under-charge with no
guard at all, which the plan's own comment calls the exact mistake the file
exists to prevent.

So the tests here do two things. They break the dataset in each of the ways a
column really goes wrong and require the builder to stop rather than write a
zero, and they take the committed catalogue, zero the counts by hand, and
require the free check to refuse it.
"""

from __future__ import annotations

import json
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from scripts import build_gdpval_task_catalog as builder  # noqa: E402

from core.execution_envelope_cost import (  # noqa: E402
    CostAssumptions,
    estimate_cost_ceiling,
)
from core.execution_envelope_preflight import (  # noqa: E402
    conditions_from_plan,
    load_plan,
    run_envelope_preflight,
)
from core.execution_envelope_tasks import (  # noqa: E402
    CATALOG_PATH,
    SHA256_OF_NOTHING,
    TaskCatalog,
    _TASKS_NAMED_IN_A_REFUSAL,
    catalog_number_problems,
    load_task_catalog,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)


# ── Building a dataset file to break ───────────────────────────────────────


def _dataset_rows(count: int = 3) -> dict[str, list]:
    """A dataset shaped like the real one, small enough to reason about."""
    return {
        "task_id": [f"task-{index}" for index in range(count)],
        "sector": ["Health Care and Social Assistance"] * count,
        "occupation": [f"Job {index}" for index in range(count)],
        "prompt": [f"Please do the work described here, number {index}." for index in range(count)],
        "reference_files": [
            [f"reference_files/{'a' * 32}/input-{index}.xlsx"] for index in range(count)
        ],
        "deliverable_files": [[f"deliverable_files/answer-{index}.xlsx"] for index in range(count)],
        "rubric_json": [
            json.dumps([{"criterion": "does the thing", "score": 2}] * (index + 3))
            for index in range(count)
        ],
        "rubric_pretty": ["1. does the thing"] * count,
    }


def _write_parquet(tmp_path: Path, columns: dict[str, list], name: str = "train.parquet") -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    target = tmp_path / name
    pq.write_table(pa.table(columns), target)
    return target


def _catalogue() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _loaded(payload: dict) -> TaskCatalog:
    return TaskCatalog.from_mapping(payload)


# ── The committed file, and the dataset it came from ───────────────────────


def test_the_committed_catalogue_passes():
    assert catalog_number_problems(load_task_catalog()) == []


def test_the_committed_catalogue_is_the_reason_each_rule_is_shaped_as_it_is():
    """The facts the refusals are argued from, read from the file itself.

    Each rule below refuses a zero, or declines to, on the strength of what
    this benchmark really contains. If that ever stops being true the rules
    need rewriting, and this is where that shows up.
    """
    tasks = load_task_catalog().tasks

    rubric = [task.rubric_item_count for task in tasks]
    assert min(rubric) > 0, "a task with no scoring lines would make the rubric rule wrong"

    wording = [task.prompt_character_count for task in tasks]
    assert min(wording) > 0, "a task with no wording would make the wording rule wrong"

    references = [task.reference_file_count for task in tasks]
    assert min(references) == 0, (
        "no task ships zero reference files, so refusing that zero would have "
        "been reasonable after all — the third rule exists because this is not "
        "the case"
    )
    assert sum(1 for value in references if value == 0) > 50, (
        "shipping no reference files has to be ordinary, not a rarity, for "
        "declining to refuse it to be the right call"
    )


def test_the_builder_still_reproduces_the_committed_catalogue_exactly():
    """The rewritten builder must write the same bytes as the old one.

    This is the whole regression test for the builder change, and it needs the
    real dataset file to say anything, so it is skipped where that file is not
    already on the machine. Nothing is downloaded.
    """
    parquet = builder.HUGGING_FACE_CACHE_PARQUET
    if not parquet.is_file():
        pytest.skip("the pinned dataset file is not on this machine")

    rebuilt = builder.render(builder.build_catalog(parquet))
    assert rebuilt == CATALOG_PATH.read_text(encoding="utf-8")


# ── What a zero really costs ───────────────────────────────────────────────


def _ceiling_usd(catalog: TaskCatalog) -> Decimal:
    plan = load_plan(PLAN_PATH)
    cost_block = plan.get("cost") or {}
    ceiling = estimate_cost_ceiling(
        conditions_by_environment=conditions_from_plan(plan),
        tasks_by_id=catalog.by_task_id(),
        assumptions=CostAssumptions.from_mapping(cost_block.get("assumptions") or {}),
    )
    return ceiling.total_usd


def _as_money(value: Decimal) -> str:
    """Rounded the way this repository reports money: up, to the cent."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def test_zeroing_the_scoring_lines_takes_three_quarters_off_the_ceiling():
    """The figure quoted in the docstrings, measured rather than remembered.

    Both the exact money and the proportion are held here. The money is what
    the docstrings claim and is pure arithmetic, so it says the same thing on
    every machine; the proportion is what the claim *means*, and survives an
    assumption being revised.
    """
    real = _ceiling_usd(load_task_catalog())

    payload = _catalogue()
    for task in payload["tasks"]:
        task["rubric_item_count"] = 0
    zeroed = _ceiling_usd(_loaded(payload))

    assert _as_money(real) == "364.00"
    assert _as_money(zeroed) == "94.16"

    lost = real - zeroed
    assert lost > real * Decimal("0.7"), (
        f"the marking half should be most of the ceiling; {real} fell to "
        f"{zeroed}"
    )


def test_nothing_else_in_the_advance_check_notices_a_zeroed_rubric():
    """Every other guard, asked about the same broken file, reports it clean.

    Not a criticism of any of them — each is answering the question it was
    written to answer. It is the reason a new rule was needed rather than a
    tightening of an old one.
    """
    from core.execution_envelope_tasks import catalog_score_problems

    payload = _catalogue()
    for task in payload["tasks"]:
        task["rubric_item_count"] = 0

    assert catalog_score_problems(payload) == [], (
        "the no-scores check reports this clean, correctly — a zero is a "
        "whole number and carries no result"
    )
    # It still loads, still holds 220 tasks, still selects the same five.
    loaded = _loaded(payload)
    assert len(loaded.tasks) == 220
    from core.execution_envelope_tasks import select_advance_check_tasks

    assert (
        select_advance_check_tasks(loaded, catalog_fingerprint="x").task_ids
        == select_advance_check_tasks(
            load_task_catalog(), catalog_fingerprint="x"
        ).task_ids
    )

    # And the new rule is the one that speaks up.
    assert catalog_number_problems(loaded) != []


# ── Rule one: a task nobody marks ──────────────────────────────────────────


def test_a_task_with_no_scoring_lines_is_refused():
    payload = _catalogue()
    payload["tasks"][0]["rubric_item_count"] = 0
    problems = catalog_number_problems(_loaded(payload))
    assert len(problems) == 1
    assert "no marking rubric" in problems[0]
    assert payload["tasks"][0]["task_id"] in problems[0]


def test_a_negative_number_of_scoring_lines_is_refused():
    payload = _catalogue()
    payload["tasks"][0]["rubric_item_count"] = -3
    assert len(catalog_number_problems(_loaded(payload))) == 1


def test_every_task_zeroed_is_still_one_refusal_naming_a_few():
    """A refusal listing 220 task numbers does not get read."""
    payload = _catalogue()
    for task in payload["tasks"]:
        task["rubric_item_count"] = 0
    problems = catalog_number_problems(_loaded(payload))
    assert len(problems) == 1
    named = sum(
        1 for task in payload["tasks"] if task["task_id"] in problems[0]
    )
    assert named == _TASKS_NAMED_IN_A_REFUSAL
    assert f"and {220 - _TASKS_NAMED_IN_A_REFUSAL} more" in problems[0]


# ── Rule two: a task with no wording ───────────────────────────────────────


def test_a_task_with_no_wording_is_refused():
    payload = _catalogue()
    payload["tasks"][2]["prompt_character_count"] = 0
    problems = catalog_number_problems(_loaded(payload))
    assert len(problems) == 1
    assert "no wording" in problems[0]
    assert payload["tasks"][2]["task_id"] in problems[0]


def test_a_wording_fingerprint_of_nothing_is_refused_even_with_a_length_beside_it():
    """Catches a length corrected by hand without the fingerprint going with it."""
    payload = _catalogue()
    payload["tasks"][2]["prompt_sha256"] = SHA256_OF_NOTHING
    assert payload["tasks"][2]["prompt_character_count"] > 0
    problems = catalog_number_problems(_loaded(payload))
    assert len(problems) == 1
    assert payload["tasks"][2]["task_id"] in problems[0]


def test_the_fingerprint_of_nothing_is_worked_out_rather_than_typed():
    """A single wrong character would switch the rule off in silence."""
    import hashlib
    import inspect

    from core import execution_envelope_tasks

    assert SHA256_OF_NOTHING == hashlib.sha256(b"").hexdigest()
    source = inspect.getsource(execution_envelope_tasks)
    assert f'"{SHA256_OF_NOTHING}"' not in source
    assert "SHA256_OF_NOTHING = hashlib.sha256(b\"\").hexdigest()" in source


# ── Rule three: the count and the paths disagreeing ────────────────────────


def test_shipping_no_reference_files_is_ordinary_and_is_not_refused():
    """95 of the 220 tasks really ship none. Refusing that zero would be wrong."""
    payload = _catalogue()
    payload["tasks"][0]["reference_file_count"] = 0
    payload["tasks"][0]["reference_file_paths"] = []
    payload["tasks"][0]["reference_file_extensions"] = []
    assert catalog_number_problems(_loaded(payload)) == []


def test_a_count_of_no_reference_files_beside_a_list_of_them_is_refused():
    """The one guard the reference column can have, since its zero is ordinary."""
    payload = _catalogue()
    task = next(entry for entry in payload["tasks"] if entry["reference_file_count"] > 0)
    task["reference_file_count"] = 0
    problems = catalog_number_problems(_loaded(payload))
    assert len(problems) == 1
    assert "counts a different number of reference files" in problems[0]
    assert task["task_id"] in problems[0]


def test_a_count_larger_than_the_list_is_refused_too():
    """Overstating is not a defect worth stopping a run for, but it is a lie."""
    payload = _catalogue()
    payload["tasks"][0]["reference_file_count"] = 99
    assert len(catalog_number_problems(_loaded(payload))) == 1


# ── All three at once ──────────────────────────────────────────────────────


def test_every_kind_of_problem_is_reported_together():
    payload = _catalogue()
    payload["tasks"][0]["rubric_item_count"] = 0
    payload["tasks"][1]["prompt_character_count"] = 0
    payload["tasks"][2]["reference_file_count"] = 99
    problems = catalog_number_problems(_loaded(payload))
    assert len(problems) == 3
    assert any("no marking rubric" in note for note in problems)
    assert any("no wording" in note for note in problems)
    assert any("counts a different number" in note for note in problems)


def test_a_refusal_says_what_it_costs_rather_than_only_that_it_refused():
    """A person reading this has to be able to tell why it matters."""
    payload = _catalogue()
    payload["tasks"][0]["rubric_item_count"] = 0
    note = catalog_number_problems(_loaded(payload))[0]
    assert "charged per scoring line" in note
    assert "cost ceiling" in note


# ── The builder: a column that is not there ────────────────────────────────


def test_the_builder_refuses_a_dataset_missing_the_rubric_column(tmp_path):
    columns = _dataset_rows()
    columns["marking_rubric"] = columns.pop("rubric_json")
    parquet = _write_parquet(tmp_path, columns)

    with pytest.raises(ValueError) as caught:
        builder.build_catalog(parquet)
    assert "rubric_json" in str(caught.value)


def test_the_refusal_names_the_columns_the_file_does_hold(tmp_path):
    """So whoever hits this can see the rename rather than guess at it."""
    columns = _dataset_rows()
    columns["marking_rubric"] = columns.pop("rubric_json")
    parquet = _write_parquet(tmp_path, columns)

    with pytest.raises(ValueError) as caught:
        builder.build_catalog(parquet)
    assert "marking_rubric" in str(caught.value)


@pytest.mark.parametrize("column", builder.COLUMNS_THE_CATALOGUE_IS_BUILT_FROM)
def test_the_builder_refuses_a_dataset_missing_any_column_it_reads(tmp_path, column):
    columns = _dataset_rows()
    columns.pop(column)
    parquet = _write_parquet(tmp_path, columns, name=f"{column}.parquet")

    with pytest.raises(ValueError) as caught:
        builder.build_catalog(parquet)
    assert column in str(caught.value)


def test_the_columns_the_builder_reads_are_all_in_the_real_dataset():
    """Guard the list above: a name typed wrong would refuse every build."""
    parquet = builder.HUGGING_FACE_CACHE_PARQUET
    if not parquet.is_file():
        pytest.skip("the pinned dataset file is not on this machine")

    import pyarrow.parquet as pq

    assert builder.missing_columns(pq.read_schema(parquet).names) == []


def test_a_column_the_builder_does_not_read_is_not_required(tmp_path):
    """The dataset ships columns this catalogue has no use for; that is fine."""
    columns = _dataset_rows()
    columns.pop("rubric_pretty")
    parquet = _write_parquet(tmp_path, columns)
    assert len(builder.build_catalog(parquet)["tasks"]) == 3


# ── The builder: a value that is not there ─────────────────────────────────


def test_the_builder_refuses_a_row_holding_nothing_under_a_column_it_reads(tmp_path):
    columns = _dataset_rows()
    columns["reference_files"][1] = None
    parquet = _write_parquet(tmp_path, columns)

    with pytest.raises(ValueError) as caught:
        builder.build_catalog(parquet)
    assert "reference_files" in str(caught.value)
    assert "task-1" in str(caught.value)


def test_nothing_and_none_are_told_apart(tmp_path):
    """An empty list is a real answer; a null is the absence of one.

    This is the distinction the old code could not draw — ``or []`` made both
    of them the same empty list — and it is the whole difference between a task
    that ships no reference files and a column nobody could read.
    """
    columns = _dataset_rows()
    columns["reference_files"][1] = []
    parquet = _write_parquet(tmp_path, columns)

    catalog = builder.build_catalog(parquet)
    assert catalog["tasks"][1]["reference_file_count"] == 0
    assert catalog_number_problems(_loaded(catalog)) == []


# ── The builder: a value that will not parse ───────────────────────────────


def test_the_builder_refuses_a_rubric_it_cannot_read(tmp_path):
    """This used to be recorded as a task with no rubric at all."""
    columns = _dataset_rows()
    columns["rubric_json"][2] = "{not json at all"
    parquet = _write_parquet(tmp_path, columns)

    with pytest.raises(ValueError) as caught:
        builder.build_catalog(parquet)
    assert "task-2" in str(caught.value)
    assert "rubric" in str(caught.value)


def test_the_builder_refuses_an_empty_rubric_string(tmp_path):
    columns = _dataset_rows()
    columns["rubric_json"][0] = ""
    parquet = _write_parquet(tmp_path, columns)

    with pytest.raises(ValueError):
        builder.build_catalog(parquet)


def test_the_builder_refuses_a_rubric_that_is_not_a_list_of_scoring_lines(tmp_path):
    columns = _dataset_rows()
    columns["rubric_json"][0] = json.dumps({"criterion": "just the one, unwrapped"})
    parquet = _write_parquet(tmp_path, columns)

    with pytest.raises(ValueError) as caught:
        builder.build_catalog(parquet)
    assert "list of scoring lines" in str(caught.value)


def test_a_rubric_holding_no_scoring_lines_does_not_reach_disk(tmp_path, monkeypatch, capsys):
    """Parseable, a list, and empty. Refused before writing, not after."""
    columns = _dataset_rows()
    columns["rubric_json"][0] = "[]"
    parquet = _write_parquet(tmp_path, columns)

    catalog = builder.build_catalog(parquet)
    assert catalog["tasks"][0]["rubric_item_count"] == 0
    assert catalog_number_problems(_loaded(catalog)) != []


# ── The builder asks before it writes ──────────────────────────────────────


def test_the_builder_refuses_to_write_a_catalogue_the_check_would_refuse(
    monkeypatch, tmp_path, capsys
):
    payload = _catalogue()
    payload["tasks"][0]["rubric_item_count"] = 0
    monkeypatch.setattr(builder, "build_catalog", lambda parquet: payload)
    monkeypatch.setattr(builder, "_find_parquet", lambda given: Path("unused"))
    out = tmp_path / "written.json"
    monkeypatch.setattr("sys.argv", ["build", "--out", str(out)])

    assert builder.main() == 1
    assert not out.exists(), "a refused catalogue must not reach disk"
    assert "no marking rubric" in capsys.readouterr().err


def test_the_builder_reports_a_broken_dataset_rather_than_a_traceback(
    monkeypatch, tmp_path, capsys
):
    columns = _dataset_rows()
    columns.pop("prompt")
    parquet = _write_parquet(tmp_path, columns)
    out = tmp_path / "written.json"
    monkeypatch.setattr(
        "sys.argv", ["build", "--parquet", str(parquet), "--out", str(out)]
    )

    assert builder.main() == 1
    assert not out.exists()
    assert "prompt" in capsys.readouterr().err


def test_the_builder_reports_a_catalogue_it_could_not_read_back(
    monkeypatch, tmp_path, capsys
):
    """A file that will not load is not worth committing either."""
    payload = _catalogue()
    payload.pop("dataset_revision")
    monkeypatch.setattr(builder, "build_catalog", lambda parquet: payload)
    monkeypatch.setattr(builder, "_find_parquet", lambda given: Path("unused"))
    out = tmp_path / "written.json"
    monkeypatch.setattr("sys.argv", ["build", "--out", str(out)])

    assert builder.main() == 1
    assert not out.exists()
    assert "dataset_revision" in capsys.readouterr().err


def test_the_builder_still_writes_a_good_catalogue(monkeypatch, tmp_path):
    monkeypatch.setattr(builder, "build_catalog", lambda parquet: _catalogue())
    monkeypatch.setattr(builder, "_find_parquet", lambda given: Path("unused"))
    out = tmp_path / "written.json"
    monkeypatch.setattr("sys.argv", ["build", "--out", str(out)])

    assert builder.main() == 0
    assert catalog_number_problems(_loaded(json.loads(out.read_text()))) == []


def test_a_dataset_that_is_whole_builds_without_complaint(tmp_path):
    catalog = builder.build_catalog(_write_parquet(tmp_path, _dataset_rows()))
    assert [task["rubric_item_count"] for task in catalog["tasks"]] == [3, 4, 5]
    assert [task["reference_file_count"] for task in catalog["tasks"]] == [1, 1, 1]
    assert catalog_number_problems(_loaded(catalog)) == []


# ── The limit of the comparison, written down ──────────────────────────────


def test_check_cannot_catch_a_renamed_column_and_the_script_says_so(tmp_path):
    """``--check`` rebuilds with the same code, so it agrees with itself.

    This is the honest boundary. If a column were renamed and the refusals in
    ``build_catalog`` did not exist, ``--check`` would compare zeros against
    zeros and report that everything matched. It is not a defect in ``--check``
    — comparing a rebuild against a committed file is a useful thing to do —
    but the docstring has to say what it does not cover, and this fails if that
    sentence is ever removed.
    """
    assert "would report a match" in (builder.__doc__ or "")

    # And demonstrate it: with the refusals switched off, a renamed column
    # produces a catalogue that compares equal to itself.
    columns = _dataset_rows()
    columns["marking_rubric"] = columns.pop("rubric_json")
    parquet = _write_parquet(tmp_path, columns)

    with patch.object(builder, "missing_columns", return_value=[]):
        with pytest.raises((ValueError, KeyError)):
            builder.build_catalog(parquet)


# ── The rule reaches the tool that decides whether to spend ────────────────


def test_the_whole_free_check_carries_the_rule():
    """A check nothing calls protects nothing."""
    payload = _catalogue()
    for task in payload["tasks"]:
        task["rubric_item_count"] = 0

    result = run_envelope_preflight(
        load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT, catalog=_loaded(payload)
    )
    assert any("no marking rubric" in note for note in result.all_problems)
    assert result.may_start is False


def test_the_free_check_reports_exactly_what_it_would_without_this_rule():
    """The rule is dormant on the real catalogue; it must not move the report.

    Held against the same check with the rule switched off rather than against
    a problem count typed in here: how many problems the free check finds
    depends on the machine it runs on, and a fixed number would fail on a build
    server for reasons that have nothing to do with what is being checked.
    """
    plan = load_plan(PLAN_PATH)
    with_rule = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)
    with patch(
        "core.execution_envelope_preflight.catalog_number_problems",
        return_value=[],
    ):
        without_rule = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    assert with_rule.all_problems == without_rule.all_problems
    assert with_rule.may_start == without_rule.may_start
    assert with_rule.cost is not None
    assert without_rule.cost is not None
    assert with_rule.cost.total_usd == without_rule.cost.total_usd


def test_the_rule_is_asked_about_the_catalogue_in_play():
    """Not about whatever file happens to be committed.

    A check that reads a different object from the one the run will use is the
    same defect in a different place.
    """
    payload = _catalogue()
    payload["tasks"][0]["prompt_character_count"] = 0
    broken = _loaded(payload)

    result = run_envelope_preflight(
        load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT, catalog=broken
    )
    assert any("no wording" in note for note in result.all_problems)
