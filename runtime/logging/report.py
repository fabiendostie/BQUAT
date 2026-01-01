from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime import storage
from runtime.logging.models import RunReport, RunReportSummary
from runtime.time_provider import get_current_time

REPORT_VERSION = "1.0"


class RunReportGenerator:
    """Generates comprehensive run report artifacts."""

    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    def generate(self) -> RunReport:
        manifest = storage.read_manifest(self._run_dir)
        events = storage.read_events(self._run_dir)
        artifacts = storage.read_artifact_index(self._run_dir)
        evidence = storage.read_evidence_links(self._run_dir)
        gates = storage.read_human_gates(self._run_dir)
        drrs = storage.read_drrs(self._run_dir)
        storage.update_timeline(self._run_dir)
        timeline = storage.read_timeline(self._run_dir)
        logs = storage.read_logs(self._run_dir)

        summary = self._build_summary(manifest, events, artifacts, evidence, gates)
        validation_results = self._extract_validation_results(manifest)
        guardrail_reports = self._extract_guardrail_reports(manifest)

        return RunReport(
            version=REPORT_VERSION,
            generated_at=get_current_time(),
            summary=summary,
            events=events.get("events", []),
            logs=logs.get("logs", []),
            artifacts=artifacts.get("artifacts", []),
            evidence=evidence.get("evidence", []),
            gates=gates.get("gates", []),
            drrs=drrs.get("drrs", []),
            validation_results=validation_results,
            guardrail_reports=guardrail_reports,
            timeline=timeline.get("entries", []),
        )

    def _build_summary(
        self,
        manifest: Dict[str, Any],
        events: Dict[str, Any],
        artifacts: Dict[str, Any],
        evidence: Dict[str, Any],
        gates: Dict[str, Any],
    ) -> RunReportSummary:
        workflow = manifest.get("workflow", {})
        steps = manifest.get("steps", [])
        gates_list = gates.get("gates", [])

        started_at = manifest.get("created_at", "")
        completed_at = manifest.get("updated_at", "")
        duration = self._calculate_duration(started_at, completed_at)

        steps_completed = sum(1 for s in steps if s.get("status") == "completed")
        steps_failed = sum(1 for s in steps if s.get("status") == "failed")

        gates_approved = sum(1 for g in gates_list if g.get("status") == "approved")
        gates_blocked = sum(1 for g in gates_list if g.get("status") == "blocked")

        validation_passed = 0
        validation_failed = 0
        guardrail_violations = 0

        for step in steps:
            v = step.get("validation", {})
            if v.get("status") == "passed":
                validation_passed += 1
            elif v.get("status") == "failed":
                validation_failed += 1

            guardrails = step.get("guardrails", {})
            for stage_report in guardrails.values():
                if isinstance(stage_report, dict):
                    violations = stage_report.get("violations", [])
                    guardrail_violations += len(violations)

        return RunReportSummary(
            run_id=manifest.get("run_id", ""),
            status=manifest.get("status", ""),
            workflow_id=f"{workflow.get('module', '')}/{workflow.get('workflow', '')}",
            module=workflow.get("module", ""),
            workflow=workflow.get("workflow", ""),
            phase=workflow.get("phase", ""),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            steps_total=len(steps),
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            gates_total=len(gates_list),
            gates_approved=gates_approved,
            gates_blocked=gates_blocked,
            evidence_count=len(evidence.get("evidence", [])),
            artifacts_count=len(artifacts.get("artifacts", [])),
            validation_passed=validation_passed,
            validation_failed=validation_failed,
            guardrail_violations=guardrail_violations,
        )

    def _calculate_duration(self, started_at: str, completed_at: str) -> float:
        if not started_at or not completed_at:
            return 0.0
        try:
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            return (end - start).total_seconds()
        except ValueError:
            return 0.0

    def _extract_validation_results(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for step in manifest.get("steps", []):
            validation = step.get("validation", {})
            if validation:
                results.append(
                    {
                        "step_id": step.get("step_id"),
                        "step_name": step.get("name"),
                        "validation": validation,
                    }
                )
        return results

    def _extract_guardrail_reports(self, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
        reports: List[Dict[str, Any]] = []
        for step in manifest.get("steps", []):
            guardrails = step.get("guardrails", {})
            if guardrails:
                reports.append(
                    {
                        "step_id": step.get("step_id"),
                        "step_name": step.get("name"),
                        "guardrails": guardrails,
                    }
                )
        return reports

    def write_report(self, output_path: Optional[Path] = None) -> Path:
        """Generate and write report to file."""
        report = self.generate()
        target = output_path or (self._run_dir / "report.json")
        storage.write_json(target, report.to_dict())
        return target
