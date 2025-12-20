import os
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.providers.base import ProviderRequest, ProviderError  # noqa: E402
from runtime.providers.registry import (  # noqa: E402
    AnthropicProvider,
    GeminiProvider,
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
    def test_litellm_provider(self, post_json_mock) -> None:
        post_json_mock.return_value = {"choices": [{"message": {"content": "ok"}}]}
        provider = LiteLLMProvider("http://localhost:4000", "key", "gpt")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertEqual(response.content, "ok")

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
        provider = GeminiProvider("https://generativelanguage.googleapis.com/v1beta", "key", "gemini-3")
        response = provider.invoke(ProviderRequest(model="", messages=[]))
        self.assertEqual(response.content, "ok")


if __name__ == "__main__":
    unittest.main()
