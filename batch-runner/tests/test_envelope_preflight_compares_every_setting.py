"""Every setting is compared, not the four blocks somebody listed.

The three-way comparison claims that the only difference between the run places
is the run place. ``check_experiment_files_match_conditions`` is what makes that
claim true, and it is the last free gate before money is involved.

One of its rules compared four named blocks — ``condition_a.model``,
``condition_a.prompt``, ``condition_a.qa`` and ``data.filter`` — under a comment
saying the blocks left out "are the ones that are meant to differ between run
places". Measured against the three settings files the plan actually names,
that was not so. The files hold 44 settings; the four blocks covered 18.

Seven of the 26 left out were caught anyway, by a different rule that holds
each file against the plan. The plan pins the time limit, the retry count, the
resume count and the code length, so a file disagreeing about those was
refused. That is a narrower question — does this file agree with the plan —
and it covers only what somebody thought to write into the plan.

The other 19 were invisible to every rule. Measured at the level of the whole
check, this work takes it from 25 of 44 to 30. What it newly sees: what the run
claims it is holding still and varying, whether the results are published,
whether they are entered for scoring, and the container's own repair loop —
which calls the model again after the code is written, and which the strict
comparison forbids in as many words.

Then a second round, for the hole left in the first. An exception is matched by
prefix, so naming a block excuses every setting under it — including settings
nobody has argued for, which are excused by where they sit and by nothing else.
``execution.sandbox.max_skills`` was one: it decides how many skill manuals are
written into the container's prompt ahead of the task, while all three files
declare they are holding ``prompt_strategy`` still. It has a rule of its own
now, taking the check to 31 of 44, and the settings the two block exceptions
let through are argued for here one at a time.

The tests here hold that from both ends. The sweep is derived, not typed: it
reads the settings out of the committed files, changes each one in a single run
place, and requires either a refusal or a stated reason. Nothing here calls a
model, runs a container, or spends anything.
"""

from __future__ import annotations

import inspect
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core import execution_envelope_preflight  # noqa: E402
from core import output_qa as output_qa_module  # noqa: E402
from core.execution_envelope_preflight import (  # noqa: E402
    CONTAINER_SETTINGS_THAT_ADD_TO_THE_PROMPT,
    CONTAINER_SETTINGS_THAT_CALL_THE_MODEL_AGAIN,
    SETTINGS_ALLOWED_TO_DIFFER,
    WHAT_THE_SETTING_DOES,
    _check_settings_the_plan_does_not_name,
    _check_the_container_calls_no_model_after_the_code_is_made,
    _check_the_container_is_told_no_more_than_the_others,
    _may_differ,
    _settings_in,
    check_experiment_files_match_conditions,
    conditions_from_plan,
)
from core.execution_environment_readiness import (  # noqa: E402
    COMPARISON_SAME_GENERATED_CODE,
    COMPARISON_TOOL_BUILT_IN_FEATURES,
    ENVIRONMENT_DOCKER_CONTAINER,
    EXECUTION_MODE_BY_ENVIRONMENT,
)
from core.experiment_config import ExperimentConfig  # noqa: E402
from core.prompt_sections import DEFAULT_SECTIONS  # noqa: E402
from core.sandbox_runner import SandboxRunner  # noqa: E402
from core.skills_registry import SkillsRegistry  # noqa: E402

ENVELOPE_DIRECTORY = BATCH_RUNNER_ROOT / "experiments" / "execution_envelope"
PLAN_PATH = ENVELOPE_DIRECTORY / "advance_check_plan.yaml"

# The settings no rule was looking at: changed in one run place, the whole
# check said nothing. Named so the specific regression is pinned and not only
# the general rule. A list in a test can only make the test stricter — if one
# of these stops being caught, this fails.
SETTINGS_NO_RULE_WAS_LOOKING_AT = (
    "control.changed",
    "control.fixed",
    "output.publish_to_hf",
    "output.submit_to_evals",
)

# The settings the plan alone was pinning. A file disagreeing with the plan
# about these was already refused, so the whole check saw them; what it did not
# do was ask whether the run places agree with each other. That distinction is
# not academic — it is the difference between a setting covered because someone
# wrote it into the plan and a setting covered because it is there at all.
SETTINGS_THE_PLAN_ALONE_WAS_PINNING = (
    "execution.max_retries",
    "execution.resume_max_rounds",
    "execution.timeout",
    "execution.tokens.code_generation",
)


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


def _refusals(plan: dict, root: Path) -> list[str]:
    return check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=root
    )


def _settings_file_of_one_run_place(plan: dict) -> str:
    """One run place's file, chosen from the plan rather than named here."""
    return str(plan["experiment_files"]["docker_container"])


def _all_settings(plan: dict) -> dict[tuple[str, ...], object]:
    """Every setting in every file the plan names, read out of the files."""
    found: dict[tuple[str, ...], object] = {}
    for relative in plan["experiment_files"].values():
        document = yaml.safe_load(
            (BATCH_RUNNER_ROOT / str(relative)).read_text(encoding="utf-8")
        )
        found.update(_settings_in(document))
    return found


