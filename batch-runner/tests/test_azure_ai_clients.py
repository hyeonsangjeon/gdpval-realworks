import gc
import importlib.metadata
import re
import warnings
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.azure_ai_clients as clients
from core.experiment_config import ExperimentConfig


REPO_ROOT = Path(__file__).resolve().parents[2]
FOUNDATION_DOCS = (
    REPO_ROOT / "tasks/0723_thursday/BOLT_TYPED_AZURE_AI_ENDPOINT_CONTRACTS.md",
    REPO_ROOT / "CHANGELOG.md",
)


def _direct_settings(
    host: str = "account.openai.azure.com",
) -> clients.AzureAIRouteSettings:
    return clients.AzureAIRouteSettings.from_env(
        {
            "AZURE_AI_ROUTE_PROFILE": "direct-v1",
            "AZURE_OPENAI_V1_ENDPOINT": f"https://{host}/openai/v1/",
        }
    )


def _project_settings() -> clients.AzureAIRouteSettings:
    return clients.AzureAIRouteSettings.from_env(
        {
            "AZURE_AI_ROUTE_PROFILE": "project-ci",
            "AZURE_OPENAI_V1_ENDPOINT": (
                "https://account.services.ai.azure.com/openai/v1/"
            ),
            "FOUNDRY_PROJECT_ENDPOINT": (
                "https://account.services.ai.azure.com/"
                "api/projects/project-one"
            ),
        }
    )


def _legacy_settings() -> clients.AzureAIRouteSettings:
    return clients.AzureAIRouteSettings.from_env(
        {
            "AZURE_AI_ROUTE_PROFILE": "legacy-rollback",
            "AZURE_OPENAI_LEGACY_ENDPOINT": (
                "https://account.openai.azure.com/"
            ),
            "AZURE_AI_ALLOW_LEGACY_ROLLBACK": "1",
        }
    )


def _inference_client() -> SimpleNamespace:
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=MagicMock())
        ),
        close=MagicMock(),
    )


def _responses_client() -> SimpleNamespace:
    return SimpleNamespace(
        responses=SimpleNamespace(create=MagicMock()),
        close=MagicMock(),
    )


def _code_interpreter_client() -> SimpleNamespace:
    return SimpleNamespace(
        responses=SimpleNamespace(create=MagicMock()),
        files=SimpleNamespace(
            create=MagicMock(),
            delete=MagicMock(),
            content=MagicMock(),
        ),
        containers=SimpleNamespace(
            create=MagicMock(),
            files=SimpleNamespace(
                list=MagicMock(),
                content=SimpleNamespace(retrieve=MagicMock()),
            ),
        ),
        close=MagicMock(),
    )


@pytest.mark.parametrize(
    ("value", "kind", "canonical", "account", "project"),
    [
        (
            "https://account.openai.azure.com/openai/v1",
            clients.EndpointKind.DIRECT_V1,
            "https://account.openai.azure.com/openai/v1/",
            "account",
            None,
        ),
        (
            "HTTPS://Account.Services.AI.Azure.Com:443/openai/v1/",
            clients.EndpointKind.DIRECT_V1,
            "https://account.services.ai.azure.com/openai/v1/",
            "account",
            None,
        ),
        (
            "https://account.services.ai.azure.com/api/projects/project-one/",
            clients.EndpointKind.PROJECT,
            "https://account.services.ai.azure.com/api/projects/project-one",
            "account",
            "project-one",
        ),
        (
            "https://account.openai.azure.com",
            clients.EndpointKind.LEGACY_DATED,
            "https://account.openai.azure.com/",
            "account",
            None,
        ),
        (
            "https://a.openai.azure.com/",
            clients.EndpointKind.LEGACY_DATED,
            "https://a.openai.azure.com/",
            "a",
            None,
        ),
    ],
)
def test_classify_endpoint_accepts_only_canonical_contracts(
    value,
    kind,
    canonical,
    account,
    project,
):
    classified = clients.classify_endpoint(value)

    assert classified.kind is kind
    assert classified.url == canonical
    assert classified.account == account
    assert classified.project == project


@pytest.mark.parametrize(
    "value",
    [
        "http://account.openai.azure.com/openai/v1/",
        "https://user@account.openai.azure.com/openai/v1/",
        "https://:password@account.openai.azure.com/openai/v1/",
        "https://@account.openai.azure.com/openai/v1/",
        "https://account.openai.azure.com:444/openai/v1/",
        "https://account.openai.azure.com:invalid/openai/v1/",
        "https://127.0.0.1/openai/v1/",
        "https://[::1]/openai/v1/",
        "https://localhost/openai/v1/",
        "https://account.openai.azure.com/openai/v1/?x=1",
        "https://account.openai.azure.com/openai/v1/?",
        "https://account.openai.azure.com/openai/v1/#fragment",
        "https://account.openai.azure.com/openai/v1/#",
        "https://account.openai.azure.com\\openai\\v1\\",
        "https://account.openai.azure.com/openai//v1/",
        "https://account.openai.azure.com/openai/v1/extra",
        "https://account.services.ai.azure.com/api/projects/a/extra",
        "https://account.services.ai.azure.com/openai/deployments/model",
        "https://account.services.ai.azure.com/",
        "https://account.openai.azure.com/api/projects/project-one",
        "https://example.com/openai/v1/",
        "https://account.openai.azure.com.evil.test/openai/v1/",
        "https://account.services.ai.azure.com.evil/openai/v1/",
        "https://account.openai.azure.comm/openai/v1/",
        "https://other.account.openai.azure.com/openai/v1/",
        "https://account.openai.azure.com./openai/v1/",
        "https://-account.openai.azure.com/openai/v1/",
        "https://account-.openai.azure.com/openai/v1/",
        "https://account_name.openai.azure.com/openai/v1/",
        f"https://{'a' * 64}.openai.azure.com/openai/v1/",
        "https://account.services.ai.azure.com/api/projects/.project",
        "https://account.services.ai.azure.com/api/projects/project.",
        "https://account.services.ai.azure.com/api/projects/project-",
        "https://account.services.ai.azure.com/api/projects/_project",
        f"https://account.services.ai.azure.com/api/projects/{'p' * 129}",
    ],
)
def test_classify_endpoint_rejects_ambiguous_or_unsafe_values(value):
    with pytest.raises(ValueError):
        clients.classify_endpoint(value)


