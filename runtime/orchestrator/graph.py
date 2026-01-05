from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass(frozen=True)
class WorkflowNode:
    module: str
    workflow: str
    dependencies: List[str] = field(default_factory=list)
    agent: str | None = None
    provider: str | None = None

    @property
    def workflow_id(self) -> str:
        return f"{self.module}/{self.workflow}"


class WorkflowGraph:
    """DAG of workflow dependencies."""

    def __init__(self) -> None:
        self._nodes: Dict[str, WorkflowNode] = {}

    def add_workflow(self, node: WorkflowNode) -> None:
        self._nodes[node.workflow_id] = node

    def get_execution_order(self) -> List[WorkflowNode]:
        nodes = dict(self._nodes)
        in_degree: Dict[str, int] = {workflow_id: 0 for workflow_id in nodes}
        for workflow_id, node in nodes.items():
            for dep in node.dependencies:
                if dep not in nodes:
                    raise ValueError(f"Missing dependency: {dep}")
                in_degree[workflow_id] += 1

        ready = [workflow_id for workflow_id, degree in in_degree.items() if degree == 0]
        order: List[WorkflowNode] = []

        while ready:
            current = ready.pop(0)
            order.append(nodes[current])
            for other_id, other_node in nodes.items():
                if current in other_node.dependencies:
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        ready.append(other_id)

        if len(order) != len(nodes):
            raise ValueError("Cycle detected in workflow graph")
        return order

    def get_ready_workflows(self, completed: Set[str]) -> List[WorkflowNode]:
        ready: List[WorkflowNode] = []
        for workflow_id, node in self._nodes.items():
            if workflow_id in completed:
                continue
            if all(dep in completed for dep in node.dependencies):
                ready.append(node)
        return ready

    def list_nodes(self) -> List[WorkflowNode]:
        return list(self._nodes.values())
