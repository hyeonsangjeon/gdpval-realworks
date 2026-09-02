"""What the RBAC diagnostic may say, and what it must never say.

The second half matters more than the first. This job runs against a public
repository, so a report that carries a subscription id or a project name cannot
be unpublished. The tests below therefore check the redaction from both
directions: that a real identifier never survives, and that the guard which
enforces that does not fire on a report which never contained one.
"""

import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER.parent
SCRIPT = BATCH_RUNNER / "scripts" / "azure_rbac_diagnostic.py"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "azure-rbac-diagnostic.yml"

SPEC = importlib.util.spec_from_file_location("azure_rbac_diagnostic", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
diagnostic = importlib.util.module_from_spec(SPEC)
sys.modules["azure_rbac_diagnostic"] = diagnostic
SPEC.loader.exec_module(diagnostic)


# Deliberately distinctive stand-ins. Every one is long enough to be redacted
# and unusual enough that finding it in an output is unambiguous.
SUBSCRIPTION = "11111111-2222-3333-4444-555555555555"
TENANT = "66666666-7777-8888-9999-000000000000"
PRINCIPAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ACCOUNT = "distinctiveaccountname"
PROJECT = "distinctiveprojectname"
RESOURCE_GROUP = "distinctiveresourcegroup"
ENDPOINT = f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}"

PROJECT_SCOPE = (
    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{RESOURCE_GROUP}"
    f"/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT}"
    f"/projects/{PROJECT}"
)
ACCOUNT_SCOPE = PROJECT_SCOPE.rsplit("/projects/", 1)[0]

AGENT_CONSUMER = "eed3b665-ab3a-47b6-8f48-c9382fb1dad6"
FOUNDRY_USER = "53ca6127-db72-4b80-b1b0-d745d6d5456d"


def _env(**updates: str) -> dict[str, str]:
    env = {
        "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION,
        "AZURE_TENANT_ID": TENANT,
        "AZURE_CLIENT_ID": PRINCIPAL,
        "FOUNDRY_PROJECT_ENDPOINT": ENDPOINT,
    }
    env.update(updates)
    return env


def _assignment(*, role: str, definition_id: str, scope: str) -> dict[str, object]:
    return {
        "roleDefinitionName": role,
        "roleDefinitionId": (
            f"/subscriptions/{SUBSCRIPTION}/providers/Microsoft.Authorization"
            f"/roleDefinitions/{definition_id}"
        ),
        "scope": scope,
        "principalId": PRINCIPAL,
    }


class FakeAz:
    """Stands in for the az CLI. Records what was asked, answers from a script."""

    def __init__(
        self,
        *,
        resources: object = None,
        assignments: object = None,
        definitions: object = None,
    ) -> None:
        self.resources = resources
        self.assignments = assignments
        self.definitions = definitions
        self.calls: list[list[str]] = []

    def __call__(self, arguments):
        recorded = list(arguments)
        self.calls.append(recorded)
        head = " ".join(recorded[:3])
        if head.startswith("resource list"):
            return self._answer(self.resources, "the Foundry account")
        if head.startswith("role assignment"):
            return self._answer(self.assignments, "role assignment list")
        if head.startswith("role definition"):
            return self._answer(self.definitions, "role definition list")
        raise AssertionError(f"unexpected az call: {recorded}")

    @staticmethod
    def _answer(value, what):
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise diagnostic.AzureReadFailure(what, exit_code=1)
        return value


def _resources() -> list[dict[str, str]]:
    return [{"id": ACCOUNT_SCOPE, "resourceGroup": RESOURCE_GROUP, "name": ACCOUNT}]


def _owner_definition() -> dict[str, object]:
    return {
        "roleName": "Owner",
        "permissions": [{"actions": ["*"], "notActions": [], "dataActions": []}],
    }


def _reader_definition() -> dict[str, object]:
    return {
        "roleName": "Reader",
        "permissions": [{"actions": ["*/read"], "notActions": []}],
    }


