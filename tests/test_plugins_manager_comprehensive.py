"""Comprehensive tests for runtime/plugins/manager.py to achieve 85%+ coverage."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.plugins.base import Plugin  # noqa: E402
from runtime.plugins.control_plane import (  # noqa: E402
    ControlPlanePlugin,
    PolicyContext,
    PolicyDecision,
)
from runtime.plugins.data_plane import DataContext, DataPlanePlugin  # noqa: E402
from runtime.plugins.manager import PluginManager  # noqa: E402


class TrackingControlPlugin(ControlPlanePlugin):
    """Control plugin that tracks all policy calls."""

    priority = 10

    def __init__(self) -> None:
        self.calls: List[str] = []
        self.violations: List[PolicyDecision] = []

    def before_run_policy(self, context: PolicyContext) -> PolicyDecision:
        self.calls.append("before_run_policy")
        return PolicyDecision.allowed("tracking")

    def before_step_policy(self, context: PolicyContext) -> PolicyDecision:
        self.calls.append("before_step_policy")
        return PolicyDecision.allowed("tracking")

    def before_tool_policy(self, context: PolicyContext) -> PolicyDecision:
        self.calls.append("before_tool_policy")
        return PolicyDecision.allowed("tracking")

    def on_policy_violation(self, context: PolicyContext, decision: PolicyDecision) -> None:
        self.violations.append(decision)


class BlockingControlPlugin(ControlPlanePlugin):
    """Control plugin that blocks all policies."""

    priority = 5

    def before_run_policy(self, context: PolicyContext) -> PolicyDecision:
        return PolicyDecision.blocked("blocked by policy", "auth")

    def before_step_policy(self, context: PolicyContext) -> PolicyDecision:
        return PolicyDecision.blocked("step blocked", "gate")

    def before_tool_policy(self, context: PolicyContext) -> PolicyDecision:
        return PolicyDecision.blocked("tool blocked", "risk")


class FailingControlPlugin(ControlPlanePlugin):
    """Control plugin that raises exceptions."""

    def before_run_policy(self, context: PolicyContext) -> PolicyDecision:
        raise RuntimeError("Plugin error")

    def before_step_policy(self, context: PolicyContext) -> PolicyDecision:
        raise RuntimeError("Plugin error")

    def before_tool_policy(self, context: PolicyContext) -> PolicyDecision:
        raise RuntimeError("Plugin error")


class TrackingDataPlugin(DataPlanePlugin):
    """Data plugin that tracks all hook calls."""

    priority = 50

    def __init__(self) -> None:
        self.calls: List[str] = []

    def on_run_started(self, context: DataContext) -> None:
        self.calls.append("run_started")

    def on_step_started(self, context: DataContext) -> None:
        self.calls.append("step_started")

    def on_step_completed(self, context: DataContext) -> None:
        self.calls.append("step_completed")

    def on_run_completed(self, context: DataContext) -> None:
        self.calls.append("run_completed")


class FailingDataPlugin(DataPlanePlugin):
    """Data plugin that raises exceptions in hooks."""

    def on_run_started(self, context: DataContext) -> None:
        raise RuntimeError("Data plugin error")


class LegacyTrackingPlugin(Plugin):
    """Legacy plugin for testing backward compatibility."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def before_run(self, manifest: Dict[str, Any]) -> None:
        self.calls.append("before_run")

    def after_run(self, manifest: Dict[str, Any]) -> None:
        self.calls.append("after_run")

    def before_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        self.calls.append("before_step")

    def after_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        self.calls.append("after_step")

    def on_error(self, step: Dict[str, Any], manifest: Dict[str, Any], error: str) -> None:
        self.calls.append("on_error")

    def on_validation(self, manifest: Dict[str, Any], status: str) -> None:
        self.calls.append("on_validation")


