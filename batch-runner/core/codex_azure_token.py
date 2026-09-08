"""Print one Microsoft Entra access token, for Codex's provider auth command.

Codex authenticates a model provider in one of two ways: an environment
variable holding a key, or a command whose **standard output is the token**.
This module is that command. It exists because the first way is closed to us —
every static Azure credential name is on
``core.azure_ai_clients.FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV`` and rejected
before any client is built — while the second way fits the sign-in this
repository already uses everywhere else.

So the run place gets Codex's provider auth without inventing a second, weaker
credential path. The token comes from ``DefaultAzureCredential`` through
``get_bearer_token_provider``, the same two calls the rest of the repository
makes, at the same scopes.

Usage, as Codex invokes it::

    python -m core.codex_azure_token --scope https://ai.azure.com/.default

Output discipline
-----------------

Standard output carries the token and nothing else: no banner, no trailing
commentary, one line. Every diagnostic goes to standard error, and no
diagnostic ever contains the token or any part of it — not a prefix, not a
length-and-first-four "for debugging". A token is a bearer credential; a
fragment of one in a log is still a fragment of a credential in a log.

On failure this exits non-zero with a short reason on standard error and
nothing at all on standard output, so that Codex sees an empty token rather
than an error message it might try to send as one.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from core.azure_ai_clients import (
    DIRECT_TOKEN_SCOPE,
    LEGACY_TOKEN_SCOPE,
    DefaultAzureCredential,
    get_bearer_token_provider,
)

#: The scopes this helper will ask for. An arbitrary scope is refused rather
#: than passed through: a token minted for an audience nobody here reviewed is
#: exactly the kind of quiet widening this repository's auth rules exist to
#: prevent.
ALLOWED_SCOPES: tuple[str, ...] = (DIRECT_TOKEN_SCOPE, LEGACY_TOKEN_SCOPE)


class TokenCommandError(RuntimeError):
    """The token could not be produced. The message never carries the token."""


def acquire_token(scope: str) -> str:
    """Return one access token for ``scope``.

    Raises :class:`TokenCommandError` when the scope is not one of
    :data:`ALLOWED_SCOPES`, when the sign-in fails, or when the provider hands
    back something that is not a usable token.
    """
    if scope not in ALLOWED_SCOPES:
        raise TokenCommandError(
            "refusing to mint a token for an unreviewed audience; allowed "
            "scopes are " + ", ".join(ALLOWED_SCOPES)
        )
    try:
        credential = DefaultAzureCredential()
    except Exception as exc:  # noqa: BLE001 - reported by type, never by value
        raise TokenCommandError(
            f"could not build the Azure credential ({type(exc).__name__})"
        ) from None
    try:
        provider = get_bearer_token_provider(credential, scope)
        token = provider()
    except Exception as exc:  # noqa: BLE001
        raise TokenCommandError(
            f"could not acquire an access token ({type(exc).__name__})"
        ) from None
    finally:
        close = getattr(credential, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001 - closing must not mask the result
                pass

    if not isinstance(token, str) or not token.strip():
        raise TokenCommandError("the credential returned an empty token")
    if "\n" in token or "\r" in token:
        # A newline would end the line Codex reads and turn the remainder into
        # whatever follows on stdout. Refuse rather than silently truncate.
        raise TokenCommandError("the credential returned a malformed token")
    return token


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.codex_azure_token",
        description=(
            "Print one Entra access token on stdout for Codex provider auth."
        ),
    )
    parser.add_argument(
        "--scope",
        default=DIRECT_TOKEN_SCOPE,
        help="token audience; one of: " + ", ".join(ALLOWED_SCOPES),
    )
    args = parser.parse_args(argv)

    try:
        token = acquire_token(args.scope)
    except TokenCommandError as exc:
        print(f"codex-azure-token: {exc}", file=sys.stderr)
        return 1

    # Written without a trailing newline suppressed on purpose: Codex reads the
    # token from stdout and strips surrounding whitespace, and a bare newline
    # is the ordinary way a command ends a single-value output.
    sys.stdout.write(token + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
