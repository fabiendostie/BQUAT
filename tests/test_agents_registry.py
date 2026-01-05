"""Tests for the agent registry with per-agent tool bindings (REQ-AGENT-001)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from runtime.agents import (  # noqa: E402
    DEFAULT_BMAD_AGENT,
    DEFAULT_QUINT_AGENT,
    DEFAULT_TELIS_AGENT,
    AgentDefinition,
    AgentRegistry,
    get_default_agent_registry,
    reset_default_agent_registry,
)


class TestAgentDefinition:
    def test_create_definition(self) -> None:
        agent = AgentDefinition(
            name="test",
            framework="test-framework",
            description="Test agent",
            tools=("tool1", "tool2"),
            instructions={"tool1": "Use carefully"},
            model_config={"temperature": 0.5},
            tags=("test", "example"),
        )
        assert agent.name == "test"
        assert agent.framework == "test-framework"
        assert "tool1" in agent.tools
        assert agent.instructions["tool1"] == "Use carefully"

    def test_can_use_tool_in_list(self) -> None:
        agent = AgentDefinition(
            name="test",
            framework="test",
            tools=("tool1", "tool2"),
        )
        assert agent.can_use_tool("tool1") is True
        assert agent.can_use_tool("tool2") is True
        assert agent.can_use_tool("tool3") is False

    def test_can_use_tool_empty_list_allows_all(self) -> None:
        agent = AgentDefinition(
            name="test",
            framework="test",
            tools=(),  # Empty = allows all
        )
        assert agent.can_use_tool("anyTool") is True
        assert agent.can_use_tool("anotherTool") is True

    def test_get_tool_instruction(self) -> None:
        agent = AgentDefinition(
            name="test",
            framework="test",
            instructions={
                "tool1": "Instruction 1",
                "tool2": "Instruction 2",
            },
        )
        assert agent.get_tool_instruction("tool1") == "Instruction 1"
        assert agent.get_tool_instruction("tool2") == "Instruction 2"
        assert agent.get_tool_instruction("tool3") is None

    def test_get_all_instructions(self) -> None:
        agent = AgentDefinition(
            name="test",
            framework="test",
            instructions={
                "tool1": "First instruction",
                "tool2": "Second instruction",
            },
        )
        all_instructions = agent.get_all_instructions()
        assert "tool1: First instruction" in all_instructions
        assert "tool2: Second instruction" in all_instructions

    def test_get_all_instructions_empty(self) -> None:
        agent = AgentDefinition(
            name="test",
            framework="test",
        )
        assert agent.get_all_instructions() == ""

    def test_to_dict(self) -> None:
        agent = AgentDefinition(
            name="test",
            framework="test",
            description="Test agent",
            tools=("tool1",),
            instructions={"tool1": "Instruction"},
            model_config={"temp": 0.7},
            tags=("tag1",),
        )
        data = agent.to_dict()
        assert data["name"] == "test"
        assert data["framework"] == "test"
        assert data["tools"] == ["tool1"]
        assert data["instructions"] == {"tool1": "Instruction"}
        assert data["model_config"] == {"temp": 0.7}
        assert data["tags"] == ["tag1"]

    def test_from_dict(self) -> None:
        data = {
            "name": "test",
            "framework": "test",
            "description": "Test agent",
            "tools": ["tool1", "tool2"],
            "instructions": {"tool1": "Instruction"},
            "model_config": {"temp": 0.7},
            "tags": ["tag1"],
        }
        agent = AgentDefinition.from_dict(data)
        assert agent.name == "test"
        assert "tool1" in agent.tools
        assert "tag1" in agent.tags


class TestDefaultAgentDefinitions:
    def test_bmad_agent(self) -> None:
        assert DEFAULT_BMAD_AGENT.name == "bmad"
        assert DEFAULT_BMAD_AGENT.framework == "bmad"
        assert len(DEFAULT_BMAD_AGENT.tools) > 0
        assert "getCurrentTime" in DEFAULT_BMAD_AGENT.tools

    def test_telis_agent(self) -> None:
        assert DEFAULT_TELIS_AGENT.name == "telis"
        assert DEFAULT_TELIS_AGENT.framework == "telis"
        assert len(DEFAULT_TELIS_AGENT.tools) > 0

    def test_quint_agent(self) -> None:
        assert DEFAULT_QUINT_AGENT.name == "quint"
        assert DEFAULT_QUINT_AGENT.framework == "quint"
        assert len(DEFAULT_QUINT_AGENT.tools) > 0


class TestAgentRegistry:
    def test_create_empty(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        assert len(registry) == 0

    def test_create_with_defaults(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        assert "bmad" in registry
        assert "telis" in registry
        assert "quint" in registry

    def test_register(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        agent = AgentDefinition(
            name="custom",
            framework="custom",
        )
        registry.register(agent)
        assert "custom" in registry
        assert len(registry) == 1

    def test_register_duplicate_raises(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        agent = AgentDefinition(
            name="custom",
            framework="custom",
        )
        registry.register(agent)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(agent)

    def test_register_or_update(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        agent1 = AgentDefinition(
            name="custom",
            framework="custom",
            description="Version 1",
        )
        agent2 = AgentDefinition(
            name="custom",
            framework="custom",
            description="Version 2",
        )

        existed = registry.register_or_update(agent1)
        assert existed is False

        existed = registry.register_or_update(agent2)
        assert existed is True

        agent = registry.get("custom")
        assert agent is not None
        assert agent.description == "Version 2"

    def test_unregister(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        agent = AgentDefinition(
            name="custom",
            framework="custom",
        )
        registry.register(agent)

        result = registry.unregister("custom")
        assert result is True
        assert "custom" not in registry

    def test_unregister_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        result = registry.unregister("nonexistent")
        assert result is False

    def test_get(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        agent = registry.get("bmad")
        assert agent is not None
        assert agent.name == "bmad"

    def test_get_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        assert registry.get("nonexistent") is None

    def test_contains(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        assert registry.contains("bmad") is True
        assert registry.contains("nonexistent") is False

    def test_list_all(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        agents = registry.list_all()
        assert len(agents) == 3
        names = [a.name for a in agents]
        assert "bmad" in names

    def test_list_names(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        names = registry.list_names()
        assert "bmad" in names
        assert "telis" in names
        assert "quint" in names

    def test_list_by_framework(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        bmad_agents = registry.list_by_framework("bmad")
        assert len(bmad_agents) == 1
        assert bmad_agents[0].name == "bmad"

    def test_list_by_tag(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        planning_agents = registry.list_by_tag("planning")
        assert len(planning_agents) >= 1
        assert any(a.name == "bmad" for a in planning_agents)

    def test_get_tools_for_agent(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        tools = registry.get_tools_for_agent("bmad")
        assert "getCurrentTime" in tools
        assert "readTextFile" in tools

    def test_get_tools_for_agent_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        tools = registry.get_tools_for_agent("nonexistent")
        assert tools == []

    def test_can_agent_use_tool(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        assert registry.can_agent_use_tool("bmad", "getCurrentTime") is True
        assert registry.can_agent_use_tool("bmad", "unknownTool") is False

    def test_can_agent_use_tool_agent_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        assert registry.can_agent_use_tool("nonexistent", "anyTool") is False

    def test_get_tool_instruction(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        instruction = registry.get_tool_instruction("bmad", "writeTextFile")
        assert instruction is not None
        assert "BMAD" in instruction

    def test_get_tool_instruction_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        instruction = registry.get_tool_instruction("bmad", "unknownTool")
        assert instruction is None

    def test_get_all_instructions(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        instructions = registry.get_all_instructions("bmad")
        assert len(instructions) > 0
        assert "writeTextFile" in instructions

    def test_get_all_instructions_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        instructions = registry.get_all_instructions("nonexistent")
        assert instructions == ""

    def test_get_model_config(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        config = registry.get_model_config("bmad")
        assert "temperature" in config

    def test_get_model_config_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        config = registry.get_model_config("nonexistent")
        assert config == {}

    def test_get_frameworks(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        frameworks = registry.get_frameworks()
        assert "bmad" in frameworks
        assert "telis" in frameworks
        assert "quint" in frameworks

    def test_get_all_tags(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        tags = registry.get_all_tags()
        assert "planning" in tags
        assert "evidence" in tags

    def test_clear(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        count = registry.clear()
        assert count == 3
        assert len(registry) == 0

    def test_iteration(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        agents = list(registry)
        assert len(agents) == 3


class TestDefaultAgentRegistry:
    def test_get_default_agent_registry(self) -> None:
        reset_default_agent_registry()
        reg1 = get_default_agent_registry()
        reg2 = get_default_agent_registry()
        assert reg1 is reg2
        assert "bmad" in reg1

    def test_reset_default_agent_registry(self) -> None:
        reset_default_agent_registry()
        reg1 = get_default_agent_registry()
        reset_default_agent_registry()
        reg2 = get_default_agent_registry()
        assert reg1 is not reg2
