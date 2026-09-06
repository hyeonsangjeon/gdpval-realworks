"""The API version the plan pins is the one the client code actually sets.

Every other fixed condition in this comparison is checked by opening the
three settings files and comparing them against each other and against the
plan. The API version cannot be checked that way, because the settings files
do not carry one. Whatever version is really in force comes from a constant
in the client code, so a plan can pin ``2025-04-01-preview``, the code send
something else, and every settings comparison still pass.

That is not hypothetical here. ``core/code_interpreter.py`` carried an
``api_version`` parameter defaulting to ``2025-03-01-preview`` — a different
version from the pinned one — for as long as the plan has existed. It did no
harm, because the parameter was never read and the runner refuses to start
without an already-built client, so the version came from whoever built that
client. But nothing said so, and nothing would have said so if the parameter
had ever become live.

These tests hold the rule that closes that gap, and the two properties the
gap depended on: that the runner takes no API version of its own, and that it
will not build its own client.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_preflight import (  # noqa: E402
    _check_the_pinned_api_version_is_the_one_the_code_uses,
    conditions_from_plan,
    load_plan,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)

#: The two constants that decide the version a client is built with. Named
#: here so a test can say which one it moved; the check reads them by import.
THE_CONSTANTS_THAT_DECIDE_IT = (
    ("core.llm_client", "DEFAULT_API_VERSION"),
    ("core.azure_ai_clients", "DEFAULT_LEGACY_API_VERSION"),
)


@pytest.fixture
def conditions():
    return conditions_from_plan(load_plan(PLAN_PATH))


def _check(conditions):
    return _check_the_pinned_api_version_is_the_one_the_code_uses(conditions)


# ── the rule as things stand ──────────────────────────────────────────────


def test_the_pinned_version_and_the_code_agree_today(conditions):
    """The check passes, and passes because the strings match.

    Asserting only that it passes would also pass if the check had quietly
    stopped looking, so the agreement is spelled out separately.
    """
    assert _check(conditions) == []

    pinned = {c.api_version for c in conditions.values()}
    assert len(pinned) == 1, f"the run places pin different versions: {pinned}"
    want = pinned.pop()
    assert want, "the plan pins no API version at all"

    from importlib import import_module

    for module_name, constant in THE_CONSTANTS_THAT_DECIDE_IT:
        module = import_module(module_name)
        assert getattr(module, constant) == want, (
            f"{module_name}.{constant} is not the pinned {want!r}"
        )


# ── the rule when it should fire ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("module_name", "constant"), THE_CONSTANTS_THAT_DECIDE_IT
)
def test_a_code_constant_moving_away_from_the_pinned_version_is_refused(
    conditions, monkeypatch, module_name, constant
):
    """Moving either constant is caught, and the message names which one."""
    from importlib import import_module

    module = import_module(module_name)
    monkeypatch.setattr(module, constant, "2024-01-01-preview")

    problems = _check(conditions)

    assert problems, (
        f"{module_name}.{constant} was moved to a version the plan does not "
        "pin and the check raised nothing"
    )
    said = " ".join(problems)
    assert f"{module_name}.{constant}" in said, said
    assert "2024-01-01-preview" in said, said


def test_a_plan_pinning_nothing_is_refused_rather_than_treated_as_agreement(
    conditions,
):
    """No pinned version is unknown, not agreed.

    An empty string here would otherwise compare equal to nothing and leave
    the loop below with no constant to check, which reads from the outside
    exactly like a check that passed.
    """
    problems = _check(
        {
            environment: replace(condition, api_version="")
            for environment, condition in conditions.items()
        }
    )

    assert problems, "a plan pinning no API version was accepted"
    assert "pins no API version" in " ".join(problems)


def test_run_places_pinning_different_versions_are_refused(conditions):
    environment = sorted(conditions)[0]
    problems = _check(
        {
            **conditions,
            environment: replace(
                conditions[environment], api_version="2023-05-15"
            ),
        }
    )

    assert problems, "two run places pinned different API versions and passed"
    said = " ".join(problems)
    assert "different API versions" in said, said
    assert "2023-05-15" in said, said


def test_one_run_place_pinning_nothing_does_not_ride_on_the_others(conditions):
    """The gap between "nobody pinned" and "everybody pinned".

    Emptying every version is caught, and disagreeing versions are caught,
    but the case in between is the quiet one: gathering the pinned versions
    into a set drops the blank rather than noticing it, so two agreeing run
    places would carry a third that was held to nothing.
    """
    environment = sorted(conditions)[0]
    problems = _check(
        {
            **conditions,
            environment: replace(conditions[environment], api_version=""),
        }
    )

    assert problems, f"{environment} pinned no API version and it passed"
    said = " ".join(problems)
    assert environment in said, said
    assert "pin no API version while the others do" in said, said


def test_a_constant_that_disappeared_is_reported_rather_than_skipped(
    conditions, monkeypatch
):
    """A version that cannot be read is not a version that agreed.

    ``getattr`` with a default, or a bare ``except``, would turn a renamed
    constant into silence — and silence here is indistinguishable from the
    versions matching.
    """
    from importlib import import_module

    module_name, constant = THE_CONSTANTS_THAT_DECIDE_IT[0]
    monkeypatch.delattr(import_module(module_name), constant)

    problems = _check(conditions)

    assert problems, f"{module_name}.{constant} vanished and nothing was said"
    assert "no longer defines" in " ".join(problems)


def test_a_module_that_will_not_import_is_reported_rather_than_skipped(
    conditions, monkeypatch
):
    """The same rule one step earlier: an unreadable module is not agreement.

    A module holding one of these constants could stop importing — a moved
    dependency, a circular import introduced elsewhere. Nothing about that
    says the version matched, so it is reported with the same weight as a
    version that did not match.
    """
    from core import execution_envelope_preflight

    def refuse_to_import(name):
        raise ImportError(f"no module named {name}")

    monkeypatch.setattr(
        execution_envelope_preflight, "import_module", refuse_to_import
    )

    problems = _check(conditions)

    assert problems, "neither constant could be imported and nothing was said"
    said = " ".join(problems)
    assert "could not be imported" in said, said
    # Both modules are reported, not just the first one that failed.
    for module_name, _constant in THE_CONSTANTS_THAT_DECIDE_IT:
        assert module_name in said, f"{module_name} was passed over: {said}"


# ── the two properties the old dead default depended on ───────────────────


def test_the_code_interpreter_runner_takes_no_api_version_of_its_own():
    """One place decides the version, so there is one place to check.

    A parameter here would be a second source: settable, defaulted, and
    invisible to the rule above, which reads the client-code constants.
    """
    import inspect

    from core.code_interpreter import CodeInterpreterRunner

    parameters = inspect.signature(CodeInterpreterRunner.__init__).parameters
    assert "api_version" not in parameters, (
        "the code interpreter runner takes an api_version again. The version "
        "in force comes from the client it is handed, so a parameter here can "
        "only disagree with that client or be ignored — it was ignored before"
    )


def test_the_code_interpreter_runner_will_not_build_its_own_client():
    """The reason a version cannot be set here: the client arrives built.

    If this ever stopped holding, the runner would need a version of its own
    and the single source above would split in two.
    """
    from core.code_interpreter import CodeInterpreterRunner

    with pytest.raises(ValueError, match="client is required"):
        CodeInterpreterRunner()


def test_the_module_no_longer_advertises_a_version_it_does_not_set():
    """The docstring said 2025-03-01-preview; the plan pins a later one.

    A reader checking which version this run place uses read that line, and
    it was neither what the plan pinned nor what anything sent.
    """
    from core import code_interpreter

    assert "2025-03-01-preview" not in (code_interpreter.__doc__ or ""), (
        "the module docstring names a specific API version again. It does not "
        "set one, so any version named here is a claim nothing keeps"
    )
