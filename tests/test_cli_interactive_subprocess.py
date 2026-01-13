"""Subprocess-driven interactive CLI test."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def _extract_run_id(output: str) -> str:
    for line in reversed(output.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id"):
            return str(payload["run_id"])
    return ""


class CliInteractiveSubprocessTests(unittest.TestCase):
    """Run `cli.main start` with scripted inputs."""

    def setUp(self) -> None:
        self.sandbox = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.config_path = self.sandbox / "runtime.json"
        config = {
            "runtime": {
                "storage_root": str(self.sandbox),
                "max_retries": 0,
                "step_timeout_seconds": 30,
            },
            "automation": {"override": True},
            "hitl": {"mode": "disabled"},
            "providers": {"default": "mock", "mock": {"type": "mock", "model": "mock"}},
        }
        self.config_path.write_text(json.dumps(config), encoding="ascii")

    def tearDown(self) -> None:
        if self.sandbox.exists():
            shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_cli_start_brainstorming(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "cli.main",
            "--config",
            str(self.config_path),
            "start",
            "--module",
            "core",
            "--workflow",
            "brainstorming",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        input_text = "\n".join(["skip"] * 20) + "\n"
        result = subprocess.run(
            cmd,
            input=input_text,
            text=True,
            capture_output=True,
            cwd=ROOT,
            env=env,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        run_id = _extract_run_id(result.stdout)
        self.assertTrue(run_id, msg="run_id not found in CLI output")
        manifest_path = self.sandbox / run_id / "manifest.json"
        self.assertTrue(manifest_path.exists())


if __name__ == "__main__":
    unittest.main()
