"""How many perception calls one task gets must live in exactly one place.

Marking may call a second model to look at a picture and a third to listen to
a sound. How many times per task it may do that is a number with a price on
it, and until now it was written by hand four times:

* ``core/perception/vision.py`` defined ``VISION_CALL_CAP = 5``,
* ``core/perception/audio.py`` defined ``AUDIO_CALL_CAP = 3`` and
  ``AUDIO_TRIM_SECONDS = 30``,
* ``core/grader.py`` typed ``5``, ``3`` and ``30`` again as its own fallbacks,
  never once consulting the constants above,
* ``core/execution_envelope_grading_cost.py`` typed ``5`` and ``3`` a third
  time, as ``DEFAULT_VISUAL_CALLS_PER_TASK`` and
  ``DEFAULT_AUDIO_CALLS_PER_TASK``.

All four agreed, so nothing was wrong today. Nothing bound them either. The
free cost check refuses a plan that allows fewer perception calls than the
settings permit, so when a settings file leaves ``call_cap_per_task`` out, its
copy *is* the figure the refusal is measured against. Raising what the run
falls back to without raising that copy would have let the run make more calls
than the ceiling was ever asked to cover — understating the bill, which is the
direction that costs more than it says, and the same direction as the two
defects before this one.

Two smaller things went with it. Both perception constants called themselves a
"Hard per-task ceiling", which they never were: ``call_cap_per_task`` in the
settings replaces the number, and the grader passed whatever it found there on
every construction. And the note above the settings paths in the cost module
cited ``test_the_limits_read_match_the_judge_the_grader_really_builds`` as the
thing that stopped the fallbacks going stale — but that test builds the real
judge from the *committed* settings, and every committed settings file names
its own caps. The fallback was never reached on either side of that
comparison. The guard was real; the claim about what it guarded was not.

So this module runs that same comparison in the one case the committed
settings cannot reach: a settings document that names perception models and no
caps at all. That is what makes the mirror honest rather than merely claimed.

``test_raising_the_run_fallback_raises_what_the_check_demands`` is the keystone.
It patches the perception modules in a fresh interpreter *before* the cost
module is first imported, and asserts the cost module follows. It is the only
test here that fails if somebody types the numbers back in while they still
agree, which is exactly how this defect would return.

Nothing here calls a model, marks anything, or spends anything.
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from core.execution_envelope_cost import CostAssumptions
from core.execution_envelope_grading_cost import (
    DEFAULT_AUDIO_CALLS_PER_TASK,
    DEFAULT_VISUAL_CALLS_PER_TASK,
    check_assumptions_cover_the_caps,
    read_grading_caps,
)
from core.execution_envelope_tasks import (
    load_task_catalog,
    widest_scoring_line_characters,
)
from core.perception.audio import AUDIO_CALL_CAP, AUDIO_TRIM_SECONDS
from core.perception.vision import VISION_CALL_CAP

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
GRADING_CONFIG_DIRECTORY = BATCH_RUNNER_ROOT / "grading_configs"
COST_MODULE = BATCH_RUNNER_ROOT / "core" / "execution_envelope_grading_cost.py"
GRADER_MODULE = BATCH_RUNNER_ROOT / "core" / "grader.py"
VISION_MODULE = BATCH_RUNNER_ROOT / "core" / "perception" / "vision.py"
AUDIO_MODULE = BATCH_RUNNER_ROOT / "core" / "perception" / "audio.py"

#: Each fallback, the module that owns it, and the settings key that replaces
#: it. Every test below that speaks about "the fallbacks" walks this list, so
#: a fourth one cannot be added without being covered.
THE_FALLBACKS = (
    ("VISION_CALL_CAP", VISION_MODULE, "call_cap_per_task"),
    ("AUDIO_CALL_CAP", AUDIO_MODULE, "call_cap_per_task"),
    ("AUDIO_TRIM_SECONDS", AUDIO_MODULE, "trim_seconds"),
)


def settings(**overrides) -> dict:
    """A marking settings document that builds a tool-calling judge."""
    document = {
        "judge": {
            "model": "gpt-5.4",
            "generation": {"max_output_tokens": 2400},
            "tools": {
                "read_deliverable": {
                    "ops": ["inspect_structure", "read_content"],
                    "per_item_call_cap": 8,
                    "max_iterations": 10,
                }
            },
        },
        "prompt": {
            "template": "prompts/grader_judge.md",
            "tool_template": "prompts/grader_judge_v2.md",
        },
        "grader": {"judge_max_retries": 1},
    }
    document.update(overrides)
    return document


def naming_no_caps(**perception) -> dict:
    """Settings that name both perception models and no limit for either.

    This is the shape no committed settings file has, and therefore the shape
    the real-judge comparison in ``test_execution_envelope_grading_cost`` has
    never once evaluated.
    """
    document = settings()
    document["judge"]["perception"] = {
        "visual": {"model": "gpt-5.4", **perception.get("visual", {})},
        "audio": {"model": "gpt-audio-1.5", **perception.get("audio", {})},
    }
    return document


def written(tmp_path: Path, document, name: str = "marking.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def caps_with_a_measured_scoring_line(path: Path):
    """Read the settings and hand in the one width they cannot hold.

    How wide a scoring line can be comes from the pinned dataset, not from a
    settings file, so ``read_grading_caps`` has to be told. Without it the
    input-per-call arithmetic refuses rather than working out a figure with a
    piece missing, which would make these perception tests fail for a reason
    that has nothing to do with perception.
    """
    return read_grading_caps(
        path,
        widest_scoring_line_characters=widest_scoring_line_characters(
            load_task_catalog()
        ),
    )


def plan(caps_used, *, vision_calls=None, audio_calls=None) -> CostAssumptions:
    """A cost sum sitting exactly on the limits these settings impose.

    Everything but the two perception call counts is derived from the caps
    rather than typed, so a change elsewhere moves this fixture instead of
    making these tests report a problem they are not about.
    """
    return CostAssumptions.from_mapping(
        {
            "characters_per_token": "3.0",
            "instruction_character_count": 100,
            "tool_loop_max_model_turns": {"host_python_process": 1},
            "output_tokens_capped_per_attempt": {"host_python_process": False},
            "max_tool_result_tokens_per_turn": {"host_python_process": 0},
            "safety_multiplier": "1.25",
            "grading_required": True,
            "grading_model": caps_used.judge_model,
            "grading_calls_per_rubric_item": (
                caps_used.judge_calls_per_rubric_item
            ),
            "grading_input_tokens_per_call": (
                caps_used.input_tokens_one_call_must_cover(Decimal("3.0"))
            ),
            "grading_output_tokens_per_call": caps_used.output_tokens_per_call,
            "grading_perception": {
                "vision": {
                    "model": caps_used.visual_model,
                    "calls_per_task": (
                        caps_used.visual_calls_per_task
                        if vision_calls is None
                        else vision_calls
                    ),
                    "input_tokens_per_call": 24000,
                    "output_tokens_per_call": 4000,
                },
                "audio": {
                    "model": caps_used.audio_model,
                    "calls_per_task": (
                        caps_used.audio_calls_per_task
                        if audio_calls is None
                        else audio_calls
                    ),
                    "input_tokens_per_call": 1000,
                    "output_tokens_per_call": 1000,
                },
            },
        }
    )


def real_judge(document):
    """The judge ``core/grader.py`` really builds from these settings."""
    from core.grader import Grader

    grader = Grader(
        document,
        rubric_loader=None,
        client=SimpleNamespace(responses=SimpleNamespace(create=None)),
    )
    judge = grader._tool_judge
    assert judge is not None, "these settings built no tool-calling judge"
    return judge


def committed_settings_paths() -> list[Path]:
    found: list[Path] = []
    for path in sorted(GRADING_CONFIG_DIRECTORY.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue
        if "read_deliverable" in ((document.get("judge") or {}).get("tools") or {}):
            found.append(path)
    return found


# --------------------------------------------------------------------------
# What the run really falls back to
# --------------------------------------------------------------------------


def test_the_grader_falls_back_to_the_vision_constant():
    judge = real_judge(naming_no_caps())
    assert judge.vision_perception is not None
    assert judge.vision_perception.call_cap == VISION_CALL_CAP


def test_the_grader_falls_back_to_the_audio_constant():
    judge = real_judge(naming_no_caps())
    assert judge.audio_perception is not None
    assert judge.audio_perception.call_cap == AUDIO_CALL_CAP


def test_the_grader_falls_back_to_the_audio_trim_constant():
    """Seconds of sound sent per call is a price, and it was a copy too."""
    judge = real_judge(naming_no_caps())
    assert judge.audio_perception is not None
    assert judge.audio_perception.trim_seconds == AUDIO_TRIM_SECONDS


@pytest.mark.parametrize("stated", [1, 7, 72, 400])
def test_settings_still_win_over_the_vision_fallback(stated):
    judge = real_judge(naming_no_caps(visual={"call_cap_per_task": stated}))
    assert judge.vision_perception.call_cap == stated


@pytest.mark.parametrize("stated", [1, 9, 120])
def test_settings_still_win_over_the_audio_fallback(stated):
    judge = real_judge(naming_no_caps(audio={"call_cap_per_task": stated}))
    assert judge.audio_perception.call_cap == stated


@pytest.mark.parametrize("stated", [5, 30, 90])
def test_settings_still_win_over_the_trim_fallback(stated):
    judge = real_judge(naming_no_caps(audio={"trim_seconds": stated}))
    assert judge.audio_perception.trim_seconds == stated


# --------------------------------------------------------------------------
# The comparison the committed settings could never reach
# --------------------------------------------------------------------------


def test_the_cost_check_reads_the_same_fallback_the_grader_does(tmp_path):
    """The real-judge comparison, run where it had never been run.

    ``test_the_limits_read_match_the_judge_the_grader_really_builds`` does this
    for every committed settings file. All of them name their caps, so both
    sides read the settings and neither reached a fallback. Here neither side
    can read the settings, so both must reach one — and it has to be the same
    one.
    """
    document = naming_no_caps()
    judge = real_judge(document)
    read = read_grading_caps(written(tmp_path, document))

    assert read.visual_calls_per_task == judge.vision_perception.call_cap
    assert read.audio_calls_per_task == judge.audio_perception.call_cap


def test_this_is_the_case_the_committed_settings_never_reach():
    """Why this module exists, asserted rather than asserted-in-a-comment.

    If a settings file ever stops naming a perception cap, the older
    comparison starts covering the fallback on its own and this note becomes
    wrong. Better to be told than to keep a stale reason.
    """
    paths = committed_settings_paths()
    assert paths, "no tool-calling marking settings found"
    for path in paths:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        perception = ((document.get("judge") or {}).get("perception") or {})
        for modality in ("visual", "audio"):
            block = perception.get(modality) or {}
            if not (block.get("model") or block.get("deployment")):
                continue
            assert "call_cap_per_task" in block, (
                f"{path.name} now leaves {modality} call_cap_per_task out, so "
                "the committed-settings comparison reaches the fallback by "
                "itself and this module's stated reason needs rewriting"
            )


def test_the_ceiling_and_the_run_agree_on_every_fallback(tmp_path):
    document = naming_no_caps()
    read = read_grading_caps(written(tmp_path, document))
    assert read.visual_calls_per_task == VISION_CALL_CAP
    assert read.audio_calls_per_task == AUDIO_CALL_CAP


def test_the_named_defaults_are_the_perception_constants():
    assert DEFAULT_VISUAL_CALLS_PER_TASK == VISION_CALL_CAP
    assert DEFAULT_AUDIO_CALLS_PER_TASK == AUDIO_CALL_CAP


# --------------------------------------------------------------------------
# The keystone: one source, proved by moving it
# --------------------------------------------------------------------------


def run_with_patched_caps(vision_cap: int, audio_cap: int) -> list[str]:
    """Import the cost module in a fresh interpreter with moved constants.

    Patching before the first import is what makes this a real test rather
    than a restatement: a module that imports its fallback picks the new
    number up, and a module that types its own does not.
    """
    program = textwrap.dedent(
        f"""
        import core.perception.vision as vision
        import core.perception.audio as audio
        vision.VISION_CALL_CAP = {vision_cap}
        audio.AUDIO_CALL_CAP = {audio_cap}
        import core.execution_envelope_grading_cost as cost
        print(cost.DEFAULT_VISUAL_CALLS_PER_TASK)
        print(cost.DEFAULT_AUDIO_CALLS_PER_TASK)
        """
    )
    done = subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(BATCH_RUNNER_ROOT),
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.split()


def test_raising_the_run_fallback_raises_what_the_check_demands():
    """Move the run's fallback; the ceiling's threshold must move with it."""
    assert run_with_patched_caps(9, 7) == ["9", "7"]


def test_lowering_the_run_fallback_lowers_it_too():
    assert run_with_patched_caps(1, 2) == ["1", "2"]


def test_the_unpatched_run_still_reports_the_committed_numbers():
    """The harness above reports the real values when it patches nothing."""
    assert run_with_patched_caps(VISION_CALL_CAP, AUDIO_CALL_CAP) == [
        str(VISION_CALL_CAP),
        str(AUDIO_CALL_CAP),
    ]


# --------------------------------------------------------------------------
# One copy, and no room for a second
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name, owner, _key", THE_FALLBACKS)
def test_each_fallback_is_assigned_in_exactly_one_module(name, owner, _key):
    assigning = [
        path
        for path in sorted((BATCH_RUNNER_ROOT / "core").rglob("*.py"))
        if re.search(rf"^{name} = ", path.read_text(encoding="utf-8"), re.M)
    ]
    assert assigning == [owner], (
        f"{name} should be written once, in {owner.name}; found it in "
        + ", ".join(path.name for path in assigning)
    )


@pytest.mark.parametrize("_name, _owner, key", THE_FALLBACKS)
def test_no_module_types_a_perception_fallback_as_a_number(_name, _owner, key):
    """``.get("call_cap_per_task", 5)`` is how the third copy got in."""
    for path in sorted((BATCH_RUNNER_ROOT / "core").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        typed = re.search(rf'"{key}"\s*,\s*\d', source)
        assert typed is None, (
            f"{path.name} types a number as the fallback for {key!r}: "
            f"{typed.group(0)!r}. Import the constant instead, or the ceiling "
            "and the run can drift apart without anything noticing"
        )


@pytest.mark.parametrize(
    "named, expected",
    [
        ("DEFAULT_VISUAL_CALLS_PER_TASK", "VISION_CALL_CAP"),
        ("DEFAULT_AUDIO_CALLS_PER_TASK", "AUDIO_CALL_CAP"),
    ],
)
def test_the_ceiling_binds_its_defaults_to_the_imported_names(named, expected):
    source = COST_MODULE.read_text(encoding="utf-8")
    match = re.search(rf"^{named} = (.+)$", source, re.M)
    assert match is not None, f"{named} is no longer assigned at module level"
    assert match.group(1).strip() == expected, (
        f"{named} must be bound to {expected}, not written out again"
    )


@pytest.mark.parametrize("name, _owner, _key", THE_FALLBACKS)
def test_the_grader_imports_each_fallback_it_uses(name, _owner, _key):
    source = GRADER_MODULE.read_text(encoding="utf-8")
    assert name in source, (
        f"core/grader.py no longer mentions {name}, so it is falling back to "
        "something of its own again"
    )


# --------------------------------------------------------------------------
# The prose that was wrong
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name, owner, _key", THE_FALLBACKS[:2])
def test_the_constants_do_not_call_themselves_a_hard_ceiling(
    name, owner, _key
):
    source = owner.read_text(encoding="utf-8")
    described = source.split(f"{name} = ")[0].rsplit("\n\n", 1)[-1]
    assert "Hard per-task ceiling" not in described, (
        f"{owner.name} still calls {name} a hard ceiling, which it is not: "
        "the settings replace it on every run that names a number"
    )


@pytest.mark.parametrize("name, owner, key", THE_FALLBACKS)
def test_each_constant_says_what_replaces_it(name, owner, key):
    source = owner.read_text(encoding="utf-8")
    described = source.split(f"{name} = ")[0].rsplit("\n\n", 1)[-1]
    assert key in described, (
        f"the note above {name} does not say that {key} in the settings "
        "replaces it, which is the thing that makes it a fallback and not a "
        "ceiling"
    )


def test_the_settings_note_no_longer_claims_the_fallbacks_are_guarded():
    """The note said the mirror could not go stale quietly. It could."""
    source = COST_MODULE.read_text(encoding="utf-8")
    note = source.split("JUDGE_TOOL_SETTINGS_PATH = ")[0].rsplit("\n\n", 1)[-1]
    assert "mirror that cannot go stale quietly" not in note
    assert "never reached on either side" in note, (
        "the note should say why the older comparison did not cover these "
        "fallbacks, not merely stop claiming that it did"
    )


def test_the_module_says_out_loud_what_it_used_to_get_wrong():
    source = COST_MODULE.read_text(encoding="utf-8")
    docstring = source.split('"""')[1]
    assert "three copies" in docstring
    assert "understat" in docstring, (
        "the docstring should name the direction of the error, because a "
        "ceiling that is too low is the one that costs money"
    )


