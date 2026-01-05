"""Tests for the dynamic tool registry (REQ-AGENT-002)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from runtime.tools.registry import (  # noqa: E402
    ToolCategory,
    ToolMetadata,
    ToolRegistry,
    get_default_registry,
    reset_default_registry,
)


def dummy_handler(args: Dict[str, Any], ctx: Any) -> Any:
    return {"result": "ok"}


class TestToolMetadata:
    def test_create_metadata(self) -> None:
        metadata = ToolMetadata(
            name="testTool",
            version="1.0.0",
            category="custom",
            description="A test tool",
            risk="low",
            spec={"name": "testTool"},
            tags=("test", "example"),
        )
        assert metadata.name == "testTool"
        assert metadata.version == "1.0.0"
        assert metadata.category == "custom"
        assert metadata.risk == "low"
        assert "test" in metadata.tags

    def test_to_dict(self) -> None:
        metadata = ToolMetadata(
            name="testTool",
            version="1.0.0",
            category="io",
            description="Test",
            risk="medium",
        )
        data = metadata.to_dict()
        assert data["name"] == "testTool"
        assert data["category"] == "io"
        assert data["risk"] == "medium"
        assert isinstance(data["tags"], list)

    def test_from_spec(self) -> None:
        spec = {
            "name": "readFile",
            "description": "Read a file",
            "risk": "low",
            "parameters": {},
        }
        metadata = ToolMetadata.from_spec(
            name="readFile",
            spec=spec,
            category="io",
            version="2.0.0",
            tags=["file", "read"],
        )
        assert metadata.name == "readFile"
        assert metadata.category == "io"
        assert metadata.version == "2.0.0"
        assert "file" in metadata.tags


class TestToolCategory:
    def test_categories_exist(self) -> None:
        assert ToolCategory.IO.value == "io"
        assert ToolCategory.VALIDATION.value == "validation"
        assert ToolCategory.REPO.value == "repo"
        assert ToolCategory.TIME.value == "time"
        assert ToolCategory.LSP.value == "lsp"
        assert ToolCategory.CUSTOM.value == "custom"


class TestToolRegistry:
    def test_register_tool(self) -> None:
        registry = ToolRegistry()
        metadata = ToolMetadata(
            name="testTool",
            version="1.0.0",
            category="custom",
            description="Test",
            risk="low",
        )
        registry.register("testTool", dummy_handler, metadata)

        assert "testTool" in registry
        assert len(registry) == 1

    def test_register_duplicate_raises(self) -> None:
        registry = ToolRegistry()
        metadata = ToolMetadata(
            name="testTool",
            version="1.0.0",
            category="custom",
            description="Test",
            risk="low",
        )
        registry.register("testTool", dummy_handler, metadata)

        with pytest.raises(ValueError, match="already registered"):
            registry.register("testTool", dummy_handler, metadata)

    def test_register_from_spec(self) -> None:
        registry = ToolRegistry()
        spec = {
            "name": "myTool",
            "description": "My tool",
            "risk": "medium",
        }
        registry.register_from_spec(
            name="myTool",
            handler=dummy_handler,
            spec=spec,
            category="io",
            version="1.0.0",
        )

        tool = registry.get("myTool")
        assert tool is not None
        assert tool.metadata.category == "io"
        assert tool.metadata.risk == "medium"

    def test_unregister(self) -> None:
        registry = ToolRegistry()
        metadata = ToolMetadata(
            name="testTool",
            version="1.0.0",
            category="custom",
            description="Test",
            risk="low",
        )
        registry.register("testTool", dummy_handler, metadata)

        result = registry.unregister("testTool")
        assert result is True
        assert "testTool" not in registry

    def test_unregister_not_found(self) -> None:
        registry = ToolRegistry()
        result = registry.unregister("nonexistent")
        assert result is False

    def test_get_tool(self) -> None:
        registry = ToolRegistry()
        metadata = ToolMetadata(
            name="testTool",
            version="1.0.0",
            category="custom",
            description="Test",
            risk="low",
        )
        registry.register("testTool", dummy_handler, metadata)

        tool = registry.get("testTool")
        assert tool is not None
        assert tool.name == "testTool"
        assert tool.handler is dummy_handler

    def test_get_not_found(self) -> None:
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_contains(self) -> None:
        registry = ToolRegistry()
        metadata = ToolMetadata(
            name="testTool",
            version="1.0.0",
            category="custom",
            description="Test",
            risk="low",
        )
        registry.register("testTool", dummy_handler, metadata)

        assert registry.contains("testTool") is True
        assert registry.contains("nonexistent") is False

    def test_enable_disable(self) -> None:
        registry = ToolRegistry()
        metadata = ToolMetadata(
            name="testTool",
            version="1.0.0",
            category="custom",
            description="Test",
            risk="low",
        )
        registry.register("testTool", dummy_handler, metadata)

        # Disable
        result = registry.disable("testTool")
        assert result is True
        assert registry.get("testTool") is None
        assert registry.contains("testTool") is False

        # Re-enable
        result = registry.enable("testTool")
        assert result is True
        assert registry.get("testTool") is not None

    def test_list_all(self) -> None:
        registry = ToolRegistry()
        for i in range(3):
            metadata = ToolMetadata(
                name=f"tool{i}",
                version="1.0.0",
                category="custom",
                description=f"Tool {i}",
                risk="low",
            )
            registry.register(f"tool{i}", dummy_handler, metadata)

        tools = registry.list_all()
        assert len(tools) == 3

    def test_list_names(self) -> None:
        registry = ToolRegistry()
        for i in range(3):
            metadata = ToolMetadata(
                name=f"tool{i}",
                version="1.0.0",
                category="custom",
                description=f"Tool {i}",
                risk="low",
            )
            registry.register(f"tool{i}", dummy_handler, metadata)

        names = registry.list_names()
        assert "tool0" in names
        assert "tool1" in names
        assert "tool2" in names

    def test_list_by_category(self) -> None:
        registry = ToolRegistry()

        io_metadata = ToolMetadata(
            name="ioTool",
            version="1.0.0",
            category="io",
            description="IO tool",
            risk="low",
        )
        registry.register("ioTool", dummy_handler, io_metadata)

        repo_metadata = ToolMetadata(
            name="repoTool",
            version="1.0.0",
            category="repo",
            description="Repo tool",
            risk="low",
        )
        registry.register("repoTool", dummy_handler, repo_metadata)

        io_tools = registry.list_by_category("io")
        assert len(io_tools) == 1
        assert io_tools[0].name == "ioTool"

        repo_tools = registry.list_by_category("repo")
        assert len(repo_tools) == 1
        assert repo_tools[0].name == "repoTool"

    def test_list_by_risk(self) -> None:
        registry = ToolRegistry()

        low_metadata = ToolMetadata(
            name="safeTool",
            version="1.0.0",
            category="custom",
            description="Safe tool",
            risk="low",
        )
        registry.register("safeTool", dummy_handler, low_metadata)

        high_metadata = ToolMetadata(
            name="dangerousTool",
            version="1.0.0",
            category="custom",
            description="Dangerous tool",
            risk="high",
        )
        registry.register("dangerousTool", dummy_handler, high_metadata)

        low_tools = registry.list_by_risk("low")
        assert len(low_tools) == 1
        assert low_tools[0].name == "safeTool"

        high_tools = registry.list_by_risk("high")
        assert len(high_tools) == 1
        assert high_tools[0].name == "dangerousTool"

    def test_list_by_tag(self) -> None:
        registry = ToolRegistry()

        metadata = ToolMetadata(
            name="taggedTool",
            version="1.0.0",
            category="custom",
            description="Tagged tool",
            risk="low",
            tags=("important", "featured"),
        )
        registry.register("taggedTool", dummy_handler, metadata)

        important = registry.list_by_tag("important")
        assert len(important) == 1

        other = registry.list_by_tag("other")
        assert len(other) == 0

    def test_get_categories(self) -> None:
        registry = ToolRegistry()

        for cat in ["io", "repo", "validation"]:
            metadata = ToolMetadata(
                name=f"{cat}Tool",
                version="1.0.0",
                category=cat,
                description=f"{cat} tool",
                risk="low",
            )
            registry.register(f"{cat}Tool", dummy_handler, metadata)

        categories = registry.get_categories()
        assert "io" in categories
        assert "repo" in categories
        assert "validation" in categories

    def test_get_capabilities(self) -> None:
        registry = ToolRegistry()

        for i, cat in enumerate(["io", "io", "repo"]):
            metadata = ToolMetadata(
                name=f"tool{i}",
                version="1.0.0",
                category=cat,
                description=f"Tool {i}",
                risk="low",
            )
            registry.register(f"tool{i}", dummy_handler, metadata)

        caps = registry.get_capabilities()
        assert len(caps["io"]) == 2
        assert len(caps["repo"]) == 1

    def test_clear(self) -> None:
        registry = ToolRegistry()
        for i in range(5):
            metadata = ToolMetadata(
                name=f"tool{i}",
                version="1.0.0",
                category="custom",
                description=f"Tool {i}",
                risk="low",
            )
            registry.register(f"tool{i}", dummy_handler, metadata)

        count = registry.clear()
        assert count == 5
        assert len(registry) == 0

    def test_iteration(self) -> None:
        registry = ToolRegistry()
        for i in range(3):
            metadata = ToolMetadata(
                name=f"tool{i}",
                version="1.0.0",
                category="custom",
                description=f"Tool {i}",
                risk="low",
            )
            registry.register(f"tool{i}", dummy_handler, metadata)

        tools = list(registry)
        assert len(tools) == 3


class TestDefaultRegistry:
    def test_get_default_registry(self) -> None:
        reset_default_registry()
        reg1 = get_default_registry()
        reg2 = get_default_registry()
        assert reg1 is reg2

    def test_reset_default_registry(self) -> None:
        reset_default_registry()
        reg1 = get_default_registry()
        reset_default_registry()
        reg2 = get_default_registry()
        assert reg1 is not reg2
