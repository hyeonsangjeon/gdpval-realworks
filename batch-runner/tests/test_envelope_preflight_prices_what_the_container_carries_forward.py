"""What the container's second question carries is measured, not estimated.

The cost sum charges ``max_tool_result_tokens_per_turn`` for everything that
sits in front of the model on a later turn without being the task or the
model's own words. For the container the plan writes ``0``, and justifies it in
its own sentence: the model "is asked once and nothing is carried forward".

That sentence is true only while ``experiments/execution_envelope/
exp031_envelope_docker_container.yaml`` says ``repair: enabled: false``. It is
one line, nothing outside it holds it in place, and ``core/sandbox_runner.py``
builds its repair settings as ``{"enabled": True, "max_attempts": 1, **(repair
or {})}`` — so deleting the block turns the loop on rather than off. Task #27
made the turn count itself readable and refused a plan that priced too few
turns. Task #31 priced what the extra turn carries, but priced only three of
its parts.

Those three were the stdout tail, the stderr tail and the failure tail: 2,200
characters, 734 tokens at the plan's three-characters-per-token ratio. The
other parts were waved off as having no stated width — and that was wrong about
every one of them. ``render_reflection`` trims the blocking errors to twelve
lines and the warnings to six; the repair guidance comes out of a prompt file
committed to this repository; the opening, the instruction, the close and every
heading are strings; and a deliverable contract section is appended on every
repair prompt whatever the task. None of that is unknowable. It just had not
been counted.

So it is counted now, by building the widest repair prompt the committed wording
allows through the same :func:`render_reflection` a repair turn renders with,
and reporting what each part came to. The answer is 3,922 characters — 1,308
tokens, about seventy-eight per cent more than the figure it replaces. No test
in this file types 3,922 or 1,308: every one of them asks the source.

Two things stay outside the figure, in opposite directions. The English the run
writes onto each blocking-error and warning line is settled by the task and the
failure, so the widest prompt is measured with those lines empty and a real one
is longer. The model's own earlier code is left out on purpose — the words
placed around it are counted, the code between them is not, because
``max_input_tokens_per_attempt`` already charges a full ``max_output_tokens``
for every earlier answer and billing it here would bill it twice.

Measured against the committed plan with repair switched on at one attempt, the
whole ceiling moves by a few pennies. That is small, and saying so is part of
the finding: what was wrong here is a figure that was too low for a reason the
source could have settled, not a large sum.

Nothing here calls a model, runs a container, or spends anything.
"""

from __future__ import annotations

import copy
import math
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_preflight import (  # noqa: E402
    _check_the_plan_counts_what_the_container_carries_forward,
    _container_carried_forward_characters,
    check_experiment_files_match_conditions,
    conditions_from_plan,
    load_plan,
    run_envelope_preflight,
)
from core.sandbox_runner import (  # noqa: E402
    EXECUTION_ERROR_TAIL_CHARS,
    REFLECTION_MAX_BLOCKING_ERRORS,
    REFLECTION_MAX_WARNINGS,
    REFLECTION_PRIOR_CODE_MAX_CHARS,
    REFLECTION_STDERR_TAIL_CHARS,
    REFLECTION_STDOUT_TAIL_CHARS,
    SandboxRunner,
    _sanitize_tail,
    execution_failure_blocking_error,
    narrowest_contract_section,
    reflection_strings,
    render_reflection,
    widest_repair_prompt_characters,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
CONTAINER_FILE = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "exp031_envelope_docker_container.yaml"
)
PROMPT_FILE = BATCH_RUNNER_ROOT / "prompts" / "sandbox_occupation_codegen.yaml"

#: The three widths this check used to count, and nothing else. Kept only so a
#: test can prove the new figure is larger than the one it replaced.
THE_THREE_TAILS_IT_USED_TO_COUNT = (
    REFLECTION_STDOUT_TAIL_CHARS
    + REFLECTION_STDERR_TAIL_CHARS
    + EXECUTION_ERROR_TAIL_CHARS
)

