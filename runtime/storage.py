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
