from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

from runtime import config as runtime_config
from runtime.tools.base import ToolSpec
from runtime.tools.file_io import resolve_path

STATUS_TOOL_SPEC = ToolSpec(
    name="gitStatus",
    description="Return a short git status summary for the project repository.",
    parameters={"type": "object", "properties": {}, "required": []},
    risk="low",
).to_dict()

DIFF_TOOL_SPEC = ToolSpec(
    name="gitDiff",
    description="Return git diff output for the project repository or a specific path.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional file path within the repository.",
            }
        },
        "required": [],
    },
    risk="low",
).to_dict()

TOOL_SPECS = [STATUS_TOOL_SPEC, DIFF_TOOL_SPEC]


def _repo_root(root: Optional[Path] = None) -> Path:
    base = root or runtime_config.project_root_from_here()
    base = base.resolve()
    if not (base / ".git").exists():
        raise ValueError("Git repository not found at project root")
    return base


def _run_git(repo_root: Path, args: List[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return result.stdout.strip()


def git_status(root: Optional[Path] = None) -> str:
    repo_root = _repo_root(root)
    return _run_git(repo_root, ["status", "-s"])


def git_diff(path: Optional[str] = None, root: Optional[Path] = None) -> str:
    repo_root = _repo_root(root)
    args = ["diff"]
    if path:
        resolved = resolve_path(path, repo_root)
        rel_path = resolved.relative_to(repo_root)
        args.extend(["--", str(rel_path)])
    return _run_git(repo_root, args)
