"""The check that refuses the comparison must compare the whole prompt.

The three-way comparison claims one thing: that the only difference between the
run places is the run place. ``check_experiment_files_match_conditions`` is what
makes that claim true, and it is the last gate before money is involved.

It compared ``condition_a.prompt.system`` and ``condition_a.prompt.suffix``.
There are four parts to a prompt. ``core/prompt_loader.py`` joins ``prefix`` and
``body`` into the wording the model is given as well, so either of them, set on
one settings file and not the others, would have changed what one run place was
asked while every free check reported nothing. Worse, of the two parts that
were being compared, ``system`` is the one that does not survive: each run place
loads a codegen prompt that carries its own ``system_message``, and that one
wins. The check was guarding the part that gets dropped and ignoring the two
that always arrive.

Which settings get compared is now read out of the settings files instead of
listed in the source, so a setting added later is compared without anybody
remembering to add it. These tests hold that from both directions: a difference
in any part of the prompt has to be refused, and the things that are *meant* to
differ between run places — the experiment's own id, the repository its results
go to, the label the run place is given — have to stay allowed.

Nothing here calls a model, runs a command, or spends anything.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.code_interpreter import CodeInterpreterRunner  # noqa: E402
from core.execution_envelope_preflight import (  # noqa: E402
    SETTINGS_ALLOWED_TO_DIFFER,
    _check_settings_the_plan_does_not_name,
    _may_differ,
    check_experiment_files_match_conditions,
    conditions_from_plan,
)
from core.prompt_loader import load_prompt, render_prompt  # noqa: E402
from core.sandbox_runner import SandboxRunner  # noqa: E402
from core.subprocess_runner import SubprocessRunner  # noqa: E402

ENVELOPE_DIRECTORY = BATCH_RUNNER_ROOT / "experiments" / "execution_envelope"
PLAN_PATH = ENVELOPE_DIRECTORY / "advance_check_plan.yaml"

# The codegen prompt each run place actually loads, taken from the runners
# rather than written out here, so a renamed prompt file fails this instead of
# quietly making the test check nothing.
CODEGEN_PROMPT_BY_RUNNER = {
    "subprocess": SubprocessRunner.DEFAULT_PROMPT,
    "sandbox": SandboxRunner.DEFAULT_PROMPT,
    "code_interpreter": CodeInterpreterRunner.DEFAULT_PROMPT,
}


@pytest.fixture
def plan() -> dict:
    return yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def copied_root(tmp_path: Path) -> Path:
    """A throwaway copy of the settings files, so a test can change one."""
    destination = tmp_path / "experiments" / "execution_envelope"
    destination.parent.mkdir(parents=True)
    shutil.copytree(ENVELOPE_DIRECTORY, destination)
    return tmp_path


def _change_one_run_place(root: Path, relative: str, path: tuple, value) -> None:
    target = root / relative
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    node = document
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    target.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _refusals(plan: dict, root: Path) -> list[str]:
    return check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=root
    )


# ── What the model is actually given ──────────────────────────────────────


@pytest.mark.parametrize("part", ["prefix", "body"])
def test_the_wording_that_was_going_uncompared_does_reach_the_model(part: str):
    """The fact that makes the rest of this file matter, checked not asserted.

    If prompt assembly ever stops using these, this fails and somebody gets to
    decide what the check should do — rather than a sentence somewhere going
    quietly out of date, which is the whole reason this file exists.
    """
    rendered = render_prompt(
        load_prompt(SubprocessRunner.DEFAULT_PROMPT),
        occupation="Accountant",
        task_prompt="the task",
        experiment_prompt={"system": "", part: "WORDING ONLY ONE RUN PLACE HAS"},
    )

    assert "WORDING ONLY ONE RUN PLACE HAS" in rendered["user_prompt"]


@pytest.mark.parametrize("codegen_prompt", sorted(CODEGEN_PROMPT_BY_RUNNER.values()))
def test_the_standing_instruction_in_the_settings_file_is_the_one_dropped(
    codegen_prompt: str,
):
    """Every run place's codegen prompt brings its own, and its own wins.

    This is not an argument for leaving prompt.system uncompared — comparing it
    costs nothing and a value that is inert today may not be tomorrow. It is
    here because a reader who pins prompt.system and believes they have pinned
    the standing instruction has pinned nothing.
    """
    prompt_data = load_prompt(codegen_prompt)
    assert (prompt_data.get("system_message") or "").strip(), (
        f"{codegen_prompt} no longer carries its own standing instruction, so "
        "the one in the settings file may now be reaching the model"
    )

    rendered = render_prompt(
        prompt_data,
        occupation="Accountant",
        task_prompt="the task",
        experiment_prompt={"system": "STANDING INSTRUCTION FROM THE SETTINGS FILE"},
    )

    assert "STANDING INSTRUCTION FROM THE SETTINGS FILE" not in (
        rendered["system_message"]
    )


# ── A difference in any part of the prompt is refused ─────────────────────


@pytest.mark.parametrize("part", ["prefix", "body", "suffix", "system"])
def test_wording_given_to_one_run_place_only_is_refused(
    plan: dict, copied_root: Path, part: str
):
    """All four parts, though only two of them were ever getting through.

    ``system`` and ``suffix`` were already refused, by being compared against
    the wording written into the plan. They are here because that comparison
    cannot see the case where all three files drift together, and because one
    kind of difference ought to produce one kind of message. ``prefix`` and
    ``body`` are the two that were reaching the model uncompared.
    """
    relative = plan["experiment_files"]["host_python_process"]
    _change_one_run_place(
        copied_root, relative, ("condition_a", "prompt", part), "only here"
    )

    refusals = _refusals(plan, copied_root)

    assert any(f"condition_a.prompt.{part}" in note for note in refusals), (
        f"a {part} on one run place alone was not refused: {refusals}"
    )


def test_a_stricter_reviewer_on_one_run_place_only_is_refused(
    plan: dict, copied_root: Path
):
    """Self-review is turned off today, and that is not why this must pass.

    ``qa.enabled`` being pinned off is what makes the reviewer's settings
    harmless right now. Something that is only safe because of a neighbouring
    value is not safe, it is lucky.
    """
    relative = plan["experiment_files"]["docker_container"]
    _change_one_run_place(
        copied_root, relative, ("condition_a", "qa", "min_score"), 9
    )

    refusals = _refusals(plan, copied_root)

    assert any("condition_a.qa.min_score" in note for note in refusals)


def test_a_setting_nobody_ever_listed_is_refused_all_the_same(
    plan: dict, copied_root: Path
):
    """The point of reading the keys out of the files rather than naming them."""
    relative = plan["experiment_files"]["azure_code_interpreter"]
    _change_one_run_place(
        copied_root, relative, ("condition_a", "model", "top_p"), 0.5
    )

    refusals = _refusals(plan, copied_root)

    assert any("condition_a.model.top_p" in note for note in refusals), (
        "a setting that is not written down anywhere in the check went "
        f"uncompared: {refusals}"
    )


def test_a_narrowing_filter_on_one_run_place_only_is_refused(
    plan: dict, copied_root: Path
):
    """This one would have failed loudly later; refusing now is the point.

    A sector that excludes a pinned task makes step1_prepare_tasks.py raise,
    because it builds its lookup from the already-filtered tasks. That is a run
    that had already been started.
    """
    relative = plan["experiment_files"]["host_python_process"]
    _change_one_run_place(
        copied_root, relative, ("data", "filter", "sector"), "Health Care"
    )

    refusals = _refusals(plan, copied_root)

    assert any("data.filter.sector" in note for note in refusals)


def test_the_refusal_says_which_run_place_is_the_odd_one_out(
    plan: dict, copied_root: Path
):
    relative = plan["experiment_files"]["host_python_process"]
    _change_one_run_place(
        copied_root, relative, ("condition_a", "prompt", "prefix"), "only here"
    )

    note = next(
        note for note in _refusals(plan, copied_root) if "prompt.prefix" in note
    )

    assert "host_python_process" in note
    assert "docker_container" in note
    assert "azure_code_interpreter" in note


# ── What is meant to differ must stay allowed ─────────────────────────────


def test_the_committed_settings_files_still_pass(plan: dict):
    assert _refusals(plan, BATCH_RUNNER_ROOT) == []


def test_the_run_places_do_differ_in_the_ways_they_are_supposed_to(plan: dict):
    """Otherwise the test above passes because there is nothing to compare."""
    documents = [
        yaml.safe_load((BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"))
        for relative in plan["experiment_files"].values()
    ]

    for path in (("experiment", "id"), ("data", "source"), ("condition_a", "name")):
        values = {
            str(document[path[0]][path[1]]) for document in documents
        }
        assert len(values) == len(documents), (
            f"{'.'.join(path)} is the same everywhere, so allowing it to differ "
            "is not being tested by anything"
        )


# ── How the comparison behaves at the edges ───────────────────────────────


def test_a_setting_one_file_leaves_out_while_another_sets_it_is_a_difference():
    problems = _check_settings_the_plan_does_not_name(
        {
            "one": {"condition_a": {"model": {"temperature": 0.0}}},
            "two": {"condition_a": {"model": {}}},
        }
    )

    assert any("condition_a.model.temperature" in note for note in problems)


def test_a_setting_holding_a_list_is_compared_without_falling_over():
    problems = _check_settings_the_plan_does_not_name(
        {
            "one": {"data": {"filter": {"task_ids": ["a", "b"]}}},
            "two": {"data": {"filter": {"task_ids": ["a", "c"]}}},
        }
    )

    assert any("data.filter.task_ids" in note for note in problems)


def test_a_missing_block_is_treated_as_empty_rather_than_raising():
    problems = _check_settings_the_plan_does_not_name(
        {
            "one": {"condition_a": {"prompt": {"prefix": "here"}}},
            "two": {},
        }
    )

    assert any("condition_a.prompt.prefix" in note for note in problems)


def test_one_run_place_is_not_compared_with_itself():
    assert (
        _check_settings_the_plan_does_not_name(
            {"one": {"condition_a": {"model": {"temperature": 0.0}}}}
        )
        == []
    )


def test_the_prompt_is_compared_because_nothing_excuses_it():
    """The same guarantee as before, now the other way round.

    This used to read ``("condition_a", "prompt") in
    BLOCKS_THAT_MUST_MATCH_EVERYWHERE`` — the prompt was compared because
    somebody had put it on a list of four blocks to compare. Everything off
    that list went unlooked at, which is what pull request #237 turned round.
    The prompt is now compared for the reason every other setting is: no entry
    in :data:`SETTINGS_ALLOWED_TO_DIFFER` gives a reason for it to differ.
    """
    assert _may_differ(("condition_a", "prompt")) is None
    assert _may_differ(("condition_a", "prompt", "prefix")) is None
    assert not any(
        excused[:2] == ("condition_a", "prompt")
        for excused in SETTINGS_ALLOWED_TO_DIFFER
    )
