import unittest

from runtime.telis import context, shards


class RuntimeTelisContextTests(unittest.TestCase):
    def _registry(self) -> shards.ShardRegistry:
        registry = shards.ShardRegistry()
        registry.add(
            shards.Shard(
                shard_id="py.async",
                language="python",
                version="3.11",
                tier="tier_2_micro",
                topics=["async", "await"],
                tokens=200,
                content="async def main(): await task",
            )
        )
        return registry

    def test_lsp_success_returns_lsp_context(self) -> None:
        registry = self._registry()
        policy = shards.default_tier_budgets()
        request = context.TelisContextRequest(
            query="async",
            language="python",
            tier="tier_2_micro",
            method="hover",
        )

        def provider(_request: context.TelisContextRequest) -> dict:
            return {
                "result": {
                    "contents": {
                        "kind": "markdown",
                        "value": "async def main()",
                    }
                }
            }

        result = context.resolve_context(request, registry, policy, lsp_provider=provider)
        self.assertEqual(result.source, "lsp")
        self.assertFalse(result.used_fallback)
        self.assertEqual(result.content, "async def main()")

    def test_lsp_failure_falls_back_to_shards(self) -> None:
        registry = self._registry()
        policy = shards.default_tier_budgets()
        request = context.TelisContextRequest(
            query="async",
            language="python",
            tier="tier_2_micro",
            method="signatureHelp",
        )

        def provider(_request: context.TelisContextRequest) -> dict:
            raise RuntimeError("boom")

        result = context.resolve_context(request, registry, policy, lsp_provider=provider)
        self.assertEqual(result.source, "shards")
        self.assertTrue(result.used_fallback)
        self.assertIn("async def main()", result.content)


if __name__ == "__main__":
    unittest.main()
