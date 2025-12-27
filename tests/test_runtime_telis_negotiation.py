import unittest

from runtime.telis import negotiation, shards


class RuntimeTelisNegotiationTests(unittest.TestCase):
    def _registry(self) -> shards.ShardRegistry:
        registry = shards.ShardRegistry()
        registry.add(
            shards.Shard(
                shard_id="py.nano",
                language="python",
                version="3.11",
                tier="tier_1_nano",
                topics=["syntax"],
                tokens=40,
                content="def func(x): return x",
            )
        )
        registry.add(
            shards.Shard(
                shard_id="py.micro",
                language="python",
                version="3.11",
                tier="tier_2_micro",
                topics=["async"],
                tokens=200,
                content="async def main(): await task",
            )
        )
        registry.add(
            shards.Shard(
                shard_id="py.full",
                language="python",
                version="3.11",
                tier="tier_3_full",
                topics=["advanced"],
                tokens=500,
                content="Advanced async patterns and caveats.",
            )
        )
        return registry

    def test_negotiation_stops_when_no_escalation(self) -> None:
        registry = self._registry()
        policy = shards.default_tier_budgets()
        request = negotiation.TelisNegotiationRequest(
            query="syntax",
            language="python",
            signals=[False],
            max_phase=3,
        )
        result = negotiation.negotiate_context(request, registry, policy)
        self.assertEqual(len(result.phases), 1)
        self.assertEqual(result.final_context.source, "shards")
        self.assertEqual(result.phases[0].tier, "tier_1_nano")

    def test_negotiation_escalates_through_tiers(self) -> None:
        registry = self._registry()
        policy = shards.default_tier_budgets()
        request = negotiation.TelisNegotiationRequest(
            query="async",
            language="python",
            signals=[True, True],
            max_phase=3,
        )
        result = negotiation.negotiate_context(request, registry, policy)
        self.assertEqual(len(result.phases), 3)
        self.assertEqual(result.phases[-1].tier, "tier_3_full")
        self.assertIn("Advanced async", result.final_context.content)

    def test_uncertainty_markers_trigger_escalation(self) -> None:
        registry = self._registry()
        policy = shards.default_tier_budgets()
        request = negotiation.TelisNegotiationRequest(
            query="async",
            language="python",
            draft_response="Not sure about async behavior.",
            max_phase=2,
        )
        result = negotiation.negotiate_context(request, registry, policy)
        self.assertEqual(len(result.phases), 2)
        self.assertEqual(result.phases[-1].tier, "tier_2_micro")


if __name__ == "__main__":
    unittest.main()
