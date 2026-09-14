"""One question about reference files, one answer in the run record.

``scripts/run_agentic_v2_stage.py`` builds the run record from two modules that
both know something about a task's input files.
:func:`core.agentic_v2_manifest_binding.unmet_needs` knows which tasks *named*
files, from the binding alone, before anything runs.
:func:`core.agentic_v2_reference_staging.staging_record` knows which ones
*received* them, per file, by name, with reasons for every refusal.

For a while both were emitted and they disagreed. ``unmet_needs`` hard-coded
``reference_file_bytes_are_in_the_guest: False`` and a sentence ending "A
failure on one of them is not evidence about the model" -- true when nothing was
staged, and left in place after :mod:`core.agentic_v2_reference_staging` made it
false. So the record carried the stale answer a few keys from the real one, and
on the thirty-task cohort the stale answer named **14 of 30 tasks** and told a
reader to discount them for missing inputs they had been given.

Nothing caught it. The staging module's own docstring said the flat boolean was
what it replaced, the stage script's banner had already been corrected, and a
test asserted the false value under the heading "what is still missing" -- so
the suite went green *because* the claim was wrong in exactly the place the
suite checked.

What this file pins is the split, across both modules and the script that joins
them: wanting is answered in one place, receiving in the other, and the
unconditional form of the discount sentence does not come back. The real cohort
numbers are read from the committed catalogue so the size of what was at stake
is not a remembered figure.

Offline, free, read-only. Nothing here calls a model or opens a guest.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from core import agentic_v2_manifest_binding as binding
from core import agentic_v2_reference_staging as staging
from core.agentic_v2_preregistration import STAGE_FIVE, STAGE_THIRTY, cohorts

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
STAGE_SCRIPT = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_v2_stage.py"
CATALOG = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "gdpval_task_catalog.json"
)

#: The field that carried the stale answer. Named once, here, so that every
#: assertion below refers to the same string and a rename cannot half-land.
THE_RETIRED_FLAG = "reference_file_bytes_are_in_the_guest"

#: The sentence that must only ever be said about tasks that were counted as
#: having gone short. Said of every task that merely *named* a file, it is the
#: defect this module exists for.
THE_DISCOUNT = "not evidence about the model"


@pytest.fixture(scope="module")
def script() -> str:
    return STAGE_SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def catalog_rows() -> dict[str, dict]:
    loaded = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = loaded["tasks"] if isinstance(loaded, dict) else loaded
    return {row["task_id"]: row for row in rows}


# ── the split, in the two modules ─────────────────────────────────────────


def test_the_binding_makes_no_claim_about_what_arrived():
    """``unmet_needs`` reads a binding. A binding cannot know what was staged.

    It is called before any task runs -- that is the whole point of it -- so any
    delivery claim in it is a constant, and a constant that was already wrong
    once.
    """
    source = inspect.getsource(binding.unmet_needs)
    body = source.split('"""')[-1]

    assert THE_RETIRED_FLAG not in body
    assert THE_DISCOUNT not in body
    assert "nothing copies" not in body
    assert "reference_files" in body, (
        "it should still point at the field that does answer delivery"
    )


def test_the_staging_record_is_the_one_that_answers_delivery():
    source = inspect.getsource(staging.staging_record)
    for counted in (
        "tasks_given_everything_they_named",
        "tasks_that_ran_without_some_input",
        "tasks_that_could_open_nothing",
    ):
        assert counted in source


def test_the_discount_sentence_survives_only_where_it_is_counted():
    """It is a true sentence about a measured subset and a false one about all.

    ``staging_record`` says it of ``len(short)`` -- the tasks it found went
    without an input. The retired field said it of every task that named a file,
    which on the thirty-task cohort was more than twice as many as could
    possibly have gone short.
    """
    said_in = inspect.getsource(staging.staging_record)
    assert THE_DISCOUNT in said_in
    assert "len(short)" in said_in or "{len(short)}" in said_in

    assert THE_DISCOUNT not in inspect.getsource(binding.unmet_needs).split('"""')[-1]


def test_the_binding_docstring_does_not_re_assert_what_staging_disproved():
    """The module the plan names as its sealer is where a reviewer goes first.

    ``experiment_record.inputs`` cites this module by name for the claim that
    the cohort travels with its reference files. A reviewer checking that claim
    opens this docstring, and it used to tell them the opposite under the
    heading "What is still missing, stated plainly".
    """
    doc = binding.__doc__ or ""
    assert "What is still missing, stated plainly" not in doc
    assert "Nothing yet copies those files" not in doc
    assert "agentic_v2_reference_staging" in doc, (
        "the correction has to name the module that made the old text false"
    )
    assert "are now false" in doc


# ── the script that joins them ────────────────────────────────────────────


def test_the_record_routes_each_question_to_the_module_that_can_answer_it(script):
    """Asserted on the wiring, because swapping these two would type-check.

    Both return a ``dict[str, Any]`` with a ``what_that_means`` key.
    """
    assert '"reference_files": staging_record(stagings),' in script
    assert '"binding": binding_record(bound),' in script
    assert '"reference_files": binding_record' not in script


def test_the_operator_banner_does_not_say_the_files_are_absent(script):
    """The banner was corrected when staging landed; the record was not.

    Keeping a test on it means the two cannot drift apart again in the other
    direction either.
    """
    assert "staged from" in script
    assert "are not in the workspace" not in script.split('"""')[-1]


# ── what the stale answer would have said, from the real catalogue ────────


def test_the_cohorts_that_would_have_carried_the_stale_sentence():
    """Not a remembered figure: read from the committed catalogue each run.

    If the cohort selection ever changes these move, and the docstring above
    quotes 14 of 30. A test that hard-codes it would let the prose go stale the
    way the field did.
    """
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {row["task_id"]: row for row in (rows["tasks"] if isinstance(rows, dict) else rows)}
    chosen = cohorts()

    naming = {
        stage: sum(
            1 for task_id in chosen[stage] if by_id[task_id].get("reference_file_paths")
        )
        for stage in (STAGE_FIVE, STAGE_THIRTY)
    }
    assert naming[STAGE_THIRTY] == 14, (
        f"the docstring says 14 of 30; the catalogue now says {naming[STAGE_THIRTY]}"
    )
    assert naming[STAGE_FIVE] == 2
    assert 0 < naming[STAGE_THIRTY] < len(chosen[STAGE_THIRTY]), (
        "a flat boolean is only misread when the truth is 'some'; if it ever "
        "becomes all or none, this whole module is about a different risk"
    )
