import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import gates  # noqa: E402


class RuntimeGateTests(unittest.TestCase):
    def test_gate_required_logic(self) -> None:
        cfg = {"hitl": {"mode": "blocking", "require_conditional": False}}
        decision = gates.gate_required("required", cfg, phase="Phase 2 Planning", workflow="prd")
        self.assertTrue(decision.required)

        decision = gates.gate_required(
            "conditional", cfg, phase="Phase 4 Implementation", workflow="dev"
        )
        self.assertFalse(decision.required)

        cfg["hitl"]["require_conditional"] = True
        decision = gates.gate_required(
            "conditional", cfg, phase="Phase 4 Implementation", workflow="dev"
        )
        self.assertTrue(decision.required)

        decision = gates.gate_required(
            "optional", cfg, phase="Phase 4 Implementation", workflow="dev"
        )
        self.assertFalse(decision.required)

        cfg = {"hitl": {"mode": "disabled", "require_conditional": True}}
        decision = gates.gate_required("required", cfg, phase="Phase 2 Planning", workflow="prd")
        self.assertFalse(decision.required)

        decision = gates.gate_required("unknown", {}, phase="Phase 2 Planning", workflow="prd")
        self.assertFalse(decision.required)

    def test_approvals_tracking(self) -> None:
        approvals = {"approvals": []}
        self.assertFalse(gates.has_approval(approvals, "gate-1"))

        approvals = gates.record_approval(approvals, "gate-1", "user", "now", "ok")
        self.assertTrue(gates.has_approval(approvals, "gate-1"))

    def test_gate_policy_phase_and_risk(self) -> None:
        cfg = {"hitl": {"mode": "blocking", "policy": {"required_phases": ["Phase 2 Planning"]}}}
        decision = gates.gate_required("optional", cfg, phase="Phase 2 Planning", workflow="prd")
        self.assertTrue(decision.required)

        cfg = {"hitl": {"mode": "blocking", "policy": {"high_risk_keywords": ["deploy"]}}}
        decision = gates.gate_required(
            "optional", cfg, phase="Phase 4 Production", workflow="deploy-app"
        )
        self.assertTrue(decision.required)

        cfg = {
            "hitl": {
                "mode": "blocking",
                "policy": {"conditional_keywords": ["security"], "conditional_required": True},
            }
        }
        decision = gates.gate_required(
            "optional", cfg, phase="Phase 4 Implementation", workflow="security-review"
        )
        self.assertTrue(decision.required)

        cfg = {"hitl": {"mode": "blocking", "policy": {"recommended_required": True}}}
        decision = gates.gate_required(
            "recommended", cfg, phase="Phase 0 Documentation", workflow="document-project"
        )
        self.assertTrue(decision.required)


if __name__ == "__main__":
    unittest.main()
