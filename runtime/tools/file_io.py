from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from runtime import config as runtime_config
from runtime.tools.base import ToolSpec

READ_TOOL_SPEC = ToolSpec(
    name="readTextFile",
    description="Read a UTF-8 text file within the project root.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to project root or absolute within it.",
            }
        },
        "required": ["path"],
    },
    risk="low",
).to_dict()

WRITE_TOOL_SPEC = ToolSpec(
    name="writeTextFile",
    description="Write a UTF-8 text file within the project root.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to project root or absolute within it.",
            },
            "content": {"type": "string", "description": "Full file contents."},
            "create_dirs": {
                "type": "boolean",
                "description": "Create missing parent directories.",
            },
        },
        "required": ["path", "content"],
    },
    risk="medium",
).to_dict()

LIST_TOOL_SPEC = ToolSpec(
    name="listDirectory",
    description="List directory entries within the project root.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to project root or absolute within it.",
            }
        },
        "required": ["path"],
    },
    risk="low",
).to_dict()

TOOL_SPECS = [READ_TOOL_SPEC, WRITE_TOOL_SPEC, LIST_TOOL_SPEC]


def _project_root(root: Optional[Path] = None) -> Path:
    base = root or runtime_config.project_root_from_here()
    return base.resolve()


def resolve_path(path: str, root: Optional[Path] = None) -> Path:
    base = _project_root(root)
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Path outside project root: {path}") from exc
    return resolved


def read_text_file(path: str, root: Optional[Path] = None) -> str:
    target = resolve_path(path, root)
    return target.read_text(encoding="utf-8", errors="ignore")


def write_text_file(
    path: str,
    content: str,
    root: Optional[Path] = None,
    create_dirs: bool = True,
) -> None:
    target = resolve_path(path, root)
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def list_directory(path: str, root: Optional[Path] = None) -> List[str]:
    target = resolve_path(path, root)
    return sorted([entry.name for entry in target.iterdir()])
