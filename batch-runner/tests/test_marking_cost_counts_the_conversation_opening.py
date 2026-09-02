"""Every marking conversation opens with wording this repository pins.

``core.execution_envelope_grading_cost`` demands a figure for how many input
tokens one marking call can carry, and refuses a plan that states less. Until
this file existed the demand counted the tool results and nothing else. Its own
docstring explained why: what the conversation *starts* with — the standing
instructions, the scoring line, "the first 500 characters of the task" — "is
not capped by anything".

All three of those are capped, and one of the caps was written down in prose in
the sentence that denied it.

* The standing instructions are a committed file. ``prompt.tool_template``
  names it in all nine settings files, the judge splits it and sends both
  halves on every single call, and it is 6,866 characters long today.
* The task preview is cut to ``ToolCallingJudge.task_prompt_truncate``
  characters, which is 500, and every task in the committed catalogue is longer
  than that — so the cut is always taken in full.
* The scoring line is not capped by any *setting*, which the module read as not
  capped at all. It comes from ``rubric_json`` in the pinned dataset, where the
  widest of all 10,453 of them is 1,203 characters and cannot change without
  the revision changing. Its width is measured into the task catalogue and
  handed in, because the settings file cannot supply it.

Leaving them out made the demanded figure *lower* than the truth. That is the
direction that costs money: a plan clears a figure that is too low and is
recorded as having been checked. Worse, the module said so itself — it called
its own demand "still a floor" inside a report headed the largest possible
bill, and a sum with an unbounded part has no maximum. The tests here hold the
demand to all three pieces, hold the module to reading each of them from where
the marking run reads it, and hold it to refusing rather than quietly
subtracting when the third was never handed in.

They also pin the thing found next door. ``grader.task_prompt_truncate_chars``
sits in nine settings files and reaches nothing: ``core.grader`` builds the
judge without passing it. A width an operator can edit without effect is how a
number stops describing the run it is written next to, so the check now says so.

Nothing here calls a model, marks anything, or spends anything.
"""

from __future__ import annotations

import re
from dataclasses import MISSING, fields, replace
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.execution_envelope_cost import CostAssumptions
from core.execution_envelope_grading_cost import (
    BATCH_RUNNER_ROOT,
    FALLBACK_TOOL_TEMPLATE_NAME,
    GradingCaps,
    TASK_PROMPT_TRUNCATE_SETTING,
    check_assumptions_cover_the_caps,
    describe_grading_caps,
    read_grading_caps,
    resolve_standing_instructions_path,
    standing_instructions_characters,
)
from core.execution_envelope_preflight import load_plan, run_envelope_preflight
from core.execution_envelope_tasks import (
    load_task_catalog,
    widest_scoring_line_characters,
)
from core.grader import resolve_tool_prompt_path
from core.tool_calling_judge import ToolCallingJudge
from core.tools.read_deliverable import MAX_CONTENT_CHARS

