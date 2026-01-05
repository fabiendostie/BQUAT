"""Comprehensive tests for cli/main.py to achieve 85%+ coverage."""

from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cli import main as cli_main  # noqa: E402


class TestBuildParser(unittest.TestCase):
    """Test the CLI parser construction."""

    def test_parser_creation(self) -> None:
        parser = cli_main.build_parser()
        self.assertIsNotNone(parser)
        self.assertEqual(parser.prog, "baqt")

    def test_parser_validate(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["validate"])
        self.assertEqual(args.command, "validate")

    def test_parser_run(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["run", "bmm", "prd"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.module, "bmm")
        self.assertEqual(args.workflow, "prd")

    def test_parser_run_with_options(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(
            [
                "run",
                "bmm",
                "prd",
                "--run-id",
                "test-123",
                "--agent",
                "bmad",
                "--provider",
                "mock",
                "--auto",
            ]
        )
        self.assertEqual(args.run_id, "test-123")
        self.assertEqual(args.agent, "bmad")
        self.assertEqual(args.provider, "mock")
        self.assertTrue(args.auto)

    def test_parser_run_orchestrate(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["run", "bmm", "prd", "--orchestrate"])
        self.assertTrue(args.orchestrate)

    def test_parser_resume(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["resume", "run-123"])
        self.assertEqual(args.command, "resume")
        self.assertEqual(args.run_id, "run-123")

    def test_parser_orchestrate(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["orchestrate", "--plan", "plan.yaml"])
        self.assertEqual(args.command, "orchestrate")
        self.assertEqual(args.plan, "plan.yaml")

    def test_parser_approve(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["approve", "run-123", "--by", "user"])
        self.assertEqual(args.command, "approve")
        self.assertEqual(args.run_id, "run-123")
        self.assertEqual(args.by, "user")

    def test_parser_status(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["status", "run-123"])
        self.assertEqual(args.command, "status")
        self.assertEqual(args.run_id, "run-123")

    def test_parser_list(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["list"])
        self.assertEqual(args.command, "list")
        self.assertIsNone(args.module)

    def test_parser_list_with_module(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["list", "--module", "bmm"])
        self.assertEqual(args.module, "bmm")

    def test_parser_history(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["history"])
        self.assertEqual(args.command, "history")
        self.assertIsNone(args.limit)

    def test_parser_history_with_limit(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["history", "--limit", "5"])
        self.assertEqual(args.limit, 5)

    def test_parser_export(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["export", "run-123"])
        self.assertEqual(args.command, "export")
        self.assertEqual(args.run_id, "run-123")

    def test_parser_export_with_output(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["export", "run-123", "--output", "out.json"])
        self.assertEqual(args.output, "out.json")

    def test_parser_export_with_report(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["export", "run-123", "--report"])
        self.assertTrue(args.report)

    def test_parser_providers(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["providers"])
        self.assertEqual(args.command, "providers")

    def test_parser_interactive(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["interactive"])
        self.assertEqual(args.command, "interactive")

    def test_parser_interactive_with_options(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(
            [
                "interactive",
                "--module",
                "bmm",
                "--workflow",
                "prd",
                "--run-id",
                "test-123",
                "--provider",
                "mock",
            ]
        )
        self.assertEqual(args.module, "bmm")
        self.assertEqual(args.workflow, "prd")

    def test_parser_start(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(["start"])
        self.assertEqual(args.command, "start")
        self.assertEqual(args.module, "core")
        self.assertEqual(args.workflow, "brainstorming")

    def test_parser_start_with_options(self) -> None:
        parser = cli_main.build_parser()
        args = parser.parse_args(
            [
                "start",
                "--module",
                "bmm",
                "--workflow",
                "prd",
                "--provider",
                "mock",
            ]
        )
        self.assertEqual(args.module, "bmm")
        self.assertEqual(args.workflow, "prd")


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""

    def setUp(self) -> None:
        self.test_dir = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_config_default(self) -> None:
        config = cli_main._load_config(None)
        self.assertIsInstance(config, dict)

    def test_load_config_from_path(self) -> None:
        cfg_path = self.test_dir / "config.json"
        cfg_path.write_text(json.dumps({"test": "value"}), encoding="utf-8")
        config = cli_main._load_config(str(cfg_path))
        self.assertIn("test", config)

    def test_with_automation_override(self) -> None:
        config = {"automation": {"phases": ["Phase 1"]}}
        updated = cli_main._with_automation_override(config)
        self.assertTrue(updated["automation"]["override"])
        self.assertIn("phases", updated["automation"])

    def test_workflow_payload(self) -> None:
        from runtime.models import WorkflowSpec

        spec = WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2",
            quint="L1",
            telis="Tier 1",
            validation="Schema",
            human="required",
            evidence="L1",
            artifacts=["out.md"],
            scope="production",
            path="test/path",
        )
        payload = cli_main._workflow_payload(spec)
        self.assertEqual(payload["module"], "bmm")
        self.assertEqual(payload["workflow"], "prd")
        self.assertEqual(payload["artifacts"], ["out.md"])

    def test_summarize_run(self) -> None:
        manifest = {
            "run_id": "run-123",
            "status": "completed",
            "workflow": {"module": "bmm", "workflow": "prd", "phase": "Phase 2"},
            "steps": [
                {"status": "completed"},
                {"status": "completed"},
            ],
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T01:00:00",
            "current_step": 2,
        }
        summary = cli_main._summarize_run(manifest)
        self.assertEqual(summary["run_id"], "run-123")
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["steps_completed"], 2)
        self.assertEqual(summary["steps_total"], 2)


class TestLoadPlanFile(unittest.TestCase):
    """Test plan file loading."""

    def setUp(self) -> None:
        self.test_dir = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_json_plan(self) -> None:
        plan_path = self.test_dir / "plan.json"
        plan_data = {
            "workflows": [
                {"module": "bmm", "workflow": "prd"},
            ]
        }
        plan_path.write_text(json.dumps(plan_data), encoding="ascii")
        loaded = cli_main._load_plan_file(str(plan_path))
        self.assertEqual(loaded["workflows"][0]["module"], "bmm")

    def test_load_orchestration_nodes(self) -> None:
        plan_path = self.test_dir / "plan.json"
        plan_data = {
            "workflows": [
                {
                    "module": "bmm",
                    "workflow": "prd",
                    "depends_on": ["core/brainstorming"],
                    "agent": "bmad",
                    "provider": "mock",
                },
            ]
        }
        plan_path.write_text(json.dumps(plan_data), encoding="ascii")
        nodes = cli_main._load_orchestration_nodes(str(plan_path))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].module, "bmm")
        self.assertEqual(nodes[0].workflow, "prd")
        self.assertIn("core/brainstorming", nodes[0].dependencies)

    def test_load_orchestration_nodes_empty(self) -> None:
        plan_path = self.test_dir / "plan.json"
        plan_path.write_text("{}", encoding="ascii")
        nodes = cli_main._load_orchestration_nodes(str(plan_path))
        self.assertEqual(len(nodes), 0)

    def test_load_orchestration_nodes_invalid_items(self) -> None:
        plan_path = self.test_dir / "plan.json"
        plan_data = {
            "workflows": [
                "not a dict",
                {"module": ""},  # Missing workflow
                {"workflow": "prd"},  # Missing module
                {"module": "bmm", "workflow": "prd"},  # Valid
            ]
        }
        plan_path.write_text(json.dumps(plan_data), encoding="ascii")
        nodes = cli_main._load_orchestration_nodes(str(plan_path))
        self.assertEqual(len(nodes), 1)