#: A committed prompt file that is not a repair prompt at all: it has neither
#: of the two keys ``load_prompt`` requires, so naming it is a real, unfaked way
#: for the measurement to fail.
A_COMMITTED_FILE_THAT_IS_NOT_A_PROMPT = "agentic_sandbox_solver"


def _plan(**assumption_overrides) -> dict:
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"].update(assumption_overrides)
    return plan


def _priced_at(tokens: int) -> dict:
    return _plan(
        max_tool_result_tokens_per_turn={
            "host_python_process": 0,
            "docker_container": tokens,
            "azure_code_interpreter": 5000,
        }
    )


def _container_settings(**sandbox_overrides) -> dict:
    settings = yaml.safe_load(CONTAINER_FILE.read_text(encoding="utf-8"))
    settings = copy.deepcopy(settings)
    settings["execution"]["sandbox"].update(sandbox_overrides)
    return settings


def _repairing_container(max_attempts: int = 1, **sandbox_overrides) -> dict:
    return _container_settings(
        repair={"enabled": True, "max_attempts": max_attempts},
        **sandbox_overrides,
    )


def _refusals(settings: dict, plan: dict | None = None) -> list[str]:
    return _check_the_plan_counts_what_the_container_carries_forward(
        {"docker_container": settings}, plan if plan is not None else _plan()
    )


def _measured() -> dict[str, int]:
    return _container_carried_forward_characters(_repairing_container())


def _characters() -> int:
    return sum(_measured().values())


def _tokens(ratio: float = 3.0) -> int:
    return math.ceil(_characters() / ratio)


class _ContractStub:
    """Stands in for a deliverable contract in the behavioural tests below."""

    def to_prompt_section(self) -> str:
        return "[CONTRACT]"


# ── The figure is a repair prompt that was really built ───────────────────


def test_the_parts_come_to_the_length_of_a_prompt_this_test_builds_itself():
    """The strongest claim here: the parts are a real prompt, cut into pieces.

    The measurement adds one part at a time and records what each addition cost,
    which is only trustworthy if the pieces come back to the whole. So this
    assembles the same widest prompt independently — the runner's own limits, its
    own render function, its own contract section — and holds the total against
    it. The stand-in character for the model's earlier code is taken off, because
    the measurement counts the words around that code and not the code.
    """
    prompt_data = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))
    built = render_reflection(
        strings=reflection_strings(prompt_data),
        contract_section=narrowest_contract_section(),
        blocking_errors=(
            [execution_failure_blocking_error(None, "x" * EXECUTION_ERROR_TAIL_CHARS)]
            + [""] * (REFLECTION_MAX_BLOCKING_ERRORS - 1)
        ),
        guidance=list(prompt_data["repair_guidance"].values()),
        warnings=[""] * REFLECTION_MAX_WARNINGS,
        stdout_tail="o" * REFLECTION_STDOUT_TAIL_CHARS,
        stderr_tail="e" * REFLECTION_STDERR_TAIL_CHARS,
        code="c",
    )
    assert _characters() == len(built) - len("c")


def test_every_part_of_the_prompt_is_worth_something():
    """A part measured at nothing is a part the measurement never reached."""
    for what, width in _measured().items():
        assert width > 0, f"{what} was counted as nothing"


def test_each_part_is_described_so_a_reader_knows_what_it_is():
    """The refusal quotes these, so they have to read as English."""
    for what in _measured():
        assert what == what.lower()
        assert len(what.split()) >= 4


def test_the_parts_name_everything_the_render_can_hold():
    named = " ".join(_measured()).lower()
    for part in (
        "blocking-error",
        "warning",
        "guidance",
        "contract",
        "printed",
        "error",
        "code",
    ):
        assert part in named, f"nothing in the measurement names {part}"


# ── Editing a committed source moves the figure ───────────────────────────


def test_widening_a_tail_widens_the_figure(monkeypatch):
    """The old three widths still count, and still count for what they are."""
    before = _characters()
    monkeypatch.setattr(
        "core.sandbox_runner.REFLECTION_STDOUT_TAIL_CHARS",
        REFLECTION_STDOUT_TAIL_CHARS + 500,
    )
    assert _characters() == before + 500


