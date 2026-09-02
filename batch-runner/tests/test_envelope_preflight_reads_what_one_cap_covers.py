"""Whether one cap on answer length covers a whole attempt is read, not typed.

``cost.assumptions.output_tokens_capped_per_attempt`` is three hand-written
booleans in ``experiments/execution_envelope/advance_check_plan.yaml`` with a
four-line prose justification beside them, and — before this file — nothing in
the repository held them against anything.

They are the largest single divisor in the whole cost sum. Two places read
them, both in ``core/execution_envelope_cost.py``:

* ``answers_per_attempt = 1 if output_tokens_capped_per_attempt else
  tool_loop_max_model_turns`` — so a ``true`` bills one answer where a
  ``false`` bills one per turn;
* the input side charges every earlier answer again, and a ``true`` collapses
  the growing sum ``turns * (turns - 1) / 2`` into the flat ``turns - 1``.

Measured against the committed plan: flipping Azure from ``true`` to ``false``
moves the ceiling from 7645.90 United States dollars to 7696.08, and Azure's
own line from 14.48 to 54.62 — a factor of 3.77. The container fails in the
direction that is harder to notice: at the two turns task #27 made reachable,
flipping it from ``false`` to ``true`` *lowers* the ceiling, 7651.33 to
7647.24. A wrong figure that makes the bill look smaller is the one nobody goes
looking for.

None of that has to be taken on trust, because the answer is readable from the
shape of the request each run place sends:

* ``CodeInterpreterRunner.run`` issues exactly one ``responses.create`` an
  attempt, with the code interpreter attached to that same call and one
  ``max_output_tokens`` on it. However many times the service hands a tool
  result back to the model, it happens inside that one request.
* ``SandboxRunner.run`` repairs with an ordinary Python ``for`` loop, and every
  go through it calls ``complete`` again with the whole
  ``max_completion_tokens`` budget. Nothing joins those into one reply.
* ``SubprocessRunner.run`` calls ``complete`` once and runs the code itself.

So each runner declares ``SENDS_A_FRESH_REQUEST_PER_TURN``, the preflight reads
it, and a plan claiming one cap where the repository itself opens a fresh
request each turn is refused. Only that direction is refused: claiming a fresh
cap where one really covers the attempt over-charges, and over-charging is
safe.

A ``true`` for a run place whose runner says nothing is refused too. Nothing
looked is not a pass — the same rule the settings comparison already applies.

One part of this is a claim about somebody else's service and is named as such
in the plan rather than checked here: that the request really is one call
carrying one cap is read below, but whether Azure honours that cap across its
own tool turns is Microsoft's behaviour, taken on the documentation's word. If
it does not hold, the honest value is ``false`` and the ceiling rises about 50
dollars. That is the same class of fact as
``tool_loop_max_model_turns.azure_code_interpreter``, which the plan already
says cannot be read from anywhere in this repository.

Nothing here calls a model, opens a container, reaches Azure, or spends
anything. Every request is counted with the call patched out.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

import core.sandbox_runner as sandbox_module  # noqa: E402
import core.execution_envelope_preflight as preflight_module  # noqa: E402
from core.code_interpreter import CodeInterpreterRunner  # noqa: E402
from core.execution_envelope_cost import (  # noqa: E402
    CostAssumptions,
    estimate_cost_ceiling,
)
from core.execution_envelope_preflight import (  # noqa: E402
    _check_the_plan_knows_what_one_cap_covers,
    _runner_sends_a_fresh_request_per_turn,
    check_experiment_files_match_conditions,
    conditions_from_plan,
    load_plan,
    run_envelope_preflight,
)
from core.execution_envelope_tasks import load_task_catalog  # noqa: E402
from core.execution_environment_readiness import (  # noqa: E402
    ENVIRONMENT_AGENTIC_SANDBOX_V2,
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_CODEX_BUILT_IN_AGENT,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    RUNNER_CLASS_BY_ENVIRONMENT,
)
from core.sandbox_runner import SandboxRunner  # noqa: E402
from core.subprocess_runner import SubprocessRunner  # noqa: E402

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)

THE_CLAIM = "output_tokens_capped_per_attempt"
REFUSAL_OPENING = "one cap on answer length covers a whole"

#: The clause a refusal carries when the plan's turn count really is 1, and the
#: mistake therefore moves no money until the settings change.
QUIET_WORDING = "changes no figure today"

#: The clause it carries when no turn count could be read, and what the mistake
#: is worth is therefore not known — which is not the same as it being nothing.
NO_WORTH_KNOWN = "cannot be worked out here"

#: Everything a plan can write where a turn count belongs that the cost sum
#: would refuse: nothing at all, something that will not come to a whole
#: number, and numbers below the one turn every attempt takes.
TURN_COUNTS_THE_SUM_REFUSES = ("eight", None, {}, [], 0, -3)


def _plan(capped: dict | None = None, turns: dict | None = None) -> dict:
    plan = load_plan(PLAN_PATH)
    if capped is not None:
        plan["cost"]["assumptions"][THE_CLAIM].update(capped)
    if turns is not None:
        plan["cost"]["assumptions"]["tool_loop_max_model_turns"].update(turns)
    return plan


def _refusals(capped: dict | None = None, turns: dict | None = None) -> list[str]:
    return _check_the_plan_knows_what_one_cap_covers(_plan(capped, turns))


# ── What each run place really does, driven rather than read ─────────────


def test_azure_asks_once_an_attempt_and_puts_the_cap_on_that_one_call():
    """Behaviour, not a string search: drive ``run`` and count the requests."""
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=Mock(
                return_value=SimpleNamespace(output=[], output_text="done")
            )
        ),
        files=SimpleNamespace(create=Mock(), delete=Mock(), content=Mock()),
        containers=SimpleNamespace(
            create=Mock(),
            files=SimpleNamespace(
                list=Mock(), content=SimpleNamespace(retrieve=Mock())
            ),
        ),
        close=Mock(),
    )
    runner = CodeInterpreterRunner(client=client, max_completion_tokens=4321)

    result = runner.run(task_prompt="Build the deck", model="m")

    assert result["success"] is True
    assert client.responses.create.call_count == 1
    (_, kwargs), = client.responses.create.call_args_list
    assert kwargs["max_output_tokens"] == 4321
    # The tool that does the extra turns is attached to this same request, so
    # those turns cannot escape the cap it carries.
    assert kwargs["tools"][0]["type"] == "code_interpreter"


def test_the_container_asks_again_for_every_repair_and_recharges_the_budget():
    """Two goes through the repair loop are two requests, not one long one."""
    runner = SandboxRunner(
        llm_client=object(),
        use_docker="never",
        output_qa={"enabled": True, "render": False},
        repair={"enabled": True, "max_attempts": 1},
        max_completion_tokens=7777,
    )
    pptx = pytest.importorskip("pptx")
    docx = pytest.importorskip("docx")
    import io

    buf = io.BytesIO()
    presentation = pptx.Presentation()
    presentation.slides.add_slide(presentation.slide_layouts[6])
    presentation.save(buf)
    deck = buf.getvalue()

    buf = io.BytesIO()
    document = docx.Document()
    document.add_paragraph("wrong type")
    document.save(buf)
    letter = buf.getvalue()

    caps: list[int] = []

    def _record(**kwargs):
        caps.append(kwargs["max_completion_tokens"])
        message = SimpleNamespace(content="```python\nprint('build')\n```")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)], usage=None
        ), {}

    executions = [
        ("local", {"success": True, "text": "first",
                   "files": [{"filename": "deck.docx", "content": letter}]}),
        ("local", {"success": True, "text": "second",
                   "files": [{"filename": "deck.pptx", "content": deck}]}),
    ]
    with patch.object(sandbox_module, "complete", _record), \
         patch.object(runner, "_execute", side_effect=executions):
        result = runner.run(
            task_prompt="Create a PowerPoint pptx deck for the board",
            model="m",
            reference_files=[],
        )

    assert result["final_status"] == "repaired_ok"
    # Two turns, two requests — and the second one is handed the whole budget
    # over again rather than what the first one left unspent.
    assert caps == [7777, 7777]


def test_the_host_process_asks_once_and_runs_the_code_itself():
    response = Mock()
    response.choices = [
        Mock(message=Mock(content="```python\nprint('done')\n```"))
    ]
    response.usage = Mock(total_tokens=10)
    runner = SubprocessRunner(Mock(), max_completion_tokens=5150)

    with patch("core.subprocess_runner.complete") as complete:
        complete.return_value = (response, 10)
        result = runner.run(task_prompt="Print a word", model="m")

    assert result["success"] is True
    assert complete.call_count == 1
    assert complete.call_args.kwargs["max_completion_tokens"] == 5150


# ── The constants say what those behaviours are ──────────────────────────


def test_azure_declares_that_one_request_covers_the_attempt():
    assert CodeInterpreterRunner.SENDS_A_FRESH_REQUEST_PER_TURN is False


@pytest.mark.parametrize("runner", [SandboxRunner, SubprocessRunner])
def test_the_two_local_places_declare_a_fresh_request_each_turn(runner):
    assert runner.SENDS_A_FRESH_REQUEST_PER_TURN is True


def test_the_declaration_lives_on_the_class_the_registry_names():
    """A constant on some other class would be read by nobody."""
    for environment, named in RUNNER_CLASS_BY_ENVIRONMENT.items():
        if named is None:
            continue
        module_name, class_name = named
        module = __import__(module_name, fromlist=[class_name])
        runner = getattr(module, class_name)
        declared = getattr(runner, "SENDS_A_FRESH_REQUEST_PER_TURN", None)
        assert declared is None or isinstance(declared, bool), environment


# ── The reader ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        (ENVIRONMENT_AZURE_CODE_INTERPRETER, False),
        (ENVIRONMENT_DOCKER_CONTAINER, True),
        (ENVIRONMENT_HOST_PYTHON_PROCESS, True),
    ],
)
def test_the_reader_returns_what_the_runner_declares(environment, expected):
    assert _runner_sends_a_fresh_request_per_turn(environment) is expected


def test_a_run_place_with_no_runner_at_all_reads_as_unknown():
    """Codex is registered as ``None`` — there is no class to ask."""
    assert (
        _runner_sends_a_fresh_request_per_turn(ENVIRONMENT_CODEX_BUILT_IN_AGENT)
        is None
    )


def test_a_name_the_registry_never_heard_of_reads_as_unknown():
    assert _runner_sends_a_fresh_request_per_turn("nowhere") is None


def test_the_fixture_runner_is_left_undeclared_on_purpose():
    """It makes no model calls, so no request shape would be true of it."""
    assert (
        _runner_sends_a_fresh_request_per_turn(ENVIRONMENT_AGENTIC_SANDBOX_V2)
        is None
    )


def test_unknown_is_not_the_same_as_a_fresh_request_each_turn():
    """``None`` and ``False`` both fail the ``is False`` gate; only one is a fact."""
    assert _runner_sends_a_fresh_request_per_turn("nowhere") is not False


def test_a_runner_that_answers_with_something_odd_is_read_as_a_yes_or_no():
    with patch.object(SandboxRunner, "SENDS_A_FRESH_REQUEST_PER_TURN", 1):
        assert (
            _runner_sends_a_fresh_request_per_turn(ENVIRONMENT_DOCKER_CONTAINER)
            is True
        )


def test_a_runner_that_cannot_be_imported_reads_as_unknown():
    with patch.dict(
        RUNNER_CLASS_BY_ENVIRONMENT,
        {ENVIRONMENT_DOCKER_CONTAINER: ("core.no_such_module", "Nothing")},
    ):
        assert (
            _runner_sends_a_fresh_request_per_turn(ENVIRONMENT_DOCKER_CONTAINER)
            is None
        )


def test_a_class_the_module_does_not_hold_reads_as_unknown():
    with patch.dict(
        RUNNER_CLASS_BY_ENVIRONMENT,
        {ENVIRONMENT_DOCKER_CONTAINER: ("core.sandbox_runner", "NoSuchRunner")},
    ):
        assert (
            _runner_sends_a_fresh_request_per_turn(ENVIRONMENT_DOCKER_CONTAINER)
            is None
        )


# ── What the check refuses, and what it lets through ─────────────────────


def test_the_committed_plan_is_not_refused():
    """Azure is the only ``true``, and Azure really does ask once."""
    assert _refusals() == []


def test_claiming_one_cap_for_the_container_is_refused():
    problems = _refusals({ENVIRONMENT_DOCKER_CONTAINER: True})
    assert len(problems) == 1
    assert REFUSAL_OPENING in problems[0]
    assert ENVIRONMENT_DOCKER_CONTAINER in problems[0]


def test_the_refusal_names_the_file_and_the_class_that_settle_it():
    """A reader who doubts the refusal has to be told where to look."""
    problem = _refusals({ENVIRONMENT_DOCKER_CONTAINER: True})[0]
    assert "core/sandbox_runner.py" in problem
    assert "SandboxRunner" in problem


def test_the_refusal_for_the_host_process_names_its_own_file():
    problem = _refusals({ENVIRONMENT_HOST_PYTHON_PROCESS: True})[0]
    assert "core/subprocess_runner.py" in problem
    assert "SubprocessRunner" in problem


def test_both_wrong_places_are_refused_and_neither_hides_the_other():
    problems = _refusals(
        {
            ENVIRONMENT_DOCKER_CONTAINER: True,
            ENVIRONMENT_HOST_PYTHON_PROCESS: True,
        }
    )
    assert len(problems) == 2


def test_the_refusals_come_out_in_a_settled_order():
    """Two runs of the same plan must read the same, or diffs are noise."""
    capped = {
        ENVIRONMENT_DOCKER_CONTAINER: True,
        ENVIRONMENT_HOST_PYTHON_PROCESS: True,
    }
    assert _refusals(capped) == _refusals(capped)
    assert _refusals(capped) == sorted(_refusals(capped), key=lambda p: p)


def test_a_true_nothing_looked_at_is_refused_as_well():
    """A run place with no runner registered cannot support the claim."""
    problems = _refusals({ENVIRONMENT_CODEX_BUILT_IN_AGENT: True})
    assert len(problems) == 1
    assert "nothing in this repository says" in problems[0]
    assert "SENDS_A_FRESH_REQUEST_PER_TURN" in problems[0]
    assert "a claim nothing checked is not a claim that holds" in problems[0]


def test_the_fixture_runner_claimed_capped_is_refused_the_same_way():
    problems = _refusals({ENVIRONMENT_AGENTIC_SANDBOX_V2: True})
    assert len(problems) == 1
    assert "nothing in this repository says" in problems[0]


def test_over_charging_is_allowed_because_it_cannot_hide_a_bill():
    """Azure to ``false`` costs 50 dollars more and is nobody's mistake to catch."""
    assert _refusals({ENVIRONMENT_AZURE_CODE_INTERPRETER: False}) == []


