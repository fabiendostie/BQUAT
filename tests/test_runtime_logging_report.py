from __future__ import annotations

import json
import unittest
from pathlib import Path
from uuid import uuid4

from runtime import storage
from runtime.logging.report import REPORT_VERSION, RunReportGenerator


class RunReportGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sandbox = Path(__file__).resolve().parent / f"sandbox_{uuid4().hex}"
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.run_id = f"run-{uuid4().hex[:8]}"
        self.run_dir = self.sandbox / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        import shutil

        if self.sandbox.exists():
            shutil.rmtree(self.sandbox)

    def _write_manifest(self, manifest: dict) -> None:
        storage.write_manifest(self.run_dir, manifest)

    def _make_manifest(self, **overrides) -> dict:
        base = {
            "run_id": self.run_id,
            "status": "completed",
            "workflow": {
                "module": "bmm",
                "workflow": "prd",
                "phase": "Phase 2 Planning",
            },
            "steps": [
                {
                    "name": "execute",
                    "step_id": "step-01",
                    "status": "completed",
                }
            ],
            "current_step": 0,
            "created_at": "2025-01-01T12:00:00-05:00",
            "updated_at": "2025-01-01T12:05:00-05:00",
        }
        base.update(overrides)
        return base

    def test_generate_report(self) -> None:
        self._write_manifest(self._make_manifest())
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.version, REPORT_VERSION)
        self.assertIsNotNone(report.generated_at)
        self.assertEqual(report.summary.run_id, self.run_id)
        self.assertEqual(report.summary.status, "completed")

    def test_summary_workflow_info(self) -> None:
        self._write_manifest(self._make_manifest())
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.module, "bmm")
        self.assertEqual(report.summary.workflow, "prd")
        self.assertEqual(report.summary.phase, "Phase 2 Planning")
        self.assertEqual(report.summary.workflow_id, "bmm/prd")

    def test_summary_step_counts(self) -> None:
        manifest = self._make_manifest(
            steps=[
                {"name": "step1", "step_id": "s1", "status": "completed"},
                {"name": "step2", "step_id": "s2", "status": "completed"},
                {"name": "step3", "step_id": "s3", "status": "failed"},
            ]
        )
        self._write_manifest(manifest)
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.steps_total, 3)
        self.assertEqual(report.summary.steps_completed, 2)
        self.assertEqual(report.summary.steps_failed, 1)

    def test_summary_gate_counts(self) -> None:
        self._write_manifest(self._make_manifest())
        storage.write_human_gates(
            self.run_dir,
            {
                "gates": [
                    {"gate_id": "g1", "status": "approved"},
                    {"gate_id": "g2", "status": "blocked"},
                ]
            },
        )
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.gates_total, 2)
        self.assertEqual(report.summary.gates_approved, 1)
        self.assertEqual(report.summary.gates_blocked, 1)

    def test_summary_duration_calculation(self) -> None:
        manifest = self._make_manifest(
            created_at="2025-01-01T12:00:00-05:00",
            updated_at="2025-01-01T12:05:00-05:00",
        )
        self._write_manifest(manifest)
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.duration_seconds, 300.0)

    def test_summary_duration_missing_timestamps(self) -> None:
        manifest = self._make_manifest(created_at="", updated_at="")
        self._write_manifest(manifest)
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.duration_seconds, 0.0)

    def test_summary_validation_counts(self) -> None:
        manifest = self._make_manifest(
            steps=[
                {
                    "name": "s1",
                    "step_id": "s1",
                    "status": "completed",
                    "validation": {"status": "passed"},
                },
                {
                    "name": "s2",
                    "step_id": "s2",
                    "status": "completed",
                    "validation": {"status": "passed"},
                },
                {
                    "name": "s3",
                    "step_id": "s3",
                    "status": "failed",
                    "validation": {"status": "failed"},
                },
            ]
        )
        self._write_manifest(manifest)
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.validation_passed, 2)
        self.assertEqual(report.summary.validation_failed, 1)

    def test_summary_guardrail_violations(self) -> None:
        manifest = self._make_manifest(
            steps=[
                {
                    "name": "s1",
                    "step_id": "s1",
                    "status": "failed",
                    "guardrails": {
                        "inputs": {"status": "failed", "violations": ["pii", "blocked"]},
                    },
                },
                {
                    "name": "s2",
                    "step_id": "s2",
                    "status": "failed",
                    "guardrails": {
                        "outputs": {"status": "failed", "violations": ["dangerous"]},
                    },
                },
            ]
        )
        self._write_manifest(manifest)
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.guardrail_violations, 3)

    def test_summary_evidence_count(self) -> None:
        self._write_manifest(self._make_manifest())
        storage.write_evidence_links(
            self.run_dir,
            {"evidence": [{"id": "e1"}, {"id": "e2"}, {"id": "e3"}]},
        )
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.evidence_count, 3)

    def test_summary_artifacts_count(self) -> None:
        self._write_manifest(self._make_manifest())
        storage.write_artifact_index(
            self.run_dir,
            {"artifacts": [{"path": "a.md"}, {"path": "b.md"}]},
        )
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(report.summary.artifacts_count, 2)

    def test_report_includes_events(self) -> None:
        self._write_manifest(self._make_manifest())
        storage.write_events(
            self.run_dir,
            {"events": [{"event_type": "test"}]},
        )
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(len(report.events), 1)
        self.assertEqual(report.events[0]["event_type"], "test")

    def test_report_includes_logs(self) -> None:
        self._write_manifest(self._make_manifest())
        storage.write_logs(
            self.run_dir,
            {"logs": [{"level": "info", "message": "test"}]},
        )
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(len(report.logs), 1)
        self.assertEqual(report.logs[0]["level"], "info")

    def test_extract_validation_results(self) -> None:
        manifest = self._make_manifest(
            steps=[
                {
                    "name": "step1",
                    "step_id": "s1",
                    "status": "completed",
                    "validation": {"status": "passed", "targets": ["file.py"]},
                }
            ]
        )
        self._write_manifest(manifest)
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(len(report.validation_results), 1)
        self.assertEqual(report.validation_results[0]["step_id"], "s1")
        self.assertEqual(report.validation_results[0]["validation"]["status"], "passed")

    def test_extract_guardrail_reports(self) -> None:
        manifest = self._make_manifest(
            steps=[
                {
                    "name": "step1",
                    "step_id": "s1",
                    "status": "completed",
                    "guardrails": {"inputs": {"status": "passed"}},
                }
            ]
        )
        self._write_manifest(manifest)
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()

        self.assertEqual(len(report.guardrail_reports), 1)
        self.assertEqual(report.guardrail_reports[0]["step_name"], "step1")

    def test_write_report_default_path(self) -> None:
        self._write_manifest(self._make_manifest())
        generator = RunReportGenerator(self.run_dir)
        path = generator.write_report()

        self.assertEqual(path, self.run_dir / "report.json")
        self.assertTrue(path.exists())

        content = json.loads(path.read_text(encoding="ascii"))
        self.assertEqual(content["version"], REPORT_VERSION)

    def test_write_report_custom_path(self) -> None:
        self._write_manifest(self._make_manifest())
        custom_path = self.sandbox / "custom_report.json"
        generator = RunReportGenerator(self.run_dir)
        path = generator.write_report(custom_path)

        self.assertEqual(path, custom_path)
        self.assertTrue(path.exists())

    def test_report_to_dict_serializable(self) -> None:
        self._write_manifest(self._make_manifest())
        generator = RunReportGenerator(self.run_dir)
        report = generator.generate()
        data = report.to_dict()

        serialized = json.dumps(data)
        self.assertIsInstance(serialized, str)


if __name__ == "__main__":
    unittest.main()
