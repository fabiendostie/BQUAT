import unittest
from pathlib import Path
from uuid import uuid4

from runtime import engine, models, storage
from runtime.telis import BehavioralCache, TelisPolicyEngine, parse_policy, shards

ROOT = Path(__file__).resolve().parents[1]


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class RecordingExecutor(engine.StepExecutor):
    def __init__(self) -> None:
        self.telis_context = None

    def execute(self, step: dict, context: dict) -> None:
        self.telis_context = context.get("telis_context")


class RuntimeTelisManagerTests(unittest.TestCase):
    def _config(self) -> dict:
        return {
            "runtime": {
                "storage_root": "runs",
                "max_retries": 0,
                "step_timeout_seconds": 5,
            },
            "hitl": {"mode": "blocking", "require_conditional": False},
        }

    def _spec(self, telis_policy: str) -> models.WorkflowSpec:
        return models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            quint="Deduction (L1)",
            telis=telis_policy,
            validation="Template/schema validation",
            human="optional",
            evidence="L1",
            artifacts=["{output_folder}/prd.md"],
            scope="production",
            path="src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
        )

    def _registry(self) -> shards.ShardRegistry:
        registry = shards.ShardRegistry()
        registry.add(
            shards.Shard(
                shard_id="py.syntax",
                language="python",
                version="3.11",
                tier="tier_1_nano",
                topics=["syntax", "async"],
                tokens=40,
                content="async def main(): await task",
            )
        )
        return registry

    def test_parse_policy_progressive_tier(self) -> None:
        policy = parse_policy("Tier 2 shards + progressive negotiation")
        self.assertTrue(policy.progressive)
        self.assertEqual(policy.tiers, ["tier_2_micro", "tier_3_full"])
        self.assertFalse(policy.use_lsp)

    def test_cache_hit_reuses_context(self) -> None:
        registry = self._registry()
        policy = shards.default_tier_budgets()
        cache = BehavioralCache(ttl_seconds=60)
        manager = TelisPolicyEngine(registry=registry, policy=policy, cache=cache)
        spec = self._spec("Tier 1 minimal")
        manifest = {"workflow": spec.to_dict()}
        step = {"inputs": {"telis_query": "syntax", "telis_language": "python"}}
        first = manager.resolve_for_step(step, None, manifest)
        second = manager.resolve_for_step(step, None, manifest)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertFalse(first.get("cached"))
        self.assertTrue(second.get("cached"))
        self.assertIn("async def main", second.get("context", ""))

    def test_engine_passes_telis_context(self) -> None:
        registry = self._registry()
        telis_engine = TelisPolicyEngine(registry=registry)
        spec = self._spec("Tier 1 minimal")
        tmp = _sandbox_root()
        eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp, telis=telis_engine)
        created = eng.create_run("bmm", "prd")
        run_dir = tmp / created["run_id"]
        step_spec = models.StepSpec(
            id="step-1",
            name="context",
            description="",
            phase=spec.phase,
            inputs={"telis_query": "async", "telis_language": "python"},
            outputs=["{output_folder}/prd.md"],
            templates=[],
            tools=[],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        executor = RecordingExecutor()
        result = eng.run("bmm", "prd", run_id=created["run_id"], executor=executor)
        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(executor.telis_context)
        self.assertIn("async def main", executor.telis_context.get("context", ""))
        self.assertIn("telis_context", result["steps"][0])


if __name__ == "__main__":
    unittest.main()
