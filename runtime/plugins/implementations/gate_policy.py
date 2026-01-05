from __future__ import annotations

from typing import Any, Dict

from runtime import gates
from runtime.plugins.control_plane import (
    ControlPlanePlugin,
    PolicyContext,
    PolicyDecision,
)
from runtime.plugins.ordering import PluginPriority


class GatePolicyPlugin(ControlPlanePlugin):
    """Control plane plugin that enforces HITL gate policies.

    Wraps the existing runtime/gates.py logic in the plugin interface.
    Evaluates gate requirements before steps execute.
    """

    priority = PluginPriority.GATE_POLICY

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        self._config = config or {}

    def before_step_policy(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate gate policy before step execution.

        Checks if the step requires a human gate and whether
        the gate has been approved.
        """
        step = context.step
        if not step:
            return PolicyDecision.allowed()

        # Get step spec for human_gate field
        step_spec = context.config.get("step_spec")
        human_gate = ""
        if step_spec and hasattr(step_spec, "human_gate"):
            human_gate = step_spec.human_gate or ""
        else:
            human_gate = step.get("human_gate", "")

        if not human_gate:
            return PolicyDecision.allowed()

        # Determine phase and workflow from context
        phase = ""
        workflow = ""
        if step_spec:
            phase = getattr(step_spec, "phase", "") or ""
        manifest = context.manifest
        if manifest:
            spec = manifest.get("workflow_spec", {})
            workflow = f"{spec.get('module', '')}/{spec.get('workflow', '')}"
            if not phase:
                phase = spec.get("phase", "")

        # Use the config from context, falling back to instance config
        config = context.config if context.config else self._config

        # Check if gate is required
        decision = gates.gate_required(human_gate, config, phase, workflow)

        if not decision.required:
            return PolicyDecision.allowed(reason=decision.reason)

        # Gate is required - check for approval
        step_id = step.get("step_id") or step.get("name", "")
        gate_id = f"step:{step_id}"

        # Try to load approvals if run_dir is available
        approvals: Dict[str, Any] = {}
        if context.run_dir:
            try:
                from pathlib import Path

                from runtime import storage

                approvals = storage.read_approvals(Path(context.run_dir))
            except Exception:  # noqa: BLE001, S110
                pass

        if gates.has_approval(approvals, gate_id):
            return PolicyDecision.allowed(reason="gate approved")

        return PolicyDecision.blocked(
            reason=f"Human gate required: {decision.reason}",
            block_type="gate",
            metadata={
                "gate_id": gate_id,
                "human_gate": human_gate,
                "phase": phase,
                "workflow": workflow,
                "policy_reason": decision.reason,
            },
        )

    def on_policy_violation(
        self,
        context: PolicyContext,
        decision: PolicyDecision,
    ) -> None:
        """Log gate policy violations for audit trail."""
        # Could emit to event bus or log here
        pass
