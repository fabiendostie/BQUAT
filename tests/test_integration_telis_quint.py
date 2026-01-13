"""Integration tests for TELIS and QUINT working together through workflows."""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import engine, models, storage  # noqa: E402
from runtime.quint import assurance, store  # noqa: E402
from runtime.telis import BehavioralCache, TelisPolicyEngine, shards  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class RecordingExecutor(engine.StepExecutor):
    """Executor that records TELIS context from each step."""

    def __init__(self) -> None:
        self.contexts: list = []

    def execute(self, step: dict, context: dict) -> None:
        self.contexts.append(context.get("telis_context"))


class TelisQuintIntegrationTests(unittest.TestCase):
    """Integration tests for TELIS policy engine and QUINT evidence store."""

    def setUp(self) -> None:
        self.sandbox = _sandbox_root()

    def tearDown(self) -> None:
        if self.sandbox.exists():
            shutil.rmtree(self.sandbox, ignore_errors=True)

    def _config(self) -> dict:
        return {
            "runtime": {
                "storage_root": str(self.sandbox),
                "max_retries": 0,
                "step_timeout_seconds": 5,
            },
            "hitl": {"mode": "blocking", "require_conditional": False},
            "automation": {"phases": ["Phase 4 Implementation"]},
        }

    def _spec(self, telis_policy: str = "Tier 1 minimal") -> models.WorkflowSpec:
        return models.WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 4 Implementation",
            quint="Deduction (L1)",
            telis=telis_policy,
            validation="Template/schema validation",
            human="optional",
            evidence="L1",
            artifacts=["{output_folder}/prd.md"],
            scope="production",
            path="src/modules/bmm/workflows/prd/workflow.md",
        )

    def _registry(self) -> shards.ShardRegistry:
        registry = shards.ShardRegistry()
        registry.add(
            shards.Shard(
                shard_id="py.syntax",
                language="python",
                version="3.11",
                tier="tier_1_nano",
                topics=["syntax", "async"],
                tokens=40,
                content="async def main(): await task",
            )
        )
        registry.add(
            shards.Shard(
                shard_id="py.types",
                language="python",
                version="3.11",
                tier="tier_2_micro",
                topics=["types", "typing"],
                tokens=80,
                content="from typing import Optional, List, Dict",
            )
        )
        return registry

    def test_telis_context_propagates_through_steps(self) -> None:
        """Test that TELIS context is injected into each step."""
        registry = self._registry()
        telis_engine = TelisPolicyEngine(registry=registry)
        spec = self._spec("Tier 1 minimal")

        eng = engine.WorkflowEngine(
            self._config(), [spec], storage_root=self.sandbox, telis=telis_engine
        )
        created = eng.create_run("bmm", "prd")
        run_dir = self.sandbox / created["run_id"]

        step_spec = models.StepSpec(
            id="step-1",
            name="context",
            description="Test step",
            phase=spec.phase,
            inputs={"telis_query": "async", "telis_language": "python"},
            outputs=["{output_folder}/prd.md"],
            templates=[],
            tools=[],
            validation=spec.validation,
            evidence=spec.evidence,
            human_gate=spec.human,
            retries={"max": 0, "backoff_seconds": 0},
        )

        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        executor = RecordingExecutor()
        result = eng.run("bmm", "prd", run_id=created["run_id"], executor=executor)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(executor.contexts), 1)
        self.assertIsNotNone(executor.contexts[0])
        self.assertIn("async def main", executor.contexts[0].get("context", ""))

    def test_telis_cache_hit_across_steps(self) -> None:
        """Test that TELIS cache is reused across multiple steps with same query."""
        registry = self._registry()
        cache = BehavioralCache(ttl_seconds=60)
        telis_engine = TelisPolicyEngine(registry=registry, cache=cache)
        spec = self._spec("Tier 1 minimal")

        eng = engine.WorkflowEngine(
            self._config(), [spec], storage_root=self.sandbox, telis=telis_engine
        )
        created = eng.create_run("bmm", "prd")
        run_dir = self.sandbox / created["run_id"]

        # Two steps with the same TELIS query
        step1 = models.StepSpec(
            id="step-1",
            name="first",
            description="First step",
            phase=spec.phase,
            inputs={"telis_query": "syntax", "telis_language": "python"},
            outputs=[],
            templates=[],
            tools=[],
            validation="",
            evidence="",
            human_gate="optional",
            retries={"max": 0, "backoff_seconds": 0},
        )
        step2 = models.StepSpec(
            id="step-2",
            name="second",
            description="Second step",
            phase=spec.phase,
            inputs={"telis_query": "syntax", "telis_language": "python"},
            outputs=[],
            templates=[],
            tools=[],
            validation="",
            evidence="",
            human_gate="optional",
            retries={"max": 0, "backoff_seconds": 0},
        )

        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step1.to_dict(), step2.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        executor = RecordingExecutor()
        result = eng.run("bmm", "prd", run_id=created["run_id"], executor=executor)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(executor.contexts), 2)
        self.assertIsNotNone(executor.contexts[0])
        self.assertIsNotNone(executor.contexts[1])
        # First should not be cached, second should be
        self.assertFalse(executor.contexts[0].get("cached", False))
        self.assertTrue(executor.contexts[1].get("cached", False))

    def test_quint_evidence_recorded_at_levels(self) -> None:
        """Test that QUINT evidence can be recorded at L0, L1, L2 levels."""
        run_dir = storage.init_run_dir(self.sandbox, f"run-{uuid4().hex[:8]}")
        evidence_store = store.EvidenceStore(run_dir)

        # Record evidence at different levels
        l0_link = store.build_evidence_link(
            claim="Observed behavior",
            level="L0",
            source="test",
            carrier_ref="artifact.md",
            artifacts=["artifact.md"],
        )
        l1_link = store.build_evidence_link(
            claim="Deduced from observations",
            level="L1",
            source="test",
            carrier_ref="artifact.md",
            artifacts=["artifact.md"],
        )
        l2_link = store.build_evidence_link(
            claim="Validated through induction",
            level="L2",
            source="test",
            carrier_ref="artifact.md",
            artifacts=["artifact.md"],
        )

        evidence_store.record(l0_link)
        evidence_store.record(l1_link)
        evidence_store.record(l2_link)

        records = evidence_store.list()
        levels = [item.get("level") for item in records]

        self.assertEqual(len(records), 3)
        self.assertIn("L0", levels)
        self.assertIn("L1", levels)
        self.assertIn("L2", levels)

    def test_quint_wlnk_scoring_with_multiple_evidence(self) -> None:
        """Test WLNK scoring calculates weakest link correctly."""
        links = [
            models.EvidenceLink(
                id="ev-1",
                claim="High confidence",
                level="L2",
                source="test",
                date="2025-01-01",
                valid_until="2026-01-01",
                congruence="CL3",
                reliability=0.9,
                wlnk=0.0,
                carrier_ref="a.md",
                artifacts=["a.md"],
                notes="",
            ),
            models.EvidenceLink(
                id="ev-2",
                claim="Medium confidence",
                level="L1",
                source="test",
                date="2025-01-01",
                valid_until="2026-01-01",
                congruence="CL2",
                reliability=0.6,
                wlnk=0.0,
                carrier_ref="b.md",
                artifacts=["b.md"],
                notes="",
            ),
            models.EvidenceLink(
                id="ev-3",
                claim="Low confidence",
                level="L0",
                source="test",
                date="2025-01-01",
                valid_until="2026-01-01",
                congruence="CL1",
                reliability=0.8,
                wlnk=0.0,
                carrier_ref="c.md",
                artifacts=["c.md"],
                notes="",
            ),
        ]

        result = assurance.wlnk_score(links)

        # CL1 with 0.8 reliability = 0.8 * 0.5 = 0.4 (weakest)
        # CL2 with 0.6 reliability = 0.6 * 0.8 = 0.48
        # CL3 with 0.9 reliability = 0.9 * 1.0 = 0.9
        self.assertAlmostEqual(result.reliability, 0.4, places=2)
        self.assertEqual(result.weakest_id, "ev-3")

    def test_evidence_links_to_artifacts(self) -> None:
        """Test that evidence gets linked to artifacts in the index."""
        run_dir = storage.init_run_dir(self.sandbox, f"run-{uuid4().hex[:8]}")

        # Create an artifact first
        artifact_index = {
            "run_id": run_dir.name,
            "artifacts": [
                {
                    "artifact_id": "art-1",
                    "path": "output.md",
                    "artifact_type": "document",
                    "checksum": "abc123",
                    "workflow": "prd",
                    "created_at": "2025-01-01T00:00:00",
                    "metadata": {},
                }
            ],
            "updated_at": "2025-01-01T00:00:00",
        }
        storage.write_artifact_index(run_dir, artifact_index)

        # Record evidence linking to the artifact
        evidence_store = store.EvidenceStore(run_dir)
        link = store.build_evidence_link(
            claim="Test claim",
            level="L1",
            source="test",
            carrier_ref="output.md",
            artifacts=["output.md"],
        )
        evidence_store.record(link)

        # Verify the artifact now has the evidence link
        updated_index = storage.read_artifact_index(run_dir)
        artifact = updated_index["artifacts"][0]
        evidence_ids = artifact.get("metadata", {}).get("evidence_ids", [])

        self.assertIn(link.id, evidence_ids)

    def test_telis_progressive_negotiation_policy(self) -> None:
        """Test that progressive negotiation policy works correctly."""
        registry = self._registry()
        telis_engine = TelisPolicyEngine(registry=registry)
        spec = self._spec("Tier 2 shards + progressive negotiation")

        eng = engine.WorkflowEngine(
            self._config(), [spec], storage_root=self.sandbox, telis=telis_engine
        )
        created = eng.create_run("bmm", "prd")
        run_dir = self.sandbox / created["run_id"]

        step_spec = models.StepSpec(
            id="step-1",
            name="progressive",
            description="Test progressive negotiation",
            phase=spec.phase,
            inputs={"telis_query": "types", "telis_language": "python"},
            outputs=[],
            templates=[],
            tools=[],
            validation="",
            evidence="",
            human_gate="optional",
            retries={"max": 0, "backoff_seconds": 0},
        )

        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        executor = RecordingExecutor()
        result = eng.run("bmm", "prd", run_id=created["run_id"], executor=executor)

        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(executor.contexts[0])
        telis_ctx = executor.contexts[0]
        self.assertTrue(telis_ctx.get("progressive", False))
        self.assertIn("tier_2_micro", telis_ctx.get("tiers", []))

    def test_evidence_invalidation_updates_records(self) -> None:
        """Test that evidence invalidation properly marks records."""
        run_dir = storage.init_run_dir(self.sandbox, f"run-{uuid4().hex[:8]}")
        evidence_store = store.EvidenceStore(run_dir)

        link = store.build_evidence_link(
            claim="Valid claim",
            level="L1",
            source="test",
            carrier_ref="artifact.md",
            artifacts=["artifact.md"],
        )
        evidence_store.record(link)

        # Verify it's recorded as L1
        records = evidence_store.list()
        self.assertEqual(records[0]["level"], "L1")

        # Invalidate it
        updated = evidence_store.invalidate(link.id, reason="superseded")

        self.assertEqual(updated["level"], "invalid")
        self.assertIn("superseded", updated.get("notes", ""))

        # Verify the stored record is updated
        records = evidence_store.list()
        self.assertEqual(records[0]["level"], "invalid")

    def test_congruence_factors_applied_correctly(self) -> None:
        """Test that congruence factors are applied correctly."""
        self.assertEqual(assurance.congruence_factor("CL1"), 0.5)
        self.assertEqual(assurance.congruence_factor("CL2"), 0.8)
        self.assertEqual(assurance.congruence_factor("CL3"), 1.0)

        # Test penalty application
        score = assurance.apply_congruence_penalty(1.0, "CL1")
        self.assertAlmostEqual(score, 0.5, places=2)

        score = assurance.apply_congruence_penalty(1.0, "CL2")
        self.assertAlmostEqual(score, 0.8, places=2)

        score = assurance.apply_congruence_penalty(1.0, "CL3")
        self.assertAlmostEqual(score, 1.0, places=2)

    def test_telis_and_quint_workflow_integration(self) -> None:
        """Test a full workflow with both TELIS context and QUINT evidence."""
        registry = self._registry()
        telis_engine = TelisPolicyEngine(registry=registry)
        spec = self._spec("Tier 1 minimal")

        eng = engine.WorkflowEngine(
            self._config(), [spec], storage_root=self.sandbox, telis=telis_engine
        )
        created = eng.create_run("bmm", "prd")
        run_dir = self.sandbox / created["run_id"]

        step_spec = models.StepSpec(
            id="step-1",
            name="integrated",
            description="Integrated TELIS + QUINT step",
            phase=spec.phase,
            inputs={"telis_query": "syntax", "telis_language": "python"},
            outputs=["{output_folder}/result.md"],
            templates=[],
            tools=[],
            validation="",
            evidence="L1",
            human_gate="optional",
            retries={"max": 0, "backoff_seconds": 0},
        )

        manifest = storage.read_manifest(run_dir)
        manifest["step_specs"] = [step_spec.to_dict()]
        manifest["steps"] = []
        storage.write_manifest(run_dir, manifest)

        executor = RecordingExecutor()
        result = eng.run("bmm", "prd", run_id=created["run_id"], executor=executor)

        # Verify TELIS context was injected
        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(executor.contexts[0])
        self.assertIn("async def main", executor.contexts[0].get("context", ""))

        # Now record QUINT evidence for the step
        evidence_store = store.EvidenceStore(run_dir)
        link = store.build_evidence_link(
            claim="Step completed with TELIS context",
            level="L1",
            source="workflow",
            carrier_ref="result.md",
            artifacts=["result.md"],
        )
        evidence_store.record(link)

        records = evidence_store.list()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["level"], "L1")


if __name__ == "__main__":
    unittest.main()