def _something_else(value: object) -> object:
    """A value of the same shape that is definitely not the one given."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 1
    if isinstance(value, list):
        return list(value) + ["one extra"]
    if value is None:
        return "was not set here before"
    return str(value) + " — changed in one run place only"


def _nest(path: tuple[str, ...], value: object) -> dict:
    """A settings file holding one value at one key path and nothing else."""
    node: object = value
    for key in reversed(path):
        node = {key: node}
    return node  # type: ignore[return-value]


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


# ── The files as they are committed ───────────────────────────────────────


def test_the_committed_files_are_reported_clean(plan, copied_root):
    """Nothing is invented. A check that cries wolf gets switched off."""
    assert _refusals(plan, copied_root) == []


def test_there_are_plenty_of_settings_to_sweep(plan):
    """Guard the sweep below: an empty reading would make it pass vacuously."""
    settings = _all_settings(plan)
    assert len(settings) >= 40, (
        "the three settings files should supply plenty to sweep with, found "
        f"{len(settings)}"
    )


def test_most_settings_are_compared_rather_than_excused(plan):
    """The exceptions are meant to be the small part, not the bulk.

    Before this work the proportions were the other way up: 18 of 44 settings
    compared. If a later edit ever excuses its way back to that, say so here
    rather than leaving the check quietly hollow.
    """
    settings = _all_settings(plan)
    compared = [path for path in settings if _may_differ(path) is None]
    assert len(compared) > len(settings) / 2, (
        f"only {len(compared)} of {len(settings)} settings are compared; the "
        "rest are excused, which is how the previous version went wrong"
    )


# ── The sweep this work exists because of ─────────────────────────────────


def test_every_setting_is_either_compared_or_excused_with_a_reason(
    plan, copied_root
):
    """Change each setting in one run place; require a refusal or a reason.

    This is the whole point, and it is derived rather than typed: the settings
    come out of the committed files, so one added tomorrow is swept without
    anybody remembering to add it here.
    """
    unnoticed: list[str] = []
    for path, value in sorted(_all_settings(plan).items()):
        if _may_differ(path) is not None:
            continue
        dotted = ".".join(path)
        root = copied_root / dotted
        shutil.copytree(copied_root / "experiments", root / "experiments")
        _change_one_run_place(
            root, _settings_file_of_one_run_place(plan), path, _something_else(value)
        )
        if not any(dotted in note for note in _refusals(plan, root)):
            unnoticed.append(dotted)
    assert unnoticed == [], (
        "these settings were changed in one run place and nothing was "
        "reported: " + ", ".join(unnoticed)
    )


@pytest.mark.parametrize("dotted", SETTINGS_NO_RULE_WAS_LOOKING_AT)
def test_the_settings_no_rule_was_looking_at_are_caught(
    plan, copied_root, dotted: str
):
    """The named regression. Every one of these walked through before."""
    path = tuple(dotted.split("."))
    settings = _all_settings(plan)
    assert path in settings, (
        f"{dotted} is no longer in the settings files, so this test is "
        "checking nothing — decide what it should say instead of deleting it"
    )
    _change_one_run_place(
        copied_root,
        _settings_file_of_one_run_place(plan),
        path,
        _something_else(settings[path]),
    )
    assert any(dotted in note for note in _refusals(plan, copied_root))


@pytest.mark.parametrize("dotted", SETTINGS_THE_PLAN_ALONE_WAS_PINNING)
def test_the_settings_the_plan_alone_was_pinning_are_compared_too(
    plan, dotted: str
):
    """These were covered by the plan. Now they are covered either way.

    Deliberately asks the run-place comparison on its own rather than the whole
    check: going through the whole check would pass on the old code as well,
    because the other rule was already refusing a file that disagreed with the
    plan. What is new is that this holds when the plan says nothing.
    """
    path = tuple(dotted.split("."))
    assert _may_differ(path) is None
    problems = _check_settings_the_plan_does_not_name(
        {
            "one": _nest(path, "what one run place holds"),
            "two": _nest(path, "what the other holds"),
        }
    )
    assert any(dotted in note for note in problems)


def test_a_setting_nobody_has_thought_of_yet_is_compared(plan, copied_root):
    """The guarantee the old design could not give.

    A setting that exists in no file today, added to one run place tomorrow,
    is compared because nothing excused it — not because somebody remembered.
    """
    _change_one_run_place(
        copied_root,
        _settings_file_of_one_run_place(plan),
        ("some_setting_invented_later", "that_nobody_listed"),
        "only this run place has it",
    )
    problems = _refusals(plan, copied_root)
    assert any(
        "some_setting_invented_later.that_nobody_listed" in note
        for note in problems
    )


def test_a_setting_one_place_leaves_out_is_a_difference_too():
    """Absent in one file and set in another is a real disagreement."""
    problems = _check_settings_the_plan_does_not_name(
        {
            "one": {"execution": {"timeout": 900}},
            "two": {"execution": {}},
        }
    )
    assert any("execution.timeout" in note for note in problems)


def test_the_refusal_says_which_run_places_disagree_and_what_they_hold():
    """A refusal nobody can act on is only slightly better than silence."""
    problems = _check_settings_the_plan_does_not_name(
        {
            "docker_container": {"execution": {"timeout": 900}},
            "host_python_process": {"execution": {"timeout": 1200}},
        }
    )
    assert len(problems) == 1
    note = problems[0]
    assert "execution.timeout" in note
    assert "how long one task may run" in note
    assert "900: docker_container" in note
    assert "1200: host_python_process" in note


def test_a_setting_with_no_plain_words_is_still_compared():
    """Missing from the glossary means described by its own name, not skipped."""
    problems = _check_settings_the_plan_does_not_name(
        {
            "one": {"a_setting_with_no_description": 1},
            "two": {"a_setting_with_no_description": 2},
        }
    )
    assert len(problems) == 1
    assert "a_setting_with_no_description" in problems[0]


def test_one_run_place_is_never_compared_with_itself():
    assert _check_settings_the_plan_does_not_name({"one": {"execution": {}}}) == []
    assert _check_settings_the_plan_does_not_name({}) == []


# ── The exceptions, each of which has to be argued for ────────────────────


@pytest.mark.parametrize("excused", sorted(SETTINGS_ALLOWED_TO_DIFFER))
def test_every_exception_gives_a_reason(excused: tuple[str, ...]):
    """An exception without a reason is the old design wearing a new hat."""
    reason = SETTINGS_ALLOWED_TO_DIFFER[excused]
    assert reason.strip(), f"{'.'.join(excused)} is excused with no reason given"
    assert len(reason.split()) >= 6, (
        f"{'.'.join(excused)} is excused with '{reason}', which is too short "
        "to be an argument"
    )


@pytest.mark.parametrize("excused", sorted(SETTINGS_ALLOWED_TO_DIFFER))
def test_every_exception_covers_something_the_files_really_hold(
    plan, excused: tuple[str, ...]
):
    """An exception matching nothing is stale, and stale is how this began."""
    settings = _all_settings(plan)
    assert any(path[: len(excused)] == excused for path in settings), (
        f"{'.'.join(excused)} is excused but no settings file holds it, so "
        "either the exception or the files moved on without the other"
    )


@pytest.mark.parametrize(
    "must_be_compared",
    [
        ("condition_a", "model", "deployment"),
        ("condition_a", "model", "temperature"),
        ("condition_a", "prompt", "prefix"),
        ("condition_a", "qa", "enabled"),
        ("data", "filter", "task_ids"),
        ("execution", "timeout"),
    ],
)
def test_nothing_excuses_the_things_the_comparison_holds_still(
    must_be_compared: tuple[str, ...],
):
    assert _may_differ(must_be_compared) is None


def test_the_run_place_itself_is_the_one_thing_allowed_to_differ():
    """The comparison varies exactly this, so it cannot be a refusal."""
    assert _may_differ(("execution", "mode")) is not None


def test_an_exception_covers_everything_beneath_it():
    assert _may_differ(("experiment", "id")) is not None
    assert _may_differ(("experiment",)) is not None
    assert _may_differ(("execution", "sandbox", "image")) is not None
    # …and nothing above or beside it.
    assert _may_differ(("execution",)) is None
    assert _may_differ(("experimental",)) is None


# ── The container's own way of calling the model again ────────────────────


def _container_settings(**sandbox) -> dict:
    """One run place that is a container, named the way the runner names it.

    The rule decides who to ask by ``execution.mode``, the setting the runner
    itself dispatches on, so the mode is what makes this a container here too.
    """
    return {
        "docker_container": {
            "execution": {
                "mode": EXECUTION_MODE_BY_ENVIRONMENT[ENVIRONMENT_DOCKER_CONTAINER],
                "sandbox": sandbox,
            }
        }
    }


def test_the_committed_container_file_is_clean(plan, copied_root):
    """`repair: enabled: false` is written in the file, and it is load-bearing."""
    assert (
        _check_the_container_calls_no_model_after_the_code_is_made(
            {
                place: yaml.safe_load(
                    (copied_root / str(relative)).read_text(encoding="utf-8")
                )
                for place, relative in plan["experiment_files"].items()
            },
            COMPARISON_SAME_GENERATED_CODE,
        )
        == []
    )


def test_switching_the_repair_loop_on_is_refused():
    problems = _check_the_container_calls_no_model_after_the_code_is_made(
        _container_settings(repair={"enabled": True}),
        COMPARISON_SAME_GENERATED_CODE,
    )
    assert len(problems) == 1
    assert "execution.sandbox.repair.enabled" in problems[0]
    assert "sets" in problems[0]
    assert "asks the model for the code again" in problems[0]


@pytest.mark.parametrize(
    "sandbox",
    [
        pytest.param({}, id="the whole repair block deleted"),
        pytest.param({"repair": {}}, id="the enabled setting deleted"),
        pytest.param({"repair": {"max_attempts": 2}}, id="only max_attempts left"),
    ],
)
def test_leaving_the_repair_loop_out_is_refused_because_absent_means_on(sandbox):
    """The case that matters most, and the one a falsy check would miss.

    ``core/sandbox_runner.py`` builds its settings as
    ``{"enabled": True, ..., **(repair or {})}``, so deleting the block turns
    the repair loop *on*. A check that read an absent setting as "off" would
    report the run clean at the moment it became least safe.
    """
    problems = _check_the_container_calls_no_model_after_the_code_is_made(
        _container_settings(**sandbox), COMPARISON_SAME_GENERATED_CODE
    )
    assert len(problems) == 1
    assert "leaves execution.sandbox.repair.enabled out" in problems[0]
    assert "the runner reads as True" in problems[0]


def test_the_default_this_check_assumes_is_the_one_the_runner_really_uses():
    """Read the default from the runner, not from a sentence about it.

    This is the difference between a check that is right and a check that was
    right on the day it was written.
    """
    absent, _ = CONTAINER_SETTINGS_THAT_CALL_THE_MODEL_AGAIN[("repair", "enabled")]
    built_with_nothing_written = SandboxRunner(llm_client=object())
    assert built_with_nothing_written.repair_cfg["enabled"] is absent


def test_the_picture_check_calls_a_vision_model_and_is_refused():
    problems = _check_the_container_calls_no_model_after_the_code_is_made(
        _container_settings(
            repair={"enabled": False}, output_qa={"vision": {"enabled": True}}
        ),
        COMPARISON_SAME_GENERATED_CODE,
    )
    assert len(problems) == 1
    assert "execution.sandbox.output_qa.vision.enabled" in problems[0]
    assert "vision model" in problems[0]


def test_the_picture_check_really_is_off_when_left_out(tmp_path, monkeypatch):
    """The other default, also derived: run the real function and watch.

    ``core/output_qa.py`` reads ``vision.enabled`` with no default, so absent
    means off — but that is checked here by calling it, because the table this
    module keeps is only worth anything if it matches the code.
    """
    rendered = tmp_path / "page.png"
    rendered.write_bytes(b"")
    monkeypatch.setattr(
        output_qa_module,
        "classify_kind",
        lambda suffix: next(iter(output_qa_module._PRIMARY_KINDS)),
    )
    monkeypatch.setattr(
        output_qa_module,
        "render_artifact",
        lambda *args, **kwargs: SimpleNamespace(
            to_dict=lambda: {},
            rendered_images=[rendered],
            errors=[],
            blank_pages=[],
            page_white_fractions=[0.5],
            page_count=1,
        ),
    )
    asked: list[str] = []

    def watched_vision_qa(*args, **kwargs):
        asked.append("called")
        return {"visual_ok": True, "issues": []}

    monkeypatch.setattr(output_qa_module, "_vision_qa", watched_vision_qa)
    deliverable = tmp_path / "deliverable.pdf"
    deliverable.write_bytes(b"")

    absent, _ = CONTAINER_SETTINGS_THAT_CALL_THE_MODEL_AGAIN[
        ("output_qa", "vision", "enabled")
    ]
    output_qa_module.run_output_qa([deliverable], config={}, out_dir=tmp_path)
    assert bool(asked) is bool(absent)

    output_qa_module.run_output_qa(
        [deliverable], config={"vision": {"enabled": True}}, out_dir=tmp_path
    )
    assert asked, (
        "the vision check was never reachable, so the test above proved "
        "nothing about the default"
    )


def test_every_container_setting_watched_here_says_what_calling_it_does():
    for path, (_, what_it_does) in CONTAINER_SETTINGS_THAT_CALL_THE_MODEL_AGAIN.items():
        assert len(what_it_does.split()) >= 6, (
            f"{'.'.join(path)} is watched with the reason '{what_it_does}', "
            "which will not survive the next person who wonders whether it "
            "still applies"
        )


def test_both_container_settings_are_reported_together():
    problems = _check_the_container_calls_no_model_after_the_code_is_made(
        _container_settings(
            repair={"enabled": True}, output_qa={"vision": {"enabled": True}}
        ),
        COMPARISON_SAME_GENERATED_CODE,
    )
    assert len(problems) == 2


def test_the_run_places_with_no_container_are_not_asked():
    assert (
        _check_the_container_calls_no_model_after_the_code_is_made(
            {
                "host_python_process": {"execution": {"mode": "subprocess"}},
                "azure_code_interpreter": {"execution": {"mode": "code_interpreter"}},
            },
            COMPARISON_SAME_GENERATED_CODE,
        )
        == []
    )


def test_a_container_with_no_sandbox_block_at_all_is_still_asked():
    """Who gets asked is decided by the mode, not by finding a block to read.

    This was wrong first time round: the rule skipped any run place whose
    sandbox block was empty or missing, which is precisely the state that
    leaves the repair loop switched on.
    """
    problems = _check_the_container_calls_no_model_after_the_code_is_made(
        {
            "docker_container": {
                "execution": {
                    "mode": EXECUTION_MODE_BY_ENVIRONMENT[
                        ENVIRONMENT_DOCKER_CONTAINER
                    ]
                }
            }
        },
        COMPARISON_SAME_GENERATED_CODE,
    )
    assert any("execution.sandbox.repair.enabled" in note for note in problems)


@pytest.mark.parametrize(
    "sandbox",
    [
        {},
        {"repair": {"enabled": True}},
        {"output_qa": {"vision": {"enabled": True}}},
    ],
)
def test_the_other_comparison_leaves_each_tool_its_own_features(sandbox):
    """§6.2 exists to let each tool run as it really runs.

    A rule written for the strict comparison must not fire for the one whose
    whole purpose is to leave these switched on.
    """
    assert (
        _check_the_container_calls_no_model_after_the_code_is_made(
            _container_settings(**sandbox), COMPARISON_TOOL_BUILT_IN_FEATURES
        )
        == []
    )


def test_the_container_rule_is_reached_from_the_check_that_gates_the_spend(
    plan, copied_root
):
    """A rule nothing calls protects nothing."""
    _change_one_run_place(
        copied_root,
        _settings_file_of_one_run_place(plan),
        ("execution", "sandbox", "repair", "enabled"),
        True,
    )
    assert any(
        "execution.sandbox.repair.enabled" in note
        for note in _refusals(plan, copied_root)
    )


def test_the_plan_this_repository_ships_asks_for_the_strict_comparison(plan):
    """If the plan changed comparison, the rule above stops applying — say so."""
    assert plan["comparison"] == COMPARISON_SAME_GENERATED_CODE


# ── How it is written, not only what it does ──────────────────────────────


def test_the_compared_settings_are_read_from_the_files_not_typed(plan):
    """An equality result cannot tell a derived set from a lucky list.

    The previous version went wrong precisely because its set was typed out,
    so look at how the replacement is written as well as what it returns.
    """
    body = inspect.getsource(_check_settings_the_plan_does_not_name)
    body = body.split('"""')[-1]
    assert "_settings_in(" in body
    assert "_may_differ(" in body
    for path in _all_settings(plan):
        if _may_differ(path) is not None:
            continue
        assert f'"{path[-1]}"' not in body, (
            f"{'.'.join(path)} is typed into the comparison as well as being "
            "read from the files, so the two can drift apart again"
        )


