from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from runtime.logging.models import EmittedEvent
from runtime.plugins.base import Plugin
from runtime.time_provider import get_current_time


class EventHandler:
    """Base class for event handlers (external integrations)."""

    def handle(self, event: EmittedEvent) -> None:
        raise NotImplementedError


class CallbackHandler(EventHandler):
    """Handler that invokes a callback function."""

    def __init__(self, callback: Callable[[EmittedEvent], None]) -> None:
        self._callback = callback

    def handle(self, event: EmittedEvent) -> None:
        self._callback(event)


class EventEmitter:
    """Emits events for external tooling consumption."""

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._handlers: List[EventHandler] = []
        self._filters: Dict[str, Optional[List[str]]] = {}

    def register(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def add_filter(self, event_type: str, sources: Optional[List[str]] = None) -> None:
        """Add filter to only emit specific event types from specific sources."""
        self._filters[event_type] = sources

    def clear_filters(self) -> None:
        """Clear all filters (emit all events)."""
        self._filters.clear()

    def _should_emit(self, event_type: str, source: str) -> bool:
        if not self._filters:
            return True
        if event_type not in self._filters:
            return False
        sources = self._filters[event_type]
        return sources is None or source in sources

    def emit(
        self,
        event_type: str,
        source: str,
        payload: Optional[Dict[str, Any]] = None,
        step_id: Optional[str] = None,
    ) -> None:
        if not self._should_emit(event_type, source):
            return
        event = EmittedEvent(
            event_type=event_type,
            timestamp=get_current_time(),
            run_id=self._run_id,
            source=source,
            payload=dict(payload or {}),
            step_id=step_id,
        )
        for handler in self._handlers:
            try:
                handler.handle(event)
            except Exception:
                pass


class ObservabilityPlugin(Plugin):
    """Plugin that bridges engine events to the EventEmitter and StructuredLogger."""

    def __init__(
        self,
        emitter: Optional[EventEmitter] = None,
        logger: Optional[Any] = None,
    ) -> None:
        self._emitter = emitter
        self._logger = logger

    def before_run(self, manifest: Dict[str, Any]) -> None:
        if self._emitter:
            self._emitter.emit(
                "run.started",
                "engine",
                {"workflow": manifest.get("workflow", {})},
            )
        if self._logger:
            self._logger.run("info", "workflow run started")

    def after_run(self, manifest: Dict[str, Any]) -> None:
        if self._emitter:
            self._emitter.emit(
                "run.completed",
                "engine",
                {"status": manifest.get("status")},
            )
        if self._logger:
            self._logger.run("info", f"workflow run completed: {manifest.get('status')}")

    def before_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        step_id = step.get("step_id")
        if self._emitter:
            self._emitter.emit(
                "step.started",
                "step",
                {"step_name": step.get("name"), "attempt": step.get("attempts", 1)},
                step_id=step_id,
            )
        if self._logger:
            self._logger.step("info", f"step started: {step.get('name')}", step_id or "")

    def after_step(self, step: Dict[str, Any], manifest: Dict[str, Any]) -> None:
        step_id = step.get("step_id")
        if self._emitter:
            self._emitter.emit(
                "step.completed",
                "step",
                {"step_name": step.get("name"), "outputs": step.get("outputs", [])},
                step_id=step_id,
            )
        if self._logger:
            self._logger.step("info", f"step completed: {step.get('name')}", step_id or "")

    def on_error(self, step: Dict[str, Any], manifest: Dict[str, Any], error: str) -> None:
        step_id = step.get("step_id")
        if self._emitter:
            self._emitter.emit(
                "step.error",
                "step",
                {"step_name": step.get("name"), "error": error},
                step_id=step_id,
            )
        if self._logger:
            self._logger.step("error", f"step failed: {error}", step_id or "")

    def on_validation(self, manifest: Dict[str, Any], status: str) -> None:
        if self._emitter:
            self._emitter.emit(
                "run.validation",
                "validation",
                {"status": status},
            )
        if self._logger:
            level = "info" if status == "completed" else "warn"
            self._logger.validation(level, f"run validation: {status}")
