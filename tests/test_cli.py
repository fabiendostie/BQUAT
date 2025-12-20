import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cli import main as cli_main  # noqa: E402


class CliTests(unittest.TestCase):
    def _config_path(self, tmpdir: str) -> Path:
        cfg = {
            "runtime": {"storage_root": tmpdir},
            "providers": {"default": "mock", "mock": {"type": "mock"}},
        }
        path = Path(tmpdir) / "runtime.json"
        path.write_text(json.dumps(cfg), encoding="ascii")
        return path

    def test_validate_and_providers(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli_main.cmd_validate(cli_main.argparse.Namespace(config=None))
        data = json.loads(buf.getvalue())
        self.assertGreater(data["records"], 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = self._config_path(tmpdir)
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli_main.cmd_providers(cli_main.argparse.Namespace(config=str(cfg)))
            data = json.loads(buf.getvalue())
            self.assertIn("mock", data["providers"])

    def test_run_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = self._config_path(tmpdir)
            buf = io.StringIO()
            args = cli_main.argparse.Namespace(
                config=str(cfg),
                module="bmm",
                workflow="prd",
                run_id=None,
                agent="bmad",
                provider="mock",
            )
            with redirect_stdout(buf):
                cli_main.cmd_run(args)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["status"], "blocked")

            approve_args = cli_main.argparse.Namespace(
                config=str(cfg),
                run_id=payload["run_id"],
                by="tester",
                notes=None,
            )
            with redirect_stdout(io.StringIO()):
                cli_main.cmd_approve(approve_args)

            resume_args = cli_main.argparse.Namespace(
                config=str(cfg),
                run_id=payload["run_id"],
                agent="bmad",
                provider="mock",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli_main.cmd_resume(resume_args)
            resumed = json.loads(buf.getvalue())
            self.assertEqual(resumed["status"], "completed")

            status_args = cli_main.argparse.Namespace(
                config=str(cfg),
                run_id=payload["run_id"],
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli_main.cmd_status(status_args)
            manifest = json.loads(buf.getvalue())
            self.assertEqual(manifest["run_id"], payload["run_id"])


if __name__ == "__main__":
    unittest.main()
