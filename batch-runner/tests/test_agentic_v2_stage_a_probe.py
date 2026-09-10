"""Stage A's paid probe, exercised without paying for it.

The probe exists to ask a real Microsoft Foundry deployment one question. That
question cannot be answered here — no test reaches a network — but everything
around it can be, and the parts worth proving for free are the ones that decide
what a paid run is allowed to do before it does it.

Three of those:

* the tool list. ``finalize`` reaching the offered tools would turn a question
  about tool-choosing into the graded run it comes before, and marking is
  almost the whole of stage one's cost. It is refused before a call is made.
* the loop underneath really being the loop. A stand-in client answers, the
  real dispatcher runs the tool it asked for against a backend that really
  writes bytes, and the next request goes out carrying what came back.
* what is written down. One row per call, no bodies, and a total that is
  ``None`` rather than zero when a price is missing.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_stage_a_probe import (  # noqa: E402
    PROBE_INSTRUCTIONS,
    PROBE_TOOLS,
    ProbeToolsAreWrong,
    StageAProbeOutcome,
    check_probe_tools,
    run_stage_a_probe,
)
from core.agentic_v2_stage_one_budget import StageOneBudget  # noqa: E402
from core.execution_envelope_cost import ModelPrice  # noqa: E402

MODEL = "gpt-5.4"


# ── stand-ins ─────────────────────────────────────────────────────────────


class FakeResponses:
    """Answers what it was told to, and keeps every request it was handed."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls: list[dict] = []

    def create(self, **payload):
        self.calls.append(payload)
        if not self.answers:
            raise AssertionError("the probe asked more times than it was told to")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeClient:
    def __init__(self, answers):
        self.responses = FakeResponses(answers)


def asks_for(name: str, arguments: dict, *, call_id: str = "call-1") -> dict:
    """One Responses-API answer that chooses a tool."""
    return {
        "model": MODEL,
        "usage": {"input_tokens": 120, "output_tokens": 30},
        "output_text": "",
        "output": [
            {
                "type": "function_call",
                "call_id": call_id,
                "name": name,
                "arguments": json.dumps(arguments),
            }
        ],
    }


def says_nothing_useful(text: str = "I have finished thinking") -> dict:
    return {
        "model": MODEL,
        "usage": {"input_tokens": 140, "output_tokens": 12},
        "output_text": text,
        "output": [],
    }


def a_budget(**changes) -> StageOneBudget:
    settings = {
        "max_model_calls": 8,
        "max_input_tokens": 300_000,
        "max_output_tokens": 16_384,
    }
    settings.update(changes)
    return StageOneBudget(**settings)


def prices_for(model: str = MODEL) -> dict[str, ModelPrice]:
    return {
        model: ModelPrice(
            model=model,
            input_usd_per_million=Decimal("1.25"),
            output_usd_per_million=Decimal("10"),
        )
    }


def run_probe(answers, tmp_path, *, budget=None, prices=None, **changes):
    settings = {
        "client": FakeClient(answers),
        "deployment": "gpt-5.4",
        "resource": "a-foundry-resource",
        "budget": budget if budget is not None else a_budget(),
        "task_prompt": "write a one-page summary of the attached figures",
        "workspace_root": tmp_path / "probe",
        "max_output_tokens_per_turn": 2_048,
        "max_tool_calls": 4,
        "max_seconds": 60.0,
        "prices": prices if prices is not None else prices_for(),
    }
    settings.update(changes)
    return run_stage_a_probe(**settings)


# ── the tool list, which is the thing that keeps this cheap ───────────────


def test_the_offered_tools_are_the_two_that_answer_the_question():
    """Written down so widening the list is a change somebody has to make."""
    assert PROBE_TOOLS == ("capabilities_query", "workspace_apply")


def test_the_shipped_list_is_acceptable_to_the_check_that_guards_it():
    assert check_probe_tools() == []


def test_offering_finalize_is_refused_because_it_reaches_the_grader():
    problems = check_probe_tools(("capabilities_query", "finalize"))

    assert len(problems) == 1
    assert "finalize" in problems[0]
    assert "marking" in problems[0]


