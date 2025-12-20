import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import engine  # noqa: E402
from runtime import models  # noqa: E402


class FlakyExecutor(engine.StepExecutor):
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, step: dict, context: dict) -> None:
        self.calls += 1
        if self.calls == 1:
            raise ValueError("boom")


class FailingExecutor(engine.StepExecutor):
    def execute(self, step: dict, context: dict) -> None:
        raise RuntimeError("nope")


class RuntimeEngineTests(unittest.TestCase):
    def _config(self, max_retries: int = 0, require_conditional: bool = False) -> dict:
        return {
            "runtime": {
                "storage_root": "runs",
                "max_retries": max_retries,
                "step_timeout_seconds": 5,
            },
            "hitl": {"mode": "blocking", "require_conditional": require_conditional},
        }

    def _spec(self, human_gate: str = "required") -> models.WorkflowSpec:
        return models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            quint="Deduction (L1)",
            telis="Tier 2 shards + progressive negotiation",
            validation="Template/schema validation",
            human=human_gate,
            evidence="L1",
            artifacts=["{output_folder}/prd.md"],
            scope="production",
            path="src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
        )

    def test_blocking_gate_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            spec = self._spec(human_gate="required")
            eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp)
            manifest = eng.run("bmm", "prd")
            self.assertEqual(manifest["status"], "blocked")

            run_id = manifest["run_id"]
            eng.approve_gate(run_id, approved_by="tester")
            resumed = eng.resume(run_id)
            self.assertEqual(resumed["status"], "completed")

    def test_retries_then_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            spec = self._spec(human_gate="optional")
            eng = engine.WorkflowEngine(self._config(max_retries=1), [spec], storage_root=tmp)
            manifest = eng.run("bmm", "prd", executor=FlakyExecutor())
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["steps"][0]["attempts"], 2)

    def test_load_mapping_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            mapping_path = tmp / "integration-mapping.json"
            payload = {
                "records": [
                    {
                        "module": "bmm",
                        "workflow": "prd",
                        "phase": "Phase 2 Planning",
                        "quint": "Deduction (L1)",
                        "telis": "Tier 2 shards + progressive negotiation",
                        "validation": "Template/schema validation",
                        "human": "required",
                        "evidence": "L1",
                        "artifacts": ["{output_folder}/prd.md"],
                        "scope": "production",
                        "path": "src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
                    }
                ]
            }
            mapping_path.write_text(json.dumps(payload), encoding="ascii")
            records = engine.load_mapping_records(mapping_path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].workflow, "prd")

    def test_failure_when_retries_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            spec = self._spec(human_gate="optional")
            eng = engine.WorkflowEngine(self._config(max_retries=0), [spec], storage_root=tmp)
            manifest = eng.run("bmm", "prd", executor=FailingExecutor())
            self.assertEqual(manifest["status"], "failed")

    def test_create_run_and_resume_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            spec = self._spec(human_gate="required")
            eng = engine.WorkflowEngine(self._config(), [spec], storage_root=tmp)
            created = eng.create_run("bmm", "prd")
            run_id = created["run_id"]
            resumed = eng.resume(run_id)
            self.assertEqual(resumed["status"], "blocked")

    def test_default_mapping_path_loads(self) -> None:
        path = engine.default_mapping_path()
        self.assertTrue(path.name == "integration-mapping.json")
        records = engine.load_mapping_records(path)
        self.assertTrue(len(records) >= 1)


if __name__ == "__main__":
    unittest.main()
