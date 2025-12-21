import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import storage  # noqa: E402


class RuntimeStorageTests(unittest.TestCase):
    def test_manifest_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_dir = storage.init_run_dir(tmp, "run-1")
            manifest = {"run_id": "run-1", "status": "pending"}
            storage.write_manifest(run_dir, manifest)
            loaded = storage.read_manifest(run_dir)
            self.assertEqual(loaded["run_id"], "run-1")

    def test_approvals_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_dir = storage.init_run_dir(tmp, "run-2")
            approvals = storage.read_approvals(run_dir)
            self.assertEqual(approvals, {"approvals": []})

    def test_schema_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_dir = storage.init_run_dir(tmp, "run-3")
            artifacts = storage.read_artifact_index(run_dir)
            evidence = storage.read_evidence_links(run_dir)
            gates = storage.read_human_gates(run_dir)
            events = storage.read_events(run_dir)
            self.assertEqual(artifacts["artifacts"], [])
            self.assertEqual(evidence, {"evidence": []})
            self.assertEqual(gates, {"gates": []})
            self.assertEqual(events, {"events": []})


if __name__ == "__main__":
    unittest.main()
