"""The 34 experiments that predate ``shared_first_request`` must not move.

A setting that changes how a prompt is built is the kind of change that can
silently rewrite every run in the repository, including the ones whose results
are already published and compared against. So the guarantee this file holds is
narrow and absolute: unless an experiment writes ``shared_first_request: true``
in its ``execution`` block, nothing about its first request changes — same
prompt file, same section assembly, same bytes on the wire, same prepared-file
JSON.

The tests are ordered from the config outward to the wire, because that is where
a regression would enter: a default flipped in a dataclass, a key written into a
prepared file that used to be absent, a runner receiving a keyword it used to
build itself, and finally the request text.
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.code_interpreter as code_interpreter_module
import core.sandbox_runner as sandbox_runner_module
import core.subprocess_runner as subprocess_runner_module
from core.code_interpreter import CodeInterpreterRunner
from core.executor import TaskExecutor
from core.experiment_config import ExperimentConfig
from core.sandbox_runner import SandboxRunner
from core.shared_first_request import SHARED_PROMPT_NAME, first_request_fingerprint
from core.subprocess_runner import SubprocessRunner

from tests.test_the_three_run_places_really_send_one_request import (
    MODEL,
    OCCUPATION,
    TASK_PROMPT,
    _ChatCapture,
    _ResponsesCapture,
    _first_request_texts,
)


EXPERIMENTS_DIR = Path(__file__).resolve().parents[1] / "experiments"
SANDBOX_OPTIONS = {"use_docker": "never", "max_skills": 0}


@pytest.fixture
def reference_files(tmp_path: Path) -> list[str]:
    csv_path = tmp_path / "quarterly_revenue.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region", "quarter", "revenue"])
        writer.writerow(["north", "Q1", "1200"])
        writer.writerow(["south", "Q1", "900"])
    notes_path = tmp_path / "analyst_notes.txt"
    notes_path.write_text(
        "North outperformed on the enterprise renewal cycle.\n",
        encoding="utf-8",
    )
    return [str(csv_path), str(notes_path)]


# ── the config layer ─────────────────────────────────────────────────────


def test_the_setting_is_off_unless_an_experiment_writes_it():
    """Every committed experiment, parsed, with the reason it is off recorded."""
    yaml_paths = sorted(EXPERIMENTS_DIR.glob("*.yaml"))
    assert yaml_paths, f"no experiment files found under {EXPERIMENTS_DIR}"

    on, off, unparsable = [], [], []
    for path in yaml_paths:
        try:
            config = ExperimentConfig.from_yaml(str(path))
        except Exception as exc:  # a file this test cannot read is reported, not skipped
            unparsable.append(f"{path.name}: {type(exc).__name__}: {exc}")
            continue
        (on if config.execution.shared_first_request else off).append(path.name)

    assert not unparsable, unparsable
    declared = {
        path.name
        for path in yaml_paths
        if "shared_first_request" in path.read_text(encoding="utf-8")
    }
    assert set(on) == declared, (
        "an experiment is running the shared first request without saying so in "
        f"its file. on={sorted(on)} declared={sorted(declared)}"
    )


def test_a_prepared_file_gains_no_key_when_the_setting_is_off():
    """``to_dict`` output is what it was, key for key, for an experiment that is off.

    The prepared file is read by step2 and is hashed into run records, so an
    extra key with a falsy value is not harmless: it changes the bytes of every
    prepared file in the repository.
    """
    off_paths = [
        path
        for path in sorted(EXPERIMENTS_DIR.glob("*.yaml"))
        if "shared_first_request" not in path.read_text(encoding="utf-8")
    ]
    assert off_paths, "expected at least one experiment that does not set the key"

    for path in off_paths:
        execution = ExperimentConfig.from_yaml(str(path)).to_dict()["execution"]
        assert "shared_first_request" not in execution, path.name


@pytest.mark.parametrize("declared", [False, 0, None, "", "false", "no"])
def test_only_a_real_true_turns_it_on(tmp_path: Path, declared):
    """``is True``, not truthiness — and a string "false" is not a way in.

    YAML makes it easy to write a value that reads as on to a human and as off
    to Python, or the reverse. The parse refuses to guess: anything that is not
    the boolean ``True`` leaves the run on its historical path.
    """
    source = _minimal_experiment_yaml(shared_first_request=declared)
    path = tmp_path / "exp_probe.yaml"
    path.write_text(source, encoding="utf-8")

    assert ExperimentConfig.from_yaml(str(path)).execution.shared_first_request is False


def test_a_real_true_does_turn_it_on(tmp_path: Path):
    """The negative test above is only meaningful next to this one."""
    path = tmp_path / "exp_probe_on.yaml"
    path.write_text(_minimal_experiment_yaml(shared_first_request=True), encoding="utf-8")

    config = ExperimentConfig.from_yaml(str(path))
    assert config.execution.shared_first_request is True
    assert config.to_dict()["execution"]["shared_first_request"] is True


def _minimal_experiment_yaml(*, shared_first_request) -> str:
    rendered = {
        True: "true",
        False: "false",
        0: "0",
        None: "null",
        "": '""',
        "false": '"false"',
        "no": '"no"',
    }[shared_first_request]
    return f"""
