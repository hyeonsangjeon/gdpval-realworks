"""The boot-host survey, exercised without an Azure subscription.

:mod:`scripts.azure_boot_host_survey` exists to answer one question -- could a
Firecracker host go in the subscription the model deployment already lives in,
under permissions that already exist -- and to answer it without doing anything
about the answer. Three properties carry that, and each has a way of quietly
breaking:

**An unmeasured read must never become an absence.** If ``az`` does not answer
the quota question, "there is no quota" and "nobody looked" are different facts
that justify different decisions, and only one of them is true. A survey that
collapsed them would report a block that does not exist and send somebody to
ask for a quota increase they already have. Asserted first and asserted hardest.

**It must have no write path.** The whole justification for running this freely
is that it creates nothing and grants nothing. That is a property of the source,
so it is checked against the source rather than promised in a docstring.

**A blocked answer must report rather than request.** Creating a machine and
granting a role are access changes. The script's job ends at naming them.

Nothing here contacts Azure, calls a model, or spends anything. Every ``az``
read is injected.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
SCRIPT = BATCH_RUNNER_ROOT / "scripts" / "azure_boot_host_survey.py"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "azure-boot-host-survey.yml"

SPEC = importlib.util.spec_from_file_location("azure_boot_host_survey", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
# Registered before execution, not after: ``dataclasses`` resolves a field's
# annotation through ``sys.modules[cls.__module__]``, so a frozen dataclass in a
# by-path module that is not yet registered raises while the class is defined.
sys.modules["azure_boot_host_survey"] = module
SPEC.loader.exec_module(module)

rbac = module._rbac_module()


# ── a fake subscription that answers ──────────────────────────────────────


CONTRIBUTOR = {
    "roleName": "Contributor",
    "permissions": [{"actions": ["*"], "notActions": ["Microsoft.Authorization/*/Write"]}],
}
READER = {"roleName": "Reader", "permissions": [{"actions": ["*/read"], "notActions": []}]}


def az(
    *,
    account=None,
    provider="Registered",
    machines=0,
    free_vcpus=96,
    definitions=(CONTRIBUTOR,),
    fails=(),
):
    """A runner that answers the five reads, and fails whichever are named."""

    def run(arguments):
        head = " ".join(arguments[:2])
        for failing in fails:
            if head.startswith(failing):
                raise rbac.AzureReadFailure(head, exit_code=1)
        if head == "account show":
            return account if account is not None else {
                "id": "s" * 36, "state": "Enabled"
            }
        if head == "provider show":
            return {"registrationState": provider}
        if head == "vm list":
            return [{"name": f"vm{i}"} for i in range(machines)]
        if head == "vm list-usage":
            return [
                {
                    "name": {"value": module.HOST_QUOTA_FAMILY},
                    "limit": free_vcpus,
                    "currentValue": 0,
                }
            ]
        if head == "role assignment":
            return [
                {"roleDefinitionId": f"/x/{i}", "scope": "/subscriptions/x"}
                for i, _ in enumerate(definitions)
            ]
        if head == "role definition":
            return [definitions[0]] if definitions else []
        raise AssertionError(f"the survey asked something unexpected: {head}")

    return run


def surveyed(**kwargs):
    return module.survey(
        runner=az(**kwargs), rbac=rbac, env={"AZURE_CLIENT_ID": "p" * 36}
    )


# ── the property that matters most ────────────────────────────────────────


class TestAnUnmeasuredReadIsNotAnAbsence:
    @pytest.mark.parametrize(
        "failing_read", ["provider show", "vm list-usage", "role assignment", "vm list"]
    )
    def test_any_read_that_did_not_complete_stops_the_verdict(self, failing_read):
        report = surveyed(fails=(failing_read,))
        assert report["verdict"] == module.VERDICT_NOT_MEASURED
        assert report["what_would_have_to_change"] == []

    def test_it_says_which_read_was_missing_rather_than_that_something_failed(self):
        report = surveyed(fails=("vm list-usage",))
        assert "quota" in report["because"]
        assert "evidence of absence" in report["because"]

    def test_a_session_az_cannot_describe_is_not_a_blocked_subscription(self):
        # The shape a local login produces. Reporting a block from here would be
        # reporting on a subscription nobody looked at.
        report = surveyed(fails=("account show",))
        assert report["verdict"] == module.VERDICT_NOT_MEASURED
        assert "outside CI" in report["findings"]["session"]["note"]

    def test_a_role_definition_that_would_not_read_does_not_become_a_denial(self):
        # The subtle one: the assignments listed fine, so it would be easy to
        # evaluate the permissions against an incomplete set of definitions and
        # report a denial the identity does not have.
        report = surveyed(fails=("role definition",))
        assert report["verdict"] == module.VERDICT_NOT_MEASURED
        assert report["findings"]["permissions"]["measured"] is False

    def test_a_quota_family_azure_does_not_list_is_measured_and_is_zero(self):
        # Distinct from the above: Azure answered, and the family was not in the
        # answer. That *is* an absence, and it is allowed to be one.
        def run(arguments):
            if " ".join(arguments[:2]) == "vm list-usage":
                return [{"name": {"value": "standardOtherFamily"}, "limit": 9, "currentValue": 0}]
            return az()(arguments)

        report = module.survey(
            runner=run, rbac=rbac, env={"AZURE_CLIENT_ID": "p" * 36}
        )
        assert report["findings"]["quota"]["measured"] is True
        assert report["verdict"] == module.VERDICT_BLOCKED


# ── the four answers ──────────────────────────────────────────────────────


class TestTheVerdict:
    def test_a_subscription_that_could_take_a_host_today(self):
        report = surveyed()
        assert report["verdict"] == module.VERDICT_WITHIN_PERMISSIONS
        assert report["what_would_have_to_change"] == []

    def test_an_existing_machine_outranks_the_permission_question(self):
        # If a host is already there, the roles to create one are beside the
        # point -- and answering "you may not create one" would be true and
        # useless.
        report = surveyed(machines=2, definitions=(READER,))
        assert report["verdict"] == module.VERDICT_HOST_EXISTS
        assert report["findings"]["existing_hosts"]["answer"]["count"] == 2

    def test_an_existing_machine_is_not_a_claim_that_it_can_boot_a_guest(self):
        report = surveyed(machines=1)
        assert "C2's question" in report["because"]
        assert "a measurement that any machine here can actually boot a guest" in (
            report["is_not"]
        )

    def test_a_reader_role_is_blocked_and_the_three_writes_are_named(self):
        report = surveyed(definitions=(READER,))
        assert report["verdict"] == module.VERDICT_BLOCKED
        named = " ".join(report["what_would_have_to_change"])
        for action, _ in module.REQUIRED_ACTIONS:
            assert action in named

    def test_an_unregistered_provider_blocks_and_is_not_registered_by_the_survey(self):
        report = surveyed(provider="NotRegistered")
        assert report["verdict"] == module.VERDICT_BLOCKED
        assert "would have to be registered" in " ".join(
            report["what_would_have_to_change"]
        )
        assert "itself a write" in report["findings"]["provider"]["note"]

    def test_a_region_with_no_room_blocks_on_capacity_not_on_permission(self):
        report = surveyed(free_vcpus=4)
        assert report["verdict"] == module.VERDICT_BLOCKED
        changes = " ".join(report["what_would_have_to_change"])
        assert "quota increase" in changes
        assert "do not permit" not in changes

    def test_being_blocked_is_reported_and_not_requested(self):
        report = surveyed(definitions=(READER,))
        assert "a report, not a request" in report["and_note"]
        assert "left undone" in report["and_note"]


class TestReadingTheRoles:
    def test_a_wildcard_role_permits_all_three_writes(self):
        report = surveyed()
        assert report["findings"]["permissions"]["answer"]["permits_all_three"] is True

    def test_a_not_action_takes_a_permission_back(self):
        narrowed = {
            "roleName": "Almost",
            "permissions": [
                {"actions": ["*"], "notActions": ["Microsoft.Compute/*/write"]}
            ],
        }
        report = surveyed(definitions=(narrowed,))
        permits = report["findings"]["permissions"]["answer"]["permits"]
        assert permits["Microsoft.Compute/virtualMachines/write"] is False
        assert permits["Microsoft.Network/networkInterfaces/write"] is True

    def test_no_principal_to_ask_about_is_unmeasured_rather_than_denied(self):
        report = module.survey(runner=az(), rbac=rbac, env={})
        assert report["verdict"] == module.VERDICT_NOT_MEASURED


# ── what it must not do, or say ───────────────────────────────────────────


class TestItOnlyReads:
    @pytest.fixture
    def source(self):
        return SCRIPT.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "verb",
        ["vm create", "deployment group create", "provider register",
         "role assignment create", "vm start", "group create"],
    )
    def test_no_mutating_az_command_appears_in_the_source(self, source, verb):
        # A grep, not a promise: if a future edit reaches for a write from the
        # survey, this is the thing that says so.
        assert verb not in source

    def test_it_never_calls_a_model(self, source):
        for path in (
            "responses.create", "chat.completions", "AzureOpenAI",
            "llm_client", "code_interpreter",
        ):
            assert path not in source

    def test_every_az_argument_list_starts_with_a_read(self):
        seen = []

        def watching(arguments):
            seen.append(" ".join(arguments))
            return az()(arguments)

        module.survey(runner=watching, rbac=rbac, env={"AZURE_CLIENT_ID": "p" * 36})
        assert seen, "a survey that asked nothing would pass every check above"
        for call in seen:
            assert any(
                call.endswith(tail) or f" {tail} " in f" {call} "
                for tail in ("show", "list")
            ) or "list" in call, call


class TestItSaysNothingItShouldNot:
    def test_the_subscription_id_is_not_in_the_report(self):
        report = surveyed()
        assert "s" * 36 not in json.dumps(report)
        assert report["findings"]["session"]["answer"]["subscription_id_was_read"] is True

    def test_machine_names_are_counted_and_not_listed(self):
        report = surveyed(machines=3)
        text = json.dumps(report)
        assert "vm0" not in text and "vm1" not in text
        assert report["findings"]["existing_hosts"]["answer"]["count"] == 3

    def test_the_host_it_sizes_for_is_the_one_this_repository_defines(self):
        # If the bicep changes size and this does not, the survey would report
        # room for a machine nobody would deploy.
        bicep = (BATCH_RUNNER_ROOT.parent / "infra" / "dev-host" / "main.bicep")
        if not bicep.is_file():  # pragma: no cover - it is committed
            pytest.skip("the dev-host definition is not committed here")
        assert f"'{module.HOST_VM_SIZE}'" in bicep.read_text(encoding="utf-8")

    def test_it_renders_without_raising_for_every_verdict(self):
        for report in (
            surveyed(),
            surveyed(machines=1),
            surveyed(definitions=(READER,)),
            surveyed(fails=("vm list",)),
        ):
            assert module.render(report).startswith("Boot-host survey")


# ── the workflow that runs it ─────────────────────────────────────────────


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


class TestTheWorkflow:
    def test_it_loads_at_all(self):
        # An unloadable workflow does not fail visibly: GitHub reports a run
        # with zero jobs, named after the file path, which is easy to read as
        # "nothing happened" rather than "this is broken".
        workflow = _workflow()
        assert isinstance(workflow, dict) and workflow["jobs"]

    def test_it_can_only_be_started_by_hand(self):
        # PyYAML reads a bare `on` key as the boolean True.
        assert list(_workflow()[True]) == ["workflow_dispatch"]

    def test_it_asks_for_no_more_than_it_needs(self):
        assert _workflow()["permissions"] == {"contents": "read", "id-token": "write"}

    def test_it_runs_as_the_identity_the_paid_runs_use(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        batch_run = (REPOSITORY_ROOT / ".github/workflows/batch-run.yml").read_text(
            encoding="utf-8"
        )
        login = "azure/login@f5d393ae46f8fde4be8b75f32e3fc50e654ad0ca"
        assert login in text
        assert login in batch_run, "the pinned login action moved; re-pin this one"
        for name in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"):
            assert f"secrets.{name}" in text

    def test_every_action_it_uses_is_pinned_to_a_commit(self):
        for line in WORKFLOW.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("uses:"):
                assert re.search(r"@[0-9a-f]{40}\b", stripped), stripped

    def test_it_carries_no_credential_that_could_spend(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for name in (
            "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
            "HF_TOKEN", "AZURE_CLIENT_SECRET", "FOUNDRY_PROJECT_ENDPOINT",
        ):
            assert name not in text, name

    def test_the_identity_is_checked_before_anything_is_read(self):
        # Surveying whatever identity happens to be signed in would answer a
        # question nobody asked, and could answer it about somebody else's
        # subscription.
        steps = _workflow()["jobs"]["survey"]["steps"]
        names = [step.get("name", "") for step in steps]
        verify = next(i for i, n in enumerate(names) if "OIDC session identity" in n)
        read = next(i for i, n in enumerate(names) if "Survey the subscription" in n)
        assert verify < read
        env = steps[verify]["env"]
        for name in (
            "AZURE_AI_EXPECTED_CLIENT_ID",
            "AZURE_AI_EXPECTED_TENANT_ID",
            "AZURE_AI_EXPECTED_SUBSCRIPTION_ID",
        ):
            assert name in env

    def test_the_step_that_prints_the_report_names_no_repository_variable(self):
        """A variable is not a secret, and this job's logs are public.

        GitHub reprints whatever a step lists under `env:` in the step header,
        and it masks secrets there but not variables. The Foundry account and
        project names are stored as variables, so naming one here would publish
        it in the header of a job whose whole point is to report without naming
        the resource. This survey does not need them -- it asks about the
        subscription, not the account.
        """
        steps = _workflow()["jobs"]["survey"]["steps"]
        printing = next(
            step for step in steps
            if "scripts/azure_boot_host_survey.py" in (step.get("run") or "")
        )
        assert "vars." not in json.dumps(printing.get("env") or {})

    def test_the_survey_is_not_allowed_to_fail_the_job_for_reporting_a_block(self):
        # A red job invites somebody to make it green, and the only way to make
        # this one green would be to grant something. Reporting a block is the
        # result, not an error.
        steps = _workflow()["jobs"]["survey"]["steps"]
        invocation = next(
            step["run"] for step in steps
            if "scripts/azure_boot_host_survey.py" in (step.get("run") or "")
        )
        # The command line, not the whole block: the comment above it says the
        # word "--require" on purpose, and matching that would pass forever.
        command = next(
            line for line in invocation.splitlines()
            if "scripts/azure_boot_host_survey.py" in line
        )
        assert "--require" not in command

    def test_a_final_step_greps_for_writes_and_model_calls(self):
        steps = _workflow()["jobs"]["survey"]["steps"]
        last = steps[-1]
        assert last.get("if") == "always()"
        assert "vm create" in last["run"] and "responses" in last["run"]
