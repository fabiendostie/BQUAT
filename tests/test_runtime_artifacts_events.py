import hashlib
import unittest
from pathlib import Path
from uuid import uuid4

from runtime import engine, models, storage
from runtime.quint import store

ROOT = Path(__file__).resolve().parents[1]


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class WritingExecutor(engine.StepExecutor):
    def __init__(self, filename: str, content: str) -> None:
        self.filename = filename
        self.content = content

    def execute(self, step: dict, context: dict) -> None:
        run_dir = Path(context["run_dir"])
        (run_dir / self.filename).write_text(self.content, encoding="utf-8")
        step["outputs"] = [self.filename]


class RuntimeArtifactEventTests(unittest.TestCase):
    def _config(self) -> dict:
        return {
            "runtime": {
                "storage_root": "runs",
                "max_retries": 0,
                "step_timeout_seconds": 5,
            },
            "automation": {"override": True},
            "hitl": {"mode": "disabled", "require_conditional": False},
        }

    def test_artifact_index_and_events_recorded(self) -> None:
        tmp = _sandbox_root()
        spec = models.WorkflowSpec(
            module="bmm",
            workflow="artifact-test",
            phase="Phase 2 Planning",
            quint="Deduction (L1)",
            telis="Tier 2 shards + progressive negotiation",
            validation="Template/schema validation",
            human="optional",
            evidence="L1",
            artifacts=["{output_folder}/artifact.txt"],
            scope="production",
            path="src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
        )
        eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp)
        created = eng.create_run("bmm", "artifact-test")
        run_dir = tmp / created["run_id"]
        step_spec = models.StepSpec(
            id="step-1",
            name="write",
            description="",
            phase=spec.phase,
            inputs={},
            outputs=["{output_folder}/artifact.txt"],
            templates=[],
            tools=[],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)
        gate = models.HumanGate(
            gate_id="bmm:artifact-test:hitl",
            status="approved",
            required=True,
            approved_by="tester",
            approved_at="2025-12-30T00:00:00-05:00",
            notes="ok",
            phase=spec.phase,
            workflow="bmm/artifact-test",
            reason="explicit human gate",
            recorded_at="2025-12-30T00:00:00-05:00",
        )
        storage.write_human_gates(run_dir, {"gates": [gate.to_dict()]})

        executor = WritingExecutor("artifact.txt", "hello")
        result = eng.run("bmm", "artifact-test", run_id=created["run_id"], executor=executor)
        self.assertEqual(result["status"], "completed")

        artifacts = storage.read_artifact_index(run_dir)
        self.assertEqual(len(artifacts["artifacts"]), 1)
        record = artifacts["artifacts"][0]
        self.assertEqual(record["artifact_type"], "output")
        self.assertTrue(record["path"].endswith("artifact.txt"))
        expected_checksum = hashlib.sha256(b"hello").hexdigest()
        self.assertEqual(record["checksum"], expected_checksum)
        self.assertEqual(record["metadata"]["gate"]["gate_id"], "bmm:artifact-test:hitl")
        self.assertEqual(record["metadata"]["gate"]["status"], "approved")

        events = storage.read_events(run_dir)["events"]
        event_types = {event.get("event_type") for event in events}
        self.assertIn("WorkflowStarted", event_types)
        self.assertIn("WorkflowStepStarted", event_types)
        self.assertIn("WorkflowStepCompleted", event_types)
        self.assertIn("WorkflowCompleted", event_types)

        evidence = store.EvidenceStore(run_dir)
        link = models.EvidenceLink(
            id="ev-123",
            claim="artifact captured",
            level="L1",
            source="unit-test",
            date="2025-12-30T00:00:00-05:00",
            valid_until="2025-12-31T00:00:00-05:00",
            congruence="CL1",
            reliability=0.5,
            wlnk=0.5,
            carrier_ref="artifact.txt",
            artifacts=[record["path"]],
            notes="",
        )
        evidence.record(link)
        updated = storage.read_artifact_index(run_dir)["artifacts"][0]
        self.assertIn("ev-123", updated["metadata"]["evidence_ids"])

        timeline = storage.read_timeline(run_dir)["entries"]
        timeline_types = {entry.get("type") for entry in timeline}
        self.assertIn("event", timeline_types)
        self.assertIn("artifact", timeline_types)
        self.assertIn("gate", timeline_types)
        self.assertIn("evidence", timeline_types)


if __name__ == "__main__":
    unittest.main()
