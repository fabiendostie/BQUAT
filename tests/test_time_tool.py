import re
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.tools import time_tool  # noqa: E402


class TimeToolTests(unittest.TestCase):
    def test_get_current_time_utc_format(self) -> None:
        value = time_tool.get_current_time("UTC")
        self.assertTrue(value.endswith("Z"))
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_get_current_time_timezone_format(self) -> None:
        try:
            ZoneInfo("America/New_York")
        except ZoneInfoNotFoundError:
            self.skipTest("tzdata not available")
        value = time_tool.get_current_time("America/New_York")
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[-+]\d{2}:\d{2}$")

    def test_invalid_timezone(self) -> None:
        with self.assertRaises(ValueError):
            time_tool.get_current_time("Not/AZone")


if __name__ == "__main__":
    unittest.main()