THREE = Decimal("3.0")
GRADING_CONFIG_DIRECTORY = BATCH_RUNNER_ROOT / "grading_configs"
PLAN_PATH = (
    BATCH_RUNNER_ROOT / "experiments" / "execution_envelope" / "advance_check_plan.yaml"
)
COMMITTED_SETTINGS = GRADING_CONFIG_DIRECTORY / "default_v2.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def tool_calling_settings_files() -> list[Path]:
    """Every committed settings file that builds a tool-calling judge."""
    found: list[Path] = []
    for path in sorted(GRADING_CONFIG_DIRECTORY.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue
        if "read_deliverable" in ((document.get("judge") or {}).get("tools") or {}):
            found.append(path)
    return found


def settings(**overrides) -> dict:
    document = {
        "judge": {
            "model": "gpt-5.4",
            "generation": {"max_output_tokens": 2400},
            "tools": {"read_deliverable": {"per_item_call_cap": 8,
                                           "max_iterations": 10}},
        },
        "prompt": {"tool_template": "prompts/grader_judge_v2.md"},
        "grader": {"judge_max_retries": 1, "task_prompt_truncate_chars": 500},
    }
    document.update(overrides)
    return document


def written(tmp_path: Path, document, name: str = "marking.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def real_widest_scoring_line() -> int:
    """The benchmark's widest scoring line, read from the committed catalogue.

    Measured rather than typed, like everything else this module counts. It is
    the one piece of the opening that is not in the settings file at all — it
    comes from the pinned dataset — so a caller has to hand it to
    ``read_grading_caps`` and the fixture below does that once.
    """
    return widest_scoring_line_characters(load_task_catalog())


def caps(**overrides) -> GradingCaps:
    base = read_grading_caps(
        COMMITTED_SETTINGS,
        widest_scoring_line_characters=real_widest_scoring_line(),
    )
    return replace(base, **overrides)


def assumptions(**overrides) -> CostAssumptions:
    raw = {
        "characters_per_token": "3.0",
        "instruction_character_count": 100,
        "tool_loop_max_model_turns": {"host_python_process": 1},
        "output_tokens_capped_per_attempt": {"host_python_process": False},
        "max_tool_result_tokens_per_turn": {"host_python_process": 0},
        "safety_multiplier": "1.25",
        "grading_required": True,
        "grading_model": read_grading_caps(COMMITTED_SETTINGS).judge_model,
        "grading_calls_per_rubric_item": 11,
        "grading_input_tokens_per_call": 10_000_000,
        "grading_output_tokens_per_call": 2400,
    }
    raw.update(overrides)
    return CostAssumptions.from_mapping(raw)


def input_problems(caps_used: GradingCaps, **overrides) -> list[str]:
    return [
        problem
        for problem in check_assumptions_cover_the_caps(
            assumptions(**overrides), caps_used
        )
        if "input per marking call" in problem
    ]


# ---------------------------------------------------------------------------
# The instruction file is read from where the marking run reads it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", tool_calling_settings_files(), ids=lambda p: p.name
)
def test_this_module_names_the_same_file_the_grader_would(path):
    """The mirror of ``resolve_tool_prompt_path``, checked against the original.

    If someone changes how the marking run finds its instruction file and does
    not change this module, the two answers part company here rather than in a
    cost figure nobody can trace.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert resolve_standing_instructions_path(document) == resolve_tool_prompt_path(
        document
    )


@pytest.mark.parametrize(
    "path", tool_calling_settings_files(), ids=lambda p: p.name
)
def test_every_committed_settings_file_names_an_instruction_file_that_exists(path):
    """A named file that is not there would otherwise be counted as no wording."""
    read = read_grading_caps(path)
    assert read.characters_of_standing_instructions > 0


def test_the_fallback_is_mirrored_too(tmp_path):
    """``prompt.template`` with the filename swapped, exactly as the grader does."""
    document = settings(prompt={"template": "prompts/grader_something_else.md"})
    named = resolve_standing_instructions_path(document)
    assert named == resolve_tool_prompt_path(document)
    assert named.name == FALLBACK_TOOL_TEMPLATE_NAME


def test_the_file_is_counted_in_characters_and_not_in_bytes(tmp_path):
    """The ratio it is divided by is characters per token, so characters it is.

    The committed instruction file holds a handful of multi-byte characters, so
    counting bytes would overstate it — in the safe direction today, but by an
    amount that depends on which characters someone happens to type next.
    """
    wide = tmp_path / "prompts"
    wide.mkdir()
    (wide / "wide.md").write_text("a€b", encoding="utf-8")

    assert standing_instructions_characters(wide / "wide.md") == 3
    assert len((wide / "wide.md").read_bytes()) == 5


def test_the_committed_file_really_does_hold_multibyte_characters():
    """Otherwise the test above is guarding against nothing that is here."""
    named = resolve_standing_instructions_path(
        yaml.safe_load(COMMITTED_SETTINGS.read_text(encoding="utf-8"))
    )
    on_disk = BATCH_RUNNER_ROOT / named
    assert len(on_disk.read_bytes()) > len(on_disk.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A width nobody could read is refused, not priced at nothing
# ---------------------------------------------------------------------------


def test_settings_that_name_no_instruction_file_are_refused(tmp_path):
    document = settings()
    del document["prompt"]
    with pytest.raises(ValueError) as raised:
        read_grading_caps(written(tmp_path, document))
    assert "price the opening at nothing" in str(raised.value)


def test_settings_naming_a_file_that_is_not_there_are_refused(tmp_path):
    document = settings(prompt={"tool_template": "prompts/not_a_real_file.md"})
    with pytest.raises(ValueError) as raised:
        read_grading_caps(written(tmp_path, document))
    message = str(raised.value)
    assert "cannot be guessed" in message
    assert "prompts/not_a_real_file.md" in message


def test_the_refusals_name_the_settings_file(tmp_path):
    """So a person reading a stack of them knows which one to open."""
    document = settings()
    del document["prompt"]
    with pytest.raises(ValueError) as raised:
        read_grading_caps(written(tmp_path, document, "some_marking.yaml"))
    assert "some_marking.yaml" in str(raised.value)


def test_the_new_measurements_have_no_defaults():
    """A default of zero here would be the whole bug, written more quietly.

    Every other limit on this class is required, and these are too, so a future
    caller cannot leave the opening out by forgetting rather than by deciding.
    """
    named = {declared.name: declared for declared in fields(GradingCaps)}
    for measurement in (
        "standing_instructions_path",
        "characters_of_standing_instructions",
        "characters_of_task_prompt_preview",
        "task_prompt_preview_setting",
    ):
        declared = named[measurement]
        assert declared.default is MISSING, (
            f"{measurement} has a default, so a caller can leave the opening "
            "out by forgetting rather than by deciding"
        )
        assert declared.default_factory is MISSING, f"{measurement} has a default"


def test_the_one_measurement_that_does_default_defaults_to_nobody_looked():
    """The scoring line's width is the exception, and it has to be a loud one.

    It cannot be required like the others, because it is not in the settings
    file — it comes from the pinned dataset, and callers that only want to read
    a settings file have no way to supply it. So it defaults. What it must
    never default to is a number: ``None`` makes the check refuse, while a zero
    would make it work out a smaller opening and say nothing.
    """
    declared = {f.name: f for f in fields(GradingCaps)}[
        "characters_of_widest_scoring_line"
    ]
    assert declared.default is None
    assert declared.default_factory is MISSING
    read = read_grading_caps(COMMITTED_SETTINGS)
    assert read.characters_of_widest_scoring_line is None


# ---------------------------------------------------------------------------
# The width counted is the width the judge applies
# ---------------------------------------------------------------------------


def test_the_task_preview_width_is_read_off_the_judge():
    """Not typed here. Moving the judge's default has to move the demand."""
    read = read_grading_caps(COMMITTED_SETTINGS)
    applied = {f.name: f.default for f in fields(ToolCallingJudge)}[
        "task_prompt_truncate"
    ]
    assert read.characters_of_task_prompt_preview == applied


def test_the_judge_really_applies_that_width_to_the_task_wording():
    """The number above is only worth counting if it is the one being used."""
    source = (BATCH_RUNNER_ROOT / "core" / "tool_calling_judge.py").read_text(
        encoding="utf-8"
    )
    assert source.count("[:self.task_prompt_truncate]") >= 1


def test_nothing_carries_the_settings_width_to_the_judge():
    """The reason the applied width is the one counted, stated as a test.

    ``core.grader`` builds the judge without ``task_prompt_truncate``, so the
    setting nine files carry has never taken effect. If someone wires it up,
    this fails and whoever did it can decide which number the cost should use.
    """
    source = (BATCH_RUNNER_ROOT / "core" / "grader.py").read_text(encoding="utf-8")
    construction = source.split("return ToolCallingJudge(", 1)[1].split("\n        )", 1)[0]
    assert "task_prompt_truncate" not in construction
    assert "task_prompt_truncate_chars" not in source


def test_every_task_in_the_catalogue_is_longer_than_the_preview():
    """So the cut is taken in full on the real dataset, never partly.

    If a task shorter than the cut were ever added, the opening this module
    demands would be above the truth for that task. It would still be a demand
    on a plan rather than a charge, but the claim in the docstring would stop
    being exactly true, and it should stop quietly.
    """
    catalog = load_task_catalog()
    width = read_grading_caps(COMMITTED_SETTINGS).characters_of_task_prompt_preview
    shortest = min(task.prompt_character_count for task in catalog.tasks)
    assert shortest > width


# ---------------------------------------------------------------------------
# The opening is added to the demand, and lowering it lowers the demand
# ---------------------------------------------------------------------------


def test_the_demand_is_the_tool_results_plus_the_opening():
    read = caps()
    assert read.input_tokens_one_call_must_cover(THREE) == (
        read.input_tokens_carried_by_tool_results(THREE)
        + read.input_tokens_the_conversation_opens_with(THREE)
    )


def test_the_opening_is_all_three_pieces_and_nothing_else():
    read = caps(
        characters_of_standing_instructions=6_000,
        characters_of_task_prompt_preview=600,
        characters_of_widest_scoring_line=1_200,
    )
    assert read.input_tokens_the_conversation_opens_with(THREE) == 2_600


def test_a_fraction_of_a_token_is_charged_as_a_token():
    read = caps(
        characters_of_standing_instructions=1,
        characters_of_task_prompt_preview=0,
        characters_of_widest_scoring_line=1,
    )
    assert read.input_tokens_the_conversation_opens_with(THREE) == 1


def test_forgetting_the_opening_lowers_the_demand():
    """The direction that matters, measured rather than asserted in prose."""
    with_opening = caps().input_tokens_one_call_must_cover(THREE)
    # One character of scoring line rather than none: a width of zero is
    # refused outright, so this is the smallest opening the module will work
    # out at all.
    without = caps(
        characters_of_standing_instructions=0,
        characters_of_task_prompt_preview=0,
        characters_of_widest_scoring_line=1,
    ).input_tokens_one_call_must_cover(THREE)
    assert without < with_opening
    assert with_opening - without == 2_856


def test_leaving_the_scoring_line_out_of_the_opening_lowers_the_demand():
    """The piece this task added, priced on its own.

    401 tokens a call does not sound like the finding. Multiplied by the calls
    the settings allow across 10,453 scoring lines it is the difference between
    a figure that is a ceiling and a figure that was printed as one.

    The 1,202 characters removed here are 400.67 tokens at three characters a
    token, so the figure the subtraction leaves behind is 400 or 401 depending
    on where the whole sum's rounding-up lands. Both are the same finding.
    """
    whole = caps().input_tokens_one_call_must_cover(THREE)
    almost_without = caps(
        characters_of_widest_scoring_line=1
    ).input_tokens_one_call_must_cover(THREE)
    assert whole - almost_without == 401


def test_a_longer_instruction_file_raises_the_demand_by_itself():
    """No edit to this module. That is the point of reading it rather than typing it."""
    read = caps()
    wider = caps(
        characters_of_standing_instructions=(
            read.characters_of_standing_instructions + 3_000
        )
    )
    assert wider.input_tokens_one_call_must_cover(THREE) == (
        read.input_tokens_one_call_must_cover(THREE) + 1_000
    )


def test_a_plan_that_covers_the_tool_results_but_not_the_opening_is_refused():
    """The exact plan the old rule would have waved through."""
    read = caps()
    just_the_results = read.input_tokens_carried_by_tool_results(THREE)
    problems = input_problems(
        read, grading_input_tokens_per_call=just_the_results
    )
    assert len(problems) == 1
    assert str(read.input_tokens_one_call_must_cover(THREE)) in problems[0]


def test_a_plan_that_covers_the_whole_demand_is_left_alone():
    read = caps()
    assert input_problems(
        read,
        grading_input_tokens_per_call=read.input_tokens_one_call_must_cover(THREE),
    ) == []


def test_the_refusal_names_every_piece_and_where_they_were_read():
    read = caps()
    problems = input_problems(read, grading_input_tokens_per_call=1)
    assert len(problems) == 1
    message = problems[0]
    assert str(read.characters_of_standing_instructions) in message
    assert read.standing_instructions_path in message
    assert str(read.characters_of_task_prompt_preview) in message
    assert str(read.characters_of_widest_scoring_line) in message


def test_the_refusal_no_longer_calls_its_own_figure_a_floor():
    """The demand is complete now, and must not be read as anything less.

    It used to end "and that is still a floor: the scoring line being judged is
    not capped by anything", printed inside a report headed the largest
    possible bill. A sum with an unbounded part has no maximum, so that report
    contradicted itself. The scoring line is bounded by the pinned dataset, it
    is counted, and the sentence has to go with it.
    """
    problems = input_problems(caps(), grading_input_tokens_per_call=1)
    assert "floor" not in problems[0]
    assert "not capped by anything" not in problems[0]
    assert "widest scoring line in the benchmark" in problems[0]


def test_a_width_nobody_measured_is_refused_instead_of_left_out():
    """``None`` means nobody looked, which is not the same as narrow.

    Working out an opening without it would hand back a smaller figure than the
    truth and nothing would say so. That is the shape of every finding on this
    check so far, so the check refuses instead.
    """
    problems = input_problems(caps(characters_of_widest_scoring_line=None))
    assert len(problems) == 1
    assert "never measured" in problems[0]
    assert "does not make it free" in problems[0]

    with pytest.raises(ValueError, match="never measured"):
        caps(
            characters_of_widest_scoring_line=None
        ).input_tokens_the_conversation_opens_with(THREE)


def test_a_width_that_came_out_as_nothing_is_refused_too():
    """No scoring line in this benchmark is blank, so zero is a failed reading.

    A zero would slip past a ``None`` check and price the wording every marking
    call carries at nothing — the same bug, entered by the other door.
    """
    problems = input_problems(caps(characters_of_widest_scoring_line=0))
    assert len(problems) == 1
    assert "came out as nothing" in problems[0]

    with pytest.raises(ValueError, match="came out as"):
        caps(
            characters_of_widest_scoring_line=0
        ).input_tokens_the_conversation_opens_with(THREE)


def test_the_report_names_the_instruction_file_the_way_the_settings_do():
    """Where this check happens to be running from is nobody else's business.

    The settings file is named however the caller named it — that is the
    caller's own string coming back. The instruction file is this module's
    choice, and it has to come out as the settings write it, or two machines
    checking the same plan print two different reports.
    """
    problems = input_problems(caps(), grading_input_tokens_per_call=1)
    assert "prompts/grader_judge_v2.md" in problems[0]
    assert str(BATCH_RUNNER_ROOT / "prompts") not in problems[0]


# ---------------------------------------------------------------------------
# The settings key that reaches nothing
# ---------------------------------------------------------------------------


def test_the_committed_settings_agree_with_what_the_judge_applies():
    """They do today, by coincidence rather than by wiring. Hence the rule below."""
    read = read_grading_caps(COMMITTED_SETTINGS)
    assert read.task_prompt_preview_setting == 500
    assert not read.task_prompt_preview_setting_is_ignored


def test_a_settings_width_the_run_will_not_apply_is_reported(tmp_path):
    document = settings()
    document["grader"]["task_prompt_truncate_chars"] = 5_000
    read = read_grading_caps(written(tmp_path, document))

    assert read.task_prompt_preview_setting == 5_000
    assert read.characters_of_task_prompt_preview == 500
    assert read.task_prompt_preview_setting_is_ignored

    problems = [
        p
        for p in check_assumptions_cover_the_caps(assumptions(), read)
        if "task wording" in p
    ]
    assert len(problems) == 1
    assert "nothing carries that setting to the judge" in problems[0]


def test_settings_that_leave_the_width_out_are_not_accused_of_anything(tmp_path):
    """Silence is not a wrong claim. Only a stated width that does nothing is."""
    document = settings()
    del document["grader"]["task_prompt_truncate_chars"]
    read = read_grading_caps(written(tmp_path, document))

    assert read.task_prompt_preview_setting is None
    assert not read.task_prompt_preview_setting_is_ignored
    assert [
        p for p in check_assumptions_cover_the_caps(assumptions(), read)
        if "task wording" in p
    ] == []


def test_the_ignored_width_is_counted_at_what_is_applied_not_at_what_is_written(
    tmp_path,
):
    """A settings file cannot lower the demand by claiming a narrower cut."""
    document = settings()
    document["grader"]["task_prompt_truncate_chars"] = 1
    read = read_grading_caps(written(tmp_path, document))
    assert read.characters_of_task_prompt_preview == 500


@pytest.mark.parametrize(
    "path", tool_calling_settings_files(), ids=lambda p: p.name
)
def test_the_setting_sits_where_this_module_looks_for_it(path):
    """Nine files carry it. If one moved it, the comparison would go quiet."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    section, key = TASK_PROMPT_TRUNCATE_SETTING
    assert key in (document.get(section) or {})


# ---------------------------------------------------------------------------
# What this changed in the free check, and what it did not
# ---------------------------------------------------------------------------


def test_the_committed_plan_still_records_the_bigger_number():
    """The wording, checked where the plan can no longer draw it.

    The committed plan states the whole figure now, so the free check says
    nothing about it — which is the outcome this rule was for, and which leaves
    this test nowhere to read the wording from. So the plan is lowered here to
    what it used to say. What has to survive is that the note names both halves:
    the 533334 the tool results carry and the 536191 they come to once the
    opening is added, because a note showing only the first would understate
    itself by exactly the amount this rule exists to count.
    """
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = 10_000
    result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    matching = [p for p in result.cost_findings if "input per marking call" in p]
    assert len(matching) == 1
    assert "536191" in matching[0]
    assert "533334" in matching[0]
    assert matching[0] not in result.problems


def test_the_only_thing_this_rule_moved_is_that_one_line(monkeypatch):
    """Machine-independent: the same check, run twice, differing in one place.

    The second run has the opening forced to nothing, which is what the module
    counted before this rule. Everything else in the report — the ceiling, the
    other problems, which run places are blocked — has to come out identical,
    or this change did something beyond what it claims.

    Both runs use a plan lowered to the old flat 10,000, because the difference
    this rule makes is only visible in a note, and the committed plan covers the
    figure so draws no note at all.
    """

    def lowered():
        plan = load_plan(PLAN_PATH)
        plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = 10_000
        return plan

    with_opening = run_envelope_preflight(lowered(), root=BATCH_RUNNER_ROOT)

    import core.execution_envelope_grading_cost as grading_cost

    monkeypatch.setattr(
        grading_cost.GradingCaps,
        "input_tokens_the_conversation_opens_with",
        lambda self, characters_per_token: 0,
    )
    without = run_envelope_preflight(lowered(), root=BATCH_RUNNER_ROOT)

    assert with_opening.may_start == without.may_start
    assert len(with_opening.cost_findings) == len(without.cost_findings)

    differing = [
        (before, after)
        for before, after in zip(
            without.cost_findings, with_opening.cost_findings
        )
        if before != after
    ]
    assert len(differing) == 1
    assert "input per marking call" in differing[0][0]


def test_this_rule_does_not_touch_the_ceiling(monkeypatch):
    """It constrains what a plan may state. It does not restate the sum.

    The ceiling is worked out from the plan's own figures, so counting more of
    what a call carries must not quietly move the dollar total — otherwise two
    numbers would be changing at once and neither could be traced.
    """
    plan = load_plan(PLAN_PATH)
    before = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT).cost

    import core.execution_envelope_grading_cost as grading_cost

    monkeypatch.setattr(
        grading_cost.GradingCaps,
        "input_tokens_the_conversation_opens_with",
        lambda self, characters_per_token: 0,
    )
    after = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT)

    assert before.total_usd == after.cost.total_usd
    assert str(before.total_usd) == "7645.9048453125"


# ---------------------------------------------------------------------------
# What a person reading the description is told
# ---------------------------------------------------------------------------


def test_the_description_says_what_every_call_opens_with():
    lines = describe_grading_caps(read_grading_caps(COMMITTED_SETTINGS))
    opening = [line for line in lines if "opens with" in line]
    assert len(opening) == 1
    assert "prompts/grader_judge_v2.md" in opening[0]
    assert "6866" in opening[0]


def test_the_description_says_the_figure_is_a_ceiling_once_the_width_is_known():
    lines = describe_grading_caps(
        read_grading_caps(
            COMMITTED_SETTINGS,
            widest_scoring_line_characters=real_widest_scoring_line(),
        )
    )
    scoring_line = [line for line in lines if "scoring line it is judging" in line]
    assert len(scoring_line) == 1
    assert str(real_widest_scoring_line()) in scoring_line[0]
    assert "ceiling rather than a floor" in scoring_line[0]
    assert not [line for line in lines if line.startswith("WARNING")]


def test_the_description_warns_rather_than_quoting_a_short_figure():
    """A width nobody handed in must be visible, not absorbed.

    ``describe_grading_caps`` prints an opening worked out from the two pieces
    it can read. With the third missing that opening is below what a call
    carries, and the reader has to be told, because a figure with a piece
    silently left out is exactly what this task exists to remove.
    """
    lines = describe_grading_caps(read_grading_caps(COMMITTED_SETTINGS))
    warnings = [line for line in lines if line.startswith("WARNING")]
    assert len(warnings) == 1
    assert "never measured" in warnings[0]
    assert "below what one call carries" in warnings[0]


def test_the_description_no_longer_calls_anything_uncapped():
    """The description must not leave a reader thinking a piece is free.

    The sentence this task exists to delete named three things as uncapped, and
    the previous task read two of them from disk. The third is read from the
    pinned dataset now, so nothing in these lines may still claim a part of a
    marking call is unbounded.
    """
    lines = describe_grading_caps(
        read_grading_caps(
            COMMITTED_SETTINGS,
            widest_scoring_line_characters=real_widest_scoring_line(),
        )
    )
    assert [line for line in lines if "not capped" in line] == []
    assert not any(
        re.search(r"first \d+ characters of the task", line) for line in lines
    )


def test_the_description_flags_a_width_that_does_nothing(tmp_path):
    document = settings()
    document["grader"]["task_prompt_truncate_chars"] = 9_000
    lines = describe_grading_caps(read_grading_caps(written(tmp_path, document)))
    assert any("9000" in line and "nothing carries" in line for line in lines)


def test_the_written_out_form_carries_the_new_measurements():
    written_out = read_grading_caps(COMMITTED_SETTINGS).as_dict()
    assert written_out["standing_instructions_read_from"] == (
        "prompts/grader_judge_v2.md"
    )
    assert written_out["characters_of_standing_instructions"] == 6866
    assert written_out["characters_of_task_wording_shown"] == 500
    assert written_out["task_wording_width_named_by_the_settings"] == 500
    assert written_out["the_settings_width_is_ignored"] is False
    assert written_out["characters_of_widest_scoring_line"] is None

    measured = read_grading_caps(
        COMMITTED_SETTINGS,
        widest_scoring_line_characters=real_widest_scoring_line(),
    ).as_dict()
    assert measured["characters_of_widest_scoring_line"] == (
        real_widest_scoring_line()
    )


def test_the_module_says_out_loud_what_it_used_to_get_wrong():
    """Not tidiness. A module that quietly corrects itself teaches nobody.

    The old claim is quoted in the docstring so the next reader can see what
    the wrong answer looked like, and it has to be quoted *as* wrong — the
    sentence naming the mistake is what stops the quotation reading as current.
    """
    import core.execution_envelope_grading_cost as grading_cost

    assert "wrote one of those caps down in prose" in grading_cost.__doc__
    assert (
        "The third piece was the contradiction this module printed in its own "
        "report." in grading_cost.__doc__
    )
    assert "has never done anything at all" in grading_cost.__doc__


def test_the_tool_result_half_is_unchanged():
    """This task added to the demand. It must not have altered what was there."""
    read = caps()
    assert read.input_tokens_carried_by_tool_results(THREE) == 533_334
    assert read.tool_calls_per_rubric_item * read.characters_per_tool_result == (
        8 * MAX_CONTENT_CHARS
    )
