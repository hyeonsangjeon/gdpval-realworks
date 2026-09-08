"""What the Foundry connection diagnostic may and may not say.

The script's job is to turn one request into a finding, and there are two ways
it could fail at that without failing loudly. It could say more than the
request supports — call a one-word text answer proof that the run place works.
Or it could write down something it must not: the endpoint, the account name,
the project name, a token. Both are checked here.

None of these tests make a request. The classification, the redaction and the
record shape are all decidable without one, which is the point of separating
them from the call.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from enum import Enum
from pathlib import Path

import pytest
import yaml

from scripts.diagnose_codex_foundry_connection import (
    EXPECTED_REPLY,
    IDENTITY_ENV_NAMES,
    MESSAGE_LIMIT,
    NOT_ESTABLISHED_BY_A_TEXT_TURN,
    PROMPT,
    SCHEMA,
    VERDICT_AUTHENTICATION_REJECTED,
    VERDICT_CONNECTED,
    VERDICT_CONTENT_FILTERED,
    VERDICT_CONTEXT_WINDOW_EXCEEDED,
    VERDICT_DEPLOYMENT_NOT_FOUND,
    VERDICT_NOT_SENT,
    VERDICT_PROVIDER_SERVER_ERROR,
    VERDICT_PROVIDER_UNREACHABLE,
    VERDICT_QUOTA_EXHAUSTED,
    VERDICT_RATE_LIMITED,
    VERDICT_REQUEST_SHAPE_REJECTED,
    VERDICT_SANDBOX_FAILED,
    VERDICT_SETTINGS_INCOMPLETE,
    VERDICT_UNCLASSIFIED_FAILURE,
    VERDICTS,
    VERDICTS_THE_PROVIDER_ANSWERED,
    _empty_observation,
    _record,
    build_redactor,
    classify_turn_error,
    describe_settings,
    host_fingerprint,
    main,
    read_codex_error_info,
    request_plan,
    settings_fingerprint,
    settings_from_environment,
    verdict_for_http_status,
)

ACCOUNT = "some-account-name"
PROJECT = "some-project-name"
ENDPOINT = f"https://{ACCOUNT}.services.ai.azure.com/openai/v1/"
DEPLOYMENT = "gpt-5.4"


def _settings(**overrides):
    from core.codex_runtime_config import CodexProviderSettings

    values = {"endpoint": ENDPOINT, "model": DEPLOYMENT}
    values.update(overrides)
    return CodexProviderSettings(**values)


# ── Stand-ins for the SDK's error types ─────────────────────────────────────
#
# Shaped like the real ones rather than imported, so these tests describe the
# contract the script reads — a root model over an enum or a one-field model —
# and keep working if the SDK is not installed.


class _ErrorName(Enum):
    unauthorized = "unauthorized"
    bad_request = "badRequest"
    cyber_policy = "cyberPolicy"
    usage_limit_exceeded = "usageLimitExceeded"
    context_window_exceeded = "contextWindowExceeded"
    sandbox_error = "sandboxError"
    other = "other"


class _Root:
    def __init__(self, root):
        self.root = root


class _Inner:
    def __init__(self, http_status_code=None):
        self.http_status_code = http_status_code


class HttpConnectionFailedCodexErrorInfo:
    model_fields = {"http_connection_failed": None}

    def __init__(self, status=None):
        self.http_connection_failed = _Inner(status)


class ResponseStreamDisconnectedCodexErrorInfo:
    model_fields = {"response_stream_disconnected": None}

    def __init__(self, status=None):
        self.response_stream_disconnected = _Inner(status)


class SomethingNewCodexErrorInfo:
    """A variant this SDK version does not have. Later ones might."""

    model_fields = {"something_new": None}

    def __init__(self):
        self.something_new = _Inner(None)


class _TurnError:
    def __init__(self, message="", info=None, additional_details=None):
        self.message = message
        self.codex_error_info = info
        self.additional_details = additional_details


# ── Reading the structured error ────────────────────────────────────────────


def test_the_enum_form_reports_its_name_and_no_status():
    name, status = read_codex_error_info(_Root(_ErrorName.unauthorized))
    assert name == "unauthorized"
    assert status is None


def test_the_variant_form_reports_the_forwarded_http_status():
    """This is the number the SDK's own collector throws away.

    ``TurnHandle.run`` raises ``RuntimeError(turn.error.message)`` and drops
    ``codex_error_info`` with it, so recovering the status after the fact would
    cost a second paid request to learn what the first one already said.
    """
    name, status = read_codex_error_info(
        _Root(HttpConnectionFailedCodexErrorInfo(status=401))
    )
    assert name == "http_connection_failed"
    assert status == 401


def test_a_variant_this_sdk_does_not_have_reports_its_name_rather_than_other():
    """A later SDK's new error must not be classified as one we understand."""
    name, status = read_codex_error_info(_Root(SomethingNewCodexErrorInfo()))
    assert name == "something_new"
    assert status is None


