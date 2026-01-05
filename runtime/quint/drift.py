from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime import storage
from runtime.quint.snapshot import ContextSnapshot
from runtime.time_provider import get_current_time


@dataclass(frozen=True)
class DriftIndicator:
    snapshot_id: str
    detected_at: str
    drift_type: str
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "detected_at": self.detected_at,
            "drift_type": self.drift_type,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DriftIndicator":
        return cls(
            snapshot_id=data.get("snapshot_id", ""),
            detected_at=data.get("detected_at", ""),
            drift_type=data.get("drift_type", ""),
            details=data.get("details", ""),
        )


def detect_drift(snapshot: ContextSnapshot, current: ContextSnapshot) -> List[DriftIndicator]:
    now = get_current_time()
    drifts: List[DriftIndicator] = []

    snapshot_shards = set(snapshot.shards_available)
    current_shards = set(current.shards_available)
    removed = sorted(snapshot_shards - current_shards)
    if removed:
        drifts.append(
            DriftIndicator(
                snapshot_id=snapshot.snapshot_id,
                detected_at=now,
                drift_type="shard_removed",
                details=f"Removed shards: {', '.join(removed)}",
            )
        )

    if snapshot.telis_policy_hash != current.telis_policy_hash:
        drifts.append(
            DriftIndicator(
                snapshot_id=snapshot.snapshot_id,
                detected_at=now,
                drift_type="policy_changed",
                details="TELIS policy hash changed",
            )
        )

    if snapshot.lsp_enabled != current.lsp_enabled:
        drifts.append(
            DriftIndicator(
                snapshot_id=snapshot.snapshot_id,
                detected_at=now,
                drift_type="lsp_changed",
                details=f"LSP enabled changed to {current.lsp_enabled}",
            )
        )

    if snapshot.token_budget_total != current.token_budget_total:
        drifts.append(
            DriftIndicator(
                snapshot_id=snapshot.snapshot_id,
                detected_at=now,
                drift_type="budget_changed",
                details=f"Token budget changed to {current.token_budget_total}",
            )
        )

    for path, checksum in snapshot.artifact_checksums.items():
        current_checksum = current.artifact_checksums.get(path)
        if not current_checksum:
            drifts.append(
                DriftIndicator(
                    snapshot_id=snapshot.snapshot_id,
                    detected_at=now,
                    drift_type="artifact_modified",
                    details=f"Artifact missing: {path}",
                )
            )
        elif current_checksum != checksum:
            drifts.append(
                DriftIndicator(
                    snapshot_id=snapshot.snapshot_id,
                    detected_at=now,
                    drift_type="artifact_modified",
                    details=f"Artifact checksum changed: {path}",
                )
            )

    return drifts


def mark_evidence_drifted(run_dir: Path, drifts: List[DriftIndicator]) -> int:
    if not drifts:
        return 0
    payload = storage.read_evidence_links(run_dir)
    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list):
        return 0
    drift_types = sorted({drift.drift_type for drift in drifts})
    for record in evidence:
        if not isinstance(record, dict):
            continue
        record["drifted"] = True
        record["drift_types"] = drift_types
    payload["evidence"] = evidence
    storage.write_evidence_links(run_dir, payload)
    storage.update_timeline(run_dir)
    return len(evidence)


class DriftStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def _read_drifts(self) -> Dict[str, Any]:
        path = self.run_dir / "context-drifts.json"
        if not path.exists():
            return {"drifts": [], "updated_at": ""}
        return storage.read_json(path)

    def _write_drifts(self, payload: Dict[str, Any]) -> None:
        path = self.run_dir / "context-drifts.json"
        payload["updated_at"] = get_current_time()
        storage.write_json(path, payload)

    def list(self) -> List[Dict[str, Any]]:
        payload = self._read_drifts()
        drifts = payload.get("drifts", [])
        if isinstance(drifts, list):
            return [dict(item) for item in drifts]
        return []

    def record(self, indicators: List[DriftIndicator]) -> List[Dict[str, Any]]:
        payload = self._read_drifts()
        drifts = payload.get("drifts", [])
        if not isinstance(drifts, list):
            drifts = []
        rendered = [indicator.to_dict() for indicator in indicators]
        drifts.extend(rendered)
        payload["drifts"] = drifts
        self._write_drifts(payload)
        storage.update_timeline(self.run_dir)
        return rendered

    def latest(self) -> Optional[Dict[str, Any]]:
        drifts = self.list()
        if not drifts:
            return None
        return max(drifts, key=lambda entry: entry.get("detected_at", ""))