@pytest.mark.parametrize(
    "capped",
    [False, 0, "", None],
)
def test_anything_that_is_not_a_yes_passes_without_comment(capped):
    assert _refusals({ENVIRONMENT_DOCKER_CONTAINER: capped}) == []


# ── The refusal says what the mistake is worth ───────────────────────────


@pytest.mark.parametrize("turns", [2, 3, 8])
def test_the_refusal_names_the_divisor_the_plans_own_turn_count_gives(turns):
    problem = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: turns},
    )[0]
    assert f"at the {turns} turns this plan allows" in problem
    assert f"divides the answer charge by {turns}" in problem


def test_at_one_turn_it_says_plainly_that_no_figure_moves_today():
    """The committed container turn count is 1. Overstating it would be a lie."""
    problem = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: 1},
    )[0]
    assert "changes no figure today" in problem
    assert "rises the moment they do" in problem


def test_the_committed_container_turn_count_is_the_one_that_says_nothing_moves():
    plan = load_plan(PLAN_PATH)
    turns = plan["cost"]["assumptions"]["tool_loop_max_model_turns"]
    assert turns[ENVIRONMENT_DOCKER_CONTAINER] == 1
    problem = _refusals({ENVIRONMENT_DOCKER_CONTAINER: True})[0]
    assert "changes no figure today" in problem