class TestPromptAutomation(unittest.TestCase):
    """Test automation prompting."""

    def test_automation_decision_no_agent(self) -> None:
        from runtime.models import WorkflowSpec

        spec = WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2",
            quint="L1",
            telis="Tier 1",
            validation="",
            human="",
            evidence="",
            artifacts=[],
            scope="",
            path="",
        )
        args = cli_main.argparse.Namespace(agent=None, auto=False, manual=False)
        result = cli_main._automation_decision({}, spec, args)
        self.assertIsNone(result)

    def test_automation_decision_auto_flag(self) -> None:
        from runtime.models import WorkflowSpec

        spec = WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2",
            quint="L1",
            telis="Tier 1",
            validation="",
            human="",
            evidence="",
            artifacts=[],
            scope="",
            path="",
        )
        config = {"automation": {"phases": ["Phase 1"]}}
        args = cli_main.argparse.Namespace(agent="bmad", auto=True, manual=False)
        result = cli_main._automation_decision(config, spec, args)
        self.assertTrue(result)

    def test_automation_decision_manual_flag(self) -> None:
        from runtime.models import WorkflowSpec

        spec = WorkflowSpec(
            module="bmm",
            workflow="prd",
            phase="Phase 2",
            quint="L1",
            telis="Tier 1",
            validation="",
            human="",
            evidence="",
            artifacts=[],
            scope="",
            path="",
        )
        config = {"automation": {"phases": ["Phase 1"]}}
        args = cli_main.argparse.Namespace(agent="bmad", auto=False, manual=True)
        result = cli_main._automation_decision(config, spec, args)
        self.assertFalse(result)


