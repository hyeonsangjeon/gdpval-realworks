#!/usr/bin/env python3
"""Validate configured and active Azure OIDC workload identity."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import subprocess
import time
from collections.abc import Mapping
from typing import Callable


AI_SCOPE = "https://ai.azure.com/.default"
AI_AUDIENCE = "https://ai.azure.com"
TOKEN_CLOCK_SKEW_SECONDS = 60
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)
_IDENTITY_FIELDS = (
    ("client", "AZURE_CLIENT_ID", "AZURE_AI_EXPECTED_CLIENT_ID"),
    ("tenant", "AZURE_TENANT_ID", "AZURE_AI_EXPECTED_TENANT_ID"),
    (
        "subscription",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_AI_EXPECTED_SUBSCRIPTION_ID",
    ),
)


def _uuid(value: object, label: str) -> str:
    if not isinstance(value, str) or _UUID_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a UUID")
    return value.lower()


def expected_identity(environ: Mapping[str, str]) -> dict[str, str]:
    return {
        name: _uuid(environ.get(expected_env), f"expected Azure OIDC {name} ID")
        for name, _configured_env, expected_env in _IDENTITY_FIELDS
    }


def validate_configured_identity(environ: Mapping[str, str]) -> dict[str, str]:
    expected = expected_identity(environ)
    configured = {
        name: _uuid(environ.get(configured_env), f"configured Azure OIDC {name} ID")
        for name, configured_env, _expected_env in _IDENTITY_FIELDS
    }
    if configured != expected:
        raise ValueError("configured Azure OIDC identity differs from expected identity")
    return expected


def _decode_claims(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Azure AI access token is not a JWT")
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Azure AI access token claims are invalid") from exc
    if not isinstance(claims, dict):
        raise ValueError("Azure AI access token claims are invalid")
    return claims


def _run_az(arguments: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["az", *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Azure CLI identity query failed") from exc
    return completed.stdout.strip()


def _numeric_date(claims: Mapping[str, object], name: str) -> float:
    value = claims.get(name)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"Azure AI token {name} claim is invalid")
    return float(value)


def verify_session_identity(
    environ: Mapping[str, str],
    run_az: Callable[[list[str]], str] = _run_az,
    now: Callable[[], float] = time.time,
) -> dict[str, str]:
    expected = expected_identity(environ)
    try:
        account = json.loads(run_az(["account", "show", "--output", "json"]))
    except json.JSONDecodeError as exc:
        raise ValueError("Azure CLI account identity is invalid") from exc
    if not isinstance(account, dict):
        raise ValueError("Azure CLI account identity is invalid")
    account_identity = {
        "tenant": _uuid(account.get("tenantId"), "active Azure tenant ID"),
        "subscription": _uuid(
            account.get("id"), "active Azure subscription ID"
        ),
    }
    if account_identity != {
        "tenant": expected["tenant"],
        "subscription": expected["subscription"],
    }:
        raise ValueError("active Azure account differs from expected identity")

    token = run_az([
        "account",
        "get-access-token",
        "--scope",
        AI_SCOPE,
        "--query",
        "accessToken",
        "--output",
        "tsv",
    ])
    claims = _decode_claims(token)
    if claims.get("aud") != AI_AUDIENCE:
        raise ValueError("Azure AI token audience is invalid")
    not_before = _numeric_date(claims, "nbf")
    expires_at = _numeric_date(claims, "exp")
    current_time = float(now())
    if not math.isfinite(current_time):
        raise ValueError("Azure AI token validation clock is invalid")
    if expires_at <= not_before:
        raise ValueError("Azure AI token lifetime is invalid")
    if not_before > current_time + TOKEN_CLOCK_SKEW_SECONDS:
        raise ValueError("Azure AI token is not yet valid")
    if expires_at <= current_time - TOKEN_CLOCK_SKEW_SECONDS:
        raise ValueError("Azure AI token is expired")
    tenant = _uuid(claims.get("tid"), "Azure AI token tenant claim")
    client = claims.get("azp") or claims.get("appid")
    client = _uuid(client, "Azure AI token client claim")
    if tenant != expected["tenant"] or client != expected["client"]:
        raise ValueError("Azure AI token differs from expected identity")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-session",
        action="store_true",
        help="Verify active Azure CLI account and ai.azure.com token claims",
    )
    args = parser.parse_args()
    try:
        if args.verify_session:
            verify_session_identity(os.environ)
            print("Azure OIDC session identity verified")
        else:
            validate_configured_identity(os.environ)
            print("Azure OIDC configured identity verified")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
