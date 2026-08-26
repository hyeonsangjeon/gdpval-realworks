"""Does the "this file holds no scores" check actually catch a score?

The run-place comparison only means anything if the five tasks were chosen
before anybody saw a result. The evidence offered for that is a committed
catalogue of every benchmark task, plus a check that walks the file and reports
anything score-shaped. The module said, in as many words, that no score is
present "and :func:`check_catalog_carries_no_scores` proves it by looking".

Nobody had asked the check what it can see. It held fourteen field names
somebody had typed out and reported a leak only when one of those exact names
appeared. Against the field names this repository's own grading pipeline really
writes, that caught 8 of 45 and missed 37 — ``avg_score``, ``scores``,
``pass_rate``, ``child_grades``, ``graded_by`` and thirty-two more went through
with a clean report.

So the tests here do not check that the check refuses ``score``. They take the
names out of the repository's committed grade files and require every one of
them to be refused, and they require the permitted names to be read from the
schema rather than typed, so that neither list can go stale without a failure.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from scripts import build_gdpval_task_catalog as builder

from core.execution_envelope_tasks import (
    CATALOG_PATH,
    CatalogTask,
    TaskCatalog,
    _PROSE_ONLY_CATALOG_KEYS,
    _allowed_catalog_field_names,
    check_catalog_carries_no_scores,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_GRADES = REPOSITORY_ROOT / "data" / "grades"

# Words that mark a field as carrying something about how a run turned out.
# Deliberately broad: the point of the sweep below is to be generous about what
# counts as a result, then require every one of them to be refused.
RESULT_WORDS = (
    "score",
    "grade",
    "verdict",
    "pass",
    "fail",
    "rating",
    "rank",
    "award",
    "point",
    "pct",
    "percent",
    "correct",
    "confid",
    "judge",
    "eval",
    "result",
)


def _result_shaped_names_this_repository_writes() -> list[str]:
    """Every result-carrying field name in the committed grade files.

    Read out of the files rather than listed here. A list typed into a test is
    the same mistake as a list typed into the code it tests: it is right on the
    day it is written and nothing tells anyone when it stops being right.
    """
    found: set[str] = set()

    def harvest(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                name = str(key)
                if any(word in name.lower() for word in RESULT_WORDS):
                    found.add(name)
                harvest(value)
        elif isinstance(node, list):
            for value in node:
                harvest(value)

    for path in sorted(PUBLISHED_GRADES.glob("*.json")):
        harvest(json.loads(path.read_text(encoding="utf-8")))
    return sorted(found)


def _catalogue() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _write(tmp_path: Path, payload: dict) -> Path:
    target = tmp_path / "gdpval_task_catalog.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


# ── The file that is actually committed ────────────────────────────────────


def test_the_committed_catalogue_is_reported_clean():
    assert check_catalog_carries_no_scores() == []


def test_the_committed_catalogue_uses_only_names_the_schema_describes():
    """The permitted set covers the real file exactly, with nothing spare.

    If this fails one of two things happened: the catalogue grew a field, or
    the permitted set holds a name nothing uses. Both are worth knowing.
    """
    present: set[str] = set()

    def harvest(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                present.add(str(key))
                harvest(value)
        elif isinstance(node, list):
            for value in node:
                harvest(value)

    harvest(_catalogue())
    assert present == _allowed_catalog_field_names()


# ── The measurement this work exists because of ────────────────────────────


def test_the_grade_corpus_is_here_to_read():
    """Guard the sweep below: an empty corpus would make it pass vacuously."""
    names = _result_shaped_names_this_repository_writes()
    assert len(names) >= 40, (
        "the committed grade files should supply plenty of result-carrying "
        f"field names to sweep with, found {len(names)}"
    )


def test_every_result_name_this_repository_writes_is_refused(tmp_path):
    """Inject each real grade field name into a task entry; all must be caught.

    This is the whole point. Against the list-of-names version, 37 of these
    walked straight through.
    """
    names = _result_shaped_names_this_repository_writes()
    missed = []
    for index, name in enumerate(names):
        leaked = _catalogue()
        leaked["tasks"][0][name] = 0.87
        target = tmp_path / f"catalog_{index}.json"
        target.write_text(json.dumps(leaked), encoding="utf-8")
        if not check_catalog_carries_no_scores(target):
            missed.append(name)
    assert missed == [], (
        "these result-carrying field names were reported as clean: "
        + ", ".join(missed)
    )


# ── Where the permitted names come from ────────────────────────────────────


def test_the_permitted_names_are_read_from_the_two_dataclasses():
    schema_names = {field.name for field in dataclasses.fields(TaskCatalog)} | {
        field.name for field in dataclasses.fields(CatalogTask)
    }
    assert schema_names <= _allowed_catalog_field_names()
    assert _allowed_catalog_field_names() == schema_names | _PROSE_ONLY_CATALOG_KEYS


def test_the_hand_written_part_holds_nothing_the_file_does_not_use():
    """Three names are still typed out. Keep them honest.

    They carry prose, not data, so the schema cannot supply them. That makes
    them the one place this can go stale, so require each to be a name the
    committed catalogue really uses.
    """
    top_level = set(_catalogue())
    assert _PROSE_ONLY_CATALOG_KEYS <= top_level
    schema_names = {field.name for field in dataclasses.fields(TaskCatalog)} | {
        field.name for field in dataclasses.fields(CatalogTask)
    }
    assert not (_PROSE_ONLY_CATALOG_KEYS & schema_names), (
        "a name is both a schema field and a hand-written prose key, so one "
        "of the two is not doing what it says"
    )


def test_the_permitted_names_are_never_typed_out(tmp_path):
    """Read the source: the schema half must be derived, not listed.

    The previous version of this check went wrong precisely because its list
    was typed. An equality assertion cannot tell a derived set from a listed
    one that happens to match today, so look at how it is written.
    """
    import inspect

    from core import execution_envelope_tasks

    source = inspect.getsource(
        execution_envelope_tasks._allowed_catalog_field_names
    )
    body = source.split('"""')[-1]
    assert "dataclasses.fields(TaskCatalog)" in body
    assert "dataclasses.fields(CatalogTask)" in body
    for field in dataclasses.fields(CatalogTask):
        assert f'"{field.name}"' not in body, (
            f"{field.name} is typed into the permitted set as well as being "
            "in the schema, so the two can drift apart again"
        )


