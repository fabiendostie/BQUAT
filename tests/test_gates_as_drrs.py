import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import gates, models, storage  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def _evidence_link() -> models.EvidenceLink:
    return models.EvidenceLink(
        id=f"ev-{uuid4().hex[:6]}",
        claim="Gate decision",
        level="L1",
        source="unit-test",
        date="2025-12-27",
        valid_until="2026-12-27",
        congruence="CL1",
        reliability=0.9,
        wlnk=0.8,
        carrier_ref="gate.md",
        context_fingerprint_id="fp-123",
        artifacts=["gate.md"],
        notes="",
    )


class GateDrrTests(unittest.TestCase):
    def test_record_gate_as_drr(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-gate")
        gate_id = "core:prd:hitl"
        record = gates.record_gate_as_drr(
            run_dir=run_dir,
            gate_id=gate_id,
            phase="Phase 2 Planning",
            workflow="core/prd",
            policy_reason="policy required",
            supporting_evidence=[_evidence_link()],
            approved_by="tester",
            approval_notes="ok",
        )
        self.assertEqual(record.decision_id, f"gate-{gate_id}")

        payload = storage.read_drrs(run_dir)
        self.assertEqual(payload["drrs"][0]["decision_id"], f"gate-{gate_id}")
        self.assertEqual(
            payload["drrs"][0]["evidence_links"][0]["context_fingerprint_id"],
            "fp-123",
        )

        summary_path = run_dir / "drr-summaries.json"
        self.assertTrue(summary_path.exists())
        summary = storage.read_json(summary_path)["summaries"][0]
        self.assertEqual(summary["selected_option"], "Require human approval")


if __name__ == "__main__":
    unittest.main()