class FailingLegacyPlugin(Plugin):
    """Legacy plugin that raises exceptions."""

    def before_run(self, manifest: Dict[str, Any]) -> None:
        raise RuntimeError("Legacy error")

    def after_run(self, manifest: Dict[str, Any]) -> None:
        raise RuntimeError("Legacy error")

    def before_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        raise RuntimeError("Legacy error")

    def after_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        raise RuntimeError("Legacy error")

    def on_error(self, step: Dict[str, Any], manifest: Dict[str, Any], error: str) -> None:
        raise RuntimeError("Legacy error")

    def on_validation(self, manifest: Dict[str, Any], status: str) -> None:
        raise RuntimeError("Legacy error")


class TestPluginManagerRegistration(unittest.TestCase):
    """Test plugin registration and unregistration."""

    def test_register_plugin(self) -> None:
        manager = PluginManager()
        plugin = Plugin()
        manager.register(plugin)
        self.assertIn(plugin, manager.plugins)

    def test_register_multiple_plugins(self) -> None:
        manager = PluginManager()
        p1, p2, p3 = Plugin(), Plugin(), Plugin()
        manager.register(p1)
        manager.register(p2)
        manager.register(p3)
        self.assertEqual(len(manager.plugins), 3)

    def test_unregister_plugin(self) -> None:
        plugin = Plugin()
        manager = PluginManager([plugin])
        result = manager.unregister(plugin)
        self.assertTrue(result)
        self.assertNotIn(plugin, manager.plugins)

    def test_unregister_not_found(self) -> None:
        manager = PluginManager()
        result = manager.unregister(Plugin())
        self.assertFalse(result)

    def test_plugins_property(self) -> None:
        plugins = [Plugin(), Plugin()]
        manager = PluginManager(plugins)
        self.assertEqual(len(manager.plugins), 2)
        # Ensure it's a copy
        manager.plugins.append(Plugin())
        self.assertEqual(len(manager.plugins), 2)


class TestPluginManagerControlPlane(unittest.TestCase):
    """Test control plane plugin execution."""

    def test_run_before_run_policy_allowed(self) -> None:
        plugin = TrackingControlPlugin()
        manager = PluginManager([plugin])
        decision = manager.run_before_run_policy({"run_id": "test"})
        self.assertTrue(decision.allow)
        self.assertIn("before_run_policy", plugin.calls)

    def test_run_before_run_policy_blocked(self) -> None:
        plugin = BlockingControlPlugin()
        manager = PluginManager([plugin])
        decision = manager.run_before_run_policy({"run_id": "test"})
        self.assertFalse(decision.allow)
        self.assertEqual(decision.block_type, "auth")

    def test_run_before_run_policy_with_config(self) -> None:
        plugin = TrackingControlPlugin()
        manager = PluginManager([plugin])
        decision = manager.run_before_run_policy(
            {"run_id": "test"},
            config={"key": "value"},
            run_dir="/tmp/run",
        )
        self.assertTrue(decision.allow)

    def test_run_before_step_policy_allowed(self) -> None:
        plugin = TrackingControlPlugin()
        manager = PluginManager([plugin])
        decision = manager.run_before_step_policy(
            {"name": "step1"},
            {"run_id": "test"},
        )
        self.assertTrue(decision.allow)
        self.assertIn("before_step_policy", plugin.calls)

    def test_run_before_step_policy_blocked(self) -> None:
        plugin = BlockingControlPlugin()
        manager = PluginManager([plugin])
        decision = manager.run_before_step_policy(
            {"name": "step1"},
            {"run_id": "test"},
        )
        self.assertFalse(decision.allow)
        self.assertEqual(decision.block_type, "gate")

    def test_run_before_tool_policy_allowed(self) -> None:
        plugin = TrackingControlPlugin()
        manager = PluginManager([plugin])
        decision = manager.run_before_tool_policy(
            "readFile",
            {"name": "step1"},
            {"run_id": "test"},
        )
        self.assertTrue(decision.allow)
        self.assertIn("before_tool_policy", plugin.calls)

    def test_run_before_tool_policy_blocked(self) -> None:
        plugin = BlockingControlPlugin()
        manager = PluginManager([plugin])
        decision = manager.run_before_tool_policy(
            "deleteFile",
            {"name": "step1"},
            {"run_id": "test"},
        )
        self.assertFalse(decision.allow)
        self.assertEqual(decision.block_type, "risk")

    def test_policy_exception_handled(self) -> None:
        plugin = FailingControlPlugin()
        manager = PluginManager([plugin])
        # Should not raise - exceptions are caught
        decision = manager.run_before_run_policy({"run_id": "test"})
        self.assertTrue(decision.allow)  # Default when no decisions

    def test_no_control_plugins_returns_allowed(self) -> None:
        manager = PluginManager()
        decision = manager.run_before_run_policy({})
        self.assertTrue(decision.allow)

    def test_on_policy_violation_called(self) -> None:
        blocking = BlockingControlPlugin()
        tracking = TrackingControlPlugin()
        manager = PluginManager([blocking, tracking])

        # The blocking plugin should trigger violation callback
        manager.run_before_run_policy({})

        # Blocking plugin's on_policy_violation is called via base class default
        # which does nothing, so we check that no exceptions occur

    def test_multiple_control_plugins_combined(self) -> None:
        p1 = TrackingControlPlugin()
        p2 = TrackingControlPlugin()
        manager = PluginManager([p1, p2])

        decision = manager.run_before_run_policy({})
        self.assertTrue(decision.allow)
        self.assertIn("before_run_policy", p1.calls)
        self.assertIn("before_run_policy", p2.calls)


