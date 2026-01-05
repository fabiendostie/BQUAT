from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from runtime.orchestrator.graph import WorkflowNode


@dataclass(frozen=True)
class RoutingDecision:
    agent: str
    provider: str
    reason: str = ""


class AgentRouter:
    def __init__(self, config: Dict[str, object]) -> None:
        self.config = config

    def select_agent(self, node: WorkflowNode) -> str:
        if node.agent:
            return node.agent
        orchestrator_cfg = (
            self.config.get("orchestrator", {}) if isinstance(self.config, dict) else {}
        )
        if isinstance(orchestrator_cfg, dict):
            default_agent = orchestrator_cfg.get("default_agent")
        else:
            default_agent = None
        return str(default_agent or "bmad")


class ProviderRouter:
    def __init__(self, config: Dict[str, object]) -> None:
        self.config = config

    def select_provider(self, node: WorkflowNode) -> str:
        if node.provider:
            return node.provider
        providers_cfg = self.config.get("providers", {}) if isinstance(self.config, dict) else {}
        if isinstance(providers_cfg, dict):
            default_provider = providers_cfg.get("default", "")
        else:
            default_provider = ""
        return str(default_provider)


class AgentProviderRouter:
    def __init__(self, config: Dict[str, object]) -> None:
        self.agent_router = AgentRouter(config)
        self.provider_router = ProviderRouter(config)

    def route(self, node: WorkflowNode) -> RoutingDecision:
        agent = self.agent_router.select_agent(node)
        provider = self.provider_router.select_provider(node)
        reason = "explicit" if node.agent or node.provider else "default"
        return RoutingDecision(agent=agent, provider=provider, reason=reason)
