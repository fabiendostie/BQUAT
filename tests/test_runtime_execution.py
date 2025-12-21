import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import (
    execution,  # noqa: E402
    models,  # noqa: E402
    storage,  # noqa: E402
)
from runtime.providers.registry import MockProvider  # noqa: E402


class RuntimeExecutionTests(unittest.TestCase):
    def test_plan_executor_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = storage.init_run_dir(Path(tmpdir), "run-1")
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
            executor.execute({}, {"run_dir": run_dir, "manifest": manifest})
            self.assertTrue((run_dir / "plan.json").exists())
            self.assertTrue((run_dir / "response.json").exists())


if __name__ == "__main__":
    unittest.main()
