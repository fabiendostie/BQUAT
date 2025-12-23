import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.tools import repo_tool  # noqa: E402


def _sandbox_root() -> Path:
    root = ROOT / "runs" / "tmp-tests" / uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


class RuntimeRepoToolTests(unittest.TestCase):
    def test_git_status_from_repo(self) -> None:
        output = repo_tool.git_status()
        self.assertIsInstance(output, str)

    def test_git_diff_from_repo(self) -> None:
        output = repo_tool.git_diff("README.md")
        self.assertIsInstance(output, str)

    def test_git_status_requires_repo(self) -> None:
        root = _sandbox_root()
        with self.assertRaises(ValueError):
            repo_tool.git_status(root=root)


if __name__ == "__main__":
    unittest.main()
