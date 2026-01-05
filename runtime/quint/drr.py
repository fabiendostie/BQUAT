from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from runtime import storage
from runtime.time_provider import get_current_time


@dataclass(frozen=True)
class DrrContext:
    problem_statement: str
    constraints: str
    dependencies: str
    assumptions: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "problem_statement": self.problem_statement,
            "constraints": self.constraints,
            "dependencies": self.dependencies,
            "assumptions": self.assumptions,
        }


@dataclass(frozen=True)
class DrrOption:
    name: str
    pros: List[str]
    cons: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "pros": list(self.pros),
            "cons": list(self.cons),
        }


@dataclass(frozen=True)
class DrrEvidence:
    l0: str
    l1: str
    l2: str
    wlnk: str
    congruence: str
    validity_window: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "l0": self.l0,
            "l1": self.l1,
            "l2": self.l2,
            "wlnk": self.wlnk,
            "congruence": self.congruence,
            "validity_window": self.validity_window,
        }


@dataclass(frozen=True)
class DrrDecision:
    selected_option: str
    rationale: str
    reversibility: str
    follow_ups: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "selected_option": self.selected_option,
            "rationale": self.rationale,
            "reversibility": self.reversibility,
            "follow_ups": self.follow_ups,
        }


@dataclass(frozen=True)
class DrrSummary:
    """Surface layer summary for stakeholder-friendly DRR output."""

    decision_id: str
    selected_option: str
    rationale_brief: str
    confidence: float
    approval_status: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "selected_option": self.selected_option,
            "rationale_brief": self.rationale_brief,
            "confidence": self.confidence,
            "approval_status": self.approval_status,
        }


@dataclass(frozen=True)
class DrrSignoff:
    approver: str
    date: str

    def to_dict(self) -> Dict[str, str]:
        return {"approver": self.approver, "date": self.date}


@dataclass(frozen=True)
class DrrRecord:
    decision_id: str
    date: str
    owner: str
    status: str
    context: DrrContext
    options: List[DrrOption]
    evidence: DrrEvidence
    decision: DrrDecision
    signoff: DrrSignoff
    evidence_links: List[Dict[str, object]] = field(default_factory=list)
    summary: Optional[DrrSummary] = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "decision_id": self.decision_id,
            "date": self.date,
            "owner": self.owner,
            "status": self.status,
            "context": self.context.to_dict(),
            "options": [option.to_dict() for option in self.options],
            "evidence": self.evidence.to_dict(),
            "decision": self.decision.to_dict(),
            "signoff": self.signoff.to_dict(),
            "evidence_links": [dict(item) for item in self.evidence_links],
        }
        if self.summary:
            payload["summary"] = self.summary.to_dict()
        return payload


def build_drr(
    decision_id: str,
    owner: str,
    status: str,
    context: DrrContext,
    options: List[DrrOption],
    evidence: DrrEvidence,
    decision: DrrDecision,
    signoff: Optional[DrrSignoff] = None,
    evidence_links: Optional[List[Dict[str, object]]] = None,
    summary: Optional[DrrSummary] = None,
) -> DrrRecord:
    timestamp = get_current_time()
    return DrrRecord(
        decision_id=decision_id,
        date=timestamp,
        owner=owner,
        status=status,
        context=context,
        options=options,
        evidence=evidence,
        decision=decision,
        signoff=signoff or DrrSignoff(approver="", date=""),
        evidence_links=list(evidence_links or []),
        summary=summary,
    )


class DrrStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def list(self) -> List[Dict[str, object]]:
        payload = storage.read_drrs(self.run_dir)
        drrs = payload.get("drrs", [])
        if isinstance(drrs, list):
            return [dict(item) for item in drrs]
        return []

    def record(self, record: DrrRecord, write_markdown: bool = True) -> Dict[str, object]:
        payload = storage.read_drrs(self.run_dir)
        drrs = payload.get("drrs", [])
        if not isinstance(drrs, list):
            drrs = []
        summary = record.summary or build_summary(record)
        rendered = record.to_dict()
        rendered["summary"] = summary.to_dict()
        if write_markdown:
            markdown_path = self._write_markdown(record)
            rendered["markdown_path"] = markdown_path
        drrs.append(rendered)
        payload["drrs"] = drrs
        storage.write_drrs(self.run_dir, payload)
        self._record_summary(summary)
        storage.update_timeline(self.run_dir)
        return rendered

    def _write_markdown(self, record: DrrRecord) -> str:
        directory = storage.ensure_dir(self.run_dir / "drr")
        filename = f"drr-{_safe_id(record.decision_id)}.md"
        path = directory / filename
        path.write_text(render_drr_markdown(record), encoding="ascii")
        return str(path)

    def _record_summary(self, summary: DrrSummary) -> None:
        path = self.run_dir / "drr-summaries.json"
        if path.exists():
            payload: Dict[str, object] = storage.read_json(path)
        else:
            payload = {"summaries": []}
        summaries = payload.get("summaries", [])
        if not isinstance(summaries, list):
            summaries = []
        summaries.append(summary.to_dict())
        payload["summaries"] = summaries
        payload["updated_at"] = get_current_time()
        storage.write_json(path, payload)


def build_summary(record: DrrRecord) -> DrrSummary:
    rationale = record.decision.rationale.strip()
    if len(rationale) > 160:
        rationale = f"{rationale[:157]}..."
    confidence = 0.0
    try:
        confidence = float(record.evidence.wlnk.replace("WLNK=", ""))
    except (ValueError, AttributeError):
        confidence = 0.0
    return DrrSummary(
        decision_id=record.decision_id,
        selected_option=record.decision.selected_option,
        rationale_brief=rationale,
        confidence=confidence,
        approval_status=record.status,
    )


def render_drr_markdown(record: DrrRecord) -> str:
    lines = [
        "# Design Rationale Record (DRR)",
        "",
        "## Decision",
        "",
        f"- Decision ID: {record.decision_id}",
        f"- Date: {record.date}",
        f"- Owner: {record.owner}",
        f"- Status (proposed/approved/rejected): {record.status}",
        "",
        "## Context",
        "",
        f"- Problem statement: {record.context.problem_statement}",
        f"- Constraints: {record.context.constraints}",
        f"- Dependencies: {record.context.dependencies}",
        f"- Assumptions: {record.context.assumptions}",
        "",
        "## Options Considered",
        "",
    ]
    for idx, option in enumerate(record.options, 1):
        lines.append(f"{idx}. {option.name}")
        lines.append(f"   - Pros: {', '.join(option.pros) if option.pros else 'none'}")
        lines.append(f"   - Cons: {', '.join(option.cons) if option.cons else 'none'}")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- L0 observations: {record.evidence.l0}",
            f"- L1 reasoning: {record.evidence.l1}",
            f"- L2 validation: {record.evidence.l2}",
            f"- WLNK analysis: {record.evidence.wlnk}",
            f"- Congruence level: {record.evidence.congruence}",
            f"- Validity window: {record.evidence.validity_window}",
            "",
            "## Decision and Rationale",
            "",
            f"- Selected option: {record.decision.selected_option}",
            f"- Rationale: {record.decision.rationale}",
            f"- Reversibility: {record.decision.reversibility}",
            f"- Follow-ups: {record.decision.follow_ups}",
            "",
            "## Signoff",
            "",
            f"- Approver: {record.signoff.approver}",
            f"- Date: {record.signoff.date}",
        ]
    )
    return "\n".join(lines)


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)
    return cleaned.strip("-") or "decision"
