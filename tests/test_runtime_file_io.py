import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.tools import file_io  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class RuntimeFileIoTests(unittest.TestCase):
    def test_write_and_read_text_file(self) -> None:
        root = _sandbox_root()
        file_io.write_text_file("notes/readme.txt", "hello", root=root)
        content = file_io.read_text_file("notes/readme.txt", root=root)
        self.assertEqual(content, "hello")

    def test_list_directory(self) -> None:
        root = _sandbox_root()
        (root / "a.txt").write_text("a", encoding="utf-8")
        (root / "b.txt").write_text("b", encoding="utf-8")
        entries = file_io.list_directory(".", root=root)
        self.assertEqual(entries, ["a.txt", "b.txt"])

    def test_disallow_outside_root(self) -> None:
        root = _sandbox_root()
        with self.assertRaises(ValueError):
            file_io.write_text_file("../escape.txt", "nope", root=root)


if __name__ == "__main__":
    unittest.main()
