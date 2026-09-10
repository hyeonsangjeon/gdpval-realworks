"""Pinned settings for driving the real Codex runtime against Foundry.

This module holds the *configuration half* of the Codex run place: which
version of the official SDK and of the Codex binary we run, what environment
that binary is allowed to see, and how a Microsoft Foundry deployment is
described to it as a model provider. The *execution half* — handing one GDPVal
task to that runtime and collecting what it produced — is in
``core/codex_runner.py``.

What is pinned here, and why each pin is load-bearing
-----------------------------------------------------

``openai-codex`` is OpenAI's own Python SDK for Codex. It does not reimplement
the agent: :class:`openai_codex.client.CodexClient` spawns the Codex binary as
``codex app-server --listen stdio://`` and speaks JSON-RPC to it. So using this
SDK is using the real runtime, which is the whole point of the run place. The
distribution declares ``Requires-Dist: openai-codex-cli-bin==0.147.0``, an
exact pin rather than a range, so fixing the SDK version fixes the binary
version with it.

Two version facts worth keeping straight, because they look like a mistake and
are not:

* The Python SDK and the npm packages are on different numbers.
  ``openai-codex`` is at 0.147.0 while ``@openai/codex`` and
  ``@openai/codex-sdk`` are at 0.153.4. We take the Python line, because this
  repository is Python and the SDK's own dependency pin is what gives us a
  reproducible binary.
* ``/openai/v1/`` in an endpoint is not a dated ``api-version``. It is Azure
  OpenAI's *undated* contract, in which the request's ``model`` argument names
  the deployment — see ``core.azure_ai_clients.DIRECT_V1_CALL_IDENTITY``. A
  dated ``api-version`` belongs to the legacy route only. Codex's
  ``query_params`` provider setting can carry either, so the distinction has to
  be made here rather than left to whoever writes the experiment file.

What this module does **not** claim
-----------------------------------

Nothing here has been shown to work against a real Foundry deployment. The
settings are built from the published provider reference and from the pinned
SDK's own source; whether our tenant's deployment answers Codex's ``responses``
wire format, at which region and which api-version, is a separate question that
needs a real call to settle. ``core/codex_runner.py`` refuses rather than
guesses when a setting is missing, and the run place stays graded
``structure_check_only`` in ``core.execution_environment_readiness`` until a
real connection is on record.
"""

from __future__ import annotations

import importlib.util
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from core.azure_ai_clients import (
    DIRECT_TOKEN_SCOPE,
    FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV,
    AzureAIRouteSettings,
    EndpointKind,
    classify_endpoint,
)

# ── Version pins ────────────────────────────────────────────────────────────

#: The Python SDK release this repository is written against. Everything below
#: — the provider keys, the isolation behaviour, the shape of the usage numbers
#: — was read out of this version's source, not out of prose about it.
PINNED_CODEX_SDK_DISTRIBUTION = "openai-codex"
PINNED_CODEX_SDK_VERSION = "0.147.0"

#: The Codex binary that ``openai-codex==0.147.0`` pins, exactly, in its own
#: ``Requires-Dist``. Stated here so a reader can check the claim without
#: unpacking a wheel, and so :func:`describe_version_pin` can report both
#: halves of what actually runs.
PINNED_CODEX_CLI_DISTRIBUTION = "openai-codex-cli-bin"
PINNED_CODEX_CLI_VERSION = "0.147.0"

#: The npm line, recorded for completeness because the published SDK guide is
#: written around it. We do not install it; it is a different number from the
#: Python line and mixing them would put an unpinned binary on PATH.
NPM_CODEX_CLI_PACKAGE = "@openai/codex"
NPM_CODEX_SDK_PACKAGE = "@openai/codex-sdk"
NPM_CODEX_LINE_VERSION = "0.153.4"


class CodexRuntimeUnavailable(RuntimeError):
    """The pinned Codex SDK or binary is not installed, or is the wrong one.

    Raised instead of falling back to another run place. A comparison between
    run places is only worth reading if each place either ran or said clearly
    why it could not; quietly substituting a different runner would make the
    Codex column a copy of some other column.
    """


def installed_sdk_version() -> str | None:
    """Return the installed ``openai-codex`` version, or ``None`` if absent."""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - importlib.metadata is stdlib ≥3.8
        return None
    try:
        return version(PINNED_CODEX_SDK_DISTRIBUTION)
    except PackageNotFoundError:
        return None


def installed_cli_version() -> str | None:
    """Return the installed ``openai-codex-cli-bin`` version, or ``None``."""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover
        return None
    try:
        return version(PINNED_CODEX_CLI_DISTRIBUTION)
    except PackageNotFoundError:
        return None


def require_pinned_runtime() -> tuple[str, str]:
    """Check that the pinned SDK and binary are installed; return both versions.

    Raises :class:`CodexRuntimeUnavailable` naming the mismatch. A version that
    merely *differs* is still a refusal: the usage fields, the provider keys and
    the isolation behaviour documented here were read from 0.147.0's source, and
    a different release is a different set of facts.
    """
    sdk = installed_sdk_version()
    if sdk is None:
        raise CodexRuntimeUnavailable(
            f"{PINNED_CODEX_SDK_DISTRIBUTION} is not installed; the Codex run "
            f"place needs {PINNED_CODEX_SDK_DISTRIBUTION}=="
            f"{PINNED_CODEX_SDK_VERSION}"
        )
    if sdk != PINNED_CODEX_SDK_VERSION:
        raise CodexRuntimeUnavailable(
            f"{PINNED_CODEX_SDK_DISTRIBUTION}=={sdk} is installed but this "
            f"repository is written against {PINNED_CODEX_SDK_VERSION}"
        )
    cli = installed_cli_version()
    if cli is None:
        raise CodexRuntimeUnavailable(
            f"{PINNED_CODEX_CLI_DISTRIBUTION} is not installed; the SDK pins "
            f"{PINNED_CODEX_CLI_VERSION} and without the binary there is no "
            "Codex runtime to drive"
        )
    if cli != PINNED_CODEX_CLI_VERSION:
        raise CodexRuntimeUnavailable(
            f"{PINNED_CODEX_CLI_DISTRIBUTION}=={cli} is installed but the "
            f"pinned SDK requires {PINNED_CODEX_CLI_VERSION}"
        )
    return sdk, cli