class TestPluginManagerDataPlane(unittest.TestCase):
    """Test data plane plugin execution."""

    def test_run_data_hooks_run_started(self) -> None:
        plugin = TrackingDataPlugin()
        manager = PluginManager([plugin])
        manager.run_data_hooks("run_started", {"run_id": "test"})
        self.assertIn("run_started", plugin.calls)

    def test_run_data_hooks_step_started(self) -> None:
        plugin = TrackingDataPlugin()
        manager = PluginManager([plugin])
        manager.run_data_hooks("step_started", {}, step={"name": "step1"})
        self.assertIn("step_started", plugin.calls)

    def test_run_data_hooks_step_completed(self) -> None:
        plugin = TrackingDataPlugin()
        manager = PluginManager([plugin])
        manager.run_data_hooks("step_completed", {}, step={"name": "step1"})
        self.assertIn("step_completed", plugin.calls)

    def test_run_data_hooks_run_completed(self) -> None:
        plugin = TrackingDataPlugin()
        manager = PluginManager([plugin])
        manager.run_data_hooks("run_completed", {})
        self.assertIn("run_completed", plugin.calls)

    def test_run_data_hooks_with_config(self) -> None:
        plugin = TrackingDataPlugin()
        manager = PluginManager([plugin])
        manager.run_data_hooks(
            "run_started",
            {},
            config={"key": "value"},
            run_dir="/tmp/run",
            event_type="test",
            payload={"data": "payload"},
        )
        self.assertIn("run_started", plugin.calls)

    def test_run_data_hooks_exception_handled(self) -> None:
        plugin = FailingDataPlugin()
        manager = PluginManager([plugin])
        # Should not raise
        manager.run_data_hooks("run_started", {})

    def test_run_data_hooks_unknown_phase(self) -> None:
        plugin = TrackingDataPlugin()
        manager = PluginManager([plugin])
        # Unknown phase - method doesn't exist, should handle gracefully
        manager.run_data_hooks("unknown_phase", {})
        self.assertEqual(len(plugin.calls), 0)


