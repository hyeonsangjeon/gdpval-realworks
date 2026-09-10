"""The path from an experiment file to a Codex run, checked end to end on paper.

Everything the Codex run place needs existed before this: a runtime, an auth
command, a workspace per task, deliverable collection, a cost adapter. What did
not exist was any way for an experiment to ask for it. Five separate things
stood between the two, and each of them is checked here, because each one was
found by trying to build the path rather than by reading it:

1. ``execution.mode`` accepted a fixed list of strings that did not include
   ``codex_foundry``, even though the type annotation beside it did and a whole
   validation branch was written against it.
2. The endpoint setting took a literal address only, and this deployment's
   address is a secret in a public repository.
3. ``step1_prepare_tasks.py`` did not carry ``execution.codex`` into the
   prepared file at all, so nothing downstream could see it.
4. ``step2_run_inference.py`` built an Azure client for every mode, and
   ``core.executor`` refuses this one outright if it is handed a client.
5. Only ``prompt.system`` reaches the agent; a prefix, body or suffix would be
   text the file claims and no request carries.

These tests are cheap and call nothing. They exist so that a later edit that
quietly re-opens any of the five fails here rather than at the start of a run
that costs money.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from core.azure_ai_clients import DIRECT_ENDPOINT_ENV, PROJECT_ENDPOINT_ENV
from core.codex_runtime_config import (
    ENDPOINT_FROM_ROUTE_KEY,
    ENDPOINT_LITERAL_KEY,
    CodexProviderConfigurationError,
    resolve_endpoint_setting,
)
from core.experiment_config import ExperimentConfig
from step1_prepare_tasks import _public_codex_config

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = BATCH_RUNNER_ROOT / "experiments" / "exp033_codex_foundry_fixed5.yaml"
ENVELOPE_HOST = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "exp030_envelope_host_python_process.yaml"
)

#: A route that describes the direct ``/openai/v1/`` endpoint, in the shape
#: ``AzureAIRouteSettings.from_env`` reads. Not a real account.
A_DIRECT_ROUTE = {
    "AZURE_AI_ROUTE_PROFILE": "direct-v1",
    DIRECT_ENDPOINT_ENV: "https://example-account.openai.azure.com/openai/v1/",
}


# ── The endpoint setting ────────────────────────────────────────────────────


def test_the_address_comes_from_the_route_the_rest_of_the_repository_uses():
    resolved = resolve_endpoint_setting(
        {ENDPOINT_FROM_ROUTE_KEY: True}, A_DIRECT_ROUTE
    )
    assert resolved == "https://example-account.openai.azure.com/openai/v1/"


def test_a_project_endpoint_alone_still_yields_the_openai_route():
    """The derivation is the repository's, not this function's.

    ``FOUNDRY_PROJECT_ENDPOINT`` is the variable the connection diagnostic is
    given, and ``AzureAIRouteSettings.from_env`` turns it into the account's
    ``/openai/v1/`` address. If this ever stopped working, an experiment would
    need a second secret for an address the run already has.
    """
    resolved = resolve_endpoint_setting(
        {ENDPOINT_FROM_ROUTE_KEY: True},
        {
            "AZURE_AI_ROUTE_PROFILE": "direct-v1",
            PROJECT_ENDPOINT_ENV: (
                "https://example-account.services.ai.azure.com/api/projects/p1"
            ),
        },
    )
    assert resolved.endswith("/openai/v1/")
    assert "/api/projects/" not in resolved


def test_a_literal_address_is_still_accepted():
    literal = "https://example-account.openai.azure.com/openai/v1/"
    assert resolve_endpoint_setting({ENDPOINT_LITERAL_KEY: literal}, {}) == literal


def test_setting_both_is_refused_rather_than_resolved_by_precedence():
    with pytest.raises(CodexProviderConfigurationError) as caught:
        resolve_endpoint_setting(
            {
                ENDPOINT_LITERAL_KEY: "https://a.openai.azure.com/openai/v1/",
                ENDPOINT_FROM_ROUTE_KEY: True,
            },
            A_DIRECT_ROUTE,
        )
    message = str(caught.value)
    assert ENDPOINT_LITERAL_KEY in message and ENDPOINT_FROM_ROUTE_KEY in message


def test_setting_neither_names_both_keys_so_the_fix_is_readable():
    with pytest.raises(CodexProviderConfigurationError) as caught:
        resolve_endpoint_setting({"model": "gpt-5.4"}, A_DIRECT_ROUTE)
    message = str(caught.value)
    assert ENDPOINT_LITERAL_KEY in message and ENDPOINT_FROM_ROUTE_KEY in message


def test_a_missing_route_is_an_error_and_not_an_empty_address():
    """Not ``""``.

    An empty string would arrive at ``CodexProviderSettings`` as a
    missing-endpoint failure with no mention of where the address was supposed
    to come from — a silent absence reported as something else.
    """
    with pytest.raises(CodexProviderConfigurationError) as caught:
        resolve_endpoint_setting({ENDPOINT_FROM_ROUTE_KEY: True}, {})
    assert ENDPOINT_FROM_ROUTE_KEY in str(caught.value)


def test_a_route_that_describes_no_openai_path_is_refused():
    """The legacy route is a different contract, not a fallback.

    ``legacy-rollback`` is the one profile that legitimately resolves without a
    ``/openai/v1/`` endpoint. Codex speaks the undated Responses contract and
    has nothing to post to on the dated route, so this stops rather than
    calling the wrong product.
    """
    with pytest.raises(CodexProviderConfigurationError) as caught:
        resolve_endpoint_setting(
            {ENDPOINT_FROM_ROUTE_KEY: True},
            {
                "AZURE_AI_ROUTE_PROFILE": "legacy-rollback",
                "AZURE_AI_ALLOW_LEGACY_ROLLBACK": "1",
                "AZURE_OPENAI_LEGACY_ENDPOINT": (
                    "https://example-account.openai.azure.com/"
                ),
            },
        )
    assert "openai/v1" in str(caught.value)


# ── What step 1 is allowed to write down ────────────────────────────────────


def test_the_prepared_file_never_carries_the_address():
    kept = _public_codex_config(
        {
            "endpoint": "https://a-real-account.openai.azure.com/openai/v1/",
            "endpoint_from_route": True,
            "model": "gpt-5.4",
            "request_max_retries": 0,
            "stream_max_retries": 0,
        }
    )
    assert "endpoint" not in kept
    assert kept["endpoint_from_route"] is True
    assert kept["model"] == "gpt-5.4"
    for value in kept.values():
        assert "azure.com" not in str(value)


def test_a_codex_block_that_is_only_an_address_leaves_nothing_to_write():
    assert _public_codex_config({"endpoint": "https://a.openai.azure.com/openai/v1/"}) is None
    assert _public_codex_config(None) is None


# ── The experiment file ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def exp033() -> ExperimentConfig:
    return ExperimentConfig.from_yaml(str(EXPERIMENT))


def test_the_mode_is_accepted_rather_than_reported_as_unknown(exp033, monkeypatch):
    """The check and the annotation are one list now.

    Before this, ``valid_modes`` was typed out a second time without
    ``codex_foundry``, so this file collected "execution.mode must be one of
    [...]" next to the errors from the branch that validates ``codex_foundry``.
    """
    for name, value in A_DIRECT_ROUTE.items():
        monkeypatch.setenv(name, value)
    assert exp033.execution.mode == "codex_foundry"
    assert exp033.validate() == []


def test_without_a_route_the_file_is_still_readable(exp033, monkeypatch):
    """Reading the file is not the step that needs the run place's credentials.

    This assertion used to be the other way round, under the name
    *fails early rather than at spend*, and that name was the mistake: the
    process that reads the file and the process that spends are not the same
    one. ``batch-run.yml`` validates the experiment in an early step that
    deliberately holds no credentials — before the gate that decides whether
    the dispatch may spend at all — and the eager check failed run
    ``34479664460`` there with "this environment describes no usable Azure
    route" on a dispatch whose route was present three steps later.

    Nothing about the file goes unchecked as a result; see
    ``test_the_config_check_does_not_need_the_run_places_credentials.py``,
    which also holds the guard that still stops a routeless run before a turn.
    """
    for name in ("AZURE_AI_ROUTE_PROFILE", DIRECT_ENDPOINT_ENV, PROJECT_ENDPOINT_ENV):
        monkeypatch.delenv(name, raising=False)
    assert exp033.validate() == []


def test_the_five_tasks_are_the_envelope_five(exp033):
    """The same five, in the same order, not a comparable-looking different five."""
    pattern = re.compile(r'^\s+- "([0-9a-f-]{36})"$', re.M)
    envelope_ids = pattern.findall(ENVELOPE_HOST.read_text(encoding="utf-8"))
    assert len(envelope_ids) == 5
    assert exp033.data_filter.task_ids == envelope_ids


def test_the_run_is_bounded_before_it_starts(exp033):
    """Fifteen turns, worst case, and no second call per task.

    5 tasks x (1 attempt + 2 infrastructure retries). Self-QA off means no
    review call. The Codex-side retry counters are 0, so one attempt is one
    turn rather than up to thirty requests.
    """
    assert len(exp033.data_filter.task_ids) == 5
    assert exp033.execution.max_retries == 2
    assert exp033.execution.resume_max_rounds == 0
    assert exp033.condition_a.qa is None or not exp033.condition_a.qa.enabled
    codex = exp033.execution.codex
    assert codex["request_max_retries"] == 0
    assert codex["stream_max_retries"] == 0


def test_the_file_names_no_address(exp033):
    raw = EXPERIMENT.read_text(encoding="utf-8")
    assert "azure.com" not in raw
    assert "ai.azure.com" not in raw
    assert exp033.execution.codex.get("endpoint") is None
    assert exp033.execution.codex[ENDPOINT_FROM_ROUTE_KEY] is True


def test_the_deployment_is_named_once_in_two_places_that_must_agree(exp033):
    """``CodexAgentRunner.run`` refuses a mismatch, so catch it here instead.

    A file whose condition records one deployment and whose provider calls
    another would fail at the first task, after the runtime has started.
    """
    assert exp033.execution.codex["model"] == exp033.condition_a.model.deployment


# ── The prompt fields that do not reach the agent ───────────────────────────


@pytest.mark.parametrize("part", ["prefix", "body", "suffix"])
def test_a_prompt_part_the_runner_ignores_is_refused(part, monkeypatch, tmp_path):
    """exp026 declared ``reasoning_effort: low``, step 1 dropped it, and
    exp027's header exists to correct the record. One such correction is
    enough."""
    for name, value in A_DIRECT_ROUTE.items():
        monkeypatch.setenv(name, value)
    document = yaml.safe_load(EXPERIMENT.read_text(encoding="utf-8"))
    document["condition_a"]["prompt"][part] = "text that no request carries"
    path = tmp_path / "modified.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    errors = ExperimentConfig.from_yaml(str(path)).validate()
    assert any(f"condition_a.prompt.{part}" in error for error in errors), errors


def test_the_system_prompt_is_the_one_that_does_reach_it(exp033):
    system = exp033.condition_a.prompt.system
    assert isinstance(system, str) and system.strip()
    assert exp033.condition_a.prompt.prefix is None
    assert exp033.condition_a.prompt.suffix is None
