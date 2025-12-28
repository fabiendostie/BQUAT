from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from runtime import storage


@dataclass(frozen=True)
class EvidenceDecayResult:
    checked_at: str
    expired: List[Dict[str, object]]
    active: List[Dict[str, object]]
    invalid: List[Dict[str, object]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "checked_at": self.checked_at,
            "expired": list(self.expired),
            "active": list(self.active),
            "invalid": list(self.invalid),
        }


def scan_evidence(
    run_dir: Path,
    now_provider: Optional[Callable[[], datetime]] = None,
) -> EvidenceDecayResult:
    now = (now_provider or _utc_now)()
    payload = storage.read_evidence_links(run_dir)
    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    expired: List[Dict[str, object]] = []
    active: List[Dict[str, object]] = []
    invalid: List[Dict[str, object]] = []

    for record in evidence:
        if not isinstance(record, dict):
            continue
        level = str(record.get("level", ""))
        if level == "invalid":
            invalid.append(_decay_entry(record, "invalid", "already_invalid"))
            continue
        valid_until = str(record.get("valid_until", "")).strip()
        parsed = _parse_timestamp(valid_until)
        if not valid_until:
            expired.append(_decay_entry(record, "expired", "missing_valid_until"))
            continue
        if parsed is None:
            expired.append(_decay_entry(record, "expired", "invalid_valid_until"))
            continue
        if parsed <= now:
            expired.append(_decay_entry(record, "expired", "expired"))
        else:
            active.append(_decay_entry(record, "active", "valid"))

    return EvidenceDecayResult(
        checked_at=_format_iso(now),
        expired=expired,
        active=active,
        invalid=invalid,
    )


def _decay_entry(record: Dict[str, object], status: str, reason: str) -> Dict[str, object]:
    return {
        "id": str(record.get("id", "")),
        "status": status,
        "reason": reason,
        "valid_until": record.get("valid_until", ""),
        "level": record.get("level", ""),
        "record": dict(record),
    }


def _parse_timestamp(value: str) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_iso(moment: datetime) -> str:
    return moment.isoformat()
