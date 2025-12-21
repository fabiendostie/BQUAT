import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.tools import time_tool  # noqa: E402


class TimeToolTests(unittest.TestCase):
    def test_get_current_time_default_format(self) -> None:
        value = time_tool.get_current_time()
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[-+]\d{2}:\d{2}$")

    def test_get_current_time_utc_format(self) -> None:
        value = time_tool.get_current_time("UTC")
        self.assertTrue(value.endswith("Z"))
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_get_current_time_z_format(self) -> None:
        value = time_tool.get_current_time("Z")
        self.assertTrue(value.endswith("Z"))

    def test_get_current_time_timezone_format(self) -> None:
        try:
            ZoneInfo("America/New_York")
        except ZoneInfoNotFoundError:
            self.skipTest("tzdata not available")
        value = time_tool.get_current_time("America/New_York")
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[-+]\d{2}:\d{2}$")

    def test_get_current_time_toronto_fallback(self) -> None:
        with patch(
            "runtime.tools.time_tool.ZoneInfo",
            side_effect=ZoneInfoNotFoundError("missing"),
        ):
            value = time_tool.get_current_time("America/Toronto")
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[-+]\d{2}:\d{2}$")

    def test_invalid_timezone(self) -> None:
        with self.assertRaises(ValueError):
            time_tool.get_current_time("Not/AZone")


if __name__ == "__main__":
    unittest.main()
