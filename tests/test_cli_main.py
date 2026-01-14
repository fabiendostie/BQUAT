"""Tests for cli/main.py commands."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest import mock

from cli import main as cli_main


class TestHelperFunctions(unittest.TestCase):
    """Tests for helper functions."""

    def test_load_config_default(self) -> None:
        """Test _load_config with default path."""
        with mock.patch("cli.main.runtime_config.load_config") as mock_load:
            mock_load.return_value = {"key": "value"}
            result = cli_main._load_config(None)
            self.assertEqual(result, {"key": "value"})
            mock_load.assert_called_once_with(None)

    def test_load_config_with_path(self) -> None:
        """Test _load_config with explicit path."""
        with mock.patch("cli.main.runtime_config.load_config") as mock_load:
            mock_load.return_value = {"key": "value"}
            result = cli_main._load_config("/some/path")
            self.assertEqual(result, {"key": "value"})
            mock_load.assert_called_once_with(Path("/some/path"))

    def test_engine_creates_workflow_engine(self) -> None:
        """Test _engine creates WorkflowEngine."""
        config: Dict[str, Any] = {"runtime": {}}
        with mock.patch("cli.main.engine.load_mapping_records") as mock_records:
            with mock.patch("cli.main.engine.WorkflowEngine") as mock_engine:
                mock_records.return_value = []
                cli_main._engine(config)
                mock_engine.assert_called_once_with(config, [])

    def test_with_automation_override(self) -> None:
        """Test _with_automation_override sets override flag."""
        config: Dict[str, Any] = {"automation": {"phases": ["planning"]}}
        result = cli_main._with_automation_override(config)
        self.assertTrue(result["automation"]["override"])
        self.assertEqual(result["automation"]["phases"], ["planning"])

    def test_with_automation_override_empty(self) -> None:
        """Test _with_automation_override with empty config."""
        config: Dict[str, Any] = {}
        result = cli_main._with_automation_override(config)
        self.assertTrue(result["automation"]["override"])

    def test_workflow_payload(self) -> None:
        """Test _workflow_payload extracts fields."""
        from runtime.models import WorkflowSpec

        spec = WorkflowSpec(
            module="core",
            workflow="prd",
            phase="planning",
            quint="enabled",
            telis="enabled",
            validation="typecheck",
            human="required",
            evidence="L2",
            scope="full",
            path="/path/to/workflow",
            artifacts=["doc.md"],
        )
        result = cli_main._workflow_payload(spec)
        self.assertEqual(result["module"], "core")
        self.assertEqual(result["workflow"], "prd")
        self.assertEqual(result["phase"], "planning")
        self.assertEqual(result["artifacts"], ["doc.md"])

    def test_summarize_run(self) -> None:
        """Test _summarize_run extracts summary."""
        manifest: Dict[str, Any] = {
            "run_id": "run-123",
            "status": "completed",
            "workflow": {"module": "core", "workflow": "prd", "phase": "planning"},
            "steps": [
                {"status": "completed"},
                {"status": "completed"},
                {"status": "pending"},
            ],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "current_step": 2,
        }
        result = cli_main._summarize_run(manifest)
        self.assertEqual(result["run_id"], "run-123")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["steps_completed"], 2)
        self.assertEqual(result["steps_total"], 3)

    def test_load_plan_file_json(self) -> None:
        """Test _load_plan_file with JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text('{"workflows": []}', encoding="ascii")
            result = cli_main._load_plan_file(str(path))
            self.assertEqual(result, {"workflows": []})

    def test_load_orchestration_nodes_empty(self) -> None:
        """Test _load_orchestration_nodes with empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text("{}", encoding="ascii")
            result = cli_main._load_orchestration_nodes(str(path))
            self.assertEqual(result, [])

    def test_load_orchestration_nodes_with_workflows(self) -> None:
        """Test _load_orchestration_nodes with workflows."""
        data = {
            "workflows": [
                {"module": "core", "workflow": "prd", "dependencies": ["brainstorm"]},
                {"module": "core", "workflow": "arch"},
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text(json.dumps(data), encoding="ascii")
            result = cli_main._load_orchestration_nodes(str(path))
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].module, "core")
            self.assertEqual(result[0].workflow, "prd")
            self.assertEqual(result[0].dependencies, ["brainstorm"])


class TestCmdValidate(unittest.TestCase):
    """Tests for cmd_validate."""

    def test_cmd_validate(self) -> None:
        """Test validate command outputs record count."""
        with mock.patch("cli.main.engine.load_mapping_records") as mock_records:
            mock_records.return_value = [mock.Mock(), mock.Mock()]
            args = argparse.Namespace()
            with mock.patch("builtins.print") as mock_print:
                result = cli_main.cmd_validate(args)
                self.assertEqual(result, 0)
                mock_print.assert_called_once()
                output = mock_print.call_args[0][0]
                self.assertIn('"records": 2', output)


class TestCmdList(unittest.TestCase):
    """Tests for cmd_list."""

    def test_cmd_list_all(self) -> None:
        """Test list command shows all workflows."""
        from runtime.models import WorkflowSpec

        mock_record = WorkflowSpec(
            module="core",
            workflow="prd",
            phase="planning",
            quint="enabled",
            telis="enabled",
            validation="none",
            human="false",
            evidence="L1",
            scope="full",
            path="/path",
            artifacts=[],
        )
        with mock.patch("cli.main.engine.load_mapping_records") as mock_records:
            mock_records.return_value = [mock_record]
            args = argparse.Namespace(module=None)
            with mock.patch("builtins.print") as mock_print:
                result = cli_main.cmd_list(args)
                self.assertEqual(result, 0)
                output = mock_print.call_args[0][0]
                self.assertIn("workflows", output)

    def test_cmd_list_by_module(self) -> None:
        """Test list command filters by module."""
        from runtime.models import WorkflowSpec

        mock_record = WorkflowSpec(
            module="core",
            workflow="prd",
            phase="planning",
            quint="enabled",
            telis="enabled",
            validation="none",
            human="false",
            evidence="L1",
            scope="full",
            path="/path",
            artifacts=[],
        )
        with mock.patch("cli.main.engine.load_mapping_records") as mock_records:
            mock_records.return_value = [mock_record]
            args = argparse.Namespace(module="core")
            with mock.patch("builtins.print"):
                result = cli_main.cmd_list(args)
                self.assertEqual(result, 0)


class TestCmdProviders(unittest.TestCase):
    """Tests for cmd_providers."""

    def test_cmd_providers(self) -> None:
        """Test providers command lists providers."""
        config = {"providers": {"openai": {}, "anthropic": {}, "default": "openai"}}
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = config
            args = argparse.Namespace(config=None)
            with mock.patch("builtins.print") as mock_print:
                result = cli_main.cmd_providers(args)
                self.assertEqual(result, 0)
                output = mock_print.call_args[0][0]
                self.assertIn("providers", output)


class TestCmdTelisStatus(unittest.TestCase):
    """Tests for cmd_telis_status."""

    def test_telis_status_default(self) -> None:
        """Test telis status with defaults."""
        config: Dict[str, Any] = {"telis": {}}
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = config
            args = argparse.Namespace(config=None)
            with mock.patch("builtins.print") as mock_print:
                result = cli_main.cmd_telis_status(args)
                self.assertEqual(result, 0)
                calls = [str(c) for c in mock_print.call_args_list]
                self.assertTrue(any("TELIS Configuration" in c for c in calls))

    def test_telis_status_with_budgets(self) -> None:
        """Test telis status with tier budgets."""
        config: Dict[str, Any] = {
            "telis": {
                "policy": "strict",
                "tier_budgets": {"tier_1_nano": 100, "tier_2_micro": 1000},
            }
        }
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = config
            args = argparse.Namespace(config=None)
            with mock.patch("builtins.print"):
                result = cli_main.cmd_telis_status(args)
                self.assertEqual(result, 0)

    def test_telis_status_with_shards_path(self) -> None:
        """Test telis status with shards path configured."""
        config: Dict[str, Any] = {
            "telis": {
                "shards_path": "/path/to/shards.yaml",
                "shards": [{"id": "test"}],
            }
        }
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = config
            args = argparse.Namespace(config=None)
            with mock.patch("builtins.print"):
                result = cli_main.cmd_telis_status(args)
                self.assertEqual(result, 0)


class TestCmdTelisList(unittest.TestCase):
    """Tests for cmd_telis_list."""

    def test_telis_list_disabled(self) -> None:
        """Test telis list when TELIS is disabled."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {"telis": {"enabled": False}}
            with mock.patch("runtime.telis.manager.TelisPolicyEngine.from_config") as mock_engine:
                mock_engine.return_value = None
                args = argparse.Namespace(config=None, language=None, tier=None)
                with mock.patch("builtins.print") as mock_print:
                    result = cli_main.cmd_telis_list(args)
                    self.assertEqual(result, 1)
                    calls = [str(c) for c in mock_print.call_args_list]
                    self.assertTrue(any("disabled" in c for c in calls))

    def test_telis_list_empty(self) -> None:
        """Test telis list with no shards."""
        mock_engine = mock.Mock()
        mock_engine.registry.list.return_value = []
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {"telis": {}}
            with mock.patch(
                "runtime.telis.manager.TelisPolicyEngine.from_config"
            ) as mock_from_config:
                mock_from_config.return_value = mock_engine
                args = argparse.Namespace(config=None, language=None, tier=None)
                with mock.patch("builtins.print") as mock_print:
                    result = cli_main.cmd_telis_list(args)
                    self.assertEqual(result, 0)
                    calls = [str(c) for c in mock_print.call_args_list]
                    self.assertTrue(any("No shards" in c for c in calls))

    def test_telis_list_with_shards(self) -> None:
        """Test telis list with shards."""
        mock_shard = mock.Mock()
        mock_shard.shard_id = "python.async"
        mock_shard.language = "python"
        mock_shard.tier = "tier_2_micro"
        mock_shard.topics = ["async", "await"]
        mock_shard.tokens = 200

        mock_engine = mock.Mock()
        mock_engine.registry.list.return_value = [mock_shard]

        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {"telis": {}}
            with mock.patch(
                "runtime.telis.manager.TelisPolicyEngine.from_config"
            ) as mock_from_config:
                mock_from_config.return_value = mock_engine
                args = argparse.Namespace(config=None, language="python", tier=None)
                with mock.patch("builtins.print"):
                    result = cli_main.cmd_telis_list(args)
                    self.assertEqual(result, 0)
                    mock_engine.registry.list.assert_called_with(language="python", tier=None)