def test_no_error_information_at_all_reads_as_nothing():
    assert read_codex_error_info(None) == (None, None)


# ── Turning it into a verdict ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, VERDICT_AUTHENTICATION_REJECTED),
        (403, VERDICT_AUTHENTICATION_REJECTED),
        (404, VERDICT_DEPLOYMENT_NOT_FOUND),
        (429, VERDICT_RATE_LIMITED),
        (400, VERDICT_REQUEST_SHAPE_REJECTED),
        (422, VERDICT_REQUEST_SHAPE_REJECTED),
        (500, VERDICT_PROVIDER_SERVER_ERROR),
        (503, VERDICT_PROVIDER_SERVER_ERROR),
    ],
)
def test_each_http_status_maps_to_the_verdict_that_names_its_cause(
    status, expected
):
    assert verdict_for_http_status(status) == expected


def test_a_sign_in_failure_and_a_payload_failure_stay_apart():
    """The distinction the whole diagnostic exists to draw.

    ``core.execution_environment_readiness`` lists "the sign-in has never been
    accepted" and "which API contract this deployment serves Codex on is
    unmeasured" as two separate blockers, and they are fixed in different
    files. A verdict that merged a 401 with a 400 would clear neither and would
    read as if it had cleared both.
    """
    unauthorized = classify_turn_error(
        _TurnError(info=_Root(_ErrorName.unauthorized))
    )
    bad_request = classify_turn_error(
        _TurnError(info=_Root(_ErrorName.bad_request))
    )
    assert unauthorized[0] == VERDICT_AUTHENTICATION_REJECTED
    assert bad_request[0] == VERDICT_REQUEST_SHAPE_REJECTED
    assert unauthorized[0] != bad_request[0]


def test_the_http_status_wins_over_the_name_when_both_are_present():
    """The name is Codex's summary; the status is what the provider said.

    A ``httpConnectionFailed`` carrying 404 is a deployment that does not
    exist, which is a different fix from a connection that failed.
    """
    verdict, name, status = classify_turn_error(
        _TurnError(info=_Root(HttpConnectionFailedCodexErrorInfo(status=404)))
    )
    assert verdict == VERDICT_DEPLOYMENT_NOT_FOUND
    assert name == "http_connection_failed"
    assert status == 404


def test_a_connection_that_never_got_a_status_is_unreachable_not_rejected():
    verdict, _name, status = classify_turn_error(
        _TurnError(info=_Root(ResponseStreamDisconnectedCodexErrorInfo()))
    )
    assert verdict == VERDICT_PROVIDER_UNREACHABLE
    assert status is None


@pytest.mark.parametrize(
    "name,expected",
    [
        (_ErrorName.cyber_policy, VERDICT_CONTENT_FILTERED),
        (_ErrorName.usage_limit_exceeded, VERDICT_QUOTA_EXHAUSTED),
        (_ErrorName.context_window_exceeded, VERDICT_CONTEXT_WINDOW_EXCEEDED),
        (_ErrorName.sandbox_error, VERDICT_SANDBOX_FAILED),
    ],
)
def test_the_remaining_named_errors_keep_their_own_verdicts(name, expected):
    assert classify_turn_error(_TurnError(info=_Root(name)))[0] == expected


def test_an_unexplained_failure_stays_unexplained():
    """No guessing a cause out of the message text.

    Reading prose to decide what went wrong is exactly what the structured
    error replaces, and a wrong guess here would send somebody to fix the
    wrong file.
    """
    verdict, name, status = classify_turn_error(
        _TurnError(message="401 Unauthorized: token rejected by the gateway")
    )
    assert verdict == VERDICT_UNCLASSIFIED_FAILURE
    assert (name, status) == (None, None)


def test_every_verdict_the_classifier_can_produce_is_in_the_vocabulary():
    produced = {
        classify_turn_error(_TurnError(info=_Root(value)))[0]
        for value in _ErrorName
    }
    produced |= {verdict_for_http_status(code) for code in (400, 401, 404, 429, 500)}
    assert produced <= set(VERDICTS)


