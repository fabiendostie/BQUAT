import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.orchestrator.engine import WorkflowOrchestrator  # noqa: E402
from runtime.orchestrator.graph import WorkflowNode  # noqa: E402


def _fake_execute(node, _decision):
    return {
        "run_id": f"run-{node.workflow}",
        "status": "completed",
        "workflow": {"module": node.module, "workflow": node.workflow},
    }


class OrchestratorEngineTests(unittest.TestCase):
    def test_execute_plan_tracks_completion(self) -> None:
        config = {"providers": {"default": "mock"}}
        orchestrator = WorkflowOrchestrator(config)
        nodes = [
            WorkflowNode(module="core", workflow="prd", dependencies=[]),
            WorkflowNode(module="core", workflow="architecture", dependencies=["core/prd"]),
        ]
        plan = orchestrator.plan_execution(nodes)
        with patch.object(WorkflowOrchestrator, "_execute_node", side_effect=_fake_execute):
            manifests = orchestrator.execute_plan(plan)
        self.assertEqual(len(manifests), 2)
        self.assertIn("core/prd", orchestrator.state.completed)
        self.assertIn("core/architecture", orchestrator.state.completed)


if __name__ == "__main__":
    unittest.main()
