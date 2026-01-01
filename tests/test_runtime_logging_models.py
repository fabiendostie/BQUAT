from __future__ import annotations

import unittest

from runtime.logging.models import EmittedEvent, LogRecord, RunReport, RunReportSummary


class LogRecordTests(unittest.TestCase):
    def test_to_dict(self) -> None:
        record = LogRecord(
            level="info",
            category="run",
            message="workflow started",
            timestamp="2025-01-01T12:00:00-05:00",
            run_id="run-123",
            step_id=None,
            payload={"workflow": "test"},
        )
        data = record.to_dict()
        self.assertEqual(data["level"], "info")
        self.assertEqual(data["category"], "run")
        self.assertEqual(data["message"], "workflow started")
        self.assertEqual(data["timestamp"], "2025-01-01T12:00:00-05:00")
        self.assertEqual(data["run_id"], "run-123")
        self.assertIsNone(data["step_id"])
        self.assertEqual(data["payload"], {"workflow": "test"})

    def test_from_dict(self) -> None:
        data = {
            "level": "error",
            "category": "step",
            "message": "step failed",
            "timestamp": "2025-01-01T12:05:00-05:00",
            "run_id": "run-456",
            "step_id": "step-01",
            "payload": {"error": "timeout"},
        }
        record = LogRecord.from_dict(data)
        self.assertEqual(record.level, "error")
        self.assertEqual(record.category, "step")
        self.assertEqual(record.message, "step failed")
        self.assertEqual(record.step_id, "step-01")
        self.assertEqual(record.payload, {"error": "timeout"})

    def test_round_trip(self) -> None:
        original = LogRecord(
            level="warn",
            category="gate",
            message="gate blocked",
            timestamp="2025-01-01T12:10:00-05:00",
            run_id="run-789",
            step_id="step-02",
            payload={"gate_id": "gate-01"},
        )
        data = original.to_dict()
        restored = LogRecord.from_dict(data)
        self.assertEqual(original, restored)

    def test_frozen(self) -> None:
        record = LogRecord(
            level="info",
            category="run",
            message="test",
            timestamp="2025-01-01T12:00:00-05:00",
        )
        with self.assertRaises(AttributeError):
            record.level = "error"  # type: ignore[misc]

    def test_defaults(self) -> None:
        record = LogRecord(
            level="info",
            category="run",
            message="test",
            timestamp="2025-01-01T12:00:00-05:00",
        )
        self.assertIsNone(record.run_id)
        self.assertIsNone(record.step_id)
        self.assertEqual(record.payload, {})


class EmittedEventTests(unittest.TestCase):
    def test_to_dict(self) -> None:
        event = EmittedEvent(
            event_type="run.started",
            timestamp="2025-01-01T12:00:00-05:00",
            run_id="run-123",
            source="engine",
            payload={"workflow": "test"},
            step_id=None,
        )
        data = event.to_dict()
        self.assertEqual(data["event_type"], "run.started")
        self.assertEqual(data["source"], "engine")
        self.assertEqual(data["run_id"], "run-123")

    def test_from_dict(self) -> None:
        data = {
            "event_type": "step.completed",
            "timestamp": "2025-01-01T12:05:00-05:00",
            "run_id": "run-456",
            "source": "step",
            "payload": {"outputs": []},
            "step_id": "step-01",
        }
        event = EmittedEvent.from_dict(data)
        self.assertEqual(event.event_type, "step.completed")
        self.assertEqual(event.step_id, "step-01")

    def test_round_trip(self) -> None:
        original = EmittedEvent(
            event_type="gate.approved",
            timestamp="2025-01-01T12:10:00-05:00",
            run_id="run-789",
            source="gate",
            payload={"approved_by": "user"},
        )
        data = original.to_dict()
        restored = EmittedEvent.from_dict(data)
        self.assertEqual(original, restored)