def test_no_block_list_survives_anywhere_in_the_module():
    """The constant that caused this is gone, not renamed."""
    assert not hasattr(
        execution_envelope_preflight, "BLOCKS_THAT_MUST_MATCH_EVERYWHERE"
    )


def test_the_plain_words_describe_settings_the_files_really_hold(plan):
    """A glossary entry for a setting nothing sets is a sentence going stale."""
    settings = {".".join(path) for path in _all_settings(plan)}
    unused = sorted(name for name in WHAT_THE_SETTING_DOES if name not in settings)
    assert unused == [], (
        "these settings are described in plain words but no settings file "
        "holds them: " + ", ".join(unused)
    )


# ── The container's own way of being briefed better than the others ───────


def test_the_committed_container_file_is_told_no_more_than_the_others(
    plan, copied_root
):
    """`max_skills: 0` is written in the file, and it is load-bearing."""
    assert (
        _check_the_container_is_told_no_more_than_the_others(
            {
                place: yaml.safe_load(
                    (copied_root / str(relative)).read_text(encoding="utf-8")
                )
                for place, relative in plan["experiment_files"].items()
            }
        )
        == []
    )


def test_giving_the_container_skills_is_refused():
    problems = _check_the_container_is_told_no_more_than_the_others(
        _container_settings(max_skills=3)
    )
    assert len(problems) == 1
    assert "execution.sandbox.max_skills" in problems[0]
    assert "sets" in problems[0]
    assert "prompt_strategy" in problems[0]