# ── Scope shapes say the kind, never the name ─────────────────────────────


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (PROJECT_SCOPE, "foundry-project"),
        (ACCOUNT_SCOPE, "foundry-account"),
        (f"{PROJECT_SCOPE}/", "foundry-project"),
        (f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{RESOURCE_GROUP}", "resource-group"),
        (f"/subscriptions/{SUBSCRIPTION}", "subscription"),
        ("/", "tenant-root"),
        (
            "/providers/Microsoft.Management/managementGroups/anything",
            "management-group",
        ),
        (
            f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{RESOURCE_GROUP}"
            "/providers/Microsoft.Storage/storageAccounts/somewhere",
            "other-resource",
        ),
    ],
)
def test_a_scope_is_reported_as_a_kind_of_place(scope, expected):
    assert diagnostic.scope_shape(scope) == expected


@pytest.mark.parametrize("scope", ["", "   ", None, 7])
def test_a_scope_that_cannot_be_read_says_so_rather_than_guessing(scope):
    assert diagnostic.scope_shape(scope) == "unreadable"


def test_a_scope_shape_nobody_anticipated_is_not_filed_under_a_known_one():
    """Fail closed on shape too. An unknown scope is not quietly a subscription."""
    assert diagnostic.scope_shape("/subscriptions/a/b/c/d/e") == "unrecognised"


def test_the_shape_never_carries_the_name_it_was_derived_from():
    for scope in (PROJECT_SCOPE, ACCOUNT_SCOPE, f"/subscriptions/{SUBSCRIPTION}"):
        shape = diagnostic.scope_shape(scope)
        for secret in (SUBSCRIPTION, ACCOUNT, PROJECT, RESOURCE_GROUP):
            assert secret not in shape


# ── Building the scope the role has to be assigned at ─────────────────────


def test_the_project_scope_is_the_shape_the_documentation_gives():
    built = diagnostic.project_scope(
        subscription_id=SUBSCRIPTION,
        resource_group=RESOURCE_GROUP,
        account=ACCOUNT,
        project=PROJECT,
    )
    assert built == PROJECT_SCOPE
    assert diagnostic.scope_shape(built) == "foundry-project"


@pytest.mark.parametrize(
    "overrides",
    [
        {"subscription_id": ""},
        {"resource_group": "   "},
        {"account": ""},
        {"project": ""},
        {"account": "with/separator"},
        {"project": "../escape"},
    ],
)
def test_a_scope_cannot_be_built_from_a_missing_or_smuggled_part(overrides):
    arguments = {
        "subscription_id": SUBSCRIPTION,
        "resource_group": RESOURCE_GROUP,
        "account": ACCOUNT,
        "project": PROJECT,
    }
    arguments.update(overrides)
    with pytest.raises(ValueError):
        diagnostic.project_scope(**arguments)


def test_the_resource_group_is_read_out_of_an_arm_id_and_absence_is_none():
    assert diagnostic.resource_group_of(PROJECT_SCOPE) == RESOURCE_GROUP
    assert diagnostic.resource_group_of(f"/subscriptions/{SUBSCRIPTION}") is None
    assert diagnostic.resource_group_of(None) is None


# ── Inheritance ───────────────────────────────────────────────────────────


def test_a_role_higher_up_reaches_the_project_below_it():
    for scope in (
        PROJECT_SCOPE,
        ACCOUNT_SCOPE,
        f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{RESOURCE_GROUP}",
        f"/subscriptions/{SUBSCRIPTION}",
        "/",
    ):
        assert diagnostic._covers(scope, PROJECT_SCOPE), scope


def test_a_role_on_a_sibling_resource_does_not_reach_the_project():
    sibling = ACCOUNT_SCOPE.replace(ACCOUNT, f"{ACCOUNT}-other")
    assert not diagnostic._covers(sibling, PROJECT_SCOPE)


def test_an_account_whose_name_is_a_prefix_is_not_mistaken_for_this_one():
    """The bug this test exists for: a plain startswith on the raw string.

    An account called ``name`` and one called ``nameother`` share a prefix, and
    a naive comparison would report a role on the second as reaching the first.
    """
    shorter = ACCOUNT_SCOPE.replace(ACCOUNT, ACCOUNT[:-3])
    assert not diagnostic._covers(shorter, PROJECT_SCOPE)


def test_a_scope_that_is_absent_reaches_nothing():
    assert not diagnostic._covers("", PROJECT_SCOPE)
    assert not diagnostic._covers(None, PROJECT_SCOPE)


