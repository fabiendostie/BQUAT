import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.providers.base import ProviderError, ProviderRequest  # noqa: E402
from runtime.providers.registry import (  # noqa: E402
    AnthropicProvider,
    GeminiProvider,
    GroqProvider,
    LiteLLMProvider,
    MockProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderRegistry,
)


class RuntimeProviderTests(unittest.TestCase):
    def test_mock_provider(self) -> None:
        provider = MockProvider("stub")
        response = provider.invoke(
            ProviderRequest(model="", messages=[{"role": "user", "content": "hi"}])
        )
        self.assertIn("[mock:stub]", response.content)

    def test_registry_default(self) -> None:
        config = {"providers": {"default": "mock", "mock": {"type": "mock"}}}
        registry = ProviderRegistry(config)
        provider = registry.get()
        self.assertIsInstance(provider, MockProvider)

    def test_registry_missing_config(self) -> None:
        registry = ProviderRegistry({})
        with self.assertRaises(ProviderError):
            registry.get()

    def test_registry_unknown_type(self) -> None:
        config = {"providers": {"default": "mystery", "mystery": {"type": "mystery"}}}
        registry = ProviderRegistry(config)
        with self.assertRaises(ProviderError):
            registry.get()

    def test_missing_api_key(self) -> None:
        config = {
            "providers": {
                "default": "openai",
                "openai": {"type": "openai", "api_key_env": "OPENAI_API_KEY", "model": "gpt"},
            }
        }
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        registry = ProviderRegistry(config)
        with self.assertRaises(ProviderError):
            registry.get("openai")

    @patch("runtime.providers.registry.post_json")
    def test_openai_provider(self, post_json_mock) -> None:
        post_json_mock.return_value = {"choices": [{"message": {"content": "ok"}}]}
        provider = OpenAIProvider("https://api.openai.com", "key", "gpt")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertEqual(response.content, "ok")

    @patch("runtime.providers.registry.post_json")
    def test_openai_model_override(self, post_json_mock) -> None:
        post_json_mock.return_value = {"choices": [{"message": {"content": "ok"}}]}
        provider = OpenAIProvider("https://api.openai.com", "key", "gpt-default")
        provider.invoke(
            ProviderRequest(model="gpt-override", messages=[], temperature=0.2, max_tokens=7)
        )
        payload = post_json_mock.call_args[0][1]
        self.assertEqual(payload.get("model"), "gpt-override")

    @patch("runtime.providers.registry.post_json_stream")
    def test_openai_streaming(self, post_json_stream_mock) -> None:
        post_json_stream_mock.return_value = [
            {"choices": [{"delta": {"content": "hi"}}]},
            {"choices": [{"delta": {"content": "!"}}]},
        ]
        provider = OpenAIProvider("https://api.openai.com", "key", "gpt-default")
        response = provider.invoke_stream(ProviderRequest(model="", messages=[], stream=True))
        self.assertEqual(response.content, "hi!")
        self.assertEqual(response.chunks, ["hi", "!"])

    @patch("runtime.providers.registry.post_json")
    def test_litellm_provider(self, post_json_mock) -> None:
        post_json_mock.return_value = {"choices": [{"message": {"content": "ok"}}]}
        provider = LiteLLMProvider("http://localhost:4000", "key", "gpt")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertEqual(response.content, "ok")

    def test_registry_litellm_missing_env(self) -> None:
        config = {"providers": {"default": "litellm", "litellm": {"type": "litellm"}}}
        registry = ProviderRegistry(config)
        provider = registry.get("litellm")
        self.assertIsInstance(provider, LiteLLMProvider)
        self.assertEqual(provider.api_key, "")

    @patch("runtime.providers.registry.post_json")
    def test_ollama_provider(self, post_json_mock) -> None:
        post_json_mock.return_value = {"message": {"content": "ok"}}
        provider = OllamaProvider("http://localhost:11434", "llama3")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertEqual(response.content, "ok")

    @patch("runtime.providers.registry.post_json")
    def test_anthropic_provider(self, post_json_mock) -> None:
        post_json_mock.return_value = {"content": [{"text": "ok"}]}
        provider = AnthropicProvider("https://api.anthropic.com", "key", "claude")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertEqual(response.content, "ok")

    @patch("runtime.providers.registry.post_json")
    def test_gemini_provider(self, post_json_mock) -> None:
        post_json_mock.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        provider = GeminiProvider(
            "https://generativelanguage.googleapis.com/v1beta", "key", "gemini-3"
        )
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertEqual(response.content, "ok")

    @patch("runtime.providers.registry.post_json")
    def test_groq_provider(self, post_json_mock) -> None:
        post_json_mock.return_value = {"choices": [{"message": {"content": "ok"}}]}
        os.environ["GROQ_API_KEY"] = "key"
        try:
            config = {
                "providers": {
                    "default": "groq",
                    "groq": {"type": "groq", "api_key_env": "GROQ_API_KEY", "model": "llama"},
                }
            }
            registry = ProviderRegistry(config)
            provider = registry.get("groq")
            self.assertIsInstance(provider, GroqProvider)
            response = provider.invoke(ProviderRequest(model="", messages=[]))
            self.assertEqual(response.content, "ok")
        finally:
            del os.environ["GROQ_API_KEY"]


if __name__ == "__main__":
    unittest.main()
