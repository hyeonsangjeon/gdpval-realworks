"""The plan registered a falsification criterion that counts zero by construction.

``agentic_corrected_harness_plan.yaml`` promises to separate three failures over
all 30 tasks. Criterion (a), turn exhaustion, named ``stop_reason
tool_call_limit_reached``, "which the desk raises as ``tool_budget_exhausted``
when the model has spent its ``tool_calls_per_attempt``".

There are two ceilings and that sentence describes the wrong one.

========================  ==================================  ==============
                          raised by                           in the map?
========================  ==================================  ==============
``tool_call_limit_reached``  only a desk, about its own budget   yes
``turn_limit_reached``       the conversation loop, every run    no
========================  ==================================  ==============

The desk's budget is not ``tool_calls_per_attempt``. It is
``budget_caps["tool_calls"]``, which ``scripts/run_agentic_v2_stage.py`` never
passes, so it is the default 32 -- while ``tool_calls_per_attempt`` is the
fixed 8 and the loop's ceiling is ``calls + 1 = 9``. Nine binds first, leaving
23 of the desk's 32 calls unspent, and the registered ending never occurs.

What happens instead is worse than an empty column. ``turn_limit_reached`` is
unmapped, so it is recorded as ``finalize_not_called`` -- and so is
``model_stopped_without_finishing``, which is criterion (b). The two are
opposite findings, one saying the ceiling was too low and the other that the
model could not do the task, and they reach the report as one word, one
disposition and one blame: ``attributable_to: "model"``, for a ceiling the run
itself chose. So (a) was empty, (b) held both, and the three categories the
plan calls a partition did not partition.

**Nothing is hand-made below.** The pairs are produced by the real
:class:`~core.agentic_v2_runner.AgenticV2ScriptedRunner` against the real
:class:`~core.agentic_v2_fixture_backend.AgenticV2FixtureBackend`, at the
ceilings ``scripts/run_agentic_v2_stage.py`` builds from the plan. The plan
file itself records why that matters: an earlier draft of this same line was
checked on built records, "several of those pairs are shapes no run can
produce, and building them was how the falsification line came to describe a
harness that does not exist".

**What is fixed and what is not.** The plan now names the reachable ending and
:func:`~core.agentic_v2_outcome.endings_the_conversations_recorded` counts it
from ``conversations[].stop_reason``, which the run record already carries.
The published ``terminal_error_category`` still merges the two, because
splitting it means a new :data:`core.agentic_v2_contract.ERROR_TYPES` member
and a matching disposition, which decides retries and therefore cost. That is a
paid-path change and is not made here.

Offline, free, model-free.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from core.agentic_v2_contract import (
    AgenticV2Lifecycle,
    AgenticV2Profile,
    LifecycleState,
)
from core.agentic_v2_conversation import (
    AskForTool,
    DispatcherToolDesk,
    GaveUp,
    ScriptedVoice,
    StopReason,
    run_model_conversation,
)
from core.agentic_v2_conversation_runner import (
    TaskConversations,
    ceilings_from,
    conversation_seam,
)
from core.agentic_v2_cost_binding import describe_run_outcome
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_outcome import endings_the_conversations_recorded
from core.agentic_v2_runner import (
    ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED,
    AgenticV2ScriptedRunner,
    _validate_budget_caps,
)
from core.agentic_v2_stage_one_budget import load_stage_one_plan
from core.agentic_v2_tools import AgenticV2ToolDispatcher

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = BATCH_RUNNER_ROOT / "experiments" / "execution_envelope"
CORRECTED_PLAN = ENVELOPE / "agentic_corrected_harness_plan.yaml"
STAGE_SCRIPT = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_v2_stage.py"

PROFILE = {
    "tool_contract_version": "2.0",
    "policy_profile_id": "offline-full-v1",
    "foundation_only": True,
}

#: The ending the plan registered for criterion (a).
THE_REGISTERED = "tool_call_limit_reached"

#: The ending a task that keeps working actually reaches.
THE_REACHED = "turn_limit_reached"

#: Criterion (b).
THE_QUIET = "model_stopped_without_finishing"


# ── the two numbers, off the plan and off the script ──────────────────────


@pytest.fixture(scope="module")
def plan() -> dict:
    return load_stage_one_plan()


@pytest.fixture(scope="module")
def chosen(plan) -> Any:
    settings = dict(plan["cost"]["chosen_settings"])

    class Chosen:
        tool_calls_per_attempt = int(settings["tool_calls_per_attempt"])
        max_output_tokens_per_turn = int(settings["max_output_tokens_per_turn"])

    return Chosen


@pytest.fixture(scope="module")
def ceilings(plan, chosen):
    """Built the way ``run_agentic_v2_stage.py`` builds them, from the plan."""
    return ceilings_from(plan, chosen)


#: What the runner falls back to when a caller passes no ``budget_caps``.
DEFAULT_CAPS = _validate_budget_caps(None)


@pytest.fixture(scope="module")
def desk_budget() -> int:
    """What the runner gives the desk when the stage script passes nothing."""
    return int(DEFAULT_CAPS["tool_calls"])


def test_the_stage_script_hands_the_runner_no_tool_call_budget():
    """The premise of the whole file, asserted where it is decided.

    ``build_runner_factory`` takes ``budget_caps`` and defaults it to ``None``.
    If a caller ever starts passing one, the arithmetic below changes and this
    test is where that shows up.
    """
    source = STAGE_SCRIPT.read_text(encoding="utf-8")
    assert "budget_caps" not in source


def test_the_desk_ceiling_is_not_the_tool_calls_per_attempt(chosen, desk_budget):
    """The sentence the plan used to carry, checked as arithmetic."""
    assert chosen.tool_calls_per_attempt == 8
    assert desk_budget == 32
    assert desk_budget != chosen.tool_calls_per_attempt


def test_the_loop_ceiling_binds_first_at_the_settings_this_run_fixes(
    ceilings, desk_budget
):
    """Nine turns cannot spend thirty-two calls, so the desk never refuses."""
    assert ceilings.max_model_turns < desk_budget


# ── run it, rather than argue it ──────────────────────────────────────────


def _keeps_asking(n: int = 60) -> list[AskForTool]:
    """Every request differs, or ``max_repeats_of_one_request`` ends it first."""
    return [
        AskForTool(
            call_id=f"c{i}",
            tool_name="capabilities_query",
            arguments={"kind": "commands", "query": f"step-{i}"},
        )
        for i in range(1, n + 1)
    ]


def _against_the_real_desk(ceilings, desk_budget, replies):
    """The real dispatcher, the real adapter, the real fixture backend."""
    with tempfile.TemporaryDirectory() as tmp:
        profile = AgenticV2Profile(
            tool_contract_version="2.0",
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        )
        backend = AgenticV2FixtureBackend(
            root=tmp, profile=profile, budget_caps=DEFAULT_CAPS
        )
        lifecycle = AgenticV2Lifecycle()
        lifecycle.transition(LifecycleState.STARTED)
        lifecycle.transition(LifecycleState.ACTIVE)
        dispatcher = AgenticV2ToolDispatcher(
            backend=backend,
            lifecycle=lifecycle,
            max_total_calls=desk_budget,
            deadline=None,
            record_wall_time=False,
        )
        outcome = run_model_conversation(
            task_prompt="keep working",
            voice=ScriptedVoice(replies=replies),
            desk=DispatcherToolDesk(dispatcher=dispatcher),
            limits=ceilings.fresh_limits(),
        )
        return outcome, dispatcher.total_calls


def test_a_task_that_keeps_working_ends_on_turns_with_desk_budget_to_spare(
    ceilings, desk_budget
):
    """The registered ending is not merely rare here. It cannot happen."""
    outcome, calls_made = _against_the_real_desk(
        ceilings, desk_budget, _keeps_asking()
    )

    assert outcome.stop_reason is StopReason.TURN_LIMIT_REACHED
    assert calls_made == ceilings.max_model_turns
    assert calls_made < desk_budget, (
        "the desk still had budget left, so it had no reason to refuse"
    )


def test_every_candidate_but_one_ends_at_the_turn_ceiling(plan, desk_budget):
    """Why a later turn-limit comparison cannot include the top of the grid.

    At 32 the loop's ceiling becomes 33, the desk's 32 binds first, and the
    recorded ending changes kind. A comparison spanning that value is comparing
    two different outcome variables, and the change of label reads as an effect.
    """
    grid = [4, 6, 8, 12, 16, 32]
    assert grid == _candidate_grid(), "the plan's own candidate list has moved"

    endings: dict[int, str] = {}
    for calls in grid:

        class Chosen:
            tool_calls_per_attempt = calls
            max_output_tokens_per_turn = 8192

        ceilings = ceilings_from(plan, Chosen)
        outcome, _ = _against_the_real_desk(
            ceilings, desk_budget, _keeps_asking(2 * calls + 8)
        )
        endings[calls] = outcome.stop_reason.value

    assert {c: endings[c] for c in (4, 6, 8, 12, 16)} == {
        c: THE_REACHED for c in (4, 6, 8, 12, 16)
    }
    assert endings[32] == THE_REGISTERED, (
        "the registered ending is reachable at exactly one candidate, and it "
        "is the one that changes what the column means"
    )


def _candidate_grid() -> list[int]:
    raw = yaml.safe_load(
        (ENVELOPE / "agentic_stage_one_plan.yaml").read_text(encoding="utf-8")
    )

    def find(node: Any) -> Any:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "tool_calls_per_attempt" and isinstance(value, list):
                    return value
                found = find(value)
                if found:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = find(value)
                if found:
                    return found
        return None

    return [int(one) for one in find(raw)]


# ── what the report would have published ──────────────────────────────────


def _through_the_real_runner(ceilings, task_id: str, replies):
    with tempfile.TemporaryDirectory() as tmp:
        held = TaskConversations(ceilings)
        runner = AgenticV2ScriptedRunner(
            backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
                root=tmp, **kwargs
            ),
            conversation=conversation_seam(
                voice=ScriptedVoice(replies=replies),
                limits=held.limits_for(task_id, 1),
                on_outcome=lambda outcome: held.record(task_id, 1, outcome),
            ),
            profile=PROFILE,
        )
        record = runner.run("Write the report", task_id=task_id)
        return record, held


@pytest.fixture
def worked_to_the_end(ceilings):
    return _through_the_real_runner(ceilings, "kept-working", _keeps_asking())


@pytest.fixture
def talked_and_stopped(ceilings):
    return _through_the_real_runner(
        ceilings, "went-quiet", [GaveUp(note="not sure how")]
    )


def test_the_two_endings_really_are_different_in_the_conversation(
    worked_to_the_end, talked_and_stopped
):
    _, kept = worked_to_the_end
    _, quiet = talked_and_stopped

    assert kept.outcome_of("kept-working", 1).stop_reason is (
        StopReason.TURN_LIMIT_REACHED
    )
    assert quiet.outcome_of("went-quiet", 1).stop_reason is (
        StopReason.MODEL_STOPPED_WITHOUT_FINISHING
    )


def test_the_published_column_gives_them_one_word_one_blame(
    worked_to_the_end, talked_and_stopped
):
    """``terminal_error_category`` is ``describe_run_outcome(record)["error_type"]``.

    ``attributable_to`` is the part to read twice. The table it comes from has
    a label for a bound the run imposed -- it is what a terminal-budget
    disposition gets -- and a turn ceiling does not receive it.
    """
    kept_record, _ = worked_to_the_end
    quiet_record, _ = talked_and_stopped

    kept = describe_run_outcome(kept_record)
    quiet = describe_run_outcome(quiet_record)

    assert kept["error_type"] == quiet["error_type"] == "finalize_not_called"
    assert kept["disposition"] == quiet["disposition"]
    assert kept["attributable_to"] == quiet["attributable_to"] == "model"


def test_neither_ending_is_named_by_the_contract(worked_to_the_end):
    """The merge is not a bug in the report. There is no word to publish."""
    assert THE_REACHED not in ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED
    assert THE_QUIET not in ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED


# ── the counter that makes criterion (a) answerable ───────────────────────


def test_the_conversations_block_separates_what_the_report_merged(
    worked_to_the_end, talked_and_stopped
):
    """One run record's worth of both endings, counted apart."""
    _, kept = worked_to_the_end
    _, quiet = talked_and_stopped
    conversations = {
        **kept.as_dict()["conversations"],
        **quiet.as_dict()["conversations"],
    }

    counted = endings_the_conversations_recorded(conversations)

    assert counted["tasks"] == 2
    assert counted["ran_out_of_turns"] == 1
    assert counted["stopped_without_finishing"] == 1
    assert counted["recorded_as_finalize_not_called"] == 2, (
        "both reach the report as one word; that is the size of the merge"
    )
    assert counted["by_stop_reason"] == {THE_REACHED: 1, THE_QUIET: 1}


