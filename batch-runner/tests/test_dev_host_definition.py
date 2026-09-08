"""The development host's definition, held to the card that allowed it.

Two things are tested here and they are not the same thing.

The first is the *reader*. `scripts/check_dev_host_definition.py` parses Bicep,
and a parser that quietly sees nothing reports that nothing is wrong -- which is
the worst possible failure for a security check. So the reader is fed templates
that were deliberately broken in each of the ways that matter, and it is
required to notice. A check that cannot fail is not a check, and the way to
demonstrate that these can fail is to break the thing and watch them.

The second is the *definition*. `infra/dev-host/main.bicep` is run through the
reader as it actually stands in the repository, and every check must pass. That
is the one that fails on a future edit, and the reason each check carries a
`promise` string naming the card clause it comes from: the failure should say
which promise was withdrawn, not merely that a boolean went false.

What none of this can tell you: what is deployed in Azure. A template saying
`disablePasswordAuthentication: true` and a machine with password
authentication off are different facts, and only the first is readable from
here. `deploy.sh status` reads the other one.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_dev_host_definition as checker  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA = REPO_ROOT / "infra" / "dev-host"
TEMPLATE = INFRA / "main.bicep"
DEPLOY = INFRA / "deploy.sh"
BOOTSTRAP = INFRA / "bootstrap.sh"
README = INFRA / "README.md"


# ── The files exist and are what they claim to be ──────────────────────────


def test_the_definition_is_in_the_repository():
    """구현 방식 1: a declarative infrastructure definition lives in the repo.

    Not a wiki page, not a shell transcript -- a file that a pull request can
    disagree with.
    """
    assert TEMPLATE.is_file()
    assert DEPLOY.is_file()
    assert BOOTSTRAP.is_file()
    assert README.is_file()


# ── The README describes these files rather than some other ones ───────────


@pytest.mark.parametrize(
    "variable",
    [
        "GDPVAL_DEV_HOST_SUBSCRIPTION",
        "GDPVAL_DEV_HOST_SSH_PUBLIC_KEY",
        "GDPVAL_DEV_HOST_CONFIRM_DELETE",
    ],
)
def test_the_readme_names_variables_that_exist(variable):
    """A README naming an environment variable the script does not read sends
    somebody to type a command that silently does something else."""
    assert variable in README.read_text(encoding="utf-8")
    assert variable in DEPLOY.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "subcommand",
    ["plan", "deploy", "bootstrap", "status", "deallocate", "start", "delete"],
)
def test_the_readme_names_subcommands_that_exist(subcommand):
    assert f"./deploy.sh {subcommand}" in README.read_text(encoding="utf-8")
    assert re.search(rf"^\s*{subcommand}\)", DEPLOY.read_text(encoding="utf-8"), re.M), (
        f"deploy.sh has no {subcommand} case"
    )


def test_the_readme_does_not_promise_the_shortcut_is_taken():
    """The one paragraph most likely to be softened later. Ubuntu 24.04 is the
    card's image and is also the image that cannot sandbox without a security
    change; the README has to say the change was not made."""
    text = README.read_text(encoding="utf-8")
    assert "reads that sysctl and does not write it" in text
    assert "belongs to" in text and "person" in text


def test_the_scripts_are_executable():
    assert DEPLOY.stat().st_mode & 0o111, "deploy.sh is not executable"
    assert BOOTSTRAP.stat().st_mode & 0o111, "bootstrap.sh is not executable"


def test_the_executable_bit_is_the_one_a_clone_gets():
    """The filesystem is not the fact that travels.

    ``core.fileMode=false`` is set on at least one machine this repository is
    developed on, and under it git records 100644 for a file that is `+x` on
    disk. The assertion above then passes locally for a reason a fresh clone
    does not inherit, and the first machine to notice is CI -- which is how
    this test came to exist rather than a hypothetical it guards against.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-s", "--", "infra/dev-host"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    modes = {
        line.split("\t", 1)[1]: line.split(" ", 1)[0]
        for line in listing.splitlines() if line
    }
    for path in ("infra/dev-host/deploy.sh", "infra/dev-host/bootstrap.sh"):
        assert modes.get(path) == "100755", (
            f"git has {path} at mode {modes.get(path)}; a clone would get a file "
            "it cannot run. `git update-index --chmod=+x` records the bit."
        )