@pytest.mark.parametrize(
    "value",
    [
        "https://account.openai.azure.com/openai%2fv1/",
        "https://account.openai.azure.com/openai/%76%31/",
        "https://account.openai.azure.com/%6fpenai/v1/",
        "https://account.openai.azure.com/openai/v1%2f",
        (
            "https://account.services.ai.azure.com/"
            "api/projects/%70roject-one"
        ),
        (
            "https://account.services.ai.azure.com/"
            "api/%70rojects/project-one"
        ),
        (
            "https://account.services.ai.azure.com/"
            "api/projects/project%2done"
        ),
    ],
)
def test_classify_endpoint_rejects_every_percent_encoded_path_component(value):
    with pytest.raises(ValueError, match="percent encoding"):
        clients.classify_endpoint(value)


@pytest.mark.parametrize("character", ["\r", "\n", "\t"])
def test_classify_endpoint_rejects_characters_urlsplit_would_normalize(character):
    value = (
        "https://account.openai.azure.com"
        f"{character}/openai/v1/"
    )

    with pytest.raises(ValueError, match="control characters"):
        clients.classify_endpoint(value)


@pytest.mark.parametrize(
    "character",
    ["\x00", "\x1f", "\x7f", "\x80", "\x9f", "\u2028", "\u2029"],
)
def test_classify_endpoint_rejects_control_and_line_separator_characters(
    character,
):
    value = f"https://account.openai.azure.com/{character}openai/v1/"

    with pytest.raises(ValueError, match="control characters"):
        clients.classify_endpoint(value)


@pytest.mark.parametrize(
    "value",
    [
        "https://account.openai.azure.com/openai/%",
        "https://account.openai.azure.com/openai/%2/v1/",
        "https://account.openai.azure.com/openai/%GG/v1/",
    ],
)
def test_classify_endpoint_rejects_malformed_percent_sequences(value):
    with pytest.raises(ValueError, match="percent encoding"):
        clients.classify_endpoint(value)


@pytest.mark.parametrize(
    "value",
    [
        "https://account.openai.azure.com:/openai/v1/",
        "https://account.openai.azure.com.evil/openai/v1/",
        "https://account.openai.azure.com./openai/v1/",
        "https://account.openai.azure.com/\uff0fopenai/v1/",
    ],
)
def test_classify_endpoint_rejects_empty_port_and_host_path_lookalikes(value):
    with pytest.raises(ValueError):
        clients.classify_endpoint(value)


def test_classify_endpoint_errors_do_not_echo_raw_endpoint():
    endpoint = (
        "https://user:private-value@account.openai.azure.com/openai/v1/"
    )

    with pytest.raises(ValueError) as error:
        clients.classify_endpoint(endpoint)

    assert endpoint not in str(error.value)
    assert "private-value" not in str(error.value)


def test_classified_endpoint_repr_hides_url():
    endpoint = clients.classify_endpoint(
        "https://account.openai.azure.com/openai/v1/"
    )

    assert endpoint.url not in repr(endpoint)


def test_project_ci_routes_only_code_interpreter_through_project():
    settings = _project_settings()

    for workload in ("inference", "narrative", "grader"):
        route = settings.select(workload)
        assert route.endpoint.kind is clients.EndpointKind.DIRECT_V1
        assert route.token_scope == clients.DIRECT_TOKEN_SCOPE

    code_route = settings.select("code-interpreter")
    assert code_route.endpoint.kind is clients.EndpointKind.PROJECT
    assert code_route.token_scope == clients.DIRECT_TOKEN_SCOPE


def test_direct_profile_routes_all_workloads_to_direct_v1():
    settings = _direct_settings()

    for workload in clients.AzureAIWorkload:
        route = settings.select(workload)
        assert route.endpoint.kind is clients.EndpointKind.DIRECT_V1
        assert route.token_scope == "https://ai.azure.com/.default"


def test_legacy_profile_routes_all_workloads_with_legacy_scope():
    settings = _legacy_settings()

    for workload in clients.AzureAIWorkload:
        route = settings.select(workload)
        assert route.endpoint.kind is clients.EndpointKind.LEGACY_DATED
        assert route.token_scope == (
            "https://cognitiveservices.azure.com/.default"
        )


def test_project_endpoint_derives_same_account_direct_v1_route():
    settings = clients.AzureAIRouteSettings.from_env(
        {
            "AZURE_AI_ROUTE_PROFILE": "project-ci",
            "FOUNDRY_PROJECT_ENDPOINT": (
                "https://account.services.ai.azure.com/"
                "api/projects/project-one"
            ),
        }
    )

    direct = settings.select("inference").endpoint
    project = settings.select("code-interpreter").endpoint
    assert direct.url == "https://account.services.ai.azure.com/openai/v1/"
    assert direct.account == project.account


def test_legacy_route_requires_explicit_authorization():
    env = {
        "AZURE_AI_ROUTE_PROFILE": "legacy-rollback",
        "AZURE_OPENAI_LEGACY_ENDPOINT": (
            "https://account.openai.azure.com/"
        ),
    }

    with pytest.raises(ValueError, match="explicitly authorized"):
        clients.AzureAIRouteSettings.from_env(env)

    env["AZURE_AI_ALLOW_LEGACY_ROLLBACK"] = "1"
    settings = clients.AzureAIRouteSettings.from_env(env)
    assert settings.profile is clients.RouteProfile.LEGACY_ROLLBACK


@pytest.mark.parametrize("name", clients.FORBIDDEN_API_KEY_ENV)
def test_static_azure_keys_and_secrets_are_rejected(name):
    with pytest.raises(ValueError, match="forbidden") as error:
        clients.AzureAIRouteSettings.from_env(
            {
                "AZURE_AI_ROUTE_PROFILE": "direct-v1",
                "AZURE_OPENAI_V1_ENDPOINT": (
                    "https://account.openai.azure.com/openai/v1/"
                ),
                name: "not-a-real-secret",
            }
        )

    assert "not-a-real-secret" not in str(error.value)


@pytest.mark.parametrize("name", clients.FORBIDDEN_API_KEY_ENV)
def test_owned_factory_rejects_process_static_secret_before_credential(
    name, monkeypatch
):
    constructor = MagicMock()
    monkeypatch.setattr(clients, "DefaultAzureCredential", constructor)
    monkeypatch.setenv(name, "not-a-real-secret")

    with pytest.raises(ValueError, match="forbidden") as error:
        clients.AzureAIClientFactory(settings=_direct_settings())

    constructor.assert_not_called()
    assert "not-a-real-secret" not in str(error.value)


def test_injected_credential_does_not_consult_process_secret_env(monkeypatch):
    credential = object()
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "caller-managed-secret")

    factory = clients.AzureAIClientFactory(
        settings=_direct_settings(),
        credential=credential,
    )

    assert factory.credential is credential


