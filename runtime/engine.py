from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from runtime import agents as agent_registry
from runtime import config as runtime_config
from runtime import gates, models, storage, workflow_parser
from runtime.events.bus import EventBus
from runtime.events.handlers import (
    JsonPersistenceHandler,
    LoggingHandler,
    ObservabilityBridgeHandler,
    TimelineHandler,
)
from runtime.events.types import BusEvent
from runtime.failure.isolation import FailureIsolator
from runtime.guardrails import checks as guardrails
from runtime.guardrails import concurrent as guardrails_concurrent
from runtime.logging import EventEmitter, StructuredLogger
from runtime.plugins.manager import PluginManager
from runtime.quint import drift as quint_drift
from runtime.quint import fingerprint as quint_fingerprint
from runtime.quint import snapshot as quint_snapshot
from runtime.telis.manager import TelisPolicyEngine
from runtime.time_provider import get_current_time
from runtime.tools import file_io
from runtime.tools import validation as validation_tools
from runtime.tools.pipeline import ToolApprovalRequired, run_tool_calls


class StepExecutor:
    def execute(self, step: Dict[str, Any], context: Dict[str, Any]) -> None:
        raise NotImplementedError


class NoopExecutor(StepExecutor):
    def execute(self, step: Dict[str, Any], context: Dict[str, Any]) -> None:
        return None


def utc_now() -> str:
    return get_current_time()


def generate_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run-{stamp}-{uuid4().hex[:8]}"


def default_mapping_path() -> Path:
    return (
        Path(__file__).resolve().parents[1] / "methodology" / "mapping" / "integration-mapping.json"
    )


def load_mapping_records(path: Optional[Path] = None) -> List[models.WorkflowSpec]:
    target = path or default_mapping_path()
    data = json.loads(target.read_text(encoding="ascii"))
    return [models.WorkflowSpec.from_mapping(item) for item in data.get("records", [])]


def _default_steps() -> List[Dict[str, Any]]:
    step = models.RunStep(name="execute")
    return [step.to_dict()]


def _split_artifacts(artifacts: List[str]) -> Tuple[List[str], List[str]]:
    outputs: List[str] = []
    templates: List[str] = []
    for artifact in artifacts:
        if artifact.startswith("template:"):
            templates.append(artifact.split("template:", 1)[1])
        else:
            outputs.append(artifact)
    return outputs, templates


_ALLOWED_OUTPUT_PLACEHOLDERS = ("{output_folder}", "{bmb_creations_output_folder}")
_VALIDATION_TARGET_KEYS = ("validation_targets", "validation_paths", "validation_files")
_STEP_STATUSES = {"pending", "running", "blocked", "failed", "completed"}
_STEP_TRANSITIONS = {
    "pending": {"running"},
    "running": {"completed", "failed", "blocked"},
    "failed": {"running"},
    "blocked": {"running"},
    "completed": set(),
}


def _transition_step(step: Dict[str, Any], status: str) -> None:
    current = step.get("status") or "pending"
    if current == status:
        return
    if current not in _STEP_TRANSITIONS:
        raise ValueError(f"unknown step status: {current}")
    if status not in _STEP_STATUSES:
        raise ValueError(f"invalid step status: {status}")
    if status not in _STEP_TRANSITIONS[current]:
        raise ValueError(f"invalid step transition: {current} -> {status}")
    step["status"] = status


def _validation_policy_stages(policy: str) -> List[str]:
    normalized = policy.strip().lower()
    if not normalized or normalized in {"n/a", "na", "none"}:
        return []
    if "ast" in normalized or "type" in normalized or "lint" in normalized:
        return ["ast", "typecheck", "lint"]
    if "template" in normalized or "schema" in normalized or "format" in normalized:
        return ["ast"]
    return []


def _output_layout_issues(outputs: List[str]) -> List[str]:
    issues: List[str] = []
    for output in outputs:
        if not output:
            issues.append("output path is empty")
            continue
        if output.startswith("id:"):
            continue
        if output.startswith("template:"):
            issues.append(f"template artifact listed as output: {output}")
            continue
        if any(token in output for token in _ALLOWED_OUTPUT_PLACEHOLDERS):
            continue
        issues.append(f"output path missing output folder placeholder: {output}")
    return issues


def _init_event_bus(run_dir: Path, run_id: str, config: Dict[str, Any]) -> EventBus:
    bus = EventBus()
    bus.subscribe(JsonPersistenceHandler(run_dir))
    bus.subscribe(TimelineHandler(run_dir))

    observability_cfg = config.get("observability", {})
    if observability_cfg.get("enabled", True) and observability_cfg.get("events", {}).get(
        "enabled", True
    ):
        emitter = EventEmitter(run_id)

        def emit(event_type: str, payload: Dict[str, Any]) -> None:
            source = str(payload.get("source", "engine"))
            step_id = payload.get("step_id")
            emitter.emit(event_type, source, payload, step_id=step_id)

        bus.subscribe(ObservabilityBridgeHandler(emit))

    logging_cfg = observability_cfg.get("logging", {})
    if observability_cfg.get("enabled", True) and logging_cfg.get("enabled", True):
        logger = StructuredLogger(
            run_dir,
            run_id,
            min_level=str(logging_cfg.get("level", "info")),
        )

        def log(level: str, event_type: str, payload: Dict[str, Any]) -> None:
            logger.log(level, "event", event_type, step_id=payload.get("step_id"), payload=payload)

        bus.subscribe(LoggingHandler(log))

    return bus


def _append_event(
    run_dir: Path,
    event_type: str,
    run_id: str,
    payload: Optional[Dict[str, Any]] = None,
    step_id: Optional[str] = None,
    bus: Optional[EventBus] = None,
    source: str = "engine",
) -> None:
    if bus is not None:
        event = BusEvent(
            event_type=event_type,
            run_id=run_id,
            timestamp=utc_now(),
            payload=dict(payload or {}),
            step_id=step_id,
            source=source,
        )
        bus.publish(event)
        return
    events = storage.read_events(run_dir)
    entries: List[Dict[str, Any]] = events.get("events", [])
    record = models.EventRecord(
        event_type=event_type,
        run_id=run_id,
        timestamp=utc_now(),
        payload=dict(payload or {}),
        step_id=step_id,
    )
    entries.append(record.to_dict())
    events["events"] = entries
    storage.write_events(run_dir, events)
    storage.update_timeline(run_dir)


