import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.orchestrator.graph import WorkflowGraph, WorkflowNode  # noqa: E402


class OrchestratorGraphTests(unittest.TestCase):
    def test_topological_order(self) -> None:
        graph = WorkflowGraph()
        node_a = WorkflowNode(module="core", workflow="prd", dependencies=[])
        node_b = WorkflowNode(module="core", workflow="architecture", dependencies=["core/prd"])
        graph.add_workflow(node_a)
        graph.add_workflow(node_b)
        order = graph.get_execution_order()
        self.assertEqual([node.workflow_id for node in order], ["core/prd", "core/architecture"])

    def test_ready_workflows(self) -> None:
        graph = WorkflowGraph()
        node_a = WorkflowNode(module="core", workflow="prd", dependencies=[])
        node_b = WorkflowNode(module="core", workflow="architecture", dependencies=["core/prd"])
        graph.add_workflow(node_a)
        graph.add_workflow(node_b)
        ready = graph.get_ready_workflows(set())
        self.assertEqual([node.workflow_id for node in ready], ["core/prd"])
        ready = graph.get_ready_workflows({"core/prd"})
        self.assertEqual([node.workflow_id for node in ready], ["core/architecture"])


if __name__ == "__main__":
    unittest.main()