def describe_version_pin() -> dict[str, str | None]:
    """Report what is pinned and what is actually installed, side by side."""
    return {
        "sdk_distribution": PINNED_CODEX_SDK_DISTRIBUTION,
        "sdk_pinned": PINNED_CODEX_SDK_VERSION,
        "sdk_installed": installed_sdk_version(),
        "cli_distribution": PINNED_CODEX_CLI_DISTRIBUTION,
        "cli_pinned": PINNED_CODEX_CLI_VERSION,
        "cli_installed": installed_cli_version(),
    }


# ── Environment isolation ───────────────────────────────────────────────────
#
# The pinned SDK builds the child environment like this, in
# ``openai_codex/client.py`` at ``CodexClient.start``:
#
#     env = os.environ.copy()
#     if self.config.env:
#         env.update(self.config.env)
#
# Two consequences follow, and both matter more than they look:
#
# 1. ``CodexConfig.env`` **adds to** the parent environment; it does not
#    replace it. This is the opposite of the TypeScript SDK, whose ``env``
#    option is documented as "the SDK will not inherit variables from
#    process.env". Anyone porting the published TypeScript guidance to Python
#    would get inheritance they did not ask for.
# 2. ``dict.update`` cannot *remove* a key. The strongest thing a caller can do
#    is overwrite it. So isolation here means "every name that could carry the
#    operator's identity is overwritten with a value that carries none", not
#    "the name is gone". :func:`build_isolated_environment` overwrites; the
#    accompanying test asserts the overwrite covers the whole list, because the
#    list is the security claim.

#: Names that would otherwise hand the Codex process this machine's own
#: identity, sign-in state, or plugin set. ``CODEX_HOME`` is the big one: the
#: binary keeps ``auth.json``, ``config.toml``, session transcripts and
#: installed plugins under it, so leaving it inherited would mean the
#: experiment silently runs as whoever last signed in at a terminal.
PERSONAL_STATE_ENV_NAMES: tuple[str, ...] = (
    "CODEX_HOME",
    "CODEX_API_KEY",
    "CODEX_CONFIG",
    "CODEX_CONFIG_HOME",
    "CODEX_PROFILE",
    "CODEX_SANDBOX",
    "CODEX_SANDBOX_NETWORK_DISABLED",
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
)