def test_offering_the_shut_command_tool_is_refused():
    """A shut tool on offer spends a paid turn to be told no."""
    problems = check_probe_tools(("capabilities_query", "exec_run"))

    assert len(problems) == 1
    assert "exec_run" in problems[0]


def test_offering_nothing_is_refused_because_no_choice_could_be_made():
    problems = check_probe_tools(())

    assert len(problems) == 1
    assert "offers no tools" in problems[0]


def test_a_tool_the_contract_does_not_define_is_refused():
    problems = check_probe_tools(("capabilities_query", "make_it_work"))

    assert len(problems) == 1
    assert "make_it_work" in problems[0]


def test_a_wrong_list_stops_the_probe_before_it_spends_anything(tmp_path):
    """The cheapest moment to catch this is before the first call."""
    client = FakeClient([asks_for("finalize", {})])

    with pytest.raises(ProbeToolsAreWrong, match="finalize"):
        run_probe(
            [],
            tmp_path,
            client=client,
            tools=("capabilities_query", "finalize"),
        )

    assert client.responses.calls == []


# ── the loop underneath, run for real against a stand-in model ────────────


def test_a_second_turn_goes_out_holding_the_first_turn_s_answer(tmp_path):
    """Stage A's question, asked of a stand-in so the shape can be proved free.

    The real one costs money and needs a real deployment. What can be settled
    here is that everything between the model and the tool is wired up: the
    dispatcher runs what was asked for, the answer comes back, and the request
    after it carries that answer.
    """
    outcome = run_probe(
        [
            asks_for("capabilities_query", {"kind": "commands"}),
            asks_for(
                "workspace_apply",
                {
                    "operation": "write",
                    "path": "summary.md",
                    "content": "# summary\n",
                },
                call_id="call-2",
            ),
            says_nothing_useful(),
        ],
        tmp_path,
    )

    assert outcome.reached_a_model is True
    assert outcome.resolved_model == MODEL
    assert outcome.tools_asked_for == ("capabilities_query", "workspace_apply")
    assert outcome.carried_the_first_result is True
    assert [row["history_entries_sent"] for row in outcome.ledger] == [0, 1, 2]


def test_the_tool_really_ran_and_the_file_really_exists(tmp_path):
    """A dispatcher that answered without doing anything would pass a mock."""
    run_probe(
        [
            asks_for(
                "workspace_apply",
                {
                    "operation": "write",
                    "path": "summary.md",
                    "content": "# summary\n",
                },
            ),
            says_nothing_useful(),
        ],
        tmp_path,
    )

    written = tmp_path / "probe" / "work" / "summary.md"
    assert written.read_text(encoding="utf-8") == "# summary\n"


def test_the_model_is_not_told_which_tool_to_call(tmp_path):
    """Otherwise the probe proves models follow instructions, not that they choose."""
    for name in PROBE_TOOLS:
        assert name not in PROBE_INSTRUCTIONS

    client = FakeClient([says_nothing_useful()])
    run_probe([], tmp_path, client=client)

    sent = client.responses.calls[0]
    assert {tool["name"] for tool in sent["tools"]} == set(PROBE_TOOLS)


def test_a_model_that_chose_nothing_still_counts_as_reached(tmp_path):
    """Stage A records findings. "It declined" is one, and is not a failure."""
    outcome = run_probe([says_nothing_useful()], tmp_path)

    assert outcome.reached_a_model is True
    assert outcome.tools_asked_for == ()
    assert outcome.carried_the_first_result is False
    assert outcome.stop_reason == "model_stopped_without_finishing"


def test_a_service_that_never_answered_is_not_reported_as_reached(tmp_path):
    outcome = run_probe([RuntimeError("the route was refused")], tmp_path)

    assert outcome.reached_a_model is False
    assert outcome.resolved_model is None
    assert outcome.ledger == ()
    assert outcome.turns_taken == 0


# ── what the money did, and what was written down about it ────────────────


