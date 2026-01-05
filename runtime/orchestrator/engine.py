from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List

from runtime import engine as workflow_engine
from runtime import execution
from runtime.orchestrator.graph import WorkflowGraph, WorkflowNode
from runtime.orchestrator.policies import PolicyEngine
from runtime.orchestrator.router import AgentProviderRouter, RoutingDecision
from runtime.orchestrator.scheduler import ResourceScheduler
from runtime.orchestrator.state import OrchestratorState
from runtime.providers.registry import ProviderRegistry


@dataclass(frozen=True)
class ExecutionPlan:
    order: List[WorkflowNode]
    assignments: Dict[str, RoutingDecision]


class WorkflowOrchestrator:
    """Coordinator for routing and executing workflows."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.graph = WorkflowGraph()
        self.scheduler = ResourceScheduler(config)
        self.router = AgentProviderRouter(config)
        self.policy_engine = PolicyEngine(config)
        self.state = OrchestratorState()
        self.engine = workflow_engine.WorkflowEngine(
            config,
            workflow_engine.load_mapping_records(),
        )
        self.providers = ProviderRegistry(config)

    def route_workflow(self, module: str, workflow: str) -> RoutingDecision:
        node = WorkflowNode(module=module, workflow=workflow)
        decision = self.router.route(node)
        policy = self.policy_engine.evaluate(node, decision)
        if not policy.allowed:
            return RoutingDecision(
                agent=decision.agent, provider=decision.provider, reason=policy.reason
            )
        return policy.routing

    def plan_execution(self, workflows: List[WorkflowNode]) -> ExecutionPlan:
        self.graph = WorkflowGraph()
        for node in workflows:
            self.graph.add_workflow(node)
        order = self.graph.get_execution_order()
        assignments = {node.workflow_id: self.router.route(node) for node in order}
        return ExecutionPlan(order=order, assignments=assignments)

    def execute_plan(self, plan: ExecutionPlan) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        self.state = OrchestratorState()
        if not self.graph.list_nodes():
            self.graph = WorkflowGraph()
            for node in plan.order:
                self.graph.add_workflow(node)
        pending = {node.workflow_id: node for node in plan.order}

        while pending:
            ready = self.graph.get_ready_workflows(self.state.completed)
            if not ready:
                raise ValueError("No ready workflows (possible cycle)")

            futures = {}
            with ThreadPoolExecutor(max_workers=len(ready)) as executor:
                for node in ready:
                    decision = plan.assignments.get(node.workflow_id) or self.router.route(node)
                    if not self.scheduler.acquire(node.workflow_id, decision.provider):
                        continue
                    self.state.mark_running(node.workflow_id)
                    futures[executor.submit(self._execute_node, node, decision)] = (node, decision)

                if not futures:
                    raise RuntimeError("No workflows scheduled due to resource limits")

                for future in as_completed(futures):
                    node, decision = futures[future]
                    manifest = future.result()
                    results.append(manifest)
                    self.scheduler.release(node.workflow_id, decision.provider)
                    if manifest.get("status") == "failed":
                        self.state.mark_failed(node.workflow_id, manifest)
                    else:
                        self.state.mark_completed(node.workflow_id, manifest)
                    pending.pop(node.workflow_id, None)
        return results

    def execute_single(self, module: str, workflow: str) -> Dict[str, Any]:
        decision = self.route_workflow(module, workflow)
        node = WorkflowNode(module=module, workflow=workflow)
        return self._execute_node(node, decision)

    def _execute_node(self, node: WorkflowNode, decision: RoutingDecision) -> Dict[str, Any]:
        provider = None
        if decision.provider:
            provider = self.providers.get(decision.provider)
        executor = None
        if decision.agent:
            executor = execution.PlanExecutor(decision.agent, provider)
        return self.engine.run(
            node.module,
            node.workflow,
            executor=executor,
            agent_name=decision.agent,
        )
