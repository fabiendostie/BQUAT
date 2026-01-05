import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import storage  # noqa: E402
from runtime.quint import drift, snapshot  # noqa: E402
from runtime.quint.snapshot import ContextSnapshot  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class QuintSnapshotDriftTests(unittest.TestCase):
    def test_snapshot_store_records(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-snap")
        storage.write_artifact_index(
            run_dir,
            {"run_id": "run-snap", "artifacts": [{"path": "a.txt", "checksum": "abc"}]},
        )
        manifest = {"workflow": {"telis": "tier 1", "validation": "ast"}}
        snap = snapshot.build_snapshot(manifest, run_dir, telis=None, config={})
        store = snapshot.SnapshotStore(run_dir)
        recorded = store.record(snap)
        self.assertEqual(recorded["snapshot_id"], snap.snapshot_id)
        loaded = store.get(snap.snapshot_id)
        self.assertIsNotNone(loaded)
        self.assertIn("a.txt", loaded["artifact_checksums"])

    def test_detect_drift_changes(self) -> None:
        base = ContextSnapshot(
            snapshot_id="cs-1",
            captured_at="t0",
            shards_available=("s1", "s2"),
            lsp_enabled=True,
            token_budget_total=10,
            telis_policy_hash="aaa",
            validation_gates=("ast",),
            artifact_checksums={"a.txt": "abc"},
        )
        current = ContextSnapshot(
            snapshot_id="cs-2",
            captured_at="t1",
            shards_available=("s1",),
            lsp_enabled=False,
            token_budget_total=20,
            telis_policy_hash="bbb",
            validation_gates=("ast",),
            artifact_checksums={"a.txt": "def"},
        )
        drifts = drift.detect_drift(base, current)
        kinds = {item.drift_type for item in drifts}
        self.assertIn("shard_removed", kinds)
        self.assertIn("policy_changed", kinds)
        self.assertIn("lsp_changed", kinds)
        self.assertIn("budget_changed", kinds)
        self.assertIn("artifact_modified", kinds)

    def test_mark_evidence_drifted(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-drift")
        storage.write_evidence_links(run_dir, {"evidence": [{"id": "ev-1"}]})
        drifts = [
            drift.DriftIndicator(
                snapshot_id="cs-1",
                detected_at="now",
                drift_type="policy_changed",
                details="policy updated",
            )
        ]
        updated = drift.mark_evidence_drifted(run_dir, drifts)
        self.assertEqual(updated, 1)
        payload = storage.read_evidence_links(run_dir)
        record = payload["evidence"][0]
        self.assertTrue(record.get("drifted"))
        self.assertIn("policy_changed", record.get("drift_types", []))
        store = drift.DriftStore(run_dir)
        stored = store.record(drifts)
        self.assertEqual(stored[0]["drift_type"], "policy_changed")


if __name__ == "__main__":
    unittest.main()
