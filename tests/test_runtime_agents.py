import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import agents  # noqa: E402
from runtime import models  # noqa: E402
from runtime import prompts  # noqa: E402


class RuntimeAgentTests(unittest.TestCase):
    def _spec(self) -> models.WorkflowSpec:
        return models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2 Planning",
            quint="Deduction (L1)",
            telis="Tier 2 shards + progressive negotiation",
            validation="Template/schema validation",
            human="required",
            evidence="L1",
            artifacts=["{output_folder}/prd.md", "template:prd-template.md"],
            scope="production",
            path="src/modules/bmm/workflows/2-plan-workflows/prd/workflow.md",
        )

    def test_split_artifacts(self) -> None:
        outputs, templates = agents.split_artifacts(
            ["{output_folder}/a.md", "template:tmpl.md"]
        )
        self.assertEqual(outputs, ["{output_folder}/a.md"])
        self.assertEqual(templates, ["tmpl.md"])

    def test_prompt_render_safe(self) -> None:
        template = "Hello {name} {missing}"
        rendered = prompts.render_prompt(template, {"name": "world"})
        self.assertEqual(rendered, "Hello world {missing}")

    def test_agent_plan_outputs(self) -> None:
        spec = self._spec()
        agent = agents.get_agent("bmad")
        plan = agent.build_plan(spec)
        self.assertEqual(plan.outputs, ["{output_folder}/prd.md"])
        self.assertEqual(plan.templates, ["prd-template.md"])
        self.assertIn("prd", plan.prompt)

    def test_agent_lookup_failure(self) -> None:
        with self.assertRaises(KeyError):
            agents.get_agent("unknown")


if __name__ == "__main__":
    unittest.main()