def test_the_shell_scripts_parse():
    """A script that does not parse fails at the worst moment: half way in."""
    for script in (DEPLOY, BOOTSTRAP):
        result = subprocess.run(
            ["bash", "-n", str(script)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"{script.name}: {result.stderr}"


def test_one_definition_covers_the_whole_card_list():
    """구현 방식 2: VM, network, NSG, disk, managed identity and auto-shutdown,
    reproduced in one go rather than assembled by hand each time."""
    template = checker.parse(TEMPLATE)
    for required in (
        "Microsoft.Compute/virtualMachines",
        "Microsoft.Network/virtualNetworks",
        "Microsoft.Network/networkSecurityGroups",
        "Microsoft.Network/networkInterfaces",
        "Microsoft.Compute/disks",
        "Microsoft.DevTestLab/schedules",
    ):
        assert template.by_type(required), f"the definition has no {required}"


# ── The definition as it stands ────────────────────────────────────────────


@pytest.fixture(scope="module")
def report() -> checker.Report:
    return checker.check(REPO_ROOT)


def test_every_check_passes_on_the_definition_in_the_repository(report):
    failures = [f"{c.check_id}: {c.evidence} ({c.promise})" for c in report.failed]
    assert not failures, "the definition no longer matches the card:\n" + "\n".join(failures)


def test_the_report_says_what_it_is_and_is_not_about(report):
    """The distinction that makes this honest, carried in the artifact itself."""
    payload = report.as_dict()
    caveat = payload["reads_the_definition_not_the_deployment"]
    # It has to name the other thing, not just disclaim itself -- a reader who
    # is told this report does not describe the running machine is owed the
    # command that does.
    assert "infra/dev-host/" in caveat
    assert "not readable from here" in caveat
    assert "deploy.sh status" in caveat
    assert payload["verdict"] == "ok"
    assert payload["checked"] == len(payload["checks"])


def test_each_check_names_the_promise_it_is_keeping(report):
    for check in report.checks:
        assert check.promise.strip(), f"{check.check_id} has no promise"
        assert check.evidence.strip(), f"{check.check_id} has no evidence"


@pytest.mark.parametrize(
    "check_id",
    [
        "region_default_is_koreacentral",
        "image_is_ubuntu_24_04_lts",
        "size_is_eight_vcpu_thirty_two_gib",
        "password_authentication_is_off",
        "no_password_is_carried_at_all",
        "ssh_key_is_required_and_has_no_default",
        "ssh_source_defaults_to_none",
        "public_address_is_off_by_default",
        "no_inbound_allow_rule_names_a_wildcard_source",
        "a_wildcard_is_refused_at_deployment_time_too",
        "identity_is_system_assigned",
        "the_identity_is_granted_nothing",
        "no_credential_shaped_parameter_carries_a_default",
        "nothing_is_baked_into_the_machine_at_first_boot",
        "it_shuts_itself_down",
        "no_existing_resource_is_adopted",
        "deploy_will_not_pick_a_subscription_for_you",
        "deploy_refuses_the_subscription_the_foundry_checks_expect",
        "teardown_is_a_command_not_a_paragraph",
        "bootstrap_reads_the_namespace_restriction_and_does_not_clear_it",
        "bootstrap_marks_the_machine_as_not_a_benchmark_environment",
        "bootstrap_clones_rather_than_copying_the_users_checkout",
    ],
)
def test_the_check_is_present(report, check_id):
    """Naming them one by one, so deleting a check fails a test rather than
    silently shrinking the contract."""
    assert check_id in {c.check_id for c in report.checks}


# ── The reader can fail: each check, broken on purpose ─────────────────────


def _fake_repo(tmp_path: Path, *, template: str | None = None,
               deploy: str | None = None, bootstrap: str | None = None) -> Path:
    root = tmp_path / "repo"
    (root / "infra" / "dev-host").mkdir(parents=True, exist_ok=True)
    (root / "infra/dev-host/main.bicep").write_text(
        TEMPLATE.read_text(encoding="utf-8") if template is None else template,
        encoding="utf-8",
    )
    (root / "infra/dev-host/deploy.sh").write_text(
        DEPLOY.read_text(encoding="utf-8") if deploy is None else deploy,
        encoding="utf-8",
    )
    (root / "infra/dev-host/bootstrap.sh").write_text(
        BOOTSTRAP.read_text(encoding="utf-8") if bootstrap is None else bootstrap,
        encoding="utf-8",
    )
    return root


def _failed_ids(root: Path) -> set[str]:
    return {c.check_id for c in checker.check(root).failed}


def _edited(old: str, new: str) -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert old in text, f"the template no longer contains {old!r}; update this test"
    return text.replace(old, new, 1)


def test_an_unbroken_copy_passes(tmp_path):
    """The control. Without this, every test below could be passing because the
    fixture is broken rather than because the reader works."""
    assert _failed_ids(_fake_repo(tmp_path)) == set()


def test_a_different_region_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "param location string = 'koreacentral'",
        "param location string = 'eastus'",
    ))
    assert "region_default_is_koreacentral" in _failed_ids(root)