def test_only_verdicts_that_mean_the_provider_spoke_are_marked_as_such():
    """A missing setting and a refused token are not the same kind of fact.

    One says something about the deployment; the other says something about
    us. Only the first can settle a readiness blocker, so the record carries
    the difference rather than leaving a reader to infer it.
    """
    assert VERDICT_CONNECTED in VERDICTS_THE_PROVIDER_ANSWERED
    assert VERDICT_AUTHENTICATION_REJECTED in VERDICTS_THE_PROVIDER_ANSWERED
    assert VERDICT_SETTINGS_INCOMPLETE not in VERDICTS_THE_PROVIDER_ANSWERED
    assert VERDICT_NOT_SENT not in VERDICTS_THE_PROVIDER_ANSWERED
    assert VERDICT_PROVIDER_UNREACHABLE not in VERDICTS_THE_PROVIDER_ANSWERED
    assert VERDICTS_THE_PROVIDER_ANSWERED <= set(VERDICTS)


# ── Keeping the resource out of the record ──────────────────────────────────


def test_the_endpoint_never_appears_in_a_message_that_is_written_down():
    redact = build_redactor({})
    message = f"POST {ENDPOINT}responses failed with 400"
    assert ENDPOINT not in redact(message)
    assert "<url redacted>" in redact(message)


def test_a_token_shaped_string_is_blanked_even_though_it_should_not_be_there():
    """Defence in depth: nothing is supposed to put a token in a message.

    ``core/codex_azure_token.py`` never prints one, not even a prefix. This
    exists because the message being redacted comes from the runtime rather
    than from us, and a rule that only holds while every other component
    behaves is not a rule.
    """
    redact = build_redactor({})
    token = "eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJodHRwcyJ9.c2lnbmF0dXJl"
    cleaned = redact(f"authorization: Bearer {token}")
    assert token not in cleaned
    assert "redacted" in cleaned


def test_the_identity_variables_are_blanked_because_actions_will_not_mask_them():
    """They are repository *variables*, so they reach a public log verbatim.

    Which means the discipline has to live here rather than in the runner's
    secret masking, and it has to cover the account and the project name
    separately: a message can quote either.
    """
    environ = {
        "AZURE_AI_EXPECTED_PROJECT_ACCOUNT": ACCOUNT,
        "AZURE_AI_EXPECTED_PROJECT_NAME": PROJECT,
    }
    redact = build_redactor(environ)
    cleaned = redact(f"resource {ACCOUNT} project {PROJECT} refused the request")
    assert ACCOUNT not in cleaned
    assert PROJECT not in cleaned


def test_redaction_covers_every_identity_variable_the_script_knows_about():
    values = {name: f"value-for-{index}" for index, name in enumerate(IDENTITY_ENV_NAMES)}
    redact = build_redactor(values)
    cleaned = redact(" ".join(values.values()))
    for value in values.values():
        assert value not in cleaned


def test_the_names_are_recovered_from_the_endpoint_the_run_was_given():
    """So the workflow does not have to pass the identity variables at all.

    It must not pass them: a step's ``env:`` block is reprinted verbatim in the
    log, a repository variable is not masked, and the endpoint is a secret. So
    the names are mined back out of the secret, which is what
    ``azure_rbac_diagnostic.py`` does for the same reason.
    """
    redact = build_redactor(
        {
            "FOUNDRY_PROJECT_ENDPOINT": (
                f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}"
            )
        }
    )
    cleaned = redact(f"deployment on {ACCOUNT} in project {PROJECT} was not found")
    assert ACCOUNT not in cleaned
    assert PROJECT not in cleaned


def test_an_endpoint_that_cannot_be_parsed_does_not_stop_the_redactor():
    redact = build_redactor({"FOUNDRY_PROJECT_ENDPOINT": "not a url at all"})
    assert redact("something went wrong") == "something went wrong"


def test_a_name_is_blanked_however_it_was_capitalised():
    redact = build_redactor({"AZURE_AI_EXPECTED_PROJECT_ACCOUNT": ACCOUNT})
    cleaned = redact(f"resource {ACCOUNT.upper()} refused")
    assert ACCOUNT.upper() not in cleaned


def test_a_long_message_is_truncated_rather_than_pasted_whole():
    redact = build_redactor({})
    cleaned = redact("x" * (MESSAGE_LIMIT * 3))
    assert len(cleaned) <= MESSAGE_LIMIT + 1


def test_nothing_stays_nothing():
    assert build_redactor({})(None) is None