def test_each_call_is_charged_once_so_an_approved_run_gets_what_it_paid_for(
    tmp_path,
):
    """Charged twice, a four-call approval would stop after two calls."""
    budget = a_budget()

    outcome = run_probe(
        [
            asks_for("capabilities_query", {"kind": "commands"}),
            says_nothing_useful(),
        ],
        tmp_path,
        budget=budget,
    )

    assert outcome.turns_taken == 2
    assert budget.model_calls_made == 2
    assert budget.input_tokens_used == 120 + 140
    assert budget.output_tokens_used == 30 + 12


def test_the_run_stops_at_the_amount_it_was_given_not_at_the_service_s_limit(
    tmp_path,
):
    """The stand-in would happily answer a third time. The budget is what says no.

    A model still asking for tools is the case that matters: a run that stopped
    because the model gave up would prove nothing about the limit. Here it has
    not given up, and the ending is named as the money rather than left to look
    like a model that lost interest.
    """
    budget = a_budget(max_model_calls=2)
    still_asking = [
        asks_for("capabilities_query", {"kind": "commands"}, call_id=f"c{turn}")
        for turn in range(1, 4)
    ]

    outcome = run_probe(still_asking, tmp_path, budget=budget)

    assert outcome.turns_taken == 2
    assert outcome.stop_reason == "cost_limit_reached"
    assert budget.model_calls_made == 2


def test_the_number_of_tool_calls_approved_is_also_the_number_of_turns(
    tmp_path,
):
    """One setting, both ceilings, because a turn here is a tool call.

    The plan prices four tool calls. If the dispatcher stopped at four while
    the loop went on asking, the extra turns would be paid for and answered
    with a refusal, and the bill would leave the priced figure behind.
    """
    outcome = run_probe(
        [
            asks_for("capabilities_query", {"kind": "commands"}, call_id=f"c{turn}")
            for turn in range(1, 5)
        ],
        tmp_path,
        max_tool_calls=2,
    )

    assert outcome.turns_taken == 2
    assert outcome.stop_reason == "turn_limit_reached"


def test_nothing_the_model_said_is_kept(tmp_path):
    outcome = run_probe(
        [
            asks_for(
                "workspace_apply",
                {
                    "operation": "write",
                    "path": "private-name.md",
                    "content": "my private working out",
                },
            ),
            says_nothing_useful("my private working out"),
        ],
        tmp_path,
    )

    written = json.dumps(outcome.as_dict()["model_calls"])
    assert "private working out" not in written
    assert "private-name.md" not in written
    for row in outcome.ledger:
        assert set(row) == {
            "turn",
            "requested_deployment",
            "resolved_model",
            "input_tokens",
            "output_tokens",
            "history_entries_sent",
            "price_usd",
            "price_missing",
        }


def test_an_unpriced_call_makes_the_total_missing_rather_than_zero(tmp_path):
    """Zero would make an unsettled bill look settled."""
    outcome = run_probe([says_nothing_useful()], tmp_path, prices={})

    assert outcome.spent_usd is None
    assert outcome.price_missing is True
    assert outcome.as_dict()["spent_usd"] is None


def test_the_report_can_be_written_down_as_it_stands(tmp_path):
    outcome = run_probe(
        [
            asks_for("capabilities_query", {"kind": "commands"}),
            says_nothing_useful(),
        ],
        tmp_path,
    )

    written = outcome.as_dict()
    assert json.loads(json.dumps(written))["carried_the_first_result"] is True
    assert written["tools_offered"] == list(PROBE_TOOLS)
    assert written["requested_deployment"] == "gpt-5.4"
    assert written["resource"] == "a-foundry-resource"


def test_carrying_is_read_from_the_calls_not_from_the_turn_count():
    """Two turns that each started from nothing must not read as carrying."""
    empty = StageAProbeOutcome(
        reached_a_model=True,
        resolved_model=MODEL,
        requested_deployment="gpt-5.4",
        resource="a-foundry-resource",
        tools_offered=PROBE_TOOLS,
        tools_asked_for=("capabilities_query", "capabilities_query"),
        turns_taken=2,
        stop_reason="turn_limit_reached",
        detail="",
        ledger=(
            {"turn": 1, "history_entries_sent": 0},
            {"turn": 2, "history_entries_sent": 0},
        ),
    )

    assert empty.carried_the_first_result is False