def test_native_openai_key_can_coexist_with_typed_azure_route():
    settings = clients.AzureAIRouteSettings.from_env(
        {
            "AZURE_AI_ROUTE_PROFILE": "direct-v1",
            "AZURE_OPENAI_V1_ENDPOINT": (
                "https://account.openai.azure.com/openai/v1/"
            ),
            "OPENAI_API_KEY": "native-provider-key",
        }
    )

    assert settings.profile is clients.RouteProfile.DIRECT_V1


def test_federated_token_file_can_coexist_with_typed_azure_route():
    settings = clients.AzureAIRouteSettings.from_env(
        {
            "AZURE_AI_ROUTE_PROFILE": "direct-v1",
            "AZURE_OPENAI_V1_ENDPOINT": (
                "https://account.openai.azure.com/openai/v1/"
            ),
            "AZURE_FEDERATED_TOKEN_FILE": "/tmp/federated-token",
        }
    )

    assert settings.profile is clients.RouteProfile.DIRECT_V1


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        (
            "AZURE_OPENAI_V1_ENDPOINT",
            "https://account.openai.azure.com/",
        ),
        (
            "FOUNDRY_PROJECT_ENDPOINT",
            "https://account.services.ai.azure.com/openai/v1/",
        ),
        (
            "AZURE_OPENAI_LEGACY_ENDPOINT",
            "https://account.openai.azure.com/openai/v1/",
        ),
    ],
)
def test_typed_endpoint_variables_reject_wrong_endpoint_kinds(variable, value):
    env = {
        "AZURE_AI_ROUTE_PROFILE": "project-ci",
        "AZURE_OPENAI_V1_ENDPOINT": (
            "https://account.services.ai.azure.com/openai/v1/"
        ),
        "FOUNDRY_PROJECT_ENDPOINT": (
            "https://account.services.ai.azure.com/api/projects/project-one"
        ),
        "AZURE_OPENAI_LEGACY_ENDPOINT": (
            "https://account.openai.azure.com/"
        ),
        variable: value,
    }

    with pytest.raises(ValueError, match=variable):
        clients.AzureAIRouteSettings.from_env(env)


def test_deprecated_untyped_endpoint_has_endpoint_free_migration_guidance():
    endpoint = (
        "https://private-account.services.ai.azure.com/"
        "api/projects/private-project"
    )

    with pytest.raises(ValueError, match="FOUNDRY_PROJECT_ENDPOINT") as error:
        clients.AzureAIRouteSettings.from_env(
            {
                "AZURE_AI_ROUTE_PROFILE": "project-ci",
                "AZURE_OPENAI_ENDPOINT": endpoint,
            }
        )

    assert endpoint not in str(error.value)
    assert "private-account" not in str(error.value)
    assert "private-project" not in str(error.value)


def test_deprecated_untyped_endpoint_is_rejected_with_typed_endpoint():
    with pytest.raises(ValueError, match="must be unset"):
        clients.AzureAIRouteSettings.from_env(
            {
                "AZURE_AI_ROUTE_PROFILE": "direct-v1",
                "AZURE_OPENAI_V1_ENDPOINT": (
                    "https://account.openai.azure.com/openai/v1/"
                ),
                "AZURE_OPENAI_ENDPOINT": (
                    "https://other.openai.azure.com/openai/v1/"
                ),
            }
        )


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        (
            "AZURE_AI_EXPECTED_DIRECT_ACCOUNT",
            "other",
            "direct endpoint account identity mismatch",
        ),
        (
            "AZURE_AI_EXPECTED_PROJECT_ACCOUNT",
            "other",
            "project endpoint account identity mismatch",
        ),
        (
            "AZURE_AI_EXPECTED_PROJECT_NAME",
            "other",
            "Foundry project identity mismatch",
        ),
    ],
)
def test_expected_endpoint_identities_fail_closed(name, value, message):
    env = {
        "AZURE_AI_ROUTE_PROFILE": "project-ci",
        "AZURE_OPENAI_V1_ENDPOINT": (
            "https://account.services.ai.azure.com/openai/v1/"
        ),
        "FOUNDRY_PROJECT_ENDPOINT": (
            "https://account.services.ai.azure.com/api/projects/project-one"
        ),
        name: value,
    }

    with pytest.raises(ValueError, match=message):
        clients.AzureAIRouteSettings.from_env(env)


def test_expected_identity_values_are_validated():
    with pytest.raises(ValueError, match="account name is invalid"):
        clients.AzureAIRouteSettings.from_env(
            {
                "AZURE_AI_ROUTE_PROFILE": "direct-v1",
                "AZURE_OPENAI_V1_ENDPOINT": (
                    "https://account.openai.azure.com/openai/v1/"
                ),
                "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": "invalid.account",
            }
        )


def test_strict_identity_mode_requires_profile_identities():
    with pytest.raises(ValueError, match="EXPECTED_PROJECT_ACCOUNT"):
        clients.AzureAIRouteSettings.from_env(
            {
                "AZURE_AI_ROUTE_PROFILE": "project-ci",
                "FOUNDRY_PROJECT_ENDPOINT": (
                    "https://account.services.ai.azure.com/"
                    "api/projects/project-one"
                ),
                "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES": "1",
                "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": "account",
            }
        )


def test_strict_identity_mode_accepts_exact_identities():
    settings = clients.AzureAIRouteSettings.from_env(
        {
            "AZURE_AI_ROUTE_PROFILE": "project-ci",
            "FOUNDRY_PROJECT_ENDPOINT": (
                "https://account.services.ai.azure.com/"
                "api/projects/project-one"
            ),
            "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES": "1",
            "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": "account",
            "AZURE_AI_EXPECTED_PROJECT_ACCOUNT": "account",
            "AZURE_AI_EXPECTED_PROJECT_NAME": "project-one",
        }
    )

    assert settings.profile is clients.RouteProfile.PROJECT_CI


def test_strict_legacy_identity_requires_and_verifies_active_legacy_account():
    base = {
        "AZURE_AI_ROUTE_PROFILE": "legacy-rollback",
        "AZURE_OPENAI_LEGACY_ENDPOINT": (
            "https://legacy-account.openai.azure.com/"
        ),
        "AZURE_AI_ALLOW_LEGACY_ROLLBACK": "1",
        "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES": "1",
    }

    with pytest.raises(ValueError, match="EXPECTED_LEGACY_ACCOUNT"):
        clients.AzureAIRouteSettings.from_env(base)

    with pytest.raises(ValueError, match="legacy endpoint account identity"):
        clients.AzureAIRouteSettings.from_env(
            {**base, "AZURE_AI_EXPECTED_LEGACY_ACCOUNT": "other"}
        )

    settings = clients.AzureAIRouteSettings.from_env(
        {
            **base,
            "AZURE_AI_EXPECTED_LEGACY_ACCOUNT": "legacy-account",
            "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": "untrusted-direct",
        }
    )

    assert settings.direct_v1 is None
    assert settings.legacy is not None
    assert settings.legacy.account == "legacy-account"


