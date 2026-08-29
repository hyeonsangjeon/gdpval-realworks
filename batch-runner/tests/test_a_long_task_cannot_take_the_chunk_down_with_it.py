"""One task must not be able to spend the whole chunk's budget in silence.

Stage 3, shard 4 of 11 (run ``33239148807``) finished six tasks in seventy-one
minutes, entered the seventh, and was still in it four hours and nine minutes
later when ``timeout-minutes: 320`` killed the job. It committed nothing. The
six finished tasks had to be marked again, and paid for again.

Two things let that happen, and both are addressed here:

* the four-hour budget was consulted only at the top of the per-task loop, so
  a task that never returned never met it — the guard was unreachable from
  precisely the situation it exists for;
* the checkpoint was ``partial_save_every_n_tasks``, which is ten, and a shard
  holds seventeen tasks, so the first save of a default run lands after the
  tenth. Six finished tasks were never written down.

So the budget is now checked between rubric items and between split children —
the two loops inside a task that have no bound other than the deliverable —
and a finished task is written to disk on a clock as well as on a counter.

Nothing here calls a model. The grader tests drive a real ``Grader`` with a
scripted client; the ``step8_grade`` tests read the module's syntax tree,
because the Track 2 loop needs a graded corpus and a live endpoint to reach.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import step8_grade as s8
from core.grader import Grader, GradingDeadlineExceeded
from core.rubric_loader import RubricItem, TaskRubric

STEP8 = Path(s8.__file__).resolve()


# ── a grader with a scripted client ──────────────────────────────────────


def _verdict(evidence: str) -> str:
    return json.dumps({
        "verdict": "pass", "partial_score": 1.0, "evidence": evidence,
        "confidence": 0.9, "reasoning": "ok", "tool_calls_made": 0,
    })


def _response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        output=[{"type": "message",
                 "content": [{"type": "output_text", "text": text}]}],
        output_text="",
        usage=SimpleNamespace(
            input_tokens=80, output_tokens=20,
            input_tokens_details=SimpleNamespace(cached_tokens=5),
        ),
        incomplete_details=None,
        status=None,
    )


class ScriptedResponses:
    """Runs out loudly, which is how a test proves an item never started."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("ScriptedResponses ran out of responses")
        return self.script.pop(0)


def _grader(client, **kwargs) -> Grader:
    import core.grader as grader_mod

    prompt = (Path(grader_mod.__file__).resolve().parent.parent
              / "prompts" / "grader_judge.md")
    config = {
        "judge": {
            "provider": "azure_openai",
            "api_version": "2025-04-01-preview",
            "model": "gpt-5.4",
            "reasoning": {"effort": "medium"},
            "generation": {"max_output_tokens": 2400},
            "tools": {"read_deliverable": {
                "ops": ["inspect_structure", "read_content", "inspect_formatting"],
                "per_item_call_cap": 8, "max_iterations": 6}},
        },
        "prompt": {"template": str(prompt)},
        "grader": {"evidence_max_chars": 200},
        "tpm_guard": {},
    }
    return Grader(config, rubric_loader=None, client=client, **kwargs)


def _task(*criteria: str) -> TaskRubric:
    return TaskRubric(
        task_id="9e39df84-ac57-4c9b-a2e3-12b8abf2c797",
        sector="Information",
        occupation="Analyst",
        prompt="Write the report.",
        rubric_items=[
            RubricItem(f"r{n}", criterion, 5, None)
            for n, criterion in enumerate(criteria, start=1)
        ],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )


@pytest.fixture
def deliverable(tmp_path: Path) -> Path:
    directory = tmp_path / "task"
    directory.mkdir()
    (directory / "report.txt").write_text(
        "Total revenue 42. Prepared by the analyst.", encoding="utf-8"
    )
    return directory


# ── the budget, reached from inside a task ───────────────────────────────


