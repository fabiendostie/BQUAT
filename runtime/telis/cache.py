from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional


def _parse_iso(timestamp: str) -> datetime:
    value = timestamp.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def _format_iso(moment: datetime) -> str:
    return moment.isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CacheEntry:
    key: str
    response: str
    tokens_saved: int
    hit_count: int
    created_at: str
    last_hit: str
    ttl_seconds: int
    metadata: Dict[str, object] = field(default_factory=dict)


class BehavioralCache:
    def __init__(
        self,
        ttl_seconds: int = 60 * 60 * 24 * 7,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.ttl_seconds = int(ttl_seconds)
        self._now = now_provider or _utc_now
        self._entries: Dict[str, CacheEntry] = {}

    def set(
        self,
        key: str,
        response: str,
        tokens_saved: int = 0,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> CacheEntry:
        now = self._now()
        entry = CacheEntry(
            key=key,
            response=response,
            tokens_saved=int(tokens_saved),
            hit_count=0,
            created_at=_format_iso(now),
            last_hit=_format_iso(now),
            ttl_seconds=int(ttl_seconds if ttl_seconds is not None else self.ttl_seconds),
            metadata=dict(metadata or {}),
        )
        self._entries[key] = entry
        return entry

    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self._entries.get(key)
        if not entry:
            return None
        now = self._now()
        if self._is_expired(entry, now):
            self._entries.pop(key, None)
            return None
        entry.hit_count += 1
        entry.last_hit = _format_iso(now)
        return entry

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)

    def invalidate_language_version(self, language: str, version: str) -> int:
        return self._invalidate_where(
            lambda entry: entry.metadata.get("language") == language
            and entry.metadata.get("version") == version
        )

    def invalidate_shard_update(self, shard_id: str) -> int:
        return self._invalidate_where(
            lambda entry: _contains_shard(entry.metadata.get("shard_ids"), shard_id)
        )

    def invalidate_manual(self, keys: List[str]) -> int:
        removed = 0
        for key in keys:
            if key in self._entries:
                removed += 1
                self._entries.pop(key, None)
        return removed

    def _invalidate_where(self, predicate: Callable[[CacheEntry], bool]) -> int:
        removed = 0
        for key, entry in list(self._entries.items()):
            if predicate(entry):
                removed += 1
                self._entries.pop(key, None)
        return removed

    def _is_expired(self, entry: CacheEntry, now: datetime) -> bool:
        try:
            created_at = _parse_iso(entry.created_at)
        except ValueError:
            return True
        expiry = created_at + timedelta(seconds=max(0, entry.ttl_seconds))
        return now >= expiry


def _contains_shard(raw: object, shard_id: str) -> bool:
    if not raw:
        return False
    if isinstance(raw, list):
        return shard_id in {str(item) for item in raw}
    return shard_id == str(raw)