# ── Whether the identity could fix this itself ────────────────────────────


def test_a_role_with_the_write_action_can_assign():
    assert diagnostic.permits_role_assignment([_owner_definition()])
    assert diagnostic.permits_role_assignment(
        [{"permissions": [{"actions": ["Microsoft.Authorization/*"]}]}]
    )
    assert diagnostic.permits_role_assignment(
        [{"permissions": [{"actions": [diagnostic.ROLE_ASSIGNMENT_WRITE]}]}]
    )


def test_a_read_only_role_cannot_assign():
    assert not diagnostic.permits_role_assignment([_reader_definition()])
    assert not diagnostic.permits_role_assignment([])
    assert not diagnostic.permits_role_assignment([{"permissions": []}])


def test_a_denied_action_takes_the_grant_back():
    """The Contributor shape. Everything, except the one thing that matters."""
    contributor = {
        "permissions": [
            {
                "actions": ["*"],
                "notActions": [
                    "Microsoft.Authorization/*/Delete",
                    "Microsoft.Authorization/*/Write",
                ],
            }
        ]
    }
    assert not diagnostic.permits_role_assignment([contributor])


def test_the_denial_only_applies_inside_its_own_permission_block():
    definitions = [
        {"permissions": [{"actions": ["*"], "notActions": ["Microsoft.Authorization/*/Write"]}]},
        {"permissions": [{"actions": [diagnostic.ROLE_ASSIGNMENT_WRITE]}]},
    ]
    assert diagnostic.permits_role_assignment(definitions)


def test_a_malformed_definition_is_skipped_rather_than_crashing():
    assert not diagnostic.permits_role_assignment(["not a mapping", None, 7])


# ── Reading the assignments ───────────────────────────────────────────────


def test_the_role_definition_guid_is_taken_off_the_end_of_its_path():
    held = diagnostic.summarize_assignments(
        [_assignment(role="Foundry User", definition_id=FOUNDRY_USER, scope=PROJECT_SCOPE)],
        target_scope=PROJECT_SCOPE,
    )
    assert [role.definition_id for role in held] == [FOUNDRY_USER]
    assert held[0].covers_the_project is True


def test_the_same_role_twice_is_recorded_once():
    duplicate = _assignment(
        role="Foundry User", definition_id=FOUNDRY_USER, scope=PROJECT_SCOPE
    )
    held = diagnostic.summarize_assignments(
        [duplicate, dict(duplicate)], target_scope=PROJECT_SCOPE
    )
    assert len(held) == 1


def test_an_assignment_with_no_readable_name_is_kept_and_labelled():
    held = diagnostic.summarize_assignments(
        [{"scope": PROJECT_SCOPE, "roleDefinitionId": 7}], target_scope=PROJECT_SCOPE
    )
    assert held[0].role_name == "unnamed"
    assert held[0].definition_id == ""


def test_the_ladder_is_satisfied_only_by_a_role_that_reaches_the_project():
    on_the_project = diagnostic.summarize_assignments(
        [
            _assignment(
                role="Foundry Agent Consumer",
                definition_id=AGENT_CONSUMER,
                scope=PROJECT_SCOPE,
            )
        ],
        target_scope=PROJECT_SCOPE,
    )
    assert [rung.name for rung in diagnostic.missing_rungs(on_the_project)] == [
        "Foundry User"
    ]

    elsewhere = diagnostic.summarize_assignments(
        [
            _assignment(
                role="Foundry Agent Consumer",
                definition_id=AGENT_CONSUMER,
                scope=f"/subscriptions/{SUBSCRIPTION}/resourceGroups/elsewhere",
            )
        ],
        target_scope=PROJECT_SCOPE,
    )
    assert len(diagnostic.missing_rungs(elsewhere)) == 2


def test_the_roles_the_documentation_rules_out_are_named_when_held():
    held = diagnostic.summarize_assignments(
        [
            _assignment(
                role="Cognitive Services Contributor",
                definition_id="25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68",
                scope=ACCOUNT_SCOPE,
            ),
            _assignment(
                role="Cognitive Services OpenAI User",
                definition_id="00000000-0000-0000-0000-000000000000",
                scope=ACCOUNT_SCOPE,
            ),
        ],
        target_scope=PROJECT_SCOPE,
    )
    flagged = diagnostic.forbidden_roles_held(held)
    assert len(flagged) == 2
    assert any("no data actions" in entry for entry in flagged)


