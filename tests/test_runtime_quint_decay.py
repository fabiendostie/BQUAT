import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import models, storage  # noqa: E402
from runtime.quint import decay  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def _link(valid_until: str, level: str = "L1") -> models.EvidenceLink:
    return models.EvidenceLink(
        id=f"ev-{uuid4().hex[:6]}",
        claim="claim",
        level=level,
        source="unit-test",
        date="2025-12-27",
        valid_until=valid_until,
        congruence="CL1",
        reliability=0.9,
        wlnk=0.8,
        carrier_ref="artifact.md",
        artifacts=["artifact.md"],
        notes="",
    )


def _now() -> datetime:
    return datetime(2025, 12, 31, tzinfo=timezone.utc)


class RuntimeQuintDecayTests(unittest.TestCase):
    def test_expired_and_active(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-1")
        payload = {
            "evidence": [
                _link("2025-12-01").to_dict(),
                _link("2026-01-01").to_dict(),
            ]
        }
        storage.write_evidence_links(run_dir, payload)
        result = decay.scan_evidence(run_dir, now_provider=_now)
        self.assertEqual(len(result.expired), 1)
        self.assertEqual(len(result.active), 1)
        self.assertEqual(result.expired[0]["reason"], "expired")

    def test_invalid_or_missing_dates(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-2")
        payload = {
            "evidence": [
                _link("").to_dict(),
                _link("not-a-date").to_dict(),
            ]
        }
        storage.write_evidence_links(run_dir, payload)
        result = decay.scan_evidence(run_dir, now_provider=_now)
        reasons = {entry["reason"] for entry in result.expired}
        self.assertIn("missing_valid_until", reasons)
        self.assertIn("invalid_valid_until", reasons)

    def test_invalid_level_is_separate(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-3")
        payload = {"evidence": [_link("2026-01-01", level="invalid").to_dict()]}
        storage.write_evidence_links(run_dir, payload)
        result = decay.scan_evidence(run_dir, now_provider=_now)
        self.assertEqual(len(result.invalid), 1)
        self.assertEqual(result.invalid[0]["reason"], "already_invalid")


if __name__ == "__main__":
    unittest.main()