def test_strict_direct_identity_does_not_require_project_identity():
    settings = clients.AzureAIRouteSettings.from_env(
        {
            "AZURE_AI_ROUTE_PROFILE": "direct-v1",
            "AZURE_OPENAI_V1_ENDPOINT": (
                "https://account.openai.azure.com/openai/v1/"
            ),
            "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES": "1",
            "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": "account",
        }
    )

    assert settings.profile is clients.RouteProfile.DIRECT_V1


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"AZURE_AI_ROUTE_PROFILE": "unsupported"},
        {"AZURE_AI_ROUTE_PROFILE": "direct-v1"},
        {"AZURE_AI_ROUTE_PROFILE": "project-ci"},
    ],
)
def test_route_profiles_require_explicit_valid_configuration(env):
    with pytest.raises(ValueError):
        clients.AzureAIRouteSettings.from_env(env)


def test_route_fingerprint_binds_all_route_and_transport_inputs(monkeypatch):
    versions = {
        "azure-core": "core-1",
        "azure-identity": "identity-1",
        "openai": "openai-1",
        "azure-ai-projects": "projects-1",
    }
    monkeypatch.setattr(
        clients,
        "_package_version",
        lambda name: versions[name],
    )
    direct = _direct_settings("account.services.ai.azure.com")
    project = _project_settings()
    base_route = direct.select("inference")
    base = clients.route_fingerprint(
        base_route,
        "deployment",
        timeout=30,
        max_retries=None,
        legacy_api_version="legacy-v1",
    )

    alternatives = {
        clients.route_fingerprint(
            _direct_settings("other.services.ai.azure.com").select("inference"),
            "deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            project.select("inference"),
            "deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            project.select("code-interpreter"),
            "deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            direct.select("narrative"),
            "deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            base_route,
            "other-deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            base_route,
            "deployment",
            timeout=31,
            max_retries=None,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            base_route,
            "deployment",
            timeout=30,
            max_retries=0,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            base_route,
            "deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v2",
        ),
    }

    assert len(base) == 64
    assert base not in alternatives
    assert len(alternatives) == 8

    versions["openai"] = "openai-2"
    assert clients.route_fingerprint(
        base_route,
        "deployment",
        timeout=30,
        max_retries=None,
        legacy_api_version="legacy-v1",
    ) != base


def test_project_fingerprint_binds_project_sdk_version(monkeypatch):
    versions = {
        "azure-core": "core-1",
        "azure-identity": "identity-1",
        "openai": "openai-1",
        "azure-ai-projects": "projects-1",
    }
    monkeypatch.setattr(clients, "_package_version", versions.__getitem__)
    route = _project_settings().select("code-interpreter")
    first = clients.route_fingerprint(route, "deployment")

    versions["azure-ai-projects"] = "projects-2"

    assert clients.route_fingerprint(route, "deployment") != first


def test_fingerprint_binds_contract_scope_and_transport_settings(monkeypatch):
    versions = {
        "azure-core": "core-1",
        "azure-identity": "identity-1",
        "openai": "openai-1",
    }
    monkeypatch.setattr(clients, "_package_version", versions.__getitem__)
    route = _direct_settings().select("grader")
    base = clients.route_fingerprint(
        route,
        "deployment",
        timeout=30,
        max_retries=None,
        legacy_api_version="legacy-v1",
    )
    alternatives = {
        clients.route_fingerprint(
            replace(route, token_scope="https://other.example/.default"),
            "deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            route,
            "deployment",
            timeout=31,
            max_retries=None,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            route,
            "deployment",
            timeout=30,
            max_retries=0,
            legacy_api_version="legacy-v1",
        ),
        clients.route_fingerprint(
            route,
            "deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v2",
        ),
    }
    monkeypatch.setattr(
        clients,
        "ROUTE_FINGERPRINT_CONTRACT_VERSION",
        "azure-ai-route-v2",
    )
    alternatives.add(
        clients.route_fingerprint(
            route,
            "deployment",
            timeout=30,
            max_retries=None,
            legacy_api_version="legacy-v1",
        )
    )

    assert len(alternatives) == 5
    assert base not in alternatives


def test_route_fingerprint_does_not_expose_endpoint_or_deployment():
    route = _direct_settings().select("grader")

    fingerprint = clients.route_fingerprint(route, "private-deployment")

    assert len(fingerprint) == 64
    assert "account" not in fingerprint
    assert "private-deployment" not in fingerprint


def test_preflight_records_are_endpoint_and_deployment_free():
    records = clients.preflight_routes(
        [
            ("narrative", "private-deployment"),
            ("code-interpreter", "private-deployment"),
            ("narrative", "private-deployment"),
        ],
        settings=_project_settings(),
    )

    assert len(records) == 2
    assert records[0]["endpoint_kind"] == "direct-v1"
    assert records[1]["endpoint_kind"] == "project"
    for record in records:
        assert set(record) == {
            "endpoint_kind",
            "profile",
            "runtime_fingerprint",
            "workload",
        }
    encoded = str(records)
    assert "account" not in encoded
    assert "project-one" not in encoded
    assert "private-deployment" not in encoded


def test_preflight_fingerprint_is_transport_sensitive():
    workloads = [("grader", "deployment")]
    settings = _direct_settings()

    base = clients.preflight_routes(
        workloads,
        settings=settings,
        timeout=30,
        max_retries=None,
        legacy_api_version="legacy-v1",
    )[0]["runtime_fingerprint"]
    retry = clients.preflight_routes(
        workloads,
        settings=settings,
        timeout=30,
        max_retries=0,
        legacy_api_version="legacy-v1",
    )[0]["runtime_fingerprint"]
    timeout = clients.preflight_routes(
        workloads,
        settings=settings,
        timeout=31,
        max_retries=None,
        legacy_api_version="legacy-v1",
    )[0]["runtime_fingerprint"]

    assert len({base, retry, timeout}) == 3


def test_preflight_requires_at_least_one_workload():
    with pytest.raises(ValueError, match="at least one"):
        clients.preflight_routes([], settings=_direct_settings())


def test_inference_workloads_discover_main_qa_preprocessor_and_ci():
    condition = {
        "model": {"provider": "azure", "deployment": "main"},
        "qa": {"enabled": True, "model": "qa"},
        "preprocessors": [
            {
                "type": "audio_analyzer",
                "model": {
                    "provider": "azure_openai",
                    "deployment": "audio",
                },
            },
            {
                "type": "external",
                "model": {
                    "provider": "openai",
                    "deployment": "external",
                },
            },
        ],
    }

    assert clients.inference_route_workloads(condition, "code_interpreter") == [
        (clients.AzureAIWorkload.INFERENCE, "main"),
        (clients.AzureAIWorkload.INFERENCE, "qa"),
        (clients.AzureAIWorkload.INFERENCE, "audio"),
        (clients.AzureAIWorkload.CODE_INTERPRETER, "main"),
    ]


