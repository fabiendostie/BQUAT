import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.orchestrator.graph import WorkflowNode  # noqa: E402
from runtime.orchestrator.router import AgentProviderRouter  # noqa: E402


class OrchestratorRoutingTests(unittest.TestCase):
    def test_default_routing(self) -> None:
        config = {"providers": {"default": "mock"}, "orchestrator": {"default_agent": "telis"}}
        router = AgentProviderRouter(config)
        decision = router.route(WorkflowNode(module="core", workflow="prd"))
        self.assertEqual(decision.agent, "telis")
        self.assertEqual(decision.provider, "mock")

    def test_explicit_routing(self) -> None:
        router = AgentProviderRouter({"providers": {"default": "mock"}})
        node = WorkflowNode(module="core", workflow="prd", agent="quint", provider="ollama")
        decision = router.route(node)
        self.assertEqual(decision.agent, "quint")
        self.assertEqual(decision.provider, "ollama")


if __name__ == "__main__":
    unittest.main()
