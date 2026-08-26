"""Every marking conversation opens with wording this repository pins.

``core.execution_envelope_grading_cost`` demands a floor on how many input
tokens one marking call can carry, and refuses a plan that states less. Until
this file existed the floor counted the tool results and nothing else. Its own
docstring explained why: what the conversation *starts* with — the standing
instructions, the scoring line, "the first 500 characters of the task" — "is
not capped by anything".

Two of those three are capped, and one of the caps was written down in prose in
the sentence that denied it.

* The standing instructions are a committed file. ``prompt.tool_template``
  names it in all nine settings files, the judge splits it and sends both
  halves on every single call, and it is 6,263 characters long today.
* The task preview is cut to ``ToolCallingJudge.task_prompt_truncate``
  characters, which is 500, and every task in the committed catalogue is longer
  than that — so the cut is always taken in full.

Leaving them out made the demanded floor *lower* than the truth. That is the
direction that costs money: a plan clears a floor that is too low and is
recorded as having been checked. The tests here hold the floor to the two
capped pieces, hold the module to reading them from where the marking run reads
them, and hold it to still saying out loud that the third piece is uncapped.

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
from core.execution_envelope_tasks import load_task_catalog
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


def caps(**overrides) -> GradingCaps:
    base = read_grading_caps(COMMITTED_SETTINGS)
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


def test_the_opening_is_both_pieces_and_nothing_else():
    read = caps(
        characters_of_standing_instructions=6_000,
        characters_of_task_prompt_preview=600,
    )
    assert read.input_tokens_the_conversation_opens_with(THREE) == 2_200


def test_a_fraction_of_a_token_is_charged_as_a_token():
    read = caps(
        characters_of_standing_instructions=1,
        characters_of_task_prompt_preview=0,
    )
    assert read.input_tokens_the_conversation_opens_with(THREE) == 1


def test_forgetting_the_opening_lowers_the_demand():
    """The direction that matters, measured rather than asserted in prose."""
    with_opening = caps().input_tokens_one_call_must_cover(THREE)
    without = caps(
        characters_of_standing_instructions=0,
        characters_of_task_prompt_preview=0,
    ).input_tokens_one_call_must_cover(THREE)
    assert without < with_opening
    assert with_opening - without == 2_255


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


def test_the_refusal_names_both_pieces_and_where_they_were_read():
    read = caps()
    problems = input_problems(read, grading_input_tokens_per_call=1)
    assert len(problems) == 1
    message = problems[0]
    assert str(read.characters_of_standing_instructions) in message
    assert read.standing_instructions_path in message
    assert str(read.characters_of_task_prompt_preview) in message


def test_the_refusal_still_says_the_scoring_line_is_not_capped():
    """The demand is bigger, not complete. A reader must not read it as complete."""
    problems = input_problems(caps(), grading_input_tokens_per_call=1)
    assert "still a floor" in problems[0]
    assert "scoring line being judged is not capped" in problems[0]


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


def test_the_committed_plan_is_still_refused_and_by_a_bigger_number():
    plan = load_plan(PLAN_PATH)
    result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    matching = [p for p in result.problems if "input per marking call" in p]
    assert len(matching) == 1
    assert "535589" in matching[0]
    assert "533334" in matching[0]


def test_the_only_thing_this_rule_moved_is_that_one_line(monkeypatch):
    """Machine-independent: the same check, run twice, differing in one place.

    The second run has the opening forced to nothing, which is what the module
    counted before this rule. Everything else in the report — the ceiling, the
    other problems, which run places are blocked — has to come out identical,
    or this change did something beyond what it claims.
    """
    plan = load_plan(PLAN_PATH)
    with_opening = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    import core.execution_envelope_grading_cost as grading_cost

    monkeypatch.setattr(
        grading_cost.GradingCaps,
        "input_tokens_the_conversation_opens_with",
        lambda self, characters_per_token: 0,
    )
    without = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT)

    assert with_opening.may_start == without.may_start
    assert len(with_opening.problems) == len(without.problems)

    differing = [
        (before, after)
        for before, after in zip(without.problems, with_opening.problems)
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
    assert str(before.total_usd) == "363.58481250"


# ---------------------------------------------------------------------------
# What a person reading the description is told
# ---------------------------------------------------------------------------


def test_the_description_says_what_every_call_opens_with():
    lines = describe_grading_caps(read_grading_caps(COMMITTED_SETTINGS))
    opening = [line for line in lines if "opens with" in line]
    assert len(opening) == 1
    assert "prompts/grader_judge_v2.md" in opening[0]
    assert "6263" in opening[0]


def test_the_description_still_says_the_figure_is_a_floor():
    lines = describe_grading_caps(read_grading_caps(COMMITTED_SETTINGS))
    assert any(
        "not capped is the scoring line" in line and "floor" in line
        for line in lines
    )


def test_the_description_says_only_the_scoring_line_is_uncapped():
    """The description must not leave a reader thinking the opening is free.

    Exactly one line may talk about something being uncapped, and it has to be
    the scoring line. The sentence this task exists to delete named three
    things there, two of which are read from disk now.
    """
    lines = describe_grading_caps(read_grading_caps(COMMITTED_SETTINGS))
    uncapped = [line for line in lines if "not capped" in line]
    assert len(uncapped) == 1
    assert "scoring line" in uncapped[0]
    assert "standing instructions" not in uncapped[0]
    assert not re.search(r"first \d+ characters of the task", uncapped[0])


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
    assert written_out["characters_of_standing_instructions"] == 6263
    assert written_out["characters_of_task_wording_shown"] == 500
    assert written_out["task_wording_width_named_by_the_settings"] == 500
    assert written_out["the_settings_width_is_ignored"] is False


def test_the_module_says_out_loud_what_it_used_to_get_wrong():
    """Not tidiness. A module that quietly corrects itself teaches nobody.

    The old claim is quoted in the docstring so the next reader can see what
    the wrong answer looked like, and it has to be quoted *as* wrong — the
    sentence naming the mistake is what stops the quotation reading as current.
    """
    import core.execution_envelope_grading_cost as grading_cost

    assert "wrote one of those caps down in prose" in grading_cost.__doc__
    assert "The third piece really is uncapped" in grading_cost.__doc__
    assert "has never done anything at all" in grading_cost.__doc__


def test_the_tool_result_half_is_unchanged():
    """This task added to the demand. It must not have altered what was there."""
    read = caps()
    assert read.input_tokens_carried_by_tool_results(THREE) == 533_334
    assert read.tool_calls_per_rubric_item * read.characters_per_tool_result == (
        8 * MAX_CONTENT_CHARS
    )