@pytest.mark.parametrize(
    "sandbox",
    [
        pytest.param({}, id="the whole sandbox block empty"),
        pytest.param(
            {"repair": {"enabled": False}}, id="everything else written but not this"
        ),
    ],
)
def test_leaving_max_skills_out_is_refused_because_absent_means_all_of_them(sandbox):
    """The case that matters most here too, and for the same reason.

    ``core/executor.py`` reads the setting as ``opts.get("max_skills", 5)``, so
    deleting the line does not mean "no skills" — it means as many as the
    repository has. The one run place with a block of its own is the one that
    can be quietly given a manual the other two never see.
    """
    problems = _check_the_container_is_told_no_more_than_the_others(
        _container_settings(**sandbox)
    )
    assert len(problems) == 1
    assert "leaves execution.sandbox.max_skills out" in problems[0]
    assert "the runner reads as 5" in problems[0]


def test_the_skill_default_this_check_assumes_is_the_runner_s_own():
    """Read the default from the runner, not from a sentence about it."""
    absent, _ = CONTAINER_SETTINGS_THAT_ADD_TO_THE_PROMPT[("max_skills",)]
    built_with_nothing_written = SandboxRunner(llm_client=object())
    assert built_with_nothing_written.max_skills == absent


def test_the_default_really_reaches_for_every_skill_the_repository_has():
    """The reason given is a claim about this repository, so check it here."""
    absent, _ = CONTAINER_SETTINGS_THAT_ADD_TO_THE_PROMPT[("max_skills",)]
    shipped = sorted(SkillsRegistry().skills)
    assert shipped, "no skill documents found, so this rule guards nothing"
    assert absent >= len(shipped), (
        f"the reason says an absent setting hands the container every skill "
        f"there is, but the default selects {absent} and the repository now "
        f"ships {len(shipped)}: {', '.join(shipped)} — reword the reason"
    )