def test_a_task_is_counted_once_however_many_attempts_it_took():
    """The denominator is tasks, not attempts, and retries are not dropped."""
    counted = endings_the_conversations_recorded(
        {
            "t1#1": {"stop_reason": "time_limit_reached"},
            "t1#2": {"stop_reason": THE_REACHED},
            "t2#1": {"stop_reason": THE_QUIET},
        }
    )

    assert counted["tasks"] == 2
    assert counted["ran_out_of_turns"] == 1
    assert counted["attempts_not_counted"] == 1
    assert "time_limit_reached" not in counted["by_stop_reason"]


def test_a_mapped_ending_is_not_counted_as_merged():
    """``time_limit_reached`` has a name of its own and keeps it."""
    counted = endings_the_conversations_recorded(
        {"t1#1": {"stop_reason": "time_limit_reached"}}
    )

    assert counted["recorded_as_finalize_not_called"] == 0
    assert counted["ran_out_of_turns"] == 0


def test_the_counter_does_not_pretend_to_answer_tool_refusal():
    """Criterion (c) is not derivable here and the function says so.

    The loop reports a desk that said no and a desk that fell over as the same
    ``tool_desk_broke``. Counting it from this block would file a closed tool
    desk under the model being told no.
    """
    counted = endings_the_conversations_recorded(
        {"t1#1": {"stop_reason": "tool_desk_broke"}}
    )

    assert "refusals" not in counted
    assert "refusals_the_desk_gave" in counted["note"]


