from __future__ import annotations

import unittest
from typing import List
from uuid import uuid4

from runtime.logging.emitter import (
    CallbackHandler,
    EventEmitter,
    EventHandler,
    ObservabilityPlugin,
)
from runtime.logging.models import EmittedEvent


class MockHandler(EventHandler):
    def __init__(self) -> None:
        self.events: List[EmittedEvent] = []

    def handle(self, event: EmittedEvent) -> None:
        self.events.append(event)


class FailingHandler(EventHandler):
    def handle(self, event: EmittedEvent) -> None:
        raise RuntimeError("handler error")


class EventEmitterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = f"run-{uuid4().hex[:8]}"
        self.emitter = EventEmitter(self.run_id)

    def test_emit_to_handler(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.emit("test.event", "test")

        self.assertEqual(len(handler.events), 1)
        self.assertEqual(handler.events[0].event_type, "test.event")
        self.assertEqual(handler.events[0].source, "test")
        self.assertEqual(handler.events[0].run_id, self.run_id)

    def test_emit_with_payload(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.emit("test.event", "test", payload={"key": "value"})

        self.assertEqual(handler.events[0].payload, {"key": "value"})

    def test_emit_with_step_id(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.emit("step.event", "step", step_id="step-01")

        self.assertEqual(handler.events[0].step_id, "step-01")

    def test_emit_to_multiple_handlers(self) -> None:
        handler1 = MockHandler()
        handler2 = MockHandler()
        self.emitter.register(handler1)
        self.emitter.register(handler2)
        self.emitter.emit("test.event", "test")

        self.assertEqual(len(handler1.events), 1)
        self.assertEqual(len(handler2.events), 1)

    def test_handler_error_does_not_propagate(self) -> None:
        failing = FailingHandler()
        handler = MockHandler()
        self.emitter.register(failing)
        self.emitter.register(handler)

        self.emitter.emit("test.event", "test")
        self.assertEqual(len(handler.events), 1)

    def test_filter_allows_matching_event(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.add_filter("run.started", None)
        self.emitter.emit("run.started", "engine")

        self.assertEqual(len(handler.events), 1)

    def test_filter_blocks_non_matching_event(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.add_filter("run.started", None)
        self.emitter.emit("run.completed", "engine")

        self.assertEqual(len(handler.events), 0)

    def test_filter_with_source_restriction(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.add_filter("step.event", ["step"])
        self.emitter.emit("step.event", "step")
        self.emitter.emit("step.event", "other")

        self.assertEqual(len(handler.events), 1)
        self.assertEqual(handler.events[0].source, "step")

    def test_clear_filters(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.add_filter("run.started", None)
        self.emitter.clear_filters()
        self.emitter.emit("run.completed", "engine")

        self.assertEqual(len(handler.events), 1)

    def test_no_filters_emits_all(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.emit("event1", "source1")
        self.emitter.emit("event2", "source2")

        self.assertEqual(len(handler.events), 2)

    def test_timestamp_populated(self) -> None:
        handler = MockHandler()
        self.emitter.register(handler)
        self.emitter.emit("test.event", "test")

        self.assertIsNotNone(handler.events[0].timestamp)
        self.assertIn("T", handler.events[0].timestamp)


class CallbackHandlerTests(unittest.TestCase):
    def test_callback_invoked(self) -> None:
        received: List[EmittedEvent] = []

        def callback(event: EmittedEvent) -> None:
            received.append(event)

        handler = CallbackHandler(callback)
        emitter = EventEmitter("run-123")
        emitter.register(handler)
        emitter.emit("test.event", "test")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_type, "test.event")


class ObservabilityPluginTests(unittest.TestCase):
    def test_before_run_emits_and_logs(self) -> None:
        handler = MockHandler()
        emitter = EventEmitter("run-123")
        emitter.register(handler)

        logged: List[str] = []

        class MockLogger:
            def run(self, level: str, message: str) -> None:
                logged.append(message)

        plugin = ObservabilityPlugin(emitter=emitter, logger=MockLogger())
        plugin.before_run({"workflow": {"module": "bmm", "workflow": "prd"}})

        self.assertEqual(len(handler.events), 1)
        self.assertEqual(handler.events[0].event_type, "run.started")
        self.assertIn("workflow run started", logged)

    def test_after_run_emits_and_logs(self) -> None:
        handler = MockHandler()
        emitter = EventEmitter("run-123")
        emitter.register(handler)

        logged: List[str] = []

        class MockLogger:
            def run(self, level: str, message: str) -> None:
                logged.append(message)

        plugin = ObservabilityPlugin(emitter=emitter, logger=MockLogger())
        plugin.after_run({"status": "completed"})

        self.assertEqual(len(handler.events), 1)
        self.assertEqual(handler.events[0].event_type, "run.completed")
        self.assertIn("completed", logged[0])

    def test_before_step_emits(self) -> None:
        handler = MockHandler()
        emitter = EventEmitter("run-123")
        emitter.register(handler)
        plugin = ObservabilityPlugin(emitter=emitter)
        plugin.before_step({"name": "execute", "step_id": "step-01"}, {})

        self.assertEqual(handler.events[0].event_type, "step.started")
        self.assertEqual(handler.events[0].step_id, "step-01")

    def test_after_step_emits(self) -> None:
        handler = MockHandler()
        emitter = EventEmitter("run-123")
        emitter.register(handler)
        plugin = ObservabilityPlugin(emitter=emitter)
        plugin.after_step({"name": "execute", "step_id": "step-01", "outputs": ["out.md"]}, {})

        self.assertEqual(handler.events[0].event_type, "step.completed")
        self.assertEqual(handler.events[0].payload["outputs"], ["out.md"])

    def test_on_error_emits(self) -> None:
        handler = MockHandler()
        emitter = EventEmitter("run-123")
        emitter.register(handler)

        logged: List[str] = []

        class MockLogger:
            def step(self, level: str, message: str, step_id: str) -> None:
                logged.append(f"{level}: {message}")

        plugin = ObservabilityPlugin(emitter=emitter, logger=MockLogger())
        plugin.on_error({"name": "execute", "step_id": "step-01"}, {}, "timeout")

        self.assertEqual(handler.events[0].event_type, "step.error")
        self.assertEqual(handler.events[0].payload["error"], "timeout")
        self.assertIn("error: step failed: timeout", logged)

    def test_on_validation_emits(self) -> None:
        handler = MockHandler()
        emitter = EventEmitter("run-123")
        emitter.register(handler)

        logged: List[str] = []

        class MockLogger:
            def validation(self, level: str, message: str) -> None:
                logged.append(f"{level}: {message}")

        plugin = ObservabilityPlugin(emitter=emitter, logger=MockLogger())
        plugin.on_validation({}, "blocked")

        self.assertEqual(handler.events[0].event_type, "run.validation")
        self.assertEqual(handler.events[0].payload["status"], "blocked")
        self.assertIn("warn: run validation: blocked", logged)

    def test_on_validation_completed_logs_info(self) -> None:
        logged: List[str] = []

        class MockLogger:
            def validation(self, level: str, message: str) -> None:
                logged.append(level)

        plugin = ObservabilityPlugin(logger=MockLogger())
        plugin.on_validation({}, "completed")

        self.assertEqual(logged[0], "info")

    def test_plugin_without_emitter_or_logger(self) -> None:
        plugin = ObservabilityPlugin()
        plugin.before_run({})
        plugin.after_run({})
        plugin.before_step({}, {})
        plugin.after_step({}, {})
        plugin.on_error({}, {}, "error")
        plugin.on_validation({}, "blocked")


if __name__ == "__main__":
    unittest.main()