experiment_id: exp_probe
name: probe
model:
  provider: azure_openai
  name: gpt-5.2-chat
  deployment: gpt-5.2-chat
execution:
  mode: subprocess
  shared_first_request: {rendered}
conditions:
  - name: condition_a
    prompt_template: default
"""


# ── the runner layer ─────────────────────────────────────────────────────


def test_each_runner_still_loads_its_own_prompt_by_default():
    host = TaskExecutor(mode="subprocess", llm_client=_ChatCapture())
    container = TaskExecutor(
        mode="sandbox", llm_client=_ChatCapture(), sandbox_options=SANDBOX_OPTIONS
    )
    azure = TaskExecutor(
        mode="code_interpreter", code_interpreter_client=_ResponsesCapture()
    )

    assert host.runner.prompt_name == SubprocessRunner.DEFAULT_PROMPT
    assert container.runner.prompt_name == SandboxRunner.DEFAULT_PROMPT
    assert azure.runner.prompt_name == CodeInterpreterRunner.DEFAULT_PROMPT
    for executor in (host, container, azure):
        assert executor.runner.prompt_name != SHARED_PROMPT_NAME
        assert executor.runner.shared_first_request is False


def test_the_default_path_never_calls_the_shared_builder(reference_files, monkeypatch):
    """Proof by removal: with the setting off, the new code is not on the path.

    Asserting that the output looks unchanged would pass if the shared builder
    happened to produce the same text today. Making the function raise proves the
    default request is built by the code that always built it.
    """

    def _refuse(**_kwargs):
        raise AssertionError("the default path reached the shared builder")

    monkeypatch.setattr(subprocess_runner_module, "build_shared_task_text", _refuse)
    monkeypatch.setattr(sandbox_runner_module, "build_shared_task_text", _refuse)
    monkeypatch.setattr(code_interpreter_module, "build_shared_task_text", _refuse)

    for mode, kwargs in (
        ("subprocess", {"llm_client": _ChatCapture()}),
        ("sandbox", {"llm_client": _ChatCapture(), "sandbox_options": SANDBOX_OPTIONS}),
        ("code_interpreter", {"code_interpreter_client": _ResponsesCapture()}),
    ):
        client = kwargs.get("llm_client") or kwargs["code_interpreter_client"]
        result = TaskExecutor(mode=mode, **kwargs).execute(
            task_prompt=TASK_PROMPT,
            model=MODEL,
            reference_files=reference_files,
            occupation=OCCUPATION,
        )
        assert "reached the shared builder" not in (result.get("error") or ""), mode
        assert client.requests, f"{mode} never reached its provider call"


def test_the_default_result_gains_no_record_of_the_request(reference_files):
    """An ordinary experiment's result keeps exactly the keys it always had.

    The request record is the comparison's own bookkeeping. A run that did not
    opt in must not start carrying it: downstream code reads these dicts by key,
    and a new one appearing in every result is a change to every experiment
    rather than to this one.
    """
    for mode, kwargs in (
        ("subprocess", {"llm_client": _ChatCapture()}),
        ("sandbox", {"llm_client": _ChatCapture(), "sandbox_options": SANDBOX_OPTIONS}),
        ("code_interpreter", {"code_interpreter_client": _ResponsesCapture()}),
    ):
        result = TaskExecutor(mode=mode, **kwargs).execute(
            task_prompt=TASK_PROMPT,
            model=MODEL,
            reference_files=reference_files,
            occupation=OCCUPATION,
            # Passed on purpose. The executor writes the task id onto a record
            # when there is one, and this proves it does not create one.
            task_id="02aa1805-c658-4069-8a6a-02dec146063a",
        )
        assert "first_request_observation" not in result, (mode, sorted(result))


# ── the wire ─────────────────────────────────────────────────────────────


def test_the_three_default_requests_stay_three_different_requests(reference_files):
    """The historical asymmetry is still there when nobody opted in.

    This is the control for the capture suite next door. If the defaults were
    quietly made equal too, that suite would pass without the setting doing
    anything, and every published run would have moved.
    """
    captured = {}
    for run_place, mode, kwargs in (
        ("host_python_process", "subprocess", {"llm_client": _ChatCapture()}),
        (
            "docker_container",
            "sandbox",
            {"llm_client": _ChatCapture(), "sandbox_options": SANDBOX_OPTIONS},
        ),
        (
            "azure_code_interpreter",
            "code_interpreter",
            {"code_interpreter_client": _ResponsesCapture()},
        ),
    ):
        client = kwargs.get("llm_client") or kwargs["code_interpreter_client"]
        TaskExecutor(mode=mode, **kwargs).execute(
            task_prompt=TASK_PROMPT,
            model=MODEL,
            reference_files=reference_files,
            occupation=OCCUPATION,
        )
        captured[run_place] = _first_request_texts(client.requests, run_place)

    fingerprints = {
        run_place: first_request_fingerprint(*texts)
        for run_place, texts in captured.items()
    }
    assert len(set(fingerprints.values())) == 3, fingerprints

    # And the wording each run place has always used is still the wording it
    # sends. These three phrases are false in the other two places, which is why
    # the shared prompt drops them and why finding them here is the right check.
    host_text = "\n".join(captured["host_python_process"])
    azure_text = "\n".join(captured["azure_code_interpreter"])
    container_text = "\n".join(captured["docker_container"])
    assert "current directory" in host_text
    assert "/mnt/data" in azure_text
    assert "pip install" in container_text


# ── the refusals ─────────────────────────────────────────────────────────


def test_a_mode_the_setting_is_not_wired_for_refuses_it():
    """Better a raise than a run recorded as shared and built the old way."""
    with pytest.raises(ValueError, match="not implemented for mode"):
        TaskExecutor(
            mode="json_renderer",
            llm_client=_ChatCapture(),
            shared_first_request=True,
        )


def test_the_hardened_substrate_refuses_it():
    """It is a sandbox mode, so the allow-list alone would have let it through."""
    with pytest.raises(ValueError, match="hardened"):
        TaskExecutor(
            mode="sandbox",
            llm_client=_ChatCapture(),
            shared_first_request=True,
            sandbox_options={"hardened_substrate": True},
        )


def test_a_conflicting_prompt_name_refuses_rather_than_wins():
    with pytest.raises(ValueError, match="prompt_name"):
        TaskExecutor(
            mode="subprocess",
            llm_client=_ChatCapture(),
            prompt_name="subprocess_occupation_codegen",
            shared_first_request=True,
        )


@pytest.mark.parametrize(
    "runner_call",
    [
        lambda: SubprocessRunner(
            _ChatCapture(),
            prompt_name="subprocess_occupation_codegen",
            shared_first_request=True,
        ),
        lambda: SandboxRunner(
            _ChatCapture(),
            prompt_name="sandbox_occupation_codegen",
            shared_first_request=True,
        ),
        lambda: CodeInterpreterRunner(
            client=_ResponsesCapture(),
            prompt_name="code_interpreter_occupation_codegen",
            shared_first_request=True,
        ),
    ],
)
def test_each_runner_refuses_the_pair_on_its_own(runner_call):
    """The executor is not the only door into a runner; each one holds the rule."""
    with pytest.raises(ValueError, match=SHARED_PROMPT_NAME):
        runner_call()
