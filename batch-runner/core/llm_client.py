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
    def __init__(self, content: str, finish_reason: str | None = None):
        self.message = _Message(content)
        self.finish_reason = finish_reason


class _Usage:
    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class NormalizedResponse:
    """OpenAI-compatible response wrapper for non-OpenAI providers."""
    def __init__(self, content: str, model: str = "", usage=None, finish_reason: str | None = None):
        self.choices = [_Choice(content, finish_reason=finish_reason)]
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
            if k not in ("seed", "max_completion_tokens", "reasoning_effort")
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

        # Anthropic returns a list of content blocks. Extended thinking and
        # tool use produce ThinkingBlock / ToolUseBlock objects that have no
        # `.text` attribute — accessing response.content[0].text on those
        # would raise AttributeError. Concatenate the text from all text blocks
        # and skip the rest.
        text_parts = []
        for block in (response.content or []):
            if getattr(block, "type", None) == "text":
                text_parts.append(getattr(block, "text", ""))
        content = "".join(text_parts)

        # Map Anthropic stop_reason to OpenAI-style finish_reason so callers
        # that check choices[0].finish_reason == "length" (truncation guard)
        # work for both providers.
        finish_reason = self._map_stop_reason(getattr(response, "stop_reason", None))

        usage = _Usage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )
        return NormalizedResponse(
            content=content,
            model=response.model,
            usage=usage,
            finish_reason=finish_reason,
        )

    @staticmethod
    def _map_stop_reason(stop_reason: str | None) -> str | None:
        """Translate Anthropic stop_reason to OpenAI-style finish_reason.

        Anthropic values: "end_turn", "max_tokens", "stop_sequence", "tool_use".
        OpenAI values:    "stop", "length", "tool_calls", ...
        """
        if stop_reason is None:
            return None
        mapping = {
            "max_tokens": "length",
            "end_turn": "stop",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
        }
        return mapping.get(stop_reason, stop_reason)


# ─── Client Factory ──────────────────────────────────────────────────────

def create_client(
    endpoint: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
) -> AzureOpenAI:
    """AzureOpenAI 클라이언트 생성 (DefaultAzureCredential 전용 / OIDC only)

    인증 정책:
    - DefaultAzureCredential (Entra ID 토큰) — az login / Managed Identity / OIDC 전용
    - API Key fallback 비활성화 (Azure 리소스 disableLocalAuth=true). 또한 openai SDK 가
      AZURE_OPENAI_API_KEY 환경변수를 자동 픽업해 azure_ad_token_provider 를 silently
      덮어쓰는 문제 회피.

    Args:
        endpoint:    Azure endpoint (기본: AZURE_OPENAI_ENDPOINT 환경변수)
        api_key:     (deprecated) 사용되지 않음. fail-loud 진단 목적으로만 남김.
        api_version: API version   (기본: 2025-04-01-preview)

    Returns:
        openai.AzureOpenAI 클라이언트

    Raises:
        ValueError: DefaultAzureCredential 가 실패하면 항상 raise.
                    로컬: `az login`. CI: azure/login@v2 OIDC step 확인.
    """
    endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", DEFAULT_ENDPOINT)
    api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
    api_version = api_version or DEFAULT_API_VERSION

    # OIDC only: DefaultAzureCredential (Entra ID token)
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        print("   🔐 Auth: DefaultAzureCredential (Entra ID token)")
        return AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
            timeout=480,
        )
    except Exception as e:
        # API Key fallback disabled — fail loud with OIDC debug guidance.
        print(f"   ⚠️  DefaultAzureCredential failed: {e}")
        print(f"   ⚠️  API Key fallback disabled (Azure disableLocalAuth=true)")
        print(f"   ⚠️  Local: run 'az login' then retry")
        print(f"   ⚠️  CI: verify azure/login@v2 OIDC step succeeded")
        raise ValueError(
            f"Azure authentication failed.\n"
            f"  - DefaultAzureCredential failed: {e}\n"
            f"  - API key fallback disabled (disableLocalAuth=true).\n"
            f"  Fix: 'az login' locally, or check OIDC config in GitHub Actions."
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
        azure:     AZURE_OPENAI_ENDPOINT (OIDC only — DefaultAzureCredential, no API key)
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
    reasoning_effort: str | None = None,
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
        # Note: Anthropic doesn't support reasoning_effort, so it's handled via
        # kwargs_filtered in AnthropicClient.chat_complete() (filters out the param)
        create_kwargs = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_completion_tokens,
            **kwargs,
        }
        if reasoning_effort is not None:
            create_kwargs["reasoning_effort"] = reasoning_effort

        response = client.chat.completions.create(**create_kwargs)

    latency_ms = (time.time() - start) * 1000
    return response, latency_ms
