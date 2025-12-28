import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models  # noqa: E402
from runtime.quint import assurance  # noqa: E402


def _link(reliability: float, congruence: str) -> models.EvidenceLink:
    return models.EvidenceLink(
        id=f"ev-{uuid4().hex[:6]}",
        claim="claim",
        level="L1",
        source="unit-test",
        date="2025-12-27",
        valid_until="2026-12-27",
        congruence=congruence,
        reliability=reliability,
        wlnk=0.0,
        carrier_ref="artifact.md",
        artifacts=["artifact.md"],
        notes="",
    )


class RuntimeQuintAssuranceTests(unittest.TestCase):
    def test_congruence_factor(self) -> None:
        self.assertEqual(assurance.congruence_factor("CL1"), 0.5)
        self.assertEqual(assurance.congruence_factor("CL2"), 0.8)
        self.assertEqual(assurance.congruence_factor("CL3"), 1.0)

    def test_apply_congruence_penalty(self) -> None:
        score = assurance.apply_congruence_penalty(0.9, "CL1")
        self.assertAlmostEqual(score, 0.45, places=2)

    def test_wlnk_score_uses_weakest_link(self) -> None:
        records = [
            _link(0.9, "CL3"),
            _link(0.6, "CL2"),
            _link(0.8, "CL3"),
        ]
        result = assurance.wlnk_score(records)
        self.assertAlmostEqual(result.score, 0.48, places=2)
        self.assertEqual(result.weakest_id, records[1].id)

    def test_wlnk_empty_returns_zero(self) -> None:
        result = assurance.wlnk_score([])
        self.assertEqual(result.score, 0.0)
        self.assertIsNone(result.weakest_id)


if __name__ == "__main__":
    unittest.main()
