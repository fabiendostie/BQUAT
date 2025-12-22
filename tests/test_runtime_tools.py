import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.tools.base import ToolCall, ToolSpec, normalize_risk  # noqa: E402


class RuntimeToolTests(unittest.TestCase):
    def test_tool_spec_round_trip(self) -> None:
        spec = ToolSpec(
            name="getCurrentTime",
            description="Return current time",
            parameters={"type": "object"},
            risk="medium",
        )
        data = spec.to_dict()
        loaded = ToolSpec.from_dict(data)
        self.assertEqual(loaded.to_dict(), data)

    def test_tool_call_round_trip(self) -> None:
        call = ToolCall(
            name="getCurrentTime",
            args={"timezone": "UTC"},
            required=True,
            risk="high",
            gate="time-approval",
        )
        data = call.to_dict()
        loaded = ToolCall.from_dict(data)
        self.assertEqual(loaded.to_dict(), data)

    def test_invalid_risk_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_risk("critical")


if __name__ == "__main__":
    unittest.main()
