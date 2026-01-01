from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class LogRecord:
    """Structured log entry."""

    level: str
    category: str
    message: str
    timestamp: str
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogRecord":
        return cls(
            level=data["level"],
            category=data["category"],
            message=data["message"],
            timestamp=data["timestamp"],
            run_id=data.get("run_id"),
            step_id=data.get("step_id"),
            payload=dict(data.get("payload", {})),
        )


@dataclass(frozen=True)
class EmittedEvent:
    """Event record for external consumption."""

    event_type: str
    timestamp: str
    run_id: str
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmittedEvent":
        return cls(
            event_type=data["event_type"],
            timestamp=data["timestamp"],
            run_id=data["run_id"],
            source=data["source"],
            payload=dict(data.get("payload", {})),
            step_id=data.get("step_id"),
        )


@dataclass(frozen=True)
class RunReportSummary:
    """High-level run statistics for the report."""

    run_id: str
    status: str
    workflow_id: str
    module: str
    workflow: str
    phase: str
    started_at: str
    completed_at: str
    duration_seconds: float
    steps_total: int
    steps_completed: int
    steps_failed: int
    gates_total: int
    gates_approved: int
    gates_blocked: int
    evidence_count: int
    artifacts_count: int
    validation_passed: int
    validation_failed: int
    guardrail_violations: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunReportSummary":
        return cls(
            run_id=data["run_id"],
            status=data["status"],
            workflow_id=data["workflow_id"],
            module=data["module"],
            workflow=data["workflow"],
            phase=data["phase"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            steps_total=int(data.get("steps_total", 0)),
            steps_completed=int(data.get("steps_completed", 0)),
            steps_failed=int(data.get("steps_failed", 0)),
            gates_total=int(data.get("gates_total", 0)),
            gates_approved=int(data.get("gates_approved", 0)),
            gates_blocked=int(data.get("gates_blocked", 0)),
            evidence_count=int(data.get("evidence_count", 0)),
            artifacts_count=int(data.get("artifacts_count", 0)),
            validation_passed=int(data.get("validation_passed", 0)),
            validation_failed=int(data.get("validation_failed", 0)),
            guardrail_violations=int(data.get("guardrail_violations", 0)),
        )


@dataclass(frozen=True)
class RunReport:
    """Complete run report artifact."""

    version: str
    generated_at: str
    summary: RunReportSummary
    events: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    gates: List[Dict[str, Any]] = field(default_factory=list)
    drrs: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    guardrail_reports: List[Dict[str, Any]] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "summary": self.summary.to_dict(),
            "events": list(self.events),
            "logs": list(self.logs),
            "artifacts": list(self.artifacts),
            "evidence": list(self.evidence),
            "gates": list(self.gates),
            "drrs": list(self.drrs),
            "validation_results": list(self.validation_results),
            "guardrail_reports": list(self.guardrail_reports),
            "timeline": list(self.timeline),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunReport":
        return cls(
            version=data["version"],
            generated_at=data["generated_at"],
            summary=RunReportSummary.from_dict(data["summary"]),
            events=list(data.get("events", [])),
            logs=list(data.get("logs", [])),
            artifacts=list(data.get("artifacts", [])),
            evidence=list(data.get("evidence", [])),
            gates=list(data.get("gates", [])),
            drrs=list(data.get("drrs", [])),
            validation_results=list(data.get("validation_results", [])),
            guardrail_reports=list(data.get("guardrail_reports", [])),
            timeline=list(data.get("timeline", [])),
        )
