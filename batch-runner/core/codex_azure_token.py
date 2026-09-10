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

    python -m core.codex_azure_token --scope https://ai.azure.com/.default \
        --azure-config-dir /home/runner/.azure

Where the sign-in lives
-----------------------

Codex runs this command **inside the isolated environment it builds for a
task**, and that environment rewrites ``HOME`` to the task's own directory so
that anything the model writes "to the user's home" lands somewhere disposable.
That is worth keeping. But ``DefaultAzureCredential``'s working leg here is the
Azure CLI, and the CLI finds its sign-in under ``$HOME/.azure``. With ``HOME``
rewritten there is no sign-in to find, the mint fails, and — per the output
discipline below — the command prints nothing. Codex then sends an empty
bearer, and the gateway answers ``401 Access denied due to invalid subscription
key or wrong API endpoint``: a message about the endpoint and the key, which
are both fine, for a fault that is neither.

``--azure-config-dir`` is how the caller hands the location back. It travels in
argv rather than in the environment on purpose: only *this* process, which
prints a token and exits, learns where the sign-in is. The Codex process and
every tool it runs keep the environment they had, so the isolation the sandbox
depends on is unchanged. A path is not a credential, and the directory itself
stays outside everything Codex can reach.

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
import os
import sys
from pathlib import Path
from typing import MutableMapping, Sequence

if __package__ in (None, ""):  # pragma: no cover - exercised as a subprocess
    # Run by path rather than as ``-m core.codex_azure_token``, because Codex
    # starts this command with the *task's* directory as the working
    # directory. From there ``core`` is not importable and ``-m`` fails before
    # argument parsing — which, given the output discipline below, means an
    # empty stdout and a token-shaped silence. Putting the package root on the
    # path here makes the command independent of where it is started from.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.azure_ai_clients import (
    DIRECT_TOKEN_SCOPE,
    LEGACY_TOKEN_SCOPE,
    DefaultAzureCredential,
    get_bearer_token_provider,
)

#: The variable the Azure CLI reads its configuration and token cache from.
#: Setting it is equivalent to pointing the CLI at a different ``~/.azure``.
AZURE_CONFIG_DIR_ENV = "AZURE_CONFIG_DIR"

#: The scopes this helper will ask for. An arbitrary scope is refused rather
#: than passed through: a token minted for an audience nobody here reviewed is
#: exactly the kind of quiet widening this repository's auth rules exist to
#: prevent.
ALLOWED_SCOPES: tuple[str, ...] = (DIRECT_TOKEN_SCOPE, LEGACY_TOKEN_SCOPE)


class TokenCommandError(RuntimeError):
    """The token could not be produced. The message never carries the token."""


def point_at_azure_config_dir(
    directory: str | os.PathLike[str],
    environment: MutableMapping[str, str] | None = None,
) -> str:
    """Point the Azure CLI at ``directory`` for the rest of this process.

    Returns the resolved path, so the caller can report *which* directory was
    used without having to re-derive it.

    A directory that does not exist is refused rather than set. Setting it
    anyway would land us back where this option started: the CLI would look in
    an empty place, report no sign-in, and this command would exit quietly —
    the failure would just have moved. A wrong path is a fixable mistake, and
    saying so is the whole point.
    """
    path = Path(directory)
    if not path.is_dir():
        raise TokenCommandError(
            f"the Azure CLI configuration directory {str(path)!r} does not "
            "exist, so there is no sign-in to read there"
        )
    resolved = str(path)
    target = os.environ if environment is None else environment
    target[AZURE_CONFIG_DIR_ENV] = resolved
    return resolved


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
    parser.add_argument(
        "--azure-config-dir",
        default=None,
        help=(
            "the Azure CLI configuration directory to sign in from, for when "
            "this command runs somewhere HOME does not point at it"
        ),
    )
    args = parser.parse_args(argv)

    try:
        if args.azure_config_dir is not None:
            point_at_azure_config_dir(args.azure_config_dir)
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
