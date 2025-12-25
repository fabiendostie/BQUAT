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
            if not record.artifacts:
                continue
            for artifact in record.artifacts:
                self.assertFalse(artifact.startswith("implicit:"))
                self.assertFalse(artifact.startswith("schema:"))

    def test_prd_output_present(self) -> None:
        target = None
        for record in self.records:
            if "/bmm/workflows/2-plan-workflows/prd/" in record.path:
                target = record
                break
        self.assertIsNotNone(target, "PRD workflow mapping not found")
        self.assertTrue(any("prd.md" in artifact for artifact in target.artifacts))

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

    def test_default_output_file_captured(self) -> None:
        target = None
        for record in self.records:
            if "/cis/workflows/innovation-strategy/" in record.path:
                target = record
                break
        self.assertIsNotNone(target, "Innovation strategy workflow mapping not found")
        self.assertTrue(
            any("innovation-strategy" in artifact for artifact in target.artifacts),
            "default_output_file not captured for innovation-strategy",
        )

    def test_artifacts_exclude_bracket_placeholders(self) -> None:
        for record in self.records:
            for artifact in record.artifacts:
                self.assertFalse(artifact.startswith("[") and artifact.endswith("]"))

    def test_records_sorted_by_path(self) -> None:
        paths = [record.path for record in self.records]
        self.assertEqual(paths, sorted(paths))

    def test_registry_sorted_by_path(self) -> None:
        paths = [record.path for record in self.registry]
        self.assertEqual(paths, sorted(paths))

    def test_artifacts_sorted(self) -> None:
        for record in self.records:
            self.assertEqual(record.artifacts, sorted(record.artifacts))


if __name__ == "__main__":
    unittest.main()