def test_the_host_fingerprint_identifies_a_run_without_naming_the_resource():
    fingerprint = host_fingerprint(ENDPOINT)
    assert fingerprint.startswith("sha256:")
    assert ACCOUNT not in fingerprint
    # Same resource, same fingerprint; different resource, different one.
    assert fingerprint == host_fingerprint(ENDPOINT.replace("/openai/v1/", "/"))
    assert fingerprint != host_fingerprint(
        ENDPOINT.replace(ACCOUNT, "another-account")
    )


def test_the_written_description_carries_no_url_and_no_account():
    description = describe_settings(_settings())
    text = json.dumps(description)
    assert ACCOUNT not in text
    assert "services.ai.azure.com" not in text
    # ...and still says enough to know what was measured.
    assert description["deployment"] == DEPLOYMENT
    assert description["endpoint_kind"] == "direct-v1"
    assert description["endpoint_path"] == "/openai/v1/"
    assert description["wire_api"] == "responses"
    assert description["sandbox"] == "workspace-write"
    assert description["approval_mode"] == "deny-all"


# ── The fingerprint ─────────────────────────────────────────────────────────


def test_the_same_settings_fingerprint_the_same_way():
    assert settings_fingerprint(describe_settings(_settings())) == (
        settings_fingerprint(describe_settings(_settings()))
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"model": "gpt-5.3"},
        {"endpoint": ENDPOINT.replace(ACCOUNT, "another-account")},
        {"provider_id": "another-provider"},
    ],
)
def test_changing_what_was_measured_changes_the_fingerprint(overrides):
    """A verdict is only about the settings it was measured under.

    Without this, an old record could be read as evidence for a configuration
    it never saw — which is how a run place gets called connected on the
    strength of a request to something else.
    """
    baseline = settings_fingerprint(describe_settings(_settings()))
    assert settings_fingerprint(describe_settings(_settings(**overrides))) != baseline


# ── The record ──────────────────────────────────────────────────────────────


def test_the_request_is_fixed_before_it_is_sent():
    """One turn, no retries, no tools, and a prompt pinned by its hash.

    Fixing the call count and the prompt before the request exists is what
    makes the cost of this diagnostic a known quantity rather than a discovered
    one.
    """
    plan = request_plan()
    assert plan["turns_sent"] == 1
    assert plan["retries_configured"] == 0
    assert plan["tools_requested"] is False
    assert plan["prompt_characters"] == len(PROMPT)
    assert len(plan["prompt_sha256"]) == 64


def test_the_prompt_forbids_the_tools_it_is_not_testing():
    """So that a success cannot be read as the agent having done anything.

    If the prompt allowed a command, a green verdict would be ambiguous
    between "the model answered" and "the model answered after running
    something", and the second is a claim this probe is not entitled to make.
    """
    lowered = PROMPT.lower()
    assert "do not run any command" in lowered
    assert "do not read any file" in lowered
    assert "do not write any file" in lowered
    assert EXPECTED_REPLY in PROMPT


def test_a_record_always_says_what_it_did_not_establish():
    record = _record(
        verdict=VERDICT_CONNECTED,
        description=describe_settings(_settings()),
        observed=_empty_observation(),
    )
    assert record["schema"] == SCHEMA
    assert record["not_established"] == list(NOT_ESTABLISHED_BY_A_TEXT_TURN)
    joined = " ".join(record["not_established"])
    for missing in ("tool leg", "deliverable leg", "batch leg", "cost leg"):
        assert missing in joined


def test_a_connected_record_still_reports_no_tool_execution():
    """The one claim this probe must never make by accident.

    The directive it was built under is explicit: a single text success is not
    execution success. So the field that would say otherwise is false in the
    record's own default, and the observation that sets it looks for command,
    exec and patch items rather than for the turn having succeeded.
    """
    record = _record(
        verdict=VERDICT_CONNECTED,
        description=describe_settings(_settings()),
        observed=_empty_observation(),
    )
    assert record["observed"]["tool_execution_observed"] is False


def test_the_served_model_is_left_empty_rather_than_filled_in_with_the_request():
    """We asked for a deployment; that is not the same as being served it.

    The pinned SDK exposes no field carrying what the provider reported
    serving, so the honest record is an empty one with the reason attached.
    Copying the requested deployment into it would manufacture a confirmation.
    """
    observed = _empty_observation()
    assert observed["served_model"] is None
    assert "left unrecorded" in observed["served_model_note"]


def test_a_record_with_no_settings_carries_no_fingerprint():
    record = _record(
        verdict=VERDICT_SETTINGS_INCOMPLETE,
        description=None,
        observed=_empty_observation(),
        note="nothing was configured",
    )
    assert record["settings"] is None
    assert record["settings_fingerprint"] is None
    assert record["provider_answered"] is False