def test_a_correct_role_is_not_flagged_as_the_wrong_instrument():
    """The negative control for the check above."""
    held = diagnostic.summarize_assignments(
        [
            _assignment(
                role="Foundry Agent Consumer",
                definition_id=AGENT_CONSUMER,
                scope=PROJECT_SCOPE,
            )
        ],
        target_scope=PROJECT_SCOPE,
    )
    assert diagnostic.forbidden_roles_held(held) == ()


# ── Redaction ─────────────────────────────────────────────────────────────


def test_every_configured_identifier_is_replaced_by_its_placeholder():
    secrets = diagnostic.collect_secrets(_env())
    text = f"{SUBSCRIPTION} {TENANT} {PRINCIPAL} {ENDPOINT}"
    cleaned = diagnostic.redact(text, secrets)
    for value in (SUBSCRIPTION, TENANT, PRINCIPAL, ENDPOINT):
        assert value not in cleaned
    assert "<subscriptionId>" in cleaned
    assert "<projectEndpoint>" in cleaned


def test_redaction_is_case_insensitive_because_arm_ids_are():
    secrets = diagnostic.collect_secrets(_env())
    cleaned = diagnostic.redact(SUBSCRIPTION.upper(), secrets)
    assert SUBSCRIPTION.upper() not in cleaned


def test_a_value_too_short_to_defend_is_left_alone_rather_than_corrupting_the_text():
    secrets = diagnostic.collect_secrets(_env(AZURE_CLIENT_ID="dev"))
    assert "dev" not in secrets
    assert diagnostic.redact("a development note", secrets) == "a development note"


def test_the_leak_check_finds_what_redaction_missed():
    secrets = diagnostic.collect_secrets(_env())
    assert diagnostic.leaked_placeholders(f"see {SUBSCRIPTION}", secrets) == (
        "<subscriptionId>",
    )


def test_the_leak_check_does_not_fire_on_a_report_that_never_had_one():
    """Negative control. A guard that always fires protects nothing."""
    secrets = diagnostic.collect_secrets(_env())
    clean = diagnostic.render(
        {
            "route_profile": "project-ci",
            "endpoint_kind": "project",
            "target_scope_shape": "foundry-project",
            "verdict": "role_missing_and_an_owner_must_grant_it",
            "roles_held": [],
            "missing_least_privilege_roles": [
                {"name": "Foundry Agent Consumer", "role_definition_id": AGENT_CONSUMER}
            ],
            "principal_can_assign_roles": False,
        }
    )
    assert diagnostic.leaked_placeholders(clean, secrets) == ()


# ── The diagnosis end to end ──────────────────────────────────────────────


def test_a_project_with_the_consumer_role_is_reported_as_already_covered():
    az = FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(
                role="Foundry Agent Consumer",
                definition_id=AGENT_CONSUMER,
                scope=PROJECT_SCOPE,
            ),
            _assignment(
                role="Foundry User", definition_id=FOUNDRY_USER, scope=PROJECT_SCOPE
            ),
        ],
        definitions=[_reader_definition()],
    )
    report = diagnostic.diagnose(_env(), runner=az)
    assert report["verdict"] == "least_privilege_role_already_held"
    assert report["missing_least_privilege_roles"] == []
    assert report["principal_can_assign_roles"] is False


def test_the_403_shape_is_reported_as_a_missing_role_an_owner_must_grant():
    """The situation the two failed dispatches were actually in."""
    az = FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(
                role="Cognitive Services Contributor",
                definition_id="25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68",
                scope=ACCOUNT_SCOPE,
            )
        ],
        definitions=[_reader_definition()],
    )
    report = diagnostic.diagnose(_env(), runner=az)
    assert report["verdict"] == "role_missing_and_an_owner_must_grant_it"
    assert [rung["name"] for rung in report["missing_least_privilege_roles"]] == [
        "Foundry Agent Consumer",
        "Foundry User",
    ]
    assert report["forbidden_roles_held"]


