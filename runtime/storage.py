from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from runtime.time_provider import get_current_time


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def init_run_dir(storage_root: Path, run_id: str) -> Path:
    return ensure_dir(storage_root / run_id)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    payload = json.dumps(data, indent=2, sort_keys=True)
    path.write_text(payload, encoding="ascii")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="ascii"))


def write_manifest(run_dir: Path, manifest: Dict[str, Any]) -> Path:
    target = run_dir / "manifest.json"
    write_json(target, manifest)
    return target


def read_manifest(run_dir: Path) -> Dict[str, Any]:
    return read_json(run_dir / "manifest.json")


def write_approvals(run_dir: Path, approvals: Dict[str, Any]) -> Path:
    target = run_dir / "approvals.json"
    write_json(target, approvals)
    return target


def read_approvals(run_dir: Path) -> Dict[str, Any]:
    target = run_dir / "approvals.json"
    if not target.exists():
        return {"approvals": []}
    return read_json(target)


def write_artifact_index(run_dir: Path, index: Dict[str, Any]) -> Path:
    target = run_dir / "artifacts.json"
    write_json(target, index)
    return target


def read_artifact_index(run_dir: Path) -> Dict[str, Any]:
    target = run_dir / "artifacts.json"
    if not target.exists():
        return {"run_id": run_dir.name, "artifacts": [], "updated_at": ""}
    return read_json(target)


def write_evidence_links(run_dir: Path, evidence: Dict[str, Any]) -> Path:
    target = run_dir / "evidence.json"
    write_json(target, evidence)
    return target


def read_evidence_links(run_dir: Path) -> Dict[str, Any]:
    target = run_dir / "evidence.json"
    if not target.exists():
        return {"evidence": []}
    return read_json(target)


def write_drrs(run_dir: Path, drrs: Dict[str, Any]) -> Path:
    target = run_dir / "drr.json"
    write_json(target, drrs)
    return target


def read_drrs(run_dir: Path) -> Dict[str, Any]:
    target = run_dir / "drr.json"
    if not target.exists():
        return {"drrs": []}
    return read_json(target)


def write_human_gates(run_dir: Path, gates: Dict[str, Any]) -> Path:
    target = run_dir / "gates.json"
    write_json(target, gates)
    return target


def read_human_gates(run_dir: Path) -> Dict[str, Any]:
    target = run_dir / "gates.json"
    if not target.exists():
        return {"gates": []}
    return read_json(target)


def write_events(run_dir: Path, events: Dict[str, Any]) -> Path:
    target = run_dir / "events.json"
    write_json(target, events)
    return target


def read_events(run_dir: Path) -> Dict[str, Any]:
    target = run_dir / "events.json"
    if not target.exists():
        return {"events": []}
    return read_json(target)


def write_tool_results(run_dir: Path, results: Dict[str, Any]) -> Path:
    target = run_dir / "tool_results.json"
    write_json(target, results)
    return target


def read_tool_results(run_dir: Path) -> Dict[str, Any]:
    target = run_dir / "tool_results.json"
    if not target.exists():
        return {"results": []}
    return read_json(target)


def write_timeline(run_dir: Path, timeline: Dict[str, Any]) -> Path:
    target = run_dir / "timeline.json"
    write_json(target, timeline)
    return target


def read_timeline(run_dir: Path) -> Dict[str, Any]:
    target = run_dir / "timeline.json"
    if not target.exists():
        return {"run_id": run_dir.name, "generated_at": "", "entries": []}
    return read_json(target)


def build_timeline(run_dir: Path) -> Dict[str, Any]:
    run_id = run_dir.name
    try:
        manifest = read_manifest(run_dir)
        run_id = str(manifest.get("run_id", run_id))
    except FileNotFoundError:
        pass

    entries: List[Dict[str, Any]] = []

    events_payload = read_events(run_dir)
    for event in events_payload.get("events", []):
        entries.append(
            {
                "type": "event",
                "timestamp": event.get("timestamp", ""),
                "event_type": event.get("event_type", ""),
                "step_id": event.get("step_id"),
                "payload": dict(event.get("payload", {})),
            }
        )

    artifacts_payload = read_artifact_index(run_dir)
    for artifact in artifacts_payload.get("artifacts", []):
        entries.append(
            {
                "type": "artifact",
                "timestamp": artifact.get("created_at", ""),
                "artifact_id": artifact.get("artifact_id", ""),
                "path": artifact.get("path", ""),
                "artifact_type": artifact.get("artifact_type", ""),
                "checksum": artifact.get("checksum", ""),
                "workflow": artifact.get("workflow", ""),
                "step": artifact.get("step"),
                "metadata": dict(artifact.get("metadata", {})),
            }
        )

    gates_payload = read_human_gates(run_dir)
    for gate in gates_payload.get("gates", []):
        entries.append(
            {
                "type": "gate",
                "timestamp": gate.get("recorded_at") or gate.get("approved_at") or "",
                "gate_id": gate.get("gate_id", ""),
                "status": gate.get("status", ""),
                "required": gate.get("required", False),
                "approved_by": gate.get("approved_by"),
                "approved_at": gate.get("approved_at"),
                "reason": gate.get("reason"),
                "phase": gate.get("phase"),
                "workflow": gate.get("workflow"),
            }
        )

    evidence_payload = read_evidence_links(run_dir)
    for evidence in evidence_payload.get("evidence", []):
        entries.append(
            {
                "type": "evidence",
                "timestamp": evidence.get("date", ""),
                "evidence_id": evidence.get("id", ""),
                "level": evidence.get("level", ""),
                "claim": evidence.get("claim", ""),
                "source": evidence.get("source", ""),
                "artifacts": list(evidence.get("artifacts", [])),
                "carrier_ref": evidence.get("carrier_ref", ""),
            }
        )

    drr_payload = read_drrs(run_dir)
    for record in drr_payload.get("drrs", []):
        entries.append(
            {
                "type": "drr",
                "timestamp": record.get("date", ""),
                "decision_id": record.get("decision_id", ""),
                "status": record.get("status", ""),
                "owner": record.get("owner", ""),
                "markdown_path": record.get("markdown_path", ""),
            }
        )

    entries.sort(key=_timeline_sort_key)
    return {"run_id": run_id, "generated_at": get_current_time(), "entries": entries}


def update_timeline(run_dir: Path) -> Path:
    return write_timeline(run_dir, build_timeline(run_dir))


def _timeline_sort_key(entry: Dict[str, Any]) -> Tuple[str, str, str]:
    timestamp = entry.get("timestamp") or "9999-12-31T23:59:59Z"
    entry_type = entry.get("type", "")
    entry_id = str(
        entry.get("event_type")
        or entry.get("artifact_id")
        or entry.get("gate_id")
        or entry.get("evidence_id")
        or entry.get("decision_id")
        or ""
    )
    return timestamp, entry_type, entry_id
