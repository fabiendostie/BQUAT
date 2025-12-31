import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import storage  # noqa: E402
from runtime.guardrails import checks as guardrails  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class RuntimeGuardrailsTests(unittest.TestCase):
    def test_pii_detection_inputs(self) -> None:
        config = {
            "guardrails": {
                "enabled": True,
                "stages": ["inputs"],
                "pii": {"enabled": True},
                "moderation": {"enabled": False},
                "rules": {"enabled": False},
            }
        }
        step = {"inputs": {"contact": "Reach me at test@example.com"}}
        report = guardrails.evaluate_guardrails(
            "inputs",
            step,
            None,
            config,
            run_dir=_sandbox_root(),
        )
        self.assertIsNotNone(report)
        self.assertEqual(report.status, "failed")
        self.assertEqual(report.violations[0]["type"], "pii")

    def test_rules_blocklist(self) -> None:
        config = {
            "guardrails": {
                "enabled": True,
                "stages": ["inputs"],
                "pii": {"enabled": False},
                "moderation": {"enabled": False},
                "rules": {"enabled": True, "blocklist": ["drop table"]},
            }
        }
        step = {"inputs": {"sql": "DROP TABLE users;"}}
        report = guardrails.evaluate_guardrails(
            "inputs",
            step,
            None,
            config,
            run_dir=_sandbox_root(),
        )
        self.assertIsNotNone(report)
        self.assertEqual(report.status, "failed")
        self.assertEqual(report.violations[0]["type"], "rules_blocklist")

    def test_outputs_scan_file(self) -> None:
        config = {
            "guardrails": {
                "enabled": True,
                "stages": ["outputs"],
                "pii": {"enabled": True},
                "moderation": {"enabled": False},
                "rules": {"enabled": False},
            }
        }
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-1")
        (run_dir / "output.txt").write_text("SSN 123-45-6789", encoding="ascii")
        step = {"outputs": ["output.txt"]}
        report = guardrails.evaluate_guardrails(
            "outputs",
            step,
            None,
            config,
            run_dir=run_dir,
        )
        self.assertIsNotNone(report)
        self.assertEqual(report.status, "failed")
        self.assertEqual(report.violations[0]["type"], "pii")


if __name__ == "__main__":
    unittest.main()