def test_an_identity_that_can_assign_is_told_so_rather_than_sent_to_an_owner():
    az = FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(
                role="Owner",
                definition_id="8e3af657-a8ff-443c-a75c-2fe8c4bcb635",
                scope=f"/subscriptions/{SUBSCRIPTION}",
            )
        ],
        definitions=[_owner_definition()],
    )
    report = diagnostic.diagnose(_env(), runner=az)
    assert report["verdict"] == "role_missing_and_this_identity_can_grant_it"
    assert report["principal_can_assign_roles"] is True


def test_a_control_plane_that_answers_without_the_account_is_a_finding():
    az = FakeAz(resources=[], assignments=[], definitions=[])
    report = diagnostic.diagnose(_env(), runner=az)
    assert report["verdict"] == "cannot_read_control_plane"
    assert report["read_failures"]
    # It stopped there rather than reporting "no roles held", which would read
    # as a measured zero.
    assert report["roles_held"] == []
    assert len(az.calls) == 1
    # az answered, and the account was not in the answer. That is a real fact
    # about what this identity can see, so the stronger sentence is earned.
    assert "no reader" in " ".join(report["read_failures"])


def test_a_lookup_az_never_completed_is_not_reported_as_a_missing_reader():
    """The failure a login taken outside CI actually produces.

    ``az resource list --subscription <one this session is not signed into>``
    exits non-zero without querying anything; it does not come back with an
    empty list. Both used to land on the same verdict and the same sentence,
    and that sentence -- "this identity has no reader on the account" -- is an
    inference about a resource nobody asked Azure about. It sends the next
    reader hunting a role to grant in a directory that never held the project.
    """
    az = FakeAz(resources=None, assignments=[], definitions=[])
    report = diagnostic.diagnose(_env(), runner=az)
    assert report["verdict"] == "control_plane_read_never_completed"
    assert report["read_failures"]
    assert report["roles_held"] == []
    assert len(az.calls) == 1
    assert "no reader" not in " ".join(report["read_failures"])


def test_the_two_control_plane_failures_do_not_read_the_same_way():
    answered = diagnostic.render(
        diagnostic.diagnose(
            _env(), runner=FakeAz(resources=[], assignments=[], definitions=[])
        )
    )
    unanswered = diagnostic.render(
        diagnostic.diagnose(
            _env(), runner=FakeAz(resources=None, assignments=[], definitions=[])
        )
    )
    assert answered != unanswered
    assert "no reader" in answered
    assert "no reader" not in unanswered
    assert "nothing was measured" in unanswered.lower()


def test_a_lookup_that_never_completed_still_fails_the_project_role_gate():
    """A new verdict must not open the gate by not being on a deny list.

    The gate names the one verdict that passes rather than the ones that fail,
    so an unmeasured run stays closed without anything here being updated.
    """
    code, text = _run_main(
        ["--require-project-role"],
        FakeAz(resources=None, assignments=[], definitions=[]),
    )
    assert code == 1
    assert "control_plane_read_never_completed" in text


def test_every_verdict_the_diagnosis_can_reach_has_a_sentence_written_for_it():
    # Without this, a verdict added later renders under the fallback line and
    # reads as though nothing was measured, whatever it actually found.
    source = SCRIPT.read_text(encoding="utf-8")
    reachable = set(re.findall(r'report\["verdict"\] = "([a-z_]+)"', source))
    assert reachable, "the verdict assignments moved; this check went vacuous"
    assert reachable <= set(diagnostic._VERDICT_LINES)


def test_being_unable_to_read_its_own_assignments_is_not_reported_as_none_held():
    az = FakeAz(resources=_resources(), assignments=None, definitions=[])
    report = diagnostic.diagnose(_env(), runner=az)
    assert report["verdict"] == "cannot_read_role_assignments"
    assert report["roles_held"] == []


def test_an_unreadable_role_definition_leaves_the_grantor_unmeasured_not_false():
    az = FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(
                role="Reader",
                definition_id="acdd72a7-3385-48ef-bd42-f606fba81ae7",
                scope=PROJECT_SCOPE,
            )
        ],
        definitions=None,
    )
    report = diagnostic.diagnose(_env(), runner=az)
    assert report["principal_can_assign_roles"] is None
    assert report["verdict"] == "role_missing_and_the_grantor_is_unmeasured"


