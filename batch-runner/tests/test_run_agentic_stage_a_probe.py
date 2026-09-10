"""The runner that spends stage A's money, exercised without spending it.

One paid run is the whole of stage A, so the parts that decide whether it is
allowed to happen are worth more here than the run itself. Three of them:

* **the wording check.** The catalogue holds a hash, never the benchmark text,
  so the prompt is read from the pinned dataset at run time. If that text ever
  differs from what was priced, the run would be asking a different task than
  the one approved, and the money would be spent finding that out. It is caught
  before the first call instead.
* **the free path really being free.** ``--dry-run`` is the whole path minus
  the network. It is only worth having if it genuinely cannot reach out, which
  this proves rather than asserts: no Azure environment is configured under
  test, and building a client without one raises.
* **what survives the run.** The record is the only thing left afterwards, and
  it must not carry the benchmark wording or anything the model said.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

RUNNER_PATH = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_stage_a_probe.py"

from core.agentic_v2_stage_a_probe import PROBE_TOOLS, StageAProbeOutcome  # noqa: E402


def _load_runner():
    """Import the script by path, the way a script without a package is loaded."""
    spec = importlib.util.spec_from_file_location(
        "run_agentic_stage_a_probe", RUNNER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def a_parquet(tmp_path: Path, rows) -> Path:
    import pandas

    target = tmp_path / "pinned.parquet"
    pandas.DataFrame(rows).to_parquet(target)
    return target


def an_outcome(**changes) -> StageAProbeOutcome:
    settings = {
        "reached_a_model": True,
        "resolved_model": "gpt-5.4",
        "requested_deployment": "gpt-5.4",
        "resource": "a-foundry-resource",
        "tools_offered": PROBE_TOOLS,
        "tools_asked_for": ("capabilities_query", "workspace_apply"),
        "turns_taken": 3,
        "stop_reason": "model_stopped_without_finishing",
        "detail": "",
        "ledger": (
            {"turn": 1, "history_entries_sent": 0},
            {"turn": 2, "history_entries_sent": 1},
        ),
    }
    settings.update(changes)
    return StageAProbeOutcome(**settings)


def run_command(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER_PATH), *arguments],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


# ── the wording, which is what says this is the task that was priced ──────


def test_the_task_s_own_wording_is_what_comes_back(tmp_path):
    wording = "write a one-page summary of the attached figures"
    parquet = a_parquet(
        tmp_path,
        [
            {"task_id": "wanted", "prompt": wording},
            {"task_id": "another", "prompt": "something else entirely"},
        ],
    )

    found = runner.read_task_prompt(
        "wanted",
        parquet=parquet,
        expected_sha256=hashlib.sha256(wording.encode("utf-8")).hexdigest(),
    )

    assert found == wording


def test_a_prompt_that_changed_is_refused_as_a_different_task(tmp_path):
    """The dataset is pinned, but pinning is a claim until something checks it.

    A revision that resolved to different text would leave every figure in the
    plan describing a task nobody is running. Cheaper to refuse than to spend a
    dollar discovering it.
    """
    parquet = a_parquet(
        tmp_path, [{"task_id": "wanted", "prompt": "not what was priced"}]
    )

    with pytest.raises(runner.ProbeRefused, match="does not match"):
        runner.read_task_prompt(
            "wanted",
            parquet=parquet,
            expected_sha256=hashlib.sha256(b"what was priced").hexdigest(),
        )


def test_a_task_the_dataset_holds_twice_is_refused(tmp_path):
    """The probe runs one task. Two rows means guessing which, so it stops."""
    parquet = a_parquet(
        tmp_path,
        [
            {"task_id": "wanted", "prompt": "first copy"},
            {"task_id": "wanted", "prompt": "second copy"},
        ],
    )

    with pytest.raises(runner.ProbeRefused, match="exactly one task"):
        runner.read_task_prompt(
            "wanted", parquet=parquet, expected_sha256="does not matter"
        )


def test_a_task_the_dataset_does_not_hold_is_refused(tmp_path):
    parquet = a_parquet(tmp_path, [{"task_id": "another", "prompt": "text"}])

    with pytest.raises(runner.ProbeRefused, match="0 rows"):
        runner.read_task_prompt(
            "wanted", parquet=parquet, expected_sha256="does not matter"
        )


def test_a_missing_dataset_says_how_to_get_the_pinned_one(tmp_path):
    with pytest.raises(runner.ProbeRefused) as refusal:
        runner.read_task_prompt(
            "wanted",
            parquet=tmp_path / "nothing-here.parquet",
            expected_sha256="does not matter",
        )

    assert runner.DATASET_REVISION in str(refusal.value)
    assert runner.DATASET_REPO_ID in str(refusal.value)


# ── what the run has to have done to count ────────────────────────────────


def test_reaching_a_model_that_then_carried_an_answer_is_what_counts():
    assert runner.exit_condition_met(an_outcome()) is True


def test_a_model_that_was_reached_and_declined_does_not_count():
    """A finding, recorded as one — but stage A's question is still unanswered."""
    declined = an_outcome(
        tools_asked_for=(),
        turns_taken=1,
        ledger=({"turn": 1, "history_entries_sent": 0},),
    )

    assert declined.reached_a_model is True
    assert runner.exit_condition_met(declined) is False