# --------------------------------------------------------------------------
# The refusal these numbers feed
# --------------------------------------------------------------------------


def test_a_plan_allowing_fewer_calls_than_the_fallback_is_refused(tmp_path):
    """This is what the copied number was the threshold for."""
    document = naming_no_caps()
    caps = caps_with_a_measured_scoring_line(written(tmp_path, document))
    problems = check_assumptions_cover_the_caps(
        plan(caps, vision_calls=VISION_CALL_CAP - 1), caps
    )
    assert any(
        "calls per" in problem and "reading pictures" in problem
        for problem in problems
    ), problems


def test_a_plan_allowing_fewer_sound_calls_is_refused_too(tmp_path):
    document = naming_no_caps()
    caps = caps_with_a_measured_scoring_line(written(tmp_path, document))
    problems = check_assumptions_cover_the_caps(
        plan(caps, audio_calls=AUDIO_CALL_CAP - 1), caps
    )
    assert any(
        "calls per" in problem and "listening to sound" in problem
        for problem in problems
    ), problems


def test_a_plan_meeting_the_fallback_is_not_refused_for_the_call_count(
    tmp_path,
):
    document = naming_no_caps()
    caps = caps_with_a_measured_scoring_line(written(tmp_path, document))
    problems = check_assumptions_cover_the_caps(plan(caps), caps)
    assert not any("calls per" in problem for problem in problems), problems