def test_a_selected_skill_really_is_written_into_the_prompt():
    """Why this setting is not just a container detail, derived by calling it.

    The manual goes into the prompt ahead of the task, which is exactly what
    every one of the three files says it is holding still. Run against the real
    registry and the real renderer rather than trusting a sentence about them.
    """
    assert DEFAULT_SECTIONS.index("skills_manual") < DEFAULT_SECTIONS.index("task")

    registry = SkillsRegistry()
    # Built from what the skills themselves say they match, so the probe keeps
    # working when the skills change.
    files = [
        f"reference{skill.file_extensions[0]}"
        for skill in registry.skills.values()
        if skill.file_extensions
    ]
    task_text = " ".join(
        keyword for skill in registry.skills.values() for keyword in skill.keywords
    )

    none_at_all = registry.select(files, task_text, max_skills=0)
    assert none_at_all == []
    assert registry.render_manual(none_at_all) == ""

    absent, _ = CONTAINER_SETTINGS_THAT_ADD_TO_THE_PROMPT[("max_skills",)]
    what_absent_would_give = registry.select(files, task_text, max_skills=absent)
    assert what_absent_would_give, "the probe selected nothing, so this proves nothing"
    assert registry.render_manual(what_absent_would_give).strip() != ""


def test_the_promise_this_rule_holds_the_container_to_is_in_every_file(plan):
    """The rule is not invented here; the files say it themselves."""
    for relative in plan["experiment_files"].values():
        document = yaml.safe_load(
            (BATCH_RUNNER_ROOT / str(relative)).read_text(encoding="utf-8")
        )
        assert "prompt_strategy" in document["control"]["fixed"]


def test_the_rule_holds_whichever_comparison_is_being_run():
    """A file that says it is holding the prompt still has said so either way.

    Written as a fact about the function rather than a pair of cases: unlike
    the rule about calling the model again, this one takes no comparison to
    weigh, so there is no comparison under which it can be skipped.
    """
    parameters = inspect.signature(
        _check_the_container_is_told_no_more_than_the_others
    ).parameters
    assert "comparison" not in parameters


def test_the_whole_check_refuses_a_container_given_extra_skills(plan, copied_root):
    """End to end, through the entry point the gate really calls.

    The regression this pins: with the setting exempted, changing it moved the
    refusal count not at all.
    """
    before = _refusals(plan, copied_root)
    _change_one_run_place(
        copied_root,
        _settings_file_of_one_run_place(plan),
        ("execution", "sandbox", "max_skills"),
        3,
    )
    after = _refusals(plan, copied_root)
    assert len(after) == len(before) + 1
    assert any("execution.sandbox.max_skills" in problem for problem in after)


# ── An exception has to be argued for setting by setting ──────────────────


