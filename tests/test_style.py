import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECK_PATHS = [
    ROOT / "methodology" / "tools" / "mapping.py",
    ROOT / "methodology" / "tools" / "generate_mapping.py",
    ROOT / "tests" / "test_mapping.py",
    ROOT / "tests" / "test_style.py",
    ROOT / "tests" / "run_tests.py",
]


class StyleTests(unittest.TestCase):
    def test_no_tabs_or_trailing_whitespace(self) -> None:
        for path in CHECK_PATHS:
            text = path.read_text(encoding="ascii", errors="ignore")
            for idx, line in enumerate(text.splitlines(), 1):
                self.assertNotIn("\t", line, f"Tab found in {path}:{idx}")
                self.assertEqual(line, line.rstrip(), f"Trailing whitespace in {path}:{idx}")


if __name__ == "__main__":
    unittest.main()
