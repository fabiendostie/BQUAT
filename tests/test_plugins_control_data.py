"""Tests for the plugin pipeline with control/data plane split (REQ-SPEC-005, REQ-SPEC-006)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.plugins.base import Plugin  # noqa: E402
from runtime.plugins.control_plane import (  # noqa: E402
    ControlPlanePlugin,
    PolicyContext,
    PolicyDecision,
    combine_decisions,
)
from runtime.plugins.data_plane import DataContext, DataPlanePlugin  # noqa: E402
from runtime.plugins.implementations.audit import AuditPlugin  # noqa: E402
from runtime.plugins.implementations.gate_policy import GatePolicyPlugin  # noqa: E402
from runtime.plugins.manager import PluginManager  # noqa: E402
from runtime.plugins.ordering import (  # noqa: E402
    get_priority,
    partition_plugins,
    sort_by_priority,
)


class TestPolicyDecision:
    def test_allowed_decision(self) -> None:
        decision = PolicyDecision.allowed("test reason")
        assert decision.allow is True
        assert decision.reason == "test reason"

    def test_blocked_decision(self) -> None:
        decision = PolicyDecision.blocked(
            reason="access denied",
            block_type="auth",
            metadata={"user": "test"},
        )
        assert decision.allow is False
        assert decision.reason == "access denied"
        assert decision.block_type == "auth"
        assert decision.metadata["user"] == "test"

    def test_combine_all_allowed(self) -> None:
        decisions = [
            PolicyDecision.allowed("check1"),
            PolicyDecision.allowed("check2"),
        ]
        combined = combine_decisions(decisions)
        assert combined.allow is True

    def test_combine_with_blocked(self) -> None:
        decisions = [
            PolicyDecision.allowed("ok"),
            PolicyDecision.blocked("denied", "auth"),
            PolicyDecision.allowed("also ok"),
        ]
        combined = combine_decisions(decisions)
        assert combined.allow is False
        assert "denied" in combined.reason

    def test_combine_multiple_blocked(self) -> None:
        decisions = [
            PolicyDecision.blocked("reason1", "auth"),
            PolicyDecision.blocked("reason2", "rate_limit"),
        ]
        combined = combine_decisions(decisions)
        assert combined.allow is False
        assert "reason1" in combined.reason
        assert "reason2" in combined.reason
        assert combined.block_type == "multiple"

    def test_combine_empty_list(self) -> None:
        combined = combine_decisions([])
        assert combined.allow is True


class TestControlPlanePlugin:
    def test_default_allows_all(self) -> None:
        plugin = ControlPlanePlugin()
        context = PolicyContext(
            phase="before_run",
            manifest={"run_id": "test"},
        )

        assert plugin.before_run_policy(context).allow is True
        assert plugin.before_step_policy(context).allow is True
        assert plugin.before_tool_policy(context).allow is True

    def test_custom_policy(self) -> None:
        class BlockingPlugin(ControlPlanePlugin):
            def before_step_policy(self, context: PolicyContext) -> PolicyDecision:
                if context.step and context.step.get("dangerous"):
                    return PolicyDecision.blocked("step is dangerous")
                return PolicyDecision.allowed()

        plugin = BlockingPlugin()

        safe_context = PolicyContext(
            phase="before_step",
            manifest={},
            step={"name": "safe-step"},
        )
        assert plugin.before_step_policy(safe_context).allow is True

        dangerous_context = PolicyContext(
            phase="before_step",
            manifest={},
            step={"name": "dangerous-step", "dangerous": True},
        )
        assert plugin.before_step_policy(dangerous_context).allow is False


class TestDataPlanePlugin:
    def test_data_plugin_methods(self) -> None:
        events: List[str] = []

        class TrackingPlugin(DataPlanePlugin):
            def on_run_started(self, context: DataContext) -> None:
                events.append("run_started")

            def on_step_completed(self, context: DataContext) -> None:
                events.append("step_completed")

        plugin = TrackingPlugin()
        context = DataContext(
            phase="run_started",
            manifest={"run_id": "test"},
        )

        plugin.on_run_started(context)
        plugin.on_step_completed(context)

        assert events == ["run_started", "step_completed"]


class TestPluginOrdering:
    def test_get_priority_control_plane(self) -> None:
        plugin = ControlPlanePlugin()
        assert get_priority(plugin) == 0

    def test_get_priority_data_plane(self) -> None:
        plugin = DataPlanePlugin()
        assert get_priority(plugin) == 100

    def test_get_priority_legacy(self) -> None:
        plugin = Plugin()
        assert get_priority(plugin) == 50

    def test_get_priority_custom(self) -> None:
        class CustomPriorityPlugin(ControlPlanePlugin):
            priority = 25

        plugin = CustomPriorityPlugin()
        assert get_priority(plugin) == 25

    def test_sort_by_priority(self) -> None:
        class LowPriority(ControlPlanePlugin):
            priority = 10

        class HighPriority(DataPlanePlugin):
            priority = 200

        plugins = [
            HighPriority(),
            LowPriority(),
            Plugin(),
        ]

        sorted_plugins = sort_by_priority(plugins)

        assert isinstance(sorted_plugins[0], LowPriority)
        assert isinstance(sorted_plugins[1], Plugin)
        assert isinstance(sorted_plugins[2], HighPriority)

    def test_partition_plugins(self) -> None:
        control = ControlPlanePlugin()
        data = DataPlanePlugin()
        legacy = Plugin()

        control_list, data_list, legacy_list = partition_plugins([control, data, legacy])

        assert control in control_list
        assert data in data_list
        assert legacy in legacy_list


class TestPluginManager:
    def test_register_and_list(self) -> None:
        manager = PluginManager()
        plugin = Plugin()
        manager.register(plugin)

        assert plugin in manager.plugins

    def test_unregister(self) -> None:
        manager = PluginManager()
        plugin = Plugin()
        manager.register(plugin)

        result = manager.unregister(plugin)
        assert result is True
        assert plugin not in manager.plugins

    def test_unregister_not_found(self) -> None:
        manager = PluginManager()
        plugin = Plugin()

        result = manager.unregister(plugin)
        assert result is False

    def test_control_plugins_property(self) -> None:
        manager = PluginManager()
        control = ControlPlanePlugin()
        data = DataPlanePlugin()
        legacy = Plugin()

        manager.register(control)
        manager.register(data)
        manager.register(legacy)

        assert control in manager.control_plugins
        assert data not in manager.control_plugins

    def test_data_plugins_property(self) -> None:
        manager = PluginManager()
        control = ControlPlanePlugin()
        data = DataPlanePlugin()
        legacy = Plugin()

        manager.register(control)
        manager.register(data)
        manager.register(legacy)

        assert data in manager.data_plugins
        assert control not in manager.data_plugins

    def test_legacy_plugins_property(self) -> None:
        manager = PluginManager()
        control = ControlPlanePlugin()
        data = DataPlanePlugin()
        legacy = Plugin()

        manager.register(control)
        manager.register(data)
        manager.register(legacy)

        assert legacy in manager.legacy_plugins
        assert control not in manager.legacy_plugins
        assert data not in manager.legacy_plugins


class TestPluginManagerControlPlane:
    def test_run_before_run_policy(self) -> None:
        class AllowingPlugin(ControlPlanePlugin):
            def before_run_policy(self, context: PolicyContext) -> PolicyDecision:
                return PolicyDecision.allowed("ok")

        manager = PluginManager()
        manager.register(AllowingPlugin())

        decision = manager.run_before_run_policy({"run_id": "test"})
        assert decision.allow is True

    def test_run_before_run_policy_blocks(self) -> None:
        class BlockingPlugin(ControlPlanePlugin):
            def before_run_policy(self, context: PolicyContext) -> PolicyDecision:
                return PolicyDecision.blocked("not allowed")

        manager = PluginManager()
        manager.register(BlockingPlugin())

        decision = manager.run_before_run_policy({"run_id": "test"})
        assert decision.allow is False
        assert "not allowed" in decision.reason

    def test_run_before_step_policy(self) -> None:
        class ConditionalPlugin(ControlPlanePlugin):
            def before_step_policy(self, context: PolicyContext) -> PolicyDecision:
                if context.step and context.step.get("skip"):
                    return PolicyDecision.blocked("skipped")
                return PolicyDecision.allowed()

        manager = PluginManager()
        manager.register(ConditionalPlugin())

        # Should allow
        decision = manager.run_before_step_policy(
            {"name": "step1"},
            {"run_id": "test"},
        )
        assert decision.allow is True

        # Should block
        decision = manager.run_before_step_policy(
            {"name": "step2", "skip": True},
            {"run_id": "test"},
        )
        assert decision.allow is False

    def test_run_before_tool_policy(self) -> None:
        class ToolBlockerPlugin(ControlPlanePlugin):
            def before_tool_policy(self, context: PolicyContext) -> PolicyDecision:
                if context.tool_name == "dangerous_tool":
                    return PolicyDecision.blocked("tool blocked")
                return PolicyDecision.allowed()

        manager = PluginManager()
        manager.register(ToolBlockerPlugin())

        decision = manager.run_before_tool_policy(
            "safe_tool",
            {},
            {"run_id": "test"},
        )
        assert decision.allow is True

        decision = manager.run_before_tool_policy(
            "dangerous_tool",
            {},
            {"run_id": "test"},
        )
        assert decision.allow is False

    def test_on_policy_violation_called(self) -> None:
        violations: List[PolicyDecision] = []

        class TrackingPlugin(ControlPlanePlugin):
            def before_run_policy(self, context: PolicyContext) -> PolicyDecision:
                return PolicyDecision.blocked("tracked")

            def on_policy_violation(
                self,
                context: PolicyContext,
                decision: PolicyDecision,
            ) -> None:
                violations.append(decision)

        manager = PluginManager()
        manager.register(TrackingPlugin())

        manager.run_before_run_policy({"run_id": "test"})
        assert len(violations) == 1
        assert violations[0].reason == "tracked"


class TestPluginManagerDataPlane:
    def test_run_data_hooks(self) -> None:
        events: List[str] = []

        class TrackingPlugin(DataPlanePlugin):
            def on_run_started(self, context: DataContext) -> None:
                events.append("run_started")

            def on_step_completed(self, context: DataContext) -> None:
                events.append("step_completed")

        manager = PluginManager()
        manager.register(TrackingPlugin())

        manager.run_data_hooks("run_started", {"run_id": "test"})
        manager.run_data_hooks("step_completed", {"run_id": "test"})

        assert events == ["run_started", "step_completed"]

    def test_data_hooks_dont_block(self) -> None:
        class FailingPlugin(DataPlanePlugin):
            def on_run_started(self, context: DataContext) -> None:
                raise ValueError("data plugin error")

        manager = PluginManager()
        manager.register(FailingPlugin())

        # Should not raise - exceptions are caught
        manager.run_data_hooks("run_started", {"run_id": "test"})


class TestPluginManagerBackwardCompatibility:
    def test_legacy_before_run(self) -> None:
        calls: List[str] = []

        class LegacyPlugin(Plugin):
            def before_run(self, manifest: Dict[str, Any]) -> None:
                calls.append("legacy_before_run")

        class NewControlPlugin(ControlPlanePlugin):
            def before_run(self, manifest: Dict[str, Any]) -> None:
                calls.append("control_before_run")

        class NewDataPlugin(DataPlanePlugin):
            def before_run(self, manifest: Dict[str, Any]) -> None:
                calls.append("data_before_run")

        manager = PluginManager()
        manager.register(NewDataPlugin())  # Priority 100
        manager.register(LegacyPlugin())  # Priority 50
        manager.register(NewControlPlugin())  # Priority 0

        manager.before_run({"run_id": "test"})

        # Should be called in priority order
        assert calls == ["control_before_run", "legacy_before_run", "data_before_run"]

    def test_legacy_after_step(self) -> None:
        calls: List[str] = []

        class LegacyPlugin(Plugin):
            def after_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
                calls.append(f"step:{step.get('name')}")

        manager = PluginManager()
        manager.register(LegacyPlugin())

        manager.after_step({"name": "test-step"}, {"run_id": "test"})
        assert calls == ["step:test-step"]

    def test_legacy_on_error(self) -> None:
        errors: List[str] = []

        class LegacyPlugin(Plugin):
            def on_error(self, step: Dict[str, Any], manifest: Dict[str, Any], error: str) -> None:
                errors.append(error)

        manager = PluginManager()
        manager.register(LegacyPlugin())

        manager.on_error({}, {}, "test error")
        assert errors == ["test error"]

    def test_exception_in_legacy_hook_doesnt_propagate(self) -> None:
        class FailingPlugin(Plugin):
            def before_run(self, manifest: Dict[str, Any]) -> None:
                raise RuntimeError("legacy plugin error")

        manager = PluginManager()
        manager.register(FailingPlugin())

        # Should not raise
        manager.before_run({"run_id": "test"})


class TestGatePolicyPlugin:
    def test_no_gate_allows(self) -> None:
        plugin = GatePolicyPlugin()
        context = PolicyContext(
            phase="before_step",
            manifest={},
            step={"name": "step1"},
        )

        decision = plugin.before_step_policy(context)
        assert decision.allow is True

    def test_gate_required_blocks(self) -> None:
        plugin = GatePolicyPlugin()
        context = PolicyContext(
            phase="before_step",
            manifest={},
            step={"name": "step1", "human_gate": "required"},
            config={
                "hitl": {
                    "mode": "blocking",
                    "policy": {},
                },
            },
        )

        decision = plugin.before_step_policy(context)
        assert decision.allow is False
        assert decision.block_type == "gate"


class TestAuditPlugin:
    def test_captures_events(self) -> None:
        plugin = AuditPlugin()

        context = DataContext(
            phase="run_started",
            manifest={"run_id": "test-123"},
        )
        plugin.on_run_started(context)

        entries = plugin.get_entries()
        assert len(entries) == 1
        assert entries[0]["event_type"] == "run_started"
        assert entries[0]["run_id"] == "test-123"

    def test_writes_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            plugin = AuditPlugin(run_dir)

            context = DataContext(
                phase="run_started",
                manifest={"run_id": "test-456"},
            )
            plugin.on_run_started(context)

            audit_file = run_dir / "audit.json"
            assert audit_file.exists()

            import json

            data = json.loads(audit_file.read_text())
            assert len(data["entries"]) == 1

    def test_captures_step_events(self) -> None:
        plugin = AuditPlugin()

        context = DataContext(
            phase="step_completed",
            manifest={"run_id": "test"},
            step={"name": "test-step", "outputs": ["out.md"]},
        )
        plugin.on_step_completed(context)

        entries = plugin.get_entries()
        assert entries[0]["event_type"] == "step_completed"
        assert entries[0]["details"]["step_name"] == "test-step"

    def test_clear_entries(self) -> None:
        plugin = AuditPlugin()

        context = DataContext(phase="test", manifest={})
        plugin.on_run_started(context)
        plugin.on_run_started(context)

        assert len(plugin.get_entries()) == 2

        plugin.clear()
        assert len(plugin.get_entries()) == 0
