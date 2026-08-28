import os
import time

from core.azure_ai_clients import (
    DEFAULT_LEGACY_API_VERSION,
    DEFAULT_TIMEOUT,
    AzureAIClientFactory,
    AzureAIClientLease,
    AzureAIRouteSettings,
    AzureAIWorkload,
)
from core.config import (
    DEFAULT_API_VERSION,
    DEFAULT_DEPLOYMENT,
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

class ManagedAzureAIClient:
    """Synchronous delegating Azure AI client adapter; not thread-safe.

    The adapter closes its lease before an internally-created factory. A
    caller-injected factory remains caller-owned.
    """

    def __init__(
        self,
        lease: AzureAIClientLease,
        owned_factory: AzureAIClientFactory | None = None,
    ):
        self._lease = lease
        self._owned_factory = owned_factory
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("managed Azure AI client is closed")

    @property
    def client(self):
        self._require_open()
        return self._lease.client

    @property
    def route(self):
        self._require_open()
        return self._lease.route

    @property
    def runtime_fingerprint(self) -> str:
        self._require_open()
        return self._lease.runtime_fingerprint

    def __getattr__(self, name: str):
        self._require_open()
        return getattr(self._lease.client, name)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        first_error: BaseException | None = None
        for resource in (self._lease, self._owned_factory):
            if resource is None:
                continue
            try:
                resource.close()
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    def __enter__(self) -> "ManagedAzureAIClient":
        self._require_open()
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


def create_typed_azure_client(
    workload: AzureAIWorkload | str,
    deployment: str,
    *,
    factory: AzureAIClientFactory | None = None,
    settings: AzureAIRouteSettings | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    max_retries: int | None = None,
    legacy_api_version: str = DEFAULT_LEGACY_API_VERSION,
) -> ManagedAzureAIClient:
    """Create an explicitly managed client from the typed Azure AI foundation."""
    if factory is not None and settings is not None:
        raise ValueError("factory and settings are mutually exclusive")

    owned_factory = None
    active_factory = factory
    if active_factory is None:
        owned_factory = AzureAIClientFactory(settings=settings)
        active_factory = owned_factory

    try:
        lease = active_factory.create(
            workload,
            deployment=deployment,
            timeout=timeout,
            max_retries=max_retries,
            legacy_api_version=legacy_api_version,
        )
    except BaseException as creation_error:
        if owned_factory is not None:
            try:
                owned_factory.close()
            except BaseException as close_error:
                raise close_error from creation_error
        raise

    return ManagedAzureAIClient(lease, owned_factory=owned_factory)


def close_provider_client(client) -> None:
    """Close a provider client when it exposes synchronous ownership."""
    close = getattr(client, "close", None)
    if callable(close):
        close()


def create_client(
    endpoint: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
    max_retries: int | None = None,
    deployment: str | None = None,
    workload: AzureAIWorkload | str = AzureAIWorkload.INFERENCE,
) -> ManagedAzureAIClient:
    """Create an OIDC-only managed client from the typed Azure AI route."""
    if endpoint is not None:
        raise ValueError(
            "endpoint overrides are forbidden; configure a typed Azure AI endpoint"
        )
    if api_key is not None:
        raise ValueError("static Azure AI API keys are forbidden")
    return create_typed_azure_client(
        workload,
        deployment or DEFAULT_DEPLOYMENT,
        max_retries=max_retries,
        legacy_api_version=api_version or DEFAULT_API_VERSION,
    )


def create_provider_client(
    provider: str,
    endpoint: str | None = None,
    api_key: str | None = None,
    api_version: str | None = None,
    max_retries: int | None = None,
    deployment: str | None = None,
    workload: AzureAIWorkload | str = AzureAIWorkload.INFERENCE,
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
            max_retries=max_retries,
            deployment=deployment,
            workload=workload,
        )

    elif provider == "openai":
        from openai import OpenAI
        if max_retries is None:
            return OpenAI(
                api_key=api_key or os.getenv("OPENAI_API_KEY"),
                base_url=endpoint or None,
                timeout=480,
            )
        return OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=endpoint or None,
            timeout=480,
            max_retries=max_retries,
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

    # A client may be wrapped by core.cost_metering so that each call records
    # what it cost. The wrapper forwards every attribute but not its type, so
    # the provider test below looks *through* it while the call itself still
    # goes *through* it — the request has to stay metered.
    probe = client.inner if getattr(client, "_is_cost_metered", False) else client

    if isinstance(probe, AnthropicClient):
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
