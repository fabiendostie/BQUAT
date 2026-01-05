from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from runtime import models, prompts


def split_artifacts(artifacts: List[str]) -> Tuple[List[str], List[str]]:
    outputs: List[str] = []
    templates: List[str] = []
    for artifact in artifacts:
        if artifact.startswith("template:"):
            templates.append(artifact.split("template:", 1)[1])
        else:
            outputs.append(artifact)
    return outputs, templates


@dataclass(frozen=True)
class AgentPlan:
    workflow: models.WorkflowSpec
    prompt: str
    outputs: List[str]
    templates: List[str]
    framework: str


class BaseAgent:
    framework: str

    def __init__(self, framework: str) -> None:
        self.framework = framework

    def build_plan(self, spec: models.WorkflowSpec) -> AgentPlan:
        outputs, templates = split_artifacts(spec.artifacts)
        context = {
            "workflow": spec.workflow,
            "phase": spec.phase,
            "outputs": ", ".join(outputs) if outputs else "none",
            "quint": spec.quint,
            "telis": spec.telis,
        }
        template = prompts.get_template(self.framework)
        prompt = prompts.render_prompt(template, context)
        return AgentPlan(
            workflow=spec,
            prompt=prompt,
            outputs=outputs,
            templates=templates,
            framework=self.framework,
        )


class BMADAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("bmad")


class TELISAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("telis")


class QUINTAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("quint")


AGENTS: Dict[str, BaseAgent] = {
    "bmad": BMADAgent(),
    "telis": TELISAgent(),
    "quint": QUINTAgent(),
}


def get_agent(name: str) -> BaseAgent:
    if name not in AGENTS:
        raise KeyError(f"Unknown agent: {name}")
    return AGENTS[name]


