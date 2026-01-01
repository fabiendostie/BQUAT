from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.providers.base import (  # noqa: E402
    Provider,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
)
from runtime.providers.registry import (  # noqa: E402
    AnthropicProvider,
    GeminiProvider,
    GroqProvider,
    LiteLLMProvider,
    MockProvider,
    OllamaProvider,
    OpenAIProvider,
)


class ProviderRequestContractTests(unittest.TestCase):
    """Tests for ProviderRequest dataclass contract."""

    def test_request_is_frozen(self) -> None:
        request = ProviderRequest(model="gpt", messages=[])
        with self.assertRaises(FrozenInstanceError):
            request.model = "other"  # type: ignore[misc]

    def test_request_required_fields(self) -> None:
        request = ProviderRequest(model="gpt", messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(request.model, "gpt")
        self.assertEqual(len(request.messages), 1)

    def test_request_optional_fields_default(self) -> None:
        request = ProviderRequest(model="gpt", messages=[])
        self.assertIsNone(request.temperature)
        self.assertIsNone(request.max_tokens)
        self.assertFalse(request.stream)
        self.assertIsNone(request.timeout_seconds)

    def test_request_optional_fields_set(self) -> None:
        request = ProviderRequest(
            model="gpt",
            messages=[],
            temperature=0.7,
            max_tokens=100,
            stream=True,
            timeout_seconds=30,
        )
        self.assertEqual(request.temperature, 0.7)
        self.assertEqual(request.max_tokens, 100)
        self.assertTrue(request.stream)
        self.assertEqual(request.timeout_seconds, 30)


class ProviderResponseContractTests(unittest.TestCase):
    """Tests for ProviderResponse dataclass contract."""

    def test_response_is_frozen(self) -> None:
        response = ProviderResponse(content="hello", raw={})
        with self.assertRaises(FrozenInstanceError):
            response.content = "other"  # type: ignore[misc]

    def test_response_content_is_string(self) -> None:
        response = ProviderResponse(content="hello", raw={})
        self.assertIsInstance(response.content, str)

    def test_response_raw_is_dict(self) -> None:
        response = ProviderResponse(content="hello", raw={"key": "value"})
        self.assertIsInstance(response.raw, dict)

    def test_response_chunks_default_none(self) -> None:
        response = ProviderResponse(content="hello", raw={})
        self.assertIsNone(response.chunks)

    def test_response_chunks_is_list_when_set(self) -> None:
        response = ProviderResponse(content="hello", raw={}, chunks=["hel", "lo"])
        self.assertIsInstance(response.chunks, list)
        self.assertEqual(response.chunks, ["hel", "lo"])


class ProviderErrorContractTests(unittest.TestCase):
    """Tests for ProviderError exception contract."""

    def test_error_is_runtime_error(self) -> None:
        error = ProviderError("test error")
        self.assertIsInstance(error, RuntimeError)

    def test_error_message(self) -> None:
        error = ProviderError("test error")
        self.assertEqual(str(error), "test error")

    def test_error_status_code_default(self) -> None:
        error = ProviderError("test error")
        self.assertIsNone(error.status_code)

    def test_error_status_code_set(self) -> None:
        error = ProviderError("test error", status_code=429)
        self.assertEqual(error.status_code, 429)

    def test_error_retriable_default_true(self) -> None:
        error = ProviderError("test error")
        self.assertTrue(error.retriable)

    def test_error_retriable_false(self) -> None:
        error = ProviderError("test error", retriable=False)
        self.assertFalse(error.retriable)

    def test_error_type_default_empty(self) -> None:
        error = ProviderError("test error")
        self.assertEqual(error.error_type, "")

    def test_error_type_set(self) -> None:
        error = ProviderError("test error", error_type="rate_limit")
        self.assertEqual(error.error_type, "rate_limit")


class ProviderBaseContractTests(unittest.TestCase):
    """Tests for Provider base class contract."""

    def test_base_invoke_not_implemented(self) -> None:
        provider = Provider()
        with self.assertRaises(NotImplementedError):
            provider.invoke(ProviderRequest(model="", messages=[]))

    def test_base_invoke_stream_raises_provider_error(self) -> None:
        provider = Provider()
        with self.assertRaises(ProviderError) as ctx:
            provider.invoke_stream(ProviderRequest(model="", messages=[]))
        self.assertIn("not supported", str(ctx.exception))


class MockProviderContractTests(unittest.TestCase):
    """Tests for MockProvider implementation contract."""

    def test_invoke_returns_provider_response(self) -> None:
        provider = MockProvider("test")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertIsInstance(response, ProviderResponse)

    def test_invoke_response_content_not_empty(self) -> None:
        provider = MockProvider("test")
        response = provider.invoke(
            ProviderRequest(model="", messages=[{"role": "user", "content": "hello"}])
        )
        self.assertTrue(len(response.content) > 0)

    def test_invoke_response_raw_is_dict(self) -> None:
        provider = MockProvider("test")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertIsInstance(response.raw, dict)
        self.assertTrue(response.raw.get("mock"))

    def test_invoke_stream_returns_provider_response(self) -> None:
        provider = MockProvider("test")
        response = provider.invoke_stream(ProviderRequest(model="", messages=[], stream=True))
        self.assertIsInstance(response, ProviderResponse)

    def test_invoke_stream_populates_chunks(self) -> None:
        provider = MockProvider("test")
        response = provider.invoke_stream(
            ProviderRequest(model="", messages=[{"role": "user", "content": "hi"}], stream=True)
        )
        self.assertIsNotNone(response.chunks)
        self.assertIsInstance(response.chunks, list)
        self.assertTrue(len(response.chunks) > 0)

    def test_message_compaction(self) -> None:
        provider = MockProvider("test")
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "bye"},
        ]
        response = provider.invoke(ProviderRequest(model="", messages=messages))
        self.assertIn("hello", response.content)
        self.assertIn("hi", response.content)
        self.assertIn("bye", response.content)

    def test_model_reflected_in_output(self) -> None:
        provider = MockProvider("custom-model")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertIn("custom-model", response.content)

    def test_empty_messages(self) -> None:
        provider = MockProvider("test")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertIsInstance(response, ProviderResponse)
        self.assertIn("[mock:test]", response.content)

    def test_special_characters_in_messages(self) -> None:
        provider = MockProvider("test")
        messages = [{"role": "user", "content": "hello <>&\"' world"}]
        response = provider.invoke(ProviderRequest(model="", messages=messages))
        self.assertIn("<>&\"'", response.content)

    def test_state_isolation_between_calls(self) -> None:
        provider = MockProvider("test")
        response1 = provider.invoke(
            ProviderRequest(model="", messages=[{"role": "user", "content": "first"}])
        )
        response2 = provider.invoke(
            ProviderRequest(model="", messages=[{"role": "user", "content": "second"}])
        )
        self.assertIn("first", response1.content)
        self.assertNotIn("first", response2.content)
        self.assertIn("second", response2.content)


