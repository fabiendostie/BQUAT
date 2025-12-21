from __future__ import annotations

from datetime import datetime, timezone


def get_current_time() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