def test_a_record_cannot_carry_a_verdict_outside_the_vocabulary():
    with pytest.raises(ValueError):
        _record(
            verdict="looks_fine",
            description=None,
            observed=_empty_observation(),
        )


# ── Refusing to measure something else ──────────────────────────────────────


def test_no_deployment_is_refused_rather_than_defaulted():
    with pytest.raises(ValueError):
        settings_from_environment("", {})


def test_the_endpoint_is_derived_from_the_project_endpoint_already_configured():
    """No new variable and no new secret, which is the point.

    ``AzureAIRouteSettings.from_env`` builds the direct ``/openai/v1/`` URL
    from the Foundry project endpoint the existing OIDC jobs already set, so
    this diagnostic needs nothing granted to it that the repository does not
    already have.
    """
    settings = settings_from_environment(
        DEPLOYMENT,
        {
            "AZURE_AI_ROUTE_PROFILE": "direct-v1",
            "FOUNDRY_PROJECT_ENDPOINT": (
                f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}"
            ),
        },
    )
    assert settings.model == DEPLOYMENT
    assert settings.endpoint.endswith("/openai/v1/")
    assert describe_settings(settings)["endpoint_kind"] == "direct-v1"


def test_an_environment_that_describes_nothing_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        settings_from_environment(DEPLOYMENT, {})


# ── The command ─────────────────────────────────────────────────────────────


ROUTED = {
    "AZURE_AI_ROUTE_PROFILE": "direct-v1",
    "FOUNDRY_PROJECT_ENDPOINT": (
        f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}"
    ),
    "AZURE_AI_EXPECTED_PROJECT_ACCOUNT": ACCOUNT,
    "AZURE_AI_EXPECTED_PROJECT_NAME": PROJECT,
}