class RunReportSummaryTests(unittest.TestCase):
    def test_to_dict(self) -> None:
        summary = RunReportSummary(
            run_id="run-123",
            status="completed",
            workflow_id="bmm/prd",
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            started_at="2025-01-01T12:00:00-05:00",
            completed_at="2025-01-01T12:05:00-05:00",
            duration_seconds=300.0,
            steps_total=3,
            steps_completed=3,
            steps_failed=0,
            gates_total=1,
            gates_approved=1,
            gates_blocked=0,
            evidence_count=2,
            artifacts_count=5,
            validation_passed=3,
            validation_failed=0,
            guardrail_violations=0,
        )
        data = summary.to_dict()
        self.assertEqual(data["run_id"], "run-123")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["duration_seconds"], 300.0)
        self.assertEqual(data["steps_total"], 3)

    def test_from_dict(self) -> None:
        data = {
            "run_id": "run-456",
            "status": "failed",
            "workflow_id": "bmb/ui",
            "module": "bmb",
            "workflow": "ui",
            "phase": "Phase 4 Implementation",
            "started_at": "2025-01-01T12:00:00-05:00",
            "completed_at": "2025-01-01T12:10:00-05:00",
            "duration_seconds": 600.0,
            "steps_total": 5,
            "steps_completed": 3,
            "steps_failed": 2,
            "gates_total": 2,
            "gates_approved": 1,
            "gates_blocked": 1,
            "evidence_count": 1,
            "artifacts_count": 3,
            "validation_passed": 2,
            "validation_failed": 1,
            "guardrail_violations": 2,
        }
        summary = RunReportSummary.from_dict(data)
        self.assertEqual(summary.status, "failed")
        self.assertEqual(summary.steps_failed, 2)
        self.assertEqual(summary.guardrail_violations, 2)

    def test_round_trip(self) -> None:
        original = RunReportSummary(
            run_id="run-789",
            status="blocked",
            workflow_id="core/init",
            module="core",
            workflow="init",
            phase="Phase 2 Design",
            started_at="2025-01-01T12:00:00-05:00",
            completed_at="2025-01-01T12:00:30-05:00",
            duration_seconds=30.0,
            steps_total=1,
            steps_completed=0,
            steps_failed=0,
            gates_total=1,
            gates_approved=0,
            gates_blocked=1,
            evidence_count=0,
            artifacts_count=0,
            validation_passed=0,
            validation_failed=0,
            guardrail_violations=0,
        )
        data = original.to_dict()
        restored = RunReportSummary.from_dict(data)
        self.assertEqual(original, restored)


class RunReportTests(unittest.TestCase):
    def _make_summary(self) -> RunReportSummary:
        return RunReportSummary(
            run_id="run-123",
            status="completed",
            workflow_id="bmm/prd",
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            started_at="2025-01-01T12:00:00-05:00",
            completed_at="2025-01-01T12:05:00-05:00",
            duration_seconds=300.0,
            steps_total=1,
            steps_completed=1,
            steps_failed=0,
            gates_total=0,
            gates_approved=0,
            gates_blocked=0,
            evidence_count=0,
            artifacts_count=0,
            validation_passed=0,
            validation_failed=0,
            guardrail_violations=0,
        )

    def test_to_dict(self) -> None:
        summary = self._make_summary()
        report = RunReport(
            version="1.0",
            generated_at="2025-01-01T12:10:00-05:00",
            summary=summary,
            events=[{"event_type": "run.started"}],
            logs=[{"level": "info"}],
        )
        data = report.to_dict()
        self.assertEqual(data["version"], "1.0")
        self.assertIsInstance(data["summary"], dict)
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(len(data["logs"]), 1)

    def test_from_dict(self) -> None:
        summary_data = self._make_summary().to_dict()
        data = {
            "version": "1.0",
            "generated_at": "2025-01-01T12:10:00-05:00",
            "summary": summary_data,
            "events": [{"event_type": "run.completed"}],
            "logs": [],
            "artifacts": [{"path": "test.md"}],
            "evidence": [],
            "gates": [],
            "drrs": [],
            "validation_results": [],
            "guardrail_reports": [],
            "timeline": [],
        }
        report = RunReport.from_dict(data)
        self.assertEqual(report.version, "1.0")
        self.assertEqual(report.summary.run_id, "run-123")
        self.assertEqual(len(report.events), 1)
        self.assertEqual(len(report.artifacts), 1)

    def test_round_trip(self) -> None:
        summary = self._make_summary()
        original = RunReport(
            version="1.0",
            generated_at="2025-01-01T12:10:00-05:00",
            summary=summary,
            events=[{"event_type": "test"}],
            logs=[{"level": "debug"}],
            artifacts=[],
            evidence=[],
            gates=[],
            drrs=[],
            validation_results=[],
            guardrail_reports=[],
            timeline=[],
        )
        data = original.to_dict()
        restored = RunReport.from_dict(data)
        self.assertEqual(original.version, restored.version)
        self.assertEqual(original.summary, restored.summary)
        self.assertEqual(original.events, restored.events)

    def test_defaults(self) -> None:
        summary = self._make_summary()
        report = RunReport(
            version="1.0",
            generated_at="2025-01-01T12:10:00-05:00",
            summary=summary,
        )
        self.assertEqual(report.events, [])
        self.assertEqual(report.logs, [])
        self.assertEqual(report.artifacts, [])


if __name__ == "__main__":
    unittest.main()