#: Credentials that must never reach a child process. The Azure entries are
#: taken from the repository's own ban list rather than copied, so that adding
#: a name there covers this run place too and the two cannot drift apart.
CREDENTIAL_ENV_NAMES: tuple[str, ...] = (
    *FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV,
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "ANTHROPIC_API_KEY",
    "HF_TOKEN",
    "HUGGINGFACE_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)

#: Everything the child must not inherit, in one list, deduplicated and stable
#: so a test can assert against it by name.
NEUTRALISED_ENV_NAMES: tuple[str, ...] = tuple(
    dict.fromkeys((*PERSONAL_STATE_ENV_NAMES, *CREDENTIAL_ENV_NAMES))
)

#: Variables the child does need, taken from the parent when present. Kept
#: short and explicit; ``PATH`` is here because the SDK prepends the bundled
#: binary's directory to it and dropping it would break that.
INHERITED_ENV_NAMES: tuple[str, ...] = (
    "PATH",
    "LANG",
    "LC_ALL",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "AZURE_CLIENT_ID",
    "AZURE_TENANT_ID",
    "AZURE_FEDERATED_TOKEN_FILE",
    "AZURE_AUTHORITY_HOST",
    "MSI_ENDPOINT",
    "IDENTITY_ENDPOINT",
    "IDENTITY_HEADER",
    "ACTIONS_ID_TOKEN_REQUEST_URL",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
)


def build_isolated_environment(
    *,
    codex_home: str | os.PathLike[str],
    task_home: str | os.PathLike[str],
    source_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the ``CodexConfig.env`` overlay for one task's runtime.

    ``codex_home`` becomes the process's ``CODEX_HOME`` — its config, its
    sign-in state, its session files — and ``task_home`` becomes ``HOME`` and
    the XDG roots, so that anything the binary writes "to the user's home"
    lands inside the task's own directory and disappears with it.

    Every other name in :data:`NEUTRALISED_ENV_NAMES` is set to the empty
    string. That is an overwrite, not a deletion, for the reason given above:
    the SDK merges this mapping into a copy of ``os.environ`` and merging
    cannot delete. An empty value is what a caller can guarantee, so an empty
    value is what this function promises — see
    :func:`inherited_names_that_survive` for the honest report of the
    difference.
    """
    source = dict(os.environ if source_environment is None else source_environment)
    codex_home_path = str(Path(codex_home))
    task_home_path = str(Path(task_home))

    overlay: dict[str, str] = {}
    for name in INHERITED_ENV_NAMES:
        value = source.get(name)
        if value is not None:
            overlay[name] = value

    for name in NEUTRALISED_ENV_NAMES:
        overlay[name] = ""

    overlay["CODEX_HOME"] = codex_home_path
    overlay["HOME"] = task_home_path
    overlay["XDG_CONFIG_HOME"] = str(Path(task_home_path) / ".config")
    overlay["XDG_CACHE_HOME"] = str(Path(task_home_path) / ".cache")
    overlay["XDG_DATA_HOME"] = str(Path(task_home_path) / ".local" / "share")
    overlay["XDG_STATE_HOME"] = str(Path(task_home_path) / ".local" / "state")
    return overlay


def inherited_names_that_survive(
    overlay: Mapping[str, str],
    source_environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Names present in the parent that the overlay leaves at a real value.

    The merge the SDK performs is ``parent | overlay``, so this is the set of
    parent names the overlay neither overwrites nor blanks. It exists to be
    asserted on: the isolation claim is exactly "no name in
    :data:`NEUTRALISED_ENV_NAMES` appears here", and a claim nobody can check
    is not a control.
    """
    source = dict(os.environ if source_environment is None else source_environment)
    merged = {**source, **dict(overlay)}
    return tuple(
        sorted(
            name
            for name in NEUTRALISED_ENV_NAMES
            if merged.get(name, "") != ""
        )
    )


# ── Where a task's runtime may live ─────────────────────────────────────────
#
# There is no separate ``codex-linux-sandbox`` program. The sandbox helper is
# the ``codex`` binary itself under a different argv[0], and the runtime makes
# that possible at start-up by writing a directory of symlinks back to itself —
# ``codex-linux-sandbox``, ``codex-execve-wrapper``, ``apply_patch`` — under
# ``$CODEX_HOME/tmp/arg0/`` and putting that directory on the PATH its children
# inherit.
#
# It refuses to write them when ``CODEX_HOME`` is inside the process's own
# temporary directory, and says so on stderr:
#
#     WARNING: proceeding, even though we could not create PATH aliases:
#     Refusing to create helper binaries under temporary dir "/tmp"
#
# "Proceeding" is the trap. Start-up succeeds, a session opens, a turn runs, and
# nothing goes wrong until the agent first tries to execute something:
#
#     bwrap: execvp codex-linux-sandbox: No such file or directory
#
# Which reads like a machine with no working sandbox and is the opposite of one.
# bubblewrap started, took the namespace, and then could not find the program it
# had been told to run. Every task directory here was built with
# ``tempfile.mkdtemp()``, so ``CODEX_HOME`` was always under ``/tmp``, so the
# helper was never created — the execution leg could not have worked on any
# host, and on the hosts where the sandbox genuinely will not start the two
# causes were indistinguishable. This was found by running the end-to-end file
# on the one runner image measured able to sandbox, with skips turned into
# failures; on every other machine it had been a green skip.
#
# So per-task roots are made somewhere that is not the temporary directory.
#
# What is deliberately *not* done: pointing the child's ``TMPDIR`` at a
# directory inside the task would satisfy the same check, because
# ``std::env::temp_dir`` reads ``TMPDIR`` — and would leave the files exactly
# where they are. It is left alone for a second reason as well: Codex derives a
# writable sandbox carve-out from ``TMPDIR`` (its permission model names
# ``tmpdir`` and ``slash_tmp`` separately), so moving it changes what the agent
# is allowed to write, and nothing here has measured what that does.

#: Overrides where per-task roots are created. For a host whose home directory
#: is itself inside the temporary directory, and for anyone who wants the run
#: directories on a particular disk.
RUN_ROOT_ENV_NAME = "GDPVAL_CODEX_RUN_ROOT"

#: Appended to the cache directory when nothing overrides it.
RUN_ROOT_DIR_NAME = "gdpval-codex-runs"


class CodexRunRootError(RuntimeError):
    """There is nowhere to put a task's runtime that Codex will accept.

    Raised rather than falling back to the temporary directory. Falling back
    would restore exactly the failure this class exists to prevent, and would
    restore it silently — the run would start, and only the first command the
    agent tried to execute would go wrong.
    """


def system_temporary_directory(
    environment: Mapping[str, str] | None = None,
) -> Path:
    """What the Codex process will consider "the temporary directory".

    Rust's ``std::env::temp_dir`` on unix is ``$TMPDIR`` when that is set and
    non-empty, and ``/tmp`` otherwise. Python's :func:`tempfile.gettempdir`
    consults a longer list and would sometimes answer differently; the value
    that matters is the one the binary computes, not the one we would.
    """
    source = os.environ if environment is None else environment
    value = source.get("TMPDIR") or ""
    return Path(value) if value else Path("/tmp")


def path_is_within(
    child: str | os.PathLike[str], parent: str | os.PathLike[str]
) -> bool:
    """True when ``child`` is ``parent`` or sits under it, symlinks resolved.

    Resolved rather than compared as text because ``/tmp`` is a symlink on some
    systems, and a check that a symlink defeats is not a check.
    """
    try:
        resolved_child = Path(child).resolve()
        resolved_parent = Path(parent).resolve()
    except OSError:  # pragma: no cover - depends on the filesystem
        return False
    return (
        resolved_child == resolved_parent
        or resolved_parent in resolved_child.parents
    )


def resolve_run_root_base(
    environment: Mapping[str, str] | None = None,
) -> Path:
    """The directory per-task roots are made in. Never the temporary directory.

    In order: :data:`RUN_ROOT_ENV_NAME`, then ``XDG_CACHE_HOME``, then
    ``~/.cache``. Whatever is chosen is checked against
    :func:`system_temporary_directory` and refused if it is inside it, including
    when it was named explicitly — an override is a statement about *where*, not
    permission to reintroduce the fault.

    The directory is not created here. Callers make it, so that a caller which
    only wants to know the answer does not leave one behind.
    """
    source = dict(os.environ if environment is None else environment)
    temporary = system_temporary_directory(source)

    override = source.get(RUN_ROOT_ENV_NAME, "").strip()
    cache_home = source.get("XDG_CACHE_HOME", "").strip()
    home = source.get("HOME", "").strip()

    if override:
        candidate, chosen_because = Path(override), f"{RUN_ROOT_ENV_NAME}={override}"
    elif cache_home:
        candidate = Path(cache_home) / RUN_ROOT_DIR_NAME
        chosen_because = f"XDG_CACHE_HOME={cache_home}"
    elif home:
        candidate = Path(home) / ".cache" / RUN_ROOT_DIR_NAME
        chosen_because = f"HOME={home}"
    else:
        raise CodexRunRootError(
            "a Codex task needs a directory to live in and this process has no "
            f"HOME, no XDG_CACHE_HOME and no {RUN_ROOT_ENV_NAME}. The "
            "temporary directory is not a fallback: the runtime will not "
            "create its codex-linux-sandbox helper under one, and the agent "
            "would then be unable to execute anything."
        )

    if path_is_within(candidate, temporary):
        raise CodexRunRootError(
            f"{candidate} is inside the temporary directory {temporary}, and "
            "Codex refuses to create its codex-linux-sandbox helper under a "
            "temporary directory. A run started there would look healthy until "
            "the agent's first command failed with `bwrap: execvp "
            "codex-linux-sandbox: No such file or directory`. The candidate "
            f"came from {chosen_because}; set {RUN_ROOT_ENV_NAME} to a "
            f"directory outside {temporary}."
        )
    return candidate


# ── Provider settings ───────────────────────────────────────────────────────

#: The only wire format Codex's provider reference accepts. Kept as a constant
#: rather than inlined so the refusal below can name it.
SUPPORTED_WIRE_API = "responses"

#: The provider id we register under. Deliberately not a model name: pinning a
#: general contract to one GPT version is what the roadmap card rules out, so
#: the deployment goes in :attr:`CodexProviderSettings.model` and can change
#: without touching the provider.
DEFAULT_PROVIDER_ID = "gdpval-foundry"

_PROVIDER_ID_PATTERN = re.compile(r"\A[a-z0-9][a-z0-9-]{0,63}\Z")

#: How the provider gets a token. Codex runs this command and reads the token
#: from its stdout; ``core/codex_azure_token.py`` is that command, and it goes
#: through ``DefaultAzureCredential`` exactly as the rest of this repository
#: does. This is what lets the run place satisfy Codex's provider auth without
#: any of the static credentials in
#: ``core.azure_ai_clients.FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV``.
DEFAULT_AUTH_MODULE = "core.codex_azure_token"

#: Where the Azure CLI keeps its configuration and its signed-in accounts. The
#: CLI reads ``AZURE_CONFIG_DIR`` when it is set and falls back to this name
#: under ``HOME`` when it is not.
AZURE_CLI_CONFIG_DIR_NAME = ".azure"


def discover_azure_cli_config_dir(
    source_environment: Mapping[str, str] | None = None,
) -> str | None:
    """Find the Azure CLI sign-in this machine already has, or ``None``.

    This is read in the **parent** — the process that builds the Codex command
    line — because by the time the auth command runs there is nothing left to
    read it from. :func:`build_isolated_environment` rewrites ``HOME`` to the
    task's directory, and the CLI's sign-in is the one thing under the real
    ``HOME`` that the auth command genuinely needs. Passing the answer down as
    an argument is narrower than inheriting ``HOME``, and narrower than adding
    a name to :data:`INHERITED_ENV_NAMES`: the Codex process's own environment
    does not change at all, so neither does what the model's tools can see.

    ``None`` means "this machine has no Azure CLI sign-in to point at", which
    is the ordinary case on a runner authenticating some other way. The caller
    then omits the argument and ``DefaultAzureCredential`` behaves as before.
    """
    source = dict(os.environ if source_environment is None else source_environment)
    configured = source.get("AZURE_CONFIG_DIR", "").strip()
    if configured:
        return configured if Path(configured).is_dir() else None
    home = source.get("HOME", "").strip()
    if not home:
        return None
    candidate = Path(home) / AZURE_CLI_CONFIG_DIR_NAME
    return str(candidate) if candidate.is_dir() else None


#: Codex re-runs the auth command on this interval. Entra access tokens are
#: good for roughly an hour; refreshing well inside that avoids a long task
#: dying mid-turn on an expiry.
DEFAULT_AUTH_REFRESH_MS = 1_800_000

#: How long the auth command may take before Codex gives up on it.
DEFAULT_AUTH_TIMEOUT_MS = 30_000

#: Retries, pinned off. Both keys are per-provider settings of the pinned
#: 0.147.0 runtime -- they appear in its ``ModelProviderInfo`` field list and in
#: the published config reference, whose defaults are ``request_max_retries``
#: 4 and ``stream_max_retries`` 5.
#:
#: Leaving them unset is not "one request per turn". Measured against the
#: pinned binary and a local server that answers from a script, one turn sends:
#:
#:   ===================  =================  ============
#:   server answers       shipped defaults   pinned to 0
#:   ===================  =================  ============
#:   HTTP 500                 30 requests      1 request
#:   mid-stream disconnect     6 requests      1 request
#:   HTTP 429                  1 request       1 request
#:   HTTP 401                 12 requests     2 requests
#:   ===================  =================  ============
#:
#: 30 is the product the reference implies: 5 request attempts x 6 stream
#: attempts. It is the number that turns "one diagnostic turn" into thirty
#: billable calls against a real deployment, which is why these are pinned here
#: rather than described in a plan dictionary.
#:
#: The 401 row is the honest residue. Pinning takes it from 12 requests to 2,
#: not to 1: Codex re-runs the auth command once on an authentication failure
#: and retries with the fresh token, and neither counter binds that. The
#: reference says as much under ``auth.refresh_interval_ms`` -- "set to 0 to
#: refresh only after an authentication retry" -- so the retry exists by
#: design. There is no supported key that removes it. ``tests/
#: test_codex_retry_pins_are_enforced.py`` measures all four rows against the
#: real binary so the table cannot quietly stop being true.
DEFAULT_REQUEST_MAX_RETRIES = 0
DEFAULT_STREAM_MAX_RETRIES = 0

#: What one 401 costs even with both counters at 0, measured rather than
#: reasoned about. Exported so the diagnostic can state the bound instead of
#: claiming a zero it does not have.
AUTH_RETRY_REQUESTS_NOT_REMOVED_BY_PINNING = 2


class CodexProviderConfigurationError(ValueError):
    """A provider setting is missing, malformed, or forbidden here."""


#: The experiment-file key that says the address comes from this run's Azure
#: route, the same one every other Azure caller in this repository derives.
#: It holds ``true``, never an address and never a variable name.
ENDPOINT_FROM_ROUTE_KEY = "endpoint_from_route"

#: The experiment-file key that holds the endpoint literally. Every other run
#: place in this repository takes its address this way, and so may this one on
#: a machine where the address is not a secret.
ENDPOINT_LITERAL_KEY = "endpoint"


def select_endpoint_source(block: Mapping[str, Any] | None) -> str | None:
    """The address this block names, or ``None`` if it defers to the route.

    Everything decided here is a property of the file, so it answers the same
    on a machine holding this run's Azure route and on one that does not. That
    separation is the point: :func:`resolve_endpoint_setting` used to make both
    decisions at once, and callers who only had the file in hand were made to
    prove they had the run place's credentials as well.

    A block may carry ``endpoint`` *or* ``endpoint_from_route``, and exactly
    one of them. Not neither, and not both:

    * neither, and there is nothing to call;
    * both, and the file has two answers to one question, which is worth
      refusing rather than resolving by precedence — a precedence rule is
      invisible in review, and the loser would be a plausible-looking address
      that never gets used.
    """
    if not isinstance(block, Mapping):
        raise CodexProviderConfigurationError(
            "codex_foundry needs an execution.codex block naming the "
            "deployment and its address"
        )
    literal = str(block.get(ENDPOINT_LITERAL_KEY) or "").strip()
    from_route = bool(block.get(ENDPOINT_FROM_ROUTE_KEY))
    if literal and from_route:
        raise CodexProviderConfigurationError(
            f"execution.codex sets both {ENDPOINT_LITERAL_KEY} and "
            f"{ENDPOINT_FROM_ROUTE_KEY}; set exactly one, so the file has one "
            "answer for which deployment is called"
        )
    if not literal and not from_route:
        raise CodexProviderConfigurationError(
            f"execution.codex needs {ENDPOINT_LITERAL_KEY} or "
            f"{ENDPOINT_FROM_ROUTE_KEY}; neither is set, so there is no "
            "deployment to call"
        )
    return literal or None


#: A deferred block is contractually an undated ``/openai/v1/`` address:
#: :func:`resolve_endpoint_setting` returns ``route.direct_v1.url`` or raises,
#: so no branch of it yields a project or a dated legacy endpoint. This URL
#: stands in for that certainty while the *rest* of a deferred block is
#: checked, which is what lets that check still enforce the ``api-version``
#: rule — the one setting whose legality depends on the endpoint's kind. It
#: names no resource, is discarded inside the function below, and is never
#: returned, stored or sent anywhere.
_THE_SHAPE_A_ROUTE_MUST_PRODUCE = "https://route.services.ai.azure.com/openai/v1/"


def check_block_apart_from_its_address(block: Mapping[str, Any]) -> None:
    """Raise if a route-deferred ``execution.codex`` block is wrong about
    anything the file itself decides.

    The address is the run place's rather than the file's, so a process that
    holds only the file cannot check it and should not pretend to. Everything
    the *file* decides about the provider is still checked here: the deployment
    name, the provider id, and the query parameters' names, types and the
    ``api-version`` prohibition.

    This exists because the eager version cost a dispatch. ``batch-run.yml``
    validates the experiment file in an early step that deliberately holds no
    credentials — it runs before the gate that decides whether the dispatch may
    spend at all — and resolving the address there failed with "this
    environment describes no usable Azure route" on a run whose route was
    present three steps later. The check was not wrong about the environment it
    was given; it was asking the wrong process.

    Nothing is skipped as a result. ``step2_run_inference`` resolves the real
    address where the route exists and exits before the first turn if it
    cannot, so a run whose address is missing still stops before it spends.
    """
    CodexProviderSettings(
        endpoint=_THE_SHAPE_A_ROUTE_MUST_PRODUCE,
        model=str(block.get("model", "")),
        provider_id=str(block.get("provider_id") or DEFAULT_PROVIDER_ID),
        query_params=dict(block.get("query_params") or {}),
    )


def resolve_endpoint_setting(
    block: Mapping[str, Any] | None,
    environ: Mapping[str, str],
) -> str:
    """Read the deployment address out of an ``execution.codex`` block.

    This exists because of a collision between two things that are both true:
    ``CodexProviderSettings`` needs a literal address, and this deployment's
    address is a secret that cannot be committed to a public repository. Every
    other run place here resolves that by taking the address from the
    environment at run time; this one had no way to say so, which is why no
    experiment file could name this mode at all.

    ``endpoint_from_route: true`` is that way of saying so, and it deliberately
    names nothing. An earlier version of this function took an ``endpoint_env``
    key holding the *name* of an environment variable, which would have been a
    new variable and a new secret for an address this repository already knows
    how to find: ``scripts/diagnose_codex_foundry_connection.py`` derives it
    with :meth:`AzureAIRouteSettings.from_env`, and that is the derivation the
    one answered turn used. A second way to reach the same address is a second
    thing to keep in agreement, and it would also let an experiment file point
    a run at some other resource without changing any code — which is exactly
    what "the confirmed Foundry resource only" rules out.

    Which of the two ways a block uses is :func:`select_endpoint_source`'s
    question, and it is a question about the file. This function answers the
    one that follows and is about the run place: given that the file defers,
    what address does *this* environment provide? Callers holding only the file
    should ask the first and not this one.

    A route that describes no ``/openai/v1/`` endpoint is an error, not an
    empty string. Falling through to ``""`` would reach
    ``CodexProviderSettings`` as a missing-endpoint failure with no mention of
    where the address was supposed to come from, which is the same class of
    mistake as the empty bearer token: a silent absence reported as something
    else.

    The value is deliberately *not* stored anywhere by its callers. It is
    resolved at the point of use, so it never reaches
    ``workspace/step1_tasks_prepared.json`` or any other file this run writes
    down.
    """
    literal = select_endpoint_source(block)
    if literal is not None:
        return literal
    try:
        route = AzureAIRouteSettings.from_env(environ)
    except ValueError as exc:
        raise CodexProviderConfigurationError(
            f"execution.codex.{ENDPOINT_FROM_ROUTE_KEY} is set, but this "
            f"environment describes no usable Azure route: {exc}"
        ) from None
    if route.direct_v1 is None:
        raise CodexProviderConfigurationError(
            f"execution.codex.{ENDPOINT_FROM_ROUTE_KEY} is set, but this "
            "environment describes no direct /openai/v1/ endpoint; the dated "
            "legacy route is a different contract rather than a fallback"
        )
    return route.direct_v1.url


class CodexProviderLike:
    """The three things :class:`core.codex_runner.CodexAgentRunner` asks of a
    provider description: which deployment to name, which provider table to
    name it in, and the ``--config`` arguments that define that table.

    There are exactly two implementations and they are not interchangeable.
    :class:`CodexProviderSettings` describes a real Microsoft endpoint and is
    the only one any production path can construct.
    :class:`LoopbackCodexProvider` cannot describe anything except a server on
    this machine, which is what lets the end-to-end check drive the real
    runtime without a paid deployment.

    The base class exists so that distinction is a type rather than a flag. A
    boolean like ``allow_insecure_endpoint`` on the real settings class would
    put the loopback path one wrong argument away from production; a separate
    class that is structurally incapable of naming a remote host does not.
    """

    #: The deployment to ask for. Set by each subclass.
    model: str
    #: The provider table's key in Codex's config.
    provider_id: str

    def config_overrides(self) -> tuple[str, ...]:
        """The ``--config key=value`` arguments defining this provider."""
        raise NotImplementedError

    def extra_environment(self) -> Mapping[str, str]:
        """Names to add to the isolated environment for this provider.

        Empty for the real settings, which authenticate with a command rather
        than a variable. The runner refuses to merge any name the isolation
        blanks or the repository forbids, so this cannot become a way back in
        for a static Azure credential.
        """
        return {}


@dataclass(frozen=True)
class CodexProviderSettings(CodexProviderLike):
    """One Foundry deployment, described the way Codex describes providers.

    ``endpoint`` is checked by the repository's own
    :func:`core.azure_ai_clients.classify_endpoint`, so this run place accepts
    exactly the endpoint shapes every other Azure caller here accepts — no
    wider, and with the same rejection of IP literals, ports, query strings and
    non-Microsoft hosts.
    """

    endpoint: str
    model: str
    provider_id: str = DEFAULT_PROVIDER_ID
    #: Extra query string items on every request. This is the documented place
    #: for a dated ``api-version``. Left empty for the undated ``/openai/v1/``
    #: route, where a dated value would be wrong rather than merely redundant.
    query_params: Mapping[str, str] = field(default_factory=dict)
    auth_module: str = DEFAULT_AUTH_MODULE
    auth_scope: str = DIRECT_TOKEN_SCOPE
    auth_refresh_interval_ms: int = DEFAULT_AUTH_REFRESH_MS
    auth_timeout_ms: int = DEFAULT_AUTH_TIMEOUT_MS
    #: Retries on a refused or dropped request. Both default to 0; see the
    #: measured table beside :data:`DEFAULT_REQUEST_MAX_RETRIES` for what the
    #: runtime does when they are left unset.
    #:
    #: 0 is the right default for a diagnostic, where the cost of one turn has
    #: to be a known quantity. It is not obviously right for a 220-task batch,
    #: where a transient 500 would now fail a task instead of being retried.
    #: That is a decision for whoever turns the batch leg on, and this default
    #: is set so the decision has to be made rather than inherited: a caller
    #: that wants retries passes a number, and the number is in the settings
    #: fingerprint, so the record says which run had them.
    request_max_retries: int = DEFAULT_REQUEST_MAX_RETRIES
    stream_max_retries: int = DEFAULT_STREAM_MAX_RETRIES
    python_executable: str | None = None

    def __post_init__(self) -> None:
        if not _PROVIDER_ID_PATTERN.match(self.provider_id):
            raise CodexProviderConfigurationError(
                "Codex provider id must be lower-case letters, digits and "
                f"hyphens; got {self.provider_id!r}"
            )
        if not isinstance(self.model, str) or not self.model.strip():
            raise CodexProviderConfigurationError(
                "a Codex provider needs the deployment to call; none was given"
            )
        try:
            classified = classify_endpoint(self.endpoint)
        except ValueError as exc:
            raise CodexProviderConfigurationError(
                f"Codex provider endpoint is not a supported Microsoft "
                f"endpoint: {exc}"
            ) from None
        if classified.kind is EndpointKind.PROJECT:
            raise CodexProviderConfigurationError(
                "a Foundry project endpoint has no OpenAI-shaped path for "
                "Codex to post to; give the account's /openai/v1/ endpoint "
                "instead"
            )
        object.__setattr__(self, "endpoint", classified.url)

        for key, value in dict(self.query_params).items():
            if not isinstance(key, str) or not key.strip():
                raise CodexProviderConfigurationError(
                    "a Codex provider query parameter needs a name"
                )
            if not isinstance(value, str):
                raise CodexProviderConfigurationError(
                    f"the query parameter {key!r} must be a string"
                )
        if (
            classified.kind is EndpointKind.DIRECT_V1
            and "api-version" in dict(self.query_params)
        ):
            raise CodexProviderConfigurationError(
                "the /openai/v1/ endpoint is the undated contract, in which "
                "the request's model argument names the deployment; a dated "
                "api-version belongs to the legacy route and setting it here "
                "would describe a route we are not using"
            )
        if self.auth_refresh_interval_ms <= 0 or self.auth_timeout_ms <= 0:
            raise CodexProviderConfigurationError(
                "Codex provider auth timings must be positive milliseconds"
            )
        for name in ("request_max_retries", "stream_max_retries"):
            value = getattr(self, name)
            # ``bool`` is an ``int``, and ``_toml_literal`` renders it as
            # ``true``. A provider table carrying ``request_max_retries=true``
            # is a type error the runtime reports about a config file the
            # operator never wrote, so it is refused here where it is legible.
            if isinstance(value, bool) or not isinstance(value, int):
                raise CodexProviderConfigurationError(
                    f"Codex provider {name} must be a whole number of retries; "
                    f"got {value!r}"
                )
            if value < 0:
                raise CodexProviderConfigurationError(
                    f"Codex provider {name} cannot be negative; got {value!r}"
                )

    @property
    def base_url(self) -> str:
        """The provider ``base_url``, without the trailing slash Codex adds."""
        return self.endpoint.rstrip("/")

    def auth_command(
        self, source_environment: Mapping[str, str] | None = None
    ) -> list[str]:
        """The command Codex runs to get a token, as argv.

        It prints one Entra access token to stdout and nothing else — see
        ``core/codex_azure_token.py``. Passing a command rather than a key is
        what keeps this run place inside the repository's rule that no static
        Azure credential exists in any environment we build.

        When this machine has an Azure CLI sign-in, its location is appended as
        ``--azure-config-dir``. Codex runs this command inside the isolated
        environment, where ``HOME`` no longer points at that sign-in; without
        the argument the mint fails, the command prints nothing by design, and
        Codex sends an empty bearer that the gateway rejects as an invalid
        subscription key. The argument is a path, not a credential, and it goes
        to this command alone — the Codex process's environment is untouched.
        """
        import sys

        executable = self.python_executable or sys.executable
        argv = [executable, *self.auth_entrypoint(), "--scope", self.auth_scope]
        config_dir = discover_azure_cli_config_dir(source_environment)
        if config_dir:
            argv += ["--azure-config-dir", config_dir]
        return argv

    def auth_entrypoint(self) -> list[str]:
        """How to name the auth module to an interpreter, as argv fragments.

        A file path when one can be resolved, because Codex starts the auth
        command with the *task's* directory as its working directory — see
        ``CodexConfig.cwd`` in :meth:`core.codex_runner.CodexAgentRunner.
        open_runtime`, which the pinned SDK passes straight to ``Popen``. From
        there ``-m core.codex_azure_token`` raises ``No module named 'core'``
        before the module's first line runs, and the command exits with an
        empty stdout that Codex forwards as an empty bearer.

        ``-m`` remains the fallback for a module that cannot be resolved to a
        file, which is how the tests point this at a stub on ``PYTHONPATH``.
        """
        try:
            spec = importlib.util.find_spec(self.auth_module)
        except (ImportError, ValueError, AttributeError):
            spec = None
        origin = getattr(spec, "origin", None)
        if origin and origin.endswith(".py") and Path(origin).is_file():
            # Resolved, because the recorded argv is read by people comparing
            # one run's configuration with another's, and ``a/./b`` and ``a/b``
            # are the same file wearing two names.
            return [str(Path(origin).resolve())]
        return ["-m", self.auth_module]

    def config_overrides(self) -> tuple[str, ...]:
        """The provider table for this deployment, as command-line overrides."""
        return provider_config_overrides(self)


#: The value handed to the loopback provider's ``env_key``. Codex requires
#: *some* credential source for a provider it authenticates by variable, and
#: the stand-in server ignores what arrives; naming it this way makes an
#: accidental appearance in a log obviously not a key.
LOOPBACK_PLACEHOLDER_KEY = "loopback-stand-in-not-a-credential"


@dataclass(frozen=True)
class LoopbackCodexProvider(CodexProviderLike):
    """A provider that can only point at a Responses server on this machine.

    This is what makes the mock end-to-end check possible without weakening
    anything. :class:`CodexProviderSettings` will not accept a loopback address
    — it runs the repository's own endpoint classifier, which rejects IP
    literals, ports and non-Microsoft hosts — and that refusal is worth
    keeping. So the stand-in gets its own class which inverts the rule: it
    takes a port and nothing else, and builds ``http://127.0.0.1:<port>/v1``
    itself, so no value it can be constructed with reaches the network.

    Everything downstream of the provider is the same object in both cases:
    the same runner, the same isolated environment, the same real SDK, the same
    real ``codex`` binary, the same JSON-RPC session. Only the URL in the
    provider table differs.
    """

    port: int
    model: str = "gdpval-loopback-model"
    provider_id: str = "gdpval-loopback"
    #: The variable Codex reads the provider's credential from. A name, not a
    #: value; the value is :data:`LOOPBACK_PLACEHOLDER_KEY`.
    env_key_name: str = "GDPVAL_CODEX_LOOPBACK_KEY"

    def __post_init__(self) -> None:
        if not isinstance(self.port, int) or isinstance(self.port, bool):
            raise CodexProviderConfigurationError(
                "the loopback provider needs the port its server is listening "
                f"on; got {self.port!r}"
            )
        if not 1 <= self.port <= 65535:
            raise CodexProviderConfigurationError(
                f"{self.port} is not a port number"
            )
        if not _PROVIDER_ID_PATTERN.match(self.provider_id):
            raise CodexProviderConfigurationError(
                "Codex provider id must be lower-case letters, digits and "
                f"hyphens; got {self.provider_id!r}"
            )
        if not isinstance(self.model, str) or not self.model.strip():
            raise CodexProviderConfigurationError(
                "a Codex provider needs the deployment to call; none was given"
            )
        blanked = set(NEUTRALISED_ENV_NAMES) | set(
            FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV
        )
        if self.env_key_name in blanked:
            raise CodexProviderConfigurationError(
                f"{self.env_key_name} is a name this repository blanks or "
                "forbids; the loopback stand-in may not reuse it"
            )

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def config_overrides(self) -> tuple[str, ...]:
        prefix = f"model_providers.{self.provider_id}"
        return (
            f"{prefix}.name={_toml_literal(self.provider_id)}",
            f"{prefix}.base_url={_toml_literal(self.base_url)}",
            f"{prefix}.wire_api={_toml_literal(SUPPORTED_WIRE_API)}",
            f"{prefix}.env_key={_toml_literal(self.env_key_name)}",
        )

    def extra_environment(self) -> Mapping[str, str]:
        return {self.env_key_name: LOOPBACK_PLACEHOLDER_KEY}


def _toml_literal(value: object) -> str:
    """Render one value the way the Codex CLI's ``--config`` parser reads it.

    The CLI parses each ``--config key=value`` right-hand side as a TOML value,
    so a string has to arrive quoted and a number must not be. Basic strings
    with the standard escapes are enough for everything we pass.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_literal(item) for item in value) + "]"
    raise CodexProviderConfigurationError(
        f"cannot render {type(value).__name__} as a Codex config value"
    )


def provider_config_overrides(
    settings: CodexProviderSettings,
) -> tuple[str, ...]:
    """Build the ``--config key=value`` arguments that define the provider.

    These go on the Codex command line, which matters for a reason that is easy
    to miss: Codex ignores provider, credential and telemetry settings found in
    a *repository-local* config file, on purpose, so that checking a config
    into a repository cannot redirect somebody's agent. A provider table
    committed under this repository would therefore be inert. Passing the same
    table as command-line overrides is the supported way to configure a
    provider for one run without touching the operator's own config.
    """
    prefix = f"model_providers.{settings.provider_id}"
    argv = settings.auth_command()
    overrides: list[str] = [
        f"{prefix}.name={_toml_literal(settings.provider_id)}",
        f"{prefix}.base_url={_toml_literal(settings.base_url)}",
        f"{prefix}.wire_api={_toml_literal(SUPPORTED_WIRE_API)}",
        f"{prefix}.auth.command={_toml_literal(argv[0])}",
        f"{prefix}.auth.args={_toml_literal(list(argv[1:]))}",
        f"{prefix}.auth.timeout_ms={_toml_literal(settings.auth_timeout_ms)}",
        f"{prefix}.auth.refresh_interval_ms="
        f"{_toml_literal(settings.auth_refresh_interval_ms)}",
        # Emitted always, including at the default 0. An unset key is not a
        # zero here: the runtime falls back to 4 and 5, which is up to thirty
        # requests for one turn.
        f"{prefix}.request_max_retries="
        f"{_toml_literal(settings.request_max_retries)}",
        f"{prefix}.stream_max_retries="
        f"{_toml_literal(settings.stream_max_retries)}",
    ]
    for key, value in sorted(dict(settings.query_params).items()):
        overrides.append(
            f"{prefix}.query_params.{key}={_toml_literal(value)}"
        )
    return tuple(overrides)


def describe_provider(settings: CodexProviderSettings) -> dict[str, object]:
    """A printable summary of the provider, carrying no secret.

    The auth command appears as argv because that is a path and a scope, not a
    credential; the token it prints never passes through this process.
    """
    return {
        "provider_id": settings.provider_id,
        "base_url": settings.base_url,
        "wire_api": SUPPORTED_WIRE_API,
        "model": settings.model,
        "query_params": dict(settings.query_params),
        "auth_command": settings.auth_command(),
        "auth_scope": settings.auth_scope,
        "request_max_retries": settings.request_max_retries,
        "stream_max_retries": settings.stream_max_retries,
        "endpoint_kind": classify_endpoint(settings.endpoint).kind.value,
    }
