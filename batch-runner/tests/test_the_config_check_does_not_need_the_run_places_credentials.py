"""Reading an experiment file must not require the run place's credentials.

``exp033``'s address is not in the file. It says ``endpoint_from_route: true``,
which means "use the Azure route this run place provides" — the same derivation
every other Azure caller here uses, chosen precisely so that a secret endpoint
never has to be committed to a public repository.

The check that read that setting resolved the address immediately, against
``os.environ``. That is right where the environment is the run's own, and wrong
where it is not, and ``batch-run.yml`` is the second case: it validates the
experiment file in an early step that deliberately holds no credentials, before
the gate that decides whether the dispatch may spend at all. So a dispatch of
``exp033`` died at step 9 of the batch job with

    Invalid experiment config: execution.codex is not usable:
    execution.codex.endpoint_from_route is set, but this environment describes
    no usable Azure route: AZURE_AI_ROUTE_PROFILE is required

on run ``34479664460`` — a run whose route was present three steps later. The
check was not wrong about the environment it was handed. It was asking the
wrong process.

The split this pins is between two questions that were being answered together:

* **Which way does the file name its address?** A property of the file. Answered
  wherever the file is, credentials or not, and still refusing a block that sets
  both keys or neither.
* **What address does this environment provide?** A property of the run place.
  Answered only where the run place is.

Nothing is skipped to achieve that, and the guarantee the old check claimed --
that a run whose address is missing stops before it spends -- is still kept, by
the step that has the environment to keep it with. Both halves are held below,
because dropping either would turn this fix into a hole.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from core.codex_runtime_config import (
    ENDPOINT_FROM_ROUTE_KEY,
    ENDPOINT_LITERAL_KEY,
    CodexProviderConfigurationError,
    check_block_apart_from_its_address,
    select_endpoint_source,
)
from core.experiment_config import ExperimentConfig


BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER_ROOT.parent
EXPERIMENT = BATCH_RUNNER_ROOT / "experiments" / "exp033_codex_foundry_fixed5.yaml"
STEP2 = BATCH_RUNNER_ROOT / "step2_run_inference.py"
BATCH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "batch-run.yml"

#: Everything ``AzureAIRouteSettings.from_env`` reads. Cleared together, so the
#: environment under test is the one the uncredentialed step actually has
#: rather than whatever the developer running pytest happens to export.
EVERY_ROUTE_NAME = (
    "AZURE_AI_ROUTE_PROFILE",
    "AZURE_AI_DIRECT_ENDPOINT",
    "AZURE_OPENAI_ENDPOINT",
    "FOUNDRY_PROJECT_ENDPOINT",
    "AZURE_AI_PROJECT_ENDPOINT",
    "AZURE_AI_LEGACY_ENDPOINT",
    "AZURE_AI_EXPECTED_DIRECT_ACCOUNT",
    "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES",
)

#: A deferred block with nothing wrong with it, as exp033 writes one.
A_GOOD_DEFERRED_BLOCK = {
    ENDPOINT_FROM_ROUTE_KEY: True,
    "model": "gpt-5.4",
    "request_max_retries": 0,
    "stream_max_retries": 0,
}


@pytest.fixture
def no_route(monkeypatch):
    """The environment the early workflow step has: no route, at all."""
    for name in EVERY_ROUTE_NAME:
        monkeypatch.delenv(name, raising=False)


# ── The failure that happened ───────────────────────────────────────────────


def test_the_dispatch_that_died_at_step_nine_now_reads(no_route):
    """The exact reproduction, with the exact file that failed."""
    assert ExperimentConfig.from_yaml(str(EXPERIMENT)).validate() == []


def test_the_two_questions_are_answered_in_different_places(no_route):
    """Which key names the address is answerable here; what it resolves to is not."""
    assert select_endpoint_source(A_GOOD_DEFERRED_BLOCK) is None

    from core.codex_runtime_config import resolve_endpoint_setting

    with pytest.raises(CodexProviderConfigurationError) as raised:
        resolve_endpoint_setting(A_GOOD_DEFERRED_BLOCK, {})
    assert "no usable Azure route" in str(raised.value)


# ── What is still checked without a route ───────────────────────────────────


def test_a_block_naming_neither_is_still_refused():
    with pytest.raises(CodexProviderConfigurationError) as raised:
        select_endpoint_source({"model": "gpt-5.4"})
    assert "neither is set" in str(raised.value)


def test_a_block_naming_both_is_still_refused():
    with pytest.raises(CodexProviderConfigurationError) as raised:
        select_endpoint_source(
            {
                ENDPOINT_LITERAL_KEY: "https://a.services.ai.azure.com/openai/v1/",
                ENDPOINT_FROM_ROUTE_KEY: True,
            }
        )
    assert "set exactly one" in str(raised.value)


def test_a_block_that_is_not_a_block_is_still_refused():
    for absent in (None, "endpoint_from_route", ["endpoint_from_route"]):
        with pytest.raises(CodexProviderConfigurationError):
            select_endpoint_source(absent)


@pytest.mark.parametrize(
    "broken, expected",
    [
        ({"model": ""}, "needs the deployment to call"),
        ({"model": "gpt-5.4", "provider_id": "Not_Valid"}, "lower-case letters"),
        ({"model": "gpt-5.4", "query_params": {"": "x"}}, "needs a name"),
        ({"model": "gpt-5.4", "query_params": {"k": 7}}, "must be a string"),
        (
            {"model": "gpt-5.4", "query_params": {"api-version": "2024-12-01"}},
            "undated contract",
        ),
    ],
)
def test_the_rest_of_a_deferred_block_is_still_its_own_responsibility(
    broken, expected, no_route
):
    """Everything the file decides is still decided while reading the file.

    The ``api-version`` case is the one worth naming: whether it is legal
    depends on the endpoint's *kind*, and a deferred block has no endpoint to
    classify. It is still checkable because the route case has exactly one
    possible kind -- ``resolve_endpoint_setting`` returns ``route.direct_v1``
    or raises -- so "undated" is known from the file alone.
    """
    block = {ENDPOINT_FROM_ROUTE_KEY: True, **broken}
    with pytest.raises(CodexProviderConfigurationError) as raised:
        check_block_apart_from_its_address(block)
    assert expected in str(raised.value)


def test_a_literal_address_is_still_checked_where_it_is_written(no_route, tmp_path):
    """A file that *does* name an address owns it, so a bad one fails here."""
    document = yaml.safe_load(EXPERIMENT.read_text(encoding="utf-8"))
    codex = document["execution"]["codex"]
    codex.pop(ENDPOINT_FROM_ROUTE_KEY)
    codex[ENDPOINT_LITERAL_KEY] = "https://example.services.ai.azure.com/api/projects/p"
    path = tmp_path / "literal.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")

    errors = ExperimentConfig.from_yaml(str(path)).validate()
    assert any("execution.codex is not usable" in error for error in errors), errors


def test_the_stand_in_address_never_leaves_the_function():
    """It exists to fix the endpoint's *kind*, not to describe a resource.

    If it were returned, stored or defaulted to, a run could be pointed at a
    hostname nobody owns; the whole reason the file names no address is that
    the address must be the approved resource's and nothing else.
    """
    from core import codex_runtime_config

    stand_in = codex_runtime_config._THE_SHAPE_A_ROUTE_MUST_PRODUCE
    module = ast.parse(Path(codex_runtime_config.__file__).read_text(encoding="utf-8"))

    def reads_of_it(tree):
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and node.id == "_THE_SHAPE_A_ROUTE_MUST_PRODUCE"
            and isinstance(node.ctx, ast.Load)
        ]

    the_one_function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "check_block_apart_from_its_address"
    )
    assert len(reads_of_it(the_one_function)) == 1
    assert len(reads_of_it(module)) == 1, "read somewhere other than the one place"

    assert check_block_apart_from_its_address(A_GOOD_DEFERRED_BLOCK) is None
    assert stand_in not in str(select_endpoint_source(A_GOOD_DEFERRED_BLOCK))


# ── The guarantee that moved rather than disappeared ────────────────────────


def test_a_routeless_run_still_stops_before_the_first_turn():
    """Step 2 resolves the address and exits, and does it before the executor.

    This is the half that makes the relaxation above safe. Without it the fix
    would be a hole: a file that defers to a route no environment provides
    would read clean and be discovered mid-run, after a turn was bought.
    """
    source = STEP2.read_text(encoding="utf-8")
    resolve_at = source.index("resolve_endpoint_setting(codex_config, os.environ)")
    exit_at = source.index("sys.exit(1)", resolve_at)
    handed_to_executor_at = source.index("codex_options=codex_options")

    assert resolve_at < exit_at < handed_to_executor_at
    assert "execution.codex is not usable" in source[resolve_at:exit_at]


# ── Why the early step cannot simply be given the route ─────────────────────


def _batch_steps():
    workflow = yaml.safe_load(BATCH_WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["batch-run"]["steps"]


def _step_named(name):
    for step in _batch_steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r}")


def test_the_step_that_reads_the_file_holds_no_credentials():
    """Handing it the route would be the other fix, and it is the wrong one.

    This step runs before ``Block unconfirmed codex_foundry``, so giving it the
    Foundry endpoint would put a secret earlier than the gate that decides
    whether this dispatch may spend at all. Moving a credential earlier to
    satisfy a check is exactly the trade this repository does not make.
    """
    step = _step_named("Validate full experiment config")
    declared = " ".join(str(value) for value in (step.get("env") or {}).values())
    for name in EVERY_ROUTE_NAME:
        assert name not in declared, name
    assert "secrets." not in declared


def test_it_still_runs_before_the_gate_that_decides_on_spending():
    names = [step.get("name") for step in _batch_steps()]
    assert names.index("Validate full experiment config") < names.index(
        "Block unconfirmed codex_foundry in credentialed general workflow"
    )
    assert names.index("Validate full experiment config") < names.index(
        "Validate Azure OIDC identity before remote access"
    )
