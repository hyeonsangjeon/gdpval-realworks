"""The Docker run place must never quietly become the server run place.

This is the single most dangerous failure mode in the whole comparison, and it
is silent. ``SandboxRunner._execute`` has a path that runs the model's Python on
the server's own operating system, after printing a warning, when the container
setting is ``"auto"`` and either the Docker service or the image is missing. If
that happened during a comparison run, the Docker column of the result table
would in fact hold the server column's numbers, and nothing in the table would
say so. Anyone reading it afterwards would draw a conclusion about containers
from a measurement that never involved one.

The comparison therefore requires the container setting ``"always"``. These
tests hold that in place from three directions:

* the behaviour, by running ``_execute`` with the Docker service missing and
  with the image missing, and requiring that neither reaches the server;
* the settings, by reading the committed Docker experiment file;
* the free check, by feeding it a plan that weakens the setting and requiring
  it to refuse.

Nothing here calls a model or starts a container.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core import sandbox_runner  # noqa: E402
from core.execution_envelope_preflight import (  # noqa: E402
    REQUIRED_CONTAINER_SETTING,
    check_container_cannot_fall_back,
    conditions_from_plan,
    check_experiment_files_match_conditions,
    load_plan,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
DOCKER_EXPERIMENT_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "exp031_envelope_docker_container.yaml"
)


class _RefuseToRunOnTheServer:
    """Stands in for the server-side runner and fails if it is ever reached."""

    def __init__(self) -> None:
        self.was_called = False

    def run_code(self, *args, **kwargs):  # pragma: no cover - must not run
        self.was_called = True
        raise AssertionError(
            "the model's Python was about to run on the server's own operating "
            "system while the container was required. That would record a "
            "container result that never involved a container."
        )


def _runner_with_container_required(monkeypatch, *, use_docker="always"):
    runner = sandbox_runner.SandboxRunner(
        llm_client=SimpleNamespace(), use_docker=use_docker
    )
    local = _RefuseToRunOnTheServer()
    monkeypatch.setattr(runner, "_local", local, raising=False)
    return runner, local


def _manifest():
    return SimpleNamespace(to_dict=lambda: {})


def test_missing_docker_service_fails_instead_of_using_the_server(monkeypatch):
    """No Docker service, container required: the task fails and stays failed."""
    monkeypatch.setattr(sandbox_runner, "docker_available", lambda *a, **k: False)
    monkeypatch.setattr(
        sandbox_runner, "docker_image_exists", lambda image: False
    )
    runner, local = _runner_with_container_required(monkeypatch)

    where, result = runner._execute("print(1)", [], _manifest())

    assert local.was_called is False
    assert where == "docker"
    assert result["success"] is False
    assert result["error_category"] == "backend_unavailable"


def test_missing_image_fails_instead_of_using_the_server(monkeypatch):
    """Docker is there but the image is not: still a failure, never the server."""
    monkeypatch.setattr(sandbox_runner, "docker_available", lambda *a, **k: True)
    monkeypatch.setattr(
        sandbox_runner, "docker_image_exists", lambda image: False
    )
    runner, local = _runner_with_container_required(monkeypatch)

    where, result = runner._execute("print(1)", [], _manifest())

    assert local.was_called is False
    assert where == "docker"
    assert result["success"] is False
    assert result["error_category"] == "backend_unavailable"


def test_the_container_is_used_when_it_is_there(monkeypatch):
    """With the setting at 'always', a working container is still used normally."""
    monkeypatch.setattr(sandbox_runner, "docker_available", lambda *a, **k: True)
    monkeypatch.setattr(
        sandbox_runner, "docker_image_exists", lambda image: True
    )
    runner, local = _runner_with_container_required(monkeypatch)
    monkeypatch.setattr(
        runner,
        "_execute_docker",
        lambda code, reference_files: {"success": True, "text": "", "files": []},
        raising=False,
    )

    where, result = runner._execute("print(1)", [], _manifest())

    assert local.was_called is False
    assert where == "docker"
    assert result["success"] is True


def test_the_default_setting_really_would_fall_back(monkeypatch):
    """Show why 'always' is required rather than merely recommended.

    If this test ever stops passing, the silent substitution has been removed
    from the code itself and the comparison no longer needs to defend against
    it. Until then, it documents exactly what the default does.
    """
    monkeypatch.setattr(sandbox_runner, "docker_available", lambda *a, **k: False)
    monkeypatch.setattr(
        sandbox_runner, "docker_image_exists", lambda image: False
    )
    runner = sandbox_runner.SandboxRunner(
        llm_client=SimpleNamespace(), use_docker="auto"
    )
    reached_the_server = {"yes": False}

    class _Noted:
        def run_code(self, *args, **kwargs):
            reached_the_server["yes"] = True
            return {"success": True, "text": "", "files": []}

    monkeypatch.setattr(runner, "_local", _Noted(), raising=False)

    where, _ = runner._execute("print(1)", [], _manifest())

    assert where == "local"
    assert reached_the_server["yes"] is True


def test_the_committed_docker_experiment_requires_the_container():
    """The settings file that would actually run must pin the container."""
    settings = yaml.safe_load(DOCKER_EXPERIMENT_PATH.read_text(encoding="utf-8"))
    sandbox = settings["execution"]["sandbox"]
    assert sandbox["use_docker"] == REQUIRED_CONTAINER_SETTING


def test_the_plan_requires_the_container():
    plan = load_plan(PLAN_PATH)
    assert plan["container"]["use_docker"] == REQUIRED_CONTAINER_SETTING
    assert check_container_cannot_fall_back(plan) == []


@pytest.mark.parametrize("weakened", ["auto", "never", None, ""])
def test_the_free_check_refuses_a_weakened_container_setting(weakened):
    plan = load_plan(PLAN_PATH)
    plan["container"]["use_docker"] = weakened

    problems = check_container_cannot_fall_back(plan)

    assert problems, f"a container setting of {weakened!r} was accepted"
    assert "always" in problems[0]


def test_the_free_check_refuses_a_plan_with_no_container_block():
    plan = load_plan(PLAN_PATH)
    plan.pop("container")

    problems = check_container_cannot_fall_back(plan)

    assert problems
    assert "without anyone noticing" in problems[0]


def test_the_free_check_refuses_a_weakened_docker_experiment_file(tmp_path):
    """Weakening the settings file, not the plan, must also be refused."""
    plan = load_plan(PLAN_PATH)
    conditions = conditions_from_plan(plan)

    weakened = yaml.safe_load(
        DOCKER_EXPERIMENT_PATH.read_text(encoding="utf-8")
    )
    weakened["execution"]["sandbox"]["use_docker"] = "auto"

    root = tmp_path / "batch-runner"
    (root / "experiments" / "execution_envelope").mkdir(parents=True)
    for environment, relative in plan["experiment_files"].items():
        destination = root / relative
        if environment == "docker_container":
            destination.write_text(
                yaml.safe_dump(weakened, sort_keys=False), encoding="utf-8"
            )
        else:
            destination.write_text(
                (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    problems = check_experiment_files_match_conditions(
        plan, conditions, root=root
    )

    assert len(problems) == 1
    assert "sets the container requirement to 'auto'" in problems[0]
    assert "must be 'always'" in problems[0]


def test_the_docker_experiment_otherwise_matches_the_shared_conditions():
    """The container setting is the only thing this run place may differ on."""
    plan = load_plan(PLAN_PATH)
    conditions = conditions_from_plan(plan)

    problems = check_experiment_files_match_conditions(
        plan, conditions, root=BATCH_RUNNER_ROOT
    )

    assert problems == []
