"""Typed Microsoft Foundry and Azure OpenAI client routing.

Authentication is based on ``DefaultAzureCredential``. Known static Azure
credential environment variables are rejected before any client is built.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
import ipaddress
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from core.cost_metering import ROUTE_IDENTITY_ATTRIBUTE, RouteCallIdentity

DIRECT_TOKEN_SCOPE = "https://ai.azure.com/.default"
LEGACY_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
DEFAULT_TIMEOUT = 480.0
DEFAULT_LEGACY_API_VERSION = "2025-04-01-preview"
ROUTE_FINGERPRINT_CONTRACT_VERSION = "azure-ai-route-v1"

#: What a cost receipt can be told about a call made over the undated v1 route.
#:
#: The endpoint is pinned to ``https://{account}.openai.azure.com/openai/v1/``
#: by :func:`_classify_endpoint`, and it is reached through the plain ``OpenAI``
#: class — which is why nothing about it can be read back off the client. Both
#: facts below are properties of that URL, fixed at classification time:
#: ``/openai/v1/`` routes by the request's ``model`` argument, and it is Azure
#: OpenAI's undated v1 contract rather than a dated ``api-version``.
DIRECT_V1_CALL_IDENTITY = RouteCallIdentity(
    model_argument_names_deployment=True,
    api_version="v1",
)

FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV = (
    "AZURE_OPENAI_API_KEY",
    "AZURE_API_KEY",
    "AZURE_AI_API_KEY",
    "AZURE_AI_PROJECT_API_KEY",
    "AZURE_OPENAI_AD_TOKEN",
    "AZURE_CLIENT_SECRET",
    "AZURE_CLIENT_CERTIFICATE_PATH",
    "AZURE_CLIENT_CERTIFICATE_PASSWORD",
    "AZURE_USERNAME",
    "AZURE_PASSWORD",
)
FORBIDDEN_API_KEY_ENV = FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV

# The environment variables that decide which route is built and which
# resource it is allowed to reach.
#
# These live at module scope, rather than as string literals inside the
# functions that read them, so that a check wanting to report the same
# requirement up front can read the names from here instead of retyping them. A
# retyped copy agrees until somebody edits one of the two, and then the check
# that was meant to give early warning gives a clean answer about a setting the
# run refuses.
ROUTE_PROFILE_ENV = "AZURE_AI_ROUTE_PROFILE"
DIRECT_ENDPOINT_ENV = "AZURE_OPENAI_V1_ENDPOINT"
PROJECT_ENDPOINT_ENV = "FOUNDRY_PROJECT_ENDPOINT"
LEGACY_ENDPOINT_ENV = "AZURE_OPENAI_LEGACY_ENDPOINT"
DEPRECATED_ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
ALLOW_LEGACY_ROLLBACK_ENV = "AZURE_AI_ALLOW_LEGACY_ROLLBACK"

EXPECTED_DIRECT_ACCOUNT_ENV = "AZURE_AI_EXPECTED_DIRECT_ACCOUNT"
EXPECTED_PROJECT_ACCOUNT_ENV = "AZURE_AI_EXPECTED_PROJECT_ACCOUNT"
EXPECTED_PROJECT_NAME_ENV = "AZURE_AI_EXPECTED_PROJECT_NAME"
EXPECTED_LEGACY_ACCOUNT_ENV = "AZURE_AI_EXPECTED_LEGACY_ACCOUNT"

# Which endpoint identities must be named before a route is built, per profile,
# when AZURE_AI_REQUIRE_EXPECTED_IDENTITIES is "1". Keyed by the profile's
# written value, so a reader that only has the string can look it up without
# importing the enumeration.
#
# For every profile these are also exactly the identities
# ``_verify_expected_identities`` compares against the endpoints, so a checker
# reading this table learns both which names must be present and which names
# are acted on.
REQUIRE_EXPECTED_IDENTITIES_ENV = "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES"
REQUIRED_IDENTITY_ENV_BY_PROFILE: Mapping[str, tuple[str, ...]] = {
    "direct-v1": (EXPECTED_DIRECT_ACCOUNT_ENV,),
    "project-ci": (
        EXPECTED_DIRECT_ACCOUNT_ENV,
        EXPECTED_PROJECT_ACCOUNT_ENV,
        EXPECTED_PROJECT_NAME_ENV,
    ),
    "legacy-rollback": (EXPECTED_LEGACY_ACCOUNT_ENV,),
}

_AZURE_PROVIDER_ALIASES = frozenset({"azure", "azure_openai"})
_PREPROCESSOR_DEFAULT_DEPLOYMENTS = {
    "audio_analyzer": "gpt-audio-1.5",
    "video_analyzer": "gpt-5.2",
}

_ACCOUNT_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)
_PROJECT_PATTERN = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?"
)


def DefaultAzureCredential(*args, **kwargs):
    from azure.identity import DefaultAzureCredential as Credential

    return Credential(*args, **kwargs)


def get_bearer_token_provider(*args, **kwargs):
    from azure.identity import get_bearer_token_provider as provider_factory

    return provider_factory(*args, **kwargs)


def OpenAI(*args, **kwargs):
    from openai import OpenAI as Client

    return Client(*args, **kwargs)


def AzureOpenAI(*args, **kwargs):
    from openai import AzureOpenAI as Client

    return Client(*args, **kwargs)


class EndpointKind(str, Enum):
    DIRECT_V1 = "direct-v1"
    PROJECT = "project"
    LEGACY_DATED = "legacy-dated"


class RouteProfile(str, Enum):
    DIRECT_V1 = "direct-v1"
    PROJECT_CI = "project-ci"
    LEGACY_ROLLBACK = "legacy-rollback"


class AzureAIWorkload(str, Enum):
    INFERENCE = "inference"
    CODE_INTERPRETER = "code-interpreter"
    NARRATIVE = "narrative"
    GRADER = "grader"


@dataclass(frozen=True)
class ClassifiedEndpoint:
    kind: EndpointKind
    url: str = field(repr=False)
    account: str
    project: str | None = None


@dataclass(frozen=True)
class RouteSelection:
    profile: RouteProfile
    workload: AzureAIWorkload
    endpoint: ClassifiedEndpoint
    token_scope: str


def _validate_account(account: str) -> str:
    normalized = account.lower()
    if not _ACCOUNT_PATTERN.fullmatch(normalized):
        raise ValueError("Azure AI endpoint account name is invalid")
    return normalized


def _validate_project(project: str) -> str:
    if not _PROJECT_PATTERN.fullmatch(project):
        raise ValueError("Foundry project name is invalid")
    return project


def _validate_hostname(hostname: str) -> str:
    host = hostname.lower()
    if host.endswith("."):
        raise ValueError("Azure AI endpoint hostname is invalid")
    if host == "localhost":
        raise ValueError("Azure AI endpoint must not use localhost")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Azure AI endpoint must not use an IP address")
    return host


def _resource_account(host: str, suffix: str) -> str | None:
    marker = f".{suffix}"
    if not host.endswith(marker):
        return None
    return _validate_account(host[: -len(marker)])


def classify_endpoint(value: str) -> ClassifiedEndpoint:
    """Classify and canonicalize one supported Microsoft endpoint shape."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Azure AI endpoint is required")
    if any(
        ord(character) < 0x20
        or 0x7F <= ord(character) <= 0x9F
        or character in {"\u2028", "\u2029"}
        for character in value
    ):
        raise ValueError("Azure AI endpoint contains control characters")
    if not value.isascii():
        raise ValueError("Azure AI endpoint must contain ASCII characters only")
    raw = value.strip()
    if "\\" in raw:
        raise ValueError("Azure AI endpoint contains an invalid path separator")
    if "?" in raw or "#" in raw:
        raise ValueError("Azure AI endpoint must not contain query or fragment data")

    try:
        parsed = urlsplit(raw)
    except ValueError:
        raise ValueError("Azure AI endpoint URL is invalid") from None
    if parsed.scheme != "https":
        raise ValueError("Azure AI endpoint must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Azure AI endpoint must not contain user information")
    if parsed.netloc.rsplit("@", 1)[-1].endswith(":"):
        raise ValueError("Azure AI endpoint port must not be empty")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Azure AI endpoint port is invalid") from None
    if port not in (None, 443):
        raise ValueError("Azure AI endpoint must use HTTPS port 443")
    if not parsed.hostname:
        raise ValueError("Azure AI endpoint hostname is missing")

    host = _validate_hostname(parsed.hostname)
    path = parsed.path
    if "%" in path:
        raise ValueError("Azure AI endpoint path must not use percent encoding")

    openai_account = _resource_account(host, "openai.azure.com")
    services_account = _resource_account(host, "services.ai.azure.com")

    if path in ("/openai/v1", "/openai/v1/"):
        account = openai_account or services_account
        if account is not None:
            return ClassifiedEndpoint(
                kind=EndpointKind.DIRECT_V1,
                url=f"https://{host}/openai/v1/",
                account=account,
            )

    project_match = re.fullmatch(r"/api/projects/([^/]+)/?", path)
    if project_match is not None and services_account is not None:
        project = _validate_project(project_match.group(1))
        return ClassifiedEndpoint(
            kind=EndpointKind.PROJECT,
            url=f"https://{host}/api/projects/{project}",
            account=services_account,
            project=project,
        )

    if path in ("", "/") and openai_account is not None:
        return ClassifiedEndpoint(
            kind=EndpointKind.LEGACY_DATED,
            url=f"https://{host}/",
            account=openai_account,
        )

    raise ValueError("Azure AI endpoint shape or Microsoft host kind is unsupported")