def test_allowing_more_blocking_lines_widens_the_figure(monkeypatch):
    """``blocking_errors[:12]`` is a limit, so twelve lines is a countable thing."""
    before = _characters()
    monkeypatch.setattr("core.sandbox_runner.REFLECTION_MAX_BLOCKING_ERRORS", 13)
    assert _characters() == before + len("\n- ")


def test_allowing_more_warnings_widens_the_figure(monkeypatch):
    before = _characters()
    monkeypatch.setattr("core.sandbox_runner.REFLECTION_MAX_WARNINGS", 7)
    assert _characters() == before + len("\n- ")


def test_a_wordier_heading_in_the_prompt_file_widens_the_figure(monkeypatch):
    """The wording lives in a committed YAML file, so its length is committed too."""
    prompt_data = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))
    before = _characters()

    wordier = copy.deepcopy(prompt_data)
    wordier["reflection_strings"]["blocking_header"] += " (every one of them)"
    monkeypatch.setattr(
        "core.sandbox_runner.load_prompt", lambda *a, **k: wordier
    )
    assert _characters() == before + len(" (every one of them)")


def test_another_repair_guidance_entry_widens_the_figure(monkeypatch):
    """Guidance is written in the prompt file, not invented at run time."""
    prompt_data = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))
    before = _characters()

    with_another = copy.deepcopy(prompt_data)
    with_another["repair_guidance"]["a_new_category"] = "Do the thing properly."
    monkeypatch.setattr(
        "core.sandbox_runner.load_prompt", lambda *a, **k: with_another
    )
    assert _characters() == before + len("\n- Do the thing properly.")


def test_all_five_committed_guidance_entries_are_counted():
    """Not the ones one failure happens to hit — every one the file holds.

    Which categories a run meets is settled while it runs. Which categories the
    file holds is settled here, and the widest prompt is the one that meets them
    all, so all of them are counted.
    """
    prompt_data = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))
    guidance = prompt_data["repair_guidance"]
    counted = next(
        width for what, width in _measured().items() if "guidance" in what
    )
    assert counted == sum(len(f"\n- {v}") for v in guidance.values()) + len(
        f"\n\n{prompt_data['reflection_strings']['strategy_header']}"
    )


# ── The contract section, built by the contract ───────────────────────────


def test_the_contract_section_counted_is_one_the_contract_really_renders():
    from core.deliverable_contract import DeliverableContract

    section = narrowest_contract_section()
    assert section.startswith("DELIVERABLE CONTRACT")
    assert len(section) <= len(
        DeliverableContract(expected_extensions=[".xlsx"]).to_prompt_section()
    )


def test_a_real_contract_never_renders_shorter_than_the_one_counted():
    """The contract part has to be a figure a real run cannot undercut."""
    from core.deliverable_contract import DeliverableContract

    least = len(narrowest_contract_section())
    for contract in (
        DeliverableContract(expected_extensions=[]),
        DeliverableContract(expected_extensions=[".docx"]),
        DeliverableContract(
            expected_extensions=[".pptx"],
            required_keywords=["deck"],
            notes=["watch the margins"],
            confidence="high",
        ),
    ):
        assert len(contract.to_prompt_section()) >= least


def test_the_contract_section_is_counted_at_all():
    counted = next(
        width for what, width in _measured().items() if "contract" in what
    )
    assert counted >= len(narrowest_contract_section())


# ── The prompt the settings name is the prompt measured ───────────────────


def test_the_settings_own_prompt_name_is_the_one_measured():
    """``core/executor.py`` hands this straight to the runner, so it decides."""
    named = _container_carried_forward_characters(
        _repairing_container(prompt_name="subprocess_occupation_codegen")
    )
    assert sum(named.values()) != _characters()