# ── the plan text ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def corrected_plan() -> str:
    return CORRECTED_PLAN.read_text(encoding="utf-8")


def test_the_plan_no_longer_registers_an_ending_this_run_cannot_reach(
    corrected_plan,
):
    """Asserted on the live criterion, not on the file.

    The superseded draft is quoted a few lines below the correction, which is
    this file's convention, so a bare substring search would pass either way.
    """
    criterion = corrected_plan.split("falsification: >-")[1]
    live = criterion.split("Line (a) is a third correction")[0]

    assert THE_REACHED in live
    assert THE_REGISTERED not in live
    assert "endings_the_conversations_recorded" in live


def test_the_plan_keeps_the_draft_it_replaced(corrected_plan):
    """The superseded wording is quoted, not deleted.

    Asserted on the sentence about criterion (a) specifically. The file also
    carries a "wrong in both directions and both drafts are kept" line, and
    that one is about criterion (c) -- a different correction with its own
    history, which would make a green test here about the wrong paragraph.
    """
    assert "Line (a) is a third correction and the draft it replaces is kept" in (
        corrected_plan
    )
    assert THE_REGISTERED in corrected_plan
    assert "when the model has spent its tool_calls_per_attempt" in corrected_plan


def test_the_plan_no_longer_says_the_later_run_moves_one_thing(corrected_plan):
    """The header claim the candidate grid above disproves."""
    assert "tool_calls_per_attempt and nothing else" in corrected_plan
    assert '"And nothing else" is the intent and it is not what the knob does' in (
        corrected_plan
    )
    assert "turn-and-token comparison rather than a turn comparison" in corrected_plan