def _run(argv, environ, monkeypatch, capsys):
    for name in (
        "AZURE_AI_ROUTE_PROFILE",
        "AZURE_OPENAI_V1_ENDPOINT",
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_OPENAI_LEGACY_ENDPOINT",
        "AZURE_OPENAI_ENDPOINT",
        *IDENTITY_ENV_NAMES,
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_without_send_request_the_command_sends_nothing(monkeypatch, capsys):
    code, record = _run(
        ["--deployment", DEPLOYMENT], ROUTED, monkeypatch, capsys
    )
    assert code == 0
    assert record["verdict"] == VERDICT_NOT_SENT
    assert record["provider_answered"] is False
    assert record["observed"]["turn_sent"] is False
    assert record["settings_fingerprint"].startswith("sha256:")


def test_sending_is_something_you_have_to_ask_for(monkeypatch, capsys):
    """A missing flag must not be the difference between free and paid.

    The default is the direction that costs nothing, so forgetting the flag
    produces a plan rather than a charge.
    """
    import scripts.diagnose_codex_foundry_connection as module

    def _refuse(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("the probe placed a request it was not asked to")

    monkeypatch.setattr(module, "probe", _refuse)
    code, _record_ = _run(["--deployment", DEPLOYMENT], ROUTED, monkeypatch, capsys)
    assert code == 0


def test_the_plan_can_be_kept_as_a_file(monkeypatch, capsys, tmp_path):
    out = tmp_path / "plan.json"
    code, _record_ = _run(
        ["--deployment", DEPLOYMENT, "--out", str(out)],
        ROUTED,
        monkeypatch,
        capsys,
    )
    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["verdict"] == VERDICT_NOT_SENT
    assert ACCOUNT not in out.read_text(encoding="utf-8")


def test_a_run_that_could_not_be_configured_still_leaves_a_record(
    monkeypatch, capsys, tmp_path
):
    """Otherwise the artifact is empty, and empty reads as "never ran".

    Which is the one confusion this whole diagnostic exists to remove: a run
    that was refused before it started and a run that never happened look
    identical from the outside unless the first one says so.
    """
    out = tmp_path / "record.json"
    code, record = _run(
        ["--deployment", DEPLOYMENT, "--out", str(out)], {}, monkeypatch, capsys
    )
    assert code == 2
    assert record["verdict"] == VERDICT_SETTINGS_INCOMPLETE
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == (
        VERDICT_SETTINGS_INCOMPLETE
    )


def test_a_deployment_must_be_named(capsys):
    with pytest.raises(SystemExit):
        main([])


# ── The workflow that runs it ───────────────────────────────────────────────
#
# The script's own discipline is checked above. This section checks the one
# place it is actually invoked, because a careful script called carelessly is
# not careful.


WORKFLOW_PATH = Path("../.github/workflows/codex-foundry-connection-diagnostic.yml")


def _workflow() -> tuple[str, dict]:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def _steps() -> dict:
    _text, parsed = _workflow()
    job = parsed["jobs"]["diagnose"]
    return {step["name"]: step for step in job["steps"] if step.get("name")}


def test_the_workflow_exists_and_only_a_person_can_start_it():
    _text, parsed = _workflow()
    triggers = parsed.get("on", parsed.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    assert triggers["workflow_dispatch"]["inputs"]["deployment"]["required"] is True
    assert "default" not in triggers["workflow_dispatch"]["inputs"]["deployment"]


def test_sending_is_off_unless_it_is_asked_for():
    """The costed path is opt-in in the workflow as well as in the script.

    Two independent defaults rather than one, because the flag and the input
    are edited by different hands at different times.
    """
    _text, parsed = _workflow()
    triggers = parsed.get("on", parsed.get(True))
    assert triggers["workflow_dispatch"]["inputs"]["send_request"]["default"] is False
    send = _steps()["Send the one turn"]
    assert send["if"] == "${{ inputs.send_request }}"
    assert "--send-request" in send["run"]


def test_only_the_step_that_was_asked_to_send_passes_that_flag():
    for name, step in _steps().items():
        if name == "Send the one turn":
            continue
        assert "--send-request" not in step.get("run", ""), name


def test_the_workflow_never_asks_for_a_variable_that_would_name_the_resource():
    """A repository variable is reprinted verbatim in the step's env header.

    So the two that carry the account and project names are not requested
    anywhere in this file — not to redact with, not to verify with. The script
    recovers what it needs from the endpoint secret, which Actions does mask.
    """
    text, _parsed = _workflow()
    assert "AZURE_AI_EXPECTED_PROJECT_ACCOUNT" not in text
    assert "AZURE_AI_EXPECTED_PROJECT_NAME" not in text
    assert "AZURE_AI_EXPECTED_DIRECT_ACCOUNT" not in text
    assert "AZURE_AI_EXPECTED_LEGACY_ACCOUNT" not in text


def test_the_request_is_planned_before_it_can_be_sent():
    steps = list(_steps())
    assert steps.index("Fix the request before anything is sent") < steps.index(
        "Send the one turn"
    )


def test_the_run_is_pinned_to_one_resource_by_a_hash_that_is_safe_to_print():
    """The identity check that does not cost a public account name.

    ``AZURE_AI_REQUIRE_EXPECTED_IDENTITIES`` would do this by comparing against
    a repository variable, which cannot be read without printing it. A sha256
    of the host answers the same question — is this the resource we mean — and
    is safe to write into a public workflow file.
    """
    _text, parsed = _workflow()
    assert "EXPECTED_HOST_FINGERPRINT" in parsed["jobs"]["diagnose"]["env"]
    check = _steps()["Confirm the plan is about the resource this job is pinned to"]
    assert "endpoint_host_fingerprint" in check["run"]
    assert "exit 1" in check["run"]


def test_the_workflow_runs_on_the_host_where_the_sandbox_starts():
    """24.04 restricts unprivileged user namespaces and Codex's sandbox dies.

    A turn that died there would look like the deployment refusing when it was
    the runner, and it would have cost a request to learn nothing.
    """
    _text, parsed = _workflow()
    assert parsed["jobs"]["diagnose"]["runs-on"] == "ubuntu-22.04"


def test_the_python_matches_the_one_the_licence_check_pins():
    setup = _steps()["Setup Python"]
    assert setup["with"]["python-version"] == "3.10.12"


def test_every_action_is_pinned_to_a_commit():
    text, _parsed = _workflow()
    for use in re.findall(r"uses:\s*(\S+)", text):
        assert re.search(r"@[0-9a-f]{40}\Z", use), use


def test_it_signs_in_as_the_identity_the_paid_runs_use():
    """Otherwise a green answer is about somebody else's token.

    Blocker (a) is that *this* identity's token has never been accepted. A
    probe authenticated as anything else could not settle it.
    """
    login = _steps()["Azure Login (OIDC)"]
    assert login["uses"].startswith("azure/login@")
    assert login["with"]["client-id"] == "${{ secrets.AZURE_CLIENT_ID }}"
    _text, parsed = _workflow()
    assert parsed["permissions"]["id-token"] == "write"
    assert parsed["permissions"]["contents"] == "read"


def test_it_runs_from_the_reviewed_branch_only():
    _text, parsed = _workflow()
    assert parsed["jobs"]["diagnose"]["if"] == "github.ref == 'refs/heads/main'"


def test_two_paid_runs_cannot_overlap():
    _text, parsed = _workflow()
    assert parsed["concurrency"]["cancel-in-progress"] is False


def test_the_script_the_workflow_runs_is_in_the_repository():
    """Asks git, not the allowlist, because the allowlist is what goes stale.

    ``batch-runner/scripts/*`` is ignored with a ``!`` list of exceptions. A
    file missing from that list is skipped by ``git add`` without a word, and
    the first sign of it is a job calling a path the checkout does not have.
    """
    text, _parsed = _workflow()
    referenced = set(re.findall(r"scripts/[A-Za-z0-9_./-]+\.py", text))
    assert "scripts/diagnose_codex_foundry_connection.py" in referenced
    for relative in sorted(referenced):
        path = Path(relative)
        assert path.exists(), relative
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(path)],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
        )
        assert tracked.returncode == 0, (
            f"the workflow runs {relative}, but git is not tracking it, so a "
            "clone does not have it and the job cannot run. Add a '!' line for "
            f"it in .gitignore. git said: {tracked.stderr.strip()!r}"
        )


def _redaction_check() -> str:
    for step in _steps().values():
        run = step.get("run", "")
        if "<<'PY'" in run:
            return run.split("<<'PY'", 1)[1].split("\nPY", 1)[0]
    raise AssertionError("the workflow has no redaction check")


def _run_redaction_check(tmp_path, plan, endpoint=None):
    script = tmp_path / "check.py"
    script.write_text(_redaction_check(), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    if plan is not None:
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
    body = _redaction_check().replace(
        '"/tmp/codex-foundry-plan.json"', json.dumps(str(plan_path))
    ).replace(
        '"/tmp/codex-foundry-connection.json"',
        json.dumps(str(tmp_path / "absent.json")),
    )
    script.write_text(body, encoding="utf-8")
    environment = dict(os.environ)
    environment["FOUNDRY_PROJECT_ENDPOINT"] = endpoint or (
        f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}"
    )
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=environment,
        # The step runs from the repository root, and the check reads a file
        # out of the checkout. Running it from anywhere else would test a
        # different program.
        cwd=Path("..").resolve(),
    )


