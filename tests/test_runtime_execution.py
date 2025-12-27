import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (
    execution,  # noqa: E402
    models,  # noqa: E402
    storage,  # noqa: E402
)
from runtime.providers.registry import MockProvider  # noqa: E402


class RuntimeExecutionTests(unittest.TestCase):
    def _sandbox_root(self) -> Path:
        root = ROOT / "runs" / "tmp-tests" / uuid4().hex
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_plan_executor_writes_outputs(self) -> None:
        run_dir = storage.init_run_dir(self._sandbox_root(), "run-1")
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
        manifest = {"workflow": spec.to_dict()}
        executor = execution.PlanExecutor("bmad", MockProvider("mock"))
        step = {}
        executor.execute(step, {"run_dir": run_dir, "manifest": manifest})
        self.assertTrue((run_dir / "plan.json").exists())
        self.assertTrue((run_dir / "response.json").exists())
        self.assertIn("plan.json", step.get("outputs", []))
        self.assertIn("response.json", step.get("outputs", []))

    def test_plan_executor_appends_telis_context(self) -> None:
        run_dir = storage.init_run_dir(self._sandbox_root(), "run-2")
        spec = models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            quint="Deduction (L1)",
            telis="Tier 1 minimal",
            validation="Template/schema validation",
            human="required",
            evidence="L1",
            artifacts=["{output_folder}/prd.md"],
            scope="production",
            path="src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
        )
        manifest = {"workflow": spec.to_dict()}
        executor = execution.PlanExecutor("bmad", None)
        step = {}
        telis_context = {"context": "async def main()", "source": "shards"}
        executor.execute(
            step,
            {"run_dir": run_dir, "manifest": manifest, "telis_context": telis_context},
        )
        plan = storage.read_json(run_dir / "plan.json")
        self.assertIn("TELIS context", plan.get("prompt", ""))
        self.assertEqual(plan.get("telis_context"), telis_context)


if __name__ == "__main__":
    unittest.main()
