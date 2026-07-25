import base64
import json

import pytest

from scripts.azure_oidc_identity_preflight import (
    AI_AUDIENCE,
    AI_SCOPE,
    validate_configured_identity,
    verify_session_identity,
)


CLIENT_ID = "11111111-1111-4111-8111-111111111111"
TENANT_ID = "22222222-2222-4222-8222-222222222222"
SUBSCRIPTION_ID = "33333333-3333-4333-8333-333333333333"
NOW = 2_000_000_000


def _environment(**updates):
    environ = {
        "AZURE_CLIENT_ID": CLIENT_ID,
        "AZURE_TENANT_ID": TENANT_ID,
        "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION_ID,
        "AZURE_AI_EXPECTED_CLIENT_ID": CLIENT_ID,
        "AZURE_AI_EXPECTED_TENANT_ID": TENANT_ID,
        "AZURE_AI_EXPECTED_SUBSCRIPTION_ID": SUBSCRIPTION_ID,
    }
    environ.update(updates)
    return environ


def _token(**claims):
    claims = {
        "aud": AI_AUDIENCE,
        "nbf": NOW - 60,
        "exp": NOW + 3600,
        **claims,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(claims, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"


def test_configured_identity_requires_independent_exact_match():
    with pytest.raises(ValueError, match="differs from expected") as error:
        validate_configured_identity(_environment(
            AZURE_CLIENT_ID="44444444-4444-4444-8444-444444444444"
        ))

    assert CLIENT_ID not in str(error.value)


def test_configured_identity_requires_all_expected_values():
    with pytest.raises(ValueError, match="expected Azure OIDC tenant ID"):
        validate_configured_identity(_environment(
            AZURE_AI_EXPECTED_TENANT_ID=""
        ))


def test_session_identity_binds_account_and_ai_token_claims():
    calls = []

    def run_az(arguments):
        calls.append(arguments)
        if arguments[:2] == ["account", "show"]:
            return json.dumps({"id": SUBSCRIPTION_ID, "tenantId": TENANT_ID})
        return _token(tid=TENANT_ID, azp=CLIENT_ID)

    assert verify_session_identity(
        _environment(), run_az, now=lambda: NOW
    ) == {
        "client": CLIENT_ID,
        "tenant": TENANT_ID,
        "subscription": SUBSCRIPTION_ID,
    }
    assert calls[1] == [
        "account",
        "get-access-token",
        "--scope",
        AI_SCOPE,
        "--query",
        "accessToken",
        "--output",
        "tsv",
    ]


def test_session_identity_rejects_wrong_valid_token_client_without_leaking_it():
    wrong_client = "44444444-4444-4444-8444-444444444444"

    def run_az(arguments):
        if arguments[:2] == ["account", "show"]:
            return json.dumps({"id": SUBSCRIPTION_ID, "tenantId": TENANT_ID})
        return _token(tid=TENANT_ID, appid=wrong_client)

    with pytest.raises(ValueError, match="token differs") as error:
        verify_session_identity(_environment(), run_az, now=lambda: NOW)

    assert wrong_client not in str(error.value)


def test_session_identity_rejects_wrong_active_subscription():
    def run_az(arguments):
        if arguments[:2] == ["account", "show"]:
            return json.dumps({
                "id": "44444444-4444-4444-8444-444444444444",
                "tenantId": TENANT_ID,
            })
        raise AssertionError("token must not be requested")

    with pytest.raises(ValueError, match="account differs"):
        verify_session_identity(_environment(), run_az, now=lambda: NOW)


@pytest.mark.parametrize(
    ("claim_updates", "message"),
    [
        ({"aud": "https://cognitiveservices.azure.com"}, "audience"),
        ({"nbf": NOW - 3600, "exp": NOW - 61}, "expired"),
        ({"nbf": NOW + 61}, "not yet valid"),
        ({"nbf": NOW + 10, "exp": NOW}, "lifetime"),
    ],
)
def test_session_identity_rejects_wrong_audience_or_lifetime(
    claim_updates, message
):
    def run_az(arguments):
        if arguments[:2] == ["account", "show"]:
            return json.dumps({"id": SUBSCRIPTION_ID, "tenantId": TENANT_ID})
        return _token(tid=TENANT_ID, azp=CLIENT_ID, **claim_updates)

    with pytest.raises(ValueError, match=message):
        verify_session_identity(_environment(), run_az, now=lambda: NOW)