# ── A new field is refused wherever it hides ───────────────────────────────


def test_a_new_field_at_the_top_level_is_refused(tmp_path):
    payload = _catalogue()
    payload["overall_quality"] = "good"
    problems = check_catalog_carries_no_scores(_write(tmp_path, payload))
    assert len(problems) == 1
    assert "overall_quality" in problems[0]
    assert "the schema does not describe" in problems[0]


def test_a_new_field_inside_a_task_is_refused(tmp_path):
    payload = _catalogue()
    payload["tasks"][17]["how_it_went"] = "well"
    problems = check_catalog_carries_no_scores(_write(tmp_path, payload))
    assert len(problems) == 1
    assert "how_it_went" in problems[0]


def test_a_new_field_nested_inside_an_allowed_one_is_refused(tmp_path):
    """Depth is not a hiding place."""
    payload = _catalogue()
    payload["tasks"][0]["reference_file_paths"] = [
        {"path": "a.xlsx", "how_it_went": {"buried": "deeper"}}
    ]
    problems = check_catalog_carries_no_scores(_write(tmp_path, payload))
    assert len(problems) == 1
    for name in ("path", "how_it_went", "buried"):
        assert name in problems[0]


def test_the_refusal_names_every_field_it_found(tmp_path):
    payload = _catalogue()
    payload["first_new_thing"] = "x"
    payload["tasks"][3]["second_new_thing"] = "y"
    problems = check_catalog_carries_no_scores(_write(tmp_path, payload))
    assert len(problems) == 1
    assert "first_new_thing" in problems[0]
    assert "second_new_thing" in problems[0]


# ── A result taking over a field that is allowed ───────────────────────────


def test_a_fraction_under_an_allowed_name_is_refused(tmp_path):
    """Every number the schema holds is a count. A fraction is something else."""
    payload = _catalogue()
    payload["tasks"][0]["rubric_item_count"] = 0.87
    problems = check_catalog_carries_no_scores(_write(tmp_path, payload))
    assert len(problems) == 1
    assert "rubric_item_count" in problems[0]
    assert "fraction" in problems[0]


def test_true_or_false_under_an_allowed_name_is_refused(tmp_path):
    """Python counts True as 1, so a pass/fail flag needs naming separately."""
    payload = _catalogue()
    payload["tasks"][0]["reference_file_count"] = True
    problems = check_catalog_carries_no_scores(_write(tmp_path, payload))
    assert len(problems) == 1
    assert "reference_file_count" in problems[0]


