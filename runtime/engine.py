from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from runtime import config as runtime_config
from runtime import gates, models, storage
from runtime.plugins.manager import PluginManager
from runtime.time_provider import get_current_time


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


def _ensure_steps(manifest: Dict[str, Any]) -> None:
    if not manifest.get("steps"):
        manifest["steps"] = _default_steps()
        manifest["current_step"] = 0


def _step_timeout_seconds(config: Dict[str, Any]) -> int:
    runtime_cfg = config.get("runtime", {})
    return int(runtime_cfg.get("step_timeout_seconds", 1800))


def _max_retries(config: Dict[str, Any]) -> int:
    runtime_cfg = config.get("runtime", {})
    return int(runtime_cfg.get("max_retries", 0))


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
        manifest = models.RunManifest(
            run_id=run_id,
            workflow=spec,
            status="pending",
            steps=[models.RunStep(name="execute")],
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

        decision = gates.gate_required(spec.human, self.config)
        approvals = storage.read_approvals(run_dir)
        if decision.required and not gates.has_approval(approvals, _gate_id(spec)):
            manifest["status"] = "blocked"
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
            if self.plugins:
                self.plugins.on_validation(manifest, "blocked")
            return manifest

        if self.plugins:
            self.plugins.before_run(manifest)

        manifest["status"] = "running"
        manifest["updated_at"] = utc_now()
        storage.write_manifest(run_dir, manifest)

        step_executor = executor or NoopExecutor()
        return self._execute_steps(run_dir, manifest, step_executor)

    def resume(self, run_id: str, executor: Optional[StepExecutor] = None) -> Dict[str, Any]:
        run_dir = self._run_dir(run_id)
        manifest = storage.read_manifest(run_dir)
        spec = _load_spec_from_manifest(manifest)

        _ensure_steps(manifest)

        decision = gates.gate_required(spec.human, self.config)
        approvals = storage.read_approvals(run_dir)
        if decision.required and not gates.has_approval(approvals, _gate_id(spec)):
            manifest["status"] = "blocked"
            manifest["updated_at"] = utc_now()
            storage.write_manifest(run_dir, manifest)
            if self.plugins:
                self.plugins.on_validation(manifest, "blocked")
            return manifest

        if self.plugins:
            self.plugins.before_run(manifest)

        manifest["status"] = "running"
        manifest["updated_at"] = utc_now()
        storage.write_manifest(run_dir, manifest)

        step_executor = executor or NoopExecutor()
        return self._execute_steps(run_dir, manifest, step_executor)

    def _execute_steps(
        self,
        run_dir: Path,
        manifest: Dict[str, Any],
        executor: StepExecutor,
    ) -> Dict[str, Any]:
        steps = manifest.get("steps", [])
        max_retries = _max_retries(self.config)
        timeout_seconds = _step_timeout_seconds(self.config)

        for idx, step in enumerate(steps):
            if step.get("status") == "completed":
                continue
            manifest["current_step"] = idx
            attempts = int(step.get("attempts", 0))
            while attempts <= max_retries:
                attempts += 1
                step["attempts"] = attempts
                step["status"] = "running"
                step["started_at"] = utc_now()
                manifest["updated_at"] = utc_now()
                storage.write_manifest(run_dir, manifest)

                try:
                    if self.plugins:
                        self.plugins.before_step(step, manifest)
                    started = time.time()
                    executor.execute(step, {"run_dir": run_dir, "manifest": manifest})
                    elapsed = time.time() - started
                    if elapsed > timeout_seconds:
                        raise TimeoutError("step timeout")
                    step["status"] = "completed"
                    step["ended_at"] = utc_now()
                    step["error"] = None
                    if self.plugins:
                        self.plugins.after_step(step, manifest)
                    break
                except Exception as exc:  # noqa: BLE001
                    step["status"] = "failed"
                    step["ended_at"] = utc_now()
                    step["error"] = str(exc)
                    if self.plugins:
                        self.plugins.on_error(step, manifest, step["error"] or "error")
                    if attempts > max_retries:
                        manifest["status"] = "failed"
                        manifest["updated_at"] = utc_now()
                        storage.write_manifest(run_dir, manifest)
                        if self.plugins:
                            self.plugins.on_validation(manifest, "failed")
                        if self.plugins:
                            self.plugins.after_run(manifest)
                        return manifest

            storage.write_manifest(run_dir, manifest)

        manifest["status"] = "completed"
        manifest["updated_at"] = utc_now()
        storage.write_manifest(run_dir, manifest)
        if self.plugins:
            self.plugins.on_validation(manifest, "completed")
        if self.plugins:
            self.plugins.after_run(manifest)
        return manifest
