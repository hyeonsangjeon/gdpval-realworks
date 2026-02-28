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

from core.llm_client import create_client, complete
from core.config import (
    DEFAULT_ENDPOINT,
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

    def test_default_endpoint(self):
        assert "openai.azure.com" in DEFAULT_ENDPOINT

    def test_default_model(self):
        assert DEFAULT_MODEL == "gpt-5.2-chat"

    def test_default_api_version(self):
        assert DEFAULT_API_VERSION == "2025-04-01-preview"

    def test_default_max_tokens(self):
        assert DEFAULT_TOKENS["code_generation"] == 16384


# ─── create_client Tests ─────────────────────────────────────────────────

class TestCreateClient:
    """create_client() 팩토리 함수 테스트"""

    @patch("core.llm_client.AzureOpenAI")
    def test_explicit_params(self, mock_cls):
        """명시적 파라미터로 클라이언트 생성"""
        client = create_client(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2024-12-01-preview",
        )
        mock_cls.assert_called_once_with(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2024-12-01-preview",
        )

    @patch("core.llm_client.AzureOpenAI")
    def test_defaults_from_env(self, mock_cls):
        """환경변수 fallback"""
        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://env-endpoint.azure.com/",
            "AZURE_API_KEY": "env-key",
        }):
            create_client()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["azure_endpoint"] == "https://env-endpoint.azure.com/"
            assert call_kwargs["api_key"] == "env-key"
            assert call_kwargs["api_version"] == DEFAULT_API_VERSION

    @patch("core.llm_client.AzureOpenAI")
    def test_returns_azure_openai_instance(self, mock_cls):
        """반환 타입이 AzureOpenAI mock 인스턴스"""
        client = create_client(endpoint="https://x.com/", api_key="k")
        assert client == mock_cls.return_value

    @patch("core.llm_client.AzureOpenAI")
    def test_grok_different_endpoint(self, mock_cls):
        """Grok용 다른 endpoint — 같은 SDK"""
        create_client(
            endpoint="https://grok-resource.azure.com/",
            api_key="grok-key",
        )
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["azure_endpoint"] == "https://grok-resource.azure.com/"
        assert call_kwargs["api_key"] == "grok-key"


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
    """실제 Azure OpenAI API를 사용하는 통합 테스트

    실행 전 환경변수 필요:
        export AZURE_API_KEY="your-key"
        export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"

    실행:
        pytest -m integration -v
    """

    @pytest.fixture
    def client(self):
        """환경변수에서 AzureOpenAI 클라이언트 생성"""
        api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")

        if not api_key or not endpoint:
            pytest.skip("Azure credentials not set. Set AZURE_API_KEY and AZURE_OPENAI_ENDPOINT.")

        return create_client(endpoint=endpoint, api_key=api_key)

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