def test_the_runner_really_takes_its_prompt_name_from_those_settings():
    source = (BATCH_RUNNER_ROOT / "core" / "executor.py").read_text(
        encoding="utf-8"
    )
    assert 'opts.get("prompt_name") or SandboxRunner.DEFAULT_PROMPT' in source


def test_settings_that_name_no_prompt_get_the_runners_default():
    assert _measured() == widest_repair_prompt_characters(
        SandboxRunner.DEFAULT_PROMPT
    )


# ── Fail closed when the prompt cannot be read ────────────────────────────


def test_a_prompt_that_is_not_there_is_refused_rather_than_skipped():
    problems = _refusals(_repairing_container(prompt_name="no_such_prompt"))
    assert len(problems) == 1
    assert "cannot be read here and so cannot be priced" in problems[0]
    assert "no_such_prompt" in problems[0]


def test_a_committed_file_that_is_not_a_repair_prompt_is_refused():
    """Not a made-up failure: this file is in ``prompts/`` and will not load."""
    problems = _refusals(
        _repairing_container(prompt_name=A_COMMITTED_FILE_THAT_IS_NOT_A_PROMPT)
    )
    assert len(problems) == 1
    assert "cannot be priced" in problems[0]


def test_an_unreadable_prompt_is_refused_even_when_the_plan_prices_nothing():
    """The refusal must not depend on the plan having a number to compare.

    Reading the plan's figure first and the prompt second would let a plan that
    prices the container at nothing walk past an unreadable prompt in silence.
    """
    plan = _plan(
        max_tool_result_tokens_per_turn={
            "host_python_process": 0,
            "azure_code_interpreter": 5000,
        }
    )
    problems = _refusals(_repairing_container(prompt_name="no_such_prompt"), plan)
    assert len(problems) == 1


def test_an_unreadable_prompt_is_refused_even_when_the_plan_pays_generously():
    problems = _refusals(
        _repairing_container(prompt_name="no_such_prompt"), _priced_at(50_000)
    )
    assert len(problems) == 1


def test_a_container_that_asks_once_is_never_asked_to_read_a_prompt():
    """A rule that fires where there is no loop would refuse the committed run."""
    assert _refusals(_container_settings(prompt_name="no_such_prompt")) == []


def test_a_prompt_that_will_not_parse_is_refused(monkeypatch):
    """No committed file is malformed YAML, so this is the one failure faked.

    Only the named prompt is made to fail, and every other load is left alone:
    the rule reads the runner's own loop defaults out of the default prompt
    before it prices anything, and breaking that would be testing a different
    step than the one this is about.
    """
    from core import sandbox_runner

    real = sandbox_runner.load_prompt

    def will_not_parse(name=SandboxRunner.DEFAULT_PROMPT, *args, **kwargs):
        if name == "prompt_that_will_not_parse":
            raise yaml.YAMLError("mapping values are not allowed here")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(sandbox_runner, "load_prompt", will_not_parse)
    problems = _refusals(
        _repairing_container(prompt_name="prompt_that_will_not_parse")
    )
    assert len(problems) == 1
    assert "cannot be priced" in problems[0]
    assert "mapping values are not allowed here" in problems[0]


def test_the_measurement_itself_raises_rather_than_guessing():
    """The rule catches; the measurement must not swallow it first."""
    with pytest.raises(FileNotFoundError):
        widest_repair_prompt_characters("no_such_prompt")


# ── The arithmetic ────────────────────────────────────────────────────────


def test_the_figure_is_the_measured_characters_over_the_plans_ratio():
    problem = _refusals(_repairing_container())[0]
    assert f"{_characters()} characters is {_tokens()} tokens" in problem


def test_a_part_token_is_charged_as_a_whole_one():
    """Rounding down would price the prompt at less than it comes to."""
    exact = Decimal(_characters()) / Decimal("3.0")
    assert _tokens() >= exact
    assert _tokens() - 1 < exact


def test_a_kinder_ratio_lowers_the_figure_rather_than_being_ignored():
    problem = _refusals(_repairing_container(), _plan(characters_per_token="4.0"))[0]
    assert f"is {_tokens(4.0)} tokens" in problem
    assert _tokens(4.0) < _tokens()


