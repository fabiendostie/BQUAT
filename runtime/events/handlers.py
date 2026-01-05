from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from runtime import storage
from runtime.events.bus import EventHandler
from runtime.events.types import BusEvent


class JsonPersistenceHandler(EventHandler):
    """Handler that persists events to events.json in the run directory.

    Bridges the event bus to the existing storage.append_event() pattern.
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def handle(self, event: BusEvent) -> None:
        payload = storage.read_events(self.run_dir)
        events_list: List[Dict[str, Any]] = payload.get("events", [])
        events_list.append(event.to_dict())
        payload["events"] = events_list
        storage.write_events(self.run_dir, payload)

    def on_error(self, event: BusEvent, error: Exception) -> None:
        # Log persistence errors but don't block workflow
        pass


class ObservabilityBridgeHandler(EventHandler):
    """Handler that bridges events to the existing observability system.

    Connects the event bus to runtime/logging/emitter.py EventEmitter.
    """

    def __init__(
        self,
        emitter_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self._emit = emitter_callback

    def handle(self, event: BusEvent) -> None:
        if self._emit is None:
            return

        # Map BusEvent to observability format
        obs_payload = {
            "run_id": event.run_id,
            "timestamp": event.timestamp,
            "source": event.source,
            **event.payload,
        }
        if event.step_id:
            obs_payload["step_id"] = event.step_id
        if event.correlation_id:
            obs_payload["correlation_id"] = event.correlation_id

        self._emit(event.event_type, obs_payload)

    def on_error(self, event: BusEvent, error: Exception) -> None:
        pass


class TimelineHandler(EventHandler):
    """Handler that updates the timeline.json with events.

    Triggers timeline rebuild after significant events.
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def handle(self, event: BusEvent) -> None:
        storage.update_timeline(self.run_dir)

    def on_error(self, event: BusEvent, error: Exception) -> None:
        pass


class AggregatingHandler(EventHandler):
    """Handler that collects events in memory for batch processing.

    Useful for testing or batch analytics.
    """

    def __init__(self, max_events: int = 10000) -> None:
        self.events: List[BusEvent] = []
        self.max_events = max_events

    def handle(self, event: BusEvent) -> None:
        if len(self.events) < self.max_events:
            self.events.append(event)

    def clear(self) -> List[BusEvent]:
        events = self.events
        self.events = []
        return events

    def get_by_type(self, event_type: str) -> List[BusEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def get_by_step(self, step_id: str) -> List[BusEvent]:
        return [e for e in self.events if e.step_id == step_id]


class LoggingHandler(EventHandler):
    """Handler that logs events using the structured logger.

    Connects the event bus to runtime/logging/structured.py.
    """

    def __init__(
        self,
        log_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
    ) -> None:
        self._log = log_callback

    def handle(self, event: BusEvent) -> None:
        if self._log is None:
            return

        # Determine log level based on event type
        level = "info"
        if "Failed" in event.event_type or "Error" in event.event_type:
            level = "error"
        elif "Blocked" in event.event_type or "Required" in event.event_type:
            level = "warning"

        log_data = {
            "event_type": event.event_type,
            "run_id": event.run_id,
            "timestamp": event.timestamp,
            "source": event.source,
            **event.payload,
        }
        if event.step_id:
            log_data["step_id"] = event.step_id

        self._log(level, event.event_type, log_data)

    def on_error(self, event: BusEvent, error: Exception) -> None:
        if self._log:
            self._log(
                "error",
                "EventHandlerError",
                {
                    "event_type": event.event_type,
                    "error": str(error),
                },
            )


class FilteringHandler(EventHandler):
    """Handler that wraps another handler with additional filtering logic.

    Allows runtime filtering beyond the EventFilter.
    """

    def __init__(
        self,
        inner: EventHandler,
        predicate: Callable[[BusEvent], bool],
    ) -> None:
        self._inner = inner
        self._predicate = predicate

    def handle(self, event: BusEvent) -> None:
        if self._predicate(event):
            self._inner.handle(event)

    def on_error(self, event: BusEvent, error: Exception) -> None:
        self._inner.on_error(event, error)


class CompositeHandler(EventHandler):
    """Handler that dispatches to multiple handlers.

    Useful for fan-out scenarios.
    """

    def __init__(self, handlers: Optional[List[EventHandler]] = None) -> None:
        self._handlers = list(handlers or [])

    def add(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def remove(self, handler: EventHandler) -> bool:
        try:
            self._handlers.remove(handler)
            return True
        except ValueError:
            return False

    def handle(self, event: BusEvent) -> None:
        for handler in self._handlers:
            try:
                handler.handle(event)
            except Exception as exc:  # noqa: BLE001
                handler.on_error(event, exc)

    def on_error(self, event: BusEvent, error: Exception) -> None:
        for handler in self._handlers:
            handler.on_error(event, error)