def test_the_assignment_read_asks_for_inherited_and_group_roles():
    az = FakeAz(resources=_resources(), assignments=[], definitions=[])
    diagnostic.diagnose(_env(), runner=az)
    assignment_call = next(
        call for call in az.calls if call[:2] == ["role", "assignment"]
    )
    assert "--include-inherited" in assignment_call
    assert "--include-groups" in assignment_call
    assert "--scope" in assignment_call


def test_nothing_the_diagnostic_runs_changes_anything():
    """The whole safety claim, checked against what was actually asked for."""
    az = FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(role="Reader", definition_id="acdd72a7", scope=PROJECT_SCOPE)
        ],
        definitions=[_reader_definition()],
    )
    diagnostic.diagnose(_env(), runner=az)
    assert az.calls
    for call in az.calls:
        assert call[1] in {"list"} or call[2] == "list", call
        for verb in ("create", "update", "delete", "set", "add", "remove"):
            assert verb not in call


def test_an_endpoint_that_is_not_a_project_is_refused():
    direct = f"https://{ACCOUNT}.services.ai.azure.com/openai/v1/"
    with pytest.raises(ValueError, match="not a Foundry project endpoint"):
        diagnostic.diagnose(
            _env(FOUNDRY_PROJECT_ENDPOINT=direct), runner=FakeAz(resources=_resources())
        )


@pytest.mark.parametrize(
    "missing", ["FOUNDRY_PROJECT_ENDPOINT", "AZURE_SUBSCRIPTION_ID", "AZURE_CLIENT_ID"]
)
def test_a_missing_setting_stops_the_run_instead_of_being_read_as_empty(missing):
    with pytest.raises(ValueError, match=missing):
        diagnostic.diagnose(_env(**{missing: ""}), runner=FakeAz())


# ── What actually reaches the log ─────────────────────────────────────────


def _run_main(argv, az, **env_updates):
    stream = io.StringIO()
    code = diagnostic.main(
        argv, env=_env(**env_updates), runner=az, stream=stream
    )
    return code, stream.getvalue()


def _every_secret():
    return (SUBSCRIPTION, TENANT, PRINCIPAL, ACCOUNT, PROJECT, RESOURCE_GROUP, ENDPOINT)


def test_the_printed_report_carries_no_identifier_at_all():
    az = FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(
                role="Cognitive Services Contributor",
                definition_id="25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68",
                scope=ACCOUNT_SCOPE,
            )
        ],
        definitions=[_reader_definition()],
    )
    code, output = _run_main([], az)
    assert code == 0
    for secret in _every_secret():
        assert secret.lower() not in output.lower(), secret
    assert "<projectName>" in output
    assert "role_missing_and_an_owner_must_grant_it" in output


def test_the_resource_group_read_back_from_azure_is_redacted_too():
    """The one identifier no environment variable could have told us about.

    It is discovered mid-run, so it has to be added to the redaction set after
    collect_secrets has already looked at the environment. If that wiring
    breaks, this is what catches it.
    """
    az = FakeAz(resources=_resources(), assignments=[], definitions=[])
    _, output = _run_main([], az)
    assert RESOURCE_GROUP not in output
    assert "<resourceGroup>" in output


def test_the_json_form_is_redacted_by_the_same_path():
    az = FakeAz(resources=_resources(), assignments=[], definitions=[])
    code, output = _run_main(["--json"], az)
    assert code == 0
    payload = json.loads(output)
    assert payload["verdict"] == "role_missing_and_an_owner_must_grant_it"
    assert "secret_values" not in payload
    for secret in _every_secret():
        assert secret.lower() not in output.lower(), secret


def test_the_remediation_command_is_a_template_not_a_filled_in_command():
    az = FakeAz(resources=_resources(), assignments=[], definitions=[])
    _, output = _run_main([], az)
    assert "az role assignment create" in output
    assert f'--role "{diagnostic.LEAST_PRIVILEGE_LADDER[0].definition_id}"' in output
    assert "<subscriptionId>" in output and "<principalId>" in output
    # Only the first rung is offered. Printing both would invite the broader
    # one being assigned first.
    assert f'--role "{FOUNDRY_USER}"' not in output


