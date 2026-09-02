"""The plan's marking figure reaches what one marking call can really carry.

``test_envelope_preflight_prices_the_marking_tool_results.py`` established what
one marking call can be asked to carry and made the free check say so. It left
the plan itself at 10,000 tokens a call on purpose, so that the check would
report the gap out loud instead of the mistake being quietly tidied away. The
report has been saying it ever since, under a heading calling the totals the
largest possible bill:

    WARNING: the marking figure above is not a ceiling — 3 thing(s) the
    marking settings allow are not counted in it, so every total here is
    too low.

This file closes the one of those three that can be closed without calling a
model or paying for anything. The plan now states 536,191 tokens a call, and
the tests below hold it there by rebuilding the figure the way the run would:

* ``read_grading_caps`` reads ``per_item_call_cap`` and the judge's limits out
  of ``grading_configs/default_v2.yaml``, the file the plan names;
* ``MAX_CONTENT_CHARS`` comes from ``core/tools/read_deliverable.py``, the
  module that truncates every tool result;
* the standing instructions are counted off ``prompts/grader_judge_v2.md``, the
  committed file the marking run sends on every call;
* the widest scoring line comes from the task catalogue, via
  ``widest_scoring_line_characters``.

Nothing here types 536,191 as an input. Every test that asserts it derives it
first and compares. Widen any of the four and these tests fail, which is the
whole point: the last time one of them moved, the plan went on quoting a number
that had stopped being true.

**What this does not close.** Two of the three remain, and neither is free:
how much one sound-listening call sends has never been measured, and
``gpt-audio-1.5`` has no published price. Both need something from outside this
repository. The warning still fires, and now says two.

**What this does not change.** The marking run is untouched: no settings file,
no judge limit, no prompt. The settings always permitted this; only the sum
stopped understating it. Under the record-only cost policy the larger figure is
recorded and does not stop anything, and the tests below pin that the list of
things that *do* stop a run is exactly the same before and after.

Nothing here calls a model, marks anything, or spends anything.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_stage_one_budget import (  # noqa: E402
    load_stage_one_plan,
    run_stage_one_preflight,
)
from core.execution_envelope_cost import CostAssumptions  # noqa: E402
from core.execution_envelope_grading_cost import (  # noqa: E402
    check_assumptions_cover_the_caps,
    read_grading_caps,
    standing_instructions_characters,
)
from core.execution_envelope_preflight import (  # noqa: E402
    load_plan,
    run_envelope_preflight,
)
from core.execution_envelope_tasks import (  # noqa: E402
    load_task_catalog,
    widest_scoring_line_characters,
)
from core.tools.read_deliverable import MAX_CONTENT_CHARS  # noqa: E402

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
COMMITTED_MARKING_SETTINGS = (
    BATCH_RUNNER_ROOT / "grading_configs" / "default_v2.yaml"
)

#: The wording the free check uses for this finding. Matched rather than
#: reproduced, so a reworded finding cannot silently stop being detected.
THIS_FINDING = "input per marking call"


def _plan() -> dict:
    return load_plan(PLAN_PATH)


def _assumptions(plan: dict) -> CostAssumptions:
    return CostAssumptions.from_mapping(plan["cost"]["assumptions"])


def _caps_the_run_would_apply(plan: dict):
    """The marking limits, read the way the free check reads them.

    Deliberately routed through ``read_grading_caps`` and the committed
    catalogue rather than through a fixture: a fixture would let this file
    agree with itself while disagreeing with the run.
    """
    return read_grading_caps(
        BATCH_RUNNER_ROOT / str(plan["grading_config"]),
        widest_scoring_line_characters=widest_scoring_line_characters(
            load_task_catalog()
        ),
    )


def _demanded(plan: dict) -> int:
    assumptions = _assumptions(plan)
    return _caps_the_run_would_apply(plan).input_tokens_one_call_must_cover(
        assumptions.characters_per_token
    )


def _findings_about_this(plan: dict) -> list[str]:
    result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)
    return [line for line in result.cost_findings if THIS_FINDING in line]


# ── The plan reaches the figure, and the figure is rebuilt to check ────────


def test_the_plan_states_what_one_marking_call_can_carry():
    """Rebuilt from the settings, the instruction file and the catalogue."""
    plan = _plan()
    stated = _assumptions(plan).grading_input_tokens_per_call

    assert stated >= _demanded(plan), (
        f"the plan states {stated} tokens of input per marking call, and the "
        f"settings it names permit {_demanded(plan)}"
    )


def test_the_stated_figure_is_the_demand_exactly_and_not_a_round_number():
    """A ceiling that overshoots by an unexplained margin is a guess again.

    Reaching the demand is what the check requires, so any larger number would
    pass. This pins the plan to the measured figure itself, so that a reader
    who adds up the four parts gets the number in the file.
    """
    plan = _plan()

    assert _assumptions(plan).grading_input_tokens_per_call == _demanded(plan)


def test_the_four_parts_add_up_to_the_stated_figure():
    """Each part read from where the marking run reads it, counted once."""
    plan = _plan()
    caps = _caps_the_run_would_apply(plan)
    ratio = _assumptions(plan).characters_per_token

    tool_results = caps.input_tokens_carried_by_tool_results(ratio)
    opening = caps.input_tokens_the_conversation_opens_with(ratio)

    assert caps.characters_per_tool_result == MAX_CONTENT_CHARS
    assert caps.characters_of_standing_instructions == (
        standing_instructions_characters(Path(caps.standing_instructions_path))
    )
    assert caps.characters_of_widest_scoring_line == (
        widest_scoring_line_characters(load_task_catalog())
    )
    # No double charge: the opening is the three opening pieces and nothing
    # else, and the tool results are the pile-up and nothing else.
    assert opening * ratio >= Decimal(
        caps.characters_of_standing_instructions
        + caps.characters_of_task_prompt_preview
        + caps.characters_of_widest_scoring_line
    )
    assert tool_results + opening == _demanded(plan)
    assert _assumptions(plan).grading_input_tokens_per_call == (
        tool_results + opening
    )


# ── The report changed, and only in the way it was meant to ───────────────


def test_the_committed_plan_no_longer_records_this_finding():
    assert _findings_about_this(_plan()) == []


def test_the_warning_now_names_two_things_and_says_which():
    """Two remain, both needing something from outside this repository."""
    result = run_envelope_preflight(_plan(), root=BATCH_RUNNER_ROOT)

    assert len(result.grading_ceiling_problems) == 2
    remaining = "\n".join(result.grading_ceiling_problems)
    assert "listening to sound" in remaining
    assert "no published price" in remaining
    assert THIS_FINDING not in remaining


def test_nothing_new_stops_the_run():
    """The larger figure is recorded, not enforced.

    The cost policy has been record-only since 2026-08-28. Raising a recorded
    ceiling past the credit on record must not quietly become a block, and
    every non-cost block — security, account, support status — must survive
    untouched.
    """
    raised = run_envelope_preflight(_plan(), root=BATCH_RUNNER_ROOT)

    lowered_plan = _plan()
    lowered_plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = 10_000
    lowered = run_envelope_preflight(lowered_plan, root=BATCH_RUNNER_ROOT)

    assert raised.problems == lowered.problems
    assert raised.cost.total_usd > lowered.cost.total_usd


def test_the_recorded_ceiling_moved_by_the_marking_line_alone():
    """Running the tasks is priced by other code and must not have moved."""
    raised = run_envelope_preflight(_plan(), root=BATCH_RUNNER_ROOT).cost

    lowered_plan = _plan()
    lowered_plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = 10_000
    lowered = run_envelope_preflight(lowered_plan, root=BATCH_RUNNER_ROOT).cost

    assert raised.running_usd == lowered.running_usd
    assert raised.perception_usd == lowered.perception_usd
    assert raised.grading_usd > lowered.grading_usd * 20
    assert raised.total_model_calls == lowered.total_model_calls


# ── Boundary ──────────────────────────────────────────────────────────────


def test_one_token_short_is_short():
    plan = _plan()
    plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = (
        _demanded(_plan()) - 1
    )

    assert len(_findings_about_this(plan)) == 1


def test_exactly_the_demand_is_enough():
    plan = _plan()
    plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = _demanded(
        _plan()
    )

    assert _findings_about_this(plan) == []


# ── Regression: the undercount this closed ────────────────────────────────


def test_the_old_number_is_caught_again_if_it_comes_back():
    """10,000 was 1.865 per cent of what the settings permit."""
    plan = _plan()
    plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = 10_000

    findings = _findings_about_this(plan)
    assert len(findings) == 1
    assert "allows 10000 tokens of input" in findings[0]
    assert str(_demanded(_plan())) in findings[0]


def test_the_plan_no_longer_calls_the_opening_uncapped():
    """The sentence that was wrong must not survive next to the fix.

    The comment above the number used to end by saying what the conversation
    opens with "is capped by nothing, so 533,334 is a floor on the largest a
    call can be, not the largest itself". The opening is measured — 2,857
    tokens of instruction file, task preview and scoring line — and a caveat
    saying otherwise, sitting above a number that includes it, is how the next
    reader gets talked out of trusting the figure.
    """
    text = PLAN_PATH.read_text(encoding="utf-8")

    assert "is capped by nothing" not in text
    assert "is a floor on the largest a call" not in text
    assert "now works that out and refuses" not in text


# ── Mutation proof: each of the four inputs moves the demand ──────────────


@pytest.mark.parametrize(
    "widen",
    [
        pytest.param(
            lambda settings: settings["judge"]["tools"]["read_deliverable"]
            .__setitem__("per_item_call_cap", 9),
            id="one more tool result may pile up",
        ),
        pytest.param(
            lambda settings: settings["judge"]["tools"]["read_deliverable"]
            .__setitem__("max_iterations", 20),
            id="the tool loop may run longer",
        ),
    ],
)
def test_widening_the_marking_settings_is_noticed(tmp_path, widen):
    """The plan cannot be left behind when the settings grow.

    The settings file is copied and widened in a temporary directory. The
    committed one is never written to: this repository's marking behaviour is
    not what is under test here, and changing it would change every run.
    """
    settings = yaml.safe_load(
        COMMITTED_MARKING_SETTINGS.read_text(encoding="utf-8")
    )
    widen(settings)
    widened = tmp_path / "widened.yaml"
    widened.write_text(yaml.safe_dump(settings), encoding="utf-8")

    plan = _plan()
    caps = read_grading_caps(
        widened,
        widest_scoring_line_characters=widest_scoring_line_characters(
            load_task_catalog()
        ),
    )
    assumptions = _assumptions(plan)
    demanded_now = caps.input_tokens_one_call_must_cover(
        assumptions.characters_per_token
    )

    if demanded_now > assumptions.grading_input_tokens_per_call:
        problems = [
            line
            for line in check_assumptions_cover_the_caps(assumptions, caps)
            if THIS_FINDING in line
        ]
        assert len(problems) == 1
    else:
        # A longer tool loop does not widen what one call carries — the pile-up
        # is capped by per_item_call_cap, not by how many turns there are — so
        # this arm proves the demand does *not* move, which is the claim the
        # plan's comment makes about which four things bound it.
        assert demanded_now == _demanded(plan)


def test_a_longer_instruction_file_raises_the_demand_by_itself(tmp_path):
    """The opening is read off the file, not written down beside it."""
    plan = _plan()
    ratio = _assumptions(plan).characters_per_token
    before = _caps_the_run_would_apply(plan)

    settings = yaml.safe_load(
        COMMITTED_MARKING_SETTINGS.read_text(encoding="utf-8")
    )
    longer = tmp_path / "prompts" / "grader_judge_v2.md"
    longer.parent.mkdir(parents=True)
    longer.write_text(
        (BATCH_RUNNER_ROOT / before.standing_instructions_path).read_text(
            encoding="utf-8"
        )
        + "x" * 3_000,
        encoding="utf-8",
    )
    settings.setdefault("prompt", {})["tool_template"] = str(longer)
    widened = tmp_path / "widened.yaml"
    widened.write_text(yaml.safe_dump(settings), encoding="utf-8")

    after = read_grading_caps(
        widened,
        widest_scoring_line_characters=widest_scoring_line_characters(
            load_task_catalog()
        ),
    )

    assert after.characters_of_standing_instructions == (
        before.characters_of_standing_instructions + 3_000
    )
    assert after.input_tokens_one_call_must_cover(ratio) == (
        before.input_tokens_one_call_must_cover(ratio) + 1_000
    )


def test_a_wider_scoring_line_raises_the_demand_by_itself():
    """The dataset's widest line is an input to the figure, not a constant."""
    plan = _plan()
    ratio = _assumptions(plan).characters_per_token
    caps = _caps_the_run_would_apply(plan)

    from dataclasses import replace

    wider = replace(
        caps,
        characters_of_widest_scoring_line=(
            caps.characters_of_widest_scoring_line + 300
        ),
    )

    assert wider.input_tokens_one_call_must_cover(ratio) == (
        caps.input_tokens_one_call_must_cover(ratio) + 100
    )