def test_two_turns_that_each_started_from_nothing_do_not_count():
    """Turn count alone would pass this. Carrying is the thing being asked."""
    forgetful = an_outcome(
        ledger=(
            {"turn": 1, "history_entries_sent": 0},
            {"turn": 2, "history_entries_sent": 0},
        )
    )

    assert forgetful.turns_taken == 3
    assert runner.exit_condition_met(forgetful) is False


def test_a_service_that_never_answered_does_not_count():
    unreachable = an_outcome(
        reached_a_model=False, resolved_model=None, turns_taken=0, ledger=()
    )

    assert runner.exit_condition_met(unreachable) is False


# ── what is left on disk afterwards ───────────────────────────────────────


class FakeVerdict:
    task_id = "02aa1805-c658-4069-8a6a-02dec146063a"


def a_record(**changes) -> dict:
    settings = {
        "verdict": FakeVerdict(),
        "said": {
            "prompt_sha256": "a" * 64,
            "approved_maximum_usd": "1.00",
            "most_it_could_cost_usd": "0.59",
        },
        "outcome": an_outcome(),
        "fingerprint": "route-fingerprint-abc123",
        "workspace": Path("/tmp/agentic-v2-stage-a-xyz"),
    }
    settings.update(changes)
    return runner.build_record(**settings)


def test_the_record_names_the_task_and_hashes_its_wording_but_keeps_neither():
    """Enough to say which task ran; not enough to republish the benchmark."""
    record = a_record()

    assert record["task_id"] == FakeVerdict.task_id
    assert record["prompt_sha256"] == "a" * 64
    assert record["dataset_revision"] == runner.DATASET_REVISION
    assert "prompt" not in record
    assert "task_prompt" not in record


def test_nothing_the_model_said_survives_into_the_record():
    secrets = [
        "the model's private working out",
        "sk-a-credential-that-must-not-be-here",
    ]
    record = a_record(
        outcome=an_outcome(
            detail="stopped early",
            ledger=(
                {"turn": 1, "history_entries_sent": 0, "price_usd": "0.01"},
                {"turn": 2, "history_entries_sent": 1, "price_usd": "0.01"},
            ),
        )
    )

    written = json.dumps(record)
    for secret in secrets:
        assert secret not in written


def test_the_route_is_recorded_as_a_fingerprint_and_not_as_an_endpoint():
    record = a_record(fingerprint="route-fingerprint-abc123")

    written = json.dumps(record)
    assert record["route_fingerprint"] == "route-fingerprint-abc123"
    assert "https://" not in written
    assert "openai.azure.com" not in written


def test_the_record_carries_the_gate_s_figures_unchanged():
    """Reformatting the money here would make two numbers for one amount."""
    record = a_record()

    assert record["approved_maximum_usd"] == "1.00"
    assert record["most_it_could_cost_usd"] == "0.59"


def test_the_record_says_whether_the_question_was_answered():
    assert a_record()["exit_condition_met"] is True
    assert (
        a_record(outcome=an_outcome(reached_a_model=False, ledger=()))[
            "exit_condition_met"
        ]
        is False
    )