def _custom_role_named_after_the_project():
    """The one field Azure lets a human write free text into.

    Scopes are reduced to shapes and ids are GUIDs, so neither can carry a
    resource name. A custom role's display name can, and often does, because
    people name custom roles after the thing they apply to.
    """
    return FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(
                role=f"{PROJECT} operator",
                definition_id="12345678-1234-1234-1234-123456789abc",
                scope=PROJECT_SCOPE,
            )
        ],
        definitions=[_reader_definition()],
    )


def test_a_custom_role_named_after_the_project_is_withheld_at_the_source():
    """First layer: the name never enters the report in the first place."""
    code, output = _run_main([], _custom_role_named_after_the_project())
    assert code == 0
    assert PROJECT not in output
    assert diagnostic.WITHHELD_ROLE_NAME in output


def test_a_built_in_role_name_is_not_withheld():
    """Negative control for the layer above. Withholding everything is not safety."""
    az = FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(
                role="Foundry Agent Consumer",
                definition_id=AGENT_CONSUMER,
                scope=PROJECT_SCOPE,
            )
        ],
        definitions=[_reader_definition()],
    )
    _, output = _run_main([], az)
    assert "Foundry Agent Consumer" in output
    assert diagnostic.WITHHELD_ROLE_NAME not in output


def test_redaction_catches_the_name_if_the_source_check_is_broken(monkeypatch):
    """Second layer, checked by disabling the first."""
    monkeypatch.setattr(diagnostic, "safe_role_name", lambda name, values: name)
    code, output = _run_main([], _custom_role_named_after_the_project())
    assert code == 0
    assert PROJECT not in output
    assert "<projectName> operator" in output


def test_the_report_is_withheld_when_both_earlier_layers_are_broken(monkeypatch):
    """Third layer, checked by disabling the two in front of it.

    This is the guard that matters most, so it is verified by taking away
    everything it depends on rather than by trusting that it works. The input
    is the one shape that genuinely carries a name into the raw report, so a
    pass here means the leak check caught a real leak, not a hypothetical one.
    """
    monkeypatch.setattr(diagnostic, "safe_role_name", lambda name, values: name)
    monkeypatch.setattr(diagnostic, "redact", lambda text, secrets: text)
    code, output = _run_main([], _custom_role_named_after_the_project())
    assert code == 3
    assert output == ""


def test_breaking_every_layer_on_a_report_with_nothing_to_leak_still_prints(monkeypatch):
    """Negative control for the check above.

    Without this, the test above would pass just as happily if the leak check
    refused every report it was ever shown.
    """
    monkeypatch.setattr(diagnostic, "safe_role_name", lambda name, values: name)
    monkeypatch.setattr(diagnostic, "redact", lambda text, secrets: text)
    az = FakeAz(resources=_resources(), assignments=[], definitions=[])
    code, output = _run_main([], az)
    assert code == 0
    assert "role_missing_and_an_owner_must_grant_it" in output


def test_a_missing_setting_exits_two_without_printing_a_report():
    code, output = _run_main([], FakeAz(), AZURE_CLIENT_ID="")
    assert code == 2
    assert output == ""


def test_the_gate_flag_is_the_only_thing_that_turns_a_gap_into_a_failure():
    az = FakeAz(resources=_resources(), assignments=[], definitions=[])
    assert _run_main([], az)[0] == 0
    assert _run_main(["--require-project-role"], az)[0] == 1

    covered = FakeAz(
        resources=_resources(),
        assignments=[
            _assignment(
                role="Foundry Agent Consumer",
                definition_id=AGENT_CONSUMER,
                scope=PROJECT_SCOPE,
            ),
            _assignment(
                role="Foundry User", definition_id=FOUNDRY_USER, scope=PROJECT_SCOPE
            ),
        ],
        definitions=[_reader_definition()],
    )
    assert _run_main(["--require-project-role"], covered)[0] == 0


# ── The role facts this rests on ──────────────────────────────────────────