def test_inference_workloads_default_missing_provider_to_azure():
    condition = {
        "model": {"deployment": "main"},
        "preprocessors": [
            {"type": "audio_analyzer", "model": {"deployment": "audio"}}
        ],
    }

    assert clients.inference_route_workloads(condition, "subprocess") == [
        (clients.AzureAIWorkload.INFERENCE, "main"),
        (clients.AzureAIWorkload.INFERENCE, "audio"),
    ]


@pytest.mark.parametrize("provider", ["azure", "azure_openai"])
def test_inference_workloads_apply_runtime_preprocessor_defaults(provider):
    condition = {
        "model": {"provider": provider},
        "preprocessors": [
            {"type": "audio_analyzer", "model": {"provider": provider}},
            {"type": "video_analyzer", "model": {"provider": provider}},
        ],
    }

    assert clients.inference_route_workloads(condition, "subprocess") == [
        (clients.AzureAIWorkload.INFERENCE, "gpt-4"),
        (clients.AzureAIWorkload.INFERENCE, "gpt-audio-1.5"),
        (clients.AzureAIWorkload.INFERENCE, "gpt-5.2"),
    ]


def test_inference_workloads_match_raw_and_serialized_condition_semantics():
    raw = {
        "model": {"provider": "azure", "model": "ignored-main-alias"},
        "qa": {
            "enabled": True,
            "deployment": "ignored-qa-alias",
        },
        "preprocessors": [
            {
                "type": "audio_analyzer",
                "model": {"provider": "azure", "model": "ignored-audio-alias"},
            }
        ],
    }
    parsed = ExperimentConfig._parse_condition(raw)
    serialized = ExperimentConfig._condition_to_dict(parsed)

    expected = [
        (clients.AzureAIWorkload.INFERENCE, "gpt-4"),
        (clients.AzureAIWorkload.INFERENCE, "gpt-4"),
        (clients.AzureAIWorkload.INFERENCE, "gpt-audio-1.5"),
    ]
    assert clients.inference_route_workloads(raw, "subprocess") == expected
    assert clients.inference_route_workloads(serialized, "subprocess") == expected


def test_inference_workloads_ignore_runtime_unsupported_aliases():
    condition = {
        "model": {
            "provider": "azure",
            "model": "ignored-main-alias",
            "deployment": "main",
        },
        "qa": {
            "enabled": True,
            "model": "qa",
            "deployment": "ignored-qa-alias",
        },
    }

    assert clients.inference_route_workloads(condition, "subprocess") == [
        (clients.AzureAIWorkload.INFERENCE, "main"),
        (clients.AzureAIWorkload.INFERENCE, "qa"),
    ]


def test_inference_discovers_azure_preprocessor_with_native_main():
    condition = {
        "model": {"provider": "openai", "deployment": "native-main"},
        "preprocessors": [
            {
                "type": "audio_analyzer",
                "model": {"provider": "azure", "deployment": "audio"},
            }
        ],
    }

    assert clients.inference_route_workloads(condition, "subprocess") == [
        (clients.AzureAIWorkload.INFERENCE, "audio")
    ]


def test_native_main_discovers_defaulted_azure_preprocessor():
    condition = {
        "model": {"provider": "openai", "deployment": "native-main"},
        "preprocessors": [
            {
                "type": "audio_analyzer",
                "model": {"provider": "azure_openai"},
            }
        ],
    }

    assert clients.inference_route_workloads(condition, "subprocess") == [
        (clients.AzureAIWorkload.INFERENCE, "gpt-audio-1.5")
    ]


def test_preprocessor_model_alias_does_not_override_runtime_default():
    condition = {
        "model": {"provider": "openai", "deployment": "native-main"},
        "preprocessors": [
            {
                "type": "audio_analyzer",
                "model": {"provider": "azure", "model": "ignored-alias"},
            }
        ],
    }

    assert clients.inference_route_workloads(condition, "subprocess") == [
        (clients.AzureAIWorkload.INFERENCE, "gpt-audio-1.5")
    ]


def test_unknown_preprocessor_type_is_not_an_azure_workload():
    condition = {
        "model": {"provider": "openai", "deployment": "native-main"},
        "preprocessors": [
            {
                "type": "custom",
                "model": {"provider": "azure", "deployment": "unused"},
            }
        ],
    }

    assert clients.inference_route_workloads(condition, "subprocess") == []


@pytest.mark.parametrize("preprocessor_type", ["audio_analyzer", "video_analyzer"])
def test_runtime_preprocessor_rejects_explicit_null_deployment(
    preprocessor_type,
):
    condition = {
        "model": {"provider": "openai", "deployment": "native-main"},
        "preprocessors": [
            {
                "type": preprocessor_type,
                "model": {"provider": "azure", "deployment": None},
            }
        ],
    }

    with pytest.raises(ValueError, match="deployment must be a nonempty string"):
        clients.inference_route_workloads(condition, "subprocess")


@pytest.mark.parametrize(
    "condition",
    [{"model": None}, {"model": []}, {"model": "azure"}],
)
def test_code_interpreter_rejects_missing_or_malformed_model(condition):
    with pytest.raises(ValueError, match="model must be an object"):
        clients.inference_route_workloads(condition, "code_interpreter")


def test_code_interpreter_missing_model_uses_runtime_default():
    assert clients.inference_route_workloads({}, "code_interpreter") == [
        (clients.AzureAIWorkload.INFERENCE, "gpt-4"),
        (clients.AzureAIWorkload.CODE_INTERPRETER, "gpt-4"),
    ]


def test_code_interpreter_rejects_non_azure_main_provider():
    with pytest.raises(ValueError, match="requires an Azure provider"):
        clients.inference_route_workloads(
            {
                "model": {
                    "provider": "openai",
                    "deployment": "native-main",
                }
            },
            "code_interpreter",
        )


def test_grader_workloads_include_tiers_and_perception():
    config = {
        "judge": {
            "provider": "azure_openai",
            "deployment": "main",
            "perception": {
                "visual": {"model": "vision"},
                "audio": {"deployment": "audio"},
            },
        },
        "judge_routing": {
            "tier_standard": {"deployment": "standard"},
            "tier_pro": {"model": "pro"},
        },
    }

    assert clients.grader_route_workloads(config) == [
        (clients.AzureAIWorkload.GRADER, "main"),
        (clients.AzureAIWorkload.GRADER, "standard"),
        (clients.AzureAIWorkload.GRADER, "pro"),
        (clients.AzureAIWorkload.GRADER, "vision"),
        (clients.AzureAIWorkload.GRADER, "audio"),
    ]