# ── Fail closed rather than measure low ───────────────────────────────────


def test_settings_that_cannot_be_read_are_refused_not_priced_at_nothing(
    tmp_path,
):
    plan = _plan()
    plan["grading_config"] = "grading_configs/there-is-no-such-file.yaml"

    result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    assert any(
        "the marking settings could not be read" in line
        for line in result.problems + result.cost_findings
    )


def test_a_missing_instruction_file_is_refused_not_counted_as_empty(tmp_path):
    settings = yaml.safe_load(
        COMMITTED_MARKING_SETTINGS.read_text(encoding="utf-8")
    )
    settings.setdefault("prompt", {})["tool_template"] = str(
        tmp_path / "gone.md"
    )
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(settings), encoding="utf-8")

    with pytest.raises(ValueError) as raised:
        read_grading_caps(
            broken,
            widest_scoring_line_characters=widest_scoring_line_characters(
                load_task_catalog()
            ),
        )

    assert "price the opening" in str(raised.value)


def test_an_unmeasured_scoring_line_is_refused_not_treated_as_zero():
    """No catalogue means no width, and no width means no figure."""
    plan = _plan()
    caps = read_grading_caps(
        BATCH_RUNNER_ROOT / str(plan["grading_config"]),
        widest_scoring_line_characters=None,
    )

    with pytest.raises(ValueError):
        caps.input_tokens_one_call_must_cover(
            _assumptions(plan).characters_per_token
        )

    findings = check_assumptions_cover_the_caps(_assumptions(plan), caps)
    assert any("never measured" in line for line in findings)


