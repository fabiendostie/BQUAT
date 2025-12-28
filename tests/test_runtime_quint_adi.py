import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models, storage  # noqa: E402
from runtime.quint import adi, store  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def _link(level: str, claim: str = "claim") -> models.EvidenceLink:
    return models.EvidenceLink(
        id=f"ev-{uuid4().hex[:6]}",
        claim=claim,
        level=level,
        source="unit-test",
        date="2025-12-27",
        valid_until="2026-12-27",
        congruence="CL1",
        reliability=0.9,
        wlnk=0.8,
        carrier_ref="artifact.md",
        artifacts=["artifact.md"],
        notes="",
    )


class RuntimeQuintAdiTests(unittest.TestCase):
    def test_promote_l0_to_l1(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-1")
        evidence = store.EvidenceStore(run_dir)
        link = _link("L0")
        evidence.record(link)
        updated = adi.promote_evidence(run_dir, link.id, "L1", notes="verified")
        self.assertEqual(updated.get("level"), "L1")
        self.assertIn("verified", updated.get("notes", ""))

    def test_promote_l1_to_l2(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-2")
        evidence = store.EvidenceStore(run_dir)
        link = _link("L1")
        evidence.record(link)
        updated = adi.promote_evidence(run_dir, link.id, "L2")
        self.assertEqual(updated.get("level"), "L2")

    def test_invalid_promotion_raises(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-3")
        evidence = store.EvidenceStore(run_dir)
        link = _link("L0")
        evidence.record(link)
        with self.assertRaises(ValueError):
            adi.promote_evidence(run_dir, link.id, "L2")

    def test_invalidated_cannot_promote(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-4")
        evidence = store.EvidenceStore(run_dir)
        link = _link("L0")
        evidence.record(link)
        adi.invalidate_evidence(run_dir, link.id, reason="failed")
        with self.assertRaises(ValueError):
            adi.promote_evidence(run_dir, link.id, "L1")


if __name__ == "__main__":
    unittest.main()