class TestCmdTelisAdd(unittest.TestCase):
    """Tests for cmd_telis_add."""

    def test_telis_add_file_not_found(self) -> None:
        """Test telis add with missing file."""
        args = argparse.Namespace(file="/nonexistent/file.yaml")
        with mock.patch("builtins.print") as mock_print:
            result = cli_main.cmd_telis_add(args)
            self.assertEqual(result, 1)
            calls = [str(c) for c in mock_print.call_args_list]
            self.assertTrue(any("not found" in c for c in calls))

    def test_telis_add_no_shards(self) -> None:
        """Test telis add with file containing no shards."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "empty.json"
            path.write_text("{}", encoding="utf-8")
            args = argparse.Namespace(file=str(path))
            with mock.patch("builtins.print") as mock_print:
                result = cli_main.cmd_telis_add(args)
                self.assertEqual(result, 1)
                calls = [str(c) for c in mock_print.call_args_list]
                self.assertTrue(any("No shards" in c for c in calls))

    def test_telis_add_with_shards(self) -> None:
        """Test telis add with valid shards."""
        data = {"shards": [{"id": "test.shard", "language": "python", "tier": "tier_1_nano"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "shards.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            args = argparse.Namespace(file=str(path))
            with mock.patch("builtins.print"):
                result = cli_main.cmd_telis_add(args)
                self.assertEqual(result, 0)

    def test_telis_add_with_config_exists(self) -> None:
        """Test telis add when config file exists."""
        data = {"shards": [{"id": "test.shard", "language": "python", "tier": "tier_1_nano"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create shards file
            shards_path = Path(tmpdir) / "shards.json"
            shards_path.write_text(json.dumps(data), encoding="utf-8")

            # Create config directory
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            (config_dir / "runtime.yaml").write_text("test: true", encoding="utf-8")

            # Run from tmpdir so config/runtime.yaml exists
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                args = argparse.Namespace(file=str(shards_path))
                with mock.patch("builtins.print"):
                    result = cli_main.cmd_telis_add(args)
                    self.assertEqual(result, 0)
            finally:
                os.chdir(old_cwd)


class TestCmdTelisInit(unittest.TestCase):
    """Tests for cmd_telis_init."""

    def test_telis_init_creates_file(self) -> None:
        """Test telis init creates sample config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "telis-shards.yaml"
            args = argparse.Namespace(output=str(output_path))
            with mock.patch("builtins.print"):
                result = cli_main.cmd_telis_init(args)
                self.assertEqual(result, 0)
                self.assertTrue(output_path.exists())
                content = output_path.read_text()
                self.assertIn("shards:", content)
                self.assertIn("python.async", content)