def _artifact_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_id(path: str, checksum: str, artifact_type: str) -> str:
    basis = f"{path}:{checksum}:{artifact_type}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _resolve_artifact_path(value: str, root: Path, run_dir: Path) -> Optional[Path]:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned or "{" in cleaned:
        return None
    if cleaned.startswith("template:") or cleaned.startswith("id:"):
        return None
    for base in (root, run_dir):
        try:
            resolved = file_io.resolve_path(cleaned, root=base)
        except ValueError:
            continue
        if resolved.exists() and resolved.is_file():
            return resolved
    return None


def _evidence_ids_for_artifact(
    evidence_payload: Dict[str, Any], artifact_id: str, path: str
) -> List[str]:
    evidence_ids: List[str] = []
    for record in evidence_payload.get("evidence", []):
        if not isinstance(record, dict):
            continue
        artifacts = record.get("artifacts", [])
        if not isinstance(artifacts, list):
            continue
        if artifact_id in artifacts or path in artifacts:
            evidence_id = record.get("id")
            if evidence_id:
                evidence_ids.append(str(evidence_id))
    return evidence_ids


def _gate_metadata(gates_payload: Dict[str, Any], gate_id: str) -> Dict[str, Any]:
    for gate in gates_payload.get("gates", []):
        if gate.get("gate_id") == gate_id:
            return {
                "gate_id": gate.get("gate_id", ""),
                "status": gate.get("status", ""),
                "required": gate.get("required", False),
                "reason": gate.get("reason"),
                "phase": gate.get("phase"),
                "workflow": gate.get("workflow"),
                "recorded_at": gate.get("recorded_at"),
                "approved_by": gate.get("approved_by"),
                "approved_at": gate.get("approved_at"),
            }
    return {}


def _update_artifact_index(
    run_dir: Path,
    manifest: Dict[str, Any],
    step: Dict[str, Any],
    step_spec: Optional[models.StepSpec],
) -> None:
    root = runtime_config.project_root_from_here()
    index = storage.read_artifact_index(run_dir)
    artifacts: List[Dict[str, Any]] = index.get("artifacts", [])
    existing = {(item.get("path"), item.get("checksum")) for item in artifacts}
    workflow = manifest.get("workflow", {})
    module_name = str(workflow.get("module", ""))
    workflow_name = str(workflow.get("workflow", ""))
    workflow_id = f"{module_name}/{workflow_name}"
    gate_id = ""
    if module_name and workflow_name:
        gate_id = f"{module_name}:{workflow_name}:hitl"
    evidence_payload = storage.read_evidence_links(run_dir)
    gate_payload = storage.read_human_gates(run_dir)
    gate_info = _gate_metadata(gate_payload, gate_id) if gate_id else {}
    created_at = step.get("ended_at") or utc_now()
    step_id = step.get("step_id")

    candidates: List[Tuple[str, str]] = []
    for output in step.get("outputs", []):
        if isinstance(output, str):
            candidates.append((output, "output"))
    if step_spec:
        for template in step_spec.templates:
            if isinstance(template, str):
                candidates.append((template, "template"))

    for value, artifact_type in candidates:
        resolved = _resolve_artifact_path(value, root, run_dir)
        if not resolved:
            continue
        rel_path = (
            str(resolved.relative_to(root)) if resolved.is_relative_to(root) else str(resolved)
        )
        checksum = _artifact_checksum(resolved)
        key = (rel_path, checksum)
        if key in existing:
            continue
        artifact_id = _artifact_id(rel_path, checksum, artifact_type)
        metadata = {"step_name": step.get("name", "")}
        evidence_ids = _evidence_ids_for_artifact(evidence_payload, artifact_id, rel_path)
        if evidence_ids:
            metadata["evidence_ids"] = evidence_ids
        if gate_info:
            metadata["gate"] = gate_info
        record = models.ArtifactRecord(
            artifact_id=artifact_id,
            path=rel_path,
            artifact_type=artifact_type,
            checksum=checksum,
            workflow=workflow_id,
            created_at=created_at,
            step=step_id,
            metadata=metadata,
        )
        artifacts.append(record.to_dict())
        existing.add(key)

    index["artifacts"] = artifacts
    index["updated_at"] = utc_now()
    storage.write_artifact_index(run_dir, index)


def _collect_validation_targets(
    step: Dict[str, Any],
    step_spec: Optional[models.StepSpec],
    root: Path,
) -> Tuple[List[str], List[str]]:
    inputs = step_spec.inputs if step_spec else step.get("inputs", {})
    raw_targets: List[str] = []
    for key in _VALIDATION_TARGET_KEYS:
        value = inputs.get(key)
        if not value:
            continue
        if isinstance(value, list):
            raw_targets.extend([str(item) for item in value])
        elif isinstance(value, str):
            raw_targets.append(value)
    issues: List[str] = []
    targets: List[str] = []
    for target in raw_targets:
        try:
            resolved = file_io.resolve_path(target, root=root)
        except ValueError:
            issues.append(f"validation target outside project root: {target}")
            continue
        if not resolved.exists():
            issues.append(f"validation target missing: {target}")
            continue
        if resolved.is_dir():
            issues.append(f"validation target is a directory: {target}")
            continue
        targets.append(str(resolved))
    outputs = step_spec.outputs if step_spec else step.get("outputs", [])
    for output in outputs:
        if not isinstance(output, str):
            continue
        if output.startswith("id:") or output.startswith("template:"):
            continue
        if "{" in output:
            continue
        try:
            resolved = file_io.resolve_path(output, root=root)
        except ValueError:
            continue
        if resolved.exists() and resolved.is_file():
            targets.append(str(resolved))
    return targets, issues


def _validation_error_message(report: Dict[str, Any]) -> str:
    issues = report.get("issues", [])
    if issues:
        return "; ".join(issues)
    failed_targets = [
        item.get("target") for item in report.get("results", []) if item.get("status") == "failed"
    ]
    if failed_targets:
        return f"failed targets: {', '.join(failed_targets)}"
    return "validation failed"


def _run_validation_gate(
    step: Dict[str, Any],
    step_spec: Optional[models.StepSpec],
) -> Optional[Dict[str, Any]]:
    if not step_spec:
        return None
    policy = step_spec.validation or ""
    stages = _validation_policy_stages(policy)
    issues = _output_layout_issues(step_spec.outputs)
    root = runtime_config.project_root_from_here()
    targets, target_issues = _collect_validation_targets(step, step_spec, root)
    issues.extend(target_issues)
    results: List[Dict[str, Any]] = []
    if stages and targets:
        for target in targets:
            summary = validation_tools.run_validation_pipeline(
                target,
                root=root,
                stages=stages,
            )
            results.append(
                {
                    "target": target,
                    "status": summary.status,
                    "results": [item.to_dict() for item in summary.results],
                }
            )
    statuses = [item.get("status") for item in results]
    if issues or "failed" in statuses:
        status = "failed"
    elif "passed" in statuses:
        status = "passed"
    else:
        status = "skipped"
    return {
        "policy": policy,
        "status": status,
        "issues": issues,
        "targets": targets,
        "stages": stages,
        "results": results,
    }


def _workflow_path(spec: models.WorkflowSpec) -> Optional[Path]:
    if not spec.path:
        return None
    root = runtime_config.project_root_from_here()
    bmad_root = root / "BMAD-METHOD"
    return bmad_root / spec.path


def _step_specs_for_workflow(
    spec: models.WorkflowSpec, config: Dict[str, Any]
) -> List[models.StepSpec]:
    workflow_path = _workflow_path(spec)
    if not workflow_path or not workflow_path.exists():
        return []
    steps = workflow_parser.parse_workflow_steps(workflow_path)
    if not steps:
        return []
    outputs, templates = _split_artifacts(spec.artifacts)
    retries = {"max": _max_retries(config), "backoff_seconds": 0}
    enriched: List[models.StepSpec] = []
    last_idx = len(steps) - 1
    for idx, step in enumerate(steps):
        step_outputs = list(step.outputs)
        step_templates = list(step.templates)
        if idx == last_idx:
            if not step_outputs:
                step_outputs = list(outputs)
            if not step_templates:
                step_templates = list(templates)
        enriched.append(
            models.StepSpec(
                id=step.id,
                name=step.name,
                description=step.description,
                phase=spec.phase,
                inputs=dict(step.inputs),
                outputs=step_outputs,
                templates=step_templates,
                tools=list(step.tools),
                validation=spec.validation,
                evidence=spec.evidence,
                human_gate=spec.human,
                retries=retries,
            )
        )
    return enriched


def _run_steps_from_specs(step_specs: List[models.StepSpec]) -> List[models.RunStep]:
    steps: List[models.RunStep] = []
    for spec in step_specs:
        step = models.RunStep(
            name=spec.name or spec.id,
            step_id=spec.id,
            inputs=dict(spec.inputs),
            outputs=list(spec.outputs),
            tools=[],
        )
        steps.append(step)
    return steps


def _ensure_steps(manifest: Dict[str, Any]) -> None:
    if not manifest.get("steps"):
        step_specs = manifest.get("step_specs", [])
        if step_specs:
            parsed = [models.StepSpec.from_dict(item) for item in step_specs]
            manifest["steps"] = [step.to_dict() for step in _run_steps_from_specs(parsed)]
        else:
            manifest["steps"] = _default_steps()
        manifest["current_step"] = 0


def _resume_start_index(steps: List[Dict[str, Any]]) -> int:
    for idx, step in enumerate(steps):
        if step.get("status") != "completed":
            return idx
    return len(steps)


def _step_timeout_seconds(config: Dict[str, Any]) -> int:
    runtime_cfg = config.get("runtime", {})
    return int(runtime_cfg.get("step_timeout_seconds", 1800))


def _max_retries(config: Dict[str, Any]) -> int:
    runtime_cfg = config.get("runtime", {})
    return int(runtime_cfg.get("max_retries", 0))


def _step_retry_policy(
    step: Dict[str, Any],
    step_spec: Optional[models.StepSpec],
    config: Dict[str, Any],
) -> Tuple[int, int]:
    retries: Dict[str, Any] = {}
    if step_spec:
        retries = dict(step_spec.retries)
    elif isinstance(step.get("retries"), dict):
        retries = dict(step.get("retries", {}))
    max_retries = retries.get("max", _max_retries(config))
    backoff_seconds = retries.get("backoff_seconds", 0)
    return max(0, int(max_retries)), max(0, int(backoff_seconds))


def _isolate_step_failures(config: Dict[str, Any]) -> bool:
    failure_cfg = config.get("failure_isolation", {})
    return bool(failure_cfg.get("isolate_step_failures", False))


def _record_isolated_failure(
    manifest: Dict[str, Any],
    step: Dict[str, Any],
    error: str,
    tool_name: str,
    impact: Optional[Dict[str, Any]] = None,
) -> None:
    entry = {
        "step_id": step.get("step_id") or step.get("name", ""),
        "step_name": step.get("name", ""),
        "error": error,
        "tool_name": tool_name,
        "recorded_at": utc_now(),
    }
    if impact:
        entry["impact"] = dict(impact)
    failures = manifest.setdefault("isolated_failures", [])
    if isinstance(failures, list):
        failures.append(entry)


def _automation_allowed(spec: models.WorkflowSpec, config: Dict[str, Any]) -> bool:
    automation_cfg = config.get("automation", {})
    if automation_cfg.get("override"):
        return True
    phases = automation_cfg.get("phases")
    if not phases:
        return True
    return spec.phase in set(phases)


def _clear_manual_block(manifest: Dict[str, Any]) -> None:
    if manifest.get("blocked_reason") == "manual_phase":
        manifest.pop("blocked_reason", None)
        manifest.pop("blocked_phase", None)


def _clear_tool_block(manifest: Dict[str, Any]) -> None:
    if manifest.get("blocked_reason") == "tool_gate":
        manifest.pop("blocked_reason", None)
        manifest.pop("blocked_gate", None)
        manifest.pop("blocked_tool", None)


def _clear_human_block(manifest: Dict[str, Any]) -> None:
    if manifest.get("blocked_reason") == "human_gate":
        manifest.pop("blocked_reason", None)
        manifest.pop("blocked_gate", None)


def _gate_id(spec: models.WorkflowSpec) -> str:
    return f"{spec.module}:{spec.workflow}:hitl"


def _load_spec_from_manifest(manifest: Dict[str, Any]) -> models.WorkflowSpec:
    return models.WorkflowSpec.from_mapping(manifest["workflow"])


def _apply_agent_definition(manifest: Dict[str, Any], agent_name: str) -> None:
    registry = agent_registry.get_default_agent_registry()
    definition = registry.get(agent_name)
    if not definition:
        return
    manifest["agent"] = agent_name
    manifest["agent_tools"] = list(definition.tools)
    manifest["agent_instructions"] = dict(definition.instructions)


def _ensure_context_snapshot(
    run_dir: Path,
    manifest: Dict[str, Any],
    telis: Optional[TelisPolicyEngine],
    config: Dict[str, Any],
    event_bus: Optional[EventBus],
) -> None:
    if manifest.get("context_snapshot_id"):
        return
    snapshot = quint_snapshot.build_snapshot(manifest, run_dir, telis, config)
    store = quint_snapshot.SnapshotStore(run_dir)
    recorded = store.record(snapshot)
    manifest["context_snapshot_id"] = recorded.get("snapshot_id", "")
    storage.write_manifest(run_dir, manifest)
    _append_event(
        run_dir,
        "ContextSnapshotCreated",
        manifest.get("run_id", run_dir.name),
        {"snapshot_id": recorded.get("snapshot_id")},
        bus=event_bus,
    )


def _evaluate_context_drift(
    run_dir: Path,
    manifest: Dict[str, Any],
    telis: Optional[TelisPolicyEngine],
    config: Dict[str, Any],
    event_bus: Optional[EventBus],
) -> None:
    snapshot_id = manifest.get("context_snapshot_id")
    if not snapshot_id:
        return
    store = quint_snapshot.SnapshotStore(run_dir)
    stored = store.get(snapshot_id)
    if not stored:
        return
    base_snapshot = quint_snapshot.ContextSnapshot.from_dict(stored)
    current_snapshot = quint_snapshot.build_snapshot(manifest, run_dir, telis, config)
    store.record(current_snapshot)
    _append_event(
        run_dir,
        "ContextSnapshotCreated",
        manifest.get("run_id", run_dir.name),
        {"snapshot_id": current_snapshot.snapshot_id},
        bus=event_bus,
    )
    drifts = quint_drift.detect_drift(base_snapshot, current_snapshot)
    if not drifts:
        return
    drift_store = quint_drift.DriftStore(run_dir)
    drift_store.record(drifts)
    quint_drift.mark_evidence_drifted(run_dir, drifts)
    _append_event(
        run_dir,
        "EvidenceDrifted",
        manifest.get("run_id", run_dir.name),
        {"drifts": [drift.to_dict() for drift in drifts]},
        bus=event_bus,
    )


def _record_human_gate(
    run_dir: Path,
    spec: models.WorkflowSpec,
    decision: gates.GateDecision,
    status: str,
    notes: str = "",
    approved_by: Optional[str] = None,
    approved_at: Optional[str] = None,
    event_bus: Optional[EventBus] = None,
) -> None:
    gates_payload = storage.read_human_gates(run_dir)
    existing_drr_id = None
    for gate in gates_payload.get("gates", []):
        if gate.get("gate_id") == _gate_id(spec):
            existing_drr_id = gate.get("drr_id")
            break
    if not existing_drr_id:
        evidence_payload = storage.read_evidence_links(run_dir)
        evidence_links = []
        for record in evidence_payload.get("evidence", []):
            if isinstance(record, dict) and record.get("id"):
                try:
                    evidence_links.append(models.EvidenceLink.from_dict(record))
                except Exception:  # noqa: BLE001, S110
                    continue
        drr_record = gates.record_gate_as_drr(
            run_dir=run_dir,
            gate_id=_gate_id(spec),
            phase=spec.phase,
            workflow=f"{spec.module}/{spec.workflow}",
            policy_reason=decision.reason,
            supporting_evidence=evidence_links,
            approved_by=approved_by,
            approval_notes=notes,
        )
        existing_drr_id = drr_record.decision_id
        _append_event(
            run_dir,
            "GateDrrCreated",
            run_dir.name,
            {"gate_id": _gate_id(spec), "drr_id": existing_drr_id},
            bus=event_bus,
        )
    gates_payload = gates.record_gate(
        gates_payload,
        _gate_id(spec),
        status,
        decision.required,
        decision.reason,
        spec.phase,
        f"{spec.module}/{spec.workflow}",
        utc_now(),
        approved_by=approved_by,
        approved_at=approved_at,
        notes=notes,
        drr_id=existing_drr_id,
    )
    storage.write_human_gates(run_dir, gates_payload)


class WorkflowEngine:
    def __init__(
        self,
        config: Dict[str, Any],
        mapping_records: List[models.WorkflowSpec],
        storage_root: Optional[Path] = None,
        plugins: Optional[PluginManager] = None,
        telis: Optional[TelisPolicyEngine] = None,
    ) -> None:
        self.config = config
        self.mapping = {(rec.module, rec.workflow): rec for rec in mapping_records}
        self.storage_root = storage_root or runtime_config.storage_root(config)
        self.plugins = plugins
        self.telis = telis or TelisPolicyEngine.from_config(config)

    def get_workflow_spec(self, module: str, workflow: str) -> models.WorkflowSpec:
        key = (module, workflow)
        if key not in self.mapping:
            raise KeyError(f"Workflow not found: {module}/{workflow}")
        return self.mapping[key]

    def _build_manifest(self, run_id: str, spec: models.WorkflowSpec) -> Dict[str, Any]:
        now = utc_now()
        step_specs = _step_specs_for_workflow(spec, self.config)
        steps = (
            _run_steps_from_specs(step_specs) if step_specs else [models.RunStep(name="execute")]
        )
        manifest = models.RunManifest(
            run_id=run_id,
            workflow=spec,
            status="pending",
            step_specs=step_specs,
            steps=steps,
            current_step=0,
            created_at=now,
            updated_at=now,
        )
        return manifest.to_dict()

    def _run_dir(self, run_id: str) -> Path:
        return storage.init_run_dir(self.storage_root, run_id)

    def create_run(
        self, module: str, workflow: str, run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        spec = self.get_workflow_spec(module, workflow)
        run_id = run_id or generate_run_id()
        run_dir = self._run_dir(run_id)
        manifest = self._build_manifest(run_id, spec)
        storage.write_manifest(run_dir, manifest)
        return manifest

    def approve_gate(
        self,
        run_id: str,
        approved_by: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        run_dir = self._run_dir(run_id)
        manifest = storage.read_manifest(run_dir)
        event_bus = _init_event_bus(run_dir, manifest["run_id"], self.config)
        spec = _load_spec_from_manifest(manifest)
        decision = gates.gate_required(
            spec.human,
            self.config,
            phase=spec.phase,
            workflow=spec.workflow,
        )
        approved_at = utc_now()
        approvals = storage.read_approvals(run_dir)
        approvals = gates.record_approval(
            approvals,
            _gate_id(spec),
            approved_by,
            approved_at,
            notes,
        )
        storage.write_approvals(run_dir, approvals)
        _record_human_gate(
            run_dir,
            spec,
            decision,
            status="approved",
            notes=notes,
            approved_by=approved_by,
            approved_at=approved_at,
            event_bus=event_bus,
        )
        _append_event(
            run_dir,
            "HumanGateApproved",
            manifest["run_id"],
            {"gate_id": _gate_id(spec), "approved_by": approved_by, "notes": notes},
            bus=event_bus,
        )
        return approvals

    def run(
        self,
        module: str,
        workflow: str,
        run_id: Optional[str] = None,
        executor: Optional[StepExecutor] = None,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if run_id:
            run_dir = self._run_dir(run_id)
            manifest = storage.read_manifest(run_dir)
            spec = _load_spec_from_manifest(manifest)
        else:
            spec = self.get_workflow_spec(module, workflow)
            run_id = generate_run_id()
            run_dir = self._run_dir(run_id)
            manifest = self._build_manifest(run_id, spec)

        if agent_name:
            _apply_agent_definition(manifest, agent_name)

        _ensure_steps(manifest)
        event_bus = _init_event_bus(run_dir, manifest["run_id"], self.config)
        _ensure_context_snapshot(run_dir, manifest, self.telis, self.config, event_bus)

        if not _automation_allowed(spec, self.config):
            manifest["status"] = "blocked"
            manifest["blocked_reason"] = "manual_phase"
            manifest["blocked_phase"] = spec.phase
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
            _append_event(
                run_dir,
                "WorkflowBlocked",
                manifest["run_id"],
                {"reason": "manual_phase", "phase": spec.phase},
                bus=event_bus,
            )
            if self.plugins:
                self.plugins.on_validation(manifest, "blocked")
            return manifest

        _clear_manual_block(manifest)
        _clear_tool_block(manifest)
        _clear_human_block(manifest)

        if self.plugins:
            decision = self.plugins.run_before_run_policy(
                manifest,
                config=self.config,
                run_dir=str(run_dir),
            )
            if not decision.allow:
                manifest["status"] = "blocked"
                manifest["blocked_reason"] = "policy"
                manifest["blocked_policy"] = decision.block_type or "policy"
                manifest["blocked_policy_reason"] = decision.reason
                manifest["blocked_policy_metadata"] = dict(decision.metadata)
                manifest["updated_at"] = utc_now()
                storage.write_manifest(run_dir, manifest)
                _append_event(
                    run_dir,
                    "WorkflowBlocked",
                    manifest["run_id"],
                    {
                        "reason": "policy",
                        "policy_reason": decision.reason,
                        "policy_type": decision.block_type,
                        "policy_metadata": decision.metadata,
                    },
                    bus=event_bus,
                )
                self.plugins.on_validation(manifest, "blocked")
                return manifest

        decision = gates.gate_required(
            spec.human,
            self.config,
            phase=spec.phase,
            workflow=spec.workflow,
        )
        approvals = storage.read_approvals(run_dir)
        if decision.required and not gates.has_approval(approvals, _gate_id(spec)):
            manifest["status"] = "blocked"
            manifest["blocked_reason"] = "human_gate"
            manifest["blocked_gate"] = _gate_id(spec)
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
            _record_human_gate(
                run_dir,
                spec,
                decision,
                status="blocked",
                event_bus=event_bus,
            )
            _append_event(
                run_dir,
                "HumanGateRequired",
                manifest["run_id"],
                {
                    "gate_id": _gate_id(spec),
                    "phase": spec.phase,
                    "workflow": f"{spec.module}/{spec.workflow}",
                    "reason": decision.reason,
                },
                bus=event_bus,
            )
            if self.plugins:
                self.plugins.run_data_hooks(
                    "gate_triggered",
                    manifest=manifest,
                    step=None,
                    config=self.config,
                    run_dir=str(run_dir),
                    payload={
                        "gate_id": _gate_id(spec),
                        "required": decision.required,
                        "reason": decision.reason,
                        "phase": spec.phase,
                        "workflow": f"{spec.module}/{spec.workflow}",
                    },
                )
            _append_event(
                run_dir,
                "WorkflowBlocked",
                manifest["run_id"],
                {"reason": "human_gate", "gate_id": _gate_id(spec)},
                bus=event_bus,
            )
            if self.plugins:
                self.plugins.on_validation(manifest, "blocked")
            return manifest

        if self.plugins:
            self.plugins.before_run(manifest)

        manifest["status"] = "running"
        manifest["updated_at"] = utc_now()
        storage.write_manifest(run_dir, manifest)
        _append_event(
            run_dir,
            "WorkflowStarted",
            manifest["run_id"],
            {"workflow": manifest["workflow"]},
            bus=event_bus,
        )
        if self.plugins:
            self.plugins.run_data_hooks(
                "run_started",
                manifest=manifest,
                step=None,
                config=self.config,
                run_dir=str(run_dir),
            )

        step_executor = executor or NoopExecutor()
        return self._execute_steps(run_dir, manifest, step_executor, event_bus)

    def resume(
        self,
        run_id: str,
        executor: Optional[StepExecutor] = None,
        agent_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_dir = self._run_dir(run_id)
        manifest = storage.read_manifest(run_dir)
        spec = _load_spec_from_manifest(manifest)

        if agent_name:
            _apply_agent_definition(manifest, agent_name)

        _ensure_steps(manifest)
        event_bus = _init_event_bus(run_dir, manifest["run_id"], self.config)
        _ensure_context_snapshot(run_dir, manifest, self.telis, self.config, event_bus)

        if not _automation_allowed(spec, self.config):
            manifest["status"] = "blocked"
            manifest["blocked_reason"] = "manual_phase"
            manifest["blocked_phase"] = spec.phase
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
            _append_event(
                run_dir,
                "WorkflowBlocked",
                manifest["run_id"],
                {"reason": "manual_phase", "phase": spec.phase},
                bus=event_bus,
            )
            if self.plugins:
                self.plugins.on_validation(manifest, "blocked")
            return manifest

        _clear_manual_block(manifest)
        _clear_tool_block(manifest)
        _clear_human_block(manifest)

        if self.plugins:
            decision = self.plugins.run_before_run_policy(
                manifest,
                config=self.config,
                run_dir=str(run_dir),
            )
            if not decision.allow:
                manifest["status"] = "blocked"
                manifest["blocked_reason"] = "policy"
                manifest["blocked_policy"] = decision.block_type or "policy"
                manifest["blocked_policy_reason"] = decision.reason
                manifest["blocked_policy_metadata"] = dict(decision.metadata)
                manifest["updated_at"] = utc_now()
                storage.write_manifest(run_dir, manifest)
                _append_event(
                    run_dir,
                    "WorkflowBlocked",
                    manifest["run_id"],
                    {
                        "reason": "policy",
                        "policy_reason": decision.reason,
                        "policy_type": decision.block_type,
                        "policy_metadata": decision.metadata,
                    },
                    bus=event_bus,
                )
                self.plugins.on_validation(manifest, "blocked")
                return manifest

        decision = gates.gate_required(
            spec.human,
            self.config,
            phase=spec.phase,
            workflow=spec.workflow,
        )
        approvals = storage.read_approvals(run_dir)
        if decision.required and not gates.has_approval(approvals, _gate_id(spec)):
            manifest["status"] = "blocked"
            manifest["blocked_reason"] = "human_gate"
            manifest["blocked_gate"] = _gate_id(spec)
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
            _record_human_gate(
                run_dir,
                spec,
                decision,
                status="blocked",
                event_bus=event_bus,
            )
            _append_event(
                run_dir,
                "HumanGateRequired",
                manifest["run_id"],
                {
                    "gate_id": _gate_id(spec),
                    "phase": spec.phase,
                    "workflow": f"{spec.module}/{spec.workflow}",
                    "reason": decision.reason,
                },
                bus=event_bus,
            )
            if self.plugins:
                self.plugins.run_data_hooks(
                    "gate_triggered",
                    manifest=manifest,
                    step=None,
                    config=self.config,
                    run_dir=str(run_dir),
                    payload={
                        "gate_id": _gate_id(spec),
                        "required": decision.required,
                        "reason": decision.reason,
                        "phase": spec.phase,
                        "workflow": f"{spec.module}/{spec.workflow}",
                    },
                )
            _append_event(
                run_dir,
                "WorkflowBlocked",
                manifest["run_id"],
                {"reason": "human_gate", "gate_id": _gate_id(spec)},
                bus=event_bus,
            )
            if self.plugins:
                self.plugins.on_validation(manifest, "blocked")
            return manifest

        if self.plugins:
            self.plugins.before_run(manifest)

        manifest["status"] = "running"
        manifest["updated_at"] = utc_now()
        storage.write_manifest(run_dir, manifest)
        _append_event(
            run_dir,
            "WorkflowResumed",
            manifest["run_id"],
            {"workflow": manifest["workflow"]},
            bus=event_bus,
        )
        if self.plugins:
            self.plugins.run_data_hooks(
                "run_started",
                manifest=manifest,
                step=None,
                config=self.config,
                run_dir=str(run_dir),
            )

        step_executor = executor or NoopExecutor()
        return self._execute_steps(run_dir, manifest, step_executor, event_bus)

    def _execute_steps(
        self,
        run_dir: Path,
        manifest: Dict[str, Any],
        executor: StepExecutor,
        event_bus: Optional[EventBus] = None,
    ) -> Dict[str, Any]:
        steps = manifest.get("steps", [])
        start_idx = _resume_start_index(steps)
        if start_idx != manifest.get("current_step", 0):
            manifest["current_step"] = start_idx
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
        spec_list = [models.StepSpec.from_dict(item) for item in manifest.get("step_specs", [])]
        spec_by_id = {spec.id: spec for spec in spec_list}
        timeout_seconds = _step_timeout_seconds(self.config)
        allowed_tools: Optional[List[str]] = None
        agent_tools = manifest.get("agent_tools")
        if isinstance(agent_tools, list) and agent_tools:
            allowed_tools = [str(item) for item in agent_tools]

        for idx in range(start_idx, len(steps)):
            step = steps[idx]
            if step.get("status") == "completed":
                continue
            manifest["current_step"] = idx
            step_spec = None
            step_id = step.get("step_id")
            if step_id:
                step_spec = spec_by_id.get(step_id)
            if not step_spec and idx < len(spec_list):
                step_spec = spec_list[idx]
            if step_spec:
                if not step.get("inputs"):
                    step["inputs"] = dict(step_spec.inputs)
                if not step.get("outputs"):
                    step["outputs"] = list(step_spec.outputs)
            max_retries, backoff_seconds = _step_retry_policy(step, step_spec, self.config)
            attempts = int(step.get("attempts", 0))
            while attempts <= max_retries:
                if self.plugins:
                    decision = self.plugins.run_before_step_policy(
                        step,
                        manifest,
                        config=self.config,
                        run_dir=str(run_dir),
                    )
                    if not decision.allow:
                        _transition_step(step, "blocked")
                        step["ended_at"] = utc_now()
                        step["error"] = decision.reason or "policy blocked"
                        manifest["status"] = "blocked"
                        manifest["blocked_reason"] = "policy"
                        manifest["blocked_policy"] = decision.block_type or "policy"
                        manifest["blocked_policy_reason"] = decision.reason
                        manifest["blocked_policy_metadata"] = dict(decision.metadata)
                        manifest["updated_at"] = utc_now()
                        storage.write_manifest(run_dir, manifest)
                        _append_event(
                            run_dir,
                            "WorkflowStepBlocked",
                            manifest["run_id"],
                            {"step": step.get("name"), "reason": "policy"},
                            step_id=step_id,
                            bus=event_bus,
                        )
                        _append_event(
                            run_dir,
                            "WorkflowBlocked",
                            manifest["run_id"],
                            {"reason": "policy", "policy_reason": decision.reason},
                            bus=event_bus,
                        )
                        self.plugins.on_validation(manifest, "blocked")
                        return manifest
                attempts += 1
                step["attempts"] = attempts
                _transition_step(step, "running")
                step["started_at"] = utc_now()
                manifest["updated_at"] = utc_now()
                storage.write_manifest(run_dir, manifest)
                _append_event(
                    run_dir,
                    "WorkflowStepStarted",
                    manifest["run_id"],
                    {"step": step.get("name"), "attempt": attempts},
                    step_id=step_id,
                    bus=event_bus,
                )
                if self.plugins:
                    self.plugins.run_data_hooks(
                        "step_started",
                        manifest=manifest,
                        step=step,
                        config=self.config,
                        run_dir=str(run_dir),
                    )

                try:
                    if self.plugins:
                        self.plugins.before_step(step, manifest)

                    guardrails_cfg = self.config.get("guardrails", {})
                    use_concurrent = bool(guardrails_cfg.get("concurrent", False))
                    optimistic = bool(guardrails_cfg.get("optimistic", False))
                    guardrail_eval = (
                        guardrails_concurrent.evaluate_guardrails_concurrent
                        if use_concurrent
                        else guardrails.evaluate_guardrails
                    )
                    input_report = None

                    if use_concurrent and optimistic:
                        with ThreadPoolExecutor(max_workers=1) as guardrail_executor:
                            future = guardrail_executor.submit(
                                guardrail_eval,
                                "inputs",
                                step,
                                step_spec,
                                self.config,
                                run_dir,
                            )
                            run_tool_calls(
                                step=step,
                                step_spec=step_spec,
                                manifest=manifest,
                                run_dir=run_dir,
                                config=self.config,
                                registry=None,
                                allowed_tools=allowed_tools,
                                plugins=self.plugins,
                            )
                            telis_context = None
                            if self.telis:
                                telis_context = self.telis.resolve_for_step(
                                    step, step_spec, manifest
                                )
                                if telis_context:
                                    step["telis_context"] = telis_context
                                    fingerprint = quint_fingerprint.fingerprint_from_telis_result(
                                        step_id or step.get("name", ""),
                                        telis_context,
                                    )
                                    store = quint_fingerprint.FingerprintStore(run_dir)
                                    recorded = store.record(fingerprint)
                                    step["context_fingerprint_id"] = recorded.get("fingerprint_id")
                                    _append_event(
                                        run_dir,
                                        "ContextFingerprintCreated",
                                        manifest["run_id"],
                                        {"fingerprint_id": recorded.get("fingerprint_id")},
                                        step_id=step_id,
                                        bus=event_bus,
                                    )
                            if future.done():
                                input_report = future.result()
                                if input_report and input_report.status == "failed":
                                    _append_event(
                                        run_dir,
                                        "GuardrailFailed",
                                        manifest["run_id"],
                                        {
                                            "stage": input_report.stage,
                                            "violations": input_report.violations,
                                        },
                                        step_id=step_id,
                                        bus=event_bus,
                                    )
                                    raise guardrails.GuardrailViolation(input_report)
                            started = time.time()
                            executor.execute(
                                step,
                                {
                                    "run_dir": run_dir,
                                    "manifest": manifest,
                                    "step_spec": step_spec,
                                    "telis_context": telis_context,
                                },
                            )
                            if input_report is None:
                                input_report = future.result()
                    else:
                        input_report = guardrail_eval(
                            "inputs",
                            step,
                            step_spec,
                            self.config,
                            run_dir,
                        )
                        if input_report:
                            step.setdefault("guardrails", {})["inputs"] = input_report.to_dict()
                            if input_report.status == "failed":
                                _append_event(
                                    run_dir,
                                    "GuardrailFailed",
                                    manifest["run_id"],
                                    {
                                        "stage": input_report.stage,
                                        "violations": input_report.violations,
                                    },
                                    step_id=step_id,
                                    bus=event_bus,
                                )
                                raise guardrails.GuardrailViolation(input_report)
                        run_tool_calls(
                            step=step,
                            step_spec=step_spec,
                            manifest=manifest,
                            run_dir=run_dir,
                            config=self.config,
                            registry=None,
                            allowed_tools=allowed_tools,
                            plugins=self.plugins,
                        )
                        telis_context = None
                        if self.telis:
                            telis_context = self.telis.resolve_for_step(step, step_spec, manifest)
                            if telis_context:
                                step["telis_context"] = telis_context
                                fingerprint = quint_fingerprint.fingerprint_from_telis_result(
                                    step_id or step.get("name", ""),
                                    telis_context,
                                )
                                store = quint_fingerprint.FingerprintStore(run_dir)
                                recorded = store.record(fingerprint)
                                step["context_fingerprint_id"] = recorded.get("fingerprint_id")
                                _append_event(
                                    run_dir,
                                    "ContextFingerprintCreated",
                                    manifest["run_id"],
                                    {"fingerprint_id": recorded.get("fingerprint_id")},
                                    step_id=step_id,
                                    bus=event_bus,
                                )
                        started = time.time()
                        executor.execute(
                            step,
                            {
                                "run_dir": run_dir,
                                "manifest": manifest,
                                "step_spec": step_spec,
                                "telis_context": telis_context,
                            },
                        )

                    if input_report:
                        step.setdefault("guardrails", {})["inputs"] = input_report.to_dict()
                        if input_report.status == "failed":
                            _append_event(
                                run_dir,
                                "GuardrailFailed",
                                manifest["run_id"],
                                {
                                    "stage": input_report.stage,
                                    "violations": input_report.violations,
                                },
                                step_id=step_id,
                                bus=event_bus,
                            )
                            raise guardrails.GuardrailViolation(input_report)

                    report = guardrail_eval(
                        "outputs",
                        step,
                        step_spec,
                        self.config,
                        run_dir,
                    )
                    if report:
                        step.setdefault("guardrails", {})["outputs"] = report.to_dict()
                        if report.status == "failed":
                            _append_event(
                                run_dir,
                                "GuardrailFailed",
                                manifest["run_id"],
                                {"stage": report.stage, "violations": report.violations},
                                step_id=step_id,
                                bus=event_bus,
                            )
                            raise guardrails.GuardrailViolation(report)
                    elapsed = time.time() - started
                    if elapsed > timeout_seconds:
                        raise TimeoutError("step timeout")
                    validation_report = _run_validation_gate(step, step_spec)
                    if validation_report:
                        step["validation"] = validation_report
                        if self.plugins:
                            self.plugins.run_data_hooks(
                                "validation_result",
                                manifest=manifest,
                                step=step,
                                config=self.config,
                                run_dir=str(run_dir),
                                payload=validation_report,
                            )
                        if validation_report["status"] == "failed":
                            message = _validation_error_message(validation_report)
                            raise RuntimeError(f"validation failed: {message}")
                    _transition_step(step, "completed")
                    step["ended_at"] = utc_now()
                    step["error"] = None
                    manifest["updated_at"] = utc_now()
                    _update_artifact_index(run_dir, manifest, step, step_spec)
                    _append_event(
                        run_dir,
                        "WorkflowStepCompleted",
                        manifest["run_id"],
                        {"step": step.get("name"), "outputs": step.get("outputs", [])},
                        step_id=step_id,
                        bus=event_bus,
                    )
                    if self.plugins:
                        self.plugins.run_data_hooks(
                            "step_completed",
                            manifest=manifest,
                            step=step,
                            config=self.config,
                            run_dir=str(run_dir),
                        )
                    if self.plugins:
                        self.plugins.after_step(step, manifest)
                    break
                except ToolApprovalRequired as exc:
                    _transition_step(step, "blocked")
                    step["ended_at"] = utc_now()
                    step["error"] = str(exc)
                    manifest["status"] = "blocked"
                    manifest["blocked_reason"] = "tool_gate"
                    manifest["blocked_gate"] = exc.gate_id
                    manifest["blocked_tool"] = exc.tool_name
                    manifest["updated_at"] = utc_now()
                    storage.write_manifest(run_dir, manifest)
                    _append_event(
                        run_dir,
                        "WorkflowStepBlocked",
                        manifest["run_id"],
                        {"step": step.get("name"), "reason": "tool_gate"},
                        step_id=step_id,
                        bus=event_bus,
                    )
                    _append_event(
                        run_dir,
                        "WorkflowBlocked",
                        manifest["run_id"],
                        {"reason": "tool_gate", "gate_id": exc.gate_id},
                        bus=event_bus,
                    )
                    if self.plugins:
                        self.plugins.run_data_hooks(
                            "gate_triggered",
                            manifest=manifest,
                            step=step,
                            config=self.config,
                            run_dir=str(run_dir),
                            payload={
                                "gate_id": exc.gate_id,
                                "required": True,
                                "reason": "tool_gate",
                                "workflow": manifest.get("workflow", {}),
                            },
                        )
                    if self.plugins:
                        self.plugins.on_validation(manifest, "blocked")
                    return manifest
                except Exception as exc:  # noqa: BLE001
                    _transition_step(step, "failed")
                    step["ended_at"] = utc_now()
                    step["error"] = str(exc)
                    manifest["updated_at"] = utc_now()
                    storage.write_manifest(run_dir, manifest)
                    _append_event(
                        run_dir,
                        "WorkflowStepFailed",
                        manifest["run_id"],
                        {"step": step.get("name"), "error": step.get("error")},
                        step_id=step_id,
                        bus=event_bus,
                    )
                    if self.plugins:
                        self.plugins.run_data_hooks(
                            "step_failed",
                            manifest=manifest,
                            step=step,
                            config=self.config,
                            run_dir=str(run_dir),
                            payload={"error": step.get("error")},
                        )
                    if self.plugins:
                        self.plugins.on_error(step, manifest, step["error"] or "error")
                    if attempts > max_retries:
                        failed_tool = getattr(exc, "tool_name", "")
                        isolator = FailureIsolator(self.config)
                        impact = isolator.analyze_impact(
                            failed_tool,
                            step_id or step.get("name", ""),
                            manifest,
                        )
                        step["failure_impact"] = impact.to_dict()
                        if _isolate_step_failures(self.config):
                            _record_isolated_failure(
                                manifest,
                                step,
                                step.get("error", ""),
                                failed_tool,
                                impact.to_dict(),
                            )
                            manifest["updated_at"] = utc_now()
                            storage.write_manifest(run_dir, manifest)
                            break
                        manifest["status"] = "failed"
                        manifest["updated_at"] = utc_now()
                        storage.write_manifest(run_dir, manifest)
                        _append_event(
                            run_dir,
                            "WorkflowFailed",
                            manifest["run_id"],
                            {"reason": "step_failed", "step": step.get("name")},
                            bus=event_bus,
                        )
                        _evaluate_context_drift(
                            run_dir,
                            manifest,
                            self.telis,
                            self.config,
                            event_bus,
                        )
                        if self.plugins:
                            self.plugins.run_data_hooks(
                                "run_failed",
                                manifest=manifest,
                                step=step,
                                config=self.config,
                                run_dir=str(run_dir),
                                payload={"reason": "step_failed", "step": step.get("name")},
                            )
                        if self.plugins:
                            self.plugins.on_validation(manifest, "failed")
                        if self.plugins:
                            self.plugins.after_run(manifest)
                        return manifest
                    if backoff_seconds > 0:
                        time.sleep(backoff_seconds)

            storage.write_manifest(run_dir, manifest)

        if manifest.get("isolated_failures"):
            manifest["completed_with_errors"] = True
        manifest["status"] = "completed"
        manifest["updated_at"] = utc_now()
        storage.write_manifest(run_dir, manifest)
        _append_event(
            run_dir,
            "WorkflowCompleted",
            manifest["run_id"],
            {"workflow": manifest.get("workflow", {})},
            bus=event_bus,
        )
        _evaluate_context_drift(
            run_dir,
            manifest,
            self.telis,
            self.config,
            event_bus,
        )
        if self.plugins:
            self.plugins.run_data_hooks(
                "run_completed",
                manifest=manifest,
                step=None,
                config=self.config,
                run_dir=str(run_dir),
            )
        if self.plugins:
            self.plugins.on_validation(manifest, "completed")
        if self.plugins:
            self.plugins.after_run(manifest)
        return manifest