def test_the_record_can_be_written_down_as_it_stands():
    assert json.loads(json.dumps(a_record(), sort_keys=True))["stage"] == (
        "agentic-v2-stage-a"
    )


# ── the route, checked once it is a fact rather than a request ────────────


PLAN_CONNECTION = {
    "account": "hjeon-fdpo-foundry-eus2",
    "project": "gdpval-realworks",
    "route_profile": "project-ci",
}


def a_route(**changes):
    from core.azure_ai_clients import (
        AzureAIWorkload,
        ClassifiedEndpoint,
        EndpointKind,
        RouteProfile,
        RouteSelection,
    )

    endpoint = {
        "kind": EndpointKind.PROJECT,
        "url": "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/"
        "api/projects/gdpval-realworks",
        "account": "hjeon-fdpo-foundry-eus2",
        "project": "gdpval-realworks",
    }
    profile = changes.pop("profile", RouteProfile.PROJECT_CI)
    endpoint.update(changes)
    return RouteSelection(
        profile=profile,
        workload=AzureAIWorkload.INFERENCE,
        endpoint=ClassifiedEndpoint(**endpoint),
        token_scope="https://ai.azure.com/.default",
    )


def test_the_route_the_plan_fixed_is_accepted():
    assert (
        runner.check_route_is_the_one_the_plan_fixed(a_route(), PLAN_CONNECTION)
        == []
    )


def test_a_different_account_is_refused():
    """A real model over the wrong route costs the same and proves less."""
    problems = runner.check_route_is_the_one_the_plan_fixed(
        a_route(account="some-other-foundry"), PLAN_CONNECTION
    )

    assert len(problems) == 1
    assert "some-other-foundry" in problems[0]


def test_a_different_project_is_refused():
    problems = runner.check_route_is_the_one_the_plan_fixed(
        a_route(project="somebody-elses-project"), PLAN_CONNECTION
    )

    assert len(problems) == 1
    assert "somebody-elses-project" in problems[0]


def test_a_different_route_profile_is_refused():
    from core.azure_ai_clients import RouteProfile

    problems = runner.check_route_is_the_one_the_plan_fixed(
        a_route(profile=RouteProfile.DIRECT_V1), PLAN_CONNECTION
    )

    assert len(problems) == 1
    assert "direct-v1" in problems[0]


def test_every_way_the_route_is_wrong_is_reported_at_once():
    """One dispatch, one list. Fixing these one refusal at a time is three runs."""
    from core.azure_ai_clients import RouteProfile

    problems = runner.check_route_is_the_one_the_plan_fixed(
        a_route(
            account="some-other-foundry",
            project="somebody-elses-project",
            profile=RouteProfile.DIRECT_V1,
        ),
        PLAN_CONNECTION,
    )

    assert len(problems) == 3


# ── the route CI actually produces, which is not the one above ────────────
#
# Measured rather than imagined. With AZURE_AI_ROUTE_PROFILE=project-ci and a
# project endpoint configured, the selection for inference comes back as an
# account-scoped `direct-v1` URL derived from that project endpoint — carrying
# the account, and `project` of None. Checking the selection's project alone
# would therefore refuse the one configuration the workflow uses, after the
# Azure sign-in and before anything was asked: no money, but a dispatch spent
# reporting a fault that was in the check.


def the_route_ci_produces():
    """What `project-ci` really selects for inference: no project on it."""
    from core.azure_ai_clients import (
        AzureAIWorkload,
        ClassifiedEndpoint,
        EndpointKind,
        RouteProfile,
        RouteSelection,
    )

    return RouteSelection(
        profile=RouteProfile.PROJECT_CI,
        workload=AzureAIWorkload.INFERENCE,
        endpoint=ClassifiedEndpoint(
            kind=EndpointKind.DIRECT_V1,
            url="https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/openai/v1/",
            account="hjeon-fdpo-foundry-eus2",
            project=None,
        ),
        token_scope="https://ai.azure.com/.default",
    )