def test_swapping_the_image_for_one_that_sandboxes_more_easily_is_caught(tmp_path):
    """Ubuntu 22.04 is the image measured `ready` for Codex's sandbox, and
    24.04 is the one the card fixed. Substituting it silently is exactly the
    move this check exists to make visible."""
    root = _fake_repo(tmp_path, template=_edited(
        "param imageOffer string = 'ubuntu-24_04-lts'",
        "param imageOffer string = 'ubuntu-22_04-lts'",
    ))
    assert "image_is_ubuntu_24_04_lts" in _failed_ids(root)


def test_a_bigger_machine_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "param vmSize string = 'Standard_D8as_v5'",
        "param vmSize string = 'Standard_D32as_v5'",
    ))
    assert "size_is_eight_vcpu_thirty_two_gib" in _failed_ids(root)


def test_an_unrecognised_size_fails_rather_than_being_assumed_to_fit(tmp_path):
    """The failure mode that matters: a size nobody listed is not silently
    treated as 8/32 because its name has an 8 in it."""
    root = _fake_repo(tmp_path, template=_edited(
        "param vmSize string = 'Standard_D8as_v5'",
        "param vmSize string = 'Standard_E8as_v5'",
    ))
    assert "size_is_eight_vcpu_thirty_two_gib" in _failed_ids(root)


def test_turning_password_authentication_on_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "disablePasswordAuthentication: true",
        "disablePasswordAuthentication: false",
    ))
    assert "password_authentication_is_off" in _failed_ids(root)


def test_adding_a_password_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "      adminUsername: adminUsername",
        "      adminUsername: adminUsername\n      adminPassword: 'hunter2'",
    ))
    failed = _failed_ids(root)
    assert "no_password_is_carried_at_all" in failed


def test_giving_the_ssh_key_a_default_is_caught(tmp_path):
    """A default for a key is a key committed to the repository."""
    root = _fake_repo(tmp_path, template=_edited(
        "param adminPublicKey string",
        "param adminPublicKey string = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5 nobody@nowhere'",
    ))
    assert "ssh_key_is_required_and_has_no_default" in _failed_ids(root)


def test_defaulting_the_ssh_source_to_the_internet_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "param sshAllowedSourcePrefixes array = []",
        "param sshAllowedSourcePrefixes array = ['0.0.0.0/0']",
    ))
    failed = _failed_ids(root)
    assert "ssh_source_defaults_to_none" in failed


@pytest.mark.parametrize("wildcard", ["*", "0.0.0.0/0", "Internet", "any", "::/0"])
def test_every_spelling_of_the_internet_is_caught(tmp_path, wildcard):
    """Azure accepts all of these and they mean the same thing. A check for the
    literal '*' alone would pass three of the five."""
    root = _fake_repo(tmp_path, template=_edited(
        "            sourceAddressPrefixes: sshAllowedSourcePrefixes",
        f"            sourceAddressPrefix: '{wildcard}'",
    ))
    assert "no_inbound_allow_rule_names_a_wildcard_source" in _failed_ids(root)


def test_a_second_nsg_with_an_open_rule_is_caught(tmp_path):
    """The reader looks at every NSG, not just the one it expects. A rule added
    in a new resource is the likeliest way this gets loosened."""
    text = TEMPLATE.read_text(encoding="utf-8")
    text += """
resource sneaky 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: 'extra-nsg'
  location: location
  properties: {
    securityRules: [
      {
        name: 'allow-everything'
        properties: {
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
          access: 'Allow'
          direction: 'Inbound'
          priority: 100
        }
      }
    ]
  }
}
"""
    assert "no_inbound_allow_rule_names_a_wildcard_source" in _failed_ids(
        _fake_repo(tmp_path, template=text)
    )


