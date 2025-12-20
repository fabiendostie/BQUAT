from __future__ import annotations

from typing import Any, Dict


class Plugin:
    def before_run(self, manifest: Dict[str, Any]) -> None:
        return None

    def after_run(self, manifest: Dict[str, Any]) -> None:
        return None

    def before_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        return None

    def after_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        return None

    def on_error(self, step: Dict[str, Any], manifest: Dict[str, Any], error: str) -> None:
        return None

    def on_validation(self, manifest: Dict[str, Any], status: str) -> None:
        return None