@pytest.mark.parametrize("turns", TURN_COUNTS_THE_SUM_REFUSES)
def test_an_unreadable_turn_count_does_not_borrow_the_quiet_wording(turns):
    """A broken turn count must not crash this — and must not read as cheap.

    The half of the old expectation that was right is kept: a turn count the
    cost sum will refuse is somebody else's refusal, and this rule still has to
    finish and still has to produce its own. What is refused now is the rest of
    it. ``"eight"`` is a plan that really allows eight turns, and reporting it
    with the sentence written for a plan that allows one told a reader the
    largest divisor in the sum was worth nothing today.
    """
    problem = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: turns},
    )[0]
    assert NO_WORTH_KNOWN in problem
    assert QUIET_WORDING not in problem
    assert "divides the answer charge" not in problem


def test_a_missing_turn_count_block_does_not_stop_the_refusal():
    plan = _plan({ENVIRONMENT_DOCKER_CONTAINER: True})
    plan["cost"]["assumptions"].pop("tool_loop_max_model_turns")
    problems = _check_the_plan_knows_what_one_cap_covers(plan)
    assert len(problems) == 1
    assert NO_WORTH_KNOWN in problems[0]
    assert QUIET_WORDING not in problems[0]


def test_a_missing_claim_block_leaves_nothing_to_refuse():
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"].pop(THE_CLAIM)
    assert _check_the_plan_knows_what_one_cap_covers(plan) == []


