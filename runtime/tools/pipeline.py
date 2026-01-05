from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from runtime import config as runtime_config
from runtime import gates, storage
from runtime.failure.isolation import FailureIsolator, ToolFailureContext
from runtime.models import StepSpec
from runtime.plugins.manager import PluginManager
from runtime.time_provider import get_current_time
from runtime.tools.base import ToolCall, normalize_risk
from runtime.tools.registry import (
    ToolMetadata,
    ToolRegistry,
    build_default_registry,
)

ToolHandler = Callable[[Dict[str, Any], "ToolExecutionContext"], Any]


@dataclass(frozen=True)
class ToolExecutionContext:
    run_dir: Path
    manifest: Dict[str, Any]
    step: Dict[str, Any]
    step_spec: Optional[StepSpec]
    config: Dict[str, Any]
    root: Path


@dataclass(frozen=True)
class ToolDefinition:
    spec: Dict[str, Any]
    handler: ToolHandler


@dataclass(frozen=True)
class ToolResult:
    name: str
    status: str
    risk: str
    started_at: str
    ended_at: str
    duration_ms: int
    result: Any = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    artifacts: List[str] = field(default_factory=list)
    step_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ToolExecutionError(RuntimeError):
    def __init__(self, message: str, tool_name: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name


class ToolApprovalRequired(RuntimeError):
    def __init__(self, message: str, tool_name: str, gate_id: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.gate_id = gate_id


def _project_root(root: Optional[Path] = None) -> Path:
    base = root or runtime_config.project_root_from_here()
    return base.resolve()


def _now() -> str:
    return get_current_time()


def _policy_config(config: Dict[str, Any]) -> Dict[str, Any]:
    return config.get("tools", {})


def _allowlist(config: Dict[str, Any], registry: ToolRegistry) -> Iterable[str]:
    tools_cfg = _policy_config(config)
    allowlist = tools_cfg.get("allowlist")
    if allowlist is None:
        return registry.list_names()
    if isinstance(allowlist, list) and not allowlist:
        return registry.list_names()
    if isinstance(allowlist, list):
        return allowlist
    return registry.list_names()


def _blocklist(config: Dict[str, Any]) -> Iterable[str]:
    tools_cfg = _policy_config(config)
    blocklist = tools_cfg.get("blocklist", [])
    if isinstance(blocklist, list):
        return blocklist
    return []


def _timeout_seconds(config: Dict[str, Any]) -> int:
    tools_cfg = _policy_config(config)
    return int(tools_cfg.get("timeout_seconds", 30))


def _tool_retry_backoff_seconds(config: Dict[str, Any]) -> float:
    cfg = config.get("failure_isolation", {})
    try:
        return float(cfg.get("tool_retry_backoff_seconds", 0))
    except (TypeError, ValueError):
        return 0.0


def _is_recoverable_error(error: str) -> bool:
    if not error:
        return True
    lowered = error.lower()
    non_recoverable = (
        "missing required args",
        "unknown tool",
        "blocklisted tool",
        "allowlist",
        "approval required",
    )
    return not any(token in lowered for token in non_recoverable)


def _risk_policy(config: Dict[str, Any]) -> Dict[str, Any]:
    tools_cfg = _policy_config(config)
    return tools_cfg.get("risk_policy", {})


def _requires_approval(risk: str, policy: Dict[str, Any]) -> bool:
    if risk == "high":
        return bool(policy.get("high_requires_approval", True))
    if risk == "medium":
        return bool(policy.get("medium_requires_approval", False))
    return False


def _tool_risk(call_data: Dict[str, Any], spec: Dict[str, Any]) -> str:
    if "risk" in call_data:
        return normalize_risk(call_data.get("risk")).strip()
    return normalize_risk(spec.get("risk")).strip()


def _validate_args(spec: Dict[str, Any], args: Dict[str, Any]) -> Optional[str]:
    params = spec.get("parameters", {})
    required = params.get("required", [])
    if not required:
        return None
    missing = [name for name in required if name not in args]
    if missing:
        return f"missing required args: {', '.join(missing)}"
    return None


def _gate_id(tool_name: str, step: Dict[str, Any], step_spec: Optional[StepSpec]) -> str:
    step_id = step.get("step_id") or (step_spec.id if step_spec else "") or step.get("name", "")
    return f"tool:{tool_name}:{step_id}"


def build_default_registry_for_pipeline() -> ToolRegistry:
    """Build a ToolRegistry compatible with the tool pipeline."""
    return build_default_registry()


def _normalize_registry(registry: ToolRegistry | Dict[str, ToolDefinition]) -> ToolRegistry:
    if isinstance(registry, ToolRegistry):
        return registry
    normalized = ToolRegistry()
    for name, definition in registry.items():
        metadata = ToolMetadata.from_spec(name=name, spec=definition.spec)
        normalized.register(name, definition.handler, metadata)
    return normalized


def _execute_with_timeout(
    handler: ToolHandler,
    args: Dict[str, Any],
    context: ToolExecutionContext,
    timeout_seconds: int,
) -> Any:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(handler, args, context)
        return future.result(timeout=timeout_seconds)


def _record_results(run_dir: Path, results: List[ToolResult]) -> None:
    payload = storage.read_tool_results(run_dir)
    existing = payload.get("results", [])
    existing.extend([result.to_dict() for result in results])
    payload["results"] = existing
    payload["updated_at"] = _now()
    storage.write_tool_results(run_dir, payload)


def run_tool_calls(
    step: Dict[str, Any],
    step_spec: Optional[StepSpec],
    manifest: Dict[str, Any],
    run_dir: Path,
    config: Dict[str, Any],
    registry: Optional[ToolRegistry | Dict[str, ToolDefinition]] = None,
    allowed_tools: Optional[List[str]] = None,
    plugins: Optional[PluginManager] = None,
) -> List[ToolResult]:
    if step_spec and step_spec.tools:
        calls = list(step_spec.tools)
    else:
        calls = list(step.get("tools", []))
    if not calls:
        return []

    tool_registry = _normalize_registry(registry or build_default_registry_for_pipeline())
    allowlist = set(_allowlist(config, tool_registry))
    if allowed_tools:
        allowlist &= set(allowed_tools)
    blocklist = set(_blocklist(config))
    policy = _risk_policy(config)
    timeout_seconds = _timeout_seconds(config)
    isolator = FailureIsolator(config)
    retry_backoff = _tool_retry_backoff_seconds(config)
    approvals = storage.read_approvals(run_dir)
    root = _project_root()
    context = ToolExecutionContext(
        run_dir=run_dir,
        manifest=manifest,
        step=step,
        step_spec=step_spec,
        config=config,
        root=root,
    )

    results: List[ToolResult] = []
    for raw in calls:
        call = ToolCall.from_dict(raw)
        definition = tool_registry.get(call.name)
        risk = "low"
        if definition:
            risk = _tool_risk(raw, definition.spec)
        gate = call.gate or _gate_id(call.name, step, step_spec)
        step_id = step.get("step_id") or (step_spec.id if step_spec else "") or ""
        attempt = 0
        status = "completed"
        error = ""
        output = None
        started = _now()
        ended = started
        duration_ms = 0

        while True:
            attempt += 1
            started = _now()
            start_perf = time.perf_counter()
            status = "completed"
            error = ""
            output = None

            if not definition:
                status = "skipped"
                error = "unknown tool"
            elif call.name in blocklist:
                status = "blocked"
                error = "blocklisted tool"
            elif call.name not in allowlist:
                status = "blocked"
                error = "tool not in allowlist"
            else:
                if plugins:
                    decision = plugins.run_before_tool_policy(
                        call.name,
                        step,
                        manifest,
                        config=config,
                        run_dir=str(run_dir),
                    )
                    if not decision.allow:
                        status = "blocked"
                        error = decision.reason or "policy blocked"
                if status == "completed":
                    arg_error = _validate_args(definition.spec, call.args)
                    if arg_error:
                        status = "failed"
                        error = arg_error
                    elif _requires_approval(risk, policy) and not gates.has_approval(
                        approvals, gate
                    ):
                        status = "blocked"
                        error = "approval required"
                    else:
                        try:
                            output = _execute_with_timeout(
                                definition.handler,
                                call.args,
                                context,
                                timeout_seconds,
                            )
                        except FutureTimeout:
                            status = "failed"
                            error = "timeout"
                        except Exception as exc:  # noqa: BLE001
                            status = "failed"
                            error = str(exc)

            ended = _now()
            duration_ms = int((time.perf_counter() - start_perf) * 1000)

            if status == "failed":
                failure_ctx = ToolFailureContext(
                    tool_name=call.name,
                    step_id=step_id,
                    attempt=attempt,
                    error=error,
                    recoverable=_is_recoverable_error(error),
                    required=call.required,
                )
                decision = isolator.isolate_tool_failure(failure_ctx)
                if decision.action == "retry":
                    if retry_backoff > 0:
                        time.sleep(retry_backoff)
                    continue
            break
        result = ToolResult(
            name=call.name,
            status=status,
            risk=risk,
            started_at=started,
            ended_at=ended,
            duration_ms=duration_ms,
            result=output,
            error=error,
            step_id=step_id,
        )
        results.append(result)

        if plugins:
            plugins.run_data_hooks(
                "tool_executed",
                manifest=manifest,
                step=step,
                config=config,
                run_dir=str(run_dir),
                payload={
                    "tool_name": call.name,
                    "status": status,
                    "risk": risk,
                    "duration_ms": duration_ms,
                    "error": error,
                },
            )

        if status == "blocked" and error == "approval required":
            _record_results(run_dir, results)
            step["tools"] = [res.to_dict() for res in results]
            raise ToolApprovalRequired(error, call.name, gate)
        if status != "completed" and call.required:
            _record_results(run_dir, results)
            step["tools"] = [res.to_dict() for res in results]
            raise ToolExecutionError(error or "tool failed", call.name)

    _record_results(run_dir, results)
    step["tools"] = [res.to_dict() for res in results]
    return results