class TestCmdQuintStatus(unittest.TestCase):
    """Tests for cmd_quint_status."""

    def test_quint_status_run_not_found(self) -> None:
        """Test quint status with missing run."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {"runtime": {"storage_root": "/tmp/runs"}}
            with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                mock_root.return_value = Path("/tmp/nonexistent")
                args = argparse.Namespace(config=None, run_id="run-missing")
                with mock.patch("builtins.print") as mock_print:
                    result = cli_main.cmd_quint_status(args)
                    self.assertEqual(result, 1)
                    calls = [str(c) for c in mock_print.call_args_list]
                    self.assertTrue(any("not found" in c for c in calls))

    def test_quint_status_with_evidence(self) -> None:
        """Test quint status with evidence data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "evidence.json").write_text(
                json.dumps(
                    {
                        "evidence": [
                            {"level": "L1", "evidence_id": "e1"},
                            {"level": "L2", "evidence_id": "e2"},
                        ]
                    }
                )
            )
            (run_dir / "drr.json").write_text(json.dumps({"drrs": [{"drr_id": "d1"}]}))

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123")
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_quint_status(args)
                        self.assertEqual(result, 0)

    def test_quint_status_with_drift(self) -> None:
        """Test quint status with drift detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "evidence.json").write_text(json.dumps({"evidence": []}))
            (run_dir / "drr.json").write_text(json.dumps({"drrs": []}))
            (run_dir / "drift.json").write_text(json.dumps({"drifts": [{"type": "context"}]}))

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123")
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_quint_status(args)
                        self.assertEqual(result, 0)


class TestCmdQuintEvidence(unittest.TestCase):
    """Tests for cmd_quint_evidence."""

    def test_quint_evidence_run_not_found(self) -> None:
        """Test quint evidence with missing run."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                mock_root.return_value = Path("/tmp/nonexistent")
                args = argparse.Namespace(config=None, run_id="run-missing", level=None)
                with mock.patch("builtins.print"):
                    result = cli_main.cmd_quint_evidence(args)
                    self.assertEqual(result, 1)

    def test_quint_evidence_empty(self) -> None:
        """Test quint evidence with no records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "evidence.json").write_text(json.dumps({"evidence": []}))

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123", level=None)
                    with mock.patch("builtins.print") as mock_print:
                        result = cli_main.cmd_quint_evidence(args)
                        self.assertEqual(result, 0)
                        calls = [str(c) for c in mock_print.call_args_list]
                        self.assertTrue(any("No evidence" in c for c in calls))

    def test_quint_evidence_with_records(self) -> None:
        """Test quint evidence with records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "evidence.json").write_text(
                json.dumps(
                    {
                        "evidence": [
                            {
                                "evidence_id": "e1",
                                "level": "L2",
                                "evidence_type": "test",
                                "source_step": "step1",
                                "wlnk_score": 0.8,
                                "claim": "This is a test claim for the evidence",
                            }
                        ]
                    }
                )
            )

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123", level=None)
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_quint_evidence(args)
                        self.assertEqual(result, 0)

    def test_quint_evidence_filter_by_level(self) -> None:
        """Test quint evidence filters by level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "evidence.json").write_text(
                json.dumps(
                    {
                        "evidence": [
                            {"evidence_id": "e1", "level": "L1"},
                            {"evidence_id": "e2", "level": "L2"},
                        ]
                    }
                )
            )

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123", level="L2")
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_quint_evidence(args)
                        self.assertEqual(result, 0)


class TestCmdQuintDrr(unittest.TestCase):
    """Tests for cmd_quint_drr."""

    def test_quint_drr_run_not_found(self) -> None:
        """Test quint drr with missing run."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                mock_root.return_value = Path("/tmp/nonexistent")
                args = argparse.Namespace(config=None, run_id="run-missing")
                with mock.patch("builtins.print"):
                    result = cli_main.cmd_quint_drr(args)
                    self.assertEqual(result, 1)

    def test_quint_drr_empty(self) -> None:
        """Test quint drr with no records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "drr.json").write_text(json.dumps({"drrs": []}))

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123")
                    with mock.patch("builtins.print") as mock_print:
                        result = cli_main.cmd_quint_drr(args)
                        self.assertEqual(result, 0)
                        calls = [str(c) for c in mock_print.call_args_list]
                        self.assertTrue(any("No Decision" in c for c in calls))

    def test_quint_drr_with_records(self) -> None:
        """Test quint drr with records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "drr.json").write_text(
                json.dumps(
                    {
                        "drrs": [
                            {
                                "drr_id": "d1",
                                "title": "Architecture Decision",
                                "status": "approved",
                                "decision": {"choice": "option_a"},
                                "options": ["a", "b"],
                                "evidence": ["e1"],
                            }
                        ]
                    }
                )
            )

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123")
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_quint_drr(args)
                        self.assertEqual(result, 0)

    def test_quint_drr_with_string_decision(self) -> None:
        """Test quint drr with string decision value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "drr.json").write_text(
                json.dumps(
                    {
                        "drrs": [
                            {
                                "drr_id": "d1",
                                "title": "Simple Decision",
                                "status": "approved",
                                "decision": "option_a",
                            }
                        ]
                    }
                )
            )

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123")
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_quint_drr(args)
                        self.assertEqual(result, 0)


class TestBuildParser(unittest.TestCase):
    """Tests for build_parser."""

    def test_build_parser_commands(self) -> None:
        """Test parser has all expected commands."""
        parser = cli_main.build_parser()
        # Check that parser was created
        self.assertIsNotNone(parser)

    def test_parse_telis_status(self) -> None:
        """Test parsing telis status command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["telis", "status"])
        self.assertEqual(args.func, cli_main.cmd_telis_status)

    def test_parse_telis_list(self) -> None:
        """Test parsing telis list command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["telis", "list", "--language", "python"])
        self.assertEqual(args.func, cli_main.cmd_telis_list)
        self.assertEqual(args.language, "python")

    def test_parse_telis_init(self) -> None:
        """Test parsing telis init command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["telis", "init", "--output", "/tmp/shards.yaml"])
        self.assertEqual(args.func, cli_main.cmd_telis_init)
        self.assertEqual(args.output, "/tmp/shards.yaml")

    def test_parse_telis_add(self) -> None:
        """Test parsing telis add command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["telis", "add", "/path/to/shards.yaml"])
        self.assertEqual(args.func, cli_main.cmd_telis_add)
        self.assertEqual(args.file, "/path/to/shards.yaml")

    def test_parse_quint_status(self) -> None:
        """Test parsing quint status command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["quint", "status", "run-123"])
        self.assertEqual(args.func, cli_main.cmd_quint_status)
        self.assertEqual(args.run_id, "run-123")

    def test_parse_quint_evidence(self) -> None:
        """Test parsing quint evidence command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["quint", "evidence", "run-123", "--level", "L2"])
        self.assertEqual(args.func, cli_main.cmd_quint_evidence)
        self.assertEqual(args.run_id, "run-123")
        self.assertEqual(args.level, "L2")

    def test_parse_quint_drr(self) -> None:
        """Test parsing quint drr command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["quint", "drr", "run-123"])
        self.assertEqual(args.func, cli_main.cmd_quint_drr)

    def test_parse_validate(self) -> None:
        """Test parsing validate command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["validate"])
        self.assertEqual(args.func, cli_main.cmd_validate)

    def test_parse_list(self) -> None:
        """Test parsing list command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["list", "--module", "core"])
        self.assertEqual(args.func, cli_main.cmd_list)
        self.assertEqual(args.module, "core")

    def test_parse_providers(self) -> None:
        """Test parsing providers command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["providers"])
        self.assertEqual(args.func, cli_main.cmd_providers)

    def test_parse_history(self) -> None:
        """Test parsing history command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["history", "--limit", "5"])
        self.assertEqual(args.func, cli_main.cmd_history)
        self.assertEqual(args.limit, 5)

    def test_parse_status(self) -> None:
        """Test parsing status command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["status", "run-123"])
        self.assertEqual(args.func, cli_main.cmd_status)

    def test_parse_run(self) -> None:
        """Test parsing run command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["run", "core", "prd", "--agent", "bmad"])
        self.assertEqual(args.func, cli_main.cmd_run)
        self.assertEqual(args.module, "core")
        self.assertEqual(args.workflow, "prd")
        self.assertEqual(args.agent, "bmad")

    def test_parse_export(self) -> None:
        """Test parsing export command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["export", "run-123", "--report"])
        self.assertEqual(args.func, cli_main.cmd_export)
        self.assertTrue(args.report)


class TestMain(unittest.TestCase):
    """Tests for main function."""

    def test_main_calls_func(self) -> None:
        """Test main calls the command function."""
        with mock.patch("cli.main.build_parser") as mock_parser:
            mock_args = mock.Mock()
            mock_args.func.return_value = 0
            mock_parser.return_value.parse_args.return_value = mock_args
            result = cli_main.main()
            self.assertEqual(result, 0)
            mock_args.func.assert_called_once_with(mock_args)


class TestAutomationDecision(unittest.TestCase):
    """Tests for _automation_decision."""

    def test_no_agent_returns_none(self) -> None:
        """Test returns None when no agent specified."""
        config: Dict[str, Any] = {}
        spec = mock.Mock()
        args = argparse.Namespace(agent=None, auto=False, manual=False)
        result = cli_main._automation_decision(config, spec, args)
        self.assertIsNone(result)

    def test_auto_flag_returns_true(self) -> None:
        """Test returns True when --auto flag set."""
        config: Dict[str, Any] = {"automation": {"phases": ["planning"]}}
        spec = mock.Mock()
        spec.phase = "other"
        args = argparse.Namespace(agent="bmad", auto=True, manual=False)
        result = cli_main._automation_decision(config, spec, args)
        self.assertTrue(result)

    def test_manual_flag_returns_false(self) -> None:
        """Test returns False when --manual flag set."""
        config: Dict[str, Any] = {"automation": {"phases": ["planning"]}}
        spec = mock.Mock()
        spec.phase = "other"
        args = argparse.Namespace(agent="bmad", auto=False, manual=True)
        result = cli_main._automation_decision(config, spec, args)
        self.assertFalse(result)

    def test_phase_in_list_returns_none(self) -> None:
        """Test returns None when phase is in automation list."""
        config: Dict[str, Any] = {"automation": {"phases": ["planning"]}}
        spec = mock.Mock()
        spec.phase = "planning"
        args = argparse.Namespace(agent="bmad", auto=False, manual=False)
        result = cli_main._automation_decision(config, spec, args)
        self.assertIsNone(result)

    def test_no_phases_returns_none(self) -> None:
        """Test returns None when no phases configured."""
        config: Dict[str, Any] = {"automation": {}}
        spec = mock.Mock()
        spec.phase = "planning"
        args = argparse.Namespace(agent="bmad", auto=False, manual=False)
        result = cli_main._automation_decision(config, spec, args)
        self.assertIsNone(result)


class TestCmdHistory(unittest.TestCase):
    """Tests for cmd_history."""

    def test_history_empty(self) -> None:
        """Test history with no runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    with mock.patch("cli.main.storage.list_runs") as mock_list:
                        mock_list.return_value = []
                        args = argparse.Namespace(config=None, limit=None)
                        with mock.patch("builtins.print"):
                            result = cli_main.cmd_history(args)
                            self.assertEqual(result, 0)

    def test_history_with_limit(self) -> None:
        """Test history with limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    with mock.patch("cli.main.storage.list_runs") as mock_list:
                        mock_list.return_value = []
                        args = argparse.Namespace(config=None, limit=5)
                        with mock.patch("builtins.print"):
                            result = cli_main.cmd_history(args)
                            self.assertEqual(result, 0)


class TestCmdStatus(unittest.TestCase):
    """Tests for cmd_status."""

    def test_status_reads_manifest(self) -> None:
        """Test status reads and prints manifest."""
        manifest = {"run_id": "test", "status": "completed"}
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    with mock.patch("cli.main.storage.read_manifest") as mock_read:
                        mock_read.return_value = manifest
                        args = argparse.Namespace(config=None, run_id="test")
                        with mock.patch("builtins.print"):
                            result = cli_main.cmd_status(args)
                            self.assertEqual(result, 0)


class TestCmdExport(unittest.TestCase):
    """Tests for cmd_export."""

    def test_export_to_stdout(self) -> None:
        """Test export prints to stdout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    with mock.patch("cli.main.storage.update_timeline"):
                        with mock.patch("cli.main.storage.read_manifest") as m1:
                            m1.return_value = {}
                            with mock.patch("cli.main.storage.read_approvals") as m2:
                                m2.return_value = []
                                with mock.patch("cli.main.storage.read_human_gates") as m3:
                                    m3.return_value = []
                                    with mock.patch("cli.main.storage.read_events") as m4:
                                        m4.return_value = []
                                        with mock.patch(
                                            "cli.main.storage.read_artifact_index"
                                        ) as m5:
                                            m5.return_value = []
                                            with mock.patch(
                                                "cli.main.storage.read_tool_results"
                                            ) as m6:
                                                m6.return_value = []
                                                with mock.patch(
                                                    "cli.main.storage.read_evidence_links"
                                                ) as m7:
                                                    m7.return_value = {}
                                                    with mock.patch(
                                                        "cli.main.storage.read_drrs"
                                                    ) as m8:
                                                        m8.return_value = {}
                                                        with mock.patch(
                                                            "cli.main.storage.read_timeline"
                                                        ) as m9:
                                                            m9.return_value = {}
                                                            args = argparse.Namespace(
                                                                config=None,
                                                                run_id="run-123",
                                                                output=None,
                                                                report=False,
                                                            )
                                                            with mock.patch("builtins.print"):
                                                                result = cli_main.cmd_export(args)
                                                                self.assertEqual(result, 0)

    def test_export_to_file(self) -> None:
        """Test export writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "export.json"
            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    with mock.patch("cli.main.storage.update_timeline"):
                        with mock.patch("cli.main.storage.read_manifest") as m1:
                            m1.return_value = {}
                            with mock.patch("cli.main.storage.read_approvals") as m2:
                                m2.return_value = []
                                with mock.patch("cli.main.storage.read_human_gates") as m3:
                                    m3.return_value = []
                                    with mock.patch("cli.main.storage.read_events") as m4:
                                        m4.return_value = []
                                        with mock.patch(
                                            "cli.main.storage.read_artifact_index"
                                        ) as m5:
                                            m5.return_value = []
                                            with mock.patch(
                                                "cli.main.storage.read_tool_results"
                                            ) as m6:
                                                m6.return_value = []
                                                with mock.patch(
                                                    "cli.main.storage.read_evidence_links"
                                                ) as m7:
                                                    m7.return_value = {}
                                                    with mock.patch(
                                                        "cli.main.storage.read_drrs"
                                                    ) as m8:
                                                        m8.return_value = {}
                                                        with mock.patch(
                                                            "cli.main.storage.read_timeline"
                                                        ) as m9:
                                                            m9.return_value = {}
                                                            args = argparse.Namespace(
                                                                config=None,
                                                                run_id="run-123",
                                                                output=str(output_file),
                                                                report=False,
                                                            )
                                                            with mock.patch("builtins.print"):
                                                                result = cli_main.cmd_export(args)
                                                                self.assertEqual(result, 0)
                                                                self.assertTrue(
                                                                    output_file.exists()
                                                                )


class TestCmdRun(unittest.TestCase):
    """Tests for cmd_run."""

    def test_run_basic(self) -> None:
        """Test basic run command."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_eng = mock.Mock()
                mock_eng.get_workflow_spec.return_value = mock.Mock(phase="planning")
                mock_eng.run.return_value = {"run_id": "test", "status": "completed"}
                mock_engine.return_value = mock_eng
                args = argparse.Namespace(
                    config=None,
                    module="core",
                    workflow="prd",
                    run_id=None,
                    agent=None,
                    provider=None,
                    orchestrate=False,
                    auto=False,
                    manual=False,
                )
                with mock.patch("builtins.print"):
                    result = cli_main.cmd_run(args)
                    self.assertEqual(result, 0)

    def test_run_with_agent(self) -> None:
        """Test run command with agent."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {"automation": {"phases": ["planning"]}}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_eng = mock.Mock()
                mock_eng.get_workflow_spec.return_value = mock.Mock(phase="planning")
                mock_eng.run.return_value = {"run_id": "test", "status": "completed"}
                mock_engine.return_value = mock_eng
                with mock.patch("cli.main.ProviderRegistry") as mock_registry:
                    mock_registry.return_value.get.return_value = mock.Mock()
                    with mock.patch("cli.main.execution.PlanExecutor"):
                        args = argparse.Namespace(
                            config=None,
                            module="core",
                            workflow="prd",
                            run_id="run-123",
                            agent="bmad",
                            provider="mock",
                            orchestrate=False,
                            auto=False,
                            manual=False,
                        )
                        with mock.patch("builtins.print"):
                            result = cli_main.cmd_run(args)
                            self.assertEqual(result, 0)


class TestCmdResume(unittest.TestCase):
    """Tests for cmd_resume."""

    def test_resume_basic(self) -> None:
        """Test basic resume command."""
        manifest = {
            "workflow": {
                "module": "core",
                "workflow": "prd",
                "phase": "planning",
                "quint": "enabled",
                "telis": "enabled",
                "validation": "none",
                "human": "false",
                "evidence": "L1",
                "scope": "full",
                "path": "/path",
                "artifacts": [],
            }
        }
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                mock_root.return_value = Path("/tmp")
                with mock.patch("cli.main.storage.read_manifest") as mock_read:
                    mock_read.return_value = manifest
                    with mock.patch("cli.main._engine") as mock_engine:
                        mock_eng = mock.Mock()
                        mock_eng.resume.return_value = {"run_id": "test", "status": "completed"}
                        mock_engine.return_value = mock_eng
                        args = argparse.Namespace(
                            config=None,
                            run_id="run-123",
                            agent=None,
                            provider=None,
                            auto=False,
                            manual=False,
                        )
                        with mock.patch("builtins.print"):
                            result = cli_main.cmd_resume(args)
                            self.assertEqual(result, 0)


class TestCmdOrchestrate(unittest.TestCase):
    """Tests for cmd_orchestrate."""

    def test_orchestrate_basic(self) -> None:
        """Test basic orchestrate command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.json"
            plan_path.write_text(json.dumps({"workflows": []}), encoding="ascii")
            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.orchestrator_engine.WorkflowOrchestrator") as mock_orch:
                    mock_inst = mock.Mock()
                    mock_inst.plan_execution.return_value = []
                    mock_inst.execute_plan.return_value = []
                    mock_orch.return_value = mock_inst
                    args = argparse.Namespace(config=None, plan=str(plan_path))
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_orchestrate(args)
                        self.assertEqual(result, 0)