def test_removing_the_deployment_time_guard_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "length(wildcardSources) == 0 ? true : fail(",
        "length(wildcardSources) >= 0 ? true : _unreachable(",
    ))
    assert "a_wildcard_is_refused_at_deployment_time_too" in _failed_ids(root)


def test_a_guard_nothing_reads_is_caught(tmp_path):
    """An unreferenced Bicep var is never evaluated. A guard that is present and
    unread is a guard that never fires, which looks exactly like a guard."""
    root = _fake_repo(tmp_path, template=_edited(
        "output sshSourceGuardPassed bool = _sshSourceGuard",
        "output sshSourceGuardPassed bool = true",
    ))
    assert "a_wildcard_is_refused_at_deployment_time_too" in _failed_ids(root)


def test_turning_the_public_address_on_by_default_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "param attachPublicIp bool = false",
        "param attachPublicIp bool = true",
    ))
    assert "public_address_is_off_by_default" in _failed_ids(root)


def test_a_user_assigned_identity_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "    type: 'SystemAssigned'",
        "    type: 'UserAssigned'",
    ))
    assert "identity_is_system_assigned" in _failed_ids(root)


def test_granting_the_identity_a_role_is_caught(tmp_path):
    """The permission change the card requires to be asked for rather than
    defaulted into."""
    text = TEMPLATE.read_text(encoding="utf-8") + """
resource grant 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vm.id, 'Contributor')
  properties: {
    principalId: vm.identity.principalId
    roleDefinitionId: 'whatever'
  }
}
"""
    assert "the_identity_is_granted_nothing" in _failed_ids(
        _fake_repo(tmp_path, template=text)
    )


@pytest.mark.parametrize(
    "param_name",
    [
        "adminPassword",
        "storageAccountKey",  # camelCase: no word boundary before the K
        "storage_account_key",
        "apiKey",
        "clientSecret",
        "sasToken",
        "vmConnectionString",
    ],
)
def test_a_defaulted_credential_parameter_is_caught(tmp_path, param_name):
    text = TEMPLATE.read_text(encoding="utf-8") + f"""
param {param_name} string = 'a-real-looking-value'
"""
    assert "no_credential_shaped_parameter_carries_a_default" in _failed_ids(
        _fake_repo(tmp_path, template=text)
    )


def test_the_credential_check_sees_camel_case_at_all():
    """The bug this check was written with, kept as a regression.

    The first version matched names with ``r"\\bkey\\b"``, which cannot match the
    ``Key`` in ``storageAccountKey`` -- there is no word boundary between ``t``
    and ``K``. It also missed ``adminPublicKey``, the one credential-shaped
    parameter this template actually has, so the check could not fail and was
    passing for the wrong reason. Names are split into words before matching."""
    assert checker.is_credential_shaped("storageAccountKey")
    assert checker.is_credential_shaped("adminPublicKey")
    assert checker.is_credential_shaped("ADMIN_PASSWORD")
    assert checker.is_credential_shaped("vmConnectionString")
    # And the parameters this template does carry are not swept up by it.
    for benign in ("location", "namePrefix", "vmSize", "adminUsername", "tags",
                   "osDiskSizeGb", "attachPublicIp", "autoShutdownTimeZone",
                   "imagePublisher", "sshAllowedSourcePrefixes", "monkeyBusiness"):
        assert not checker.is_credential_shaped(benign), benign


def test_the_one_credential_shaped_parameter_here_is_the_key_and_it_has_no_default(report):
    """``adminPublicKey`` is credential-shaped and is allowed to exist. What is
    refused is a default, because a default is a value in the repository."""
    entry = next(c for c in report.checks
                 if c.check_id == "no_credential_shaped_parameter_carries_a_default")
    assert entry.ok
    assert "adminPublicKey" in entry.evidence
    assert "with defaults: none" in entry.evidence


def test_custom_data_is_caught(tmp_path):
    """customData runs at first boot, before anybody reviews it, and is where
    secrets end up when a bootstrap is inlined into the template."""
    root = _fake_repo(tmp_path, template=_edited(
        "      adminUsername: adminUsername",
        "      adminUsername: adminUsername\n      customData: base64('#!/bin/sh\\necho hi')",
    ))
    assert "nothing_is_baked_into_the_machine_at_first_boot" in _failed_ids(root)


def test_disabling_the_automatic_shutdown_is_caught(tmp_path):
    root = _fake_repo(tmp_path, template=_edited(
        "    status: 'Enabled'",
        "    status: 'Disabled'",
    ))
    assert "it_shuts_itself_down" in _failed_ids(root)