@pytest.mark.parametrize(
    "config",
    [
        {
            "judge": {"model": "main", "deployment": "main"},
            "judge_routing": {
                "tier_pro": {"model": "pro-a", "deployment": "pro-b"}
            },
        },
        {
            "judge": {
                "model": "main",
                "deployment": "main",
                "perception": {
                    "visual": {
                        "model": "vision-a",
                        "deployment": "vision-b",
                    }
                },
            }
        },
    ],
)
def test_grader_workloads_reject_conflicting_nested_aliases(config):
    with pytest.raises(ValueError, match="must match"):
        clients.grader_route_workloads(config)


def test_non_azure_grader_has_no_azure_workload():
    assert clients.grader_route_workloads(
        {"judge": {"provider": "openai", "model": "native"}}
    ) == []


def test_narrative_workloads_include_fallbacks_and_mapping_aliases():
    assert clients.narrative_route_workloads(
        {"model": "primary", "deployment": "primary"},
        ["fallback-a", {"deployment": "fallback-b"}],
    ) == [
        (clients.AzureAIWorkload.NARRATIVE, "primary"),
        (clients.AzureAIWorkload.NARRATIVE, "fallback-a"),
        (clients.AzureAIWorkload.NARRATIVE, "fallback-b"),
    ]


def test_narrative_workloads_reject_conflicting_aliases():
    with pytest.raises(ValueError, match="must match"):
        clients.narrative_route_workloads(
            {"model": "narrative-a", "deployment": "narrative-b"}
        )


def test_direct_factory_uses_openai_constructor_and_exact_scope(monkeypatch):
    token_provider = object()
    provider_factory = MagicMock(return_value=token_provider)
    openai_client = _inference_client()
    constructor = MagicMock(return_value=openai_client)
    monkeypatch.setattr(clients, "get_bearer_token_provider", provider_factory)
    monkeypatch.setattr(clients, "OpenAI", constructor)
    credential = MagicMock()
    factory = clients.AzureAIClientFactory(
        settings=_direct_settings(),
        credential=credential,
    )

    lease = factory.create(
        "inference",
        deployment="deployment",
        timeout=31,
        max_retries=0,
    )

    constructor.assert_called_once_with(
        base_url="https://account.openai.azure.com/openai/v1/",
        api_key=token_provider,
        timeout=31,
        max_retries=0,
    )
    provider_factory.assert_called_once_with(
        credential,
        "https://ai.azure.com/.default",
    )
    credential.get_token.assert_not_called()
    assert lease.client is openai_client
    assert lease.owner is None
    assert not hasattr(lease, "factory")


def test_direct_factory_omits_none_max_retries(monkeypatch):
    constructor = MagicMock(return_value=_inference_client())
    monkeypatch.setattr(clients, "OpenAI", constructor)
    monkeypatch.setattr(
        clients,
        "get_bearer_token_provider",
        MagicMock(return_value=object()),
    )

    clients.AzureAIClientFactory(
        settings=_direct_settings(),
        credential=object(),
    ).create("inference", deployment="deployment")

    constructor.assert_called_once_with(
        base_url="https://account.openai.azure.com/openai/v1/",
        api_key=pytest.ANY if hasattr(pytest, "ANY") else constructor.call_args.kwargs["api_key"],
        timeout=clients.DEFAULT_TIMEOUT,
    )