# ── A turn count nobody can read is priced as unknown, not as one ────────


def test_a_word_where_a_number_should_be_is_not_priced_as_one_turn():
    """``"eight"`` is a plan that really allows eight turns.

    This is the case the old wording got worst. Eight turns is the largest
    divisor the sum uses and the one the docstring prices at the difference
    between 14.06 and 54.20 dollars for a single run place. Reporting it with
    the sentence written for a plan that allows one turn told the reader that
    the most expensive mistake available here moved no money today.
    """
    problem = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: "eight"},
    )[0]
    assert NO_WORTH_KNOWN in problem
    assert QUIET_WORDING not in problem
    assert "divides the answer charge by 8" not in problem
    assert ENVIRONMENT_DOCKER_CONTAINER in problem


def test_zero_turns_is_not_a_smaller_number_of_turns():
    """``0`` is not a cheaper plan, it is not a turn count.

    Every attempt asks the model at least once, which is why
    :meth:`CostAssumptions.from_mapping` refuses it outright rather than
    charging for nothing. A refusal here that priced it as the quiet case
    would have been agreeing with a figure the sum will not even compute.
    """
    problem = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: 0},
    )[0]
    assert NO_WORTH_KNOWN in problem
    assert QUIET_WORDING not in problem


def test_a_negative_turn_count_is_refused_the_same_way():
    problem = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: -3},
    )[0]
    assert NO_WORTH_KNOWN in problem
    assert QUIET_WORDING not in problem