def test_a_ratio_that_makes_no_sense_is_left_to_the_rule_that_owns_it():
    """The cost reader already refuses these; saying it twice helps nobody."""
    for nonsense in ("0", "-1", "not a number", None):
        assert (
            _refusals(_repairing_container(), _plan(characters_per_token=nonsense))
            == []
        )


# ── When it fires, and when it stays quiet ────────────────────────────────


def test_a_container_that_asks_once_carries_nothing_and_is_left_alone():
    assert _refusals(_container_settings()) == []


def test_a_container_whose_repair_loop_is_on_is_refused_at_zero():
    problems = _refusals(_repairing_container())
    assert len(problems) == 1
    assert "charges 0 tokens for what a later turn carries" in problems[0]


def test_deleting_the_repair_block_is_enough_to_make_it_fire():
    """The runner turns repair on when the block is absent, not off."""
    settings = _container_settings()
    settings["execution"]["sandbox"].pop("repair")
    assert len(_refusals(settings)) == 1


def test_pricing_it_at_the_measured_figure_settles_the_rule():
    assert _refusals(_repairing_container(), _priced_at(_tokens())) == []


def test_pricing_it_above_the_measured_figure_is_allowed():
    """A plan may be more careful than the settings; it may not be less."""
    assert _refusals(_repairing_container(), _priced_at(50_000)) == []


def test_pricing_it_one_token_short_is_not_allowed():
    assert len(_refusals(_repairing_container(), _priced_at(_tokens() - 1))) == 1


def test_the_old_figure_is_no_longer_enough_to_settle_the_rule():
    """The regression this task exists to prevent, stated as a number.

    734 tokens satisfied this check before. It has to stop satisfying it, or
    nothing was fixed — a plan written against the old figure would still pass.
    """
    old = math.ceil(THE_THREE_TAILS_IT_USED_TO_COUNT / 3.0)
    assert old == 734
    assert len(_refusals(_repairing_container(), _priced_at(old))) == 1


def test_switching_repair_off_again_is_a_real_way_to_satisfy_the_check():
    """Two ways out, and turning the loop off is the honest one for this run."""
    assert _refusals(_container_settings(repair={"enabled": False})) == []


def test_a_bigger_repair_budget_still_gets_one_refusal_naming_its_turns():
    problems = _refusals(_repairing_container(max_attempts=3))
    assert len(problems) == 1
    assert "ask for the code 4 times" in problems[0]


def test_a_run_place_that_is_not_a_container_is_not_looked_at():
    settings = _container_settings()
    settings["execution"]["mode"] = "subprocess"
    assert _refusals(settings) == []


def test_a_place_the_plan_prices_nothing_for_is_left_to_the_cost_reader():
    plan = _plan(
        max_tool_result_tokens_per_turn={
            "host_python_process": 0,
            "azure_code_interpreter": 5000,
        }
    )
    assert _refusals(_repairing_container(), plan) == []


@pytest.mark.parametrize("budget,expected_turns", [(1, 2), (2, 3), (3, 4)])
def test_the_refusal_names_the_turn_count_the_settings_really_allow(
    budget, expected_turns
):
    problems = _refusals(_repairing_container(max_attempts=budget))
    assert f"ask for the code {expected_turns} times" in problems[0]


# ── The runner really applies the limits that were measured ───────────────


def test_the_runner_really_trims_what_the_code_printed_to_that_width():
    """Behaviour, not a string search: hand it too much and count what survives."""
    runner = SandboxRunner(llm_client=None)
    reflection = runner._build_reflection(
        _ContractStub(),
        ["something went wrong"],
        "",
        {"text": "o" * 50_000, "error": ""},
        {"warnings": []},
    )
    assert "o" * REFLECTION_STDOUT_TAIL_CHARS in reflection
    assert "o" * (REFLECTION_STDOUT_TAIL_CHARS + 1) not in reflection