def test_legacy_factory_uses_azure_constructor_scope_and_version(monkeypatch):
    token_provider = object()
    provider_factory = MagicMock(return_value=token_provider)
    azure_client = _responses_client()
    constructor = MagicMock(return_value=azure_client)
    monkeypatch.setattr(clients, "get_bearer_token_provider", provider_factory)
    monkeypatch.setattr(clients, "AzureOpenAI", constructor)
    credential = object()

    lease = clients.AzureAIClientFactory(
        settings=_legacy_settings(),
        credential=credential,
    ).create(
        "grader",
        deployment="deployment",
        timeout=45,
        max_retries=3,
        legacy_api_version="legacy-version",
    )

    constructor.assert_called_once_with(
        azure_endpoint="https://account.openai.azure.com/",
        azure_ad_token_provider=token_provider,
        api_version="legacy-version",
        timeout=45,
        max_retries=3,
    )
    provider_factory.assert_called_once_with(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    assert lease.client is azure_client


def test_project_factory_uses_lazy_project_client_without_api_calls(monkeypatch):
    openai_client = _code_interpreter_client()
    project = SimpleNamespace(
        get_openai_client=MagicMock(return_value=openai_client),
        close=MagicMock(),
    )
    project_class = MagicMock(return_value=project)
    provider_factory = MagicMock(return_value=object())
    monkeypatch.setattr(clients, "_load_project_client_class", lambda: project_class)
    monkeypatch.setattr(clients, "get_bearer_token_provider", provider_factory)
    credential = MagicMock()

    lease = clients.AzureAIClientFactory(
        settings=_project_settings(),
        credential=credential,
    ).create(
        "code-interpreter",
        deployment="deployment",
        timeout=52,
        max_retries=1,
    )

    project_class.assert_called_once_with(
        endpoint=(
            "https://account.services.ai.azure.com/"
            "api/projects/project-one"
        ),
        credential=credential,
    )
    project.get_openai_client.assert_called_once_with(
        timeout=52,
        max_retries=1,
    )
    provider_factory.assert_not_called()
    credential.get_token.assert_not_called()
    openai_client.responses.create.assert_not_called()
    openai_client.files.create.assert_not_called()
    openai_client.files.delete.assert_not_called()
    openai_client.files.content.assert_not_called()
    openai_client.containers.create.assert_not_called()
    assert lease.client is openai_client
    assert lease.owner is project


def test_pinned_real_project_sdk_constructs_offline_without_credential_use(
    monkeypatch,
):
    from azure.ai.projects import AIProjectClient

    expected_versions = {
        "openai": "2.46.0",
        "azure-core": "1.41.0",
        "azure-identity": "1.25.3",
        "azure-ai-projects": "2.3.0",
    }
    assert {
        package: importlib.metadata.version(package)
        for package in expected_versions
    } == expected_versions

    class FakeSyncCredential:
        def __init__(self):
            self.get_token_calls = 0
            self.close_calls = 0

        def get_token(self, *_scopes, **_kwargs):
            self.get_token_calls += 1
            raise AssertionError("offline construction must not request a token")

        def close(self):
            self.close_calls += 1

    endpoint = (
        "https://account.services.ai.azure.com/api/projects/project-one"
    )
    credential = FakeSyncCredential()
    network_send = MagicMock(
        side_effect=AssertionError("offline construction must not use network")
    )
    monkeypatch.setattr("httpx.Client.send", network_send)
    monkeypatch.setattr("requests.sessions.Session.send", network_send)
    project = AIProjectClient(endpoint=endpoint, credential=credential)
    openai_client = None
    try:
        openai_client = project.get_openai_client(
            timeout=480,
            max_retries=0,
        )
        assert str(openai_client.base_url) == f"{endpoint}/openai/v1/"
        clients.validate_client_capabilities(
            openai_client,
            clients.AzureAIWorkload.CODE_INTERPRETER,
        )
        assert callable(openai_client.files.delete)
        assert callable(openai_client.files.content)
    finally:
        if openai_client is not None:
            openai_client.close()
        project.close()

    assert credential.get_token_calls == 0
    assert credential.close_calls == 0
    network_send.assert_not_called()


def test_factory_and_lease_document_sync_lifetime_and_thread_safety():
    factory_doc = clients.AzureAIClientFactory.__doc__ or ""
    lease_doc = clients.AzureAIClientLease.__doc__ or ""

    for doc in (factory_doc, lease_doc):
        assert "synchronous" in doc
        assert "not thread-safe" in doc
    assert "survives lease closure and failed client construction" in factory_doc
    assert "Async close implementations are rejected" in factory_doc


def _foundation_record(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.name != "CHANGELOG.md":
        return text
    start = text.index("- **Typed Azure AI endpoint foundation**")
    end = text.index("\n\n### Changed", start)
    return text[start:end]


@pytest.mark.parametrize("path", FOUNDATION_DOCS, ids=lambda path: path.name)
def test_foundation_docs_use_precise_credential_and_provenance_language(path):
    record = " ".join(_foundation_record(path).split())
    lowered = record.lower()

    assert "DefaultAzureCredential" in record
    assert "endpoint-free" in record
    assert "redacted provenance" in record
    assert "not a confidentiality boundary" in record
    assert "not a secret" in record
    assert "CodeInterpreterRunner is Azure-only" in record
    assert "NOT WIRED" in record
    for requirement in (
        "openai==2.46.0",
        "azure-core==1.41.0",
        "azure-identity==1.25.3",
        "azure-ai-projects==2.3.0",
    ):
        assert requirement in record
    for prohibited in ("cannot disclose", "oidc-only", "tested api"):
        assert prohibited not in lowered


def test_shared_factory_survives_lease_close_and_can_create_again(monkeypatch):
    first_client = _inference_client()
    second_client = _inference_client()
    constructor = MagicMock(side_effect=[first_client, second_client])
    monkeypatch.setattr(clients, "OpenAI", constructor)
    monkeypatch.setattr(
        clients,
        "get_bearer_token_provider",
        MagicMock(return_value=object()),
    )
    credential = MagicMock()
    factory = clients.AzureAIClientFactory(
        settings=_direct_settings(),
        credential=credential,
    )

    first_lease = factory.create("inference", deployment="first")
    first_lease.close()
    second_lease = factory.create("inference", deployment="second")

    first_client.close.assert_called_once_with()
    credential.close.assert_not_called()
    assert second_lease.client is second_client
    assert constructor.call_count == 2


def test_shared_factory_survives_failed_create(monkeypatch):
    broken_client = SimpleNamespace(close=MagicMock())
    healthy_client = _responses_client()
    constructor = MagicMock(side_effect=[broken_client, healthy_client])
    monkeypatch.setattr(clients, "OpenAI", constructor)
    monkeypatch.setattr(
        clients,
        "get_bearer_token_provider",
        MagicMock(return_value=object()),
    )
    credential = MagicMock()
    factory = clients.AzureAIClientFactory(
        settings=_direct_settings(),
        credential=credential,
    )

    with pytest.raises(RuntimeError, match="responses.create"):
        factory.create("grader", deployment="broken")
    lease = factory.create("grader", deployment="healthy")

    broken_client.close.assert_called_once_with()
    credential.close.assert_not_called()
    assert lease.client is healthy_client


def test_owned_credential_closes_only_when_factory_closes(monkeypatch):
    credential = MagicMock()
    client = _inference_client()
    monkeypatch.setattr(clients, "DefaultAzureCredential", lambda: credential)
    monkeypatch.setattr(clients, "OpenAI", MagicMock(return_value=client))
    monkeypatch.setattr(
        clients,
        "get_bearer_token_provider",
        MagicMock(return_value=object()),
    )
    factory = clients.AzureAIClientFactory(settings=_direct_settings())
    lease = factory.create("inference", deployment="deployment")

    lease.close()
    credential.close.assert_not_called()
    factory.close()
    factory.close()

    credential.close.assert_called_once_with()


def test_failed_create_does_not_close_owned_credential(monkeypatch):
    credential = MagicMock()
    broken_client = SimpleNamespace(close=MagicMock())
    monkeypatch.setattr(clients, "DefaultAzureCredential", lambda: credential)
    monkeypatch.setattr(
        clients,
        "OpenAI",
        MagicMock(return_value=broken_client),
    )
    monkeypatch.setattr(
        clients,
        "get_bearer_token_provider",
        MagicMock(return_value=object()),
    )
    factory = clients.AzureAIClientFactory(settings=_direct_settings())

    with pytest.raises(RuntimeError, match="responses.create"):
        factory.create("grader", deployment="deployment")

    broken_client.close.assert_called_once_with()
    credential.close.assert_not_called()
    factory.close()
    credential.close.assert_called_once_with()


def test_injected_credential_is_never_closed_by_factory(monkeypatch):
    credential = MagicMock()
    monkeypatch.setattr(
        clients,
        "OpenAI",
        MagicMock(return_value=_inference_client()),
    )
    monkeypatch.setattr(
        clients,
        "get_bearer_token_provider",
        MagicMock(return_value=object()),
    )

    with clients.AzureAIClientFactory(
        settings=_direct_settings(),
        credential=credential,
    ) as factory:
        lease = factory.create("inference", deployment="deployment")
        lease.close()

    credential.close.assert_not_called()


def test_closed_factory_rejects_create():
    factory = clients.AzureAIClientFactory(
        settings=_direct_settings(),
        credential=object(),
    )
    factory.close()

    with pytest.raises(RuntimeError, match="factory is closed"):
        factory.create("inference", deployment="deployment")


def test_project_failure_closes_client_and_project_not_credential(monkeypatch):
    broken_client = SimpleNamespace(
        responses=SimpleNamespace(create=MagicMock()),
        files=SimpleNamespace(
            create=MagicMock(),
            delete=MagicMock(),
            content=MagicMock(),
        ),
        close=MagicMock(),
    )
    project = SimpleNamespace(
        get_openai_client=MagicMock(return_value=broken_client),
        close=MagicMock(),
    )
    monkeypatch.setattr(
        clients,
        "_load_project_client_class",
        lambda: MagicMock(return_value=project),
    )
    credential = MagicMock()
    factory = clients.AzureAIClientFactory(
        settings=_project_settings(),
        credential=credential,
    )

    with pytest.raises(RuntimeError, match="containers.create"):
        factory.create("code-interpreter", deployment="deployment")

    broken_client.close.assert_called_once_with()
    project.close.assert_called_once_with()
    credential.close.assert_not_called()


def test_project_get_client_failure_closes_partial_project(monkeypatch):
    project = SimpleNamespace(
        get_openai_client=MagicMock(side_effect=RuntimeError("creation failed")),
        close=MagicMock(),
    )
    monkeypatch.setattr(
        clients,
        "_load_project_client_class",
        lambda: MagicMock(return_value=project),
    )
    credential = MagicMock()
    factory = clients.AzureAIClientFactory(
        settings=_project_settings(),
        credential=credential,
    )

    with pytest.raises(RuntimeError, match="creation failed"):
        factory.create("code-interpreter", deployment="deployment")

    project.close.assert_called_once_with()
    credential.close.assert_not_called()


def test_lease_close_attempts_project_after_client_failure():
    client = _code_interpreter_client()
    client.close.side_effect = RuntimeError("client close failed")
    project = SimpleNamespace(close=MagicMock())
    lease = clients.AzureAIClientLease(
        client=client,
        owner=project,
        route=MagicMock(),
        runtime_fingerprint="f" * 64,
    )

    with pytest.raises(RuntimeError, match="client close failed"):
        lease.close()

    project.close.assert_called_once_with()


def test_lease_close_is_idempotent_and_deduplicates_owner():
    client = _inference_client()
    lease = clients.AzureAIClientLease(
        client=client,
        owner=client,
        route=MagicMock(),
        runtime_fingerprint="f" * 64,
    )

    lease.close()
    lease.close()

    client.close.assert_called_once_with()


def test_lease_rejects_async_close_method_and_still_closes_owner():
    class AsyncClient:
        async def close(self):
            return None

    project = SimpleNamespace(close=MagicMock())
    lease = clients.AzureAIClientLease(
        client=AsyncClient(),
        owner=project,
        route=MagicMock(),
        runtime_fingerprint="f" * 64,
    )

    with pytest.raises(RuntimeError, match="does not support async client close"):
        lease.close()

    project.close.assert_called_once_with()


def test_lease_closes_awaitable_result_without_unawaited_warning():
    async def async_close():
        return None

    class AwaitableCloseClient:
        def close(self):
            return async_close()

    lease = clients.AzureAIClientLease(
        client=AwaitableCloseClient(),
        owner=None,
        route=MagicMock(),
        runtime_fingerprint="f" * 64,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeError, match="does not support async client close"):
            lease.close()
        gc.collect()

    assert not [
        warning
        for warning in caught
        if "was never awaited" in str(warning.message)
    ]


def test_factory_rejects_async_owned_credential_close():
    class AsyncCredential:
        async def close(self):
            return None

    factory = clients.AzureAIClientFactory(
        settings=_direct_settings(),
        credential=object(),
    )
    factory.credential = AsyncCredential()
    factory._owns_credential = True

    with pytest.raises(RuntimeError, match="async credential close"):
        factory.close()

    factory.close()


@pytest.mark.parametrize(
    ("workload", "client", "missing"),
    [
        (
            clients.AzureAIWorkload.INFERENCE,
            SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace())),
            "chat.completions.create",
        ),
        (
            clients.AzureAIWorkload.NARRATIVE,
            SimpleNamespace(responses=SimpleNamespace()),
            "responses.create",
        ),
        (
            clients.AzureAIWorkload.CODE_INTERPRETER,
            SimpleNamespace(
                responses=SimpleNamespace(create=lambda: None),
                files=SimpleNamespace(
                    create=lambda: None,
                    delete=lambda: None,
                    content=lambda: None,
                ),
                containers=SimpleNamespace(create=lambda: None),
            ),
            "containers.files.list",
        ),
    ],
)
def test_capability_validation_reports_missing_paths(workload, client, missing):
    with pytest.raises(RuntimeError, match=missing):
        clients.validate_client_capabilities(client, workload)