@pytest.mark.parametrize(
    ("turns", "expected", "unwanted"),
    [
        (1, QUIET_WORDING, NO_WORTH_KNOWN),
        (0, NO_WORTH_KNOWN, QUIET_WORDING),
    ],
)
def test_the_boundary_between_one_and_none_is_exactly_one(
    turns, expected, unwanted
):
    """The line sits between 0 and 1, on both sides, in one place.

    Kept as a single parametrised pair so the two halves cannot drift apart:
    whichever way the helper's ``>= 1`` is later edited, one of these fails.
    """
    problem = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: turns},
    )[0]
    assert expected in problem
    assert unwanted not in problem


def test_a_whole_number_written_as_a_float_is_read_the_way_the_cost_sum_reads_it():
    """``1.9`` is reported as 1 because 1 is what the sum will charge for.

    This is deliberately *not* refused. The sum does ``int(value)`` and stores
    ``1``, so a refusal saying "at the 1 turn this plan allows" is describing
    the figure that will really be used. Refusing it here instead would invent
    a standard the sum does not hold, which is the mistake this whole rule is
    written to avoid making in the other direction.
    """
    plan = _plan(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: 1.9},
    )
    assumptions = CostAssumptions.from_mapping(plan["cost"]["assumptions"])
    assert assumptions.tool_loop_max_model_turns[ENVIRONMENT_DOCKER_CONTAINER] == 1

    problem = _check_the_plan_knows_what_one_cap_covers(plan)[0]
    assert QUIET_WORDING in problem
    assert NO_WORTH_KNOWN not in problem


def test_a_boolean_is_read_the_way_the_cost_sum_reads_it():
    """Same reasoning as the float: ``int(True)`` is ``1`` over there too."""
    plan = _plan(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: True},
    )
    assumptions = CostAssumptions.from_mapping(plan["cost"]["assumptions"])
    assert assumptions.tool_loop_max_model_turns[ENVIRONMENT_DOCKER_CONTAINER] == 1

    problem = _check_the_plan_knows_what_one_cap_covers(plan)[0]
    assert QUIET_WORDING in problem
    assert NO_WORTH_KNOWN not in problem


def test_a_turn_count_block_that_is_not_a_block_at_all():
    """The settings can hold a line of text where a block belongs.

    ``_dig`` hands back an empty mapping for anything that is not one, so
    nothing crashes; what matters is that nothing is read out of it either.
    """
    plan = _plan({ENVIRONMENT_DOCKER_CONTAINER: True})
    plan["cost"]["assumptions"]["tool_loop_max_model_turns"] = "see the runbook"
    problems = _check_the_plan_knows_what_one_cap_covers(plan)
    assert len(problems) == 1
    assert NO_WORTH_KNOWN in problems[0]
    assert QUIET_WORDING not in problems[0]