# What each exception in SETTINGS_ALLOWED_TO_DIFFER really lets through, and
# why each one may differ — setting by setting, not block by block.
#
# An exception is written as a key path and matched by prefix, so naming one
# block excuses every setting under it, including settings written long after
# the argument was made. Those settings have not been argued for. They have
# been inherited.
#
# `execution.sandbox.max_skills` is why this exists. It sat under an exception
# granted for the container's shape — its image, its memory, how many
# processors it gets — and it decides how much instruction goes into the
# container's prompt. It was excused by where it sat, and by nothing else.
#
# Adding a setting under one of these blocks will fail the test below. That is
# the point: write the reason here, or give the setting a rule of its own, as
# max_skills now has.
SETTINGS_EACH_EXCEPTION_COVERS = {
    ("experiment",): {
        "experiment.id": "the name the results are filed under; if the three "
        "shared one they would overwrite each other",
        "experiment.name": "the human title of the run, for the same reason",
        "experiment.description": "prose about the run; nothing reads it back",
        "experiment.author": "who wrote the file; nothing reads it back",
        "experiment.created_at": "when it was written; nothing reads it back",
    },
    ("condition_a", "name"): {
        "condition_a.name": "the label the run place is reported under, which "
        "is the thing being varied",
    },
    ("data", "source"): {
        "data.source": "the repository this run publishes its own results to. "
        "What tasks are run is pinned separately, by data.filter.task_ids, "
        "which is compared, and by the plan's input_file_versions, which pins "
        "the dataset itself by content fingerprint",
    },
    ("execution", "mode"): {
        "execution.mode": "which run place is used, which is the whole point "
        "of the comparison",
    },
    ("execution", "sandbox"): {
        "execution.sandbox.image": "which container image is used; only the "
        "container has one, and it is what the container *is*",
        "execution.sandbox.use_docker": "whether a container is required. "
        "Checked separately and harder, by check_container_cannot_fall_back: "
        "a container run place quietly falling back to the server would make "
        "two of the three run places the same one",
        "execution.sandbox.memory_gb": "how much memory the container gets; "
        "part of describing the run place, not of shaping the answer",
        "execution.sandbox.cpus": "how many processors the container gets, "
        "for the same reason",
        "execution.sandbox.max_skills": "argued for on its own terms and no "
        "longer excused by this block: see "
        "CONTAINER_SETTINGS_THAT_ADD_TO_THE_PROMPT and the tests above",
        "execution.sandbox.repair.enabled": "the container's repair loop, "
        "which the strict comparison forbids outright; watched by "
        "CONTAINER_SETTINGS_THAT_CALL_THE_MODEL_AGAIN rather than compared",
        "execution.sandbox.repair.max_attempts": "how many repair rounds are "
        "allowed, which does not matter while the loop itself is refused",
        "execution.sandbox.output_qa.enabled": "the container's own look at "
        "the files it produced. It reads them; it does not rewrite them, and "
        "the vision half — the half that would call a model — is watched "
        "separately as output_qa.vision.enabled",
        "execution.sandbox.manifest.enabled": "whether a record of the run "
        "place — which executor ran, which packages were installed, what each "
        "attempt did — is written out beside the answer. It is built after "
        "the code has finished and the answer has been chosen, so it cannot "
        "reach the model. It does join the delivered file list, so the "
        "container ships one file the other two do not; that file is about "
        "the run place, which is the thing this comparison is varying",
        "execution.sandbox.manifest.filename": "what that record is called. "
        "Same argument as the line above, and it decides nothing further: an "
        "empty name would not suppress the file, only misname it",
    },
}


def test_every_exception_is_argued_for_setting_by_setting(plan):
    assert set(SETTINGS_EACH_EXCEPTION_COVERS) == set(SETTINGS_ALLOWED_TO_DIFFER), (
        "a new exception was granted without saying which settings it lets "
        "through; add it here with that list"
    )
    settings = _all_settings(plan)
    for exception, argued_for in SETTINGS_EACH_EXCEPTION_COVERS.items():
        covered = {
            ".".join(path)
            for path in settings
            if path[: len(exception)] == exception
        }
        block = ".".join(exception)
        unargued = sorted(covered - set(argued_for))
        assert not unargued, (
            f"{', '.join(unargued)} is excused from the settings comparison "
            f"only because it sits under {block}, and nobody has argued that "
            "it may differ between run places. Either write the reason here, "
            "in SETTINGS_EACH_EXCEPTION_COVERS, or give it a rule of its own, "
            "as execution.sandbox.max_skills has."
        )
        gone = sorted(set(argued_for) - covered)
        assert not gone, (
            f"{', '.join(gone)} is argued for here but no settings file holds "
            f"it any more; drop it from SETTINGS_EACH_EXCEPTION_COVERS"
        )


def test_the_arguments_are_arguments_and_not_placeholders(plan):
    """A one-word reason is how a list of reasons becomes a list of names."""
    too_thin = sorted(
        name
        for reasons in SETTINGS_EACH_EXCEPTION_COVERS.values()
        for name, reason in reasons.items()
        if len(reason.split()) < 6
    )
    assert too_thin == [], (
        "these exemptions are stated but not argued: " + ", ".join(too_thin)
    )


def test_the_setting_that_caused_this_is_no_longer_excused_by_where_it_sits(plan):
    """It is still under an exempt block, and it is no longer unwatched."""
    assert _may_differ(("execution", "sandbox", "max_skills")) is not None
    assert ("max_skills",) in CONTAINER_SETTINGS_THAT_ADD_TO_THE_PROMPT


