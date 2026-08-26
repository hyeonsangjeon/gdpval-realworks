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
    CONTAINER_SETTINGS_THAT_CALL_THE_MODEL_AGAIN,
    SETTINGS_ALLOWED_TO_DIFFER,
    WHAT_THE_SETTING_DOES,
    _check_settings_the_plan_does_not_name,
    _check_the_container_calls_no_model_after_the_code_is_made,
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
from core.sandbox_runner import SandboxRunner  # noqa: E402

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
