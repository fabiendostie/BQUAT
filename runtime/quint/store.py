from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from runtime import models, storage
from runtime.time_provider import get_current_time

_ALLOWED_LEVELS = {"L0", "L1", "L2", "invalid"}


@dataclass(frozen=True)
class EvidenceRecord:
    link: models.EvidenceLink

    def to_dict(self) -> Dict[str, object]:
        record = self.link.to_dict()
        record["level"] = normalize_level(record.get("level", ""))
        return record


def normalize_level(level: str) -> str:
    value = (level or "").strip()
    if not value:
        raise ValueError("evidence level is required")
    upper = value.upper()
    if upper in {"L0", "L1", "L2"}:
        return upper
    if upper == "INVALID":
        return "invalid"
    if value in _ALLOWED_LEVELS:
        return value
    raise ValueError(f"unsupported evidence level: {level}")


def build_evidence_link(
    claim: str,
    level: str,
    source: str,
    carrier_ref: str,
    artifacts: List[str] | None = None,
    notes: str = "",
) -> models.EvidenceLink:
    timestamp = get_current_time()
    normalized = normalize_level(level)
    return models.EvidenceLink(
        id=f"ev-{uuid4().hex[:8]}",
        claim=claim,
        level=normalized,
        source=source,
        date=timestamp,
        valid_until=timestamp,
        congruence="",
        reliability=0.0,
        wlnk=0.0,
        carrier_ref=carrier_ref,
        artifacts=list(artifacts or []),
        notes=notes,
    )


class EvidenceStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def list(self) -> List[Dict[str, object]]:
        payload = storage.read_evidence_links(self.run_dir)
        evidence = payload.get("evidence", [])
        if isinstance(evidence, list):
            return [dict(item) for item in evidence]
        return []

    def record(self, link: models.EvidenceLink) -> Dict[str, object]:
        record = EvidenceRecord(link).to_dict()
        payload = storage.read_evidence_links(self.run_dir)
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        evidence.append(record)
        payload["evidence"] = evidence
        storage.write_evidence_links(self.run_dir, payload)
        return record

    def invalidate(self, evidence_id: str, reason: str = "") -> Dict[str, object]:
        payload = storage.read_evidence_links(self.run_dir)
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        for record in evidence:
            if record.get("id") == evidence_id:
                record["level"] = "invalid"
                if reason:
                    notes = str(record.get("notes", ""))
                    record["notes"] = f"{notes} {reason}".strip()
                payload["evidence"] = evidence
                storage.write_evidence_links(self.run_dir, payload)
                return dict(record)
        raise KeyError(f"Evidence not found: {evidence_id}")