class TestCmdApprove(unittest.TestCase):
    """Tests for cmd_approve."""

    def test_approve_basic(self) -> None:
        """Test basic approve command."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_eng = mock.Mock()
                mock_eng.approve_gate.return_value = [{"gate": "test"}]
                mock_engine.return_value = mock_eng
                args = argparse.Namespace(
                    config=None, run_id="run-123", by="tester", notes="approved"
                )
                with mock.patch("builtins.print"):
                    result = cli_main.cmd_approve(args)
                    self.assertEqual(result, 0)


class TestCmdInteractive(unittest.TestCase):
    """Tests for cmd_interactive."""

    def test_interactive_with_workflow(self) -> None:
        """Test interactive with specific workflow."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_engine.return_value = mock.Mock()
                with mock.patch("cli.interactive.InteractiveCLI") as mock_cli:
                    mock_inst = mock.Mock()
                    mock_inst.run_workflow.return_value = "run-123"
                    mock_cli.return_value = mock_inst
                    args = argparse.Namespace(
                        config=None,
                        module="core",
                        workflow="prd",
                        run_id=None,
                        provider=None,
                    )
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_interactive(args)
                        self.assertEqual(result, 0)

    def test_interactive_session(self) -> None:
        """Test interactive session mode."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_engine.return_value = mock.Mock()
                with mock.patch("cli.interactive.InteractiveCLI") as mock_cli:
                    mock_inst = mock.Mock()
                    mock_cli.return_value = mock_inst
                    args = argparse.Namespace(
                        config=None,
                        module=None,
                        workflow=None,
                        run_id=None,
                        provider=None,
                    )
                    result = cli_main.cmd_interactive(args)
                    self.assertEqual(result, 0)
                    mock_inst.run_interactive_session.assert_called_once()

    def test_interactive_failed(self) -> None:
        """Test interactive when workflow fails."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_engine.return_value = mock.Mock()
                with mock.patch("cli.interactive.InteractiveCLI") as mock_cli:
                    mock_inst = mock.Mock()
                    mock_inst.run_workflow.return_value = None
                    mock_cli.return_value = mock_inst
                    args = argparse.Namespace(
                        config=None,
                        module="core",
                        workflow="prd",
                        run_id=None,
                        provider=None,
                    )
                    result = cli_main.cmd_interactive(args)
                    self.assertEqual(result, 1)


