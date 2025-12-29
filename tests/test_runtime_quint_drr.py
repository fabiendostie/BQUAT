import sys
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

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


class RuntimeQuintDrrTests(unittest.TestCase):
    def test_store_writes_json_and_markdown(self) -> None:
        root = _sandbox_root()
        run_dir = storage.init_run_dir(root, "run-drr")
        store = DrrStore(run_dir)
        context = DrrContext(
            problem_statement="Select a storage backend.",
            constraints="Must be local-first.",
            dependencies="runtime/storage.py",
            assumptions="JSON payloads are acceptable.",
        )
        options = [
            DrrOption(name="JSON files", pros=["Portable"], cons=["No queries"]),
            DrrOption(name="SQLite", pros=["Queryable"], cons=["Extra dependency"]),
        ]
        evidence = DrrEvidence(
            l0="Existing runtime storage uses JSON.",
            l1="JSON keeps the stack minimal.",
            l2="Validated via storage tests.",
            wlnk="WLNK=0.7",
            congruence="medium",
            validity_window="2025-12-01 to 2026-12-01",
        )
        decision = DrrDecision(
            selected_option="JSON files",
            rationale="Align with existing storage primitives.",
            reversibility="Medium",
            follow_ups="Revisit if indexing becomes complex.",
        )
        signoff = DrrSignoff(approver="Lead", date="2025-12-28")

        with patch("runtime.quint.drr.get_current_time", return_value="2025-12-28T00:00:00-05:00"):
            record = build_drr(
                decision_id="DRR 001",
                owner="Runtime",
                status="approved",
                context=context,
                options=options,
                evidence=evidence,
                decision=decision,
                signoff=signoff,
            )

        rendered = store.record(record)
        markdown_path = Path(rendered["markdown_path"])
        self.assertTrue(markdown_path.exists())
        self.assertEqual(markdown_path.name, "drr-DRR-001.md")
        markdown = markdown_path.read_text(encoding="ascii")
        self.assertIn("Decision ID: DRR 001", markdown)
        self.assertIn("Selected option: JSON files", markdown)

        payload = storage.read_drrs(run_dir)
        self.assertEqual(len(payload["drrs"]), 1)
        self.assertEqual(payload["drrs"][0]["decision_id"], "DRR 001")


if __name__ == "__main__":
    unittest.main()
