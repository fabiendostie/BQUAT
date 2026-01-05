from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """Canonical event types for workflow state transitions."""

    # Workflow lifecycle
    WORKFLOW_REQUESTED = "WorkflowRequested"
    WORKFLOW_STARTED = "WorkflowStarted"
    WORKFLOW_COMPLETED = "WorkflowCompleted"
    WORKFLOW_FAILED = "WorkflowFailed"
    WORKFLOW_BLOCKED = "WorkflowBlocked"
    WORKFLOW_RESUMED = "WorkflowResumed"

    # Step lifecycle
    STEP_REQUESTED = "StepRequested"
    STEP_STARTED = "WorkflowStepStarted"
    STEP_COMPLETED = "WorkflowStepCompleted"
    STEP_FAILED = "WorkflowStepFailed"
    STEP_BLOCKED = "StepBlocked"
    STEP_RETRY = "StepRetry"

    # Gate events
    GATE_REQUIRED = "HumanGateRequired"
    GATE_APPROVED = "HumanGateApproved"
    GATE_REJECTED = "HumanGateRejected"
    GATE_DRR_CREATED = "GateDrrCreated"

    # Tool events
    TOOL_STARTED = "ToolStarted"
    TOOL_COMPLETED = "ToolCompleted"
    TOOL_FAILED = "ToolFailed"
    TOOL_BLOCKED = "ToolBlocked"
    TOOL_APPROVAL_REQUIRED = "ToolApprovalRequired"

    # Guardrail events
    GUARDRAIL_STARTED = "GuardrailStarted"
    GUARDRAIL_PASSED = "GuardrailPassed"
    GUARDRAIL_FAILED = "GuardrailFailed"

    # Validation events
    VALIDATION_STARTED = "ValidationStarted"
    VALIDATION_PASSED = "ValidationPassed"
    VALIDATION_FAILED = "ValidationFailed"

    # Evidence events
    EVIDENCE_RECORDED = "EvidenceRecorded"
    EVIDENCE_INVALIDATED = "EvidenceInvalidated"
    EVIDENCE_DRIFTED = "EvidenceDrifted"

    # Artifact events
    ARTIFACT_CREATED = "ArtifactCreated"
    ARTIFACT_INDEXED = "ArtifactIndexed"

    # Context events
    CONTEXT_RESOLVED = "ContextResolved"
    CONTEXT_FINGERPRINT_CREATED = "ContextFingerprintCreated"
    CONTEXT_SNAPSHOT_CREATED = "ContextSnapshotCreated"

    # Plugin events
    PLUGIN_POLICY_EVALUATED = "PluginPolicyEvaluated"
    PLUGIN_HOOK_EXECUTED = "PluginHookExecuted"


@dataclass(frozen=True)
class BusEvent:
    """Immutable event published to the event bus."""

    event_type: str
    run_id: str
    timestamp: str
    payload: Dict[str, Any] = field(default_factory=dict)
    step_id: Optional[str] = None
    source: str = "engine"
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "event_type": self.event_type,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
            "source": self.source,
        }
        if self.step_id:
            result["step_id"] = self.step_id
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BusEvent:
        return cls(
            event_type=data.get("event_type", ""),
            run_id=data.get("run_id", ""),
            timestamp=data.get("timestamp", ""),
            payload=dict(data.get("payload", {})),
            step_id=data.get("step_id"),
            source=data.get("source", "engine"),
            correlation_id=data.get("correlation_id"),
        )


# Event categories for filtering
EVENT_CATEGORIES: Dict[str, list[str]] = {
    "workflow": [
        EventType.WORKFLOW_REQUESTED.value,
        EventType.WORKFLOW_STARTED.value,
        EventType.WORKFLOW_COMPLETED.value,
        EventType.WORKFLOW_FAILED.value,
        EventType.WORKFLOW_BLOCKED.value,
        EventType.WORKFLOW_RESUMED.value,
    ],
    "step": [
        EventType.STEP_REQUESTED.value,
        EventType.STEP_STARTED.value,
        EventType.STEP_COMPLETED.value,
        EventType.STEP_FAILED.value,
        EventType.STEP_BLOCKED.value,
        EventType.STEP_RETRY.value,
    ],
    "gate": [
        EventType.GATE_REQUIRED.value,
        EventType.GATE_APPROVED.value,
        EventType.GATE_REJECTED.value,
        EventType.GATE_DRR_CREATED.value,
    ],
    "tool": [
        EventType.TOOL_STARTED.value,
        EventType.TOOL_COMPLETED.value,
        EventType.TOOL_FAILED.value,
        EventType.TOOL_BLOCKED.value,
        EventType.TOOL_APPROVAL_REQUIRED.value,
    ],
    "guardrail": [
        EventType.GUARDRAIL_STARTED.value,
        EventType.GUARDRAIL_PASSED.value,
        EventType.GUARDRAIL_FAILED.value,
    ],
    "validation": [
        EventType.VALIDATION_STARTED.value,
        EventType.VALIDATION_PASSED.value,
        EventType.VALIDATION_FAILED.value,
    ],
    "evidence": [
        EventType.EVIDENCE_RECORDED.value,
        EventType.EVIDENCE_INVALIDATED.value,
        EventType.EVIDENCE_DRIFTED.value,
    ],
    "artifact": [
        EventType.ARTIFACT_CREATED.value,
        EventType.ARTIFACT_INDEXED.value,
    ],
    "context": [
        EventType.CONTEXT_RESOLVED.value,
        EventType.CONTEXT_FINGERPRINT_CREATED.value,
        EventType.CONTEXT_SNAPSHOT_CREATED.value,
    ],
    "plugin": [
        EventType.PLUGIN_POLICY_EVALUATED.value,
        EventType.PLUGIN_HOOK_EXECUTED.value,
    ],
}
