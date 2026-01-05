from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.plugins.data_plane import DataContext, DataPlanePlugin
from runtime.plugins.ordering import PluginPriority
from runtime.time_provider import get_current_time


class AuditPlugin(DataPlanePlugin):
    """Data plane plugin that writes audit logs.

    Captures workflow, step, gate, and error events to an audit log file.
    Provides an immutable audit trail for compliance and debugging.
    """

    priority = PluginPriority.AUDIT

    def __init__(self, run_dir: Optional[Path] = None) -> None:
        self._run_dir = run_dir
        self._entries: List[Dict[str, Any]] = []

    def _write_entry(self, entry: Dict[str, Any]) -> None:
        """Write an audit entry to the log."""
        self._entries.append(entry)

        if self._run_dir:
            audit_path = self._run_dir / "audit.json"
            try:
                if audit_path.exists():
                    payload = json.loads(audit_path.read_text(encoding="utf-8"))
                else:
                    payload = {"entries": []}

                entries = payload.get("entries", [])
                entries.append(entry)
                payload["entries"] = entries
                payload["updated_at"] = get_current_time()

                audit_path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True),
                    encoding="ascii",
                )
            except Exception:  # noqa: BLE001, S110
                pass

    def _build_entry(
        self,
        event_type: str,
        context: DataContext,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a standardized audit entry."""
        entry: Dict[str, Any] = {
            "timestamp": get_current_time(),
            "event_type": event_type,
            "phase": context.phase,
        }

        manifest = context.manifest
        if manifest:
            entry["run_id"] = manifest.get("run_id", "")

        step = context.step
        if step:
            entry["step_id"] = step.get("step_id") or step.get("name", "")
            entry["step_status"] = step.get("status", "")

        if details:
            entry["details"] = details

        return entry

    def on_run_started(self, context: DataContext) -> None:
        """Record workflow run start."""
        manifest = context.manifest
        details = {}
        if manifest:
            spec = manifest.get("workflow_spec", {})
            details = {
                "module": spec.get("module", ""),
                "workflow": spec.get("workflow", ""),
                "status": manifest.get("status", ""),
            }
        entry = self._build_entry("run_started", context, details)
        self._write_entry(entry)

    def on_run_completed(self, context: DataContext) -> None:
        """Record workflow run completion."""
        manifest = context.manifest
        details = {}
        if manifest:
            details = {
                "status": manifest.get("status", ""),
                "steps_completed": len(
                    [s for s in manifest.get("steps", []) if s.get("status") == "completed"]
                ),
            }
        entry = self._build_entry("run_completed", context, details)
        self._write_entry(entry)

    def on_run_failed(self, context: DataContext) -> None:
        """Record workflow run failure."""
        details = {"error": context.payload.get("error", "")}
        entry = self._build_entry("run_failed", context, details)
        self._write_entry(entry)

    def on_step_started(self, context: DataContext) -> None:
        """Record step start."""
        step = context.step
        details = {}
        if step:
            details = {
                "step_name": step.get("name", ""),
                "attempt": step.get("attempts", 0),
            }
        entry = self._build_entry("step_started", context, details)
        self._write_entry(entry)

    def on_step_completed(self, context: DataContext) -> None:
        """Record step completion."""
        step = context.step
        details = {}
        if step:
            details = {
                "step_name": step.get("name", ""),
                "outputs": step.get("outputs", []),
            }
        entry = self._build_entry("step_completed", context, details)
        self._write_entry(entry)

    def on_step_failed(self, context: DataContext) -> None:
        """Record step failure."""
        step = context.step
        details = {
            "error": context.payload.get("error", ""),
        }
        if step:
            details["step_name"] = step.get("name", "")
            details["attempt"] = step.get("attempts", 0)
        entry = self._build_entry("step_failed", context, details)
        self._write_entry(entry)

    def on_gate_triggered(self, context: DataContext) -> None:
        """Record human gate trigger."""
        details = {
            "gate_id": context.payload.get("gate_id", ""),
            "reason": context.payload.get("reason", ""),
            "required": context.payload.get("required", False),
        }
        entry = self._build_entry("gate_triggered", context, details)
        self._write_entry(entry)

    def on_tool_executed(self, context: DataContext) -> None:
        """Record tool execution."""
        details = {
            "tool_name": context.payload.get("tool_name", ""),
            "status": context.payload.get("status", ""),
            "risk": context.payload.get("risk", ""),
            "duration_ms": context.payload.get("duration_ms", 0),
        }
        entry = self._build_entry("tool_executed", context, details)
        self._write_entry(entry)

    def on_validation_result(self, context: DataContext) -> None:
        """Record validation result."""
        details = {
            "status": context.payload.get("status", ""),
            "errors": context.payload.get("errors", []),
        }
        entry = self._build_entry("validation_result", context, details)
        self._write_entry(entry)

    def get_entries(self) -> List[Dict[str, Any]]:
        """Return all captured audit entries."""
        return list(self._entries)

    def clear(self) -> None:
        """Clear in-memory entries."""
        self._entries.clear()
