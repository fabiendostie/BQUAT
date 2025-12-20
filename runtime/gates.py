from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class GateDecision:
    required: bool
    reason: str


def gate_required(human_gate: str, config: Dict[str, Any]) -> GateDecision:
    hitl_cfg = config.get("hitl", {})
    mode = hitl_cfg.get("mode", "blocking")
    if mode != "blocking":
        return GateDecision(False, "hitl disabled")
    if human_gate == "required":
        return GateDecision(True, "explicit human gate")
    if human_gate == "conditional":
        if hitl_cfg.get("require_conditional", False):
            return GateDecision(True, "conditional gate enabled")
        return GateDecision(False, "conditional gate disabled")
    return GateDecision(False, "no blocking gate")


def has_approval(approvals: Dict[str, Any], gate_id: str) -> bool:
    entries: List[Dict[str, Any]] = approvals.get("approvals", [])
    return any(entry.get("gate_id") == gate_id for entry in entries)


def record_approval(
    approvals: Dict[str, Any],
    gate_id: str,
    approved_by: str,
    approved_at: str,
    notes: str,
) -> Dict[str, Any]:
    entry = {
        "gate_id": gate_id,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "notes": notes,
    }
    entries: List[Dict[str, Any]] = approvals.get("approvals", [])
    entries.append(entry)
    approvals["approvals"] = entries
    return approvals
