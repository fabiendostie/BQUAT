import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models, storage  # noqa: E402
from runtime.tools.base import ToolSpec  # noqa: E402
from runtime.tools.pipeline import (  # noqa: E402
    ToolApprovalRequired,
    ToolDefinition,
    ToolExecutionError,
    run_tool_calls,
)


def _step_spec(tools: list[dict]) -> models.StepSpec:
    return models.StepSpec(
        id="step-1",
        name="pipeline-test",
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


def _registry() -> dict[str, ToolDefinition]:
    spec = ToolSpec(
        name="echo",
        description="echo tool",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        risk="high",
    ).to_dict()

    def handler(args: dict, _ctx) -> dict:
        return {"echo": args["value"]}

    return {"echo": ToolDefinition(spec=spec, handler=handler)}


class RuntimeToolPipelineTests(unittest.TestCase):
    def test_allowlist_blocks_required_tool(self) -> None:
        run_dir = storage.init_run_dir(ROOT / "runs" / "tmp-tests", "run-tool-1")
        spec = _step_spec([{"name": "echo", "args": {"value": "hi"}, "required": True}])
        config = {"tools": {"allowlist": ["other"], "blocklist": []}}
        with self.assertRaises(ToolExecutionError):
            run_tool_calls(
                step={"step_id": "step-1"},
                step_spec=spec,
                manifest={"run_id": "run-tool-1"},
                run_dir=run_dir,
                config=config,
                registry=_registry(),
            )
        payload = storage.read_tool_results(run_dir)
        self.assertEqual(payload["results"][0]["status"], "blocked")

    def test_high_risk_requires_approval(self) -> None:
        run_dir = storage.init_run_dir(ROOT / "runs" / "tmp-tests", "run-tool-2")
        spec = _step_spec([{"name": "echo", "args": {"value": "hi"}, "required": True}])
        config = {"tools": {"allowlist": ["echo"], "risk_policy": {"high_requires_approval": True}}}
        with self.assertRaises(ToolApprovalRequired):
            run_tool_calls(
                step={"step_id": "step-1"},
                step_spec=spec,
                manifest={"run_id": "run-tool-2"},
                run_dir=run_dir,
                config=config,
                registry=_registry(),
            )
        payload = storage.read_tool_results(run_dir)
        self.assertEqual(payload["results"][0]["status"], "blocked")

    def test_tool_execution_records_result(self) -> None:
        run_dir = storage.init_run_dir(ROOT / "runs" / "tmp-tests", "run-tool-3")
        spec = _step_spec([{"name": "echo", "args": {"value": "ok"}, "required": True}])
        gate_id = "tool:echo:step-1"
        storage.write_approvals(
            run_dir,
            {
                "approvals": [
                    {"gate_id": gate_id, "approved_by": "tester", "approved_at": "now", "notes": ""}
                ]
            },
        )
        config = {"tools": {"allowlist": ["echo"], "risk_policy": {"high_requires_approval": True}}}
        results = run_tool_calls(
            step={"step_id": "step-1"},
            step_spec=spec,
            manifest={"run_id": "run-tool-3"},
            run_dir=run_dir,
            config=config,
            registry=_registry(),
        )
        self.assertEqual(results[0].status, "completed")
        payload = storage.read_tool_results(run_dir)
        self.assertEqual(payload["results"][0]["result"]["echo"], "ok")


if __name__ == "__main__":
    unittest.main()
