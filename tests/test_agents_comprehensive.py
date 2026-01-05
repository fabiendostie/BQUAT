"""Comprehensive tests for runtime/agents.py to achieve 85%+ coverage."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models  # noqa: E402
from runtime.agents import (  # noqa: E402
    AGENTS,
    DEFAULT_BMAD_AGENT,
    DEFAULT_QUINT_AGENT,
    DEFAULT_TELIS_AGENT,
    AgentDefinition,
    AgentPlan,
    AgentRegistry,
    BaseAgent,
    BMADAgent,
    QUINTAgent,
    TELISAgent,
    get_agent,
    get_default_agent_registry,
    reset_default_agent_registry,
    split_artifacts,
)


class TestSplitArtifacts(unittest.TestCase):
    """Test the split_artifacts function."""

    def test_split_empty(self) -> None:
        outputs, templates = split_artifacts([])
        self.assertEqual(outputs, [])
        self.assertEqual(templates, [])

    def test_split_only_outputs(self) -> None:
        outputs, templates = split_artifacts(["output1.md", "output2.md"])
        self.assertEqual(outputs, ["output1.md", "output2.md"])
        self.assertEqual(templates, [])

    def test_split_only_templates(self) -> None:
        outputs, templates = split_artifacts(["template:t1.md", "template:t2.md"])
        self.assertEqual(outputs, [])
        self.assertEqual(templates, ["t1.md", "t2.md"])

    def test_split_mixed(self) -> None:
        outputs, templates = split_artifacts(
            [
                "output.md",
                "template:template.md",
                "another.md",
            ]
        )
        self.assertEqual(outputs, ["output.md", "another.md"])
        self.assertEqual(templates, ["template.md"])


class TestBaseAgent(unittest.TestCase):
    """Test BaseAgent class."""

    def test_create_base_agent(self) -> None:
        agent = BaseAgent("test")
        self.assertEqual(agent.framework, "test")

    def test_build_plan(self) -> None:
        agent = BaseAgent("bmad")
        spec = models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            quint="Deduction (L1)",
            telis="Tier 1 minimal",
            validation="Template/schema validation",
            human="required",
            evidence="L1",
            artifacts=["output.md", "template:t.md"],
            scope="production",
            path="test/path",
        )
        plan = agent.build_plan(spec)

        self.assertIsInstance(plan, AgentPlan)
        self.assertEqual(plan.framework, "bmad")
        self.assertIn("output.md", plan.outputs)
        self.assertIn("t.md", plan.templates)
        self.assertEqual(plan.workflow, spec)


class TestAgentClasses(unittest.TestCase):
    """Test specific agent classes."""

    def test_bmad_agent(self) -> None:
        agent = BMADAgent()
        self.assertEqual(agent.framework, "bmad")

    def test_telis_agent(self) -> None:
        agent = TELISAgent()
        self.assertEqual(agent.framework, "telis")

    def test_quint_agent(self) -> None:
        agent = QUINTAgent()
        self.assertEqual(agent.framework, "quint")


class TestGetAgent(unittest.TestCase):
    """Test get_agent function."""

    def test_get_bmad(self) -> None:
        agent = get_agent("bmad")
        self.assertIsInstance(agent, BMADAgent)

    def test_get_telis(self) -> None:
        agent = get_agent("telis")
        self.assertIsInstance(agent, TELISAgent)

    def test_get_quint(self) -> None:
        agent = get_agent("quint")
        self.assertIsInstance(agent, QUINTAgent)

    def test_get_unknown_raises(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            get_agent("unknown")
        self.assertIn("Unknown agent", str(ctx.exception))


class TestAgentDefinition(unittest.TestCase):
    """Test AgentDefinition dataclass."""

    def test_create_minimal(self) -> None:
        defn = AgentDefinition(name="test", framework="test")
        self.assertEqual(defn.name, "test")
        self.assertEqual(defn.framework, "test")
        self.assertEqual(defn.description, "")
        self.assertEqual(len(defn.tools), 0)

    def test_create_full(self) -> None:
        defn = AgentDefinition(
            name="full",
            framework="full",
            description="Full agent",
            tools=("tool1", "tool2"),
            instructions={"tool1": "Use carefully"},
            model_config={"temp": 0.5},
            tags=("tag1", "tag2"),
        )
        self.assertEqual(defn.name, "full")
        self.assertEqual(len(defn.tools), 2)
        self.assertEqual(defn.instructions["tool1"], "Use carefully")
        self.assertIn("tag1", defn.tags)

    def test_post_init_converts_lists(self) -> None:
        defn = AgentDefinition(
            name="test",
            framework="test",
            tools=["a", "b"],  # type: ignore - testing conversion
            tags=["x", "y"],  # type: ignore - testing conversion
        )
        self.assertIsInstance(defn.tools, tuple)
        self.assertIsInstance(defn.tags, tuple)

    def test_can_use_tool_in_list(self) -> None:
        defn = AgentDefinition(
            name="test",
            framework="test",
            tools=("allowed1", "allowed2"),
        )
        self.assertTrue(defn.can_use_tool("allowed1"))
        self.assertTrue(defn.can_use_tool("allowed2"))
        self.assertFalse(defn.can_use_tool("notallowed"))

    def test_can_use_tool_empty_allows_all(self) -> None:
        defn = AgentDefinition(name="test", framework="test", tools=())
        self.assertTrue(defn.can_use_tool("any"))
        self.assertTrue(defn.can_use_tool("tool"))

    def test_get_tool_instruction(self) -> None:
        defn = AgentDefinition(
            name="test",
            framework="test",
            instructions={"tool1": "Instruction 1", "tool2": "Instruction 2"},
        )
        self.assertEqual(defn.get_tool_instruction("tool1"), "Instruction 1")
        self.assertEqual(defn.get_tool_instruction("tool2"), "Instruction 2")
        self.assertIsNone(defn.get_tool_instruction("tool3"))

    def test_get_all_instructions(self) -> None:
        defn = AgentDefinition(
            name="test",
            framework="test",
            instructions={"tool1": "First", "tool2": "Second"},
        )
        all_instr = defn.get_all_instructions()
        self.assertIn("tool1: First", all_instr)
        self.assertIn("tool2: Second", all_instr)

    def test_get_all_instructions_empty(self) -> None:
        defn = AgentDefinition(name="test", framework="test")
        self.assertEqual(defn.get_all_instructions(), "")

    def test_to_dict(self) -> None:
        defn = AgentDefinition(
            name="test",
            framework="test",
            description="Desc",
            tools=("t1",),
            instructions={"t1": "Instr"},
            model_config={"temp": 0.7},
            tags=("tag",),
        )
        data = defn.to_dict()
        self.assertEqual(data["name"], "test")
        self.assertEqual(data["tools"], ["t1"])
        self.assertEqual(data["tags"], ["tag"])
        self.assertEqual(data["model_config"], {"temp": 0.7})

    def test_from_dict(self) -> None:
        data = {
            "name": "from-dict",
            "framework": "fd",
            "description": "From dict",
            "tools": ["a", "b"],
            "instructions": {"a": "inst"},
            "model_config": {"x": 1},
            "tags": ["y"],
        }
        defn = AgentDefinition.from_dict(data)
        self.assertEqual(defn.name, "from-dict")
        self.assertEqual(defn.framework, "fd")
        self.assertIn("a", defn.tools)
        self.assertEqual(defn.instructions["a"], "inst")

    def test_from_dict_defaults(self) -> None:
        defn = AgentDefinition.from_dict({})
        self.assertEqual(defn.name, "")
        self.assertEqual(defn.framework, "")


class TestDefaultAgentDefinitions(unittest.TestCase):
    """Test default agent definitions."""

    def test_default_bmad(self) -> None:
        self.assertEqual(DEFAULT_BMAD_AGENT.name, "bmad")
        self.assertEqual(DEFAULT_BMAD_AGENT.framework, "bmad")
        self.assertIn("getCurrentTime", DEFAULT_BMAD_AGENT.tools)
        self.assertIn("readTextFile", DEFAULT_BMAD_AGENT.tools)
        self.assertIn("planning", DEFAULT_BMAD_AGENT.tags)

    def test_default_telis(self) -> None:
        self.assertEqual(DEFAULT_TELIS_AGENT.name, "telis")
        self.assertEqual(DEFAULT_TELIS_AGENT.framework, "telis")
        self.assertIn("context", DEFAULT_TELIS_AGENT.tags)

    def test_default_quint(self) -> None:
        self.assertEqual(DEFAULT_QUINT_AGENT.name, "quint")
        self.assertEqual(DEFAULT_QUINT_AGENT.framework, "quint")
        self.assertIn("evidence", DEFAULT_QUINT_AGENT.tags)


class TestAgentRegistry(unittest.TestCase):
    """Test AgentRegistry class."""

    def test_create_empty(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        self.assertEqual(len(registry), 0)

    def test_create_with_defaults(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        self.assertIn("bmad", registry)
        self.assertIn("telis", registry)
        self.assertIn("quint", registry)

    def test_register(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        defn = AgentDefinition(name="custom", framework="custom")
        registry.register(defn)
        self.assertIn("custom", registry)

    def test_register_duplicate_raises(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        defn = AgentDefinition(name="dup", framework="dup")
        registry.register(defn)
        with self.assertRaises(ValueError):
            registry.register(defn)

    def test_register_or_update(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        defn1 = AgentDefinition(name="test", framework="v1", description="V1")
        defn2 = AgentDefinition(name="test", framework="v2", description="V2")

        existed = registry.register_or_update(defn1)
        self.assertFalse(existed)

        existed = registry.register_or_update(defn2)
        self.assertTrue(existed)

        agent = registry.get("test")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.framework, "v2")

    def test_unregister(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        defn = AgentDefinition(name="test", framework="test")
        registry.register(defn)

        result = registry.unregister("test")
        self.assertTrue(result)
        self.assertNotIn("test", registry)

    def test_unregister_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        result = registry.unregister("nonexistent")
        self.assertFalse(result)

    def test_get(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        agent = registry.get("bmad")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "bmad")

    def test_get_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        self.assertIsNone(registry.get("missing"))

    def test_contains(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        self.assertTrue(registry.contains("bmad"))
        self.assertFalse(registry.contains("nonexistent"))

    def test_list_all(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        agent_list = registry.list_all()
        self.assertEqual(len(agent_list), 3)

    def test_list_names(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        names = registry.list_names()
        self.assertIn("bmad", names)
        self.assertIn("telis", names)
        self.assertIn("quint", names)

    def test_list_by_framework(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        bmad_agents = registry.list_by_framework("bmad")
        self.assertEqual(len(bmad_agents), 1)
        self.assertEqual(bmad_agents[0].name, "bmad")

    def test_list_by_tag(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        planning = registry.list_by_tag("planning")
        self.assertTrue(any(a.name == "bmad" for a in planning))

    def test_get_tools_for_agent(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        tools = registry.get_tools_for_agent("bmad")
        self.assertIn("getCurrentTime", tools)
        self.assertIn("readTextFile", tools)

    def test_get_tools_for_agent_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        tools = registry.get_tools_for_agent("missing")
        self.assertEqual(tools, [])

    def test_can_agent_use_tool(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        self.assertTrue(registry.can_agent_use_tool("bmad", "getCurrentTime"))
        self.assertFalse(registry.can_agent_use_tool("bmad", "unknownTool"))

    def test_can_agent_use_tool_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        self.assertFalse(registry.can_agent_use_tool("missing", "any"))

    def test_get_tool_instruction(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        instr = registry.get_tool_instruction("bmad", "writeTextFile")
        self.assertIsNotNone(instr)

    def test_get_tool_instruction_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        instr = registry.get_tool_instruction("bmad", "unknownTool")
        self.assertIsNone(instr)

    def test_get_all_instructions(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        instructions = registry.get_all_instructions("bmad")
        self.assertIn("writeTextFile", instructions)

    def test_get_all_instructions_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        instructions = registry.get_all_instructions("missing")
        self.assertEqual(instructions, "")

    def test_get_model_config(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        config = registry.get_model_config("bmad")
        self.assertIn("temperature", config)

    def test_get_model_config_not_found(self) -> None:
        registry = AgentRegistry(load_defaults=False)
        config = registry.get_model_config("missing")
        self.assertEqual(config, {})

    def test_get_frameworks(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        frameworks = registry.get_frameworks()
        self.assertIn("bmad", frameworks)
        self.assertIn("telis", frameworks)
        self.assertIn("quint", frameworks)

    def test_get_all_tags(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        tags = registry.get_all_tags()
        self.assertIn("planning", tags)
        self.assertIn("evidence", tags)

    def test_clear(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        count = registry.clear()
        self.assertEqual(count, 3)
        self.assertEqual(len(registry), 0)

    def test_len(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        self.assertEqual(len(registry), 3)

    def test_contains_operator(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        self.assertIn("bmad", registry)
        self.assertNotIn("missing", registry)

    def test_iter(self) -> None:
        registry = AgentRegistry(load_defaults=True)
        agent_items = list(registry)
        self.assertEqual(len(agent_items), 3)


class TestDefaultRegistry(unittest.TestCase):
    """Test default registry functions."""

    def test_get_default_registry(self) -> None:
        reset_default_agent_registry()
        reg1 = get_default_agent_registry()
        reg2 = get_default_agent_registry()
        self.assertIs(reg1, reg2)

    def test_reset_default_registry(self) -> None:
        reset_default_agent_registry()
        reg1 = get_default_agent_registry()
        reset_default_agent_registry()
        reg2 = get_default_agent_registry()
        self.assertIsNot(reg1, reg2)


class TestAgentsDict(unittest.TestCase):
    """Test the AGENTS dict."""

    def test_agents_contains_all(self) -> None:
        self.assertIn("bmad", AGENTS)
        self.assertIn("telis", AGENTS)
        self.assertIn("quint", AGENTS)


if __name__ == "__main__":
    unittest.main()
