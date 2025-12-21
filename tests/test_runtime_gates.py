import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import gates  # noqa: E402


class RuntimeGateTests(unittest.TestCase):
    def test_gate_required_logic(self) -> None:
        cfg = {"hitl": {"mode": "blocking", "require_conditional": False}}
        decision = gates.gate_required("required", cfg)
        self.assertTrue(decision.required)

        decision = gates.gate_required("conditional", cfg)
        self.assertFalse(decision.required)

        cfg["hitl"]["require_conditional"] = True
        decision = gates.gate_required("conditional", cfg)
        self.assertTrue(decision.required)

        decision = gates.gate_required("optional", cfg)
        self.assertFalse(decision.required)

        cfg = {"hitl": {"mode": "disabled", "require_conditional": True}}
        decision = gates.gate_required("required", cfg)
        self.assertFalse(decision.required)

        decision = gates.gate_required("unknown", {})
        self.assertFalse(decision.required)

    def test_approvals_tracking(self) -> None:
        approvals = {"approvals": []}
        self.assertFalse(gates.has_approval(approvals, "gate-1"))

        approvals = gates.record_approval(approvals, "gate-1", "user", "now", "ok")
        self.assertTrue(gates.has_approval(approvals, "gate-1"))


if __name__ == "__main__":
    unittest.main()