class TestCmdStart(unittest.TestCase):
    """Tests for cmd_start."""

    def test_start_default(self) -> None:
        """Test start with defaults."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_engine.return_value = mock.Mock()
                with mock.patch("cli.interactive.InteractiveCLI") as mock_cli:
                    mock_inst = mock.Mock()
                    mock_inst.run_workflow.return_value = "run-123"
                    mock_cli.return_value = mock_inst
                    args = argparse.Namespace(
                        config=None,
                        module=None,
                        workflow=None,
                        provider=None,
                    )
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_start(args)
                        self.assertEqual(result, 0)

    def test_start_failed(self) -> None:
        """Test start when workflow fails."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_engine.return_value = mock.Mock()
                with mock.patch("cli.interactive.InteractiveCLI") as mock_cli:
                    mock_inst = mock.Mock()
                    mock_inst.run_workflow.return_value = None
                    mock_cli.return_value = mock_inst
                    args = argparse.Namespace(
                        config=None, module="core", workflow="prd", provider=None
                    )
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_start(args)
                        self.assertEqual(result, 1)


class TestPromptAutomationChoice(unittest.TestCase):
    """Tests for _prompt_automation_choice."""

    def test_prompt_automation_yes(self) -> None:
        """Test prompt automation returns True for yes."""
        spec = mock.Mock()
        spec.phase = "planning"
        spec.module = "core"
        spec.workflow = "prd"
        with mock.patch("builtins.input", return_value="a"):
            with mock.patch("builtins.print"):
                result = cli_main._prompt_automation_choice(spec)
                self.assertTrue(result)

    def test_prompt_automation_no(self) -> None:
        """Test prompt automation returns False for no."""
        spec = mock.Mock()
        spec.phase = "planning"
        spec.module = "core"
        spec.workflow = "prd"
        with mock.patch("builtins.input", return_value="m"):
            with mock.patch("builtins.print"):
                result = cli_main._prompt_automation_choice(spec)
                self.assertFalse(result)

    def test_prompt_automation_eof(self) -> None:
        """Test prompt automation returns False on EOF."""
        spec = mock.Mock()
        spec.phase = "planning"
        spec.module = "core"
        spec.workflow = "prd"
        with mock.patch("builtins.input", side_effect=EOFError):
            with mock.patch("builtins.print"):
                result = cli_main._prompt_automation_choice(spec)
                self.assertFalse(result)