def test_the_runner_really_trims_what_it_printed_as_an_error_to_that_width():
    runner = SandboxRunner(llm_client=None)
    reflection = runner._build_reflection(
        _ContractStub(),
        ["something went wrong"],
        "",
        {"text": "", "error": "e" * 50_000},
        {"warnings": []},
    )
    assert "e" * REFLECTION_STDERR_TAIL_CHARS in reflection
    assert "e" * (REFLECTION_STDERR_TAIL_CHARS + 1) not in reflection


def test_the_runner_really_stops_at_twelve_blocking_lines():
    runner = SandboxRunner(llm_client=None)
    reflection = runner._build_reflection(
        _ContractStub(),
        [f"problem number {i}" for i in range(40)],
        "",
        {"text": "", "error": ""},
        {"warnings": []},
    )
    assert f"problem number {REFLECTION_MAX_BLOCKING_ERRORS - 1}" in reflection
    assert f"problem number {REFLECTION_MAX_BLOCKING_ERRORS}" not in reflection


def test_the_runner_really_stops_at_six_warnings():
    runner = SandboxRunner(llm_client=None)
    reflection = runner._build_reflection(
        _ContractStub(),
        ["something went wrong"],
        "",
        {"text": "", "error": ""},
        {"warnings": [f"warning number {i}" for i in range(40)]},
    )
    assert f"warning number {REFLECTION_MAX_WARNINGS - 1}" in reflection
    assert f"warning number {REFLECTION_MAX_WARNINGS}" not in reflection


def test_the_runner_really_appends_the_contract_section():
    runner = SandboxRunner(llm_client=None)
    reflection = runner._build_reflection(
        _ContractStub(), ["something went wrong"], "", {"text": "", "error": ""}, {}
    )
    assert "[CONTRACT]" in reflection


def test_the_runner_really_reaches_the_committed_repair_guidance():
    """One failure category, and the file's own words for it come back."""
    prompt_data = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))
    runner = SandboxRunner(llm_client=None)
    reflection = runner._build_reflection(
        _ContractStub(),
        ["syntax_preflight_failed: unexpected EOF"],
        "",
        {"text": "", "error": ""},
        {},
    )
    assert prompt_data["repair_guidance"]["syntax_error"].strip() in reflection


def test_the_failure_that_stopped_it_is_trimmed_to_its_own_width():
    """``run`` puts this at the head of the blocking errors before reflecting."""
    trimmed = _sanitize_tail("x" * 50_000, limit=EXECUTION_ERROR_TAIL_CHARS)
    assert len(trimmed) == EXECUTION_ERROR_TAIL_CHARS


def test_the_default_trim_width_is_the_failure_tail_and_not_a_loose_number():
    assert len(_sanitize_tail("x" * 50_000)) == EXECUTION_ERROR_TAIL_CHARS


def test_the_failure_line_the_run_builds_is_the_one_that_was_measured():
    """``run`` and the measurement have to build the same line, or they disagree."""
    line = execution_failure_blocking_error(None, "x" * 50_000)
    assert line.startswith("execution_failed[execution_error]: ")
    assert line.endswith("x" * EXECUTION_ERROR_TAIL_CHARS)
    assert "x" * (EXECUTION_ERROR_TAIL_CHARS + 1) not in line


def test_the_run_builds_its_failure_line_through_that_one_function():
    source = (BATCH_RUNNER_ROOT / "core" / "sandbox_runner.py").read_text(
        encoding="utf-8"
    )
    assert "execution_failure_blocking_error(\n" in source
    assert 'f"execution_failed[{execution_error_category' not in source


def test_the_runner_and_the_measurement_share_one_render():
    """Two renderers would be two answers, and one of them would drift unseen."""
    source = (BATCH_RUNNER_ROOT / "core" / "sandbox_runner.py").read_text(
        encoding="utf-8"
    )
    assert source.count("def render_reflection(") == 1
    assert source.count('lines.append(strings["close"])') == 1
    assert "return render_reflection(" in source


# ── What is deliberately not counted ──────────────────────────────────────