def test_a_fraction_inside_a_list_is_refused(tmp_path):
    payload = _catalogue()
    payload["tasks"][0]["reference_file_extensions"] = [".xlsx", 0.5]
    problems = check_catalog_carries_no_scores(_write(tmp_path, payload))
    assert len(problems) == 1
    assert "reference_file_extensions" in problems[0]


def test_a_whole_number_is_still_a_perfectly_good_count(tmp_path):
    payload = _catalogue()
    payload["tasks"][0]["reference_file_count"] = 41
    payload["tasks"][0]["prompt_character_count"] = 0
    assert check_catalog_carries_no_scores(_write(tmp_path, payload)) == []


def test_both_kinds_of_problem_are_reported_together(tmp_path):
    payload = _catalogue()
    payload["tasks"][0]["avg_score"] = "0.9"
    payload["tasks"][1]["rubric_item_count"] = 0.5
    problems = check_catalog_carries_no_scores(_write(tmp_path, payload))
    assert len(problems) == 2
    assert any("avg_score" in note for note in problems)
    assert any("fraction" in note for note in problems)


# ── The limit, written down so nobody assumes otherwise ────────────────────


def test_a_score_written_into_text_is_not_caught_and_that_is_stated(tmp_path):
    """The honest boundary of a check that reads names and number shapes.

    A result hidden in the text of a field that is allowed to hold text goes
    through. This is not a defect to fix here — deciding whether an occupation
    string is really an occupation is a different kind of job — but the module
    docstring has to say so instead of claiming the file is proven clean, and
    this test fails if that sentence is ever removed.
    """
    payload = _catalogue()
    payload["tasks"][0]["occupation"] = "Registered Nurse (scored 0.87)"
    assert check_catalog_carries_no_scores(_write(tmp_path, payload)) == []

    from core import execution_envelope_tasks

    docstring = execution_envelope_tasks.__doc__ or ""
    assert "cannot prove" in docstring
    assert "Nurse" in docstring


# ── The check reaches the tool that decides whether to spend ───────────────


def test_the_advance_check_reports_what_this_finds(monkeypatch, tmp_path):
    """A check nothing calls protects nothing."""
    from core import execution_envelope_preflight

    payload = _catalogue()
    payload["tasks"][0]["avg_score"] = "0.9"
    leaked = _write(tmp_path, payload)

    monkeypatch.setattr(
        execution_envelope_preflight,
        "check_catalog_carries_no_scores",
        lambda path=None: check_catalog_carries_no_scores(leaked),
    )
    problems = execution_envelope_preflight.check_catalog_carries_no_scores()
    assert any("avg_score" in note for note in problems)


def test_a_missing_catalogue_file_raises_rather_than_reporting_clean():
    """Silence from a check that could not read anything is the worst answer."""
    with pytest.raises(OSError):
        check_catalog_carries_no_scores(Path("/nonexistent/catalog.json"))


# ── The builder is asked before it writes, not after ───────────────────────


def test_the_builder_refuses_to_write_a_catalogue_that_would_be_refused(
    monkeypatch, tmp_path, capsys
):
    """Catch the leak at the edit that causes it, not three steps later.

    The committed catalogue is clean because the builder happens to construct
    each field by hand. The next person to add one useful-looking column would
    have written it out, committed it, and found out at the advance check.
    """
    leaked = _catalogue()
    leaked["tasks"][0]["avg_score"] = 0.9
    monkeypatch.setattr(builder, "build_catalog", lambda parquet: leaked)
    monkeypatch.setattr(builder, "_find_parquet", lambda given: Path("unused"))
    out = tmp_path / "written.json"
    monkeypatch.setattr("sys.argv", ["build", "--out", str(out)])

    assert builder.main() == 1
    assert not out.exists(), "a refused catalogue must not reach disk"
    assert "avg_score" in capsys.readouterr().err


def test_the_builder_still_writes_a_clean_catalogue(monkeypatch, tmp_path):
    monkeypatch.setattr(builder, "build_catalog", lambda parquet: _catalogue())
    monkeypatch.setattr(builder, "_find_parquet", lambda given: Path("unused"))
    out = tmp_path / "written.json"
    monkeypatch.setattr("sys.argv", ["build", "--out", str(out)])

    assert builder.main() == 0
    assert check_catalog_carries_no_scores(out) == []
