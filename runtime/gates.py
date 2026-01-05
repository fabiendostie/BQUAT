from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime import models
from runtime.quint import drr as quint_drr
from runtime.quint.drr import DrrDecision, DrrEvidence, DrrOption, DrrSignoff
from runtime.time_provider import get_current_time


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
    drr_id: Optional[str] = None,
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
        "drr_id": drr_id,
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


def record_gate_as_drr(
    run_dir: Path,
    gate_id: str,
    phase: str,
    workflow: str,
    policy_reason: str,
    supporting_evidence: List[models.EvidenceLink],
    approved_by: Optional[str] = None,
    approval_notes: str = "",
) -> quint_drr.DrrRecord:
    decision_id = f"gate-{gate_id}"
    owner = approved_by or "system"
    status = "approved" if approved_by else "proposed"
    context = quint_drr.DrrContext(
        problem_statement=f"Gate {gate_id} required for {workflow}.",
        constraints="HITL policy enforcement",
        dependencies="runtime/gates.py",
        assumptions="Manual approval required before execution continues",
    )
    options = [
        DrrOption(
            name="Require human approval",
            pros=["Policy compliance", "Auditability"],
            cons=["Blocks automation until approved"],
        ),
        DrrOption(
            name="Auto-approve gate",
            pros=["Faster automation"],
            cons=["Violates HITL policy"],
        ),
    ]
    evidence_links = [link.to_dict() for link in supporting_evidence]
    evidence = DrrEvidence(
        l0=policy_reason or "Gate policy evaluated",
        l1="HITL policy requires explicit approval",
        l2=f"Supporting evidence links: {', '.join(link.id for link in supporting_evidence) or 'none'}",
        wlnk="0.0",
        congruence="CL0",
        validity_window="until approved",
    )
    decision = DrrDecision(
        selected_option="Require human approval",
        rationale=policy_reason or "Gate enforced by policy",
        reversibility="Reversible upon approval",
        follow_ups=approval_notes or "Await approval",
    )
    signoff = DrrSignoff(
        approver=approved_by or "",
        date=get_current_time() if approved_by else "",
    )
    record = quint_drr.build_drr(
        decision_id=decision_id,
        owner=owner,
        status=status,
        context=context,
        options=options,
        evidence=evidence,
        decision=decision,
        signoff=signoff,
        evidence_links=evidence_links,
        summary=None,
    )
    store = quint_drr.DrrStore(run_dir)
    store.record(record)
    return record


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