class TestAutomationDecisionInteractive(unittest.TestCase):
    """Tests for _automation_decision interactive mode."""

    def test_interactive_prompt(self) -> None:
        """Test interactive prompt when tty."""
        config: Dict[str, Any] = {"automation": {"phases": ["other"]}}
        spec = mock.Mock()
        spec.phase = "planning"
        args = argparse.Namespace(agent="bmad", auto=False, manual=False)
        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with mock.patch("cli.main._prompt_automation_choice") as mock_prompt:
                mock_prompt.return_value = True
                result = cli_main._automation_decision(config, spec, args)
                self.assertTrue(result)

    def test_non_tty_returns_false(self) -> None:
        """Test non-tty returns False."""
        config: Dict[str, Any] = {"automation": {"phases": ["other"]}}
        spec = mock.Mock()
        spec.phase = "planning"
        args = argparse.Namespace(agent="bmad", auto=False, manual=False)
        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = cli_main._automation_decision(config, spec, args)
            self.assertFalse(result)


class TestLoadPlanFileYaml(unittest.TestCase):
    """Tests for _load_plan_file with YAML."""

    def test_load_yaml_plan(self) -> None:
        """Test loading YAML plan file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.yaml"
            path.write_text("workflows: []", encoding="ascii")
            with mock.patch("cli.main.yaml") as mock_yaml:
                mock_yaml.safe_load.return_value = {"workflows": []}
                result = cli_main._load_plan_file(str(path))
                self.assertEqual(result, {"workflows": []})

    def test_load_yaml_no_yaml_module(self) -> None:
        """Test loading YAML plan without PyYAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.yaml"
            path.write_text("workflows: []", encoding="ascii")
            original_yaml = cli_main.yaml
            try:
                cli_main.yaml = None
                with self.assertRaises(RuntimeError):
                    cli_main._load_plan_file(str(path))
            finally:
                cli_main.yaml = original_yaml


