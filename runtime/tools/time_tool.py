from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TOOL_SPEC = {
    "name": "getCurrentTime",
    "description": (
        "Return the current date/time from the system clock in ISO 8601 format. "
        "Use this when the user asks for the current time or date."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone, e.g. America/New_York. Defaults to UTC.",
            }
        },
        "required": [],
    },
}


def get_current_time(timezone_name: str = "UTC") -> str:
    """Return current time for the requested timezone in ISO 8601 format."""
    if timezone_name.upper() in {"UTC", "Z"}:
        now = datetime.now(timezone.utc)
        return now.isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc
    now = datetime.now(tz)
    return now.isoformat(timespec="seconds")
