import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models, schemas  # noqa: E402


def _workflow_spec() -> models.WorkflowSpec:
    return models.WorkflowSpec(
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


class RuntimeSchemaTests(unittest.TestCase):
    def test_run_manifest_schema_valid(self) -> None:
        spec = _workflow_spec()
        step_spec = models.StepSpec(
            id="step-1",
            name="init",
            description="",
            phase=spec.phase,
            inputs={},
            outputs=["{output_folder}/prd.md"],
            templates=[],
            tools=[],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )
        step = models.RunStep(name="init", validation={"status": "passed"})
        manifest = models.RunManifest(
            run_id="run-1",
            workflow=spec,
            status="pending",
            step_specs=[step_spec],
            steps=[step],
            current_step=0,
            created_at="2025-12-25T00:00:00-05:00",
            updated_at="2025-12-25T00:00:00-05:00",
        )
        errors = schemas.validate_schema(schemas.RUN_MANIFEST_SCHEMA, manifest.to_dict())
        self.assertEqual(errors, [])

    def test_event_schema_valid(self) -> None:
        event = models.EventRecord(
            event_type="WorkflowStarted",
            run_id="run-1",
            timestamp="2025-12-25T00:00:00-05:00",
            payload={"workflow": "bmm/prd"},
            step_id=None,
        )
        errors = schemas.validate_schema(schemas.EVENT_RECORD_SCHEMA, event.to_dict())
        self.assertEqual(errors, [])

    def test_run_timeline_schema_valid(self) -> None:
        timeline = {
            "run_id": "run-1",
            "generated_at": "2025-12-25T00:00:00-05:00",
            "entries": [
                {
                    "type": "event",
                    "timestamp": "2025-12-25T00:00:01-05:00",
                    "event_type": "WorkflowStarted",
                }
            ],
        }
        errors = schemas.validate_schema(schemas.RUN_TIMELINE_SCHEMA, timeline)
        self.assertEqual(errors, [])

    def test_missing_required_field_fails(self) -> None:
        bad = {"status": "pending"}
        errors = schemas.validate_schema(schemas.RUN_MANIFEST_SCHEMA, bad)
        self.assertTrue(errors)

    def test_schema_registry_serializes(self) -> None:
        payload = schemas.schema_registry()
        text = json.dumps(payload, sort_keys=True)
        self.assertIn("schemas", text)
        self.assertIn("version", payload)
        self.assertIn("generated_at", payload)


if __name__ == "__main__":
    unittest.main()