def test_the_place_with_no_runner_also_gets_the_honest_worth():
    """The two halves of a refusal are built separately and both must hold.

    A run place with no runner registered takes the other branch of the
    refusal — nothing in this repository looked at all — and that branch
    carries the same priced clause. An unreadable turn count there must not
    get the reassuring half back through the side door.
    """
    for environment in (
        ENVIRONMENT_AGENTIC_SANDBOX_V2,
        ENVIRONMENT_CODEX_BUILT_IN_AGENT,
    ):
        problem = _refusals({environment: True}, {environment: "eight"})[0]
        assert "nothing in this repository says" in problem
        assert NO_WORTH_KNOWN in problem
        assert QUIET_WORDING not in problem


@pytest.mark.parametrize("turns", TURN_COUNTS_THE_SUM_REFUSES + (1, 2, 8, 1.9, True))
def test_the_refusal_count_is_unchanged_for_every_turn_count(turns):
    """What is refused did not move — only what the refusal says.

    A plan claiming the wrong cap was blocked before this change and is
    blocked after it, at every turn count a plan can write, readable or not.
    The opening of the sentence is asserted byte for byte so that a later
    edit to the priced clause cannot quietly reword the part other readers
    match on.
    """
    problems = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: turns},
    )
    assert len(problems) == 1
    assert REFUSAL_OPENING in problems[0]


def test_the_old_fallback_would_be_caught_if_it_came_back():
    """A check nobody has watched fail is not different from one that cannot.

    The old reading is put back in memory only. Two things are asserted: the
    reassuring sentence returns for a plan that really allows eight turns,
    and the number of refusals is *identical* either way — which is exactly
    why this went unnoticed. Nothing was blocked or unblocked by it; the only
    casualty was what the approver was told.
    """
    honest = _refusals(
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: "eight"},
    )
    with patch.object(
        preflight_module,
        "_turn_count_the_cost_sum_would_use",
        lambda written, environment: 1,
    ):
        old = _refusals(
            {ENVIRONMENT_DOCKER_CONTAINER: True},
            {ENVIRONMENT_DOCKER_CONTAINER: "eight"},
        )

    assert QUIET_WORDING in old[0]
    assert NO_WORTH_KNOWN not in old[0]
    assert len(old) == len(honest) == 1


@pytest.mark.parametrize("turns", TURN_COUNTS_THE_SUM_REFUSES)
def test_the_cost_sum_refuses_every_turn_count_this_calls_unreadable(turns):
    """The boundary drawn here is the sum's boundary, not a second one.

    If this rule called something unreadable that the sum would happily
    charge for, the report and the bill would disagree — a new standard
    invented in a checker, which is the thing the owner's rule forbids.

    Which kind of refusal comes out is not the point and is not pinned: a
    word raises :class:`ValueError` from ``int``, a thing that is not a
    number at all raises :class:`TypeError`, and a number below one raises
    :class:`ValueError` from the plan's own rule. What is pinned is that
    none of them get through.
    """
    plan = _plan(turns={ENVIRONMENT_DOCKER_CONTAINER: turns})
    with pytest.raises((TypeError, ValueError)):
        CostAssumptions.from_mapping(plan["cost"]["assumptions"])


def test_a_missing_turn_count_is_refused_by_the_sum_as_well(catalog):
    """The one unreadable case the parser cannot see: the key simply absent.

    ``from_mapping`` keeps whatever run places are written, so a plan missing
    one is only caught when the sum reaches for it. It is still caught.
    """
    plan = _plan()
    plan["cost"]["assumptions"]["tool_loop_max_model_turns"].pop(
        ENVIRONMENT_DOCKER_CONTAINER
    )
    assumptions = CostAssumptions.from_mapping(plan["cost"]["assumptions"])
    with pytest.raises(ValueError):
        estimate_cost_ceiling(
            conditions_by_environment=conditions_from_plan(plan),
            tasks_by_id=catalog.by_task_id(),
            assumptions=assumptions,
        )


