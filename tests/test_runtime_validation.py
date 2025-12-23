import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.tools import validation  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class RuntimeValidationTests(unittest.TestCase):
    def test_ast_python_pass(self) -> None:
        root = _sandbox_root()
        source = "def add(a: int, b: int) -> int:\n    return a + b\n"
        (root / "good.py").write_text(source, encoding="utf-8")
        result = validation.validate_ast("good.py", root=root)
        self.assertEqual(result.status, "passed")

    def test_ast_python_fail(self) -> None:
        root = _sandbox_root()
        (root / "bad.py").write_text("def add(:\n    pass\n", encoding="utf-8")
        result = validation.validate_ast("bad.py", root=root)
        self.assertEqual(result.status, "failed")

    def test_typecheck_python_fail(self) -> None:
        root = _sandbox_root()
        (root / "types.py").write_text(
            "def add(a: int, b: int) -> int:\n    return 'nope'\n",
            encoding="utf-8",
        )
        result = validation.validate_typecheck("types.py", root=root)
        if result.status == "skipped":
            self.skipTest(result.stderr or "typecheck skipped")
        self.assertEqual(result.status, "failed")

    def test_lint_python_fail(self) -> None:
        root = _sandbox_root()
        source = "import os\n\n\ndef main() -> None:\n    pass\n"
        (root / "lint.py").write_text(source, encoding="utf-8")
        result = validation.validate_lint("lint.py", root=root)
        if result.status == "skipped":
            self.skipTest(result.stderr or "lint skipped")
        self.assertEqual(result.status, "failed")

    def test_pipeline_summary(self) -> None:
        root = _sandbox_root()
        source = "def add(a: int, b: int) -> int:\n    return a + b\n"
        (root / "ok.py").write_text(source, encoding="utf-8")
        summary = validation.run_validation_pipeline("ok.py", root=root)
        self.assertEqual(summary.status, "passed")


if __name__ == "__main__":
    unittest.main()