def test_the_model_s_earlier_code_is_not_added_to_the_figure():
    """It is the model's own earlier answer, already charged as output.

    ``max_input_tokens_per_attempt`` bills a full ``max_output_tokens`` for
    every answer an earlier turn wrote. The repair prompt's copy of that code is
    those same words coming back, so adding its 4,000 characters here would
    charge for them twice and make the ceiling look better founded than it is.
    """
    around_the_code = next(
        width for what, width in _measured().items() if "earlier code" in what
    )
    assert 0 < around_the_code < 200
    assert REFLECTION_PRIOR_CODE_MAX_CHARS not in _measured().values()
    assert str(REFLECTION_PRIOR_CODE_MAX_CHARS) not in _refusals(
        _repairing_container()
    )[0]


def test_the_words_placed_around_that_code_are_counted():
    """Those are the runner's own, and nobody else in the sum pays for them."""
    prompt_data = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))
    strings = reflection_strings(prompt_data)
    around_the_code = next(
        width for what, width in _measured().items() if "earlier code" in what
    )
    assert around_the_code == len(
        "\n\n{}\n{}\n\n{}".format(
            strings["code_header"], strings["code_fence"], strings["code_fence"]
        )
    )


def test_the_source_still_carries_the_prior_code_at_that_width():
    """If this ever stopped being true the reasoning above would need redoing."""
    source = (BATCH_RUNNER_ROOT / "core" / "sandbox_runner.py").read_text(
        encoding="utf-8"
    )
    assert "len(code) <= REFLECTION_PRIOR_CODE_MAX_CHARS" in source
    assert REFLECTION_PRIOR_CODE_MAX_CHARS == 4000


def test_a_full_earlier_answer_is_worth_more_than_the_code_the_prompt_carries():
    """The reason the code may be left out: output already covers it, and more."""
    plan = load_plan(PLAN_PATH)
    conditions = plan["model_run_conditions"]["shared"]
    ratio = Decimal(str(plan["cost"]["assumptions"]["characters_per_token"]))
    assert int(conditions["max_output_tokens"]) > math.ceil(
        REFLECTION_PRIOR_CODE_MAX_CHARS / float(ratio)
    )


def test_the_line_text_left_out_is_named_and_is_the_only_thing_left_out():
    problem = _refusals(_repairing_container())[0]
    assert (
        "the only part of the prompt outside that figure is the English the run "
        "writes onto those lines while it runs" in problem
    )


def test_the_refusal_no_longer_excuses_itself_from_counting_four_things():
    """The sentence this task exists to delete, asserted gone from the message."""
    problem = _refusals(_repairing_container())[0]
    for excuse in (
        "that is a floor",
        "have no fixed width",
        "no fixed width at all",
    ):
        assert excuse not in problem


def test_the_check_source_no_longer_prints_that_excuse():
    source = (
        BATCH_RUNNER_ROOT / "core" / "execution_envelope_preflight.py"
    ).read_text(encoding="utf-8")
    assert "and that is a floor — the blocking-error lines" not in source


def test_the_figure_is_larger_than_the_three_tails_it_replaced():
    """The whole point, as one comparison."""
    assert _characters() > THE_THREE_TAILS_IT_USED_TO_COUNT
    assert _tokens() > math.ceil(THE_THREE_TAILS_IT_USED_TO_COUNT / 3.0)


def test_no_figure_in_this_file_or_the_check_is_typed_by_hand():
    """The invariant the task was set to protect, checked on the check itself."""
    source = (
        BATCH_RUNNER_ROOT / "core" / "execution_envelope_preflight.py"
    ).read_text(encoding="utf-8")
    inside = source.split(
        "def _check_the_plan_counts_what_the_container_carries_forward"
    )[1].split('\n    """')[2]
    for typed in ("800", "600", "2200", "3922", "734", "1308", "12", "6"):
        assert typed not in inside, (
            f"{typed} is typed into the rule body — it has to come from "
            "core/sandbox_runner.py"
        )


# ── The committed plan and the committed container file ───────────────────