class TestCmdExportReport(unittest.TestCase):
    """Tests for cmd_export with report flag."""

    def test_export_with_report(self) -> None:
        """Test export with --report flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    with mock.patch("cli.main.storage.update_timeline"):
                        with mock.patch("cli.main.RunReportGenerator") as mock_gen:
                            mock_report = mock.Mock()
                            mock_report.to_dict.return_value = {"summary": {}}
                            mock_gen.return_value.generate.return_value = mock_report
                            args = argparse.Namespace(
                                config=None,
                                run_id="run-123",
                                output=None,
                                report=True,
                            )
                            with mock.patch("builtins.print"):
                                result = cli_main.cmd_export(args)
                                self.assertEqual(result, 0)


class TestTelisAddYaml(unittest.TestCase):
    """Tests for cmd_telis_add with YAML."""

    def test_telis_add_yaml_no_module(self) -> None:
        """Test telis add YAML without PyYAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "shards.yaml"
            path.write_text("shards: []", encoding="utf-8")
            original_yaml = cli_main.yaml
            try:
                cli_main.yaml = None
                args = argparse.Namespace(file=str(path))
                with mock.patch("builtins.print") as mock_print:
                    result = cli_main.cmd_telis_add(args)
                    self.assertEqual(result, 1)
                    calls = [str(c) for c in mock_print.call_args_list]
                    self.assertTrue(any("PyYAML" in c for c in calls))
            finally:
                cli_main.yaml = original_yaml


class TestCmdRunOrchestrate(unittest.TestCase):
    """Tests for cmd_run with --orchestrate."""

    def test_run_with_orchestrate(self) -> None:
        """Test run command with --orchestrate flag."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_eng = mock.Mock()
                mock_eng.get_workflow_spec.return_value = mock.Mock(phase="planning")
                mock_engine.return_value = mock_eng
                with mock.patch("cli.main.orchestrator_engine.WorkflowOrchestrator") as mock_orch:
                    mock_orch_inst = mock.Mock()
                    mock_orch_inst.plan_execution.return_value = []
                    mock_orch_inst.execute_plan.return_value = [
                        {"run_id": "test", "status": "completed"}
                    ]
                    mock_orch.return_value = mock_orch_inst
                    args = argparse.Namespace(
                        config=None,
                        module="core",
                        workflow="prd",
                        run_id=None,
                        agent="bmad",
                        provider="mock",
                        orchestrate=True,
                        auto=False,
                        manual=False,
                    )
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_run(args)
                        self.assertEqual(result, 0)


class TestCmdResumeWithAgent(unittest.TestCase):
    """Tests for cmd_resume with agent."""

    def test_resume_with_agent_and_provider(self) -> None:
        """Test resume command with agent and provider."""
        manifest = {
            "workflow": {
                "module": "core",
                "workflow": "prd",
                "phase": "planning",
                "quint": "enabled",
                "telis": "enabled",
                "validation": "none",
                "human": "false",
                "evidence": "L1",
                "scope": "full",
                "path": "/path",
                "artifacts": [],
            }
        }
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {"automation": {"phases": ["planning"]}}
            with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                mock_root.return_value = Path("/tmp")
                with mock.patch("cli.main.storage.read_manifest") as mock_read:
                    mock_read.return_value = manifest
                    with mock.patch("cli.main._engine") as mock_engine:
                        mock_eng = mock.Mock()
                        mock_eng.resume.return_value = {
                            "run_id": "test",
                            "status": "completed",
                        }
                        mock_engine.return_value = mock_eng
                        with mock.patch("cli.main.ProviderRegistry") as mock_reg:
                            mock_reg.return_value.get.return_value = mock.Mock()
                            with mock.patch("cli.main.execution.PlanExecutor"):
                                args = argparse.Namespace(
                                    config=None,
                                    run_id="run-123",
                                    agent="bmad",
                                    provider="mock",
                                    auto=False,
                                    manual=False,
                                )
                                with mock.patch("builtins.print"):
                                    result = cli_main.cmd_resume(args)
                                    self.assertEqual(result, 0)


class TestCmdInteractiveWithProvider(unittest.TestCase):
    """Tests for cmd_interactive with provider."""

    def test_interactive_with_provider(self) -> None:
        """Test interactive with provider specified."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_engine.return_value = mock.Mock()
                with mock.patch("cli.main.ProviderRegistry") as mock_reg:
                    mock_reg.return_value.get.return_value = mock.Mock()
                    with mock.patch("cli.interactive.InteractiveCLI") as mock_cli:
                        mock_inst = mock.Mock()
                        mock_inst.run_workflow.return_value = "run-123"
                        mock_cli.return_value = mock_inst
                        args = argparse.Namespace(
                            config=None,
                            module="core",
                            workflow="prd",
                            run_id="existing-run",
                            provider="mock",
                        )
                        with mock.patch("builtins.print"):
                            result = cli_main.cmd_interactive(args)
                            self.assertEqual(result, 0)


class TestCmdStartWithProvider(unittest.TestCase):
    """Tests for cmd_start with provider."""

    def test_start_with_provider(self) -> None:
        """Test start with provider specified."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_engine.return_value = mock.Mock()
                with mock.patch("cli.main.ProviderRegistry") as mock_reg:
                    mock_reg.return_value.get.return_value = mock.Mock()
                    with mock.patch("cli.interactive.InteractiveCLI") as mock_cli:
                        mock_inst = mock.Mock()
                        mock_inst.run_workflow.return_value = "run-123"
                        mock_cli.return_value = mock_inst
                        args = argparse.Namespace(
                            config=None,
                            module=None,
                            workflow=None,
                            provider="mock",
                        )
                        with mock.patch("builtins.print"):
                            result = cli_main.cmd_start(args)
                            self.assertEqual(result, 0)


class TestCmdHistoryWithRuns(unittest.TestCase):
    """Tests for cmd_history with actual runs."""

    def test_history_with_runs(self) -> None:
        """Test history with multiple runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    with mock.patch("cli.main.storage.list_runs") as mock_list:
                        mock_list.return_value = [
                            Path(tmpdir) / "run-1",
                            Path(tmpdir) / "run-2",
                        ]
                        with mock.patch("cli.main.storage.read_manifest") as mock_read:
                            mock_read.side_effect = [
                                {
                                    "run_id": "run-1",
                                    "status": "completed",
                                    "workflow": {"module": "core", "workflow": "prd"},
                                    "steps": [],
                                    "updated_at": "2024-01-01T00:00:00Z",
                                },
                                {
                                    "run_id": "run-2",
                                    "status": "blocked",
                                    "workflow": {"module": "core", "workflow": "arch"},
                                    "steps": [],
                                    "updated_at": "2024-01-02T00:00:00Z",
                                },
                            ]
                            args = argparse.Namespace(config=None, limit=None)
                            with mock.patch("builtins.print"):
                                result = cli_main.cmd_history(args)
                                self.assertEqual(result, 0)