# ── The second place the same under-count was live ──────────────────────────


STAGE_ONE_PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "agentic_stage_one_plan.yaml"
)


def _stage_one_priced(input_tokens_per_call: int):
    """Price stage one's cheapest row under a given marking-input figure.

    Stage one does not carry cost assumptions of its own — its tests and its
    check script both read them out of ``advance_check_plan.yaml``. So the
    figure this file corrects was being used in two places, and only one of
    them was the comparison it was written for.
    """
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = (
        input_tokens_per_call
    )
    assumptions = CostAssumptions.from_mapping(plan["cost"]["assumptions"])

    stage_one = load_stage_one_plan(STAGE_ONE_PLAN_PATH)
    stage_one["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": 4,
        "max_output_tokens_per_turn": 2_048,
    }
    result = run_stage_one_preflight(
        stage_one,
        tasks_by_id=load_task_catalog().by_task_id(),
        assumptions=assumptions,
    )
    assert result.chosen is not None
    return result.chosen


def _looking_at_pictures(option) -> Decimal:
    """The row total less the two lines ``StageOneOption`` names.

    The option keeps running and marking apart on purpose and then totals a
    third line it does not carry: what stage one would spend looking at
    pictures. Naming the remainder here means a change to the visual budget
    shows up as itself. When the visual task cap went from 72 to 112, both row
    totals below rose by 12.50 while neither named line moved by a cent —
    which, without this, reads as an unexplained break in a test about
    marking.
    """
    return option.most_it_could_cost_usd - (
        option.most_running_could_cost_usd + option.most_grading_could_cost_usd
    )


