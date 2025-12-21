import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models  # noqa: E402


class RuntimeModelTests(unittest.TestCase):
    def test_run_step_round_trip(self) -> None:
        step = models.RunStep(
            name="plan",
            status="running",
            attempts=2,
            step_id="step-1",
            inputs={"goal": "draft"},
            outputs=["plan.json"],
            tools=["tool-a"],
        )
        data = step.to_dict()
        loaded = models.RunStep.from_dict(data)
        self.assertEqual(loaded.to_dict(), data)

    def test_artifact_index_round_trip(self) -> None:
        record = models.ArtifactRecord(
            artifact_id="artifact-1",
            path="runs/run-1/prd.md",
            artifact_type="output",
            checksum="abc123",
            workflow="bmm/prd",
            created_at="2025-12-21T11:45:11-05:00",
            step="step-1",
        )
        index = models.ArtifactIndex(
            run_id="run-1", artifacts=[record], updated_at="2025-12-21T11:45:11-05:00"
        )
        data = index.to_dict()
        loaded = models.ArtifactIndex.from_dict(data)
        self.assertEqual(loaded.to_dict(), data)

    def test_evidence_link_round_trip(self) -> None:
        link = models.EvidenceLink(
            id="ev-1",
            claim="Claim",
            level="L1",
            source="test",
            date="2025-12-21T11:45:11-05:00",
            valid_until="2025-12-21T11:45:11-05:00",
            congruence="CL2",
            reliability=0.9,
            wlnk=0.9,
            carrier_ref="runs/run-1/prd.md",
            artifacts=["runs/run-1/prd.md"],
            notes="ok",
        )
        data = link.to_dict()
        loaded = models.EvidenceLink.from_dict(data)
        self.assertEqual(loaded.to_dict(), data)

    def test_human_gate_round_trip(self) -> None:
        gate = models.HumanGate(
            gate_id="bmm:prd:hitl",
            status="approved",
            required=True,
            approved_by="tester",
            approved_at="2025-12-21T11:45:11-05:00",
            notes="ok",
        )
        data = gate.to_dict()
        loaded = models.HumanGate.from_dict(data)
        self.assertEqual(loaded.to_dict(), data)

    def test_event_record_round_trip(self) -> None:
        event = models.EventRecord(
            event_type="WorkflowStarted",
            run_id="run-1",
            timestamp="2025-12-21T11:45:11-05:00",
            payload={"workflow": "bmm/prd"},
            step_id=None,
        )
        data = event.to_dict()
        loaded = models.EventRecord.from_dict(data)
        self.assertEqual(loaded.to_dict(), data)

    def test_run_manifest_round_trip(self) -> None:
        spec = models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            quint="Deduction (L1)",
            telis="Tier 2 shards + progressive negotiation",
            validation="Template/schema validation",
            human="required",
            evidence="L1",
            artifacts=["{output_folder}/prd.md"],
            scope="production",
            path="src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
        )
        manifest = models.RunManifest(
            run_id="run-1",
            workflow=spec,
            status="pending",
            steps=[models.RunStep(name="execute")],
            current_step=0,
            created_at="2025-12-21T11:45:11-05:00",
            updated_at="2025-12-21T11:45:11-05:00",
        )
        data = manifest.to_dict()
        loaded = models.RunManifest.from_dict(data)
        self.assertEqual(loaded.to_dict(), data)


if __name__ == "__main__":
    unittest.main()