CLEAN_RECORD = {
    "observed": {"tool_execution_observed": False},
    "settings": {"endpoint_host_fingerprint": "sha256:0123456789abcdef"},
}


def test_the_workflows_own_check_passes_a_clean_record(tmp_path):
    result = _run_redaction_check(tmp_path, CLEAN_RECORD)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "record=clean" in result.stdout


@pytest.mark.parametrize(
    "label,record",
    [
        (
            "the account name",
            {
                "observed": {"tool_execution_observed": False},
                "note": f"account {ACCOUNT} refused the request",
            },
        ),
        (
            "the project name",
            {
                "observed": {"tool_execution_observed": False},
                "note": f"project {PROJECT} is not visible",
            },
        ),
        (
            "a url",
            {
                "observed": {"tool_execution_observed": False},
                "note": "POST https://elsewhere.example/responses failed",
            },
        ),
        (
            "a token",
            {
                "observed": {"tool_execution_observed": False},
                "note": "eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJodHRwcyJ9",
            },
        ),
        (
            "a claim of tool execution",
            {"observed": {"tool_execution_observed": True}},
        ),
    ],
)
def test_the_workflows_own_check_catches_what_must_not_be_published(
    tmp_path, label, record
):
    """The script redacts; this is the step that checks it did.

    Held here rather than only in the workflow so the check itself cannot rot
    into a step that greps for nothing and reports clean.
    """
    result = _run_redaction_check(tmp_path, record)
    assert result.returncode == 1, f"{label} was not caught: {result.stdout}"


def test_a_run_with_no_record_is_not_reported_as_clean(tmp_path):
    """The check runs on failure too, and "clean" about nothing is a lie."""
    result = _run_redaction_check(tmp_path, None)
    assert result.returncode == 0
    assert "record=clean" not in result.stdout
    assert "no record exists" in result.stdout


# ── The check against the record that actually gets written ─────────────────
#
# Everything above feeds the check hand-made dictionaries. That is how a real
# plan came to be rejected by it: the plan carries the Entra token scope, which
# is a URL, and the rule was "any URL at all". Nothing had leaked — the scope
# is a tenant-independent constant already sitting in this public repository's
# source — but the run failed, and the upload step ran anyway, which is the
# defect that actually mattered.


