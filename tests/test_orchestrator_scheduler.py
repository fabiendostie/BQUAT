import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.orchestrator.scheduler import ResourceScheduler  # noqa: E402


class OrchestratorSchedulerTests(unittest.TestCase):
    def test_provider_limits(self) -> None:
        config = {"orchestrator": {"provider_limits": {"mock": 1}}}
        scheduler = ResourceScheduler(config)
        self.assertTrue(scheduler.acquire("w1", "mock"))
        self.assertFalse(scheduler.acquire("w2", "mock"))
        scheduler.release("w1", "mock")
        self.assertTrue(scheduler.acquire("w2", "mock"))


if __name__ == "__main__":
    unittest.main()
