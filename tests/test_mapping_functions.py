import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "methodology" / "tools"
sys.path.insert(0, str(TOOLS))

import mapping  # noqa: E402


class MappingFunctionTests(unittest.TestCase):
    def test_module_from_path(self) -> None:
        self.assertEqual(mapping.module_from_path(Path("src/modules/bmm/foo")), "bmm")
        self.assertEqual(mapping.module_from_path(Path("src/core/agents")), "core")
        self.assertEqual(
            mapping.module_from_path(Path("docs/sample-custom-modules/foo")),
            "sample",
        )

    def test_classify_scope(self) -> None:
        self.assertEqual(mapping.classify_scope(Path("test/fixtures/a")), "test")
        self.assertEqual(
            mapping.classify_scope(Path("docs/sample-custom-modules/a")),
            "sample",
        )
        self.assertEqual(mapping.classify_scope(Path("reference/a")), "reference")
        self.assertEqual(mapping.classify_scope(Path("src/modules/bmm/a")), "production")

    def test_phase_from_path(self) -> None:
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/1-analysis/x", "bmm"),
            "Phase 1 Analysis",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/2-plan-workflows/x", "bmm"),
            "Phase 2 Planning",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/3-solutioning/x", "bmm"),
            "Phase 3 Solutioning",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/4-implementation/x", "bmm"),
            "Phase 4 Implementation",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/testarch/x", "bmm"),
            "Testing/QA",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/bmad-quick-flow/x", "bmm"),
            "Quick Flow",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/document-project/x", "bmm"),
            "Phase 0 Documentation",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/generate-project-context/x", "bmm"),
            "Context Generation",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/excalidraw-diagrams/x", "bmm"),
            "Diagramming",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmm/workflows/workflow-status/x", "bmm"),
            "Meta",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmgd/workflows/1-preproduction/x", "bmgd"),
            "Phase 1 Preproduction",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmgd/workflows/2-design/x", "bmgd"),
            "Phase 2 Design",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmgd/workflows/3-technical/x", "bmgd"),
            "Phase 3 Technical",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmgd/workflows/4-production/x", "bmgd"),
            "Phase 4 Production",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmgd/workflows/gametest/x", "bmgd"),
            "Testing/QA",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmgd/workflows/bmgd-quick-flow/x", "bmgd"),
            "Quick Flow",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmgd/workflows/workflow-status/x", "bmgd"),
            "Meta",
        )
        self.assertEqual(
            mapping.phase_from_path("src/modules/bmb/workflows-legacy/x", "bmb"),
            "Builder Legacy",
        )
        self.assertEqual(mapping.phase_from_path("src/modules/bmb/workflows/x", "bmb"), "Builder")
        self.assertEqual(mapping.phase_from_path("src/modules/cis/workflows/x", "cis"), "CIS")
        self.assertEqual(
            mapping.phase_from_path("src/core/workflows/party-mode/workflow.md", "core"),
            "Meta",
        )
        self.assertEqual(mapping.phase_from_path("src/core/workflows/x", "core"), "Core")

    def test_quint_telis_validation(self) -> None:
        self.assertEqual(mapping.quint_checkpoint("Phase 1 Analysis"), "Abduction (L0)")
        self.assertEqual(mapping.quint_checkpoint("Phase 2 Planning"), "Deduction (L1)")
        self.assertEqual(mapping.quint_checkpoint("Phase 4 Implementation"), "Induction (L2)")
        self.assertEqual(mapping.quint_checkpoint("Phase 0 Documentation"), "Observation (L0)")
        self.assertEqual(mapping.quint_checkpoint("Meta"), "Audit/Decision")
        self.assertEqual(mapping.quint_checkpoint("Quick Flow"), "Mixed (ADI compressed)")

        self.assertEqual(mapping.telis_policy("Phase 1 Analysis"), "Tier 1 minimal, Tier 2 on demand")
        self.assertEqual(mapping.telis_policy("Phase 2 Planning"), "Tier 2 shards + progressive negotiation")
        self.assertEqual(mapping.telis_policy("Phase 4 Implementation"), "LSP-first + Tier 2 + validation gate")
        self.assertEqual(mapping.telis_policy("Meta"), "Tier 1 minimal")

        self.assertEqual(mapping.validation_gate("Phase 4 Implementation"), "AST + type + lint (as applicable)")
        self.assertEqual(mapping.validation_gate("Phase 2 Planning"), "Template/schema validation")
        self.assertEqual(mapping.validation_gate("Phase 1 Analysis"), "Format validation")
        self.assertEqual(mapping.validation_gate("Meta"), "N/A")

        self.assertEqual(mapping.evidence_required("Phase 1 Analysis"), "L0")
        self.assertEqual(mapping.evidence_required("Phase 2 Planning"), "L1")
        self.assertEqual(mapping.evidence_required("Phase 4 Implementation"), "L2")
        self.assertEqual(mapping.evidence_required("Quick Flow"), "L1/L2")
        self.assertEqual(mapping.evidence_required("Meta"), "L1")

    def test_human_gate_variants(self) -> None:
        self.assertEqual(mapping.human_gate("Meta", "workflow-status"), "none")
        self.assertEqual(mapping.human_gate("Phase 2 Planning", "prd"), "required")
        self.assertEqual(mapping.human_gate("Phase 4 Implementation", "dev-story"), "conditional")
        self.assertEqual(mapping.human_gate("Phase 4 Implementation", "other"), "optional")
        self.assertEqual(mapping.human_gate("Phase 0 Documentation", "document-project"), "recommended")
        self.assertEqual(mapping.human_gate("Quick Flow", "quick-dev"), "conditional")

    def test_artifact_heuristics(self) -> None:
        self.assertEqual(mapping.artifact_from_workflow("Phase 2 Planning", "prd"), "PRD")
        self.assertEqual(mapping.artifact_from_workflow("Phase 2 Planning", "tech-spec"), "Tech Spec")
        self.assertEqual(mapping.artifact_from_workflow("Phase 2 Planning", "gdd"), "GDD")
        self.assertEqual(mapping.artifact_from_workflow("Phase 3 Solutioning", "create-architecture"), "Architecture")
        self.assertEqual(mapping.artifact_from_workflow("Phase 2 Planning", "create-ux-design"), "UX/Design Artifacts")
        self.assertEqual(mapping.artifact_from_workflow("Phase 4 Implementation", "create-story"), "Story")
        self.assertEqual(mapping.artifact_from_workflow("Phase 4 Implementation", "sprint-planning"), "Sprint Plan/Status")
        self.assertEqual(mapping.artifact_from_workflow("Phase 0 Documentation", "document-project"), "Project Documentation")
        self.assertEqual(mapping.artifact_from_workflow("Phase 1 Analysis", "research"), "Research Brief")
        self.assertEqual(mapping.artifact_from_workflow("Phase 1 Analysis", "brainstorm"), "Idea Set")
        self.assertEqual(mapping.artifact_from_workflow("Testing/QA", "test-design"), "Test Artifacts")
        self.assertEqual(mapping.artifact_from_workflow("Phase 4 Implementation", "code-review"), "Code Review")
        self.assertEqual(mapping.artifact_from_workflow("Phase 4 Implementation", "retrospective"), "Retrospective")
        self.assertEqual(mapping.artifact_from_workflow("Phase 4 Implementation", "correct-course"), "Course Correction Plan")

    def test_extract_outputs_and_artifacts(self) -> None:
        text = """
outputFile: '{output_folder}/prd.md'
outputs:
  - output-a.md
  - output-b.md
"""
        outputs = mapping.extract_outputs(text)
        self.assertIn("{output_folder}/prd.md", outputs)
        self.assertIn("output-a.md", outputs)
        self.assertIn("output-b.md", outputs)

        with tempfile.TemporaryDirectory() as tmpdir:
            wf_dir = Path(tmpdir)
            (wf_dir / "workflow.yaml").write_text("outputFile: '{output_folder}/foo.md'", encoding="ascii")
            (wf_dir / "steps").mkdir()
            (wf_dir / "steps" / "step-01-init.md").write_text(
                "outputFile: '{output_folder}/bar.md'",
                encoding="ascii",
            )
            (wf_dir / "template.md").write_text("", encoding="ascii")
            artifacts = mapping.artifacts_from_workflow_dir(wf_dir)
            self.assertIn("{output_folder}/foo.md", artifacts)
            self.assertIn("{output_folder}/bar.md", artifacts)
            self.assertIn("template:template.md", artifacts)

    def test_write_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            records = [
                mapping.WorkflowRecord(
                    module="core",
                    workflow="workflow-status",
                    phase="Meta",
                    quint="Audit/Decision",
                    telis="Tier 1 minimal",
                    validation="N/A",
                    human="none",
                    evidence="L1",
                    artifacts="none",
                    scope="production",
                    path="src/core/workflows/workflow-status/workflow.yaml",
                )
            ]
            mapping.write_mapping(records, tmp / "mapping.md")
            self.assertTrue((tmp / "mapping.md").exists())

            reg_records = [
                mapping.WorkflowRegistryRecord(
                    module="core",
                    workflow="workflow-status",
                    phase="Meta",
                    definition="workflow.yaml",
                    scope="production",
                    path="src/core/workflows/workflow-status/workflow.yaml",
                )
            ]
            mapping.write_registry_workflows(reg_records, tmp / "registry.md")
            self.assertTrue((tmp / "registry.md").exists())


if __name__ == "__main__":
    unittest.main()