def _real_record(**setting_overrides):
    """The record the script builds, not a stand-in shaped like one."""
    return _record(
        verdict=VERDICT_NOT_SENT,
        description=describe_settings(_settings(**setting_overrides)),
        observed=_empty_observation(),
        note="planned only; no request was sent",
    )


def test_the_check_passes_the_record_the_script_actually_writes(tmp_path):
    """The regression. A hand-made record is not the thing being published."""
    result = _run_redaction_check(tmp_path, _real_record())
    assert result.returncode == 0, result.stdout + result.stderr
    assert "record=clean" in result.stdout


def test_the_one_url_allowed_through_is_the_repositorys_own_constant():
    """Not a string in the workflow file — the constant, read from source.

    Written into the workflow instead, the exception would keep passing after
    somebody pointed the scope at a resource-specific audience, which is
    exactly the case a URL rule exists to catch.
    """
    from core.azure_ai_clients import DIRECT_TOKEN_SCOPE

    check = _redaction_check()
    assert "DIRECT_TOKEN_SCOPE" in check
    assert "batch-runner/core/azure_ai_clients.py" in check
    assert DIRECT_TOKEN_SCOPE not in check, (
        "the allowed URL is written into the workflow, so changing the "
        "constant no longer changes what the check allows"
    )


def test_a_scope_pointing_somewhere_else_is_still_caught(tmp_path):
    record = _real_record()
    record["settings"]["auth"]["scope"] = "https://elsewhere.example/.default"
    result = _run_redaction_check(tmp_path, record)
    assert result.returncode == 1, result.stdout


def test_a_second_url_beside_the_allowed_one_is_caught(tmp_path):
    """The allowance is for one string, not for the presence of that string."""
    record = _real_record()
    record["note"] = "POST https://elsewhere.example/responses failed"
    result = _run_redaction_check(tmp_path, record)
    assert result.returncode == 1, result.stdout


def test_a_scope_that_names_the_resource_is_caught_by_the_other_rule(tmp_path):
    """Two independent rules, so neither has to be the whole answer.

    If the constant itself became resource-specific, the URL rule would allow
    it — it allows whatever the constant says. The needle search does not.
    """
    record = _real_record()
    record["settings"]["auth"]["scope"] = f"https://{ACCOUNT}.example/.default"
    result = _run_redaction_check(tmp_path, record)
    assert result.returncode == 1, result.stdout


def test_an_unreadable_source_refuses_rather_than_allowing_every_url(tmp_path):
    """Fail closed. The check cannot establish what is allowed, so nothing is."""
    script = tmp_path / "check.py"
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_real_record()), encoding="utf-8")
    body = _redaction_check().replace(
        '"/tmp/codex-foundry-plan.json"', json.dumps(str(plan_path))
    ).replace(
        '"/tmp/codex-foundry-connection.json"',
        json.dumps(str(tmp_path / "absent.json")),
    )
    script.write_text(body, encoding="utf-8")
    environment = dict(os.environ)
    environment["FOUNDRY_PROJECT_ENDPOINT"] = ENDPOINT
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=environment,
        cwd=tmp_path,  # no checkout here, so the source file is not readable
    )
    assert result.returncode == 1
    assert "FATAL" in result.stdout


# ── A rejected record does not get published ────────────────────────────────


def test_a_record_the_check_rejected_is_not_uploaded():
    """The defect the first real dispatch found.

    The check failed, and ``Keep the record`` uploaded the record anyway,
    because it was ``if: always()``. On a public repository an artifact is
    world-readable the moment it exists, and deleting it afterwards is a
    different fact from never having uploaded it. Nothing had leaked that
    time. The step ordering was the reason it did not matter, and step
    ordering is not a control.
    """
    steps = _steps()
    guard = steps["Confirm the record names no resource and carries no token"]
    assert guard.get("id"), "the guard has no id, so nothing can depend on it"
    upload = steps["Keep the record"]
    condition = upload["if"]
    assert guard["id"] in condition, condition
    assert "!= 'failure'" in condition, condition


def test_the_upload_still_happens_when_something_else_failed():
    """A record of a run that broke is the point of the run.

    The gate is on the redaction check's own verdict, not on the job's.
    """
    upload = _steps()["Keep the record"]
    assert upload["if"].startswith("always()"), upload["if"]


def test_withholding_the_record_is_said_out_loud():
    """A missing artifact reads as "the run did not get that far"."""
    steps = _steps()
    guard = steps["Confirm the record names no resource and carries no token"]
    withheld = steps["Say that the record was withheld"]
    assert guard["id"] in withheld["if"]
    assert "== 'failure'" in withheld["if"]
    assert "GITHUB_STEP_SUMMARY" in withheld["run"]