@pytest.mark.parametrize("turns", [1, 2, 3, 4, 5, 6, 7, 8])
def test_the_helper_agrees_with_the_cost_sum_on_every_number_it_accepts(turns):
    """The other side of the same boundary: what is accepted here is charged.

    Read back off the parser rather than compared to the literal, so the two
    are pinned to each other and not to a number written twice.
    """
    plan = _plan(turns={ENVIRONMENT_DOCKER_CONTAINER: turns})
    assumptions = CostAssumptions.from_mapping(plan["cost"]["assumptions"])
    charged = assumptions.tool_loop_max_model_turns[ENVIRONMENT_DOCKER_CONTAINER]
    assert (
        preflight_module._turn_count_the_cost_sum_would_use(
            plan["cost"]["assumptions"]["tool_loop_max_model_turns"],
            ENVIRONMENT_DOCKER_CONTAINER,
        )
        == charged
    )


# ── What the mistake is actually worth, priced ───────────────────────────


@pytest.fixture(scope="module")
def catalog():
    return load_task_catalog()


def _ceiling(catalog, capped: dict | None = None, turns: dict | None = None):
    plan = _plan(capped, turns)
    ceiling = estimate_cost_ceiling(
        conditions_by_environment=conditions_from_plan(plan),
        tasks_by_id=catalog.by_task_id(),
        assumptions=CostAssumptions.from_mapping(plan["cost"]["assumptions"]),
    )
    azure = next(
        line
        for line in ceiling.environments
        if line.environment == ENVIRONMENT_AZURE_CODE_INTERPRETER
    )
    return ceiling.total_usd, azure.usd


def test_azure_flipped_the_wrong_way_is_worth_about_fifty_dollars(catalog):
    """The figure the docstring quotes, checked rather than remembered.

    The two totals move whenever any line of the ceiling moves — raising the
    visual task cap from 72 to 112 put 37.50 on both of them — and the
    difference does not, because the flip touches only Azure's line. That is
    why the fifty dollars is asserted as a difference and not inferred from the
    pair: it is the part of this test that is about the boolean.
    """
    committed_total, committed_azure = _ceiling(catalog)
    flipped_total, flipped_azure = _ceiling(
        catalog, {ENVIRONMENT_AZURE_CODE_INTERPRETER: False}
    )
    assert committed_total == Decimal("7645.9048453125")
    assert flipped_total == Decimal("7696.0808453125")
    assert flipped_total - committed_total == Decimal("50.17600000")
    assert flipped_azure > committed_azure * 3


def test_that_one_flip_stays_visible_without_a_per_run_dollar_threshold(catalog):
    """Removing the threshold must not remove the arithmetic."""
    plan = load_plan(PLAN_PATH)
    committed_total, _ = _ceiling(catalog)
    flipped_total, _ = _ceiling(catalog, {ENVIRONMENT_AZURE_CODE_INTERPRETER: False})
    assert plan["cost"]["approved_maximum_usd"] is None
    assert (
        "available_monthly_credit_usd" not in plan["cost"]["owner_approval"]
    )
    assert flipped_total - committed_total == Decimal("50.17600000")


def test_the_container_claimed_capped_at_two_turns_lowers_the_bill(catalog):
    """The dangerous direction: a wrong ``true`` makes the ceiling look smaller."""
    honest_one_turn, _ = _ceiling(catalog)
    honest_two_turns, _ = _ceiling(
        catalog,
        {ENVIRONMENT_DOCKER_CONTAINER: False},
        {ENVIRONMENT_DOCKER_CONTAINER: 2},
    )
    claimed_capped, _ = _ceiling(
        catalog,
        {ENVIRONMENT_DOCKER_CONTAINER: True},
        {ENVIRONMENT_DOCKER_CONTAINER: 2},
    )
    assert honest_two_turns > honest_one_turn
    assert claimed_capped < honest_two_turns
    # And it lands below the committed ceiling too, so the extra turn would
    # read as free rather than as a cost.
    assert claimed_capped > honest_one_turn
    assert honest_two_turns - claimed_capped > Decimal("4")


# ── The check is wired to the entry that actually runs ───────────────────


def _copy_settings_files(plan: dict, root: Path) -> None:
    (root / "experiments" / "execution_envelope").mkdir(parents=True)
    for relative in plan["experiment_files"].values():
        (root / relative).write_text(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def test_the_public_check_refuses_a_plan_that_claims_the_wrong_cap(tmp_path):
    """A rule nobody calls refuses nothing — so call the door, not the rule."""
    plan = _plan({ENVIRONMENT_DOCKER_CONTAINER: True})
    _copy_settings_files(plan, tmp_path)

    problems = check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=tmp_path
    )
    assert any(REFUSAL_OPENING in problem for problem in problems)


