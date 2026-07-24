"""Tests for LLM Client (openai.AzureOpenAI 기반)

Usage:
    pytest                          # mock only (CI default)
    pytest -m integration           # real Azure OpenAI API (needs credentials)
    pytest -m ""                    # all tests
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from core.llm_client import (
    ManagedAzureAIClient,
    close_provider_client,
    complete,
    create_client,
    create_provider_client,
    create_typed_azure_client,
)
from core.config import (
    DEFAULT_MODEL,
    DEFAULT_API_VERSION,
    DEFAULT_TOKENS,
)


# ─── Helpers ──────────────────────────────────────────────────────────────

def _make_mock_response(content="Hello from Azure!", model="gpt-5.2-chat-2025-12-11"):
    """mock openai ChatCompletion 응답 생성"""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.model = model
    resp.usage = SimpleNamespace(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    resp.model_dump.return_value = {
        "id": "chatcmpl-123",
        "model": model,
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return resp


# ─── Constants Tests ──────────────────────────────────────────────────────

class TestDefaults:
    """기본 설정값 테스트"""

    def test_default_model(self):
        assert DEFAULT_MODEL == "gpt-5.2-chat"

    def test_default_api_version(self):
        assert DEFAULT_API_VERSION == "2025-04-01-preview"

    def test_default_max_tokens(self):
        assert DEFAULT_TOKENS["code_generation"] == 16384


# ─── create_client Tests ─────────────────────────────────────────────────

class TestCreateClient:
    """create_client() 팩토리 함수 테스트"""

    @patch("core.llm_client.AzureAIClientFactory")
    def test_returns_managed_typed_client(self, factory_cls):
        lease = _FakeLease()
        factory_cls.return_value.create.return_value = lease

        client = create_client(deployment="deployment")

        assert isinstance(client, ManagedAzureAIClient)
        assert client.client is lease.client
        factory_cls.return_value.create.assert_called_once_with(
            "inference",
            deployment="deployment",
            timeout=480.0,
            max_retries=None,
            legacy_api_version=DEFAULT_API_VERSION,
        )

    def test_endpoint_override_is_rejected(self):
        with pytest.raises(ValueError, match="overrides are forbidden"):
            create_client(endpoint="https://account.openai.azure.com/")

    def test_api_key_argument_is_rejected(self):
        with pytest.raises(ValueError, match="API keys are forbidden"):
            create_client(api_key="not-a-real-key")

    @patch("core.llm_client.AzureAIClientFactory")
    def test_explicit_zero_transport_retries_reach_typed_factory(
        self, factory_cls
    ):
        factory_cls.return_value.create.return_value = _FakeLease()

        create_provider_client(
            "azure",
            deployment="deployment",
            max_retries=0,
        )

        assert factory_cls.return_value.create.call_args.kwargs[
            "max_retries"
        ] == 0

    def test_explicit_zero_transport_retries_reach_openai_sdk(self):
        openai_module = MagicMock()
        with patch.dict("sys.modules", {"openai": openai_module}):
            create_provider_client("openai", api_key="test", max_retries=0)

        assert openai_module.OpenAI.call_args.kwargs["max_retries"] == 0

    def test_close_provider_client_delegates_to_managed_client(self):
        client = MagicMock()

        from core.llm_client import close_provider_client

        close_provider_client(client)

        client.close.assert_called_once_with()


# ─── typed Azure client adapter tests ────────────────────────────────────

class _FakeLease:
    def __init__(self, events=None, close_error=None):
        self.response_create = MagicMock()
        self.client = SimpleNamespace(
            responses=SimpleNamespace(create=self.response_create),
            marker="raw-client",
        )
        self.route = object()
        self.runtime_fingerprint = "f" * 64
        self.events = events if events is not None else []
        self.close_error = close_error
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        self.events.append("lease")
        if self.close_error is not None:
            raise self.close_error


class _FakeFactory:
    def __init__(self, lease=None, events=None, create_error=None, close_error=None):
        self.lease = lease or _FakeLease()
        self.events = events if events is not None else []
        self.create_error = create_error
        self.close_error = close_error
        self.create_calls = []
        self.close_calls = 0

    def create(self, workload, **kwargs):
        self.create_calls.append((workload, kwargs))
        if self.create_error is not None:
            raise self.create_error
        return self.lease

    def close(self):
        self.close_calls += 1
        self.events.append("factory")
        if self.close_error is not None:
            raise self.close_error


def test_typed_client_owned_factory_delegates_and_closes_in_order():
    events = []
    lease = _FakeLease(events=events)
    factory = _FakeFactory(lease=lease, events=events)
    settings = object()

    with patch("core.llm_client.AzureAIClientFactory", return_value=factory) as constructor:
        client = create_typed_azure_client(
            "inference",
            "deployment",
            settings=settings,
            timeout=30,
            max_retries=0,
            legacy_api_version="legacy-version",
        )

    constructor.assert_called_once_with(settings=settings)
    assert client.client is lease.client
    assert client.responses is lease.client.responses
    assert client.marker == "raw-client"
    assert client.route is lease.route
    assert client.runtime_fingerprint == "f" * 64
    assert factory.create_calls == [(
        "inference",
        {
            "deployment": "deployment",
            "timeout": 30,
            "max_retries": 0,
            "legacy_api_version": "legacy-version",
        },
    )]

    client.close()
    client.close()

    assert events == ["lease", "factory"]
    assert lease.close_calls == 1
    assert factory.close_calls == 1


def test_typed_client_rejects_all_public_access_after_close():
    lease = _FakeLease()
    client = ManagedAzureAIClient(lease)
    client.close()

    for access in (
        lambda: client.client,
        lambda: client.route,
        lambda: client.runtime_fingerprint,
        lambda: client.responses.create(),
        lambda: client.__enter__(),
    ):
        with pytest.raises(RuntimeError) as error:
            access()
        assert str(error.value) == "managed Azure AI client is closed"

    lease.response_create.assert_not_called()


def test_typed_client_shared_factory_remains_caller_owned():
    lease = _FakeLease()
    factory = _FakeFactory(lease=lease)

    with create_typed_azure_client(
        "grader",
        "deployment",
        factory=factory,
    ) as client:
        assert isinstance(client, ManagedAzureAIClient)

    assert lease.close_calls == 1
    assert factory.close_calls == 0


def test_typed_client_close_attempts_owned_factory_and_raises_first_error():
    events = []
    lease = _FakeLease(events=events, close_error=RuntimeError("lease failed"))
    factory = _FakeFactory(
        lease=lease,
        events=events,
        close_error=RuntimeError("factory failed"),
    )
    client = ManagedAzureAIClient(lease, owned_factory=factory)

    with pytest.raises(RuntimeError, match="lease failed"):
        client.close()

    assert events == ["lease", "factory"]


def test_typed_client_owned_factory_closes_on_create_failure():
    creation_error = RuntimeError("creation failed")
    factory = _FakeFactory(create_error=creation_error)

    with patch("core.llm_client.AzureAIClientFactory", return_value=factory):
        with pytest.raises(RuntimeError) as caught:
            create_typed_azure_client("inference", "deployment")

    assert caught.value is creation_error
    assert caught.value.__cause__ is None
    assert factory.close_calls == 1


def test_typed_client_owned_factory_close_failure_is_primary():
    creation_error = RuntimeError("creation failed")
    close_error = OSError("factory close failed")
    factory = _FakeFactory(
        create_error=creation_error,
        close_error=close_error,
    )

    with patch("core.llm_client.AzureAIClientFactory", return_value=factory):
        with pytest.raises(OSError) as caught:
            create_typed_azure_client("inference", "deployment")

    assert caught.value is close_error
    assert caught.value.__cause__ is creation_error
    assert factory.close_calls == 1


def test_typed_client_shared_factory_survives_create_failure():
    creation_error = RuntimeError("creation failed")
    factory = _FakeFactory(create_error=creation_error)

    with pytest.raises(RuntimeError) as caught:
        create_typed_azure_client(
            "inference",
            "deployment",
            factory=factory,
        )

    assert caught.value is creation_error
    assert factory.close_calls == 0


def test_typed_client_rejects_factory_and_settings_ambiguity():
    with pytest.raises(ValueError, match="mutually exclusive"):
        create_typed_azure_client(
            "inference",
            "deployment",
            factory=_FakeFactory(),
            settings=object(),
        )


def test_create_provider_client_forwards_typed_azure_identity():
    sentinel = object()
    with patch("core.llm_client.create_client", return_value=sentinel) as legacy:
        result = create_provider_client(
            "azure",
            endpoint="https://example.invalid",
            api_key="ignored",
            api_version="version",
            max_retries=0,
            deployment="deployment",
            workload="grader",
        )

    assert result is sentinel
    legacy.assert_called_once_with(
        endpoint="https://example.invalid",
        api_key="ignored",
        api_version="version",
        max_retries=0,
        deployment="deployment",
        workload="grader",
    )


# ─── complete() Tests ────────────────────────────────────────────────────

class TestComplete:
    """complete() 헬퍼 함수 테스트"""

    def test_basic_call(self):
        """기본 호출 — response + latency 반환"""
        mock_client = MagicMock()
        mock_resp = _make_mock_response()
        mock_client.chat.completions.create.return_value = mock_resp

        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Say hello"},
        ]
        response, latency_ms = complete(mock_client, "gpt-5.2-chat", messages)

        assert response.choices[0].message.content == "Hello from Azure!"
        assert response.model == "gpt-5.2-chat-2025-12-11"
        assert latency_ms >= 0
        assert isinstance(latency_ms, float)

    def test_passes_model_and_messages(self):
        """model, messages가 SDK에 정확히 전달"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()

        messages = [{"role": "user", "content": "Hi"}]
        complete(mock_client, "grok-3", messages)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "grok-3"
        assert call_kwargs["messages"] == messages

    def test_default_max_tokens(self):
        """기본 max_completion_tokens == 16384"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()

        complete(mock_client, "gpt-5.2-chat", [{"role": "user", "content": "x"}])

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_completion_tokens"] == 16384

    def test_custom_max_tokens(self):
        """max_completion_tokens 오버라이드"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()

        complete(
            mock_client, "gpt-5.2-chat",
            [{"role": "user", "content": "x"}],
            max_completion_tokens=1024,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["max_completion_tokens"] == 1024

    def test_extra_kwargs_passed_through(self):
        """temperature 등 추가 파라미터 전달"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()

        complete(
            mock_client, "gpt-5.2-chat",
            [{"role": "user", "content": "x"}],
            temperature=0.7,
            top_p=0.9,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["top_p"] == 0.9

    def test_multi_turn_messages(self):
        """멀티턴 대화 메시지"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()

        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "My name is Alice"},
            {"role": "assistant", "content": "Hello Alice!"},
            {"role": "user", "content": "What is my name?"},
        ]
        complete(mock_client, "gpt-5.2-chat", messages)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert len(call_kwargs["messages"]) == 4
        assert call_kwargs["messages"][2]["role"] == "assistant"

    def test_latency_measured(self):
        """latency 양수"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()

        _, latency_ms = complete(
            mock_client, "gpt-5.2-chat",
            [{"role": "user", "content": "x"}],
        )

        assert latency_ms >= 0

    def test_returns_raw_sdk_response(self):
        """반환값이 openai SDK 원본 응답 (래핑 없음)"""
        mock_client = MagicMock()
        mock_resp = _make_mock_response()
        mock_client.chat.completions.create.return_value = mock_resp

        response, _ = complete(
            mock_client, "gpt-5.2-chat",
            [{"role": "user", "content": "x"}],
        )

        # response는 SDK 원본 그대로
        assert response is mock_resp
        assert response.usage.total_tokens == 15


# ─── Integration Tests (실제 Azure 연결) ──────────────────────────────────

@pytest.mark.integration
class TestIntegration:
    """실제 typed Azure AI route를 사용하는 통합 테스트

    실행 전 환경변수 필요:
        az login
        export AZURE_AI_ROUTE_PROFILE="direct-v1"
        export AZURE_OPENAI_V1_ENDPOINT="https://resource.services.ai.azure.com/openai/v1/"

    실행:
        pytest -m integration -v
    """

    @pytest.fixture
    def client(self, model):
        if not os.getenv("AZURE_AI_ROUTE_PROFILE") or not os.getenv(
            "AZURE_OPENAI_V1_ENDPOINT"
        ):
            pytest.skip("typed Azure AI route env is not configured")
        client = create_client(deployment=model)
        yield client
        close_provider_client(client)

    @pytest.fixture
    def model(self):
        return os.getenv("AZURE_OPENAI_DEPLOYMENT") or DEFAULT_MODEL

    def test_simple_call(self, client, model):
        """간단한 호출"""
        resp, latency = complete(client, model, [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Say 'Hello, World!' in exactly those words."},
        ])

        assert resp.choices[0].message.content is not None
        assert len(resp.choices[0].message.content) > 0
        assert latency > 0

        print(f"\n  Model: {resp.model}")
        print(f"  Response: {resp.choices[0].message.content}")
        print(f"  Tokens: {resp.usage.total_tokens}")
        print(f"  Latency: {latency:.2f}ms")

    def test_system_prompt(self, client, model):
        """system prompt 동작 확인"""
        resp, _ = complete(client, model, [
            {"role": "system", "content": "You are a math tutor. Always respond with just the numerical answer."},
            {"role": "user", "content": "What is 2 + 2?"},
        ])

        assert "4" in resp.choices[0].message.content
        print(f"\n  Math response: {resp.choices[0].message.content}")

    def test_multi_turn(self, client, model):
        """멀티턴 대화"""
        resp, _ = complete(client, model, [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Hello Alice! How can I help you?"},
            {"role": "user", "content": "What is my name?"},
        ])

        assert "Alice" in resp.choices[0].message.content
        print(f"\n  Multi-turn: {resp.choices[0].message.content}")

    def test_multiple_calls(self, client, model):
        """연속 호출"""
        latencies = []
        for i in range(3):
            resp, latency = complete(client, model, [
                {"role": "user", "content": f"Count: {i+1}"},
            ])
            assert resp.choices[0].message.content is not None
            latencies.append(latency)

        print(f"\n  Average latency: {sum(latencies)/len(latencies):.2f}ms")

    def test_usage_tracking(self, client, model):
        """토큰 사용량 확인"""
        resp, _ = complete(client, model, [
            {"role": "user", "content": "Tell me a very short joke (one sentence)."},
        ])

        assert resp.usage.prompt_tokens > 0
        assert resp.usage.completion_tokens > 0
        assert resp.usage.total_tokens == resp.usage.prompt_tokens + resp.usage.completion_tokens

        print(f"\n  Prompt: {resp.usage.prompt_tokens}, "
              f"Completion: {resp.usage.completion_tokens}, "
              f"Total: {resp.usage.total_tokens}")

    def test_raw_response(self, client, model):
        """SDK 원본 응답 구조"""
        resp, _ = complete(client, model, [
            {"role": "user", "content": "Say hello."},
        ])

        raw = resp.model_dump()
        assert "id" in raw
        assert "model" in raw
        assert "choices" in raw
        assert "usage" in raw
        print(f"\n  Response ID: {raw['id']}")