def _env_value(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value.strip()


def _reject_static_azure_credential_env(env: Mapping[str, str]) -> None:
    forbidden = [
        name
        for name in FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV
        if env.get(name)
    ]
    if forbidden:
        raise ValueError(
            "static Azure credential environment variables are forbidden: "
            + ", ".join(forbidden)
        )


def _classify_typed_endpoint(
    env: Mapping[str, str],
    variable: str,
    required_kind: EndpointKind,
) -> ClassifiedEndpoint | None:
    raw = _env_value(env, variable)
    if not raw:
        return None
    endpoint = classify_endpoint(raw)
    if endpoint.kind is not required_kind:
        raise ValueError(
            f"{variable} must contain a {required_kind.value} endpoint"
        )
    return endpoint


def _deprecated_endpoint_error(raw: str) -> ValueError:
    try:
        kind = classify_endpoint(raw).kind
    except ValueError:
        return ValueError(
            f"{DEPRECATED_ENDPOINT_ENV} is deprecated and must be unset; use "
            "the typed endpoint variable for the required endpoint kind"
        )
    variable = {
        EndpointKind.DIRECT_V1: DIRECT_ENDPOINT_ENV,
        EndpointKind.PROJECT: PROJECT_ENDPOINT_ENV,
        EndpointKind.LEGACY_DATED: LEGACY_ENDPOINT_ENV,
    }[kind]
    return ValueError(
        f"{DEPRECATED_ENDPOINT_ENV} is deprecated and must be unset; move the "
        f"{kind.value} endpoint to {variable}"
    )


@dataclass(frozen=True)
class AzureAIRouteSettings:
    profile: RouteProfile
    direct_v1: ClassifiedEndpoint | None = None
    project: ClassifiedEndpoint | None = None
    legacy: ClassifiedEndpoint | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AzureAIRouteSettings":
        values = os.environ if env is None else env
        _reject_static_azure_credential_env(values)

        raw_profile = _env_value(values, ROUTE_PROFILE_ENV)
        if not raw_profile:
            raise ValueError(f"{ROUTE_PROFILE_ENV} is required")
        try:
            profile = RouteProfile(raw_profile)
        except ValueError:
            raise ValueError(f"{ROUTE_PROFILE_ENV} is unsupported") from None

        deprecated = _env_value(values, DEPRECATED_ENDPOINT_ENV)
        if deprecated:
            raise _deprecated_endpoint_error(deprecated)

        direct = _classify_typed_endpoint(
            values,
            DIRECT_ENDPOINT_ENV,
            EndpointKind.DIRECT_V1,
        )
        project = _classify_typed_endpoint(
            values,
            PROJECT_ENDPOINT_ENV,
            EndpointKind.PROJECT,
        )
        legacy = _classify_typed_endpoint(
            values,
            LEGACY_ENDPOINT_ENV,
            EndpointKind.LEGACY_DATED,
        )

        if direct is None and project is not None:
            direct = ClassifiedEndpoint(
                kind=EndpointKind.DIRECT_V1,
                url=(
                    f"https://{project.account}.services.ai.azure.com/"
                    "openai/v1/"
                ),
                account=project.account,
            )

        if profile is RouteProfile.DIRECT_V1 and direct is None:
            raise ValueError("direct-v1 profile requires a direct-v1 endpoint")
        if profile is RouteProfile.PROJECT_CI and (
            direct is None or project is None
        ):
            raise ValueError(
                "project-ci profile requires direct-v1 and project endpoints"
            )
        if profile is RouteProfile.LEGACY_ROLLBACK:
            if _env_value(values, ALLOW_LEGACY_ROLLBACK_ENV) != "1":
                raise ValueError("legacy rollback is not explicitly authorized")
            if legacy is None:
                raise ValueError(
                    "legacy-rollback profile requires a legacy-dated endpoint"
                )

        settings = cls(
            profile=profile,
            direct_v1=direct,
            project=project,
            legacy=legacy,
        )
        settings._verify_expected_identities(values)
        settings._require_expected_identities(values)
        return settings

    def _require_expected_identities(self, env: Mapping[str, str]) -> None:
        if _env_value(env, REQUIRE_EXPECTED_IDENTITIES_ENV) != "1":
            return
        required = REQUIRED_IDENTITY_ENV_BY_PROFILE[self.profile.value]
        missing = [name for name in required if not _env_value(env, name)]
        if missing:
            raise ValueError(
                "required Azure AI endpoint identities are missing: "
                + ", ".join(missing)
            )

    def _verify_expected_identities(self, env: Mapping[str, str]) -> None:
        if self.profile in (RouteProfile.DIRECT_V1, RouteProfile.PROJECT_CI):
            expected_direct = _env_value(env, EXPECTED_DIRECT_ACCOUNT_ENV)
            if expected_direct:
                expected_direct = _validate_account(expected_direct)
                if (
                    self.direct_v1 is None
                    or self.direct_v1.account != expected_direct
                ):
                    raise ValueError("direct endpoint account identity mismatch")

        if self.profile is RouteProfile.PROJECT_CI:
            expected_project_account = _env_value(
                env, EXPECTED_PROJECT_ACCOUNT_ENV
            )
            if expected_project_account:
                expected_project_account = _validate_account(
                    expected_project_account
                )
                if (
                    self.project is None
                    or self.project.account != expected_project_account
                ):
                    raise ValueError("project endpoint account identity mismatch")

            expected_project = _env_value(env, EXPECTED_PROJECT_NAME_ENV)
            if expected_project:
                expected_project = _validate_project(expected_project)
                if (
                    self.project is None
                    or self.project.project != expected_project
                ):
                    raise ValueError("Foundry project identity mismatch")

        if self.profile is RouteProfile.LEGACY_ROLLBACK:
            expected_legacy = _env_value(env, EXPECTED_LEGACY_ACCOUNT_ENV)
            if expected_legacy:
                expected_legacy = _validate_account(expected_legacy)
                if (
                    self.legacy is None
                    or self.legacy.account != expected_legacy
                ):
                    raise ValueError("legacy endpoint account identity mismatch")

    def select(self, workload: AzureAIWorkload | str) -> RouteSelection:
        selected_workload = AzureAIWorkload(workload)
        if selected_workload is AzureAIWorkload.CODE_INTERPRETER:
            if self.profile is not RouteProfile.PROJECT_CI:
                raise ValueError(
                    "Code Interpreter requires the project-ci profile"
                )
            if self.project is None:
                raise ValueError("Foundry project endpoint is unavailable")
            return RouteSelection(
                profile=self.profile,
                workload=selected_workload,
                endpoint=self.project,
                token_scope=DIRECT_TOKEN_SCOPE,
            )
        if self.profile in (RouteProfile.DIRECT_V1, RouteProfile.PROJECT_CI):
            if self.direct_v1 is None:
                raise ValueError("direct v1 endpoint is unavailable")
            return RouteSelection(
                profile=self.profile,
                workload=selected_workload,
                endpoint=self.direct_v1,
                token_scope=DIRECT_TOKEN_SCOPE,
            )
        if self.legacy is None:
            raise ValueError("legacy endpoint is unavailable")
        return RouteSelection(
            profile=self.profile,
            workload=selected_workload,
            endpoint=self.legacy,
            token_scope=LEGACY_TOKEN_SCOPE,
        )


def _close_sync(resource: object | None, role: str) -> None:
    if resource is None:
        return
    close = getattr(resource, "close", None)
    if not callable(close):
        return
    if inspect.iscoroutinefunction(close):
        raise RuntimeError(
            f"sync Azure AI client lifecycle does not support async {role} close"
        )
    result = close()
    if inspect.isawaitable(result):
        if inspect.iscoroutine(result):
            result.close()
        raise RuntimeError(
            f"sync Azure AI client lifecycle does not support async {role} close"
        )


def _close_resources_sync(
    resources: Sequence[tuple[str, object | None]],
) -> None:
    first_error: BaseException | None = None
    seen: set[int] = set()
    for role, resource in resources:
        if resource is None or id(resource) in seen:
            continue
        seen.add(id(resource))
        try:
            _close_sync(resource, role)
        except BaseException as exc:
            if first_error is None:
                first_error = exc
    if first_error is not None:
        raise first_error


@dataclass
class AzureAIClientLease:
    """Explicit synchronous client lease; instances are not thread-safe.

    Closing a lease closes its SDK client and project owner, but never the
    shared factory or its credential. Async close implementations are rejected.
    """

    client: object
    owner: object | None
    route: RouteSelection
    runtime_fingerprint: str
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _close_resources_sync(
            (
                ("client", self.client),
                ("project owner", self.owner),
            )
        )

    def __enter__(self) -> "AzureAIClientLease":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def route_fingerprint(
    route: RouteSelection,
    deployment: str,
    *,
    timeout: float | None = DEFAULT_TIMEOUT,
    max_retries: int | None = None,
    legacy_api_version: str = DEFAULT_LEGACY_API_VERSION,
) -> str:
    """Hash endpoint-free, redacted route provenance.

    The contract-versioned digest is a comparison identifier, not a
    confidentiality boundary or secret. Raw endpoint and deployment values are
    absent from emitted provenance records.
    """
    if not isinstance(deployment, str) or not deployment.strip():
        raise ValueError("Azure AI deployment identity is required")
    if not isinstance(legacy_api_version, str) or not legacy_api_version.strip():
        raise ValueError("Azure AI legacy API version is required")

    sdk_versions = {
        "azure_core": _package_version("azure-core"),
        "azure_identity": _package_version("azure-identity"),
        "openai": _package_version("openai"),
    }
    if route.endpoint.kind is EndpointKind.PROJECT:
        sdk_versions["azure_ai_projects"] = _package_version(
            "azure-ai-projects"
        )
    identity = {
        "contract_version": ROUTE_FINGERPRINT_CONTRACT_VERSION,
        "deployment": deployment.strip(),
        "endpoint_sha256": hashlib.sha256(
            route.endpoint.url.encode("utf-8")
        ).hexdigest(),
        "kind": route.endpoint.kind.value,
        "legacy_api_version": legacy_api_version.strip(),
        "max_retries": max_retries,
        "profile": route.profile.value,
        "sdk_versions": sdk_versions,
        "timeout": timeout,
        "token_scope": route.token_scope,
        "workload": route.workload.value,
    }
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def preflight_routes(
    workloads: Sequence[tuple[AzureAIWorkload | str, str]],
    *,
    settings: AzureAIRouteSettings | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    max_retries: int | None = None,
    legacy_api_version: str = DEFAULT_LEGACY_API_VERSION,
) -> list[dict[str, str]]:
    """Validate routes and return endpoint-free, redacted provenance records."""
    resolved = settings or AzureAIRouteSettings.from_env()
    if not workloads:
        raise ValueError("at least one Azure AI workload is required")

    records: list[dict[str, str]] = []
    seen: set[tuple[AzureAIWorkload, str]] = set()
    for raw_workload, raw_deployment in workloads:
        workload = AzureAIWorkload(raw_workload)
        deployment = (
            raw_deployment.strip()
            if isinstance(raw_deployment, str)
            else ""
        )
        if not deployment:
            raise ValueError("Azure AI deployment identity is required")
        identity = (workload, deployment)
        if identity in seen:
            continue
        seen.add(identity)
        route = resolved.select(workload)
        records.append(
            {
                "endpoint_kind": route.endpoint.kind.value,
                "profile": route.profile.value,
                "runtime_fingerprint": route_fingerprint(
                    route,
                    deployment,
                    timeout=timeout,
                    max_retries=max_retries,
                    legacy_api_version=legacy_api_version,
                ),
                "workload": workload.value,
            }
        )
    return records


def canonical_deployment(
    config: Mapping[str, object],
    path: str,
    *,
    fallback: str | None = None,
) -> str:
    """Resolve one SDK model identity and reject conflicting aliases."""
    model = config.get("model")
    deployment = config.get("deployment")
    for field_name, value in (("model", model), ("deployment", deployment)):
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            raise ValueError(f"{path}.{field_name} must be a nonempty string")
    if isinstance(model, str) and isinstance(deployment, str):
        if model.strip() != deployment.strip():
            raise ValueError(f"{path}.model and {path}.deployment must match")
    selected = deployment or model or fallback
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError(f"{path} deployment identity is missing")
    return selected.strip()


def inference_route_workloads(
    condition: Mapping[str, object],
    execution_mode: str,
) -> list[tuple[AzureAIWorkload, str]]:
    """Return every Azure deployment the inference condition can call.

    The current ``CodeInterpreterRunner`` is Azure-only, so Code Interpreter
    discovery requires an explicit, well-formed Azure main-model mapping.
    """
    raw_model = condition.get("model", {})
    if not isinstance(raw_model, Mapping):
        raise ValueError("model must be an object")
    model = raw_model
    provider = model.get("provider", "azure")
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("model.provider must be a nonempty string")
    azure_main = provider in _AZURE_PROVIDER_ALIASES
    if execution_mode == "code_interpreter" and not azure_main:
        raise ValueError(
            "code_interpreter mode requires an Azure provider because the "
            "current CodeInterpreterRunner is Azure-only"
        )

    main_deployment: str | None = None
    workloads: list[tuple[AzureAIWorkload, str]] = []
    if azure_main:
        raw_main_deployment = model.get("deployment", "gpt-4")
        if (
            not isinstance(raw_main_deployment, str)
            or not raw_main_deployment.strip()
        ):
            raise ValueError("model.deployment must be a nonempty string")
        main_deployment = raw_main_deployment.strip()
        workloads.append((AzureAIWorkload.INFERENCE, main_deployment))

        qa = condition.get("qa")
        if isinstance(qa, Mapping) and qa.get("enabled") is True:
            raw_qa_model = qa.get("model")
            if raw_qa_model in (None, ""):
                qa_deployment = main_deployment
            elif isinstance(raw_qa_model, str) and raw_qa_model.strip():
                qa_deployment = raw_qa_model.strip()
            else:
                raise ValueError("qa.model must be a nonempty string or null")
            workloads.append((AzureAIWorkload.INFERENCE, qa_deployment))

    preprocessors = condition.get("preprocessors") or []
    if not isinstance(preprocessors, list):
        raise ValueError("Azure AI preprocessors must be a list")
    for index, preprocessor in enumerate(preprocessors):
        if not isinstance(preprocessor, Mapping):
            raise ValueError("Azure AI preprocessor config must be an object")
        preprocessor_type = preprocessor.get("type")
        if preprocessor_type not in _PREPROCESSOR_DEFAULT_DEPLOYMENTS:
            continue
        raw_preprocessor_model = preprocessor.get("model")
        if raw_preprocessor_model is None:
            preprocessor_model: Mapping[str, object] = {}
        elif isinstance(raw_preprocessor_model, Mapping):
            preprocessor_model = raw_preprocessor_model
        else:
            raise ValueError("Azure AI preprocessor model must be an object")
        preprocessor_provider = preprocessor_model.get("provider", "azure")
        if not isinstance(preprocessor_provider, str):
            raise ValueError(
                "Azure AI preprocessor provider must be a string"
            )
        if preprocessor_provider not in _AZURE_PROVIDER_ALIASES:
            continue
        raw_deployment = preprocessor_model.get(
            "deployment",
            _PREPROCESSOR_DEFAULT_DEPLOYMENTS[preprocessor_type],
        )
        if not isinstance(raw_deployment, str) or not raw_deployment.strip():
            raise ValueError(
                f"preprocessors[{index}].model.deployment must be a "
                "nonempty string"
            )
        preprocessor_deployment = raw_deployment.strip()
        workloads.append(
            (AzureAIWorkload.INFERENCE, preprocessor_deployment)
        )

    if execution_mode == "code_interpreter":
        if main_deployment is None:
            raise ValueError("code_interpreter deployment identity is missing")
        workloads.append(
            (AzureAIWorkload.CODE_INTERPRETER, main_deployment)
        )
    return workloads


def grader_route_workloads(
    config: Mapping[str, object],
) -> list[tuple[AzureAIWorkload, str]]:
    """Return every Azure deployment a grading config can call.

    This is the credential boundary: the caller turns the result into the
    allowlist ``azure/login`` federates for, so a deployment absent here is one
    the run cannot reach, and a deployment present here is one it can.

    That is why a ``judge_routing`` block is refused rather than enumerated.
    Task 207 removed the tiered judge; nothing on the grading path reads the
    block any more. But ``Grader`` only refuses a config for *lacking*
    ``judge.tools.read_deliverable`` -- it does not look at ``judge_routing``
    at all -- so a config carrying both used to validate, credential its two
    or three tier deployments, and then grade every item on the single main
    judge. The operator reads a tiered config and a successful run; the run
    was not tiered. Deleting the enumeration alone would keep that config
    passing and merely stop crediting the unreachable deployments, which
    trades a wide boundary for a silent one. Refusing it costs a config edit
    and is loud, before any spend.
    """
    judge = config.get("judge")
    if not isinstance(judge, Mapping):
        raise ValueError("judge config must be an object")
    # Before the provider check on purpose: a non-Azure config gets no Azure
    # workloads, but it must not be the one shape that carries this block
    # through unremarked.
    if "judge_routing" in config:
        raise ValueError(
            "judge_routing is not a grading path: the tiered judge was "
            "removed in task 207 and nothing reads this block, so leaving it "
            "in a config grants its deployments credentials the grader will "
            "never spend and hides that every item went to judge.deployment. "
            "Remove judge_routing from the grading config."
        )
    provider = judge.get("provider", "azure_openai")
    if provider not in {"azure", "azure_openai"}:
        return []
    deployments = [canonical_deployment(judge, "judge")]

    perception = judge.get("perception") or {}
    if not isinstance(perception, Mapping):
        raise ValueError("judge.perception must be an object")
    for modality in ("visual", "audio"):
        modality_config = perception.get(modality) or {}
        if not isinstance(modality_config, Mapping):
            raise ValueError(f"judge.perception.{modality} must be an object")
        if (
            modality_config.get("deployment") is None
            and modality_config.get("model") is None
        ):
            continue
        deployments.append(
            canonical_deployment(
                modality_config,
                f"judge.perception.{modality}",
            )
        )

    return [(AzureAIWorkload.GRADER, value) for value in deployments]


def _narrative_deployment(
    value: str | Mapping[str, object],
    path: str,
) -> str:
    if isinstance(value, Mapping):
        return canonical_deployment(value, path)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("narrative deployment identity is invalid")
    return value.strip()


def narrative_route_workloads(
    primary_deployment: str | Mapping[str, object],
    fallback_deployments: Sequence[str | Mapping[str, object]] = (),
) -> list[tuple[AzureAIWorkload, str]]:
    """Return primary and possible fallback narrative deployments."""
    deployments = [primary_deployment, *fallback_deployments]
    return [
        (
            AzureAIWorkload.NARRATIVE,
            _narrative_deployment(value, f"narrative[{index}]"),
        )
        for index, value in enumerate(deployments)
    ]


def verify_direct_token(credential=None) -> None:
    """Verify Entra token acquisition without calling a model endpoint."""
    owns_credential = credential is None
    if owns_credential:
        _reject_static_azure_credential_env(os.environ)
        active_credential = DefaultAzureCredential()
    else:
        active_credential = credential
    try:
        active_credential.get_token(DIRECT_TOKEN_SCOPE)
    finally:
        if owns_credential:
            _close_sync(active_credential, "credential")


def verify_route_tokens(
    workloads: Sequence[tuple[AzureAIWorkload | str, str]],
    *,
    settings: AzureAIRouteSettings | None = None,
    credential=None,
) -> None:
    """Acquire one token for every audience selected by the typed routes."""
    resolved = settings or AzureAIRouteSettings.from_env()
    scopes = {
        resolved.select(workload).token_scope
        for workload, _deployment in workloads
    }
    if not scopes:
        raise ValueError("at least one Azure AI workload is required")

    owns_credential = credential is None
    if owns_credential:
        _reject_static_azure_credential_env(os.environ)
        active_credential = DefaultAzureCredential()
    else:
        active_credential = credential
    try:
        for scope in sorted(scopes):
            active_credential.get_token(scope)
    finally:
        if owns_credential:
            _close_sync(active_credential, "credential")


def _require_attr_path(client: object, path: str) -> None:
    current = client
    for part in path.split("."):
        try:
            current = getattr(current, part)
        except (AttributeError, TypeError):
            raise RuntimeError(
                f"Azure AI client lacks required capability: {path}"
            ) from None
    if not callable(current):
        raise RuntimeError(
            f"Azure AI client lacks required capability: {path}"
        )


def validate_client_capabilities(
    client: object,
    workload: AzureAIWorkload,
) -> None:
    required = {
        AzureAIWorkload.INFERENCE: ("chat.completions.create",),
        AzureAIWorkload.NARRATIVE: ("responses.create",),
        AzureAIWorkload.GRADER: ("responses.create",),
        AzureAIWorkload.CODE_INTERPRETER: (
            "responses.create",
            "files.create",
            "files.delete",
            "files.content",
            "containers.create",
            "containers.files.list",
            "containers.files.content.retrieve",
        ),
    }[workload]
    for path in required:
        _require_attr_path(client, path)


def _load_project_client_class():
    try:
        from azure.ai.projects import AIProjectClient
    except ImportError as exc:
        raise RuntimeError(
            "project-ci requires azure-ai-projects==2.3.0"
        ) from exc
    return AIProjectClient


class AzureAIClientFactory:
    """Explicitly managed synchronous client factory; not thread-safe.

    A shared factory survives lease closure and failed client construction.
    Callers must close the factory explicitly; injected credentials remain
    caller-owned. Async close implementations are rejected.
    """

    def __init__(
        self,
        settings: AzureAIRouteSettings | None = None,
        credential=None,
    ):
        self.settings = settings or AzureAIRouteSettings.from_env()
        self._owns_credential = credential is None
        if self._owns_credential:
            _reject_static_azure_credential_env(os.environ)
            self.credential = DefaultAzureCredential()
        else:
            self.credential = credential
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_credential:
            _close_sync(self.credential, "credential")

    def __enter__(self) -> "AzureAIClientFactory":
        if self._closed:
            raise RuntimeError("Azure AI client factory is closed")
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def create(
        self,
        workload: AzureAIWorkload | str,
        *,
        deployment: str,
        timeout: float | None = DEFAULT_TIMEOUT,
        max_retries: int | None = None,
        legacy_api_version: str = DEFAULT_LEGACY_API_VERSION,
    ) -> AzureAIClientLease:
        if self._closed:
            raise RuntimeError("Azure AI client factory is closed")
        route = self.settings.select(workload)
        fingerprint = route_fingerprint(
            route,
            deployment,
            timeout=timeout,
            max_retries=max_retries,
            legacy_api_version=legacy_api_version,
        )
        common: dict[str, object] = {"timeout": timeout}
        if max_retries is not None:
            common["max_retries"] = max_retries

        if route.endpoint.kind is EndpointKind.PROJECT:
            project = None
            client = None
            try:
                project_class = _load_project_client_class()
                project = project_class(
                    endpoint=route.endpoint.url,
                    credential=self.credential,
                )
                client = project.get_openai_client(**common)
                validate_client_capabilities(client, route.workload)
            except BaseException as creation_error:
                try:
                    _close_resources_sync(
                        (
                            ("client", client),
                            ("project owner", project),
                        )
                    )
                except BaseException as close_error:
                    raise close_error from creation_error
                raise
            return AzureAIClientLease(
                client=client,
                owner=project,
                route=route,
                runtime_fingerprint=fingerprint,
            )

        token_provider = get_bearer_token_provider(
            self.credential,
            route.token_scope,
        )
        client = None
        try:
            if route.endpoint.kind is EndpointKind.DIRECT_V1:
                client = OpenAI(
                    base_url=route.endpoint.url,
                    api_key=token_provider,
                    **common,
                )
                # The plain OpenAI class has nowhere to keep the deployment or
                # the API contract, so a cost receipt questioning this client
                # gets "unknown" for both — as every call of the first paid
                # grading run did. What is unknown to the client is not unknown
                # here, so the route records it on the way out.
                setattr(
                    client,
                    ROUTE_IDENTITY_ATTRIBUTE,
                    DIRECT_V1_CALL_IDENTITY,
                )
            else:
                client = AzureOpenAI(
                    azure_endpoint=route.endpoint.url,
                    azure_ad_token_provider=token_provider,
                    api_version=legacy_api_version,
                    **common,
                )
            validate_client_capabilities(client, route.workload)
        except BaseException as creation_error:
            try:
                _close_resources_sync((("client", client),))
            except BaseException as close_error:
                raise close_error from creation_error
            raise
        return AzureAIClientLease(
            client=client,
            owner=None,
            route=route,
            runtime_fingerprint=fingerprint,
        )