def test_capability_validation_requires_callable_operation():
    client = SimpleNamespace(
        responses=SimpleNamespace(create=object()),
    )

    with pytest.raises(RuntimeError, match="responses.create"):
        clients.validate_client_capabilities(
            client,
            clients.AzureAIWorkload.GRADER,
        )


@pytest.mark.parametrize(
    "missing",
    [
        "responses.create",
        "files.create",
        "files.delete",
        "files.content",
        "containers.create",
        "containers.files.list",
        "containers.files.content.retrieve",
    ],
)
def test_code_interpreter_capability_requires_every_operation(missing):
    client = SimpleNamespace(
        responses=SimpleNamespace(create=lambda: None),
        files=SimpleNamespace(
            create=lambda: None,
            delete=lambda: None,
            content=lambda: None,
        ),
        containers=SimpleNamespace(
            create=lambda: None,
            files=SimpleNamespace(
                list=lambda: None,
                content=SimpleNamespace(retrieve=lambda: None),
            ),
        ),
    )
    parent = client
    parts = missing.split(".")
    for part in parts[:-1]:
        parent = getattr(parent, part)
    delattr(parent, parts[-1])

    with pytest.raises(RuntimeError, match=re.escape(missing)):
        clients.validate_client_capabilities(
            client,
            clients.AzureAIWorkload.CODE_INTERPRETER,
        )


def test_verify_direct_token_uses_scope_without_closing_injected_credential():
    credential = MagicMock()

    clients.verify_direct_token(credential)

    credential.get_token.assert_called_once_with(
        "https://ai.azure.com/.default"
    )
    credential.close.assert_not_called()


@pytest.mark.parametrize("name", clients.FORBIDDEN_API_KEY_ENV)
def test_owned_token_check_rejects_process_static_secret_before_credential(
    name, monkeypatch
):
    constructor = MagicMock()
    monkeypatch.setattr(clients, "DefaultAzureCredential", constructor)
    monkeypatch.setenv(name, "not-a-real-secret")

    with pytest.raises(ValueError, match="forbidden") as error:
        clients.verify_direct_token()

    constructor.assert_not_called()
    assert "not-a-real-secret" not in str(error.value)