class ProviderImplementationContractTests(unittest.TestCase):
    """Tests that all provider implementations follow the contract."""

    def _make_provider(self, provider_class: type) -> Provider:
        if provider_class == MockProvider:
            return MockProvider("test")
        if provider_class == OllamaProvider:
            return OllamaProvider("http://localhost:11434", "llama3")
        if provider_class in (OpenAIProvider, LiteLLMProvider, GroqProvider):
            return provider_class("https://api.example.com", "key", "model")
        if provider_class == AnthropicProvider:
            return AnthropicProvider("https://api.anthropic.com", "key", "claude")
        if provider_class == GeminiProvider:
            return GeminiProvider("https://api.google.com", "key", "gemini")
        raise ValueError(f"Unknown provider class: {provider_class}")

    def test_all_providers_have_invoke(self) -> None:
        providers = [
            MockProvider,
            OllamaProvider,
            OpenAIProvider,
            LiteLLMProvider,
            GroqProvider,
            AnthropicProvider,
            GeminiProvider,
        ]
        for provider_class in providers:
            provider = self._make_provider(provider_class)
            self.assertTrue(
                hasattr(provider, "invoke"),
                f"{provider_class.__name__} missing invoke method",
            )
            self.assertTrue(
                callable(provider.invoke),
                f"{provider_class.__name__}.invoke not callable",
            )

    def test_all_providers_have_invoke_stream(self) -> None:
        providers = [
            MockProvider,
            OllamaProvider,
            OpenAIProvider,
            LiteLLMProvider,
            GroqProvider,
            AnthropicProvider,
            GeminiProvider,
        ]
        for provider_class in providers:
            provider = self._make_provider(provider_class)
            self.assertTrue(
                hasattr(provider, "invoke_stream"),
                f"{provider_class.__name__} missing invoke_stream method",
            )
            self.assertTrue(
                callable(provider.invoke_stream),
                f"{provider_class.__name__}.invoke_stream not callable",
            )

    @patch("runtime.providers.registry.post_json")
    def test_openai_response_structure(self, post_json_mock) -> None:
        post_json_mock.return_value = {"choices": [{"message": {"content": "ok"}}]}
        provider = OpenAIProvider("https://api.openai.com", "key", "gpt")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertIsInstance(response, ProviderResponse)
        self.assertIsInstance(response.content, str)
        self.assertIsInstance(response.raw, dict)

    @patch("runtime.providers.registry.post_json")
    def test_ollama_response_structure(self, post_json_mock) -> None:
        post_json_mock.return_value = {"message": {"content": "ok"}}
        provider = OllamaProvider("http://localhost:11434", "llama3")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertIsInstance(response, ProviderResponse)
        self.assertIsInstance(response.content, str)
        self.assertIsInstance(response.raw, dict)

    @patch("runtime.providers.registry.post_json")
    def test_anthropic_response_structure(self, post_json_mock) -> None:
        post_json_mock.return_value = {"content": [{"text": "ok"}]}
        provider = AnthropicProvider("https://api.anthropic.com", "key", "claude")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertIsInstance(response, ProviderResponse)
        self.assertIsInstance(response.content, str)
        self.assertIsInstance(response.raw, dict)

    @patch("runtime.providers.registry.post_json")
    def test_gemini_response_structure(self, post_json_mock) -> None:
        post_json_mock.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        provider = GeminiProvider("https://api.google.com", "key", "gemini")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertIsInstance(response, ProviderResponse)
        self.assertIsInstance(response.content, str)
        self.assertIsInstance(response.raw, dict)

    @patch("runtime.providers.registry.post_json_stream")
    def test_openai_streaming_response_structure(self, post_json_stream_mock) -> None:
        post_json_stream_mock.return_value = [
            {"choices": [{"delta": {"content": "hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
        ]
        provider = OpenAIProvider("https://api.openai.com", "key", "gpt")
        response = provider.invoke_stream(ProviderRequest(model="", messages=[], stream=True))
        self.assertIsInstance(response, ProviderResponse)
        self.assertIsInstance(response.content, str)
        self.assertIsInstance(response.raw, dict)
        self.assertIsNotNone(response.chunks)
        self.assertIsInstance(response.chunks, list)

    @patch("runtime.providers.registry.post_json_stream")
    def test_ollama_streaming_response_structure(self, post_json_stream_mock) -> None:
        post_json_stream_mock.return_value = [
            {"message": {"content": "hel"}},
            {"message": {"content": "lo"}, "done": True},
        ]
        provider = OllamaProvider("http://localhost:11434", "llama3")
        response = provider.invoke_stream(ProviderRequest(model="", messages=[], stream=True))
        self.assertIsInstance(response, ProviderResponse)
        self.assertIsInstance(response.content, str)
        self.assertIsInstance(response.raw, dict)
        self.assertIsNotNone(response.chunks)
        self.assertIsInstance(response.chunks, list)


if __name__ == "__main__":
    unittest.main()
