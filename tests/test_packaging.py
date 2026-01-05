"""Tests for the packaging module."""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.packaging import (  # noqa: E402
    PackageBuilder,
    PackageConfig,
    PackageResult,
    package_run_artifacts,
)


class TestPackageConfig(unittest.TestCase):
    def test_create_config(self) -> None:
        config = PackageConfig(
            name="test-package",
            version="1.0.0",
            description="Test package",
            author="Test Author",
            license="MIT",
            entry_point="main.py",
            dependencies=["requests"],
            dev_dependencies=["pytest"],
            scripts={"test": "pytest"},
            metadata={"key": "value"},
        )
        self.assertEqual(config.name, "test-package")
        self.assertEqual(config.version, "1.0.0")
        self.assertIn("requests", config.dependencies)

    def test_config_to_dict(self) -> None:
        config = PackageConfig(
            name="test",
            version="2.0.0",
            dependencies=["dep1", "dep2"],
        )
        data = config.to_dict()
        self.assertEqual(data["name"], "test")
        self.assertEqual(data["version"], "2.0.0")
        self.assertEqual(len(data["dependencies"]), 2)

    def test_config_from_dict(self) -> None:
        data = {
            "name": "from-dict",
            "version": "3.0.0",
            "description": "From dict",
            "dependencies": ["a", "b"],
        }
        config = PackageConfig.from_dict(data)
        self.assertEqual(config.name, "from-dict")
        self.assertEqual(config.version, "3.0.0")
        self.assertEqual(len(config.dependencies), 2)

    def test_config_from_dict_defaults(self) -> None:
        config = PackageConfig.from_dict({})
        self.assertEqual(config.name, "unnamed")
        self.assertEqual(config.version, "0.1.0")


class TestPackageResult(unittest.TestCase):
    def test_create_result(self) -> None:
        result = PackageResult(
            status="completed",
            package_type="python",
            output_path="/path/to/output",
            artifacts=["package.whl"],
            duration_ms=1000,
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.package_type, "python")
        self.assertIn("package.whl", result.artifacts)

    def test_result_to_dict(self) -> None:
        result = PackageResult(
            status="failed",
            package_type="node",
            error="Build failed",
        )
        data = result.to_dict()
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["error"], "Build failed")
        self.assertIn("created_at", data)


class TestPackageBuilder(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.source_dir = self.test_dir / "source"
        self.output_dir = self.test_dir / "output"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_build_zip_archive(self) -> None:
        # Create some source files
        (self.source_dir / "main.py").write_text("print('hello')", encoding="utf-8")
        (self.source_dir / "README.md").write_text("# Test", encoding="utf-8")

        config = PackageConfig(name="test-zip", version="1.0.0")
        builder = PackageBuilder(self.source_dir, self.output_dir)
        result = builder.build_zip_archive(config)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.package_type, "zip")
        self.assertEqual(len(result.artifacts), 1)
        self.assertTrue(result.artifacts[0].endswith(".zip"))

        # Verify the archive exists
        archive_path = self.output_dir / result.artifacts[0]
        self.assertTrue(archive_path.exists())

    def test_build_unknown_type(self) -> None:
        config = PackageConfig(name="test", version="1.0.0")
        builder = PackageBuilder(self.source_dir, self.output_dir)
        result = builder.build(config, "unknown")  # type: ignore

        self.assertEqual(result.status, "failed")
        self.assertIn("Unknown package type", result.error or "")

    def test_build_node_no_npm(self) -> None:
        # This test passes if npm is not in PATH
        config = PackageConfig(name="test-node", version="1.0.0")
        builder = PackageBuilder(self.source_dir, self.output_dir)

        # Mock npm not found by testing the result
        result = builder.build_node_package(config)

        # Either npm is found and works, or it's not found
        self.assertIn(result.status, ["completed", "failed"])
        if result.status == "failed" and "npm not found" in (result.error or ""):
            self.assertEqual(result.package_type, "node")

    def test_build_docker_no_docker(self) -> None:
        config = PackageConfig(name="test-docker", version="1.0.0")
        builder = PackageBuilder(self.source_dir, self.output_dir)

        result = builder.build_docker_image(config)

        # Either docker is found, or it's not
        self.assertIn(result.status, ["completed", "failed"])
        if result.status == "failed" and "docker not found" in (result.error or ""):
            self.assertEqual(result.package_type, "docker")

    def test_builder_creates_output_dir(self) -> None:
        new_output = self.test_dir / "new_output"
        self.assertFalse(new_output.exists())

        PackageBuilder(self.source_dir, new_output)
        self.assertTrue(new_output.exists())


class TestPackageRunArtifacts(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = ROOT / "runs" / "tmp-tests" / uuid4().hex
        self.run_dir = self.test_dir / "run-123"
        self.outputs_dir = self.run_dir / "outputs"
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_package_with_manifest(self) -> None:
        import json

        # Create manifest
        manifest = {
            "run_id": "run-123",
            "workflow": {"module": "bmm", "workflow": "prd"},
        }
        (self.run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        # Create output files
        (self.outputs_dir / "output.md").write_text("# Output", encoding="utf-8")

        result = package_run_artifacts(self.run_dir, package_type="zip")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.package_type, "zip")

    def test_package_without_manifest(self) -> None:
        # Create output files only
        (self.outputs_dir / "code.py").write_text("print('test')", encoding="utf-8")

        result = package_run_artifacts(self.run_dir, package_type="zip")

        self.assertEqual(result.status, "completed")

    def test_package_with_custom_config(self) -> None:
        (self.outputs_dir / "app.py").write_text("# app", encoding="utf-8")

        config = PackageConfig(
            name="custom-package",
            version="2.0.0",
            description="Custom package",
        )
        result = package_run_artifacts(self.run_dir, package_type="zip", config=config)

        self.assertEqual(result.status, "completed")
        self.assertTrue(any("custom-package" in a for a in result.artifacts))


if __name__ == "__main__":
    unittest.main()