def test_removing_the_automatic_shutdown_entirely_is_caught(tmp_path):
    text = TEMPLATE.read_text(encoding="utf-8")
    start = text.index("resource autoShutdown")
    end = text.index("output vmName")
    assert "it_shuts_itself_down" in _failed_ids(
        _fake_repo(tmp_path, template=text[:start] + text[end:])
    )


def test_adopting_an_existing_resource_is_caught(tmp_path):
    """다른 프로젝트의 기존 VM을 소유권 확인 없이 재사용하지 않는다 -- a template
    that can only create cannot reuse."""
    text = TEMPLATE.read_text(encoding="utf-8") + """
resource borrowed 'Microsoft.Compute/virtualMachines@2024-07-01' existing = {
  name: 'somebody-elses-vm'
}
"""
    assert "no_existing_resource_is_adopted" in _failed_ids(
        _fake_repo(tmp_path, template=text)
    )


# ── The reader can fail on the scripts too ─────────────────────────────────


def test_dropping_the_subscription_requirement_is_caught(tmp_path):
    deploy = DEPLOY.read_text(encoding="utf-8").replace(
        'intended="${GDPVAL_DEV_HOST_SUBSCRIPTION:-}"',
        'intended="$(az account show --query id -o tsv)"',
    )
    failed = _failed_ids(_fake_repo(tmp_path, deploy=deploy))
    assert "deploy_will_not_pick_a_subscription_for_you" in failed


def test_dropping_the_foundry_refusal_is_caught(tmp_path):
    deploy = DEPLOY.read_text(encoding="utf-8").replace(
        "AZURE_AI_EXPECTED_SUBSCRIPTION_ID", "SOMETHING_ELSE"
    )
    assert "deploy_refuses_the_subscription_the_foundry_checks_expect" in _failed_ids(
        _fake_repo(tmp_path, deploy=deploy)
    )


def test_losing_the_teardown_commands_is_caught(tmp_path):
    deploy = DEPLOY.read_text(encoding="utf-8").replace("az vm deallocate", "az vm stop")
    assert "teardown_is_a_command_not_a_paragraph" in _failed_ids(
        _fake_repo(tmp_path, deploy=deploy)
    )


@pytest.mark.parametrize(
    "line",
    [
        "sysctl -w kernel.apparmor_restrict_unprivileged_userns=0",
        "echo 0 > /proc/sys/kernel/apparmor_restrict_unprivileged_userns",
        "echo 0 | tee /proc/sys/kernel/apparmor_restrict_unprivileged_userns",
    ],
)
def test_clearing_the_namespace_restriction_is_caught(tmp_path, line):
    """The refused shortcut, in each of the ways somebody would reach for it.

    Setting this to 0 makes the sandbox tests pass on Ubuntu 24.04 by removing
    unprivileged user namespace restriction from every process on the machine.
    That is not a fix; it is the absence of the restriction the tests were
    checking for. If the answer turns out to be an AppArmor profile for one
    binary, that is a security-policy change to ask for, not to slip into a
    bootstrap script.
    """
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8") + f"\n{line}\n"
    assert "bootstrap_reads_the_namespace_restriction_and_does_not_clear_it" in _failed_ids(
        _fake_repo(tmp_path, bootstrap=bootstrap)
    )