def settings_naming(project: str | None):
    from core.azure_ai_clients import (
        AzureAIRouteSettings,
        ClassifiedEndpoint,
        EndpointKind,
        RouteProfile,
    )

    endpoint = None
    if project is not None:
        endpoint = ClassifiedEndpoint(
            kind=EndpointKind.PROJECT,
            url="https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/"
            f"api/projects/{project}",
            account="hjeon-fdpo-foundry-eus2",
            project=project,
        )
    return AzureAIRouteSettings(profile=RouteProfile.PROJECT_CI, project=endpoint)


def test_the_route_the_workflow_really_gets_is_accepted():
    assert (
        runner.check_route_is_the_one_the_plan_fixed(
            the_route_ci_produces(),
            PLAN_CONNECTION,
            settings=settings_naming("gdpval-realworks"),
        )
        == []
    )


def test_a_project_endpoint_for_somebody_else_is_still_refused():
    """The point of looking further, not a way of looking away."""
    problems = runner.check_route_is_the_one_the_plan_fixed(
        the_route_ci_produces(),
        PLAN_CONNECTION,
        settings=settings_naming("somebody-elses-project"),
    )

    assert len(problems) == 1
    assert "somebody-elses-project" in problems[0]


def test_a_project_nothing_names_is_refused_rather_than_skipped():
    """An unconfirmable project is the case a quiet skip would hide."""
    problems = runner.check_route_is_the_one_the_plan_fixed(
        the_route_ci_produces(), PLAN_CONNECTION, settings=settings_naming(None)
    )

    assert len(problems) == 1
    assert "nothing to check it against" in problems[0]


def test_the_runner_hands_the_check_the_settings_it_built_the_client_from():
    """Two readings of the environment could disagree; there is only one."""
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert "settings = AzureAIRouteSettings.from_env()" in source
    assert "settings=settings," in source
    assert "managed.route, connection, settings=settings" in source


# ── the command itself ────────────────────────────────────────────────────


def test_a_missing_dataset_stops_the_command_before_anything_is_built(tmp_path):
    finished = run_command("--parquet", str(tmp_path / "nothing-here.parquet"))

    assert finished.returncode == 1
    assert "Refused before spending anything" in finished.stdout
    assert runner.DATASET_REVISION in finished.stdout


@pytest.mark.skipif(
    not runner.PINNED_DATASET_PARQUET.is_file(),
    reason="the pinned dataset has not been downloaded here",
)
def test_the_dry_run_gets_all_the_way_through_without_reaching_a_network():
    """Not asserted — demonstrated.

    Nothing here configures an Azure route, and the factory refuses to build a
    client without one. So a dry run that exits cleanly is a dry run that never
    tried, and the free path is free for a reason rather than by intention.
    """
    assert "AZURE_AI_ROUTE_PROFILE" not in os.environ

    finished = run_command("--dry-run")

    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "Nothing was asked and nothing was spent" in finished.stdout
    assert "capabilities_query, workspace_apply" in finished.stdout


@pytest.mark.skipif(
    not runner.PINNED_DATASET_PARQUET.is_file(),
    reason="the pinned dataset has not been downloaded here",
)
def test_the_dry_run_prints_the_amount_the_gate_worked_out():
    """The figure a reader sees before approving the spend is the priced one."""
    finished = run_command("--dry-run")

    _, verdict, _ = runner._verdict(runner.STAGE_ONE_PLAN_PATH)
    said = verdict.as_dict()

    assert f"${said['most_it_could_cost_usd']}" in finished.stdout
    assert f"${said['approved_maximum_usd']} approved" in finished.stdout
    assert Decimal(said["most_it_could_cost_usd"]) <= Decimal(
        said["approved_maximum_usd"]
    )


def test_finalize_is_not_something_this_command_could_put_on_offer():
    """The runner hands the module's list over, rather than a list of its own."""
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert "tools=PROBE_TOOLS" in source
    assert "finalize" not in source


# ── the workflow, which is the only place this can actually spend ─────────
#
# Not decoration. The client factory refuses static credentials and takes its
# identity from a federated session, so a job holding ``id-token: write`` is
# the only place a client can be built at all. That makes the workflow file
# part of the guard rather than a convenience around it.


WORKFLOW_PATH = (
    BATCH_RUNNER_ROOT.parent
    / ".github"
    / "workflows"
    / "agentic-v2-stage-a-probe.yml"
)


