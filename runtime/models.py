from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class WorkflowSpec:
    module: str
    workflow: str
    phase: str
    quint: str
    telis: str
    validation: str
    human: str
    evidence: str
    artifacts: List[str]
    scope: str
    path: str

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "WorkflowSpec":
        return cls(
            module=data["module"],
            workflow=data["workflow"],
            phase=data["phase"],
            quint=data["quint"],
            telis=data["telis"],
            validation=data["validation"],
            human=data["human"],
            evidence=data["evidence"],
            artifacts=list(data.get("artifacts", [])),
            scope=data["scope"],
            path=data["path"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StepSpec:
    id: str
    name: str
    description: str
    phase: str
    inputs: Dict[str, Any]
    outputs: List[str]
    templates: List[str]
    tools: List[Dict[str, Any]]
    validation: str
    evidence: str
    human_gate: str
    retries: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepSpec":
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            phase=data.get("phase", ""),
            inputs=dict(data.get("inputs", {})),
            outputs=list(data.get("outputs", [])),
            templates=list(data.get("templates", [])),
            tools=list(data.get("tools", [])),
            validation=data.get("validation", ""),
            evidence=data.get("evidence", ""),
            human_gate=data.get("human_gate", ""),
            retries=dict(data.get("retries", {})),
        )


@dataclass
class RunStep:
    name: str
    status: str = "pending"
    attempts: int = 0
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    error: Optional[str] = None
    step_id: Optional[str] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunStep":
        return cls(
            name=data["name"],
            status=data.get("status", "pending"),
            attempts=int(data.get("attempts", 0)),
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            error=data.get("error"),
            step_id=data.get("step_id"),
            inputs=dict(data.get("inputs", {})),
            outputs=list(data.get("outputs", [])),
            tools=list(data.get("tools", [])),
        )


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    path: str
    artifact_type: str
    checksum: str
    workflow: str
    created_at: str
    step: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactRecord":
        return cls(
            artifact_id=data["artifact_id"],
            path=data["path"],
            artifact_type=data["artifact_type"],
            checksum=data["checksum"],
            workflow=data["workflow"],
            created_at=data["created_at"],
            step=data.get("step"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ArtifactIndex:
    run_id: str
    artifacts: List[ArtifactRecord] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactIndex":
        return cls(
            run_id=data["run_id"],
            artifacts=[ArtifactRecord.from_dict(item) for item in data.get("artifacts", [])],
            updated_at=data.get("updated_at", ""),
        )


@dataclass(frozen=True)
class EvidenceLink:
    id: str
    claim: str
    level: str
    source: str
    date: str
    valid_until: str
    congruence: str
    reliability: float
    wlnk: float
    carrier_ref: str
    artifacts: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceLink":
        return cls(
            id=data["id"],
            claim=data["claim"],
            level=data["level"],
            source=data["source"],
            date=data.get("date", ""),
            valid_until=data.get("valid_until", ""),
            congruence=data.get("congruence", ""),
            reliability=float(data.get("reliability", 0.0)),
            wlnk=float(data.get("wlnk", 0.0)),
            carrier_ref=data.get("carrier_ref", ""),
            artifacts=list(data.get("artifacts", [])),
            notes=data.get("notes", ""),
        )


@dataclass(frozen=True)
class HumanGate:
    gate_id: str
    status: str
    required: bool = True
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanGate":
        return cls(
            gate_id=data["gate_id"],
            status=data["status"],
            required=bool(data.get("required", True)),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            notes=data.get("notes", ""),
        )


@dataclass(frozen=True)
class EventRecord:
    event_type: str
    run_id: str
    timestamp: str
    payload: Dict[str, Any] = field(default_factory=dict)
    step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
            "step_id": self.step_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventRecord":
        return cls(
            event_type=data["event_type"],
            run_id=data["run_id"],
            timestamp=data["timestamp"],
            payload=dict(data.get("payload", {})),
            step_id=data.get("step_id"),
        )


@dataclass
class RunManifest:
    run_id: str
    workflow: WorkflowSpec
    status: str
    step_specs: List[StepSpec] = field(default_factory=list)
    steps: List[RunStep] = field(default_factory=list)
    current_step: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow": self.workflow.to_dict(),
            "status": self.status,
            "step_specs": [step.to_dict() for step in self.step_specs],
            "steps": [step.to_dict() for step in self.steps],
            "current_step": self.current_step,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunManifest":
        return cls(
            run_id=data["run_id"],
            workflow=WorkflowSpec.from_mapping(data["workflow"]),
            status=data["status"],
            step_specs=[StepSpec.from_dict(item) for item in data.get("step_specs", [])],
            steps=[RunStep.from_dict(item) for item in data.get("steps", [])],
            current_step=int(data.get("current_step", 0)),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
