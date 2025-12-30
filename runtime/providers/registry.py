from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Dict, List, Optional

from runtime.providers.base import Provider, ProviderError, ProviderRequest, ProviderResponse
from runtime.providers.http import post_json, post_json_stream
from runtime.providers.reliability import CircuitBreaker, ReliableProvider, RetryPolicy


def _env_value(name: Optional[str]) -> str:
    if not name:
        return ""
    return os.environ.get(name, "")


def _model_from_request(request: ProviderRequest, fallback: str) -> str:
    return request.model or fallback


def _require(value: str, message: str) -> None:
    if not value:
        raise ProviderError(message)


def _timeout_seconds(request: ProviderRequest, fallback: int = 60) -> int:
    if request.timeout_seconds is None:
        return fallback
    return request.timeout_seconds


def _compact_messages(messages: List[Dict[str, str]]) -> str:
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _merge_reliability_config(
    providers_cfg: Dict[str, Any], provider_cfg: Dict[str, Any]
) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(providers_cfg.get("reliability", {}))
    reliability_override = provider_cfg.get("reliability", {})
    if isinstance(reliability_override, dict):
        merged.update(reliability_override)
    for key in (
        "enabled",
        "timeout_seconds",
        "max_retries",
        "max_attempts",
        "backoff_seconds",
        "backoff_factor",
        "backoff_max_seconds",
        "jitter_seconds",
    ):
        if key in provider_cfg:
            merged[key] = provider_cfg[key]
    if "circuit_breaker" in provider_cfg:
        base = dict(merged.get("circuit_breaker", {}))
        override = provider_cfg.get("circuit_breaker", {})
        if isinstance(override, dict):
            base.update(override)
        merged["circuit_breaker"] = base
    return merged


def _retry_policy_from_config(config: Dict[str, Any]) -> RetryPolicy:
    max_attempts = config.get("max_attempts")
    if max_attempts is None:
        max_retries = int(config.get("max_retries", 0))
        max_attempts = max(1, max_retries + 1)
    return RetryPolicy(
        max_attempts=int(max_attempts),
        backoff_seconds=float(config.get("backoff_seconds", 0.5)),
        backoff_factor=float(config.get("backoff_factor", 2.0)),
        backoff_max_seconds=float(config.get("backoff_max_seconds", 8.0)),
        jitter_seconds=float(config.get("jitter_seconds", 0.1)),
    )


def _circuit_breaker_from_config(config: Dict[str, Any]) -> Optional[CircuitBreaker]:
    breaker_cfg = config.get("circuit_breaker", {})
    if not isinstance(breaker_cfg, dict):  # pragma: no cover - defensive
        return None
    if breaker_cfg.get("enabled") is False:
        return None
    if not breaker_cfg and config.get("enabled") is False:
        return None
    failure_threshold = int(breaker_cfg.get("failure_threshold", 3))
    reset_seconds = float(breaker_cfg.get("reset_seconds", 30.0))
    return CircuitBreaker(failure_threshold=failure_threshold, reset_seconds=reset_seconds)


def _wrap_provider(
    provider: Provider, providers_cfg: Dict[str, Any], provider_cfg: Dict[str, Any]
) -> Provider:
    has_reliability = "reliability" in providers_cfg or "reliability" in provider_cfg
    if not has_reliability and not any(
        key in provider_cfg
        for key in (
            "timeout_seconds",
            "max_retries",
            "max_attempts",
            "backoff_seconds",
            "backoff_factor",
            "backoff_max_seconds",
            "jitter_seconds",
            "circuit_breaker",
        )
    ):
        return provider
    merged = _merge_reliability_config(providers_cfg, provider_cfg)
    if merged.get("enabled") is False:
        return provider
    retry_policy = _retry_policy_from_config(merged)
    timeout_seconds = merged.get("timeout_seconds")
    circuit_breaker = _circuit_breaker_from_config(merged)
    return ReliableProvider(
        provider,
        retry_policy=retry_policy,
        timeout_seconds=timeout_seconds,
        circuit_breaker=circuit_breaker,
    )


class MockProvider(Provider):
    def __init__(self, model: str = "mock") -> None:
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        text = _compact_messages(request.messages)
        return ProviderResponse(content=f"[mock:{self.model}] {text}", raw={"mock": True})

    def invoke_stream(self, request: ProviderRequest) -> ProviderResponse:
        response = self.invoke(replace(request, stream=False))
        return ProviderResponse(
            content=response.content, raw=response.raw, chunks=[response.content]
        )


