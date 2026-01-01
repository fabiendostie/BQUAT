"""End-to-end workflow integration tests for WS14.

Tests complete BMAD workflow execution including:
- Human gate blocking and approval flow
- Artifact creation with checksums
- Event emission during workflow
- Run timeline generation
- Report generation at completion
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import engine, models, storage  # noqa: E402
from runtime.logging.report import RunReportGenerator  # noqa: E402
from runtime.plugins.base import Plugin  # noqa: E402
from runtime.providers.registry import MockProvider  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class EventRecordingPlugin(Plugin):
    """Plugin that records all lifecycle events."""

    def __init__(self) -> None:
        self.events: list = []

    def before_run(self, manifest: dict) -> None:
        self.events.append({"type": "before_run", "run_id": manifest.get("run_id")})

    def after_run(self, manifest: dict) -> None:
        self.events.append(
            {
                "type": "after_run",
                "run_id": manifest.get("run_id"),
                "status": manifest.get("status"),
            }
        )

    def before_step(self, step: dict, manifest: dict) -> None:
        self.events.append({"type": "before_step", "step_name": step.get("name")})

    def after_step(self, step: dict, manifest: dict) -> None:
        self.events.append(
            {"type": "after_step", "step_name": step.get("name"), "status": step.get("status")}
        )

    def on_error(self, step: dict, manifest: dict, error: str) -> None:
        self.events.append({"type": "on_error", "step_name": step.get("name"), "error": error})

    def on_validation(self, manifest: dict, status: str) -> None:
        self.events.append({"type": "on_validation", "status": status})


class ArtifactWritingExecutor(engine.StepExecutor):
    """Executor that writes artifacts during step execution."""

    def execute(self, step: dict, context: dict) -> None:
        run_dir = Path(context["run_dir"])
        output_dir = run_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write an artifact file
        artifact_path = output_dir / "result.md"
        artifact_path.write_text("# Result\n\nGenerated content.", encoding="ascii")
        step["outputs"] = [str(artifact_path.relative_to(run_dir))]


class EndToEndWorkflowTests(unittest.TestCase):
    """End-to-end tests for complete workflow lifecycle."""

    def setUp(self) -> None:
        self.sandbox = _sandbox_root()

    def tearDown(self) -> None:
        if self.sandbox.exists():
            shutil.rmtree(self.sandbox, ignore_errors=True)

    def _config(
        self, max_retries: int = 0, hitl_mode: str = "blocking", automation_override: bool = False
    ) -> dict:
        config = {
            "runtime": {
                "storage_root": str(self.sandbox),
                "max_retries": max_retries,
                "step_timeout_seconds": 30,
            },
            "hitl": {"mode": hitl_mode, "require_conditional": False},
            "observability": {
                "enabled": True,
                "logging": {"enabled": True, "level": "info"},
                "events": {"enabled": True},
                "reports": {"auto_generate": True},
            },
        }
        if automation_override:
            config["automation"] = {"override": True}
        return config

    def _spec(
        self, human_gate: str = "required", phase: str = "Phase 4 Implementation"
    ) -> models.WorkflowSpec:
        return models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase=phase,
            quint="Deduction (L1)",
            telis="Tier 1 minimal",
            validation="Template/schema validation",
            human=human_gate,
            evidence="L1",
            artifacts=["{output_folder}/prd.md"],
            scope="production",
            path="src/modules/bmm/workflows/prd/workflow.md",
        )

    def _step_spec(
        self,
        spec: models.WorkflowSpec,
        step_id: str = "step-1",
        name: str = "execute",
        human_gate: str = "optional",
    ) -> models.StepSpec:
        return models.StepSpec(
            id=step_id,
            name=name,
            description="Test step",
            phase=spec.phase,
            inputs={},
            outputs=["{output_folder}/result.md"],
            templates=[],
            tools=[],
            validation="Template/schema validation",
            evidence="L1",
            human_gate=human_gate,
            retries={"max": 0, "backoff_seconds": 0},
        )

    def test_complete_workflow_with_human_gate_approval(self) -> None:
        """Test full workflow: run -> block -> approve -> resume -> complete."""
        spec = self._spec(human_gate="required")
        config = self._config(automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox)

        # Create run and execute - should block on human gate
        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        # Set up step spec with required human gate
        step_spec = self._step_spec(spec, human_gate="required")
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        # Run - should block
        result = eng.run("bmm", "prd", run_id=run_id)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result.get("blocked_reason"), "human_gate")

        # Verify gate is recorded as blocked
        gates_payload = storage.read_human_gates(run_dir)
        self.assertEqual(len(gates_payload.get("gates", [])), 1)
        gate_entry = gates_payload["gates"][0]
        self.assertEqual(gate_entry.get("status"), "blocked")

        # Approve the gate
        eng.approve_gate(run_id, approved_by="tester", notes="Approved for testing")

        # Verify gate is now approved
        gates_payload = storage.read_human_gates(run_dir)
        gate_entry = gates_payload["gates"][0]
        self.assertEqual(gate_entry.get("status"), "approved")
        self.assertEqual(gate_entry.get("approved_by"), "tester")

        # Resume - should complete
        executor = ArtifactWritingExecutor()
        resumed = eng.resume(run_id, executor=executor)
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(len(resumed["steps"]), 1)
        self.assertEqual(resumed["steps"][0]["status"], "completed")

    def test_workflow_emits_events_via_plugin(self) -> None:
        """Test that workflow emits lifecycle events via plugins."""
        spec = self._spec(human_gate="optional")
        config = self._config(automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        plugin = EventRecordingPlugin()
        manager = engine.PluginManager([plugin])
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox, plugins=manager)

        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        step_spec = self._step_spec(spec)
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        result = eng.run("bmm", "prd", run_id=run_id)
        self.assertEqual(result["status"], "completed")

        # Verify events were recorded
        event_types = [e["type"] for e in plugin.events]
        self.assertIn("before_run", event_types)
        self.assertIn("before_step", event_types)
        self.assertIn("after_step", event_types)
        self.assertIn("on_validation", event_types)
        self.assertIn("after_run", event_types)

        # Verify order: before_run should be first, after_run should be last
        self.assertEqual(plugin.events[0]["type"], "before_run")
        self.assertEqual(plugin.events[-1]["type"], "after_run")

    def test_workflow_creates_artifacts_with_checksums(self) -> None:
        """Test that artifacts are indexed with checksums."""
        spec = self._spec(human_gate="optional")
        config = self._config(automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox)

        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        step_spec = self._step_spec(spec)
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        executor = ArtifactWritingExecutor()
        result = eng.run("bmm", "prd", run_id=run_id, executor=executor)
        self.assertEqual(result["status"], "completed")

        # Verify artifacts are indexed
        artifact_index = storage.read_artifact_index(run_dir)
        artifacts = artifact_index.get("artifacts", [])
        self.assertGreaterEqual(len(artifacts), 1)

        # Each artifact should have a checksum
        for artifact in artifacts:
            self.assertIn("checksum", artifact)
            self.assertTrue(len(artifact["checksum"]) > 0)
            self.assertIn("artifact_id", artifact)
            self.assertIn("path", artifact)

    def test_workflow_generates_timeline(self) -> None:
        """Test that workflow generates a run timeline."""
        spec = self._spec(human_gate="optional")
        config = self._config(automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox)

        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        step_spec = self._step_spec(spec)
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        result = eng.run("bmm", "prd", run_id=run_id)
        self.assertEqual(result["status"], "completed")

        # Update timeline explicitly
        storage.update_timeline(run_dir)

        # Verify timeline exists and has entries
        timeline = storage.read_timeline(run_dir)
        self.assertIn("run_id", timeline)
        self.assertIn("entries", timeline)
        entries = timeline.get("entries", [])
        self.assertGreaterEqual(len(entries), 1)

        # Each entry should have type and timestamp
        for entry in entries:
            self.assertIn("type", entry)
            self.assertIn("timestamp", entry)

    def test_workflow_stores_events(self) -> None:
        """Test that workflow stores events to storage."""
        spec = self._spec(human_gate="optional")
        config = self._config(automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox)

        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        step_spec = self._step_spec(spec)
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        result = eng.run("bmm", "prd", run_id=run_id)
        self.assertEqual(result["status"], "completed")

        # Verify events are stored
        events_payload = storage.read_events(run_dir)
        events = events_payload.get("events", [])
        self.assertGreaterEqual(len(events), 1)

        # Each event should have required fields
        for event in events:
            self.assertIn("event_type", event)
            self.assertIn("timestamp", event)

    def test_workflow_generates_report(self) -> None:
        """Test that workflow can generate a comprehensive report."""
        spec = self._spec(human_gate="optional")
        config = self._config(automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox)

        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        step_spec = self._step_spec(spec)
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        executor = ArtifactWritingExecutor()
        result = eng.run("bmm", "prd", run_id=run_id, executor=executor)
        self.assertEqual(result["status"], "completed")

        # Generate report
        generator = RunReportGenerator(run_dir)
        report = generator.generate()

        # Verify report structure
        self.assertIsNotNone(report.summary)
        self.assertEqual(report.summary.run_id, run_id)
        self.assertEqual(report.summary.status, "completed")
        self.assertEqual(report.summary.module, "bmm")
        self.assertEqual(report.summary.workflow, "prd")
        self.assertGreaterEqual(report.summary.steps_total, 1)
        self.assertGreaterEqual(report.summary.steps_completed, 1)

    def test_multi_step_workflow_completion(self) -> None:
        """Test a workflow with multiple steps completes in order."""
        spec = self._spec(human_gate="optional")
        config = self._config(automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox)

        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        # Create multiple step specs
        step_specs = [
            models.StepSpec(
                id="step-1",
                name="analyze",
                description="Analysis step",
                phase=spec.phase,
                inputs={},
                outputs=["{output_folder}/analysis.md"],
                templates=[],
                tools=[],
                validation="Template/schema validation",
                evidence="L0",
                human_gate="optional",
                retries={"max": 0, "backoff_seconds": 0},
            ),
            models.StepSpec(
                id="step-2",
                name="design",
                description="Design step",
                phase=spec.phase,
                inputs={},
                outputs=["{output_folder}/design.md"],
                templates=[],
                tools=[],
                validation="Template/schema validation",
                evidence="L1",
                human_gate="optional",
                retries={"max": 0, "backoff_seconds": 0},
            ),
            models.StepSpec(
                id="step-3",
                name="implement",
                description="Implementation step",
                phase=spec.phase,
                inputs={},
                outputs=["{output_folder}/impl.md"],
                templates=[],
                tools=[],
                validation="Template/schema validation",
                evidence="L2",
                human_gate="optional",
                retries={"max": 0, "backoff_seconds": 0},
            ),
        ]

        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [s.to_dict() for s in step_specs]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        result = eng.run("bmm", "prd", run_id=run_id)
        self.assertEqual(result["status"], "completed")

        # Verify all steps completed
        self.assertEqual(len(result["steps"]), 3)
        for step in result["steps"]:
            self.assertEqual(step["status"], "completed")

        # Verify steps ran in order
        step_names = [s["name"] for s in result["steps"]]
        self.assertEqual(step_names, ["analyze", "design", "implement"])

    def test_workflow_resume_from_failed_step(self) -> None:
        """Test resuming a workflow that failed mid-execution."""
        spec = self._spec(human_gate="optional")
        config = self._config(max_retries=0, automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox)

        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        # Set up steps where first is completed, second pending
        step_specs = [
            models.StepSpec(
                id="step-1",
                name="completed_step",
                description="Already done",
                phase=spec.phase,
                inputs={},
                outputs=["{output_folder}/done.md"],
                templates=[],
                tools=[],
                validation="",
                evidence="",
                human_gate="optional",
                retries={"max": 0, "backoff_seconds": 0},
            ),
            models.StepSpec(
                id="step-2",
                name="pending_step",
                description="To be done",
                phase=spec.phase,
                inputs={},
                outputs=["{output_folder}/pending.md"],
                templates=[],
                tools=[],
                validation="",
                evidence="",
                human_gate="optional",
                retries={"max": 0, "backoff_seconds": 0},
            ),
        ]

        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [s.to_dict() for s in step_specs]
        manifest["steps"] = [
            models.RunStep(name="completed_step", status="completed", step_id="step-1").to_dict(),
            models.RunStep(name="pending_step", status="pending", step_id="step-2").to_dict(),
        ]
        storage.write_manifest(run_dir, manifest)

        # Resume should only execute the pending step
        class StepRecordingExecutor(engine.StepExecutor):
            def __init__(self):
                self.executed_steps = []

            def execute(self, step: dict, context: dict) -> None:
                self.executed_steps.append(step.get("name"))

        executor = StepRecordingExecutor()
        result = eng.resume(run_id, executor=executor)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(executor.executed_steps, ["pending_step"])

    def test_workflow_with_provider_integration(self) -> None:
        """Test workflow execution with a mock provider."""
        from runtime import execution

        spec = self._spec(human_gate="optional")
        config = self._config(automation_override=True)
        config["automation"]["phases"] = [spec.phase]
        eng = engine.WorkflowEngine(config, [spec], storage_root=self.sandbox)

        created = eng.create_run("bmm", "prd")
        run_id = created["run_id"]
        run_dir = self.sandbox / run_id

        step_spec = self._step_spec(spec)
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        # Use PlanExecutor with MockProvider
        provider = MockProvider("test-model")
        executor = execution.PlanExecutor("bmad", provider)
        result = eng.run("bmm", "prd", run_id=run_id, executor=executor)

        self.assertEqual(result["status"], "completed")

        # Verify provider response was stored
        response_path = run_dir / "response.json"
        if response_path.exists():
            import json

            response_data = json.loads(response_path.read_text(encoding="ascii"))
            self.assertIn("content", response_data)
            self.assertIn("[mock:test-model]", response_data["content"])


if __name__ == "__main__":
    unittest.main()
