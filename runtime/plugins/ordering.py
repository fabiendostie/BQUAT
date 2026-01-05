from __future__ import annotations

from typing import List, TypeVar

from runtime.plugins.base import Plugin
from runtime.plugins.control_plane import ControlPlanePlugin
from runtime.plugins.data_plane import DataPlanePlugin

T = TypeVar("T", bound=Plugin)


def get_priority(plugin: Plugin) -> int:
    """Get the priority of a plugin.

    Control plane plugins default to 0 (run first).
    Data plane plugins default to 100 (run after control plane).
    Legacy plugins default to 50 (run between).
    """
    priority = getattr(plugin, "priority", None)
    if isinstance(priority, int):
        return priority
    if isinstance(plugin, ControlPlanePlugin):
        return 0
    if isinstance(plugin, DataPlanePlugin):
        return 100
    return 50  # Legacy plugins run in the middle


def sort_by_priority(plugins: List[T]) -> List[T]:
    """Sort plugins by priority (lower priority runs first)."""
    return sorted(plugins, key=get_priority)


def partition_plugins(
    plugins: List[Plugin],
) -> tuple[List[ControlPlanePlugin], List[DataPlanePlugin], List[Plugin]]:
    """Partition plugins into control plane, data plane, and legacy.

    Returns:
        Tuple of (control_plugins, data_plugins, legacy_plugins).
    """
    control: List[ControlPlanePlugin] = []
    data: List[DataPlanePlugin] = []
    legacy: List[Plugin] = []

    for plugin in plugins:
        if isinstance(plugin, ControlPlanePlugin):
            control.append(plugin)
        elif isinstance(plugin, DataPlanePlugin):
            data.append(plugin)
        else:
            legacy.append(plugin)

    return (
        sort_by_priority(control),
        sort_by_priority(data),
        sort_by_priority(legacy),
    )


class PluginPriority:
    """Common priority values for plugins."""

    # Control plane priorities (0-49)
    RATE_LIMIT = 0
    AUTHORIZATION = 10
    GATE_POLICY = 20
    VALIDATION = 30

    # Legacy plugin priority (50)
    LEGACY = 50

    # Data plane priorities (100+)
    LOGGING = 100
    METRICS = 110
    OBSERVABILITY = 120
    AUDIT = 130
    ARTIFACT_TRACKING = 140
