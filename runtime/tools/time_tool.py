from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from runtime.tools.base import ToolSpec

TOOL_SPEC = ToolSpec(
    name="getCurrentTime",
    description=(
        "Return the current date/time from the system clock in ISO 8601 format. "
        "Use this when the user asks for the current time or date. Default timezone: America/Toronto."
    ),
    parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone, e.g. America/New_York. Defaults to America/Toronto.",
            }
        },
        "required": [],
    },
    risk="low",
).to_dict()


def get_current_time(timezone_name: str = "America/Toronto") -> str:
    """Return current time for the requested timezone in ISO 8601 format."""
    if timezone_name.upper() in {"UTC", "Z"}:
        now = datetime.now(timezone.utc)
        return now.isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        if timezone_name == "America/Toronto":
            now = datetime.now().astimezone()
            return now.isoformat(timespec="seconds")
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc
    now = datetime.now(tz)
    return now.isoformat(timespec="seconds")
