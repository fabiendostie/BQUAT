from __future__ import annotations

import os

from runtime.tools.time_tool import get_current_time as tool_current_time

DEFAULT_TIMEZONE = os.environ.get("BAQT_TIMEZONE", "America/Toronto")


def get_current_time() -> str:
    """Return current time in ISO 8601 format using the configured timezone."""
    return tool_current_time(DEFAULT_TIMEZONE)