def test_stage_one_was_under_counted_by_the_same_figure_and_is_not_now():
    """The correction reaches stage one too, and only on the marking side.

    This was not planned for; it was found by running the whole suite. Stage
    one borrows these assumptions wholesale, so the flat 10,000 was quietly
    under-counting a second comparison the whole time.

    The split is the evidence that this is the same fault rather than a new
    one. Stage one's *running* line does not move by a cent — the same 40
    calls, the same 3.3654250 — because nothing about how stage one runs
    changed. Its *marking* line moves 89.945625 to 2504.6690109375, a factor
    of nearly twenty-eight, and carries the row from 128.3110500 to
    2543.0344359375.

    The looking line is held equal on both sides rather than left inside the
    row, because it answers to the visual task cap and not to this correction
    at all: 35.00 either way, and the two row totals differ by exactly the
    marking line.
    """
    before = _stage_one_priced(10_000)
    after = _stage_one_priced(536_191)

    assert before.most_running_model_calls == after.most_running_model_calls == 40
    assert (
        before.most_running_could_cost_usd
        == after.most_running_could_cost_usd
        == Decimal("3.3654250")
    ), "running stage one did not change, so its price must not have either"

    assert before.most_grading_model_calls == after.most_grading_model_calls == 2937
    assert before.most_grading_could_cost_usd == Decimal("89.945625")
    assert after.most_grading_could_cost_usd == Decimal("2504.6690109375")

    assert _looking_at_pictures(before) == _looking_at_pictures(after) == Decimal(
        "35.00"
    ), "the marking figure must not have reached the picture budget"

    assert before.most_it_could_cost_usd == Decimal("128.3110500")
    assert after.most_it_could_cost_usd == Decimal("2543.0344359375")


def test_stage_one_reads_these_assumptions_rather_than_keeping_its_own():
    """Why the correction reached stage one at all, stated where it can fail.

    If stage one ever grows its own ``cost.assumptions`` block, this test is
    the one that should stop and make somebody decide whether the two are
    meant to agree — rather than the two drifting apart unremarked, which is
    the failure mode this whole file exists to close.
    """
    stage_one = load_stage_one_plan(STAGE_ONE_PLAN_PATH)

    assert "assumptions" not in (stage_one.get("cost") or {}), (
        "stage one has started carrying its own cost assumptions; decide "
        "whether they must still track advance_check_plan.yaml"
    )

    script = (
        BATCH_RUNNER_ROOT / "scripts" / "check_agentic_stage_one_ceiling.py"
    ).read_text(encoding="utf-8")
    assert "advance_check_plan.yaml" in script, (
        "the stage one check no longer reads the shared plan, so the two can "
        "now disagree about what one marking call carries"
    )