class TestCliCommands(unittest.TestCase):
    """Test CLI command functions."""

    def setUp(self) -> None:
        self.test_dir = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self._create_config()

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_config(self) -> Path:
        cfg = {
            "runtime": {"storage_root": str(self.test_dir)},
            "providers": {"default": "mock", "mock": {"type": "mock"}},
        }
        path = self.test_dir / "runtime.json"
        path.write_text(json.dumps(cfg), encoding="ascii")
        return path

    def test_cmd_validate(self) -> None:
        buf = io.StringIO()
        args = cli_main.argparse.Namespace(config=None)
        with redirect_stdout(buf):
            result = cli_main.cmd_validate(args)
        self.assertEqual(result, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("records", data)

    def test_cmd_list(self) -> None:
        buf = io.StringIO()
        args = cli_main.argparse.Namespace(config=str(self.config_path), module=None)
        with redirect_stdout(buf):
            result = cli_main.cmd_list(args)
        self.assertEqual(result, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("workflows", data)

    def test_cmd_list_with_filter(self) -> None:
        buf = io.StringIO()
        args = cli_main.argparse.Namespace(config=str(self.config_path), module="bmm")
        with redirect_stdout(buf):
            result = cli_main.cmd_list(args)
        self.assertEqual(result, 0)
        data = json.loads(buf.getvalue())
        for workflow in data["workflows"]:
            self.assertEqual(workflow["module"], "bmm")

    def test_cmd_providers(self) -> None:
        buf = io.StringIO()
        args = cli_main.argparse.Namespace(config=str(self.config_path))
        with redirect_stdout(buf):
            result = cli_main.cmd_providers(args)
        self.assertEqual(result, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("mock", data["providers"])

    def test_cmd_history_empty(self) -> None:
        buf = io.StringIO()
        args = cli_main.argparse.Namespace(config=str(self.config_path), limit=None)
        with redirect_stdout(buf):
            result = cli_main.cmd_history(args)
        self.assertEqual(result, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("runs", data)

    def test_cmd_run_creates_run(self) -> None:
        buf = io.StringIO()
        args = cli_main.argparse.Namespace(
            config=str(self.config_path),
            module="bmm",
            workflow="prd",
            run_id=None,
            agent="bmad",
            provider="mock",
            auto=False,
            manual=False,
            orchestrate=False,
        )
        with redirect_stdout(buf):
            result = cli_main.cmd_run(args)
        self.assertEqual(result, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("run_id", data)
        self.assertIn("status", data)


class TestMain(unittest.TestCase):
    """Test main entry point."""

    def test_main_with_validate(self) -> None:
        with patch.object(sys, "argv", ["baqt", "validate"]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = cli_main.main()
            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
