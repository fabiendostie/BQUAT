from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from runtime import storage
from runtime.telis.manager import TelisPolicyEngine
from runtime.time_provider import get_current_time


@dataclass(frozen=True)
class ContextSnapshot:
    snapshot_id: str
    captured_at: str
    shards_available: tuple[str, ...] = field(default_factory=tuple)
    lsp_enabled: bool = False
    token_budget_total: int = 0
    telis_policy_hash: str = ""
    validation_gates: tuple[str, ...] = field(default_factory=tuple)
    artifact_checksums: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.shards_available, list):
            object.__setattr__(self, "shards_available", tuple(self.shards_available))
        if isinstance(self.validation_gates, list):
            object.__setattr__(self, "validation_gates", tuple(self.validation_gates))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "shards_available": list(self.shards_available),
            "lsp_enabled": self.lsp_enabled,
            "token_budget_total": self.token_budget_total,
            "telis_policy_hash": self.telis_policy_hash,
            "validation_gates": list(self.validation_gates),
            "artifact_checksums": dict(self.artifact_checksums),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextSnapshot":
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            captured_at=data.get("captured_at", ""),
            shards_available=tuple(data.get("shards_available", [])),
            lsp_enabled=bool(data.get("lsp_enabled", False)),
            token_budget_total=int(data.get("token_budget_total", 0)),
            telis_policy_hash=data.get("telis_policy_hash", ""),
            validation_gates=tuple(data.get("validation_gates", [])),
            artifact_checksums=dict(data.get("artifact_checksums", {})),
        )


def build_snapshot(
    manifest: Dict[str, Any],
    run_dir: Path,
    telis: Optional[TelisPolicyEngine],
    config: Dict[str, Any],
) -> ContextSnapshot:
    snapshot_id = f"cs-{uuid4().hex[:8]}"
    captured_at = get_current_time()

    shards_available: List[str] = []
    lsp_enabled = False
    token_budget_total = 0
    if telis:
        shards_available = [shard.shard_id for shard in telis.registry.list()]
        lsp_enabled = telis.lsp_provider is not None
        token_budget_total = sum(telis.policy.budgets.values())

    workflow = manifest.get("workflow", {})
    policy_text = str(workflow.get("telis", "")).strip()
    telis_policy_hash = ""
    if policy_text:
        telis_policy_hash = hashlib.sha256(policy_text.encode("utf-8")).hexdigest()[:12]

    validation_gate = str(workflow.get("validation", "")).strip()
    validation_gates = [validation_gate] if validation_gate else []

    artifacts_payload = storage.read_artifact_index(run_dir)
    artifact_checksums = {
        str(item.get("path", "")): str(item.get("checksum", ""))
        for item in artifacts_payload.get("artifacts", [])
        if isinstance(item, dict)
    }

    return ContextSnapshot(
        snapshot_id=snapshot_id,
        captured_at=captured_at,
        shards_available=tuple(shards_available),
        lsp_enabled=lsp_enabled,
        token_budget_total=token_budget_total,
        telis_policy_hash=telis_policy_hash,
        validation_gates=tuple(validation_gates),
        artifact_checksums=artifact_checksums,
    )


class SnapshotStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def _read_snapshots(self) -> Dict[str, Any]:
        path = self.run_dir / "context-snapshots.json"
        if not path.exists():
            return {"snapshots": [], "updated_at": ""}
        return storage.read_json(path)

    def _write_snapshots(self, payload: Dict[str, Any]) -> None:
        path = self.run_dir / "context-snapshots.json"
        payload["updated_at"] = get_current_time()
        storage.write_json(path, payload)

    def list(self) -> List[Dict[str, Any]]:
        payload = self._read_snapshots()
        snapshots = payload.get("snapshots", [])
        if isinstance(snapshots, list):
            return [dict(item) for item in snapshots]
        return []

    def record(self, snapshot: ContextSnapshot) -> Dict[str, Any]:
        payload = self._read_snapshots()
        snapshots = payload.get("snapshots", [])
        if not isinstance(snapshots, list):
            snapshots = []
        rendered = snapshot.to_dict()
        snapshots.append(rendered)
        payload["snapshots"] = snapshots
        self._write_snapshots(payload)
        storage.update_timeline(self.run_dir)
        return rendered

    def get(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        for snapshot in self.list():
            if snapshot.get("snapshot_id") == snapshot_id:
                return snapshot
        return None

    def latest(self) -> Optional[Dict[str, Any]]:
        snapshots = self.list()
        if not snapshots:
            return None
        return max(snapshots, key=lambda snap: snap.get("captured_at", ""))
