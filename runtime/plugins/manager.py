from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from runtime.plugins.base import Plugin
from runtime.plugins.control_plane import (
    ControlPlanePlugin,
    PolicyContext,
    PolicyDecision,
    combine_decisions,
)
from runtime.plugins.data_plane import DataContext, DataPlanePlugin
from runtime.plugins.ordering import sort_by_priority


class PluginManager:
    """Enhanced plugin manager supporting control plane and data plane plugins.

    Maintains backward compatibility with legacy Plugin instances.

    Control plane plugins (ControlPlanePlugin):
        - Make policy decisions that can block execution
        - Evaluated first, before any data processing
        - Return PolicyDecision from policy methods

    Data plane plugins (DataPlanePlugin):
        - Observe and process data without blocking
        - Run after control plane allows the operation
        - Used for logging, metrics, observability

    Legacy plugins (Plugin):
        - Treated as data plane (non-blocking)
        - Existing hooks continue to work
    """

    def __init__(self, plugins: Iterable[Plugin] | None = None) -> None:
        self._plugins: List[Plugin] = list(plugins or [])

    def register(self, plugin: Plugin) -> None:
        """Register a plugin."""
        self._plugins.append(plugin)

    def unregister(self, plugin: Plugin) -> bool:
        """Unregister a plugin.

        Returns:
            True if plugin was found and removed, False otherwise.
        """
        try:
            self._plugins.remove(plugin)
            return True
        except ValueError:
            return False

    @property
    def plugins(self) -> List[Plugin]:
        """Return all registered plugins."""
        return list(self._plugins)

    @property
    def control_plugins(self) -> List[ControlPlanePlugin]:
        """Return control plane plugins sorted by priority."""
        return sort_by_priority([p for p in self._plugins if isinstance(p, ControlPlanePlugin)])

    @property
    def data_plugins(self) -> List[DataPlanePlugin]:
        """Return data plane plugins sorted by priority."""
        return sort_by_priority([p for p in self._plugins if isinstance(p, DataPlanePlugin)])

    @property
    def legacy_plugins(self) -> List[Plugin]:
        """Return legacy plugins (not control or data plane)."""
        return [
            p for p in self._plugins if not isinstance(p, (ControlPlanePlugin, DataPlanePlugin))
        ]

    # -------------------------------------------------------------------------
    # Control Plane Methods
    # -------------------------------------------------------------------------

    def run_before_run_policy(
        self,
        manifest: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        run_dir: Optional[str] = None,
    ) -> PolicyDecision:
        """Run control plane policies before workflow run.

        Returns:
            Combined PolicyDecision from all control plane plugins.
        """
        context = PolicyContext(
            phase="before_run",
            manifest=manifest,
            config=config or {},
            run_dir=run_dir,
        )
        decisions: List[PolicyDecision] = []
        for plugin in self.control_plugins:
            try:
                decision = plugin.before_run_policy(context)
                decisions.append(decision)
                if not decision.allow:
                    plugin.on_policy_violation(context, decision)
            except Exception:  # noqa: BLE001, S110
                pass
        return combine_decisions(decisions) if decisions else PolicyDecision.allowed()

    def run_before_step_policy(
        self,
        step: Dict[str, Any],
        manifest: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        run_dir: Optional[str] = None,
    ) -> PolicyDecision:
        """Run control plane policies before step execution.

        Returns:
            Combined PolicyDecision from all control plane plugins.
        """
        context = PolicyContext(
            phase="before_step",
            manifest=manifest,
            step=step,
            config=config or {},
            run_dir=run_dir,
        )
        decisions: List[PolicyDecision] = []
        for plugin in self.control_plugins:
            try:
                decision = plugin.before_step_policy(context)
                decisions.append(decision)
                if not decision.allow:
                    plugin.on_policy_violation(context, decision)
            except Exception:  # noqa: BLE001, S110
                pass
        return combine_decisions(decisions) if decisions else PolicyDecision.allowed()

    def run_before_tool_policy(
        self,
        tool_name: str,
        step: Dict[str, Any],
        manifest: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        run_dir: Optional[str] = None,
    ) -> PolicyDecision:
        """Run control plane policies before tool invocation.

        Returns:
            Combined PolicyDecision from all control plane plugins.
        """
        context = PolicyContext(
            phase="before_tool",
            manifest=manifest,
            step=step,
            tool_name=tool_name,
            config=config or {},
            run_dir=run_dir,
        )
        decisions: List[PolicyDecision] = []
        for plugin in self.control_plugins:
            try:
                decision = plugin.before_tool_policy(context)
                decisions.append(decision)
                if not decision.allow:
                    plugin.on_policy_violation(context, decision)
            except Exception:  # noqa: BLE001, S110
                pass
        return combine_decisions(decisions) if decisions else PolicyDecision.allowed()

    # -------------------------------------------------------------------------
    # Data Plane Methods
    # -------------------------------------------------------------------------

    def run_data_hooks(
        self,
        phase: str,
        manifest: Dict[str, Any],
        step: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        run_dir: Optional[str] = None,
        event_type: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Run data plane hooks for a given phase.

        Calls the appropriate method on each data plane plugin.
        Exceptions are caught and do not propagate.
        """
        context = DataContext(
            phase=phase,
            manifest=manifest,
            step=step,
            config=config or {},
            run_dir=run_dir,
            event_type=event_type,
            payload=payload or {},
        )

        for plugin in self.data_plugins:
            try:
                method = getattr(plugin, f"on_{phase}", None)
                if method:
                    method(context)
            except Exception:  # noqa: BLE001, S110
                pass

    # -------------------------------------------------------------------------
    # Legacy Backward-Compatible Methods
    # -------------------------------------------------------------------------

    def before_run(self, manifest: Dict[str, Any]) -> None:
        """Legacy hook: called before workflow run starts.

        Calls all plugins (control, data, legacy) for backward compatibility.
        """
        for plugin in sort_by_priority(self._plugins):
            try:
                plugin.before_run(manifest)
            except Exception:  # noqa: BLE001, S110
                pass

    def after_run(self, manifest: Dict[str, Any]) -> None:
        """Legacy hook: called after workflow run completes.

        Calls all plugins (control, data, legacy) for backward compatibility.
        """
        for plugin in sort_by_priority(self._plugins):
            try:
                plugin.after_run(manifest)
            except Exception:  # noqa: BLE001, S110
                pass

    def before_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        """Legacy hook: called before step execution.

        Calls all plugins (control, data, legacy) for backward compatibility.
        """
        for plugin in sort_by_priority(self._plugins):
            try:
                plugin.before_step(step, manifest)
            except Exception:  # noqa: BLE001, S110
                pass

    def after_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        """Legacy hook: called after step execution.

        Calls all plugins (control, data, legacy) for backward compatibility.
        """
        for plugin in sort_by_priority(self._plugins):
            try:
                plugin.after_step(step, manifest)
            except Exception:  # noqa: BLE001, S110
                pass

    def on_error(self, step: Dict[str, Any], manifest: Dict[str, Any], error: str) -> None:
        """Legacy hook: called on step error.

        Calls all plugins (control, data, legacy) for backward compatibility.
        """
        for plugin in sort_by_priority(self._plugins):
            try:
                plugin.on_error(step, manifest, error)
            except Exception:  # noqa: BLE001, S110
                pass

    def on_validation(self, manifest: Dict[str, Any], status: str) -> None:
        """Legacy hook: called on validation result.

        Calls all plugins (control, data, legacy) for backward compatibility.
        """
        for plugin in sort_by_priority(self._plugins):
            try:
                plugin.on_validation(manifest, status)
            except Exception:  # noqa: BLE001, S110
                pass
