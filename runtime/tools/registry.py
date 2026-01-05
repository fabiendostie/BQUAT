from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from runtime.tools import file_io, repo_tool, time_tool, validation
from runtime.tools.base import normalize_risk

ToolHandler = Callable[[Dict[str, Any], Any], Any]


class ToolCategory(str, Enum):
    """Standard tool categories."""

    IO = "io"
    VALIDATION = "validation"
    REPO = "repo"
    TIME = "time"
    LSP = "lsp"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ToolMetadata:
    """Metadata describing a registered tool."""

    name: str
    version: str
    category: str
    description: str
    risk: str
    spec: Dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "description": self.description,
            "risk": self.risk,
            "spec": dict(self.spec),
            "tags": list(self.tags),
        }

    @classmethod
    def from_spec(
        cls,
        name: str,
        spec: Dict[str, Any],
        category: str = "custom",
        version: str = "1.0.0",
        tags: Optional[List[str]] = None,
    ) -> ToolMetadata:
        """Create metadata from a tool spec dictionary."""
        return cls(
            name=name,
            version=version,
            category=category,
            description=spec.get("description", ""),
            risk=normalize_risk(spec.get("risk", "low")),
            spec=dict(spec),
            tags=tuple(tags or []),
        )


@dataclass
class RegisteredTool:
    """A tool registered in the registry."""

    metadata: ToolMetadata
    handler: ToolHandler
    enabled: bool = True

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def spec(self) -> Dict[str, Any]:
        return self.metadata.spec

    @property
    def risk(self) -> str:
        return self.metadata.risk


