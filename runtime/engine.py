from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from runtime import config as runtime_config
from runtime import gates, models, storage, workflow_parser
from runtime.plugins.manager import PluginManager
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


def _append_event(
    run_dir: Path,
    event_type: str,
    run_id: str,
    payload: Optional[Dict[str, Any]] = None,
    step_id: Optional[str] = None,
) -> None:
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
    workflow_id = f"{workflow.get('module')}/{workflow.get('workflow')}"
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
        record = models.ArtifactRecord(
            artifact_id=_artifact_id(rel_path, checksum, artifact_type),
            path=rel_path,
            artifact_type=artifact_type,
            checksum=checksum,
            workflow=workflow_id,
            created_at=created_at,
            step=step_id,
            metadata={"step_name": step.get("name", "")},
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


def _gate_id(spec: models.WorkflowSpec) -> str:
    return f"{spec.module}:{spec.workflow}:hitl"


def _load_spec_from_manifest(manifest: Dict[str, Any]) -> models.WorkflowSpec:
    return models.WorkflowSpec.from_mapping(manifest["workflow"])


class WorkflowEngine:
    def __init__(
        self,
        config: Dict[str, Any],
        mapping_records: List[models.WorkflowSpec],
        storage_root: Optional[Path] = None,
        plugins: Optional[PluginManager] = None,
    ) -> None:
        self.config = config
        self.mapping = {(rec.module, rec.workflow): rec for rec in mapping_records}
        self.storage_root = storage_root or runtime_config.storage_root(config)
        self.plugins = plugins

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
        spec = _load_spec_from_manifest(manifest)
        approvals = storage.read_approvals(run_dir)
        approvals = gates.record_approval(
            approvals,
            _gate_id(spec),
            approved_by,
            utc_now(),
            notes,
        )
        storage.write_approvals(run_dir, approvals)
        return approvals

    def run(
        self,
        module: str,
        workflow: str,
        run_id: Optional[str] = None,
        executor: Optional[StepExecutor] = None,
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

        _ensure_steps(manifest)

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
            )
            if self.plugins:
                self.plugins.on_validation(manifest, "blocked")
            return manifest

        _clear_manual_block(manifest)
        _clear_tool_block(manifest)

        decision = gates.gate_required(spec.human, self.config)
        approvals = storage.read_approvals(run_dir)
        if decision.required and not gates.has_approval(approvals, _gate_id(spec)):
            manifest["status"] = "blocked"
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
            _append_event(
                run_dir,
                "WorkflowBlocked",
                manifest["run_id"],
                {"reason": "human_gate", "gate_id": _gate_id(spec)},
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
        )

        step_executor = executor or NoopExecutor()
        return self._execute_steps(run_dir, manifest, step_executor)

    def resume(self, run_id: str, executor: Optional[StepExecutor] = None) -> Dict[str, Any]:
        run_dir = self._run_dir(run_id)
        manifest = storage.read_manifest(run_dir)
        spec = _load_spec_from_manifest(manifest)

        _ensure_steps(manifest)

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
            )
            if self.plugins:
                self.plugins.on_validation(manifest, "blocked")
            return manifest

        _clear_manual_block(manifest)
        _clear_tool_block(manifest)

        decision = gates.gate_required(spec.human, self.config)
        approvals = storage.read_approvals(run_dir)
        if decision.required and not gates.has_approval(approvals, _gate_id(spec)):
            manifest["status"] = "blocked"
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
            _append_event(
                run_dir,
                "WorkflowBlocked",
                manifest["run_id"],
                {"reason": "human_gate", "gate_id": _gate_id(spec)},
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
        )

        step_executor = executor or NoopExecutor()
        return self._execute_steps(run_dir, manifest, step_executor)

    def _execute_steps(
        self,
        run_dir: Path,
        manifest: Dict[str, Any],
        executor: StepExecutor,
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
                )

                try:
                    if self.plugins:
                        self.plugins.before_step(step, manifest)
                    run_tool_calls(
                        step=step,
                        step_spec=step_spec,
                        manifest=manifest,
                        run_dir=run_dir,
                        config=self.config,
                    )
                    started = time.time()
                    executor.execute(
                        step,
                        {"run_dir": run_dir, "manifest": manifest, "step_spec": step_spec},
                    )
                    elapsed = time.time() - started
                    if elapsed > timeout_seconds:
                        raise TimeoutError("step timeout")
                    validation_report = _run_validation_gate(step, step_spec)
                    if validation_report:
                        step["validation"] = validation_report
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
                    )
                    _append_event(
                        run_dir,
                        "WorkflowBlocked",
                        manifest["run_id"],
                        {"reason": "tool_gate", "gate_id": exc.gate_id},
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
                    )
                    if self.plugins:
                        self.plugins.on_error(step, manifest, step["error"] or "error")
                    if attempts > max_retries:
                        manifest["status"] = "failed"
                        manifest["updated_at"] = utc_now()
                        storage.write_manifest(run_dir, manifest)
                        _append_event(
                            run_dir,
                            "WorkflowFailed",
                            manifest["run_id"],
                            {"reason": "step_failed", "step": step.get("name")},
                        )
                        if self.plugins:
                            self.plugins.on_validation(manifest, "failed")
                        if self.plugins:
                            self.plugins.after_run(manifest)
                        return manifest
                    if backoff_seconds > 0:
                        time.sleep(backoff_seconds)

            storage.write_manifest(run_dir, manifest)

        manifest["status"] = "completed"
        manifest["updated_at"] = utc_now()
        storage.write_manifest(run_dir, manifest)
        _append_event(
            run_dir,
            "WorkflowCompleted",
            manifest["run_id"],
            {"workflow": manifest.get("workflow", {})},
        )
        if self.plugins:
            self.plugins.on_validation(manifest, "completed")
        if self.plugins:
            self.plugins.after_run(manifest)
        return manifest
