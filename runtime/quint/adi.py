from __future__ import annotations

from pathlib import Path
from typing import Dict

from runtime import storage
from runtime.quint.store import EvidenceStore, normalize_level

_ALLOWED_PROMOTIONS = {
    "L0": "L1",
    "L1": "L2",
}


def promote_evidence(
    run_dir: Path,
    evidence_id: str,
    target_level: str,
    notes: str = "",
) -> Dict[str, object]:
    payload = storage.read_evidence_links(run_dir)
    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    target = normalize_level(target_level)
    if target == "invalid":
        raise ValueError("promotion target cannot be invalid")

    for record in evidence:
        if record.get("id") != evidence_id:
            continue
        current = normalize_level(str(record.get("level", "")))
        if current == "invalid":
            raise ValueError("cannot promote invalid evidence")
        expected = _ALLOWED_PROMOTIONS.get(current)
        if expected != target:
            raise ValueError(f"invalid promotion: {current} -> {target}")
        record["level"] = target
        if notes:
            existing = str(record.get("notes", ""))
            record["notes"] = f"{existing} {notes}".strip()
        payload["evidence"] = evidence
        storage.write_evidence_links(run_dir, payload)
        return dict(record)

    raise KeyError(f"Evidence not found: {evidence_id}")


def invalidate_evidence(
    run_dir: Path,
    evidence_id: str,
    reason: str = "",
) -> Dict[str, object]:
    store = EvidenceStore(run_dir)
    return store.invalidate(evidence_id, reason=reason)
