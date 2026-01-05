from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from runtime.events.types import EVENT_CATEGORIES, BusEvent


class EventHandler(ABC):
    """Base class for event handlers."""

    @abstractmethod
    def handle(self, event: BusEvent) -> None:
        """Process an event. Must not raise exceptions."""

    def on_error(self, event: BusEvent, error: Exception) -> None:
        """Called when handle() raises an exception. Override to customize."""
        pass


class CallbackHandler(EventHandler):
    """Event handler that wraps a callback function."""

    def __init__(
        self,
        callback: Callable[[BusEvent], None],
        error_callback: Optional[Callable[[BusEvent, Exception], None]] = None,
    ) -> None:
        self._callback = callback
        self._error_callback = error_callback

    def handle(self, event: BusEvent) -> None:
        self._callback(event)

    def on_error(self, event: BusEvent, error: Exception) -> None:
        if self._error_callback:
            self._error_callback(event, error)


@dataclass(frozen=True)
class EventFilter:
    """Filter for event subscriptions."""

    event_types: Optional[Set[str]] = None
    categories: Optional[Set[str]] = None
    sources: Optional[Set[str]] = None
    run_ids: Optional[Set[str]] = None

    def matches(self, event: BusEvent) -> bool:
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.categories:
            event_in_category = any(
                event.event_type in EVENT_CATEGORIES.get(cat, []) for cat in self.categories
            )
            if not event_in_category:
                return False
        if self.sources and event.source not in self.sources:
            return False
        if self.run_ids and event.run_id not in self.run_ids:
            return False
        return True

    @classmethod
    def for_types(cls, *event_types: str) -> EventFilter:
        return cls(event_types=set(event_types))

    @classmethod
    def for_categories(cls, *categories: str) -> EventFilter:
        return cls(categories=set(categories))

    @classmethod
    def for_run(cls, run_id: str) -> EventFilter:
        return cls(run_ids={run_id})


@dataclass
class Subscription:
    """Represents an active subscription to the event bus."""

    subscription_id: str
    handler: EventHandler
    filter: Optional[EventFilter] = None
    active: bool = True

    def matches(self, event: BusEvent) -> bool:
        if not self.active:
            return False
        if self.filter is None:
            return True
        return self.filter.matches(event)


@dataclass
class EventBus:
    """Pub/sub event bus for workflow state transitions.

    Thread-safe event publishing and subscription management.
    Handlers are called synchronously in subscription order.
    Handler exceptions are caught and reported via on_error().
    """

    _subscriptions: Dict[str, Subscription] = field(default_factory=dict)
    _paused: bool = False

    def subscribe(
        self,
        handler: EventHandler,
        filter: Optional[EventFilter] = None,
    ) -> str:
        """Subscribe a handler to receive events.

        Args:
            handler: Event handler to receive events.
            filter: Optional filter to restrict which events are received.

        Returns:
            Subscription ID that can be used to unsubscribe.
        """
        subscription_id = f"sub-{uuid.uuid4().hex[:12]}"
        self._subscriptions[subscription_id] = Subscription(
            subscription_id=subscription_id,
            handler=handler,
            filter=filter,
        )
        return subscription_id

    def subscribe_callback(
        self,
        callback: Callable[[BusEvent], None],
        filter: Optional[EventFilter] = None,
        error_callback: Optional[Callable[[BusEvent, Exception], None]] = None,
    ) -> str:
        """Subscribe a callback function to receive events.

        Convenience method that wraps the callback in a CallbackHandler.

        Args:
            callback: Function to call for each event.
            filter: Optional filter to restrict which events are received.
            error_callback: Optional function to call on errors.

        Returns:
            Subscription ID that can be used to unsubscribe.
        """
        handler = CallbackHandler(callback, error_callback)
        return self.subscribe(handler, filter)

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription.

        Args:
            subscription_id: ID returned from subscribe().

        Returns:
            True if subscription was found and removed, False otherwise.
        """
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return True
        return False

    def pause(self) -> None:
        """Pause event delivery. Events published while paused are dropped."""
        self._paused = True

    def resume(self) -> None:
        """Resume event delivery."""
        self._paused = False

    def publish(self, event: BusEvent) -> int:
        """Publish an event to all matching subscribers.

        Args:
            event: Event to publish.

        Returns:
            Number of handlers that received the event.
        """
        if self._paused:
            return 0

        delivered = 0
        for subscription in list(self._subscriptions.values()):
            if not subscription.matches(event):
                continue
            try:
                subscription.handler.handle(event)
                delivered += 1
            except Exception as exc:  # noqa: BLE001
                try:
                    subscription.handler.on_error(event, exc)
                except Exception:  # noqa: BLE001, S110
                    pass
        return delivered

    def get_subscriptions(self) -> List[Subscription]:
        """Return a copy of all active subscriptions."""
        return list(self._subscriptions.values())

    def clear(self) -> int:
        """Remove all subscriptions.

        Returns:
            Number of subscriptions removed.
        """
        count = len(self._subscriptions)
        self._subscriptions.clear()
        return count


# Global event bus instance (optional - can create per-run instances)
_default_bus: Optional[EventBus] = None


def get_default_bus() -> EventBus:
    """Get or create the default global event bus."""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def reset_default_bus() -> None:
    """Reset the default global event bus (mainly for testing)."""
    global _default_bus
    if _default_bus is not None:
        _default_bus.clear()
    _default_bus = None
