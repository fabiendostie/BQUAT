from __future__ import annotations

from typing import Any, Dict, Iterable, List

from runtime.plugins.base import Plugin


class PluginManager:
    def __init__(self, plugins: Iterable[Plugin] | None = None) -> None:
        self._plugins: List[Plugin] = list(plugins or [])

    def register(self, plugin: Plugin) -> None:
        self._plugins.append(plugin)

    def before_run(self, manifest: Dict[str, Any]) -> None:
        for plugin in self._plugins:
            plugin.before_run(manifest)

    def after_run(self, manifest: Dict[str, Any]) -> None:
        for plugin in self._plugins:
            plugin.after_run(manifest)

    def before_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        for plugin in self._plugins:
            plugin.before_step(step, manifest)

    def after_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        for plugin in self._plugins:
            plugin.after_step(step, manifest)

    def on_error(self, step: Dict[str, Any], manifest: Dict[str, Any], error: str) -> None:
        for plugin in self._plugins:
            plugin.on_error(step, manifest, error)

    def on_validation(self, manifest: Dict[str, Any], status: str) -> None:
        for plugin in self._plugins:
            plugin.on_validation(manifest, status)
