import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import storage  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class RuntimeStorageTests(unittest.TestCase):
    def test_manifest_round_trip(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-1")
        manifest = {"run_id": "run-1", "status": "pending"}
        storage.write_manifest(run_dir, manifest)
        loaded = storage.read_manifest(run_dir)
        self.assertEqual(loaded["run_id"], "run-1")

    def test_approvals_default(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-2")
        approvals = storage.read_approvals(run_dir)
        self.assertEqual(approvals, {"approvals": []})

    def test_schema_defaults(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-3")
        artifacts = storage.read_artifact_index(run_dir)
        evidence = storage.read_evidence_links(run_dir)
        drrs = storage.read_drrs(run_dir)
        gates = storage.read_human_gates(run_dir)
        events = storage.read_events(run_dir)
        timeline = storage.read_timeline(run_dir)
        self.assertEqual(artifacts["artifacts"], [])
        self.assertEqual(evidence, {"evidence": []})
        self.assertEqual(drrs, {"drrs": []})
        self.assertEqual(gates, {"gates": []})
        self.assertEqual(events, {"events": []})
        self.assertEqual(timeline["entries"], [])

    def test_artifact_index_round_trip(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-4")
        payload = {"run_id": "run-4", "artifacts": [{"path": "a"}], "updated_at": "now"}
        storage.write_artifact_index(run_dir, payload)
        loaded = storage.read_artifact_index(run_dir)
        self.assertEqual(loaded, payload)

    def test_evidence_round_trip(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-5")
        payload = {"evidence": [{"id": "e1"}]}
        storage.write_evidence_links(run_dir, payload)
        loaded = storage.read_evidence_links(run_dir)
        self.assertEqual(loaded, payload)

    def test_drr_round_trip(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-5b")
        payload = {"drrs": [{"id": "d1"}]}
        storage.write_drrs(run_dir, payload)
        loaded = storage.read_drrs(run_dir)
        self.assertEqual(loaded, payload)

    def test_gates_round_trip(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-6")
        payload = {"gates": [{"gate_id": "g1"}]}
        storage.write_human_gates(run_dir, payload)
        loaded = storage.read_human_gates(run_dir)
        self.assertEqual(loaded, payload)

    def test_events_round_trip(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-7")
        payload = {"events": [{"event_type": "WorkflowStarted"}]}
        storage.write_events(run_dir, payload)
        loaded = storage.read_events(run_dir)
        self.assertEqual(loaded, payload)

    def test_tool_results_round_trip(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-8")
        payload = {"results": [{"name": "getCurrentTime", "status": "completed"}]}
        storage.write_tool_results(run_dir, payload)
        loaded = storage.read_tool_results(run_dir)
        self.assertEqual(loaded, payload)

    def test_timeline_round_trip(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-9")
        payload = {
            "run_id": "run-9",
            "generated_at": "2025-12-30T00:00:00-05:00",
            "entries": [{"type": "event", "timestamp": "2025-12-30T00:01:00-05:00"}],
        }
        storage.write_timeline(run_dir, payload)
        loaded = storage.read_timeline(run_dir)
        self.assertEqual(loaded, payload)


if __name__ == "__main__":
    unittest.main()
