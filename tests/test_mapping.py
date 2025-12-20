import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "methodology" / "tools"
sys.path.insert(0, str(TOOLS))

import mapping  # noqa: E402


class MappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bmad_root = ROOT / "BMAD-METHOD"
        cls.records = mapping.generate_mapping_records(cls.bmad_root)
        cls.registry = mapping.generate_registry_workflows(cls.bmad_root)

    def test_only_production_records(self) -> None:
        self.assertTrue(self.records, "No mapping records generated")
        for record in self.records:
            self.assertEqual(record.scope, "production")

    def test_artifacts_only_explicit_or_templates(self) -> None:
        for record in self.records:
            if record.artifacts == "none":
                continue
            self.assertNotIn("implicit:", record.artifacts)
            self.assertNotIn("schema:", record.artifacts)

    def test_prd_output_present(self) -> None:
        target = None
        for record in self.records:
            if "/bmm/workflows/2-plan-workflows/prd/" in record.path:
                target = record
                break
        self.assertIsNotNone(target, "PRD workflow mapping not found")
        self.assertIn("prd.md", target.artifacts)

    def test_human_gate_planning_required(self) -> None:
        target = None
        for record in self.records:
            if "/bmm/workflows/2-plan-workflows/prd/" in record.path:
                target = record
                break
        self.assertIsNotNone(target, "PRD workflow mapping not found")
        self.assertEqual(target.human, "required")

    def test_registry_excludes_sample_reference(self) -> None:
        self.assertTrue(self.registry, "No registry records generated")
        for record in self.registry:
            self.assertEqual(record.scope, "production")
            self.assertNotIn("sample-custom-modules", record.path)
            self.assertNotIn("reference", record.path)


if __name__ == "__main__":
    unittest.main()
