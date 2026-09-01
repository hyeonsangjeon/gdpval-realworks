"""The free check can read the plan file it exists to check.

Section 11.2 of the run-place comparison specification documents a command:

    python scripts/check_execution_environment_readiness.py --plan <plan>.yaml

and section 13 names the plan it is meant to be given,
``experiments/execution_envelope/advance_check_plan.yaml``. Run together, they
never printed a report. They stopped on

    ValueError: model run conditions are missing required entries: resource

before a single readiness rule was reached — so the free gate standing in front
of a paid run had never once been run against the plan it guards.

The plan is not missing anything, and the fill-in it describes was not missing
either. It says, standing exactly where the field would otherwise be written:

    The Microsoft Foundry resource the deployment lives in is deliberately NOT
    repeated here. It is named once, in the azure_connection block below, and
    the free check fills it in from there; writing it twice would let the two
    copies drift with nothing to notice.

``core.execution_envelope_preflight.conditions_from_plan`` does exactly that.
The command-line tool did not use it. It carried a second, older copy of the
same function, private to the script, and when f728b24 made ``resource``
required it taught the copy in ``core`` to fill the value in and left the copy
in the script behind. Two functions for one job, and only one of them
maintained — which is the drift the plan's comment warns about, arrived at
through code rather than through YAML.

Nothing pointed at it. Thirteen test files call the maintained copy against
this same plan and stayed green throughout. The script is covered too, by
``test_execution_environment_readiness.py``, but only against plans those tests
write themselves, and every one of them wrote the resource into ``shared`` —
which was the only way past the stale copy. So both loaders were proven, on
inputs that could not tell them apart. No workflow runs the command at all.

The fix is a deletion: the script's copy is gone and the maintained one is
imported. These tests hold the result — the documented command reads the
committed plan, the resource reaches the run places from the one place the plan
writes it, and the two loaders are one loader.

Nothing here calls a model, signs in to a cloud account, or spends anything.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_environment_readiness import (  # noqa: E402
    ModelRunConditions,
    check_model_run_conditions,
)
from core.execution_envelope_preflight import (  # noqa: E402
    conditions_from_plan as maintained_loader,
)
from scripts import check_execution_environment_readiness as tool  # noqa: E402

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
CHECK_SCRIPT = (
    BATCH_RUNNER_ROOT / "scripts" / "check_execution_environment_readiness.py"
)

# Where the plan names the Microsoft Foundry resource, and the only place it
# does. The plan's own comment gives this as the reason the run conditions
# leave the field out.
RESOURCE_IS_NAMED_AT = ("azure_connection", "account")


@pytest.fixture(scope="module")
def plan() -> dict:
    return yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))


def test_the_committed_plan_turns_into_run_conditions(plan: dict) -> None:
    """The loader gets through the real file, not a made-up one."""
    try:
        conditions = tool.conditions_from_plan(plan)
    except ValueError as error:  # pragma: no cover - the failure being fixed
        pytest.fail(
            f"{PLAN_PATH.name} cannot be read by the check that guards it: "
            f"{error}"
        )
    assert set(conditions) == {
        "host_python_process",
        "docker_container",
        "azure_code_interpreter",
    }
    assert all(
        isinstance(entry, ModelRunConditions) for entry in conditions.values()
    )


def test_the_tool_and_the_rest_of_the_repository_share_one_loader() -> None:
    """Not two functions that agree today — one function.

    The break was a second copy going stale while the first was fixed. Two
    copies that agree can be checked for agreement; one copy cannot disagree
    with itself, so this asserts the stronger thing.
    """
    assert tool.conditions_from_plan is maintained_loader


def test_the_documented_command_prints_a_report_instead_of_a_traceback() -> None:
    """Section 11.2's command, run exactly as written.

    Exit status alone cannot tell the two outcomes apart: ``--json`` returns 1
    when a run place is blocked, which is the correct and expected answer here,
    and the crash returned 1 as well. So the test asks for the thing only a
    working run produces — a report that parses.
    """
    finished = subprocess.run(
        [
            sys.executable,
            str(CHECK_SCRIPT),
            "--plan",
            str(PLAN_PATH),
            "--skip-docker-probe",
            "--json",
        ],
        cwd=str(BATCH_RUNNER_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert "Traceback" not in finished.stderr, finished.stderr
    report = json.loads(finished.stdout)
    assert report["compared_environments"] == [
        "host_python_process",
        "docker_container",
        "azure_code_interpreter",
    ]


def test_the_resource_each_run_place_holds_is_the_account_the_plan_connects_to(
    plan: dict,
) -> None:
    """One written name, three run places holding it."""
    block, key = RESOURCE_IS_NAMED_AT
    named = plan[block][key]
    assert named, f"the plan writes nothing at {block}.{key}"
    held = {
        environment: entry.resource
        for environment, entry in tool.conditions_from_plan(plan).items()
    }
    assert set(held.values()) == {named}, held


def test_the_plan_does_not_write_the_resource_where_the_conditions_are(
    plan: dict,
) -> None:
    """The file keeps its own promise not to write the name twice.

    If it ever does write it there, the fill-in stops being exercised by the
    committed plan and this file stops proving the thing it was written for.
    """
    conditions = plan["model_run_conditions"]
    assert "resource" not in (conditions.get("shared") or {})
    for environment, override in conditions["by_environment"].items():
        assert "resource" not in (override or {}), environment


def test_a_plan_naming_no_account_is_refused_rather_than_left_half_filled(
    plan: dict,
) -> None:
    """With nothing to inherit, the deployment name alone is not an answer.

    Two deployments of the same name in two different Foundry resources are
    two different models, so a missing account has to stop the check rather
    than produce conditions that merely look complete.
    """
    block, key = RESOURCE_IS_NAMED_AT
    edited = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))
    edited[block].pop(key)
    with pytest.raises(ValueError, match="names no account"):
        tool.conditions_from_plan(edited)


def test_a_run_place_served_by_another_model_must_name_its_own_resource(
    plan: dict,
) -> None:
    """The case the stale copy never knew about.

    Inheriting the pinned resource for a run place whose model comes from
    somewhere else would file it under a resource it does not use. The
    maintained loader refuses instead, and importing it is how the tool gets
    that behaviour.
    """
    edited = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))
    edited["model_run_conditions"]["by_environment"]["docker_container"] = {
        "model_serving_path": "somebody_elses_service"
    }
    with pytest.raises(ValueError, match="nothing here for it to inherit"):
        tool.conditions_from_plan(edited)


def test_a_plan_listing_no_run_place_still_gets_the_plainer_complaint() -> None:
    """The readiness report answers this one, and keeps the right words.

    A plan that lists no run place has nobody to fill the resource in for. The
    report already says exactly that — "no run place was given" — and demanding
    the resource first would swap a plain answer for a complaint about a
    different field.
    """
    empty = {"model_run_conditions": {"shared": {}, "by_environment": {}}}
    assert tool.conditions_from_plan(empty) == {}


def test_the_conditions_the_plan_fixes_are_accepted_as_a_comparison(
    plan: dict,
) -> None:
    """What the check finds now that it can look.

    The three run places are blocked, but not by anything they disagree on:
    every fixed condition matches across all three. Before this could be read,
    that was unknown rather than true.
    """
    problems = check_model_run_conditions(
        tool.conditions_from_plan(plan), comparison=plan["comparison"]
    )
    assert problems == []


def test_every_required_condition_is_carried_by_the_plan(plan: dict) -> None:
    """The guard for the next required field, whatever it turns out to be.

    ``resource`` went missing for weeks because nothing compared this plan
    against the list of conditions a run needs — through the tool that is meant
    to check it. This does the comparison, and names the field rather than
    making the next person find it.
    """
    written = set(plan["model_run_conditions"]["shared"])
    filled_in = {"resource"}
    required = set(ModelRunConditions.field_names())

    missing = sorted(required - written - filled_in)
    assert missing == [], (
        f"{PLAN_PATH.name} does not write these run conditions, and the check "
        f"does not fill them in either: {', '.join(missing)}"
    )

    assert filled_in <= required
    assert not (filled_in & written), (
        "the check fills these in, so the plan writing them too would make two "
        f"copies: {', '.join(sorted(filled_in & written))}"
    )
