from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from runtime.plugins.base import Plugin


@dataclass(frozen=True)
class PolicyDecision:
    """Result of a control plane policy evaluation."""

    allow: bool
    reason: str = ""
    block_type: str = ""  # "gate", "rate_limit", "auth", "policy"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allowed(cls, reason: str = "") -> PolicyDecision:
        return cls(allow=True, reason=reason)

    @classmethod
    def blocked(
        cls,
        reason: str,
        block_type: str = "policy",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        return cls(
            allow=False,
            reason=reason,
            block_type=block_type,
            metadata=metadata or {},
        )


@dataclass
class PolicyContext:
    """Context passed to control plane plugins for policy decisions."""

    phase: str  # "before_run", "before_step", "before_tool", etc.
    manifest: Dict[str, Any]
    step: Optional[Dict[str, Any]] = None
    tool_name: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    run_dir: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


class ControlPlanePlugin(Plugin):
    """Base class for control plane plugins.

    Control plane plugins make policy decisions that can block execution.
    They are evaluated before data plane plugins and can prevent operations.

    Extends Plugin for backward compatibility with existing plugin system.
    """

    # Lower priority = runs first
    priority: int = 0

    def before_run_policy(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate policy before workflow run starts.

        Override to implement custom policy logic.

        Args:
            context: Policy evaluation context with manifest and config.

        Returns:
            PolicyDecision indicating whether to allow the run.
        """
        return PolicyDecision.allowed()

    def before_step_policy(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate policy before step execution.

        Override to implement custom policy logic.

        Args:
            context: Policy evaluation context with step and manifest.

        Returns:
            PolicyDecision indicating whether to allow the step.
        """
        return PolicyDecision.allowed()

    def before_tool_policy(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate policy before tool invocation.

        Override to implement custom policy logic.

        Args:
            context: Policy evaluation context with tool_name.

        Returns:
            PolicyDecision indicating whether to allow the tool call.
        """
        return PolicyDecision.allowed()

    def on_policy_violation(
        self,
        context: PolicyContext,
        decision: PolicyDecision,
    ) -> None:
        """Called when a policy violation is detected.

        Override to implement logging, alerting, or other side effects.

        Args:
            context: The context that triggered the violation.
            decision: The blocking decision.
        """
        pass


def combine_decisions(decisions: List[PolicyDecision]) -> PolicyDecision:
    """Combine multiple policy decisions into one.

    Returns blocked if any decision blocks.
    Aggregates reasons from all blocking decisions.
    """
    blocking = [d for d in decisions if not d.allow]
    if not blocking:
        return PolicyDecision.allowed()

    reasons = [d.reason for d in blocking if d.reason]
    combined_reason = "; ".join(reasons) if reasons else "Policy blocked"
    block_types = list({d.block_type for d in blocking if d.block_type})
    block_type = block_types[0] if len(block_types) == 1 else "multiple"

    return PolicyDecision.blocked(
        reason=combined_reason,
        block_type=block_type,
        metadata={"decisions": [d.reason for d in blocking]},
    )