def test_the_public_check_stays_quiet_on_the_committed_plan(tmp_path):
    plan = load_plan(PLAN_PATH)
    _copy_settings_files(plan, tmp_path)

    problems = check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=tmp_path
    )
    assert not any(REFUSAL_OPENING in problem for problem in problems)


def test_the_free_check_reports_exactly_what_it_would_without_this_rule():
    """This rule is dormant today; it must not move the standing report.

    Held against the same check with this rule switched off rather than against
    a problem count typed in here. How many problems the free check finds
    depends on the machine it runs on — a box with no container daemon and no
    Azure route has more to say than one with both — so a fixed number would
    only be true where it was written, and would fail on a build server for
    reasons that have nothing to do with what is being checked.
    """
    plan = load_plan(PLAN_PATH)
    with_rule = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)
    with patch(
        "core.execution_envelope_preflight."
        "_check_the_plan_knows_what_one_cap_covers",
        return_value=[],
    ):
        without_rule = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    assert with_rule.all_problems == without_rule.all_problems
    assert with_rule.may_start is without_rule.may_start is False


def test_the_committed_plan_draws_no_refusal_from_the_free_check():
    """The committed plan is priced, not refused, and the total is pinned here.

    The total moved from 363.58481250 to 363.99643750 when the wording every
    request opens with started being measured by rendering the prompt each run
    place really sends, rather than by adding up two blocks written into the
    plan; to 364.23468750 when the three sections the container's runner
    builds *before* that render — and hands to the renderer as the task, where
    its one-character stand-in hid them — were measured as well; to
    7608.4048453125 when the marking sum stopped assuming a flat 10,000 tokens
    of input a call and started stating the 536,191 the committed marking
    settings permit one call to carry; and to 7645.9048453125 when the visual
    task cap the plan mirrors went from 72 to 112 renders. Nothing about this
    rule changed with any of the four.
    """
    result = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT)

    assert not any(REFUSAL_OPENING in problem for problem in result.all_problems)
    assert result.cost is not None
    assert result.cost.total_usd == Decimal("7645.9048453125")


def test_the_free_check_does_refuse_once_the_plan_claims_the_wrong_cap():
    """The other half: dormant because the plan is right, not because it is off."""
    result = run_envelope_preflight(
        _plan({ENVIRONMENT_DOCKER_CONTAINER: True}), root=BATCH_RUNNER_ROOT
    )

    assert any(REFUSAL_OPENING in problem for problem in result.all_problems)
    assert result.may_start is False


# ── The plan says which part is a claim about somebody else ──────────────


def test_the_plan_no_longer_states_azures_behaviour_as_a_flat_fact():
    text = PLAN_PATH.read_text(encoding="utf-8")
    assert (
        "Azure's Responses API applies one cap to the whole reply,"
        not in text
    )


def test_the_plan_says_where_the_readable_half_is_read_from():
    text = PLAN_PATH.read_text(encoding="utf-8")
    for expected in (
        "code_interpreter.py",
        "sandbox_runner.py",
        "subprocess_runner.py",
        "SENDS_A_FRESH_REQUEST_PER_TURN",
    ):
        assert expected in text


def test_the_plan_says_plainly_which_half_it_cannot_check():
    """The honest sentence is the point of the rewrite, so pin it."""
    plan_text = PLAN_PATH.read_text(encoding="utf-8")
    claim_block = plan_text.split(THE_CLAIM)[0].rsplit("\n\n", 1)[-1]
    assert "cannot be checked" in claim_block
    assert "50" in claim_block


def test_the_committed_claim_is_still_the_three_the_check_was_built_for():
    """If a fourth run place appears, this file should be revisited."""
    plan = load_plan(PLAN_PATH)
    assert sorted(plan["cost"]["assumptions"][THE_CLAIM]) == [
        ENVIRONMENT_AZURE_CODE_INTERPRETER,
        ENVIRONMENT_DOCKER_CONTAINER,
        ENVIRONMENT_HOST_PYTHON_PROCESS,
    ]


def test_the_plan_file_still_parses_as_ordinary_settings():
    assert isinstance(yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8")), dict)
