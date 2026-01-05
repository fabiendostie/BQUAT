from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from runtime.plugins.base import Plugin


@dataclass
class DataContext:
    """Context passed to data plane plugins for observation/processing."""

    phase: str  # "before_run", "after_run", "before_step", "after_step", etc.
    manifest: Dict[str, Any]
    step: Optional[Dict[str, Any]] = None
    config: Dict[str, Any] = field(default_factory=dict)
    run_dir: Optional[str] = None
    event_type: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


class DataPlanePlugin(Plugin):
    """Base class for data plane plugins.

    Data plane plugins observe and process data but do not block execution.
    They run after control plane plugins have allowed the operation.

    Examples: logging, metrics, artifact tracking, observability.

    Extends Plugin for backward compatibility with existing plugin system.
    """

    # Higher priority = runs later (after control plane)
    priority: int = 100

    def on_run_started(self, context: DataContext) -> None:
        """Called when a workflow run starts.

        Override to implement custom observation/processing.

        Args:
            context: Data context with manifest.
        """
        pass

    def on_run_completed(self, context: DataContext) -> None:
        """Called when a workflow run completes successfully.

        Override to implement custom observation/processing.

        Args:
            context: Data context with manifest.
        """
        pass

    def on_run_failed(self, context: DataContext) -> None:
        """Called when a workflow run fails.

        Override to implement custom observation/processing.

        Args:
            context: Data context with manifest and error info in payload.
        """
        pass

    def on_step_started(self, context: DataContext) -> None:
        """Called when a step starts execution.

        Override to implement custom observation/processing.

        Args:
            context: Data context with step and manifest.
        """
        pass

    def on_step_completed(self, context: DataContext) -> None:
        """Called when a step completes successfully.

        Override to implement custom observation/processing.

        Args:
            context: Data context with step and manifest.
        """
        pass

    def on_step_failed(self, context: DataContext) -> None:
        """Called when a step fails.

        Override to implement custom observation/processing.

        Args:
            context: Data context with step, manifest, and error in payload.
        """
        pass

    def on_tool_executed(self, context: DataContext) -> None:
        """Called after a tool is executed.

        Override to implement custom observation/processing.

        Args:
            context: Data context with tool result in payload.
        """
        pass

    def on_artifact_created(self, context: DataContext) -> None:
        """Called when an artifact is created.

        Override to implement custom observation/processing.

        Args:
            context: Data context with artifact info in payload.
        """
        pass

    def on_evidence_recorded(self, context: DataContext) -> None:
        """Called when evidence is recorded.

        Override to implement custom observation/processing.

        Args:
            context: Data context with evidence info in payload.
        """
        pass

    def on_gate_triggered(self, context: DataContext) -> None:
        """Called when a human gate is triggered.

        Override to implement custom observation/processing.

        Args:
            context: Data context with gate info in payload.
        """
        pass

    def on_validation_result(self, context: DataContext) -> None:
        """Called when validation completes.

        Override to implement custom observation/processing.

        Args:
            context: Data context with validation result in payload.
        """
        pass