def test_the_ladder_is_least_privilege_first_and_pinned_to_the_documented_ids():
    ladder = diagnostic.LEAST_PRIVILEGE_LADDER
    assert [rung.name for rung in ladder] == ["Foundry Agent Consumer", "Foundry User"]
    assert [rung.definition_id for rung in ladder] == [AGENT_CONSUMER, FOUNDRY_USER]
    for rung in ladder:
        assert re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", rung.definition_id)
        assert rung.why


def test_the_roles_the_documentation_rules_out_stay_ruled_out():
    assert "25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68" in diagnostic.FORBIDDEN_ROLE_IDS
    assert "64702f94-c441-49e6-a78b-ef80e0188fee" in diagnostic.FORBIDDEN_ROLE_IDS
    for rung in diagnostic.LEAST_PRIVILEGE_LADDER:
        assert rung.definition_id not in diagnostic.FORBIDDEN_ROLE_IDS
        assert not rung.name.startswith(diagnostic.FORBIDDEN_ROLE_NAME_PREFIX)


# ── The workflow that runs it ─────────────────────────────────────────────


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_workflow_can_only_be_started_by_hand():
    # PyYAML reads a bare `on` key as the boolean True.
    triggers = _workflow()[True]
    assert list(triggers) == ["workflow_dispatch"]


def test_the_workflow_asks_for_no_more_than_it_needs():
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}


def test_the_workflow_runs_as_the_identity_the_paid_runs_use():
    text = WORKFLOW.read_text(encoding="utf-8")
    batch_run = (REPOSITORY_ROOT / ".github/workflows/batch-run.yml").read_text(
        encoding="utf-8"
    )
    login = "azure/login@f5d393ae46f8fde4be8b75f32e3fc50e654ad0ca"
    assert login in text
    assert login in batch_run, "the pinned login action moved; re-pin this one"
    for name in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"):
        assert f"secrets.{name}" in text


def test_every_action_the_workflow_uses_is_pinned_to_a_commit():
    for line in WORKFLOW.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("uses:"):
            assert re.search(r"@[0-9a-f]{40}\b", stripped), stripped


def test_the_workflow_carries_no_credential_that_could_spend():
    text = WORKFLOW.read_text(encoding="utf-8")
    for name in (
        "AZURE_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "HF_TOKEN",
        "AZURE_CLIENT_SECRET",
    ):
        assert name not in text, name


def test_the_workflow_demands_the_expected_identities_like_every_other_run_place():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES: '1'" in text


def test_the_step_that_prints_the_report_names_no_repository_variable():
    """A variable is not a secret, and this job's logs are public.

    GitHub reprints whatever a step lists under `env:` in the step header, and
    it masks secrets there but not variables. The Foundry account and project
    names are stored as variables, so asking for them by name in this step
    would publish them in the header of the one job whose entire purpose is to
    report without naming the resource. Measured on run 33510351756, which is
    what this test exists to stop happening again.
    """
    steps = _workflow()["jobs"]["diagnose"]["steps"]
    invocation = "python3 scripts/azure_rbac_diagnostic.py"
    reporting = [step for step in steps if invocation in step.get("run", "")]
    assert len(reporting) == 1, "the reporting step moved or was duplicated"
    for key, value in reporting[0].get("env", {}).items():
        assert "vars." not in str(value), f"{key} publishes a repository variable"


def test_the_report_still_hides_both_names_without_those_variables():
    """The check above only holds if the names are recoverable elsewhere.

    They are: both live inside the project endpoint, which is a secret, and the
    script pulls them out of it. Without this, dropping the variables would
    look like a tightening while quietly removing a redaction source.
    """
    environment = _env()
    for name in (
        "AZURE_AI_EXPECTED_PROJECT_ACCOUNT",
        "AZURE_AI_EXPECTED_PROJECT_NAME",
    ):
        assert name not in environment, "this test is measuring the wrong thing"
    _, output = _run_main([], _custom_role_named_after_the_project())
    assert ACCOUNT not in output
    assert PROJECT not in output


def test_the_diagnostic_never_reaches_for_the_inference_path():
    """Kept in step with the workflow's own last step, which greps for this."""
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "responses.create",
        "chat.completions",
        "AzureOpenAI",
        "llm_client",
        "code_interpreter",
    ):
        assert forbidden not in source, forbidden
