"""The turn-limit design, held to the plan its comparison would actually run.

``tasks/0822_saturday/TURN_LIMIT_COMPARISON_DESIGN.md`` §3 is the list of what
must not move while ``tool_calls_per_attempt`` does. It is the section the whole
document exists for: a comparison that moves a second axis answers a different
question than the one it reports.

The list was anchored to **trial_30's values**, and that anchor is stale. Its
own Verdict requires two of the things it named -- the instruction text and the
replay format -- to change *before* the comparison runs, and
``agentic_corrected_harness_plan.yaml`` has already changed both. The document
was last edited at ``78df149``; ``3acc0b1`` added
``fixed_settings.replay_format`` to a config file three hours later and nothing
came back to §3. So a reader following the section as written would take
trial_30's instruction text and paraphrase replay for the control leg, move
three axes, and report one -- by obeying the section that exists to stop exactly
that.

The constraint was never wrong. The anchor was. What this file pins is that the
anchor stays on the corrected baseline, and that the retraction keeps quoting
the sentence it retracts, because that sentence has been read and will be
remembered.

It also pins the three conditions the old list left out -- the deployment, the
API route and the per-task time limit. All three were being held; none was
written down. A condition that is held but unlisted is the one that moves
without anyone noticing, which is the same failure one step earlier.

Every fact comes from the two plan YAMLs. Offline, free, read-only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER_ROOT.parent
ENVELOPE = BATCH_RUNNER_ROOT / "experiments" / "execution_envelope"

DESIGN = REPO_ROOT / "tasks" / "0822_saturday" / "TURN_LIMIT_COMPARISON_DESIGN.md"
THE_PLAN_THAT_RAN = ENVELOPE / "agentic_stage_one_plan.yaml"
THE_CORRECTED_PLAN = ENVELOPE / "agentic_corrected_harness_plan.yaml"

#: The sentence §3 retracts. Kept as a literal because the point of the test is
#: that it survives as a quotation rather than being deleted.
THE_RETRACTED_ANCHOR = "is held at trial_30's values"

#: The reason §3 used to give for writing the replay format down in prose.
#: False since ``3acc0b1``, and the test below checks the key it denies.
THE_RETRACTED_REASON = "does not appear in any config file"


def _load(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name} is not a mapping"
    return loaded


@pytest.fixture(scope="module")
def design() -> str:
    return DESIGN.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def axes(design: str) -> str:
    """§3 only, with its line breaks collapsed.

    Collapsed because reflowing a paragraph is not a change to what it says,
    and a test that fails on a rewrap teaches people to stop editing the file.
    Scoped to §3 because the rest of the document quotes trial_30 constantly
    and legitimately -- it is the run every figure is measured against.
    """
    section = design.split("## 3. How many axes move")[1]
    return " ".join(section.split("## 4. What the limit can actually reach")[0].split())


@pytest.fixture(scope="module")
def record(design: str) -> str:
    return " ".join(design.split("## The record this would keep")[1].split())


@pytest.fixture(scope="module")
def ran() -> dict[str, Any]:
    return _load(THE_PLAN_THAT_RAN)


@pytest.fixture(scope="module")
def corrected() -> dict[str, Any]:
    return _load(THE_CORRECTED_PLAN)


# ── what the corrected plan moves, and what §3 must say about it ───────────


def test_everything_the_corrected_plan_moves_is_named_as_moved(ran, corrected):
    """Derived from the YAMLs, so a third change cannot slip past the section.

    ``experiment_record`` is excluded: it is the design record, not a condition
    the model is run under, and the run it describes is this one.
    """
    moved = {
        key for key in set(ran) | set(corrected) if ran.get(key) != corrected.get(key)
    } - {"experiment_record"}
    assert moved == {"instructions", "fixed_settings"}, (
        "the corrected plan moves something §3 has never been told about; "
        f"moved = {sorted(moved)}"
    )

    settings_moved = {
        key
        for key in set(ran["fixed_settings"]) | set(corrected["fixed_settings"])
        if ran["fixed_settings"].get(key) != corrected["fixed_settings"].get(key)
    }
    assert settings_moved == {"replay_format"}


def test_section_three_anchors_on_the_corrected_plan_and_not_on_trial_30(axes):
    """The repair itself. Both legs take the corrected values, or the run lies.

    Naming the file matters more than naming the idea: "the corrected harness"
    is a phrase, ``agentic_corrected_harness_plan.yaml`` is something a reader
    can open and a run can be dispatched against.
    """
    assert "The anchor is the **corrected baseline**" in axes
    assert "agentic_corrected_harness_plan.yaml" in axes
    assert "Both legs take the corrected values." in axes
    assert "would move three axes and report one" in axes


def test_the_two_moved_conditions_are_each_named_in_the_section(axes):
    """Named one at a time, because "the corrected values" hides a count."""
    assert "the instruction text" in axes
    assert "derived from whichever backend is mounted" in axes
    assert "`replay_format: faithful`" in axes


def test_the_retraction_still_quotes_the_sentence_it_retracts(axes):
    """A retraction that deletes its subject leaves the reader doubting memory.

    The old anchor was in the file for a day and is the sort of sentence that
    gets quoted into a summary. Someone who remembers it has to be able to find
    it here, marked, rather than conclude they misread it.
    """
    assert "used to say" in axes
    assert THE_RETRACTED_ANCHOR in axes, (
        "the retraction dropped the sentence it retracts; keep it quoted"
    )
    assert THE_RETRACTED_REASON in axes

    # ...and each survives only inside the quotation, never as a live claim.
    for retracted in (THE_RETRACTED_ANCHOR, THE_RETRACTED_REASON):
        assert axes.count(retracted) == 1, (
            f"{retracted!r} appears twice in §3; one of them is being asserted"
        )
        assert axes.index("used to say") < axes.index(retracted), (
            f"{retracted!r} comes before the retraction that governs it"
        )
    assert "Both halves are now wrong" in axes


def test_the_denied_config_key_is_really_there(corrected):
    """The other half of the same retraction, checked against the file.

    §3 used to say the replay format appears in no config file. It does, and
    this is the assertion that would fail first if it were ever removed again
    -- at which point the old sentence becomes true and §3 needs rewriting
    rather than re-quoting.
    """
    assert "replay_format" in corrected["fixed_settings"]
    assert corrected["fixed_settings"]["replay_format"] == "faithful"


def test_the_verdict_sentence_the_section_cites_is_still_in_the_file(design):
    """§3's evidence that the contradiction was real, not inferred.

    If the Verdict is ever reworded, §3 is quoting something that is no longer
    in the document, and the argument for the repair has to be rebuilt from
    scratch by whoever notices.
    """
    verdict = design.split("## Verdict")[1]
    assert "the instruction text is a pinned condition, and trial_30" in " ".join(
        verdict.split()
    )


# ── the conditions that were held but never listed ─────────────────────────


HELD_BUT_UNLISTED = (
    # (what §3 must name, how to read it out of a plan)
    ("`model.resolved_model`", ("model", "resolved_model")),
    ("`model.deployment`", ("model", "deployment")),
    ("`azure_connection.account`", ("azure_connection", "account")),
    ("`fixed_settings.per_task_timeout_seconds: 1200`",
     ("fixed_settings", "per_task_timeout_seconds")),
    ("`fixed_settings.retry_max_attempts`", ("fixed_settings", "retry_max_attempts")),
)


@pytest.mark.parametrize("named,path", HELD_BUT_UNLISTED, ids=lambda v: str(v)[:40])
def test_a_condition_that_is_held_is_also_written_down(axes, ran, corrected, named, path):
    """Held in both plans *and* named in §3 -- neither alone is enough.

    The deployment, the API route and the per-task time limit were identical in
    both plans from the day the corrected one was written, and none of the
    three was in the list a person reads. Holding a condition silently works
    right up until somebody edits the plan and checks the list to see whether
    it mattered.
    """
    section, key = path
    assert ran[section][key] == corrected[section][key], (
        f"{section}.{key} differs between the plans and §3 lists it as held"
    )
    # The table writes these with their section prefix; accept the bare key too
    # so that renaming a heading does not fail a test about conditions.
    assert named in axes or f"`{key}" in axes, (
        f"{section}.{key} is held by both plans and §3 never mentions it"
    )


def test_the_route_profile_is_named_because_it_is_the_api_and_not_the_account(
    axes, ran, corrected
):
    """Same account, same project, same route -- three facts, one row.

    ``route_profile`` is the one of the three that selects how the request is
    made rather than where it goes, so a run that kept the account and changed
    the route would read as "same endpoint" in every other record.
    """
    assert ran["azure_connection"] == corrected["azure_connection"]
    assert "route_profile" in axes


def test_the_tool_result_cap_is_labelled_as_code_and_not_as_a_plan_key(axes):
    """Because looking for it in the plan and not finding it reads as unheld.

    ``max_result_bytes`` is a default in ``agentic_v2_tools.py``. The old list
    named it beside settings that are plan keys, which is how a reader ends up
    grepping the YAML for it and concluding the condition is loose.
    """
    assert "max_result_bytes" in axes
    assert "agentic_v2_tools.py" in axes
    assert "not a plan key" in axes


# ── the record block, which is what gets copied into a report ──────────────


def test_the_record_block_agrees_with_the_section_it_summarises(record):
    """It is the part that travels, so it is the part that must not lag.

    Everything above it can be right while this reads "fixed: ... instructions,
    replay format" with no anchor, and that block is what gets pasted into a
    write-up.
    """
    assert "corrected harness" in record
    assert "not trial_30 the run" in record
    assert "all at the corrected baseline's" in record


@pytest.mark.parametrize(
    "condition", ("model and deployment", "API route", "per-task time limit")
)
def test_the_record_block_lists_the_three_that_were_missing(record, condition):
    assert condition in record
