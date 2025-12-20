import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import config as runtime_config  # noqa: E402


class RuntimeConfigTests(unittest.TestCase):
    def test_load_config_from_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cfg = {"runtime": {"storage_root": "runs"}}
            path = tmp / "runtime.yaml"
            path.write_text(json.dumps(cfg), encoding="ascii")
            loaded = runtime_config.load_config(path)
            self.assertEqual(loaded["runtime"]["storage_root"], "runs")

    def test_storage_root_resolution(self) -> None:
        cfg = {"runtime": {"storage_root": "runs"}}
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            resolved = runtime_config.storage_root(cfg, root=root)
            self.assertEqual(resolved, (root / "runs").resolve())


if __name__ == "__main__":
    unittest.main()
