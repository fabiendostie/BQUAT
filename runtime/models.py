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


@dataclass
class RunStep:
    name: str
    status: str = "pending"
    attempts: int = 0
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunManifest:
    run_id: str
    workflow: WorkflowSpec
    status: str
    steps: List[RunStep] = field(default_factory=list)
    current_step: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow": self.workflow.to_dict(),
            "status": self.status,
            "steps": [step.to_dict() for step in self.steps],
            "current_step": self.current_step,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
