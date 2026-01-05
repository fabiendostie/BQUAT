from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class ToolFailureContext:
    tool_name: str
    step_id: str
    attempt: int
    error: str
    recoverable: bool
    required: bool
    isolation_level: str = "tool"


@dataclass(frozen=True)
class IsolationResult:
    action: str
    reason: str
    attempts_remaining: int = 0


@dataclass(frozen=True)
class ImpactReport:
    tool_name: str
    step_id: str
    impact_level: str
    recommendation: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "step_id": self.step_id,
            "impact_level": self.impact_level,
            "recommendation": self.recommendation,
            "details": dict(self.details),
        }


class FailureIsolator:
    """Evaluate tool failures and provide isolation recommendations."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def _failure_config(self) -> Dict[str, Any]:
        return self.config.get("failure_isolation", {})

    def _max_tool_retries(self) -> int:
        cfg = self._failure_config()
        return max(0, int(cfg.get("tool_retries", 0)))

    def _isolate_optional(self) -> bool:
        cfg = self._failure_config()
        return bool(cfg.get("isolate_optional_tools", True))

    def _isolate_step_failures(self) -> bool:
        cfg = self._failure_config()
        return bool(cfg.get("isolate_step_failures", False))

    def isolate_tool_failure(self, context: ToolFailureContext) -> IsolationResult:
        max_retries = self._max_tool_retries()
        remaining = max(0, max_retries - context.attempt + 1)
        if context.recoverable and remaining > 0:
            return IsolationResult(
                action="retry",
                reason="recoverable tool failure",
                attempts_remaining=remaining,
            )
        if not context.required and self._isolate_optional():
            return IsolationResult(action="skip", reason="optional tool failure")
        return IsolationResult(action="fail_step", reason="required tool failure")

    def analyze_impact(
        self, failed_tool: str, step_id: str, manifest: Dict[str, Any]
    ) -> ImpactReport:
        required = _tool_required(failed_tool, step_id, manifest)
        if required and not self._isolate_step_failures():
            impact_level = "workflow"
            recommendation = "escalate workflow"
        elif required:
            impact_level = "step"
            recommendation = "isolate step and continue"
        else:
            impact_level = "tool"
            recommendation = "skip tool and continue"
        return ImpactReport(
            tool_name=failed_tool,
            step_id=step_id,
            impact_level=impact_level,
            recommendation=recommendation,
            details={"required": required, "isolate_step_failures": self._isolate_step_failures()},
        )


def _tool_required(tool_name: str, step_id: str, manifest: Dict[str, Any]) -> bool:
    if not tool_name:
        return False
    step_specs = manifest.get("step_specs", [])
    for spec in step_specs:
        if spec.get("id") != step_id:
            continue
        for tool in spec.get("tools", []):
            if tool.get("name") == tool_name:
                return bool(tool.get("required", False))
    return False