def test_a_task_that_outlives_the_budget_stops_at_the_next_item(deliverable):
    """The check that was missing while shard 4 spent four hours.

    One response is scripted for three items. The deadline turns true once the
    first item is done, so if the second ever started, the scripted client
    would raise instead — which makes "the loop stopped" an assertion about
    behaviour rather than about a counter the test set itself.
    """
    responses = ScriptedResponses([_response(_verdict("revenue 42 present"))])
    grader = _grader(SimpleNamespace(responses=responses))
    grader.should_stop = lambda: len(responses.calls) >= 1

    with pytest.raises(GradingDeadlineExceeded) as expired:
        grader.grade_task(
            _task("The report states total revenue of 42",
                  "The report names the analyst",
                  "The report gives a date"),
            str(deliverable),
        )

    assert len(responses.calls) == 1
    message = str(expired.value)
    assert "9e39df84-ac57-4c9b-a2e3-12b8abf2c797" in message
    assert "r2" in message, "the message must name the item that was refused"


def test_a_task_is_abandoned_whole_rather_than_marked_short(deliverable):
    """No ``TaskGrade`` comes back, and that is the point.

    A task returned with two of its three items graded would be scored on
    what it managed, and the item it never reached would read as a failure —
    a lower mark for having been unlucky with the clock. Raising leaves the
    driver no way to record a half-marked task by accident.
    """
    responses = ScriptedResponses([_response(_verdict("revenue 42 present"))])
    grader = _grader(SimpleNamespace(responses=responses))
    grader.should_stop = lambda: len(responses.calls) >= 1

    with pytest.raises(GradingDeadlineExceeded):
        grader.grade_task(
            _task("The report states total revenue of 42",
                  "The report names the analyst"),
            str(deliverable),
        )


def test_a_task_that_fits_the_budget_is_graded_normally(deliverable):
    """A deadline that never comes due changes nothing."""
    responses = ScriptedResponses([
        _response(_verdict("revenue 42 present")),
        _response(_verdict("analyst named")),
    ])
    grader = _grader(SimpleNamespace(responses=responses))
    grader.should_stop = lambda: False

    grade = grader.grade_task(
        _task("The report states total revenue of 42",
              "The report names the analyst"),
        str(deliverable),
    )

    assert len(grade.items) == 2
    assert [item.verdict for item in grade.items] == ["pass", "pass"]


def test_a_grader_with_no_deadline_never_consults_one(deliverable):
    """The default is unchanged behaviour, not a deadline of zero.

    Every other caller of ``Grader`` — the preflight, the analysis scripts,
    the tests — constructs it without a driver, and none of them should start
    raising because grading took a while.
    """
    responses = ScriptedResponses([_response(_verdict("revenue 42 present"))])
    grader = _grader(SimpleNamespace(responses=responses))

    assert grader.should_stop is None
    grade = grader.grade_task(
        _task("The report states total revenue of 42"), str(deliverable)
    )
    assert len(grade.items) == 1


def test_the_deadline_can_be_supplied_at_construction():
    """Not only assignable afterwards, so a caller can pass one in."""
    marker = object()
    grader = _grader(
        SimpleNamespace(responses=ScriptedResponses([])),
        should_stop=lambda: marker,
    )
    assert grader.should_stop() is marker


def test_the_check_is_silent_until_the_driver_says_stop():
    """The unit under both loops, on its own."""
    grader = _grader(SimpleNamespace(responses=ScriptedResponses([])))
    grader.should_stop = lambda: False
    grader._check_should_stop("t", "item r1")  # no raise

    grader.should_stop = lambda: True
    with pytest.raises(GradingDeadlineExceeded):
        grader._check_should_stop("t", "item r1")