class ToolRegistry:
    """Dynamic tool registry with categories and metadata.

    Supports:
    - Dynamic registration and unregistration of tools
    - Tool categorization
    - Tool metadata with version and tags
    - Filtering by category, risk level, or tags
    - Capability discovery

    Example:
        registry = ToolRegistry()
        registry.register(
            name="getCurrentTime",
            handler=time_handler,
            metadata=ToolMetadata(
                name="getCurrentTime",
                version="1.0.0",
                category="time",
                description="Get current timestamp",
                risk="low",
                spec=TIME_TOOL_SPEC,
            ),
        )

        # Get a specific tool
        tool = registry.get("getCurrentTime")

        # List all IO tools
        io_tools = registry.list_by_category("io")

        # Get capabilities
        caps = registry.get_capabilities()
    """

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        handler: ToolHandler,
        metadata: ToolMetadata,
    ) -> None:
        """Register a tool with the registry.

        Args:
            name: Unique tool name.
            handler: Function to execute the tool.
            metadata: Tool metadata including spec, category, risk.

        Raises:
            ValueError: If tool name is already registered.
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")
        self._tools[name] = RegisteredTool(
            metadata=metadata,
            handler=handler,
        )

    def register_from_spec(
        self,
        name: str,
        handler: ToolHandler,
        spec: Dict[str, Any],
        category: str = "custom",
        version: str = "1.0.0",
        tags: Optional[List[str]] = None,
    ) -> None:
        """Register a tool using a spec dictionary.

        Convenience method that creates ToolMetadata from spec.

        Args:
            name: Unique tool name.
            handler: Function to execute the tool.
            spec: Tool specification dictionary.
            category: Tool category.
            version: Tool version.
            tags: Optional tags for filtering.
        """
        metadata = ToolMetadata.from_spec(
            name=name,
            spec=spec,
            category=category,
            version=version,
            tags=tags,
        )
        self.register(name, handler, metadata)

    def unregister(self, name: str) -> bool:
        """Unregister a tool.

        Args:
            name: Tool name to remove.

        Returns:
            True if tool was found and removed, False otherwise.
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[RegisteredTool]:
        """Get a registered tool by name.

        Args:
            name: Tool name.

        Returns:
            RegisteredTool if found, None otherwise.
        """
        tool = self._tools.get(name)
        if tool and tool.enabled:
            return tool
        return None

    def contains(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Tool name.

        Returns:
            True if tool is registered and enabled.
        """
        tool = self._tools.get(name)
        return tool is not None and tool.enabled

    def enable(self, name: str) -> bool:
        """Enable a disabled tool.

        Args:
            name: Tool name.

        Returns:
            True if tool was found and enabled.
        """
        tool = self._tools.get(name)
        if tool:
            tool.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a tool without unregistering it.

        Args:
            name: Tool name.

        Returns:
            True if tool was found and disabled.
        """
        tool = self._tools.get(name)
        if tool:
            tool.enabled = False
            return True
        return False

    def list_all(self) -> List[ToolMetadata]:
        """List metadata for all enabled tools."""
        return [tool.metadata for tool in self._tools.values() if tool.enabled]

    def list_names(self) -> List[str]:
        """List names of all enabled tools."""
        return [name for name, tool in self._tools.items() if tool.enabled]

    def list_by_category(self, category: str) -> List[ToolMetadata]:
        """List tools in a specific category.

        Args:
            category: Category to filter by.

        Returns:
            List of tool metadata in the category.
        """
        return [
            tool.metadata
            for tool in self._tools.values()
            if tool.enabled and tool.metadata.category == category
        ]

    def list_by_risk(self, risk: str) -> List[ToolMetadata]:
        """List tools with a specific risk level.

        Args:
            risk: Risk level ("low", "medium", "high").

        Returns:
            List of tool metadata with that risk level.
        """
        normalized = normalize_risk(risk)
        return [
            tool.metadata
            for tool in self._tools.values()
            if tool.enabled and tool.metadata.risk == normalized
        ]

    def list_by_tag(self, tag: str) -> List[ToolMetadata]:
        """List tools with a specific tag.

        Args:
            tag: Tag to filter by.

        Returns:
            List of tool metadata with that tag.
        """
        return [
            tool.metadata
            for tool in self._tools.values()
            if tool.enabled and tag in tool.metadata.tags
        ]

    def get_categories(self) -> Set[str]:
        """Get all categories that have registered tools."""
        return {tool.metadata.category for tool in self._tools.values() if tool.enabled}

    def get_capabilities(self) -> Dict[str, List[str]]:
        """Get a summary of registry capabilities.

        Returns:
            Dict mapping categories to tool names.
        """
        caps: Dict[str, List[str]] = {}
        for tool in self._tools.values():
            if not tool.enabled:
                continue
            category = tool.metadata.category
            if category not in caps:
                caps[category] = []
            caps[category].append(tool.name)
        return caps

    def clear(self) -> int:
        """Clear all registered tools.

        Returns:
            Number of tools removed.
        """
        count = len(self._tools)
        self._tools.clear()
        return count

    def __len__(self) -> int:
        """Return number of enabled tools."""
        return sum(1 for t in self._tools.values() if t.enabled)

    def __contains__(self, name: str) -> bool:
        """Check if tool is registered and enabled."""
        return self.contains(name)

    def __iter__(self):
        """Iterate over enabled tools."""
        for tool in self._tools.values():
            if tool.enabled:
                yield tool


def build_default_registry() -> ToolRegistry:
    """Build a registry preloaded with the default tool suite."""
    registry = ToolRegistry()

    def handler_time(args: Dict[str, Any], _ctx: Any) -> Any:
        return time_tool.get_current_time(args.get("timezone", "America/Toronto"))

    def handler_read(args: Dict[str, Any], ctx: Any) -> Any:
        root = getattr(ctx, "root", None)
        return {"content": file_io.read_text_file(args["path"], root=root)}

    def handler_write(args: Dict[str, Any], ctx: Any) -> Any:
        root = getattr(ctx, "root", None)
        file_io.write_text_file(
            args["path"],
            args.get("content", ""),
            root=root,
            create_dirs=bool(args.get("create_dirs", True)),
        )
        return {"path": args["path"]}

    def handler_list(args: Dict[str, Any], ctx: Any) -> Any:
        root = getattr(ctx, "root", None)
        return {"entries": file_io.list_directory(args["path"], root=root)}

    def handler_status(_args: Dict[str, Any], ctx: Any) -> Any:
        root = getattr(ctx, "root", None)
        return {"output": repo_tool.git_status(root=root)}

    def handler_diff(args: Dict[str, Any], ctx: Any) -> Any:
        root = getattr(ctx, "root", None)
        return {"output": repo_tool.git_diff(args.get("path"), root=root)}

    def handler_validate_ast(args: Dict[str, Any], ctx: Any) -> Any:
        root = getattr(ctx, "root", None)
        result = validation.validate_ast(
            args["path"],
            language=args.get("language"),
            root=root,
        )
        return result.to_dict()

    def handler_typecheck(args: Dict[str, Any], ctx: Any) -> Any:
        root = getattr(ctx, "root", None)
        result = validation.validate_typecheck(
            args["path"],
            language=args.get("language"),
            root=root,
        )
        return result.to_dict()

    def handler_lint(args: Dict[str, Any], ctx: Any) -> Any:
        root = getattr(ctx, "root", None)
        result = validation.validate_lint(
            args["path"],
            language=args.get("language"),
            root=root,
        )
        return result.to_dict()

    registry.register_from_spec(
        name="getCurrentTime",
        handler=handler_time,
        spec=time_tool.TOOL_SPEC,
        category=ToolCategory.TIME.value,
    )
    registry.register_from_spec(
        name="readTextFile",
        handler=handler_read,
        spec=file_io.READ_TOOL_SPEC,
        category=ToolCategory.IO.value,
    )
    registry.register_from_spec(
        name="writeTextFile",
        handler=handler_write,
        spec=file_io.WRITE_TOOL_SPEC,
        category=ToolCategory.IO.value,
    )
    registry.register_from_spec(
        name="listDirectory",
        handler=handler_list,
        spec=file_io.LIST_TOOL_SPEC,
        category=ToolCategory.IO.value,
    )
    registry.register_from_spec(
        name="gitStatus",
        handler=handler_status,
        spec=repo_tool.STATUS_TOOL_SPEC,
        category=ToolCategory.REPO.value,
    )
    registry.register_from_spec(
        name="gitDiff",
        handler=handler_diff,
        spec=repo_tool.DIFF_TOOL_SPEC,
        category=ToolCategory.REPO.value,
    )
    registry.register_from_spec(
        name="validateAst",
        handler=handler_validate_ast,
        spec=validation.AST_TOOL_SPEC,
        category=ToolCategory.VALIDATION.value,
    )
    registry.register_from_spec(
        name="typecheck",
        handler=handler_typecheck,
        spec=validation.TYPECHECK_TOOL_SPEC,
        category=ToolCategory.VALIDATION.value,
    )
    registry.register_from_spec(
        name="lint",
        handler=handler_lint,
        spec=validation.LINT_TOOL_SPEC,
        category=ToolCategory.VALIDATION.value,
    )

    return registry


# Global default registry
_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Get or create the default global tool registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry


def reset_default_registry() -> None:
    """Reset the default global tool registry."""
    global _default_registry
    if _default_registry is not None:
        _default_registry.clear()
    _default_registry = None
