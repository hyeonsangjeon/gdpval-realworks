import os
import time

from openai import AzureOpenAI

from core.config import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    DEFAULT_DEPLOYMENT,
    DEFAULT_API_VERSION,
    DEFAULT_TOKENS,
)


# ─── Anthropic Response Wrapper (OpenAI-compatible interface) ─────────────

class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Usage:
    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class NormalizedResponse:
    """OpenAI-compatible response wrapper for non-OpenAI providers."""
    def __init__(self, content: str, model: str = "", usage=None):
        self.choices = [_Choice(content)]
        self.model = model
        self.usage = usage or _Usage()


# ─── Anthropic Client Wrapper ─────────────────────────────────────────────

class AnthropicClient:
    """Anthropic Claude client with OpenAI-compatible interface.

    Usage:
        client = AnthropicClient()
        response, latency_ms = complete(client, "claude-opus-4-5", messages)
        text = response.choices[0].message.content
    """

    def __init__(self, api_key: str | None = None, timeout: int = 480):
        try:
            import anthropic
            self.client = anthropic.Anthropic(
                api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
                timeout=timeout,  # 8min — prevent hang before GitHub Actions 10min no-output kill
            )
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

    def chat_complete(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = DEFAULT_TOKENS["code_generation"],
        **kwargs,
    ) -> NormalizedResponse:
        """Call Anthropic API with OpenAI-style messages."""
        system_prompt = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                user_messages.append({"role": msg["role"], "content": msg["content"]})

        # Remove OpenAI-specific kwargs that Anthropic doesn't support
        kwargs_filtered = {
            k: v for k, v in kwargs.items()
            if k not in ("seed", "max_completion_tokens")
        }

        create_kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            messages=user_messages,
            **kwargs_filtered,
        )
        if system_prompt:
            create_kwargs["system"] = system_prompt

        response = self.client.messages.create(**create_kwargs)

        content = response.content[0].text if response.content else ""
        usage = _Usage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )
        return NormalizedResponse(content=content, model=response.model, usage=usage)


# ─── Client Factory ──────────────────────────────────────────────────────

def create_client(
    endpoint: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
) -> AzureOpenAI:
    """AzureOpenAI 클라이언트 생성 (하위 호환성 유지)

    모든 Azure AI 모델(GPT, Grok, Claude)에 동일하게 사용.
    endpoint만 바꾸면 다른 모델 호출 가능.

    Args:
        endpoint:    Azure endpoint (기본: AZURE_OPENAI_ENDPOINT 환경변수)
        api_key:     API key       (기본: AZURE_API_KEY 환경변수)
        api_version: API version   (기본: 2025-04-01-preview)

    Returns:
        openai.AzureOpenAI 클라이언트
    """
    return AzureOpenAI(
        azure_endpoint=endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", DEFAULT_ENDPOINT),
        api_key=api_key or os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY"),
        api_version=api_version or DEFAULT_API_VERSION,
        timeout=480,  # 8min — prevent hang before GitHub Actions 10min no-output kill
    )


def create_provider_client(
    provider: str,
    endpoint: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
):
    """Provider별 클라이언트 생성.

    Args:
        provider:    "azure" | "openai" | "anthropic"
        endpoint:    API endpoint (Azure/OpenAI only)
        api_key:     API key
        api_version: API version (Azure only)

    Returns:
        AzureOpenAI, openai.OpenAI, or AnthropicClient instance

    Environment variables (provider별):
        azure:     AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY
        openai:    OPENAI_API_KEY
        anthropic: ANTHROPIC_API_KEY
    """
    if provider in ("azure", "azure_openai"):
        return create_client(
            endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )

    elif provider == "openai":
        from openai import OpenAI
        return OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=endpoint or None,
            timeout=480,
        )

    elif provider == "anthropic":
        return AnthropicClient(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            timeout=480,  # 8min — prevent hang before GitHub Actions 10min no-output kill
        )

    else:
        raise ValueError(
            f"Unsupported provider: '{provider}'. "
            f"Must be one of: azure, openai, anthropic"
        )


# ─── Completion Helper ───────────────────────────────────────────────────

def complete(
    client,
    model: str,
    messages: list[dict],
    max_completion_tokens: int = DEFAULT_TOKENS["code_generation"],
    **kwargs,
) -> tuple:
    """Provider-agnostic chat completion with latency measurement.

    Supports AzureOpenAI, openai.OpenAI, and AnthropicClient.

    Args:
        client:   AzureOpenAI | openai.OpenAI | AnthropicClient
        model:    deployment/model name (e.g., "gpt-5.2-chat", "claude-opus-4-5")
        messages: [{"role": "...", "content": "..."}] 형태
        max_completion_tokens: 최대 completion 토큰 (기본: 16384)
        **kwargs: temperature 등 추가 파라미터

    Returns:
        (response, latency_ms) tuple
        - response: OpenAI ChatCompletion 객체 또는 NormalizedResponse
        - latency_ms: 응답 시간 (밀리초)
    """
    start = time.time()

    if isinstance(client, AnthropicClient):
        response = client.chat_complete(
            model=model,
            messages=messages,
            max_tokens=max_completion_tokens,
            **kwargs,
        )
    else:
        # AzureOpenAI or openai.OpenAI
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            **kwargs,
        )

    latency_ms = (time.time() - start) * 1000
    return response, latency_ms
