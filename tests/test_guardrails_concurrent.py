import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import storage  # noqa: E402
from runtime.guardrails import (
    checks,  # noqa: E402
    concurrent,  # noqa: E402
)


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class GuardrailsConcurrentTests(unittest.TestCase):
    def test_concurrent_matches_sync(self) -> None:
        run_dir = storage.init_run_dir(_sandbox_root(), "run-guardrails")
        config = {
            "guardrails": {
                "enabled": True,
                "stages": ["inputs"],
                "pii": {"enabled": True},
                "moderation": {"enabled": False},
                "rules": {"enabled": False},
            }
        }
        step = {"inputs": {"email": "user@example.com"}}
        sync_report = checks.evaluate_guardrails("inputs", step, None, config, run_dir)
        async_report = concurrent.evaluate_guardrails_concurrent(
            "inputs", step, None, config, run_dir
        )
        self.assertIsNotNone(sync_report)
        self.assertIsNotNone(async_report)
        self.assertEqual(sync_report.status, async_report.status)
        self.assertEqual(sync_report.violations[0]["type"], async_report.violations[0]["type"])


if __name__ == "__main__":
    unittest.main()