def workflow() -> dict:
    import yaml

    loaded = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    # PyYAML reads a bare ``on:`` key as the boolean True.
    loaded["on"] = loaded.pop(True, loaded.get("on"))
    return loaded


def test_nothing_but_a_deliberate_dispatch_can_start_this():
    """A push that could spend money is a push nobody asked to pay for."""
    assert set(workflow()["on"]) == {"workflow_dispatch"}


def test_a_dispatch_that_says_nothing_does_not_spend():
    """The default has to be the free one, because defaults are what get run."""
    mode = workflow()["on"]["workflow_dispatch"]["inputs"]["mode"]

    assert mode["default"] == "dry-run"
    assert set(mode["options"]) == {"dry-run", "paid"}


def test_the_paid_job_only_runs_when_the_dispatch_asked_for_it():
    paid = workflow()["jobs"]["paid"]

    assert "inputs.mode == 'paid'" in paid["if"]
    assert paid["needs"] == "free"


def test_the_free_job_cannot_reach_a_network():
    """No federated token, so no client, so no spend — whatever it is asked."""
    free = workflow()["jobs"]["free"]

    assert "id-token" not in (free.get("permissions") or {})
    assert free.get("if") is None


def test_only_the_paid_job_can_hold_a_token_that_reaches_azure():
    paid = workflow()["jobs"]["paid"]

    assert paid["permissions"]["id-token"] == "write"
    assert paid["permissions"]["contents"] == "read"


def test_a_run_is_never_cancelled_part_way_through_a_paid_conversation():
    """A killed run has been charged for turns it will leave no record of."""
    assert workflow()["concurrency"]["cancel-in-progress"] is False


def test_the_record_is_kept_whatever_the_answer_turned_out_to_be():
    """A model that declined is a finding, and findings have to survive."""
    steps = workflow()["jobs"]["paid"]["steps"]
    keeping = [step for step in steps if "upload-artifact" in str(step.get("uses"))]

    assert len(keeping) == 1
    assert "always()" in keeping[0]["if"]


def test_the_run_is_pinned_to_the_same_dataset_revision_the_code_is():
    """A workflow fetching a different revision would fetch a different task."""
    written = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert runner.DATASET_REVISION in written
    assert written.count(runner.DATASET_REVISION) == 2  # once per job


def test_the_workflow_does_not_restate_the_deployment_the_plan_fixes():
    """Two places naming a model is one place waiting to disagree with the run."""
    written = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "gpt-5.4" not in written
    assert "load_stage_one_plan" in written


def test_every_step_that_turns_the_identity_check_on_can_satisfy_it():
    """A step that demands identities it does not pass in dies before asking.

    ``AzureAIRouteSettings.from_env`` refuses outright when
    ``AZURE_AI_REQUIRE_EXPECTED_IDENTITIES`` is on and any of the names its own
    table lists for the profile is absent. It is a good refusal — it is the
    thing that stops a paid run reaching an account nobody named — but a step
    that switches it on and then withholds one of the names does not get a
    careful check, it gets a crash, and it gets it after the federated login
    and before the question. This job set two of the three ``project-ci``
    wants.

    The list is read from the code's table rather than written out here, so a
    profile that grows a fourth requirement fails this test on the day it grows
    it instead of on the day somebody dispatches.
    """
    from core.azure_ai_clients import (
        REQUIRE_EXPECTED_IDENTITIES_ENV,
        REQUIRED_IDENTITY_ENV_BY_PROFILE,
        ROUTE_PROFILE_ENV,
    )

    demanding = [
        step
        for job in workflow()["jobs"].values()
        for step in job.get("steps", [])
        if str((step.get("env") or {}).get(REQUIRE_EXPECTED_IDENTITIES_ENV)) == "1"
    ]

    assert demanding, "no step turns the identity check on"
    for step in demanding:
        env = step["env"]
        profile = str(env[ROUTE_PROFILE_ENV])
        missing = [
            name
            for name in REQUIRED_IDENTITY_ENV_BY_PROFILE[profile]
            if not env.get(name)
        ]
        assert not missing, (
            f"{step.get('name')!r} asks for the {profile} identity check "
            f"without passing {', '.join(missing)}"
        )
