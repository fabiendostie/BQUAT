"""Integration test for idea -> interactive BMAD -> autonomous delivery."""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cli import interactive as cli_interactive  # noqa: E402
from cli.interactive import InteractiveCLI  # noqa: E402
from runtime import (  # noqa: E402
    engine,
    execution,
    step_executor,  # noqa: E402
    storage,
)
from runtime.providers.base import Provider, ProviderRequest, ProviderResponse  # noqa: E402


class StaticProvider(Provider):
    """Provider that returns a fixed response without questions."""

    def __init__(self, content: str = "ACK") -> None:
        self.content = content

    def invoke(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(content=self.content, raw={"mock": True})


class FixedInput:
    """Input callback that always returns the same response."""

    def __init__(self, response: str) -> None:
        self.response = response

    def __call__(self, prompt: str) -> str:
        return self.response


class ProductExecutor(execution.PlanExecutor):
    """Plan executor that emits a final product artifact."""

    def __init__(self, agent_name: str, provider: Provider, idea: str) -> None:
        super().__init__(agent_name, provider)
        self.idea = idea

    def execute(self, step: dict, context: dict) -> None:
        super().execute(step, context)
        run_dir = Path(context["run_dir"])
        output_dir = run_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        product_path = output_dir / "final-product.txt"
        product_path.write_text(
            f"Final product for idea: {self.idea}\n",
            encoding="ascii",
        )
        outputs = list(step.get("outputs", []))
        output_key = "outputs/final-product.txt"
        if output_key not in outputs:
            outputs.append(output_key)
        step["outputs"] = outputs


class IdeaToProductIntegrationTests(unittest.TestCase):
    """Simulate idea -> interactive BMAD -> autonomous delivery."""

    def setUp(self) -> None:
        self.sandbox = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.config = {
            "runtime": {
                "storage_root": str(self.sandbox),
                "max_retries": 0,
                "step_timeout_seconds": 30,
            },
            "automation": {"override": True},
            "hitl": {"mode": "disabled"},
            "providers": {"default": "mock", "mock": {"type": "mock", "model": "mock"}},
        }
        mapping = engine.load_mapping_records()
        self.engine = engine.WorkflowEngine(self.config, mapping, storage_root=self.sandbox)
        self.idea = "A command-line habit tracker with weekly summaries."
        self.provider = StaticProvider("ACK")
        self.input_cb = FixedInput(self.idea)
        self.cli = InteractiveCLI(
            engine=self.engine,
            provider=self.provider,
            bmad_root=ROOT / "BMAD-METHOD",
            output_callback=lambda _text: None,
            input_callback=self.input_cb,
        )

    def tearDown(self) -> None:
        if self.sandbox.exists():
            shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_idea_to_product_flow(self) -> None:
        workflows = [
            ("core", "brainstorming"),
            ("bmm", "create-product-brief"),
            ("bmm", "prd"),
            ("bmm", "create-ux-design"),
            ("bmm", "create-architecture"),
            ("bmm", "create-epics-and-stories"),
        ]

        original_parse = step_executor.parse_step_file

        def _parse_without_outputs(path: Path):
            content = original_parse(path)
            content.outputs = []
            return content

        with (
            patch.object(step_executor, "parse_step_file", side_effect=_parse_without_outputs),
            patch.object(cli_interactive, "parse_step_file", side_effect=_parse_without_outputs),
        ):
            for module, workflow in workflows:
                run_id = self.cli.run_workflow(module, workflow)
                self.assertIsNotNone(run_id)
                run_dir = self.sandbox / str(run_id)
                self.assertTrue(run_dir.exists())
                manifest_path = run_dir / "manifest.json"
                self.assertTrue(manifest_path.exists())
                workflow_dir = self.cli._find_workflow_dir(module, workflow)
                if workflow_dir and step_executor.find_step_files(workflow_dir):
                    state_path = run_dir / "conversation_state.json"
                    self.assertTrue(state_path.exists())
                    state = storage.read_json(state_path)
                    self.assertTrue(state.get("turns"))

        dev_executor = ProductExecutor("bmad", self.provider, self.idea)
        manifest = self.engine.run(
            "bmm",
            "dev-story",
            executor=dev_executor,
            agent_name="bmad",
        )
        self.assertEqual(manifest.get("status"), "completed")

        dev_run_dir = self.sandbox / manifest["run_id"]
        product_path = dev_run_dir / "outputs" / "final-product.txt"
        self.assertTrue(product_path.exists())
        self.assertIn(self.idea, product_path.read_text(encoding="ascii"))

        artifact_index = storage.read_artifact_index(dev_run_dir)
        artifact_paths = [
            str(item.get("path", "")).replace("\\", "/")
            for item in artifact_index.get("artifacts", [])
        ]
        self.assertTrue(any(path.endswith("outputs/final-product.txt") for path in artifact_paths))


if __name__ == "__main__":
    unittest.main()
