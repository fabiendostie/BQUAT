"""Tests for the event bus module (REQ-SPEC-001)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.events.bus import (  # noqa: E402
    CallbackHandler,
    EventBus,
    EventFilter,
    EventHandler,
    get_default_bus,
    reset_default_bus,
)
from runtime.events.handlers import (  # noqa: E402
    AggregatingHandler,
    CompositeHandler,
    FilteringHandler,
)
from runtime.events.types import EVENT_CATEGORIES, BusEvent, EventType  # noqa: E402


class TestBusEvent:
    def test_create_event(self) -> None:
        event = BusEvent(
            event_type=EventType.WORKFLOW_STARTED.value,
            run_id="run-123",
            timestamp="2026-01-04T10:00:00-05:00",
            payload={"module": "bmm", "workflow": "prd"},
            step_id="step-01",
            source="engine",
        )
        assert event.event_type == "WorkflowStarted"
        assert event.run_id == "run-123"
        assert event.step_id == "step-01"
        assert event.payload["module"] == "bmm"

    def test_event_to_dict(self) -> None:
        event = BusEvent(
            event_type="TestEvent",
            run_id="run-456",
            timestamp="2026-01-04T10:00:00-05:00",
            payload={"key": "value"},
        )
        data = event.to_dict()
        assert data["event_type"] == "TestEvent"
        assert data["run_id"] == "run-456"
        assert data["payload"] == {"key": "value"}
        assert "step_id" not in data  # None values excluded

    def test_event_from_dict(self) -> None:
        data = {
            "event_type": "TestEvent",
            "run_id": "run-789",
            "timestamp": "2026-01-04T10:00:00-05:00",
            "payload": {"test": True},
            "step_id": "step-02",
            "source": "test",
        }
        event = BusEvent.from_dict(data)
        assert event.event_type == "TestEvent"
        assert event.step_id == "step-02"
        assert event.payload["test"] is True


class TestEventFilter:
    def test_filter_by_event_type(self) -> None:
        filter = EventFilter.for_types("WorkflowStarted", "WorkflowCompleted")
        event1 = BusEvent(
            event_type="WorkflowStarted",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        event2 = BusEvent(
            event_type="WorkflowFailed",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        assert filter.matches(event1) is True
        assert filter.matches(event2) is False

    def test_filter_by_category(self) -> None:
        filter = EventFilter.for_categories("gate")
        gate_event = BusEvent(
            event_type="HumanGateRequired",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        step_event = BusEvent(
            event_type="WorkflowStepStarted",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        assert filter.matches(gate_event) is True
        assert filter.matches(step_event) is False

    def test_filter_by_run_id(self) -> None:
        filter = EventFilter.for_run("run-specific")
        event1 = BusEvent(
            event_type="TestEvent",
            run_id="run-specific",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        event2 = BusEvent(
            event_type="TestEvent",
            run_id="run-other",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        assert filter.matches(event1) is True
        assert filter.matches(event2) is False

    def test_filter_by_source(self) -> None:
        filter = EventFilter(sources={"plugin", "guardrail"})
        event1 = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
            source="plugin",
        )
        event2 = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
            source="engine",
        )
        assert filter.matches(event1) is True
        assert filter.matches(event2) is False

    def test_empty_filter_matches_all(self) -> None:
        filter = EventFilter()
        event = BusEvent(
            event_type="AnyEvent",
            run_id="any-run",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        assert filter.matches(event) is True


class TestEventBus:
    def test_subscribe_and_publish(self) -> None:
        bus = EventBus()
        received: List[BusEvent] = []

        def handler(event: BusEvent) -> None:
            received.append(event)

        bus.subscribe_callback(handler)

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        delivered = bus.publish(event)

        assert delivered == 1
        assert len(received) == 1
        assert received[0].event_type == "TestEvent"

    def test_subscribe_with_filter(self) -> None:
        bus = EventBus()
        received: List[BusEvent] = []

        def handler(event: BusEvent) -> None:
            received.append(event)

        filter = EventFilter.for_types("TargetEvent")
        bus.subscribe_callback(handler, filter)

        bus.publish(
            BusEvent(
                event_type="OtherEvent",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
            )
        )
        bus.publish(
            BusEvent(
                event_type="TargetEvent",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
            )
        )

        assert len(received) == 1
        assert received[0].event_type == "TargetEvent"

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        received: List[BusEvent] = []

        def handler(event: BusEvent) -> None:
            received.append(event)

        sub_id = bus.subscribe_callback(handler)

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        bus.publish(event)
        assert len(received) == 1

        result = bus.unsubscribe(sub_id)
        assert result is True

        bus.publish(event)
        assert len(received) == 1  # No new events

    def test_unsubscribe_unknown_returns_false(self) -> None:
        bus = EventBus()
        result = bus.unsubscribe("unknown-id")
        assert result is False

    def test_pause_and_resume(self) -> None:
        bus = EventBus()
        received: List[BusEvent] = []

        def handler(event: BusEvent) -> None:
            received.append(event)

        bus.subscribe_callback(handler)

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )

        bus.pause()
        delivered = bus.publish(event)
        assert delivered == 0
        assert len(received) == 0

        bus.resume()
        delivered = bus.publish(event)
        assert delivered == 1
        assert len(received) == 1

    def test_handler_error_does_not_block(self) -> None:
        bus = EventBus()
        received: List[BusEvent] = []

        def failing_handler(event: BusEvent) -> None:
            raise ValueError("Handler error")

        def good_handler(event: BusEvent) -> None:
            received.append(event)

        bus.subscribe_callback(failing_handler)
        bus.subscribe_callback(good_handler)

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        delivered = bus.publish(event)

        assert delivered == 1  # Only good handler succeeded
        assert len(received) == 1

    def test_handler_on_error_called(self) -> None:
        bus = EventBus()
        errors: List[Exception] = []

        class ErrorTrackingHandler(EventHandler):
            def handle(self, event: BusEvent) -> None:
                raise ValueError("Test error")

            def on_error(self, event: BusEvent, error: Exception) -> None:
                errors.append(error)

        bus.subscribe(ErrorTrackingHandler())

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        bus.publish(event)

        assert len(errors) == 1
        assert str(errors[0]) == "Test error"

    def test_multiple_subscribers(self) -> None:
        bus = EventBus()
        received1: List[BusEvent] = []
        received2: List[BusEvent] = []

        bus.subscribe_callback(lambda e: received1.append(e))
        bus.subscribe_callback(lambda e: received2.append(e))

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        delivered = bus.publish(event)

        assert delivered == 2
        assert len(received1) == 1
        assert len(received2) == 1

    def test_clear_subscriptions(self) -> None:
        bus = EventBus()
        bus.subscribe_callback(lambda e: None)
        bus.subscribe_callback(lambda e: None)

        assert len(bus.get_subscriptions()) == 2

        count = bus.clear()
        assert count == 2
        assert len(bus.get_subscriptions()) == 0

    def test_get_subscriptions(self) -> None:
        bus = EventBus()
        sub_id = bus.subscribe_callback(lambda e: None)

        subs = bus.get_subscriptions()
        assert len(subs) == 1
        assert subs[0].subscription_id == sub_id


class TestDefaultBus:
    def test_get_default_bus(self) -> None:
        reset_default_bus()
        bus1 = get_default_bus()
        bus2 = get_default_bus()
        assert bus1 is bus2

    def test_reset_default_bus(self) -> None:
        reset_default_bus()
        bus1 = get_default_bus()
        reset_default_bus()
        bus2 = get_default_bus()
        assert bus1 is not bus2


class TestCallbackHandler:
    def test_callback_handler(self) -> None:
        received: List[BusEvent] = []
        handler = CallbackHandler(lambda e: received.append(e))

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        handler.handle(event)

        assert len(received) == 1

    def test_callback_handler_with_error_callback(self) -> None:
        errors: List[Exception] = []
        handler = CallbackHandler(
            lambda e: (_ for _ in ()).throw(ValueError("test")),
            lambda e, err: errors.append(err),
        )

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        try:
            handler.handle(event)
        except ValueError:
            pass

        handler.on_error(event, ValueError("on_error test"))
        assert len(errors) == 1


class TestAggregatingHandler:
    def test_collects_events(self) -> None:
        handler = AggregatingHandler()

        for i in range(5):
            event = BusEvent(
                event_type=f"Event{i}",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
            )
            handler.handle(event)

        assert len(handler.events) == 5

    def test_max_events_limit(self) -> None:
        handler = AggregatingHandler(max_events=3)

        for i in range(10):
            event = BusEvent(
                event_type=f"Event{i}",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
            )
            handler.handle(event)

        assert len(handler.events) == 3

    def test_clear_returns_events(self) -> None:
        handler = AggregatingHandler()
        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        handler.handle(event)

        events = handler.clear()
        assert len(events) == 1
        assert len(handler.events) == 0

    def test_get_by_type(self) -> None:
        handler = AggregatingHandler()
        handler.handle(
            BusEvent(
                event_type="TypeA",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
            )
        )
        handler.handle(
            BusEvent(
                event_type="TypeB",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
            )
        )
        handler.handle(
            BusEvent(
                event_type="TypeA",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
            )
        )

        type_a = handler.get_by_type("TypeA")
        assert len(type_a) == 2


class TestCompositeHandler:
    def test_dispatches_to_all(self) -> None:
        received1: List[BusEvent] = []
        received2: List[BusEvent] = []

        handler = CompositeHandler(
            [
                CallbackHandler(lambda e: received1.append(e)),
                CallbackHandler(lambda e: received2.append(e)),
            ]
        )

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        handler.handle(event)

        assert len(received1) == 1
        assert len(received2) == 1

    def test_add_and_remove(self) -> None:
        received: List[BusEvent] = []
        inner = CallbackHandler(lambda e: received.append(e))

        handler = CompositeHandler()
        handler.add(inner)

        event = BusEvent(
            event_type="TestEvent",
            run_id="run-1",
            timestamp="2026-01-04T10:00:00-05:00",
        )
        handler.handle(event)
        assert len(received) == 1

        result = handler.remove(inner)
        assert result is True

        handler.handle(event)
        assert len(received) == 1  # No new events


class TestFilteringHandler:
    def test_filters_events(self) -> None:
        received: List[BusEvent] = []
        inner = CallbackHandler(lambda e: received.append(e))
        handler = FilteringHandler(
            inner,
            lambda e: e.payload.get("important", False),
        )

        handler.handle(
            BusEvent(
                event_type="TestEvent",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
                payload={"important": False},
            )
        )
        handler.handle(
            BusEvent(
                event_type="TestEvent",
                run_id="run-1",
                timestamp="2026-01-04T10:00:00-05:00",
                payload={"important": True},
            )
        )

        assert len(received) == 1
        assert received[0].payload["important"] is True


class TestEventCategories:
    def test_all_event_types_categorized(self) -> None:
        all_categorized = set()
        for events in EVENT_CATEGORIES.values():
            all_categorized.update(events)

        for event_type in EventType:
            assert event_type.value in all_categorized, f"{event_type.value} not in any category"

    def test_categories_exist(self) -> None:
        expected = {
            "workflow",
            "step",
            "gate",
            "tool",
            "guardrail",
            "validation",
            "evidence",
            "artifact",
            "context",
            "plugin",
        }
        assert set(EVENT_CATEGORIES.keys()) == expected
