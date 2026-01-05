from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from runtime import config as runtime_config
from runtime.tools.base import ToolSpec
from runtime.tools.file_io import resolve_path

_yaml: Any | None
try:
    import yaml as _yaml
except Exception:
    _yaml = None

ValidationStatus = Literal["passed", "failed", "skipped"]

AST_TOOL_SPEC = ToolSpec(
    name="validateAst",
    description="Validate source syntax by parsing to an AST when supported.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to validate."},
            "language": {
                "type": "string",
                "description": "Optional language override (python, json, yaml, javascript).",
            },
        },
        "required": ["path"],
    },
    risk="low",
).to_dict()

TYPECHECK_TOOL_SPEC = ToolSpec(
    name="typecheck",
    description="Run a language-specific type checker when available.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to typecheck."},
            "language": {
                "type": "string",
                "description": "Optional language override (python, typescript).",
            },
        },
        "required": ["path"],
    },
    risk="low",
).to_dict()

LINT_TOOL_SPEC = ToolSpec(
    name="lint",
    description="Run a language-specific linter when available.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to lint."},
            "language": {"type": "string", "description": "Optional language override."},
        },
        "required": ["path"],
    },
    risk="low",
).to_dict()

TOOL_SPECS = [AST_TOOL_SPEC, TYPECHECK_TOOL_SPEC, LINT_TOOL_SPEC]


@dataclass(frozen=True)
class ValidationResult:
    stage: str
    status: ValidationStatus
    tool: str
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationSummary:
    status: ValidationStatus
    results: List[ValidationResult]


def _project_root(root: Optional[Path] = None) -> Path:
    base = root or runtime_config.project_root_from_here()
    return base.resolve()


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _node_bin_path(root: Path, name: str) -> Optional[Path]:
    suffixes = [""]
    if os.name == "nt":
        suffixes = [".cmd", ".exe", ""]
    bin_dir = root / "node_modules" / ".bin"
    for suffix in suffixes:
        candidate = bin_dir / f"{name}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _tool_path(name: str, root: Path) -> Optional[str]:
    cmd = shutil.which(name)
    if cmd:
        return cmd
    local = _node_bin_path(root, name)
    if local:
        return str(local)
    return None


def _result(
    stage: str,
    status: ValidationStatus,
    tool: str,
    exit_code: Optional[int] = None,
    stdout: str = "",
    stderr: str = "",
    duration_ms: int = 0,
) -> ValidationResult:
    return ValidationResult(
        stage=stage,
        status=status,
        tool=tool,
        exit_code=exit_code,
        stdout=stdout.strip(),
        stderr=stderr.strip(),
        duration_ms=duration_ms,
    )


def _run_command(
    stage: str,
    tool: str,
    command: List[str],
    cwd: Path,
    timeout_seconds: int,
) -> ValidationResult:
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        status: ValidationStatus = "passed" if completed.returncode == 0 else "failed"
        return _result(
            stage,
            status,
            tool,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_ms=duration_ms,
        )
    except FileNotFoundError:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _result(stage, "skipped", tool, stderr="tool not found", duration_ms=duration_ms)
    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _result(stage, "failed", tool, stderr="timeout", duration_ms=duration_ms)


def detect_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".json"}:
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix in {".js", ".jsx"}:
        return "javascript"
    if suffix in {".ts", ".tsx"}:
        return "typescript"
    return "unknown"


def _normalize_language(language: Optional[str], path: Path) -> str:
    if language:
        value = language.strip().lower()
        aliases = {
            "py": "python",
            "python": "python",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "js": "javascript",
            "javascript": "javascript",
            "ts": "typescript",
            "typescript": "typescript",
        }
        return aliases.get(value, value)
    return detect_language(path)