def test_the_number_this_module_claims_is_the_number_it_reaches(plan, copied_root):
    """The count in the comments, measured rather than remembered.

    Every setting is changed in one run place and the whole check is run. A
    number written in a comment is a number that goes stale; this one cannot,
    because failing here is what stops it.
    """
    settings = _all_settings(plan)
    noticed = []
    for path, value in sorted(settings.items()):
        root = copied_root
        relative = _settings_file_of_one_run_place(plan)
        original = yaml.safe_load(
            (root / relative).read_text(encoding="utf-8")
        )
        _change_one_run_place(root, relative, path, _something_else(value))
        if _refusals(plan, root):
            noticed.append(".".join(path))
        (root / relative).write_text(
            yaml.safe_dump(original, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    assert (len(noticed), len(settings)) == (31, 44), (
        f"the comments in this module and in core/execution_envelope_"
        f"preflight.py say the check reaches 31 of 44 settings; it now "
        f"reaches {len(noticed)} of {len(settings)}. Update both."
    )
    assert "execution.sandbox.max_skills" in noticed


# ---------------------------------------------------------------------------
# A setting the file never mentions
# ---------------------------------------------------------------------------
#
# Every rule above changes a setting and asks whether the check compares it.
# There is a second question, and the check used to answer it wrongly: what
# happens when a file never mentions a setting at all.
#
# The check read an absent key as nought. The runtime does not.
# ``core.experiment_config`` fills a silent file in with its own defaults, and
# for two of these settings that default is not nought — so a file that never
# mentioned re-running failed tasks was read as forbidding it, passed, and then
# re-ran them three times. Silence and the required value were the same 0, so
# the rule written to stop exactly that could not see it.
#
# The other three were refused either way, but the refusal named a number the
# file did not hold, which sends whoever reads it looking for a line that is
# not there.

# What the runtime fills in here is not what a check reading silence as nought
# would assume. These are the two that used to pass.
SETTINGS_WHERE_SILENCE_USED_TO_PASS = (
    ("execution", "resume_max_rounds"),
    ("condition_a", "qa", "max_retries"),
)

# Every setting a run place has to write down rather than leave to a default.
SETTINGS_THAT_HAVE_TO_BE_WRITTEN_DOWN = SETTINGS_WHERE_SILENCE_USED_TO_PASS + (
    ("execution", "max_retries"),
    ("execution", "timeout"),
    ("execution", "mode"),
)


def _delete_from_one_run_place(root: Path, relative: str, path: tuple) -> object:
    """Take a setting out of one file, so it reads as one that never had it.

    The mirror of :func:`_change_one_run_place`. Changing a value asks whether
    the check compares it. Taking it out asks the harder question — whether the
    check can tell a file that forbids something from a file that never
    mentioned it.
    """
    target = root / relative
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    node = document
    for key in path[:-1]:
        node = node[key]
    removed = node.pop(path[-1])
    target.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return removed


def _what_the_runtime_would_do(root: Path, relative: str) -> ExperimentConfig:
    """The same file, read by the loader the real run uses.

    Not a second opinion written here — :mod:`core.experiment_config` is what
    turns one of these files into a run, so what it says a silent file means is
    what a silent file means.
    """
    return ExperimentConfig.from_dict(
        yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    )


def test_the_runtime_fills_in_what_a_silent_file_leaves_out(plan, copied_root):
    """The disagreement this is all about, read out of both real paths.

    Nothing is typed from memory: the defaults come back through
    ``ExperimentConfig.from_dict``. If the loader ever starts reading silence
    as nought, this fails and the rules below become unnecessary — which is the
    point of measuring it rather than asserting it.
    """
    relative = _settings_file_of_one_run_place(plan)
    for path in SETTINGS_THAT_HAVE_TO_BE_WRITTEN_DOWN:
        root = copied_root
        original = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        _delete_from_one_run_place(root, relative, path)
        run = _what_the_runtime_would_do(root, relative)
        settled = {
            ("execution", "resume_max_rounds"): run.execution.resume_max_rounds,
            ("execution", "max_retries"): run.execution.max_retries,
            ("execution", "timeout"): run.execution.timeout,
            ("execution", "mode"): run.execution.mode,
            ("condition_a", "qa", "max_retries"): (
                run.condition_a.qa.max_retries if run.condition_a.qa else None
            ),
        }[path]
        (root / relative).write_text(
            yaml.safe_dump(original, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        if path in SETTINGS_WHERE_SILENCE_USED_TO_PASS:
            assert settled not in (0, None), (
                f"{'.'.join(path)} left out settles at {settled!r}, which the "
                "comparison requires to be 0. If the loader now reads silence "
                "as nought this is no longer a hole — say so here."
            )
        else:
            assert settled == {
                ("execution", "max_retries"): 3,
                ("execution", "timeout"): None,
                ("execution", "mode"): "subprocess",
            }[path]


@pytest.mark.parametrize(
    "path,what_the_refusal_has_to_mention",
    [
        (("execution", "resume_max_rounds"), "re-run"),
        (("condition_a", "qa", "max_retries"), "self-review"),
        (("execution", "max_retries"), "network failure"),
        (("execution", "timeout"), "how long one task may take"),
        (("execution", "mode"), "which mode it runs in"),
    ],
)
def test_a_setting_a_file_never_mentions_is_refused(
    plan, copied_root, path, what_the_refusal_has_to_mention
):
    """Leaving it out is refused, and the refusal says what was left out.

    A refusal that only says the numbers disagree is no use to somebody whose
    file has no such number to look at.
    """
    relative = _settings_file_of_one_run_place(plan)
    _delete_from_one_run_place(copied_root, relative, path)
    refusals = _refusals(plan, copied_root)

    assert refusals, (
        f"a file that never mentions {'.'.join(path)} was accepted. The "
        "runtime would fill it in with a default, so what ran would not be "
        "what was compared."
    )
    assert any("does not say" in one for one in refusals), (
        f"the refusals for a missing {'.'.join(path)} do not say it is "
        f"missing: {refusals}"
    )
    assert any(
        what_the_refusal_has_to_mention in one for one in refusals
    ), f"no refusal names what was left out: {refusals}"


def test_no_refusal_names_a_number_the_file_does_not_hold(plan, copied_root):
    """The three that were refused anyway said 0, or None, or nothing.

    ``execution.max_retries`` left out was refused with "allows 0 attempts",
    and 0 appears nowhere in the file. Whoever went looking for it found the
    key absent and the refusal unexplained.
    """
    relative = _settings_file_of_one_run_place(plan)
    for path, stale in (
        (("execution", "max_retries"), "allows 0 attempts"),
        (("execution", "timeout"), "allows one task None seconds"),
        (("execution", "resume_max_rounds"), "allows 0 extra rounds"),
        (("condition_a", "qa", "max_retries"), "allows 0 self-review attempts"),
    ):
        root = copied_root
        original = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        _delete_from_one_run_place(root, relative, path)
        refusals = _refusals(plan, root)
        (root / relative).write_text(
            yaml.safe_dump(original, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        assert not any(stale in one for one in refusals), (
            f"with {'.'.join(path)} absent, a refusal still quotes {stale!r} "
            f"as though the file held it: {refusals}"
        )


def test_no_self_review_block_at_all_is_read_as_off_and_left_alone(
    plan, copied_root
):
    """The boundary the fix must not cross.

    An absent self-review block really does mean no self-review — the loader
    builds no ``QAConfig`` at all unless the block holds something. So this one
    absence is not a hole, and refusing it would be a false alarm on a file
    that is doing exactly what the shared conditions ask.

    Taken out of every run place, not one, so nothing here is answered by the
    separate rule that holds the files against each other. What is left is the
    rule this work added, and it has to stay quiet.
    """
    for relative in plan["experiment_files"].values():
        _delete_from_one_run_place(copied_root, str(relative), ("condition_a", "qa"))
        run = _what_the_runtime_would_do(copied_root, str(relative))
        assert run.condition_a.qa is None, (
            "this test rests on the loader building no self-review at all "
            "from a missing block; it now builds one, so the rule needs "
            "revisiting"
        )

    assert _refusals(plan, copied_root) == [], (
        "files with no self-review block were refused, but the runtime reads "
        "that as no self-review, which is what the shared conditions ask for"
    )


def test_an_empty_self_review_block_is_read_the_way_the_runtime_reads_it(
    plan, copied_root
):
    """``qa: {}`` too — the loader tests the block for content, not presence."""
    for relative in plan["experiment_files"].values():
        _change_one_run_place(
            copied_root, str(relative), ("condition_a", "qa"), {}
        )
        assert (
            _what_the_runtime_would_do(copied_root, str(relative)).condition_a.qa
            is None
        )

    assert _refusals(plan, copied_root) == []


def test_one_run_place_dropping_the_block_is_still_a_difference(
    plan, copied_root
):
    """Quiet about the absence is not quiet about the disagreement.

    The rule above must not become a licence to leave the block out of one file
    and not the others. That is caught by the rule that holds the run places
    against each other, and it stays caught.
    """
    relative = _settings_file_of_one_run_place(plan)
    _delete_from_one_run_place(copied_root, relative, ("condition_a", "qa"))

    refusals = _refusals(plan, copied_root)
    assert any(
        "condition_a.qa.enabled" in one and "disagree" in one for one in refusals
    ), refusals
    assert not any("does not say how many self-review" in one for one in refusals), (
        "the missing-setting rule fired on a block the runtime reads as no "
        f"self-review at all: {refusals}"
    )


def test_a_self_review_block_that_says_nothing_useful_is_still_refused(
    plan, copied_root
):
    """Present but silent is the case the truthiness guard must still catch.

    A block holding anything at all makes the loader build a self-review with
    its own two attempts. So ``qa`` with a model in it and no attempt count is
    a run that reviews itself twice while the shared conditions allow none.
    """
    relative = _settings_file_of_one_run_place(plan)
    _change_one_run_place(
        copied_root, relative, ("condition_a", "qa"), {"model": None}
    )

    run = _what_the_runtime_would_do(copied_root, relative)
    assert run.condition_a.qa is not None
    assert run.condition_a.qa.max_retries == 2

    refusals = _refusals(plan, copied_root)
    assert any(
        "does not say how many self-review attempts" in one for one in refusals
    ), refusals


def test_the_old_reading_could_not_tell_the_two_files_apart(plan, copied_root):
    """Proof that this can fail, and proof of why it did not fail before.

    The reading the check used to do is written out here rather than patched
    back in, so this test keeps standing once the line it is about is gone. It
    gives the same answer for a file that forbids extra rounds and a file that
    never mentions them. The runtime gives answers three rounds apart.
    """
    relative = _settings_file_of_one_run_place(plan)
    forbids = yaml.safe_load((copied_root / relative).read_text(encoding="utf-8"))
    _delete_from_one_run_place(
        copied_root, relative, ("execution", "resume_max_rounds")
    )
    never_mentions = yaml.safe_load(
        (copied_root / relative).read_text(encoding="utf-8")
    )

    def as_the_check_used_to_read_it(document):
        execution = document.get("execution", {})
        return int(execution.get("resume_max_rounds", 0) or 0)

    assert forbids["execution"]["resume_max_rounds"] == 0
    assert "resume_max_rounds" not in never_mentions["execution"]
    assert as_the_check_used_to_read_it(forbids) == 0
    assert as_the_check_used_to_read_it(never_mentions) == 0, (
        "the old reading is supposed to be blind to the difference; if it is "
        "not, this test no longer proves anything"
    )

    assert ExperimentConfig.from_dict(forbids).execution.resume_max_rounds == 0
    assert (
        ExperimentConfig.from_dict(never_mentions).execution.resume_max_rounds == 3
    )

    refusals = _refusals(plan, copied_root)
    assert any("re-run" in one and "does not say" in one for one in refusals), (
        "the check still cannot tell them apart: " f"{refusals}"
    )


def test_the_refusal_does_not_claim_to_know_what_the_default_is(
    plan, copied_root
):
    """It says a default would decide it, not what the default is.

    The numbers live in :mod:`core.experiment_config`. Copying them here would
    make a second place to change them, and a wrong second place is worse than
    none — it would name a value confidently while the loader used another.
    """
    relative = _settings_file_of_one_run_place(plan)
    for path in SETTINGS_THAT_HAVE_TO_BE_WRITTEN_DOWN:
        root = copied_root
        original = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
        _delete_from_one_run_place(root, relative, path)
        said = [one for one in _refusals(plan, root) if "does not say" in one]
        (root / relative).write_text(
            yaml.safe_dump(original, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        assert said, f"nothing was said about a missing {'.'.join(path)}"
        for one in said:
            assert "fall back to a built-in default" in one or (
                "fall back to a default" in one
            ), one
            assert "the built-in default is" not in one, one
            assert "which is 3" not in one, one


def test_the_committed_files_still_say_all_of_it(plan):
    """The three real files are unaffected, so no existing run changes.

    This is the owner's standing rule — a new condition must not reach back
    into an experiment already agreed. The rule only bites a file that leaves
    one of these out, and none of them does.
    """
    for environment, relative in plan["experiment_files"].items():
        document = yaml.safe_load(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8")
        )
        for path in SETTINGS_THAT_HAVE_TO_BE_WRITTEN_DOWN:
            node = document
            for key in path:
                assert isinstance(node, dict) and key in node, (
                    f"{environment} ({relative}) leaves out {'.'.join(path)}, "
                    "so this rule would newly refuse a file that was already "
                    "agreed. It has to be written into the file first."
                )
                node = node[key]
