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

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from core.azure_ai_clients import (
    DIRECT_TOKEN_SCOPE,
    FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV,
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

#: Codex re-runs the auth command on this interval. Entra access tokens are
#: good for roughly an hour; refreshing well inside that avoids a long task
#: dying mid-turn on an expiry.
DEFAULT_AUTH_REFRESH_MS = 1_800_000

#: How long the auth command may take before Codex gives up on it.
DEFAULT_AUTH_TIMEOUT_MS = 30_000


class CodexProviderConfigurationError(ValueError):
    """A provider setting is missing, malformed, or forbidden here."""


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

    @property
    def base_url(self) -> str:
        """The provider ``base_url``, without the trailing slash Codex adds."""
        return self.endpoint.rstrip("/")

    def auth_command(self) -> list[str]:
        """The command Codex runs to get a token, as argv.

        It prints one Entra access token to stdout and nothing else — see
        ``core/codex_azure_token.py``. Passing a command rather than a key is
        what keeps this run place inside the repository's rule that no static
        Azure credential exists in any environment we build.
        """
        import sys

        executable = self.python_executable or sys.executable
        return [executable, "-m", self.auth_module, "--scope", self.auth_scope]

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
        "endpoint_kind": classify_endpoint(settings.endpoint).kind.value,
    }