def test_the_split_child_loop_is_guarded_as_well():
    """Asserted on the syntax tree, and worth saying why.

    Split children are where a single item multiplies: one criterion against
    forty sibling files is forty judge conversations, each of which may retry.
    Reaching that loop from a test needs a deliverable that the selector
    actually splits, so what is pinned here is narrower and more durable —
    that the loop which calls the judge also asks whether to stop, in the same
    body, so the two cannot be separated by a later edit.
    """
    import core.grader as grader_mod

    tree = ast.parse(
        Path(grader_mod.__file__).resolve().read_text(encoding="utf-8")
    )
    split = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_judge_split_children"
    )
    judging_loops = [
        loop for loop in ast.walk(split)
        if isinstance(loop, ast.For)
        and "_judge_via_tool_calling_selected" in ast.unparse(loop)
    ]
    assert judging_loops, "the per-child judging loop moved or was renamed"
    for loop in judging_loops:
        assert "_check_should_stop" in ast.unparse(loop), (
            "a child loop that judges without checking the deadline is the "
            "shard-4 hang again, one level down"
        )


# ── what the driver does with it ─────────────────────────────────────────


def _main_body() -> list[ast.stmt]:
    tree = ast.parse(STEP8.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node.body
    raise AssertionError("step8_grade has no main")


def _local(name: str) -> ast.FunctionDef:
    for node in _main_body():
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"main has no local function {name!r}")


def _grade_loop() -> ast.For:
    for node in _main_body():
        if isinstance(node, ast.For) and "grade_task" in ast.unparse(node):
            return node
    raise AssertionError("main has no per-task grading loop")


def test_the_driver_installs_its_budget_on_the_grader():
    """Without this line the grader has a deadline it is never given."""
    source = ast.unparse(ast.Module(body=_main_body(), type_ignores=[]))
    assert "grader.should_stop = out_of_time" in source
    assert "GRADER_TIME_BUDGET_SEC" in source


def test_an_abandoned_task_is_dropped_not_recorded():
    """The handler keeps the finished tasks and forgets the unfinished one."""
    loop = ast.unparse(_grade_loop())
    assert "except GradingDeadlineExceeded" in loop

    handler = next(
        h for h in ast.walk(_grade_loop())
        if isinstance(h, ast.ExceptHandler)
        and "GradingDeadlineExceeded" in ast.unparse(h.type or ast.Constant(None))
    )
    body = ast.unparse(handler)
    assert "out_of_time_exit" in body
    assert "task_payloads.append" not in body, (
        "a task cut short must not be filed; its ungraded items would be "
        "scored as failures"
    )


def test_a_chunk_that_finished_nothing_does_not_buy_another_one():
    """Exit 7 asks for a paid resume, so it has to be earned.

    The next chunk would start on the same task and reach the same place. The
    guard predates this change; what is new is that a task abandoned mid-way
    leaves through the same door, so it cannot bypass it.
    """
    body = ast.unparse(_local("out_of_time_exit"))
    assert "graded_count <= initial_completed_count" in body
    assert "GRADE_EXIT_PERSISTENCE_FAILURE" in body
    assert "GRADE_EXIT_RESUME" in body
    assert "save_checkpoint('partial')" in body


def test_a_finished_task_is_written_down_on_a_clock_too():
    """Ten tasks is not a checkpoint on a seventeen-task shard.

    Both rules are kept: the counter still fires, and a slow chunk that has
    not saved for the interval saves anyway. Shard 4 had six finished tasks
    and a default of ten.
    """
    loop = ast.unparse(_grade_loop())
    assert "due_by_count or due_by_clock" in loop
    assert "idx % partial_every == 0" in loop
    assert "partial_save_max_interval_sec" in loop

    source = ast.unparse(ast.Module(body=_main_body(), type_ignores=[]))
    assert "'partial_save_max_interval_sec', 900" in source, (
        "the interval needs a default; a run that does not set it is the "
        "run that needs it"
    )


def test_every_save_still_goes_through_one_builder():
    """Four call sites, one payload shape, so they cannot drift apart."""
    source = ast.unparse(ast.Module(body=_main_body(), type_ignores=[]))
    assert source.count("_build_grade_payload(") == 1, (
        "the payload is built in one place so that a field added for the "
        "final save is not missing from the partial one"
    )
    for status in ("'partial'", "'diagnostic'"):
        assert f"save_checkpoint({status}" in source
    assert "build_payload(emitted_run_status)" in source
