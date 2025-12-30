from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class GateDecision:
    required: bool
    reason: str


def gate_required(
    human_gate: str,
    config: Dict[str, Any],
    phase: str = "",
    workflow: str = "",
) -> GateDecision:
    hitl_cfg = config.get("hitl", {})
    mode = hitl_cfg.get("mode", "blocking")
    if mode != "blocking":
        return GateDecision(False, "hitl disabled")
    gate_value = (human_gate or "").strip().lower()
    if gate_value in {"none", "no", "n/a"}:
        return GateDecision(False, "gate disabled")

    policy = hitl_cfg.get("policy", {})
    required_phases = _normalize_list(policy.get("required_phases", []))
    conditional_phases = _normalize_list(policy.get("conditional_phases", []))
    high_risk_keywords = _normalize_keywords(policy.get("high_risk_keywords", []))
    conditional_keywords = _normalize_keywords(policy.get("conditional_keywords", []))
    conditional_required = bool(
        policy.get("conditional_required", hitl_cfg.get("require_conditional", False))
    )
    recommended_required = bool(policy.get("recommended_required", False))

    if phase in required_phases:
        return GateDecision(True, "policy required phase")
    if _matches_keyword(workflow, high_risk_keywords):
        return GateDecision(True, "high-risk workflow")
    if gate_value == "required":
        return GateDecision(True, "explicit human gate")
    if gate_value == "conditional" or phase in conditional_phases:
        if conditional_required:
            return GateDecision(True, "conditional gate enforced")
        return GateDecision(False, "conditional gate disabled")
    if _matches_keyword(workflow, conditional_keywords):
        if conditional_required:
            return GateDecision(True, "conditional risk gate")
        return GateDecision(False, "conditional risk gate disabled")
    if gate_value == "recommended":
        if recommended_required:
            return GateDecision(True, "recommended gate enforced")
        return GateDecision(False, "recommended gate")
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


def record_gate(
    gates_payload: Dict[str, Any],
    gate_id: str,
    status: str,
    required: bool,
    reason: str,
    phase: str,
    workflow: str,
    recorded_at: str,
    approved_by: str | None = None,
    approved_at: str | None = None,
    notes: str = "",
) -> Dict[str, Any]:
    entry = {
        "gate_id": gate_id,
        "status": status,
        "required": required,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "notes": notes,
        "reason": reason,
        "phase": phase,
        "workflow": workflow,
        "recorded_at": recorded_at,
    }
    entries: List[Dict[str, Any]] = gates_payload.get("gates", [])
    for existing in entries:
        if existing.get("gate_id") == gate_id:
            existing.update(entry)
            gates_payload["gates"] = entries
            return gates_payload
    entries.append(entry)
    gates_payload["gates"] = entries
    return gates_payload


def _normalize_list(values: Any) -> List[str]:
    if not values:
        return []
    if isinstance(values, list):
        return [str(item).strip() for item in values if str(item).strip()]
    return [str(values).strip()]


def _normalize_keywords(values: Any) -> List[str]:
    return [item.lower() for item in _normalize_list(values)]


def _matches_keyword(text: str, keywords: List[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)
