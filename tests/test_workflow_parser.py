import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import workflow_parser  # noqa: E402


class WorkflowParserTests(unittest.TestCase):
    def test_parse_steps_from_step_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wf_dir = root / "wf"
            steps_dir = wf_dir / "steps"
            steps_dir.mkdir(parents=True, exist_ok=True)

            (steps_dir / "step-01-init.md").write_text(
                """---
name: step-01-init
description: Init step
---
# Step 1: Init
""",
                encoding="ascii",
            )
            (steps_dir / "step-01b-continue.md").write_text(
                """---
name: step-01b-continue
description: Continue step
---
# Step 1b: Continue
""",
                encoding="ascii",
            )
            workflow_path = wf_dir / "workflow.md"
            workflow_path.write_text("# Workflow", encoding="ascii")

            steps = workflow_parser.parse_workflow_steps(workflow_path)
            self.assertEqual(len(steps), 2)
            self.assertEqual(steps[0].id, "step-01-init")
            self.assertEqual(steps[0].name, "step-01-init")
            self.assertEqual(steps[0].description, "Init step")
            self.assertEqual(steps[1].id, "step-01b-continue")

    def test_parse_steps_from_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wf_dir = root / "wf"
            wf_dir.mkdir(parents=True, exist_ok=True)
            instructions = wf_dir / "instructions.md"
            instructions.write_text(
                """<step n=\"1\" goal=\"First step\"></step>
<step n=\"2\" title=\"Second step\"></step>
<step n=\"3\" goal=\"Third step\" id=\"step_3\"></step>
""",
                encoding="ascii",
            )
            workflow_yaml = wf_dir / "workflow.yaml"
            workflow_yaml.write_text(
                "instructions: '{installed_path}/instructions.md'",
                encoding="ascii",
            )

            steps = workflow_parser.parse_workflow_steps(workflow_yaml)
            self.assertEqual(len(steps), 3)
            self.assertEqual(steps[0].id, "step-1")
            self.assertEqual(steps[0].name, "First step")
            self.assertEqual(steps[1].id, "step-2")
            self.assertEqual(steps[1].name, "Second step")
            self.assertEqual(steps[2].id, "step_3")

    def test_parse_steps_disambiguates_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wf_dir = root / "wf"
            wf_dir.mkdir(parents=True, exist_ok=True)
            instructions = wf_dir / "instructions.md"
            instructions.write_text(
                """<step n="1" goal="First"></step>
<step n="1" goal="Second"></step>
<step n="1" goal="Third"></step>
""",
                encoding="ascii",
            )
            workflow_yaml = wf_dir / "workflow.yaml"
            workflow_yaml.write_text(
                "instructions: '{installed_path}/instructions.md'",
                encoding="ascii",
            )

            steps = workflow_parser.parse_workflow_steps(workflow_yaml)
            self.assertEqual([step.id for step in steps], ["step-1", "step-1-2", "step-1-3"])

    def test_steps_directory_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wf_dir = root / "wf"
            steps_dir = wf_dir / "steps"
            steps_dir.mkdir(parents=True, exist_ok=True)
            (steps_dir / "step-02-ready.md").write_text(
                """---
name: step-02-ready
description: Ready
---
# Ready
""",
                encoding="ascii",
            )
            instructions = wf_dir / "instructions.md"
            instructions.write_text(
                "<step n=\"99\" goal=\"Ignore me\"></step>", encoding="ascii"
            )
            workflow_yaml = wf_dir / "workflow.yaml"
            workflow_yaml.write_text(
                "instructions: '{installed_path}/instructions.md'",
                encoding="ascii",
            )

            steps = workflow_parser.parse_workflow_steps(workflow_yaml)
            self.assertEqual(len(steps), 1)
            self.assertEqual(steps[0].id, "step-02-ready")

    def test_template_outputs_with_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wf_dir = root / "wf"
            wf_dir.mkdir(parents=True, exist_ok=True)
            instructions = wf_dir / "instructions.md"
            instructions.write_text(
                """<step n="1" goal="First">
<template-output>alpha, beta</template-output>
</step>
<step n="2" goal="Second">
<template-output file="{output_folder}/out.md">gamma = {{gamma}}</template-output>
<template-output file="{default_output_file}">delta</template-output>
</step>
""",
                encoding="ascii",
            )
            workflow_yaml = wf_dir / "workflow.yaml"
            workflow_yaml.write_text(
                "instructions: '{installed_path}/instructions.md'",
                encoding="ascii",
            )

            steps = workflow_parser.parse_workflow_steps(workflow_yaml)
            self.assertEqual(steps[0].inputs.get("template_outputs"), ["alpha", "beta"])
            self.assertNotIn("template_output_files", steps[0].inputs)
            self.assertEqual(steps[1].inputs.get("template_outputs"), ["gamma", "delta"])
            self.assertEqual(
                steps[1].inputs.get("template_output_files", {}).get("gamma"),
                "{output_folder}/out.md",
            )
            self.assertEqual(steps[1].outputs, ["{output_folder}/out.md"])


if __name__ == "__main__":
    unittest.main()