def validate_ast(
    path: str,
    language: Optional[str] = None,
    root: Optional[Path] = None,
    timeout_seconds: int = 10,
) -> ValidationResult:
    base = _project_root(root)
    target = resolve_path(path, base)
    lang = _normalize_language(language, target)
    start = time.perf_counter()
    try:
        source = target.read_text(encoding="utf-8", errors="ignore")
        if lang == "python":
            ast.parse(source, filename=str(target))
            duration_ms = int((time.perf_counter() - start) * 1000)
            return _result("ast", "passed", "ast.parse", duration_ms=duration_ms)
        if lang == "json":
            json.loads(source)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return _result("ast", "passed", "json.loads", duration_ms=duration_ms)
        if lang == "yaml":
            if _yaml is None:
                duration_ms = int((time.perf_counter() - start) * 1000)
                return _result(
                    "ast",
                    "skipped",
                    "yaml.safe_load",
                    stderr="pyyaml missing",
                    duration_ms=duration_ms,
                )
            _yaml.safe_load(source)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return _result("ast", "passed", "yaml.safe_load", duration_ms=duration_ms)
        if lang == "javascript":
            node_cmd = _tool_path("node", base)
            if not node_cmd:
                duration_ms = int((time.perf_counter() - start) * 1000)
                return _result(
                    "ast",
                    "skipped",
                    "node --check",
                    stderr="node missing",
                    duration_ms=duration_ms,
                )
            return _run_command(
                "ast",
                "node --check",
                [node_cmd, "--check", str(target)],
                cwd=base,
                timeout_seconds=timeout_seconds,
            )
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _result(
            "ast",
            "skipped",
            "unsupported",
            stderr=f"unsupported language: {lang}",
            duration_ms=duration_ms,
        )
    except SyntaxError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _result("ast", "failed", "ast.parse", stderr=str(exc), duration_ms=duration_ms)
    except json.JSONDecodeError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _result("ast", "failed", "json.loads", stderr=str(exc), duration_ms=duration_ms)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - start) * 1000)
        return _result("ast", "failed", "ast", stderr=str(exc), duration_ms=duration_ms)


def validate_typecheck(
    path: str,
    language: Optional[str] = None,
    root: Optional[Path] = None,
    timeout_seconds: int = 30,
) -> ValidationResult:
    base = _project_root(root)
    target = resolve_path(path, base)
    lang = _normalize_language(language, target)
    if lang == "python":
        if not _module_available("mypy"):
            return _result("typecheck", "skipped", "mypy", stderr="mypy missing")
        command = [sys.executable, "-m", "mypy", str(target)]
        return _run_command(
            "typecheck",
            "mypy",
            command,
            cwd=base,
            timeout_seconds=timeout_seconds,
        )
    if lang == "typescript":
        tsc_cmd = _tool_path("tsc", base)
        if not tsc_cmd:
            return _result("typecheck", "skipped", "tsc", stderr="tsc missing")
        command = [tsc_cmd, "--noEmit", "--pretty", "false", str(target)]
        return _run_command(
            "typecheck",
            "tsc",
            command,
            cwd=base,
            timeout_seconds=timeout_seconds,
        )
    return _result(
        "typecheck",
        "skipped",
        "unsupported",
        stderr=f"unsupported language: {lang}",
    )


def validate_lint(
    path: str,
    language: Optional[str] = None,
    root: Optional[Path] = None,
    timeout_seconds: int = 30,
) -> ValidationResult:
    base = _project_root(root)
    target = resolve_path(path, base)
    lang = _normalize_language(language, target)
    if lang == "python":
        if not _module_available("ruff"):
            return _result("lint", "skipped", "ruff", stderr="ruff missing")
        command = [sys.executable, "-m", "ruff", "check", str(target)]
        result = _run_command(
            "lint",
            "ruff",
            command,
            cwd=base,
            timeout_seconds=timeout_seconds,
        )
        # Handle case where ruff module exists but binary is missing
        if result.status == "failed" and "FileNotFoundError" in (result.stderr or ""):
            return _result("lint", "skipped", "ruff", stderr="ruff binary not found")
        return result
    return _result("lint", "skipped", "unsupported", stderr=f"unsupported language: {lang}")


def summarize_results(results: List[ValidationResult]) -> ValidationSummary:
    if any(result.status == "failed" for result in results):
        return ValidationSummary(status="failed", results=results)
    if any(result.status == "passed" for result in results):
        return ValidationSummary(status="passed", results=results)
    return ValidationSummary(status="skipped", results=results)


def run_validation_pipeline(
    path: str,
    language: Optional[str] = None,
    root: Optional[Path] = None,
    stages: Optional[List[str]] = None,
    timeout_seconds: int = 30,
) -> ValidationSummary:
    stage_map = {
        "ast": validate_ast,
        "typecheck": validate_typecheck,
        "lint": validate_lint,
    }
    selected = stages or ["ast", "typecheck", "lint"]
    results: List[ValidationResult] = []
    for stage in selected:
        func = stage_map.get(stage)
        if not func:
            results.append(_result(stage, "skipped", "unsupported", stderr="unknown stage"))
            continue
        result = func(path, language=language, root=root, timeout_seconds=timeout_seconds)
        results.append(result)
    return summarize_results(results)