def test_the_committed_plan_and_container_file_pass_this_rule_today():
    """Because repair is off in the file, not because the plan priced it."""
    settings = yaml.safe_load(CONTAINER_FILE.read_text(encoding="utf-8"))
    assert settings["execution"]["sandbox"]["repair"]["enabled"] is False
    assert _refusals(settings) == []


def test_the_plan_still_prices_the_container_at_nothing():
    plan = load_plan(PLAN_PATH)
    carried = plan["cost"]["assumptions"]["max_tool_result_tokens_per_turn"]
    assert carried["docker_container"] == 0


def test_the_whole_free_check_is_unchanged_by_this_rule_today():
    result = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT)
    assert not any(
        "what a later turn carries" in problem for problem in result.all_problems
    )
    assert result.may_start is False


def test_the_rule_is_reached_by_the_free_check_and_not_only_by_this_file(tmp_path):
    """A rule nobody calls refuses nothing.

    Every other test here calls the rule directly, which proves the rule works
    and proves nothing about whether the free check runs it. So this one copies
    the plan's own settings files somewhere writable, switches the container's
    repair loop on there, and asks the free check the way a person would.
    """
    plan = load_plan(PLAN_PATH)
    copied = tmp_path / "experiments" / "execution_envelope"
    copied.mkdir(parents=True)
    for relative in plan["experiment_files"].values():
        source = BATCH_RUNNER_ROOT / relative
        (tmp_path / relative).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )

    container = tmp_path / plan["experiment_files"]["docker_container"]
    settings = yaml.safe_load(container.read_text(encoding="utf-8"))
    settings["execution"]["sandbox"]["repair"] = {
        "enabled": True,
        "max_attempts": 1,
    }
    container.write_text(yaml.safe_dump(settings), encoding="utf-8")

    problems = check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=tmp_path
    )
    assert any("what a later turn carries" in problem for problem in problems)


def test_the_free_check_also_reaches_the_refusal_to_price_an_unreadable_prompt(
    tmp_path,
):
    """The fail-closed path has to be reachable the same way, not only from here."""
    plan = load_plan(PLAN_PATH)
    (tmp_path / "experiments" / "execution_envelope").mkdir(parents=True)
    for relative in plan["experiment_files"].values():
        (tmp_path / relative).write_text(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    container = tmp_path / plan["experiment_files"]["docker_container"]
    settings = yaml.safe_load(container.read_text(encoding="utf-8"))
    settings["execution"]["sandbox"]["repair"] = {"enabled": True}
    settings["execution"]["sandbox"]["prompt_name"] = "no_such_prompt"
    container.write_text(yaml.safe_dump(settings), encoding="utf-8")

    problems = check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=tmp_path
    )
    assert any("cannot be priced" in problem for problem in problems)


def test_the_free_check_stays_quiet_on_the_same_files_left_alone(tmp_path):
    """The other half of the tests above: it is the repair line that fires it."""
    plan = load_plan(PLAN_PATH)
    (tmp_path / "experiments" / "execution_envelope").mkdir(parents=True)
    for relative in plan["experiment_files"].values():
        (tmp_path / relative).write_text(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    problems = check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=tmp_path
    )
    assert not any("what a later turn carries" in problem for problem in problems)
    assert not any("cannot be priced" in problem for problem in problems)


def test_the_plan_no_longer_says_nothing_is_carried_forward():
    """The sentence that talked the reader out of checking is gone."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    assert "the model is asked once and nothing is carried forward" not in text


def test_the_plan_quotes_the_measured_figure_and_not_the_old_one():
    text = PLAN_PATH.read_text(encoding="utf-8")
    assert str(_characters()) in text
    assert str(_tokens()) in text
    assert "2200 characters" not in text
    assert "734 tokens" not in text


def test_the_plan_says_what_makes_the_zero_true_and_what_would_end_it():
    text = PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "repair",
        "sandbox_runner.py",
        "sandbox_occupation_codegen.yaml",
        "cannot be read",
    ):
        assert expected in text
