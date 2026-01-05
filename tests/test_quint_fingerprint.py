import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import storage  # noqa: E402
from runtime.quint import fingerprint  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class QuintFingerprintTests(unittest.TestCase):
    def test_fingerprint_store_records(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-fp")
        store = fingerprint.FingerprintStore(run_dir)
        fp = fingerprint.build_fingerprint(
            step_id="step-1",
            shard_ids=["s1"],
            cache_keys=["cache-1"],
            token_budget_used=10,
            token_budget_total=50,
        )
        recorded = store.record(fp)
        self.assertEqual(recorded["fingerprint_id"], fp.fingerprint_id)
        latest = store.get_latest_for_step("step-1")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["fingerprint_id"], fp.fingerprint_id)


if __name__ == "__main__":
    unittest.main()
