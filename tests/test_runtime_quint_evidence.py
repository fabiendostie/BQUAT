import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models, storage  # noqa: E402
from runtime.quint import store  # noqa: E402


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


class RuntimeQuintEvidenceTests(unittest.TestCase):
    def test_record_levels(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-1")
        evidence = store.EvidenceStore(run_dir)
        evidence.record(_link("L0", "obs"))
        evidence.record(_link("L1", "deduction"))
        evidence.record(_link("L2", "induction"))
        levels = [item.get("level") for item in evidence.list()]
        self.assertEqual(levels, ["L0", "L1", "L2"])

    def test_invalidate_marks_invalid(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-2")
        evidence = store.EvidenceStore(run_dir)
        link = _link("L1")
        evidence.record(link)
        updated = evidence.invalidate(link.id, reason="expired")
        self.assertEqual(updated.get("level"), "invalid")
        self.assertIn("expired", updated.get("notes", ""))

    def test_invalid_level_raises(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-3")
        evidence = store.EvidenceStore(run_dir)
        with self.assertRaises(ValueError):
            evidence.record(_link("L9"))


if __name__ == "__main__":
    unittest.main()
