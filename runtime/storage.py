from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


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
