import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import storage  # noqa: E402
from runtime.quint.drr import (  # noqa: E402
    DrrContext,
    DrrDecision,
    DrrEvidence,
    DrrOption,
    DrrSignoff,
    DrrStore,
    build_drr,
)


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class QuintSurfaceGroundingTests(unittest.TestCase):
    def test_drr_summary_written(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-summary")
        store = DrrStore(run_dir)
        context = DrrContext(
            problem_statement="Pick a storage layer.",
            constraints="Local-first.",
            dependencies="runtime/storage.py",
            assumptions="Minimal dependencies.",
        )
        options = [
            DrrOption(name="JSON files", pros=["Portable"], cons=["No queries"]),
            DrrOption(name="SQLite", pros=["Queryable"], cons=["Extra dependency"]),
        ]
        rationale = "x" * 200
        evidence = DrrEvidence(
            l0="Existing storage is JSON.",
            l1="JSON keeps stack minimal.",
            l2="Validated by tests.",
            wlnk="WLNK=0.85",
            congruence="CL1",
            validity_window="2025-12-01 to 2026-12-01",
        )
        decision = DrrDecision(
            selected_option="JSON files",
            rationale=rationale,
            reversibility="Medium",
            follow_ups="Revisit if scale changes.",
        )
        signoff = DrrSignoff(approver="Lead", date="2025-12-28")
        record = build_drr(
            decision_id="DRR-100",
            owner="Runtime",
            status="approved",
            context=context,
            options=options,
            evidence=evidence,
            decision=decision,
            signoff=signoff,
        )

        store.record(record)
        summary_path = run_dir / "drr-summaries.json"
        self.assertTrue(summary_path.exists())
        payload = storage.read_json(summary_path)
        summary = payload["summaries"][0]
        self.assertEqual(summary["decision_id"], "DRR-100")
        self.assertEqual(summary["confidence"], 0.85)
        self.assertTrue(summary["rationale_brief"].endswith("..."))
        self.assertEqual(len(summary["rationale_brief"]), 160)

        drr_payload = storage.read_drrs(run_dir)
        self.assertIn("summary", drr_payload["drrs"][0])


if __name__ == "__main__":
    unittest.main()
