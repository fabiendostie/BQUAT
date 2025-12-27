import unittest
from datetime import datetime, timedelta, timezone

from runtime.telis.cache import BehavioralCache


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)

    def now(self) -> datetime:
        return self.current


class RuntimeTelisCacheTests(unittest.TestCase):
    def test_cache_hit_updates_counters(self) -> None:
        clock = FakeClock(datetime(2025, 1, 1, tzinfo=timezone.utc))
        cache = BehavioralCache(now_provider=clock.now)
        cache.set("k1", "value", tokens_saved=10)
        entry = cache.get("k1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.hit_count, 1)

    def test_cache_expires_by_ttl(self) -> None:
        clock = FakeClock(datetime(2025, 1, 1, tzinfo=timezone.utc))
        cache = BehavioralCache(now_provider=clock.now)
        cache.set("k1", "value", ttl_seconds=1)
        clock.advance(2)
        self.assertIsNone(cache.get("k1"))

    def test_invalidation_triggers(self) -> None:
        clock = FakeClock(datetime(2025, 1, 1, tzinfo=timezone.utc))
        cache = BehavioralCache(now_provider=clock.now)
        cache.set(
            "k1",
            "value",
            metadata={"language": "python", "version": "3.11", "shard_ids": ["py.async"]},
        )
        removed = cache.invalidate_language_version("python", "3.11")
        self.assertEqual(removed, 1)
        cache.set(
            "k2",
            "value",
            metadata={"language": "python", "version": "3.11", "shard_ids": ["py.async"]},
        )
        removed = cache.invalidate_shard_update("py.async")
        self.assertEqual(removed, 1)


if __name__ == "__main__":
    unittest.main()