# ---------------------------------------------------------------------------
# Agent Definition and Registry (REQ-AGENT-001)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentDefinition:
    """Definition of an agent with its tool bindings and instructions.

    An agent definition specifies:
    - Which tools the agent can use
    - Per-tool instructions for prompt injection
    - Model configuration (provider, parameters)
    """

    name: str
    framework: str
    description: str = ""
    tools: tuple[str, ...] = field(default_factory=tuple)
    instructions: Dict[str, str] = field(default_factory=dict)
    model_config: Dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if isinstance(self.tools, list):
            object.__setattr__(self, "tools", tuple(self.tools))
        if isinstance(self.tags, list):
            object.__setattr__(self, "tags", tuple(self.tags))

    def can_use_tool(self, tool_name: str) -> bool:
        """Check if this agent can use a specific tool."""
        if not self.tools:
            return True
        return tool_name in self.tools

    def get_tool_instruction(self, tool_name: str) -> Optional[str]:
        """Get the per-tool instruction for a specific tool."""
        return self.instructions.get(tool_name)

    def get_all_instructions(self) -> str:
        """Get all per-tool instructions as a combined string."""
        if not self.instructions:
            return ""
        lines = []
        for tool_name, instruction in sorted(self.instructions.items()):
            lines.append(f"- {tool_name}: {instruction}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "framework": self.framework,
            "description": self.description,
            "tools": list(self.tools),
            "instructions": dict(self.instructions),
            "model_config": dict(self.model_config),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentDefinition:
        return cls(
            name=data.get("name", ""),
            framework=data.get("framework", ""),
            description=data.get("description", ""),
            tools=tuple(data.get("tools", [])),
            instructions=dict(data.get("instructions", {})),
            model_config=dict(data.get("model_config", {})),
            tags=tuple(data.get("tags", [])),
        )


# Default agent definitions
DEFAULT_BMAD_AGENT = AgentDefinition(
    name="bmad",
    framework="bmad",
    description="BMAD workflow execution agent for planning and development phases",
    tools=(
        "getCurrentTime",
        "readTextFile",
        "writeTextFile",
        "listDirectory",
        "gitStatus",
        "gitDiff",
        "validateAst",
        "typecheck",
        "lint",
    ),
    instructions={
        "writeTextFile": "Use BMAD templates and output conventions",
        "getCurrentTime": "Include timestamps in document headers",
    },
    model_config={"temperature": 0.7, "max_tokens": 4096},
    tags=("planning", "development", "artifacts"),
)

DEFAULT_TELIS_AGENT = AgentDefinition(
    name="telis",
    framework="telis",
    description="TELIS context management agent for token efficiency",
    tools=("getCurrentTime", "readTextFile", "validateAst", "typecheck"),
    instructions={"readTextFile": "Minimize context by reading only relevant sections"},
    model_config={"temperature": 0.3, "max_tokens": 2048},
    tags=("context", "efficiency", "validation"),
)

DEFAULT_QUINT_AGENT = AgentDefinition(
    name="quint",
    framework="quint",
    description="QUINT evidence agent for validation and DRR generation",
    tools=(
        "getCurrentTime",
        "readTextFile",
        "writeTextFile",
        "validateAst",
        "typecheck",
        "lint",
    ),
    instructions={"writeTextFile": "Generate DRR documents with proper evidence structure"},
    model_config={"temperature": 0.5, "max_tokens": 3072},
    tags=("evidence", "validation", "drr"),
)


class AgentRegistry:
    """Registry for agent definitions with tool bindings."""

    def __init__(self, load_defaults: bool = True) -> None:
        self._agents: Dict[str, AgentDefinition] = {}
        if load_defaults:
            self._load_default_agents()

    def _load_default_agents(self) -> None:
        self.register(DEFAULT_BMAD_AGENT)
        self.register(DEFAULT_TELIS_AGENT)
        self.register(DEFAULT_QUINT_AGENT)

    def register(self, definition: AgentDefinition) -> None:
        if definition.name in self._agents:
            raise ValueError(f"Agent '{definition.name}' is already registered")
        self._agents[definition.name] = definition

    def register_or_update(self, definition: AgentDefinition) -> bool:
        existed = definition.name in self._agents
        self._agents[definition.name] = definition
        return existed

    def unregister(self, name: str) -> bool:
        if name in self._agents:
            del self._agents[name]
            return True
        return False

    def get(self, name: str) -> Optional[AgentDefinition]:
        return self._agents.get(name)

    def contains(self, name: str) -> bool:
        return name in self._agents

    def list_all(self) -> List[AgentDefinition]:
        return list(self._agents.values())

    def list_names(self) -> List[str]:
        return list(self._agents.keys())

    def list_by_framework(self, framework: str) -> List[AgentDefinition]:
        return [a for a in self._agents.values() if a.framework == framework]

    def list_by_tag(self, tag: str) -> List[AgentDefinition]:
        return [a for a in self._agents.values() if tag in a.tags]

    def get_tools_for_agent(self, name: str) -> List[str]:
        agent = self._agents.get(name)
        if agent is None:
            return []
        return list(agent.tools)

    def can_agent_use_tool(self, agent_name: str, tool_name: str) -> bool:
        agent = self._agents.get(agent_name)
        if agent is None:
            return False
        return agent.can_use_tool(tool_name)

    def get_tool_instruction(self, agent_name: str, tool_name: str) -> Optional[str]:
        agent = self._agents.get(agent_name)
        if agent is None:
            return None
        return agent.get_tool_instruction(tool_name)

    def get_all_instructions(self, agent_name: str) -> str:
        agent = self._agents.get(agent_name)
        if agent is None:
            return ""
        return agent.get_all_instructions()

    def get_model_config(self, agent_name: str) -> Dict[str, Any]:
        agent = self._agents.get(agent_name)
        if agent is None:
            return {}
        return dict(agent.model_config)

    def get_frameworks(self) -> Set[str]:
        return {a.framework for a in self._agents.values()}

    def get_all_tags(self) -> Set[str]:
        tags: Set[str] = set()
        for agent in self._agents.values():
            tags.update(agent.tags)
        return tags

    def clear(self) -> int:
        count = len(self._agents)
        self._agents.clear()
        return count

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __iter__(self):
        return iter(self._agents.values())


_default_registry: Optional[AgentRegistry] = None


def get_default_agent_registry() -> AgentRegistry:
    """Get or create the default global agent registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = AgentRegistry(load_defaults=True)
    return _default_registry


def reset_default_agent_registry() -> None:
    """Reset the default global agent registry."""
    global _default_registry
    if _default_registry is not None:
        _default_registry.clear()
    _default_registry = None