class OpenAIProvider(Provider):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": _model_from_request(request, self.model),
            "messages": request.messages,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        data = post_json(
            url,
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
            timeout_seconds=_timeout_seconds(request),
        )
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ProviderResponse(content=content, raw=data)

    def invoke_stream(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": _model_from_request(request, self.model),
            "messages": request.messages,
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        chunks: List[str] = []
        raw_chunks: List[Dict[str, Any]] = []
        for chunk in post_json_stream(
            url,
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
            timeout_seconds=_timeout_seconds(request),
        ):
            raw_chunks.append(chunk)
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
            text = delta.get("content")
            if text:
                chunks.append(text)
        return ProviderResponse(content="".join(chunks), raw={"chunks": raw_chunks}, chunks=chunks)


class GroqProvider(OpenAIProvider):
    pass


class LiteLLMProvider(OpenAIProvider):
    pass


class OllamaProvider(Provider):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": _model_from_request(request, self.model),
            "messages": request.messages,
            "stream": False,
        }
        data = post_json(url, payload, timeout_seconds=_timeout_seconds(request))
        content = data.get("message", {}).get("content", "")
        return ProviderResponse(content=content, raw=data)

    def invoke_stream(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": _model_from_request(request, self.model),
            "messages": request.messages,
            "stream": True,
        }
        chunks: List[str] = []
        raw_chunks: List[Dict[str, Any]] = []
        for chunk in post_json_stream(url, payload, timeout_seconds=_timeout_seconds(request)):
            raw_chunks.append(chunk)
            message = chunk.get("message", {}) if isinstance(chunk, dict) else {}
            text = message.get("content") if isinstance(message, dict) else None
            if text:
                chunks.append(text)
            if chunk.get("done"):
                break
        return ProviderResponse(content="".join(chunks), raw={"chunks": raw_chunks}, chunks=chunks)


class AnthropicProvider(Provider):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.base_url}/v1/messages"
        payload: Dict[str, Any] = {
            "model": _model_from_request(request, self.model),
            "messages": request.messages,
            "max_tokens": request.max_tokens or 1024,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        data = post_json(url, payload, headers=headers, timeout_seconds=_timeout_seconds(request))
        content = ""
        content_items = data.get("content")
        if isinstance(content_items, list) and content_items:
            first = content_items[0]
            if isinstance(first, dict):
                content = first.get("text", "")
        return ProviderResponse(content=content, raw=data)


class GeminiProvider(Provider):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        model = _model_from_request(request, self.model)
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": _compact_messages(request.messages)}],
                }
            ]
        }
        data = post_json(url, payload, timeout_seconds=_timeout_seconds(request))
        content = ""
        candidates = data.get("candidates", [])
        if isinstance(candidates, list) and candidates:
            first = candidates[0]
            if isinstance(first, dict):
                parts = first.get("content", {}).get("parts", [])
                if isinstance(parts, list) and parts:
                    part = parts[0]
                    if isinstance(part, dict):
                        content = part.get("text", "")
        return ProviderResponse(content=content, raw=data)


class ProviderRegistry:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def get(self, name: Optional[str] = None) -> Provider:
        providers = self.config.get("providers", {})
        default_name = providers.get("default", "mock")
        provider_name = name or default_name
        cfg = providers.get(provider_name)
        if not cfg:
            raise ProviderError(f"Provider not configured: {provider_name}")
        provider_type = cfg.get("type", "mock")
        model = cfg.get("model", "")
        if provider_type == "mock":
            return _wrap_provider(MockProvider(model or "mock"), providers, cfg)
        if provider_type == "ollama":
            base_url = cfg.get("base_url", "http://localhost:11434")
            return _wrap_provider(OllamaProvider(base_url, model), providers, cfg)
        if provider_type == "litellm":
            base_url = cfg.get("base_url", "http://localhost:4000")
            api_key = _env_value(cfg.get("api_key_env"))
            return _wrap_provider(LiteLLMProvider(base_url, api_key, model), providers, cfg)
        if provider_type == "openai":
            base_url = cfg.get("base_url", "https://api.openai.com")
            api_key = _env_value(cfg.get("api_key_env"))
            _require(api_key, "Missing OpenAI API key")
            return _wrap_provider(OpenAIProvider(base_url, api_key, model), providers, cfg)
        if provider_type == "anthropic":
            base_url = cfg.get("base_url", "https://api.anthropic.com")
            api_key = _env_value(cfg.get("api_key_env"))
            _require(api_key, "Missing Anthropic API key")
            return _wrap_provider(AnthropicProvider(base_url, api_key, model), providers, cfg)
        if provider_type == "gemini":
            base_url = cfg.get("base_url", "https://generativelanguage.googleapis.com/v1beta")
            api_key = _env_value(cfg.get("api_key_env"))
            _require(api_key, "Missing Gemini API key")
            return _wrap_provider(GeminiProvider(base_url, api_key, model), providers, cfg)
        if provider_type == "groq":
            base_url = cfg.get("base_url", "https://api.groq.com/openai/v1")
            api_key = _env_value(cfg.get("api_key_env"))
            _require(api_key, "Missing Groq API key")
            return _wrap_provider(GroqProvider(base_url, api_key, model), providers, cfg)
        raise ProviderError(f"Unknown provider type: {provider_type}")