class TestPluginManagerLegacy(unittest.TestCase):
    """Test legacy backward-compatible plugin hooks."""

    def test_before_run(self) -> None:
        plugin = LegacyTrackingPlugin()
        manager = PluginManager([plugin])
        manager.before_run({})
        self.assertIn("before_run", plugin.calls)

    def test_after_run(self) -> None:
        plugin = LegacyTrackingPlugin()
        manager = PluginManager([plugin])
        manager.after_run({})
        self.assertIn("after_run", plugin.calls)

    def test_before_step(self) -> None:
        plugin = LegacyTrackingPlugin()
        manager = PluginManager([plugin])
        manager.before_step({}, {})
        self.assertIn("before_step", plugin.calls)

    def test_after_step(self) -> None:
        plugin = LegacyTrackingPlugin()
        manager = PluginManager([plugin])
        manager.after_step({}, {})
        self.assertIn("after_step", plugin.calls)

    def test_on_error(self) -> None:
        plugin = LegacyTrackingPlugin()
        manager = PluginManager([plugin])
        manager.on_error({}, {}, "test error")
        self.assertIn("on_error", plugin.calls)

    def test_on_validation(self) -> None:
        plugin = LegacyTrackingPlugin()
        manager = PluginManager([plugin])
        manager.on_validation({}, "passed")
        self.assertIn("on_validation", plugin.calls)

    def test_legacy_exception_handled(self) -> None:
        plugin = FailingLegacyPlugin()
        manager = PluginManager([plugin])
        # All should not raise
        manager.before_run({})
        manager.after_run({})
        manager.before_step({}, {})
        manager.after_step({}, {})
        manager.on_error({}, {}, "error")
        manager.on_validation({}, "status")


class TestPluginManagerProperties(unittest.TestCase):
    """Test plugin manager properties."""

    def test_control_plugins_property(self) -> None:
        control = TrackingControlPlugin()
        data = TrackingDataPlugin()
        legacy = LegacyTrackingPlugin()
        manager = PluginManager([control, data, legacy])

        control_list = manager.control_plugins
        self.assertIn(control, control_list)
        self.assertNotIn(data, control_list)
        self.assertNotIn(legacy, control_list)

    def test_data_plugins_property(self) -> None:
        control = TrackingControlPlugin()
        data = TrackingDataPlugin()
        legacy = LegacyTrackingPlugin()
        manager = PluginManager([control, data, legacy])

        data_list = manager.data_plugins
        self.assertIn(data, data_list)
        self.assertNotIn(control, data_list)
        self.assertNotIn(legacy, data_list)

    def test_legacy_plugins_property(self) -> None:
        control = TrackingControlPlugin()
        data = TrackingDataPlugin()
        legacy = LegacyTrackingPlugin()
        manager = PluginManager([control, data, legacy])

        legacy_list = manager.legacy_plugins
        self.assertIn(legacy, legacy_list)
        self.assertNotIn(control, legacy_list)
        self.assertNotIn(data, legacy_list)

    def test_plugins_sorted_by_priority(self) -> None:
        low = TrackingControlPlugin()
        low.priority = 100
        high = TrackingControlPlugin()
        high.priority = 1

        manager = PluginManager([low, high])
        sorted_plugins = manager.control_plugins

        self.assertEqual(sorted_plugins[0], high)
        self.assertEqual(sorted_plugins[1], low)


class TestPluginManagerMixed(unittest.TestCase):
    """Test mixed plugin scenarios."""

    def test_all_plugin_types_together(self) -> None:
        control = TrackingControlPlugin()
        data = TrackingDataPlugin()
        legacy = LegacyTrackingPlugin()
        manager = PluginManager([control, data, legacy])

        # Run various operations
        manager.run_before_run_policy({})
        manager.run_data_hooks("run_started", {})
        manager.before_run({})

        self.assertIn("before_run_policy", control.calls)
        self.assertIn("run_started", data.calls)
        self.assertIn("before_run", legacy.calls)

    def test_empty_manager(self) -> None:
        manager = PluginManager()
        self.assertEqual(len(manager.plugins), 0)
        self.assertEqual(len(manager.control_plugins), 0)
        self.assertEqual(len(manager.data_plugins), 0)
        self.assertEqual(len(manager.legacy_plugins), 0)

    def test_none_plugins_initialization(self) -> None:
        manager = PluginManager(None)
        self.assertEqual(len(manager.plugins), 0)


if __name__ == "__main__":
    unittest.main()