def test_the_real_bootstrap_still_reads_that_sysctl(tmp_path):
    """The counterpart. Not writing it is only meaningful if it is still read --
    otherwise the check would pass on a bootstrap that never looked."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert checker.APPARMOR_SYSCTL in text
    assert "/proc/sys/kernel/apparmor_restrict_unprivileged_userns" in text


def test_dropping_the_development_host_marker_is_caught(tmp_path):
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8").replace(
        "benchmark_execution_environment=no", "benchmark_execution_environment=maybe"
    )
    assert "bootstrap_marks_the_machine_as_not_a_benchmark_environment" in _failed_ids(
        _fake_repo(tmp_path, bootstrap=bootstrap)
    )


def test_copying_the_users_checkout_instead_of_cloning_is_caught(tmp_path):
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8").replace(
        'git clone --depth 50 "${REPO_URL}" "${CHECKOUT}"',
        'rsync -a /home/dev/checkout/ "${CHECKOUT}"',
    )
    assert "bootstrap_clones_rather_than_copying_the_users_checkout" in _failed_ids(
        _fake_repo(tmp_path, bootstrap=bootstrap)
    )


# ── The Bicep reader itself ────────────────────────────────────────────────


def test_comments_do_not_satisfy_a_check():
    """The failure a grep-based checker has. A promise written in a comment is
    not a promise the deployment keeps."""
    text = "// disablePasswordAuthentication: true\nparam x string = 'y'\n"
    assert "disablePasswordAuthentication" not in checker.strip_comments(text).replace(
        " ", ""
    ).replace("param", "|")[: text.index("param")]
    stripped = checker.strip_comments(text)
    assert "disablePasswordAuthentication" not in stripped
    assert "param x string" in stripped


def test_a_url_inside_a_string_is_not_read_as_a_comment():
    """`'https://example'` contains `//`. A naive comment stripper eats the rest
    of the line and everything after it becomes unparseable -- or worse, parses
    into something else."""
    text = "param u string = 'https://example.invalid/x'\nparam v bool = true\n"
    stripped = checker.strip_comments(text)
    assert "https://example.invalid/x" in stripped
    assert "param v bool = true" in stripped


def test_a_brace_inside_a_string_does_not_close_a_block():
    block = "{\n  a: 'has } inside'\n  b: true\n}"
    assert dict(checker.fields(block)) == {"a": "'has } inside'", "b": "true"}


def test_a_multiline_call_value_does_not_leak_its_insides():
    """The bug this reader had, kept as a test. `securityRules: concat(` spans
    lines; stopping the value at the first newline lifts the nested
    `access: 'Allow'` up to the top level, where a security check then finds a
    rule that is not in that object at all."""
    block = """{
  securityRules: concat(
    [
      {
        name: 'inner'
        properties: {
          access: 'Allow'
        }
      }
    ]
  )
  other: 'x'
}"""
    keys = dict(checker.fields(block))
    assert set(keys) == {"securityRules", "other"}
    assert checker.field_at(block, "access") is None


def test_field_at_walks_a_path_rather_than_searching_the_file():
    block = "{\n  properties: {\n    osProfile: {\n      x: 'deep'\n    }\n  }\n}"
    assert checker.literal(checker.field_at(block, "properties.osProfile.x")) == "deep"
    assert checker.field_at(block, "properties.x") is None


def test_literals_come_back_as_values_and_expressions_come_back_as_text():
    assert checker.literal("'a'") == "a"
    assert checker.literal("true") is True
    assert checker.literal("false") is False
    assert checker.literal("128") == 128
    assert checker.literal("[]") == []
    assert checker.literal("['a', 'b']") == ["a", "b"]
    assert checker.literal("union(a, b)") == "union(a, b)"


def test_an_unparseable_template_is_an_error_not_a_pass(tmp_path):
    """The honest failure. A reader that cannot read the file must say so, not
    return an empty set of findings that looks identical to a clean bill."""
    root = _fake_repo(tmp_path, template="resource broken 'A/b@1' = {\n  name: 'x'\n")
    with pytest.raises(checker.BicepParseError):
        checker.check(root)


def test_an_empty_template_is_an_error_not_a_pass(tmp_path):
    root = _fake_repo(tmp_path, template="// nothing here at all\n")
    with pytest.raises(checker.BicepParseError):
        checker.check(root)


# ── The command-line surface ───────────────────────────────────────────────


def test_the_cli_exits_zero_on_the_real_definition(tmp_path):
    out = tmp_path / "report.json"
    code = checker.main(["--root", str(REPO_ROOT), "--json", "--out", str(out)])
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == checker.SCHEMA
    assert payload["verdict"] == "ok"


def test_the_cli_exits_one_when_a_promise_is_withdrawn(tmp_path, capsys):
    root = _fake_repo(tmp_path, template=_edited(
        "param attachPublicIp bool = false",
        "param attachPublicIp bool = true",
    ))
    assert checker.main(["--root", str(root)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_the_cli_exits_two_when_it_cannot_read(tmp_path, capsys):
    """Two states, not one: a definition that broke a promise and a reader that
    could not read. Collapsing them would let a deleted file look like a pass."""
    assert checker.main(["--root", str(tmp_path / "nothing-here")]) == 2
    assert "could not read" in capsys.readouterr().err


def test_running_it_as_a_program_works():
    """It is documented as `python scripts/check_dev_host_definition.py`, so
    that is exercised rather than assumed."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "batch-runner/scripts/check_dev_host_definition.py"),
         "--root", str(REPO_ROOT), "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["verdict"] == "ok"
