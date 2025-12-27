import unittest

from runtime.telis import shards


class RuntimeTelisShardTests(unittest.TestCase):
    def _registry(self) -> shards.ShardRegistry:
        registry = shards.ShardRegistry()
        registry.add(
            shards.Shard(
                shard_id="py.syntax",
                language="python",
                version="3.11",
                tier="tier_1_nano",
                topics=["syntax", "def", "class"],
                tokens=40,
                content="def func(x): return x",
            )
        )
        registry.add(
            shards.Shard(
                shard_id="py.async",
                language="python",
                version="3.11",
                tier="tier_2_micro",
                topics=["async", "await", "tasks"],
                tokens=220,
                content="async def main(): await task",
            )
        )
        registry.add(
            shards.Shard(
                shard_id="py.iter",
                language="python",
                version="3.11",
                tier="tier_2_micro",
                topics=["loop", "iterators"],
                tokens=220,
                content="for item in items:",
            )
        )
        registry.add(
            shards.Shard(
                shard_id="js.async",
                language="javascript",
                version="ES2024",
                tier="tier_2_micro",
                topics=["promise", "async", "await"],
                tokens=200,
                content="Promise.all(items.map(async x => x))",
            )
        )
        return registry

    def test_registry_filters_by_language_and_tier(self) -> None:
        registry = self._registry()
        python = registry.list(language="python")
        self.assertEqual(len(python), 3)
        python_tier2 = registry.list(language="python", tier="tier_2_micro")
        self.assertEqual(len(python_tier2), 2)

    def test_search_prefers_topic_matches(self) -> None:
        registry = self._registry()
        results = registry.search("async await", language="python", tier="tier_2_micro")
        self.assertTrue(results)
        self.assertEqual(results[0][0].shard_id, "py.async")

    def test_budget_enforcement_limits_tokens(self) -> None:
        registry = self._registry()
        result = registry.select_for_budget(
            query="async loop",
            language="python",
            tier="tier_2_micro",
            budget_tokens=220,
        )
        self.assertEqual(result.tokens_selected, 220)
        self.assertEqual(len(result.shards), 1)
        self.assertIn(result.shards[0].shard_id, {"py.async", "py.iter"})

    def test_default_budget_policy(self) -> None:
        registry = self._registry()
        policy = shards.default_tier_budgets()
        result = registry.select_for_policy(
            query="syntax def",
            language="python",
            tier="tier_1_nano",
            policy=policy,
        )
        self.assertEqual(result.budget_tokens, 50)
        self.assertEqual(result.tokens_selected, 40)
        self.assertEqual(result.shards[0].shard_id, "py.syntax")


if __name__ == "__main__":
    unittest.main()