class TestLoadOrchestrationNodesEdgeCases(unittest.TestCase):
    """Tests for _load_orchestration_nodes edge cases."""

    def test_non_list_workflows(self) -> None:
        """Test with non-list workflows value."""
        data = {"workflows": "not a list"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text(json.dumps(data), encoding="ascii")
            result = cli_main._load_orchestration_nodes(str(path))
            self.assertEqual(result, [])

    def test_non_dict_workflow_item(self) -> None:
        """Test with non-dict workflow items."""
        data = {"workflows": ["not a dict", {"module": "core", "workflow": "prd"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text(json.dumps(data), encoding="ascii")
            result = cli_main._load_orchestration_nodes(str(path))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].module, "core")

    def test_missing_module_or_workflow(self) -> None:
        """Test with missing module or workflow."""
        data = {
            "workflows": [
                {"module": "core"},  # Missing workflow
                {"workflow": "prd"},  # Missing module
                {"module": "core", "workflow": "prd"},  # Valid
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text(json.dumps(data), encoding="ascii")
            result = cli_main._load_orchestration_nodes(str(path))
            self.assertEqual(len(result), 1)

    def test_depends_on_field(self) -> None:
        """Test with depends_on field."""
        data = {
            "workflows": [
                {
                    "module": "core",
                    "workflow": "prd",
                    "depends_on": ["brainstorm"],
                    "agent": "bmad",
                    "provider": "mock",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "plan.json"
            path.write_text(json.dumps(data), encoding="ascii")
            result = cli_main._load_orchestration_nodes(str(path))
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].dependencies, ["brainstorm"])
            self.assertEqual(result[0].agent, "bmad")
            self.assertEqual(result[0].provider, "mock")


class TestQuintEvidenceEdgeCases(unittest.TestCase):
    """Tests for QUINT evidence edge cases."""

    def test_evidence_no_claim(self) -> None:
        """Test evidence record without claim."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "evidence.json").write_text(
                json.dumps(
                    {
                        "evidence": [
                            {
                                "evidence_id": "e1",
                                "level": "L1",
                                "evidence_type": "assertion",
                                "source_step": "step1",
                            }
                        ]
                    }
                )
            )

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123", level=None)
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_quint_evidence(args)
                        self.assertEqual(result, 0)


class TestQuintStatusNoEvidence(unittest.TestCase):
    """Tests for QUINT status without evidence."""

    def test_quint_status_no_evidence_list(self) -> None:
        """Test quint status with empty evidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run-123"
            run_dir.mkdir()
            (run_dir / "evidence.json").write_text(json.dumps({"evidence": []}))
            (run_dir / "drr.json").write_text(json.dumps({"drrs": []}))
            (run_dir / "fingerprints.json").write_text(json.dumps({}))

            with mock.patch("cli.main._load_config") as mock_config:
                mock_config.return_value = {}
                with mock.patch("cli.main.runtime_config.storage_root") as mock_root:
                    mock_root.return_value = Path(tmpdir)
                    args = argparse.Namespace(config=None, run_id="run-123")
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_quint_status(args)
                        self.assertEqual(result, 0)


class TestCmdRunDecision(unittest.TestCase):
    """Tests for cmd_run with automation decision."""

    def test_run_with_automation_decision_true(self) -> None:
        """Test run when automation decision returns True."""
        with mock.patch("cli.main._load_config") as mock_config:
            mock_config.return_value = {"automation": {"phases": []}}
            with mock.patch("cli.main._engine") as mock_engine:
                mock_eng = mock.Mock()
                mock_eng.get_workflow_spec.return_value = mock.Mock(phase="planning")
                mock_eng.run.return_value = {"run_id": "test", "status": "completed"}
                mock_engine.return_value = mock_eng
                args = argparse.Namespace(
                    config=None,
                    module="core",
                    workflow="prd",
                    run_id=None,
                    agent="bmad",
                    provider=None,
                    orchestrate=False,
                    auto=True,
                    manual=False,
                )
                with mock.patch("cli.main.execution.PlanExecutor"):
                    with mock.patch("builtins.print"):
                        result = cli_main.cmd_run(args)
                        self.assertEqual(result, 0)


class TestParseAdditionalCommands(unittest.TestCase):
    """Tests for parsing additional commands."""

    def test_parse_resume(self) -> None:
        """Test parsing resume command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["resume", "run-123", "--agent", "bmad", "--auto"])
        self.assertEqual(args.func, cli_main.cmd_resume)
        self.assertEqual(args.run_id, "run-123")
        self.assertEqual(args.agent, "bmad")
        self.assertTrue(args.auto)

    def test_parse_orchestrate(self) -> None:
        """Test parsing orchestrate command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["orchestrate", "--plan", "/path/to/plan.json"])
        self.assertEqual(args.func, cli_main.cmd_orchestrate)
        self.assertEqual(args.plan, "/path/to/plan.json")

    def test_parse_approve(self) -> None:
        """Test parsing approve command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["approve", "run-123", "--by", "tester", "--notes", "looks good"])
        self.assertEqual(args.func, cli_main.cmd_approve)
        self.assertEqual(args.run_id, "run-123")
        self.assertEqual(args.by, "tester")
        self.assertEqual(args.notes, "looks good")

    def test_parse_interactive(self) -> None:
        """Test parsing interactive command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(
            [
                "interactive",
                "--module",
                "core",
                "--workflow",
                "prd",
                "--provider",
                "mock",
            ]
        )
        self.assertEqual(args.func, cli_main.cmd_interactive)
        self.assertEqual(args.module, "core")
        self.assertEqual(args.workflow, "prd")
        self.assertEqual(args.provider, "mock")

    def test_parse_start(self) -> None:
        """Test parsing start command."""
        parser = cli_main.build_parser()
        args = parser.parse_args(["start", "--module", "bmm", "--provider", "mock"])
        self.assertEqual(args.func, cli_main.cmd_start)
        self.assertEqual(args.module, "bmm")
        self.assertEqual(args.provider, "mock")


if __name__ == "__main__":
    unittest.main()
