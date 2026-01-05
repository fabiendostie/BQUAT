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
    context_fingerprint_id: str | None = None,
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
        context_fingerprint_id=context_fingerprint_id,
        artifacts=list(artifacts or []),
        notes=notes,
    )


def _artifact_matches(reference: str, artifact: Dict[str, object]) -> bool:
    if reference == artifact.get("artifact_id") or reference == artifact.get("path"):
        return True
    if "/" not in reference and "\\" not in reference:
        path = str(artifact.get("path", ""))
        return Path(path).name == reference
    return False


def _link_evidence_artifacts(run_dir: Path, record: Dict[str, object]) -> None:
    evidence_id = record.get("id")
    if not evidence_id:
        return
    references = record.get("artifacts", [])
    if not isinstance(references, list) or not references:
        return
    payload = storage.read_artifact_index(run_dir)
    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list):
        return
    updated = False
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if not any(_artifact_matches(str(ref), artifact) for ref in references):
            continue
        metadata = dict(artifact.get("metadata", {}))
        evidence_ids = metadata.get("evidence_ids", [])
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        if evidence_id not in evidence_ids:
            evidence_ids.append(evidence_id)
            metadata["evidence_ids"] = evidence_ids
            artifact["metadata"] = metadata
            updated = True
    if updated:
        payload["updated_at"] = get_current_time()
        storage.write_artifact_index(run_dir, payload)


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
        _link_evidence_artifacts(self.run_dir, record)
        storage.update_timeline(self.run_dir)
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
                storage.update_timeline(self.run_dir)
                return dict(record)
        raise KeyError(f"Evidence not found: {evidence_id}")
