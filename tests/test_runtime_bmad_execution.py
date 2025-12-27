import unittest
from pathlib import Path
from uuid import uuid4

from runtime import engine

ROOT = Path(__file__).resolve().parents[1]


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class RuntimeBmadExecutionTests(unittest.TestCase):
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

    def _select_workflow(self, records: list[engine.models.WorkflowSpec], module: str) -> tuple:
        config = self._config()
        for spec in records:
            if spec.module != module:
                continue
            workflow_path = engine._workflow_path(spec)
            if not workflow_path or not workflow_path.exists():
                continue
            step_specs = engine._step_specs_for_workflow(spec, config)
            if step_specs:
                return spec, step_specs
        self.fail(f"No workflow steps found for module {module}")

    def test_run_one_workflow_per_module(self) -> None:
        config = self._config()
        records = engine.load_mapping_records()
        modules = sorted({spec.module for spec in records})
        selections = {module: self._select_workflow(records, module) for module in modules}

        tmp = _sandbox_root()
        eng = engine.WorkflowEngine(config, records, storage_root=tmp)
        for module, (spec, expected_steps) in selections.items():
            manifest = eng.run(spec.module, spec.workflow)
            self.assertEqual(manifest["status"], "completed", msg=f"{module} did not complete")
            self.assertEqual(len(manifest["step_specs"]), len(expected_steps))
            self.assertEqual(len(manifest["steps"]), len(expected_steps))
            for step, spec_step in zip(manifest["steps"], expected_steps):
                self.assertEqual(step.get("step_id"), spec_step.id)


if __name__ == "__main__":
    unittest.main()
