"""The marking half of the cost ceiling must rest on limits, not on averages.

``core.execution_envelope_cost`` promises that every number in it is a ceiling.
The half that prices running the tasks keeps that promise. The half that prices
marking rested on three numbers typed into the plan by hand, two of which this
repository's own marking settings already bound — and it named neither of the
two extra models marking is allowed to call.

These tests pin all of that down. The one that matters most is
``test_the_limits_read_match_the_judge_the_grader_really_builds``: it builds the
real judge from the real settings and compares, so this module cannot drift away
from what marking would actually do.

Nothing here calls a model, marks anything, or spends anything.
"""

from __future__ import annotations

import io
import tokenize
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from core.execution_envelope_cost import (
    CostAssumptions,
    ModelPrice,
    load_price_table,
)
from core.execution_envelope_grading_cost import (
    DEFAULT_AUDIO_CALLS_PER_TASK,
    DEFAULT_VISUAL_CALLS_PER_TASK,
    GradingCaps,
    check_assumptions_cover_the_caps,
    describe_grading_caps,
    read_grading_caps,
)
from core.execution_envelope_preflight import (
    _check_grading_assumptions_match_the_settings,
    describe_preflight,
    run_envelope_preflight,
)
from core.tool_calling_judge import ToolCallingJudge

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
GRADING_CONFIG_DIRECTORY = BATCH_RUNNER_ROOT / "grading_configs"
COMMITTED_PLAN = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def tool_calling_config_paths() -> list[Path]:
    """Every committed marking settings file that uses the tool-calling judge.

    The archived version-one settings are left out because they do not build a
    tool-calling judge at all, so there is no loop for these limits to bound.
    """
    found: list[Path] = []
    for path in sorted(GRADING_CONFIG_DIRECTORY.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue
        tools = ((document.get("judge") or {}).get("tools") or {})
        if "read_deliverable" in tools:
            found.append(path)
    return found


def settings(**overrides) -> dict:
    """A minimal marking settings document that builds a tool-calling judge."""
    document = {
        "judge": {
            "model": "gpt-5.4",
            "generation": {"max_output_tokens": 2400},
            "tools": {
                "read_deliverable": {
                    "per_item_call_cap": 8,
                    "max_iterations": 10,
                }
            },
        },
        "grader": {"judge_max_retries": 1},
    }
    document.update(overrides)
    return document


def written(tmp_path: Path, document, name: str = "marking.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def assumptions(**overrides) -> CostAssumptions:
    """A cost sum whose marking numbers sit exactly on the limits above."""
    raw = {
        "characters_per_token": "3.0",
        "instruction_character_count": 100,
        "tool_loop_max_model_turns": {"host_python_process": 1},
        "output_tokens_capped_per_attempt": {"host_python_process": False},
        "max_tool_result_tokens_per_turn": {"host_python_process": 0},
        "safety_multiplier": "1.25",
        "grading_required": True,
        "grading_model": "gpt-5.4",
        "grading_calls_per_rubric_item": 11,
        "grading_input_tokens_per_call": 10000,
        "grading_output_tokens_per_call": 2400,
    }
    raw.update(overrides)
    return CostAssumptions.from_mapping(raw)


def caps(**overrides) -> GradingCaps:
    base = GradingCaps(
        settings_path="marking.yaml",
        judge_model="gpt-5.4",
        judge_calls_per_rubric_item=11,
        tool_calls_per_rubric_item=8,
        output_tokens_per_call=2400,
        visual_model=None,
        visual_calls_per_task=0,
        audio_model=None,
        audio_calls_per_task=0,
    )
    return replace(base, **overrides)


# ---------------------------------------------------------------------------
# The limits read here must be the limits marking really applies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config_path", tool_calling_config_paths(), ids=lambda p: p.name
)
def test_the_limits_read_match_the_judge_the_grader_really_builds(config_path):
    """Build the real judge from the real settings and compare every limit.

    This is the test that stops this module from quoting numbers that marking
    no longer uses. If somebody changes how ``core/grader.py`` reads a limit,
    or changes what it falls back to, the two sides stop agreeing here.
    """
    from core.grader import Grader

    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    grader = Grader(
        document,
        rubric_loader=None,
        client=SimpleNamespace(responses=SimpleNamespace(create=None)),
    )
    judge = grader._tool_judge
    assert judge is not None, f"{config_path.name} built no tool-calling judge"

    read = read_grading_caps(config_path)

    assert read.judge_model == judge.model
    assert read.judge_calls_per_rubric_item == (
        judge.max_iterations + judge.finalization_retries
    )
    assert read.tool_calls_per_rubric_item == judge.per_item_tool_call_cap
    assert read.output_tokens_per_call == judge.max_output_tokens

    vision = judge.vision_perception
    if vision is None:
        assert read.visual_model is None
        assert read.visual_calls_per_task == 0
    else:
        assert read.visual_model == vision.deployment
        assert read.visual_calls_per_task == vision.call_cap

    audio = judge.audio_perception
    if audio is None:
        assert read.audio_model is None
        assert read.audio_calls_per_task == 0
    else:
        assert read.audio_model == audio.deployment
        assert read.audio_calls_per_task == audio.call_cap


def test_every_committed_marking_settings_file_can_be_read():
    assert tool_calling_config_paths(), "no tool-calling marking settings found"
    for path in tool_calling_config_paths():
        read_grading_caps(path)


def test_a_missing_limit_falls_back_to_what_the_judge_itself_defaults_to(
    tmp_path,
):
    document = settings()
    document["judge"]["tools"]["read_deliverable"] = {}
    document["judge"]["generation"] = {}
    document["grader"] = {}
    read = read_grading_caps(written(tmp_path, document))

    judge = ToolCallingJudge(client=None, model="gpt-5.4", prompt_template="x")
    assert read.judge_calls_per_rubric_item == (
        judge.max_iterations + judge.finalization_retries
    )
    assert read.tool_calls_per_rubric_item == judge.per_item_tool_call_cap
    assert read.output_tokens_per_call == judge.max_output_tokens


def test_the_finalisation_retry_is_clamped_the_way_the_judge_clamps_it(tmp_path):
    """The judge caps the retry at one however large the setting is.

    A cost sum that believed a setting of five meant five extra turns would be
    counting turns that cannot happen, which is the mirror image of the fault
    this module exists to catch.
    """
    document = settings()
    document["grader"]["judge_max_retries"] = 5
    read = read_grading_caps(written(tmp_path, document))
    assert read.judge_calls_per_rubric_item == 11

    judge = ToolCallingJudge(
        client=None, model="gpt-5.4", prompt_template="x", finalization_retries=5
    )
    assert judge.finalization_retries == 1


def test_settings_that_are_not_there_are_refused(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        read_grading_caps(tmp_path / "nothing.yaml")


def test_settings_that_are_not_a_mapping_are_refused(tmp_path):
    path = tmp_path / "marking.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a mapping"):
        read_grading_caps(path)


def test_settings_that_name_no_model_are_refused(tmp_path):
    document = settings()
    document["judge"].pop("model")
    with pytest.raises(ValueError, match="no model"):
        read_grading_caps(written(tmp_path, document))


def test_a_deployment_name_is_preferred_over_a_model_name(tmp_path):
    """``core/grader.py`` marks with the deployment when one is named."""
    document = settings()
    document["judge"]["deployment"] = "gpt-5.6-sol"
    assert read_grading_caps(written(tmp_path, document)).judge_model == (
        "gpt-5.6-sol"
    )


# ---------------------------------------------------------------------------
# Perception: two models the sum never named
# ---------------------------------------------------------------------------


def test_a_perception_block_that_names_nothing_is_not_counted(tmp_path):
    document = settings()
    document["judge"]["perception"] = {
        "visual": {"call_cap_per_task": 72},
        "audio": {"call_cap_per_task": 3},
    }
    read = read_grading_caps(written(tmp_path, document))
    assert read.visual_model is None
    assert read.audio_model is None
    assert read.visual_calls_per_task == 0
    assert read.audio_calls_per_task == 0


def test_a_perception_block_naming_only_a_deployment_still_counts(tmp_path):
    document = settings()
    document["judge"]["perception"] = {"visual": {"deployment": "gpt-5.4"}}
    read = read_grading_caps(written(tmp_path, document))
    assert read.visual_model == "gpt-5.4"
    assert read.visual_calls_per_task == DEFAULT_VISUAL_CALLS_PER_TASK


def test_a_perception_block_with_no_stated_limit_uses_the_graders_fallback(
    tmp_path,
):
    document = settings()
    document["judge"]["perception"] = {
        "visual": {"model": "gpt-5.4"},
        "audio": {"model": "gpt-audio-1.5"},
    }
    read = read_grading_caps(written(tmp_path, document))
    assert read.visual_calls_per_task == DEFAULT_VISUAL_CALLS_PER_TASK
    assert read.audio_calls_per_task == DEFAULT_AUDIO_CALLS_PER_TASK


def test_each_model_the_marking_can_call_is_named_once(tmp_path):
    """Marking and picture reading often share one model. It counts once."""
    document = settings()
    document["judge"]["perception"] = {
        "visual": {"model": "gpt-5.4", "call_cap_per_task": 72},
        "audio": {"model": "gpt-audio-1.5", "call_cap_per_task": 3},
    }
    read = read_grading_caps(written(tmp_path, document))
    assert read.models_the_marking_can_call == ("gpt-5.4", "gpt-audio-1.5")


# ---------------------------------------------------------------------------
# Comparing the written sum against the limits
# ---------------------------------------------------------------------------


def test_a_sum_that_sits_on_every_limit_reports_nothing():
    assert check_assumptions_cover_the_caps(assumptions(), caps()) == []


def test_a_sum_above_every_limit_reports_nothing():
    stated = assumptions(
        grading_calls_per_rubric_item=20, grading_output_tokens_per_call=9999
    )
    assert check_assumptions_cover_the_caps(stated, caps()) == []


def test_a_sum_below_the_call_limit_is_reported():
    stated = assumptions(grading_calls_per_rubric_item=1)
    problems = check_assumptions_cover_the_caps(stated, caps())
    assert len(problems) == 1
    assert "11 times about one line" in problems[0]


def test_a_sum_below_the_reply_limit_is_reported():
    stated = assumptions(grading_output_tokens_per_call=1000)
    problems = check_assumptions_cover_the_caps(stated, caps())
    assert len(problems) == 1
    assert "2400" in problems[0]


def test_pricing_the_wrong_model_is_reported():
    stated = assumptions(grading_model="gpt-5.4-nano")
    problems = check_assumptions_cover_the_caps(stated, caps())
    assert len(problems) == 1
    assert "gpt-5.4-nano" in problems[0] and "gpt-5.4" in problems[0]


def test_picture_reading_the_sum_counts_none_of_is_reported():
    problems = check_assumptions_cover_the_caps(
        assumptions(),
        caps(visual_model="gpt-5.4", visual_calls_per_task=72),
    )
    assert len(problems) == 1
    assert "72 times per task" in problems[0]
    assert "counts none of it" in problems[0]


def test_sound_listening_the_sum_counts_none_of_is_reported():
    problems = check_assumptions_cover_the_caps(
        assumptions(),
        caps(audio_model="gpt-audio-1.5", audio_calls_per_task=3),
    )
    assert len(problems) == 1
    assert "gpt-audio-1.5" in problems[0]


def test_a_perception_model_switched_on_with_a_zero_limit_is_not_reported():
    """No calls allowed means nothing to count, so nothing to complain about."""
    problems = check_assumptions_cover_the_caps(
        assumptions(), caps(visual_model="gpt-5.4", visual_calls_per_task=0)
    )
    assert problems == []


def test_an_unpriced_model_is_reported_as_unknown_rather_than_free():
    """The rule already exists; the marking half just never triggered it.

    ``check_cost_ceiling`` refuses a run when a model has no published price,
    on the stated grounds that an unpriced model would otherwise be counted as
    free. Marking never named its perception models, so that refusal never had
    the chance to fire for them.
    """
    prices = {"gpt-5.4": ModelPrice("gpt-5.4", Decimal("1.25"), Decimal("5.00"))}
    problems = check_assumptions_cover_the_caps(
        assumptions(),
        caps(audio_model="gpt-audio-1.5", audio_calls_per_task=3),
        prices=prices,
    )
    assert len(problems) == 2
    assert "it is not zero" in problems[1]


def test_a_priced_perception_model_is_still_reported_as_uncounted():
    """Being priced does not make an uncounted call free."""
    prices = {"gpt-5.4": ModelPrice("gpt-5.4", Decimal("1.25"), Decimal("5.00"))}
    problems = check_assumptions_cover_the_caps(
        assumptions(),
        caps(visual_model="gpt-5.4", visual_calls_per_task=72),
        prices=prices,
    )
    assert len(problems) == 1
    assert "counts none of it" in problems[0]


def test_no_price_list_does_not_become_a_claim_that_everything_is_priced():
    """Passing no prices must not silently assert every model has one."""
    problems = check_assumptions_cover_the_caps(
        assumptions(),
        caps(audio_model="gpt-audio-1.5", audio_calls_per_task=3),
        prices=None,
    )
    assert len(problems) == 1
    assert "it is not zero" not in problems[0]


def test_a_plan_that_marks_nothing_reports_nothing():
    stated = assumptions(grading_required=False, grading_calls_per_rubric_item=0)
    assert check_assumptions_cover_the_caps(stated, caps()) == []


# ---------------------------------------------------------------------------
# What a person reads
# ---------------------------------------------------------------------------


def test_the_description_says_which_number_is_not_a_ceiling():
    """The input length per call cannot be pinned, and that is said out loud.

    Leaving it unsaid would let a reader believe the whole marking sum became a
    ceiling when one number in it is still an average of runs that happened.
    """
    lines = describe_grading_caps(caps())
    assert any("is not a ceiling" in line for line in lines)


def test_the_description_names_the_file_it_read():
    lines = describe_grading_caps(caps(settings_path="somewhere/else.yaml"))
    assert any("somewhere/else.yaml" in line for line in lines)


def test_switched_off_perception_is_described_as_switched_off():
    lines = describe_grading_caps(caps())
    assert any("reading pictures: switched off" in line for line in lines)
    assert any("listening to sound: switched off" in line for line in lines)


# ---------------------------------------------------------------------------
# Wired into the free check
# ---------------------------------------------------------------------------


def test_a_plan_that_marks_but_names_no_settings_is_a_problem(tmp_path):
    """Nothing looked is not the same as the numbers being high enough."""
    problems = _check_grading_assumptions_match_the_settings(
        {}, assumptions(), root=tmp_path
    )
    assert len(problems) == 1
    assert "names no marking settings file" in problems[0]


def test_a_plan_that_marks_nothing_needs_no_settings(tmp_path):
    stated = assumptions(grading_required=False)
    assert (
        _check_grading_assumptions_match_the_settings({}, stated, root=tmp_path)
        == []
    )


def test_settings_the_plan_names_but_that_are_not_there_are_a_problem(tmp_path):
    problems = _check_grading_assumptions_match_the_settings(
        {"grading_config": "nowhere.yaml"}, assumptions(), root=tmp_path
    )
    assert len(problems) == 1
    assert "could not be read" in problems[0]


def test_the_problem_names_the_file_the_way_the_plan_does(tmp_path):
    """Where the check happens to run from is nobody else's business."""
    document = settings()
    document["judge"]["generation"]["max_output_tokens"] = 4000
    (tmp_path / "settings").mkdir()
    written(tmp_path / "settings", document, "marking.yaml")
    problems = _check_grading_assumptions_match_the_settings(
        {"grading_config": "settings/marking.yaml"},
        assumptions(),
        root=tmp_path,
    )
    assert len(problems) == 1
    assert "settings/marking.yaml" in problems[0]
    assert str(tmp_path) not in problems[0]


# ---------------------------------------------------------------------------
# The committed plan, as it stands today
# ---------------------------------------------------------------------------


def committed_plan() -> dict:
    return yaml.safe_load(COMMITTED_PLAN.read_text(encoding="utf-8"))


def test_the_committed_plan_names_marking_settings_that_exist():
    named = committed_plan().get("grading_config")
    assert named, "the plan must name the settings its answers are marked with"
    assert (BATCH_RUNNER_ROOT / str(named)).is_file()


def test_the_committed_plan_marking_sum_is_below_the_limits_today():
    """Pin the finding so it cannot be undone without this failing.

    Every one of these is a way the largest possible bill is larger than the
    number the run is being checked against. Raising the stated numbers to meet
    the limits is what makes this pass; deleting the check is not.
    """
    plan = committed_plan()
    problems = _check_grading_assumptions_match_the_settings(
        plan,
        CostAssumptions.from_mapping(plan["cost"]["assumptions"]),
        root=BATCH_RUNNER_ROOT,
    )
    joined = " | ".join(problems)
    assert "marking calls per scoring line" in joined
    assert "tokens of reply per marking call" in joined
    assert "reading pictures" in joined
    assert "listening to sound" in joined
    assert "it is not zero" in joined


def test_the_sound_model_the_marking_can_call_is_still_unpriced():
    """If somebody publishes a price for it, this should be updated, not deleted.

    The point of the check is not that this model is missing from the list. It
    is that marking can call a model the cost sum never named, and a model that
    is not in the list cannot be priced at all.
    """
    read = read_grading_caps(
        BATCH_RUNNER_ROOT / str(committed_plan()["grading_config"])
    )
    assert read.audio_model == "gpt-audio-1.5"
    assert read.audio_model not in load_price_table()


# ---------------------------------------------------------------------------
# The printed total must carry its own caveat
# ---------------------------------------------------------------------------


def preflight_on_the_committed_plan():
    return run_envelope_preflight(
        committed_plan(),
        root=BATCH_RUNNER_ROOT,
        docker_daemon_available=False,
        docker_image_available=False,
        environ={},
    )


def test_the_printed_total_says_it_is_too_low_while_marking_is_uncounted():
    """A reader who only looks at the total must still be told it is short.

    The lines below are printed under a heading calling them the largest
    possible bill. Reporting the shortfall further down the page and leaving
    the total to read as final is how a known-low number gets quoted as a
    ceiling.
    """
    result = preflight_on_the_committed_plan()
    assert result.grading_ceiling_problems
    warnings = [
        line for line in describe_preflight(result) if line.startswith("WARNING")
    ]
    assert len(warnings) == 1
    assert "not a ceiling" in warnings[0]
    assert "too low" in warnings[0]


def test_no_caveat_is_printed_once_the_marking_half_is_a_ceiling():
    """The warning must disappear when it stops being true, and only then."""
    result = replace(preflight_on_the_committed_plan(), grading_ceiling_problems=[])
    assert not [
        line for line in describe_preflight(result) if line.startswith("WARNING")
    ]


def test_the_written_answer_says_whether_the_marking_half_is_a_ceiling():
    """Anything reading the answer as data gets the same fact as a reader."""
    result = preflight_on_the_committed_plan()
    written_out = result.as_dict()
    assert written_out["marking_half_is_a_ceiling"] is False
    assert written_out["grading_ceiling_problems"] == result.grading_ceiling_problems
    for problem in result.grading_ceiling_problems:
        assert problem in written_out["problems"]


def test_reading_the_limits_calls_nothing_and_spends_nothing():
    """Nothing in this module reaches a provider.

    Read from the module's own code rather than trusted from its wording, so
    that adding a client to it fails here instead of on a bill. Comments and
    text are stripped out first and whole words are compared, because the
    module explains in prose what it does not do, and describing a thing must
    not read as doing it.
    """
    source = (
        BATCH_RUNNER_ROOT / "core" / "execution_envelope_grading_cost.py"
    ).read_text(encoding="utf-8")
    names = {
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.NAME
    }
    for forbidden in (
        "responses",
        "AzureOpenAI",
        "OpenAI",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "subprocess",
        "eval",
        "exec",
        "open",
    ):
        assert forbidden not in names, f"{forbidden} must not appear here"
