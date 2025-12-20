from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from runtime.providers.base import Provider, ProviderError, ProviderRequest, ProviderResponse
from runtime.providers.http import post_json


def _env_value(name: Optional[str]) -> str:
    if not name:
        return ""
    return os.environ.get(name, "")


def _model_from_request(request: ProviderRequest, fallback: str) -> str:
    return request.model or fallback


def _require(value: str, message: str) -> None:
    if not value:
        raise ProviderError(message)


def _compact_messages(messages: List[Dict[str, str]]) -> str:
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role}: {content}")
    return "\n".join(parts)


class MockProvider(Provider):
    def __init__(self, model: str = "mock") -> None:
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        text = _compact_messages(request.messages)
        return ProviderResponse(content=f"[mock:{self.model}] {text}", raw={"mock": True})


class OpenAIProvider(Provider):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": _model_from_request(request, self.model),
            "messages": request.messages,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        data = post_json(url, payload, {"Authorization": f"Bearer {self.api_key}"})
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ProviderResponse(content=content, raw=data)


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
        payload = {
            "model": _model_from_request(request, self.model),
            "messages": request.messages,
            "stream": False,
        }
        data = post_json(url, payload)
        content = data.get("message", {}).get("content", "")
        return ProviderResponse(content=content, raw=data)


class AnthropicProvider(Provider):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        url = f"{self.base_url}/v1/messages"
        payload = {
            "model": _model_from_request(request, self.model),
            "messages": request.messages,
            "max_tokens": request.max_tokens or 1024,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        data = post_json(url, payload, headers=headers)
        content = ""
        if data.get("content"):
            content = data.get("content")[0].get("text", "")
        return ProviderResponse(content=content, raw=data)


class GeminiProvider(Provider):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        model = _model_from_request(request, self.model)
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": _compact_messages(request.messages)}],
                }
            ]
        }
        data = post_json(url, payload)
        content = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                content = parts[0].get("text", "")
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
            return MockProvider(model or "mock")
        if provider_type == "ollama":
            base_url = cfg.get("base_url", "http://localhost:11434")
            return OllamaProvider(base_url, model)
        if provider_type == "litellm":
            base_url = cfg.get("base_url", "http://localhost:4000")
            api_key = _env_value(cfg.get("api_key_env"))
            return LiteLLMProvider(base_url, api_key, model)
        if provider_type == "openai":
            base_url = cfg.get("base_url", "https://api.openai.com")
            api_key = _env_value(cfg.get("api_key_env"))
            _require(api_key, "Missing OpenAI API key")
            return OpenAIProvider(base_url, api_key, model)
        if provider_type == "anthropic":
            base_url = cfg.get("base_url", "https://api.anthropic.com")
            api_key = _env_value(cfg.get("api_key_env"))
            _require(api_key, "Missing Anthropic API key")
            return AnthropicProvider(base_url, api_key, model)
        if provider_type == "gemini":
            base_url = cfg.get("base_url", "https://generativelanguage.googleapis.com/v1beta")
            api_key = _env_value(cfg.get("api_key_env"))
            _require(api_key, "Missing Gemini API key")
            return GeminiProvider(base_url, api_key, model)
        if provider_type == "groq":
            base_url = cfg.get("base_url", "https://api.groq.com/openai/v1")
            api_key = _env_value(cfg.get("api_key_env"))
            _require(api_key, "Missing Groq API key")
            return GroqProvider(base_url, api_key, model)
        raise ProviderError(f"Unknown provider type: {provider_type}")
