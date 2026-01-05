import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models, storage  # noqa: E402
from runtime.failure.isolation import FailureIsolator, ToolFailureContext  # noqa: E402
from runtime.tools.base import ToolSpec  # noqa: E402
from runtime.tools.pipeline import ToolDefinition, run_tool_calls  # noqa: E402


def _registry_with_flaky(counter: list[int]) -> dict[str, ToolDefinition]:
    spec = ToolSpec(
        name="flaky",
        description="flaky tool",
        parameters={"type": "object", "properties": {}, "required": []},
        risk="low",
    ).to_dict()

    def handler(_args: dict, _ctx) -> dict:
        counter[0] += 1
        if counter[0] == 1:
            raise RuntimeError("boom")
        return {"ok": True}

    return {"flaky": ToolDefinition(spec=spec, handler=handler)}


def _step_spec(tools: list[dict]) -> models.StepSpec:
    return models.StepSpec(
        id="step-1",
        name="failure-isolation",
        description="",
        phase="",
        inputs={},
        outputs=[],
        templates=[],
        tools=tools,
        validation="",
        evidence="",
        human_gate="",
        retries={"max": 0, "backoff_seconds": 0},
    )


class FailureIsolationTests(unittest.TestCase):
    def test_isolator_skips_optional_tool(self) -> None:
        isolator = FailureIsolator({})
        context = ToolFailureContext(
            tool_name="optional",
            step_id="step-1",
            attempt=1,
            error="boom",
            recoverable=False,
            required=False,
        )
        decision = isolator.isolate_tool_failure(context)
        self.assertEqual(decision.action, "skip")

    def test_tool_retry_succeeds(self) -> None:
        counter = [0]
        run_dir = storage.init_run_dir(ROOT / "runs" / "tmp-tests", "run-failure")
        spec = _step_spec([{"name": "flaky", "args": {}, "required": True}])
        config = {"tools": {"allowlist": ["flaky"]}, "failure_isolation": {"tool_retries": 1}}
        results = run_tool_calls(
            step={"step_id": "step-1"},
            step_spec=spec,
            manifest={"run_id": "run-failure"},
            run_dir=run_dir,
            config=config,
            registry=_registry_with_flaky(counter),
        )
        self.assertEqual(results[0].status, "completed")
        self.assertEqual(counter[0], 2)

    def test_impact_escalates_required(self) -> None:
        config = {"failure_isolation": {"isolate_step_failures": False}}
        isolator = FailureIsolator(config)
        manifest = {
            "step_specs": [{"id": "step-1", "tools": [{"name": "tool-a", "required": True}]}]
        }
        report = isolator.analyze_impact("tool-a", "step-1", manifest)
        self.assertEqual(report.impact_level, "workflow")


if __name__ == "__main__":
    unittest.main()
